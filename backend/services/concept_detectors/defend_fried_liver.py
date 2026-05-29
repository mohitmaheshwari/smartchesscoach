"""
Defend-against-Fried-Liver in-game detector.

The Fried Liver Attack arises from the Italian Knight Attack:

    1.e4 e5 2.Nf3 Nc6 3.Bc4 Nf6 4.Ng5  d5
    5.exd5  Nxd5??  6.Nxf7!  Kxf7  7.Qf3+  …

After 5.exd5, Black to move. The trap is 5...Nxd5 (recapturing with the
knight) — White then plays Nxf7! which forks the queen on d8 and the
rook on h8 once Kxf7 is forced. Black ends up down material with a
naked king.

Defensive options for Black:
  5...Na5   — the canonical defense. Attacks Bc4, side-stepping the trap.
  5...b5    — the Ulvestad / Fritz variation. Also attacks the bishop.
  5...Nd4   — Lolli / sharper line.

Detection (Black to move at the position after 5.exd5):

    Pre-condition ("clean test"):
      - User plays Black
      - It IS black's turn
      - Early opening (full_move_number <= 7)
      - White owns Bc4 + Ng5 + pawn on d5 (the d5 came from exd5)
      - Black still has the knight that originally went to f6
        (i.e. a black knight on f6, in the canonical line)

    Grade:
      - 5...Nxd5 — walks into the Fried Liver trap                  → "missed"
      - Anything else (Na5 / b5 / Nd4 / Be7 / Qe7 / etc.)           → "applied"

We grade "anything not Nxd5" as applied because the SKILL being tested
is recognising the trap. Even a suboptimal alternative is better than
walking into the fork.
"""
from __future__ import annotations

from typing import Optional

import chess


def detect_defend_fried_liver_application(
    board_before: chess.Board,
    move: chess.Move,
    user_color: chess.Color,
) -> Optional[str]:
    if user_color != chess.BLACK:
        return None
    if board_before.turn != chess.BLACK:
        return None
    if board_before.fullmove_number > 7:
        return None

    if not _is_fried_liver_test_position(board_before):
        return None

    # The trap move is Nxd5 — black knight captures on d5.
    if not board_before.is_capture(move):
        return "applied"
    if move.to_square != chess.D5:
        return "applied"

    moved = board_before.piece_at(move.from_square)
    if moved is None or moved.piece_type != chess.KNIGHT:
        return "applied"

    return "missed"


def _is_fried_liver_test_position(board: chess.Board) -> bool:
    """Returns True when the position is the canonical Black-to-move
    Fried Liver test: white Bc4 + Ng5 + pawn on d5 + black Nf6 still
    on f6."""
    bc4 = board.piece_at(chess.C4)
    if (
        bc4 is None
        or bc4.color != chess.WHITE
        or bc4.piece_type != chess.BISHOP
    ):
        return False
    ng5 = board.piece_at(chess.G5)
    if (
        ng5 is None
        or ng5.color != chess.WHITE
        or ng5.piece_type != chess.KNIGHT
    ):
        return False
    d5 = board.piece_at(chess.D5)
    if (
        d5 is None
        or d5.color != chess.WHITE
        or d5.piece_type != chess.PAWN
    ):
        return False
    nf6 = board.piece_at(chess.F6)
    if (
        nf6 is None
        or nf6.color != chess.BLACK
        or nf6.piece_type != chess.KNIGHT
    ):
        return False
    return True
