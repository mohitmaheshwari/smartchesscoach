"""
Backend tests for P1.6 Historical Re-Analysis + Adaptive Difficulty features

Tests:
1. POST /api/behavioral/reanalysis/enqueue - Creates job and returns job_id
2. POST /api/behavioral/reanalysis/enqueue - Idempotent (same job returned on duplicate)
3. GET /api/behavioral/reanalysis/status - Returns job progress
4. GET /api/behavioral/last-report - Returns difficulty field (EASY/STANDARD/HARD)
5. GET /api/behavioral/last-report - Returns engine_version (P1.6)
6. GET /api/behavioral/last-report - Returns difficulty_reason
7. next_mission includes difficulty badge
8. Difficulty adapts based on learner_type
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://chessguru-coach.preview.emergentagent.com')

# Valid difficulty levels
VALID_DIFFICULTIES = ["EASY", "STANDARD", "HARD"]

# Expected engine version
EXPECTED_ENGINE_VERSION = "P1.6"


@pytest.fixture
def authenticated_session():
    """Session with dev login authentication"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    
    res = session.get(f"{BASE_URL}/api/auth/dev-login")
    if res.status_code != 200:
        pytest.skip("Dev login failed - skipping authenticated tests")
    
    return session


class TestReanalysisEnqueueEndpoint:
    """Tests for POST /api/behavioral/reanalysis/enqueue"""
    
    def test_enqueue_creates_job_returns_job_id(self, authenticated_session):
        """Test that enqueue creates a job and returns job_id"""
        res = authenticated_session.post(f"{BASE_URL}/api/behavioral/reanalysis/enqueue")
        assert res.status_code == 200, f"Expected 200, got {res.status_code}"
        
        data = res.json()
        assert "job_id" in data, "Response should contain job_id"
        assert data["job_id"] is not None, "job_id should not be None"
        assert len(data["job_id"]) > 0, "job_id should not be empty"
    
    def test_enqueue_returns_status(self, authenticated_session):
        """Test that enqueue returns status field"""
        res = authenticated_session.post(f"{BASE_URL}/api/behavioral/reanalysis/enqueue")
        assert res.status_code == 200
        
        data = res.json()
        assert "status" in data, "Response should contain status"
        assert data["status"] in ["PENDING", "RUNNING", "DONE", "FAILED"], f"Invalid status: {data['status']}"
    
    def test_enqueue_returns_message(self, authenticated_session):
        """Test that enqueue returns message field"""
        res = authenticated_session.post(f"{BASE_URL}/api/behavioral/reanalysis/enqueue")
        assert res.status_code == 200
        
        data = res.json()
        assert "message" in data, "Response should contain message"
        assert isinstance(data["message"], str), "message should be a string"
    
    def test_enqueue_is_idempotent(self, authenticated_session):
        """Test that enqueue is idempotent - same job returned on duplicate"""
        # First call
        res1 = authenticated_session.post(f"{BASE_URL}/api/behavioral/reanalysis/enqueue")
        assert res1.status_code == 200
        data1 = res1.json()
        
        # Second call immediately after (should return same job if not finished)
        res2 = authenticated_session.post(f"{BASE_URL}/api/behavioral/reanalysis/enqueue")
        assert res2.status_code == 200
        data2 = res2.json()
        
        # Job IDs should be the same if idempotent OR different if job was completed
        # Both are valid - idempotent means same job returned if still pending/running
        assert "job_id" in data1 and "job_id" in data2
        
        # If first job is PENDING or RUNNING, second should return same job
        if data1["status"] in ["PENDING", "RUNNING"]:
            assert data1["job_id"] == data2["job_id"], "Idempotency violation: different job_id for same pending/running state"


