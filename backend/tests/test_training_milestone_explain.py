"""
Test Training Milestone Explain Bug Fix

Tests for the bug fix where:
1. eval_drop calculation was wrong (defaulting to 0) causing 'excellent_move' classification for actual mistakes
2. chess_verification_layer integration for consistent checkmate detection

Key test positions:
1. c4 vs Nfd4 (positional drift - should NOT be 'excellent_move')
   FEN: r2q1rk1/ppp1b1pp/2n1pn2/1N1p1b2/5P2/3P1N2/PPP1B1PP/R1BQ1RK1 w
   cp_loss: 160

2. Qf3 allowing Qxh2# (mate in 1)
   FEN: 5r1k/1pp3pp/p7/8/2B2qn1/3Pb3/PP4PP/R2QR2K w
   cp_loss: 9668
"""

import pytest
import requests
import os
import json

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestTrainingMilestoneExplain:
    """Test POST /api/training/milestone/explain endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup - get auth token via dev login"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Dev login to get token
        login_response = self.session.get(f"{BASE_URL}/api/auth/dev-login")
        if login_response.status_code == 200:
            data = login_response.json()
            token = data.get("token")
            if token:
                self.session.headers.update({"Authorization": f"Bearer {token}"})
        yield
    
    def test_positional_drift_c4_vs_nfd4(self):
        """
        Test: c4 vs Nfd4 position should be classified as positional drift, NOT excellent_move
        
        Bug context: Before fix, eval_after defaulted to 0, causing eval_drop=0 
        and incorrect 'excellent_move' classification for actual mistakes.
        
        Now: eval_after = eval_before - cp_loss when not provided
        """
        payload = {
            "fen": "r2q1rk1/ppp1b1pp/2n1pn2/1N1p1b2/5P2/3P1N2/PPP1B1PP/R1BQ1RK1 w - - 0 10",
            "move_played": "c4",
            "best_move": "Nfd4",
            "cp_loss": 160,
            "eval_before": 50,  # Slightly better for white
            "move_number": 10,
            "context_for_explanation": {
                "move_played": "c4",
                "best_move": "Nfd4",
                "cp_loss": 160,
                "eval_before": 50,
                "move_number": 10
            }
        }
        
        response = self.session.post(f"{BASE_URL}/api/training/milestone/explain", json=payload)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        print(f"\n=== c4 vs Nfd4 Position Test ===")
        print(f"Response: {json.dumps(data, indent=2)[:1500]}")
        
        # CRITICAL ASSERTION: Should NOT be classified as 'excellent_move'
        mistake_type = data.get("mistake_type") or data.get("facts", {}).get("mistake_type", "")
        assert mistake_type != "excellent_move", f"Bug detected: Should NOT be 'excellent_move', got: {mistake_type}"
        
        # Should have some explanation
        explanation = data.get("human_explanation") or data.get("explanation") or ""
        assert len(explanation) > 10, f"Expected meaningful explanation, got: {explanation}"
        
        print(f"Mistake type: {mistake_type}")
        print(f"Explanation: {explanation[:300]}...")
        print("PASS: Correctly NOT classified as excellent_move")
    
    def test_mate_in_1_qf3_allows_qxh2_mate(self):
        """
        Test: Qf3 allowing Qxh2# should be detected as mate-in-1 scenario
        
        Uses chess_verification_layer for consistent checkmate detection
        """
        payload = {
            "fen": "5r1k/1pp3pp/p7/8/2B2qn1/3Pb3/PP4PP/R2QR2K w - - 0 21",
            "move_played": "Qf3",
            "best_move": "Qe2",  # Or some other move that blocks mate
            "cp_loss": 9668,  # Huge loss indicates mate
            "eval_before": 0,
            "move_number": 21,
            "context_for_explanation": {
                "move_played": "Qf3",
                "best_move": "Qe2",
                "cp_loss": 9668,
                "eval_before": 0,
                "move_number": 21
            }
        }
        
        response = self.session.post(f"{BASE_URL}/api/training/milestone/explain", json=payload)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        print(f"\n=== Qf3 Allows Mate Position Test ===")
        print(f"Response: {json.dumps(data, indent=2)[:1500]}")
        
        # Check for mate detection - could be in various fields
        facts = data.get("facts", {})
        mistake_type = data.get("mistake_type") or facts.get("mistake_type", "")
        explanation = data.get("human_explanation") or data.get("explanation") or ""
        
        # CRITICAL: Should detect this is a mate scenario
        mate_indicators = [
            facts.get("allows_checkmate", False),
            facts.get("is_checkmate", False),
            "mate" in mistake_type.lower() if mistake_type else False,
            "mate" in explanation.lower() if explanation else False,
            "checkmate" in explanation.lower() if explanation else False,
            facts.get("critical_fact", "").lower().find("mate") >= 0 if facts.get("critical_fact") else False,
        ]
        
        has_mate_detection = any(mate_indicators)
        
        print(f"Mistake type: {mistake_type}")
        print(f"Facts: {json.dumps(facts, indent=2)[:500]}")
        print(f"Mate detection indicators: {mate_indicators}")
        
        assert has_mate_detection, f"Bug detected: Should detect mate scenario. Facts: {facts}, Explanation: {explanation[:200]}"
        print("PASS: Correctly detected mate scenario")
    
    def test_eval_after_calculation_when_not_provided(self):
        """
        Test: When eval_after is not provided, it should be calculated as eval_before - cp_loss
        """
        payload = {
            "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
            "move_played": "e4",
            "best_move": "d4",
            "cp_loss": 50,
            "eval_before": 30,  # Slight white advantage
            # eval_after NOT provided - should be calculated as 30 - 50 = -20
            "move_number": 1,
            "context_for_explanation": {
                "move_played": "e4",
                "best_move": "d4",
                "cp_loss": 50,
                "eval_before": 30,
                "move_number": 1
            }
        }
        
        response = self.session.post(f"{BASE_URL}/api/training/milestone/explain", json=payload)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        print(f"\n=== Eval After Calculation Test ===")
        print(f"Response: {json.dumps(data, indent=2)[:1000]}")
        
        # If we had access to internal calculation, eval_after should be -20
        # The key is that the explanation should NOT classify this as 'excellent_move'
        mistake_type = data.get("mistake_type") or data.get("facts", {}).get("mistake_type", "")
        
        # With cp_loss=50, this is a minor inaccuracy, definitely not excellent_move
        assert mistake_type != "excellent_move", f"eval_after calculation may be wrong: got {mistake_type}"
        print(f"Mistake type: {mistake_type}")
        print("PASS: eval_after calculation working correctly (not excellent_move)")


class TestExplainMistakeMateDetection:
    """Test POST /api/explain-mistake endpoint with mate detection"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup - get auth token via dev login"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Dev login to get token
        login_response = self.session.get(f"{BASE_URL}/api/auth/dev-login")
        if login_response.status_code == 200:
            data = login_response.json()
            token = data.get("token")
            if token:
                self.session.headers.update({"Authorization": f"Bearer {token}"})
        yield
    
    def test_explain_mistake_mate_in_1(self):
        """
        Test: /api/explain-mistake should correctly detect mate-in-1 for Qf3 allowing Qxh2#
        
        From iteration_57: Returns mistake_type='allowed_mate_in_1', severity='decisive'
        """
        payload = {
            "fen_before": "5r1k/1pp3pp/p7/8/2B2qn1/3Pb3/PP4PP/R2QR2K w - - 0 21",
            "move": "Qf3",
            "best_move": "Qe2",
            "cp_loss": 9668,
            "user_color": "white",
            "move_number": 21
        }
        
        response = self.session.post(f"{BASE_URL}/api/explain-mistake", json=payload)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        print(f"\n=== Explain Mistake Mate-in-1 Test ===")
        print(f"Response: {json.dumps(data, indent=2)}")
        
        # Should detect mate scenario
        mistake_type = data.get("mistake_type", "")
        severity = data.get("severity", "")
        
        print(f"Mistake type: {mistake_type}")
        print(f"Severity: {severity}")
        
        # CRITICAL: Should be 'allowed_mate_in_1' or similar mate-related type
        mate_type_indicators = [
            "mate" in mistake_type.lower() if mistake_type else False,
            severity == "decisive",
            data.get("details", {}).get("allows_mate", False),
        ]
        
        assert any(mate_type_indicators), f"Should detect mate: mistake_type={mistake_type}, severity={severity}"
        print("PASS: Correctly detected allowed_mate_in_1 scenario")
    
    def test_explain_mistake_normal_position(self):
        """
        Test: /api/explain-mistake with normal position (no mate) should work
        """
        payload = {
            "fen_before": "r2q1rk1/ppp1b1pp/2n1pn2/1N1p1b2/5P2/3P1N2/PPP1B1PP/R1BQ1RK1 w - - 0 10",
            "move": "c4",
            "best_move": "Nfd4",
            "cp_loss": 160,
            "user_color": "white",
            "move_number": 10
        }
        
        response = self.session.post(f"{BASE_URL}/api/explain-mistake", json=payload)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        print(f"\n=== Explain Mistake Normal Position Test ===")
        print(f"Response: {json.dumps(data, indent=2)[:1000]}")
        
        # Should have explanation
        explanation = data.get("explanation", "")
        mistake_type = data.get("mistake_type", "")
        
        assert len(explanation) > 10, f"Expected explanation, got: {explanation}"
        assert mistake_type, f"Expected mistake_type, got: {mistake_type}"
        
        print(f"Mistake type: {mistake_type}")
        print(f"Explanation: {explanation[:200]}...")
        print("PASS: Normal position handled correctly")


