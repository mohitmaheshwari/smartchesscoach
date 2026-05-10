"""
One-shot migration: grant `is_reviewer = True` to Parth Gilda's user
record so he can read games / analyses / decryption output across ALL
users (for content-quality auditing of beta users).

Run inside the backend container:
    python scripts/grant_reviewer_to_parth.py

Idempotent — safe to run multiple times. Looks up the user by name
("Parth Gilda" or partial match) and prints a summary of what changed.
"""
from __future__ import annotations

import asyncio
import os
import re
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv
load_dotenv(BACKEND_DIR / ".env")

from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "chess_coach")


async def main():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    # Match by name (case-insensitive). Parth's record name is "Parth Gilda"
    # per the bug-feedback exports. We search broadly for safety.
    name_re = re.compile(r"\bparth\b", re.IGNORECASE)
    candidates = await db.users.find(
        {"name": {"$regex": name_re}},
        {"_id": 0, "user_id": 1, "name": 1, "email": 1, "is_reviewer": 1}
    ).to_list(20)

    if not candidates:
        # Fall back to email match if name doesn't hit
        candidates = await db.users.find(
            {"email": {"$regex": re.compile(r"parth", re.IGNORECASE)}},
            {"_id": 0, "user_id": 1, "name": 1, "email": 1, "is_reviewer": 1}
        ).to_list(20)

    if not candidates:
        print("No user matching 'Parth' found in users collection.")
        print("Available users:")
        async for u in db.users.find({}, {"_id": 0, "user_id": 1, "name": 1, "email": 1}):
            print(f"  {u.get('user_id')}  {u.get('name')!r}  {u.get('email')!r}")
        client.close()
        return 1

    print(f"Found {len(candidates)} candidate(s):")
    for u in candidates:
        flag = u.get("is_reviewer", False)
        print(f"  {u.get('user_id')}  {u.get('name')!r}  {u.get('email')!r}  is_reviewer={flag}")
    print()

    # Set is_reviewer=True on every match (defensive — usually 1 record).
    result = await db.users.update_many(
        {"user_id": {"$in": [u["user_id"] for u in candidates]}},
        {"$set": {"is_reviewer": True}}
    )
    print(f"Updated {result.modified_count} user record(s) with is_reviewer=True.")

    # Verify
    print("\nAfter update:")
    async for u in db.users.find(
        {"user_id": {"$in": [u["user_id"] for u in candidates]}},
        {"_id": 0, "user_id": 1, "name": 1, "email": 1, "is_reviewer": 1}
    ):
        print(f"  {u.get('user_id')}  {u.get('name')!r}  is_reviewer={u.get('is_reviewer')}")

    client.close()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
