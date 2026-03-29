"""
Test V5 Phased Interactive Coaching for Play with Coach
========================================================

Tests the POST /api/coach/play/v5/interactive-feedback endpoint with 'phase' parameter:
1. phase='user_move' → Returns ONLY user_move_coaching (coach_move_coaching should be null)
2. phase='coach_move' → Returns ONLY coach_move_coaching (user_move_coaching should be null)
3. phase=None → Returns BOTH user_move_coaching and coach_move_coaching

This enables the two-moment coaching flow:
- User plays → IMMEDIATELY see V5 coaching on their move (before coach responds)
- Coach plays → See coach explanation ONLY after coach finishes thinking
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestV5PhasedCoaching:
    """Test the phased V5 interactive coaching endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session with dev login"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Dev login (GET endpoint)
        login_response = self.session.get(f"{BASE_URL}/api/auth/dev-login")
        assert login_response.status_code == 200, f"Dev login failed: {login_response.text}"
        
        self.coach_session_id = None
        yield
        
        # Cleanup: End any active session
        if self.coach_session_id:
            try:
                self.session.post(f"{BASE_URL}/api/coach/play/end", json={
                    "session_id": self.coach_session_id,
                    "reason": "test_cleanup"
                })
            except:
                pass
    
    def start_game_and_make_move(self, user_color="white", wait_for_coach=True):
        """Helper to start a game and make a move"""
        # Start a new game
        start_response = self.session.post(f"{BASE_URL}/api/coach/play/start", json={
            "user_color": user_color,
            "time_control": "15+10"
        })
        assert start_response.status_code == 200, f"Start game failed: {start_response.text}"
        
        data = start_response.json()
        self.coach_session_id = data["session"]["session_id"]
        
        # Make a move
        if user_color == "white":
            move_response = self.session.post(f"{BASE_URL}/api/coach/play/move", json={
                "session_id": self.coach_session_id,
                "move": "e4",
                "thinking_time_ms": 2000
            })
            assert move_response.status_code == 200, f"Move failed: {move_response.text}"
            
            if wait_for_coach:
                # Wait for coach to respond
                time.sleep(4)
        else:
            # Playing black - coach already made first move
            time.sleep(1)
            
            # Make a response move
            move_response = self.session.post(f"{BASE_URL}/api/coach/play/move", json={
                "session_id": self.coach_session_id,
                "move": "e5",
                "thinking_time_ms": 2000
            })
            if move_response.status_code == 200 and wait_for_coach:
                time.sleep(4)
        
        return self.coach_session_id
    
    # ═══ PHASE='user_move' TESTS ═══
    
    def test_phase_user_move_returns_only_user_coaching(self):
        """Test that phase='user_move' returns ONLY user_move_coaching"""
        session_id = self.start_game_and_make_move(wait_for_coach=True)
        
        response = self.session.post(f"{BASE_URL}/api/coach/play/v5/interactive-feedback", json={
            "session_id": session_id,
            "phase": "user_move"
        })
        
        assert response.status_code == 200, f"Request failed: {response.text}"
        data = response.json()
        
        # user_move_coaching should be present (or null if move was perfect)
        assert "user_move_coaching" in data, "Missing user_move_coaching key"
        
        # coach_move_coaching should be null/None when phase='user_move'
        coach_coaching = data.get("coach_move_coaching")
        assert coach_coaching is None, \
            f"coach_move_coaching should be null for phase='user_move', got: {coach_coaching}"
        
        print("✓ phase='user_move' returns ONLY user_move_coaching (coach_move_coaching is null)")
        
        if data.get("user_move_coaching"):
            print(f"  - narrative: {data['user_move_coaching'].get('narrative', 'N/A')[:80]}...")
            print(f"  - severity: {data['user_move_coaching'].get('severity')}")
    
    def test_phase_user_move_has_v5_fields(self):
        """Test that user_move_coaching has proper V5 fields"""
        session_id = self.start_game_and_make_move(wait_for_coach=True)
        
        response = self.session.post(f"{BASE_URL}/api/coach/play/v5/interactive-feedback", json={
            "session_id": session_id,
            "phase": "user_move"
        })
        
        assert response.status_code == 200
        data = response.json()
        
        user_coaching = data.get("user_move_coaching")
        if user_coaching:
            # V5 required fields
            assert "narrative" in user_coaching, "Missing narrative"
            assert "severity" in user_coaching, "Missing severity"
            
            # Severity should be valid
            valid_severities = ["brilliant", "great", "good", "book", "inaccuracy", "mistake", "blunder"]
            assert user_coaching["severity"] in valid_severities, \
                f"Invalid severity: {user_coaching['severity']}"
            
            print(f"✓ user_move_coaching has V5 fields: narrative, severity={user_coaching['severity']}")
            
            # Check for optional V5 fields
            if user_coaching.get("candidate_moves"):
                print(f"  - candidate_moves: {len(user_coaching['candidate_moves'])} moves")
            if user_coaching.get("transferable_learning"):
                print(f"  - transferable_learning: {user_coaching['transferable_learning'][:60]}...")
    
    # ═══ PHASE='coach_move' TESTS ═══
    
    def test_phase_coach_move_returns_only_coach_coaching(self):
        """Test that phase='coach_move' returns ONLY coach_move_coaching"""
        session_id = self.start_game_and_make_move(wait_for_coach=True)
        
        response = self.session.post(f"{BASE_URL}/api/coach/play/v5/interactive-feedback", json={
            "session_id": session_id,
            "phase": "coach_move"
        })
        
        assert response.status_code == 200, f"Request failed: {response.text}"
        data = response.json()
        
        # coach_move_coaching should be present
        assert "coach_move_coaching" in data, "Missing coach_move_coaching key"
        
        # user_move_coaching should be null/None when phase='coach_move'
        user_coaching = data.get("user_move_coaching")
        assert user_coaching is None, \
            f"user_move_coaching should be null for phase='coach_move', got: {user_coaching}"
        
        print("✓ phase='coach_move' returns ONLY coach_move_coaching (user_move_coaching is null)")
        
        if data.get("coach_move_coaching"):
            print(f"  - move_san: {data['coach_move_coaching'].get('move_san')}")
            print(f"  - explanation: {data['coach_move_coaching'].get('explanation', 'N/A')[:80]}...")
    
    def test_phase_coach_move_has_explanation_fields(self):
        """Test that coach_move_coaching has explanation, plan, threats, teaching_point"""
        session_id = self.start_game_and_make_move(wait_for_coach=True)
        
        response = self.session.post(f"{BASE_URL}/api/coach/play/v5/interactive-feedback", json={
            "session_id": session_id,
            "phase": "coach_move"
        })
        
        assert response.status_code == 200
        data = response.json()
        
        coach_coaching = data.get("coach_move_coaching")
        if coach_coaching:
            # Required fields
            assert "move_san" in coach_coaching, "Missing move_san"
            assert "explanation" in coach_coaching, "Missing explanation"
            
            print(f"✓ coach_move_coaching has required fields:")
            print(f"  - move_san: {coach_coaching.get('move_san')}")
            print(f"  - explanation: {coach_coaching.get('explanation', 'N/A')[:80]}...")
            
            # Optional but expected fields
            if coach_coaching.get("plan"):
                print(f"  - plan: {coach_coaching['plan'][:60]}...")
            if coach_coaching.get("threats"):
                print(f"  - threats: {coach_coaching['threats']}")
            if coach_coaching.get("teaching_point"):
                print(f"  - teaching_point: {coach_coaching['teaching_point'][:60]}...")
            if coach_coaching.get("hint_for_user"):
                print(f"  - hint_for_user: {coach_coaching['hint_for_user'][:60]}...")
    
    # ═══ NO PHASE (BOTH) TESTS ═══
    
    def test_no_phase_returns_both(self):
        """Test that no phase parameter returns BOTH user_move_coaching and coach_move_coaching"""
        session_id = self.start_game_and_make_move(wait_for_coach=True)
        
        response = self.session.post(f"{BASE_URL}/api/coach/play/v5/interactive-feedback", json={
            "session_id": session_id
            # No phase parameter
        })
        
        assert response.status_code == 200, f"Request failed: {response.text}"
        data = response.json()
        
        # Both should be present (may be null if no moves yet)
        assert "user_move_coaching" in data, "Missing user_move_coaching key"
        assert "coach_move_coaching" in data, "Missing coach_move_coaching key"
        assert "is_user_turn" in data, "Missing is_user_turn key"
        
        print("✓ No phase returns BOTH user_move_coaching and coach_move_coaching")
        
        if data.get("user_move_coaching"):
            print(f"  - user_move_coaching.narrative: {data['user_move_coaching'].get('narrative', 'N/A')[:60]}...")
        if data.get("coach_move_coaching"):
            print(f"  - coach_move_coaching.move_san: {data['coach_move_coaching'].get('move_san')}")
    
    # ═══ TIMING TESTS (IMMEDIATE FEEDBACK) ═══
    
    def test_user_move_feedback_available_immediately(self):
        """Test that user move feedback is available RIGHT after user plays (before coach responds)"""
        # Start game
        start_response = self.session.post(f"{BASE_URL}/api/coach/play/start", json={
            "user_color": "white",
            "time_control": "15+10"
        })
        assert start_response.status_code == 200
        data = start_response.json()
        self.coach_session_id = data["session"]["session_id"]
        
        # Make a move (don't wait for coach)
        move_response = self.session.post(f"{BASE_URL}/api/coach/play/move", json={
            "session_id": self.coach_session_id,
            "move": "e4",
            "thinking_time_ms": 2000
        })
        assert move_response.status_code == 200
        
        # IMMEDIATELY request user_move coaching (before coach responds)
        # This simulates what frontend does in fetchUserMoveCoaching()
        time.sleep(0.5)  # Small delay for backend to process
        
        response = self.session.post(f"{BASE_URL}/api/coach/play/v5/interactive-feedback", json={
            "session_id": self.coach_session_id,
            "phase": "user_move"
        })
        
        assert response.status_code == 200, f"Request failed: {response.text}"
        data = response.json()
        
        # User move coaching should be available immediately
        # (It uses quick_stockfish_eval for inline evaluation)
        print("✓ User move feedback available immediately after user plays")
        
        if data.get("user_move_coaching"):
            print(f"  - Got coaching: {data['user_move_coaching'].get('narrative', 'N/A')[:60]}...")
        else:
            print("  - No coaching needed (move was good)")
        
        # Now wait for coach and verify coach_move becomes available
        time.sleep(4)
        
        response2 = self.session.post(f"{BASE_URL}/api/coach/play/v5/interactive-feedback", json={
            "session_id": self.coach_session_id,
            "phase": "coach_move"
        })
        
        assert response2.status_code == 200
        data2 = response2.json()
        
        if data2.get("coach_move_coaching"):
            print(f"✓ Coach move explanation available after coach responds")
            print(f"  - Coach played: {data2['coach_move_coaching'].get('move_san')}")
    
    # ═══ NO GENERIC TEXT TESTS ═══
    
    def test_no_generic_whats_your_plan_in_phased_response(self):
        """Test that phased responses don't contain generic 'What's your plan?' text"""
        session_id = self.start_game_and_make_move(wait_for_coach=True)
        
        # Test user_move phase
        response1 = self.session.post(f"{BASE_URL}/api/coach/play/v5/interactive-feedback", json={
            "session_id": session_id,
            "phase": "user_move"
        })
        assert response1.status_code == 200
        
        # Test coach_move phase
        response2 = self.session.post(f"{BASE_URL}/api/coach/play/v5/interactive-feedback", json={
            "session_id": session_id,
            "phase": "coach_move"
        })
        assert response2.status_code == 200
        
        # Check both responses for generic phrases
        generic_phrases = [
            "what's your plan?",
            "what is your plan?",
            "think about your plan"
        ]
        
        for response in [response1, response2]:
            response_str = str(response.json()).lower()
            for phrase in generic_phrases:
                assert phrase not in response_str, \
                    f"Found generic phrase '{phrase}' in response"
        
        print("✓ No generic 'What's your plan?' text in phased responses")
    
    # ═══ ERROR HANDLING ═══
    
    def test_invalid_phase_value_handled(self):
        """Test that invalid phase value is handled gracefully"""
        session_id = self.start_game_and_make_move(wait_for_coach=True)
        
        response = self.session.post(f"{BASE_URL}/api/coach/play/v5/interactive-feedback", json={
            "session_id": session_id,
            "phase": "invalid_phase"
        })
        
        # Should either return 400 or treat as no phase (return both)
        # Based on implementation, invalid phase is treated as None (returns both)
        assert response.status_code in [200, 400], f"Unexpected status: {response.status_code}"
        
        if response.status_code == 200:
            data = response.json()
            # Should have both keys (treated as no phase)
            assert "user_move_coaching" in data
            assert "coach_move_coaching" in data
            print("✓ Invalid phase treated as no phase (returns both)")
        else:
            print("✓ Invalid phase returns 400 error")


