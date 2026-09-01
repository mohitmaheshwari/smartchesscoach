"""Phase 1 contracts for the default-off Personalized Game Review Coach."""
from __future__ import annotations

from dataclasses import fields
from datetime import datetime, timezone
import inspect
import json

import pytest

from services.detector_quality import QualitySurface
from services.game_review_contracts import (
    CONTRACT_SCHEMA_VERSION,
    ChapterRole,
    ConceptReference,
    EventActor,
    EventEvidence,
    EventOutcome,
    GameTeachingPlan,
    MoveReference,
    OpportunityEvidence,
    PlanChapter,
    PlayerReflection,
    ReflectionOption,
    ReflectionPrompt,
    ReviewContractViolation,
    ReviewNextAction,
    ReviewPresentationMode,
    TeachableEvent,
    TeachingReference,
    VisualReference,
    event_index,
    maybe_attach_game_teaching_plan,
    personalized_game_review_access,
    personalized_game_review_enabled,
    resolve_review_presentation_mode,
)


NOW = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)
SIMPLE_HANG = "gap:piece_safety:simple_hang"
UNKNOWN_SHAPE = "shape:future_geometry"
DISABLED_ENDGAME = "concept:endgame_rule_of_square"
FINGERPRINT = "a" * 64


def _event(
    *,
    event_id: str = "g:23:piece-safety:allowed",
    quality_id: str = SIMPLE_HANG,
    surface: QualitySurface = QualitySurface.CAPTION,
    outcome: EventOutcome = EventOutcome.ALLOWED,
    final_verified: bool = True,
    reflection_eligible: bool = False,
    teaching: TeachingReference | None = None,
) -> TeachableEvent:
    return TeachableEvent(
        event_id=event_id,
        move=MoveReference(
            ply=23,
            number=12,
            san="Bg5",
            actor=EventActor.USER,
        ),
        concept=ConceptReference(concept_id="piece_relationships.pinned_defender"),
        outcome=outcome,
        opportunity=OpportunityEvidence(
            eligible=True,
            before="safe",
            after="bishop_undefended",
        ),
        evidence=EventEvidence(
            quality_id=quality_id,
            source_version="move_teaching_decision.v138",
            provenance=("caption_pipeline:R12", "detector_quality"),
            final_verified=final_verified,
        ),
        teaching=(
            teaching
            if teaching is not None
            else TeachingReference(
                caption="Your bishop looked protected, but its defender could not move.",
                principle="Check whether the defender is free to recapture.",
                visual=VisualReference(
                    arrows=(("f3", "g5"),),
                    highlights=("g5",),
                ),
            )
        ),
        requested_surface=surface,
        reflection_eligible=reflection_eligible,
    )


def _next_action(event_id: str) -> ReviewNextAction:
    return ReviewNextAction(
        source_event_id=event_id,
        href="/training/prescribed?weakness=piece_safety",
        action_kind="practise",
        content_kind="concept",
        content_id="piece_safety",
        canonical_source="personal_curriculum",
    )


def _plan(
    event_id: str,
    *,
    role: ChapterRole = ChapterRole.TURNING_POINT,
    with_next_action: bool = False,
) -> GameTeachingPlan:
    return GameTeachingPlan(
        plan_id="review-plan-g",
        generated_at=NOW,
        input_fingerprint=FINGERPRINT,
        opening_text="I watched how this game unfolded.",
        game_arc="Your attack worked until the defender could no longer move.",
        chapters=(PlanChapter(event_id=event_id, role=role),),
        takeaway="Verify that a defender can really recapture.",
        next_action=_next_action(event_id) if with_next_action else None,
    )


def _prompt() -> ReflectionPrompt:
    return ReflectionPrompt(
        prompt_id="prompt:g:23",
        event_id="g:23:piece-safety:allowed",
        question="What did you believe about your bishop?",
        options=(
            ReflectionOption("still_protected", "It was still protected."),
            ReflectionOption("attack_first", "They had to answer my attack."),
            ReflectionOption("not_sure", "I wasn't sure."),
            ReflectionOption("none_of_these", "None of these."),
        ),
        source_version="quick_tag_registry.v1",
    )


def test_feature_flag_is_default_off_and_read_at_call_time():
    assert personalized_game_review_enabled({}) is False
    assert personalized_game_review_enabled(
        {"PERSONALIZED_GAME_REVIEW_COACH_ENABLED": "false"}
    ) is False
    assert personalized_game_review_enabled(
        {"PERSONALIZED_GAME_REVIEW_COACH_ENABLED": "true"}
    ) is True


