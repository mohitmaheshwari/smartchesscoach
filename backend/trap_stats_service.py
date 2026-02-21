"""
Trap Statistics Service

Tracks user attempts on traps and provides statistics/recommendations.
"""

from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any
from motor.motor_asyncio import AsyncIOMotorDatabase
import logging

logger = logging.getLogger(__name__)


async def record_trap_attempt(
    db: AsyncIOMotorDatabase,
    user_id: str,
    trap_key: str,
    mode: str,  # execution | avoidance | recognition
    success: bool,
    details: Optional[Dict] = None
) -> Dict:
    """
    Record a user's attempt on a trap practice mode.
    """
    attempt = {
        "user_id": user_id,
        "trap_key": trap_key,
        "mode": mode,
        "success": success,
        "details": details or {},
        "timestamp": datetime.now(timezone.utc)
    }
    
    result = await db.trap_attempts.insert_one(attempt)
    
    # Update user's trap stats cache
    await update_user_trap_stats(db, user_id, trap_key, mode, success)
    
    return {"recorded": True, "attempt_id": str(result.inserted_id)}


async def update_user_trap_stats(
    db: AsyncIOMotorDatabase,
    user_id: str,
    trap_key: str,
    mode: str,
    success: bool
):
    """
    Update the aggregated stats for a user's trap performance.
    Uses upsert to create or update the stats document.
    """
    stat_key = f"{trap_key}_{mode}"
    
    update_ops = {
        "$inc": {
            f"traps.{stat_key}.attempts": 1,
            f"traps.{stat_key}.successes": 1 if success else 0,
            f"total_attempts": 1,
            f"total_successes": 1 if success else 0
        },
        "$set": {
            f"traps.{stat_key}.last_attempt": datetime.now(timezone.utc),
            f"traps.{stat_key}.trap_key": trap_key,
            f"traps.{stat_key}.mode": mode,
            "user_id": user_id,
            "updated_at": datetime.now(timezone.utc)
        },
        "$setOnInsert": {
            "created_at": datetime.now(timezone.utc)
        }
    }
    
    await db.user_trap_stats.update_one(
        {"user_id": user_id},
        update_ops,
        upsert=True
    )


async def get_user_trap_stats(
    db: AsyncIOMotorDatabase,
    user_id: str
) -> Dict:
    """
    Get comprehensive trap statistics for a user.
    """
    # Get aggregated stats
    stats_doc = await db.user_trap_stats.find_one({"user_id": user_id})
    
    if not stats_doc:
        return {
            "total_attempts": 0,
            "total_successes": 0,
            "success_rate": 0,
            "traps": {},
            "weakest_traps": [],
            "strongest_traps": [],
            "recent_activity": []
        }
    
    # Calculate per-trap success rates
    traps_with_rates = []
    for stat_key, trap_stats in stats_doc.get("traps", {}).items():
        attempts = trap_stats.get("attempts", 0)
        successes = trap_stats.get("successes", 0)
        rate = (successes / attempts * 100) if attempts > 0 else 0
        
        traps_with_rates.append({
            "trap_key": trap_stats.get("trap_key"),
            "mode": trap_stats.get("mode"),
            "attempts": attempts,
            "successes": successes,
            "success_rate": round(rate, 1),
            "last_attempt": trap_stats.get("last_attempt")
        })
    
    # Sort to find weakest and strongest
    sorted_by_rate = sorted(traps_with_rates, key=lambda x: x["success_rate"])
    
    # Filter for traps with at least 2 attempts for meaningful stats
    meaningful_stats = [t for t in sorted_by_rate if t["attempts"] >= 2]
    
    # Get recent activity
    recent = await db.trap_attempts.find(
        {"user_id": user_id}
    ).sort("timestamp", -1).limit(10).to_list(10)
    
    recent_activity = [
        {
            "trap_key": r["trap_key"],
            "mode": r["mode"],
            "success": r["success"],
            "timestamp": r["timestamp"].isoformat() if r.get("timestamp") else None
        }
        for r in recent
    ]
    
    total_attempts = stats_doc.get("total_attempts", 0)
    total_successes = stats_doc.get("total_successes", 0)
    
    return {
        "total_attempts": total_attempts,
        "total_successes": total_successes,
        "success_rate": round((total_successes / total_attempts * 100) if total_attempts > 0 else 0, 1),
        "traps": {t["trap_key"]: t for t in traps_with_rates},
        "weakest_traps": meaningful_stats[:5],  # Bottom 5
        "strongest_traps": list(reversed(meaningful_stats[-5:])),  # Top 5
        "recent_activity": recent_activity
    }


