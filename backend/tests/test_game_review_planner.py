"""Phase 3 shadow-planner tests."""
from __future__ import annotations

from datetime import datetime, timezone
import inspect

import pytest

from services.detector_quality import QualitySurface
from services.game_review_contracts import (
    ConceptReference,
    EventActor,
    EventEvidence,
    EventOutcome,
    MoveReference,
    OpportunityEvidence,
    ReviewContractViolation,
    ReviewNextAction,
    TeachableEvent,
    TeachingReference,
    VisualReference,
)
from services.game_review_planner import (
    PLANNER_VERSION,
    SHADOW_FORMULA,
    SHADOW_MOMENT_CAP,
    SHADOW_REFLECTION_QUESTION_BUDGET,
    PlannerEventFeatures,
    build_shadow_game_teaching_plan,
)


NOW = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)


def _event(
    event_id: str,
    ply: int,
    *,
    caption: bool = True,
    principle: bool = True,
    visual: bool = True,
    reflection: bool = False,
    outcome: EventOutcome = EventOutcome.ALLOWED,
    quality_id: str = "gap:piece_safety:simple_hang",
    surface: QualitySurface = QualitySurface.PLAN,
) -> TeachableEvent:
    return TeachableEvent(
        event_id=event_id,
        move=MoveReference(
            ply=ply,
            number=(ply + 1) // 2,
            san="Bg5",
            actor=EventActor.USER,
        ),
        concept=ConceptReference(
            concept_id="piece_safety.undefended_piece"
        ),
        outcome=outcome,
        opportunity=OpportunityEvidence(eligible=True),
        evidence=EventEvidence(
            quality_id=quality_id,
            source_version="fixture.v1",
            provenance=(f"move_observation:g:{ply}",),
            final_verified=True,
        ),
        teaching=TeachingReference(
            caption="Your bishop could be taken." if caption else "",
            principle=(
                "Check whether every defender can move."
                if principle
                else ""
            ),
            visual=VisualReference(
                arrows=(("c6", "g2"),) if visual else (),
            ),
        ),
        requested_surface=surface,
        reflection_eligible=reflection,
    )


def _feature(
    event: TeachableEvent,
    *,
    critical: bool = True,
    cp_loss: float = 300,
) -> PlannerEventFeatures:
    return PlannerEventFeatures(
        event_id=event.event_id,
        was_critical_moment=critical,
        cp_loss=cp_loss,
    )


def test_shadow_constants_match_the_data_lock():
    assert SHADOW_FORMULA == "D_teaching_then_critical"
    assert SHADOW_MOMENT_CAP == 2
    assert SHADOW_REFLECTION_QUESTION_BUDGET == 1


def test_formula_prefers_complete_teaching_before_larger_loss():
    complete = _event("complete", 20)
    larger_loss = _event(
        "larger-loss",
        10,
        principle=False,
        visual=False,
    )
    result = build_shadow_game_teaching_plan(
        game_id="g",
        events=(larger_loss, complete),
        features={
            complete.event_id: _feature(complete, cp_loss=300),
            larger_loss.event_id: _feature(larger_loss, cp_loss=900),
        },
        generated_at=NOW,
    )
    assert result.selected_event_ids == ("larger-loss", "complete")
    assert result.plan is not None
    assert result.plan.takeaway == "Check whether every defender can move."


def test_cap_is_two_and_display_order_is_chronological():
    events = (
        _event("late-complete", 40),
        _event("early-complete", 10),
        _event("middle-incomplete", 20, visual=False),
    )
    result = build_shadow_game_teaching_plan(
        game_id="g",
        events=events,
        features={
            event.event_id: _feature(event, cp_loss=300)
            for event in events
        },
        generated_at=NOW,
    )
    assert result.selected_event_ids == ("early-complete", "late-complete")
    assert len(result.plan.chapters) == 2


def test_only_one_selected_event_can_request_reflection():
    first = _event("first", 10, reflection=True)
    second = _event("second", 20, reflection=True)
    result = build_shadow_game_teaching_plan(
        game_id="g",
        events=(first, second),
        features={
            first.event_id: _feature(first, cp_loss=500),
            second.event_id: _feature(second, cp_loss=300),
        },
        generated_at=NOW,
    )
    assert result.selected_reflection_event_ids == ("first",)


def test_shadow_or_missing_feature_is_rejected_without_a_plan_claim():
    shadow = _event(
        "shadow",
        10,
        quality_id="gap:future:unknown",
        surface=QualitySurface.DIAGNOSTIC,
        reflection=False,
    )
    result = build_shadow_game_teaching_plan(
        game_id="g",
        events=(shadow,),
        features={shadow.event_id: _feature(shadow)},
        generated_at=NOW,
    )
    assert result.plan is None
    assert result.rejected_event_ids == ("shadow",)


def test_visual_only_event_cannot_create_a_textual_game_takeaway():
    visual_only = _event(
        "visual-only",
        10,
        caption=False,
        principle=False,
        visual=True,
    )
    result = build_shadow_game_teaching_plan(
        game_id="g",
        events=(visual_only,),
        features={visual_only.event_id: _feature(visual_only)},
        generated_at=NOW,
    )
    assert result.plan is None
    assert result.rejected_event_ids == ("visual-only",)


def test_recurring_role_and_next_action_require_plan_authority():
    event = _event("recurring", 10)
    action = ReviewNextAction(
        source_event_id=event.event_id,
        href="/training/prescribed?weakness=piece_safety",
        action_kind="practise",
        content_kind="concept",
        content_id="piece_safety",
        canonical_source="personal_curriculum",
    )
    result = build_shadow_game_teaching_plan(
        game_id="g",
        events=(event,),
        features={event.event_id: _feature(event)},
        generated_at=NOW,
        recurring_event_ids=(event.event_id,),
        next_actions={event.event_id: action},
    )
    payload = result.plan.contract_dict()
    assert payload["chapters"][0]["role"] == "recurring_connection"
    assert payload["next_action"]["source_event_id"] == event.event_id


def test_plan_is_deterministic_shadow_and_does_not_claim_causality():
    event = _event("e", 10)
    kwargs = {
        "game_id": "g",
        "events": (event,),
        "features": {event.event_id: _feature(event)},
        "generated_at": NOW,
    }
    first = build_shadow_game_teaching_plan(**kwargs)
    second = build_shadow_game_teaching_plan(**kwargs)
    assert first.contract_dict() == second.contract_dict()
    assert first.contract_dict()["planner_version"] == PLANNER_VERSION
    assert first.plan.rollout_mode == "shadow"
    assert first.plan.game_arc == "I found one moment worth studying in this game."


def test_unknown_feature_or_recurring_reference_fails_closed():
    event = _event("e", 10)
    with pytest.raises(ReviewContractViolation, match="unknown events"):
        build_shadow_game_teaching_plan(
            game_id="g",
            events=(event,),
            features={"missing": PlannerEventFeatures("missing", True, 300)},
            generated_at=NOW,
        )
    with pytest.raises(ReviewContractViolation, match="unknown events"):
        build_shadow_game_teaching_plan(
            game_id="g",
            events=(event,),
            features={event.event_id: _feature(event)},
            generated_at=NOW,
            recurring_event_ids=("missing",),
        )


def test_planner_has_no_engine_database_network_or_llm_dependency():
    import services.game_review_planner as module

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
