"""
Memory Brain — Connects player memory to all coaching decisions.

Single source of truth for "what do we know about this player and what should we do about it?"

Used by:
- Play with Coach: what opening to teach, what to focus on
- Training: which drills to surface first
- Game Review (Coach tab): trend context
- Pregame intro: personalized message
"""

import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


async def get_player_brain(db, user_id: str) -> Dict:
    """
    Get everything we know about this player in one call.
    This is THE function every coaching feature should call.
    """
    # 1. Player Identity (Chess DNA)
    identity = await db.player_identity.find_one({"user_id": user_id}, {"_id": 0})

    # 2. Coach Memory (performance trends, weaknesses, learning history)
    memory = await db.coach_memory.find_one({"user_id": user_id}, {"_id": 0})

    # 3. Player Profile (rating, accuracy stats)
    profile = await db.player_profiles.find_one({"user_id": user_id}, {"_id": 0})

    # Build the brain
    brain = {
        "user_id": user_id,
        "rating": _get_rating(profile, identity),
        "games_analyzed": profile.get("games_analyzed", 0) if profile else 0,
    }

    # Weaknesses (prioritized)
    brain["top_weakness"] = _get_top_weakness(identity, memory)
    brain["all_weaknesses"] = _get_all_weaknesses(identity, memory)

    # Strengths
    brain["strengths"] = _get_strengths(identity)

    # Play style
    brain["play_style"] = _get_play_style(identity)

    # Momentum (winning/losing streak)
    brain["momentum"] = _get_momentum(identity, memory)

    # What to practice (auto-selected drill focus)
    brain["drill_focus"] = _get_drill_focus(identity, memory)

    # What opening to teach
    brain["opening_recommendation"] = _get_opening_recommendation(identity, memory)

    # One-line coaching focus
    brain["focus_message"] = _build_focus_message(brain)

    return brain


def _get_rating(profile: Optional[Dict], identity: Optional[Dict]) -> int:
    if profile:
        r = profile.get("current_rating") or profile.get("estimated_rating") or profile.get("estimated_elo")
        if r:
            return int(r)
    if identity:
        r = identity.get("estimated_rating") or identity.get("rating")
        if r:
            return int(r)
    return 1200


def _get_top_weakness(identity: Optional[Dict], memory: Optional[Dict]) -> Optional[Dict]:
    """The ONE thing holding this player back the most."""
    # From identity: blunder taxonomy
    if identity:
        taxonomy = identity.get("blunder_taxonomy", {})
        by_type = taxonomy.get("by_type", {})
        if by_type:
            worst_type = max(by_type.items(), key=lambda x: x[1], default=None)
            if worst_type and worst_type[1] > 0:
                return {
                    "type": worst_type[0],
                    "count": worst_type[1],
                    "label": _weakness_label(worst_type[0]),
                    "fix": _weakness_fix(worst_type[0]),
                }

    # From memory: tracked weaknesses
    if memory:
        weaknesses = memory.get("weaknesses", [])
        if weaknesses:
            worst = max(weaknesses, key=lambda w: w.get("detection_count", 0))
            if worst.get("detection_count", 0) > 0:
                return {
                    "type": worst.get("name", "unknown"),
                    "count": worst.get("detection_count", 0),
                    "label": _weakness_label(worst.get("name", "")),
                    "fix": _weakness_fix(worst.get("name", "")),
                    "improving": worst.get("improving", False),
                }

    return None


def _get_all_weaknesses(identity: Optional[Dict], memory: Optional[Dict]) -> list:
    """All weaknesses sorted by severity."""
    results = []
    if identity:
        by_type = identity.get("blunder_taxonomy", {}).get("by_type", {})
        for wtype, count in sorted(by_type.items(), key=lambda x: x[1], reverse=True):
            if count > 0:
                results.append({
                    "type": wtype,
                    "count": count,
                    "label": _weakness_label(wtype),
                    "drill_pattern": _type_to_drill_pattern(wtype),
                })
    return results[:5]


def _get_strengths(identity: Optional[Dict]) -> list:
    if not identity:
        return []
    strengths = identity.get("strengths", [])
    if isinstance(strengths, list):
        return [s if isinstance(s, str) else s.get("name", "") for s in strengths[:3]]
    return []


def _get_play_style(identity: Optional[Dict]) -> str:
    if not identity:
        return "developing"
    style = identity.get("style_profile", {})
    if isinstance(style, dict):
        return style.get("primary_style", "developing")
    return identity.get("play_style", "developing")


