"""
Player Identity Service - The 9/10 Memory System
=================================================

This is the CORE of personalized coaching. Every user gets a comprehensive
identity document that evolves over time.

WHAT THIS TRACKS:
1. Blunder Taxonomy - Not just "blunder" but WHY (fork, hanging piece, time trouble)
2. Style Profile - Aggressive/positional, opening preferences, piece preferences
3. Behavioral Profile - Tilt triggers, time usage, post-blunder recovery
4. Opening Repertoire - What they play, what they know, what they fall for
5. Pattern History - Exact game references for "remember when..."
6. Trend Analysis - Improving/worsening on specific patterns
7. Learning Velocity - How fast they improve on each area

DESIGN PRINCIPLES:
- NO RAG needed - Chess is structured, use MongoDB queries
- DETERMINISTIC retrieval - Exact game IDs, not fuzzy search
- ALWAYS INJECTED - Every coaching prompt gets memory context
- EVOLVING - Profile updates after every game

Author: Built for 9/10 memory system
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
from enum import Enum
import logging
import chess

logger = logging.getLogger(__name__)


# =============================================================================
# ENUMS AND CONSTANTS
# =============================================================================

class BlunderType(str, Enum):
    """Granular blunder classification - the WHY behind mistakes"""
    # Tactical blindness
    MISSED_FORK = "missed_fork"
    MISSED_PIN = "missed_pin"
    MISSED_SKEWER = "missed_skewer"
    MISSED_DISCOVERY = "missed_discovery"
    MISSED_BACK_RANK = "missed_back_rank"
    MISSED_CHECKMATE = "missed_checkmate"
    
    # Piece safety
    HANGING_PIECE = "hanging_piece"
    UNDEFENDED_PIECE = "undefended_piece"
    TRAPPED_PIECE = "trapped_piece"
    
    # Positional errors
    KING_SAFETY_NEGLECT = "king_safety_neglect"
    PAWN_STRUCTURE_DAMAGE = "pawn_structure_damage"
    PIECE_ACTIVITY_LOSS = "piece_activity_loss"
    
    # Psychological/behavioral
    TIME_TROUBLE_BLUNDER = "time_trouble_blunder"
    IMPULSE_MOVE = "impulse_move"
    POST_BLUNDER_TILT = "post_blunder_tilt"
    WINNING_POSITION_COLLAPSE = "winning_position_collapse"
    
    # Opening specific
    OPENING_TRAP_FELL = "opening_trap_fell"
    OPENING_PRINCIPLE_VIOLATED = "opening_principle_violated"
    
    # Calculation
    CALCULATION_ERROR = "calculation_error"
    HORIZON_EFFECT = "horizon_effect"
    
    # Unknown
    UNCLEAR = "unclear"


class PlayStyle(str, Enum):
    """User's playing style classification"""
    AGGRESSIVE = "aggressive"
    POSITIONAL = "positional"
    TACTICAL = "tactical"
    DEFENSIVE = "defensive"
    UNIVERSAL = "universal"
    DEVELOPING = "developing"  # Not enough data yet


class PiecePreference(str, Enum):
    """Which pieces user handles better"""
    KNIGHT_LOVER = "knight_lover"  # Prefers knights, trades bishops
    BISHOP_PAIR = "bishop_pair"    # Values bishop pair
    ROOK_PLAYER = "rook_player"    # Strong in rook endgames
    QUEEN_DEPENDENT = "queen_dependent"  # Struggles without queen
    BALANCED = "balanced"


class TiltTrigger(str, Enum):
    """What causes user to tilt"""
    CONSECUTIVE_LOSSES = "consecutive_losses"
    MISSED_WIN = "missed_win"
    TIME_PRESSURE = "time_pressure"
    BLUNDER_SPIRAL = "blunder_spiral"
    OPPONENT_TRASH_TALK = "opponent_trash_talk"
    UNKNOWN = "unknown"


class GamePhase(str, Enum):
    """Game phases for tracking"""
    OPENING = "opening"
    MIDDLEGAME = "middlegame"
    ENDGAME = "endgame"


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class BlunderRecord:
    """A single blunder with full context"""
    blunder_type: BlunderType
    game_id: str
    move_number: int
    fen_before: str
    move_played: str
    best_move: str
    cp_loss: int
    phase: GamePhase
    time_spent: float  # seconds spent on this move
    time_remaining: float  # clock time remaining
    eval_before: float  # position eval before blunder
    opponent: str
    date: datetime
    
    # Additional context
    was_winning: bool  # Were we winning before this?
    piece_lost: Optional[str]  # What piece was lost, if any
    tactical_theme: Optional[str]  # fork, pin, etc.
    
    def to_dict(self) -> Dict:
        return {
            "blunder_type": self.blunder_type.value,
            "game_id": self.game_id,
            "move_number": self.move_number,
            "fen_before": self.fen_before,
            "move_played": self.move_played,
            "best_move": self.best_move,
            "cp_loss": self.cp_loss,
            "phase": self.phase.value,
            "time_spent": self.time_spent,
            "time_remaining": self.time_remaining,
            "eval_before": self.eval_before,
            "opponent": self.opponent,
            "date": self.date.isoformat(),
            "was_winning": self.was_winning,
            "piece_lost": self.piece_lost,
            "tactical_theme": self.tactical_theme
        }
    
    @classmethod
    def from_dict(cls, d: Dict) -> 'BlunderRecord':
        return cls(
            blunder_type=BlunderType(d.get("blunder_type", "unclear")),
            game_id=d["game_id"],
            move_number=d["move_number"],
            fen_before=d.get("fen_before", ""),
            move_played=d.get("move_played", ""),
            best_move=d.get("best_move", ""),
            cp_loss=d.get("cp_loss", 0),
            phase=GamePhase(d.get("phase", "middlegame")),
            time_spent=d.get("time_spent", 0),
            time_remaining=d.get("time_remaining", 0),
            eval_before=d.get("eval_before", 0),
            opponent=d.get("opponent", "unknown"),
            date=datetime.fromisoformat(d["date"]) if isinstance(d.get("date"), str) else d.get("date", datetime.now(timezone.utc)),
            was_winning=d.get("was_winning", False),
            piece_lost=d.get("piece_lost"),
            tactical_theme=d.get("tactical_theme")
        )


