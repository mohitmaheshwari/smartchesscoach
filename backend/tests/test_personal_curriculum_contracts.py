from __future__ import annotations

import inspect
from datetime import datetime, timezone
from pathlib import Path

import pytest

from services.endgame_theory_service import (
    CANONICAL_SOURCE,
    get_lesson_by_content_ref,
    resolve_content_ref,
)
from services.personal_curriculum import (
    ApplicationOutcome,
    AssistanceKind,
    AttemptKind,
    ContractViolation,
    CurriculumCandidate,
    CurriculumDestination,
    CurriculumOutcome,
    EvidenceStatus,
    EvidenceSourceType,
    HelpAction,
    LessonCapability,
    LessonResult,
    StudentState,
    TeachingStage,
    _knowledge_destination,
    build_curriculum_decision,
    compose_personal_curriculum,
    personal_curriculum_enabled,
    personalized_teaching_eligible,
    resolve_endgame_destination,
)


NOW = datetime(2026, 8, 28, 14, 30, tzinfo=timezone.utc)


def _destination(
    *,
    content_id: str = "piece_safety",
    capability: LessonCapability = LessonCapability.GUIDED_PRACTICE,
) -> CurriculumDestination:
    return CurriculumDestination(
        href="/training/prescribed?weakness=piece_safety",
        medium="puzzles",
        capability=capability,
        content_kind="concept",
        content_id=content_id,
        canonical_source="existing focus/concept registries",
    )


def _candidate(
    outcome: CurriculumOutcome,
    *,
    destination: CurriculumDestination | None = None,
    state: StudentState = StudentState.LEARNING,
    quality_id: str | None = None,
) -> CurriculumCandidate:
    return CurriculumCandidate(
        outcome=outcome,
        student_state=state,
        title="Keep your pieces safe",
        reason="This is the one idea to work on next.",
        evidence_summary="Seen repeatedly in measured games.",
        evidence_status=EvidenceStatus.TRUSTWORTHY,
        destination=destination or _destination(),
        evidence_owner="active focus/PIC",
        evidence_ref="synthetic-probe",
        detector_quality_id=quality_id,
    )


