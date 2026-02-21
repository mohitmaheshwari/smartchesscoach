"""
Test Suite for Puzzle Validation API with Smart Stockfish Feedback

Tests the following scenarios:
1. Correct move is accepted (returns correct: true)
2. Wrong move is rejected (returns correct: false)
3. Smart feedback with eval_diff and move_quality is provided
4. Different move quality classifications work properly
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
SESSION_TOKEN = "test_session_356539ff12b1"


class TestPuzzleValidationAPI:
    """Tests for /api/training/puzzle/validate endpoint"""
    
    @pytest.fixture
    def api_client(self):
        """Setup requests session with auth"""
        session = requests.Session()
        session.headers.update({
            "Content-Type": "application/json",
            "Cookie": f"session_token={SESSION_TOKEN}"
        })
        return session
    
    def test_correct_move_accepted(self, api_client):
        """Test that the exact correct move returns correct: true"""
        # Starting position - e4 is one of the best moves
        response = api_client.post(f"{BASE_URL}/api/training/puzzle/validate", json={
            "puzzle_id": "test_1",
            "user_answer": "e4",
            "correct_move": "e4",
            "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        })
        
        assert response.status_code == 200
        data = response.json()
        
        # Exact match should be correct
        assert data["correct"] == True
        assert data["move_quality"] == "perfect"
        assert "user_move" in data
        assert "correct_move" in data
        assert "explanation" in data
        
    def test_wrong_move_rejected(self, api_client):
        """Test that an obviously wrong move returns correct: false"""
        # In the Fried Liver attack position, not playing Nxf7 is a blunder
        # Position: White has Qh5 and Bc4, threatening Qxf7# or Nf7 fork
        response = api_client.post(f"{BASE_URL}/api/training/puzzle/validate", json={
            "puzzle_id": "test_2",
            "user_answer": "a3",  # Random bad move
            "correct_move": "Nxf7",  # Knight fork wins the queen
            "fen": "r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 4 4"
        })
        
        assert response.status_code == 200
        data = response.json()
        
        # Should be marked as incorrect
        assert data["correct"] == False
        assert data["move_quality"] == "blunder"
        assert "eval_diff" in data
        assert data["eval_diff"] > 300  # Should show significant loss
        
    def test_good_move_accepted(self, api_client):
        """Test that a good (but not best) move is marked as correct"""
        # Starting position - d4 is good but e4 might be slightly preferred
        response = api_client.post(f"{BASE_URL}/api/training/puzzle/validate", json={
            "puzzle_id": "test_3",
            "user_answer": "d4",
            "correct_move": "e4",
            "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        })
        
        assert response.status_code == 200
        data = response.json()
        
        # d4 should be marked as good/acceptable (both are main line moves)
        assert "move_quality" in data
        assert data["move_quality"] in ["perfect", "excellent", "good", "acceptable"]
        # correct should be True for good moves
        if data["move_quality"] in ["perfect", "excellent", "good"]:
            assert data["correct"] == True
            
    def test_smart_feedback_includes_eval_diff(self, api_client):
        """Test that response includes evaluation difference in centipawns"""
        response = api_client.post(f"{BASE_URL}/api/training/puzzle/validate", json={
            "puzzle_id": "test_4",
            "user_answer": "a4",  # Weak move
            "correct_move": "e4",
            "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        })
        
        assert response.status_code == 200
        data = response.json()
        
        # Should include eval_diff
        assert "eval_diff" in data
        assert isinstance(data["eval_diff"], (int, float))
        
        # Should include quality text
        assert "quality_text" in data
        assert len(data["quality_text"]) > 0
        
    def test_move_quality_classification(self, api_client):
        """Test that move quality is properly classified"""
        response = api_client.post(f"{BASE_URL}/api/training/puzzle/validate", json={
            "puzzle_id": "test_5",
            "user_answer": "h4",  # Dubious move
            "correct_move": "e4",
            "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        })
        
        assert response.status_code == 200
        data = response.json()
        
        # Move quality should be one of the defined classifications
        valid_qualities = ["perfect", "excellent", "good", "acceptable", "inaccuracy", "mistake", "blunder"]
        assert data["move_quality"] in valid_qualities
        
    def test_explanation_provided(self, api_client):
        """Test that explanatory text is provided for wrong moves"""
        response = api_client.post(f"{BASE_URL}/api/training/puzzle/validate", json={
            "puzzle_id": "test_6",
            "user_answer": "a3",
            "correct_move": "Nxf7",
            "fen": "r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 4 4"
        })
        
        assert response.status_code == 200
        data = response.json()
        
        # Should have explanation
        assert "explanation" in data
        assert len(data["explanation"]) > 10  # Non-trivial explanation
        
    def test_invalid_move_returns_error(self, api_client):
        """Test that an invalid move notation returns appropriate error"""
        response = api_client.post(f"{BASE_URL}/api/training/puzzle/validate", json={
            "puzzle_id": "test_7",
            "user_answer": "xyz123",  # Invalid move
            "correct_move": "e4",
            "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        })
        
        assert response.status_code == 200
        data = response.json()
        
        # Should indicate the move is invalid
        assert data["correct"] == False
        assert "invalid" in data.get("message", "").lower() or "Invalid" in data.get("message", "")


class TestStockfishEngineIntegration:
    """Tests for Stockfish engine integration in puzzle validation"""
    
    @pytest.fixture
    def api_client(self):
        """Setup requests session with auth"""
        session = requests.Session()
        session.headers.update({
            "Content-Type": "application/json",
            "Cookie": f"session_token={SESSION_TOKEN}"
        })
        return session
    
    def test_stockfish_evaluates_mate_in_one(self, api_client):
        """Test Stockfish properly evaluates mate-in-1 positions"""
        # Position where Qxf7# is mate in 1
        # Scholar's mate position
        response = api_client.post(f"{BASE_URL}/api/training/puzzle/validate", json={
            "puzzle_id": "mate_test",
            "user_answer": "Qxf7",  # Checkmate
            "correct_move": "Qxf7",
            "fen": "r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5Q2/PPPP1PPP/RNB1K1NR w KQkq - 4 4"
        })
        
        assert response.status_code == 200
        data = response.json()
        
        # Checkmate should be correct
        assert data["correct"] == True
        
    def test_stockfish_detects_blunder(self, api_client):
        """Test Stockfish properly detects blunders (>300 cp loss)"""
        response = api_client.post(f"{BASE_URL}/api/training/puzzle/validate", json={
            "puzzle_id": "blunder_test",
            "user_answer": "a3",  # Terrible move in this position
            "correct_move": "Nxf7",  # Wins queen
            "fen": "r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 4 4"
        })
        
        assert response.status_code == 200
        data = response.json()
        
        # Should be classified as blunder
        assert data["move_quality"] == "blunder"
        assert data["correct"] == False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
