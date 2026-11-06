"""The ledger sentence has to reach the card, not only the facts.

The first version of the reply-gap change (a9b707ae) passed 498 tests and
shipped the ledger sentence on no card at all: the pipeline stage read the
card's tier from `inputs.severity_practical`, a field MoveInputs does not
have, so the tier was always None and the mistake-or-worse gate withheld the
sentence everywhere. A 347-game dry run showed it: 309 old one-ply sentences
removed, 0 ledger sentences in their place. Every test before this file
called the facts function or the sentence function directly.

These go through build_move_teaching_decision, the function the review page
is rendered from, on cards dumped from the corpus (position and both stored
lines as the card holds them).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from services import caption_pipeline
from services.caption_pipeline import CrossMoveState, MoveInputs, build_move_teaching_decision

# 43968fb0 m24 (White, the user): g3 lets axb6 take the b6 pawn for nothing;
# b7 was the move. Stored tier: serious.
G3 = dict(
    fen_before="4r1k1/p4p1p/1Pp3p1/8/8/P6Q/3q1PPP/5RK1 w - - 1 24",
    played_san="g3", mover_is_user=True, mover_is_white=True, user_color="white",
    full_move_number=24, move_history_san=[],
    best_move_san="b7", best_move_uci="b6b7",
    eval_before_cp=188, eval_after_cp=-236, cp_loss=424, opp_cp_loss=0,
    pv_after_played=["axb6", "Qh4", "c5", "Qf6"],
    pv_after_best=["Kg7", "Qb3", "Rb8", "Rb1"],
)

# d1fa053b m24 (Black, the user): Na3 puts the knight where the bishop takes
# it; Rxd5 was the move. Stored tier: mistake.
NA3 = dict(
    fen_before="2kr4/ppp2p1p/8/2BP4/2n3b1/1P3NP1/P3R1PP/R6K b - - 0 24",
    played_san="Na3", mover_is_user=True, mover_is_white=False, user_color="black",
    full_move_number=24, move_history_san=[],
    best_move_san="Rxd5", best_move_uci="d8d5",
    eval_before_cp=603, eval_after_cp=748, cp_loss=163, opp_cp_loss=0,
    pv_after_played=["Bxa3", "Rxd5", "Re8+", "Kd7", "Re7+", "Kc8", "Rxf7", "Bh5", "Rf8+", "Kd7", "Re1", "Bxf3"],
    pv_after_best=["Re8+", "Kd7", "Re7+", "Kd8", "bxc4", "Rxc5", "Rxf7", "Bxf3", "Rxf3", "Rxc4", "Rd1+", "Ke8"],
)

# 3628ebef m32: the exchange on e7 nets the mover two pawns; no material
# sentence belongs on this card, and the old one named Qxe7.
RXE7 = dict(
    fen_before="8/pp2n1q1/5k2/4R3/2PP2p1/1P4P1/n4P2/4R1K1 w - - 2 32",
    played_san="Rxe7", mover_is_user=True, mover_is_white=True, user_color="white",
    full_move_number=32, move_history_san=[],
    best_move_san="Re6+", best_move_uci="e5e6",
    eval_before_cp=0, eval_after_cp=-507, cp_loss=507, opp_cp_loss=0,
    pv_after_played=["Qxe7", "Rxe7", "Kxe7", "Kf1", "a5", "Ke1", "Nc1", "b4", "Nd3+", "Ke2", "Nxb4", "d5"],
    pv_after_best=["Kg5", "Rxe7", "Qxd4", "R1e5+", "Kf6", "R7e6+", "Kf7", "Re7+", "Kg6", "R7e6+", "Kg7", "Re7+"],
)


@pytest.fixture(params=[False, True], ids=["distilled_off", "distilled_on"])
def distilled(request):
    prev = caption_pipeline._DISTILLED_CAPTIONS_ENABLED
    caption_pipeline._DISTILLED_CAPTIONS_ENABLED = request.param
    try:
        yield request.param
    finally:
        caption_pipeline._DISTILLED_CAPTIONS_ENABLED = prev


def _decide(card):
    return build_move_teaching_decision(MoveInputs(**card), CrossMoveState())


def _says_the_loss(caption, *needles):
    return all(n in caption for n in needles)


def test_the_card_for_g3_says_the_pawn_is_simply_taken(distilled):
    text = _decide(G3).text
    caption = text.caption
    # Either the ledger sentence itself, or an earlier clause that already
    # names axb6 and the b6 pawn (the stage stands down on a duplicate).
    assert "axb6" in caption, caption
    assert "b6" in caption
    assert "That lets them take" not in caption


def test_the_card_for_na3_says_the_knight_is_simply_taken(distilled):
    caption = _decide(NA3).text.caption
    assert "Bxa3" in caption, caption
    assert "That lets them take" not in caption


def test_a_ledger_sentence_ships_when_nothing_else_named_the_capture():
    """The stage's own output, with the distilled layer off so no other
    clause can name the capture first on these two cards. At least one of
    them must carry the ledger's words and the REPLY_GAP mark."""
    prev = caption_pipeline._DISTILLED_CAPTIONS_ENABLED
    caption_pipeline._DISTILLED_CAPTIONS_ENABLED = False
    try:
        shipped = []
        for card in (G3, NA3):
            text = _decide(card).text
            if "REPLY_GAP" in (text.rule_name or "") and "simply takes your" in text.caption:
                shipped.append(card["played_san"])
    finally:
        caption_pipeline._DISTILLED_CAPTIONS_ENABLED = prev
    assert shipped, "the ledger sentence reached neither card"


def test_the_rxe7_card_carries_no_one_ply_capture_sentence(distilled):
    caption = _decide(RXE7).text.caption
    assert "take the rook on e7 with Qxe7" not in caption
    assert "That lets them take" not in caption
