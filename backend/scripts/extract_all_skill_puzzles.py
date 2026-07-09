#!/usr/bin/env python3
"""
Comprehensive Skill Puzzle Extraction

Extracts drill puzzles for ALL skills across ALL users:
- Engine 2 Skills: endgames, concepts, openings, trap sets, mate patterns
- Engine 1 Patterns: cognitive gaps (already extracted, this backfills)
- Motifs: forks, pins, skewers (if present)

This is the master script that wires up the entire drill system.
"""

import os
import sys
import asyncio
import logging
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient
from collections import defaultdict

# Add backend to path so imports work
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")


async def get_all_skill_ids():
    """Get all skill IDs from skill_tree.json"""
    import json
    from pathlib import Path

    skill_tree_path = Path(__file__).parent.parent / "data" / "coaching" / "skill_tree.json"
    with open(skill_tree_path) as f:
        tree = json.load(f)

    skill_ids = list(tree.get("skills", {}).keys())
    # Filter out notes
    skill_ids = [s for s in skill_ids if not s.startswith("_")]
    return skill_ids


async def extract_for_skill(db, skill_id):
    """Extract puzzles for a single skill across all users"""
    from services.skill_puzzle_extraction import extract_skill_puzzles_for_user

    total_created = 0
    total_skipped = 0
    users_with_evidence = 0

    # Get all users with coach_memory
    async for mem in db.coach_memory.find():
        user_id = mem.get("user_id")
        skills = mem.get("learning", {}).get("skills", [])

        # Check if this user has evidence for this skill
        skill_entry = next((s for s in skills if s.get("skill_id") == skill_id), None)
        if not skill_entry:
            continue

        evidence = skill_entry.get("evidence", [])
        if not evidence:
            continue

        users_with_evidence += 1

        try:
            result = await extract_skill_puzzles_for_user(db, user_id, skill_id)
            total_created += result.get("created", 0)
            total_skipped += result.get("skipped_dupe", 0)
        except Exception as e:
            logger.warning(f"Extraction failed for {user_id}/{skill_id}: {e}")

    return {
        "skill_id": skill_id,
        "users_with_evidence": users_with_evidence,
        "puzzles_created": total_created,
        "puzzles_skipped": total_skipped,
    }


async def main():
    db = AsyncIOMotorClient(MONGO_URL)[DB_NAME]

    print("=" * 80)
    print("COMPREHENSIVE SKILL PUZZLE EXTRACTION")
    print("=" * 80)

    skill_ids = await get_all_skill_ids()
    print(f"\nFound {len(skill_ids)} skills in skill_tree.json")

    results = {}

    for skill_id in sorted(skill_ids):
        try:
            result = await extract_for_skill(db, skill_id)
            results[skill_id] = result

            if result["users_with_evidence"] > 0:
                status = f"✅ {result['puzzles_created']} created"
                if result["puzzles_skipped"] > 0:
                    status += f" ({result['puzzles_skipped']} dupes)"
                print(
                    f"{skill_id:40} {result['users_with_evidence']:2} users  {status}"
                )
        except Exception as e:
            logger.error(f"Failed to extract {skill_id}: {e}")
            results[skill_id] = {"error": str(e)}

    # Summary
    print("\n" + "=" * 80)
    print("EXTRACTION SUMMARY")
    print("=" * 80)

    total_puzzles = 0
    total_users = 0
    skills_with_puzzles = 0

    for skill_id, result in results.items():
        if result.get("puzzles_created", 0) > 0:
            skills_with_puzzles += 1
            total_puzzles += result["puzzles_created"]
            total_users += result["users_with_evidence"]

    print(f"\nSkills with puzzles extracted: {skills_with_puzzles}/{len(skill_ids)}")
    print(f"Total puzzles created: {total_puzzles}")
    print(f"Total users with evidence: {total_users}")

    # Drill system readiness
    print("\n" + "=" * 80)
    print("DRILL SYSTEM READINESS")
    print("=" * 80)

    # Count by type
    by_type = defaultdict(int)
    import json
    from pathlib import Path

    skill_tree_path = Path(__file__).parent.parent / "data" / "coaching" / "skill_tree.json"
    with open(skill_tree_path) as f:
        tree = json.load(f)

    for skill_id, result in results.items():
        if result.get("puzzles_created", 0) > 0:
            skill_def = tree["skills"].get(skill_id, {})
            kind = skill_def.get("kind", "unknown")
            by_type[kind] += 1

    print("\nSkills ready for drill by type:")
    for kind in sorted(by_type.keys()):
        print(f"  {kind:20} {by_type[kind]}")

    print("\n✅ Extraction complete!")
    print("\nNext steps:")
    print("1. Users can now visit /training/skill/{skill_id} to drill")
    print("2. Skill drill pages will render extracted puzzles")
    print("3. Detector-grading will score moves based on skill application")


if __name__ == "__main__":
    asyncio.run(main())
