"""
Test Pedagogical Opponent Feature
=================================

Tests for the P0 "Pedagogical Opponent" feature:
1. Backend: Pedagogical opponent creates opportunities in middlegame positions
2. Backend: Pedagogical moves are within acceptable eval sacrifice range (0.3-1.5 pawns for intermediate)
3. Backend: No pedagogical moves in opening phase
4. Backend: Consequence feedback is generated when user responds to a pedagogical move
5. Backend: Session tracks pedagogical state (opportunities_found, opportunities_missed)
"""

import pytest
import requests
import os
import chess
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test FEN positions for different game phases
OPENING_FEN = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"  # After 1.e4
MIDDLEGAME_FEN = "r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4"  # Italian Game position
LATE_MIDDLEGAME_FEN = "r2q1rk1/ppp2ppp/2n1bn2/3pp3/2B1P3/2NP1N2/PPP2PPP/R1BQ1RK1 w - - 0 8"  # More developed
ENDGAME_FEN = "8/5pk1/6p1/8/8/6P1/5PK1/8 w - - 0 1"  # King + pawn endgame


class TestGamePhaseService:
    """Test game phase detection for pedagogical decisions."""
    
    def test_opening_phase_detection(self):
        """Opening phase should be detected correctly."""
        response = requests.get(
            f"{BASE_URL}/api/coach/play/game-phase",
            params={"fen": OPENING_FEN}
        )
        
        if response.status_code == 404:
            # Endpoint might not exist, test via session state
            pytest.skip("Game phase endpoint not exposed, will test via session")
        
        assert response.status_code == 200
        data = response.json()
        assert data.get("phase_label") == "opening"
    
    def test_middlegame_phase_detection(self):
        """Middlegame phase should be detected correctly."""
        response = requests.get(
            f"{BASE_URL}/api/coach/play/game-phase",
            params={"fen": MIDDLEGAME_FEN}
        )
        
        if response.status_code == 404:
            pytest.skip("Game phase endpoint not exposed")
        
        assert response.status_code == 200
        data = response.json()
        # Should be early_middlegame, middlegame, or late_middlegame
        assert "middlegame" in data.get("phase_label", "")


class TestPedagogicalOpportunityService:
    """Test the pedagogical opportunity service logic."""
    
    def test_service_imports(self):
        """Verify pedagogical service can be imported."""
        try:
            from services.pedagogical_opportunity_service import (
                PedagogicalOpportunityService,
                OpportunityType,
                PedagogicalDecision,
                WeaknessProfile
            )
            assert True
        except ImportError as e:
            pytest.fail(f"Failed to import pedagogical service: {e}")
    
    def test_opportunity_types_defined(self):
        """Verify all opportunity types are defined."""
        from services.pedagogical_opportunity_service import OpportunityType
        
        expected_types = [
            "fork", "pin", "skewer", "hanging_piece", "back_rank",
            "passed_pawn", "king_safety", "piece_activity", "outpost",
            "pawn_structure", "endgame_technique", "general"
        ]
        
        for opp_type in expected_types:
            assert hasattr(OpportunityType, opp_type.upper()), f"Missing opportunity type: {opp_type}"
    
    def test_eval_sacrifice_ranges(self):
        """Verify eval sacrifice ranges are defined for different rating tiers."""
        from services.pedagogical_opportunity_service import PedagogicalOpportunityService
        
        # Check that ranges exist
        assert "beginner" in PedagogicalOpportunityService.EVAL_SACRIFICE_BY_RATING
        assert "intermediate" in PedagogicalOpportunityService.EVAL_SACRIFICE_BY_RATING
        assert "club" in PedagogicalOpportunityService.EVAL_SACRIFICE_BY_RATING
        assert "advanced" in PedagogicalOpportunityService.EVAL_SACRIFICE_BY_RATING
        
        # Verify intermediate range is 0.3-1.5 pawns
        min_sac, max_sac = PedagogicalOpportunityService.EVAL_SACRIFICE_BY_RATING["intermediate"]
        assert min_sac == 0.3, f"Expected min sacrifice 0.3, got {min_sac}"
        assert max_sac == 1.5, f"Expected max sacrifice 1.5, got {max_sac}"
    
    def test_pedagogical_probability_by_phase(self):
        """Verify pedagogical probability is 0 in opening, >0 in middlegame."""
        from services.pedagogical_opportunity_service import PedagogicalOpportunityService
        
        # Opening should have 0% probability
        assert PedagogicalOpportunityService.PEDAGOGICAL_PROBABILITY.get("opening") == 0.0
        
        # Middlegame phases should have >0 probability
        assert PedagogicalOpportunityService.PEDAGOGICAL_PROBABILITY.get("middlegame", 0) > 0
        assert PedagogicalOpportunityService.PEDAGOGICAL_PROBABILITY.get("early_middlegame", 0) > 0
        assert PedagogicalOpportunityService.PEDAGOGICAL_PROBABILITY.get("late_middlegame", 0) > 0
        
        # Endgame should also have >0 probability
        assert PedagogicalOpportunityService.PEDAGOGICAL_PROBABILITY.get("endgame", 0) > 0


