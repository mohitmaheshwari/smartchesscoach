"""
Pick 10 stratified games for Parth's caption-template authoring round.

Pulls from the active 1600 games and picks 2 from each of 5 buckets so
Parth sees variety in his first authoring batch:

  bucket 1 — TACTICAL_BLUNDER: at least one user move with cp_loss >= 200
             (the kind where R12 fires)
  bucket 2 — POSITIONAL_MISTAKE: at least one user move with cp_loss in
             [50, 150] and is_exchange_losing False (eval drop without
             a clean material reason — the Ne7-style cases)
  bucket 3 — ENDGAME: game reaches endgame phase (any move with
             phase == "endgame")
  bucket 4 — OPENING_DRIFT: at least one user move in opening with
             cp_loss in [30, 100] (subtle opening miss)
  bucket 5 — WON_WITH_BLUNDER: result is a win for user but the game
             contains at least one blunder (cp_loss >= 200)

Output: 10 game_ids + brief summary per game (result, blunder count,
critical move). Parth opens each in /lab review.

Usage:
    docker exec -it chess-coach-backend python scripts/pick_authoring_games.py
    docker exec -it chess-coach-backend python scripts/pick_authoring_games.py --output /tmp/parth_games.txt
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Set

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv
load_dotenv(BACKEND_DIR / ".env")

from motor.motor_asyncio import AsyncIOMotorClient


MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "chess_coach")


def _classify_game(v5_data: List[Dict], game_result: str, user_color: str) -> Set[str]:
    """Return the set of bucket labels this game qualifies for.
    A game can land in multiple buckets — we just need variety in picks.
    """
    buckets: Set[str] = set()
    user_won = (
        (game_result == "1-0" and user_color == "white")
        or (game_result == "0-1" and user_color == "black")
    )
    has_blunder = False
    has_positional = False
    has_endgame = False
    has_opening_drift = False
    for rec in v5_data:
        if not rec.get("is_user_move"):
            continue
        cpl = rec.get("cp_loss") or 0
        phase = rec.get("phase")
        # tactical blunder
        if cpl >= 200:
            buckets.add("TACTICAL_BLUNDER")
            has_blunder = True
        # positional mistake — eval drop but no clean material reason.
        # Use principles_violated as proxy: TAC_HANGING_PIECE absent.
        if 50 <= cpl <= 150:
            ev_pids = {(p or {}).get("principle_id")
                       for p in (rec.get("caption_facts_principles_violated") or [])}
            if "TAC_HANGING_PIECE" not in ev_pids and "TAC_DEFENDER_COUNT" not in ev_pids:
                buckets.add("POSITIONAL_MISTAKE")
                has_positional = True
        # endgame phase reached
        if phase == "endgame":
            has_endgame = True
        # opening drift
        if phase == "opening" and 30 <= cpl <= 100:
            buckets.add("OPENING_DRIFT")
            has_opening_drift = True
    if has_endgame:
        buckets.add("ENDGAME")
    if user_won and has_blunder:
        buckets.add("WON_WITH_BLUNDER")
    return buckets


def _short_summary(game_doc: Dict, analysis_doc: Dict) -> str:
    """One-line summary for the picked-games report."""
    result = game_doc.get("result", "?")
    opening = game_doc.get("opening") or game_doc.get("opening_name") or "?"
    user_color = game_doc.get("user_color", "?")
    sf = analysis_doc.get("stockfish_analysis", {}) or {}
    blunders = sf.get("blunders", 0) or 0
    mistakes = sf.get("mistakes", 0) or 0
    return (f"result={result}  color={user_color:5s}  opening={(opening or '?')[:30]:30s}  "
            f"blunders={blunders}  mistakes={mistakes}")


async def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--per-bucket", type=int, default=2,
                    help="Games to pick per bucket (default 2 → 10 total)")
    ap.add_argument("--output", type=str, default=None,
                    help="Also write report to this file")
    args = ap.parse_args()

    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    # Active games only — Parth shouldn't author against archived data.
    active_cursor = db.games.find(
        {"is_active": {"$ne": False}, "is_analyzed": True},
        {"_id": 0, "game_id": 1, "result": 1, "user_color": 1, "user_id": 1,
         "opening": 1, "opening_name": 1, "imported_at": 1},
    )
    active_games: Dict[str, Dict] = {}
    async for g in active_cursor:
        gid = g.get("game_id")
        if gid:
            active_games[gid] = g
    print(f"[picker] Active games scanned: {len(active_games)}", file=sys.stderr)

    # Walk game_analyses for each active game; classify into buckets.
    bucket_to_games: Dict[str, List[str]] = defaultdict(list)
    game_to_buckets: Dict[str, Set[str]] = {}
    game_to_analysis: Dict[str, Dict] = {}
    scanned = 0
    async for analysis in db.game_analyses.find(
        {"game_id": {"$in": list(active_games.keys())}},
        {"_id": 0, "game_id": 1, "decryption_v5_data": 1, "stockfish_analysis": 1},
    ):
        scanned += 1
        gid = analysis.get("game_id")
        if not gid or gid not in active_games:
            continue
        v5 = analysis.get("decryption_v5_data") or []
        if not v5:
            continue
        g = active_games[gid]
        buckets = _classify_game(v5, g.get("result", ""), g.get("user_color", "white"))
        if not buckets:
            continue
        game_to_buckets[gid] = buckets
        game_to_analysis[gid] = analysis
        for b in buckets:
            bucket_to_games[b].append(gid)
    print(f"[picker] Analyses scanned: {scanned}, classifiable: {len(game_to_buckets)}", file=sys.stderr)

    # Pick per bucket, prefer games NOT yet chosen for another bucket
    # (so we cover variety, not just hit the same game 5×).
    BUCKETS = ["TACTICAL_BLUNDER", "POSITIONAL_MISTAKE", "ENDGAME",
               "OPENING_DRIFT", "WON_WITH_BLUNDER"]
    picked: List[str] = []
    picked_set: Set[str] = set()
    for b in BUCKETS:
        candidates = [g for g in bucket_to_games.get(b, []) if g not in picked_set]
        # Order: most recent imports first (better signal for current product)
        candidates.sort(key=lambda gid: active_games[gid].get("imported_at") or "", reverse=True)
        chosen = candidates[:args.per_bucket]
        if len(chosen) < args.per_bucket:
            # Fall back to already-picked games if a bucket is thin
            extras = bucket_to_games.get(b, [])[:args.per_bucket - len(chosen)]
            chosen = chosen + [g for g in extras if g not in chosen]
        for gid in chosen[:args.per_bucket]:
            picked.append(gid)
            picked_set.add(gid)

    # Render report
    lines = []
    lines.append("\n── Picked authoring games ──────────────────────────────")
    lines.append(f"  Total picked: {len(picked)} (target {len(BUCKETS) * args.per_bucket})")
    lines.append("")
    pick_idx = 0
    for b in BUCKETS:
        lines.append(f"  ── bucket: {b} ──")
        for _ in range(args.per_bucket):
            if pick_idx >= len(picked):
                break
            gid = picked[pick_idx]
            pick_idx += 1
            g = active_games.get(gid, {})
            a = game_to_analysis.get(gid, {})
            buckets = sorted(game_to_buckets.get(gid, set()))
            lines.append(f"    {gid}  buckets={buckets}")
            lines.append(f"      {_short_summary(g, a)}")
        lines.append("")
    report = "\n".join(lines)
    print(report)

    if args.output:
        Path(args.output).write_text(report, encoding="utf-8")
        print(f"\nReport also written to {args.output}", file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(main())
