"""
Migration: Create learning_checkpoints collection for active recall tracking.

Stores user responses to active recall questions (ranking + concept) for learning analytics.
Used by spaced repetition to identify patterns to review.

Run once:
  python3 backend/migrations/001_create_learning_checkpoints.py
"""

import os
import asyncio
import logging
from motor.motor_asyncio import AsyncIOMotorClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def create_learning_checkpoints_collection():
    """Create collection and indexes for active recall tracking."""

    # Connect to MongoDB via Docker network with credentials
    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    client = AsyncIOMotorClient(mongo_url)
    db = client["test_database"]

    try:
        # Create collection if not exists
        collection_names = await db.list_collection_names()
        if "learning_checkpoints" not in collection_names:
            await db.create_collection("learning_checkpoints")
            logger.info("✓ Created learning_checkpoints collection")
        else:
            logger.info("✓ learning_checkpoints collection already exists")

        # Create indexes
        # Index 1: Query by user + pattern + time (spaced repetition service)
        await db.learning_checkpoints.create_index([
            ("user_id", 1),
            ("pattern", 1),
            ("timestamp", -1)
        ])
        logger.info("✓ Created index: user_id, pattern, timestamp")

        # Index 2: Query recent checkpoints by user (for dashboard)
        await db.learning_checkpoints.create_index([
            ("user_id", 1),
            ("timestamp", -1)
        ])
        logger.info("✓ Created index: user_id, timestamp")

        # Index 3: Find weak patterns (combined_score != "mastered")
        await db.learning_checkpoints.create_index([
            ("user_id", 1),
            ("combined_score", 1)
        ])
        logger.info("✓ Created index: user_id, combined_score")

        logger.info("\n✅ Migration complete: learning_checkpoints ready")

    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        raise
    finally:
        client.close()


if __name__ == "__main__":
    asyncio.run(create_learning_checkpoints_collection())
