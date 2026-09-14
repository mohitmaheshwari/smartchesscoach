"""Three of Mohit's five 2026-09-14 flags, and the coverage they must not cost.

fb_f6050ba76406  "which piece is undefended here, that sort of scanning"
fb_ca8cc3ec9c5f  "why??"                 -- Qb1+ shipped as a bare verdict
fb_fbdee5ee58be  "it is doing a very big job" -- Qd1 was in check, 3 legal, best
"""
from __future__ import annotations

import chess

from services.caption_facts import (
    _opp_check_answered_by_hitting_it,
    _recapture_cost_target_is_undefended,
)
from services.caption_pipeline import MoveInputs
from services.distilled_caption_service import try_distilled_caption

# after 8...Bd6: Nxb5 leaves the a8 rook unable to take back, nothing guards it
AFTER_BD6 = "r1bqk1nr/2ppbppp/p7/1p2p3/4P2P/1PNP1N2/1PP2PP1/R1BQK2R w KQkq - 1 9"
BEFORE_QB1 = "r4r1k/5pp1/p4b1p/2R2N2/4P1QP/2Pq4/1P3PP1/4K2R b K - 0 23"
QD1_POS = "r4r1k/5pp1/p4b1p/2R2N2/4P1QP/2P5/1P3PP1/1q2K2R w K - 1 24"


def test_b1_names_the_undefended_piece():
    board = chess.Board(AFTER_BD6)
    found = _recapture_cost_target_is_undefended(board, board.parse_san("Nxb5"))
    assert found == {"piece": "rook", "square": "a8"}
    # and the board really does back that up
    assert not board.attackers(chess.BLACK, chess.A8)


def test_b1_silent_when_the_piece_is_defended():
    board = chess.Board(AFTER_BD6)
    assert _recapture_cost_target_is_undefended(board, board.parse_san("h5")) is None


def test_b2_fires_when_every_answer_hits_the_checker():
    board = chess.Board(BEFORE_QB1)
    found = _opp_check_answered_by_hitting_it(board, board.parse_san("Qb1+"))
    assert found is not None
    assert found["piece"] == "queen" and found["square"] == "b1"
    # verify the claim by enumeration rather than trusting the detector
    after = board.copy()
    after.push_san("Qb1+")
    for answer in after.legal_moves:
        probe = after.copy()
        probe.push(answer)
        assert probe.is_attacked_by(chess.WHITE, chess.B1)


def test_b2_silent_on_a_non_check():
    board = chess.Board(BEFORE_QB1)
    assert _opp_check_answered_by_hitting_it(board, board.parse_san("Rad8")) is None


def _inputs(fen, san, best, **over):
    board = chess.Board(fen)
    base = dict(fen_before=fen, played_san=san, mover_is_user=True,
                mover_is_white=(board.turn == chess.WHITE), user_color="white",
                full_move_number=24, move_history_san=[], best_move_san=best,
                cp_loss=0, eval_before_cp=0, eval_after_cp=0,
                allow_fresh_engine_verification=False)
    base.update(over)
    return MoveInputs(**base)


def test_c_a_forced_best_move_is_not_dismissed():
    out = try_distilled_caption(_inputs(QD1_POS, "Qd1", "Qd1"))
    assert out is not None
    caption = out[0]
    assert "does not do much" not in caption
    assert "in check" in caption


def test_c_keeps_the_generic_lesson_for_an_ordinary_move():
    """The hedge is not wrong in general -- gating it must not lose coverage."""
    fen = "r1bqkb1r/pppp1ppp/2n2n2/4p3/4P3/2N2N2/PPPP1PPP/R1BQKB1R w KQkq - 6 4"
    out = try_distilled_caption(_inputs(fen, "h3", "Bb5", cp_loss=30,
                                        eval_before_cp=20, eval_after_cp=-10))
    assert out is not None
    assert out[1] == "distilled:good_space"
