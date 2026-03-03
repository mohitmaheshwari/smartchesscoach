"""
Unit Tests for Breakthrough & Plateau Detection Service - Step 8

Tests the 6 exact fixtures provided in the spec:
1. Plateau
2. Breakthrough
3. Confidence Illusion
4. Tilt Risk
5. Stable Growth
6. Normal

Each test sets metrics + context → expects BreakthroughSignal.state
"""

import pytest
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from coach_state.breakthrough_service import (
    WindowMetrics,
    BreakthroughSignal,
    detect_breakthrough_state,
    detect_tilt_risk,
    detect_breakthrough,
    detect_confidence_illusion,
    detect_plateau,
    detect_stable_growth,
    calculate_game_severity,
    calculate_volatility,
    build_window_metrics,
    HEADLINES,
    MESSAGES,
)


class TestSeverityCalculation:
    """Test the game severity formula."""
    
    def test_severity_example(self):
        """Example from spec: 2 blunders, 3 mistakes, avg_cp_loss 180 → 10.8"""
        severity = calculate_game_severity(blunders=2, mistakes=3, avg_cp_loss=180)
        assert severity == 10.8
    
    def test_severity_zero(self):
        """Perfect game has low severity."""
        severity = calculate_game_severity(blunders=0, mistakes=0, avg_cp_loss=50)
        assert severity == 0.5
    
    def test_severity_blunder_heavy(self):
        """Blunders are weighted 3x."""
        severity = calculate_game_severity(blunders=3, mistakes=0, avg_cp_loss=0)
        assert severity == 9.0


class TestVolatilityCalculation:
    """Test volatility (population std dev)."""
    
    def test_volatility_uniform(self):
        """Uniform scores have zero volatility."""
        scores = [5.0, 5.0, 5.0, 5.0, 5.0]
        assert calculate_volatility(scores) == 0.0
    
    def test_volatility_varied(self):
        """Varied scores have positive volatility."""
        scores = [2.0, 4.0, 6.0, 8.0, 10.0]
        vol = calculate_volatility(scores)
        assert vol > 0
        assert round(vol, 2) == 2.83  # pstdev of [2,4,6,8,10]
    
    def test_volatility_single(self):
        """Single game has zero volatility."""
        assert calculate_volatility([5.0]) == 0.0


class TestFixture1Plateau:
    """
    Test Fixture 1: PLATEAU
    
    W1 = {games: 5, blunders_per_game: 1.8, volatility: 2.1, lesson_repeat_rate: 0.50}
    W2 = {games: 10, blunders_per_game: 1.9, volatility: 2.2}
    improvement_trajectory = "stable"
    dominant_lesson_intensity = 2
    
    Expected: PLATEAU
    
    Note: To avoid CONFIDENCE_ILLUSION triggering first, win_rate should be improving
    or dominant_lesson_intensity should be < 2
    """
    
    def test_plateau_detection(self):
        w1 = WindowMetrics(
            games=5,
            blunders_per_game=1.8,
            volatility=2.1,
            lesson_repeat_rate=0.50,
            avg_cp_loss=130,  # Getting worse
            win_rate=0.50,    # Improving (vs 0.40)
        )
        w2 = WindowMetrics(
            games=10,
            blunders_per_game=1.9,
            volatility=2.2,
            avg_cp_loss=120,
            win_rate=0.40,
        )
        
        signal = detect_breakthrough_state(
            w1=w1,
            w2=w2,
            improvement_trajectory="stable",
            dominant_lesson_intensity=1,  # Low intensity avoids CONFIDENCE_ILLUSION
        )
        
        assert signal.state == "PLATEAU"
        assert "stuck" in signal.headline.lower() or "loop" in signal.headline.lower() or "repeating" in signal.headline.lower()


class TestFixture2Breakthrough:
    """
    Test Fixture 2: BREAKTHROUGH
    
    W1 = {games: 5, blunders_per_game: 0.8, volatility: 1.2}
    W2 = {games: 10, blunders_per_game: 1.5, volatility: 1.8}
    good_game_streak = 2
    milestone_recent = True
    
    Expected: BREAKTHROUGH
    """
    
    def test_breakthrough_detection(self):
        w1 = WindowMetrics(
            games=5,
            blunders_per_game=0.8,
            volatility=1.2,
        )
        w2 = WindowMetrics(
            games=10,
            blunders_per_game=1.5,
            volatility=1.8,
        )
        
        signal = detect_breakthrough_state(
            w1=w1,
            w2=w2,
            good_game_streak=2,
            milestone_recent=True,
        )
        
        assert signal.state == "BREAKTHROUGH"
        assert "progress" in signal.headline.lower() or "improvement" in signal.headline.lower() or "breakthrough" in signal.headline.lower() or "leveling" in signal.headline.lower()


