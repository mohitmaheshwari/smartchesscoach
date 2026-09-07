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
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone, timedelta
from urllib.parse import urlencode, urlsplit
import base64
import binascii
import hashlib
import hmac
import json
import os
import secrets
import time
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
    # Explicit provenance for analytics and test isolation. These fields are
    # returned to the authenticated client, but never contain identity data.
    is_demo: bool = False
    analytics_excluded: bool = False
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
            "is_demo": self.is_demo,
            "analytics_excluded": self.analytics_excluded,
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

OAUTH_STATE_VERSION = 1
OAUTH_STATE_MAX_AGE_SECONDS = 10 * 60
OAUTH_STATE_CLOCK_SKEW_SECONDS = 30
OAUTH_STATE_COOKIE = "oauth_state_nonce"
OAUTH_STATE_COOKIE_PATH = "/api/auth/google"


def _safe_frontend_redirect_path(value: Optional[str]) -> str:
    """Return a local path only; query, fragment, hosts and controls are rejected."""
    if not isinstance(value, str) or not value:
        return "/home"
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        return "/home"
    parsed = urlsplit(value)
    if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment:
        return "/home"
    if not parsed.path.startswith("/") or parsed.path.startswith("//"):
        return "/home"
    return parsed.path


def _oauth_platform(value: Optional[str]) -> str:
    platform = (value or "web").strip().lower()
    if platform not in {"web", "mobile"}:
        raise HTTPException(status_code=400, detail="Unsupported OAuth platform")
    return platform


def _urlsafe_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _urlsafe_decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + ("=" * (-len(value) % 4)))


