"""
Primary Weakness Picker — the "pick ONE thing, lock it, measure it" service.

Consumes move_observations (Theme 1 layer) to pick a single focus per user,
locks it for 14 days, and provides a day-14 outcome check.

See docs/primary_weakness_picker_scope.md for the full design.

Defaults chosen (per Mohit's implicit signoff via "go get it, finish things"):
  - Lock duration: 14 days
  - Improvement threshold: -20% rate change → "improved"
  - Regression threshold: +10% rate change → "regressed"
  - Escalation action: email suggesting Play-with-Coach (no auto-schedule)
  - New user path: minimum 10 analyzed games before assignment
  - Cooldown: 30 days on the same topic after completion

Collection: user_active_focus
Indexes:
  - (user_id, status) — 1 active per user, fast lookup
  - (locked_until) — cron finds focuses ready for outcome check
"""
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List

COLLECTION = "user_active_focus"

# Editorial impact weights — how much benefit does fixing this pattern yield
# relative to its per-game rate. Higher = coach picks it first.
IMPACT_TABLE: Dict[str, float] = {
    "piece_safety":                    1.00,
    "ignoring_king_safety_threats":    0.90,
    "fork_misses":                     0.70,
    "discovered_attack_misses":        0.70,
    "removal_of_defender_misses":      0.60,
    "neglecting_development":          0.50,
    "poor_piece_activity":             0.50,
    "pawn_structure_damage":           0.40,
    "king_activity_neglect":           0.40,
    # positive-signal-gap topics (things they DON'T do)
    "threat_awareness":                0.80,   # via threat_response_rate
    "punish_blunders":                 0.60,   # via blunder_punish_rate
}

# Topic → moments_topic_registry key (some subcategories map to same page)
TOPIC_TO_MOMENTS_KEY: Dict[str, str] = {
    "piece_safety":                    "piece_safety",
    "ignoring_king_safety_threats":    "piece_safety",  # same page for now
    "fork_misses":                     "piece_safety",
    "discovered_attack_misses":        "piece_safety",
    "removal_of_defender_misses":      "piece_safety",
    "neglecting_development":          "piece_safety",  # placeholder until per-topic pages
    "poor_piece_activity":             "piece_safety",
    "pawn_structure_damage":           "piece_safety",
    "king_activity_neglect":           "long_game_conversion",
    "threat_awareness":                "piece_safety",
    "punish_blunders":                 "piece_safety",
}

MIN_EVIDENCE = 3           # a pattern needs ≥3 occurrences to be pickable
MIN_ANALYZED_GAMES = 10    # user must have ≥10 analyzed games
LOCK_DURATION_DAYS = 14
COOLDOWN_DAYS = 30
IMPROVEMENT_THRESHOLD = -0.20
REGRESSION_THRESHOLD = +0.10
BASELINE_WINDOW_GAMES = 30


async def ensure_indexes(db) -> None:
    coll = db[COLLECTION]
    await coll.create_index([("user_id", 1), ("status", 1)])
    await coll.create_index([("locked_until", 1)])
    await coll.create_index([("user_id", 1), ("topic_key", 1)])


async def _get_active_focus(db, user_id: str) -> Optional[Dict[str, Any]]:
    return await db[COLLECTION].find_one({"user_id": user_id, "status": "active"})


async def _get_cohort_signals(db, user_id: str) -> Dict[str, Any]:
    """Compute the aggregate signals from this user's move_observations."""
    from services.move_observation_deriver import aggregate_user_signals
    # Cap at 5000 obs (roughly last 200 games) to keep read fast + focus recent
    obs = await db.move_observations.find({"user_id": user_id}).to_list(length=5000)
    return aggregate_user_signals(obs), len(obs)


async def _in_cooldown(db, user_id: str, topic: str) -> bool:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=COOLDOWN_DAYS)).isoformat()
    prev = await db[COLLECTION].find_one({
        "user_id": user_id,
        "topic_key": topic,
        "status": {"$in": ["completed", "escalated"]},
        "closed_at": {"$gte": cutoff},
    })
    return prev is not None


async def _compute_baseline_metric(db, user_id: str, topic: str) -> Dict[str, Any]:
    """Baseline per-game rate — total occurrences divided by total analyzed
    games. Simple + correct. Previous version divided by a capped n which
    made rates 30x too high."""
    games_analyzed = await db.games.count_documents(
        {"user_id": user_id, "is_analyzed": True}
    )
    total = await db.move_observations.count_documents({
        "user_id": user_id,
        "missed_pattern": topic,
    })
    rate = round(total / max(games_analyzed, 1), 3)
    return {
        "name": f"{topic}_per_game",
        "value": rate,
        "occurrence_count": total,
        "n_games_at_baseline": games_analyzed,
    }


