"""
Coach State Service - Single Source of Truth for Coaching

This is the SPINE of the coaching system.
Every page reads from CoachState to maintain consistency.

CoachState answers:
- What is the user's current focus theme?
- What are the micro-rules they should follow?
- When did they last have a deep session?

GameCoachSummary answers:
- What happened in THIS game?
- How does it connect to their theme?
- What's the ONE action they should take?
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone, timedelta
from enum import Enum
import random


class CoachTheme(str, Enum):
    """Active coaching themes - what the user is working on"""
    CALCULATION_DEPTH = "CalculationDepth"
    THREAT_VERIFICATION = "ThreatVerification"
    CONVERSION_DISCIPLINE = "ConversionDiscipline"
    PIECE_SAFETY = "PieceSafety"
    TIME_MANAGEMENT = "TimeManagement"
    OPENING_REPERTOIRE = "OpeningRepertoire"
    ENDGAME_TECHNIQUE = "EndgameTechnique"
    POSITIONAL_PATIENCE = "PositionalPatience"


class PrimaryIssue(str, Enum):
    """Primary issue labels for game summaries"""
    THREAT_SCAN_FAILURE = "ThreatScanFailure"
    RUSHED_WHEN_AHEAD = "RushedWhenAhead"
    STOPPED_CALCULATION_EARLY = "StoppedCalculationEarly"
    PIECE_LEFT_UNDEFENDED = "PieceLeftUndefended"
    MISSED_TACTIC = "MissedTactic"
    POOR_PIECE_PLACEMENT = "PoorPiecePlacement"
    KING_SAFETY_NEGLECT = "KingSafetyNeglect"
    TIME_PRESSURE_COLLAPSE = "TimePressureCollapse"
    OPENING_INACCURACY = "OpeningInaccuracy"
    ENDGAME_TECHNIQUE_FAILURE = "EndgameTechniqueFailure"
    PREMATURE_ATTACK = "PrematureAttack"
    DEFENSIVE_LAPSE = "DefensiveLapse"


class Confidence(str, Enum):
    """Confidence level in the analysis"""
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"


# Theme to issue mapping
THEME_ISSUE_MAP = {
    CoachTheme.CALCULATION_DEPTH: [
        PrimaryIssue.STOPPED_CALCULATION_EARLY,
        PrimaryIssue.MISSED_TACTIC
    ],
    CoachTheme.THREAT_VERIFICATION: [
        PrimaryIssue.THREAT_SCAN_FAILURE,
        PrimaryIssue.DEFENSIVE_LAPSE
    ],
    CoachTheme.CONVERSION_DISCIPLINE: [
        PrimaryIssue.RUSHED_WHEN_AHEAD,
        PrimaryIssue.PREMATURE_ATTACK
    ],
    CoachTheme.PIECE_SAFETY: [
        PrimaryIssue.PIECE_LEFT_UNDEFENDED,
        PrimaryIssue.POOR_PIECE_PLACEMENT
    ],
    CoachTheme.TIME_MANAGEMENT: [
        PrimaryIssue.TIME_PRESSURE_COLLAPSE
    ],
    CoachTheme.OPENING_REPERTOIRE: [
        PrimaryIssue.OPENING_INACCURACY
    ],
    CoachTheme.ENDGAME_TECHNIQUE: [
        PrimaryIssue.ENDGAME_TECHNIQUE_FAILURE
    ],
    CoachTheme.POSITIONAL_PATIENCE: [
        PrimaryIssue.PREMATURE_ATTACK,
        PrimaryIssue.POOR_PIECE_PLACEMENT
    ]
}

# Micro rules per theme
THEME_MICRO_RULES = {
    CoachTheme.CALCULATION_DEPTH: [
        "Before moving, count one move deeper than feels comfortable",
        "Ask: What does my opponent want to do after this?",
        "If unsure, take 10 more seconds"
    ],
    CoachTheme.THREAT_VERIFICATION: [
        "Before YOUR move, check what THEY are threatening",
        "Scan all their pieces, especially knights and bishops",
        "Ask: Is anything of mine undefended right now?"
    ],
    CoachTheme.CONVERSION_DISCIPLINE: [
        "When ahead, trade pieces not pawns",
        "No need to attack - just improve your worst piece",
        "Ask: Can I simplify and still be winning?"
    ],
    CoachTheme.PIECE_SAFETY: [
        "Before moving, check if the piece will be safe on its new square",
        "Count defenders vs attackers for every piece move",
        "If a piece is attacked, deal with it before anything else"
    ],
    CoachTheme.TIME_MANAGEMENT: [
        "Use at least 30 seconds on critical moments",
        "Don't blitz through the opening - think about plans",
        "Keep 2+ minutes for the last 10 moves"
    ],
    CoachTheme.OPENING_REPERTOIRE: [
        "Focus on development, not tricks",
        "Castle before move 10 if possible",
        "Control the center with pawns or pieces"
    ],
    CoachTheme.ENDGAME_TECHNIQUE: [
        "Activate your king in the endgame",
        "Passed pawns must be pushed",
        "Cut off the enemy king with your rook"
    ],
    CoachTheme.POSITIONAL_PATIENCE: [
        "Improve your worst placed piece",
        "Don't attack until all pieces are developed",
        "Small advantages accumulate - no need to force"
    ]
}

# Emotion mirror line templates (Indian coach tone)
EMOTION_MIRRORS = {
    PrimaryIssue.THREAT_SCAN_FAILURE: [
        "You missed their threat here.",
        "Their attack was visible. You didn't look.",
        "This one hurt because you didn't check what they wanted."
    ],
    PrimaryIssue.RUSHED_WHEN_AHEAD: [
        "You were winning. Then you rushed.",
        "Patience left you when victory was close.",
        "You got excited and stopped being careful."
    ],
    PrimaryIssue.STOPPED_CALCULATION_EARLY: [
        "You saw part of it. But stopped too soon.",
        "One more move of thinking would have saved you.",
        "The idea was right. The execution stopped short."
    ],
    PrimaryIssue.PIECE_LEFT_UNDEFENDED: [
        "That piece was hanging. You didn't see it.",
        "Free piece for them. Painful.",
        "Basic oversight. Your piece had no protection."
    ],
    PrimaryIssue.MISSED_TACTIC: [
        "There was a tactic. You walked past it.",
        "The combination was there. You didn't look for it.",
        "Tactics don't announce themselves. You have to hunt."
    ],
    PrimaryIssue.POOR_PIECE_PLACEMENT: [
        "Your pieces weren't working together.",
        "That piece sat there doing nothing.",
        "Coordination was missing."
    ],
    PrimaryIssue.KING_SAFETY_NEGLECT: [
        "Your king was exposed. You ignored the danger.",
        "Castle was available. You chose otherwise.",
        "King safety is not optional."
    ],
    PrimaryIssue.TIME_PRESSURE_COLLAPSE: [
        "Clock pressure got to you.",
        "You had time earlier. You wasted it.",
        "When time ran low, so did your accuracy."
    ],
    PrimaryIssue.OPENING_INACCURACY: [
        "The opening went wrong early.",
        "Basic principles were forgotten.",
        "Development was slow. They punished it."
    ],
    PrimaryIssue.ENDGAME_TECHNIQUE_FAILURE: [
        "The endgame was holdable. Technique failed.",
        "Endgame knowledge gap showed here.",
        "This ending required precision. It wasn't there."
    ],
    PrimaryIssue.PREMATURE_ATTACK: [
        "You attacked before you were ready.",
        "The attack was emotional, not prepared.",
        "Pieces weren't supporting each other yet."
    ],
    PrimaryIssue.DEFENSIVE_LAPSE: [
        "Defense slipped at the critical moment.",
        "You were defending well. Then you stopped.",
        "One defensive move would have held."
    ]
}


@dataclass
class CoachState:
    """
    Single Source of Truth for user's coaching journey.
    
    This is the SPINE - every page reads from this.
    """
    user_id: str
    active_theme: CoachTheme
    theme_started_at: datetime
    theme_confidence: float  # 0-1
    theme_reason: str
    micro_rules: List[str]
    last_micro_coach_game_id: Optional[str] = None
    last_deep_session_at: Optional[datetime] = None
    next_deep_session_due_at: Optional[datetime] = None
    recent_coach_sentences: List[str] = field(default_factory=list)
    games_on_theme: int = 0
    theme_improvement_delta: Optional[Dict] = None
    # Behavioral Maturity Layer (Step 3)
    behavioral_maturity_level: str = "Novice"  # Novice | Developing | Disciplined | Advanced
    coach_tone_mode: str = "ExplainMore"  # ExplainMore | Balanced | ChallengeMore
    theme_resistance_score: float = 0.0
    improvement_velocity: float = 0.0
    
    def to_dict(self) -> Dict:
        return {
            "user_id": self.user_id,
            "active_theme": self.active_theme.value,
            "theme_started_at": self.theme_started_at.isoformat(),
            "theme_confidence": round(self.theme_confidence, 2),
            "theme_reason": self.theme_reason,
            "micro_rules": self.micro_rules,
            "last_micro_coach_game_id": self.last_micro_coach_game_id,
            "last_deep_session_at": self.last_deep_session_at.isoformat() if self.last_deep_session_at else None,
            "next_deep_session_due_at": self.next_deep_session_due_at.isoformat() if self.next_deep_session_due_at else None,
            "recent_coach_sentences": self.recent_coach_sentences[-10:],
            "games_on_theme": self.games_on_theme,
            "theme_improvement_delta": self.theme_improvement_delta,
            # Behavioral Maturity
            "behavioral_maturity_level": self.behavioral_maturity_level,
            "coach_tone_mode": self.coach_tone_mode,
            "theme_resistance_score": round(self.theme_resistance_score, 2),
            "improvement_velocity": round(self.improvement_velocity, 2)
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'CoachState':
        return cls(
            user_id=data["user_id"],
            active_theme=CoachTheme(data["active_theme"]),
            theme_started_at=datetime.fromisoformat(data["theme_started_at"]) if isinstance(data["theme_started_at"], str) else data["theme_started_at"],
            theme_confidence=data["theme_confidence"],
            theme_reason=data["theme_reason"],
            micro_rules=data["micro_rules"],
            last_micro_coach_game_id=data.get("last_micro_coach_game_id"),
            last_deep_session_at=datetime.fromisoformat(data["last_deep_session_at"]) if data.get("last_deep_session_at") else None,
            next_deep_session_due_at=datetime.fromisoformat(data["next_deep_session_due_at"]) if data.get("next_deep_session_due_at") else None,
            recent_coach_sentences=data.get("recent_coach_sentences", []),
            games_on_theme=data.get("games_on_theme", 0),
            theme_improvement_delta=data.get("theme_improvement_delta"),
            # Behavioral Maturity
            behavioral_maturity_level=data.get("behavioral_maturity_level", "Novice"),
            coach_tone_mode=data.get("coach_tone_mode", "ExplainMore"),
            theme_resistance_score=data.get("theme_resistance_score", 0.0),
            improvement_velocity=data.get("improvement_velocity", 0.0)
        )


@dataclass
class PrimaryMoment:
    """The critical moment in a game"""
    move_number: int
    fen: str
    label: str  # Human readable: "Move 23 - Missed fork"
    
    def to_dict(self) -> Dict:
        return {
            "move_number": self.move_number,
            "fen": self.fen,
            "label": self.label
        }


@dataclass
class MicroDrill:
    """Optional drill tied to the game"""
    type: str  # "positions" | "mission"
    positions: List[str] = field(default_factory=list)  # FENs
    mission_id: Optional[str] = None
    cta_text: str = "Start 3-min Drill"
    
    def to_dict(self) -> Dict:
        return {
            "type": self.type,
            "positions": self.positions,
            "mission_id": self.mission_id,
            "cta_text": self.cta_text
        }


@dataclass
class GameCoachSummary:
    """
    Generated after each game analysis.
    
    This is what the Home page "Last Game" card renders from.
    """
    game_id: str
    user_id: str
    confidence: Confidence
    primary_moment: PrimaryMoment
    primary_issue: PrimaryIssue
    emotion_mirror_line: str  # "You rushed here."
    coach_explain_line: str   # Positional + contextual
    micro_drill: Optional[MicroDrill]
    ties_to_active_theme: bool
    theme_reinforcement_line: Optional[str]  # "This connects to your current focus: X."
    cta_type: str  # "review_moment" | "start_drill"
    cta_text: str
    cta_target: str  # URL or action
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> Dict:
        return {
            "game_id": self.game_id,
            "user_id": self.user_id,
            "confidence": self.confidence.value,
            "primary_moment": self.primary_moment.to_dict(),
            "primary_issue": self.primary_issue.value,
            "emotion_mirror_line": self.emotion_mirror_line,
            "coach_explain_line": self.coach_explain_line,
            "micro_drill": self.micro_drill.to_dict() if self.micro_drill else None,
            "ties_to_active_theme": self.ties_to_active_theme,
            "theme_reinforcement_line": self.theme_reinforcement_line,
            "cta_type": self.cta_type,
            "cta_text": self.cta_text,
            "cta_target": self.cta_target,
            "generated_at": self.generated_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'GameCoachSummary':
        return cls(
            game_id=data["game_id"],
            user_id=data["user_id"],
            confidence=Confidence(data["confidence"]),
            primary_moment=PrimaryMoment(**data["primary_moment"]),
            primary_issue=PrimaryIssue(data["primary_issue"]),
            emotion_mirror_line=data["emotion_mirror_line"],
            coach_explain_line=data["coach_explain_line"],
            micro_drill=MicroDrill(**data["micro_drill"]) if data.get("micro_drill") else None,
            ties_to_active_theme=data["ties_to_active_theme"],
            theme_reinforcement_line=data.get("theme_reinforcement_line"),
            cta_type=data["cta_type"],
            cta_text=data["cta_text"],
            cta_target=data["cta_target"],
            generated_at=datetime.fromisoformat(data["generated_at"]) if isinstance(data.get("generated_at"), str) else datetime.now(timezone.utc)
        )


class CoachStateService:
    """
    Service for managing CoachState and GameCoachSummary.
    
    This is the single source of truth for coaching across all pages.
    """
    
    # Minimum games/days before theme switch
    MIN_GAMES_BEFORE_SWITCH = 10
    MIN_DAYS_BEFORE_SWITCH = 7
    
    def __init__(self, db):
        self.db = db
    
    async def get_coach_state(self, user_id: str) -> Optional[CoachState]:
        """Get user's current coach state"""
        doc = await self.db.coach_states.find_one({"user_id": user_id})
        if doc:
            doc.pop("_id", None)
            return CoachState.from_dict(doc)
        return None
    
    async def initialize_coach_state(self, user_id: str, initial_theme: CoachTheme = None) -> CoachState:
        """Initialize coach state for new user or after analysis"""
        if not initial_theme:
            initial_theme = CoachTheme.THREAT_VERIFICATION  # Safe default
        
        state = CoachState(
            user_id=user_id,
            active_theme=initial_theme,
            theme_started_at=datetime.now(timezone.utc),
            theme_confidence=0.5,
            theme_reason="Starting focus based on common improvement areas",
            micro_rules=THEME_MICRO_RULES[initial_theme][:2],
            games_on_theme=0
        )
        
        await self.db.coach_states.replace_one(
            {"user_id": user_id},
            state.to_dict(),
            upsert=True
        )
        
        return state
    
    async def update_coach_state(self, state: CoachState) -> None:
        """Update coach state in DB"""
        await self.db.coach_states.replace_one(
            {"user_id": state.user_id},
            state.to_dict(),
            upsert=True
        )
    
    async def should_switch_theme(
        self, 
        current_state: CoachState, 
        new_theme: CoachTheme,
        new_theme_severity: float
    ) -> bool:
        """
        Determine if we should switch themes.
        
        Rules:
        - Minimum 7 days OR 10 games on current theme
        - New theme must have significantly higher severity
        - Exception: severe new weakness (severity > 0.8)
        """
        if not current_state:
            return True
        
        days_on_theme = (datetime.now(timezone.utc) - current_state.theme_started_at).days
        
        # Check minimum thresholds
        if days_on_theme < self.MIN_DAYS_BEFORE_SWITCH and current_state.games_on_theme < self.MIN_GAMES_BEFORE_SWITCH:
            # Only switch if new theme is severe
            return new_theme_severity > 0.8
        
        # Allow switch if new theme is significantly more important
        return new_theme_severity > current_state.theme_confidence + 0.3
    
    async def add_coach_sentence(self, user_id: str, sentence: str) -> None:
        """Add sentence to recent list for anti-repetition"""
        state = await self.get_coach_state(user_id)
        if state:
            state.recent_coach_sentences.append(sentence)
            state.recent_coach_sentences = state.recent_coach_sentences[-10:]
            await self.update_coach_state(state)
    
    def get_non_repetitive_line(self, lines: List[str], recent: List[str]) -> str:
        """Get a line that hasn't been used recently"""
        available = [l for l in lines if l not in recent]
        if not available:
            available = lines
        return random.choice(available)
    
    async def get_game_coach_summary(self, game_id: str) -> Optional[GameCoachSummary]:
        """Get coach summary for a game"""
        doc = await self.db.game_coach_summaries.find_one({"game_id": game_id})
        if doc:
            doc.pop("_id", None)
            return GameCoachSummary.from_dict(doc)
        return None
    
    async def get_latest_game_coach_summary(self, user_id: str) -> Optional[GameCoachSummary]:
        """Get the most recent game coach summary for user"""
        doc = await self.db.game_coach_summaries.find_one(
            {"user_id": user_id},
            sort=[("generated_at", -1)]
        )
        if doc:
            doc.pop("_id", None)
            return GameCoachSummary.from_dict(doc)
        return None
    
    async def save_game_coach_summary(self, summary: GameCoachSummary) -> None:
        """Save game coach summary"""
        await self.db.game_coach_summaries.replace_one(
            {"game_id": summary.game_id},
            summary.to_dict(),
            upsert=True
        )
    
    async def get_theme_improvement_stats(self, user_id: str, theme: CoachTheme) -> Dict:
        """
        Get improvement stats for a theme.
        
        Returns:
        - mistakes_before: count in older games
        - mistakes_after: count in recent games
        - trend: "improving" | "stable" | "declining"
        """
        issues = THEME_ISSUE_MAP.get(theme, [])
        issue_values = [i.value for i in issues]
        
        # Get last 20 game summaries
        cursor = self.db.game_coach_summaries.find(
            {"user_id": user_id}
        ).sort("generated_at", -1).limit(20)
        
        summaries = []
        async for doc in cursor:
            summaries.append(doc)
        
        if len(summaries) < 4:
            return {"trend": "insufficient_data", "delta": 0}
        
        # Split into old vs recent
        mid = len(summaries) // 2
        recent = summaries[:mid]
        older = summaries[mid:]
        
        # Count issues matching theme
        recent_count = sum(1 for s in recent if s.get("primary_issue") in issue_values)
        older_count = sum(1 for s in older if s.get("primary_issue") in issue_values)
        
        delta = older_count - recent_count
        
        if delta > 1:
            trend = "improving"
        elif delta < -1:
            trend = "declining"
        else:
            trend = "stable"
        
        return {
            "mistakes_before": older_count,
            "mistakes_after": recent_count,
            "delta": delta,
            "trend": trend,
            "games_analyzed": len(summaries)
        }


