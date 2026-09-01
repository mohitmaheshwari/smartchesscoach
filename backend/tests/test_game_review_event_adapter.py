"""Phase 2 tests for the central-decision review-event projection."""
from __future__ import annotations

import inspect
import json
from pathlib import Path
from datetime import datetime, timezone

import pytest

from services.caption_pipeline import (
    CaptionExplanation,
    MoveTeachingDecision,
    TeachingMeta,
    TextSurface,
    VisualSurface,
)
from services.detector_quality import QualitySurface
from services.game_review_contracts import (
    ChapterRole,
    EventActor,
    EventOutcome,
    GameTeachingPlan,
    PlanChapter,
    ReviewContractViolation,
    event_index,
)
from services.game_review_event_adapter import (
    MoveEventContext,
    adapt_move_teaching_decision,
    maybe_attach_phase2_review_fields,
    maybe_attach_phase5_review_fields,
)


SNAPSHOT = (
    Path(__file__).parents[1]
    / "data"
    / "corpus_snapshots"
    / "personalized_game_review_phase2_legacy_contracts_2026-09-01.json"
)


def _decision(*, verified: bool = True, skip: bool = False) -> MoveTeachingDecision:
    return MoveTeachingDecision(
        text=TextSurface(
            caption="Your bishop could be taken after its defender was pinned.",
            rule_name="R12_BLUNDER",
        ),
        visual=VisualSurface(
            arrows=[{"from": "c6", "to": "g2"}],
            highlight_squares=["g2"],
        ),
        teaching_meta=TeachingMeta(
            has_teaching_content=True,
            principle_cue="Check whether the defender can actually move.",
        ),
        explanation=CaptionExplanation(
            board_explanation="Your bishop could be taken after its defender was pinned.",
            transferable_instruction="Check whether the defender can actually move.",
            confidence="verified" if verified else "limited",
            provenance=["caption_pipeline:R12"],
            final_verified=verified,
        ),
        should_skip=skip,
        skip_reason="suppressed" if skip else "",
    )


def _context(**overrides) -> MoveEventContext:
    values = {
        "game_id": "fixture-game",
        "ply": 23,
        "move_number": 12,
        "san": "Bg5",
        "actor": EventActor.USER,
        "concept_id": "piece_relationships.pinned_defender",
        "outcome": EventOutcome.ALLOWED,
        "quality_id": "gap:piece_safety:simple_hang",
        "provenance": (
            "move_observation:fixture-game:23",
            "caption_pipeline:R12",
        ),
        "opportunity_eligible": True,
        "opportunity_before": "bishop_safe",
        "opportunity_after": "bishop_undefended",
        "requested_surface": QualitySurface.CAPTION,
        "reflection_requested": True,
    }
    values.update(overrides)
    return MoveEventContext(**values)


def test_caption_grade_event_projects_typed_explanation_and_visuals():
    event = adapt_move_teaching_decision(_decision(), _context())
    payload = event.contract_dict()

    assert event.player_authorized is True
    assert event.reflection_eligible is True
    assert payload["teaching"]["caption"].startswith("Your bishop")
    assert payload["teaching"]["principle"].startswith("Check whether")
    assert payload["teaching"]["visual"] == {
        "arrows": [["c6", "g2"]],
        "highlights": ["g2"],
    }


def test_adapted_event_can_enter_the_existing_plan_contract():
    event = adapt_move_teaching_decision(_decision(), _context())
    plan = GameTeachingPlan(
        plan_id="phase2-adapter-plan",
        generated_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
        input_fingerprint="b" * 64,
        opening_text="I watched how this game changed.",
        game_arc="One piece relationship changed the game.",
        chapters=(PlanChapter(event.event_id, ChapterRole.TURNING_POINT),),
        takeaway="Check whether every defender can actually move.",
    )
    plan.validate_against(event_index((event,)))


