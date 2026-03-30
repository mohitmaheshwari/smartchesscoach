#!/usr/bin/env python3
"""
Backfill training positions from already-analyzed games.

Usage:
    docker exec -it chess-coach-backend python backfill_training.py
"""

import os
import sys
import asyncio

try:
    from dotenv import load_dotenv
    load_dotenv()
except:
    pass

from motor.motor_asyncio import AsyncIOMotorClient
from services.community_training_service import extract_training_positions

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "chess_coach")


async def main():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    # Get all analyzed games
    analyses = []
    async for doc in db.game_analyses.find({}, {"_id": 0, "game_id": 1, "user_id": 1}):
        analyses.append(doc)

    print(f"Found {len(analyses)} analyzed games")

    total_positions = 0
    for a in analyses:
        game_id = a["game_id"]
        user_id = a["user_id"]
        try:
            positions = await extract_training_positions(db, game_id, user_id)
            if positions:
                total_positions += len(positions)
                print(f"  {game_id}: {len(positions)} positions extracted")
        except Exception as e:
            print(f"  {game_id}: error - {e}")

    print(f"\nDone. Extracted {total_positions} training positions total.")
    client.close()


if __name__ == "__main__":
    asyncio.run(main())
