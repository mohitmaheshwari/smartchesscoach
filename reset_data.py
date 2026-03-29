#!/usr/bin/env python3
"""
Reset all data EXCEPT:
  - admin feedback
  - the super_admin user (bhutramohit@gmail.com)

Usage:
  # On your server (inside backend container):
  docker exec -it chess-coach-backend python3 reset_data.py

  # Or from host with MongoDB exposed:
  python3 reset_data.py
"""

import os
from pymongo import MongoClient

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://admin_user_mii_s_c:Mii123$44$@localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "chess_coach")

ADMIN_EMAIL = "bhutramohit@gmail.com"

# Collections to SKIP entirely (never touch)
SKIP_COLLECTIONS = {"admin_feedback", "feedback"}

# Collections to CLEAR completely
# (everything except users, which we handle specially)
CLEAR_ALL = True

def main():
    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]

    collections = db.list_collection_names()
    print(f"Database: {DB_NAME}")
    print(f"Collections found: {len(collections)}")
    print(f"Preserving: admin user ({ADMIN_EMAIL}) + feedback collections\n")

    for col_name in sorted(collections):
        col = db[col_name]
        before = col.count_documents({})

        # Skip feedback collections
        if col_name in SKIP_COLLECTIONS or "feedback" in col_name.lower():
            print(f"  ⏭  {col_name}: {before} docs — SKIPPED (feedback)")
            continue

        # Special handling for users: keep the admin, delete rest
        if col_name == "users":
            result = col.delete_many({"email": {"$ne": ADMIN_EMAIL}})
            # Ensure the admin stays super_admin
            col.update_one(
                {"email": ADMIN_EMAIL},
                {"$set": {"role": "super_admin"}}
            )
            after = col.count_documents({})
            print(f"  🧹 {col_name}: {before} → {after} docs (kept admin, deleted {result.deleted_count})")
            continue

        # Clear everything else
        result = col.delete_many({})
        print(f"  🗑  {col_name}: {before} → 0 docs (deleted {result.deleted_count})")

    print(f"\n✅ Reset complete. Only {ADMIN_EMAIL} (super_admin) and feedback data remain.")
    client.close()

if __name__ == "__main__":
    main()
