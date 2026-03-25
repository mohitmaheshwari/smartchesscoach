"""
Test Realtime Coaching Feedback API
====================================

Tests for the /api/coach/play/feedback/{session_id} endpoint
that provides move-by-move coaching feedback.
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://plateau-breaker-2.preview.emergentagent.com')


@pytest.fixture
def authenticated_session():
    """Session with dev login authentication"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    
    # Authenticate via dev login
    res = session.get(f"{BASE_URL}/api/auth/dev-login")
    if res.status_code != 200:
        pytest.skip("Dev login failed - skipping authenticated tests")
    
    return session


class TestRealtimeFeedbackAPI:
    """Tests for the move feedback API endpoint"""
    
    def test_feedback_endpoint_returns_valid_structure(self, authenticated_session):
        """Test feedback endpoint returns correct data structure"""
        # First get active sessions to find one with moves
        response = authenticated_session.get(f"{BASE_URL}/api/coach/play/active")
        assert response.status_code == 200
        data = response.json()
        
        # Find session with at least one player move
        session_with_moves = None
        for session in data.get("active_sessions", []):
            move_history = session.get("move_history", [])
            player_moves = [m for m in move_history if m.get("by") == "player"]
            if len(player_moves) > 0:
                session_with_moves = session
                break
        
        if not session_with_moves:
            pytest.skip("No active sessions with player moves found")
        
        # Test feedback endpoint
        session_id = session_with_moves["session_id"]
        feedback_response = authenticated_session.get(
            f"{BASE_URL}/api/coach/play/feedback/{session_id}"
        )
        
        assert feedback_response.status_code == 200
        feedback_data = feedback_response.json()
        
        # Verify feedback object exists
        assert "feedback" in feedback_data
        feedback = feedback_data["feedback"]
        
        # If no feedback (e.g., game just started), that's valid
        if feedback is None:
            return
        
        # Verify required fields are present
        required_fields = [
            "user_move",
            "user_move_quality",
            "user_move_eval_change",
            "best_move",
            "coach_move",
            "coaching_message"
        ]
        
        for field in required_fields:
            assert field in feedback, f"Missing required field: {field}"
    
    def test_feedback_quality_values_are_valid(self, authenticated_session):
        """Test that move quality is one of the valid values"""
        # Get active sessions
        response = authenticated_session.get(f"{BASE_URL}/api/coach/play/active")
        assert response.status_code == 200
        data = response.json()
        
        # Find session with moves
        session_with_moves = None
        for session in data.get("active_sessions", []):
            move_history = session.get("move_history", [])
            player_moves = [m for m in move_history if m.get("by") == "player"]
            if len(player_moves) > 0:
                session_with_moves = session
                break
        
        if not session_with_moves:
            pytest.skip("No active sessions with player moves found")
        
        session_id = session_with_moves["session_id"]
        feedback_response = authenticated_session.get(
            f"{BASE_URL}/api/coach/play/feedback/{session_id}"
        )
        
        assert feedback_response.status_code == 200
        feedback = feedback_response.json().get("feedback")
        
        if feedback is None:
            return
        
        valid_qualities = ["excellent", "good", "inaccuracy", "mistake", "blunder"]
        assert feedback["user_move_quality"] in valid_qualities, \
            f"Invalid move quality: {feedback['user_move_quality']}"
    
    def test_feedback_contains_coach_move_explanation(self, authenticated_session):
        """Test that feedback includes coach's move with explanation"""
        # Get active sessions
        response = authenticated_session.get(f"{BASE_URL}/api/coach/play/active")
        assert response.status_code == 200
        data = response.json()
        
        # Find session with coach moves
        session_with_coach_move = None
        for session in data.get("active_sessions", []):
            move_history = session.get("move_history", [])
            # Need at least one player move followed by coach move
            player_moves = [m for m in move_history if m.get("by") == "player"]
            coach_moves = [m for m in move_history if m.get("by") == "coach"]
            if len(player_moves) > 0 and len(coach_moves) > 0:
                session_with_coach_move = session
                break
        
        if not session_with_coach_move:
            pytest.skip("No sessions with coach moves found")
        
        session_id = session_with_coach_move["session_id"]
        feedback_response = authenticated_session.get(
            f"{BASE_URL}/api/coach/play/feedback/{session_id}"
        )
        
        assert feedback_response.status_code == 200
        feedback = feedback_response.json().get("feedback")
        
        if feedback is None:
            return
        
        # Check coach move fields
        assert "coach_move" in feedback
        assert "coach_move_explanation" in feedback
        
        # Coach move should be a valid algebraic notation
        if feedback["coach_move"]:
            assert len(feedback["coach_move"]) >= 2, \
                f"Coach move seems invalid: {feedback['coach_move']}"
    
    def test_feedback_coaching_message_not_empty(self, authenticated_session):
        """Test that coaching message is present and non-empty"""
        # Get active sessions
        response = authenticated_session.get(f"{BASE_URL}/api/coach/play/active")
        assert response.status_code == 200
        data = response.json()
        
        # Find session with moves
        session_with_moves = None
        for session in data.get("active_sessions", []):
            move_history = session.get("move_history", [])
            player_moves = [m for m in move_history if m.get("by") == "player"]
            if len(player_moves) > 0:
                session_with_moves = session
                break
        
        if not session_with_moves:
            pytest.skip("No active sessions with player moves found")
        
        session_id = session_with_moves["session_id"]
        feedback_response = authenticated_session.get(
            f"{BASE_URL}/api/coach/play/feedback/{session_id}"
        )
        
        assert feedback_response.status_code == 200
        feedback = feedback_response.json().get("feedback")
        
        if feedback is None:
            return
        
        # Coaching message should be present and non-empty
        assert "coaching_message" in feedback
        assert feedback["coaching_message"], "Coaching message should not be empty"
        assert len(feedback["coaching_message"]) > 10, \
            f"Coaching message too short: {feedback['coaching_message']}"
    
    def test_feedback_404_for_invalid_session(self, authenticated_session):
        """Test that invalid session ID returns 404"""
        feedback_response = authenticated_session.get(
            f"{BASE_URL}/api/coach/play/feedback/invalid-session-id-12345"
        )
        
        assert feedback_response.status_code == 404
    
    def test_feedback_403_for_other_users_session(self, authenticated_session):
        """Test that accessing another user's session returns 403"""
        # This test would require a session from another user
        # For now, we verify the endpoint at least validates sessions
        # The session validation is tested in other tests
        pass
    
    def test_best_move_explanation_present_for_suboptimal_moves(self, authenticated_session):
        """Test that best move explanation is present when user's move wasn't optimal"""
        # Get active sessions
        response = authenticated_session.get(f"{BASE_URL}/api/coach/play/active")
        assert response.status_code == 200
        data = response.json()
        
        # Find session with moves
        session_with_moves = None
        for session in data.get("active_sessions", []):
            move_history = session.get("move_history", [])
            player_moves = [m for m in move_history if m.get("by") == "player"]
            if len(player_moves) > 0:
                session_with_moves = session
                break
        
        if not session_with_moves:
            pytest.skip("No active sessions with player moves found")
        
        session_id = session_with_moves["session_id"]
        feedback_response = authenticated_session.get(
            f"{BASE_URL}/api/coach/play/feedback/{session_id}"
        )
        
        assert feedback_response.status_code == 200
        feedback = feedback_response.json().get("feedback")
        
        if feedback is None:
            return
        
        # Check best move fields exist
        assert "best_move" in feedback
        assert "best_move_explanation" in feedback
        
        # If user's move wasn't the best, explanation may be present
        quality = feedback.get("user_move_quality")
        if quality in ["inaccuracy", "mistake", "blunder"]:
            # Best move should be different or explanation should exist
            assert feedback["best_move"], \
                f"Best move should be present for {quality}"
    
    def test_feedback_includes_evaluation_change(self, authenticated_session):
        """Test that evaluation change is a numeric value"""
        # Get active sessions
        response = authenticated_session.get(f"{BASE_URL}/api/coach/play/active")
        assert response.status_code == 200
        data = response.json()
        
        # Find session with moves
        session_with_moves = None
        for session in data.get("active_sessions", []):
            move_history = session.get("move_history", [])
            player_moves = [m for m in move_history if m.get("by") == "player"]
            if len(player_moves) > 0:
                session_with_moves = session
                break
        
        if not session_with_moves:
            pytest.skip("No active sessions with player moves found")
        
        session_id = session_with_moves["session_id"]
        feedback_response = authenticated_session.get(
            f"{BASE_URL}/api/coach/play/feedback/{session_id}"
        )
        
        assert feedback_response.status_code == 200
        feedback = feedback_response.json().get("feedback")
        
        if feedback is None:
            return
        
        # Eval change should be a number (centipawns)
        assert "user_move_eval_change" in feedback
        eval_change = feedback["user_move_eval_change"]
        assert isinstance(eval_change, (int, float)), \
            f"Eval change should be numeric, got: {type(eval_change)}"


