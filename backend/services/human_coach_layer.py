"""
Human Coach Layer
=================

Transforms raw chess analysis into human-coach-like insights.
This adds the "WHY" behind mistakes - psychological and behavioral context.

Key features:
- Behavioral tagging for each mistake (impatience, laziness, hope chess, etc.)
- Cross-game pattern detection ("This is the 3rd time you've...")
- Specific, actionable moments (not generic "something important")
- Coach voice throughout
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
from enum import Enum

logger = logging.getLogger(__name__)


class BehavioralTag(str, Enum):
    """Psychological/behavioral reasons behind mistakes"""
    IMPATIENCE = "impatience"          # Played too fast, didn't consider alternatives
    HOPE_CHESS = "hope_chess"          # Assumed opponent wouldn't find the best move
    LAZINESS = "laziness"              # Didn't calculate deep enough
    OVERCONFIDENCE = "overconfidence"  # Assumed position was winning, stopped trying
    TUNNEL_VISION = "tunnel_vision"    # Focused on one idea, missed opponent's threat
    TIME_PRESSURE = "time_pressure"    # Running low on time
    FATIGUE = "fatigue"                # Late in session, accuracy dropped
    TILT = "tilt"                      # After a bad move, made more bad moves
    PATTERN_BLIND = "pattern_blind"    # Missed a common tactical pattern
    POSITIONAL_NEGLECT = "positional_neglect"  # Ignored positional factors
    DEFENSIVE_LAPSE = "defensive_lapse"  # Forgot to check opponent's threats


BEHAVIORAL_EXPLANATIONS = {
    BehavioralTag.IMPATIENCE: {
        "short": "You were impatient",
        "long": "You played this move quickly without considering the alternatives. A good habit is to always ask 'What else can I do here?' before committing.",
        "question": "Did you feel rushed here? What made you choose this move so quickly?"
    },
    BehavioralTag.HOPE_CHESS: {
        "short": "You played 'hope chess'",
        "long": "You assumed your opponent wouldn't find the best response. Strong players always assume their opponent will play the best move.",
        "question": "Did you consider what your opponent's best reply would be?"
    },
    BehavioralTag.LAZINESS: {
        "short": "You didn't calculate deeply enough",
        "long": "The winning move required calculating 2-3 moves deeper. Training your calculation muscle takes practice.",
        "question": "How many moves ahead did you calculate here?"
    },
    BehavioralTag.OVERCONFIDENCE: {
        "short": "You relaxed too early",
        "long": "When you're winning, it's tempting to think any move works. But winning positions require precision to convert.",
        "question": "Did you feel like the game was already won?"
    },
    BehavioralTag.TUNNEL_VISION: {
        "short": "You were focused on your own plan",
        "long": "You were so focused on your own idea that you missed your opponent's threat. Always ask 'What does my opponent want?' before moving.",
        "question": "What was your opponent threatening with their last move?"
    },
    BehavioralTag.TIME_PRESSURE: {
        "short": "Time pressure affected your decision",
        "long": "When the clock is ticking, we make faster, less accurate decisions. Practice time management in the opening and middlegame.",
        "question": "How much time did you have here?"
    },
    BehavioralTag.FATIGUE: {
        "short": "Mental fatigue may have affected you",
        "long": "This was late in the game or your session. Our accuracy naturally drops when we're tired.",
        "question": "Were you feeling mentally tired at this point?"
    },
    BehavioralTag.TILT: {
        "short": "You were tilting after a mistake",
        "long": "After making an error, it's common to make more errors. Taking a breath and refocusing is crucial.",
        "question": "Did your previous mistake affect your mindset here?"
    },
    BehavioralTag.PATTERN_BLIND: {
        "short": "You missed a common tactical pattern",
        "long": "This position contained a tactical pattern (fork, pin, skewer, etc.) that you didn't recognize. Pattern training helps!",
        "question": "Can you see the tactical theme now?"
    },
    BehavioralTag.POSITIONAL_NEGLECT: {
        "short": "You ignored positional factors",
        "long": "This move looked active but weakened your position. Chess is about balance between tactics and strategy.",
        "question": "What did this move do to your pawn structure or piece coordination?"
    },
    BehavioralTag.DEFENSIVE_LAPSE: {
        "short": "You forgot to check for threats",
        "long": "Before playing, always run through: Checks, Captures, Threats. What is my opponent threatening?",
        "question": "What was your opponent's threat after their last move?"
    },
}


def infer_behavioral_tag(
    move_data: Dict,
    game_context: Dict,
    position_eval: Dict,
    similar_mistakes: List[Dict] = None
) -> Optional[Dict[str, Any]]:
    """
    Infer the psychological/behavioral reason behind a mistake.
    
    Args:
        move_data: The move that was played (move, best_move, eval_loss)
        game_context: Context (move_number, time_left, game_phase, previous_moves)
        position_eval: Evaluation before/after (was winning/losing/equal)
        similar_mistakes: List of similar mistakes from other games
    
    Returns:
        Dict with tag, explanation, and coaching question
    """
    tags = []
    
    cp_loss = move_data.get("cp_loss", 0)
    move_number = game_context.get("move_number", 0)
    game_phase = game_context.get("game_phase", "middlegame")
    eval_before = position_eval.get("eval_before", 0)
    time_left = game_context.get("time_left_seconds")
    previous_blunders = game_context.get("previous_blunders_in_game", 0)
    session_game_number = game_context.get("session_game_number", 1)
    category = move_data.get("category", "")
    
    # Time pressure
    if time_left is not None and time_left < 60:
        tags.append((BehavioralTag.TIME_PRESSURE, 0.9))
    elif time_left is not None and time_left < 120:
        tags.append((BehavioralTag.TIME_PRESSURE, 0.6))
    
    # Tilt - multiple blunders in same game
    if previous_blunders >= 2:
        tags.append((BehavioralTag.TILT, 0.8))
    elif previous_blunders >= 1:
        tags.append((BehavioralTag.TILT, 0.5))
    
    # Overconfidence - blunder when significantly winning
    if eval_before > 300:  # Was winning by 3+ pawns
        tags.append((BehavioralTag.OVERCONFIDENCE, 0.85))
    elif eval_before > 150:
        tags.append((BehavioralTag.OVERCONFIDENCE, 0.6))
    
    # Fatigue - late in session
    if session_game_number >= 5:
        tags.append((BehavioralTag.FATIGUE, 0.7))
    
    # Pattern blind - tactical mistakes
    if "tactical" in category.lower() or "oversight" in category.lower():
        tags.append((BehavioralTag.PATTERN_BLIND, 0.75))
    
    # Defensive lapse - missed opponent's threat
    if move_data.get("missed_threat"):
        tags.append((BehavioralTag.DEFENSIVE_LAPSE, 0.85))
        tags.append((BehavioralTag.TUNNEL_VISION, 0.7))
    
    # Positional neglect
    if "positional" in category.lower():
        tags.append((BehavioralTag.POSITIONAL_NEGLECT, 0.8))
    
    # Calculation error without time pressure = laziness or hope chess
    if "calculation" in category.lower() and (time_left is None or time_left > 120):
        if cp_loss > 300:  # Big blunder
            tags.append((BehavioralTag.LAZINESS, 0.7))
        else:
            tags.append((BehavioralTag.HOPE_CHESS, 0.65))
    
    # If no specific tag, default based on magnitude
    if not tags:
        if cp_loss > 200:
            tags.append((BehavioralTag.IMPATIENCE, 0.5))
        else:
            tags.append((BehavioralTag.TUNNEL_VISION, 0.4))
    
    # Get the most likely tag
    if tags:
        tags.sort(key=lambda x: -x[1])
        primary_tag = tags[0][0]
        confidence = tags[0][1]
        
        explanation = BEHAVIORAL_EXPLANATIONS.get(primary_tag, {})
        
        result = {
            "tag": primary_tag.value,
            "confidence": confidence,
            "short_explanation": explanation.get("short", ""),
            "long_explanation": explanation.get("long", ""),
            "reflection_question": explanation.get("question", ""),
            "all_tags": [(t.value, c) for t, c in tags[:3]]
        }
        
        # Add cross-game pattern if similar mistakes exist
        if similar_mistakes and len(similar_mistakes) > 0:
            result["recurring_pattern"] = {
                "count": len(similar_mistakes) + 1,
                "message": f"This is the {len(similar_mistakes) + 1}{'st' if len(similar_mistakes) == 0 else 'nd' if len(similar_mistakes) == 1 else 'rd' if len(similar_mistakes) == 2 else 'th'} time you've made this type of mistake.",
                "previous_games": [
                    {"game_id": m.get("game_id"), "move_number": m.get("move_number")}
                    for m in similar_mistakes[:3]
                ]
            }
        
        return result
    
    return None


def generate_moment_insight(
    position: Dict,
    moment_type: str,
    game_context: Dict
) -> Dict[str, Any]:
    """
    Generate a specific, actionable insight for a critical moment.
    
    Instead of "Something important is happening", we say exactly what and why.
    """
    fen = position.get("fen", "")
    eval_change = position.get("eval_change", 0)
    your_move = position.get("your_move", "")
    best_move = position.get("best_move", "")
    threats = position.get("threats", [])
    
    insight = {
        "type": moment_type,
        "move_number": position.get("move_number"),
        "specific": True
    }
    
    if moment_type == "critical_decision":
        if abs(eval_change) > 200:
            insight["headline"] = "This move changed the game"
            insight["detail"] = f"The evaluation swung by {abs(eval_change)/100:.1f} pawns here. This was the moment the game turned."
        else:
            insight["headline"] = "A crossroads in the position"
            insight["detail"] = "Multiple plans were possible here. The choice you made shaped the rest of the game."
    
    elif moment_type == "missed_tactic":
        insight["headline"] = f"You missed a tactical shot"
        insight["detail"] = f"Instead of {your_move}, {best_move} would have won material or created a decisive attack."
        insight["training_link"] = "tactical_patterns"
    
    elif moment_type == "defensive_moment":
        if threats:
            threat_desc = threats[0] if isinstance(threats[0], str) else threats[0].get("description", "a threat")
            insight["headline"] = f"Your opponent created {threat_desc}"
            insight["detail"] = "This was a moment to pause and ask: What is my opponent threatening? How do I defend?"
        else:
            insight["headline"] = "A defensive challenge"
            insight["detail"] = "Your opponent put pressure on your position. Finding the right defense was key."
    
    elif moment_type == "winning_technique":
        insight["headline"] = "Converting a winning position"
        insight["detail"] = "You were ahead here. The question was: how to simplify and win cleanly?"
        insight["principle"] = "When winning, trade pieces, not pawns. Simplify to a won endgame."
    
    elif moment_type == "opening_deviation":
        insight["headline"] = "You left the book here"
        insight["detail"] = "This move took you out of known opening theory. From here, you were on your own."
    
    else:
        insight["headline"] = "A key moment"
        insight["detail"] = "Pay attention to positions like this in your training."
        insight["specific"] = False
    
    return insight


def generate_coach_voice_summary(
    game_data: Dict,
    analysis: Dict,
    player_identity: Dict
) -> Dict[str, Any]:
    """
    Generate a human-coach-style summary of the game.
    
    This is what a real coach would say after reviewing your game.
    """
    result = game_data.get("result", "unknown")
    accuracy = analysis.get("accuracy", 0)
    blunders = analysis.get("blunders", 0)
    mistakes = analysis.get("mistakes", 0)
    turning_point = analysis.get("turning_point", {})
    
    # Get player's known weaknesses
    known_weaknesses = player_identity.get("blunder_taxonomy", {}).get("by_type", {})
    most_common_weakness = max(known_weaknesses.items(), key=lambda x: x[1])[0] if known_weaknesses else None
    
    summary = {
        "opening_line": "",
        "key_observation": "",
        "behavioral_insight": "",
        "actionable_takeaway": "",
        "encouragement": ""
    }
    
    # Opening line based on result
    if result == "win":
        if accuracy >= 90:
            summary["opening_line"] = "Excellent game! You played with precision and earned this win."
        elif accuracy >= 75:
            summary["opening_line"] = "A solid win. You played well, though there's room to sharpen a few moments."
        else:
            summary["opening_line"] = "You got the win, but let's be honest—there were some shaky moments. Let's learn from them."
    elif result == "loss":
        if accuracy >= 80:
            summary["opening_line"] = "A tough loss, but you actually played quite well. Sometimes that happens in chess."
        else:
            summary["opening_line"] = "This game had some struggles. Let's understand what went wrong so it doesn't happen again."
    else:
        summary["opening_line"] = "An interesting battle that ended in a draw. Let's see if there were missed opportunities."
    
    # Key observation
    if turning_point:
        move_num = turning_point.get("move_number", "?")
        pattern = turning_point.get("pattern_name", "error")
        summary["key_observation"] = f"The critical moment was move {move_num}. A {pattern.lower()} that cost you the advantage."
    elif blunders > 0:
        summary["key_observation"] = f"You had {blunders} serious error{'s' if blunders > 1 else ''} that significantly affected the game."
    elif mistakes > 0:
        summary["key_observation"] = f"The game was mostly solid with {mistakes} inaccurac{'ies' if mistakes > 1 else 'y'} that slightly shifted the balance."
    else:
        summary["key_observation"] = "No major errors—this was a clean game from your side."
    
    # Behavioral insight (if we have pattern data)
    if most_common_weakness and turning_point:
        tp_category = turning_point.get("category", "")
        if most_common_weakness.lower() in tp_category.lower():
            summary["behavioral_insight"] = f"This type of mistake ({most_common_weakness.replace('_', ' ')}) has come up before in your games. It's becoming a pattern we should address."
        else:
            summary["behavioral_insight"] = f"This mistake was different from your usual pattern. Stay aware of this type of position."
    
    # Actionable takeaway
    if turning_point:
        focus = turning_point.get("training_focus", "general")
        if focus == "tactical":
            summary["actionable_takeaway"] = "Practice tactical puzzles, especially ones involving the pattern you missed here."
        elif focus == "positional":
            summary["actionable_takeaway"] = "Study similar pawn structures and plans. Understanding the position helps you find the right moves."
        elif focus == "endgame":
            summary["actionable_takeaway"] = "Endgame technique! This phase cost you. Work on basic endgame patterns."
        else:
            summary["actionable_takeaway"] = "Review this position until the correct idea feels natural."
    else:
        summary["actionable_takeaway"] = "Keep playing and analyzing. Consistent practice is how you improve."
    
    # Encouragement
    if accuracy >= 85:
        summary["encouragement"] = "You're playing at a strong level. Keep it up!"
    elif accuracy >= 70:
        summary["encouragement"] = "Solid foundation. A bit more focus and you'll see real improvement."
    else:
        summary["encouragement"] = "Every game is a lesson. The fact that you're analyzing shows you're on the right path."
    
    return summary


async def enrich_game_analysis(
    db,
    game_id: str,
    user_id: str,
    analysis: Dict
) -> Dict[str, Any]:
    """
    Enrich a game analysis with human coach layer.
    
    Adds:
    - Behavioral tags to mistakes
    - Cross-game pattern connections
    - Specific moment insights
    - Coach voice summary
    """
    enriched = dict(analysis)
    
    # Get player identity for context
    identity = await db.player_identities.find_one(
        {"user_id": user_id},
        {"_id": 0}
    ) or {}
    
    # Get similar mistakes from other games
    turning_point = analysis.get("turning_point", {})
    similar_mistakes = []
    
    if turning_point:
        category = turning_point.get("category", "")
        if category:
            similar = await db.game_analyses.find(
                {
                    "user_id": user_id,
                    "game_id": {"$ne": game_id},
                    "turning_point.category": category
                },
                {"_id": 0, "game_id": 1, "turning_point.move_number": 1}
            ).limit(5).to_list(5)
            similar_mistakes = [
                {"game_id": s["game_id"], "move_number": s.get("turning_point", {}).get("move_number")}
                for s in similar
            ]
    
    # Add behavioral analysis to turning point
    if turning_point:
        game_context = {
            "move_number": turning_point.get("move_number", 0),
            "game_phase": "middlegame",  # Could be inferred from move number
            "previous_blunders_in_game": analysis.get("blunders", 0) - 1,
            "session_game_number": 1  # Would need session tracking
        }
        
        position_eval = {
            "eval_before": turning_point.get("eval_before", 0),
            "eval_after": turning_point.get("eval_after", 0)
        }
        
        behavioral = infer_behavioral_tag(
            turning_point,
            game_context,
            position_eval,
            similar_mistakes
        )
        
        if behavioral:
            enriched["turning_point"]["behavioral"] = behavioral
    
    # Generate coach voice summary
    game_data = await db.games.find_one(
        {"game_id": game_id, "user_id": user_id},
        {"_id": 0, "result": 1, "user_color": 1, "opponent": 1}
    ) or {}
    
    enriched["coach_summary"] = generate_coach_voice_summary(
        game_data,
        analysis,
        identity
    )
    
    # Add cross-game stats
    total_games = await db.game_analyses.count_documents({"user_id": user_id})
    enriched["cross_game_context"] = {
        "total_games_analyzed": total_games,
        "similar_mistake_count": len(similar_mistakes),
        "similar_mistakes": similar_mistakes[:3]
    }
    
    return enriched


async def get_aggregated_patterns(
    db,
    user_id: str,
    limit: int = 10
) -> Dict[str, Any]:
    """
    Get aggregated patterns across all games for the Memory tab.
    """
    # Get all analyses
    analyses = await db.game_analyses.find(
        {"user_id": user_id},
        {"_id": 0, "turning_point": 1, "game_id": 1, "stockfish_analysis": 1}
    ).to_list(100)
    
    # Aggregate by category
    category_stats = {}
    pattern_examples = {}
    
    for a in analyses:
        tp = a.get("turning_point")
        if tp:
            category = tp.get("category", "unknown")
            pattern = tp.get("pattern_name", "Unknown")
            
            if category not in category_stats:
                category_stats[category] = {
                    "count": 0,
                    "patterns": {},
                    "examples": []
                }
            
            category_stats[category]["count"] += 1
            
            if pattern not in category_stats[category]["patterns"]:
                category_stats[category]["patterns"][pattern] = 0
            category_stats[category]["patterns"][pattern] += 1
            
            if len(category_stats[category]["examples"]) < 3:
                category_stats[category]["examples"].append({
                    "game_id": a.get("game_id"),
                    "move_number": tp.get("move_number"),
                    "move": tp.get("move"),
                    "pattern": pattern
                })
    
    # Calculate accuracy trend
    accuracy_trend = []
    for a in sorted(analyses, key=lambda x: x.get("game_id", ""))[-10:]:
        sf = a.get("stockfish_analysis", {})
        if sf.get("accuracy"):
            accuracy_trend.append({
                "game_id": a.get("game_id"),
                "accuracy": sf.get("accuracy")
            })
    
    # Identify top weaknesses
    top_weaknesses = sorted(
        category_stats.items(),
        key=lambda x: -x[1]["count"]
    )[:5]
    
    return {
        "total_games": len(analyses),
        "category_breakdown": category_stats,
        "top_weaknesses": [
            {
                "category": cat,
                "count": data["count"],
                "percentage": round(data["count"] / len(analyses) * 100, 1) if analyses else 0,
                "top_pattern": max(data["patterns"].items(), key=lambda x: x[1])[0] if data["patterns"] else None,
                "examples": data["examples"]
            }
            for cat, data in top_weaknesses
        ],
        "accuracy_trend": accuracy_trend,
        "has_enough_data": len(analyses) >= 5
    }
