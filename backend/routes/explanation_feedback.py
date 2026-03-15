"""
Explanation Feedback Routes
============================

API endpoints for collecting and managing explanation feedback.
Used by beta users to rate explanations and suggest improvements.
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/explanation-feedback", tags=["Explanation Feedback"])

# Database reference - will be set by server.py
db = None

def set_db(database):
    """Set the database reference"""
    global db
    db = database

# Import User model and get_current_user from auth routes
from routes.auth import User, get_current_user


# =============================================================================
# MODELS
# =============================================================================

class FeedbackSubmission(BaseModel):
    """User feedback on an explanation"""
    game_id: str
    move_number: int
    explanation: str
    template_id: str
    feedback_type: str  # "rating" | "correction" | "accuracy"
    rating: Optional[int] = None  # 1-5 stars
    is_helpful: Optional[bool] = None
    suggested_improvement: Optional[str] = None
    is_chess_accurate: Optional[bool] = None


class SuggestionApproval(BaseModel):
    """Coach approval of a suggestion"""
    suggestion_id: str
    action: str  # "add_variation" | "replace_template" | "reject"


class ABTestCreate(BaseModel):
    """Create new A/B test"""
    template_id: str
    variation_a: str
    variation_b: str
    test_name: str
    target_sample_size: int = 100


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.post("/submit")
async def submit_feedback(
    feedback: FeedbackSubmission,
    user: User = Depends(get_current_user)
):
    """
    Submit feedback on an explanation.
    
    Anyone can submit feedback, but coaches/experts get higher weight.
    """
    from services.explanation_feedback_service import submit_explanation_feedback
    
    success = await submit_explanation_feedback(
        db=db,
        user_id=user.user_id,
        game_id=feedback.game_id,
        move_number=feedback.move_number,
        explanation=feedback.explanation,
        template_id=feedback.template_id,
        feedback_type=feedback.feedback_type,
        rating=feedback.rating,
        is_helpful=feedback.is_helpful,
        suggested_improvement=feedback.suggested_improvement,
        is_chess_accurate=feedback.is_chess_accurate,
        user_role=user.role if hasattr(user, 'role') else "player"
    )
    
    if success:
        return {
            "success": True,
            "message": "Feedback recorded. Thank you for helping improve ChessGuru!"
        }
    else:
        raise HTTPException(status_code=500, detail="Failed to record feedback")


@router.get("/performance")
async def get_performance_report(
    min_usage: int = 10,
    user: User = Depends(get_current_user)
):
    """
    Get template performance report.
    
    Shows which explanations users find helpful.
    """
    from services.explanation_feedback_service import get_template_performance_report
    
    report = await get_template_performance_report(db, min_usage)
    return report


@router.get("/suggestions")
async def get_pending_suggestions(
    user_role: Optional[str] = None,
    limit: int = 20,
    user: User = Depends(get_current_user)
):
    """
    Get pending user suggestions.
    
    Coaches can review and approve these.
    """
    from services.explanation_feedback_service import get_pending_suggestions
    
    suggestions = await get_pending_suggestions(db, user_role, limit)
    return {"suggestions": suggestions}


@router.post("/suggestions/approve")
async def approve_user_suggestion(
    approval: SuggestionApproval,
    user: User = Depends(get_current_user)
):
    """
    Approve a user suggestion (coaches/experts only).
    
    This adds the suggestion as a new template variation.
    """
    # Check if user is coach/expert
    if not hasattr(user, 'role') or user.role not in ['coach', 'expert', 'admin']:
        raise HTTPException(status_code=403, detail="Only coaches can approve suggestions")
    
    from services.explanation_feedback_service import approve_suggestion
    
    success = await approve_suggestion(
        db=db,
        suggestion_id=approval.suggestion_id,
        approved_by=user.user_id,
        action=approval.action
    )
    
    if success:
        return {"success": True, "message": "Suggestion approved"}
    else:
        raise HTTPException(status_code=500, detail="Failed to approve suggestion")


@router.post("/ab-test/create")
async def create_ab_test_endpoint(
    test: ABTestCreate,
    user: User = Depends(get_current_user)
):
    """
    Create A/B test for template variations (admin only).
    """
    if not hasattr(user, 'role') or user.role != 'admin':
        raise HTTPException(status_code=403, detail="Admin only")
    
    from services.explanation_feedback_service import create_ab_test
    
    test_id = await create_ab_test(
        db=db,
        template_id=test.template_id,
        variation_a=test.variation_a,
        variation_b=test.variation_b,
        test_name=test.test_name,
        target_sample_size=test.target_sample_size
    )
    
    if test_id:
        return {"success": True, "test_id": test_id}
    else:
        raise HTTPException(status_code=500, detail="Failed to create A/B test")


@router.get("/ab-test/{test_id}")
async def get_ab_test_results_endpoint(
    test_id: str,
    user: User = Depends(get_current_user)
):
    """Get A/B test results"""
    from services.explanation_feedback_service import get_ab_test_results
    
    results = await get_ab_test_results(db, test_id)
    return results


# =============================================================================
# STATS ENDPOINTS (For dashboard)
# =============================================================================

@router.get("/stats/overview")
async def get_feedback_overview(
    user: User = Depends(get_current_user)
):
    """
    Get overall feedback statistics.
    
    Shows how many feedbacks collected, average ratings, etc.
    """
    try:
        # Total feedback count
        total_feedback = await db.explanation_feedback.count_documents({})
        
        # Helpful vs not helpful
        helpful_count = await db.explanation_feedback.count_documents({"is_helpful": True})
        not_helpful_count = await db.explanation_feedback.count_documents({"is_helpful": False})
        
        # Pending suggestions
        pending_suggestions = await db.explanation_feedback.count_documents({
            "feedback_type": "correction",
            "processed": False
        })
        
        # Average rating
        ratings_pipeline = [
            {"$match": {"rating": {"$exists": True, "$ne": None}}},
            {"$group": {"_id": None, "avg_rating": {"$avg": "$rating"}}}
        ]
        rating_result = await db.explanation_feedback.aggregate(ratings_pipeline).to_list(1)
        avg_rating = rating_result[0]["avg_rating"] if rating_result else 0
        
        return {
            "total_feedback": total_feedback,
            "helpful_count": helpful_count,
            "not_helpful_count": not_helpful_count,
            "helpfulness_rate": helpful_count / (helpful_count + not_helpful_count) if (helpful_count + not_helpful_count) > 0 else 0,
            "pending_suggestions": pending_suggestions,
            "average_rating": round(avg_rating, 2)
        }
    
    except Exception as e:
        logger.error(f"Error getting feedback overview: {e}")
        return {"error": str(e)}
