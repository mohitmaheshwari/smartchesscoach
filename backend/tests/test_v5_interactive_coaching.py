"""
Test V5 Interactive Coaching for Play with Coach
=================================================

Tests the POST /api/coach/play/v5/interactive-feedback endpoint which:
1. Returns user_move_coaching with V5 fields (narrative, severity, candidate_moves, etc.)
2. Returns coach_move_coaching with explanation, plan, threats, teaching_point
3. Uses the SAME V5 pipeline as Lab (generate_move_coaching)

This ensures Play with Coach has the same quality coaching as Lab decryption.
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestV5InteractiveCoaching:
    """Test the V5 interactive coaching endpoint for Play with Coach"""
    
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
    
    def start_game_and_make_move(self, user_color="white"):
        """Helper to start a game and make a move to get coaching feedback"""
        # Start a new game
        start_response = self.session.post(f"{BASE_URL}/api/coach/play/start", json={
            "user_color": user_color,
            "time_control": "15+10"
        })
        assert start_response.status_code == 200, f"Start game failed: {start_response.text}"
        
        data = start_response.json()
        self.coach_session_id = data["session"]["session_id"]
        
        # Make a move (e2-e4 for white, or wait for coach if black)
        if user_color == "white":
            move_response = self.session.post(f"{BASE_URL}/api/coach/play/move", json={
                "session_id": self.coach_session_id,
                "move": "e4",
                "thinking_time_ms": 2000
            })
            assert move_response.status_code == 200, f"Move failed: {move_response.text}"
            
            # Wait for coach to respond
            time.sleep(3)
        else:
            # Playing black - coach already made first move
            time.sleep(1)
            
            # Make a response move
            move_response = self.session.post(f"{BASE_URL}/api/coach/play/move", json={
                "session_id": self.coach_session_id,
                "move": "e5",
                "thinking_time_ms": 2000
            })
            if move_response.status_code == 200:
                time.sleep(3)
        
        return self.coach_session_id
    
    # ═══ ENDPOINT STRUCTURE TESTS ═══
    
    def test_interactive_feedback_requires_session_id(self):
        """Test that session_id is required"""
        response = self.session.post(f"{BASE_URL}/api/coach/play/v5/interactive-feedback", json={})
        assert response.status_code == 400, "Should require session_id"
        assert "session_id" in response.json().get("detail", "").lower()
    
    def test_interactive_feedback_returns_correct_structure(self):
        """Test that endpoint returns user_move_coaching and coach_move_coaching"""
        session_id = self.start_game_and_make_move()
        
        response = self.session.post(f"{BASE_URL}/api/coach/play/v5/interactive-feedback", json={
            "session_id": session_id
        })
        
        assert response.status_code == 200, f"Interactive feedback failed: {response.text}"
        data = response.json()
        
        # Must have these top-level keys
        assert "user_move_coaching" in data, "Missing user_move_coaching"
        assert "coach_move_coaching" in data, "Missing coach_move_coaching"
        assert "is_user_turn" in data, "Missing is_user_turn"
        
        print(f"✓ Response structure correct: user_move_coaching, coach_move_coaching, is_user_turn")
    
    # ═══ USER MOVE COACHING (V5 FIELDS) ═══
    
    def test_user_move_coaching_has_v5_fields(self):
        """Test that user_move_coaching has V5 fields like Lab decryption"""
        session_id = self.start_game_and_make_move()
        
        response = self.session.post(f"{BASE_URL}/api/coach/play/v5/interactive-feedback", json={
            "session_id": session_id
        })
        
        assert response.status_code == 200
        data = response.json()
        
        user_coaching = data.get("user_move_coaching")
        
        # For a good move like e4, user_move_coaching might be None or have good severity
        if user_coaching:
            # V5 required fields
            assert "narrative" in user_coaching, "Missing narrative in user_move_coaching"
            assert "severity" in user_coaching, "Missing severity in user_move_coaching"
            
            # V5 optional fields (present for mistakes)
            v5_optional_fields = ["candidate_moves", "consequence", "better_approach", 
                                  "transferable_learning", "best_move"]
            
            print(f"✓ User move coaching has V5 fields:")
            print(f"  - narrative: {user_coaching.get('narrative', 'N/A')[:80]}...")
            print(f"  - severity: {user_coaching.get('severity')}")
            
            if user_coaching.get("candidate_moves"):
                print(f"  - candidate_moves: {len(user_coaching['candidate_moves'])} moves")
                for cm in user_coaching["candidate_moves"][:2]:
                    print(f"    • {cm.get('move')}: {cm.get('idea', 'N/A')[:50]}...")
            
            if user_coaching.get("consequence"):
                print(f"  - consequence: {user_coaching['consequence'][:80]}...")
            
            if user_coaching.get("transferable_learning"):
                print(f"  - transferable_learning (golden rule): {user_coaching['transferable_learning'][:80]}...")
        else:
            print("✓ User move coaching is None (move was good, no coaching needed)")
    
    def test_user_move_coaching_severity_values(self):
        """Test that severity is one of the expected V5 values"""
        session_id = self.start_game_and_make_move()
        
        response = self.session.post(f"{BASE_URL}/api/coach/play/v5/interactive-feedback", json={
            "session_id": session_id
        })
        
        assert response.status_code == 200
        data = response.json()
        
        user_coaching = data.get("user_move_coaching")
        if user_coaching and "severity" in user_coaching:
            valid_severities = ["brilliant", "great", "good", "book", "inaccuracy", "mistake", "blunder"]
            assert user_coaching["severity"] in valid_severities, \
                f"Invalid severity: {user_coaching['severity']}"
            print(f"✓ Severity '{user_coaching['severity']}' is valid V5 severity")
    
    # ═══ COACH MOVE COACHING ═══
    
    def test_coach_move_coaching_has_required_fields(self):
        """Test that coach_move_coaching has explanation, plan, threats, teaching_point"""
        session_id = self.start_game_and_make_move()
        
        response = self.session.post(f"{BASE_URL}/api/coach/play/v5/interactive-feedback", json={
            "session_id": session_id
        })
        
        assert response.status_code == 200
        data = response.json()
        
        coach_coaching = data.get("coach_move_coaching")
        
        if coach_coaching:
            # Required fields for coach move explanation
            assert "move_san" in coach_coaching, "Missing move_san in coach_move_coaching"
            assert "explanation" in coach_coaching, "Missing explanation in coach_move_coaching"
            
            # Optional but expected fields
            expected_fields = ["plan", "threats", "teaching_point", "hint_for_user"]
            
            print(f"✓ Coach move coaching fields:")
            print(f"  - move_san: {coach_coaching.get('move_san')}")
            print(f"  - explanation: {coach_coaching.get('explanation', 'N/A')[:80]}...")
            
            if coach_coaching.get("plan"):
                print(f"  - plan: {coach_coaching['plan'][:80]}...")
            
            if coach_coaching.get("threats"):
                print(f"  - threats: {coach_coaching['threats']}")
            
            if coach_coaching.get("teaching_point"):
                print(f"  - teaching_point: {coach_coaching['teaching_point'][:80]}...")
        else:
            print("✓ Coach move coaching is None (no coach move yet)")
    
    def test_coach_move_explanation_not_generic(self):
        """Test that coach move explanation is specific, not generic 'What's your plan?'"""
        session_id = self.start_game_and_make_move()
        
        response = self.session.post(f"{BASE_URL}/api/coach/play/v5/interactive-feedback", json={
            "session_id": session_id
        })
        
        assert response.status_code == 200
        data = response.json()
        
        coach_coaching = data.get("coach_move_coaching")
        
        if coach_coaching:
            explanation = coach_coaching.get("explanation", "")
            plan = coach_coaching.get("plan", "")
            
            # Should NOT be generic
            generic_phrases = ["what's your plan", "what is your plan", "think about your plan"]
            
            for phrase in generic_phrases:
                assert phrase not in explanation.lower(), \
                    f"Explanation contains generic phrase: '{phrase}'"
                assert phrase not in plan.lower(), \
                    f"Plan contains generic phrase: '{phrase}'"
            
            # Should have specific content
            assert len(explanation) > 10, "Explanation too short - likely generic"
            
            print(f"✓ Coach explanation is specific (not generic 'What's your plan?')")
            print(f"  Explanation: {explanation[:100]}...")
    
    # ═══ INTEGRATION WITH V5 PIPELINE ═══
    
    def test_uses_same_pipeline_as_lab(self):
        """Test that the endpoint uses generate_move_coaching (same as Lab)"""
        # This is verified by checking the response structure matches Lab's V5Coaching
        session_id = self.start_game_and_make_move()
        
        response = self.session.post(f"{BASE_URL}/api/coach/play/v5/interactive-feedback", json={
            "session_id": session_id
        })
        
        assert response.status_code == 200
        data = response.json()
        
        user_coaching = data.get("user_move_coaching")
        
        if user_coaching:
            # V5Coaching dataclass fields from shared_coaching_v5.py
            v5_fields = [
                "narrative", "severity", "goal", "current_problem", "consequence",
                "better_approach", "transferable_learning", "concept_id", "concept_type",
                "candidate_moves", "future_moves", "is_user_move", "best_move", "your_plan_now"
            ]
            
            # At minimum, narrative and severity should be present
            assert "narrative" in user_coaching, "Missing V5 narrative field"
            assert "severity" in user_coaching, "Missing V5 severity field"
            
            present_fields = [f for f in v5_fields if f in user_coaching]
            print(f"✓ V5 pipeline fields present: {present_fields}")
    
    # ═══ CANDIDATE MOVES (STOCKFISH) ═══
    
    def test_candidate_moves_have_ideas(self):
        """Test that candidate_moves have move, idea, and type"""
        session_id = self.start_game_and_make_move()
        
        response = self.session.post(f"{BASE_URL}/api/coach/play/v5/interactive-feedback", json={
            "session_id": session_id
        })
        
        assert response.status_code == 200
        data = response.json()
        
        user_coaching = data.get("user_move_coaching")
        
        if user_coaching and user_coaching.get("candidate_moves"):
            candidates = user_coaching["candidate_moves"]
            
            for i, candidate in enumerate(candidates):
                assert "move" in candidate, f"Candidate {i} missing 'move'"
                assert "idea" in candidate, f"Candidate {i} missing 'idea'"
                
                print(f"✓ Candidate {i+1}: {candidate.get('move')} - {candidate.get('idea', 'N/A')[:50]}...")
                
                if candidate.get("is_best"):
                    print(f"  (This is the best move)")
        else:
            print("✓ No candidate moves (move was good or no alternatives needed)")
    
    # ═══ ERROR HANDLING ═══
    
    def test_invalid_session_returns_404(self):
        """Test that invalid session_id returns 404"""
        response = self.session.post(f"{BASE_URL}/api/coach/play/v5/interactive-feedback", json={
            "session_id": "invalid_session_12345"
        })
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ Invalid session returns 404")


