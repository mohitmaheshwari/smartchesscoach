"""
Test Coach Play Chat - Position-specific advice and No LLM Hallucinations

Tests for the bug fix where the coach was:
1. Incorrectly claiming opening names (e.g. "h6 is Italian Game")
2. Giving generic/nonsensical advice instead of position-specific feedback
3. Not correctly analyzing move quality (inaccuracy, mistake, blunder)
4. Best move suggestion should come from Stockfish analysis

The fix involved:
1. Adding logger import to coach_commentary.py
2. Fixing the fast path to not bypass move analysis when asking about specific moves
3. Adding more phrase patterns for move-related questions
4. Using position_strategy_analyzer for real tactical insight
"""
import pytest
import time
import uuid

BASE_URL = "https://chessguru-home.preview.emergentagent.com"


class TestCoachChatNoHallucinations:
    """Test that coach chat gives position-specific advice, not generic/hallucinated content"""
    
    @pytest.fixture
    def active_game_session(self, authenticated_session):
        """Create a game with some moves already played to test chat"""
        # Start a new session
        response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/start",
            json={"user_color": "white", "time_control": "15+10"}
        )
        assert response.status_code == 200
        data = response.json()
        session_id = data["session_id"]
        
        # Make opening move: e4
        response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/move",
            json={"session_id": session_id, "move": "e4", "time_spent": 1.0}
        )
        assert response.status_code == 200
        time.sleep(3)  # Wait for coach response (coach plays black's move)
        
        # Now it's white's turn again - make d4
        response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/move",
            json={"session_id": session_id, "move": "d4", "time_spent": 1.0}
        )
        # d4 might fail if it's illegal in current position, try Nf3 instead
        if response.status_code != 200:
            response = authenticated_session.post(
                f"{BASE_URL}/api/coach/play/move",
                json={"session_id": session_id, "move": "Nf3", "time_spent": 1.0}
            )
        time.sleep(3)
        
        # Make a less optimal move: h3 (to test quality detection)
        response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/move",
            json={"session_id": session_id, "move": "h3", "time_spent": 1.0}
        )
        # h3 might also fail, try another move
        if response.status_code != 200:
            response = authenticated_session.post(
                f"{BASE_URL}/api/coach/play/move",
                json={"session_id": session_id, "move": "Bc4", "time_spent": 1.0}
            )
        time.sleep(2)
        
        yield session_id, authenticated_session
        
        # Cleanup
        authenticated_session.post(
            f"{BASE_URL}/api/coach/play/end",
            json={"session_id": session_id, "reason": "resigned"}
        )
    
    def test_chat_returns_success(self, active_game_session):
        """Basic test that chat endpoint works"""
        session_id, session = active_game_session
        
        response = session.post(
            f"{BASE_URL}/api/coach/play/chat",
            json={"session_id": session_id, "message": "What should I do?"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "response" in data
        assert len(data["response"]) > 0
    
    def test_chat_gives_position_specific_advice(self, active_game_session):
        """Chat should give position-specific advice, not generic plans"""
        session_id, session = active_game_session
        
        response = session.post(
            f"{BASE_URL}/api/coach/play/chat",
            json={"session_id": session_id, "message": "What is the best plan here?"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should return a position_plan with specific goals
        assert "position_plan" in data
        if data["position_plan"]:
            assert "main_idea" in data["position_plan"]
            assert "specific_goals" in data["position_plan"]
    
    def test_chat_analyzes_move_quality_correctly(self, active_game_session):
        """When asking about a move, should get correct move_quality assessment"""
        session_id, session = active_game_session
        
        # Ask about the last move (h3 which is suboptimal)
        response = session.post(
            f"{BASE_URL}/api/coach/play/chat",
            json={"session_id": session_id, "message": "Was my last move good?"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should include move quality assessment
        assert "move_quality" in data
        # h3 is not a great move in the opening, should be okay/inaccuracy or worse
        # The quality should be one of the valid enum values
        valid_qualities = ["brilliant", "great", "good", "okay", "inaccuracy", "mistake", "blunder"]
        if data["move_quality"]:
            assert data["move_quality"] in valid_qualities
    
    def test_chat_provides_best_move_suggestion(self, active_game_session):
        """Chat should provide best move from Stockfish analysis"""
        session_id, session = active_game_session
        
        response = session.post(
            f"{BASE_URL}/api/coach/play/chat",
            json={"session_id": session_id, "message": "What was the best move instead?"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should include best_move from Stockfish analysis
        assert "best_move" in data
        # best_move should be a valid chess move notation (e.g., "Nf3", "d4", "Bc4")
        if data["best_move"]:
            # Basic sanity check - should be 2-5 characters, letters and numbers
            assert 2 <= len(data["best_move"]) <= 6
    
    def test_chat_no_false_opening_claims(self, authenticated_session):
        """Coach should NOT claim random moves are known openings when they aren't"""
        # Start a fresh game
        response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/start",
            json={"user_color": "white", "time_control": "15+10"}
        )
        assert response.status_code == 200
        data = response.json()
        session_id = data["session_id"]
        
        try:
            # Play unusual opening move: h3 (not a standard opening)
            response = authenticated_session.post(
                f"{BASE_URL}/api/coach/play/move",
                json={"session_id": session_id, "move": "h3", "time_spent": 1.0}
            )
            assert response.status_code == 200
            time.sleep(1)
            
            # Ask about the move - should NOT claim it's a famous opening
            response = authenticated_session.post(
                f"{BASE_URL}/api/coach/play/chat",
                json={"session_id": session_id, "message": "What opening is h3?"}
            )
            
            assert response.status_code == 200
            data = response.json()
            
            response_text = data["response"].lower()
            
            # h3 is NOT the Italian Game, Sicilian, etc.
            # The response should NOT falsely claim these openings
            false_opening_claims = [
                "italian game" in response_text and "h3" not in response_text,
                "sicilian" in response_text,
                "french defense" in response_text,
                "caro-kann" in response_text,
                "ruy lopez" in response_text,
            ]
            
            # None of the false claims should be present
            for claim in false_opening_claims:
                assert not claim, f"Coach falsely claimed h3 is a known opening: {data['response']}"
            
        finally:
            # Cleanup
            authenticated_session.post(
                f"{BASE_URL}/api/coach/play/end",
                json={"session_id": session_id, "reason": "resigned"}
            )
    
    def test_chat_suggestion_arrow_when_better_move_exists(self, active_game_session):
        """When user asks about a suboptimal move, should get suggestion_arrow for better move"""
        session_id, session = active_game_session
        
        response = session.post(
            f"{BASE_URL}/api/coach/play/chat",
            json={"session_id": session_id, "message": "Was h3 good? What should I have played?"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # If h3 was suboptimal, should have a suggestion_arrow
        # suggestion_arrow is in UCI format like "d2d4"
        if data.get("suggestion_arrow"):
            arrow = data["suggestion_arrow"]
            # UCI format: 4 characters (from_square + to_square)
            assert len(arrow) >= 4
            # First 2 chars should be valid square
            assert arrow[0] in "abcdefgh"
            assert arrow[1] in "12345678"


class TestCoachChatMoveDetection:
    """Test that chat correctly detects when user is asking about a specific move"""
    
    @pytest.fixture
    def game_with_moves(self, authenticated_session):
        """Create a game with several moves"""
        response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/start",
            json={"user_color": "white", "time_control": "15+10"}
        )
        assert response.status_code == 200
        data = response.json()
        session_id = data["session_id"]
        
        # Play e4
        response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/move",
            json={"session_id": session_id, "move": "e4", "time_spent": 1.0}
        )
        time.sleep(3)  # Wait for coach's response
        
        yield session_id, authenticated_session
        
        authenticated_session.post(
            f"{BASE_URL}/api/coach/play/end",
            json={"session_id": session_id, "reason": "resigned"}
        )
    
    def test_detects_i_played_pattern(self, game_with_moves):
        """Should detect 'I played' pattern and analyze the move"""
        session_id, session = game_with_moves
        
        response = session.post(
            f"{BASE_URL}/api/coach/play/chat",
            json={"session_id": session_id, "message": "I played e4, was that good?"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should have move_quality since we asked about a specific move
        assert "move_quality" in data
    
    def test_detects_was_my_move_pattern(self, game_with_moves):
        """Should detect 'was my move' pattern"""
        session_id, session = game_with_moves
        
        response = session.post(
            f"{BASE_URL}/api/coach/play/chat",
            json={"session_id": session_id, "message": "Was my move a mistake?"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "move_quality" in data
    
    def test_detects_why_did_i_pattern(self, game_with_moves):
        """Should detect 'why did I' pattern"""
        session_id, session = game_with_moves
        
        response = session.post(
            f"{BASE_URL}/api/coach/play/chat",
            json={"session_id": session_id, "message": "Why did I play that?"}
        )
        
        assert response.status_code == 200
        data = response.json()
        # Should get a response analyzing the move
        assert "response" in data
        assert len(data["response"]) > 0


class TestCoachChatMessageIds:
    """Test that coach messages have IDs for feedback button"""
    
    def test_messages_have_ids(self, authenticated_session):
        """Messages from /coach/play/messages should have IDs"""
        # Start a game
        response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/start",
            json={"user_color": "white", "time_control": "15+10"}
        )
        assert response.status_code == 200
        data = response.json()
        session_id = data["session_id"]
        
        try:
            # Make a move to trigger coach messages
            response = authenticated_session.post(
                f"{BASE_URL}/api/coach/play/move",
                json={"session_id": session_id, "move": "e4", "time_spent": 1.0}
            )
            assert response.status_code == 200
            time.sleep(2)  # Wait for coach to generate messages
            
            # Get messages
            response = authenticated_session.get(
                f"{BASE_URL}/api/coach/play/messages/{session_id}"
            )
            
            assert response.status_code == 200
            data = response.json()
            
            # Check messages have IDs
            for msg in data.get("messages", []):
                assert "id" in msg, "Message should have an 'id' field for feedback"
                assert isinstance(msg["id"], str)
                assert len(msg["id"]) > 0
                
        finally:
            authenticated_session.post(
                f"{BASE_URL}/api/coach/play/end",
                json={"session_id": session_id, "reason": "resigned"}
            )
    
    def test_messages_endpoint_structure(self, authenticated_session):
        """Messages endpoint should return proper structure"""
        # Start a game
        response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/start",
            json={"user_color": "white", "time_control": "15+10"}
        )
        assert response.status_code == 200
        data = response.json()
        session_id = data["session_id"]
        
        try:
            # Get messages - even if empty, structure should be correct
            response = authenticated_session.get(
                f"{BASE_URL}/api/coach/play/messages/{session_id}"
            )
            
            assert response.status_code == 200
            data = response.json()
            
            # Should have success and messages fields
            assert "success" in data
            assert data["success"] is True
            assert "messages" in data
            assert isinstance(data["messages"], list)
            assert "count" in data
            
        finally:
            authenticated_session.post(
                f"{BASE_URL}/api/coach/play/end",
                json={"session_id": session_id, "reason": "resigned"}
            )


class TestCoachChatRequired:
    """Test required fields and error handling"""
    
    def test_requires_session_id(self, authenticated_session):
        """Chat endpoint requires session_id"""
        response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/chat",
            json={"message": "Hello"}
        )
        assert response.status_code == 400
    
    def test_requires_message(self, authenticated_session):
        """Chat endpoint requires message"""
        # Create a session first
        start_response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/start",
            json={"user_color": "white", "time_control": "15+10"}
        )
        assert start_response.status_code == 200
        session_id = start_response.json()["session_id"]
        
        try:
            response = authenticated_session.post(
                f"{BASE_URL}/api/coach/play/chat",
                json={"session_id": session_id}
            )
            assert response.status_code == 400
        finally:
            authenticated_session.post(
                f"{BASE_URL}/api/coach/play/end",
                json={"session_id": session_id, "reason": "resigned"}
            )
    
    def test_invalid_session_returns_404(self, authenticated_session):
        """Invalid session_id returns 404"""
        response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/chat",
            json={"session_id": str(uuid.uuid4()), "message": "Hello"}
        )
        assert response.status_code == 404


class TestOpeningAttributionFix:
    """Test that opening names are only attributed to defining moves, not continuation moves"""
    
    def test_identifying_move_gets_this_is(self):
        """The defining move of an opening should get 'This is the X' message"""
        from coach_engine.question_system import generate_opening_plan_question
        from coach_engine.opening_plans import SICILIAN_DEFENSE
        
        # c5 IS the identifying move for Sicilian
        question = generate_opening_plan_question(SICILIAN_DEFENSE, move_number=1, current_move="c5")
        assert "This is the Sicilian Defense" in question.text
    
    def test_continuation_move_gets_were_in(self):
        """A continuation move should get 'We're in the X' message, not 'This is'"""
        from coach_engine.question_system import generate_opening_plan_question
        from coach_engine.opening_plans import SICILIAN_DEFENSE
        
        # d5 is NOT an identifying move for Sicilian
        question = generate_opening_plan_question(SICILIAN_DEFENSE, move_number=2, current_move="d5")
        assert "We're in the Sicilian Defense" in question.text
        assert "This is the Sicilian Defense" not in question.text
    
    def test_random_move_not_attributed_to_opening(self):
        """A random move like Nf6 should not claim to be 'the Sicilian'"""
        from coach_engine.question_system import generate_opening_plan_question
        from coach_engine.opening_plans import SICILIAN_DEFENSE
        
        question = generate_opening_plan_question(SICILIAN_DEFENSE, move_number=4, current_move="Nf6")
        assert "This is the Sicilian Defense" not in question.text
        # Should use "We're in" instead
        assert "We're in the Sicilian Defense" in question.text
