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
from typing import Any, Dict, Optional
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
    """Completion carries no score; the server owns the score."""
    pass


class MissionAttemptRequest(BaseModel):
    """One move submitted against a server-issued mission position."""
    puzzle_id: str
    played_uci: str
    time_taken_ms: Optional[int] = None
    used_hint: bool = False
    submission_id: Optional[str] = None


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
    mission = await db.behavioral_missions.find_one({
        "mission_id": mission_id,
        "user_id": user.user_id,
    })
    if not mission:
        raise HTTPException(status_code=404, detail="Mission not found")
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

    from services.verified_puzzle_runtime import (
        public_puzzle_payload,
        resolve_verified_puzzle,
    )

    # Once issued, a mission is immutable. Re-resolve the frozen identities so
    # a later import or detector change cannot silently swap the work beneath
    # an active session. A newly invalid item fails closed and is not replaced.
    issued_ids = mission.get("eligible_puzzle_ids")
    if isinstance(issued_ids, list):
        served = []
        for puzzle_id in issued_ids:
            resolved = await resolve_verified_puzzle(
                db, str(puzzle_id), user_id=user.user_id
            )
            if not resolved:
                continue
            public = public_puzzle_payload(resolved)
            public.update({
                "puzzle_id": str(puzzle_id),
                "position_id": str(puzzle_id),
                "category": resolved.get("pattern_type") or "calculation_depth",
                "explanation": "From your game. Find the strongest move without looking at the answer.",
            })
            served.append(public)
        focus_info = (_PATTERN_FOCUS_MAP or {}).get(focus_pattern, {})
        return {
            "positions": served,
            "total": len(served),
            "focus_pattern": focus_pattern,
            "focus_label": focus_info.get(
                "focus_label", mission.get("focus_label")
            ),
            "micro_protocol": focus_info.get(
                "micro_protocol", mission.get("micro_protocol") or []
            ),
            "goal": {
                "target": int(mission.get("goal_target") or len(served)),
                "success_threshold": int(
                    mission.get("goal_success_threshold") or len(served)
                ),
            },
            "mission_id": mission_id,
        }
    
    # Get positions from user's analyzed games
    positions = []
    
    # If mission is from a specific game, prioritize that game
    if source_game_id:
        source_analysis = await db.game_analyses.find_one({
            "game_id": source_game_id,
            "user_id": user.user_id,
        })
        if source_analysis:
            positions = _extract_drill_positions(source_analysis, focus_pattern, limit=target_count)
    
    # Get more from other games if needed
    if len(positions) < target_count:
        other_analyses = await db.game_analyses.find(
            {"user_id": user.user_id},
            # PERF: drop the ~126KB decryption blobs (game-review only, unused here).
            {"decryption_v5_data": 0, "decryption_data": 0, "decryption_block": 0},
        ).sort("analyzed_at", -1).limit(15).to_list(15)
        
        for analysis in other_analyses:
            more_positions = _extract_drill_positions(analysis, focus_pattern, limit=target_count - len(positions))
            positions.extend(more_positions)
            if len(positions) >= target_count:
                break
    
    # Legacy authored samples have no stored analysis provenance, so they are
    # not eligible for a scored mission. Resolve every real-game candidate via
    # the same verified-admission engine used by all other puzzle surfaces.
    from services.puzzle_extraction_service import verdict_serves_pattern
    verified = []
    fallback = []
    seen_ids = set()
    for position in positions:
        game_id = position.get("game_id")
        move_number = position.get("move_number")
        if not game_id or move_number is None:
            continue
        puzzle_id = f"{game_id}_m{move_number}"
        if puzzle_id in seen_ids:
            continue
        seen_ids.add(puzzle_id)
        resolved = await resolve_verified_puzzle(db, puzzle_id, user_id=user.user_id)
        if not resolved:
            continue
        public = public_puzzle_payload(resolved)
        public.update({
            "puzzle_id": puzzle_id,
            "position_id": puzzle_id,
            "type": position.get("type"),
            "category": resolved.get("pattern_type") or "calculation_depth",
            "explanation": "From your game. Find the strongest move without looking at the answer.",
        })
        fallback.append(public)
        if verdict_serves_pattern(resolved, focus_pattern):
            verified.append(public)

    # Prefer an exact verified focus match. If the old behavioral mission label
    # has no provable positions, keep the real content and relabel the mission
    # to the verified broad category instead of showing an unrelated puzzle or
    # an unproved sample.
    served = (verified or fallback)[:target_count]
    effective_pattern = focus_pattern
    if served and not verified:
        effective_pattern = served[0].get("category") or "calculation_depth"
        focus_info = (_PATTERN_FOCUS_MAP or {}).get(effective_pattern, {})
        effective_target = len(served)
        effective_threshold = min(
            int(mission.get("goal_success_threshold") or effective_target),
            effective_target,
        )
        await db.behavioral_missions.update_one(
            {"mission_id": mission_id, "user_id": user.user_id},
            {"$set": {
                "focus_pattern": effective_pattern,
                "focus_label": focus_info.get("focus_label", effective_pattern.replace("_", " ").title()),
                "micro_protocol": focus_info.get("micro_protocol", mission.get("micro_protocol") or []),
                "eligible_puzzle_ids": [item["puzzle_id"] for item in served],
                "goal_target": effective_target,
                "goal_success_threshold": effective_threshold,
            }},
        )
    else:
        effective_target = len(served)
        effective_threshold = min(
            int(mission.get("goal_success_threshold") or effective_target),
            effective_target,
        )
        await db.behavioral_missions.update_one(
            {"mission_id": mission_id, "user_id": user.user_id},
            {"$set": {
                "eligible_puzzle_ids": [item["puzzle_id"] for item in served],
                "goal_target": effective_target,
                "goal_success_threshold": effective_threshold,
            }},
        )

    effective_info = (_PATTERN_FOCUS_MAP or {}).get(effective_pattern, {})

    return {
        "positions": served,
        "total": len(served),
        "focus_pattern": effective_pattern,
        "focus_label": effective_info.get(
            "focus_label", mission.get("focus_label") if effective_pattern == focus_pattern
            else effective_pattern.replace("_", " ").title()
        ),
        "micro_protocol": effective_info.get(
            "micro_protocol", mission.get("micro_protocol") or []
        ),
        "goal": {
            "target": effective_target,
            "success_threshold": effective_threshold,
        },
        "mission_id": mission_id
    }


