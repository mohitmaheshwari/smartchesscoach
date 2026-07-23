"""
Daily Fix resolver — "what is today's fix for this user, and is it done?"

The single orchestration point for the Daily Fix (docs/daily_fix_scope.md). It:
  1. Resolves the user's locked focus (the primary_weakness_picker's
     user_active_focus — the rating-aware picker), falling back to the brain
     focus only if none.
  2. Routes focus → drill type:
       - time_management  → the timed rush-test drill (rush_test_drill.py)
       - any board weakness → the existing mission drill (reused, not rebuilt)
  3. Attaches the practice-streak view (current/done_today/at_risk).

Every focus therefore maps to a drill a drill can actually improve — board
weaknesses to board drills, time trouble to a timed test. No user is drilled on
the wrong thing, and no focus is left un-drillable.
"""
from typing import Any, Dict, Optional

from services.rush_test_drill import build_rush_test_drill
from services.mistake_streak_service import get_practice_streak_view
from services.focus_bridge import get_active_focus_bundle

TIME_FOCUS = "time_management"


async def _resolve_focus(db, user_id: str) -> Optional[str]:
    """The locked weakness focus. Prefer the rating-aware picker
    (user_active_focus, via the canonical focus_bridge reader); fall back
    to the curriculum-brain focus. Was a standalone re-query of
    user_active_focus with the same filter focus_bridge already uses —
    consolidated so this and every other "what's the user's focus" surface
    share one query (docs/coach_mirror_activation_scope.md follow-up audit,
    2026-07-23)."""
    bundle = await get_active_focus_bundle(db, user_id)
    if bundle and bundle.get("topic_key"):
        return bundle["topic_key"]
    cm = await db.coach_memory.find_one({"user_id": user_id}, {"learning.current_focus": 1})
    return (cm or {}).get("learning", {}).get("current_focus")


async def resolve_daily_fix(db, user_id: str, limit: int = 5, today: Any = None) -> Dict[str, Any]:
    """Return today's fix for the user: the focus, the drill type, the drills
    (for the rush-test path), and the practice-streak view.

    For board focuses this returns drill_type='board' and defers the actual
    positions to the existing mission flow (single source — we do not rebuild
    board drilling here). For time_management it returns drill_type='rush_test'
    with ready-to-play timed drills.
    """
    focus = await _resolve_focus(db, user_id)
    streak = await get_practice_streak_view(db, user_id, today=today)

    result: Dict[str, Any] = {
        "focus": focus,
        "streak": streak,
        "drills": [],
    }

    if focus == TIME_FOCUS:
        drills = await build_rush_test_drill(db, user_id, limit=limit)
        result["drill_type"] = "rush_test"
        result["drills"] = drills
        result["has_drills"] = len(drills) > 0
        # If a time-focus user somehow has no rushed positions to drill, the
        # caller should fall back to the board mission rather than show nothing.
        result["fallback_to_board"] = len(drills) == 0
    else:
        result["drill_type"] = "board"
        result["has_drills"] = focus is not None
        result["fallback_to_board"] = False

    return result
