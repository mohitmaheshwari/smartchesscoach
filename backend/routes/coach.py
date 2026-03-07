"""
Coach Routes
============

Handles all coach-related functionality including:
- Coach state and analytics
- Play with Coach mode
- Deep session management
- Coach memory and summaries
- Maturity tracking
- Focus lock

This is a large module covering the AI coaching features.
"""

from fastapi import APIRouter, HTTPException, Depends, Body
from pydantic import BaseModel
from typing import Optional, List, Dict
from datetime import datetime, timezone
import logging
import uuid

logger = logging.getLogger(__name__)

# Create router for coach endpoints
router = APIRouter(prefix="/coach", tags=["Coach"])

# Database reference - will be set by server.py
db = None

# LLM function reference
call_llm = None

def set_db(database):
    """Set the database reference for coach routes"""
    global db
    db = database

def set_llm(llm_func):
    """Set the LLM function reference"""
    global call_llm
    call_llm = llm_func


# Import User model and get_current_user from auth routes
from routes.auth import User, get_current_user


# ==================== MODELS ====================

class CoachMoveRequest(BaseModel):
    session_id: str
    move: str
    thinking_time_ms: Optional[int] = None


class CoachFeedbackRequest(BaseModel):
    session_id: str
    move_number: int
    feedback_type: str  # helpful, not_helpful, wrong
    comment: Optional[str] = ""


class FocusLockActivateRequest(BaseModel):
    focus_type: str  # e.g., "piece_safety", "tactics"
    duration_hours: int = 24


# ==================== CORE STATE ENDPOINTS ====================

@router.get("/state")
async def get_coach_state(user: User = Depends(get_current_user)):
    """
    Get current coach state including:
    - Active focus area
    - Session status
    - Maturity level
    """
    global db
    
    user_doc = await db.users.find_one({"user_id": user.user_id})
    if not user_doc:
        return {"state": "new_user", "focus": None}
    
    # Get active focus
    focus_lock = await db.focus_locks.find_one({
        "user_id": user.user_id,
        "active": True
    })
    
    # Get maturity
    maturity = await db.coach_maturity.find_one({"user_id": user.user_id})
    
    return {
        "state": "active",
        "focus": focus_lock.get("focus_type") if focus_lock else None,
        "maturity_level": maturity.get("level", 1) if maturity else 1,
        "rating": user_doc.get("assessed_rating", 1200)
    }


@router.get("/today")
async def get_coach_today(user: User = Depends(get_current_user)):
    """Get coach's daily briefing."""
    global db
    from datetime import date
    
    today = date.today().isoformat()
    
    # Get today's stats
    games_today = await db.games.count_documents({
        "user_id": user.user_id,
        "imported_at": {"$regex": f"^{today}"}
    })
    
    reflections_today = await db.reflections.count_documents({
        "user_id": user.user_id,
        "created_at": {"$regex": f"^{today}"}
    })
    
    puzzles_today = await db.puzzle_attempts.count_documents({
        "user_id": user.user_id,
        "created_at": {"$regex": f"^{today}"}
    })
    
    return {
        "date": today,
        "games_played": games_today,
        "reflections_done": reflections_today,
        "puzzles_solved": puzzles_today,
        "message": "Keep up the good work!" if games_today > 0 else "Ready for some chess?"
    }


@router.get("/habits")
async def get_coach_habits(user: User = Depends(get_current_user)):
    """Get user's chess habits and patterns."""
    global db
    
    # Get habit data
    habits = await db.user_habits.find_one({"user_id": user.user_id})
    
    if not habits:
        return {"habits": [], "message": "Play more games to discover your habits"}
    
    return {
        "habits": habits.get("patterns", []),
        "last_updated": habits.get("updated_at")
    }


# ==================== MEMORY & SUMMARIES ====================

@router.get("/memory-summary")
async def get_memory_summary(user: User = Depends(get_current_user)):
    """
    Get coach's memory of the user - what patterns have been observed.
    """
    global db
    
    # Get recent analyses
    analyses = await db.game_analyses.find(
        {"user_id": user.user_id},
        {"_id": 0}
    ).sort("created_at", -1).limit(20).to_list(20)
    
    # Aggregate patterns
    patterns = {}
    for analysis in analyses:
        for blunder in analysis.get("blunders", []):
            category = blunder.get("mistake_category", "unknown")
            patterns[category] = patterns.get(category, 0) + 1
    
    # Sort by frequency
    sorted_patterns = sorted(patterns.items(), key=lambda x: x[1], reverse=True)
    
    return {
        "games_analyzed": len(analyses),
        "top_patterns": sorted_patterns[:5],
        "total_patterns": len(patterns)
    }


