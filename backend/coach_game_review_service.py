"""
Coach Game Review Service - Personalized Analysis of User's Last Game

This service acts like a personal chess coach reviewing the student's most recent game:
- Did they follow our opening suggestions?
- Are they fixing the mistakes we identified?
- Where did they improve? Where do they still struggle?
- Personalized, factual feedback based on real data

Architecture:
- DETERMINISTIC ANALYSIS: We gather all facts from the database
- LLM COMMENTARY: GPT writes the personalized message based on facts (no chess analysis)
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime, timezone

# Import opening guidance function from blunder intelligence service
from blunder_intelligence_service import get_opening_guidance, get_dominant_weakness_ranking

logger = logging.getLogger(__name__)


async def get_coach_game_review(db, user_id: str, llm_call_func) -> Dict:
    """
    Generate a personalized coach review of the user's last game.
    
    Returns:
        Dict with coach review data including:
        - last_game: Info about the game being reviewed
        - opening_check: Did they play suggested openings?
        - weakness_check: Did they avoid their known weaknesses?
        - improvement_areas: Where they improved
        - still_struggling: Where they still need work
        - coach_message: Personalized commentary from the coach
    """
    
    # 1. Get user's last analyzed game (after they started using the platform)
    last_game = await db.games.find_one(
        {"user_id": user_id, "is_analyzed": True},
        {"_id": 0},
        sort=[("date", -1)]
    )
    
    if not last_game:
        return {"has_review": False, "reason": "no_games"}
    
    game_id = last_game.get("game_id")
    
    # 2. Get the analysis for this game
    analysis = await db.game_analyses.find_one(
        {"game_id": game_id, "user_id": user_id},
        {"_id": 0}
    )
    
    if not analysis:
        return {"has_review": False, "reason": "no_analysis"}
    
    # 3. Get user's known weaknesses (what we've been telling them to work on)
    user_profile = await db.user_profiles.find_one(
        {"user_id": user_id},
        {"_id": 0, "weaknesses": 1, "suggested_openings": 1, "focus_areas": 1}
    )
    
    # 4. Get user's historical average for comparison
    all_analyses = await db.game_analyses.find(
        {"user_id": user_id},
        {"_id": 0, "stockfish_analysis.accuracy": 1, "stockfish_analysis.blunders": 1, 
         "stockfish_analysis.mistakes": 1, "game_id": 1}
    ).sort("created_at", -1).limit(20).to_list(20)
    
    # Calculate averages (excluding current game)
    other_analyses = [a for a in all_analyses if a.get("game_id") != game_id]
    if other_analyses:
        avg_accuracy = sum(a.get("stockfish_analysis", {}).get("accuracy", 0) for a in other_analyses) / len(other_analyses)
        avg_blunders = sum(a.get("stockfish_analysis", {}).get("blunders", 0) for a in other_analyses) / len(other_analyses)
    else:
        avg_accuracy = 0
        avg_blunders = 0
    
    # 5. Extract facts about this game
    sf_analysis = analysis.get("stockfish_analysis", {})
    game_accuracy = sf_analysis.get("accuracy", 0)
    game_blunders = sf_analysis.get("blunders", 0)
    game_mistakes = sf_analysis.get("mistakes", 0)
    move_evals = sf_analysis.get("move_evaluations", [])
    
    # Get opening played
    opening_name = "Unknown"
    if last_game.get("pgn"):
        import re
        eco_match = re.search(r'\[ECOUrl ".*?/([^"]+)"\]', last_game["pgn"])
        if eco_match:
            opening_name = eco_match.group(1).replace("-", " ").title()
        else:
            opening_match = re.search(r'\[Opening "([^"]+)"\]', last_game["pgn"])
            if opening_match:
                opening_name = opening_match.group(1)
    
    # 6. Analyze blunder types in this game
    blunder_types = []
    for move in move_evals:
        if move.get("classification") in ["blunder", "mistake"]:
            blunder_types.append({
                "move_number": move.get("move_number"),
                "classification": move.get("classification"),
                "phase": move.get("phase", "unknown"),
                "cp_loss": move.get("cp_loss", 0)
            })
    
    # 7. Check against known weaknesses
    known_weaknesses = user_profile.get("weaknesses", []) if user_profile else []
    suggested_openings = user_profile.get("suggested_openings", {}) if user_profile else {}
    
    # Determine if they played a suggested opening
    user_color = last_game.get("user_color", "white")
    suggested_for_color = suggested_openings.get(f"as_{user_color}", [])
    played_suggested = any(
        sug.lower() in opening_name.lower() 
        for sug in suggested_for_color
    ) if suggested_for_color else None
    
    # 8. Build the facts object
    facts = {
        "game_info": {
            "opponent": last_game.get("opponent", "Unknown"),
            "result": last_game.get("result", "unknown"),
            "user_color": user_color,
            "opening": opening_name,
            "date": last_game.get("date", ""),
            "rating_diff": last_game.get("opponent_rating", 0) - last_game.get("user_rating", 0) if last_game.get("opponent_rating") and last_game.get("user_rating") else None
        },
        "performance": {
            "accuracy": round(game_accuracy, 1),
            "blunders": game_blunders,
            "mistakes": game_mistakes,
            "total_errors": game_blunders + game_mistakes
        },
        "comparison": {
            "vs_avg_accuracy": round(game_accuracy - avg_accuracy, 1) if avg_accuracy else None,
            "vs_avg_blunders": round(avg_blunders - game_blunders, 1) if avg_blunders else None,
            "avg_accuracy": round(avg_accuracy, 1),
            "avg_blunders": round(avg_blunders, 1),
            "is_improvement": game_accuracy > avg_accuracy and game_blunders <= avg_blunders
        },
        "opening_check": {
            "played": opening_name,
            "was_suggested": played_suggested,
            "suggested_openings": suggested_for_color[:2] if suggested_for_color else []
        },
        "weakness_check": {
            "known_weaknesses": known_weaknesses[:3] if known_weaknesses else [],
            "blunders_in_game": blunder_types[:5],
            "repeated_weakness": False  # Will calculate below
        },
        "phases": {
            "opening_blunders": len([b for b in blunder_types if b.get("phase") == "opening"]),
            "middlegame_blunders": len([b for b in blunder_types if b.get("phase") == "middlegame"]),
            "endgame_blunders": len([b for b in blunder_types if b.get("phase") == "endgame"])
        }
    }
    
    # Check if they repeated a known weakness
    # (This would require more sophisticated pattern matching - simplified for now)
    
    # 9. Generate coach message using LLM
    coach_message = await generate_coach_message(facts, llm_call_func)
    
    # 10. Determine overall sentiment
    sentiment = "neutral"
    if facts["comparison"]["is_improvement"]:
        sentiment = "proud"
    elif game_blunders > avg_blunders + 1:
        sentiment = "concerned"
    elif game_accuracy > 80:
        sentiment = "impressed"
    elif facts["performance"]["total_errors"] == 0:
        sentiment = "excellent"
    
    return {
        "has_review": True,
        "game_id": game_id,
        "facts": facts,
        "coach_message": coach_message,
        "sentiment": sentiment,
        "quick_stats": {
            "accuracy": facts["performance"]["accuracy"],
            "accuracy_trend": "up" if (facts["comparison"]["vs_avg_accuracy"] or 0) > 0 else "down" if (facts["comparison"]["vs_avg_accuracy"] or 0) < 0 else "same",
            "blunders": facts["performance"]["blunders"],
            "result": facts["game_info"]["result"],
            "opponent": facts["game_info"]["opponent"]
        }
    }


async def generate_coach_message(facts: Dict, llm_call_func) -> str:
    """
    Generate a personalized coach message based on the facts.
    
    GPT's role: Write like a supportive but honest chess coach.
    GPT does NOT analyze chess - we provide all the facts.
    """
    
    # Build context for GPT
    context_parts = []
    
    # Game info
    game = facts["game_info"]
    perf = facts["performance"]
    comp = facts["comparison"]
    opening = facts["opening_check"]
    
    context_parts.append(f"GAME: vs {game['opponent']}, played as {game['user_color']}, result: {game['result']}")
    context_parts.append(f"ACCURACY: {perf['accuracy']}% (their average is {comp['avg_accuracy']}%)")
    context_parts.append(f"BLUNDERS: {perf['blunders']} (their average is {comp['avg_blunders']})")
    context_parts.append(f"OPENING PLAYED: {opening['played']}")
    
    if opening['was_suggested'] is True:
        context_parts.append("OPENING CHECK: They played an opening we suggested!")
    elif opening['was_suggested'] is False and opening['suggested_openings']:
        context_parts.append(f"OPENING CHECK: They did NOT play our suggested openings ({', '.join(opening['suggested_openings'])})")
    
    if comp['is_improvement']:
        context_parts.append("TREND: This game was BETTER than their average")
    elif comp['vs_avg_accuracy'] and comp['vs_avg_accuracy'] < -5:
        context_parts.append("TREND: This game was WORSE than their average")
    
    phases = facts["phases"]
    if phases['opening_blunders'] > 0:
        context_parts.append(f"CONCERN: {phases['opening_blunders']} blunders in the opening")
    if phases['endgame_blunders'] > 0:
        context_parts.append(f"CONCERN: {phases['endgame_blunders']} blunders in the endgame")
    
    context_str = "\n".join(context_parts)
    
    prompt = f"""You are a personal chess coach reviewing your student's most recent game. You've been working with them, suggesting openings and helping them fix weaknesses.

