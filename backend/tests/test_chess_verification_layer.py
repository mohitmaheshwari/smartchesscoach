"""
Test suite for chess_verification_layer.py - Unified Chess Position Verification

This module tests the SINGLE SOURCE OF TRUTH for position analysis:
- verify_position(): Analyzes any FEN and returns verified facts
- verify_move(): Analyzes what happens when a move is played
- get_critical_facts(): Provides LLM-ready context for explanations

CRITICAL TEST CASE (from main agent):
FEN: 5r1k/1pp3pp/p7/8/2B2qn1/3Pb3/PP4PP/R2QR2K w - - 1 21
Move: Qf3 (allows mate in 1)
Best Move: Qxg4
Expected: mistake_type='allowed_mate_in_1', mating_move='Qxh2#'
"""

import pytest
import requests
import os
import sys

# Add backend to path for direct imports
sys.path.insert(0, '/app/backend')

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://adaptive-trainer-3.preview.emergentagent.com')

# ============================================================================
# TEST DATA - The specific test case from main agent
# ============================================================================

MATE_IN_1_TEST_CASE = {
    "fen": "5r1k/1pp3pp/p7/8/2B2qn1/3Pb3/PP4PP/R2QR2K w - - 1 21",
    "move": "Qf3",
    "best_move": "Qxg4",
    "cp_loss": 9999,  # Mate = huge cp_loss
    "user_color": "white",
    "move_number": 21,
    "expected_mistake_type": "allowed_mate_in_1",
    "expected_mating_move": "Qxh2#"  # Black can play Qxh2 checkmate
}

# Additional test cases for comprehensive coverage
ADDITIONAL_MATE_TESTS = {
    "missed_mate_in_1": {
        # Position where best_move is checkmate
        "fen": "r1bqk2r/pppp1ppp/2n2n2/2b1p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 4 4",
        "move": "Qf3",  # Not the best - misses Qxf7#
        "best_move": "Qxf7+",  # Checkmate!
        "cp_loss": 9999,
        "user_color": "white",
        "expected_mistake_type": "missed_mate_in_1"
    }
}


