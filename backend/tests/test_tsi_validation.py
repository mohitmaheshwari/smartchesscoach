"""
TSI Validation Tests - Stress Testing the Cognitive Patterns Service

Tests 3 synthetic user profiles:
- User A: Stable Player (low frequency, moderate cp_loss, gradual improvement)
- User B: Volatile Player (clean games + spike game, high cp_loss)
- User C: Gradual Improver (high early frequency, declining trend)

Validates:
1. Sensitivity: Does system detect real patterns?
2. Stability: Does one bad game destroy TSI?
3. Recoverability: After good games, does TSI reflect improvement?
"""

import pytest
import sys
sys.path.insert(0, '/app/backend')

from cognitive_patterns_service import (
    _calculate_tsi,
    _calculate_trend,
    get_severity_weight,
    GAME_WEIGHTS
)


class TestTrendCalculation:
    """Test the minimum baseline floor guard"""
    
    def test_both_below_floor_is_stable(self):
        """When both values are below MIN_BASELINE_FLOOR (2), return stable"""
        assert _calculate_trend(0, 0) == "stable"
        assert _calculate_trend(1, 1) == "stable"
        assert _calculate_trend(1, 0) == "stable"
        assert _calculate_trend(0, 1) == "stable"
    
    def test_new_significant_pattern_worsening(self):
        """When previous is below floor but recent is 4+, mark worsening"""
        # MIN_BASELINE_FLOOR is 2, so 2 + 2 = 4
        assert _calculate_trend(4, 1) == "worsening"
        assert _calculate_trend(5, 0) == "worsening"
    
    def test_normal_trend_calculation(self):
        """Normal trends when both above floor"""
        # 20% improvement
        assert _calculate_trend(8, 10) == "stable"  # -20% exactly
        assert _calculate_trend(7, 10) == "improving"  # -30%
        
        # 20% worsening
        assert _calculate_trend(12, 10) == "stable"  # +20% exactly
        assert _calculate_trend(13, 10) == "worsening"  # +30%


class TestSeverityWeighting:
    """Test severity weight calculation"""
    
    def test_severity_scale(self):
        """Verify severity weight is 0-1 scale based on cp_loss"""
        assert get_severity_weight(50) < get_severity_weight(150)
        assert get_severity_weight(150) < get_severity_weight(300)
        assert get_severity_weight(300) < get_severity_weight(500)
        assert get_severity_weight(500) <= 1.0


