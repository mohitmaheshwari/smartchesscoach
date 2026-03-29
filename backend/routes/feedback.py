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
from datetime import datetime, timezone
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


@router.post("/quick-rating")
async def submit_quick_rating(
    request: Dict = Body(...),
    user: User = Depends(get_current_user)
):
    """
    Quick thumbs up/down rating for explanations.
    
    Lightweight feedback - just track if explanation was helpful.
    Extends existing feedback system with simple rating.
    
    Body:
    - template_id: ID of template that generated explanation (optional)
    - generation_method: "template" | "llm" | "smart_pattern"
    - is_helpful: true | false
    - game_id: Game ID for context
    - move_number: Move number
    - explanation_text: The explanation shown (for reference)
    
    Returns:
    - success: True if rating was recorded
    """
    global db
    
    try:
        # Store quick rating
        rating_doc = {
            "user_id": user.user_id,
            "template_id": request.get("template_id"),
            "generation_method": request.get("generation_method", "unknown"),
            "is_helpful": request.get("is_helpful"),
            "game_id": request.get("game_id"),
            "move_number": request.get("move_number"),
            "explanation_text": request.get("explanation_text", ""),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "rating_type": "quick"
        }
        
        await db.explanation_ratings.insert_one(rating_doc)
        
        # Update template stats if template_id provided
        if request.get("template_id"):
            await db.template_stats.update_one(
                {"template_id": request["template_id"]},
                {
                    "$inc": {
                        "total_ratings": 1,
                        "helpful_count" if request.get("is_helpful") else "not_helpful_count": 1
                    },
                    "$set": {
                        "last_rated": datetime.now(timezone.utc).isoformat()
                    }
                },
                upsert=True
            )
        
        logger.info(f"Quick rating submitted: template={request.get('template_id')}, helpful={request.get('is_helpful')}")
        
        return {
            "success": True,
            "message": "Thanks for your feedback!"
        }
    
    except Exception as e:
        logger.error(f"Error submitting quick rating: {e}")
        raise HTTPException(status_code=500, detail="Failed to record rating")


