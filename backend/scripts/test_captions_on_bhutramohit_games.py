#!/usr/bin/env python3
"""
Test deterministic caption system on all bhutramohit games.

Generates principle-based captions for every move and compares with engine truth.
"""

import asyncio
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from motor.motor_asyncio import AsyncIOMotorClient
from services.simple_endgame_caption_builder import build_endgame_caption
import chess


async def main():
    # Connect to MongoDB
    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.environ.get("DB_NAME", "test_database")

    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]

    print("=" * 80)
    print("Testing Deterministic Captions on bhutramohit Games")
    print("=" * 80)
    print()

    # Get bhutramohit's user ID (dev_user_local)
    user = await db.users.find_one({"user_id": "dev_user_local"})
    if not user:
        print("ERROR: Could not find dev_user_local user")
        return

    user_id = user["_id"]
    print(f"User: {user['user_id']} (ID: {user_id})")
    print()

    # Get all games by this user
    games = []
    async for game in db.games.find({"user_id": user_id}):
        games.append(game)

    print(f"Found {len(games)} games")
    print()

    # For each game, get analysis and generate captions
    total_moves = 0
    captions_generated = 0
    blunders_found = 0
    mistakes_found = 0
    principles_detected_count = 0

    results = []

    for game_idx, game in enumerate(games[:5]):  # Test on first 5 games
        game_id = game["game_id"]
        print(f"\n--- Game {game_idx + 1}: {game_id} ---")

        # Get analysis
        analysis = await db.game_analyses.find_one({"game_id": game_id})
        if not analysis:
            print("  (no analysis found)")
            continue

        move_evals = analysis.get("move_evaluations", [])
        print(f"  Moves analyzed: {len(move_evals)}")

        game_results = {
            "game_id": game_id,
            "moves": [],
        }

        for move_eval in move_evals:
            move_num = move_eval.get("move_number")
            move_san = move_eval.get("move")
            fen_before = move_eval.get("fen_before")
            eval_before = move_eval.get("eval_before")
            eval_after = move_eval.get("eval_after")
            best_move = move_eval.get("best_move")
            cp_loss = move_eval.get("cp_loss", 0)
            classification = move_eval.get("classification")

            if not fen_before or not move_san:
                continue

            total_moves += 1

            # Only analyze blunders and mistakes
            if classification not in ("blunder", "mistake"):
                continue

            # Generate caption
            try:
                caption_result = await build_endgame_caption(
                    fen=fen_before,
                    move_san=move_san,
                    eval_before=eval_before or 0,
                    eval_after=eval_after or 0,
                    best_move_san=best_move,
                )

                captions_generated += 1
                principles = caption_result.get("principles", [])
                if principles:
                    principles_detected_count += len(principles)

                # Track stats
                if classification == "blunder":
                    blunders_found += 1
                elif classification == "mistake":
                    mistakes_found += 1

                move_result = {
                    "move_number": move_num,
                    "move_san": move_san,
                    "classification": classification,
                    "cp_loss": cp_loss,
                    "caption": caption_result["caption"],
                    "principles": principles,
                    "quality_score": caption_result["quality_score"],
                    "best_move": best_move,
                }

                game_results["moves"].append(move_result)

                # Print sample
                if len(game_results["moves"]) <= 3:  # Show first 3 per game
                    print(f"\n    Move {move_num}: {move_san}")
                    print(f"      Eval: {eval_before} → {eval_after} (loss: {cp_loss}cp)")
                    print(f"      Class: {classification}")
                    print(f"      Caption: {caption_result['caption']}")
                    print(f"      Principles: {principles or 'none'}")
                    print(f"      Quality: {caption_result['quality_score']:.2f}")

            except Exception as e:
                print(f"    Error on move {move_num} {move_san}: {e}")

        results.append(game_results)

    # Summary
    print()
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Games tested: {len([r for r in results if r['moves']])}")
    print(f"Total moves analyzed: {total_moves}")
    print(f"Blunders: {blunders_found}")
    print(f"Mistakes: {mistakes_found}")
    print(f"Captions generated: {captions_generated}")
    print(f"Principles detected (avg): {principles_detected_count / max(1, captions_generated):.2f} per caption")
    print()

    # Show detailed results
    print("=" * 80)
    print("DETAILED RESULTS")
    print("=" * 80)
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
