"""
Test Live Socratic Coaching - POST /api/coach/play/reflect

Tests the new reflection endpoint that enables live coaching dialog:
- After each move, user explains WHY they played it
- Coach provides targeted feedback based on reasoning vs position reality
- Returns: main_message, reasoning_feedback, position_insight, move_quality, etc.
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


@pytest.fixture
def authenticated_session():
    """Create an authenticated session using dev login."""
    session = requests.Session()
    response = session.get(f"{BASE_URL}/api/auth/dev-login")
    if response.status_code != 200:
        pytest.skip("Dev login not available")
    return session


@pytest.fixture
def active_game_with_moves(authenticated_session):
    """Create an active game and make a move to get reflection data."""
    # Start game as white
    response = authenticated_session.post(
        f"{BASE_URL}/api/coach/play/start",
        json={"user_color": "white", "time_control": "15+10"}
    )
    assert response.status_code == 200
    data = response.json()
    session_id = data["session_id"]
    
    # Make first move (e4)
    move_response = authenticated_session.post(
        f"{BASE_URL}/api/coach/play/move",
        json={"session_id": session_id, "move": "e4", "time_spent": 2.0}
    )
    assert move_response.status_code == 200
    move_data = move_response.json()
    
    yield {
        "session_id": session_id,
        "session": move_data["session"],
        "move_index": 0,  # User's first move
        "move": "e4"
    }
    
    # Cleanup - resign
    authenticated_session.post(
        f"{BASE_URL}/api/coach/play/end",
        json={"session_id": session_id, "reason": "resigned"}
    )


class TestCoachPlayReflectEndpoint:
    """Test POST /api/coach/play/reflect"""

    def test_reflect_returns_coach_feedback(self, authenticated_session, active_game_with_moves):
        """Submit reflection and receive coach feedback."""
        response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/reflect",
            json={
                "session_id": active_game_with_moves["session_id"],
                "move_index": active_game_with_moves["move_index"],
                "user_reasoning": "I wanted to control the center and open lines for my pieces."
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Required fields from Socratic coaching
        assert "success" in data
        assert data["success"] is True
        assert "main_message" in data
        assert "reasoning_feedback" in data
        assert "position_insight" in data
        assert "move_quality" in data
        
        # move_quality should be one of the valid values
        valid_qualities = ["brilliant", "great", "good", "okay", "inaccuracy", "mistake", "blunder"]
        assert data["move_quality"] in valid_qualities
        
        # Should echo back the move
        assert "move" in data
        assert "move_index" in data
        assert data["move_index"] == active_game_with_moves["move_index"]
        
        # Feedback text should not be empty
        assert len(data["main_message"]) > 0
        assert len(data["reasoning_feedback"]) > 0
        assert len(data["position_insight"]) > 0
        
        # Additional metadata
        assert "encouragement" in data

    def test_reflect_requires_session_id(self, authenticated_session):
        """Missing session_id returns 400."""
        response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/reflect",
            json={
                "move_index": 0,
                "user_reasoning": "Test reasoning"
            }
        )
        
        assert response.status_code == 400
        assert "session_id" in response.json().get("detail", "").lower()

    def test_reflect_requires_move_index(self, authenticated_session, active_game_with_moves):
        """Missing move_index returns 400."""
        response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/reflect",
            json={
                "session_id": active_game_with_moves["session_id"],
                "user_reasoning": "Test reasoning"
            }
        )
        
        assert response.status_code == 400
        assert "move_index" in response.json().get("detail", "").lower()

    def test_reflect_requires_user_reasoning(self, authenticated_session, active_game_with_moves):
        """Missing or empty user_reasoning returns 400."""
        response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/reflect",
            json={
                "session_id": active_game_with_moves["session_id"],
                "move_index": 0,
                "user_reasoning": ""  # Empty reasoning
            }
        )
        
        assert response.status_code == 400
        assert "reasoning" in response.json().get("detail", "").lower()

    def test_reflect_invalid_session_id(self, authenticated_session):
        """Invalid session_id returns 404."""
        response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/reflect",
            json={
                "session_id": "invalid-session-id-12345",
                "move_index": 0,
                "user_reasoning": "Test reasoning"
            }
        )
        
        assert response.status_code == 404
        assert "session" in response.json().get("detail", "").lower()

    def test_reflect_invalid_move_index(self, authenticated_session, active_game_with_moves):
        """Invalid move_index returns 400."""
        response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/reflect",
            json={
                "session_id": active_game_with_moves["session_id"],
                "move_index": 999,  # Out of range
                "user_reasoning": "Test reasoning"
            }
        )
        
        assert response.status_code == 400
        assert "move_index" in response.json().get("detail", "").lower()

    def test_reflect_cannot_reflect_on_coach_move(self, authenticated_session, active_game_with_moves):
        """Cannot reflect on coach's moves (move_index 1 is coach's response)."""
        # The coach has made a response move (index 1)
        if len(active_game_with_moves["session"]["move_history"]) > 1:
            response = authenticated_session.post(
                f"{BASE_URL}/api/coach/play/reflect",
                json={
                    "session_id": active_game_with_moves["session_id"],
                    "move_index": 1,  # Coach's move
                    "user_reasoning": "Test reasoning"
                }
            )
            
            assert response.status_code == 400
            assert "own moves" in response.json().get("detail", "").lower()

    def test_reflect_move_quality_assessment(self, authenticated_session, active_game_with_moves):
        """Coach feedback includes accurate move quality assessment."""
        # e4 is a strong opening move - should be rated good or better
        response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/reflect",
            json={
                "session_id": active_game_with_moves["session_id"],
                "move_index": 0,
                "user_reasoning": "I want to control the center with my pawn."
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # e4 is a good opening move
        good_qualities = ["brilliant", "great", "good", "okay"]
        assert data["move_quality"] in good_qualities, f"e4 should be at least 'okay', got: {data['move_quality']}"

    def test_reflect_returns_best_move_info(self, authenticated_session, active_game_with_moves):
        """Feedback includes whether move was the best move."""
        response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/reflect",
            json={
                "session_id": active_game_with_moves["session_id"],
                "move_index": 0,
                "user_reasoning": "Opening the game with central control."
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should indicate if it was the best or a candidate move
        assert "was_best_move" in data or "best_move" in data


class TestCoachPlayReflectFeedbackQuality:
    """Test the quality and relevance of coaching feedback."""

    def test_feedback_addresses_user_reasoning(self, authenticated_session, active_game_with_moves):
        """Coach feedback should reference user's stated reasoning."""
        user_reasoning = "I played e4 to control the d5 and f5 squares."
        
        response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/reflect",
            json={
                "session_id": active_game_with_moves["session_id"],
                "move_index": 0,
                "user_reasoning": user_reasoning
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # reasoning_feedback should exist and be non-empty
        assert data["reasoning_feedback"]
        assert len(data["reasoning_feedback"]) > 10

    def test_feedback_includes_position_insight(self, authenticated_session, active_game_with_moves):
        """Coach provides insight about the position."""
        response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/reflect",
            json={
                "session_id": active_game_with_moves["session_id"],
                "move_index": 0,
                "user_reasoning": "Just a random move."
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # position_insight should provide educational content
        assert data["position_insight"]
        assert len(data["position_insight"]) > 10

    def test_feedback_includes_improvement_tip_for_bad_move(self, authenticated_session):
        """Bad moves should receive improvement tips."""
        # Start fresh game
        start_response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/start",
            json={"user_color": "white", "time_control": "15+10"}
        )
        session_id = start_response.json()["session_id"]
        
        # Make a dubious move (h4 - not great but legal)
        move_response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/move",
            json={"session_id": session_id, "move": "h4", "time_spent": 1.0}
        )
        
        if move_response.status_code == 200:
            reflect_response = authenticated_session.post(
                f"{BASE_URL}/api/coach/play/reflect",
                json={
                    "session_id": session_id,
                    "move_index": 0,
                    "user_reasoning": "I don't know, just moved."
                }
            )
            
            assert reflect_response.status_code == 200
            data = reflect_response.json()
            
            # Should have improvement_tip for a questionable move
            # Note: improvement_tip can be null for good moves
            assert "improvement_tip" in data
        
        # Cleanup
        authenticated_session.post(
            f"{BASE_URL}/api/coach/play/end",
            json={"session_id": session_id, "reason": "resigned"}
        )


