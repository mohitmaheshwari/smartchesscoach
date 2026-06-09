"""
Focus Engine — ONE weakness at a time
======================================

Converts root behavioral clusters into a persistent focus.
The focus persists across games until the player improves.

Flow:
  Game ends → detect root problem → set focus → lock training
  Next game → same focus enforced → warnings + holds
  After training → reduce severity → eventually resolve

Enforcement levels:
  LIGHT   — soft reminders (small issue)
  MEDIUM  — warnings (recurring)
  STRICT  — blocks + required acknowledgment (dominant issue)
"""

import logging
from typing import Dict, Optional, List
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# ─── ENFORCEMENT LEVELS ───────────────────────────────────────────

ENFORCEMENT_LEVELS = {
    "LIGHT": {
        "label": "Light",
        "description": "Gentle reminders",
        "puzzles_required": 3,
    },
    "MEDIUM": {
        "label": "Medium",
        "description": "Active warnings during play",
        "puzzles_required": 5,
    },
    "STRICT": {
        "label": "Strict",
        "description": "Must acknowledge before committing moves",
        "puzzles_required": 7,
    },
}

# ─── FOCUS RULES PER CLUSTER ─────────────────────────────────────

FOCUS_RULES = {
    # Universal Habit Coach V1 (CANDIDATE habit). Detected mistake = piece_safety only
    # ("anything hanging?"); the threat-detection half is not reliably measurable yet
    # (see services/core_habit.py). The opponent-threat clause is intentionally omitted
    # from the rule text so the reminder matches what we actually measure.
    "threat_scan": {
        "name": "Threat Scan",
        "rule": "Before you move, check: is any piece of yours hanging?",
        "short_rule": "Anything hanging?",
        "puzzle_type": "piece_safety",
        "puzzle_query": {"pattern_type": {"$in": ["piece_safety"]}},
    },
    "threat_awareness": {
        "name": "Threat Awareness",
        "rule": "Before every move, ask: what is my opponent attacking?",
        "short_rule": "Check opponent threats first",
        "puzzle_type": "threat_detection",
        "puzzle_query": {"pattern_type": {"$in": ["piece_safety", "tactical_oversight", "calculation_depth"]}},
    },
    "calculation": {
        "name": "Calculation Discipline",
        "rule": "Before committing, trace 2 moves ahead. What can your opponent do?",
        "short_rule": "Calculate before moving",
        "puzzle_type": "calculation",
        "puzzle_query": {"pattern_type": {"$in": ["calculation_depth", "tactical_oversight"]}},
    },
    "patience": {
        "name": "Patience & Timing",
        "rule": "Finish your setup before starting action. Development first.",
        "short_rule": "Build position before attacking",
        "puzzle_type": "patience",
        "puzzle_query": {"pattern_type": {"$in": ["piece_safety", "calculation_depth"]}},
    },
    "coordination": {
        "name": "Piece Coordination",
        "rule": "Connect your pieces. Make sure they defend each other.",
        "short_rule": "Coordinate pieces",
        "puzzle_type": "coordination",
        "puzzle_query": {"pattern_type": {"$in": ["piece_safety", "tactical_oversight"]}},
    },
    "planning": {
        "name": "Planning & Direction",
        "rule": "Before each move, ask: what am I trying to achieve in the next 3 moves?",
        "short_rule": "Play with a plan",
        "puzzle_type": "planning",
        "puzzle_query": {"pattern_type": {"$in": ["calculation_depth", "piece_safety"]}},
    },
}


# ─── GET / SET FOCUS ──────────────────────────────────────────────

# Map curriculum brain's current_focus keys → focus_engine cluster keys.
# Keeps users.focus aligned with coach_memory.learning.current_focus so
# HomePage's focusPlan card can't disagree with Lab's active_focus.
_BRAIN_TO_CLUSTER = {
    "hanging_piece":    "threat_awareness",
    "missed_fork":      "threat_awareness",
    "missed_pin":       "threat_awareness",
    "missed_skewer":    "threat_awareness",
    "missed_discovery": "threat_awareness",
    "missed_overload":  "threat_awareness",
    "king_safety":      "threat_awareness",
    "tactical_error":   "calculation",
}


