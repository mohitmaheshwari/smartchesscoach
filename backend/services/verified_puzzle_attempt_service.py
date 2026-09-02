"""One server-owned write path for puzzle attempts and recovery credit."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Mapping, Optional, Tuple

from services.verified_puzzle_runtime import GRADER_VERSION, grade_resolved_puzzle


PUZZLE_ATTEMPT_SCHEMA_VERSION = "puzzle_attempt.v2"


def _stable_id(prefix: str, *parts: str) -> str:
    encoded = "\x1f".join(parts).encode("utf-8")
    return f"{prefix}_{hashlib.sha256(encoded).hexdigest()}"


def _credit_id(user_id: str, puzzle_id: str) -> str:
    return hashlib.sha256(f"{user_id}\0{puzzle_id}".encode("utf-8")).hexdigest()


def _submission_identity(value: Optional[str]) -> Tuple[str, bool]:
    """Return a canonical UUID and whether the client supplied it."""
    if value is None:
        return str(uuid.uuid4()), False
    try:
        return str(uuid.UUID(str(value).strip())), True
    except (AttributeError, TypeError, ValueError) as exc:
        raise ValueError("submission_id must be a UUID") from exc


def _attempt_id(
    *,
    user_id: str,
    puzzle_id: str,
    attempt_context: str,
    submission_id: str,
) -> str:
    return _stable_id(
        "pa2",
        PUZZLE_ATTEMPT_SCHEMA_VERSION,
        str(user_id),
        str(puzzle_id),
        str(attempt_context),
        str(submission_id),
    )


def _request_fingerprint(
    *,
    puzzle: Mapping[str, Any],
    played_uci: str,
) -> str:
    """Bind one client submission identity to one server-graded payload."""
    grading_snapshot = {
        "fen": puzzle.get("fen"),
        "best_move_uci": puzzle.get("best_move_uci"),
        "best_move_san": puzzle.get("best_move_san"),
        "source": puzzle.get("source"),
        "verified_admission": puzzle.get("verified_admission") or {},
    }
    encoded = json.dumps(
        grading_snapshot,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return _stable_id(
        "par",
        PUZZLE_ATTEMPT_SCHEMA_VERSION,
        GRADER_VERSION,
        str(played_uci),
        encoded,
    )


def _pic_identity(puzzle: Mapping[str, Any]) -> Optional[Dict[str, str]]:
    """Resolve only the already-supported PIC compatibility identity."""
    verdict = puzzle.get("verified_admission") or {}
    if (
        verdict.get("quality_id")
        != "gap:piece_safety:destination_safety_exact"
        and verdict.get("concept_id")
        not in {
            "piece_safety.destination_safety_exact",
            "piece_safety.simple_hang",
        }
    ):
        return None
    from services.personal_curriculum import (
        PIC_CANONICAL_SOURCE,
        PIC_CONTENT_ID,
        PIC_CONTENT_KIND,
        PIC_CONTENT_VERSION,
        PIC_SKILL_ID,
    )

    return {
        "content_kind": PIC_CONTENT_KIND,
        "content_id": PIC_CONTENT_ID,
        "canonical_source": PIC_CANONICAL_SOURCE,
        "content_version": PIC_CONTENT_VERSION,
        "skill_id": PIC_SKILL_ID,
    }


async def _rating_snapshot(db, user_id: str) -> Tuple[Dict[str, Any], Optional[str]]:
    try:
        from services.rating_resolver import resolve_coaching_rating

        return await resolve_coaching_rating(db, user_id), None
    except Exception:
        return {
            "rating": None,
            "source": "unavailable",
            "platform": None,
            "sample_games": 0,
            "as_of": None,
        }, "attempt_time_rating_unavailable"


async def _claim_recovery_credit(
    db,
    *,
    user_id: str,
    puzzle_id: str,
    weakness: Optional[str],
    attempt_id: str,
    now: datetime,
) -> Tuple[bool, bool]:
    """Return (belongs_to_this_attempt, newly_claimed_now)."""
    if not weakness:
        return False, False
    credit_id = _credit_id(user_id, puzzle_id)
    claim = await db.puzzle_recovery_credits.update_one(
        {"_id": credit_id},
        {"$setOnInsert": {
            "user_id": user_id,
            "puzzle_id": puzzle_id,
            "weakness_type": weakness,
            "source_attempt_id": attempt_id,
            "created_at": now.isoformat(),
        }},
        upsert=True,
    )
    if claim.upserted_id is not None:
        return True, True
    existing = await db.puzzle_recovery_credits.find_one(
        {"_id": credit_id}, {"_id": 0, "source_attempt_id": 1}
    )
    return bool(existing and existing.get("source_attempt_id") == attempt_id), False


async def _store_attempt_once(collection, document: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
    """Use Mongo's unique `_id` index as the concurrency boundary."""
    inserted = False
    try:
        result = await collection.update_one(
            {"_id": document["_id"]},
            {"$setOnInsert": document},
            upsert=True,
        )
        inserted = result.upserted_id is not None
    except Exception as exc:
        # A concurrent identical upsert can lose the race on `_id`.  Only a
        # real duplicate-key result is safe to reinterpret as a retry.
        try:
            from pymongo.errors import DuplicateKeyError
        except Exception:  # pragma: no cover - pymongo is a runtime dependency
            DuplicateKeyError = ()  # type: ignore[assignment]
        if not isinstance(exc, DuplicateKeyError):
            raise
    if inserted:
        return True, document
    stored = await collection.find_one({"_id": document["_id"]})
    if not stored:
        raise RuntimeError("attempt upsert did not persist a document")
    return False, dict(stored)


