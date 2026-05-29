"""
King + Queen vs lone King mate detector.

Grades the user on the canonical "confine and mate" technique. Fires
ONLY when the opponent has nothing but the king on the board — the
user may still have extra material (other pieces / pawns) and the
detector still applies, since the K+Q technique is what's being tested.

Decision logic:

    Pre-condition ("clean test"):
      - It's the user's move
      - Opponent has exactly one piece on the board: their king
      - User owns at least one queen (extra pieces / pawns are fine)

    Grade:
      - User's move delivers checkmate                                 → "applied"
      - Mate-in-1 was available (some user-side queen move mates) and
        the played move did NOT take it                                → "missed"
      - Mate-in-1 wasn't on the board this move (still grinding the
        king toward the edge)                                          → None

Why we restrict "missed" to mate-in-1: the canonical technique builds
up over several moves, and most positions don't have a single
clear-cut mating move. Grading every non-mating move as "missed"
would be hostile to a player executing the right slow-grind plan.
"""
from __future__ import annotations

from typing import Optional

import chess


def detect_mate_kq_vs_k_application(
    board_before: chess.Board,
    move: chess.Move,
    user_color: chess.Color,
) -> Optional[str]:
    """Did this move execute the King + Queen vs lone King technique?

    Args:
        board_before: position immediately before `move` is played.
        move:         the user's move.
        user_color:   chess.WHITE or chess.BLACK — the user's side.

    Returns:
        "applied" — the move delivered checkmate.
        "missed"  — a mate-in-1 was available but the move skipped it.
        None      — position isn't a clean test (opponent has other
                    pieces, user has no queen, or no mate-in-1
                    available to grade against).
    """
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

    # User must have at least one queen.
    if not board_before.pieces(chess.QUEEN, user_color):
        return None

    # Apply the played move — did it deliver mate?
    board_after = board_before.copy()
    try:
        board_after.push(move)
    except Exception:
        return None
    if board_after.is_checkmate():
        return "applied"

    # Mate-in-1 check: was any queen move (or king move setting up the
    # mate) mate this turn? If yes and the user didn't play it, miss.
    if _user_had_mate_in_one(board_before, user_color):
        return "missed"

    # No mate-in-1 on the board this move — slow-grind move, don't grade.
    return None


def _user_had_mate_in_one(board: chess.Board, user_color: chess.Color) -> bool:
    """Scan every legal move; True if any one of them is checkmate."""
    for candidate in board.legal_moves:
        test = board.copy()
        test.push(candidate)
        if test.is_checkmate():
            return True
    return False
