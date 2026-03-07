"""
Identity Formation Layer
========================

Tracks the evolution of a player's chess identity over time.

Key Features:
1. Periodic identity snapshots (stored in DB)
2. Change detection (style shifts, improvement, regression)
3. Long-term growth trajectory
4. Milestone tracking (first 100 games, rating milestones, etc.)

This builds on top of player_identity_engine.py to add temporal tracking.
"""

import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
from collections import defaultdict
import logging
import uuid

logger = logging.getLogger(__name__)


# ============================================
# IDENTITY EVOLUTION CONSTANTS
# ============================================

# Snapshot frequency - create snapshot if more than this many days since last
SNAPSHOT_INTERVAL_DAYS = 7

# Minimum games between snapshots
MIN_GAMES_BETWEEN_SNAPSHOTS = 5

# Change detection thresholds
SIGNIFICANT_STABILITY_CHANGE = 0.15  # 15% change in stability score
SIGNIFICANT_ACCURACY_CHANGE = 5.0    # 5% accuracy change
STYLE_SHIFT_THRESHOLD = 0.2          # 20% change in risk style

# Milestones
GAME_MILESTONES = [10, 25, 50, 100, 250, 500, 1000]
RATING_MILESTONES = [800, 1000, 1200, 1400, 1600, 1800, 2000, 2200]


# ============================================
# IDENTITY SNAPSHOT FUNCTIONS
# ============================================

async def create_identity_snapshot(db, user_id: str, identity: Dict) -> Dict:
    """
    Create and store an identity snapshot.
    
    Args:
        db: Database connection
        user_id: User ID
        identity: Current identity from player_identity_engine
    
    Returns:
        The stored snapshot document
    """
    now = datetime.now(timezone.utc)
    
    snapshot = {
        "snapshot_id": f"ids_{uuid.uuid4().hex[:12]}",
        "user_id": user_id,
        "created_at": now.isoformat(),
        
        # Core identity data
        "games_analyzed": identity.get("games_analyzed", 0),
        "confidence": identity.get("confidence", {}),
        "collapsed_summary": identity.get("collapsed_summary", ""),
        
        # Key metrics for comparison
        "stability_score": identity.get("stability", {}).get("score", 0),
        "stability_label": identity.get("stability", {}).get("label", "unknown"),
        "primary_leak": identity.get("primary_leak", {}).get("pattern", "unknown"),
        "primary_leak_score": identity.get("primary_leak", {}).get("score", 0),
        "phase_vulnerability": identity.get("phase_vulnerability", {}).get("weakest_phase", "unknown"),
        "risk_style": identity.get("risk_style", {}).get("style", "unknown"),
        "risk_score": identity.get("risk_style", {}).get("score", 0),
        
        # Full identity for detailed comparison
        "full_identity": identity,
    }
    
    await db.identity_snapshots.insert_one(snapshot)
    logger.info(f"Created identity snapshot {snapshot['snapshot_id']} for user {user_id}")
    
    return snapshot


async def get_latest_snapshot(db, user_id: str) -> Optional[Dict]:
    """Get the most recent identity snapshot for a user."""
    snapshot = await db.identity_snapshots.find_one(
        {"user_id": user_id},
        {"_id": 0},
        sort=[("created_at", -1)]
    )
    return snapshot


async def get_snapshot_history(db, user_id: str, limit: int = 12) -> List[Dict]:
    """Get historical identity snapshots for a user."""
    cursor = db.identity_snapshots.find(
        {"user_id": user_id},
        {"_id": 0}
    ).sort("created_at", -1).limit(limit)
    
    return await cursor.to_list(length=limit)


async def should_create_snapshot(db, user_id: str, current_games: int) -> bool:
    """
    Determine if a new snapshot should be created.
    
    Creates snapshot if:
    1. No previous snapshot exists
    2. More than SNAPSHOT_INTERVAL_DAYS since last snapshot
    3. At least MIN_GAMES_BETWEEN_SNAPSHOTS new games analyzed
    """
    latest = await get_latest_snapshot(db, user_id)
    
    if not latest:
        return True
    
    # Check time since last snapshot
    last_time = datetime.fromisoformat(latest["created_at"].replace('Z', '+00:00'))
    days_since = (datetime.now(timezone.utc) - last_time).days
    
    if days_since >= SNAPSHOT_INTERVAL_DAYS:
        # Check if enough new games
        last_games = latest.get("games_analyzed", 0)
        if current_games - last_games >= MIN_GAMES_BETWEEN_SNAPSHOTS:
            return True
    
    return False


# ============================================
# IDENTITY EVOLUTION ANALYSIS
# ============================================