class TestVerificationLayerDirect:
    """Direct tests of chess_verification_layer.py functions"""
    
    def test_verify_position_valid_fen(self):
        """Test verify_position returns correct structure for valid FEN"""
        from chess_verification_layer import verify_position
        
        fen = MATE_IN_1_TEST_CASE["fen"]
        result = verify_position(fen)
        
        assert result.get("valid") == True, f"Expected valid=True, got: {result}"
        assert "side_to_move" in result
        assert result["side_to_move"] == "white"  # White to move in this position
        assert "is_check" in result
        assert "is_checkmate" in result
        assert "mate_in_1" in result
        
        print(f"✓ verify_position returns correct structure")
        print(f"  Side to move: {result['side_to_move']}")
        print(f"  In check: {result['is_check']}")
        print(f"  Mate in 1: {result['mate_in_1']}")
    
    def test_verify_position_invalid_fen(self):
        """Test verify_position handles invalid FEN gracefully"""
        from chess_verification_layer import verify_position
        
        result = verify_position("invalid_fen")
        
        assert result.get("valid") == False or result.get("error") is not None
        print(f"✓ verify_position handles invalid FEN correctly")
    
    def test_check_mate_in_1_function(self):
        """Test check_mate_in_1 directly"""
        from chess_verification_layer import safe_board, check_mate_in_1
        
        fen = MATE_IN_1_TEST_CASE["fen"]
        board = safe_board(fen)
        
        # Push the user's move (Qf3) and check if opponent has mate
        board.push_san(MATE_IN_1_TEST_CASE["move"])
        
        # Now from Black's perspective - do they have mate in 1?
        mating_move = check_mate_in_1(board)
        
        print(f"  After {MATE_IN_1_TEST_CASE['move']}, opponent's mating move: {mating_move}")
        
        # Black should have Qxh2# available
        assert mating_move is not None, "Expected Black to have mate in 1 after Qf3"
        assert "Qxh2" in mating_move or "h2" in mating_move, f"Expected Qxh2#, got: {mating_move}"
        
        print(f"✓ check_mate_in_1 correctly identifies {mating_move} as checkmate")
    
    def test_verify_move_detects_allows_mate_in_1(self):
        """CRITICAL TEST: verify_move must detect that Qf3 allows mate in 1"""
        from chess_verification_layer import verify_move
        
        fen = MATE_IN_1_TEST_CASE["fen"]
        move = MATE_IN_1_TEST_CASE["move"]
        best_move = MATE_IN_1_TEST_CASE["best_move"]
        cp_loss = MATE_IN_1_TEST_CASE["cp_loss"]
        
        result = verify_move(fen, move, best_move, cp_loss)
        
        assert result.get("valid") == True, f"verify_move failed: {result}"
        
        # Check critical_issues
        critical_issues = result.get("critical_issues", [])
        print(f"  Critical issues found: {len(critical_issues)}")
        for issue in critical_issues:
            print(f"    - {issue.get('type')}: {issue.get('detail')}")
        
        # The most_critical should be allows_mate_in_1
        most_critical = result.get("most_critical")
        assert most_critical is not None, "Expected a critical issue for mate-allowing move"
        assert most_critical["type"] == "allows_mate_in_1", f"Expected allows_mate_in_1, got: {most_critical['type']}"
        
        # Check that mating_move is included
        assert "mating_move" in most_critical, "Expected mating_move in critical issue details"
        mating_move = most_critical["mating_move"]
        print(f"  Most critical: {most_critical['type']}")
        print(f"  Mating move: {mating_move}")
        
        # The mating move should be Qxh2#
        assert "Qxh2" in mating_move or "h2" in mating_move, f"Expected Qxh2#, got: {mating_move}"
        
        print(f"✓ verify_move correctly detects allows_mate_in_1 with mating_move={mating_move}")
    
    def test_get_critical_facts_returns_mate_info(self):
        """Test get_critical_facts provides correct info for mate-allowing move"""
        from chess_verification_layer import get_critical_facts
        
        fen = MATE_IN_1_TEST_CASE["fen"]
        user_move = MATE_IN_1_TEST_CASE["move"]
        best_move = MATE_IN_1_TEST_CASE["best_move"]
        cp_loss = MATE_IN_1_TEST_CASE["cp_loss"]
        
        facts = get_critical_facts(fen, user_move, best_move, cp_loss)
        
        print(f"  primary_issue: {facts.get('primary_issue')}")
        print(f"  primary_detail: {facts.get('primary_detail')}")
        print(f"  thinking_habit: {facts.get('thinking_habit')}")
        print(f"  mating_move: {facts.get('mating_move')}")
        
        # Primary issue should be allows_mate_in_1
        assert facts["primary_issue"] == "allows_mate_in_1", f"Expected allows_mate_in_1, got: {facts['primary_issue']}"
        
        # Should include mating move
        assert facts.get("mating_move") is not None, "Expected mating_move in facts"
        
        # Should have thinking habit
        assert facts.get("thinking_habit") is not None, "Expected thinking_habit for mate-allowing move"
        
        print(f"✓ get_critical_facts returns correct mate information")


