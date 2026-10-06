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
        """Including the OTHER bishop, which is the mechanism.

        Mohit 2026-10-06, reading the rendered card: "a8 bishop is missing,
        the arrow is missing there". Without a8->d5 the rook appears to run
        for no reason -- it is Bd5 hitting g8 through e6 and f7 that forces
        the second flight to g7, where the first bishop takes it. Two bishops
        cornering a rook.
        """
        assert [(a["from"], a["to"], a["color"]) for a in _plan()] == [
            ("f4", "e5", "blue"),       # Be5 attacks the rook on h8
            ("h8", "g8", "palegrey"),   # it runs
            ("a8", "d5", "blue"),       # the other bishop now hits g8
            ("g8", "g7", "palegrey"),   # it runs again
            ("e5", "g7", "green"),      # and the first bishop takes it
        ]

    def test_the_hunter_really_does_attack_the_square_it_drove_it_from(self):
        """Verified on the board, not assumed from the move order."""
        board = chess.Board(FEN)
        for san in ["Be5", "Rg8", "Bd5"]:
            board.push_san(san)
        assert chess.G8 in board.attacks(chess.D5), (
            "Bd5 must actually hit g8, or the arrow explains nothing")

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
        assert len(_plan()) == 5


class TestOurPieceGetsThereVisibly:
    """An arrow may not start from a square our piece has not reached.

    Mohit 2026-10-06, pointing at a lone green arrow: "why this arrow?". The
    card drew h1->a8 for a capture that is real but nine plies away, after the
    queen travels g1 -> c1 -> h1. On the board he was looking at the queen is
    on g1, so the arrow began on an empty square with no way to see how it got
    there -- the same fault as the mate arrow that started on c7 after the rook
    had already moved to c8.
    """

    FEN37 = "Q7/p4ppk/7p/8/1P1P1KP1/Pb3P2/8/6q1 b - - 3 37"
    LINE37 = ["Ke4", "Qc1", "f4", "Qh1+", "Ke3", "gxf4+", "Kxf4", "Qxa8"]

    def _plan37(self):
        board = chess.Board(self.FEN37)
        return winning_plan_arrows(
            board, board.parse_san("g5+").uci(), self.LINE37)

    def test_the_first_arrow_of_the_route_stands_on_the_real_queen(self):
        board = chess.Board(self.FEN37)
        piece = board.piece_at(chess.G1)
        assert piece is not None and piece.piece_type == chess.QUEEN
        froms = [a["from"] for a in self._plan37()]
        assert "g1" in froms, "the route must start where the queen actually is"

    def test_the_whole_route_is_drawn(self):
        pairs = [(a["from"], a["to"]) for a in self._plan37()]
        assert ("g1", "c1") in pairs
        assert ("c1", "h1") in pairs
        assert ("h1", "a8") in pairs

    def test_each_step_is_reached_by_the_one_before_it(self):
        """So no arrow appears from nowhere, even on squares empty right now."""
        route = [(a["from"], a["to"]) for a in self._plan37()
                 if a["from"] != "g7"]
        for (_prev_from, prev_to), (nxt_from, _nxt_to) in zip(route, route[1:]):
            assert prev_to == nxt_from, f"{prev_to} does not lead to {nxt_from}"

    def test_the_payoff_really_takes_the_queen(self):
        board = chess.Board(self.FEN37)
        board.push_san("g5+")
        for san in self.LINE37[:-1]:
            board.push_san(san)
        target = board.piece_at(chess.A8)
        assert target is not None and target.piece_type == chess.QUEEN
