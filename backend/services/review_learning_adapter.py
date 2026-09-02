"""Phase 4 adapters into the existing learning-session evidence ledger.

This module owns no chess rules and no mastery thresholds. It converts
server-owned review, guided-practice and current-schema application evidence
into ``personal_curriculum.LessonResult`` values, then appends their serialized
form to ``learning_sessions.events`` in shadow mode.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable, List, Mapping

from services.detector_quality import gap_quality_id
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


def application_results_from_observations(
    *,
    game_id: str,
    observations: Iterable[Mapping[str, Any]],
    occurred_at: Any,
    include_handled: bool = False,
) -> List[LessonResult]:
    """Adapt explicit exact opportunities; absence is never application."""
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
            and exact_fact.get("version")
            == "piece_safety.destination_safety_exact.v1"
            and exact_fact.get("fires") is True
            and exact_fact.get("derivation_status") == "ok"
            and exact_fact.get("eligible") is True
            and exact_fact.get("outcome") == "miss"
        )
        legacy_exact_miss = (
            int(observation.get("schema_version") or 0) >= 18
            and exact_fact.get("version")
            == "piece_safety.destination_safety_exact.v1"
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
            and exact_fact.get("version")
            == "piece_safety.destination_safety_exact.v1"
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
                source_type=EvidenceSourceType.ORGANIC_GAME,
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
