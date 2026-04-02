"""
Identity Formation Layer
========================

Tracks the evolution of a player's chess identity over time.

Key Features:
1. Periodic identity snapshots (stored in DB)
2. Change detection (style shifts, improvement, regression)
3. Long-term growth trajectory
4. Milestone tracking (first 100 games, rating milestones, etc.)
5. "Coaching moments" - auto-detect significant identity shifts
6. Comparative insights ("You used to be X, now you're Y")

This builds on top of player_identity_engine.py to add temporal tracking.
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional
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

# Coaching moment triggers
COACHING_MOMENT_TRIGGERS = {
    "breakthrough": "Your stability score jumped significantly - you're playing more consistently!",
    "style_shift": "Your playing style has evolved - embrace this change.",
    "leak_change": "Your main weakness has shifted - time to update your training focus.",
    "phase_mastery": "You've improved in your previously weakest phase!",
    "regression": "Your consistency dropped - let's figure out why.",
}


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
    
    # Extract raw values from identity - handle nested structure
    raw = identity.get("raw", {})
    expanded = identity.get("expanded", {})
    
    # Get stability info
    stability_raw = raw.get("stability", "mixed")
    stability_section = expanded.get("stability", {})
    
    # Get leak info
    leak_raw = raw.get("leak", "unknown")
    leak_section = expanded.get("leak", {})
    
    # Get phase info
    phase_raw = raw.get("phase", "unknown")
    phase_section = expanded.get("phase", {})
    
    # Get style info  
    style_raw = raw.get("style", "balanced")
    style_section = expanded.get("style", {})
    
    snapshot = {
        "snapshot_id": f"ids_{uuid.uuid4().hex[:12]}",
        "user_id": user_id,
        "created_at": now,
        
        # Core identity data
        "identity": {
            "primary_archetype": _derive_archetype(stability_raw, leak_raw, style_raw),
            "traits": _extract_traits(identity),
            "summary": identity.get("collapsed_summary", ""),
        },
        
        # Key metrics for comparison
        "metrics": {
            "stability_label": stability_raw,
            "stability_description": stability_section.get("title", ""),
            "primary_leak": leak_raw,
            "leak_description": leak_section.get("title", ""),
            "weak_phase": phase_raw,
            "phase_description": phase_section.get("title", ""),
            "risk_style": style_raw,
            "style_description": style_section.get("title", ""),
        },
        
        # Stats snapshot for tracking over time
        "stats_snapshot": {
            "total_games": identity.get("games_analyzed", 0),
            "confidence": identity.get("confidence", {}).get("score", 0),
            "confidence_label": identity.get("confidence", {}).get("label", "unknown"),
        },
        
        # Full identity for detailed comparison
        "full_identity": identity,
    }
    
    await db.identity_snapshots.insert_one(snapshot)
    logger.info(f"Created identity snapshot {snapshot['snapshot_id']} for user {user_id}")
    
    return snapshot


def _derive_archetype(stability: str, leak: str, style: str) -> str:
    """Derive a player archetype from identity components."""
    # Map style raw values to human-readable
    style_map = {"low": "solid", "medium": "balanced", "high": "aggressive"}
    mapped_style = style_map.get(style, style)
    
    archetypes = {
        ("stable", "tactical_oversight", "aggressive"): "The Calculating Attacker",
        ("stable", "tactical_oversight", "solid"): "The Methodical Defender",
        ("stable", "threat_blindness", "aggressive"): "The Bold Calculator",
        ("stable", "threat_blindness", "solid"): "The Careful Strategist",
        ("volatile", "calculation_depth", "aggressive"): "The Impulsive Tactician",
        ("volatile", "calculation_depth", "solid"): "The Cautious Thinker",
        ("volatile", "time_pressure", "aggressive"): "The Time Scrambler",
        ("volatile", "positional_misread", "solid"): "The Positional Learner",
        ("volatile", "positional_misread", "aggressive"): "The Experimental Player",
        ("mixed", "advantage_collapse", "aggressive"): "The Opportunist",
        ("mixed", "advantage_collapse", "solid"): "The Position Builder",
        ("mixed", "threat_blindness", "balanced"): "The Developing Tactician",
    }
    
    key = (stability, leak, mapped_style)
    if key in archetypes:
        return archetypes[key]
    
    # Default archetypes based on style
    if mapped_style == "aggressive":
        return "The Attacker"
    elif mapped_style == "solid":
        return "The Defender"
    else:
        return "The Balanced Player"


def _extract_traits(identity: Dict) -> List[str]:
    """Extract key traits from identity for snapshot."""
    traits = []
    raw = identity.get("raw", {})
    
    if raw.get("stability") == "stable":
        traits.append("Consistent decision-maker")
    elif raw.get("stability") == "volatile":
        traits.append("Variable performance")
    
    if raw.get("style") == "aggressive":
        traits.append("Aggressive playstyle")
    elif raw.get("style") == "solid":
        traits.append("Solid positional approach")
    
    leak = raw.get("leak", "")
    if leak == "time_pressure":
        traits.append("Struggles under time pressure")
    elif leak == "tactical_oversight":
        traits.append("Tactical blind spots")
    elif leak == "threat_blindness":
        traits.append("Misses opponent threats")
    
    return traits[:4]  # Max 4 traits


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
    
    # Check time since last snapshot - handle both datetime and string formats
    created_at = latest.get("created_at")
    if isinstance(created_at, str):
        last_time = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
    elif isinstance(created_at, datetime):
        last_time = created_at if created_at.tzinfo else created_at.replace(tzinfo=timezone.utc)
    else:
        # Can't parse, assume we should create a new one
        return True
    
    days_since = (datetime.now(timezone.utc) - last_time).days
    
    if days_since >= SNAPSHOT_INTERVAL_DAYS:
        # Check if enough new games - check multiple locations for game count
        last_games = latest.get("stats_snapshot", {}).get("total_games", 0)
        if last_games == 0:
            last_games = latest.get("games_analyzed", 0)
        if current_games - last_games >= MIN_GAMES_BETWEEN_SNAPSHOTS:
            return True
    
    return False


# ============================================
# IDENTITY EVOLUTION ANALYSIS
# ============================================

def _map_style_label(style: str) -> str:
    """Map raw style value to human-readable label."""
    style_map = {"low": "solid", "medium": "balanced", "high": "aggressive"}
    return style_map.get(style, style)


def compare_identities(old_snapshot: Dict, new_snapshot: Dict) -> Dict:
    """
    Compare two identity snapshots and detect changes.
    
    Returns:
        Dict with changes, improvements, regressions, style shifts, and coaching moments
    """
    changes = {
        "has_changes": False,
        "improvements": [],
        "regressions": [],
        "style_shifts": [],
        "notable_changes": [],
        "coaching_moments": [],  # NEW: Significant moments that warrant coaching intervention
        "comparative_insight": "",  # NEW: "You used to be X, now you're Y"
        "summary": "",
    }
    
    old_metrics = old_snapshot.get("metrics", {})
    new_metrics = new_snapshot.get("metrics", {})
    
    old_identity = old_snapshot.get("identity", {})
    new_identity = new_snapshot.get("identity", {})
    
    # Compare stability
    old_stability = old_metrics.get("stability_label", "mixed")
    new_stability = new_metrics.get("stability_label", "mixed")
    
    stability_order = {"volatile": 0, "mixed": 1, "stable": 2}
    old_score = stability_order.get(old_stability, 1)
    new_score = stability_order.get(new_stability, 1)
    
    if new_score > old_score:
        changes["has_changes"] = True
        changes["improvements"].append({
            "area": "stability",
            "label": "Decision Consistency",
            "from": old_stability,
            "to": new_stability,
            "message": f"Your decision-making improved from {old_stability} to {new_stability}"
        })
        changes["coaching_moments"].append({
            "type": "breakthrough",
            "message": COACHING_MOMENT_TRIGGERS["breakthrough"]
        })
    elif new_score < old_score:
        changes["has_changes"] = True
        changes["regressions"].append({
            "area": "stability",
            "label": "Decision Consistency",
            "from": old_stability,
            "to": new_stability,
            "message": f"Your consistency dropped from {old_stability} to {new_stability}"
        })
        changes["coaching_moments"].append({
            "type": "regression",
            "message": COACHING_MOMENT_TRIGGERS["regression"]
        })
    
    # Compare risk style (map to human-readable)
    old_style_raw = old_metrics.get("risk_style", "medium")
    new_style_raw = new_metrics.get("risk_style", "medium")
    old_style = _map_style_label(old_style_raw)
    new_style = _map_style_label(new_style_raw)
    
    if old_style != new_style:
        changes["has_changes"] = True
        changes["style_shifts"].append({
            "area": "risk_style",
            "from_style": old_style,
            "to_style": new_style,
            "message": f"Your playing style shifted from {old_style} to {new_style}"
        })
        changes["coaching_moments"].append({
            "type": "style_shift",
            "message": COACHING_MOMENT_TRIGGERS["style_shift"]
        })
    
    # Compare primary leak
    old_leak = old_metrics.get("primary_leak", "unknown")
    new_leak = new_metrics.get("primary_leak", "unknown")
    
    if old_leak != new_leak and old_leak != "unknown" and new_leak != "unknown":
        changes["has_changes"] = True
        changes["notable_changes"].append({
            "area": "primary_weakness",
            "from": old_leak,
            "to": new_leak,
            "message": f"Main weakness shifted from {old_leak.replace('_', ' ')} to {new_leak.replace('_', ' ')}"
        })
        changes["coaching_moments"].append({
            "type": "leak_change",
            "message": COACHING_MOMENT_TRIGGERS["leak_change"]
        })
    
    # Compare phase vulnerability
    old_phase = old_metrics.get("weak_phase", "unknown")
    new_phase = new_metrics.get("weak_phase", "unknown")
    
    if old_phase != new_phase and old_phase != "unknown" and new_phase != "unknown":
        changes["has_changes"] = True
        changes["notable_changes"].append({
            "area": "weak_phase",
            "from": old_phase,
            "to": new_phase,
            "message": f"Weakest phase changed from {old_phase} to {new_phase}"
        })
    
    # Generate comparative insight (the "You used to be X, now you're Y" feature)
    old_archetype = old_identity.get("primary_archetype", "")
    new_archetype = new_identity.get("primary_archetype", "")
    
    if old_archetype and new_archetype and old_archetype != new_archetype:
        changes["comparative_insight"] = f"You've evolved from '{old_archetype}' to '{new_archetype}'. Your chess identity is developing."
    elif changes["has_changes"]:
        if changes["improvements"]:
            changes["comparative_insight"] = f"You're becoming more consistent. {changes['improvements'][0]['message']}."
        elif changes["style_shifts"]:
            shift = changes["style_shifts"][0]
            changes["comparative_insight"] = f"Your style has evolved. You used to play {shift['from_style']}, now you're more {shift['to_style']}."
    
    # Generate summary
    if changes["has_changes"]:
        parts = []
        if changes["improvements"]:
            parts.append(f"{len(changes['improvements'])} area(s) improved")
        if changes["regressions"]:
            parts.append(f"{len(changes['regressions'])} area(s) need attention")
        if changes["style_shifts"]:
            parts.append("playing style evolved")
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
        - Coaching moments (significant changes that warrant attention)
        - Comparative insights
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
    
    # Build current snapshot dict for comparison
    raw = current_identity.get("raw", {})
    current_snapshot = {
        "metrics": {
            "stability_label": raw.get("stability", "mixed"),
            "primary_leak": raw.get("leak", "unknown"),
            "weak_phase": raw.get("phase", "unknown"),
            "risk_style": raw.get("style", "balanced"),
        },
        "identity": {
            "primary_archetype": _derive_archetype(
                raw.get("stability", "mixed"),
                raw.get("leak", "unknown"),
                raw.get("style", "balanced")
            ),
        }
    }
    
    # Compute changes from last snapshot
    recent_changes = None
    if len(snapshots) >= 1:
        recent_changes = compare_identities(snapshots[0], current_snapshot)
    
    # Compute long-term trajectory
    trajectory = compute_trajectory(snapshots) if len(snapshots) >= 3 else None
    
    # Check milestones
    milestones = await check_milestones(db, user_id, current_identity.get("games_analyzed", 0))
    
    # Extract coaching moments
    coaching_moments = []
    if recent_changes and recent_changes.get("coaching_moments"):
        coaching_moments = recent_changes["coaching_moments"]
    
    # Generate comparative insight
    comparative_insight = ""
    if recent_changes:
        comparative_insight = recent_changes.get("comparative_insight", "")
    
    return {
        "has_evolution": True,
        "current_identity": current_identity,
        "current_archetype": current_snapshot["identity"]["primary_archetype"],
        "recent_changes": recent_changes,
        "trajectory": trajectory,
        "milestones": milestones,
        "coaching_moments": coaching_moments,
        "comparative_insight": comparative_insight,
        "snapshot_count": len(snapshots),
        "first_snapshot": snapshots[-1].get("created_at") if snapshots else None,
        "latest_snapshot": snapshots[0].get("created_at") if snapshots else None,
    }


def compute_trajectory(snapshots: List[Dict]) -> Dict:
    """
    Compute long-term trajectory from snapshot history.
    
    Returns:
        Overall direction of identity evolution with rich insights
    """
    if len(snapshots) < 3:
        return None
    
    # Track stability progression
    stability_order = {"volatile": 0, "mixed": 1, "stable": 2}
    stability_scores = []
    
    for s in reversed(snapshots):
        metrics = s.get("metrics", {})
        label = metrics.get("stability_label", "mixed")
        stability_scores.append(stability_order.get(label, 1))
    
    # Simple trend analysis
    n = len(stability_scores)
    first_half = stability_scores[:n//2]
    second_half = stability_scores[n//2:]
    
    first_avg = sum(first_half) / len(first_half) if first_half else 1
    second_avg = sum(second_half) / len(second_half) if second_half else 1
    
    trend_diff = second_avg - first_avg
    
    # Determine trajectory
    if trend_diff > 0.3:
        direction = "improving"
        message = "Your consistency has been steadily improving"
        coaching_note = "Keep up this momentum - your identity is solidifying."
    elif trend_diff < -0.3:
        direction = "declining"
        message = "Your consistency has dipped recently"
        coaching_note = "Let's identify what changed and get you back on track."
    else:
        direction = "stable"
        message = "Your identity has been relatively stable"
        coaching_note = "Stability is good - now focus on specific weak areas to break through."
    
    # Track style evolution over time
    style_timeline = []
    for s in reversed(snapshots):
        metrics = s.get("metrics", {})
        identity = s.get("identity", {})
        style_timeline.append({
            "date": s.get("created_at"),
            "archetype": identity.get("primary_archetype", "Unknown"),
            "style": metrics.get("risk_style", "balanced"),
            "stability": metrics.get("stability_label", "mixed"),
        })
    
    # Detect style evolution narrative
    style_narrative = ""
    if len(style_timeline) >= 2:
        first_style = style_timeline[0].get("style", "balanced")
        last_style = style_timeline[-1].get("style", "balanced")
        if first_style != last_style:
            style_narrative = f"Over time, you've shifted from {first_style} to {last_style} play."
    
    return {
        "direction": direction,
        "message": message,
        "coaching_note": coaching_note,
        "style_narrative": style_narrative,
        "snapshots_analyzed": len(snapshots),
        "timeline": style_timeline[-5:],  # Last 5 snapshots for visualization
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
    
    # Archetype insight
    archetype = evolution.get("current_archetype")
    if archetype:
        parts.append(f"You are '{archetype}'.")
    
    # Comparative insight (the key "You used to be X, now you're Y" feature)
    comparative = evolution.get("comparative_insight")
    if comparative:
        parts.append(comparative)
    
    # Coaching moments
    moments = evolution.get("coaching_moments", [])
    if moments:
        parts.append(moments[0].get("message", ""))
    
    # Trajectory insight
    trajectory = evolution.get("trajectory")
    if trajectory:
        parts.append(trajectory.get("coaching_note", trajectory.get("message", "")))
    
    # Milestone insight
    milestones = evolution.get("milestones", {})
    if milestones.get("new_milestones"):
        m = milestones["new_milestones"][0]
        parts.append(f"Milestone: {m['message']}")
    
    if not parts:
        parts.append("Your chess identity continues to develop with each game.")
    
    return " ".join(parts)


async def get_identity_trajectory_summary(db, user_id: str) -> Dict:
    """
    Get a summarized trajectory view for display in UI.
    
    Returns:
        - Current archetype
        - Key changes over time
        - Next focus area
    """
    evolution = await compute_identity_evolution(db, user_id)
    
    if not evolution.get("has_evolution"):
        return {
            "has_data": False,
            "message": "Analyze more games to track your identity evolution."
        }
    
    current_identity = evolution.get("current_identity", {})
    trajectory = evolution.get("trajectory")
    
    # Get key stats
    raw = current_identity.get("raw", {})
    
    # Map style to human-readable
    style_raw = raw.get("style", "medium")
    style_readable = _map_style_label(style_raw)
    
    return {
        "has_data": True,
        "archetype": evolution.get("current_archetype", "Unknown"),
        "stability": raw.get("stability", "mixed"),
        "style": style_readable,
        "primary_leak": raw.get("leak", "unknown"),
        "trajectory_direction": trajectory.get("direction") if trajectory else "building",
        "trajectory_message": trajectory.get("message") if trajectory else "Building your identity...",
        "comparative_insight": evolution.get("comparative_insight", ""),
        "coaching_moments": evolution.get("coaching_moments", []),
        "snapshot_count": evolution.get("snapshot_count", 0),
        "next_milestone": evolution.get("milestones", {}).get("next_game_milestone"),
    }