async def generate_game_coach_summary(
    db,
    game_id: str,
    user_id: str,
    game_analysis: Dict,
    coach_state: Optional[CoachState],
    game_result: str = None,
    user_color: str = "white"
) -> GameCoachSummary:
    """
    Generate GameCoachSummary after game analysis completes.
    
    Uses coach_moment_selector to pick the most coaching-relevant moment,
    not just the highest cp_loss.
    
    Inputs:
    - game_analysis: from game_analyses collection
    - coach_state: user's current CoachState
    - game_result: "1-0", "0-1", "1/2-1/2"
    - user_color: "white" or "black"
    
    Output:
    - GameCoachSummary ready for Home page display
    """
    from coach_moment_selector import select_teaching_moment
    
    service = CoachStateService(db)
    
    # Extract analysis data
    sf_analysis = game_analysis.get("stockfish_analysis", {})
    move_evals = sf_analysis.get("move_evaluations", [])
    
    # =========================================================================
    # NEW: Use Coach Moment Selector instead of highest cp_loss
    # =========================================================================
    selection_result = select_teaching_moment(move_evals, user_color, game_result)
    
    if not selection_result:
        # No critical moves - use a default
        primary_moment = PrimaryMoment(
            move_number=1,
            fen=game_analysis.get("initial_fen", "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"),
            label="No critical mistakes found"
        )
        primary_issue = PrimaryIssue.MISSED_TACTIC
        confidence = Confidence.LOW
        selected_move = None
        selection_reason = "no_critical_moves"
    else:
        selected_move = selection_result.get("selected_move", {})
        move_num = selected_move.get("move_number", 1)
        fen = selected_move.get("fen_before", "")
        eval_label = selected_move.get("evaluation", "mistake")
        cp_loss = selected_move.get("cp_loss", 0)
        selection_reason = selection_result.get("selection_reason", "tactical_error")
        
        # Create label based on selection reason
        if selection_reason == "pattern_event":
            pattern_freq = selected_move.get("pattern_frequency", 0)
            label = f"Move {move_num} - Pattern ({pattern_freq}x)"
        elif selection_reason == "turning_point":
            label = f"Move {move_num} - Turning Point"
        elif selection_reason == "missed_mate":
            label = f"Move {move_num} - Missed Mate"
        else:
            label = f"Move {move_num} - {eval_label.title()}"
        
        primary_moment = PrimaryMoment(
            move_number=move_num,
            fen=fen,
            label=label
        )
        
        # Determine primary issue from cognitive gap or selection reason
        cognitive_gap = selected_move.get("cognitive_gap")
        primary_issue = _map_gap_to_issue(cognitive_gap, selection_reason)
        
        # Confidence based on CRS score and context
        crs_score = selection_result.get("selection_score", 0)
        position_ctx = selected_move.get("position_context", {})
        
        if crs_score >= 200 or position_ctx.get("result_flipped"):
            confidence = Confidence.HIGH
        elif crs_score >= 100 or cp_loss >= 150:
            confidence = Confidence.MEDIUM
        else:
            confidence = Confidence.LOW
    
    # Generate emotion mirror line
    recent_sentences = coach_state.recent_coach_sentences if coach_state else []
    emotion_lines = EMOTION_MIRRORS.get(primary_issue, ["That was a tough moment."])
    emotion_mirror = service.get_non_repetitive_line(emotion_lines, recent_sentences)
    
    # Generate coach explain line (using new selection data)
    coach_explain = _generate_coach_explain_v2(selected_move, primary_issue, selection_reason)
    
    # Check if ties to active theme
    ties_to_theme = False
    theme_line = None
    
    if coach_state:
        theme_issues = THEME_ISSUE_MAP.get(coach_state.active_theme, [])
        if primary_issue in theme_issues:
            ties_to_theme = True
            theme_line = f"This connects to your current focus: {coach_state.active_theme.value.replace('_', ' ')}."
    
    # Determine CTA
    if selected_move:
        move_num = selected_move.get("move_number", 1)
        cta_type = "review_moment"
        cta_text = "Review This Moment"
        cta_target = f"/game/{game_id}?move={move_num}"
    else:
        cta_type = "review_game"
        cta_text = "Review Game"
        cta_target = f"/game/{game_id}"
    
    # Create summary with selection metadata
    summary = GameCoachSummary(
        game_id=game_id,
        user_id=user_id,
        confidence=confidence,
        primary_moment=primary_moment,
        primary_issue=primary_issue,
        emotion_mirror_line=emotion_mirror,
        coach_explain_line=coach_explain,
        micro_drill=None,  # Can be added later
        ties_to_active_theme=ties_to_theme,
        theme_reinforcement_line=theme_line,
        cta_type=cta_type,
        cta_text=cta_text,
        cta_target=cta_target
    )
    
    # Store selection metadata for debugging
    summary_dict = summary.to_dict()
    summary_dict["selection_metadata"] = {
        "selection_reason": selection_reason,
        "selection_score": selection_result.get("selection_score") if selection_result else 0,
        "selection_factors": selection_result.get("selection_factors", []) if selection_result else [],
        "runner_up_count": len(selection_result.get("runner_up_moves", [])) if selection_result else 0
    }
    
    # Save summary
    await service.save_game_coach_summary(summary)
    
    # Log analytics event
    from coach_analytics_service import get_analytics_service
    analytics = get_analytics_service(db)
    await analytics.log_game_coach_summary(
        user_id=user_id,
        game_id=game_id,
        primary_issue=primary_issue.value,
        confidence=confidence.value,
        ties_to_theme=ties_to_theme,
        current_theme=coach_state.active_theme.value if coach_state else "Unknown"
    )
    
    # Update coach state
    if coach_state:
        coach_state.last_micro_coach_game_id = game_id
        coach_state.games_on_theme += 1
        coach_state.recent_coach_sentences.append(emotion_mirror)
        coach_state.recent_coach_sentences = coach_state.recent_coach_sentences[-10:]
        
        # Update improvement delta
        stats = await service.get_theme_improvement_stats(user_id, coach_state.active_theme)
        coach_state.theme_improvement_delta = stats
        
        await service.update_coach_state(coach_state)
    
    return summary


