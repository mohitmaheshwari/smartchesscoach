"""
Habit Rotation Service for Chess Coach AI

Handles:
1. Tracking user improvement on habits
2. Auto-rotating habits when user demonstrates mastery
3. Managing habit states (active, improving, resolved)
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

# Thresholds for habit improvement
CONSECUTIVE_CORRECT_THRESHOLD = 4  # Correct PDR answers in a row for same habit
TOTAL_CORRECT_THRESHOLD = 6  # Total correct out of last 8 attempts
MIN_ATTEMPTS_FOR_ROTATION = 5  # Minimum attempts before considering rotation


async def get_habit_performance(db, user_id: str, habit: str) -> Dict[str, Any]:
    """
    Get user's performance on a specific habit.
    
    Returns:
        {
            "habit": "one_move_blunders",
            "total_attempts": 10,
            "correct_attempts": 7,
            "consecutive_correct": 3,
            "success_rate": 0.7,
            "status": "active" | "improving" | "resolved"
        }
    """
    # Get recent reflection results for this habit
    # We need to match habits by looking at the game's identified weaknesses
    
    # Get user's games with this habit
    games_with_habit = await db.game_analyses.find(
        {
            "user_id": user_id,
            "$or": [
                {"identified_weaknesses": {"$elemMatch": {"subcategory": {"$regex": habit, "$options": "i"}}}},
                {"weaknesses": {"$regex": habit, "$options": "i"}}
            ]
        },
        {"_id": 0, "game_id": 1}
    ).to_list(50)
    
    game_ids = [g["game_id"] for g in games_with_habit]
    
    if not game_ids:
        return {
            "habit": habit,
            "total_attempts": 0,
            "correct_attempts": 0,
            "consecutive_correct": 0,
            "success_rate": 0,
            "status": "active"
        }
    
    # Get reflection results for these games
    results = await db.reflection_results.find(
        {
            "user_id": user_id,
            "game_id": {"$in": game_ids}
        },
        {"_id": 0, "move_correct": 1, "created_at": 1}
    ).sort("created_at", -1).to_list(20)
    
    if not results:
        return {
            "habit": habit,
            "total_attempts": 0,
            "correct_attempts": 0,
            "consecutive_correct": 0,
            "success_rate": 0,
            "status": "active"
        }
    
    total = len(results)
    correct = sum(1 for r in results if r.get("move_correct", False))
    
    # Calculate consecutive correct from most recent
    consecutive = 0
    for r in results:
        if r.get("move_correct", False):
            consecutive += 1
        else:
            break
    
    success_rate = correct / total if total > 0 else 0
    
    # Determine status
    status = "active"
    if total >= MIN_ATTEMPTS_FOR_ROTATION:
        if consecutive >= CONSECUTIVE_CORRECT_THRESHOLD or (total >= 8 and correct >= TOTAL_CORRECT_THRESHOLD):
            status = "resolved"
        elif success_rate >= 0.6:
            status = "improving"
    
    return {
        "habit": habit,
        "total_attempts": total,
        "correct_attempts": correct,
        "consecutive_correct": consecutive,
        "success_rate": round(success_rate, 2),
        "status": status
    }


async def check_and_rotate_habit(db, user_id: str) -> Dict[str, Any]:
    """
    Check if current dominant habit should be rotated.
    
    Returns:
        {
            "rotated": True/False,
            "previous_habit": "one_move_blunders",
            "new_habit": "time_trouble",
            "reason": "Mastered after 6 correct in a row"
        }
    """
    # Get current profile
    profile = await db.player_profiles.find_one(
        {"user_id": user_id},
        {"_id": 0, "top_weaknesses": 1, "resolved_habits": 1, "improving_habits": 1}
    )
    
    if not profile or not profile.get("top_weaknesses"):
        return {"rotated": False, "reason": "No weaknesses tracked"}
    
    top_weaknesses = profile.get("top_weaknesses", [])
    resolved_habits = profile.get("resolved_habits", [])
    
    if not top_weaknesses:
        return {"rotated": False, "reason": "No active weaknesses"}
    
    # Get current dominant habit
    current_habit = top_weaknesses[0]
    habit_name = current_habit.get("subcategory", "") if isinstance(current_habit, dict) else str(current_habit)
    
    # Check performance on current habit
    performance = await get_habit_performance(db, user_id, habit_name)
    
    if performance["status"] != "resolved":
        return {
            "rotated": False,
            "current_habit": habit_name,
            "performance": performance,
            "reason": f"Still working on {habit_name} ({performance['correct_attempts']}/{performance['total_attempts']} correct)"
        }
    
    # Habit is resolved - rotate!
    # Move current habit to resolved list
    resolved_entry = {
        "habit": habit_name,
        "resolved_at": datetime.now(timezone.utc).isoformat(),
        "final_stats": performance
    }
    
    # Find next habit (from remaining weaknesses)
    new_habit = None
    remaining_weaknesses = []
    
    for w in top_weaknesses[1:]:
        w_name = w.get("subcategory", "") if isinstance(w, dict) else str(w)
        # Check if not already resolved
        if not any(r.get("habit") == w_name for r in resolved_habits):
            if new_habit is None:
                new_habit = w
            remaining_weaknesses.append(w)
    
    # Update profile
    update_data = {
        "$push": {"resolved_habits": resolved_entry},
        "$set": {
            "top_weaknesses": remaining_weaknesses,
            "last_habit_rotation": datetime.now(timezone.utc).isoformat()
        }
    }
    
    if remaining_weaknesses:
        update_data["$set"]["current_dominant_habit"] = remaining_weaknesses[0]
    
    await db.player_profiles.update_one(
        {"user_id": user_id},
        update_data,
        upsert=False
    )
    
    new_habit_name = new_habit.get("subcategory", "") if isinstance(new_habit, dict) else str(new_habit) if new_habit else "None"
    
    logger.info(f"Habit rotated for user {user_id}: {habit_name} -> {new_habit_name}")
    
    return {
        "rotated": True,
        "previous_habit": habit_name,
        "new_habit": new_habit_name,
        "reason": f"Mastered {habit_name} ({performance['consecutive_correct']} consecutive correct)",
        "resolved_stats": performance
    }


async def get_all_habit_statuses(db, user_id: str) -> List[Dict[str, Any]]:
    """
    Get status of all tracked habits for a user.
    
    Returns list of habit statuses with their current state.
    """
    profile = await db.player_profiles.find_one(
        {"user_id": user_id},
        {"_id": 0, "top_weaknesses": 1, "resolved_habits": 1}
    )
    
    if not profile:
        return []
    
    statuses = []
    
    # Active habits
    for w in profile.get("top_weaknesses", []):
        habit_name = w.get("subcategory", "") if isinstance(w, dict) else str(w)
        if habit_name:
            perf = await get_habit_performance(db, user_id, habit_name)
            statuses.append({
                **perf,
                "is_dominant": len(statuses) == 0  # First one is dominant
            })
    
    # Resolved habits
    for r in profile.get("resolved_habits", []):
        statuses.append({
            "habit": r.get("habit", ""),
            "status": "resolved",
            "resolved_at": r.get("resolved_at"),
            "final_stats": r.get("final_stats", {}),
            "is_dominant": False
        })
    
    return statuses


async def update_habit_after_reflection(db, user_id: str, game_id: str, move_correct: bool) -> Optional[Dict]:
    """
    Called after each PDR reflection to check if habit should rotate.
    
    Returns rotation info if a rotation occurred.
    """
    # Check if we should rotate
    rotation_result = await check_and_rotate_habit(db, user_id)
    
    if rotation_result.get("rotated"):
        return rotation_result
    
    return None