def test_validation_rollout_requires_master_and_existing_user_flag():
    user_doc = {
        "feature_flags": {
            "personalized_game_review_coach": {
                "enabled": True,
                "validation_compare": True,
            }
        }
    }
    assert personalized_game_review_access(user_doc, {}).enabled is False

    access = personalized_game_review_access(
        user_doc,
        {"PERSONALIZED_GAME_REVIEW_COACH_ENABLED": "true"},
    )
    assert access.enabled is True
    assert access.comparison_allowed is True
    assert access.rollout_mode == "validation"

    unlisted = personalized_game_review_access(
        {},
        {"PERSONALIZED_GAME_REVIEW_COACH_ENABLED": "true"},
    )
    assert unlisted.enabled is False
    assert unlisted.comparison_allowed is False


def test_rollout_all_enables_review_but_not_internal_comparison():
    access = personalized_game_review_access(
        {},
        {
            "PERSONALIZED_GAME_REVIEW_COACH_ENABLED": "true",
            "PERSONALIZED_GAME_REVIEW_COACH_ROLLOUT": "all",
        },
    )
    assert access.enabled is True
    assert access.comparison_allowed is False
    assert resolve_review_presentation_mode(access) == (
        ReviewPresentationMode.PERSONALIZED
    )
    with pytest.raises(ReviewContractViolation, match="not enabled"):
        resolve_review_presentation_mode(access, "legacy")


def test_invalid_rollout_and_unknown_presentation_fail_closed():
    access = personalized_game_review_access(
        {"feature_flags": {"personalized_game_review_coach": {"enabled": True}}},
        {
            "PERSONALIZED_GAME_REVIEW_COACH_ENABLED": "true",
            "PERSONALIZED_GAME_REVIEW_COACH_ROLLOUT": "surprise",
        },
    )
    assert access.enabled is False
    assert resolve_review_presentation_mode(access) == ReviewPresentationMode.LEGACY

    validator = personalized_game_review_access(
        {
            "feature_flags": {
                "personalized_game_review_coach": {
                    "enabled": True,
                    "validation_compare": True,
                }
            }
        },
        {"PERSONALIZED_GAME_REVIEW_COACH_ENABLED": "true"},
    )
    with pytest.raises(ReviewContractViolation, match="unknown"):
        resolve_review_presentation_mode(validator, "secret")


def test_flag_off_returns_original_legacy_payload_byte_for_byte():
    legacy = {
        "game_id": "g",
        "moves": [{"move_san": "e4", "caption": "You claimed the centre."}],
    }
    before = json.dumps(legacy, separators=(",", ":"), ensure_ascii=False)
    event = _event()

    result = maybe_attach_game_teaching_plan(
        legacy,
        _plan(event.event_id),
        events=event_index((event,)),
        env={},
    )

    after = json.dumps(result, separators=(",", ":"), ensure_ascii=False)
    assert result is legacy
    assert after == before
    assert "game_teaching_plan" not in result


def test_flag_on_adds_contract_without_mutating_legacy_payload():
    legacy = {"game_id": "g", "moves": []}
    event = _event()
    result = maybe_attach_game_teaching_plan(
        legacy,
        _plan(event.event_id),
        events=event_index((event,)),
        env={"PERSONALIZED_GAME_REVIEW_COACH_ENABLED": "true"},
    )
    assert result is not legacy
    assert legacy == {"game_id": "g", "moves": []}
    assert result["game_teaching_plan"]["schema_version"] == CONTRACT_SCHEMA_VERSION
    assert result["game_teaching_plan"]["rollout_mode"] == "shadow"


def test_event_serialization_is_deterministic_and_keeps_provenance():
    event = _event(reflection_eligible=True)
    first = event.contract_dict()
    second = event.contract_dict()
    assert first == second
    assert first["evidence"]["provenance"] == [
        "caption_pipeline:R12",
        "detector_quality",
    ]
    assert first["evidence"]["grade"] == "caption"
    assert first["display"] == {
        "requested_surface": "caption",
        "authorized": True,
        "reflection_eligible": True,
    }


def test_unknown_detector_can_exist_only_as_non_player_shadow():
    event = _event(
        quality_id=UNKNOWN_SHAPE,
        surface=QualitySurface.DIAGNOSTIC,
    )
    assert event.player_authorized is False
    assert event.contract_dict()["evidence"]["grade"] == "shadow"
    with pytest.raises(ReviewContractViolation, match="cannot be serialized"):
        event.player_dict()