@router.get("/game-summary/{game_id}")
async def get_game_summary(game_id: str, user: User = Depends(get_current_user)):
    """Get coach's summary for a specific game."""
    global db
    
    analysis = await db.game_analyses.find_one({
        "game_id": game_id,
        "user_id": user.user_id
    }, {"_id": 0})
    
    if not analysis:
        raise HTTPException(status_code=404, detail="Game analysis not found")
    
    game = await db.games.find_one({
        "game_id": game_id,
        "user_id": user.user_id
    }, {"_id": 0})
    
    return {
        "game_id": game_id,
        "result": game.get("result") if game else "unknown",
        "blunders": analysis.get("blunders", 0),
        "mistakes": analysis.get("mistakes", 0),
        "accuracy": analysis.get("stockfish_analysis", {}).get("accuracy", 0),
        "lesson": analysis.get("lesson", {})
    }


@router.get("/last-game-summary")
async def get_last_game_summary(user: User = Depends(get_current_user)):
    """Get summary of the most recent game."""
    global db
    
    # Get most recent game
    game = await db.games.find_one(
        {"user_id": user.user_id},
        {"_id": 0}
    )
    
    if not game:
        return {"message": "No games found"}
    
    # Get analysis
    analysis = await db.game_analyses.find_one({
        "game_id": game["game_id"]
    }, {"_id": 0})
    
    return {
        "game_id": game["game_id"],
        "result": game.get("result"),
        "opponent": game.get("opponent_name", "Unknown"),
        "analysis_available": analysis is not None,
        "blunders": analysis.get("blunders", 0) if analysis else 0
    }


# ==================== MATURITY TRACKING ====================

@router.get("/maturity")
async def get_coach_maturity(user: User = Depends(get_current_user)):
    """Get user's coaching maturity level."""
    global db
    
    maturity = await db.coach_maturity.find_one({"user_id": user.user_id})
    
    if not maturity:
        return {
            "level": 1,
            "xp": 0,
            "next_level_xp": 100,
            "message": "Welcome! Let's start your chess journey."
        }
    
    return {
        "level": maturity.get("level", 1),
        "xp": maturity.get("xp", 0),
        "next_level_xp": maturity.get("next_level_xp", 100),
        "achievements": maturity.get("achievements", [])
    }


@router.post("/maturity/update")
async def update_coach_maturity(
    request: Dict = Body(...),
    user: User = Depends(get_current_user)
):
    """Update maturity based on activity."""
    global db
    
    xp_gained = request.get("xp", 10)
    activity = request.get("activity", "unknown")
    
    maturity = await db.coach_maturity.find_one({"user_id": user.user_id})
    
    if not maturity:
        maturity = {"user_id": user.user_id, "level": 1, "xp": 0, "next_level_xp": 100}
    
    new_xp = maturity.get("xp", 0) + xp_gained
    level = maturity.get("level", 1)
    next_level_xp = maturity.get("next_level_xp", 100)
    
    # Level up check
    leveled_up = False
    if new_xp >= next_level_xp:
        level += 1
        new_xp = new_xp - next_level_xp
        next_level_xp = int(next_level_xp * 1.5)
        leveled_up = True
    
    await db.coach_maturity.update_one(
        {"user_id": user.user_id},
        {"$set": {
            "level": level,
            "xp": new_xp,
            "next_level_xp": next_level_xp,
            "last_activity": activity,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }},
        upsert=True
    )
    
    return {
        "level": level,
        "xp": new_xp,
        "xp_gained": xp_gained,
        "leveled_up": leveled_up
    }


# ==================== FOCUS LOCK ====================

@router.get("/focus-lock")
async def get_focus_lock(user: User = Depends(get_current_user)):
    """Get current focus lock status."""
    global db
    
    lock = await db.focus_locks.find_one({
        "user_id": user.user_id,
        "active": True
    }, {"_id": 0})
    
    if not lock:
        return {"active": False, "focus_type": None}
    
    return {
        "active": True,
        "focus_type": lock.get("focus_type"),
        "started_at": lock.get("started_at"),
        "expires_at": lock.get("expires_at"),
        "puzzles_completed": lock.get("puzzles_completed", 0)
    }


@router.post("/focus-lock/activate")
async def activate_focus_lock(
    request: FocusLockActivateRequest,
    user: User = Depends(get_current_user)
):
    """Activate a focus lock on a specific weakness."""
    global db
    from datetime import timedelta
    
    now = datetime.now(timezone.utc)
    expires = now + timedelta(hours=request.duration_hours)
    
    lock = {
        "user_id": user.user_id,
        "focus_type": request.focus_type,
        "active": True,
        "started_at": now.isoformat(),
        "expires_at": expires.isoformat(),
        "puzzles_completed": 0
    }
    
    # Deactivate any existing locks
    await db.focus_locks.update_many(
        {"user_id": user.user_id, "active": True},
        {"$set": {"active": False}}
    )
    
    await db.focus_locks.insert_one(lock)
    
    return {
        "success": True,
        "focus_type": request.focus_type,
        "expires_at": expires.isoformat()
    }


