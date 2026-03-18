"""
Test trigger-coach-move API endpoint

Tests the POST /api/coach/play/trigger-coach-move endpoint which is used
when resuming a game that was interrupted during coach's turn.

Tests:
1. Trigger coach move when it's coach's turn (successful path)
2. Trigger when it's already player's turn (returns success with message)
3. Trigger with non-existent session (404)
4. Trigger without session_id (400)
5. Trigger on inactive session (400)
6. SAN to UCI move conversion works correctly
"""
import pytest
import uuid

BASE_URL = "https://chess-lab-sync.preview.emergentagent.com"


class TestTriggerCoachMoveEndpoint:
    """Test POST /api/coach/play/trigger-coach-move"""

    @pytest.fixture
    def active_white_session(self, authenticated_session):
        """Create an active session as white (player moves first)"""
        response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/start",
            json={"user_color": "white", "time_control": "15+10"}
        )
        assert response.status_code == 200
        data = response.json()
        session_id = data["session_id"]
        
        yield {"session_id": session_id, "session": authenticated_session}
        
        # Cleanup
        authenticated_session.post(
            f"{BASE_URL}/api/coach/play/end",
            json={"session_id": session_id, "reason": "resigned"}
        )

    @pytest.fixture
    def active_black_session(self, authenticated_session):
        """Create an active session as black (coach moves first)"""
        response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/start",
            json={"user_color": "black", "time_control": "15+10"}
        )
        assert response.status_code == 200
        data = response.json()
        session_id = data["session_id"]
        
        yield {"session_id": session_id, "session": authenticated_session}
        
        # Cleanup
        authenticated_session.post(
            f"{BASE_URL}/api/coach/play/end",
            json={"session_id": session_id, "reason": "resigned"}
        )

    def test_trigger_when_player_turn_returns_your_turn_message(self, active_white_session):
        """When it's player's turn, trigger should return 'already your turn'"""
        session_id = active_white_session["session_id"]
        session = active_white_session["session"]
        
        response = session.post(
            f"{BASE_URL}/api/coach/play/trigger-coach-move",
            json={"session_id": session_id}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert "already your turn" in data["message"].lower() or "your turn" in data["message"].lower()
        assert data["is_player_turn"] is True
        assert "current_fen" in data

    def test_trigger_after_player_move_coach_responds(self, active_white_session):
        """After player moves, trigger should make coach move"""
        session_id = active_white_session["session_id"]
        session = active_white_session["session"]
        
        # Make a player move first (e4)
        move_response = session.post(
            f"{BASE_URL}/api/coach/play/move",
            json={"session_id": session_id, "move": "e4"}
        )
        assert move_response.status_code == 200
        move_data = move_response.json()
        assert move_data["awaiting_coach"] is True
        
        # Now trigger coach move
        response = session.post(
            f"{BASE_URL}/api/coach/play/trigger-coach-move",
            json={"session_id": session_id}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert "coach_move" in data
        assert data["coach_move"] is not None
        assert data["is_player_turn"] is True
        assert data["current_fen"] != "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"
        assert "message" in data

    def test_trigger_without_session_id_returns_400(self, authenticated_session):
        """Missing session_id should return 400 error"""
        response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/trigger-coach-move",
            json={}
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "session_id" in data["detail"].lower() or "required" in data["detail"].lower()

    def test_trigger_with_nonexistent_session_returns_404(self, authenticated_session):
        """Non-existent session should return 404"""
        fake_session_id = f"nonexistent_{uuid.uuid4()}"
        
        response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/trigger-coach-move",
            json={"session_id": fake_session_id}
        )
        
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()

    def test_trigger_on_inactive_session_returns_error(self, authenticated_session):
        """Triggering on completed/resigned session should return error"""
        # First create and end a session
        start_response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/start",
            json={"user_color": "white", "time_control": "15+10"}
        )
        assert start_response.status_code == 200
        session_id = start_response.json()["session_id"]
        
        # End the session
        end_response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/end",
            json={"session_id": session_id, "reason": "resigned"}
        )
        assert end_response.status_code == 200
        
        # Now try to trigger coach move on ended session
        response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/trigger-coach-move",
            json={"session_id": session_id}
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "not active" in data["detail"].lower() or "active" in data["detail"].lower()

    def test_trigger_returns_valid_fen_and_san_move(self, active_white_session):
        """Verify the returned FEN and move format are valid"""
        session_id = active_white_session["session_id"]
        session = active_white_session["session"]
        
        # Make player move
        session.post(
            f"{BASE_URL}/api/coach/play/move",
            json={"session_id": session_id, "move": "d4"}
        )
        
        # Trigger coach move
        response = session.post(
            f"{BASE_URL}/api/coach/play/trigger-coach-move",
            json={"session_id": session_id}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify FEN is valid format (should contain standard FEN elements)
        fen = data["current_fen"]
        fen_parts = fen.split(" ")
        assert len(fen_parts) == 6  # Valid FEN has 6 parts
        assert fen_parts[1] in ["w", "b"]  # Turn indicator
        
        # Coach move should be in SAN format (e.g., e5, Nf6, d6)
        coach_move = data["coach_move"]
        assert coach_move is not None
        assert len(coach_move) >= 2  # At least 2 chars for SAN

    def test_multiple_trigger_calls_idempotent(self, active_white_session):
        """Multiple trigger calls when already player's turn should be safe"""
        session_id = active_white_session["session_id"]
        session = active_white_session["session"]
        
        # Make player move
        session.post(
            f"{BASE_URL}/api/coach/play/move",
            json={"session_id": session_id, "move": "e4"}
        )
        
        # First trigger
        response1 = session.post(
            f"{BASE_URL}/api/coach/play/trigger-coach-move",
            json={"session_id": session_id}
        )
        assert response1.status_code == 200
        data1 = response1.json()
        
        # Second trigger (should say it's player's turn)
        response2 = session.post(
            f"{BASE_URL}/api/coach/play/trigger-coach-move",
            json={"session_id": session_id}
        )
        assert response2.status_code == 200
        data2 = response2.json()
        
        # Both should succeed, second should say it's player's turn
        assert data1["success"] is True
        assert data2["success"] is True
        assert data2["is_player_turn"] is True

    def test_trigger_updates_move_history(self, active_white_session):
        """Verify coach move is recorded in session's move history"""
        session_id = active_white_session["session_id"]
        session = active_white_session["session"]
        
        # Make player move
        session.post(
            f"{BASE_URL}/api/coach/play/move",
            json={"session_id": session_id, "move": "Nf3"}
        )
        
        # Trigger coach move
        trigger_response = session.post(
            f"{BASE_URL}/api/coach/play/trigger-coach-move",
            json={"session_id": session_id}
        )
        assert trigger_response.status_code == 200
        coach_move = trigger_response.json()["coach_move"]
        
        # Get session state
        state_response = session.get(
            f"{BASE_URL}/api/coach/play/state/{session_id}"
        )
        assert state_response.status_code == 200
        state = state_response.json()
        
        # Verify move history contains the coach move
        move_history = state["session"]["move_history"]
        assert len(move_history) >= 2  # Player move + coach move
        
        # Find the coach move in history
        coach_moves = [m for m in move_history if m.get("by") == "coach"]
        assert len(coach_moves) >= 1
        
        # The last coach move should match what trigger returned
        last_coach_move = coach_moves[-1]
        assert last_coach_move["move"] == coach_move
        assert "uci" in last_coach_move  # UCI format should also be recorded


class TestTriggerCoachMoveAsBlack:
    """Test trigger-coach-move behavior when playing as black"""

    @pytest.fixture
    def black_session_after_player_move(self, authenticated_session):
        """Create session as black, make player move so it's coach's turn"""
        # Start as black
        response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/start",
            json={"user_color": "black", "time_control": "15+10"}
        )
        assert response.status_code == 200
        session_id = response.json()["session_id"]
        
        # Make player move (as black)
        move_response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/move",
            json={"session_id": session_id, "move": "e5"}
        )
        
        yield {"session_id": session_id, "session": authenticated_session}
        
        # Cleanup
        authenticated_session.post(
            f"{BASE_URL}/api/coach/play/end",
            json={"session_id": session_id, "reason": "resigned"}
        )

    def test_trigger_as_black_when_coach_turn(self, black_session_after_player_move):
        """When playing as black and coach (white) needs to move"""
        session_id = black_session_after_player_move["session_id"]
        session = black_session_after_player_move["session"]
        
        # Trigger should work
        response = session.post(
            f"{BASE_URL}/api/coach/play/trigger-coach-move",
            json={"session_id": session_id}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