async def get_recommended_traps(
    db: AsyncIOMotorDatabase,
    user_id: str,
    limit: int = 5
) -> List[Dict]:
    """
    Get recommended traps for a user based on their weaknesses.
    
    Prioritizes:
    1. Traps user has failed most often
    2. Traps user hasn't tried yet
    3. Traps related to user's most-played openings
    """
    from trick_library_service import get_all_traps, get_trap_by_key
    
    all_traps = get_all_traps()
    all_trap_keys = {t["key"] for t in all_traps}
    
    # Get user's stats
    stats = await get_user_trap_stats(db, user_id)
    attempted_traps = set(stats.get("traps", {}).keys())
    
    recommendations = []
    
    # 1. Add weakest traps (user struggles with these)
    for weak in stats.get("weakest_traps", [])[:3]:
        trap_data = get_trap_by_key(weak["trap_key"])
        if trap_data:
            recommendations.append({
                "trap_key": weak["trap_key"],
                "name": trap_data.get("name"),
                "reason": f"You're struggling with this trap ({weak['success_rate']}% success rate)",
                "priority": "high",
                "stats": weak
            })
    
    # 2. Add untried traps
    untried = all_trap_keys - {k.split("_")[0] for k in attempted_traps}  # Extract trap_key from stat_key
    for trap_key in list(untried)[:3]:
        trap_data = get_trap_by_key(trap_key)
        if trap_data:
            recommendations.append({
                "trap_key": trap_key,
                "name": trap_data.get("name"),
                "reason": "You haven't practiced this trap yet",
                "priority": "medium",
                "stats": None
            })
    
    # 3. Get user's most-played openings and recommend related traps
    user_openings = await get_user_top_openings(db, user_id)
    if user_openings:
        from trick_library_service import get_traps_by_opening
        for opening in user_openings[:2]:
            related_traps = get_traps_by_opening(opening["opening_name"])
            for trap in related_traps[:2]:
                if trap["key"] not in [r["trap_key"] for r in recommendations]:
                    recommendations.append({
                        "trap_key": trap["key"],
                        "name": trap["name"],
                        "reason": f"Related to {opening['opening_name']} which you play often",
                        "priority": "medium",
                        "stats": stats.get("traps", {}).get(trap["key"])
                    })
    
    return recommendations[:limit]


async def get_user_top_openings(
    db: AsyncIOMotorDatabase,
    user_id: str,
    limit: int = 5
) -> List[Dict]:
    """
    Get user's most-played openings from their game history.
    """
    pipeline = [
        {"$match": {"user_id": user_id, "opening_name": {"$ne": None, "$ne": "Unknown"}}},
        {"$group": {
            "_id": "$opening_name",
            "count": {"$sum": 1}
        }},
        {"$sort": {"count": -1}},
        {"$limit": limit},
        {"$project": {
            "_id": 0,
            "opening_name": "$_id",
            "games_played": "$count"
        }}
    ]
    
    result = await db.games.aggregate(pipeline).to_list(limit)
    return result


async def get_trap_leaderboard(
    db: AsyncIOMotorDatabase,
    trap_key: str,
    mode: str = "execution",
    limit: int = 10
) -> List[Dict]:
    """
    Get leaderboard for a specific trap showing top performers.
    """
    stat_key = f"{trap_key}_{mode}"
    
    pipeline = [
        {"$match": {f"traps.{stat_key}": {"$exists": True}}},
        {"$project": {
            "user_id": 1,
            "attempts": f"$traps.{stat_key}.attempts",
            "successes": f"$traps.{stat_key}.successes",
            "success_rate": {
                "$cond": {
                    "if": {"$gt": [f"$traps.{stat_key}.attempts", 0]},
                    "then": {
                        "$multiply": [
                            {"$divide": [f"$traps.{stat_key}.successes", f"$traps.{stat_key}.attempts"]},
                            100
                        ]
                    },
                    "else": 0
                }
            }
        }},
        {"$match": {"attempts": {"$gte": 3}}},  # Minimum 3 attempts for leaderboard
        {"$sort": {"success_rate": -1, "attempts": -1}},
        {"$limit": limit}
    ]
    
    result = await db.user_trap_stats.aggregate(pipeline).to_list(limit)
    
    # Get usernames
    for entry in result:
        user = await db.users.find_one({"_id": entry["user_id"]}, {"username": 1, "display_name": 1})
        if user:
            entry["username"] = user.get("display_name") or user.get("username") or "Anonymous"
        else:
            entry["username"] = "Anonymous"
        entry["success_rate"] = round(entry.get("success_rate", 0), 1)
        del entry["_id"]
    
    return result


async def get_global_trap_stats(
    db: AsyncIOMotorDatabase
) -> Dict:
    """
    Get global statistics across all users for all traps.
    """
    pipeline = [
        {"$group": {
            "_id": {"trap_key": "$trap_key", "mode": "$mode"},
            "total_attempts": {"$sum": 1},
            "total_successes": {"$sum": {"$cond": ["$success", 1, 0]}},
            "unique_users": {"$addToSet": "$user_id"}
        }},
        {"$project": {
            "_id": 0,
            "trap_key": "$_id.trap_key",
            "mode": "$_id.mode",
            "total_attempts": 1,
            "total_successes": 1,
            "success_rate": {
                "$cond": {
                    "if": {"$gt": ["$total_attempts", 0]},
                    "then": {"$multiply": [{"$divide": ["$total_successes", "$total_attempts"]}, 100]},
                    "else": 0
                }
            },
            "unique_users": {"$size": "$unique_users"}
        }},
        {"$sort": {"total_attempts": -1}}
    ]
    
    result = await db.trap_attempts.aggregate(pipeline).to_list(100)
    
    # Round success rates
    for entry in result:
        entry["success_rate"] = round(entry.get("success_rate", 0), 1)
    
    # Calculate overall stats
    total_attempts = sum(r["total_attempts"] for r in result)
    total_successes = sum(r["total_successes"] for r in result)
    
    return {
        "overall": {
            "total_attempts": total_attempts,
            "total_successes": total_successes,
            "success_rate": round((total_successes / total_attempts * 100) if total_attempts > 0 else 0, 1)
        },
        "by_trap": result,
        "most_attempted": result[:5] if result else [],
        "hardest_traps": sorted(result, key=lambda x: x["success_rate"])[:5] if result else [],
        "easiest_traps": sorted(result, key=lambda x: -x["success_rate"])[:5] if result else []
    }
