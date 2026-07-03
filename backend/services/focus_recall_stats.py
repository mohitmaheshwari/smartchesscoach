"""
Focus Recall Stats — the "coach remembers" backbone.

For a given user's active focus, computes three time windows of event
counts against move_observations:

  - LIFETIME: everything on record
  - WEEK: last 7 days (rolling)
  - SINCE_FOCUS: since started_at of the current focus

Handles two shapes of focus:
  - Analyzer-tagged (piece_safety, king_safety, missed_tactic, etc.) —
    filter by `missed_pattern == topic_key AND subtype == dominant_subtype`
  - Time management (synthetic) — filter by `time_flag == dominant_subtype`

Used by session_greeting_service to render lines like:
  "You've had 88 impulsive-critical moments across 178 games — 12 in the
   last 7 days, 5 since your focus started 3 days ago."
"""
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional


TIME_MANAGEMENT_SUBTYPES = {
    "impulsive_critical", "time_pressure_blunder",
    "slow_paralysis", "chronic_timeout",
}


async def compute_focus_recall_stats(
    db, user_id: str, focus: Dict[str, Any]
) -> Dict[str, Any]:
    """Return recall stats for the user's active focus.

    Shape:
      {
        "lifetime_events": int,
        "lifetime_games": int,
        "week_events": int,
        "week_games": int,
        "since_focus_events": int,
        "since_focus_games": int,
        "days_since_focus_start": int,
        "topic_key": str,
        "dominant_subtype": str | None,
      }
    """
    topic = focus.get("topic_key")
    dom = focus.get("dominant_subtype")
    if not topic:
        return {}

    # Build the observation query per topic shape
    if topic == "time_management" and dom in TIME_MANAGEMENT_SUBTYPES:
        base_query = {"user_id": user_id, "time_flag": dom}
    elif dom:
        base_query = {"user_id": user_id, "missed_pattern": topic, "subtype": dom}
    else:
        base_query = {"user_id": user_id, "missed_pattern": topic}

    # LIFETIME
    lifetime_events = await db.move_observations.count_documents(base_query)
    lifetime_games = await db.games.count_documents(
        {"user_id": user_id, "is_analyzed": True}
    )

    # LAST 7 DAYS (rolling).
    # Filter by the GAME'S date_played, not by observation.derived_at
    # — the backfill sets derived_at to "when we processed," not
    # "when the user played."
    now = datetime.now(timezone.utc)
    week_start_iso = (now - timedelta(days=7)).isoformat()
    week_game_ids = await db.games.distinct("game_id", {
        "user_id": user_id, "is_analyzed": True,
        "date_played": {"$gte": week_start_iso},
    })
    week_query = dict(base_query)
    if week_game_ids:
        week_query["game_id"] = {"$in": week_game_ids}
        week_events = await db.move_observations.count_documents(week_query)
    else:
        week_events = 0
    week_games = len(week_game_ids)

    # SINCE FOCUS STARTED
    started_iso = focus.get("started_at")
    since_events = 0
    since_games = 0
    days_since_start = None
    if started_iso:
        try:
            started_dt = datetime.fromisoformat(started_iso.replace("Z", "+00:00"))
            days_since_start = max(0, (now - started_dt).days)
            since_game_ids = await db.games.distinct("game_id", {
                "user_id": user_id, "is_analyzed": True,
                "date_played": {"$gte": started_iso},
            })
            since_query = dict(base_query)
            if since_game_ids:
                since_query["game_id"] = {"$in": since_game_ids}
                since_events = await db.move_observations.count_documents(since_query)
            since_games = len(since_game_ids)
        except Exception:
            pass

    return {
        "topic_key": topic,
        "dominant_subtype": dom,
        "lifetime_events": lifetime_events,
        "lifetime_games": lifetime_games,
        "week_events": week_events,
        "week_games": week_games,
        "since_focus_events": since_events,
        "since_focus_games": since_games,
        "days_since_focus_start": days_since_start,
    }


def build_recall_sentence(stats: Dict[str, Any]) -> Optional[str]:
    """Turn the stats into a coach-voice one-sentence recall.

    Prefers strongest number. If lifetime is impressive → lead with it.
    If week is notable → mention it. If since-focus has data → mention it.
    """
    if not stats or not stats.get("lifetime_events"):
        return None

    dom = stats.get("dominant_subtype") or ""
    subject = _subject_phrase(dom)

    lifetime = stats["lifetime_events"]
    lifetime_games = stats.get("lifetime_games") or 0
    week = stats.get("week_events") or 0
    since = stats.get("since_focus_events") or 0
    days_since = stats.get("days_since_focus_start")

    parts = []

    # Line 1 — lifetime
    if lifetime_games > 0:
        parts.append(f"You've had {lifetime} {subject} across {lifetime_games} analyzed games.")
    else:
        parts.append(f"You've had {lifetime} {subject}.")

    # Line 2 — recent window (whichever is more meaningful)
    trailing = []
    if week > 0:
        trailing.append(f"{week} in the last 7 days")
    if since > 0 and days_since is not None:
        if days_since == 0:
            trailing.append(f"{since} today alone")
        elif days_since <= 2:
            trailing.append(f"{since} since your focus started {days_since}d ago")
        else:
            trailing.append(f"{since} since your focus started {days_since} days ago")
    if trailing:
        parts[-1] = parts[-1].rstrip(".") + " — " + ", ".join(trailing) + "."

    return " ".join(parts)


_SUBJECT_MAP = {
    "impulsive_critical":     "impulsive-critical moments",
    "time_pressure_blunder":  "time-pressure blunders",
    "slow_paralysis":         "slow-paralysis blunders",
    "chronic_timeout":        "games lost on time",
    "simple_hang":            "simple hangs",
    "threat_ignored":         "ignored opponent threats",
    "tactical_seq_loss":      "tactical-sequence losses",
    "quiet_blunder":          "quiet-position blunders",
    "small_slip":             "small slips",
    "ignored_king_attack":    "ignored king attacks",
    "weakened_shelter":       "shelter weakenings",
    "king_in_center":         "moments with your king in the center",
    "king_walked_into_attack": "king walks into attack",
    "missed_fork":            "missed forks",
    "missed_pin":             "missed pins",
    "missed_skewer":          "missed skewers",
    "missed_discovered_attack": "missed discovered attacks",
    "missed_generic_tactic":  "missed tactics",
    "generic_oversight":      "tactical oversights",
    "queen_out_early":        "early queen moves",
    "piece_parked_on_start":  "moments with a parked piece",
    "isolated_pawn_created":  "moments creating isolated pawns",
    "backward_pawn_created":  "moments creating backward pawns",
    "passive_king_in_endgame":"passive king endgames",
}


def _subject_phrase(subtype: str) -> str:
    return _SUBJECT_MAP.get(subtype, "focus moments")
