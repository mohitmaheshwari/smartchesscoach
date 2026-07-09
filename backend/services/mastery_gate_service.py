"""
Mastery Gate Service — Define when a player has "beaten" a pattern.

Phase 1, 2026-07-09: Mastery gates provide closure on coaching patterns.
When a gate is crossed, coaching rotates to the next focus area and celebration
is shown to the player (mastery badge / milestone).
"""

import logging
from typing import Dict, Optional, List
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

# Mastery thresholds per focus area
MASTERY_THRESHOLDS = {
    "time_management": {
        "min_sessions": 3,           # Achieved in at least 3 PWC sessions
        "clean_streak": 5,           # OR 5 consecutive games with >70%
        "total_games_threshold": 10, # OR 10+ total games with >70% avg
        "achievement_rate": 0.70,    # Achieved when matched >= 70% of moments
    },
    "piece_safety": {
        "min_sessions": 3,
        "clean_streak": 5,
        "total_games_threshold": 10,
        "achievement_rate": 0.75,  # Slightly higher bar for piece safety
    },
    "king_safety": {
        "min_sessions": 3,
        "clean_streak": 5,
        "total_games_threshold": 10,
        "achievement_rate": 0.70,
    },
    "missed_tactic": {
        "min_sessions": 2,           # Faster mastery (tactics are learnable)
        "clean_streak": 4,
        "total_games_threshold": 8,
        "achievement_rate": 0.65,  # Lower bar (harder to achieve 100%)
    },
}


async def check_mastery_gate(
    db,
    user_id: str,
    focus_area: str
) -> Optional[Dict]:
    """
    Check if a player has achieved mastery on a focus area.

    Returns:
        {
            is_mastered: bool,
            reason: str,                   # Why they achieved/haven't achieved mastery
            stats: {
                sessions_count: int,
                achieved_sessions: int,
                clean_streak_current: int,
                avg_achievement_rate: float,
            },
            celebration_message: str,      # Shown when is_mastered=True
        }
    """

    try:
        thresholds = MASTERY_THRESHOLDS.get(focus_area)
        if not thresholds:
            return None

        # Get all PWC sessions for this user with this focus area
        sessions_cursor = db.coach_sessions.find(
            {
                "user_id": user_id,
                "session_goal.focus_area": focus_area,
                "status": "ended"
            },
            {"_id": 0, "session_id": 1, "ended_at": 1, "mission_scoreboard": 1}
        ).sort("ended_at", -1)

        sessions = await sessions_cursor.to_list(length=None)

        if len(sessions) == 0:
            return {
                "is_mastered": False,
                "reason": f"No sessions completed yet for {focus_area}",
                "stats": {
                    "sessions_count": 0,
                    "achieved_sessions": 0,
                    "clean_streak_current": 0,
                    "avg_achievement_rate": 0.0,
                },
                "celebration_message": None,
            }

        # Analyze sessions for achievement rate
        achieved_sessions = 0
        achievement_rates = []
        clean_streak = 0
        max_streak = 0

        for session in sessions:
            mission = session.get("mission_scoreboard", {})
            matched = mission.get("matched_moments", 0)
            total = mission.get("total_moments", 1)

            if total > 0:
                rate = matched / total
                achievement_rates.append(rate)

                if rate >= thresholds["achievement_rate"]:
                    achieved_sessions += 1
                    clean_streak += 1
                    max_streak = max(max_streak, clean_streak)
                else:
                    clean_streak = 0

        avg_rate = sum(achievement_rates) / len(achievement_rates) if achievement_rates else 0.0

        # Check mastery conditions (OR logic)
        is_mastered = (
            (achieved_sessions >= thresholds["min_sessions"])  # Condition 1: min sessions
            or (max_streak >= thresholds["clean_streak"])      # Condition 2: clean streak
            or (                                                # Condition 3: long-term average
                len(sessions) >= thresholds["total_games_threshold"]
                and avg_rate >= thresholds["achievement_rate"]
            )
        )

        reason = ""
        if is_mastered:
            if achieved_sessions >= thresholds["min_sessions"]:
                reason = f"Achieved {focus_area} in {achieved_sessions}/{len(sessions)} sessions"
            elif max_streak >= thresholds["clean_streak"]:
                reason = f"Consistent {max_streak}-session clean streak"
            else:
                reason = f"Long-term average: {int(avg_rate*100)}% success rate over {len(sessions)} sessions"

        celebration_msg = _get_celebration_message(focus_area) if is_mastered else None

        return {
            "is_mastered": is_mastered,
            "reason": reason,
            "stats": {
                "sessions_count": len(sessions),
                "achieved_sessions": achieved_sessions,
                "clean_streak_current": clean_streak,
                "avg_achievement_rate": round(avg_rate, 2),
            },
            "celebration_message": celebration_msg,
        }

    except Exception as e:
        logger.warning(f"Mastery gate check failed for {user_id}/{focus_area}: {e}")
        return None


def _get_celebration_message(focus_area: str) -> str:
    """Generate celebration message for mastery achievement."""

    messages = {
        "time_management": "🎯 You've mastered time management! You're taking the clock seriously, and it's winning you games. Next: piece safety.",
        "piece_safety": "🛡️ You've mastered piece safety! Your pieces are protected, and your opponents can't exploit undefended material. Next: king safety.",
        "king_safety": "👑 You've mastered king safety! Your king is a fortress. Time to focus on: missed tactics.",
        "missed_tactic": "⚡ You've mastered tactical vision! You're spotting forcing moves before your opponents. You're playing stronger chess.",
    }

    return messages.get(focus_area, f"🎓 You've mastered {focus_area}!")


async def suggest_next_focus(
    db,
    user_id: str,
    current_focus: str
) -> Optional[str]:
    """
    Suggest the next focus area based on current mastery and weaknesses.

    Rotation priority (if current is mastered):
    time_management → piece_safety → king_safety → missed_tactic → time_management
    """

    rotation = {
        "time_management": "piece_safety",
        "piece_safety": "king_safety",
        "king_safety": "missed_tactic",
        "missed_tactic": "time_management",
    }

    return rotation.get(current_focus)


async def get_mastery_summary(db, user_id: str) -> Dict:
    """
    Get mastery status across all focus areas.

    Returns:
        {
            total_mastered: int,
            mastered_areas: [str],
            current_focus: str,
            progress: {
                time_management: {is_mastered, pct_to_mastery},
                piece_safety: {...},
                ...
            }
        }
    """

    try:
        summary = {
            "total_mastered": 0,
            "mastered_areas": [],
            "progress": {},
        }

        for focus_area in MASTERY_THRESHOLDS.keys():
            gate = await check_mastery_gate(db, user_id, focus_area)

            if gate:
                if gate["is_mastered"]:
                    summary["total_mastered"] += 1
                    summary["mastered_areas"].append(focus_area)

                summary["progress"][focus_area] = {
                    "is_mastered": gate["is_mastered"],
                    "achieved_sessions": gate["stats"]["achieved_sessions"],
                    "min_required": MASTERY_THRESHOLDS[focus_area]["min_sessions"],
                    "pct_to_mastery": min(
                        100,
                        int(
                            100
                            * gate["stats"]["achieved_sessions"]
                            / MASTERY_THRESHOLDS[focus_area]["min_sessions"]
                        ),
                    ),
                }

        return summary

    except Exception as e:
        logger.warning(f"Mastery summary failed for {user_id}: {e}")
        return {"total_mastered": 0, "mastered_areas": [], "progress": {}}
