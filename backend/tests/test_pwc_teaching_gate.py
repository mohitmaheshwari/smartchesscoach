from __future__ import annotations

import os
import sys

import chess

_BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

from services.caption_pipeline import (
    CrossMoveState,
    MoveInputs,
    _ensure_serious_teaching_contract,
    _rewrite_phase2_forced_attack_response,
    build_move_teaching_decision,
)
from services.caption_facts import _recommended_move_why
from services.live_v5_teaching import coach_move_narration_for_live_move
from services.shared_coaching_v5 import (
    _pwc_teaching_worthiness,
)


def _meta(**overrides):
    value = {
        "caption_verification": {"verdict": "pass"},
        "caption_tier": "HIGH",
        "has_teaching_content": True,
        "teaching_contract": {
            "complete": True,
        },
    }
    value.update(overrides)
    return value


def test_unverified_caption_never_gets_a_live_card():
    worthy, reason = _pwc_teaching_worthiness(
        raw_severity="mistake",
        practical_severity="mistake",
        central_meta=_meta(caption_verification={"verdict": "not_run"}),
        conductor_thread=None,
    )
    assert worthy is False
    assert reason == "unverified_caption"


def test_softened_already_decided_error_is_silent():
    worthy, reason = _pwc_teaching_worthiness(
        raw_severity="mistake",
        practical_severity="good",
        central_meta=_meta(),
        conductor_thread=None,
    )
    assert worthy is False
    assert reason == "already_decided"


def test_serious_caption_requires_complete_teaching_contract():
    worthy, reason = _pwc_teaching_worthiness(
        raw_severity="blunder",
        practical_severity="blunder",
        central_meta=_meta(teaching_contract={"complete": False}),
        conductor_thread=None,
    )
    assert worthy is False
    assert reason == "incomplete_serious_lesson"


def test_complete_serious_lesson_is_shown():
    worthy, reason = _pwc_teaching_worthiness(
        raw_severity="mistake",
        practical_severity="mistake",
        central_meta=_meta(),
        conductor_thread=None,
    )
    assert worthy is True
    assert reason == "complete_serious_lesson"


def test_routine_good_caption_is_silent_but_high_value_good_caption_is_shown():
    quiet, quiet_reason = _pwc_teaching_worthiness(
        raw_severity="good",
        practical_severity="good",
        central_meta=_meta(caption_tier="MID", has_teaching_content=False),
        conductor_thread=None,
    )
    useful, useful_reason = _pwc_teaching_worthiness(
        raw_severity="good",
        practical_severity="good",
        central_meta=_meta(),
        conductor_thread=None,
    )
    assert (quiet, quiet_reason) == (False, "routine_or_low_value")
    assert (useful, useful_reason) == (True, "high_value_teaching")


def test_central_pipeline_completes_a_plain_serious_missed_opportunity():
    decision = build_move_teaching_decision(
        MoveInputs(
            fen_before=chess.STARTING_FEN,
            played_san="a3",
            mover_is_user=True,
            mover_is_white=True,
            user_color="white",
            full_move_number=1,
            move_history_san=[],
            best_move_san="Nf3",
            eval_before_cp=20,
            eval_after_cp=-100,
            cp_loss=120,
            pv_after_played=[],
            pv_after_best=[],
        ),
        CrossMoveState(),
    )
    contract = decision.debug_facts["teaching_contract"]
    assert contract["complete"] is True
    assert contract == {
        "required": True,
        "complete": True,
        "what": True,
        "why_bad": True,
        "better_move": True,
        "why_better": True,
        "verified": True,
    }
    assert "misses the chance to" in decision.text.caption
    assert "Nf3 was better" in decision.text.caption


def test_serious_contract_recovers_an_empty_upstream_caption_from_verified_facts():
    inputs = MoveInputs(
        fen_before=chess.STARTING_FEN,
        played_san="a3",
        mover_is_user=True,
        mover_is_white=True,
        user_color="white",
        full_move_number=1,
        move_history_san=[],
        best_move_san="Nf3",
        eval_before_cp=20,
        eval_after_cp=-100,
        cp_loss=120,
        pv_after_played=[],
        pv_after_best=[],
    )
    payload = {"caption": "", "rule_name": "R_SILENT"}
    _ensure_serious_teaching_contract(
        caption_payload=payload,
        caption_facts={"best_move_why": "develops a piece"},
        inputs=inputs,
        severity_practical="mistake",
    )
    assert payload["caption"] == (
        "a3 needs attention because it misses the chance to develop a piece. "
        "Nf3 was better — it develops a piece."
    )


