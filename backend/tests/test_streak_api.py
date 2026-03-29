"""
Test Streak API - P0: Carry-Forward + Mistake-Free Streak

Tests:
- GET /api/streak/status - Get current streak state for pre-game display
- GET /api/streak/focus-types - Get all available focus mistake types
- POST /api/streak/set-focus - Set user's focus mistake type
- GET /api/streak/history - Get streak history
- POST /api/streak/update - Update streak after game analysis
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestStreakFocusTypes:
    """Test GET /api/streak/focus-types endpoint"""
    
    def test_get_focus_types_returns_all_types(self):
        """Should return all 5 focus mistake types"""
        response = requests.get(f"{BASE_URL}/api/streak/focus-types")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify structure
        assert "focus_types" in data
        focus_types = data["focus_types"]
        
        # Should have 5 types
        assert len(focus_types) == 5
        
        # Verify each type has required fields
        expected_keys = ["THREAT_VERIFICATION", "FORCING_BLIND", "STOPPED_CALCULATION_EARLY", "HANGING_PIECE", "TACTICAL_MISS"]
        actual_keys = [ft["key"] for ft in focus_types]
        
        for key in expected_keys:
            assert key in actual_keys, f"Missing focus type: {key}"
        
        # Verify each type has name, short_name, description, rule
        for ft in focus_types:
            assert "key" in ft
            assert "name" in ft
            assert "short_name" in ft
            assert "description" in ft
            assert "rule" in ft
            assert len(ft["rule"]) > 10, "Rule should be descriptive"


class TestStreakStatus:
    """Test GET /api/streak/status endpoint"""
    
    def test_get_streak_status_new_user(self):
        """Should return default streak data for new user"""
        response = requests.get(f"{BASE_URL}/api/streak/status?user_id=TEST_new_user_streak_123")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify default values for new user
        assert data["current_streak"] == 0
        assert data["best_streak"] == 0
        assert data["last_game_had_mistake"] == False
        assert data["headline"] == "Start Your Streak"
        assert data["tone"] == "neutral"
        
        # Verify focus mistake info
        assert "focus_mistake_name" in data
        assert "rule" in data
        assert len(data["rule"]) > 10
    
    def test_get_streak_status_requires_user_id(self):
        """Should handle missing user_id gracefully"""
        response = requests.get(f"{BASE_URL}/api/streak/status")
        
        # Should return 422 (validation error) or handle gracefully
        assert response.status_code in [400, 422, 500]


class TestSetFocus:
    """Test POST /api/streak/set-focus endpoint"""
    
    def test_set_focus_success(self):
        """Should successfully set focus mistake type"""
        payload = {
            "user_id": "TEST_set_focus_user_123",
            "focus_type": "HANGING_PIECE"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/streak/set-focus",
            json=payload
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] == True
        assert data["focus_type"] == "HANGING_PIECE"
        assert data["focus_name"] == "Hanging Pieces"
        assert "Before EVERY move" in data["focus_rule"]
        
        # Verify streak_data is returned
        assert "streak_data" in data
        assert data["streak_data"]["current_focus_mistake"] == "HANGING_PIECE"
    
    def test_set_focus_invalid_type(self):
        """Should reject invalid focus type"""
        payload = {
            "user_id": "TEST_invalid_focus_user",
            "focus_type": "INVALID_TYPE"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/streak/set-focus",
            json=payload
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "Invalid focus_type" in data.get("detail", "")
    
    def test_set_focus_missing_fields(self):
        """Should reject request with missing fields"""
        payload = {"user_id": "TEST_missing_fields"}
        
        response = requests.post(
            f"{BASE_URL}/api/streak/set-focus",
            json=payload
        )
        
        assert response.status_code == 400
    
    def test_set_focus_with_reset(self):
        """Should reset streak when reset_streak=True"""
        user_id = "TEST_reset_streak_user"
        
        # First set a focus
        requests.post(
            f"{BASE_URL}/api/streak/set-focus",
            json={"user_id": user_id, "focus_type": "THREAT_VERIFICATION"}
        )
        
        # Now set new focus with reset
        payload = {
            "user_id": user_id,
            "focus_type": "TACTICAL_MISS",
            "reset_streak": True
        }
        
        response = requests.post(
            f"{BASE_URL}/api/streak/set-focus",
            json=payload
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["focus_type"] == "TACTICAL_MISS"
        assert data["streak_data"]["mistake_streak"]["current"] == 0
        assert data["streak_data"]["last_5_games"] == []


class TestStreakHistory:
    """Test GET /api/streak/history endpoint"""
    
    def test_get_streak_history_new_user(self):
        """Should return default history for new user"""
        response = requests.get(f"{BASE_URL}/api/streak/history?user_id=TEST_history_new_user")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "streak_data" in data
        assert "focus_types" in data
        
        # Verify default streak data
        streak_data = data["streak_data"]
        assert streak_data["current_focus_mistake"] == "THREAT_VERIFICATION"
        assert streak_data["mistake_streak"]["current"] == 0
        assert streak_data["last_5_games"] == []
        
        # Verify focus types list
        assert len(data["focus_types"]) == 5


class TestStreakUpdate:
    """Test POST /api/streak/update endpoint"""
    
    def test_update_streak_missing_fields(self):
        """Should reject update with missing required fields"""
        payload = {"user_id": "TEST_update_missing"}
        
        response = requests.post(
            f"{BASE_URL}/api/streak/update",
            json=payload
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "user_id and game_id required" in data.get("detail", "")
    
    def test_update_streak_no_move_evaluations(self):
        """Should handle game with no move evaluations"""
        payload = {
            "user_id": "TEST_update_no_evals",
            "game_id": "game_123",
            "user_color": "white",
            "stockfish_analysis": {}
        }
        
        response = requests.post(
            f"{BASE_URL}/api/streak/update",
            json=payload
        )
        
        # Should return 200 but not update streak (no move evals)
        assert response.status_code == 200
    
    def test_update_streak_with_clean_game(self):
        """Should increment streak for game without focus mistakes"""
        user_id = "TEST_clean_game_user"
        
        # First set focus type
        requests.post(
            f"{BASE_URL}/api/streak/set-focus",
            json={"user_id": user_id, "focus_type": "THREAT_VERIFICATION", "reset_streak": True}
        )
        
        # Simulate a clean game (no significant mistakes)
        payload = {
            "user_id": user_id,
            "game_id": "clean_game_001",
            "user_color": "white",
            "stockfish_analysis": {
                "move_evaluations": [
                    {"is_user_move": True, "move_number": 1, "cp_loss": 10},
                    {"is_user_move": False, "move_number": 1, "cp_loss": 5},
                    {"is_user_move": True, "move_number": 2, "cp_loss": 15},
                    {"is_user_move": False, "move_number": 2, "cp_loss": 8},
                    {"is_user_move": True, "move_number": 3, "cp_loss": 20},
                    {"is_user_move": False, "move_number": 3, "cp_loss": 12},
                    {"is_user_move": True, "move_number": 4, "cp_loss": 5},
                    {"is_user_move": False, "move_number": 4, "cp_loss": 10},
                    {"is_user_move": True, "move_number": 5, "cp_loss": 15},
                    {"is_user_move": False, "move_number": 5, "cp_loss": 8},
                    {"is_user_move": True, "move_number": 6, "cp_loss": 10},
                    {"is_user_move": False, "move_number": 6, "cp_loss": 5},
                    {"is_user_move": True, "move_number": 7, "cp_loss": 20},
                    {"is_user_move": False, "move_number": 7, "cp_loss": 15},
                    {"is_user_move": True, "move_number": 8, "cp_loss": 10},
                    {"is_user_move": False, "move_number": 8, "cp_loss": 5},
                ]
            }
        }
        
        response = requests.post(
            f"{BASE_URL}/api/streak/update",
            json=payload
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify streak data
        assert "streak_data" in data
        assert "postgame_result" in data
        
        # Clean game should continue streak
        postgame = data["postgame_result"]
        assert postgame["result"] in ["continued", "new_best"]


class TestStreakIntegration:
    """Integration tests for streak flow"""
    
    def test_full_streak_flow(self):
        """Test complete flow: set focus -> check status -> verify"""
        user_id = "TEST_full_flow_user"
        
        # 1. Set focus type
        set_response = requests.post(
            f"{BASE_URL}/api/streak/set-focus",
            json={"user_id": user_id, "focus_type": "FORCING_BLIND", "reset_streak": True}
        )
        assert set_response.status_code == 200
        
        # 2. Get status
        status_response = requests.get(f"{BASE_URL}/api/streak/status?user_id={user_id}")
        assert status_response.status_code == 200
        status_data = status_response.json()
        
        # Verify focus was set
        assert status_data["focus_mistake_name"] == "Forcing Move Blindness"
        assert "check" in status_data["rule"].lower()
        
        # 3. Get history
        history_response = requests.get(f"{BASE_URL}/api/streak/history?user_id={user_id}")
        assert history_response.status_code == 200
        history_data = history_response.json()
        
        assert history_data["streak_data"]["current_focus_mistake"] == "FORCING_BLIND"


# Cleanup fixture
@pytest.fixture(scope="module", autouse=True)
def cleanup_test_data():
    """Cleanup test data after all tests"""
    yield
    # Note: In production, would delete TEST_ prefixed users
    # For now, test data will persist but is isolated by TEST_ prefix
