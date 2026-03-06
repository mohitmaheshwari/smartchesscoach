"""
Pattern Learning & Feedback Routes
===================================

Self-learning pattern recognition system for improving coach accuracy.

Handles:
- Feedback submission when coach explanations are wrong
- Pattern learning system statistics
- Rule approval/rejection workflow
- Pattern classification
"""

from fastapi import APIRouter, HTTPException, Depends, Body
from typing import Dict
import logging

logger = logging.getLogger(__name__)

# Create router for pattern learning endpoints
router = APIRouter(prefix="/coach/pattern-learning", tags=["Pattern Learning"])

# Database reference - will be set by server.py
db = None

def set_db(database):
    """Set the database reference for feedback routes"""
    global db
    db = database


# Import User model and get_current_user from auth routes
from routes.auth import User, get_current_user


@router.post("/feedback")
async def submit_pattern_feedback(
    request: Dict = Body(...),
    user: User = Depends(get_current_user)
):
    """
    Submit feedback when a coach explanation is wrong.
    
    This triggers the self-learning system to:
    1. Store the feedback
    2. Generate a corrected explanation immediately
    3. Learn a new classification rule for similar positions
    
    Body:
    - position_fen: FEN of the position before the move
    - move_played: The move that was played (UCI or SAN)
    - move_san: SAN notation of the move (optional)
    - system_classification: What the system classified it as (e.g., "MISSED_TRAP")
    - system_explanation: The explanation the system gave
    - correct_classification: What it actually was (e.g., "WALKED_INTO_FORK")
    - user_explanation: User's explanation of what went wrong (optional)
    - eval_before: Eval before move in centipawns (optional)
    - eval_after: Eval after move in centipawns (optional)
    - best_move: What Stockfish recommends (optional)
    - pv_after_played: Principal variation after the played move (optional)
    - game_id: Game ID for context (optional)
    - move_number: Move number (optional)
    - user_color: "white" or "black" (optional)
    
    Returns:
    - success: True if feedback was processed
    - feedback_id: ID of the stored feedback
    - corrected_explanation: The corrected explanation to show the user
    - pattern: The correct pattern classification
    - learning_status: "queued", "correction_exists", or "rule_generated"
    """
    from services.pattern_learning.auto_correction_service import get_auto_correction_service
    
    service = get_auto_correction_service()
    
    result = await service.submit_feedback_and_correct(
        user_id=user.user_id,
        position_fen=request.get("position_fen", ""),
        move_played=request.get("move_played", ""),
        system_classification=request.get("system_classification", ""),
        system_explanation=request.get("system_explanation", ""),
        correct_classification=request.get("correct_classification", ""),
        user_explanation=request.get("user_explanation", ""),
        move_san=request.get("move_san", ""),
        eval_before=request.get("eval_before", 0.0),
        eval_after=request.get("eval_after", 0.0),
        best_move=request.get("best_move", ""),
        pv_after_played=request.get("pv_after_played", []),
        game_id=request.get("game_id", ""),
        move_number=request.get("move_number", 0),
        user_color=request.get("user_color", "white")
    )
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to process feedback"))
    
    logger.info(f"Pattern feedback submitted: {result.get('feedback_id')} - {result.get('learning_status')}")
    
    return result


@router.get("/my-feedback")
async def get_my_feedback(user: User = Depends(get_current_user)):
    """
    Get the current user's submitted feedback with corrections.
    
    Returns:
    - List of feedback submissions with status and corrections
    """
    global db
    feedback_list = []
    
    # Get user's feedback
    cursor = db.pattern_feedback.find(
        {"user_id": user.user_id}
    ).sort("created_at", -1).limit(50)
    
    async for doc in cursor:
        feedback_id = doc.get("feedback_id")
        
        # Get corresponding correction if exists
        correction = await db.verified_corrections.find_one(
            {"feedback_id": feedback_id},
            {"_id": 0}
        )
        
        feedback_list.append({
            "feedback_id": feedback_id,
            "created_at": doc.get("created_at"),
            "status": doc.get("status", "pending"),
            "position_fen": doc.get("position_fen"),
            "move_played": doc.get("move_played"),
            "best_move": doc.get("best_move"),
            "move_number": doc.get("move_number"),
            "game_id": doc.get("game_id"),
            "section_type": doc.get("section_type"),
            "system_classification": doc.get("system_classification"),
            "system_explanation": doc.get("system_explanation"),
            "correct_classification": doc.get("correct_classification"),
            "user_explanation": doc.get("user_explanation"),
            "correction": correction
        })
    
    return {"feedback": feedback_list, "count": len(feedback_list)}


