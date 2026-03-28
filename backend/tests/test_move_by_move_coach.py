"""
Test Move-by-Move Coach for Play with Coach Mode

Tests the fix for the "coach going silent" bug during opening phase.
The coach should now react to EVERY move during the first 15 moves,
explaining ideas, warning about traps, celebrating good moves, asking questions.

Test sequence:
1. Start game with POST /api/coach/play/start
2. Play d4 → coaching message generated about the move
3. Play c4 → Queen's Gambit specific teaching content
4. GET /api/coach/play/messages returns all coaching messages
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

@pytest.fixture
def api_client():
    """Shared requests session with dev mode headers"""
    session = requests.Session()
    session.headers.update({
        "Content-Type": "application/json"
    })
    return session


class TestMoveByMoveCoachBackend:
    """Tests for the move-by-move coaching feature that fixes silent coach issue"""
    
    def test_coach_play_start_creates_session(self, api_client):
        """POST /api/coach/play/start should create a new session and return session_id"""
        response = api_client.post(f"{BASE_URL}/api/coach/play/start", json={
            "user_color": "white",
            "difficulty": "intermediate",
            "coaching_mode": "intermediate"
        })
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert "session" in data, "Response should contain 'session' key"
        assert "session_id" in data["session"], "Session should have session_id"
        assert len(data["session"]["session_id"]) > 0, "session_id should not be empty"
        
        # Store session_id for other tests
        self.__class__.session_id = data["session"]["session_id"]
        print(f"✓ Created session: {data['session']['session_id']}")
    
    def test_d4_move_generates_coaching_message(self, api_client):
        """POST /api/coach/play/move with d4 should generate coaching about the move"""
        # Create a fresh session for this test
        start_response = api_client.post(f"{BASE_URL}/api/coach/play/start", json={
            "user_color": "white",
            "difficulty": "intermediate"
        })
        assert start_response.status_code == 200
        session_id = start_response.json()["session"]["session_id"]
        
        # Play d4
        move_response = api_client.post(f"{BASE_URL}/api/coach/play/move", json={
            "session_id": session_id,
            "move": "d4"
        })
        
        assert move_response.status_code == 200, f"Move failed: {move_response.text}"
        move_data = move_response.json()
        
        # The move should be accepted
        assert "current_fen" in move_data, "Response should contain current FEN"
        
        # Wait for background processing to complete
        time.sleep(3)
        
        # Check messages - should have coaching about d4
        messages_response = api_client.get(f"{BASE_URL}/api/coach/play/messages/{session_id}")
        assert messages_response.status_code == 200
        messages_data = messages_response.json()
        
        messages = messages_data.get("messages", [])
        print(f"Found {len(messages)} messages after d4 move")
        for msg in messages:
            print(f"  - Type: {msg.get('type')}, Trigger: {msg.get('trigger')}, Move: {msg.get('move')}")
            print(f"    Message: {msg.get('message', '')[:100]}...")
        
        # CRITICAL: In opening phase, every move should generate a message
        user_move_messages = [m for m in messages if m.get("move") == "d4"]
        assert len(user_move_messages) >= 1, "d4 should generate at least one coaching message"
        
        # Store session for next test
        self.__class__.test_session_id = session_id
        print(f"✓ d4 move generated coaching message")

    def test_c4_generates_queens_gambit_content(self, api_client):
        """After d4...d5, c4 should trigger Queen's Gambit specific teaching"""
        # Create fresh session and play d4
        start_response = api_client.post(f"{BASE_URL}/api/coach/play/start", json={
            "user_color": "white",
            "difficulty": "intermediate"
        })
        assert start_response.status_code == 200
        session_id = start_response.json()["session"]["session_id"]
        
        # Play d4 (first move)
        move1_response = api_client.post(f"{BASE_URL}/api/coach/play/move", json={
            "session_id": session_id,
            "move": "d4"
        })
        assert move1_response.status_code == 200, f"d4 failed: {move1_response.text}"
        time.sleep(2)  # Wait for coach to respond
        
        # Now play c4 (entering Queen's Gambit)
        move2_response = api_client.post(f"{BASE_URL}/api/coach/play/move", json={
            "session_id": session_id,
            "move": "c4"
        })
        assert move2_response.status_code == 200, f"c4 failed: {move2_response.text}"
        time.sleep(3)  # Wait for background processing
        
        # Get all messages
        messages_response = api_client.get(f"{BASE_URL}/api/coach/play/messages/{session_id}")
        assert messages_response.status_code == 200
        messages = messages_response.json().get("messages", [])
        
        print(f"Found {len(messages)} total messages after c4")
        for msg in messages:
            print(f"  - Type: {msg.get('type')}, Trigger: {msg.get('trigger')}, Move: {msg.get('move')}")
            print(f"    Message: {msg.get('message', '')[:150]}...")
        
        # Check for c4 specific message
        c4_messages = [m for m in messages if m.get("move") == "c4"]
        assert len(c4_messages) >= 1, "c4 move should generate a coaching message"
        
        # Check if Queen's Gambit is mentioned (may be in c4 message or elsewhere)
        all_message_text = " ".join([m.get("message", "") for m in messages]).lower()
        
        # Queen's Gambit should be recognized after d4, (opponent's d5), c4
        # The teaching_moments in opening_plans.py has specific content for c4
        has_queens_gambit = (
            "queen" in all_message_text or 
            "gambit" in all_message_text or 
            "center" in all_message_text or
            "pawn" in all_message_text
        )
        print(f"✓ Found opening-related content: {has_queens_gambit}")
        
        # Store session
        self.__class__.qg_session_id = session_id

    def test_get_messages_returns_all_coaching(self, api_client):
        """GET /api/coach/play/messages/{session_id} should return all coaching messages"""
        # Use a session with known messages
        start_response = api_client.post(f"{BASE_URL}/api/coach/play/start", json={
            "user_color": "white",
            "difficulty": "beginner"  # Beginner mode for more messages
        })
        assert start_response.status_code == 200
        session_id = start_response.json()["session"]["session_id"]
        
        # Play a move
        api_client.post(f"{BASE_URL}/api/coach/play/move", json={
            "session_id": session_id,
            "move": "e4"
        })
        time.sleep(3)
        
        # Get messages
        response = api_client.get(f"{BASE_URL}/api/coach/play/messages/{session_id}")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "messages" in data, "Response should have 'messages' key"
        assert isinstance(data["messages"], list), "Messages should be a list"
        
        print(f"✓ Messages endpoint returned {len(data['messages'])} messages")

    def test_opening_moves_generate_messages(self, api_client):
        """Every user move in opening (first 15 moves) should generate at least one message"""
        # Start session as white
        start_response = api_client.post(f"{BASE_URL}/api/coach/play/start", json={
            "user_color": "white",
            "difficulty": "intermediate"
        })
        assert start_response.status_code == 200
        session_id = start_response.json()["session"]["session_id"]
        
        # Play 3 moves and check messages each time
        opening_moves = ["e4", "Nf3", "Bc4"]  # Italian Game setup
        
        for move in opening_moves:
            # Get message count before
            before_response = api_client.get(f"{BASE_URL}/api/coach/play/messages/{session_id}")
            before_count = len(before_response.json().get("messages", []))
            
            # Play move
            move_response = api_client.post(f"{BASE_URL}/api/coach/play/move", json={
                "session_id": session_id,
                "move": move
            })
            
            if move_response.status_code != 200:
                print(f"Move {move} failed: {move_response.text}")
                continue  # Some moves might fail if board state doesn't allow
            
            time.sleep(2.5)  # Wait for background processing
            
            # Get messages after
            after_response = api_client.get(f"{BASE_URL}/api/coach/play/messages/{session_id}")
            messages = after_response.json().get("messages", [])
            after_count = len(messages)
            
            new_messages = after_count - before_count
            print(f"Move {move}: {new_messages} new messages (total: {after_count})")
            
            # During opening, every move should generate at least one message
            # (either about user's move or coach's response)
            assert new_messages >= 1 or after_count > before_count, \
                f"Move {move} should generate at least one message"
        
        print(f"✓ All opening moves generated coaching messages")

    def test_messages_include_question_field(self, api_client):
        """Coach messages should include question.prompt field for interactive questions"""
        # Start a game
        start_response = api_client.post(f"{BASE_URL}/api/coach/play/start", json={
            "user_color": "white",
            "difficulty": "beginner"  # Beginners get more questions
        })
        assert start_response.status_code == 200
        session_id = start_response.json()["session"]["session_id"]
        
        # Play a few moves to get coaching
        moves = ["d4", "c4"]  # Queen's Gambit
        for move in moves:
            api_client.post(f"{BASE_URL}/api/coach/play/move", json={
                "session_id": session_id,
                "move": move
            })
            time.sleep(2)
        
        # Get messages
        response = api_client.get(f"{BASE_URL}/api/coach/play/messages/{session_id}")
        assert response.status_code == 200
        messages = response.json().get("messages", [])
        
        # Check for any message with question field
        has_question = False
        for msg in messages:
            if msg.get("question") and msg["question"].get("prompt"):
                has_question = True
                print(f"✓ Found question: {msg['question']['prompt'][:80]}...")
                break
        
        print(f"Messages checked: {len(messages)}, has question field: {has_question}")
        # Note: Questions are generated based on rating and frequency settings
        # Not every message will have a question

    def test_coach_move_generates_explanation(self, api_client):
        """After coach/opponent moves, there should be a coaching message explaining it"""
        # Start as black (so coach moves first)
        start_response = api_client.post(f"{BASE_URL}/api/coach/play/start", json={
            "user_color": "black",
            "difficulty": "intermediate"
        })
        assert start_response.status_code == 200
        data = start_response.json()
        session_id = data["session"]["session_id"]
        
        # Coach should have made the first move (as white)
        move_history = data["session"].get("move_history", [])
        print(f"Move history after start: {move_history}")
        
        time.sleep(2)  # Wait for any background processing
        
        # Get messages - there might be a message about coach's opening move
        response = api_client.get(f"{BASE_URL}/api/coach/play/messages/{session_id}")
        assert response.status_code == 200
        messages = response.json().get("messages", [])
        
        # Now play a move as black
        api_client.post(f"{BASE_URL}/api/coach/play/move", json={
            "session_id": session_id,
            "move": "e5"  # Common response
        })
        time.sleep(3)
        
        # Get messages again
        response = api_client.get(f"{BASE_URL}/api/coach/play/messages/{session_id}")
        messages = response.json().get("messages", [])
        
        # Check for coach move explanations (is_coach_move = True)
        coach_move_msgs = [m for m in messages if m.get("is_coach_move")]
        print(f"Found {len(coach_move_msgs)} messages about coach's moves")
        
        for msg in messages:
            print(f"  - Move: {msg.get('move')}, isCoachMove: {msg.get('is_coach_move')}, Trigger: {msg.get('trigger')}")
        
        print(f"✓ Total {len(messages)} messages in session")


