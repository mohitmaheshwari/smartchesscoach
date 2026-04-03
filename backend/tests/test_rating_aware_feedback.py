"""
Rating-Aware Feedback System Tests
===================================

Tests the rating-aware move classification and coaching message generation:
1. _classify_move_quality with different ratings (800, 1200, 1600, 1900)
2. _generate_coaching_message for beginners vs intermediate players
3. Puzzle extraction rating-aware thresholds

Run: cd /app/backend && pytest tests/test_rating_aware_feedback.py -v
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.realtime_coaching_feedback import (
    _classify_move_quality,
    _generate_coaching_message
)
from services.puzzle_extraction_service import extract_puzzles_from_game


class TestClassifyMoveQuality:
    """Test rating-aware move classification thresholds"""
    
    def test_800_rating_small_loss_is_good(self):
        """800-rated player: -30cp loss should be 'good' (beginner threshold is lenient)"""
        # eval_before=0, eval_after=-0.3 (30cp loss for white)
        quality = _classify_move_quality(
            eval_before=0.0, 
            eval_after=-0.30, 
            user_color="white", 
            user_rating=800
        )
        assert quality == "good", f"Expected 'good' for 800 player with -30cp, got '{quality}'"
    
    def test_800_rating_120cp_loss_is_inaccuracy(self):
        """800-rated player: -120cp loss should be 'inaccuracy' (not 'mistake' like for higher rated)"""
        # For 800 player: inaccuracy threshold is -150cp, mistake is -300cp
        # -120cp is between good (-30) and inaccuracy (-150), so it's inaccuracy
        quality = _classify_move_quality(
            eval_before=0.0, 
            eval_after=-1.20, 
            user_color="white", 
            user_rating=800
        )
        assert quality == "inaccuracy", f"Expected 'inaccuracy' for 800 player with -120cp, got '{quality}'"
    
    def test_1600_rating_120cp_loss_is_mistake(self):
        """1600-rated player: -120cp loss should be 'mistake'"""
        # For 1600 player: inaccuracy threshold is -50cp, mistake is -150cp
        # -120cp is between inaccuracy (-50) and mistake (-150), so it's mistake
        quality = _classify_move_quality(
            eval_before=0.0, 
            eval_after=-1.20, 
            user_color="white", 
            user_rating=1600
        )
        assert quality == "mistake", f"Expected 'mistake' for 1600 player with -120cp, got '{quality}'"
    
    def test_1900_rating_120cp_loss_is_blunder(self):
        """1900-rated player: -120cp loss should be 'blunder'"""
        # For 1900 player: inaccuracy threshold is -30cp, mistake is -100cp
        # -120cp is worse than mistake (-100), so it's blunder
        quality = _classify_move_quality(
            eval_before=0.0, 
            eval_after=-1.20, 
            user_color="white", 
            user_rating=1900
        )
        assert quality == "blunder", f"Expected 'blunder' for 1900 player with -120cp, got '{quality}'"
    
    def test_800_rating_350cp_loss_is_blunder(self):
        """800-rated player: -350cp loss should be 'blunder' (big blunders caught at all levels)"""
        # For 800 player: mistake threshold is -300cp, so -350cp is blunder
        quality = _classify_move_quality(
            eval_before=0.0, 
            eval_after=-3.50, 
            user_color="white", 
            user_rating=800
        )
        assert quality == "blunder", f"Expected 'blunder' for 800 player with -350cp, got '{quality}'"
    
    def test_black_player_perspective(self):
        """Test that evaluation is correctly calculated from black's perspective"""
        # For black: positive eval change is good (eval goes from 0 to +0.5 means black is worse)
        # eval_before=0, eval_after=0.5 means white improved, so black lost 50cp
        quality = _classify_move_quality(
            eval_before=0.0, 
            eval_after=0.50, 
            user_color="black", 
            user_rating=1200
        )
        # For 1200 player: -50cp is between good (-20) and inaccuracy (-75)
        assert quality == "inaccuracy", f"Expected 'inaccuracy' for black with +50cp eval change, got '{quality}'"
    
    def test_excellent_move_detection(self):
        """Test that moves that improve position are classified as excellent"""
        # eval_before=0, eval_after=0.5 for white means +50cp gain
        quality = _classify_move_quality(
            eval_before=0.0, 
            eval_after=0.50, 
            user_color="white", 
            user_rating=1200
        )
        assert quality == "excellent", f"Expected 'excellent' for +50cp gain, got '{quality}'"