@dataclass
class BlunderTaxonomy:
    """Complete blunder analysis for a user"""
    total_blunders: int = 0
    
    # By type
    by_type: Dict[str, int] = field(default_factory=dict)
    
    # By piece involved
    by_piece: Dict[str, int] = field(default_factory=dict)  # knight: 12, queen: 3
    
    # By phase
    by_phase: Dict[str, int] = field(default_factory=dict)  # opening: 5, middlegame: 20
    
    # By context
    when_winning: int = 0
    when_losing: int = 0
    when_equal: int = 0
    
    # Time-related
    under_time_pressure: int = 0  # <60 seconds
    impulse_moves: int = 0  # <2 seconds spent
    
    # Trends (last 10 games vs previous 10)
    recent_rate: float = 0.0  # blunders per game recently
    historical_rate: float = 0.0  # blunders per game historically
    trend: str = "stable"  # improving, worsening, stable
    
    # Most common
    most_common_type: Optional[BlunderType] = None
    most_vulnerable_piece: Optional[str] = None
    worst_phase: Optional[GamePhase] = None
    
    def to_dict(self) -> Dict:
        return {
            "total_blunders": self.total_blunders,
            "by_type": self.by_type,
            "by_piece": self.by_piece,
            "by_phase": self.by_phase,
            "when_winning": self.when_winning,
            "when_losing": self.when_losing,
            "when_equal": self.when_equal,
            "under_time_pressure": self.under_time_pressure,
            "impulse_moves": self.impulse_moves,
            "recent_rate": self.recent_rate,
            "historical_rate": self.historical_rate,
            "trend": self.trend,
            "most_common_type": self.most_common_type.value if self.most_common_type else None,
            "most_vulnerable_piece": self.most_vulnerable_piece,
            "worst_phase": self.worst_phase.value if self.worst_phase else None
        }
    
    @classmethod
    def from_dict(cls, d: Dict) -> 'BlunderTaxonomy':
        return cls(
            total_blunders=d.get("total_blunders", 0),
            by_type=d.get("by_type", {}),
            by_piece=d.get("by_piece", {}),
            by_phase=d.get("by_phase", {}),
            when_winning=d.get("when_winning", 0),
            when_losing=d.get("when_losing", 0),
            when_equal=d.get("when_equal", 0),
            under_time_pressure=d.get("under_time_pressure", 0),
            impulse_moves=d.get("impulse_moves", 0),
            recent_rate=d.get("recent_rate", 0.0),
            historical_rate=d.get("historical_rate", 0.0),
            trend=d.get("trend", "stable"),
            most_common_type=BlunderType(d["most_common_type"]) if d.get("most_common_type") else None,
            most_vulnerable_piece=d.get("most_vulnerable_piece"),
            worst_phase=GamePhase(d["worst_phase"]) if d.get("worst_phase") else None
        )


@dataclass
class StyleProfile:
    """User's playing style characteristics"""
    # Overall style
    primary_style: PlayStyle = PlayStyle.DEVELOPING
    confidence: float = 0.0  # How confident we are in this classification
    
    # Style metrics (0-1 scale)
    aggression_score: float = 0.5  # Pawn pushes, piece activity, attacks
    positional_score: float = 0.5  # Quiet moves, pawn structure care
    tactical_score: float = 0.5  # Sacrifices, combinations
    defensive_score: float = 0.5  # Defensive accuracy, fortress building
    
    # Opening preferences
    opening_as_white: str = "e4"  # Most played first move as white
    opening_as_black_vs_e4: str = "e5"  # Most played response to e4
    opening_as_black_vs_d4: str = "d5"  # Most played response to d4
    prefers_open_games: bool = True  # Open vs closed positions
    
    # Piece handling
    piece_preference: PiecePreference = PiecePreference.BALANCED
    trades_pieces_early: bool = False  # Tends to simplify
    keeps_queens: bool = True  # Avoids queen trades
    
    # Endgame
    endgame_comfort: float = 0.5  # 0 = avoids, 1 = seeks
    rook_endgame_skill: float = 0.5
    pawn_endgame_skill: float = 0.5
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, d: Dict) -> 'StyleProfile':
        return cls(
            primary_style=PlayStyle(d.get("primary_style", "developing")),
            confidence=d.get("confidence", 0.0),
            aggression_score=d.get("aggression_score", 0.5),
            positional_score=d.get("positional_score", 0.5),
            tactical_score=d.get("tactical_score", 0.5),
            defensive_score=d.get("defensive_score", 0.5),
            opening_as_white=d.get("opening_as_white", "e4"),
            opening_as_black_vs_e4=d.get("opening_as_black_vs_e4", "e5"),
            opening_as_black_vs_d4=d.get("opening_as_black_vs_d4", "d5"),
            prefers_open_games=d.get("prefers_open_games", True),
            piece_preference=PiecePreference(d.get("piece_preference", "balanced")),
            trades_pieces_early=d.get("trades_pieces_early", False),
            keeps_queens=d.get("keeps_queens", True),
            endgame_comfort=d.get("endgame_comfort", 0.5),
            rook_endgame_skill=d.get("rook_endgame_skill", 0.5),
            pawn_endgame_skill=d.get("pawn_endgame_skill", 0.5)
        )


