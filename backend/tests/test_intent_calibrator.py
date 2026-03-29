"""
Test Intent Quality Calibrator v1.1

Tests the human coach judgment calibration layer.
Key: Intent × Position Context × Timing = Quality
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.intent_quality_calibrator import (
    calibrate_intent_quality,
    calibrate_with_forcing_context,
    build_coach_sentence,
    CalibratedQuality,
    PositionPressure,
    classify_pressure,
    calculate_timing_score,
    user_eval,
)


class TestPressureClassification:
    """Test position pressure classification"""
    
    def test_winning_pressure(self):
        """Eval > +200 = winning"""
        pressure = classify_pressure(250)
        assert pressure == PositionPressure.WINNING
    
    def test_better_pressure(self):
        """Eval +80 to +200 = better"""
        pressure = classify_pressure(150)
        assert pressure == PositionPressure.BETTER
    
    def test_equal_pressure(self):
        """Eval -80 to +80 = equal"""
        pressure = classify_pressure(0)
        assert pressure == PositionPressure.EQUAL
        
        pressure = classify_pressure(50)
        assert pressure == PositionPressure.EQUAL
    
    def test_worse_pressure(self):
        """Eval -200 to -80 = worse"""
        pressure = classify_pressure(-150)
        assert pressure == PositionPressure.WORSE
    
    def test_losing_pressure(self):
        """Eval < -200 = losing"""
        pressure = classify_pressure(-300)
        assert pressure == PositionPressure.LOSING


class TestTimingScore:
    """Test timing evaluation rules"""
    
    def test_attack_while_losing_good_courage(self):
        """Attack while losing = +1 (good courage)"""
        score = calculate_timing_score("ATTACKING", PositionPressure.LOSING)
        assert score == 1
    
    def test_attack_while_winning_risky(self):
        """Attack while winning = -1 (no need to complicate)"""
        score = calculate_timing_score("ATTACKING", PositionPressure.WINNING)
        assert score == -1
    
    def test_simplify_while_winning_excellent(self):
        """Simplify while winning = +2 (good technique)"""
        score = calculate_timing_score("SIMPLIFYING", PositionPressure.WINNING)
        assert score == 2
    
    def test_simplify_while_losing_bad(self):
        """Simplify while losing = -2 (need complications)"""
        score = calculate_timing_score("SIMPLIFYING", PositionPressure.LOSING)
        assert score == -2
    
    def test_defend_while_losing_good_instinct(self):
        """Defend while losing = +1 (correct priority)"""
        score = calculate_timing_score("DEFENDING", PositionPressure.LOSING)
        assert score == 1
    
    def test_develop_in_opening_good(self):
        """Development in opening = +1"""
        score = calculate_timing_score("DEVELOPING", PositionPressure.EQUAL, "opening")
        assert score == 1


class TestUserEval:
    """Test user perspective normalization"""
    
    def test_white_perspective(self):
        """White sees positive as good"""
        assert user_eval(100, "white") == 100
        assert user_eval(-100, "white") == -100
    
    def test_black_perspective(self):
        """Black sees negative as good"""
        assert user_eval(100, "black") == -100
        assert user_eval(-100, "black") == 100


class TestCalibrateIntentQuality:
    """Test main calibration function"""
    
    def test_excellent_quality(self):
        """Low loss + good timing = excellent"""
        result = calibrate_intent_quality(
            intent_type="SIMPLIFYING",
            cp_loss=10,  # Very low loss
            eval_before=250,  # Winning
            user_color="white",
            phase="middlegame"
        )
        # base=2 + timing=2 = 4 >= 3 → excellent
        assert result.calibrated_quality == CalibratedQuality.EXCELLENT.value
    
    def test_good_quality(self):
        """Moderate loss + neutral timing = good"""
        result = calibrate_intent_quality(
            intent_type="DEFENDING",
            cp_loss=50,  # Moderate loss
            eval_before=-150,  # Worse position
            user_color="white",
            phase="middlegame"
        )
        # base=1 + timing=1 = 2 >= 1 → good
        assert result.calibrated_quality == CalibratedQuality.GOOD.value
    
    def test_premature_quality(self):
        """Higher loss + bad timing = premature"""
        result = calibrate_intent_quality(
            intent_type="ATTACKING",
            cp_loss=100,  # Some loss
            eval_before=300,  # Winning (bad time to attack)
            user_color="white",
            phase="middlegame"
        )
        # base=0 + timing=-1 = -1 → premature
        assert result.calibrated_quality == CalibratedQuality.PREMATURE.value
    
    def test_incorrect_quality(self):
        """High loss + very bad timing = incorrect"""
        result = calibrate_intent_quality(
            intent_type="SIMPLIFYING",
            cp_loss=200,  # High loss
            eval_before=-300,  # Losing (bad time to simplify)
            user_color="white",
            phase="middlegame"
        )
        # base=-1 + timing=-2 = -3 < -2 → incorrect
        assert result.calibrated_quality == CalibratedQuality.INCORRECT.value


class TestCoachSentences:
    """Test Indian coach tone sentences"""
    
    def test_attack_premature_sentence(self):
        """Premature attack should have timing-aware sentence"""
        sentence = build_coach_sentence("ATTACKING", "premature")
        assert "timing" in sentence.lower() or "ready" in sentence.lower()
    
    def test_develop_incorrect_sentence(self):
        """Incorrect development should mention forcing"""
        sentence = build_coach_sentence("DEVELOPING", "incorrect")
        assert "forcing" in sentence.lower() or "action" in sentence.lower()
    
    def test_defend_excellent_sentence(self):
        """Excellent defense should be positive"""
        sentence = build_coach_sentence("DEFENDING", "excellent")
        assert "correct" in sentence.lower() or "safety" in sentence.lower()
    
    def test_no_wrong_move_language(self):
        """Never say 'wrong move' - Indian coach tone"""
        for intent in ["ATTACKING", "DEFENDING", "DEVELOPING", "SIMPLIFYING"]:
            for quality in ["excellent", "good", "reasonable", "premature", "incorrect"]:
                sentence = build_coach_sentence(intent, quality)
                assert "wrong" not in sentence.lower()
                assert "bad move" not in sentence.lower()


class TestRecalibratedSamples:
    """Test the 3 samples with calibration"""
    
    def test_sample_1_early_queen_attack(self):
        """Sample 1: Qh5 early - should be premature"""
        result = calibrate_intent_quality(
            intent_type="ATTACKING",
            cp_loss=40,  # Slight loss
            eval_before=30,  # Equal position
            user_color="white",
            phase="opening"
        )
        
        print(f"\n=== Recalibrated Sample 1: Early Queen Attack ===")
        print(f"Intent: {result.intent_type}")
        print(f"Quality: {result.calibrated_quality}")
        print(f"Score: {result.quality_score}")
        print(f"Pressure: {result.pressure}")
        print(f"Timing Score: {result.timing_score}")
        print(f"Coach Interpretation: {result.coach_interpretation}")
        print(f"Full Sentence: {result.full_sentence}")
        print(f"Raw: {result.to_dict()}")
        
        # In equal position, attack with slight loss should be reasonable/premature
        assert result.calibrated_quality in ["reasonable", "premature", "good"]
    
    def test_sample_2_castling(self):
        """Sample 2: Castling - should be good/excellent"""
        result = calibrate_intent_quality(
            intent_type="DEFENDING",
            cp_loss=0,  # No loss (best move)
            eval_before=50,  # Slightly better
            user_color="white",
            phase="opening"
        )
        
        print(f"\n=== Recalibrated Sample 2: Castling ===")
        print(f"Quality: {result.calibrated_quality}")
        print(f"Full Sentence: {result.full_sentence}")
        print(f"Raw: {result.to_dict()}")
        
        # Castling (defending) with no loss should be good+
        assert result.calibrated_quality in ["excellent", "good"]
    
    def test_sample_3_missed_mate(self):
        """Sample 3: Nc3 instead of Qxf7# - should be incorrect"""
        result = calibrate_with_forcing_context(
            intent_type="DEVELOPING",
            cp_loss=800,  # Huge loss (missed mate)
            eval_before=9999,  # Winning (mate available)
            user_color="white",
            phase="opening",
            move_uci="b1c3",
            best_move_uci="h5f7",  # Qxf7# 
            board_fen="r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 4 4"
        )
        
        print(f"\n=== Recalibrated Sample 3: Missed Mate ===")
        print(f"Intent: {result.intent_type}")
        print(f"Quality: {result.calibrated_quality}")
        print(f"Score: {result.quality_score}")
        print(f"Full Sentence: {result.full_sentence}")
        print(f"Raw: {result.to_dict()}")
        
        # Development when mate available should be incorrect
        assert result.calibrated_quality == "incorrect"


class TestFullCoachExplanation:
    """Test generating full coach explanation"""
    
    def test_full_explanation_example(self):
        """Generate complete coach explanation combining intent + quality"""
        # Simulate: Player attacked when position required defense
        result = calibrate_intent_quality(
            intent_type="ATTACKING",
            cp_loss=150,
            eval_before=-100,  # Worse position
            user_color="white",
            phase="middlegame"
        )
        
        # Build full explanation
        intent_description = "You tried to start an attack."
        quality_context = result.full_sentence
        
        # Combine into coach-like explanation
        full_explanation = f"{intent_description} {quality_context}"
        
        print(f"\n=== Full Coach Explanation Example ===")
        print(f"Move context: Attack in worse position, 150cp loss")
        print(f"Coach says: {full_explanation}")
        print()
        
        # Before Step 6: "You had a plan here."
        # After Step 6: "You tried to start an attack. [quality-aware sentence]"
        
        assert "attack" in full_explanation.lower()
        assert len(full_explanation) > 30  # Should be substantial


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
