"""
Test Lesson Resolver - Deterministic Lesson Resolution

Key test requirements:
1. Same cognitive_gap + selection_reason → same lesson_key (deterministic)
2. lesson_key is NEVER None/empty for corrective strategies
3. Positive coaching → "positive_stability" explicitly
4. lesson_intensity is 0.0-1.0

This test ensures the memory layer will have stable identifiers.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lesson_resolver import (
    resolve,
    LessonResolution,
    LessonCategory,
    get_lesson_cooldown,
    get_lesson_description,
    validate_lesson_key,
    get_all_lesson_keys
)


class TestLessonResolverDeterminism:
    """Test that lesson resolution is deterministic"""
    
    def test_same_input_same_output(self):
        """Same cognitive_gap + selection_reason → same lesson_key"""
        # Run resolve multiple times with same inputs
        results = []
        for _ in range(5):
            result = resolve(
                cognitive_gap="THREAT_BLINDNESS",
                selection_reason="pattern_event"
            )
            results.append(result.lesson_key)
        
        # All results should be identical
        assert len(set(results)) == 1, "Lesson key should be deterministic"
        assert results[0] == "verify_opponent_threats"
    
    def test_case_insensitive_gap(self):
        """cognitive_gap should be case-insensitive"""
        result_upper = resolve("THREAT_BLINDNESS", "pattern_event")
        result_lower = resolve("threat_blindness", "pattern_event")
        result_mixed = resolve("Threat_Blindness", "pattern_event")
        
        assert result_upper.lesson_key == result_lower.lesson_key
        assert result_lower.lesson_key == result_mixed.lesson_key
    
    def test_different_wording_same_gap_same_key(self):
        """Different narrative wording but same gap → same key"""
        # Both inputs have same cognitive_gap and reason
        # Narrative text doesn't matter - only gap + reason
        result1 = resolve("TACTICAL_OVERSIGHT", "tactical_error")
        result2 = resolve("TACTICAL_OVERSIGHT", "tactical_error")
        
        assert result1.lesson_key == result2.lesson_key
        assert result1.lesson_category == result2.lesson_category


class TestLessonResolverNonNullable:
    """Test that lesson_key is never null for corrective strategies"""
    
    def test_unknown_gap_gets_fallback(self):
        """Unknown cognitive_gap should get fallback lesson"""
        result = resolve(
            cognitive_gap="UNKNOWN_GAP_TYPE",
            selection_reason="tactical_error"
        )
        
        assert result.lesson_key != ""
        assert result.lesson_key is not None
        assert validate_lesson_key(result.lesson_key)
    
    def test_none_gap_gets_lesson(self):
        """None cognitive_gap should still get lesson"""
        result = resolve(
            cognitive_gap=None,
            selection_reason="turning_point"
        )
        
        assert result.lesson_key != ""
        assert result.lesson_key is not None
    
    def test_empty_gap_gets_lesson(self):
        """Empty string cognitive_gap should still get lesson"""
        result = resolve(
            cognitive_gap="",
            selection_reason="tactical_error"
        )
        
        assert result.lesson_key != ""
        assert result.lesson_key is not None
    
    def test_unknown_reason_gets_fallback(self):
        """Unknown selection_reason should get fallback"""
        result = resolve(
            cognitive_gap="THREAT_BLINDNESS",
            selection_reason="unknown_reason_xyz"
        )
        
        assert result.lesson_key != ""
        assert result.lesson_key is not None


class TestPositiveCoaching:
    """Test positive coaching scenarios"""
    
    def test_positive_game_explicit_key(self):
        """Positive coaching should explicitly return positive_stability"""
        result = resolve(
            cognitive_gap=None,
            selection_reason="positive_coaching",
            is_positive_game=True
        )
        
        assert result.lesson_key == "positive_stability"
        assert result.lesson_category == LessonCategory.DISCIPLINE.value
    
    def test_no_critical_moves_is_positive(self):
        """No critical moves should be treated as positive"""
        result = resolve(
            cognitive_gap=None,
            selection_reason="no_critical_moves"
        )
        
        assert result.lesson_key == "positive_stability"
    
    def test_positive_has_low_intensity(self):
        """Positive coaching should have low intensity"""
        result = resolve(
            cognitive_gap=None,
            selection_reason="positive_coaching",
            is_positive_game=True
        )
        
        assert result.lesson_intensity <= 0.4
    
    def test_is_positive_flag_overrides_gap(self):
        """is_positive_game=True should override any gap"""
        result = resolve(
            cognitive_gap="THREAT_BLINDNESS",
            selection_reason="pattern_event",
            is_positive_game=True
        )
        
        assert result.lesson_key == "positive_stability"


class TestLessonIntensity:
    """Test lesson_intensity calculations"""
    
    def test_intensity_in_range(self):
        """lesson_intensity should be 0.0-1.0"""
        test_cases = [
            ("THREAT_BLINDNESS", "pattern_event"),
            ("TACTICAL_OVERSIGHT", "tactical_error"),
            (None, "missed_mate"),
            ("PREMATURE_ACTION", "turning_point"),
        ]
        
        for gap, reason in test_cases:
            result = resolve(gap, reason)
            assert 0.0 <= result.lesson_intensity <= 1.0, f"Intensity out of range for {gap}/{reason}"
    
    def test_high_crs_increases_intensity(self):
        """Higher CRS should increase intensity"""
        result_low_crs = resolve("THREAT_BLINDNESS", "tactical_error", crs_score=50)
        result_high_crs = resolve("THREAT_BLINDNESS", "tactical_error", crs_score=300)
        
        assert result_high_crs.lesson_intensity >= result_low_crs.lesson_intensity
    
    def test_missed_mate_high_intensity(self):
        """Missed mate should have high intensity"""
        result = resolve(None, "missed_mate")
        
        assert result.lesson_intensity >= 0.8


class TestLessonCategories:
    """Test lesson category assignments"""
    
    def test_threat_awareness_category(self):
        """Threat-related gaps should be threat_awareness"""
        result = resolve("THREAT_BLINDNESS", "tactical_error")
        assert result.lesson_category == "threat_awareness"
    
    def test_calculation_category(self):
        """Calculation gaps should be calculation category"""
        result = resolve("TACTICAL_OVERSIGHT", "tactical_error")
        assert result.lesson_category == "calculation"
    
    def test_conversion_category(self):
        """Premature action when ahead should be conversion"""
        result = resolve("PREMATURE_ACTION", "turning_point")
        assert result.lesson_category == "conversion"
    
    def test_discipline_category_for_positive(self):
        """Positive coaching should be discipline category"""
        result = resolve(None, "positive_coaching")
        assert result.lesson_category == "discipline"


class TestLessonMetadata:
    """Test lesson metadata functions"""
    
    def test_cooldown_returns_int(self):
        """get_lesson_cooldown should return int"""
        cooldown = get_lesson_cooldown("verify_opponent_threats")
        assert isinstance(cooldown, int)
        assert cooldown > 0
    
    def test_description_returns_string(self):
        """get_lesson_description should return string"""
        desc = get_lesson_description("verify_opponent_threats")
        assert isinstance(desc, str)
        assert len(desc) > 0
    
    def test_validate_known_key(self):
        """Known lesson keys should validate"""
        assert validate_lesson_key("verify_opponent_threats")
        assert validate_lesson_key("positive_stability")
    
    def test_validate_unknown_key(self):
        """Unknown lesson keys should not validate"""
        assert not validate_lesson_key("unknown_key_xyz")
    
    def test_all_lesson_keys_non_empty(self):
        """get_all_lesson_keys should return non-empty list"""
        keys = get_all_lesson_keys()
        assert len(keys) > 0
        for key in keys:
            assert validate_lesson_key(key)


class TestLessonResolutionObject:
    """Test LessonResolution dataclass"""
    
    def test_to_dict(self):
        """LessonResolution.to_dict should return proper dict"""
        result = resolve("THREAT_BLINDNESS", "pattern_event")
        d = result.to_dict()
        
        assert "lesson_key" in d
        assert "lesson_category" in d
        assert "lesson_intensity" in d
        assert "description" in d
        assert "cooldown_games" in d
    
    def test_resolution_is_immutable(self):
        """LessonResolution should be immutable (frozen)"""
        result = resolve("THREAT_BLINDNESS", "pattern_event")
        
        # Attempting to modify should raise error
        with pytest.raises(Exception):  # FrozenInstanceError
            result.lesson_key = "different_key"


class TestAllCognitiveGaps:
    """Test all known cognitive gaps produce valid lessons"""
    
    COGNITIVE_GAPS = [
        "THREAT_BLINDNESS",
        "TACTICAL_OVERSIGHT",
        "CALCULATION_DEPTH",
        "HANGING_PIECE_BLINDNESS",
        "POSITIONAL_MISREAD",
        "PREMATURE_ACTION",
        "DEFENSIVE_LAPSE",
    ]
    
    SELECTION_REASONS = [
        "pattern_event",
        "tactical_error",
        "turning_point",
        "missed_mate",
        "advantage_squander",
    ]
    
    def test_all_gaps_all_reasons(self):
        """All gap/reason combinations should produce valid lessons"""
        for gap in self.COGNITIVE_GAPS:
            for reason in self.SELECTION_REASONS:
                result = resolve(gap, reason)
                
                assert result.lesson_key != "", f"Empty key for {gap}/{reason}"
                assert result.lesson_category != "", f"Empty category for {gap}/{reason}"
                assert 0.0 <= result.lesson_intensity <= 1.0, f"Bad intensity for {gap}/{reason}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
