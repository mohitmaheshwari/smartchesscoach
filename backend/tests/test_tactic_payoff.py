"""The payoff must be a floor, not a hope.

The prover this replaces walked material along the engine's stored line, which
is absent on 69.1% of moves, so fork/pin/skewer have never had an opportunity
denominator. These tests pin the three things that make an exhaustive ply 2 a
proof instead of a guess: it examines every reply, it believes the opponent
will pick the best one, and it refuses a move that gets mated.
"""
from __future__ import annotations

import sys
from pathlib import Path

import chess
import pytest

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from services import tactic_payoff as tp  # noqa: E402


def test_a_free_rook_is_worth_a_rook():
    # Undefended black rook on a7; white rook takes it and nothing answers.
    board = chess.Board("4k3/r7/8/8/8/8/8/R3K3 w - - 0 1")
    gain = tp.forced_material_gain(board, chess.Move.from_uci("a1a7"))
    assert gain == pytest.approx(500)


def test_a_defended_rook_is_worth_nothing():
    # Black king on b8 guards a7. Rxa7 Kxa7 is an even trade, so the floor is
    # zero -- and crucially NOT +500, which is what counting only my capture
    # would have said.
    board = chess.Board("1k6/r7/8/8/8/8/8/R3K3 w - - 0 1")
    gain = tp.forced_material_gain(board, chess.Move.from_uci("a1a7"))
    assert gain <= 0


def test_every_reply_is_examined_so_the_rook_really_does_fall():
    # THE WHOLE MECHANISM: ply 2 is exhaustive, so there is no defence left
    # unexamined. Nd3-e5 forks the king on g6 and the rook on c4. A check must
    # be ANSWERED, so all seven of Black's replies are king moves and none of
    # them can also save the rook.
    #
    # The premise is asserted here rather than trusted, because the first two
    # positions written for this file were illegal and the prover was right to
    # refuse them.
    board = chess.Board("8/8/6k1/8/2r5/3N4/8/4K3 w - - 0 1")
    fork = chess.Move.from_uci("d3e5")
    assert board.is_valid() and not board.is_check()
    after = board.copy(stack=False)
    after.push(fork)
    assert after.is_check()
    replies = list(after.legal_moves)
    assert len(replies) == 7
    assert all(after.piece_at(m.from_square).piece_type == chess.KING
               for m in replies)
    assert tp.forced_material_gain(board, fork) == 500


def test_a_move_that_gets_mated_is_refuted_whatever_it_wins():
    # Qxb7 takes a genuinely undefended rook, and Black answers with mate in
    # one. A material-only prover would have called this a +500 tactic.
    board = chess.Board("1Q6/1r6/4k3/8/8/4q3/6PP/7K w - - 0 1")
    grab = chess.Move.from_uci("b8b7")
    assert board.is_valid() and not board.is_check()
    assert not board.attackers(chess.BLACK, chess.B7)   # really is free
    assert board.piece_at(chess.B7).piece_type == chess.ROOK
    after = board.copy(stack=False)
    after.push(grab)
    mates = [m for m in after.legal_moves
             if (lambda p: (p.push(m), p.is_checkmate())[1])(
                 after.copy(stack=False))]
    assert mates, "the premise of this test is that Black has mate in one"
    assert tp.forced_material_gain(board, grab) == -tp.MATE_GAIN


def test_mate_is_not_scored_as_material():
    # Back-rank mate. A mate is a different kind of fact and must not land in
    # the material range, or a caller comparing against a knight would read it
    # as "wins a thousand pawns".
    board = chess.Board("6k1/5ppp/8/8/8/8/8/R6K w - - 0 1")
    gain = tp.forced_material_gain(board, chess.Move.from_uci("a1a8"))
    assert gain == tp.MATE_GAIN
    assert gain > 100 * tp.MIN_TACTIC_GAIN_CP


def test_an_illegal_move_is_unjudged_not_zero():
    # "Could not judge" and "wins nothing" are different facts.
    board = chess.Board()
    assert tp.forced_material_gain(board, chess.Move.from_uci("e2e5")) is None


def test_the_opening_position_proves_no_tactic():
    # A positive control for the negative: if this returned a payoff, the
    # prover would be inventing one. Every first move must fail.
    board = chess.Board()
    proved = tp.proved_payoff_moves(board, list(board.legal_moves))
    assert proved == {}


def test_giving_up_early_cannot_change_the_verdict():
    # The early exit is a speed trick and must never alter an answer. For
    # every legal move in a real middlegame, the floor with and without the
    # cutoff must agree about whether the bar is cleared.
    board = chess.Board(
        "r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4")
    for move in board.legal_moves:
        exact = tp.forced_material_gain(board, move)
        capped = tp.forced_material_gain(
            board, move, give_up_below=tp.MIN_TACTIC_GAIN_CP)
        assert (exact >= tp.MIN_TACTIC_GAIN_CP) == (
            capped >= tp.MIN_TACTIC_GAIN_CP), move.uci()


def test_declining_to_capture_is_always_available():
    # best_followup_capture may never return a negative number: a bad capture
    # is a choice, not an obligation.
    board = chess.Board(
        "r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4")
    assert tp.best_followup_capture(board, chess.WHITE) >= 0


def test_it_is_not_my_turn_so_i_capture_nothing():
    board = chess.Board()
    assert tp.best_followup_capture(board, chess.BLACK) == 0


def test_material_balance_ignores_the_king():
    board = chess.Board("4k3/8/8/8/8/8/8/4K3 w - - 0 1")
    assert tp.material_balance(board, chess.WHITE) == 0
