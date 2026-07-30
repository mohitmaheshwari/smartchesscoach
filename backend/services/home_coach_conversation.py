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

_THEORY_OF_WHY: Dict[str, str] = {
    "piece_safety": (
        "I don't think you are careless. I think when you find a plan, you "
        "stop looking at the whole board again. You trust it looks the same "
        "as before. But it changes every move."
    ),
    "king_safety": (
        "I think you like making threats more than staying safe. Castling can "
        "feel like a slow move. But it is often the most important move you "
        "can make."
    ),
    "tactical_oversight": (
        "I think you stop thinking as soon as you find a move that looks "
        "good. Not because you cannot think further. Finding a good move "
        "feels like the job is already done."
    ),
    "missed_tactic": (
        "I don't think you cannot see the tactic. I think you look for your "
        "own plan first. You check your opponent's plan second — or not at "
        "all."
    ),
    "opening_knowledge": (
        "I don't think you dislike opening theory. I think when a position "
        "looks new to you, you trust your own idea more than what you "
        "learned before."
    ),
    "endgame_technique": (
        "I think when you are clearly winning, you relax. It feels like the "
        "hard part is over. But that is exactly when careful play matters "
        "most."
    ),
}

# Today's one mission per category — plain English, one instruction, the
# thing the whole page ends on.
_ONE_ACTION: Dict[str, str] = {
    "piece_safety": 'Before you move, look at the whole board one more time. Ask: "is anything of mine free to take?"',
    "king_safety": "If your king is still in the middle after move 10, castle first. Do that before anything else.",
    "tactical_oversight": "When you find a move you like, stop. Look one move further before you play it.",
    "missed_tactic": 'Before you move, ask "what does their last move want?" Ask this before "is my move good?"',
    "opening_knowledge": "Play the same opening as last time. Trust what you learned, even if the position feels new.",
    "endgame_technique": "When you are ahead, slow down. Check every capture all the way to the end before you play it.",
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


def _compose_narrative(
    stage: str,
    topic_key: str,
    topic_label: str,
    days_into_focus: int,
    theory: Optional[str],
    revision: Optional[Dict[str, str]],
) -> Dict[str, str]:
    label = (topic_label or topic_key.replace("_", " ")).lower()

    if days_into_focus <= 0:
        continuity = f"We just started working on {label} together."
    elif days_into_focus == 1:
        continuity = f"We've worked on {label} for one day now."
    else:
        continuity = f"We've worked on {label} for {days_into_focus} days now."

    if revision and theory:
        prev_label = revision["previous_topic"].replace("_", " ")
        belief = (
            f"I thought {prev_label} was your biggest problem. After "
            f"watching your last games again, I don't think that's it "
            f"anymore. {theory}"
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
    )

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
    }
