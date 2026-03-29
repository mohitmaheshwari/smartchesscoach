"""
Mission Lifecycle Service

Manages the full lifecycle of coaching missions:
1. START: When mission is shown to user
2. COMPLETE: When user finishes mission (triggers validation)
3. FAILED: When validation shows no improvement
4. ABANDONED: After 48h timeout

Integrates with:
- Difficulty decay (validated failures)
- Learning velocity (mission validation boost)
- Narrative engine (mission result references)
"""

import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional, List
from dataclasses import dataclass, asdict

from .mission_validation import validate_mission_effect, ValidationResult

logger = logging.getLogger(__name__)

# Mission timeout (48 hours)
MISSION_TIMEOUT_HOURS = 48

# Validation thresholds for narrative confidence
VALIDATION_SUCCESS_THRESHOLD = 0.6  # Score >= 0.6 → allow success narrative
VALIDATION_FAILURE_THRESHOLD = 0.3  # Score <= 0.3 → allow failure narrative


@dataclass
class MissionRecord:
    """Mission history record"""
    mission_id: str
    user_id: str
    game_id_context: Optional[str]
    mission_type: str
    difficulty: str
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    
    status: str = "STARTED"  # STARTED | COMPLETED | FAILED | ABANDONED
    
    user_self_rating: Optional[int] = None  # 1-5
    engine_validation_score: Optional[float] = None
    difficulty_cap_at_time: Optional[str] = None
    root_cause_context: Optional[str] = None
    
    validation_games_used: List[str] = None
    validation_metrics: Dict = None
    validation_reason: str = None
    validation_applicable: bool = None
    
    def to_dict(self):
        d = asdict(self)
        if d.get("validation_games_used") is None:
            d["validation_games_used"] = []
        if d.get("validation_metrics") is None:
            d["validation_metrics"] = {}
        return d


async def start_mission(
    db,
    user_id: str,
    mission: Dict,
    game_id_context: str = None,
    root_cause: str = None
) -> MissionRecord:
    """
    Record a mission as STARTED when shown to user.
    
    Returns the created MissionRecord.
    """
    now = datetime.now(timezone.utc).isoformat()
    
    record = MissionRecord(
        mission_id=str(uuid.uuid4()),
        user_id=user_id,
        game_id_context=game_id_context,
        mission_type=mission.get("type") or mission.get("mission_type"),
        difficulty=mission.get("difficulty", "STANDARD"),
        created_at=now,
        started_at=now,
        status="STARTED",
        difficulty_cap_at_time=mission.get("difficulty"),
        root_cause_context=root_cause or mission.get("payload", {}).get("root_cause"),
        validation_games_used=[],
        validation_metrics={},
    )
    
    await db.mission_history.insert_one(record.to_dict())
    logger.info(f"Started mission {record.mission_id} ({record.mission_type}) for user {user_id}")
    
    return record


