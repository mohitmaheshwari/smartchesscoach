"""
Streak API Routes - P0: Carry-Forward + Mistake-Free Streak

Endpoints:
- GET /api/streak/status - Get current streak state for pre-game display
- POST /api/streak/update - Update streak after game analysis (called by worker)
- GET /api/streak/history - Get last 5 games with streak data
"""

from fastapi import APIRouter, HTTPException, Request
from typing import Dict, Any, Optional
from datetime import datetime, timezone
import logging

from services.mistake_streak_service import (
    update_streak_after_game,
    get_pregame_streak_data,
    get_postgame_streak_result,
    FOCUS_MISTAKE_TYPES
)

router = APIRouter(prefix="/streak", tags=["streak"])
logger = logging.getLogger(__name__)

# Database reference - will be set by server.py
db = None

def set_db(database):
    """Set the database reference for streak routes"""
    global db
    db = database


# =============================================================================
# GET STREAK STATUS (Pre-game carry-forward)
# =============================================================================

@router.get("/status")
async def get_streak_status(user_id: str) -> Dict[str, Any]:
    """
    Get current streak status for pre-game popup.
    
    This powers the "carry-forward" feature:
    - Shows current streak
    - Shows focus rule
    - Applies psychological pressure
    
    Returns:
        Streak state with messaging for UI
    """
    global db
    
    # Get user's streak data
    user = await db.users.find_one(
        {"user_id": user_id},
        {"_id": 0, "streak_data": 1}
    )
    
    if not user or not user.get("streak_data"):
        # Initialize default streak data
        default_streak = _get_default_streak_data()
        return get_pregame_streak_data(default_streak)
    
    return get_pregame_streak_data(user["streak_data"])


@router.get("/history")
async def get_streak_history(user_id: str) -> Dict[str, Any]:
    """
    Get detailed streak history (last 5 games).
    
    Returns:
        Full streak state with game history
    """
    global db
    
    user = await db.users.find_one(
        {"user_id": user_id},
        {"_id": 0, "streak_data": 1}
    )
    
    if not user or not user.get("streak_data"):
        return {
            "streak_data": _get_default_streak_data(),
            "focus_types": list(FOCUS_MISTAKE_TYPES.keys())
        }
    
    return {
        "streak_data": user["streak_data"],
        "focus_types": list(FOCUS_MISTAKE_TYPES.keys())
    }


# =============================================================================
# UPDATE STREAK (Called after game analysis)
# =============================================================================

@router.post("/update")
async def update_streak(request: Request) -> Dict[str, Any]:
    """
    Update streak after a game is analyzed.
    
    Called by the analysis worker after Stockfish analysis completes.
    
    Body:
        user_id: str
        game_id: str
        user_color: "white" | "black"
        stockfish_analysis: Dict (move evaluations)
    
    Returns:
        Updated streak state + post-game messaging
    """
    global db
    body = await request.json()
    
    user_id = body.get("user_id")
    game_id = body.get("game_id")
    user_color = body.get("user_color", "white")
    game_analysis = body.get("stockfish_analysis", body.get("analysis", {}))
    
    if not user_id or not game_id:
        raise HTTPException(status_code=400, detail="user_id and game_id required")
    
    # Get current streak data
    user = await db.users.find_one(
        {"user_id": user_id},
        {"_id": 0, "streak_data": 1}
    )
    
    streak_before = user.get("streak_data") if user else None
    if not streak_before:
        streak_before = _get_default_streak_data()
    
    # Update streak
    streak_after = update_streak_after_game(
        user_streak_data=streak_before,
        game_analysis=game_analysis,
        game_id=game_id,
        user_color=user_color
    )
    
    # Add updated_at to streak_data before saving
    streak_after["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    # Save to database
    await db.users.update_one(
        {"user_id": user_id},
        {
            "$set": {
                "streak_data": streak_after
            }
        },
        upsert=True
    )
    
    # Generate post-game result
    postgame_result = get_postgame_streak_result(streak_before, streak_after)
    
    logger.info(f"Streak updated for {user_id}: {postgame_result['result']}")
    
    return {
        "streak_data": streak_after,
        "postgame_result": postgame_result,
        "pregame_next": get_pregame_streak_data(streak_after)
    }


# =============================================================================
# SET FOCUS MISTAKE (Admin/user choice)
# =============================================================================

@router.post("/set-focus")
async def set_focus_mistake(request: Request) -> Dict[str, Any]:
    """
    Set the user's current focus mistake type.
    
    This determines what mistake the streak tracks.
    Typically set automatically after game analysis or by user choice.
    
    Body:
        user_id: str
        focus_type: str (e.g., "THREAT_VERIFICATION")
        reset_streak: bool (default False)
    """
    global db
    body = await request.json()
    
    user_id = body.get("user_id")
    focus_type = body.get("focus_type")
    reset_streak = body.get("reset_streak", False)
    
    if not user_id or not focus_type:
        raise HTTPException(status_code=400, detail="user_id and focus_type required")
    
    if focus_type not in FOCUS_MISTAKE_TYPES:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid focus_type. Valid types: {list(FOCUS_MISTAKE_TYPES.keys())}"
        )
    
    # Get current data
    user = await db.users.find_one(
        {"user_id": user_id},
        {"_id": 0, "streak_data": 1}
    )
    
    streak_data = user.get("streak_data") if user else _get_default_streak_data()
    
    # Update focus type
    streak_data["current_focus_mistake"] = focus_type
    
    # Optionally reset streak
    if reset_streak:
        streak_data["mistake_streak"] = {
            "current": 0,
            "best": streak_data.get("mistake_streak", {}).get("best", 0),  # Keep best
            "last_game_had_mistake": False,
            "streak_started_at": None
        }
        streak_data["last_5_games"] = []
    
    # Add updated_at to streak_data before saving
    streak_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    # Save
    await db.users.update_one(
        {"user_id": user_id},
        {
            "$set": {
                "streak_data": streak_data
            }
        },
        upsert=True
    )
    
    focus_info = FOCUS_MISTAKE_TYPES[focus_type]
    
    return {
        "success": True,
        "focus_type": focus_type,
        "focus_name": focus_info["name"],
        "focus_rule": focus_info["rule"],
        "streak_data": streak_data
    }


# =============================================================================
# GET FOCUS TYPES (For UI selection)
# =============================================================================

@router.get("/focus-types")
async def get_focus_types() -> Dict[str, Any]:
    """
    Get all available focus mistake types.
    
    For UI to display options when user wants to change focus.
    """
    return {
        "focus_types": [
            {
                "key": key,
                "name": info["name"],
                "short_name": info["short_name"],
                "description": info["description"],
                "rule": info["rule"]
            }
            for key, info in FOCUS_MISTAKE_TYPES.items()
        ]
    }


# =============================================================================
# HELPERS
# =============================================================================

def _get_default_streak_data() -> Dict[str, Any]:
    """Get default streak data for new users."""
    return {
        "current_focus_mistake": "THREAT_VERIFICATION",
        "mistake_streak": {
            "current": 0,
            "best": 0,
            "last_game_had_mistake": False,
            "streak_started_at": None
        },
        "mistake_trend": {
            "before_avg": None,
            "recent_avg": None,
            "improvement_pct": None,
            "baseline_locked": False
        },
        "last_5_games": []
    }
