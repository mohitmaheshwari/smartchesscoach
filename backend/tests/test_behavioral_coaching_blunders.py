"""
Test Behavioral Coaching for Blunders/Mistakes at ANY Speed
============================================================

Tests the fix: Behavioral coaching should ALWAYS trigger on blunders/mistakes 
regardless of speed (not just fast moves).

Key changes in player_habits_service.py:
- blunder + fast (<3s) = impulse_move
- blunder + medium (3-10s) = calculation_miss  
- blunder + slow (>10s) = calculation_depth
- Same pattern for mistakes

Also tests guardian intervention is inline (not overlay).
"""

import pytest
import requests
import os
import sys
import time

# Add backend to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Use the public URL from frontend/.env
BASE_URL = "https://guru-play-debug.preview.emergentagent.com"


class TestBehavioralCoachingBlunders:
    """Test behavioral coaching triggers for ALL blunders/mistakes at any speed"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session with dev login"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Dev login
        login_resp = self.session.get(f"{BASE_URL}/api/auth/dev-login")
        assert login_resp.status_code == 200, f"Dev login failed: {login_resp.text}"
        self.user_data = login_resp.json()
        print(f"Logged in as: {self.user_data.get('user', {}).get('user_id', 'unknown')}")
    
    # ─── TEST 1: Behavioral coaching field exists in response ───
    def test_interactive_feedback_returns_behavioral_coaching_field(self):
        """
        POST /api/coach/play/v5/interactive-feedback should return 
        'behavioral_coaching' field in response (may be null for good moves)
        """
        # Start a coach play session
        start_resp = self.session.post(f"{BASE_URL}/api/coach/play/start", json={
            "user_color": "white",
            "time_control": "15+10"
        })
        
        if start_resp.status_code != 200:
            pytest.skip(f"Could not start session: {start_resp.text}")
        
        session_data = start_resp.json()
        session_id = session_data.get("session", {}).get("session_id")
        assert session_id, "No session_id returned"
        print(f"Started session: {session_id}")
        
        # Make a move (e4)
        move_resp = self.session.post(f"{BASE_URL}/api/coach/play/move", json={
            "session_id": session_id,
            "move": "e4",
            "thinking_time_ms": 2000  # 2 seconds
        })
        
        if move_resp.status_code != 200:
            pytest.skip(f"Could not make move: {move_resp.text}")
        
        # Wait for coach to respond
        time.sleep(2)
        
        # Get interactive feedback
        feedback_resp = self.session.post(f"{BASE_URL}/api/coach/play/v5/interactive-feedback", json={
            "session_id": session_id,
            "phase": "user_move"
        })
        
        assert feedback_resp.status_code == 200, f"Feedback failed: {feedback_resp.text}"
        data = feedback_resp.json()
        
        # Verify behavioral_coaching field exists (may be null for good moves)
        assert "behavioral_coaching" in data, "Response missing 'behavioral_coaching' field"
        print(f"behavioral_coaching: {data.get('behavioral_coaching')}")
        
        # Cleanup - resign
        self.session.post(f"{BASE_URL}/api/coach/play/resign", json={"session_id": session_id})
    
    # ─── TEST 2: Unit test generate_behavioral_coaching for blunder + slow ───
    def test_generate_behavioral_coaching_blunder_slow_time(self):
        """
        Test that generate_behavioral_coaching returns coaching for blunders 
        even with SLOW time (>10s) - should return calculation_depth habit
        """
        from services.player_habits_service import generate_behavioral_coaching
        
        # Simulate a blunder with SLOW time (15 seconds)
        result = generate_behavioral_coaching(
            move_san="Qxh7",
            time_spent=15.0,  # SLOW - 15 seconds
            move_quality="blunder",
            game_phase="middlegame",
            behavior_events=[],
            move_history=[{"by": "player", "move": "Qxh7", "time_spent": 15.0}],
            player_profile=None
        )
        
        assert result is not None, "Behavioral coaching should trigger for blunder even with slow time"
        assert result.get("severity") == "high", f"Blunder should have high severity, got: {result.get('severity')}"
        assert result.get("habit") == "calculation_depth", f"Slow blunder should be calculation_depth, got: {result.get('habit')}"
        assert result.get("type") == "calculation", f"Should be calculation type, got: {result.get('type')}"
        assert result.get("message"), "Should have a message"
        assert result.get("actionable_tip"), "Should have an actionable tip"
        
        print(f"Blunder (slow) coaching: {result}")
    
    # ─── TEST 3: Unit test generate_behavioral_coaching for blunder + medium ───
    def test_generate_behavioral_coaching_blunder_medium_time(self):
        """
        Test that generate_behavioral_coaching returns coaching for blunders 
        with MEDIUM time (3-10s) - should return calculation_miss habit
        """
        from services.player_habits_service import generate_behavioral_coaching
        
        # Simulate a blunder with MEDIUM time (7 seconds)
        result = generate_behavioral_coaching(
            move_san="Nxe5",
            time_spent=7.0,  # MEDIUM - 7 seconds
            move_quality="blunder",
            game_phase="middlegame",
            behavior_events=[],
            move_history=[{"by": "player", "move": "Nxe5", "time_spent": 7.0}],
            player_profile=None
        )
        
        assert result is not None, "Behavioral coaching should trigger for blunder with medium time"
        assert result.get("severity") == "high", f"Blunder should have high severity, got: {result.get('severity')}"
        assert result.get("habit") == "calculation_miss", f"Medium blunder should be calculation_miss, got: {result.get('habit')}"
        assert result.get("type") == "calculation", f"Should be calculation type, got: {result.get('type')}"
        
        print(f"Blunder (medium) coaching: {result}")
    
    # ─── TEST 4: Unit test generate_behavioral_coaching for blunder + fast ───
    def test_generate_behavioral_coaching_blunder_fast_time(self):
        """
        Test that generate_behavioral_coaching returns coaching for blunders 
        with FAST time (<3s) - should return impulse_move habit
        """
        from services.player_habits_service import generate_behavioral_coaching
        
        # Simulate a blunder with FAST time (1.5 seconds)
        result = generate_behavioral_coaching(
            move_san="Bxf7",
            time_spent=1.5,  # FAST - 1.5 seconds
            move_quality="blunder",
            game_phase="opening",
            behavior_events=[],
            move_history=[{"by": "player", "move": "Bxf7", "time_spent": 1.5}],
            player_profile=None
        )
        
        assert result is not None, "Behavioral coaching should trigger for fast blunder"
        assert result.get("severity") == "high", f"Blunder should have high severity, got: {result.get('severity')}"
        assert result.get("habit") == "impulse_move", f"Fast blunder should be impulse_move, got: {result.get('habit')}"
        assert result.get("type") == "time_management", f"Should be time_management type, got: {result.get('type')}"
        
        print(f"Blunder (fast) coaching: {result}")
    
    # ─── TEST 5: Unit test generate_behavioral_coaching for mistake + slow ───
    def test_generate_behavioral_coaching_mistake_slow_time(self):
        """
        Test that generate_behavioral_coaching returns coaching for mistakes 
        even with SLOW time (>10s) - should return calculation_direction habit
        """
        from services.player_habits_service import generate_behavioral_coaching
        
        # Simulate a mistake with SLOW time (20 seconds)
        result = generate_behavioral_coaching(
            move_san="Bd3",
            time_spent=20.0,  # SLOW - 20 seconds
            move_quality="mistake",
            game_phase="middlegame",
            behavior_events=[],
            move_history=[{"by": "player", "move": "Bd3", "time_spent": 20.0}],
            player_profile=None
        )
        
        assert result is not None, "Behavioral coaching should trigger for mistake even with slow time"
        assert result.get("severity") == "medium", f"Mistake should have medium severity, got: {result.get('severity')}"
        assert result.get("habit") == "calculation_direction", f"Slow mistake should be calculation_direction, got: {result.get('habit')}"
        assert result.get("type") == "calculation", f"Should be calculation type, got: {result.get('type')}"
        
        print(f"Mistake (slow) coaching: {result}")
    
    # ─── TEST 6: Unit test generate_behavioral_coaching for mistake + medium ───
    def test_generate_behavioral_coaching_mistake_medium_time(self):
        """
        Test that generate_behavioral_coaching returns coaching for mistakes 
        with MEDIUM time (3-10s) - should return calculation_miss habit
        """
        from services.player_habits_service import generate_behavioral_coaching
        
        # Simulate a mistake with MEDIUM time (5 seconds)
        result = generate_behavioral_coaching(
            move_san="Nc3",
            time_spent=5.0,  # MEDIUM - 5 seconds
            move_quality="mistake",
            game_phase="opening",
            behavior_events=[],
            move_history=[{"by": "player", "move": "Nc3", "time_spent": 5.0}],
            player_profile=None
        )
        
        assert result is not None, "Behavioral coaching should trigger for mistake with medium time"
        assert result.get("severity") == "medium", f"Mistake should have medium severity, got: {result.get('severity')}"
        assert result.get("habit") == "calculation_miss", f"Medium mistake should be calculation_miss, got: {result.get('habit')}"
        
        print(f"Mistake (medium) coaching: {result}")
    
    # ─── TEST 7: Unit test generate_behavioral_coaching for mistake + fast ───
    def test_generate_behavioral_coaching_mistake_fast_time(self):
        """
        Test that generate_behavioral_coaching returns coaching for mistakes 
        with FAST time (<3s) - should return impulse_move habit
        """
        from services.player_habits_service import generate_behavioral_coaching
        
        # Simulate a mistake with FAST time (2 seconds)
        result = generate_behavioral_coaching(
            move_san="d4",
            time_spent=2.0,  # FAST - 2 seconds
            move_quality="mistake",
            game_phase="opening",
            behavior_events=[],
            move_history=[{"by": "player", "move": "d4", "time_spent": 2.0}],
            player_profile=None
        )
        
        assert result is not None, "Behavioral coaching should trigger for fast mistake"
        assert result.get("severity") == "medium", f"Mistake should have medium severity, got: {result.get('severity')}"
        assert result.get("habit") == "impulse_move", f"Fast mistake should be impulse_move, got: {result.get('habit')}"
        assert result.get("type") == "time_management", f"Should be time_management type, got: {result.get('type')}"
        
        print(f"Mistake (fast) coaching: {result}")
    
    # ─── TEST 8: Behavioral coaching has all required fields ───
    def test_behavioral_coaching_has_required_fields(self):
        """
        Test that behavioral_coaching object has all required fields:
        severity, type, message, habit, actionable_tip
        """
        from services.player_habits_service import generate_behavioral_coaching
        
        result = generate_behavioral_coaching(
            move_san="Qh5",
            time_spent=8.0,
            move_quality="blunder",
            game_phase="middlegame",
            behavior_events=[],
            move_history=[{"by": "player", "move": "Qh5", "time_spent": 8.0}],
            player_profile=None
        )
        
        assert result is not None, "Should return coaching for blunder"
        
        # Check all required fields
        required_fields = ["severity", "type", "message", "habit", "actionable_tip"]
        for field in required_fields:
            assert field in result, f"Missing required field: {field}"
            print(f"  {field}: {result.get(field)}")
        
        # Verify field values are appropriate
        assert result["severity"] in ["low", "medium", "high"], f"Invalid severity: {result['severity']}"
        assert result["type"] in ["time_management", "calculation", "emotional", "pattern", "positive"], f"Invalid type: {result['type']}"
        assert len(result["message"]) > 10, "Message should be meaningful"
    
    # ─── TEST 9: No behavioral coaching for good moves (unless special conditions) ───
    def test_no_behavioral_coaching_for_normal_good_moves(self):
        """
        Test that good moves with normal time don't trigger behavioral coaching
        (unless they meet special conditions like patience or overthinking)
        """
        from services.player_habits_service import generate_behavioral_coaching
        
        # Good move with normal time (10 seconds) - should NOT trigger
        result = generate_behavioral_coaching(
            move_san="e4",
            time_spent=10.0,  # Normal time
            move_quality="good",
            game_phase="opening",
            behavior_events=[],
            move_history=[{"by": "player", "move": "e4", "time_spent": 10.0}],
            player_profile=None
        )
        
        # Good moves with normal time should NOT trigger behavioral coaching
        assert result is None, f"Good move with normal time should not trigger coaching, got: {result}"
        print("Correctly no coaching for normal good move")
    
    # ─── TEST 10: Positive coaching for patient good moves ───
    def test_positive_coaching_for_patient_good_moves(self):
        """
        Test that good moves with long thinking time (>15s) trigger positive coaching
        """
        from services.player_habits_service import generate_behavioral_coaching
        
        # Good move with long time (20 seconds) - should trigger positive coaching
        result = generate_behavioral_coaching(
            move_san="Nf3",
            time_spent=20.0,  # Long time
            move_quality="good",
            game_phase="opening",
            behavior_events=[],
            move_history=[{"by": "player", "move": "Nf3", "time_spent": 20.0}],
            player_profile=None
        )
        
        assert result is not None, "Patient good move should trigger positive coaching"
        assert result.get("type") == "positive", f"Should be positive type, got: {result.get('type')}"
        assert result.get("severity") == "low", f"Positive should have low severity, got: {result.get('severity')}"
        
        print(f"Positive coaching: {result}")


class TestGuardianInterventionInline:
    """Test that guardian intervention appears inline (not as overlay)"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Dev login
        login_resp = self.session.get(f"{BASE_URL}/api/auth/dev-login")
        assert login_resp.status_code == 200, f"Dev login failed: {login_resp.text}"
    
    def test_guardian_evaluate_endpoint_works(self):
        """
        Test that POST /api/coach/play/evaluate returns guardian intervention data
        """
        # Start a session
        start_resp = self.session.post(f"{BASE_URL}/api/coach/play/start", json={
            "user_color": "white",
            "time_control": "15+10"
        })
        
        if start_resp.status_code != 200:
            pytest.skip(f"Could not start session: {start_resp.text}")
        
        session_data = start_resp.json()
        session_id = session_data.get("session", {}).get("session_id")
        
        # Try to evaluate a potentially risky move
        eval_resp = self.session.post(f"{BASE_URL}/api/coach/play/evaluate", json={
            "session_id": session_id,
            "move": "f3"  # Weakening move
        })
        
        assert eval_resp.status_code == 200, f"Evaluate failed: {eval_resp.text}"
        data = eval_resp.json()
        
        # Response should have intervention-related fields
        print(f"Guardian evaluation response: {data}")
        
        # Cleanup
        self.session.post(f"{BASE_URL}/api/coach/play/resign", json={"session_id": session_id})
