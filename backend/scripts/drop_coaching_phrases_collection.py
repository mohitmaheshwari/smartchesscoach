"""One-time migration: drop the coaching_phrases mongo collection.

Run after PR-6E (2026-05-27) deletes services/smart_coaching.py. The
collection cached LLM responses for:
  - generate_smart_coach_explanation (deleted PR-5, commit abbd7f88)
  - generate_smart_user_feedback (deleted PR-6E)

With both writers gone the collection is an orphan. Drop it to free
disk + keep mongo browse-able. Safe to run multiple times (mongo's
drop is idempotent — succeeds even when the collection doesn't exist).

Per [[one-source-of-truth-for-coaching]] — every coaching surface
flows through caption_pipeline.build_move_teaching_decision; no LLM
caches remain.

Usage:
    docker exec chess-coach-backend python /app/backend/scripts/drop_coaching_phrases_collection.py
"""
from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from motor.motor_asyncio import AsyncIOMotorClient


async def main() -> None:
    url = os.environ.get(
        "MONGO_URL",
        "mongodb://admin_user_mii_s_c:Mii123$44$@host.docker.internal:27018/?authSource=admin",
    )
    db_name = os.environ.get("DB_NAME", "chess_coach")
    db = AsyncIOMotorClient(url)[db_name]

    collections = await db.list_collection_names()
    if "coaching_phrases" not in collections:
        print(f"coaching_phrases collection not present in {db_name} — nothing to drop")
        return

    count = await db.coaching_phrases.count_documents({})
    print(f"Dropping coaching_phrases ({count} cached LLM responses)...")
    await db.coaching_phrases.drop()
    print("Dropped.")

    # Re-check.
    collections_after = await db.list_collection_names()
    if "coaching_phrases" in collections_after:
        print("WARNING: collection still listed after drop — investigate")
    else:
        print("Confirmed gone.")


if __name__ == "__main__":
    asyncio.run(main())
