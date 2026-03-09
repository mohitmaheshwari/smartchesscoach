"""
Human Coach Service
====================

The SOUL of human-like coaching - combines all elements to make the coach feel human.

Components:
1. Socratic Engine Integration - Guide discovery, don't tell answers
2. Progressive Curriculum - Track weaknesses, create focused training plans
3. Emotional Intelligence - Detect frustration, adapt tone
4. Memory Surfacing - Remember past sessions, connect patterns

This service transforms:
    "You blundered. Best move was Qxd4."
Into:
    "Welcome back! Last session we worked on piece safety. 
     I notice this position is tricky - what were you trying to achieve with Nf3?
     (If frustrated) Take a breath, you're doing better than you think.
     Remember that fork pattern from yesterday? Similar idea here..."

Usage:
    coach = HumanCoachService(db, user_id, user_rating)
    
    # Get welcome message with memory
    welcome = await coach.get_welcome_message()
    
    # Get Socratic response to a mistake
    response = await coach.get_mistake_response(fen, move_played, best_move, eval_loss)
    
    # Get curriculum recommendation
    curriculum = await coach.get_weekly_curriculum()
    
    # Detect emotional state
    emotion = coach.detect_emotional_state(recent_results, time_between_moves)
"""

import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
import random

logger = logging.getLogger(__name__)


class EmotionalState(str, Enum):
    """Detected emotional state of the player."""
    CONFIDENT = "confident"        # Winning streak, quick moves
    FRUSTRATED = "frustrated"      # Losing streak, long pauses
    TILTED = "tilted"              # Multiple blunders in a row
    FOCUSED = "focused"            # Consistent time, careful play
    RUSHED = "rushed"              # Very fast moves, might be impatient
    UNCERTAIN = "uncertain"        # Long pauses, tentative moves
    NEUTRAL = "neutral"            # Default state


class WeaknessCategory(str, Enum):
    """Categories of chess weaknesses."""
    TACTICS = "tactics"            # Missing forks, pins, etc.
    PIECE_SAFETY = "piece_safety"  # Hanging pieces
    KING_SAFETY = "king_safety"    # Exposing king
    PAWN_STRUCTURE = "pawn_structure"  # Weak pawns, bad structure
    DEVELOPMENT = "development"    # Slow piece development
    ENDGAME = "endgame"           # Endgame technique
    TIME_MANAGEMENT = "time_management"  # Time trouble
    OPENINGS = "openings"          # Opening mistakes


@dataclass
class CoachMemory:
    """What the coach remembers about the player."""
    total_sessions: int = 0
    last_session_date: Optional[str] = None
    recent_results: List[str] = field(default_factory=list)  # ["win", "loss", "loss"]
    top_weaknesses: List[str] = field(default_factory=list)
    concepts_practiced: List[str] = field(default_factory=list)
    best_moments: List[Dict] = field(default_factory=list)
    recurring_mistakes: List[Dict] = field(default_factory=list)
    current_focus: Optional[str] = None
    streak_type: Optional[str] = None  # "winning", "losing", None
    streak_count: int = 0


@dataclass
class CurriculumPlan:
    """Weekly training plan based on weaknesses."""
    focus_area: str
    reason: str
    exercises: List[Dict]
    target_games: int
    target_puzzles: int
    concepts_to_practice: List[str]
    estimated_sessions: int
    motivation_message: str


@dataclass
class EmotionalResponse:
    """Response adapted to emotional state."""
    base_message: str
    emotional_prefix: str
    emotional_suffix: str
    tone: str
    should_offer_break: bool = False
    encouragement_level: str = "normal"  # low, normal, high


