"""
Game Decryption Feature Tests
=============================

Tests for the Game Decryption feature that explains every move of a chess game in plain English.

Endpoints tested:
- GET /api/coach/decryption/{gameId} - returns move-by-move coaching for all moves
- POST /api/coach/decryption/feedback - submit 'not helpful' feedback with correction
- GET /api/coach/decryption/feedback/{gameId} - get feedback for a game

Test game_id: 0da0f930-b9b5-4940-be50-a1c2ea6e5e62
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://plateau-breaker-2.preview.emergentagent.com').rstrip('/')
TEST_GAME_ID = "0da0f930-b9b5-4940-be50-a1c2ea6e5e62"


@pytest.fixture
def api_client():
    """Shared requests session with auth cookie"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    session.cookies.set("session_token", "test")
    return session


class TestGameDecryptionAPI:
    """Tests for Game Decryption endpoints"""
    
    def test_get_decryption_returns_200(self, api_client):
        """Test GET /api/coach/decryption/{gameId} returns 200"""
        response = api_client.get(f"{BASE_URL}/api/coach/decryption/{TEST_GAME_ID}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Should have either decryption_data or error
        assert "decryption_data" in data or "error" in data, "Response should have decryption_data or error"
    
    def test_decryption_data_structure(self, api_client):
        """Test decryption data has correct structure"""
        response = api_client.get(f"{BASE_URL}/api/coach/decryption/{TEST_GAME_ID}")
        
        assert response.status_code == 200
        data = response.json()
        
        # If decryption data exists, verify structure
        if data.get("decryption_data"):
            decryption_data = data["decryption_data"]
            assert isinstance(decryption_data, list), "decryption_data should be a list"
            
            if len(decryption_data) > 0:
                first_move = decryption_data[0]
                
                # Required fields for each move
                required_fields = [
                    "move_number",
                    "is_user_move",
                    "move_san",
                    "fen_before",
                    "fen_after",
                    "phase",
                    "what_happened",
                    "move_idea"
                ]
                
                for field in required_fields:
                    assert field in first_move, f"Missing required field: {field}"
                
                # Verify types
                assert isinstance(first_move["move_number"], int), "move_number should be int"
                assert isinstance(first_move["is_user_move"], bool), "is_user_move should be bool"
                assert isinstance(first_move["move_san"], str), "move_san should be string"
                assert isinstance(first_move["what_happened"], str), "what_happened should be string"
                
                print(f"First move: {first_move['move_san']} - {first_move['what_happened']}")
    
    def test_decryption_summary_structure(self, api_client):
        """Test decryption summary has correct structure"""
        response = api_client.get(f"{BASE_URL}/api/coach/decryption/{TEST_GAME_ID}")
        
        assert response.status_code == 200
        data = response.json()
        
        # If summary exists, verify structure
        if data.get("summary"):
            summary = data["summary"]
            
            # Expected summary fields
            expected_fields = ["total_moves", "user_moves", "mistakes", "good_moves"]
            
            for field in expected_fields:
                assert field in summary, f"Summary missing field: {field}"
            
            # Verify types
            assert isinstance(summary["total_moves"], int), "total_moves should be int"
            assert isinstance(summary["mistakes"], int), "mistakes should be int"
            assert isinstance(summary["good_moves"], int), "good_moves should be int"
            
            print(f"Summary: {summary['total_moves']} moves, {summary['mistakes']} mistakes, {summary['good_moves']} good moves")
    
    def test_decryption_move_coaching_fields(self, api_client):
        """Test move coaching has all expected coaching fields"""
        response = api_client.get(f"{BASE_URL}/api/coach/decryption/{TEST_GAME_ID}")
        
        assert response.status_code == 200
        data = response.json()
        
        if data.get("decryption_data") and len(data["decryption_data"]) > 0:
            # Find a user move
            user_moves = [m for m in data["decryption_data"] if m.get("is_user_move")]
            
            if user_moves:
                user_move = user_moves[0]
                
                # Coaching fields that should be present
                coaching_fields = [
                    "your_focus",
                    "is_mistake",
                    "is_good_move"
                ]
                
                for field in coaching_fields:
                    assert field in user_move, f"User move missing coaching field: {field}"
                
                print(f"User move {user_move['move_san']}: focus='{user_move.get('your_focus', '')[:50]}...'")
    
    def test_decryption_mistake_fields(self, api_client):
        """Test mistake moves have proper mistake fields"""
        response = api_client.get(f"{BASE_URL}/api/coach/decryption/{TEST_GAME_ID}")
        
        assert response.status_code == 200
        data = response.json()
        
        if data.get("decryption_data"):
            # Find a mistake
            mistakes = [m for m in data["decryption_data"] if m.get("is_mistake")]
            
            if mistakes:
                mistake = mistakes[0]
                
                # Mistake-specific fields
                mistake_fields = [
                    "cp_loss",
                    "mistake_type",
                    "what_you_missed",
                    "better_move",
                    "principle"
                ]
                
                for field in mistake_fields:
                    assert field in mistake, f"Mistake missing field: {field}"
                
                print(f"Mistake at move {mistake['move_number']}: {mistake['move_san']} - {mistake.get('what_you_missed', '')[:50]}...")
            else:
                print("No mistakes found in game - skipping mistake field validation")
    
    def test_decryption_nonexistent_game(self, api_client):
        """Test decryption for non-existent game returns appropriate response"""
        response = api_client.get(f"{BASE_URL}/api/coach/decryption/nonexistent-game-id-12345")
        
        assert response.status_code == 200, "Should return 200 even for non-existent game"
        data = response.json()
        
        # Should have error or null decryption_data
        assert data.get("error") or data.get("decryption_data") is None, "Should indicate game not found"
        print(f"Non-existent game response: {data.get('error', 'No error message')}")


class TestDecryptionFeedbackAPI:
    """Tests for Decryption Feedback endpoints"""
    
    def test_submit_feedback_returns_200(self, api_client):
        """Test POST /api/coach/decryption/feedback returns 200"""
        feedback_payload = {
            "game_id": TEST_GAME_ID,
            "move_number": 1,
            "fen": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
            "coach_explanation": "Advanced the king pawn two squares",
            "user_feedback": "not_helpful",
            "user_correction": "This is a test correction for the explanation",
            "is_user_move": True
        }
        
        response = api_client.post(
            f"{BASE_URL}/api/coach/decryption/feedback",
            json=feedback_payload
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert data.get("success") == True, "Feedback submission should succeed"
        assert "message" in data, "Response should have message"
        print(f"Feedback response: {data.get('message')}")
    
    def test_get_feedback_for_game(self, api_client):
        """Test GET /api/coach/decryption/feedback/{gameId} returns feedback"""
        response = api_client.get(f"{BASE_URL}/api/coach/decryption/feedback/{TEST_GAME_ID}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert "feedback" in data, "Response should have feedback array"
        assert isinstance(data["feedback"], list), "feedback should be a list"
        
        if len(data["feedback"]) > 0:
            feedback_item = data["feedback"][0]
            assert "game_id" in feedback_item, "Feedback item should have game_id"
            assert "move_number" in feedback_item, "Feedback item should have move_number"
            print(f"Found {len(data['feedback'])} feedback items for game")
        else:
            print("No feedback found for game")
    
    def test_submit_feedback_validation(self, api_client):
        """Test feedback submission validates required fields"""
        # Missing required fields
        incomplete_payload = {
            "game_id": TEST_GAME_ID,
            "move_number": 1
            # Missing fen, coach_explanation, user_feedback
        }
        
        response = api_client.post(
            f"{BASE_URL}/api/coach/decryption/feedback",
            json=incomplete_payload
        )
        
        # Should return 422 for validation error
        assert response.status_code in [422, 400], f"Expected validation error, got {response.status_code}"
        print(f"Validation error response: {response.status_code}")


class TestOnDemandDecryption:
    """Tests for on-demand decryption generation"""
    
    def test_decryption_generated_on_demand(self, api_client):
        """Test that decryption is generated on-demand for games without it"""
        response = api_client.get(f"{BASE_URL}/api/coach/decryption/{TEST_GAME_ID}")
        
        assert response.status_code == 200
        data = response.json()
        
        # Check if generated_on_demand flag is present
        if data.get("generated_on_demand"):
            print("Decryption was generated on-demand")
            assert data.get("decryption_data") is not None, "On-demand generation should produce data"
        elif data.get("decryption_data"):
            print("Decryption was already cached")
        else:
            print(f"Decryption not available: {data.get('error', 'Unknown reason')}")
    
    def test_decryption_has_generated_at_timestamp(self, api_client):
        """Test that decryption response includes generated_at timestamp"""
        response = api_client.get(f"{BASE_URL}/api/coach/decryption/{TEST_GAME_ID}")
        
        assert response.status_code == 200
        data = response.json()
        
        if data.get("decryption_data"):
            assert "generated_at" in data, "Response should have generated_at timestamp"
            print(f"Generated at: {data.get('generated_at')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
