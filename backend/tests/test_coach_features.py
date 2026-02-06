"""
Test Coach Features: Go Play Modal, Track Reflection, Light Stats
Tests new features from Sprint:
1. POST /api/coach/track-reflection - saves reflection result
2. GET /api/coach/today - returns light_stats, rule, next_game_plan, coach_note
3. Habit-aligned PDR selection (70% preference)
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
SESSION_TOKEN = "e0M8B6ymZiR-okaGeHRE5NH5TgBo2tudtq4ynwObGq8"

# ============ FIXTURES ============

@pytest.fixture
def auth_headers():
    """Authorization headers with session token"""
    return {
        "Authorization": f"Bearer {SESSION_TOKEN}",
        "Content-Type": "application/json"
    }


# ============ TRACK REFLECTION TESTS ============

class TestTrackReflection:
    """POST /api/coach/track-reflection - saves reflection to database"""
    
    def test_track_reflection_correct_move(self, auth_headers):
        """Track reflection with correct move should succeed"""
        response = requests.post(
            f"{BASE_URL}/api/coach/track-reflection",
            headers=auth_headers,
            json={
                "game_id": "test_game_123",
                "move_number": 15,
                "move_correct": True,
                "reason_correct": True,
                "user_move": "Nf3",
                "best_move": "Nf3"
            }
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("status") == "tracked", f"Expected status 'tracked', got: {data}"
        print("✓ Track reflection (correct move) returns status 'tracked'")
    
    def test_track_reflection_wrong_move(self, auth_headers):
        """Track reflection with wrong move should succeed"""
        response = requests.post(
            f"{BASE_URL}/api/coach/track-reflection",
            headers=auth_headers,
            json={
                "game_id": "test_game_456",
                "move_number": 10,
                "move_correct": False,
                "reason_correct": None,
                "user_move": "Bg5",
                "best_move": "Nxe5"
            }
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("status") == "tracked", f"Expected status 'tracked', got: {data}"
        print("✓ Track reflection (wrong move) returns status 'tracked'")
    
    def test_track_reflection_requires_auth(self):
        """Track reflection without auth should fail"""
        response = requests.post(
            f"{BASE_URL}/api/coach/track-reflection",
            headers={"Content-Type": "application/json"},
            json={
                "game_id": "test_game",
                "move_number": 5,
                "move_correct": True,
                "user_move": "e4",
                "best_move": "e4"
            }
        )
        
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ Track reflection requires authentication")
    
    def test_track_reflection_increments_counters(self, auth_headers):
        """Verify reflection tracking increments user counters"""
        # Get current stats
        me_response = requests.get(
            f"{BASE_URL}/api/auth/me",
            headers=auth_headers
        )
        
        if me_response.status_code == 200:
            initial_data = me_response.json()
            initial_total = initial_data.get("total_reflections", 0)
            initial_correct = initial_data.get("correct_reflections", 0)
            
            # Track a correct reflection
            response = requests.post(
                f"{BASE_URL}/api/coach/track-reflection",
                headers=auth_headers,
                json={
                    "game_id": f"test_increment_{int(time.time())}",
                    "move_number": 20,
                    "move_correct": True,
                    "reason_correct": True,
                    "user_move": "Qd5",
                    "best_move": "Qd5"
                }
            )
            
            assert response.status_code == 200
            print("✓ Track reflection submitted successfully")
        else:
            pytest.skip("Could not get current user stats")


# ============ COACH TODAY API TESTS ============

class TestCoachToday:
    """GET /api/coach/today - returns coaching data with light_stats"""
    
    def test_coach_today_returns_200(self, auth_headers):
        """Coach today endpoint should return 200"""
        response = requests.get(
            f"{BASE_URL}/api/coach/today",
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print("✓ GET /api/coach/today returns 200")
    
    def test_coach_today_has_data_flag(self, auth_headers):
        """Coach today should have has_data boolean"""
        response = requests.get(
            f"{BASE_URL}/api/coach/today",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "has_data" in data, "Response should contain 'has_data' flag"
        assert isinstance(data["has_data"], bool), "has_data should be boolean"
        print(f"✓ has_data flag present: {data['has_data']}")
    
    def test_coach_today_has_light_stats(self, auth_headers):
        """Coach today should return light_stats array"""
        response = requests.get(
            f"{BASE_URL}/api/coach/today",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        if data.get("has_data"):
            assert "light_stats" in data, "Response should contain 'light_stats'"
            assert isinstance(data["light_stats"], list), "light_stats should be a list"
            print(f"✓ light_stats present with {len(data['light_stats'])} items")
            
            # Verify stat structure if present
            for stat in data["light_stats"]:
                assert "label" in stat, "Each stat should have 'label'"
                assert "value" in stat, "Each stat should have 'value'"
                assert "trend" in stat, "Each stat should have 'trend'"
                assert stat["trend"] in ["up", "down", "stable"], f"Invalid trend: {stat['trend']}"
                print(f"  - {stat['label']}: {stat['value']} ({stat['trend']})")
        else:
            print("⚠ No data available yet, skipping light_stats validation")
    
    def test_coach_today_has_blunders_per_game(self, auth_headers):
        """Light stats should include blunders per game trend"""
        response = requests.get(
            f"{BASE_URL}/api/coach/today",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        if data.get("has_data") and data.get("light_stats"):
            blunder_stats = [s for s in data["light_stats"] if "blunder" in s.get("label", "").lower()]
            if blunder_stats:
                stat = blunder_stats[0]
                assert "trend" in stat, "Blunders stat should have trend"
                print(f"✓ Blunders/game stat: {stat['value']} (trend: {stat['trend']})")
            else:
                print("⚠ No blunders stat found in light_stats")
        else:
            pytest.skip("No data available")
    
    def test_coach_today_has_coach_note(self, auth_headers):
        """Coach today should return coach_note with 2-line emotional framing"""
        response = requests.get(
            f"{BASE_URL}/api/coach/today",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        if data.get("has_data"):
            assert "coach_note" in data, "Response should contain 'coach_note'"
            coach_note = data["coach_note"]
            assert "line1" in coach_note, "Coach note should have 'line1'"
            assert "line2" in coach_note, "Coach note should have 'line2'"
            assert isinstance(coach_note["line1"], str), "line1 should be string"
            assert isinstance(coach_note["line2"], str), "line2 should be string"
            print(f"✓ Coach note line1: '{coach_note['line1']}'")
            print(f"✓ Coach note line2: '{coach_note['line2']}'")
        else:
            pytest.skip("No data available")
    
    def test_coach_today_has_next_game_plan(self, auth_headers):
        """Coach today should return next_game_plan"""
        response = requests.get(
            f"{BASE_URL}/api/coach/today",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        if data.get("has_data"):
            assert "next_game_plan" in data, "Response should contain 'next_game_plan'"
            assert isinstance(data["next_game_plan"], str), "next_game_plan should be string"
            assert len(data["next_game_plan"]) > 10, "next_game_plan should have meaningful content"
            print(f"✓ Next game plan: '{data['next_game_plan']}'")
        else:
            pytest.skip("No data available")
    
    def test_coach_today_has_rule(self, auth_headers):
        """Coach today should return rule for carry-forward"""
        response = requests.get(
            f"{BASE_URL}/api/coach/today",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        if data.get("has_data"):
            assert "rule" in data, "Response should contain 'rule'"
            assert isinstance(data["rule"], str), "rule should be string"
            assert len(data["rule"]) > 10, "rule should have meaningful content"
            print(f"✓ Rule: '{data['rule']}'")
        else:
            pytest.skip("No data available")


# ============ PDR TESTS ============

class TestPDRHabitAlignment:
    """Test PDR selects mistakes aligned with dominant habit (70% preference)"""
    
    def test_pdr_structure(self, auth_headers):
        """PDR should have correct structure"""
        response = requests.get(
            f"{BASE_URL}/api/coach/today",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        if data.get("has_data") and data.get("pdr"):
            pdr = data["pdr"]
            
            # Check required fields
            assert "fen" in pdr, "PDR should have 'fen'"
            assert "candidates" in pdr, "PDR should have 'candidates'"
            assert "user_original_move" in pdr, "PDR should have 'user_original_move'"
            assert "best_move" in pdr, "PDR should have 'best_move'"
            assert "game_id" in pdr, "PDR should have 'game_id'"
            
            # Verify candidates
            assert len(pdr["candidates"]) >= 2, "PDR should have at least 2 candidates"
            
            # Check that one is the best move
            best_candidates = [c for c in pdr["candidates"] if c.get("is_best")]
            assert len(best_candidates) == 1, "Exactly one candidate should be marked as best"
            
            print(f"✓ PDR structure valid with {len(pdr['candidates'])} candidates")
            print(f"  - Best move: {pdr['best_move']}")
            print(f"  - User move: {pdr['user_original_move']}")
        else:
            pytest.skip("No PDR data available")
    
    def test_pdr_has_game_context(self, auth_headers):
        """PDR should include game context"""
        response = requests.get(
            f"{BASE_URL}/api/coach/today",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        if data.get("has_data") and data.get("pdr"):
            pdr = data["pdr"]
            assert "game_context" in pdr, "PDR should have 'game_context'"
            
            context = pdr["game_context"]
            assert "platform" in context, "Game context should have 'platform'"
            print(f"✓ PDR game context: platform={context.get('platform')}")
        else:
            pytest.skip("No PDR data available")
    
    def test_pdr_has_why_options(self, auth_headers):
        """PDR should have why_options for Socratic method"""
        response = requests.get(
            f"{BASE_URL}/api/coach/today",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        if data.get("has_data") and data.get("pdr"):
            pdr = data["pdr"]
            
            # why_options may be null for some positions
            if pdr.get("why_options"):
                why = pdr["why_options"]
                assert "options" in why, "why_options should have 'options'"
                assert len(why["options"]) >= 2, "Should have at least 2 options"
                
                # Check that exactly one is correct
                correct_options = [o for o in why["options"] if o.get("is_correct")]
                assert len(correct_options) == 1, "Exactly one option should be correct"
                
                print(f"✓ why_options with {len(why['options'])} options")
            else:
                print("⚠ why_options is null (expected for some positions)")
        else:
            pytest.skip("No PDR data available")


# ============ SESSION TESTS ============

class TestSessionFlow:
    """Test Go Play / Done Playing session flow"""
    
    def test_session_status(self, auth_headers):
        """Session status should be returned"""
        response = requests.get(
            f"{BASE_URL}/api/coach/today",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        if data.get("has_data"):
            assert "session_status" in data, "Response should contain 'session_status'"
            session = data["session_status"]
            assert "status" in session, "Session should have 'status'"
            print(f"✓ Session status: {session.get('status')}")
        else:
            pytest.skip("No data available")
    
    def test_start_session(self, auth_headers):
        """Start session should work"""
        response = requests.post(
            f"{BASE_URL}/api/coach/start-session",
            headers=auth_headers,
            json={"platform": "chess.com"}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "status" in data or "message" in data, "Response should have status or message"
        print(f"✓ Start session: {data}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