class HumanCoachService:
    """
    Makes the coach feel human through memory, emotion, and Socratic teaching.
    """
    
    # Emotional tone adaptations
    EMOTIONAL_PREFIXES = {
        EmotionalState.FRUSTRATED: [
            "I know it's tough right now, but",
            "Take a breath.",
            "Chess is hard - that's why we practice.",
            "Don't be too hard on yourself.",
        ],
        EmotionalState.TILTED: [
            "Hey, let's slow down a bit.",
            "Sometimes stepping back helps see the board better.",
            "I've noticed you're moving quickly - take your time.",
            "Let's reset and focus on one thing.",
        ],
        EmotionalState.CONFIDENT: [
            "You're playing well!",
            "Nice momentum!",
            "Keep that energy!",
            "Good form today!",
        ],
        EmotionalState.RUSHED: [
            "No need to rush.",
            "Take your time - there's no prize for speed.",
            "Slow down a bit.",
            "Quality over speed.",
        ],
        EmotionalState.UNCERTAIN: [
            "Trust your instincts.",
            "You know more than you think.",
            "Let's work through this together.",
            "Take your time to think.",
        ],
    }
    
    # Memory-based welcome messages
    WELCOME_WITH_MEMORY = [
        "Welcome back! Last time we worked on {focus}. Ready to continue?",
        "Good to see you again! You've been practicing {focus} - let's build on that.",
        "Hey! Remember our session on {focus}? Let's apply what we learned.",
        "Back for more! Your {focus} has been improving. Let's keep it going.",
    ]
    
    WELCOME_AFTER_WIN_STREAK = [
        "You're on fire! {streak_count} wins in a row. Let's keep the momentum!",
        "Great streak going! {streak_count} wins. Ready for a challenge?",
        "Impressive run! Let's see if we can learn something new while you're sharp.",
    ]
    
    WELCOME_AFTER_LOSS_STREAK = [
        "Tough stretch, but that's how we grow. Let's focus on one thing today.",
        "Losses are lessons. I've noticed a pattern we can work on together.",
        "Fresh start today! Let's take it slow and build confidence.",
    ]
    
    # Curriculum focus messages
    CURRICULUM_INTROS = {
        WeaknessCategory.TACTICS: "You're missing some tactical shots. This week, let's sharpen your pattern recognition.",
        WeaknessCategory.PIECE_SAFETY: "Pieces are getting left undefended. Let's build the habit of checking safety before each move.",
        WeaknessCategory.KING_SAFETY: "Your king has been a bit exposed. Time to focus on when to castle and keeping the king safe.",
        WeaknessCategory.PAWN_STRUCTURE: "Pawn structure is the skeleton of your position. Let's learn to keep it healthy.",
        WeaknessCategory.DEVELOPMENT: "Quick development wins games. Let's work on getting pieces out efficiently.",
        WeaknessCategory.ENDGAME: "Endgames are where games are won and lost. Let's build your technique.",
        WeaknessCategory.TIME_MANAGEMENT: "Time trouble is hurting your play. Let's work on making decisions faster.",
        WeaknessCategory.OPENINGS: "Openings set the tone. Let's build a reliable repertoire.",
    }
    
    def __init__(self, db, user_id: str, user_rating: int = 1200):
        """Initialize with database connection and user info."""
        self.db = db
        self.user_id = user_id
        self.user_rating = user_rating
        self.memory: Optional[CoachMemory] = None
        self.emotional_state = EmotionalState.NEUTRAL
        self._tone_calibration = self._get_tone_for_rating(user_rating)
    
    def _get_tone_for_rating(self, rating: int) -> Dict:
        """Get tone settings based on rating."""
        if rating < 1000:
            return {
                "warmth": "high",
                "complexity": "simple",
                "encouragement": "frequent",
                "technical_depth": "minimal"
            }
        elif rating < 1400:
            return {
                "warmth": "high",
                "complexity": "moderate",
                "encouragement": "regular",
                "technical_depth": "basic"
            }
        elif rating < 1800:
            return {
                "warmth": "moderate",
                "complexity": "detailed",
                "encouragement": "occasional",
                "technical_depth": "intermediate"
            }
        else:
            return {
                "warmth": "collegial",
                "complexity": "advanced",
                "encouragement": "minimal",
                "technical_depth": "deep"
            }
    
    async def load_memory(self) -> CoachMemory:
        """Load coach's memory of this player from database."""
        if self.memory:
            return self.memory
        
        # Get session history
        sessions = await self.db.coach_sessions.find(
            {"user_id": self.user_id, "status": "completed"},
            {"_id": 0, "result": 1, "created_at": 1, "concepts_taught": 1, "user_color": 1}
        ).sort("created_at", -1).limit(20).to_list(20)
        
        # Get weakness analysis
        weakness_doc = await self.db.user_weaknesses.find_one(
            {"user_id": self.user_id},
            {"_id": 0}
        )
        
        # Get focus lock if active
        focus_lock = await self.db.focus_locks.find_one(
            {"user_id": self.user_id, "active": True},
            {"_id": 0}
        )
        
        # Build memory
        memory = CoachMemory()
        memory.total_sessions = len(sessions)
        
        if sessions:
            memory.last_session_date = sessions[0].get("created_at", "")
            memory.recent_results = [s.get("result", "unknown") for s in sessions[:5]]
            
            # Detect streak
            if memory.recent_results:
                first_result = memory.recent_results[0]
                streak = 1
                for r in memory.recent_results[1:]:
                    if r == first_result:
                        streak += 1
                    else:
                        break
                if streak >= 2 and first_result in ["win", "loss"]:
                    memory.streak_type = "winning" if first_result == "win" else "losing"
                    memory.streak_count = streak
            
            # Collect concepts practiced
            for s in sessions[:10]:
                concepts = s.get("concepts_taught", [])
                memory.concepts_practiced.extend(concepts)
            memory.concepts_practiced = list(set(memory.concepts_practiced))[:10]
        
        if weakness_doc:
            memory.top_weaknesses = weakness_doc.get("top_weaknesses", [])[:5]
            memory.recurring_mistakes = weakness_doc.get("recurring_patterns", [])[:3]
        
        if focus_lock:
            memory.current_focus = focus_lock.get("focus_type")
        
        self.memory = memory
        return memory
    
    def detect_emotional_state(
        self,
        recent_results: List[str] = None,
        avg_move_time: float = 0,
        blunders_this_game: int = 0,
        time_since_last_move: float = 0
    ) -> EmotionalState:
        """
        Detect player's emotional state based on various signals.
        
        Signals:
        - Recent results (win/loss streak)
        - Move timing (rushing vs overthinking)
        - Blunder frequency this game
        - Time between moves
        """
        if recent_results is None:
            recent_results = self.memory.recent_results if self.memory else []
        
        # Check for tilt (multiple blunders in current game)
        if blunders_this_game >= 3:
            self.emotional_state = EmotionalState.TILTED
            return self.emotional_state
        
        # Check for rushing
        if avg_move_time > 0 and avg_move_time < 5:  # Less than 5 seconds average
            self.emotional_state = EmotionalState.RUSHED
            return self.emotional_state
        
        # Check for uncertainty (very long thinks)
        if time_since_last_move > 60:  # Over a minute on one move
            self.emotional_state = EmotionalState.UNCERTAIN
            return self.emotional_state
        
        # Check loss streak (frustration)
        if recent_results:
            losses_in_row = 0
            for r in recent_results:
                if r == "loss":
                    losses_in_row += 1
                else:
                    break
            if losses_in_row >= 3:
                self.emotional_state = EmotionalState.FRUSTRATED
                return self.emotional_state
            
            # Check win streak (confidence)
            wins_in_row = 0
            for r in recent_results:
                if r == "win":
                    wins_in_row += 1
                else:
                    break
            if wins_in_row >= 3:
                self.emotional_state = EmotionalState.CONFIDENT
                return self.emotional_state
        
        # Default: focused or neutral
        if avg_move_time > 15 and avg_move_time < 45:
            self.emotional_state = EmotionalState.FOCUSED
        else:
            self.emotional_state = EmotionalState.NEUTRAL
        
        return self.emotional_state
    
    async def get_welcome_message(self) -> str:
        """
        Generate a personalized welcome message based on memory.
        
        Shows the coach remembers:
        - Last session and what was practiced
        - Recent results and streaks
        - Current focus area
        """
        memory = await self.load_memory()
        
        # First-time player
        if memory.total_sessions == 0:
            return (
                "Welcome! I'm your chess coach. I'll help you improve by asking questions "
                "and guiding you to discover patterns yourself. Let's start!"
            )
        
        # Returning player with streak
        if memory.streak_type == "winning" and memory.streak_count >= 3:
            template = random.choice(self.WELCOME_AFTER_WIN_STREAK)
            return template.format(streak_count=memory.streak_count)
        
        if memory.streak_type == "losing" and memory.streak_count >= 3:
            return random.choice(self.WELCOME_AFTER_LOSS_STREAK)
        
        # Returning player with focus area
        if memory.current_focus:
            template = random.choice(self.WELCOME_WITH_MEMORY)
            return template.format(focus=memory.current_focus.replace("_", " "))
        
        # Returning player - mention recent concepts
        if memory.concepts_practiced:
            recent_concept = random.choice(memory.concepts_practiced[:3])
            return f"Good to see you again! Last time we practiced {recent_concept}. Ready to build on that?"
        
        # Generic returning player
        return f"Welcome back! You've played {memory.total_sessions} sessions with me. Let's make this one count!"
    
    async def get_socratic_mistake_response(
        self,
        fen: str,
        move_played: str,
        best_move: str,
        eval_loss: float,
        position_type: str = "blunder"
    ) -> Dict:
        """
        Get a Socratic response to a mistake - NEVER give the answer first.
        
        Returns:
            Dict with:
            - message: The Socratic question/response
            - dialogue_id: For continuing the dialogue
            - expects_response: True (waiting for student input)
            - emotional_adaptation: How message was adapted for emotion
        """
        from services.socratic_engine import create_socratic_dialogue
        
        # Start Socratic dialogue
        context, opening_question = create_socratic_dialogue(
            fen=fen,
            move_played=move_played,
            best_move=best_move,
            eval_loss=eval_loss,
            position_type=position_type,
            user_rating=self.user_rating
        )
        
        # Adapt message for emotional state
        message = opening_question.message
        emotional_prefix = ""
        
        if self.emotional_state in self.EMOTIONAL_PREFIXES:
            emotional_prefix = random.choice(self.EMOTIONAL_PREFIXES[self.emotional_state])
            message = f"{emotional_prefix} {message}"
        
        # Check for recurring mistake pattern
        memory = await self.load_memory()
        pattern_connection = None
        
        if memory.recurring_mistakes:
            # Check if this mistake type matches a recurring pattern
            for pattern in memory.recurring_mistakes:
                if pattern.get("type") == position_type:
                    pattern_connection = (
                        "This reminds me of something we've seen before. "
                        "Do you remember the pattern?"
                    )
                    break
        
        return {
            "message": message,
            "dialogue_id": context.dialogue_id,
            "state": opening_question.state.value,
            "expects_response": opening_question.expects_response,
            "response_type": opening_question.response_type,
            "emotional_state": self.emotional_state.value,
            "emotional_adaptation": emotional_prefix,
            "pattern_connection": pattern_connection,
            "context": {
                "fen": fen,
                "move_played": move_played,
                "best_move": best_move,
                "hints_given": 0
            }
        }
    
    async def generate_weekly_curriculum(self) -> CurriculumPlan:
        """
        Generate a progressive training plan based on weaknesses.
        
        Analyzes:
        - Recent game patterns
        - Identified weaknesses
        - What's been practiced already
        - Current skill level
        
        Returns a focused plan for the week.
        """
        # Load memory for context (used for emotional state adaptation)
        await self.load_memory()
        
        # Get weakness data
        weakness_doc = await self.db.user_weaknesses.find_one(
            {"user_id": self.user_id},
            {"_id": 0}
        )
        
        # Determine focus area
        focus_area = WeaknessCategory.TACTICS  # Default
        
        if weakness_doc and weakness_doc.get("top_weaknesses"):
            top_weakness = weakness_doc["top_weaknesses"][0]
            # Map to category
            weakness_mapping = {
                "missed_tactic": WeaknessCategory.TACTICS,
                "piece_safety": WeaknessCategory.PIECE_SAFETY,
                "hanging_piece": WeaknessCategory.PIECE_SAFETY,
                "king_exposed": WeaknessCategory.KING_SAFETY,
                "bad_pawn_structure": WeaknessCategory.PAWN_STRUCTURE,
                "slow_development": WeaknessCategory.DEVELOPMENT,
                "endgame_error": WeaknessCategory.ENDGAME,
                "time_trouble": WeaknessCategory.TIME_MANAGEMENT,
                "opening_mistake": WeaknessCategory.OPENINGS,
            }
            focus_area = weakness_mapping.get(top_weakness, WeaknessCategory.TACTICS)
        
        # Generate exercises based on focus
        exercises = self._generate_exercises_for_focus(focus_area)
        
        # Create motivation message based on emotional state
        if self.emotional_state == EmotionalState.FRUSTRATED:
            motivation = "Small steps lead to big improvements. Let's focus on just one thing this week."
        elif self.emotional_state == EmotionalState.CONFIDENT:
            motivation = "You're ready for a challenge! This week's focus will push you to the next level."
        else:
            motivation = "Consistent practice beats intense cramming. A little every day adds up!"
        
        # Create curriculum
        curriculum = CurriculumPlan(
            focus_area=focus_area.value,
            reason=self.CURRICULUM_INTROS.get(focus_area, "Let's work on improving your overall play."),
            exercises=exercises,
            target_games=5,
            target_puzzles=20,
            concepts_to_practice=self._get_concepts_for_focus(focus_area),
            estimated_sessions=4,
            motivation_message=motivation
        )
        
        return curriculum
    
    def _generate_exercises_for_focus(self, focus: WeaknessCategory) -> List[Dict]:
        """Generate specific exercises for the focus area."""
        exercises_db = {
            WeaknessCategory.TACTICS: [
                {"type": "puzzle", "theme": "fork", "count": 5, "description": "Find the fork!"},
                {"type": "puzzle", "theme": "pin", "count": 5, "description": "Spot the pin pattern"},
                {"type": "puzzle", "theme": "discovered_attack", "count": 5, "description": "Unleash the discovered attack"},
                {"type": "game", "focus": "look_for_tactics", "description": "Play a game focusing on tactical shots"},
            ],
            WeaknessCategory.PIECE_SAFETY: [
                {"type": "drill", "name": "piece_safety_check", "description": "Before each move, check: are all my pieces safe?"},
                {"type": "puzzle", "theme": "hanging_piece", "count": 10, "description": "Find the undefended piece"},
                {"type": "game", "focus": "no_hanging_pieces", "description": "Play a game with zero hanging pieces"},
            ],
            WeaknessCategory.KING_SAFETY: [
                {"type": "study", "name": "when_to_castle", "description": "Learn the right time to castle"},
                {"type": "puzzle", "theme": "king_attack", "count": 10, "description": "Recognize king attacks"},
                {"type": "game", "focus": "castle_early", "description": "Practice castling by move 10"},
            ],
            WeaknessCategory.PAWN_STRUCTURE: [
                {"type": "study", "name": "pawn_structure_basics", "description": "Learn isolated, doubled, and passed pawns"},
                {"type": "puzzle", "theme": "pawn_endgame", "count": 10, "description": "Practice pawn structures"},
                {"type": "game", "focus": "healthy_pawns", "description": "Avoid creating weak pawns"},
            ],
            WeaknessCategory.DEVELOPMENT: [
                {"type": "drill", "name": "development_count", "description": "Count developed pieces each move"},
                {"type": "study", "name": "opening_principles", "description": "Review development principles"},
                {"type": "game", "focus": "all_pieces_out_by_10", "description": "Develop all minor pieces by move 10"},
            ],
            WeaknessCategory.ENDGAME: [
                {"type": "study", "name": "basic_endgames", "description": "Learn K+Q vs K, K+R vs K"},
                {"type": "puzzle", "theme": "endgame", "count": 15, "description": "Practice endgame technique"},
                {"type": "drill", "name": "king_activity", "description": "In endgames, activate your king!"},
            ],
            WeaknessCategory.TIME_MANAGEMENT: [
                {"type": "drill", "name": "move_timing", "description": "Spend max 30 seconds on simple moves"},
                {"type": "game", "focus": "time_discipline", "description": "Play with strict time allocation"},
                {"type": "study", "name": "quick_patterns", "description": "Learn to recognize patterns instantly"},
            ],
            WeaknessCategory.OPENINGS: [
                {"type": "study", "name": "one_opening", "description": "Master one opening for white and black"},
                {"type": "drill", "name": "opening_moves", "description": "Practice your opening moves until automatic"},
                {"type": "game", "focus": "stick_to_repertoire", "description": "Play your prepared opening"},
            ],
        }
        
        return exercises_db.get(focus, exercises_db[WeaknessCategory.TACTICS])
    
    def _get_concepts_for_focus(self, focus: WeaknessCategory) -> List[str]:
        """Get concepts to practice for the focus area."""
        concepts_db = {
            WeaknessCategory.TACTICS: ["pattern recognition", "calculation", "forcing moves"],
            WeaknessCategory.PIECE_SAFETY: ["piece coordination", "defense", "threats"],
            WeaknessCategory.KING_SAFETY: ["castling", "pawn shield", "attack patterns"],
            WeaknessCategory.PAWN_STRUCTURE: ["pawn chains", "weak squares", "pawn breaks"],
            WeaknessCategory.DEVELOPMENT: ["piece activity", "center control", "tempo"],
            WeaknessCategory.ENDGAME: ["king activity", "pawn promotion", "technique"],
            WeaknessCategory.TIME_MANAGEMENT: ["intuition", "pattern recognition", "decisiveness"],
            WeaknessCategory.OPENINGS: ["theory", "plans", "typical middlegames"],
        }
        
        return concepts_db.get(focus, ["general improvement"])
    
    def adapt_message_for_emotion(self, base_message: str) -> EmotionalResponse:
        """
        Adapt any message based on the detected emotional state.
        
        Adds appropriate prefix/suffix and adjusts tone.
        """
        prefix = ""
        suffix = ""
        should_offer_break = False
        encouragement_level = "normal"
        
        if self.emotional_state == EmotionalState.FRUSTRATED:
            prefix = random.choice(self.EMOTIONAL_PREFIXES[EmotionalState.FRUSTRATED])
            suffix = "You've got this."
            encouragement_level = "high"
            
        elif self.emotional_state == EmotionalState.TILTED:
            prefix = random.choice(self.EMOTIONAL_PREFIXES[EmotionalState.TILTED])
            suffix = "Want to take a quick break and come back fresh?"
            should_offer_break = True
            encouragement_level = "high"
            
        elif self.emotional_state == EmotionalState.CONFIDENT:
            prefix = random.choice(self.EMOTIONAL_PREFIXES[EmotionalState.CONFIDENT])
            suffix = ""
            encouragement_level = "low"
            
        elif self.emotional_state == EmotionalState.RUSHED:
            prefix = random.choice(self.EMOTIONAL_PREFIXES[EmotionalState.RUSHED])
            suffix = "The position will wait for you."
            encouragement_level = "normal"
            
        elif self.emotional_state == EmotionalState.UNCERTAIN:
            prefix = random.choice(self.EMOTIONAL_PREFIXES[EmotionalState.UNCERTAIN])
            suffix = "What's your gut telling you?"
            encouragement_level = "high"
        
        return EmotionalResponse(
            base_message=base_message,
            emotional_prefix=prefix,
            emotional_suffix=suffix,
            tone=self.emotional_state.value,
            should_offer_break=should_offer_break,
            encouragement_level=encouragement_level
        )
    
    async def surface_relevant_memory(
        self,
        current_fen: str = "",
        current_theme: str = "",
        current_opening: str = ""
    ) -> Optional[str]:
        """
        Surface relevant memory from past sessions.
        
        Looks for:
        - Similar positions played before
        - Same opening
        - Same tactical theme
        - Recent lessons related to current position
        """
        memory = await self.load_memory()
        
        # Check for opening connection
        if current_opening and memory.concepts_practiced:
            for concept in memory.concepts_practiced:
                if current_opening.lower() in concept.lower():
                    return f"Remember our work on the {current_opening}? This is a great chance to apply what we learned!"
        
        # Check for theme connection
        if current_theme and memory.recurring_mistakes:
            for mistake in memory.recurring_mistakes:
                if mistake.get("type") == current_theme:
                    return f"Watch out - {current_theme.replace('_', ' ')} is something we've been working on. Take your time here."
        
        # Check for recent concepts
        if memory.concepts_practiced and len(memory.concepts_practiced) > 0:
            recent_concept = memory.concepts_practiced[0]
            # Randomly surface memory (not every time - would be annoying)
            if random.random() < 0.3:  # 30% chance
                return f"By the way, remember when we talked about {recent_concept}? Keep that in mind."
        
        return None
    
    async def get_session_summary_with_memory(
        self,
        session_result: str,
        concepts_covered: List[str],
        mistakes_made: int,
        good_moves: int
    ) -> str:
        """
        Generate end-of-session summary that connects to long-term progress.
        
        Shows:
        - What was accomplished this session
        - How it connects to overall progress
        - What to focus on next
        """
        memory = await self.load_memory()
        
        parts = []
        
        # Result acknowledgment
        if session_result == "win":
            parts.append("Great win!")
        elif session_result == "loss":
            parts.append("Tough game, but lots to learn.")
        else:
            parts.append("Solid draw!")
        
        # Session highlights
        if good_moves > 0:
            parts.append(f"You found {good_moves} strong move{'s' if good_moves > 1 else ''} today.")
        
        if mistakes_made > 0:
            parts.append(f"We found {mistakes_made} learning moment{'s' if mistakes_made > 1 else ''} to work on.")
        
        # Concepts
        if concepts_covered:
            parts.append(f"Today we practiced: {', '.join(concepts_covered[:3])}.")
        
        # Long-term connection
        if memory.total_sessions > 5:
            parts.append(f"That's session #{memory.total_sessions + 1} together!")
            
            if memory.top_weaknesses:
                focus = memory.top_weaknesses[0].replace("_", " ")
                parts.append(f"Keep focusing on {focus} - you're making progress!")
        
        # Encouragement
        if self.emotional_state == EmotionalState.FRUSTRATED:
            parts.append("Remember: every game makes you stronger, win or lose.")
        elif self.emotional_state == EmotionalState.CONFIDENT:
            parts.append("Ride this momentum into your next session!")
        
        return " ".join(parts)


