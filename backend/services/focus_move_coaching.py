"""
Focus Move Coaching — topic-aware coach message emitter for Play with Coach.

Runs alongside the impulse_warning (which is a universal fast+mistake rule).
This service asks: "does this specific mistake match the user's active
focus?" — and if so, insert a coach message that names the topic and
uses the same closing/prescription copy that the FocusCard renders.

Design principles:
1. Fires ONLY when the mistake actually maps to the user's focus. If focus
   is king_safety and the user hangs a piece far from their king → silent.
2. Reuses the SAME phrasings and closings as primary_weakness_picker
   (single source of truth). No new coaching copy invented here.
3. Reuses the SAME is_focus_moment classifier as mission_scoreboard.
   No duplicate live-position detection.
4. Recall count added when >= 3 events today, same pattern as impulse_warning.

Not for time_management — impulse_warning already covers that topic;
running both would double-post.
"""
from typing import Any, Dict, Optional

from services.mission_scoreboard import is_focus_moment
from services.primary_weakness_picker import (
    _PS_SUBTYPE_PHRASING, _CLOSING_BY_SUBTYPE,
)


TOPIC_LABELS = {
    "piece_safety":       "piece-safety",
    "king_safety":        "king-safety",
    "missed_tactic":      "tactical",
    "tactical_oversight": "tactical",
    "calculation_depth":  "calculation",
    "piece_activity":     "piece-activity",
    "opening_knowledge":  "opening",
    "endgame_technique":  "endgame",
    "pawn_structure":     "structural",
}


def _article(word: str) -> str:
    """'a' vs 'an' for the topic label."""
    return "an" if word and word[0].lower() in "aeiou" else "a"


def _grade(cp_loss: float) -> str:
    if cp_loss >= 300:
        return "blunder"
    if cp_loss >= 150:
        return "big mistake"
    return "mistake"


def _ordinal(n: int) -> str:
    if n <= 0:
        return "0th"
    if 10 <= n % 100 <= 20:
        return f"{n}th"
    return f"{n}{ {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th') }"


def build_focus_coach_message(
    focus_topic: str,
    dominant_subtype: Optional[str],
    move_san: str,
    cp_loss: float,
    today_topic_count: int,
) -> Optional[str]:
    """Return the coach message body if the mistake maps to the user's
    focus topic. Returns None if the topic is time_management (owned by
    impulse_warning) or the topic isn't in our supported set.

    Args:
      focus_topic: e.g., 'king_safety' — from session mission_scoreboard.
      dominant_subtype: e.g., 'ignored_king_attack'. Optional.
      move_san: the just-played move in SAN.
      cp_loss: how much the move cost, cp.
      today_topic_count: how many events of THIS topic the user has
        already had TODAY across all games. Used for recall line.
    """
    if focus_topic == "time_management":
        return None   # handled by impulse_warning
    if focus_topic not in TOPIC_LABELS:
        return None

    topic_label = TOPIC_LABELS[focus_topic]
    grade = _grade(cp_loss)
    art = _article(topic_label)

    # Lead — name the topic + the grade
    lead = f"That {move_san} was {art} {topic_label} {grade} — {int(cp_loss)}cp lost."

    # Recall line — only when there's meaningful data
    recall = None
    if today_topic_count >= 3 and dominant_subtype:
        # "the 4th ignored_king_attack today"
        subtype_label = dominant_subtype.replace("_", " ")
        recall = f"That's your {_ordinal(today_topic_count + 1)} {subtype_label} today."

    # Prescription — reuse the same closing line as FocusCard
    closing = None
    if dominant_subtype and dominant_subtype in _CLOSING_BY_SUBTYPE:
        closing = _CLOSING_BY_SUBTYPE[dominant_subtype]

    parts = [lead]
    if recall:
        parts.append(recall)
    if closing:
        parts.append(closing)
    return " ".join(parts)


async def should_fire_focus_coach(
    focus_topic: str,
    fen_before: str,
    move_uci: str,
    user_color: str,
    is_critical: bool,
    time_spent_seconds: Optional[float],
    cp_loss: float,
) -> bool:
    """Gate: does the current mistake actually match the user's focus?

    Rules (in order):
      1. Never for time_management (owned by impulse_warning).
      2. cp_loss must be at mistake level (>= 100).
      3. The live position must classify as a focus-moment per
         mission_scoreboard.is_focus_moment.
    """
    if focus_topic == "time_management":
        return False
    if cp_loss < 100:
        return False
    return is_focus_moment(
        focus_topic, fen_before, move_uci, user_color,
        is_critical=is_critical, time_spent_seconds=time_spent_seconds,
    )
