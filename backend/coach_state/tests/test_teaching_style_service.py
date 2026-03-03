"""
Unit Tests for Teaching Style Service - Step 7

Tests:
- Tier defaults are correctly applied
- Strictness switch works as specified
- Component lists are correct per strategy
- Palette rotation is deterministic
- Sentence limits are enforced
"""

import pytest
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from coach_state.teaching_style_service import (
    StyleDirective,
    get_style_directive,
    adjust_for_trend,
    get_component_list,
    should_include_component,
    enforce_sentence_limit,
    maturity_to_tier,
    detect_trend,
    get_palette_id,
    get_palette_phrase,
    TIER_DEFAULTS,
    STRATEGY_COMPONENTS,
)


class TestTierDefaults:
    """Test that tier defaults match the spec exactly."""
    
    def test_novice_defaults(self):
        style = get_style_directive("Novice", "PATTERN_COACHING")
        
        assert style.max_sentences == 5
        assert style.include_intent is True
        assert style.include_consequence is True
        assert style.include_rule is True
        assert style.include_encouragement is True
        assert style.include_example_cue is True
        assert style.firmness == "soft"
        assert style.reduce_fluff is False
    
    def test_developing_defaults(self):
        style = get_style_directive("Developing", "PATTERN_COACHING")
        
        assert style.max_sentences == 4
        assert style.include_intent is True
        assert style.include_consequence is True
        assert style.include_rule is True
        assert style.include_encouragement is False
        assert style.include_example_cue is True
        assert style.firmness == "neutral"
        assert style.reduce_fluff is True
    
    def test_disciplined_defaults(self):
        style = get_style_directive("Disciplined", "PATTERN_COACHING")
        
        assert style.max_sentences == 3
        assert style.include_intent is True
        assert style.include_consequence is True
        assert style.include_rule is True
        assert style.include_encouragement is False
        assert style.include_example_cue is False
        assert style.firmness == "firm"
        assert style.reduce_fluff is True
    
    def test_advanced_defaults(self):
        style = get_style_directive("Advanced", "PATTERN_COACHING")
        
        assert style.max_sentences == 2
        assert style.include_intent is False  # Skip intent for Advanced
        assert style.include_consequence is True
        assert style.include_rule is True
        assert style.include_encouragement is False
        assert style.include_example_cue is False
        assert style.firmness == "firm"
        assert style.reduce_fluff is True


class TestStrictnessSwitch:
    """Test the dynamic strictness adjustment."""
    
    def test_declining_with_repeated_lesson_becomes_firm(self):
        """When declining + repeated lesson → firmer tone."""
        style = get_style_directive("Developing", "PATTERN_COACHING")
        
        # Initially neutral firmness
        assert style.firmness == "neutral"
        assert style.include_encouragement is False
        
        # Apply strictness switch
        adjusted = adjust_for_trend(style, "declining", lesson_repeated=True)
        
        assert adjusted.firmness == "firm"
        assert adjusted.include_encouragement is False
        assert adjusted.reduce_fluff is True
    
    def test_declining_without_repeated_lesson_no_change(self):
        """Declining alone doesn't trigger firm override."""
        style = get_style_directive("Developing", "PATTERN_COACHING")
        adjusted = adjust_for_trend(style, "declining", lesson_repeated=False)
        
        # Should remain unchanged
        assert adjusted.firmness == "neutral"
    
    def test_improving_adds_encouragement_for_developing(self):
        """Improving trend adds encouragement for Developing tier."""
        style = get_style_directive("Developing", "PATTERN_COACHING")
        
        assert style.include_encouragement is False
        
        adjusted = adjust_for_trend(style, "improving", lesson_repeated=False)
        
        assert adjusted.include_encouragement is True
    
    def test_improving_adds_encouragement_for_novice(self):
        """Improving trend keeps encouragement for Novice."""
        style = get_style_directive("Novice", "PATTERN_COACHING")
        
        assert style.include_encouragement is True
        
        adjusted = adjust_for_trend(style, "improving", lesson_repeated=False)
        
        assert adjusted.include_encouragement is True
    
    def test_improving_no_encouragement_for_advanced(self):
        """Improving doesn't add encouragement for Advanced tier."""
        style = get_style_directive("Advanced", "PATTERN_COACHING")
        
        assert style.include_encouragement is False
        
        adjusted = adjust_for_trend(style, "improving", lesson_repeated=False)
        
        # Advanced should NOT get encouragement even when improving
        assert adjusted.include_encouragement is False
    
    def test_stable_trend_no_change(self):
        """Stable trend doesn't modify style."""
        style = get_style_directive("Developing", "PATTERN_COACHING")
        adjusted = adjust_for_trend(style, "stable", lesson_repeated=False)
        
        assert adjusted == style


