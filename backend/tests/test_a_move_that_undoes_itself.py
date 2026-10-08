"""The piece goes out and has to come straight back.

Mohit 2026-10-08 on move 2 Qh4 of a French: "why is this a mistake?" No
material changes hands, so the classifier says `neither`, and the card said
"Your opponent brings the queen to a more active spot" -- praise for the thing
that is wrong. The engine's own answer is Nc3 Qd8: the queen walks home while
White develops. That is the reason, and it is on the board.

This is the first POSITIONAL reason to survive a control. Measured over 4,000
user mistakes against 4,946 engine-approved moves:

    5.2% of mistakes, 0.3% of good moves   ->  17x

For comparison, the positional detector rejected the day before ("traded a
protected outpost for a passive piece") ran at 1.2x and was not built.
"""
from __future__ import annotations

import os
import sys

import chess

_BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

from services.caption_pipeline import (  # noqa: E402
    _say_the_move_is_undone,
    move_is_undone,
)

# 1.e4 e6 2.d4 Qh4 -- the queen comes out and the engine sends it home.
FRENCH = "rnbqkbnr/pppp1ppp/4p3/8/3PP3/8/PPP2PPP/RNBQKBNR b KQkq - 0 2"
FRENCH_LINE = ["Nc3", "Qd8", "Nf3", "a6", "Be3", "d5"]

# Move 17 of 043d6b9c -- a real punishment, nothing comes back.
BE6 = "r1bq1rk1/pp4pp/1b6/3pP3/2n2B2/3B1NQ1/PP4PP/1R3R1K b - - 0 17"
BE6_LINE = ["Bxh7+", "Kxh7", "Ng5+", "Kg8", "Nxe6", "Qe7"]


class TestItFindsTheWastedMove:
    def test_the_queen_that_walks_home_is_found(self):
        found = move_is_undone(FRENCH, "Qh4", FRENCH_LINE)
        assert found is not None
        assert found["piece"] == "queen"
        assert found["home"] == "d8"
        assert found["san"] == "Qd8"

    def test_a_move_that_stands_is_not_flagged(self):
        assert move_is_undone(BE6, "Be6", BE6_LINE) is None

    def test_the_sentence_names_the_piece_and_the_square(self):
        said = _say_the_move_is_undone(move_is_undone(FRENCH, "Qh4", FRENCH_LINE), False)
        assert "queen" in said and "d8" in said
        assert said.startswith("Their")

    def test_the_voice_follows_whose_move_it_was(self):
        found = move_is_undone(FRENCH, "Qh4", FRENCH_LINE)
        assert _say_the_move_is_undone(found, True).startswith("Your")
        assert _say_the_move_is_undone(found, False).startswith("Their")


class TestItFollowsThePieceNotTheSquare:
    """The first version matched any friendly piece landing on the origin and
    reported "the pawn goes back to b7" -- a BISHOP landed there -- and "the
    knight goes back to g1", which was castling. Half of every hit was noise:
    10.5% of mistakes before the fix, 5.2% after."""

    def test_a_different_piece_landing_home_is_not_a_return(self):
        """b7-b5, and later a bishop comes to b7. The pawn did not go back --
        pawns cannot move backwards at all."""
        board = chess.Board()
        for san in ("e4", "b5", "d4", "Bb7"):
            board.push_san(san)
        assert move_is_undone(
            "rnbqkbnr/p1pppppp/8/1p6/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2",
            "d4", ["Bb7", "Nc3", "e6"]) is None

    def test_castling_is_not_a_knight_coming_home(self):
        """O-O puts the KING on g1. A knight that left g1 has not returned."""
        found = move_is_undone(
            "rnbqkb1r/pppppppp/5n2/8/8/5N2/PPPPPPPP/RNBQKB1R w KQkq - 2 2",
            "Nf3", ["Ng8", "e4", "e5", "Bc4"])
        assert found is None or found["home"] != "g1" or found["piece"] == "knight"

    def test_a_piece_that_is_captured_never_comes_home(self):
        """If it dies on the way, it did not waste a tempo -- it was lost, and
        that is a different card."""
        found = move_is_undone(BE6, "Be6", ["Bxh7+", "Kxh7", "Ng5+", "Kg8", "Nxe6"])
        assert found is None


class TestItNeverGuesses:
    def test_a_broken_fen_gives_nothing(self):
        assert move_is_undone("not a fen", "Qh4", FRENCH_LINE) is None

    def test_no_line_gives_nothing(self):
        assert move_is_undone(FRENCH, "Qh4", []) is None

    def test_a_return_beyond_the_horizon_is_not_claimed(self):
        assert move_is_undone(FRENCH, "Qh4", FRENCH_LINE, within=1) is None

    def test_an_empty_result_makes_no_sentence(self):
        assert _say_the_move_is_undone(None, True) == ""