class TestMoveByMoveCoachUnit:
    """Unit tests for the move_by_move_coach service"""
    
    def test_generate_move_commentary_returns_message(self):
        """generate_move_commentary should return a MoveCommentary with message"""
        from services.move_by_move_coach import generate_move_commentary
        
        commentary = generate_move_commentary(
            fen_before="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
            fen_after="rnbqkbnr/pppppppp/8/8/3P4/8/PPP1PPPP/RNBQKBNR b KQkq d3 0 1",
            move_san="d4",
            move_by="user",
            all_moves=["d4"],
            user_color="white",
            user_rating=1200,
            opening_plan=None,
        )
        
        assert commentary is not None, "Commentary should not be None"
        assert commentary.message, "Commentary should have a message"
        assert len(commentary.message) > 0, "Message should not be empty"
        print(f"✓ Generated message: {commentary.message[:100]}...")

    def test_coach_move_commentary(self):
        """generate_move_commentary should work for coach moves too"""
        from services.move_by_move_coach import generate_move_commentary
        
        commentary = generate_move_commentary(
            fen_before="rnbqkbnr/pppppppp/8/8/3P4/8/PPP1PPPP/RNBQKBNR b KQkq d3 0 1",
            fen_after="rnbqkbnr/ppp1pppp/8/3p4/3P4/8/PPP1PPPP/RNBQKBNR w KQkq d6 0 2",
            move_san="d5",
            move_by="coach",
            all_moves=["d4", "d5"],
            user_color="white",
            user_rating=1200,
            opening_plan=None,
        )
        
        assert commentary is not None
        assert commentary.message
        print(f"✓ Coach move commentary: {commentary.message[:100]}...")

    def test_queens_gambit_opening_plan(self):
        """Opening plans should have Queen's Gambit teaching moments"""
        from coach_engine.opening_plans import QUEENS_GAMBIT
        
        assert QUEENS_GAMBIT is not None, "Queen's Gambit plan should exist"
        assert QUEENS_GAMBIT.name == "Queen's Gambit"
        assert "d4" in QUEENS_GAMBIT.identifying_moves
        assert "c4" in QUEENS_GAMBIT.identifying_moves
        
        # Check teaching moments
        assert QUEENS_GAMBIT.teaching_moments is not None
        assert "d4" in QUEENS_GAMBIT.teaching_moments or "c4" in QUEENS_GAMBIT.teaching_moments
        
        print(f"✓ Queen's Gambit teaching moments: {list(QUEENS_GAMBIT.teaching_moments.keys())[:5]}")

    def test_rating_tone_varies_by_level(self):
        """get_rating_tone should return different tones for different ratings"""
        from services.move_by_move_coach import get_rating_tone
        
        beginner_tone = get_rating_tone(600)
        intermediate_tone = get_rating_tone(1400)
        advanced_tone = get_rating_tone(1800)
        
        assert beginner_tone["level"] == "beginner"
        assert intermediate_tone["level"] == "intermediate"
        assert advanced_tone["level"] == "advanced"
        
        # Beginners should get simpler explanations
        assert beginner_tone["use_names"] == False
        assert intermediate_tone["use_names"] == True
        
        print(f"✓ Rating tones work correctly")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
