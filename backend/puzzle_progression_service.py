"""
Puzzle Progression Service

Implements adaptive difficulty progression for puzzles.
Tracks user performance and adjusts puzzle difficulty dynamically.
"""

from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any
from motor.motor_asyncio import AsyncIOMotorDatabase
import logging
import math

logger = logging.getLogger(__name__)

# Difficulty levels with rating ranges
DIFFICULTY_LEVELS = {
    "beginner": {"min": 0, "max": 800, "label": "Beginner", "color": "green"},
    "easy": {"min": 800, "max": 1200, "label": "Easy", "color": "emerald"},
    "intermediate": {"min": 1200, "max": 1600, "label": "Intermediate", "color": "amber"},
    "advanced": {"min": 1600, "max": 2000, "label": "Advanced", "color": "orange"},
    "expert": {"min": 2000, "max": 2400, "label": "Expert", "color": "red"},
    "master": {"min": 2400, "max": 3000, "label": "Master", "color": "purple"}
}

# Starting rating for new users
DEFAULT_PUZZLE_RATING = 1200

# Rating change constants (similar to Elo system)
K_FACTOR = 32  # How much ratings change per puzzle


def get_difficulty_for_rating(rating: int) -> str:
    """Get difficulty level name for a given rating."""
    for level, config in DIFFICULTY_LEVELS.items():
        if config["min"] <= rating < config["max"]:
            return level
    return "master" if rating >= 2400 else "beginner"


def get_level_config(level: str) -> Dict:
    """Get configuration for a difficulty level."""
    return DIFFICULTY_LEVELS.get(level, DIFFICULTY_LEVELS["intermediate"])


def calculate_expected_score(user_rating: int, puzzle_rating: int) -> float:
    """Calculate expected probability of solving a puzzle (Elo formula)."""
    return 1 / (1 + 10 ** ((puzzle_rating - user_rating) / 400))


def calculate_rating_change(user_rating: int, puzzle_rating: int, solved: bool) -> int:
    """Calculate rating change after solving/failing a puzzle."""
    expected = calculate_expected_score(user_rating, puzzle_rating)
    actual = 1.0 if solved else 0.0
    change = K_FACTOR * (actual - expected)
    return int(round(change))


async def get_user_puzzle_progress(
    db: AsyncIOMotorDatabase,
    user_id: str
) -> Dict:
    """
    Get user's puzzle progression data including rating, level, and stats.
    """
    # Get or create user's puzzle progress document
    progress = await db.puzzle_progress.find_one({"user_id": user_id})
    
    if not progress:
        # Initialize new user progress
        progress = {
            "user_id": user_id,
            "puzzle_rating": DEFAULT_PUZZLE_RATING,
            "highest_rating": DEFAULT_PUZZLE_RATING,
            "total_puzzles": 0,
            "puzzles_solved": 0,
            "current_streak": 0,
            "best_streak": 0,
            "rating_history": [],
            "level_ups": 0,
            "achievements": [],
            "last_puzzle_at": None,
            "created_at": datetime.now(timezone.utc)
        }
        await db.puzzle_progress.insert_one(progress)
    
    # Calculate derived fields
    current_level = get_difficulty_for_rating(progress["puzzle_rating"])
    level_config = get_level_config(current_level)
    
    # Calculate progress to next level
    rating = progress["puzzle_rating"]
    level_min = level_config["min"]
    level_max = level_config["max"]
    progress_in_level = ((rating - level_min) / (level_max - level_min)) * 100 if level_max > level_min else 100
    
    # Get next level
    levels = list(DIFFICULTY_LEVELS.keys())
    current_idx = levels.index(current_level)
    next_level = levels[current_idx + 1] if current_idx < len(levels) - 1 else None
    points_to_next = level_max - rating if next_level else 0
    
    # Calculate recent performance (last 20 puzzles)
    recent_attempts = await db.puzzle_attempts_history.find(
        {"user_id": user_id}
    ).sort("timestamp", -1).limit(20).to_list(20)
    
    recent_solved = sum(1 for a in recent_attempts if a.get("solved"))
    recent_accuracy = (recent_solved / len(recent_attempts) * 100) if recent_attempts else 0
    
    return {
        "puzzle_rating": progress["puzzle_rating"],
        "highest_rating": progress.get("highest_rating", progress["puzzle_rating"]),
        "current_level": current_level,
        "level_label": level_config["label"],
        "level_color": level_config["color"],
        "progress_in_level": round(progress_in_level, 1),
        "next_level": next_level,
        "next_level_label": DIFFICULTY_LEVELS.get(next_level, {}).get("label"),
        "points_to_next_level": points_to_next,
        "total_puzzles": progress.get("total_puzzles", 0),
        "puzzles_solved": progress.get("puzzles_solved", 0),
        "solve_rate": round((progress.get("puzzles_solved", 0) / progress.get("total_puzzles", 1)) * 100, 1) if progress.get("total_puzzles", 0) > 0 else 0,
        "current_streak": progress.get("current_streak", 0),
        "best_streak": progress.get("best_streak", 0),
        "recent_accuracy": round(recent_accuracy, 1),
        "level_ups": progress.get("level_ups", 0),
        "achievements": progress.get("achievements", []),
        "last_puzzle_at": progress.get("last_puzzle_at").isoformat() if progress.get("last_puzzle_at") else None
    }


