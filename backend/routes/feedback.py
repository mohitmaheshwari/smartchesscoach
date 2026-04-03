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


# /feedback moved to routes/coach_advanced.py


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



# /my-feedback moved to routes/coach_advanced.py


# /stats, /pending-rules, /approve-rule, /reject-rule, /classify, /track-accuracy
# moved to routes/coach_advanced.py


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
    from services.game_tagging_service import GAME_TAGS
    
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
