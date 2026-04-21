"""
Training Routes
===============

Handles all training-related functionality including:
- Spaced repetition cards and sessions
- Puzzle training
- Weakness-based prescribed training
- Opening training
- Trick/trap training
- Progress tracking

This is a large module - ~60 endpoints covering all training features.
"""

from fastapi import APIRouter, HTTPException, Depends, Body
from pydantic import BaseModel
from typing import Optional, List, Dict
import logging

logger = logging.getLogger(__name__)

# Create router for training endpoints
router = APIRouter(prefix="/training", tags=["Training"])

# Database reference - will be set by server.py
db = None

def set_db(database):
    """Set the database reference for training routes"""
    global db
    db = database


# Import User model and get_current_user from auth routes
from routes.auth import User, get_current_user

# Import training services (from mistake_card_service)
from mistake_card_service import (
    get_training_session,
    get_due_cards,
    get_card_by_id,
    record_card_attempt,
    generate_why_question,
    get_user_habit_progress,
    get_training_stats,
    set_active_habit,
    HABIT_DEFINITIONS
)


# ==================== MODELS ====================

class CardAttemptRequest(BaseModel):
    card_id: str
    correct: bool


class SetActiveHabitRequest(BaseModel):
    habit_key: str


class PuzzleAttemptRequest(BaseModel):
    puzzle_id: str
    correct: bool
    time_taken_ms: Optional[int] = None
    moves_tried: Optional[List[str]] = []


# ==================== CORE SESSION ENDPOINTS ====================

@router.get("/session")
async def get_training_session_endpoint(user: User = Depends(get_current_user)):
    """
    Get the current training session.
    Returns either:
    - Post-Game Debrief (if user just played a game)
    - Daily Training (cards due for review)
    - All Caught Up (no cards due)
    """
    global db
    session = await get_training_session(db, user.user_id)
    return session


@router.get("/due-cards")
async def get_due_cards_endpoint(user: User = Depends(get_current_user), limit: int = 5):
    """Get cards due for review today."""
    global db
    cards = await get_due_cards(db, user.user_id, limit=limit)
    return {"cards": cards, "count": len(cards)}


