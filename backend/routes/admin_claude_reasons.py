"""The fourth queue on /admin/geometry-gaps: Claude's reason, judged by the board.

Mohit, 2026-10-29: "the best way for you to add a section on claude reason for
those positions too, so I can verify them right there."

What a row is
-------------
One of the positions the why button could not explain. Each carries, from the
run that produced it:

  reason        what I would say, in plain English, about the move PLAYED
  probes        every hypothesis I put to the board, each as a change to the
                position (a relation broken, a piece moved, the move not made)
                with the recovery it measured and a generated control
  judge_overall what the board decided -- confirmed / refuted / not_probeable /
                cannot_test. "not_probeable" means the only thing scored was
                the null move: nothing about the reason was tested, so it is
                NOT a refutation. The first version of the summary called those
                refuted; 21 of 61 were mislabelled that way.

The verdict recorded here is a human one, same as the other three queues. The
rows are candidate evidence and reach no caption and no player.

Rows are seeded from the offline run (scripts/seed_claude_reason_reviews.py),
never computed on request: each one cost several fresh engine searches.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query

from routes.admin import require_admin, require_geometry_reviewer
from routes.auth import User

router = APIRouter(tags=["Admin"])
db = None

VERDICTS = {"agree", "disagree", "unsure"}
JUDGE = {"confirmed", "refuted", "not_probeable", "cannot_test"}


def set_db(database) -> None:
    global db
    db = database


def _require_db() -> None:
    if db is None:
        raise HTTPException(status_code=500, detail="Database not initialized")


def _public(row: Dict[str, Any]) -> Dict[str, Any]:
    """The row as the page gets it. `queue` tells the page which panel to draw."""
    out = {k: v for k, v in row.items() if k != "_id"}
    out["queue"] = "claude"
    # The page's board and line replay read these names on every queue.
    out.setdefault("pv_after_played", [])
    out.setdefault("pv_after_best", [])
    return out


@router.get("/admin/geometry-gaps/claude-reasons/next")
async def next_claude_reason(
    judge: Optional[str] = Query(default=None, pattern="^(confirmed|refuted|not_probeable|cannot_test)$"),
    bucket: Optional[str] = Query(default=None),
    user: User = Depends(require_geometry_reviewer),
):
    """One position with my reason and the board's verdict, not yet ruled on.

    Ordered confirmed first, then refuted, then the rest: the confirmed ones
    are where a wrong reason would do the most damage if it shipped, so they
    want the human eye first.
    """
    _require_db()
    ruled = set(await db.claude_reason_rulings.distinct("key"))
    # The live Why queue's studies come first (services/why_queue.py, 2026-11-02):
    # they are waiting to reach a card, the seeded set is not. Review-first
    # means a gate-passed study sits here until someone presses Agree.
    from services.why_queue import HELD, HELD_FOR_REVIEW, PUBLISHED, review_row
    # A study the checker published (docs/why_queue_checker_scope.md) is already
    # on cards; it stays here until a person rules, and comes first.
    checker_live = {"status": PUBLISHED, "ruled_by": "checker"}
    live_query: Dict[str, Any] = {"$or": [{"status": {"$in": [HELD_FOR_REVIEW, HELD]}}, checker_live]}
    if judge == "confirmed":
        live_query = {"$or": [{"status": HELD_FOR_REVIEW}, checker_live]}
    elif judge:
        live_query = {"status": HELD if judge == "refuted" else "__none__"}
    live = [review_row(r) for r in await db.why_reasons.find(live_query, {"_id": 0}).to_list(length=None)]
    live.sort(key=lambda r: (0 if r.get("status") == PUBLISHED else 1,
                             0 if r.get("judge_overall") == "confirmed" else 1, str(r.get("created_at") or "")))
    query: Dict[str, Any] = {}
    if judge:
        query["judge_overall"] = judge
    if bucket:
        query["bucket"] = bucket
    rows = await db.claude_reason_reviews.find(query, {"_id": 0}).to_list(length=None)
    order = {"confirmed": 0, "refuted": 1, "not_probeable": 2, "cannot_test": 3}
    rows.sort(key=lambda r: (order.get(str(r.get("judge_overall")), 9), int(r.get("idx") or 0)))
    rows = live + rows if not bucket else rows
    for row in rows:
        if row.get("key") in ruled:
            continue
        out = _public(row)
        out["ruled_count"] = len(ruled)
        out["remaining"] = sum(1 for r in rows if r.get("key") not in ruled)
        return out
    raise HTTPException(
        status_code=404,
        detail="Every reason in this set has been ruled on (%d)." % len(ruled),
    )


@router.post("/admin/geometry-gaps/claude-reasons")
async def rule_claude_reason(
    payload: Dict = Body(...),
    user: User = Depends(require_geometry_reviewer),
):
    """Record agree / disagree / unsure, with an optional reason of your own."""
    _require_db()
    key = str(payload.get("key") or "").strip()
    verdict = str(payload.get("verdict") or "").strip().lower()
    if not key:
        raise HTTPException(status_code=400, detail="key is required")
    if verdict not in VERDICTS:
        raise HTTPException(status_code=400, detail="verdict must be agree, disagree or unsure")
    row = await db.claude_reason_reviews.find_one({"key": key}, {"_id": 0})
    live_status = None
    if not row:
        # A study from the live Why queue: the ruling also decides whether
        # it reaches the card. Agree publishes, disagree rejects.
        from services.why_queue import apply_ruling, review_row
        live = await db.why_reasons.find_one({"key": key}, {"_id": 0})
        if not live:
            raise HTTPException(status_code=404, detail="no such position in the review set")
        row = review_row(live)
        live_status = await apply_ruling(db, key, verdict, ruled_by=user.user_id,
                                         note=str(payload.get("note") or ""))
    await db.claude_reason_rulings.update_one(
        {"key": key},
        {"$set": {
            "key": key,
            "verdict": verdict,
            "note": str(payload.get("note") or "")[:2000],
            # Carried so the results read without a join, and so a later
            # reseed of the review set cannot orphan what was ruled.
            "fen": row.get("fen"),
            "played_san": row.get("played_san"),
            "best_san": row.get("best_san"),
            "bucket": row.get("bucket"),
            "judge_overall": row.get("judge_overall"),
            "reason_reviewed": row.get("reason"),
            "ruled_by": user.user_id,
            "author_email": (getattr(user, "email", "") or "").lower(),
            "ruled_at": datetime.now(timezone.utc).isoformat(),
            "source": row.get("source") or "seeded",
        }},
        upsert=True,
    )
    out = {"ok": True, "key": key, "verdict": verdict}
    if live_status is not None:
        out["study_status"] = live_status
    return out


@router.get("/admin/geometry-gaps/claude-reasons/results")
async def claude_reason_results(user: User = Depends(require_geometry_reviewer)):
    """How often the human agreed, split by what the board had said.

    The cell that matters is judge=confirmed x human=disagree: a reason the
    board verified and a person rejects is either a bad reason the control did
    not catch, or a verified fact that is not the lesson -- and those are the
    two ways this engine can be wrong while every number is right.
    """
    _require_db()
    total = await db.claude_reason_reviews.count_documents({})
    live_by_status: Dict[str, int] = {}
    for status in ("held_for_review", "held", "published", "rejected", "no_lesson"):
        live_by_status[status] = await db.why_reasons.count_documents({"status": status})
    rows = await db.claude_reason_rulings.find({}, {"_id": 0}).to_list(length=None)
    grid: Dict[str, Dict[str, int]] = {}
    by_verdict: Dict[str, int] = {}
    for r in rows:
        j = str(r.get("judge_overall") or "unknown")
        v = str(r.get("verdict") or "unsure")
        grid.setdefault(j, {})
        grid[j][v] = grid[j].get(v, 0) + 1
        by_verdict[v] = by_verdict.get(v, 0) + 1
    return {
        "total": len(rows),
        "in_set": total,
        "why_queue": live_by_status,
        "by_verdict": by_verdict,
        "by_judge_then_verdict": grid,
        "disagreed_with_confirmed": [
            {"fen": r.get("fen"), "played_san": r.get("played_san"),
             "reason": r.get("reason_reviewed"), "note": r.get("note")}
            for r in rows
            if r.get("judge_overall") == "confirmed" and r.get("verdict") == "disagree"
        ],
    }


@router.get("/admin/why-queue/positions")
async def why_queue_positions(user: User = Depends(require_admin)):
    """Every position the Why button sent to be studied, with Claude's text when
    a study exists and "To be processed" when not. Read-only; ruling stays on
    /admin/geometry-gaps. Owner admins only. docs/why_queue_admin_page_scope.md
    """
    _require_db()
    from services.why_queue import admin_list
    rows = await admin_list(db)
    return {"count": len(rows), "positions": rows}
