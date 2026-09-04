"""Stage 4 causal/personal caption invariants."""
from __future__ import annotations

import os
import sys

_BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

import services.caption_pipeline as pipeline  # noqa: E402
import services.coach_conductor as conductor  # noqa: E402
from services.caption_pipeline import CrossMoveState, MoveInputs  # noqa: E402


START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"


def _inputs(*, shadow: bool, with_context: bool = True) -> MoveInputs:
    return MoveInputs(
        fen_before=START_FEN,
        played_san="f3",
        mover_is_user=True,
        mover_is_white=True,
        user_color="white",
        full_move_number=1,
        move_history_san=[],
        best_move_san="e4",
        eval_before_cp=20,
        eval_after_cp=-120,
        cp_loss=140,
        pv_after_played=["e5"],
        pv_after_best=["e5"],
        player_concept_threads=(
            {"weaknesses": {"KING_PAWN": {"name": "king pawn safety"}}}
            if with_context else None
        ),
        player_context_shadow_only=shadow,
    )


def _thread(text: str):
    return {
        "kind": "concept_miss",
        "motif": "KING_PAWN",
        "side": "concept",
        "text": text,
    }


def test_shadow_records_connection_without_changing_caption(monkeypatch):
    monkeypatch.setattr(pipeline, "_CAUSAL_PERSONAL_CAPTIONS_ENABLED", False)
    monkeypatch.setattr(
        conductor,
        "compute_concept_thread",
        lambda **kwargs: _thread("You've been rushing this king-pawn decision."),
    )

    decision = pipeline.build_move_teaching_decision(
        _inputs(shadow=True), CrossMoveState()
    )

    assert decision.explanation.player_connection
    assert decision.explanation.personal_evidence == {
        "eligible": True,
        "source": "player_concept_threads",
        "kind": "concept_miss",
        "key": "KING_PAWN",
    }
    assert decision.explanation.rendered_personalization is False
    assert decision.text.caption == decision.explanation.board_explanation


def test_enabled_personalization_frames_and_never_replaces_board_reason(monkeypatch):
    monkeypatch.setattr(pipeline, "_CAUSAL_PERSONAL_CAPTIONS_ENABLED", True)
    connection = "You've been rushing this king-pawn decision."
    monkeypatch.setattr(
        conductor,
        "compute_concept_thread",
        lambda **kwargs: _thread(connection),
    )

    decision = pipeline.build_move_teaching_decision(
        _inputs(shadow=True), CrossMoveState()
    )

    assert decision.explanation.board_explanation
    assert decision.text.caption.startswith(connection)
    assert decision.explanation.board_explanation in decision.text.caption
    assert decision.explanation.rendered_personalization is True
    assert decision.explanation.final_verified is True
    assert decision.explanation.rollout_mode == "visible"
    assert decision.explanation.transferable_instruction
    assert (
        decision.teaching_meta.principle_cue
        == decision.explanation.transferable_instruction
    )


def test_false_personal_board_claim_is_removed_by_final_verifier(monkeypatch):
    monkeypatch.setattr(pipeline, "_CAUSAL_PERSONAL_CAPTIONS_ENABLED", True)
    monkeypatch.setattr(
        conductor,
        "compute_concept_thread",
        lambda **kwargs: _thread("Your queen on a1 is loose again."),
    )

    decision = pipeline.build_move_teaching_decision(
        _inputs(shadow=True), CrossMoveState()
    )

    assert "queen on a1" not in decision.text.caption
    assert decision.text.caption == decision.explanation.board_explanation
    assert decision.explanation.rendered_personalization is False
    assert decision.explanation.final_verified is True


def test_no_player_evidence_means_no_personal_claim(monkeypatch):
    monkeypatch.setattr(pipeline, "_CAUSAL_PERSONAL_CAPTIONS_ENABLED", True)

    decision = pipeline.build_move_teaching_decision(
        _inputs(shadow=True, with_context=False), CrossMoveState()
    )

    assert decision.explanation.player_connection == ""
    assert decision.explanation.personal_evidence is None
    assert decision.explanation.rendered_personalization is False
