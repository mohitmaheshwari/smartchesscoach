"""Audit raw data structure in database"""
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import json

async def audit():
    client = AsyncIOMotorClient("mongodb://localhost:27017")
    db = client["test_database"]

    print("\n" + "="*80)
    print("RAW DATA STRUCTURE AUDIT")
    print("="*80 + "\n")

    # Get a game with analysis
    game = await db.games.find_one({"is_analyzed": True})
    if not game:
        print("❌ No analyzed games found")
        return

    game_id = game["game_id"]
    print(f"Game: {game_id}")
    print(f"Analyzed: {game.get('is_analyzed')}\n")

    # Get its analysis
    analysis = await db.game_analyses.find_one({"game_id": game_id})
    if not analysis:
        print("❌ No analysis found for this game")
        return

    print("Analysis keys:", list(analysis.keys()))
    print()

    # Check stockfish_analysis
    sf = analysis.get("stockfish_analysis", {})
    print(f"✓ stockfish_analysis exists: {bool(sf)}")
    print(f"  Keys: {list(sf.keys())}")
    print(f"  move_evaluations count: {len(sf.get('move_evaluations', []))}")
    print()

    # Sample first 3 moves
    if sf.get("move_evaluations"):
        print("Sample moves (first 3):\n")
        for i, move in enumerate(sf["move_evaluations"][:3]):
            print(f"  Move {i}:")
            print(f"    move: {move.get('move')}")
            print(f"    is_user_move: {move.get('is_user_move')}")
            print(f"    cp_loss: {move.get('cp_loss')}")
            print(f"    cognitive_gap: {move.get('cognitive_gap')}")
            print(f"    evaluation: {move.get('evaluation')}")
            print()

    # Count by cp_loss ranges
    moves = sf.get("move_evaluations", [])
    user_moves = [m for m in moves if m.get("is_user_move")]

    ranges = {
        "0-50cp": [m for m in user_moves if 0 <= m.get("cp_loss", 0) < 50],
        "50-100cp": [m for m in user_moves if 50 <= m.get("cp_loss", 0) < 100],
        "100-200cp": [m for m in user_moves if 100 <= m.get("cp_loss", 0) < 200],
        "200+cp": [m for m in user_moves if m.get("cp_loss", 0) >= 200],
    }

    print("User move distribution:")
    for range_name, moves_in_range in ranges.items():
        print(f"  {range_name}: {len(moves_in_range)} moves")
        if moves_in_range:
            sample = moves_in_range[0]
            print(f"    Sample: {sample.get('move')} (gap: {sample.get('cognitive_gap')})")

    # Check cognitive_gap distribution
    gaps = {}
    for m in user_moves:
        gap = m.get("cognitive_gap") or "NONE"
        gaps[gap] = gaps.get(gap, 0) + 1

    print(f"\nCognitive gap distribution (ALL user moves):")
    for gap, count in sorted(gaps.items(), key=lambda x: -x[1]):
        print(f"  {gap:20} {count:3}x")

    client.close()

asyncio.run(audit())
