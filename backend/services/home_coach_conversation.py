"""
Home Coach Conversation Service
================================

Builds the single continuous coach narrative for the Home page — replaces
the old ten-section dashboard stack (recommendations grid with elo/confidence
numbers, a raw-percentage "you're improving" line, a numeric domain-score
grid). See docs/home_page_coach_conversation_scope.md for the full spec,
including why every threshold below is set the way it is.

Reuses, never duplicates:
  - focus_bridge.get_active_focus_bundle() — the canonical "what are we
    working on" read (topic_key, days_into_focus, dominant_subtype).
  - pattern_decay_service's stored db.user_pattern_decay scores — ACTIVE /
    DECLINING / FADING states, used for the "coach revises a theory" beat.

Adds one small piece of new bookkeeping: db.home_conversation_state, one
doc per user, remembering which topic_key was last shown as the headline
so a real state change (not a timer, not chance) can trigger the revision
beat.

The belief bank (_IDENTITY_FRAME / _THEORY_OF_WHY / _ONE_ACTION) is
hand-authored and reviewed — see the scope doc's "Identity over skill" and
"theory-of-why bank" sections. Extend this dict when a category earns real
signal; don't have anything generate new entries live.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional

# ── Relationship-stage ladder — keyed to games_analyzed, not calendar time.
# Calendar tenure was checked against production data (July 30, 2026) and
# found unreliable for most of the current user base: ~40 of 62 active
# accounts share a created_at clustered at ~100-102 days regardless of real
# activity (1 to 1,281 games analyzed), consistent with a bulk backfill
# rather than organic signup timing. games_analyzed is the honest signal —
# it also matches the product's own framing ("after watching hundreds of
# games") better than a date would.
_STAGE_BOUNDARIES = [
    (20, "week_one"),
    (150, "month_three"),
    (400, "month_six"),
]
_STAGE_FALLBACK = "one_year"

_STAGE_OPENER = {
    "week_one": "I'm still learning how you play.",
    "month_three": "I'm starting to see your habits.",
    "month_six": "I know what usually causes your losses.",
    "one_year": "I already know what will be hard for you, before it happens.",
}

# One identity frame + one hedged theory-of-why + one plain action per
# confirmed-signal cognitive-gap category (the six categories with real
# labeled instances in production data as of July 30, 2026).
_IDENTITY_FRAME: Dict[str, str] = {
    "piece_safety": "We're making you a player who keeps pieces safe without thinking about it.",
    "king_safety": "We're making you a player who stays calm when the king is under attack.",
    "tactical_oversight": "We're teaching you to slow down before you move.",
    "missed_tactic": "We're training you to check your opponent's plan, not just your own.",
    "opening_knowledge": "We're building your confidence in positions you don't know yet.",
    "endgame_technique": "We're teaching you to stay careful even when you are already winning.",
}

# Each entry follows one shape on purpose: a surface guess, a correction,
# the real (hedged) theory, then one identity-affirming reassurance clause.
# This is a deliberate copy pattern (Mohit, 2026-07-31 rewrite pass) — it
# should read like the coach thinking out loud, not stating a fact.
_THEORY_OF_WHY: Dict[str, str] = {
    "piece_safety": (
        "At first, I thought you moved too fast. I don't think that "
        "anymore. I think when you find a plan you like, you stop checking "
        "the rest of the board. You believe it still looks the same. But it "
        "changes every move. You are not careless. You just believe in "
        "your plan too much. That is why pieces disappear."
    ),
    "king_safety": (
        "At first, I thought you did not know castling was important. I "
        "don't think that anymore. I think making a threat feels more fun "
        "than making your king safe. Castling can feel slow. But it is "
        "often your best move. This is not a mistake in your skill. It is "
        "just where your excitement goes first."
    ),
    "tactical_oversight": (
        "At first, I thought you could not calculate deep enough. I don't "
        "think that anymore. I think once a move looks good to you, your "
        "mind relaxes. Finding a good move feels like the end of the work. "
        "But the real danger is often one move later. This is a habit, not "
        "a limit. Habits can change."
    ),
    "missed_tactic": (
        "At first, I thought you could not see these ideas. I don't think "
        "that anymore. I think you spend all your attention on your own "
        "plan. You forget to ask what your opponent wants. You are not "
        "blind to it. You just are not looking for it yet."
    ),
    "opening_knowledge": (
        "At first, I thought you did not like studying openings. I don't "
        "think that anymore. I think when a position feels new, you trust "
        "your own idea more than what you already learned. That is not a "
        "knowledge problem. It is confidence looking in the wrong place."
    ),
    "endgame_technique": (
        "At first, I thought you got careless at the end of games. I don't "
        "think that anymore. I think winning makes you relax, because it "
        "feels like the hard part is over. That relief is normal. But "
        "staying careful to the very end is the real hard part."
    ),
}

# Today's one mission per category — a single memorable question, not a
# checklist. Mohit, 2026-07-31: "that's memorable — I can repeat it in my
# head." Same shape for every category on purpose: "ask one question."
_ONE_ACTION: Dict[str, str] = {
    "piece_safety": 'Today, don\'t try to play better chess. Just ask one question before every move: "What changed after their last move?"',
    "king_safety": 'Today, ask one question before every move: "Is my king really safe right now?"',
    "tactical_oversight": 'Today, ask one question before every move: "Is there something even better, one move further?"',
    "missed_tactic": 'Today, ask one question before every move: "What is my opponent trying to do?"',
    "opening_knowledge": 'Today, ask one question before every move: "Am I following a plan I know, or just guessing?"',
    "endgame_technique": 'Today, ask one question before every move: "Have I checked this all the way to the end?"',
}

_FALLBACK_ACTION = "Play one game today. Let's see what it shows us."

# Clean display labels, deliberately NOT read from focus_bridge's own
# topic_label — that field is written for a different surface (the old
# FocusCard) and carries baked-in text like "Piece safety (50% critical)".
# Home never shows a percentage, so it needs its own controlled label.
_CLEAN_LABEL: Dict[str, str] = {
    "piece_safety": "piece safety",
    "king_safety": "king safety",
    "tactical_oversight": "calculating a little further",
    "missed_tactic": "spotting your opponent's ideas",
    "opening_knowledge": "your openings",
    "endgame_technique": "endgame patience",
}


def _relationship_stage(games_analyzed: int) -> str:
    for boundary, stage in _STAGE_BOUNDARIES:
        if games_analyzed < boundary:
            return stage
    return _STAGE_FALLBACK


async def _games_analyzed_count(db, user_id: str) -> int:
    return await db.game_analyses.count_documents({"user_id": user_id})


async def _get_topic_decay_state(db, user_id: str, topic_key: str) -> Optional[Dict[str, Any]]:
    doc = await db.user_pattern_decay.find_one({"user_id": user_id}, {"_id": 0, "scores": 1})
    if not doc:
        return None
    return (doc.get("scores") or {}).get(topic_key)


async def _check_theory_revision(db, user_id: str, current_topic: str) -> Optional[Dict[str, str]]:
    """A real, data-backed 'I was wrong, updating my theory' moment: the
    topic shown as headline last time has since moved to declining/fading,
    AND a different topic is now the headline. Never fires on a timer or
    at random — see scope doc §6, open question 2."""
    state_doc = await db.home_conversation_state.find_one({"user_id": user_id}, {"_id": 0})
    if not state_doc:
        return None
    prev_topic = state_doc.get("last_headline_topic_key")
    if not prev_topic or prev_topic == current_topic:
        return None
    prev_state = await _get_topic_decay_state(db, user_id, prev_topic)
    if not prev_state or prev_state.get("state") not in ("declining", "fading"):
        return None
    if prev_topic not in _IDENTITY_FRAME or current_topic not in _IDENTITY_FRAME:
        return None
    return {"previous_topic": prev_topic, "new_topic": current_topic}


async def _remember_headline(db, user_id: str, topic_key: str) -> None:
    await db.home_conversation_state.update_one(
        {"user_id": user_id},
        {"$set": {
            "last_headline_topic_key": topic_key,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }},
        upsert=True,
    )


def _ordinal(n: int) -> str:
    if 10 <= n % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


async def _update_topic_cycle(db, user_id: str, topic_key: str, started_at: Optional[str]) -> int:
    """Real, data-backed count of how many separate times this topic has
    been the headline focus — a genuine 'this is the Nth time we've worked
    on this' claim (Mohit, 2026-07-31 §9), not a decorative guess.

    A 'cycle' is a distinct focus period: started_at changing for the same
    topic_key means the user drifted away and it came back, not that the
    same still-open focus period is being re-read on every page load."""
    doc = await db.home_conversation_state.find_one({"user_id": user_id}, {"_id": 0, "topic_cycles": 1})
    cycles = (doc or {}).get("topic_cycles") or {}
    entry = cycles.get(topic_key)

    if not entry:
        cycles[topic_key] = {"last_started_at": started_at, "cycle_count": 1}
    elif started_at and entry.get("last_started_at") != started_at:
        cycles[topic_key] = {"last_started_at": started_at, "cycle_count": entry.get("cycle_count", 1) + 1}
    # else: same open cycle, no change

    await db.home_conversation_state.update_one(
        {"user_id": user_id},
        {"$set": {"topic_cycles": cycles}},
        upsert=True,
    )
    return cycles[topic_key]["cycle_count"]


async def _days_since_last_game(db, user_id: str) -> Optional[int]:
    """Same date_played normalization pattern as pattern_decay_service's
    build_decay_games — reused rather than re-invented. Used only to gate
    the 'I've been thinking about your games' signature line on a real
    absence, not a random draw (see scope discussion, Mohit 2026-07-31)."""
    games = await db.games.find(
        {"user_id": user_id, "is_analyzed": True},
        {"_id": 0, "date_played": 1},
    ).to_list(None)

    def norm(d):
        s = str(d or "").replace(".", "-")[:10]
        return s if len(s) == 10 else None

    dates = sorted((norm(g.get("date_played")) for g in games if norm(g.get("date_played"))), reverse=True)
    if not dates:
        return None
    try:
        last = datetime.fromisoformat(dates[0]).replace(tzinfo=timezone.utc)
    except Exception:
        return None
    return max(0, (datetime.now(timezone.utc) - last).days)


def _compose_narrative(
    stage: str,
    topic_key: str,
    topic_label: str,
    days_into_focus: int,
    theory: Optional[str],
    revision: Optional[Dict[str, str]],
    cycle_count: int,
) -> Dict[str, str]:
    label = (topic_label or topic_key.replace("_", " ")).lower()

    if days_into_focus <= 0:
        continuity = f"We just started working on {label} together."
    elif days_into_focus == 1:
        continuity = f"We've worked on {label} for one day now."
    else:
        continuity = f"We've worked on {label} for {days_into_focus} days now."

    # A REAL recurrence claim — cycle_count comes from _update_topic_cycle,
    # which only increments when the topic's started_at genuinely changed
    # (they drifted away and it came back). Never shown on a first cycle.
    if cycle_count >= 2 and not revision:
        continuity += f" This is the {_ordinal(cycle_count)} time we've worked on this together."

    if revision and theory:
        prev_label = revision["previous_topic"].replace("_", " ")
        belief = (
            f"For a while, {prev_label} was the biggest thing holding you "
            f"back. You've been getting better there, so today I'm moving "
            f"our attention. {theory}"
        )
    else:
        belief = theory or ""

    return {
        "stage_opener": _STAGE_OPENER[stage],
        "continuity": continuity,
        "belief": belief,
    }


async def build_home_conversation(db, user_id: str) -> Optional[Dict[str, Any]]:
    """Assemble the single Home page coach conversation.

    Returns None when there isn't enough signal yet (no analyzed games) —
    the caller falls back to the existing new-user Activation flow,
    unchanged (see ActivationHub.jsx / the !hasGames branch of Home).
    """
    from services.focus_bridge import get_active_focus_bundle

    games_analyzed = await _games_analyzed_count(db, user_id)
    if games_analyzed == 0:
        return None

    focus = await get_active_focus_bundle(db, user_id)
    if not focus or not focus.get("topic_key"):
        return None

    topic_key = focus["topic_key"]
    topic_label = _CLEAN_LABEL.get(topic_key, topic_key.replace("_", " "))
    stage = _relationship_stage(games_analyzed)
    days_into_focus = focus.get("days_into_focus") or 0

    revision = await _check_theory_revision(db, user_id, topic_key)
    await _remember_headline(db, user_id, topic_key)
    cycle_count = await _update_topic_cycle(db, user_id, topic_key, focus.get("started_at"))

    identity = _IDENTITY_FRAME.get(topic_key)
    theory = _THEORY_OF_WHY.get(topic_key)
    action = _ONE_ACTION.get(topic_key, _FALLBACK_ACTION)

    narrative = _compose_narrative(
        stage=stage,
        topic_key=topic_key,
        topic_label=topic_label,
        days_into_focus=days_into_focus,
        theory=theory,
        revision=revision,
        cycle_count=cycle_count,
    )

    # A real-absence-gated signature line, not a random draw (Mohit,
    # 2026-07-31: "not every day — but often" — tied to a genuine gap
    # since their last game rather than an arbitrary coin flip).
    days_away = await _days_since_last_game(db, user_id)
    thinking_signature = "I've been thinking about your games." if (days_away or 0) >= 1 else None

    return {
        "stage": stage,
        "topic_key": topic_key,
        "topic_label": topic_label,
        "days_into_focus": days_into_focus,
        "identity_frame": identity,
        "is_theory_revision": bool(revision),
        "one_action": action,
        "narrative": narrative,
        "encouragement": "I'll tell you how it looks tomorrow.",
        "closing_line": "Now go play. I want to see if my theory is right.",
        "thinking_signature": thinking_signature,
    }
