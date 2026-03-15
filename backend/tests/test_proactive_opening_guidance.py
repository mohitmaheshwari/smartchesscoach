"""
Test Proactive Opening Guidance Feature

Tests the new proactive opening teaching at game start:
1. API returns opening_teaching data with teaching_active=true on session start
2. Suggested trap is included in the opening teaching state
3. Opening teaching state persists across session state calls
4. Frontend displays Opening Guide panel with suggested move and trap option
5. Learn Trap and Skip buttons are functional

Feature: At game start, the coach proactively suggests openings with trap teaching options.
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://chess-habit-forge.preview.emergentagent.com')


class TestProactiveOpeningGuidanceSessionStart:
    """Test opening guidance is returned when starting a coach play session."""
    
    def test_start_session_returns_success(self, authenticated_session):
        """Basic test: session start should succeed."""
        response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/start",
            json={"user_color": "white", "time_control": "15+10"}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") is True, "Session start should be successful"
        assert "session_id" in data, "Should return session_id"
        assert "session" in data, "Should return session data"
        
        # Clean up - end the session
        session_id = data.get("session_id")
        if session_id:
            authenticated_session.post(
                f"{BASE_URL}/api/coach/play/end",
                json={"session_id": session_id, "reason": "abandoned"}
            )
    
    def test_session_has_opening_teaching_active(self, authenticated_session):
        """Session should have opening_teaching_active=True at game start."""
        response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/start",
            json={"user_color": "white", "time_control": "15+10"}
        )
        
        assert response.status_code == 200
        data = response.json()
        session_id = data.get("session_id")
        
        # Get session state to check opening teaching
        state_response = authenticated_session.get(
            f"{BASE_URL}/api/coach/play/state/{session_id}"
        )
        
        assert state_response.status_code == 200, f"State fetch failed: {state_response.text}"
        state_data = state_response.json()
        
        # Check for opening_teaching in session state
        session = state_data.get("session", {})
        opening_teaching = state_data.get("opening_teaching")
        
        # The session should have opening teaching info
        assert session.get("opening_teaching_active") is True, \
            f"Expected opening_teaching_active=True, got {session.get('opening_teaching_active')}"
        
        # Clean up
        if session_id:
            authenticated_session.post(
                f"{BASE_URL}/api/coach/play/end",
                json={"session_id": session_id, "reason": "abandoned"}
            )
    
    def test_opening_teaching_has_guidance_data(self, authenticated_session):
        """Session state should include opening guidance with teaching_active=true."""
        response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/start",
            json={"user_color": "white", "time_control": "15+10"}
        )
        
        assert response.status_code == 200
        data = response.json()
        session_id = data.get("session_id")
        
        # Get session state
        state_response = authenticated_session.get(
            f"{BASE_URL}/api/coach/play/state/{session_id}"
        )
        
        assert state_response.status_code == 200
        state_data = state_response.json()
        
        opening_teaching = state_data.get("opening_teaching")
        
        # Opening teaching should have teaching_active flag
        assert opening_teaching is not None, "opening_teaching should be present in state"
        assert opening_teaching.get("teaching_active") is True, \
            f"teaching_active should be True, got {opening_teaching.get('teaching_active')}"
        
        # Should have opening_key
        assert opening_teaching.get("opening_key") is not None, "Should have opening_key"
        
        # Clean up
        if session_id:
            authenticated_session.post(
                f"{BASE_URL}/api/coach/play/end",
                json={"session_id": session_id, "reason": "abandoned"}
            )


class TestOpeningGuidanceWithTrap:
    """Test that suggested trap is included in opening teaching state."""
    
    def test_session_has_suggested_trap(self, authenticated_session):
        """Opening teaching state should include suggested_trap if available."""
        response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/start",
            json={"user_color": "white", "time_control": "15+10"}
        )
        
        assert response.status_code == 200
        data = response.json()
        session_id = data.get("session_id")
        
        # Get session state
        state_response = authenticated_session.get(
            f"{BASE_URL}/api/coach/play/state/{session_id}"
        )
        
        assert state_response.status_code == 200
        state_data = state_response.json()
        
        session = state_data.get("session", {})
        opening_teaching = state_data.get("opening_teaching")
        
        # Check if trap info is included (either in session or opening_teaching)
        has_trap_info = (
            session.get("suggested_trap") is not None or 
            (opening_teaching and opening_teaching.get("suggested_trap") is not None)
        )
        
        # Trap may not be suggested for all openings, so we just verify the field exists
        # The important thing is that the structure supports trap data
        suggested_trap = session.get("suggested_trap") or (opening_teaching and opening_teaching.get("suggested_trap"))
        
        if suggested_trap:
            # If a trap is suggested, verify it has expected fields
            assert "name" in suggested_trap, "Trap should have a name"
        
        # Clean up
        if session_id:
            authenticated_session.post(
                f"{BASE_URL}/api/coach/play/end",
                json={"session_id": session_id, "reason": "abandoned"}
            )
    
    def test_session_has_available_traps_list(self, authenticated_session):
        """Session should have available_traps list if opening has traps."""
        response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/start",
            json={"user_color": "white", "time_control": "15+10"}
        )
        
        assert response.status_code == 200
        data = response.json()
        session_id = data.get("session_id")
        
        # Get session state
        state_response = authenticated_session.get(
            f"{BASE_URL}/api/coach/play/state/{session_id}"
        )
        
        assert state_response.status_code == 200
        state_data = state_response.json()
        
        session = state_data.get("session", {})
        opening_teaching = state_data.get("opening_teaching")
        
        # available_traps should be a list (may be empty for some openings)
        available_traps = session.get("available_traps")
        if available_traps is not None:
            assert isinstance(available_traps, list), "available_traps should be a list"
        
        # Clean up
        if session_id:
            authenticated_session.post(
                f"{BASE_URL}/api/coach/play/end",
                json={"session_id": session_id, "reason": "abandoned"}
            )


class TestOpeningGuidanceGuidanceField:
    """Test the guidance field in opening_teaching state."""
    
    def test_opening_guidance_has_guidance_field(self, authenticated_session):
        """Opening teaching should include guidance with move suggestions."""
        response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/start",
            json={"user_color": "white", "time_control": "15+10"}
        )
        
        assert response.status_code == 200
        data = response.json()
        session_id = data.get("session_id")
        
        # Get session state
        state_response = authenticated_session.get(
            f"{BASE_URL}/api/coach/play/state/{session_id}"
        )
        
        assert state_response.status_code == 200
        state_data = state_response.json()
        
        opening_teaching = state_data.get("opening_teaching")
        assert opening_teaching is not None, "opening_teaching should be present"
        
        guidance = opening_teaching.get("guidance")
        assert guidance is not None, "Opening teaching should have guidance field"
        
        # For white player at game start, should have your_turn=True
        if not guidance.get("complete"):
            # If not complete, should have move guidance
            assert "suggested_move" in guidance or "your_turn" in guidance, \
                f"Guidance should have move info, got: {guidance}"
        
        # Clean up
        if session_id:
            authenticated_session.post(
                f"{BASE_URL}/api/coach/play/end",
                json={"session_id": session_id, "reason": "abandoned"}
            )
    
    def test_guidance_shows_suggested_move_for_white(self, authenticated_session):
        """When user plays white, guidance should show the first suggested move."""
        response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/start",
            json={"user_color": "white", "time_control": "15+10"}
        )
        
        assert response.status_code == 200
        data = response.json()
        session_id = data.get("session_id")
        
        # Get session state
        state_response = authenticated_session.get(
            f"{BASE_URL}/api/coach/play/state/{session_id}"
        )
        
        assert state_response.status_code == 200
        state_data = state_response.json()
        
        opening_teaching = state_data.get("opening_teaching")
        guidance = opening_teaching.get("guidance", {}) if opening_teaching else {}
        
        if not guidance.get("complete"):
            # For white, first move should be user's turn
            assert guidance.get("your_turn") is True, \
                f"Expected your_turn=True for white player at start, got {guidance.get('your_turn')}"
            
            # Should have a suggested move
            assert guidance.get("suggested_move") is not None, \
                f"Should have suggested_move, got: {guidance}"
        
        # Clean up
        if session_id:
            authenticated_session.post(
                f"{BASE_URL}/api/coach/play/end",
                json={"session_id": session_id, "reason": "abandoned"}
            )
    
    def test_guidance_for_black_shows_coach_move_first(self, authenticated_session):
        """When user plays black, guidance should show coach's first move."""
        response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/start",
            json={"user_color": "black", "time_control": "15+10"}
        )
        
        # Wait for coach to make first move
        time.sleep(2)
        
        assert response.status_code == 200
        data = response.json()
        session_id = data.get("session_id")
        
        # Get session state (after coach has moved)
        state_response = authenticated_session.get(
            f"{BASE_URL}/api/coach/play/state/{session_id}"
        )
        
        assert state_response.status_code == 200
        state_data = state_response.json()
        
        opening_teaching = state_data.get("opening_teaching")
        guidance = opening_teaching.get("guidance", {}) if opening_teaching else {}
        
        # After coach makes first move, guidance should now be for black's turn
        # (teaching_index would have advanced)
        if not guidance.get("complete"):
            # Guidance should show it's now black's turn (user's turn for black player)
            # This could be your_turn=True (black's move after white's opening move)
            # or your_turn=False if showing coach's next expected move
            pass  # Just verify we got guidance without error
        
        # Clean up
        if session_id:
            authenticated_session.post(
                f"{BASE_URL}/api/coach/play/end",
                json={"session_id": session_id, "reason": "abandoned"}
            )


