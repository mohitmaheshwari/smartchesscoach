"""
Missions Routes
===============

Handles daily missions, mission sessions, steps, and completion.

Endpoints:
- GET /missions/today - Get or generate today's mission
- POST /missions/{mission_id}/start - Start a mission session
- GET /missions/{mission_id}/positions - Get drill positions for mission
- POST /missions/generate-fix - Generate a fix-it mission for a game
- POST /missions/{mission_id}/step - Record a step in mission session
- POST /missions/{mission_id}/complete - Complete a mission
- GET /missions/history - Get mission history
- GET /missions/focus-mastery - Get focus mastery data
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Dict, Optional
from datetime import datetime, timezone
import logging
import uuid

logger = logging.getLogger(__name__)

# Create router for missions endpoints
router = APIRouter(prefix="/missions", tags=["Missions"])

# Database reference - will be set by server.py
db = None
# Mission service functions - will be set by server.py
_generate_daily_mission = None
_start_mission = None
_complete_mission = None
_extract_drill_positions = None
_get_sample_drill_positions = None
_PATTERN_FOCUS_MAP = None
_RewardEventType = None
_get_reward_message = None

def set_db(database):
    """Set the database reference for missions routes"""
    global db
    db = database

def set_mission_services(
    generate_daily_mission_fn,
    start_mission_fn,
    complete_mission_fn,
    extract_drill_positions_fn,
    get_sample_drill_positions_fn,
    pattern_focus_map,
    reward_event_type,
    get_reward_message_fn
):
    """Set mission service functions"""
    global _generate_daily_mission, _start_mission, _complete_mission
    global _extract_drill_positions, _get_sample_drill_positions
    global _PATTERN_FOCUS_MAP, _RewardEventType, _get_reward_message
    
    _generate_daily_mission = generate_daily_mission_fn
    _start_mission = start_mission_fn
    _complete_mission = complete_mission_fn
    _extract_drill_positions = extract_drill_positions_fn
    _get_sample_drill_positions = get_sample_drill_positions_fn
    _PATTERN_FOCUS_MAP = pattern_focus_map
    _RewardEventType = reward_event_type
    _get_reward_message = get_reward_message_fn

# Import User model and get_current_user from auth routes
from routes.auth import User, get_current_user


# ==================== MODELS ====================

class MissionStepRequest(BaseModel):
    """Request for recording a mission step"""
    step_type: str
    payload: Dict = {}

class MissionCompleteRequest(BaseModel):
    """Request for completing a mission"""
    score: Dict


# ==================== ENDPOINTS ====================

@router.get("/today")
async def get_today_mission(user: User = Depends(get_current_user)):
    """
    Get or generate today's mission.
    Returns active mission if exists, otherwise generates new one.
    """
    global db, _generate_daily_mission, _PATTERN_FOCUS_MAP
    
    user_doc = await db.users.find_one({"user_id": user.user_id})
    rating = user_doc.get("assessed_rating", 1200) if user_doc else 1200
    
    mission = await _generate_daily_mission(user.user_id, rating, db)
    
    # Get focus info
    focus_data = _PATTERN_FOCUS_MAP.get(mission.get("focus_pattern"), {})
    
    return {
        "mission_id": mission.get("mission_id"),
        "trigger_type": mission.get("trigger_type"),
        "focus_label": mission.get("focus_label"),
        "focus_pattern": mission.get("focus_pattern"),
        "micro_protocol": mission.get("micro_protocol", focus_data.get("micro_protocol", [])),
        "goal": {
            "type": mission.get("goal_type"),
            "target": mission.get("goal_target"),
            "success_threshold": mission.get("goal_success_threshold"),
        },
        "estimated_minutes": mission.get("estimated_minutes"),
        "difficulty_band": mission.get("difficulty_band"),
        "status": mission.get("status"),
        "source_game_id": mission.get("source_game_id"),
    }


@router.post("/{mission_id}/start")
async def start_mission_endpoint(mission_id: str, user: User = Depends(get_current_user)):
    """Start a mission session."""
    global db, _start_mission
    result = await _start_mission(mission_id, user.user_id, db)
    return result


@router.get("/{mission_id}/positions")
async def get_mission_positions(mission_id: str, user: User = Depends(get_current_user)):
    """
    Get drill positions for a specific mission.
    Returns positions from user's games that match the mission's focus pattern.
    """
    global db, _extract_drill_positions, _get_sample_drill_positions
    
    # Get mission
    mission = await db.behavioral_missions.find_one({
        "mission_id": mission_id,
        "user_id": user.user_id
    })
    
    if not mission:
        raise HTTPException(status_code=404, detail="Mission not found")
    
    focus_pattern = mission.get("focus_pattern", "critical_moment_drift")
    target_count = mission.get("goal_target", 5)
    source_game_id = mission.get("source_game_id")
    
    # Get positions from user's analyzed games
    positions = []
    
    # If mission is from a specific game, prioritize that game
    if source_game_id:
        source_analysis = await db.game_analyses.find_one({"game_id": source_game_id})
        if source_analysis:
            positions = _extract_drill_positions(source_analysis, focus_pattern, limit=target_count)
    
    # Get more from other games if needed
    if len(positions) < target_count:
        other_analyses = await db.game_analyses.find({
            "user_id": user.user_id,
        }).sort("analyzed_at", -1).limit(15).to_list(15)
        
        for analysis in other_analyses:
            more_positions = _extract_drill_positions(analysis, focus_pattern, limit=target_count - len(positions))
            positions.extend(more_positions)
            if len(positions) >= target_count:
                break
    
    # If still no positions, generate sample positions for the pattern
    if len(positions) == 0:
        positions = _get_sample_drill_positions(focus_pattern, target_count)
    
    return {
        "positions": positions[:target_count],
        "total": len(positions[:target_count]),
        "focus_pattern": focus_pattern,
        "mission_id": mission_id
    }


@router.post("/generate-fix")
async def generate_fix_mission(data: dict, user: User = Depends(get_current_user)):
    """
    Generate a fix-it mission for a specific game (post-loss recovery).
    Returns the mission that targets the main issue from the game.
    """
    global db, _generate_daily_mission, _PATTERN_FOCUS_MAP
    from collections import Counter
    
    game_id = data.get("game_id")
    if not game_id:
        raise HTTPException(status_code=400, detail="game_id required")
    
    # Get game analysis
    analysis = await db.game_analyses.find_one({"game_id": game_id, "user_id": user.user_id})
    if not analysis:
        raise HTTPException(status_code=404, detail="Game analysis not found")
    
    # Get user rating
    user_doc = await db.users.find_one({"user_id": user.user_id})
    rating = user_doc.get("assessed_rating", 1200) if user_doc else 1200
    
    # Find main issue pattern
    blunders = analysis.get("blunders", [])
    main_pattern = "critical_moment_drift"  # Default
    
    if blunders:
        categories = [b.get("mistake_category") for b in blunders if b.get("mistake_category")]
        if categories:
            main_pattern = Counter(categories).most_common(1)[0][0]
    
    # Generate mission targeting this pattern
    mission = await _generate_daily_mission(
        user.user_id, 
        rating, 
        db,
        trigger_type="post_loss",
        source_game_id=game_id,
        force_pattern=main_pattern
    )
    
    # Get focus info
    focus_data = _PATTERN_FOCUS_MAP.get(mission.get("focus_pattern"), {})
    
    return {
        "mission_id": mission.get("mission_id"),
        "trigger_type": "post_loss",
        "focus_label": mission.get("focus_label"),
        "focus_pattern": mission.get("focus_pattern"),
        "micro_protocol": mission.get("micro_protocol", focus_data.get("micro_protocol", [])),
        "goal": {
            "type": mission.get("goal_type"),
            "target": mission.get("goal_target"),
            "success_threshold": mission.get("goal_threshold"),
        },
        "estimated_minutes": mission.get("estimated_minutes"),
        "difficulty_band": mission.get("difficulty_band"),
        "source_game_id": game_id,
    }


@router.post("/{mission_id}/step")
async def record_mission_step(
    mission_id: str,
    data: MissionStepRequest,
    user: User = Depends(get_current_user)
):
    """
    Record a step in the mission session.
    Emits reward events for process recognition.
    """
    global db
    now = datetime.now(timezone.utc)
    
    # Get active session
    session = await db.mission_sessions.find_one({
        "mission_id": mission_id,
        "user_id": user.user_id,
        "ended_at": None,
    })
    
    if not session:
        raise HTTPException(status_code=404, detail="No active session for this mission")
    
    # Build step record
    step = {
        "type": data.step_type,
        "payload": data.payload,
        "status": data.payload.get("status", "done"),
        "duration_ms": data.payload.get("duration_ms", 0),
        "timestamp": now.isoformat(),
    }
    
    # Update session with new step
    await db.mission_sessions.update_one(
        {"session_id": session["session_id"]},
        {
            "$push": {"steps": step},
            "$set": {"last_activity": now.isoformat()}
        }
    )
    
    return {
        "success": True,
        "step_recorded": data.step_type
    }


@router.post("/{mission_id}/complete")
async def complete_mission_endpoint(
    mission_id: str,
    data: MissionCompleteRequest,
    user: User = Depends(get_current_user)
):
    """Complete a mission and get result + rewards."""
    global db, _complete_mission, _RewardEventType, _get_reward_message
    
    # Get active session
    session = await db.mission_sessions.find_one({
        "mission_id": mission_id,
        "user_id": user.user_id,
        "ended_at": None,
    })
    
    if not session:
        raise HTTPException(status_code=404, detail="No active session")
    
    result = await _complete_mission(
        mission_id=mission_id,
        session_id=session["session_id"],
        user_id=user.user_id,
        score=data.score,
        db=db,
    )
    
    # Get reward message
    user_doc = await db.users.find_one({"user_id": user.user_id})
    rating = user_doc.get("assessed_rating", 1200) if user_doc else 1200
    
    passed = result.get("result") == "pass"
    reward_event = _RewardEventType.MISSION_COMPLETE_PASS if passed else _RewardEventType.MISSION_COMPLETE_FAIL
    
    reward_msg = _get_reward_message(reward_event, rating, {
        "focus_label": result.get("focus_label"),
        "correct": result.get("score", {}).get("correct", 0),
        "attempted": result.get("score", {}).get("attempted", 0),
    })
    
    # Store reward event
    if reward_msg:
        await db.reward_events.insert_one({
            "event_id": f"e_{uuid.uuid4().hex[:12]}",
            "user_id": user.user_id,
            "event_type": reward_event.value,
            "source": "mission",
            "payload": {"mission_id": mission_id, "result": result.get("result")},
            "message_id": reward_msg["message_id"],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "seen": False,
        })
    
    return {
        "result": result.get("result"),
        "score": result.get("score"),
        "threshold": result.get("threshold"),
        "focus_label": result.get("focus_label"),
        "coach_message": reward_msg["text"] if reward_msg else ("Good work!" if passed else "Keep practicing."),
    }


@router.get("/history")
async def get_mission_history(limit: int = 10, user: User = Depends(get_current_user)):
    """Get user's recent mission history."""
    global db
    
    missions = await db.behavioral_missions.find({
        "user_id": user.user_id,
        "status": "completed",
    }).sort("completed_at", -1).limit(limit).to_list(limit)
    
    result = []
    for m in missions:
        result.append({
            "mission_id": m.get("mission_id"),
            "focus_label": m.get("focus_label"),
            "result": m.get("result"),
            "completed_at": m.get("completed_at"),
            "trigger_type": m.get("trigger_type"),
        })
    
    # Stats
    total = len(result)
    passed = sum(1 for m in result if m["result"] == "pass")
    
    return {
        "missions": result,
        "stats": {
            "total": total,
            "passed": passed,
            "pass_rate": passed / total if total > 0 else 0,
        },
    }


