"""Caption coverage audit — measures how often V5 blunder captions
surface specific tactical content vs fall back to generic phrasings.

Run inside the backend container:

    docker exec chess-coach-backend python /app/backend/scripts/caption_coverage_v5.py
    docker exec chess-coach-backend python /app/backend/scripts/caption_coverage_v5.py --sample 100
    docker exec chess-coach-backend python /app/backend/scripts/caption_coverage_v5.py --user user_8b599930d7ef

The audit walks `decryption_v5_data` for a sample of games, picks user
moves with cp_loss >= 100 (the R12_blunder threshold), and classifies
the caption's why-clause by template-match:

  HIGH specificity (named tactical concept):
    - why_user_missed_mate              ('mate in N')
    - why_user_missed_piece             ('wins the {piece} on {sq}')
    - why_user_missed_clearance_attack  ('clears the line — your slider...')
    - why_user_missed_king_pawn_pressure ('keeps the pressure on {sq}')

  MID specificity (concrete consequence):
    - why_user_attacks_played, hanging, capture, check, exchange_losing

  LOW specificity (generic fallback):
    - why_user_missed_material   ('wins material in the resulting line')
    - why_user_reply             ('Opponent's strongest reply:')

  NONE (silent / no why-clause):
    - bare severity caption ('Ng1 is a serious mistake. Nxe5 was better.')

The output:
  1. Aggregate counts + percentages per tier
  2. Per-template frequency table
  3. Sample LOW-specificity positions (game_id + move + FEN + caption)
     — these are the positions worth authoring better content for

This is the FREQUENCY-PRIORITIZED CONTENT BACKLOG. Don't author
patterns blindly — author the ones that appear most in LOW-specificity
captions.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional, Tuple

from motor.motor_asyncio import AsyncIOMotorClient


# ── Caption classification ──────────────────────────────────────────

# Order matters: HIGH templates checked before MID before LOW.
CLASSIFIERS: List[Tuple[str, str, re.Pattern]] = [
    ("HIGH", "missed_mate",              re.compile(r"would have led to mate in \d+ moves?", re.I)),
    ("HIGH", "missed_piece",             re.compile(r"wins the (pawn|knight|bishop|rook|queen) on [a-h][1-8]", re.I)),
    ("HIGH", "missed_clearance_attack",  re.compile(r"clears the line", re.I)),
    ("HIGH", "missed_king_pawn_pressure", re.compile(r"keeps the pressure on [a-h][1-8]", re.I)),

    ("MID",  "attacks_played",           re.compile(r"has no safe square", re.I)),
    ("MID",  "exchange_losing",          re.compile(r"falls\.|can't be defended", re.I)),
    ("MID",  "hanging",                  re.compile(r"is now undefended", re.I)),
    ("MID",  "capture",                  re.compile(r"winning your (pawn|knight|bishop|rook|queen)", re.I)),
    ("MID",  "check",                    re.compile(r"forcing your king", re.I)),

    ("LOW",  "missed_material",          re.compile(r"wins material in the resulting line", re.I)),
    ("LOW",  "reply",                    re.compile(r"Opponent's strongest reply:", re.I)),
]

SEVERITY_TAIL_RE = re.compile(
    r"\.\s*([A-Z][a-zA-Z0-9+\-#=]+ was better\.?)?\s*$"
)


def classify_caption(caption: str) -> Tuple[str, str]:
    """Return (tier, template_key) for the given caption.

    Tier ∈ {HIGH, MID, LOW, NONE}. NONE = either no why-clause appended
    (just severity + best_move), or the caption is empty.
    """
    if not caption:
        return ("NONE", "empty")
    for tier, key, pat in CLASSIFIERS:
        if pat.search(caption):
            return (tier, key)
    # No why-clause matched — likely bare severity phrasing.
    return ("NONE", "bare_severity")


# ── Audit ────────────────────────────────────────────────────────────

async def audit(sample_size: int, user_filter: Optional[str]) -> None:
    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.environ.get("DB_NAME", "chess_coach")
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]

    # Pick recently-analyzed games with V5 data
    query: Dict[str, Any] = {"decryption_v5_data": {"$exists": True, "$ne": None}}
    if user_filter:
        query["user_id"] = user_filter

    games = []
    cursor = (db.game_analyses.find(
        query, {"_id": 0, "game_id": 1, "user_id": 1, "decryption_v5_data": 1, "decryption_v5_version": 1}
    ).sort("created_at", -1).limit(sample_size))
    async for g in cursor:
        games.append(g)

    if not games:
        print("No analyzed games found. Exiting.")
        return

    # Walk user blunder moves
    by_tier = Counter()
    by_template = Counter()
    version_dist = Counter()
    low_examples: List[Dict[str, Any]] = []
    none_examples: List[Dict[str, Any]] = []
    total_moves = 0

    for game in games:
        gid = game["game_id"]
        version_dist[game.get("decryption_v5_version", "unknown")] += 1
        for m in game.get("decryption_v5_data") or []:
            if not m.get("is_user_move"):
                continue
            cpl = m.get("cp_loss") or 0
            if cpl < 100:
                continue  # below R12 threshold
            total_moves += 1
            cap = m.get("caption") or ""
            tier, key = classify_caption(cap)
            by_tier[tier] += 1
            by_template[(tier, key)] += 1

            sample = {
                "game_id": gid[:8],
                "move_number": m.get("move_number"),
                "move_san": m.get("move_san"),
                "cp_loss": cpl,
                "fen_before": m.get("fen_before"),
                "caption": cap,
                "rule_name": m.get("rule_name"),
            }
            if tier == "LOW" and len(low_examples) < 15:
                low_examples.append(sample)
            elif tier == "NONE" and len(none_examples) < 10:
                none_examples.append(sample)

    # ── Print report ────────────────────────────────────────────────
    print(f"Games scanned: {len(games)}")
    print(f"V5 version distribution: {dict(version_dist)}")
    print(f"User blunder moves (cp_loss >= 100): {total_moves}")
    print()

    if not total_moves:
        print("No blunder moves found — nothing to classify.")
        return

    print("=" * 60)
    print("COVERAGE BY TIER")
    print("=" * 60)
    for tier in ("HIGH", "MID", "LOW", "NONE"):
        n = by_tier[tier]
        pct = 100.0 * n / total_moves
        bar = "█" * int(pct / 2)
        print(f"  {tier:5} {n:5d} ({pct:5.1f}%)  {bar}")
    print()
    high_pct = 100.0 * by_tier["HIGH"] / total_moves
    print(f"Specific-content rate (HIGH): {high_pct:.1f}%")
    print(f"Fallback rate (LOW + NONE):   {100.0 * (by_tier['LOW'] + by_tier['NONE']) / total_moves:.1f}%")
    print()

    print("=" * 60)
    print("PER-TEMPLATE FREQUENCY")
    print("=" * 60)
    for (tier, key), n in by_template.most_common():
        pct = 100.0 * n / total_moves
        print(f"  [{tier}] {key:30} {n:5d} ({pct:5.1f}%)")
    print()

    print("=" * 60)
    print("LOW-SPECIFICITY SAMPLE POSITIONS (generic fallback fired)")
    print("These are content-authoring candidates — what's the right caption?")
    print("=" * 60)
    for s in low_examples:
        print(f"  game {s['game_id']} m{s['move_number']} {s['move_san']} cp={s['cp_loss']}")
        print(f"    FEN: {s['fen_before']}")
        print(f"    CAPTION: {s['caption']}")
        print()

    if none_examples:
        print("=" * 60)
        print("NONE / bare-severity captions (no why-clause)")
        print("=" * 60)
        for s in none_examples:
            print(f"  game {s['game_id']} m{s['move_number']} {s['move_san']} cp={s['cp_loss']}")
            print(f"    CAPTION: {s['caption']}")
            print()


def main():
    parser = argparse.ArgumentParser(description="V5 caption coverage audit")
    parser.add_argument("--sample", type=int, default=50, help="Number of games to scan (default 50)")
    parser.add_argument("--user", type=str, default=None, help="Restrict to one user_id")
    args = parser.parse_args()
    asyncio.run(audit(args.sample, args.user))


if __name__ == "__main__":
    main()