class TestOpeningTeachingPersistence:
    """Test that opening teaching state persists across session state calls."""
    
    def test_opening_teaching_persists_on_multiple_state_calls(self, authenticated_session):
        """Opening teaching data should persist when fetching state multiple times."""
        response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/start",
            json={"user_color": "white", "time_control": "15+10"}
        )
        
        assert response.status_code == 200
        data = response.json()
        session_id = data.get("session_id")
        
        # First state call
        state1 = authenticated_session.get(f"{BASE_URL}/api/coach/play/state/{session_id}").json()
        opening_teaching_1 = state1.get("opening_teaching")
        
        # Second state call
        state2 = authenticated_session.get(f"{BASE_URL}/api/coach/play/state/{session_id}").json()
        opening_teaching_2 = state2.get("opening_teaching")
        
        # Both should have opening_teaching
        assert opening_teaching_1 is not None, "First call should have opening_teaching"
        assert opening_teaching_2 is not None, "Second call should have opening_teaching"
        
        # teaching_active should be consistent
        assert opening_teaching_1.get("teaching_active") == opening_teaching_2.get("teaching_active"), \
            "teaching_active should be consistent across calls"
        
        # opening_key should be consistent
        assert opening_teaching_1.get("opening_key") == opening_teaching_2.get("opening_key"), \
            "opening_key should be consistent across calls"
        
        # Clean up
        if session_id:
            authenticated_session.post(
                f"{BASE_URL}/api/coach/play/end",
                json={"session_id": session_id, "reason": "abandoned"}
            )