@router.get("/stats")
async def get_pattern_learning_stats(user: User = Depends(get_current_user)):
    """
    Get statistics about the pattern learning system.
    
    Returns:
    - feedback: Feedback statistics (pending, processed, total)
    - rules: Rule statistics (by status, total triggers, accuracy)
    - corrections: Correction statistics (by motif, usage counts)
    - loaded_rules: Currently active rules summary
    """
    from services.pattern_learning.auto_correction_service import get_auto_correction_service
    
    service = get_auto_correction_service()
    stats = await service.get_system_stats()
    
    return stats


@router.get("/pending-rules")
async def get_pending_rules(user: User = Depends(get_current_user)):
    """
    Get rules pending human review.
    
    Use this to review and approve/reject learned rules.
    """
    from services.pattern_learning.auto_correction_service import get_auto_correction_service
    
    service = get_auto_correction_service()
    pending = await service.get_pending_rules()
    
    return {"rules": pending, "count": len(pending)}


@router.post("/approve-rule")
async def approve_learned_rule(
    request: Dict = Body(...),
    user: User = Depends(get_current_user)
):
    """
    Approve a pending rule to become active.
    
    Body:
    - rule_id: The ID of the rule to approve
    - notes: Optional notes about the approval
    """
    from services.pattern_learning.auto_correction_service import get_auto_correction_service
    
    rule_id = request.get("rule_id")
    if not rule_id:
        raise HTTPException(status_code=400, detail="rule_id is required")
    
    service = get_auto_correction_service()
    result = await service.approve_rule(rule_id, reviewer_id=user.user_id)
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to approve rule"))
    
    return result


@router.post("/reject-rule")
async def reject_learned_rule(
    request: Dict = Body(...),
    user: User = Depends(get_current_user)
):
    """
    Reject a pending rule.
    
    Body:
    - rule_id: The ID of the rule to reject
    - reason: Reason for rejection
    """
    from services.pattern_learning.auto_correction_service import get_auto_correction_service
    
    rule_id = request.get("rule_id")
    reason = request.get("reason", "")
    
    if not rule_id:
        raise HTTPException(status_code=400, detail="rule_id is required")
    
    service = get_auto_correction_service()
    result = await service.reject_rule(rule_id, reason=reason, reviewer_id=user.user_id)
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to reject rule"))
    
    return result


@router.post("/classify")
async def classify_position(
    request: Dict = Body(...),
    user: User = Depends(get_current_user)
):
    """
    Classify a position using the learned rules.
    
    Use this to test how the system would classify a position
    before or after feedback is processed.
    
    Body:
    - position_fen: FEN of the position
    - move_played: Optional - the move that was played
    - eval_before: Optional - evaluation before move
    - eval_after: Optional - evaluation after move
    - best_move: Optional - Stockfish's best move
    
    Returns:
    - matched_rules: List of rules that match this position
    - classification: The determined classification
    - explanation: Generated explanation
    - source: "learned_rule" or "default_classifier"
    """
    from services.pattern_learning.auto_correction_service import get_auto_correction_service
    
    service = get_auto_correction_service()
    
    result = await service.classify_position(
        position_fen=request.get("position_fen", ""),
        move_played=request.get("move_played", ""),
        eval_before=request.get("eval_before"),
        eval_after=request.get("eval_after"),
        best_move=request.get("best_move", "")
    )
    
    return result


@router.post("/track-accuracy")
async def track_rule_accuracy(
    request: Dict = Body(...),
    user: User = Depends(get_current_user)
):
    """
    Track whether a learned rule classification was correct.
    
    Use this after showing a classification to the user to
    update the rule's accuracy statistics.
    
    Body:
    - rule_id: The rule that was used
    - was_correct: True if the classification was correct
    """
    from services.pattern_learning.auto_correction_service import get_auto_correction_service
    
    rule_id = request.get("rule_id")
    was_correct = request.get("was_correct", True)
    
    if not rule_id:
        raise HTTPException(status_code=400, detail="rule_id is required")
    
    service = get_auto_correction_service()
    await service.track_classification_feedback(rule_id, was_correct)
    
    return {
        "success": True,
        "message": "Accuracy tracked"
    }
