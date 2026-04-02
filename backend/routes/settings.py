"""
Settings Routes
===============

Handles user settings, email notifications, profile, and onboarding.

Endpoints:
- GET /settings/email-notifications - Get email notification preferences
- PUT /settings/email-notifications - Update email notification preferences
- POST /settings/test-email - Send test email
- GET /onboarding/status - Check onboarding status
- POST /settings/profile - Update profile settings
- POST /settings/link-account - Link chess account
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

# Create router for settings endpoints
router = APIRouter(tags=["Settings"])

# Database reference - will be set by server.py
db = None

def set_db(database):
    """Set the database reference for settings routes"""
    global db
    db = database


# Import User model and get_current_user from auth routes
from routes.auth import User, get_current_user


# ==================== MODELS ====================

class EmailNotificationSettings(BaseModel):
    game_analyzed: bool = True
    weekly_summary: bool = True
    weakness_alert: bool = True


class ProfileSettingsRequest(BaseModel):
    fide_rating: Optional[int] = None
    detected_rating: Optional[int] = None  # Auto-detected from linked account
    detected_platform: Optional[str] = None  # chess.com or lichess
    focus_intent: Optional[str] = None  # tactics, openings, endgames, stability


class LinkAccountRequest(BaseModel):
    """Request model for linking chess accounts"""
    platform: str  # "chess.com" or "lichess"
    username: str


# ==================== EMAIL NOTIFICATION SETTINGS ====================

@router.get("/settings/email-notifications")
async def get_email_notification_settings(user: User = Depends(get_current_user)):
    """Get user's email notification preferences"""
    global db
    
    user_doc = await db.users.find_one(
        {"user_id": user.user_id},
        {"_id": 0, "email_notifications": 1, "email": 1}
    )
    
    if not user_doc:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Default settings if not set
    default_settings = {
        "game_analyzed": True,
        "weekly_summary": True,
        "weakness_alert": True
    }
    
    return {
        "email": user_doc.get("email", ""),
        "notifications": user_doc.get("email_notifications", default_settings)
    }


@router.put("/settings/email-notifications")
async def update_email_notification_settings(
    settings: EmailNotificationSettings,
    user: User = Depends(get_current_user)
):
    """Update user's email notification preferences"""
    global db
    
    await db.users.update_one(
        {"user_id": user.user_id},
        {"$set": {
            "email_notifications": {
                "game_analyzed": settings.game_analyzed,
                "weekly_summary": settings.weekly_summary,
                "weakness_alert": settings.weakness_alert
            }
        }}
    )
    
    return {
        "message": "Email notification settings updated",
        "notifications": {
            "game_analyzed": settings.game_analyzed,
            "weekly_summary": settings.weekly_summary,
            "weakness_alert": settings.weakness_alert
        }
    }


@router.post("/settings/test-email")
async def send_test_email(user: User = Depends(get_current_user)):
    """Send a test email to verify email configuration"""
    global db
    from email_service import send_email, is_email_configured
    
    if not is_email_configured():
        raise HTTPException(
            status_code=503, 
            detail="Email service not configured. Please add SENDGRID_API_KEY to environment."
        )
    
    user_doc = await db.users.find_one(
        {"user_id": user.user_id},
        {"_id": 0, "email": 1, "name": 1}
    )
    
    if not user_doc or not user_doc.get("email"):
        raise HTTPException(status_code=400, detail="No email address found for user")
    
    subject = "Chess Coach AI - Test Email"
    html_content = f"""
    <html>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
        <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
            <h2>Email Test Successful!</h2>
            <p>Hey {user_doc.get('name', 'Chess Player')}!</p>
            <p>Great news - your email notifications are working correctly.</p>
            <p>You'll receive notifications when:</p>
            <ul>
                <li>New games are analyzed</li>
                <li>Weekly progress summaries are ready</li>
                <li>Recurring weaknesses are detected</li>
            </ul>
            <p>Keep improving your game!</p>
            <p><em>— Your Chess Coach</em></p>
        </div>
    </body>
    </html>
    """
    
    success = await send_email(user_doc["email"], subject, html_content)
    
    if success:
        return {"message": "Test email sent successfully", "email": user_doc["email"]}
    else:
        raise HTTPException(status_code=500, detail="Failed to send test email")


# ==================== ONBOARDING ====================

