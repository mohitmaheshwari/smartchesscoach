"""
Gamification Service - XP, Levels, Achievements, Streaks
Makes the chess coaching app addictive and engaging
"""

from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from bson import ObjectId
import os
from motor.motor_asyncio import AsyncIOMotorClient

# MongoDB connection
MONGO_URL = os.environ.get('MONGO_URL')
DB_NAME = os.environ.get('DB_NAME', 'chess_coach')

client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]

# Collections
user_progress_collection = db['user_progress']
achievements_collection = db['user_achievements']

# =============================================================================
# LEVEL SYSTEM - Chess-themed ranks
# =============================================================================

LEVELS = [
    {"level": 1, "name": "Pawn", "xp_required": 0, "icon": "♟"},
    {"level": 2, "name": "Pawn II", "xp_required": 100, "icon": "♟"},
    {"level": 3, "name": "Pawn III", "xp_required": 250, "icon": "♟"},
    {"level": 4, "name": "Knight", "xp_required": 500, "icon": "♞"},
    {"level": 5, "name": "Knight II", "xp_required": 800, "icon": "♞"},
    {"level": 6, "name": "Knight III", "xp_required": 1200, "icon": "♞"},
    {"level": 7, "name": "Bishop", "xp_required": 1700, "icon": "♝"},
    {"level": 8, "name": "Bishop II", "xp_required": 2300, "icon": "♝"},
    {"level": 9, "name": "Bishop III", "xp_required": 3000, "icon": "♝"},
    {"level": 10, "name": "Rook", "xp_required": 4000, "icon": "♜"},
    {"level": 11, "name": "Rook II", "xp_required": 5200, "icon": "♜"},
    {"level": 12, "name": "Rook III", "xp_required": 6500, "icon": "♜"},
    {"level": 13, "name": "Queen", "xp_required": 8000, "icon": "♛"},
    {"level": 14, "name": "Queen II", "xp_required": 10000, "icon": "♛"},
    {"level": 15, "name": "Queen III", "xp_required": 12500, "icon": "♛"},
    {"level": 16, "name": "King", "xp_required": 15500, "icon": "♚"},
    {"level": 17, "name": "King II", "xp_required": 19000, "icon": "♚"},
    {"level": 18, "name": "King III", "xp_required": 23000, "icon": "♚"},
    {"level": 19, "name": "Master", "xp_required": 28000, "icon": "👑"},
    {"level": 20, "name": "Grandmaster", "xp_required": 35000, "icon": "🏆"},
]

# =============================================================================
# XP REWARDS - Actions that earn XP
# =============================================================================

XP_REWARDS = {
    "daily_login": 10,
    "game_imported": 5,
    "game_analyzed": 25,
    "puzzle_solved": 15,
    "puzzle_solved_fast": 25,  # Under 30 seconds
    "streak_day": 20,  # Bonus per streak day
    "streak_week": 100,  # 7-day streak bonus
    "streak_month": 500,  # 30-day streak bonus
    "first_game": 50,
    "accuracy_90_plus": 30,  # Game with 90%+ accuracy
    "no_blunders": 20,  # Game without blunders
    "achievement_unlocked": 50,
}

# =============================================================================
# ACHIEVEMENTS DEFINITIONS
# =============================================================================

