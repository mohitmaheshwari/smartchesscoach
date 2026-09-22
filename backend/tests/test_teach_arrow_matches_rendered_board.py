"""The arrows must describe the board the card is showing.

Reported 2026-09-22 on an opponent card: "Opponent's b4 is a major blunder.
Play Qe7 -- it attacks the queen on h7", drawn with an arrow at White's queen
on h7. "Qe7" was legal for both sides, so the picture and the words named
different moves while looking like one.

The review board renders fen_after = board_before + the PLAYED move. Any
picture computed on a different position is describing something the player
cannot see.
"""
from __future__ import annotations

import sys
from pathlib import Path

import chess
import pytest

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from services.caption_pipeline import (  # noqa: E402
    _check_attack_arrows,
    _reply_attack_arrows,
)


def _arrow_pairs(arrows):
    return {(a["from"], a["to"]) for a in arrows}


# --- the helper draws on the board it was handed ---------------------------

# Both sides can play "Qe7" here. White's is Qh7-e7; Black's is Qd8-e7+, which
# checks down the e-file and attacks the white queen still on h7. Only Black's
# exists on the board the card renders.
AMBIGUOUS = "k2q4/7Q/1p6/2N5/8/8/PP4PP/4K3 w - - 0 1"


def test_the_reply_picture_is_built_on_the_board_after_their_move():
    before = chess.Board(AMBIGUOUS)
    played = before.parse_san("b4")
    arrows = _reply_attack_arrows(before, played, "Qe7+")
    pairs = _arrow_pairs(arrows)

    assert pairs, "the reply checks and wins -- this must draw"
    # Every arrow STARTS at the square our queen lands on, and the green one
    # ends on the piece the caption names: "Play Qe7 -- it attacks the queen
    # on h7". That is the picture the card was supposed to draw all along.
    assert ("e7", "h7") in pairs, pairs
    assert ("e7", "e1") in pairs, pairs
    assert all(a["from"] == "e7" for a in arrows), pairs


def test_no_arrow_starts_at_the_opponents_queen():
    """The reported symptom, stated as an assertion.

    The opponent's queen sits on h7. Every arrow on this card belongs to our
    reply, so none of them may start there.
    """
    before = chess.Board(AMBIGUOUS)
    played = before.parse_san("b4")
    assert before.piece_at(chess.H7).symbol() == "Q"
    for a in _reply_attack_arrows(before, played, "Qe7+"):
        assert a["from"] != "h7", f"arrow drawn from the opponent's queen: {a}"


def test_the_opponents_own_best_move_is_not_what_gets_drawn():
    """Feeding the mover's best move to the old path describes another board."""
    before = chess.Board(AMBIGUOUS)
    white_qe7 = before.parse_san("Qe7")
    assert white_qe7.from_square == chess.H7
    reply_pairs = _arrow_pairs(
        _reply_attack_arrows(before, before.parse_san("b4"), "Qe7+")
    )
    old_pairs = _arrow_pairs(_check_attack_arrows(before, white_qe7.uci()))
    assert reply_pairs != old_pairs


def test_a_reply_that_is_illegal_after_their_move_draws_nothing():
    before = chess.Board(AMBIGUOUS)
    played = before.parse_san("b4")
    assert _reply_attack_arrows(before, played, "Nf6") == []
    assert _reply_attack_arrows(before, played, "totally not san") == []
    assert _reply_attack_arrows(before, played, None) == []
    assert _reply_attack_arrows(before, None, "Qe7") == []
    assert _reply_attack_arrows(None, played, "Qe7") == []


def test_the_same_san_means_two_different_moves_by_side():
    """The exact ambiguity behind the report."""
    before = chess.Board(AMBIGUOUS)
    white_qe7 = before.parse_san("Qe7")
    assert white_qe7.from_square == chess.H7

    after = before.copy()
    after.push(before.parse_san("b4"))
    black_qe7 = after.parse_san("Qe7+")
    assert black_qe7.from_square == chess.D8
    assert black_qe7.from_square != white_qe7.from_square


# --- the picture only fires where it is true -------------------------------

def test_the_check_picture_needs_a_check():
    """Right-or-silent: a quiet best move draws nothing."""
    board = chess.Board("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")
    assert _check_attack_arrows(board, "e2e4") == []


def test_the_check_picture_needs_a_winnable_target():
    """A bare check with nothing hanging is not the lesson."""
    board = chess.Board("4k3/8/8/8/8/8/8/4K1R1 w - - 0 1")
    assert _check_attack_arrows(board, "g1g8") == []


