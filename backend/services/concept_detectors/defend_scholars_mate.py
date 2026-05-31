"""
Defend-against-Scholar's-Mate in-game detector.

Scholar's Mate is the classical four-move attack at f7:

    1.e4 e5 2.Bc4 ... 3.Qh5 (or 3.Qf3) ... 4.Qxf7#

The mate works because the white queen captures the pawn on f7 with
check, the queen is defended by the bishop on c4 (so the king cannot
take), and the king has no legal escape (e7 / d7 / etc. are covered or
blocked). The classical defenses for Black are:

    g6           — block the queen's diagonal to f7
    Qe7 / Qf6    — add a defender of f7
    Move the king out of the line (rare in this phase)

Decision logic (Black to move; detector fires only when the user plays
Black, since the SKILL is "defend against"):

    Pre-conditions ("clean test"):
      - Classical-window opening (full_move_number <= 5). Mohit
        2026-05-31: a 1300 understands "Scholar's Mate" as the named
        early pattern. Move-7 / move-8 setups where white delays the
        queen sortie are geometrically the same Qxf7# threat but
        pedagogically a different skill ("late queen attack").
        Confirmed evidence from production: 4 different users had
        move-7/8 entries credited that the user would NOT recognize
        as Scholar's Mate. Tightened from <= 8.
      - White has exactly one queen, and that queen attacks f7
      - White bishop sits on c4 (the queen-defender for Qxf7+)
      - It IS currently mate-threat: if white were to play Qxf7 right
        now (we test by simulating with the turn flipped to white), it
        would deliver checkmate

    Grade:
      - After Black's move, does Qxf7# still mate? If YES → "missed".
      - If NO (Black defended / blocked / removed the threat) → "applied".

False-positive guards:
  - We require Bc4 specifically. An "Qh5 without Bc4" attack is amateur
    bluster, not a real mate threat — we don't grade it as Scholar's
    Mate.
  - We require the simulated Qxf7 to ACTUALLY be checkmate, not just
    "wins a pawn." Plenty of early Qh5 positions threaten material
    without mating; those aren't Scholar's Mate either.
"""
from __future__ import annotations

from typing import Optional

import chess


def detect_defend_scholars_mate_application(
    board_before: chess.Board,
    move: chess.Move,
    user_color: chess.Color,
) -> Optional[str]:
    """Was this move a clean test of defending Scholar's Mate?

    Args:
        board_before: position immediately before `move` is played.
        move:         the user's move.
        user_color:   chess.WHITE or chess.BLACK — the user's side.

    Returns:
        "applied" — Black defused the Qxf7# threat with this move.
        "missed"  — Black ignored / mis-played; Qxf7# is still on.
        None      — position is not a clean Scholar's Mate test.
    """
    # Scope: only Black ever DEFENDS Scholar's Mate.
    if user_color != chess.BLACK:
        return None
    if board_before.turn != chess.BLACK:
        return None
    # Scholar's Mate is the NAMED early-opening attack — the user must
    # be able to recognise the pattern as "Scholar's Mate", not a generic
    # f7 attack. Move 5+ is outside the named-pattern window for a
    # 1300-rated audience. See module docstring (Mohit 2026-05-31).
    if board_before.fullmove_number > 5:
        return None

    if not _has_scholars_mate_threat(board_before):
        return None

    board_after = board_before.copy()
    try:
        board_after.push(move)
    except Exception:
        return None

    if _has_scholars_mate_threat(board_after):
        return "missed"
    return "applied"


# ─── helpers ───────────────────────────────────────────────────────────────

def _has_scholars_mate_threat(board: chess.Board) -> bool:
    """True if the geometry says white can play Qxf7# right now.

    Geometry requirements:
      - exactly one white queen, attacking f7
      - white bishop on c4
      - simulating Qxf7 (forcing white's turn) results in checkmate
    """
    white_queens = list(board.pieces(chess.QUEEN, chess.WHITE))
    if len(white_queens) != 1:
        return False
    queen_sq = white_queens[0]

    if chess.F7 not in board.attacks(queen_sq):
        return False

    bc4 = board.piece_at(chess.C4)
    if (
        bc4 is None
        or bc4.color != chess.WHITE
        or bc4.piece_type != chess.BISHOP
    ):
        return False

    return _qxf7_is_mate(board, queen_sq)


def _qxf7_is_mate(board: chess.Board, queen_sq: chess.Square) -> bool:
    """Hypothetical: if it were white's turn, would Qxf7 deliver mate?

    We deep-copy the board, force the turn to white, and try the move.
    python-chess.is_checkmate() does the rest.
    """
    test_board = board.copy()
    if test_board.turn == chess.BLACK:
        # Hand white the move. Clear en-passant so the legal-move
        # generator doesn't trip over a stale ep target meant for the
        # other side.
        test_board.turn = chess.WHITE
        test_board.ep_square = None

    qxf7 = chess.Move(queen_sq, chess.F7)
    if qxf7 not in test_board.legal_moves:
        return False
    test_board.push(qxf7)
    return test_board.is_checkmate()
