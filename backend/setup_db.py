#!/usr/bin/env python3
"""
ChessGuru — MongoDB Setup Script

Usage:
    python setup_db.py              # Create collections + indexes (safe, won't delete data)
    python setup_db.py --reset      # DROP all collections first, then recreate (DESTRUCTIVE)
    python setup_db.py --seed       # Create collections + indexes + seed demo data

Requires: MONGO_URL and DB_NAME environment variables (or .env file)
"""

import asyncio
import os
import sys
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "chessguru")

# All collections with their indexes
COLLECTIONS = {
    # ─── CORE ───
    "users": [
        {"keys": [("user_id", 1)], "unique": True},
        {"keys": [("email", 1)], "unique": True, "sparse": True},
    ],
    "user_sessions": [
        {"keys": [("session_id", 1)], "unique": True},
        {"keys": [("user_id", 1)]},
        {"keys": [("expires_at", 1)], "expireAfterSeconds": 0},
    ],

    # ─── GAMES ───
    "games": [
        {"keys": [("game_id", 1)], "unique": True},
        {"keys": [("user_id", 1), ("imported_at", -1)]},
        {"keys": [("user_id", 1), ("is_analyzed", 1)]},
        {"keys": [("user_id", 1), ("reviewed", 1)]},
        {"keys": [("user_id", 1), ("review_status", 1)]},
    ],
    "game_analyses": [
        {"keys": [("game_id", 1), ("user_id", 1)], "unique": True},
        {"keys": [("user_id", 1)]},
        {"keys": [("game_id", 1)]},
    ],
    "analysis_queue": [
        {"keys": [("game_id", 1)]},
        {"keys": [("user_id", 1)]},
        {"keys": [("status", 1), ("created_at", 1)]},
    ],

    # ─── COACHING ───
    "coach_sessions": [
        {"keys": [("session_id", 1)], "unique": True},
        {"keys": [("user_id", 1), ("created_at", -1)]},
    ],
    "coach_messages": [
        {"keys": [("session_id", 1), ("created_at", 1)]},
        {"keys": [("user_id", 1)]},
    ],
    "coach_memory": [
        {"keys": [("user_id", 1)]},
    ],

    # ─── PLAYER IDENTITY ───
    "player_identities": [
        {"keys": [("user_id", 1)], "unique": True},
    ],
    "player_identity": [
        {"keys": [("user_id", 1)]},
    ],
    "player_profiles": [
        {"keys": [("user_id", 1)], "unique": True},
    ],
    "identity_snapshots": [
        {"keys": [("user_id", 1), ("created_at", -1)]},
    ],
    "chess_understanding": [
        {"keys": [("user_id", 1)]},
    ],

    # ─── THINKING SCORES ───
    "thinking_scores": [
        {"keys": [("user_id", 1), ("game_id", 1)]},
        {"keys": [("user_id", 1), ("calculated_at", -1)]},
    ],

    # ─── TRAINING ───
    "community_training_positions": [
        {"keys": [("position_id", 1)], "unique": True},
        {"keys": [("pattern_type", 1)]},
        {"keys": [("source_user_id", 1)]},
        {"keys": [("source_user_rating", 1)]},
        {"keys": [("difficulty", 1)]},
    ],
    "training_solve_attempts": [
        {"keys": [("user_id", 1), ("position_id", 1)]},
        {"keys": [("user_id", 1), ("solved_at", -1)]},
    ],
    "training_attempts": [
        {"keys": [("user_id", 1)]},
    ],
    "puzzle_attempts": [
        {"keys": [("user_id", 1)]},
    ],
    "puzzle_attempts_history": [
        {"keys": [("user_id", 1)]},
    ],
    "puzzle_progress": [
        {"keys": [("user_id", 1)]},
    ],

    # ─── FEEDBACK ───
    "move_feedback": [
        {"keys": [("status", 1)]},
        {"keys": [("created_at", -1)]},
        {"keys": [("user_id", 1)]},
        {"keys": [("game_id", 1)]},
    ],
    "coaching_feedback": [
        {"keys": [("user_id", 1)]},
    ],

    # ─── CONCEPTS & HABITS ───
    "user_concept_understanding": [
        {"keys": [("user_id", 1), ("concept_id", 1)]},
    ],
    "user_habit_progress": [
        {"keys": [("user_id", 1)]},
    ],
    "question_insights": [
        {"keys": [("user_id", 1)]},
        {"keys": [("game_id", 1)]},
    ],

    # ─── OPENINGS ───
    "user_opening_progress": [
        {"keys": [("user_id", 1)]},
    ],
    "opening_practice_sessions": [
        {"keys": [("user_id", 1)]},
    ],

    # ─── JOURNEY & MISSIONS ───
    "journey_stats": [
        {"keys": [("user_id", 1)]},
    ],
    "behavioral_missions": [
        {"keys": [("user_id", 1)]},
    ],
    "module_injections": [
        {"keys": [("user_id", 1)]},
    ],

    # ─── MISC ───
    "notifications": [
        {"keys": [("user_id", 1), ("created_at", -1)]},
        {"keys": [("user_id", 1), ("read", 1)]},
    ],
    "postgame_analyses": [
        {"keys": [("game_id", 1)]},
        {"keys": [("user_id", 1)]},
    ],
    "user_thoughts": [
        {"keys": [("user_id", 1), ("game_id", 1)]},
    ],
}