@router.post("/focus-lock/deactivate")
async def deactivate_focus_lock(user: User = Depends(get_current_user)):
    """Deactivate current focus lock."""
    global db
    
    result = await db.focus_locks.update_many(
        {"user_id": user.user_id, "active": True},
        {"$set": {"active": False, "deactivated_at": datetime.now(timezone.utc).isoformat()}}
    )
    
    return {"success": True, "deactivated": result.modified_count}


# ==================== PLAY WITH COACH ====================

@router.post("/play/start")
async def start_play_session(
    request: Dict = Body(...),
    user: User = Depends(get_current_user)
):
    """Start a new Play with Coach session."""
    global db
    
    session_id = f"play_{uuid.uuid4().hex[:12]}"
    color = request.get("color", "white")
    time_control = request.get("time_control", "10+0")
    
    session = {
        "session_id": session_id,
        "user_id": user.user_id,
        "user_color": color,
        "time_control": time_control,
        "moves": [],
        "coach_comments": [],
        "started_at": datetime.now(timezone.utc).isoformat(),
        "status": "active"
    }
    
    await db.play_sessions.insert_one(session)
    
    return {
        "session_id": session_id,
        "user_color": color,
        "message": "Let's play! I'll give you hints as we go."
    }


@router.post("/play/move")
async def record_play_move(
    request: CoachMoveRequest,
    user: User = Depends(get_current_user)
):
    """Record a move in the Play with Coach session."""
    global db
    
    session = await db.play_sessions.find_one({
        "session_id": request.session_id,
        "user_id": user.user_id
    })
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    moves = session.get("moves", [])
    move_number = len(moves) + 1
    
    move_data = {
        "move_number": move_number,
        "move": request.move,
        "thinking_time_ms": request.thinking_time_ms,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    moves.append(move_data)
    
    await db.play_sessions.update_one(
        {"session_id": request.session_id},
        {"$set": {"moves": moves}}
    )
    
    # Generate coach comment (simplified - real implementation uses engine)
    comment = None
    if move_number % 5 == 0:
        comment = "Good progress! Keep thinking about piece activity."
    
    return {
        "move_number": move_number,
        "coach_comment": comment,
        "status": "ok"
    }


@router.get("/play/identity")
async def get_play_identity(user: User = Depends(get_current_user)):
    """Get user's playing identity based on past games."""
    global db
    
    # Get recent play sessions
    sessions = await db.play_sessions.find(
        {"user_id": user.user_id},
        {"_id": 0}
    ).sort("started_at", -1).limit(10).to_list(10)
    
    if not sessions:
        return {"identity": "explorer", "description": "Still discovering your style"}
    
    # Simple identity calculation
    total_moves = sum(len(s.get("moves", [])) for s in sessions)
    avg_thinking = 0
    
    return {
        "identity": "thoughtful" if avg_thinking > 5000 else "intuitive",
        "games_analyzed": len(sessions),
        "total_moves": total_moves
    }


@router.post("/play/feedback")
async def submit_play_feedback(
    request: CoachFeedbackRequest,
    user: User = Depends(get_current_user)
):
    """Submit feedback on coach's comments during play."""
    global db
    
    feedback = {
        "user_id": user.user_id,
        "session_id": request.session_id,
        "move_number": request.move_number,
        "feedback_type": request.feedback_type,
        "comment": request.comment,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.coach_feedback.insert_one(feedback)
    
    return {"success": True, "message": "Thank you for the feedback!"}


# ==================== ANALYTICS ====================

@router.get("/analytics/summary")
async def get_analytics_summary(user: User = Depends(get_current_user)):
    """Get summary analytics for the user."""
    global db
    
    # Count games
    total_games = await db.games.count_documents({"user_id": user.user_id})
    analyzed_games = await db.game_analyses.count_documents({"user_id": user.user_id})
    
    # Get reflection count
    reflections = await db.reflections.count_documents({"user_id": user.user_id})
    
    # Get puzzle stats
    puzzles_attempted = await db.puzzle_attempts.count_documents({"user_id": user.user_id})
    puzzles_correct = await db.puzzle_attempts.count_documents({
        "user_id": user.user_id,
        "correct": True
    })
    
    return {
        "total_games": total_games,
        "analyzed_games": analyzed_games,
        "reflections": reflections,
        "puzzles_attempted": puzzles_attempted,
        "puzzles_correct": puzzles_correct,
        "accuracy": round(puzzles_correct / puzzles_attempted * 100, 1) if puzzles_attempted > 0 else 0
    }


@router.get("/analytics/theme-history")
async def get_theme_history(user: User = Depends(get_current_user)):
    """Get history of themes/weaknesses worked on."""
    global db
    
    # Get puzzle attempts by weakness type
    pipeline = [
        {"$match": {"user_id": user.user_id}},
        {"$group": {
            "_id": "$weakness_type",
            "count": {"$sum": 1},
            "correct": {"$sum": {"$cond": ["$correct", 1, 0]}}
        }},
        {"$sort": {"count": -1}},
        {"$limit": 10}
    ]
    
    results = await db.puzzle_attempts.aggregate(pipeline).to_list(10)
    
    themes = []
    for r in results:
        if r["_id"]:
            themes.append({
                "theme": r["_id"],
                "attempts": r["count"],
                "correct": r["correct"],
                "accuracy": round(r["correct"] / r["count"] * 100, 1) if r["count"] > 0 else 0
            })
    
    return {"themes": themes}


# ==================== IDENTITY FORMATION LAYER ====================

@router.get("/identity/evolution")
async def get_identity_evolution(user: User = Depends(get_current_user)):
    """
    Get the user's identity evolution over time.
    
    Returns:
    - Current identity snapshot
    - Changes since last snapshot
    - Long-term trajectory
    - Milestones achieved
    """
    global db
    from services.identity_formation_service import compute_identity_evolution
    
    evolution = await compute_identity_evolution(db, user.user_id)
    return evolution


@router.get("/identity/snapshots")
async def get_identity_snapshots(
    limit: int = 12,
    user: User = Depends(get_current_user)
):
    """
    Get historical identity snapshots.
    
    Returns list of snapshots showing how identity evolved.
    """
    global db
    from services.identity_formation_service import get_snapshot_history
    
    snapshots = await get_snapshot_history(db, user.user_id, limit)
    
    return {
        "snapshots": [{
            "snapshot_id": s.get("snapshot_id"),
            "created_at": s.get("created_at"),
            "games_analyzed": s.get("games_analyzed"),
            "stability_label": s.get("stability_label"),
            "primary_leak": s.get("primary_leak"),
            "risk_style": s.get("risk_style"),
            "collapsed_summary": s.get("collapsed_summary"),
        } for s in snapshots],
        "count": len(snapshots)
    }


@router.post("/identity/snapshot")
async def create_manual_snapshot(user: User = Depends(get_current_user)):
    """
    Manually create an identity snapshot.
    
    Useful for marking a point in time (e.g., after completing training).
    """
    global db
    from player_identity_engine import compute_player_identity
    from services.identity_formation_service import create_identity_snapshot
    
    # Compute current identity
    identity = await compute_player_identity(db, user.user_id)
    
    if not identity.get("has_identity"):
        raise HTTPException(
            status_code=400, 
            detail="Not enough games to create identity snapshot"
        )
    
    # Create snapshot
    snapshot = await create_identity_snapshot(db, user.user_id, identity)
    
    return {
        "success": True,
        "snapshot_id": snapshot.get("snapshot_id"),
        "message": "Identity snapshot created"
    }


@router.get("/identity/trajectory")
async def get_identity_trajectory(user: User = Depends(get_current_user)):
    """
    Get the long-term trajectory of identity evolution.
    
    Shows overall direction: improving, declining, or stable.
    """
    global db
    from services.identity_formation_service import get_snapshot_history, compute_trajectory
    
    snapshots = await get_snapshot_history(db, user.user_id, limit=12)
    
    if len(snapshots) < 3:
        return {
            "has_trajectory": False,
            "reason": "Need at least 3 snapshots for trajectory analysis",
            "snapshots_available": len(snapshots)
        }
    
    trajectory = compute_trajectory(snapshots)
    
    return {
        "has_trajectory": True,
        **trajectory
    }


@router.get("/identity/insight")
async def get_identity_insight(user: User = Depends(get_current_user)):
    """
    Get a human-readable insight about identity evolution.
    
    Returns a single paragraph summarizing recent changes and trajectory.
    """
    global db
    from services.identity_formation_service import (
        compute_identity_evolution,
        generate_evolution_insight
    )
    
    evolution = await compute_identity_evolution(db, user.user_id)
    insight = generate_evolution_insight(evolution)
    
    return {
        "insight": insight,
        "has_evolution": evolution.get("has_evolution", False),
        "snapshot_count": evolution.get("snapshot_count", 0)
    }



@router.get("/identity/summary")
async def get_identity_summary(user: User = Depends(get_current_user)):
    """
    Get a summarized identity trajectory for UI display.
    
    Returns:
        - Current archetype (e.g., "The Calculating Attacker")
        - Stability and style labels
        - Trajectory direction
        - Comparative insight ("You used to be X, now you're Y")
        - Coaching moments
    """
    global db
    from services.identity_formation_service import get_identity_trajectory_summary
    
    summary = await get_identity_trajectory_summary(db, user.user_id)
    return summary