class TestStrategyComponents:
    """Test component lists per strategy per tier."""
    
    def test_pattern_coaching_novice(self):
        components = get_component_list("PATTERN_COACHING", "Novice")
        assert components == ["intent", "consequence", "pattern_reminder", "rule", "encouragement"]
    
    def test_pattern_coaching_disciplined(self):
        components = get_component_list("PATTERN_COACHING", "Disciplined")
        assert components == ["intent", "consequence", "rule"]
    
    def test_pattern_coaching_advanced(self):
        components = get_component_list("PATTERN_COACHING", "Advanced")
        assert components == ["consequence", "rule"]
        assert "intent" not in components  # Advanced skips intent
    
    def test_tactical_coaching_novice(self):
        components = get_component_list("TACTICAL_COACHING", "Novice")
        assert "break_point" in components
        assert "encouragement" in components
    
    def test_tactical_coaching_advanced(self):
        components = get_component_list("TACTICAL_COACHING", "Advanced")
        assert components == ["consequence", "rule"]
    
    def test_turning_point_coaching_novice(self):
        components = get_component_list("TURNING_POINT_COACHING", "Novice")
        assert "what_changed" in components
        assert "why_it_mattered" in components
    
    def test_positive_coaching_advanced(self):
        """Positive coaching for Advanced has minimal output."""
        components = get_component_list("POSITIVE_COACHING", "Advanced")
        assert components == ["what_went_right"]
        assert "rule" not in components  # No rule needed for positive


class TestComponentInclusion:
    """Test should_include_component logic."""
    
    def test_intent_respects_directive(self):
        style_with = get_style_directive("Novice", "PATTERN_COACHING")
        style_without = get_style_directive("Advanced", "PATTERN_COACHING")
        
        assert should_include_component("intent", style_with) is True
        assert should_include_component("intent", style_without) is False
    
    def test_encouragement_respects_directive(self):
        novice = get_style_directive("Novice", "PATTERN_COACHING")
        disciplined = get_style_directive("Disciplined", "PATTERN_COACHING")
        
        assert should_include_component("encouragement", novice) is True
        assert should_include_component("encouragement", disciplined) is False


class TestSentenceLimit:
    """Test hard sentence cap enforcement."""
    
    def test_enforces_limit(self):
        lines = ["Line 1", "Line 2", "Line 3", "Line 4", "Line 5", "Line 6"]
        
        result = enforce_sentence_limit(lines, max_sentences=3)
        
        assert len(result) == 3
        assert result == ["Line 1", "Line 2", "Line 3"]
    
    def test_shorter_list_unchanged(self):
        lines = ["Line 1", "Line 2"]
        
        result = enforce_sentence_limit(lines, max_sentences=5)
        
        assert result == lines
    
    def test_empty_list(self):
        result = enforce_sentence_limit([], max_sentences=3)
        assert result == []