FACTS ABOUT THIS GAME (these are accurate - do not contradict):
{context_str}

Write a 2-3 sentence personalized review. Be:
- SPECIFIC: Reference actual numbers and facts
- HONEST: Praise improvement, but note concerns
- SUPPORTIVE: Like a coach who believes in them
- ACTIONABLE: End with one thing to focus on next

Tone: Warm but direct, like a mentor. Not generic praise.

Examples of good openings:
- "78% accuracy against a tough opponent - that's solid work."
- "I noticed you went back to the Sicilian instead of the Italian we discussed..."
- "Zero blunders! That discipline is showing."

Write the review (no preamble):"""

    try:
        message = await llm_call_func(
            system_message="You are a supportive chess coach giving brief, specific feedback on a student's game.",
            user_message=prompt,
            model="gpt-4o-mini"
        )
        return message.strip()
    except Exception as e:
        logger.error(f"LLM call failed for coach review: {e}")
        # Fallback to template-based message
        if facts["comparison"]["is_improvement"]:
            return f"Good game! {perf['accuracy']}% accuracy is above your average. Keep up the focused play."
        elif perf["blunders"] == 0:
            return f"Clean game with no blunders! {perf['accuracy']}% accuracy shows your discipline is improving."
        else:
            return f"This one was a bit rough - {perf['blunders']} blunders brought your accuracy to {perf['accuracy']}%. Let's work on that pattern awareness."


def get_improvement_highlights(facts: Dict) -> List[Dict]:
    """Extract specific improvements to highlight."""
    highlights = []
    
    comp = facts["comparison"]
    perf = facts["performance"]
    
    if comp["vs_avg_accuracy"] and comp["vs_avg_accuracy"] > 5:
        highlights.append({
            "type": "accuracy_up",
            "text": f"Accuracy {comp['vs_avg_accuracy']:+.1f}% vs your average",
            "positive": True
        })
    
    if comp["vs_avg_blunders"] and comp["vs_avg_blunders"] > 0:
        highlights.append({
            "type": "fewer_blunders",
            "text": f"{comp['vs_avg_blunders']:.1f} fewer blunders than usual",
            "positive": True
        })
    
    if perf["blunders"] == 0:
        highlights.append({
            "type": "clean_game",
            "text": "Zero blunders!",
            "positive": True
        })
    
    if facts["opening_check"]["was_suggested"]:
        highlights.append({
            "type": "followed_advice",
            "text": "Played a suggested opening",
            "positive": True
        })
    
    return highlights


def get_concern_areas(facts: Dict) -> List[Dict]:
    """Extract areas of concern to address."""
    concerns = []
    
    comp = facts["comparison"]
    perf = facts["performance"]
    phases = facts["phases"]
    
    if comp["vs_avg_accuracy"] and comp["vs_avg_accuracy"] < -10:
        concerns.append({
            "type": "accuracy_drop",
            "text": f"Accuracy dropped {abs(comp['vs_avg_accuracy']):.1f}% below average",
            "severity": "high"
        })
    
    if perf["blunders"] >= 3:
        concerns.append({
            "type": "many_blunders",
            "text": f"{perf['blunders']} blunders in one game",
            "severity": "high"
        })
    
    if phases["opening_blunders"] >= 2:
        concerns.append({
            "type": "opening_issues",
            "text": f"Opening phase needs work ({phases['opening_blunders']} blunders)",
            "severity": "medium"
        })
    
    if phases["endgame_blunders"] >= 2:
        concerns.append({
            "type": "endgame_issues",
            "text": f"Endgame technique needs practice ({phases['endgame_blunders']} blunders)",
            "severity": "medium"
        })
    
    return concerns