ACHIEVEMENTS = [
    # Getting Started
    {
        "id": "first_steps",
        "name": "First Steps",
        "description": "Import your first game",
        "icon": "🎯",
        "category": "beginner",
        "xp_reward": 50,
        "condition": {"type": "games_imported", "count": 1}
    },
    {
        "id": "curious_mind",
        "name": "Curious Mind",
        "description": "Analyze your first game",
        "icon": "🔍",
        "category": "beginner",
        "xp_reward": 50,
        "condition": {"type": "games_analyzed", "count": 1}
    },
    {
        "id": "puzzle_starter",
        "name": "Puzzle Starter",
        "description": "Solve your first puzzle",
        "icon": "🧩",
        "category": "beginner",
        "xp_reward": 50,
        "condition": {"type": "puzzles_solved", "count": 1}
    },
    
    # Streak Achievements
    {
        "id": "on_fire",
        "name": "On Fire",
        "description": "Maintain a 3-day streak",
        "icon": "🔥",
        "category": "streak",
        "xp_reward": 75,
        "condition": {"type": "streak_days", "count": 3}
    },
    {
        "id": "dedicated_student",
        "name": "Dedicated Student",
        "description": "Maintain a 7-day streak",
        "icon": "📚",
        "category": "streak",
        "xp_reward": 150,
        "condition": {"type": "streak_days", "count": 7}
    },
    {
        "id": "vishys_apprentice",
        "name": "Vishy's Apprentice",
        "description": "Maintain a 14-day streak",
        "icon": "🌟",
        "category": "streak",
        "xp_reward": 300,
        "condition": {"type": "streak_days", "count": 14}
    },
    {
        "id": "chess_warrior",
        "name": "Chess Warrior",
        "description": "Maintain a 30-day streak",
        "icon": "⚔️",
        "category": "streak",
        "xp_reward": 500,
        "condition": {"type": "streak_days", "count": 30}
    },
    
    # Analysis Achievements
    {
        "id": "analyst",
        "name": "Analyst",
        "description": "Analyze 5 games",
        "icon": "📊",
        "category": "analysis",
        "xp_reward": 100,
        "condition": {"type": "games_analyzed", "count": 5}
    },
    {
        "id": "deep_thinker",
        "name": "Deep Thinker",
        "description": "Analyze 25 games",
        "icon": "🧠",
        "category": "analysis",
        "xp_reward": 250,
        "condition": {"type": "games_analyzed", "count": 25}
    },
    {
        "id": "game_scholar",
        "name": "Game Scholar",
        "description": "Analyze 100 games",
        "icon": "🎓",
        "category": "analysis",
        "xp_reward": 500,
        "condition": {"type": "games_analyzed", "count": 100}
    },
    
    # Accuracy Achievements
    {
        "id": "sharp_player",
        "name": "Sharp Player",
        "description": "Achieve 80%+ accuracy in a game",
        "icon": "🎯",
        "category": "accuracy",
        "xp_reward": 100,
        "condition": {"type": "accuracy_game", "value": 80}
    },
    {
        "id": "precision_master",
        "name": "Precision Master",
        "description": "Achieve 90%+ accuracy in a game",
        "icon": "💎",
        "category": "accuracy",
        "xp_reward": 200,
        "condition": {"type": "accuracy_game", "value": 90}
    },
    {
        "id": "computer_like",
        "name": "Computer-Like",
        "description": "Achieve 95%+ accuracy in a game",
        "icon": "🤖",
        "category": "accuracy",
        "xp_reward": 350,
        "condition": {"type": "accuracy_game", "value": 95}
    },
    
    # Blunder-Free Achievements
    {
        "id": "careful_player",
        "name": "Careful Player",
        "description": "Play a game without blunders",
        "icon": "🛡️",
        "category": "quality",
        "xp_reward": 75,
        "condition": {"type": "no_blunders_game", "count": 1}
    },
    {
        "id": "blunder_free_warrior",
        "name": "Blunder-Free Warrior",
        "description": "Play 5 games without blunders",
        "icon": "🏰",
        "category": "quality",
        "xp_reward": 200,
        "condition": {"type": "no_blunders_game", "count": 5}
    },
    {
        "id": "fortress",
        "name": "Fortress",
        "description": "Play 10 games without blunders",
        "icon": "🏯",
        "category": "quality",
        "xp_reward": 400,
        "condition": {"type": "no_blunders_game", "count": 10}
    },
    
    # Puzzle Achievements
    {
        "id": "tactical_eye",
        "name": "Tactical Eye",
        "description": "Solve 10 puzzles",
        "icon": "👁️",
        "category": "puzzles",
        "xp_reward": 100,
        "condition": {"type": "puzzles_solved", "count": 10}
    },
    {
        "id": "tactical_tiger",
        "name": "Tactical Tiger",
        "description": "Solve 50 puzzles",
        "icon": "🐯",
        "category": "puzzles",
        "xp_reward": 250,
        "condition": {"type": "puzzles_solved", "count": 50}
    },
    {
        "id": "puzzle_master",
        "name": "Puzzle Master",
        "description": "Solve 200 puzzles",
        "icon": "🧙",
        "category": "puzzles",
        "xp_reward": 500,
        "condition": {"type": "puzzles_solved", "count": 200}
    },
    {
        "id": "speed_demon",
        "name": "Speed Demon",
        "description": "Solve 10 puzzles in under 30 seconds each",
        "icon": "⚡",
        "category": "puzzles",
        "xp_reward": 200,
        "condition": {"type": "fast_puzzles", "count": 10}
    },
    
    # Level Achievements
    {
        "id": "rising_star",
        "name": "Rising Star",
        "description": "Reach Level 5 (Knight)",
        "icon": "⭐",
        "category": "level",
        "xp_reward": 100,
        "condition": {"type": "level_reached", "value": 5}
    },
    {
        "id": "climbing_ranks",
        "name": "Climbing Ranks",
        "description": "Reach Level 10 (Rook)",
        "icon": "📈",
        "category": "level",
        "xp_reward": 200,
        "condition": {"type": "level_reached", "value": 10}
    },
    {
        "id": "elite_player",
        "name": "Elite Player",
        "description": "Reach Level 15 (Queen III)",
        "icon": "👑",
        "category": "level",
        "xp_reward": 350,
        "condition": {"type": "level_reached", "value": 15}
    },
    {
        "id": "grandmaster_material",
        "name": "Grandmaster Material",
        "description": "Reach Level 20 (Grandmaster)",
        "icon": "🏆",
        "category": "level",
        "xp_reward": 1000,
        "condition": {"type": "level_reached", "value": 20}
    },
    
    # Special Achievements
    {
        "id": "early_bird",
        "name": "Early Bird",
        "description": "Practice before 7 AM",
        "icon": "🌅",
        "category": "special",
        "xp_reward": 50,
        "condition": {"type": "special", "key": "early_bird"}
    },
    {
        "id": "night_owl",
        "name": "Night Owl",
        "description": "Practice after 11 PM",
        "icon": "🦉",
        "category": "special",
        "xp_reward": 50,
        "condition": {"type": "special", "key": "night_owl"}
    },
    {
        "id": "weekend_warrior",
        "name": "Weekend Warrior",
        "description": "Practice on 4 consecutive weekends",
        "icon": "🗓️",
        "category": "special",
        "xp_reward": 150,
        "condition": {"type": "special", "key": "weekend_warrior"}
    },
]

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_level_for_xp(xp: int) -> dict:
    """Get the level info for a given XP amount"""
    current_level = LEVELS[0]
    for level in LEVELS:
        if xp >= level["xp_required"]:
            current_level = level
        else:
            break
    return current_level

