"""
Problem Lifecycle Manager
==========================

Tracks the state of each coaching problem across the user's journey.

States:
  ACTIVE     — currently being worked on (showing in Home/Lab/Progress)
  DECLINING  — fewer occurrences recently, still watching
  RESOLVED   — hasn't appeared in last 5+ games
  RETURNED   — was resolved, came back → ANGER ESCALATION

The lifecycle drives:
  - Which problem to show (always the highest-priority ACTIVE)
  - When to advance to the next problem (current RESOLVED)
  - Anger level when a RESOLVED problem returns

Storage: problem_lifecycle collection
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional
from services.pattern_decay_service import compute_pattern_scores

logger = logging.getLogger(__name__)

# How many clean games before a problem is RESOLVED
RESOLVE_THRESHOLD = 5

# Anger levels when problem returns
ANGER_LEVELS = {
    "first_time":    {"tone": "calm",   "prefix": ""},
    "recurring":     {"tone": "firm",   "prefix": "Again — "},
    "returned":      {"tone": "sharp",  "prefix": "This came back. "},
    "chronic":       {"tone": "harsh",  "prefix": "We fixed this before. You stopped applying the rule. "},
}


async def get_problem_state(db, user_id: str, category: str) -> Dict:
    """
    Get the lifecycle state of a specific problem.
    """
    doc = await db.problem_lifecycle.find_one(
        {"user_id": user_id, "category": category},
        {"_id": 0}
    )
    if not doc:
        return {"state": "active", "anger": "first_time", "times_resolved": 0, "times_returned": 0}
    return doc


async def update_problem_lifecycle(
    db,
    user_id: str,
    enriched_games: List[Dict],
    game_reasons: List[Dict],
) -> Dict:
    """
    Update the lifecycle for all problems based on current game data.
    Called after game analysis or when loading Lab.

    Returns the current active problem with its anger level.
    """
    from services.game_reason_classifier import aggregate_game_reasons

    top_problems = aggregate_game_reasons(game_reasons)
    if not top_problems:
        return None

    # Get current active problem from DB
    current_active = await db.problem_lifecycle.find_one(
        {"user_id": user_id, "state": {"$in": ["active", "returned"]}},
        {"_id": 0}
    )

    primary_category = top_problems[0]["category"]
    primary_count = top_problems[0]["count"]

    # Check if current active problem is still the top one
    if current_active and current_active.get("category") != primary_category:
        old_category = current_active["category"]
        old_count = next((p["count"] for p in top_problems if p["category"] == old_category), 0)

        # Check decay: if old problem has few recent occurrences, it's declining/resolved
        recent_losses = [g for g in enriched_games[:10] if g.get("result") == "L" or g.get("result") == "D"]
        recent_with_old = sum(1 for g in recent_losses
                             if g.get("game_reason", {}).get("category") == old_category)

        if recent_with_old == 0:
            # Old problem is RESOLVED
            await db.problem_lifecycle.update_one(
                {"user_id": user_id, "category": old_category},
                {"$set": {
                    "state": "resolved",
                    "resolved_at": datetime.now(timezone.utc).isoformat(),
                    "times_resolved": (current_active.get("times_resolved", 0) or 0) + 1,
                }, "$setOnInsert": {"user_id": user_id, "category": old_category}},
                upsert=True
            )
            logger.info(f"[LIFECYCLE] {old_category} → RESOLVED for {user_id}")

    # Check if primary problem was previously resolved (RETURNED = anger escalation)
    prev_state = await db.problem_lifecycle.find_one(
        {"user_id": user_id, "category": primary_category},
        {"_id": 0}
    )

    anger = "first_time"
    times_resolved = 0
    times_returned = 0

    if prev_state:
        times_resolved = prev_state.get("times_resolved", 0)
        times_returned = prev_state.get("times_returned", 0)

        if prev_state.get("state") == "resolved":
            # It's BACK — anger escalation
            anger = "returned"
            times_returned += 1
            if times_returned >= 2:
                anger = "chronic"
            logger.info(f"[LIFECYCLE] {primary_category} RETURNED (times: {times_returned}) for {user_id}")
        elif prev_state.get("state") in ("active", "returned"):
            # Still active
            if primary_count >= 5:
                anger = "recurring"
            else:
                anger = "first_time"
    else:
        anger = "first_time" if primary_count < 5 else "recurring"

    # Save current state
    await db.problem_lifecycle.update_one(
        {"user_id": user_id, "category": primary_category},
        {"$set": {
            "state": "returned" if anger in ("returned", "chronic") else "active",
            "anger": anger,
            "count": primary_count,
            "times_resolved": times_resolved,
            "times_returned": times_returned,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }, "$setOnInsert": {"user_id": user_id, "category": primary_category}},
        upsert=True
    )

    return {
        "category": primary_category,
        "anger": anger,
        "anger_config": ANGER_LEVELS.get(anger, ANGER_LEVELS["first_time"]),
        "times_resolved": times_resolved,
        "times_returned": times_returned,
    }


def get_anger_headline_prefix(anger: str) -> str:
    """Get the prefix to add to coaching headlines based on anger level."""
    return ANGER_LEVELS.get(anger, ANGER_LEVELS["first_time"])["prefix"]
