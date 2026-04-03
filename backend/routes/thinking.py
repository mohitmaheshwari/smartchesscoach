"""
Thinking Coach & Thinking Score Routes
=======================================

Handles:
- Thought process walkthroughs
- Principle-based feedback
- Behavioral interventions
- Mindset prompts
- Pre-move checklists
- Thinking scores (get, calculate, history, recommendations)
- Opening principles
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import List, Optional, Dict
import logging

from routes.auth import get_current_user, User

logger = logging.getLogger(__name__)

# Create router for thinking coach endpoints
router = APIRouter(tags=["Thinking Coach"])

# Database reference - will be set by server.py
db = None

def set_db(database):
    """Set the database reference for thinking routes"""
    global db
    db = database


# ==================== PYDANTIC MODELS ====================

class ThoughtProcessRequest(BaseModel):
    fen: str
    best_move: str
    played_move: Optional[str] = None
    position_context: Optional[Dict] = None


class PrincipleBasedFeedbackRequest(BaseModel):
    mistake_type: str
    fen: str
    move_played: str
    best_move: str


class BehavioralInterventionRequest(BaseModel):
    behavioral_pattern: str
    examples: Optional[List[Dict]] = None


class MindsetPromptRequest(BaseModel):
    fen: str
    position_characteristics: Optional[Dict] = None


class PreMoveChecklistRequest(BaseModel):
    move_number: int
    has_castled: bool = False
    developed_pieces: int = 0
    player_weaknesses: Optional[List[str]] = None


# ==================== HELPER FUNCTIONS ====================

def _get_score_explanation(score: float) -> str:
    """Generate explanation for overall thinking score."""
    if score >= 90:
        return "Excellent! You're applying strong thinking habits consistently."
    elif score >= 80:
        return "Great thinking process. Focus on your weak areas to reach mastery."
    elif score >= 70:
        return "Good foundation. The thinking checklist will help you improve further."
    elif score >= 60:
        return "Room for improvement. Slow down and apply the thinking process on each move."
    else:
        return "Focus on the basics: check threats, verify moves, keep king safe."


# ==================== THINKING COACH ROUTES ====================

@router.post("/thinking-coach/walkthrough")
async def get_thought_process_walkthrough(req: ThoughtProcessRequest, user: User = Depends(get_current_user)):
    """
    Generate a step-by-step thought process walkthrough for a position.

    Shows HOW a strong player would think through this position.
    This is the core of the "Thinking Coach" feature.
    """
    from services.thinking_coach import generate_thought_process_walkthrough

    result = generate_thought_process_walkthrough(
        fen=req.fen,
        best_move=req.best_move,
        played_move=req.played_move,
        position_context=req.position_context
    )

    return result


@router.post("/thinking-coach/principle-feedback")
async def get_principle_based_feedback(req: PrincipleBasedFeedbackRequest, user: User = Depends(get_current_user)):
    """
    Connect a mistake to a fundamental chess principle.

    Instead of just "this was wrong", explains WHY and gives a thinking habit.
    """
    from services.thinking_coach import get_principle_based_feedback

    result = get_principle_based_feedback(
        mistake_type=req.mistake_type,
        fen=req.fen,
        move_played=req.move_played,
        best_move=req.best_move
    )

    return result


@router.post("/thinking-coach/behavioral-intervention")
async def get_behavioral_intervention(req: BehavioralInterventionRequest, user: User = Depends(get_current_user)):
    """
    Get a specific intervention for a diagnosed behavioral pattern.

    Returns actionable thinking habits to break bad patterns like hope_chess, impulsive_play, etc.
    """
    from services.thinking_coach import get_behavioral_intervention

    result = get_behavioral_intervention(
        behavioral_pattern=req.behavioral_pattern,
        examples=req.examples
    )

    return result


@router.post("/thinking-coach/mindset-prompt")
async def get_position_mindset_prompt(req: MindsetPromptRequest, user: User = Depends(get_current_user)):
    """
    Generate mindset prompts based on position characteristics.

    E.g., "This position has a weak back rank. What should you be looking for?"
    """
    from services.thinking_coach import get_position_mindset_prompt

    result = get_position_mindset_prompt(
        fen=req.fen,
        position_characteristics=req.position_characteristics
    )

    return result


@router.get("/thinking-coach/pre-move-checklist")
async def get_pre_move_checklist(
    move_number: int,
    has_castled: bool = False,
    developed_pieces: int = 0,
    user: User = Depends(get_current_user)
):
    """
    Get a pre-move checklist for the player based on current game state.

    Reinforces good thinking habits before each move.
    """
    from services.thinking_coach import get_pre_move_checklist

    # Get player's known weaknesses from identity
    player_weaknesses = []
    try:
        identity = await db.player_identities.find_one(
            {"user_id": user.user_id},
            {"_id": 0, "behavioral_patterns": 1}
        )
        if identity and identity.get("behavioral_patterns"):
            # Extract pattern names
            player_weaknesses = [p.get("pattern") for p in identity["behavioral_patterns"] if p.get("pattern")]
    except:
        pass

    result = get_pre_move_checklist(
        move_number=move_number,
        has_castled=has_castled,
        developed_pieces=developed_pieces,
        player_weaknesses=player_weaknesses
    )

    return {
        "checklist": result,
        "player_weaknesses": player_weaknesses
    }


# ==================== THINKING SCORE ROUTES ====================

@router.get("/thinking-score")
async def get_user_thinking_score(user: User = Depends(get_current_user)):
    """
    Get the user's overall thinking score and progress.

    The score is calculated from REAL game analysis data - it measures
    how well the player applies thinking habits based on their actual mistakes.
    """
    from services.thinking_score import calculate_thinking_progress, get_weakest_habits

    # Get or calculate thinking scores from recent games
    thinking_scores = await db.thinking_scores.find(
        {"user_id": user.user_id},
        {"_id": 0}
    ).sort("calculated_at", -1).limit(20).to_list(20)

    if not thinking_scores:
        # No scores calculated yet - try to calculate from existing analyses
        return {
            "has_data": False,
            "message": "No thinking scores calculated yet. Play and analyze some games first.",
            "overall_score": None,
            "progress": None,
            "recommendations": []
        }

    # Calculate progress from scores
    progress = calculate_thinking_progress(thinking_scores)

    # Get recommendations for weakest areas
    recommendations = get_weakest_habits(progress, top_n=2) if progress.get("has_enough_data") else []

    return {
        "has_data": True,
        "overall_score": progress.get("overall_score"),
        "overall_trend": progress.get("overall_trend"),
        "overall_change": progress.get("overall_change"),
        "habit_progress": progress.get("habit_progress", {}),
        "games_analyzed": progress.get("games_analyzed", 0),
        "recommendations": recommendations,
        "explanation": _get_score_explanation(progress.get("overall_score", 0))
    }


@router.post("/thinking-score/calculate/{game_id}")
async def calculate_game_thinking_score(game_id: str, user: User = Depends(get_current_user)):
    """
    Calculate thinking score for a specific game.

    This analyzes the game's move evaluations to determine which
    thinking habits were followed or violated.
    """
    from services.thinking_score import calculate_game_thinking_scores

    # Get the game analysis
    analysis = await db.game_analyses.find_one(
        {"game_id": game_id},
        {"_id": 0, "stockfish_analysis": 1, "game_id": 1}
    )

    if not analysis:
        return {"error": "Game analysis not found", "game_id": game_id}

    # Extract move_evaluations from stockfish_analysis
    stockfish_analysis = analysis.get("stockfish_analysis", {})
    move_evaluations = stockfish_analysis.get("move_evaluations", [])

    # Get user color for this game
    game = await db.games.find_one(
        {"game_id": game_id},
        {"_id": 0, "user_color": 1}
    )
    user_color = game.get("user_color", "white") if game else "white"

    # Build analysis dict for thinking score calculation
    analysis_for_score = {
        "game_id": game_id,
        "move_evaluations": move_evaluations,
        "critical_moments": []
    }

    # Calculate scores
    scores = calculate_game_thinking_scores(analysis_for_score, user_color)
    scores["user_id"] = user.user_id
    scores["game_id"] = game_id

    # Store the scores
    await db.thinking_scores.update_one(
        {"user_id": user.user_id, "game_id": game_id},
        {"$set": scores},
        upsert=True
    )

    return scores


@router.get("/thinking-score/history")
async def get_thinking_score_history(
    limit: int = 10,
    user: User = Depends(get_current_user)
):
    """
    Get thinking score history for recent games.

    Shows how scores have changed over time.
    """
    scores = await db.thinking_scores.find(
        {"user_id": user.user_id},
        {"_id": 0}
    ).sort("calculated_at", -1).limit(limit).to_list(limit)

    return {
        "scores": scores,
        "count": len(scores)
    }


@router.get("/thinking-score/recommendations")
async def get_thinking_recommendations(user: User = Depends(get_current_user)):
    """
    Get personalized thinking habit recommendations.

    Based on analysis of recent games, identifies the weakest
    thinking habits and provides actionable advice.
    """
    from services.thinking_score import calculate_thinking_progress, get_weakest_habits

    # Get recent thinking scores
    thinking_scores = await db.thinking_scores.find(
        {"user_id": user.user_id},
        {"_id": 0}
    ).sort("calculated_at", -1).limit(10).to_list(10)

    if len(thinking_scores) < 2:
        return {
            "has_data": False,
            "message": "Analyze more games to get personalized recommendations",
            "recommendations": [
                {
                    "habit": "general",
                    "habit_label": "Thinking Process",
                    "priority": "medium",
                    "recommendation": "Use the Pre-Move Checklist during your games to build good habits.",
                    "checklist_item": "Did I follow my thinking process?",
                    "icon": "🧠"
                }
            ]
        }

    progress = calculate_thinking_progress(thinking_scores)
    recommendations = get_weakest_habits(progress, top_n=3)

    return {
        "has_data": True,
        "overall_score": progress.get("overall_score"),
        "recommendations": recommendations
    }


@router.get("/principles/opening")
async def get_opening_principles():
    """
    Get all opening principles with their teachings.

    This is the "curriculum" - what a player needs to learn
    to improve their opening play.
    """
    from services.opening_fundamentals_checker import get_all_principles
    return {
        "principles": get_all_principles(),
        "recommendation": "Focus on one principle at a time. Master it before moving to the next."
    }
