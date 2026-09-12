"""Immutable Phase 8 baselines and server-owned journey projections."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from typing import Any, Dict, Iterable, Optional

import chess

from services.complete_coaching_access import (
    BASELINE_COLLECTION,
    BASELINE_VERSION,
    TARGET_COLLECTION,
    TARGET_LOCK_ID,
)
from services.destination_safety_detector import FACT_VERSION, QUALITY_ID
from services.detector_quality import QualitySurface, is_authorized
from services.game_decryption_v5_service import V5_COACHING_VERSION
from services.game_review_shadow_runtime import SHADOW_RUNTIME_VERSION


JOURNEY_COLLECTION = "complete_coaching_journeys"
JOURNEY_VERSION = "complete_coaching_journey.v1"
FOCUS_KIND = "piece_safety/destination_safety_exact"
REACH_STEPS = frozenset({
    "home_focus_served",
    "lesson_opened",
    "lesson_completed",
    "review_served",
    "progress_verdict_served",
})


def _utc(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _stable_id(*parts: object) -> str:
    payload = "\x1f".join(str(part or "") for part in parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


async def _pre_enrollment_games(
    db,
    user_id: str,
    *,
    cutoff: datetime,
    limit: Optional[int] = 3,
) -> list[Dict[str, Any]]:
    rows = await db.games.find(
        {"user_id": user_id, "is_analyzed": True},
        {"_id": 0, "game_id": 1, "date_played": 1, "analyzed_at": 1},
    ).sort("date_played", -1).to_list(length=None)
    eligible = []
    for row in rows:
        played = _utc(row.get("date_played"))
        if played is None or played >= cutoff:
            continue
        eligible.append(row)
        if limit is not None and len(eligible) == limit:
            break
    return eligible


def _current_review_plan(plan: Any, source_v5_version: Any) -> bool:
    if not isinstance(plan, dict):
        return False
    try:
        same_caption_version = int(plan.get("source_v5_version") or 0) == int(
            source_v5_version or 0
        )
    except (TypeError, ValueError):
        return False
    return bool(
        plan.get("schema_version") == "personalized_game_review.shadow_plan.v1"
        and same_caption_version
        and str(plan.get("planner_version") or "").strip()
        and (
            plan.get("plan") is None
            or isinstance(plan.get("plan"), dict)
        )
    )


async def _baseline_review_coverage(
    db,
    user_id: str,
    *,
    cutoff: datetime,
) -> Dict[str, int]:
    games = await _pre_enrollment_games(
        db,
        user_id,
        cutoff=cutoff,
        limit=None,
    )
    game_ids = [
        str(row.get("game_id"))
        for row in games
        if row.get("game_id")
    ]
    counts = {
        "analyzed_games": len(game_ids),
        "analysis_records": 0,
        "current_v5_reviews": 0,
        "stale_or_missing_v5_reviews": 0,
        "current_teaching_plans": 0,
        "stale_or_missing_teaching_plans": 0,
    }
    if not game_ids:
        return counts
    rows = await db.game_analyses.find(
        {"game_id": {"$in": game_ids}},
        {
            "_id": 0,
            "game_id": 1,
            "decryption_v5_data": 1,
            "decryption_v5_version": 1,
            "game_teaching_plan": 1,
        },
    ).to_list(length=None)
    counts["analysis_records"] = len(rows)
    by_game = {
        str(row.get("game_id")): row
        for row in rows
        if row.get("game_id")
    }
    for game_id in game_ids:
        analysis = by_game.get(game_id)
        if not analysis:
            counts["stale_or_missing_v5_reviews"] += 1
            counts["stale_or_missing_teaching_plans"] += 1
            continue
        try:
            current_v5 = (
                int(analysis.get("decryption_v5_version") or 0)
                >= V5_COACHING_VERSION
                and isinstance(analysis.get("decryption_v5_data"), list)
            )
        except (TypeError, ValueError):
            current_v5 = False
        if current_v5:
            counts["current_v5_reviews"] += 1
        else:
            counts["stale_or_missing_v5_reviews"] += 1
        if _current_review_plan(
            analysis.get("game_teaching_plan"),
            analysis.get("decryption_v5_version"),
        ):
            counts["current_teaching_plans"] += 1
        else:
            counts["stale_or_missing_teaching_plans"] += 1
    return counts


async def _baseline_observation_summary(
    db,
    user_id: str,
    game_ids: Iterable[str],
) -> Dict[str, Any]:
    ids = tuple(str(value) for value in game_ids if value)
    if not ids:
        return {
            "decisions": 0,
            "handled": 0,
            "missed": 0,
            "unclear": 0,
            "did_not_occur": 0,
            "observation_ids": [],
        }
    rows = await db.move_observations.find(
        {
            "user_id": user_id,
            "game_id": {"$in": list(ids)},
            "schema_version": {"$gte": 18},
            "destination_safety_exact.version": FACT_VERSION,
        },
        {
            "_id": 1,
            "destination_safety_exact": 1,
        },
    ).to_list(length=None)
    summary = {
        "decisions": 0,
        "handled": 0,
        "missed": 0,
        "unclear": 0,
        "did_not_occur": 0,
        "observation_ids": [],
    }
    for row in rows:
        fact = row.get("destination_safety_exact") or {}
        summary["observation_ids"].append(str(row.get("_id")))
        if fact.get("derivation_status") != "ok":
            summary["unclear"] += 1
        elif fact.get("eligible") is not True:
            summary["did_not_occur"] += 1
        elif fact.get("outcome") == "miss":
            summary["decisions"] += 1
            summary["missed"] += 1
        elif fact.get("outcome") == "handled":
            summary["decisions"] += 1
            summary["handled"] += 1
        else:
            summary["unclear"] += 1
    summary["observation_ids"].sort()
    return summary


async def build_pre_enrollment_baseline(
    db,
    user_id: str,
    *,
    cutoff: datetime,
    source_commit: str,
    allow_admin: bool = False,
) -> Dict[str, Any]:
    """`allow_admin` is an explicit single-account escape hatch.

    Admin accounts are kept out of the real-user cohort so they cannot skew
    the pilot's reach and transfer metrics. That rule belongs to MEASUREMENT.
    Applied to PROVISIONING it also denied the validation account the baseline
    that gates its own access, so the one account used to check the product
    could not see it -- observed 2026-09-12 as
    /api/game-review/recommendation returning reason="baseline_missing" while
    41 pilot users were correctly provisioned.

    Defaults to False, so every existing caller and the --all cohort path are
    unchanged. The caller that passes True must name a single account.
    """
    if cutoff.tzinfo is None:
        raise ValueError("baseline cutoff must be timezone-aware")
    if not source_commit:
        raise ValueError("source commit is required")
    if not is_authorized(QUALITY_ID, QualitySurface.PLAN):
        raise ValueError("destination-safety detector is not Plan-authorized")
    target = await db[TARGET_COLLECTION].find_one(
        {"_id": TARGET_LOCK_ID, "status": "locked"},
        {"_id": 1, "contract_version": 1, "eligible_denominator": 1},
    )
    if not target:
        raise ValueError("Phase 8 target is not locked")
    user = await db.users.find_one(
        {"user_id": user_id},
        {"_id": 0, "user_id": 1, "role": 1, "feature_flags": 1},
    )
    if not user:
        raise ValueError("user does not exist")
    if (
        not allow_admin
        and str(user.get("role") or "user").lower() in {"admin", "super_admin"}
    ):
        raise ValueError("admin accounts cannot enter the real-user baseline")
    enrollment = ((user.get("feature_flags") or {}).get(
        "personalized_game_review_coach"
    ) or {})
    if enrollment.get("phase8_enrolled_at"):
        raise ValueError("baseline cutoff is after Phase 8 enrollment")

    focus = await db.user_active_focus.find_one({
        "user_id": user_id,
        "status": "active",
        "focus_kind": FOCUS_KIND,
        "detector_quality_id": QUALITY_ID,
    })
    if not focus:
        raise ValueError("current exact Plan focus is required")
    games = await _pre_enrollment_games(db, user_id, cutoff=cutoff)
    game_ids = [str(row.get("game_id")) for row in games if row.get("game_id")]
    summary = await _baseline_observation_summary(db, user_id, game_ids)
    review_coverage = await _baseline_review_coverage(
        db,
        user_id,
        cutoff=cutoff,
    )
    from services.concept_mastery_service import get_pic_mastery_projection

    learner_state = await get_pic_mastery_projection(
        db,
        user_id,
        diagnosed=summary["missed"] > 0,
    )
    focus_id = str(focus.get("_id"))
    baseline_id = _stable_id(
        BASELINE_VERSION,
        TARGET_LOCK_ID,
        user_id,
        focus_id,
    )
    status = (
        "captured"
        if len(game_ids) == 3 and summary["decisions"] > 0
        else "insufficient_pre_period"
    )
    return {
        "_id": baseline_id,
        "baseline_version": BASELINE_VERSION,
        "target_lock_id": TARGET_LOCK_ID,
        "target_contract_version": target.get("contract_version"),
        "status": status,
        "created_at": datetime.now(timezone.utc),
        "cutoff_at": cutoff,
        "source_commit": source_commit,
        "user_id": user_id,
        "focus_id": focus_id,
        "instruction_id": focus.get("instruction_id"),
        "instruction_version": focus.get("instruction_version"),
        "focus_kind": focus.get("focus_kind"),
        "detector_quality_id": QUALITY_ID,
        "proof_version": FACT_VERSION,
        "pre_period": {
            "game_ids": game_ids,
            "games": len(game_ids),
            "opportunities": {
                key: summary[key]
                for key in (
                    "decisions",
                    "handled",
                    "missed",
                    "unclear",
                    "did_not_occur",
                )
            },
            "observation_ids": summary["observation_ids"],
        },
        "coverage_at_cutoff": {
            **review_coverage,
            "review_schema_version": V5_COACHING_VERSION,
            "review_plan_runtime": SHADOW_RUNTIME_VERSION,
        },
        "learner_state": learner_state,
    }


def same_immutable_baseline(
    existing: Dict[str, Any],
    proposed: Dict[str, Any],
) -> bool:
    keys = (
        "baseline_version",
        "target_lock_id",
        "target_contract_version",
        "status",
        "cutoff_at",
        "source_commit",
        "user_id",
        "focus_id",
        "instruction_id",
        "instruction_version",
        "focus_kind",
        "detector_quality_id",
        "proof_version",
        "pre_period",
        "coverage_at_cutoff",
        "learner_state",
    )
    return all(
        _comparable(existing.get(key)) == _comparable(proposed.get(key))
        for key in keys
    )


def _comparable(value: Any) -> Any:
    """Normalise a stored value so it can be compared with a freshly built one.

    MongoDB returns BSON dates as NAIVE datetimes, while a newly built
    baseline carries timezone-aware ones. Comparing them with == made every
    stored baseline read as an "immutable baseline conflict" the moment it
    was re-checked -- a healthy, byte-identical baseline reported as
    corruption. Only the tzinfo differed.
    """
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    if isinstance(value, dict):
        return {key: _comparable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_comparable(item) for item in value]
    return value


async def record_phase8_reach_event(
    db,
    user_id: str,
    *,
    step: str,
    source_id: str,
    metadata: Optional[Dict[str, Any]] = None,
    occurred_at: Optional[datetime] = None,
) -> bool:
    """Record product reach only; never impersonate lesson/mastery evidence."""
    if step not in REACH_STEPS:
        raise ValueError("unknown Phase 8 reach step")
    if not str(source_id or "").strip():
        raise ValueError("source_id is required")
    from services.complete_coaching_access import get_complete_coaching_access

    access = await get_complete_coaching_access(db, user_id)
    if not access.enabled:
        return False
    baseline = await db[BASELINE_COLLECTION].find_one(
        {"_id": access.baseline_id},
        {"_id": 1, "focus_id": 1, "instruction_id": 1},
    )
    if not baseline:
        return False
    now = occurred_at or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("reach event timestamp must be timezone-aware")
    event_id = _stable_id(
        JOURNEY_VERSION,
        user_id,
        access.baseline_id,
        step,
        source_id,
    )
    document = {
        "_id": event_id,
        "schema_version": JOURNEY_VERSION,
        "user_id": user_id,
        "baseline_id": access.baseline_id,
        "target_lock_id": TARGET_LOCK_ID,
        "focus_id": baseline.get("focus_id"),
        "instruction_id": baseline.get("instruction_id"),
        "step": step,
        "source_id": source_id,
        "occurred_at": now,
        "metadata": dict(metadata or {}),
    }
    result = await db[JOURNEY_COLLECTION].update_one(
        {"_id": event_id},
        {"$setOnInsert": document},
        upsert=True,
    )
    return bool(result.upserted_id)


async def _verified_lesson_and_application_evidence(
    db,
    user_id: str,
    *,
    enrollment_at: datetime,
) -> Dict[str, Any]:
    from services.personal_curriculum import (
        ApplicationOutcome,
        AttemptKind,
        EvidenceSourceType,
        LessonResult,
        PIC_SKILL_ID,
    )

    result = {
        "server_graded_first_attempt": False,
        "lesson_evidence_events": 0,
        "later_application_events": 0,
        "later_handled": 0,
        "later_missed": 0,
        "coached_application_events": 0,
        "coached_handled": 0,
        "coached_missed": 0,
        "assisted_practice_events": 0,
        "unassisted_checkpoint_events": 0,
        "ordinary_coach_play_events": 0,
        "coached_modes": {
            "practice_assisted": {
                "opportunities": 0,
                "handled": 0,
                "missed": 0,
            },
            "checkpoint_unassisted": {
                "opportunities": 0,
                "handled": 0,
                "missed": 0,
            },
            "just_play": {
                "opportunities": 0,
                "handled": 0,
                "missed": 0,
            },
        },
        "server_grade_times": [],
        "application_times": [],
        "application_refs": [],
    }
    sessions = db.learning_sessions.find(
        {"user_id": user_id, "skill_id": PIC_SKILL_ID},
        {"_id": 0, "events": 1},
    )
    async for session in sessions:
        for event in session.get("events") or []:
            payload = event.get("lesson_result") or {}
            try:
                lesson_result = LessonResult.from_event_dict(payload)
            except (TypeError, ValueError):
                continue
            occurred = lesson_result.occurred_at.astimezone(timezone.utc)
            if occurred < enrollment_at:
                continue
            if lesson_result.attempt_kind != AttemptKind.APPLICATION:
                result["lesson_evidence_events"] += 1
                if (
                    lesson_result.first_answer is True
                    and lesson_result.board_verified
                    and lesson_result.attempt_id
                ):
                    result["server_graded_first_attempt"] = True
                    result["server_grade_times"].append(occurred)
                continue
            if (
                lesson_result.detector_quality_id != QUALITY_ID
                or not lesson_result.evidence_complete
            ):
                continue
            if lesson_result.source_type == EvidenceSourceType.COACHED_APPLICATION:
                result["coached_application_events"] += 1
                origin = str(event.get("origin") or "")
                if origin == "pwc_practice_assisted_observation":
                    mode = "practice_assisted"
                    result["assisted_practice_events"] += 1
                elif origin == "pwc_checkpoint_unassisted_observation":
                    mode = "checkpoint_unassisted"
                    result["unassisted_checkpoint_events"] += 1
                else:
                    mode = "just_play"
                    result["ordinary_coach_play_events"] += 1
                bucket = result["coached_modes"][mode]
                bucket["opportunities"] += 1
                if lesson_result.application_outcome == ApplicationOutcome.APPLIED:
                    result["coached_handled"] += 1
                    bucket["handled"] += 1
                elif lesson_result.application_outcome == ApplicationOutcome.MISSED:
                    result["coached_missed"] += 1
                    bucket["missed"] += 1
                continue
            if lesson_result.source_type != EvidenceSourceType.ORGANIC_GAME:
                continue
            result["later_application_events"] += 1
            result["application_times"].append(occurred)
            source_ref = str(lesson_result.source_event_id or "")
            if source_ref.startswith("move_observation:"):
                source_ref = source_ref[len("move_observation:"):]
                game_id, separator, ply_text = source_ref.rpartition(":")
                try:
                    ply = int(ply_text) if separator else 0
                except (TypeError, ValueError):
                    ply = 0
                if game_id and ply > 0:
                    result["application_refs"].append({
                        "game_id": game_id,
                        "ply": ply,
                        "outcome": lesson_result.application_outcome.value,
                        "occurred_at": occurred,
                    })
            if lesson_result.application_outcome == ApplicationOutcome.APPLIED:
                result["later_handled"] += 1
            elif lesson_result.application_outcome == ApplicationOutcome.MISSED:
                result["later_missed"] += 1
    return result


def _public_progress_observation(
    row: Dict[str, Any],
    *,
    expected_outcome: str,
    game: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """Project one exact owned observation without exposing detector internals."""
    fact = row.get("destination_safety_exact") or {}
    if (
        int(row.get("schema_version") or 0) < 18
        or fact.get("version") != FACT_VERSION
        or fact.get("quality_id") != QUALITY_ID
        or fact.get("derivation_status") != "ok"
        or fact.get("eligible") is not True
        or fact.get("outcome") != expected_outcome
        or (expected_outcome == "miss" and fact.get("fires") is not True)
        or (expected_outcome == "handled" and fact.get("fires") is True)
    ):
        return None

    fen = str(row.get("fen_before") or "").strip()
    move_uci = str(row.get("move_uci") or "").strip().lower()
    try:
        board = chess.Board(fen)
        move = chess.Move.from_uci(move_uci)
    except (ValueError, TypeError):
        return None
    if move not in board.legal_moves:
        return None
    piece = board.piece_at(move.from_square)
    destination = chess.square_name(move.to_square)
    moved_piece = chess.piece_name(piece.piece_type) if piece else ""
    if (
        not piece
        or fact.get("moved_piece") != moved_piece
        or fact.get("destination") != destination
    ):
        return None

    played_at = _utc((game or {}).get("date_played"))
    return {
        "game_id": str(row.get("game_id") or ""),
        "ply": int(row.get("ply") or 0),
        "move_number": int(
            row.get("move_number") or ((int(row.get("ply") or 1) + 1) // 2)
        ),
        "fen": board.fen(),
        "move_uci": move.uci(),
        "move_san": board.san(move),
        "piece": moved_piece,
        "destination": destination,
        "outcome": expected_outcome,
        "opponent": str((game or {}).get("opponent_name") or "Opponent"),
        "played_at": played_at.isoformat() if played_at else None,
    }


async def _progress_evidence_examples(
    db,
    user_id: str,
    *,
    baseline: Dict[str, Any],
    evidence: Dict[str, Any],
) -> Dict[str, Optional[Dict[str, Any]]]:
    """Resolve one baseline miss and one later exact application, fail closed."""
    empty = {"before": None, "recent": None}
    if not is_authorized(QUALITY_ID, QualitySurface.PLAN):
        return empty

    baseline_games = tuple(
        str(game_id)
        for game_id in (
            (baseline.get("pre_period") or {}).get("game_ids") or []
        )
        if game_id
    )
    application_refs = sorted(
        evidence.get("application_refs") or [],
        key=lambda item: (
            _utc(item.get("occurred_at"))
            or datetime.min.replace(tzinfo=timezone.utc)
        ),
        reverse=True,
    )
    application_refs = [
        item
        for item in application_refs
        if item.get("outcome") in {"applied", "missed"}
    ]

    game_ids = set(baseline_games)
    game_ids.update(str(item.get("game_id") or "") for item in application_refs)
    game_ids.discard("")
    games = (
        await db.games.find(
            {"user_id": user_id, "game_id": {"$in": sorted(game_ids)}},
            {"_id": 0, "game_id": 1, "opponent_name": 1, "date_played": 1},
        ).to_list(length=None)
        if game_ids
        else []
    )
    games_by_id = {
        str(game.get("game_id")): game
        for game in games
        if game.get("game_id")
    }

    before = None
    if baseline_games:
        before_rows = await db.move_observations.find(
            {
                "user_id": user_id,
                "game_id": {"$in": list(baseline_games)},
                "schema_version": {"$gte": 18},
                "destination_safety_exact.version": FACT_VERSION,
                "destination_safety_exact.quality_id": QUALITY_ID,
                "destination_safety_exact.outcome": "miss",
                "destination_safety_exact.fires": True,
            },
            {
                "_id": 0,
                "game_id": 1,
                "ply": 1,
                "move_number": 1,
                "fen_before": 1,
                "move_uci": 1,
                "move_san": 1,
                "schema_version": 1,
                "destination_safety_exact": 1,
            },
        ).to_list(length=None)
        before_rows.sort(
            key=lambda row: (
                baseline_games.index(str(row.get("game_id")))
                if str(row.get("game_id")) in baseline_games
                else len(baseline_games),
                -int(row.get("ply") or 0),
            )
        )
        for row in before_rows:
            before = _public_progress_observation(
                row,
                expected_outcome="miss",
                game=games_by_id.get(str(row.get("game_id") or "")),
            )
            if before:
                break

    recent = None
    for item in application_refs:
        outcome = "handled" if item.get("outcome") == "applied" else "miss"
        row = await db.move_observations.find_one(
            {
                "user_id": user_id,
                "game_id": str(item.get("game_id") or ""),
                "ply": int(item.get("ply") or 0),
                "schema_version": {"$gte": 18},
                "destination_safety_exact.version": FACT_VERSION,
                "destination_safety_exact.quality_id": QUALITY_ID,
            },
            {
                "_id": 0,
                "game_id": 1,
                "ply": 1,
                "move_number": 1,
                "fen_before": 1,
                "move_uci": 1,
                "move_san": 1,
                "schema_version": 1,
                "destination_safety_exact": 1,
            },
        )
        if not row:
            continue
        recent = _public_progress_observation(
            row,
            expected_outcome=outcome,
            game=games_by_id.get(str(row.get("game_id") or "")),
        )
        if recent:
            break

    return {"before": before, "recent": recent}


async def build_phase8_journey_projection(
    db,
    user_id: str,
) -> Dict[str, Any]:
    """Reduce server facts into reach plus practice-vs-transfer truth."""
    from services.complete_coaching_access import get_complete_coaching_access

    access = await get_complete_coaching_access(db, user_id)
    if not access.enabled:
        return {
            "schema_version": JOURNEY_VERSION,
            "enabled": False,
            "paused": access.paused,
            "reason": access.reason,
            **({"message": access.public_dict().get("message")} if access.paused else {}),
        }
    baseline = await db[BASELINE_COLLECTION].find_one(
        {"_id": access.baseline_id},
        {"_id": 0},
    )
    user = await db.users.find_one(
        {"user_id": user_id},
        {"_id": 0, "feature_flags.personalized_game_review_coach": 1},
    )
    enrollment = ((user or {}).get("feature_flags") or {}).get(
        "personalized_game_review_coach"
    ) or {}
    enrollment_at = _utc(enrollment.get("phase8_enrolled_at"))
    if not baseline or not enrollment_at:
        return {
            "schema_version": JOURNEY_VERSION,
            "enabled": False,
            "paused": False,
            "reason": "enrollment_provenance_missing",
        }

    events = await db[JOURNEY_COLLECTION].find(
        {"user_id": user_id, "baseline_id": access.baseline_id},
        {"_id": 0, "step": 1, "source_id": 1, "occurred_at": 1, "metadata": 1},
    ).to_list(length=None)
    reached = {str(event.get("step")) for event in events}
    evidence = await _verified_lesson_and_application_evidence(
        db,
        user_id,
        enrollment_at=enrollment_at,
    )
    from services.concept_mastery_service import get_pic_mastery_projection

    learner = await get_pic_mastery_projection(db, user_id, diagnosed=True)
    evidence_examples = await _progress_evidence_examples(
        db,
        user_id,
        baseline=baseline,
        evidence=evidence,
    )
    if baseline.get("status") != "captured":
        verdict = "insufficient_evidence"
        transfer_message = (
            "I am tracking this now, but I did not have a comparable "
            "decision in your earlier games, so I cannot judge change yet."
        )
    elif evidence["later_application_events"] <= 0:
        verdict = "insufficient_evidence"
        transfer_message = (
            "Practice is recorded. I need to see the same decision in a later "
            "unassisted game before I can judge improvement."
        )
    elif evidence["later_missed"] > 0:
        verdict = "still_recurring"
        transfer_message = (
            "The same decision appeared again in a later game, so this stays "
            "in your plan."
        )
    elif learner.get("state") == "proven_in_games":
        verdict = "improved"
        transfer_message = (
            "You have now handled this decision in later unassisted games."
        )
    else:
        verdict = "insufficient_evidence"
        transfer_message = (
            "I saw a later handled decision, but there is not enough verified "
            "evidence yet to call this improved."
        )
    transfer_evidence_identity = _stable_id(
        JOURNEY_VERSION,
        access.baseline_id,
        verdict,
        evidence["later_application_events"],
        evidence["later_handled"],
        evidence["later_missed"],
        learner.get("state"),
        learner.get("current_demonstrated_checkpoint"),
    )
    event_times: Dict[str, list[datetime]] = {}
    for event in events:
        occurred = _utc(event.get("occurred_at"))
        if occurred is not None:
            event_times.setdefault(str(event.get("step") or ""), []).append(
                occurred
            )
    matching_verdict_times = [
        _utc(event.get("occurred_at"))
        for event in events
        if event.get("step") == "progress_verdict_served"
        and (event.get("metadata") or {}).get("evidence_identity")
        == transfer_evidence_identity
        and _utc(event.get("occurred_at")) is not None
    ]
    verdict_served_at = (
        min(matching_verdict_times)
        if matching_verdict_times
        else None
    )
    current_verdict_served = verdict_served_at is not None

    step_state = {
        "baseline_frozen": True,
        "cohort_eligible": True,
        "home_focus_served": "home_focus_served" in reached,
        "lesson_opened": "lesson_opened" in reached,
        "server_graded_first_attempt": evidence[
            "server_graded_first_attempt"
        ],
        "lesson_completed": "lesson_completed" in reached,
        "review_served": "review_served" in reached,
        "later_unassisted_opportunity": (
            evidence["later_application_events"] > 0
        ),
        "verdict_served": current_verdict_served,
    }
    milestone_candidates = (
        event_times.get("home_focus_served", []),
        event_times.get("lesson_opened", []),
        evidence["server_grade_times"],
        event_times.get("lesson_completed", []),
        event_times.get("review_served", []),
        evidence["application_times"],
        matching_verdict_times,
    )
    previous = None
    sequence_valid = True
    for candidates in milestone_candidates:
        ordered = sorted(item for item in candidates if item is not None)
        selected = next(
            (
                item
                for item in ordered
                if previous is None or item >= previous
            ),
            None,
        )
        if selected is None:
            sequence_valid = False
            break
        previous = selected
    return {
        "schema_version": JOURNEY_VERSION,
        "enabled": True,
        "paused": False,
        "focus": {
            "focus_id": baseline.get("focus_id"),
            "instruction_id": baseline.get("instruction_id"),
            "focus_kind": baseline.get("focus_kind"),
        },
        "practice": {
            "lesson_evidence_events": evidence["lesson_evidence_events"],
            "completed": step_state["lesson_completed"],
            "changes_transfer_verdict": False,
        },
        "coach_games": {
            "opportunities": evidence["coached_application_events"],
            "handled": evidence["coached_handled"],
            "missed": evidence["coached_missed"],
            "assisted_practice": evidence["assisted_practice_events"],
            "unassisted_checkpoints": evidence[
                "unassisted_checkpoint_events"
            ],
            "ordinary_play": evidence["ordinary_coach_play_events"],
            "practice": dict(evidence["coached_modes"]["practice_assisted"]),
            "checkpoint": dict(
                evidence["coached_modes"]["checkpoint_unassisted"]
            ),
            "discovery": dict(evidence["coached_modes"]["just_play"]),
            "changes_transfer_verdict": False,
        },
        "transfer": {
            "later_opportunities": evidence["later_application_events"],
            "handled": evidence["later_handled"],
            "missed": evidence["later_missed"],
            "verdict": verdict,
            "message": transfer_message,
            "evidence_identity": transfer_evidence_identity,
        },
        "evidence_examples": evidence_examples,
        "learner_state": learner,
        "steps": step_state,
        "sequence_valid": sequence_valid,
        "complete": all(step_state.values()) and sequence_valid,
    }


__all__ = [
    "FOCUS_KIND",
    "JOURNEY_COLLECTION",
    "JOURNEY_VERSION",
    "REACH_STEPS",
    "build_pre_enrollment_baseline",
    "build_phase8_journey_projection",
    "record_phase8_reach_event",
    "same_immutable_baseline",
]
