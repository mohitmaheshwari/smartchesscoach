"""
Visual-shape backfill — attach shapes[] to existing game_analyses.

Existing analyses (created before the visual_shapes layer shipped) have
no shapes field on their move_evaluations. This script walks each game,
runs the shape detectors with the same lookahead + per-game dedup as
production, and updates the document in place.

Idempotent — re-running on already-backfilled games just rewrites the
same shapes (no harm). Safe to run multiple times.

Dry-run by default. Pass --apply to actually write.

Usage:
    python scripts/visual_shapes_backfill.py --dry-run --limit 50
    python scripts/visual_shapes_backfill.py --apply
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, List

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv
load_dotenv(BACKEND_DIR / ".env")

from motor.motor_asyncio import AsyncIOMotorClient

from services.visual_shapes import detect_shapes_for_move

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "chess_coach")

SHAPE_LOOKAHEAD = 6


async def run(args):
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    cursor = db.game_analyses.find(
        {"stockfish_analysis.move_evaluations": {"$exists": True, "$ne": []}},
        {
            "_id": 1,
            "game_id": 1,
            "stockfish_analysis.move_evaluations": 1,
        },
    )
    if args.limit:
        cursor = cursor.limit(args.limit)

    games_processed = 0
    games_updated = 0
    games_with_any_shape = 0
    shape_total: Counter = Counter()

    async for ga in cursor:
        games_processed += 1
        sa = ga.get("stockfish_analysis") or {}
        moves = sa.get("move_evaluations") or []
        if not moves:
            continue

        seen_types: set = set()
        any_shape = False
        any_changed = False

        for idx, me in enumerate(moves):
            future = moves[idx + 1: idx + 1 + SHAPE_LOOKAHEAD]
            shapes = detect_shapes_for_move(me, future) or []
            # Per-game dedup — keep first occurrence per type.
            kept: List[Dict] = []
            for shape in shapes:
                stype = shape.get("type")
                if not stype or stype in seen_types:
                    continue
                kept.append(shape)
                seen_types.add(stype)
                shape_total[stype] += 1
                any_shape = True

            existing = me.get("shapes")
            # Always set, even to empty list — keeps the field shape
            # consistent across all moves for the frontend.
            if existing != kept:
                me["shapes"] = kept
                any_changed = True

        if any_shape:
            games_with_any_shape += 1

        if any_changed and args.apply:
            await db.game_analyses.update_one(
                {"_id": ga["_id"]},
                {"$set": {"stockfish_analysis.move_evaluations": moves}},
            )
            games_updated += 1
        elif any_changed and not args.apply:
            games_updated += 1  # would-be updates in dry-run

        if games_processed % 100 == 0:
            print(f"  ... {games_processed} processed, {games_updated} {'updated' if args.apply else 'would update'}", flush=True)

    client.close()

    print()
    print("=" * 60)
    print(f"Mode:                  {'APPLY (writes)' if args.apply else 'DRY-RUN'}")
    print(f"Games processed:       {games_processed}")
    print(f"Games {'updated' if args.apply else 'that would update'}: {games_updated}")
    print(f"Games with any shape:  {games_with_any_shape}")
    print(f"Shape fires (deduped): {sum(shape_total.values())}")
    print("Distribution:")
    for stype, n in shape_total.most_common():
        print(f"  {n:5d}  {stype}")
    print("=" * 60)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--limit", type=int, default=None, help="cap to N games (default: all)")
    p.add_argument("--apply", action="store_true", help="actually write (default: dry-run)")
    p.add_argument("--dry-run", action="store_true", help="default mode — preview only")
    args = p.parse_args()

    if args.dry_run and args.apply:
        print("Pick one: --dry-run OR --apply")
        sys.exit(1)

    asyncio.run(run(args))
