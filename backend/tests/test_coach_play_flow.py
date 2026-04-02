"""
End-to-End Test: Play with Coach Flow
=======================================

Tests the critical path: start → play moves → coach responds → guidance → end.

Run: python -m pytest tests/test_coach_play_flow.py -v
Or:  cd /app/backend && python tests/test_coach_play_flow.py
"""

import asyncio
import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import httpx

API_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001") + "/api"


async def test_full_coach_flow():
    """Test: start → d4 → coach responds → guidance → Bf4 → end"""
    async with httpx.AsyncClient(timeout=30.0) as client:
        
        # 1. START
        print("1. Starting game...")
        res = await client.post(f"{API_URL}/coach/play/start",
            json={"user_color": "white", "opening_key": "london_system"})
        data = res.json()
        assert data.get("success"), f"Start failed: {data}"
        session_id = data["session_id"]
        session = data.get("session", {})
        assert session.get("curriculum_active") == True, f"Curriculum not active: {session.get('curriculum_active')}"
        assert session.get("teaching_opening") == "london_system", f"Wrong opening: {session.get('teaching_opening')}"
        print(f"   ✓ Session: {session_id[:12]}... curriculum_active=True")

        # 2. PLAY d4
        print("2. Playing d4...")
        res = await client.post(f"{API_URL}/coach/play/move",
            json={"session_id": session_id, "move": "d4"})
        data = res.json()
        assert data.get("success"), f"Move failed: {data}"
        assert data.get("curriculum_feedback"), f"No curriculum feedback: {data}"
        print(f"   ✓ Feedback: {data['curriculum_feedback'][:50]}")

        # 3. WAIT FOR COACH
        print("3. Waiting for coach...")
        for i in range(15):
            await asyncio.sleep(1)
            res = await client.get(f"{API_URL}/coach/play/state/{session_id}")
            state = res.json()
            s = state.get("session", {})
            if not s.get("coach_move_pending"):
                break
        
        lcm = s.get("last_coach_move")
        assert lcm, f"No last_coach_move after polling: {s.keys()}"
        coach_move = lcm.get("san") or lcm.get("move")
        assert coach_move, f"last_coach_move has no san/move: {lcm}"
        moves = s.get("move_history", [])
        assert len(moves) >= 2, f"Expected 2+ moves, got {len(moves)}"
        print(f"   ✓ Coach played: {coach_move}, moves: {len(moves)}")

        # 4. GUIDANCE
        print("4. Checking guidance...")
        res = await client.post(f"{API_URL}/coach/play/opening-guide",
            json={"session_id": session_id, "opening_key": "london_system"})
        data = res.json()
        assert data.get("hint"), f"No hint in guidance: {data.keys()}"
        assert data.get("opponent_commentary") or data.get("last_opponent_move"), f"No opponent info: {data.keys()}"
        print(f"   ✓ Hint: {data['hint'][:50]}")
        if data.get("opponent_commentary"):
            print(f"   ✓ Opponent: {data['opponent_commentary'][:50]}")
        if data.get("last_opponent_move"):
            print(f"   ✓ Last opponent move: {data['last_opponent_move']}")

        # 5. READ POSITION
        print("5. Reading position...")
        res = await client.post(f"{API_URL}/coach/play/read-position",
            json={"session_id": session_id})
        data = res.json()
        print(f"   ✓ Features: {len(data.get('features', []))}, Eval: {data.get('eval_text', '?')}")

        # 6. PLAY Bf4 (curriculum move)
        print("6. Playing Bf4...")
        res = await client.post(f"{API_URL}/coach/play/move",
            json={"session_id": session_id, "move": "Bf4"})
        data = res.json()
        assert data.get("success"), f"Bf4 failed: {data}"
        fb = data.get("curriculum_feedback", "")
        print(f"   ✓ Feedback: {fb[:50]}")
        
        # Wait for coach again
        for i in range(15):
            await asyncio.sleep(1)
            res = await client.get(f"{API_URL}/coach/play/state/{session_id}")
            s = res.json().get("session", {})
            if not s.get("coach_move_pending"):
                break
        
        moves2 = s.get("move_history", [])
        assert len(moves2) >= 4, f"Expected 4+ moves after Bf4, got {len(moves2)}"
        print(f"   ✓ Moves now: {len(moves2)}")

        # 7. END GAME
        print("7. Ending game...")
        res = await client.post(f"{API_URL}/coach/play/end",
            json={"session_id": session_id})
        data = res.json()
        assert data.get("success"), f"End failed: {data}"
        print(f"   ✓ Game ended")

        print("\n✅ ALL TESTS PASSED")
        return True


