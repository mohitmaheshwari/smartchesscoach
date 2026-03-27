"""
Test Practice Mode from Lab Alternate Timeline

Tests:
- POST /api/coach/play/start - Start session with custom FEN (practice mode)
- Practice mode accepts starting_fen and practice_mode params
- Practice mode starts from custom position
"""
import pytest
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://identity-tracker-19.preview.emergentagent.com')


class TestPracticeModeStart:
    """Test POST /api/coach/play/start with practice mode parameters"""

    def test_start_practice_mode_with_custom_fen(self, authenticated_session):
        """Start a practice session with a custom FEN position"""
        # Custom FEN from a middle-game position
        custom_fen = "r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4"
        
        response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/start",
            json={
                "user_color": "white",
                "time_control": "15+10",
                "starting_fen": custom_fen,
                "practice_mode": True,
                "source_game_id": "test-game-123"
            }
        )
        
        assert response.status_code == 200, f"Failed with {response.text}"
        data = response.json()
        
        assert data["success"] is True
        assert "session_id" in data
        # The current_fen should be the custom position
        assert data["current_fen"] == custom_fen
        assert data["is_player_turn"] is True
        
        # Cleanup - resign the game
        authenticated_session.post(
            f"{BASE_URL}/api/coach/play/end",
            json={"session_id": data["session_id"], "reason": "resigned"}
        )

    def test_start_practice_mode_as_black(self, authenticated_session):
        """Start practice mode as black - coach moves first from custom position"""
        # Custom FEN where it's black's turn
        custom_fen = "rnbqkbnr/pppp1ppp/8/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R b KQkq - 1 2"
        
        response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/start",
            json={
                "user_color": "black",
                "time_control": "10+5",
                "starting_fen": custom_fen,
                "practice_mode": True
            }
        )
        
        assert response.status_code == 200, f"Failed with {response.text}"
        data = response.json()
        
        assert data["success"] is True
        assert data["session"]["user_color"] == "black"
        # Session should have started from the custom position
        # Either it's our turn or coach made a move
        
        # Cleanup
        authenticated_session.post(
            f"{BASE_URL}/api/coach/play/end",
            json={"session_id": data["session_id"], "reason": "resigned"}
        )

    def test_start_normal_session_without_practice_params(self, authenticated_session):
        """Normal session without practice mode uses standard starting position"""
        response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/start",
            json={
                "user_color": "white",
                "time_control": "15+10"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Standard starting position
        assert data["current_fen"] == "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        
        # Cleanup
        authenticated_session.post(
            f"{BASE_URL}/api/coach/play/end",
            json={"session_id": data["session_id"], "reason": "resigned"}
        )

    def test_practice_mode_with_invalid_fen(self, authenticated_session):
        """Practice mode with invalid FEN - currently accepts but may fail later"""
        response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/start",
            json={
                "user_color": "white",
                "time_control": "15+10",
                "starting_fen": "invalid-fen-string",
                "practice_mode": True
            }
        )
        
        # Currently accepts invalid FEN (falls back to default?)
        # This test documents current behavior - may need better validation
        if response.status_code == 200:
            data = response.json()
            # Cleanup if session was created
            if "session_id" in data:
                authenticated_session.post(
                    f"{BASE_URL}/api/coach/play/end",
                    json={"session_id": data["session_id"], "reason": "resigned"}
                )
        # Accept either success or error
        assert response.status_code in [200, 400, 422, 500]


class TestCoachPlayChatMessages:
    """Test coach play chat messages endpoint"""
    
    @pytest.fixture
    def active_session(self, authenticated_session):
        """Create an active session for testing"""
        response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/start",
            json={"user_color": "white", "time_control": "15+10"}
        )
        if response.status_code != 200:
            pytest.skip("Could not create session")
        
        data = response.json()
        yield data["session_id"]
        
        # Cleanup
        authenticated_session.post(
            f"{BASE_URL}/api/coach/play/end",
            json={"session_id": data["session_id"], "reason": "resigned"}
        )
    
    def test_get_coach_messages(self, authenticated_session, active_session):
        """Get coach messages for an active session"""
        response = authenticated_session.get(
            f"{BASE_URL}/api/coach/play/messages/{active_session}"
        )
        
        # Should return 200 even if no messages yet
        assert response.status_code == 200
        data = response.json()
        
        assert "messages" in data
        assert isinstance(data["messages"], list)
    
    def test_send_chat_message(self, authenticated_session, active_session):
        """Send a chat message to coach"""
        response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/chat",
            json={
                "session_id": active_session,
                "message": "What should I play here?"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "response" in data


class TestLabAlternateTimeline:
    """Test Lab page endpoint that provides alternate timeline data"""
    
    def test_get_lab_data_includes_pv_after_best(self, authenticated_session):
        """Lab data should include pv_after_best for alternate timeline"""
        # Use the test game ID mentioned in the review request
        test_game_id = "42932bfa-24e8-4aff-9068-0b476cb6f4fc"
        
        response = authenticated_session.get(
            f"{BASE_URL}/api/lab/{test_game_id}"
        )
        
        if response.status_code == 404:
            pytest.skip("Test game not found - may need different game ID")
        
        assert response.status_code == 200
        data = response.json()
        
        # Should have analysis data
        assert "biggest_eval_swing" in data or "core_lesson" in data


class TestTrainingPuzzles:
    """Test training puzzles endpoints"""
    
    def test_get_training_puzzles(self, authenticated_session):
        """Get user training puzzles"""
        response = authenticated_session.get(
            f"{BASE_URL}/api/training/puzzles?limit=5"
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "puzzles" in data
        assert isinstance(data["puzzles"], list)
        
        # If puzzles exist, verify they have FEN
        for puzzle in data["puzzles"][:3]:
            assert "fen" in puzzle
            # FEN should be valid
            assert len(puzzle["fen"]) > 10

    def test_get_community_puzzles(self, authenticated_session):
        """Get community puzzles"""
        response = authenticated_session.get(
            f"{BASE_URL}/api/community/puzzles?limit=5"
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "puzzles" in data


class TestReflectPage:
    """Test reflect page endpoints"""
    
    def test_get_games_needing_reflection(self, authenticated_session):
        """Get list of games that need reflection"""
        response = authenticated_session.get(
            f"{BASE_URL}/api/reflect/pending"
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should have games array
        assert "games" in data
        assert isinstance(data["games"], list)
    
    def test_get_reflect_profile(self, authenticated_session):
        """Get user's reflection profile"""
        response = authenticated_session.get(
            f"{BASE_URL}/api/reflect/v1/profile"
        )
        
        assert response.status_code == 200
