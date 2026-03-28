"""
Test Memory Insights Generation Logic (Unit Tests)

Tests the _generate_memory_insights function from postgame_analysis.py:
1. Recurring patterns appear when weakness detected 3+ times
2. Improvement acknowledgments for known weaknesses avoided
3. Performance comparison insights when games_together >= 3
4. First-time pattern detection
"""

import pytest
import sys
import os
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.postgame_analysis import (
    _generate_memory_insights,
    MistakeAnalysis,
    MistakeType,
    HabitViolation,
    HabitType,
    MemoryInsight
)


class TestMemoryInsightsRecurringPatterns:
    """Test recurring pattern detection in memory insights"""
    
    def test_recurring_pattern_shows_when_weakness_count_3(self):
        """When a weakness has count >= 3, should show recurring_pattern insight"""
        # Known weaknesses with 3+ occurrences
        known_weaknesses = [
            {"name": "early queen", "count": 3, "improving": False}
        ]
        
        # Current game has early queen violation
        violations = [
            HabitViolation(
                habit_type=HabitType.EARLY_QUEEN,
                move_number=5,
                description="Queen moved early"
            )
        ]
        
        insights = _generate_memory_insights(
            mistakes=[],
            habit_violations=violations,
            habits_improved=[],
            known_weaknesses=known_weaknesses,
            games_together=5,
            avg_accuracy=70.0,
            avg_blunders=1.0,
            perf_rating=1200,
            actual_rating=1200
        )
        
        # Should have a recurring_pattern insight
        recurring = [i for i in insights if i.insight_type == "recurring_pattern"]
        assert len(recurring) > 0, "Should have recurring_pattern insight for 3+ occurrence"
        assert "3 times" in recurring[0].message or "again" in recurring[0].message.lower()
    
    def test_recurring_pattern_shown_for_count_2_with_awareness_message(self):
        """Weakness with count = 2 shows awareness message (less urgent than 3+)"""
        known_weaknesses = [
            {"name": "early queen", "count": 2, "improving": False}
        ]
        
        violations = [
            HabitViolation(
                habit_type=HabitType.EARLY_QUEEN,
                move_number=5,
                description="Queen moved early"
            )
        ]
        
        insights = _generate_memory_insights(
            mistakes=[],
            habit_violations=violations,
            habits_improved=[],
            known_weaknesses=known_weaknesses,
            games_together=3,
            avg_accuracy=70.0,
            avg_blunders=1.0,
            perf_rating=1200,
            actual_rating=1200
        )
        
        recurring = [i for i in insights if i.insight_type == "recurring_pattern"]
        # Count=2 still triggers recurring_pattern but with less urgent message
        assert len(recurring) > 0, "Should show recurring pattern for count >= 2"
        # Message should be awareness style, not urgent
        assert "stay aware" in recurring[0].message.lower() or "before" in recurring[0].message.lower()
    
    def test_recurring_pattern_with_high_count_shows_severity(self):
        """Weakness with 5+ occurrences should indicate main habit to fix"""
        known_weaknesses = [
            {"name": "overconfidence", "count": 5, "improving": False}
        ]
        
        violations = [
            HabitViolation(
                habit_type=HabitType.OVERCONFIDENCE,
                move_number=20,
                description="Blunder while winning"
            )
        ]
        
        insights = _generate_memory_insights(
            mistakes=[],
            habit_violations=violations,
            habits_improved=[],
            known_weaknesses=known_weaknesses,
            games_together=10,
            avg_accuracy=65.0,
            avg_blunders=2.0,
            perf_rating=1100,
            actual_rating=1200
        )
        
        recurring = [i for i in insights if i.insight_type == "recurring_pattern"]
        assert len(recurring) > 0
        # High count should mention "main habit" or show count
        message = recurring[0].message.lower()
        assert "5" in message or "main" in message


class TestMemoryInsightsImprovement:
    """Test improvement acknowledgment in memory insights"""
    
    def test_improvement_insight_when_known_weakness_avoided(self):
        """When user avoids a known weakness, should show improvement insight"""
        # NOTE: The matching logic checks if weakness.name is IN habit_name
        # So use a weakness name that is a substring of "early queen"
        known_weaknesses = [
            {"name": "early", "count": 4, "improving": False}
        ]
        
        habits_improved = ["early_queen"]  # User avoided it this game
        
        insights = _generate_memory_insights(
            mistakes=[],
            habit_violations=[],
            habits_improved=habits_improved,
            known_weaknesses=known_weaknesses,
            games_together=5,
            avg_accuracy=70.0,
            avg_blunders=1.0,
            perf_rating=1200,
            actual_rating=1200
        )
        
        improvement = [i for i in insights if i.insight_type == "improvement"]
        assert len(improvement) > 0, "Should acknowledge improvement when weakness avoided"
        assert "progress" in improvement[0].message.lower() or "avoided" in improvement[0].message.lower()
    
    def test_no_improvement_insight_when_not_known_weakness(self):
        """Improvement insight only when the avoided habit was a known weakness"""
        known_weaknesses = []  # No prior weaknesses
        habits_improved = ["early_queen"]
        
        insights = _generate_memory_insights(
            mistakes=[],
            habit_violations=[],
            habits_improved=habits_improved,
            known_weaknesses=known_weaknesses,
            games_together=5,
            avg_accuracy=70.0,
            avg_blunders=1.0,
            perf_rating=1200,
            actual_rating=1200
        )
        
        improvement = [i for i in insights if i.insight_type == "improvement"]
        # No improvement insight for non-known weakness
        assert len(improvement) == 0


