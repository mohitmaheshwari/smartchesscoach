"""
Gamification, RAG, and Subscription Routes
============================================

Handles gamification progress/achievements, RAG processing, and subscription management.

Endpoints:
- GET /gamification/progress - Get user's XP, level, streak, and stats
- GET /gamification/achievements - Get all achievements with unlock status
- POST /gamification/daily-reward - Claim daily login reward
- GET /gamification/leaderboard - Get XP leaderboard
- GET /gamification/levels - Get all level definitions
- GET /gamification/achievement-definitions - Get all achievement definitions
- GET /gamification/xp-rewards - Get XP reward values
- POST /rag/process-games - Process games for RAG embeddings
- GET /rag/status - Get RAG processing status
- GET /subscription - Get subscription info
- POST /subscription/upgrade - Upgrade to Pro plan
- GET /subscription/can-analyze - Check if user can analyze another game
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
import logging

logger = logging.getLogger(__name__)

# Create router for gamification/RAG/subscription endpoints
router = APIRouter(tags=["Gamification"])

# Database reference - will be set by server.py
db = None

def set_db(database):
    """Set the database reference for gamification routes"""
    global db
    db = database


# Import User model and get_current_user from auth routes
from routes.auth import User, get_current_user

# Import gamification service
from gamification_service import (
    get_user_progress,
    add_xp,
    update_streak,
    increment_stat,
    update_best_accuracy,
    get_user_achievements,
    check_and_award_achievements,
    claim_daily_reward,
    get_leaderboard,
    LEVELS,
    ACHIEVEMENTS,
    XP_REWARDS
)

# Import RAG service
from rag_service import (
    process_user_games_for_rag
)

# Import Subscription service
from subscription_service import (
    get_effective_plan,
    can_analyze_game,
    upgrade_to_pro
)


# ==================== GAMIFICATION ENDPOINTS ====================

@router.get("/gamification/progress")
async def get_progress(user: User = Depends(get_current_user)):
    """Get user's XP, level, streak, and stats"""
    progress = await get_user_progress(user.user_id)
    return progress

@router.get("/gamification/achievements")
async def get_achievements(user: User = Depends(get_current_user)):
    """Get all achievements with unlock status"""
    achievements = await get_user_achievements(user.user_id)
    return achievements

@router.post("/gamification/daily-reward")
async def claim_daily(user: User = Depends(get_current_user)):
    """Claim daily login reward and update streak"""
    result = await claim_daily_reward(user.user_id)
    return result

@router.get("/gamification/leaderboard")
async def leaderboard(limit: int = 20, user: User = Depends(get_current_user)):
    """Get XP leaderboard"""
    leaders = await get_leaderboard(limit)
    return {"leaderboard": leaders}

@router.get("/gamification/levels")
async def get_levels():
    """Get all level definitions (public endpoint)"""
    return {"levels": LEVELS}

@router.get("/gamification/achievement-definitions")
async def get_achievement_definitions():
    """Get all achievement definitions (public endpoint)"""
    return {"achievements": ACHIEVEMENTS}

@router.get("/gamification/xp-rewards")
async def get_xp_rewards():
    """Get XP reward values (public endpoint)"""
    return {"rewards": XP_REWARDS}


# ==================== RAG ENDPOINTS ====================

@router.post("/rag/process-games")
async def process_games_for_rag(background_tasks: BackgroundTasks, user: User = Depends(get_current_user)):
    """Process all user games to create RAG embeddings"""
    # Start processing in background
    background_tasks.add_task(process_user_games_for_rag, db, user.user_id, 100)

    return {
        "message": "RAG processing started in background",
        "status": "processing"
    }

@router.get("/rag/status")
async def get_rag_status(user: User = Depends(get_current_user)):
    """Get RAG processing status for user"""
    game_embeddings = await db.game_embeddings.count_documents({"user_id": user.user_id})
    pattern_embeddings = await db.pattern_embeddings.count_documents({"user_id": user.user_id})
    analysis_embeddings = await db.analysis_embeddings.count_documents({"user_id": user.user_id})
    total_games = await db.games.count_documents({"user_id": user.user_id})
    total_patterns = await db.mistake_patterns.count_documents({"user_id": user.user_id})
    total_analyses = await db.game_analyses.count_documents({"user_id": user.user_id})

    return {
        "total_games": total_games,
        "game_embeddings": game_embeddings,
        "total_patterns": total_patterns,
        "pattern_embeddings": pattern_embeddings,
        "total_analyses": total_analyses,
        "analysis_embeddings": analysis_embeddings,
        "rag_coverage": {
            "games": f"{(game_embeddings / max(total_games * 4, 1)) * 100:.1f}%",  # 4 chunks per game
            "patterns": f"{(pattern_embeddings / max(total_patterns, 1)) * 100:.1f}%",
            "analyses": f"{(analysis_embeddings / max(total_analyses, 1)) * 100:.1f}%"
        }
    }


# ==================== SUBSCRIPTION ENDPOINTS ====================

@router.get("/subscription")
async def get_subscription_info(user: User = Depends(get_current_user)):
    """
    Get user's subscription/plan information.
    """
    return await get_effective_plan(db, user.user_id)


@router.post("/subscription/upgrade")
async def upgrade_subscription(user: User = Depends(get_current_user)):
    """
    Upgrade user to Pro plan.
    NOTE: This is a mock endpoint. Real implementation would involve payment.
    """
    success = await upgrade_to_pro(db, user.user_id)
    if success:
        return {"success": True, "message": "Upgraded to Pro!", "plan": "pro"}
    return {"success": False, "message": "Failed to upgrade"}


@router.get("/subscription/can-analyze")
async def check_can_analyze(user: User = Depends(get_current_user)):
    """
    Check if user can analyze another game.
    """
    return await can_analyze_game(db, user.user_id)
