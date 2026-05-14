"""
Backfill LLM captions for N games (default 50) and assign them to the
authoring queue for Mohit/Parth review.

For each picked game this script:
  1. Loads decryption_v5_data from game_analyses.
  2. Annotates trap + opening context per move (in memory).
  3. For each move with a teaching signal, calls gpt-4o-mini through
     services.llm_caption_generator → caption string.
  4. Writes the result to `decryption_v5_data[i].caption_llm` in MongoDB.
     If the LLM returned empty, writes "" (intentional silence on
     forced moves / no-teaching positions).
  5. Inserts the game into authoring_queue under a round_id so the
     /review/authoring page lists it.

Stratification: same 5 buckets as scripts/pick_authoring_games.py
(TACTICAL_BLUNDER, POSITIONAL_MISTAKE, ENDGAME, OPENING_DRIFT,
WON_WITH_BLUNDER). Default 10 games per bucket → 50 total.

Idempotency: by default the script skips moves where `caption_llm`
already exists. Pass --force to overwrite.

Cost note: ~$0.03 per game at gpt-4o-mini → ~$1.50 for 50 games.

Usage:
    docker exec -it chess-coach-backend python scripts/backfill_llm_captions.py
    docker exec -it chess-coach-backend python scripts/backfill_llm_captions.py --per-bucket 10 --persist
    docker exec -it chess-coach-backend python scripts/backfill_llm_captions.py --per-bucket 5 --round-id round_llm_pilot --persist
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv
load_dotenv(BACKEND_DIR / ".env")

from motor.motor_asyncio import AsyncIOMotorClient

from services.llm_caption_generator import (
    build_system_prompt,
    has_teaching_signal,
    annotate_runtime_facts,
    generate_caption_for_move,
)


MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "chess_coach")


BUCKETS = ["TACTICAL_BLUNDER", "POSITIONAL_MISTAKE", "ENDGAME", "OPENING_DRIFT", "WON_WITH_BLUNDER"]


def _classify_game(v5_data: List[Dict], game_result: str, user_color: str) -> Set[str]:
    """Same bucket classifier as scripts/pick_authoring_games.py."""
    buckets: Set[str] = set()
    user_won = (
        (game_result == "1-0" and user_color == "white")
        or (game_result == "0-1" and user_color == "black")
    )
    has_blunder = False
    has_endgame = False
    for rec in v5_data:
        if not rec.get("is_user_move"):
            continue
        cpl = rec.get("cp_loss") or 0
        phase = rec.get("phase")
        if cpl >= 200:
            buckets.add("TACTICAL_BLUNDER")
            has_blunder = True
        if 50 <= cpl <= 150:
            ev_pids = {(p or {}).get("principle_id")
                       for p in (rec.get("caption_facts_principles_violated") or [])}
            if "TAC_HANGING_PIECE" not in ev_pids and "TAC_DEFENDER_COUNT" not in ev_pids:
                buckets.add("POSITIONAL_MISTAKE")
        if phase == "endgame":
            has_endgame = True
        if phase == "opening" and 30 <= cpl <= 100:
            buckets.add("OPENING_DRIFT")
    if has_endgame:
        buckets.add("ENDGAME")
    if user_won and has_blunder:
        buckets.add("WON_WITH_BLUNDER")
    return buckets


async def _pick_stratified(db, per_bucket: int) -> List[Dict[str, Any]]:
    """Pick `per_bucket` games for each of the 5 buckets. Returns the
    resulting list ordered by bucket, then by most-recent-import within
    bucket. Each item carries game_id, bucket, plus game metadata.
    """
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
    print(f"[backfill] active games scanned: {len(active_games)}", file=sys.stderr)

    bucket_to_games: Dict[str, List[str]] = defaultdict(list)
    game_to_buckets: Dict[str, Set[str]] = {}
    scanned = 0
    async for analysis in db.game_analyses.find(
        {"game_id": {"$in": list(active_games.keys())}},
        {"_id": 0, "game_id": 1, "decryption_v5_data": 1},
    ):
        scanned += 1
        gid = analysis.get("game_id")
        if not gid or gid not in active_games:
            continue
        v5 = analysis.get("decryption_v5_data") or []
        if not v5:
            continue
        g = active_games[gid]
        bs = _classify_game(v5, g.get("result", ""), g.get("user_color", "white"))
        if not bs:
            continue
        game_to_buckets[gid] = bs
        for b in bs:
            bucket_to_games[b].append(gid)
    print(f"[backfill] analyses scanned={scanned} classifiable={len(game_to_buckets)}", file=sys.stderr)

    picked: List[Dict[str, Any]] = []
    picked_set: Set[str] = set()
    for b in BUCKETS:
        candidates = [g for g in bucket_to_games.get(b, []) if g not in picked_set]
        candidates.sort(key=lambda gid: active_games[gid].get("imported_at") or "", reverse=True)
        chosen = candidates[:per_bucket]
        if len(chosen) < per_bucket:
            extras = [g for g in bucket_to_games.get(b, []) if g not in chosen]
            chosen = chosen + extras[:per_bucket - len(chosen)]
        for gid in chosen[:per_bucket]:
            picked.append({
                "game_id": gid,
                "bucket": b,
                "user_id": active_games[gid].get("user_id"),
                "result": active_games[gid].get("result"),
                "user_color": active_games[gid].get("user_color"),
                "opening": active_games[gid].get("opening") or active_games[gid].get("opening_name"),
                "imported_at": active_games[gid].get("imported_at"),
            })
            picked_set.add(gid)
    return picked


async def _backfill_one_game(
    db,
    game_meta: Dict[str, Any],
    sys_prompt: str,
    force: bool,
) -> Dict[str, int]:
    """Generate + persist LLM captions for one game. Returns per-game stats."""
    gid = game_meta["game_id"]
    stats = {"moves": 0, "skipped_existing": 0, "called": 0, "gated": 0,
             "llm_empty": 0, "errors": 0, "written": 0}

    analysis = await db.game_analyses.find_one(
        {"game_id": gid},
        {"_id": 0, "decryption_v5_data": 1},
    )
    if not analysis or not analysis.get("decryption_v5_data"):
        print(f"  [{gid[:8]}] no V5 data — skipping", file=sys.stderr)
        return stats

    moves = analysis["decryption_v5_data"]
    annotate_runtime_facts(moves)

    # Build the array-level updates to push at the end. We use the
    # positional dotted-path update so each move record only sees its
    # own caption_llm field touched.
    set_ops: Dict[str, str] = {}

    for idx, m in enumerate(moves):
        stats["moves"] += 1

        # Idempotency: skip if already has caption_llm and --force not set.
        if not force and "caption_llm" in m:
            stats["skipped_existing"] += 1
            continue

        if not has_teaching_signal(m):
            stats["gated"] += 1
            # Don't write anything — absence of caption_llm means
            # frontend falls back to the existing renderer caption.
            continue

        stats["called"] += 1
        cap = await generate_caption_for_move(m, sys_prompt)

        if cap.startswith("[ERROR"):
            stats["errors"] += 1
            print(f"  [{gid[:8]}] move {m.get('move_number')}.{m.get('move_san')}: {cap[:100]}", file=sys.stderr)
            continue

        if not cap:
            stats["llm_empty"] += 1
            cap = ""  # explicit empty string — intentional silence

        set_ops[f"decryption_v5_data.{idx}.caption_llm"] = cap
        stats["written"] += 1

    if set_ops:
        await db.game_analyses.update_one({"game_id": gid}, {"$set": set_ops})

    return stats


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-bucket", type=int, default=10,
                    help="Games per bucket (default 10 → 50 total across 5 buckets).")
    ap.add_argument("--persist", action="store_true",
                    help="Insert picks into authoring_queue under --round-id.")
    ap.add_argument("--round-id", type=str, default=None,
                    help="Round id for authoring_queue (default round_llm_YYYYMMDD). "
                         "Re-running with the same round_id replaces that round's queue.")
    ap.add_argument("--force", action="store_true",
                    help="Overwrite existing caption_llm fields. Default: skip.")
    ap.add_argument("--dry-run", action="store_true",
                    help="Pick games and report what WOULD happen, no LLM calls, no writes.")
    args = ap.parse_args()

    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    picks = await _pick_stratified(db, args.per_bucket)
    print(f"[backfill] picked {len(picks)} games "
          f"(target {len(BUCKETS) * args.per_bucket})", file=sys.stderr)

    if args.dry_run:
        print("\n── DRY RUN ────────────────────────────────────")
        per_bucket = defaultdict(int)
        for p in picks:
            per_bucket[p["bucket"]] += 1
            print(f"  {p['bucket']:20s}  {p['game_id']}  result={p['result']}  color={p['user_color']}")
        print("\nBy bucket:")
        for b in BUCKETS:
            print(f"  {b:20s}  {per_bucket[b]}")
        return

    sys_prompt = build_system_prompt()
    print(f"[backfill] system prompt: {len(sys_prompt):,} chars", file=sys.stderr)

    totals = defaultdict(int)
    for i, game_meta in enumerate(picks, 1):
        print(f"\n[{i}/{len(picks)}] {game_meta['bucket']:20s}  {game_meta['game_id']}", file=sys.stderr)
        per_game = await _backfill_one_game(db, game_meta, sys_prompt, force=args.force)
        for k, v in per_game.items():
            totals[k] += v
        print(f"    moves={per_game['moves']} called={per_game['called']} "
              f"gated={per_game['gated']} empty={per_game['llm_empty']} "
              f"written={per_game['written']} skipped_existing={per_game['skipped_existing']} "
              f"errors={per_game['errors']}", file=sys.stderr)

    if args.persist:
        round_id = args.round_id or f"round_llm_{datetime.now(timezone.utc).strftime('%Y%m%d')}"
        await db.authoring_queue.delete_many({"round_id": round_id})
        now = datetime.now(timezone.utc).isoformat()
        docs = []
        for i, p in enumerate(picks, 1):
            docs.append({
                "round_id": round_id,
                "game_id": p["game_id"],
                "bucket": p["bucket"],
                "user_id": p.get("user_id"),
                "result": p.get("result"),
                "user_color": p.get("user_color"),
                "opening": p.get("opening"),
                "imported_at": p.get("imported_at"),
                "picked_at": now,
                "order_in_round": i,
            })
        if docs:
            await db.authoring_queue.insert_many(docs)
            print(f"\n[backfill] persisted {len(docs)} games to authoring_queue "
                  f"under round_id={round_id}", file=sys.stderr)

    print("\n── SUMMARY ────────────────────────────────────")
    print(f"games processed       : {len(picks)}")
    print(f"total moves           : {totals['moves']}")
    print(f"LLM calls             : {totals['called']}")
    print(f"  → captions written  : {totals['written']}")
    print(f"  → LLM said empty    : {totals['llm_empty']}")
    print(f"  → errors            : {totals['errors']}")
    print(f"gated (no signal)     : {totals['gated']}")
    print(f"skipped (existing)    : {totals['skipped_existing']}")


if __name__ == "__main__":
    asyncio.run(main())