class TestVerificationLayerIntegration:
    """Integration tests via /api/explain-mistake endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login via dev endpoint and store session"""
        self.session = requests.Session()
        resp = self.session.get(f"{BASE_URL}/api/auth/dev-login")
        assert resp.status_code == 200, f"Dev login failed: {resp.text}"
    
    def test_explain_mistake_detects_mate_in_1(self):
        """CRITICAL: /api/explain-mistake must return allowed_mate_in_1 for the test case"""
        payload = {
            "fen_before": MATE_IN_1_TEST_CASE["fen"],
            "move": MATE_IN_1_TEST_CASE["move"],
            "best_move": MATE_IN_1_TEST_CASE["best_move"],
            "cp_loss": MATE_IN_1_TEST_CASE["cp_loss"],
            "user_color": MATE_IN_1_TEST_CASE["user_color"],
            "move_number": MATE_IN_1_TEST_CASE["move_number"]
        }
        
        resp = self.session.post(f"{BASE_URL}/api/explain-mistake", json=payload)
        
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        
        print(f"  Response keys: {list(data.keys())}")
        print(f"  mistake_type: {data.get('mistake_type')}")
        print(f"  short_label: {data.get('short_label')}")
        print(f"  severity: {data.get('severity')}")
        print(f"  explanation: {data.get('explanation', '')[:200]}...")
        print(f"  details: {data.get('details', {})}")
        
        # CRITICAL ASSERTION: mistake_type must be allowed_mate_in_1
        assert data["mistake_type"] == "allowed_mate_in_1", \
            f"Expected allowed_mate_in_1, got: {data['mistake_type']}"
        
        # Severity should be decisive
        assert data["severity"] == "decisive", \
            f"Expected severity=decisive for mate, got: {data['severity']}"
        
        # Details should include mating_move
        details = data.get("details", {})
        if "mating_move" in details:
            assert "Qxh2" in details["mating_move"], \
                f"Expected Qxh2 in mating_move, got: {details['mating_move']}"
        
        # Explanation should mention checkmate
        explanation = data.get("explanation", "").lower()
        assert "mate" in explanation or "checkmate" in explanation, \
            f"Explanation should mention mate/checkmate: {data.get('explanation')}"
        
        print(f"✓ /api/explain-mistake correctly identifies mate in 1")
        print(f"  Move {MATE_IN_1_TEST_CASE['move']} allows {details.get('mating_move', 'checkmate')}")
    
    def test_explain_mistake_short_label_for_mate(self):
        """Test that short_label is appropriate for mate-allowing move"""
        payload = {
            "fen_before": MATE_IN_1_TEST_CASE["fen"],
            "move": MATE_IN_1_TEST_CASE["move"],
            "best_move": MATE_IN_1_TEST_CASE["best_move"],
            "cp_loss": MATE_IN_1_TEST_CASE["cp_loss"],
            "user_color": MATE_IN_1_TEST_CASE["user_color"],
            "move_number": MATE_IN_1_TEST_CASE["move_number"]
        }
        
        resp = self.session.post(f"{BASE_URL}/api/explain-mistake", json=payload)
        assert resp.status_code == 200
        
        data = resp.json()
        short_label = data.get("short_label", "")
        
        # Short label should mention mate
        assert "mate" in short_label.lower() or "Mate" in short_label, \
            f"short_label should mention mate for allowed_mate_in_1: got '{short_label}'"
        
        print(f"✓ short_label is appropriate: '{short_label}'")
    
    def test_explain_mistake_thinking_habit_for_mate(self):
        """Test that thinking_habit is provided for mate-allowing move"""
        payload = {
            "fen_before": MATE_IN_1_TEST_CASE["fen"],
            "move": MATE_IN_1_TEST_CASE["move"],
            "best_move": MATE_IN_1_TEST_CASE["best_move"],
            "cp_loss": MATE_IN_1_TEST_CASE["cp_loss"],
            "user_color": MATE_IN_1_TEST_CASE["user_color"],
            "move_number": MATE_IN_1_TEST_CASE["move_number"]
        }
        
        resp = self.session.post(f"{BASE_URL}/api/explain-mistake", json=payload)
        assert resp.status_code == 200
        
        data = resp.json()
        thinking_habit = data.get("thinking_habit")
        
        assert thinking_habit is not None, "thinking_habit should be provided for mate mistake"
        assert len(thinking_habit) > 10, "thinking_habit should be meaningful"
        
        # Should mention checking for checks/mate
        assert "check" in thinking_habit.lower() or "mate" in thinking_habit.lower(), \
            f"thinking_habit should guide checking for mate: '{thinking_habit}'"
        
        print(f"✓ thinking_habit provided: '{thinking_habit}'")