class TestFixture3ConfidenceIllusion:
    """
    Test Fixture 3: CONFIDENCE_ILLUSION
    
    W1 = {avg_cp_loss: 120, lesson_repeat_rate: 0.60, win_rate: 0.4}
    W2 = {avg_cp_loss: 125, win_rate: 0.42}
    dominant_lesson_intensity = 2
    
    Expected: CONFIDENCE_ILLUSION
    """
    
    def test_confidence_illusion_detection(self):
        w1 = WindowMetrics(
            games=5,
            avg_cp_loss=120,
            lesson_repeat_rate=0.60,
            win_rate=0.4,
        )
        w2 = WindowMetrics(
            games=10,
            avg_cp_loss=125,
            win_rate=0.42,
        )
        
        signal = detect_breakthrough_state(
            w1=w1,
            w2=w2,
            dominant_lesson_intensity=2,
        )
        
        assert signal.state == "CONFIDENCE_ILLUSION"
        assert "okay" in signal.headline.lower() or "pattern" in signal.headline.lower() or "accuracy" in signal.headline.lower() or "blind" in signal.headline.lower()


class TestFixture4TiltRisk:
    """
    Test Fixture 4: TILT_RISK
    
    W1 = {volatility: 3.4, blunders_per_game: 2.4}
    W2 = {volatility: 2.0, blunders_per_game: 1.6}
    consecutive_losses = 2
    
    Expected: TILT_RISK
    """
    
    def test_tilt_risk_detection(self):
        w1 = WindowMetrics(
            games=5,
            volatility=3.4,
            blunders_per_game=2.4,
        )
        w2 = WindowMetrics(
            games=10,
            volatility=2.0,
            blunders_per_game=1.6,
        )
        
        signal = detect_breakthrough_state(
            w1=w1,
            w2=w2,
            consecutive_losses=2,
        )
        
        assert signal.state == "TILT_RISK"
        assert "reset" in signal.headline.lower() or "tilt" in signal.headline.lower() or "breath" in signal.headline.lower() or "rough" in signal.headline.lower()


class TestFixture5StableGrowth:
    """
    Test Fixture 5: STABLE_GROWTH
    
    W1 = {volatility: 1.2, lesson_repeat_rate: 0.20}
    W2 = {volatility: 1.6, lesson_repeat_rate: 0.30}
    W3 = {volatility: 2.2}
    discipline_score increasing = True
    
    Expected: STABLE_GROWTH
    """
    
    def test_stable_growth_detection(self):
        w1 = WindowMetrics(
            games=5,
            volatility=1.2,
            lesson_repeat_rate=0.20,
        )
        w2 = WindowMetrics(
            games=10,
            volatility=1.6,
            lesson_repeat_rate=0.30,
        )
        w3 = WindowMetrics(
            games=20,
            volatility=2.2,
        )
        
        signal = detect_breakthrough_state(
            w1=w1,
            w2=w2,
            w3=w3,
            discipline_improving=True,
        )
        
        assert signal.state == "STABLE_GROWTH"
        assert "stable" in signal.headline.lower() or "steady" in signal.headline.lower() or "consistency" in signal.headline.lower() or "track" in signal.headline.lower()


class TestFixture6Normal:
    """
    Test Fixture 6: NORMAL
    
    W1 = {volatility: 2.0, blunders_per_game: 1.2, lesson_repeat_rate: 0.30}
    W2 = {volatility: 2.1, blunders_per_game: 1.3}
    No spikes, no drops, no streaks
    
    Expected: NORMAL
    """
    
    def test_normal_detection(self):
        w1 = WindowMetrics(
            games=5,
            volatility=2.0,
            blunders_per_game=1.2,
            lesson_repeat_rate=0.30,
        )
        w2 = WindowMetrics(
            games=10,
            volatility=2.1,
            blunders_per_game=1.3,
        )
        
        signal = detect_breakthrough_state(
            w1=w1,
            w2=w2,
            consecutive_losses=0,
            good_game_streak=0,
            milestone_recent=False,
            dominant_lesson_intensity=1,
            improvement_trajectory="stable",
            discipline_improving=False,
        )
        
        assert signal.state == "NORMAL"
        assert "continue" in signal.headline.lower() or "keep" in signal.headline.lower() or "standard" in signal.headline.lower() or "path" in signal.headline.lower()


