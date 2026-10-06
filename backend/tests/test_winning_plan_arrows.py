"""Draw the whole idea: the move, the chase, and the capture.

Mohit 2026-10-06: "for a 1000, he couldn't really see Be5 attacking rook, but
rook can move right? and then white bishop traps him, so i want to show the
complete idea with arrow, you know so user can see everything together... the
idea is to really find a move in stockfish line that actually takes up the
bigger piece".

"Be5 attacks the rook" is useless alone, because the rook moves. The lesson is
that it gets caught anyway.
"""
from __future__ import annotations

import os
import sys

import chess

_BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

from services.caption_pipeline import winning_plan_arrows  # noqa: E402

# Game 66ac48e5 move 24: White played O-O, Be5 was best "and it wins the rook".
FEN = "Bn3b1r/2k1p2p/p2n2p1/5p2/3p1B2/7N/1PP2PPP/4K2R w K - 2 24"
LINE = ["Rg8", "Bd5", "e6", "Bxe6", "Rg7", "Bxg7", "Bxg7", "Nf4"]


def _plan(fen=FEN, san="Be5", line=None):
    board = chess.Board(fen)
    return winning_plan_arrows(
        board, board.parse_san(san).uci(), LINE if line is None else line)


class TestTheCompleteIdea:

    def test_it_draws_the_move_the_chase_and_the_capture(self):
        assert [(a["from"], a["to"], a["color"]) for a in _plan()] == [
            ("f4", "e5", "blue"),
            ("h8", "g8", "palegrey"),
            ("g8", "g7", "palegrey"),
            ("e5", "g7", "green"),
        ]

    def test_the_payoff_is_the_rook_not_the_pawn_on_the_way(self):
        """Bxe6 grabs a pawn at step four. The lesson is the rook."""
        board = chess.Board(FEN)
        board.push_san("Be5")
        for san in ["Rg8", "Bd5", "e6"]:
            board.push_san(san)
        taken = board.piece_at(chess.E6)
        assert taken is not None and taken.piece_type == chess.PAWN
        assert _plan()[-1]["to"] == "g7", "the picture must end on the rook"

    def test_the_bishop_that_takes_it_is_the_one_we_moved(self):
        """Which is what makes the plan one idea rather than two."""
        arrows = _plan()
        assert arrows[0]["to"] == arrows[-1]["from"] == "e5"

    def test_the_chase_really_is_the_rook_moving_twice(self):
        board = chess.Board(FEN)
        board.push_san("Be5")
        assert board.parse_san("Rg8").from_square == chess.H8
        for san in ["Rg8", "Bd5", "e6", "Bxe6"]:
            board.push_san(san)
        assert board.parse_san("Rg7").from_square == chess.G8

    def test_the_picture_stays_small(self):
        assert len(_plan()) <= 5


class TestItOnlyFiresOnARealPlan:

    def test_a_line_with_no_big_capture_draws_nothing(self):
        """A pawn grab is not worth four arrows."""
        assert _plan(line=["Rg8", "Bd5", "e6", "Bxe6"]) == []

    def test_no_line_draws_nothing(self):
        assert _plan(line=[]) == []

    def test_an_unreadable_line_is_not_guessed_past(self):
        assert _plan(line=["not-a-move", "Rg7", "Bxg7"]) == []

    def test_an_illegal_recommendation_draws_nothing(self):
        board = chess.Board(FEN)
        assert winning_plan_arrows(board, "a1a8", LINE) == []

    def test_garbage_draws_nothing(self):
        board = chess.Board(FEN)
        assert winning_plan_arrows(board, "zzzz", LINE) == []
        assert winning_plan_arrows(None, "f4e5", LINE) == []
        assert winning_plan_arrows(board, None, LINE) == []


class TestARecaptureIsNotAWin:
    """The capture must leave us AHEAD, not merely even.

    Found by inspecting corpus output rather than by being told. On this
    position the engine line is Qd3 Qxd3 Nxd3 -- a queen TRADE. Nxd3 takes a
    queen, clears the 320 threshold, and the picture would have announced
    "play Qd3 and win the queen" about an even swap. A recapture looks
    identical to a win if you only read the piece that came off the board.
    """

    TRADE_FEN = "5rk1/1pp3p1/3qp2p/p3p3/P3Pn2/N1P2NPP/1PQ2B2/6K1 b - - 0 24"
    TRADE_LINE = ["Qxd3", "Nxd3", "Kg2", "Nxb2", "Nxe5", "Nxa4"]

    def test_the_line_really_is_an_even_trade(self):
        board = chess.Board(self.TRADE_FEN)
        board.push_san("Qd3")
        taken_from_us = board.piece_at(chess.D3)
        assert taken_from_us is not None and taken_from_us.piece_type == chess.QUEEN
        board.push_san("Qxd3")          # they take our queen
        recaptured = board.piece_at(chess.D3)
        assert recaptured is not None and recaptured.piece_type == chess.QUEEN
        board.push_san("Nxd3")          # we take theirs: net zero

    def test_so_it_draws_no_plan(self):
        board = chess.Board(self.TRADE_FEN)
        assert winning_plan_arrows(
            board, board.parse_san("Qd3").uci(), self.TRADE_LINE) == []

    def test_the_reported_card_still_draws_its_plan(self):
        """The guard must not cost the case it was built for: Be5 wins a rook
        outright and gives nothing back."""
        assert len(_plan()) == 4
