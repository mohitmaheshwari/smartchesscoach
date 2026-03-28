"""
Coach Memory Service - Coaching Memory Continuity Layer

This service manages the coach's "memory" of the player's journey:
- What lessons have been taught recently (for cooldowns)
- How patterns are progressing over time
- Long-term themes and milestones

ARCHITECTURE:
- This service is ISOLATED (no narrative code)
- It only handles: memory update, memory summarization, cooldown logic, milestone detection
- Narrative engine reads from `build_context()` - never raw DB

MEMORY TIERS:
1. Active Memory (rolling 20 games):
   - lesson_memory: Recent lessons for cooldown tracking
   - pattern_progress: How specific patterns are trending
   
2. Identity Memory (lifetime):
   - theme_history: Major themes worked on
   - milestones: First clean game, first streak, etc.

PHILOSOPHY:
- ONE lesson per game (never multiple)
- Memory influences PHRASING, not ANALYSIS
- Cooldowns prevent repetitive coaching
- Milestones create meaningful narrative anchors
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


# =============================================================================
# MILESTONE DEFINITIONS
# =============================================================================

class MilestoneType(str, Enum):
    """Types of memorable coaching milestones"""
    FIRST_CLEAN_GAME = "first_clean_game"           # First game with positive coaching
    FIRST_THREE_STREAK = "first_three_streak"       # First 3-game clean streak
    FIRST_FIVE_STREAK = "first_five_streak"         # First 5-game clean streak
    LESSON_MASTERY = "lesson_mastery"               # Lesson not triggered for 10+ games
    THEME_GRADUATION = "theme_graduation"           # Successfully moved on from a theme
    FIRST_IMPROVEMENT = "first_improvement"         # First detected improvement in pattern


MILESTONE_DESCRIPTIONS = {
    MilestoneType.FIRST_CLEAN_GAME: "First game with clean play",
    MilestoneType.FIRST_THREE_STREAK: "Three games in a row without major errors",
    MilestoneType.FIRST_FIVE_STREAK: "Five games in a row without major errors",
    MilestoneType.LESSON_MASTERY: "This lesson hasn't appeared in 10 games - great progress",
    MilestoneType.THEME_GRADUATION: "Successfully graduated from this focus area",
    MilestoneType.FIRST_IMPROVEMENT: "First time this pattern has improved",
}


# =============================================================================
# MEMORY DATA STRUCTURES
# =============================================================================

@dataclass
class LessonMemoryEntry:
    """A single lesson memory entry"""
    lesson_key: str
    game_id: str
    timestamp: datetime
    lesson_category: str
    lesson_intensity: float
    
    def to_dict(self) -> Dict:
        return {
            "lesson_key": self.lesson_key,
            "game_id": self.game_id,
            "timestamp": self.timestamp.isoformat(),
            "lesson_category": self.lesson_category,
            "lesson_intensity": round(self.lesson_intensity, 2)
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'LessonMemoryEntry':
        return cls(
            lesson_key=data["lesson_key"],
            game_id=data["game_id"],
            timestamp=datetime.fromisoformat(data["timestamp"]) if isinstance(data["timestamp"], str) else data["timestamp"],
            lesson_category=data["lesson_category"],
            lesson_intensity=data.get("lesson_intensity", 0.5)
        )


@dataclass
class PatternProgress:
    """Progress tracking for a specific pattern/lesson"""
    lesson_key: str
    occurrence_count: int          # Total times this lesson has appeared
    last_occurrence_game_id: str   # Most recent game
    last_occurrence_at: datetime
    games_since_last: int          # Games since this pattern appeared
    trend: str                     # "improving", "stable", "recurring"
    
    def to_dict(self) -> Dict:
        return {
            "lesson_key": self.lesson_key,
            "occurrence_count": self.occurrence_count,
            "last_occurrence_game_id": self.last_occurrence_game_id,
            "last_occurrence_at": self.last_occurrence_at.isoformat(),
            "games_since_last": self.games_since_last,
            "trend": self.trend
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'PatternProgress':
        return cls(
            lesson_key=data["lesson_key"],
            occurrence_count=data["occurrence_count"],
            last_occurrence_game_id=data["last_occurrence_game_id"],
            last_occurrence_at=datetime.fromisoformat(data["last_occurrence_at"]) if isinstance(data["last_occurrence_at"], str) else data["last_occurrence_at"],
            games_since_last=data.get("games_since_last", 0),
            trend=data.get("trend", "stable")
        )


@dataclass
class Milestone:
    """A memorable coaching milestone"""
    milestone_type: str
    achieved_at: datetime
    game_id: Optional[str]
    context: Dict  # Additional context (e.g., which lesson was mastered)
    
    def to_dict(self) -> Dict:
        return {
            "milestone_type": self.milestone_type,
            "achieved_at": self.achieved_at.isoformat(),
            "game_id": self.game_id,
            "context": self.context
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Milestone':
        return cls(
            milestone_type=data["milestone_type"],
            achieved_at=datetime.fromisoformat(data["achieved_at"]) if isinstance(data["achieved_at"], str) else data["achieved_at"],
            game_id=data.get("game_id"),
            context=data.get("context", {})
        )


@dataclass
class ThemeHistoryEntry:
    """Historical record of a theme the user worked on"""
    theme: str
    started_at: datetime
    ended_at: Optional[datetime]
    games_on_theme: int
    outcome: str  # "graduated", "ongoing", "switched"
    
    def to_dict(self) -> Dict:
        return {
            "theme": self.theme,
            "started_at": self.started_at.isoformat(),
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "games_on_theme": self.games_on_theme,
            "outcome": self.outcome
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'ThemeHistoryEntry':
        return cls(
            theme=data["theme"],
            started_at=datetime.fromisoformat(data["started_at"]) if isinstance(data["started_at"], str) else data["started_at"],
            ended_at=datetime.fromisoformat(data["ended_at"]) if data.get("ended_at") else None,
            games_on_theme=data.get("games_on_theme", 0),
            outcome=data.get("outcome", "ongoing")
        )


# =============================================================================
# MEMORY CONTEXT - What Narrative Engine Receives
# =============================================================================

@dataclass
class MemoryContext:
    """
    Summarized memory context for narrative engine.
    
    This is the ONLY thing narrative engine should read.
    It abstracts away the raw memory data.
    """
    # Cooldown info
    is_lesson_on_cooldown: bool
    games_until_cooldown_expires: int
    
    # Pattern info
    lesson_occurrence_count: int      # How many times this lesson has appeared
    lesson_trend: str                 # "improving", "stable", "recurring"
    games_since_lesson: int           # Games since this lesson last appeared
    
    # Recent context
    recent_lessons: List[str]         # Last 3-5 lesson keys for variety
    recent_categories: List[str]      # Last 3-5 categories
    
    # Milestone context
    active_milestone: Optional[str]   # If a milestone was just achieved
    milestone_message: Optional[str]  # Human-readable milestone message
    
    # Identity context
    most_frequent_lesson: Optional[str]  # The player's most common lesson
    total_games_analyzed: int
    current_streak: int               # Clean game streak
    
    def to_dict(self) -> Dict:
        return {
            "is_lesson_on_cooldown": self.is_lesson_on_cooldown,
            "games_until_cooldown_expires": self.games_until_cooldown_expires,
            "lesson_occurrence_count": self.lesson_occurrence_count,
            "lesson_trend": self.lesson_trend,
            "games_since_lesson": self.games_since_lesson,
            "recent_lessons": self.recent_lessons,
            "recent_categories": self.recent_categories,
            "active_milestone": self.active_milestone,
            "milestone_message": self.milestone_message,
            "most_frequent_lesson": self.most_frequent_lesson,
            "total_games_analyzed": self.total_games_analyzed,
            "current_streak": self.current_streak
        }


# =============================================================================
# COACH MEMORY SERVICE
# =============================================================================

class CoachMemoryService:
    """
    Service for managing coaching memory.
    
    Responsibilities:
    - Update memory after each game summary
    - Build context for narrative engine
    - Check cooldowns
    - Detect milestones
    """
    
    ACTIVE_MEMORY_WINDOW = 20  # Rolling window of games for active memory
    
    def __init__(self, db):
        self.db = db
    
    async def get_memory_state(self, user_id: str) -> Optional[Dict]:
        """Get raw memory state from database"""
        doc = await self.db.coach_memory.find_one({"user_id": user_id})
        if doc:
            doc.pop("_id", None)
        return doc
    
    async def initialize_memory(self, user_id: str) -> Dict:
        """Initialize empty memory for a new user"""
        memory = {
            "user_id": user_id,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            # Active Memory
            "lesson_memory": [],        # List of LessonMemoryEntry dicts
            "pattern_progress": {},     # Dict of lesson_key -> PatternProgress dict
            # Identity Memory
            "theme_history": [],        # List of ThemeHistoryEntry dicts
            "milestones": [],           # List of Milestone dicts
            # Stats
            "total_games_analyzed": 0,
            "games_since_memory_start": 0
        }
        
        await self.db.coach_memory.replace_one(
            {"user_id": user_id},
            memory,
            upsert=True
        )
        
        return memory
    
    async def update_memory_after_game(
        self,
        user_id: str,
        game_id: str,
        lesson_key: str,
        lesson_category: str,
        lesson_intensity: float,
        is_positive_game: bool,
        current_streak: int
    ) -> Dict[str, Any]:
        """
        Update memory after a game is analyzed.
        
        Returns dict with:
        - new_milestone: Optional[Milestone] if one was achieved
        - cooldown_triggered: bool
        - pattern_update: str description of pattern change
        """
        memory = await self.get_memory_state(user_id)
        if not memory:
            memory = await self.initialize_memory(user_id)
        
        now = datetime.now(timezone.utc)
        updates = {
            "new_milestone": None,
            "cooldown_triggered": False,
            "pattern_update": None
        }
        
        # 1. Update lesson memory (rolling window)
        lesson_entry = LessonMemoryEntry(
            lesson_key=lesson_key,
            game_id=game_id,
            timestamp=now,
            lesson_category=lesson_category,
            lesson_intensity=lesson_intensity
        )
        
        lesson_memory = memory.get("lesson_memory", [])
        lesson_memory.append(lesson_entry.to_dict())
        
        # Keep only last ACTIVE_MEMORY_WINDOW entries
        if len(lesson_memory) > self.ACTIVE_MEMORY_WINDOW:
            lesson_memory = lesson_memory[-self.ACTIVE_MEMORY_WINDOW:]
        
        # 2. Update pattern progress
        pattern_progress = memory.get("pattern_progress", {})
        
        if lesson_key in pattern_progress:
            progress = PatternProgress.from_dict(pattern_progress[lesson_key])
            old_count = progress.occurrence_count
            progress.occurrence_count += 1
            progress.games_since_last = 0
            progress.last_occurrence_game_id = game_id
            progress.last_occurrence_at = now
            
            # Determine trend
            if progress.occurrence_count >= 3 and progress.games_since_last < 3:
                progress.trend = "recurring"
                updates["pattern_update"] = f"Pattern recurring: {lesson_key} ({progress.occurrence_count}x)"
            elif progress.games_since_last > 5:
                progress.trend = "improving"
                updates["pattern_update"] = f"Pattern improving: {lesson_key}"
            else:
                progress.trend = "stable"
            
            pattern_progress[lesson_key] = progress.to_dict()
        else:
            # First occurrence of this lesson
            progress = PatternProgress(
                lesson_key=lesson_key,
                occurrence_count=1,
                last_occurrence_game_id=game_id,
                last_occurrence_at=now,
                games_since_last=0,
                trend="stable"
            )
            pattern_progress[lesson_key] = progress.to_dict()
            updates["pattern_update"] = f"New pattern detected: {lesson_key}"
        
        # 3. Increment games_since_last for OTHER patterns
        for key in pattern_progress:
            if key != lesson_key:
                progress_dict = pattern_progress[key]
                progress_dict["games_since_last"] = progress_dict.get("games_since_last", 0) + 1
        
        # 4. Check for milestones
        milestones = memory.get("milestones", [])
        milestone_types_achieved = {m["milestone_type"] for m in milestones}
        
        # First clean game
        if is_positive_game and MilestoneType.FIRST_CLEAN_GAME.value not in milestone_types_achieved:
            new_milestone = Milestone(
                milestone_type=MilestoneType.FIRST_CLEAN_GAME.value,
                achieved_at=now,
                game_id=game_id,
                context={"lesson_key": lesson_key}
            )
            milestones.append(new_milestone.to_dict())
            updates["new_milestone"] = new_milestone.to_dict()
            logger.info(f"[MILESTONE] {user_id} achieved FIRST_CLEAN_GAME")
        
        # First 3-game streak
        if current_streak >= 3 and MilestoneType.FIRST_THREE_STREAK.value not in milestone_types_achieved:
            new_milestone = Milestone(
                milestone_type=MilestoneType.FIRST_THREE_STREAK.value,
                achieved_at=now,
                game_id=game_id,
                context={"streak": current_streak}
            )
            milestones.append(new_milestone.to_dict())
            updates["new_milestone"] = new_milestone.to_dict()
            logger.info(f"[MILESTONE] {user_id} achieved FIRST_THREE_STREAK")
        
        # First 5-game streak
        if current_streak >= 5 and MilestoneType.FIRST_FIVE_STREAK.value not in milestone_types_achieved:
            new_milestone = Milestone(
                milestone_type=MilestoneType.FIRST_FIVE_STREAK.value,
                achieved_at=now,
                game_id=game_id,
                context={"streak": current_streak}
            )
            milestones.append(new_milestone.to_dict())
            updates["new_milestone"] = new_milestone.to_dict()
            logger.info(f"[MILESTONE] {user_id} achieved FIRST_FIVE_STREAK")
        
        # Lesson mastery (10+ games without this lesson)
        for key, prog_dict in pattern_progress.items():
            if prog_dict.get("games_since_last", 0) >= 10:
                mastery_type = f"{MilestoneType.LESSON_MASTERY.value}:{key}"
                if mastery_type not in milestone_types_achieved:
                    new_milestone = Milestone(
                        milestone_type=MilestoneType.LESSON_MASTERY.value,
                        achieved_at=now,
                        game_id=game_id,
                        context={"lesson_key": key, "games_without": prog_dict["games_since_last"]}
                    )
                    milestones.append(new_milestone.to_dict())
                    updates["new_milestone"] = new_milestone.to_dict()
                    logger.info(f"[MILESTONE] {user_id} achieved LESSON_MASTERY for {key}")
        
        # 5. Update stats
        total_games = memory.get("total_games_analyzed", 0) + 1
        
        # 6. Save updated memory
        memory["lesson_memory"] = lesson_memory
        memory["pattern_progress"] = pattern_progress
        memory["milestones"] = milestones
        memory["total_games_analyzed"] = total_games
        memory["updated_at"] = now
        
        await self.db.coach_memory.replace_one(
            {"user_id": user_id},
            memory,
            upsert=True
        )
        
        return updates
    
    def is_on_cooldown(
        self,
        lesson_key: str,
        lesson_memory: List[Dict],
        cooldown_games: int
    ) -> Tuple[bool, int]:
        """
        Check if a lesson is on cooldown.
        
        Returns:
            (is_on_cooldown, games_until_cooldown_expires)
        """
        # Find last occurrence of this lesson
        recent_occurrences = [
            entry for entry in lesson_memory
            if entry.get("lesson_key") == lesson_key
        ]
        
        if not recent_occurrences:
            return False, 0
        
        # Count games since last occurrence
        # lesson_memory is ordered chronologically
        last_idx = -1
        for i, entry in enumerate(lesson_memory):
            if entry.get("lesson_key") == lesson_key:
                last_idx = i
        
        if last_idx == -1:
            return False, 0
        
        games_since = len(lesson_memory) - 1 - last_idx
        
        if games_since < cooldown_games:
            return True, cooldown_games - games_since
        
        return False, 0
    
    async def build_context(
        self,
        user_id: str,
        current_lesson_key: str,
        current_streak: int = 0
    ) -> MemoryContext:
        """
        Build memory context for narrative engine.
        
        This is the ABSTRACTION LAYER. Narrative engine should
        ONLY read from this, never raw database.
        
        Args:
            user_id: The user
            current_lesson_key: The lesson being assigned this game
            current_streak: Current clean game streak
            
        Returns:
            MemoryContext with summarized memory state
        """
        import lesson_resolver
        
        memory = await self.get_memory_state(user_id)
        
        if not memory:
            # No memory yet - return empty context
            return MemoryContext(
                is_lesson_on_cooldown=False,
                games_until_cooldown_expires=0,
                lesson_occurrence_count=0,
                lesson_trend="stable",
                games_since_lesson=0,
                recent_lessons=[],
                recent_categories=[],
                active_milestone=None,
                milestone_message=None,
                most_frequent_lesson=None,
                total_games_analyzed=0,
                current_streak=current_streak
            )
        
        lesson_memory = memory.get("lesson_memory", [])
        pattern_progress = memory.get("pattern_progress", {})
        milestones = memory.get("milestones", [])
        
        # Check cooldown
        cooldown_games = lesson_resolver.get_lesson_cooldown(current_lesson_key)
        is_cooldown, games_until = self.is_on_cooldown(
            current_lesson_key,
            lesson_memory,
            cooldown_games
        )
        
        # Get pattern info for current lesson
        pattern = pattern_progress.get(current_lesson_key, {})
        occurrence_count = pattern.get("occurrence_count", 0)
        trend = pattern.get("trend", "stable")
        games_since = pattern.get("games_since_last", 0)
        
        # Recent lessons (last 5)
        recent_lessons = [
            entry.get("lesson_key")
            for entry in lesson_memory[-5:]
        ]
        
        # Recent categories (last 5)
        recent_categories = [
            entry.get("lesson_category")
            for entry in lesson_memory[-5:]
        ]
        
        # Find most recent milestone (within last 3 games)
        active_milestone = None
        milestone_message = None
        if milestones:
            # Check if any milestone was achieved in last 3 games
            recent_game_ids = [e.get("game_id") for e in lesson_memory[-3:]]
            for m in reversed(milestones):
                if m.get("game_id") in recent_game_ids:
                    active_milestone = m.get("milestone_type")
                    milestone_message = MILESTONE_DESCRIPTIONS.get(
                        MilestoneType(active_milestone) if active_milestone in [e.value for e in MilestoneType] else None
                    )
                    break
        
        # Find most frequent lesson
        lesson_counts = {}
        for entry in lesson_memory:
            key = entry.get("lesson_key")
            lesson_counts[key] = lesson_counts.get(key, 0) + 1
        
        most_frequent = None
        if lesson_counts:
            most_frequent = max(lesson_counts, key=lesson_counts.get)
        
        return MemoryContext(
            is_lesson_on_cooldown=is_cooldown,
            games_until_cooldown_expires=games_until,
            lesson_occurrence_count=occurrence_count,
            lesson_trend=trend,
            games_since_lesson=games_since,
            recent_lessons=recent_lessons,
            recent_categories=recent_categories,
            active_milestone=active_milestone,
            milestone_message=milestone_message,
            most_frequent_lesson=most_frequent,
            total_games_analyzed=memory.get("total_games_analyzed", 0),
            current_streak=current_streak
        )
    
    async def add_theme_history(
        self,
        user_id: str,
        theme: str,
        started_at: datetime,
        games_on_theme: int,
        outcome: str = "ongoing"
    ) -> None:
        """Add or update theme in history"""
        memory = await self.get_memory_state(user_id)
        if not memory:
            memory = await self.initialize_memory(user_id)
        
        theme_history = memory.get("theme_history", [])
        
        # Check if theme already exists
        for entry in theme_history:
            if entry.get("theme") == theme and entry.get("outcome") == "ongoing":
                entry["games_on_theme"] = games_on_theme
                entry["outcome"] = outcome
                if outcome != "ongoing":
                    entry["ended_at"] = datetime.now(timezone.utc).isoformat()
                break
        else:
            # New theme
            new_entry = ThemeHistoryEntry(
                theme=theme,
                started_at=started_at,
                ended_at=None,
                games_on_theme=games_on_theme,
                outcome=outcome
            )
            theme_history.append(new_entry.to_dict())
        
        memory["theme_history"] = theme_history
        memory["updated_at"] = datetime.now(timezone.utc)
        
        await self.db.coach_memory.replace_one(
            {"user_id": user_id},
            memory,
            upsert=True
        )


def get_memory_service(db) -> CoachMemoryService:
    """Factory function to get memory service instance"""
    return CoachMemoryService(db)
