"""Backfill engine-aware opening accuracy for all analyzed games.

Walks games with decryption_v5_data and runs the new
update_mastery_from_analyzed_game on each, populating accuracy_history
with cp_loss-graded scores. Replaces the curriculum-exact-match values
that the original opening_mastery_tracker wrote (the metric only fired
on PWC sessions and treated any book alternative as wrong).

Idempotent via the _accuracy_evaluated_games set on each opening_mastery row.

Usage:
  docker exec chess-coach-backend python \\
    /app/backend/scripts/backfill_opening_accuracy.py
  docker exec chess-coach-backend python \\
    /app/backend/scripts/backfill_opening_accuracy.py --user-id user_8b599930d7ef
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
from services.opening_mastery_tracker import update_mastery_from_analyzed_game

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "chess_coach")


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--user-id", default=None)
    ap.add_argument("--reset", action="store_true",
                    help="Clear stored accuracy_history + _accuracy_evaluated_games on "
                         "all matching rows before running. Use after the formula "
                         "changes — otherwise old (curriculum-match) entries linger.")
    args = ap.parse_args()

    db = AsyncIOMotorClient(MONGO_URL, serverSelectionTimeoutMS=10000)[DB_NAME]

    if args.reset:
        match = {"user_id": args.user_id} if args.user_id else {}
        r = await db.user_opening_mastery.update_many(
            match,
            {"$set": {"accuracy_history": [], "_accuracy_evaluated_games": []}},
        )
        print(f"[reset] cleared accuracy_history on {r.modified_count} rows")

    if args.user_id:
        user_ids = [args.user_id]
    else:
        user_ids = await db.game_analyses.distinct(
            "user_id", {"decryption_v5_data": {"$type": "array"}}
        )
    print(f"[backfill-acc] users to process: {len(user_ids)}")

    grand = {
        "users_processed": 0,
        "games_processed": 0,
        "games_scored": 0,
        "games_skipped": 0,
    }
    t0 = time.time()

    for idx, uid in enumerate(user_ids, 1):
        games = await db.game_analyses.find(
            {"user_id": uid, "decryption_v5_data": {"$type": "array"}},
            {"_id": 0, "game_id": 1},
        ).sort([("analyzed_at", 1)]).to_list(length=None)
        try:
            for g in games:
                gid = g.get("game_id")
                if not gid:
                    continue
                grand["games_processed"] += 1
                result = await update_mastery_from_analyzed_game(db, uid, gid)
                if result and result.get("accuracy") is not None:
                    grand["games_scored"] += 1
                else:
                    grand["games_skipped"] += 1
            grand["users_processed"] += 1
            if idx % 10 == 0 or idx == len(user_ids):
                elapsed = time.time() - t0
                print(f"  [{idx}/{len(user_ids)}] {elapsed:.1f}s — "
                      f"scored={grand['games_scored']} skipped={grand['games_skipped']}")
        except Exception as e:
            print(f"  user {uid[-12:]} FAILED: {type(e).__name__}: {e}")

    print()
    print(f"Backfill complete in {time.time() - t0:.1f}s")
    for k, v in grand.items():
        print(f"  {k}: {v}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
