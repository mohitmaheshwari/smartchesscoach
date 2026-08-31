"""
Daily Fix routes — the solo daily-return loop (docs/daily_fix_scope.md).

GET  /api/daily-fix/today    → today's fix: focus, drill_type, drills/mission, streak
POST /api/daily-fix/complete → mark today's fix done → advance the practice streak
GET  /api/daily-fix/streak   → practice-streak view (for home + reminder)

Routing is delegated to services.daily_fix_service.resolve_daily_fix:
  - time_management focus → timed rush-test drills (returned inline)
  - board weakness focus  → the existing mission engine (reused, not rebuilt);
    a mission is generated so the frontend fetches positions via /missions.
"""
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from routes.auth import User, get_current_user
from services.daily_fix_service import resolve_daily_fix
from services.mistake_streak_service import (
    record_daily_fix_completion,
    get_practice_streak_view,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/daily-fix", tags=["daily-fix"])

db = None


def set_db(database):
    global db
    db = database


@router.get("/today")
async def daily_fix_today(user: User = Depends(get_current_user)):
    """Resolve today's fix. For a board focus, attach a mission so the frontend
    can pull positions through the existing /missions flow (single source)."""
    res = await resolve_daily_fix(db, user.user_id, limit=5)

    if res.get("drill_type") == "board" or res.get("fallback_to_board"):
        try:
            from mission_generation_service import generate_daily_mission
            user_doc = await db.users.find_one({"user_id": user.user_id})
            rating = user_doc.get("assessed_rating", 1200) if user_doc else 1200
            mission = await generate_daily_mission(user.user_id, rating, db)
            res["drill_type"] = "board"
            res["mission"] = {
                "mission_id": mission.get("mission_id"),
                "focus_label": mission.get("focus_label"),
                "focus_pattern": mission.get("focus_pattern"),
                "estimated_minutes": mission.get("estimated_minutes"),
                "goal_target": mission.get("goal_target"),
                "status": mission.get("status"),
            }
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[DAILY-FIX] board mission generation failed for {user.user_id}: {e}")
            res["mission"] = None
            res["mission_error"] = str(e)

    # Freeze the exact server-issued work for this UTC day. Completion checks
    # this record against server-graded attempts; the browser never tells us
    # which positions it completed or whether they were correct.
    today_key = datetime.now(timezone.utc).date().isoformat()
    assignment = await db.daily_fix_assignments.find_one({
        "user_id": user.user_id,
        "date": today_key,
    }, {"_id": 0})
    if not assignment:
        assignment = {
            "assignment_id": f"{user.user_id}:{today_key}",
            "user_id": user.user_id,
            "date": today_key,
            "drill_type": res.get("drill_type"),
            "puzzle_ids": [
                item.get("puzzle_id") for item in (res.get("drills") or [])
                if item.get("puzzle_id")
            ],
            "mission_id": (res.get("mission") or {}).get("mission_id"),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.daily_fix_assignments.update_one(
            {"assignment_id": assignment["assignment_id"]},
            {"$setOnInsert": assignment},
            upsert=True,
        )
        # Read back the winner of a concurrent first-open race. Never return a
        # locally generated mission/puzzle set that lost the immutable
        # assignment claim.
        assignment = await db.daily_fix_assignments.find_one({
            "assignment_id": assignment["assignment_id"],
        }, {"_id": 0})

    if assignment.get("drill_type") == "rush_test":
        issued = set(assignment.get("puzzle_ids") or [])
        res["drills"] = [
            item for item in (res.get("drills") or [])
            if item.get("puzzle_id") in issued
        ]
        res["has_drills"] = bool(res["drills"])
    elif assignment.get("mission_id"):
        frozen_mission = await db.behavioral_missions.find_one({
            "mission_id": assignment.get("mission_id"),
            "user_id": user.user_id,
        }, {"_id": 0})
        if frozen_mission:
            res["drill_type"] = "board"
            res["mission"] = {
                "mission_id": frozen_mission.get("mission_id"),
                "focus_label": frozen_mission.get("focus_label"),
                "focus_pattern": frozen_mission.get("focus_pattern"),
                "estimated_minutes": frozen_mission.get("estimated_minutes"),
                "goal_target": frozen_mission.get("goal_target"),
                "status": frozen_mission.get("status"),
            }

    return res


@router.post("/complete")
async def daily_fix_complete(user: User = Depends(get_current_user)):
    """Advance the streak only after the issued work is server-verified."""
    today_key = datetime.now(timezone.utc).date().isoformat()
    assignment = await db.daily_fix_assignments.find_one({
        "user_id": user.user_id,
        "date": today_key,
    }, {"_id": 0})
    if not assignment:
        raise HTTPException(status_code=409, detail="Open today's fix before completing it")

    if assignment.get("drill_type") == "rush_test":
        required = set(assignment.get("puzzle_ids") or [])
        if not required:
            raise HTTPException(status_code=409, detail="No verified Daily Fix positions were issued")
        issued_at = assignment.get("created_at")
        if not issued_at:
            raise HTTPException(status_code=409, detail="Open today's fix again to create a verified assignment")
        attempts = await db.puzzle_attempts.find({
            "user_id": user.user_id,
            "puzzle_id": {"$in": list(required)},
            "correct": True,
            "created_at": {"$gte": issued_at},
        }, {"_id": 0, "puzzle_id": 1}).to_list(200)
        solved = {str(item.get("puzzle_id")) for item in attempts}
        if not required.issubset(solved):
            raise HTTPException(
                status_code=409,
                detail="Find the verified move in every issued position before finishing",
            )
    else:
        mission_id = assignment.get("mission_id")
        mission = await db.behavioral_missions.find_one({
            "mission_id": mission_id,
            "user_id": user.user_id,
        }, {"_id": 0, "status": 1, "result": 1}) if mission_id else None
        if not mission or mission.get("status") != "completed" or mission.get("result") != "pass":
            raise HTTPException(status_code=409, detail="Complete today's verified mission first")

    new_state = await record_daily_fix_completion(db, user.user_id)
    await db.daily_fix_assignments.update_one(
        {"assignment_id": assignment.get("assignment_id")},
        {"$set": {"completed_at": datetime.now(timezone.utc).isoformat()}},
    )
    view = await get_practice_streak_view(db, user.user_id)
    return {"success": True, "practice_streak": new_state, "streak": view}


@router.get("/streak")
async def daily_fix_streak(user: User = Depends(get_current_user)):
    """Practice-streak view — current/best/done_today/at_risk."""
    return await get_practice_streak_view(db, user.user_id)
