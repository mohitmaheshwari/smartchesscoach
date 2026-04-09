"""
Test evaluate-pending endpoint directly on server.

Usage:
  docker cp scripts/test_evaluate_pending.py chess-coach-backend:/app/backend/scripts/
  docker exec -it chess-coach-backend python3 scripts/test_evaluate_pending.py
"""
import asyncio
import os
import sys
import json
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


async def main():
    from motor.motor_asyncio import AsyncIOMotorClient

    url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.environ.get("DB_NAME", "chess_coach")
    client = AsyncIOMotorClient(url)
    db = client[db_name]

    # Get most recent session
    session = await db.coach_sessions.find_one({}, sort=[("created_at", -1)])
    if not session:
        print("No sessions found")
        return

    session_id = session["session_id"]
    user_color = session.get("user_color", "white")
    user_id = session.get("user_id", "")
    print(f"Session: {session_id[:8]}, Color: {user_color}, User: {user_id}")

    # Test 1: Can we load player profile?
    print("\n=== Test 1: Player Profile ===")
    try:
        strength_doc = await db.player_strength_profiles.find_one(
            {"user_id": user_id},
            {"_id": 0, "strongest": 1, "weakest": 1, "overall_score": 1}
        )
        print(f"  Found: {strength_doc is not None}")
        if strength_doc:
            print(f"  Strongest: {strength_doc.get('strongest')}")
            print(f"  Weakest: {strength_doc.get('weakest')}")
    except Exception as e:
        print(f"  ERROR: {e}")

    # Test 2: Can we run read_board_like_a_coach?
    print("\n=== Test 2: Board Reading ===")
    try:
        from services.position_intelligence import read_board_like_a_coach
        fen = "rnbqkbnr/pppp1ppp/8/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R b KQkq - 1 2"
        result = read_board_like_a_coach(fen, user_color, 1200)
        print(f"  Result keys: {list(result.keys()) if result else 'None'}")
        if result:
            print(f"  Summary: {result.get('summary', '')[:80]}")
            print(f"  Phase: {result.get('phase')}")
            print(f"  Plan: {result.get('plan', '')[:80]}")
            print(f"  Observations: {len(result.get('observations', []))}")
    except Exception as e:
        print(f"  ERROR: {e}")
        import traceback
        traceback.print_exc()

    # Test 3: Check if fen_after_user bug exists
    print("\n=== Test 3: Variable Check ===")
    try:
        import chess
        board_before = chess.Board(fen)
        move = chess.Move.from_uci("b8c6")
        board_after = board_before.copy()
        board_after.push(move)
        fen_after = board_after.fen()
        commentary = read_board_like_a_coach(fen_after, user_color, 1200)
        print(f"  Using board_after.fen(): {'OK' if commentary else 'FAILED'}")
    except Exception as e:
        print(f"  ERROR: {e}")

    # Test 4: Compute weaknesses
    print("\n=== Test 4: Weaknesses ===")
    try:
        from services.player_behavior_tracker import compute_top_weaknesses
        weaknesses = await compute_top_weaknesses(db, user_id)
        print(f"  Found: {len(weaknesses)} weaknesses")
        for w in weaknesses:
            print(f"    {w['signal']}: severity={w['severity']}, count={w['count']}")
    except Exception as e:
        print(f"  ERROR: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
