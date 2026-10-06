"""A card that names a better move must draw it.

Mohit 2026-10-06, on "O-O is a major blunder. Be5 was better -- it wins the
rook" over an empty board: "now why not arrow here?".

The best-move picture came only from _check_attack_arrows, which requires the
move to give CHECK. Be5 does not, so a card naming a concrete prize drew
nothing -- the same shape as the "you can win it with bxc5" card one surface
over.
"""
from __future__ import annotations

import os
import sys

import chess

_BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

from services.caption_pipeline import recommended_move_arrows  # noqa: E402

# The reported position: game 66ac48e5 move 24, White played O-O, Be5 was best.
FEN = "Bn3b1r/2k1p2p/p2n2p1/5p2/3p1B2/7N/1PP2PPP/4K2R w K - 2 24"
LINE = ["Rg8", "Bd5", "e6", "Bxe6", "Rg7", "Bxg7"]


def _arrows(line=None, san="Be5"):
    board = chess.Board(FEN)
    return recommended_move_arrows(
        board, board.parse_san(san).uci(), LINE if line is None else line)


class TestTheMoveItselfIsAlwaysDrawn:

    def test_the_card_no_longer_draws_nothing(self):
        assert _arrows(), "a card naming a better move drew an empty board"

    def test_it_draws_the_recommended_move(self):
        first = _arrows()[0]
        assert (first["from"], first["to"]) == ("f4", "e5")

    def test_it_works_without_a_stored_line(self):
        """The move is true whether or not we know their reply."""
        assert _arrows(line=[])[0]["to"] == "e5"

    def test_be5_is_not_a_check(self):
        """Pin down why the old builder stayed silent."""
        board = chess.Board(FEN)
        board.push_san("Be5")
        assert not board.is_check()


class TestItDoesNotClaimAPieceTheReplyMoves:
    """v184's rule, applied to the picture instead of the sentence."""

    def test_be5_really_does_attack_the_rook(self):
        board = chess.Board(FEN)
        board.push_san("Be5")
        assert chess.H8 in board.attacks(chess.E5)
        rook = board.piece_at(chess.H8)
        assert rook is not None and rook.piece_type == chess.ROOK

    def test_but_their_reply_moves_it(self):
        board = chess.Board(FEN)
        board.push_san("Be5")
        reply = board.parse_san("Rg8")
        assert reply.from_square == chess.H8

    def test_so_no_arrow_is_drawn_to_h8(self):
        targets = {a["to"] for a in _arrows()}
        assert "h8" not in targets, (
            "the rook is won nine plies later, not on arrival")

    def test_a_defended_piece_is_not_claimed_either(self):
        """The knight on d6 is held by their king on c7."""
        board = chess.Board(FEN)
        board.push_san("Be5")
        assert chess.C7 in board.attackers(chess.BLACK, chess.D6)
        assert "d6" not in {a["to"] for a in _arrows()}

    def test_an_unreadable_line_still_draws_only_the_move(self):
        assert [a["to"] for a in _arrows(line=["not-a-move"])] == ["e5"]


class TestItStaysQuietWhenItShould:

    def test_an_illegal_recommendation_draws_nothing(self):
        board = chess.Board(FEN)
        assert recommended_move_arrows(board, "a1a8", LINE) == []

    def test_garbage_draws_nothing(self):
        board = chess.Board(FEN)
        assert recommended_move_arrows(board, "zzzz", LINE) == []
        assert recommended_move_arrows(None, "f4e5", LINE) == []
        assert recommended_move_arrows(board, None, LINE) == []
