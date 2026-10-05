"""A move that keeps a forced mate is not a mistake.

Mohit, 2026-10-05, on a K+2B vs K+P endgame card reading
"Bg5 - Blunder - Tactical, missed tactic", with "We can't show a clear
reason here": "look at it".

At depth 22 the engine says Be6 mates in 9, Ke6 mates in 10, and the Bg5 he
played mates in 20. He was mating before the move and mating after it, and
we called it a blunder.

The cause is that `mate_info` is read nowhere in the render path. Severity
comes from cp_loss, and in a mate position cp_loss is the difference between
two clamped mate scores -- so "mate in 9 became mate in 20" and "you dropped
a rook" are the same number. Measured on the rendered cards: 3,966 are tiered as
an error while the mover still has a forced mate, 3,770 of them saying
BLUNDER, and in 2,609 the mate got FASTER -- we called people blunderers for
mating sooner. One player (3da52c5e) is told "blunder" on three consecutive
moves while delivering mate.
"""
from __future__ import annotations

import os
import sys

import chess
import pytest

_BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

from services.caption_pipeline import compute_severity_for_move  # noqa: E402

# The reported position: White Ke5 Bf5 Bh4, Black Kg7 pawn h5. White to move.
REPORTED_FEN = "8/6k1/8/4KB1p/7B/8/8/8 w - - 0 1"

# Mate scores as the analysis stores them: clamped, white-POV, higher means a
# shorter mate. Mate in 9 before, mate in 20 after.
MATE_IN_9 = 9910
MATE_IN_20 = 9800
ERROR_TIERS = {"inaccuracy", "mistake", "serious", "blunder"}


def _severity(fen, played_san, cp_loss, eval_before, eval_after, is_white=True):
    board = chess.Board(fen)
    return compute_severity_for_move(
        cp_loss=cp_loss,
        opp_cp_loss=cp_loss,
        is_user=True,
        is_white=is_white,
        user_color="white" if is_white else "black",
        mate_sentinel_eval_cp=None,
        user_eval_before_white_pov=eval_before,
        user_eval_after_white_pov=eval_after,
        opp_eval_before=None,
        opp_eval_after=None,
        board_before=board,
        played_move=board.parse_san(played_san),
        prev_move=None,
        full_move_number=1,
        best_move_san="Be6",
        played_san=played_san,
    )


class TestTheReportedCard:

    def test_a_slower_mate_is_not_an_error(self):
        out = _severity(REPORTED_FEN, "Bg5", cp_loss=110,
                        eval_before=MATE_IN_9, eval_after=MATE_IN_20)
        assert out.mate_preserved is True
        assert out.severity_user_facing not in ERROR_TIERS, (
            "he was mating before and after; this is not a blunder")

    def test_even_a_much_slower_mate_is_not_a_blunder(self):
        out = _severity(REPORTED_FEN, "Bg5", cp_loss=900,
                        eval_before=9990, eval_after=9660)
        assert out.severity_user_facing not in ERROR_TIERS

    def test_a_faster_mate_is_not_an_error_either(self):
        """90 of the 94 mislabelled moves were this case."""
        out = _severity(REPORTED_FEN, "Bg5", cp_loss=120,
                        eval_before=9800, eval_after=9950)
        assert out.severity_user_facing not in ERROR_TIERS


class TestItOnlyTouchesMatePositions:

    def test_a_real_blunder_without_mate_is_untouched(self):
        """The negative control: ordinary positions must still be judged."""
        out = _severity(REPORTED_FEN, "Bg5", cp_loss=900,
                        eval_before=300, eval_after=-600)
        assert out.mate_preserved is False
        assert out.severity_user_facing in ERROR_TIERS, (
            "a 900cp loss with no mate on the board is still a blunder")

    def test_the_highest_non_mate_eval_in_the_corpus_is_not_a_mate(self):
        """8308 is the largest eval the corpus carries without a mate score;
        9650 is the smallest it carries with one. The floor sits between."""
        out = _severity(REPORTED_FEN, "Bg5", cp_loss=900,
                        eval_before=8308, eval_after=8308)
        assert out.mate_preserved is False

    def test_losing_a_mate_outright_is_still_an_error(self):
        """Mate before, no mate after: that really is a blunder."""
        out = _severity(REPORTED_FEN, "Bg5", cp_loss=900,
                        eval_before=MATE_IN_9, eval_after=120)
        assert out.mate_preserved is False
        assert out.severity_user_facing in ERROR_TIERS


class TestTheMoverPointOfView:

    def test_black_mating_is_read_from_blacks_side(self):
        """Evals are white-POV. A black forced mate is a large NEGATIVE
        number, and must not be read as black being mated."""
        fen = "8/6K1/8/4kb1P/7b/8/8/8 b - - 0 1"
        board = chess.Board(fen)
        assert board.turn == chess.BLACK
        out = compute_severity_for_move(
            cp_loss=110, opp_cp_loss=110, is_user=True, is_white=False,
            user_color="black", mate_sentinel_eval_cp=None,
            user_eval_before_white_pov=-MATE_IN_9,
            user_eval_after_white_pov=-MATE_IN_20,
            opp_eval_before=None, opp_eval_after=None,
            board_before=board, played_move=board.parse_san("Bg5"),
            prev_move=None, full_move_number=1,
            best_move_san=None, played_san="Bg5",
        )
        assert out.mate_preserved is True
        assert out.severity_user_facing not in ERROR_TIERS

    def test_black_being_mated_is_not_mistaken_for_black_mating(self):
        """Same magnitudes, opposite sign: here WHITE is mating, so black's
        move must still be judged normally."""
        fen = "8/6K1/8/4kb1P/7b/8/8/8 b - - 0 1"
        board = chess.Board(fen)
        out = compute_severity_for_move(
            cp_loss=900, opp_cp_loss=900, is_user=True, is_white=False,
            user_color="black", mate_sentinel_eval_cp=None,
            user_eval_before_white_pov=MATE_IN_9,
            user_eval_after_white_pov=MATE_IN_20,
            opp_eval_before=None, opp_eval_after=None,
            board_before=board, played_move=board.parse_san("Bg5"),
            prev_move=None, full_move_number=1,
            best_move_san=None, played_san="Bg5",
        )
        assert out.mate_preserved is False
