"""
V5 Learning Tracker Service
============================

Tracks what the user is learning and getting better at.
Integrates with coach_memory and provides insights for the "Thinking Simulator".

Key Features:
1. Track concepts applied correctly in games
2. Track when user finds the best move
3. Build a "What you're getting better at" profile
4. Detect improvement trends
5. Remember acknowledged concepts
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone, timedelta
from collections import Counter

logger = logging.getLogger(__name__)


async def track_game_learning(
    db,
    user_id: str,
    game_id: str,
    decryption_data: List[Dict]
) -> Dict:
    """
    Analyze a game's decryption data and track learning progress.
    
    Called after V5 analysis is complete.
    
    Returns:
        Summary of what user demonstrated in this game
    """
    if not decryption_data:
        return {"tracked": False, "reason": "No decryption data"}
    
    # Collect concepts demonstrated
    concepts_applied = []
    best_moves_found = 0
    mistakes_made = []
    user_moves = 0
    
    for move_data in decryption_data:
        if not move_data.get("is_user_move"):
            continue
        
        user_moves += 1
        
        # Track concepts applied
        if move_data.get("concept_applied"):
            concepts_applied.append(move_data["concept_applied"])
        
        # Track best moves found
        if move_data.get("is_best_move"):
            best_moves_found += 1
        
        # Track mistakes
        if move_data.get("severity") in ("mistake", "blunder"):
            mistakes_made.append({
                "move_number": move_data.get("move_number"),
                "move_san": move_data.get("move_san"),
                "concept_id": move_data.get("concept_id"),
                "concept_type": move_data.get("concept_type")
            })
    
    # Calculate accuracy
    accuracy = (user_moves - len(mistakes_made)) / user_moves * 100 if user_moves > 0 else 0
    best_move_rate = best_moves_found / user_moves * 100 if user_moves > 0 else 0
    
    # Count concept frequencies
    concept_counts = Counter(concepts_applied)
    
    # Update database
    try:
        # Update user_learning_progress collection
        learning_update = {
            "$push": {
                "games_analyzed": {
                    "game_id": game_id,
                    "date": datetime.now(timezone.utc).isoformat(),
                    "accuracy": round(accuracy, 1),
                    "best_move_rate": round(best_move_rate, 1),
                    "concepts_applied": list(concept_counts.keys()),
                    "mistake_count": len(mistakes_made)
                }
            },
            "$inc": {
                "total_games_analyzed": 1,
                "total_best_moves_found": best_moves_found,
                "total_user_moves": user_moves,
                **{f"concept_applications.{c}": count for c, count in concept_counts.items()}
            },
            "$set": {
                "updated_at": datetime.now(timezone.utc).isoformat()
            },
            "$setOnInsert": {
                "user_id": user_id,
                "created_at": datetime.now(timezone.utc).isoformat()
            }
        }
        
        await db.user_learning_progress.update_one(
            {"user_id": user_id},
            learning_update,
            upsert=True
        )
        
        # Update coach_memory with learning summary
        await db.coach_memory.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "learning.last_game_accuracy": round(accuracy, 1),
                    "learning.last_game_best_moves": best_moves_found,
                    "updated_at": datetime.now(timezone.utc).isoformat()
                },
                "$addToSet": {
                    "learning.concepts_demonstrated": {"$each": list(concept_counts.keys())}
                }
            }
        )
        
        logger.info(f"[LEARNING TRACKER] Tracked game {game_id}: accuracy={accuracy:.1f}%, best_moves={best_moves_found}")
        
    except Exception as e:
        logger.error(f"Error tracking game learning: {e}")
    
    return {
        "tracked": True,
        "accuracy": round(accuracy, 1),
        "best_move_rate": round(best_move_rate, 1),
        "concepts_applied": dict(concept_counts),
        "best_moves_found": best_moves_found,
        "mistakes_made": len(mistakes_made),
        "user_moves": user_moves
    }


async def get_user_strengths(db, user_id: str, limit: int = 5) -> List[Dict]:
    """
    Get what the user is getting better at based on concept applications.
    
    Returns:
        List of strengths with counts and trends
    """
    try:
        progress = await db.user_learning_progress.find_one(
            {"user_id": user_id},
            {"_id": 0, "concept_applications": 1, "games_analyzed": 1}
        )
        
        if not progress:
            return []
        
        concept_apps = progress.get("concept_applications", {})
        
        # Sort by frequency
        sorted_concepts = sorted(
            concept_apps.items(),
            key=lambda x: x[1],
            reverse=True
        )[:limit]
        
        # Format nicely
        strengths = []
        for concept, count in sorted_concepts:
            # Make the concept readable
            readable = concept.replace("_", " ").title()
            
            strengths.append({
                "concept_id": concept,
                "name": readable,
                "times_demonstrated": count,
                "category": _infer_category(concept)
            })
        
        return strengths
        
    except Exception as e:
        logger.error(f"Error getting user strengths: {e}")
        return []


async def get_learning_insights(db, user_id: str) -> Dict:
    """
    Generate learning insights for the user.
    
    Returns:
        Personalized insights about their chess growth
    """
    try:
        progress = await db.user_learning_progress.find_one(
            {"user_id": user_id},
            {"_id": 0}
        )
        
        if not progress:
            return {
                "message": "Keep playing! Your coach is learning about you.",
                "games_analyzed": 0,
                "strengths": [],
                "areas_to_improve": []
            }
        
        total_games = progress.get("total_games_analyzed", 0)
        total_best = progress.get("total_best_moves_found", 0)
        total_moves = progress.get("total_user_moves", 0)
        
        overall_best_rate = (total_best / total_moves * 100) if total_moves > 0 else 0
        
        # Get recent games for trend
        recent_games = progress.get("games_analyzed", [])[-10:]
        
        # Calculate trend
        if len(recent_games) >= 3:
            first_half = recent_games[:len(recent_games)//2]
            second_half = recent_games[len(recent_games)//2:]
            
            first_avg = sum(g.get("accuracy", 0) for g in first_half) / len(first_half)
            second_avg = sum(g.get("accuracy", 0) for g in second_half) / len(second_half)
            
            trend = "improving" if second_avg > first_avg + 2 else ("declining" if second_avg < first_avg - 2 else "stable")
        else:
            trend = "not_enough_data"
        
        # Get strengths
        strengths = await get_user_strengths(db, user_id, limit=3)
        
        # Get acknowledged concepts count
        acked_count = await db.user_concept_understanding.count_documents({
            "user_id": user_id,
            "acknowledged": True
        })
        
        # Generate message
        if total_games < 3:
            message = f"You've analyzed {total_games} games. Keep going — your coach is learning your patterns!"
        elif trend == "improving":
            message = f"Great progress! Your accuracy is improving over the last {len(recent_games)} games."
        elif trend == "declining":
            message = "Your recent games show some struggles. Let's focus on the fundamentals."
        else:
            message = f"You've analyzed {total_games} games with {overall_best_rate:.0f}% best-move rate. Solid work!"
        
        if strengths:
            top_strength = strengths[0]["name"]
            message += f" You're particularly good at {top_strength}."
        
        return {
            "message": message,
            "games_analyzed": total_games,
            "overall_best_move_rate": round(overall_best_rate, 1),
            "concepts_learned": acked_count,
            "trend": trend,
            "strengths": strengths,
            "recent_accuracy": [g.get("accuracy", 0) for g in recent_games]
        }
        
    except Exception as e:
        logger.error(f"Error getting learning insights: {e}")
        return {
            "message": "Keep playing! Your coach is learning about you.",
            "games_analyzed": 0,
            "strengths": [],
            "error": str(e)
        }


async def get_personalized_coaching_context(db, user_id: str) -> Dict:
    """
    Get context for personalizing coaching based on user's history.
    
    Returns:
        Context dict to be used when generating coaching
    """
    try:
        # Get user's acknowledged concepts
        acked_cursor = db.user_concept_understanding.find(
            {"user_id": user_id, "acknowledged": True},
            {"_id": 0, "concept_id": 1}
        )
        acked_concepts = set()
        async for doc in acked_cursor:
            acked_concepts.add(doc.get("concept_id"))
        
        # Get user's strengths
        strengths = await get_user_strengths(db, user_id, limit=5)
        strength_concepts = {s["concept_id"] for s in strengths}
        
        # Get recurring mistakes
        recurring_cursor = db.user_concept_understanding.find(
            {"user_id": user_id, "shown_count": {"$gte": 3}, "acknowledged": False},
            {"_id": 0, "concept_id": 1, "concept_text": 1, "shown_count": 1}
        )
        recurring_issues = []
        async for doc in recurring_cursor:
            recurring_issues.append({
                "concept_id": doc.get("concept_id"),
                "text": doc.get("concept_text"),
                "times_shown": doc.get("shown_count")
            })
        
        return {
            "acknowledged_concepts": list(acked_concepts),
            "strength_concepts": list(strength_concepts),
            "recurring_issues": recurring_issues,
            "personalization_available": bool(acked_concepts or strengths)
        }
        
    except Exception as e:
        logger.error(f"Error getting coaching context: {e}")
        return {
            "acknowledged_concepts": [],
            "strength_concepts": [],
            "recurring_issues": [],
            "personalization_available": False
        }


def _infer_category(concept_id: str) -> str:
    """Infer the category of a concept from its ID."""
    concept_lower = concept_id.lower()
    
    if any(kw in concept_lower for kw in ["opening", "develop", "castle", "center"]):
        return "opening"
    if any(kw in concept_lower for kw in ["fork", "pin", "skewer", "tactic", "attack"]):
        return "tactics"
    if any(kw in concept_lower for kw in ["endgame", "king", "pawn_ending"]):
        return "endgame"
    if any(kw in concept_lower for kw in ["position", "space", "weak", "outpost"]):
        return "positional"
    
    return "general"


# API endpoint helpers
async def format_learning_summary_for_api(db, user_id: str) -> Dict:
    """Format learning data for the frontend API."""
    insights = await get_learning_insights(db, user_id)
    strengths = await get_user_strengths(db, user_id, limit=5)
    
    return {
        "summary": insights.get("message", ""),
        "stats": {
            "games_analyzed": insights.get("games_analyzed", 0),
            "best_move_rate": insights.get("overall_best_move_rate", 0),
            "concepts_learned": insights.get("concepts_learned", 0)
        },
        "trend": insights.get("trend", "not_enough_data"),
        "strengths": strengths,
        "recent_accuracy": insights.get("recent_accuracy", [])
    }