def test_an_illegal_uci_is_silent_not_an_exception():
    board = chess.Board("4k3/8/8/8/8/8/8/4K1R1 w - - 0 1")
    assert _check_attack_arrows(board, "a1a8") == []
    assert _check_attack_arrows(board, "nonsense") == []
    assert _check_attack_arrows(board, "") == []
    assert _check_attack_arrows(None, "g1g8") == []


def test_every_arrow_names_real_squares():
    """A malformed square string renders as a stray line on the board."""
    before = chess.Board(AMBIGUOUS)
    played = before.parse_san("b4")
    for a in _reply_attack_arrows(before, played, "Qe7+"):
        assert len(a["from"]) == 2 and len(a["to"]) == 2
        assert a["from"][0] in "abcdefgh" and a["from"][1] in "12345678"
        assert a["to"][0] in "abcdefgh" and a["to"][1] in "12345678"
        assert a.get("teach") is True


# --- the regression, stated as a board fact --------------------------------

# White's best is Qd1-d5+, forking the king on g8 and the loose rook on a8.
# White instead plays b4. The card renders the position after b4, where d5 is
# an empty square.
MISSED_FORK = "r5k1/7p/8/8/8/8/1P4PP/3Q2K1 w - - 0 1"


def test_arrows_for_a_move_that_was_not_played_start_on_an_empty_square():
    """Why feeding best_move_uci to this helper was wrong.

    The picture is computed on board_before + BEST move. The card renders
    board_before + PLAYED move. When those differ, the arrows are anchored to
    a square that holds nothing on the board the player is looking at.
    """
    before = chess.Board(MISSED_FORK)
    best = before.parse_san("Qd5+")
    arrows = _check_attack_arrows(before, best.uci())
    assert _arrow_pairs(arrows) == {("d5", "a8"), ("d5", "g8")}

    rendered = before.copy()
    rendered.push(before.parse_san("b4"))
    for a in arrows:
        assert rendered.piece_at(chess.parse_square(a["from"])) is None, (
            f"arrow starts at {a['from']}, which is empty on the rendered board"
        )


def test_the_same_picture_is_honest_when_the_move_was_actually_played():
    """The 238 of 514 cards that were fine, and stay fine."""
    before = chess.Board(MISSED_FORK)
    best = before.parse_san("Qd5+")
    arrows = _check_attack_arrows(before, best.uci())

    rendered = before.copy()
    rendered.push(best)
    for a in arrows:
        assert rendered.piece_at(chess.parse_square(a["from"])) is not None


# --- the tag has to survive the dedupe -------------------------------------

def test_a_picture_another_rule_already_drew_still_renders():
    """The fork board came out empty.

    The fork rule emits d5->a8 and d5->g8 with no "teach" tag. The check
    picture emits the same two pairs WITH the tag. The dedupe dropped the
    tagged copies as already-present, and the suppression filter then removed
    the untagged originals for having no tag -- so the arrows Mohit asked for
    were deleted by their own duplicate.
    """
    from services.caption_pipeline import (
        CrossMoveState,
        MoveInputs,
        build_move_teaching_decision,
    )

    before = chess.Board(MISSED_FORK)
    best_uci = before.parse_san("Qd5+").uci()
    decision = build_move_teaching_decision(
        MoveInputs(
            fen_before=MISSED_FORK, played_san="Qd5+",
            mover_is_user=True, mover_is_white=True, user_color="white",
            full_move_number=1, move_history_san=[],
            best_move_san="Qd5+", best_move_uci=best_uci,
            eval_before_cp=100, eval_after_cp=120, cp_loss=0, opp_cp_loss=0,
            pv_after_played=[], pv_after_best=[],
        ),
        CrossMoveState(),
    )
    pairs = _arrow_pairs(decision.visual.arrows or [])
    assert pairs == {("d5", "a8"), ("d5", "g8")}, pairs
    assert all(a.get("teach") is True for a in decision.visual.arrows)


def test_a_mistake_card_draws_no_picture_of_the_move_not_played():
    from services.caption_pipeline import (
        CrossMoveState,
        MoveInputs,
        build_move_teaching_decision,
    )

    before = chess.Board(MISSED_FORK)
    decision = build_move_teaching_decision(
        MoveInputs(
            fen_before=MISSED_FORK, played_san="b4",
            mover_is_user=True, mover_is_white=True, user_color="white",
            full_move_number=1, move_history_san=[],
            best_move_san="Qd5+", best_move_uci=before.parse_san("Qd5+").uci(),
            eval_before_cp=100, eval_after_cp=-200, cp_loss=300, opp_cp_loss=0,
            pv_after_played=[], pv_after_best=[],
        ),
        CrossMoveState(),
    )
    rendered = before.copy()
    rendered.push(before.parse_san("b4"))
    for a in decision.visual.arrows or []:
        assert rendered.piece_at(chess.parse_square(a["from"])) is not None, a
