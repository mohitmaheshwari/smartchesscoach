"""Whose move is it? Read the board, not the flag.

The caption layer addresses the reader differently depending on this one
boolean: "you played Nf3" against "your opponent played Nf3". It used to be
hardcoded -- everything in move_evaluations was the reader's, everything in
opponent_move_evaluations was theirs -- which holds for imported games and
is wrong for 130 of Mohit's, where both sides sit in move_evaluations with
the opponent's entries unflagged. Every Play-with-Coach game has that shape.

Nothing wrong reached a screen, because the caption writer has never run on
a PWC game: 0 captions across 1,158 user moves in 120 of them, against 100
on imported games. These tests are so that it stays that way when it does.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analysis_worker import mover_is_user

WHITE_TO_MOVE = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
BLACK_TO_MOVE = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"


class TestItReadsTheSideToMove:
    def test_white_reader_owns_the_white_moves(self):
        assert mover_is_user({"fen_before": WHITE_TO_MOVE}, "white") is True
        assert mover_is_user({"fen_before": BLACK_TO_MOVE}, "white") is False

    def test_black_reader_owns_the_black_moves(self):
        assert mover_is_user({"fen_before": BLACK_TO_MOVE}, "black") is True
        assert mover_is_user({"fen_before": WHITE_TO_MOVE}, "black") is False

    def test_user_color_casing_and_absence(self):
        assert mover_is_user({"fen_before": WHITE_TO_MOVE}, "WHITE") is True
        assert mover_is_user({"fen_before": WHITE_TO_MOVE}, "White") is True
        # no colour recorded: the repo's own default is white
        assert mover_is_user({"fen_before": WHITE_TO_MOVE}, None) is True
        assert mover_is_user({"fen_before": WHITE_TO_MOVE}, "") is True


class TestItDoesNotTrustTheFlag:
    def test_an_unflagged_opponent_move_is_still_theirs(self):
        """The 130-game shape: the opponent's entry carries no
        is_opponent_move at all."""
        move = {"fen_before": BLACK_TO_MOVE, "move": "e5"}
        assert "is_opponent_move" not in move
        assert mover_is_user(move, "white") is False

    def test_a_flag_that_contradicts_the_board_loses(self):
        """If a writer ever sets the flag wrongly, the board wins. The board
        is the thing that cannot be stale."""
        assert mover_is_user(
            {"fen_before": BLACK_TO_MOVE, "is_opponent_move": False},
            "white") is False
        assert mover_is_user(
            {"fen_before": WHITE_TO_MOVE, "is_opponent_move": True},
            "white") is True


class TestItDoesNotUseMoveNumberParity:
    def test_a_black_readers_own_moves_are_numbered_from_one(self):
        """In the user-only storage shape a black player's moves are
        numbered 1, 2, 3..., so `move_number % 2 == 0` rejects half of them.
        That is the trap this function exists to avoid."""
        for number in (1, 2, 3, 4, 5):
            assert mover_is_user(
                {"fen_before": BLACK_TO_MOVE, "move_number": number},
                "black") is True


class TestTheFallbackIsTheCallersExpectation:
    def test_no_fen_falls_back_to_the_default(self):
        assert mover_is_user({}, "white", True) is True
        assert mover_is_user({}, "white", False) is False

    def test_a_malformed_fen_falls_back(self):
        for bad in ("", "not-a-fen", "8/8/8/8/8/8/8/8", None):
            assert mover_is_user({"fen_before": bad}, "white", True) is True
            assert mover_is_user({"fen_before": bad}, "white", False) is False

    def test_a_side_field_that_is_not_w_or_b_falls_back(self):
        fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR x KQkq - 0 1"
        assert mover_is_user({"fen_before": fen}, "white", False) is False


class TestTheWorkerUsesIt:
    def test_the_caption_lists_are_not_hardcoded_any_more(self):
        """Both the flagged-fault list and the plan list used to pin the
        boolean to a literal. A literal cannot be right for both storage
        shapes, so neither list may contain one."""
        source = (Path(__file__).resolve().parents[1]
                  / "analysis_worker.py").read_text(encoding="utf-8")
        start = source.index("_flagged = [")
        end = source.index("async def _write_all", start)
        region = source[start:end]
        # The hardcoded form is the tuple built straight in the
        # comprehension. `_mover_is_user(m, True)` contains the same
        # characters, so the assertion has to name the comprehension.
        assert "(m, True) for m in" not in region, (
            "a literal True cannot be right for a list holding both sides")
        assert "(m, False) for m in" not in region
        assert region.count("_mover_is_user") >= 4
