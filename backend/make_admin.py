#!/usr/bin/env python3
"""
Grant super_admin role to a user.
Usage: python make_admin.py
Requires: MONGO_URL and DB_NAME environment variables (or .env file)
"""

import asyncio
import os

from motor.motor_asyncio import AsyncIOMotorClient

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "chessguru")
EMAIL = "bhutramohit@gmail.com"


async def main():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    result = await db.users.update_one(
        {"email": EMAIL},
        {"$set": {"role": "super_admin"}}
    )

    if result.matched_count:
        print(f"Done. {EMAIL} is now super_admin.")
    else:
        print(f"No user found with email {EMAIL}. Make sure you've logged in at least once.")

    client.close()


if __name__ == "__main__":
    asyncio.run(main())
