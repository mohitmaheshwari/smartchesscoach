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
    "snap_decision", "impulsive_critical", "time_pressure_blunder",
    "slow_paralysis", "chronic_timeout",
}


def _dominant_subtype_of(focus: Dict[str, Any]) -> Optional[str]:
    """Which subtype this focus is actually about.

    `dominant_subtype` is read from the focus document by the original code,
    and NOTHING HAS EVER WRITTEN IT: measured 2026-09-30, 0 of 48 active
    weakness focuses carry the field. The consequences differed by topic and
    both were wrong:

      time_management (8 users) -- the query fell through to
        {"missed_pattern": "time_management"}, and no observation carries that
        as a pattern, so the card read 0 events across 810 games and rendered
        nothing. This is the "it's not showing" report.

      every other topic (40 users) -- it fell through to
        {"missed_pattern": topic}, which DOES match, so the count came back
        non-zero but covered the whole pattern instead of the subtype the focus
        is about. Wrong, and invisible because it looked plausible.

    The subtype is not lost: the picker stamps it into `detector_quality_id`
    as gap:<topic>:<subtype>, and `subtype_histogram` holds the counts. So it is
    derived here rather than migrated, which fixes all 48 without a write, and
    keeps working for documents written before the field existed.

    `_pick_dominant_subtype` is imported from focus_bridge rather than
    reimplemented -- it already owns the "highest count, ignoring the noise
    buckets" rule and a second copy would drift.
    """
    stored = focus.get("dominant_subtype")
    if stored:
        return stored

    # The id the picker stamped is the most direct evidence of what it chose.
    quality_id = str(focus.get("detector_quality_id") or "")
    parts = quality_id.split(":")
    if len(parts) == 3 and parts[0] == "gap" and parts[2]:
        return parts[2]

    from services.focus_bridge import _pick_dominant_subtype
    return _pick_dominant_subtype(focus.get("subtype_histogram") or {})


async def _timeout_loss_stats(db, user_id: str, topic: str,
                              focus: Dict[str, Any]) -> Dict[str, Any]:
    """Recall stats for a focus on games lost to the clock.

    Same shape as the per-move path, counted over GAMES. An "event" here is a
    game the player lost on time, which is what the picker counted when it
    chose this focus.
    """
    from services.game_outcome import lost_on_time

    now = datetime.now(timezone.utc)
    week_start = now - timedelta(days=7)
    started_iso = focus.get("started_at")
    started_dt = None
    if started_iso:
        try:
            started_dt = datetime.fromisoformat(str(started_iso).replace("Z", "+00:00"))
            if started_dt.tzinfo is None:
                started_dt = started_dt.replace(tzinfo=timezone.utc)
        except (TypeError, ValueError):
            started_dt = None

    lifetime_events = lifetime_games = 0
    week_events = week_games = 0
    since_events = since_games = 0
    async for game in db.games.find(
        {"user_id": user_id, "is_analyzed": True},
        {"_id": 0, "result": 1, "user_color": 1, "termination": 1,
         "played_at_utc": 1},
    ):
        lifetime_games += 1
        # played_at_utc is the typed date. `date_played` holds three
        # incompatible shapes and sorts wrongly as a string.
        played = game.get("played_at_utc")
        if isinstance(played, datetime) and played.tzinfo is None:
            played = played.replace(tzinfo=timezone.utc)
        timed_out = lost_on_time(game)
        if timed_out:
            lifetime_events += 1
        if isinstance(played, datetime):
            if played >= week_start:
                week_games += 1
                if timed_out:
                    week_events += 1
            if started_dt and played >= started_dt:
                since_games += 1
                if timed_out:
                    since_events += 1

    days_since_start = None
    if started_dt:
        days_since_start = max(0, (now - started_dt).days)

    return {
        "topic_key": topic,
        "dominant_subtype": "chronic_timeout",
        "lifetime_events": lifetime_events,
        "lifetime_games": lifetime_games,
        "week_events": week_events,
        "week_games": week_games,
        "since_focus_events": since_events,
        "since_focus_games": since_games,
        "days_since_focus_start": days_since_start,
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
    dom = _dominant_subtype_of(focus)
    if not topic:
        return {}

    # Build the observation query per topic shape
    if topic == "time_management" and dom in TIME_MANAGEMENT_SUBTYPES:
        base_query = {"user_id": user_id, "time_flag": dom}
    elif dom:
        base_query = {"user_id": user_id, "missed_pattern": topic, "subtype": dom}
    else:
        base_query = {"user_id": user_id, "missed_pattern": topic}

    # chronic_timeout is a GAME-level event and has no move observations at
    # all, so it is counted from games and returns early rather than being
    # threaded through three per-move queries that can only ever return zero.
    if dom == "chronic_timeout":
        return await _timeout_loss_stats(db, user_id, topic, focus)

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
    "snap_decision":          "moves you played fast for you",
    "impulsive_critical":     "moves you played fast",
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
    "king_walked_into_attack": "king runs into attack",
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
