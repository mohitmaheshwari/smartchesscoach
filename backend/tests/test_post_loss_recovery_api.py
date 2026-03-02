"""
Test Post-Loss Recovery and Mission Generation APIs
"""
import pytest
import requests
import os
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://socratic-chess-guide.preview.emergentagent.com').rstrip('/')
TEST_GAME_ID = "2d46940d-dfce-4534-9935-9b1ba3829c92"


@pytest.fixture
def api_session():
    """Requests session with dev login"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    
    # Dev login to get session cookie
    login_res = session.get(f"{BASE_URL}/api/auth/dev-login")
    assert login_res.status_code == 200, f"Dev login failed: {login_res.text}"
    
    return session


class TestPostLossRecoveryAPI:
    """Tests for /api/reflect/v1/post-loss/{game_id} endpoint"""
    
    def test_post_loss_endpoint_returns_200(self, api_session):
        """Test that post-loss endpoint returns 200 for valid game"""
        response = api_session.get(f"{BASE_URL}/api/reflect/v1/post-loss/{TEST_GAME_ID}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    
    def test_post_loss_returns_required_fields(self, api_session):
        """Test that post-loss response contains all required fields"""
        response = api_session.get(f"{BASE_URL}/api/reflect/v1/post-loss/{TEST_GAME_ID}")
        assert response.status_code == 200
        
        data = response.json()
        
        # Required fields for post-loss recovery
        required_fields = [
            "game_id",
            "result",
            "opponent_name",
            "user_color",
            "main_issue",
            "headline",
            "estimated_minutes",
            "critical_moment",
        ]
        
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"
    
    def test_post_loss_headline_is_non_empty(self, api_session):
        """Test that headline is a meaningful non-empty string"""
        response = api_session.get(f"{BASE_URL}/api/reflect/v1/post-loss/{TEST_GAME_ID}")
        data = response.json()
        
        headline = data.get("headline")
        assert headline is not None, "Headline should not be None"
        assert isinstance(headline, str), "Headline should be a string"
        assert len(headline) > 10, f"Headline too short: {headline}"
    
    def test_post_loss_main_issue_is_descriptive(self, api_session):
        """Test that main_issue provides a clear focus pattern"""
        response = api_session.get(f"{BASE_URL}/api/reflect/v1/post-loss/{TEST_GAME_ID}")
        data = response.json()
        
        main_issue = data.get("main_issue")
        assert main_issue is not None, "main_issue should not be None"
        assert len(main_issue) > 5, f"main_issue too short: {main_issue}"
    
    def test_post_loss_estimated_minutes_is_reasonable(self, api_session):
        """Test that estimated_minutes is a reasonable value"""
        response = api_session.get(f"{BASE_URL}/api/reflect/v1/post-loss/{TEST_GAME_ID}")
        data = response.json()
        
        minutes = data.get("estimated_minutes")
        assert minutes is not None, "estimated_minutes should not be None"
        assert isinstance(minutes, (int, float)), "estimated_minutes should be numeric"
        assert 1 <= minutes <= 30, f"estimated_minutes out of range: {minutes}"
    
    def test_post_loss_critical_moment_structure(self, api_session):
        """Test critical_moment has correct structure if present"""
        response = api_session.get(f"{BASE_URL}/api/reflect/v1/post-loss/{TEST_GAME_ID}")
        data = response.json()
        
        critical_moment = data.get("critical_moment")
        # critical_moment can be None if no blunders/mistakes
        if critical_moment is not None:
            expected_keys = ["fen", "user_move", "best_move", "eval_change", "move_number"]
            for key in expected_keys:
                assert key in critical_moment, f"critical_moment missing key: {key}"
    
    def test_post_loss_returns_404_for_invalid_game(self, api_session):
        """Test that invalid game ID returns 404"""
        response = api_session.get(f"{BASE_URL}/api/reflect/v1/post-loss/invalid-game-id-12345")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"


class TestMissionGenerateFixAPI:
    """Tests for /api/missions/generate-fix endpoint"""
    
    def test_generate_fix_returns_200(self, api_session):
        """Test that generate-fix endpoint returns 200 for valid game"""
        response = api_session.post(
            f"{BASE_URL}/api/missions/generate-fix",
            json={"game_id": TEST_GAME_ID}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    
    def test_generate_fix_returns_mission_structure(self, api_session):
        """Test that generate-fix returns valid mission structure"""
        response = api_session.post(
            f"{BASE_URL}/api/missions/generate-fix",
            json={"game_id": TEST_GAME_ID}
        )
        assert response.status_code == 200
        
        data = response.json()
        
        # Required mission fields
        required_fields = [
            "mission_id",
            "trigger_type",
            "focus_label",
            "focus_pattern",
            "micro_protocol",
            "goal",
            "estimated_minutes",
        ]
        
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"
    
    def test_generate_fix_trigger_type_is_post_loss(self, api_session):
        """Test that trigger_type is 'post_loss'"""
        response = api_session.post(
            f"{BASE_URL}/api/missions/generate-fix",
            json={"game_id": TEST_GAME_ID}
        )
        data = response.json()
        
        assert data.get("trigger_type") == "post_loss", f"Wrong trigger_type: {data.get('trigger_type')}"
    
    def test_generate_fix_source_game_id_matches(self, api_session):
        """Test that source_game_id matches the requested game"""
        response = api_session.post(
            f"{BASE_URL}/api/missions/generate-fix",
            json={"game_id": TEST_GAME_ID}
        )
        data = response.json()
        
        assert data.get("source_game_id") == TEST_GAME_ID, f"source_game_id mismatch"
    
    def test_generate_fix_micro_protocol_is_list(self, api_session):
        """Test that micro_protocol is a list of steps"""
        response = api_session.post(
            f"{BASE_URL}/api/missions/generate-fix",
            json={"game_id": TEST_GAME_ID}
        )
        data = response.json()
        
        protocol = data.get("micro_protocol")
        assert isinstance(protocol, list), f"micro_protocol should be a list"
        assert len(protocol) > 0, "micro_protocol should not be empty"
    
    def test_generate_fix_goal_has_type_and_target(self, api_session):
        """Test that goal contains type and target"""
        response = api_session.post(
            f"{BASE_URL}/api/missions/generate-fix",
            json={"game_id": TEST_GAME_ID}
        )
        data = response.json()
        
        goal = data.get("goal")
        assert goal is not None, "goal should not be None"
        assert "type" in goal, "goal missing 'type'"
        assert "target" in goal, "goal missing 'target'"
    
    def test_generate_fix_requires_game_id(self, api_session):
        """Test that game_id is required"""
        response = api_session.post(
            f"{BASE_URL}/api/missions/generate-fix",
            json={}
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
    
    def test_generate_fix_returns_404_for_invalid_game(self, api_session):
        """Test that invalid game ID returns 404"""
        response = api_session.post(
            f"{BASE_URL}/api/missions/generate-fix",
            json={"game_id": "invalid-game-id-12345"}
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"


class TestCoachFreshLossAPI:
    """Tests for /api/coach/fresh-loss endpoint"""
    
    def test_fresh_loss_returns_200(self, api_session):
        """Test that fresh-loss endpoint returns 200"""
        response = api_session.get(f"{BASE_URL}/api/coach/fresh-loss")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    
    def test_fresh_loss_returns_has_fresh_loss_flag(self, api_session):
        """Test that response contains has_fresh_loss boolean"""
        response = api_session.get(f"{BASE_URL}/api/coach/fresh-loss")
        data = response.json()
        
        assert "has_fresh_loss" in data, "Missing has_fresh_loss field"
        assert isinstance(data["has_fresh_loss"], bool), "has_fresh_loss should be boolean"
    
    def test_fresh_loss_returns_game_details_when_present(self, api_session):
        """Test that when fresh loss exists, game details are returned"""
        response = api_session.get(f"{BASE_URL}/api/coach/fresh-loss")
        data = response.json()
        
        if data.get("has_fresh_loss"):
            # If there's a fresh loss, these fields should be present
            assert "game_id" in data, "Missing game_id when fresh loss exists"
            assert "focus_label" in data, "Missing focus_label when fresh loss exists"
            assert "estimated_minutes" in data, "Missing estimated_minutes when fresh loss exists"


class TestCoachWeeklyProofAPI:
    """Tests for /api/coach/weekly-proof endpoint"""
    
    def test_weekly_proof_returns_200(self, api_session):
        """Test that weekly-proof endpoint returns 200"""
        response = api_session.get(f"{BASE_URL}/api/coach/weekly-proof")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    
    def test_weekly_proof_returns_required_fields(self, api_session):
        """Test that weekly-proof returns required statistics"""
        response = api_session.get(f"{BASE_URL}/api/coach/weekly-proof")
        data = response.json()
        
        required_fields = ["wins", "missions_completed", "streak_days"]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"
    
    def test_weekly_proof_wins_is_non_negative(self, api_session):
        """Test that wins count is non-negative integer"""
        response = api_session.get(f"{BASE_URL}/api/coach/weekly-proof")
        data = response.json()
        
        wins = data.get("wins")
        assert isinstance(wins, int), f"wins should be int, got {type(wins)}"
        assert wins >= 0, f"wins should be non-negative, got {wins}"
    
    def test_weekly_proof_missions_completed_is_non_negative(self, api_session):
        """Test that missions_completed is non-negative"""
        response = api_session.get(f"{BASE_URL}/api/coach/weekly-proof")
        data = response.json()
        
        missions = data.get("missions_completed")
        assert isinstance(missions, int), f"missions_completed should be int"
        assert missions >= 0, f"missions_completed should be non-negative"


class TestMissionsTodayAPI:
    """Tests for /api/missions/today endpoint"""
    
    def test_missions_today_returns_200(self, api_session):
        """Test that missions/today endpoint returns 200"""
        response = api_session.get(f"{BASE_URL}/api/missions/today")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    
    def test_missions_today_returns_mission_data(self, api_session):
        """Test that missions/today returns valid mission structure"""
        response = api_session.get(f"{BASE_URL}/api/missions/today")
        data = response.json()
        
        # Mission should have these fields when present
        if data.get("mission_id"):
            expected_fields = ["mission_id", "focus_label", "micro_protocol", "estimated_minutes"]
            for field in expected_fields:
                assert field in data, f"Missing field: {field}"
