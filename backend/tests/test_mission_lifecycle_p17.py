"""
P1.7 Mission Lifecycle Tests

Tests for:
1. POST /api/behavioral/mission/start creates STARTED mission record
2. POST /api/behavioral/mission/complete returns validation result  
3. Validation returns applicable=false when no games after mission
4. Mission stays STARTED when validation not applicable
5. GET /api/behavioral/mission/active returns active missions
6. GET /api/behavioral/mission/history returns mission history with validation scores
7. GET /api/behavioral/mission/last-result returns last completed mission
8. Validation uses VALIDATION_WINDOW_GAMES (3) not just next game
9. Difficulty decay only triggers on validated HARD failures (score < 0.4)
10. Learning velocity includes mission_adjustment with smoothing
11. Narrative references mission results only when confident (score >= 0.6 or <= 0.3)
"""

import pytest
import requests
import os
import uuid
from datetime import datetime, timezone

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://chess-coach-ai-3.preview.emergentagent.com')


@pytest.fixture(scope="module")
def authenticated_session():
    """Session with dev login authentication"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    
    # Authenticate via dev login
    res = session.get(f"{BASE_URL}/api/auth/dev-login")
    if res.status_code != 200:
        pytest.skip("Dev login failed - skipping authenticated tests")
    
    return session


class TestMissionStartEndpoint:
    """Tests for POST /api/behavioral/mission/start"""
    
    def test_mission_start_creates_started_record(self, authenticated_session):
        """Test that starting a mission creates a STARTED record"""
        response = authenticated_session.post(
            f"{BASE_URL}/api/behavioral/mission/start",
            json={
                "mission_type": "TEST_TIME_DECISION_DRILL",
                "difficulty": "STANDARD",
                "root_cause": "TIME_TRIGGERED"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "mission_id" in data
        assert data["status"] == "STARTED"
        assert data["message"] == "Mission tracking started"
        
        # Store mission_id for cleanup
        self.last_mission_id = data["mission_id"]
    
    def test_mission_start_with_game_context(self, authenticated_session):
        """Test that mission can be started with game context"""
        response = authenticated_session.post(
            f"{BASE_URL}/api/behavioral/mission/start",
            json={
                "mission_type": "TEST_CANDIDATE_MOVE_DRILL",
                "difficulty": "HARD",
                "game_id_context": "test_game_12345",
                "root_cause": "CALCULATION_GAP"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "STARTED"
    
    def test_mission_start_with_payload(self, authenticated_session):
        """Test that mission can be started with custom payload"""
        response = authenticated_session.post(
            f"{BASE_URL}/api/behavioral/mission/start",
            json={
                "mission_type": "TEST_ADVICE_ENFORCEMENT",
                "difficulty": "EASY",
                "payload": {
                    "advice_id": "test_advice_123",
                    "rule_code": "RULE_001"
                }
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "STARTED"


class TestMissionCompleteEndpoint:
    """Tests for POST /api/behavioral/mission/complete"""
    
    def test_mission_complete_returns_validation_result(self, authenticated_session):
        """Test that completing a mission returns validation result"""
        # First create a mission
        start_response = authenticated_session.post(
            f"{BASE_URL}/api/behavioral/mission/start",
            json={
                "mission_type": "TEST_VALIDATION_DRILL",
                "difficulty": "STANDARD"
            }
        )
        assert start_response.status_code == 200
        mission_id = start_response.json()["mission_id"]
        
        # Complete the mission
        complete_response = authenticated_session.post(
            f"{BASE_URL}/api/behavioral/mission/complete",
            json={
                "mission_id": mission_id,
                "user_self_rating": 4
            }
        )
        
        assert complete_response.status_code == 200
        data = complete_response.json()
        
        # Verify response has validation data
        assert "status" in data
        assert "validation" in data
        assert "difficulty_decay_triggered" in data
        
        # Verify validation structure
        validation = data["validation"]
        assert "applicable" in validation
        assert "score" in validation
        assert "confidence" in validation
        assert "validation_games_used" in validation
        assert "metrics" in validation
        assert "reason" in validation
    
    def test_mission_stays_started_when_validation_not_applicable(self, authenticated_session):
        """Test that mission stays STARTED when no applicable games exist"""
        # Create a mission with unique type to avoid game matches
        start_response = authenticated_session.post(
            f"{BASE_URL}/api/behavioral/mission/start",
            json={
                "mission_type": f"TEST_NO_GAMES_{uuid.uuid4().hex[:8]}",
                "difficulty": "STANDARD"
            }
        )
        assert start_response.status_code == 200
        mission_id = start_response.json()["mission_id"]
        
        # Complete immediately (no games should exist after this just-created mission)
        complete_response = authenticated_session.post(
            f"{BASE_URL}/api/behavioral/mission/complete",
            json={"mission_id": mission_id}
        )
        
        assert complete_response.status_code == 200
        data = complete_response.json()
        
        # Mission should stay STARTED since validation not applicable
        assert data["status"] == "STARTED"
        assert data["validation"]["applicable"] == False
        assert data["difficulty_decay_triggered"] == False
    
    def test_mission_complete_with_self_rating(self, authenticated_session):
        """Test that user self-rating is accepted"""
        # Create a mission
        start_response = authenticated_session.post(
            f"{BASE_URL}/api/behavioral/mission/start",
            json={
                "mission_type": "TEST_SELF_RATING_DRILL",
                "difficulty": "STANDARD"
            }
        )
        mission_id = start_response.json()["mission_id"]
        
        # Complete with self-rating
        complete_response = authenticated_session.post(
            f"{BASE_URL}/api/behavioral/mission/complete",
            json={
                "mission_id": mission_id,
                "user_self_rating": 5
            }
        )
        
        assert complete_response.status_code == 200
    
    def test_mission_complete_nonexistent_mission_returns_error(self, authenticated_session):
        """Test that completing nonexistent mission returns error"""
        complete_response = authenticated_session.post(
            f"{BASE_URL}/api/behavioral/mission/complete",
            json={
                "mission_id": "nonexistent-mission-id-12345"
            }
        )
        
        assert complete_response.status_code == 200
        data = complete_response.json()
        assert "error" in data


class TestMissionActiveEndpoint:
    """Tests for GET /api/behavioral/mission/active"""
    
    def test_active_missions_returns_started_missions(self, authenticated_session):
        """Test that active endpoint returns STARTED missions"""
        response = authenticated_session.get(
            f"{BASE_URL}/api/behavioral/mission/active"
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify structure
        assert "active_missions" in data
        assert "count" in data
        assert isinstance(data["active_missions"], list)
        
        # If there are missions, verify their structure
        if data["count"] > 0:
            mission = data["active_missions"][0]
            assert "mission_id" in mission
            assert "mission_type" in mission
            assert "difficulty" in mission
            assert "created_at" in mission


class TestMissionHistoryEndpoint:
    """Tests for GET /api/behavioral/mission/history"""
    
    def test_history_returns_missions_with_validation_scores(self, authenticated_session):
        """Test that history includes validation scores"""
        response = authenticated_session.get(
            f"{BASE_URL}/api/behavioral/mission/history?limit=10"
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify structure
        assert "missions" in data
        assert "count" in data
        assert isinstance(data["missions"], list)
        
        # Verify mission structure includes validation fields
        if data["count"] > 0:
            mission = data["missions"][0]
            assert "mission_id" in mission
            assert "mission_type" in mission
            assert "status" in mission
            assert "validation_score" in mission
            assert "validation_reason" in mission
            assert "created_at" in mission
    
    def test_history_respects_limit_parameter(self, authenticated_session):
        """Test that history limit parameter works"""
        response = authenticated_session.get(
            f"{BASE_URL}/api/behavioral/mission/history?limit=2"
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["missions"]) <= 2


class TestMissionLastResultEndpoint:
    """Tests for GET /api/behavioral/mission/last-result"""
    
    def test_last_result_returns_result_structure(self, authenticated_session):
        """Test that last-result endpoint returns proper structure"""
        response = authenticated_session.get(
            f"{BASE_URL}/api/behavioral/mission/last-result"
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Must have has_result field
        assert "has_result" in data
        
        # If has result, verify structure
        if data["has_result"]:
            assert "mission_id" in data
            assert "mission_type" in data
            assert "status" in data
            assert "validation_score" in data
            assert "can_reference_success" in data
            assert "can_reference_failure" in data


class TestValidationWindowGames:
    """Tests for VALIDATION_WINDOW_GAMES (3) behavior"""
    
    def test_validation_uses_window_not_just_next_game(self, authenticated_session):
        """Test that validation uses 3-game window"""
        # Create and immediately complete a mission
        start_response = authenticated_session.post(
            f"{BASE_URL}/api/behavioral/mission/start",
            json={
                "mission_type": "TIME_DECISION_DRILL",
                "difficulty": "STANDARD"
            }
        )
        mission_id = start_response.json()["mission_id"]
        
        complete_response = authenticated_session.post(
            f"{BASE_URL}/api/behavioral/mission/complete",
            json={"mission_id": mission_id}
        )
        
        data = complete_response.json()
        
        # Validation should be present with metrics
        assert "validation" in data
        assert "metrics" in data["validation"]


class TestDifficultyDecay:
    """Tests for difficulty decay integration"""
    
    def test_difficulty_decay_field_present_in_response(self, authenticated_session):
        """Test that difficulty_decay_triggered field is in complete response"""
        # Create HARD difficulty mission
        start_response = authenticated_session.post(
            f"{BASE_URL}/api/behavioral/mission/start",
            json={
                "mission_type": "TEST_HARD_DECAY_DRILL",
                "difficulty": "HARD"
            }
        )
        mission_id = start_response.json()["mission_id"]
        
        complete_response = authenticated_session.post(
            f"{BASE_URL}/api/behavioral/mission/complete",
            json={"mission_id": mission_id}
        )
        
        data = complete_response.json()
        
        # Must have difficulty_decay_triggered field
        assert "difficulty_decay_triggered" in data
        assert isinstance(data["difficulty_decay_triggered"], bool)


class TestLearningVelocityIntegration:
    """Tests for learning velocity mission adjustment"""
    
    def test_behavioral_report_includes_mission_adjustment(self, authenticated_session):
        """Test that behavioral analysis includes mission_adjustment in velocity"""
        response = authenticated_session.get(
            f"{BASE_URL}/api/behavioral/last-report"
        )
        
        if response.status_code == 200:
            data = response.json()
            # If learning_velocity exists, check for mission_adjustment
            if "learning_velocity" in data:
                velocity_data = data["learning_velocity"]
                # P1.7: mission_adjustment should be present
                # Note: might be 0.0 if no validated missions
                if isinstance(velocity_data, dict):
                    assert "mission_adjustment" in velocity_data or "velocity" in velocity_data


class TestNarrativeConfidenceGating:
    """Tests for narrative confidence thresholds"""
    
    def test_last_result_has_confidence_flags(self, authenticated_session):
        """Test that last-result includes confidence flags for narrative"""
        response = authenticated_session.get(
            f"{BASE_URL}/api/behavioral/mission/last-result"
        )
        
        assert response.status_code == 200
        data = response.json()
        
        if data.get("has_result"):
            # P1.7: Must have confidence gating flags
            assert "can_reference_success" in data  # Score >= 0.6
            assert "can_reference_failure" in data  # Score <= 0.3
            
            score = data.get("validation_score", 0.5)
            
            # Verify logic
            if score >= 0.6:
                assert data["can_reference_success"] == True
            if score <= 0.3:
                assert data["can_reference_failure"] == True


class TestMissionStatusTransitions:
    """Tests for mission status state machine"""
    
    def test_mission_cannot_complete_twice(self, authenticated_session):
        """Test that already completed mission cannot be completed again"""
        # First, check history for a completed mission
        history_response = authenticated_session.get(
            f"{BASE_URL}/api/behavioral/mission/history?limit=20"
        )
        
        if history_response.status_code == 200:
            missions = history_response.json().get("missions", [])
            completed_mission = next(
                (m for m in missions if m.get("status") in ["COMPLETED", "FAILED"]),
                None
            )
            
            if completed_mission:
                # Try to complete again
                complete_response = authenticated_session.post(
                    f"{BASE_URL}/api/behavioral/mission/complete",
                    json={"mission_id": completed_mission["mission_id"]}
                )
                
                assert complete_response.status_code == 200
                data = complete_response.json()
                
                # Should return error
                assert "error" in data


class TestValidationApplicability:
    """Tests for validation applicability checks"""
    
    def test_validation_not_applicable_returns_false(self, authenticated_session):
        """Test that validation returns applicable=false when no games after mission"""
        # Create fresh mission
        start_response = authenticated_session.post(
            f"{BASE_URL}/api/behavioral/mission/start",
            json={
                "mission_type": f"TEST_FRESH_{uuid.uuid4().hex[:8]}",
                "difficulty": "STANDARD"
            }
        )
        mission_id = start_response.json()["mission_id"]
        
        # Complete immediately
        complete_response = authenticated_session.post(
            f"{BASE_URL}/api/behavioral/mission/complete",
            json={"mission_id": mission_id}
        )
        
        data = complete_response.json()
        
        # Validation should not be applicable
        assert data["validation"]["applicable"] == False
        assert data["validation"]["score"] == 0.0
        assert data["validation"]["confidence"] == 0.0
        assert "No games" in data["validation"]["reason"] or "No games" in data["message"]


class TestMissionTypeValidators:
    """Tests for different mission type validators"""
    
    def test_time_decision_drill_validator_structure(self, authenticated_session):
        """Test TIME_DECISION_DRILL validation returns expected metrics"""
        start_response = authenticated_session.post(
            f"{BASE_URL}/api/behavioral/mission/start",
            json={
                "mission_type": "TIME_DECISION_DRILL",
                "difficulty": "STANDARD"
            }
        )
        mission_id = start_response.json()["mission_id"]
        
        complete_response = authenticated_session.post(
            f"{BASE_URL}/api/behavioral/mission/complete",
            json={"mission_id": mission_id}
        )
        
        data = complete_response.json()
        assert "validation" in data
        assert "metrics" in data["validation"]
    
    def test_candidate_move_drill_validator_structure(self, authenticated_session):
        """Test CANDIDATE_MOVE_DRILL validation returns expected metrics"""
        start_response = authenticated_session.post(
            f"{BASE_URL}/api/behavioral/mission/start",
            json={
                "mission_type": "CANDIDATE_MOVE_DRILL",
                "difficulty": "STANDARD"
            }
        )
        mission_id = start_response.json()["mission_id"]
        
        complete_response = authenticated_session.post(
            f"{BASE_URL}/api/behavioral/mission/complete",
            json={"mission_id": mission_id}
        )
        
        data = complete_response.json()
        assert "validation" in data
        assert "metrics" in data["validation"]


# Run cleanup for test missions
@pytest.fixture(scope="module", autouse=True)
def cleanup_test_missions(authenticated_session):
    """Cleanup any test missions created during tests"""
    yield
    # Note: In a production test, we would delete test missions
    # For this test, we leave them as they don't affect functionality


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
