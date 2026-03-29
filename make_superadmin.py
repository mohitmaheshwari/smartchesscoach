#!/usr/bin/env python3
"""
Make a user super_admin by email.

Usage (inside the backend Docker container):
  docker exec -it chess-coach-backend python3 make_superadmin.py

Or from host with MongoDB exposed:
  python3 make_superadmin.py
"""

import os
from pymongo import MongoClient

# Config — change these if needed
EMAIL = "bhutramohit@gmail.com"
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://admin_user_mii_s_c:Mii123$44$@localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "chess_coach")

def main():
    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]

    user = db.users.find_one({"email": EMAIL})
    if not user:
        print(f"❌ No user found with email: {EMAIL}")
        print("   (They need to log in at least once before being promoted)")
        client.close()
        return

    old_role = user.get("role", "user")
    if old_role == "super_admin":
        print(f"✅ {EMAIL} is already super_admin. Nothing to do.")
        client.close()
        return

    result = db.users.update_one(
        {"email": EMAIL},
        {"$set": {"role": "super_admin"}}
    )

    if result.modified_count == 1:
        print(f"✅ Done! {EMAIL} promoted: {old_role} → super_admin")
    else:
        print(f"⚠️  Update matched but didn't modify. Current role: {old_role}")

    client.close()

if __name__ == "__main__":
    main()