def _map_gap_to_issue(cognitive_gap: Optional[str], selection_reason: str) -> PrimaryIssue:
    """Map cognitive gap to primary issue enum"""
    if not cognitive_gap:
        # Fall back to selection reason
        if selection_reason == "missed_mate":
            return PrimaryIssue.MISSED_TACTIC
        elif selection_reason == "turning_point":
            return PrimaryIssue.POSITIONAL_DRIFT
        elif selection_reason == "pattern_event":
            return PrimaryIssue.THREAT_SCAN_FAILURE
        return PrimaryIssue.MISSED_TACTIC
    
    # Map cognitive gap types to primary issues
    gap_to_issue = {
        "THREAT_BLINDNESS": PrimaryIssue.THREAT_SCAN_FAILURE,
        "threat_blindness": PrimaryIssue.THREAT_SCAN_FAILURE,
        "HANGING_PIECE_BLINDNESS": PrimaryIssue.PIECE_LEFT_UNDEFENDED,
        "hanging_piece_blindness": PrimaryIssue.PIECE_LEFT_UNDEFENDED,
        "TACTICAL_OVERSIGHT": PrimaryIssue.MISSED_TACTIC,
        "tactical_oversight": PrimaryIssue.MISSED_TACTIC,
        "CALCULATION_DEPTH": PrimaryIssue.STOPPED_CALCULATION_EARLY,
        "calculation_depth": PrimaryIssue.STOPPED_CALCULATION_EARLY,
        "POSITIONAL_MISREAD": PrimaryIssue.POSITIONAL_DRIFT,
        "positional_misread": PrimaryIssue.POSITIONAL_DRIFT,
        "PREMATURE_ACTION": PrimaryIssue.RUSHED_WHEN_AHEAD,
        "premature_action": PrimaryIssue.RUSHED_WHEN_AHEAD,
        "DEFENSIVE_LAPSE": PrimaryIssue.DEFENSIVE_LAPSE,
        "defensive_lapse": PrimaryIssue.DEFENSIVE_LAPSE,
    }
    
    return gap_to_issue.get(cognitive_gap, PrimaryIssue.MISSED_TACTIC)