async def complete_mission(
    db,
    user_id: str,
    mission_id: str,
    user_self_rating: int = None
) -> Dict:
    """
    Mark a mission as complete and trigger validation.
    
    Validation happens asynchronously against next applicable games.
    If no applicable games yet, mission stays STARTED.
    
    Returns:
        {
            "status": "COMPLETED" | "STARTED" | "FAILED",
            "validation": ValidationResult,
            "difficulty_decay_triggered": bool
        }
    """
    # Load mission
    mission = await db.mission_history.find_one({
        "mission_id": mission_id,
        "user_id": user_id
    })
    
    if not mission:
        return {"error": "Mission not found"}
    
    if mission.get("status") in ["COMPLETED", "FAILED", "ABANDONED"]:
        return {"error": f"Mission already {mission.get('status')}"}
    
    # Update self-rating if provided
    if user_self_rating is not None:
        await db.mission_history.update_one(
            {"mission_id": mission_id},
            {"$set": {"user_self_rating": user_self_rating}}
        )
    
    # Trigger validation
    validation = await validate_mission_effect(db, user_id, mission)
    
    # If not applicable yet, keep STARTED
    if not validation.applicable:
        logger.info(f"Mission {mission_id} validation not applicable yet")
        return {
            "status": "STARTED",
            "validation": validation.to_dict(),
            "difficulty_decay_triggered": False,
            "message": validation.reason
        }
    
    # Determine final status based on validation score
    now = datetime.now(timezone.utc).isoformat()
    
    if validation.score >= VALIDATION_FAILURE_THRESHOLD:
        # Mission COMPLETED (even partial success counts)
        new_status = "COMPLETED"
    else:
        # Mission FAILED (score too low)
        new_status = "FAILED"
    
    # Update mission record
    await db.mission_history.update_one(
        {"mission_id": mission_id},
        {"$set": {
            "status": new_status,
            "completed_at": now,
            "engine_validation_score": validation.score,
            "validation_games_used": validation.validation_games_used,
            "validation_metrics": validation.metrics,
            "validation_reason": validation.reason,
            "validation_applicable": validation.applicable,
        }}
    )
    
    # Handle difficulty decay
    difficulty_decay_triggered = False
    if mission.get("difficulty") == "HARD" and validation.score < 0.4:
        difficulty_decay_triggered = await _handle_difficulty_decay(
            db, user_id, mission_id, validation.score
        )
    elif validation.score >= 0.4 and mission.get("difficulty") == "HARD":
        # Reset decay counter on HARD success
        await _reset_difficulty_decay(db, user_id)
    
    logger.info(f"Mission {mission_id} completed with status {new_status}, score {validation.score:.2f}")
    
    return {
        "status": new_status,
        "validation": validation.to_dict(),
        "difficulty_decay_triggered": difficulty_decay_triggered,
        "message": validation.reason
    }


