"""
Authentication Routes
=====================

Handles:
- Google OAuth login flow
- Emergent auth session exchange
- Dev mode login
- Session management (status, logout)
- Mobile auth
- Demo login
"""

from fastapi import APIRouter, HTTPException, Request, Response, Depends
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone, timedelta
import os
import uuid
import httpx
import logging

# Config imports
from config import SESSION_EXPIRY_DAYS, COOKIE_MAX_AGE_SECONDS

logger = logging.getLogger(__name__)

# Create router for auth endpoints
router = APIRouter(prefix="/auth", tags=["Authentication"])

# Database reference - will be set by server.py
db = None

def set_db(database):
    """Set the database reference for auth routes"""
    global db
    db = database

# ==================== MODELS ====================

class User(BaseModel):
    user_id: str
    email: str
    name: str
    picture: Optional[str] = None
    created_at: Optional[datetime] = None
    chess_com_username: Optional[str] = None
    lichess_username: Optional[str] = None
    role: Optional[str] = "user"
    
    class Config:
        extra = "ignore"
    
    def model_dump(self):
        """Return dict representation for JSON response"""
        return {
            "user_id": self.user_id,
            "email": self.email,
            "name": self.name,
            "picture": self.picture,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "chess_com_username": self.chess_com_username,
            "lichess_username": self.lichess_username,
            "role": self.role or "user"
        }

class MobileAuthRequest(BaseModel):
    """Request for mobile Google authentication"""
    access_token: str

class DemoLoginRequest(BaseModel):
    """Request for demo login (testing only)"""
    email: str

# ==================== AUTH HELPERS ====================

DEV_MODE = os.environ.get("DEV_MODE", "false").lower() == "true"
DEV_USER_ID = os.environ.get("DEV_USER_ID", "dev_user_local")

async def get_current_user(request: Request) -> User:
    """Get current user from session token in cookie or Authorization header"""
    global db
    
    # First, try normal auth flow
    session_token = request.cookies.get("session_token")
    
    if not session_token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            session_token = auth_header.split(" ")[1]
    
    # If we have a session token, validate it (even in DEV_MODE)
    if session_token:
        session_doc = await db.user_sessions.find_one(
            {"session_token": session_token},
            {"_id": 0}
        )
        
        if session_doc:
            expires_at = session_doc["expires_at"]
            if isinstance(expires_at, str):
                expires_at = datetime.fromisoformat(expires_at)
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            
            # Valid session - return the actual user
            if expires_at >= datetime.now(timezone.utc):
                user_doc = await db.users.find_one(
                    {"user_id": session_doc["user_id"]},
                    {"_id": 0}
                )
                if user_doc:
                    return User(**user_doc)
    
    # DEV MODE fallback: Only use dev user if no valid session exists
    if DEV_MODE:
        logger.warning("⚠️ DEV_MODE: No valid session, using dev user fallback")
        dev_user = await db.users.find_one({"user_id": DEV_USER_ID}, {"_id": 0})
        if not dev_user:
            dev_user = {
                "user_id": DEV_USER_ID,
                "email": "dev@localhost",
                "name": "Dev User",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "rating": 1300
            }
            await db.users.insert_one(dev_user)
            logger.info(f"Created dev user: {DEV_USER_ID}")
        return User(**dev_user)
    
    # No valid authentication
    raise HTTPException(status_code=401, detail="Not authenticated")


# ==================== GOOGLE OAUTH ====================

GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID', '')
GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET', '')
GOOGLE_REDIRECT_URI = os.environ.get('GOOGLE_REDIRECT_URI', '')

@router.get("/google/login")
async def google_login(request: Request):
    """
    Redirect user to Google OAuth consent screen.
    Frontend should redirect to this endpoint to start login flow.
    """
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=500, detail="Google OAuth not configured")
    
    redirect_uri = GOOGLE_REDIRECT_URI or str(request.base_url).rstrip('/') + '/api/auth/google/callback'
    
    google_auth_url = (
        "https://accounts.google.com/o/oauth2/v2/auth?"
        f"client_id={GOOGLE_CLIENT_ID}"
        f"&redirect_uri={redirect_uri}"
        "&response_type=code"
        "&scope=openid%20email%20profile"
        "&access_type=offline"
        "&prompt=consent"
    )
    
    return {"auth_url": google_auth_url}