def _keys(value):
    if isinstance(value, dict):
        for key, nested in value.items():
            yield key
            yield from _keys(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _keys(nested)


def test_feature_flag_is_default_off():
    assert personal_curriculum_enabled({}) is False
    assert personal_curriculum_enabled({"PERSONAL_CURRICULUM_ENABLED": "false"}) is False
    assert personal_curriculum_enabled({"PERSONAL_CURRICULUM_ENABLED": "true"}) is True


def test_flag_off_returns_no_replacement_decision():
    result = compose_personal_curriculum(
        _candidate(CurriculumOutcome.REPAIR),
        generated_at=NOW,
        env={},
    )
    assert result is None


def test_flag_on_returns_the_same_pure_contract_shape():
    primary = _candidate(CurriculumOutcome.REPAIR)
    flagged = compose_personal_curriculum(
        primary,
        generated_at=NOW,
        env={"PERSONAL_CURRICULUM_ENABLED": "true"},
    )
    pure = build_curriculum_decision(primary, generated_at=NOW)
    assert flagged == pure


@pytest.mark.parametrize(
    ("outcome", "state", "quality_id"),
    [
        (CurriculumOutcome.OBSERVE, StudentState.NEW, None),
        (CurriculumOutcome.REPAIR, StudentState.LEARNING, None),
        (CurriculumOutcome.EXPAND, StudentState.NEW, None),
        (CurriculumOutcome.CONTINUE, StudentState.CAN_DO_WITH_HELP, None),
        (CurriculumOutcome.REVIEW, StudentState.CAN_DO_ALONE, None),
        (
            CurriculumOutcome.APPLY,
            StudentState.USED_IN_GAMES,
            "gap:piece_safety:simple_hang",
        ),
    ],
)
def test_each_signed_outcome_has_a_deterministic_contract(
    outcome,
    state,
    quality_id,
):
    candidate = _candidate(outcome, state=state, quality_id=quality_id)
    first = build_curriculum_decision(candidate, generated_at=NOW)
    second = build_curriculum_decision(candidate, generated_at=NOW)

    assert first == second
    assert first["primary"]["outcome"] == outcome.value
    assert first["primary"]["state"] == state.value
    assert first["generated_at"] == "2026-08-28T14:30:00+00:00"


def test_public_decision_contains_one_primary_and_at_most_one_review():
    primary = _candidate(CurriculumOutcome.EXPAND)
    review = _candidate(
        CurriculumOutcome.REVIEW,
        destination=_destination(content_id="king_safety"),
        state=StudentState.CAN_DO_ALONE,
    )

    result = build_curriculum_decision(
        primary,
        review=review,
        generated_at=NOW,
    )

    assert result["plan_rules"] == {
        "primary_items": 1,
        "maximum_review_items": 1,
        "explore_replaces_plan": False,
    }
    assert result["review"]["outcome"] == "review"


def test_optional_secondary_item_must_be_review():
    with pytest.raises(ContractViolation, match="review outcome"):
        build_curriculum_decision(
            _candidate(CurriculumOutcome.REPAIR),
            review=_candidate(
                CurriculumOutcome.EXPAND,
                destination=_destination(content_id="king_safety"),
            ),
            generated_at=NOW,
        )


def test_primary_and_review_cannot_duplicate_the_same_lesson():
    with pytest.raises(ContractViolation, match="same lesson"):
        build_curriculum_decision(
            _candidate(CurriculumOutcome.EXPAND),
            review=_candidate(
                CurriculumOutcome.REVIEW,
                state=StudentState.CAN_DO_ALONE,
            ),
            generated_at=NOW,
        )


def test_public_contract_hides_internal_evidence_and_quality_keys():
    result = build_curriculum_decision(
        _candidate(CurriculumOutcome.REPAIR),
        generated_at=NOW,
    )
    forbidden = {
        "skill_id",
        "tier",
        "gate",
        "mastery_formula",
        "evidence_owner",
        "evidence_ref",
        "detector_quality_id",
        "canonical_source",
    }
    assert not forbidden.intersection(set(_keys(result)))


def test_reliable_claim_is_rejected_until_thresholds_are_locked():
    with pytest.raises(ContractViolation, match="Reliable"):
        _candidate(
            CurriculumOutcome.REVIEW,
            state=StudentState.RELIABLE,
        )


@pytest.mark.parametrize(
    "status",
    [EvidenceStatus.SPARSE, EvidenceStatus.STALE, EvidenceStatus.CONFLICTING],
)
def test_untrustworthy_evidence_cannot_create_repair_or_apply(status):
    with pytest.raises(ContractViolation, match="trustworthy evidence"):
        CurriculumCandidate(
            outcome=CurriculumOutcome.REPAIR,
            student_state=StudentState.LEARNING,
            title="Keep your pieces safe",
            reason="This is the one idea to work on next.",
            evidence_summary="The current evidence is not strong enough.",
            evidence_status=status,
            destination=_destination(),
            evidence_owner="active focus/PIC",
        )


@pytest.mark.parametrize(
    "status",
    [
        EvidenceStatus.NOT_MEASURED,
        EvidenceStatus.SPARSE,
        EvidenceStatus.STALE,
        EvidenceStatus.CONFLICTING,
    ],
)
def test_uncertain_evidence_can_produce_an_honest_observe_contract(status):
    candidate = CurriculumCandidate(
        outcome=CurriculumOutcome.OBSERVE,
        student_state=StudentState.NEW,
        title="Let me learn how you play",
        reason="A measured game will give us something real to work with.",
        evidence_summary="No trustworthy personal pattern is available yet.",
        evidence_status=status,
        destination=CurriculumDestination(
            href="/play-with-coach",
            medium="live_game",
            capability=LessonCapability.DIAGNOSTIC,
            content_kind="diagnostic",
            content_id="coached_game",
            canonical_source="coach game session",
        ),
        evidence_owner="diagnostic",
    )
    result = build_curriculum_decision(candidate, generated_at=NOW)
    assert result["primary"]["outcome"] == "observe"


def test_apply_claim_rejects_disabled_rule_of_square_detector():
    with pytest.raises(ContractViolation, match="Plan-grade"):
        _candidate(
            CurriculumOutcome.APPLY,
            state=StudentState.USED_IN_GAMES,
            quality_id="concept:endgame_rule_of_square",
        )


def test_endgame_content_refs_resolve_through_one_canonical_owner():
    expected = {
        "opposition": "king_and_pawn/opposition",
        "rule_of_square": "king_and_pawn/square_rule",
        "lucena_position": "rook_endgames/lucena",
        "philidor_position": "rook_endgames/philidor",
    }
    for content_ref, lesson_id in expected.items():
        resolved = resolve_content_ref(content_ref)
        assert resolved is not None
        assert resolved["lesson_id"] == lesson_id
        assert resolved["canonical_source"] == CANONICAL_SOURCE
        assert get_lesson_by_content_ref(content_ref) is not None


def test_rule_of_square_destination_copies_no_lesson_content():
    destination = resolve_endgame_destination(
        "rule_of_square",
        capability=LessonCapability.TEACH,
    )
    assert destination.href == "/endgames/king_and_pawn/square_rule"
    assert destination.content_id == "king_and_pawn/square_rule"
    assert destination.canonical_source == CANONICAL_SOURCE
    assert set(destination.public_dict()) == {
        "href",
        "medium",
        "capability",
        "lesson_kind",
        "lesson_id",
    }


def test_today_composer_no_longer_owns_an_endgame_route_table():
    import services.today_composer as today_composer

    assert not hasattr(today_composer, "ENDGAME_ROUTES")
    source = inspect.getsource(today_composer)
    assert "resolve_content_ref(content_ref)" in source


def test_today_composer_uses_the_canonical_endgame_route_and_safe_fallback():
    from services.today_composer import _action_for_band

    routed = _action_for_band(
        "beginner_high",
        {
            "kind": "endgame",
            "content_ref": "rule_of_square",
            "skill_id": "endgame_rule_of_square",
        },
    )
    assert routed["href"] == "/endgames/king_and_pawn/square_rule"

    fallback = _action_for_band(
        "beginner_high",
        {
            "kind": "endgame",
            "content_ref": "not_in_theory_tree",
            "skill_id": "legacy_endgame",
        },
    )
    assert fallback["href"] == "/play-with-coach?focus=legacy_endgame"


def test_today_composer_remains_the_only_player_facing_engine2_selector():
    services = Path(__file__).resolve().parents[1] / "services"
    callers = []
    for path in services.glob("*.py"):
        if path.name == "engine2_skill_builder.py":
            continue
        if "pick_next_skill(" in path.read_text(encoding="utf-8"):
            callers.append(path.name)
    assert callers == ["today_composer.py"]


def test_curriculum_contract_cannot_read_legacy_learning_aggregate():
    import services.personal_curriculum as module

    assert "user_learning_progress" not in inspect.getsource(module)


def _lesson_result(**overrides) -> LessonResult:
    values = {
        "content_kind": "endgame",
        "content_id": "king_and_pawn/square_rule",
        "canonical_source": CANONICAL_SOURCE,
        "content_version": "2026-08-29",
        "attempt_kind": AttemptKind.INDEPENDENT,
        "occurred_at": NOW,
        "correct": True,
        "position_id": "square-rule-probe-2",
        "board_verified": True,
        "distinct_position": True,
    }
    values.update(overrides)
    return LessonResult(**values)


def test_explanation_only_earns_learning():
    result = _lesson_result(
        attempt_kind=AttemptKind.EXPLANATION,
        correct=None,
        position_id=None,
        board_verified=False,
        distinct_position=False,
    )
    assert result.earned_state() == StudentState.LEARNING


def test_guided_correct_attempt_earns_with_help_only():
    result = _lesson_result(
        attempt_kind=AttemptKind.GUIDED,
        assistance=(AssistanceKind.GUIDED_LINE,),
    )
    assert result.earned_state() == StudentState.CAN_DO_WITH_HELP


def test_answer_reveal_blocks_independent_credit():
    result = _lesson_result(
        assistance=(AssistanceKind.ANSWER_REVEALED,),
    )
    assert result.earned_state() == StudentState.CAN_DO_WITH_HELP


def test_unassisted_distinct_verified_position_earns_can_do_alone():
    assert _lesson_result().earned_state() == StudentState.CAN_DO_ALONE


def test_same_position_retry_does_not_earn_can_do_alone():
    result = _lesson_result(distinct_position=False)
    assert result.earned_state() == StudentState.LEARNING


@pytest.mark.parametrize(
    "outcome",
    [ApplicationOutcome.DID_NOT_OCCUR, ApplicationOutcome.UNCLEAR],
)
def test_no_or_unclear_game_opportunity_never_changes_state(outcome):
    result = _lesson_result(
        attempt_kind=AttemptKind.APPLICATION,
        correct=None,
        position_id=None,
        board_verified=False,
        distinct_position=False,
        application_outcome=outcome,
        source_type=EvidenceSourceType.ORGANIC_GAME,
        detector_quality_id="concept:endgame_rule_of_square",
    )
    assert result.earned_state() is None


def test_disabled_detector_cannot_earn_used_in_games():
    result = _lesson_result(
        attempt_kind=AttemptKind.APPLICATION,
        correct=None,
        position_id=None,
        board_verified=False,
        distinct_position=False,
        application_outcome=ApplicationOutcome.APPLIED,
        source_type=EvidenceSourceType.ORGANIC_GAME,
        detector_quality_id="concept:endgame_rule_of_square",
    )
    assert result.earned_state() is None
    assert result.event_dict()["application"]["plan_authorized"] is False


def test_plan_grade_detector_can_earn_used_in_games():
    result = LessonResult(
        content_kind="concept",
        content_id="piece_safety",
        canonical_source="existing focus/concept registries",
        content_version="1",
        attempt_kind=AttemptKind.APPLICATION,
        occurred_at=NOW,
        source_type=EvidenceSourceType.ORGANIC_GAME,
        application_outcome=ApplicationOutcome.APPLIED,
        detector_quality_id="gap:piece_safety:simple_hang",
    )
    assert result.earned_state() == StudentState.USED_IN_GAMES


def test_lesson_result_event_is_versioned_and_never_emits_reliable():
    event = _lesson_result().event_dict()
    assert event["schema_version"] == "lesson_result.v2"
    assert event["earned_state"] == "can_do_alone"
    assert event["earned_state"] != StudentState.RELIABLE.value


def test_personalized_teaching_requires_both_default_off_flags_and_role():
    enabled = {
        "PERSONAL_CURRICULUM_ENABLED": "true",
        "PERSONALIZED_TEACHING_ENABLED": "true",
        "PERSONAL_CURRICULUM_ROLES": "admin",
    }
    assert personalized_teaching_eligible("admin", enabled) is True
    assert personalized_teaching_eligible("user", enabled) is False
    assert personalized_teaching_eligible(
        "admin",
        {"PERSONAL_CURRICULUM_ENABLED": "true"},
    ) is False


def test_mate_pattern_keeps_legacy_kind_but_routes_to_canonical_endgame():
    destination = _knowledge_destination(
        {
            "kind": "mate_pattern",
            "content_ref": "queen_checkmate",
            "skill_id": "mate_kq_vs_k",
        },
        {
            "href": "/play-with-coach?focus=mate_kq_vs_k",
            "medium": "coached_game",
        },
    )

    assert destination.content_kind == "endgame"
    assert destination.content_id == "basic_mates/queen_mate"
    assert destination.canonical_source == CANONICAL_SOURCE


def test_lucky_move_with_conflicting_reason_does_not_earn_independent_proof():
    result = _lesson_result(
        stage=TeachingStage.TRANSFER,
        prediction_correct=True,
        reasoning_consistent=False,
    )
    assert result.earned_state() == StudentState.LEARNING
    event = result.event_dict()
    assert event["attempt"]["reasoning_consistent"] is False


def test_requested_help_caps_credit_at_can_do_with_help():
    result = _lesson_result(
        requested_help=(HelpAction.SHOW_ON_BOARD,),
    )
    assert result.earned_state() == StudentState.CAN_DO_WITH_HELP


def test_application_event_preserves_organic_source_and_provenance():
    event = LessonResult(
        content_kind="concept",
        content_id="piece_safety",
        canonical_source="backend/data/theory/tactical_patterns.json",
        content_version="1",
        skill_id="piece_safety",
        primary_skill_id="piece_safety",
        attempt_kind=AttemptKind.APPLICATION,
        occurred_at=NOW,
        stage=TeachingStage.APPLY,
        source_type=EvidenceSourceType.ORGANIC_GAME,
        application_outcome=ApplicationOutcome.APPLIED,
        detector_quality_id="gap:piece_safety:simple_hang",
        detector_version="simple_hang.v1",
        evidence_owner="move_observations",
        evidence_ref="game-1:move-17",
    ).event_dict()

    assert event["application"]["source_type"] == "organic_game"
    assert event["provenance"] == {
        "owner": "move_observations",
        "ref": "game-1:move-17",
    }
