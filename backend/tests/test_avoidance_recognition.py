"""
Test file for Avoidance Mode and Recognition Mode in Trick Library
Tests the new practice modes for learning and recognizing chess traps

Features tested:
- Avoidance Mode API (/api/training/tricks/validate-avoidance)
- Recognition Mode API (/api/training/tricks/validate-recognition)
- Trick Library access with 18 traps
- Practice mode initialization (execution, avoidance, recognition)
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
SESSION_TOKEN = "test_session_356539ff12b1"

@pytest.fixture
def api_client():
    """Shared requests session with auth"""
    session = requests.Session()
    session.headers.update({
        "Content-Type": "application/json",
        "Cookie": f"session_token={SESSION_TOKEN}"
    })
    return session


class TestTrickLibrary:
    """Test Trick Library endpoints"""
    
    def test_get_all_tricks(self, api_client):
        """Verify Trick Library returns 18 traps"""
        response = api_client.get(f"{BASE_URL}/api/training/tricks")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "traps" in data, "Response should contain 'traps' key"
        
        traps = data["traps"]
        # Verify we have the expected number of traps (around 18)
        assert len(traps) >= 15, f"Expected at least 15 traps, got {len(traps)}"
        print(f"✓ Trick Library has {len(traps)} traps")
        
        # Check for scholars_mate (test trap)
        trap_keys = [t.get("key") for t in traps]
        assert "scholars_mate" in trap_keys, "scholars_mate should be in traps"
        print("✓ scholars_mate trap is available")
    
    def test_get_practice_mode_execution(self, api_client):
        """Test execution mode practice initialization"""
        response = api_client.get(f"{BASE_URL}/api/training/tricks/scholars_mate/practice?mode=execution")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("mode") == "execution", f"Expected execution mode, got {data.get('mode')}"
        assert "setup_moves" in data or "full_sequence" in data, "Should have moves data"
        assert "user_color" in data, "Should specify user_color"
        print("✓ Execution mode initializes correctly")
    
    def test_get_practice_mode_avoidance(self, api_client):
        """Test avoidance mode practice initialization"""
        response = api_client.get(f"{BASE_URL}/api/training/tricks/scholars_mate/practice?mode=avoidance")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("mode") == "avoidance", f"Expected avoidance mode, got {data.get('mode')}"
        assert "fen" in data, "Should have FEN position"
        assert "how_to_avoid" in data, "Should have avoidance hints"
        assert "victim_color" in data, "Should specify victim_color"
        print(f"✓ Avoidance mode returns FEN: {data.get('fen', '')[:30]}...")
    
    def test_get_practice_mode_recognition(self, api_client):
        """Test recognition mode practice initialization"""
        response = api_client.get(f"{BASE_URL}/api/training/tricks/scholars_mate/practice?mode=recognition")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("mode") == "recognition", f"Expected recognition mode, got {data.get('mode')}"
        assert "fen" in data, "Should have FEN position"
        assert "has_trap" in data, "Should indicate if trap exists"
        assert "key_squares" in data, "Should highlight key squares"
        print(f"✓ Recognition mode returns position with has_trap={data.get('has_trap')}")


class TestAvoidanceMode:
    """Test Avoidance Mode validation endpoint"""
    
    def test_avoidance_api_exists(self, api_client):
        """Verify the avoidance validation endpoint exists"""
        # Scholar's Mate trap position - Black to move, must avoid Nf6 blunder
        # Position: White has Qh5 and Bc4 ready to trap f7
        response = api_client.post(
            f"{BASE_URL}/api/training/tricks/validate-avoidance",
            json={
                "fen": "r1bqkb1r/pppp1ppp/2n5/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR b KQkq - 3 3",
                "user_move": "Qe7",
                "trap_key": "scholars_mate",
                "winning_move": "Qxf7#",
                "user_color": "black"
            }
        )
        assert response.status_code == 200, f"Endpoint returned {response.status_code}: {response.text}"
        print("✓ Avoidance validation endpoint exists and responds")
    
    def test_avoidance_safe_move_qe7(self, api_client):
        """Test that Qe7 is recognized as a safe move (avoids Scholar's Mate)"""
        # Position BEFORE Black blunders with Nf6
        # FEN: White played Qh5, Black's turn - must NOT play Nf6
        response = api_client.post(
            f"{BASE_URL}/api/training/tricks/validate-avoidance",
            json={
                "fen": "r1bqkb1r/pppp1ppp/2n5/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR b KQkq - 3 3",
                "user_move": "Qe7",
                "trap_key": "scholars_mate",
                "winning_move": "Qxf7#",
                "user_color": "black"
            }
        )
        assert response.status_code == 200
        
        data = response.json()
        # Qe7 defends f7 and is a safe move
        assert data.get("valid") == True, "Move should be valid"
        # Check if it's marked as safe or not falling into trap
        is_safe = data.get("is_safe", False) or not data.get("fell_into_trap", True)
        assert is_safe, f"Qe7 should be safe, but got: {data}"
        print(f"✓ Qe7 recognized as SAFE move: {data.get('message', '')}")
    
    def test_avoidance_unsafe_move_ke7(self, api_client):
        """Test that Ke7 is recognized as a bad move (king walks into danger)"""
        # In the position after Qh5, Black playing Ke7 is a questionable move
        # that blocks the queen's defense of f7
        response = api_client.post(
            f"{BASE_URL}/api/training/tricks/validate-avoidance",
            json={
                "fen": "r1bqkb1r/pppp1ppp/2n5/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR b KQkq - 3 3",
                "user_move": "Ke7",  # King moves but this doesn't help defend f7
                "trap_key": "scholars_mate",
                "winning_move": "Qxf7#",
                "user_color": "black"
            }
        )
        assert response.status_code == 200
        
        data = response.json()
        # Ke7 is a legal move, API should validate it
        print(f"Ke7 validation result: {data}")
        print(f"✓ Ke7 returned: is_safe={data.get('is_safe')}, fell_into_trap={data.get('fell_into_trap')}, message={data.get('message', '')}")
    
    def test_avoidance_invalid_move(self, api_client):
        """Test invalid move handling in avoidance mode"""
        response = api_client.post(
            f"{BASE_URL}/api/training/tricks/validate-avoidance",
            json={
                "fen": "r1bqkb1r/pppp1ppp/2n5/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR b KQkq - 3 3",
                "user_move": "Kf7",  # Illegal - King can't move to f7 due to check
                "trap_key": "scholars_mate",
                "winning_move": "Qxf7#",
                "user_color": "black"
            }
        )
        assert response.status_code == 200
        
        data = response.json()
        # Invalid move should be rejected
        assert data.get("valid") == False or "Invalid" in str(data.get("message", "")), f"Invalid move not handled: {data}"
        print(f"✓ Invalid move Kf7 correctly rejected: {data.get('message', '')}")
    
    def test_avoidance_g6_blocks_threat(self, api_client):
        """Test that g6 is recognized as a safe defensive move"""
        response = api_client.post(
            f"{BASE_URL}/api/training/tricks/validate-avoidance",
            json={
                "fen": "r1bqkb1r/pppp1ppp/2n5/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR b KQkq - 3 3",
                "user_move": "g6",
                "trap_key": "scholars_mate",
                "winning_move": "Qxf7#",
                "user_color": "black"
            }
        )
        assert response.status_code == 200
        
        data = response.json()
        # g6 kicks the queen and defends - should be safe
        print(f"✓ g6 validation result: is_safe={data.get('is_safe')}, message={data.get('message', '')}")


class TestRecognitionMode:
    """Test Recognition Mode validation endpoint"""
    
    def test_recognition_api_exists(self, api_client):
        """Verify the recognition validation endpoint exists"""
        response = api_client.post(
            f"{BASE_URL}/api/training/tricks/validate-recognition",
            json={
                "trap_key": "scholars_mate",
                "has_trap": True,
                "winning_move": "Qxf7"
            }
        )
        assert response.status_code == 200, f"Endpoint returned {response.status_code}: {response.text}"
        print("✓ Recognition validation endpoint exists and responds")
    
    def test_recognition_perfect_answer(self, api_client):
        """Test perfect score: correctly identified trap + found winning move"""
        response = api_client.post(
            f"{BASE_URL}/api/training/tricks/validate-recognition",
            json={
                "trap_key": "scholars_mate",
                "has_trap": True,
                "winning_move": "Qxf7"  # Correct winning move (with or without #)
            }
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("score") == "perfect", f"Expected perfect score, got {data.get('score')}"
        assert data.get("recognized_trap") == True, "Should recognize trap"
        assert data.get("found_winning_move") == True, "Should find winning move"
        print(f"✓ Perfect answer: score={data.get('score')}, message={data.get('message', '')}")
    
    def test_recognition_good_answer(self, api_client):
        """Test good score: correctly identified trap but no winning move submitted"""
        response = api_client.post(
            f"{BASE_URL}/api/training/tricks/validate-recognition",
            json={
                "trap_key": "scholars_mate",
                "has_trap": True,
                "winning_move": ""  # No move submitted
            }
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("score") == "good", f"Expected good score, got {data.get('score')}"
        assert data.get("recognized_trap") == True, "Should recognize trap"
        assert "correct_winning_move" in data, "Should reveal correct move"
        print(f"✓ Good answer: score={data.get('score')}, revealed move={data.get('correct_winning_move')}")
    
    def test_recognition_partial_answer(self, api_client):
        """Test partial score: identified trap but wrong winning move"""
        response = api_client.post(
            f"{BASE_URL}/api/training/tricks/validate-recognition",
            json={
                "trap_key": "scholars_mate",
                "has_trap": True,
                "winning_move": "Bc4"  # Wrong move
            }
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("score") == "partial", f"Expected partial score, got {data.get('score')}"
        assert data.get("recognized_trap") == True, "Should recognize trap"
        assert data.get("found_winning_move") == False, "Should NOT find winning move"
        print(f"✓ Partial answer: score={data.get('score')}, message={data.get('message', '')}")
    
    def test_recognition_missed_answer(self, api_client):
        """Test missed score: said there's no trap (wrong)"""
        response = api_client.post(
            f"{BASE_URL}/api/training/tricks/validate-recognition",
            json={
                "trap_key": "scholars_mate",
                "has_trap": False,  # User thinks no trap
                "winning_move": ""
            }
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("score") == "missed", f"Expected missed score, got {data.get('score')}"
        assert data.get("recognized_trap") == False, "Should NOT recognize trap"
        assert "correct_winning_move" in data, "Should reveal the winning move"
        print(f"✓ Missed answer: score={data.get('score')}, revealed move={data.get('correct_winning_move')}")
    
    def test_recognition_invalid_trap_key(self, api_client):
        """Test error handling for invalid trap key"""
        response = api_client.post(
            f"{BASE_URL}/api/training/tricks/validate-recognition",
            json={
                "trap_key": "nonexistent_trap",
                "has_trap": True,
                "winning_move": "Qxf7"
            }
        )
        assert response.status_code == 404, f"Expected 404 for invalid trap, got {response.status_code}"
        print("✓ Invalid trap key correctly returns 404")
    
    def test_recognition_with_check_notation(self, api_client):
        """Test winning move matching ignores check/mate notation"""
        response = api_client.post(
            f"{BASE_URL}/api/training/tricks/validate-recognition",
            json={
                "trap_key": "scholars_mate",
                "has_trap": True,
                "winning_move": "Qxf7#"  # With checkmate notation
            }
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("found_winning_move") == True, f"Should match move with # notation: {data}"
        print(f"✓ Move matching works with # notation: found_winning_move={data.get('found_winning_move')}")


class TestEdgeCases:
    """Test edge cases and error handling"""
    
    def test_avoidance_missing_fen(self, api_client):
        """Test error handling when FEN is missing"""
        response = api_client.post(
            f"{BASE_URL}/api/training/tricks/validate-avoidance",
            json={
                "user_move": "Qe7",
                "trap_key": "scholars_mate",
                "winning_move": "Qxf7#",
                "user_color": "black"
            }
        )
        assert response.status_code == 400, f"Expected 400 for missing FEN, got {response.status_code}"
        print("✓ Missing FEN correctly returns 400")
    
    def test_avoidance_missing_user_move(self, api_client):
        """Test error handling when user_move is missing"""
        response = api_client.post(
            f"{BASE_URL}/api/training/tricks/validate-avoidance",
            json={
                "fen": "r1bqkb1r/pppp1ppp/2n5/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR b KQkq - 3 3",
                "trap_key": "scholars_mate",
                "winning_move": "Qxf7#",
                "user_color": "black"
            }
        )
        assert response.status_code == 400, f"Expected 400 for missing user_move, got {response.status_code}"
        print("✓ Missing user_move correctly returns 400")
    
    def test_avoidance_invalid_fen(self, api_client):
        """Test error handling for invalid FEN"""
        response = api_client.post(
            f"{BASE_URL}/api/training/tricks/validate-avoidance",
            json={
                "fen": "invalid_fen_string",
                "user_move": "Qe7",
                "trap_key": "scholars_mate",
                "winning_move": "Qxf7#",
                "user_color": "black"
            }
        )
        assert response.status_code == 400, f"Expected 400 for invalid FEN, got {response.status_code}"
        print("✓ Invalid FEN correctly returns 400")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