@router.get("/google/callback")
async def google_callback(code: str, response: Response, request: Request):
    """
    Handle Google OAuth callback.
    Exchange authorization code for tokens and create user session.
    """
    global db
    print(f"[AUTH] OAuth callback - Origin: {request.headers.get('origin')}, Referer: {request.headers.get('referer')}")
    
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        raise HTTPException(status_code=500, detail="Google OAuth not configured")
    
    redirect_uri = GOOGLE_REDIRECT_URI or ''
    
    try:
        async with httpx.AsyncClient() as client_http:
            token_resp = await client_http.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "code": code,
                    "client_id": GOOGLE_CLIENT_ID,
                    "client_secret": GOOGLE_CLIENT_SECRET,
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code"
                }
            )
            
            if token_resp.status_code != 200:
                logger.error(f"Token exchange failed: {token_resp.text}")
                raise HTTPException(status_code=401, detail="Failed to exchange authorization code")
            
            tokens = token_resp.json()
            access_token = tokens.get("access_token")
            
            user_resp = await client_http.get(
                "https://www.googleapis.com/oauth2/v2/userinfo",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            
            if user_resp.status_code != 200:
                raise HTTPException(status_code=401, detail="Failed to get user info from Google")
            
            google_data = user_resp.json()
        
        email = google_data.get("email")
        name = google_data.get("name", email.split("@")[0] if email else "User")
        picture = google_data.get("picture")
        
        if not email:
            raise HTTPException(status_code=400, detail="Email not provided by Google")
        
        user_id = f"user_{uuid.uuid4().hex[:12]}"
        session_token = f"session_{uuid.uuid4().hex}"
        
        existing_user = await db.users.find_one({"email": email}, {"_id": 0})
        
        if existing_user:
            user_id = existing_user["user_id"]
            await db.users.update_one(
                {"user_id": user_id},
                {"$set": {
                    "name": name,
                    "picture": picture,
                    "last_login": datetime.now(timezone.utc).isoformat()
                }}
            )
        else:
            user_doc = {
                "user_id": user_id,
                "email": email,
                "name": name,
                "picture": picture,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "chess_com_username": None,
                "lichess_username": None
            }
            await db.users.insert_one(user_doc)
        
        await db.user_sessions.delete_many({"user_id": user_id})
        
        session_doc = {
            "user_id": user_id,
            "session_token": session_token,
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=SESSION_EXPIRY_DAYS)).isoformat(),
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        await db.user_sessions.insert_one(session_doc)
        
        frontend_url = os.environ.get('FRONTEND_URL', 'https://chessguru.ai')
        print(f"[AUTH] Setting session cookie for user {user_id}, token: {session_token[:20]}...")
        print(f"[AUTH] FRONTEND_URL from env: {frontend_url}")
        print(f"[AUTH] Cookie settings: httponly=True, secure=True, samesite=lax, path=/, max_age={COOKIE_MAX_AGE_SECONDS}")

        from fastapi.responses import RedirectResponse
        redirect_response = RedirectResponse(url=f"{frontend_url}/dashboard?auth=success")
        redirect_response.set_cookie(
            key="session_token",
            value=session_token,
            httponly=True,
            secure=True,
            samesite="lax",
            path="/",
            max_age=COOKIE_MAX_AGE_SECONDS
        )

        print(f"[AUTH] Cookie set on redirect response, redirecting to {frontend_url}/dashboard?auth=success")
        return redirect_response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Google OAuth error: {e}")
        raise HTTPException(status_code=500, detail="Authentication failed")


