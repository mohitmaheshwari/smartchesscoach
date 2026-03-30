"""
Smart Coach Feedback
=====================

Instead of "bad move", the coach:
1. Figures out WHAT you were trying to do (from the board, not asking)
2. Acknowledges your idea  
3. Only then explains why something better exists

Rating-based filtering:
- Under 1400: Only react to blunders (200+) and big mistakes (150+)
- 1400-1700: Blunders + mistakes + known weakness patterns
- 1800+: Everything including inaccuracies
"""

import logging
from typing import Dict, Optional
from services.move_intent_analyzer import analyze_move_intent, MoveIntent

logger = logging.getLogger(__name__)


def generate_smart_feedback(
    fen: str,
    move_san: str,
    best_move_san: str,
    cp_loss: int,
    user_rating: int = 1200,
    eval_before: float = 0,
    eval_after: float = 0,
    is_best: bool = False,
    is_candidate: bool = False,
) -> Optional[Dict]:
    """
    Generate intent-aware coaching feedback for a move.
    
    Returns None if the move doesn't warrant feedback (e.g., inaccuracy for a 1200 player).
    """

    # ─── Step 1: Should we even comment on this move? ───
    threshold = _get_feedback_threshold(user_rating)

    if cp_loss < threshold:
        # Move is fine for this player's level — no feedback needed
        if is_best:
            return {"type": "good", "message": "Good move.", "show_intent": False}
        if is_candidate:
            return {"type": "good", "message": "Solid choice.", "show_intent": False}
        return None  # Silent — don't comment on minor inaccuracies for this rating

    # ─── Step 2: Analyze what they were TRYING to do ───
    intent = analyze_move_intent(fen, move_san, best_move_san, cp_loss)

    # ─── Step 3: Build feedback based on severity + intent ───
    if cp_loss >= 300:
        severity = "blunder"
    elif cp_loss >= 150:
        severity = "mistake"
    else:
        severity = "inaccuracy"

    # Acknowledge their idea first, then explain
    if intent.is_reasonable:
        # Their idea was fine, execution was off
        feedback = _reasonable_intent_feedback(intent, best_move_san, severity)
    else:
        # Their idea didn't make sense for the position
        feedback = _unclear_intent_feedback(intent, best_move_san, severity)

    return {
        "type": severity,
        "intent": {
            "type": intent.intent,
            "target": intent.target,
            "description": intent.description,
        },
        "message": feedback["message"],
        "coach_response": feedback["response"],
        "better_move": best_move_san,
        "show_intent": True,
    }


def _get_feedback_threshold(rating: int) -> int:
    """What cp_loss threshold triggers feedback for this rating?"""
    if rating < 1000:
        return 250  # Only blunders
    elif rating < 1400:
        return 150  # Blunders + big mistakes
    elif rating < 1700:
        return 100  # Mistakes too
    else:
        return 50   # Everything


def _reasonable_intent_feedback(intent: MoveIntent, best_move: str, severity: str) -> Dict:
    """Their idea was reasonable, but execution was off."""

    if severity == "blunder":
        return {
            "message": intent.description,
            "response": f"{intent.feedback} But this move has a big problem. {best_move} was much safer and still keeps your idea alive.",
        }
    elif severity == "mistake":
        return {
            "message": intent.description,
            "response": f"{intent.feedback} The idea is right, but the timing isn't. {best_move} does something similar but stronger.",
        }
    else:
        return {
            "message": intent.description,
            "response": f"{intent.feedback} Not bad, but {best_move} was a bit more accurate here.",
        }


def _unclear_intent_feedback(intent: MoveIntent, best_move: str, severity: str) -> Dict:
    """Their idea didn't really make sense."""

    if severity == "blunder":
        return {
            "message": intent.description,
            "response": f"This doesn't help your position. {best_move} was the move — it does something concrete.",
        }
    elif severity == "mistake":
        return {
            "message": intent.description,
            "response": f"Not sure what the plan was here. {best_move} keeps your position healthy.",
        }
    else:
        return {
            "message": intent.description,
            "response": f"There's a clearer move here: {best_move}.",
        }
