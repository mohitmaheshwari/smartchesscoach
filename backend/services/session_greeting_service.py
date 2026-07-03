"""
Session Greeting Service — the first coaching message the user sees
when they open Play with Coach.

Warm, personal, and CONTINUOUS across sessions. Reads:
  - Active focus (from focus_bridge) — day into focus, topic, dominant subtype
  - Last coach session — game outcome, mission scoreboard, biggest miss

Returns a 1-3 sentence coaching greeting that stitches the current
session to the ongoing focus + the last time they showed up.

Example outputs:

  "Welcome back — day 4 of your king-safety focus. Last game you
   handled 3/5 focus moments cleanly. Let's push for 4/5 today."

  "Day 7 already — halfway through your time-management focus. Last
   game you played move 22 in 1.2 seconds; watch the clock on
   critical moments today."
"""
from datetime import datetime, timezone
from typing import Any, Dict, Optional


async def build_session_greeting(db, user_id: str) -> Optional[Dict[str, Any]]:
    """Build the greeting struct for a fresh session start.
    Never raises — returns None on any failure so the caller can fall
    back to a generic hello."""
    try:
        from services.focus_bridge import get_active_focus_bundle
        focus = await get_active_focus_bundle(db, user_id)
    except Exception:
        focus = None

    if not focus or not focus.get("topic_key"):
        return None

    days_in = focus.get("days_into_focus") or 0
    topic_label = focus.get("topic_label") or focus["topic_key"].replace("_", " ").title()
    dominant = focus.get("dominant_subtype")

    # Look up the user's LAST coach session for continuity
    last_session_summary = await _last_session_summary(db, user_id)

    # Compute recall stats — this is what makes the coach feel present.
    # "You've had 88 X across 178 games — 12 in the last 7 days,
    #  5 since your focus started 4 days ago."
    recall_sentence = None
    recall_stats = None
    try:
        from services.focus_recall_stats import compute_focus_recall_stats, build_recall_sentence
        recall_stats = await compute_focus_recall_stats(db, user_id, focus)
        recall_sentence = build_recall_sentence(recall_stats)
    except Exception:
        pass

    parts = []
    # Line 1: which day of the focus
    if days_in == 0:
        parts.append(f"Day 1 of your focus on {topic_label.lower()}. Let's set a baseline today.")
    else:
        day_num = days_in + 1
        parts.append(f"Welcome back — day {day_num} of your focus on {topic_label.lower()}.")

    # Line 2: recall sentence — the "coach remembers" line
    if recall_sentence:
        parts.append(recall_sentence)

    # Line 3: reference the last session if we have one
    if last_session_summary:
        parts.append(last_session_summary)

    # Line 4: focus reminder if there's a specific subtype closing available
    if dominant:
        parts.append(_subtype_prompt(dominant))

    return {
        "text": " ".join(p for p in parts if p),
        "day_num": days_in + 1,
        "topic_key": focus["topic_key"],
        "dominant_subtype": dominant,
        "referenced_last_session": bool(last_session_summary),
        "recall_stats": recall_stats,
        "recall_sentence": recall_sentence,
    }


async def _last_session_summary(db, user_id: str) -> Optional[str]:
    """Return a one-sentence recap of the user's most recent coach session,
    or None if they don't have one."""
    try:
        last = await db.coach_sessions.find_one(
            {"user_id": user_id, "status": {"$in": ["completed", "abandoned", "resigned"]}},
            sort=[("ended_at", -1)],
        )
    except Exception:
        return None
    if not last:
        return None

    sb = last.get("mission_scoreboard") or {}
    matched = sb.get("matched_moments", 0)
    handled = sb.get("handled_correctly", 0)
    if matched > 0:
        if handled == matched:
            return f"Last game you handled all {matched} focus moments cleanly — let's keep it going."
        elif handled >= matched * 0.7:
            return f"Last game you handled {handled}/{matched} focus moments cleanly."
        else:
            return f"Last game you handled only {handled}/{matched} focus moments cleanly — let's watch for the pattern today."

    # No scoreboard hits — use game outcome instead
    result = last.get("result")
    ended_at = last.get("ended_at") or last.get("last_move_at")
    when = _relative_time(ended_at)
    if result and when:
        outcome = {"user_won": "you won", "coach_won": "you lost", "draw": "you drew"}.get(result, "game ended")
        return f"Last time ({when}), {outcome}."
    return None


def _relative_time(t) -> Optional[str]:
    if not t:
        return None
    try:
        if isinstance(t, str):
            dt = datetime.fromisoformat(t.replace("Z", "+00:00"))
        else:
            dt = t
        if not dt.tzinfo:
            dt = dt.replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - dt
        days = delta.days
        if days <= 0:
            hours = delta.seconds // 3600
            if hours < 1:
                return "just now"
            return f"{hours}h ago"
        if days == 1:
            return "yesterday"
        return f"{days} days ago"
    except Exception:
        return None


_SUBTYPE_PROMPTS = {
    "impulsive_critical":     "On critical moments today, force yourself to spend 10 seconds before you move.",
    "time_pressure_blunder":  "When your clock drops under a minute, simplify — trade pieces, play safe.",
    "chronic_timeout":        "Watch the clock — losing on time is losing the game.",
    "ignored_king_attack":    "When there are opposing pieces near your king, defense before attack.",
    "weakened_shelter":       "Pushing pawns near your king today? Ask what lines you're opening.",
    "king_in_center":         "Castle by move 12 unless the position screams otherwise.",
    "simple_hang":            "Before every move: can this piece be taken?",
    "tactical_seq_loss":      "In any forcing sequence today, walk it to the last move before playing move one.",
    "quiet_blunder":          "The quiet-looking positions bite you — slow down when nothing looks forced.",
    "threat_ignored":         "Ask 'what does the opponent threaten?' before every move today.",
    "missed_fork":            "Scan for knight geometry on every knight move.",
    "missed_pin":             "Look for opponent's king or queen behind another piece on a straight line.",
    "missed_skewer":          "A big-piece target with a smaller piece behind — that's the pattern.",
    "ignored_forcing_threat": "When they capture or check, address it first — before your plan.",
    "queen_out_early":        "Develop knights and bishops before the queen.",
    "piece_parked_on_start":  "Every piece needs a job — check yours by move 10.",
    "passive_king_in_endgame":"In queenless endgames, march the king to the center.",
    "isolated_pawn_created":  "Before every pawn move, ask whether it isolates one of yours.",
    "backward_pawn_created":  "Backward pawns are long-term liabilities — watch pawn structure.",
}


def _subtype_prompt(subtype: str) -> Optional[str]:
    return _SUBTYPE_PROMPTS.get(subtype)
