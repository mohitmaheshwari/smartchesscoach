from fastapi import FastAPI, APIRouter, HTTPException, Request, Response, Depends, BackgroundTasks
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import asyncio
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timezone, timedelta
import httpx
import re
import io

# Import centralized config
from config import (
    LLM_PROVIDER, LLM_MODEL, TTS_MODEL, TTS_VOICE,
    STOCKFISH_DEPTH, STOCKFISH_MAX_RETRIES,
    SESSION_EXPIRY_DAYS, COOKIE_MAX_AGE_SECONDS,
    PLAY_SESSION_LOOKBACK_HOURS, DEFAULT_RATING,
    BACKGROUND_SYNC_INTERVAL_SECONDS, FIRST_SYNC_MONTHS,
    DAILY_SYNC_MAX_GAMES, SYNC_INTERVAL_HOURS,
    QUICK_SYNC_INTERVAL_SECONDS, QUICK_SYNC_MAX_GAMES
)

# Import RAG service
from rag_service import (
    build_rag_context,
    create_game_embeddings,
    create_pattern_embedding,
    create_analysis_embedding,
    process_user_games_for_rag
)

# Import Player Profile service
from player_profile_service import (
    get_or_create_profile,
    update_profile_after_analysis,
    record_challenge_result,
    build_profile_context_for_prompt,
    build_explanation_prompt_contract,
    validate_explanation,
    categorize_weakness,
    normalize_weakness_key,
    WEAKNESS_CATEGORIES,
    LearningStyle,
    CoachingTone
)

# Import Coach Quality Score system (internal only)
from cqs_service import (
    calculate_cqs,
    get_stricter_prompt_constraints,
    should_accept_after_regenerations,
    log_cqs_result,
    MAX_REGENERATIONS
)

# Import Journey Dashboard service
from journey_service import (
    generate_journey_dashboard_data,
    run_background_sync,
    fetch_recent_chesscom_games,
    fetch_recent_lichess_games,
    select_games_for_analysis
)

# Import Rating & Training service
from rating_service import (
    predict_rating_trajectory,
    calculate_improvement_velocity,
    calculate_performance_rating,
    analyze_time_usage,
    generate_training_session,
    generate_calculation_analysis,
    fetch_platform_ratings
)

# Import Stockfish engine service
from stockfish_service import (
    analyze_game_with_stockfish,
    get_position_evaluation,
    get_best_moves_for_position
)

# Import Phase Theory service for strategic coaching
from phase_theory_service import (
    analyze_game_phases,
    get_phase_theory,
    detect_game_phase,
    detect_endgame_type,
    get_rating_bracket
)

# Import Auto-Coach service for live post-game feedback
from auto_coach_service import (
    build_deterministic_summary,
    generate_and_save_commentary,
    get_quick_notification_message
)

# Import Notification service
from notification_service import (
    create_notification,
    get_user_notifications,
    get_unread_count,
    mark_notification_read,
    dismiss_notification,
    notify_game_analyzed,
    notify_focus_updated,
    get_push_notification_payload,
    NotificationType,
    NotificationPriority
)

# Import Subscription service
from subscription_service import (
    get_user_plan,
    get_effective_plan,
    can_analyze_game,
    increment_analysis_count,
    has_feature_access,
    upgrade_to_pro
)

# Import Mistake Card service for the Mistake Mastery System
from mistake_card_service import (
    extract_mistake_cards_from_analysis,
    get_training_session,
    get_due_cards,
    get_post_game_card,
    record_card_attempt,
    get_user_habit_progress,
    update_user_habit_progress,
    set_active_habit,
    get_training_stats,
    get_card_by_id,
    generate_why_question,
    HABIT_DEFINITIONS
)

# Import Chess Journey service for comprehensive progress tracking
from chess_journey_service import get_chess_journey

# Import Coach Game Review Service
from coach_game_review_service import (
    get_coach_game_review,
    get_improvement_highlights,
    get_concern_areas
)

# Import Blunder Intelligence Service for the Blunder Reduction System
from blunder_intelligence_service import (
    get_core_lesson,
    get_dominant_weakness_ranking,
    get_win_state_analysis,
    get_mistake_heatmap,
    estimate_rating_impact,
    get_identity_profile,
    get_mission,
    check_milestones,
    get_focus_data,
    get_journey_data,
    get_lab_data,
    get_drill_positions,
    find_similar_pattern_games
)

# Import Badge Service
from badge_service import calculate_all_badges, get_badge_history, calculate_badge_trends

# Import Mistake Explanation Service for educational commentary
from mistake_explanation_service import (
    generate_mistake_explanation,
    analyze_mistake_position,
    get_quick_explanation
)

# Import Discipline Check Service for sharp, data-driven analysis
from discipline_check_service import get_discipline_check

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# LLM Key
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY', '')

# Global variable to track the background task
_background_sync_task = None

# Configure logging (moved up so lifespan can use logger)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ==================== LLM SERVICE ====================
# Import the abstraction layer that handles Emergent vs OpenAI
from llm_service import call_llm, call_tts, get_provider_mode

logger.info(f"Using LLM provider: {get_provider_mode()}")

# Background sync loop function (defined before lifespan)
async def background_sync_loop():
    """
    Periodic background task to sync games for all users.
    Runs every 6 hours (configurable via BACKGROUND_SYNC_INTERVAL_SECONDS).
    """
    while True:
        try:
            logger.info("Starting background game sync...")
            synced_count = await run_background_sync(db)
            logger.info(f"Background sync completed: {synced_count} games synced")
        except Exception as e:
            logger.error(f"Background sync error: {e}")
        
        # Wait for next sync interval (6 hours by default)
        await asyncio.sleep(BACKGROUND_SYNC_INTERVAL_SECONDS)

# Lifespan context manager (replaces deprecated on_event)
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for FastAPI.
    Handles startup and shutdown events.
    """
    global _background_sync_task
    
    # === STARTUP ===
    # Start the background sync loop
    _background_sync_task = asyncio.create_task(background_sync_loop())
    logger.info("Background sync scheduler started")
    
    yield  # App runs here
    
    # === SHUTDOWN ===
    # Cancel background task
    if _background_sync_task:
        _background_sync_task.cancel()
        try:
            await _background_sync_task
        except asyncio.CancelledError:
            pass
    
    # Close MongoDB connection
    client.close()
    logger.info("Application shutdown complete")

# Create the main app with lifespan
app = FastAPI(lifespan=lifespan)

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# ==================== MODELS ====================

class User(BaseModel):
    model_config = ConfigDict(extra="ignore")
    user_id: str
    email: str
    name: str
    picture: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    chess_com_username: Optional[str] = None
    lichess_username: Optional[str] = None

class UserSession(BaseModel):
    model_config = ConfigDict(extra="ignore")
    user_id: str
    session_token: str
    expires_at: datetime
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class Game(BaseModel):
    model_config = ConfigDict(extra="ignore")
    game_id: str = Field(default_factory=lambda: f"game_{uuid.uuid4().hex[:12]}")
    user_id: str
    platform: str  # "chess.com" or "lichess"
    pgn: str
    white_player: str
    black_player: str
    result: str
    time_control: Optional[str] = None
    date_played: Optional[str] = None
    opening: Optional[str] = None
    user_color: str  # "white" or "black"
    imported_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    is_analyzed: bool = False

class GameCreate(BaseModel):
    platform: str
    pgn: str
    white_player: str
    black_player: str
    result: str
    time_control: Optional[str] = None
    date_played: Optional[str] = None
    opening: Optional[str] = None
    user_color: str

class MistakePattern(BaseModel):
    model_config = ConfigDict(extra="ignore")
    pattern_id: str = Field(default_factory=lambda: f"pattern_{uuid.uuid4().hex[:12]}")
    user_id: str
    category: str  # "tactical", "positional", "endgame", "opening", "time_management"
    subcategory: str  # "pinning", "center_control", "one_move_blunder", etc.
    description: str
    occurrences: int = 1
    game_ids: List[str] = []
    first_seen: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_seen: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class GameAnalysis(BaseModel):
    model_config = ConfigDict(extra="ignore")
    analysis_id: str = Field(default_factory=lambda: f"analysis_{uuid.uuid4().hex[:12]}")
    game_id: str
    user_id: str
    commentary: List[Dict[str, Any]] = []  # [{move_number, move, comment, evaluation}]
    blunders: int = 0
    mistakes: int = 0
    inaccuracies: int = 0
    best_moves: int = 0
    overall_summary: str = ""
    identified_patterns: List[str] = []  # pattern_ids
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class ImportGamesRequest(BaseModel):
    platform: str
    username: str

class AnalyzeGameRequest(BaseModel):
    game_id: str
    force: bool = False  # Force re-analysis even if already analyzed

class ConnectPlatformRequest(BaseModel):
    platform: str
    username: str

# ==================== AUTH HELPERS ====================

# DEV MODE - Set DEV_MODE=true in .env to bypass authentication for local testing
DEV_MODE = os.environ.get("DEV_MODE", "false").lower() == "true"
DEV_USER_ID = os.environ.get("DEV_USER_ID", "dev_user_local")

async def get_current_user(request: Request) -> User:
    """Get current user from session token in cookie or Authorization header"""
    
    # DEV MODE: Bypass auth and return a test user
    if DEV_MODE:
        logger.warning("⚠️ DEV_MODE enabled - authentication bypassed!")
        # Try to get or create a dev user
        dev_user = await db.users.find_one({"user_id": DEV_USER_ID}, {"_id": 0})
        if not dev_user:
            # Create dev user if doesn't exist
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
    
    # Normal auth flow
    session_token = request.cookies.get("session_token")
    
    if not session_token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            session_token = auth_header.split(" ")[1]
    
    if not session_token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    session_doc = await db.user_sessions.find_one(
        {"session_token": session_token},
        {"_id": 0}
    )
    
    if not session_doc:
        raise HTTPException(status_code=401, detail="Invalid session")
    
    expires_at = session_doc["expires_at"]
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Session expired")
    
    user_doc = await db.users.find_one(
        {"user_id": session_doc["user_id"]},
        {"_id": 0}
    )
    
    if not user_doc:
        raise HTTPException(status_code=401, detail="User not found")
    
    return User(**user_doc)

# ==================== AUTH ROUTES ====================

# Google OAuth Configuration
GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID', '')
GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET', '')
GOOGLE_REDIRECT_URI = os.environ.get('GOOGLE_REDIRECT_URI', '')  # e.g., https://chessguru.ai/auth/callback

@api_router.get("/auth/google/login")
async def google_login(request: Request):
    """
    Redirect user to Google OAuth consent screen.
    Frontend should redirect to this endpoint to start login flow.
    """
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=500, detail="Google OAuth not configured")
    
    # Get redirect URI from environment or construct from request
    redirect_uri = GOOGLE_REDIRECT_URI or str(request.base_url).rstrip('/') + '/api/auth/google/callback'
    
    # Google OAuth authorization URL
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

@api_router.get("/auth/google/callback")
async def google_callback(code: str, response: Response):
    """
    Handle Google OAuth callback.
    Exchange authorization code for tokens and create user session.
    """
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        raise HTTPException(status_code=500, detail="Google OAuth not configured")
    
    redirect_uri = GOOGLE_REDIRECT_URI or ''
    
    try:
        # Exchange authorization code for tokens
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
            
            # Get user info from Google
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
        
        # Create or update user
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
        
        # Clear old sessions and create new one
        await db.user_sessions.delete_many({"user_id": user_id})
        
        session_doc = {
            "user_id": user_id,
            "session_token": session_token,
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=SESSION_EXPIRY_DAYS)).isoformat(),
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        await db.user_sessions.insert_one(session_doc)
        
        # Set session cookie
        response.set_cookie(
            key="session_token",
            value=session_token,
            httponly=True,
            secure=True,
            samesite="none",
            path="/",
            max_age=COOKIE_MAX_AGE_SECONDS
        )
        
        # Redirect to frontend dashboard with success
        frontend_url = os.environ.get('FRONTEND_URL', 'https://chessguru.ai')
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url=f"{frontend_url}/dashboard?auth=success")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Google OAuth error: {e}")
        raise HTTPException(status_code=500, detail="Authentication failed")

@api_router.post("/auth/session")
async def create_session(request: Request, response: Response):
    """Exchange session_id for session_token (Emergent auth - only works in Emergent environment)"""
    from llm_service import get_provider_mode
    
    # This endpoint only works in Emergent environment
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

@api_router.get("/auth/dev-login")
async def dev_login(response: Response):
    """
    DEV MODE ONLY: Auto-login without Google OAuth.
    Use this for local testing when Google OAuth redirect doesn't work.
    """
    if not DEV_MODE:
        raise HTTPException(status_code=403, detail="Dev login only available in DEV_MODE")
    
    # Get or create dev user
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
        # Fetch back without _id
        dev_user = await db.users.find_one({"user_id": DEV_USER_ID}, {"_id": 0})
    
    # Create session
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

@api_router.get("/auth/status")
async def auth_status():
    """Check if DEV_MODE is enabled"""
    return {"dev_mode": DEV_MODE}

@api_router.get("/auth/me")
async def get_me(user: User = Depends(get_current_user)):
    """Get current user profile"""
    return user.model_dump()

@api_router.post("/auth/logout")
async def logout(request: Request, response: Response):
    """Logout and clear session"""
    session_token = request.cookies.get("session_token")
    if session_token:
        await db.user_sessions.delete_many({"session_token": session_token})
    
    response.delete_cookie(key="session_token", path="/")
    return {"message": "Logged out successfully"}

class MobileAuthRequest(BaseModel):
    """Request for mobile Google authentication"""
    access_token: str

@api_router.post("/auth/google/mobile")
async def mobile_google_auth(request: MobileAuthRequest):
    """
    Authenticate mobile users with Google access token.
    Fetches user info from Google and creates/updates user.
    """
    # Validate access token is not empty
    if not request.access_token or not request.access_token.strip():
        raise HTTPException(status_code=401, detail="Access token is required")
    
    try:
        # Verify and get user info from Google
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
        
        # Create or update user
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
        
        # Create session
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

class DemoLoginRequest(BaseModel):
    """Request for demo login (testing only)"""
    email: str

@api_router.post("/auth/demo-login")
async def demo_login(request: DemoLoginRequest):
    """
    Demo login for testing the mobile app without Google OAuth.
    Creates or logs in a user with the provided email.
    """
    email = request.email.strip().lower()
    
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="Valid email required")
    
    # Create user ID from email
    user_id = f"demo_{email.replace('@', '_').replace('.', '_')}"
    session_token = f"demo_session_{uuid.uuid4().hex}"
    name = email.split("@")[0].title()
    
    # Check if user exists
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
    
    # Create session
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

# ==================== PLATFORM CONNECTION ROUTES ====================

@api_router.post("/connect-platform")
async def connect_platform(req: ConnectPlatformRequest, user: User = Depends(get_current_user)):
    """Connect Chess.com or Lichess username to user profile"""
    platform = req.platform.lower()
    username = req.username.strip()
    
    if platform == "chess.com":
        async with httpx.AsyncClient() as client_http:
            resp = await client_http.get(f"https://api.chess.com/pub/player/{username}")
            if resp.status_code != 200:
                raise HTTPException(status_code=400, detail="Chess.com username not found")
        
        await db.users.update_one(
            {"user_id": user.user_id},
            {"$set": {"chess_com_username": username}}
        )
    elif platform == "lichess":
        async with httpx.AsyncClient() as client_http:
            resp = await client_http.get(f"https://lichess.org/api/user/{username}")
            if resp.status_code != 200:
                raise HTTPException(status_code=400, detail="Lichess username not found")
        
        await db.users.update_one(
            {"user_id": user.user_id},
            {"$set": {"lichess_username": username}}
        )
    else:
        raise HTTPException(status_code=400, detail="Invalid platform")
    
    return {"message": f"Connected {platform} account: {username}"}

# ==================== GAME IMPORT ROUTES ====================

def parse_pgn_games(pgn_text: str, platform: str, user_username: str) -> List[Dict]:
    """Parse PGN text and extract games"""
    games = []
    current_game = {}
    moves = []
    in_moves = False
    
    for line in pgn_text.split('\n'):
        line = line.strip()
        if not line:
            if current_game and moves:
                current_game['pgn_moves'] = ' '.join(moves)
                games.append(current_game)
                current_game = {}
                moves = []
                in_moves = False
            continue
        
        if line.startswith('['):
            match = re.match(r'\[(\w+)\s+"(.*)"\]', line)
            if match:
                key, value = match.groups()
                current_game[key.lower()] = value
                in_moves = False
        else:
            in_moves = True
            moves.append(line)
    
    if current_game and moves:
        current_game['pgn_moves'] = ' '.join(moves)
        games.append(current_game)
    
    parsed_games = []
    for g in games:
        white = g.get('white', 'Unknown')
        black = g.get('black', 'Unknown')
        user_color = 'white' if white.lower() == user_username.lower() else 'black'
        
        full_pgn = ""
        for key, value in g.items():
            if key != 'pgn_moves':
                full_pgn += f'[{key.capitalize()} "{value}"]\n'
        full_pgn += f'\n{g.get("pgn_moves", "")}'
        
        parsed_games.append({
            'platform': platform,
            'pgn': full_pgn,
            'white_player': white,
            'black_player': black,
            'result': g.get('result', '*'),
            'time_control': g.get('timecontrol', g.get('event', '')),
            'date_played': g.get('date', g.get('utcdate', '')),
            'opening': g.get('opening', g.get('eco', '')),
            'user_color': user_color
        })
    
    return parsed_games

@api_router.post("/import-games")
async def import_games(req: ImportGamesRequest, user: User = Depends(get_current_user)):
    """Import games from Chess.com or Lichess"""
    platform = req.platform.lower()
    username = req.username.strip()
    
    games_to_import = []
    
    if platform == "chess.com":
        async with httpx.AsyncClient(timeout=30.0) as client_http:
            archives_resp = await client_http.get(
                f"https://api.chess.com/pub/player/{username}/games/archives"
            )
            if archives_resp.status_code != 200:
                raise HTTPException(status_code=400, detail="Could not fetch Chess.com archives")
            
            archives = archives_resp.json().get("archives", [])
            recent_archives = archives[-3:] if len(archives) > 3 else archives
            
            for archive_url in recent_archives:
                try:
                    pgn_url = archive_url + "/pgn"
                    pgn_resp = await client_http.get(pgn_url)
                    if pgn_resp.status_code == 200:
                        parsed = parse_pgn_games(pgn_resp.text, "chess.com", username)
                        games_to_import.extend(parsed[:20])
                except Exception as e:
                    logger.error(f"Error fetching archive: {e}")
                    continue
    
    elif platform == "lichess":
        async with httpx.AsyncClient(timeout=30.0) as client_http:
            resp = await client_http.get(
                f"https://lichess.org/api/games/user/{username}",
                params={"max": 30, "pgnInJson": False},
                headers={"Accept": "application/x-chess-pgn"}
            )
            if resp.status_code != 200:
                raise HTTPException(status_code=400, detail="Could not fetch Lichess games")
            
            parsed = parse_pgn_games(resp.text, "lichess", username)
            games_to_import.extend(parsed)
    
    else:
        raise HTTPException(status_code=400, detail="Invalid platform")
    
    imported_count = 0
    for game_data in games_to_import[:30]:
        existing = await db.games.find_one({
            "user_id": user.user_id,
            "pgn": game_data['pgn']
        })
        if existing:
            continue
        
        game = Game(
            user_id=user.user_id,
            **game_data
        )
        doc = game.model_dump()
        doc['imported_at'] = doc['imported_at'].isoformat()
        await db.games.insert_one(doc)
        imported_count += 1
    
    # GAMIFICATION: Award XP for importing games
    if imported_count > 0:
        try:
            for _ in range(imported_count):
                await add_xp(user.user_id, "game_imported")
                await increment_stat(user.user_id, "games_imported")
            
            # First game achievement
            if imported_count >= 1:
                await check_and_award_achievements(user.user_id, "games_imported", imported_count)
            
            await update_streak(user.user_id)
        except Exception as gam_err:
            logger.warning(f"Gamification update error (non-critical): {gam_err}")
    
    return {"imported": imported_count, "total_found": len(games_to_import)}

@api_router.get("/games")
async def get_games(user: User = Depends(get_current_user)):
    """Get all games for the current user"""
    games = await db.games.find(
        {"user_id": user.user_id},
        {"_id": 0}
    ).sort("imported_at", -1).to_list(100)
    return games


# IMPORTANT: These specific routes must come BEFORE /games/{game_id} wildcard
@api_router.get("/games/analyzed")
async def get_analyzed_games(user: User = Depends(get_current_user)):
    """Get list of all analyzed games with summary stats"""
    games = await db.games.find(
        {"user_id": user.user_id, "is_analyzed": True},
        {"_id": 0, "game_id": 1, "result": 1, "user_color": 1, "user_result": 1,
         "white_player": 1, "black_player": 1, "platform": 1, "imported_at": 1}
    ).sort("imported_at", -1).to_list(50)
    
    result = []
    for game in games:
        # Get analysis for this game
        analysis = await db.game_analyses.find_one(
            {"game_id": game["game_id"]},
            {"_id": 0, "accuracy": 1, "blunders": 1, "mistakes": 1, "best_moves": 1, "stockfish_analysis": 1}
        )
        
        # Determine opponent
        user_color = game.get("user_color", "white")
        opponent = game.get("black_player") if user_color == "white" else game.get("white_player")
        
        # Get accuracy from stockfish_analysis if available
        accuracy = 0
        if analysis:
            sf = analysis.get("stockfish_analysis", {})
            accuracy = sf.get("accuracy", analysis.get("accuracy", 0))
        
        result.append({
            "game_id": game["game_id"],
            "opponent": opponent or "Unknown",
            "result": game.get("user_result", "unknown"),
            "accuracy": round(accuracy, 1) if accuracy else 0,
            "blunders": analysis.get("blunders", 0) if analysis else 0,
            "mistakes": analysis.get("mistakes", 0) if analysis else 0,
            "best_moves": analysis.get("best_moves", 0) if analysis else 0,
            "platform": game.get("platform", "chess.com")
        })
    
    return {"games": result, "total": len(result)}


@api_router.get("/games/blunders")
async def get_all_blunders(user: User = Depends(get_current_user)):
    """Get all blunders from user's games with position and explanation"""
    # Get all analyzed games
    analyses = await db.game_analyses.find(
        {"user_id": user.user_id},
        {"_id": 0, "game_id": 1, "commentary": 1, "stockfish_analysis": 1}
    ).to_list(100)
    
    blunders = []
    for analysis in analyses:
        commentary = analysis.get("commentary", [])
        sf_analysis = analysis.get("stockfish_analysis", {})
        move_evals = sf_analysis.get("move_evaluations", [])
        
        # Create a map of move_number to FEN
        fen_map = {m.get("move_number"): m.get("fen_before") for m in move_evals}
        
        for move in commentary:
            if move.get("evaluation") in ["blunder", "mistake"]:
                move_num = move.get("move_number")
                # Try to get FEN from stockfish data
                fen = fen_map.get(move_num, "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")
                
                blunders.append({
                    "game_id": analysis["game_id"],
                    "move_number": move_num,
                    "move": move.get("move"),
                    "evaluation": move.get("evaluation"),
                    "fen": fen,
                    "feedback": move.get("feedback", ""),
                    "consider": move.get("consider", ""),
                    "threat": move.get("details", {}).get("threat_line"),
                    "thinking_pattern": move.get("details", {}).get("thinking_pattern")
                })
    
    # Sort by most recent (game_id contains timestamp info)
    blunders.sort(key=lambda x: x["game_id"], reverse=True)
    
    return {"blunders": blunders[:50], "total": len(blunders)}


