"""
Generic Principle Analyzer — Works for ANY endgame position.

Instead of position-type-specific logic, use general principle checks.
"""

import chess
from typing import Optional, List, Dict


async def analyze_endgame_move_for_principles(
    board: chess.Board,
    move: chess.Move,
    user_color: chess.Color,
) -> Dict[str, str]:
    """
    Analyze a move in endgame for principle violations.

    Returns principles that apply or are violated:
    {
        "principle_name": "applies" | "violates" | None
    }
    """

    results = {}

    # Principle 1: Does the move threaten opponent promotion?
    results["threats_promotion"] = await _check_threatens_promotion(board, move, user_color)

    # Principle 2: Does the move defend against promotion?
    results["defends_promotion"] = await _check_defends_promotion(board, move, user_color)

    # Principle 3: Does the move activate pieces (improve position)?
    results["piece_activity"] = await _check_piece_activity(board, move, user_color)

    # Principle 4: Is the rook active and defending?
    results["rook_defense"] = await _check_rook_defense(board, move, user_color)

    return results


async def _check_threatens_promotion(board: chess.Board, move: chess.Move, user_color: chess.Color) -> Optional[str]:
    """Does the move threaten opponent pawn promotion?"""
    opponent_color = not user_color

    # Get opponent pawns
    for pawn_sq in board.pieces(chess.PAWN, opponent_color):
        pawn_rank = chess.square_rank(pawn_sq)

        # Check if pawn is close to queening
        if opponent_color == chess.WHITE and pawn_rank >= 6:
            # Check if move attacks or blocks the pawn
            if move.to_square == pawn_sq:
                return "applies"  # Move captures pawn
        elif opponent_color == chess.BLACK and pawn_rank <= 2:
            # Check if move attacks or blocks the pawn
            if move.to_square == pawn_sq:
                return "applies"  # Move captures pawn

    return None


async def _check_defends_promotion(board: chess.Board, move: chess.Move, user_color: chess.Color) -> Optional[str]:
    """Does the move defend against opponent promotion threat?"""
    opponent_color = not user_color

    board.push(move)

    # After move, check if we defend promotion squares
    for pawn_sq in board.pieces(chess.PAWN, opponent_color):
        pawn_rank = chess.square_rank(pawn_sq)
        pawn_file = chess.square_file(pawn_sq)

        if opponent_color == chess.WHITE:
            if pawn_rank >= 6:
                promotion_sq = chess.square(pawn_file, 7)
                # Do we defend the promotion square?
                if board.is_attacked_by(user_color, promotion_sq):
                    board.pop()
                    return "applies"
        else:
            if pawn_rank <= 2:
                promotion_sq = chess.square(pawn_file, 0)
                # Do we defend the promotion square?
                if board.is_attacked_by(user_color, promotion_sq):
                    board.pop()
                    return "applies"

    board.pop()
    return None


async def _check_piece_activity(board: chess.Board, move: chess.Move, user_color: chess.Color) -> Optional[str]:
    """Does the move activate a piece (improve its position)?"""
    piece = board.piece_at(move.from_square)
    if not piece or piece.color != user_color:
        return None

    # Piece is moving - that's generally good (unless it's a retreat)
    from_file = chess.square_file(move.from_square)
    from_rank = chess.square_rank(move.from_square)
    to_file = chess.square_file(move.to_square)
    to_rank = chess.square_rank(move.to_square)

    # Moving pieces is usually activating them
    # Unless moving away from action
    if piece.piece_type == chess.ROOK:
        # Rook moving forward/sideways to active file is good
        if to_file != from_file or to_rank > from_rank:
            return "applies"

    return None


async def _check_rook_defense(board: chess.Board, move: chess.Move, user_color: chess.Color) -> Optional[str]:
    """Is the rook playing a key defensive role?"""
    piece = board.piece_at(move.from_square)
    if not piece or piece.piece_type != chess.ROOK:
        return None  # Not a rook move

    board.push(move)

    # After move, is rook still defending key squares?
    opponent_pawns = list(board.pieces(chess.PAWN, not user_color))

    for pawn_sq in opponent_pawns:
        pawn_rank = chess.square_rank(pawn_sq)
        pawn_file = chess.square_file(pawn_sq)

        # Check if this is a threatening pawn
        if user_color == chess.WHITE and pawn_rank >= 6:
            promotion_sq = chess.square(pawn_file, 7)
            if board.is_attacked_by(user_color, promotion_sq):
                board.pop()
                return "applies"
        elif user_color == chess.BLACK and pawn_rank <= 2:
            promotion_sq = chess.square(pawn_file, 0)
            if board.is_attacked_by(user_color, promotion_sq):
                board.pop()
                return "applies"

    board.pop()
    return None