def test_review_and_play_with_coach_receive_identical_event_identity():
    # The adapter has no caller/surface branch. Passing the same canonical
    # decision packet from Review and PWC must therefore be deterministic.
    review_event = adapt_move_teaching_decision(_decision(), _context())
    pwc_event = adapt_move_teaching_decision(_decision(), _context())
    assert review_event.contract_dict() == pwc_event.contract_dict()
    assert review_event.concept.concept_id == pwc_event.concept.concept_id


def test_shadow_quality_is_retained_for_audit_but_not_exposed():
    event = adapt_move_teaching_decision(
        _decision(),
        _context(
            quality_id="gap:future:unknown",
            provenance=("move_observation:fixture-game:23",),
            requested_surface=QualitySurface.CAPTION,
        ),
    )
    assert event.requested_surface == QualitySurface.DIAGNOSTIC
    assert event.player_authorized is False
    assert event.reflection_eligible is False
    assert not event.teaching.is_empty


@pytest.mark.parametrize("verified,skip", [(False, False), (True, True)])
def test_unverified_or_skipped_decision_becomes_empty_silent_event(verified, skip):
    event = adapt_move_teaching_decision(
        _decision(verified=verified, skip=skip),
        _context(reflection_requested=True),
    )
    assert event.outcome == EventOutcome.SILENT
    assert event.requested_surface == QualitySurface.DIAGNOSTIC
    assert event.teaching.is_empty
    assert event.reflection_eligible is False


def test_gap_identity_requires_upstream_observation_not_adapter_inference():
    with pytest.raises(ReviewContractViolation, match="move_observation"):
        _context(provenance=("caption_pipeline:R12",))


def test_shape_and_principle_identity_must_match_central_decision():
    with pytest.raises(ReviewContractViolation, match="shape quality_id"):
        adapt_move_teaching_decision(
            _decision(),
            _context(
                quality_id="shape:fork_geometry",
                provenance=("caption_pipeline:shape",),
            ),
        )

    with pytest.raises(ReviewContractViolation, match="principle quality_id"):
        adapt_move_teaching_decision(
            _decision(),
            _context(
                quality_id="principle:check_the_defender",
                provenance=("caption_pipeline:principle",),
            ),
        )


def test_flag_off_preserves_captured_game_review_payload_exactly():
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    legacy = snapshot["fixtures"]["game_review_complete"]
    before = json.dumps(legacy, separators=(",", ":"), ensure_ascii=False)

    result = maybe_attach_phase2_review_fields(legacy, env={})

    assert result is legacy
    assert json.dumps(result, separators=(",", ":"), ensure_ascii=False) == before
    assert "teachable_events" not in result


def test_flag_on_exposes_only_authorized_precomputed_fields():
    authorized = adapt_move_teaching_decision(_decision(), _context()).contract_dict()
    shadow = adapt_move_teaching_decision(
        _decision(),
        _context(
            quality_id="gap:future:unknown",
            provenance=("move_observation:fixture-game:23",),
            requested_surface=QualitySurface.CAPTION,
        ),
    ).contract_dict()
    prompt = {"prompt_id": "p", "event_id": authorized["event_id"]}
    legacy = {
        "decryption_data": [
            {"teachable_event": authorized, "reflection_prompt": prompt},
            {"teachable_event": shadow},
        ],
        "status": "complete",
    }

    result = maybe_attach_phase2_review_fields(
        legacy,
        env={"PERSONALIZED_GAME_REVIEW_COACH_ENABLED": "true"},
    )

    assert result is not legacy
    assert result["teachable_events"] == [authorized]
    assert result["reflection_prompts"] == [prompt]
    assert all(
        "teachable_event" not in move and "reflection_prompt" not in move
        for move in result["decryption_data"]
    )
    assert "teachable_events" not in legacy


def test_flag_on_rechecks_stored_evidence_instead_of_trusting_display_boolean():
    tampered = adapt_move_teaching_decision(_decision(), _context()).contract_dict()
    tampered["evidence"]["final_verified"] = False
    legacy = {"decryption_data": [{"teachable_event": tampered}]}

    result = maybe_attach_phase2_review_fields(
        legacy,
        env={"PERSONALIZED_GAME_REVIEW_COACH_ENABLED": "true"},
    )

    assert result["teachable_events"] == []


