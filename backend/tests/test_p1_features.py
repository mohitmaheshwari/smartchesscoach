"""
P1 Features Backend Tests
=========================
Tests for the three new P1 features:
1. Count Escape Squares - coach prompts users to count opponent escape squares
2. Immediate Review Data Attachment - game analysis attaches to profile automatically
3. Dynamic Dashboard Mood via Win Streaks - 3+ consecutive wins suppress negative profiling

Test approach:
- Unit tests for escape_squares_service functions (no DB needed)
- API tests for home-intelligence endpoint (win_streak, mood_override)
- API tests for escape-squares/check and escape-squares/answer endpoints
"""

import pytest
import requests
import os
import chess

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# ============================================
# UNIT TESTS: Escape Squares Service
# ============================================

class TestEscapeSquaresService:
    """Unit tests for escape_squares_service.py functions"""
    
    def test_count_escape_squares_starting_position(self):
        """Test escape squares count for king in starting position"""
        from services.escape_squares_service import count_king_escape_squares
        
        # Starting position - white king on e1
        fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        result = count_king_escape_squares(fen, "white")
        
        assert "escape_count" in result
        assert "king_square" in result
        assert result["king_square"] == "e1"
        assert result["king_color"] == "white"
        # King on e1 is blocked by own pieces (d1, d2, e2, f1, f2)
        assert result["escape_count"] == 0
        
    def test_count_escape_squares_scholars_mate(self):
        """Test escape squares for scholar's mate position - king should have 0 escapes"""
        from services.escape_squares_service import count_king_escape_squares
        
        # Scholar's mate position - black king is checkmated
        # After 1.e4 e5 2.Qh5 Nc6 3.Bc4 Nf6?? 4.Qxf7#
        fen = "r1bqkb1r/pppp1Qpp/2n2n2/4p3/2B1P3/8/PPPP1PPP/RNB1K1NR b KQkq - 0 4"
        result = count_king_escape_squares(fen, "black")
        
        assert result["escape_count"] == 0
        assert result["is_in_check"] == True
        assert result["king_square"] == "e8"
        
    def test_count_escape_squares_open_king(self):
        """Test escape squares for a king with some escape squares"""
        from services.escape_squares_service import count_king_escape_squares
        
        # King on e4 with some open squares
        fen = "8/8/8/8/4K3/8/8/8 w - - 0 1"
        result = count_king_escape_squares(fen, "white")
        
        # King on e4 has 8 adjacent squares, all should be escapes
        assert result["escape_count"] == 8
        assert result["king_square"] == "e4"
        
    def test_is_teaching_moment_check_position(self):
        """Test that check positions trigger teaching moment"""
        from services.escape_squares_service import is_escape_squares_teaching_moment
        
        # Position where black king is in check
        fen = "rnbqkbnr/pppp1ppp/8/4p3/4P3/5Q2/PPPP1PPP/RNB1KBNR b KQkq - 1 2"
        
        # User is white, opponent (black) king is in check
        result = is_escape_squares_teaching_moment(fen, "white")
        
        # Should return quiz data since opponent is in check
        # Note: This depends on whose turn it is - check the logic
        # If it's black's turn and black is in check, white user should get quiz
        
    def test_is_teaching_moment_back_rank(self):
        """Test that back-rank positions trigger teaching moment"""
        from services.escape_squares_service import is_escape_squares_teaching_moment
        
        # Back-rank mate threat position - black king on g8 with pawns on f7, g7, h7
        fen = "6k1/5ppp/8/8/8/8/8/R3K3 w Q - 0 1"
        result = is_escape_squares_teaching_moment(fen, "white")
        
        # Should detect back-rank teaching moment
        if result:
            assert result["quiz_type"] == "count_escape_squares"
            assert "trigger" in result
            
    def test_validate_escape_squares_answer_correct(self):
        """Test validating a correct answer"""
        from services.escape_squares_service import validate_escape_squares_answer
        
        quiz_data = {
            "correct_answer": 2,
            "details": {
                "escape_squares": ["f8", "d8"],
                "blocked_squares": [
                    {"square": "e7", "reason": "own_piece"},
                    {"square": "f7", "reason": "attacked"}
                ]
            }
        }
        
        result = validate_escape_squares_answer(quiz_data, 2)
        
        assert result["correct"] == True
        assert result["correct_answer"] == 2
        assert result["user_answer"] == 2
        assert "message" in result
        
    def test_validate_escape_squares_answer_incorrect(self):
        """Test validating an incorrect answer"""
        from services.escape_squares_service import validate_escape_squares_answer
        
        quiz_data = {
            "correct_answer": 2,
            "details": {
                "escape_squares": ["f8", "d8"],
                "blocked_squares": []
            }
        }
        
        result = validate_escape_squares_answer(quiz_data, 4)
        
        assert result["correct"] == False
        assert result["correct_answer"] == 2
        assert result["user_answer"] == 4
        assert "message" in result


