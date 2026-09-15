"""Phase 4 adapters into the existing learning-session evidence ledger.

This module owns no chess rules and no mastery thresholds. It converts
server-owned review, guided-practice and current-schema application evidence
into ``personal_curriculum.LessonResult`` values, then appends their serialized
form to ``learning_sessions.events`` in shadow mode.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Mapping

from services.detector_quality import gap_quality_id
from services.destination_safety_detector import is_destination_safety_fact_version
from services.personal_curriculum import (
    ApplicationOutcome,
    AssistanceKind,
    AttemptKind,
    ContractViolation,
    EvidenceSourceType,
    LessonResult,
    PIC_CANONICAL_SOURCE,
    PIC_CONTENT_ID,
    PIC_CONTENT_KIND,
    PIC_CONTENT_VERSION,
    PIC_SKILL_ID,
)
from services.learning_evidence_ledger import (
    EVENT_KEY_COMPATIBILITY_VERSION as REVIEW_LEARNING_ADAPTER_VERSION,
    build_shadow_learning_event,
    store_shadow_lesson_results,
    store_shadow_lesson_results_sync,
)


def _parse_datetime(value: Any, field_name: str) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        raw = str(value or "").strip()
        if len(raw) >= 10:
            # Chess.com imports commonly store the calendar day as
            # YYYY.MM.DD. Preserve any time suffix while normalizing the date.
            raw = raw[:10].replace(".", "-") + raw[10:]
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except (TypeError, ValueError) as exc:
            raise ContractViolation(f"{field_name} must be an ISO timestamp") from exc
    if parsed.tzinfo is None:
        # Existing imported games can carry naive UTC datetimes. Preserve the
        # stored instant instead of dropping otherwise valid learning evidence.
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def lesson_result_from_review_reflection(
    document: Mapping[str, Any],
) -> LessonResult:
    """A completed review/reveal proves exposure, never independent skill."""
    if document.get("reflection_kind") != "game_review_event":
        raise ContractViolation("unsupported reflection kind")
    event = document.get("event")
    response = document.get("response")
    if not isinstance(event, Mapping) or not isinstance(response, Mapping):
        raise ContractViolation("reflection evidence is incomplete")
    content_id = str(event.get("content_ref") or "")
    canonical_source = str(event.get("canonical_source") or "")
    if not content_id or not canonical_source:
        raise ContractViolation("reflection lacks canonical content identity")
    if (
        content_id != PIC_CONTENT_ID
        or canonical_source != PIC_CANONICAL_SOURCE
    ):
        raise ContractViolation("reflection canonical content is unsupported")
    source_event_id = str(event.get("event_id") or "")
    if not source_event_id:
        raise ContractViolation("reflection lacks source event identity")
    return LessonResult(
        content_kind=PIC_CONTENT_KIND,
        content_id=content_id,
        canonical_source=canonical_source,
        content_version=PIC_CONTENT_VERSION,
        skill_id=PIC_SKILL_ID,
        primary_skill_id=PIC_SKILL_ID,
        attempt_kind=AttemptKind.EXPLANATION,
        occurred_at=_parse_datetime(response.get("submitted_at"), "submitted_at"),
        correct=None,
        assistance=(AssistanceKind.ANSWER_REVEALED,),
        detector_quality_id=event.get("quality_id"),
        source_event_id=source_event_id,
    )


def lesson_result_from_guided_pic_practice(
    *,
    session_id: str,
    item_id: str,
    interaction_id: str,
    occurred_at: datetime,
    correct: bool,
) -> LessonResult:
    """PIC is guided practice; correctness can prove only 'with help'."""
    if not session_id or not item_id or not interaction_id:
        raise ContractViolation("practice identity is incomplete")
    return LessonResult(
        content_kind=PIC_CONTENT_KIND,
        content_id=PIC_CONTENT_ID,
        canonical_source=PIC_CANONICAL_SOURCE,
        content_version=PIC_CONTENT_VERSION,
        skill_id=PIC_SKILL_ID,
        primary_skill_id=PIC_SKILL_ID,
        attempt_kind=AttemptKind.GUIDED,
        occurred_at=occurred_at,
        correct=bool(correct),
        assistance=(AssistanceKind.GUIDED_LINE,),
        position_id=item_id,
        board_verified=True,
        distinct_position=False,
        detector_quality_id=gap_quality_id("piece_safety", "simple_hang"),
        source_event_id=(
            f"pic_practice:{session_id}:{item_id}:{interaction_id}"
        ),
    )


def lesson_results_from_community_walkthrough(
    *,
    prescription_id: str,
    study: Mapping[str, Any],
    progress: Mapping[str, Any],
    occurred_at: datetime,
) -> List[LessonResult]:
    """Convert a completed community walkthrough into assisted evidence.

    Prediction, reveal, watching and a board-verified replay can establish
    guided practice. They can never establish later-game application.
    """
    study_id = str(study.get("study_id") or "").strip()
    policy_version = str(study.get("admission_policy_version") or "").strip()
    plan = study.get("plan")
    if not prescription_id or not study_id or not policy_version:
        raise ContractViolation("community walkthrough identity is incomplete")
    if not isinstance(plan, Mapping):
        raise ContractViolation("community walkthrough plan is missing")
    plan_fingerprint = str(plan.get("input_fingerprint") or "").strip()
    chapters = plan.get("chapters")
    if not plan_fingerprint or not isinstance(chapters, list):
        raise ContractViolation("community walkthrough plan evidence is incomplete")

    by_event = {
        str(item.get("event_id") or ""): item
        for item in progress.values()
        if isinstance(item, Mapping) and item.get("event_id")
    }
    results: List[LessonResult] = []
    for chapter in chapters:
        if not isinstance(chapter, Mapping):
            raise ContractViolation("community walkthrough chapter is invalid")
        event_id = str(chapter.get("event_id") or "").strip()
        concept_id = str(chapter.get("concept_id") or "").strip()
        quality_id = str(chapter.get("quality_id") or "").strip()
        state = by_event.get(event_id)
        if (
            not event_id
            or not concept_id
            or not quality_id
            or not isinstance(state, Mapping)
            or not all(
                state.get(field) is True
                for field in ("predicted", "revealed", "watched", "replayed")
            )
        ):
            raise ContractViolation("community walkthrough is not complete")
        assistance = [AssistanceKind.ANSWER_REVEALED, AssistanceKind.GUIDED_LINE]
        if state.get("hinted") is True:
            assistance.insert(0, AssistanceKind.HINT)
        results.append(
            LessonResult(
                content_kind="community_game_study",
                content_id=study_id,
                canonical_source="community_game_study_service",
                content_version=policy_version,
                skill_id=concept_id,
                primary_skill_id=concept_id,
                attempt_kind=AttemptKind.GUIDED,
                occurred_at=occurred_at,
                correct=True,
                assistance=tuple(assistance),
                position_id=event_id,
                board_verified=True,
                distinct_position=True,
                prediction_correct=bool(state.get("correct")),
                reason_choice=str(state.get("selected_option_id") or "") or None,
                source_type=EvidenceSourceType.LESSON,
                detector_quality_id=quality_id,
                evidence_owner="community_game_studies",
                evidence_ref=f"{study_id}:{event_id}",
                source_event_id=(
                    f"community_walkthrough:{prescription_id}:{event_id}"
                ),
                response_move_uci=str(state.get("replayed_move_uci") or "") or None,
                first_answer=bool(state.get("correct")),
                admission_version=policy_version,
                admission_fingerprint=plan_fingerprint,
            )
        )
    return results


async def store_community_walkthrough_results(
    collection: Any,
    *,
    user_id: str,
    prescription_id: str,
    study: Mapping[str, Any],
    progress: Mapping[str, Any],
    occurred_at: datetime,
) -> Dict[str, Any]:
    """Idempotently append one assisted result per verified chapter."""
    results = lesson_results_from_community_walkthrough(
        prescription_id=prescription_id,
        study=study,
        progress=progress,
        occurred_at=occurred_at,
    )
    receipts = []
    for result in results:
        event = build_shadow_learning_event(
            result,
            origin="community_game_walkthrough",
        )
        receipts.append(
            await store_shadow_lesson_results(
                collection,
                user_id=user_id,
                events=[event],
            )
        )
    return {
        "assisted_learning_recorded": True,
        "chapter_results": len(results),
        "transfer_status": "not_measured",
        "receipts": receipts,
    }


def application_results_from_observations(
    *,
    game_id: str,
    observations: Iterable[Mapping[str, Any]],
    occurred_at: Any,
    include_handled: bool = False,
    source_type: EvidenceSourceType = EvidenceSourceType.ORGANIC_GAME,
    assistance: tuple[AssistanceKind, ...] = (),
    assistance_measured: bool = True,
) -> List[LessonResult]:
    """Adapt explicit exact opportunities; absence is never application.

    The board fact is identical for imported and Play With Coach games. Its
    provenance is not: callers preserve whether the decision happened in an
    organic game or a coached environment, and whether help was available.
    """
    if source_type not in (
        EvidenceSourceType.ORGANIC_GAME,
        EvidenceSourceType.COACHED_APPLICATION,
    ):
        raise ContractViolation(
            "observation applications require an organic or coached source"
        )
    if any(not isinstance(item, AssistanceKind) for item in assistance):
        raise ContractViolation("assistance entries must be AssistanceKind values")
    if not isinstance(assistance_measured, bool):
        raise ContractViolation("assistance_measured must be boolean")
    results: List[LessonResult] = []
    event_time = _parse_datetime(occurred_at, "occurred_at")
    for observation in observations or []:
        if int(observation.get("schema_version") or 0) < 16:
            continue
        simple_hang = (
            observation.get("missed_pattern") == "piece_safety"
            and observation.get("subtype") == "simple_hang"
        )
        exact_fact = observation.get("destination_safety_exact") or {}
        current_exact_miss = (
            int(observation.get("schema_version") or 0) >= 18
            and is_destination_safety_fact_version(exact_fact.get("version"))
            and exact_fact.get("fires") is True
            and exact_fact.get("derivation_status") == "ok"
            and exact_fact.get("eligible") is True
            and exact_fact.get("outcome") == "miss"
        )
        legacy_exact_miss = (
            int(observation.get("schema_version") or 0) >= 18
            and is_destination_safety_fact_version(exact_fact.get("version"))
            and exact_fact.get("fires") is True
            and exact_fact.get("derivation_status") in {None, "ok"}
            and exact_fact.get("eligible") in {None, True}
            and exact_fact.get("outcome") in {None, "miss"}
            and (
                exact_fact.get("derivation_status") is None
                or exact_fact.get("eligible") is None
                or exact_fact.get("outcome") is None
            )
        )
        exact_miss = current_exact_miss or legacy_exact_miss
        exact_handled = (
            include_handled
            and int(observation.get("schema_version") or 0) >= 18
            and is_destination_safety_fact_version(exact_fact.get("version"))
            and exact_fact.get("derivation_status") == "ok"
            and exact_fact.get("eligible") is True
            and exact_fact.get("outcome") == "handled"
        )
        exact_destination = exact_miss or exact_handled
        if not (simple_hang or exact_destination):
            continue
        ply = int(observation.get("ply") or 0)
        if not game_id or ply < 1:
            continue
        exact_outcome = str(exact_fact.get("outcome") or "")
        application_outcome = (
            ApplicationOutcome.APPLIED
            if exact_destination and exact_outcome == "handled"
            else ApplicationOutcome.MISSED
        )
        exact_measurement_complete = bool(
            simple_hang or current_exact_miss or exact_handled
        )
        limitations = (
            ()
            if exact_measurement_complete
            else ("legacy_exact_opportunity_fields_missing",)
        )
        results.append(
            LessonResult(
                content_kind=PIC_CONTENT_KIND,
                content_id=PIC_CONTENT_ID,
                canonical_source=PIC_CANONICAL_SOURCE,
                content_version=PIC_CONTENT_VERSION,
                skill_id=PIC_SKILL_ID,
                primary_skill_id=PIC_SKILL_ID,
                attempt_kind=AttemptKind.APPLICATION,
                occurred_at=event_time,
                application_outcome=application_outcome,
                source_type=source_type,
                assistance=assistance,
                assistance_measured=assistance_measured,
                detector_quality_id=(
                    "gap:piece_safety:destination_safety_exact"
                    if exact_destination
                    else gap_quality_id("piece_safety", "simple_hang")
                ),
                detector_version=(
                    str(exact_fact.get("version"))
                    if exact_destination
                    else None
                ),
                evidence_owner="move_observations",
                evidence_ref=f"{game_id}:{ply}",
                proof_contract_version=(
                    str(exact_fact.get("version"))
                    if exact_destination
                    else None
                ),
                evidence_complete=exact_measurement_complete,
                evidence_limitations=limitations,
                source_event_id=f"move_observation:{game_id}:{ply}",
            )
        )
    return results