def compare_identities(old_identity: Dict, new_identity: Dict) -> Dict:
    """
    Compare two identity snapshots and detect changes.
    
    Returns:
        Dict with changes, improvements, regressions, and style shifts
    """
    changes = {
        "has_changes": False,
        "improvements": [],
        "regressions": [],
        "style_shifts": [],
        "notable_changes": [],
        "summary": "",
    }
    
    # Compare stability
    old_stability = old_identity.get("stability_score", 0)
    new_stability = new_identity.get("stability_score", 0)
    stability_change = new_stability - old_stability
    
    if abs(stability_change) >= SIGNIFICANT_STABILITY_CHANGE:
        changes["has_changes"] = True
        if stability_change > 0:
            changes["improvements"].append({
                "area": "stability",
                "label": "Decision Stability",
                "change": stability_change,
                "message": f"Your decision-making is {abs(stability_change)*100:.0f}% more consistent"
            })
        else:
            changes["regressions"].append({
                "area": "stability",
                "label": "Decision Stability", 
                "change": stability_change,
                "message": f"Your decisions have become {abs(stability_change)*100:.0f}% less consistent"
            })
    
    # Compare risk style
    old_risk = old_identity.get("risk_score", 0.5)
    new_risk = new_identity.get("risk_score", 0.5)
    risk_change = new_risk - old_risk
    
    if abs(risk_change) >= STYLE_SHIFT_THRESHOLD:
        changes["has_changes"] = True
        old_style = old_identity.get("risk_style", "balanced")
        new_style = new_identity.get("risk_style", "balanced")
        
        changes["style_shifts"].append({
            "area": "risk_style",
            "from_style": old_style,
            "to_style": new_style,
            "message": f"Your playing style shifted from {old_style} to {new_style}"
        })
    
    # Compare primary leak
    old_leak = old_identity.get("primary_leak", "unknown")
    new_leak = new_identity.get("primary_leak", "unknown")
    
    if old_leak != new_leak and old_leak != "unknown" and new_leak != "unknown":
        changes["has_changes"] = True
        changes["notable_changes"].append({
            "area": "primary_weakness",
            "from": old_leak,
            "to": new_leak,
            "message": f"Your main weakness shifted from {old_leak.replace('_', ' ')} to {new_leak.replace('_', ' ')}"
        })
    
    # Compare phase vulnerability
    old_phase = old_identity.get("phase_vulnerability", "unknown")
    new_phase = new_identity.get("phase_vulnerability", "unknown")
    
    if old_phase != new_phase and old_phase != "unknown" and new_phase != "unknown":
        changes["has_changes"] = True
        changes["notable_changes"].append({
            "area": "weak_phase",
            "from": old_phase,
            "to": new_phase,
            "message": f"Your weakest phase changed from {old_phase} to {new_phase}"
        })
    
    # Generate summary
    if changes["has_changes"]:
        parts = []
        if changes["improvements"]:
            parts.append(f"{len(changes['improvements'])} area(s) improved")
        if changes["regressions"]:
            parts.append(f"{len(changes['regressions'])} area(s) regressed")
        if changes["style_shifts"]:
            parts.append("playing style shifted")
        changes["summary"] = "Your identity has evolved: " + ", ".join(parts)
    else:
        changes["summary"] = "Your playing identity has remained stable"
    
    return changes


async def compute_identity_evolution(db, user_id: str) -> Dict:
    """
    Compute the full identity evolution for a user.
    
    Returns:
        - Current identity
        - Change from last snapshot
        - Long-term trajectory
        - Milestones achieved
    """
    from player_identity_engine import compute_player_identity
    
    # Get current identity
    current_identity = await compute_player_identity(db, user_id)
    
    if not current_identity.get("has_identity"):
        return {
            "has_evolution": False,
            "current_identity": current_identity,
            "reason": "Not enough games for identity tracking"
        }
    
    # Get snapshot history
    snapshots = await get_snapshot_history(db, user_id, limit=12)
    
    # Check if we should create a new snapshot
    should_snapshot = await should_create_snapshot(
        db, user_id, 
        current_identity.get("games_analyzed", 0)
    )
    
    if should_snapshot:
        await create_identity_snapshot(db, user_id, current_identity)
        # Refresh snapshots
        snapshots = await get_snapshot_history(db, user_id, limit=12)
    
    # Compute changes from last snapshot
    recent_changes = None
    if len(snapshots) >= 2:
        recent_changes = compare_identities(snapshots[1], {
            "stability_score": current_identity.get("stability", {}).get("score", 0),
            "primary_leak": current_identity.get("primary_leak", {}).get("pattern", "unknown"),
            "phase_vulnerability": current_identity.get("phase_vulnerability", {}).get("weakest_phase", "unknown"),
            "risk_style": current_identity.get("risk_style", {}).get("style", "unknown"),
            "risk_score": current_identity.get("risk_style", {}).get("score", 0.5),
        })
    
    # Compute long-term trajectory
    trajectory = compute_trajectory(snapshots) if len(snapshots) >= 3 else None
    
    # Check milestones
    milestones = await check_milestones(db, user_id, current_identity.get("games_analyzed", 0))
    
    return {
        "has_evolution": True,
        "current_identity": current_identity,
        "recent_changes": recent_changes,
        "trajectory": trajectory,
        "milestones": milestones,
        "snapshot_count": len(snapshots),
        "first_snapshot": snapshots[-1].get("created_at") if snapshots else None,
        "latest_snapshot": snapshots[0].get("created_at") if snapshots else None,
    }


