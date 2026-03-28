"""
Test Coach Memory Service - Memory Continuity Layer

Tests:
1. Memory initialization
2. Memory updates after game
3. Cooldown logic
4. Milestone detection
5. build_context() abstraction
"""

import pytest
import sys
import os
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from coach_memory_service import (
    CoachMemoryService,
    MemoryContext,
    LessonMemoryEntry,
    PatternProgress,
    Milestone,
    MilestoneType,
    MILESTONE_DESCRIPTIONS
)


class MockDB:
    """Mock database for testing"""
    def __init__(self):
        self.coach_memory = MockCollection()


class MockCollection:
    """Mock MongoDB collection"""
    def __init__(self):
        self.data = {}
    
    async def find_one(self, query):
        user_id = query.get("user_id")
        return self.data.get(user_id)
    
    async def replace_one(self, query, doc, upsert=False):
        user_id = query.get("user_id")
        self.data[user_id] = doc
        return MagicMock(modified_count=1)


class TestMemoryInitialization:
    """Test memory initialization"""
    
    @pytest.mark.asyncio
    async def test_initialize_empty_memory(self):
        """Initialize memory for new user"""
        db = MockDB()
        service = CoachMemoryService(db)
        
        memory = await service.initialize_memory("test_user")
        
        assert memory["user_id"] == "test_user"
        assert memory["lesson_memory"] == []
        assert memory["pattern_progress"] == {}
        assert memory["theme_history"] == []
        assert memory["milestones"] == []
        assert memory["total_games_analyzed"] == 0
    
    @pytest.mark.asyncio
    async def test_get_memory_returns_none_for_new_user(self):
        """get_memory_state returns None for user without memory"""
        db = MockDB()
        service = CoachMemoryService(db)
        
        memory = await service.get_memory_state("nonexistent_user")
        
        assert memory is None


class TestMemoryUpdates:
    """Test memory updates after games"""
    
    @pytest.mark.asyncio
    async def test_update_creates_lesson_entry(self):
        """update_memory_after_game creates lesson entry"""
        db = MockDB()
        service = CoachMemoryService(db)
        
        await service.initialize_memory("test_user")
        
        await service.update_memory_after_game(
            user_id="test_user",
            game_id="game_1",
            lesson_key="verify_opponent_threats",
            lesson_category="threat_awareness",
            lesson_intensity=0.7,
            is_positive_game=False,
            current_streak=0
        )
        
        memory = await service.get_memory_state("test_user")
        
        assert len(memory["lesson_memory"]) == 1
        assert memory["lesson_memory"][0]["lesson_key"] == "verify_opponent_threats"
        assert memory["total_games_analyzed"] == 1
    
    @pytest.mark.asyncio
    async def test_update_creates_pattern_progress(self):
        """update_memory_after_game creates pattern progress"""
        db = MockDB()
        service = CoachMemoryService(db)
        
        await service.initialize_memory("test_user")
        
        await service.update_memory_after_game(
            user_id="test_user",
            game_id="game_1",
            lesson_key="verify_opponent_threats",
            lesson_category="threat_awareness",
            lesson_intensity=0.7,
            is_positive_game=False,
            current_streak=0
        )
        
        memory = await service.get_memory_state("test_user")
        
        assert "verify_opponent_threats" in memory["pattern_progress"]
        progress = memory["pattern_progress"]["verify_opponent_threats"]
        assert progress["occurrence_count"] == 1
        assert progress["trend"] == "stable"
    
    @pytest.mark.asyncio
    async def test_recurring_pattern_detected(self):
        """Recurring patterns are detected correctly"""
        db = MockDB()
        service = CoachMemoryService(db)
        
        await service.initialize_memory("test_user")
        
        # Add same lesson 3 times
        for i in range(3):
            await service.update_memory_after_game(
                user_id="test_user",
                game_id=f"game_{i}",
                lesson_key="verify_opponent_threats",
                lesson_category="threat_awareness",
                lesson_intensity=0.7,
                is_positive_game=False,
                current_streak=0
            )
        
        memory = await service.get_memory_state("test_user")
        progress = memory["pattern_progress"]["verify_opponent_threats"]
        
        assert progress["occurrence_count"] == 3
        assert progress["trend"] == "recurring"
    
    @pytest.mark.asyncio
    async def test_games_since_last_increments(self):
        """games_since_last increments for other patterns"""
        db = MockDB()
        service = CoachMemoryService(db)
        
        await service.initialize_memory("test_user")
        
        # Add pattern A
        await service.update_memory_after_game(
            user_id="test_user",
            game_id="game_1",
            lesson_key="pattern_a",
            lesson_category="calculation",
            lesson_intensity=0.5,
            is_positive_game=False,
            current_streak=0
        )
        
        # Add pattern B
        await service.update_memory_after_game(
            user_id="test_user",
            game_id="game_2",
            lesson_key="pattern_b",
            lesson_category="defense",
            lesson_intensity=0.5,
            is_positive_game=False,
            current_streak=0
        )
        
        memory = await service.get_memory_state("test_user")
        
        # Pattern A should have games_since_last = 1
        assert memory["pattern_progress"]["pattern_a"]["games_since_last"] == 1
        # Pattern B should have games_since_last = 0 (just occurred)
        assert memory["pattern_progress"]["pattern_b"]["games_since_last"] == 0


