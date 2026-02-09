"""
Migration Script - Add Missing Collections and Indexes
Run this if you already ran init_db.py before the update.

This script is SAFE to run multiple times - it only adds what's missing.

Usage:
    python migrate_add_new_collections.py

Environment Variables Required:
    MONGO_URL - MongoDB connection string
    DB_NAME - Database name
"""

import os
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

# Configuration
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "chess_coach")


async def migrate():
    """Add new collections and indexes without affecting existing data."""
    
    print("=" * 60)
    print("MIGRATION: Adding New Collections & Indexes")
    print("=" * 60)
    print(f"\nConnecting to: {MONGO_URL}")
    print(f"Database: {DB_NAME}\n")
    
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    
    existing = await db.list_collection_names()
    print(f"Existing collections: {existing}\n")
    
    # ==================== NEW COLLECTIONS ====================
    
    new_collections = [
        "puzzle_attempts",
        "analysis_queue", 
        "notifications",
        "reflection_results"
    ]
    
    print("Creating new collections...")
    for coll in new_collections:
        if coll not in existing:
            await db.create_collection(coll)
            print(f"  ✅ Created: {coll}")
        else:
            print(f"  ⏭️  Already exists: {coll}")
    
    # ==================== NEW INDEXES ====================
    # Note: MongoDB ignores create_index if index already exists
    
    print("\nCreating new indexes...")
    
    # Puzzle attempts indexes
    try:
        await db.puzzle_attempts.create_index("attempt_id", unique=True)
        await db.puzzle_attempts.create_index("user_id")
        await db.puzzle_attempts.create_index("puzzle_id")
        await db.puzzle_attempts.create_index([("user_id", 1), ("puzzle_id", 1)])
        print("  ✅ puzzle_attempts indexes")
    except Exception as e:
        print(f"  ⚠️  puzzle_attempts indexes: {e}")
    
    # Analysis queue indexes
    try:
        await db.analysis_queue.create_index("queue_id", unique=True)
        await db.analysis_queue.create_index("user_id")
        await db.analysis_queue.create_index("status")
        await db.analysis_queue.create_index([("user_id", 1), ("status", 1)])
        print("  ✅ analysis_queue indexes")
    except Exception as e:
        print(f"  ⚠️  analysis_queue indexes: {e}")
    
    # Notifications indexes
    try:
        await db.notifications.create_index("notification_id", unique=True)
        await db.notifications.create_index("user_id")
        await db.notifications.create_index([("user_id", 1), ("read", 1)])
        await db.notifications.create_index("created_at")
        print("  ✅ notifications indexes")
    except Exception as e:
        print(f"  ⚠️  notifications indexes: {e}")
    
    # Reflection results indexes
    try:
        await db.reflection_results.create_index("reflection_id", unique=True)
        await db.reflection_results.create_index("user_id")
        await db.reflection_results.create_index("game_id")
        print("  ✅ reflection_results indexes")
    except Exception as e:
        print(f"  ⚠️  reflection_results indexes: {e}")
    
    # ==================== VERIFY ====================
    
    print("\n" + "=" * 60)
    print("VERIFICATION")
    print("=" * 60)
    
    final_collections = await db.list_collection_names()
    print(f"\nFinal collections ({len(final_collections)}):")
    for coll in sorted(final_collections):
        print(f"  - {coll}")
    
    print("\n" + "=" * 60)
    print("✅ Migration complete!")
    print("=" * 60)
    print("\nYour existing data is untouched.")
    print("New collections and indexes have been added.\n")
    
    client.close()


if __name__ == "__main__":
    asyncio.run(migrate())