@router.post("/session")
async def create_session(request: Request, response: Response):
    """Exchange session_id for session_token (Emergent auth - only works in Emergent environment)"""
    global db
    from llm_service import get_provider_mode
    
    if get_provider_mode() != "emergent":
        raise HTTPException(
            status_code=404, 
            detail="This auth method is not available. Use /api/auth/google/login instead."
        )
    
    body = await request.json()
    session_id = body.get("session_id")
    
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id required")
    
    async with httpx.AsyncClient() as client_http:
        resp = await client_http.get(
            "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data",
            headers={"X-Session-ID": session_id}
        )
        
        if resp.status_code != 200:
            raise HTTPException(status_code=401, detail="Invalid session_id")
        
        data = resp.json()
    
    user_id = f"user_{uuid.uuid4().hex[:12]}"
    session_token = data.get("session_token", f"session_{uuid.uuid4().hex}")
    
    existing_user = await db.users.find_one({"email": data["email"]}, {"_id": 0})
    
    if existing_user:
        user_id = existing_user["user_id"]
        await db.users.update_one(
            {"user_id": user_id},
            {"$set": {
                "name": data["name"],
                "picture": data.get("picture")
            }}
        )
    else:
        user_doc = {
            "user_id": user_id,
            "email": data["email"],
            "name": data["name"],
            "picture": data.get("picture"),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "chess_com_username": None,
            "lichess_username": None
        }
        await db.users.insert_one(user_doc)
    
    await db.user_sessions.delete_many({"user_id": user_id})
    
    session_doc = {
        "user_id": user_id,
        "session_token": session_token,
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=SESSION_EXPIRY_DAYS)).isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.user_sessions.insert_one(session_doc)
    
    response.set_cookie(
        key="session_token",
        value=session_token,
        httponly=True,
        secure=True,
        samesite="none",
        path="/",
        max_age=COOKIE_MAX_AGE_SECONDS
    )
    
    user_doc = await db.users.find_one({"user_id": user_id}, {"_id": 0})
    return user_doc


@router.get("/dev-login")
async def dev_login(response: Response):
    """
    DEV MODE ONLY: Auto-login without Google OAuth.
    Use this for local testing when Google OAuth redirect doesn't work.
    """
    global db
    
    if not DEV_MODE:
        raise HTTPException(status_code=403, detail="Dev login only available in DEV_MODE")
    
    dev_user = await db.users.find_one({"user_id": DEV_USER_ID}, {"_id": 0})
    if not dev_user:
        new_user = {
            "user_id": DEV_USER_ID,
            "email": "dev@localhost",
            "name": "Dev User",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "rating": 1300,
            "chess_com_username": None,
            "lichess_username": None
        }
        await db.users.insert_one(new_user)
        dev_user = await db.users.find_one({"user_id": DEV_USER_ID}, {"_id": 0})
    
    session_token = str(uuid.uuid4())
    await db.user_sessions.delete_many({"user_id": DEV_USER_ID})
    
    session_doc = {
        "user_id": DEV_USER_ID,
        "session_token": session_token,
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=SESSION_EXPIRY_DAYS)).isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.user_sessions.insert_one(session_doc)
    
    response.set_cookie(
        key="session_token",
        value=session_token,
        httponly=True,
        secure=False,  # Allow HTTP for localhost
        samesite="lax",
        path="/",
        max_age=COOKIE_MAX_AGE_SECONDS
    )
    
    logger.info(f"Dev user logged in: {DEV_USER_ID}")
    return {"status": "ok", "user": dev_user, "message": "Dev login successful"}


@router.get("/status")
async def auth_status():
    """Check if DEV_MODE is enabled"""
    return {"dev_mode": DEV_MODE}


@router.get("/me")
async def get_me(user: User = Depends(get_current_user)):
    """Get current user profile"""
    return user.model_dump()


@router.post("/logout")
async def logout(request: Request, response: Response):
    """Logout and clear session"""
    global db
    
    session_token = request.cookies.get("session_token")
    if session_token:
        await db.user_sessions.delete_many({"session_token": session_token})
    
    response.delete_cookie(key="session_token", path="/")
    return {"message": "Logged out successfully"}


@router.post("/reset-game-history")
async def reset_game_history(user: User = Depends(get_current_user)):
    """
    Reset all game history for the current user.
    This clears games, analyses, and resets the player profile stats.
    
    WARNING: This action is irreversible!
    """
    global db
    
    user_id = user.user_id
    logger.warning(f"🗑️ RESET GAME HISTORY requested for user: {user_id}")
    
    # Delete all games for this user
    games_deleted = await db.games.delete_many({"user_id": user_id})
    
    # Delete all game analyses
    analyses_deleted = await db.game_analyses.delete_many({"user_id": user_id})
    
    # Reset player profile stats (but keep the profile)
    await db.player_profiles.update_one(
        {"user_id": user_id},
        {"$set": {
            "games_analyzed_count": 0,
            "total_blunders": 0,
            "total_mistakes": 0,
            "total_best_moves": 0,
            "average_accuracy": 0,
            "top_weaknesses": [],
            "strengths": [],
            "habits": [],
            "recent_games": [],
            "estimated_elo": 1200,  # Reset to default
            "estimated_level": "casual"
        }}
    )
    
    # Delete chess understanding cache
    await db.chess_understanding.delete_many({"user_id": user_id})
    
    # Delete training progress
    await db.training_progress.delete_many({"user_id": user_id})
    
    logger.info(f"✅ Reset complete for {user_id}: {games_deleted.deleted_count} games, {analyses_deleted.deleted_count} analyses")
    
    return {
        "message": "Game history reset successfully",
        "games_deleted": games_deleted.deleted_count,
        "analyses_deleted": analyses_deleted.deleted_count
    }


