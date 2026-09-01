"""Phase 4 adapters into the existing learning-session evidence ledger.

This module owns no chess rules and no mastery thresholds. It converts
server-owned review, guided-practice and current-schema application evidence
into ``personal_curriculum.LessonResult`` values, then appends their serialized
form to ``learning_sessions.events`` in shadow mode.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

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
    PIC_LESSON_ID,
    PIC_SKILL_ID,
)


REVIEW_LEARNING_ADAPTER_VERSION = "review_learning_adapter.v1"
SHADOW_LEARNING_SESSION_TYPE = "personalized_game_review_shadow"


def _stable_id(prefix: str, parts: Sequence[str]) -> str:
    encoded = "\x1f".join(parts).encode("utf-8")
    return f"{prefix}_{hashlib.sha256(encoded).hexdigest()[:24]}"


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
) -> List[LessonResult]:
    """Record only verified positive misses; absence is never application."""
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
        exact_destination = (
            int(observation.get("schema_version") or 0) >= 18
            and exact_fact.get("version")
            == "piece_safety.destination_safety_exact.v1"
            and exact_fact.get("fires") is True
        )
        if not (simple_hang or exact_destination):
            continue
        ply = int(observation.get("ply") or 0)
        if not game_id or ply < 1:
            continue
        results.append(
            LessonResult(
                content_kind=PIC_CONTENT_KIND,
                content_id=PIC_CONTENT_ID,
                canonical_source=PIC_CANONICAL_SOURCE,
                content_version=PIC_CONTENT_VERSION,
                attempt_kind=AttemptKind.APPLICATION,
                occurred_at=event_time,
                application_outcome=ApplicationOutcome.MISSED,
                source_type=EvidenceSourceType.ORGANIC_GAME,
                detector_quality_id=(
                    "gap:piece_safety:destination_safety_exact"
                    if exact_destination
                    else gap_quality_id("piece_safety", "simple_hang")
                ),
                source_event_id=f"move_observation:{game_id}:{ply}",
            )
        )
    return results


def build_shadow_learning_event(
    result: LessonResult,
    *,
    origin: str,
) -> Dict[str, Any]:
    """Wrap one canonical result without making it visible-mastery eligible."""
    if not isinstance(result, LessonResult):
        raise ContractViolation("result must be a LessonResult")
    if not origin:
        raise ContractViolation("learning event origin is required")
    payload = result.event_dict()
    source_event_id = str(result.source_event_id or "")
    if not source_event_id:
        raise ContractViolation("LessonResult lacks source_event_id")
    idempotency_key = _stable_id(
        "grl",
        (
            REVIEW_LEARNING_ADAPTER_VERSION,
            origin,
            source_event_id,
            result.attempt_kind.value,
            str(result.position_id or ""),
            result.application_outcome.value,
        ),
    )
    return {
        "event_id": idempotency_key,
        "idempotency_key": idempotency_key,
        "event_type": "lesson_result",
        "origin": origin,
        "occurred_at": result.occurred_at,
        "rollout_mode": "shadow",
        "adapter_version": REVIEW_LEARNING_ADAPTER_VERSION,
        "lesson_result": payload,
        "shadow_earned_state": payload.get("earned_state"),
        "evidence_eligible": False,
        "rejection_reason": "shadow_only_not_visible_mastery",
    }


def _deduplicate_events(events: Iterable[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    unique: Dict[str, Dict[str, Any]] = {}
    for event in events or []:
        key = str(event.get("idempotency_key") or "")
        if not key:
            raise ContractViolation("learning event lacks idempotency_key")
        unique.setdefault(key, dict(event))
    return list(unique.values())


def _session_id(user_id: str) -> str:
    if not user_id:
        raise ContractViolation("user_id is required")
    return _stable_id("grls", (user_id, PIC_SKILL_ID))


def _append_pipeline(
    *,
    user_id: str,
    events: Iterable[Mapping[str, Any]],
    now: datetime,
) -> tuple[str, List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Build one atomic append-if-key-missing Mongo update pipeline."""
    session_id = _session_id(user_id)
    additions = _deduplicate_events(events)
    existing = {"$ifNull": ["$events", []]}
    existing_keys = {
        "$map": {
            "input": existing,
            "as": "event",
            "in": "$$event.idempotency_key",
        }
    }
    missing = {
        "$filter": {
            "input": additions,
            "as": "candidate",
            "cond": {
                "$not": [
                    {
                        "$in": [
                            "$$candidate.idempotency_key",
                            existing_keys,
                        ]
                    }
                ]
            },
        }
    }
    pipeline = [
        {
            "$set": {
                "session_id": {"$ifNull": ["$session_id", session_id]},
                "user_id": {"$ifNull": ["$user_id", user_id]},
                "lesson_type": {
                    "$ifNull": ["$lesson_type", SHADOW_LEARNING_SESSION_TYPE]
                },
                "lesson_id": {"$ifNull": ["$lesson_id", PIC_LESSON_ID]},
                "skill_id": {"$ifNull": ["$skill_id", PIC_SKILL_ID]},
                "status": {"$ifNull": ["$status", "shadow"]},
                "rollout_mode": {"$ifNull": ["$rollout_mode", "shadow"]},
                "created_at": {"$ifNull": ["$created_at", now]},
                "events": {"$concatArrays": [existing, missing]},
                "updated_at": now,
            }
        }
    ]
    return session_id, additions, pipeline


async def store_shadow_lesson_results(
    collection: Any,
    *,
    user_id: str,
    events: Iterable[Mapping[str, Any]],
) -> Dict[str, Any]:
    """Atomically append new logical events to the existing ledger."""
    session_id, additions, pipeline = _append_pipeline(
        user_id=user_id,
        events=events,
        now=datetime.now(timezone.utc),
    )
    if additions:
        await collection.update_one(
            {"session_id": session_id}, pipeline, upsert=True
        )
    return {"session_id": session_id, "candidate_events": len(additions)}


def store_shadow_lesson_results_sync(
    collection: Any,
    *,
    user_id: str,
    events: Iterable[Mapping[str, Any]],
) -> Dict[str, Any]:
    """Synchronous worker equivalent of ``store_shadow_lesson_results``."""
    session_id, additions, pipeline = _append_pipeline(
        user_id=user_id,
        events=events,
        now=datetime.now(timezone.utc),
    )
    if additions:
        collection.update_one(
            {"session_id": session_id}, pipeline, upsert=True
        )
    return {"session_id": session_id, "candidate_events": len(additions)}
