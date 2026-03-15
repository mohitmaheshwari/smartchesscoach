"""
Explanation Feedback & Auto-Improvement System
===============================================

Beta users can rate explanations and suggest improvements.
System learns from feedback to improve templates over time.

Feedback Types:
1. Simple rating (helpful / not helpful)
2. Correction submission (coach suggests better explanation)
3. Pattern reporting (explanation doesn't match what happened)

Auto-Improvement:
- Track which templates get positive feedback
- Demote templates with negative feedback
- Learn new variations from coach suggestions
- A/B test template variations
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)


# =============================================================================
# FEEDBACK COLLECTION
# =============================================================================

async def submit_explanation_feedback(
    db: AsyncIOMotorDatabase,
    user_id: str,
    game_id: str,
    move_number: int,
    explanation: str,
    template_id: str,
    feedback_type: str,
    rating: Optional[int] = None,  # 1-5 stars
    is_helpful: Optional[bool] = None,
    suggested_improvement: Optional[str] = None,
    is_chess_accurate: Optional[bool] = None,
    user_role: str = "player"  # player | coach | expert
) -> bool:
    """
    Record user feedback on an explanation.
    
    Args:
        db: MongoDB database
        user_id: Who submitted feedback
        game_id: Which game
        move_number: Which move
        explanation: The explanation that was shown
        template_id: Template used to generate it
        feedback_type: "rating" | "correction" | "accuracy"
        rating: 1-5 stars (optional)
        is_helpful: Simple yes/no (optional)
        suggested_improvement: Better explanation text (optional)
        is_chess_accurate: Was the chess analysis correct? (optional)
        user_role: Player, coach, or expert
        
    Returns:
        True if successful
    """
    try:
        feedback_doc = {
            "user_id": user_id,
            "game_id": game_id,
            "move_number": move_number,
            "explanation": explanation,
            "template_id": template_id,
            "feedback_type": feedback_type,
            "rating": rating,
            "is_helpful": is_helpful,
            "suggested_improvement": suggested_improvement,
            "is_chess_accurate": is_chess_accurate,
            "user_role": user_role,  # Weight coach/expert feedback higher
            "created_at": datetime.now(timezone.utc),
            "processed": False,  # For batch processing
            "approved_by_coach": None  # For suggestions
        }
        
        await db.explanation_feedback.insert_one(feedback_doc)
        
        # Update template stats in real-time
        await _update_template_stats(db, template_id, is_helpful, rating, user_role)
        
        logger.info(f"Feedback collected for template {template_id}: helpful={is_helpful}, rating={rating}")
        return True
    
    except Exception as e:
        logger.error(f"Error submitting feedback: {e}")
        return False


async def _update_template_stats(
    db: AsyncIOMotorDatabase,
    template_id: str,
    is_helpful: Optional[bool],
    rating: Optional[int],
    user_role: str
):
    """Update template statistics based on feedback"""
    try:
        # Weight based on user role
        weight = {
            "player": 1.0,
            "coach": 3.0,
            "expert": 5.0
        }.get(user_role, 1.0)
        
        update_fields = {
            "$inc": {"usage_count": 1}
        }
        
        if is_helpful is not None:
            if is_helpful:
                update_fields["$inc"]["positive_feedback"] = weight
            else:
                update_fields["$inc"]["negative_feedback"] = weight
        
        if rating is not None:
            # Update average rating
            update_fields["$push"] = {
                "ratings": {
                    "score": rating,
                    "weight": weight,
                    "timestamp": datetime.now(timezone.utc)
                }
            }
        
        await db.template_stats.update_one(
            {"template_id": template_id},
            update_fields,
            upsert=True
        )
    
    except Exception as e:
        logger.error(f"Error updating template stats: {e}")


# =============================================================================
# TEMPLATE QUALITY ANALYSIS
# =============================================================================

async def get_template_performance_report(
    db: AsyncIOMotorDatabase,
    min_usage: int = 10
) -> Dict[str, Any]:
    """
    Generate performance report for all templates.
    
    Shows which templates work well, which need improvement.
    
    Args:
        db: MongoDB database
        min_usage: Minimum uses before rating (statistical significance)
        
    Returns:
        Report with high/low performing templates
    """
    try:
        stats = await db.template_stats.find({}).to_list(1000)
        
        high_performers = []
        low_performers = []
        needs_more_data = []
        
        for stat in stats:
            template_id = stat.get("template_id")
            usage = stat.get("usage_count", 0)
            positive = stat.get("positive_feedback", 0)
            negative = stat.get("negative_feedback", 0)
            
            if usage < min_usage:
                needs_more_data.append({
                    "template_id": template_id,
                    "usage_count": usage,
                    "status": "needs_more_data"
                })
                continue
            
            # Calculate effectiveness score
            total_feedback = positive + negative
            if total_feedback == 0:
                continue
            
            effectiveness = positive / total_feedback
            
            template_info = {
                "template_id": template_id,
                "usage_count": usage,
                "positive_feedback": positive,
                "negative_feedback": negative,
                "effectiveness": round(effectiveness, 3),
                "confidence": _calculate_confidence(usage, positive, negative)
            }
            
            if effectiveness >= 0.7:
                high_performers.append(template_info)
            elif effectiveness < 0.4:
                low_performers.append(template_info)
        
        # Sort by effectiveness
        high_performers.sort(key=lambda x: x["effectiveness"], reverse=True)
        low_performers.sort(key=lambda x: x["effectiveness"])
        
        return {
            "total_templates": len(stats),
            "high_performers": high_performers[:10],
            "low_performers": low_performers[:10],
            "needs_more_data": len(needs_more_data),
            "recommendations": _generate_template_recommendations(
                high_performers,
                low_performers
            )
        }
    
    except Exception as e:
        logger.error(f"Error generating performance report: {e}")
        return {"error": str(e)}


def _calculate_confidence(usage: int, positive: float, negative: float) -> float:
    """
    Calculate confidence score for template effectiveness.
    More usage = higher confidence.
    """
    if usage < 10:
        return 0.3
    elif usage < 50:
        return 0.6
    elif usage < 100:
        return 0.8
    else:
        return 0.95


def _generate_template_recommendations(
    high_performers: List[Dict],
    low_performers: List[Dict]
) -> List[str]:
    """Generate actionable recommendations from template performance"""
    recommendations = []
    
    if low_performers:
        recommendations.append(
            f"Found {len(low_performers)} underperforming templates. "
            "Review these for chess accuracy or clarity issues."
        )
    
    if high_performers:
        recommendations.append(
            f"{len(high_performers)} templates performing excellently (>70% positive feedback). "
            "Consider creating variations of these patterns."
        )
    
    return recommendations


# =============================================================================
# AUTO-IMPROVEMENT FROM SUGGESTIONS
# =============================================================================

async def get_pending_suggestions(
    db: AsyncIOMotorDatabase,
    user_role: Optional[str] = None,
    limit: int = 20
) -> List[Dict]:
    """
    Get user suggestions that haven't been reviewed yet.
    Coaches/experts can approve these to improve templates.
    
    Args:
        db: MongoDB database
        user_role: Filter by suggester role (coach/expert suggestions prioritized)
        limit: Max suggestions to return
        
    Returns:
        List of pending suggestions
    """
    try:
        query = {
            "feedback_type": "correction",
            "suggested_improvement": {"$exists": True, "$ne": None},
            "processed": False
        }
        
        if user_role:
            query["user_role"] = user_role
        
        suggestions = await db.explanation_feedback.find(query).limit(limit).to_list(limit)
        
        return [{
            "suggestion_id": str(s["_id"]),
            "template_id": s.get("template_id"),
            "original_explanation": s.get("explanation"),
            "suggested_improvement": s.get("suggested_improvement"),
            "user_role": s.get("user_role"),
            "game_id": s.get("game_id"),
            "move_number": s.get("move_number"),
            "submitted_at": s.get("created_at")
        } for s in suggestions]
    
    except Exception as e:
        logger.error(f"Error fetching suggestions: {e}")
        return []


async def approve_suggestion(
    db: AsyncIOMotorDatabase,
    suggestion_id: str,
    approved_by: str,
    action: str = "add_variation"  # add_variation | replace_template | reject
) -> bool:
    """
    Approve a user suggestion and apply it.
    
    Args:
        db: MongoDB database
        suggestion_id: ID of the suggestion
        approved_by: Coach/expert who approved it
        action: What to do with the suggestion
        
    Returns:
        True if successful
    """
    try:
        from bson import ObjectId
        
        suggestion = await db.explanation_feedback.find_one({"_id": ObjectId(suggestion_id)})
        
        if not suggestion:
            return False
        
        template_id = suggestion.get("template_id")
        new_text = suggestion.get("suggested_improvement")
        
        if action == "add_variation":
            # Add this as a new template variation
            await db.template_variations.insert_one({
                "base_template_id": template_id,
                "text": new_text,
                "source": "user_suggestion",
                "approved_by": approved_by,
                "approved_at": datetime.now(timezone.utc),
                "usage_count": 0,
                "positive_feedback": 0,
                "negative_feedback": 0,
                "status": "active"
            })
            logger.info(f"Added new template variation from suggestion {suggestion_id}")
        
        elif action == "replace_template":
            # Replace the original template (for major improvements)
            await db.template_versions.insert_one({
                "template_id": template_id,
                "old_text": suggestion.get("explanation"),
                "new_text": new_text,
                "replaced_by": approved_by,
                "replaced_at": datetime.now(timezone.utc),
                "reason": "user_suggestion_approved"
            })
            logger.info(f"Replaced template {template_id} with suggestion {suggestion_id}")
        
        # Mark suggestion as processed
        await db.explanation_feedback.update_one(
            {"_id": ObjectId(suggestion_id)},
            {
                "$set": {
                    "processed": True,
                    "approved_by_coach": approved_by,
                    "action_taken": action,
                    "processed_at": datetime.now(timezone.utc)
                }
            }
        )
        
        return True
    
    except Exception as e:
        logger.error(f"Error approving suggestion: {e}")
        return False


# =============================================================================
# A/B TESTING
# =============================================================================

async def create_ab_test(
    db: AsyncIOMotorDatabase,
    template_id: str,
    variation_a: str,
    variation_b: str,
    test_name: str,
    target_sample_size: int = 100
) -> str:
    """
    Create A/B test for two template variations.
    System will randomly show A or B and track which performs better.
    
    Args:
        db: MongoDB database
        template_id: Base template being tested
        variation_a: First variation
        variation_b: Second variation
        test_name: Descriptive name
        target_sample_size: How many users before declaring winner
        
    Returns:
        Test ID
    """
    try:
        test_doc = {
            "test_name": test_name,
            "template_id": template_id,
            "variations": {
                "a": {
                    "text": variation_a,
                    "shown_count": 0,
                    "positive_feedback": 0,
                    "negative_feedback": 0
                },
                "b": {
                    "text": variation_b,
                    "shown_count": 0,
                    "positive_feedback": 0,
                    "negative_feedback": 0
                }
            },
            "target_sample_size": target_sample_size,
            "status": "active",
            "created_at": datetime.now(timezone.utc),
            "completed_at": None,
            "winner": None
        }
        
        result = await db.ab_tests.insert_one(test_doc)
        logger.info(f"Created A/B test: {test_name}")
        return str(result.inserted_id)
    
    except Exception as e:
        logger.error(f"Error creating A/B test: {e}")
        return None


async def get_ab_test_results(
    db: AsyncIOMotorDatabase,
    test_id: str
) -> Dict[str, Any]:
    """Get results of an A/B test"""
    try:
        from bson import ObjectId
        
        test = await db.ab_tests.find_one({"_id": ObjectId(test_id)})
        
        if not test:
            return {"error": "Test not found"}
        
        var_a = test["variations"]["a"]
        var_b = test["variations"]["b"]
        
        # Calculate win rates
        a_total = var_a["positive_feedback"] + var_a["negative_feedback"]
        b_total = var_b["positive_feedback"] + var_b["negative_feedback"]
        
        a_win_rate = var_a["positive_feedback"] / a_total if a_total > 0 else 0
        b_win_rate = var_b["positive_feedback"] / b_total if b_total > 0 else 0
        
        # Determine if test is complete
        sample_size = var_a["shown_count"] + var_b["shown_count"]
        is_complete = sample_size >= test["target_sample_size"]
        
        winner = None
        if is_complete:
            winner = "a" if a_win_rate > b_win_rate else "b"
        
        return {
            "test_name": test["test_name"],
            "status": "complete" if is_complete else "active",
            "sample_size": sample_size,
            "target": test["target_sample_size"],
            "variation_a": {
                "shown": var_a["shown_count"],
                "win_rate": round(a_win_rate, 3),
                "positive": var_a["positive_feedback"],
                "negative": var_a["negative_feedback"]
            },
            "variation_b": {
                "shown": var_b["shown_count"],
                "win_rate": round(b_win_rate, 3),
                "positive": var_b["positive_feedback"],
                "negative": var_b["negative_feedback"]
            },
            "winner": winner,
            "confidence": "high" if sample_size >= test["target_sample_size"] else "low"
        }
    
    except Exception as e:
        logger.error(f"Error getting A/B test results: {e}")
        return {"error": str(e)}