def get_next_level(current_level: int) -> Optional[dict]:
    """Get the next level info"""
    for level in LEVELS:
        if level["level"] == current_level + 1:
            return level
    return None

def calculate_level_progress(xp: int) -> dict:
    """Calculate progress to next level"""
    current = get_level_for_xp(xp)
    next_level = get_next_level(current["level"])
    
    if not next_level:
        return {
            "current_level": current,
            "next_level": None,
            "progress_percent": 100,
            "xp_to_next": 0
        }
    
    xp_in_level = xp - current["xp_required"]
    xp_needed = next_level["xp_required"] - current["xp_required"]
    progress = (xp_in_level / xp_needed) * 100 if xp_needed > 0 else 100
    
    return {
        "current_level": current,
        "next_level": next_level,
        "progress_percent": min(progress, 100),
        "xp_to_next": next_level["xp_required"] - xp
    }

# =============================================================================
# USER PROGRESS FUNCTIONS
# =============================================================================

async def get_user_progress(user_id: str) -> dict:
    """Get or create user progress document"""
    progress = await user_progress_collection.find_one({"user_id": user_id})
    
    if not progress:
        # Create new progress document
        progress = {
            "user_id": user_id,
            "xp": 0,
            "level": 1,
            "games_imported": 0,
            "games_analyzed": 0,
            "puzzles_solved": 0,
            "fast_puzzles": 0,
            "no_blunders_games": 0,
            "best_accuracy": 0,
            "current_streak": 0,
            "longest_streak": 0,
            "last_activity_date": None,
            "streak_start_date": None,
            "total_play_time_minutes": 0,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }
        await user_progress_collection.insert_one(progress)
    
    # Remove MongoDB _id for JSON serialization
    progress.pop("_id", None)
    
    # Add level details
    level_info = calculate_level_progress(progress.get("xp", 0))
    progress["level_info"] = level_info
    
    return progress

