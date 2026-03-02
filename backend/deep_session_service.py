"""
Deep Coaching Session Service

Simulates a real coaching class - NOT after every game.
Triggered by: time (weekly), pattern threshold, or manual action.

Flow:
1. Pattern Summary (Authority)
2. Guided Reflection (Discovery) 
3. Mirror Back Thinking
4. Structured Teaching (A Mode)
5. Assignment (Trainer Mode)
6. Commitment Anchor

Tone: Calm authority, slight firmness. Indian coaching rhythm.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone, timedelta
from enum import Enum
import random


class DeepSessionTrigger(str, Enum):
    """Why the deep session was triggered"""
    SCHEDULED = "scheduled"          # Weekly timer
    GAME_THRESHOLD = "game_threshold"  # 8+ games since last
    NO_IMPROVEMENT = "no_improvement"  # High confidence, no progress
    REGRESSION = "regression"          # Severe decline
    MANUAL = "manual"                  # User requested


class AssignmentType(str, Enum):
    """Type of assignment given at end"""
    PUZZLES = "puzzles"
    REPLAY_MOMENTS = "replay_moments"
    THREAT_SCAN_DRILL = "threat_scan_drill"
    CALCULATION_DRILL = "calculation_drill"


@dataclass
class DeepSession:
    """A deep coaching session record"""
    session_id: str
    user_id: str
    theme: str
    triggered_by: DeepSessionTrigger
    games_considered: int
    reflection_answer: Optional[str] = None
    summary_snapshot: Optional[Dict] = None
    assignment_type: Optional[AssignmentType] = None
    assignment_data: Optional[Dict] = None
    micro_rule_assigned: Optional[str] = None
    completed: bool = False
    current_step: int = 1  # 1-6
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict:
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "theme": self.theme,
            "triggered_by": self.triggered_by.value,
            "games_considered": self.games_considered,
            "reflection_answer": self.reflection_answer,
            "summary_snapshot": self.summary_snapshot,
            "assignment_type": self.assignment_type.value if self.assignment_type else None,
            "assignment_data": self.assignment_data,
            "micro_rule_assigned": self.micro_rule_assigned,
            "completed": self.completed,
            "current_step": self.current_step,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'DeepSession':
        return cls(
            session_id=data["session_id"],
            user_id=data["user_id"],
            theme=data["theme"],
            triggered_by=DeepSessionTrigger(data["triggered_by"]),
            games_considered=data["games_considered"],
            reflection_answer=data.get("reflection_answer"),
            summary_snapshot=data.get("summary_snapshot"),
            assignment_type=AssignmentType(data["assignment_type"]) if data.get("assignment_type") else None,
            assignment_data=data.get("assignment_data"),
            micro_rule_assigned=data.get("micro_rule_assigned"),
            completed=data.get("completed", False),
            current_step=data.get("current_step", 1),
            created_at=datetime.fromisoformat(data["created_at"]) if isinstance(data.get("created_at"), str) else datetime.now(timezone.utc),
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None
        )


# ============================================================================
# REFLECTION QUESTIONS BY THEME
# ============================================================================

REFLECTION_QUESTIONS = {
    "ThreatVerification": {
        "question": "When you attack, what usually feels most important to you?",
        "options": [
            {"id": "momentum", "text": "Maintaining momentum"},
            {"id": "material", "text": "Winning material quickly"},
            {"id": "counterplay", "text": "Avoiding counterplay"},
            {"id": "unaware", "text": "I don't consciously think about opponent threats"}
        ],
        "mirror_responses": {
            "momentum": "That makes sense. You focus strongly on momentum. But in your games, opponent forcing moves are often overlooked during these attacking moments.",
            "material": "Understandable. Material is concrete. But when hunting for gains, their threats tend to slip past your radar.",
            "counterplay": "Good instinct. Yet the data shows counterplay often catches you anyway. The scan isn't happening consistently.",
            "unaware": "That's honest. And that's exactly what the data confirms. Building this habit will change your results."
        }
    },
    "CalculationDepth": {
        "question": "When you see a promising move, how do you usually decide?",
        "options": [
            {"id": "intuition", "text": "I trust my gut feeling"},
            {"id": "one_move", "text": "I check one move ahead"},
            {"id": "full_calc", "text": "I try to calculate the full line"},
            {"id": "time_pressure", "text": "I often don't have time to calculate"}
        ],
        "mirror_responses": {
            "intuition": "Intuition is valuable. But in your critical moments, one more move of calculation would have changed the outcome.",
            "one_move": "One move is a start. The pattern shows that your opponents' second reply is where things go wrong.",
            "full_calc": "You try to calculate deeply. But the data suggests the calculation stops one move too early in key moments.",
            "time_pressure": "Time pressure is real. But these mistakes happen even when time is available. It's the habit, not the clock."
        }
    },
    "ConversionDiscipline": {
        "question": "When you're winning, what's your typical approach?",
        "options": [
            {"id": "attack", "text": "Push for quick checkmate"},
            {"id": "simplify", "text": "Trade pieces and simplify"},
            {"id": "improve", "text": "Keep improving my position"},
            {"id": "nervous", "text": "I get nervous and sometimes rush"}
        ],
        "mirror_responses": {
            "attack": "Attacking spirit is good. But your games show that winning positions often collapse during these attacks.",
            "simplify": "Simplification is correct technique. But the timing of when to simplify seems to be the issue.",
            "improve": "Patience is wise. Yet the data shows impatience creeps in when victory feels close.",
            "nervous": "That honesty helps. The pattern confirms: when ahead, something shifts and accuracy drops."
        }
    },
    "PieceSafety": {
        "question": "Before moving a piece, what do you typically check?",
        "options": [
            {"id": "destination", "text": "Where it's going"},
            {"id": "attack", "text": "What it will attack"},
            {"id": "safety", "text": "If it will be safe there"},
            {"id": "nothing", "text": "I don't have a consistent check"}
        ],
        "mirror_responses": {
            "destination": "Destination matters. But pieces keep landing on unsafe squares. The safety check is missing.",
            "attack": "Attacking intent is good. But the data shows pieces are being lost while hunting.",
            "safety": "Safety awareness exists. But it's not triggering consistently in your games.",
            "nothing": "That's the pattern we see. Building a simple safety habit will prevent most of these losses."
        }
    }
}

# Default for themes without specific questions
DEFAULT_REFLECTION = {
    "question": "When you make a mistake, what usually happens?",
    "options": [
        {"id": "rush", "text": "I moved too quickly"},
        {"id": "missed", "text": "I missed something"},
        {"id": "plan", "text": "I had a wrong plan"},
        {"id": "unsure", "text": "I'm not sure what went wrong"}
    ],
    "mirror_responses": {
        "rush": "Speed is often the culprit. The data confirms: your mistakes cluster when pace increases.",
        "missed": "Missing things is human. The pattern shows a specific blind spot we can work on.",
        "plan": "Strategic confusion happens. But looking at your games, it's more tactical than strategic.",
        "unsure": "That uncertainty is common. The analysis gives us clarity on what to focus on."
    }
}

# ============================================================================
# TEACHING CONTENT BY THEME
# ============================================================================

TEACHING_CONTENT = {
    "ThreatVerification": {
        "principle": "Before committing to any action, scan opponent's forcing moves: checks, captures, threats.",
        "rule": "Before YOUR move, ask: What do THEY want to do?",
        "explanation": "In this position, before attacking, you needed to check forcing replies. The opponent had a discovered attack that changed everything."
    },
    "CalculationDepth": {
        "principle": "Every candidate move deserves at least one reply considered.",
        "rule": "If you see a good move, look for a better one. Then check their best response.",
        "explanation": "Here, the first move looked strong. But calculating one move deeper would have revealed the refutation."
    },
    "ConversionDiscipline": {
        "principle": "When winning, safety first. No need to find the fastest win.",
        "rule": "When ahead, trade pieces not pawns. Simplify, don't complicate.",
        "explanation": "You had a winning position. The attacking move felt natural, but a simple exchange would have sealed the game."
    },
    "PieceSafety": {
        "principle": "Every piece move must pass the safety test: Is it protected? Can it be attacked?",
        "rule": "Before moving, count: attackers vs defenders on the destination square.",
        "explanation": "This piece landed on an unsafe square. One quick count would have shown the danger."
    }
}

DEFAULT_TEACHING = {
    "principle": "Slow down at critical moments. The game is decided in 3-4 key positions.",
    "rule": "When the position feels critical, take an extra 30 seconds.",
    "explanation": "This was a turning point. A bit more care here would have changed the outcome."
}

# ============================================================================
# MICRO RULES BY THEME (for commitment anchor)
# ============================================================================

MICRO_RULES_BY_THEME = {
    "ThreatVerification": [
        "Before committing, scan their forcing moves",
        "When attacking, pause to check what they threaten",
        "Ask 'What do they want?' before every move"
    ],
    "CalculationDepth": [
        "If it looks good, calculate one move deeper",
        "Check their best reply before you commit",
        "Trust calculation over intuition in critical moments"
    ],
    "ConversionDiscipline": [
        "When ahead, simplify rather than attack",
        "Pause before committing when victory feels close",
        "Trade pieces, not pawns, when winning"
    ],
    "PieceSafety": [
        "Count attackers vs defenders before moving",
        "Check if the piece is safe on its new square",
        "If in doubt, don't move there"
    ]
}


class DeepSessionService:
    """
    Service for managing Deep Coaching Sessions.
    
    Implements the weekly coaching rhythm:
    - Trigger based on time/games/regression
    - 6-step guided flow
    - Updates CoachState at completion
    """
    
    # Configuration
    MIN_DAYS_BETWEEN_SESSIONS = 7
    MIN_GAMES_FOR_TRIGGER = 8
    REGRESSION_THRESHOLD = 0.4  # 40% increase in theme mistakes
    
    def __init__(self, db):
        self.db = db
    
    async def should_trigger_deep_session(self, user_id: str) -> Dict[str, Any]:
        """
        Check if a deep session should be triggered.
        
        Returns:
        - should_trigger: bool
        - reason: DeepSessionTrigger
        - message: str (for UI banner)
        """
        from coach_state_service import CoachStateService
        
        coach_service = CoachStateService(self.db)
        coach_state = await coach_service.get_coach_state(user_id)
        
        if not coach_state:
            return {"should_trigger": False, "reason": None, "message": None}
        
        now = datetime.now(timezone.utc)
        
        # Check if already has an incomplete session
        active_session = await self.get_active_session(user_id)
        if active_session and not active_session.completed:
            return {
                "should_trigger": True,
                "reason": "resume",
                "message": "You have an unfinished coaching review.",
                "session_id": active_session.session_id
            }
        
        # Rule 1: Scheduled (weekly)
        if coach_state.next_deep_session_due_at:
            due_at = coach_state.next_deep_session_due_at
            if isinstance(due_at, str):
                due_at = datetime.fromisoformat(due_at)
            if now >= due_at:
                return {
                    "should_trigger": True,
                    "reason": DeepSessionTrigger.SCHEDULED,
                    "message": "It's time for your weekly coaching review."
                }
        
        # Rule 2: Game threshold (8+ games since last session)
        games_since = await self._count_games_since_last_session(user_id, coach_state)
        if games_since >= self.MIN_GAMES_FOR_TRIGGER:
            return {
                "should_trigger": True,
                "reason": DeepSessionTrigger.GAME_THRESHOLD,
                "message": f"You've played {games_since} games. Let's review your progress."
            }
        
        # Rule 3: High confidence but no improvement
        if coach_state.theme_confidence > 0.7:
            improvement = coach_state.theme_improvement_delta or {}
            if improvement.get("trend") == "stable" and improvement.get("games_analyzed", 0) >= 6:
                return {
                    "should_trigger": True,
                    "reason": DeepSessionTrigger.NO_IMPROVEMENT,
                    "message": "Your focus area needs attention. Let's dig deeper."
                }
        
        # Rule 4: Severe regression
        improvement = coach_state.theme_improvement_delta or {}
        if improvement.get("trend") == "declining":
            before = improvement.get("mistakes_before", 0)
            after = improvement.get("mistakes_after", 0)
            if before > 0 and (after - before) / before > self.REGRESSION_THRESHOLD:
                return {
                    "should_trigger": True,
                    "reason": DeepSessionTrigger.REGRESSION,
                    "message": "We need to address a pattern that's getting worse."
                }
        
        # No trigger
        days_until_due = 0
        if coach_state.next_deep_session_due_at:
            due = coach_state.next_deep_session_due_at
            if isinstance(due, str):
                due = datetime.fromisoformat(due)
            days_until_due = (due - now).days
        
        return {
            "should_trigger": False,
            "reason": None,
            "message": None,
            "days_until_due": max(0, days_until_due),
            "games_since_last": games_since
        }
    
    async def _count_games_since_last_session(self, user_id: str, coach_state) -> int:
        """Count analyzed games since last deep session"""
        last_session = coach_state.last_deep_session_at
        if not last_session:
            # No previous session - count all games
            count = await self.db.game_analyses.count_documents({"user_id": user_id})
            return count
        
        if isinstance(last_session, str):
            last_session = datetime.fromisoformat(last_session)
        
        count = await self.db.game_analyses.count_documents({
            "user_id": user_id,
            "analyzed_at": {"$gt": last_session.isoformat()}
        })
        return count
    
    async def start_session(
        self, 
        user_id: str, 
        trigger: DeepSessionTrigger = DeepSessionTrigger.MANUAL
    ) -> DeepSession:
        """
        Start a new deep coaching session.
        """
        import uuid
        from coach_state_service import CoachStateService
        
        coach_service = CoachStateService(self.db)
        coach_state = await coach_service.get_coach_state(user_id)
        
        if not coach_state:
            coach_state = await coach_service.initialize_coach_state(user_id)
        
        # Build summary snapshot
        summary = await self._build_summary_snapshot(user_id, coach_state)
        
        session = DeepSession(
            session_id=str(uuid.uuid4()),
            user_id=user_id,
            theme=coach_state.active_theme.value,
            triggered_by=trigger,
            games_considered=summary.get("games_analyzed", 0),
            summary_snapshot=summary,
            current_step=1
        )
        
        await self.db.deep_sessions.insert_one(session.to_dict())
        return session
    
    async def _build_summary_snapshot(self, user_id: str, coach_state) -> Dict:
        """Build the pattern summary for Screen 1"""
        from coach_state_service import CoachStateService
        
        service = CoachStateService(self.db)
        stats = await service.get_theme_improvement_stats(user_id, coach_state.active_theme)
        
        # Get recent game summaries for this theme
        cursor = self.db.game_coach_summaries.find(
            {"user_id": user_id}
        ).sort("generated_at", -1).limit(10)
        
        summaries = []
        theme_failures = 0
        when_ahead_failures = 0
        
        async for doc in cursor:
            summaries.append(doc)
            if doc.get("ties_to_active_theme"):
                theme_failures += 1
            # Check if failure when ahead (would need more data in summary)
        
        # Build observations
        observations = []
        games_analyzed = len(summaries)
        
        if theme_failures > 0:
            observations.append(
                f"Across your last {games_analyzed} games, {coach_state.active_theme.value.replace('_', ' ').lower()} "
                f"failed in {theme_failures} critical moments."
            )
        
        if stats.get("trend") == "declining":
            observations.append(
                f"This pattern is getting more frequent: {stats.get('mistakes_before', 0)} → {stats.get('mistakes_after', 0)} mistakes."
            )
        elif stats.get("trend") == "improving":
            observations.append(
                f"Good progress: mistakes dropped from {stats.get('mistakes_before', 0)} to {stats.get('mistakes_after', 0)}."
            )
        
        # Find a critical moment to reference
        critical_moment = None
        for s in summaries:
            if s.get("ties_to_active_theme") and s.get("primary_moment"):
                critical_moment = {
                    "game_id": s.get("game_id"),
                    "move_number": s["primary_moment"].get("move_number"),
                    "fen": s["primary_moment"].get("fen"),
                    "label": s["primary_moment"].get("label"),
                    "emotion_line": s.get("emotion_mirror_line")
                }
                break
        
        return {
            "games_analyzed": games_analyzed,
            "theme_failures": theme_failures,
            "observations": observations,
            "trend": stats.get("trend", "stable"),
            "critical_moment": critical_moment,
            "stats": stats
        }
    
    async def get_active_session(self, user_id: str) -> Optional[DeepSession]:
        """Get user's current active (incomplete) session"""
        doc = await self.db.deep_sessions.find_one({
            "user_id": user_id,
            "completed": False
        })
        if doc:
            doc.pop("_id", None)
            return DeepSession.from_dict(doc)
        return None
    
    async def get_session(self, session_id: str) -> Optional[DeepSession]:
        """Get session by ID"""
        doc = await self.db.deep_sessions.find_one({"session_id": session_id})
        if doc:
            doc.pop("_id", None)
            return DeepSession.from_dict(doc)
        return None
    
    async def update_session(self, session: DeepSession) -> None:
        """Update session in DB"""
        await self.db.deep_sessions.replace_one(
            {"session_id": session.session_id},
            session.to_dict()
        )
    
    def get_step_content(self, session: DeepSession, step: int) -> Dict[str, Any]:
        """
        Get content for a specific step.
        
        Steps:
        1. Pattern Summary
        2. Guided Reflection
        3. Mirror Back
        4. Structured Teaching
        5. Assignment
        6. Commitment Anchor
        """
        theme = session.theme
        
        if step == 1:
            return self._get_summary_content(session)
        elif step == 2:
            return self._get_reflection_content(theme)
        elif step == 3:
            return self._get_mirror_content(session)
        elif step == 4:
            return self._get_teaching_content(session)
        elif step == 5:
            return self._get_assignment_content(session)
        elif step == 6:
            return self._get_commitment_content(session)
        
        return {"error": "Invalid step"}
    
    def _get_summary_content(self, session: DeepSession) -> Dict:
        """Screen 1: Pattern Summary"""
        snapshot = session.summary_snapshot or {}
        theme_display = session.theme.replace("_", " ")
        
        return {
            "step": 1,
            "title": "Let's review your recent games.",
            "theme": theme_display,
            "observations": snapshot.get("observations", [
                f"We've been tracking your {theme_display.lower()} pattern.",
                "Let's look at what the data shows."
            ]),
            "games_analyzed": snapshot.get("games_analyzed", 0),
            "trend": snapshot.get("trend", "stable"),
            "critical_moment": snapshot.get("critical_moment"),
            "cta": "Continue"
        }
    
    def _get_reflection_content(self, theme: str) -> Dict:
        """Screen 2: Guided Reflection"""
        reflection = REFLECTION_QUESTIONS.get(theme, DEFAULT_REFLECTION)
        
        return {
            "step": 2,
            "title": "A quick question",
            "question": reflection["question"],
            "options": reflection["options"],
            "instruction": "Select the option that feels most true.",
            "cta": "Continue"
        }
    
    def _get_mirror_content(self, session: DeepSession) -> Dict:
        """Screen 3: Mirror Back"""
        theme = session.theme
        answer = session.reflection_answer
        
        reflection = REFLECTION_QUESTIONS.get(theme, DEFAULT_REFLECTION)
        mirror_responses = reflection.get("mirror_responses", {})
        
        response = mirror_responses.get(answer, 
            "That's helpful context. The data aligns with what you described.")
        
        return {
            "step": 3,
            "title": "Here's what I see",
            "response": response,
            "cta": "Show Me"
        }
    
    def _get_teaching_content(self, session: DeepSession) -> Dict:
        """Screen 4: Structured Teaching"""
        theme = session.theme
        teaching = TEACHING_CONTENT.get(theme, DEFAULT_TEACHING)
        snapshot = session.summary_snapshot or {}
        critical = snapshot.get("critical_moment")
        
        return {
            "step": 4,
            "title": "The Key Principle",
            "principle": teaching["principle"],
            "rule": teaching["rule"],
            "explanation": teaching["explanation"],
            "position": critical,  # FEN + move for board display
            "cta": "Got It"
        }
    
    def _get_assignment_content(self, session: DeepSession) -> Dict:
        """Screen 5: Assignment"""
        theme = session.theme
        
        # Choose assignment type based on theme
        assignment_type = AssignmentType.PUZZLES
        assignment_text = "5 puzzles focused on this pattern"
        drill_duration = "3-5 mins"
        
        if theme == "ThreatVerification":
            assignment_type = AssignmentType.THREAT_SCAN_DRILL
            assignment_text = "Threat Scan Drill - find opponent threats"
            drill_duration = "3 mins"
        elif theme == "CalculationDepth":
            assignment_type = AssignmentType.CALCULATION_DRILL
            assignment_text = "Calculation Challenge - go one move deeper"
            drill_duration = "5 mins"
        elif theme == "ConversionDiscipline":
            assignment_type = AssignmentType.REPLAY_MOMENTS
            assignment_text = "Replay 2 winning positions - find the safe path"
            drill_duration = "4 mins"
        
        return {
            "step": 5,
            "title": "Your Focus Drill",
            "assignment_type": assignment_type.value,
            "assignment_text": assignment_text,
            "duration": drill_duration,
            "cta": "Start Focus Drill"
        }
    
    def _get_commitment_content(self, session: DeepSession) -> Dict:
        """Screen 6: Commitment Anchor"""
        theme = session.theme
        rules = MICRO_RULES_BY_THEME.get(theme, ["Slow down at critical moments"])
        
        # Pick a rule (prefer one not recently used)
        micro_rule = random.choice(rules)
        
        return {
            "step": 6,
            "title": "Your Focus for Next Games",
            "micro_rule": micro_rule,
            "message": f"For your next games: {micro_rule.lower()}.",
            "cta": "I'm Ready"
        }
    
    async def submit_reflection(self, session_id: str, answer: str) -> DeepSession:
        """Submit reflection answer and advance to step 3"""
        session = await self.get_session(session_id)
        if not session:
            raise ValueError("Session not found")
        
        session.reflection_answer = answer
        session.current_step = 3
        await self.update_session(session)
        return session
    
    async def advance_step(self, session_id: str) -> DeepSession:
        """Advance to next step"""
        session = await self.get_session(session_id)
        if not session:
            raise ValueError("Session not found")
        
        session.current_step = min(session.current_step + 1, 6)
        await self.update_session(session)
        return session
    
    async def complete_session(self, session_id: str) -> DeepSession:
        """
        Complete the deep session.
        
        - Marks session as completed
        - Updates CoachState with new micro rule
        - Sets next_deep_session_due_at
        """
        from coach_state_service import CoachStateService
        
        session = await self.get_session(session_id)
        if not session:
            raise ValueError("Session not found")
        
        # Get commitment content for the micro rule
        commitment = self._get_commitment_content(session)
        micro_rule = commitment["micro_rule"]
        
        # Mark session complete
        session.completed = True
        session.completed_at = datetime.now(timezone.utc)
        session.micro_rule_assigned = micro_rule
        
        # Get assignment info
        assignment = self._get_assignment_content(session)
        session.assignment_type = AssignmentType(assignment["assignment_type"])
        
        await self.update_session(session)
        
        # Update CoachState
        coach_service = CoachStateService(self.db)
        coach_state = await coach_service.get_coach_state(session.user_id)
        
        if coach_state:
            coach_state.last_deep_session_at = datetime.now(timezone.utc)
            coach_state.next_deep_session_due_at = datetime.now(timezone.utc) + timedelta(days=7)
            
            # Update micro rules - new one at front
            if micro_rule not in coach_state.micro_rules:
                coach_state.micro_rules.insert(0, micro_rule)
                coach_state.micro_rules = coach_state.micro_rules[:3]  # Keep max 3
            
            await coach_service.update_coach_state(coach_state)
        
        return session
    
    async def get_session_history(self, user_id: str, limit: int = 10) -> List[Dict]:
        """Get user's past deep sessions"""
        cursor = self.db.deep_sessions.find(
            {"user_id": user_id, "completed": True}
        ).sort("completed_at", -1).limit(limit)
        
        sessions = []
        async for doc in cursor:
            doc.pop("_id", None)
            sessions.append(doc)
        
        return sessions


