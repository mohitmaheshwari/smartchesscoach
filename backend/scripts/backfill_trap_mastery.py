"""Backfill trap mastery (traps_handled / traps_fallen_for / traps_encountered)
across all analyzed games.

Engine 2 — bootstraps the trap-mastery signal so PWC Phase 2's gate can
read it. After this runs, user_opening_mastery rows will have populated
trap-outcome fields instead of the empty defaults that have sat there
since the schema was introduced.

Idempotent. Each (user × game × trap_fire) is processed once via the
_evaluated_trap_fires signature.

Usage:
  docker exec chess-coach-backend python \\
    /app/backend/scripts/backfill_trap_mastery.py        # all users
  docker exec chess-coach-backend python \\
    /app/backend/scripts/backfill_trap_mastery.py --user-id user_8b599930d7ef
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
from services.trap_mastery_tracker import update_trap_mastery_for_game

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "chess_coach")


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--user-id", default=None,
                    help="Scope to one user (default: all users with opening_mastery rows)")
    args = ap.parse_args()

    db = AsyncIOMotorClient(MONGO_URL, serverSelectionTimeoutMS=10000)[DB_NAME]

    if args.user_id:
        user_ids = [args.user_id]
    else:
        # Iterate users who have trap_fires on ANY game — not just users
        # with existing opening_mastery rows (chicken-and-egg).
        user_ids = await db.game_analyses.distinct(
            "user_id", {"trap_fires": {"$exists": True, "$ne": []}}
        )
    print(f"[backfill-traps] users to process: {len(user_ids)}", file=sys.stderr)

    grand = {
        "users_processed": 0,
        "games_processed": 0,
        "fires_seen": 0,
        "newly_encountered": 0,
        "newly_handled": 0,
        "newly_fallen_for": 0,
    }
    t0 = time.time()

    for idx, uid in enumerate(user_ids, 1):
        # Walk every analyzed game for this user that HAS trap_fires.
        cursor = db.game_analyses.find(
            {"user_id": uid, "trap_fires": {"$exists": True, "$ne": []}},
            {"_id": 0, "game_id": 1},
        ).sort([("analyzed_at", 1)])
        games = await cursor.to_list(length=None)
        try:
            for g in games:
                gid = g.get("game_id")
                if not gid:
                    continue
                summary = await update_trap_mastery_for_game(db, uid, gid)
                grand["games_processed"] += 1
                for k in ("fires_seen", "newly_encountered", "newly_handled", "newly_fallen_for"):
                    grand[k] += summary.get(k, 0)
            grand["users_processed"] += 1
            if idx % 10 == 0 or idx == len(user_ids):
                elapsed = time.time() - t0
                print(f"  [{idx}/{len(user_ids)}] {elapsed:.1f}s — "
                      f"games={grand['games_processed']} "
                      f"handled+={grand['newly_handled']} "
                      f"fallen+={grand['newly_fallen_for']}",
                      file=sys.stderr)
        except Exception as e:
            print(f"  user {uid[-12:]} FAILED: {type(e).__name__}: {e}", file=sys.stderr)

    elapsed = time.time() - t0
    print()
    print(f"Backfill complete in {elapsed:.1f}s")
    print(f"  users_processed:    {grand['users_processed']}")
    print(f"  games_processed:    {grand['games_processed']}")
    print(f"  fires_seen:         {grand['fires_seen']}")
    print(f"  newly_encountered:  {grand['newly_encountered']}")
    print(f"  newly_handled:      {grand['newly_handled']}")
    print(f"  newly_fallen_for:   {grand['newly_fallen_for']}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
