"""PIC Focus Game lifecycle on canonical focus/game documents.

No collection is introduced. Commitment state lives on `user_active_focus`;
the immutable evidence envelope lives on the analyzed game. Raw move evidence
remains in `move_observations`.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Optional

from pymongo import ReturnDocument

from services.focus_bridge import (
    DESTINATION_SAFETY_FACT_VERSION,
    PIC_FACT_VERSION,
    _pic_fields_eligible,
    _to_dt,
)
from services.detector_quality import (
    focus_document_is_authorized,
    quality_id_for_focus_document,
)


DESTINATION_SAFETY_QUALITY_ID = "gap:piece_safety:destination_safety_exact"


FOCUS_COLLECTION = "user_active_focus"


def summarize_pic_observations(
    observations: Iterable[Dict[str, Any]],
    *,
    proof_detector_id: str = PIC_FACT_VERSION,
) -> Dict[str, int]:
    """Reduce only observations comparable to the focus's proof detector.

    The validation-only legacy cycle keeps its D_live evidence. New exact
    cycles count the Plan-authorized destination-safety fact instead. Mixing
    the two would make a player's diagnosis, practice, and measurement disagree.
    """
    exact = proof_detector_id == DESTINATION_SAFETY_FACT_VERSION
    minimum_schema = 18 if exact else 16
    fact_field = "destination_safety_exact" if exact else "piece_safety_decision"
    diagnosis_subtype = "destination_safety_exact" if exact else "simple_hang"
    decisions = 0
    misses = 0
    diagnoses = 0
    for observation in observations or []:
        if int(observation.get("schema_version") or 0) < minimum_schema:
            continue
        if (
            observation.get("missed_pattern") == "piece_safety"
            and observation.get("subtype") == diagnosis_subtype
        ):
            diagnoses += 1
        fact = observation.get(fact_field) or {}
        if (
            fact.get("version") != proof_detector_id
            or fact.get("derivation_status") != "ok"
            or fact.get("eligible") is not True
        ):
            continue
        decisions += 1
        if fact.get("outcome") == "miss":
            misses += 1
    result = {
        "decisions": decisions,
        "misses": misses,
        "handled": max(0, decisions - misses),
        "positive_piece_safety_diagnoses": diagnoses,
    }
    result[
        "positive_destination_safety_diagnoses"
        if exact
        else "positive_simple_hang_diagnoses"
    ] = diagnoses
    return result


async def _require_pic_focus(db, user_id: str) -> Dict[str, Any]:
    user = await db.users.find_one({"user_id": user_id}, {"_id": 0, "role": 1})
    if not _pic_fields_eligible((user or {}).get("role")):
        raise ValueError("personal improvement cycle is not enabled for this user")
    focus = await db[FOCUS_COLLECTION].find_one({
        "user_id": user_id,
        "status": "active",
        "type": "weakness",
        "topic_key": "piece_safety",
        "cycle_version": 1,
    })
    if not focus:
        raise ValueError("an active PIC piece-safety focus is required")
    if not focus_document_is_authorized(focus):
        raise ValueError("the active focus detector is not Plan-grade")
    return focus


async def commit_next_focus_game(db, user_id: str) -> Dict[str, Any]:
    focus = await _require_pic_focus(db, user_id)
    pending = focus.get("pending_focus_game") or {}
    if pending.get("status") == "waiting":
        return pending
    now = datetime.now(timezone.utc)
    pending = {
        "commitment_id": str(uuid.uuid4()),
        "status": "waiting",
        "committed_at": now,
        "game_id": None,
    }
    await db[FOCUS_COLLECTION].update_one(
        {"_id": focus["_id"], "status": "active"},
        {"$set": {"pending_focus_game": pending, "updated_at": now}},
    )
    return pending


async def cancel_focus_game_commitment(db, user_id: str) -> Dict[str, Any]:
    focus = await _require_pic_focus(db, user_id)
    pending = focus.get("pending_focus_game") or {}
    if pending.get("status") != "waiting":
        return pending
    now = datetime.now(timezone.utc)
    pending = {**pending, "status": "cancelled", "cancelled_at": now}
    await db[FOCUS_COLLECTION].update_one(
        {"_id": focus["_id"], "pending_focus_game.status": "waiting"},
        {"$set": {"pending_focus_game": pending, "updated_at": now}},
    )
    return pending


async def correct_claimed_focus_game(
    db, user_id: str, game_id: str
) -> Dict[str, Any]:
    focus = await _require_pic_focus(db, user_id)
    pending = focus.get("pending_focus_game") or {}
    if pending.get("status") != "claimed" or pending.get("game_id") != game_id:
        raise ValueError("that game is not the currently claimed Focus Game")
    now = datetime.now(timezone.utc)
    replacement = {
        "commitment_id": str(uuid.uuid4()),
        "status": "waiting",
        "committed_at": now,
        "game_id": None,
        "correction_of": game_id,
        "corrected_at": now,
    }
    await db.games.update_one(
        {"user_id": user_id, "game_id": game_id},
        {"$unset": {"pic_evidence": ""}},
    )
    await db[FOCUS_COLLECTION].update_one(
        {
            "_id": focus["_id"],
            "pending_focus_game.status": "claimed",
            "pending_focus_game.game_id": game_id,
        },
        {"$set": {"pending_focus_game": replacement, "updated_at": now}},
    )
    return replacement


def claim_pending_focus_game_sync(
    db, user_id: str, game_id: str, imported_at: Any
) -> Optional[Dict[str, Any]]:
    """Atomically claim the next imported game when commitment predates import."""
    imported_dt = _to_dt(imported_at)
    if imported_dt is None:
        return None
    focus = db[FOCUS_COLLECTION].find_one({
        "user_id": user_id,
        "status": "active",
        "type": "weakness",
        "topic_key": "piece_safety",
        "cycle_version": 1,
    })
    if not focus:
        return None
    if not focus_document_is_authorized(focus):
        return None
    pending = focus.get("pending_focus_game") or {}
    if pending.get("status") == "claimed" and pending.get("game_id") == game_id:
        return focus
    committed_dt = _to_dt(pending.get("committed_at"))
    if pending.get("status") != "waiting" or committed_dt is None:
        return None
    if imported_dt < committed_dt:
        return None
    now = datetime.now(timezone.utc)
    return db[FOCUS_COLLECTION].find_one_and_update(
        {
            "_id": focus["_id"],
            "pending_focus_game.status": "waiting",
            "pending_focus_game.commitment_id": pending.get("commitment_id"),
        },
        {"$set": {
            "pending_focus_game.status": "claimed",
            "pending_focus_game.game_id": game_id,
            "pending_focus_game.claimed_at": now,
            "updated_at": now,
        }},
        return_document=ReturnDocument.AFTER,
    )


def record_pic_game_evidence_sync(
    db,
    user_id: str,
    game: Dict[str, Any],
    observations: Iterable[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Write one deterministic evidence envelope after observation completion."""
    user = db.users.find_one({"user_id": user_id}, {"_id": 0, "role": 1}) or {}
    if not _pic_fields_eligible(user.get("role")):
        return None
    focus = db[FOCUS_COLLECTION].find_one({
        "user_id": user_id,
        "status": "active",
        "type": "weakness",
        "topic_key": "piece_safety",
        "cycle_version": 1,
    })
    if not focus:
        return None
    if not focus_document_is_authorized(focus):
        return None

    game_id = str(game.get("game_id") or "")
    claimed_focus = claim_pending_focus_game_sync(
        db, user_id, game_id, game.get("imported_at")
    )
    if claimed_focus is not None:
        focus = claimed_focus
    pending = focus.get("pending_focus_game") or {}
    committed = (
        pending.get("status") == "claimed"
        and pending.get("game_id") == game_id
    )
    exact_focus = (
        quality_id_for_focus_document(focus) == DESTINATION_SAFETY_QUALITY_ID
    )
    proof_detector_id = (
        DESTINATION_SAFETY_FACT_VERSION if exact_focus else PIC_FACT_VERSION
    )
    observation_version = 18 if exact_focus else 17
    summary = summarize_pic_observations(
        observations,
        proof_detector_id=proof_detector_id,
    )
    measured_at = datetime.now(timezone.utc)
    envelope = {
        "version": 1,
        "idempotency_key": (
            f"pic:{focus['_id']}:{game_id}:move-observation-v{observation_version}"
        ),
        "focus_id": str(focus["_id"]),
        "instruction_id": focus.get("instruction_id"),
        "environment": "external",
        "evidence_mode": "external_focus_game" if committed else "ordinary_play",
        "assisted": False,
        "pre_committed": committed,
        "commitment_id": pending.get("commitment_id") if committed else None,
        "proof_detector_id": proof_detector_id,
        "summary": summary,
        "mastery_eligible": False,
        "demotion_eligible": False,
        "proof_rule_locked": False,
        "verdict": "measurement_pending" if committed else "discovery_only",
        "measured_at": measured_at,
    }
    db.games.update_one(
        {"user_id": user_id, "game_id": game_id},
        {"$set": {"pic_evidence": envelope}},
    )
    return envelope
