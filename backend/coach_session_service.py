"""
Coach Session Service - Tracks play sessions for ritual-based coaching
"""

from datetime import datetime, timezone, timedelta
from typing import Dict, Optional
import logging

# Import centralized config
from config import PLAY_SESSION_LOOKBACK_HOURS

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
    
    # Get user doc for sync
    user_doc = await db.users.find_one({"user_id": user_id}, {"_id": 0})
    if user_doc:
        await sync_user_games(db, user_id, user_doc)
    
    # Find the most recent game after session start
    if started_at:
        try:
            start_dt = datetime.fromisoformat(started_at.replace('Z', '+00:00'))
        except:
            start_dt = datetime.now(timezone.utc) - timedelta(hours=2)
    else:
        start_dt = datetime.now(timezone.utc) - timedelta(hours=2)
    
    # Look for the most recent game (sorted by imported_at descending)
    recent_game = await db.games.find_one(
        {
            "user_id": user_id,
            "platform": {"$regex": platform, "$options": "i"}
        },
        {"_id": 0, "game_id": 1, "imported_at": 1, "pgn": 1, "result": 1, 
         "termination": 1, "user_color": 1, "user_result": 1},
        sort=[("imported_at", -1)]
    )
    
    if not recent_game:
        return {
            "status": "no_game",
            "message": "No completed game detected yet. Keep playing!"
        }
    
    # Extract opponent from PGN
    opponent = "Opponent"
    user_color = recent_game.get("user_color", "white")
    pgn = recent_game.get("pgn", "")
    if pgn:
        import re
        white_match = re.search(r'\[White "([^"]+)"\]', pgn)
        black_match = re.search(r'\[Black "([^"]+)"\]', pgn)
        if white_match and black_match:
            opponent = black_match.group(1) if user_color == "white" else white_match.group(1)
    
    game_id = recent_game.get("game_id")
    
    # Check if already analyzed
    existing_analysis = await db.game_analyses.find_one(
        {"game_id": game_id},
        {"_id": 0, "game_id": 1}
    )
    
    if existing_analysis:
        # Get the actual analysis to show real feedback
        full_analysis = await db.game_analyses.find_one(
            {"game_id": game_id},
            {"_id": 0, "blunders": 1, "mistakes": 1, "best_moves": 1, 
             "identified_weaknesses": 1, "commentary": 1}
        )
        
        # Get user's dominant habit to check if repeated
        profile = await db.player_profiles.find_one(
            {"user_id": user_id},
            {"_id": 0, "top_weaknesses": 1}
        )
        
        dominant_habit = None
        if profile and profile.get("top_weaknesses"):
            w = profile["top_weaknesses"][0]
            dominant_habit = w.get("subcategory", str(w)) if isinstance(w, dict) else str(w)
        
        # Build real feedback
        feedback = _build_game_feedback(full_analysis, dominant_habit, recent_game)
        
        return {
            "status": "already_analyzed",
            "message": feedback["message"],
            "game_id": game_id,
            "opponent": opponent,
            "result": recent_game.get("result"),
            "feedback": feedback
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
        "message": "Okay, let me take a look at this one...",
        "game_id": game_id,
        "opponent": opponent,
        "result": recent_game.get("result")
    }


def _build_game_feedback(analysis: Dict, dominant_habit: str, game: Dict) -> Dict:
    """Build real feedback based on game analysis"""
    if not analysis:
        return {
            "type": "neutral",
            "message": "I've looked at your game.",
            "detail": None
        }
    
    blunders = analysis.get("blunders", 0)
    mistakes = analysis.get("mistakes", 0)
    best_moves = analysis.get("best_moves", 0)
    result = game.get("result", "")
    opponent = game.get("opponent", "your opponent")
    
    # Check if the dominant habit appeared in this game
    repeated_habit = False
    weaknesses = analysis.get("identified_weaknesses", [])
    if dominant_habit and weaknesses:
        for w in weaknesses:
            w_name = w.get("subcategory", str(w)) if isinstance(w, dict) else str(w)
            if dominant_habit.lower() in w_name.lower():
                repeated_habit = True
                break
    
    # Determine win/loss
    won = "1-0" in result or "won" in result.lower()
    lost = "0-1" in result or "lost" in result.lower()
    draw = "1/2" in result or "draw" in result.lower()
    
    # Build feedback message
    if blunders == 0:
        # No blunders - great!
        if mistakes <= 1:
            if won:
                message = "Nice win! Clean game with no blunders."
                feedback_type = "excellent"
            elif draw:
                message = "Solid draw. No blunders — well played."
                feedback_type = "good"
            else:
                message = "No blunders this time. The loss wasn't about big mistakes."
                feedback_type = "okay"
            detail = "Your focus is paying off."
        else:
            # No blunders but multiple mistakes
            if won:
                message = "You won! A few inaccuracies, but no blunders. Good discipline."
                feedback_type = "good"
            else:
                message = "No blunders — that's progress. A few mistakes to learn from."
                feedback_type = "okay"
            detail = "The big errors are under control. Now we refine."
        
    elif blunders == 1:
        if repeated_habit:
            message = f"One blunder — and it was the same pattern: {dominant_habit.replace('_', ' ')}."
            feedback_type = "repeated"
            detail = "This is exactly what we're working on. Let's review it."
        else:
            message = "One blunder slipped through, but it's not your usual pattern."
            feedback_type = "okay"
            detail = "Progress on your main habit. New puzzle incoming."
            
    else:
        # Multiple blunders
        if repeated_habit:
            message = f"{blunders} blunders, including your usual pattern: {dominant_habit.replace('_', ' ')}."
            feedback_type = "needs_work"
            detail = "Let's slow down and work through this together."
        else:
            message = f"Tough game — {blunders} blunders. But not your dominant habit."
            feedback_type = "okay"
            detail = "Bad day at the office. Tomorrow we go again."
    
    return {
        "type": feedback_type,
        "message": message,
        "detail": detail,
        "stats": {
            "blunders": blunders,
            "mistakes": mistakes,
            "best_moves": best_moves,
            "repeated_habit": repeated_habit
        }
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
