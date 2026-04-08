"""
Backfill opening info for all games missing it.
Extracts opening name from PGN headers.

Usage:
  docker cp scripts/backfill_openings.py chess-coach-backend:/app/backend/scripts/
  docker exec -it chess-coach-backend python3 scripts/backfill_openings.py
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from motor.motor_asyncio import AsyncIOMotorClient
from journey_service import extract_opening_from_pgn


async def main():
    url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.environ.get("DB_NAME", "test_database")

    print(f"Connecting to {db_name}...")
    client = AsyncIOMotorClient(url)
    db = client[db_name]

    total = await db.games.count_documents({})
    print(f"Total games: {total}")

    # Find ALL games missing opening_name (covers None, "", and field not existing)
    query = {
        "$or": [
            {"opening_name": None},
            {"opening_name": ""},
            {"opening_name": {"$exists": False}},
        ]
    }
    games = await db.games.find(query, {"_id": 1, "game_id": 1, "pgn": 1}).to_list(1000)
    print(f"Missing opening_name: {len(games)}")

    if not games:
        print("All games already have opening info.")
        return

    updated = 0
    skipped = 0
    for game in games:
        pgn = game.get("pgn", "")
        if not pgn:
            skipped += 1
            continue

        opening_info = extract_opening_from_pgn(pgn)
        opening_name = opening_info.get("opening_name") or opening_info.get("opening")

        if opening_name:
            await db.games.update_one(
                {"_id": game["_id"]},
                {"$set": {
                    "eco": opening_info.get("eco"),
                    "opening": opening_info.get("opening"),
                    "opening_name": opening_name,
                    "opening_url": opening_info.get("opening_url"),
                }}
            )
            updated += 1
            print(f"  {game.get('game_id', '?')}: {opening_name}")
        else:
            skipped += 1
            print(f"  {game.get('game_id', '?')}: no opening found in PGN")

    print(f"\nDone. Updated: {updated}, Skipped: {skipped}")


if __name__ == "__main__":
    asyncio.run(main())
