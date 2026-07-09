"""
Critical Piece Detector — Identifies which pieces are essential to position.

Detects if a move abandons a critical defensive role.

Examples:
  - Rook is the only defender of a queening pawn → moving rook is critical
  - King is the only piece stopping back rank mate → moving king abandons defense
"""

import chess
from typing import Optional, Tuple, List


def detect_critical_piece_abandonment(
    board: chess.Board,
    move: chess.Move,
    user_color: chess.Color,
) -> Optional[str]:
    """
    Detect if move abandons a piece's critical role.

    Args:
        board: Position BEFORE move
        move: The move
        user_color: User's color

    Returns:
        "applies"  → move maintains critical piece's role
        "violates" → move abandons a critical defense
        None       → no critical piece in position
    """

    # Only applies to endgames
    if not _is_endgame(board):
        return None

    # Identify critical pieces before move
    critical_pieces_before = _identify_critical_pieces(board, user_color)

    if not critical_pieces_before:
        return None  # No critical pieces

    # Check if the move touches a critical piece
    moving_piece = board.piece_at(move.from_square)
    if not moving_piece or moving_piece.color != user_color:
        return None  # Not user's move or invalid

    # If moving piece is critical, check if move maintains its role
    piece_role = critical_pieces_before.get(move.from_square)
    if piece_role:
        # Piece is moving from a critical square
        board.push(move)
        piece_still_critical = _piece_maintains_role(board, move, piece_role, user_color)
        board.pop()

        if piece_still_critical:
            return "applies"  # Move maintains critical role (e.g., rook to different square still defends)
        else:
            return "violates"  # Move abandons critical role

    return None


def _is_endgame(board: chess.Board) -> bool:
    """Check if position is an endgame (few pieces remaining)"""
    piece_count = sum(
        len(board.pieces(piece, color))
        for piece in [chess.QUEEN, chess.ROOK, chess.BISHOP, chess.KNIGHT, chess.PAWN]
        for color in [chess.WHITE, chess.BLACK]
    )
    return piece_count <= 10


def _identify_critical_pieces(board: chess.Board, user_color: chess.Color) -> dict:
    """
    Identify pieces that play critical roles.

    Returns: {square: role_description}
    where role can be "only_defender_of_pawn", "defending_promotion", etc.
    """
    critical = {}

    # Case 1: Rook defending pawn from queening
    opponent_pawns = list(board.pieces(chess.PAWN, not user_color))
    user_rooks = list(board.pieces(chess.ROOK, user_color))

    for pawn_sq in opponent_pawns:
        pawn_rank = chess.square_rank(pawn_sq)
        if pawn_rank >= 5:  # Pawn close to queening
            # Is there a rook defending?
            for rook_sq in user_rooks:
                if _rook_defends_pawn(board, rook_sq, pawn_sq, user_color):
                    if rook_sq not in critical:
                        critical[rook_sq] = "only_defender_of_promotion_threat"

    # Case 2: King as only defender on back rank
    user_king_sq = board.king(user_color)
    if _king_is_only_defender_of_back_rank(board, user_king_sq, user_color):
        critical[user_king_sq] = "only_defender_of_back_rank"

    return critical


def _rook_defends_pawn(board: chess.Board, rook_sq: int, pawn_sq: int, user_color: chess.Color) -> bool:
    """Check if rook on rook_sq defends against pawn on pawn_sq"""
    # Rook defends if it can reach the pawn in one move
    rook_rank = chess.square_rank(rook_sq)
    rook_file = chess.square_file(rook_sq)
    pawn_rank = chess.square_rank(pawn_sq)
    pawn_file = chess.square_file(pawn_sq)

    # Same rank or file, no pieces in between
    if rook_rank == pawn_rank or rook_file == pawn_file:
        # Check if path is clear
        test_board = board.copy()
        try:
            move = chess.Move(rook_sq, pawn_sq)
            return test_board.is_legal(move)
        except:
            return False

    return False


def _king_is_only_defender_of_back_rank(board: chess.Board, king_sq: int, user_color: chess.Color) -> bool:
    """Check if king is defending against back rank mate"""
    user_back_rank = 0 if user_color == chess.BLACK else 7
    king_rank = chess.square_rank(king_sq)

    # King must be on back rank
    if king_rank != user_back_rank:
        return False

    # Check if opponent has rook/queen that could threaten back rank
    opponent_color = not user_color
    has_rook_or_queen = bool(board.pieces(chess.ROOK, opponent_color)) or bool(
        board.pieces(chess.QUEEN, opponent_color)
    )

    return has_rook_or_queen


def _piece_maintains_role(board: chess.Board, move: chess.Move, original_role: str, user_color: chess.Color) -> bool:
    """After move, does piece still maintain its role?"""
    # This is simplified — in reality need to check if new position still fulfills the role
    # For now, assume piece moving away from critical square loses the role
    return False