def _stored_plan_envelope(event):
    plan = GameTeachingPlan(
        plan_id="phase5-plan",
        generated_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
        input_fingerprint="c" * 64,
        opening_text="I watched how this game unfolded.",
        game_arc="I found one moment worth studying in this game.",
        chapters=(PlanChapter(event.event_id, ChapterRole.TURNING_POINT),),
        takeaway="Check whether every defender can actually move.",
    ).contract_dict()
    return {
        "rollout_mode": "shadow",
        "selected_event_ids": [event.event_id],
        "plan": plan,
    }


def test_phase5_flag_off_preserves_identity_even_with_stored_plan():
    legacy = {"decryption_data": [{"move_san": "Bg5"}], "status": "complete"}
    event = adapt_move_teaching_decision(_decision(), _context()).contract_dict()
    result = maybe_attach_phase5_review_fields(
        legacy,
        stored_moves=({"teachable_event": event},),
        stored_plan=_stored_plan_envelope(
            adapt_move_teaching_decision(_decision(), _context())
        ),
        env={},
    )
    assert result is legacy
    assert set(result) == {"decryption_data", "status"}


def test_phase5_exposes_only_plan_whose_chapters_remain_authorized():
    typed_event = adapt_move_teaching_decision(_decision(), _context())
    event = typed_event.contract_dict()
    prompt = {"prompt_id": "prompt", "event_id": event["event_id"]}
    legacy = {"decryption_data": [{"move_san": "Bg5"}], "status": "complete"}
    result = maybe_attach_phase5_review_fields(
        legacy,
        stored_moves=(
            {"teachable_event": event, "reflection_prompt": prompt},
        ),
        stored_plan=_stored_plan_envelope(typed_event),
        env={"PERSONALIZED_GAME_REVIEW_COACH_ENABLED": "true"},
    )
    assert result["game_teaching_plan"]["plan_id"] == "phase5-plan"
    assert result["teachable_events"] == [event]
    assert result["reflection_prompts"] == [prompt]
    assert result["decryption_data"] == [{"move_san": "Bg5"}]


def test_phase5_rejects_plan_with_unknown_or_tampered_chapter():
    typed_event = adapt_move_teaching_decision(_decision(), _context())
    event = typed_event.contract_dict()
    envelope = _stored_plan_envelope(typed_event)
    envelope["plan"]["chapters"][0]["event_id"] = "unknown"
    result = maybe_attach_phase5_review_fields(
        {"decryption_data": []},
        stored_moves=({"teachable_event": event},),
        stored_plan=envelope,
        env={"PERSONALIZED_GAME_REVIEW_COACH_ENABLED": "true"},
    )
    assert "game_teaching_plan" not in result


def test_phase5_rejects_protocol_relative_next_action():
    typed_event = adapt_move_teaching_decision(_decision(), _context())
    event = typed_event.contract_dict()
    envelope = _stored_plan_envelope(typed_event)
    envelope["plan"]["next_action"] = {
        "source_event_id": event["event_id"],
        "href": "//outside.example/training",
        "action_kind": "practise",
        "content_kind": "concept",
        "content_id": "piece_safety",
        "canonical_source": "personal_curriculum",
    }
    result = maybe_attach_phase5_review_fields(
        {"decryption_data": []},
        stored_moves=({"teachable_event": event},),
        stored_plan=envelope,
        env={"PERSONALIZED_GAME_REVIEW_COACH_ENABLED": "true"},
    )
    assert "game_teaching_plan" not in result


def test_adapter_has_no_board_engine_database_network_or_llm_dependency():
    import services.game_review_event_adapter as module

    source = inspect.getsource(module).lower()
    forbidden = (
        "import chess",
        "stockfish",
        "pymongo",
        "motor",
        "requests",
        "httpx",
        "openai",
        "anthropic",
    )
    assert all(token not in source for token in forbidden)