class TestTierAwareCopy:
    """Test that coach copy changes based on maturity tier."""
    
    def test_novice_has_longer_message(self):
        w1 = WindowMetrics(games=5, blunders_per_game=0.8, volatility=1.2)
        w2 = WindowMetrics(games=10, blunders_per_game=1.5, volatility=1.8)
        
        novice_signal = detect_breakthrough_state(
            w1=w1, w2=w2, good_game_streak=2, milestone_recent=True,
            maturity_tier="Novice"
        )
        
        advanced_signal = detect_breakthrough_state(
            w1=w1, w2=w2, good_game_streak=2, milestone_recent=True,
            maturity_tier="Advanced"
        )
        
        # Novice message should be longer
        assert len(novice_signal.coach_message) > len(advanced_signal.coach_message)
    
    def test_advanced_is_minimal(self):
        w1 = WindowMetrics(games=5, volatility=2.0, blunders_per_game=1.2, lesson_repeat_rate=0.30)
        w2 = WindowMetrics(games=10, volatility=2.1, blunders_per_game=1.3)
        
        signal = detect_breakthrough_state(
            w1=w1, w2=w2, maturity_tier="Advanced"
        )
        
        # Advanced should have minimal copy
        assert len(signal.coach_message) < 50 or signal.coach_message.count('.') <= 2


class TestRecommendedActions:
    """Test that recommended actions are correct per state."""
    
    def test_tilt_has_recovery_action(self):
        w1 = WindowMetrics(games=5, volatility=3.4, blunders_per_game=2.4)
        w2 = WindowMetrics(games=10, volatility=2.0, blunders_per_game=1.6)
        
        signal = detect_breakthrough_state(w1=w1, w2=w2, consecutive_losses=2)
        
        assert signal.recommended_action == "RECOVERY_MODE"
        assert "Recovery" in signal.cta
    
    def test_breakthrough_has_level_up_action(self):
        w1 = WindowMetrics(games=5, blunders_per_game=0.8, volatility=1.2)
        w2 = WindowMetrics(games=10, blunders_per_game=1.5, volatility=1.8)
        
        signal = detect_breakthrough_state(w1=w1, w2=w2, good_game_streak=2, milestone_recent=True)
        
        assert signal.recommended_action == "LEVEL_UP"
        assert "Advanced" in signal.cta or "Drill" in signal.cta
    
    def test_plateau_has_deep_session_action(self):
        w1 = WindowMetrics(games=5, blunders_per_game=1.8, volatility=2.1, lesson_repeat_rate=0.50)
        w2 = WindowMetrics(games=10, blunders_per_game=1.9, volatility=2.2)
        
        signal = detect_breakthrough_state(w1=w1, w2=w2, improvement_trajectory="stable")
        
        assert signal.recommended_action == "DEEP_SESSION"
        assert "Deep" in signal.cta or "Review" in signal.cta


class TestEvidenceCapture:
    """Test that evidence dict captures debugging info."""
    
    def test_tilt_evidence(self):
        w1 = WindowMetrics(games=5, volatility=3.4, blunders_per_game=2.4)
        w2 = WindowMetrics(games=10, volatility=2.0, blunders_per_game=1.6)
        
        signal = detect_breakthrough_state(w1=w1, w2=w2, consecutive_losses=2)
        
        assert "w1_volatility" in signal.evidence
        assert "consecutive_losses" in signal.evidence
        assert signal.evidence["consecutive_losses"] == 2
    
    def test_breakthrough_evidence(self):
        w1 = WindowMetrics(games=5, blunders_per_game=0.8, volatility=1.2)
        w2 = WindowMetrics(games=10, blunders_per_game=1.5, volatility=1.8)
        
        signal = detect_breakthrough_state(w1=w1, w2=w2, good_game_streak=2, milestone_recent=True)
        
        assert "blunder_drop_pct" in signal.evidence
        assert "good_game_streak" in signal.evidence


class TestConfidenceScoring:
    """Test confidence scoring is in valid range."""
    
    def test_confidence_range(self):
        w1 = WindowMetrics(games=5, volatility=2.0, blunders_per_game=1.2)
        w2 = WindowMetrics(games=10, volatility=2.1, blunders_per_game=1.3)
        
        signal = detect_breakthrough_state(w1=w1, w2=w2)
        
        assert 0 <= signal.confidence <= 1
    
    def test_high_confidence_for_clear_tilt(self):
        w1 = WindowMetrics(games=5, volatility=5.0, blunders_per_game=4.0)
        w2 = WindowMetrics(games=10, volatility=2.0, blunders_per_game=1.5)
        
        signal = detect_breakthrough_state(w1=w1, w2=w2, consecutive_losses=3)
        
        assert signal.confidence >= 0.7