async def _emit_shadow_learning_result(
    db,
    *,
    user_id: str,
    attempt: Mapping[str, Any],
    puzzle: Mapping[str, Any],
    grade: Mapping[str, Any],
    identity: Mapping[str, str],
) -> None:
    from services.learning_evidence_ledger import (
        build_shadow_learning_event,
        store_shadow_lesson_results,
    )
    from services.personal_curriculum import (
        AttemptKind,
        EvidenceSourceType,
        LessonResult,
    )

    rating = attempt.get("rating") or {}
    admission = attempt.get("admission") or {}
    measurement = attempt.get("measurement") or {}
    limitations = tuple(measurement.get("evidence_limitations") or ())
    result = LessonResult(
        content_kind=identity["content_kind"],
        content_id=identity["content_id"],
        canonical_source=identity["canonical_source"],
        content_version=identity["content_version"],
        skill_id=identity["skill_id"],
        primary_skill_id=identity["skill_id"],
        attempt_kind=AttemptKind.INDEPENDENT,
        occurred_at=datetime.fromisoformat(str(attempt["created_at"])),
        correct=bool(grade.get("correct")),
        position_id=str(attempt["puzzle_id"]),
        board_verified=True,
        distinct_position=False,
        source_type=EvidenceSourceType.MIXED_DRILL,
        detector_quality_id=admission.get("quality_id"),
        detector_version=admission.get("detector_version"),
        grader_version=GRADER_VERSION,
        evidence_owner=str(admission.get("source_kind") or "verified_puzzle"),
        evidence_ref=admission.get("source_fingerprint"),
        source_event_id=f"puzzle_attempt:{attempt['attempt_id']}",
        attempt_id=str(attempt["attempt_id"]),
        response_move_uci=str(attempt["played_uci"]),
        response_time_ms=attempt.get("time_taken_ms"),
        first_answer=True,
        retry_index=0,
        assistance_measured=False,
        evidence_complete=False,
        evidence_limitations=limitations,
        rating=rating.get("value"),
        rating_source=rating.get("source"),
        rating_platform=rating.get("platform"),
        rating_sample_games=rating.get("sample_games"),
        rating_as_of=rating.get("as_of"),
        admission_version=admission.get("version"),
        admission_fingerprint=admission.get("verdict_fingerprint"),
        proof_contract_version=admission.get("version"),
    )
    event = build_shadow_learning_event(result, origin="verified_puzzle_attempt")
    await store_shadow_lesson_results(
        db.learning_sessions,
        user_id=user_id,
        events=(event,),
    )