def test_diagnostic_only_event_cannot_enter_a_plan():
    diagnostic = _event(surface=QualitySurface.DIAGNOSTIC)
    plan = _plan(diagnostic.event_id)
    with pytest.raises(ReviewContractViolation, match="diagnostic-only"):
        plan.validate_against(event_index((diagnostic,)))


def test_unknown_detector_cannot_request_caption_even_if_rollout_gate_is_off(
    monkeypatch,
):
    monkeypatch.delenv("DETECTOR_QUALITY_GATE_ENFORCED", raising=False)
    with pytest.raises(ReviewContractViolation, match="not authorized for caption"):
        _event(quality_id=UNKNOWN_SHAPE, surface=QualitySurface.CAPTION)


def test_disabled_detector_cannot_enter_any_player_surface():
    with pytest.raises(ReviewContractViolation, match="not authorized for caption"):
        _event(quality_id=DISABLED_ENDGAME, surface=QualitySurface.CAPTION)


def test_unverified_evidence_cannot_enter_a_player_surface():
    with pytest.raises(ReviewContractViolation, match="not authorized for caption"):
        _event(final_verified=False)


def test_silent_event_is_empty_diagnostic_only():
    event = _event(
        quality_id=UNKNOWN_SHAPE,
        surface=QualitySurface.DIAGNOSTIC,
        outcome=EventOutcome.SILENT,
        teaching=TeachingReference(),
    )
    assert event.player_authorized is False
    assert event.contract_dict()["display"]["authorized"] is False


def test_silent_event_cannot_carry_teaching_or_reflection():
    with pytest.raises(ReviewContractViolation, match="cannot teach"):
        _event(
            surface=QualitySurface.DIAGNOSTIC,
            outcome=EventOutcome.SILENT,
        )


def test_content_reference_requires_its_canonical_source():
    with pytest.raises(ReviewContractViolation, match="supplied together"):
        ConceptReference(
            concept_id="endgame.opposition",
            content_ref="king_and_pawn/opposition",
        )


def test_reflection_prompt_requires_honest_escape_options():
    with pytest.raises(ReviewContractViolation, match="none_of_these"):
        ReflectionPrompt(
            prompt_id="p",
            event_id="e",
            question="What were you checking?",
            options=(
                ReflectionOption("candidate", "My attacking idea."),
                ReflectionOption("not_sure", "I wasn't sure."),
            ),
            source_version="quick_tag_registry.v1",
        )


def test_reflection_prompt_rejects_duplicate_stable_ids():
    with pytest.raises(ReviewContractViolation, match="must be unique"):
        ReflectionPrompt(
            prompt_id="p",
            event_id="e",
            question="What were you checking?",
            options=(
                ReflectionOption("not_sure", "I wasn't sure."),
                ReflectionOption("not_sure", "Still not sure."),
                ReflectionOption("none_of_these", "None of these."),
            ),
            source_version="quick_tag_registry.v1",
        )


def test_reflection_contract_is_options_only_and_has_no_free_text_field():
    prompt = _prompt()
    assert prompt.public_dict()["input_mode"] == "options_only"
    assert "free_text" not in {item.name for item in fields(PlayerReflection)}
    assert "text" not in prompt.public_dict()


def test_reflection_records_exact_options_shown_and_selected():
    prompt = _prompt()
    reflection = PlayerReflection(
        prompt_id=prompt.prompt_id,
        event_id=prompt.event_id,
        shown_option_ids=prompt.option_ids,
        selected_option_id="not_sure",
        elapsed_ms=1800,
        answered_before_reveal=True,
        submitted_at=NOW,
    )
    reflection.validate_against(prompt)
    assert reflection.event_dict()["shown_option_ids"] == list(prompt.option_ids)
    assert reflection.event_dict()["answered_before_reveal"] is True


def test_reflection_rejects_an_option_that_was_not_shown():
    prompt = _prompt()
    with pytest.raises(ReviewContractViolation, match="must have been shown"):
        PlayerReflection(
            prompt_id=prompt.prompt_id,
            event_id=prompt.event_id,
            shown_option_ids=prompt.option_ids,
            selected_option_id="invented_answer",
            elapsed_ms=400,
            answered_before_reveal=True,
            submitted_at=NOW,
        )


def test_reflection_rejects_changed_option_set_on_submit():
    prompt = _prompt()
    reflection = PlayerReflection(
        prompt_id=prompt.prompt_id,
        event_id=prompt.event_id,
        shown_option_ids=("still_protected", "not_sure", "none_of_these"),
        selected_option_id="not_sure",
        elapsed_ms=900,
        answered_before_reveal=True,
        submitted_at=NOW,
    )
    with pytest.raises(ReviewContractViolation, match="exactly match"):
        reflection.validate_against(prompt)


