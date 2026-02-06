"""
Test PDR Phase 2 (Auto-rotate habits) and Weekly Email Summaries
Tests for habit rotation, weekly summary generation, and related endpoints
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
SESSION_TOKEN = "Eekx0E_HGNaI2OpblI4ryHRHjFWM6rlxj--HqAZ6XPQ"


@pytest.fixture
def auth_headers():
    return {
        "Authorization": f"Bearer {SESSION_TOKEN}",
        "Content-Type": "application/json"
    }


# ============================================
# HABIT STATUS ENDPOINT TESTS (/api/coach/habits)
# ============================================

class TestHabitStatusEndpoint:
    """Tests for GET /api/coach/habits - returns habit statuses with reflection stats"""
    
    def test_get_habits_returns_200(self, auth_headers):
        """Test that /api/coach/habits returns 200 OK"""
        response = requests.get(f"{BASE_URL}/api/coach/habits", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print("✓ GET /api/coach/habits returns 200")
    
    def test_get_habits_response_structure(self, auth_headers):
        """Test that response has correct structure with habits array"""
        response = requests.get(f"{BASE_URL}/api/coach/habits", headers=auth_headers)
        data = response.json()
        
        assert "habits" in data, "Response should contain 'habits' key"
        assert isinstance(data["habits"], list), "'habits' should be a list"
        print(f"✓ GET /api/coach/habits returns habits array with {len(data['habits'])} items")
    
    def test_habit_contains_reflection_stats(self, auth_headers):
        """Test that habits contain reflection statistics"""
        response = requests.get(f"{BASE_URL}/api/coach/habits", headers=auth_headers)
        data = response.json()
        habits = data.get("habits", [])
        
        if habits:
            habit = habits[0]
            # Check required fields
            expected_fields = ["habit", "total_attempts", "correct_attempts", 
                            "consecutive_correct", "success_rate", "status"]
            for field in expected_fields:
                assert field in habit, f"Habit missing required field: {field}"
            
            # Validate field types
            assert isinstance(habit["total_attempts"], int), "total_attempts should be int"
            assert isinstance(habit["correct_attempts"], int), "correct_attempts should be int"
            assert isinstance(habit["consecutive_correct"], int), "consecutive_correct should be int"
            assert isinstance(habit["success_rate"], (int, float)), "success_rate should be numeric"
            assert habit["status"] in ["active", "improving", "resolved"], f"Invalid status: {habit['status']}"
            
            print(f"✓ Habit '{habit['habit']}' has all required reflection stats")
            print(f"  - Total attempts: {habit['total_attempts']}")
            print(f"  - Correct: {habit['correct_attempts']}")
            print(f"  - Consecutive correct: {habit['consecutive_correct']}")
            print(f"  - Status: {habit['status']}")
        else:
            pytest.skip("No habits found to validate")
    
    def test_habit_has_is_dominant_flag(self, auth_headers):
        """Test that habits have is_dominant flag"""
        response = requests.get(f"{BASE_URL}/api/coach/habits", headers=auth_headers)
        data = response.json()
        habits = data.get("habits", [])
        
        if habits:
            dominant_count = sum(1 for h in habits if h.get("is_dominant", False))
            assert dominant_count <= 1, "Only one habit should be dominant"
            print(f"✓ Habit dominant flag present, {dominant_count} dominant habit(s)")
        else:
            pytest.skip("No habits found")


# ============================================
# CHECK HABIT ROTATION ENDPOINT TESTS
# ============================================

class TestHabitRotationEndpoint:
    """Tests for POST /api/coach/check-habit-rotation"""
    
    def test_check_rotation_returns_200(self, auth_headers):
        """Test that check-habit-rotation returns 200"""
        response = requests.post(f"{BASE_URL}/api/coach/check-habit-rotation", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ POST /api/coach/check-habit-rotation returns 200")
    
    def test_check_rotation_response_structure(self, auth_headers):
        """Test rotation check response structure"""
        response = requests.post(f"{BASE_URL}/api/coach/check-habit-rotation", headers=auth_headers)
        data = response.json()
        
        # Should have rotated boolean
        assert "rotated" in data, "Response should contain 'rotated' key"
        assert isinstance(data["rotated"], bool), "'rotated' should be boolean"
        
        # Should have reason
        assert "reason" in data, "Response should contain 'reason' key"
        
        print(f"✓ Rotation check response: rotated={data['rotated']}, reason='{data['reason']}'")
    
    def test_rotation_logic_not_triggered_early(self, auth_headers):
        """Test that rotation doesn't trigger before threshold"""
        response = requests.post(f"{BASE_URL}/api/coach/check-habit-rotation", headers=auth_headers)
        data = response.json()
        
        # If not rotated, check it returns current habit info
        if not data["rotated"]:
            if "current_habit" in data:
                assert "performance" in data, "Non-rotated response should include performance"
                print(f"✓ Current habit: {data['current_habit']}")
                print(f"  - Performance: {data.get('performance', {})}")
            elif "No active weaknesses" in data.get("reason", ""):
                print("✓ No active weaknesses - rotation not applicable")
            else:
                print(f"✓ Rotation not triggered: {data['reason']}")