class TestPaletteRotation:
    """Test deterministic palette selection."""
    
    def test_same_input_same_palette(self):
        """Same game_id + lesson_key always gets same palette."""
        palette1 = get_palette_id("game_123", "MISSED_TACTIC")
        palette2 = get_palette_id("game_123", "MISSED_TACTIC")
        
        assert palette1 == palette2
    
    def test_different_inputs_may_differ(self):
        """Different inputs may get different palettes."""
        palette1 = get_palette_id("game_123", "MISSED_TACTIC")
        palette2 = get_palette_id("game_456", "MISSED_TACTIC")
        
        # They might be same or different, but should be deterministic
        assert isinstance(palette1, str)
        assert isinstance(palette2, str)
    
    def test_get_palette_phrase(self):
        """Can retrieve phrases from palette."""
        phrase = get_palette_phrase("neutral_1", "encouragement", 0)
        assert phrase == "Keep building this habit."
        
        phrase2 = get_palette_phrase("neutral_1", "encouragement", 1)
        assert phrase2 == "This will pay off over time."


class TestMaturityConversion:
    """Test maturity level string conversion."""
    
    def test_novice_variants(self):
        assert maturity_to_tier("novice") == "Novice"
        assert maturity_to_tier("Novice") == "Novice"
        assert maturity_to_tier("beginner") == "Novice"
    
    def test_developing_variants(self):
        assert maturity_to_tier("developing") == "Developing"
        assert maturity_to_tier("intermediate") == "Developing"
    
    def test_disciplined_variants(self):
        assert maturity_to_tier("disciplined") == "Disciplined"
        assert maturity_to_tier("consistent") == "Disciplined"
    
    def test_advanced_variants(self):
        assert maturity_to_tier("advanced") == "Advanced"
        assert maturity_to_tier("expert") == "Advanced"
    
    def test_unknown_defaults_to_developing(self):
        assert maturity_to_tier("unknown") == "Developing"
        assert maturity_to_tier("") == "Developing"


class TestTrendDetection:
    """Test performance trend detection."""
    
    def test_improving_trend(self):
        # Recent games getting better
        accuracies = [60.0, 65.0, 70.0, 75.0, 80.0]
        assert detect_trend(accuracies) == "improving"
    
    def test_declining_trend(self):
        # Recent games getting worse
        accuracies = [80.0, 75.0, 70.0, 65.0, 60.0]
        assert detect_trend(accuracies) == "declining"
    
    def test_stable_trend(self):
        # Consistent performance
        accuracies = [70.0, 71.0, 69.0, 70.0, 70.0]
        assert detect_trend(accuracies) == "stable"
    
    def test_too_few_games(self):
        # Not enough data defaults to stable
        assert detect_trend([70.0]) == "stable"
        assert detect_trend([70.0, 71.0]) == "stable"


class TestCrossTierOutput:
    """
    Test that same strategy produces different outputs per tier.
    This is the core acceptance criteria for Step 7.
    """
    
    def test_sentence_limits_differ_by_tier(self):
        """Different tiers have different max_sentences."""
        novice = get_style_directive("Novice", "PATTERN_COACHING")
        developing = get_style_directive("Developing", "PATTERN_COACHING")
        disciplined = get_style_directive("Disciplined", "PATTERN_COACHING")
        advanced = get_style_directive("Advanced", "PATTERN_COACHING")
        
        assert novice.max_sentences == 5
        assert developing.max_sentences == 4
        assert disciplined.max_sentences == 3
        assert advanced.max_sentences == 2
    
    def test_component_count_differs_by_tier(self):
        """Higher tiers have fewer components."""
        novice_comp = get_component_list("PATTERN_COACHING", "Novice")
        advanced_comp = get_component_list("PATTERN_COACHING", "Advanced")
        
        assert len(novice_comp) > len(advanced_comp)
        assert len(novice_comp) == 5  # intent, consequence, pattern, rule, encouragement
        assert len(advanced_comp) == 2  # consequence, rule only
    
    def test_firmness_differs_by_tier(self):
        """Higher tiers are firmer."""
        novice = get_style_directive("Novice", "PATTERN_COACHING")
        disciplined = get_style_directive("Disciplined", "PATTERN_COACHING")
        
        assert novice.firmness == "soft"
        assert disciplined.firmness == "firm"