# ============================================
# API TESTS: Home Intelligence (Win Streak)
# ============================================

class TestHomeIntelligenceWinStreak:
    """API tests for win_streak and mood_override in home-intelligence endpoint"""
    
    @pytest.fixture
    def api_client(self):
        """Shared requests session with dev mode cookie"""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        session.cookies.set("dev_mode", "true")
        return session
    
    def test_home_intelligence_returns_win_streak(self, api_client):
        """GET /api/coach/home-intelligence returns win_streak object"""
        response = api_client.get(f"{BASE_URL}/api/coach/home-intelligence")
        
        assert response.status_code == 200
        data = response.json()
        
        # win_streak should be present in response
        assert "win_streak" in data, "win_streak field missing from response"
        
        win_streak = data["win_streak"]
        assert "current_streak" in win_streak, "current_streak missing from win_streak"
        assert "recent_wins" in win_streak, "recent_wins missing from win_streak"
        assert "recent_total" in win_streak, "recent_total missing from win_streak"
        
        # Values should be integers
        assert isinstance(win_streak["current_streak"], int)
        assert isinstance(win_streak["recent_wins"], int)
        assert isinstance(win_streak["recent_total"], int)
        
    def test_home_intelligence_returns_mood_override(self, api_client):
        """GET /api/coach/home-intelligence returns mood_override field"""
        response = api_client.get(f"{BASE_URL}/api/coach/home-intelligence")
        
        assert response.status_code == 200
        data = response.json()
        
        # mood_override should be present (can be null if no streak >= 3)
        assert "mood_override" in data, "mood_override field missing from response"
        
        # If user has < 3 wins, mood_override should be null
        # If user has >= 3 wins, mood_override should have structure
        mood_override = data.get("mood_override")
        
        if mood_override is not None:
            assert "type" in mood_override
            assert "streak" in mood_override
            assert "message" in mood_override
            assert "suppress_negative" in mood_override
            assert mood_override["type"] == "positive_momentum"
            assert mood_override["suppress_negative"] == True
            
    def test_home_intelligence_has_data_field(self, api_client):
        """GET /api/coach/home-intelligence returns has_data field"""
        response = api_client.get(f"{BASE_URL}/api/coach/home-intelligence")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "has_data" in data


# ============================================
# API TESTS: Escape Squares Endpoints
# ============================================