async def record_verified_puzzle_attempt(
    db,
    *,
    user_id: str,
    puzzle_id: str,
    puzzle: Mapping[str, Any],
    played_uci: str,
    time_taken_ms: Optional[int] = None,
    moves_tried: Optional[list] = None,
    attempt_context: str = "training",
    submission_id: Optional[str] = None,
) -> Dict:
    """Grade once on the server, log each logical try once, credit once."""
    if not str(user_id or "").strip() or not str(puzzle_id or "").strip():
        return {"quality": "invalid", "feedback": "Attempt target is invalid."}
    if not str(attempt_context or "").strip():
        return {"quality": "invalid", "feedback": "Attempt context is invalid."}
    if time_taken_ms is not None and (
        isinstance(time_taken_ms, bool)
        or not isinstance(time_taken_ms, int)
        or time_taken_ms < 0
    ):
        return {"quality": "invalid", "feedback": "Attempt time is invalid."}
    grade = grade_resolved_puzzle(puzzle, played_uci)
    if grade.get("quality") == "invalid":
        return grade

    now = datetime.now(timezone.utc)
    correct = bool(grade.get("correct"))
    try:
        canonical_submission_id, idempotency_proven = _submission_identity(
            submission_id
        )
    except ValueError:
        return {"quality": "invalid", "feedback": "Attempt identity is invalid."}
    attempt_id = _attempt_id(
        user_id=user_id,
        puzzle_id=puzzle_id,
        attempt_context=attempt_context,
        submission_id=canonical_submission_id,
    )
    request_fingerprint = _request_fingerprint(
        puzzle=puzzle,
        played_uci=played_uci,
    )
    rating, rating_limitation = await _rating_snapshot(db, user_id)
    verdict = dict(puzzle.get("verified_admission") or {})
    identity = _pic_identity(puzzle)
    limitations = ["assistance_and_reveal_state_not_measured"]
    if not idempotency_proven:
        limitations.append("client_submission_identity_not_supplied")
    if rating_limitation:
        limitations.append(rating_limitation)
    if identity is None:
        limitations.append("canonical_lesson_identity_unresolved")
    # Only a BROAD/SPECIFIC admission supplies this field. Generic puzzles are
    # still valid calculation practice, but their unverified legacy label must
    # never alter named recovery/decay state.
    weakness = grade.get("recovery_weakness")
    attempt_document = {
        "_id": attempt_id,
        "schema_version": PUZZLE_ATTEMPT_SCHEMA_VERSION,
        "attempt_id": attempt_id,
        "submission_id": canonical_submission_id,
        "request_fingerprint": request_fingerprint,
        "idempotency_proven": idempotency_proven,
        "user_id": user_id,
        "puzzle_id": puzzle_id,
        "correct": correct,
        "quality": grade.get("quality"),
        "played_uci": played_uci,
        "time_taken_ms": time_taken_ms,
        # A client cannot certify its own unseen move history. This request
        # proves exactly the one move the server graded.
        "moves_tried": [played_uci],
        "attempt_context": attempt_context,
        "weakness_type": weakness,
        "recovery_credit_awarded": False,
        "created_at": now.isoformat(),
        "rating": {
            "value": rating.get("rating"),
            "source": rating.get("source"),
            "platform": rating.get("platform"),
            "sample_games": rating.get("sample_games"),
            "as_of": rating.get("as_of"),
        },
        "admission": {
            "version": verdict.get("admission_version"),
            "verdict_fingerprint": verdict.get("verdict_fingerprint"),
            "status": verdict.get("status"),
            "quality_id": verdict.get("quality_id"),
            "quality_grade": verdict.get("quality_grade"),
            "concept_id": verdict.get("concept_id"),
            "detector_id": verdict.get("detector_id"),
            "detector_version": verdict.get("detector_version"),
            "verifier_id": verdict.get("verifier_id"),
            "verifier_version": verdict.get("verifier_version"),
            "source_kind": verdict.get("source_kind"),
            "source_fingerprint": verdict.get("source_fingerprint"),
        },
        "grader_version": GRADER_VERSION,
        "grade_result": dict(grade),
        "measurement": {
            "first_answer": True,
            "retry_index": 0,
            "response_time_source": (
                "client_reported" if time_taken_ms is not None else "not_measured"
            ),
            "assistance": "not_measured",
            "answer_revealed_before_attempt": "not_measured",
            "measurement_status": "partial",
            "evidence_complete": False,
            "evidence_limitations": limitations,
        },
    }
    inserted, stored = await _store_attempt_once(
        db.puzzle_attempts, attempt_document
    )
    if stored.get("request_fingerprint") != request_fingerprint:
        return {
            "quality": "invalid",
            "feedback": "Attempt identity was already used for a different answer.",
            "attempt_id": attempt_id,
            "duplicate": True,
            "idempotency_proven": idempotency_proven,
            "measurement_status": "partial",
            "shadow_event_emitted": False,
            "recovery_credit_awarded": False,
        }

    stored_grade = dict(stored.get("grade_result") or grade)
    stored_credit = bool(stored.get("recovery_credit_awarded"))
    credit_claimed_now = False
    if not stored_credit and stored.get("correct") and stored.get("weakness_type"):
        stored_credit, credit_claimed_now = await _claim_recovery_credit(
            db,
            user_id=user_id,
            puzzle_id=puzzle_id,
            weakness=stored.get("weakness_type"),
            attempt_id=attempt_id,
            now=now,
        )
        if stored_credit:
            await db.puzzle_attempts.update_one(
                {"_id": attempt_id},
                {"$set": {"recovery_credit_awarded": True}},
            )
            stored["recovery_credit_awarded"] = True

    event_emitted = False
    if idempotency_proven and identity is not None:
        from services.concept_contract_registry import (
            complete_coaching_system_enabled,
        )

        if complete_coaching_system_enabled():
            await _emit_shadow_learning_result(
                db,
                user_id=user_id,
                attempt=stored,
                puzzle=puzzle,
                grade=stored_grade,
                identity=identity,
            )
            event_emitted = True

    return {
        **stored_grade,
        "attempt_id": attempt_id,
        "duplicate": not inserted,
        "idempotency_proven": idempotency_proven,
        "measurement_status": "partial",
        "shadow_event_emitted": event_emitted,
        "recovery_credit_awarded": stored_credit,
        "recovery_credit_claimed_now": credit_claimed_now,
    }