@api_router.get("/games/best-moves")
async def get_all_best_moves(user: User = Depends(get_current_user)):
    """Get all best/excellent moves from user's games"""
    # Get all analyzed games
    analyses = await db.game_analyses.find(
        {"user_id": user.user_id},
        {"_id": 0, "game_id": 1, "commentary": 1, "stockfish_analysis": 1}
    ).to_list(100)
    
    best_moves = []
    for analysis in analyses:
        commentary = analysis.get("commentary", [])
        sf_analysis = analysis.get("stockfish_analysis", {})
        move_evals = sf_analysis.get("move_evaluations", [])
        
        # Create a map of move_number to data
        move_data_map = {m.get("move_number"): m for m in move_evals}
        
        # First, check commentary for best/excellent/good
        for move in commentary:
            if move.get("evaluation") in ["best", "excellent", "good"]:
                move_num = move.get("move_number")
                move_data = move_data_map.get(move_num, {})
                fen = move_data.get("fen_before", "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")
                
                best_moves.append({
                    "game_id": analysis["game_id"],
                    "move_number": move_num,
                    "move": move.get("move"),
                    "evaluation": move.get("evaluation"),
                    "fen": fen,
                    "feedback": move.get("feedback", ""),
                    "intent": move.get("intent", "")
                })
        
        # Also check stockfish evaluations for moves with very low cp_loss (excellent moves)
        for move_data in move_evals:
            cp_loss = move_data.get("cp_loss", 100)
            eval_type = move_data.get("evaluation", "")
            if hasattr(eval_type, "value"):
                eval_type = eval_type.value
            
            # Moves with < 5 centipawn loss are excellent
            if cp_loss <= 5 and eval_type not in ["blunder", "mistake", "inaccuracy"]:
                move_num = move_data.get("move_number")
                # Avoid duplicates
                if not any(m["game_id"] == analysis["game_id"] and m["move_number"] == move_num for m in best_moves):
                    best_moves.append({
                        "game_id": analysis["game_id"],
                        "move_number": move_num,
                        "move": move_data.get("move", ""),
                        "evaluation": "excellent" if cp_loss == 0 else "good",
                        "fen": move_data.get("fen_before", ""),
                        "feedback": f"Perfect move with {cp_loss} centipawn loss",
                        "intent": ""
                    })
    
    # Sort and limit
    best_moves.sort(key=lambda x: (x["game_id"], x["move_number"]), reverse=True)
    
    return {"best_moves": best_moves[:50], "total": len(best_moves)}


@api_router.get("/games/{game_id}")
async def get_game(game_id: str, user: User = Depends(get_current_user)):
    """Get a specific game with player names and termination reason"""
    import re
    
    game = await db.games.find_one(
        {"game_id": game_id, "user_id": user.user_id},
        {"_id": 0}
    )
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    
    # Extract player names from PGN if not already present
    pgn = game.get("pgn", "")
    if pgn:
        white_match = re.search(r'\[White "([^"]+)"\]', pgn)
        black_match = re.search(r'\[Black "([^"]+)"\]', pgn)
        game["white_player"] = white_match.group(1) if white_match else "White"
        game["black_player"] = black_match.group(1) if black_match else "Black"
        
        # Extract ratings from PGN
        white_elo_match = re.search(r'\[WhiteElo "(\d+)"\]', pgn)
        black_elo_match = re.search(r'\[BlackElo "(\d+)"\]', pgn)
        if white_elo_match:
            game["white_rating"] = int(white_elo_match.group(1))
        if black_elo_match:
            game["black_rating"] = int(black_elo_match.group(1))
        
        # Also try to extract termination from PGN if not stored
        if not game.get("termination"):
            term_match = re.search(r'\[Termination "([^"]+)"\]', pgn)
            if term_match:
                game["termination"] = term_match.group(1).lower()
    else:
        game["white_player"] = "White"
        game["black_player"] = "Black"
    
    # Generate human-readable termination text
    termination = game.get("termination", "")
    user_color = game.get("user_color", "white")
    result = game.get("result", "")
    
    # Determine if user won or lost
    if user_color == "white":
        user_won = result == "1-0"
    else:
        user_won = result == "0-1"
    
    termination_text = ""
    if termination == "timeout":
        termination_text = "You lost on time" if not user_won else "Opponent lost on time"
    elif termination == "resigned":
        termination_text = "You resigned" if not user_won else "Opponent resigned"
    elif termination == "checkmated":
        termination_text = "You got checkmated" if not user_won else "You checkmated opponent"
    elif termination == "won":
        termination_text = "You won" if user_won else "You lost"
    elif termination == "stalemate":
        termination_text = "Draw by stalemate"
    elif termination == "repetition":
        termination_text = "Draw by repetition"
    elif termination == "insufficient_material":
        termination_text = "Draw - insufficient material"
    elif termination == "draw_agreed":
        termination_text = "Draw by agreement"
    
    game["termination_text"] = termination_text
    
    return game

# ==================== AI ANALYSIS ROUTES ====================

async def get_user_mistake_context(user_id: str) -> str:
    """Get user's mistake history for AI context"""
    patterns = await db.mistake_patterns.find(
        {"user_id": user_id},
        {"_id": 0}
    ).sort("occurrences", -1).to_list(10)
    
    if not patterns:
        return "This is a new player with no previous mistake history."
    
    context_parts = ["Here are the player's recurring mistakes:"]
    for p in patterns:
        days_ago = (datetime.now(timezone.utc) - datetime.fromisoformat(p['last_seen'].replace('Z', '+00:00') if isinstance(p['last_seen'], str) else p['last_seen'].isoformat())).days if isinstance(p.get('last_seen'), (str, datetime)) else 0
        context_parts.append(
            f"- {p['subcategory']} ({p['category']}): seen {p['occurrences']} times, "
            f"last occurrence {days_ago} days ago. {p['description']}"
        )
    
    return "\n".join(context_parts)

