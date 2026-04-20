"""
PositionFacts — single source of truth for "what is this position/move?"

Composes existing extractors into one typed object. Does NOT reimplement anything.
Every downstream classifier, template, LLM prompt should read from PositionFacts
instead of peeking at the board directly.

Delegates to:
  - coach_play.teaching.pattern_detectors  (hanging, fork, forcing moves)
  - mistake_classifier                     (pins, skewers, discovered, overload, phase)
  - services.position_reader               (pawn shield, center control, development)
  - services.escape_squares_service        (king mobility)
  - services.opening_mastery               (opening name/key/variation)
  - stockfish_service (optional)           (eval, best move, cp_loss)

Adds ONE thing new: `move_category` — classifies where the move went, which the
old dispatchers ignored (the a3-labeled-as-center bug).
"""

import chess
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Optional, Any

from coach_play.teaching.pattern_detectors import (
    find_hanging_pieces as _find_hanging,
    find_fork_opportunities as _find_forks,
    count_forcing_moves as _count_forcing,
)
from coach_play.teaching.types import HangingPieceInfo, ForkInfo
from mistake_classifier import (
    find_pins as _find_pins,
    find_skewers as _find_skewers,
    find_discovered_attacks as _find_discovered,
    find_overloaded_defenders as _find_overloaded,
    determine_phase as _determine_phase,
    GamePhase,
)


CENTER_SQUARES = {chess.D4, chess.D5, chess.E4, chess.E5}
EXTENDED_CENTER = CENTER_SQUARES | {chess.C4, chess.C5, chess.F4, chess.F5}
FLANK_FILES = {0, 1, 6, 7}  # a, b, g, h


class MoveCategory(str, Enum):
    CASTLE_KINGSIDE = "castle_kingside"
    CASTLE_QUEENSIDE = "castle_queenside"
    CENTRAL_PAWN_PUSH = "central_pawn_push"       # pawn to e4/d4/e5/d5
    EXTENDED_CENTER_PAWN = "extended_center_pawn" # pawn to c4/c5/f4/f5
    FLANK_PAWN_PUSH = "flank_pawn_push"            # pawn to a/b/g/h file
    BISHOP_PAWN_PUSH = "bishop_pawn_push"          # pawn to c/f file non-central
    KNIGHT_DEVELOP = "knight_develop"              # knight from home to active square
    KNIGHT_RETREAT = "knight_retreat"
    BISHOP_DEVELOP = "bishop_develop"
    BISHOP_RETREAT = "bishop_retreat"
    ROOK_LIFT = "rook_lift"
    ROOK_MOVE = "rook_move"
    QUEEN_DEVELOP = "queen_develop"
    QUEEN_MOVE = "queen_move"
    KING_MOVE = "king_move"
    CAPTURE = "capture"
    PAWN_PROMOTION = "pawn_promotion"
    EN_PASSANT = "en_passant"
    OTHER = "other"


HOME_SQUARES = {
    chess.KNIGHT: {chess.B1, chess.G1, chess.B8, chess.G8},
    chess.BISHOP: {chess.C1, chess.F1, chess.C8, chess.F8},
    chess.QUEEN: {chess.D1, chess.D8},
    chess.ROOK: {chess.A1, chess.H1, chess.A8, chess.H8},
}


def classify_move(board_before: chess.Board, move: chess.Move) -> MoveCategory:
    """Classify WHAT kind of move this is based on piece, from_square, to_square.

    This is the signal the old dispatchers (match_coach_scenario) were missing.
    Every caller that wants "is this a developing move / a flank push / a retreat"
    should use this instead of branching on `piece` alone.
    """
    piece = board_before.piece_at(move.from_square)
    if not piece:
        return MoveCategory.OTHER

    if board_before.is_castling(move):
        return (MoveCategory.CASTLE_KINGSIDE
                if chess.square_file(move.to_square) > 4
                else MoveCategory.CASTLE_QUEENSIDE)

    if move.promotion:
        return MoveCategory.PAWN_PROMOTION

    if board_before.is_en_passant(move):
        return MoveCategory.EN_PASSANT

    if board_before.is_capture(move):
        return MoveCategory.CAPTURE

    pt = piece.piece_type
    to_file = chess.square_file(move.to_square)

    if pt == chess.PAWN:
        if move.to_square in CENTER_SQUARES:
            return MoveCategory.CENTRAL_PAWN_PUSH
        if move.to_square in EXTENDED_CENTER:
            return MoveCategory.EXTENDED_CENTER_PAWN
        if to_file in FLANK_FILES:
            return MoveCategory.FLANK_PAWN_PUSH
        return MoveCategory.BISHOP_PAWN_PUSH  # c/f file, non-central

    if pt == chess.KNIGHT:
        from_home = move.from_square in HOME_SQUARES[chess.KNIGHT]
        to_home = move.to_square in HOME_SQUARES[chess.KNIGHT]
        if from_home and not to_home:
            return MoveCategory.KNIGHT_DEVELOP
        if to_home and not from_home:
            return MoveCategory.KNIGHT_RETREAT
        return MoveCategory.KNIGHT_DEVELOP  # generic knight move — treat as active

    if pt == chess.BISHOP:
        from_home = move.from_square in HOME_SQUARES[chess.BISHOP]
        to_home = move.to_square in HOME_SQUARES[chess.BISHOP]
        if from_home and not to_home:
            return MoveCategory.BISHOP_DEVELOP
        if to_home and not from_home:
            return MoveCategory.BISHOP_RETREAT
        return MoveCategory.BISHOP_DEVELOP

    if pt == chess.ROOK:
        to_rank = chess.square_rank(move.to_square)
        rook_rank_own = 0 if piece.color == chess.WHITE else 7
        if to_rank != rook_rank_own and to_rank not in (0, 7):
            return MoveCategory.ROOK_LIFT
        return MoveCategory.ROOK_MOVE

    if pt == chess.QUEEN:
        if move.from_square in HOME_SQUARES[chess.QUEEN]:
            return MoveCategory.QUEEN_DEVELOP
        return MoveCategory.QUEEN_MOVE

    if pt == chess.KING:
        return MoveCategory.KING_MOVE

    return MoveCategory.OTHER


