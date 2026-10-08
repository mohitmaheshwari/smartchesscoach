"""One short sentence per ply, and the square where a piece dies.

Mohit 2026-10-08, looking at a five-arrow board: "can we write short sentences
there, like bishop sacrifices on h7 and then checks king, king takes back,
fork, something very easy to explain, very short sentences" -- and "the piece
that is under attack should have a red background or something, so we see that
this is gone".

Arrows say WHERE. A player who cannot already see the tactic cannot read WHAT
off three lines.

Every sentence is derived from the board after that move. Nothing comes from
the caption or the evaluation.
"""
from __future__ import annotations

import os
import sys

import chess

_BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

from services.caption_pipeline import describe_line_steps  # noqa: E402

# Move 17 of 043d6b9c: the Greek-gift shape, ending on a fork.
FEN = "r1bq1rk1/pp4pp/1b6/3pP3/2n2B2/3B1NQ1/PP4PP/1R3R1K b - - 0 17"
LINE = ["Bxh7+", "Kxh7", "Ng5+", "Kg8", "Nxe6", "Qe7"]


def _steps():
    return describe_line_steps(FEN, "Be6", LINE)


class TestItReadsLikeAPersonTalking:
    def test_a_sacrifice_is_called_a_sacrifice(self):
        """"Bishop takes the pawn on h7" hides the whole point. It loses a
        bishop for a pawn; the point is what comes after."""
        text = _steps()[1]["text"]
        assert "gives itself up" in text
        assert "takes the pawn" not in text

    def test_a_recapture_is_called_taking_back(self):
        assert "takes back" in _steps()[2]["text"]

    def test_a_check_says_check(self):
        joined = " ".join(s["text"] for s in _steps())
        assert "Check." in joined or "checks the king" in joined

    def test_the_fork_is_named_with_both_pieces(self):
        text = _steps()[5]["text"]
        assert "forks" in text
        assert "queen" in text and "rook" in text

    def test_every_sentence_is_short(self):
        for step in _steps():
            assert len(step["text"].split()) <= 14, step["text"]

    def test_every_sentence_ends_as_a_sentence(self):
        for step in _steps():
            assert step["text"].endswith("."), step["text"]


class TestTheSquareWhereAPieceDies:
    def test_a_capture_marks_its_square(self):
        steps = _steps()
        assert steps[1]["captured_square"] == "h7"   # Bxh7+
        assert steps[2]["captured_square"] == "h7"   # Kxh7
        assert steps[5]["captured_square"] == "e6"   # Nxe6

    def test_a_quiet_move_marks_nothing(self):
        steps = _steps()
        assert steps[0]["captured_square"] is None   # Be6
        assert steps[3]["captured_square"] is None   # Ng5+
        assert steps[4]["captured_square"] is None   # Kg8

    def test_the_marked_square_really_held_an_enemy_piece(self):
        """Verified against the board, not trusted from the walk."""
        board = chess.Board(FEN)
        board.push_san("Be6")
        for step, san in zip(_steps()[1:], LINE):
            move = board.parse_san(san)
            was_capture = board.is_capture(move)
            assert (step["captured_square"] is not None) == was_capture, san
            board.push(move)


class TestItNeverGuesses:
    def test_a_broken_fen_gives_no_steps(self):
        assert describe_line_steps("not a fen", "Be6", LINE) == []

    def test_an_illegal_move_stops_the_walk_rather_than_throwing(self):
        steps = describe_line_steps(FEN, "Be6", ["Bxh7+", "Qxz9", "Ng5+"])
        assert len(steps) == 2          # Be6, Bxh7+ -- then it stops

    def test_no_line_gives_just_the_move(self):
        assert len(describe_line_steps(FEN, "Be6", [])) == 1

    def test_it_stops_at_the_step_budget(self):
        long_line = LINE + ["Nxf8", "Rxf8", "b3", "Rxf4"]
        assert len(describe_line_steps(FEN, "Be6", long_line, max_steps=4)) == 4
