"""
Test Interactive Coaching Panel API - POST /api/coach/play/v5/interactive-feedback

This endpoint provides two-part coaching:
1. user_move_coaching - Feedback on user's last move
2. coach_move_coaching - Explanation of coach's last move

Tests verify the endpoint returns correct structure and data.
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://thinking-sim.preview.emergentagent.com')

# Test user credentials
DEV_USER_COOKIE = {"dev_user_id": "user_62852a1b64e7"}


class TestInteractiveCoachingAPI:
    """Tests for POST /api/coach/play/v5/interactive-feedback endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session"""
        self.session = requests.Session()
        self.session.cookies.update(DEV_USER_COOKIE)
        self.session.headers.update({"Content-Type": "application/json"})
    
    def test_interactive_feedback_endpoint_exists(self):
        """Test that the endpoint exists and responds"""
        # First start a game
        start_response = self.session.post(
            f"{BASE_URL}/api/coach/play/start",
            json={"user_color": "white", "time_control": "15+10"}
        )
        assert start_response.status_code == 200, f"Failed to start game: {start_response.text}"
        
        session_data = start_response.json()
        session_id = session_data["session_id"]
        
        # Test the interactive-feedback endpoint
        response = self.session.post(
            f"{BASE_URL}/api/coach/play/v5/interactive-feedback",
            json={"session_id": session_id}
        )
        
        assert response.status_code == 200, f"Endpoint returned {response.status_code}: {response.text}"
        print(f"✓ Interactive feedback endpoint exists and responds with 200")
    
    def test_interactive_feedback_returns_correct_structure(self):
        """Test that response has user_move_coaching, coach_move_coaching, is_user_turn"""
        # Start a game
        start_response = self.session.post(
            f"{BASE_URL}/api/coach/play/start",
            json={"user_color": "white", "time_control": "15+10"}
        )
        session_id = start_response.json()["session_id"]
        
        # Get interactive feedback
        response = self.session.post(
            f"{BASE_URL}/api/coach/play/v5/interactive-feedback",
            json={"session_id": session_id}
        )
        
        data = response.json()
        
        # Check required fields exist
        assert "user_move_coaching" in data, "Missing user_move_coaching field"
        assert "coach_move_coaching" in data, "Missing coach_move_coaching field"
        assert "is_user_turn" in data, "Missing is_user_turn field"
        
        print(f"✓ Response has correct structure: user_move_coaching, coach_move_coaching, is_user_turn")
    
    def test_interactive_feedback_after_move_cycle(self):
        """Test feedback after user move + coach response"""
        # Start a game
        start_response = self.session.post(
            f"{BASE_URL}/api/coach/play/start",
            json={"user_color": "white", "time_control": "15+10"}
        )
        session_id = start_response.json()["session_id"]
        
        # Make a move (e4)
        move_response = self.session.post(
            f"{BASE_URL}/api/coach/play/move",
            json={"session_id": session_id, "move": "e4", "thinking_time_ms": 2000}
        )
        assert move_response.status_code == 200, f"Move failed: {move_response.text}"
        
        # Wait for coach to respond
        time.sleep(5)
        
        # Get interactive feedback
        response = self.session.post(
            f"{BASE_URL}/api/coach/play/v5/interactive-feedback",
            json={"session_id": session_id}
        )
        
        data = response.json()
        
        # After a move cycle, coach_move_coaching should have data
        assert data.get("coach_move_coaching") is not None, "coach_move_coaching should have data after coach moves"
        
        coach_coaching = data["coach_move_coaching"]
        assert "move_san" in coach_coaching, "coach_move_coaching missing move_san"
        assert "explanation" in coach_coaching, "coach_move_coaching missing explanation"
        
        print(f"✓ Coach move coaching returned: {coach_coaching.get('move_san')} - {coach_coaching.get('explanation')[:50]}...")
    
    def test_coach_move_coaching_has_required_fields(self):
        """Test that coach_move_coaching has all required fields"""
        # Start a game
        start_response = self.session.post(
            f"{BASE_URL}/api/coach/play/start",
            json={"user_color": "white", "time_control": "15+10"}
        )
        session_id = start_response.json()["session_id"]
        
        # Make a move
        self.session.post(
            f"{BASE_URL}/api/coach/play/move",
            json={"session_id": session_id, "move": "e4", "thinking_time_ms": 2000}
        )
        
        # Wait for coach
        time.sleep(5)
        
        # Get feedback
        response = self.session.post(
            f"{BASE_URL}/api/coach/play/v5/interactive-feedback",
            json={"session_id": session_id}
        )
        
        data = response.json()
        coach_coaching = data.get("coach_move_coaching", {})
        
        # Check required fields for coach move explanation
        required_fields = ["move_san", "explanation"]
        optional_fields = ["plan", "threats", "teaching_point", "hint_for_user"]
        
        for field in required_fields:
            assert field in coach_coaching, f"coach_move_coaching missing required field: {field}"
        
        print(f"✓ coach_move_coaching has required fields: {required_fields}")
        
        # Check optional fields
        present_optional = [f for f in optional_fields if f in coach_coaching]
        print(f"✓ coach_move_coaching has optional fields: {present_optional}")
    
    def test_is_user_turn_correct_after_coach_move(self):
        """Test that is_user_turn is True after coach makes a move"""
        # Start a game
        start_response = self.session.post(
            f"{BASE_URL}/api/coach/play/start",
            json={"user_color": "white", "time_control": "15+10"}
        )
        session_id = start_response.json()["session_id"]
        
        # Make a move
        self.session.post(
            f"{BASE_URL}/api/coach/play/move",
            json={"session_id": session_id, "move": "e4", "thinking_time_ms": 2000}
        )
        
        # Wait for coach
        time.sleep(5)
        
        # Get feedback
        response = self.session.post(
            f"{BASE_URL}/api/coach/play/v5/interactive-feedback",
            json={"session_id": session_id}
        )
        
        data = response.json()
        
        # After coach moves, it should be user's turn
        assert data.get("is_user_turn") == True, f"is_user_turn should be True after coach moves, got {data.get('is_user_turn')}"
        
        print(f"✓ is_user_turn is correctly True after coach move")
    
    def test_session_id_required(self):
        """Test that session_id is required"""
        response = self.session.post(
            f"{BASE_URL}/api/coach/play/v5/interactive-feedback",
            json={}
        )
        
        assert response.status_code == 400, f"Expected 400 for missing session_id, got {response.status_code}"
        print(f"✓ Endpoint correctly requires session_id")
    
    def test_invalid_session_returns_404(self):
        """Test that invalid session_id returns 404"""
        response = self.session.post(
            f"{BASE_URL}/api/coach/play/v5/interactive-feedback",
            json={"session_id": "invalid-session-id-12345"}
        )
        
        assert response.status_code == 404, f"Expected 404 for invalid session, got {response.status_code}"
        print(f"✓ Endpoint correctly returns 404 for invalid session")


class TestInteractiveCoachingPanelIntegration:
    """Integration tests for the full coaching flow"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session"""
        self.session = requests.Session()
        self.session.cookies.update(DEV_USER_COOKIE)
        self.session.headers.update({"Content-Type": "application/json"})
    
    def test_full_move_cycle_coaching(self):
        """Test complete move cycle: user move -> coach response -> get coaching"""
        # Start game
        start_response = self.session.post(
            f"{BASE_URL}/api/coach/play/start",
            json={"user_color": "white", "time_control": "15+10"}
        )
        assert start_response.status_code == 200
        session_id = start_response.json()["session_id"]
        print(f"✓ Started game with session_id: {session_id}")
        
        # Make move 1: e4
        move1 = self.session.post(
            f"{BASE_URL}/api/coach/play/move",
            json={"session_id": session_id, "move": "e4", "thinking_time_ms": 2000}
        )
        assert move1.status_code == 200
        print(f"✓ Made move e4")
        
        # Wait for coach
        time.sleep(5)
        
        # Get coaching after first cycle
        coaching1 = self.session.post(
            f"{BASE_URL}/api/coach/play/v5/interactive-feedback",
            json={"session_id": session_id}
        )
        assert coaching1.status_code == 200
        data1 = coaching1.json()
        
        assert data1.get("coach_move_coaching") is not None
        coach_move_1 = data1["coach_move_coaching"]["move_san"]
        print(f"✓ Coach played: {coach_move_1}")
        print(f"✓ Coach explanation: {data1['coach_move_coaching'].get('explanation', 'N/A')}")
        
        # Make move 2: Nf3
        move2 = self.session.post(
            f"{BASE_URL}/api/coach/play/move",
            json={"session_id": session_id, "move": "Nf3", "thinking_time_ms": 2000}
        )
        assert move2.status_code == 200
        print(f"✓ Made move Nf3")
        
        # Wait for coach
        time.sleep(5)
        
        # Get coaching after second cycle
        coaching2 = self.session.post(
            f"{BASE_URL}/api/coach/play/v5/interactive-feedback",
            json={"session_id": session_id}
        )
        assert coaching2.status_code == 200
        data2 = coaching2.json()
        
        assert data2.get("coach_move_coaching") is not None
        coach_move_2 = data2["coach_move_coaching"]["move_san"]
        print(f"✓ Coach played: {coach_move_2}")
        print(f"✓ Coach explanation: {data2['coach_move_coaching'].get('explanation', 'N/A')}")
        
        print(f"\n✓ Full move cycle test passed!")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