class TestPositionAnalysisServiceIntegration:
    """Test that position_analysis_service uses verification layer"""
    
    def test_generate_verified_insight_uses_verification_layer(self):
        """Test that generate_verified_insight uses chess_verification_layer"""
        from position_analysis_service import generate_verified_insight
        
        fen = MATE_IN_1_TEST_CASE["fen"]
        user_move = MATE_IN_1_TEST_CASE["move"]
        best_move = MATE_IN_1_TEST_CASE["best_move"]
        eval_change = -99.0  # Huge eval drop for mate
        
        insights = generate_verified_insight(fen, user_move, best_move, eval_change)
        
        print(f"  critical_issue: {insights.get('critical_issue')}")
        print(f"  verified_impact: {insights.get('verified_impact')}")
        print(f"  thinking_habit: {insights.get('thinking_habit')}")
        
        # Should have critical_issue set to mate-related
        critical_issue = insights.get("critical_issue", "")
        assert "mate" in critical_issue or critical_issue == "allows_mate_in_1", \
            f"Expected mate-related critical_issue, got: {critical_issue}"
        
        print(f"✓ generate_verified_insight correctly identifies mate threat")


class TestMistakeExplanationServiceIntegration:
    """Test that mistake_explanation_service uses verification layer"""
    
    def test_analyze_mistake_position_detects_mate(self):
        """Test analyze_mistake_position for mate-allowing move"""
        from mistake_explanation_service import analyze_mistake_position
        
        fen = MATE_IN_1_TEST_CASE["fen"]
        move = MATE_IN_1_TEST_CASE["move"]
        best_move = MATE_IN_1_TEST_CASE["best_move"]
        cp_loss = MATE_IN_1_TEST_CASE["cp_loss"]
        user_color = MATE_IN_1_TEST_CASE["user_color"]
        
        analysis = analyze_mistake_position(fen, move, best_move, cp_loss, user_color)
        
        print(f"  mistake_type: {analysis.get('mistake_type')}")
        print(f"  severity: {analysis.get('severity')}")
        print(f"  details: {analysis.get('details')}")
        print(f"  note: {analysis.get('note')}")
        
        # Must be allowed_mate_in_1
        assert analysis["mistake_type"] == "allowed_mate_in_1", \
            f"Expected allowed_mate_in_1, got: {analysis['mistake_type']}"
        
        # Severity must be decisive
        assert analysis["severity"] == "decisive", \
            f"Expected decisive, got: {analysis['severity']}"
        
        # Details should have mating_move
        details = analysis.get("details", {})
        assert "mating_move" in details, "Details should include mating_move"
        
        print(f"✓ analyze_mistake_position correctly identifies mate in 1")


class TestAdditionalMateScenarios:
    """Test additional mate-related scenarios"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login via dev endpoint"""
        self.session = requests.Session()
        resp = self.session.get(f"{BASE_URL}/api/auth/dev-login")
        assert resp.status_code == 200
    
    def test_actual_game_move_21_qf3(self):
        """Test the actual game position: Move 21 Qf3 in game 9935cf55-2d7c-419a-8273-2409de102760"""
        # This is the exact test case from the bug report
        payload = {
            "fen_before": "5r1k/1pp3pp/p7/8/2B2qn1/3Pb3/PP4PP/R2QR2K w - - 1 21",
            "move": "Qf3",
            "best_move": "Qxg4",
            "cp_loss": 9999,  # Mate = decisive
            "user_color": "white",
            "move_number": 21
        }
        
        resp = self.session.post(f"{BASE_URL}/api/explain-mistake", json=payload)
        
        assert resp.status_code == 200
        data = resp.json()
        
        print("\n=== ACTUAL GAME TEST: Move 21 Qf3 ===")
        print(f"  mistake_type: {data.get('mistake_type')}")
        print(f"  short_label: {data.get('short_label')}")
        print(f"  severity: {data.get('severity')}")
        print(f"  details: {data.get('details')}")
        print(f"  explanation: {data.get('explanation')}")
        
        # CRITICAL: This MUST return allowed_mate_in_1
        assert data["mistake_type"] == "allowed_mate_in_1", \
            f"CRITICAL FAILURE: Expected allowed_mate_in_1, got: {data['mistake_type']}"
        
        # The mating move should be Qxh2#
        details = data.get("details", {})
        mating_move = details.get("mating_move", "")
        assert "Qxh2" in mating_move or "h2" in mating_move, \
            f"Expected Qxh2# as mating move, got: {mating_move}"
        
        print(f"\n✓ Move 21 Qf3 correctly identified as allowing mate in 1 (Qxh2#)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
