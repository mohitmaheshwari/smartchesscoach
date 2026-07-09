#!/usr/bin/env python3
"""
Test deterministic captions on real games from the database.
Generate captions and show them to the user for quality assessment.
"""

import asyncio
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pymongo import MongoClient
from services.simple_endgame_caption_builder import build_endgame_caption
import chess


def main():
    # Connect to MongoDB
    client = MongoClient("mongodb://localhost:27017")
    db = client["test_database"]

    print("=" * 80)
    print("Testing Deterministic Captions on Real Games")
    print("=" * 80)
    print()

    # Get dev_user_local games
    user = db.users.find_one({"user_id": "dev_user_local"})
    if not user:
        print("ERROR: Could not find dev_user_local")
        return

    user_id = user["_id"]
    print(f"User: {user['user_id']}\n")

    # Get games
    games = list(db.games.find({"user_id": user_id}).limit(10))
    print(f"Found {len(games)} games (showing first 10)\n")

    total_captions = 0
    principles_found = 0
    quality_scores = []

    for game_idx, game in enumerate(games):
        game_id = game["game_id"]
        print(f"\n--- Game {game_idx + 1}: {game_id} ---")

        # Get analysis
        analysis = db.game_analyses.find_one({"game_id": game_id})
        if not analysis:
            print("  (no analysis)")
            continue

        move_evals = analysis.get("move_evaluations", [])

        # Find mistakes/blunders
        mistakes = [m for m in move_evals if m.get("classification") in ("mistake", "blunder")]

        if not mistakes:
            print(f"  (no mistakes/blunders in {len(move_evals)} moves)")
            continue

        print(f"  {len(move_evals)} moves analyzed, {len(mistakes)} mistakes/blunders\n")

        # Generate captions for first 3 mistakes
        for move in mistakes[:3]:
            move_num = move.get("move_number")
            move_san = move.get("move")
            fen_before = move.get("fen_before")
            eval_before = move.get("eval_before", 0)
            eval_after = move.get("eval_after", 0)
            best_move = move.get("best_move")
            classification = move.get("classification")
            cp_loss = move.get("cp_loss", 0)

            if not fen_before or not move_san:
                continue

            try:
                # Generate caption
                result = asyncio.run(build_endgame_caption(
                    fen=fen_before,
                    move_san=move_san,
                    eval_before=eval_before,
                    eval_after=eval_after,
                    best_move_san=best_move,
                ))

                total_captions += 1
                caption = result["caption"]
                principles = result["principles"]
                quality = result["quality_score"]

                if principles:
                    principles_found += 1

                quality_scores.append(quality)

                print(f"  Move {move_num}: {move_san} ({classification}, {cp_loss}cp loss)")
                print(f"    Caption: {caption}")
                print(f"    Principles: {principles if principles else '(none)'}")
                print(f"    Quality: {quality:.2f}")
                print()

            except Exception as e:
                print(f"  Error on move {move_num} {move_san}: {e}")

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Captions generated: {total_captions}")
    print(f"With principles: {principles_found} ({100*principles_found//max(1,total_captions)}%)")
    print(f"Avg quality score: {sum(quality_scores)/len(quality_scores):.2f}" if quality_scores else "N/A")
    print()
    print("RATING (out of 10):")
    print("  - Quality of captions: ?")
    print("  - Usefulness as coaching: ?")
    print("  - Overall: ?")
    print()
    print("(Please review above and rate)")


if __name__ == "__main__":
    main()
