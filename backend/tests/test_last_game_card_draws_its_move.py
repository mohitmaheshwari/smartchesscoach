"""The card draws the move it names.

Mohit 2026-10-17, on a card showing 4...Bd6: "look, bd6 here, look at
board, it doesn't make sense."

The board is the position BEFORE the turning move, so on move 4 every
black piece is still on its home square. The card said "They played Bd6
here" and drew no arrow, so nothing on screen connected the sentence to
the picture. The move itself was right -- Stockfish puts the swing at
+160 to +612, the largest in that game, because Bd6 allows Qh5+.

Squares are derived from the stored FEN and SAN at card-build time, not
written by the review, because reviews are cached: deriving fixes every
card that already exists without re-analysing anything.
"""
import sys
from pathlib import Path

import chess

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.both_sides_review import turning_point_squares  # noqa: E402

FEN = "rnbqkbnr/ppp3pp/8/3pNP2/8/8/PPPP1PPP/RNBQKB1R b KQkq - 0 4"


def test_the_squares_match_the_named_move():
    got = turning_point_squares({"fen_before": FEN, "san": "Bd6"})
    assert got == {"from": "f8", "to": "d6"}


def test_the_squares_agree_with_the_board():
    """Derived, not guessed: parse the SAN and compare."""
    got = turning_point_squares({"fen_before": FEN, "san": "Bd6"})
    move = chess.Board(FEN).parse_san("Bd6")
    assert chess.square_name(move.from_square) == got["from"]
    assert chess.square_name(move.to_square) == got["to"]


def test_a_capture_is_drawn_to_the_square_it_lands_on():
    """Bxf5 is the OTHER bishop, c8->f5. Written first as an
    illegal-move case, which the test caught: in this position both
    bishops have a move and only the board says which one."""
    assert turning_point_squares({"fen_before": FEN, "san": "Bxf5"}) == {
        "from": "c8", "to": "f5"}


def test_a_knight_move_is_drawn():
    assert turning_point_squares({"fen_before": FEN, "san": "Nc6"}) == {
        "from": "b8", "to": "c6"}


def test_an_illegal_san_draws_nothing():
    assert turning_point_squares({"fen_before": FEN, "san": "dxe4"}) == {}


def test_a_bad_row_costs_the_arrow_not_the_card():
    assert turning_point_squares(None) == {}
    assert turning_point_squares({}) == {}
    assert turning_point_squares({"fen_before": FEN}) == {}
    assert turning_point_squares({"san": "Bd6"}) == {}
    assert turning_point_squares({"fen_before": "nonsense", "san": "Bd6"}) == {}
    assert turning_point_squares({"fen_before": FEN, "san": "Qz9"}) == {}