@router.post("/{mission_id}/attempt")
async def grade_mission_attempt(
    mission_id: str,
    data: MissionAttemptRequest,
    user: User = Depends(get_current_user),
):
    """Grade one issued mission position from server-owned stored evidence."""
    mission = await db.behavioral_missions.find_one({
        "mission_id": mission_id,
        "user_id": user.user_id,
    })
    if not mission:
        raise HTTPException(status_code=404, detail="Mission not found")
    session = await db.mission_sessions.find_one({
        "mission_id": mission_id,
        "user_id": user.user_id,
        "ended_at": None,
    })
    if not session:
        raise HTTPException(status_code=404, detail="No active session for this mission")
    if data.puzzle_id not in set(mission.get("eligible_puzzle_ids") or []):
        raise HTTPException(status_code=400, detail="Position was not issued for this mission")
    if data.puzzle_id in set(session.get("graded_puzzle_ids") or []):
        raise HTTPException(status_code=409, detail="Position already scored")

    from services.verified_puzzle_attempt_service import record_verified_puzzle_attempt
    from services.verified_puzzle_runtime import resolve_verified_puzzle

    resolved = await resolve_verified_puzzle(db, data.puzzle_id, user_id=user.user_id)
    if not resolved:
        raise HTTPException(status_code=404, detail="Position is not ready for training")
    grade = await record_verified_puzzle_attempt(
        db,
        user_id=user.user_id,
        puzzle_id=data.puzzle_id,
        puzzle=resolved,
        played_uci=data.played_uci.strip().lower(),
        time_taken_ms=data.time_taken_ms,
        moves_tried=[data.played_uci.strip().lower()],
        attempt_context=f"mission:{mission_id}",
        submission_id=data.submission_id,
    )
    if grade.get("quality") == "invalid":
        raise HTTPException(status_code=400, detail=grade.get("feedback"))

    correct = bool(grade.get("correct"))
    claim = await db.mission_sessions.update_one(
        {
            "session_id": session["session_id"],
            "graded_puzzle_ids": {"$ne": data.puzzle_id},
        },
        {
            "$addToSet": {"graded_puzzle_ids": data.puzzle_id},
            "$inc": {
                "score.attempted": 1,
                "score.correct": 1 if correct else 0,
            },
            "$push": {"steps": {
                "type": "verified_drill_result",
                "puzzle_id": data.puzzle_id,
                "correct": correct,
                "used_hint": bool(data.used_hint),
                "duration_ms": data.time_taken_ms or 0,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }},
        },
    )
    if getattr(claim, "modified_count", 1) == 0:
        raise HTTPException(status_code=409, detail="Position already scored")

    return {
        "correct": correct,
        "quality": grade.get("quality"),
        "best_move_san": grade.get("best_move_san"),
        "best_move_uci": grade.get("best_move_uci"),
        "feedback": grade.get("feedback"),
    }


