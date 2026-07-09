"""
Session Reflection Service — Post-game goal achievement analysis.

Computes whether the player achieved their session goal and provides
evidence-based feedback. Used by post-game reflection card.
"""

import logging
from typing import Dict, Optional, List
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def compute_session_reflection(session: Dict) -> Optional[Dict]:
    """
    Analyze a completed Play with Coach session and compute goal achievement.

    Returns:
        {
            goal: str,               # The session goal (e.g., "manage time")
            achieved: bool,          # Did the player meet the goal?
            confidence: float,       # 0.0-1.0 confidence in verdict
            evidence: str,           # Explanation (e.g., "managed time in 7/9 critical moments")
            stat_label: str,         # For UI display (e.g., "7 of 9 critical moments")
            encouragement: str,      # Affirmation message
            next_focus: Optional[str] # Suggested next goal
        }
    """

    try:
        # Unpack session data
        goal_text = session.get("session_goal", {}).get("text", "")
        focus_topic = session.get("session_goal", {}).get("focus_area", "")
        mission_board = session.get("mission_scoreboard", {})
        move_history = session.get("move_history", [])
        result = session.get("result")

        if not goal_text or not focus_topic:
            return None

        # Compute achievement based on focus area
        achievement_data = _compute_achievement_by_topic(
            focus_topic=focus_topic,
            mission_board=mission_board,
            move_history=move_history,
            result=result
        )

        if not achievement_data:
            return None

        achieved = achievement_data.get("achieved", False)
        matched = achievement_data.get("matched", 0)
        total = achievement_data.get("total", 1)
        stat_key = achievement_data.get("stat_key", "")

        # Build reflection card
        return {
            "goal": goal_text,
            "focus_topic": focus_topic,
            "achieved": achieved,
            "confidence": achievement_data.get("confidence", 0.7),
            "evidence": _build_evidence_text(focus_topic, matched, total, achieved),
            "stat_label": f"{matched} of {total} {stat_key}",
            "encouragement": _build_encouragement(focus_topic, achieved, matched, total),
            "next_focus": _suggest_next_focus(focus_topic, achieved)
        }

    except Exception as e:
        logger.warning(f"Session reflection failed: {e}")
        return None


def _compute_achievement_by_topic(
    focus_topic: str,
    mission_board: Dict,
    move_history: List,
    result: Optional[Dict]
) -> Optional[Dict]:
    """
    Compute achievement metrics specific to the focus topic.

    time_management:
      - Matched moments: critical positions where player took ≥5s
      - Total: all critical moments in the game
      - Achieved: matched ≥ 60% of total

    piece_safety:
      - Matched moments: critical moments without hanging pieces
      - Total: all critical moments
      - Achieved: matched ≥ 70% of total

    king_safety:
      - Matched moments: critical moments without king threats
      - Total: all critical moments
      - Achieved: matched ≥ 60% of total

    missed_tactic:
      - Matched moments: found forcing moves when available
      - Total: positions with forcing moves
      - Achieved: matched ≥ 50% of total
    """

    if focus_topic == "time_management":
        matched = mission_board.get("matched_moments", 0)
        total = mission_board.get("total_moments", 0)
        threshold = 0.60

        if total == 0:
            return None

        return {
            "achieved": (matched / total) >= threshold,
            "matched": matched,
            "total": total,
            "stat_key": "critical moments",
            "confidence": 0.92
        }

    elif focus_topic == "piece_safety":
        # TODO: Extract from move history/analysis
        # For now, use mission_board if available
        matched = mission_board.get("safe_moves", 0)
        total = mission_board.get("critical_moments", 1)
        threshold = 0.70

        if total == 0:
            return None

        return {
            "achieved": (matched / total) >= threshold,
            "matched": matched,
            "total": total,
            "stat_key": "moves without hanging pieces",
            "confidence": 0.75
        }

    elif focus_topic == "king_safety":
        matched = mission_board.get("safe_king_moves", 0)
        total = mission_board.get("critical_moments", 1)
        threshold = 0.60

        if total == 0:
            return None

        return {
            "achieved": (matched / total) >= threshold,
            "matched": matched,
            "total": total,
            "stat_key": "safe king moves",
            "confidence": 0.70
        }

    elif focus_topic == "missed_tactic":
        matched = mission_board.get("found_tactics", 0)
        total = mission_board.get("tactical_moments", 1)
        threshold = 0.50

        if total == 0:
            return None

        return {
            "achieved": (matched / total) >= threshold,
            "matched": matched,
            "total": total,
            "stat_key": "tactical opportunities found",
            "confidence": 0.70
        }

    # Generic fallback
    return None


def _build_evidence_text(focus_topic: str, matched: int, total: int, achieved: bool) -> str:
    """Generate evidence text for the reflection."""

    pct = int(100 * matched / total) if total > 0 else 0

    messages = {
        "time_management": f"You managed time carefully in {matched}/{total} critical moments ({pct}%).",
        "piece_safety": f"You kept your pieces safe in {matched}/{total} critical moments ({pct}%).",
        "king_safety": f"You protected your king in {matched}/{total} critical moments ({pct}%).",
        "missed_tactic": f"You spotted tactics in {matched}/{total} available positions ({pct}%).",
    }

    base = messages.get(focus_topic, f"You hit the mark on {matched}/{total} critical moments.")

    if achieved:
        return base + " Great work!"
    else:
        return base + f" Keep practicing — {100 - pct}% of the time, focus back on this."


def _build_encouragement(focus_topic: str, achieved: bool, matched: int, total: int) -> str:
    """Generate encouragement message."""

    if not achieved:
        encouragements = {
            "time_management": "Next time, take an extra breath on critical positions. Your instinct is good — give it time to shine.",
            "piece_safety": "Quick scan before each move: are your pieces defended? Next game, you'll catch this earlier.",
            "king_safety": "Your king is your most important piece. On critical moments, ask: is my king safe? Then move.",
            "missed_tactic": "Slow down: checks, captures, threats. Look for forcing moves every turn.",
        }
        return encouragements.get(focus_topic, "Keep practicing this focus area.")
    else:
        encouragements = {
            "time_management": "You're building the habit! Taking time on critical moments is exactly the pattern that wins games.",
            "piece_safety": "Your pieces are well-protected — that's the foundation of good chess.",
            "king_safety": "Your king is fortress. With this skill, you'll convert those winning positions.",
            "missed_tactic": "You're seeing the board sharper! Keep this up.",
        }
        return encouragements.get(focus_topic, "You're improving on this focus area.")


def _suggest_next_focus(current_topic: str, achieved: bool) -> Optional[str]:
    """Suggest what to focus on next."""

    # If goal achieved, suggest rotation to next area
    if achieved:
        rotation = {
            "time_management": "piece_safety",
            "piece_safety": "king_safety",
            "king_safety": "missed_tactic",
            "missed_tactic": "time_management",
        }
        return rotation.get(current_topic)

    # If not achieved, suggest staying on current focus
    return None