def _encode_oauth_state(
    *,
    platform: str,
    redirect_to: str,
    nonce: str,
    secret: str,
    issued_at: Optional[int] = None,
) -> str:
    payload = {
        "iat": int(time.time()) if issued_at is None else int(issued_at),
        "nonce": nonce,
        "platform": platform,
        "redirect_to": redirect_to,
        "version": OAUTH_STATE_VERSION,
    }
    body = _urlsafe_encode(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    signature = _urlsafe_encode(hmac.new(secret.encode("utf-8"), body.encode("ascii"), hashlib.sha256).digest())
    return f"{body}.{signature}"


def _decode_oauth_state(
    state: Optional[str],
    *,
    secret: str,
    expected_nonce: Optional[str] = None,
    now: Optional[int] = None,
    require_nonce: bool = True,
) -> dict:
    if not state or len(state) > 2048:
        raise HTTPException(status_code=400, detail="Invalid OAuth state")
    if require_nonce and not expected_nonce:
        raise HTTPException(status_code=400, detail="Invalid OAuth state")
    try:
        body, supplied_signature = state.split(".", 1)
        expected_signature = _urlsafe_encode(
            hmac.new(secret.encode("utf-8"), body.encode("ascii"), hashlib.sha256).digest()
        )
        if not hmac.compare_digest(supplied_signature, expected_signature):
            raise ValueError("signature mismatch")
        payload = json.loads(_urlsafe_decode(body).decode("utf-8"))
        issued_at = payload.get("iat")
        nonce = payload.get("nonce")
        platform = payload.get("platform")
        redirect_to = payload.get("redirect_to")
        if payload.get("version") != OAUTH_STATE_VERSION:
            raise ValueError("unsupported version")
        if not isinstance(issued_at, int) or isinstance(issued_at, bool):
            raise ValueError("invalid timestamp")
        current_time = int(time.time()) if now is None else int(now)
        if issued_at > current_time + OAUTH_STATE_CLOCK_SKEW_SECONDS:
            raise ValueError("future state")
        if current_time - issued_at > OAUTH_STATE_MAX_AGE_SECONDS:
            raise ValueError("expired state")
        if expected_nonce:
            if not isinstance(nonce, str) or not hmac.compare_digest(nonce, expected_nonce):
                raise ValueError("nonce mismatch")
        if platform not in {"web", "mobile"}:
            raise ValueError("invalid platform")
        if redirect_to != _safe_frontend_redirect_path(redirect_to):
            raise ValueError("unsafe redirect")
        return payload
    except HTTPException:
        raise
    except (ValueError, TypeError, binascii.Error, json.JSONDecodeError, UnicodeDecodeError):
        raise HTTPException(status_code=400, detail="Invalid OAuth state")


def _oauth_cookie_secure(effective_redirect_uri: str) -> bool:
    parsed = urlsplit(effective_redirect_uri)
    return parsed.scheme == "https" and parsed.hostname not in {"localhost", "127.0.0.1"}


def _set_oauth_state_cookie(response: Response, nonce: str, *, secure: bool) -> None:
    response.set_cookie(
        key=OAUTH_STATE_COOKIE,
        value=nonce,
        max_age=OAUTH_STATE_MAX_AGE_SECONDS,
        httponly=True,
        secure=secure,
        samesite="lax",
        path=OAUTH_STATE_COOKIE_PATH,
    )


def _delete_oauth_state_cookie(response: Response) -> None:
    response.delete_cookie(key=OAUTH_STATE_COOKIE, path=OAUTH_STATE_COOKIE_PATH)


def _web_auth_payload(user_doc: dict) -> dict:
    """Web auth credentials live only in the HttpOnly cookie."""
    return {"user": user_doc}

# Helper for current user
async def get_current_user(request: Request) -> Optional[User]:
    """Authenticate web cookies or explicitly mobile bearer sessions."""
    global db
    session_token = request.cookies.get("session_token")
    credential_source = "cookie" if session_token else None

    # Bearer auth is reserved for native sessions. A browser cookie always wins.
    auth_header = request.headers.get("Authorization")
    if not session_token and auth_header and auth_header.startswith("Bearer "):
        session_token = auth_header.split(" ", 1)[1].strip()
        credential_source = "bearer"
    
    if session_token and db is not None:
        session = await db.user_sessions.find_one({"session_token": session_token}, {"_id": 0})
        if session:
            if credential_source == "bearer" and session.get("is_mobile") is not True:
                raise HTTPException(status_code=401, detail="Not authenticated")
            # Check expiry
            expires_at = session.get("expires_at")
            if expires_at:
                if isinstance(expires_at, str):
                    expires_at = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
                if expires_at < datetime.now(timezone.utc):
                    raise HTTPException(status_code=401, detail="Not authenticated")
            
            user_doc = await db.users.find_one({"user_id": session["user_id"]}, {"_id": 0})
            if user_doc:
                return User(**user_doc)

    if credential_source is not None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
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
    load_dotenv(Path(__file__).parent.parent / '.env', override=True)
    client_id = os.environ.get('GOOGLE_CLIENT_ID', '').strip()
    client_secret = os.environ.get('GOOGLE_CLIENT_SECRET', '').strip()
    redirect_uri = os.environ.get('GOOGLE_REDIRECT_URI', '').strip()
    frontend_url = os.environ.get('FRONTEND_URL', 'http://localhost:3000').strip()
    return client_id, client_secret, redirect_uri, frontend_url

@router.get("/google/login")
async def google_login(
    request: Request,
    response: Response,
    platform: Optional[str] = None,
    redirect_to: Optional[str] = None,
    flow: Optional[str] = None,
):
    """
    Redirect user to Google OAuth consent screen.
    Frontend should redirect to this endpoint to start login flow.
    """
    client_id, client_secret, redirect_uri, _ = _get_google_config()
    if not client_id:
        raise HTTPException(status_code=500, detail="Google OAuth not configured")
    
    effective_redirect_uri = redirect_uri or str(request.base_url).rstrip('/') + '/api/auth/google/callback'
    
    user_agent = request.headers.get("user-agent", "").lower()
    inferred_platform = platform or request.query_params.get("platform")
    if not inferred_platform and any(kw in user_agent for kw in ["mobile", "android", "iphone", "ipad", "ipod", "wv"]):
        inferred_platform = "mobile"

    plat = _oauth_platform(inferred_platform or "web")
    dest = _safe_frontend_redirect_path(redirect_to or request.query_params.get("redirect_to", "/home"))
    nonce = secrets.token_urlsafe(32)
    state = _encode_oauth_state(
        platform=plat,
        redirect_to=dest,
        nonce=nonce,
        secret=client_secret,
    )

    google_auth_url = "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode({
        "client_id": client_id,
        "redirect_uri": effective_redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    })
    secure_cookie = _oauth_cookie_secure(effective_redirect_uri)

    if flow == "redirect" or request.headers.get("sec-fetch-dest") == "document":
        redirect_response = RedirectResponse(url=google_auth_url, status_code=302)
        _set_oauth_state_cookie(redirect_response, nonce, secure=secure_cookie)
        return redirect_response

    _set_oauth_state_cookie(response, nonce, secure=secure_cookie)
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
    
    cookie_nonce = request.cookies.get(OAUTH_STATE_COOKIE)
    state_payload = _decode_oauth_state(
        state or request.query_params.get("state"),
        secret=client_secret,
        expected_nonce=cookie_nonce,
        require_nonce=False if not cookie_nonce else True,
    )
    oauth_platform = state_payload["platform"]
    redirect_to = state_payload["redirect_to"]

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
            "created_at": datetime.now(timezone.utc).isoformat(),
            "is_mobile": oauth_platform == "mobile",
        }
        await db.user_sessions.insert_one(session_doc)

        # Backfill coach memory from imported games on first login (non-blocking)
        is_first_login = not existing_user or not existing_user.get("coach_memory_initialized")
        if is_first_login and background_tasks:
            from services.coach_memory import backfill_coach_memory_from_imported_games
            background_tasks.add_task(backfill_coach_memory_from_imported_games, db, user_id)

        if oauth_platform == "mobile":
            app_url = "chessguru://auth?" + urlencode({"token": session_token, "user_id": user_id})
            if not frontend_url:
                frontend_url = os.environ.get('FRONTEND_URL', 'http://localhost:3000').strip()
            web_fallback_url = f"{frontend_url.rstrip('/')}{redirect_to}?auth=success&token={session_token}&user_id={user_id}"
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
            setTimeout(function() {{
                try {{
                    window.location.href = "{web_fallback_url}";
                }} catch (e) {{}}
            }}, 2000);
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
            html_response = HTMLResponse(content=html_content)
            _delete_oauth_state_cookie(html_response)
            html_response.set_cookie(
                key="session_token",
                value=session_token,
                httponly=True,
                secure=False if ("localhost" in frontend_url or "127.0.0.1" in frontend_url) else True,
                samesite="lax",
                path="/",
                max_age=COOKIE_MAX_AGE_SECONDS,
            )
            return html_response

        if not frontend_url:
            frontend_url = os.environ.get('FRONTEND_URL', 'http://localhost:3000').strip()
        redirect_url = f"{frontend_url.rstrip('/')}{redirect_to}?auth=success"

        is_localhost = "localhost" in frontend_url or "127.0.0.1" in frontend_url
        redirect_response = RedirectResponse(url=redirect_url)
        _delete_oauth_state_cookie(redirect_response)
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
        secure=_web_session_cookie_secure(),
        samesite="lax",
        path="/",
        max_age=COOKIE_MAX_AGE_SECONDS
    )
    
    logger.info(f"Dev user logged in: {DEV_USER_ID}")
    return {"status": "ok", "user": dev_user, "message": "Dev login successful"}


