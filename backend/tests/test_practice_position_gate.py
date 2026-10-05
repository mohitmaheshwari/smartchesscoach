"""The gate must reject the card that caused it and keep the obvious keepers.

Every position here is a real admitted practice position. Pure board
arithmetic: no DB, no engine.
"""
from __future__ import annotations

import os
import sys

import chess

_BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

from services.practice_position_gate import (  # noqa: E402
    MATERIAL_FLOOR_CP,
    evaluate_position,
    keeps,
)

# The card Mohit reported. Black's knight on e7 is attacked by Re1 and Bg5 and
# defended only by Kd8 -- lost before the student moves. The drill coaches the
# rook's destination and accepts Rf5, which abandons the knight.
E7_FEN = "r1bk1r2/ppp1n2N/3p4/6B1/8/1B1P4/PPP3PP/4R1K1 b - - 0 20"
E7_ACCEPTED = "f8f5"   # Rf5


class TestTheCardThatCausedThis:
    def test_the_e7_position_is_rejected(self):
        v = evaluate_position(E7_FEN, E7_ACCEPTED)
        assert not v.keep
        assert v.square == "e7"
        assert v.gain_cp >= 300          # a whole knight

    def test_and_the_reason_names_the_square_a_human_can_check(self):
        v = evaluate_position(E7_FEN, E7_ACCEPTED)
        assert "already" in v.reason
        board = chess.Board(E7_FEN)
        sq = chess.parse_square(v.square)
        # the thing the gate complains about is really there
        assert len(board.attackers(chess.WHITE, sq)) == 2
        assert len(board.attackers(chess.BLACK, sq)) == 1

    def test_the_move_the_card_calls_a_mistake_actually_defends_it(self):
        """Rf7 adds a defender to e7. That is why the card reads backwards."""
        board = chess.Board(E7_FEN)
        after = board.copy(); after.push_san("Rf7")
        assert len(after.attackers(chess.BLACK, chess.E7)) == 2


class TestItDoesNotThrowAwayGoodDrills:
    def test_a_mate_position_is_kept(self):
        """When the answer ends the game, material elsewhere is irrelevant.
        back_rank_mate_exact measured 38/38 kept; this is that shape."""
        fen = "6k1/5ppp/8/8/8/8/8/R5K1 w - - 0 1"
        assert keeps(fen, "a1a8")        # Ra8#

    def test_a_position_whose_answer_saves_the_piece_is_kept(self):
        """Nothing hanging before, nothing hanging after."""
        fen = "4k3/8/8/8/8/8/4P3/4K3 w - - 0 1"
        assert keeps(fen, "e2e4")

    def test_neither_candidate_saves_the_knight_which_is_the_whole_point(self):
        """Written expecting Rf7 to rescue e7 by defending it. It does not, and
        the gate was right: Bxe7+ arrives WITH CHECK, so the extra defender
        never gets to matter and the exchange still wins the piece.

        That is the strongest statement of why this position is not a piece
        safety drill -- every answer on offer loses the knight, so there is no
        move the student can find that makes the lesson true."""
        for answer in ("f8f5", "f8f7"):     # Rf5 and Rf7
            v = evaluate_position(E7_FEN, answer)
            assert not v.keep, answer
            assert v.square == "e7"
            assert v.gain_cp >= 300


class TestInputsThatAreNotLessons:
    def test_an_illegal_answer_is_rejected(self):
        v = evaluate_position(E7_FEN, "a1a8")
        assert not v.keep and "legal" in v.reason

    def test_unreadable_input_is_rejected_not_raised(self):
        assert not evaluate_position("not a fen", "e2e4").keep
        assert not evaluate_position(E7_FEN, "zzzz").keep

    def test_the_floor_is_a_pawn(self):
        assert MATERIAL_FLOOR_CP == 100
