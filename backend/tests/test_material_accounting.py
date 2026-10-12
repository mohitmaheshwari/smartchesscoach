"""Material across a line, counted from before the move. Nothing subtler.

Mohit 2026-10-12, after a card told him dxc5 lost a pawn when bxc5 simply
recaptured: "you're hallucinating on lost material moves, they are easiest
bro". He is right. The error was accounting, not chess -- the swing was
measured starting AFTER his own capture, so the gain was treated as the
baseline and the recapture read as a loss. 318 cards were affected.

`_story_swing` already carries a docstring warning about this exact mistake,
written after it happened once before. It happened again in new code hours
later, which is why this file exists: the cheapest thing in chess gets a test
so the third time is caught by CI and not by Mohit reading a board.

Every case below is hand-checkable in one line.
"""
from __future__ import annotations

import os
import sys

import chess
import pytest

_BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

from services.caption_pipeline import _story_swing  # noqa: E402

# The card Mohit read. White's d4 pawn takes on c5, Black's b6 pawn takes back.
# A pawn for a pawn: nothing is lost and nothing is won.
CARD_12 = "rn1q1rk1/pb2npbp/1p2p1p1/2ppP1B1/3P4/2NB4/PPPN1PPP/R2Q1RK1 w - - 0 12"

# Simple, constructed, each one obvious at a glance. First written with the
# black pawn on c7, where cxd5 is not a legal capture at all -- the code
# correctly stopped at the illegal move and my fixture was the thing that
# was wrong. A test for the easiest arithmetic in chess should at least use
# legal moves.
FREE_PAWN = "4k3/8/8/3p4/4P3/8/8/4K3 w - - 0 1"        # exd5, nothing recaptures
EVEN_TRADE = "4k3/8/2p5/3p4/4P3/8/8/4K3 w - - 0 1"      # exd5 cxd5
LOSE_A_PIECE = "4k3/8/2p5/3p4/8/4N3/8/4K3 w - - 0 1"    # Nxd5 cxd5


class TestTheCardThatWasWrong:
    """dxc5 bxc5 is a pawn for a pawn. The old code called it minus one."""

    def test_an_even_recapture_is_zero(self):
        board = chess.Board(CARD_12)
        swing = _story_swing(board, "dxc5", ["bxc5"], board.turn)
        assert swing == 0, (
            f"dxc5 bxc5 is a pawn for a pawn; got {swing}. A non-zero answer "
            f"here means the baseline moved back after the played move again.")

    def test_and_the_longer_stored_line_is_also_zero(self):
        """The real line continues Re1 Nd7 Nf3 with no further captures."""
        board = chess.Board(CARD_12)
        swing = _story_swing(board, "dxc5", ["bxc5", "Re1", "Nd7", "Nf3"],
                             board.turn)
        assert swing == 0


class TestTheThreeCasesThatCoverIt:
    """A capture that keeps the pawn, one that trades it, one that loses a
    piece for it. If all three are right the accounting is right."""

    def test_a_free_pawn_is_plus_one(self):
        board = chess.Board(FREE_PAWN)
        assert _story_swing(board, "exd5", [], board.turn) == 1

    def test_an_even_trade_is_zero(self):
        board = chess.Board(EVEN_TRADE)
        assert _story_swing(board, "exd5", ["cxd5"], board.turn) == 0

    def test_a_knight_for_a_pawn_is_minus_two(self):
        board = chess.Board(LOSE_A_PIECE)
        assert _story_swing(board, "Nxd5", ["cxd5"], board.turn) == -2


class TestTheBaselineItself:
    """The whole bug in one assertion: the player's own capture must be
    counted, not assumed."""

    def test_the_capture_the_move_itself_makes_is_counted(self):
        """Measuring from after the move would make this 0 instead of +1."""
        board = chess.Board(FREE_PAWN)
        assert _story_swing(board, "exd5", [], board.turn) == 1

    def test_a_quiet_move_changes_nothing(self):
        board = chess.Board(FREE_PAWN)
        assert _story_swing(board, "Kd2", [], board.turn) == 0

    @pytest.mark.parametrize("line", [[], ["cxd5"], ["cxd5", "Kd2"]])
    def test_the_answer_does_not_drift_with_line_length(self, line):
        """Once the captures are done, extra quiet moves must not move it."""
        board = chess.Board(EVEN_TRADE)
        expected = 1 if not line else 0
        assert _story_swing(board, "exd5", line, board.turn) == expected
