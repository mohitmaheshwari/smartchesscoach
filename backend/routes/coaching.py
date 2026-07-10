"""
Coaching Prescriptions Routes
==============================

Handles all coaching prescription management endpoints including:
- Current active prescriptions with progress tracking
- Coach recommendations for next focus area
- User acceptance/rejection of prescriptions
- Alternative plan selection
- Parallel plan management (multiple concurrent plans)
- Historical audit trail of all prescriptions

This module integrates with:
- coaching_model.py (schema definitions)
- coaching_engine.py (issue detection and prescription generation)
"""

from fastapi import APIRouter, HTTPException, Depends, Body
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta
import logging
import uuid

logger = logging.getLogger(__name__)

# Create router for coaching endpoints
router = APIRouter(prefix="/coaching", tags=["Coaching"])

# Database reference - will be set by server.py
db = None

def set_db(database):
    """Set the database reference for coaching routes"""
    global db
    db = database


# Import User model and get_current_user from auth routes
from routes.auth import User, get_current_user


# ==================== PYDANTIC MODELS ====================

class PrescriptionModule(BaseModel):
    """Individual module within a training plan"""
    module_id: str
    title: str
    description: str
    duration_minutes: int
    content_type: str
    puzzle_count: int


class TrainingPlan(BaseModel):
    """Full training plan with all metadata"""
    plan_id: str
    name: str
    description: str
    difficulty: str
    target_rating_min: int
    target_rating_max: int
    duration_weeks: int
    weekly_commitment_hours: int
    cognitive_gap: str
    related_gaps: List[str]
    learning_outcomes: List[str]
    modules: List[PrescriptionModule]
    success_criteria: Dict[str, Any]
    is_active: bool


class PrescriptionResponse(BaseModel):
    """User's current or historical prescription"""
    prescription_id: str
    plan_id: str
    plan_name: str
    status: str
    issue_detected: str
    reasoning: str
    baseline_metric: float
    current_metric: float
    improvement_pct: float
    priority_order: int
    modules_completed: List[str]
    current_module: Optional[str]
    puzzles_completed: int
    puzzle_accuracy: float
    started_at: Optional[str]
    completed_at: Optional[str]
    expected_completion_date: str
    notes: str
    created_at: str
    updated_at: str
    plan_details: Optional[TrainingPlan] = None


class PrescriptionRecommendation(BaseModel):
    """Coach recommendation for next focus"""
    recommended_plan_id: str
    plan_name: str
    description: str
    reasoning: str
    issue_severity: str
    occurrence_count: int
    trend: str
    alternatives: List[Dict[str, Any]] = Field(default_factory=list)
    urgency: str


class AcceptPrescriptionRequest(BaseModel):
    """Request to accept/activate a prescribed plan"""
    prescription_id: str
    start_immediately: bool = True


class ChooseAlternativeRequest(BaseModel):
    """Request to select a different plan instead of recommended one"""
    plan_id: str
    reason: Optional[str] = None


class AddParallelPlanRequest(BaseModel):
    """Request to add a second concurrent training plan"""
    plan_id: str
    reason: Optional[str] = None
    max_concurrent_plans: int = 2


class PrescriptionHistoryEntry(BaseModel):
    """Historical record of prescription changes"""
    history_id: str
    prescription_id: str
    action: str
    previous_status: str
    new_status: str
    metric_before: Optional[float]
    metric_after: Optional[float]
    reason: Optional[str]
    triggered_by: str
    timestamp: str


class CompletePrescriptionRequest(BaseModel):
    """Request to mark prescription as completed"""
    prescription_id: str


class PausePrescriptionRequest(BaseModel):
    """Request to pause a prescription"""
    prescription_id: str


# ==================== HELPER FUNCTIONS ====================

async def get_user_current_rating(user_id: str) -> int:
    """
    Fetch user's current rating from their profile.
    Falls back to 1200 if not found.
    """
    user_doc = await db.users.find_one(
        {"user_id": user_id},
        {"_id": 0, "assessed_rating": 1}
    )
    return user_doc.get("assessed_rating", 1200) if user_doc else 1200


async def get_active_prescriptions(user_id: str) -> List[Dict]:
    """Get all active prescriptions for a user"""
    prescriptions = await db.user_coaching_prescriptions.find(
        {
            "user_id": user_id,
            "status": {"$in": ["active", "pending"]}
        },
        {"_id": 0}
    ).sort("priority_order", 1).to_list(None)
    return prescriptions or []