@router.post("/generate-fix")
async def generate_fix_mission(data: dict, user: User = Depends(get_current_user)):
    """
    Generate a fix-it mission for a specific game (post-loss recovery).
    Returns the mission that targets the main issue from the game.
    """
    global db, _generate_daily_mission, _PATTERN_FOCUS_MAP

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
    
    # Find main issue pattern from real per-move cognitive_gap tags — the
    # old logic here read analysis["blunders"], a field never populated on
    # any real document, so this always fell back to the generic default
    # regardless of what actually went wrong in the game.
    from mission_generation_service import build_pattern_stats_from_analyses
    main_pattern = "critical_moment_drift"  # Default when no gap-tagged mistake exists
    pattern_stats = build_pattern_stats_from_analyses([analysis])
    if pattern_stats:
        main_pattern = max(pattern_stats.items(), key=lambda kv: kv[1]["repeat_count_14d"])[0]
    
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
    
    if data.step_type == "drill_result":
        raise HTTPException(
            status_code=400,
            detail="Use the verified mission-attempt endpoint for scored moves",
        )

    # Build a non-scoring process step record.
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
    
    mission = await db.behavioral_missions.find_one({
        "mission_id": mission_id,
        "user_id": user.user_id,
    })
    eligible = list((mission or {}).get("eligible_puzzle_ids") or [])
    graded = set(session.get("graded_puzzle_ids") or [])
    server_score = session.get("score") or {}
    required_attempts = min(int((mission or {}).get("goal_target") or len(eligible)), len(eligible))
    if (
        not eligible
        or int(server_score.get("attempted") or 0) < required_attempts
        or not set(eligible).issubset(graded)
    ):
        raise HTTPException(status_code=409, detail="Finish the issued positions before completing the mission")

    result = await _complete_mission(
        mission_id=mission_id,
        session_id=session["session_id"],
        user_id=user.user_id,
        score=None,
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
    Get verified mission-practice checkpoints by focus pattern.

    This endpoint deliberately does not claim chess mastery; transfer into
    later real games and retention are measured elsewhere.
    """
    global db, _PATTERN_FOCUS_MAP
    
    # Get all game analyses for this user
    await db.game_analyses.find(
        {"user_id": user.user_id},
        # PERF: drop the ~126KB decryption blobs (game-review only, unused here).
        {"_id": 0, "decryption_v5_data": 0, "decryption_data": 0, "decryption_block": 0}
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
            practice_score = 0
            status = "not_started"
        elif total < 3:
            practice_score = int((passed / total) * 30)  # Max 30 for <3 attempts
            status = "practising"
        else:
            practice_score = int((passed / total) * 100)
            if practice_score >= 80:
                status = "checkpoint_passed"
            elif practice_score >= 50:
                status = "practising"
            else:
                status = "needs_work"
        
        mastery_data[pattern_key] = {
            "label": pattern_info.get("focus_label", pattern_key),
            "description": pattern_info.get("description", ""),
            "practice_score": practice_score,
            "mastery_status": "not_measured",
            "status": status,
            "attempts": total,
            "passed": passed,
            "pass_rate": passed / total if total > 0 else 0,
        }
    
    # Get recommendations
    recommendations = []
    for pattern_key, data in mastery_data.items():
        if data["status"] in ["not_started", "needs_work", "practising"]:
            recommendations.append({
                "pattern": pattern_key,
                "label": data["label"],
                "reason": "More verified practice evidence is needed here",
                "priority": "high" if data["status"] == "needs_work" else "medium"
            })
    
    return {
        "mastery": mastery_data,
        "recommendations": recommendations[:3],  # Top 3
        "total_missions": len(missions),
        "overall_pass_rate": sum(1 for m in missions if m.get("result") == "pass") / len(missions) if missions else 0
    }