async def setup_db(reset=False, seed=False):
    print(f"Connecting to MongoDB: {MONGO_URL}")
    print(f"Database: {DB_NAME}")
    print()

    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    if reset:
        print("⚠️  RESETTING DATABASE — dropping all collections...")
        existing = await db.list_collection_names()
        for coll_name in existing:
            await db.drop_collection(coll_name)
            print(f"  Dropped: {coll_name}")
        print()

    # Create collections and indexes
    print("Creating collections and indexes...")
    for coll_name, indexes in COLLECTIONS.items():
        # Ensure collection exists
        existing = await db.list_collection_names()
        if coll_name not in existing:
            await db.create_collection(coll_name)
            print(f"  ✓ Created: {coll_name}")
        else:
            print(f"  · Exists:  {coll_name}")

        # Create indexes
        coll = db[coll_name]
        for idx in indexes:
            keys = idx["keys"]
            opts = {k: v for k, v in idx.items() if k != "keys"}
            try:
                name = await coll.create_index(keys, **opts)
                # Only print if it's a new index
            except Exception as e:
                print(f"    ⚠ Index error on {coll_name}: {e}")

    print(f"\n✅ {len(COLLECTIONS)} collections ready with indexes.")

    if seed:
        print("\nSeeding demo data...")
        await seed_demo_data(db)

    # Final summary
    print("\n── Summary ──")
    for coll_name in sorted(COLLECTIONS.keys()):
        count = await db[coll_name].count_documents({})
        indexes = await db[coll_name].index_information()
        idx_count = len([k for k in indexes if k != "_id_"])
        print(f"  {coll_name}: {count} docs, {idx_count} indexes")

    client.close()
    print("\nDone.")


async def seed_demo_data(db):
    """Seed minimal demo data for testing."""
    now = datetime.now(timezone.utc).isoformat()

    # Demo user
    demo_user = {
        "user_id": "demo_user_001",
        "email": "demo@chessguru.com",
        "name": "Demo Player",
        "picture": None,
        "role": "super_admin",
        "created_at": now,
        "chess_com_username": None,
        "lichess_username": None,
    }
    await db.users.update_one(
        {"user_id": demo_user["user_id"]},
        {"$setOnInsert": demo_user},
        upsert=True
    )
    print("  ✓ Demo user created (demo@chessguru.com)")

    # Demo player profile
    demo_profile = {
        "user_id": "demo_user_001",
        "estimated_elo": 1200,
        "average_accuracy": 55.0,
        "games_analyzed": 0,
        "created_at": now,
    }
    await db.player_profiles.update_one(
        {"user_id": demo_profile["user_id"]},
        {"$setOnInsert": demo_profile},
        upsert=True
    )
    print("  ✓ Demo player profile created")

    # Demo player identity
    demo_identity = {
        "user_id": "demo_user_001",
        "play_style": "developing",
        "blunder_taxonomy": {"by_type": {}},
        "strengths": [],
        "priority_focus": None,
        "updated_at": now,
    }
    await db.player_identities.update_one(
        {"user_id": demo_identity["user_id"]},
        {"$setOnInsert": demo_identity},
        upsert=True
    )
    print("  ✓ Demo player identity created")

    print("  ✓ Seed complete. Import games to populate analysis data.")


if __name__ == "__main__":
    reset = "--reset" in sys.argv
    seed = "--seed" in sys.argv

    if reset:
        confirm = input("This will DELETE ALL DATA. Type 'yes' to confirm: ")
        if confirm != "yes":
            print("Aborted.")
            sys.exit(0)

    asyncio.run(setup_db(reset=reset, seed=seed))
