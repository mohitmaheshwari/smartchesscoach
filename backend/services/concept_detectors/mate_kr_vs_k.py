"""
King + Rook vs lone King mate detector.

Mirrors mate_kq_vs_k but for the slower rook-mate technique. The
checkmate position has the rook delivering check along a rank or file
with the user's king holding the opposition.

Decision logic mirrors KQvK exactly:

    Pre-condition ("clean test"):
      - User's move
      - Opponent has exactly one piece on board: their king
      - User owns at least one rook (extra material is fine)

    Grade:
      - User's move delivers checkmate                                 → "applied"
      - Mate-in-1 was on the board (some user-side move mates) and the
        played move skipped it                                         → "missed"
      - Mid-grind move (no mate-in-1 yet)                              → None
"""
from __future__ import annotations

from typing import Optional

import chess


def detect_mate_kr_vs_k_application(
    board_before: chess.Board,
    move: chess.Move,
    user_color: chess.Color,
) -> Optional[str]:
    if board_before.turn != user_color:
        return None

    opp_color = not user_color

    # Opponent must have exactly one piece: their king.
    opp_squares = [
        sq for sq in chess.SQUARES
        if (p := board_before.piece_at(sq)) is not None and p.color == opp_color
    ]
    if len(opp_squares) != 1:
        return None
    if board_before.piece_at(opp_squares[0]).piece_type != chess.KING:
        return None

    # User must have at least one rook.
    if not board_before.pieces(chess.ROOK, user_color):
        return None

    board_after = board_before.copy()
    try:
        board_after.push(move)
    except Exception:
        return None
    if board_after.is_checkmate():
        return "applied"

    if _user_had_mate_in_one(board_before):
        return "missed"

    return None


def _user_had_mate_in_one(board: chess.Board) -> bool:
    for candidate in board.legal_moves:
        test = board.copy()
        test.push(candidate)
        if test.is_checkmate():
            return True
    return False
