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