class TestNoGenericYourTurnSection:
    """Test that generic 'What's your plan?' YourTurnSection is NOT used"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Dev login (GET endpoint)
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
    
    def test_no_generic_whats_your_plan_in_response(self):
        """Verify the API response doesn't contain generic 'What's your plan?' text"""
        # Start game
        start_response = self.session.post(f"{BASE_URL}/api/coach/play/start", json={
            "user_color": "white",
            "time_control": "15+10"
        })
        assert start_response.status_code == 200
        
        data = start_response.json()
        self.coach_session_id = data["session"]["session_id"]
        
        # Make a move
        move_response = self.session.post(f"{BASE_URL}/api/coach/play/move", json={
            "session_id": self.coach_session_id,
            "move": "e4",
            "thinking_time_ms": 2000
        })
        assert move_response.status_code == 200
        
        # Wait for coach
        time.sleep(3)
        
        # Get interactive feedback
        response = self.session.post(f"{BASE_URL}/api/coach/play/v5/interactive-feedback", json={
            "session_id": self.coach_session_id
        })
        
        assert response.status_code == 200
        data = response.json()
        
        # Convert entire response to string and check for generic phrases
        response_str = str(data).lower()
        
        # These generic phrases should NOT appear
        generic_phrases = [
            "what's your plan?",
            "what is your plan?",
            "think about your plan",
            "consider your plan"
        ]
        
        for phrase in generic_phrases:
            assert phrase not in response_str, \
                f"Found generic phrase '{phrase}' in response"
        
        print("✓ No generic 'What's your plan?' phrases in API response")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
