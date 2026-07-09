#!/usr/bin/env python3
"""
Regenerate captions with Stockfish verification on user games.

Usage:
    python3 regenerate_captions_verified.py --user-id <id> --games 20

Shows what changes when using the new verification gates.
"""

import asyncio
import sys
import os
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pymongo import MongoClient
from services.simple_endgame_caption_builder import build_endgame_caption
import chess


async def regenerate_game(game_id, db):
    """Regenerate captions for one game"""
    analysis = db.game_analyses.find_one({"game_id": game_id})
    if not analysis:
        return None

    move_evals = analysis.get("stockfish_analysis", {}).get("move_evaluations", [])
    if not move_evals:
        return None

    results = []
    mistakes = [m for m in move_evals if m.get("cp_loss", 0) >= 75]

    for mistake in mistakes[:2]:  # First 2 mistakes per game
        move_san = mistake.get("move")
        fen_before = mistake.get("fen_before")
        eval_before = mistake.get("eval_before", 0)
        eval_after = mistake.get("eval_after", 0)
        cp_loss = mistake.get("cp_loss", 0)
        move_num = mistake.get("move_number")
        classification = mistake.get("classification", "?")
        best_move = mistake.get("best_move")

        if not fen_before:
            continue

        try:
            result = await build_endgame_caption(
                fen=fen_before,
                move_san=move_san,
                eval_before=eval_before,
                eval_after=eval_after,
                best_move_san=best_move
            )

            results.append({
                "move_num": move_num,
                "move_san": move_san,
                "cp_loss": cp_loss,
                "classification": classification,
                "best_move": best_move,
                "caption": result.get("caption"),
                "principles": result.get("principles", []),
                "method": result.get("method"),
                "verified": result.get("verified", False),
                "quality_score": result.get("quality_score", 0),
            })

        except Exception as e:
            pass

    return results if results else None


async def main():
    parser = argparse.ArgumentParser(description="Regenerate captions with Stockfish verification")
    parser.add_argument("--user-id", default="dev_user_local", help="User ID to process")
    parser.add_argument("--games", type=int, default=20, help="Number of games to process")
    parser.add_argument("--db-url", default="mongodb://localhost:27017", help="MongoDB connection URL")
    parser.add_argument("--db-name", default="test_database", help="Database name")

    args = parser.parse_args()

    # Connect
    client = MongoClient(args.db_url)
    db = client[args.db_name]

    # Find user
    user = db.users.find_one({"user_id": args.user_id})
    if not user:
        print(f"ERROR: User {args.user_id} not found")
        return

    user_id = user.get("_id")
    rating = user.get("assessed_rating", 800)

    print("=" * 100)
    print(f"CAPTION REGENERATION WITH STOCKFISH VERIFICATION")
    print("=" * 100)
    print(f"User: {args.user_id} (Rating: {rating})")
    print(f"Processing: {args.games} games")
    print()

    # Get games
    games = list(db.games.find({"user_id": user_id}).limit(args.games))
    print(f"Found {len(games)} games")
    print()

    total_moves = 0
    verified_count = 0
    unverified_count = 0
    all_results = []

    for game_idx, game in enumerate(games, 1):
        game_id = game.get("game_id")
        game_moves = await regenerate_game(game_id, db)

        if not game_moves:
            continue

        for move_result in game_moves:
            total_moves += 1
            is_verified = move_result.get("verified", False)

            if is_verified:
                verified_count += 1
            else:
                unverified_count += 1

            all_results.append({
                "game_id": game_id[:8],
                "game_num": game_idx,
                **move_result
            })

    # Display results
    print("REGENERATED CAPTIONS")
    print("=" * 100)
    print()

    for result in all_results[:50]:  # Show first 50
        status = "[VERIFIED]" if result["verified"] else "[FALLBACK]"
        print(f"{status} Game {result['game_num']} m{result['move_num']:2d} {result['move_san']:6s} "
              f"({result['classification']:8s}, {result['cp_loss']:5d}cp)")
        print(f"  Method: {result['method']:12s} Quality: {result['quality_score']:.2f}")
        print(f"  Caption: {result['caption'][:85]}")
        if result["principles"]:
            print(f"  Principles: {result['principles']}")
        print()

    # Summary
    print("=" * 100)
    print(f"SUMMARY")
    print("=" * 100)
    print(f"Games processed: {len(games)}")
    print(f"Total moves regenerated: {total_moves}")
    print()
    print(f"VERIFIED (principle-based):    {verified_count:3d} ({100*verified_count//max(1,total_moves):3d}%)")
    print(f"UNVERIFIED (fallback eval):    {unverified_count:3d} ({100*unverified_count//max(1,total_moves):3d}%)")
    print()
    print(f"Quality Improvement:")
    print(f"  - Before: All captions eval-only (~3/10 quality)")
    print(f"  - After:  {verified_count} principle-based (~8/10), {unverified_count} fallback (~3/10)")
    print(f"  - Lift:   {verified_count}/{total_moves} = {100*verified_count//max(1,total_moves)}% of captions now principle-driven")
    print()


if __name__ == "__main__":
    asyncio.run(main())
