"""
Seed a Razorpay reviewer test account.

Creates (or updates) a user with email + bcrypt password hash so the
Razorpay onboarding reviewers can log in via the standard email/password
flow at /login. Idempotent — safe to re-run.

Usage:
    python scripts/seed_reviewer_account.py
    python scripts/seed_reviewer_account.py --email reviewer@example.com --password 'Strong#Pass123'

Defaults are intentionally hardcoded so the team has one canonical
reviewer credential. Override at the CLI when rotating.
"""

import argparse
import asyncio
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from passlib.context import CryptContext

load_dotenv(BACKEND_DIR / ".env")

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")

DEFAULT_EMAIL = "test@chessguru.ai"
DEFAULT_PASSWORD = "Password@123"
DEFAULT_NAME = "Test Reviewer"

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


async def seed(email: str, password: str, name: str) -> None:
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    email = email.strip().lower()
    password_hash = pwd_context.hash(password)

    existing = await db.users.find_one({"email": email}, {"_id": 0})
    if existing:
        await db.users.update_one(
            {"email": email},
            {"$set": {
                "password_hash": password_hash,
                "name": name,
                "is_reviewer": True,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }},
        )
        print(f"Updated existing user → {email} (user_id={existing['user_id']})")
    else:
        user_id = f"user_reviewer_{int(datetime.now(timezone.utc).timestamp())}"
        await db.users.insert_one({
            "user_id": user_id,
            "email": email,
            "name": name,
            "picture": None,
            "password_hash": password_hash,
            "is_reviewer": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "chess_com_username": None,
            "lichess_username": None,
        })
        print(f"Created reviewer account → {email} (user_id={user_id})")

    print()
    print("Hand these to the reviewer:")
    print(f"  URL:      https://chessguru.ai/login")
    print(f"  Email:    {email}")
    print(f"  Password: {password}")

    client.close()


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--email", default=DEFAULT_EMAIL)
    p.add_argument("--password", default=DEFAULT_PASSWORD)
    p.add_argument("--name", default=DEFAULT_NAME)
    args = p.parse_args()
    asyncio.run(seed(args.email, args.password, args.name))


if __name__ == "__main__":
    main()
