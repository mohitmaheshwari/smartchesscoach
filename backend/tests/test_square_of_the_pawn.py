"""The rule of the square, drawn rather than asserted.

A verdict ("the king catches it") teaches nothing to a player who does not
already know the rule. The box does. These lock the geometry, and in
particular the case that looks like a contradiction on screen: the king is
OUTSIDE the square and still catches the pawn, because it moves first.
"""
import chess
import pytest

from services.board_concepts import square_of_the_pawn


def test_box_side_equals_the_moves_the_pawn_needs():
    r = square_of_the_pawn(chess.Board("7k/8/8/8/8/1P6/2K5/8 w - - 0 1"))
    assert r["pawn_square"] == "b3"
    assert r["pawn_steps"] == 5
    # b3 through g8: six files by six ranks.
    assert r["square_corners"] == ["b3", "g3", "b8", "g8"]
    assert len(r["square_squares"]) == 36
    assert "h8" not in r["square_squares"]


def test_king_outside_and_pawn_moves_first_promotes():
    r = square_of_the_pawn(chess.Board("7k/8/8/8/8/1P6/2K5/8 w - - 0 1"))
    assert r["king_inside_square"] is False
    assert r["verdict"] == "pawn_promotes"
    assert "outside the square" in r["explanation"]


def test_outside_the_square_but_catches_on_tempo():
    """The case worth teaching, and verified by playing it out.

    Kh8 is outside b3-g8, but with Black to move: Kg8 b4 Kf8 b5 Ke8 b6 Kd8
    b7 Kc7 b8=Q+ Kxb8 -- bare kings. Drawing only the box would look wrong
    here, so the payload names the tempo explicitly.
    """
    board = chess.Board("7k/8/8/8/8/1P6/2K5/8 b - - 0 1")
    r = square_of_the_pawn(board)
    assert r["king_inside_square"] is False
    assert r["enters_on_tempo"] is True
    assert r["verdict"] == "king_catches"
    assert "moves first" in r["explanation"]

    # and it really is a catch
    play = chess.Board("7k/8/8/8/8/1P6/8/6K1 b - - 0 1")
    for san in ["Kg8", "b4", "Kf8", "b5", "Ke8", "b6", "Kd8", "b7",
                "Kc7", "b8=Q+", "Kxb8"]:
        play.push_san(san)
    assert not play.pieces(chess.QUEEN, chess.WHITE)


def test_king_inside_the_square_catches():
    r = square_of_the_pawn(chess.Board("8/8/8/5k2/8/1P6/2K5/8 w - - 0 1"))
    assert r["king_inside_square"] is True
    assert r["verdict"] == "king_catches"
    assert "inside the square" in r["explanation"]


def test_edge_pawn_box_is_clipped_at_the_board():
    """An a-pawn cannot extend a full side to the left."""
    r = square_of_the_pawn(chess.Board("7k/8/8/8/8/P7/2K5/8 w - - 0 1"))
    assert all(sq[0] >= "a" for sq in r["square_squares"])
    assert r["square_corners"][0] == "a3"


def test_double_step_shortens_the_box():
    """A pawn still on its starting rank needs one move fewer."""
    start = square_of_the_pawn(chess.Board("7k/8/8/8/8/8/1P6/2K5 w - - 0 1"))
    assert start["pawn_square"] == "b2"
    assert start["pawn_steps"] == 5, "b2 promotes in 5 via the double step"


def test_blocked_pawn_is_not_this_lesson():
    """The rule does not apply to a pawn that cannot run."""
    assert square_of_the_pawn(chess.Board("8/8/8/8/8/1n6/1P6/2K1k3 w - - 0 1")) is None


def test_returns_none_when_there_is_no_passed_pawn():
    assert square_of_the_pawn(chess.Board()) is None


def test_every_listed_square_is_a_real_square():
    r = square_of_the_pawn(chess.Board("7k/8/8/8/8/1P6/2K5/8 w - - 0 1"))
    for name in r["square_squares"]:
        assert chess.parse_square(name) is not None