class TestCooldownLogic:
    """Test cooldown calculations"""
    
    def test_is_on_cooldown_empty_memory(self):
        """No cooldown with empty memory"""
        db = MockDB()
        service = CoachMemoryService(db)
        
        is_cooldown, games_until = service.is_on_cooldown(
            "verify_opponent_threats",
            [],
            cooldown_games=3
        )
        
        assert is_cooldown is False
        assert games_until == 0
    
    def test_is_on_cooldown_within_window(self):
        """Cooldown active within window"""
        db = MockDB()
        service = CoachMemoryService(db)
        
        lesson_memory = [
            {"lesson_key": "verify_opponent_threats", "game_id": "g1"},
            {"lesson_key": "other_lesson", "game_id": "g2"},
        ]
        
        is_cooldown, games_until = service.is_on_cooldown(
            "verify_opponent_threats",
            lesson_memory,
            cooldown_games=3
        )
        
        assert is_cooldown is True
        assert games_until == 2  # 3 - 1 (games since) = 2
    
    def test_is_on_cooldown_expired(self):
        """Cooldown expired after enough games"""
        db = MockDB()
        service = CoachMemoryService(db)
        
        lesson_memory = [
            {"lesson_key": "verify_opponent_threats", "game_id": "g1"},
            {"lesson_key": "other_lesson", "game_id": "g2"},
            {"lesson_key": "other_lesson", "game_id": "g3"},
            {"lesson_key": "other_lesson", "game_id": "g4"},
        ]
        
        is_cooldown, games_until = service.is_on_cooldown(
            "verify_opponent_threats",
            lesson_memory,
            cooldown_games=3
        )
        
        assert is_cooldown is False
        assert games_until == 0


class TestMilestoneDetection:
    """Test milestone detection"""
    
    @pytest.mark.asyncio
    async def test_first_clean_game_milestone(self):
        """First clean game triggers milestone"""
        db = MockDB()
        service = CoachMemoryService(db)
        
        await service.initialize_memory("test_user")
        
        result = await service.update_memory_after_game(
            user_id="test_user",
            game_id="game_1",
            lesson_key="positive_stability",
            lesson_category="discipline",
            lesson_intensity=0.3,
            is_positive_game=True,
            current_streak=1
        )
        
        assert result["new_milestone"] is not None
        assert result["new_milestone"]["milestone_type"] == MilestoneType.FIRST_CLEAN_GAME.value
    
    @pytest.mark.asyncio
    async def test_first_clean_game_only_once(self):
        """First clean game milestone only triggers once"""
        db = MockDB()
        service = CoachMemoryService(db)
        
        await service.initialize_memory("test_user")
        
        # First clean game
        result1 = await service.update_memory_after_game(
            user_id="test_user",
            game_id="game_1",
            lesson_key="positive_stability",
            lesson_category="discipline",
            lesson_intensity=0.3,
            is_positive_game=True,
            current_streak=1
        )
        
        # Second clean game
        result2 = await service.update_memory_after_game(
            user_id="test_user",
            game_id="game_2",
            lesson_key="positive_stability",
            lesson_category="discipline",
            lesson_intensity=0.3,
            is_positive_game=True,
            current_streak=2
        )
        
        # First should trigger milestone, second should not
        assert result1["new_milestone"] is not None
        # Second might trigger streak milestone, but not clean game again
        if result2["new_milestone"]:
            assert result2["new_milestone"]["milestone_type"] != MilestoneType.FIRST_CLEAN_GAME.value
    
    @pytest.mark.asyncio
    async def test_three_streak_milestone(self):
        """Three-game streak triggers milestone"""
        db = MockDB()
        service = CoachMemoryService(db)
        
        await service.initialize_memory("test_user")
        
        result = await service.update_memory_after_game(
            user_id="test_user",
            game_id="game_3",
            lesson_key="positive_stability",
            lesson_category="discipline",
            lesson_intensity=0.3,
            is_positive_game=True,
            current_streak=3
        )
        
        # Should trigger three streak milestone (and possibly first clean game)
        memory = await service.get_memory_state("test_user")
        milestone_types = [m["milestone_type"] for m in memory["milestones"]]
        
        assert MilestoneType.FIRST_THREE_STREAK.value in milestone_types


