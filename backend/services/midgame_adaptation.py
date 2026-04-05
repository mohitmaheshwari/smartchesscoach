"""
Mid-Game Adaptation Service
============================

Detects HOW the user is playing in THIS game and adapts coaching tone/depth.

Signals tracked:
- Tempo: Are they playing fast (< 5s/move) or slow (> 30s/move)?
- Momentum: Streak of good moves vs streak of mistakes?
- Consistency: Were they focused early but sloppy late?
- Emotional state: Did they just blunder after 10 good moves? (tilt risk)

Returns an adaptation context that the coaching message generator uses
to adjust tone, depth, and type of feedback.

No LLM. No database writes. Pure computation from move history.
"""

from typing import Dict, List, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


def compute_game_adaptation(
    move_history: List[Dict],
    user_color: str,
    evaluations: List[Dict] = None,
) -> Dict:
    """
    Analyze the current game's tempo, momentum, and emotional state.

    Args:
        move_history: List of {move, by, timestamp, fen_before, ...}
        user_color: "white" or "black"
        evaluations: List of per-move feedback with quality/eval data (if available)

    Returns:
        {
            "tempo": "rushing" | "normal" | "deliberate" | "unknown",
            "avg_time_per_move": float (seconds),
            "momentum": "hot_streak" | "cold_streak" | "mixed" | "neutral",
            "good_moves_streak": int,
            "bad_moves_streak": int,
            "tilt_risk": bool,
            "focus_shift": "steady" | "fading" | "improving" | "unknown",
            "coaching_depth": "brief" | "standard" | "detailed",
            "tone_modifier": "encouraging" | "neutral" | "firm" | "urgent",
            "nudge": str or None,  # One-line contextual nudge
        }
    """
    result = {
        "tempo": "unknown",
        "avg_time_per_move": 0,
        "momentum": "neutral",
        "good_moves_streak": 0,
        "bad_moves_streak": 0,
        "tilt_risk": False,
        "focus_shift": "unknown",
        "coaching_depth": "standard",
        "tone_modifier": "neutral",
        "nudge": None,
    }

    if not move_history or len(move_history) < 4:
        return result

    # ── COMPUTE USER MOVE TIMES ──
    user_moves = [m for m in move_history if m.get("by") == "player"]
    move_times = []

    for i in range(1, len(user_moves)):
        t1 = user_moves[i - 1].get("timestamp")
        t2 = user_moves[i].get("timestamp")
        if t1 and t2:
            try:
                if isinstance(t1, str):
                    t1 = datetime.fromisoformat(t1.replace("Z", "+00:00"))
                if isinstance(t2, str):
                    t2 = datetime.fromisoformat(t2.replace("Z", "+00:00"))
                diff = (t2 - t1).total_seconds()
                # Filter out unreasonable times (coach thinking time included)
                # Approximate user think time: total interval minus ~3-5s for coach
                user_think = max(diff - 4, 1)
                move_times.append(user_think)
            except Exception:
                pass

    if move_times:
        avg_time = sum(move_times) / len(move_times)
        result["avg_time_per_move"] = round(avg_time, 1)

        # ── TEMPO CLASSIFICATION (hard thresholds) ──
        if avg_time < 5:
            result["tempo"] = "rushing"
        elif avg_time < 15:
            result["tempo"] = "normal"
        elif avg_time < 40:
            result["tempo"] = "deliberate"
        else:
            result["tempo"] = "deliberate"

        # Check if recent moves are faster than early moves (fading focus)
        if len(move_times) >= 6:
            early_avg = sum(move_times[:3]) / 3
            recent_avg = sum(move_times[-3:]) / 3

            if recent_avg < early_avg * 0.5:
                result["focus_shift"] = "fading"  # Getting faster = less careful
            elif recent_avg > early_avg * 1.5:
                result["focus_shift"] = "improving"  # Slowing down = more careful
            else:
                result["focus_shift"] = "steady"

    # ── MOMENTUM (from evaluations if available) ──
    if evaluations:
        recent_evals = evaluations[-5:] if len(evaluations) >= 5 else evaluations
        recent_qualities = [e.get("user_move_quality", e.get("quality", "")) for e in recent_evals]

        good = sum(1 for q in recent_qualities if q in ("best", "excellent", "good", "brilliant"))
        bad = sum(1 for q in recent_qualities if q in ("mistake", "blunder"))

        # Count current streak
        good_streak = 0
        bad_streak = 0
        for q in reversed(recent_qualities):
            if q in ("best", "excellent", "good", "brilliant"):
                if bad_streak == 0:
                    good_streak += 1
                else:
                    break
            elif q in ("mistake", "blunder"):
                if good_streak == 0:
                    bad_streak += 1
                else:
                    break
            else:
                break

        result["good_moves_streak"] = good_streak
        result["bad_moves_streak"] = bad_streak

        if good_streak >= 3:
            result["momentum"] = "hot_streak"
        elif bad_streak >= 2:
            result["momentum"] = "cold_streak"
        elif good >= 3 and bad <= 1:
            result["momentum"] = "hot_streak"
        elif bad >= 2 and good <= 1:
            result["momentum"] = "cold_streak"
        else:
            result["momentum"] = "mixed"

        # ── TILT DETECTION ──
        # Tilt = was playing well, then suddenly blundered
        if len(recent_qualities) >= 4:
            early_good = sum(1 for q in recent_qualities[:3] if q in ("best", "excellent", "good"))
            late_bad = sum(1 for q in recent_qualities[-2:] if q in ("mistake", "blunder"))
            if early_good >= 2 and late_bad >= 1:
                result["tilt_risk"] = True

    # ── DERIVE COACHING ADAPTATIONS ──

    # Coaching depth: brief for rushers, detailed for deliberate players
    if result["tempo"] == "rushing":
        result["coaching_depth"] = "brief"
    elif result["tempo"] == "deliberate":
        result["coaching_depth"] = "detailed"
    else:
        result["coaching_depth"] = "standard"

    # Tone modifier
    if result["tilt_risk"]:
        result["tone_modifier"] = "urgent"
    elif result["momentum"] == "cold_streak":
        result["tone_modifier"] = "firm"
    elif result["momentum"] == "hot_streak":
        result["tone_modifier"] = "encouraging"
    else:
        result["tone_modifier"] = "neutral"

    # ── NUDGE (one-line contextual message) ──
    if result["tempo"] == "rushing" and result["bad_moves_streak"] >= 1:
        result["nudge"] = "You're moving fast. Slow down — think before you click."
    elif result["tilt_risk"]:
        result["nudge"] = "You were playing well — don't let one mistake snowball. Take a breath."
    elif result["focus_shift"] == "fading":
        result["nudge"] = "You're speeding up. Stay focused — the game isn't over yet."
    elif result["good_moves_streak"] >= 4:
        result["nudge"] = "You're in the zone. Stay sharp."
    elif result["momentum"] == "cold_streak" and result["bad_moves_streak"] >= 2:
        result["nudge"] = "Two mistakes in a row. Pause. Check what your opponent is doing."

    return result
