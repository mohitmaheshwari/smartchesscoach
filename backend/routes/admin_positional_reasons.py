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
    _INDEXES_ENSURED = True


async def _progress() -> Dict[str, Any]:
    rows = await db.positional_reason_queue.find(
        {}, {"_id": 0, "status": 1, "disposition": 1}
    ).to_list(length=None)
    dispositions = Counter(
        row.get("disposition")
        for row in rows
        if row.get("disposition") in DISPOSITION_LABELS
    )
    pending = sum(row.get("status", "pending") == "pending" for row in rows)
    return {
        "resolved": len(rows) - pending,
        "pending": pending,
        "total": len(rows),
        "by_disposition": dict(dispositions),
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


# ---------------------------------------------------------------------------
# Blind judging of model explanations.
#
# The first comparison had Opus grading Fable, which Mohit rightly called out.
# The mechanical claim checks were run against a real board so those are safe,
# but "is this reason true and useful" was one model judging another. This
# adds a human judge, and shows the two answers anonymously so a prior about
# which model is which cannot decide the vote. The side each model occupies is
# fixed by hashing the position, so reloading never reveals it.
# ---------------------------------------------------------------------------


@router.get("/admin/reason-judge/next")
async def next_pair(user: User = Depends(require_admin)):
    """A position with two anonymous explanations, or 404 when done."""
    judged = await db.reason_judgements.distinct("fen")
    row = await db.model_reason_answers.find_one(
        {"fen": {"$nin": judged}}, {"_id": 0}
    )
    if not row:
        raise HTTPException(status_code=404, detail="Every position has been judged")
    pair = await db.model_reason_answers.find(
        {"fen": row["fen"]}, {"_id": 0}
    ).to_list(2)
    if len(pair) != 2:
        raise HTTPException(status_code=409, detail="Position is missing an answer")

    def anon(entry):
        # model / model_id deliberately omitted — that is the whole point
        return {
            "slot": entry["slot"],
            "reason": entry.get("reason"),
            "concept_label": entry.get("concept_label"),
            "is_positional": entry.get("is_positional"),
            "checkable_claims": entry.get("checkable_claims") or [],
        }

    first = pair[0]
    total = len(await db.model_reason_answers.distinct("fen"))
    return {
        "fen": first["fen"],
        "played_san": first.get("played_san"),
        "best_san": first.get("best_san"),
        "cp_loss": first.get("cp_loss"),
        "men": first.get("men"),
        "bucket": first.get("bucket"),
        "side_to_move": first.get("side_to_move"),
        "answers": sorted((anon(p) for p in pair), key=lambda a: a["slot"]),
        "progress": {"judged": len(judged), "total": total},
    }


@router.post("/admin/reason-judge")
async def judge_pair(
    payload: Dict = Body(...),
    user: User = Depends(require_admin),
):
    """Record a human verdict, then reveal which side was which."""
    fen = str(payload.get("fen") or "").strip()
    better = str(payload.get("better") or "").strip().upper()
    if not fen or better not in {"A", "B", "TIE", "NEITHER"}:
        raise HTTPException(status_code=400, detail="fen and better (A/B/TIE/NEITHER) required")

    pair = await db.model_reason_answers.find({"fen": fen}, {"_id": 0}).to_list(2)
    if len(pair) != 2:
        raise HTTPException(status_code=404, detail="Position not found")
    by_slot = {p["slot"]: p for p in pair}

    await db.reason_judgements.insert_one({
        "fen": fen,
        "better": better,
        "a_is_true": payload.get("a_is_true"),
        "b_is_true": payload.get("b_is_true"),
        "notes": str(payload.get("notes") or "").strip() or None,
        "winning_model": by_slot[better]["model"] if better in ("A", "B") else None,
        "slot_models": {s: p["model"] for s, p in by_slot.items()},
        "judged_by": user.user_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    judged = await db.reason_judgements.distinct("fen")
    total = len(await db.model_reason_answers.distinct("fen"))
    return {
        "ok": True,
        # revealed only after the vote is stored
        "reveal": {s: p["model"] for s, p in by_slot.items()},
        "progress": {"judged": len(judged), "total": total},
    }


@router.get("/admin/reason-judge/results")
async def judge_results(user: User = Depends(require_admin)):
    """Human verdicts so far, and whether they agree with the model grader."""
    rows = await db.reason_judgements.find({}, {"_id": 0}).to_list(500)
    wins: Dict[str, int] = {"opus": 0, "fable": 0, "tie": 0, "neither": 0}
    for r in rows:
        if r.get("better") in ("TIE", "NEITHER"):
            wins[r["better"].lower()] += 1
        elif r.get("winning_model"):
            wins[r["winning_model"]] = wins.get(r["winning_model"], 0) + 1
    return {"judged": len(rows), "wins": wins, "judgements": rows}
