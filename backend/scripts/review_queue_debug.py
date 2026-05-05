"""
Diagnose why /admin/decryption-review may be empty.

Walks the same data path the API uses, separately for each layer:
  1. game_analyses with decryption_block at all
  2. with at least one moment
  3. with at least one moment having needs_review:true
  4. exact API aggregation, first 5 rows
  5. coach_overrides count (in case all rows are filtered as overridden)

Usage:
    python scripts/review_queue_debug.py
"""

import asyncio
import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv
load_dotenv(BACKEND_DIR / ".env")

from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "chess_coach")


async def main() -> None:
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    has_block = await db.game_analyses.count_documents(
        {"decryption_block": {"$exists": True, "$ne": None}}
    )
    has_moments = await db.game_analyses.count_documents(
        {"decryption_block.moments.0": {"$exists": True}}
    )
    has_flagged = await db.game_analyses.count_documents(
        {"decryption_block.moments.needs_review": True}
    )
    has_unflagged = await db.game_analyses.count_documents(
        {"decryption_block.moments.needs_review": False}
    )

    # Sample one analyzed game to confirm field shape.
    sample = await db.game_analyses.find_one(
        {"decryption_block.moments.0": {"$exists": True}},
        {
            "_id": 0,
            "game_id": 1,
            "decryption_block.moments.move_number": 1,
            "decryption_block.moments.move_san": 1,
            "decryption_block.moments.confidence": 1,
            "decryption_block.moments.needs_review": 1,
            "decryption_block.moments.source": 1,
        },
    )

    print("=" * 70)
    print("REVIEW QUEUE DIAGNOSTIC")
    print("=" * 70)
    print(f"  game_analyses with decryption_block:        {has_block}")
    print(f"  game_analyses with at least one moment:     {has_moments}")
    print(f"  game_analyses with needs_review:true:       {has_flagged}")
    print(f"  game_analyses with needs_review:false:      {has_unflagged}")
    print()

    if sample:
        print("Sample moment fields from one game:")
        print(f"  game_id: {sample.get('game_id')}")
        for i, m in enumerate(((sample.get('decryption_block') or {}).get('moments') or [])[:4]):
            print(f"    [{i+1}] move {m.get('move_number')} {m.get('move_san')}  "
                  f"confidence={m.get('confidence')}  needs_review={m.get('needs_review')}  "
                  f"source={m.get('source')}")
    else:
        print("  No game_analyses with moments found at all.")
    print()

    # Run the EXACT aggregation the API uses.
    pipeline = [
        {"$match": {"decryption_block.moments": {"$exists": True, "$ne": []}}},
        {"$unwind": "$decryption_block.moments"},
        {"$match": {"decryption_block.moments.needs_review": True}},
        {"$project": {
            "_id": 0,
            "game_id": 1,
            "moment": "$decryption_block.moments",
        }},
        {"$sort": {"moment.confidence": 1, "game_id": 1}},
        {"$limit": 5},
    ]
    api_rows = []
    async for d in db.game_analyses.aggregate(pipeline):
        api_rows.append(d)

    print(f"API aggregation returns {len(api_rows)} rows (first 5 shown):")
    for r in api_rows:
        m = r.get("moment") or {}
        print(f"  {r.get('game_id')}  M{m.get('move_number')} {m.get('move_san')}  "
              f"conf={m.get('confidence')}  source={m.get('source')}")
    print()

    overrides_count = await db.coach_overrides.count_documents({})
    print(f"  coach_overrides total (would hide rows when include_overridden=False): {overrides_count}")
    client.close()


if __name__ == "__main__":
    asyncio.run(main())
