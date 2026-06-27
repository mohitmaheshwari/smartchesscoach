#!/usr/bin/env python3
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

load_dotenv('/.env')

async def main():
    mongo_url = os.environ.get('MONGO_URL')
    db_name = os.environ.get('DB_NAME', 'chess_coach')

    if not mongo_url:
        print("ERROR: MONGO_URL not set")
        return

    print(f"Connecting to MongoDB...")
    try:
        client = AsyncIOMotorClient(mongo_url, serverSelectionTimeoutMS=10000)
        db = client[db_name]

        # Test connection
        await db.command('ping')
        print("Connected successfully!\n")

    except Exception as e:
        print(f"Connection error: {e}")
        print("\nTrying localhost:27017 instead...")

        # Fallback to localhost
        client = AsyncIOMotorClient('mongodb://localhost:27017')
        db = client[db_name]

    total = await db.games.count_documents({'is_analyzed': True})
    print(f"Total analyzed games in DB: {total}\n")

    cutoff = datetime(2026, 6, 24)

    count_last_3 = await db.games.count_documents({
        'is_analyzed': True,
        'date_played': {'$gte': cutoff}
    })
    print(f"Analyzed in last 3 days (2026-06-24 to 2026-06-27): {count_last_3}\n")

    print("Breakdown by day:")
    for day_offset in range(3, -1, -1):
        day = datetime(2026, 6, 27) - timedelta(days=day_offset)
        day_end = day + timedelta(days=1)

        day_count = await db.games.count_documents({
            'is_analyzed': True,
            'date_played': {'$gte': day, '$lt': day_end}
        })
        print(f"  {day.date()}: {day_count} games")

if __name__ == '__main__':
    asyncio.run(main())