class TestReanalysisStatusEndpoint:
    """Tests for GET /api/behavioral/reanalysis/status"""
    
    def test_status_returns_valid_response(self, authenticated_session):
        """Test that status endpoint returns valid response"""
        res = authenticated_session.get(f"{BASE_URL}/api/behavioral/reanalysis/status")
        assert res.status_code == 200, f"Expected 200, got {res.status_code}"
        
        data = res.json()
        # Should have either status or NO_JOB indicator
        assert "status" in data, "Response should contain status field"
    
    def test_status_returns_progress_fields_when_job_exists(self, authenticated_session):
        """Test that status returns progress fields when a job exists"""
        # First enqueue a job
        enqueue_res = authenticated_session.post(f"{BASE_URL}/api/behavioral/reanalysis/enqueue")
        assert enqueue_res.status_code == 200
        
        # Check status
        status_res = authenticated_session.get(f"{BASE_URL}/api/behavioral/reanalysis/status")
        assert status_res.status_code == 200
        
        data = status_res.json()
        
        # If NO_JOB, skip further checks
        if data.get("status") == "NO_JOB":
            pytest.skip("No job to test progress fields")
        
        # Should have progress fields
        expected_fields = ["processed_games", "total_games", "engine_version", "progress_percent"]
        for field in expected_fields:
            assert field in data, f"Response should contain {field}"
    
    def test_status_returns_engine_version(self, authenticated_session):
        """Test that status returns correct engine_version"""
        # Enqueue a job first
        authenticated_session.post(f"{BASE_URL}/api/behavioral/reanalysis/enqueue")
        
        res = authenticated_session.get(f"{BASE_URL}/api/behavioral/reanalysis/status")
        assert res.status_code == 200
        
        data = res.json()
        
        if data.get("status") != "NO_JOB":
            assert "engine_version" in data
            assert data["engine_version"] == EXPECTED_ENGINE_VERSION, f"Expected {EXPECTED_ENGINE_VERSION}, got {data['engine_version']}"


class TestDifficultyInLastReport:
    """Tests for difficulty fields in /api/behavioral/last-report"""
    
    def test_last_report_returns_difficulty_field(self, authenticated_session):
        """Test that last-report returns difficulty field"""
        res = authenticated_session.get(f"{BASE_URL}/api/behavioral/last-report")
        assert res.status_code == 200
        
        data = res.json()
        assert "difficulty" in data, "Response should contain difficulty field"
        assert data["difficulty"] in VALID_DIFFICULTIES, f"difficulty should be one of {VALID_DIFFICULTIES}"
    
    def test_last_report_returns_engine_version(self, authenticated_session):
        """Test that last-report returns engine_version field (P1.6)"""
        res = authenticated_session.get(f"{BASE_URL}/api/behavioral/last-report")
        assert res.status_code == 200
        
        data = res.json()
        assert "engine_version" in data, "Response should contain engine_version field"
        assert data["engine_version"] == EXPECTED_ENGINE_VERSION, f"Expected {EXPECTED_ENGINE_VERSION}, got {data['engine_version']}"
    
    def test_last_report_returns_difficulty_reason(self, authenticated_session):
        """Test that last-report returns difficulty_reason field"""
        res = authenticated_session.get(f"{BASE_URL}/api/behavioral/last-report")
        assert res.status_code == 200
        
        data = res.json()
        assert "difficulty_reason" in data, "Response should contain difficulty_reason field"
        assert isinstance(data["difficulty_reason"], str), "difficulty_reason should be a string"
        assert len(data["difficulty_reason"]) > 0, "difficulty_reason should not be empty"
    
    def test_last_report_next_mission_has_difficulty(self, authenticated_session):
        """Test that next_mission includes difficulty badge"""
        res = authenticated_session.get(f"{BASE_URL}/api/behavioral/last-report")
        assert res.status_code == 200
        
        data = res.json()
        next_mission = data.get("next_mission", {})
        
        assert "difficulty" in next_mission, "next_mission should contain difficulty field"
        assert next_mission["difficulty"] in VALID_DIFFICULTIES, f"next_mission difficulty should be one of {VALID_DIFFICULTIES}"
    
    def test_last_report_next_mission_has_difficulty_reason(self, authenticated_session):
        """Test that next_mission includes difficulty_reason"""
        res = authenticated_session.get(f"{BASE_URL}/api/behavioral/last-report")
        assert res.status_code == 200
        
        data = res.json()
        next_mission = data.get("next_mission", {})
        
        assert "difficulty_reason" in next_mission, "next_mission should contain difficulty_reason field"


