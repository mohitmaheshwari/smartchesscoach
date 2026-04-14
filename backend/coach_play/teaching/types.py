"""
Core types for the teaching move selector v2.

Design principle: score resulting POSITIONS, not move labels.
One intent per move selection. Structured breakdowns for every decision.
"""

import chess
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Optional


class TeachingIntent(str, Enum):
    """What the coach is trying to teach with this move."""
    HANGING_PIECE_PUNISHMENT = "hanging_piece_punishment"
    FORK_OPPORTUNITY = "fork_opportunity"
    THREAT_AWARENESS = "threat_awareness"
    # Phase 2 (not yet):
    # KING_EXPOSURE_PRESSURE = "king_exposure_pressure"
    # SIMPLIFY_TO_ENDGAME = "simplify_to_endgame"


@dataclass
class CandidateMove:
    """A candidate move from the engine with evaluation."""
    move: chess.Move
    san: str
    eval_cp: int
    eval_rank: int  # 1 = best engine move
    pv: Optional[List[chess.Move]] = None


@dataclass
class HangingPieceInfo:
    """A piece that is attacked and not adequately defended."""
    square: int
    piece_type: int  # chess.KNIGHT, etc.
    piece_value: int  # 1=pawn, 3=minor, 5=rook, 9=queen
    attacker_squares: List[int] = field(default_factory=list)
    defender_count: int = 0
    attacker_count: int = 0


@dataclass
class ForkInfo:
    """A piece forking multiple targets."""
    forker_square: int
    forker_type: int
    target_squares: List[int] = field(default_factory=list)
    target_types: List[int] = field(default_factory=list)
    total_target_value: int = 0


@dataclass
class PositionFeatures:
    """Features extracted from a resulting position after a candidate move."""
    # Hanging pieces (opponent's pieces we can capture)
    opponent_hanging: List[HangingPieceInfo] = field(default_factory=list)
    opponent_underdefended: List[HangingPieceInfo] = field(default_factory=list)

    # Fork opportunities (our pieces forking opponent pieces)
    fork_opportunities: List[ForkInfo] = field(default_factory=list)

    # Threats we create
    checks_available: int = 0
    captures_available: int = 0
    high_value_attacks: int = 0  # attacks on Q/R

    # King exposure (phase 2)
    # opponent_king_zone_attacks: int = 0
    # open_file_to_king: bool = False
    # opponent_king_exposed: bool = False

    # Simplification (phase 2)
    # material_delta_after: int = 0


@dataclass
class IntentScore:
    """Score breakdown for a single candidate move against a single intent."""
    intent: TeachingIntent
    raw_score: float  # 0.0+ from pattern detectors
    sub_scores: Dict[str, float] = field(default_factory=dict)
    engine_quality: float = 0.0  # 0.0-1.0
    final_score: float = 0.0
    explanation: str = ""


@dataclass
class MoveSelection:
    """Final result of move selection."""
    selected_move: chess.Move
    selected_san: str
    intent: TeachingIntent
    intent_reason: str  # why this intent was chosen
    score_breakdown: IntentScore
    all_candidates: List[IntentScore] = field(default_factory=list)
    eval_cp: int = 0
    eval_rank: int = 0
    feasibility_fallbacks: int = 0  # how many intents were tried before finding a feasible one


# Piece values used throughout
PIECE_VALUES = {
    chess.PAWN: 1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9,
    chess.KING: 0,  # not capturable
}
