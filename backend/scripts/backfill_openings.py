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
from journey_service import backfill_opening_info


async def main():
    url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.environ.get("DB_NAME", "test_database")

    print(f"Connecting to {db_name}...")
    client = AsyncIOMotorClient(url)
    db = client[db_name]

    total = await db.games.count_documents({})
    missing = await db.games.count_documents({
        "$or": [
            {"opening_name": None},
            {"opening_name": ""},
            {"opening_name": {"$exists": False}},
        ]
    })
    print(f"Total games: {total}")
    print(f"Missing opening info: {missing}")

    if missing == 0:
        print("All games already have opening info.")
        return

    count = await backfill_opening_info(db)
    print(f"Backfilled {count} games with opening info.")

    # Verify
    still_missing = await db.games.count_documents({
        "$or": [
            {"opening_name": None},
            {"opening_name": ""},
            {"opening_name": {"$exists": False}},
        ]
    })
    print(f"Still missing: {still_missing}")


if __name__ == "__main__":
    asyncio.run(main())
