"""Backfill concept mastery streaks across all users from analyzed games.

Engine 2 Phase 1 — bootstrap. After this runs, the user_concept_understanding
collection's streak_clean / acknowledged / mastered_at fields will reflect
the user's actual demonstrated mastery instead of the all-False default.

Idempotent. Each (user, game_id) is processed once via last_evaluated_game_id
on the user_concept_understanding row. Re-running picks up only games not yet
evaluated for each concept.

Usage:
  docker exec chess-coach-backend python \\
    /app/backend/scripts/backfill_concept_mastery.py

  # Or scope to one user (debug):
  docker exec chess-coach-backend python \\
    /app/backend/scripts/backfill_concept_mastery.py --user-id user_8b599930d7ef
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv
load_dotenv(BACKEND_DIR / ".env")

from motor.motor_asyncio import AsyncIOMotorClient
from services.concept_mastery_tracker import update_user_mastery_for_recent_games

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "chess_coach")


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--user-id", default=None,
                    help="Scope backfill to one user_id (default: all users)")
    ap.add_argument("--max-games-per-user", type=int, default=500,
                    help="Cap on how far back to evaluate per user")
    args = ap.parse_args()

    db = AsyncIOMotorClient(MONGO_URL, serverSelectionTimeoutMS=10000)[DB_NAME]

    # Pick the user set to process.
    if args.user_id:
        user_ids = [args.user_id]
    else:
        # Only users who have any concept tracking rows — backfilling
        # users with zero rows is a no-op.
        user_ids = await db.user_concept_understanding.distinct("user_id")
    print(f"[backfill] Processing {len(user_ids)} user(s)", file=sys.stderr)

    grand_totals = {
        "users_processed": 0,
        "games_processed": 0,
        "violated_count": 0,
        "clean_count": 0,
        "mastered_count": 0,
        "skipped_idempotent": 0,
    }
    t0 = time.time()

    for idx, uid in enumerate(user_ids, 1):
        try:
            t = await update_user_mastery_for_recent_games(
                db, uid, max_games=args.max_games_per_user,
            )
            grand_totals["users_processed"] += 1
            for k in ("games_processed", "violated_count", "clean_count",
                      "mastered_count", "skipped_idempotent"):
                grand_totals[k] += t.get(k, 0)
            if t["mastered_count"] > 0:
                print(f"  user {uid[-12:]}: {t['games_processed']} games → "
                      f"{t['mastered_count']} NEW mastered, {t['violated_count']} violations",
                      file=sys.stderr)
        except Exception as e:
            print(f"  user {uid[-12:]} FAILED: {type(e).__name__}: {e}", file=sys.stderr)
        if idx % 10 == 0:
            elapsed = time.time() - t0
            print(f"  [{idx}/{len(user_ids)}] {elapsed:.1f}s elapsed", file=sys.stderr)

    elapsed = time.time() - t0
    print()
    print(f"Backfill complete in {elapsed:.1f}s")
    print(f"  users_processed:     {grand_totals['users_processed']}")
    print(f"  games_processed:     {grand_totals['games_processed']}")
    print(f"  clean concept-games: {grand_totals['clean_count']}")
    print(f"  violated:            {grand_totals['violated_count']}")
    print(f"  NEW mastered:        {grand_totals['mastered_count']}")
    print(f"  skipped idempotent:  {grand_totals['skipped_idempotent']}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