@router.get("/template-performance")
async def get_template_performance(
    min_ratings: int = 5,
    user: User = Depends(get_current_user)
):
    """
    Get performance statistics for explanation templates.
    
    Shows which templates users find helpful.
    Complements existing pattern learning stats.
    
    Args:
        min_ratings: Minimum ratings before showing (default: 5)
    
    Returns:
        Performance report with high/low performers
    """
    global db
    
    try:
        # Get all template stats
        stats_cursor = db.template_stats.find({
            "total_ratings": {"$gte": min_ratings}
        })
        
        stats = await stats_cursor.to_list(100)
        
        high_performers = []
        low_performers = []
        
        for stat in stats:
            template_id = stat.get("template_id")
            total = stat.get("total_ratings", 0)
            helpful = stat.get("helpful_count", 0)
            not_helpful = stat.get("not_helpful_count", 0)
            
            if total == 0:
                continue
            
            helpfulness_rate = helpful / total if total > 0 else 0
            
            template_info = {
                "template_id": template_id,
                "total_ratings": total,
                "helpful_count": helpful,
                "not_helpful_count": not_helpful,
                "helpfulness_rate": round(helpfulness_rate, 3),
                "last_rated": stat.get("last_rated")
            }
            
            if helpfulness_rate >= 0.7:
                high_performers.append(template_info)
            elif helpfulness_rate < 0.4:
                low_performers.append(template_info)
        
        # Sort by helpfulness rate
        high_performers.sort(key=lambda x: x["helpfulness_rate"], reverse=True)
        low_performers.sort(key=lambda x: x["helpfulness_rate"])
        
        return {
            "high_performers": high_performers[:10],
            "low_performers": low_performers[:10],
            "total_templates_rated": len(stats),
            "recommendation": (
                f"Found {len(high_performers)} high-performing templates (>70% helpful) "
                f"and {len(low_performers)} low-performing templates (<40% helpful)."
            )
        }
    
    except Exception as e:
        logger.error(f"Error getting template performance: {e}")
        raise HTTPException(status_code=500, detail="Failed to get performance stats")



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
    - loaded_rules: Currently active rules from smart_patterns
    - system_health: Whether auto-correction is working
    """
    from services.pattern_learning.auto_correction_service import get_auto_correction_service
    
    service = get_auto_correction_service()
    stats = await service.get_system_stats()
    
    # Add smart_patterns stats (the actual loaded patterns)
    smart_count = await db.smart_patterns.count_documents({})
    patterns_by_type = {}
    async for p in db.smart_patterns.find({}, {"pattern_type": 1, "_id": 0}):
        ptype = p.get("pattern_type", "unknown")
        patterns_by_type[ptype] = patterns_by_type.get(ptype, 0) + 1
    
    # Add match history stats
    match_count = await db.pattern_match_history.count_documents({})
    
    stats["loaded_rules"] = {
        "total": smart_count,
        "by_pattern": patterns_by_type
    }
    
    stats["system_health"] = {
        "patterns_loaded": smart_count > 0,
        "total_matches_applied": match_count,
        "status": "active" if smart_count > 0 else "no_patterns"
    }
    
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
    
    try:
        await service.approve_rule(rule_id, approved_by=user.user_id)
        return {"success": True, "message": f"Rule {rule_id} approved"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


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
    reason = request.get("reason", "Rejected by user")
    
    if not rule_id:
        raise HTTPException(status_code=400, detail="rule_id is required")
    
    service = get_auto_correction_service()
    
    try:
        await service.reject_rule(rule_id, reason=reason)
        return {"success": True, "message": f"Rule {rule_id} rejected"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


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
    - pv_after_played: Optional - principal variation after move
    - user_color: Optional - "white" or "black"
    
    Returns:
    - matched_rules: List of rules that match this position
    - classification: The determined classification
    - explanation: Generated explanation
    - source: "learned_rule" or "default_classifier"
    """
    from services.pattern_learning.auto_correction_service import get_auto_correction_service
    
    service = get_auto_correction_service()
    
    position_fen = request.get("position_fen", "")
    if not position_fen:
        raise HTTPException(status_code=400, detail="position_fen is required")
    
    # Calculate eval_drop from eval_before and eval_after
    eval_before = request.get("eval_before", 0.0) or 0.0
    eval_after = request.get("eval_after", 0.0) or 0.0
    eval_drop = abs(eval_before - eval_after)
    
    # Use the correct method signature from the service
    result = await service.classify_with_learned_rules(
        position_fen=position_fen,
        move_played=request.get("move_played", ""),
        pv_after_played=request.get("pv_after_played", []),
        eval_drop=eval_drop,
        best_move=request.get("best_move"),
        user_color=request.get("user_color", "white")
    )
    
    if result:
        return {
            "matched": True,
            "classification": result.classification if hasattr(result, 'classification') else str(result),
            "explanation": result.explanation if hasattr(result, 'explanation') else None,
            "source": "learned_rule"
        }
    else:
        return {
            "matched": False,
            "classification": None,
            "explanation": None,
            "source": "no_matching_rules"
        }


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


