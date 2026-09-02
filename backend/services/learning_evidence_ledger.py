"""One idempotent shadow writer for canonical ``LessonResult`` evidence.

The collection is still ``learning_sessions``.  This module owns only event
identity and atomic append mechanics; chess truth, content, grading and
mastery remain in their existing canonical owners.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from typing import Any, Dict, Iterable, List, Mapping, Sequence

from services.lesson_session_compatibility import LessonCompatibilityDescriptor
from services.personal_curriculum import ContractViolation, LessonResult


LEDGER_VERSION = "learning_evidence_ledger.v1"
# Preserve the already-stored Phase 4 event IDs.  Changing this value would
# duplicate the same logical review/game evidence during a replay.
EVENT_KEY_COMPATIBILITY_VERSION = "review_learning_adapter.v1"
SHADOW_LEARNING_SESSION_TYPE = "canonical_learning_shadow"
PIC_SHADOW_LEARNING_SESSION_TYPE = "personalized_game_review_shadow"
PIC_COMPATIBILITY_SKILL_ID = "piece_safety_simple_hang"


def _stable_id(prefix: str, parts: Sequence[str]) -> str:
    encoded = "\x1f".join(parts).encode("utf-8")
    return f"{prefix}_{hashlib.sha256(encoded).hexdigest()[:24]}"


def _skill_id_from_result(result: LessonResult) -> str:
    skill_id = str(result.skill_id or result.content_id or "").strip()
    if not skill_id:
        raise ContractViolation("LessonResult lacks canonical skill identity")
    return skill_id


def _compatibility(result: LessonResult) -> LessonCompatibilityDescriptor:
    return LessonCompatibilityDescriptor(
        lesson_kind=result.content_kind,
        lesson_id=result.content_id,
        content_revision=result.content_version,
        grader_version=str(result.grader_version or "not_supplied"),
        diagnostic_version=None,
        proof_contract_version=result.proof_contract_version,
        assigned_form=result.attempt_kind.value,
    )


def build_shadow_learning_event(
    result: LessonResult,
    *,
    origin: str,
) -> Dict[str, Any]:
    """Wrap one canonical result without making visible mastery eligible."""
    if not isinstance(result, LessonResult):
        raise ContractViolation("result must be a LessonResult")
    if not str(origin or "").strip():
        raise ContractViolation("learning event origin is required")
    payload = result.event_dict()
    source_event_id = str(result.source_event_id or "")
    if not source_event_id:
        raise ContractViolation("LessonResult lacks source_event_id")
    skill_id = _skill_id_from_result(result)
    # This reproduces the previous PIC-specific identity exactly while also
    # isolating other concepts by their canonical skill id.
    idempotency_key = _stable_id(
        "grl",
        (
            EVENT_KEY_COMPATIBILITY_VERSION,
            str(origin),
            source_event_id,
            result.attempt_kind.value,
            str(result.position_id or ""),
            result.application_outcome.value,
        ),
    )
    compatibility = _compatibility(result)
    return {
        "event_id": idempotency_key,
        "idempotency_key": idempotency_key,
        "event_type": "lesson_result",
        "origin": str(origin),
        "skill_id": skill_id,
        "occurred_at": result.occurred_at,
        "rollout_mode": "shadow",
        "adapter_version": EVENT_KEY_COMPATIBILITY_VERSION,
        "ledger_version": LEDGER_VERSION,
        "compatibility_fingerprint": compatibility.fingerprint,
        "compatibility": compatibility.semantic_payload(),
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


def _event_skill_id(event: Mapping[str, Any]) -> str:
    payload = event.get("lesson_result")
    lesson = payload.get("lesson") if isinstance(payload, Mapping) else None
    if (
        event.get("event_type") != "lesson_result"
        or event.get("rollout_mode") != "shadow"
        or event.get("evidence_eligible") is not False
        or not isinstance(payload, Mapping)
        or not isinstance(lesson, Mapping)
    ):
        raise ContractViolation("learning event is not canonical shadow evidence")
    if event.get("event_id") != event.get("idempotency_key"):
        raise ContractViolation("learning event identity fields disagree")
    result = LessonResult.from_event_dict(payload)
    nested_skill_id = str(result.skill_id or result.content_id or "").strip()
    outer_skill_id = str(event.get("skill_id") or "").strip()
    if outer_skill_id and outer_skill_id != nested_skill_id:
        raise ContractViolation("learning event skill identities disagree")
    if event.get("shadow_earned_state") != payload.get("earned_state"):
        raise ContractViolation("learning event shadow state disagrees with evidence")
    if not nested_skill_id:
        raise ContractViolation("learning event lacks canonical skill identity")
    return nested_skill_id


def _session_id(user_id: str, skill_id: str) -> str:
    if not str(user_id or "").strip():
        raise ContractViolation("user_id is required")
    if not str(skill_id or "").strip():
        raise ContractViolation("skill_id is required")
    return _stable_id("grls", (str(user_id), str(skill_id)))


def _append_pipeline(
    *,
    user_id: str,
    events: Iterable[Mapping[str, Any]],
    now: datetime,
) -> tuple[str, str, List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Build one atomic append-if-key-missing Mongo update pipeline."""
    additions = _deduplicate_events(events)
    skill_ids = {_event_skill_id(event) for event in additions}
    if len(skill_ids) != 1:
        raise ContractViolation("one ledger append must contain exactly one skill")
    skill_id = next(iter(skill_ids))
    session_id = _session_id(user_id, skill_id)
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
                    {"$in": ["$$candidate.idempotency_key", existing_keys]}
                ]
            },
        }
    }
    session_type = (
        PIC_SHADOW_LEARNING_SESSION_TYPE
        if skill_id == PIC_COMPATIBILITY_SKILL_ID
        else SHADOW_LEARNING_SESSION_TYPE
    )
    pipeline = [
        {
            "$set": {
                "session_id": {"$ifNull": ["$session_id", session_id]},
                "user_id": {"$ifNull": ["$user_id", str(user_id)]},
                "lesson_type": {"$ifNull": ["$lesson_type", session_type]},
                "lesson_id": {"$ifNull": ["$lesson_id", skill_id]},
                "skill_id": {"$ifNull": ["$skill_id", skill_id]},
                "status": {"$ifNull": ["$status", "shadow"]},
                "rollout_mode": {"$ifNull": ["$rollout_mode", "shadow"]},
                "ledger_version": {"$ifNull": ["$ledger_version", LEDGER_VERSION]},
                "created_at": {"$ifNull": ["$created_at", now]},
                "events": {"$concatArrays": [existing, missing]},
                "updated_at": now,
            }
        }
    ]
    return session_id, skill_id, additions, pipeline


