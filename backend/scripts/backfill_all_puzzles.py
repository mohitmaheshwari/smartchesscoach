#!/usr/bin/env python3
"""
Aggressive Puzzle Extraction Backfill

Re-extract puzzles from ALL analyzed games with LOWER thresholds.
This captures all meaningful mistakes (75cp+ for beginners down to 20cp+ for experts),
not just major blunders.

Expected result: 1,000 → 3,000-5,000+ puzzles
"""

import os
import asyncio
import logging
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")


async def backfill_all_games(db, limit_games=None):
    """Extract puzzles from all analyzed games"""
    from services.puzzle_extraction_service import extract_and_store_puzzles

    # Get all analyzed games
    query = {"is_analyzed": True}
    if limit_games:
        games_cursor = db.games.find(query).limit(limit_games)
    else:
        games_cursor = db.games.find(query)

    total_games = await db.games.count_documents(query)
    print(f"\nProcessing {total_games} analyzed games...")
    print("=" * 70)

    stats = {
        "processed": 0,
        "skipped": 0,
        "total_puzzles_created": 0,
        "errors": 0,
    }

    batch_num = 0
    async for game in games_cursor:
        batch_num += 1
        game_id = game.get("game_id")
        user_id = game.get("user_id")

        try:
            result = await extract_and_store_puzzles(db, game_id, user_id)
            if result:
                stats["processed"] += 1
                stats["total_puzzles_created"] += len(result)
                if batch_num % 100 == 0:
                    print(
                        f"  [{batch_num}/{total_games}] {stats['total_puzzles_created']} puzzles created"
                    )
            else:
                stats["skipped"] += 1
        except Exception as e:
            logger.debug(f"Game {game_id} extraction failed: {e}")
            stats["errors"] += 1

    print("=" * 70)
    print(f"\nBACKFILL RESULTS:")
    print(f"  Games processed:        {stats['processed']}")
    print(f"  Games skipped (no evals): {stats['skipped']}")
    print(f"  Total puzzles created:  {stats['total_puzzles_created']}")
    print(f"  Errors:                 {stats['errors']}")
    print(f"  Average per game:       {stats['total_puzzles_created'] / max(stats['processed'], 1):.2f}")

    return stats


async def compare_with_old_thresholds(db):
    """Show what we WOULD have extracted with old thresholds"""
    print("\n" + "=" * 70)
    print("THRESHOLD COMPARISON:")
    print("=" * 70)

    # Sample 50 games
    sample_stats = {"old": 0, "new": 0}

    async for analysis in db.game_analyses.find().limit(50):
        game_id = analysis.get("game_id")
        game = await db.games.find_one({"game_id": game_id})
        if not game:
            continue

        user_id = game.get("user_id")
        user_doc = await db.users.find_one({"user_id": user_id})
        user_rating = (user_doc or {}).get("rating", 1200)

        # Old thresholds
        if user_rating < 1000:
            old_threshold = 200
        elif user_rating < 1400:
            old_threshold = 150
        elif user_rating < 1800:
            old_threshold = 100
        else:
            old_threshold = 75

        # New thresholds
        if user_rating < 1000:
            new_threshold = 75
        elif user_rating < 1400:
            new_threshold = 50
        elif user_rating < 1800:
            new_threshold = 30
        else:
            new_threshold = 20

        for me in analysis.get("stockfish_analysis", {}).get("move_evaluations", []):
            if me.get("is_opponent_move"):
                continue

            cp_loss = me.get("cp_loss", 0)
            if cp_loss >= old_threshold:
                sample_stats["old"] += 1
            if cp_loss >= new_threshold:
                sample_stats["new"] += 1

    print(f"\nSample of 50 games:")
    print(f"  Old thresholds (100-200cp): {sample_stats['old']} puzzles")
    print(f"  New thresholds (20-75cp):   {sample_stats['new']} puzzles")
    print(f"  Improvement:                {sample_stats['new'] / max(sample_stats['old'], 1):.1f}x more puzzles")

    print(f"\nProjected for ALL {await db.games.count_documents({'is_analyzed': True})} games:")
    print(
        f"  Old estimate:  ~{await db.community_puzzles.count_documents({})} puzzles"
    )
    print(
        f"  New estimate:  ~{int(await db.community_puzzles.count_documents({}) * sample_stats['new'] / max(sample_stats['old'], 1))} puzzles"
    )


async def main():
    db = AsyncIOMotorClient(MONGO_URL)[DB_NAME]

    print("\n" + "=" * 70)
    print("AGGRESSIVE PUZZLE EXTRACTION BACKFILL")
    print("=" * 70)

    # Show comparison
    await compare_with_old_thresholds(db)

    # Run backfill
    print("\n" + "=" * 70)
    print("EXTRACTING WITH NEW THRESHOLDS...")
    print("=" * 70)

    # Clear old community_puzzles to re-extract cleanly (optional - comment to keep existing)
    # old_count = await db.community_puzzles.delete_many({})
    # print(f"\nCleared {old_count.deleted_count} old puzzles")

    stats = await backfill_all_games(db)

    print("\n" + "=" * 70)
    print("BACKFILL COMPLETE")
    print("=" * 70)
    print(f"\nTotal puzzles now available for drilling: {await db.community_puzzles.count_documents({})}")
    print("\nUsers can now access drills at:")
    print("  /training/pattern/piece_safety")
    print("  /training/pattern/missed_tactic")
    print("  /training/pattern/king_safety")
    print("  ... (9 cognitive gap patterns)")
    print("  /training/skill/endgame_opposition")
    print("  /training/skill/endgame_rule_of_square")


if __name__ == "__main__":
    asyncio.run(main())