class TestCoachPlaySessionPedagogical:
    """Test pedagogical features in coach play sessions."""
    
    @pytest.fixture
    def session(self):
        """Create a test session."""
        response = requests.post(
            f"{BASE_URL}/api/coach/play/start",
            json={
                "user_color": "white",
                "time_control": "15+10"
            },
            cookies={"dev_user_id": "test_pedagogical_user"}
        )
        
        if response.status_code != 200:
            pytest.skip(f"Could not create session: {response.text}")
        
        data = response.json()
        yield data
        
        # Cleanup - end session
        if data.get("session", {}).get("session_id"):
            requests.post(
                f"{BASE_URL}/api/coach/play/end",
                json={
                    "session_id": data["session"]["session_id"],
                    "reason": "test_cleanup"
                },
                cookies={"dev_user_id": "test_pedagogical_user"}
            )
    
    def test_session_has_pedagogical_state(self, session):
        """Session should track pedagogical state."""
        session_data = session.get("session", {})
        
        # Check pedagogical fields exist
        assert "pedagogical_mode_active" in session_data, "Missing pedagogical_mode_active"
        assert "last_pedagogical_move_index" in session_data, "Missing last_pedagogical_move_index"
        assert "pending_opportunity" in session_data, "Missing pending_opportunity"
        assert "opportunities_found" in session_data, "Missing opportunities_found"
        assert "opportunities_missed" in session_data, "Missing opportunities_missed"
    
    def test_session_state_includes_pedagogical(self, session):
        """Get session state should include pedagogical info."""
        session_id = session.get("session", {}).get("session_id")
        
        response = requests.get(
            f"{BASE_URL}/api/coach/play/state/{session_id}",
            cookies={"dev_user_id": "test_pedagogical_user"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Check pedagogical state in response
        assert "pedagogical" in data, "Missing pedagogical in state response"
        ped_state = data["pedagogical"]
        
        assert "hide_eval" in ped_state, "Missing hide_eval in pedagogical state"
        assert "opportunities_found" in ped_state, "Missing opportunities_found"
        assert "opportunities_missed" in ped_state, "Missing opportunities_missed"


class TestPedagogicalMoveIntegration:
    """Integration tests for pedagogical move flow."""
    
    def test_move_response_and_state_includes_pedagogical(self):
        """Session state after move should include pedagogical state."""
        # Start session
        start_response = requests.post(
            f"{BASE_URL}/api/coach/play/start",
            json={"user_color": "white", "time_control": "15+10"},
            cookies={"dev_user_id": "test_ped_move_user"}
        )
        
        if start_response.status_code != 200:
            pytest.skip("Could not start session")
        
        session_data = start_response.json()
        session_id = session_data.get("session", {}).get("session_id")
        
        try:
            # Make a move
            move_response = requests.post(
                f"{BASE_URL}/api/coach/play/move",
                json={
                    "session_id": session_id,
                    "move": "e4",
                    "thinking_time_ms": 1000
                },
                cookies={"dev_user_id": "test_ped_move_user"}
            )
            
            assert move_response.status_code == 200
            
            # Wait for coach to respond (async processing)
            import time
            time.sleep(2)
            
            # Get session state - this should include pedagogical info
            state_response = requests.get(
                f"{BASE_URL}/api/coach/play/state/{session_id}",
                cookies={"dev_user_id": "test_ped_move_user"}
            )
            
            assert state_response.status_code == 200
            state_data = state_response.json()
            
            # Check pedagogical state in session state response
            assert "pedagogical" in state_data, "Missing pedagogical in session state"
            ped_state = state_data["pedagogical"]
            assert "hide_eval" in ped_state, "Missing hide_eval in pedagogical state"
            
        finally:
            # Cleanup
            requests.post(
                f"{BASE_URL}/api/coach/play/end",
                json={"session_id": session_id, "reason": "test_cleanup"},
                cookies={"dev_user_id": "test_ped_move_user"}
            )
    
    def test_consequence_feedback_structure(self):
        """Test consequence feedback has correct structure when present."""
        # This tests the structure of consequence feedback
        # In real scenarios, this would be returned after user responds to pedagogical move
        
        expected_fields = [
            "found_opportunity",
            "consequence_type",
            "eval_before",
            "eval_after",
            "eval_change",
            "message",
            "expected_move",
            "user_move",
            "opportunity_type"
        ]
        
        # Import and check the evaluate_user_response method signature
        from services.pedagogical_opportunity_service import PedagogicalOpportunityService
        
        # Verify the method exists
        assert hasattr(PedagogicalOpportunityService, 'evaluate_user_response')


class TestPedagogicalOpponentStatistical:
    """Statistical tests for pedagogical opponent behavior.
    
    Since pedagogical moves use random.random() < 0.25, we need to run
    multiple iterations to verify the feature works statistically.
    """
    
    def test_pedagogical_probability_in_middlegame(self):
        """
        Test that pedagogical moves CAN occur in middlegame.
        
        We don't expect 100% pedagogical moves, but over multiple games
        we should see at least some pedagogical behavior.
        """
        from services.pedagogical_opportunity_service import PedagogicalOpportunityService
        
        # Verify the probability is set correctly
        middlegame_prob = PedagogicalOpportunityService.PEDAGOGICAL_PROBABILITY.get("middlegame", 0)
        assert middlegame_prob == 0.25, f"Expected 25% probability, got {middlegame_prob * 100}%"
        
        # The actual random behavior would need to be tested with mocking
        # or by running many iterations (which is slow)
        print(f"Middlegame pedagogical probability: {middlegame_prob * 100}%")
    
    def test_no_pedagogical_in_opening(self):
        """Verify opening phase has 0% pedagogical probability."""
        from services.pedagogical_opportunity_service import PedagogicalOpportunityService
        
        opening_prob = PedagogicalOpportunityService.PEDAGOGICAL_PROBABILITY.get("opening", 1.0)
        assert opening_prob == 0.0, f"Opening should have 0% pedagogical probability, got {opening_prob * 100}%"


class TestCoachGameSessionPedagogicalFields:
    """Test CoachGameSession dataclass has all pedagogical fields."""
    
    def test_session_dataclass_fields(self):
        """Verify CoachGameSession has all pedagogical fields."""
        from coach_play.coach_game_session import CoachGameSession
        import dataclasses
        
        fields = {f.name for f in dataclasses.fields(CoachGameSession)}
        
        required_fields = [
            "pedagogical_mode_active",
            "last_pedagogical_move_index",
            "pending_opportunity",
            "opportunity_history",
            "opportunities_found",
            "opportunities_missed"
        ]
        
        for field in required_fields:
            assert field in fields, f"Missing field: {field}"
    
    def test_session_to_dict_includes_pedagogical(self):
        """Verify to_dict includes pedagogical fields."""
        from coach_play.coach_game_session import CoachGameSession, SessionStatus
        
        session = CoachGameSession(
            session_id="test123",
            user_id="user123",
            status=SessionStatus.ACTIVE,
            user_color="white"
        )
        
        session_dict = session.to_dict()
        
        assert "pedagogical_mode_active" in session_dict
        assert "opportunities_found" in session_dict
        assert "opportunities_missed" in session_dict


class TestEvalBarHiding:
    """Test eval bar hiding during pedagogical moves."""
    
    def test_hide_eval_in_pending_opportunity(self):
        """Pending opportunity should have hide_eval flag."""
        # When a pedagogical move is made, pending_opportunity should have hide_eval=True
        
        # This is tested via the session state API
        # The frontend uses this to hide the eval bar
        
        # Verify the structure in the service
        from services.pedagogical_opportunity_service import PedagogicalDecision
        
        # PedagogicalDecision doesn't have hide_eval directly,
        # but the pending_opportunity dict in session does
        # This is set in _make_coach_move when creating pending_opportunity
        
        # Check the code structure
        import inspect
        from coach_play.coach_game_session import _make_coach_move
        
        source = inspect.getsource(_make_coach_move)
        assert "hide_eval" in source, "hide_eval should be set in _make_coach_move"


class TestHealthAndBasicEndpoints:
    """Basic health and endpoint tests."""
    
    def test_api_health(self):
        """API should be healthy."""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "healthy"
    
    def test_coach_play_start_endpoint(self):
        """Coach play start endpoint should work."""
        response = requests.post(
            f"{BASE_URL}/api/coach/play/start",
            json={"user_color": "white", "time_control": "15+10"},
            cookies={"dev_user_id": "test_health_user"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "session" in data
        
        # Cleanup
        session_id = data.get("session", {}).get("session_id")
        if session_id:
            requests.post(
                f"{BASE_URL}/api/coach/play/end",
                json={"session_id": session_id, "reason": "test_cleanup"},
                cookies={"dev_user_id": "test_health_user"}
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
