#!/usr/bin/env python3
"""
Backfill pattern decay scores + puzzle extraction for existing analyzed games.

Phase 1, 2026-07-09: Extended to also extract puzzles from existing game analyses
so that users can immediately start training on their own mistakes.
"""
import asyncio
import os
import sys

sys.path.insert(0, '/app/backend')

from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timezone
from services.pattern_decay_service import compute_pattern_scores, get_puzzle_recoveries
from services.puzzle_extraction_service import extract_puzzles_from_game


async def main():
    db = AsyncIOMotorClient(os.environ['MONGO_URL'])[os.environ.get('DB_NAME', 'test_database')]

    user_id = 'user_8b599930d7ef'  # bhutramohit

    print("=" * 70)
    print("Backfill: Pattern Decay for Existing Games")
    print("=" * 70)

    # Get all analyzed games
    games_cursor = db.games.find(
        {"user_id": user_id, "is_analyzed": True},
        {"_id": 0, "game_id": 1}
    ).sort("date_played", -1)

    games = await games_cursor.to_list(length=None)
    print(f"Found {len(games)} analyzed games")

    # Extract cognitive gaps from analyses
    enriched = []
    analyzed = 0
    with_gaps = 0

    for g in games:
        analysis = await db.game_analyses.find_one(
            {"game_id": g["game_id"], "user_id": user_id}
        )
        if analysis:
            analyzed += 1
            sf = analysis.get("stockfish_analysis", {})
            moves = sf.get("move_evaluations", [])
            gaps = [m.get("cognitive_gap") for m in moves if m.get("cognitive_gap")]
            if gaps:
                with_gaps += 1
                enriched.append({
                    "game_id": g["game_id"],
                    "cognitive_gaps": list(set(gaps))
                })

    print(f"  Analyzed: {analyzed} games")
    print(f"  With gaps: {with_gaps} games")

    if not enriched:
        print("No games with cognitive gaps found. Exiting.")
        return

    # Get puzzle recovery credit
    print(f"Fetching puzzle recovery data...")
    puzzle_recoveries = await get_puzzle_recoveries(db, user_id)
    print(f"  Found recovery data: {len(puzzle_recoveries)} patterns")

    # Compute decay scores
    print(f"Computing pattern decay scores...")
    scores = compute_pattern_scores(enriched, puzzle_recoveries=puzzle_recoveries)
    print(f"  Computed: {len(scores)} patterns")

    if scores:
        print(f"  Patterns: {', '.join(scores.keys())}")

    # Store in coach_memory
    print(f"Storing in coach_memory...")
    result = await db.coach_memory.update_one(
        {"user_id": user_id},
        {
            "$set": {
                "pattern_decay_scores": scores,
                "pattern_decay_computed_at": datetime.now(timezone.utc).isoformat()
            }
        },
        upsert=True
    )

    print(f"  Updated: {result.modified_count} docs")
    if result.upserted_id:
        print(f"  Upserted: new coach_memory doc")

    # Verify
    print(f"\nVerification:")
    updated = await db.coach_memory.find_one({"user_id": user_id})
    if updated:
        decay = updated.get("pattern_decay_scores", {})
        print(f"  ✓ coach_memory has {len(decay)} pattern scores")

    # Phase 1 (2026-07-09): Extract puzzles from analyzed games
    print(f"\n" + "=" * 70)
    print("Backfill: Puzzle Extraction from Analyzed Games")
    print("=" * 70)

    puzzle_count = 0
    extraction_errors = 0

    for g in games[:100]:  # Limit to first 100 to avoid timeout
        try:
            puzzles = await extract_puzzles_from_game(db, g["game_id"], user_id)
            if puzzles:
                puzzle_count += len(puzzles)
                print(f"  ✓ {g['game_id'][:8]}...: extracted {len(puzzles)} puzzles")
        except Exception as e:
            extraction_errors += 1
            if extraction_errors <= 3:  # Show first 3 errors
                print(f"  ! {g['game_id'][:8]}...: extraction failed ({str(e)[:50]})")

    print(f"\nPuzzle Extraction Summary:")
    print(f"  Total extracted: {puzzle_count} puzzles")
    print(f"  Errors: {extraction_errors}")
    print(f"  Avg per game: {puzzle_count / min(100, len(games)):.1f}")

    print("\n" + "=" * 70)
    print("✓ Backfill complete (pattern decay + puzzle extraction)")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