# ============================================
# CONVENIENCE FUNCTIONS
# ============================================

async def create_human_coach(db, user_id: str, user_rating: int = 1200) -> HumanCoachService:
    """Create and initialize a human coach instance."""
    coach = HumanCoachService(db, user_id, user_rating)
    await coach.load_memory()
    return coach


async def get_welcome_with_memory(db, user_id: str, user_rating: int = 1200) -> str:
    """Quick function to get a memory-aware welcome message."""
    coach = await create_human_coach(db, user_id, user_rating)
    return await coach.get_welcome_message()


async def get_socratic_response(
    db,
    user_id: str,
    user_rating: int,
    fen: str,
    move_played: str,
    best_move: str,
    eval_loss: float,
    emotional_context: Dict = None
) -> Dict:
    """Get a Socratic response adapted for the user's emotional state."""
    coach = await create_human_coach(db, user_id, user_rating)
    
    # Update emotional state if context provided
    if emotional_context:
        coach.detect_emotional_state(
            recent_results=emotional_context.get("recent_results"),
            avg_move_time=emotional_context.get("avg_move_time", 0),
            blunders_this_game=emotional_context.get("blunders_this_game", 0),
            time_since_last_move=emotional_context.get("time_since_last_move", 0)
        )
    
    return await coach.get_socratic_mistake_response(
        fen=fen,
        move_played=move_played,
        best_move=best_move,
        eval_loss=eval_loss
    )
