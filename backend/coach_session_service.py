"""
Coach Session Service - Tracks play sessions for ritual-based coaching
"""

from datetime import datetime, timezone, timedelta
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


async def start_play_session(db, user_id: str, platform: str) -> Dict:
    """
    Called when user taps "Go Play. I'll watch this game."
    Stores session start time for later game detection.
    """
    session = {
        "user_id": user_id,
        "platform": platform,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "active": True,
        "game_detected": False,
        "game_id": None
    }
    
    # Upsert - only one active session per user
    await db.coach_sessions.update_one(
        {"user_id": user_id, "active": True},
        {"$set": session},
        upsert=True
    )
    
    return {"status": "session_started", "message": "Go play. I'll be watching."}


async def end_play_session(db, user_id: str) -> Dict:
    """
    Called when user taps "Done Playing"
    Finds the latest completed game since session start and queues it for analysis.
    """
    # Get active session
    session = await db.coach_sessions.find_one(
        {"user_id": user_id, "active": True},
        {"_id": 0}
    )
    
    if not session:
        return {
            "status": "no_session",
            "message": "No active play session found."
        }
    
    started_at = session.get("started_at")
    platform = session.get("platform", "chess.com")
    
    # Mark session as ended
    await db.coach_sessions.update_one(
        {"user_id": user_id, "active": True},
        {"$set": {"active": False, "ended_at": datetime.now(timezone.utc).isoformat()}}
    )
    
    # Find games imported after session start
    # First, trigger a quick sync to get latest games
    from journey_service import sync_user_games
    await sync_user_games(db, user_id)
    
    # Find the most recent game after session start
    if started_at:
        try:
            start_dt = datetime.fromisoformat(started_at.replace('Z', '+00:00'))
        except:
            start_dt = datetime.now(timezone.utc) - timedelta(hours=2)
    else:
        start_dt = datetime.now(timezone.utc) - timedelta(hours=2)
    
    # Look for games that ended after session started
    recent_game = await db.games.find_one(
        {
            "user_id": user_id,
            "platform": {"$regex": platform, "$options": "i"}
        },
        {"_id": 0, "game_id": 1, "date": 1, "opponent": 1, "result": 1},
        sort=[("date", -1)]
    )
    
    if not recent_game:
        return {
            "status": "no_game",
            "message": "No completed game detected yet. Keep playing!"
        }
    
    game_id = recent_game.get("game_id")
    
    # Check if already analyzed
    existing_analysis = await db.game_analyses.find_one(
        {"game_id": game_id},
        {"_id": 0, "game_id": 1}
    )
    
    if existing_analysis:
        return {
            "status": "already_analyzed",
            "message": "Your last game has been reviewed.",
            "game_id": game_id
        }
    
    # Queue for priority analysis
    await db.analysis_queue.update_one(
        {"game_id": game_id},
        {
            "$set": {
                "user_id": user_id,
                "game_id": game_id,
                "priority": True,
                "queued_at": datetime.now(timezone.utc).isoformat(),
                "status": "pending"
            }
        },
        upsert=True
    )
    
    # Trigger analysis in background (non-blocking)
    try:
        from journey_service import auto_analyze_game
        import asyncio
        asyncio.create_task(analyze_priority_game(db, user_id, game_id))
    except Exception as e:
        logger.error(f"Failed to start priority analysis: {e}")
    
    return {
        "status": "analyzing",
        "message": "Your game is being reviewed.",
        "game_id": game_id,
        "opponent": recent_game.get("opponent"),
        "result": recent_game.get("result")
    }


async def analyze_priority_game(db, user_id: str, game_id: str):
    """Background task to analyze a priority game"""
    try:
        from journey_service import auto_analyze_game
        await auto_analyze_game(db, user_id, game_id)
        
        # Update queue status
        await db.analysis_queue.update_one(
            {"game_id": game_id},
            {"$set": {"status": "completed"}}
        )
    except Exception as e:
        logger.error(f"Priority analysis failed for {game_id}: {e}")
        await db.analysis_queue.update_one(
            {"game_id": game_id},
            {"$set": {"status": "failed", "error": str(e)}}
        )


async def get_active_session(db, user_id: str) -> Optional[Dict]:
    """Check if user has an active play session"""
    session = await db.coach_sessions.find_one(
        {"user_id": user_id, "active": True},
        {"_id": 0}
    )
    return session


async def get_session_status(db, user_id: str) -> Dict:
    """Get the current session status for UI"""
    session = await db.coach_sessions.find_one(
        {"user_id": user_id},
        {"_id": 0},
        sort=[("started_at", -1)]
    )
    
    if not session:
        return {"has_session": False, "status": "none"}
    
    if session.get("active"):
        return {
            "has_session": True,
            "status": "playing",
            "started_at": session.get("started_at"),
            "platform": session.get("platform")
        }
    
    # Check if analysis is pending
    if session.get("game_id"):
        queue_item = await db.analysis_queue.find_one(
            {"game_id": session["game_id"]},
            {"_id": 0, "status": 1}
        )
        if queue_item:
            return {
                "has_session": True,
                "status": queue_item.get("status", "pending"),
                "game_id": session.get("game_id")
            }
    
    return {"has_session": False, "status": "none"}