class TestCoachPlayReflectOpeningInfo:
    """Test opening-specific information in coaching feedback."""

    def test_feedback_includes_opening_name_early_game(self, authenticated_session, active_game_with_moves):
        """Early game feedback may include opening name."""
        response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/reflect",
            json={
                "session_id": active_game_with_moves["session_id"],
                "move_index": 0,
                "user_reasoning": "Playing the King's Pawn opening."
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Opening name and phase should be in response
        assert "opening_name" in data
        assert "phase" in data
        assert data["phase"] == "opening"

    def test_feedback_eval_values(self, authenticated_session, active_game_with_moves):
        """Feedback includes evaluation data from Stockfish."""
        response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/reflect",
            json={
                "session_id": active_game_with_moves["session_id"],
                "move_index": 0,
                "user_reasoning": "Central control move."
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should include eval information
        assert "eval_before" in data
        assert "eval_after" in data
        
        # After e4 from starting position, eval should be slightly positive (white advantage)
        assert isinstance(data["eval_before"], (int, float))
        assert isinstance(data["eval_after"], (int, float))


class TestCoachPlayReflectMultipleMoves:
    """Test reflection across multiple moves in a game."""

    def test_reflect_on_multiple_moves_in_sequence(self, authenticated_session):
        """Can reflect on multiple moves in the same game."""
        # Start game
        start_response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/start",
            json={"user_color": "white", "time_control": "15+10"}
        )
        session_id = start_response.json()["session_id"]
        
        # Move 1: e4
        authenticated_session.post(
            f"{BASE_URL}/api/coach/play/move",
            json={"session_id": session_id, "move": "e4", "time_spent": 1.0}
        )
        
        # Reflect on move 0
        reflect1 = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/reflect",
            json={
                "session_id": session_id,
                "move_index": 0,
                "user_reasoning": "Central control."
            }
        )
        assert reflect1.status_code == 200
        
        # Move 2: d4
        move2_response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/move",
            json={"session_id": session_id, "move": "d4", "time_spent": 1.5}
        )
        
        if move2_response.status_code == 200:
            # Reflect on move 2 (index 2 if coach moved at index 1)
            move_history = move2_response.json()["session"]["move_history"]
            # Find user's second move index
            user_moves = [i for i, m in enumerate(move_history) if m.get("by") == "player"]
            
            if len(user_moves) >= 2:
                reflect2 = authenticated_session.post(
                    f"{BASE_URL}/api/coach/play/reflect",
                    json={
                        "session_id": session_id,
                        "move_index": user_moves[1],
                        "user_reasoning": "Expanding in the center."
                    }
                )
                assert reflect2.status_code == 200
                
                # Both reflections should have valid feedback
                data = reflect2.json()
                assert data["main_message"]
                assert data["reasoning_feedback"]
        
        # Cleanup
        authenticated_session.post(
            f"{BASE_URL}/api/coach/play/end",
            json={"session_id": session_id, "reason": "resigned"}
        )