def _generate_coach_explain_v2(
    selected_move: Optional[Dict],
    primary_issue: PrimaryIssue,
    selection_reason: str
) -> str:
    """
    Generate contextual coach explanation using selection data.
    
    Uses PV lines, position context, and selection reason
    for more realistic explanations.
    """
    if not selected_move:
        return "Review your game to identify areas for improvement."
    
    position_ctx = selected_move.get("position_context", {})
    pv_played = selected_move.get("pv_after_played", [])
    pv_best = selected_move.get("pv_after_best", [])
    threat = selected_move.get("threat")
    best_move = selected_move.get("best_move")
    gap_evidence = selected_move.get("gap_evidence", "")
    coaching_focus = selected_move.get("coaching_focus", "")
    cp_loss = selected_move.get("cp_loss", 0)
    
    lines = []
    
    # Different explanation structure by selection reason
    if selection_reason == "pattern_event":
        pattern_freq = selected_move.get("pattern_frequency", 0)
        lines.append(f"This is the {_ordinal(pattern_freq)} time this pattern appeared.")
        if coaching_focus:
            lines.append(coaching_focus)
    
    elif selection_reason == "turning_point":
        state_before = position_ctx.get("state_before", "")
        state_after = position_ctx.get("state_after", "")
        if state_before and state_after:
            lines.append(f"You were {state_before} but became {state_after} after this move.")
        else:
            lines.append("This was a turning point in the game.")
    
    elif selection_reason == "missed_mate":
        if pv_best and len(pv_best) >= 2:
            short_line = " ".join(pv_best[:3])
            lines.append(f"There was a forced mate: {short_line}...")
        else:
            lines.append("You missed a forced mating sequence.")
        lines.append("In winning positions, check for forcing sequences.")
    
    else:  # tactical_error or default
        if threat:
            lines.append(f"After your move, opponent had {threat}.")
        if best_move and cp_loss >= 100:
            lines.append(f"Consider {best_move} instead.")
    
    # Add coaching focus if not already included
    if coaching_focus and coaching_focus not in lines:
        lines.append(coaching_focus)
    
    # Ensure we have at least one line
    if not lines:
        lines.append("Review this moment carefully.")
    
    return " ".join(lines[:3])  # Max 3 sentences