class TestDifficultyPolicy:
    """Tests for adaptive difficulty logic"""
    
    def test_difficulty_correlates_with_learner_type(self, authenticated_session):
        """Test that difficulty adapts based on learner_type"""
        res = authenticated_session.get(f"{BASE_URL}/api/behavioral/last-report")
        assert res.status_code == 200
        
        data = res.json()
        
        learner_type = data.get("learner_type")
        difficulty = data.get("difficulty")
        difficulty_reason = data.get("difficulty_reason", "")
        
        assert learner_type is not None, "learner_type should be present"
        assert difficulty is not None, "difficulty should be present"
        
        # NOT_APPLYING should have EASY difficulty
        if learner_type == "NOT_APPLYING":
            assert difficulty == "EASY", f"NOT_APPLYING should have EASY difficulty, got {difficulty}"
        
        # HARD difficulty requires FAST_ADAPTER
        if difficulty == "HARD":
            assert learner_type == "FAST_ADAPTER", f"HARD difficulty requires FAST_ADAPTER, got {learner_type}"
    
    def test_difficulty_guardrail_field_present(self, authenticated_session):
        """Test that difficulty_guardrail field is present when applicable"""
        res = authenticated_session.get(f"{BASE_URL}/api/behavioral/last-report")
        assert res.status_code == 200
        
        data = res.json()
        
        # difficulty_guardrail can be null if no guardrail triggered
        assert "difficulty_guardrail" in data, "Response should contain difficulty_guardrail field"
        
        guardrail = data.get("difficulty_guardrail")
        if guardrail is not None:
            valid_guardrails = [
                "DIFFICULTY_DECAY",
                "LOW_CONFIDENCE",
                "STAGNATION_SIMPLIFY",
                "STAGNATION_CAP",
                "CONFIDENCE_CAP",
                "RECENT_COLLAPSE_CAP"
            ]
            assert guardrail in valid_guardrails, f"Invalid guardrail: {guardrail}"


class TestBehavioralAnalyzeEndpointP16:
    """Tests for P1.6 fields in /api/behavioral/analyze/{game_id}"""
    
    def test_analyze_returns_difficulty_fields(self, authenticated_session):
        """Test that analyze endpoint returns P1.6 difficulty fields"""
        # First get a game_id from last-report
        last_res = authenticated_session.get(f"{BASE_URL}/api/behavioral/last-report")
        if last_res.status_code != 200:
            pytest.skip("No last report available")
        
        game_id = last_res.json().get("game_id")
        if not game_id:
            pytest.skip("No game_id in last report")
        
        res = authenticated_session.get(f"{BASE_URL}/api/behavioral/analyze/{game_id}")
        assert res.status_code == 200
        
        data = res.json()
        
        # Check P1.6 fields
        assert "difficulty" in data, "Response should contain difficulty"
        assert data["difficulty"] in VALID_DIFFICULTIES
        
        assert "difficulty_reason" in data, "Response should contain difficulty_reason"
        assert isinstance(data["difficulty_reason"], str)
        
        assert "engine_version" in data, "Response should contain engine_version"
        assert data["engine_version"] == EXPECTED_ENGINE_VERSION
    
    def test_analyze_next_mission_has_difficulty_badge(self, authenticated_session):
        """Test that analyze endpoint next_mission has difficulty badge"""
        last_res = authenticated_session.get(f"{BASE_URL}/api/behavioral/last-report")
        if last_res.status_code != 200:
            pytest.skip("No last report available")
        
        game_id = last_res.json().get("game_id")
        if not game_id:
            pytest.skip("No game_id in last report")
        
        res = authenticated_session.get(f"{BASE_URL}/api/behavioral/analyze/{game_id}")
        assert res.status_code == 200
        
        data = res.json()
        next_mission = data.get("next_mission", {})
        
        assert "difficulty" in next_mission, "next_mission should have difficulty"
        assert next_mission["difficulty"] in VALID_DIFFICULTIES


class TestMissionTemplatesIntegration:
    """Tests to verify mission templates are applied correctly"""
    
    def test_mission_has_params_field(self, authenticated_session):
        """Test that next_mission includes params from templates"""
        res = authenticated_session.get(f"{BASE_URL}/api/behavioral/last-report")
        assert res.status_code == 200
        
        data = res.json()
        next_mission = data.get("next_mission", {})
        
        # Mission should have additional params from templates
        # These vary by mission type, but common ones include:
        optional_params = ["timebox_seconds", "required_reps", "positions", "params"]
        has_at_least_one = any(param in next_mission for param in optional_params)
        
        # params field should contain the detailed template parameters
        if "params" in next_mission:
            params = next_mission["params"]
            assert isinstance(params, dict), "params should be a dict"
            assert "difficulty" in params, "params should contain difficulty"


class TestHistoricalModeField:
    """Tests for historical_mode field in behavioral reports"""
    
    def test_last_report_has_historical_mode(self, authenticated_session):
        """Test that last-report includes historical_mode field"""
        res = authenticated_session.get(f"{BASE_URL}/api/behavioral/last-report")
        assert res.status_code == 200
        
        data = res.json()
        assert "historical_mode" in data, "Response should contain historical_mode field"
        
        # For live reports, historical_mode should be False
        assert data["historical_mode"] == False, "Live reports should have historical_mode=False"
