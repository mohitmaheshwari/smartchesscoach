"""A loose-piece card is a mistake claim, so the move has to be a mistake.

`build_legal_material_loss_cause` answers one board question: "after this move,
is something of mine worth >=150cp capturable for free?" The review path used
that answer as a verdict on the move, with no other test at all.

Measured on 500 analysed games (641 loose-piece cards rendered), cross-tabbing
what the move actually cost against how decided the game already was (eval
units normalised -- 3.9% of stored analyses hold pawns, not centipawns):

    cp_loss    close   one side better   decided 600-1499   over 1500+   row
      <30          5                14                 23            7    49
      <50          0                 7                  3            4    14
      <75          3                12                 16            2    33
     <100          2                15                 16            0    33
     <150         10                23                 23            5    61
     <300          8                53                 65            0   126
    >=300         47               159                 77           42   325

Two gates come out of that, and nothing else does:

1. cost >= 50cp. Below it the engine considers the move essentially free, so
   the card contradicts the engine it is quoting. Real removals: "Rxf8 ...
   Kxf8" at cp_loss 10 (a trade, narrated as a rook left available) and a
   recapture at cp_loss 0.

   The floor is FLAT, not the rating-band inaccuracy floor. Using the bands
   removed 170 cards including a genuine free knight at cp_loss 142 for a
   988-rated player. The bands are a volume control for subtle engine
   preferences; a piece hanging for free is not subtle, and a 700 needs to
   hear about it more than an 1800 does, not less.

2. skip once |eval| >= 1500. Cards fired at +9880 and -9990 -- the game is
   over and we are discussing a rook. 600 was tempting and wrong: 223 of the
   641 cards (35%) are played while one side is already 600-1499 ahead, and
   losing a rook while down 700 is still a real mistake.

Together they remove 112 of 641 cards (17.5%) and keep 529.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.caption_pipeline import (
    CrossMoveState,
    MoveInputs,
    build_move_teaching_decision,
)

# White to move. Nc4 abandons the knight's defence of d1 and Black wins the
# rook with Qxd1+ (the king has h2, so this is material and not mate). The
# board fact is identical in every case below; only the verdict changes.
LOOSE_ROOK_FEN = "3q3k/5ppp/8/8/8/4N2P/5PP1/3R2K1 w - - 0 1"


def _decide(cp_loss: int, eval_after_cp=0, user_rating: int = 900):
    return build_move_teaching_decision(
        MoveInputs(
            fen_before=LOOSE_ROOK_FEN,
            played_san="Nc4",
            mover_is_user=True,
            mover_is_white=True,
            user_color="white",
            full_move_number=1,
            move_history_san=[],
            best_move_san="Ra1",
            eval_before_cp=(None if eval_after_cp is None
                            else eval_after_cp + cp_loss),
            eval_after_cp=eval_after_cp,
            cp_loss=cp_loss,
            user_rating=user_rating,
            pv_after_played=[],
            pv_after_best=[],
            allow_fresh_engine_verification=False,
        ),
        CrossMoveState(),
    )


def _is_loose_piece_card(decision) -> bool:
    cause = decision.cause
    return cause is not None and getattr(cause, "affected", None) is not None


def test_a_real_mistake_still_gets_the_card():
    decision = _decide(cp_loss=400)
    assert _is_loose_piece_card(decision), (
        "400cp is a blunder at any rating -- the loose-rook card is exactly "
        "the right lesson and must survive both gates"
    )
    assert decision.cause.affected.square == "d1"


def test_an_eight_centipawn_move_is_not_told_it_left_a_piece_available():
    decision = _decide(cp_loss=8)
    assert not _is_loose_piece_card(decision), (
        "the engine lost 8cp on this move; calling it a piece giveaway "
        f"contradicts the engine we are quoting. Got: {decision.cause}"
    )


def test_the_cost_floor_is_flat_and_not_a_rating_band():
    # The 988-rated free-knight card (cp_loss 142) is the case the rating-band
    # version got wrong: its beginner_low floor of 150cp would silence it.
    # Same cost, two very different players, same correct answer -- show it.
    for rating in (700, 988, 1500, 1900):
        assert _is_loose_piece_card(_decide(cp_loss=142, user_rating=rating)), (
            f"a free piece at 142cp must be taught to a {rating}-rated player"
        )


def test_the_boundary_is_the_measured_fifty_centipawns():
    from services.caption_pipeline import LEGAL_LOSS_MIN_COST_CP

    assert LEGAL_LOSS_MIN_COST_CP == 50
    assert not _is_loose_piece_card(_decide(cp_loss=LEGAL_LOSS_MIN_COST_CP - 1))
    assert _is_loose_piece_card(_decide(cp_loss=LEGAL_LOSS_MIN_COST_CP))


def test_no_material_lecture_once_the_game_is_already_over():
    # Live shape: a card about a rook fired at an eval of +9880.
    assert not _is_loose_piece_card(_decide(cp_loss=400, eval_after_cp=9880)), (
        "the game is decided by ten queens; a rook is not the lesson"
    )
    assert not _is_loose_piece_card(_decide(cp_loss=400, eval_after_cp=-9990))


def test_being_clearly_worse_is_not_the_same_as_being_finished():
    # 600 was the tempting threshold and it costs 35% of all cards. Losing a
    # rook while already down 700 is still a real, teachable mistake.
    assert _is_loose_piece_card(_decide(cp_loss=400, eval_after_cp=-700))
    assert _is_loose_piece_card(_decide(cp_loss=400, eval_after_cp=1400))


def test_a_missing_eval_never_costs_the_player_a_card():
    # Also covers the ~3.9% of stored analyses that hold pawns rather than
    # centipawns: those read as tiny numbers, never trip the gate, keep
    # their card. The gate fails open by design.
    assert _is_loose_piece_card(_decide(cp_loss=400, eval_after_cp=None))