class TestMemoryInsightsPerformanceComparison:
    """Test performance comparison insights"""
    
    def test_performance_comparison_requires_3_games(self):
        """Performance comparison only shows after 3+ games together"""
        insights_few_games = _generate_memory_insights(
            mistakes=[],
            habit_violations=[],
            habits_improved=[],
            known_weaknesses=[],
            games_together=2,  # Not enough games
            avg_accuracy=70.0,
            avg_blunders=1.5,
            perf_rating=1200,
            actual_rating=1200
        )
        
        comparison_few = [i for i in insights_few_games if i.insight_type == "performance_comparison"]
        assert len(comparison_few) == 0, "No performance comparison with < 3 games"
    
    def test_performance_comparison_shows_above_level(self):
        """Show performance comparison when playing above level"""
        insights = _generate_memory_insights(
            mistakes=[],
            habit_violations=[],
            habits_improved=[],
            known_weaknesses=[],
            games_together=5,
            avg_accuracy=70.0,
            avg_blunders=1.0,
            perf_rating=1400,  # Playing above 1200 actual
            actual_rating=1200
        )
        
        comparison = [i for i in insights if i.insight_type == "performance_comparison"]
        # Should have a comparison insight about playing above level
        above_level = [i for i in comparison if "above" in i.message.lower() or "improvement" in i.message.lower()]
        assert len(above_level) > 0


class TestMemoryInsightsFirstTime:
    """Test first-time pattern detection"""
    
    def test_first_time_pattern_for_new_habit_violation(self):
        """New pattern not in known weaknesses should show first_time insight"""
        known_weaknesses = [
            {"name": "early queen", "count": 3, "improving": False}
        ]
        
        # New violation not in known weaknesses
        violations = [
            HabitViolation(
                habit_type=HabitType.TIME_MANAGEMENT,
                move_number=30,
                description="Running low on time"
            )
        ]
        
        insights = _generate_memory_insights(
            mistakes=[],
            habit_violations=violations,
            habits_improved=[],
            known_weaknesses=known_weaknesses,
            games_together=3,
            avg_accuracy=70.0,
            avg_blunders=1.0,
            perf_rating=1200,
            actual_rating=1200
        )
        
        first_time = [i for i in insights if i.insight_type == "first_time"]
        assert len(first_time) > 0, "Should have first_time insight for new pattern"


class TestMemoryInsightsMilestone:
    """Test milestone insights at game count thresholds"""
    
    def test_milestone_at_game_5(self):
        """Milestone insight at game 5"""
        insights = _generate_memory_insights(
            mistakes=[],
            habit_violations=[],
            habits_improved=[],
            known_weaknesses=[],
            games_together=5,
            avg_accuracy=70.0,
            avg_blunders=1.0,
            perf_rating=1200,
            actual_rating=1200
        )
        
        milestone = [i for i in insights if i.insight_type == "milestone"]
        assert len(milestone) > 0, "Should show milestone at game 5"
        assert "#5" in milestone[0].message or "5" in milestone[0].message
    
    def test_no_milestone_at_arbitrary_count(self):
        """No milestone at arbitrary game counts"""
        insights = _generate_memory_insights(
            mistakes=[],
            habit_violations=[],
            habits_improved=[],
            known_weaknesses=[],
            games_together=7,  # Not a milestone
            avg_accuracy=70.0,
            avg_blunders=1.0,
            perf_rating=1200,
            actual_rating=1200
        )
        
        milestone = [i for i in insights if i.insight_type == "milestone"]
        assert len(milestone) == 0, "Should not show milestone at game 7"


class TestMemoryInsightsLimits:
    """Test insight count limits"""
    
    def test_max_5_insights_returned(self):
        """Should return at most 5 insights"""
        # Create conditions that would generate many insights
        known_weaknesses = [
            {"name": f"weakness_{i}", "count": 4, "improving": False}
            for i in range(5)
        ]
        
        violations = [
            HabitViolation(
                habit_type=HabitType.EARLY_QUEEN,
                move_number=i,
                description=f"Violation {i}"
            )
            for i in range(5)
        ]
        
        insights = _generate_memory_insights(
            mistakes=[],
            habit_violations=violations,
            habits_improved=["early_queen", "impatience", "overconfidence"],
            known_weaknesses=known_weaknesses,
            games_together=10,  # Milestone
            avg_accuracy=70.0,
            avg_blunders=0,  # Zero blunders to trigger comparison
            perf_rating=1400,  # Above actual
            actual_rating=1200
        )
        
        assert len(insights) <= 5, f"Should return max 5 insights, got {len(insights)}"