async def add_xp(user_id: str, action: str, bonus_multiplier: float = 1.0) -> dict:
    """Add XP for an action and check for level up"""
    base_xp = XP_REWARDS.get(action, 0)
    xp_earned = int(base_xp * bonus_multiplier)
    
    if xp_earned <= 0:
        return {"xp_earned": 0, "leveled_up": False}
    
    # Get current progress
    progress = await get_user_progress(user_id)
    old_level = get_level_for_xp(progress.get("xp", 0))
    
    # Update XP
    new_xp = progress.get("xp", 0) + xp_earned
    new_level = get_level_for_xp(new_xp)
    
    await user_progress_collection.update_one(
        {"user_id": user_id},
        {
            "$inc": {"xp": xp_earned},
            "$set": {
                "level": new_level["level"],
                "updated_at": datetime.now(timezone.utc)
            }
        }
    )
    
    leveled_up = new_level["level"] > old_level["level"]
    
    # Check for level achievements
    if leveled_up:
        await check_and_award_achievements(user_id, "level_reached", new_level["level"])
    
    return {
        "xp_earned": xp_earned,
        "total_xp": new_xp,
        "leveled_up": leveled_up,
        "new_level": new_level if leveled_up else None,
        "action": action
    }

async def update_streak(user_id: str) -> dict:
    """Update user's daily streak"""
    progress = await get_user_progress(user_id)
    today = datetime.now(timezone.utc).date()
    last_activity = progress.get("last_activity_date")
    
    if last_activity:
        if isinstance(last_activity, str):
            last_activity = datetime.fromisoformat(last_activity.replace('Z', '+00:00')).date()
        elif isinstance(last_activity, datetime):
            last_activity = last_activity.date()
    
    current_streak = progress.get("current_streak", 0)
    longest_streak = progress.get("longest_streak", 0)
    streak_extended = False
    streak_reset = False
    xp_bonus = 0
    
    if last_activity is None:
        # First activity ever
        current_streak = 1
        streak_extended = True
    elif last_activity == today:
        # Already logged in today, no change
        pass
    elif last_activity == today - timedelta(days=1):
        # Consecutive day - extend streak
        current_streak += 1
        streak_extended = True
    else:
        # Streak broken
        current_streak = 1
        streak_reset = True
    
    # Update longest streak
    if current_streak > longest_streak:
        longest_streak = current_streak
    
    # Award streak XP bonuses
    if streak_extended:
        xp_bonus = XP_REWARDS["streak_day"] * min(current_streak, 7)  # Cap multiplier at 7
        
        # Milestone bonuses
        if current_streak == 7:
            xp_bonus += XP_REWARDS["streak_week"]
        elif current_streak == 30:
            xp_bonus += XP_REWARDS["streak_month"]
        
        if xp_bonus > 0:
            await add_xp(user_id, "streak_day", xp_bonus / XP_REWARDS["streak_day"])
    
    # Update database
    await user_progress_collection.update_one(
        {"user_id": user_id},
        {
            "$set": {
                "current_streak": current_streak,
                "longest_streak": longest_streak,
                "last_activity_date": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            }
        }
    )
    
    # Check streak achievements
    await check_and_award_achievements(user_id, "streak_days", current_streak)
    
    return {
        "current_streak": current_streak,
        "longest_streak": longest_streak,
        "streak_extended": streak_extended,
        "streak_reset": streak_reset,
        "xp_bonus": xp_bonus
    }

