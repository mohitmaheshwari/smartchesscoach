"""
Subscription/Plan Service - Mock Implementation

Handles:
- User plan status (Free/Pro)
- Game analysis limits
- Feature access control

NOTE: This is a mock implementation. Replace with actual payment integration later.
"""

import logging
from typing import Dict, Optional
from datetime import datetime, timezone
from enum import Enum

logger = logging.getLogger(__name__)


class UserPlan(str, Enum):
    FREE = "free"
    PRO = "pro"


# Plan limits.
# daily_pwc_session_limit: how many Play-with-Coach sessions a user can
# START in a 24h window. -1 means unlimited. Counted against
# `coach_sessions.created_at` from UTC midnight today.
PLAN_LIMITS = {
    UserPlan.FREE: {
        "monthly_analysis_limit": 5,
        "daily_pwc_session_limit": 1,
        "auto_sync": False,
        "immediate_feedback": False,
        "llm_commentary": False,
        "priority_analysis": False
    },
    UserPlan.PRO: {
        "monthly_analysis_limit": 25,
        "daily_pwc_session_limit": -1,
        "auto_sync": True,
        "immediate_feedback": True,
        "llm_commentary": True,
        "priority_analysis": True
    }
}


async def get_user_plan(db, user_id: str) -> Dict:
    """
    Get user's current plan and usage.
    """
    user = await db.users.find_one(
        {"user_id": user_id},
        {"_id": 0, "plan": 1, "plan_start_date": 1, "monthly_analyses_used": 1, "analyses_reset_date": 1}
    )
    
    if not user:
        return {
            "plan": UserPlan.FREE.value,
            "limits": PLAN_LIMITS[UserPlan.FREE],
            "usage": {"analyses_used": 0, "analyses_remaining": 5}
        }
    
    plan = UserPlan(user.get("plan", "free"))
    limits = PLAN_LIMITS[plan]
    
    # Check if we need to reset monthly usage
    analyses_used = user.get("monthly_analyses_used", 0)
    reset_date = user.get("analyses_reset_date")
    
    now = datetime.now(timezone.utc)
    if reset_date:
        reset_dt = datetime.fromisoformat(reset_date.replace("Z", "+00:00")) if isinstance(reset_date, str) else reset_date
        # Reset on the 1st of each month
        if now.month != reset_dt.month or now.year != reset_dt.year:
            analyses_used = 0
            await db.users.update_one(
                {"user_id": user_id},
                {"$set": {
                    "monthly_analyses_used": 0,
                    "analyses_reset_date": now.isoformat()
                }}
            )
    
    analyses_remaining = max(0, limits["monthly_analysis_limit"] - analyses_used)
    
    return {
        "plan": plan.value,
        "limits": limits,
        "usage": {
            "analyses_used": analyses_used,
            "analyses_remaining": analyses_remaining,
            "monthly_limit": limits["monthly_analysis_limit"]
        }
    }


async def can_analyze_game(db, user_id: str) -> Dict:
    """
    Check if user can analyze another game.
    Returns analysis permission and reason.
    """
    plan_info = await get_user_plan(db, user_id)
    
    if plan_info["usage"]["analyses_remaining"] > 0:
        return {
            "allowed": True,
            "reason": None,
            "analyses_remaining": plan_info["usage"]["analyses_remaining"]
        }
    
    return {
        "allowed": False,
        "reason": "monthly_limit_reached",
        "message": f"You've reached your monthly limit of {plan_info['limits']['monthly_analysis_limit']} analyses. Upgrade to Pro for more!",
        "upgrade_url": "/upgrade"
    }


async def increment_analysis_count(db, user_id: str) -> int:
    """
    Increment the user's monthly analysis count.
    Returns new count.
    """
    result = await db.users.find_one_and_update(
        {"user_id": user_id},
        {
            "$inc": {"monthly_analyses_used": 1},
            "$set": {"analyses_reset_date": datetime.now(timezone.utc).isoformat()}
        },
        return_document=True
    )
    
    return result.get("monthly_analyses_used", 1) if result else 1


