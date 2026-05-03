"""
CCT voice — turn detected CCT signals into player-facing strings.

Consumes the CCT aggregate + held-initiative segments produced by
cct_detector.py and renders coach-voice lines per the canonical
voice rules (memory/project_coach_voice.md).

Public surfaces:

  game_review_cct_line(cct_aggregate, held_initiative_summary)
    → Optional[str]
    A single line for the Game Review / Game Decryption narrative.
    Returns None when there's no CCT signal worth narrating (low
    decisions count, no held-initiative segment).

  coach_play_held_initiative_message(segment, voice="default")
    → str
    A single coach-play moment line. Used inline when the analyzer
    flags a missed best-forcing move but the segment shows the user
    rebounded with their own forcing move.

The strings use templates from coaching_library.py — never invent
voice. If a template is missing or rendering fails, return None and
let the caller fall back to silence.
"""

from __future__ import annotations

from typing import Dict, List, Optional

try:
    from services.coaching_library import get_user_feedback_text
except Exception:
    get_user_feedback_text = None  # graceful degrade if import path differs


# Minimum decisions count before we narrate the CCT score in a game
# review. With <3 forcing decisions in a game there's not enough data
# to say anything meaningful about discipline.
MIN_DECISIONS_TO_NARRATE = 3

# Min streak length before we celebrate it. <3 isn't a streak, it's
# just a couple of moves.
MIN_STREAK_TO_CELEBRATE = 3


def _render_template(scenario_key: str, **kwargs) -> Optional[str]:
    """Render a coaching_library template, returning None on any
    failure (missing template, missing kwargs, library import broken).
    """
    if get_user_feedback_text is None:
        return None
    try:
        result = get_user_feedback_text(scenario_key, **kwargs)
        if not result:
            return None
        narrative = result.get("narrative")
        return narrative.strip() if narrative else None
    except Exception:
        return None


def game_review_cct_line(
    cct_aggregate: Optional[Dict],
    held_initiative_summary: Optional[Dict] = None,
) -> Optional[str]:
    """Single coach-voice line for the game review panel about CCT
    discipline.

    Priority order (we return the FIRST that fires, not all):
      1. Held-initiative-after-miss segment exists → narrate it
         (the user's specific reported pattern: "missed killer but
         kept hunting forcing moves")
      2. cct_max_streak is high (>= MIN_STREAK_TO_CELEBRATE) →
         celebrate the streak
      3. Otherwise → no CCT line (return None; let the rest of the
         game review carry the narrative)

    Returns None when there's not enough signal to say anything in
    voice. Silence is always preferable to filler.
    """
    # Priority 1: held-initiative segment
    if held_initiative_summary:
        best_segment = held_initiative_summary.get("best_segment")
        if best_segment:
            missed = best_segment.get("missed_best_san") or "the engine's move"
            played = best_segment.get("miss_move_san") or "your move"
            window_moves = best_segment.get("window_moves_san") or []
            # Pick the first forcing move from the window as the rebound
            # (we don't have per-move tags here, so just use the first
            # non-empty SAN in the window as a stand-in)
            rebound = next(
                (m for m in window_moves if m), None
            ) or "the next forcing move"

            line = _render_template(
                "held_initiative_after_miss",
                missed_move=missed,
                played_move=played,
                rebound_move=rebound,
            )
            if line:
                return line

    # Priority 2: streak celebration
    if cct_aggregate:
        streak = cct_aggregate.get("cct_max_streak", 0)
        if streak >= MIN_STREAK_TO_CELEBRATE:
            line = _render_template("cct_discipline_streak", streak=streak)
            if line:
                return line

    return None


def coach_play_held_initiative_message(segment: Dict) -> Optional[str]:
    """Single voice line for coach play when a held-initiative
    segment fires.

    Same template family as game review, but called per-segment
    rather than per-game. Used to suppress a "you missed mate" cold
    blunder message when the system also detected the recovery.
    """
    if not segment:
        return None

    missed = segment.get("missed_best_san") or "the engine's move"
    played = segment.get("miss_move_san") or "your move"
    window_moves = segment.get("window_moves_san") or []
    rebound = next((m for m in window_moves if m), None) or "the next forcing move"

    return _render_template(
        "held_initiative_after_miss",
        missed_move=missed,
        played_move=played,
        rebound_move=rebound,
    )


def has_cct_signal(
    cct_aggregate: Optional[Dict],
    held_initiative_summary: Optional[Dict] = None,
) -> bool:
    """Quick check for whether there's anything worth narrating about
    CCT in this game. Lets callers skip the rendering call when the
    answer is obvious."""
    if held_initiative_summary and held_initiative_summary.get("count", 0) > 0:
        return True
    if cct_aggregate:
        if cct_aggregate.get("cct_max_streak", 0) >= MIN_STREAK_TO_CELEBRATE:
            return True
        if cct_aggregate.get("cct_decisions", 0) >= MIN_DECISIONS_TO_NARRATE:
            # Even without a streak or held-initiative, we may want to
            # surface low-discipline as a teaching moment — but not in
            # this signal check; that's the job of higher-level coach
            # logic. Return True only when there's a positive signal.
            score = cct_aggregate.get("cct_score") or 0
            if score >= 0.7:
                return True
    return False
