"""
Debug opening guidance end-to-end.
Simulates what evaluate-pending does with real session data.

Usage:
  docker cp scripts/debug_opening_guidance.py chess-coach-backend:/app/backend/scripts/
  docker exec -it chess-coach-backend python3 scripts/debug_opening_guidance.py
"""

import asyncio
import os
import sys
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from motor.motor_asyncio import AsyncIOMotorClient


async def main():
    url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.environ.get("DB_NAME", "chess_coach")
    client = AsyncIOMotorClient(url)
    db = client[db_name]

    # Get most recent session
    session = await db.coach_sessions.find_one({}, sort=[("created_at", -1)], projection={"_id": 0})
    if not session:
        print("No sessions found")
        return

    sid = session.get("session_id", "?")[:8]
    print(f"=== Session: {sid} ===")
    print(f"User color: {session.get('user_color')}")
    print(f"Opening key: {session.get('opening_key')}")
    print(f"Opening to teach: {session.get('opening_to_teach')}")
    print(f"Opening teaching active: {session.get('opening_teaching_active')}")
    print(f"Opening teaching moves: {session.get('opening_teaching_moves', [])[:5]}")
    print(f"Opening teaching index: {session.get('opening_teaching_index')}")
    print(f"Move history length: {len(session.get('move_history', []))}")
    print()

    # Simulate what evaluate-pending does
    print("=== Simulating evaluate-pending guidance ===")

    # Step 1: Query session like evaluate-pending does
    session_doc = await db.coach_sessions.find_one(
        {"session_id": session["session_id"]},
        {"_id": 0, "evaluations": 1, "user_color": 1, "user_id": 1, "move_history": 1,
         "coaching_decisions": 1, "last_coaching_move_index": 1,
         "opening_to_teach": 1, "opening_key": 1, "opening_teaching_active": 1,
         "opening_teaching_moves": 1, "opening_teaching_index": 1,
         "behavior_summary": 1}
    )

    print(f"\nSession doc keys: {list(session_doc.keys())}")
    print(f"opening_to_teach in doc: {session_doc.get('opening_to_teach')}")
    print(f"opening_key in doc: {session_doc.get('opening_key')}")
    print(f"opening_teaching_active in doc: {session_doc.get('opening_teaching_active')}")

    # Step 2: Compute guidance like evaluate-pending does
    teaching_opening = session_doc.get("opening_to_teach") or session_doc.get("opening_key")
    _ota = session_doc.get("opening_teaching_active")
    print(f"\nteaching_opening: {teaching_opening}")
    print(f"opening_teaching_active: {_ota}")

    if teaching_opening and _ota:
        print("\n--- Guidance would be computed ---")
        from services.opening_mastery_tracker import (
            get_opening_mastery, get_move_guidance, get_trap_warning, get_phase_label
        )

        user_id = session_doc.get("user_id", "")
        mastery = await get_opening_mastery(db, user_id, teaching_opening)
        phase = mastery.get("phase", "introduction")
        move_history = session_doc.get("move_history", [])

        print(f"Phase: {phase}")
        print(f"Move history length: {len(move_history)}")

        # Simulate for each move
        for i in range(min(10, len(move_history) + 1)):
            next_idx = i + 1
            guidance = get_move_guidance(teaching_opening, next_idx, phase)
            coach_guidance = get_move_guidance(teaching_opening, i, phase)

            print(f"\n  After ply {i}:")
            if coach_guidance:
                print(f"    Coach move idea: {coach_guidance.get('idea', '')[:50]}")
            if guidance:
                print(f"    Next user idea: {guidance.get('idea', '')[:50]}")
                print(f"    Arrow: {guidance.get('arrow')}")
                print(f"    Expected: {guidance.get('move')}")
            else:
                print(f"    No guidance (past teaching line or free_play)")

        # Check trap warnings
        moves_played = [m.get("move", "") for m in move_history if isinstance(m, dict)]
        trap = get_trap_warning(teaching_opening, moves_played)
        print(f"\nTrap warning: {trap}")

    else:
        print("\n--- Guidance NOT computed ---")
        if not teaching_opening:
            print("  Reason: teaching_opening is None/empty")
        if not _ota:
            print("  Reason: opening_teaching_active is False/None")

    # Step 3: Check commentary override
    print("\n=== Commentary Override Check ===")
    opening_guidance_data = None
    if teaching_opening and _ota:
        from services.opening_mastery_tracker import get_move_guidance, get_phase_label
        mastery_phase = mastery.get("phase", "introduction") if 'mastery' in dir() else "introduction"
        move_history = session_doc.get("move_history", [])
        next_guidance = get_move_guidance(teaching_opening, len(move_history) + 1, mastery_phase)
        if next_guidance:
            opening_guidance_data = {
                "opening_key": teaching_opening,
                "move_idea": next_guidance.get("idea"),
                "arrow": next_guidance.get("arrow"),
            }

    if opening_guidance_data and opening_guidance_data.get("move_idea"):
        print(f"  Commentary would be OVERRIDDEN with: {opening_guidance_data['move_idea']}")
    else:
        print(f"  Commentary would use DEFAULT board reading")
        print(f"  opening_guidance_data: {opening_guidance_data}")


if __name__ == "__main__":
    asyncio.run(main())
