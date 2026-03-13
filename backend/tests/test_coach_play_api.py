"""
Test Coach Play API endpoints - P2 Play With Coach Step 1

Tests:
- POST /api/coach/play/start - Create session with color and time control
- POST /api/coach/play/move - Player move and coach response
- GET /api/coach/play/state/{session_id} - Get session state
- POST /api/coach/play/end - End session (resign)
- GET /api/coach/play/active - List active sessions
- GET /api/coach/play/history - List completed sessions
"""
import pytest
import uuid

BASE_URL = "https://socratic-chess.preview.emergentagent.com"


class TestCoachPlayStart:
    """Test POST /api/coach/play/start"""

    def test_start_session_as_white(self, authenticated_session):
        """Start a game as white - player moves first"""
        response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/start",
            json={"user_color": "white", "time_control": "15+10"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert "session_id" in data
        assert "session" in data
        assert data["current_fen"] == "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        assert data["is_player_turn"] is True
        assert data["session"]["user_color"] == "white"
        assert data["session"]["status"] == "active"
        
        # Cleanup - resign the game
        authenticated_session.post(
            f"{BASE_URL}/api/coach/play/end",
            json={"session_id": data["session_id"], "reason": "resigned"}
        )

    def test_start_session_as_black(self, authenticated_session):
        """Start a game as black - coach (white) moves first"""
        response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/start",
            json={"user_color": "black", "time_control": "10+5"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert data["session"]["user_color"] == "black"
        # After coach's first move, it should NOT be starting position
        assert data["current_fen"] != "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        # Now it's player's (black's) turn
        assert data["is_player_turn"] is False or len(data["session"]["move_history"]) > 0
        
        # Cleanup
        authenticated_session.post(
            f"{BASE_URL}/api/coach/play/end",
            json={"session_id": data["session_id"], "reason": "resigned"}
        )

    def test_start_session_invalid_color(self, authenticated_session):
        """Invalid color should return 400"""
        response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/start",
            json={"user_color": "red", "time_control": "15+10"}
        )
        
        assert response.status_code == 400

    def test_start_session_different_time_controls(self, authenticated_session):
        """Test various time control formats"""
        for tc in ["3+2", "10+5", "15+10"]:
            response = authenticated_session.post(
                f"{BASE_URL}/api/coach/play/start",
                json={"user_color": "white", "time_control": tc}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["session"]["time_control"] == tc
            
            # Cleanup
            authenticated_session.post(
                f"{BASE_URL}/api/coach/play/end",
                json={"session_id": data["session_id"], "reason": "resigned"}
            )


class TestCoachPlayMove:
    """Test POST /api/coach/play/move"""

    @pytest.fixture
    def active_session(self, authenticated_session):
        """Create an active session for testing moves"""
        response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/start",
            json={"user_color": "white", "time_control": "15+10"}
        )
        data = response.json()
        yield data["session_id"], authenticated_session
        
        # Cleanup
        authenticated_session.post(
            f"{BASE_URL}/api/coach/play/end",
            json={"session_id": data["session_id"], "reason": "resigned"}
        )

    def test_make_valid_move_e4(self, active_session):
        """Make a valid opening move e4"""
        session_id, session = active_session
        
        response = session.post(
            f"{BASE_URL}/api/coach/play/move",
            json={"session_id": session_id, "move": "e4", "time_spent": 2.5}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert "session" in data
        # Coach should have responded (unless game is over)
        if not data.get("game_over"):
            assert "coach_move" in data
            assert data["coach_move"] is not None

    def test_make_valid_move_sequence(self, active_session):
        """Play a few moves in sequence"""
        session_id, session = active_session
        
        # Move 1: e4
        response = session.post(
            f"{BASE_URL}/api/coach/play/move",
            json={"session_id": session_id, "move": "e4", "time_spent": 1.0}
        )
        assert response.status_code == 200
        assert response.json()["success"] is True
        
        # Move 2: d4 (if coach played something like e5 or c5)
        response = session.post(
            f"{BASE_URL}/api/coach/play/move",
            json={"session_id": session_id, "move": "d4", "time_spent": 1.5}
        )
        assert response.status_code == 200

    def test_make_invalid_move(self, active_session):
        """Invalid move should return error"""
        session_id, session = active_session
        
        response = session.post(
            f"{BASE_URL}/api/coach/play/move",
            json={"session_id": session_id, "move": "Ke9", "time_spent": 1.0}
        )
        
        assert response.status_code == 400

    def test_make_illegal_move(self, active_session):
        """Illegal but syntactically correct move should fail"""
        session_id, session = active_session
        
        # Can't move knight to d4 on first move
        response = session.post(
            f"{BASE_URL}/api/coach/play/move",
            json={"session_id": session_id, "move": "Nd4", "time_spent": 1.0}
        )
        
        assert response.status_code == 400

    def test_move_without_session_id(self, authenticated_session):
        """Missing session_id should return 400"""
        response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/move",
            json={"move": "e4"}
        )
        
        assert response.status_code == 400

    def test_move_invalid_session(self, authenticated_session):
        """Invalid session_id should return 404"""
        response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/move",
            json={"session_id": str(uuid.uuid4()), "move": "e4"}
        )
        
        assert response.status_code == 404