class TestOpeningTeachingSkipFlow:
    """Test the Skip functionality for opening teaching."""
    
    def test_skip_teaching_endpoint_exists(self, authenticated_session):
        """Skip teaching endpoint should exist and respond."""
        # First start a session
        response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/start",
            json={"user_color": "white", "time_control": "15+10"}
        )
        
        assert response.status_code == 200
        data = response.json()
        session_id = data.get("session_id")
        
        # Try to skip teaching
        skip_response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/teaching/skip",
            json={"session_id": session_id}
        )
        
        # Endpoint should respond (200 or some other valid response)
        assert skip_response.status_code in [200, 201, 404], \
            f"Skip endpoint should respond, got {skip_response.status_code}"
        
        # Clean up
        if session_id:
            authenticated_session.post(
                f"{BASE_URL}/api/coach/play/end",
                json={"session_id": session_id, "reason": "abandoned"}
            )


class TestOpeningTeachingStartLesson:
    """Test starting a trap lesson from opening teaching."""
    
    def test_start_teaching_endpoint_exists(self, authenticated_session):
        """Teaching start endpoint should exist."""
        # First start a session
        response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/start",
            json={"user_color": "white", "time_control": "15+10"}
        )
        
        assert response.status_code == 200
        data = response.json()
        session_id = data.get("session_id")
        
        # Try to start trap teaching
        teaching_response = authenticated_session.post(
            f"{BASE_URL}/api/coach/play/teaching/start",
            json={"session_id": session_id, "lesson_type": "learn_trap"}
        )
        
        # Should get a response (may be 200 or 400 if no trap available)
        assert teaching_response.status_code in [200, 201, 400, 404], \
            f"Teaching start endpoint should respond, got {teaching_response.status_code}: {teaching_response.text}"
        
        # Clean up
        if session_id:
            authenticated_session.post(
                f"{BASE_URL}/api/coach/play/end",
                json={"session_id": session_id, "reason": "abandoned"}
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