async def increment_stat(user_id: str, stat: str, value: int = 1) -> dict:
    """Increment a user stat and check achievements"""
    await user_progress_collection.update_one(
        {"user_id": user_id},
        {
            "$inc": {stat: value},
            "$set": {"updated_at": datetime.now(timezone.utc)}
        },
        upsert=True
    )
    
    # Get updated value
    progress = await get_user_progress(user_id)
    new_value = progress.get(stat, 0)
    
    # Check related achievements
    achievement_type_map = {
        "games_imported": "games_imported",
        "games_analyzed": "games_analyzed",
        "puzzles_solved": "puzzles_solved",
        "fast_puzzles": "fast_puzzles",
        "no_blunders_games": "no_blunders_game"
    }
    
    if stat in achievement_type_map:
        await check_and_award_achievements(user_id, achievement_type_map[stat], new_value)
    
    return {"stat": stat, "new_value": new_value}

async def update_best_accuracy(user_id: str, accuracy: float) -> dict:
    """Update best accuracy and check achievements"""
    progress = await get_user_progress(user_id)
    current_best = progress.get("best_accuracy", 0)
    
    if accuracy > current_best:
        await user_progress_collection.update_one(
            {"user_id": user_id},
            {"$set": {"best_accuracy": accuracy, "updated_at": datetime.now(timezone.utc)}}
        )
    
    # Check accuracy achievements
    await check_and_award_achievements(user_id, "accuracy_game", accuracy)
    
    return {"best_accuracy": max(accuracy, current_best)}

# =============================================================================
# ACHIEVEMENTS FUNCTIONS
# =============================================================================

async def get_user_achievements(user_id: str) -> dict:
    """Get all achievements with unlock status for user"""
    # Get user's unlocked achievements
    user_achievements = await achievements_collection.find(
        {"user_id": user_id}
    ).to_list(length=100)
    
    unlocked_ids = {a["achievement_id"] for a in user_achievements}
    unlocked_map = {a["achievement_id"]: a for a in user_achievements}
    
    # Build full achievement list
    all_achievements = []
    for achievement in ACHIEVEMENTS:
        ach_data = {
            **achievement,
            "unlocked": achievement["id"] in unlocked_ids,
            "unlocked_at": None
        }
        if achievement["id"] in unlocked_map:
            unlocked_at = unlocked_map[achievement["id"]].get("unlocked_at")
            if unlocked_at:
                ach_data["unlocked_at"] = unlocked_at.isoformat() if isinstance(unlocked_at, datetime) else unlocked_at
        all_achievements.append(ach_data)
    
    # Group by category
    by_category = {}
    for ach in all_achievements:
        cat = ach["category"]
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(ach)
    
    unlocked_count = len(unlocked_ids)
    total_count = len(ACHIEVEMENTS)
    
    return {
        "achievements": all_achievements,
        "by_category": by_category,
        "unlocked_count": unlocked_count,
        "total_count": total_count,
        "completion_percent": round((unlocked_count / total_count) * 100, 1) if total_count > 0 else 0
    }

