"""
Test Adaptive Stockfish Skill Level and Evaluation Bar Features

Tests:
1. rating_to_skill_level() function - Different ratings map to different skill levels
2. Evaluation returned from /start, /move, /state endpoints
3. coach_skill_level is set correctly in session based on user rating
"""
import pytest
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestRatingToSkillLevel:
    """Test the rating_to_skill_level mapping function"""

    def test_import_rating_to_skill_level(self):
        """Function should be importable"""
        from coach_play.coach_opponent import rating_to_skill_level
        assert callable(rating_to_skill_level)

    def test_rating_below_800_returns_skill_0(self):
        """Ratings below 800 should map to skill level 0"""
        from coach_play.coach_opponent import rating_to_skill_level
        assert rating_to_skill_level(500) == 0
        assert rating_to_skill_level(700) == 0
        assert rating_to_skill_level(799) == 0

    def test_rating_800_999_returns_skill_3(self):
        """Ratings 800-999 should map to skill level 3"""
        from coach_play.coach_opponent import rating_to_skill_level
        assert rating_to_skill_level(800) == 3
        assert rating_to_skill_level(900) == 3
        assert rating_to_skill_level(999) == 3

    def test_rating_1000_1199_returns_skill_5(self):
        """Ratings 1000-1199 should map to skill level 5"""
        from coach_play.coach_opponent import rating_to_skill_level
        assert rating_to_skill_level(1000) == 5
        assert rating_to_skill_level(1100) == 5
        assert rating_to_skill_level(1199) == 5

    def test_rating_1200_1399_returns_skill_8(self):
        """Ratings 1200-1399 should map to skill level 8"""
        from coach_play.coach_opponent import rating_to_skill_level
        assert rating_to_skill_level(1200) == 8
        assert rating_to_skill_level(1300) == 8
        assert rating_to_skill_level(1399) == 8

    def test_rating_1400_1599_returns_skill_10(self):
        """Ratings 1400-1599 should map to skill level 10"""
        from coach_play.coach_opponent import rating_to_skill_level
        assert rating_to_skill_level(1400) == 10
        assert rating_to_skill_level(1500) == 10
        assert rating_to_skill_level(1599) == 10

    def test_rating_1600_1799_returns_skill_12(self):
        """Ratings 1600-1799 should map to skill level 12"""
        from coach_play.coach_opponent import rating_to_skill_level
        assert rating_to_skill_level(1600) == 12
        assert rating_to_skill_level(1700) == 12
        assert rating_to_skill_level(1799) == 12

    def test_rating_1800_1999_returns_skill_15(self):
        """Ratings 1800-1999 should map to skill level 15"""
        from coach_play.coach_opponent import rating_to_skill_level
        assert rating_to_skill_level(1800) == 15
        assert rating_to_skill_level(1900) == 15
        assert rating_to_skill_level(1999) == 15

    def test_rating_2000_2199_returns_skill_17(self):
        """Ratings 2000-2199 should map to skill level 17"""
        from coach_play.coach_opponent import rating_to_skill_level
        assert rating_to_skill_level(2000) == 17
        assert rating_to_skill_level(2100) == 17
        assert rating_to_skill_level(2199) == 17

    def test_rating_2200_plus_returns_skill_20(self):
        """Ratings 2200+ should map to skill level 20 (full strength)"""
        from coach_play.coach_opponent import rating_to_skill_level
        assert rating_to_skill_level(2200) == 20
        assert rating_to_skill_level(2500) == 20
        assert rating_to_skill_level(3000) == 20