@router.post("/process-pending-feedback")
async def process_pending_feedback(
    request: Dict = Body(default={}),
    user: User = Depends(get_current_user)
):
    """
    Process pending feedback items and generate smart patterns.
    
    This batch processes all pending feedback to:
    1. Analyze each feedback using the AI pattern extractor
    2. Generate smart_patterns for position matching
    3. Update feedback status to 'processed'
    
    Body:
    - limit: Max items to process (default: 10)
    - dry_run: If true, analyze but don't save patterns (default: false)
    """
    global db
    import uuid
    from datetime import datetime, timezone
    
    limit = request.get("limit", 10)
    dry_run = request.get("dry_run", False)
    
    # Get pending feedback items
    pending = await db.pattern_feedback.find(
        {"status": "pending"},
        {"_id": 0}
    ).limit(limit).to_list(length=limit)
    
    if not pending:
        return {
            "success": True,
            "processed": 0,
            "message": "No pending feedback to process"
        }
    
    processed = []
    errors = []
    
    # Import the pattern extractor
    try:
        from services.pattern_learning.deep_position_analyzer import SmartPatternExtractor
        extractor = SmartPatternExtractor()
    except Exception as e:
        logger.error(f"Failed to import pattern extractor: {e}")
        raise HTTPException(status_code=500, detail="Pattern extractor unavailable")
    
    for feedback in pending:
        try:
            feedback_id = feedback.get("feedback_id")
            user_explanation = feedback.get("user_explanation", "")
            
            if not user_explanation:
                # Mark as skipped - no user explanation to learn from
                if not dry_run:
                    await db.pattern_feedback.update_one(
                        {"feedback_id": feedback_id},
                        {"$set": {"status": "skipped", "skip_reason": "no_user_explanation"}}
                    )
                errors.append({
                    "feedback_id": feedback_id,
                    "error": "No user explanation provided"
                })
                continue
            
            # Prepare for extraction
            extractor_feedback = {
                "feedback_id": feedback_id,
                "position_fen": feedback.get("position_fen", ""),
                "move_played": feedback.get("move_played", ""),
                "move_san": feedback.get("move_san", ""),
                "best_move": feedback.get("best_move", ""),
                "user_explanation": user_explanation,
                "correct_classification": feedback.get("correct_classification", ""),
            }
            
            # Extract pattern
            rule = await extractor.extract_pattern(extractor_feedback)
            
            if rule and not dry_run:
                # Store the smart pattern
                await db.smart_patterns.update_one(
                    {"rule_id": rule["rule_id"]},
                    {"$set": rule},
                    upsert=True
                )
                
                # Update feedback status
                await db.pattern_feedback.update_one(
                    {"feedback_id": feedback_id},
                    {"$set": {
                        "status": "processed",
                        "processed_at": datetime.now(timezone.utc).isoformat(),
                        "generated_rule_id": rule["rule_id"]
                    }}
                )
                
                processed.append({
                    "feedback_id": feedback_id,
                    "pattern_type": rule.get("pattern_type"),
                    "rule_id": rule["rule_id"],
                    "explanation": rule.get("explanation_template", "")[:100]
                })
            elif rule:
                # Dry run - just report
                processed.append({
                    "feedback_id": feedback_id,
                    "pattern_type": rule.get("pattern_type"),
                    "rule_id": rule["rule_id"],
                    "dry_run": True
                })
            else:
                # Couldn't extract a pattern
                if not dry_run:
                    await db.pattern_feedback.update_one(
                        {"feedback_id": feedback_id},
                        {"$set": {"status": "unprocessable", "skip_reason": "no_pattern_extracted"}}
                    )
                errors.append({
                    "feedback_id": feedback_id,
                    "error": "Could not extract pattern"
                })
                
        except Exception as e:
            logger.error(f"Error processing feedback {feedback.get('feedback_id')}: {e}")
            errors.append({
                "feedback_id": feedback.get("feedback_id"),
                "error": str(e)
            })
    
    return {
        "success": True,
        "processed": len(processed),
        "errors": len(errors),
        "total_pending": len(pending),
        "results": processed,
        "error_details": errors[:5],  # Limit error details
        "dry_run": dry_run
    }


@router.get("/pending-feedback")
async def get_pending_feedback(
    limit: int = 10,
    user: User = Depends(get_current_user)
):
    """Get pending feedback items waiting to be processed"""
    global db
    
    pending = await db.pattern_feedback.find(
        {"status": "pending"},
        {"_id": 0}
    ).limit(limit).to_list(length=limit)
    
    total = await db.pattern_feedback.count_documents({"status": "pending"})
    
    return {
        "items": pending,
        "count": len(pending),
        "total": total
    }


# ==================== TAG FEEDBACK ENDPOINTS ====================