@router.post("/google/mobile")
async def mobile_google_auth(request: MobileAuthRequest):
    """
    Authenticate mobile users with Google access token.
    Fetches user info from Google and creates/updates user.
    """
    global db
    
    # Validate access token is not empty
    if not request.access_token or not request.access_token.strip():
        raise HTTPException(status_code=401, detail="Access token is required")
    
    try:
        async with httpx.AsyncClient() as client_http:
            resp = await client_http.get(
                "https://www.googleapis.com/oauth2/v2/userinfo",
                headers={"Authorization": f"Bearer {request.access_token}"}
            )
            
            if resp.status_code != 200:
                raise HTTPException(status_code=401, detail="Invalid Google access token")
            
            google_data = resp.json()
        
        email = google_data.get("email")
        name = google_data.get("name", email.split("@")[0])
        picture = google_data.get("picture")
        
        if not email:
            raise HTTPException(status_code=400, detail="Email not provided by Google")
        
        user_id = f"user_{uuid.uuid4().hex[:12]}"
        session_token = f"mobile_session_{uuid.uuid4().hex}"
        
        existing_user = await db.users.find_one({"email": email}, {"_id": 0})
        
        if existing_user:
            user_id = existing_user["user_id"]
            await db.users.update_one(
                {"user_id": user_id},
                {"$set": {
                    "name": name,
                    "picture": picture,
                    "last_login": datetime.now(timezone.utc).isoformat()
                }}
            )
        else:
            user_doc = {
                "user_id": user_id,
                "email": email,
                "name": name,
                "picture": picture,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "chess_com_username": None,
                "lichess_username": None
            }
            await db.users.insert_one(user_doc)
        
        await db.user_sessions.delete_many({"user_id": user_id})
        
        session_doc = {
            "user_id": user_id,
            "session_token": session_token,
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "is_mobile": True
        }
        await db.user_sessions.insert_one(session_doc)
        
        user_doc = await db.users.find_one({"user_id": user_id}, {"_id": 0})
        
        return {
            "user": user_doc,
            "session_token": session_token
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Mobile auth error: {e}")
        raise HTTPException(status_code=500, detail="Authentication failed")


@router.post("/demo-login")
async def demo_login(request: DemoLoginRequest):
    """
    Demo login for testing the mobile app without Google OAuth.
    Creates or logs in a user with the provided email.
    """
    global db
    
    email = request.email.strip().lower()
    
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="Valid email required")
    
    user_id = f"demo_{email.replace('@', '_').replace('.', '_')}"
    session_token = f"demo_session_{uuid.uuid4().hex}"
    name = email.split("@")[0].title()
    
    existing_user = await db.users.find_one({"email": email}, {"_id": 0})
    
    if existing_user:
        user_id = existing_user["user_id"]
        await db.users.update_one(
            {"user_id": user_id},
            {"$set": {"last_login": datetime.now(timezone.utc).isoformat()}}
        )
    else:
        user_doc = {
            "user_id": user_id,
            "email": email,
            "name": name,
            "picture": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "chess_com_username": None,
            "lichess_username": None,
            "is_demo": True
        }
        await db.users.insert_one(user_doc)
    
    await db.user_sessions.delete_many({"user_id": user_id})
    
    session_doc = {
        "user_id": user_id,
        "session_token": session_token,
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=SESSION_EXPIRY_DAYS)).isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "is_demo": True
    }
    await db.user_sessions.insert_one(session_doc)
    
    user_doc = await db.users.find_one({"user_id": user_id}, {"_id": 0})
    
    logger.info(f"Demo login: {email}")
    
    return {
        "user": user_doc,
        "session_token": session_token
    }
