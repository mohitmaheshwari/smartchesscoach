"""
Clear old cached coaching text that contains "Horsey", "Slicey Boi", "Little Soldier", "Tower".
Forces re-generation with new piece names (knight, bishop, pawn, rook).

Also clears coaching_feedback_cache so LLM regenerates with better prompts.

Usage:
  docker cp clear_old_names.py chess-coach-backend:/app/backend/ && docker exec -it chess-coach-backend python3 clear_old_names.py
"""

import os
from pymongo import MongoClient

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://admin_user_mii_s_c:Mii123$44$@localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "chess_coach")

client = MongoClient(MONGO_URL)
db = client[DB_NAME]

# 1. Clear V5 decryption cache (forces re-generation)
v5_count = db.game_decryptions_v5.count_documents({})
if v5_count > 0:
    db.game_decryptions_v5.delete_many({})
    print(f"  Cleared {v5_count} V5 decryption caches")
else:
    print(f"  No V5 decryption caches found")

# 2. Clear coaching cache
cache_count = db.coaching_cache.count_documents({})
if cache_count > 0:
    db.coaching_cache.delete_many({})
    print(f"  Cleared {cache_count} coaching caches")
else:
    print(f"  No coaching caches found")

# 3. Clear LLM coaching feedback cache
fb_count = db.coaching_feedback_cache.count_documents({})
if fb_count > 0:
    db.coaching_feedback_cache.delete_many({})
    print(f"  Cleared {fb_count} coaching feedback caches")
else:
    print(f"  No coaching feedback caches found")

# 4. Check coach_summary fields in game_analyses for old names
old_names = ["Horsey", "Slicey Boi", "Little Soldier", "Tower"]
for name in old_names:
    count = db.game_analyses.count_documents({
        "$or": [
            {"coach_summary.behavioral_insight": {"$regex": name}},
            {"coach_summary.key_observation": {"$regex": name}},
        ]
    })
    if count > 0:
        # Clear those summaries so they regenerate
        db.game_analyses.update_many(
            {"$or": [
                {"coach_summary.behavioral_insight": {"$regex": name}},
                {"coach_summary.key_observation": {"$regex": name}},
            ]},
            {"$unset": {"coach_summary": ""}}
        )
        print(f"  Cleared {count} analyses with '{name}' in coach_summary")

print("\nDone. Old cached text cleared. Will regenerate on next page load.")
client.close()
