"""Admin surface for capturing a coach's reason for a good move.

The machine can verify a positional idea and count how often it separates
the played move from the best one. It cannot reliably originate the idea:
of five predicates written in one pass, one fired zero times across 46,655
positions, and there was no way to tell which in advance.

So this collects the missing half. A position is shown with the move that
was played and the move that was best, and the coach writes, in plain
English, why the good move is good. Those reasons become candidate
predicates, which are then measured against the whole corpus before any of
them is allowed near a user.

Nothing here is shown to players. Reasons are raw input for authoring, not
captions.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Dict, Optional

import chess
from fastapi import APIRouter, Body, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorClient

from routes.admin import require_admin
from routes.auth import User

router = APIRouter(tags=["Admin"])

_client = AsyncIOMotorClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
db = _client[os.environ.get("DB_NAME", "test_database")]

MAX_REASON = 2000


@router.get("/admin/positional-reasons/next")
async def next_position(
    skip_answered: bool = True,
    user: User = Depends(require_admin),
):
    """The next position worth a coach's time.

    Ordered so positions no existing predicate explains come first: those
    are the only ones that can teach us a concept we do not already have.
    """
    query: Dict = {"status": "pending"} if skip_answered else {}
    row = await db.positional_reason_queue.find_one(
        query, {"_id": 0}, sort=[("priority", 1), ("cp_loss", -1)]
    )
    if not row:
        raise HTTPException(status_code=404, detail="Queue is empty — reseed it")

    total = await db.positional_reason_queue.count_documents({})
    answered = await db.positional_reason_queue.count_documents({"status": "answered"})
    row["progress"] = {"answered": answered, "total": total}
    return row


@router.post("/admin/positional-reasons")
async def submit_reason(
    payload: Dict = Body(...),
    user: User = Depends(require_admin),
):
    """Store one coach reason against one position."""
    fen = str(payload.get("fen") or "").strip()
    reason = str(payload.get("reason") or "").strip()
    if not fen or not reason:
        raise HTTPException(status_code=400, detail="fen and reason are required")
    if len(reason) > MAX_REASON:
        raise HTTPException(status_code=400, detail="reason is too long")
    try:
        chess.Board(fen)
    except ValueError:
        raise HTTPException(status_code=400, detail="fen is not a legal position")

    row = await db.positional_reason_queue.find_one({"fen": fen}, {"_id": 0})
    await db.positional_reason_submissions.insert_one({
        "fen": fen,
        "reason": reason,
        # Free text from the coach, plus a short label when they give one, so
        # related reasons can be grouped into a single candidate predicate.
        "concept_label": str(payload.get("concept_label") or "").strip() or None,
        "confidence": str(payload.get("confidence") or "").strip() or None,
        "played_san": (row or {}).get("played_san"),
        "best_san": (row or {}).get("best_san"),
        "cp_loss": (row or {}).get("cp_loss"),
        "men": (row or {}).get("men"),
        "already_explained_by": (row or {}).get("already_explained_by") or [],
        "submitted_by": user.user_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    await db.positional_reason_queue.update_one(
        {"fen": fen}, {"$set": {"status": "answered"}}
    )

    answered = await db.positional_reason_queue.count_documents({"status": "answered"})
    total = await db.positional_reason_queue.count_documents({})
    return {"ok": True, "answered": answered, "total": total}


@router.post("/admin/positional-reasons/skip")
async def skip_position(
    payload: Dict = Body(...),
    user: User = Depends(require_admin),
):
    """Skip a position without answering. Skipped is not answered."""
    fen = str(payload.get("fen") or "").strip()
    if not fen:
        raise HTTPException(status_code=400, detail="fen is required")
    await db.positional_reason_queue.update_one(
        {"fen": fen}, {"$set": {"status": "skipped"}}
    )
    return {"ok": True}


@router.get("/admin/positional-reasons/submissions")
async def list_submissions(
    limit: int = 100,
    user: User = Depends(require_admin),
):
    """Everything captured so far — the input to predicate authoring."""
    rows = await db.positional_reason_submissions.find(
        {}, {"_id": 0}
    ).sort("created_at", -1).to_list(min(max(limit, 1), 500))
    labels: Dict[str, int] = {}
    for r in rows:
        label = r.get("concept_label")
        if label:
            labels[label] = labels.get(label, 0) + 1
    return {
        "count": len(rows),
        "by_concept": sorted(labels.items(), key=lambda kv: -kv[1]),
        "submissions": rows,
    }
