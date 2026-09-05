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

from fastapi import APIRouter, HTTPException, Request, Response, Depends, BackgroundTasks
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone, timedelta
import os
import uuid
import httpx
import logging

import bcrypt
if not hasattr(bcrypt, "__about__"):
    bcrypt.__about__ = type("about", (), {"__version__": getattr(bcrypt, "__version__", "4.0.0")})

from passlib.context import CryptContext

# Config imports
from config import SESSION_EXPIRY_DAYS, COOKIE_MAX_AGE_SECONDS

# Password hashing context. bcrypt cost is the passlib default (12),
# which is the right speed/security balance for an interactive login.
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

logger = logging.getLogger(__name__)

# Create router for auth endpoints
router = APIRouter(prefix="/auth", tags=["Authentication"])

from pathlib import Path
from dotenv import load_dotenv

# Ensure environment variables are loaded
_env_path = Path(__file__).resolve().parent.parent / '.env'
if _env_path.exists():
    load_dotenv(_env_path)
_root_env = Path(__file__).resolve().parent.parent.parent / '.env'
if _root_env.exists():
    load_dotenv(_root_env)

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
    # Reviewer flag — when True, user can read games / analyses across
    # ALL users (not just their own). Used for content-quality auditors
    # like Parth Gilda, who flag bugs against any user's coaching output.
    is_reviewer: bool = False
    # Self-declared "why are you here" (compete/improve/learn/fun). Exposed so
    # the Home backfill prompt knows whether the user has answered yet.
    player_motivation: Optional[str] = None

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
            "role": self.role or "user",
            "is_reviewer": self.is_reviewer,
            "player_motivation": self.player_motivation,
        }

class MobileAuthRequest(BaseModel):
    """Request for mobile Google authentication"""
    access_token: str

class DemoLoginRequest(BaseModel):
    """Request for demo login (testing only)"""
    email: str

class RegisterRequest(BaseModel):
    """Email + password signup."""
    email: str
    password: str
    name: Optional[str] = None

class LoginRequest(BaseModel):
    """Email + password sign-in."""
    email: str
    password: str

# Dev mode config
DEV_MODE = os.environ.get("DEV_MODE", "false").lower() == "true"
DEV_USER_ID = "dev_user_local"

# Helper for current user
async def get_current_user(request: Request) -> Optional[User]:
    """Get current user from session token (cookie or header) or dev mode"""
    global db
    session_token = request.cookies.get("session_token")
    
    # Also check Authorization header
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        session_token = auth_header.replace("Bearer ", "")
    
    if session_token and db is not None:
        session = await db.user_sessions.find_one({"session_token": session_token}, {"_id": 0})
        if session:
            # Check expiry
            expires_at = session.get("expires_at")
            if expires_at:
                if isinstance(expires_at, str):
                    expires_at = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
                if expires_at < datetime.now(timezone.utc):
                    return None
            
            user_doc = await db.users.find_one({"user_id": session["user_id"]}, {"_id": 0})
            if user_doc:
                return User(**user_doc)
    
    # Dev mode fallback
    if DEV_MODE and db is not None:
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

def _get_google_config():
    client_id = os.environ.get('GOOGLE_CLIENT_ID', '').strip()
    client_secret = os.environ.get('GOOGLE_CLIENT_SECRET', '').strip()
    redirect_uri = os.environ.get('GOOGLE_REDIRECT_URI', '').strip()
    frontend_url = os.environ.get('FRONTEND_URL', 'http://localhost:3000').strip()
    return client_id, client_secret, redirect_uri, frontend_url

@router.get("/google/login")
async def google_login(request: Request, platform: Optional[str] = None, redirect_to: Optional[str] = None):
    """
    Redirect user to Google OAuth consent screen.
    Frontend should redirect to this endpoint to start login flow.
    """
    client_id, client_secret, redirect_uri, _ = _get_google_config()
    if not client_id:
        raise HTTPException(status_code=500, detail="Google OAuth not configured")
    
    effective_redirect_uri = redirect_uri or str(request.base_url).rstrip('/') + '/api/auth/google/callback'
    
    plat = platform or request.query_params.get("platform", "web")
    dest = redirect_to or request.query_params.get("redirect_to", "/home")
    state = f"{plat}___{dest}"
    
    google_auth_url = (
        "https://accounts.google.com/o/oauth2/v2/auth?"
        f"client_id={client_id}"
        f"&redirect_uri={effective_redirect_uri}"
        f"&response_type=code"
        f"&scope=openid%20email%20profile"
        f"&access_type=offline"
        f"&prompt=consent"
        f"&state={state}"
    )
    
    return {"auth_url": google_auth_url}