class TestCoachPlayState:
    """Test GET /api/coach/play/state/{session_id}"""

    def test_get_session_state(self, authenticated_session):
        """Get state of an active session"""
        # First create a session
        start_response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/start",
            json={"user_color": "white", "time_control": "15+10"}
        )
        session_id = start_response.json()["session_id"]
        
        # Get the state
        response = authenticated_session.get(
            f"{BASE_URL}/api/coach/play/state/{session_id}"
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "session" in data
        assert "current_fen" in data
        assert "is_player_turn" in data
        assert "legal_moves" in data
        assert "move_count" in data
        assert "game_over" in data
        
        # At start, white to move
        assert data["is_player_turn"] is True
        assert "e4" in data["legal_moves"]
        assert "d4" in data["legal_moves"]
        assert "Nf3" in data["legal_moves"]
        
        # Cleanup
        authenticated_session.post(
            f"{BASE_URL}/api/coach/play/end",
            json={"session_id": session_id, "reason": "resigned"}
        )

    def test_get_nonexistent_session(self, authenticated_session):
        """Invalid session_id returns 404"""
        response = authenticated_session.get(
            f"{BASE_URL}/api/coach/play/state/{str(uuid.uuid4())}"
        )
        
        assert response.status_code == 404


class TestCoachPlayEnd:
    """Test POST /api/coach/play/end"""

    def test_resign_session(self, authenticated_session):
        """Resign an active session"""
        # Start a session
        start_response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/start",
            json={"user_color": "white", "time_control": "15+10"}
        )
        session_id = start_response.json()["session_id"]
        
        # Resign
        response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/end",
            json={"session_id": session_id, "reason": "resigned"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert data["session"]["status"] == "resigned"
        assert data["session"]["result"] == "loss"
        
        # Should have summary
        assert "summary" in data
        summary = data["summary"]
        assert "session_id" in summary
        assert "result" in summary
        assert "total_moves" in summary
        assert "player_moves" in summary

    def test_end_nonexistent_session(self, authenticated_session):
        """Cannot end nonexistent session"""
        response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/end",
            json={"session_id": str(uuid.uuid4()), "reason": "resigned"}
        )
        
        assert response.status_code == 404

    def test_cannot_end_already_ended_session(self, authenticated_session):
        """Cannot resign a session that's already ended"""
        # Start and resign
        start_response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/start",
            json={"user_color": "white", "time_control": "15+10"}
        )
        session_id = start_response.json()["session_id"]
        
        authenticated_session.post(
            f"{BASE_URL}/api/coach/play/end",
            json={"session_id": session_id, "reason": "resigned"}
        )
        
        # Try to resign again
        response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/end",
            json={"session_id": session_id, "reason": "resigned"}
        )
        
        assert response.status_code == 400


class TestCoachPlayActiveSessions:
    """Test GET /api/coach/play/active"""

    def test_get_active_sessions_empty(self, authenticated_session):
        """Returns empty when no active sessions"""
        response = authenticated_session.get(
            f"{BASE_URL}/api/coach/play/active"
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "active_sessions" in data
        assert "count" in data

    def test_get_active_sessions_with_one_active(self, authenticated_session):
        """Returns active session after starting one"""
        # Start a session
        start_response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/start",
            json={"user_color": "white", "time_control": "15+10"}
        )
        session_id = start_response.json()["session_id"]
        
        # Check active sessions
        response = authenticated_session.get(
            f"{BASE_URL}/api/coach/play/active"
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["count"] >= 1
        session_ids = [s["session_id"] for s in data["active_sessions"]]
        assert session_id in session_ids
        
        # Cleanup
        authenticated_session.post(
            f"{BASE_URL}/api/coach/play/end",
            json={"session_id": session_id, "reason": "resigned"}
        )


class TestCoachPlayHistory:
    """Test GET /api/coach/play/history"""

    def test_get_history(self, authenticated_session):
        """Get history after completing a session"""
        # Start and resign a session to create history
        start_response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/start",
            json={"user_color": "white", "time_control": "15+10"}
        )
        session_id = start_response.json()["session_id"]
        
        authenticated_session.post(
            f"{BASE_URL}/api/coach/play/end",
            json={"session_id": session_id, "reason": "resigned"}
        )
        
        # Get history
        response = authenticated_session.get(
            f"{BASE_URL}/api/coach/play/history"
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "sessions" in data
        assert "stats" in data
        assert "total" in data["stats"]
        assert "wins" in data["stats"]
        assert "losses" in data["stats"]
        assert "draws" in data["stats"]

    def test_history_limit_param(self, authenticated_session):
        """History respects limit parameter"""
        response = authenticated_session.get(
            f"{BASE_URL}/api/coach/play/history?limit=5"
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["sessions"]) <= 5
