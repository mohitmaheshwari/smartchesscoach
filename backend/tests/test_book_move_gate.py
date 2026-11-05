"""The book-move gate withdraws the engine's grade only for a move that is
actually in a line we know.

Mohit 2026-11-05, on 5e68fc88 move 6: a card reading "Be2 was a mistake"
under a Mistake badge, with no why button. Both stored grades were "good"
because is_book_opening_move asked the opening DETECTOR about the sequence,
and the detector names an opening from a fixed prefix (e4 d5 is already the
Scandinavian), so any move after the prefix at up to 120 cp was "book".
"""
from __future__ import annotations

import os
import sys

import chess
import pytest

_BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

from services.game_decryption_v5_service import is_book_opening_move  # noqa: E402
from services.opening_mastery import _san_key, known_line_covers  # noqa: E402

# 1.e4 d5 2.exd5 Qxd5 3.d4 Nc6 4.Nf3 Bg4 5.Nc3 Qe6+ -- Mohit's game, White to move.
MOHIT_HISTORY = ["e4", "d5", "exd5", "Qxd5", "d4", "Nc6", "Nf3", "Bg4", "Nc3", "Qe6+"]
MOHIT_OPENING = "Nimzowitsch Defense Scandinavian Exchange Variation 4.Nf3 Bg4"

# The theory file's Scandinavian main line, as stored.
MAIN_LINE = ["e4", "d5", "exd5", "Qxd5", "Nc3", "Qa5", "d4", "Nf6", "Nf3", "Bf5", "Bc4", "e6", "Bd2", "c6"]


def _board_after(sans):
    b = chess.Board()
    for s in sans:
        b.push_san(s)
    return b


class TestTheLineMustCoverTheMove:
    def test_a_move_inside_the_known_line_is_book(self):
        assert known_line_covers(MAIN_LINE[:10]) is True          # ...Bf5 is in the line
        assert known_line_covers(MAIN_LINE[:6]) is True

    def test_a_move_the_line_does_not_hold_is_not_book_even_in_a_known_opening(self):
        # The detector still says "Scandinavian" for all of these; that is the
        # bug the old check had. The gate now needs the move itself.
        assert known_line_covers(MAIN_LINE[:9] + ["Bg4"]) is False
        assert known_line_covers(MOHIT_HISTORY + ["Be2"]) is False
        assert known_line_covers(MOHIT_HISTORY + ["Nb5"]) is False

    def test_check_marks_do_not_break_the_match(self):
        assert _san_key("Qe6+") == "qe6"
        assert _san_key("Qxf7#") == "qxf7"
        assert _san_key("O-O") == "o-o"

    def test_nothing_known_is_not_book(self):
        assert known_line_covers([]) is False
        assert known_line_covers(["a3", "h6", "a4", "h5", "a5"]) is False


class TestTheGateOnMohitsCard:
    def test_be2_keeps_its_grade(self):
        board = _board_after(MOHIT_HISTORY)
        assert board.fen() == "r3kbnr/ppp1pppp/2n1q3/8/3P2b1/2N2N2/PPP2PPP/R1BQKB1R w KQkq - 5 6"
        assert is_book_opening_move(board, "Be2", 10, MOHIT_OPENING, 113, move_history=MOHIT_HISTORY) is False

    def test_a_random_move_in_the_same_position_is_not_book_either(self):
        board = _board_after(MOHIT_HISTORY)
        assert is_book_opening_move(board, "Nb5", 10, MOHIT_OPENING, 113, move_history=MOHIT_HISTORY) is False

    def test_the_real_book_move_at_the_same_depth_still_is(self):
        history = MAIN_LINE[:9]                                     # White to play 5.Nf3 done; Black's ...Bf5 next
        board = _board_after(history)
        assert is_book_opening_move(board, "Bf5", 9, None, 40, move_history=history) is True

    def test_the_two_later_checks_are_unchanged(self):
        # Check 2: a named opening in the first eight plies is still trusted,
        # whatever the move. Not touched today; measured at 346 of the 653
        # withdrawn early cards on 2026-11-05.
        history = MAIN_LINE[:7]
        board = _board_after(history)
        assert is_book_opening_move(board, "h6", 7, "Scandinavian Defense", 50, move_history=history) is True
        # The 120 cp bar still ends the question before any check runs.
        board = _board_after(MOHIT_HISTORY)
        assert is_book_opening_move(board, "Be2", 10, MOHIT_OPENING, 121, move_history=MOHIT_HISTORY) is False