class TestBuildContext:
    """Test build_context() abstraction"""
    
    @pytest.mark.asyncio
    async def test_build_context_empty_memory(self):
        """build_context returns valid context for empty memory"""
        db = MockDB()
        service = CoachMemoryService(db)
        
        context = await service.build_context(
            user_id="test_user",
            current_lesson_key="verify_opponent_threats",
            current_streak=0
        )
        
        assert isinstance(context, MemoryContext)
        assert context.is_lesson_on_cooldown is False
        assert context.lesson_occurrence_count == 0
        assert context.recent_lessons == []
        assert context.total_games_analyzed == 0
    
    @pytest.mark.asyncio
    async def test_build_context_with_memory(self):
        """build_context returns populated context with memory"""
        db = MockDB()
        service = CoachMemoryService(db)
        
        await service.initialize_memory("test_user")
        
        # Add some games
        await service.update_memory_after_game(
            user_id="test_user",
            game_id="game_1",
            lesson_key="verify_opponent_threats",
            lesson_category="threat_awareness",
            lesson_intensity=0.7,
            is_positive_game=False,
            current_streak=0
        )
        
        context = await service.build_context(
            user_id="test_user",
            current_lesson_key="verify_opponent_threats",
            current_streak=0
        )
        
        assert context.lesson_occurrence_count == 1
        assert context.total_games_analyzed == 1
        assert "verify_opponent_threats" in context.recent_lessons
    
    @pytest.mark.asyncio
    async def test_build_context_to_dict(self):
        """MemoryContext.to_dict() works correctly"""
        db = MockDB()
        service = CoachMemoryService(db)
        
        context = await service.build_context(
            user_id="test_user",
            current_lesson_key="verify_opponent_threats",
            current_streak=2
        )
        
        d = context.to_dict()
        
        assert "is_lesson_on_cooldown" in d
        assert "lesson_occurrence_count" in d
        assert "current_streak" in d
        assert d["current_streak"] == 2


class TestMemoryContextIntegration:
    """Test memory context integration with lesson resolver"""
    
    @pytest.mark.asyncio
    async def test_context_includes_cooldown_from_resolver(self):
        """Context uses cooldown from lesson_resolver"""
        db = MockDB()
        service = CoachMemoryService(db)
        
        await service.initialize_memory("test_user")
        
        # Add a lesson
        await service.update_memory_after_game(
            user_id="test_user",
            game_id="game_1",
            lesson_key="verify_opponent_threats",
            lesson_category="threat_awareness",
            lesson_intensity=0.7,
            is_positive_game=False,
            current_streak=0
        )
        
        # Build context for same lesson
        context = await service.build_context(
            user_id="test_user",
            current_lesson_key="verify_opponent_threats",
            current_streak=0
        )
        
        # Should be on cooldown (default cooldown is 3 games)
        assert context.is_lesson_on_cooldown is True
        assert context.games_until_cooldown_expires > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