async def check_post_session_improvement(db, user_id: str) -> Optional[Dict]:
    """
    Check if user improved after completing a deep session.
    
    If yes, returns message for Home page:
    "You handled threat verification better in your last game."
    """
    from coach_state_service import CoachStateService
    
    # Get last completed session
    last_session = await db.deep_sessions.find_one(
        {"user_id": user_id, "completed": True},
        sort=[("completed_at", -1)]
    )
    
    if not last_session:
        return None
    
    session_completed = last_session.get("completed_at")
    if isinstance(session_completed, str):
        session_completed = datetime.fromisoformat(session_completed)
    
    # Get games since session
    games_since = await db.game_coach_summaries.count_documents({
        "user_id": user_id,
        "generated_at": {"$gt": session_completed.isoformat()}
    })
    
    if games_since < 3:
        return None  # Need at least 3 games to assess
    
    # Check if theme issues decreased
    theme = last_session.get("theme")
    theme_issues_before = last_session.get("summary_snapshot", {}).get("theme_failures", 0)
    
    # Count theme issues in recent games
    cursor = db.game_coach_summaries.find({
        "user_id": user_id,
        "generated_at": {"$gt": session_completed.isoformat()}
    }).limit(3)
    
    theme_issues_after = 0
    async for doc in cursor:
        if doc.get("ties_to_active_theme"):
            theme_issues_after += 1
    
    # If improved (fewer issues)
    if theme_issues_after < theme_issues_before:
        theme_display = theme.replace("_", " ").lower()
        return {
            "show_improvement": True,
            "message": f"You handled {theme_display} better in your recent games.",
            "theme": theme
        }
    
    return None