@dataclass
class BehavioralProfile:
    """Psychological and behavioral patterns"""
    # Tilt analysis
    tilt_trigger: TiltTrigger = TiltTrigger.UNKNOWN
    tilt_recovery_games: int = 2  # Games needed to recover from tilt
    tilt_detected_count: int = 0  # Times tilt was detected
    
    # Time management
    avg_move_time_opening: float = 10.0  # seconds
    avg_move_time_middlegame: float = 15.0
    avg_move_time_endgame: float = 8.0
    time_trouble_frequency: float = 0.0  # % of games ending in time trouble
    rushes_in_winning_positions: bool = False
    
    # Post-blunder behavior
    post_blunder_accuracy: float = 0.5  # Accuracy of next 3 moves after blunder
    blunder_spiral_rate: float = 0.0  # % of games with 2+ blunders in a row
    recovery_capability: float = 0.5  # How well they recover from bad positions
    
    # Emotional patterns
    plays_worse_after_loss: bool = False
    plays_better_after_win: bool = False
    consistency_score: float = 0.5  # 0 = highly variable, 1 = consistent
    
    # Session patterns
    first_game_accuracy: float = 0.5  # Accuracy in first game of session
    fatigue_game_threshold: int = 5  # After N games, performance drops
    best_time_of_day: Optional[str] = None  # morning, afternoon, evening, night
    
    def to_dict(self) -> Dict:
        return {
            "tilt_trigger": self.tilt_trigger.value,
            "tilt_recovery_games": self.tilt_recovery_games,
            "tilt_detected_count": self.tilt_detected_count,
            "avg_move_time_opening": self.avg_move_time_opening,
            "avg_move_time_middlegame": self.avg_move_time_middlegame,
            "avg_move_time_endgame": self.avg_move_time_endgame,
            "time_trouble_frequency": self.time_trouble_frequency,
            "rushes_in_winning_positions": self.rushes_in_winning_positions,
            "post_blunder_accuracy": self.post_blunder_accuracy,
            "blunder_spiral_rate": self.blunder_spiral_rate,
            "recovery_capability": self.recovery_capability,
            "plays_worse_after_loss": self.plays_worse_after_loss,
            "plays_better_after_win": self.plays_better_after_win,
            "consistency_score": self.consistency_score,
            "first_game_accuracy": self.first_game_accuracy,
            "fatigue_game_threshold": self.fatigue_game_threshold,
            "best_time_of_day": self.best_time_of_day
        }
    
    @classmethod
    def from_dict(cls, d: Dict) -> 'BehavioralProfile':
        return cls(
            tilt_trigger=TiltTrigger(d.get("tilt_trigger", "unknown")),
            tilt_recovery_games=d.get("tilt_recovery_games", 2),
            tilt_detected_count=d.get("tilt_detected_count", 0),
            avg_move_time_opening=d.get("avg_move_time_opening", 10.0),
            avg_move_time_middlegame=d.get("avg_move_time_middlegame", 15.0),
            avg_move_time_endgame=d.get("avg_move_time_endgame", 8.0),
            time_trouble_frequency=d.get("time_trouble_frequency", 0.0),
            rushes_in_winning_positions=d.get("rushes_in_winning_positions", False),
            post_blunder_accuracy=d.get("post_blunder_accuracy", 0.5),
            blunder_spiral_rate=d.get("blunder_spiral_rate", 0.0),
            recovery_capability=d.get("recovery_capability", 0.5),
            plays_worse_after_loss=d.get("plays_worse_after_loss", False),
            plays_better_after_win=d.get("plays_better_after_win", False),
            consistency_score=d.get("consistency_score", 0.5),
            first_game_accuracy=d.get("first_game_accuracy", 0.5),
            fatigue_game_threshold=d.get("fatigue_game_threshold", 5),
            best_time_of_day=d.get("best_time_of_day")
        )


@dataclass
class OpeningRepertoire:
    """What the user plays and knows"""
    # As White
    white_main_opening: str = "e4"  # Italian, London, etc.
    white_openings_played: Dict[str, int] = field(default_factory=dict)  # {opening: count}
    white_openings_win_rate: Dict[str, float] = field(default_factory=dict)
    
    # As Black vs e4
    black_vs_e4_main: str = "e5"
    black_vs_e4_played: Dict[str, int] = field(default_factory=dict)
    black_vs_e4_win_rate: Dict[str, float] = field(default_factory=dict)
    
    # As Black vs d4
    black_vs_d4_main: str = "d5"
    black_vs_d4_played: Dict[str, int] = field(default_factory=dict)
    black_vs_d4_win_rate: Dict[str, float] = field(default_factory=dict)
    
    # Traps
    traps_known: List[str] = field(default_factory=list)  # Successfully executed
    traps_fell_for: List[str] = field(default_factory=list)  # Fell victim to
    traps_success_rate: Dict[str, float] = field(default_factory=dict)
    
    # Theory depth
    average_book_moves: float = 5.0  # How deep into theory they typically play
    deviates_early: bool = False  # Tends to leave theory early
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, d: Dict) -> 'OpeningRepertoire':
        return cls(
            white_main_opening=d.get("white_main_opening", "e4"),
            white_openings_played=d.get("white_openings_played", {}),
            white_openings_win_rate=d.get("white_openings_win_rate", {}),
            black_vs_e4_main=d.get("black_vs_e4_main", "e5"),
            black_vs_e4_played=d.get("black_vs_e4_played", {}),
            black_vs_e4_win_rate=d.get("black_vs_e4_win_rate", {}),
            black_vs_d4_main=d.get("black_vs_d4_main", "d5"),
            black_vs_d4_played=d.get("black_vs_d4_played", {}),
            black_vs_d4_win_rate=d.get("black_vs_d4_win_rate", {}),
            traps_known=d.get("traps_known", []),
            traps_fell_for=d.get("traps_fell_for", []),
            traps_success_rate=d.get("traps_success_rate", {}),
            average_book_moves=d.get("average_book_moves", 5.0),
            deviates_early=d.get("deviates_early", False)
        )


@dataclass
class PatternHistoryEntry:
    """A single pattern occurrence for cross-game reference"""
    pattern_type: str  # BlunderType value
    game_id: str
    move_number: int
    opponent: str
    date: datetime
    description: str  # "Missed knight fork, lost queen"
    
    def to_dict(self) -> Dict:
        return {
            "pattern_type": self.pattern_type,
            "game_id": self.game_id,
            "move_number": self.move_number,
            "opponent": self.opponent,
            "date": self.date.isoformat(),
            "description": self.description
        }
    
    @classmethod
    def from_dict(cls, d: Dict) -> 'PatternHistoryEntry':
        return cls(
            pattern_type=d["pattern_type"],
            game_id=d["game_id"],
            move_number=d["move_number"],
            opponent=d.get("opponent", "unknown"),
            date=datetime.fromisoformat(d["date"]) if isinstance(d.get("date"), str) else datetime.now(timezone.utc),
            description=d.get("description", "")
        )


