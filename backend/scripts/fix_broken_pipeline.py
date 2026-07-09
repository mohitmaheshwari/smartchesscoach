#!/usr/bin/env python3
"""
Emergency pipeline fixes for bhutramohit

FIXES:
1. Enable analysis_worker async writes to game_analyses
2. Integrate pattern_decay_service into post-game flow
3. Trigger puzzle extraction backfill for all analyzed games
4. Route coaching messages to coach_messages collection
"""

import asyncio
import sys
import os
from pymongo import MongoClient
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")
USER_ID = "bhutramohit"

async def fix_1_verify_analysis_queue():
    """Check if analysis jobs are queued and waiting"""
    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]

    print("\n[FIX 1] Checking analysis_queue status...")
    pending = db.analysis_queue.count_documents({"status": "pending"})
    processing = db.analysis_queue.count_documents({"status": "processing"})
    completed = db.analysis_queue.count_documents({"status": "completed"})
    failed = db.analysis_queue.count_documents({"status": "failed"})

    print(f"  Pending: {pending}")
    print(f"  Processing: {processing}")
    print(f"  Completed: {completed}")
    print(f"  Failed: {failed}")
    print(f"  → If Pending > 0 and analysis_worker running but game_analyses empty:")
    print(f"    Workers are NOT writing to database (async/motor issue)")

    client.close()


async def fix_2_integrate_pattern_decay():
    """Backfill pattern decay scores for existing games"""
    async_client = AsyncIOMotorClient(MONGO_URL)
    async_db = async_client[DB_NAME]

    print("\n[FIX 2] Integrating pattern_decay_service...")

    from services.pattern_decay_service import compute_pattern_scores, get_puzzle_recoveries

    # Get user's recent games with cognitive gaps
    pipeline = [
        {"$match": {"user_id": USER_ID}},
        {"$lookup": {
            "from": "game_analyses",
            "localField": "game_id",
            "foreignField": "game_id",
            "as": "analysis"
        }},
        {"$unwind": {"path": "$analysis", "preserveNullAndEmptyArrays": True}},
        {"$sort": {"analyzed_at": -1}},
        {"$limit": 30},
        {"$project": {
            "game_id": 1,
            "cognitive_gaps": {"$cond": [
                {"$isArray": "$analysis.stockfish_analysis.move_evaluations"},
                {"$map": {
                    "input": "$analysis.stockfish_analysis.move_evaluations",
                    "as": "move",
                    "in": "$$move.cognitive_gap"
                }},
                []
            ]},
            "cognitive_gaps": {"$filter": {
                "input": {"$ifNull": ["$cognitive_gaps", []]},
                "as": "gap",
                "cond": {"$ne": ["$$gap", None]}
            }}
        }}
    ]

    games = []
    async for game in async_db.games.aggregate(pipeline):
        games.append(game)

    if games:
        puzzle_recoveries = await get_puzzle_recoveries(async_db, USER_ID)
        pattern_scores = compute_pattern_scores(games, puzzle_recoveries=puzzle_recoveries)

        # Store in coach_memory
        coach_memory = await async_db.coach_memory.find_one({"user_id": USER_ID})
        if coach_memory:
            await async_db.coach_memory.update_one(
                {"user_id": USER_ID},
                {"$set": {
                    "pattern_decay_scores": pattern_scores,
                    "pattern_decay_computed_at": datetime.now(timezone.utc).isoformat()
                }}
            )
            print(f"  ✓ Updated coach_memory with {len(pattern_scores)} pattern decay scores")
        else:
            await async_db.coach_memory.insert_one({
                "user_id": USER_ID,
                "pattern_decay_scores": pattern_scores,
                "pattern_decay_computed_at": datetime.now(timezone.utc).isoformat()
            })
            print(f"  ✓ Created coach_memory with {len(pattern_scores)} pattern decay scores")
    else:
        print(f"  ✗ No games with cognitive gaps found (analysis_worker must write first)")

    async_client.close()