def _ordinal(n: int) -> str:
    """Convert number to ordinal (1st, 2nd, 3rd, etc.)"""
    if 11 <= n % 100 <= 13:
        suffix = 'th'
    else:
        suffix = ['th', 'st', 'nd', 'rd', 'th'][min(n % 10, 4)]
    return f"{n}{suffix}"


def _determine_primary_issue(worst_move: Dict, cognitive_gaps: List, game_analysis: Dict) -> PrimaryIssue:
    """Determine the primary issue from move data"""
    
    # Check cognitive gaps first
    gap_to_issue = {
        "missed_fork": PrimaryIssue.MISSED_TACTIC,
        "threat_blindness": PrimaryIssue.THREAT_SCAN_FAILURE,
        "hanging_piece_blindness": PrimaryIssue.PIECE_LEFT_UNDEFENDED,
        "king_safety_neglect": PrimaryIssue.KING_SAFETY_NEGLECT,
        "tactical_oversight": PrimaryIssue.MISSED_TACTIC,
        "calculation_error": PrimaryIssue.STOPPED_CALCULATION_EARLY,
    }
    
    for gap in cognitive_gaps:
        if gap in gap_to_issue:
            return gap_to_issue[gap]
    
    # Infer from move context
    eval_before = worst_move.get("eval_before", 0)
    cp_loss = worst_move.get("cp_loss", 0)
    
    # If was winning and blundered
    if eval_before > 1.5 and cp_loss > 200:
        return PrimaryIssue.RUSHED_WHEN_AHEAD
    
    # Default
    return PrimaryIssue.STOPPED_CALCULATION_EARLY


