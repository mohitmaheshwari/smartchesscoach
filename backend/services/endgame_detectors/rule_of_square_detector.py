"""
Rule of the Square Detector — Deterministic endgame principle analyzer.

The rule of the square: In a K+P vs K endgame, the king can catch the pawn
if it can move into an imaginary square with the pawn at one corner.

Distance calculation:
  - If king can reach the queening square within N moves where N = distance
    from pawn to queening square, the king catches it (rule applies).
  - Otherwise, the pawn queens (rule violated).
"""

import chess
from typing import Optional, Tuple


def detect_rule_of_square(
    board: chess.Board,
    move: chess.Move,
    user_color: chess.Color,
) -> Optional[str]:
    """
    Detect if a move demonstrates understanding of the rule of the square.

    Args:
        board: Position BEFORE the move
        move: The move being played (in User's perspective)
        user_color: User's color (chess.WHITE or chess.BLACK)

    Returns:
        "applies"  → move correctly uses rule of square (catches pawn or avoids loss)
        "violates" → move ignores rule of square (allows pawn to queen)
        None       → rule of square not relevant to this position
    """

    # Check if position is a K+P vs K endgame
    if not _is_kp_vs_k_endgame(board):
        return None

    # Identify which side has pawn, which has king
    white_has_pawn = bool(board.pieces(chess.PAWN, chess.WHITE))
    black_has_pawn = bool(board.pieces(chess.PAWN, chess.BLACK))

    if white_has_pawn and black_has_pawn:
        return None  # Multiple pawns, not simple K+P vs K

    if not (white_has_pawn or black_has_pawn):
        return None  # No pawns at all

    # Determine attacking side (has pawn) and defending side (has king only)
    attacking_side = chess.WHITE if white_has_pawn else chess.BLACK
    defending_side = chess.BLACK if white_has_pawn else chess.WHITE

    # User must be the defending side (trying to catch the pawn)
    if user_color != defending_side:
        return None  # User is attacking; rule of square not their concern

    # Get pawn and defending king positions
    pawn_sq = list(board.pieces(chess.PAWN, attacking_side))[0]
    defending_king_sq = board.king(defending_side)

    # Apply rule of the square BEFORE the move
    pawn_can_be_caught_before = _can_king_catch_pawn(board, defending_king_sq, pawn_sq, defending_side)

    # Apply rule after the move
    board.push(move)
    new_king_sq = board.king(defending_side)
    # Check if pawn advanced
    new_pawn_sq = _get_pawn_position(board, attacking_side) or pawn_sq
    pawn_can_be_caught_after = _can_king_catch_pawn(board, new_king_sq, new_pawn_sq, defending_side)
    board.pop()

    # Analyze the move
    if pawn_can_be_caught_after:
        # King can still catch pawn after move
        return "applies"
    elif pawn_can_be_caught_before and not pawn_can_be_caught_after:
        # Move lost the catching zone (violated rule)
        return "violates"
    elif not pawn_can_be_caught_before:
        # Pawn was already queening; move doesn't matter
        return None

    return None


def _is_kp_vs_k_endgame(board: chess.Board) -> bool:
    """Check if position is K+P vs K (or close to it)"""
    # Only kings and at most one pawn total
    total_pieces = sum(
        len(board.pieces(piece, color))
        for piece in [chess.PAWN, chess.ROOK, chess.BISHOP, chess.KNIGHT, chess.QUEEN]
        for color in [chess.WHITE, chess.BLACK]
    )

    total_pawns = len(board.pieces(chess.PAWN, chess.WHITE)) + len(board.pieces(chess.PAWN, chess.BLACK))

    return total_pieces <= 1 and total_pawns <= 1


def _get_pawn_position(board: chess.Board, color: chess.Color) -> Optional[int]:
    """Get square of pawn for given color, or None if no pawn"""
    pawns = list(board.pieces(chess.PAWN, color))
    return pawns[0] if pawns else None


def _can_king_catch_pawn(
    board: chess.Board,
    king_sq: int,
    pawn_sq: int,
    king_color: chess.Color,
) -> bool:
    """
    Apply rule of the square: can the king catch the pawn?

    The rule: Imagine a square with the pawn at one corner and the queening
    square at opposite corner. If the king can step into this square, it can
    catch the pawn.

    Simpler calculation:
    - Moves to queen: distance from pawn to 8th rank (for white) or 1st rank (for black)
    - If king can reach queening square in <= moves_to_queen, king catches pawn
    """

    pawn_file = chess.square_file(pawn_sq)
    pawn_rank = chess.square_rank(pawn_sq)
    king_file = chess.square_file(king_sq)
    king_rank = chess.square_rank(king_sq)

    # Queening rank
    pawn_owner = chess.WHITE if pawn_rank < 4 else chess.BLACK
    queening_rank = 7 if pawn_owner == chess.WHITE else 0
    queening_sq = chess.square(pawn_file, queening_rank)

    # Moves needed for pawn to queen
    pawn_moves_to_queen = abs(pawn_rank - queening_rank)

    # Moves needed for king to reach queening square
    king_moves_to_queen = max(abs(king_file - pawn_file), abs(king_rank - queening_rank))

    # Rule of the square: king catches if it reaches within pawn_moves_to_queen moves
    # Add 1 because if king can reach queening square in same moves, it's too late
    return king_moves_to_queen < pawn_moves_to_queen or (
        king_moves_to_queen == pawn_moves_to_queen and board.turn != pawn_owner
    )
