"""
Test Coach Insight API - /api/lab/{game_id}/coach-insight
Tests the 3-tab Coach Mode: Summary, Habits, Memory
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test game ID provided in requirements
TEST_GAME_ID = "01158bd9-8c73-4eb8-b60f-6d28adc502c8"


class TestCoachInsightAPI:
    """Test the Coach Insight endpoint for the Lab page"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup session with dev login authentication"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Authenticate via dev login (GET request)
        auth_response = self.session.get(f"{BASE_URL}/api/auth/dev-login")
        if auth_response.status_code != 200:
            pytest.skip("Dev login failed - skipping authenticated tests")
        
        yield
        
        self.session.close()
    
    def test_coach_insight_endpoint_returns_200(self):
        """Test that the coach-insight endpoint returns 200 for valid game"""
        response = self.session.get(f"{BASE_URL}/api/lab/{TEST_GAME_ID}/coach-insight")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print(f"✓ Coach insight endpoint returns 200")
    
    def test_coach_insight_returns_valid_json_structure(self):
        """Test that response has summary, habits, and memory sections"""
        response = self.session.get(f"{BASE_URL}/api/lab/{TEST_GAME_ID}/coach-insight")
        
        assert response.status_code == 200
        data = response.json()
        
        # Check top-level structure
        assert "summary" in data, "Response missing 'summary' section"
        assert "habits" in data, "Response missing 'habits' section"
        assert "memory" in data, "Response missing 'memory' section"
        
        print(f"✓ Response has all 3 sections: summary, habits, memory")
    
    def test_summary_tab_structure(self):
        """Test Summary tab has diagnosis, root_cause, context, coach_note, critical_move"""
        response = self.session.get(f"{BASE_URL}/api/lab/{TEST_GAME_ID}/coach-insight")
        
        assert response.status_code == 200
        data = response.json()
        summary = data.get("summary", {})
        
        # Required fields in summary
        assert "diagnosis" in summary, "Summary missing 'diagnosis'"
        assert "root_cause" in summary, "Summary missing 'root_cause'"
        assert "context" in summary, "Summary missing 'context'"
        assert "coach_note" in summary, "Summary missing 'coach_note'"
        
        # Context should be an array
        assert isinstance(summary.get("context"), list), "Context should be an array"
        
        # Diagnosis should be a valid type
        valid_diagnoses = [
            "THROW", "MATE_BLIND", "SLOW_BLEED", "OPENING_COLLAPSE", 
            "PIECE_GIVEAWAY", "TACTICAL_MISS", "TIME_COLLAPSE",
            "WON_CLEAN", "WON_OPPONENT_BLUNDER", "DRAW", "UNKNOWN"
        ]
        assert summary.get("diagnosis") in valid_diagnoses, f"Invalid diagnosis: {summary.get('diagnosis')}"
        
        print(f"✓ Summary tab structure valid - diagnosis: {summary.get('diagnosis')}")
        print(f"  Root cause: {summary.get('root_cause', '')[:80]}...")
        
        # Critical move is optional but if present should have required fields
        if "critical_move" in summary and summary["critical_move"]:
            cm = summary["critical_move"]
            assert "move_number" in cm, "Critical move missing 'move_number'"
            assert "san" in cm, "Critical move missing 'san'"
            assert "cp_loss" in cm, "Critical move missing 'cp_loss'"
            print(f"  Critical move: {cm.get('san')} at move {cm.get('move_number')}")
    
    def test_habits_tab_structure(self):
        """Test Habits tab returns habits array with name/passed/evidence/impact plus counts"""
        response = self.session.get(f"{BASE_URL}/api/lab/{TEST_GAME_ID}/coach-insight")
        
        assert response.status_code == 200
        data = response.json()
        habits = data.get("habits", {})
        
        # Required fields
        assert "habits" in habits, "Habits section missing 'habits' array"
        assert "passed_count" in habits, "Habits section missing 'passed_count'"
        assert "total_count" in habits, "Habits section missing 'total_count'"
        
        habits_list = habits.get("habits", [])
        assert isinstance(habits_list, list), "Habits should be an array"
        assert len(habits_list) > 0, "Habits array should not be empty"
        
        # Check each habit has required fields
        for i, habit in enumerate(habits_list):
            assert "name" in habit, f"Habit {i} missing 'name'"
            assert "passed" in habit, f"Habit {i} missing 'passed'"
            assert "evidence" in habit, f"Habit {i} missing 'evidence'"
            # impact can be None for passed habits
            assert "impact" in habit or habit.get("passed") == True, f"Habit {i} missing 'impact'"
        
        passed = habits.get("passed_count", 0)
        total = habits.get("total_count", 0)
        print(f"✓ Habits tab structure valid - {passed}/{total} passed")
        
        # Print habit details
        for habit in habits_list:
            status = "✓" if habit.get("passed") else "✗"
            print(f"  {status} {habit.get('name')}: {habit.get('evidence', '')[:50]}")
    
    def test_memory_tab_structure(self):
        """Test Memory tab returns identity and impact sections"""
        response = self.session.get(f"{BASE_URL}/api/lab/{TEST_GAME_ID}/coach-insight")
        
        assert response.status_code == 200
        data = response.json()
        memory = data.get("memory", {})
        
        # Required sections
        assert "identity" in memory, "Memory missing 'identity' section"
        assert "impact" in memory, "Memory missing 'impact' section"
        
        identity = memory.get("identity", {})
        impact = memory.get("impact", {})
        
        # Identity fields (Chess DNA)
        assert "before_line" in identity, "Identity missing 'before_line'"
        assert "after_line" in identity, "Identity missing 'after_line'"
        assert "archetype" in identity, "Identity missing 'archetype'"
        assert "this_game_confirms" in identity, "Identity missing 'this_game_confirms'"
        
        print(f"✓ Memory identity structure valid")
        print(f"  Archetype: {identity.get('archetype')}")
        print(f"  Before: {identity.get('before_line', '')[:60]}...")
        print(f"  After: {identity.get('after_line', '')[:60]}...")
        
        # Impact fields (If You Fixed This)
        assert "stat_line" in impact, "Impact missing 'stat_line'"
        assert "fix_line" in impact, "Impact missing 'fix_line'"
        assert "diff_line" in impact, "Impact missing 'diff_line'"
        assert "severity" in impact, "Impact missing 'severity'"
        assert "estimated_rating_gain" in impact, "Impact missing 'estimated_rating_gain'"
        
        print(f"✓ Memory impact structure valid")
        print(f"  Severity: {impact.get('severity')}")
        print(f"  Estimated rating gain: {impact.get('estimated_rating_gain')}")
        
        # If user has rating, check projection
        if impact.get("current_rating") and impact.get("current_rating") > 0:
            assert "projected_rating" in impact, "Impact missing 'projected_rating' when user has rating"
            print(f"  Rating projection: {impact.get('current_rating')} -> ~{impact.get('projected_rating')}")
    
    def test_memory_rating_projection(self):
        """Test that Memory tab shows rating projection when user has rating"""
        response = self.session.get(f"{BASE_URL}/api/lab/{TEST_GAME_ID}/coach-insight")
        
        assert response.status_code == 200
        data = response.json()
        memory = data.get("memory", {})
        impact = memory.get("impact", {})
        
        current_rating = impact.get("current_rating", 0)
        estimated_gain = impact.get("estimated_rating_gain", 0)
        projected_rating = impact.get("projected_rating")
        
        # If there's a current rating and estimated gain, projected should be calculated
        if current_rating > 0 and estimated_gain > 0:
            assert projected_rating is not None, "Projected rating should be set when user has rating"
            expected_projection = current_rating + estimated_gain
            assert projected_rating == expected_projection, f"Projected rating mismatch: {projected_rating} != {expected_projection}"
            print(f"✓ Rating projection correct: {current_rating} + {estimated_gain} = {projected_rating}")
        else:
            print(f"✓ No rating projection (current_rating={current_rating}, gain={estimated_gain})")
    
    def test_invalid_game_id_returns_404(self):
        """Test that invalid game ID returns 404"""
        response = self.session.get(f"{BASE_URL}/api/lab/invalid-game-id-12345/coach-insight")
        
        assert response.status_code == 404, f"Expected 404 for invalid game, got {response.status_code}"
        print(f"✓ Invalid game ID returns 404")
    
    def test_unauthenticated_request_behavior(self):
        """Test unauthenticated request behavior (may return 200 in DEV_MODE)"""
        # Create new session without auth
        unauth_session = requests.Session()
        response = unauth_session.get(f"{BASE_URL}/api/lab/{TEST_GAME_ID}/coach-insight")
        
        # In DEV_MODE, unauthenticated requests may succeed with dev user
        # In production, should return 401
        assert response.status_code in [200, 401], f"Expected 200 or 401, got {response.status_code}"
        
        if response.status_code == 200:
            print(f"✓ Unauthenticated request returns 200 (DEV_MODE enabled)")
        else:
            print(f"✓ Unauthenticated request returns 401 (production mode)")
        
        unauth_session.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