async def check_and_award_achievements(user_id: str, condition_type: str, value: Any) -> List[dict]:
    """Check and award any achievements that match the condition"""
    newly_unlocked = []
    
    # Get user's current achievements
    user_achievements = await achievements_collection.find(
        {"user_id": user_id}
    ).to_list(length=100)
    unlocked_ids = {a["achievement_id"] for a in user_achievements}
    
    for achievement in ACHIEVEMENTS:
        # Skip if already unlocked
        if achievement["id"] in unlocked_ids:
            continue
        
        condition = achievement.get("condition", {})
        if condition.get("type") != condition_type:
            continue
        
        # Check if condition is met
        should_unlock = False
        
        if condition_type in ["games_imported", "games_analyzed", "puzzles_solved", 
                             "fast_puzzles", "no_blunders_game", "streak_days"]:
            should_unlock = value >= condition.get("count", 0)
        
        elif condition_type in ["accuracy_game", "level_reached"]:
            should_unlock = value >= condition.get("value", 0)
        
        if should_unlock:
            # Award achievement
            await achievements_collection.insert_one({
                "user_id": user_id,
                "achievement_id": achievement["id"],
                "unlocked_at": datetime.now(timezone.utc)
            })
            
            # Award XP
            await add_xp(user_id, "achievement_unlocked", achievement.get("xp_reward", 50) / 50)
            
            newly_unlocked.append(achievement)
    
    return newly_unlocked

async def check_special_achievements(user_id: str) -> List[dict]:
    """Check time-based and special achievements"""
    now = datetime.now(timezone.utc)
    hour = now.hour
    newly_unlocked = []
    
    # Early bird (before 7 AM)
    if hour < 7:
        unlocked = await check_and_award_achievements(user_id, "special", "early_bird")
        newly_unlocked.extend(unlocked)
    
    # Night owl (after 11 PM)
    if hour >= 23:
        unlocked = await check_and_award_achievements(user_id, "special", "night_owl")
        newly_unlocked.extend(unlocked)
    
    return newly_unlocked

# =============================================================================
# LEADERBOARD FUNCTIONS
# =============================================================================

async def get_leaderboard(limit: int = 20) -> List[dict]:
    """Get top users by XP"""
    cursor = user_progress_collection.find(
        {},
        {"_id": 0, "user_id": 1, "xp": 1, "level": 1, "current_streak": 1}
    ).sort("xp", -1).limit(limit)
    
    leaders = await cursor.to_list(length=limit)
    
    # Add rank and level info
    for i, leader in enumerate(leaders):
        leader["rank"] = i + 1
        leader["level_info"] = get_level_for_xp(leader.get("xp", 0))
    
    return leaders

# =============================================================================
# DAILY LOGIN REWARD
# =============================================================================

async def claim_daily_reward(user_id: str) -> dict:
    """Claim daily login reward"""
    progress = await get_user_progress(user_id)
    today = datetime.now(timezone.utc).date()
    last_claim = progress.get("last_daily_claim")
    
    if last_claim:
        if isinstance(last_claim, str):
            last_claim = datetime.fromisoformat(last_claim.replace('Z', '+00:00')).date()
        elif isinstance(last_claim, datetime):
            last_claim = last_claim.date()
        
        if last_claim == today:
            return {"claimed": False, "reason": "Already claimed today", "xp_earned": 0}
    
    # Award daily XP
    xp_result = await add_xp(user_id, "daily_login")
    
    # Update streak
    streak_result = await update_streak(user_id)
    
    # Mark as claimed
    await user_progress_collection.update_one(
        {"user_id": user_id},
        {"$set": {"last_daily_claim": datetime.now(timezone.utc)}}
    )
    
    # Check special achievements
    special = await check_special_achievements(user_id)
    
    return {
        "claimed": True,
        "xp_earned": xp_result["xp_earned"],
        "streak": streak_result,
        "special_achievements": special
    }