async def record_puzzle_attempt(
    db: AsyncIOMotorDatabase,
    user_id: str,
    puzzle_id: str,
    puzzle_difficulty: str,
    solved: bool,
    time_taken: Optional[int] = None
) -> Dict:
    """
    Record a puzzle attempt and update user's rating.
    
    Returns the rating change and any level-up information.
    """
    # Get current progress
    progress = await db.puzzle_progress.find_one({"user_id": user_id})
    
    if not progress:
        progress = {
            "user_id": user_id,
            "puzzle_rating": DEFAULT_PUZZLE_RATING,
            "highest_rating": DEFAULT_PUZZLE_RATING,
            "total_puzzles": 0,
            "puzzles_solved": 0,
            "current_streak": 0,
            "best_streak": 0,
            "rating_history": [],
            "level_ups": 0,
            "achievements": [],
            "created_at": datetime.now(timezone.utc)
        }
        await db.puzzle_progress.insert_one(progress)
    
    old_rating = progress["puzzle_rating"]
    old_level = get_difficulty_for_rating(old_rating)
    
    # Estimate puzzle rating based on difficulty
    puzzle_ratings = {
        "beginner": 600,
        "easy": 1000,
        "intermediate": 1400,
        "advanced": 1800,
        "expert": 2200,
        "master": 2600,
        "hard": 1600,  # Alias
        "medium": 1200  # Alias
    }
    puzzle_rating = puzzle_ratings.get(puzzle_difficulty, 1400)
    
    # Calculate rating change
    rating_change = calculate_rating_change(old_rating, puzzle_rating, solved)
    new_rating = max(100, old_rating + rating_change)  # Minimum rating of 100
    
    new_level = get_difficulty_for_rating(new_rating)
    leveled_up = new_level != old_level and rating_change > 0
    
    # Update streak
    if solved:
        new_streak = progress.get("current_streak", 0) + 1
    else:
        new_streak = 0
    
    best_streak = max(progress.get("best_streak", 0), new_streak)
    
    # Check for achievements
    new_achievements = []
    existing_achievements = set(progress.get("achievements", []))
    
    # Streak achievements
    if new_streak >= 5 and "streak_5" not in existing_achievements:
        new_achievements.append({"id": "streak_5", "name": "On Fire!", "desc": "5 puzzles in a row"})
    if new_streak >= 10 and "streak_10" not in existing_achievements:
        new_achievements.append({"id": "streak_10", "name": "Unstoppable!", "desc": "10 puzzles in a row"})
    if new_streak >= 25 and "streak_25" not in existing_achievements:
        new_achievements.append({"id": "streak_25", "name": "Puzzle Master", "desc": "25 puzzles in a row"})
    
    # Milestone achievements
    total_solved = progress.get("puzzles_solved", 0) + (1 if solved else 0)
    if total_solved >= 10 and "solved_10" not in existing_achievements:
        new_achievements.append({"id": "solved_10", "name": "Getting Started", "desc": "Solved 10 puzzles"})
    if total_solved >= 50 and "solved_50" not in existing_achievements:
        new_achievements.append({"id": "solved_50", "name": "Puzzle Enthusiast", "desc": "Solved 50 puzzles"})
    if total_solved >= 100 and "solved_100" not in existing_achievements:
        new_achievements.append({"id": "solved_100", "name": "Century Club", "desc": "Solved 100 puzzles"})
    
    # Level achievements
    if new_level == "advanced" and "reach_advanced" not in existing_achievements:
        new_achievements.append({"id": "reach_advanced", "name": "Advanced Player", "desc": "Reached Advanced level"})
    if new_level == "expert" and "reach_expert" not in existing_achievements:
        new_achievements.append({"id": "reach_expert", "name": "Expert Tactician", "desc": "Reached Expert level"})
    if new_level == "master" and "reach_master" not in existing_achievements:
        new_achievements.append({"id": "reach_master", "name": "Puzzle Grandmaster", "desc": "Reached Master level"})
    
    # Record attempt in history
    await db.puzzle_attempts_history.insert_one({
        "user_id": user_id,
        "puzzle_id": puzzle_id,
        "puzzle_difficulty": puzzle_difficulty,
        "puzzle_rating": puzzle_rating,
        "solved": solved,
        "time_taken": time_taken,
        "rating_before": old_rating,
        "rating_after": new_rating,
        "rating_change": rating_change,
        "timestamp": datetime.now(timezone.utc)
    })
    
    # Update progress
    update = {
        "$set": {
            "puzzle_rating": new_rating,
            "current_streak": new_streak,
            "best_streak": best_streak,
            "last_puzzle_at": datetime.now(timezone.utc),
            "highest_rating": max(progress.get("highest_rating", 0), new_rating)
        },
        "$inc": {
            "total_puzzles": 1,
            "puzzles_solved": 1 if solved else 0,
            "level_ups": 1 if leveled_up else 0
        },
        "$push": {
            "rating_history": {
                "$each": [{"rating": new_rating, "timestamp": datetime.now(timezone.utc)}],
                "$slice": -100  # Keep last 100 entries
            }
        }
    }
    
    if new_achievements:
        update["$push"]["achievements"] = {"$each": [a["id"] for a in new_achievements]}
    
    await db.puzzle_progress.update_one(
        {"user_id": user_id},
        update
    )
    
    return {
        "old_rating": old_rating,
        "new_rating": new_rating,
        "rating_change": rating_change,
        "old_level": old_level,
        "new_level": new_level,
        "leveled_up": leveled_up,
        "current_streak": new_streak,
        "best_streak": best_streak,
        "new_achievements": new_achievements,
        "level_config": get_level_config(new_level)
    }


