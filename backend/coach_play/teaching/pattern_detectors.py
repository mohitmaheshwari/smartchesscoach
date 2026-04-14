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
) -> Dict:
    """
    Count meaningful checks, captures, and attacks with quality assessment.

    Returns dict with:
    - checks: safe checks (piece not immediately lost)
    - captures: net-positive captures (win material or target undefended)
    - high_value_attacks: captures of queen/rook
    - safe_captures: captures that clearly win material
    - attacks_on_undefended: captures of undefended pieces
    - material_gain: total cp gain from safe captures

    Works regardless of whose turn it is. If it's not `side`'s turn,
    we temporarily flip the turn to generate legal moves for `side`.
    """
    empty = {"checks": 0, "captures": 0, "high_value_attacks": 0,
             "safe_captures": 0, "attacks_on_undefended": 0, "material_gain": 0}

    needs_flip = board.turn != side
    if needs_flip:
        # If the opponent is in check, our "next move threats" are meaningless —
        # the opponent MUST respond to check first, changing the position.
        if board.is_check():
            return empty

        parts = board.fen().split()
        parts[1] = 'w' if side == chess.WHITE else 'b'
        parts[3] = '-'
        board = chess.Board(' '.join(parts))

    checks = 0
    captures = 0
    high_value_attacks = 0
    safe_captures = 0
    attacks_on_undefended = 0
    material_gain = 0

    for move in board.legal_moves:
        mover = board.piece_at(move.from_square)
        mover_value = PIECE_VALUES.get(mover.piece_type, 0) if mover else 0

        # Check — only count if checking piece isn't immediately lost
        board.push(move)
        if board.is_check():
            if not board.is_attacked_by(board.turn, move.to_square):
                checks += 1
            elif mover_value <= 1:
                checks += 1
        board.pop()

        # Capture — assess quality
        if board.is_capture(move):
            captured = board.piece_at(move.to_square)
            if captured:
                cap_value = PIECE_VALUES.get(captured.piece_type, 0)
                target_defended = board.is_attacked_by(not side, move.to_square)

                if not target_defended:
                    # Free capture — target is undefended
                    captures += 1
                    safe_captures += 1
                    attacks_on_undefended += 1
                    material_gain += cap_value * 100  # in centipawns
                    if captured.piece_type in (chess.QUEEN, chess.ROOK):
                        high_value_attacks += 1
                elif cap_value >= mover_value:
                    # Equal or winning trade
                    captures += 1
                    safe_captures += 1
                    gain = (cap_value - mover_value) * 100
                    material_gain += gain
                    if captured.piece_type in (chess.QUEEN, chess.ROOK):
                        high_value_attacks += 1

    return {
        "checks": checks,
        "captures": captures,
        "high_value_attacks": high_value_attacks,
        "safe_captures": safe_captures,
        "attacks_on_undefended": attacks_on_undefended,
        "material_gain": material_gain,
    }


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
    threats = count_forcing_moves(board, side=coach_color)

    return PositionFeatures(
        opponent_hanging=student_hanging,
        opponent_underdefended=student_underdefended,
        fork_opportunities=coach_forks,
        checks_available=threats["checks"],
        captures_available=threats["captures"],
        high_value_attacks=threats["high_value_attacks"],
        safe_captures=threats["safe_captures"],
        attacks_on_undefended=threats["attacks_on_undefended"],
        material_gain_possible=threats["material_gain"],
    )