async def count_pwc_sessions_today(db, user_id: str) -> int:
    """How many Play-with-Coach sessions the user has STARTED since UTC
    midnight today. Counts session-creation events, not finished games."""
    from datetime import datetime, timedelta, timezone
    midnight_utc = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    # `created_at` may be stored as a datetime or as an ISO string —
    # query both shapes.
    iso_threshold = midnight_utc.isoformat()
    n = await db.coach_sessions.count_documents({
        "user_id": user_id,
        "$or": [
            {"created_at": {"$gte": midnight_utc}},
            {"created_at": {"$gte": iso_threshold}},
        ],
    })
    return n


async def can_start_pwc_session(db, user_id: str) -> Dict:
    """Gate for the Play-with-Coach /start endpoint.

    Returns:
        {"allowed": bool, "reason": Optional[str], "message": Optional[str],
         "limit": int, "used_today": int, "upgrade_url": Optional[str]}

    Free tier: 1 session/day. Premium: unlimited. DEV_MODE bypasses
    via get_effective_plan.
    """
    plan_info = await get_effective_plan(db, user_id)
    limit = plan_info["limits"].get("daily_pwc_session_limit", 1)

    # -1 = unlimited (Pro tier or dev mode).
    if limit < 0:
        return {"allowed": True, "limit": limit, "used_today": 0}

    used = await count_pwc_sessions_today(db, user_id)
    if used < limit:
        return {
            "allowed": True,
            "limit": limit,
            "used_today": used,
            "remaining": limit - used,
        }

    return {
        "allowed": False,
        "reason": "daily_pwc_limit_reached",
        "limit": limit,
        "used_today": used,
        "message": (
            f"You've used today's free Play with Coach session. "
            f"Upgrade to ChessGuru Premium for unlimited live coaching, "
            f"opening theory notes, and Engine 2 pattern detection."
        ),
        "upgrade_url": "/upgrade",
        "price_inr": 149,
    }


async def has_feature_access(db, user_id: str, feature: str) -> bool:
    """
    Check if user has access to a specific feature.
    Features: auto_sync, immediate_feedback, llm_commentary, priority_analysis
    """
    plan_info = await get_effective_plan(db, user_id)
    return plan_info["limits"].get(feature, False)


async def upgrade_to_pro(db, user_id: str) -> bool:
    """
    Upgrade user to Pro plan.
    NOTE: This is a mock - actual implementation would involve payment.
    """
    result = await db.users.update_one(
        {"user_id": user_id},
        {"$set": {
            "plan": UserPlan.PRO.value,
            "plan_start_date": datetime.now(timezone.utc).isoformat(),
            "monthly_analyses_used": 0,
            "analyses_reset_date": datetime.now(timezone.utc).isoformat()
        }}
    )
    
    logger.info(f"User {user_id} upgraded to Pro")
    return result.modified_count > 0


async def downgrade_to_free(db, user_id: str) -> bool:
    """
    Downgrade user to Free plan.
    """
    result = await db.users.update_one(
        {"user_id": user_id},
        {"$set": {
            "plan": UserPlan.FREE.value
        }}
    )
    
    logger.info(f"User {user_id} downgraded to Free")
    return result.modified_count > 0


# For development/testing - gives everyone Pro access
DEV_MODE_PRO = True

async def get_effective_plan(db, user_id: str) -> Dict:
    """
    Get effective plan considering dev mode + admin/reviewer bypass.

    Admins and reviewers ALWAYS get PRO access. They need to be able to
    play the product they own/audit without being blocked by the same
    freemium gates regular users hit. Locked 2026-05-19 after Mohit got
    paywalled out of his own Play with Coach session mid-debug.
    """
    import os
    if os.environ.get("DEV_MODE", "").lower() == "true" and DEV_MODE_PRO:
        return {
            "plan": UserPlan.PRO.value,
            "limits": PLAN_LIMITS[UserPlan.PRO],
            "usage": {"analyses_used": 0, "analyses_remaining": 999},
            "dev_mode": True,
        }

    # Admin / reviewer bypass — these users need full product access to
    # do their job (build the product, audit content, run debug sessions).
    user = await db.users.find_one(
        {"user_id": user_id},
        {"_id": 0, "role": 1, "is_reviewer": 1},
    )
    if user and (user.get("role") == "super_admin" or user.get("is_reviewer") is True):
        return {
            "plan": UserPlan.PRO.value,
            "limits": PLAN_LIMITS[UserPlan.PRO],
            "usage": {"analyses_used": 0, "analyses_remaining": 999},
            "admin_bypass": True,
        }

    return await get_user_plan(db, user_id)