@router.get("/card/{card_id}")
async def get_training_card(card_id: str, user: User = Depends(get_current_user)):
    """Get a specific training card."""
    global db
    card = await get_card_by_id(db, card_id, user.user_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    return card


@router.post("/attempt")
async def record_training_attempt(req: CardAttemptRequest, user: User = Depends(get_current_user)):
    """
    Record an attempt on a training card.
    Updates spaced repetition schedule based on correctness.
    """
    global db
    result = await record_card_attempt(db, req.card_id, user.user_id, req.correct)
    if result.get("error"):
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.get("/card/{card_id}/why")
async def get_why_question_for_card(card_id: str, user: User = Depends(get_current_user)):
    """
    Get a Socratic "Why is this move better?" question for a card.
    Used after the user answers correctly to deepen understanding.
    """
    global db
    card = await get_card_by_id(db, card_id, user.user_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    
    why_data = await generate_why_question(db, card)
    return why_data


@router.get("/progress")
async def get_training_progress(user: User = Depends(get_current_user)):
    """Get user's habit mastery progress."""
    global db
    progress = await get_user_habit_progress(db, user.user_id)
    stats = await get_training_stats(db, user.user_id)
    return {
        "habits": progress,
        "stats": stats
    }


@router.post("/set-habit")
async def set_training_habit(req: SetActiveHabitRequest, user: User = Depends(get_current_user)):
    """Manually set the active habit to focus on."""
    global db
    result = await set_active_habit(db, user.user_id, req.habit_key)
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.get("/habits")
async def get_available_habits(user: User = Depends(get_current_user)):
    """Get all available habit definitions."""
    return {"habits": HABIT_DEFINITIONS}


# ==================== PRESCRIBED TRAINING ====================

@router.get("/prescribed/{weakness}")
async def get_prescribed_training_endpoint(
    weakness: str,
    num_puzzles: int = 5,
    user: User = Depends(get_current_user)
):
    """
    Get puzzles prescribed for a specific weakness.

    Pass `current` to use whatever the curriculum brain has set as
    coach_memory.learning.current_focus (keeps every screen aligned).

    This is the IMPROVEMENT engine:
    - Takes diagnosed weakness (e.g., "missed_threat")
    - Returns puzzles with COACHING context
    - Includes puzzles from user's own games!
    """
    global db
    from services.coaching_puzzle_service import CoachingPuzzleService
    from services.focus_resolver import get_active_focus

    # If client asks for `current`, resolve to the coach's active focus
    resolved_focus = None
    if weakness in ("current", "auto", "focus"):
        resolved_focus = await get_active_focus(db, user.user_id, top_problems=None)
        if resolved_focus and resolved_focus.get("gap"):
            weakness = resolved_focus["gap"]
        else:
            # No focus known yet — safe default for beginners
            weakness = "piece_safety"

    puzzle_service = CoachingPuzzleService(db)

    # Auto-backfill community_puzzles from user's own games if they have none
    # yet. This used to only fire on /pattern-puzzles but since the training
    # surface consolidated, it needs to be here too. Safe to run on every
    # call — cheap no-op when puzzles already exist.
    try:
        from services.puzzle_extraction_service import backfill_puzzles_for_user
        own_count = await db.community_puzzles.count_documents(
            {"shared_by": user.user_id}
        )
        if own_count == 0:
            await backfill_puzzles_for_user(db, user.user_id)
    except Exception as _backfill_err:
        # Non-fatal: if backfill fails, still serve whatever puzzles we can.
        logger.debug(f"Auto-backfill skipped for {user.user_id}: {_backfill_err}")

    # Get user's rating for difficulty calibration
    player_profile = await db.player_profiles.find_one({"user_id": user.user_id})
    user_rating = 1200
    if player_profile:
        lichess_rating = player_profile.get("lichess_stats", {}).get("rating", 0)
        chesscom_rating = player_profile.get("chesscom_stats", {}).get("rating", 0)
        user_rating = max(lichess_rating, chesscom_rating, 1200)

    # Set rating range for puzzles (user rating +/- 200)
    rating_range = (max(600, user_rating - 200), user_rating + 200)

    result = await puzzle_service.get_prescribed_training(
        user_id=user.user_id,
        weakness_pattern=weakness,
        num_puzzles=num_puzzles,
        rating_range=rating_range
    )

    if resolved_focus:
        result["active_focus"] = resolved_focus

    return result


@router.post("/puzzle-attempt")
async def record_puzzle_attempt_endpoint(
    request: Dict = Body(...),
    user: User = Depends(get_current_user)
):
    """Record an attempt on a training puzzle."""
    global db
    from datetime import datetime, timezone
    
    puzzle_id = request.get("puzzle_id")
    correct = request.get("correct", False)
    time_taken_ms = request.get("time_taken_ms")
    moves_tried = request.get("moves_tried", [])
    weakness_type = request.get("weakness_type", "unknown")
    
    # Store the attempt
    attempt = {
        "user_id": user.user_id,
        "puzzle_id": puzzle_id,
        "correct": correct,
        "time_taken_ms": time_taken_ms,
        "moves_tried": moves_tried,
        "weakness_type": weakness_type,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.puzzle_attempts.insert_one(attempt)
    
    return {
        "success": True,
        "correct": correct,
        "message": "Attempt recorded"
    }


# ==================== ONE-MOVE BLUNDERS ====================

@router.get("/one-move-blunders")
async def get_one_move_blunders(user: User = Depends(get_current_user)):
    """
    Get one-move blunders as training puzzles.
    These are positions where you made a move that allowed immediate tactics.
    """
    global db
    
    # Get all analyzed games with stockfish data
    analyses = await db.game_analyses.find(
        {"user_id": user.user_id},
        {"_id": 0, "game_id": 1, "stockfish_analysis": 1}
    ).to_list(100)
    
    # Get solved puzzle IDs
    solved = await db.puzzle_attempts.find(
        {"user_id": user.user_id, "correct": True},
        {"puzzle_id": 1}
    ).to_list(500)
    solved_puzzle_ids = {s["puzzle_id"] for s in solved}
    
    one_move_blunders = []
    for analysis in analyses:
        sf = analysis.get("stockfish_analysis", {})
        evals = sf.get("move_evaluations", [])
        
        for m in evals:
            # Looking for moves where opponent has immediate tactic after
            cp_loss = abs(m.get("cp_loss", 0))
            pv = m.get("pv_after_best", [])
            
            # One-move blunder = big loss where opponent's reply is decisive
            if cp_loss >= 200 and len(pv) >= 1:
                puzzle_id = f"{analysis['game_id']}_{m.get('move_number')}"
                
                # Skip already solved
                if puzzle_id in solved_puzzle_ids:
                    continue
                
                one_move_blunders.append({
                    "puzzle_id": puzzle_id,
                    "game_id": analysis["game_id"],
                    "fen": m.get("fen_before", ""),
                    "your_move": m.get("move", ""),
                    "solution": [m.get("best_move", "")],
                    "cp_loss": cp_loss,
                    "move_number": m.get("move_number"),
                    "threat": m.get("threat", ""),
                    "source": "your_game"
                })
    
    # Sort by cp_loss (worst blunders first)
    one_move_blunders.sort(key=lambda x: abs(x["cp_loss"]), reverse=True)
    
    return {
        "puzzles": one_move_blunders[:30],
        "total": len(one_move_blunders),
        "solved_count": len(solved_puzzle_ids),
        "source": "stockfish_analysis"
    }


# ==================== DATA-DRIVEN TRAINING ====================

@router.get("/data-driven")
async def get_data_driven_training(user: User = Depends(get_current_user)):
    """
    Get personalized training based on user's actual game weaknesses.
    This analyzes recent games to find recurring patterns.
    """
    global db
    
    # Get recent analyses
    analyses = await db.game_analyses.find(
        {"user_id": user.user_id},
        {"_id": 0}
    ).sort("created_at", -1).limit(20).to_list(20)
    
    # Aggregate weakness patterns
    weakness_counts = {}
    for analysis in analyses:
        for blunder in analysis.get("blunders", []):
            category = blunder.get("mistake_category", "unknown")
            weakness_counts[category] = weakness_counts.get(category, 0) + 1
    
    # Sort by frequency
    sorted_weaknesses = sorted(
        weakness_counts.items(), 
        key=lambda x: x[1], 
        reverse=True
    )
    
    # Build training recommendations
    recommendations = []
    for weakness, count in sorted_weaknesses[:5]:
        recommendations.append({
            "weakness": weakness,
            "occurrences": count,
            "training_type": "prescribed",
            "priority": "high" if count >= 3 else "medium"
        })
    
    return {
        "recommendations": recommendations,
        "games_analyzed": len(analyses),
        "total_weaknesses_found": len(weakness_counts)
    }


# ==================== WEEKLY PLAN ====================

@router.get("/weekly-plan")
async def get_weekly_training_plan(user: User = Depends(get_current_user)):
    """
    Get personalized weekly training plan based on weaknesses.
    """
    global db
    
    # Get user's top weaknesses
    user_doc = await db.users.find_one({"user_id": user.user_id})
    weaknesses = user_doc.get("top_weaknesses", []) if user_doc else []
    
    # Get recent training activity
    recent_attempts = await db.puzzle_attempts.find(
        {"user_id": user.user_id},
        {"_id": 0}
    ).sort("created_at", -1).limit(50).to_list(50)
    
    # Calculate accuracy per weakness
    weakness_stats = {}
    for attempt in recent_attempts:
        weakness = attempt.get("weakness_type", "unknown")
        if weakness not in weakness_stats:
            weakness_stats[weakness] = {"correct": 0, "total": 0}
        weakness_stats[weakness]["total"] += 1
        if attempt.get("correct"):
            weakness_stats[weakness]["correct"] += 1
    
    # Build weekly plan
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    plan = []
    
    for i, day in enumerate(days):
        if i < len(weaknesses):
            weakness = weaknesses[i % len(weaknesses)] if weaknesses else "tactics"
            stats = weakness_stats.get(weakness, {"correct": 0, "total": 0})
            accuracy = (stats["correct"] / stats["total"] * 100) if stats["total"] > 0 else 0
            
            plan.append({
                "day": day,
                "focus": weakness,
                "puzzles_target": 5,
                "current_accuracy": round(accuracy, 1),
                "completed": False
            })
        else:
            plan.append({
                "day": day,
                "focus": "review",
                "puzzles_target": 3,
                "completed": False
            })
    
    return {
        "plan": plan,
        "weaknesses": weaknesses,
        "stats": weakness_stats
    }