def cluster_from_brain_focus(brain_focus: Optional[str]) -> Optional[str]:
    """Map a coach_memory.learning.current_focus value → focus_engine cluster."""
    if not brain_focus:
        return None
    if brain_focus in _BRAIN_TO_CLUSTER:
        return _BRAIN_TO_CLUSTER[brain_focus]
    if brain_focus.startswith("trap:") or brain_focus.startswith("opening:"):
        return "planning"
    if brain_focus.startswith("endgame:"):
        return "calculation"
    return None


async def get_user_focus(db, user_id: str) -> Optional[Dict]:
    """Get the current focus for a user. Returns None if no focus set."""
    doc = await db.users.find_one(
        {"user_id": user_id},
        {"_id": 0, "focus": 1}
    )
    return doc.get("focus") if doc else None


async def sync_focus_with_brain(db, user_id: str, brain_focus: str) -> Optional[Dict]:
    """
    Make users.focus agree with coach_memory.learning.current_focus.

    Called after every game whenever the brain sets a prescription. Keeps
    the cluster name on users.focus aligned so HomePage's focusPlan card
    points at the same thing Lab's active_focus does.

    If no focus doc exists yet, creates one (game_results empty).
    If cluster changes, resets the game_results streak tracker.
    Preserves progress when the cluster is unchanged.
    """
    cluster = cluster_from_brain_focus(brain_focus)
    if not cluster:
        return None

    rule_config = FOCUS_RULES.get(cluster, {})
    existing = await get_user_focus(db, user_id)

    # Universal Habit Coach: a pilot / universal focus is AUTHORITATIVE. The brain must not
    # overwrite it — doing so wiped the holdout arm (reminder_enabled) and the universal flag
    # the moment a pilot user's game was analyzed, silently corrupting the experiment. The
    # brain keeps its own state in coach_memory; it just stops clobbering users.focus here.
    if existing and existing.get("universal"):
        return existing

    if existing and existing.get("cluster") == cluster:
        # Same cluster — keep the progress tracker, only refresh rule text
        # (cheap no-op write, keeps things consistent).
        existing["name"] = rule_config.get("name", existing.get("name"))
        existing["rule"] = rule_config.get("rule", existing.get("rule"))
        existing["short_rule"] = rule_config.get("short_rule", existing.get("short_rule"))
        await db.users.update_one(
            {"user_id": user_id}, {"$set": {"focus": existing}}
        )
        return existing

    # New or changed cluster — fresh focus doc
    focus = {
        "cluster": cluster,
        "name": rule_config.get("name", cluster.replace("_", " ").title()),
        "rule": rule_config.get("rule", ""),
        "short_rule": rule_config.get("short_rule", ""),
        "enforcement_level": "LIGHT",
        "puzzles_required": ENFORCEMENT_LEVELS["LIGHT"]["puzzles_required"],
        "puzzles_completed": 0,
        "training_locked": False,
        "score": 1,
        "set_at": datetime.now(timezone.utc).isoformat(),
        "games_with_focus": 0,
        "violations_history": [],
        "games_target": 5,
        "clean_threshold": 3,
        "game_results": [],
        "synced_from_brain": True,
        "brain_focus": brain_focus,
    }
    await db.users.update_one(
        {"user_id": user_id}, {"$set": {"focus": focus}}, upsert=True
    )
    logger.info(f"[FOCUS-SYNC] {user_id}: {brain_focus} → cluster={cluster}")
    return focus


async def set_user_focus(db, user_id: str, root_problem: Dict) -> Dict:
    """
    Set or update the user's focus based on root problem detection.

    Args:
        root_problem: {"primary": {"key": "threat_awareness", "score": 15, ...}, ...}

    Returns:
        The focus object that was set.
    """
    primary = root_problem.get("primary")
    if not primary:
        return None

    cluster_key = primary["key"]
    score = primary.get("score", 0)
    rule_config = FOCUS_RULES.get(cluster_key, {})

    # Determine enforcement level based on score
    if score >= 10:
        level = "STRICT"
    elif score >= 5:
        level = "MEDIUM"
    else:
        level = "LIGHT"

    enforcement = ENFORCEMENT_LEVELS[level]

    focus = {
        "cluster": cluster_key,
        "name": rule_config.get("name", primary.get("label", cluster_key)),
        "rule": rule_config.get("rule", primary.get("coaching", "")),
        "short_rule": rule_config.get("short_rule", ""),
        "enforcement_level": level,
        "puzzles_required": enforcement["puzzles_required"],
        "puzzles_completed": 0,
        "training_locked": False,  # Coach is never blocked — guidance only
        "score": score,
        "set_at": datetime.now(timezone.utc).isoformat(),
        "games_with_focus": 0,
        "violations_history": [],
        # Game-based graduation tracking
        "games_target": 5,  # Graduate after 3/5 clean games
        "clean_threshold": 3,  # Need 3 clean out of 5
        "game_results": [],  # [{clean: bool, game_id, timestamp}] — last 5
    }

    await db.users.update_one(
        {"user_id": user_id},
        {"$set": {"focus": focus}}
    )

    logger.info(f"[FOCUS] Set focus for {user_id}: {cluster_key} ({level})")
    return focus