@dataclass
class ThreatFact:
    """A piece attacked after the move. is_new=True if threat didn't exist before."""
    square: int
    piece_type: int
    defender_count: int
    attacker_count: int
    is_new: bool


@dataclass
class PositionFacts:
    """Complete typed truth of a move in a position. Read, don't rebuild."""

    # ─── Move classification (THE new signal) ───
    move_san: str
    move_category: MoveCategory
    piece_moved: int                  # chess.PAWN, KNIGHT, ...
    from_square: int
    to_square: int
    is_check: bool
    is_capture: bool

    # ─── Phase & opening ───
    phase: GamePhase
    move_number: int
    opening_key: Optional[str] = None
    opening_name: Optional[str] = None   # pretty name, e.g. "King's Pawn Opening"
    opening_variation: Optional[str] = None

    # ─── Tactical facts about the resulting position ───
    # "us" = side that just moved, "them" = the opponent (side to move now)
    hanging_ours: List[HangingPieceInfo] = field(default_factory=list)
    underdefended_ours: List[HangingPieceInfo] = field(default_factory=list)
    hanging_theirs: List[HangingPieceInfo] = field(default_factory=list)
    underdefended_theirs: List[HangingPieceInfo] = field(default_factory=list)

    forks_by_us: List[ForkInfo] = field(default_factory=list)
    forks_by_them: List[ForkInfo] = field(default_factory=list)

    pins_against_them: List[Dict] = field(default_factory=list)
    pins_against_us: List[Dict] = field(default_factory=list)
    skewers_on_them: List[Dict] = field(default_factory=list)
    skewers_on_us: List[Dict] = field(default_factory=list)
    discovered_by_us: List[Dict] = field(default_factory=list)
    discovered_by_them: List[Dict] = field(default_factory=list)
    overloaded_theirs: List[Dict] = field(default_factory=list)
    overloaded_ours: List[Dict] = field(default_factory=list)

    # ─── Threats ───
    new_threats: List[ThreatFact] = field(default_factory=list)    # threats created by this move
    forcing_moves_us: Dict = field(default_factory=dict)           # checks/captures for side that just moved
    forcing_moves_them: Dict = field(default_factory=dict)         # what opponent can do now

    # ─── Engine facts (optional — only if Stockfish eval passed in) ───
    eval_before_cp: Optional[int] = None
    eval_after_cp: Optional[int] = None
    cp_loss: Optional[int] = None
    best_move_san: Optional[str] = None
    principal_variation: List[str] = field(default_factory=list)

    # ─── Raw access for escape hatches ───
    fen_before: str = ""
    fen_after: str = ""


def _to_color(c) -> chess.Color:
    """Normalize 'white'/'black' str or chess.Color to chess.Color."""
    if isinstance(c, str):
        return chess.WHITE if c.lower().startswith("w") else chess.BLACK
    return c


def _diff_threats(board_before: chess.Board, board_after: chess.Board,
                  victim_color: chess.Color) -> List[ThreatFact]:
    """Find pieces of victim_color newly attacked after the move."""
    attacker = not victim_color
    out = []
    for sq in chess.SQUARES:
        target = board_after.piece_at(sq)
        if not target or target.color != victim_color or target.piece_type == chess.KING:
            continue
        now = board_after.is_attacked_by(attacker, sq)
        if not now:
            continue
        before = board_before.is_attacked_by(attacker, sq)
        defenders = len(list(board_after.attackers(victim_color, sq)))
        attackers = len(list(board_after.attackers(attacker, sq)))
        out.append(ThreatFact(
            square=sq,
            piece_type=target.piece_type,
            defender_count=defenders,
            attacker_count=attackers,
            is_new=not before,
        ))
    return out