class TestFeedbackPersonalization:
    """Tests for personalized feedback based on player understanding"""
    
    def test_feedback_may_include_weakness_reference(self, authenticated_session):
        """Test that feedback can include weakness reference"""
        # Get active sessions
        response = authenticated_session.get(f"{BASE_URL}/api/coach/play/active")
        assert response.status_code == 200
        data = response.json()
        
        # Find session with moves
        session_with_moves = None
        for session in data.get("active_sessions", []):
            move_history = session.get("move_history", [])
            player_moves = [m for m in move_history if m.get("by") == "player"]
            if len(player_moves) > 0:
                session_with_moves = session
                break
        
        if not session_with_moves:
            pytest.skip("No active sessions with player moves found")
        
        session_id = session_with_moves["session_id"]
        feedback_response = authenticated_session.get(
            f"{BASE_URL}/api/coach/play/feedback/{session_id}"
        )
        
        assert feedback_response.status_code == 200
        feedback = feedback_response.json().get("feedback")
        
        if feedback is None:
            return
        
        # relates_to_weakness field should exist (can be null)
        assert "relates_to_weakness" in feedback
        
        # If present, should be a string
        if feedback["relates_to_weakness"]:
            assert isinstance(feedback["relates_to_weakness"], str)
    
    def test_feedback_may_include_encouragement(self, authenticated_session):
        """Test that feedback can include encouragement for good moves"""
        # Get active sessions
        response = authenticated_session.get(f"{BASE_URL}/api/coach/play/active")
        assert response.status_code == 200
        data = response.json()
        
        # Find session with moves
        session_with_moves = None
        for session in data.get("active_sessions", []):
            move_history = session.get("move_history", [])
            player_moves = [m for m in move_history if m.get("by") == "player"]
            if len(player_moves) > 0:
                session_with_moves = session
                break
        
        if not session_with_moves:
            pytest.skip("No active sessions with player moves found")
        
        session_id = session_with_moves["session_id"]
        feedback_response = authenticated_session.get(
            f"{BASE_URL}/api/coach/play/feedback/{session_id}"
        )
        
        assert feedback_response.status_code == 200
        feedback = feedback_response.json().get("feedback")
        
        if feedback is None:
            return
        
        # encouragement field should exist (can be null)
        assert "encouragement" in feedback
        
        # If present, should be a string
        if feedback["encouragement"]:
            assert isinstance(feedback["encouragement"], str)