async def set_universal_focus(db, user_id: str, reminder_enabled: bool = True,
                              habit: str = "threat_scan") -> Dict:
    """Task 3 — assign the FIXED universal habit. No per-user weakness detection (we proved
    mistake-frequency doesn't differentiate players). Every cohort user gets the same habit.

    `reminder_enabled` is the L4 holdout switch: True = TREATMENT (gets the in-game reminder),
    False = CONTROL (focus tracked + measured identically, but NO reminder). Both arms are
    measured by focus_measurement; only the reminder differs — that's the causal variable."""
    from services.core_habit import HABITS
    h = HABITS.get(habit, {})
    rule_cfg = FOCUS_RULES.get(habit, {})
    focus = {
        "cluster": habit,
        "habit": habit,
        "universal": True,                      # set by Task 3, not by weakness detection
        "reminder_enabled": reminder_enabled,   # L4 holdout arm (treatment vs control)
        "name": h.get("label", "Threat Scan"),
        "rule": rule_cfg.get("rule", h.get("rule", "")),
        "short_rule": rule_cfg.get("short_rule", "Anything hanging?"),
        "enforcement_level": "LIGHT",
        "set_at": datetime.now(timezone.utc).isoformat(),
        "games_with_focus": 0,
        "game_results": [],
        "games_target": 5,
        "clean_threshold": 3,
    }
    await db.users.update_one({"user_id": user_id}, {"$set": {"focus": focus}}, upsert=True)
    logger.info(f"[FOCUS] Universal habit set for {user_id}: {habit} (reminder={reminder_enabled})")
    return focus


async def update_focus_after_game(
    db, user_id: str, behavior_summary: Dict, root_problem: Dict,
    game_id: str = None, session_id: str = None,
) -> Dict:
    """
    Update focus after a game ends.
    Tracks whether this game was "clean" for the focus behavior.
    Graduates focus when 3/5 games are clean.
    """
    current_focus = await get_user_focus(db, user_id)

    # No focus yet -> SET one. Setting a focus requires a detected primary; this is the
    # DETECTION system's job, kept separate from measurement below.
    if not current_focus:
        return await set_user_focus(db, user_id, root_problem)

    # ─── MEASUREMENT (decoupled system — services/focus_measurement.py) ───
    # Runs whenever a focus exists. It is NEVER gated on root re-detection (the old
    # `if not primary: return current_focus` silent-skip hit 96% of games -> games_with_focus=0
    # for 50/51 users) and NEVER reads the sparse legacy behavior_summary (6% populated).
    # It reads cognitive_gap from game_analyses — the same source as the L4 metric — idempotently.
    from services.focus_measurement import measure_user
    habit = current_focus.get("habit", "threat_scan")  # V1 universal habit (candidate)
    measurement = await measure_user(db, user_id, habit, write=True)
    results = measurement.get("game_results", [])
    current_cluster = current_focus.get("cluster")

    # ─── GRADUATION (reads the measurement; 3-of-last-5 clean) ───
    games = measurement["games_with_focus"]
    clean_threshold = current_focus.get("clean_threshold", 3)
    games_target = current_focus.get("games_target", 5)
    last_n = results[-games_target:]
    graduated = (
        len(last_n) >= games_target
        and sum(1 for r in last_n if r["clean"]) >= clean_threshold
    )

    if graduated:
        clean_count = sum(1 for r in last_n if r["clean"])
        logger.info(f"[FOCUS] GRADUATED {user_id}: {current_cluster} ({clean_count}/{games_target} clean)")
        await db.focus_history.insert_one({
            "user_id": user_id,
            "cluster": current_cluster,
            "name": current_focus.get("name"),
            "rule": current_focus.get("rule"),
            "games_played": games,
            "game_results": last_n,
            "graduated_at": datetime.now(timezone.utc).isoformat(),
            "started_at": current_focus.get("set_at"),
        })
        # Re-detection: pick the next focus (DETECTION system; needs a primary/secondary).
        secondary = root_problem.get("secondary", [])
        if secondary:
            logger.info(f"[FOCUS] Next focus for {user_id}: {secondary[0].get('key')}")
            return await set_user_focus(db, user_id, {"primary": secondary[0]})
        await db.users.update_one({"user_id": user_id}, {"$set": {"focus": None}})
        return None

    # Not graduated -> keep the focus. (Re-detection/refocus only happens on graduation.
    # Measurement already recorded above, independent of whether root_problem had a primary.)
    return current_focus

    # ─── NOT GRADUATED — UPDATE STATS ───
    new_cluster = primary["key"]
    new_score = primary.get("score", 0)
    old_score = current_focus.get("score", 0)

    # Adjust enforcement based on trend
    new_level = current_focus["enforcement_level"]
    if new_score < old_score * 0.6:
        # Significant improvement — reduce enforcement
        if new_level == "STRICT":
            new_level = "MEDIUM"
        elif new_level == "MEDIUM":
            new_level = "LIGHT"

    await db.users.update_one(
        {"user_id": user_id},
        {"$set": {
            "focus.score": new_score,
            "focus.games_with_focus": games,
            "focus.enforcement_level": new_level,
            "focus.last_game_violations": cluster_violations,
            "focus.last_game_clean": is_clean,
            "focus.game_results": game_results,
            "focus.updated_at": datetime.now(timezone.utc).isoformat(),
        }}
    )

    # Switch focus if a MUCH stronger problem emerged
    if new_cluster != current_cluster and new_score > old_score * 2:
        logger.info(f"[FOCUS] Switching {user_id}: {current_cluster} -> {new_cluster} (score {old_score} -> {new_score})")
        return await set_user_focus(db, user_id, root_problem)

    updated = await get_user_focus(db, user_id)
    logger.info(f"[FOCUS] Game {games}: {'CLEAN' if is_clean else f'{cluster_violations} violations'} for {current_cluster}")
    return updated