@dataclass
class LearningVelocity:
    """How fast user improves on different areas"""
    # Per pattern type: games since last occurrence
    pattern_gaps: Dict[str, int] = field(default_factory=dict)
    
    # Improvement tracking
    improving_areas: List[str] = field(default_factory=list)
    stagnant_areas: List[str] = field(default_factory=list)
    worsening_areas: List[str] = field(default_factory=list)
    
    # Overall velocity
    overall_improvement_rate: float = 0.0  # -1 to 1
    games_analyzed: int = 0
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, d: Dict) -> 'LearningVelocity':
        return cls(
            pattern_gaps=d.get("pattern_gaps", {}),
            improving_areas=d.get("improving_areas", []),
            stagnant_areas=d.get("stagnant_areas", []),
            worsening_areas=d.get("worsening_areas", []),
            overall_improvement_rate=d.get("overall_improvement_rate", 0.0),
            games_analyzed=d.get("games_analyzed", 0)
        )


# =============================================================================
# MAIN PLAYER IDENTITY DOCUMENT
# =============================================================================

@dataclass
class PlayerIdentity:
    """
    THE COMPLETE PLAYER PROFILE
    
    This is the master document that captures everything about a player.
    Updated after every game, used in every coaching interaction.
    """
    user_id: str
    created_at: datetime
    updated_at: datetime
    
    # Core metrics
    games_analyzed: int = 0
    total_wins: int = 0
    total_losses: int = 0
    total_draws: int = 0
    current_rating: int = 1200
    peak_rating: int = 1200
    
    # The 7 pillars of identity
    blunder_taxonomy: BlunderTaxonomy = field(default_factory=BlunderTaxonomy)
    style_profile: StyleProfile = field(default_factory=StyleProfile)
    behavioral_profile: BehavioralProfile = field(default_factory=BehavioralProfile)
    opening_repertoire: OpeningRepertoire = field(default_factory=OpeningRepertoire)
    learning_velocity: LearningVelocity = field(default_factory=LearningVelocity)
    
    # Pattern history for "remember when..." (last 100)
    pattern_history: List[PatternHistoryEntry] = field(default_factory=list)
    
    # Recent blunders for detailed analysis (last 50)
    recent_blunders: List[BlunderRecord] = field(default_factory=list)
    
    # Session tracking
    current_session_games: int = 0
    current_session_result: str = ""  # "WWL" = win, win, loss
    last_game_result: str = ""
    consecutive_losses: int = 0
    consecutive_wins: int = 0
    
    # Coach notes (generated insights)
    coach_notes: List[str] = field(default_factory=list)
    priority_focus: Optional[str] = None  # Current training focus
    
    def to_dict(self) -> Dict:
        return {
            "user_id": self.user_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "games_analyzed": self.games_analyzed,
            "total_wins": self.total_wins,
            "total_losses": self.total_losses,
            "total_draws": self.total_draws,
            "current_rating": self.current_rating,
            "peak_rating": self.peak_rating,
            "blunder_taxonomy": self.blunder_taxonomy.to_dict(),
            "style_profile": self.style_profile.to_dict(),
            "behavioral_profile": self.behavioral_profile.to_dict(),
            "opening_repertoire": self.opening_repertoire.to_dict(),
            "learning_velocity": self.learning_velocity.to_dict(),
            "pattern_history": [p.to_dict() for p in self.pattern_history],
            "recent_blunders": [b.to_dict() for b in self.recent_blunders],
            "current_session_games": self.current_session_games,
            "current_session_result": self.current_session_result,
            "last_game_result": self.last_game_result,
            "consecutive_losses": self.consecutive_losses,
            "consecutive_wins": self.consecutive_wins,
            "coach_notes": self.coach_notes,
            "priority_focus": self.priority_focus
        }
    
    @classmethod
    def from_dict(cls, d: Dict) -> 'PlayerIdentity':
        return cls(
            user_id=d["user_id"],
            created_at=datetime.fromisoformat(d["created_at"]) if isinstance(d.get("created_at"), str) else d.get("created_at", datetime.now(timezone.utc)),
            updated_at=datetime.fromisoformat(d["updated_at"]) if isinstance(d.get("updated_at"), str) else d.get("updated_at", datetime.now(timezone.utc)),
            games_analyzed=d.get("games_analyzed", 0),
            total_wins=d.get("total_wins", 0),
            total_losses=d.get("total_losses", 0),
            total_draws=d.get("total_draws", 0),
            current_rating=d.get("current_rating", 1200),
            peak_rating=d.get("peak_rating", 1200),
            blunder_taxonomy=BlunderTaxonomy.from_dict(d.get("blunder_taxonomy", {})),
            style_profile=StyleProfile.from_dict(d.get("style_profile", {})),
            behavioral_profile=BehavioralProfile.from_dict(d.get("behavioral_profile", {})),
            opening_repertoire=OpeningRepertoire.from_dict(d.get("opening_repertoire", {})),
            learning_velocity=LearningVelocity.from_dict(d.get("learning_velocity", {})),
            pattern_history=[PatternHistoryEntry.from_dict(p) for p in d.get("pattern_history", [])],
            recent_blunders=[BlunderRecord.from_dict(b) for b in d.get("recent_blunders", [])],
            current_session_games=d.get("current_session_games", 0),
            current_session_result=d.get("current_session_result", ""),
            last_game_result=d.get("last_game_result", ""),
            consecutive_losses=d.get("consecutive_losses", 0),
            consecutive_wins=d.get("consecutive_wins", 0),
            coach_notes=d.get("coach_notes", []),
            priority_focus=d.get("priority_focus")
        )


# =============================================================================
# PLAYER IDENTITY SERVICE
# =============================================================================

