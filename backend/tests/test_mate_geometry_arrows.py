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
        """From where the rook ENDS UP, because this picture renders on the
        board after the mating move: c7 is empty there and the rook is on c8.
        The first version drew from c7 and so began on a bare square."""
        arrows = _arrows()
        assert arrows[0]["from"] == "c8"
        assert arrows[0]["to"] == "e8"
        assert arrows[0]["color"] == "red"

    def test_every_arrow_starts_from_a_real_piece_on_the_mate_board(self):
        board = chess.Board(FEN)
        mate = board.parse_san("Rc8#")
        after = board.copy()
        after.push(mate)
        for arrow in _arrows():
            square = chess.parse_square(arrow["from"])
            assert after.piece_at(square) is not None, (
                f"{arrow['from']}->{arrow['to']} starts on an empty square")

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


class TestTheBoardThePlayerIsLookingAt:
    """Mohit 2026-10-06: "now, no arrow at all, what's wrong with you".

    Suppressing the contradictory shape arrows and leaving the board blank was
    the wrong call. He asked to SEE the mating pattern. Silence beats
    contradiction, but a true picture beats both -- and the post-mate picture
    cannot be reused here, because on this board the rook has not reached c8
    and the bishop has left e6.
    """

    def _played(self):
        board = chess.Board(FEN)
        return board, board.parse_san("Bd5"), board.parse_san("Rc8#")

    def test_it_draws_the_move_that_was_mate(self):
        from services.caption_pipeline import mate_arrows_for_played_board
        board, played, mate = self._played()
        arrows = mate_arrows_for_played_board(board, played, mate.uci())
        assert arrows, "the board must not be blank on a missed mate"
        assert (arrows[0]["from"], arrows[0]["to"]) == ("c7", "c8")

    def test_the_rook_is_really_still_on_c7_here(self):
        """Unlike the mate board, where it has already moved."""
        board, played, _ = self._played()
        after = board.copy()
        after.push(played)
        piece = after.piece_at(chess.C7)
        assert piece is not None and piece.piece_type == chess.ROOK

    def test_it_keeps_the_cover_lines(self):
        from services.caption_pipeline import mate_arrows_for_played_board
        board, played, mate = self._played()
        covers = {(a["from"], a["to"])
                  for a in mate_arrows_for_played_board(board, played, mate.uci())[1:]}
        assert ("e6", "d7") in covers
        assert ("e6", "f7") in covers

    def test_the_cover_lines_start_from_the_square_the_bishop_left(self):
        """e6 is empty on this board, and that is the lesson: it is already
        highlighted as the from-square, so the lines read 'your bishop was
        here, holding these'."""
        board, played, _ = self._played()
        after = board.copy()
        after.push(played)
        assert after.piece_at(chess.E6) is None
        assert played.from_square == chess.E6

    def test_a_move_that_is_not_mate_draws_nothing_here_either(self):
        from services.caption_pipeline import mate_arrows_for_played_board
        board, played, _ = self._played()
        assert mate_arrows_for_played_board(
            board, played, board.parse_san("Bb3").uci()) == []