async def record_puzzle_completion(db, user_id: str) -> Dict:
    """Record that user completed one focus puzzle."""
    focus = await get_user_focus(db, user_id)
    if not focus:
        return None

    new_count = focus.get("puzzles_completed", 0) + 1
    puzzles_needed = focus.get("puzzles_required", 5)
    still_locked = new_count < puzzles_needed

    await db.users.update_one(
        {"user_id": user_id},
        {"$set": {
            "focus.puzzles_completed": new_count,
            "focus.training_locked": still_locked,
        }}
    )

    if not still_locked:
        logger.info(f"[FOCUS] Training unlocked for {user_id}: {new_count}/{puzzles_needed} puzzles done")

    return {
        "puzzles_completed": new_count,
        "puzzles_required": puzzles_needed,
        "training_locked": still_locked,
    }


# ─── FOR PLAY WITH COACH ─────────────────────────────────────────

def get_enforcement_message(focus: Dict, violation_count: int) -> Optional[Dict]:
    """
    Get enforcement message based on focus + violation count this game.
    Returns None if no enforcement needed.
    """
    if not focus:
        return None

    # L4 HOLDOUT: control-arm users are measured identically but never reminded.
    # This is the single causal variable of the experiment — gate it here so every
    # reminder call site (PWC pre-move, etc.) honours the arm automatically.
    if focus.get("reminder_enabled") is False:
        return None

    level = focus.get("enforcement_level", "LIGHT")
    rule = focus.get("short_rule", focus.get("rule", ""))

    if level == "LIGHT":
        if violation_count == 1:
            return {"type": "reminder", "text": f"Remember: {rule}"}
        elif violation_count >= 2:
            return {"type": "warning", "text": f"This is your focus area. {rule}"}
        return None

    elif level == "MEDIUM":
        if violation_count == 1:
            return {"type": "warning", "text": f"You just violated your focus: {rule}"}
        elif violation_count >= 2:
            return {"type": "strong_warning", "text": f"This keeps happening. {rule}"}
        return None

    elif level == "STRICT":
        if violation_count == 1:
            return {"type": "warning", "text": f"Focus violation: {rule}"}
        elif violation_count == 2:
            return {"type": "strong_warning", "text": f"Same mistake again. {rule}"}
        elif violation_count >= 3:
            return {
                "type": "checkpoint",
                "text": f"You've ignored this 3 times. {rule}",
                "requires_acknowledgment": True,
            }
        return None

    return None