class TestGenerateCoachingMessage:
    """Test rating-aware coaching message generation"""
    
    def test_800_player_inaccuracy_simplified(self):
        """800-rated player with inaccuracy gets simplified message (no correction shown)"""
        result = _generate_coaching_message(
            user_move="Nf3",
            quality="inaccuracy",
            best_move="Nd5",
            tactical_analysis={},
            coach_move="e5",
            understanding_context=None,
            user_name="",
            user_rating=800
        )
        
        # Beginners should get "fine for now" message, not detailed correction
        assert "fine for now" in result["coaching_message"].lower(), \
            f"Expected 'fine for now' for 800 player inaccuracy, got: {result['coaching_message']}"
        # Should NOT mention the best move for beginners
        assert "Nd5" not in result["coaching_message"], \
            f"Should not show best move to beginner for inaccuracy: {result['coaching_message']}"
    
    def test_1600_player_inaccuracy_full_correction(self):
        """1600-rated player with inaccuracy gets full correction with best move"""
        result = _generate_coaching_message(
            user_move="Nf3",
            quality="inaccuracy",
            best_move="Nd5",
            tactical_analysis={},
            coach_move="e5",
            understanding_context=None,
            user_name="",
            user_rating=1600
        )
        
        # Intermediate players should see the best move
        assert "Nd5" in result["coaching_message"], \
            f"Expected best move 'Nd5' in message for 1600 player, got: {result['coaching_message']}"
    
    def test_800_player_blunder_direct_message(self):
        """800-rated player with blunder gets direct message (not Socratic)"""
        result = _generate_coaching_message(
            user_move="Qh4",
            quality="blunder",
            best_move="Nf3",
            tactical_analysis={"best_move_captures": "knight"},
            coach_move="Nxe5",
            understanding_context=None,
            user_name="",
            user_rating=800
        )
        
        # Beginners should get direct "Oops" style message
        assert "oops" in result["coaching_message"].lower() or "loses" in result["coaching_message"].lower(), \
            f"Expected direct message for 800 player blunder, got: {result['coaching_message']}"
        
        # Should have a simple question about hanging pieces, not Socratic questioning
        if result.get("socratic_question"):
            assert "hanging" in result["socratic_question"].lower() or "take" in result["socratic_question"].lower(), \
                f"Expected simple hanging piece question for beginner, got: {result['socratic_question']}"
    
    def test_1600_player_blunder_socratic_question(self):
        """1600-rated player with blunder gets Socratic question"""
        result = _generate_coaching_message(
            user_move="Qh4",
            quality="blunder",
            best_move="Nf3",
            tactical_analysis={},
            coach_move="Nxe5",
            understanding_context=None,
            user_name="",
            user_rating=1600
        )
        
        # Intermediate players should get Socratic questioning
        assert result.get("socratic_question") is not None, \
            f"Expected Socratic question for 1600 player blunder, got None"
        assert result.get("expects_response") == True, \
            f"Expected expects_response=True for 1600 player blunder"
        
        # Socratic question should ask about thinking/reasoning
        socratic = result["socratic_question"].lower()
        assert any(word in socratic for word in ["thinking", "why", "what", "walk", "explain"]), \
            f"Expected Socratic question to ask about reasoning, got: {result['socratic_question']}"
    
    def test_800_player_mistake_direct_not_socratic(self):
        """800-rated player with mistake gets direct explanation, not Socratic"""
        result = _generate_coaching_message(
            user_move="Bc4",
            quality="mistake",
            best_move="d4",
            tactical_analysis={},
            coach_move="e5",
            understanding_context=None,
            user_name="",
            user_rating=800
        )
        
        # Beginners should NOT get Socratic questioning for mistakes
        assert result.get("expects_response") != True, \
            f"Beginner should not get expects_response=True for mistake"
        
        # Should have encouragement
        assert result.get("encouragement") is not None, \
            f"Expected encouragement for beginner mistake"
    
    def test_1600_player_mistake_socratic(self):
        """1600-rated player with mistake gets Socratic questioning"""
        result = _generate_coaching_message(
            user_move="Bc4",
            quality="mistake",
            best_move="d4",
            tactical_analysis={},
            coach_move="e5",
            understanding_context=None,
            user_name="",
            user_rating=1600
        )
        
        # Intermediate players should get Socratic questioning
        assert result.get("socratic_question") is not None, \
            f"Expected Socratic question for 1600 player mistake"
        assert result.get("expects_response") == True, \
            f"Expected expects_response=True for 1600 player mistake"
    
    def test_excellent_move_encouragement(self):
        """Excellent moves should get encouragement regardless of rating"""
        for rating in [800, 1200, 1600, 1900]:
            result = _generate_coaching_message(
                user_move="Nf3",
                quality="excellent",
                best_move="Nf3",
                tactical_analysis={},
                coach_move="e5",
                understanding_context=None,
                user_name="",
                user_rating=rating
            )
            
            assert result.get("encouragement") is not None, \
                f"Expected encouragement for excellent move at rating {rating}"
    
    def test_good_move_no_socratic(self):
        """Good moves should not trigger Socratic questioning"""
        result = _generate_coaching_message(
            user_move="Nf3",
            quality="good",
            best_move="d4",
            tactical_analysis={},
            coach_move="e5",
            understanding_context=None,
            user_name="",
            user_rating=1600
        )
        
        assert result.get("expects_response") != True, \
            f"Good moves should not expect response"