# ==================== EMAIL + PASSWORD AUTH ====================

def _web_session_cookie_secure() -> bool:
    """Keep production cookies Secure without breaking plain-http local QA."""
    frontend_url = os.environ.get("FRONTEND_URL", "").strip()
    if frontend_url:
        parsed = urlsplit(frontend_url)
        if parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1"}:
            return False
        return True
    return not DEV_MODE


def _issue_session_cookie(response: Response, session_token: str) -> None:
    """Apply the standard session cookie used by every auth path here."""
    response.set_cookie(
        key="session_token",
        value=session_token,
        httponly=True,
        secure=_web_session_cookie_secure(),
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
    return _web_auth_payload(user_doc)


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
    return _web_auth_payload(user)


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
    session_query = {"session_token": session_token} if session_token else None
    if not session_query:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            mobile_token = auth_header.split(" ", 1)[1].strip()
            if mobile_token:
                session_query = {"session_token": mobile_token, "is_mobile": True}
    if session_query:
        await db.user_sessions.delete_many(session_query)
    
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

    if not DEV_MODE:
        raise HTTPException(status_code=403, detail="Demo login only available in DEV_MODE")
    
    email = request.email.strip().lower()
    
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="Valid email required")
    
    # A demo identity must never alias a real account, even when a tester enters
    # the email address of an existing user. The stable hash also prevents the
    # analytics-safe user_id field from containing an email address.
    user_id = f"demo_{hashlib.sha256(email.encode('utf-8')).hexdigest()[:16]}"
    session_token = f"demo_session_{uuid.uuid4().hex}"
    name = email.split("@")[0].title()
    
    existing_user = await db.users.find_one({"user_id": user_id}, {"_id": 0})
    
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
        "is_demo": True,
        "is_mobile": True,
    }
    await db.user_sessions.insert_one(session_doc)
    
    user_doc = await db.users.find_one({"user_id": user_id}, {"_id": 0})
    
    logger.info(f"Demo login: {email}")
    
    return {
        "user": user_doc,
        "session_token": session_token
    }
