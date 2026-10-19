"""Checkmate ends the move, so the distilled templates must not speak on it.

fb_6fc0dcba448f (Mohit, 2026-10-19): "this is a mate, what's showing here is
wrong". On `8/6p1/8/3R4/P2Pn2p/6kP/4r1P1/2B3K1 b` the opponent played Re1#
and the card read:

    "Your opponent has checked your king with Re1#. You have to answer it
     right now - move the king, block the line, or take the piece that is
     checking. Nothing else is allowed. Look at all three before you pick."

The position has ZERO legal moves. The card asked a mated player to choose
between three options that do not exist.

Two things made it possible. The check branch tests `b.gives_check(mv)`,
which is true of mate as well; and the capture branches ahead of it never
test for check at all, so a mating capture would have said "take back to keep
the material even". The guard therefore sits before any branch.

The fix is to ABSTAIN, not to write a mate sentence. This layer swaps caption
text over whatever the pipeline produced, and the pipeline already had the
right words — `R01_mate`. A second mate sentence would be a second thing to
keep true. See memory/project_distilled_layer_overwrites_rules.

Scale when found: 659 `distilled:opp_check` cards in the corpus, **74 of them
checkmate** — 11% of that rule's output was this.
"""
import sys
from pathlib import Path

import chess
import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

# Real positions pulled from stored cards that rendered distilled:opp_check.
MATES = [
    ("Re1#", "8/6p1/8/3R4/P2Pn2p/6kP/4r1P1/2B3K1 b - - 0 38"),
    ("Rg4#", "8/Q5pk/1p3n1p/1P1q4/5K2/4R3/5P1P/6r1 b - - 3 32"),
]
ORDINARY_CHECKS = [
    ("Qf6+", "8/1p2k3/2p1p2p/p3P1p1/P7/2P2QPK/1q6/8 w - - 0 37"),
    ("Rd8+", "6k1/5pp1/Qp5p/3R4/6nP/P5P1/1Pr2PK1/8 w - - 0 32"),
    ("Nc8+", "8/N5p1/1k6/1p5p/1P2B3/P2N2r1/3K4/8 w - - 1 39"),
    ("Rg3+", "r3r1k1/p4p1p/1np1qB2/8/P1P2P2/5R2/2Q1B1PP/4N2K w - - 3 26"),
]

THE_FALSE_SENTENCE = "answer it right now"


def _distilled(san: str, fen: str):
    from services.distilled_caption_service import _good_caption

    class _Inp:
        fen_before = fen
        played_san = san
        mover_is_user = False
        cp_loss = 0
        best_move_san = san
        move_was_our_recommendation = False

    return _good_caption(_Inp())


@pytest.mark.parametrize("san,fen", MATES)
def test_the_distilled_layer_says_nothing_on_checkmate(san, fen):
    board = chess.Board(fen)
    after = board.copy()
    after.push(board.parse_san(san))
    assert after.is_checkmate(), "fixture must actually be mate"
    assert after.legal_moves.count() == 0

    rule, caption = _distilled(san, fen)
    assert rule is None and caption is None, (
        f"distilled layer spoke on a mate: {caption!r}")


@pytest.mark.parametrize("san,fen", ORDINARY_CHECKS)
def test_an_ordinary_check_still_gets_its_caption(san, fen):
    """The negative control. Abstaining on mate must not silence the 585
    non-mate checks this rule exists for — a check is the one opponent move a
    beginner must read."""
    board = chess.Board(fen)
    after = board.copy()
    after.push(board.parse_san(san))
    assert after.is_check() and not after.is_checkmate()

    rule, caption = _distilled(san, fen)
    assert rule is not None, f"{san} lost its caption"
    assert "check" in rule


@pytest.mark.parametrize("san,fen", MATES)
def test_the_rendered_card_says_checkmate(san, fen):
    """Through the real central layer, with the distilled layer ENABLED —
    memory/feedback_audit_captions_via_real_render_path. Abstaining restores
    R01_mate, which was always there underneath."""
    import os

    os.environ["DISTILLED_CAPTIONS_ENABLED"] = "1"
    from services.caption_pipeline import (
        CrossMoveState, MoveInputs, build_move_teaching_decision,
    )

    board = chess.Board(fen)
    decision = build_move_teaching_decision(
        MoveInputs(
            fen_before=fen, played_san=san, mover_is_user=False,
            mover_is_white=(board.turn == chess.WHITE),
            user_color="black" if board.turn == chess.WHITE else "white",
            full_move_number=board.fullmove_number,
            move_history_san=["d4", "d5", "Nf3", "Nc6", "Bf4", "c5"] * 4,
            prev_move_san="Rd5", best_move_san=san,
            eval_before_cp=-900, eval_after_cp=-900, cp_loss=0,
            pv_after_played=[], pv_after_best=[], user_rating=1381,
        ),
        CrossMoveState(),
    )
    caption = decision.text.caption or ""
    assert THE_FALSE_SENTENCE not in caption, f"the false card is back: {caption!r}"
    assert "heckmate" in caption, f"expected a mate card, got {caption!r}"


def test_a_mating_capture_is_covered_too():
    """The guard sits before the capture branches, not inside the check one.
    A mate delivered BY a capture never reaches `gives_check` at all — it
    would have returned 'take back to keep the material even'."""
    # Back-rank mate delivered by a capture: Rxd8#.
    fen = "3r2k1/5ppp/8/8/8/8/5PPP/3R2K1 w - - 0 1"
    board = chess.Board(fen)
    move = board.parse_san("Rxd8+")
    after = board.copy()
    after.push(move)
    if not after.is_checkmate():
        pytest.skip("fixture is not mate; the guard is still exercised by MATES")
    rule, caption = _distilled("Rxd8+", fen)
    assert rule is None and caption is None