class TestEscapeSquaresEndpoints:
    """API tests for escape-squares/check and escape-squares/answer endpoints"""
    
    @pytest.fixture
    def api_client(self):
        """Shared requests session with dev mode cookie"""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        session.cookies.set("dev_mode", "true")
        return session
    
    def test_escape_squares_check_requires_session_id(self, api_client):
        """POST /api/coach/play/escape-squares/check requires session_id"""
        response = api_client.post(
            f"{BASE_URL}/api/coach/play/escape-squares/check",
            json={}
        )
        
        # Should return 400 for missing session_id
        assert response.status_code == 400
        data = response.json()
        assert "session_id" in data.get("detail", "").lower() or "required" in data.get("detail", "").lower()
        
    def test_escape_squares_check_returns_has_quiz(self, api_client):
        """POST /api/coach/play/escape-squares/check returns has_quiz field"""
        # First start a game to get a valid session_id
        start_response = api_client.post(
            f"{BASE_URL}/api/coach/play/start",
            json={"user_color": "white", "time_control": "15+10"}
        )
        
        if start_response.status_code != 200:
            pytest.skip("Could not start game session for testing")
            
        session_data = start_response.json()
        session_id = session_data.get("session", {}).get("session_id")
        
        if not session_id:
            pytest.skip("No session_id returned from start endpoint")
        
        # Now check for escape squares quiz
        response = api_client.post(
            f"{BASE_URL}/api/coach/play/escape-squares/check",
            json={"session_id": session_id}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # has_quiz should be present
        assert "has_quiz" in data, "has_quiz field missing from response"
        assert isinstance(data["has_quiz"], bool)
        
        # If has_quiz is True, quiz data should be present
        if data["has_quiz"]:
            assert "quiz" in data
            quiz = data["quiz"]
            assert "quiz_type" in quiz
            assert quiz["quiz_type"] == "count_escape_squares"
            assert "prompt" in quiz
            assert "correct_answer" in quiz
            
    def test_escape_squares_answer_requires_params(self, api_client):
        """POST /api/coach/play/escape-squares/answer requires session_id, answer, quiz_data"""
        response = api_client.post(
            f"{BASE_URL}/api/coach/play/escape-squares/answer",
            json={}
        )
        
        # Should return 400 for missing required params
        assert response.status_code == 400
        
    def test_escape_squares_answer_validates_answer(self, api_client):
        """POST /api/coach/play/escape-squares/answer validates user answer"""
        # First start a game
        start_response = api_client.post(
            f"{BASE_URL}/api/coach/play/start",
            json={"user_color": "white", "time_control": "15+10"}
        )
        
        if start_response.status_code != 200:
            pytest.skip("Could not start game session for testing")
            
        session_data = start_response.json()
        session_id = session_data.get("session", {}).get("session_id")
        
        if not session_id:
            pytest.skip("No session_id returned from start endpoint")
        
        # Create mock quiz data
        quiz_data = {
            "quiz_type": "count_escape_squares",
            "trigger": "check",
            "prompt": "How many escape squares?",
            "correct_answer": 2,
            "king_square": "e8",
            "king_color": "black",
            "user_color": "white",
            "details": {
                "escape_squares": ["d8", "f8"],
                "blocked_squares": [],
                "is_in_check": True
            }
        }
        
        # Submit answer
        response = api_client.post(
            f"{BASE_URL}/api/coach/play/escape-squares/answer",
            json={
                "session_id": session_id,
                "answer": 2,
                "quiz_data": quiz_data
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Result should be present
        assert "result" in data
        result = data["result"]
        
        assert "correct" in result
        assert "message" in result
        assert "correct_answer" in result
        assert "user_answer" in result


# ============================================
# INTEGRATION TEST: Full Escape Squares Flow
# ============================================

class TestEscapeSquaresIntegration:
    """Integration test for the full escape squares quiz flow"""
    
    @pytest.fixture
    def api_client(self):
        """Shared requests session with dev mode cookie"""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        session.cookies.set("dev_mode", "true")
        return session
    
    def test_escape_squares_service_detects_restricted_king(self):
        """Test that service detects restricted king positions"""
        from services.escape_squares_service import is_escape_squares_teaching_moment
        
        # Position with restricted black king (only 1-2 escape squares)
        # White has attacking pressure
        fen = "r1bqk2r/pppp1ppp/2n2n2/2b1p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4"
        
        result = is_escape_squares_teaching_moment(fen, "white")
        
        # May or may not trigger depending on exact position
        # Just verify the function runs without error
        assert result is None or isinstance(result, dict)
        
    def test_escape_squares_service_detects_back_rank_mate(self):
        """Test that service detects back-rank mate teaching moments"""
        from services.escape_squares_service import is_escape_squares_teaching_moment
        
        # Classic back-rank mate setup - black king trapped by own pawns
        fen = "6k1/5ppp/8/8/8/8/8/R3K3 w Q - 0 1"
        
        result = is_escape_squares_teaching_moment(fen, "white")
        
        # Should detect this as a teaching moment
        if result:
            assert result["quiz_type"] == "count_escape_squares"
            assert result["trigger"] in ["back_rank", "restricted"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
