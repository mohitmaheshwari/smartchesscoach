"""
Grant `is_reviewer = True` to one or more user records so they can read
games / analyses / decryption output across ALL users (for content-
quality auditing of beta users).

Run inside the backend container:
    python scripts/grant_reviewer.py

By default this grants the flag to:
  - Parth Gilda (matched by name "parth" or email containing "parth")
  - Mohit (matched by email "bhutramohit@gmail.com")

Override with --email or --name to target someone else:
    python scripts/grant_reviewer.py --email someone@example.com
    python scripts/grant_reviewer.py --name "Jane Doe"

Idempotent — safe to run multiple times. Prints a summary of every
candidate found and what changed.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import re
import sys
from pathlib import Path
from typing import Dict, List

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv
load_dotenv(BACKEND_DIR / ".env")

from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "chess_coach")

# Default reviewers — looked up by either substring match. Email match
# wins when both are present (safer — emails are unique).
DEFAULT_REVIEWERS = [
    {"label": "Parth", "name_substr": "parth", "email_substr": "parth"},
    {"label": "Mohit", "name_substr": None, "email_substr": "bhutramohit"},
]


async def find_candidates(db, name_substr, email_substr) -> List[Dict]:
    """Return user docs that match name OR email substring (case-insensitive)."""
    seen = {}
    if email_substr:
        async for u in db.users.find(
            {"email": {"$regex": re.compile(re.escape(email_substr), re.IGNORECASE)}},
            {"_id": 0, "user_id": 1, "name": 1, "email": 1, "is_reviewer": 1}
        ):
            seen[u["user_id"]] = u
    if name_substr:
        async for u in db.users.find(
            {"name": {"$regex": re.compile(re.escape(name_substr), re.IGNORECASE)}},
            {"_id": 0, "user_id": 1, "name": 1, "email": 1, "is_reviewer": 1}
        ):
            seen.setdefault(u["user_id"], u)
    return list(seen.values())


async def grant_flag(db, user_ids: List[str]) -> int:
    if not user_ids:
        return 0
    result = await db.users.update_many(
        {"user_id": {"$in": user_ids}},
        {"$set": {"is_reviewer": True}},
    )
    return result.modified_count


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", action="append", default=[],
                        help="Grant reviewer flag to user with this email substring (repeatable).")
    parser.add_argument("--name", action="append", default=[],
                        help="Grant reviewer flag to user with this name substring (repeatable).")
    args = parser.parse_args()

    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    targets = []
    if args.email or args.name:
        for e in args.email:
            targets.append({"label": e, "name_substr": None, "email_substr": e})
        for n in args.name:
            targets.append({"label": n, "name_substr": n, "email_substr": None})
    else:
        targets = DEFAULT_REVIEWERS

    all_user_ids: List[str] = []

    for t in targets:
        print(f"=== {t['label']} ===")
        candidates = await find_candidates(db, t.get("name_substr"), t.get("email_substr"))
        if not candidates:
            print(f"  No user matching name~{t.get('name_substr')!r} or email~{t.get('email_substr')!r}.")
            continue
        for u in candidates:
            flag = u.get("is_reviewer", False)
            print(f"  {u.get('user_id')}  {u.get('name')!r}  {u.get('email')!r}  is_reviewer={flag}")
        all_user_ids.extend(u["user_id"] for u in candidates)
        print()

    if not all_user_ids:
        print("No matching users found. Available users in DB:")
        async for u in db.users.find({}, {"_id": 0, "user_id": 1, "name": 1, "email": 1}):
            print(f"  {u.get('user_id')}  {u.get('name')!r}  {u.get('email')!r}")
        client.close()
        return 1

    modified = await grant_flag(db, list(set(all_user_ids)))
    print(f"Updated {modified} user record(s) with is_reviewer=True.")
    print()

    print("After update:")
    async for u in db.users.find(
        {"user_id": {"$in": list(set(all_user_ids))}},
        {"_id": 0, "user_id": 1, "name": 1, "email": 1, "is_reviewer": 1},
    ):
        print(f"  {u.get('user_id')}  {u.get('name')!r}  {u.get('email')!r}  is_reviewer={u.get('is_reviewer')}")

    client.close()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