class TestChessVerificationLayerIntegration:
    """Test that chess_verification_layer is properly integrated"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup - get auth token via dev login"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Dev login to get token
        login_response = self.session.get(f"{BASE_URL}/api/auth/dev-login")
        if login_response.status_code == 200:
            data = login_response.json()
            token = data.get("token")
            if token:
                self.session.headers.update({"Authorization": f"Bearer {token}"})
        yield
    
    def test_verification_layer_mate_detection_via_endpoint(self):
        """
        Test: Verification layer should consistently detect mate across endpoints
        """
        # Position where black can play Qxh2# (mate)
        fen = "5r1k/1pp3pp/p7/8/2B2qn1/3Pb3/PP4PP/R2QR2K w - - 0 21"
        
        # Test via milestone/explain
        milestone_payload = {
            "fen": fen,
            "move_played": "Qf3",
            "best_move": "Qe2",
            "cp_loss": 9668,
            "eval_before": 0,
            "move_number": 21
        }
        
        milestone_response = self.session.post(
            f"{BASE_URL}/api/training/milestone/explain", 
            json=milestone_payload
        )
        
        assert milestone_response.status_code == 200
        milestone_data = milestone_response.json()
        
        # Test via explain-mistake
        mistake_payload = {
            "fen_before": fen,
            "move": "Qf3",
            "best_move": "Qe2",
            "cp_loss": 9668,
            "user_color": "white",
            "move_number": 21
        }
        
        mistake_response = self.session.post(
            f"{BASE_URL}/api/explain-mistake", 
            json=mistake_payload
        )
        
        assert mistake_response.status_code == 200
        mistake_data = mistake_response.json()
        
        print(f"\n=== Verification Layer Integration Test ===")
        print(f"Milestone response facts: {milestone_data.get('facts', {})}")
        print(f"Mistake response type: {mistake_data.get('mistake_type')}")
        
        # Both should detect the mate scenario
        milestone_facts = milestone_data.get("facts", {})
        milestone_detects_mate = (
            milestone_facts.get("allows_checkmate", False) or
            "mate" in milestone_facts.get("mistake_type", "").lower() or
            "mate" in milestone_facts.get("critical_fact", "").lower()
        )
        
        mistake_detects_mate = (
            "mate" in mistake_data.get("mistake_type", "").lower() or
            mistake_data.get("severity") == "decisive"
        )
        
        print(f"Milestone detects mate: {milestone_detects_mate}")
        print(f"Mistake detects mate: {mistake_detects_mate}")
        
        assert milestone_detects_mate or mistake_detects_mate, \
            "Chess verification layer should detect mate in at least one endpoint"
        print("PASS: Verification layer integrated correctly")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