def _generate_coach_explain(worst_move: Dict, issue: PrimaryIssue, game_analysis: Dict) -> str:
    """Generate positional + contextual explanation"""
    
    if not worst_move:
        return "The game had no critical mistakes. Focus on finding small improvements."
    
    best_move = worst_move.get("best_move", "a better move")
    played_move = worst_move.get("move", "your move")
    cp_loss = worst_move.get("cp_loss", 0)
    
    # Issue-specific explanations
    explanations = {
        PrimaryIssue.THREAT_SCAN_FAILURE: f"Before playing {played_move}, checking their threats would have shown the danger. {best_move} was safer.",
        PrimaryIssue.RUSHED_WHEN_AHEAD: f"You had a winning position. {played_move} gave it away. {best_move} maintained your advantage without risk.",
        PrimaryIssue.STOPPED_CALCULATION_EARLY: f"{played_move} looked reasonable, but {best_move} was much stronger. One more move of calculation would have found it.",
        PrimaryIssue.PIECE_LEFT_UNDEFENDED: f"After {played_move}, you had an undefended piece. {best_move} kept everything protected.",
        PrimaryIssue.MISSED_TACTIC: f"There was a tactical shot: {best_move}. These patterns get easier to spot with practice.",
        PrimaryIssue.POOR_PIECE_PLACEMENT: f"{played_move} put your piece on a passive square. {best_move} would have been more active.",
        PrimaryIssue.KING_SAFETY_NEGLECT: f"Your king was vulnerable. {best_move} addressed the safety issue first.",
        PrimaryIssue.TIME_PRESSURE_COLLAPSE: f"Under time pressure, {played_move} was a reflex. With more time, {best_move} was findable.",
        PrimaryIssue.OPENING_INACCURACY: f"In the opening, {played_move} violated basic principles. {best_move} follows opening theory better.",
        PrimaryIssue.ENDGAME_TECHNIQUE_FAILURE: f"The endgame required precision. {best_move} was the technical solution.",
        PrimaryIssue.PREMATURE_ATTACK: f"The attack wasn't ready yet. {best_move} continued preparation instead of forcing.",
        PrimaryIssue.DEFENSIVE_LAPSE: f"Defense was holding until {played_move}. {best_move} maintained the fortress."
    }
    
    return explanations.get(issue, f"{best_move} was stronger than {played_move} here. The position required more care.")