@router.get("/focus-mastery")
async def get_focus_mastery(user: User = Depends(get_current_user)):
    """
    Get user's comprehensive focus mastery data.
    Shows mastery scores, trends, and recommendations for cognitive patterns.
    """
    global db, _PATTERN_FOCUS_MAP
    
    # Get all game analyses for this user
    game_analyses = await db.game_analyses.find(
        {"user_id": user.user_id},
        {"_id": 0}
    ).to_list(100)
    
    # Get mission history to calculate mastery
    missions = await db.behavioral_missions.find({
        "user_id": user.user_id,
        "status": "completed",
    }).to_list(100)
    
    # Calculate mastery per pattern
    mastery_data = {}
    for pattern_key, pattern_info in _PATTERN_FOCUS_MAP.items():
        pattern_missions = [m for m in missions if m.get("focus_pattern") == pattern_key]
        
        total = len(pattern_missions)
        passed = sum(1 for m in pattern_missions if m.get("result") == "pass")
        
        # Calculate mastery score (0-100)
        if total == 0:
            mastery_score = 0
            status = "not_started"
        elif total < 3:
            mastery_score = int((passed / total) * 30)  # Max 30 for <3 attempts
            status = "learning"
        else:
            mastery_score = int((passed / total) * 100)
            if mastery_score >= 80:
                status = "mastered"
            elif mastery_score >= 50:
                status = "progressing"
            else:
                status = "needs_work"
        
        mastery_data[pattern_key] = {
            "label": pattern_info.get("label", pattern_key),
            "description": pattern_info.get("description", ""),
            "mastery_score": mastery_score,
            "status": status,
            "attempts": total,
            "passed": passed,
            "pass_rate": passed / total if total > 0 else 0,
        }
    
    # Get recommendations
    recommendations = []
    for pattern_key, data in mastery_data.items():
        if data["status"] in ["not_started", "needs_work", "learning"]:
            recommendations.append({
                "pattern": pattern_key,
                "label": data["label"],
                "reason": "Low mastery - focus on this area",
                "priority": "high" if data["status"] == "needs_work" else "medium"
            })
    
    return {
        "mastery": mastery_data,
        "recommendations": recommendations[:3],  # Top 3
        "total_missions": len(missions),
        "overall_pass_rate": sum(1 for m in missions if m.get("result") == "pass") / len(missions) if missions else 0
    }