async def pick_next_focus(db, user_id: str) -> Optional[Dict[str, Any]]:
    """Returns the topic dict to lock, or None if we shouldn't assign yet."""
    # Gate 1: don't pick if user already has an active focus
    if await _get_active_focus(db, user_id):
        return None

    # Gate 2: enough analyzed games
    n_games = await db.games.count_documents({"user_id": user_id, "is_analyzed": True})
    if n_games < MIN_ANALYZED_GAMES:
        return None

    # Signals from move_observations
    signals, n_obs = await _get_cohort_signals(db, user_id)
    if n_obs == 0:
        return None

    total_user_moves = max(signals.get("total_user_moves", 1), 1)

    # Build candidate list
    candidates: List[Dict[str, Any]] = []
    for pattern, count in (signals.get("missed_pattern_counts") or {}).items():
        if count < MIN_EVIDENCE:
            continue
        impact = IMPACT_TABLE.get(pattern, 0.3)
        # per-100-moves rate
        rate = count / total_user_moves * 100
        score = rate * impact
        candidates.append({
            "topic": pattern,
            "score": round(score, 3),
            "evidence_count": count,
            "per_100_moves": round(rate, 2),
            "impact_weight": impact,
        })

    # Positive-signal gaps (things user DOESN'T do enough of)
    threat_rate = signals.get("threat_response_rate")
    if threat_rate is not None and threat_rate < 0.7:
        candidates.append({
            "topic": "threat_awareness",
            "score": (1 - threat_rate) * 100 * IMPACT_TABLE["threat_awareness"],
            "evidence_count": signals.get("ignored_opponent_threat", 0),
            "per_100_moves": None,
            "impact_weight": IMPACT_TABLE["threat_awareness"],
        })
    punish_rate = signals.get("blunder_punish_rate")
    if punish_rate is not None and punish_rate < 0.5:
        candidates.append({
            "topic": "punish_blunders",
            "score": (1 - punish_rate) * 100 * IMPACT_TABLE["punish_blunders"],
            "evidence_count": signals.get("missed_opponent_blunder", 0),
            "per_100_moves": None,
            "impact_weight": IMPACT_TABLE["punish_blunders"],
        })

    # Cooldown filter
    fresh = []
    for c in candidates:
        if not await _in_cooldown(db, user_id, c["topic"]):
            fresh.append(c)
    if not fresh:
        return None

    # Sort desc by score. Return winner + attach runners-up so downstream
    # coaching can blend messaging. Piece_safety wins for most 1400-and-below
    # players — the runner-up is the real differentiator.
    fresh.sort(key=lambda c: -c["score"])
    winner = fresh[0]
    winner["runners_up"] = [
        {"topic": c["topic"], "score": c["score"], "evidence_count": c["evidence_count"]}
        for c in fresh[1:4]  # top 3 alternatives
    ]
    return winner


async def assign_focus(db, user_id: str) -> Optional[Dict[str, Any]]:
    """Pick + persist. Returns the created focus doc or None."""
    picked = await pick_next_focus(db, user_id)
    if not picked:
        return None
    now = datetime.now(timezone.utc)
    baseline = await _compute_baseline_metric(db, user_id, picked["topic"])
    focus = {
        "user_id": user_id,
        "status": "active",
        "topic_key": picked["topic"],
        "moments_page_topic": TOPIC_TO_MOMENTS_KEY.get(picked["topic"], "piece_safety"),
        "picker_score": picked["score"],
        "picker_evidence_count": picked["evidence_count"],
        "picker_per_100_moves": picked.get("per_100_moves"),
        "picker_impact_weight": picked.get("impact_weight"),
        "runners_up": picked.get("runners_up", []),
        "started_at": now.isoformat(),
        "locked_until": (now + timedelta(days=LOCK_DURATION_DAYS)).isoformat(),
        "baseline_metric": baseline,
        "current_metric": None,
        "resolution": None,
        "next_action": None,
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
    }
    await db[COLLECTION].insert_one(focus)
    return focus


async def check_focus_outcome(db, focus: Dict[str, Any]) -> Dict[str, Any]:
    """Called at locked_until. Returns {resolution, action, delta_pct}."""
    topic = focus["topic_key"]
    user_id = focus["user_id"]
    started_at = focus["started_at"]
    baseline_rate = focus["baseline_metric"]["value"]

    # Games analyzed since lock started
    games_since = await db.games.count_documents({
        "user_id": user_id,
        "is_analyzed": True,
        "analyzed_at": {"$gte": started_at},
    })
    if games_since == 0:
        return {"resolution": "no_data", "action": "extend", "delta_pct": None}

    obs_since = await db.move_observations.find({
        "user_id": user_id,
        "missed_pattern": topic,
        "derived_at": {"$gte": started_at},
    }).to_list(length=None)
    current_rate = len(obs_since) / games_since
    delta = (current_rate - baseline_rate) / max(baseline_rate, 0.01)

    if delta <= IMPROVEMENT_THRESHOLD:
        return {"resolution": "improved", "action": "celebrate",
                "delta_pct": round(delta * 100, 1),
                "current_metric": {"value": round(current_rate, 3),
                                   "n_games_since_start": games_since}}
    if delta >= REGRESSION_THRESHOLD:
        return {"resolution": "regressed", "action": "escalate",
                "delta_pct": round(delta * 100, 1),
                "current_metric": {"value": round(current_rate, 3),
                                   "n_games_since_start": games_since}}
    return {"resolution": "stuck", "action": "extend",
            "delta_pct": round(delta * 100, 1),
            "current_metric": {"value": round(current_rate, 3),
                               "n_games_since_start": games_since}}


async def close_focus(db, focus: Dict[str, Any], outcome: Dict[str, Any]) -> None:
    """Mark a focus completed with outcome data."""
    now = datetime.now(timezone.utc).isoformat()
    status = "completed" if outcome["action"] == "celebrate" else \
             "escalated" if outcome["action"] == "escalate" else "active"
    update = {
        "$set": {
            "resolution": outcome["resolution"],
            "next_action": outcome["action"],
            "current_metric": outcome.get("current_metric"),
            "updated_at": now,
        }
    }
    if status != "active":
        update["$set"]["status"] = status
        update["$set"]["closed_at"] = now
    else:
        # Extend the lock by another 7 days
        new_until = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        update["$set"]["locked_until"] = new_until
    await db[COLLECTION].update_one({"_id": focus["_id"]}, update)