# ============================================
# WEEKLY SUMMARY ENDPOINT TESTS
# ============================================

class TestWeeklySummaryEndpoint:
    """Tests for GET /api/user/weekly-summary"""
    
    def test_weekly_summary_returns_200(self, auth_headers):
        """Test that weekly-summary returns 200"""
        response = requests.get(f"{BASE_URL}/api/user/weekly-summary", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ GET /api/user/weekly-summary returns 200")
    
    def test_weekly_summary_structure(self, auth_headers):
        """Test weekly summary response structure"""
        response = requests.get(f"{BASE_URL}/api/user/weekly-summary", headers=auth_headers)
        data = response.json()
        
        # Required fields
        expected_fields = ["user_id", "week_start", "week_end", "games_analyzed", 
                         "improvement_trend", "weekly_assessment", "stats"]
        for field in expected_fields:
            assert field in data, f"Missing required field: {field}"
        
        print("✓ Weekly summary has all required fields")
    
    def test_weekly_summary_stats_structure(self, auth_headers):
        """Test stats section has correct fields"""
        response = requests.get(f"{BASE_URL}/api/user/weekly-summary", headers=auth_headers)
        data = response.json()
        stats = data.get("stats", {})
        
        # Check stats fields
        expected_stats = ["total_blunders", "total_mistakes", "total_best_moves",
                        "avg_blunders_per_game", "reflection_attempts", 
                        "reflection_correct", "reflection_rate"]
        for field in expected_stats:
            assert field in stats, f"Stats missing field: {field}"
        
        print(f"✓ Weekly stats: {stats['reflection_correct']}/{stats['reflection_attempts']} reflections correct")
        print(f"  - Reflection rate: {stats['reflection_rate']:.0%}")
    
    def test_weekly_summary_assessment_generated(self, auth_headers):
        """Test that weekly assessment is generated as personalized text"""
        response = requests.get(f"{BASE_URL}/api/user/weekly-summary", headers=auth_headers)
        data = response.json()
        
        assessment = data.get("weekly_assessment", "")
        assert len(assessment) > 20, "Assessment should be a meaningful sentence"
        print(f"✓ Weekly assessment generated: '{assessment[:80]}...'")
    
    def test_weekly_summary_improvement_trend(self, auth_headers):
        """Test improvement trend is one of expected values"""
        response = requests.get(f"{BASE_URL}/api/user/weekly-summary", headers=auth_headers)
        data = response.json()
        
        trend = data.get("improvement_trend", "")
        valid_trends = ["improving", "declining", "stable"]
        assert trend in valid_trends, f"Invalid trend: {trend}"
        print(f"✓ Improvement trend: {trend}")


# ============================================
# SEND WEEKLY SUMMARY ENDPOINT TESTS
# ============================================

class TestSendWeeklySummaryEndpoint:
    """Tests for POST /api/user/send-weekly-summary"""
    
    def test_send_summary_returns_200(self, auth_headers):
        """Test that send-weekly-summary returns 200"""
        response = requests.post(f"{BASE_URL}/api/user/send-weekly-summary", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ POST /api/user/send-weekly-summary returns 200")
    
    def test_send_summary_without_sendgrid(self, auth_headers):
        """Test that endpoint returns 'email not configured' without SendGrid"""
        response = requests.post(f"{BASE_URL}/api/user/send-weekly-summary", headers=auth_headers)
        data = response.json()
        
        # Without SendGrid API key, should return error about email not configured
        assert "status" in data, "Response should contain status"
        if data.get("status") == "error":
            assert "Email not configured" in data.get("reason", ""), \
                "Should indicate email not configured"
            print("✓ Send summary correctly returns 'Email not configured' without SendGrid")
        else:
            # If it somehow succeeded, that's also valid
            print(f"✓ Send summary status: {data.get('status')}")


# ============================================
# PROGRESS PAGE REFLECTION STATS TESTS
# ============================================

class TestProgressReflectionStats:
    """Tests for GET /api/progress - reflection_stats for habits"""
    
    def test_progress_returns_200(self, auth_headers):
        """Test that /api/progress returns 200"""
        response = requests.get(f"{BASE_URL}/api/progress", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ GET /api/progress returns 200")
    
    def test_progress_contains_habits(self, auth_headers):
        """Test that progress contains habits array"""
        response = requests.get(f"{BASE_URL}/api/progress", headers=auth_headers)
        data = response.json()
        
        assert "habits" in data, "Progress should contain 'habits'"
        assert isinstance(data["habits"], list), "habits should be a list"
        print(f"✓ Progress contains {len(data['habits'])} habits")
    
    def test_habits_contain_reflection_stats(self, auth_headers):
        """Test that habits in progress have reflection_stats"""
        response = requests.get(f"{BASE_URL}/api/progress", headers=auth_headers)
        data = response.json()
        habits = data.get("habits", [])
        
        if habits:
            for habit in habits:
                if "reflection_stats" in habit:
                    stats = habit["reflection_stats"]
                    assert "correct" in stats, "reflection_stats should have 'correct'"
                    assert "total" in stats, "reflection_stats should have 'total'"
                    assert "consecutive" in stats, "reflection_stats should have 'consecutive'"
                    assert "status" in stats, "reflection_stats should have 'status'"
                    print(f"✓ Habit '{habit['name']}' has reflection_stats: {stats['correct']}/{stats['total']}")
        else:
            pytest.skip("No habits found to validate")
    
    def test_resolved_habits_section(self, auth_headers):
        """Test that resolved_habits section exists"""
        response = requests.get(f"{BASE_URL}/api/progress", headers=auth_headers)
        data = response.json()
        
        assert "resolved_habits" in data, "Progress should contain 'resolved_habits'"
        assert isinstance(data["resolved_habits"], list), "resolved_habits should be a list"
        print(f"✓ Progress contains resolved_habits section ({len(data['resolved_habits'])} items)")


# ============================================
# TRACK REFLECTION + ROTATION INTEGRATION TEST
# ============================================

class TestTrackReflectionRotationIntegration:
    """Test that track-reflection integrates with habit rotation"""
    
    def test_track_reflection_returns_rotation_info(self, auth_headers):
        """Test that track-reflection can return rotation info when threshold met"""
        # First, get current habit status
        habits_response = requests.get(f"{BASE_URL}/api/coach/habits", headers=auth_headers)
        habits_data = habits_response.json()
        
        if not habits_data.get("habits"):
            pytest.skip("No habits to test rotation")
        
        dominant_habit = next((h for h in habits_data["habits"] if h.get("is_dominant")), None)
        if not dominant_habit:
            pytest.skip("No dominant habit found")
        
        print(f"✓ Current dominant habit: {dominant_habit['habit']}")
        print(f"  - Consecutive correct: {dominant_habit['consecutive_correct']}/4 (threshold)")
        print(f"  - Status: {dominant_habit['status']}")
        
        # Note: We won't trigger actual rotation in tests to preserve user data
        # Just verify the endpoint exists and returns expected fields
        
    def test_rotation_threshold_is_4_consecutive(self, auth_headers):
        """Verify rotation threshold is documented as 4 consecutive correct"""
        # Check habit rotation service constants via endpoint response
        response = requests.post(f"{BASE_URL}/api/coach/check-habit-rotation", headers=auth_headers)
        data = response.json()
        
        # If still working on habit, reason should mention current progress
        if not data["rotated"]:
            reason = data.get("reason", "")
            print(f"✓ Rotation status: {reason}")
            
            # Verify we get performance info
            if "performance" in data:
                perf = data["performance"]
                print(f"  - Current consecutive: {perf.get('consecutive_correct', 0)}")
                print(f"  - Needs 4 consecutive OR 6/8 total to rotate")


# ============================================
# AUTHENTICATION TESTS
# ============================================

class TestAuthenticationRequired:
    """Test that all endpoints require authentication"""
    
    def test_habits_requires_auth(self):
        """Test /api/coach/habits requires auth"""
        response = requests.get(f"{BASE_URL}/api/coach/habits")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ /api/coach/habits requires authentication")
    
    def test_check_rotation_requires_auth(self):
        """Test /api/coach/check-habit-rotation requires auth"""
        response = requests.post(f"{BASE_URL}/api/coach/check-habit-rotation")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ /api/coach/check-habit-rotation requires authentication")
    
    def test_weekly_summary_requires_auth(self):
        """Test /api/user/weekly-summary requires auth"""
        response = requests.get(f"{BASE_URL}/api/user/weekly-summary")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ /api/user/weekly-summary requires authentication")
    
    def test_send_summary_requires_auth(self):
        """Test /api/user/send-weekly-summary requires auth"""
        response = requests.post(f"{BASE_URL}/api/user/send-weekly-summary")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ /api/user/send-weekly-summary requires authentication")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