async def get_plan_by_id(plan_id: str) -> Optional[Dict]:
    """Fetch a training plan by its ID"""
    plan = await db.training_plans.find_one(
        {"plan_id": plan_id, "is_active": True},
        {"_id": 0}
    )
    return plan


async def count_active_user_plans(user_id: str) -> int:
    """Count how many active plans user currently has"""
    count = await db.user_coaching_prescriptions.count_documents({
        "user_id": user_id,
        "status": "active"
    })
    return count


async def record_prescription_history(
    prescription_id: str,
    user_id: str,
    action: str,
    previous_status: str,
    new_status: str,
    metric_before: Optional[float] = None,
    metric_after: Optional[float] = None,
    reason: Optional[str] = None,
    triggered_by: str = "user"
) -> str:
    """
    Record a prescription action in the audit trail.
    Returns history_id.
    """
    history_id = str(uuid.uuid4())
    history_doc = {
        "history_id": history_id,
        "prescription_id": prescription_id,
        "user_id": user_id,
        "action": action,
        "previous_status": previous_status,
        "new_status": new_status,
        "metric_before": metric_before,
        "metric_after": metric_after,
        "reason": reason,
        "triggered_by": triggered_by,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    await db.coaching_prescription_history.insert_one(history_doc)
    return history_id


def build_prescription_response(pres_doc: Dict, plan_doc: Optional[Dict] = None) -> PrescriptionResponse:
    """Convert database document to API response"""
    from datetime import datetime

    def to_iso_string(value):
        """Convert datetime to ISO string, or return as-is if already a string"""
        if isinstance(value, datetime):
            return value.isoformat()
        return value

    return PrescriptionResponse(
        prescription_id=pres_doc["prescription_id"],
        plan_id=pres_doc["plan_id"],
        plan_name=pres_doc.get("plan_name", ""),
        status=pres_doc["status"],
        issue_detected=pres_doc.get("issue_detected", ""),
        reasoning=pres_doc.get("reasoning", ""),
        baseline_metric=pres_doc.get("baseline_metric", 0.0),
        current_metric=pres_doc.get("current_metric", 0.0),
        improvement_pct=pres_doc.get("improvement_pct", 0.0),
        priority_order=pres_doc.get("priority_order", 999),
        modules_completed=pres_doc.get("modules_completed", []),
        current_module=pres_doc.get("current_module"),
        puzzles_completed=pres_doc.get("puzzles_completed", 0),
        puzzle_accuracy=pres_doc.get("puzzle_accuracy", 0.0),
        started_at=to_iso_string(pres_doc.get("started_at")),
        completed_at=to_iso_string(pres_doc.get("completed_at")),
        expected_completion_date=pres_doc.get("expected_completion_date", ""),
        notes=pres_doc.get("notes", ""),
        created_at=to_iso_string(pres_doc.get("created_at", "")),
        updated_at=to_iso_string(pres_doc.get("updated_at", "")),
        plan_details=TrainingPlan(**plan_doc) if plan_doc else None
    )


# ==================== ENDPOINT 1: GET /api/coaching/current-prescriptions ====================

@router.get("/current-prescriptions")
async def get_current_prescriptions(
    include_paused: bool = False,
    user: User = Depends(get_current_user)
):
    """
    Get all active (and optionally paused) prescriptions for the user.

    Returns:
    - List of active prescriptions with progress metrics
    - Ordered by priority (lowest number = highest priority)
    - Includes plan details and module completion status

    Query params:
    - include_paused (bool): If True, also return paused prescriptions
    """
    global db

    try:
        # Build query for active/paused prescriptions
        status_filter = ["active", "pending"]
        if include_paused:
            status_filter.append("paused")

        prescriptions = await db.user_coaching_prescriptions.find(
            {
                "user_id": user.user_id,
                "status": {"$in": status_filter}
            },
            {"_id": 0}
        ).sort("priority_order", 1).to_list(None)

        if not prescriptions:
            return {
                "prescriptions": [],
                "total_active": 0,
                "message": "No active prescriptions. Coach will recommend a focus area soon."
            }

        # Enrich with plan details
        responses = []
        for pres in prescriptions:
            plan = await get_plan_by_id(pres["plan_id"])
            response = build_prescription_response(pres, plan)
            responses.append(response)

        return {
            "prescriptions": responses,
            "total_active": len(responses),
            "highest_priority": responses[0].dict() if responses else None
        }

    except Exception as e:
        logger.error(f"Error fetching current prescriptions for {user.user_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching prescriptions: {str(e)}")


# ==================== ENDPOINT 2: GET /api/coaching/next-prescription ====================

@router.get("/next-prescription")
async def get_next_prescription_recommendation(
    user: User = Depends(get_current_user)
):
    """
    Get the coach's recommendation for the next focus area.

    The coach analyzes:
    - Recent game mistakes and patterns
    - Competence levels in each cognitive gap
    - Current prescription status
    - Player rating and rating band

    Returns:
    - Recommended primary plan
    - Up to 3 alternative plans
    - Reasoning for the recommendation
    - Urgency level (critical/high/medium/low)
    """
    global db

    try:
        user_rating = await get_user_current_rating(user.user_id)

        # Check if user already has active prescriptions
        active_count = await count_active_user_plans(user.user_id)

        # Get ALL game analyses to identify top issues (not just last 10)
        all_games = await db.game_analyses.find(
            {"user_id": user.user_id},
            {"_id": 0, "cognitive_gaps": 1, "created_at": 1}
        ).sort("created_at", -1).to_list(None)

        # Aggregate issues from all games with recency weighting
        # Recent games weighted higher than old games
        issue_scores: Dict[str, float] = {}

        if all_games:
            newest_date = all_games[0].get("created_at")

            for i, game in enumerate(all_games):
                # Recency weight: most recent = 1.0, older = decreases
                # Games in last 10: full weight, older games: reduced weight
                recency_weight = 1.0 if i < 10 else (0.5 + (0.5 * (10.0 / (i + 1))))

                for gap in game.get("cognitive_gaps", []):
                    gap_type = gap if isinstance(gap, str) else gap.get("gap_type", "piece_safety")
                    issue_scores[gap_type] = issue_scores.get(gap_type, 0.0) + recency_weight

        # Determine top issue by weighted score
        top_issue = max(issue_scores.items(), key=lambda x: x[1])[0] if issue_scores else "piece_safety"
        issue_frequency = int(issue_scores.get(top_issue, 0))

        # Find recommended plan based on issue and rating
        recommended_plan = await db.training_plans.find_one(
            {
                "cognitive_gap": top_issue,
                "target_rating_min": {"$lte": user_rating},
                "target_rating_max": {"$gte": user_rating},
                "is_active": True
            },
            {"_id": 0}
        )

        # If no exact match, find closest difficulty
        if not recommended_plan:
            recommended_plan = await db.training_plans.find_one(
                {
                    "cognitive_gap": top_issue,
                    "is_active": True
                },
                {"_id": 0}
            )

        # If still no match, recommend a general fundamental plan
        if not recommended_plan:
            recommended_plan = await db.training_plans.find_one(
                {
                    "cognitive_gap": "piece_safety",
                    "is_active": True
                },
                {"_id": 0}
            )

        # If no training plans exist at all, return error
        if not recommended_plan:
            logger.warning(f"No training plans found for user {user.user_id}")
            raise HTTPException(
                status_code=503,
                detail="Training plans are not yet available. Please check back soon."
            )

        # Get alternative plans (related gaps or same difficulty)
        alternatives = await db.training_plans.find(
            {
                "plan_id": {"$ne": recommended_plan["plan_id"]},
                "is_active": True,
                "$or": [
                    {"cognitive_gap": {"$in": recommended_plan.get("related_gaps", [])}},
                    {"difficulty": recommended_plan["difficulty"]}
                ]
            },
            {"_id": 0}
        ).limit(3).to_list(3)

        # Determine urgency based on weighted score
        # Score > 10 = many recent issues, Score 5-10 = moderate, < 5 = occasional
        urgency = "critical" if issue_frequency > 10 else "high" if issue_frequency > 5 else "medium"

        return {
            "recommendation": {
                "plan_id": recommended_plan["plan_id"],
                "name": recommended_plan["name"],
                "description": recommended_plan["description"],
                "cognitive_gap": recommended_plan["cognitive_gap"],
                "duration_weeks": recommended_plan["duration_weeks"],
                "weekly_commitment_hours": recommended_plan["weekly_commitment_hours"],
                "reasoning": f"Coach detected {int(issue_frequency)} weighted occurrences of {top_issue.replace('_', ' ')} across all your games (weighted by recency).",
                "issue_severity": top_issue,
                "occurrence_count": int(issue_frequency),
                "trend": "increasing" if issue_frequency > 10 else "stable",
                "alternatives": [
                    {
                        "plan_id": alt["plan_id"],
                        "name": alt["name"],
                        "cognitive_gap": alt["cognitive_gap"]
                    } for alt in alternatives
                ],
                "urgency": urgency
            },
            "current_prescriptions_count": active_count,
            "can_add_parallel": active_count < 2
        }

    except Exception as e:
        logger.error(f"Error generating prescription recommendation for {user.user_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error generating recommendation: {str(e)}")


# ==================== ENDPOINT 3: POST /api/coaching/accept-prescription ====================

@router.post("/accept-prescription")
async def accept_prescription(
    req: AcceptPrescriptionRequest,
    user: User = Depends(get_current_user)
):
    """
    User accepts a recommended prescription.

    Changes prescription status from 'pending' to 'active'.
    Records activation in prescription history.
    Optionally starts training immediately.

    Request body:
    - prescription_id (str): ID of prescription to activate
    - start_immediately (bool): If True, mark current_module to first module
    """
    global db

    try:
        # Fetch the prescription
        pres = await db.user_coaching_prescriptions.find_one(
            {
                "prescription_id": req.prescription_id,
                "user_id": user.user_id
            },
            {"_id": 0}
        )

        if not pres:
            raise HTTPException(status_code=404, detail="Prescription not found")

        if pres["status"] not in ["pending", "paused"]:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot activate prescription with status '{pres['status']}'"
            )

        # Update prescription to active
        now = datetime.now(timezone.utc)
        started_at = pres.get("started_at") or now.isoformat()

        update_data = {
            "status": "active",
            "started_at": started_at,
            "updated_at": now.isoformat()
        }

        # If starting immediately, set current_module to first module
        if req.start_immediately:
            plan = await get_plan_by_id(pres["plan_id"])
            if plan and plan.get("modules"):
                update_data["current_module"] = plan["modules"][0]["module_id"]

        await db.user_coaching_prescriptions.update_one(
            {
                "prescription_id": req.prescription_id,
                "user_id": user.user_id
            },
            {"$set": update_data}
        )

        # Record in history
        await record_prescription_history(
            prescription_id=req.prescription_id,
            user_id=user.user_id,
            action="activated",
            previous_status=pres["status"],
            new_status="active",
            reason="User accepted prescription"
        )

        # Fetch updated prescription for response
        updated_pres = await db.user_coaching_prescriptions.find_one(
            {
                "prescription_id": req.prescription_id,
                "user_id": user.user_id
            },
            {"_id": 0}
        )

        plan = await get_plan_by_id(updated_pres["plan_id"])
        response = build_prescription_response(updated_pres, plan)

        return {
            "status": "success",
            "message": f"Prescription activated successfully",
            "prescription": response.dict()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error accepting prescription {req.prescription_id} for {user.user_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error accepting prescription: {str(e)}")


# ==================== ENDPOINT 4: POST /api/coaching/choose-alternative ====================

@router.post("/choose-alternative")
async def choose_alternative_plan(
    req: ChooseAlternativeRequest,
    user: User = Depends(get_current_user)
):
    """
    User selects a different plan instead of coach's recommendation.

    Creates a new prescription for the chosen plan.
    Marks the originally recommended prescription as 'abandoned'.

    Request body:
    - plan_id (str): ID of alternative plan to activate
    - reason (optional str): Why user chose this instead
    """
    global db

    try:
        # Verify plan exists and is active
        plan = await get_plan_by_id(req.plan_id)
        if not plan:
            raise HTTPException(status_code=404, detail="Plan not found")

        # Create new prescription
        prescription_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        # Calculate expected completion date
        duration_weeks = plan.get("duration_weeks", 4)
        expected_completion = (
            now + timedelta(weeks=duration_weeks)
        ).isoformat()

        new_prescription = {
            "prescription_id": prescription_id,
            "user_id": user.user_id,
            "plan_id": req.plan_id,
            "plan_name": plan["name"],
            "status": "pending",
            "issue_detected": plan.get("cognitive_gap", ""),
            "reasoning": f"User chose alternative plan: {req.reason or 'No reason provided'}",
            "baseline_metric": 0.0,
            "current_metric": 0.0,
            "improvement_pct": 0.0,
            "started_at": None,
            "completed_at": None,
            "expected_completion_date": expected_completion,
            "priority_order": 999,  # User-initiated plans have lower priority
            "modules_completed": [],
            "current_module": None,
            "puzzles_completed": 0,
            "puzzle_accuracy": 0.0,
            "notes": req.reason or "",
            "created_at": now.isoformat(),
            "updated_at": now.isoformat()
        }

        # Insert new prescription
        await db.user_coaching_prescriptions.insert_one(new_prescription)

        # Record in history
        await record_prescription_history(
            prescription_id=prescription_id,
            user_id=user.user_id,
            action="prescribed",
            previous_status="none",
            new_status="pending",
            reason=f"User chose alternative: {req.reason or 'No reason provided'}"
        )

        return {
            "status": "success",
            "message": f"Alternative plan '{plan['name']}' added to your prescriptions",
            "prescription_id": prescription_id,
            "prescription": new_prescription
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error choosing alternative plan for {user.user_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error choosing alternative: {str(e)}")


# ==================== ENDPOINT 5: POST /api/coaching/add-parallel-plan ====================

@router.post("/add-parallel-plan")
async def add_parallel_plan(
    req: AddParallelPlanRequest,
    user: User = Depends(get_current_user)
):
    """
    Add a second concurrent training plan while keeping current one active.

    Validates that user hasn't exceeded max concurrent plans (default 2).
    Creates new prescription with appropriate priority order.

    Request body:
    - plan_id (str): ID of plan to add
    - reason (optional str): Why adding this plan
    - max_concurrent_plans (int): Maximum plans allowed (default 2)
    """
    global db

    try:
        # Check current active plan count
        active_count = await count_active_user_plans(user.user_id)

        if active_count >= req.max_concurrent_plans:
            raise HTTPException(
                status_code=400,
                detail=f"You already have {active_count} active plan(s). Maximum is {req.max_concurrent_plans}."
            )

        # Verify plan exists
        plan = await get_plan_by_id(req.plan_id)
        if not plan:
            raise HTTPException(status_code=404, detail="Plan not found")

        # Create new prescription
        prescription_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        duration_weeks = plan.get("duration_weeks", 4)
        expected_completion = (
            now + timedelta(weeks=duration_weeks)
        ).isoformat()

        new_prescription = {
            "prescription_id": prescription_id,
            "user_id": user.user_id,
            "plan_id": req.plan_id,
            "plan_name": plan["name"],
            "status": "pending",
            "issue_detected": plan.get("cognitive_gap", ""),
            "reasoning": f"User added parallel plan: {req.reason or 'Diversifying training'}",
            "baseline_metric": 0.0,
            "current_metric": 0.0,
            "improvement_pct": 0.0,
            "started_at": None,
            "completed_at": None,
            "expected_completion_date": expected_completion,
            "priority_order": active_count + 1,  # Lower priority than existing plans
            "modules_completed": [],
            "current_module": None,
            "puzzles_completed": 0,
            "puzzle_accuracy": 0.0,
            "notes": req.reason or "Added as parallel training focus",
            "created_at": now.isoformat(),
            "updated_at": now.isoformat()
        }

        # Insert new prescription
        await db.user_coaching_prescriptions.insert_one(new_prescription)

        # Record in history
        await record_prescription_history(
            prescription_id=prescription_id,
            user_id=user.user_id,
            action="prescribed",
            previous_status="none",
            new_status="pending",
            reason=f"Added as parallel plan: {req.reason or 'User choice'}"
        )

        return {
            "status": "success",
            "message": f"Plan '{plan['name']}' added as parallel training focus",
            "prescription_id": prescription_id,
            "active_plans_after": active_count + 1,
            "max_concurrent_plans": req.max_concurrent_plans,
            "prescription": new_prescription
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding parallel plan for {user.user_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error adding parallel plan: {str(e)}")


# ==================== ENDPOINT 6: GET /api/coaching/prescription-history ====================

@router.get("/prescription-history")
async def get_prescription_history(
    status_filter: Optional[str] = None,
    limit: int = 50,
    user: User = Depends(get_current_user)
):
    """
    Get historical record of all prescriptions and their status changes.

    Returns audit trail showing:
    - All prescriptions (completed, abandoned, paused, etc.)
    - Status transitions and when they occurred
    - Metric changes over time
    - Reasoning for changes

    Query params:
    - status_filter (optional str): Filter by 'completed', 'abandoned', 'paused'
    - limit (int): Maximum number of history entries to return (default 50)
    """
    global db

    try:
        # Build query for prescription documents
        pres_query = {"user_id": user.user_id}
        if status_filter:
            pres_query["status"] = status_filter

        # Get prescriptions (excluding pending/active for history view)
        if not status_filter:
            pres_query["status"] = {"$in": ["completed", "abandoned", "paused"]}

        prescriptions = await db.user_coaching_prescriptions.find(
            pres_query,
            {"_id": 0}
        ).sort("completed_at", -1).limit(limit).to_list(limit)

        # Get full history entries
        history_query = {"user_id": user.user_id}
        history = await db.coaching_prescription_history.find(
            history_query,
            {"_id": 0}
        ).sort("timestamp", -1).limit(limit * 3).to_list(limit * 3)  # Get more to group by prescription

        # Group history by prescription
        history_by_prescription: Dict[str, List[Dict]] = {}
        for entry in history:
            pres_id = entry["prescription_id"]
            if pres_id not in history_by_prescription:
                history_by_prescription[pres_id] = []
            history_by_prescription[pres_id].append(entry)

        # Build response with prescriptions and their histories
        result = []
        for pres in prescriptions:
            pres_id = pres["prescription_id"]
            plan = await get_plan_by_id(pres["plan_id"])
            pres_response = build_prescription_response(pres, plan)

            result.append({
                "prescription": pres_response.dict(),
                "history": history_by_prescription.get(pres_id, [])[:10]  # Last 10 changes per prescription
            })

        return {
            "history_entries": result,
            "total_count": len(result),
            "status_filter": status_filter,
            "note": "Showing completed, abandoned, or paused prescriptions. For active plans, use /current-prescriptions"
        }

    except Exception as e:
        logger.error(f"Error fetching prescription history for {user.user_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching history: {str(e)}")


# ==================== ENDPOINT 7: POST /api/coaching/complete-prescription ====================

@router.post("/complete-prescription")
async def complete_prescription(
    req: CompletePrescriptionRequest,
    user: User = Depends(get_current_user)
):
    """
    Mark a prescription as completed.

    Changes prescription status from 'active' to 'completed'.
    Records completion in prescription history.

    Request body:
    - prescription_id (str): ID of prescription to complete
    """
    global db

    try:
        # Fetch the prescription
        pres = await db.user_coaching_prescriptions.find_one(
            {
                "prescription_id": req.prescription_id,
                "user_id": user.user_id
            },
            {"_id": 0}
        )

        if not pres:
            raise HTTPException(status_code=404, detail="Prescription not found")

        if pres["status"] != "active":
            raise HTTPException(
                status_code=400,
                detail=f"Cannot complete prescription with status '{pres['status']}'"
            )

        # Update prescription to completed
        now = datetime.now(timezone.utc)

        update_data = {
            "status": "completed",
            "completed_at": now.isoformat(),
            "updated_at": now.isoformat()
        }

        await db.user_coaching_prescriptions.update_one(
            {
                "prescription_id": req.prescription_id,
                "user_id": user.user_id
            },
            {"$set": update_data}
        )

        # Record in history
        await record_prescription_history(
            prescription_id=req.prescription_id,
            user_id=user.user_id,
            action="completed",
            previous_status="active",
            new_status="completed",
            reason="User marked prescription as completed"
        )

        # Fetch updated prescription for response
        updated_pres = await db.user_coaching_prescriptions.find_one(
            {
                "prescription_id": req.prescription_id,
                "user_id": user.user_id
            },
            {"_id": 0}
        )

        plan = await get_plan_by_id(updated_pres["plan_id"])
        response = build_prescription_response(updated_pres, plan)

        return {
            "status": "success",
            "message": f"Prescription completed successfully",
            "prescription": response.dict()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error completing prescription {req.prescription_id} for {user.user_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error completing prescription: {str(e)}")


# ==================== ENDPOINT 8: POST /api/coaching/pause-prescription ====================

@router.post("/pause-prescription")
async def pause_prescription(
    req: PausePrescriptionRequest,
    user: User = Depends(get_current_user)
):
    """
    Pause a prescription temporarily.

    Changes prescription status from 'active' to 'paused'.
    Can be resumed later without loss of progress.
    Records pause in prescription history.

    Request body:
    - prescription_id (str): ID of prescription to pause
    """
    global db

    try:
        # Fetch the prescription
        pres = await db.user_coaching_prescriptions.find_one(
            {
                "prescription_id": req.prescription_id,
                "user_id": user.user_id
            },
            {"_id": 0}
        )

        if not pres:
            raise HTTPException(status_code=404, detail="Prescription not found")

        if pres["status"] != "active":
            raise HTTPException(
                status_code=400,
                detail=f"Cannot pause prescription with status '{pres['status']}'"
            )

        # Update prescription to paused
        now = datetime.now(timezone.utc)

        update_data = {
            "status": "paused",
            "updated_at": now.isoformat()
        }

        await db.user_coaching_prescriptions.update_one(
            {
                "prescription_id": req.prescription_id,
                "user_id": user.user_id
            },
            {"$set": update_data}
        )

        # Record in history
        await record_prescription_history(
            prescription_id=req.prescription_id,
            user_id=user.user_id,
            action="paused",
            previous_status="active",
            new_status="paused",
            reason="User paused prescription"
        )

        # Fetch updated prescription for response
        updated_pres = await db.user_coaching_prescriptions.find_one(
            {
                "prescription_id": req.prescription_id,
                "user_id": user.user_id
            },
            {"_id": 0}
        )

        plan = await get_plan_by_id(updated_pres["plan_id"])
        response = build_prescription_response(updated_pres, plan)

        return {
            "status": "success",
            "message": f"Prescription paused. You can resume it anytime.",
            "prescription": response.dict()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error pausing prescription {req.prescription_id} for {user.user_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error pausing prescription: {str(e)}")


# ==================== ENDPOINT 8: GET /api/coaching/training-modules ====================

@router.get("/training-modules")
async def get_training_modules(
    prescription_id: str,
    user: User = Depends(get_current_user)
):
    """
    Get training modules for an active prescription.

    Returns all modules for the prescribed training plan, allowing the user
    to see what they need to work through.

    Query params:
    - prescription_id (str): The prescription to fetch modules for

    Returns:
    - plan_name: Name of the training plan
    - plan_id: ID of the training plan
    - modules: List of modules with content
    - total_duration_minutes: Total time to complete all modules
    """
    global db

    try:
        # Get the prescription
        prescription = await db.user_coaching_prescriptions.find_one({
            "prescription_id": prescription_id,
            "user_id": user.user_id,
            "status": {"$in": ["active", "pending"]}
        }, {"_id": 0})

        if not prescription:
            raise HTTPException(status_code=404, detail="Prescription not found")

        # Get the training plan with modules
        plan = await db.training_plans.find_one({
            "plan_id": prescription["plan_id"],
            "is_active": True
        }, {"_id": 0})

        if not plan:
            raise HTTPException(status_code=404, detail="Training plan not found")

        # Calculate total duration
        total_duration = sum(m.get("duration_minutes", 0) for m in plan.get("modules", []))

        return {
            "plan_name": plan.get("name"),
            "plan_id": plan.get("plan_id"),
            "description": plan.get("description"),
            "difficulty": plan.get("difficulty"),
            "modules": plan.get("modules", []),
            "total_duration_minutes": total_duration,
            "modules_count": len(plan.get("modules", [])),
            "success_criteria": plan.get("success_criteria"),
            "learning_outcomes": plan.get("learning_outcomes")
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching training modules for {user.user_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching modules: {str(e)}")


# ==================== ENDPOINT 9: GET /api/coaching/recommendations-with-accuracy ====================

@router.get("/recommendations-with-accuracy")
async def get_recommendations_with_accuracy(
    user: User = Depends(get_current_user)
):
    """
    Get top 5 recommended training plans with data-backed accuracy.

    For each recommendation:
    - Shows actual cp_loss data from user's games
    - Calculates estimated elo rating improvement
    - Provides confidence score based on sample size
    - Shows ranges (conservative, realistic, optimistic)

    Returns top 5 cognitive gaps to train on, ranked by impact.
    """
    global db

    try:
        # 1. Fetch all user games with analyses
        games = await db.games.find({"user_id": user.user_id}).to_list(None)
        if not games:
            return {"recommendations": [], "error": "No games found"}

        game_ids = [g["game_id"] for g in games]

        # 2. Fetch all analyses for these games
        analyses = await db.game_analyses.find(
            {"game_id": {"$in": game_ids}}
        ).to_list(None)

        # 3. Aggregate cp_loss by cognitive_gap
        gap_data = {}

        for analysis in analyses:
            moves = analysis.get("stockfish_analysis", {}).get("move_evaluations", [])
            for move in moves:
                # Only count user mistakes (not opponent moves)
                if move.get("is_opponent_move"):
                    continue

                gap = move.get("cognitive_gap")
                cp_loss = move.get("cp_loss", 0)

                if gap and cp_loss and cp_loss > 0:
                    if gap not in gap_data:
                        gap_data[gap] = {
                            "cp_losses": [],
                            "mistakes": 0,
                            "games_with_gap": set(),
                            "game_dates": []
                        }

                    gap_data[gap]["cp_losses"].append(cp_loss)
                    gap_data[gap]["mistakes"] += 1
                    # Track which games had this gap
                    game_id = analysis.get("game_id")
                    if game_id:
                        gap_data[gap]["games_with_gap"].add(game_id)
                        # Get game date
                        game = next((g for g in games if g["game_id"] == game_id), None)
                        if game:
                            gap_data[gap]["game_dates"].append(game.get("date_played"))

        # 4. Calculate metrics for each gap
        recommendations = []

        for gap, data in gap_data.items():
            if data["mistakes"] < 3:  # Minimum sample size
                continue

            # Calculate totals and averages
            total_cp_loss = sum(data["cp_losses"])
            avg_cp_loss = total_cp_loss / data["mistakes"]
            num_games = len(data["games_with_gap"])

            # Calculate confidence score
            # Higher sample size = higher confidence
            confidence = min(100, 50 + (data["mistakes"] * 2))  # 50% base + 2% per mistake

            # ELO conversion: roughly 30-35 cp = 1 elo
            # Conservative: fix to 70% accuracy = recover 70% of cp_loss
            # Realistic: fix to 85% accuracy = recover 85% of cp_loss
            # Optimistic: fix to 95% accuracy = recover 95% of cp_loss
            cp_per_elo = 32

            conservative_cp_recovery = total_cp_loss * 0.70
            realistic_cp_recovery = total_cp_loss * 0.85
            optimistic_cp_recovery = total_cp_loss * 0.95

            conservative_elo = int(conservative_cp_recovery / cp_per_elo)
            realistic_elo = int(realistic_cp_recovery / cp_per_elo)
            optimistic_elo = int(optimistic_cp_recovery / cp_per_elo)

            # Get recency (days since last mistake in this gap)
            if data["game_dates"]:
                sorted_dates = sorted([d for d in data["game_dates"] if d], reverse=True)
                last_occurrence = sorted_dates[0] if sorted_dates else None
                if last_occurrence:
                    try:
                        last_date = datetime.fromisoformat(str(last_occurrence))
                        days_ago = (datetime.now(timezone.utc) - last_date).days
                    except:
                        days_ago = None
                else:
                    days_ago = None
            else:
                days_ago = None

            # Get training plan for this gap
            training_plan = await db.training_plans.find_one(
                {"cognitive_gap": gap}
            )

            recommendations.append({
                "rank": None,  # Will be set after sorting
                "gap": gap,
                "plan_id": training_plan.get("plan_id") if training_plan else None,
                "plan_name": training_plan.get("name") if training_plan else gap.replace("_", " ").title(),
                "description": training_plan.get("description") if training_plan else None,

                # Data evidence
                "total_cp_loss": total_cp_loss,
                "mistake_count": data["mistakes"],
                "avg_cp_loss_per_mistake": round(avg_cp_loss, 1),
                "games_affected": num_games,
                "recent_games": num_games,  # Last N games with this gap

                # Rating improvement estimates
                "rating_improvement": {
                    "conservative": {
                        "elo_gain": conservative_elo,
                        "recovery_pct": 70,
                        "description": f"Fix to 70% accuracy"
                    },
                    "realistic": {
                        "elo_gain": realistic_elo,
                        "recovery_pct": 85,
                        "description": f"Fix to 85% accuracy"
                    },
                    "optimistic": {
                        "elo_gain": optimistic_elo,
                        "recovery_pct": 95,
                        "description": f"Fix to 95% accuracy"
                    }
                },

                # Confidence & recency
                "confidence_pct": confidence,
                "last_mistake_days_ago": days_ago,
                "status": "active" if days_ago and days_ago <= 7 else "past"
            })

        # 5. Sort by realistic elo gain and rank
        recommendations.sort(
            key=lambda x: x["rating_improvement"]["realistic"]["elo_gain"],
            reverse=True
        )

        # Assign ranks
        for i, rec in enumerate(recommendations[:5], 1):
            rec["rank"] = i

        # Return top 5
        return {
            "recommendations": recommendations[:5],
            "total_gaps_detected": len(gap_data),
            "games_analyzed": len(games),
            "last_updated": datetime.now(timezone.utc).isoformat()
        }

    except Exception as e:
        logger.error(f"Error calculating recommendations with accuracy for {user.user_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error calculating recommendations: {str(e)}")
