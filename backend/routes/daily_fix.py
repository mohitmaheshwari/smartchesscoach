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

from fastapi import APIRouter, Depends

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

    return res


@router.post("/complete")
async def daily_fix_complete(user: User = Depends(get_current_user)):
    """Mark today's daily fix complete → advance the day-based practice streak.
    Idempotent per day (calling twice in one day counts once)."""
    new_state = await record_daily_fix_completion(db, user.user_id)
    view = await get_practice_streak_view(db, user.user_id)
    return {"success": True, "practice_streak": new_state, "streak": view}


@router.get("/streak")
async def daily_fix_streak(user: User = Depends(get_current_user)):
    """Practice-streak view — current/best/done_today/at_risk."""
    return await get_practice_streak_view(db, user.user_id)