@router.get("/google/callback")
async def google_callback(code: str, response: Response, request: Request, state: Optional[str] = None, background_tasks: BackgroundTasks = None):
    """
    Handle Google OAuth callback.
    Exchange authorization code for tokens and create user session.
    """
    global db
    print(f"[AUTH] OAuth callback - Origin: {request.headers.get('origin')}, Referer: {request.headers.get('referer')}")
    
    client_id, client_secret, redirect_uri, frontend_url = _get_google_config()
    if not client_id or not client_secret:
        raise HTTPException(status_code=500, detail="Google OAuth not configured")
    
    effective_redirect_uri = redirect_uri or str(request.base_url).rstrip('/') + '/api/auth/google/callback'
    
    try:
        async with httpx.AsyncClient() as client_http:
            token_resp = await client_http.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "code": code,
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "redirect_uri": effective_redirect_uri,
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

        # Backfill coach memory from imported games on first login (non-blocking)
        is_first_login = not existing_user or not existing_user.get("coach_memory_initialized")
        if is_first_login and background_tasks:
            from services.coach_memory import backfill_coach_memory_from_imported_games
            background_tasks.add_task(backfill_coach_memory_from_imported_games, db, user_id)

        # Check if login was requested from mobile app
        state_val = state or request.query_params.get("state", "web")
        is_mobile = any(k in state_val.lower() for k in ["mobile", "android", "ios", "capacitor", "app"])

        if is_mobile:
            from fastapi.responses import HTMLResponse
            app_url = f"chessguru://auth?token={session_token}&user_id={user_id}"
            html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Signing in...</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="refresh" content="0;url={app_url}">
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #09090b;
            color: #f4f4f5;
            display: flex;
            align-items: center;
            justify-content: center;
            min-height: 100vh;
            padding: 24px;
            text-align: center;
        }}
        .card {{
            background: #18181b;
            border: 1px solid #27272a;
            border-radius: 20px;
            padding: 36px 28px;
            max-width: 380px;
            width: 100%;
        }}
        .logo {{ font-size: 44px; margin-bottom: 16px; }}
        h2 {{ font-size: 20px; font-weight: 700; margin-bottom: 8px; color: #fff; }}
        p {{ font-size: 14px; color: #a1a1aa; line-height: 1.5; margin-bottom: 24px; }}
        .btn {{
            display: inline-block;
            width: 100%;
            padding: 14px 20px;
            background: #B7F34A;
            color: #0A1712;
            text-decoration: none;
            font-weight: 700;
            border-radius: 12px;
            font-size: 16px;
        }}
    </style>
    <script>
        window.onload = function() {{
            window.location.href = "{app_url}";
        }};
    </script>
</head>
<body>
    <div class="card">
        <div class="logo">♟️</div>
        <h2>Sign In Successful!</h2>
        <p>Connecting back to your ChessGuru App...</p>
        <a href="{app_url}" class="btn">Open ChessGuru App</a>
    </div>
</body>
</html>"""
            return HTMLResponse(content=html_content)

        if not frontend_url:
            frontend_url = os.environ.get('FRONTEND_URL', 'http://localhost:3000').strip()
        redirect_to = "/home"
        if "___" in state_val:
            redirect_to = state_val.split("___")[1]

        redirect_url = f"{frontend_url}{redirect_to}?auth=success&token={session_token}"

        is_localhost = "localhost" in frontend_url or "127.0.0.1" in frontend_url
        from fastapi.responses import RedirectResponse
        redirect_response = RedirectResponse(url=redirect_url)
        redirect_response.set_cookie(
            key="session_token",
            value=session_token,
            httponly=True,
            secure=False if is_localhost else True,
            samesite="lax",
            path="/",
            max_age=COOKIE_MAX_AGE_SECONDS
        )
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


# ==================== EMAIL + PASSWORD AUTH ====================

def _issue_session_cookie(response: Response, session_token: str) -> None:
    """Apply the standard session cookie used by every auth path here."""
    response.set_cookie(
        key="session_token",
        value=session_token,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/",
        max_age=COOKIE_MAX_AGE_SECONDS,
    )


async def _create_session(user_id: str) -> str:
    """Replace existing sessions for the user and return a fresh token."""
    global db
    await db.user_sessions.delete_many({"user_id": user_id})
    session_token = f"session_{uuid.uuid4().hex}"
    await db.user_sessions.insert_one({
        "user_id": user_id,
        "session_token": session_token,
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=SESSION_EXPIRY_DAYS)).isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    return session_token


@router.post("/register")
async def register(req: RegisterRequest, response: Response):
    """Create a new user with email + password and log them in."""
    global db

    email = (req.email or "").strip().lower()
    if "@" not in email or len(email) < 5:
        raise HTTPException(status_code=400, detail="Valid email required")
    if len(req.password or "") < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    existing = await db.users.find_one({"email": email}, {"_id": 0})
    if existing:
        if existing.get("password_hash"):
            raise HTTPException(status_code=409, detail="Email already registered. Please log in.")
        # Account exists from Google/demo path with no password set. Tell the
        # user explicitly rather than silently overwriting or merging.
        raise HTTPException(
            status_code=409,
            detail="This email is already linked to another login method. Use that to sign in.",
        )

    name = (req.name or "").strip() or email.split("@")[0]
    user_id = f"user_{uuid.uuid4().hex[:12]}"

    user_doc = {
        "user_id": user_id,
        "email": email,
        "name": name,
        "picture": None,
        "password_hash": pwd_context.hash(req.password),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "chess_com_username": None,
        "lichess_username": None,
    }
    await db.users.insert_one(user_doc)

    session_token = await _create_session(user_id)
    _issue_session_cookie(response, session_token)

    user_doc.pop("_id", None)
    user_doc.pop("password_hash", None)
    return {"user": user_doc, "session_token": session_token}


@router.post("/login")
async def login(req: LoginRequest, response: Response):
    """Log in with email + password."""
    global db

    email = (req.email or "").strip().lower()
    user = await db.users.find_one({"email": email})
    if not user or not user.get("password_hash"):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not pwd_context.verify(req.password or "", user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    user_id = user["user_id"]
    session_token = await _create_session(user_id)
    _issue_session_cookie(response, session_token)

    user.pop("_id", None)
    user.pop("password_hash", None)
    return {"user": user, "session_token": session_token}


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
