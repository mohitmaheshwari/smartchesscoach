"""
End all active coach sessions.

Usage:
  docker cp scripts/end_active_sessions.py chess-coach-backend:/app/backend/scripts/
  docker exec -it chess-coach-backend python3 scripts/end_active_sessions.py
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from motor.motor_asyncio import AsyncIOMotorClient


async def main():
    url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.environ.get("DB_NAME", "chess_coach")
    client = AsyncIOMotorClient(url)
    db = client[db_name]

    r = await db.coach_sessions.update_many(
        {"status": "active"},
        {"$set": {"status": "ended", "result": "abandoned"}}
    )
    print(f"Ended {r.modified_count} active sessions")


if __name__ == "__main__":
    asyncio.run(main())
