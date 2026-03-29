"""
Test Memory-Aware Narrative Modifications

Tests the 4 controlled memory modifications:
1. Lesson cooldown phrasing
2. Pattern trend phrasing
3. Milestone acknowledgment
4. Theme evolution phrasing

Also tests guardrails:
- Max 2 modifications per explanation
- Memory influences PHRASING only
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from coach_narrative_engine import (
    apply_memory_modifications,
    NarrativeComponents,
    COOLDOWN_RULE_MODIFICATIONS,
    PATTERN_TREND_MODIFIERS,
    MILESTONE_CELEBRATIONS,
    THEME_EVOLUTION_PHRASES
)


def create_base_components():
    """Create base narrative components for testing"""
    return NarrativeComponents(
        intent_mirror_line="You wanted to attack.",
        thinking_break_line="But you didn't check their threats first.",
        position_consequence_line="After Qxh7, Kf8 the attack stops.",
        teaching_line="Attacks work only after threats are verified.",
        rule_line="Before committing, scan checks-captures-threats.",
        theme_reinforcement_line="This connects to threat verification."
    )


class TestCooldownModification:
    """Test lesson cooldown phrasing"""
    
    def test_cooldown_modifies_rule_line(self):
        """When lesson is on cooldown, rule line changes"""
        components = create_base_components()
        original_rule = components.rule_line
        
        memory_context = {
            "is_lesson_on_cooldown": True,
            "games_until_cooldown_expires": 2,
            "lesson_trend": "stable"
        }
        
        modified, count = apply_memory_modifications(
            components, memory_context, games_on_theme=10, active_theme="ThreatVerification"
        )
        
        assert modified.rule_line != original_rule
        assert modified.rule_line in COOLDOWN_RULE_MODIFICATIONS
        assert count >= 1
    
    def test_no_cooldown_keeps_rule_line(self):
        """When no cooldown, rule line unchanged"""
        components = create_base_components()
        original_rule = components.rule_line
        
        memory_context = {
            "is_lesson_on_cooldown": False,
            "lesson_trend": "stable"
        }
        
        modified, count = apply_memory_modifications(
            components, memory_context, games_on_theme=10
        )
        
        # Rule might still change due to theme evolution, but not cooldown
        # Test that if no other modifications apply, rule is unchanged
        memory_context_minimal = {
            "is_lesson_on_cooldown": False,
            "lesson_trend": "stable"
        }
        
        modified, count = apply_memory_modifications(
            components, memory_context_minimal, games_on_theme=0
        )
        
        # With no cooldown, stable trend, and 0 games on theme (early), 
        # the only modification would be theme evolution
        # But since active_theme is None, no modification
        modified, count = apply_memory_modifications(
            components, memory_context_minimal, games_on_theme=0, active_theme=None
        )
        
        assert modified.rule_line == original_rule


class TestPatternTrendModification:
    """Test pattern trend phrasing"""
    
    def test_improving_trend_modifies_teaching(self):
        """Improving trend adds modifier to teaching line"""
        components = create_base_components()
        original_teaching = components.teaching_line
        
        memory_context = {
            "is_lesson_on_cooldown": False,
            "lesson_trend": "improving"
        }
        
        modified, count = apply_memory_modifications(
            components, memory_context, games_on_theme=0, active_theme=None
        )
        
        # Teaching line should have trend modifier prepended
        assert modified.teaching_line != original_teaching
        assert any(mod in modified.teaching_line for mod in PATTERN_TREND_MODIFIERS["improving"])
        assert original_teaching in modified.teaching_line
    
    def test_persistent_trend_modifies_teaching(self):
        """Persistent trend adds warning to teaching line"""
        components = create_base_components()
        
        memory_context = {
            "is_lesson_on_cooldown": False,
            "lesson_trend": "persistent"
        }
        
        modified, count = apply_memory_modifications(
            components, memory_context, games_on_theme=0, active_theme=None
        )
        
        assert any(mod in modified.teaching_line for mod in PATTERN_TREND_MODIFIERS["persistent"])
    
    def test_recurring_trend_modifies_teaching(self):
        """Recurring trend adds stronger warning to teaching line"""
        components = create_base_components()
        
        memory_context = {
            "is_lesson_on_cooldown": False,
            "lesson_trend": "recurring"
        }
        
        modified, count = apply_memory_modifications(
            components, memory_context, games_on_theme=0, active_theme=None
        )
        
        assert any(mod in modified.teaching_line for mod in PATTERN_TREND_MODIFIERS["recurring"])
    
    def test_stable_trend_no_modification(self):
        """Stable trend doesn't modify teaching line for trend"""
        components = create_base_components()
        original_teaching = components.teaching_line
        
        memory_context = {
            "is_lesson_on_cooldown": False,
            "lesson_trend": "stable"
        }
        
        modified, count = apply_memory_modifications(
            components, memory_context, games_on_theme=0, active_theme=None
        )
        
        # With stable trend and no other triggers, teaching should be unchanged
        assert modified.teaching_line == original_teaching


