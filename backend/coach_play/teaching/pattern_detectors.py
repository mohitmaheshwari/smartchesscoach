"""
Pattern Detectors — analyze a board position for teaching-relevant patterns.

These detect features in a RESULTING position (after a candidate move),
not features of the move itself. This is the core difference from v1.

Reuses logic from position_reader.py and detector_registry.py but returns
structured data instead of UI strings.
"""

import chess
from typing import List, Dict, Tuple
from .types import (
    HangingPieceInfo, ForkInfo, PositionFeatures, PIECE_VALUES
)


def find_hanging_pieces(
    board: chess.Board,
    victim_color: chess.Color,
) -> Tuple[List[HangingPieceInfo], List[HangingPieceInfo]]:
    """
    Find pieces of victim_color that are hanging or underdefended.

    Returns (undefended, underdefended) where:
    - undefended: attacked and zero defenders
    - underdefended: attacked by cheaper piece, or more attackers than defenders

    Based on position_reader._analyze_hanging_pieces() logic but returns
    structured data.
    """
    attacker_color = not victim_color
    undefended = []
    underdefended = []

    for sq in chess.SQUARES:
        piece = board.piece_at(sq)
        if not piece or piece.color != victim_color or piece.piece_type == chess.KING:
            continue

        attackers = list(board.attackers(attacker_color, sq))
        if not attackers:
            continue

        defenders = list(board.attackers(victim_color, sq))
        piece_value = PIECE_VALUES.get(piece.piece_type, 0)

        # Skip pawns — hanging a pawn is usually not instructive enough
        if piece.piece_type == chess.PAWN:
            continue

        info = HangingPieceInfo(
            square=sq,
            piece_type=piece.piece_type,
            piece_value=piece_value,
            attacker_squares=attackers,
            defender_count=len(defenders),
            attacker_count=len(attackers),
        )

        if len(defenders) == 0:
            # Attacked with no defenders — fully hanging
            undefended.append(info)
        else:
            # Check if cheapest attacker is cheaper than the piece
            cheapest_attacker_value = min(
                (PIECE_VALUES.get(board.piece_at(a).piece_type, 0)
                 for a in attackers if board.piece_at(a)),
                default=99,
            )
            if cheapest_attacker_value < piece_value and len(attackers) > len(defenders):
                # Can profitably capture — underdefended
                underdefended.append(info)

    return undefended, underdefended


def find_fork_opportunities(
    board: chess.Board,
    forker_color: chess.Color,
) -> List[ForkInfo]:
    """
    Find pieces of forker_color that attack 2+ non-pawn opponent pieces.

    Based on position_reader._analyze_forks() logic. Checks knights,
    queens, pawns, AND bishops (the original missed bishops).

    Returns list of ForkInfo with target details.
    """
    opponent_color = not forker_color
    forks = []

    for sq in chess.SQUARES:
        piece = board.piece_at(sq)
        if not piece or piece.color != forker_color:
            continue
        # Any piece can fork (knight most common, but rook/bishop/queen too)
        if piece.piece_type == chess.KING:
            continue

        attacks = board.attacks(sq)
        targets = []
        target_types = []
        total_value = 0

        for target_sq in attacks:
            target = board.piece_at(target_sq)
            if not target or target.color != opponent_color:
                continue
            if target.piece_type == chess.PAWN:
                continue
            targets.append(target_sq)
            target_types.append(target.piece_type)
            total_value += PIECE_VALUES.get(target.piece_type, 0)

        if len(targets) >= 2:
            forks.append(ForkInfo(
                forker_square=sq,
                forker_type=piece.piece_type,
                target_squares=targets,
                target_types=target_types,
                total_target_value=total_value,
            ))

    return forks


def count_forcing_moves(
    board: chess.Board,
    side: chess.Color,
) -> Tuple[int, int, int]:
    """
    Count meaningful checks, captures, and attacks on high-value pieces.

    Only counts:
    - Checks that don't lose the checking piece (not trapped after check)
    - Captures where captured piece value >= attacker value OR target is undefended
    - Attacks on queen/rook that are real threats

    Must be called when it's `side`'s turn to move. If it's not their turn,
    returns (0, 0, 0).

    Returns (checks, safe_captures, high_value_attacks).
    """
    if board.turn != side:
        return 0, 0, 0

    checks = 0
    captures = 0
    high_value_attacks = 0

    for move in board.legal_moves:
        mover = board.piece_at(move.from_square)
        mover_value = PIECE_VALUES.get(mover.piece_type, 0) if mover else 0

        # Check — only count if the checking piece isn't immediately captured
        board.push(move)
        if board.is_check():
            # Is our piece safe on its new square?
            if not board.is_attacked_by(board.turn, move.to_square):
                checks += 1
            elif mover_value <= 1:
                # Pawn checks are always meaningful even if pawn is captured
                checks += 1
        board.pop()

        # Capture — only count net-positive or safe captures
        if board.is_capture(move):
            captured = board.piece_at(move.to_square)
            if captured:
                cap_value = PIECE_VALUES.get(captured.piece_type, 0)
                # Safe if: target undefended, or we capture equal/higher value
                target_defended = board.is_attacked_by(not side, move.to_square)
                if cap_value >= mover_value or not target_defended:
                    captures += 1
                    if captured.piece_type in (chess.QUEEN, chess.ROOK):
                        high_value_attacks += 1

    return checks, captures, high_value_attacks


def analyze_position(
    board: chess.Board,
    coach_color: chess.Color,
) -> PositionFeatures:
    """
    Full position analysis from the coach's perspective.

    coach_color is the color the COACH is playing. We analyze:
    - Opponent's hanging/underdefended pieces (things the student must deal with)
    - Coach's fork opportunities (threats the student must see)
    - Forcing moves available to coach (threats the student must handle)

    The student is the OPPONENT of coach_color.
    """
    student_color = not coach_color

    # What opponent pieces are hanging? (student's pieces that are vulnerable)
    student_hanging, student_underdefended = find_hanging_pieces(
        board, victim_color=student_color
    )

    # What forks does the coach have? (student must deal with them)
    coach_forks = find_fork_opportunities(board, forker_color=coach_color)

    # What forcing moves does the coach have?
    checks, captures, hv_attacks = count_forcing_moves(board, side=coach_color)

    return PositionFeatures(
        opponent_hanging=student_hanging,
        opponent_underdefended=student_underdefended,
        fork_opportunities=coach_forks,
        checks_available=checks,
        captures_available=captures,
        high_value_attacks=hv_attacks,
    )