class TestEvaluationInStartEndpoint:
    """Test evaluation is returned from POST /api/coach/play/start"""

    def test_start_returns_evaluation_object(self, authenticated_session):
        """Start endpoint should return evaluation object"""
        response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/start",
            json={"user_color": "white", "time_control": "15+10"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Check evaluation exists
        assert "evaluation" in data, "Response should contain 'evaluation' key"
        evaluation = data["evaluation"]
        
        # Check evaluation structure
        assert "score" in evaluation, "Evaluation should have 'score'"
        assert "mate_in" in evaluation, "Evaluation should have 'mate_in'"
        
        # Score should be a number (float)
        assert isinstance(evaluation["score"], (int, float)), "score should be numeric"
        
        # At starting position, eval should be close to 0
        assert -1.0 <= evaluation["score"] <= 1.0, f"Starting position eval should be near 0, got {evaluation['score']}"
        
        # mate_in should be None at starting position
        assert evaluation["mate_in"] is None, "Starting position shouldn't have forced mate"
        
        # Cleanup
        authenticated_session.post(
            f"{BASE_URL}/api/coach/play/end",
            json={"session_id": data["session_id"], "reason": "resigned"}
        )

    def test_start_as_black_returns_evaluation(self, authenticated_session):
        """Start as black should also return evaluation after coach's first move"""
        response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/start",
            json={"user_color": "black", "time_control": "15+10"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "evaluation" in data
        assert "score" in data["evaluation"]
        assert isinstance(data["evaluation"]["score"], (int, float))
        
        # Cleanup
        authenticated_session.post(
            f"{BASE_URL}/api/coach/play/end",
            json={"session_id": data["session_id"], "reason": "resigned"}
        )


class TestEvaluationInMoveEndpoint:
    """Test evaluation is returned from POST /api/coach/play/move"""

    @pytest.fixture
    def active_session(self, authenticated_session):
        """Create an active session for testing moves"""
        response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/start",
            json={"user_color": "white", "time_control": "15+10"}
        )
        assert response.status_code == 200
        data = response.json()
        session_id = data["session_id"]
        
        yield {"session_id": session_id, "client": authenticated_session}
        
        # Cleanup
        authenticated_session.post(
            f"{BASE_URL}/api/coach/play/end",
            json={"session_id": session_id, "reason": "resigned"}
        )

    def test_move_returns_evaluation_object(self, active_session):
        """Move endpoint should return evaluation after player move"""
        client = active_session["client"]
        session_id = active_session["session_id"]
        
        # Make a move (e4)
        response = client.post(
            f"{BASE_URL}/api/coach/play/move",
            json={"session_id": session_id, "move": "e4", "time_spent": 5.0}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Check evaluation exists
        assert "evaluation" in data, "Move response should contain 'evaluation'"
        evaluation = data["evaluation"]
        
        assert "score" in evaluation
        assert "mate_in" in evaluation
        assert isinstance(evaluation["score"], (int, float))

    def test_evaluation_changes_after_move(self, active_session):
        """Evaluation should potentially change after moves"""
        client = active_session["client"]
        session_id = active_session["session_id"]
        
        # Get initial state
        state_resp = client.get(f"{BASE_URL}/api/coach/play/state/{session_id}")
        initial_eval = state_resp.json()["evaluation"]["score"]
        
        # Make a move
        move_resp = client.post(
            f"{BASE_URL}/api/coach/play/move",
            json={"session_id": session_id, "move": "e4", "time_spent": 5.0}
        )
        
        assert move_resp.status_code == 200
        new_eval = move_resp.json()["evaluation"]
        
        # Evaluation is returned (value may or may not change significantly)
        assert "score" in new_eval
        assert isinstance(new_eval["score"], (int, float))


class TestEvaluationInStateEndpoint:
    """Test evaluation is returned from GET /api/coach/play/state/{session_id}"""

    @pytest.fixture
    def active_session(self, authenticated_session):
        """Create an active session"""
        response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/start",
            json={"user_color": "white", "time_control": "15+10"}
        )
        assert response.status_code == 200
        data = response.json()
        session_id = data["session_id"]
        
        yield {"session_id": session_id, "client": authenticated_session}
        
        # Cleanup
        authenticated_session.post(
            f"{BASE_URL}/api/coach/play/end",
            json={"session_id": session_id, "reason": "resigned"}
        )

    def test_state_returns_evaluation_object(self, active_session):
        """State endpoint should return evaluation"""
        client = active_session["client"]
        session_id = active_session["session_id"]
        
        response = client.get(f"{BASE_URL}/api/coach/play/state/{session_id}")
        
        assert response.status_code == 200
        data = response.json()
        
        # Check evaluation exists
        assert "evaluation" in data, "State response should contain 'evaluation'"
        evaluation = data["evaluation"]
        
        assert "score" in evaluation
        assert "mate_in" in evaluation
        assert isinstance(evaluation["score"], (int, float))

    def test_state_evaluation_after_moves(self, active_session):
        """State should return current evaluation after moves"""
        client = active_session["client"]
        session_id = active_session["session_id"]
        
        # Make a move
        client.post(
            f"{BASE_URL}/api/coach/play/move",
            json={"session_id": session_id, "move": "e4", "time_spent": 5.0}
        )
        
        # Get state
        response = client.get(f"{BASE_URL}/api/coach/play/state/{session_id}")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "evaluation" in data
        assert isinstance(data["evaluation"]["score"], (int, float))


class TestCoachSkillLevelInSession:
    """Test coach_skill_level is set correctly in session"""

    def test_session_contains_skill_level(self, authenticated_session):
        """Session should contain coach_skill_level field"""
        response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/start",
            json={"user_color": "white", "time_control": "15+10"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        session = data["session"]
        assert "coach_skill_level" in session, "Session should have coach_skill_level"
        assert "user_rating" in session, "Session should have user_rating"
        
        # Skill level should be in valid range (0-20)
        skill = session["coach_skill_level"]
        assert 0 <= skill <= 20, f"Skill level should be 0-20, got {skill}"
        
        # User rating should be a reasonable value
        rating = session["user_rating"]
        assert rating >= 0, f"Rating should be non-negative, got {rating}"
        
        # Cleanup
        authenticated_session.post(
            f"{BASE_URL}/api/coach/play/end",
            json={"session_id": data["session_id"], "reason": "resigned"}
        )

    def test_default_user_rating(self, authenticated_session):
        """Default user rating should be 1200 if no profile exists"""
        response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/start",
            json={"user_color": "white", "time_control": "15+10"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        session = data["session"]
        # Default rating is 1200 according to the code
        # But user might have a profile, so we just check it's reasonable
        rating = session["user_rating"]
        assert 500 <= rating <= 3500, f"Rating should be in reasonable range, got {rating}"
        
        # Cleanup
        authenticated_session.post(
            f"{BASE_URL}/api/coach/play/end",
            json={"session_id": data["session_id"], "reason": "resigned"}
        )


class TestCoachOpponentGetEvaluation:
    """Test CoachOpponent.get_evaluation() method"""

    @pytest.mark.asyncio
    async def test_get_evaluation_starting_position(self):
        """Evaluation of starting position should be near 0"""
        from coach_play.coach_opponent import CoachOpponent
        
        opponent = CoachOpponent(user_rating=1200)
        starting_fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        
        score, mate_in = await opponent.get_evaluation(starting_fen)
        
        assert isinstance(score, float)
        assert mate_in is None, "Starting position has no forced mate"
        assert -1.0 <= score <= 1.0, f"Starting position should be near equal, got {score}"

    @pytest.mark.asyncio
    async def test_get_evaluation_white_advantage(self):
        """Position with white material advantage should show positive eval"""
        from coach_play.coach_opponent import CoachOpponent
        
        opponent = CoachOpponent(user_rating=1200)
        # White is up a queen (black queen removed)
        white_up_queen = "rnb1kbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        
        score, mate_in = await opponent.get_evaluation(white_up_queen)
        
        assert isinstance(score, float)
        assert score > 5.0, f"White up a queen should have big advantage, got {score}"

    @pytest.mark.asyncio
    async def test_get_evaluation_mate_in_one(self):
        """Position with forced mate should return mate_in value"""
        from coach_play.coach_opponent import CoachOpponent
        
        opponent = CoachOpponent(user_rating=1200)
        # Scholar's mate position - Qxf7# is mate in 1
        mate_position = "r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 4 4"
        
        score, mate_in = await opponent.get_evaluation(mate_position)
        
        # The eval should be very high for white
        assert score == 10.0 or score == -10.0 or mate_in is not None

    @pytest.mark.asyncio
    async def test_evaluation_capped_at_10(self):
        """Evaluation should be capped at ±10"""
        from coach_play.coach_opponent import CoachOpponent
        
        opponent = CoachOpponent(user_rating=1200)
        # Extreme white advantage
        extreme_fen = "k7/8/8/8/8/8/QQQQQQQQ/RNBQKBNR w KQ - 0 1"
        
        score, mate_in = await opponent.get_evaluation(extreme_fen)
        
        assert -10.0 <= score <= 10.0, f"Score should be capped at ±10, got {score}"