def _get_momentum(identity: Optional[Dict], memory: Optional[Dict]) -> Dict:
    streak_type = None
    streak_count = 0

    if identity:
        wins = identity.get("consecutive_wins", 0)
        losses = identity.get("consecutive_losses", 0)
        if wins >= 2:
            streak_type = "winning"
            streak_count = wins
        elif losses >= 2:
            streak_type = "losing"
            streak_count = losses

    if memory:
        recent = memory.get("performance", {}).get("recent_results", [])
        if recent and not streak_type:
            if recent[-1] == "win":
                streak_type = "positive"
            elif recent[-1] == "loss":
                streak_type = "negative"

    return {"type": streak_type, "count": streak_count}


def _get_drill_focus(identity: Optional[Dict], memory: Optional[Dict]) -> Optional[str]:
    """What pattern should training auto-focus on?"""
    weakness = _get_top_weakness(identity, memory)
    if weakness:
        return _type_to_drill_pattern(weakness["type"])
    return None


def _get_opening_recommendation(identity: Optional[Dict], memory: Optional[Dict]) -> str:
    """Which opening curriculum to recommend."""
    # For now, default to London. Later: check what they play most
    return "london_system"


def _build_focus_message(brain: Dict) -> str:
    """One sentence: what should this player focus on RIGHT NOW?"""
    weakness = brain.get("top_weakness")
    momentum = brain.get("momentum", {})

    if not weakness:
        return "Play more games so I can find your patterns."

    msg = f"Your #1 issue: {weakness['label']}."

    if weakness.get("improving"):
        msg += " You're getting better at this — keep going."
    elif weakness.get("count", 0) >= 5:
        msg += f" This has happened {weakness['count']} times. Let's fix it."
    
    if momentum.get("type") == "losing" and momentum.get("count", 0) >= 3:
        msg += " Tough streak — focus on this one thing and the wins will come."

    return msg


# ─── MAPPINGS ────────────────────────────────────────────────

def _weakness_label(wtype: str) -> str:
    labels = {
        "hanging_piece": "Leaving pieces undefended",
        "tactical_error": "Missing opponent's threats",
        "missed_tactic": "Missing winning tactics",
        "calculation_depth": "Not calculating deep enough",
        "positional_mistake": "Moving without a plan",
        "time_trouble": "Blundering under time pressure",
        "opening_error": "Losing in the opening",
        "endgame_error": "Poor endgame technique",
        "impulse_move": "Moving too fast without thinking",
        "king_safety_neglect": "Ignoring king safety",
        "post_blunder_tilt": "Tilting after mistakes",
        "winning_position_collapse": "Throwing winning positions",
    }
    return labels.get(wtype, wtype.replace("_", " ").title())


def _weakness_fix(wtype: str) -> str:
    fixes = {
        "hanging_piece": "Before every move: is my piece safe where it's going?",
        "tactical_error": "Before every move: what is my opponent threatening?",
        "missed_tactic": "Check all captures and checks before playing.",
        "calculation_depth": "Ask: what happens after they respond?",
        "positional_mistake": "What's my plan for the next 3 moves?",
        "time_trouble": "Under 2 minutes: simplify, don't calculate.",
        "opening_error": "Learn ONE opening well. Development, center, castle.",
        "endgame_error": "Activate your king. Push passed pawns.",
        "impulse_move": "Count to 3 before every move.",
        "king_safety_neglect": "Castle early. Don't leave your king in the center.",
        "post_blunder_tilt": "After a mistake, take a breath. Play solid, don't try to win it back immediately.",
        "winning_position_collapse": "When ahead: stay sharp, don't coast.",
    }
    return fixes.get(wtype, "Focus on this pattern in your next game.")


def _type_to_drill_pattern(wtype: str) -> str:
    """Map weakness type to training drill pattern."""
    mapping = {
        "hanging_piece": "hanging_piece",
        "tactical_error": "tactical_miss",
        "missed_tactic": "tactical_miss",
        "calculation_depth": "calculation_depth",
        "positional_mistake": "positional",
        "time_trouble": "calculation_depth",
        "opening_error": "opening_principles",
        "endgame_error": "positional",
        "impulse_move": "tactical_miss",
        "king_safety_neglect": "checkmate_pattern",
        "post_blunder_tilt": "calculation_depth",
        "winning_position_collapse": "winning_position_collapse",
    }
    return mapping.get(wtype, "tactical_miss")
