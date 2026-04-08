"""
Inspect database: show collections, document counts, and sample document fields.

Usage:
  docker cp scripts/inspect_db.py chess-coach-backend:/app/backend/scripts/
  docker exec -it chess-coach-backend python3 scripts/inspect_db.py
"""

import asyncio
import os
import json

from motor.motor_asyncio import AsyncIOMotorClient


async def main():
    url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.environ.get("DB_NAME", "test_database")

    print(f"Database: {db_name}")
    print(f"URL: {url[:30]}...")
    print("=" * 60)

    client = AsyncIOMotorClient(url)
    db = client[db_name]

    collections = await db.list_collection_names()
    print(f"\nCollections ({len(collections)}):")

    for coll_name in sorted(collections):
        count = await db[coll_name].count_documents({})
        print(f"\n  {coll_name}: {count} documents")

        if count > 0:
            sample = await db[coll_name].find_one({})
            if sample:
                # Show field names and types, not full values
                print(f"  Fields:")
                for key, value in sample.items():
                    if key == "_id":
                        continue
                    val_type = type(value).__name__
                    # Show a preview for strings
                    if isinstance(value, str):
                        preview = value[:60] + "..." if len(value) > 60 else value
                        print(f"    {key}: ({val_type}) {preview}")
                    elif isinstance(value, (int, float, bool)):
                        print(f"    {key}: ({val_type}) {value}")
                    elif isinstance(value, list):
                        print(f"    {key}: ({val_type}) [{len(value)} items]")
                    elif isinstance(value, dict):
                        print(f"    {key}: ({val_type}) {{{', '.join(list(value.keys())[:5])}}}")
                    elif value is None:
                        print(f"    {key}: (None)")
                    else:
                        print(f"    {key}: ({val_type})")

    # Extra: show a full sample game document
    print("\n" + "=" * 60)
    print("FULL SAMPLE: games collection")
    print("=" * 60)
    sample_game = await db.games.find_one({}, {"pgn": 0})  # Skip PGN (too long)
    if sample_game:
        sample_game["_id"] = str(sample_game["_id"])
        print(json.dumps(sample_game, indent=2, default=str))
    else:
        print("No games found.")


if __name__ == "__main__":
    asyncio.run(main())
