"""
Promotion Threat Detector — Identifies pawn promotion threats.

Detects if a move allows opponent pawn to promote unchallenged.
"""

import chess
from typing import Optional


def detect_promotion_threat_violation(
    board: chess.Board,
    move: chess.Move,
    user_color: chess.Color,
) -> Optional[str]:
    """
    Detect if move allows opponent pawn to promote.

    Args:
        board: Position BEFORE move
        move: User's move
        user_color: User's color

    Returns:
        "applies"  → move stops/controls promotion threat
        "violates" → move allows pawn to promote
        None       → no promotion threat in position
    """

    opponent_color = not user_color

    # Get opponent pawns close to promotion
    threatening_pawns = []
    for pawn_sq in board.pieces(chess.PAWN, opponent_color):
        pawn_rank = chess.square_rank(pawn_sq)
        # Threat if rank >= 6 (close to promotion)
        if opponent_color == chess.WHITE and pawn_rank >= 6:
            threatening_pawns.append(pawn_sq)
        elif opponent_color == chess.BLACK and pawn_rank <= 2:
            threatening_pawns.append(pawn_sq)

    if not threatening_pawns:
        return None  # No promotion threat

    # Check if move allows any pawn to promote next move
    board.push(move)

    for pawn_sq in threatening_pawns:
        pawn_rank = chess.square_rank(pawn_sq)
        queening_rank = 7 if opponent_color == chess.WHITE else 0

        # Can pawn promote next move?
        moves_to_promotion = abs(pawn_rank - queening_rank)
        if moves_to_promotion == 1:
            # Pawn can promote next move — did we defend?
            pawn_file = chess.square_file(pawn_sq)
            promotion_sq = chess.square(pawn_file, queening_rank)

            # Check if any user piece controls promotion square
            user_controls_promotion = board.is_attacked_by(user_color, promotion_sq)

            if not user_controls_promotion:
                # Pawn promotes undefended
                board.pop()
                return "violates"

    board.pop()
    return "applies"  # All threats controlled


def get_promotion_threats(board: chess.Board, color: chess.Color) -> list:
    """Get list of opponent pawns threatening to promote"""
    opponent_color = not color
    threats = []

    for pawn_sq in board.pieces(chess.PAWN, opponent_color):
        pawn_rank = chess.square_rank(pawn_sq)
        pawn_file = chess.square_file(pawn_sq)

        if opponent_color == chess.WHITE:
            if pawn_rank >= 6:
                threat_sq = chess.square(pawn_file, 7)
                threats.append({"pawn_sq": pawn_sq, "promotion_sq": threat_sq, "moves": 7 - pawn_rank})
        else:
            if pawn_rank <= 2:
                threat_sq = chess.square(pawn_file, 0)
                threats.append({"pawn_sq": pawn_sq, "promotion_sq": threat_sq, "moves": pawn_rank})

    return threats