def _detect_opening_safe(move_history_san: List[str]) -> Dict:
    """Best-effort opening detection. Returns empty dict on failure."""
    if not move_history_san:
        return {}
    try:
        from services.opening_mastery import detect_opening_from_moves
        det = detect_opening_from_moves(move_history_san)
        return det or {}
    except Exception:
        return {}


def extract_facts(
    board_before: chess.Board,
    move: chess.Move,
    move_san: str,
    *,
    board_after: Optional[chess.Board] = None,
    move_history_san: Optional[List[str]] = None,
    stockfish_eval: Optional[Dict[str, Any]] = None,
) -> PositionFacts:
    """Compose all fact extractors into one typed object.

    Args:
        board_before: position before the move
        move: the move played
        move_san: SAN notation of the move
        board_after: optional — will be computed if not passed
        move_history_san: full game move list for opening detection
        stockfish_eval: optional {eval_before_cp, eval_after_cp, best_move_san, pv:[san]}

    Returns:
        PositionFacts with all deterministic facts populated.
    """
    if board_after is None:
        board_after = board_before.copy()
        board_after.push(move)

    us = board_before.turn          # who just moved
    them = not us

    piece = board_before.piece_at(move.from_square)
    piece_type = piece.piece_type if piece else chess.PAWN

    # Hanging & forks — use pattern_detectors (richest version)
    hanging_ours, underdef_ours = _find_hanging(board_after, us)
    hanging_theirs, underdef_theirs = _find_hanging(board_after, them)
    forks_us = _find_forks(board_after, us)
    forks_them = _find_forks(board_after, them)

    # Pins/skewers/discovered/overload — use mistake_classifier (complete suite)
    # Signature: find_X(board, color) returns attacks against `color`
    pins_on_them = _find_pins(board_after, them)
    pins_on_us = _find_pins(board_after, us)
    skewers_on_them = _find_skewers(board_after, them)
    skewers_on_us = _find_skewers(board_after, us)
    # discovered attacks BY a color — pass side that could execute
    discovered_us = _find_discovered(board_after, us, move)
    discovered_them = _find_discovered(board_after, them)
    overloaded_theirs = _find_overloaded(board_after, them)
    overloaded_ours = _find_overloaded(board_after, us)

    # Forcing moves for both sides in the resulting position
    forcing_us = _count_forcing(board_after, us)
    forcing_them = _count_forcing(board_after, them)

    # Threats created by this move (pieces of `them` newly attacked)
    new_threats = _diff_threats(board_before, board_after, them)

    # Phase (deterministic by piece count)
    phase = _determine_phase(board_after)

    # Opening (best-effort — only populated if we have move history)
    opening = _detect_opening_safe(move_history_san or [])

    # Engine facts (optional)
    eval_before = stockfish_eval.get("eval_before_cp") if stockfish_eval else None
    eval_after = stockfish_eval.get("eval_after_cp") if stockfish_eval else None
    cp_loss = None
    if eval_before is not None and eval_after is not None:
        # cp_loss is from the mover's perspective: positive = loss
        sign = 1 if us == chess.WHITE else -1
        cp_loss = max(0, sign * (eval_before - eval_after))

    return PositionFacts(
        move_san=move_san,
        move_category=classify_move(board_before, move),
        piece_moved=piece_type,
        from_square=move.from_square,
        to_square=move.to_square,
        is_check=board_after.is_check(),
        is_capture=board_before.is_capture(move),

        phase=phase,
        move_number=board_before.fullmove_number,
        opening_key=opening.get("opening_key") or None,
        opening_name=opening.get("opening_name") or None,
        opening_variation=opening.get("variation") or None,

        hanging_ours=hanging_ours,
        underdefended_ours=underdef_ours,
        hanging_theirs=hanging_theirs,
        underdefended_theirs=underdef_theirs,
        forks_by_us=forks_us,
        forks_by_them=forks_them,
        pins_against_them=pins_on_them,
        pins_against_us=pins_on_us,
        skewers_on_them=skewers_on_them,
        skewers_on_us=skewers_on_us,
        discovered_by_us=discovered_us,
        discovered_by_them=discovered_them,
        overloaded_theirs=overloaded_theirs,
        overloaded_ours=overloaded_ours,

        new_threats=new_threats,
        forcing_moves_us=forcing_us,
        forcing_moves_them=forcing_them,

        eval_before_cp=eval_before,
        eval_after_cp=eval_after,
        cp_loss=cp_loss,
        best_move_san=(stockfish_eval or {}).get("best_move_san"),
        principal_variation=(stockfish_eval or {}).get("pv") or [],

        fen_before=board_before.fen(),
        fen_after=board_after.fen(),
    )
