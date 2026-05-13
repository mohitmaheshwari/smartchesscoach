"""
Mark active games and deactivate the rest.

Active set = the N most-recent games by `analyzed_at` from the
game_analyses collection. Defaults to 1600 (the user's chosen
window — the size of the shape-pattern-backfilled corpus on
2026-05-13).

Writes a single `is_active` boolean to each game document in the
`games` collection. Inactive games are hidden from coaching/training
surfaces but retained in storage and visible in admin with a badge.

Convention used by downstream read paths:
    {"is_active": {"$ne": False}}
This makes legacy documents (no `is_active` field) default to active,
so we don't accidentally hide games the migration hasn't touched yet.

Usage:
    docker exec -it chess-coach-backend python scripts/mark_active_games.py --dry-run
    docker exec -it chess-coach-backend python scripts/mark_active_games.py
    docker exec -it chess-coach-backend python scripts/mark_active_games.py --active-count 2000
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
from pathlib import Path
from typing import Set

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv
load_dotenv(BACKEND_DIR / ".env")

from motor.motor_asyncio import AsyncIOMotorClient


MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "chess_coach")


async def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--active-count", type=int, default=1600,
                    help="Number of most-recent analyzed games to keep active (default 1600)")
    ap.add_argument("--dry-run", action="store_true",
                    help="Report what would change without writing")
    args = ap.parse_args()

    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    start = time.time()

    # 1. Find the N most-recent game_ids from game_analyses by analyzed_at desc.
    print(f"Finding the {args.active_count} most-recently analyzed games...")
    cursor = db.game_analyses.find(
        {},
        {"_id": 0, "game_id": 1, "analyzed_at": 1},
    ).sort("analyzed_at", -1).limit(args.active_count)
    active_ids: Set[str] = set()
    async for doc in cursor:
        gid = doc.get("game_id")
        if gid:
            active_ids.add(gid)
    print(f"  Active set: {len(active_ids)} game_ids")

    # 2. Look at the games collection — how many total, how many already
    #    have is_active set?
    total_games = await db.games.count_documents({})
    already_active = await db.games.count_documents({"is_active": True})
    already_inactive = await db.games.count_documents({"is_active": False})
    print(f"\n`games` collection: {total_games} total")
    print(f"  already is_active=True:  {already_active}")
    print(f"  already is_active=False: {already_inactive}")
    print(f"  unmarked (legacy):       {total_games - already_active - already_inactive}")

    # 3. Compute deltas.
    games_in_active_set = await db.games.count_documents({"game_id": {"$in": list(active_ids)}})
    games_not_in_active_set = total_games - games_in_active_set
    print(f"\nIntersection with `games`:")
    print(f"  games found for active set:   {games_in_active_set}")
    print(f"  games to mark inactive:       {games_not_in_active_set}")

    if args.dry_run:
        print(f"\nDRY-RUN — no writes. Elapsed {time.time()-start:.1f}s.")
        return

    # 4. Update games: set is_active per side. Use bulk_write for speed.
    print(f"\nWriting is_active flags...")
    res_active = await db.games.update_many(
        {"game_id": {"$in": list(active_ids)}},
        {"$set": {"is_active": True}},
    )
    res_inactive = await db.games.update_many(
        {"game_id": {"$nin": list(active_ids)}},
        {"$set": {"is_active": False}},
    )

    print(f"  is_active=True  set on {res_active.modified_count} (matched {res_active.matched_count})")
    print(f"  is_active=False set on {res_inactive.modified_count} (matched {res_inactive.matched_count})")

    # 5. Sanity-check counts after.
    now_active = await db.games.count_documents({"is_active": True})
    now_inactive = await db.games.count_documents({"is_active": False})
    print(f"\nAfter:")
    print(f"  is_active=True:  {now_active}")
    print(f"  is_active=False: {now_inactive}")
    print(f"  Elapsed {time.time()-start:.1f}s")


if __name__ == "__main__":
    asyncio.run(main())
