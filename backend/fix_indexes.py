#!/usr/bin/env python3
"""
Drop all problematic unique indexes across all collections.
Keeps only the default _id index and non-unique indexes.

Usage:
    docker exec -it chess-coach-backend python fix_indexes.py
"""

import os
try:
    from dotenv import load_dotenv
    load_dotenv()
except:
    pass

from pymongo import MongoClient

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "chess_coach")

client = MongoClient(MONGO_URL, serverSelectionTimeoutMS=5000)
db = client[DB_NAME]

print(f"Database: {DB_NAME}")
print("=" * 50)

dropped = 0
for col_name in db.list_collection_names():
    col = db[col_name]
    for idx in col.list_indexes():
        name = idx["name"]
        if name == "_id_":
            continue
        is_unique = idx.get("unique", False)
        if is_unique:
            print(f"  DROP  {col_name}.{name}  (unique on {dict(idx['key'])})")
            col.drop_index(name)
            dropped += 1

print("=" * 50)
print(f"Dropped {dropped} unique indexes.")

if dropped > 0:
    # Reset failed analysis jobs
    r = db.analysis_queue.update_many(
        {"status": {"$in": ["failed", "error"]}},
        {"$set": {"status": "pending", "attempts": 0}}
    )
    print(f"Reset {r.modified_count} failed jobs to pending.")

print("Done.")