@api_router.post("/analyze-game")
async def analyze_game(req: AnalyzeGameRequest, background_tasks: BackgroundTasks, user: User = Depends(get_current_user)):
    """Analyze a game with Stockfish engine + AI coaching using PlayerProfile + RAG"""
    import json
    
    game = await db.games.find_one(
        {"game_id": req.game_id, "user_id": user.user_id},
        {"_id": 0}
    )
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    
    existing_analysis = await db.game_analyses.find_one(
        {"game_id": req.game_id},
        {"_id": 0}
    )
    
    # If force re-analysis, delete old analysis first
    if existing_analysis and req.force:
        await db.game_analyses.delete_one({"game_id": req.game_id})
        existing_analysis = None
        logger.info(f"Force re-analysis requested for game {req.game_id}")
    
    if existing_analysis:
        return existing_analysis
    
    # ============ STEP 0: STOCKFISH ENGINE ANALYSIS (ACCURATE MOVE EVALUATION) ============
    # Stockfish is the ONLY source of truth for blunders/mistakes/accuracy
    # We retry up to 3 times if it fails
    logger.info(f"Running Stockfish analysis for game {req.game_id}")
    user_color = game.get('user_color', 'white')
    
    stockfish_result = None
    max_stockfish_retries = STOCKFISH_MAX_RETRIES
    
    for attempt in range(max_stockfish_retries):
        try:
            stockfish_result = analyze_game_with_stockfish(
                game['pgn'], 
                user_color=user_color,
                depth=STOCKFISH_DEPTH  # Good balance of speed and accuracy
            )
            
            if stockfish_result and stockfish_result.get("success"):
                # Verify we actually got data
                user_stats = stockfish_result.get("user_stats", {})
                if user_stats.get("accuracy", 0) > 0 or len(stockfish_result.get("moves", [])) > 0:
                    logger.info(f"Stockfish analysis succeeded on attempt {attempt + 1}")
                    break
                else:
                    logger.warning(f"Stockfish returned empty data on attempt {attempt + 1}, retrying...")
                    stockfish_result = None
            else:
                logger.warning(f"Stockfish analysis failed on attempt {attempt + 1}: {stockfish_result.get('error') if stockfish_result else 'No result'}")
                stockfish_result = None
        except Exception as e:
            logger.error(f"Stockfish analysis error on attempt {attempt + 1}: {e}")
            stockfish_result = None
        
        if attempt < max_stockfish_retries - 1:
            import asyncio
            await asyncio.sleep(1)  # Brief pause before retry
    
    if not stockfish_result or not stockfish_result.get("success"):
        logger.error(f"Stockfish analysis failed after {max_stockfish_retries} attempts for game {req.game_id}")
    
    # Extract Stockfish evaluations for GPT context
    stockfish_context = ""
    stockfish_move_data = []
    if stockfish_result and stockfish_result.get("success"):
        user_stats = stockfish_result.get("user_stats", {})
        moves = stockfish_result.get("moves", [])
        
        # Build context for GPT
        stockfish_context = f"""
=== STOCKFISH ENGINE ANALYSIS (DEPTH 18) ===
Player: {user_color}
Accuracy: {user_stats.get('accuracy', 0)}%
Blunders: {user_stats.get('blunders', 0)}
Mistakes: {user_stats.get('mistakes', 0)}  
Inaccuracies: {user_stats.get('inaccuracies', 0)}
Best Moves: {user_stats.get('best_moves', 0)}
Excellent Moves: {user_stats.get('excellent_moves', 0)}
Average CP Loss: {user_stats.get('avg_cp_loss', 0)}

=== MOVE-BY-MOVE ENGINE EVALUATION ===
"""
        # Include significant moves (blunders, mistakes, inaccuracies)
        significant_moves = [m for m in moves if m.get('evaluation') in ['blunder', 'mistake', 'inaccuracy']]
        for m in significant_moves[:10]:  # Limit to top 10 bad moves
            eval_type = m.get('evaluation', 'unknown')
            # Handle both string and enum types
            if hasattr(eval_type, 'value'):
                eval_type = eval_type.value
            
            stockfish_context += f"""
Move {m.get('move_number')}: {m.get('move')} ({eval_type.upper()})
- CP Loss: {m.get('cp_loss', 0)} centipawns
- Best was: {m.get('best_move')}
- Eval before: {m.get('eval_before', 0)/100:.1f} → after: {m.get('eval_after', 0)/100:.1f}"""
            
            # Add PV lines for mistakes (these explain WHY it's bad)
            if eval_type.lower() in ['inaccuracy', 'mistake', 'blunder']:
                threat = m.get('threat')
                pv_played = m.get('pv_after_played', [])
                pv_best = m.get('pv_after_best', [])
                
                if threat:
                    stockfish_context += f"\n- OPPONENT'S THREAT: {threat}"
                if pv_played:
                    stockfish_context += f"\n- LINE AFTER YOUR MOVE: {' '.join(pv_played)}"
                if pv_best:
                    stockfish_context += f"\n- LINE AFTER BEST MOVE: {m.get('best_move')} {' '.join(pv_best)}"
            
            stockfish_context += "\n"
        stockfish_move_data = moves
        logger.info(f"Stockfish: {user_stats.get('blunders', 0)} blunders, {user_stats.get('mistakes', 0)} mistakes, {user_stats.get('accuracy', 0)}% accuracy")
    
    # Step 1: Get or create PlayerProfile (FIRST-CLASS requirement)
    logger.info(f"Loading PlayerProfile for user {user.user_id}")
    profile = await get_or_create_profile(db, user.user_id, user.name)
    
    # Step 2: Build RAG context (SUPPORTS memory, doesn't define habits)
    logger.info(f"Building RAG context for game {req.game_id}")
    rag_context = await build_rag_context(db, user.user_id, game)
    
    # Step 3: Get user's first name
    first_name = user.name.split()[0] if user.name else "friend"
    
    # Step 4: Build explicit memory context for coach
    top_weaknesses = profile.get("top_weaknesses", [])[:3]
    improvement_trend = profile.get("improvement_trend", "stuck")
    games_analyzed = profile.get("games_analyzed_count", 0)
    
    # Build memory call-out strings
    memory_callouts = []
    for w in top_weaknesses:
        subcat = w.get("subcategory", "").replace("_", " ")
        count = w.get("occurrence_count", 0)
        if count >= 3:
            memory_callouts.append(f"- {subcat}: seen {count} times before")
        elif count >= 2:
            memory_callouts.append(f"- {subcat}: this happened before")
    
    memory_section = ""
    if memory_callouts:
        memory_section = "COACH MEMORY (reference these when relevant):\n" + "\n".join(memory_callouts)
    
    # Build improvement awareness
    improvement_note = ""
    if improvement_trend == "improving":
        improvement_note = "STATUS: Student is IMPROVING. Acknowledge progress."
    elif improvement_trend == "regressing":
        improvement_note = "STATUS: Student needs support. Be encouraging, focus on basics."
    else:
        improvement_note = "STATUS: Student is steady. Gentle push to improve."
    
    system_prompt = f"""You are an experienced chess coach with a warm, calm teaching style.

Your approach:
- Patient, principle-driven, supportive
- Focus on thinking habits, not moves
- Simple English, short sentences
- Sound like a mentor, not a commentator
- Use Indian warmth sparingly (max once in summary, e.g., "Well done" not "Beta" repeatedly)

IMPORTANT: I have already analyzed this game with Stockfish (world's best chess engine).
The engine data below is ACCURATE - trust it completely for move evaluations.

=== HOW TO EXPLAIN MISTAKES ===
For INACCURACIES/MISTAKES/BLUNDERS, Stockfish provides:
- OPPONENT'S THREAT: The move that punishes your mistake
- LINE AFTER YOUR MOVE: What happens next (shows the problem)
- LINE AFTER BEST MOVE: What would have happened with the better choice

YOUR JOB: Turn these concrete lines into human coaching:
1. Explain what THREAT you missed (use the exact threat move from data)
2. Show WHY it hurts (use the line to explain consequences)
3. Compare to the better move (what you avoid by playing correctly)

Example transformation:
ENGINE DATA: Move 7: Qxb4 (INACCURACY), THREAT: Bb5+, LINE: Bb5+ Kf7 Ng5+
YOUR EXPLANATION: "You grabbed the pawn with Qxb4, but White has Bb5+ check. After Kf7 forced, Ng5+ comes with another attack. Your king gets stuck in the center - that's the real cost of taking that pawn."

DO NOT make up chess analysis. ONLY use the lines provided.
If no line is provided, give a general principle explanation.

{stockfish_context}

{first_name} played as {game['user_color']} in this game.
Games analyzed together: {games_analyzed}

{memory_section}

{improvement_note}

=== COACHING RULES ===

1. MEMORY REFERENCE (builds trust)
   - If current mistake matches a known weakness, mention it briefly
   - Example: "We've seen this pattern before."
   - Keep it to 1 sentence, non-judgmental

2. HABIT-FIRST EXPLANATIONS  
   - Explain "what thinking habit caused this" not "what move was wrong"
   - One thinking error per mistake
   - Advice must apply to future games

3. COACH TONE
   - Warm but professional
   - Use Indian warmth sparingly (max once in summary)
   - Avoid: "Great job!", "Amazing!", "Brilliant!"
   - Prefer: "Good", "Solid", "Well played", "This needs work"

4. CRITICAL: CONSISTENCY RULE
   - If move is "good" or "solid" → NO negative thinking_pattern
   - If move is "good" or "solid" → thinking_pattern must be "solid_thinking" or null
   - Negative patterns ONLY for mistakes/blunders/inaccuracies

5. CONCEPTUAL GUIDANCE (no engine moves)
   - ❌ "Better: Play d5 earlier"
   - ✅ "Consider: Challenge the center with a pawn break"
   - ✅ "Think about: Developing before attacking"
   - Keep suggestions conceptual, applicable to any game

=== OUTPUT FORMAT (STRICT JSON) ===
{{
    "commentary": [
        {{
            "move_number": 5,
            "move": "h6",
            "evaluation": "inaccuracy",
            "intent": "What you were thinking (1 short sentence)",
            "feedback": "Coach feedback using CONCRETE lines from Stockfish data - mention the threat move and what happens (2-3 sentences)",
            "consider": "The better move and WHY it's better (use the PV line to explain)",
            "memory_note": "Brief memory reference if this matches past weakness (null otherwise)",
            "details": {{
                "thinking_pattern": "ONLY for mistakes: rushing, tunnel_vision, hope_chess, etc. For good moves: solid_thinking or null",
                "threat_line": "The EXACT threat from Stockfish (e.g., 'exd5 Qxd5 Nc3')",
                "rule": "A principle for future games"
            }}
        }}
    ],
    "blunders": 0,
    "mistakes": 0, 
    "inaccuracies": 0,
    "best_moves": 0,
    "summary_p1": "2 sentences: Overall game assessment - what went well, where discipline showed.",
    "summary_p2": "2 sentences: The one habit to focus on + instruction for next game.",
    "improvement_note": "One sentence about progress trend (null if no data)",
    "identified_weaknesses": [
        {{
            "category": "tactical",
            "subcategory": "pin_blindness",
            "habit_description": "What thinking pattern caused this",
            "practice_tip": "What to practice"
        }}
    ],
    "identified_strengths": [
        {{
            "category": "tactical", 
            "subcategory": "good_development",
            "description": "What they did well"
        }}
    ],
    "best_move_suggestions": [
        {{
            "move_number": 15,
            "best_move": "Nf3",
            "reason": "Controls the center and prepares castling"
        }}
    ],
    "focus_this_week": "The ONE habit to work on",
    "voice_script": "30-second calm spoken summary"
}}

=== STRICT RULES ===
1. NO engine language: no "stockfish", no centipawns, no "+0.5"
2. NO flashy commentary: no "Amazing!", "Brilliant!", "What a blunder!"
3. ONE lesson per mistake only
4. "Good/solid" moves NEVER get negative thinking_pattern
5. For MISTAKES: "consider" must reference the BETTER MOVE from Stockfish data and explain WHY using the PV line
6. For GOOD moves: "consider" should be null
7. Keep everything focused - coaches explain using actual moves, not vague principles
8. Memory references are factual, never shaming
9. STRENGTHS must be POSITIVE patterns only (e.g., "good_development", "solid_defense", "active_pieces")
   NEVER list weaknesses as strengths. If no clear strength, leave empty array.
10. For key blunders/mistakes, the "feedback" MUST mention:
    - The THREAT move opponent has (from OPPONENT'S THREAT in data)
    - What happens after (from LINE AFTER YOUR MOVE)
    Example: "After Qxb4, White has Bb5+ check. After Kf7, Ng5+ continues the attack."

Evaluations: "blunder", "mistake", "inaccuracy", "good", "solid", "neutral"
"""

    try:
        # CQS: Track regeneration attempts
        cqs_scores = []
        best_analysis_data = None
        best_cqs_result = None
        has_memory = len(memory_callouts) > 0
        
        for attempt in range(MAX_REGENERATIONS + 1):
            # Build prompt with stricter constraints on regeneration
            current_prompt = system_prompt
            if attempt > 0:
                stricter_rules = get_stricter_prompt_constraints(attempt)
                current_prompt = system_prompt + "\n" + stricter_rules
                logger.info(f"CQS: Regenerating analysis for {req.game_id}, attempt {attempt + 1}")
            
            # Use OpenAI directly
            response = await call_llm(
                system_message=current_prompt,
                user_message=f"Please analyze this game:\n\n{game['pgn']}",
                model="gpt-4o-mini"
            )
        
            response_clean = response.strip()
            if response_clean.startswith("```json"):
                response_clean = response_clean[7:]
            if response_clean.startswith("```"):
                response_clean = response_clean[3:]
            if response_clean.endswith("```"):
                response_clean = response_clean[:-3:]
            
            try:
                analysis_data = json.loads(response_clean)
            except json.JSONDecodeError as e:
                logger.error(f"JSON parse error on attempt {attempt + 1}: {e}")
                continue
            
            # CQS: Evaluate quality
            cqs_result = calculate_cqs(
                analysis_data,
                has_memory=has_memory,
                memory_callouts=memory_callouts
            )
            cqs_scores.append(cqs_result["total_score"])
            
            # Log the result (internal only)
            log_cqs_result(req.game_id, cqs_result, attempt + 1, not cqs_result["should_regenerate"])
            
            # Keep track of best result
            if best_analysis_data is None or cqs_result["total_score"] > best_cqs_result["total_score"]:
                best_analysis_data = analysis_data
                best_cqs_result = cqs_result
            
            # Check if we should accept
            if not cqs_result["should_regenerate"]:
                break
            
            # If this is the last attempt, we'll use the best one
            if attempt >= MAX_REGENERATIONS:
                break
        
        # Use the best analysis data
        analysis_data = best_analysis_data
        cqs_result = best_cqs_result
        
        # Validate explanations against contract
        validated_commentary = []
        for item in analysis_data.get("commentary", []):
            explanation = item.get("explanation", {})
            if explanation:
                is_valid, errors = validate_explanation(explanation)
                if not is_valid:
                    logger.warning(f"Explanation validation failed: {errors}")
                    # Fix common issues
                    if len(explanation.get("thinking_error", "")) < 10:
                        explanation["thinking_error"] = "Move was made without full board awareness"
                    if len(explanation.get("one_repeatable_rule", "")) < 10:
                        explanation["one_repeatable_rule"] = "Always scan the whole board before moving"
            validated_commentary.append(item)
        
        # Map weaknesses to predefined categories with full details
        categorized_weaknesses = []
        for w in analysis_data.get("identified_weaknesses", []) or analysis_data.get("identified_patterns", []):
            cat, subcat = categorize_weakness(
                w.get("category", "tactical"),
                w.get("subcategory", "one_move_blunders")
            )
            categorized_weaknesses.append({
                "category": cat,
                "subcategory": subcat,
                "description": w.get("description", ""),
                "advice": w.get("advice", ""),
                "display_name": subcat.replace("_", " ").title()
            })
        
        # STOCKFISH is the ONLY source of truth for move evaluation
        # GPT is ONLY for commentary text, never for blunder/mistake counts
        sf_stats = stockfish_result.get("user_stats", {}) if stockfish_result else {}
        
        # Check if Stockfish analysis was successful
        stockfish_valid = stockfish_result and stockfish_result.get("success", False)
        stockfish_has_data = sf_stats.get("accuracy", 0) > 0 or len(stockfish_result.get("moves", [])) > 0 if stockfish_result else False
        
        if not stockfish_valid or not stockfish_has_data:
            # Stockfish failed - log warning and mark analysis as incomplete
            logger.warning(f"Stockfish analysis failed for game {req.game_id}. Analysis will be marked as incomplete.")
            analysis_incomplete = True
        else:
            analysis_incomplete = False
        
        analysis = GameAnalysis(
            game_id=req.game_id,
            user_id=user.user_id,
            commentary=validated_commentary,
            blunders=sf_stats.get("blunders", 0),
            mistakes=sf_stats.get("mistakes", 0),
            inaccuracies=sf_stats.get("inaccuracies", 0),
            best_moves=sf_stats.get("best_moves", 0),
            overall_summary=analysis_data.get("overall_summary", ""),
            identified_patterns=[]  # Legacy field - will also store full data separately
        )
        
        # Store voice script and key lesson for future use
        voice_script = analysis_data.get("voice_script", analysis_data.get("voice_script_summary", ""))
        focus_week = analysis_data.get("focus_this_week", analysis_data.get("key_lesson", ""))
        
        # Update mistake_patterns collection (legacy support for pattern IDs)
        for pattern_data in categorized_weaknesses:
            existing_pattern = await db.mistake_patterns.find_one({
                "user_id": user.user_id,
                "category": pattern_data["category"],
                "subcategory": pattern_data["subcategory"]
            })
            
            if existing_pattern:
                await db.mistake_patterns.update_one(
                    {"pattern_id": existing_pattern["pattern_id"]},
                    {
                        "$inc": {"occurrences": 1},
                        "$push": {"game_ids": req.game_id},
                        "$set": {"last_seen": datetime.now(timezone.utc).isoformat()}
                    }
                )
                analysis.identified_patterns.append(existing_pattern["pattern_id"])
            else:
                new_pattern = MistakePattern(
                    user_id=user.user_id,
                    category=pattern_data["category"],
                    subcategory=pattern_data["subcategory"],
                    description=pattern_data.get("description", ""),
                    game_ids=[req.game_id]
                )
                pattern_doc = new_pattern.model_dump()
                pattern_doc['first_seen'] = pattern_doc['first_seen'].isoformat()
                pattern_doc['last_seen'] = pattern_doc['last_seen'].isoformat()
                await db.mistake_patterns.insert_one(pattern_doc)
                pattern_doc.pop('_id', None)
                analysis.identified_patterns.append(new_pattern.pattern_id)
        
        analysis_doc = analysis.model_dump()
        analysis_doc['created_at'] = analysis_doc['created_at'].isoformat()
        
        # Store full data for frontend display
        analysis_doc['weaknesses'] = categorized_weaknesses
        analysis_doc['identified_weaknesses'] = categorized_weaknesses
        analysis_doc['strengths'] = analysis_data.get("identified_strengths", [])
        analysis_doc['focus_this_week'] = focus_week
        analysis_doc['key_lesson'] = focus_week  # Backward compatibility
        analysis_doc['voice_script_summary'] = voice_script
        analysis_doc['summary_p1'] = analysis_data.get("summary_p1", "")
        analysis_doc['summary_p2'] = analysis_data.get("summary_p2", "")
        analysis_doc['improvement_note'] = analysis_data.get("improvement_note", "")
        
        # Mark if Stockfish analysis failed - user can retry
        analysis_doc['stockfish_failed'] = analysis_incomplete
        if analysis_incomplete:
            analysis_doc['stockfish_error'] = "Stockfish engine analysis failed. Stats may be inaccurate. Please retry analysis."
        
        # Use Stockfish best move suggestions (accurate) - merge with GPT's reasoning
        stockfish_best_moves = []
        if stockfish_move_data:
            for m in stockfish_move_data:
                # Get evaluation type safely
                eval_type = m.get('evaluation', 'unknown')
                if hasattr(eval_type, 'value'):
                    eval_type = eval_type.value
                    
                if eval_type in ['blunder', 'mistake'] and m.get('best_move'):
                    stockfish_best_moves.append({
                        "move_number": m.get('move_number'),
                        "played_move": m.get('move'),
                        "best_move": m.get('best_move'),
                        "cp_loss": m.get('cp_loss', 0),
                        "evaluation": eval_type,
                        "reason": f"Engine analysis shows this loses {m.get('cp_loss', 0)/100:.1f} pawns",
                        "pv": m.get('pv_after_best', [])  # Include PV line for playback on board
                    })
        analysis_doc['best_move_suggestions'] = stockfish_best_moves or analysis_data.get("best_move_suggestions", [])
        
        # Store Stockfish accuracy and detailed move analysis
        if stockfish_result and stockfish_result.get("success"):
            analysis_doc['stockfish_analysis'] = {
                "accuracy": sf_stats.get("accuracy", 0),
                "avg_cp_loss": sf_stats.get("avg_cp_loss", 0),
                "excellent_moves": sf_stats.get("excellent_moves", 0),
                "move_evaluations": stockfish_move_data
            }
        
        # ============ PHASE-AWARE STRATEGIC COACHING ============
        # Analyze game phases and provide rating-adaptive strategic lessons
        try:
            # Get user's rating for adaptive content
            user_rating = DEFAULT_RATING  # Default
            
            # Try to get rating from player profile
            player_profile = await db.player_profiles.find_one(
                {"user_id": user.user_id},
                {"_id": 0, "current_rating": 1}
            )
            if player_profile and player_profile.get("current_rating"):
                user_rating = player_profile.get("current_rating", DEFAULT_RATING)
            
            # Analyze game phases with rating-adaptive content
            phase_analysis = analyze_game_phases(game['pgn'], user_color, user_rating)
            
            if phase_analysis and not phase_analysis.get("error"):
                analysis_doc['phase_analysis'] = {
                    "phases": phase_analysis.get("phases", []),
                    "final_phase": phase_analysis.get("final_phase", "unknown"),
                    "endgame_info": phase_analysis.get("endgame_info"),
                    "phase_summary": phase_analysis.get("phase_summary", ""),
                    "total_moves": phase_analysis.get("total_moves", 0),
                    "phase_transitions": phase_analysis.get("phase_transitions", [])
                }
                
                # Strategic lesson - rating-adaptive
                strategic_lesson = phase_analysis.get("strategic_lesson", {})
                analysis_doc['strategic_lesson'] = {
                    "lesson_title": strategic_lesson.get("lesson_title", ""),
                    "what_to_remember": strategic_lesson.get("what_to_remember", []),
                    "theory_to_study": strategic_lesson.get("theory_to_study", []),
                    "one_sentence_takeaway": strategic_lesson.get("one_sentence_takeaway", ""),
                    "next_step": strategic_lesson.get("next_step", ""),
                    "phase_reached": strategic_lesson.get("phase_reached", ""),
                    "rating_bracket": strategic_lesson.get("rating_bracket", "intermediate")
                }
                
                # Phase-specific theory - rating-adaptive
                theory = phase_analysis.get("theory", {})
                analysis_doc['phase_theory'] = {
                    "phase": theory.get("phase", ""),
                    "key_principles": theory.get("key_principles", []),
                    "key_concept": theory.get("key_concept", ""),
                    "one_thing_to_remember": theory.get("one_thing_to_remember", ""),
                    "specific_advice": theory.get("specific_advice", []),
                    "rating_bracket": theory.get("rating_bracket", "intermediate")
                }
                
                logger.info(f"Phase analysis complete: {phase_analysis.get('final_phase')} phase, rating bracket: {get_rating_bracket(user_rating)}")
        except Exception as phase_err:
            logger.warning(f"Phase analysis failed (non-critical): {phase_err}")
        
        # CQS: Store internal metadata (NEVER exposed to users)
        analysis_doc['_cqs_internal'] = {
            "score": cqs_result["total_score"],
            "breakdown": cqs_result["breakdown"],
            "quality_level": cqs_result["quality_level"],
            "regeneration_attempts": len(cqs_scores),
            "all_scores": cqs_scores
        }
        
        await db.game_analyses.insert_one(analysis_doc)
        
        await db.games.update_one(
            {"game_id": req.game_id},
            {"$set": {"is_analyzed": True}}
        )
        
        # Remove _id before returning
        analysis_doc.pop('_id', None)
        
        # IMPORTANT: Remove internal CQS data before returning to user
        analysis_doc.pop('_cqs_internal', None)
        
        # ============ MISTAKE MASTERY SYSTEM ============
        # Extract mistake cards from this analysis for spaced repetition training
        try:
            cards_created = await extract_mistake_cards_from_analysis(
                db, user.user_id, req.game_id, analysis_doc, game
            )
            if cards_created:
                logger.info(f"Created {len(cards_created)} mistake cards for user {user.user_id}")
        except Exception as card_err:
            logger.warning(f"Mistake card extraction failed (non-critical): {card_err}")
        
        # Step 5: UPDATE PLAYER PROFILE (CRITICAL - happens after every game)
        logger.info(f"Updating PlayerProfile for user {user.user_id}")
        background_tasks.add_task(
            update_profile_after_analysis,
            db,
            user.user_id,
            req.game_id,
            analysis_data.get("blunders", 0),
            analysis_data.get("mistakes", 0),
            analysis_data.get("best_moves", 0),
            categorized_weaknesses,
            analysis_data.get("identified_strengths", [])
        )
        
        # Create RAG embeddings in background (RAG supports memory, doesn't define habits)
        background_tasks.add_task(create_game_embeddings, db, game, user.user_id)
        background_tasks.add_task(create_analysis_embedding, db, analysis_doc, game, user.user_id)
        
        # GAMIFICATION: Award XP for game analysis
        try:
            await add_xp(user.user_id, "game_analyzed")
            await increment_stat(user.user_id, "games_analyzed")
            
            # Bonus XP for high accuracy
            accuracy = sf_stats.get("accuracy", 0)
            if accuracy >= 90:
                await add_xp(user.user_id, "accuracy_90_plus")
            await update_best_accuracy(user.user_id, accuracy)
            
            # Award for no blunders
            if sf_stats.get("blunders", 0) == 0:
                await add_xp(user.user_id, "no_blunders")
                await increment_stat(user.user_id, "no_blunders_games")
            
            # Update streak
            await update_streak(user.user_id)
        except Exception as gam_err:
            logger.warning(f"Gamification update error (non-critical): {gam_err}")
        
        for pattern_data in categorized_weaknesses:
            pattern = await db.mistake_patterns.find_one({
                "user_id": user.user_id,
                "category": pattern_data["category"],
                "subcategory": pattern_data["subcategory"]
            }, {"_id": 0})
            if pattern:
                background_tasks.add_task(create_pattern_embedding, db, pattern, user.user_id)
        
        return analysis_doc
        
    except Exception as e:
        logger.error(f"Analysis error: {e}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

@api_router.get("/analysis/{game_id}")
async def get_analysis(game_id: str, user: User = Depends(get_current_user)):
    """Get analysis for a specific game"""
    analysis = await db.game_analyses.find_one(
        {"game_id": game_id, "user_id": user.user_id},
        {"_id": 0, "_cqs_internal": 0}  # Exclude internal CQS data
    )
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    
    # Also get the game to extract full move list
    game = await db.games.find_one(
        {"game_id": game_id},
        {"_id": 0, "pgn": 1, "user_color": 1}
    )
    
    if game and game.get("pgn"):
        # Parse PGN to get all moves
        import chess.pgn
        import io
        try:
            pgn_io = io.StringIO(game["pgn"])
            chess_game = chess.pgn.read_game(pgn_io)
            if chess_game:
                full_moves = []
                board = chess_game.board()
                move_number = 1
                for i, move in enumerate(chess_game.mainline_moves()):
                    fen_before = board.fen()
                    san = board.san(move)
                    is_white = (i % 2 == 0)
                    
                    # Find if this move has commentary (user's move)
                    user_color = game.get("user_color", "white")
                    is_user_move = (is_white and user_color == "white") or (not is_white and user_color == "black")
                    
                    # Look up evaluation from commentary
                    evaluation = "neutral"
                    feedback = None
                    if is_user_move:
                        for c in analysis.get("commentary", []):
                            if c.get("move_number") == (move_number if is_white else move_number) and c.get("move") == san:
                                evaluation = c.get("evaluation", "neutral")
                                feedback = c.get("feedback")
                                break
                    
                    full_moves.append({
                        "ply": i,
                        "move_number": move_number if is_white else move_number,
                        "move": san,
                        "fen": fen_before,
                        "is_white": is_white,
                        "is_user_move": is_user_move,
                        "evaluation": evaluation if is_user_move else "opponent",
                        "feedback": feedback
                    })
                    
                    board.push(move)
                    if not is_white:
                        move_number += 1
                
                analysis["full_moves"] = full_moves
        except Exception as e:
            logger.warning(f"Failed to parse PGN for full moves: {e}")
    
    return analysis

# ==================== VOICE COACHING (TTS) ROUTES ====================

class TTSRequest(BaseModel):
    text: str
    voice: str = "onyx"  # Male coach voice - deep, authoritative

@api_router.post("/tts/generate")
async def generate_speech(req: TTSRequest, user: User = Depends(get_current_user)):
    """Generate speech audio from text using OpenAI TTS"""
    import base64
    
    if not req.text or len(req.text.strip()) == 0:
        raise HTTPException(status_code=400, detail="Text is required")
    
    # Limit text length (OpenAI TTS limit is 4096 chars)
    text = req.text[:4000]
    
    try:
        audio_bytes = await call_tts(text=text, voice=req.voice)
        audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
        
        return {
            "audio_base64": audio_base64,
            "format": "mp3",
            "voice": req.voice
        }
        
    except Exception as e:
        logger.error(f"TTS generation error: {e}")
        raise HTTPException(status_code=500, detail=f"Voice generation failed: {str(e)}")

@api_router.post("/tts/analysis-summary/{game_id}")
async def generate_analysis_voice(game_id: str, user: User = Depends(get_current_user)):
    """Generate voice coaching for a game analysis summary"""
    import base64
    
    # Get the analysis
    analysis = await db.game_analyses.find_one(
        {"game_id": game_id, "user_id": user.user_id},
        {"_id": 0}
    )
    
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    
    # Check if we already have cached audio
    if analysis.get("voice_audio_base64"):
        return {
            "audio_base64": analysis["voice_audio_base64"],
            "format": "mp3",
            "voice": "onyx",
            "cached": True
        }
    
    # Build the voice script
    summary = analysis.get("overall_summary", "")
    key_lesson = analysis.get("key_lesson", "")
    
    # Create a natural speaking script
    voice_script = summary
    if key_lesson:
        voice_script += f" And here's the key lesson from this game: {key_lesson}"
    
    if not voice_script:
        raise HTTPException(status_code=400, detail="No summary available for voice generation")
    
    try:
        audio_bytes = await call_tts(text=voice_script[:4000], voice="onyx")
        audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
        
        # Cache the audio in the database
        await db.game_analyses.update_one(
            {"game_id": game_id},
            {"$set": {"voice_audio_base64": audio_base64}}
        )
        
        return {
            "audio_base64": audio_base64,
            "format": "mp3",
            "voice": "onyx",
            "cached": False
        }
        
    except Exception as e:
        logger.error(f"TTS analysis voice error: {e}")
        raise HTTPException(status_code=500, detail=f"Voice generation failed: {str(e)}")

class MoveVoiceRequest(BaseModel):
    game_id: str
    move_index: int

@api_router.post("/tts/move-explanation")
async def generate_move_voice(req: MoveVoiceRequest, user: User = Depends(get_current_user)):
    """Generate voice explanation for a specific move"""
    import base64
    
    analysis = await db.game_analyses.find_one(
        {"game_id": req.game_id, "user_id": user.user_id},
        {"_id": 0}
    )
    
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    
    commentary = analysis.get("commentary", [])
    if req.move_index < 0 or req.move_index >= len(commentary):
        raise HTTPException(status_code=400, detail="Invalid move index")
    
    move = commentary[req.move_index]
    
    # Build voice script for this move
    parts = []
    
    move_num = move.get("move_number", "")
    move_name = move.get("move", "")
    parts.append(f"Move {move_num}, {move_name}.")
    
    if move.get("player_intention"):
        parts.append(f"I see what you were going for: {move['player_intention']}")
    
    if move.get("coach_response"):
        parts.append(move["coach_response"])
    elif move.get("comment"):
        parts.append(move["comment"])
    
    if move.get("better_move"):
        parts.append(f"A better option was {move['better_move']}.")
    
    explanation = move.get("explanation", {})
    if explanation.get("one_repeatable_rule"):
        parts.append(f"Remember: {explanation['one_repeatable_rule']}")
    
    voice_script = " ".join(parts)
    
    if not voice_script:
        raise HTTPException(status_code=400, detail="No explanation available for this move")
    
    try:
        audio_bytes = await call_tts(text=voice_script[:4000], voice="onyx")
        audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
        
        return {
            "audio_base64": audio_base64,
            "format": "mp3",
            "voice": "onyx",
            "move_number": move_num
        }
        
    except Exception as e:
        logger.error(f"TTS move voice error: {e}")
        raise HTTPException(status_code=500, detail=f"Voice generation failed: {str(e)}")

# ==================== JOURNEY DASHBOARD ROUTES ====================

@api_router.get("/journey")
async def get_journey_dashboard(user: User = Depends(get_current_user)):
    """
    Get Journey Dashboard data - proves learning over time.
    
    This is the primary surface where coaching results appear.
    No manual analysis required - games are analyzed automatically.
    """
    # Get player profile
    profile = await db.player_profiles.find_one(
        {"user_id": user.user_id},
        {"_id": 0}
    )
    
    if not profile:
        # Create profile if doesn't exist
        profile = await get_or_create_profile(db, user.user_id, user.name)
    
    # Generate dashboard data
    dashboard = await generate_journey_dashboard_data(db, user.user_id, profile)
    
    return dashboard


@api_router.get("/journey/comprehensive")
async def get_comprehensive_journey(user: User = Depends(get_current_user)):
    """
    Get comprehensive chess journey data.
    
    Returns:
    - Rating progression over time
    - Phase mastery (Opening, Middlegame, Endgame)
    - Improvement metrics (then vs now)
    - Habit journey (conquered, in progress, needs attention)
    - Opening repertoire with win rates
    - Weekly summary and insights
    """
    journey = await get_chess_journey(db, user.user_id)
    return journey


@api_router.get("/journey/weekly-assessment")
async def get_weekly_assessment(user: User = Depends(get_current_user)):
    """Get coach's weekly assessment paragraph"""
    from journey_service import generate_weekly_assessment
    
    profile = await db.player_profiles.find_one(
        {"user_id": user.user_id},
        {"_id": 0}
    )
    
    if not profile:
        return {
            "assessment": "Link your Chess.com or Lichess account to start your coaching journey.",
            "games_analyzed": 0
        }
    
    recent_analyses = await db.game_analyses.find(
        {"user_id": user.user_id},
        {"_id": 0, "_cqs_internal": 0}
    ).sort("created_at", -1).limit(5).to_list(5)
    
    improvement_trend = profile.get("improvement_trend", "stuck")
    
    return {
        "assessment": generate_weekly_assessment(profile, recent_analyses, improvement_trend),
        "games_analyzed": profile.get("games_analyzed_count", 0),
        "improvement_trend": improvement_trend
    }

@api_router.get("/journey/weakness-trends")
async def get_weakness_trends(user: User = Depends(get_current_user)):
    """Get weakness trend data - shows if habits are improving"""
    from journey_service import calculate_weakness_trend
    
    profile = await db.player_profiles.find_one(
        {"user_id": user.user_id},
        {"_id": 0}
    )
    
    if not profile:
        return {"trends": [], "message": "Not enough data yet"}
    
    # Get recent analyses
    recent_analyses = await db.game_analyses.find(
        {"user_id": user.user_id},
        {"_id": 0, "weaknesses": 1, "identified_weaknesses": 1}
    ).sort("created_at", -1).limit(10).to_list(10)
    
    top_weaknesses = profile.get("top_weaknesses", [])[:5]
    recent_5 = recent_analyses[:5]
    previous_5 = recent_analyses[5:10]
    
    trends = []
    for w in top_weaknesses:
        weakness_key = f"{w.get('category', '')}:{w.get('subcategory', '')}"
        trend_data = calculate_weakness_trend(weakness_key, recent_5, previous_5)
        
        trends.append({
            "name": w.get("subcategory", "").replace("_", " "),
            "category": w.get("category", ""),
            **trend_data
        })
    
    return {"trends": trends}

class LinkAccountRequest(BaseModel):
    platform: str  # "chess.com" or "lichess"
    username: str

@api_router.post("/journey/link-account")
async def link_chess_account(req: LinkAccountRequest, user: User = Depends(get_current_user)):
    """
    Link Chess.com or Lichess account for automatic game tracking.
    This enables silent background analysis.
    """
    platform = req.platform.lower()
    username = req.username.strip()
    
    if platform not in ["chess.com", "lichess"]:
        raise HTTPException(status_code=400, detail="Invalid platform. Use 'chess.com' or 'lichess'")
    
    if not username:
        raise HTTPException(status_code=400, detail="Username is required")
    
    # Validate account exists
    if platform == "chess.com":
        games = await fetch_recent_chesscom_games(username)
        if not games and games != []:
            raise HTTPException(status_code=404, detail=f"Chess.com user '{username}' not found")
        update_field = "chesscom_username"
    else:
        games = await fetch_recent_lichess_games(username)
        update_field = "lichess_username"
    
    # Update user record
    await db.users.update_one(
        {"user_id": user.user_id},
        {"$set": {
            update_field: username,
            "last_game_sync": None  # Trigger initial sync
        }}
    )
    
    return {
        "message": "Account linked successfully! We'll import your games from the last 3 months and auto-analyze up to 3 games per day.",
        "platform": platform,
        "username": username,
        "import_info": {
            "period": "Last 3 months",
            "auto_analysis_limit": "3 games per day",
            "sync_frequency": "Every 4 hours"
        }
    }

@api_router.get("/journey/linked-accounts")
async def get_linked_accounts(user: User = Depends(get_current_user)):
    """Get user's linked chess accounts"""
    user_doc = await db.users.find_one(
        {"user_id": user.user_id},
        {"_id": 0, "chesscom_username": 1, "lichess_username": 1}
    )
    
    if not user_doc:
        return {"chess_com": None, "lichess": None}
    
    return {
        "chess_com": user_doc.get("chesscom_username"),
        "lichess": user_doc.get("lichess_username")
    }

@api_router.post("/journey/sync-now")
async def trigger_game_sync(background_tasks: BackgroundTasks, user: User = Depends(get_current_user)):
    """
    Manually trigger game sync for the current user.
    Runs the sync immediately in the background.
    """
    from journey_service import sync_user_games
    
    user_doc = await db.users.find_one(
        {"user_id": user.user_id},
        {"_id": 0}
    )
    
    if not user_doc:
        raise HTTPException(status_code=404, detail="User not found")
    
    has_linked = user_doc.get("chesscom_username") or user_doc.get("lichess_username")
    if not has_linked:
        raise HTTPException(status_code=400, detail="No chess accounts linked. Link an account first.")
    
    # Run sync in background
    async def do_sync():
        try:
            count = await sync_user_games(db, user.user_id, user_doc)
            logger.info(f"Manual sync for user {user.user_id}: {count} games synced")
        except Exception as e:
            logger.error(f"Manual sync error for {user.user_id}: {e}")
    
    background_tasks.add_task(do_sync)
    
    return {"message": "Game sync started. New games will appear shortly."}

# ==================== COACH MODE ROUTES ====================

@api_router.post("/coach/start-session")
async def start_coach_session(
    data: dict,
    user: User = Depends(get_current_user)
):
    """Start a play session - user is going to play"""
    from coach_session_service import start_play_session
    platform = data.get("platform", "chess.com")
    result = await start_play_session(db, user.user_id, platform)
    return result


@api_router.post("/coach/end-session")
async def end_coach_session(user: User = Depends(get_current_user)):
    """End play session - user finished playing, find and analyze their game"""
    from coach_session_service import end_play_session
    result = await end_play_session(db, user.user_id)
    return result


@api_router.get("/coach/analysis-status/{game_id}")
async def get_analysis_status(game_id: str, user: User = Depends(get_current_user)):
    """Poll for analysis completion and get real feedback"""
    from coach_session_service import _build_game_feedback
    
    # Check if analysis exists
    analysis = await db.game_analyses.find_one(
        {"game_id": game_id, "user_id": user.user_id},
        {"_id": 0, "blunders": 1, "mistakes": 1, "best_moves": 1, "identified_weaknesses": 1}
    )
    
    if not analysis:
        # Check queue status
        queue_item = await db.analysis_queue.find_one(
            {"game_id": game_id},
            {"_id": 0, "status": 1}
        )
        if queue_item and queue_item.get("status") == "failed":
            return {"status": "failed", "message": "Analysis failed. Try importing again."}
        return {"status": "pending", "message": "Still analyzing..."}
    
    # Get game details
    game = await db.games.find_one(
        {"game_id": game_id},
        {"_id": 0, "opponent": 1, "result": 1}
    )
    
    # Get dominant habit
    profile = await db.player_profiles.find_one(
        {"user_id": user.user_id},
        {"_id": 0, "top_weaknesses": 1}
    )
    dominant_habit = None
    if profile and profile.get("top_weaknesses"):
        w = profile["top_weaknesses"][0]
        dominant_habit = w.get("subcategory", str(w)) if isinstance(w, dict) else str(w)
    
    feedback = _build_game_feedback(analysis, dominant_habit, game or {})
    
    return {
        "status": "complete",
        "feedback": feedback
    }


@api_router.get("/coach/session-status")
async def get_coach_session_status(user: User = Depends(get_current_user)):
    """Get current session status"""
    from coach_session_service import get_session_status
    return await get_session_status(db, user.user_id)


class ReflectionResult(BaseModel):
    """Track PDR reflection results"""
    game_id: str
    move_number: int
    move_correct: bool
    reason_correct: Optional[bool] = None
    user_move: str
    best_move: str


@api_router.post("/coach/track-reflection")
async def track_reflection(result: ReflectionResult, user: User = Depends(get_current_user)):
    """Track PDR reflection results for stats"""
    reflection_doc = {
        "user_id": user.user_id,
        "game_id": result.game_id,
        "move_number": result.move_number,
        "move_correct": result.move_correct,
        "reason_correct": result.reason_correct,
        "user_move": result.user_move,
        "best_move": result.best_move,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.reflection_results.insert_one(reflection_doc)
    
    # Update user's reflection stats
    await db.users.update_one(
        {"user_id": user.user_id},
        {
            "$inc": {
                "total_reflections": 1,
                "correct_reflections": 1 if result.move_correct else 0
            }
        }
    )
    
    # Check for habit rotation after tracking
    from habit_rotation_service import update_habit_after_reflection
    rotation_result = await update_habit_after_reflection(db, user.user_id, result.game_id, result.move_correct)
    
    response = {"status": "tracked"}
    if rotation_result and rotation_result.get("rotated"):
        response["habit_rotated"] = True
        response["rotation_info"] = rotation_result
    
    return response


@api_router.get("/coach/habits")
async def get_habit_statuses(user: User = Depends(get_current_user)):
    """Get all habit statuses for the user."""
    from habit_rotation_service import get_all_habit_statuses
    statuses = await get_all_habit_statuses(db, user.user_id)
    return {"habits": statuses}


@api_router.post("/coach/check-habit-rotation")
async def check_habit_rotation(user: User = Depends(get_current_user)):
    """Manually check if habit should be rotated."""
    from habit_rotation_service import check_and_rotate_habit
    result = await check_and_rotate_habit(db, user.user_id)
    return result


@api_router.get("/user/weekly-summary")
async def get_weekly_summary(user: User = Depends(get_current_user)):
    """Get user's weekly summary data."""
    from weekly_summary_service import generate_weekly_summary_data
    summary = await generate_weekly_summary_data(db, user.user_id)
    return summary


@api_router.post("/user/send-weekly-summary")
async def send_weekly_summary_to_user(user: User = Depends(get_current_user)):
    """Send weekly summary email to current user."""
    from weekly_summary_service import send_single_weekly_summary
    result = await send_single_weekly_summary(db, user.user_id)
    return result


@api_router.post("/admin/send-all-weekly-summaries")
async def send_all_weekly_summaries(user: User = Depends(get_current_user)):
    """Admin endpoint to trigger weekly summaries for all users."""
    # Simple admin check - in production, use proper admin auth
    from weekly_summary_service import send_weekly_summaries
    result = await send_weekly_summaries(db)
    return result


@api_router.get("/coach/today")
async def get_coach_today(user: User = Depends(get_current_user)):
    """
    Get today's coaching focus - structured as:
    0. Reflection Moment (critical position from recent game)
    1. Correct This (ONE dominant habit)
    2. Keep Doing This (ONE strength/improvement)
    3. Remember This Rule (carry-forward principle)
    """
    import sys
    print(f"[COACH] API called for user {user.user_id}", file=sys.stderr)
    
    # Get player profile first - this is the source of truth
    profile = await db.player_profiles.find_one(
        {"user_id": user.user_id},
        {"_id": 0}
    )
    
    # Check if we have any analyses
    analysis_count = await db.game_analyses.count_documents({"user_id": user.user_id})
    
    # If no profile and no analyses, prompt to link account
    if not profile and analysis_count == 0:
        user_doc = await db.users.find_one({"user_id": user.user_id}, {"_id": 0})
        has_account = bool(user_doc.get("chess_com_username") or user_doc.get("lichess_username"))
        
        if not has_account:
            return {
                "has_data": False,
                "message": "Link your chess account to get started"
            }
        return {
            "has_data": False,
            "message": "Analyzing your games..."
        }
    
    # Get recent analyses for context
    recent_analyses = await db.game_analyses.find(
        {"user_id": user.user_id},
        {"_id": 0, "game_id": 1, "blunders": 1, "mistakes": 1, "accuracy": 1, "created_at": 1, 
         "identified_weaknesses": 1, "strengths": 1, "weaknesses": 1}
    ).sort("created_at", -1).limit(10).to_list(10)
    
    # Get top weakness as the correction
    top_weaknesses = profile.get("top_weaknesses", []) if profile else []
    
    # ===== SECTION 1: CORRECT THIS =====
    correction = None
    if top_weaknesses:
        top = top_weaknesses[0]
        subcategory = top.get("subcategory", "").replace("_", " ").title()
        occurrences = top.get("occurrence_count", 0)
        
        # Calculate recent frequency
        recent_count = 0
        total_recent = min(5, len(recent_analyses))
        for analysis in recent_analyses[:5]:
            weaknesses = analysis.get("identified_weaknesses", []) or analysis.get("weaknesses", [])
            if isinstance(weaknesses, list):
                for w in weaknesses:
                    if isinstance(w, dict):
                        if top.get("subcategory", "").lower() in str(w.get("subcategory", "")).lower():
                            recent_count += 1
                            break
                    elif isinstance(w, str) and top.get("subcategory", "").lower() in w.lower():
                        recent_count += 1
                        break
        
        # Build context message
        if recent_count > 0 and total_recent > 0:
            context = f"This appeared in {recent_count} of your last {total_recent} games."
        else:
            context = f"This has occurred {occurrences} times in your recent games."
        
        correction = {
            "title": subcategory,
            "context": context,
            "severity": "This remains your biggest rating leak." if occurrences > 5 else "Focus here to see improvement."
        }
    
    # ===== SECTION 2: KEEP DOING THIS (Reinforcement) =====
    reinforcement = None
    
    # Check for strengths in profile
    strengths = profile.get("strengths", []) if profile else []
    improving_areas = profile.get("improving_areas", []) if profile else []
    
    # Look for genuine improvement or strength
    if improving_areas:
        area = improving_areas[0]
        reinforcement = {
            "title": area.get("name", "Positional Play").replace("_", " ").title(),
            "context": "Recent games show improvement here.",
            "trend": "Earlier this was unstable — now improving."
        }
    elif strengths:
        strength = strengths[0] if isinstance(strengths[0], dict) else {"name": strengths[0]}
        reinforcement = {
            "title": strength.get("name", "Solid Play").replace("_", " ").title(),
            "context": "You've maintained consistency in this area.",
            "trend": "Keep this discipline."
        }
    else:
        # Check recent analyses for any positive signals
        # Use stockfish_analysis.move_evaluations for accurate counts
        def get_blunders(a):
            sf = a.get("stockfish_analysis", {})
            evals = sf.get("move_evaluations", [])
            return sum(1 for m in evals if m.get("evaluation") == "blunder")
        
        recent_blunders = [get_blunders(a) for a in recent_analyses[:3]]
        if recent_blunders and sum(recent_blunders) == 0:
            reinforcement = {
                "title": "Clean Calculation",
                "context": "Your last few games had no major blunders.",
                "trend": "This focus is paying off."
            }
        elif len(recent_analyses) >= 2:
            # Default neutral reinforcement
            reinforcement = {
                "title": "Steady Progress",
                "context": "You maintained discipline this week.",
                "trend": "Consistency builds long-term strength."
            }
    
    # ===== SECTION 3: REMEMBER THIS RULE =====
    habit_rules = {
        "one_move_blunders": "Before every move, ask:\n\"What can my opponent capture if I play this?\"",
        "one_move_blunder": "Before every move, ask:\n\"What can my opponent capture if I play this?\"",
        "premature_queen_moves": "Develop knights and bishops before your queen.\nEarly queen moves invite attacks.",
        "time_trouble": "Use at least 10 seconds on each move.\nSpeed without thought is wasted calculation.",
        "missed_tactics": "On every opponent move, check for loose pieces first.\nTactics hide in plain sight.",
        "weak_endgame": "In king and pawn endings, activate your king immediately.\nThe king is a fighting piece in endgames.",
        "opening_mistakes": "Control the center with pawns.\nDevelop pieces toward the center.",
        "piece_activity": "If a piece hasn't moved, find a square for it.\nPassive pieces lose games.",
        "king_safety": "Castle early unless you have a specific reason not to.\nAn exposed king invites disaster.",
        "exposing_own_king": "Before moving, check if it weakens your king's protection.\nKing safety is non-negotiable.",
        "pawn_structure": "Avoid doubled pawns unless you get clear compensation.\nPawn structure shapes the entire game.",
        "calculation_errors": "Calculate forcing moves first: checks, captures, threats.\nForcing moves narrow the possibilities.",
    }
    
    rule = None
    if top_weaknesses:
        subcategory_key = top_weaknesses[0].get("subcategory", "").lower().replace(" ", "_")
        rule = habit_rules.get(subcategory_key)
    
    if not rule:
        rule = "Before every move, pause and ask:\n\"Is this move safe? What is my opponent's threat?\""
    
    # ===== COACH'S NOTE (2 lines max, emotional framing) =====
    coach_note = None
    if top_weaknesses:
        habit_name = top_weaknesses[0].get("subcategory", "").replace("_", " ").lower()
        occurrences = top_weaknesses[0].get("occurrence_count", 0)
        
        if occurrences > 10:
            coach_note = {
                "line1": "Your positions are generally fine.",
                "line2": f"Games are slipping due to {habit_name}. One fix, big improvement."
            }
        elif occurrences > 5:
            coach_note = {
                "line1": "You're playing solid chess.",
                "line2": f"Focus on eliminating {habit_name} and you'll see results."
            }
        else:
            coach_note = {
                "line1": "Good progress this week.",
                "line2": "Keep the discipline. Small improvements compound."
            }
    else:
        coach_note = {
            "line1": "Let's build a strong foundation.",
            "line2": "Play mindfully. I'll help identify what to work on."
        }
    
    # ===== LIGHT STATS (2-3 stats with trends) =====
    light_stats = []
    
    # Helper to count blunders from Stockfish data
    def count_blunders_sf(a):
        sf = a.get("stockfish_analysis", {})
        evals = sf.get("move_evaluations", [])
        return sum(1 for m in evals if m.get("evaluation") == "blunder")
    
    # Blunders per game trend
    recent_10 = recent_analyses[:10] if recent_analyses else []
    older_10 = recent_analyses[10:20] if len(recent_analyses) > 10 else []
    
    if recent_10:
        recent_blunders = sum(count_blunders_sf(a) for a in recent_10) / len(recent_10)
        if older_10:
            older_blunders = sum(count_blunders_sf(a) for a in older_10) / len(older_10)
            trend = "down" if recent_blunders < older_blunders else ("up" if recent_blunders > older_blunders else "stable")
            light_stats.append({
                "label": "Blunders / game",
                "value": f"{older_blunders:.1f} → {recent_blunders:.1f}",
                "trend": trend
            })
        else:
            light_stats.append({
                "label": "Blunders / game",
                "value": f"{recent_blunders:.1f}",
                "trend": "stable"
            })
    
    # NOTE: Rating intentionally NOT shown in Coach mode (Option C)
    # Rating is available on Progress page only - keeps Coach mode discipline-focused
    
    # Reflection success rate
    user_doc = await db.users.find_one({"user_id": user.user_id}, {"_id": 0})
    total_reflections = user_doc.get("total_reflections", 0) if user_doc else 0
    correct_reflections = user_doc.get("correct_reflections", 0) if user_doc else 0
    
    if total_reflections >= 3:
        success_rate = correct_reflections / total_reflections
        trend = "up" if success_rate >= 0.6 else ("down" if success_rate < 0.4 else "stable")
        light_stats.append({
            "label": "Reflection success",
            "value": f"{correct_reflections}/{total_reflections}",
            "trend": trend
        })
    
    # ===== NEXT GAME PLAN (1-2 lines) =====
    next_game_plan = None
    if top_weaknesses:
        habit = top_weaknesses[0].get("subcategory", "").lower()
        
        plans = {
            "one_move_blunders": "Before each move, pause and ask: What can my opponent do if I play this?",
            "premature_queen_moves": "First 10 moves: develop knights and bishops before the queen.",
            "time_trouble": "After move 15, use at least 10 seconds per move. No rushing.",
            "missed_tactics": "Each opponent move, check: Are any of my pieces loose?",
            "weak_endgame": "When queens come off, activate your king immediately.",
            "opening_mistakes": "Focus on controlling the center. e4/d4 pawns, then develop pieces.",
            "exposing_own_king": "Before making a move, check if it weakens your king's safety.",
        }
        
        next_game_plan = plans.get(habit, "Play slowly. Check opponent's threats before each move.")
    else:
        next_game_plan = "Focus on one thing: pause before each move and ask what your opponent wants."
    
    # ===== SESSION STATUS =====
    from coach_session_service import get_session_status
    session_status = await get_session_status(db, user.user_id)
    
    # ===== LAST GAME SUMMARY =====
    # CRITICAL: Only show games with REAL Stockfish analysis
    # See /app/backend/DATA_MODEL.md for schema details
    #
    # DATA MODEL:
    # - stockfish_analysis.move_evaluations: Array of Stockfish evals (SOURCE OF TRUTH)
    # - stockfish_analysis.accuracy: Real accuracy from Stockfish
    # - commentary: GPT text only, NOT source of truth for stats
    # - Top-level blunders/mistakes: MAY BE STALE, don't use
    #
    # A game is PROPERLY analyzed if:
    # 1. stockfish_analysis.move_evaluations exists AND has >= 3 items
    # 2. stockfish_failed is NOT True
    last_game = None
    
    recent_analyses = await db.game_analyses.find(
        {
            "user_id": user.user_id,
            "stockfish_failed": {"$ne": True},
            # CRITICAL: Must check nested path, NOT top-level
            "stockfish_analysis.move_evaluations": {"$exists": True, "$not": {"$size": 0}}
        },
        {"_id": 0, "game_id": 1, "blunders": 1, "mistakes": 1, "accuracy": 1, 
         "commentary": 1, "identified_weaknesses": 1, "stockfish_analysis": 1}
    ).sort("created_at", -1).limit(5).to_list(5)
    
    # Find the first one that has actual analysis data
    last_analysis = None
    most_recent_game = None
    
    for analysis in recent_analyses:
        # Verify it has real Stockfish data
        sf_data = analysis.get("stockfish_analysis", {})
        move_evals = sf_data.get("move_evaluations", [])
        if len(move_evals) >= 3:  # At least 3 moves evaluated by Stockfish
            # Get the corresponding game
            game = await db.games.find_one(
                {"game_id": analysis.get("game_id"), "user_id": user.user_id},
                {"_id": 0, "game_id": 1, "result": 1, "user_color": 1, "time_control": 1, 
                 "platform": 1, "url": 1, "pgn": 1, "termination": 1}
            )
            if game:
                most_recent_game = game
                last_analysis = analysis
                break
    
    if most_recent_game and last_analysis:
            # CRITICAL: Get stats from stockfish_analysis, NOT top-level fields
            # See /app/backend/DATA_MODEL.md
            sf_data = last_analysis.get("stockfish_analysis", {})
            move_evals = sf_data.get("move_evaluations", [])
            
            # Count from Stockfish move_evaluations (SOURCE OF TRUTH)
            blunders = sum(1 for m in move_evals if m.get("evaluation") == "blunder")
            mistakes = sum(1 for m in move_evals if m.get("evaluation") == "mistake")
            accuracy = sf_data.get("accuracy", 0) or 0
            
            # Get opponent name from PGN
            user_color = most_recent_game.get("user_color", "white")
            opponent = "Opponent"
            
            if most_recent_game.get("pgn"):
                import re
                pgn = most_recent_game["pgn"]
                white_match = re.search(r'\[White "([^"]+)"\]', pgn)
                black_match = re.search(r'\[Black "([^"]+)"\]', pgn)
                if white_match and black_match:
                    if user_color == "white":
                        opponent = black_match.group(1)
                    else:
                        opponent = white_match.group(1)
            
            # Determine win/loss from user's perspective
            result = most_recent_game.get("result", "")
            if user_color == "white":
                won = result == "1-0"
                lost = result == "0-1"
            else:
                won = result == "0-1"
                lost = result == "1-0"
            draw = "1/2" in result
            
            # Check if repeated habit
            repeated_habit = False
            habit_name = top_weaknesses[0].get("subcategory", "") if top_weaknesses else ""
            weaknesses = last_analysis.get("identified_weaknesses", [])
            if habit_name and weaknesses:
                for w in weaknesses:
                    w_name = w.get("subcategory", str(w)) if isinstance(w, dict) else str(w)
                    if habit_name.lower() in w_name.lower():
                        repeated_habit = True
                        break
            
            # Get termination reason
            termination = most_recent_game.get("termination", "")
            
            # Generate human-readable termination text
            termination_text = ""
            if termination == "timeout":
                termination_text = "lost on time" if lost else "opponent timed out"
            elif termination == "resigned":
                termination_text = "resigned" if lost else "opponent resigned"
            elif termination == "checkmated":
                termination_text = "checkmated" if lost else "checkmate"
            elif termination == "won":
                termination_text = ""
            elif termination == "stalemate":
                termination_text = "stalemate"
            
            # Generate coach comment based on actual game outcome
            if blunders == 0:
                if won:
                    comment = "Clean win! No blunders. This is the discipline we want."
                elif lost:
                    if termination == "timeout":
                        comment = "You lost on time but played clean — no blunders. Time management is the issue here."
                    elif termination == "resigned":
                        comment = "You resigned but had no blunders. Was there a tactical shot you missed?"
                    else:
                        comment = "You lost but played clean — no blunders. Sometimes chess is like that."
                else:
                    comment = "Solid draw, no blunders. Good focus."
            elif blunders == 1:
                if repeated_habit:
                    comment = f"One blunder — same pattern: {habit_name.replace('_', ' ')}. Let's fix this."
                else:
                    comment = "One slip-up. Let's see what happened."
            else:
                if repeated_habit:
                    comment = f"{blunders} blunders, including your old pattern. We need to work on this."
                else:
                    comment = f"{blunders} blunders. Rough game — let's review."
            
            last_game = {
                "opponent": opponent,
                "result": "Won" if won else ("Lost" if lost else "Draw"),
                "termination": termination_text,
                "time_control": most_recent_game.get("time_control"),
                "stats": {
                    "blunders": blunders,
                    "mistakes": mistakes,
                    "accuracy": accuracy
                },
                "comment": comment,
                "repeated_habit": repeated_habit,
                "game_id": most_recent_game.get("game_id"),
                "external_url": most_recent_game.get("url"),
                "has_full_analysis": True
            }
    
    # ===== OPENING DISCIPLINE (Play This Today / Rating Leak / Wisdom) =====
    opening_discipline = None
    
    try:
        # Get all analyzed games with opening data
        games_with_openings = await db.games.find(
            {"user_id": user.user_id, "is_analyzed": True},
            {"_id": 0, "game_id": 1, "user_color": 1, "result": 1, "pgn": 1}
        ).to_list(100)
        
        if games_with_openings and len(games_with_openings) >= 3:
            import re
            from collections import defaultdict
            
            # Load ECO openings for name lookup
            eco_openings = {}
            try:
                import json
                with open("data/eco_openings.json", "r") as f:
                    eco_openings = json.load(f)
            except Exception:
                pass
            
            # Track opening stats by color
            white_openings = defaultdict(lambda: {"wins": 0, "losses": 0, "draws": 0, "total": 0})
            black_openings = defaultdict(lambda: {"wins": 0, "losses": 0, "draws": 0, "total": 0})
            
            for game in games_with_openings:
                pgn = game.get("pgn", "")
                user_color = game.get("user_color", "white")
                result = game.get("result", "")
                
                # Extract opening from ECO code
                eco_match = re.search(r'\[ECO "([^"]+)"\]', pgn)
                opening_match = re.search(r'\[Opening "([^"]+)"\]', pgn)
                
                opening_name = "Unknown Opening"
                if opening_match:
                    opening_name = opening_match.group(1)
                elif eco_match:
                    eco = eco_match.group(1)
                    opening_name = eco_openings.get(eco, eco)
                
                # Simplify opening name (remove variations)
                opening_name = opening_name.split(":")[0].split(",")[0].strip()
                
                # Skip unknown openings
                if opening_name == "Unknown Opening":
                    continue
                
                # Determine win/loss/draw
                if user_color == "white":
                    won = result == "1-0"
                    lost = result == "0-1"
                else:
                    won = result == "0-1"
                    lost = result == "1-0"
                draw = "1/2" in result
                
                # Track stats
                if user_color == "white":
                    stats = white_openings[opening_name]
                else:
                    stats = black_openings[opening_name]
                stats["total"] += 1
                if won:
                    stats["wins"] += 1
                elif lost:
                    stats["losses"] += 1
                else:
                    stats["draws"] += 1
            
            # Calculate win rates and find best/worst
            def calc_win_rate(stats):
                if stats["total"] == 0:
                    return 0
                return round((stats["wins"] / stats["total"]) * 100)
            
            # Best opening as White (min 3 games)
            best_white = None
            best_white_rate = 0
            for opening, stats in white_openings.items():
                if stats["total"] >= 3:
                    rate = calc_win_rate(stats)
                    if rate > best_white_rate:
                        best_white_rate = rate
                        best_white = {"name": opening, "win_rate": rate, "games": stats["total"], "wins": stats["wins"]}
            
            # Best opening as Black (min 3 games)
            best_black = None
            best_black_rate = 0
            for opening, stats in black_openings.items():
                if stats["total"] >= 3:
                    rate = calc_win_rate(stats)
                    if rate > best_black_rate:
                        best_black_rate = rate
                        best_black = {"name": opening, "win_rate": rate, "games": stats["total"], "wins": stats["wins"]}
            
            # Worst openings (rating leaks) - min 3 games, <40% win rate
            rating_leaks = []
            all_openings = {}
            for opening, stats in white_openings.items():
                all_openings[f"white_{opening}"] = {"opening": opening, "color": "white", "stats": stats}
            for opening, stats in black_openings.items():
                all_openings[f"black_{opening}"] = {"opening": opening, "color": "black", "stats": stats}
            
            for key, data in all_openings.items():
                stats = data["stats"]
                if stats["total"] >= 3:
                    rate = calc_win_rate(stats)
                    if rate < 40:
                        rating_leaks.append({
                            "name": data["opening"],
                            "color": data["color"],
                            "win_rate": rate,
                            "games": stats["total"],
                            "wins": stats["wins"]
                        })
            rating_leaks.sort(key=lambda x: x["win_rate"])
            
            # Opening wisdom - coaching tips for best openings
            opening_wisdom = []
            
            # Tips based on opening names
            opening_tips = {
                "Italian": {
                    "tip": "Castle early, then prepare d4 push. Build pressure before attacking.",
                    "key_idea": "Control the center with pieces, not just pawns."
                },
                "Sicilian": {
                    "tip": "As Black, counterattack on the queenside. Don't be passive.",
                    "key_idea": "Pawn breaks with ...b5 or ...d5 are your weapons."
                },
                "Queen's Gambit": {
                    "tip": "Control d5. If Black captures, recapture with the knight or bishop.",
                    "key_idea": "Space advantage in the center leads to attacking chances."
                },
                "London": {
                    "tip": "Develop bishop to f4 before playing e3. Keep flexibility.",
                    "key_idea": "Solid structure, but don't be too passive."
                },
                "Caro-Kann": {
                    "tip": "Your light-squared bishop is your strength. Don't trade it easily.",
                    "key_idea": "Solid pawn structure compensates for slightly less space."
                },
                "French": {
                    "tip": "Break with ...c5 early. Your c8 bishop is the problem piece.",
                    "key_idea": "The pawn chain defines the game. Attack its base."
                },
                "King's Indian": {
                    "tip": "Kingside attack with ...f5 is your main plan. Don't delay.",
                    "key_idea": "Let White have the center, then undermine it."
                },
                "Ruy Lopez": {
                    "tip": "The bishop on b5 is not attacking a6. It's preparing for long-term pressure.",
                    "key_idea": "Patience. This opening rewards slow maneuvering."
                },
                "Scandinavian": {
                    "tip": "After ...Qd8 or ...Qa5, develop quickly. Don't move the queen again.",
                    "key_idea": "Early queen move costs time. Make up for it with rapid development."
                },
                "Pirc": {
                    "tip": "Let White build a big center, then strike with ...c5 or ...e5.",
                    "key_idea": "Hypermodern approach - control from the flanks."
                },
                "Scotch": {
                    "tip": "Open game means tactics. Calculate before every move.",
                    "key_idea": "Development speed is everything in open positions."
                },
                "English": {
                    "tip": "Flexible system. Control c4 and prepare to strike in the center.",
                    "key_idea": "Delay committing your pawns. Keep options open."
                },
                "Dutch": {
                    "tip": "The f5 pawn is your attacking spearhead. Protect it.",
                    "key_idea": "Kingside attack, but watch for Bg5 pins."
                }
            }
            
            # Add wisdom for best openings
            if best_white:
                for pattern, tips in opening_tips.items():
                    if pattern.lower() in best_white["name"].lower():
                        opening_wisdom.append({
                            "opening": best_white["name"],
                            "color": "white",
                            "tip": tips["tip"],
                            "key_idea": tips["key_idea"]
                        })
                        break
                else:
                    opening_wisdom.append({
                        "opening": best_white["name"],
                        "color": "white",
                        "tip": "Control the center. Develop pieces toward active squares.",
                        "key_idea": "Opening principles matter more than memorization."
                    })
            
            if best_black:
                for pattern, tips in opening_tips.items():
                    if pattern.lower() in best_black["name"].lower():
                        opening_wisdom.append({
                            "opening": best_black["name"],
                            "color": "black",
                            "tip": tips["tip"],
                            "key_idea": tips["key_idea"]
                        })
                        break
                else:
                    opening_wisdom.append({
                        "opening": best_black["name"],
                        "color": "black",
                        "tip": "Equalize first. Look for counterplay once you're developed.",
                        "key_idea": "Don't rush. Solid play leads to opportunities."
                    })
            
            opening_discipline = {
                "has_data": True,
                "play_this_today": {
                    "white": best_white,
                    "black": best_black,
                    "message": "Stay with what works. Master one opening before learning another."
                },
                "rating_leaks": rating_leaks[:2] if rating_leaks else [],
                "leak_message": "Avoid these until your middlegame habits are fixed." if rating_leaks else None,
                "wisdom": opening_wisdom[:2] if opening_wisdom else [],
                "total_openings_analyzed": len(white_openings) + len(black_openings)
            }
    except Exception as e:
        import traceback
        print(f"[COACH] Opening discipline error: {e}", file=sys.stderr)
        traceback.print_exc()
        opening_discipline = None
    
    return {
        "has_data": True,
        "coach_note": coach_note,
        "light_stats": light_stats,
        "next_game_plan": next_game_plan,
        "session_status": session_status,
        "last_game": last_game,
        "rule": rule,
        "opening_discipline": opening_discipline
    }


# ==================== MISTAKE MASTERY SYSTEM ROUTES ====================

@api_router.get("/training/session")
async def get_training_session_endpoint(user: User = Depends(get_current_user)):
    """
    Get the current training session.
    Returns either:
    - Post-Game Debrief (if user just played a game)
    - Daily Training (cards due for review)
    - All Caught Up (no cards due)
    """
    session = await get_training_session(db, user.user_id)
    return session


@api_router.get("/training/due-cards")
async def get_due_cards_endpoint(user: User = Depends(get_current_user), limit: int = 5):
    """Get cards due for review today."""
    cards = await get_due_cards(db, user.user_id, limit=limit)
    return {"cards": cards, "count": len(cards)}


@api_router.get("/training/card/{card_id}")
async def get_training_card(card_id: str, user: User = Depends(get_current_user)):
    """Get a specific training card."""
    card = await get_card_by_id(db, card_id, user.user_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    return card


class CardAttemptRequest(BaseModel):
    card_id: str
    correct: bool


@api_router.post("/training/attempt")
async def record_training_attempt(req: CardAttemptRequest, user: User = Depends(get_current_user)):
    """
    Record an attempt on a training card.
    Updates spaced repetition schedule based on correctness.
    """
    result = await record_card_attempt(db, req.card_id, user.user_id, req.correct)
    if result.get("error"):
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@api_router.get("/training/card/{card_id}/why")
async def get_why_question_for_card(card_id: str, user: User = Depends(get_current_user)):
    """
    Get a Socratic "Why is this move better?" question for a card.
    Used after the user answers correctly to deepen understanding.
    """
    card = await get_card_by_id(db, card_id, user.user_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    
    why_data = await generate_why_question(db, card)
    return why_data


@api_router.get("/training/progress")
async def get_training_progress(user: User = Depends(get_current_user)):
    """Get user's habit mastery progress."""
    progress = await get_user_habit_progress(db, user.user_id)
    stats = await get_training_stats(db, user.user_id)
    return {
        "habits": progress,
        "stats": stats
    }


class SetActiveHabitRequest(BaseModel):
    habit_key: str


@api_router.post("/training/set-habit")
async def set_training_habit(req: SetActiveHabitRequest, user: User = Depends(get_current_user)):
    """Manually set the active habit to focus on."""
    result = await set_active_habit(db, user.user_id, req.habit_key)
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@api_router.get("/training/habits")
async def get_available_habits(user: User = Depends(get_current_user)):
    """Get all available habit definitions."""
    return {"habits": HABIT_DEFINITIONS}


@api_router.get("/progress")
async def get_progress_metrics(user: User = Depends(get_current_user)):
    """
    Get progress metrics for the /progress page.
    Shows rating, accuracy, blunders, and habit trends.
    """
    user_doc = await db.users.find_one({"user_id": user.user_id}, {"_id": 0})
    
    # Fetch rating data
    rating_data = {"current": None, "change": 0, "peak": None, "habit_correlation": None}
    
    # Check both field naming conventions
    chess_com_user = user_doc.get("chesscom_username") or user_doc.get("chess_com_username")
    lichess_user = user_doc.get("lichess_username")
    
    if chess_com_user or lichess_user:
        try:
            ratings = await fetch_platform_ratings(chess_com_user, lichess_user)
            if ratings:
                # Get rating from chess_com or lichess
                platform_data = ratings.get("chess_com") or ratings.get("lichess") or {}
                for category in ["rapid", "blitz", "bullet"]:
                    rating_val = platform_data.get(category)
                    if rating_val:
                        rating_data["current"] = rating_val
                        rating_data["peak"] = rating_val  # We don't have historical peak easily
                        break
        except Exception as e:
            logger.warning(f"Failed to fetch ratings: {e}")
    
    # Get recent analyses for accuracy and blunders
    recent_analyses = await db.game_analyses.find(
        {"user_id": user.user_id},
        {"_id": 0, "accuracy": 1, "blunders": 1, "mistakes": 1, "created_at": 1, 
         "stockfish_failed": 1, "stockfish_analysis": 1}
    ).sort("created_at", -1).limit(20).to_list(20)
    
    # Filter out analyses where Stockfish failed - only use accurate data
    valid_analyses = [a for a in recent_analyses if not a.get("stockfish_failed", False)]
    
    # Calculate accuracy trend (only from valid Stockfish analyses)
    accuracy_data = {"current": None, "previous": None, "trend": "stable"}
    if valid_analyses:
        # Get accuracy from stockfish_analysis if available, else top-level
        def get_accuracy(a):
            sf = a.get("stockfish_analysis", {})
            if sf and sf.get("accuracy"):
                return sf.get("accuracy")
            return a.get("accuracy", 0)
        
        recent_10 = [get_accuracy(a) for a in valid_analyses[:10] if get_accuracy(a) > 0]
        previous_10 = [get_accuracy(a) for a in valid_analyses[10:20] if get_accuracy(a) > 0]
        
        if recent_10:
            accuracy_data["current"] = round(sum(recent_10) / len(recent_10), 1)
        if previous_10:
            accuracy_data["previous"] = round(sum(previous_10) / len(previous_10), 1)
        
        if accuracy_data["current"] and accuracy_data["previous"]:
            diff = accuracy_data["current"] - accuracy_data["previous"]
            if diff > 2:
                accuracy_data["trend"] = "improving"
            elif diff < -2:
                accuracy_data["trend"] = "worsening"
    
    # Helper to count blunders from Stockfish data
    def get_blunders_count(a):
        sf = a.get("stockfish_analysis", {})
        evals = sf.get("move_evaluations", [])
        return sum(1 for m in evals if m.get("evaluation") == "blunder")
    
    # Calculate blunder trend (only from valid Stockfish analyses)
    blunders_data = {"avg_per_game": None, "total": 0, "trend": "stable"}
    if valid_analyses:
        recent_blunders = [get_blunders_count(a) for a in valid_analyses[:10]]
        previous_blunders = [get_blunders_count(a) for a in valid_analyses[10:20]]
        
        if recent_blunders:
            blunders_data["total"] = sum(recent_blunders)
            blunders_data["avg_per_game"] = round(sum(recent_blunders) / len(recent_blunders), 1)
        
        if recent_blunders and previous_blunders:
            recent_avg = sum(recent_blunders) / len(recent_blunders)
            prev_avg = sum(previous_blunders) / len(previous_blunders)
            if recent_avg < prev_avg - 0.3:
                blunders_data["trend"] = "improving"
            elif recent_avg > prev_avg + 0.3:
                blunders_data["trend"] = "worsening"
    
    # Track how many valid vs failed analyses
    valid_count = len(valid_analyses)
    failed_count = len(recent_analyses) - valid_count
    
    # Get habits from profile
    profile = await db.player_profiles.find_one(
        {"user_id": user.user_id},
        {"_id": 0}
    )
    
    habits = []
    resolved_habits = []
    
    if profile:
        top_weaknesses = profile.get("top_weaknesses", [])
        for i, w in enumerate(top_weaknesses[:5]):
            habits.append({
                "name": w.get("subcategory", "").replace("_", " ").title(),
                "category": w.get("category", ""),
                "occurrences_recent": w.get("occurrences", 0),
                "trend": "stable",  # Could calculate from history
                "is_active": i == 0  # Only first one is active
            })
        
        # Get resolved weaknesses
        resolved = profile.get("resolved_weaknesses", [])
        for r in resolved[:5]:
            resolved_habits.append({
                "name": r.get("name", ""),
                "message": f"Fixed: {r.get('name', '')}",
                "resolved_at": r.get("resolved_at")
            })
        
        # Also include habits resolved via PDR rotation
        rotated_habits = profile.get("resolved_habits", [])
        for r in rotated_habits:
            stats = r.get("final_stats", {})
            resolved_habits.append({
                "name": r.get("habit", "").replace("_", " ").title(),
                "message": f"Mastered via reflection ({stats.get('correct_attempts', 0)}/{stats.get('total_attempts', 0)} correct)",
                "resolved_at": r.get("resolved_at")
            })
    
    # Get PDR reflection stats for habits
    from habit_rotation_service import get_all_habit_statuses
    habit_statuses = await get_all_habit_statuses(db, user.user_id)
    
    # Enrich habits with reflection stats
    for habit in habits:
        habit_name_lower = habit["name"].lower().replace(" ", "_")
        for status in habit_statuses:
            if status.get("habit", "").lower() == habit_name_lower:
                habit["reflection_stats"] = {
                    "correct": status.get("correct_attempts", 0),
                    "total": status.get("total_attempts", 0),
                    "consecutive": status.get("consecutive_correct", 0),
                    "status": status.get("status", "active")
                }
                break
    
    # Correlate rating to habit if possible
    if rating_data.get("change") and rating_data["change"] > 0 and habits:
        rating_data["habit_correlation"] = f"Reduced {habits[0]['name'].lower()} may have contributed."
    
    # Check for any failed analyses that need retry
    failed_analyses = await db.game_analyses.find(
        {"user_id": user.user_id, "stockfish_failed": True},
        {"_id": 0, "game_id": 1}
    ).to_list(10)
    
    failed_game_ids = [f["game_id"] for f in failed_analyses]
    
    return {
        "rating": rating_data,
        "accuracy": accuracy_data,
        "blunders": blunders_data,
        "habits": habits,
        "resolved_habits": resolved_habits,
        "failed_analyses": failed_game_ids,
        "failed_analysis_count": len(failed_game_ids),
        "valid_analysis_count": valid_count,
        "total_analysis_count": len(recent_analyses)
    }


@api_router.get("/progress/v2")
async def get_progress_v2(user: User = Depends(get_current_user)):
    """
    NEW Progress Page - Chess DNA Badges + Coach Assessment
    
    Returns:
    - Coach's honest assessment (not just stats)
    - Rating reality (framed constructively)
    - 8 skill badges with trends
    - Proof from games
    - Memorable rules
    - Next 10 games plan
    """
    from coach_assessment_service import generate_full_progress_data
    
    try:
        progress_data = await generate_full_progress_data(db, user.user_id)
        return progress_data
    except Exception as e:
        logger.error(f"Progress v2 error: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate progress data")


@api_router.get("/badges")
async def get_chess_badges(user: User = Depends(get_current_user)):
    """Get just the badge scores for quick display"""
    from badge_service import calculate_all_badges, get_badge_history, calculate_badge_trends
    
    try:
        badges = await calculate_all_badges(db, user.user_id)
        history = await get_badge_history(db, user.user_id)
        trends = calculate_badge_trends(badges, history)
        
        # Add trends to badges
        for key in badges.get("badges", {}):
            badges["badges"][key]["trend"] = trends.get(key, "stable")
        
        return badges
    except Exception as e:
        logger.error(f"Badges error: {e}")
        raise HTTPException(status_code=500, detail="Failed to calculate badges")



@api_router.get("/badges/{badge_key}/details")
async def get_badge_details_endpoint(badge_key: str, user: User = Depends(get_current_user)):
    """
    Get detailed drill-down for a specific badge.
    
    Returns:
    - Badge score and insight
    - Last 5 relevant games with specific moves
    - Each move includes FEN for board display (fen_after shows position AFTER the move)
    - Badge-specific commentary adjusted for user's rating level
    """
    from badge_service import get_badge_details, BADGES
    
    if badge_key not in BADGES:
        raise HTTPException(status_code=400, detail=f"Unknown badge: {badge_key}")
    
    try:
        # Get user's rating for rating-appropriate explanations
        user_doc = await db.users.find_one({"user_id": user.user_id}, {"_id": 0, "rating": 1})
        user_rating = user_doc.get("rating", 1200) if user_doc else 1200
        
        details = await get_badge_details(db, user.user_id, badge_key, user_rating)
        return details
    except Exception as e:
        logger.error(f"Badge details error for {badge_key}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get badge details")



# ==================== WEAKNESS/PATTERN ROUTES ====================

@api_router.get("/patterns")
async def get_patterns(user: User = Depends(get_current_user)):
    """Get all mistake patterns for the current user"""
    patterns = await db.mistake_patterns.find(
        {"user_id": user.user_id},
        {"_id": 0}
    ).sort("occurrences", -1).to_list(50)
    return patterns

# ==================== PLAYER PROFILE ROUTES ====================

@api_router.get("/profile")
async def get_player_profile(user: User = Depends(get_current_user)):
    """Get the player's coaching profile"""
    profile = await get_or_create_profile(db, user.user_id, user.name)
    return profile

@api_router.get("/profile/weaknesses")
async def get_ranked_weaknesses(user: User = Depends(get_current_user)):
    """Get player's top weaknesses with time decay applied"""
    profile = await db.player_profiles.find_one(
        {"user_id": user.user_id},
        {"_id": 0}
    )
    
    if not profile:
        return {"top_weaknesses": [], "message": "No profile found. Analyze some games first."}
    
    return {
        "top_weaknesses": profile.get("top_weaknesses", [])[:5],
        "improvement_trend": profile.get("improvement_trend", "stuck"),
        "games_analyzed": profile.get("games_analyzed_count", 0)
    }

@api_router.get("/profile/strengths")
async def get_player_strengths(user: User = Depends(get_current_user)):
    """Get player's identified strengths"""
    profile = await db.player_profiles.find_one(
        {"user_id": user.user_id},
        {"_id": 0}
    )
    
    if not profile:
        return {"strengths": [], "message": "No profile found. Analyze some games first."}
    
    return {
        "strengths": profile.get("strengths", []),
        "estimated_level": profile.get("estimated_level", "intermediate"),
        "estimated_elo": profile.get("estimated_elo", 1200)
    }

class UpdateCoachingPreferencesRequest(BaseModel):
    learning_style: Optional[str] = None  # "concise" or "detailed"
    coaching_tone: Optional[str] = None   # "firm", "encouraging", "balanced"

@api_router.patch("/profile/preferences")
async def update_coaching_preferences(
    req: UpdateCoachingPreferencesRequest,
    user: User = Depends(get_current_user)
):
    """Update coaching preferences (user override)"""
    update_data = {"last_updated": datetime.now(timezone.utc).isoformat()}
    
    if req.learning_style:
        if req.learning_style not in [LearningStyle.CONCISE.value, LearningStyle.DETAILED.value]:
            raise HTTPException(status_code=400, detail="Invalid learning_style. Use 'concise' or 'detailed'")
        update_data["learning_style"] = req.learning_style
    
    if req.coaching_tone:
        if req.coaching_tone not in [CoachingTone.FIRM.value, CoachingTone.ENCOURAGING.value, CoachingTone.BALANCED.value]:
            raise HTTPException(status_code=400, detail="Invalid coaching_tone. Use 'firm', 'encouraging', or 'balanced'")
        update_data["coaching_tone"] = req.coaching_tone
    
    await db.player_profiles.update_one(
        {"user_id": user.user_id},
        {"$set": update_data}
    )
    
    return {"message": "Preferences updated", "updated": update_data}

@api_router.get("/weakness-categories")
async def get_weakness_categories():
    """Get all predefined weakness categories"""
    return {"categories": WEAKNESS_CATEGORIES}

class RecordChallengeResultRequest(BaseModel):
    weakness_category: str
    weakness_subcategory: str
    success: bool
    puzzle_id: Optional[str] = None

@api_router.post("/profile/challenge-result")
async def record_challenge_result_endpoint(
    req: RecordChallengeResultRequest,
    user: User = Depends(get_current_user)
):
    """Record a challenge result and potentially resolve weakness"""
    result = await record_challenge_result(
        db,
        user.user_id,
        req.weakness_category,
        req.weakness_subcategory,
        req.success
    )
    
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    
    return result

# ==================== EMAIL NOTIFICATION SETTINGS ====================

class EmailNotificationSettings(BaseModel):
    game_analyzed: bool = True
    weekly_summary: bool = True
    weakness_alert: bool = True

@api_router.get("/settings/email-notifications")
async def get_email_notification_settings(user: User = Depends(get_current_user)):
    """Get user's email notification preferences"""
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

@api_router.put("/settings/email-notifications")
async def update_email_notification_settings(
    settings: EmailNotificationSettings,
    user: User = Depends(get_current_user)
):
    """Update user's email notification preferences"""
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

@api_router.post("/settings/test-email")
async def send_test_email(user: User = Depends(get_current_user)):
    """Send a test email to verify email configuration"""
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
    
    subject = "🎯 Chess Coach AI - Test Email"
    html_content = f"""
    <html>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
        <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
            <h2>✅ Email Test Successful!</h2>
            <p>Hey {user_doc.get('name', 'Chess Player')}!</p>
            <p>Great news - your email notifications are working correctly.</p>
            <p>You'll receive notifications when:</p>
            <ul>
                <li>New games are analyzed</li>
                <li>Weekly progress summaries are ready</li>
                <li>Recurring weaknesses are detected</li>
            </ul>
            <p>Keep improving your game! ♟️</p>
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

# ==================== PUSH NOTIFICATIONS ====================

class RegisterDeviceRequest(BaseModel):
    push_token: str
    platform: str  # 'ios' or 'android'

@api_router.post("/notifications/register-device")
async def register_push_device(request: RegisterDeviceRequest, user: User = Depends(get_current_user)):
    """Register a device for push notifications"""
    await db.users.update_one(
        {"user_id": user.user_id},
        {
            "$set": {
                "push_token": request.push_token,
                "push_platform": request.platform,
                "push_registered_at": datetime.now(timezone.utc).isoformat()
            }
        }
    )
    return {"message": "Device registered for push notifications"}

@api_router.delete("/notifications/unregister-device")
async def unregister_push_device(user: User = Depends(get_current_user)):
    """Unregister device from push notifications"""
    await db.users.update_one(
        {"user_id": user.user_id},
        {
            "$unset": {
                "push_token": "",
                "push_platform": "",
                "push_registered_at": ""
            }
        }
    )
    return {"message": "Device unregistered from push notifications"}

async def send_push_notification(user_id: str, title: str, body: str, data: dict = None):
    """
    Send push notification to a user via Expo Push API.
    This is called when games are analyzed, etc.
    """
    import httpx
    
    user_doc = await db.users.find_one(
        {"user_id": user_id},
        {"_id": 0, "push_token": 1, "email_notifications": 1}
    )
    
    if not user_doc or not user_doc.get("push_token"):
        return False
    
    push_token = user_doc["push_token"]
    
    # Check if user has notifications enabled
    email_prefs = user_doc.get("email_notifications", {})
    if not email_prefs.get("game_analyzed", True):
        return False
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://exp.host/--/api/v2/push/send",
                json={
                    "to": push_token,
                    "title": title,
                    "body": body,
                    "data": data or {},
                    "sound": "default",
                    "channelId": "analysis",
                },
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                logger.info(f"Push notification sent to user {user_id}")
                return True
            else:
                logger.warning(f"Push notification failed: {response.text}")
                return False
    except Exception as e:
        logger.error(f"Failed to send push notification: {e}")
        return False

@api_router.get("/dashboard-stats")
async def get_dashboard_stats(user: User = Depends(get_current_user)):
    """Get dashboard statistics including player profile for the current user"""
    total_games = await db.games.count_documents({"user_id": user.user_id})
    analyzed_games = await db.games.count_documents({"user_id": user.user_id, "is_analyzed": True})
    
    # Count games in queue
    queued_games = await db.analysis_queue.count_documents({
        "user_id": user.user_id,
        "status": {"$in": ["pending", "processing"]}
    })
    
    # Get player profile for coaching context
    profile = await db.player_profiles.find_one(
        {"user_id": user.user_id},
        {"_id": 0}
    )
    
    # Get top weaknesses from profile (with decay) instead of raw patterns
    top_weaknesses = []
    if profile:
        top_weaknesses = profile.get("top_weaknesses", [])[:5]
    else:
        # Fallback to legacy patterns if no profile
        patterns = await db.mistake_patterns.find(
            {"user_id": user.user_id},
            {"_id": 0}
        ).sort("occurrences", -1).to_list(5)
        top_weaknesses = patterns
    
    # Get queued game IDs FIRST (so we can include them in the query)
    queue_items = await db.analysis_queue.find(
        {"user_id": user.user_id, "status": {"$in": ["pending", "processing"]}},
        {"_id": 0, "game_id": 1, "status": 1, "queued_at": 1}
    ).to_list(100)
    queued_game_map = {q["game_id"]: q for q in queue_items}
    queued_game_ids = set(queued_game_map.keys())
    
    # Get recent games (up to 100)
    all_games = await db.games.find(
        {"user_id": user.user_id},
        {
            "_id": 0,
            "game_id": 1,
            "white_player": 1,
            "black_player": 1,
            "user_color": 1,
            "result": 1,
            "platform": 1,
            "opening": 1,
            "is_analyzed": 1,
            "analysis_status": 1,
            "imported_at": 1,
            "pgn": 1  # Need PGN to extract player names if not stored
        }
    ).sort("imported_at", -1).to_list(100)
    
    # Also fetch any queued games that might not be in the top 100
    all_game_ids = {g["game_id"] for g in all_games}
    missing_queued_ids = queued_game_ids - all_game_ids
    
    if missing_queued_ids:
        missing_games = await db.games.find(
            {"game_id": {"$in": list(missing_queued_ids)}, "user_id": user.user_id},
            {
                "_id": 0,
                "game_id": 1,
                "white_player": 1,
                "black_player": 1,
                "user_color": 1,
                "result": 1,
                "platform": 1,
                "opening": 1,
                "is_analyzed": 1,
                "analysis_status": 1,
                "imported_at": 1,
                "pgn": 1
            }
        ).to_list(100)
        all_games.extend(missing_games)
    
    # Categorize games
    analyzed_list = []
    in_queue_list = []
    not_analyzed_list = []  # NEW: Games that haven't been analyzed
    recent_games = []  # For backward compatibility, top 10
    
    # Enrich games with accuracy from analysis and extract player names from PGN
    import re
    for game in all_games:
        # Extract player names from PGN if not already present
        pgn = game.get("pgn", "")
        if pgn:
            if not game.get("white_player") or game.get("white_player") in ["Unknown", "?"]:
                white_match = re.search(r'\[White "([^"]+)"\]', pgn)
                if white_match:
                    game["white_player"] = white_match.group(1)
            if not game.get("black_player") or game.get("black_player") in ["Unknown", "?"]:
                black_match = re.search(r'\[Black "([^"]+)"\]', pgn)
                if black_match:
                    game["black_player"] = black_match.group(1)
            
            # Also extract ratings from PGN
            white_elo_match = re.search(r'\[WhiteElo "(\d+)"\]', pgn)
            black_elo_match = re.search(r'\[BlackElo "(\d+)"\]', pgn)
            if white_elo_match:
                game["white_rating"] = int(white_elo_match.group(1))
            if black_elo_match:
                game["black_rating"] = int(black_elo_match.group(1))
        
        # Don't send PGN to frontend (too large)
        if "pgn" in game:
            del game["pgn"]
        
        game_id = game.get("game_id")
        
        # Determine analysis status - CHECK QUEUE FIRST (priority)
        if game_id in queued_game_ids:
            # Game is in queue - show it there regardless of is_analyzed flag
            queue_info = queued_game_map.get(game_id, {})
            game["analysis_status"] = queue_info.get("status", "pending")
            game["queued_at"] = queue_info.get("queued_at")
            in_queue_list.append(game)
        elif game.get("is_analyzed"):
            analysis = await db.game_analyses.find_one(
                {"game_id": game_id, "user_id": user.user_id},
                {"_id": 0, "stockfish_analysis.accuracy": 1, "stockfish_analysis.move_evaluations": 1}
            )
            if analysis:
                accuracy = analysis.get("stockfish_analysis", {}).get("accuracy", 0)
                move_evals = analysis.get("stockfish_analysis", {}).get("move_evaluations", [])
                game["accuracy"] = accuracy
                
                # If accuracy is 0 and no move evaluations, treat as NOT analyzed (incomplete analysis)
                if accuracy == 0 and len(move_evals) == 0:
                    game["analysis_status"] = "not_analyzed"
                    not_analyzed_list.append(game)
                else:
                    game["analysis_status"] = "analyzed"
                    analyzed_list.append(game)
            else:
                # No analysis record found - treat as not analyzed
                game["analysis_status"] = "not_analyzed"
                not_analyzed_list.append(game)
        else:
            game["analysis_status"] = "not_analyzed"
            not_analyzed_list.append(game)  # Add to not_analyzed list
    
    # Update analyzed_games count to reflect actual valid analyses
    analyzed_games = len(analyzed_list)
    
    # Build recent_games for backward compatibility (top 10 of all games)
    recent_games = all_games[:10]
    
    analyses = await db.game_analyses.find(
        {"user_id": user.user_id},
        {"_id": 0}
    ).to_list(100)
    
    total_blunders = sum(a.get('blunders', 0) for a in analyses)
    total_mistakes = sum(a.get('mistakes', 0) for a in analyses)
    total_best_moves = sum(a.get('best_moves', 0) for a in analyses)
    
    # Build response with profile data
    response = {
        "total_games": total_games,
        "analyzed_games": analyzed_games,
        "queued_games": len(in_queue_list),
        "not_analyzed_games": len(not_analyzed_list),  # NEW: count of unanalyzed games
        "top_weaknesses": top_weaknesses,
        "recent_games": recent_games,  # Backward compatibility
        "analyzed_list": analyzed_list,  # Only analyzed games
        "in_queue_list": in_queue_list,  # Games currently being analyzed
        "not_analyzed_list": not_analyzed_list,  # NEW: Games that need analysis
        "stats": {
            "total_blunders": total_blunders,
            "total_mistakes": total_mistakes,
            "total_best_moves": total_best_moves
        }
    }
    
    # Add rating impact estimate
    if len(analyses) >= 5:
        rating_impact = estimate_rating_impact(analyses)
        response["rating_impact"] = rating_impact
    
    # Add profile summary if available
    if profile:
        response["profile_summary"] = {
            "estimated_level": profile.get("estimated_level", "intermediate"),
            "estimated_elo": profile.get("estimated_elo", 1200),
            "improvement_trend": profile.get("improvement_trend", "stuck"),
            "strengths": profile.get("strengths", [])[:3],
            "learning_style": profile.get("learning_style", "concise"),
            "coaching_tone": profile.get("coaching_tone", "encouraging"),
            "challenges_solved": profile.get("challenges_solved", 0),
            "challenges_attempted": profile.get("challenges_attempted", 0)
        }
    
    return response

@api_router.get("/training-recommendations")
async def get_training_recommendations(user: User = Depends(get_current_user)):
    """Get AI-generated training recommendations based on weaknesses"""
    import json
    
    patterns = await db.mistake_patterns.find(
        {"user_id": user.user_id},
        {"_id": 0}
    ).sort("occurrences", -1).to_list(10)
    
    if not patterns:
        return {
            "recommendations": [
                {
                    "title": "Import Your Games",
                    "description": "Start by importing games from Chess.com or Lichess to get personalized recommendations.",
                    "priority": "high"
                }
            ]
        }
    
    patterns_text = "\n".join([
        f"- {p['subcategory']} ({p['category']}): {p['occurrences']} occurrences - {p['description']}"
        for p in patterns
    ])
    
    system_message = """You are a chess coach creating a personalized training plan.
Based on the player's mistake patterns, suggest 3-5 specific training exercises.
Be specific and actionable. Respond in JSON format:
{
    "recommendations": [
        {"title": "...", "description": "...", "priority": "high/medium/low", "estimated_time": "15 mins"}
    ]
}"""
    
    try:
        response = await call_llm(
            system_message=system_message,
            user_message=f"Create training recommendations for a player with these weakness patterns:\n{patterns_text}",
            model="gpt-4o-mini"
        )
        
        response_clean = response.strip()
        if response_clean.startswith("```json"):
            response_clean = response_clean[7:]
        if response_clean.startswith("```"):
            response_clean = response_clean[3:]
        if response_clean.endswith("```"):
            response_clean = response_clean[:-3]
        
        return json.loads(response_clean)
        
    except Exception as e:
        logger.error(f"Recommendation error: {e}")
        return {
            "recommendations": [
                {
                    "title": "Practice Tactical Puzzles",
                    "description": "Based on your patterns, focus on tactical awareness exercises.",
                    "priority": "high"
                }
            ]
        }

# ==================== RATING & TRAINING ENDPOINTS ====================

@api_router.get("/rating/trajectory")
async def get_rating_trajectory(user: User = Depends(get_current_user)):
    """
    Get rating prediction and trajectory for the user.
    Includes platform ratings, projected ratings, and time to milestones.
    """
    # Get user data
    user_doc = await db.users.find_one({"user_id": user.user_id}, {"_id": 0})
    chess_com_username = user_doc.get("chess_com_username")
    lichess_username = user_doc.get("lichess_username")
    
    # Fetch platform ratings
    platform_ratings = await fetch_platform_ratings(chess_com_username, lichess_username)
    
    # Get current best rating
    current_rating = DEFAULT_RATING  # Default
    rating_source = "estimated"
    
    if platform_ratings.get('chess_com', {}).get('rapid'):
        current_rating = platform_ratings['chess_com']['rapid']
        rating_source = "chess_com_rapid"
    elif platform_ratings.get('lichess', {}).get('rapid'):
        current_rating = platform_ratings['lichess']['rapid']
        rating_source = "lichess_rapid"
    elif platform_ratings.get('chess_com', {}).get('blitz'):
        current_rating = platform_ratings['chess_com']['blitz']
        rating_source = "chess_com_blitz"
    elif platform_ratings.get('lichess', {}).get('blitz'):
        current_rating = platform_ratings['lichess']['blitz']
        rating_source = "lichess_blitz"
    
    # Get game analyses for improvement velocity
    analyses = await db.game_analyses.find(
        {"user_id": user.user_id},
        {"_id": 0, "blunders": 1, "mistakes": 1, "best_moves": 1, "analyzed_at": 1}
    ).to_list(50)
    
    # Calculate improvement velocity
    velocity = calculate_improvement_velocity(analyses)
    
    # Get weaknesses
    profile = await db.player_profiles.find_one(
        {"user_id": user.user_id},
        {"_id": 0, "top_weaknesses": 1, "estimated_elo": 1}
    )
    weaknesses = profile.get("top_weaknesses", []) if profile else []
    
    # If we don't have platform rating, use profile estimate
    if rating_source == "estimated" and profile:
        current_rating = profile.get("estimated_elo", 1200)
    
    # Generate trajectory prediction
    trajectory = predict_rating_trajectory(current_rating, velocity, weaknesses)
    
    return {
        "platform_ratings": platform_ratings,
        "current_rating": current_rating,
        "rating_source": rating_source,
        "improvement_velocity": velocity,
        "trajectory": trajectory,
        "linked_accounts": {
            "chess_com": chess_com_username,
            "lichess": lichess_username
        }
    }

@api_router.get("/training/time-management")
async def get_time_management_analysis(user: User = Depends(get_current_user)):
    """
    Analyze time management patterns from recent games.
    Shows clock usage, time trouble patterns, and recommendations.
    """
    # Get recent games with PGN
    games = await db.games.find(
        {"user_id": user.user_id},
        {"_id": 0, "pgn": 1, "user_color": 1, "time_control": 1, "result": 1}
    ).sort("imported_at", -1).to_list(30)
    
    if not games:
        return {
            "has_data": False,
            "message": "Import some games first to analyze your time management."
        }
    
    # Analyze time usage
    analysis = analyze_time_usage(games, user.user_id)
    
    return analysis

@api_router.get("/training/fast-thinking")
async def get_fast_thinking_analysis(user: User = Depends(get_current_user)):
    """
    Get analysis of calculation speed and pattern recognition.
    Includes tips for thinking faster and spotting tactics.
    """
    # Get analyses with move-by-move data
    analyses = await db.game_analyses.find(
        {"user_id": user.user_id},
        {"_id": 0, "move_by_move": 1, "analyzed_at": 1}
    ).sort("analyzed_at", -1).to_list(20)
    
    # Generate calculation analysis
    calc_analysis = generate_calculation_analysis(analyses)
    
    # Get weaknesses for targeted tips
    profile = await db.player_profiles.find_one(
        {"user_id": user.user_id},
        {"_id": 0, "top_weaknesses": 1}
    )
    weaknesses = profile.get("top_weaknesses", []) if profile else []
    
    # Add weakness-specific tips
    if weaknesses and calc_analysis.get("has_data"):
        top_weakness = weaknesses[0].get('subcategory', '')
        calc_analysis["focus_weakness"] = top_weakness
        calc_analysis["weakness_tip"] = f"Focus on spotting {top_weakness.replace('_', ' ')} patterns faster"
    
    return calc_analysis

@api_router.get("/training/puzzles")
async def get_training_puzzles(user: User = Depends(get_current_user), count: int = 5):
    """
    Get personalized puzzles based on weaknesses.
    Puzzles are selected to target the player's specific weak areas.
    """
    # Get weaknesses
    profile = await db.player_profiles.find_one(
        {"user_id": user.user_id},
        {"_id": 0, "top_weaknesses": 1}
    )
    weaknesses = profile.get("top_weaknesses", []) if profile else []
    
    # Generate training session
    session = generate_training_session(weaknesses, count)
    
    return session

@api_router.post("/training/puzzles/{puzzle_index}/solve")
async def submit_puzzle_solution(
    puzzle_index: int,
    solution: str,
    time_taken_seconds: int,
    user: User = Depends(get_current_user)
):
    """
    Submit a puzzle solution and track progress.
    """
    # Record puzzle attempt
    puzzle_attempt = {
        "user_id": user.user_id,
        "puzzle_index": puzzle_index,
        "solution_submitted": solution,
        "time_taken_seconds": time_taken_seconds,
        "attempted_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.puzzle_attempts.insert_one(puzzle_attempt)
    
    # Update profile stats
    await db.player_profiles.update_one(
        {"user_id": user.user_id},
        {
            "$inc": {
                "puzzles_attempted": 1,
                "total_puzzle_time_seconds": time_taken_seconds
            }
        },
        upsert=True
    )
    
    return {
        "message": "Solution recorded",
        "time_taken_seconds": time_taken_seconds
    }

# ==================== STOCKFISH POSITION ANALYSIS ====================

class PositionAnalysisRequest(BaseModel):
    fen: str
    depth: int = 18

@api_router.post("/analyze-position")
async def analyze_position(req: PositionAnalysisRequest, user: User = Depends(get_current_user)):
    """
    Analyze a single position using Stockfish.
    Returns evaluation and best moves.
    """
    try:
        result = get_position_evaluation(req.fen, depth=req.depth)
        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("error", "Analysis failed"))
        return result
    except Exception as e:
        logger.error(f"Position analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/best-moves")
async def get_best_moves(req: PositionAnalysisRequest, num_moves: int = 3, user: User = Depends(get_current_user)):
    """
    Get the top N best moves for a position using Stockfish.
    Useful for showing alternatives.
    """
    try:
        result = get_best_moves_for_position(req.fen, num_moves=num_moves, depth=req.depth)
        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("error", "Analysis failed"))
        return result
    except Exception as e:
        logger.error(f"Best moves analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== BASIC ROUTES ====================

@api_router.get("/")
async def root():
    return {"message": "Chess Coach API"}

@api_router.get("/health")
async def health():
    return {"status": "healthy"}


# ==================== ASK ABOUT MOVE (Interactive Analysis) ====================

class AskAboutMoveRequest(BaseModel):
    """Request for asking questions about a specific position/move"""
    fen: Optional[str] = None  # Position AFTER the move (current board state)
    fen_before: Optional[str] = None  # Position BEFORE the move (for analyzing what user should have played)
    question: str
    played_move: Optional[str] = None  # The move that was played (if any)
    alternative_move: Optional[str] = None  # A "what if" move to analyze
    move_number: Optional[int] = None
    user_color: Optional[str] = "white"
    conversation_history: Optional[List[Dict[str, str]]] = None  # Previous Q&A pairs for context
    context: Optional[str] = None  # Additional context (badge type, threat info, etc.)

@api_router.post("/game/{game_id}/ask")
async def ask_about_move(game_id: str, req: AskAboutMoveRequest, user: User = Depends(get_current_user)):
    """
    Ask a question about a specific position/move in a game.
    Uses Stockfish for analysis and GPT for explanation.
    
    Example questions:
    - "What if I played Nf3 instead?"
    - "Why is this move a blunder?"
    - "What was my opponent threatening?"
    - "What should my plan be here?"
    """
    import chess
    
    try:
        # Use fen_before if fen is not provided (common from badge detail modal)
        position_fen = req.fen or req.fen_before
        
        if not position_fen:
            raise HTTPException(status_code=400, detail="Either fen or fen_before must be provided")
        
        # Validate FEN
        try:
            board = chess.Board(position_fen)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid FEN position")
        
        user_color = req.user_color or "white"
        current_turn = "white" if board.turn else "black"
        
        # Position BEFORE the move - this is where we analyze what user SHOULD have played
        board_before = None
        if req.fen_before:
            try:
                board_before = chess.Board(req.fen_before)
            except:
                board_before = None
        elif req.fen:
            # If only fen is provided, use it as board_before too
            board_before = board
        
        # Analyze the position BEFORE the move to find what user should have played
        best_move_for_user = None
        best_line_for_user = []
        eval_before = None
        
        if board_before and req.played_move:
            # Get Stockfish analysis for position BEFORE the move
            before_eval = get_position_evaluation(req.fen_before, depth=18)
            if before_eval.get("success"):
                eval_before = before_eval.get("evaluation", 0)
                if isinstance(eval_before, dict):
                    eval_before = eval_before.get("centipawns", 0)
                
                best_move_data = before_eval.get("best_move", {})
                if isinstance(best_move_data, dict):
                    best_move_for_user = best_move_data.get("san", "")
                else:
                    best_move_for_user = str(best_move_data) if best_move_data else ""
                
                best_line_for_user = before_eval.get("pv", [])[:5]
        
        # Get Stockfish analysis for the CURRENT position (after the move)
        position_eval = get_position_evaluation(req.fen, depth=18)
        if not position_eval.get("success"):
            raise HTTPException(status_code=500, detail="Failed to analyze position")
        
        # Extract evaluation - handle both object and number formats
        eval_data = position_eval.get("evaluation", {})
        if isinstance(eval_data, dict):
            eval_score = eval_data.get("centipawns", 0)
            is_mate = eval_data.get("is_mate", False)
            mate_in = eval_data.get("mate_in")
        else:
            eval_score = eval_data
            is_mate = False
            mate_in = None
        
        # Extract best move for CURRENT position (opponent's best response)
        best_move_data = position_eval.get("best_move", {})
        if isinstance(best_move_data, dict):
            opponent_best_move = best_move_data.get("san", "")
        else:
            opponent_best_move = str(best_move_data) if best_move_data else ""
        
        stockfish_data = {
            "evaluation": eval_score,
            "eval_type": "mate" if is_mate else "cp",
            "best_move": opponent_best_move,  # This is opponent's best move (current turn)
            "best_line": position_eval.get("pv", [])[:5],
            "is_check": board.is_check(),
            "is_checkmate": board.is_checkmate(),
            "turn": current_turn,
            # NEW: Best move for the USER (from position BEFORE their move)
            "user_best_move": best_move_for_user,
            "user_best_line": best_line_for_user,
            "eval_before": eval_before
        }
        
        # If user asks about an alternative move, analyze it from position BEFORE
        alternative_analysis = None
        if req.alternative_move and board_before:
            try:
                # Parse and validate the alternative move on the board BEFORE
                alt_move = board_before.parse_san(req.alternative_move)
                alt_board = board_before.copy()
                alt_board.push(alt_move)
                
                # Analyze position after alternative move
                alt_eval = get_position_evaluation(alt_board.fen(), depth=18)
                if alt_eval.get("success"):
                    alternative_analysis = {
                        "move": req.alternative_move,
                        "resulting_fen": alt_board.fen(),
                        "evaluation": alt_eval.get("evaluation"),
                        "eval_type": alt_eval.get("eval_type"),
                        "opponent_best_response": alt_eval.get("best_move"),
                        "continuation": alt_eval.get("pv", [])[:5]
                    }
            except Exception as e:
                alternative_analysis = {"error": f"Invalid move: {req.alternative_move}"}
        
        # Store played move analysis
        played_analysis = None
        if req.played_move:
            played_analysis = {
                "move": req.played_move,
                "evaluation_after": eval_score,
                "opponent_best_response": opponent_best_move,
                "user_should_have_played": best_move_for_user,
                "user_best_line": best_line_for_user
            }
        
        # Build human-readable position description
        def describe_position(b):
            """Generate a human-readable description of the chess position"""
            piece_names = {
                'K': 'King', 'Q': 'Queen', 'R': 'Rook', 'B': 'Bishop', 'N': 'Knight', 'P': 'Pawn',
                'k': 'King', 'q': 'Queen', 'r': 'Rook', 'b': 'Bishop', 'n': 'Knight', 'p': 'Pawn'
            }
            
            white_pieces = []
            black_pieces = []
            
            for square in chess.SQUARES:
                piece = b.piece_at(square)
                if piece:
                    square_name = chess.square_name(square)
                    piece_name = piece_names.get(piece.symbol(), 'Piece')
                    if piece.color == chess.WHITE:
                        white_pieces.append(f"{piece_name} on {square_name}")
                    else:
                        black_pieces.append(f"{piece_name} on {square_name}")
            
            return f"White: {', '.join(white_pieces)}\nBlack: {', '.join(black_pieces)}"
        
        # Get legal moves in SAN notation (for current position)
        legal_moves_san = [board.san(m) for m in board.legal_moves]
        legal_moves_str = ', '.join(legal_moves_san[:20])
        if len(legal_moves_san) > 20:
            legal_moves_str += f" (and {len(legal_moves_san) - 20} more)"
        
        # Determine context for the prompt
        user_color_name = user_color.title()
        
        # === USE DETERMINISTIC MISTAKE CLASSIFIER ===
        # This is the "truth layer" - no LLM guessing allowed
        mistake_analysis = None
        structured_facts = []
        
        if req.played_move and req.fen_before and eval_before is not None:
            try:
                from mistake_classifier import (
                    classify_mistake, get_verbalization_template,
                    find_forks, find_pins, find_skewers
                )
                
                mistake = classify_mistake(
                    fen_before=req.fen_before,
                    fen_after=req.fen or req.fen_before,
                    move_played=req.played_move,
                    best_move=best_move_for_user or "",
                    eval_before=eval_before,
                    eval_after=eval_score,
                    user_color=user_color,
                    move_number=getattr(req, 'move_number', 20),
                    threat=None
                )
                
                mistake_analysis = {
                    "type": mistake.mistake_type.value,
                    "eval_drop": mistake.eval_drop,
                    "template": get_verbalization_template(mistake),
                    "pattern_details": mistake.pattern_details
                }
                
                # Build structured facts for LLM
                structured_facts.append(f"MISTAKE_TYPE: {mistake.mistake_type.value}")
                structured_facts.append(f"EVAL_DROP: {mistake.eval_drop:.1f} pawns")
                if mistake.pattern_details.get("reason"):
                    structured_facts.append(f"REASON: {mistake.pattern_details['reason']}")
                structured_facts.append(f"COACHING_TEMPLATE: {get_verbalization_template(mistake)}")
                
                # Check for tactical patterns in position
                user_chess_color = chess.WHITE if user_color == "white" else chess.BLACK
                forks = find_forks(board_before, not user_chess_color) if board_before else []
                pins = find_pins(board_before, user_chess_color) if board_before else []
                
                if forks:
                    structured_facts.append(f"THREAT_FORK: Opponent has fork potential with {forks[0]['attacker_piece']}")
                if pins:
                    structured_facts.append(f"YOUR_PINNED_PIECE: {pins[0]['pinned_piece']} on {pins[0]['pinned_square']}")
                    
            except Exception as e:
                logger.warning(f"Mistake classifier error: {e}")
                mistake_analysis = None
        
        # === BUILD PERSONALITY LAYER PROMPT ===
        # LLM can ONLY verbalize the structured facts - it cannot invent chess analysis
        
        prompt = f"""You are an encouraging chess coach. Your job is to VERBALIZE the structured analysis below in a friendly, educational way.

IMPORTANT RULES:
1. You CANNOT invent chess analysis. Only explain what is in the STRUCTURED FACTS.
2. You CANNOT claim a move creates a fork/pin/skewer unless it's in the STRUCTURED FACTS.
3. Keep it simple for a ~1300 rated player.
4. Be encouraging - this is a learning moment.
5. 3-4 sentences maximum.

STUDENT'S COLOR: {user_color_name}
STUDENT PLAYED: {req.played_move if req.played_move else 'N/A'}
BEST MOVE WAS: {best_move_for_user if best_move_for_user else 'N/A'}

=== STRUCTURED FACTS (from deterministic analysis) ===
{chr(10).join(structured_facts) if structured_facts else 'No structured analysis available.'}
===

STUDENT'S QUESTION: {req.question}

"""

        if alternative_analysis and "error" not in alternative_analysis:
            prompt += f"""
ALTERNATIVE MOVE ANALYZED: {req.alternative_move}
- Evaluation: {alternative_analysis.get('evaluation')} centipawns
- Opponent's best response: {alternative_analysis.get('opponent_best_response')}
"""

        # Add conversation history for context
        if req.conversation_history and len(req.conversation_history) > 0:
            prompt += "\nPREVIOUS CONVERSATION:\n"
            for exchange in req.conversation_history[-3:]:
                prompt += f"Student: {exchange.get('question', '')}\n"
                prompt += f"Coach: {exchange.get('answer', '')}\n"
            prompt += "\n"

        prompt += """
Respond naturally as a supportive mentor. Use the structured facts to explain what happened.
If the student asks about something not in the facts, say "Let me check..." and stick to what we know from the analysis."""

        # Get GPT response using OpenAI directly
        try:
            answer = await call_llm(
                system_message="You are a chess coach who ONLY verbalizes pre-analyzed facts. You cannot invent chess analysis.",
                user_message=prompt,
                model="gpt-4o-mini"
            )
            answer = answer.strip()
        except Exception as e:
            logger.error(f"GPT error in ask_about_move: {e}")
            # Fallback to the deterministic template (no LLM needed)
            if mistake_analysis:
                answer = mistake_analysis.get("template", f"The best move was {best_move_for_user}.")
            else:
                answer = f"The best move here was {best_move_for_user or stockfish_data['best_move']}."
        
        # Build response with the deterministic analysis included
        return {
            "answer": answer,
            "stockfish": {
                "evaluation": stockfish_data["evaluation"],
                "eval_type": stockfish_data["eval_type"],
                "best_move": stockfish_data["best_move"],  # Opponent's best move
                "best_line": stockfish_data["best_line"],
                "user_best_move": best_move_for_user,  # What USER should have played
                "user_best_line": best_line_for_user
            },
            "alternative_analysis": alternative_analysis,
            "played_analysis": played_analysis,
            "mistake_analysis": mistake_analysis  # NEW: Include structured analysis
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ask about move error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Failed to analyze position")


# ==================== CHALLENGE/PUZZLE ROUTES ====================

class GeneratePuzzleRequest(BaseModel):
    pattern_id: Optional[str] = None
    category: str = "tactical"
    subcategory: str = "general"

@api_router.post("/generate-puzzle")
async def generate_puzzle(req: GeneratePuzzleRequest, user: User = Depends(get_current_user)):
    """Generate a puzzle based on user's weakness pattern from PlayerProfile"""
    import json
    
    # Get player profile for context
    profile = await db.player_profiles.find_one(
        {"user_id": user.user_id},
        {"_id": 0}
    )
    
    # Determine which weakness to target
    weakness_context = ""
    target_category = req.category
    target_subcategory = req.subcategory
    
    if req.pattern_id:
        # Use specified pattern
        pattern = await db.mistake_patterns.find_one(
            {"pattern_id": req.pattern_id, "user_id": user.user_id},
            {"_id": 0}
        )
        if pattern:
            target_category, target_subcategory = categorize_weakness(
                pattern.get("category", "tactical"),
                pattern.get("subcategory", "one_move_blunders")
            )
            weakness_context = f"The player struggles with: {target_subcategory.replace('_', ' ')} ({target_category}). {pattern.get('description', '')}"
    elif profile and profile.get("top_weaknesses"):
        # Use top weakness from profile
        top_weakness = profile["top_weaknesses"][0]
        target_category = top_weakness.get("category", "tactical")
        target_subcategory = top_weakness.get("subcategory", "one_move_blunders")
        weakness_context = f"Player's #1 weakness: {target_subcategory.replace('_', ' ')} ({target_category}). Score: {top_weakness.get('decayed_score', 1)}"
    else:
        weakness_context = f"Focus on {req.subcategory.replace('_', ' ')} in the {req.category} category."
    
    # Get player level for difficulty calibration
    player_level = "intermediate"
    if profile:
        player_level = profile.get("estimated_level", "intermediate")
    
    system_prompt = f"""You are a chess puzzle creator. Create a tactical puzzle for training.

Player Level: {player_level.upper()}
Target Weakness: {weakness_context}

Create a puzzle that specifically targets this weakness. The puzzle should:
1. Have a clear winning move or sequence
2. Be instructive for the specific weakness
3. Difficulty appropriate for {player_level} level ({"1 move" if player_level == "beginner" else "1-3 moves"})

Respond in JSON format ONLY:
{{
    "title": "Short descriptive title",
    "description": "Brief description of what to look for",
    "fen": "Valid FEN position string",
    "player_color": "white" or "black",
    "solution_san": "The correct move in SAN notation (e.g., Nxf7)",
    "solution": [{{"from": "e4", "to": "f7"}}],
    "hint": "A subtle hint without giving away the answer",
    "theme": "{target_subcategory}",
    "explanation": {{
        "thinking_error": "What thinking error does this puzzle train against",
        "one_repeatable_rule": "The rule this puzzle teaches"
    }}
}}

Make sure the FEN is valid and the solution is correct for that position."""

    try:
        response = await call_llm(
            system_message=system_prompt,
            user_message=f"Generate a {target_category} puzzle focusing on {target_subcategory.replace('_', ' ')}",
            model="gpt-4o-mini"
        )
        
        response_clean = response.strip()
        if response_clean.startswith("```json"):
            response_clean = response_clean[7:]
        if response_clean.startswith("```"):
            response_clean = response_clean[3:]
        if response_clean.endswith("```"):
            response_clean = response_clean[:-3]
        
        puzzle = json.loads(response_clean)
        
        # Store puzzle with target weakness for feedback loop
        puzzle_doc = {
            "puzzle_id": f"puzzle_{uuid.uuid4().hex[:12]}",
            "user_id": user.user_id,
            "pattern_id": req.pattern_id,
            "target_category": target_category,
            "target_subcategory": target_subcategory,
            "solved": None,  # Will be updated when user submits result
            "solve_time_seconds": None,
            **puzzle,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        await db.puzzles.insert_one(puzzle_doc)
        puzzle_doc.pop('_id', None)
        
        return puzzle_doc
        
    except Exception as e:
        logger.error(f"Puzzle generation error: {e}")
        # Return a fallback puzzle with proper tracking fields
        fallback_puzzle = {
            "puzzle_id": f"puzzle_{uuid.uuid4().hex[:12]}",
            "user_id": user.user_id,
            "target_category": target_category,
            "target_subcategory": target_subcategory,
            "title": "Tactical Training",
            "description": f"Find the best move in this {target_subcategory.replace('_', ' ')} position",
            "fen": "r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 4 4",
            "player_color": "white",
            "solution_san": "Qxf7#",
            "solution": [{"from": "h5", "to": "f7"}],
            "hint": "Look for a forcing move that attacks multiple pieces",
            "theme": target_subcategory,
            "explanation": {
                "thinking_error": "Missing forcing moves that end the game",
                "one_repeatable_rule": "Always check for checkmate threats first"
            },
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        await db.puzzles.insert_one(fallback_puzzle)
        fallback_puzzle.pop('_id', None)
        return fallback_puzzle

# ==================== GAMIFICATION ROUTES ====================

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

@api_router.get("/gamification/progress")
async def get_progress(user: User = Depends(get_current_user)):
    """Get user's XP, level, streak, and stats"""
    progress = await get_user_progress(user.user_id)
    return progress

# ==================== GAMIFICATION ROUTES ====================

@api_router.get("/gamification/achievements")
async def get_achievements(user: User = Depends(get_current_user)):
    """Get all achievements with unlock status"""
    achievements = await get_user_achievements(user.user_id)
    return achievements

@api_router.post("/gamification/daily-reward")
async def claim_daily(user: User = Depends(get_current_user)):
    """Claim daily login reward and update streak"""
    result = await claim_daily_reward(user.user_id)
    return result

@api_router.get("/gamification/leaderboard")
async def leaderboard(limit: int = 20, user: User = Depends(get_current_user)):
    """Get XP leaderboard"""
    leaders = await get_leaderboard(limit)
    return {"leaderboard": leaders}

@api_router.get("/gamification/levels")
async def get_levels():
    """Get all level definitions (public endpoint)"""
    return {"levels": LEVELS}

@api_router.get("/gamification/achievement-definitions")
async def get_achievement_definitions():
    """Get all achievement definitions (public endpoint)"""
    return {"achievements": ACHIEVEMENTS}

@api_router.get("/gamification/xp-rewards")
async def get_xp_rewards():
    """Get XP reward values (public endpoint)"""
    return {"rewards": XP_REWARDS}

# ==================== OPENING REPERTOIRE ROUTES ====================

from opening_service import analyze_opening_repertoire

@api_router.get("/openings/repertoire")
async def get_opening_repertoire(user: User = Depends(get_current_user)):
    """
    Analyze user's opening repertoire from all their games.
    Returns detailed stats, problem areas, and personalized coaching.
    """
    result = await analyze_opening_repertoire(db, user.user_id)
    return result

# ==================== NOTIFICATIONS ROUTES ====================

@api_router.get("/notifications")
async def get_notifications(limit: int = 20, unread_only: bool = False, user: User = Depends(get_current_user)):
    """Get user's in-app notifications"""
    query = {"user_id": user.user_id}
    if unread_only:
        query["read"] = False
    
    notifications = await db.notifications.find(
        query,
        {"_id": 0}
    ).sort("created_at", -1).limit(limit).to_list(limit)
    
    # Count unread
    unread_count = await db.notifications.count_documents({"user_id": user.user_id, "read": False})
    
    return {
        "notifications": notifications,
        "unread_count": unread_count
    }

@api_router.post("/notifications/{notification_id}/read")
async def mark_single_notification_read(notification_id: str, user: User = Depends(get_current_user)):
    """Mark a notification as read"""
    result = await db.notifications.update_one(
        {"user_id": user.user_id, "notification_id": notification_id},
        {"$set": {"read": True}}
    )
    return {"success": result.modified_count > 0}

@api_router.post("/notifications/read-all")
async def mark_all_notifications_read(user: User = Depends(get_current_user)):
    """Mark all notifications as read"""
    result = await db.notifications.update_many(
        {"user_id": user.user_id, "read": False},
        {"$set": {"read": True}}
    )
    return {"success": True, "updated": result.modified_count}

# ==================== RAG MANAGEMENT ROUTES ====================

@api_router.post("/rag/process-games")
async def process_games_for_rag(background_tasks: BackgroundTasks, user: User = Depends(get_current_user)):
    """Process all user games to create RAG embeddings"""
    # Start processing in background
    background_tasks.add_task(process_user_games_for_rag, db, user.user_id, 100)
    
    return {
        "message": "RAG processing started in background",
        "status": "processing"
    }

@api_router.get("/rag/status")
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


# ============================================
# BLUNDER REDUCTION SYSTEM ENDPOINTS
# ============================================

@api_router.get("/focus")
async def get_focus_page_data(user: User = Depends(get_current_user)):
    """
    Get data for the Focus page (TODAY - What to focus on NOW)
    
    Returns:
    - ONE dominant weakness
    - ONE mission (scaled by rating tier)
    - Opening Guidance (what's working, what to pause)
    - Rating impact estimate
    """
    # Get analyses
    analyses = await db.game_analyses.find(
        {"user_id": user.user_id}
    ).sort("created_at", -1).limit(50).to_list(50)
    
    # Get more games for opening guidance (need at least 4 per opening)
    games = await db.games.find(
        {"user_id": user.user_id},
        {"_id": 0, "game_id": 1, "opening": 1, "pgn": 1, "user_color": 1, "result": 1, "date": 1}
    ).sort("date", -1).limit(100).to_list(100)
    
    # Extract user's rating from recent games
    user_rating = None
    for game in games[:10]:
        pgn = game.get("pgn", "")
        user_color = game.get("user_color", "white")
        
        import re
        if user_color == "white":
            match = re.search(r'\[WhiteElo "(\d+)"\]', pgn)
        else:
            match = re.search(r'\[BlackElo "(\d+)"\]', pgn)
        
        if match:
            user_rating = int(match.group(1))
            break
    
    focus_data = get_focus_data(analyses, games, user_rating=user_rating)
    
    return focus_data


@api_router.get("/coach-review")
async def get_coach_review_data(user: User = Depends(get_current_user)):
    """
    Get personalized coach review of user's last game.
    
    This endpoint acts like a personal chess coach reviewing the student's most recent game:
    - Did they follow our opening suggestions?
    - Are they fixing the mistakes we identified?
    - Where did they improve? Where do they still struggle?
    - Personalized, factual feedback based on real data
    
    Returns:
    - Coach's personalized message
    - Performance comparison (vs their average)
    - Opening check (did they play what we suggested?)
    - Improvement highlights
    - Areas of concern
    """
    review_data = await get_coach_game_review(db, user.user_id, call_llm)
    
    if review_data.get("has_review") and review_data.get("facts"):
        # Add highlights and concerns
        review_data["highlights"] = get_improvement_highlights(review_data["facts"])
        review_data["concerns"] = get_concern_areas(review_data["facts"])
    
    return review_data


@api_router.get("/discipline-check")
async def get_discipline_check_data(user: User = Depends(get_current_user)):
    """
    Get Discipline Check data for user's last game.
    
    This is a sharp, data-driven accountability check:
    - Did you follow opening advice?
    - Did you maintain composure when winning?
    - Decision Stability metric
    - Evidence-based verdict (no fluff)
    
    Returns compact card-based data with deterministic metrics.
    """
    return await get_discipline_check(db, user.user_id)


@api_router.get("/journey/v2")
async def get_journey_page_data(user: User = Depends(get_current_user)):
    """
    Get data for the Journey page (TREND - How you're evolving)
    
    Returns:
    - Weakness ranking (not equal badges)
    - Win-state analysis
    - Mistake heatmap
    - Identity profile
    - Milestones
    """
    # Get analyses
    analyses = await db.game_analyses.find(
        {"user_id": user.user_id}
    ).sort("created_at", -1).limit(15).to_list(15)
    
    games = await db.games.find(
        {"user_id": user.user_id}
    ).sort("date", -1).limit(15).to_list(15)
    
    # Get existing badge data
    badge_data = await calculate_all_badges(db, user.user_id)
    
    journey_data = get_journey_data(analyses, games, badge_data)
    
    return journey_data


@api_router.get("/lab/{game_id}")
async def get_lab_page_data(game_id: str, user: User = Depends(get_current_user)):
    """
    Get data for the Lab page (DETAIL - What actually happened)
    
    Returns:
    - Core lesson of the game
    - Evidence-based game strategy
    - Full analysis data
    - Similar games (Behavior Memory)
    """
    analysis = await db.game_analyses.find_one({
        "game_id": game_id,
        "user_id": user.user_id
    })
    
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    
    # Get game data for metadata
    game = await db.games.find_one({
        "game_id": game_id,
        "user_id": user.user_id
    })
    
    # Remove MongoDB _id
    if "_id" in analysis:
        del analysis["_id"]
    if game and "_id" in game:
        del game["_id"]
    
    lab_data = get_lab_data(analysis, game)
    
    # Add similar games (Behavior Memory)
    all_analyses = await db.game_analyses.find(
        {"user_id": user.user_id},
        {"_id": 0}
    ).to_list(50)
    
    all_games = await db.games.find(
        {"user_id": user.user_id},
        {"_id": 0, "game_id": 1, "user_color": 1, "white_player": 1, "black_player": 1, "result": 1, "imported_at": 1}
    ).to_list(50)
    
    similar_games = find_similar_pattern_games(analysis, all_analyses, all_games)
    lab_data["similar_games"] = similar_games
    
    return lab_data


class MistakeExplanationRequest(BaseModel):
    """Request for on-demand mistake explanation"""
    fen_before: str
    move: str
    best_move: str
    cp_loss: int
    user_color: str
    move_number: Optional[int] = None


@api_router.post("/explain-mistake")
async def explain_mistake(req: MistakeExplanationRequest, user: User = Depends(get_current_user)):
    """
    Generate an educational explanation for a specific mistake.
    
    This endpoint:
    1. Uses deterministic chess rules to identify WHAT went wrong
    2. Uses GPT to write a human-readable explanation of WHY
    
    GPT does NOT analyze chess - it only writes commentary based on our analysis.
    """
    move_data = {
        "fen_before": req.fen_before,
        "move": req.move,
        "best_move": req.best_move,
        "cp_loss": req.cp_loss,
        "user_color": req.user_color,
        "move_number": req.move_number
    }
    
    try:
        # Generate the explanation (uses LLM for commentary)
        explanation = await generate_mistake_explanation(move_data, call_llm)
        return explanation
    except Exception as e:
        logger.error(f"Error generating mistake explanation: {e}")
        # Return a fallback explanation based on templates
        analysis = analyze_mistake_position(
            req.fen_before, req.move, req.best_move, req.cp_loss, req.user_color
        )
        return {
            "explanation": get_quick_explanation(
                analysis.get("mistake_type", "inaccuracy"),
                analysis.get("details", {})
            ),
            "mistake_type": analysis.get("mistake_type", "inaccuracy"),
            "short_label": "Mistake",
            "thinking_habit": None,
            "severity": analysis.get("severity", "minor"),
            "phase": analysis.get("phase", "middlegame"),
            "details": analysis.get("details", {})
        }


@api_router.get("/positional-insight/{structure_id}")
async def get_structure_deep_dive(structure_id: str, user: User = Depends(get_current_user)):
    """
    Get detailed positional insight for a specific pawn structure.
    
    Returns complete knowledge base entry with:
    - Plans for both sides
    - Typical errors
    - Conversion patterns
    - Key squares and piece placement
    """
    try:
        from positional_coaching_service import get_structure_deep_dive as get_deep_dive
        deep_dive = get_deep_dive(structure_id, "white")  # Color context added dynamically
        
        if not deep_dive:
            raise HTTPException(status_code=404, detail="Structure not found in knowledge base")
        
        return deep_dive
    except ImportError:
        raise HTTPException(status_code=500, detail="Positional coaching service not available")


@api_router.get("/knowledge-base/structures")
async def get_all_structures(user: User = Depends(get_current_user)):
    """
    Get summary of all pawn structures in the knowledge base.
    """
    try:
        from positional_coaching_service import get_all_structures_summary
        return {"structures": get_all_structures_summary()}
    except ImportError:
        raise HTTPException(status_code=500, detail="Knowledge base not available")


@api_router.get("/knowledge-base/imbalances")
async def get_all_imbalances(user: User = Depends(get_current_user)):
    """
    Get summary of all strategic imbalances in the knowledge base.
    """
    try:
        from positional_coaching_service import get_all_imbalances_summary
        return {"imbalances": get_all_imbalances_summary()}
    except ImportError:
        raise HTTPException(status_code=500, detail="Knowledge base not available")


@api_router.get("/weakness-ranking")
async def get_weakness_ranking(user: User = Depends(get_current_user)):
    """
    Get dominant weakness ranking.
    
    Returns:
    - #1 Rating Killer
    - Secondary Weakness
    - Stable Strength
    """
    analyses = await db.game_analyses.find(
        {"user_id": user.user_id}
    ).sort("created_at", -1).limit(15).to_list(15)
    
    return get_dominant_weakness_ranking(analyses)


@api_router.get("/win-state")
async def get_win_state(user: User = Depends(get_current_user)):
    """
    Get win-state analysis.
    
    Returns when blunders happen:
    - When winning (with evidence)
    - When equal (with evidence)
    - When losing (with evidence)
    """
    analyses = await db.game_analyses.find(
        {"user_id": user.user_id}
    ).sort("created_at", -1).limit(15).to_list(15)
    
    games = await db.games.find(
        {"user_id": user.user_id}
    ).sort("date", -1).limit(15).to_list(15)
    
    # Remove MongoDB _id
    for game in games:
        if "_id" in game:
            del game["_id"]
    
    return get_win_state_analysis(analyses, games)


@api_router.get("/heatmap")
async def get_heatmap(user: User = Depends(get_current_user)):
    """
    Get mistake heatmap data.
    
    Returns:
    - Squares where mistakes occurred
    - Board region analysis
    - Hot squares
    """
    analyses = await db.game_analyses.find(
        {"user_id": user.user_id}
    ).sort("created_at", -1).limit(15).to_list(15)
    
    return get_mistake_heatmap(analyses)


class DrillRequest(BaseModel):
    """Request for drill positions"""
    pattern: Optional[str] = None  # Behavioral pattern to filter by
    state: Optional[str] = None  # Game state: "winning", "equal", "losing"
    limit: int = 5


@api_router.post("/drill/positions")
async def get_drill_positions_endpoint(req: DrillRequest, user: User = Depends(get_current_user)):
    """
    Get positions for Pattern Drill Mode.
    
    Returns positions where user made mistakes, for training.
    Filter by:
    - pattern: Behavioral pattern (e.g., "attacks_before_checking_threats")
    - state: Game state when blunder occurred ("winning", "equal", "losing")
    """
    analyses = await db.game_analyses.find(
        {"user_id": user.user_id}
    ).sort("created_at", -1).limit(20).to_list(20)
    
    games = await db.games.find(
        {"user_id": user.user_id}
    ).sort("date", -1).limit(20).to_list(20)
    
    # Remove MongoDB _id
    for game in games:
        if "_id" in game:
            del game["_id"]
    
    positions = get_drill_positions(
        analyses, 
        games, 
        pattern=req.pattern, 
        state=req.state, 
        limit=req.limit
    )
    
    return {
        "positions": positions,
        "total": len(positions),
        "pattern": req.pattern,
        "state": req.state
    }


@api_router.get("/rating-impact")
async def get_rating_impact(user: User = Depends(get_current_user)):
    """
    Get rating impact estimate.
    
    Returns:
    - Potential rating gain if dominant weakness fixed
    - Confidence level
    """
    analyses = await db.game_analyses.find(
        {"user_id": user.user_id}
    ).sort("created_at", -1).limit(15).to_list(15)
    
    return estimate_rating_impact(analyses)


@api_router.get("/identity")
async def get_identity(user: User = Depends(get_current_user)):
    """
    Get chess identity profile.
    
    Returns:
    - Identity label (e.g., "Aggressive but careless")
    - Description
    """
    analyses = await db.game_analyses.find(
        {"user_id": user.user_id}
    ).sort("created_at", -1).limit(15).to_list(15)
    
    return get_identity_profile(analyses)


@api_router.get("/mission")
async def get_current_mission(user: User = Depends(get_current_user)):
    """
    Get current mission based on weakness + rating tier.
    
    Mission Engine - 3 Layer Architecture:
    Layer 1: Weakness Type → Determines THEME
    Layer 2: Rating Tier → Adjusts DIFFICULTY  
    Layer 3: Mission Difficulty → Actual challenge
    """
    analyses = await db.game_analyses.find(
        {"user_id": user.user_id}
    ).sort("created_at", -1).limit(15).to_list(15)
    
    # Get user's rating from recent games
    user_rating = None
    recent_games = await db.games.find(
        {"user_id": user.user_id, "is_analyzed": True}
    ).sort("imported_at", -1).limit(5).to_list(5)
    
    for game in recent_games:
        pgn = game.get("pgn", "")
        user_color = game.get("user_color", "white")
        
        # Extract user's rating from PGN
        import re
        if user_color == "white":
            match = re.search(r'\[WhiteElo "(\d+)"\]', pgn)
        else:
            match = re.search(r'\[BlackElo "(\d+)"\]', pgn)
        
        if match:
            user_rating = int(match.group(1))
            break
    
    return get_mission(analyses, user_rating=user_rating)


@api_router.get("/milestones")
async def get_milestones(user: User = Depends(get_current_user)):
    """
    Get achievement milestones.
    
    Returns list of achieved and available milestones.
    """
    analyses = await db.game_analyses.find(
        {"user_id": user.user_id}
    ).sort("created_at", -1).limit(50).to_list(50)
    
    # Get user stats for milestone tracking
    user_stats = await db.user_stats.find_one({"user_id": user.user_id})
    
    return {
        "achieved": check_milestones(analyses, user_stats),
        "total_games": len(analyses)
    }


# ============== NOTIFICATION ENDPOINTS ==============

@api_router.get("/notifications")
async def get_notifications(
    unread_only: bool = False,
    limit: int = 20,
    user: User = Depends(get_current_user)
):
    """
    Get user's notifications.
    """
    notifications = await get_user_notifications(db, user.user_id, unread_only, limit)
    unread_count = await get_unread_count(db, user.user_id)
    
    return {
        "notifications": notifications,
        "unread_count": unread_count
    }


@api_router.post("/notifications/read")
async def mark_notifications_read(
    notification_id: str = None,
    user: User = Depends(get_current_user)
):
    """
    Mark notification(s) as read.
    If notification_id is provided, marks only that notification.
    Otherwise marks all as read.
    """
    success = await mark_notification_read(db, user.user_id, notification_id)
    return {"success": success}


@api_router.post("/notifications/{notification_id}/dismiss")
async def dismiss_user_notification(
    notification_id: str,
    user: User = Depends(get_current_user)
):
    """
    Dismiss a notification.
    """
    success = await dismiss_notification(db, user.user_id, notification_id)
    return {"success": success}


@api_router.get("/notifications/push-payload/{notification_id}")
async def get_notification_push_payload(
    notification_id: str,
    user: User = Depends(get_current_user)
):
    """
    Get push notification payload for browser Notification API.
    """
    from bson import ObjectId
    notification = await db.notifications.find_one(
        {"_id": ObjectId(notification_id), "user_id": user.user_id},
        {"_id": 0}
    )
    
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    
    notification["id"] = notification_id
    return get_push_notification_payload(notification)


# ============== SUBSCRIPTION/PLAN ENDPOINTS ==============

@api_router.get("/subscription")
async def get_subscription_info(user: User = Depends(get_current_user)):
    """
    Get user's subscription/plan information.
    """
    return await get_effective_plan(db, user.user_id)


@api_router.post("/subscription/upgrade")
async def upgrade_subscription(user: User = Depends(get_current_user)):
    """
    Upgrade user to Pro plan.
    NOTE: This is a mock endpoint. Real implementation would involve payment.
    """
    success = await upgrade_to_pro(db, user.user_id)
    if success:
        return {"success": True, "message": "Upgraded to Pro!", "plan": "pro"}
    return {"success": False, "message": "Failed to upgrade"}


@api_router.get("/subscription/can-analyze")
async def check_can_analyze(user: User = Depends(get_current_user)):
    """
    Check if user can analyze another game.
    """
    return await can_analyze_game(db, user.user_id)


# ============== AUTO-COACH ENDPOINTS ==============

@api_router.get("/coach/commentary/{game_id}")
async def get_coach_commentary(game_id: str, user: User = Depends(get_current_user)):
    """
    Get or generate coaching commentary for a game.
    """
    # Check if user has LLM commentary access
    has_access = await has_feature_access(db, user.user_id, "llm_commentary")
    
    if not has_access:
        return {
            "commentary": None,
            "access_denied": True,
            "message": "Upgrade to Pro for AI coaching commentary"
        }
    
    # Get analysis
    analysis = await db.game_analyses.find_one(
        {"game_id": game_id, "user_id": user.user_id},
        {"_id": 0}
    )
    
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    
    # Check if commentary already exists
    if analysis.get("coach_commentary"):
        return {
            "commentary": analysis["coach_commentary"],
            "generated_at": analysis.get("coach_commentary_generated_at"),
            "cached": True
        }
    
    # Get game data
    game = await db.games.find_one(
        {"game_id": game_id, "user_id": user.user_id},
        {"_id": 0}
    )
    
    # Generate commentary
    commentary = await generate_and_save_commentary(db, analysis, game)
    
    if commentary:
        return {
            "commentary": commentary,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "cached": False
        }
    
    return {
        "commentary": None,
        "error": "Failed to generate commentary"
    }


@api_router.post("/coach/trigger-analysis/{game_id}")
async def trigger_auto_coach_analysis(
    game_id: str,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user)
):
    """
    Trigger auto-coach analysis for a specific game.
    This generates deterministic summary + LLM commentary + notification.
    """
    # Check analysis limit
    can_do = await can_analyze_game(db, user.user_id)
    if not can_do["allowed"]:
        return can_do
    
    # Get analysis and game
    analysis = await db.game_analyses.find_one(
        {"game_id": game_id, "user_id": user.user_id},
        {"_id": 0}
    )
    
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    
    game = await db.games.find_one(
        {"game_id": game_id, "user_id": user.user_id},
        {"_id": 0}
    )
    
    # Build deterministic summary
    summary = build_deterministic_summary(analysis, game)
    
    # Generate notification message
    notification_message = get_quick_notification_message(summary)
    
    # Create notification
    await notify_game_analyzed(
        db,
        user.user_id,
        game_id,
        notification_message,
        summary["result"]
    )
    
    # Generate LLM commentary in background if user has access
    has_llm_access = await has_feature_access(db, user.user_id, "llm_commentary")
    if has_llm_access:
        background_tasks.add_task(generate_and_save_commentary, db, analysis, game)
    
    # Increment analysis count
    await increment_analysis_count(db, user.user_id)
    
    return {
        "success": True,
        "summary": summary,
        "notification": notification_message,
        "llm_commentary_queued": has_llm_access
    }


# ==================== RE-ANALYSIS QUEUE ROUTES ====================

@api_router.post("/games/{game_id}/reanalyze")
async def reanalyze_game(
    game_id: str,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user)
):
    """
    Queue a game for re-analysis. This is for games that were imported
    but not properly analyzed.
    """
    # Verify game exists and belongs to user
    game = await db.games.find_one(
        {"game_id": game_id, "user_id": user.user_id},
        {"_id": 0}
    )
    
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    
    # Check if already in queue
    existing_queue = await db.analysis_queue.find_one(
        {"game_id": game_id, "status": {"$in": ["pending", "processing"]}}
    )
    
    if existing_queue:
        return {
            "success": True,
            "status": "already_queued",
            "message": "Game is already queued for analysis"
        }
    
    # Add to queue (or update existing entry)
    queue_item = {
        "game_id": game_id,
        "user_id": user.user_id,
        "status": "pending",
        "queued_at": datetime.now(timezone.utc),
        "priority": 1  # User-requested re-analysis gets priority
    }
    
    # Use upsert to avoid duplicate entries - update existing or create new
    await db.analysis_queue.update_one(
        {"game_id": game_id, "user_id": user.user_id},
        {"$set": queue_item},
        upsert=True
    )
    
    # Update game status - set is_analyzed to False so it shows in queue
    await db.games.update_one(
        {"game_id": game_id},
        {"$set": {"analysis_status": "queued", "is_analyzed": False}}
    )
    
    # NOTE: Analysis is now handled by the separate analysis_worker.py process
    # The worker polls the analysis_queue collection and processes pending jobs
    # This keeps the web server fast and responsive
    
    logger.info(f"Game {game_id} queued for analysis (worker will process)")
    
    return {
        "success": True,
        "status": "queued",
        "message": "Game queued for analysis. The analysis worker will process it shortly."
    }


@api_router.get("/games/{game_id}/analysis-status")
async def get_game_analysis_status(game_id: str, user: User = Depends(get_current_user)):
    """Get the current analysis status for a specific game"""
    game = await db.games.find_one(
        {"game_id": game_id, "user_id": user.user_id},
        {"_id": 0, "is_analyzed": 1, "analysis_status": 1}
    )
    
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    
    # Check queue for progress info
    queue_item = await db.analysis_queue.find_one(
        {"game_id": game_id},
        {"_id": 0, "status": 1, "created_at": 1}
    )
    
    if game.get("is_analyzed"):
        return {"status": "analyzed"}
    
    if queue_item:
        return {
            "status": queue_item.get("status", "unknown"),
            "queued_at": queue_item.get("created_at")
        }
    
    return {"status": "not_analyzed"}


@api_router.get("/analysis-queue")
async def get_analysis_queue_status(user: User = Depends(get_current_user)):
    """Get all games in the analysis queue for the current user"""
    queue_items = await db.analysis_queue.find(
        {"user_id": user.user_id, "status": {"$in": ["pending", "processing"]}},
        {"_id": 0}
    ).sort("created_at", 1).to_list(50)
    
    return {
        "queue": queue_items,
        "count": len(queue_items)
    }


# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Note: Background sync scheduler and lifespan events are defined at the top of this file