async def check_abandoned_missions(db, user_id: str = None) -> int:
    """
    Mark missions as ABANDONED if 48h timeout exceeded.
    
    Run periodically or on user login.
    
    Returns count of missions marked abandoned.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=MISSION_TIMEOUT_HOURS)
    cutoff_str = cutoff.isoformat()
    
    query = {
        "status": "STARTED",
        "created_at": {"$lt": cutoff_str}
    }
    if user_id:
        query["user_id"] = user_id
    
    result = await db.mission_history.update_many(
        query,
        {"$set": {"status": "ABANDONED"}}
    )
    
    if result.modified_count > 0:
        logger.info(f"Marked {result.modified_count} missions as ABANDONED")
    
    return result.modified_count


async def get_last_mission_result(db, user_id: str) -> Optional[Dict]:
    """
    Get the most recent completed/failed mission for narrative reference.
    """
    mission = await db.mission_history.find_one(
        {
            "user_id": user_id,
            "status": {"$in": ["COMPLETED", "FAILED"]},
            "engine_validation_score": {"$exists": True}
        },
        sort=[("completed_at", -1)]
    )
    
    if not mission:
        return None
    
    return {
        "mission_id": mission.get("mission_id"),
        "mission_type": mission.get("mission_type"),
        "difficulty": mission.get("difficulty"),
        "status": mission.get("status"),
        "validation_score": mission.get("engine_validation_score"),
        "validation_reason": mission.get("validation_reason"),
        "completed_at": mission.get("completed_at"),
        "can_reference_success": mission.get("engine_validation_score", 0) >= VALIDATION_SUCCESS_THRESHOLD,
        "can_reference_failure": mission.get("engine_validation_score", 0) <= VALIDATION_FAILURE_THRESHOLD,
    }


async def get_recent_mission_validations(db, user_id: str, limit: int = 3) -> List[Dict]:
    """
    Get recent mission validation scores for learning velocity adjustment.
    """
    missions = await db.mission_history.find(
        {
            "user_id": user_id,
            "status": {"$in": ["COMPLETED", "FAILED"]},
            "engine_validation_score": {"$exists": True},
            "validation_applicable": True
        },
        sort=[("completed_at", -1)]
    ).limit(limit).to_list(limit)
    
    return [{
        "mission_id": m.get("mission_id"),
        "mission_type": m.get("mission_type"),
        "validation_score": m.get("engine_validation_score"),
        "completed_at": m.get("completed_at")
    } for m in missions]


async def compute_mission_velocity_adjustment(db, user_id: str) -> float:
    """
    Compute learning velocity adjustment based on mission validation scores.
    
    Formula (smoothed):
        adjustment = avg(last 3 validation scores) * 0.2
    
    Returns adjustment value (0 to 0.2)
    """
    recent = await get_recent_mission_validations(db, user_id, limit=3)
    
    if not recent:
        return 0.0
    
    avg_score = sum(m.get("validation_score", 0) for m in recent) / len(recent)
    
    # Adjustment is 0-0.2 based on average score
    return avg_score * 0.2


# ==================== DIFFICULTY DECAY ====================

async def _handle_difficulty_decay(
    db, user_id: str, mission_id: str, validation_score: float
) -> bool:
    """
    Handle difficulty decay for HARD mission failures.
    
    Rule: If HARD mission fails with score < 0.4, increment failure counter.
    After 2 consecutive validated HARD failures, downgrade difficulty cap.
    
    Returns True if decay was triggered.
    """
    # Load user profile
    user = await db.users.find_one({"user_id": user_id})
    if not user:
        return False
    
    failures = user.get("consecutive_hard_failures", 0) + 1
    
    await db.users.update_one(
        {"user_id": user_id},
        {"$set": {"consecutive_hard_failures": failures}}
    )
    
    if failures >= 2:
        logger.info(f"Difficulty decay triggered for user {user_id} after {failures} HARD failures")
        return True
    
    return False


async def _reset_difficulty_decay(db, user_id: str) -> None:
    """Reset difficulty decay counter on HARD success"""
    await db.users.update_one(
        {"user_id": user_id},
        {"$set": {"consecutive_hard_failures": 0}}
    )


# ==================== NARRATIVE HELPERS ====================

def get_mission_narrative_context(last_mission: Dict) -> Optional[Dict]:
    """
    Get narrative context for referencing mission results.
    
    Only returns context if confidence threshold is met.
    """
    if not last_mission:
        return None
    
    score = last_mission.get("validation_score", 0)
    
    if score >= VALIDATION_SUCCESS_THRESHOLD:
        return {
            "type": "success",
            "mission_type": last_mission.get("mission_type"),
            "reason": last_mission.get("validation_reason"),
            "template": _get_success_template(last_mission)
        }
    elif score <= VALIDATION_FAILURE_THRESHOLD:
        return {
            "type": "failure",
            "mission_type": last_mission.get("mission_type"),
            "reason": last_mission.get("validation_reason"),
            "template": _get_failure_template(last_mission)
        }
    
    # Score between thresholds - no confident narrative
    return None


def _get_success_template(mission: Dict) -> str:
    """Get success narrative template"""
    mission_type = mission.get("mission_type", "")
    
    templates = {
        "TIME_DECISION_DRILL": "Your time pressure drill worked — composure improved in recent games.",
        "CANDIDATE_MOVE_DRILL": "The calculation drill showed results — fewer tactical errors.",
        "DEFENSIVE_RESILIENCE_DRILL": "Your defensive resilience drill worked — holding positions better.",
        "CONVERSION_DISCIPLINE_DRILL": "The conversion drill paid off — converting winning positions cleanly.",
        "ADVICE_ENFORCEMENT": "You applied the coaching advice — the habit is forming.",
        "OPENING_DISCIPLINE": "Your opening discipline improved after the drill.",
    }
    
    return templates.get(mission_type, "Your last drill showed measurable improvement.")


def _get_failure_template(mission: Dict) -> str:
    """Get failure narrative template"""
    mission_type = mission.get("mission_type", "")
    
    templates = {
        "TIME_DECISION_DRILL": "We're not seeing change from the time pressure drill yet.",
        "CANDIDATE_MOVE_DRILL": "The calculation drill hasn't translated to games yet.",
        "DEFENSIVE_RESILIENCE_DRILL": "Defensive collapse still occurring despite the drill.",
        "CONVERSION_DISCIPLINE_DRILL": "Conversion issues persist — the drill needs reinforcement.",
        "ADVICE_ENFORCEMENT": "The advice isn't being applied in games yet.",
        "OPENING_DISCIPLINE": "Opening discipline still needs work.",
    }
    
    return templates.get(mission_type, "The last drill hasn't shown measurable change yet.")