async def store_shadow_lesson_results(
    collection: Any,
    *,
    user_id: str,
    events: Iterable[Mapping[str, Any]],
) -> Dict[str, Any]:
    """Atomically append new logical events to one existing ledger."""
    event_list = list(events or [])
    if not event_list:
        return {"session_id": None, "skill_id": None, "candidate_events": 0}
    session_id, skill_id, additions, pipeline = _append_pipeline(
        user_id=user_id,
        events=event_list,
        now=datetime.now(timezone.utc),
    )
    await collection.update_one({"session_id": session_id}, pipeline, upsert=True)
    return {
        "session_id": session_id,
        "skill_id": skill_id,
        "candidate_events": len(additions),
    }


def store_shadow_lesson_results_sync(
    collection: Any,
    *,
    user_id: str,
    events: Iterable[Mapping[str, Any]],
) -> Dict[str, Any]:
    """Synchronous worker equivalent of ``store_shadow_lesson_results``."""
    event_list = list(events or [])
    if not event_list:
        return {"session_id": None, "skill_id": None, "candidate_events": 0}
    session_id, skill_id, additions, pipeline = _append_pipeline(
        user_id=user_id,
        events=event_list,
        now=datetime.now(timezone.utc),
    )
    collection.update_one({"session_id": session_id}, pipeline, upsert=True)
    return {
        "session_id": session_id,
        "skill_id": skill_id,
        "candidate_events": len(additions),
    }


__all__ = [
    "EVENT_KEY_COMPATIBILITY_VERSION",
    "LEDGER_VERSION",
    "build_shadow_learning_event",
    "store_shadow_lesson_results",
    "store_shadow_lesson_results_sync",
]
