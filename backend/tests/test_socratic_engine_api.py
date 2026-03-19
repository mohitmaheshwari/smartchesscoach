"""
Test suite for Socratic Engine API endpoints

Tests the hyper-personalized chess coaching Socratic Engine which:
- Never gives the answer first
- Asks what the student was thinking
- Guides with progressive hints
- Only reveals after engagement
"""
import pytest
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://habit-trainer-1.preview.emergentagent.com')

# Test data - Classic Scholar's Mate position
SCHOLARS_MATE_FEN = "r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 4 4"
PLAYED_MOVE = "Nf3"
BEST_MOVE = "Qxf7#"


class TestSocraticStart:
    """Tests for /api/coach/socratic/start endpoint"""
    
    def test_start_dialogue_basic(self, authenticated_session):
        """Start a basic Socratic dialogue"""
        response = authenticated_session.post(
            f"{BASE_URL}/api/coach/socratic/start",
            json={
                "fen": SCHOLARS_MATE_FEN,
                "move_played": PLAYED_MOVE,
                "best_move": BEST_MOVE,
                "eval_loss": 10000,
                "position_type": "missed_tactic"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "dialogue_id" in data
        assert "opening_question" in data
        assert "state" in data
        assert "expects_response" in data
        assert "response_type" in data
        
        # Verify dialogue state
        assert data["state"] == "awaiting_response"
        assert data["expects_response"] == True
        assert data["response_type"] == "text"
        
        # Verify opening question is NOT the answer
        assert BEST_MOVE not in data["opening_question"]
    
    def test_start_dialogue_blunder_type(self, authenticated_session):
        """Start dialogue with blunder position type"""
        response = authenticated_session.post(
            f"{BASE_URL}/api/coach/socratic/start",
            json={
                "fen": SCHOLARS_MATE_FEN,
                "move_played": PLAYED_MOVE,
                "best_move": BEST_MOVE,
                "eval_loss": 500,
                "position_type": "blunder"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Blunder questions should reference the move played
        assert "dialogue_id" in data
        assert data["state"] == "awaiting_response"
    
    def test_start_dialogue_strategic_type(self, authenticated_session):
        """Start dialogue with strategic position type"""
        response = authenticated_session.post(
            f"{BASE_URL}/api/coach/socratic/start",
            json={
                "fen": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1",
                "move_played": "d5",
                "best_move": "e5",
                "eval_loss": 30,
                "position_type": "strategic"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "dialogue_id" in data
    
    def test_start_dialogue_endgame_type(self, authenticated_session):
        """Start dialogue with endgame position type"""
        response = authenticated_session.post(
            f"{BASE_URL}/api/coach/socratic/start",
            json={
                "fen": "8/5k2/8/8/8/4K3/8/8 w - - 0 1",
                "move_played": "Kd3",
                "best_move": "Ke4",
                "eval_loss": 50,
                "position_type": "endgame"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "dialogue_id" in data
    
    def test_start_dialogue_missing_fen(self, authenticated_session):
        """Start dialogue with missing fen should return error"""
        response = authenticated_session.post(
            f"{BASE_URL}/api/coach/socratic/start",
            json={
                "move_played": PLAYED_MOVE,
                "best_move": BEST_MOVE
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "error" in data
    
    def test_start_dialogue_missing_move_played(self, authenticated_session):
        """Start dialogue with missing move_played should return error"""
        response = authenticated_session.post(
            f"{BASE_URL}/api/coach/socratic/start",
            json={
                "fen": SCHOLARS_MATE_FEN,
                "best_move": BEST_MOVE
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "error" in data
    
    def test_start_dialogue_missing_best_move(self, authenticated_session):
        """Start dialogue with missing best_move should return error"""
        response = authenticated_session.post(
            f"{BASE_URL}/api/coach/socratic/start",
            json={
                "fen": SCHOLARS_MATE_FEN,
                "move_played": PLAYED_MOVE
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "error" in data


class TestSocraticRespond:
    """Tests for /api/coach/socratic/respond endpoint"""
    
    def test_respond_with_text(self, authenticated_session):
        """Respond with text explanation"""
        response = authenticated_session.post(
            f"{BASE_URL}/api/coach/socratic/respond",
            json={
                "dialogue_id": "test123",
                "fen": SCHOLARS_MATE_FEN,
                "move_played": PLAYED_MOVE,
                "best_move": BEST_MOVE,
                "response": "I was just developing my knight",
                "hints_given": 0,
                "state": "awaiting_response"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "message" in data
        assert "state" in data
        assert "expects_response" in data
        assert "celebration" in data
        assert "hints_given" in data
        
        # Student didn't find answer, so should redirect
        assert data["celebration"] == False
        assert data["expects_response"] == True
    
    def test_respond_with_correct_answer(self, authenticated_session):
        """Respond with correct answer should celebrate"""
        response = authenticated_session.post(
            f"{BASE_URL}/api/coach/socratic/respond",
            json={
                "dialogue_id": "test123",
                "fen": SCHOLARS_MATE_FEN,
                "move_played": PLAYED_MOVE,
                "best_move": BEST_MOVE,
                "response": "Qxf7",
                "hints_given": 0,
                "state": "awaiting_response"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should celebrate discovery
        assert data["celebration"] == True
        assert data["state"] == "celebration"
    
    def test_respond_with_close_answer(self, authenticated_session):
        """Respond with close answer should guide further"""
        response = authenticated_session.post(
            f"{BASE_URL}/api/coach/socratic/respond",
            json={
                "dialogue_id": "test123",
                "fen": SCHOLARS_MATE_FEN,
                "move_played": PLAYED_MOVE,
                "best_move": BEST_MOVE,
                "response": "I think the queen can attack the f7 square",
                "hints_given": 0,
                "state": "awaiting_response"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Response should guide them
        assert "message" in data
        assert data["expects_response"] == True
    
    def test_respond_missing_response(self, authenticated_session):
        """Respond without response text should return error"""
        response = authenticated_session.post(
            f"{BASE_URL}/api/coach/socratic/respond",
            json={
                "dialogue_id": "test123",
                "fen": SCHOLARS_MATE_FEN,
                "move_played": PLAYED_MOVE,
                "best_move": BEST_MOVE,
                "hints_given": 0,
                "state": "awaiting_response"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "error" in data
    
    def test_respond_with_tactical_keywords(self, authenticated_session):
        """Respond with tactical keywords should be recognized as getting closer"""
        response = authenticated_session.post(
            f"{BASE_URL}/api/coach/socratic/respond",
            json={
                "dialogue_id": "test123",
                "fen": SCHOLARS_MATE_FEN,
                "move_played": PLAYED_MOVE,
                "best_move": BEST_MOVE,
                "response": "There's a check and possible checkmate threat",
                "hints_given": 0,
                "state": "awaiting_response"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should recognize they're on the right track
        assert "message" in data
        assert data["expects_response"] == True


class TestSocraticHint:
    """Tests for /api/coach/socratic/hint endpoint"""
    
    def test_hint_subtle(self, authenticated_session):
        """First hint should be subtle"""
        response = authenticated_session.post(
            f"{BASE_URL}/api/coach/socratic/hint",
            json={
                "dialogue_id": "test123",
                "fen": SCHOLARS_MATE_FEN,
                "move_played": PLAYED_MOVE,
                "best_move": BEST_MOVE,
                "hints_given": 0
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "hint" in data
        assert "hint_level" in data
        assert "state" in data
        assert "hints_given" in data
        
        assert data["hint_level"] == "subtle"
        assert data["hints_given"] == 1
    
    def test_hint_directional(self, authenticated_session):
        """Second hint should be directional"""
        response = authenticated_session.post(
            f"{BASE_URL}/api/coach/socratic/hint",
            json={
                "dialogue_id": "test123",
                "fen": SCHOLARS_MATE_FEN,
                "move_played": PLAYED_MOVE,
                "best_move": BEST_MOVE,
                "hints_given": 1
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["hint_level"] == "directional"
        assert data["hints_given"] == 2
    
    def test_hint_specific(self, authenticated_session):
        """Third hint should be specific"""
        response = authenticated_session.post(
            f"{BASE_URL}/api/coach/socratic/hint",
            json={
                "dialogue_id": "test123",
                "fen": SCHOLARS_MATE_FEN,
                "move_played": PLAYED_MOVE,
                "best_move": BEST_MOVE,
                "hints_given": 2
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["hint_level"] == "specific"
        assert data["hints_given"] == 3
    
    def test_hint_almost_answer(self, authenticated_session):
        """Fourth hint should be almost_answer"""
        response = authenticated_session.post(
            f"{BASE_URL}/api/coach/socratic/hint",
            json={
                "dialogue_id": "test123",
                "fen": SCHOLARS_MATE_FEN,
                "move_played": PLAYED_MOVE,
                "best_move": BEST_MOVE,
                "hints_given": 3
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["hint_level"] == "almost_answer"
        assert data["hints_given"] == 4
        # After max hints, should be ready for reveal
        assert data["state"] == "reveal"
    
    def test_hint_missing_fen(self, authenticated_session):
        """Hint without fen should return error"""
        response = authenticated_session.post(
            f"{BASE_URL}/api/coach/socratic/hint",
            json={
                "dialogue_id": "test123",
                "move_played": PLAYED_MOVE,
                "best_move": BEST_MOVE,
                "hints_given": 0
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "error" in data
    
    def test_hint_missing_best_move(self, authenticated_session):
        """Hint without best_move should return error"""
        response = authenticated_session.post(
            f"{BASE_URL}/api/coach/socratic/hint",
            json={
                "dialogue_id": "test123",
                "fen": SCHOLARS_MATE_FEN,
                "move_played": PLAYED_MOVE,
                "hints_given": 0
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "error" in data


class TestSocraticReveal:
    """Tests for /api/coach/socratic/reveal endpoint"""
    
    def test_reveal_basic(self, authenticated_session):
        """Reveal the answer with teaching explanation"""
        response = authenticated_session.post(
            f"{BASE_URL}/api/coach/socratic/reveal",
            json={
                "fen": SCHOLARS_MATE_FEN,
                "move_played": PLAYED_MOVE,
                "best_move": BEST_MOVE,
                "eval_loss": 10000,
                "hints_given": 2,
                "student_guesses": ["Qh5", "Bc4"]
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "explanation" in data
        assert "state" in data
        assert "complete" in data
        
        assert data["state"] == "complete"
        assert data["complete"] == True
        
        # Explanation should mention the best move
        assert BEST_MOVE in data["explanation"]
    
    def test_reveal_acknowledges_guesses(self, authenticated_session):
        """Reveal should acknowledge student's guesses"""
        response = authenticated_session.post(
            f"{BASE_URL}/api/coach/socratic/reveal",
            json={
                "fen": SCHOLARS_MATE_FEN,
                "move_played": PLAYED_MOVE,
                "best_move": BEST_MOVE,
                "eval_loss": 10000,
                "hints_given": 2,
                "student_guesses": ["Qh5", "Bc4"]
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should mention their last guess
        assert "Bc4" in data["explanation"]
    
    def test_reveal_without_hints(self, authenticated_session):
        """Reveal with no hints given"""
        response = authenticated_session.post(
            f"{BASE_URL}/api/coach/socratic/reveal",
            json={
                "fen": SCHOLARS_MATE_FEN,
                "move_played": PLAYED_MOVE,
                "best_move": BEST_MOVE,
                "eval_loss": 10000,
                "hints_given": 0,
                "student_guesses": []
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["complete"] == True
        assert BEST_MOVE in data["explanation"]
    
    def test_reveal_missing_fen(self, authenticated_session):
        """Reveal without fen should return error"""
        response = authenticated_session.post(
            f"{BASE_URL}/api/coach/socratic/reveal",
            json={
                "move_played": PLAYED_MOVE,
                "best_move": BEST_MOVE,
                "eval_loss": 10000
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "error" in data
    
    def test_reveal_missing_best_move(self, authenticated_session):
        """Reveal without best_move should return error"""
        response = authenticated_session.post(
            f"{BASE_URL}/api/coach/socratic/reveal",
            json={
                "fen": SCHOLARS_MATE_FEN,
                "move_played": PLAYED_MOVE,
                "eval_loss": 10000
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "error" in data


class TestSocraticDebug:
    """Tests for /api/coach/debug/test-socratic endpoint"""
    
    def test_debug_full_dialogue(self, authenticated_session):
        """Test the full dialogue demo endpoint"""
        response = authenticated_session.post(
            f"{BASE_URL}/api/coach/debug/test-socratic",
            json={
                "fen": SCHOLARS_MATE_FEN,
                "move_played": PLAYED_MOVE,
                "best_move": BEST_MOVE
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify structure
        assert "demo_dialogue" in data
        assert "philosophy" in data
        assert "position_info" in data
        
        # Verify dialogue steps
        dialogue = data["demo_dialogue"]
        assert len(dialogue) == 4
        
        # Step 1: Opening question
        assert dialogue[0]["type"] == "opening_question"
        assert "message" in dialogue[0]
        
        # Step 2: Student response
        assert dialogue[1]["type"] == "student_response"
        assert "student_said" in dialogue[1]
        assert "coach_response" in dialogue[1]
        
        # Step 3: Hint
        assert dialogue[2]["type"] == "hint"
        assert "hint_level" in dialogue[2]
        
        # Step 4: Reveal
        assert dialogue[3]["type"] == "reveal"
        assert dialogue[3]["state"] == "complete"
        
        # Verify position info
        assert data["position_info"]["fen"] == SCHOLARS_MATE_FEN
        assert data["position_info"]["move_played"] == PLAYED_MOVE
        assert data["position_info"]["best_move"] == BEST_MOVE
    
    def test_debug_default_position(self, authenticated_session):
        """Test debug endpoint with default position (no params)"""
        response = authenticated_session.post(
            f"{BASE_URL}/api/coach/debug/test-socratic",
            json={}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should use default position (Scholar's Mate)
        assert "demo_dialogue" in data
        assert len(data["demo_dialogue"]) == 4


class TestSocraticFullFlow:
    """Integration tests for full Socratic dialogue flow"""
    
    def test_full_dialogue_student_discovers(self, authenticated_session):
        """Test full flow where student discovers the answer"""
        # Step 1: Start dialogue
        start_response = authenticated_session.post(
            f"{BASE_URL}/api/coach/socratic/start",
            json={
                "fen": SCHOLARS_MATE_FEN,
                "move_played": PLAYED_MOVE,
                "best_move": BEST_MOVE,
                "eval_loss": 10000,
                "position_type": "missed_tactic"
            }
        )
        assert start_response.status_code == 200
        start_data = start_response.json()
        dialogue_id = start_data["dialogue_id"]
        
        # Verify opening question doesn't reveal answer
        assert BEST_MOVE not in start_data["opening_question"]
        
        # Step 2: Student guesses correctly
        respond_response = authenticated_session.post(
            f"{BASE_URL}/api/coach/socratic/respond",
            json={
                "dialogue_id": dialogue_id,
                "fen": SCHOLARS_MATE_FEN,
                "move_played": PLAYED_MOVE,
                "best_move": BEST_MOVE,
                "response": "Qxf7#",
                "hints_given": 0,
                "state": "awaiting_response"
            }
        )
        assert respond_response.status_code == 200
        respond_data = respond_response.json()
        
        # Should celebrate
        assert respond_data["celebration"] == True
        assert respond_data["state"] == "celebration"
    
    def test_full_dialogue_student_needs_hints(self, authenticated_session):
        """Test full flow where student needs hints to discover"""
        # Step 1: Start dialogue
        start_response = authenticated_session.post(
            f"{BASE_URL}/api/coach/socratic/start",
            json={
                "fen": SCHOLARS_MATE_FEN,
                "move_played": PLAYED_MOVE,
                "best_move": BEST_MOVE,
                "eval_loss": 10000,
                "position_type": "missed_tactic"
            }
        )
        assert start_response.status_code == 200
        start_data = start_response.json()
        dialogue_id = start_data["dialogue_id"]
        
        # Step 2: Student responds incorrectly
        respond_response = authenticated_session.post(
            f"{BASE_URL}/api/coach/socratic/respond",
            json={
                "dialogue_id": dialogue_id,
                "fen": SCHOLARS_MATE_FEN,
                "move_played": PLAYED_MOVE,
                "best_move": BEST_MOVE,
                "response": "I was developing my knight",
                "hints_given": 0,
                "state": "awaiting_response"
            }
        )
        assert respond_response.status_code == 200
        respond_data = respond_response.json()
        assert respond_data["celebration"] == False
        
        # Step 3: Student asks for hint
        hint_response = authenticated_session.post(
            f"{BASE_URL}/api/coach/socratic/hint",
            json={
                "dialogue_id": dialogue_id,
                "fen": SCHOLARS_MATE_FEN,
                "move_played": PLAYED_MOVE,
                "best_move": BEST_MOVE,
                "hints_given": 0
            }
        )
        assert hint_response.status_code == 200
        hint_data = hint_response.json()
        assert hint_data["hint_level"] == "subtle"
        
        # Step 4: After hints, reveal
        reveal_response = authenticated_session.post(
            f"{BASE_URL}/api/coach/socratic/reveal",
            json={
                "fen": SCHOLARS_MATE_FEN,
                "move_played": PLAYED_MOVE,
                "best_move": BEST_MOVE,
                "eval_loss": 10000,
                "hints_given": hint_data["hints_given"],
                "student_guesses": []
            }
        )
        assert reveal_response.status_code == 200
        reveal_data = reveal_response.json()
        assert reveal_data["complete"] == True
        assert BEST_MOVE in reveal_data["explanation"]