async def fix_3_trigger_puzzle_extraction():
    """Backfill puzzle extraction for all analyzed games"""
    async_client = AsyncIOMotorClient(MONGO_URL)
    async_db = async_client[DB_NAME]

    print("\n[FIX 3] Triggering puzzle extraction backfill...")

    from services.puzzle_extraction_service import extract_puzzles_from_game

    # Find all analyzed games for user
    analyzed_games = await async_db.game_analyses.find(
        {"user_id": USER_ID}
    ).to_list(length=None)

    if not analyzed_games:
        print(f"  ✗ No analyzed games found (analysis_worker must write first)")
        async_client.close()
        return

    print(f"  Found {len(analyzed_games)} analyzed games")

    extracted_total = 0
    for analysis in analyzed_games[:10]:  # Start with first 10
        game_id = analysis.get("game_id")
        try:
            puzzles = await extract_puzzles_from_game(async_db, game_id, USER_ID)
            if puzzles:
                extracted_total += len(puzzles)
                print(f"  ✓ {game_id}: extracted {len(puzzles)} puzzles")
        except Exception as e:
            print(f"  ✗ {game_id}: {e}")

    print(f"  Total extracted: {extracted_total} puzzles")
    async_client.close()


async def fix_4_route_coaching_messages():
    """Route existing coaching feedback to coach_messages collection"""
    async_client = AsyncIOMotorClient(MONGO_URL)
    async_db = async_client[DB_NAME]

    print("\n[FIX 4] Routing coaching messages...")

    # Check postgame_analyses for coaching feedback
    postgame_analyses = await async_db.postgame_analyses.find(
        {"user_id": USER_ID}
    ).to_list(length=100)

    if postgame_analyses:
        messages_created = 0
        for analysis in postgame_analyses[:20]:
            game_id = analysis.get("game_id")
            feedback = analysis.get("coaching_feedback", {})

            if feedback.get("feedback_text"):
                msg_doc = {
                    "game_id": game_id,
                    "user_id": USER_ID,
                    "message_type": "coaching",
                    "content": feedback.get("feedback_text"),
                    "severity": feedback.get("severity", "info"),
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "source": "postgame_analysis"
                }

                existing = await async_db.coach_messages.find_one({
                    "game_id": game_id,
                    "user_id": USER_ID
                })

                if not existing:
                    await async_db.coach_messages.insert_one(msg_doc)
                    messages_created += 1

        print(f"  ✓ Created {messages_created} coach_messages from postgame feedback")
    else:
        print(f"  ℹ No postgame_analyses found to route")

    async_client.close()


async def main():
    print("=" * 60)
    print("ChessGuru Pipeline Emergency Fixes")
    print("=" * 60)

    await fix_1_verify_analysis_queue()
    await fix_2_integrate_pattern_decay()
    await fix_3_trigger_puzzle_extraction()
    await fix_4_route_coaching_messages()

    print("\n" + "=" * 60)
    print("FIX SUMMARY:")
    print("=" * 60)
    print("[1] Check if analysis_worker processes are running:")
    print("    $ ps aux | grep analysis_worker")
    print("\n[2] If workers running but game_analyses empty:")
    print("    → Switch from sync db to async motor in analysis_worker.py:1311")
    print("    → Change: db.game_analyses.update_one()")
    print("    → To: await async_db.game_analyses.update_one()")
    print("\n[3] Verify pattern decay is computed:")
    print("    $ mongo test_database --eval 'db.coach_memory.findOne()' | grep pattern_decay")
    print("\n[4] Verify puzzles extracted:")
    print("    $ mongo test_database --eval 'db.community_puzzles.count()'")
    print("\n[5] Verify coaching messages routed:")
    print("    $ mongo test_database --eval 'db.coach_messages.count()'")


if __name__ == "__main__":
    asyncio.run(main())
