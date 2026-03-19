"""Backend tests for Mission and Reward endpoints (Phase 2C/2D)"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://habit-trainer-1.preview.emergentagent.com')


@pytest.fixture
def api_session():
    """Create session with dev login authentication"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    
    # Authenticate via dev login
    res = session.get(f"{BASE_URL}/api/auth/dev-login")
    if res.status_code != 200:
        pytest.skip("Dev login failed - skipping authenticated tests")
    
    return session


class TestMissionsEndpoints:
    """Test mission-related endpoints"""
    
    def test_get_today_mission(self, api_session):
        """Test GET /api/missions/today returns valid mission data"""
        res = api_session.get(f"{BASE_URL}/api/missions/today")
        assert res.status_code == 200
        
        data = res.json()
        # Validate required fields
        assert "mission_id" in data
        assert "focus_label" in data
        assert "micro_protocol" in data
        assert "goal" in data
        assert "estimated_minutes" in data
        assert "status" in data
        
        # Validate goal structure
        goal = data["goal"]
        assert "type" in goal
        assert "target" in goal
        assert "success_threshold" in goal
        
        # Validate micro_protocol is a list
        assert isinstance(data["micro_protocol"], list)
        assert len(data["micro_protocol"]) > 0
        
    def test_mission_start(self, api_session):
        """Test POST /api/missions/{mission_id}/start creates session"""
        # First get today's mission
        res = api_session.get(f"{BASE_URL}/api/missions/today")
        assert res.status_code == 200
        mission = res.json()
        mission_id = mission["mission_id"]
        
        # Start the mission
        res = api_session.post(f"{BASE_URL}/api/missions/{mission_id}/start")
        assert res.status_code == 200
        
        data = res.json()
        assert "session_id" in data
        assert data["mission_id"] == mission_id
        assert data["status"] == "started"
        
    def test_mission_step_recording(self, api_session):
        """Test POST /api/missions/{mission_id}/step records drill results"""
        # Get mission
        res = api_session.get(f"{BASE_URL}/api/missions/today")
        mission = res.json()
        mission_id = mission["mission_id"]
        
        # Start mission to create session
        api_session.post(f"{BASE_URL}/api/missions/{mission_id}/start")
        
        # Record a step
        step_data = {
            "step_type": "drill_result",
            "payload": {
                "step_index": 0,
                "correct": True,
                "time_taken_ms": 5000
            }
        }
        res = api_session.post(
            f"{BASE_URL}/api/missions/{mission_id}/step",
            json=step_data
        )
        assert res.status_code == 200
        
    def test_mission_history(self, api_session):
        """Test GET /api/missions/history returns mission list"""
        res = api_session.get(f"{BASE_URL}/api/missions/history")
        assert res.status_code == 200
        
        data = res.json()
        assert "missions" in data
        assert isinstance(data["missions"], list)


class TestRewardsEndpoints:
    """Test reward message endpoints"""
    
    def test_post_loss_message(self, api_session):
        """Test GET /api/rewards/post-loss-message returns recovery message"""
        # Get a game ID from dashboard stats
        res = api_session.get(f"{BASE_URL}/api/dashboard-stats")
        assert res.status_code == 200
        stats = res.json()
        
        # Find an analyzed game
        analyzed_list = stats.get("analyzed_list", [])
        if not analyzed_list:
            pytest.skip("No analyzed games available")
        
        game_id = analyzed_list[0]["game_id"]
        
        # Get post-loss message
        res = api_session.get(f"{BASE_URL}/api/rewards/post-loss-message?game_id={game_id}")
        assert res.status_code == 200
        
        data = res.json()
        # Validate required fields
        assert "headline" in data
        assert "subtext" in data
        assert "focus_label" in data
        assert "cta_text" in data
        assert "minutes" in data
        
        # Validate minutes is a number
        assert isinstance(data["minutes"], int)
        
    def test_rewards_feed(self, api_session):
        """Test GET /api/rewards/feed returns reward events"""
        res = api_session.get(f"{BASE_URL}/api/rewards/feed")
        assert res.status_code == 200
        
        data = res.json()
        assert "events" in data
        assert isinstance(data["events"], list)


class TestDashboardIntegration:
    """Test dashboard stats include mission data"""
    
    def test_dashboard_stats_contains_games(self, api_session):
        """Test dashboard stats returns game counts"""
        res = api_session.get(f"{BASE_URL}/api/dashboard-stats")
        assert res.status_code == 200
        
        data = res.json()
        assert "total_games" in data
        assert "analyzed_games" in data
        assert data["total_games"] > 0  # User should have games
        
    def test_auth_me_returns_user(self, api_session):
        """Test /api/auth/me returns authenticated user"""
        res = api_session.get(f"{BASE_URL}/api/auth/me")
        assert res.status_code == 200
        
        data = res.json()
        assert "user_id" in data
        assert "email" in data
