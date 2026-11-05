"""The fifth queue on /admin/geometry-gaps: did this real-game move show the idea?

docs/phase1_lesson_evidence_review_scope.md, WS1. Founder decision 2026-10-20:
"right now we are not live, so shadow only mastery need to have some sort of
thing for our coaches to review and approve."

A row is one real-game move where a player kept a piece safe while a move that
would have hung one was a real temptation (services/lesson_evidence_review.py
holds the rules). The coach answers one question -- does this move show the
player understands the idea? -- which is not "is the detector right".

What a ruling is NOT: a promotion. It is evidence. The shadow ledger in
`learning_sessions` is never written here, and a "yes" awards nothing by
itself; the mastery authority reads it later (WS2). A "no" is a bug report and
strips nothing.

Same shape as the other four queues: next / POST / results, keyed on the
event's own idempotency_key, same reviewer gate. Rows are seeded offline by
scripts/seed_lesson_evidence_reviews.py, because Maia does not run here.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter, Body, Depends, HTTPException

from routes.admin import require_geometry_reviewer
from routes.auth import User
from services.lesson_evidence_review import VERDICTS, order_queue, summarise

router = APIRouter(tags=["Admin"])
db = None


def set_db(database) -> None:
    global db
    db = database


def _require_db() -> None:
    if db is None:
        raise HTTPException(status_code=500, detail="Database not initialized")


def _public(row: Dict[str, Any]) -> Dict[str, Any]:
    out = {k: v for k, v in row.items() if k != "_id"}
    out["queue"] = "lesson"
    return out


@router.get("/admin/lesson-evidence/next")
async def next_lesson_evidence(user: User = Depends(require_geometry_reviewer)):
    """The next position to judge, one player-concept pair at a time."""
    _require_db()
    rows = await db.lesson_evidence_reviews.find({}, {"_id": 0}).to_list(length=None)
    rulings = await db.lesson_evidence_rulings.find(
        {}, {"_id": 0, "key": 1, "pair": 1, "verdict": 1}
    ).to_list(length=None)
    queue = order_queue(rows, rulings)
    if not rows:
        raise HTTPException(
            status_code=404,
            detail="No positions have been seeded yet (scripts/seed_lesson_evidence_reviews.py).",
        )
    if not queue:
        raise HTTPException(
            status_code=404,
            detail="Every position in this set has been ruled on (%d)." % len(rulings),
        )
    out = _public(dict(queue[0]))
    out["pairs_waiting"] = len(queue)
    out["ruled_count"] = len(rulings)
    return out


@router.post("/admin/lesson-evidence")
async def rule_lesson_evidence(
    payload: Dict = Body(...),
    user: User = Depends(require_geometry_reviewer),
):
    """Record yes / no / not sure, with the reviewer's name and an optional note."""
    _require_db()
    key = str(payload.get("key") or "").strip()
    verdict = str(payload.get("verdict") or "").strip().lower()
    if not key:
        raise HTTPException(status_code=400, detail="key is required")
    if verdict not in VERDICTS:
        raise HTTPException(status_code=400, detail="verdict must be yes, no or unsure")
    row = await db.lesson_evidence_reviews.find_one({"key": key}, {"_id": 0})
    if not row:
        raise HTTPException(status_code=404, detail="no such position in the review set")
    await db.lesson_evidence_rulings.update_one(
        {"key": key, "skill_id": row.get("skill_id")},
        {"$set": {
            "key": key,
            "skill_id": row.get("skill_id"),
            "pair": row.get("pair"),
            "user_id": row.get("user_id"),
            "detector_quality_id": row.get("detector_quality_id"),
            # Pre-lesson demonstrations count toward mastery, but a surface that
            # claims the TEACHING worked must count only these (scope §10.6).
            "after_first_lesson": bool(row.get("after_first_lesson")),
            "verdict": verdict,
            "note": str(payload.get("note") or "")[:2000],
            # The login is shared with reviewing coaches, so the account alone
            # cannot tell two reviewers apart (scope §6.1: free text, default).
            "reviewer_name": str(payload.get("reviewer_name") or "")[:120],
            # Carried so the results read without a join, and so a reseed of
            # the review set cannot orphan what was ruled.
            "fen": row.get("fen"),
            "played_san": row.get("played_san"),
            "temptation": row.get("temptation"),
            "row_version": row.get("row_version"),
            "ruled_by": user.user_id,
            "author_email": (getattr(user, "email", "") or "").lower(),
            "ruled_at": datetime.now(timezone.utc).isoformat(),
        }},
        upsert=True,
    )
    return {"ok": True, "key": key, "verdict": verdict}


@router.get("/admin/lesson-evidence/results")
async def lesson_evidence_results(user: User = Depends(require_geometry_reviewer)):
    """Tallies, pairs approved, and every "no" -- those are the bug reports."""
    _require_db()
    rows = await db.lesson_evidence_reviews.find({}, {"_id": 0, "key": 1, "pair": 1}).to_list(length=None)
    rulings = await db.lesson_evidence_rulings.find({}, {"_id": 0}).to_list(length=None)
    return summarise(rows, rulings)