def compute_trajectory(snapshots: List[Dict]) -> Dict:
    """
    Compute long-term trajectory from snapshot history.
    
    Returns:
        Overall direction of identity evolution
    """
    if len(snapshots) < 3:
        return None
    
    # Get stability scores over time
    stability_scores = [s.get("stability_score", 0) for s in reversed(snapshots)]
    
    # Simple linear regression for trend
    n = len(stability_scores)
    x_mean = (n - 1) / 2
    y_mean = sum(stability_scores) / n
    
    numerator = sum((i - x_mean) * (y - y_mean) for i, y in enumerate(stability_scores))
    denominator = sum((i - x_mean) ** 2 for i in range(n))
    
    slope = numerator / denominator if denominator != 0 else 0
    
    # Determine trajectory
    if slope > 0.02:
        direction = "improving"
        message = "Your overall stability is trending upward"
    elif slope < -0.02:
        direction = "declining"
        message = "Your stability has been declining - focus on consistency"
    else:
        direction = "stable"
        message = "Your identity has been relatively stable"
    
    # Get style changes
    style_changes = []
    for i in range(len(snapshots) - 1):
        old_style = snapshots[i + 1].get("risk_style", "balanced")
        new_style = snapshots[i].get("risk_style", "balanced")
        if old_style != new_style:
            style_changes.append({
                "from": old_style,
                "to": new_style,
                "when": snapshots[i].get("created_at")
            })
    
    return {
        "direction": direction,
        "stability_trend": slope,
        "message": message,
        "snapshots_analyzed": len(snapshots),
        "style_changes": style_changes[:3],  # Last 3 style changes
    }


async def check_milestones(db, user_id: str, current_games: int) -> Dict:
    """
    Check for newly achieved milestones.
    """
    # Get user's milestone record
    user = await db.users.find_one({"user_id": user_id}, {"_id": 0, "achieved_milestones": 1})
    achieved = set(user.get("achieved_milestones", []) if user else [])
    
    new_milestones = []
    
    # Check game milestones
    for milestone in GAME_MILESTONES:
        key = f"games_{milestone}"
        if current_games >= milestone and key not in achieved:
            new_milestones.append({
                "type": "games",
                "value": milestone,
                "key": key,
                "message": f"You've analyzed {milestone} games!"
            })
    
    # Store new milestones
    if new_milestones:
        new_keys = [m["key"] for m in new_milestones]
        await db.users.update_one(
            {"user_id": user_id},
            {"$addToSet": {"achieved_milestones": {"$each": new_keys}}}
        )
    
    return {
        "new_milestones": new_milestones,
        "total_achieved": len(achieved) + len(new_milestones),
        "next_game_milestone": next((m for m in GAME_MILESTONES if m > current_games), None)
    }


# ============================================
# IDENTITY INSIGHT GENERATOR
# ============================================

def generate_evolution_insight(evolution: Dict) -> str:
    """
    Generate a human-readable insight about identity evolution.
    """
    if not evolution.get("has_evolution"):
        return "Keep playing to build your chess identity."
    
    parts = []
    
    # Recent changes insight
    changes = evolution.get("recent_changes")
    if changes and changes.get("has_changes"):
        if changes.get("improvements"):
            imp = changes["improvements"][0]
            parts.append(f"Good progress: {imp['message'].lower()}.")
        if changes.get("style_shifts"):
            shift = changes["style_shifts"][0]
            parts.append(f"Your style is evolving: {shift['message'].lower()}.")
    
    # Trajectory insight
    trajectory = evolution.get("trajectory")
    if trajectory:
        parts.append(trajectory["message"] + ".")
    
    # Milestone insight
    milestones = evolution.get("milestones", {})
    if milestones.get("new_milestones"):
        m = milestones["new_milestones"][0]
        parts.append(f"Milestone: {m['message']}")
    
    if not parts:
        parts.append("Your chess identity continues to develop with each game.")
    
    return " ".join(parts)