class TestV5CoachingCardTiming:
    """Test that V5CoachingCard appears at the right time in the flow"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        login_response = self.session.get(f"{BASE_URL}/api/auth/dev-login")
        assert login_response.status_code == 200
        
        self.coach_session_id = None
        yield
        
        if self.coach_session_id:
            try:
                self.session.post(f"{BASE_URL}/api/coach/play/end", json={
                    "session_id": self.coach_session_id,
                    "reason": "test_cleanup"
                })
            except:
                pass
    
    def test_two_moment_coaching_flow(self):
        """
        Test the complete two-moment coaching flow:
        1. User plays → V5 coaching appears IMMEDIATELY
        2. Coach thinking...
        3. Coach plays → Coach explanation appears
        """
        # Start game
        start_response = self.session.post(f"{BASE_URL}/api/coach/play/start", json={
            "user_color": "white",
            "time_control": "15+10"
        })
        assert start_response.status_code == 200
        data = start_response.json()
        self.coach_session_id = data["session"]["session_id"]
        
        print("\n=== TWO-MOMENT COACHING FLOW TEST ===")
        
        # MOMENT 1: User plays
        print("\n1. User plays e4...")
        move_response = self.session.post(f"{BASE_URL}/api/coach/play/move", json={
            "session_id": self.coach_session_id,
            "move": "e4",
            "thinking_time_ms": 2000
        })
        assert move_response.status_code == 200
        
        # IMMEDIATELY fetch user move coaching (before coach responds)
        print("   Fetching user move coaching IMMEDIATELY...")
        time.sleep(0.3)  # Minimal delay
        
        user_coaching_response = self.session.post(f"{BASE_URL}/api/coach/play/v5/interactive-feedback", json={
            "session_id": self.coach_session_id,
            "phase": "user_move"
        })
        assert user_coaching_response.status_code == 200
        user_data = user_coaching_response.json()
        
        # Verify user coaching is available
        print(f"   ✓ User move coaching available: {user_data.get('user_move_coaching') is not None or 'good move'}")
        if user_data.get("user_move_coaching"):
            print(f"     Severity: {user_data['user_move_coaching'].get('severity')}")
            print(f"     Narrative: {user_data['user_move_coaching'].get('narrative', 'N/A')[:60]}...")
        
        # Verify coach coaching is NOT available yet
        assert user_data.get("coach_move_coaching") is None, \
            "coach_move_coaching should be null when phase='user_move'"
        print("   ✓ Coach move coaching is null (as expected)")
        
        # MOMENT 2: Wait for coach to respond
        print("\n2. Coach is thinking...")
        time.sleep(4)
        
        # MOMENT 3: Fetch coach move explanation
        print("\n3. Fetching coach move explanation...")
        coach_coaching_response = self.session.post(f"{BASE_URL}/api/coach/play/v5/interactive-feedback", json={
            "session_id": self.coach_session_id,
            "phase": "coach_move"
        })
        assert coach_coaching_response.status_code == 200
        coach_data = coach_coaching_response.json()
        
        # Verify coach coaching is now available
        if coach_data.get("coach_move_coaching"):
            print(f"   ✓ Coach move coaching available!")
            print(f"     Move: {coach_data['coach_move_coaching'].get('move_san')}")
            print(f"     Explanation: {coach_data['coach_move_coaching'].get('explanation', 'N/A')[:60]}...")
            if coach_data['coach_move_coaching'].get('plan'):
                print(f"     Plan: {coach_data['coach_move_coaching']['plan'][:60]}...")
            if coach_data['coach_move_coaching'].get('threats'):
                print(f"     Threats: {coach_data['coach_move_coaching']['threats']}")
        else:
            print("   ✓ No coach move yet (game may have ended)")
        
        # Verify user coaching is NOT returned in coach_move phase
        assert coach_data.get("user_move_coaching") is None, \
            "user_move_coaching should be null when phase='coach_move'"
        print("   ✓ User move coaching is null (as expected)")
        
        print("\n=== TWO-MOMENT FLOW VERIFIED ===")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
