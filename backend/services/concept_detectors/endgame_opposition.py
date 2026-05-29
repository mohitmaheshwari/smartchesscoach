"""
King-and-pawn opposition detector.

Direct opposition: two kings face each other with exactly one square
between them on the same file (vertical) or same rank (horizontal),
and it's the OPPONENT's move. The side NOT to move "has the
opposition" — they've forced the other king to step away.

In a K+P vs K endgame, holding the opposition is the linchpin of
winning (or drawing as defender). This detector grades a move that
SEIZES the opposition: user king moves to the square that puts the
two kings in direct opposition with the OPPONENT to move next.

Decision logic:

    Pre-condition ("clean test"):
      - It's the user's move
      - King-and-pawn endgame only: no piece other than kings + pawns
        on the board (to avoid false positives in middlegame king
        moves that happen to land near each other)
      - Pre-move: the kings are NOT already in direct opposition
      - Post-move: the kings ARE in direct opposition (one square
        apart, same file or rank), and it's the OPPONENT's turn next

    Grade:
      - User's king move seizes opposition                        → "applied"
      - User played a non-king move (pawn move) when seizing
        opposition was possible (engine likes the K move better)  → None
        (we don't grade non-king moves negatively; lots of correct
        K+P endgame play is pawn play)
      - User's king move does NOT take opposition though a king
        move existed that would have                              → "missed"
        (only when the position is a clean opposition test)
"""
from __future__ import annotations

from typing import Optional

import chess


def detect_endgame_opposition_application(
    board_before: chess.Board,
    move: chess.Move,
    user_color: chess.Color,
) -> Optional[str]:
    if board_before.turn != user_color:
        return None
    if not _is_kp_endgame(board_before):
        return None

    user_king = board_before.king(user_color)
    opp_king = board_before.king(not user_color)
    if user_king is None or opp_king is None:
        return None

    # Skip if the kings are already in opposition before the move.
    if _in_direct_opposition(user_king, opp_king):
        return None

    moved_piece = board_before.piece_at(move.from_square)
    if moved_piece is None:
        return None

    if moved_piece.piece_type != chess.KING:
        # Don't grade non-king moves either way.
        return None

    new_user_king = move.to_square
    if _in_direct_opposition(new_user_king, opp_king):
        return "applied"

    # Did the user MISS opposition? Check if any legal king move from
    # the current square would have taken opposition. If yes — and the
    # user picked a different king square — missed. Otherwise: None
    # (opposition wasn't on the board this move).
    for sq in chess.SquareSet(chess.BB_KING_ATTACKS[user_king]):
        cand = chess.Move(user_king, sq)
        if cand not in board_before.legal_moves:
            continue
        if _in_direct_opposition(sq, opp_king):
            return "missed"
    return None


# ─── helpers ───────────────────────────────────────────────────────────────

def _is_kp_endgame(board: chess.Board) -> bool:
    """True when only kings and pawns are on the board."""
    for sq, piece in board.piece_map().items():
        if piece.piece_type not in (chess.KING, chess.PAWN):
            return False
    return True


def _in_direct_opposition(king_a: chess.Square, king_b: chess.Square) -> bool:
    """Two kings are in direct opposition iff they're exactly one
    square apart on the same file or same rank."""
    fa, ra = chess.square_file(king_a), chess.square_rank(king_a)
    fb, rb = chess.square_file(king_b), chess.square_rank(king_b)
    same_file_one_step = fa == fb and abs(ra - rb) == 2
    same_rank_one_step = ra == rb and abs(fa - fb) == 2
    return same_file_one_step or same_rank_one_step