def test_serious_contract_reuses_verified_better_clause_as_the_missed_chance():
    inputs = MoveInputs(
        fen_before=chess.STARTING_FEN,
        played_san="a3",
        mover_is_user=True,
        mover_is_white=True,
        user_color="white",
        full_move_number=1,
        move_history_san=[],
        best_move_san="Nf3",
        eval_before_cp=20,
        eval_after_cp=-100,
        cp_loss=120,
        pv_after_played=[],
        pv_after_best=[],
    )
    payload = {
        "caption": "a3 is a mistake. Nf3 was better — it develops a piece.",
        "rule_name": "R_EXISTING_BETTER",
    }
    _ensure_serious_teaching_contract(
        caption_payload=payload,
        caption_facts={},
        inputs=inputs,
        severity_practical="mistake",
    )
    assert payload["caption"] == (
        "a3 is a mistake — it misses the chance to develop a piece. "
        "Nf3 was better — it develops a piece."
    )


def test_attack_claim_becomes_forced_move_when_the_stored_reply_moves_target():
    fen = "4k3/8/8/6n1/8/8/8/2B1K3 w - - 0 1"
    rewritten = _rewrite_phase2_forced_attack_response(
        caption_text=(
            "Bf4 was better — it attacks the knight on g5."
        ),
        fen_before=fen,
        best_move_san="Bf4",
        pv_after_best=["Bf4", "Ne6"],
    )
    assert rewritten == (
        "Bf4 was better — it forces the knight on g5 to move."
    )


def test_attack_claim_is_not_rewritten_when_reply_comes_from_another_square():
    fen = "4k3/8/8/6n1/8/8/8/2B1K3 w - - 0 1"
    rewritten = _rewrite_phase2_forced_attack_response(
        caption_text=(
            "Bf4 was better — it attacks the knight on g5."
        ),
        fen_before=fen,
        best_move_san="Bf4",
        pv_after_best=["Bf4", "Kf7"],
    )
    assert rewritten is None


def test_recommended_capture_with_check_explains_the_forcing_detail():
    board = chess.Board("8/b3k3/8/8/8/8/8/R3K3 w - - 0 1")
    reason = _recommended_move_why(board, board.parse_san("Rxa7+"))
    assert reason is not None
    assert reason.endswith("with check")


def test_embedded_refutation_is_moved_before_the_verified_better_reason():
    inputs = MoveInputs(
        fen_before=chess.STARTING_FEN,
        played_san="a3",
        mover_is_user=True,
        mover_is_white=True,
        user_color="white",
        full_move_number=1,
        move_history_san=[],
        best_move_san="Nf3",
        eval_before_cp=20,
        eval_after_cp=-100,
        cp_loss=120,
        pv_after_played=[],
        pv_after_best=[],
    )
    payload = {
        "caption": (
            "You played a3; Nf3 was stronger — "
            "a3 runs into Qxd3, taking your pawn."
        ),
        "rule_name": "R_EMBEDDED_REFUTATION",
    }
    _ensure_serious_teaching_contract(
        caption_payload=payload,
        caption_facts={"best_move_why": "develops a piece"},
        inputs=inputs,
        severity_practical="mistake",
    )
    assert payload["caption"] == (
        "a3 needs attention because it allows Qxd3, which takes your pawn. "
        "You played a3; Nf3 was better — it develops a piece."
    )


def test_live_move_marked_as_best_is_suppressed_unless_it_teaches():
    worthy, reason = _pwc_teaching_worthiness(
        raw_severity="mistake",
        practical_severity="mistake",
        central_meta=_meta(caption_tier="MID", has_teaching_content=False),
        conductor_thread=None,
        played_is_best=True,
    )
    assert worthy is False
    assert reason == "not_a_mistake"


def test_routine_coach_opening_move_does_not_create_a_card():
    payload = coach_move_narration_for_live_move(
        fen_before=chess.STARTING_FEN,
        played_san="e4",
        user_color="black",
        move_history_san=[],
        full_move_number=1,
    )
    assert payload is not None
    assert payload["teaching_worthy"] is False


def test_coach_checkmate_is_teaching_worthy():
    board = chess.Board()
    for san in ("f3", "e5", "g4"):
        board.push_san(san)
    payload = coach_move_narration_for_live_move(
        fen_before=board.fen(),
        played_san="Qh4#",
        user_color="white",
        move_history_san=["f3", "e5", "g4"],
        full_move_number=2,
    )
    assert payload is not None
    assert payload["teaching_worthy"] is True
