"""A sacrifice must be drawn through to the move that wins the material back.

Mohit 2026-10-06 on the Ng5 card: "the idea is missing, the main idea is bishop
takes the pawn and king takes bishop, our knight checks the king and the knight
now behind our knight gets captured by our queen, so that's the whole line and
arrow doesn't show until there, so it's not proper really".

Two faults. The line never reached the arrows at all -- opponent moves carry no
engine row (move_evaluations holds user moves only), so the card's
pv_after_played was empty, while the continuation sat in the next position's
eval being used to write the sentence. And the sacrifice branch stopped on the
first FORCING move, which is the check at ply 3, so the picture showed a bishop
given away for a check.
"""
from __future__ import annotations

import os
import sys

import chess

_BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

from services.caption_pipeline import _line_sequence_arrows  # noqa: E402

# Game e74a53fe move 5: the opponent plays Ng5, Bxf2+ is the answer.
FEN_BEFORE_NG5 = "rnbqk2r/ppp2ppp/3p1n2/2b1p3/2B1P3/2N2N2/PPPP1PPP/R1BQK2R w KQkq - 0 5"
LINE = ["Bxf2+", "Kxf2", "Ng4+", "Kg1", "Qxg5"]


def _board_after_ng5():
    board = chess.Board(FEN_BEFORE_NG5)
    board.push_san("Ng5")
    return board


class TestTheWholeIdeaIsDrawn:

    def test_it_reaches_the_recapture(self):
        arrows = _line_sequence_arrows(_board_after_ng5(), LINE)
        assert [(a["from"], a["to"]) for a in arrows] == [
            ("c5", "f2"),   # bishop takes the pawn
            ("e1", "f2"),   # king takes the bishop
            ("f6", "g4"),   # our knight checks
            ("f2", "g1"),   # king steps away
            ("d8", "g5"),   # our queen takes the knight back
        ]

    def test_the_last_arrow_is_the_payoff_colour(self):
        assert _line_sequence_arrows(_board_after_ng5(), LINE)[-1]["color"] == "green"

    def test_the_payoff_really_captures_the_knight(self):
        board = _board_after_ng5()
        for san in LINE[:-1]:
            board.push_san(san)
        victim = board.piece_at(chess.G5)
        assert victim is not None and victim.piece_type == chess.KNIGHT
        assert victim.color == chess.WHITE

    def test_the_first_move_really_is_a_sacrifice(self):
        """Otherwise this branch should not be the one running."""
        board = _board_after_ng5()
        board.push_san("Bxf2+")
        taken = board.piece_at(chess.F2)
        assert taken is not None and taken.piece_type == chess.BISHOP
        assert chess.E1 in board.attackers(chess.WHITE, chess.F2), (
            "the king can take it back, which is what makes it a sacrifice")


class TestItDoesNotStopOnTheFirstCheck:

    def test_the_check_is_not_the_last_arrow(self):
        arrows = _line_sequence_arrows(_board_after_ng5(), LINE)
        assert (arrows[-1]["from"], arrows[-1]["to"]) != ("f6", "g4"), (
            "stopping here shows a bishop given away for a check")

    def test_a_line_with_no_recapture_still_uses_the_forcing_move(self):
        """The fallback must survive: a sacrifice whose point is the check."""
        short = ["Bxf2+", "Kxf2", "Ng4+"]
        arrows = _line_sequence_arrows(_board_after_ng5(), short)
        assert arrows, "a forcing follow-up must still draw something"
        assert (arrows[-1]["from"], arrows[-1]["to"]) == ("f6", "g4")