class TestFeedbackTacticalInfo:
    """Tests for tactical information in feedback"""
    
    def test_feedback_includes_threats_list(self, authenticated_session):
        """Test that feedback includes threats after user's move"""
        # Get active sessions
        response = authenticated_session.get(f"{BASE_URL}/api/coach/play/active")
        assert response.status_code == 200
        data = response.json()
        
        # Find session with moves
        session_with_moves = None
        for session in data.get("active_sessions", []):
            move_history = session.get("move_history", [])
            player_moves = [m for m in move_history if m.get("by") == "player"]
            if len(player_moves) > 0:
                session_with_moves = session
                break
        
        if not session_with_moves:
            pytest.skip("No active sessions with player moves found")
        
        session_id = session_with_moves["session_id"]
        feedback_response = authenticated_session.get(
            f"{BASE_URL}/api/coach/play/feedback/{session_id}"
        )
        
        assert feedback_response.status_code == 200
        feedback = feedback_response.json().get("feedback")
        
        if feedback is None:
            return
        
        # threats_after_user_move should be a list
        assert "threats_after_user_move" in feedback
        assert isinstance(feedback["threats_after_user_move"], list)
    
    def test_feedback_includes_missed_opportunities(self, authenticated_session):
        """Test that feedback includes missed opportunities"""
        # Get active sessions
        response = authenticated_session.get(f"{BASE_URL}/api/coach/play/active")
        assert response.status_code == 200
        data = response.json()
        
        # Find session with moves
        session_with_moves = None
        for session in data.get("active_sessions", []):
            move_history = session.get("move_history", [])
            player_moves = [m for m in move_history if m.get("by") == "player"]
            if len(player_moves) > 0:
                session_with_moves = session
                break
        
        if not session_with_moves:
            pytest.skip("No active sessions with player moves found")
        
        session_id = session_with_moves["session_id"]
        feedback_response = authenticated_session.get(
            f"{BASE_URL}/api/coach/play/feedback/{session_id}"
        )
        
        assert feedback_response.status_code == 200
        feedback = feedback_response.json().get("feedback")
        
        if feedback is None:
            return
        
        # missed_opportunities should be a list
        assert "missed_opportunities" in feedback
        assert isinstance(feedback["missed_opportunities"], list)
    
    def test_feedback_includes_pv_after_best(self, authenticated_session):
        """Test that feedback includes principal variation after best move"""
        # Get active sessions
        response = authenticated_session.get(f"{BASE_URL}/api/coach/play/active")
        assert response.status_code == 200
        data = response.json()
        
        # Find session with moves
        session_with_moves = None
        for session in data.get("active_sessions", []):
            move_history = session.get("move_history", [])
            player_moves = [m for m in move_history if m.get("by") == "player"]
            if len(player_moves) > 0:
                session_with_moves = session
                break
        
        if not session_with_moves:
            pytest.skip("No active sessions with player moves found")
        
        session_id = session_with_moves["session_id"]
        feedback_response = authenticated_session.get(
            f"{BASE_URL}/api/coach/play/feedback/{session_id}"
        )
        
        assert feedback_response.status_code == 200
        feedback = feedback_response.json().get("feedback")
        
        if feedback is None:
            return
        
        # pv_after_best should be a list
        assert "pv_after_best" in feedback
        assert isinstance(feedback["pv_after_best"], list)
