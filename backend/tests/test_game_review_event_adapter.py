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
from services.caption_facts import (
    LegalMaterialLossCause,
    PieceOnSquare,
    ReviewTeachingCause,
    build_verified_line_cause,
)
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
from services.game_review_planner import QUALITY_V2_FORMULA, SHADOW_FORMULA


SNAPSHOT = (
    Path(__file__).parents[1]
    / "data"
    / "corpus_snapshots"
    / "personalized_game_review_phase2_legacy_contracts_2026-09-01.json"
)


def _decision(
    *,
    verified: bool = True,
    skip: bool = False,
    cause: ReviewTeachingCause | None = None,
    stayed_winning: bool = False,
    decisiveness_changed: bool = False,
) -> MoveTeachingDecision:
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
            mover_state_before="winning" if stayed_winning else "balanced",
            mover_state_after="winning" if stayed_winning else "losing",
            stayed_winning=stayed_winning,
            decisiveness_changed=decisiveness_changed,
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
        cause=cause,
    )


def _bh6_cause() -> LegalMaterialLossCause:
    return LegalMaterialLossCause(
        affected=PieceOnSquare("rook", "a1"),
        attacker=PieceOnSquare("knight", "c2"),
        punishment_san="Nxa1",
        material_loss_cp=500,
        best_move_san="Rd1",
        best_move_purpose="moves_affected_piece",
        best_move_from="a1",
        best_move_to="d1",
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


def test_quality_v2_projects_one_cause_into_words_practical_frame_and_geometry():
    decision = _decision(cause=_bh6_cause(), stayed_winning=True)
    event = adapt_move_teaching_decision(
        decision,
        _context(
            san="Bh6",
            concept_id="piece_safety.simple_hang",
            quality_v2_requested=True,
        ),
    )
    payload = event.contract_dict()

    assert payload["cause"]["fingerprint"] == decision.cause.fingerprint
    assert payload["practical"] == {
        "kind": "stayed_winning",
        "state_before": "winning",
        "state_after": "winning",
        "headline": "You kept control — but left one piece behind",
        "lead": "You were already winning and Bh6 did not throw the game away.",
        "source": "caption_pipeline.practical_severity",
    }
    assert "rook on a1" in payload["teaching"]["caption"]
    assert "knight on c2" in payload["teaching"]["caption"]
    assert "Nxa1" in payload["teaching"]["caption"]
    assert "Rd1 moved the rook out of danger" in payload["teaching"]["caption"]
    assert payload["teaching"]["cause_fingerprint"] == decision.cause.fingerprint
    assert payload["teaching"]["visual"]["relationship_arrows"] == [
        {"from": "c2", "to": "a1", "role": "threat"},
        {"from": "a1", "to": "d1", "role": "safe_move"},
    ]


def test_quality_v2_without_a_verified_typed_cause_preserves_v1_projection():
    legacy = adapt_move_teaching_decision(_decision(), _context()).contract_dict()
    requested = adapt_move_teaching_decision(
        _decision(), _context(quality_v2_requested=True)
    ).contract_dict()
    assert requested == legacy


def test_quality_v2_projects_allowed_mate_from_the_same_verified_line_cause():
    cause = build_verified_line_cause(
        fen_before="8/p1p2p1p/6p1/6Pk/2Q5/P6P/KPP2q2/3r4 b - - 4 30",
        played_san="Rd2",
        best_move_san="Qf3",
        pv_after_played=("Qg4#",),
        pv_after_best=("Qxc7", "Rf1", "Qc4", "Rf2"),
        cp_loss=10608,
    )
    assert cause is not None
    event = adapt_move_teaching_decision(
        _decision(cause=cause, decisiveness_changed=True),
        _context(
            san="Rd2",
            concept_id="calculation.verified_stored_line",
            quality_v2_requested=True,
        ),
    )
    payload = event.contract_dict()
    assert payload["cause"]["lesson_kind"] == "allowed_forced_mate"
    assert payload["practical"]["headline"] == "This is where the game changed"
    assert payload["practical"]["lead"] == (
        "After Rd2, the position changed from balanced to losing."
    )
    assert payload["teaching"]["caption"] == (
        "Rd2 fails because it allows Qg4#, which is checkmate. "
        "Qf3 stopped that immediate finish."
    )
    assert payload["teaching"]["principle"] == (
        "Before moving, scan every check your opponent can play next."
    )
    assert payload["teaching"]["visual"]["relationship_arrows"] == [
        {"from": "c4", "to": "g4", "role": "threat"},
        {"from": "f2", "to": "f3", "role": "safe_move"},
    ]


def test_quality_v2_exchange_caption_counts_the_full_sequence():
    cause = build_verified_line_cause(
        fen_before="r2r2k1/pbq2pbp/1p1ppnp1/8/4PB2/1PN4N/1P3PPP/2RQ1RK1 w - - 4 17",
        played_san="Qc2",
        best_move_san="Nd5",
        pv_after_played=("Nxe4", "f3", "Nxc3", "bxc3"),
        pv_after_best=("Qb8", "Nc7", "Bxe4", "f3"),
        cp_loss=209,
    )
    assert cause is not None
    event = adapt_move_teaching_decision(
        _decision(cause=cause, decisiveness_changed=False),
        _context(
            san="Qc2",
            concept_id="calculation.verified_stored_line",
            quality_v2_requested=True,
        ),
    )
    caption = event.teaching.caption
    assert event.teaching.headline == "The capture sequence cost material"
    assert event.teaching.practical_lead == (
        "Qc2 began a series of captures that ended badly for you."
    )
    assert "Qc2, Nxe4, f3, Nxc3, bxc3" in caption
    assert "give up a pawn and a knight" in caption
    assert "recover only a knight" in caption
    assert "finish one pawn down" in caption
    assert "lose it for nothing" not in caption


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


def test_subordinate_flag_hides_a_stored_v2_event_immediately_on_rollback():
    typed = adapt_move_teaching_decision(
        _decision(cause=_bh6_cause(), stayed_winning=True),
        _context(
            san="Bh6",
            concept_id="piece_safety.simple_hang",
            quality_v2_requested=True,
        ),
    )
    event = typed.contract_dict()
    legacy = {"decryption_data": [], "status": "complete"}

    rolled_back = maybe_attach_phase2_review_fields(
        legacy,
        stored_moves=({"teachable_event": event},),
        env={"PERSONALIZED_GAME_REVIEW_COACH_ENABLED": "true"},
    )
    enabled = maybe_attach_phase2_review_fields(
        legacy,
        stored_moves=({"teachable_event": event},),
        env={
            "PERSONALIZED_GAME_REVIEW_COACH_ENABLED": "true",
            "PERSONALIZED_GAME_REVIEW_QUALITY_V2_ENABLED": "true",
        },
    )

    assert rolled_back["teachable_events"] == []
    assert enabled["teachable_events"] == [event]


def test_flag_on_rechecks_stored_evidence_instead_of_trusting_display_boolean():
    tampered = adapt_move_teaching_decision(_decision(), _context()).contract_dict()
    tampered["evidence"]["final_verified"] = False
    legacy = {"decryption_data": [{"teachable_event": tampered}]}

    result = maybe_attach_phase2_review_fields(
        legacy,
        env={"PERSONALIZED_GAME_REVIEW_COACH_ENABLED": "true"},
    )

    assert result["teachable_events"] == []


def _stored_plan_envelope(event, *, formula_id=SHADOW_FORMULA):
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
        "formula_id": formula_id,
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


def test_phase5_rejects_a_plan_from_the_wrong_flag_formula():
    typed_event = adapt_move_teaching_decision(_decision(), _context())
    event = typed_event.contract_dict()
    result = maybe_attach_phase5_review_fields(
        {"decryption_data": []},
        stored_moves=({"teachable_event": event},),
        stored_plan=_stored_plan_envelope(
            typed_event,
            formula_id=QUALITY_V2_FORMULA,
        ),
        env={"PERSONALIZED_GAME_REVIEW_COACH_ENABLED": "true"},
    )
    assert "game_teaching_plan" not in result


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