@router.post("/tag-feedback")
async def submit_tag_feedback(
    request: Dict = Body(...),
    user: User = Depends(get_current_user)
):
    """
    Submit feedback when a game tag is wrong.
    
    This connects the 33 game tags to the auto-correction system.
    When users disagree with a tag, the system learns and improves.
    
    Body:
    - game_id: Game where the tag was applied
    - move_number: Move number with the tag
    - position_fen: FEN of the position
    - move_san: The move played (SAN notation)
    - current_tag: The tag the system assigned (e.g., "missed_fork")
    - correct_tag: What the user says it should be (e.g., "hung_piece" or "none")
    - user_explanation: Why the user thinks it's different (optional)
    - cp_loss: Centipawn loss of the move (optional)
    - phase: Game phase - opening/middlegame/endgame (optional)
    
    Returns:
    - success: True if feedback was processed
    - feedback_id: ID of the stored feedback
    - learning_status: "queued", "pattern_generated", or "acknowledged"
    """
    from services.tag_feedback_service import TagFeedbackService
    
    service = TagFeedbackService(db)
    
    result = await service.submit_tag_feedback(
        user_id=user.user_id,
        game_id=request.get("game_id", ""),
        move_number=request.get("move_number", 0),
        position_fen=request.get("position_fen", ""),
        move_san=request.get("move_san", ""),
        current_tag=request.get("current_tag", ""),
        correct_tag=request.get("correct_tag", ""),
        user_explanation=request.get("user_explanation", ""),
        cp_loss=request.get("cp_loss", 0),
        phase=request.get("phase", "middlegame")
    )
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to process feedback"))
    
    return result


@router.get("/tag-feedback/stats")
async def get_tag_feedback_stats(user: User = Depends(get_current_user)):
    """
    Get statistics about tag feedback and corrections.
    
    Returns:
    - total_feedback: Total tag feedback submissions
    - processed: Processed feedback count
    - pending: Pending feedback count
    - total_correction_patterns: Number of learned correction patterns
    - active_correction_patterns: Active patterns being applied
    - top_corrections: Most common tag corrections
    """
    from services.tag_feedback_service import TagFeedbackService
    
    service = TagFeedbackService(db)
    stats = await service.get_tag_feedback_stats()
    
    return stats


@router.get("/tag-feedback/pending")
async def get_pending_tag_feedback(
    limit: int = 20,
    user: User = Depends(get_current_user)
):
    """
    Get pending tag feedback items.
    
    Returns list of tag feedback waiting to be processed.
    """
    from services.tag_feedback_service import TagFeedbackService
    
    service = TagFeedbackService(db)
    pending = await service.get_pending_tag_feedback(limit)
    
    return {
        "items": pending,
        "count": len(pending)
    }


@router.get("/available-tags")
async def get_available_tags(user: User = Depends(get_current_user)):
    """
    Get all available game tags that users can correct to.
    
    Returns the 33 comprehensive tags with their labels and descriptions.
    """
    from services.game_tagging_service import GAME_TAGS, get_tag_label, get_tag_description
    
    tags = []
    for tag_id, tag_info in GAME_TAGS.items():
        tags.append({
            "id": tag_id,
            "label": tag_info.get("label", tag_id),
            "description": tag_info.get("description", ""),
            "category": tag_info.get("category", "other"),
            "phase": tag_info.get("phase")
        })
    
    # Group by category
    by_category = {}
    for tag in tags:
        cat = tag["category"]
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(tag)
    
    return {
        "tags": tags,
        "by_category": by_category,
        "total": len(tags)
    }



@router.get("/pattern-quality")
async def get_pattern_quality(user: User = Depends(get_current_user)):
    """
    Get pattern quality report for monitoring and tuning.
    
    Returns:
    - Overall quality score
    - Breakdown by quality level
    - Pattern types and counts
    - Issues and recommendations
    """
    global db
    from services.pattern_quality_service import get_pattern_quality_report
    
    report = await get_pattern_quality_report(db)
    return report


@router.post("/pattern-quality/optimize")
async def optimize_patterns(user: User = Depends(get_current_user)):
    """
    Attempt to auto-fix common issues in low-quality patterns.
    
    This is a maintenance operation that:
    - Fixes empty criteria fields
    - Infers attacker pieces from geometry
    - Removes duplicate patterns
    """
    global db
    from services.pattern_quality_service import optimize_low_quality_patterns
    
    result = await optimize_low_quality_patterns(db)
    return result


@router.get("/pattern-effectiveness")
async def get_pattern_effectiveness(user: User = Depends(get_current_user)):
    """
    Get effectiveness metrics for pattern matching.
    
    Shows which pattern types are actually matching positions
    and how often patterns are reused.
    """
    global db
    from services.pattern_quality_service import get_pattern_effectiveness
    
    result = await get_pattern_effectiveness(db)
    return result