class TestMilestoneAcknowledgment:
    """Test milestone acknowledgment"""
    
    def test_first_clean_game_milestone(self):
        """First clean game milestone adds celebration"""
        components = create_base_components()
        
        memory_context = {
            "is_lesson_on_cooldown": False,
            "lesson_trend": "stable",
            "active_milestone": "first_clean_game"
        }
        
        modified, count = apply_memory_modifications(
            components, memory_context, games_on_theme=0, active_theme=None
        )
        
        # Teaching line should include milestone celebration
        assert any(cel in modified.teaching_line for cel in MILESTONE_CELEBRATIONS["first_clean_game"])
    
    def test_three_streak_milestone(self):
        """Three-streak milestone adds celebration"""
        components = create_base_components()
        
        memory_context = {
            "is_lesson_on_cooldown": False,
            "lesson_trend": "stable",
            "active_milestone": "first_three_streak"
        }
        
        modified, count = apply_memory_modifications(
            components, memory_context, games_on_theme=0, active_theme=None
        )
        
        assert any(cel in modified.teaching_line for cel in MILESTONE_CELEBRATIONS["first_three_streak"])
    
    def test_no_milestone_no_celebration(self):
        """No milestone means no celebration added"""
        components = create_base_components()
        original_teaching = components.teaching_line
        
        memory_context = {
            "is_lesson_on_cooldown": False,
            "lesson_trend": "stable",
            "active_milestone": None
        }
        
        modified, count = apply_memory_modifications(
            components, memory_context, games_on_theme=0, active_theme=None
        )
        
        # With no modifications triggered, teaching should be unchanged
        assert modified.teaching_line == original_teaching


class TestThemeEvolutionPhrasing:
    """Test theme evolution phrasing"""
    
    def test_early_theme_phrasing(self):
        """Early in theme uses 'focusing on' language"""
        components = create_base_components()
        
        memory_context = {
            "is_lesson_on_cooldown": False,
            "lesson_trend": "stable"
        }
        
        modified, count = apply_memory_modifications(
            components, memory_context, games_on_theme=3, active_theme="ThreatVerification"
        )
        
        # Should use "We're focusing on" language
        assert "focusing on" in modified.theme_reinforcement_line.lower()
    
    def test_mid_theme_phrasing(self):
        """Mid-way through theme uses 'been working on' language"""
        components = create_base_components()
        
        memory_context = {
            "is_lesson_on_cooldown": False,
            "lesson_trend": "stable"
        }
        
        modified, count = apply_memory_modifications(
            components, memory_context, games_on_theme=10, active_theme="ThreatVerification"
        )
        
        assert "been working on" in modified.theme_reinforcement_line.lower()
    
    def test_late_theme_phrasing(self):
        """Late in theme uses 'becoming natural' language"""
        components = create_base_components()
        
        memory_context = {
            "is_lesson_on_cooldown": False,
            "lesson_trend": "stable"
        }
        
        modified, count = apply_memory_modifications(
            components, memory_context, games_on_theme=20, active_theme="ThreatVerification"
        )
        
        assert "becoming more natural" in modified.theme_reinforcement_line.lower()
    
    def test_mastery_theme_phrasing(self):
        """Mastery level uses 'instinctively' language"""
        components = create_base_components()
        
        memory_context = {
            "is_lesson_on_cooldown": False,
            "lesson_trend": "stable"
        }
        
        modified, count = apply_memory_modifications(
            components, memory_context, games_on_theme=35, active_theme="ThreatVerification"
        )
        
        assert "instinctively" in modified.theme_reinforcement_line.lower()


class TestGuardrails:
    """Test guardrails on memory modifications"""
    
    def test_max_two_modifications(self):
        """At most 2 memory modifications applied"""
        components = create_base_components()
        
        # Trigger all possible modifications
        memory_context = {
            "is_lesson_on_cooldown": True,              # Trigger 1
            "games_until_cooldown_expires": 2,
            "lesson_trend": "recurring",               # Trigger 2
            "active_milestone": "first_clean_game"     # Would be trigger 3
        }
        
        modified, count = apply_memory_modifications(
            components, memory_context, games_on_theme=10, active_theme="ThreatVerification"
        )
        
        # Should cap at 2
        assert count <= 2
    
    def test_no_modifications_with_empty_context(self):
        """No modifications when context is empty"""
        components = create_base_components()
        
        modified, count = apply_memory_modifications(
            components, None, games_on_theme=0, active_theme=None
        )
        
        assert count == 0
        assert modified.rule_line == components.rule_line
        assert modified.teaching_line == components.teaching_line
    
    def test_intent_line_never_modified(self):
        """Intent line is never modified by memory"""
        components = create_base_components()
        original_intent = components.intent_mirror_line
        
        memory_context = {
            "is_lesson_on_cooldown": True,
            "lesson_trend": "recurring",
            "active_milestone": "first_clean_game"
        }
        
        modified, count = apply_memory_modifications(
            components, memory_context, games_on_theme=10, active_theme="ThreatVerification"
        )
        
        # Intent should ALWAYS be unchanged
        assert modified.intent_mirror_line == original_intent
    
    def test_break_line_never_modified(self):
        """Break line is never modified by memory"""
        components = create_base_components()
        original_break = components.thinking_break_line
        
        memory_context = {
            "is_lesson_on_cooldown": True,
            "lesson_trend": "recurring",
            "active_milestone": "first_clean_game"
        }
        
        modified, count = apply_memory_modifications(
            components, memory_context, games_on_theme=10, active_theme="ThreatVerification"
        )
        
        # Break should ALWAYS be unchanged
        assert modified.thinking_break_line == original_break
    
    def test_consequence_line_never_modified(self):
        """Consequence line is never modified by memory"""
        components = create_base_components()
        original_consequence = components.position_consequence_line
        
        memory_context = {
            "is_lesson_on_cooldown": True,
            "lesson_trend": "recurring",
            "active_milestone": "first_clean_game"
        }
        
        modified, count = apply_memory_modifications(
            components, memory_context, games_on_theme=10, active_theme="ThreatVerification"
        )
        
        # Consequence should ALWAYS be unchanged
        assert modified.position_consequence_line == original_consequence


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
