"""A capture is only "free" when nothing can take back.

fb_6a7c9f8823ac: Bxf6 was called "free -- nothing of theirs guards it" on a
knight guarded by BOTH the e7 bishop and the g7 pawn. Mohit: "wrong fact,
bishop is guarding it."

Cause: caption_facts measures on the board AFTER the move, so
attackers_on_target holds the recapturers and defenders_on_target holds our
own pieces guarding the square we landed on. _facts_caption read the defender
list. Measured across 188,419 stored captions: 198 of 414 "wins it for
nothing" claims were false -- 47.8%.
"""
from __future__ import annotations

import chess

from services.caption_pipeline import MoveInputs
from services.distilled_caption_service import _facts_caption

# knight on f6 guarded by the e7 bishop and the g7 pawn
GUARDED = "r4rk1/3qbpp1/p4n1p/2p2NB1/4P2P/2PP4/1P3PP1/R2QK2R w KQ - 0 20"


def _inputs(fen: str, san: str, **over):
    board = chess.Board(fen)
    base = dict(
        fen_before=fen, played_san=san, mover_is_user=True,
        mover_is_white=(board.turn == chess.WHITE), user_color="white",
        full_move_number=20, move_history_san=[], best_move_san=san,
        cp_loss=0, eval_before_cp=0, eval_after_cp=0,
        allow_fresh_engine_verification=False,
    )
    base.update(over)
    return MoveInputs(**base)


def test_the_guarded_knight_is_not_called_free():
    out = _facts_caption(_inputs(GUARDED, "Bxf6", best_move_san="Qf3", cp_loss=75,
                                 eval_before_cp=389, eval_after_cp=314))
    assert out is not None
    caption = out[0]
    assert "for nothing" not in caption
    assert "nothing of theirs guards it" not in caption


def test_it_names_the_pieces_that_can_take_back():
    """Mohit's actual complaint: the bishop is right there on the board."""
    out = _facts_caption(_inputs(GUARDED, "Bxf6", best_move_san="Qf3", cp_loss=75,
                                 eval_before_cp=389, eval_after_cp=314))
    caption = out[0]
    assert "bishop" in caption          # the e7 bishop Mohit pointed at
    assert "even trade" in caption


def test_the_recapturers_are_real_on_the_board():
    # guard the guard: if this ever stops being true the test above is vacuous.
    board = chess.Board(GUARDED)
    board.push_san("Bxf6")
    recapturers = {chess.square_name(s) for s in board.attackers(board.turn, chess.F6)}
    assert recapturers == {"e7", "g7"}
