"""Admin workflow for reviewed positional teaching reasons.

Reasons saved here are candidate evidence only. They cannot affect captions or
mastery until a canonical detector and verifier are separately authorized.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query

from routes.admin import require_admin
from routes.auth import User
from services.positional_reason_learning import (
    DISPOSITION_LABELS,
    PositionalReasonValidationError,
    canonical_concepts,
    normalize_submission,
    position_fingerprint,
    structural_features,
    structural_signature,
)


router = APIRouter(tags=["Admin"])
db = None
_INDEXES_ENSURED = False


def set_db(database) -> None:
    global db
    db = database


def _require_db() -> None:
    if db is None:
        raise HTTPException(status_code=500, detail="Database not initialized")


async def _ensure_indexes() -> None:
    global _INDEXES_ENSURED
    if _INDEXES_ENSURED:
        return
    _require_db()
    await db.positional_reason_queue.create_index(
        [("status", 1), ("priority", 1), ("cp_loss", -1)],
        name="positional_reason_queue_review_order",
    )
    await db.positional_reason_submissions.create_index(
        "position_fingerprint",
        unique=True,
        sparse=True,
        name="positional_reason_submission_position",
    )
    await db.positional_reason_submissions.create_index(
        [("canonical_concept_id", 1), ("structural_signature", 1)],
        name="positional_reason_submission_grouping",
    )
    await db.positional_reason_generated_candidates.create_index(
        "position_fingerprint",
        unique=True,
        name="generated_positional_position",
    )
    _INDEXES_ENSURED = True


async def _progress() -> Dict[str, Any]:
    rows = await db.positional_reason_queue.find(
        {},
        {
            "_id": 0,
            "status": 1,
            "disposition": 1,
            "fen": 1,
            "played_uci": 1,
            "best_uci": 1,
        },
    ).to_list(length=None)
    dispositions = Counter(
        row.get("disposition")
        for row in rows
        if row.get("disposition") in DISPOSITION_LABELS
    )
    pending = sum(row.get("status", "pending") == "pending" for row in rows)
    generated = await db.positional_reason_generated_candidates.find(
        {}, {"_id": 0, "position_fingerprint": 1, "disposition": 1, "verification.status": 1}
    ).to_list(length=None)
    generated_by_fingerprint = {
        row.get("position_fingerprint"): row
        for row in generated
        if row.get("position_fingerprint")
    }
    covered_positions = []
    for queue_row in rows:
        try:
            fingerprint = position_fingerprint(
                queue_row["fen"], queue_row["played_uci"], queue_row["best_uci"]
            )
        except (KeyError, PositionalReasonValidationError):
            continue
        candidate = generated_by_fingerprint.get(fingerprint)
        if candidate:
            covered_positions.append(candidate)
    generated_dispositions = Counter(row.get("disposition") for row in covered_positions)
    verified_generated = sum(
        row.get("disposition") == "eligible_positional"
        and (row.get("verification") or {}).get("status") == "pass"
        for row in covered_positions
    )
    return {
        "resolved": len(rows) - pending,
        "pending": pending,
        "total": len(rows),
        "by_disposition": dict(dispositions),
        "generated": len(covered_positions),
        "generated_unique_candidates": len(generated),
        "verified_generated_captions": verified_generated,
        "generated_by_disposition": dict(generated_dispositions),
    }


@router.get("/admin/positional-reasons/next")
async def next_position(
    skip_resolved: bool = True,
    user: User = Depends(require_admin),
):
    _require_db()
    await _ensure_indexes()
    query: Dict[str, Any] = {"status": "pending"} if skip_resolved else {}
    row = await db.positional_reason_queue.find_one(
        query,
        {"_id": 0},
        sort=[("priority", 1), ("cp_loss", -1)],
    )
    if not row:
        raise HTTPException(status_code=404, detail="Every queued position is resolved")
    try:
        row["structural_features"] = structural_features(
            row["fen"], row["played_uci"], row["best_uci"]
        )
        row["structural_signature"] = structural_signature(
            row["fen"], row["played_uci"], row["best_uci"]
        )
        fingerprint = position_fingerprint(
            row["fen"], row["played_uci"], row["best_uci"]
        )
        row["position_fingerprint"] = fingerprint
        row["generated_candidate"] = await db.positional_reason_generated_candidates.find_one(
            {"position_fingerprint": fingerprint},
            {
                "_id": 0,
                "candidate_id": 1,
                "disposition": 1,
                "concept_label": 1,
                "canonical_concept_id": 1,
                "better_move_fact": 1,
                "played_move_fact": 1,
                "contrast": 1,
                "transferable_lesson": 1,
                "caption": 1,
                "reason_category": 1,
                "verification": 1,
                "caption_eligible": 1,
                "tracker_eligible": 1,
            },
        )
    except PositionalReasonValidationError as exc:
        row["structural_error"] = str(exc)
    row["progress"] = await _progress()
    return row


@router.get("/admin/positional-reasons/concepts")
async def list_concepts(user: User = Depends(require_admin)):
    concepts = sorted(canonical_concepts().values(), key=lambda item: item["name"])
    return {"concepts": concepts}


@router.get("/admin/positional-reasons/similar")
async def similar_reasons(
    structural_signature_value: str = Query("", alias="structural_signature"),
    canonical_concept_id: str = "",
    concept_label: str = "",
    exclude_fen: str = "",
    limit: int = 8,
    user: User = Depends(require_admin),
):
    _require_db()
    clauses = []
    if canonical_concept_id:
        clauses.append({"canonical_concept_id": canonical_concept_id})
    if concept_label:
        clauses.append({"concept_label": concept_label})
    if structural_signature_value:
        clauses.append({"structural_signature": structural_signature_value})
    if not clauses:
        return {"count": 0, "submissions": []}
    query: Dict[str, Any] = {"$or": clauses}
    if exclude_fen:
        query["fen"] = {"$ne": " ".join(exclude_fen.split()[:4])}
    rows = await db.positional_reason_submissions.find(
        query,
        {
            "_id": 0,
            "fen": 1,
            "played_san": 1,
            "best_san": 1,
            "concept_label": 1,
            "canonical_concept_id": 1,
            "reason": 1,
            "disposition": 1,
            "voice_warnings": 1,
            "promotion": 1,
        },
    ).sort("updated_at", -1).to_list(min(max(limit, 1), 20))
    return {"count": len(rows), "submissions": rows}


@router.post("/admin/positional-reasons")
async def submit_reason(
    payload: Dict[str, Any] = Body(...),
    user: User = Depends(require_admin),
):
    _require_db()
    await _ensure_indexes()
    fen = str(payload.get("fen") or "").strip()
    if not fen:
        raise HTTPException(status_code=400, detail="fen is required")
    row = await db.positional_reason_queue.find_one({"fen": fen}, {"_id": 0})
    if not row:
        raise HTTPException(status_code=404, detail="Queued position not found")
    try:
        submission = normalize_submission(
            payload,
            row,
            submitted_by=user.user_id,
        )
    except PositionalReasonValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    created_at = submission.pop("created_at")
    await db.positional_reason_submissions.update_one(
        {"position_fingerprint": submission["position_fingerprint"]},
        {
            "$set": submission,
            "$setOnInsert": {"created_at": created_at},
        },
        upsert=True,
    )
    now = datetime.now(timezone.utc).isoformat()
    await db.positional_reason_queue.update_one(
        {"fen": fen},
        {
            "$set": {
                "status": "resolved",
                "disposition": submission["disposition"],
                "resolved_at": now,
                "resolved_by": user.user_id,
                "position_fingerprint": submission["position_fingerprint"],
                "structural_signature": submission["structural_signature"],
            }
        },
    )
    return {
        "ok": True,
        "saved": {
            "position_fingerprint": submission["position_fingerprint"],
            "disposition": submission["disposition"],
            "voice_warnings": submission["voice_warnings"],
            "promotion": submission["promotion"],
        },
        "progress": await _progress(),
    }


@router.post("/admin/positional-reasons/skip")
async def skip_position(
    payload: Dict[str, Any] = Body(...),
    user: User = Depends(require_admin),
):
    forwarded = dict(payload)
    forwarded["disposition"] = "insufficient_evidence"
    return await submit_reason(forwarded, user)


@router.get("/admin/positional-reasons/submissions")
async def list_submissions(
    limit: int = 100,
    disposition: Optional[str] = None,
    user: User = Depends(require_admin),
):
    _require_db()
    query = {"disposition": disposition} if disposition else {}
    rows = await db.positional_reason_submissions.find(
        query, {"_id": 0}
    ).sort("updated_at", -1).to_list(min(max(limit, 1), 500))
    labels = Counter(
        row.get("canonical_concept_id") or row.get("concept_label")
        for row in rows
        if row.get("canonical_concept_id") or row.get("concept_label")
    )
    return {
        "count": len(rows),
        "by_concept": labels.most_common(),
        "submissions": rows,
        "progress": await _progress(),
    }


@router.get("/admin/positional-reasons/generated")
async def list_generated_candidates(
    limit: int = 250,
    disposition: Optional[str] = None,
    verification_status: Optional[str] = None,
    user: User = Depends(require_admin),
):
    """List non-authoritative generated drafts waiting for admin review."""
    _require_db()
    await _ensure_indexes()
    query: Dict[str, Any] = {}
    if disposition:
        query["disposition"] = disposition
    if verification_status:
        query["verification.status"] = verification_status
    rows = await db.positional_reason_generated_candidates.find(
        query,
        {"_id": 0, "engine_evidence": 0, "board_evidence": 0},
    ).sort([("disposition", 1), ("candidate_id", 1)]).to_list(min(max(limit, 1), 500))
    return {"count": len(rows), "candidates": rows, "progress": await _progress()}