@router.get("/onboarding/status")
async def get_onboarding_status(user: User = Depends(get_current_user)):
    """
    Check if user needs onboarding.
    Returns needs_onboarding=true if no linked accounts AND no analyzed games.
    """
    global db
    
    user_doc = await db.users.find_one(
        {"user_id": user.user_id},
        {"_id": 0, "chess_com_username": 1, "chesscom_username": 1, "lichess_username": 1, "onboarding_completed": 1}
    )
    
    if not user_doc:
        return {"needs_onboarding": True, "reason": "user_not_found"}
    
    # Check if onboarding was explicitly completed
    if user_doc.get("onboarding_completed"):
        return {"needs_onboarding": False}
    
    # Check if user has linked accounts (support both field names)
    has_linked = user_doc.get("chess_com_username") or user_doc.get("chesscom_username") or user_doc.get("lichess_username")
    
    if not has_linked:
        return {"needs_onboarding": True, "reason": "no_linked_accounts"}
    
    # Check if user has analyzed games
    game_count = await db.game_analyses.count_documents({"user_id": user.user_id})
    
    if game_count == 0:
        return {"needs_onboarding": True, "reason": "no_analyzed_games"}
    
    return {"needs_onboarding": False}


@router.post("/settings/profile")
async def update_profile_settings(req: ProfileSettingsRequest, user: User = Depends(get_current_user)):
    """
    Update user profile settings from onboarding.
    - fide_rating: Official FIDE rating (optional)
    - detected_rating: Auto-detected from Chess.com/Lichess
    - focus_intent: What user wants to improve (doesn't override diagnosis)
    """
    global db
    
    update_data = {}
    
    if req.fide_rating is not None:
        update_data["fide_rating"] = req.fide_rating
    if req.detected_rating is not None:
        update_data["detected_rating"] = req.detected_rating
        update_data["detected_platform"] = req.detected_platform
        # Auto-classify skill level based on rating
        if req.detected_rating >= 1800:
            update_data["skill_level"] = "advanced"
        elif req.detected_rating >= 1200:
            update_data["skill_level"] = "intermediate"
        else:
            update_data["skill_level"] = "developing"
    if req.focus_intent is not None:
        update_data["focus_intent"] = req.focus_intent
    
    update_data["onboarding_completed"] = True
    update_data["onboarding_completed_at"] = datetime.now(timezone.utc).isoformat()
    
    await db.users.update_one(
        {"user_id": user.user_id},
        {"$set": update_data}
    )
    
    return {"message": "Profile updated successfully"}


@router.post("/settings/link-account")
async def settings_link_account(req: LinkAccountRequest, user: User = Depends(get_current_user)):
    """
    Link chess account and calculate assessed skill rating.
    """
    global db
    from skill_calibration_service import classify_time_control
    from journey_service import fetch_recent_chesscom_games, fetch_recent_lichess_games
    
    platform = req.platform.lower()
    username = req.username.strip()
    
    if platform not in ["chess.com", "lichess"]:
        raise HTTPException(status_code=400, detail="Invalid platform")
    
    if not username:
        raise HTTPException(status_code=400, detail="Username is required")
    
    # Validate and fetch games
    if platform == "chess.com":
        games = await fetch_recent_chesscom_games(username)
        if not games and games != []:
            raise HTTPException(status_code=404, detail=f"Chess.com user '{username}' not found")
        update_field = "chess_com_username"
    else:
        games = await fetch_recent_lichess_games(username)
        update_field = "lichess_username"
    
    # Calculate performance rating from recent games
    assessed_rating = None
    if games:
        time_controls = {}
        for g in games[:20]:
            tc = g.get("time_control") or g.get("time_class", "rapid")
            classified = classify_time_control(tc)
            if classified not in time_controls:
                time_controls[classified] = []
            
            # Extract rating from game
            rating = None
            if platform == "chess.com":
                white_rating = g.get("white", {}).get("rating")
                black_rating = g.get("black", {}).get("rating")
                white_user = g.get("white", {}).get("username", "").lower()
                if white_user == username.lower():
                    rating = white_rating
                else:
                    rating = black_rating
            else:
                players = g.get("players", {})
                white_rating = players.get("white", {}).get("rating")
                black_rating = players.get("black", {}).get("rating")
                white_user = players.get("white", {}).get("user", {}).get("name", "").lower()
                if white_user == username.lower():
                    rating = white_rating
                else:
                    rating = black_rating
            
            if rating:
                time_controls[classified].append(rating)
        
        # Get blitz or rapid rating
        if "blitz" in time_controls and time_controls["blitz"]:
            assessed_rating = sum(time_controls["blitz"]) // len(time_controls["blitz"])
        elif "rapid" in time_controls and time_controls["rapid"]:
            assessed_rating = sum(time_controls["rapid"]) // len(time_controls["rapid"])
        elif time_controls:
            # Use first available
            first_tc = list(time_controls.values())[0]
            if first_tc:
                assessed_rating = sum(first_tc) // len(first_tc)
    
    # Update user
    update_data = {
        update_field: username,
        "last_game_sync": None  # Trigger sync
    }
    
    if assessed_rating:
        update_data["assessed_rating"] = assessed_rating
        update_data["rating_source"] = platform
    
    await db.users.update_one(
        {"user_id": user.user_id},
        {"$set": update_data}
    )
    
    return {
        "message": "Account linked successfully",
        "platform": platform,
        "username": username,
        "assessed_rating": assessed_rating
    }