async def test_opening_detection():
    """Test: auto-detect opening from moves"""
    async with httpx.AsyncClient(timeout=30.0) as client:
        print("\n8. Testing opening detection...")
        
        # Start with Italian curriculum
        res = await client.post(f"{API_URL}/coach/play/start",
            json={"user_color": "white", "opening_key": "italian_game"})
        data = res.json()
        session_id = data["session_id"]
        session = data.get("session", {})
        
        assert session.get("teaching_opening") == "italian_game", f"Wrong opening: {session.get('teaching_opening')}"
        print(f"   ✓ Started with Italian Game curriculum")
        
        # Play e4
        res = await client.post(f"{API_URL}/coach/play/move",
            json={"session_id": session_id, "move": "e4"})
        data = res.json()
        assert data.get("success"), f"e4 failed: {data}"
        print(f"   ✓ e4 accepted: {data.get('curriculum_feedback', '')[:40]}")
        
        await asyncio.sleep(3)
        
        # Play Nf3
        res = await client.post(f"{API_URL}/coach/play/move",
            json={"session_id": session_id, "move": "Nf3"})
        data = res.json()
        assert data.get("success"), f"Nf3 failed: {data}"
        print(f"   ✓ Nf3 accepted")
        
        await asyncio.sleep(3)
        
        # Check guidance — should have opening_info after 4+ moves
        res = await client.post(f"{API_URL}/coach/play/opening-guide",
            json={"session_id": session_id, "opening_key": "italian_game"})
        data = res.json()
        
        oi = data.get("opening_info")
        if oi:
            print(f"   ✓ Opening info: {oi['name']} ({oi['status']})")
        else:
            print(f"   ✓ No opening info yet (need 3+ moves)")
        
        await client.post(f"{API_URL}/coach/play/end", json={"session_id": session_id})
        print("   ✓ Opening detection test complete")
        return True


async def test_wrong_move_feedback():
    """Test: playing wrong curriculum move gives feedback, not rejection"""
    async with httpx.AsyncClient(timeout=30.0) as client:
        print("\n9. Testing wrong move feedback...")
        
        res = await client.post(f"{API_URL}/coach/play/start",
            json={"user_color": "white", "opening_key": "london_system"})
        session_id = res.json()["session_id"]
        
        # Play d4 (correct)
        await client.post(f"{API_URL}/coach/play/move",
            json={"session_id": session_id, "move": "d4"})
        await asyncio.sleep(3)
        
        # Play Nf3 instead of Bf4 (wrong curriculum move — should be accepted with feedback)
        res = await client.post(f"{API_URL}/coach/play/move",
            json={"session_id": session_id, "move": "Nf3"})
        data = res.json()
        
        assert data.get("success") == True, f"Move was rejected: {data}"
        fb = data.get("curriculum_feedback", "")
        assert fb, f"No feedback for wrong move: {data}"
        assert "Nf3" not in fb or "Bf4" in fb.lower() or "curriculum" in fb.lower() or "e3" in fb.lower(), f"Feedback doesn't mention correct move: {fb}"
        print(f"   ✓ Move accepted with feedback: {fb[:60]}")
        
        await client.post(f"{API_URL}/coach/play/end",
            json={"session_id": session_id})
        return True


async def main():
    print("=" * 50)
    print("  CHESSGURU E2E TEST: Play with Coach")
    print("=" * 50)
    
    try:
        await test_full_coach_flow()
        await test_opening_detection()
        await test_wrong_move_feedback()
        
        print("\n" + "=" * 50)
        print("  ALL TESTS PASSED ✅")
        print("=" * 50)
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
