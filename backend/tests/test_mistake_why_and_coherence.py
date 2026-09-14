"""The two gaps Mohit found in game c7f3400f (2026-09-13).

1. An opponent mistake said WHAT to play but never WHY the move was a mistake.
   Measured across 29,087 opponent mistake/inaccuracy cards: 91% state a verdict
   and a move and stop there.
2. The card after a recommendation scolded the player for taking it: the coach
   said "Play b4", they played b4 -- the engine's top move -- and the next card
   replied "that can be okay, but first get your other pieces out".
"""
from __future__ import annotations

import dataclasses

import chess

from services.caption_facts import _recommended_move_traps_piece
from services.caption_pipeline import MoveInputs
from services.distilled_caption_service import try_distilled_caption

# After 11...O-O-O, white to move. 12.b4 leaves the a5 knight with three legal
# squares and every one of them loses material.
AFTER_OOO = "2kr3r/pbppqpp1/1p1b1n1p/n2Pp3/P3P3/2PBBN2/1P1N1PPP/R2QK2R w KQ - 3 12"


def test_trapped_piece_why_fires_on_the_real_position():
    board = chess.Board(AFTER_OOO)
    found = _recommended_move_traps_piece(board, board.parse_san("b4"))
    assert found is not None
    assert found["piece"] == "knight"
    assert found["square"] == "a5"
    assert found["on_rim"] is True
    assert "edge" in found["lesson"]


def test_it_stays_silent_when_the_piece_can_run():
    # d3 hits nothing that is stuck; the claim would be false, so say nothing.
    board = chess.Board(
        "r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4"
    )
    assert _recommended_move_traps_piece(board, board.parse_san("d3")) is None


def test_it_stays_silent_when_nothing_is_attacked():
    board = chess.Board(chess.STARTING_FEN)
    assert _recommended_move_traps_piece(board, board.parse_san("e4")) is None


def _inputs(**over):
    base = MoveInputs(
        fen_before=AFTER_OOO, played_san="b4", mover_is_user=True,
        mover_is_white=True, user_color="white", full_move_number=12,
        move_history_san=[], best_move_san="b4", cp_loss=13,
        eval_before_cp=397, eval_after_cp=400,
        allow_fresh_engine_verification=False,
    )
    return dataclasses.replace(base, **over)


def test_a_recommended_move_is_not_scolded():
    followed = try_distilled_caption(_inputs(move_was_our_recommendation=True))
    assert followed is not None
    caption = followed[0]
    assert "but first" not in caption
    assert "push side pawns later" not in caption


def test_the_generic_lesson_still_applies_when_we_did_not_recommend_it():
    """The lesson is not wrong in general -- it must survive for moves we never
    prescribed, or gating it would be a silent coverage loss.

    The move here must also not be the engine's own choice: since 2026-09-14 a
    best move does not get hedged about either (fb_fbdee5ee58be), so pointing
    best_move_san at the played move would prove nothing about recommendations.
    """
    plain = try_distilled_caption(
        _inputs(move_was_our_recommendation=False, best_move_san="Nc4", cp_loss=30)
    )
    assert plain is not None
    assert plain[1] == "distilled:good_space"
