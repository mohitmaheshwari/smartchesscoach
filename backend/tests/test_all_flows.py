"""
E2E Tests: Full Application Coverage
======================================

Tests ALL critical flows:
1. Coach Play (already exists in test_coach_play_flow.py)
2. Lab / Game Review
3. Training / Drills
4. Home Dashboard
5. Game Import Pipeline
6. Player Brain / Memory

Run all: cd /app/backend && python tests/test_all_flows.py
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import httpx

API_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001") + "/api"

PASSED = 0
FAILED = 0
ERRORS = []


def result(name, success, detail=""):
    global PASSED, FAILED, ERRORS
    if success:
        PASSED += 1
        print(f"  ✅ {name}")
    else:
        FAILED += 1
        ERRORS.append(f"{name}: {detail}")
        print(f"  ❌ {name} — {detail}")


async def test_home_dashboard():
    """Test: Home dashboard loads with data"""
    print("\n=== HOME DASHBOARD ===")
    async with httpx.AsyncClient(timeout=15.0) as client:
        # Dashboard V2
        res = await client.get(f"{API_URL}/home/dashboard-v2")
        result("Dashboard V2 loads", res.status_code == 200, f"Status: {res.status_code}")

        if res.status_code == 200:
            data = res.json()
            result("Has dashboard data", len(data) > 0, f"Keys: {list(data.keys())[:5]}")

        # Auth/me
        res = await client.get(f"{API_URL}/auth/me")
        result("Auth/me works", res.status_code == 200, f"Status: {res.status_code}")


async def test_lab_game_review():
    """Test: Lab endpoints for game review"""
    print("\n=== LAB / GAME REVIEW ===")
    async with httpx.AsyncClient(timeout=15.0) as client:
        # Get a game to review
        res = await client.get(f"{API_URL}/games?limit=1")
        if res.status_code != 200:
            result("Games list", False, f"Status: {res.status_code}")
            return

        data = res.json()
        games = data if isinstance(data, list) else data.get("games", [])
        result("Games list loads", True)

        if not games:
            print("  ⚠ No games available — skipping lab tests")
            return

        game_id = games[0].get("game_id")
        result("Has game_id", bool(game_id), f"game_id: {game_id}")

        # Lab page data
        res = await client.get(f"{API_URL}/lab/{game_id}")
        if res.status_code == 200:
            result("Lab page loads", True)
        elif res.status_code == 404:
            result("Lab page", False, "Analysis not found — game not analyzed yet")
        else:
            result("Lab page", False, f"Status: {res.status_code}")

        # Coach insight (habits tab)
        res = await client.get(f"{API_URL}/lab/{game_id}/coach-insight")
        result("Coach insight", res.status_code == 200, f"Status: {res.status_code}")

        # Coach action (diagnose → drill → track)
        res = await client.get(f"{API_URL}/lab/{game_id}/coach-action")
        result("Coach action", res.status_code == 200, f"Status: {res.status_code}")

        # Coach review
        res = await client.get(f"{API_URL}/lab/{game_id}/coach-review")
        result("Coach review", res.status_code == 200, f"Status: {res.status_code}")


async def test_training():
    """Test: Training / drill endpoints"""
    print("\n=== TRAINING ===")
    async with httpx.AsyncClient(timeout=15.0) as client:
        # Community feed
        res = await client.get(f"{API_URL}/training/community-feed?limit=3")
        result("Training feed loads", res.status_code == 200, f"Status: {res.status_code}")

        if res.status_code == 200:
            data = res.json()
            positions = data.get("positions", data.get("feed", data if isinstance(data, list) else []))
            result("Has positions", len(positions) > 0, f"Count: {len(positions)}")

            if positions:
                pos = positions[0]
                result("Position has FEN", bool(pos.get("fen")), f"FEN: {pos.get('fen', '')[:30]}")
                result("Position has best_move", bool(pos.get("best_move_san") or pos.get("best_move_uci")),
                       f"Move: {pos.get('best_move_san', pos.get('best_move_uci', ''))}")

        # Training with pattern filter
        res = await client.get(f"{API_URL}/training/community-feed?limit=3&pattern=tactical_miss")
        result("Training filter works", res.status_code == 200, f"Status: {res.status_code}")

        # Training progress
        res = await client.get(f"{API_URL}/training/progress")
        result("Training progress", res.status_code == 200, f"Status: {res.status_code}")


async def test_player_brain():
    """Test: Player brain / memory system"""
    print("\n=== PLAYER BRAIN ===")
    async with httpx.AsyncClient(timeout=15.0) as client:
        res = await client.get(f"{API_URL}/player-brain")
        result("Player brain loads", res.status_code == 200, f"Status: {res.status_code}")

        if res.status_code == 200:
            data = res.json()
            result("Has rating", "rating" in data, f"Rating: {data.get('rating')}")
            result("Has focus_message", bool(data.get("focus_message")), f"Focus: {data.get('focus_message', '')[:50]}")
            result("Has drill_focus", "drill_focus" in data, f"Drill: {data.get('drill_focus')}")


async def test_opening_system():
    """Test: Opening curriculum + suggestions + assessment"""
    print("\n=== OPENING SYSTEM ===")
    async with httpx.AsyncClient(timeout=15.0) as client:
        # Available curriculums
        res = await client.get(f"{API_URL}/coach/play/curriculum/openings")
        result("Curriculum list loads", res.status_code == 200, f"Status: {res.status_code}")

        if res.status_code == 200:
            data = res.json()
            openings = data.get("openings", [])
            result("Has openings", len(openings) > 0, f"Count: {len(openings)}")

        # Opening suggestions
        res = await client.get(f"{API_URL}/coach/play/opening-suggestions")
        result("Opening suggestions", res.status_code == 200, f"Status: {res.status_code}")

        # Opening assessment
        res = await client.get(f"{API_URL}/coach/play/opening-assessment?opening=london_system")
        result("London assessment", res.status_code == 200, f"Status: {res.status_code}")

        res = await client.get(f"{API_URL}/coach/play/opening-assessment?opening=italian_game")
        result("Italian assessment", res.status_code == 200, f"Status: {res.status_code}")

        # Pregame intro
        res = await client.get(f"{API_URL}/coach/play/pregame-intro?opening=london_system")
        result("Pregame intro", res.status_code == 200, f"Status: {res.status_code}")

        if res.status_code == 200:
            data = res.json()
            result("Has intro message", bool(data.get("intro")), f"Intro: {data.get('intro', '')[:50]}")
            result("Has brain data", bool(data.get("brain")), f"Brain: {bool(data.get('brain'))}")


async def test_coach_play_core():
    """Test: Core coach play flow (abbreviated)"""
    print("\n=== COACH PLAY (core) ===")
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Start
        res = await client.post(f"{API_URL}/coach/play/start",
            json={"user_color": "white", "opening_key": "london_system"})
        data = res.json()
        result("Start game", data.get("success") == True, f"Success: {data.get('success')}")

        session_id = data.get("session_id")
        if not session_id:
            return

        session = data.get("session", {})
        result("Curriculum active", session.get("curriculum_active") == True,
               f"Active: {session.get('curriculum_active')}")

        # Move d4
        res = await client.post(f"{API_URL}/coach/play/move",
            json={"session_id": session_id, "move": "d4"})
        data = res.json()
        result("Move d4", data.get("success") == True, f"Success: {data.get('success')}")
        result("Has feedback", bool(data.get("curriculum_feedback")),
               f"FB: {data.get('curriculum_feedback', '')[:40]}")

        # Wait for coach
        await asyncio.sleep(3)

        # State
        res = await client.get(f"{API_URL}/coach/play/state/{session_id}")
        data = res.json()
        s = data.get("session", {})
        result("Coach moved", bool(s.get("last_coach_move")),
               f"Move: {s.get('last_coach_move', {}).get('san', '?')}")

        # Guidance
        res = await client.post(f"{API_URL}/coach/play/opening-guide",
            json={"session_id": session_id, "opening_key": "london_system"})
        data = res.json()
        result("Guidance has hint", bool(data.get("hint")), f"Hint: {data.get('hint', '')[:40]}")
        result("Has opponent commentary", bool(data.get("opponent_commentary")),
               f"Opp: {data.get('opponent_commentary', '')[:40]}")

        # Position reader
        res = await client.post(f"{API_URL}/coach/play/read-position",
            json={"session_id": session_id})
        data = res.json()
        result("Position reader", "eval_text" in data, f"Eval: {data.get('eval_text', '?')}")

        # End
        res = await client.post(f"{API_URL}/coach/play/end",
            json={"session_id": session_id})
        result("End game", res.json().get("success") == True)


async def test_import_pipeline():
    """Test: Game sync/import endpoints"""
    print("\n=== IMPORT PIPELINE ===")
    async with httpx.AsyncClient(timeout=15.0) as client:
        # Sync status
        res = await client.get(f"{API_URL}/sync-status")
        result("Sync status", res.status_code == 200, f"Status: {res.status_code}")

        # Data status
        res = await client.get(f"{API_URL}/data/status")
        result("Data status", res.status_code == 200, f"Status: {res.status_code}")


async def main():
    print("=" * 55)
    print("  CHESSGURU FULL E2E TEST SUITE")
    print("=" * 55)

    await test_home_dashboard()
    await test_lab_game_review()
    await test_training()
    await test_player_brain()
    await test_opening_system()
    await test_coach_play_core()
    await test_import_pipeline()

    print("\n" + "=" * 55)
    print(f"  RESULTS: {PASSED} passed, {FAILED} failed")
    print("=" * 55)

    if ERRORS:
        print("\nFailed tests:")
        for e in ERRORS:
            print(f"  ❌ {e}")

    if FAILED > 0:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
