"""
Thinking Score Service
======================

Calculates and tracks how well a player applies thinking habits across games.

The score is based on REAL game data - analyzing patterns in mistakes to determine
which thinking steps are being followed or skipped.

Metrics tracked:
1. Threat Awareness - Did you miss opponent threats? (blunders from undefended pieces)
2. Tactical Vision - Did you miss winning tactics? (missed captures, checks)
3. Verification Habit - Did you blunder immediately after opponent's move? (impulse errors)
4. King Safety Focus - Did you neglect king safety? (back-rank issues, exposed king)
5. Patience Score - Did you rush? (time-correlated blunders, premature attacks)

Each metric is calculated from actual move-by-move analysis data.
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class ThinkingHabit(str, Enum):
    """The core thinking habits we track."""
    THREAT_AWARENESS = "threat_awareness"      # Checking opponent threats
    TACTICAL_VISION = "tactical_vision"        # Finding forcing moves
    MOVE_VERIFICATION = "move_verification"    # Double-checking before moving
    KING_SAFETY = "king_safety"                # Keeping king safe
    PATIENCE = "patience"                       # Not rushing decisions


@dataclass
class HabitScore:
    """Score for a single thinking habit."""
    habit: ThinkingHabit
    score: float  # 0-100
    games_measured: int
    trend: str  # "improving", "stable", "declining"
    explanation: str
    recent_examples: List[Dict]  # Examples from recent games


# Mapping from mistake categories to thinking habits they indicate
MISTAKE_TO_HABIT_MAPPING = {
    # Threat awareness issues
    "hanging_piece": ThinkingHabit.THREAT_AWARENESS,
    "missed_threat": ThinkingHabit.THREAT_AWARENESS,
    "undefended_piece_lost": ThinkingHabit.THREAT_AWARENESS,
    
    # Tactical vision issues  
    "missed_tactic": ThinkingHabit.TACTICAL_VISION,
    "missed_mate": ThinkingHabit.TACTICAL_VISION,
    "missed_capture": ThinkingHabit.TACTICAL_VISION,
    "missed_fork": ThinkingHabit.TACTICAL_VISION,
    "missed_pin": ThinkingHabit.TACTICAL_VISION,
    "missed_skewer": ThinkingHabit.TACTICAL_VISION,
    
    # Verification issues
    "blunder": ThinkingHabit.MOVE_VERIFICATION,
    "one_move_blunder": ThinkingHabit.MOVE_VERIFICATION,
    "immediate_blunder": ThinkingHabit.MOVE_VERIFICATION,
    
    # King safety issues
    "king_exposed": ThinkingHabit.KING_SAFETY,
    "back_rank_weakness": ThinkingHabit.KING_SAFETY,
    "failed_to_castle": ThinkingHabit.KING_SAFETY,
    "weakened_king_position": ThinkingHabit.KING_SAFETY,
    
    # Patience issues
    "premature_attack": ThinkingHabit.PATIENCE,
    "rushed_move": ThinkingHabit.PATIENCE,
    "time_trouble_blunder": ThinkingHabit.PATIENCE,
}


def calculate_game_thinking_scores(
    game_analysis: Dict,
    user_color: str
) -> Dict[str, Any]:
    """
    Calculate thinking scores for a single game based on move analysis.
    
    Returns scores for each thinking habit based on actual mistakes made.
    """
    move_evals = game_analysis.get("move_evaluations", [])
    critical_moments = game_analysis.get("critical_moments", [])
    
    # Initialize counters for each habit
    habit_mistakes = {habit: 0 for habit in ThinkingHabit}
    habit_opportunities = {habit: 0 for habit in ThinkingHabit}
    examples = {habit: [] for habit in ThinkingHabit}
    
    total_moves = len(move_evals)
    
    for move_eval in move_evals:
        # Count opportunities - every move is a chance to apply each habit
        for habit in ThinkingHabit:
            habit_opportunities[habit] += 1
        
        # Check for mistakes and categorize them
        cp_loss = abs(move_eval.get("cp_loss", 0))
        category = move_eval.get("category", "")
        
        if cp_loss >= 100:  # Significant mistake
            # Determine which habit was likely violated
            habit = _categorize_mistake(move_eval, game_analysis)
            if habit:
                habit_mistakes[habit] += 1
                if len(examples[habit]) < 3:
                    examples[habit].append({
                        "move_number": move_eval.get("move_number"),
                        "move": move_eval.get("move"),
                        "cp_loss": cp_loss,
                        "explanation": _get_mistake_explanation(move_eval, habit)
                    })
    
    # Also analyze critical moments for additional insights
    for moment in critical_moments:
        category = moment.get("category", "")
        habit = MISTAKE_TO_HABIT_MAPPING.get(category)
        if habit and moment.get("cp_loss", 0) >= 100:
            habit_mistakes[habit] += 1
    
    # Calculate scores (higher = better)
    scores = {}
    for habit in ThinkingHabit:
        opportunities = habit_opportunities[habit]
        mistakes = habit_mistakes[habit]
        
        if opportunities > 0:
            # Score = percentage of moves where habit was followed (no relevant mistake)
            score = max(0, min(100, 100 * (1 - (mistakes / opportunities * 3))))  # Scale factor of 3 to be more sensitive
        else:
            score = 100  # No data, assume perfect
        
        scores[habit.value] = {
            "score": round(score, 1),
            "mistakes": mistakes,
            "opportunities": opportunities,
            "examples": examples[habit]
        }
    
    # Calculate overall thinking score (weighted average)
    weights = {
        ThinkingHabit.THREAT_AWARENESS: 0.25,
        ThinkingHabit.TACTICAL_VISION: 0.25,
        ThinkingHabit.MOVE_VERIFICATION: 0.20,
        ThinkingHabit.KING_SAFETY: 0.15,
        ThinkingHabit.PATIENCE: 0.15,
    }
    
    overall = sum(scores[h.value]["score"] * w for h, w in weights.items())
    
    return {
        "overall_score": round(overall, 1),
        "habit_scores": scores,
        "total_moves": total_moves,
        "game_id": game_analysis.get("game_id"),
        "calculated_at": datetime.now(timezone.utc).isoformat()
    }


def _categorize_mistake(move_eval: Dict, game_analysis: Dict) -> Optional[ThinkingHabit]:
    """
    Categorize a mistake into which thinking habit was violated.
    
    Uses multiple signals to determine the most likely cause.
    """
    category = move_eval.get("category", "")
    
    # Check explicit category mapping first
    if category in MISTAKE_TO_HABIT_MAPPING:
        return MISTAKE_TO_HABIT_MAPPING[category]
    
    # Analyze the mistake based on available data
    cp_loss = abs(move_eval.get("cp_loss", 0))
    insight = move_eval.get("insight", {})
    
    # Check if it was a tactical miss
    if insight.get("missed_tactic") or insight.get("what_you_missed"):
        missed_text = str(insight.get("what_you_missed", "")).lower()
        if any(word in missed_text for word in ["capture", "take", "win", "fork", "pin"]):
            return ThinkingHabit.TACTICAL_VISION
        if any(word in missed_text for word in ["threat", "attack", "defend", "hang"]):
            return ThinkingHabit.THREAT_AWARENESS
    
    # Check if it was likely a verification failure (immediate blunder)
    if cp_loss >= 300:  # Big blunder
        return ThinkingHabit.MOVE_VERIFICATION
    
    # Check king safety indicators
    if insight.get("king_safety") or "king" in str(insight).lower():
        return ThinkingHabit.KING_SAFETY
    
    # Default to threat awareness for moderate mistakes
    if cp_loss >= 100:
        return ThinkingHabit.THREAT_AWARENESS
    
    return None


def _get_mistake_explanation(move_eval: Dict, habit: ThinkingHabit) -> str:
    """Generate a human-readable explanation for why this habit was violated."""
    
    insight = move_eval.get("insight", {})
    what_missed = insight.get("what_you_missed", "")
    
    if what_missed:
        return what_missed
    
    explanations = {
        ThinkingHabit.THREAT_AWARENESS: "Opponent's threat was missed before moving",
        ThinkingHabit.TACTICAL_VISION: "A winning tactical opportunity was missed",
        ThinkingHabit.MOVE_VERIFICATION: "Move wasn't verified - it left a weakness",
        ThinkingHabit.KING_SAFETY: "King safety was compromised",
        ThinkingHabit.PATIENCE: "Move was likely rushed without full calculation",
    }
    
    return explanations.get(habit, "Thinking habit violation detected")


def calculate_thinking_progress(
    game_scores: List[Dict],
    window_size: int = 5
) -> Dict[str, Any]:
    """
    Calculate thinking progress over multiple games.
    
    Compares recent games to older games to show improvement or decline.
    """
    if not game_scores or len(game_scores) < 2:
        return {
            "has_enough_data": False,
            "message": "Play more games to see your thinking progress",
            "games_needed": max(0, 2 - len(game_scores))
        }
    
    # Sort by date (most recent first)
    sorted_scores = sorted(
        game_scores, 
        key=lambda x: x.get("calculated_at", ""), 
        reverse=True
    )
    
    # Split into recent and older
    recent_count = min(window_size, len(sorted_scores) // 2)
    if recent_count < 1:
        recent_count = 1
    
    recent_games = sorted_scores[:recent_count]
    older_games = sorted_scores[recent_count:recent_count*2]
    
    if not older_games:
        older_games = sorted_scores[recent_count:]
    
    # Calculate averages for each habit
    habit_progress = {}
    
    for habit in ThinkingHabit:
        recent_avg = _calculate_habit_average(recent_games, habit.value)
        older_avg = _calculate_habit_average(older_games, habit.value)
        
        if older_avg is not None and recent_avg is not None:
            change = recent_avg - older_avg
            change_percent = (change / max(older_avg, 1)) * 100
            
            if change > 5:
                trend = "improving"
                trend_emoji = "📈"
            elif change < -5:
                trend = "declining"
                trend_emoji = "📉"
            else:
                trend = "stable"
                trend_emoji = "➡️"
            
            habit_progress[habit.value] = {
                "current_score": round(recent_avg, 1),
                "previous_score": round(older_avg, 1),
                "change": round(change, 1),
                "change_percent": round(change_percent, 1),
                "trend": trend,
                "trend_emoji": trend_emoji,
                "explanation": _generate_trend_explanation(habit, change, recent_avg)
            }
        else:
            habit_progress[habit.value] = {
                "current_score": recent_avg or 0,
                "previous_score": None,
                "change": None,
                "trend": "insufficient_data"
            }
    
    # Calculate overall progress
    recent_overall = sum(g.get("overall_score", 0) for g in recent_games) / len(recent_games)
    older_overall = sum(g.get("overall_score", 0) for g in older_games) / len(older_games) if older_games else None
    
    overall_change = (recent_overall - older_overall) if older_overall else None
    
    return {
        "has_enough_data": True,
        "overall_score": round(recent_overall, 1),
        "overall_change": round(overall_change, 1) if overall_change else None,
        "overall_trend": "improving" if overall_change and overall_change > 3 else "declining" if overall_change and overall_change < -3 else "stable",
        "habit_progress": habit_progress,
        "games_analyzed": len(sorted_scores),
        "recent_games_count": len(recent_games),
        "comparison_games_count": len(older_games)
    }


def _calculate_habit_average(games: List[Dict], habit_key: str) -> Optional[float]:
    """Calculate average score for a habit across games."""
    scores = []
    for game in games:
        habit_scores = game.get("habit_scores", {})
        if habit_key in habit_scores:
            scores.append(habit_scores[habit_key].get("score", 0))
    
    return sum(scores) / len(scores) if scores else None


def _generate_trend_explanation(habit: ThinkingHabit, change: float, current: float) -> str:
    """Generate a human-readable explanation of the trend."""
    
    habit_names = {
        ThinkingHabit.THREAT_AWARENESS: "threat checking",
        ThinkingHabit.TACTICAL_VISION: "tactical vision",
        ThinkingHabit.MOVE_VERIFICATION: "move verification",
        ThinkingHabit.KING_SAFETY: "king safety awareness",
        ThinkingHabit.PATIENCE: "patience and calculation",
    }
    
    name = habit_names.get(habit, str(habit.value))
    
    if change > 10:
        return f"Great improvement! Your {name} has improved significantly. Keep it up!"
    elif change > 5:
        return f"Your {name} is improving. The practice is paying off."
    elif change > 0:
        return f"Slight improvement in {name}. Stay consistent."
    elif change > -5:
        return f"Your {name} is stable. Focus here to see gains."
    elif change > -10:
        return f"Your {name} has dipped slightly. Review recent games for patterns."
    else:
        return f"Your {name} needs attention. Consider slowing down and applying the checklist."


def get_weakest_habits(progress: Dict, top_n: int = 2) -> List[Dict]:
    """
    Identify the weakest thinking habits that need the most work.
    
    Returns actionable recommendations.
    """
    habit_progress = progress.get("habit_progress", {})
    
    # Sort by current score (lowest first)
    sorted_habits = sorted(
        habit_progress.items(),
        key=lambda x: x[1].get("current_score", 100)
    )
    
    recommendations = []
    for habit_key, data in sorted_habits[:top_n]:
        habit = ThinkingHabit(habit_key)
        score = data.get("current_score", 0)
        
        # Get specific recommendation based on habit
        rec = _get_habit_recommendation(habit, score)
        recommendations.append({
            "habit": habit_key,
            "habit_label": _get_habit_label(habit),
            "score": score,
            "priority": "high" if score < 60 else "medium" if score < 75 else "low",
            "recommendation": rec["action"],
            "checklist_item": rec["checklist"],
            "icon": rec["icon"]
        })
    
    return recommendations


def _get_habit_label(habit: ThinkingHabit) -> str:
    """Get human-readable label for habit."""
    labels = {
        ThinkingHabit.THREAT_AWARENESS: "Threat Awareness",
        ThinkingHabit.TACTICAL_VISION: "Tactical Vision",
        ThinkingHabit.MOVE_VERIFICATION: "Move Verification",
        ThinkingHabit.KING_SAFETY: "King Safety",
        ThinkingHabit.PATIENCE: "Patience",
    }
    return labels.get(habit, habit.value)


def _get_habit_recommendation(habit: ThinkingHabit, score: float) -> Dict[str, str]:
    """Get specific recommendation for improving a habit."""
    
    recommendations = {
        ThinkingHabit.THREAT_AWARENESS: {
            "action": "Before every move, ask: 'What is my opponent threatening?' Look at all their pieces.",
            "checklist": "What is my opponent threatening?",
            "icon": "⚠️"
        },
        ThinkingHabit.TACTICAL_VISION: {
            "action": "Check for forcing moves first: Checks, Captures, Threats (CCT). Do this before considering quiet moves.",
            "checklist": "Are there any checks, captures, or threats?",
            "icon": "⚡"
        },
        ThinkingHabit.MOVE_VERIFICATION: {
            "action": "Before clicking, ask: 'Does this move leave anything undefended?' Take 5 extra seconds.",
            "checklist": "Is anything hanging after this move?",
            "icon": "✓"
        },
        ThinkingHabit.KING_SAFETY: {
            "action": "Periodically check: 'Is my king safe? Can opponent attack it?' Castle early when possible.",
            "checklist": "Is my king safe?",
            "icon": "🛡️"
        },
        ThinkingHabit.PATIENCE: {
            "action": "Don't rush. For critical positions, take at least 30 seconds. Calculate opponent's best reply.",
            "checklist": "Have I calculated the opponent's best response?",
            "icon": "⏳"
        },
    }
    
    return recommendations.get(habit, {
        "action": "Focus on applying the thinking checklist consistently.",
        "checklist": "Did I follow my thinking process?",
        "icon": "🧠"
    })