async def get_recommended_puzzle_difficulty(
    db: AsyncIOMotorDatabase,
    user_id: str
) -> Dict:
    """
    Get the recommended puzzle difficulty range for a user.
    
    Returns a range slightly below to slightly above user's rating
    for optimal challenge.
    """
    progress = await get_user_puzzle_progress(db, user_id)
    rating = progress["puzzle_rating"]
    
    # Recommend puzzles in a range around user's rating
    # Slightly more challenging on average (positive skew)
    min_rating = rating - 200
    max_rating = rating + 300
    
    # Map to difficulty levels
    difficulties = []
    for level, config in DIFFICULTY_LEVELS.items():
        if config["min"] < max_rating and config["max"] > min_rating:
            difficulties.append(level)
    
    return {
        "user_rating": rating,
        "recommended_min": min_rating,
        "recommended_max": max_rating,
        "recommended_difficulties": difficulties,
        "primary_difficulty": get_difficulty_for_rating(rating + 50)  # Slight challenge
    }


async def get_puzzle_leaderboard(
    db: AsyncIOMotorDatabase,
    limit: int = 20
) -> List[Dict]:
    """
    Get global puzzle rating leaderboard.
    """
    leaderboard = await db.puzzle_progress.find(
        {"total_puzzles": {"$gte": 10}}  # Minimum 10 puzzles to qualify
    ).sort("puzzle_rating", -1).limit(limit).to_list(limit)
    
    result = []
    for i, entry in enumerate(leaderboard, 1):
        # Get username
        user = await db.users.find_one(
            {"user_id": entry["user_id"]},
            {"username": 1, "display_name": 1}
        )
        username = user.get("display_name") or user.get("username", "Anonymous") if user else "Anonymous"
        
        result.append({
            "rank": i,
            "username": username,
            "puzzle_rating": entry["puzzle_rating"],
            "level": get_difficulty_for_rating(entry["puzzle_rating"]),
            "level_label": get_level_config(get_difficulty_for_rating(entry["puzzle_rating"]))["label"],
            "puzzles_solved": entry.get("puzzles_solved", 0),
            "best_streak": entry.get("best_streak", 0)
        })
    
    return result
