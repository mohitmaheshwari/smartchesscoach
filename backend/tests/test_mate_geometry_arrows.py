"""Show why the mate is mate, not just which move delivers it.

Mohit 2026-10-05 on the Rc8# card: "this is a proper mating pattern, if all
squares of king are taken by our bishop and it's just behind it's own pawn so
that's also taken, you know, this is a geometry to learn and remember".

The card drew c7->c8 and said "a forcing move at the exposed king", which
names the move and teaches none of the pattern. A player who sees the two
bishop lines learns something reusable; a player who sees one rook arrow
learns one move.
"""
from __future__ import annotations

import os
import sys

import chess

_BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

from services.caption_pipeline import _mate_geometry_arrows  # noqa: E402

# The reported position, from game 66ac48e5 move 21. Rc8# is the only mate.
FEN = "rn2kb1r/2R1p2p/p3B1p1/5p2/3pn3/7N/1PP2PPP/2B1K2R w Kkq - 0 21"


def _arrows(fen=FEN, san="Rc8#"):
    board = chess.Board(fen)
    return _mate_geometry_arrows(board, board.parse_san(san).uci())


class TestTheReportedMate:

    def test_the_geometry_is_what_mohit_described(self):
        """Verify the premise on the board before testing the drawing."""
        board = chess.Board(FEN)
        board.push_san("Rc8#")
        assert board.is_checkmate()
        # Their own men take two squares...
        assert board.piece_at(chess.E7).piece_type == chess.PAWN
        assert board.piece_at(chess.E7).color == chess.BLACK
        assert board.piece_at(chess.F8).piece_type == chess.BISHOP
        assert board.piece_at(chess.F8).color == chess.BLACK
        # ...and our bishop takes the other two.
        assert chess.E6 in board.attackers(chess.WHITE, chess.D7)
        assert chess.E6 in board.attackers(chess.WHITE, chess.F7)

    def test_the_mating_piece_points_at_the_king(self):
        arrows = _arrows()
        assert arrows[0]["from"] == "c7"
        assert arrows[0]["to"] == "e8"
        assert arrows[0]["color"] == "red"

    def test_the_bishop_lines_are_drawn(self):
        covers = {(a["from"], a["to"]) for a in _arrows()[1:]}
        assert ("e6", "d7") in covers
        assert ("e6", "f7") in covers

    def test_their_own_blockers_are_not_drawn_as_attacks(self):
        """An arrow onto their own pawn would read as 'take this'."""
        targets = {a["to"] for a in _arrows()}
        assert "e7" not in targets, "their pawn blocks e7; nothing attacks it"
        assert "f8" not in targets, "their bishop blocks f8"

    def test_the_picture_stays_small(self):
        assert len(_arrows()) <= 4


class TestItOnlyFiresOnRealMate:

    def test_a_move_that_is_not_mate_draws_nothing(self):
        assert _arrows(san="Bd5") == []

    def test_an_illegal_move_draws_nothing(self):
        board = chess.Board(FEN)
        assert _mate_geometry_arrows(board, "a1a8") == []

    def test_garbage_input_draws_nothing(self):
        board = chess.Board(FEN)
        assert _mate_geometry_arrows(board, "not-a-move") == []
        assert _mate_geometry_arrows(None, "c7c8") == []
        assert _mate_geometry_arrows(board, None) == []


class TestTheMatePictureOwnsTheCard:
    """Mohit 2026-10-06, badge and caption already fixed: "now shows missed
    mate, but arrows are still showing for missed skewer".

    A shape detector had drawn e8->d8, d8->c7, d5->a8 on the main board while
    the caption said "Bd5 missed a checkmate". The mate geometry lives on a
    different board -- the one after the mating move, which is why it carries
    its own FEN -- so the contradiction is resolved by dropping the shape
    arrows, not by moving the mate ones.
    """

    def test_shape_arrows_go_when_there_is_a_mate_picture(self):
        from services.caption_pipeline import shape_arrows_survive_mate_picture
        mate = _arrows()
        assert mate, "precondition: the reported card has a mate picture"
        assert shape_arrows_survive_mate_picture(mate, mate) is False

    def test_shape_arrows_stay_on_an_ordinary_card(self):
        from services.caption_pipeline import shape_arrows_survive_mate_picture
        assert shape_arrows_survive_mate_picture([], [{"from": "a1", "to": "a8"}]) is True

    def test_shape_arrows_stay_when_the_mate_board_was_not_built(self):
        """Both halves are required: a mate picture that never reached the
        best-move surface must not silence the main board for nothing."""
        from services.caption_pipeline import shape_arrows_survive_mate_picture
        assert shape_arrows_survive_mate_picture(_arrows(), []) is True