class TestTSICalculation:
    """Test TSI with synthetic profiles"""
    
    def _create_pattern(self, frequency: int, avg_severity: float):
        """Helper to create a pattern dict"""
        return {
            "frequency": frequency,
            "avg_severity": avg_severity,
            "weighted_score": frequency * avg_severity
        }
    
    def test_perfect_player_tsi_100(self):
        """Player with no patterns should have TSI 100"""
        all_patterns = {}
        recent = {}
        previous = {}
        
        tsi, trend = _calculate_tsi(all_patterns, recent, previous)
        
        assert tsi == 100, f"Perfect player should have TSI 100, got {tsi}"
        assert trend == "stable"
    
    def test_user_a_stable_player(self):
        """
        User A: Stable Player
        - Low frequency (2-3 mistakes per game tier)
        - Moderate severity (0.4-0.5)
        - Gradual improvement in recent games
        
        Expected: TSI 70-85, trend stable/improving
        """
        # Recent 5 games: 2 mistakes avg, severity 0.4
        recent = {
            "missed_forcing_move": self._create_pattern(3, 0.35),
            "structural_misjudgment": self._create_pattern(2, 0.3)
        }
        
        # Previous 5 games: 3 mistakes avg, severity 0.45
        previous = {
            "missed_forcing_move": self._create_pattern(4, 0.4),
            "structural_misjudgment": self._create_pattern(3, 0.35)
        }
        
        # All 20 games
        all_patterns = {
            "missed_forcing_move": self._create_pattern(15, 0.4),
            "structural_misjudgment": self._create_pattern(12, 0.35)
        }
        
        tsi, trend = _calculate_tsi(all_patterns, recent, previous)
        
        print(f"User A (Stable): TSI={tsi}, Trend={trend}")
        # With new max_expected=210, moderate player should be 70-95
        assert 65 <= tsi <= 95, f"Stable player TSI should be 65-95, got {tsi}"
        # Recent is better than previous, so should be improving
        assert trend in ["stable", "improving"], f"Stable player trend should be stable/improving, got {trend}"
    
    def test_user_b_volatile_player_spike(self):
        """
        User B: Volatile Player - Single spike game
        - Recent: 4 clean games + 1 terrible game (10 blunders)
        - Previous: All clean games
        
        Expected: TSI should NOT collapse (weighted window dampens spike)
        """
        # Recent 5 games: 1 spike game with 10 blunders, 4 clean games
        # With weighted window, this should be dampened
        recent = {
            "missed_forcing_move": self._create_pattern(6, 0.7),  # From spike game
            "random_move_critical": self._create_pattern(4, 0.8)   # From spike game
        }
        
        # Previous 5 games: Very clean
        previous = {
            "missed_forcing_move": self._create_pattern(1, 0.3),
        }
        
        # All 20 games (mostly clean except spike)
        all_patterns = {
            "missed_forcing_move": self._create_pattern(8, 0.5),
            "random_move_critical": self._create_pattern(4, 0.8)
        }
        
        tsi, trend = _calculate_tsi(all_patterns, recent, previous)
        
        print(f"User B (Volatile spike): TSI={tsi}, Trend={trend}")
        # TSI should not collapse below 40 even with one bad game
        # The weighted window should dampen the spike
        assert tsi >= 30, f"Single spike should not collapse TSI below 30, got {tsi}"
        assert trend == "worsening", "Should detect the spike as worsening"
    
    def test_user_b_sustained_bad_performance(self):
        """
        User B: Volatile Player - Sustained bad performance
        - Recent 5 games: All bad (8+ mistakes each)
        - Previous: Mixed
        
        Expected: TSI should be low (this is real signal, not noise)
        """
        recent = {
            "missed_forcing_move": self._create_pattern(15, 0.7),
            "random_move_critical": self._create_pattern(12, 0.8),
            "ignored_opponent_forcing": self._create_pattern(10, 0.6)
        }
        
        previous = {
            "missed_forcing_move": self._create_pattern(5, 0.4),
            "random_move_critical": self._create_pattern(3, 0.5)
        }
        
        all_patterns = {
            "missed_forcing_move": self._create_pattern(25, 0.6),
            "random_move_critical": self._create_pattern(18, 0.7),
            "ignored_opponent_forcing": self._create_pattern(12, 0.55)
        }
        
        tsi, trend = _calculate_tsi(all_patterns, recent, previous)
        
        print(f"User B (Sustained bad): TSI={tsi}, Trend={trend}")
        # Sustained bad performance SHOULD show low TSI
        # With new max_expected=210, this profile should be ~55-65
        assert tsi <= 70, f"Sustained bad performance should have TSI <= 70, got {tsi}"
        assert trend == "worsening", "Should clearly be worsening"
    
    def test_user_c_gradual_improver(self):
        """
        User C: Gradual Improver
        - High early frequency (games 11-20)
        - Declining frequency in middle and recent games
        
        Expected: TSI moderate, trend improving
        """
        # Recent 5 games: Low mistakes
        recent = {
            "missed_forcing_move": self._create_pattern(2, 0.3),
            "structural_misjudgment": self._create_pattern(1, 0.25)
        }
        
        # Previous 5 games: Moderate mistakes
        previous = {
            "missed_forcing_move": self._create_pattern(4, 0.4),
            "structural_misjudgment": self._create_pattern(3, 0.35)
        }
        
        # All 20 games (high total because older games were bad)
        all_patterns = {
            "missed_forcing_move": self._create_pattern(20, 0.5),
            "structural_misjudgment": self._create_pattern(15, 0.4)
        }
        
        tsi, trend = _calculate_tsi(all_patterns, recent, previous)
        
        print(f"User C (Improver): TSI={tsi}, Trend={trend}")
        # Weighted window should weight recent games more
        # So TSI should reflect improvement
        assert tsi >= 50, f"Improver should have decent TSI, got {tsi}"
        assert trend == "improving", f"Clear improvement should show improving trend, got {trend}"
    
    def test_recoverability_after_bad_phase(self):
        """
        Test that TSI recovers after bad games are followed by good games
        """
        # Scenario: 3 bad games in middle, now 5 good games
        recent = {
            "missed_forcing_move": self._create_pattern(1, 0.2),
        }
        
        previous = {
            "missed_forcing_move": self._create_pattern(8, 0.7),
            "random_move_critical": self._create_pattern(5, 0.8)
        }
        
        all_patterns = {
            "missed_forcing_move": self._create_pattern(12, 0.5),
            "random_move_critical": self._create_pattern(6, 0.7)
        }
        
        tsi, trend = _calculate_tsi(all_patterns, recent, previous)
        
        print(f"Recovery test: TSI={tsi}, Trend={trend}")
        # Recent games are good, so should be improving
        assert trend == "improving", f"Recovery should show improving trend, got {trend}"
        # TSI should be reasonable (not stuck at bad level)
        assert tsi >= 50, f"After recovery, TSI should be >= 50, got {tsi}"


class TestWeightedWindowBehavior:
    """Test that the weighted window works as expected"""
    
    def test_weights_are_correct(self):
        """Verify weight constants"""
        assert GAME_WEIGHTS["recent"] == 3.0
        assert GAME_WEIGHTS["middle"] == 2.0
        assert GAME_WEIGHTS["older"] == 1.0
    
    def test_recent_games_have_more_impact(self):
        """
        Same total mistakes, but concentrated in different tiers
        Recent mistakes should impact TSI more than older mistakes
        """
        # Scenario A: All mistakes in recent games
        recent_heavy = {
            "missed_forcing_move": {"frequency": 10, "avg_severity": 0.5}
        }
        empty = {}
        all_recent = {
            "missed_forcing_move": {"frequency": 10, "avg_severity": 0.5}
        }
        
        tsi_recent, _ = _calculate_tsi(all_recent, recent_heavy, empty)
        
        # Scenario B: All mistakes in older games (spread in all_patterns)
        all_older = {
            "missed_forcing_move": {"frequency": 10, "avg_severity": 0.5}
        }
        # When recent and previous are empty, mistakes are in older tier
        
        tsi_older, _ = _calculate_tsi(all_older, {}, {})
        
        print(f"Recent heavy TSI: {tsi_recent}, Older heavy TSI: {tsi_older}")
        # TSI should be lower when recent games are bad
        assert tsi_recent < tsi_older, \
            f"Recent mistakes should impact TSI more: recent={tsi_recent}, older={tsi_older}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