def test_plan_chapters_store_references_not_copied_lesson_text():
    chapter = PlanChapter(
        event_id="e",
        role=ChapterRole.KNOWLEDGE_GAP,
        content_ref="king_and_pawn/opposition",
        canonical_source="backend/data/coaching/endgame_theory_tree.json",
    )
    assert set(chapter.contract_dict()) == {
        "event_id",
        "role",
        "content_ref",
        "canonical_source",
    }


def test_single_position_chapter_accepts_caption_authorization():
    event = _event()
    plan = _plan(event.event_id, role=ChapterRole.TURNING_POINT)
    plan.validate_against(event_index((event,)))


def test_recurring_connection_requires_plan_grade():
    caption_event = _event()
    plan = _plan(
        caption_event.event_id,
        role=ChapterRole.RECURRING_CONNECTION,
    )
    with pytest.raises(ReviewContractViolation, match="lacks plan authorization"):
        plan.validate_against(event_index((caption_event,)))


def test_prescribed_next_action_requires_plan_grade():
    event = _event()
    plan = _plan(event.event_id, with_next_action=True)
    with pytest.raises(ReviewContractViolation, match="Plan-grade evidence"):
        plan.validate_against(event_index((event,)))


def test_plan_rejects_unknown_or_duplicate_event_references():
    plan = _plan("missing")
    with pytest.raises(ReviewContractViolation, match="unknown chapter event"):
        plan.validate_against({})

    with pytest.raises(ReviewContractViolation, match="cannot repeat"):
        GameTeachingPlan(
            plan_id="duplicate-plan",
            generated_at=NOW,
            input_fingerprint=FINGERPRINT,
            opening_text="I watched this game.",
            game_arc="One relationship decided it.",
            chapters=(
                PlanChapter("e", ChapterRole.TURNING_POINT),
                PlanChapter("e", ChapterRole.REFLECTION),
            ),
            takeaway="Check the relationship.",
        )


def test_phase1_plan_cannot_claim_visible_rollout():
    with pytest.raises(ReviewContractViolation, match="shadow mode"):
        GameTeachingPlan(
            plan_id="visible-plan",
            generated_at=NOW,
            input_fingerprint=FINGERPRINT,
            opening_text="I watched this game.",
            game_arc="One relationship decided it.",
            chapters=(PlanChapter("e", ChapterRole.TURNING_POINT),),
            takeaway="Check the relationship.",
            rollout_mode="visible",
        )


def test_next_action_must_come_from_a_selected_chapter():
    selected = _event(event_id="selected")
    other = _event(event_id="other")
    plan = GameTeachingPlan(
        plan_id="mismatched-action",
        generated_at=NOW,
        input_fingerprint=FINGERPRINT,
        opening_text="I watched this game.",
        game_arc="One relationship decided it.",
        chapters=(PlanChapter("selected", ChapterRole.TURNING_POINT),),
        takeaway="Check the relationship.",
        next_action=_next_action("other"),
    )
    with pytest.raises(ReviewContractViolation, match="selected chapter"):
        plan.validate_against(event_index((selected, other)))


def test_next_action_rejects_protocol_relative_route():
    with pytest.raises(ReviewContractViolation, match="app-relative route"):
        ReviewNextAction(
            source_event_id="selected",
            href="//outside.example/training",
            action_kind="practise",
            content_kind="concept",
            content_id="piece_safety",
            canonical_source="personal_curriculum",
        )


def test_event_index_rejects_duplicate_identities():
    event = _event()
    with pytest.raises(ReviewContractViolation, match="duplicate event_id"):
        event_index((event, event))


def test_contract_module_has_no_database_network_or_llm_dependency():
    import services.game_review_contracts as module

    source = inspect.getsource(module)
    forbidden = ("pymongo", "motor", "requests", "httpx", "openai", "anthropic")
    assert all(token not in source.lower() for token in forbidden)


def test_contracts_are_json_serializable_without_custom_encoder():
    event = _event(reflection_eligible=True)
    prompt = _prompt()
    plan = _plan(event.event_id)
    plan.validate_against(event_index((event,)))

    json.dumps(event.contract_dict(), sort_keys=True)
    json.dumps(prompt.public_dict(), sort_keys=True)
    json.dumps(plan.contract_dict(), sort_keys=True)
