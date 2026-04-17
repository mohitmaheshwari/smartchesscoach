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
    PIN_EXPLOITATION = "pin_exploitation"
    SKEWER_OPPORTUNITY = "skewer_opportunity"
    DISCOVERED_ATTACK = "discovered_attack"
    OVERLOADED_PIECE = "overloaded_piece"


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

    # Threats we create (from count_forcing_moves)
    checks_available: int = 0
    captures_available: int = 0
    high_value_attacks: int = 0  # attacks on Q/R

    # Enriched threat data (quality, not just quantity)
    safe_captures: int = 0       # captures that win material or are free
    attacks_on_undefended: int = 0  # pieces under attack with no defender
    material_gain_possible: int = 0  # total cp gain from safe captures

    # Pins student can exploit (from mistake_classifier.find_pins)
    pin_count: int = 0
    best_pin_value: int = 0      # Value of best pinned piece
    has_absolute_pin: bool = False
    pin_details: List[Dict] = field(default_factory=list)

    # Skewers student can exploit (from mistake_classifier.find_skewers)
    skewer_count: int = 0
    best_skewer_gain: int = 0    # Value of piece won when front moves
    skewer_details: List[Dict] = field(default_factory=list)

    # Discovered attacks student can make (from mistake_classifier.find_discovered_attacks)
    discovery_count: int = 0
    has_discovered_check: bool = False
    best_discovery_value: int = 0
    discovery_details: List[Dict] = field(default_factory=list)

    # Overloaded coach pieces student can exploit (from mistake_classifier.find_overloaded_defenders)
    overloaded_count: int = 0
    best_overload_value: int = 0
    overload_details: List[Dict] = field(default_factory=list)


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

    # Opportunity tracking — what pattern did this move create for the student?
    # Populated by analyze_position on the resulting board after this move.
    created_opportunity: Optional[str] = None  # e.g. "pin", "fork", "skewer", None
    opportunity_details: Dict = field(default_factory=dict)  # target squares, exploit moves, skill explanation


# Piece values used throughout
PIECE_VALUES = {
    chess.PAWN: 1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9,
    chess.KING: 0,  # not capturable
}
