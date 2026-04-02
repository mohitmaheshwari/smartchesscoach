"""
Behavioral Routes
=================

Handles behavioral analysis, reports, reanalysis jobs, and behavioral missions.

Endpoints:
- GET /behavioral/analyze/{game_id} - Get behavioral analysis report
- GET /behavioral/last-report - Get last behavioral report
- POST /behavioral/reanalysis/enqueue - Enqueue reanalysis job
- GET /behavioral/reanalysis/status - Get reanalysis job status
- POST /behavioral/mission/start - Start a behavioral mission
- POST /behavioral/mission/complete - Complete a behavioral mission
- GET /behavioral/mission/active - Get active missions
- GET /behavioral/mission/history - Get mission history
- GET /behavioral/mission/last-result - Get last mission result
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional, Dict
import logging

logger = logging.getLogger(__name__)

# Create router for behavioral endpoints
router = APIRouter(prefix="/behavioral", tags=["Behavioral"])

# Database reference - will be set by server.py
db = None

def set_db(database):
    """Set the database reference for behavioral routes"""
    global db
    db = database


# Import User model and get_current_user from auth routes
from routes.auth import User, get_current_user


# ==================== MODELS ====================

class ReanalysisRequest(BaseModel):
    """Request for enqueueing a reanalysis job"""
    user_id: Optional[str] = None  # Admin can specify, otherwise uses current user


class BehavioralMissionStartRequest(BaseModel):
    """Request to start tracking a behavioral mission"""
    mission_type: str
    difficulty: str = "STANDARD"
    game_id_context: Optional[str] = None
    root_cause: Optional[str] = None
    payload: Dict = {}


class BehavioralMissionCompleteRequest(BaseModel):
    """Request to complete a behavioral mission"""
    mission_id: str
    user_self_rating: Optional[int] = None  # 1-5


# ==================== BEHAVIORAL ANALYSIS ROUTES ====================

@router.get("/analyze/{game_id}")
async def get_behavioral_report(game_id: str, user: User = Depends(get_current_user)):
    """
    Get behavioral analysis report for a specific game.
    
    This is the core "coach memory" feature - returns:
    - 5 behavioral scorecard dimensions
    - One headline + one rich insight
    - One mission (next action)
    - Evidence references
    - Confidence score
    
    NOT just "0 blunders, 1 mistake" - actual behavioral coaching.
    """
    global db
    from behavioral_analyzer_service import generate_behavioral_report
    
    report = await generate_behavioral_report(db, user.user_id, game_id)
    return report


@router.get("/last-report")
async def get_last_behavioral_report(user: User = Depends(get_current_user)):
    """
    Get behavioral report for the user's most recent analyzed game.
    """
    global db
    from behavioral_analyzer_service import generate_behavioral_report
    
    # Find most recent analyzed game
    last_analysis = await db.game_analyses.find_one(
        {"user_id": user.user_id},
        sort=[("analyzed_at", -1)]
    )
    
    if not last_analysis:
        return {"error": "No analyzed games found"}
    
    report = await generate_behavioral_report(db, user.user_id, last_analysis.get("game_id"))
    return report


# ==================== REANALYSIS JOB ROUTES ====================

@router.post("/reanalysis/enqueue")
async def enqueue_reanalysis_job(
    request: ReanalysisRequest = None,
    user: User = Depends(get_current_user)
):
    """
    Enqueue a historical reanalysis job for a user.
    
    Re-analyzes all historical games using the latest P1.6 engine.
    - Idempotent: returns existing job if one is already pending/running
    - Safe: max 1 running job per user, max 50 games per run
    - historical_mode=True: does NOT mutate advice lifecycle
    """
    global db
    from jobs import enqueue_reanalysis, run_reanalysis_job
    import asyncio
    
    target_user_id = request.user_id if request and request.user_id else user.user_id
    
    # Enqueue job (idempotent)
    job = await enqueue_reanalysis(db, target_user_id)
    
    # Start job in background if PENDING
    if job.status == "PENDING":
        asyncio.create_task(run_reanalysis_job(db, job.job_id))
    
    return {
        "job_id": job.job_id,
        "status": job.status,
        "message": "Reanalysis job enqueued" if job.status == "PENDING" else "Existing job found"
    }


@router.get("/reanalysis/status")
async def get_reanalysis_job_status(user: User = Depends(get_current_user)):
    """
    Get the status of the most recent reanalysis job for the current user.
    
    Returns progress information including:
    - status: PENDING | RUNNING | DONE | FAILED
    - processed_games: number of games reanalyzed
    - skipped_games: number of games already up-to-date
    - total_games: total games to process
    - engine_version: version used for reanalysis
    """
    global db
    from jobs import get_reanalysis_status
    
    status = await get_reanalysis_status(db, user.user_id)
    
    if not status:
        return {"status": "NO_JOB", "message": "No reanalysis job found"}
    
    return status


# ==================== MISSION LIFECYCLE ROUTES ====================

@router.post("/mission/start")
async def start_behavioral_mission(
    request: BehavioralMissionStartRequest,
    user: User = Depends(get_current_user)
):
    """
    Start tracking a behavioral mission.
    Called when mission is shown to user.
    
    Creates a STARTED entry in mission_history.
    """
    global db
    from behavioral.mission_lifecycle import start_mission
    
    mission_data = {
        "type": request.mission_type,
        "difficulty": request.difficulty,
        "payload": request.payload,
    }
    
    record = await start_mission(
        db,
        user.user_id,
        mission_data,
        game_id_context=request.game_id_context,
        root_cause=request.root_cause
    )
    
    return {
        "mission_id": record.mission_id,
        "status": record.status,
        "message": "Mission tracking started"
    }


@router.post("/mission/complete")
async def complete_behavioral_mission(
    request: BehavioralMissionCompleteRequest,
    user: User = Depends(get_current_user)
):
    """
    Mark a behavioral mission as complete and trigger validation.
    
    Validation happens against NEXT APPLICABLE GAMES (not just next game).
    If no applicable games yet, mission stays STARTED.
    
    Returns validation result including:
    - status: COMPLETED | STARTED | FAILED
    - validation: score, applicability, games used
    - difficulty_decay_triggered: bool
    """
    global db
    from behavioral.mission_lifecycle import complete_mission
    
    result = await complete_mission(
        db,
        user.user_id,
        request.mission_id,
        user_self_rating=request.user_self_rating
    )
    
    return result


@router.get("/mission/active")
async def get_active_missions(user: User = Depends(get_current_user)):
    """
    Get user's active (STARTED) missions.
    Also checks for abandoned missions (48h timeout).
    """
    global db
    from behavioral.mission_lifecycle import check_abandoned_missions
    
    # Check for abandoned missions first
    await check_abandoned_missions(db, user.user_id)
    
    # Get active missions
    active = await db.mission_history.find({
        "user_id": user.user_id,
        "status": "STARTED"
    }).sort("created_at", -1).limit(5).to_list(5)
    
    return {
        "active_missions": [{
            "mission_id": m.get("mission_id"),
            "mission_type": m.get("mission_type"),
            "difficulty": m.get("difficulty"),
            "created_at": m.get("created_at"),
            "root_cause_context": m.get("root_cause_context")
        } for m in active],
        "count": len(active)
    }


@router.get("/mission/history")
async def get_mission_history(
    limit: int = 10,
    user: User = Depends(get_current_user)
):
    """
    Get user's mission history with validation results.
    """
    global db
    
    missions = await db.mission_history.find({
        "user_id": user.user_id
    }).sort("created_at", -1).limit(limit).to_list(limit)
    
    return {
        "missions": [{
            "mission_id": m.get("mission_id"),
            "mission_type": m.get("mission_type"),
            "difficulty": m.get("difficulty"),
            "status": m.get("status"),
            "validation_score": m.get("engine_validation_score"),
            "validation_reason": m.get("validation_reason"),
            "created_at": m.get("created_at"),
            "completed_at": m.get("completed_at"),
            "user_self_rating": m.get("user_self_rating")
        } for m in missions],
        "count": len(missions)
    }


@router.get("/mission/last-result")
async def get_last_mission_result_endpoint(user: User = Depends(get_current_user)):
    """
    Get the last completed/failed mission result.
    Used by narrative engine to reference recent mission outcomes.
    """
    global db
    from behavioral.mission_lifecycle import get_last_mission_result
    
    result = await get_last_mission_result(db, user.user_id)
    
    if not result:
        return {"has_result": False}
    
    return {
        "has_result": True,
        **result
    }
