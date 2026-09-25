from __future__ import annotations

import os
import sys

import chess

_BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

from services.narrator_claim_verifier import verify_caption


def _facts(**overrides):
    facts = {
        "fen_before": chess.STARTING_FEN,
        "move_san": "a3",
        "best_move_san": "Nf3",
        "is_user_move": True,
        "user_color": "white",
        "pv_after_played": [],
        "pv_after_best": [],
    }
    facts.update(overrides)
    return facts


def test_recommended_move_square_is_checked_on_counterfactual_board():
    violations = verify_caption(
        "Nf3 was better — it puts your knight on f3.",
        _facts(),
    )
    assert violations == []


def test_recommended_move_false_square_still_fails():
    violations = verify_caption(
        "Nf3 was better — it puts your knight on e5.",
        _facts(),
    )
    assert any(v["check"] == "piece_on_square" for v in violations)


def test_unproved_allows_mate_claim_fails_closed():
    violations = verify_caption(
        "a3 allows checkmate.",
        _facts(best_move_san="e4"),
    )
    assert any(v["check"] == "mate" for v in violations)


def test_general_mate_safety_advice_is_not_treated_as_a_position_claim():
    assert verify_caption(
        "Before every move, ask whether your opponent can checkmate you.",
        _facts(best_move_san="e4"),
    ) == []


def test_allows_mate_passes_when_stored_reply_reaches_mate():
    board = chess.Board()
    for san in ("f3", "e5"):
        board.push_san(san)
    facts = _facts(
        fen_before=board.fen(),
        move_san="g4",
        best_move_san="e4",
        pv_after_played=["Qh4#"],
    )
    assert verify_caption("g4 allows checkmate after Qh4#.", facts) == []


def test_played_checkmate_is_verified_on_the_played_board():
    board = chess.Board()
    for san in ("f3", "e5", "g4"):
        board.push_san(san)
    facts = _facts(
        fen_before=board.fen(),
        move_san="Qh4#",
        best_move_san="Qh4#",
        is_user_move=False,
        user_color="white",
    )
    assert verify_caption("Qh4# delivers checkmate.", facts) == []