class PlayerIdentityService:
    """
    Service for managing player identities.
    
    Core operations:
    - get_or_create: Get existing or create new identity
    - update_after_game: Update identity after game analysis
    - get_coaching_context: Get memory context for coaching prompts
    - find_similar_pattern: Find past games with same pattern
    """
    
    COLLECTION = "player_identities"
    MAX_PATTERN_HISTORY = 100
    MAX_RECENT_BLUNDERS = 50
    
    def __init__(self, db):
        self.db = db
    
    async def get_or_create(self, user_id: str) -> PlayerIdentity:
        """Get existing identity or create new one"""
        doc = await self.db[self.COLLECTION].find_one({"user_id": user_id})
        
        if doc:
            doc.pop("_id", None)
            return PlayerIdentity.from_dict(doc)
        
        # Create new identity
        now = datetime.now(timezone.utc)
        identity = PlayerIdentity(
            user_id=user_id,
            created_at=now,
            updated_at=now
        )
        
        await self.db[self.COLLECTION].insert_one(identity.to_dict())
        logger.info(f"Created new player identity for {user_id}")
        
        return identity
    
    async def save(self, identity: PlayerIdentity):
        """Save identity to database"""
        identity.updated_at = datetime.now(timezone.utc)
        
        await self.db[self.COLLECTION].replace_one(
            {"user_id": identity.user_id},
            identity.to_dict(),
            upsert=True
        )
    
    async def update_after_game(
        self,
        user_id: str,
        game_id: str,
        game_result: str,  # "win", "loss", "draw"
        user_color: str,
        opponent: str,
        moves_analysis: List[Dict],  # List of move evaluations
        opening_played: Optional[str],
        game_phases: Dict[str, int],  # {opening: 10, middlegame: 25, endgame: 10}
        time_data: Optional[Dict] = None,  # Move times, time trouble, etc.
        rating_after: Optional[int] = None
    ) -> PlayerIdentity:
        """
        Update player identity after a game.
        
        This is THE KEY FUNCTION that builds the memory.
        Called after every analyzed game.
        """
        identity = await self.get_or_create(user_id)
        now = datetime.now(timezone.utc)
        
        # ===========================================
        # 1. UPDATE BASIC STATS
        # ===========================================
        identity.games_analyzed += 1
        
        if game_result == "win":
            identity.total_wins += 1
            identity.consecutive_wins += 1
            identity.consecutive_losses = 0
        elif game_result == "loss":
            identity.total_losses += 1
            identity.consecutive_losses += 1
            identity.consecutive_wins = 0
        else:
            identity.total_draws += 1
            identity.consecutive_wins = 0
            identity.consecutive_losses = 0
        
        identity.last_game_result = game_result
        identity.current_session_result += game_result[0].upper()
        identity.current_session_games += 1
        
        if rating_after:
            identity.current_rating = rating_after
            if rating_after > identity.peak_rating:
                identity.peak_rating = rating_after
        
        # ===========================================
        # 2. ANALYZE BLUNDERS (THE CORE)
        # ===========================================
        blunders_this_game = []
        
        for i, move in enumerate(moves_analysis):
            cp_loss = move.get("cp_loss", 0)
            
            # Only analyze significant mistakes
            if cp_loss < 100:
                continue
            
            
            # Classify the blunder type
            blunder_type = self._classify_blunder(
                fen=move.get("fen_before", ""),
                move_played=move.get("move", ""),
                best_move=move.get("best_move", ""),
                cp_loss=cp_loss,
                time_spent=move.get("time_spent", 10),
                time_remaining=move.get("time_remaining", 300),
                eval_before=move.get("eval_before", 0)
            )
            
            # Determine game phase
            move_num = move.get("move_number", i // 2 + 1)
            if move_num <= game_phases.get("opening", 10):
                phase = GamePhase.OPENING
            elif move_num <= game_phases.get("opening", 10) + game_phases.get("middlegame", 20):
                phase = GamePhase.MIDDLEGAME
            else:
                phase = GamePhase.ENDGAME
            
            # Was winning before blunder?
            eval_before = move.get("eval_before", 0)
            was_winning = (user_color == "white" and eval_before > 1.0) or \
                         (user_color == "black" and eval_before < -1.0)
            
            # Create blunder record
            blunder = BlunderRecord(
                blunder_type=blunder_type,
                game_id=game_id,
                move_number=move_num,
                fen_before=move.get("fen_before", ""),
                move_played=move.get("move", ""),
                best_move=move.get("best_move", ""),
                cp_loss=cp_loss,
                phase=phase,
                time_spent=move.get("time_spent", 10),
                time_remaining=move.get("time_remaining", 300),
                eval_before=eval_before,
                opponent=opponent,
                date=now,
                was_winning=was_winning,
                piece_lost=self._detect_piece_lost(move.get("fen_before", ""), move.get("move", "")),
                tactical_theme=self._detect_tactical_theme(move.get("fen_before", ""), move.get("best_move", ""))
            )
            
            blunders_this_game.append(blunder)
            
            # Track time trouble
            if move.get("time_remaining", 300) < 60:
                pass
            
            # Add to pattern history
            pattern_entry = PatternHistoryEntry(
                pattern_type=blunder_type.value,
                game_id=game_id,
                move_number=move_num,
                opponent=opponent,
                date=now,
                description=self._generate_blunder_description(blunder)
            )
            identity.pattern_history.append(pattern_entry)
        
        # Trim pattern history
        if len(identity.pattern_history) > self.MAX_PATTERN_HISTORY:
            identity.pattern_history = identity.pattern_history[-self.MAX_PATTERN_HISTORY:]
        
        # Add to recent blunders
        identity.recent_blunders.extend(blunders_this_game)
        if len(identity.recent_blunders) > self.MAX_RECENT_BLUNDERS:
            identity.recent_blunders = identity.recent_blunders[-self.MAX_RECENT_BLUNDERS:]
        
        # ===========================================
        # 3. UPDATE BLUNDER TAXONOMY
        # ===========================================
        self._update_blunder_taxonomy(identity, blunders_this_game)
        
        # ===========================================
        # 4. UPDATE STYLE PROFILE
        # ===========================================
        self._update_style_profile(identity, moves_analysis, user_color, opening_played)
        
        # ===========================================
        # 5. UPDATE BEHAVIORAL PROFILE
        # ===========================================
        self._update_behavioral_profile(
            identity, 
            blunders_this_game, 
            moves_analysis, 
            time_data,
            game_result
        )
        
        # ===========================================
        # 6. UPDATE OPENING REPERTOIRE
        # ===========================================
        self._update_opening_repertoire(identity, user_color, opening_played, game_result)
        
        # ===========================================
        # 7. UPDATE LEARNING VELOCITY
        # ===========================================
        self._update_learning_velocity(identity, blunders_this_game)
        
        # ===========================================
        # 8. GENERATE COACH NOTES
        # ===========================================
        self._generate_coach_notes(identity, blunders_this_game, game_result)
        
        # Save
        await self.save(identity)
        
        logger.info(f"Updated player identity for {user_id}: {len(blunders_this_game)} blunders analyzed")
        
        return identity
    
    def _classify_blunder(
        self,
        fen: str,
        move_played: str,
        best_move: str,
        cp_loss: int,
        time_spent: float,
        time_remaining: float,
        eval_before: float
    ) -> BlunderType:
        """Classify a blunder into specific type"""
        
        # Time-based classifications first
        if time_remaining < 30:
            return BlunderType.TIME_TROUBLE_BLUNDER
        
        if time_spent < 2:
            return BlunderType.IMPULSE_MOVE
        
        try:
            board = chess.Board(fen)
            
            # Check for hanging piece
            if self._is_hanging_piece_blunder(board, move_played):
                return BlunderType.HANGING_PIECE
            
            # Check for missed tactics
            if self._is_missed_fork(board, best_move):
                return BlunderType.MISSED_FORK
            
            if self._is_missed_pin(board, best_move):
                return BlunderType.MISSED_PIN
            
            # Check for king safety
            if self._is_king_safety_issue(board, move_played):
                return BlunderType.KING_SAFETY_NEGLECT
            
            # Check for winning position collapse
            if eval_before > 2.0 and cp_loss > 300:
                return BlunderType.WINNING_POSITION_COLLAPSE
            
            # Default to calculation error for large cp loss
            if cp_loss > 200:
                return BlunderType.CALCULATION_ERROR
            
        except Exception as e:
            logger.warning(f"Error classifying blunder: {e}")
        
        return BlunderType.UNCLEAR
    
    def _is_hanging_piece_blunder(self, board: chess.Board, move: str) -> bool:
        """Check if move leaves a piece hanging"""
        try:
            m = board.parse_san(move)
            board_after = board.copy()
            board_after.push(m)
            
            # Check if any of our pieces are now undefended and attacked
            color = not board_after.turn  # We just moved
            for square in chess.SQUARES:
                piece = board_after.piece_at(square)
                if piece and piece.color == color and piece.piece_type != chess.KING:
                    if board_after.is_attacked_by(not color, square):
                        if not board_after.is_attacked_by(color, square):
                            return True
            return False
        except:
            return False
    
    def _is_missed_fork(self, board: chess.Board, best_move: str) -> bool:
        """Check if best move was a fork"""
        try:
            m = board.parse_san(best_move)
            board_after = board.copy()
            board_after.push(m)
            
            to_sq = m.to_square
            piece = board_after.piece_at(to_sq)
            if not piece:
                return False
            
            # Count high-value pieces attacked
            attacked_value = 0
            for sq in board_after.attacks(to_sq):
                target = board_after.piece_at(sq)
                if target and target.color != piece.color:
                    if target.piece_type == chess.KING:
                        attacked_value += 100
                    elif target.piece_type == chess.QUEEN:
                        attacked_value += 9
                    elif target.piece_type == chess.ROOK:
                        attacked_value += 5
            
            return attacked_value >= 14  # King + something or Queen + Rook
        except:
            return False
    
    def _is_missed_pin(self, board: chess.Board, best_move: str) -> bool:
        """Check if best move creates a pin"""
        try:
            m = board.parse_san(best_move)
            piece = board.piece_at(m.from_square)
            
            # Pins are usually by bishops, rooks, queens
            if piece and piece.piece_type in [chess.BISHOP, chess.ROOK, chess.QUEEN]:
                return True  # Simplified
        except:
            pass
        return False
    
    def _is_king_safety_issue(self, board: chess.Board, move: str) -> bool:
        """Check if move compromises king safety"""
        try:
            m = board.parse_san(move)
            piece = board.piece_at(m.from_square)
            
            # Moving king-side pawns when king is castled there
            if piece and piece.piece_type == chess.PAWN:
                file = chess.square_file(m.from_square)
                if file in [5, 6, 7]:  # f, g, h files
                    return True
        except:
            pass
        return False
    
    def _detect_piece_lost(self, fen: str, move: str) -> Optional[str]:
        """Detect which piece was lost, if any"""
        try:
            board = chess.Board(fen)
            m = board.parse_san(move)
            
            # If it's a capture, see what we captured vs what we lose
            if board.is_capture(m):
                captured = board.piece_at(m.to_square)
                if captured:
                    return chess.piece_name(captured.piece_type)
        except:
            pass
        return None
    
    def _detect_tactical_theme(self, fen: str, best_move: str) -> Optional[str]:
        """Detect the tactical theme of the best move"""
        try:
            board = chess.Board(fen)
            board.parse_san(best_move)
            
            if self._is_missed_fork(board, best_move):
                return "fork"
            if self._is_missed_pin(board, best_move):
                return "pin"
            if board.is_check():
                return "check"
        except:
            pass
        return None
    
    def _generate_blunder_description(self, blunder: BlunderRecord) -> str:
        """Generate human-readable blunder description"""
        type_descriptions = {
            BlunderType.MISSED_FORK: f"Missed fork on move {blunder.move_number}",
            BlunderType.MISSED_PIN: f"Missed pin on move {blunder.move_number}",
            BlunderType.HANGING_PIECE: f"Left piece hanging on move {blunder.move_number}",
            BlunderType.TIME_TROUBLE_BLUNDER: f"Time trouble blunder on move {blunder.move_number}",
            BlunderType.IMPULSE_MOVE: f"Impulse move (<2s) on move {blunder.move_number}",
            BlunderType.KING_SAFETY_NEGLECT: f"King safety ignored on move {blunder.move_number}",
            BlunderType.WINNING_POSITION_COLLAPSE: f"Collapsed from winning position on move {blunder.move_number}",
            BlunderType.CALCULATION_ERROR: f"Calculation error on move {blunder.move_number}",
        }
        
        desc = type_descriptions.get(blunder.blunder_type, f"Blunder on move {blunder.move_number}")
        
        if blunder.piece_lost:
            desc += f", lost {blunder.piece_lost}"
        
        return desc
    
    def _update_blunder_taxonomy(self, identity: PlayerIdentity, blunders: List[BlunderRecord]):
        """Update blunder taxonomy with new blunders"""
        tax = identity.blunder_taxonomy
        
        for b in blunders:
            tax.total_blunders += 1
            
            # By type
            type_key = b.blunder_type.value
            tax.by_type[type_key] = tax.by_type.get(type_key, 0) + 1
            
            # By piece
            if b.piece_lost:
                tax.by_piece[b.piece_lost] = tax.by_piece.get(b.piece_lost, 0) + 1
            
            # By phase
            phase_key = b.phase.value
            tax.by_phase[phase_key] = tax.by_phase.get(phase_key, 0) + 1
            
            # By context
            if b.was_winning:
                tax.when_winning += 1
            elif b.eval_before < -0.5:
                tax.when_losing += 1
            else:
                tax.when_equal += 1
            
            # Time-related
            if b.time_remaining < 60:
                tax.under_time_pressure += 1
            if b.time_spent < 2:
                tax.impulse_moves += 1
        
        # Calculate trends (last 10 vs previous 10 games)
        recent = identity.recent_blunders[-20:]
        if len(recent) >= 10:
            recent_10 = recent[-10:]
            older_10 = recent[-20:-10] if len(recent) >= 20 else []
            
            tax.recent_rate = len(recent_10) / 10
            tax.historical_rate = len(older_10) / 10 if older_10 else tax.recent_rate
            
            if tax.recent_rate < tax.historical_rate * 0.7:
                tax.trend = "improving"
            elif tax.recent_rate > tax.historical_rate * 1.3:
                tax.trend = "worsening"
            else:
                tax.trend = "stable"
        
        # Find most common
        if tax.by_type:
            tax.most_common_type = BlunderType(max(tax.by_type, key=tax.by_type.get))
        
        if tax.by_piece:
            tax.most_vulnerable_piece = max(tax.by_piece, key=tax.by_piece.get)
        
        if tax.by_phase:
            tax.worst_phase = GamePhase(max(tax.by_phase, key=tax.by_phase.get))
    
    def _update_style_profile(
        self, 
        identity: PlayerIdentity, 
        moves: List[Dict],
        user_color: str,
        opening: Optional[str]
    ):
        """Update style profile based on moves"""
        style = identity.style_profile
        
        # Count aggressive vs positional moves
        pawn_pushes = 0
        piece_trades = 0
        quiet_moves = 0
        
        for move in moves:
            move_san = move.get("move", "")
            if move_san and not move_san[0].isupper():
                pawn_pushes += 1
            if "x" in move_san:
                piece_trades += 1
            if "x" not in move_san and "+" not in move_san:
                quiet_moves += 1
        
        total_moves = len(moves) or 1
        
        # Update scores with exponential moving average
        alpha = 0.1
        style.aggression_score = style.aggression_score * (1 - alpha) + (pawn_pushes / total_moves) * alpha
        style.positional_score = style.positional_score * (1 - alpha) + (quiet_moves / total_moves) * alpha
        
        # Classify style
        if identity.games_analyzed >= 10:
            style.confidence = min(0.9, identity.games_analyzed / 50)
            
            if style.aggression_score > 0.6:
                style.primary_style = PlayStyle.AGGRESSIVE
            elif style.positional_score > 0.6:
                style.primary_style = PlayStyle.POSITIONAL
            elif style.tactical_score > 0.6:
                style.primary_style = PlayStyle.TACTICAL
            else:
                style.primary_style = PlayStyle.UNIVERSAL
    
    def _update_behavioral_profile(
        self,
        identity: PlayerIdentity,
        blunders: List[BlunderRecord],
        moves: List[Dict],
        time_data: Optional[Dict],
        result: str
    ):
        """Update behavioral profile"""
        beh = identity.behavioral_profile
        
        # Check for tilt
        if identity.consecutive_losses >= 2:
            beh.tilt_trigger = TiltTrigger.CONSECUTIVE_LOSSES
            beh.tilt_detected_count += 1
        
        # Time management
        if time_data:
            if time_data.get("ended_in_time_trouble"):
                games = identity.games_analyzed or 1
                beh.time_trouble_frequency = (beh.time_trouble_frequency * (games - 1) + 1) / games
        
        # Post-blunder behavior
        if blunders:
            impulse_count = sum(1 for b in blunders if b.blunder_type == BlunderType.IMPULSE_MOVE)
            if impulse_count >= 2:
                beh.blunder_spiral_rate = min(1.0, beh.blunder_spiral_rate + 0.1)
        
        # Consistency
        alpha = 0.1
        if result == identity.last_game_result:
            beh.consistency_score = beh.consistency_score * (1 - alpha) + 1.0 * alpha
        else:
            beh.consistency_score = beh.consistency_score * (1 - alpha) + 0.5 * alpha
    
    def _update_opening_repertoire(
        self,
        identity: PlayerIdentity,
        user_color: str,
        opening: Optional[str],
        result: str
    ):
        """Update opening repertoire"""
        if not opening:
            return
        
        rep = identity.opening_repertoire
        
        if user_color == "white":
            rep.white_openings_played[opening] = rep.white_openings_played.get(opening, 0) + 1
            
            # Update win rate
            games = rep.white_openings_played[opening]
            old_rate = rep.white_openings_win_rate.get(opening, 0.5)
            win = 1.0 if result == "win" else (0.5 if result == "draw" else 0.0)
            rep.white_openings_win_rate[opening] = ((old_rate * (games - 1)) + win) / games
            
            # Update main opening
            if rep.white_openings_played[opening] > rep.white_openings_played.get(rep.white_main_opening, 0):
                rep.white_main_opening = opening
        else:
            # Track Black openings similarly
            rep.black_vs_e4_played[opening] = rep.black_vs_e4_played.get(opening, 0) + 1
    
    def _update_learning_velocity(self, identity: PlayerIdentity, blunders: List[BlunderRecord]):
        """Update learning velocity tracking"""
        vel = identity.learning_velocity
        vel.games_analyzed = identity.games_analyzed
        
        # Track pattern gaps
        blunder_types_this_game = {b.blunder_type.value for b in blunders}
        
        for pattern in BlunderType:
            key = pattern.value
            if key in blunder_types_this_game:
                vel.pattern_gaps[key] = 0
            else:
                vel.pattern_gaps[key] = vel.pattern_gaps.get(key, 0) + 1
        
        # Classify areas
        vel.improving_areas = [k for k, v in vel.pattern_gaps.items() if v >= 10]
        vel.stagnant_areas = [k for k, v in vel.pattern_gaps.items() if 3 <= v < 10]
        vel.worsening_areas = [k for k, v in vel.pattern_gaps.items() if v < 3 and k in [b.blunder_type.value for b in identity.recent_blunders[-10:]]]
    
    def _generate_coach_notes(
        self,
        identity: PlayerIdentity,
        blunders: List[BlunderRecord],
        result: str
    ):
        """Generate coach notes and priority focus"""
        notes = []
        
        # Note about most common blunder
        if identity.blunder_taxonomy.most_common_type:
            notes.append(f"Primary weakness: {identity.blunder_taxonomy.most_common_type.value}")
        
        # Note about trend
        if identity.blunder_taxonomy.trend == "improving":
            notes.append("Blunder rate is improving!")
        elif identity.blunder_taxonomy.trend == "worsening":
            notes.append("Blunder rate increasing - need focus")
        
        # Note about tilt
        if identity.consecutive_losses >= 2:
            notes.append(f"On a {identity.consecutive_losses}-game losing streak - may be tilted")
        
        # Set priority focus
        if identity.blunder_taxonomy.most_common_type:
            identity.priority_focus = identity.blunder_taxonomy.most_common_type.value
        
        identity.coach_notes = notes[-5:]  # Keep last 5

    # =========================================================================
    # MEMORY RETRIEVAL FOR COACHING
    # =========================================================================
    
    async def get_coaching_context(self, user_id: str) -> Dict[str, Any]:
        """
        Get complete coaching context for prompts.
        
        THIS IS THE KEY FUNCTION - called before every coaching message.
        Returns everything needed for personalized coaching.
        """
        identity = await self.get_or_create(user_id)
        
        return {
            # Basic info
            "games_played": identity.games_analyzed,
            "current_rating": identity.current_rating,
            "win_rate": identity.total_wins / max(identity.games_analyzed, 1),
            
            # Blunder profile
            "blunder_profile": {
                "most_common": identity.blunder_taxonomy.most_common_type.value if identity.blunder_taxonomy.most_common_type else None,
                "trend": identity.blunder_taxonomy.trend,
                "worst_phase": identity.blunder_taxonomy.worst_phase.value if identity.blunder_taxonomy.worst_phase else None,
                "impulse_rate": identity.blunder_taxonomy.impulse_moves / max(identity.blunder_taxonomy.total_blunders, 1),
                "time_trouble_rate": identity.blunder_taxonomy.under_time_pressure / max(identity.blunder_taxonomy.total_blunders, 1),
            },
            
            # Style
            "style": {
                "primary": identity.style_profile.primary_style.value,
                "aggression": identity.style_profile.aggression_score,
                "endgame_comfort": identity.style_profile.endgame_comfort,
            },
            
            # Behavior
            "behavior": {
                "tilt_trigger": identity.behavioral_profile.tilt_trigger.value,
                "consecutive_losses": identity.consecutive_losses,
                "is_tilted": identity.consecutive_losses >= 2,
                "consistency": identity.behavioral_profile.consistency_score,
            },
            
            # Current focus
            "priority_focus": identity.priority_focus,
            "coach_notes": identity.coach_notes,
            
            # For "remember when..."
            "has_pattern_history": len(identity.pattern_history) > 0,
            "recent_patterns": [p.pattern_type for p in identity.pattern_history[-5:]],
        }
    
    async def find_similar_pattern(
        self,
        user_id: str,
        current_pattern: BlunderType,
        current_game_id: Optional[str] = None
    ) -> Optional[Dict]:
        """
        Find a similar pattern from history for "remember when..." coaching.
        
        Returns exact game reference for verification.
        """
        identity = await self.get_or_create(user_id)
        
        # Search pattern history
        for entry in reversed(identity.pattern_history):
            if entry.pattern_type == current_pattern.value:
                if current_game_id and entry.game_id == current_game_id:
                    continue  # Skip current game
                
                # Format time ago
                days_ago = (datetime.now(timezone.utc) - entry.date.replace(tzinfo=timezone.utc)).days
                if days_ago == 0:
                    when = "earlier today"
                elif days_ago == 1:
                    when = "yesterday"
                elif days_ago < 7:
                    when = f"{days_ago} days ago"
                else:
                    when = f"on {entry.date.strftime('%b %d')}"
                
                return {
                    "found": True,
                    "game_id": entry.game_id,
                    "move_number": entry.move_number,
                    "opponent": entry.opponent,
                    "when": when,
                    "description": entry.description,
                    "pattern_type": entry.pattern_type
                }
        
        return None
    
    async def get_pattern_frequency(self, user_id: str, pattern: BlunderType) -> Dict:
        """Get frequency data for a specific pattern"""
        identity = await self.get_or_create(user_id)
        
        total = identity.blunder_taxonomy.by_type.get(pattern.value, 0)
        recent = sum(1 for p in identity.pattern_history[-20:] if p.pattern_type == pattern.value)
        
        return {
            "pattern": pattern.value,
            "total_occurrences": total,
            "recent_occurrences": recent,
            "is_recurring": total >= 3,
            "is_improving": pattern.value in identity.learning_velocity.improving_areas
        }


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

async def get_player_identity_service(db) -> PlayerIdentityService:
    """Factory function"""
    return PlayerIdentityService(db)


async def get_coaching_memory(db, user_id: str) -> Dict[str, Any]:
    """
    Quick access to coaching memory context.
    
    Use this in coaching prompts:
    memory = await get_coaching_memory(db, user_id)
    """
    service = PlayerIdentityService(db)
    return await service.get_coaching_context(user_id)


async def record_game_to_memory(
    db,
    user_id: str,
    game_id: str,
    game_result: str,
    user_color: str,
    opponent: str,
    moves_analysis: List[Dict],
    opening_played: Optional[str] = None,
    game_phases: Optional[Dict] = None,
    time_data: Optional[Dict] = None,
    rating_after: Optional[int] = None
) -> PlayerIdentity:
    """
    Record a game to player memory.
    
    Call this after every game analysis.
    """
    service = PlayerIdentityService(db)
    
    phases = game_phases or {"opening": 10, "middlegame": 25, "endgame": 10}
    
    return await service.update_after_game(
        user_id=user_id,
        game_id=game_id,
        game_result=game_result,
        user_color=user_color,
        opponent=opponent,
        moves_analysis=moves_analysis,
        opening_played=opening_played,
        game_phases=phases,
        time_data=time_data,
        rating_after=rating_after
    )


async def find_pattern_in_history(
    db,
    user_id: str,
    pattern: BlunderType,
    current_game_id: Optional[str] = None
) -> Optional[Dict]:
    """
    Find a past occurrence of a pattern.
    
    For "remember when..." coaching.
    """
    service = PlayerIdentityService(db)
    return await service.find_similar_pattern(user_id, pattern, current_game_id)