class TestPuzzleExtractionThresholds:
    """Test rating-aware puzzle extraction thresholds"""
    
    def test_threshold_values_documented(self):
        """Verify the documented threshold values are correct in the code"""
        # These are the documented thresholds from the problem statement:
        # 800 player: min 200cp
        # 1600 player: min 100cp
        
        # We can't easily test the async function directly, but we can verify
        # the threshold logic by checking the code structure
        import inspect
        source = inspect.getsource(extract_puzzles_from_game)
        
        # Check that rating-aware thresholds are present
        assert "user_rating < 1000" in source, "Missing beginner threshold check"
        assert "min_cp_loss = 200" in source, "Missing 200cp threshold for beginners"
        assert "min_cp_loss = 100" in source, "Missing 100cp threshold for intermediate"


class TestRatingBandThresholds:
    """Test that rating bands have correct thresholds"""
    
    def test_beginner_thresholds(self):
        """Verify beginner (< 1000) thresholds are lenient"""
        # Test at 800 rating
        # Thresholds: excellent: 20, good: -30, inaccuracy: -150, mistake: -300
        
        # -30cp should be good
        assert _classify_move_quality(0, -0.30, "white", 800) == "good"
        
        # -31cp should be inaccuracy (just past good threshold)
        assert _classify_move_quality(0, -0.31, "white", 800) == "inaccuracy"
        
        # -150cp should still be inaccuracy
        assert _classify_move_quality(0, -1.50, "white", 800) == "inaccuracy"
        
        # -151cp should be mistake
        assert _classify_move_quality(0, -1.51, "white", 800) == "mistake"
        
        # -300cp should still be mistake
        assert _classify_move_quality(0, -3.00, "white", 800) == "mistake"
        
        # -301cp should be blunder
        assert _classify_move_quality(0, -3.01, "white", 800) == "blunder"
    
    def test_intermediate_thresholds(self):
        """Verify intermediate (1400-1800) thresholds are standard"""
        # Test at 1600 rating
        # Thresholds: excellent: 20, good: -10, inaccuracy: -50, mistake: -150
        
        # -10cp should be good
        assert _classify_move_quality(0, -0.10, "white", 1600) == "good"
        
        # -11cp should be inaccuracy
        assert _classify_move_quality(0, -0.11, "white", 1600) == "inaccuracy"
        
        # -50cp should still be inaccuracy
        assert _classify_move_quality(0, -0.50, "white", 1600) == "inaccuracy"
        
        # -51cp should be mistake
        assert _classify_move_quality(0, -0.51, "white", 1600) == "mistake"
        
        # -150cp should still be mistake
        assert _classify_move_quality(0, -1.50, "white", 1600) == "mistake"
        
        # -151cp should be blunder
        assert _classify_move_quality(0, -1.51, "white", 1600) == "blunder"
    
    def test_advanced_thresholds(self):
        """Verify advanced (1800+) thresholds are tight"""
        # Test at 1900 rating
        # Thresholds: excellent: 10, good: -5, inaccuracy: -30, mistake: -100
        
        # -5cp should be good
        assert _classify_move_quality(0, -0.05, "white", 1900) == "good"
        
        # -6cp should be inaccuracy
        assert _classify_move_quality(0, -0.06, "white", 1900) == "inaccuracy"
        
        # -30cp should still be inaccuracy
        assert _classify_move_quality(0, -0.30, "white", 1900) == "inaccuracy"
        
        # -31cp should be mistake
        assert _classify_move_quality(0, -0.31, "white", 1900) == "mistake"
        
        # -100cp should still be mistake
        assert _classify_move_quality(0, -1.00, "white", 1900) == "mistake"
        
        # -101cp should be blunder
        assert _classify_move_quality(0, -1.01, "white", 1900) == "blunder"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
