from fastapi import FastAPI, APIRouter, HTTPException, Request, Response, Depends, BackgroundTasks, Body
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

# Import Pattern Context Service for longitudinal tracking
from pattern_context_service import (
    build_pattern_history,
    get_pattern_context_for_mistake,
    get_game_pattern_summary,
    extract_mistake_patterns,
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

# === REFLECTION ENGINE V1 IMPORTS ===
from reflect_constants import (
    REFLECT_RULES_VERSION,
    get_intent_options,
    get_confidence_options,
    Intent,
    Confidence,
    RewardEventType,
)
from quick_tag_registry import generate_quick_tags
from awareness_gap_rules import evaluate_awareness_gap
from adaptive_profile_engine import get_adaptive_profile, get_adaptive_profile_sync
from reward_message_service import get_reward_message, get_post_loss_message, generate_weekly_proof
from reflect_predicates import BoardFacts

# === MISSION ENGINE IMPORTS ===
from mission_generation_service import (
    generate_daily_mission,
    start_mission,
    complete_mission,
    PATTERN_FOCUS_MAP,
)

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
_quick_sync_task = None

# Sync status tracking
_sync_status = {
    "last_sync_at": None,
    "next_sync_at": None,
    "is_syncing": False,
    "games_found_last_sync": 0
}

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

# Quick sync loop - checks for new games every 5 minutes
async def quick_sync_loop():
    """
    Real-time game monitoring - checks for new games every 5 minutes.
    Only syncs games played in the last 30 minutes to catch recent games quickly.
    """
    global _sync_status
    from journey_service import sync_user_games
    
    # Wait 1 minute before first check (let app stabilize)
    _sync_status["next_sync_at"] = (datetime.now(timezone.utc) + timedelta(seconds=60)).isoformat()
    await asyncio.sleep(60)
    
    while True:
        try:
            _sync_status["is_syncing"] = True
            _sync_status["last_sync_at"] = datetime.now(timezone.utc).isoformat()
            logger.info("Quick sync: Checking for new games...")
            
            # Get all users with linked chess accounts
            users = await db.users.find({
                "$or": [
                    {"chess_com_username": {"$exists": True, "$ne": None}},
                    {"lichess_username": {"$exists": True, "$ne": None}}
                ]
            }, {"_id": 0}).to_list(100)
            
            total_synced = 0
            for user_doc in users:
                try:
                    # Quick sync - only fetch very recent games
                    count = await sync_user_games(db, user_doc["user_id"], user_doc)
                    total_synced += count
                except Exception as e:
                    logger.error(f"Quick sync error for user {user_doc['user_id']}: {e}")
            
            _sync_status["games_found_last_sync"] = total_synced
            _sync_status["is_syncing"] = False
            
            if total_synced > 0:
                logger.info(f"Quick sync: Found and queued {total_synced} new games")
            else:
                logger.debug("Quick sync: No new games found")
                
        except Exception as e:
            logger.error(f"Quick sync loop error: {e}")
            _sync_status["is_syncing"] = False
        
        # Calculate next sync time
        _sync_status["next_sync_at"] = (datetime.now(timezone.utc) + timedelta(seconds=QUICK_SYNC_INTERVAL_SECONDS)).isoformat()
        
        # Wait 5 minutes before next check
        await asyncio.sleep(QUICK_SYNC_INTERVAL_SECONDS)

# Lifespan context manager (replaces deprecated on_event)
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for FastAPI.
    Handles startup and shutdown events.
    """
    global _background_sync_task, _quick_sync_task
    
    # === STARTUP ===
    # Start the background sync loop (every 6 hours)
    _background_sync_task = asyncio.create_task(background_sync_loop())
    logger.info("Background sync scheduler started (6 hour interval)")
    
    # Start quick sync loop (every 5 minutes for real-time game monitoring)
    _quick_sync_task = asyncio.create_task(quick_sync_loop())
    logger.info("Quick sync started (5 minute interval for real-time monitoring)")
    
    yield  # App runs here
    
    # === SHUTDOWN ===
    # Cancel background tasks
    if _background_sync_task:
        _background_sync_task.cancel()
        try:
            await _background_sync_task
        except asyncio.CancelledError:
            pass
    
    if _quick_sync_task:
        _quick_sync_task.cancel()
        try:
            await _quick_sync_task
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
    
    # Validate that the username matches user's linked account
    user_doc = await db.users.find_one({"user_id": user.user_id})
    if user_doc:
        linked_chesscom = user_doc.get("chess_com_username") or user_doc.get("chesscom_username")
        linked_lichess = user_doc.get("lichess_username")
        
        if platform == "chess.com" and linked_chesscom:
            if linked_chesscom.lower() != username.lower():
                raise HTTPException(
                    status_code=400, 
                    detail=f"You can only import games from your linked Chess.com account ({linked_chesscom}). Unlink first to change accounts."
                )
        elif platform == "lichess" and linked_lichess:
            if linked_lichess.lower() != username.lower():
                raise HTTPException(
                    status_code=400,
                    detail=f"You can only import games from your linked Lichess account ({linked_lichess}). Unlink first to change accounts."
                )
    
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
        
        # Only mark as analyzed if analysis was complete and valid
        # If Stockfish failed, we have incomplete data
        if not analysis_incomplete:
            await db.games.update_one(
                {"game_id": req.game_id},
                {"$set": {
                    "is_analyzed": True,
                    "analysis_status": "completed"
                }}
            )
        else:
            # Mark as incomplete - needs re-analysis
            await db.games.update_one(
                {"game_id": req.game_id},
                {"$set": {
                    "is_analyzed": False,
                    "analysis_status": "incomplete",
                    "analysis_error": "Stockfish analysis failed or returned invalid data"
                }}
            )
            logger.warning(f"Game {req.game_id} marked as incomplete - Stockfish analysis failed")
        
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
    Only ONE account per platform can be linked at a time.
    """
    platform = req.platform.lower()
    username = req.username.strip()
    
    if platform not in ["chess.com", "lichess"]:
        raise HTTPException(status_code=400, detail="Invalid platform. Use 'chess.com' or 'lichess'")
    
    if not username:
        raise HTTPException(status_code=400, detail="Username is required")
    
    # Check if user already has a linked account for this platform
    user_doc = await db.users.find_one({"user_id": user.user_id})
    if user_doc:
        existing_chesscom = user_doc.get("chess_com_username") or user_doc.get("chesscom_username")
        existing_lichess = user_doc.get("lichess_username")
        
        if platform == "chess.com" and existing_chesscom:
            if existing_chesscom.lower() != username.lower():
                raise HTTPException(
                    status_code=400, 
                    detail=f"You already have a linked Chess.com account ({existing_chesscom}). Please unlink it first before linking a new account."
                )
        elif platform == "lichess" and existing_lichess:
            if existing_lichess.lower() != username.lower():
                raise HTTPException(
                    status_code=400,
                    detail=f"You already have a linked Lichess account ({existing_lichess}). Please unlink it first before linking a new account."
                )
    
    # Validate account exists
    if platform == "chess.com":
        games = await fetch_recent_chesscom_games(username)
        if not games and games != []:
            raise HTTPException(status_code=404, detail=f"Chess.com user '{username}' not found")
        update_field = "chess_com_username"  # Standardized field name
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
        {"_id": 0, "chess_com_username": 1, "chesscom_username": 1, "lichess_username": 1}
    )
    
    if not user_doc:
        return {"chess_com": None, "lichess": None}
    
    # Support both field names for backward compatibility
    chess_com = user_doc.get("chess_com_username") or user_doc.get("chesscom_username")
    
    return {
        "chess_com": chess_com,
        "lichess": user_doc.get("lichess_username")
    }


class UnlinkAccountRequest(BaseModel):
    platform: str  # "chess.com" or "lichess"

@api_router.post("/journey/unlink-account")
async def unlink_chess_account(req: UnlinkAccountRequest, user: User = Depends(get_current_user)):
    """
    Unlink a Chess.com or Lichess account.
    This does NOT delete imported games, but stops future syncing.
    """
    platform = req.platform.lower()
    
    if platform not in ["chess.com", "lichess"]:
        raise HTTPException(status_code=400, detail="Invalid platform. Use 'chess.com' or 'lichess'")
    
    if platform == "chess.com":
        # Remove both field variants for safety
        await db.users.update_one(
            {"user_id": user.user_id},
            {"$unset": {"chess_com_username": "", "chesscom_username": ""}}
        )
    else:
        await db.users.update_one(
            {"user_id": user.user_id},
            {"$unset": {"lichess_username": ""}}
        )
    
    return {
        "message": f"{platform} account unlinked successfully",
        "platform": platform
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

@api_router.get("/sync-status")
async def get_sync_status(user: User = Depends(get_current_user)):
    """
    Get the current game sync status including countdown to next sync.
    Used by frontend to display sync timer.
    """
    now = datetime.now(timezone.utc)
    
    # Calculate seconds until next sync
    next_sync_in_seconds = 0
    if _sync_status.get("next_sync_at"):
        try:
            next_sync = datetime.fromisoformat(_sync_status["next_sync_at"].replace('Z', '+00:00'))
            diff = (next_sync - now).total_seconds()
            next_sync_in_seconds = max(0, int(diff))
        except:
            next_sync_in_seconds = QUICK_SYNC_INTERVAL_SECONDS
    
    return {
        "is_syncing": _sync_status.get("is_syncing", False),
        "last_sync_at": _sync_status.get("last_sync_at"),
        "next_sync_in_seconds": next_sync_in_seconds,
        "sync_interval_seconds": QUICK_SYNC_INTERVAL_SECONDS,
        "games_found_last_sync": _sync_status.get("games_found_last_sync", 0)
    }

# ==================== REFLECTION ROUTES ====================

from reflect_service import (
    get_games_needing_reflection,
    get_pending_reflection_count,
    get_game_moments,
    process_reflection,
    mark_game_reflected,
    generate_contextual_tags
)

@api_router.get("/reflect/pending")
async def get_pending_reflections(user: User = Depends(get_current_user)):
    """Get games that need reflection - most recent first."""
    games = await get_games_needing_reflection(db, user.user_id, limit=5)
    return {"games": games}

@api_router.get("/reflect/pending/count")
async def get_reflection_count(user: User = Depends(get_current_user)):
    """Get count of games needing reflection for badge display."""
    count = await get_pending_reflection_count(db, user.user_id)
    return {"count": count}

@api_router.get("/reflect/game/{game_id}/moments")
async def get_reflection_moments(game_id: str, user: User = Depends(get_current_user)):
    """Get critical moments from a game for reflection."""
    moments = await get_game_moments(db, user.user_id, game_id)
    return {"moments": moments}

class ReflectionSubmission(BaseModel):
    game_id: str
    moment_index: int
    moment_fen: str
    user_thought: str
    user_move: str
    best_move: str
    eval_change: float = 0.0
    move_number: Optional[int] = None  # For tracking reflected moments

@api_router.post("/reflect/submit")
async def submit_reflection(data: ReflectionSubmission, user: User = Depends(get_current_user)):
    """Submit a reflection for a critical moment."""
    result = await process_reflection(
        db,
        user.user_id,
        data.game_id,
        data.moment_index,
        data.moment_fen,
        data.user_thought,
        data.user_move,
        data.best_move,
        data.eval_change,
        data.move_number
    )
    return result

@api_router.post("/reflect/game/{game_id}/complete")
async def complete_game_reflection(game_id: str, user: User = Depends(get_current_user)):
    """Mark a game as fully reflected on."""
    result = await mark_game_reflected(db, user.user_id, game_id)
    return result


class ContextualTagsRequest(BaseModel):
    """Request for generating contextual quick-tags based on position."""
    fen: str
    user_move: str
    best_move: str
    eval_change: float = 0.0


@api_router.post("/reflect/moment/contextual-tags")
async def get_contextual_tags(data: ContextualTagsRequest, user: User = Depends(get_current_user)):
    """
    Generate contextual quick-tag options based on the actual chess position.
    
    Uses verified position analysis to infer what the user might have been thinking.
    Only returns tags that can be genuinely inferred - no generic placeholders.
    """
    result = generate_contextual_tags(
        data.fen,
        data.user_move,
        data.best_move,
        data.eval_change
    )
    return result


@api_router.get("/training/data-driven")
async def get_data_driven_training(user: User = Depends(get_current_user)):
    """
    Get training focus based purely on YOUR data (mistakes + reflections).
    This bypasses the rating-based curriculum.
    """
    from reflection_training_service import get_data_driven_training_focus
    result = await get_data_driven_training_focus(db, user.user_id)
    return result

@api_router.get("/training/reflection-impact")
async def get_reflection_impact(user: User = Depends(get_current_user)):
    """Get how reflections have impacted training focus."""
    impact = await db.reflection_impacts.find_one(
        {"user_id": user.user_id},
        {"_id": 0}
    )
    if not impact:
        return {
            "total_reflections": 0,
            "layer_boosts": {},
            "pattern_counts": {},
            "message": "No reflections yet - your reflections will shape your training!"
        }
    return impact

@api_router.get("/training/should-override")
async def check_training_override(user: User = Depends(get_current_user)):
    """Check if reflection data suggests overriding the rating-based curriculum."""
    from reflection_training_service import should_override_curriculum
    result = await should_override_curriculum(db, user.user_id)
    return result

class MomentExplanationRequest(BaseModel):
    fen: str
    user_move: str
    best_move: str
    eval_change: float = 0.0
    type: str = "mistake"

@api_router.post("/reflect/explain-moment")
async def explain_moment(data: MomentExplanationRequest, user: User = Depends(get_current_user)):
    """
    Get a coach-style explanation of what happened at this moment.
    Uses VERIFIED position analysis - no LLM hallucinations.
    """
    from position_analysis_service import (
        generate_verified_insight,
        build_llm_prompt_with_facts,
        validate_llm_output
    )
    from llm_service import call_llm
    
    try:
        # Step 1: Generate verified insights from actual position analysis
        verified = generate_verified_insight(
            data.fen,
            data.user_move,
            data.best_move,
            data.eval_change
        )
        
        # Step 2: Get LLM to elaborate on verified facts (optional enhancement)
        # Build prompt with ONLY verified facts
        prompt = build_llm_prompt_with_facts(
            data.fen,
            data.user_move,
            data.best_move,
            data.eval_change
        )
        
        try:
            response = await call_llm(
                system_message="You are a supportive chess coach. ONLY use the verified facts provided. Never make up piece locations.",
                user_message=prompt,
                model="gpt-4o-mini"
            )
            
            import json
            response_clean = response.strip()
            if response_clean.startswith("```json"):
                response_clean = response_clean[7:]
            if response_clean.startswith("```"):
                response_clean = response_clean[3:]
            if response_clean.endswith("```"):
                response_clean = response_clean[:-3]
            
            llm_result = json.loads(response_clean)
            
            # Step 3: Validate LLM output against position facts
            is_valid, errors = validate_llm_output(
                json.dumps(llm_result), 
                verified["position_facts"]
            )
            
            if is_valid:
                # LLM output is valid, use it
                return {
                    "impact": llm_result.get("impact", verified["verified_impact"]),
                    "better_plan": llm_result.get("better_plan", verified["verified_better_plan"]),
                    "verified": True
                }
            else:
                # LLM hallucinated, fall back to verified facts
                logger.warning(f"LLM validation failed: {errors}")
                return {
                    "impact": verified["verified_impact"],
                    "better_plan": verified["verified_better_plan"],
                    "verified": True,
                    "fallback": True
                }
                
        except Exception as llm_error:
            logger.error(f"LLM error: {llm_error}")
            # Fall back to verified analysis
            return {
                "impact": verified["verified_impact"],
                "better_plan": verified["verified_better_plan"],
                "verified": True,
                "fallback": True
            }
            
    except Exception as e:
        logger.error(f"Error analyzing moment: {e}")
        return {
            "impact": f"Your move {data.user_move} wasn't the best in this position.",
            "better_plan": f"The move {data.best_move} was stronger here.",
            "error": True
        }

# ==================== REFLECTION ENGINE V1 ROUTES ====================
# Deterministic, config-driven reflection system
# No LLM in critical path - rule-based only

class ReflectEngineTagsRequest(BaseModel):
    """Request for V1 quick tag generation"""
    fen: str
    user_move: str
    best_move: str
    mistake_category: str
    cp_loss: float = 0.0
    time_remaining_sec: Optional[int] = None
    move_number: int = 0

class ReflectSessionSubmitRequest(BaseModel):
    """Request to complete a reflection session"""
    game_id: str
    move_index: int
    fen: str
    user_move: str
    best_move: str
    mistake_category: str
    intent: str
    intent_confidence: str
    selected_quick_tags: List[str]
    auto_tag_candidates_shown: List[str] = []  # For analytics
    free_text: Optional[str] = ""
    cp_loss: float = 0.0
    time_remaining_sec: Optional[int] = None
    move_number: int = 0
    completed_in_seconds: int = 0  # Time to complete reflection
    game_ended_at: Optional[str] = None  # For freshness calculation

@api_router.get("/reflect/v1/profile")
async def get_reflection_profile(user: User = Depends(get_current_user)):
    """
    Get user's adaptive reflection profile.
    Frontend uses this to configure UX - no hardcoded values in React.
    """
    # Get user's rating
    user_doc = await db.users.find_one({"user_id": user.user_id})
    rating = user_doc.get("assessed_rating", 1200) if user_doc else 1200
    
    profile = await get_adaptive_profile(user.user_id, rating, db)
    profile["rule_version"] = REFLECT_RULES_VERSION
    
    return profile

@api_router.post("/reflect/v1/quick-tags")
async def get_quick_tags_v1(data: ReflectEngineTagsRequest, user: User = Depends(get_current_user)):
    """
    Generate quick tags using the V1 deterministic engine.
    Tags are config-driven, predicate-backed, and rating-adaptive.
    """
    # Get user's rating
    user_doc = await db.users.find_one({"user_id": user.user_id})
    rating = user_doc.get("assessed_rating", 1200) if user_doc else 1200
    
    result = generate_quick_tags(
        fen_before=data.fen,
        user_move=data.user_move,
        best_move=data.best_move,
        mistake_category=data.mistake_category,
        rating=rating,
        cp_loss=data.cp_loss,
        time_remaining_sec=data.time_remaining_sec,
        move_number=data.move_number,
    )
    
    # Add profile info for frontend
    profile = get_adaptive_profile_sync(rating)
    result["intent_options"] = profile["intent_options"]
    result["confidence_options"] = profile["confidence_options"]
    result["max_quick_tags"] = profile["max_quick_tags"]
    result["friction_budget_taps"] = profile["friction_budget_taps"]
    result["rule_version"] = REFLECT_RULES_VERSION
    
    return result

@api_router.post("/reflect/v1/submit")
async def submit_reflection_v1(data: ReflectSessionSubmitRequest, user: User = Depends(get_current_user)):
    """
    Submit a completed reflection session.
    Stores structured data, computes awareness gap, returns reward.
    """
    user_doc = await db.users.find_one({"user_id": user.user_id})
    rating = user_doc.get("assessed_rating", 1200) if user_doc else 1200
    
    # Compute awareness gap
    awareness_result = evaluate_awareness_gap(
        fen_before=data.fen,
        user_move=data.user_move,
        best_move=data.best_move,
        intent=data.intent,
        confidence=data.intent_confidence,
        selected_tags=data.selected_quick_tags,
        mistake_category=data.mistake_category,
        rating=rating,
        cp_loss=data.cp_loss,
        time_remaining_sec=data.time_remaining_sec,
        move_number=data.move_number,
    )
    
    # Build reflection session document
    reflection_id = f"r_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc)
    
    # Calculate freshness (hours since game ended)
    is_fresh = False
    hours_since_game = None
    if data.game_ended_at:
        try:
            game_time = datetime.fromisoformat(data.game_ended_at.replace("Z", "+00:00"))
            hours_since_game = (now - game_time).total_seconds() / 3600
            is_fresh = hours_since_game < 12  # Fresh if within 12 hours
        except:
            pass
    
    reflection_doc = {
        "reflection_id": reflection_id,
        "user_id": user.user_id,
        "game_id": data.game_id,
        "move_index": data.move_index,
        
        "mistake_category": data.mistake_category,
        "mistake_category_version": "v1",
        
        "intent": data.intent,
        "intent_confidence": data.intent_confidence,
        
        "selected_quick_tags": data.selected_quick_tags,
        "auto_tag_candidates_shown": data.auto_tag_candidates_shown,
        
        "awareness_gap_type": awareness_result["gap_type"],
        "awareness_gap_reason_codes": awareness_result["reason_codes"],
        "awareness_gap_rule_id": awareness_result.get("rule_id"),
        
        "free_text": data.free_text or "",
        "completed_in_seconds": data.completed_in_seconds,
        
        # Freshness tracking
        "is_fresh": is_fresh,
        "hours_since_game": hours_since_game,
        
        "rule_version": REFLECT_RULES_VERSION,
        "created_at": now.isoformat(),
        
        # Position data for replay
        "fen": data.fen,
        "user_move": data.user_move,
        "best_move": data.best_move,
        "cp_loss": data.cp_loss,
    }
    
    # Store reflection
    await db.reflection_sessions.insert_one(reflection_doc)
    
    # Get reward message
    # Determine which reward type based on reflection quality
    reward_event = RewardEventType.REFLECTION_COMPLETE
    
    # Fresh reflection gets special recognition
    if is_fresh and data.completed_in_seconds < 30:
        reward_event = RewardEventType.REFLECTION_CAPTURED_FAST
    elif data.intent_confidence == "guessing" and "not_sure" in data.selected_quick_tags:
        reward_event = RewardEventType.REFLECTION_HONEST_NOT_SURE
    elif awareness_result["gap_type"] == "confidence_gap":
        reward_event = RewardEventType.REFLECTION_CONFIDENCE_INSIGHT
    
    # Get recent messages for anti-repeat
    recent = await db.reward_events.find(
        {"user_id": user.user_id}
    ).sort("created_at", -1).limit(10).to_list(10)
    recent_ids = [r.get("message_id") for r in recent if r.get("message_id")]
    
    reward_message = get_reward_message(
        event_type=reward_event,
        rating=rating,
        context={"focus_label": awareness_result.get("focus_recommendation", "")},
        recent_message_ids=recent_ids,
    )
    
    # Store reward event
    if reward_message:
        await db.reward_events.insert_one({
            "event_id": f"e_{uuid.uuid4().hex[:12]}",
            "user_id": user.user_id,
            "event_type": reward_event.value,
            "source": "reflection",
            "payload": {
                "reflection_id": reflection_id,
                "gap_type": awareness_result["gap_type"],
            },
            "message_id": reward_message["message_id"],
            "created_at": now.isoformat(),
            "seen": False,
        })
    
    # Build next actions
    next_actions = [
        {"type": "next_moment", "label": "Next moment"},
    ]
    
    # If there's a focus recommendation, offer training
    if awareness_result.get("focus_recommendation"):
        next_actions.insert(0, {
            "type": "start_mission",
            "label": f"Train: {awareness_result['focus_recommendation']}",
            "focus": awareness_result["focus_recommendation"],
        })
    
    return {
        "reflection_status": "completed",
        "reflection_id": reflection_id,
        "awareness_result": {
            "type": awareness_result["gap_type"],
            "headline": awareness_result["headline"],
            "focus_recommendation": awareness_result.get("focus_recommendation"),
        },
        "coach_message": reward_message["text"] if reward_message else "Good. Reflection captured.",
        "next_actions": next_actions,
        "rule_version": REFLECT_RULES_VERSION,
        # Timing metrics
        "completed_in_seconds": data.completed_in_seconds,
        "is_fresh": is_fresh,
        "freshness_badge": "Fresh Memory" if is_fresh else None,
    }

# ==================== REWARD EVENT FEED ====================

@api_router.get("/rewards/feed")
async def get_reward_feed(limit: int = 20, user: User = Depends(get_current_user)):
    """
    Get user's recent reward events.
    Used for reward feed/history display.
    """
    events = await db.reward_events.find(
        {"user_id": user.user_id}
    ).sort("created_at", -1).limit(limit).to_list(limit)
    
    # Clean up for response
    result = []
    for event in events:
        result.append({
            "event_id": event.get("event_id"),
            "event_type": event.get("event_type"),
            "source": event.get("source"),
            "message_id": event.get("message_id"),
            "created_at": event.get("created_at"),
            "seen": event.get("seen", False),
        })
    
    # Count unseen
    unseen_count = sum(1 for e in result if not e["seen"])
    
    return {
        "events": result,
        "unseen_count": unseen_count,
        "total": len(result),
    }

@api_router.post("/rewards/mark-seen")
async def mark_rewards_seen(user: User = Depends(get_current_user)):
    """Mark all reward events as seen."""
    await db.reward_events.update_many(
        {"user_id": user.user_id, "seen": False},
        {"$set": {"seen": True}}
    )
    return {"status": "ok"}

@api_router.get("/rewards/stats")
async def get_reward_stats(user: User = Depends(get_current_user)):
    """
    Get reward statistics for the user.
    Used for weekly proof card and progress display.
    """
    # Get reflections for stats
    reflections = await db.reflection_sessions.find(
        {"user_id": user.user_id}
    ).sort("created_at", -1).limit(50).to_list(50)
    
    total_reflections = len(reflections)
    fresh_reflections = sum(1 for r in reflections if r.get("is_fresh"))
    avg_completion_time = 0
    if reflections:
        times = [r.get("completed_in_seconds", 0) for r in reflections if r.get("completed_in_seconds", 0) > 0]
        if times:
            avg_completion_time = sum(times) / len(times)
    
    # Intent distribution
    intent_counts = {}
    for r in reflections:
        intent = r.get("intent", "unknown")
        intent_counts[intent] = intent_counts.get(intent, 0) + 1
    
    # Tag usage
    tag_usage = {}
    for r in reflections:
        for tag in r.get("selected_quick_tags", []):
            tag_usage[tag] = tag_usage.get(tag, 0) + 1
    
    # Gap types
    gap_types = {}
    for r in reflections:
        gap = r.get("awareness_gap_type", "unknown")
        gap_types[gap] = gap_types.get(gap, 0) + 1
    
    return {
        "total_reflections": total_reflections,
        "fresh_reflections": fresh_reflections,
        "fresh_rate": fresh_reflections / total_reflections if total_reflections > 0 else 0,
        "avg_completion_time_sec": round(avg_completion_time, 1),
        "intent_distribution": intent_counts,
        "tag_usage": dict(sorted(tag_usage.items(), key=lambda x: x[1], reverse=True)[:10]),
        "gap_type_distribution": gap_types,
    }

@api_router.get("/rewards/post-loss-message")
async def get_post_loss_message_endpoint(game_id: str, user: User = Depends(get_current_user)):
    """
    Get post-loss recovery message for a specific game.
    Returns personalized, rating-adaptive messaging.
    """
    # Get user's profile for rating
    profile = await db.player_profiles.find_one({"user_id": user.user_id})
    rating = profile.get("estimated_rating", 1200) if profile else 1200
    
    # Get the game to check main pattern
    analysis = await db.game_analyses.find_one({"game_id": game_id, "user_id": user.user_id})
    
    # Find the main pattern from the game
    focus_label = "Critical Position Focus"  # Default
    minutes = 5
    
    if analysis:
        # Try to find the main mistake pattern
        blunders = analysis.get("stockfish_analysis", {}).get("move_evaluations", [])
        for move in blunders:
            eval_type = move.get("evaluation")
            if hasattr(eval_type, 'value'):
                eval_type = eval_type.value
            if eval_type in ["blunder", "mistake"]:
                # Use the first major mistake as focus
                thinking_pattern = move.get("thinking_pattern")
                if thinking_pattern:
                    focus_label = thinking_pattern.replace("_", " ").title()
                break
    
    # Get adaptive profile for this rating
    adaptive_profile = get_adaptive_profile_sync(rating)
    minutes = adaptive_profile.get("mission_minutes_target", 5)
    
    # Get the message
    message = get_post_loss_message(rating, focus_label, minutes)
    
    return message

# ==================== COACH HOME ROUTES ====================

@api_router.get("/coach/fresh-loss")
async def get_fresh_loss(user: User = Depends(get_current_user)):
    """
    Check if user has a fresh loss (within last 2 hours) that needs recovery.
    Returns the loss details and recommended recovery path.
    """
    from datetime import datetime, timezone, timedelta
    
    # Look for games in last 2 hours marked as loss
    two_hours_ago = datetime.now(timezone.utc) - timedelta(hours=2)
    
    recent_loss = await db.game_analyses.find_one(
        {
            "user_id": user.user_id,
            "result": "loss",
            "analyzed_at": {"$gte": two_hours_ago}
        },
        sort=[("analyzed_at", -1)]
    )
    
    if not recent_loss:
        return {"has_fresh_loss": False}
    
    # Get the main mistake pattern from this game
    focus_label = "Critical moment"
    blunders = recent_loss.get("stockfish_analysis", {}).get("move_evaluations", [])
    
    for move in blunders:
        eval_type = move.get("evaluation")
        if hasattr(eval_type, 'value'):
            eval_type = eval_type.value
        if eval_type in ["blunder", "mistake"]:
            thinking_pattern = move.get("thinking_pattern")
            if thinking_pattern:
                focus_label = thinking_pattern.replace("_", " ").title()
            break
    
    # Get user rating for adaptive timing
    profile = await db.player_profiles.find_one({"user_id": user.user_id})
    rating = profile.get("estimated_rating", 1200) if profile else 1200
    adaptive = get_adaptive_profile_sync(rating)
    minutes = adaptive.get("mission_minutes_target", 6)
    
    return {
        "has_fresh_loss": True,
        "game_id": str(recent_loss.get("game_id")),
        "focus_label": focus_label,
        "estimated_minutes": minutes,
        "opponent": recent_loss.get("opponent"),
        "time_since_loss_minutes": int((datetime.now(timezone.utc) - recent_loss.get("analyzed_at", datetime.now(timezone.utc))).total_seconds() / 60)
    }

@api_router.get("/coach/weekly-proof")
async def get_weekly_proof(user: User = Depends(get_current_user)):
    """
    Get weekly proof summary - wins, improvements, streaks.
    Used for the compact weekly proof card on Coach Home.
    """
    from datetime import datetime, timezone, timedelta
    
    one_week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    
    # Count wins this week
    wins = await db.game_analyses.count_documents({
        "user_id": user.user_id,
        "result": "win",
        "analyzed_at": {"$gte": one_week_ago}
    })
    
    # Count completed missions this week
    missions_completed = await db.behavioral_missions.count_documents({
        "user_id": user.user_id,
        "status": "completed",
        "completed_at": {"$gte": one_week_ago}
    })
    
    # Check for improving patterns (from focus_mastery collection)
    improving_pattern = None
    mastery_doc = await db.focus_mastery.find_one({"user_id": user.user_id})
    if mastery_doc:
        patterns = mastery_doc.get("patterns", {})
        for pattern_name, pattern_data in patterns.items():
            if pattern_data.get("trend") == "improving":
                improving_pattern = pattern_name.replace("_", " ").title()
                break
    
    # Get streak
    streak_days = 0
    streak_doc = await db.user_streaks.find_one({"user_id": user.user_id})
    if streak_doc:
        streak_days = streak_doc.get("current_streak", 0)
    
    return {
        "wins": wins,
        "missions_completed": missions_completed,
        "leak_reduced": improving_pattern,
        "streak_days": streak_days
    }

# ==================== MISSION ENGINE ROUTES ====================

class MissionStepRequest(BaseModel):
    """Request for recording a mission step"""
    step_type: str  # "drill_result" | "reflect_complete" | "process_signal"
    payload: Dict = {}

class MissionCompleteRequest(BaseModel):
    """Request for completing a mission"""
    score: Dict

@api_router.get("/missions/today")
async def get_today_mission(user: User = Depends(get_current_user)):
    """
    Get or generate today's mission.
    Returns active mission if exists, otherwise generates new one.
    """
    user_doc = await db.users.find_one({"user_id": user.user_id})
    rating = user_doc.get("assessed_rating", 1200) if user_doc else 1200
    
    mission = await generate_daily_mission(user.user_id, rating, db)
    
    # Get focus info
    focus_data = PATTERN_FOCUS_MAP.get(mission.get("focus_pattern"), {})
    
    return {
        "mission_id": mission.get("mission_id"),
        "trigger_type": mission.get("trigger_type"),
        "focus_label": mission.get("focus_label"),
        "focus_pattern": mission.get("focus_pattern"),
        "micro_protocol": mission.get("micro_protocol", focus_data.get("micro_protocol", [])),
        "goal": {
            "type": mission.get("goal_type"),
            "target": mission.get("goal_target"),
            "success_threshold": mission.get("goal_success_threshold"),
        },
        "estimated_minutes": mission.get("estimated_minutes"),
        "difficulty_band": mission.get("difficulty_band"),
        "status": mission.get("status"),
        "source_game_id": mission.get("source_game_id"),
    }

@api_router.post("/missions/{mission_id}/start")
async def start_mission_endpoint(mission_id: str, user: User = Depends(get_current_user)):
    """Start a mission session."""
    result = await start_mission(mission_id, user.user_id, db)
    return result

@api_router.get("/missions/{mission_id}/positions")
async def get_mission_positions(mission_id: str, user: User = Depends(get_current_user)):
    """
    Get drill positions for a specific mission.
    Returns positions from user's games that match the mission's focus pattern.
    """
    # Get mission
    mission = await db.behavioral_missions.find_one({
        "mission_id": mission_id,
        "user_id": user.user_id
    })
    
    if not mission:
        raise HTTPException(status_code=404, detail="Mission not found")
    
    focus_pattern = mission.get("focus_pattern", "critical_moment_drift")
    target_count = mission.get("goal_target", 5)
    source_game_id = mission.get("source_game_id")
    
    # Get positions from user's analyzed games
    positions = []
    
    # If mission is from a specific game, prioritize that game
    if source_game_id:
        source_analysis = await db.game_analyses.find_one({"game_id": source_game_id})
        if source_analysis:
            positions = extract_drill_positions(source_analysis, focus_pattern, limit=target_count)
    
    # Get more from other games if needed
    if len(positions) < target_count:
        other_analyses = await db.game_analyses.find({
            "user_id": user.user_id,
        }).sort("analyzed_at", -1).limit(15).to_list(15)
        
        for analysis in other_analyses:
            more_positions = extract_drill_positions(analysis, focus_pattern, limit=target_count - len(positions))
            positions.extend(more_positions)
            if len(positions) >= target_count:
                break
    
    # If still no positions, generate sample positions for the pattern
    if len(positions) == 0:
        positions = get_sample_drill_positions(focus_pattern, target_count)
    
    return {
        "positions": positions[:target_count],
        "total": len(positions[:target_count]),
        "focus_pattern": focus_pattern,
        "mission_id": mission_id
    }


def get_sample_drill_positions(focus_pattern: str, count: int = 5) -> list:
    """
    Generate sample drill positions for training when no user-specific positions exist.
    These are common tactical patterns matching the focus area.
    """
    # Sample positions by pattern - real tactical puzzles
    SAMPLE_POSITIONS = {
        "ignored_opponent_forcing": [
            {
                "fen": "r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 4 4",
                "best_move": "Qxf7+",
                "explanation": "White can win material - what threat did Black ignore?",
            },
            {
                "fen": "r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 2 3",
                "best_move": "Ng5",
                "explanation": "Look for forcing moves against f7.",
            },
            {
                "fen": "rnbqkb1r/pppp1ppp/5n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R b KQkq - 3 3",
                "best_move": "Nc6",
                "explanation": "Develop while defending - what threat must Black see?",
            },
            {
                "fen": "r1bqkbnr/pppp1ppp/2n5/1B2p3/4P3/5N2/PPPP1PPP/RNBQK2R b KQkq - 3 3",
                "best_move": "a6",
                "explanation": "Address the bishop's threat to the knight.",
            },
            {
                "fen": "r2qkb1r/ppp2ppp/2n1bn2/3pp3/2B1P3/2NP1N2/PPP2PPP/R1BQK2R w KQkq - 0 6",
                "best_move": "exd5",
                "explanation": "Open lines while the king is in the center.",
            },
        ],
        "missed_forcing_move": [
            {
                "fen": "r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4",
                "best_move": "Ng5",
                "explanation": "Find the most aggressive move targeting f7.",
            },
            {
                "fen": "r1bqkbnr/pppp1Qpp/2n5/4p3/2B1P3/8/PPPP1PPP/RNB1K1NR b KQkq - 0 4",
                "best_move": "Kxf7",
                "explanation": "The only legal move - but what did White miss before?",
            },
            {
                "fen": "rnb1kbnr/pppp1ppp/8/4p3/5PPq/8/PPPPP2P/RNBQKBNR w KQkq - 1 3",
                "best_move": "g3",
                "explanation": "Trap the queen - forcing moves work both ways!",
            },
            {
                "fen": "r1bqk2r/pppp1ppp/2n2n2/2b1p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4",
                "best_move": "d3",
                "explanation": "Solidify before attacking - sometimes defense is forcing.",
            },
            {
                "fen": "r1bqkb1r/1ppp1ppp/p1n2n2/4p3/B3P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 0 5",
                "best_move": "Bxc6",
                "explanation": "Exchange before Black can castle.",
            },
        ],
        "critical_moment_drift": [
            {
                "fen": "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3",
                "best_move": "Bb5",
                "explanation": "The critical moment - choose the most active development.",
            },
            {
                "fen": "r1bqkb1r/pppp1ppp/2n2n2/4p3/4P3/2N2N2/PPPP1PPP/R1BQKB1R w KQkq - 4 4",
                "best_move": "Bb5",
                "explanation": "Don't drift - keep the pressure on.",
            },
            {
                "fen": "r1bqkbnr/pppp1ppp/2n5/1B2p3/4P3/5N2/PPPP1PPP/RNBQK2R b KQkq - 3 3",
                "best_move": "Nf6",
                "explanation": "Develop with tempo - challenge the center.",
            },
            {
                "fen": "rnbqkb1r/pp2pppp/5n2/2pp4/3P4/2N2N2/PPP1PPPP/R1BQKB1R w KQkq - 0 4",
                "best_move": "cxd5",
                "explanation": "Critical pawn tension - make the right capture.",
            },
            {
                "fen": "r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4",
                "best_move": "d3",
                "explanation": "Solid over flashy - protect before attacking.",
            },
        ],
        "advantage_mismanagement": [
            {
                "fen": "r1bq1rk1/ppp2ppp/2n1pn2/3p4/1bPP4/2NBPN2/PP3PPP/R1BQK2R w KQ - 2 7",
                "best_move": "O-O",
                "explanation": "Consolidate your advantage - safety first.",
            },
            {
                "fen": "r1bqk2r/pppp1ppp/2n2n2/2b1p3/2BPP3/5N2/PPP2PPP/RNBQK2R b KQkq - 0 4",
                "best_move": "exd4",
                "explanation": "Convert the advantage carefully.",
            },
            {
                "fen": "rnbqk2r/pppp1ppp/5n2/2b1p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4",
                "best_move": "c3",
                "explanation": "Prepare d4 - don't rush the attack.",
            },
            {
                "fen": "r1bqkb1r/pppp1ppp/2n2n2/4p3/2BPP3/5N2/PPP2PPP/RNBQK2R b KQkq - 0 4",
                "best_move": "exd4",
                "explanation": "Simplify when ahead - trade pieces.",
            },
            {
                "fen": "r1bq1rk1/ppppbppp/2n2n2/4p3/2B1P3/3P1N2/PPP2PPP/RNBQ1RK1 w - - 6 6",
                "best_move": "Nc3",
                "explanation": "Develop all pieces before attacking.",
            },
        ],
    }
    
    # Default to critical_moment_drift if pattern not found
    pattern_positions = SAMPLE_POSITIONS.get(focus_pattern, SAMPLE_POSITIONS["critical_moment_drift"])
    
    positions = []
    for i, pos in enumerate(pattern_positions[:count]):
        positions.append({
            "position_id": f"sample_{focus_pattern}_{i}",
            "game_id": "sample",
            "fen": pos["fen"],
            "move_number": i + 1,
            "user_move": None,
            "best_move": pos["best_move"],
            "eval_before": 0,
            "eval_after": 0,
            "eval_change": 0,
            "category": focus_pattern,
            "explanation": pos["explanation"],
            "type": "drill",
        })
    
    return positions


def extract_drill_positions(analysis: dict, focus_pattern: str, limit: int = 5) -> list:
    """
    Extract drill-worthy positions from a game analysis based on focus pattern.
    """
    positions = []
    game_id = analysis.get("game_id")
    
    # Get move evaluations from stockfish_analysis
    sf = analysis.get("stockfish_analysis", {})
    move_evals = sf.get("move_evaluations", [])
    
    # Map focus patterns to evaluation types
    pattern_eval_map = {
        "ignored_opponent_forcing": ["blunder", "mistake"],
        "missed_forcing_move": ["blunder", "mistake"],
        "phantom_threat": ["blunder", "mistake", "inaccuracy"],
        "advantage_mismanagement": ["blunder", "mistake"],
        "critical_moment_drift": ["blunder", "mistake"],
        "structural_misjudgment": ["blunder", "mistake", "inaccuracy"],
    }
    
    target_evals = pattern_eval_map.get(focus_pattern, ["blunder", "mistake"])
    
    # Find positions matching the pattern
    for move_eval in move_evals:
        if len(positions) >= limit:
            break
            
        eval_type = move_eval.get("evaluation")
        if eval_type not in target_evals:
            continue
        
        # Get the FEN - it's stored as 'fen_before' in the move evaluation
        fen = move_eval.get("fen_before")
        if not fen:
            continue
        
        pos = {
            "position_id": f"{game_id}_{move_eval.get('move_number', 0)}",
            "game_id": game_id,
            "fen": fen,
            "move_number": move_eval.get("move_number"),
            "user_move": move_eval.get("move"),
            "best_move": move_eval.get("best_move"),
            "eval_before": move_eval.get("eval_before"),
            "eval_after": move_eval.get("eval_after"),
            "eval_change": move_eval.get("cp_loss"),
            "category": focus_pattern,
            "explanation": f"You played {move_eval.get('move')}, but {move_eval.get('best_move')} was better. {move_eval.get('threat', '')}",
            "type": eval_type,
        }
        positions.append(pos)
    
    return positions

@api_router.post("/missions/generate-fix")
async def generate_fix_mission(data: dict, user: User = Depends(get_current_user)):
    """
    Generate a fix-it mission for a specific game (post-loss recovery).
    Returns the mission that targets the main issue from the game.
    """
    game_id = data.get("game_id")
    if not game_id:
        raise HTTPException(status_code=400, detail="game_id required")
    
    # Get game analysis
    analysis = await db.game_analyses.find_one({"game_id": game_id, "user_id": user.user_id})
    if not analysis:
        raise HTTPException(status_code=404, detail="Game analysis not found")
    
    # Get user rating
    user_doc = await db.users.find_one({"user_id": user.user_id})
    rating = user_doc.get("assessed_rating", 1200) if user_doc else 1200
    
    # Find main issue pattern
    blunders = analysis.get("blunders", [])
    main_pattern = "critical_moment_drift"  # Default
    
    if blunders:
        categories = [b.get("mistake_category") for b in blunders if b.get("mistake_category")]
        if categories:
            from collections import Counter
            main_pattern = Counter(categories).most_common(1)[0][0]
    
    # Generate mission targeting this pattern
    mission = await generate_daily_mission(
        user.user_id, 
        rating, 
        db,
        trigger_type="post_loss",
        source_game_id=game_id,
        force_pattern=main_pattern
    )
    
    # Get focus info
    focus_data = PATTERN_FOCUS_MAP.get(mission.get("focus_pattern"), {})
    
    return {
        "mission_id": mission.get("mission_id"),
        "trigger_type": "post_loss",
        "focus_label": mission.get("focus_label"),
        "focus_pattern": mission.get("focus_pattern"),
        "micro_protocol": mission.get("micro_protocol", focus_data.get("micro_protocol", [])),
        "goal": {
            "type": mission.get("goal_type"),
            "target": mission.get("goal_target"),
            "success_threshold": mission.get("goal_threshold"),
        },
        "estimated_minutes": mission.get("estimated_minutes"),
        "difficulty_band": mission.get("difficulty_band"),
        "source_game_id": game_id,
    }

@api_router.post("/missions/{mission_id}/step")
async def record_mission_step(
    mission_id: str,
    data: MissionStepRequest,
    user: User = Depends(get_current_user)
):
    """
    Record a step in the mission session.
    Emits reward events for process recognition.
    """
    now = datetime.now(timezone.utc)
    
    # Get active session
    session = await db.mission_sessions.find_one({
        "mission_id": mission_id,
        "user_id": user.user_id,
        "ended_at": None,
    })
    
    if not session:
        raise HTTPException(status_code=404, detail="No active session for this mission")
    
    # Build step record
    step = {
        "type": data.step_type,
        "payload": data.payload,
        "status": data.payload.get("status", "done"),
        "duration_ms": data.payload.get("duration_ms", 0),
        "recorded_at": now.isoformat(),
    }
    
    # Update session
    await db.mission_sessions.update_one(
        {"session_id": session["session_id"]},
        {"$push": {"steps": step}}
    )
    
    # Check for reward triggers
    reward_events = []
    user_doc = await db.users.find_one({"user_id": user.user_id})
    rating = user_doc.get("assessed_rating", 1200) if user_doc else 1200
    
    # Process Recognition: Check if user used threat scan
    if data.step_type == "drill_result" and data.payload.get("used_threat_scan"):
        reward_msg = get_reward_message(
            RewardEventType.PROCESS_THREAT_SCAN,
            rating,
        )
        if reward_msg:
            reward_events.append({
                "type": "process_recognition",
                "message": reward_msg["text"],
            })
            # Store event
            await db.reward_events.insert_one({
                "event_id": f"e_{uuid.uuid4().hex[:12]}",
                "user_id": user.user_id,
                "event_type": RewardEventType.PROCESS_THREAT_SCAN.value,
                "source": "mission",
                "payload": {"mission_id": mission_id},
                "message_id": reward_msg["message_id"],
                "created_at": now.isoformat(),
                "seen": False,
            })
    
    # Pattern Recognition: Check if user got 2+ correct on same pattern
    if data.step_type == "drill_result" and data.payload.get("is_correct"):
        # Count correct in session
        correct_count = sum(1 for s in session.get("steps", []) 
                          if s.get("type") == "drill_result" and s.get("payload", {}).get("is_correct"))
        if correct_count == 1:  # This is their second correct
            reward_msg = get_reward_message(
                RewardEventType.PATTERN_RECOGNIZED,
                rating,
            )
            if reward_msg:
                reward_events.append({
                    "type": "pattern_recognition",
                    "message": reward_msg["text"],
                })
    
    # Recovery: Check for wrong → correct → correct sequence
    steps = session.get("steps", []) + [step]
    drill_results = [s for s in steps if s.get("type") == "drill_result"]
    if len(drill_results) >= 3:
        last_three = drill_results[-3:]
        results = [s.get("payload", {}).get("is_correct") for s in last_three]
        if results == [False, True, True]:
            reward_msg = get_reward_message(
                RewardEventType.RECOVERY_GOOD_RESET,
                rating,
            )
            if reward_msg:
                reward_events.append({
                    "type": "recovery_moment",
                    "message": reward_msg["text"],
                })
    
    # Update score in session
    if data.step_type == "drill_result":
        is_correct = data.payload.get("is_correct", False)
        await db.mission_sessions.update_one(
            {"session_id": session["session_id"]},
            {
                "$inc": {
                    "score.attempted": 1,
                    "score.correct": 1 if is_correct else 0,
                }
            }
        )
    
    # Get updated score
    updated_session = await db.mission_sessions.find_one({"session_id": session["session_id"]})
    
    return {
        "step_recorded": True,
        "reward_events": reward_events,
        "progress": {
            "attempted": updated_session.get("score", {}).get("attempted", 0),
            "correct": updated_session.get("score", {}).get("correct", 0),
            "target": 5,  # From mission
        },
    }

@api_router.post("/missions/{mission_id}/complete")
async def complete_mission_endpoint(
    mission_id: str,
    data: MissionCompleteRequest,
    user: User = Depends(get_current_user)
):
    """Complete a mission and get result + rewards."""
    # Get active session
    session = await db.mission_sessions.find_one({
        "mission_id": mission_id,
        "user_id": user.user_id,
        "ended_at": None,
    })
    
    if not session:
        raise HTTPException(status_code=404, detail="No active session")
    
    result = await complete_mission(
        mission_id=mission_id,
        session_id=session["session_id"],
        user_id=user.user_id,
        score=data.score,
        db=db,
    )
    
    # Get reward message
    user_doc = await db.users.find_one({"user_id": user.user_id})
    rating = user_doc.get("assessed_rating", 1200) if user_doc else 1200
    
    passed = result.get("result") == "pass"
    reward_event = RewardEventType.MISSION_COMPLETE_PASS if passed else RewardEventType.MISSION_COMPLETE_FAIL
    
    reward_msg = get_reward_message(reward_event, rating, {
        "focus_label": result.get("focus_label"),
        "correct": result.get("score", {}).get("correct", 0),
        "attempted": result.get("score", {}).get("attempted", 0),
    })
    
    # Store reward event
    if reward_msg:
        await db.reward_events.insert_one({
            "event_id": f"e_{uuid.uuid4().hex[:12]}",
            "user_id": user.user_id,
            "event_type": reward_event.value,
            "source": "mission",
            "payload": {"mission_id": mission_id, "result": result.get("result")},
            "message_id": reward_msg["message_id"],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "seen": False,
        })
    
    return {
        "result": result.get("result"),
        "score": result.get("score"),
        "threshold": result.get("threshold"),
        "focus_label": result.get("focus_label"),
        "coach_message": reward_msg["text"] if reward_msg else ("Good work!" if passed else "Keep practicing."),
    }

@api_router.get("/missions/history")
async def get_mission_history(limit: int = 10, user: User = Depends(get_current_user)):
    """Get user's recent mission history."""
    missions = await db.behavioral_missions.find({
        "user_id": user.user_id,
        "status": "completed",
    }).sort("completed_at", -1).limit(limit).to_list(limit)
    
    result = []
    for m in missions:
        result.append({
            "mission_id": m.get("mission_id"),
            "focus_label": m.get("focus_label"),
            "result": m.get("result"),
            "completed_at": m.get("completed_at"),
            "trigger_type": m.get("trigger_type"),
        })
    
    # Stats
    total = len(result)
    passed = sum(1 for m in result if m["result"] == "pass")
    
    return {
        "missions": result,
        "stats": {
            "total": total,
            "passed": passed,
            "pass_rate": passed / total if total > 0 else 0,
        },
    }

@api_router.get("/missions/focus-mastery")
async def get_focus_mastery(user: User = Depends(get_current_user)):
    """Get user's focus mastery levels."""
    masteries = await db.focus_mastery.find({
        "user_id": user.user_id,
    }).to_list(20)
    
    result = []
    for m in masteries:
        score = m.get("mastery_score", 0)
        band = "Emerging" if score < 25 else "Improving" if score < 50 else "Stable" if score < 75 else "Reliable"
        
        pattern = m.get("pattern")
        focus_data = PATTERN_FOCUS_MAP.get(pattern, {})
        
        result.append({
            "pattern": pattern,
            "label": focus_data.get("focus_label", pattern),
            "mastery_score": score,
            "band": band,
            "recent_results": m.get("recent_mission_results", [])[-5:],
        })
    
    return {"masteries": result}

@api_router.get("/weekly-proof")
async def get_weekly_proof_endpoint(user: User = Depends(get_current_user)):
    """
    Get weekly proof card data.
    Shows improvement, ongoing issues, and next focus.
    """
    user_doc = await db.users.find_one({"user_id": user.user_id})
    rating = user_doc.get("assessed_rating", 1200) if user_doc else 1200
    
    # Get recent analyses for blunder trend
    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)
    two_weeks_ago = now - timedelta(days=14)
    
    this_week = await db.game_analyses.find({
        "user_id": user.user_id,
        "analyzed_at": {"$gte": week_ago.isoformat()},
    }).to_list(50)
    
    last_week = await db.game_analyses.find({
        "user_id": user.user_id,
        "analyzed_at": {"$gte": two_weeks_ago.isoformat(), "$lt": week_ago.isoformat()},
    }).to_list(50)
    
    # Calculate blunder rates
    this_week_blunders = sum(len(a.get("blunders", [])) for a in this_week)
    this_week_games = len(this_week) or 1
    last_week_blunders = sum(len(a.get("blunders", [])) for a in last_week)
    last_week_games = len(last_week) or 1
    
    blunders_delta = (this_week_blunders / this_week_games) - (last_week_blunders / last_week_games)
    
    # Get main leak
    pattern_counts = {}
    for a in this_week:
        for b in a.get("blunders", []):
            cat = b.get("mistake_category")
            if cat:
                pattern_counts[cat] = pattern_counts.get(cat, 0) + 1
    
    main_leak = None
    if pattern_counts:
        main_pattern = max(pattern_counts, key=pattern_counts.get)
        main_leak = PATTERN_FOCUS_MAP.get(main_pattern, {}).get("focus_label", main_pattern)
    
    # Get next focus from training profile or top pattern
    training_profile = await db.training_profiles.find_one({"user_id": user.user_id})
    next_focus = training_profile.get("current_focus_label") if training_profile else main_leak
    
    # Generate proof
    proof = generate_weekly_proof(
        rating=rating,
        blunders_delta=blunders_delta,
        main_leak=main_leak or "General patterns",
        improvement_area=None,
        next_focus=next_focus,
    )
    
    return {
        "lines": proof["lines"],
        "rating_band": proof["rating_band"],
        "stats": {
            "this_week_games": this_week_games,
            "this_week_blunders_per_game": round(this_week_blunders / this_week_games, 2),
            "blunders_delta": round(blunders_delta, 2),
        },
    }

@api_router.get("/reflect/v1/post-loss/{game_id}")
async def get_post_loss_recovery(game_id: str, user: User = Depends(get_current_user)):
    """
    Get post-loss recovery screen data.
    Shows after a loss to convert pain into training.
    """
    # Get the game
    game = await db.games.find_one({"game_id": game_id, "user_id": user.user_id})
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    
    # Get analysis
    analysis = await db.game_analyses.find_one({"game_id": game_id})
    if not analysis:
        raise HTTPException(status_code=404, detail="Game not analyzed yet")
    
    # Get user rating
    user_doc = await db.users.find_one({"user_id": user.user_id})
    rating = user_doc.get("assessed_rating", 1200) if user_doc else 1200
    
    # Get main issue and critical moment from game
    blunders = analysis.get("blunders", [])
    mistakes = analysis.get("mistakes", [])
    stockfish_eval = analysis.get("stockfish_analysis", {}).get("move_evaluations", [])
    
    main_issue = "Critical position focus"
    critical_moment = None
    main_category = None
    
    # Find the most critical blunder
    if blunders:
        # Get most severe blunder category
        categories = [b.get("mistake_category", "unknown") for b in blunders if b.get("mistake_category")]
        if categories:
            from collections import Counter
            main_category = Counter(categories).most_common(1)[0][0]
            main_issue = {
                "ignored_opponent_forcing": "Opponent Threat Awareness",
                "missed_forcing_move": "Forcing Move Awareness",
                "phantom_threat": "Threat Prioritization",
                "advantage_mismanagement": "Advantage Conversion",
                "critical_moment_drift": "Critical Position Focus",
                "structural_misjudgment": "Pawn Structure Judgment",
            }.get(main_category, main_category.replace("_", " ").title())
        
        # Get the critical moment (worst blunder)
        worst_blunder = max(blunders, key=lambda b: abs(b.get("eval_change", 0)))
        critical_moment = {
            "fen": worst_blunder.get("fen"),
            "user_move": worst_blunder.get("user_move"),
            "best_move": worst_blunder.get("best_move"),
            "eval_change": worst_blunder.get("eval_change"),
            "move_number": worst_blunder.get("move_number"),
        }
    elif mistakes:
        worst_mistake = max(mistakes, key=lambda m: abs(m.get("eval_change", 0)))
        critical_moment = {
            "fen": worst_mistake.get("fen"),
            "user_move": worst_mistake.get("user_move"),
            "best_move": worst_mistake.get("best_move"),
            "eval_change": worst_mistake.get("eval_change"),
            "move_number": worst_mistake.get("move_number"),
        }
    elif stockfish_eval:
        # Find worst eval drop from stockfish analysis
        for move in stockfish_eval:
            eval_type = move.get("evaluation")
            if hasattr(eval_type, 'value'):
                eval_type = eval_type.value
            if eval_type in ["blunder", "mistake"]:
                critical_moment = {
                    "fen": move.get("fen"),
                    "user_move": move.get("san"),
                    "best_move": move.get("best_move"),
                    "eval_change": move.get("eval_delta"),
                    "move_number": move.get("move_number"),
                }
                break
    
    # Get adaptive profile for mission time
    profile = get_adaptive_profile_sync(rating)
    minutes = profile["mission_minutes_target"]
    
    # Get post-loss message for headline
    message = get_post_loss_message(rating, main_issue, minutes)
    
    return {
        "game_id": game_id,
        "result": game.get("result", "loss"),
        "opponent_name": game.get("opponent_name", "Opponent"),
        "user_color": game.get("user_color", "white"),
        "main_issue": main_issue,
        "headline": message.get("headline", "Let's fix this moment."),
        "estimated_minutes": minutes,
        "critical_moment": critical_moment,
        "has_pending_reflection": len(blunders) + len(mistakes) > 0,
        "blunder_count": len(blunders),
        "mistake_count": len(mistakes),
    }

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
    NEW Progress Page - Chess DNA Badges + Coach Assessment + Before/After Comparison
    
    Returns:
    - Coach's honest assessment (not just stats)
    - Rating reality (framed constructively)
    - 8 skill badges with trends
    - Proof from games
    - Memorable rules
    - Next 10 games plan
    - Before Coach vs After Coach comparison (stats AND patterns)
    """
    from coach_assessment_service import generate_full_progress_data
    from baseline_service import (
        get_or_create_baseline,
        get_baseline_patterns,
        calculate_current_stats,
        calculate_progress,
        calculate_pattern_snapshot,
        compare_patterns,
        MIN_GAMES_FOR_BASELINE
    )
    
    try:
        progress_data = await generate_full_progress_data(db, user.user_id)
        
        # Add Before/After Coach comparison
        all_analyses = await db.game_analyses.find(
            {"user_id": user.user_id}
        ).sort("created_at", -1).to_list(200)
        
        all_games = await db.games.find(
            {"user_id": user.user_id}
        ).sort("imported_at", -1).to_list(200)
        
        # Get or create baseline (snapshot from when user started)
        baseline = await get_or_create_baseline(db, user.user_id, all_analyses, all_games)
        
        # Get baseline patterns (weaknesses, blunder context from first games)
        baseline_patterns = await get_baseline_patterns(db, user.user_id)
        
        # If baseline exists but patterns don't (legacy user), create patterns now
        if baseline and not baseline_patterns:
            baseline_analyses = sorted(all_analyses, key=lambda x: x.get('created_at', ''))[:MIN_GAMES_FOR_BASELINE]
            baseline_games = sorted(all_games, key=lambda x: x.get('imported_at', ''))[:MIN_GAMES_FOR_BASELINE]
            baseline_patterns = calculate_pattern_snapshot(baseline_analyses, baseline_games)
            
            # Save it for future use
            await db.users.update_one(
                {'user_id': user.user_id},
                {'$set': {'baseline_patterns': baseline_patterns}}
            )
        
        # Calculate current stats from recent 25 games
        recent_analyses = all_analyses[:25] if len(all_analyses) > 25 else all_analyses
        recent_games = all_games[:25] if len(all_games) > 25 else all_games
        current_stats = calculate_current_stats(recent_analyses, recent_games)
        
        # Calculate current patterns
        current_patterns = calculate_pattern_snapshot(recent_analyses, recent_games) if recent_analyses else None
        
        # Calculate progress (stats comparison)
        comparison = None
        if baseline and current_stats:
            comparison = calculate_progress(baseline, current_stats)
        
        # Calculate pattern comparison (weaknesses comparison)
        pattern_comparison = None
        if baseline_patterns and current_patterns:
            pattern_comparison = compare_patterns(baseline_patterns, current_patterns)
        
        # Add to response
        progress_data['coaching_comparison'] = {
            'has_baseline': baseline is not None,
            'games_until_baseline': max(0, MIN_GAMES_FOR_BASELINE - len(all_analyses)) if not baseline else 0,
            'baseline': baseline,
            'current': current_stats,
            'progress': comparison,
            # NEW: Pattern data for Before/After tabs
            'baseline_patterns': baseline_patterns,
            'current_patterns': current_patterns,
            'pattern_comparison': pattern_comparison
        }
        
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

# ==================== ONBOARDING ====================

@api_router.get("/onboarding/status")
async def get_onboarding_status(user: User = Depends(get_current_user)):
    """
    Check if user needs onboarding.
    Returns needs_onboarding=true if no linked accounts AND no analyzed games.
    """
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


class ProfileSettingsRequest(BaseModel):
    fide_rating: Optional[int] = None
    detected_rating: Optional[int] = None  # Auto-detected from linked account
    detected_platform: Optional[str] = None  # chess.com or lichess
    focus_intent: Optional[str] = None  # tactics, openings, endgames, stability


@api_router.post("/settings/profile")
async def update_profile_settings(req: ProfileSettingsRequest, user: User = Depends(get_current_user)):
    """
    Update user profile settings from onboarding.
    - fide_rating: Official FIDE rating (optional)
    - detected_rating: Auto-detected from Chess.com/Lichess
    - focus_intent: What user wants to improve (doesn't override diagnosis)
    """
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


@api_router.post("/settings/link-account")
async def settings_link_account(req: LinkAccountRequest, user: User = Depends(get_current_user)):
    """
    Link chess account and calculate assessed skill rating.
    """
    from skill_calibration_service import calculate_performance_rating, classify_time_control
    
    platform = req.platform.lower()
    username = req.username.strip()
    
    if platform not in ["chess.com", "lichess"]:
        raise HTTPException(status_code=400, detail="Invalid platform. Use 'chess.com' or 'lichess'")
    
    if not username:
        raise HTTPException(status_code=400, detail="Username is required")
    
    # Update user record based on platform
    if platform == "chess.com":
        update_field = "chesscom_username"
    else:
        update_field = "lichess_username"
    
    await db.users.update_one(
        {"user_id": user.user_id},
        {"$set": {
            update_field: username,
            "last_game_sync": None
        }}
    )
    
    # Fetch recent games and calculate performance rating
    assessed_rating = None
    games_data = []
    
    try:
        if platform == "chess.com":
            import httpx
            async with httpx.AsyncClient() as client:
                # Get recent games from Chess.com
                from datetime import datetime
                now = datetime.now()
                year, month = now.year, now.month
                
                for _ in range(3):  # Check last 3 months
                    url = f"https://api.chess.com/pub/player/{username}/games/{year}/{month:02d}"
                    resp = await client.get(url, timeout=10)
                    if resp.status_code == 200:
                        data = resp.json()
                        for game in data.get("games", [])[:25]:
                            # Extract game info
                            white = game.get("white", {})
                            black = game.get("black", {})
                            is_white = white.get("username", "").lower() == username.lower()
                            
                            opp = black if is_white else white
                            player = white if is_white else black
                            
                            opp_rating = opp.get("rating")
                            result_str = player.get("result", "")
                            
                            if result_str == "win":
                                result = "win"
                            elif result_str in ["checkmated", "timeout", "resigned", "abandoned"]:
                                result = "loss"
                            else:
                                result = "draw"
                            
                            tc = game.get("time_class", "blitz")
                            
                            if opp_rating:
                                games_data.append({
                                    "opponent_rating": opp_rating,
                                    "result": result,
                                    "time_control": tc
                                })
                    
                    # Move to previous month
                    month -= 1
                    if month == 0:
                        month = 12
                        year -= 1
                    
                    if len(games_data) >= 25:
                        break
        
        elif platform == "lichess":
            import httpx
            async with httpx.AsyncClient() as client:
                url = f"https://lichess.org/api/games/user/{username}?max=25&perfType=rapid,classical,blitz"
                headers = {"Accept": "application/x-ndjson"}
                resp = await client.get(url, headers=headers, timeout=15)
                
                if resp.status_code == 200:
                    import json
                    for line in resp.text.strip().split("\n"):
                        if not line:
                            continue
                        try:
                            game = json.loads(line)
                            players = game.get("players", {})
                            white = players.get("white", {})
                            black = players.get("black", {})
                            
                            is_white = white.get("user", {}).get("name", "").lower() == username.lower()
                            
                            opp = black if is_white else white
                            player_color = "white" if is_white else "black"
                            
                            opp_rating = opp.get("rating")
                            winner = game.get("winner")
                            
                            if winner == player_color:
                                result = "win"
                            elif winner is None:
                                result = "draw"
                            else:
                                result = "loss"
                            
                            tc = game.get("speed", "blitz")
                            
                            if opp_rating:
                                games_data.append({
                                    "opponent_rating": opp_rating,
                                    "result": result,
                                    "time_control": tc
                                })
                        except (json.JSONDecodeError, KeyError, TypeError):
                            continue
        
        # Calculate performance rating
        if games_data:
            perf, confidence = calculate_performance_rating(games_data, platform)
            if perf:
                assessed_rating = int(perf)
                
                # Determine skill level
                if assessed_rating >= 2000:
                    skill_level = "expert"
                elif assessed_rating >= 1800:
                    skill_level = "advanced"
                elif assessed_rating >= 1400:
                    skill_level = "intermediate"
                elif assessed_rating >= 1000:
                    skill_level = "developing"
                else:
                    skill_level = "beginner"
                
                # Store assessed rating
                await db.users.update_one(
                    {"user_id": user.user_id},
                    {"$set": {
                        "assessed_rating": assessed_rating,
                        "skill_level": skill_level,
                        "rating_confidence": confidence,
                        "rating_source": platform,
                        "rating_games_analyzed": len(games_data)
                    }}
                )
    
    except Exception as e:
        logger.warning(f"Failed to calculate performance rating: {e}")
    
    return {
        "message": "Account linked successfully",
        "platform": platform,
        "username": username,
        "assessed_rating": assessed_rating,
        "games_analyzed": len(games_data)
    }


@api_router.post("/games/sync")
async def sync_games_now(background_tasks: BackgroundTasks, user: User = Depends(get_current_user)):
    """
    Trigger immediate game sync for onboarding.
    Runs sync in background and returns immediately.
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
        raise HTTPException(status_code=400, detail="No chess accounts linked")
    
    # Run sync in background
    async def do_sync():
        try:
            await sync_user_games(db, user.user_id, user_doc)
        except Exception as e:
            logger.error(f"Game sync failed for {user.user_id}: {e}")
    
    background_tasks.add_task(do_sync)
    
    return {"message": "Game sync started", "status": "processing"}


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
async def get_training_puzzles(
    limit: int = 10,
    user: User = Depends(get_current_user)
):
    """
    Get personalized puzzles from user's own mistakes.
    """
    from interactive_training_service import get_user_puzzles
    
    puzzles = await get_user_puzzles(db, user.user_id, limit)
    
    return {
        "puzzles": puzzles,
        "total": len(puzzles),
        "source": "your_games"
    }

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
    Analyze a single position using Stockfish with caching.
    Returns evaluation and best moves.
    """
    try:
        from position_analysis_cache_service import PositionAnalysisService
        
        service = PositionAnalysisService(db)
        result = await service.get_position_eval(req.fen, depth=req.depth)
        
        if result.get("source") == "error":
            raise HTTPException(status_code=400, detail=result.get("error", "Analysis failed"))
        
        # Convert to expected format for backwards compatibility
        return {
            "success": True,
            "evaluation": {
                "centipawns": result.get("eval_cp", 0),
                "mate_in": result.get("eval_mate")
            },
            "best_move": {
                "uci": result.get("best_move"),
                "san": result.get("best_move_san")
            },
            "pv": result.get("pv_san", []),
            "depth": result.get("depth"),
            "source": result.get("source")  # Shows if from cache or fresh
        }
    except HTTPException:
        raise
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
            # Get cached Stockfish analysis for position BEFORE the move
            from position_analysis_cache_service import PositionAnalysisService
            cache_service = PositionAnalysisService(db)
            
            before_result = await cache_service.get_position_eval(req.fen_before, depth=18)
            if before_result.get("source") != "error":
                eval_before = before_result.get("eval_cp", 0)
                best_move_for_user = before_result.get("best_move_san", "")
                best_line_for_user = before_result.get("pv_san", [])[:5]
        
        # Get cached Stockfish analysis for the CURRENT position (after the move)
        from position_analysis_cache_service import PositionAnalysisService
        cache_service = PositionAnalysisService(db)
        
        current_result = await cache_service.get_position_eval(req.fen, depth=18)
        if current_result.get("source") == "error":
            raise HTTPException(status_code=500, detail="Failed to analyze position")
        
        # Extract evaluation
        eval_score = current_result.get("eval_cp", 0)
        is_mate = current_result.get("eval_mate") is not None
        mate_in = current_result.get("eval_mate")
        
        # Extract best move for CURRENT position (opponent's best response)
        opponent_best_move = current_result.get("best_move_san", "")
        
        stockfish_data = {
            "evaluation": eval_score,
            "eval_type": "mate" if is_mate else "cp",
            "best_move": opponent_best_move,  # This is opponent's best move (current turn)
            "best_line": current_result.get("pv_san", [])[:5],
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
                
                # Analyze position after alternative move using cache
                alt_result = await cache_service.get_position_eval(alt_board.fen(), depth=18)
                if alt_result.get("source") != "error":
                    alternative_analysis = {
                        "move": req.alternative_move,
                        "resulting_fen": alt_board.fen(),
                        "evaluation": alt_result.get("eval_cp"),
                        "eval_type": "mate" if alt_result.get("eval_mate") else "cp",
                        "opponent_best_response": alt_result.get("best_move_san"),
                        "continuation": alt_result.get("pv_san", [])[:5]
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


@api_router.post("/focus/next-mission")
async def get_next_mission(user: User = Depends(get_current_user)):
    """
    Mark current mission as completed and get a new mission.
    
    This endpoint is called when the user completes a mission and wants to 
    get a new one. It stores the completion record and returns fresh focus data.
    """
    # Record mission completion
    await db.mission_completions.insert_one({
        "user_id": user.user_id,
        "completed_at": datetime.now(timezone.utc).isoformat()
    })
    
    # Increment completed missions count for the user
    await db.users.update_one(
        {"user_id": user.user_id},
        {"$inc": {"missions_completed": 1}}
    )
    
    return {"status": "ok", "message": "Mission marked as complete. Refresh to get your next mission."}


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


# =============================================================================
# ADAPTIVE PERFORMANCE COACH (NEW GOLD FEATURE - Focus Page v2)
# =============================================================================

@api_router.get("/adaptive-coach")
async def get_adaptive_coach_data_endpoint(user: User = Depends(get_current_user)):
    """
    Get Adaptive Performance Coach data for Focus page.
    
    This is the GM-style performance briefing system with 4 sections:
    1. Coach Diagnosis - Your Current Growth Priority (ONE primary leak)
    2. Next Game Plan - 5 domains (Opening, Middlegame, Tactical, Endgame, Time)
    3. Plan Audit - Last Game Execution Review (audit vs plan)
    4. Skill Signals - Live Performance Monitoring (trends)
    
    Rating-band aware:
    - 600-1000: Focus on Hanging Pieces
    - 1000-1600: Focus on Tactical Awareness
    - 1600-2000: Focus on Advantage Discipline
    - 2000+: Focus on Conversion Precision
    """
    from adaptive_coach_service import get_adaptive_coach_data
    
    data = await get_adaptive_coach_data(db, user.user_id)
    return data


@api_router.post("/adaptive-coach/audit-game/{game_id}")
async def audit_game_adaptive_coach(game_id: str, user: User = Depends(get_current_user)):
    """
    Audit a specific game against the current plan and update intensity levels.
    
    Called after game analysis completes to:
    1. Audit the game against the current plan
    2. Update intensity levels per domain (adaptive loop)
    3. Mark the plan as audited
    """
    from adaptive_coach_service import (
        audit_last_game_against_plan,
        update_intensity_after_audit
    )
    
    # Get game and analysis
    game = await db.games.find_one({"game_id": game_id, "user_id": user.user_id}, {"_id": 0})
    analysis = await db.game_analyses.find_one({"game_id": game_id, "user_id": user.user_id}, {"_id": 0})
    
    if not game or not analysis:
        return {"error": "Game or analysis not found"}
    
    # Get active plan
    active_plan = await db.user_adaptive_plans.find_one(
        {"user_id": user.user_id, "is_active": True},
        {"_id": 0}
    )
    
    if not active_plan:
        return {"error": "No active plan found"}
    
    # Audit the game
    audit_result = audit_last_game_against_plan(analysis, game, active_plan)
    
    # Update intensity levels
    intensity_update = await update_intensity_after_audit(db, user.user_id, audit_result)
    
    # Mark plan as audited
    await db.user_adaptive_plans.update_one(
        {"plan_id": active_plan["plan_id"]},
        {"$set": {"is_active": False, "is_audited": True, "audit_result": audit_result}}
    )
    
    return {
        "audit_result": audit_result,
        "intensity_update": intensity_update,
    }



# =============================================================================
# FOCUS PLAN (DETERMINISTIC PERSONALIZED COACHING)
# =============================================================================

@api_router.get("/focus-plan")
async def get_focus_plan(user: User = Depends(get_current_user)):
    """
    Get the complete Focus Plan for the user.
    
    This is the new deterministic personalized coaching system that:
    1. Computes Cost Scores per coaching bucket from last 25 games
    2. Selects Primary/Secondary focus deterministically
    3. Selects personalized openings based on usage + stability
    4. Generates mission positions from user's own games
    
    Same user + same inputs = same plan (deterministic)
    Different users + different inputs = different plan (personalized)
    
    Coaching Buckets:
    - PIECE_SAFETY: Hanging pieces
    - THREAT_AWARENESS: Missed opponent threats  
    - TACTICAL_EXECUTION: Missed tactics
    - ADVANTAGE_DISCIPLINE: Failed conversion when ahead
    - OPENING_STABILITY: Weak first 10-12 moves
    - TIME_DISCIPLINE: Late-game blunders
    - ENDGAME_FUNDAMENTALS: Conversion failures
    """
    from focus_plan_service import get_focus_page_data
    
    data = await get_focus_page_data(db, user.user_id)
    return data


@api_router.post("/focus-plan/regenerate")
async def regenerate_focus_plan(user: User = Depends(get_current_user)):
    """
    Force regenerate the focus plan.
    
    Useful after importing new games or when user wants fresh analysis.
    """
    from focus_plan_service import generate_focus_plan
    
    plan = await generate_focus_plan(db, user.user_id, force_regenerate=True)
    return plan


@api_router.post("/focus-plan/mission/start")
async def start_mission_session(user: User = Depends(get_current_user)):
    """
    Start a new mission session for active time tracking.
    
    Returns a session_id for tracking interactions.
    Active time is only counted when user interacts within idle threshold (12 sec).
    """
    from focus_plan_service import start_mission_session as start_session
    
    # Get active plan
    plan = await db.focus_plans.find_one(
        {"user_id": user.user_id, "is_active": True},
        {"_id": 0}
    )
    
    if not plan:
        return {"error": "No active plan found"}
    
    session = await start_session(db, user.user_id, plan["plan_id"])
    return session


class MissionInteractionRequest(BaseModel):
    session_id: str
    event_type: str  # "position_attempted", "replay_step", "heartbeat"
    event_data: Optional[Dict[str, Any]] = None


@api_router.post("/focus-plan/mission/interaction")
async def record_mission_interaction(
    request: MissionInteractionRequest,
    user: User = Depends(get_current_user)
):
    """
    Record a mission interaction to track active time.
    
    Event types:
    - "position_attempted": User attempted a position (correct/incorrect in event_data)
    - "replay_step": User played a move in guided replay
    - "heartbeat": Keep session alive (call every 5-10 seconds)
    
    Active time is accumulated only when events come within idle_pause_seconds (12 sec).
    """
    from focus_plan_service import update_mission_interaction
    
    result = await update_mission_interaction(
        db,
        request.session_id,
        request.event_type,
        request.event_data
    )
    return result


@api_router.post("/focus-plan/mission/complete")
async def complete_mission(
    session_id: str,
    user: User = Depends(get_current_user)
):
    """
    Mark a mission as complete.
    
    Updates weekly progress and records completion.
    """
    from focus_plan_service import complete_mission as complete_mission_fn
    
    result = await complete_mission_fn(db, session_id)
    return result


@api_router.get("/focus-plan/bucket-breakdown")
async def get_bucket_breakdown(user: User = Depends(get_current_user)):
    """
    Get detailed breakdown of cost scores per bucket.
    
    Useful for debugging and showing users why they got their focus.
    Returns all bucket costs with example positions.
    """
    from focus_plan_service import compute_bucket_costs, get_rating_band, DEFAULT_GAME_WINDOW
    
    # Get user
    user_doc = await db.users.find_one({"user_id": user.user_id}, {"_id": 0})
    rating = user_doc.get("rating", 1200) if user_doc else 1200
    
    # Get games and analyses
    games = await db.games.find(
        {"user_id": user.user_id, "is_analyzed": True},
        {"_id": 0}
    ).sort("imported_at", -1).to_list(DEFAULT_GAME_WINDOW)
    
    game_ids = [g["game_id"] for g in games]
    analyses = await db.game_analyses.find(
        {"game_id": {"$in": game_ids}},
        {"_id": 0}
    ).to_list(DEFAULT_GAME_WINDOW)
    
    # Compute costs
    bucket_costs = compute_bucket_costs(analyses, games, rating)
    band = get_rating_band(rating)
    
    return {
        "rating": rating,
        "rating_band": band["label"],
        "allowed_buckets": band["allowed_buckets"],
        "bucket_costs": bucket_costs,
    }


@api_router.get("/focus-plan/last-game-audit")
async def get_last_game_audit(user: User = Depends(get_current_user)):
    """
    Audit the user's last game against their active focus plan.
    
    Returns:
    - rules_audit: List of rules with Executed/Partial/Missed status
    - overall_alignment: Overall alignment status
    - violations: Key moments that didn't align with the focus
    - good_moments: Moments that showed good execution
    """
    from focus_plan_service import get_focus_page_data, audit_last_game
    
    # Use get_focus_page_data to ensure plan is generated/active
    data = await get_focus_page_data(db, user.user_id)
    plan = data.get("plan")
    
    if not plan:
        return {"error": "No plan available", "has_audit": False}
    
    audit = await audit_last_game(db, user.user_id, plan)
    return audit


# =============================================================================
# TRAINING ENGINE ENDPOINTS
# =============================================================================

@api_router.get("/training/profile")
async def get_training_profile_endpoint(
    force_regenerate: bool = False,
    user: User = Depends(get_current_user)
):
    """
    Get the user's training profile.
    
    The training profile contains:
    - active_phase: The layer with highest cost (stability/conversion/structure/precision)
    - micro_habit: The dominant pattern within the active phase
    - rules: 2 actionable rules for the week
    - layer_breakdown: Costs for all 4 layers
    - example_positions: Positions from their mistakes for practice
    - reflection_question: Question to prompt self-reflection
    
    Recalculates automatically every 7 games or when force_regenerate=True.
    """
    from training_profile_service import get_or_generate_training_profile
    
    # Get user's rating
    user_doc = await db.users.find_one({"user_id": user.user_id})
    rating = user_doc.get("rating", 1200) if user_doc else 1200
    
    profile = await get_or_generate_training_profile(db, user.user_id, rating, force_regenerate)
    return profile


@api_router.post("/training/profile/regenerate")
async def regenerate_training_profile(user: User = Depends(get_current_user)):
    """Force regenerate the training profile."""
    from training_profile_service import generate_training_profile
    
    user_doc = await db.users.find_one({"user_id": user.user_id})
    rating = user_doc.get("rating", 1200) if user_doc else 1200
    
    profile = await generate_training_profile(db, user.user_id, rating)
    return profile


@api_router.get("/training/reflection-options")
async def get_reflection_options_endpoint(user: User = Depends(get_current_user)):
    """
    Get reflection options based on the user's active phase.
    
    Returns tagged options the user can select from to describe
    what happened in their game. These options update pattern weights.
    """
    from training_profile_service import get_reflection_options
    
    options = await get_reflection_options(db, user.user_id)
    return options


@api_router.post("/training/reflection")
async def save_reflection_endpoint(
    game_id: str,
    reflection_data: Dict = Body(...),
    user: User = Depends(get_current_user)
):
    """
    Save a reflection for a specific game.
    
    Body:
    - selected_tags: List of pattern tags (e.g., ["rushing", "threat_blindness"])
    - free_text: Optional free-form reflection text
    
    This updates pattern weights to improve personalization.
    """
    from training_profile_service import save_reflection
    
    result = await save_reflection(db, user.user_id, game_id, reflection_data)
    return result


@api_router.get("/training/drills")
async def get_training_drills(
    limit: int = 5,
    user: User = Depends(get_current_user)
):
    """
    Get drill positions for training.
    
    Sources drills from:
    1. User's own mistakes (priority)
    2. Similar users' mistakes (same rating band, same micro habit)
    
    Each drill contains:
    - fen: Position to practice
    - correct_move: The better move
    - user_move: What was played (if from user's game)
    - cp_loss: How much the mistake cost
    - source: "own_game" or "similar_user"
    """
    from training_profile_service import get_drill_positions
    
    drills = await get_drill_positions(db, user.user_id, limit)
    return {"drills": drills, "count": len(drills)}


@api_router.get("/training/layer-info")
async def get_layer_info():
    """
    Get information about training layers and patterns.
    
    Returns static information for UI display.
    """
    from training_profile_service import TRAINING_LAYERS, PATTERN_INFO
    
    return {
        "layers": TRAINING_LAYERS,
        "patterns": PATTERN_INFO,
    }


@api_router.get("/training/game/{game_id}/milestones")
async def get_game_milestones(
    game_id: str,
    user: User = Depends(get_current_user)
):
    """
    Get ALL mistakes/milestones from a game for reflection.
    
    Rating-based filtering:
    - <1000: Only blunders (≥200cp)
    - 1000-1400: Blunders + big mistakes (≥150cp)
    - 1400-1800: All mistakes (≥100cp)
    - 1800+: Including inaccuracies (≥50cp)
    
    Each milestone includes:
    - Position FEN, move played, better move
    - PV lines for interactive board
    - Threat info if applicable
    - Contextual reflection options
    """
    from training_profile_service import get_game_milestones_for_reflection
    
    # Get user rating
    user_doc = await db.users.find_one({"user_id": user.user_id})
    rating = user_doc.get("rating", 1200) if user_doc else 1200
    
    result = await get_game_milestones_for_reflection(db, user.user_id, game_id, rating)
    return result


@api_router.post("/training/milestone/explain")
async def explain_milestone(
    milestone_data: Dict = Body(...),
    user: User = Depends(get_current_user)
):
    """
    Generate human-readable explanation for why better move is better.
    
    Uses Stockfish data (deterministic) + GPT for natural language.
    
    Body:
    - context_for_explanation: The milestone's context data
    - fen: Position FEN
    - move_played: What user played
    - best_move: What was better
    """
    from training_profile_service import generate_position_explanation
    
    # Get user rating category
    user_doc = await db.users.find_one({"user_id": user.user_id})
    rating = user_doc.get("rating", 1200) if user_doc else 1200
    
    milestone_data["rating_category"] = "beginner" if rating < 1000 else "intermediate" if rating < 1400 else "club" if rating < 1800 else "advanced"
    
    explanation = await generate_position_explanation(db, milestone_data, use_llm=True)
    
    # If LLM humanization needed, call GPT
    if explanation.get("needs_llm_humanization"):
        try:
            from emergentintegrations.llm.chat import LlmChat, UserMessage
            import os
            
            api_key = os.environ.get("EMERGENT_LLM_KEY", OPENAI_API_KEY)
            
            chat = LlmChat(
                api_key=api_key,
                session_id=f"explain_{os.urandom(8).hex()}",
                system_message="You are a chess coach explaining moves to amateur players. Be concrete and simple. Focus on the 'what happens' not abstract strategy."
            ).with_model("openai", "gpt-4o-mini")
            
            response = await chat.send_message(UserMessage(text=explanation["llm_prompt"]))
            
            explanation["human_explanation"] = response
        except Exception as e:
            logger.error(f"Error generating explanation: {e}")
            # Fallback to stockfish analysis
            sf_analysis = explanation.get("stockfish_analysis", {})
            explanation["human_explanation"] = f"{sf_analysis.get('position_context', 'In this position')}, you played {explanation['move_played']} but {explanation['best_move']} was better. {sf_analysis.get('threat_missed', '')} {sf_analysis.get('cp_lost', '')}."
    
    return explanation


@api_router.post("/training/plan/describe")
async def describe_plan_moves(
    plan_data: Dict = Body(...),
    user: User = Depends(get_current_user)
):
    """
    Convert a sequence of chess moves into a VERIFIED description of the plan.
    
    This uses actual chess analysis to understand what moves DO, not LLM guessing.
    
    Body:
    - fen: Starting position FEN
    - moves: List of moves in SAN notation (e.g., ["Nf3", "e4", "d4"])
    - user_playing_color: "white" or "black" - which color the user was playing in the game
    - turn_to_move: "white" or "black" - whose turn it is in this position
    - user_move: What the user actually played (the mistake)
    - best_move: What was the better move
    """
    fen = plan_data.get("fen")
    moves = plan_data.get("moves", [])
    user_playing_color = plan_data.get("user_playing_color", "white")
    turn_to_move = plan_data.get("turn_to_move", "white")
    user_move = plan_data.get("user_move", "")
    best_move = plan_data.get("best_move", "")
    
    if not fen or not moves:
        return {"error": "Missing fen or moves", "plan_description": ""}
    
    # Use VERIFIED chess analysis instead of LLM guessing
    try:
        from plan_interpretation_service import generate_reflection_from_plan
        
        result = generate_reflection_from_plan(
            fen=fen,
            plan_moves=moves,
            user_move=user_move,
            best_move=best_move,
            eval_change=plan_data.get("eval_change", 0.0)
        )
        
        return {
            "plan_description": result.get("thought", f"I was thinking about: {' '.join(moves)}"),
            "moves": moves,
            "fen": fen,
            "behavioral_tags": result.get("behavioral_tags", []),
            "verified": result.get("verified", False),
            "interpretation": result.get("plan_interpretation", {}),
        }
    except Exception as e:
        logger.error(f"Error interpreting plan: {e}")
        # Fallback: just list the moves
        moves_str = " ".join([
            f"{i//2 + 1}. {moves[i]}" if i % 2 == 0 else moves[i]
            for i in range(len(moves))
        ])
        return {
            "plan_description": f"I was thinking about playing: {moves_str}",
            "moves": moves,
            "fen": fen,
            "error": str(e)
        }


@api_router.post("/training/milestone/reflect")
async def save_milestone_reflection(
    game_id: str,
    move_number: int,
    reflection_data: Dict = Body(...),
    user: User = Depends(get_current_user)
):
    """
    Save reflection for a SPECIFIC position/milestone.
    
    Body:
    - selected_tags: List of contextual tags (e.g., "missed_threat", "time_pressure")
    - user_plan: What the user was thinking/planning (free text)
    - understood: Whether user understood the explanation
    - fen: Position FEN
    """
    from training_profile_service import save_position_reflection
    
    result = await save_position_reflection(db, user.user_id, game_id, move_number, reflection_data)
    return result


@api_router.get("/training/last-game-for-reflection")
async def get_last_game_for_reflection(user: User = Depends(get_current_user)):
    """
    Get the user's last analyzed game ID for reflection.
    """
    # Find last analyzed game
    last_analysis = await db.game_analyses.find_one(
        {"user_id": user.user_id},
        {"game_id": 1},
        sort=[("analyzed_at", -1)]
    )
    
    if not last_analysis:
        return {"game_id": None, "error": "No analyzed games found"}
    
    return {"game_id": last_analysis["game_id"]}


@api_router.get("/training/phase-progress")
async def get_phase_progress_endpoint(user: User = Depends(get_current_user)):
    """
    Get user's progress within their current training phase.
    
    Returns:
    - games_in_phase: How many games analyzed
    - progress_percent: Overall progress toward graduation
    - clean_games: Games without target pattern errors
    - improvement_percent: Pattern reduction percentage
    - trend: "improving" | "stable" | "regressing"
    - ready_to_graduate: Boolean
    """
    from training_profile_service import get_phase_progress
    
    result = await get_phase_progress(db, user.user_id)
    return result


@api_router.get("/training/reflection-history")
async def get_reflection_history_endpoint(user: User = Depends(get_current_user)):
    """
    Get user's reflection history with pattern evolution.
    
    Returns:
    - reflections: List of past reflections
    - tag_counts: How often each issue was identified
    - top_patterns: Most common patterns
    - user_plans: What user wrote during reflections
    """
    from training_profile_service import get_reflection_history
    
    result = await get_reflection_history(db, user.user_id, limit=50)
    return result


@api_router.get("/training/ai-insights")
async def get_ai_insights(user: User = Depends(get_current_user)):
    """
    Get AI-powered analysis of user's thinking patterns.
    
    Analyzes:
    - Common themes in their written plans
    - Recurring patterns in their mistakes
    - Personalized suggestions based on their data
    """
    from training_profile_service import generate_personalized_suggestions
    
    suggestion_data = await generate_personalized_suggestions(db, user.user_id)
    
    if not suggestion_data.get("ready_for_ai"):
        return suggestion_data
    
    # Use GPT to generate insights
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        import os
        
        api_key = os.environ.get("EMERGENT_LLM_KEY", OPENAI_API_KEY)
        
        chat = LlmChat(
            api_key=api_key,
            session_id=f"insights_{os.urandom(8).hex()}",
            system_message="You are a chess coach analyzing a player's thinking patterns. Be specific, reference their actual words, and give actionable advice."
        ).with_model("openai", "gpt-4o-mini")
        
        response = await chat.send_message(UserMessage(text=suggestion_data["prompt"]))
        
        return {
            "has_insights": True,
            "ai_analysis": response,
            "context": suggestion_data["context"],
        }
    except Exception as e:
        logger.error(f"Error generating AI insights: {e}")
        return {
            "has_insights": False,
            "error": "Could not generate AI insights",
            "context": suggestion_data.get("context", {}),
        }


# =============================================================================
# INTERACTIVE TRAINING ENDPOINTS (Phase 1)
# =============================================================================


@api_router.post("/training/puzzle/validate")
async def validate_puzzle_answer(
    data: dict,
    user: User = Depends(get_current_user)
):
    """
    Validate user's answer to a puzzle.
    
    Request body:
    - puzzle_id: str
    - user_answer: str (move in SAN notation)
    - correct_move: str
    - fen: str
    
    Returns feedback with explanation and teaching point.
    """
    from interactive_training_service import validate_puzzle_answer as validate_answer
    
    result = await validate_answer(
        db,
        user.user_id,
        data.get("puzzle_id"),
        data.get("user_answer"),
        data.get("correct_move"),
        data.get("fen")
    )
    
    # Update puzzle progression rating
    if result.get("correct") is not None:
        from puzzle_progression_service import record_puzzle_attempt
        
        difficulty = data.get("difficulty", "intermediate")
        progression = await record_puzzle_attempt(
            db,
            user.user_id,
            data.get("puzzle_id", "unknown"),
            difficulty,
            result.get("correct", False)
        )
        
        # Include progression info in result
        result["progression"] = {
            "old_rating": progression["old_rating"],
            "new_rating": progression["new_rating"],
            "rating_change": progression["rating_change"],
            "leveled_up": progression["leveled_up"],
            "new_level": progression["new_level"] if progression["leveled_up"] else None,
            "current_streak": progression["current_streak"],
            "new_achievements": progression["new_achievements"]
        }
    
    return result


# ============================================================================
# PUZZLE PROGRESSION SYSTEM
# ============================================================================

@api_router.get("/training/puzzle-progress")
async def get_puzzle_progress(user: User = Depends(get_current_user)):
    """
    Get user's puzzle progression data including rating, level, and stats.
    """
    from puzzle_progression_service import get_user_puzzle_progress
    
    progress = await get_user_puzzle_progress(db, user.user_id)
    return progress


@api_router.get("/training/puzzle-difficulty-recommendation")
async def get_puzzle_difficulty(user: User = Depends(get_current_user)):
    """
    Get recommended puzzle difficulty range for the user.
    """
    from puzzle_progression_service import get_recommended_puzzle_difficulty
    
    recommendation = await get_recommended_puzzle_difficulty(db, user.user_id)
    return recommendation


@api_router.get("/training/puzzle-leaderboard")
async def get_puzzle_leaderboard_endpoint(limit: int = 20):
    """
    Get global puzzle rating leaderboard.
    """
    from puzzle_progression_service import get_puzzle_leaderboard
    
    leaderboard = await get_puzzle_leaderboard(db, limit)
    return {"leaderboard": leaderboard}


@api_router.get("/training/weakness-patterns")
async def get_weakness_patterns(user: User = Depends(get_current_user)):
    """
    Get analysis of user's weakness patterns.
    
    Identifies:
    - Weakest game phase (opening/middlegame/endgame)
    - Common mistake types
    - Training recommendations
    """
    from interactive_training_service import get_user_weakness_patterns
    
    patterns = await get_user_weakness_patterns(db, user.user_id)
    
    return patterns


@api_router.get("/training/openings")
async def get_user_openings(user: User = Depends(get_current_user)):
    """
    Get user's most played openings with mastery levels.
    
    For future opening trainer feature.
    """
    from interactive_training_service import get_user_openings
    
    openings = await get_user_openings(db, user.user_id)
    
    return {
        "openings": openings,
        "total": len(openings)
    }


@api_router.get("/training/openings/stats")
async def get_opening_stats(user: User = Depends(get_current_user)):
    """
    Get detailed statistics on user's most-played openings with training content availability.
    Includes community comparison showing how user's accuracy compares to others at their rating level.
    """
    from opening_trainer_service import get_user_opening_stats, enrich_with_community_comparison
    
    stats = await get_user_opening_stats(db, user.user_id)
    
    # Enrich with community comparison data
    stats = await enrich_with_community_comparison(db, user.user_id, stats)
    
    return {
        "openings": stats,
        "total": len(stats)
    }


@api_router.get("/training/openings/{opening_key}")
async def get_opening_training_content(opening_key: str, user: User = Depends(get_current_user)):
    """
    Get training content for a specific opening including:
    - Key variations and move orders
    - Common traps (to set and avoid)
    - Typical plans and ideas
    - User's mistakes in this opening
    """
    from opening_trainer_service import get_opening_training_content
    
    content = await get_opening_training_content(db, user.user_id, opening_key)
    
    return content


@api_router.get("/training/openings/{opening_key}/quiz")
async def get_opening_quiz(opening_key: str, user: User = Depends(get_current_user)):
    """
    Generate quiz questions for an opening to test user's knowledge.
    """
    from opening_trainer_service import get_opening_quiz
    
    questions = await get_opening_quiz(db, user.user_id, opening_key)
    
    return {
        "opening": opening_key,
        "questions": questions
    }


@api_router.get("/training/openings-database")
async def get_openings_database():
    """
    Get the full openings database for reference/browsing.
    """
    from opening_trainer_service import OPENINGS_DATABASE
    
    # Format for frontend consumption
    openings = []
    for key, data in OPENINGS_DATABASE.items():
        openings.append({
            "key": key,
            "name": data["name"],
            "eco": data.get("eco", ""),
            "color": data["color"],
            "description": data["description"],
            "main_line": data["main_line"],
            "variations_count": len(data.get("common_variations", [])),
            "traps_count": len(data.get("traps", []))
        })
    
    return {
        "openings": openings,
        "total": len(openings)
    }


# ============================================================================
# TRICK LIBRARY ENDPOINTS
# ============================================================================

@api_router.get("/training/tricks")
async def get_all_tricks():
    """
    Get all traps in the trick library with metadata.
    """
    from trick_library_service import get_all_traps, get_trap_statistics, TRAP_CATEGORIES
    
    traps = get_all_traps()
    stats = get_trap_statistics()
    
    return {
        "traps": traps,
        "categories": TRAP_CATEGORIES,
        "statistics": stats
    }


@api_router.get("/training/tricks/categories")
async def get_trick_categories():
    """
    Get all trap categories.
    """
    from trick_library_service import TRAP_CATEGORIES, get_traps_by_category
    
    categories = []
    for key, cat_data in TRAP_CATEGORIES.items():
        traps = get_traps_by_category(key)
        categories.append({
            "key": key,
            "name": cat_data["name"],
            "description": cat_data["description"],
            "trap_count": len(traps),
            "trap_keys": cat_data["traps"]
        })
    
    return {"categories": categories}


# ============================================================================
# TRAP STATISTICS & TRACKING (Static routes - must come before {trap_key})
# ============================================================================

@api_router.post("/training/tricks/record-attempt")
async def record_trap_attempt_endpoint(request: Request, data: dict, user: User = Depends(get_current_user)):
    """
    Record a user's attempt on a trap practice mode.
    """
    from trap_stats_service import record_trap_attempt
    
    trap_key = data.get("trap_key")
    mode = data.get("mode")
    success = data.get("success")
    details = data.get("details", {})
    
    if not trap_key or not mode or success is None:
        raise HTTPException(status_code=400, detail="Missing required fields: trap_key, mode, success")
    
    if mode not in ["execution", "avoidance", "recognition"]:
        raise HTTPException(status_code=400, detail="Invalid mode")
    
    result = await record_trap_attempt(db, user.user_id, trap_key, mode, success, details)
    return result


@api_router.get("/training/tricks/stats")
async def get_user_trap_stats_endpoint(request: Request, user: User = Depends(get_current_user)):
    """Get comprehensive trap statistics for the current user."""
    from trap_stats_service import get_user_trap_stats
    stats = await get_user_trap_stats(db, user.user_id)
    return stats


@api_router.get("/training/tricks/recommendations")
async def get_trap_recommendations_endpoint(request: Request, user: User = Depends(get_current_user), limit: int = 5):
    """Get personalized trap recommendations for the current user."""
    from trap_stats_service import get_recommended_traps
    recommendations = await get_recommended_traps(db, user.user_id, limit)
    return {"recommendations": recommendations}


@api_router.get("/training/tricks/global-stats")
async def get_global_trap_stats_endpoint(request: Request):
    """Get global trap statistics across all users."""
    from trap_stats_service import get_global_trap_stats
    stats = await get_global_trap_stats(db)
    return stats


# ============================================================================
# TRAP DETAILS (Dynamic routes with {trap_key})
# ============================================================================

@api_router.get("/training/tricks/{trap_key}")
async def get_trick_details(trap_key: str):
    """
    Get detailed information about a specific trap.
    """
    from trick_library_service import get_trap_by_key
    
    trap = get_trap_by_key(trap_key)
    if not trap:
        raise HTTPException(status_code=404, detail="Trap not found")
    
    return trap


@api_router.get("/training/tricks/{trap_key}/practice")
async def get_trick_for_practice(trap_key: str, mode: str = "execution"):
    """
    Get a trap formatted for practice mode.
    
    Modes:
    - execution: Player tries to execute the trap (find the winning move)
    - avoidance: Player tries to avoid falling into the trap
    - recognition: Player identifies if there's a trap in the position
    """
    from trick_library_service import get_trap_for_practice
    
    if mode not in ["execution", "avoidance", "recognition"]:
        raise HTTPException(status_code=400, detail="Invalid mode. Use: execution, avoidance, recognition")
    
    practice_data = get_trap_for_practice(trap_key, mode)
    if not practice_data:
        raise HTTPException(status_code=404, detail="Trap not found")
    
    return practice_data


@api_router.post("/training/tricks/validate-avoidance")
async def validate_avoidance_move(data: dict):
    """
    Validate a move in avoidance mode.
    
    Checks if the user's move avoids the trap or falls into it.
    Uses Stockfish to evaluate if the move is safe.
    """
    import chess
    from stockfish_service import StockfishEngine
    
    fen = data.get("fen")
    user_move = data.get("user_move")
    trap_key = data.get("trap_key")
    winning_move = data.get("winning_move")  # The trap move opponent would play if allowed
    
    if not fen or not user_move:
        raise HTTPException(status_code=400, detail="Missing fen or user_move")
    
    try:
        board = chess.Board(fen)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid FEN")
    
    # Parse user's move
    try:
        move_obj = board.parse_san(user_move)
        move_san = board.san(move_obj)
    except Exception:
        return {"valid": False, "fell_into_trap": False, "message": f"Invalid move: {user_move}"}
    
    # Make the user's move
    board.push(move_obj)
    new_fen = board.fen()
    
    # Check if opponent can still play the winning/trap move after user's move
    try:
        trap_still_possible = False
        if winning_move:
            try:
                trap_move_obj = board.parse_san(winning_move)
                # If the trap move is still legal, check if it's still winning
                if trap_move_obj in board.legal_moves:
                    trap_still_possible = True
            except Exception:
                pass
        
        # Use Stockfish to evaluate the position after user's move
        engine = StockfishEngine()
        engine.start()
        
        try:
            # First, evaluate the position BEFORE the user's move
            board_before = chess.Board(fen)
            eval_before, mate_before = engine.evaluate_position(board_before, depth=12)
            
            # Now evaluate AFTER the user's move
            eval_after, mate_after = engine.evaluate_position(board, depth=12)
            
            # Determine who is the victim
            is_victim_white = data.get("user_color", "black") == "white"
            
            # Adjust evals to be from the victim's perspective
            # Positive = good for victim, Negative = bad for victim
            if is_victim_white:
                victim_eval_before = eval_before
                victim_eval_after = eval_after
            else:
                victim_eval_before = -eval_before
                victim_eval_after = -eval_after
            
            # Calculate how much the position changed
            eval_change = victim_eval_after - victim_eval_before
            
            # Check for mate threats after the move
            if mate_after is not None:
                if (is_victim_white and mate_after < 0) or (not is_victim_white and mate_after > 0):
                    # User is getting mated - fell into trap!
                    return {
                        "valid": True,
                        "fell_into_trap": True,
                        "is_safe": False,
                        "evaluation": eval_after,
                        "mate_in": mate_after,
                        "message": f"Oops! After {move_san}, you're getting mated in {abs(mate_after)}!",
                        "new_fen": new_fen
                    }
            
            # If there was a mate threat BEFORE and now there isn't, the move avoided the trap!
            if mate_before is not None and mate_after is None:
                return {
                    "valid": True,
                    "fell_into_trap": False,
                    "is_safe": True,
                    "evaluation": eval_after,
                    "message": f"Excellent! {move_san} avoids the checkmate threat!",
                    "new_fen": new_fen
                }
            
            # If the position got significantly WORSE (>200cp loss), they fell into trap
            if eval_change < -200:
                return {
                    "valid": True,
                    "fell_into_trap": True,
                    "is_safe": False,
                    "evaluation": eval_after,
                    "eval_change": eval_change,
                    "message": f"That move makes things worse! After {move_san}, your position deteriorated.",
                    "new_fen": new_fen
                }
            
            # If they're still in a very bad position (>500cp worse) AND didn't improve
            if victim_eval_after < -500 and eval_change < 100:
                return {
                    "valid": True,
                    "fell_into_trap": True,
                    "is_safe": False,
                    "evaluation": eval_after,
                    "message": f"Your position is still critical. {move_san} doesn't fully avoid the danger.",
                    "new_fen": new_fen
                }
            
            # Move is safe - position either improved or stayed stable
            if eval_change > 50:
                return {
                    "valid": True,
                    "fell_into_trap": False,
                    "is_safe": True,
                    "evaluation": eval_after,
                    "message": f"Great! {move_san} improves your position and avoids the trap!",
                    "new_fen": new_fen
                }
            else:
                return {
                    "valid": True,
                    "fell_into_trap": False,
                    "is_safe": True,
                    "evaluation": eval_after,
                    "message": f"Good! {move_san} is a solid defensive move.",
                    "new_fen": new_fen
                }
            
        finally:
            engine.stop()
            
    except Exception as e:
        logger.error(f"Error validating avoidance move: {e}")
        return {"valid": True, "fell_into_trap": False, "is_safe": True, "message": "Move accepted", "new_fen": new_fen}


@api_router.post("/training/tricks/validate-recognition")
async def validate_recognition_answer(data: dict):
    """
    Validate user's answer in recognition mode.
    
    User must identify:
    1. Whether there's a trap (yes/no)
    2. What the winning move is (if yes)
    """
    trap_key = data.get("trap_key")
    user_answer_has_trap = data.get("has_trap")  # Boolean: does user think there's a trap?
    user_winning_move = data.get("winning_move")  # What move does user think wins?
    
    from trick_library_service import get_trap_by_key
    
    trap = get_trap_by_key(trap_key)
    if not trap:
        raise HTTPException(status_code=404, detail="Trap not found")
    
    correct_has_trap = True  # All positions in our DB have traps
    correct_winning_move = trap.get("winning_move", "")
    
    # Check if user correctly identified trap presence
    recognized_trap = user_answer_has_trap == correct_has_trap
    
    # Check if user found the correct winning move (normalize notation)
    found_move = False
    if user_winning_move and correct_winning_move:
        # Normalize move notation for comparison
        user_move_clean = user_winning_move.replace("+", "").replace("#", "").replace("=", "")
        correct_move_clean = correct_winning_move.replace("+", "").replace("#", "").replace("=", "")
        found_move = user_move_clean.lower() == correct_move_clean.lower()
    
    # Calculate score
    if recognized_trap and found_move:
        score = "perfect"
        message = f"Excellent! You correctly identified the trap and found {correct_winning_move}!"
    elif recognized_trap and not user_winning_move:
        score = "good"
        message = f"Good! You spotted the danger. The winning move is {correct_winning_move}."
    elif recognized_trap and not found_move:
        score = "partial"
        message = f"You spotted the trap but missed the key move. The winning move is {correct_winning_move}."
    else:
        score = "missed"
        message = f"There IS a trap here! The winning move is {correct_winning_move}."
    
    return {
        "correct_has_trap": correct_has_trap,
        "correct_winning_move": correct_winning_move,
        "recognized_trap": recognized_trap,
        "found_winning_move": found_move,
        "score": score,
        "message": message,
        "explanation": trap.get("explanation", ""),
        "why_it_works": trap.get("why_it_works", ""),
        "key_squares": trap.get("key_squares", [])
    }


@api_router.get("/training/tricks/opening/{opening_name}")
async def get_tricks_for_opening(opening_name: str):
    """
    Get traps relevant to a specific opening.
    """
    from trick_library_service import get_traps_by_opening, get_recommended_traps_for_opening
    
    # Get direct matches
    direct_traps = get_traps_by_opening(opening_name)
    
    # Get recommendations
    recommendations = get_recommended_traps_for_opening(opening_name)
    
    return {
        "opening": opening_name,
        "traps": direct_traps,
        "recommendations": recommendations
    }


@api_router.get("/training/tricks/difficulty/{difficulty}")
async def get_tricks_by_difficulty(difficulty: str):
    """
    Get traps by difficulty level (beginner, intermediate, advanced).
    """
    from trick_library_service import get_traps_by_difficulty
    
    if difficulty not in ["beginner", "intermediate", "advanced"]:
        raise HTTPException(status_code=400, detail="Invalid difficulty. Use: beginner, intermediate, advanced")
    
    traps = get_traps_by_difficulty(difficulty)
    
    return {
        "difficulty": difficulty,
        "traps": traps,
        "count": len(traps)
    }


@api_router.get("/training/tricks/{trap_key}/leaderboard")
async def get_trap_leaderboard_endpoint(request: Request, trap_key: str, mode: str = "execution"):
    """Get leaderboard for a specific trap."""
    from trap_stats_service import get_trap_leaderboard
    
    if mode not in ["execution", "avoidance", "recognition"]:
        raise HTTPException(status_code=400, detail="Invalid mode")
    
    leaderboard = await get_trap_leaderboard(db, trap_key, mode)
    return {"trap_key": trap_key, "mode": mode, "leaderboard": leaderboard}


# ============================================================================
# COMMUNITY LEARNING (P2)
# ============================================================================

@api_router.post("/community/puzzles/share")
async def share_community_puzzle(request: Request, data: dict, user: User = Depends(get_current_user)):
    """Share a puzzle from user's games to the community."""
    from community_learning_service import share_puzzle
    result = await share_puzzle(db, user.user_id, data)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@api_router.get("/community/puzzles")
async def get_community_puzzles_endpoint(
    request: Request,
    difficulty: str = None,
    theme: str = None,
    opening: str = None,
    sort_by: str = "newest",
    skip: int = 0,
    limit: int = 20
):
    """Browse community puzzles with filtering."""
    from community_learning_service import get_community_puzzles
    
    # Get current user if authenticated
    user_id = None
    try:
        user = await get_current_user(request)
        user_id = user.user_id
    except Exception:
        pass
    
    result = await get_community_puzzles(
        db, user_id, difficulty, theme, opening, sort_by, skip, limit
    )
    return result


@api_router.post("/community/puzzles/{puzzle_id}/attempt")
async def attempt_community_puzzle_endpoint(
    request: Request,
    puzzle_id: str,
    data: dict,
    user: User = Depends(get_current_user)
):
    """Attempt to solve a community puzzle."""
    from community_learning_service import attempt_community_puzzle
    
    user_move = data.get("user_move")
    time_taken = data.get("time_taken")
    
    if not user_move:
        raise HTTPException(status_code=400, detail="Missing user_move")
    
    result = await attempt_community_puzzle(db, user.user_id, puzzle_id, user_move, time_taken)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@api_router.post("/community/puzzles/{puzzle_id}/rate")
async def rate_community_puzzle_endpoint(
    request: Request,
    puzzle_id: str,
    data: dict,
    user: User = Depends(get_current_user)
):
    """Rate a community puzzle (1-5 stars)."""
    from community_learning_service import rate_puzzle
    
    rating = data.get("rating")
    if not rating or not isinstance(rating, int):
        raise HTTPException(status_code=400, detail="Missing or invalid rating (must be 1-5)")
    
    result = await rate_puzzle(db, user.user_id, puzzle_id, rating)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@api_router.get("/community/stats")
async def get_community_stats_endpoint(request: Request):
    """Get overall community puzzle statistics."""
    from community_learning_service import get_community_stats
    stats = await get_community_stats(db)
    return stats


@api_router.get("/community/my-contributions")
async def get_my_contributions_endpoint(request: Request, user: User = Depends(get_current_user)):
    """Get current user's puzzle contributions."""
    from community_learning_service import get_user_contributions
    contributions = await get_user_contributions(db, user.user_id)
    return contributions


# ============================================================================
# LICHESS OPENING EXPLORER INTEGRATION
# ============================================================================

@api_router.get("/training/lichess/opening")
async def get_lichess_opening_data(
    moves: str = None,  # Comma-separated SAN moves, e.g., "e4,e5,Nf3"
    source: str = "lichess"  # "lichess" or "masters"
):
    """
    Fetch opening data from Lichess Opening Explorer.
    
    Returns real statistics from millions of games including:
    - Opening name and ECO code
    - Win/draw/loss percentages
    - Most popular continuations with statistics
    """
    from lichess_opening_service import get_opening_info
    
    move_list = moves.split(",") if moves else []
    data = await get_opening_info(move_list, source=source)
    
    return data


@api_router.get("/training/lichess/variations")
async def get_lichess_variations(
    moves: str = None,  # Comma-separated SAN moves
    depth: int = 3
):
    """
    Get popular variations from a position using Lichess data.
    
    Explores the most common continuations up to the specified depth.
    """
    from lichess_opening_service import get_opening_variations
    
    move_list = moves.split(",") if moves else []
    variations = await get_opening_variations(move_list, depth=min(depth, 5))
    
    return {
        "starting_moves": move_list,
        "variations": variations
    }


@api_router.get("/training/lichess/search")
async def search_lichess_opening(name: str):
    """
    Search for an opening by name and get Lichess statistics.
    
    Examples: "Italian Game", "Sicilian Najdorf", "Queen's Gambit"
    """
    from lichess_opening_service import search_opening_by_name
    
    data = await search_opening_by_name(name)
    
    if not data:
        return {"error": f"Opening '{name}' not found"}
    
    return data


@api_router.get("/training/progress")
async def get_training_progress(user: User = Depends(get_current_user)):
    """
    Get user's training progress and stats.
    """
    from interactive_training_service import get_training_progress
    
    progress = await get_training_progress(db, user.user_id)
    
    return progress


# =============================================================================
# POSITION ANALYSIS ENDPOINTS (Stockfish + Cache)
# =============================================================================

@api_router.get("/eval/position")
async def analyze_position_endpoint(
    fen: str,
    depth: int = 18
):
    """
    Analyze a chess position using Stockfish with caching.
    
    - First request: ~2 seconds (Stockfish runs)
    - Subsequent requests: Instant (from cache)
    
    Returns evaluation, best move, and principal variation.
    """
    from position_analysis_cache_service import PositionAnalysisService
    
    service = PositionAnalysisService(db)
    result = await service.get_position_eval(fen, depth=depth)
    
    return result


@api_router.get("/eval/best-move")
async def get_best_move_endpoint(fen: str, depth: int = 18):
    """
    Quick endpoint to get just the best move for a position.
    """
    from position_analysis_cache_service import PositionAnalysisService
    
    service = PositionAnalysisService(db)
    best_move = await service.get_best_move(fen, depth=depth)
    
    return {
        "fen": fen,
        "best_move": best_move
    }


@api_router.post("/eval/move")
async def analyze_move_endpoint(
    fen: str,
    move: str,
    depth: int = 18
):
    """
    Analyze a specific move - get evaluation and classification.
    
    Args:
        fen: Position before the move
        move: The move played (SAN or UCI format)
    
    Returns:
        Move analysis with cp_loss and classification (blunder/mistake/etc)
    """
    from position_analysis_cache_service import PositionAnalysisService
    
    service = PositionAnalysisService(db)
    result = await service.analyze_move(fen, move, depth=depth)
    
    return result


@api_router.get("/eval/cache-stats")
async def get_eval_cache_stats():
    """Get cache statistics."""
    from position_analysis_cache_service import PositionAnalysisService
    
    service = PositionAnalysisService(db)
    stats = await service.get_cache_stats()
    
    return stats


# =============================================================================
# COACHING LOOP ENDPOINTS (GOLD FEATURE)
# =============================================================================

@api_router.get("/round-preparation")
async def get_round_preparation(user: User = Depends(get_current_user)):
    """
    Get Round Preparation (Next Game Plan).
    
    This is the coach's plan for the user's next game.
    Generated using the DETERMINISTIC ADAPTIVE COACH system.
    
    Inputs used:
    - Rating band (granular: 600-1000, 1000-1400, 1400-1800, 1800+)
    - Last 25 games fundamentals profile
    - Weakness patterns with evidence
    - Opening stability recommendations
    - Domain history (consecutive misses/executions)
    - Critical insights from last game's mistakes
    
    Intensity (1-5) adjusts per domain based on consecutive failures.
    """
    from deterministic_coach_service import generate_round_preparation
    
    plan = await generate_round_preparation(db, user.user_id)
    
    # Remove audit fields for preparation view (they should be empty anyway)
    for card in plan.get("cards", []):
        card["audit"] = {"status": None, "data_points": [], "evidence": [], "coach_note": None}
    
    return plan


@api_router.get("/plan-audit")
async def get_plan_audit_data(user: User = Depends(get_current_user)):
    """
    Get Plan Audit (Last Game vs Previous Plan).
    
    Evaluates the user's last analyzed game against the plan we gave them.
    This is NOT a game summary - it's compliance evaluation.
    
    Uses DETERMINISTIC ADAPTIVE COACH for:
    - Rating-band adjusted thresholds
    - Evidence-backed audit items (links to specific moves)
    - Deterministic coach notes
    
    Returns the audited PlanCard with status (executed/partial/missed) for each domain.
    """
    from deterministic_coach_service import generate_plan_audit
    
    result = await generate_plan_audit(db, user.user_id)
    return result


@api_router.post("/coaching-loop/audit-game/{game_id}")
async def audit_specific_game(game_id: str, user: User = Depends(get_current_user)):
    """
    Manually trigger audit for a specific game.
    
    This is called after game analysis completes to:
    1. Audit the game against the current plan
    2. Generate a new plan for the next game (adaptive loop continues)
    """
    from deterministic_coach_service import (
        audit_game_against_plan,
        generate_round_preparation,
        get_coaching_profile
    )
    
    # Get the active plan
    active_plan = await db.user_plans.find_one(
        {"user_id": user.user_id, "is_active": True, "is_audited": False},
        {"_id": 0}
    )
    
    if not active_plan:
        # Generate a plan first
        active_plan = await generate_round_preparation(db, user.user_id)
    
    # Get game and analysis
    game = await db.games.find_one({"game_id": game_id, "user_id": user.user_id}, {"_id": 0})
    analysis = await db.game_analyses.find_one({"game_id": game_id, "user_id": user.user_id}, {"_id": 0})
    
    if not game or not analysis:
        return {"error": "Game or analysis not found"}
    
    # Audit the game
    audited_plan = audit_game_against_plan(active_plan, game, analysis)
    
    # Update plan in database
    await db.user_plans.update_one(
        {"plan_id": active_plan["plan_id"]},
        {"$set": audited_plan}
    )
    
    # Generate new plan (adaptive loop continues)
    new_plan = await generate_round_preparation(db, user.user_id)
    
    return {
        "audited_plan": audited_plan,
        "new_plan": new_plan
    }


@api_router.post("/coaching-loop/regenerate-plan")
async def regenerate_plan(user: User = Depends(get_current_user)):
    """
    Force regenerate the user's plan.
    
    Use this if the user wants a fresh plan without auditing.
    Uses the DETERMINISTIC ADAPTIVE COACH system.
    """
    from deterministic_coach_service import generate_round_preparation
    
    # Invalidate existing active plans
    await db.user_plans.update_many(
        {"user_id": user.user_id, "is_active": True},
        {"$set": {"is_active": False}}
    )
    
    # Generate fresh plan
    plan = await generate_round_preparation(db, user.user_id)
    
    return plan


@api_router.get("/coaching-loop/profile")
async def get_coaching_loop_profile(user: User = Depends(get_current_user)):
    """
    Get the user's full coaching profile.
    
    Returns all the inputs used for DETERMINISTIC ADAPTIVE COACH:
    - Rating band (granular: 600-1000, 1000-1400, 1400-1800, 1800+)
    - Fundamentals profile (last 25 games)
    - Weakness patterns with evidence
    - Opening stability recommendations
    - Domain history (consecutive misses/executions)
    - Training block with intensity (1-5)
    """
    from deterministic_coach_service import get_coaching_profile
    
    profile = await get_coaching_profile(db, user.user_id)
    return profile


@api_router.get("/journey/v2")
async def get_journey_page_data(user: User = Depends(get_current_user)):
    """
    Get data for the Journey page (TREND - How you're evolving)
    
    Returns:
    - Baseline vs Current progress tracking
    - Baseline patterns (weaknesses from first games)
    - Current patterns (weaknesses from recent games)
    - Pattern comparison (improvement/regression per weakness)
    - Weakness ranking (not equal badges)
    - Win-state analysis
    - Identity profile
    """
    from baseline_service import (
        get_or_create_baseline,
        get_baseline_patterns,
        calculate_current_stats,
        calculate_progress,
        calculate_pattern_snapshot,
        compare_patterns,
        MIN_GAMES_FOR_BASELINE
    )
    
    # Get ALL analyses for baseline calculation
    all_analyses = await db.game_analyses.find(
        {"user_id": user.user_id}
    ).sort("created_at", -1).to_list(200)
    
    # Get last 25 games for current stats
    analyses = all_analyses[:25] if len(all_analyses) > 25 else all_analyses
    
    # Get ALL games for baseline, last 25 for current
    all_games = await db.games.find(
        {"user_id": user.user_id}
    ).sort("imported_at", -1).to_list(200)
    
    games = all_games[:25] if len(all_games) > 25 else all_games
    
    # Get or create baseline profile
    baseline = await get_or_create_baseline(db, user.user_id, all_analyses, all_games)
    
    # Get baseline patterns (weaknesses from first games)
    baseline_patterns = await get_baseline_patterns(db, user.user_id)
    
    # If baseline exists but patterns don't (legacy user), create patterns now
    if baseline and not baseline_patterns:
        baseline_analyses = sorted(all_analyses, key=lambda x: x.get('created_at', ''))[:MIN_GAMES_FOR_BASELINE]
        baseline_games = sorted(all_games, key=lambda x: x.get('imported_at', ''))[:MIN_GAMES_FOR_BASELINE]
        baseline_patterns = calculate_pattern_snapshot(baseline_analyses, baseline_games)
        
        # Save it for future use
        await db.users.update_one(
            {'user_id': user.user_id},
            {'$set': {'baseline_patterns': baseline_patterns}}
        )
    
    # Calculate current stats from recent 25 games
    current_stats = calculate_current_stats(analyses, games)
    
    # Calculate current patterns
    current_patterns = calculate_pattern_snapshot(analyses, games) if analyses else None
    
    # Calculate progress if baseline exists
    progress = None
    if baseline and current_stats:
        progress = calculate_progress(baseline, current_stats)
    
    # Calculate pattern comparison
    pattern_comparison = None
    if baseline_patterns and current_patterns:
        pattern_comparison = compare_patterns(baseline_patterns, current_patterns)
    
    # Get existing badge data
    badge_data = await calculate_all_badges(db, user.user_id)
    
    journey_data = get_journey_data(analyses, games, badge_data)
    
    # Add baseline and progress tracking
    journey_data['baseline'] = baseline
    journey_data['current_stats'] = current_stats
    journey_data['progress'] = progress
    journey_data['has_baseline'] = baseline is not None
    journey_data['games_until_baseline'] = max(0, MIN_GAMES_FOR_BASELINE - len(all_analyses)) if not baseline else 0
    
    # Add pattern data for Before/After tabs
    journey_data['baseline_patterns'] = baseline_patterns
    journey_data['current_patterns'] = current_patterns
    journey_data['pattern_comparison'] = pattern_comparison
    
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
    - Pattern context (longitudinal tracking)
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
    
    # Get all analyses and games for pattern tracking
    all_analyses = await db.game_analyses.find(
        {"user_id": user.user_id},
        {"_id": 0}
    ).to_list(100)
    
    # Include more fields for rich pattern context
    all_games = await db.games.find(
        {"user_id": user.user_id},
        {"_id": 0, "game_id": 1, "user_color": 1, "white_player": 1, "black_player": 1, 
         "opponent_name": 1, "result": 1, "imported_at": 1,
         "white_rating": 1, "black_rating": 1, "time_control": 1, 
         "opening": 1, "opening_name": 1, "eco": 1}
    ).to_list(100)
    
    # Add similar games (Behavior Memory)
    similar_games = find_similar_pattern_games(analysis, all_analyses, all_games)
    lab_data["similar_games"] = similar_games
    
    # Add pattern context (longitudinal tracking) - THE GOLDEN INFORMATION with SPECIFIC insights
    pattern_history = build_pattern_history(user.user_id, all_analyses, all_games)
    game_pattern_summary = get_game_pattern_summary(analysis, pattern_history, all_games, game)
    
    lab_data["pattern_context"] = {
        "summary": game_pattern_summary,
        "history": {
            "most_recurring": pattern_history.get("most_recurring"),
            "improving_patterns": pattern_history.get("improving_patterns", []),
            "fixed_patterns": pattern_history.get("fixed_patterns", []),
        },
        # NEW: Global vulnerability insights
        "global_insights": {
            "rating_vulnerable": pattern_history.get("rating_vulnerable"),
            "time_vulnerable": pattern_history.get("time_vulnerable"),
            "opening_triggers": pattern_history.get("opening_triggers", []),
        }
    }
    
    return lab_data


@api_router.get("/lab/{game_id}/mistake/{move_number}/context")
async def get_mistake_pattern_context(game_id: str, move_number: int, user: User = Depends(get_current_user)):
    """
    Get pattern context for a specific mistake in a game.
    Shows if this pattern has occurred before and in which games.
    
    THE GOLDEN INFORMATION:
    - "You made this same mistake in 3 other games"
    - "You did this against opponent X too"  
    - "You FIXED this! Compare to your game vs Y"
    """
    # Get the analysis for this game
    analysis = await db.game_analyses.find_one({
        "game_id": game_id,
        "user_id": user.user_id
    })
    
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    
    # Find the specific mistake
    sf = analysis.get("stockfish_analysis", {})
    evals = sf.get("move_evaluations", [])
    
    mistake = None
    for e in evals:
        if e.get("move_number") == move_number and e.get("evaluation") in ["blunder", "mistake"]:
            mistake = {
                "move_number": e.get("move_number"),
                "move": e.get("move"),
                "threat": e.get("threat"),
                "cp_loss": e.get("cp_loss"),
            }
            break
    
    if not mistake:
        return {"context": None, "message": "No mistake found at this move"}
    
    # Get all analyses and games for pattern history
    all_analyses = await db.game_analyses.find(
        {"user_id": user.user_id},
        {"_id": 0}
    ).to_list(100)
    
    all_games = await db.games.find(
        {"user_id": user.user_id},
        {"_id": 0, "game_id": 1, "user_color": 1, "white_player": 1, "black_player": 1, "opponent_name": 1, "result": 1, "imported_at": 1}
    ).to_list(100)
    
    # Build pattern history and get context
    pattern_history = build_pattern_history(user.user_id, all_analyses, all_games)
    context = get_pattern_context_for_mistake(mistake, game_id, pattern_history, all_games)
    
    return {
        "mistake": mistake,
        "context": context,
    }


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
    ).sort("imported_at", -1).limit(15).to_list(15)
    
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


# ==================== USER THOUGHT / GOLD DATA ROUTES ====================

class UserThoughtRequest(BaseModel):
    """Request for saving user's thought on a specific move."""
    move_number: int
    fen: str
    thought_text: str
    move_played: Optional[str] = None
    best_move: Optional[str] = None
    evaluation_type: Optional[str] = None  # "blunder", "mistake", "inaccuracy"
    cp_loss: Optional[int] = None


@api_router.post("/games/{game_id}/thought")
async def save_user_thought(
    game_id: str,
    request: UserThoughtRequest,
    user: User = Depends(get_current_user)
):
    """
    Save a user's thought on a specific mistake in a game.
    
    This is "Gold Data" - the user's own understanding of what they
    were thinking when they made a mistake. Used for future pattern
    analysis to identify recurring thought patterns.
    
    Stored with full context:
    - game_id, move_number, fen
    - user_rating at time of game
    - the thought text
    - what move was played vs what was best
    - evaluation type and cp loss
    """
    # Verify game exists and belongs to user
    game = await db.games.find_one(
        {"game_id": game_id, "user_id": user.user_id},
        {"_id": 0}
    )
    
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    
    # Get user's rating (current or from game if available)
    user_doc = await db.users.find_one({"user_id": user.user_id}, {"_id": 0, "rating": 1})
    user_rating = user_doc.get("rating", 1200) if user_doc else 1200
    
    # Create thought document
    thought_id = f"thought_{uuid.uuid4().hex[:12]}"
    thought_doc = {
        "thought_id": thought_id,
        "user_id": user.user_id,
        "game_id": game_id,
        "move_number": request.move_number,
        "fen": request.fen,
        "thought_text": request.thought_text,
        "move_played": request.move_played,
        "best_move": request.best_move,
        "evaluation_type": request.evaluation_type,
        "cp_loss": request.cp_loss,
        "user_rating": user_rating,
        "created_at": datetime.now(timezone.utc).isoformat(),
        # Additional context from game
        "platform": game.get("platform"),
        "opponent": game.get("black_player") if game.get("user_color") == "white" else game.get("white_player"),
        "result": game.get("result"),
    }
    
    # Check if thought already exists for this game/move
    existing = await db.user_thoughts.find_one({
        "user_id": user.user_id,
        "game_id": game_id,
        "move_number": request.move_number
    })
    
    if existing:
        # Update existing thought
        await db.user_thoughts.update_one(
            {"thought_id": existing["thought_id"]},
            {"$set": {
                "thought_text": request.thought_text,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }}
        )
        return {
            "success": True,
            "thought_id": existing["thought_id"],
            "message": "Thought updated"
        }
    
    # Insert new thought
    await db.user_thoughts.insert_one(thought_doc)
    
    logger.info(f"Saved user thought for game {game_id}, move {request.move_number}")
    
    return {
        "success": True,
        "thought_id": thought_id,
        "message": "Thought saved - thank you for sharing!"
    }


@api_router.get("/games/{game_id}/thoughts")
async def get_game_thoughts(game_id: str, user: User = Depends(get_current_user)):
    """
    Get all thoughts the user has recorded for a specific game.
    """
    thoughts = await db.user_thoughts.find(
        {"user_id": user.user_id, "game_id": game_id},
        {"_id": 0}
    ).sort("move_number", 1).to_list(100)
    
    return {
        "game_id": game_id,
        "thoughts": thoughts,
        "count": len(thoughts)
    }


@api_router.get("/thoughts/all")
async def get_all_user_thoughts(user: User = Depends(get_current_user)):
    """
    Get all thoughts the user has recorded across all games.
    Useful for pattern analysis.
    """
    thoughts = await db.user_thoughts.find(
        {"user_id": user.user_id},
        {"_id": 0}
    ).sort("created_at", -1).to_list(200)
    
    # Group by evaluation type for pattern analysis
    by_type = {}
    for t in thoughts:
        eval_type = t.get("evaluation_type", "unknown")
        if eval_type not in by_type:
            by_type[eval_type] = []
        by_type[eval_type].append(t)
    
    return {
        "thoughts": thoughts,
        "count": len(thoughts),
        "by_evaluation_type": {k: len(v) for k, v in by_type.items()}
    }



# ============================================================
# COGNITIVE PATTERNS API (Diagnosis + Prescription + Audit)
# ============================================================

@api_router.get("/cognitive/journey")
async def get_cognitive_journey(user: User = Depends(get_current_user)):
    """
    Journey Page - 3-Tab Cognitive Progress Tracker (Master Spec v4)
    
    Tab A (Now): Snapshot - 5 items + directive
    Tab B (Journey): 4 stat rows + 4 cognitive rows + directive
    Tab C (Trend): Headline + shifts + evidence + directive
    
    INTEGRATES: Stat Interpretation Engine + Coach Voice Generator
    """
    from journey_engine import compute_journey
    
    # Get analyzed games - include ALL games for the user
    # Previously filtered by onboarding_date but this excluded pre-existing games
    all_analyses = await db.game_analyses.find(
        {"user_id": user.user_id},
        {"_id": 0, "stockfish_analysis": 1, "created_at": 1, "user_color": 1, "game_id": 1, "user_result": 1}
    ).sort("created_at", -1).to_list(100)
    
    # Compute journey with integrated engines
    result = compute_journey(all_games=all_analyses)
    
    return result


@api_router.get("/cognitive/patterns")
async def get_cognitive_patterns(user: User = Depends(get_current_user)):
    """
    Get aggregated cognitive patterns from user's games.
    
    Returns:
    - patterns: Dict of cognitive categories with frequency, severity, trend
    - thinking_stability_index: 0-100 score
    - tsi_trend: improving/worsening/stable
    """
    from cognitive_patterns_service import aggregate_cognitive_patterns
    
    result = await aggregate_cognitive_patterns(db, user.user_id)
    return result


@api_router.get("/cognitive/weaknesses")
async def get_prioritized_weaknesses_api(user: User = Depends(get_current_user)):
    """
    Get prioritized list of cognitive weaknesses.
    
    Only includes patterns that cross the threshold.
    Used by Training page for prescription.
    """
    from cognitive_patterns_service import get_prioritized_weaknesses
    
    weaknesses = await get_prioritized_weaknesses(db, user.user_id)
    return {"weaknesses": weaknesses}


@api_router.get("/cognitive/training-priority")
async def get_training_priority(user: User = Depends(get_current_user)):
    """
    Get training content prioritization based on user's weaknesses.
    
    Returns:
    - primary_focus: Main weakness to address
    - secondary_focus: Additional weaknesses
    - puzzle_priority_order: Types of puzzles to prioritize
    - trap_priority_order: Types of traps to prioritize
    - general_drills: If no specific weakness, show general drills
    """
    from cognitive_patterns_service import (
        get_prioritized_weaknesses,
        get_training_prioritization
    )
    
    weaknesses = await get_prioritized_weaknesses(db, user.user_id)
    prioritization = get_training_prioritization(weaknesses)
    
    return prioritization


@api_router.post("/cognitive/focus/activate")
async def activate_focus(
    data: dict,
    user: User = Depends(get_current_user)
):
    """
    Activate a focus module for the user.
    
    Body: { "category": "missed_forcing_move" }
    
    Starts audit tracking for next 5 games.
    """
    from cognitive_patterns_service import activate_focus_module
    
    category = data.get("category")
    if not category:
        raise HTTPException(400, "category is required")
    
    result = await activate_focus_module(db, user.user_id, category)
    return result


@api_router.get("/cognitive/focus/status")
async def get_focus_status(user: User = Depends(get_current_user)):
    """
    Get current focus module status.
    """
    from cognitive_patterns_service import get_focus_module_status
    
    status = await get_focus_module_status(db, user.user_id)
    if not status:
        return {"active": False}
    
    return {
        "active": True,
        "category": status.get("active_category"),
        "activated_at": status.get("activated_at")
    }


@api_router.get("/cognitive/focus/progress")
async def get_focus_progress(user: User = Depends(get_current_user)):
    """
    Evaluate progress on active focus module.
    
    Compares baseline (10 games before) vs audit window (5 games after).
    """
    from cognitive_patterns_service import evaluate_focus_progress
    
    progress = await evaluate_focus_progress(db, user.user_id)
    if not progress:
        return {"active": False, "message": "No focus module active"}
    
    return progress


@api_router.get("/cognitive/tsi")
async def get_thinking_stability_index(user: User = Depends(get_current_user)):
    """
    Get Thinking Stability Index.
    
    Simple derived metric showing overall thinking stability.
    """
    from cognitive_patterns_service import aggregate_cognitive_patterns
    
    result = await aggregate_cognitive_patterns(db, user.user_id, num_games=20)
    
    return {
        "thinking_stability_index": result.get("thinking_stability_index", 100),
        "trend": result.get("tsi_trend", "stable"),
        "games_analyzed": result.get("games_analyzed", 0)
    }


@api_router.get("/cognitive/trend")
async def get_cognitive_trend(user: User = Depends(get_current_user)):
    """
    Get TSI trend data for last 30 games.
    
    Returns array of {game_num, value} for charting.
    """
    from cognitive_patterns_service import aggregate_cognitive_patterns
    
    # Get analyses for last 30 games
    analyses = await db.game_analyses.find(
        {"user_id": user.user_id},
        {"_id": 0, "stockfish_analysis": 1, "created_at": 1}
    ).sort("created_at", -1).limit(30).to_list(30)
    
    if not analyses:
        return {"data": []}
    
    # Calculate rolling TSI for each game window
    trend_data = []
    analyses.reverse()  # Oldest first
    
    for i in range(len(analyses)):
        # Use a sliding window of up to 5 games
        window_start = max(0, i - 4)
        window = analyses[window_start:i + 1]
        
        # Simple TSI approximation based on mistake severity in window
        total_mistakes = 0
        total_severity = 0
        
        for analysis in window:
            sf = analysis.get("stockfish_analysis", {})
            for move in sf.get("move_evaluations", []):
                cp_loss = abs(move.get("cp_loss", 0))
                if cp_loss >= 50:  # Significant mistake
                    total_mistakes += 1
                    total_severity += min(1.0, cp_loss / 300)
        
        # Calculate TSI for this window (100 = perfect, 0 = very bad)
        if total_mistakes > 0:
            avg_severity = total_severity / total_mistakes
            # Normalize: assume max 5 mistakes per game at 0.5 severity
            normalized = min(1.0, (total_mistakes * avg_severity) / (len(window) * 2.5))
            tsi = max(0, min(100, int(100 - normalized * 100)))
        else:
            tsi = 100
        
        trend_data.append({
            "game_num": i + 1,
            "value": tsi
        })
    
    return {"data": trend_data}


@api_router.get("/cognitive/phase-insight")
async def get_phase_insight(user: User = Depends(get_current_user)):
    """
    Get phase stability insight.
    
    Returns most stable and most unstable phases.
    """
    # Get recent analyses
    analyses = await db.game_analyses.find(
        {"user_id": user.user_id},
        {"_id": 0, "stockfish_analysis": 1}
    ).sort("created_at", -1).limit(20).to_list(20)
    
    phase_mistakes = {
        "opening": {"count": 0, "severity": 0},
        "middlegame": {"count": 0, "severity": 0},
        "endgame": {"count": 0, "severity": 0}
    }
    
    for analysis in analyses:
        sf = analysis.get("stockfish_analysis", {})
        for move in sf.get("move_evaluations", []):
            cp_loss = abs(move.get("cp_loss", 0))
            if cp_loss >= 50:
                phase = move.get("phase", "middlegame")
                if phase in phase_mistakes:
                    phase_mistakes[phase]["count"] += 1
                    phase_mistakes[phase]["severity"] += min(1.0, cp_loss / 300)
    
    # Calculate weighted score per phase
    phase_scores = {}
    for phase, data in phase_mistakes.items():
        if data["count"] > 0:
            phase_scores[phase] = data["count"] * (data["severity"] / data["count"])
        else:
            phase_scores[phase] = 0
    
    # Find most unstable and most stable
    sorted_phases = sorted(phase_scores.items(), key=lambda x: x[1], reverse=True)
    
    most_unstable = sorted_phases[0][0].capitalize() if sorted_phases else "Middlegame"
    most_stable = sorted_phases[-1][0].capitalize() if sorted_phases else "Endgame"
    
    return {
        "most_unstable": most_unstable,
        "most_stable": most_stable,
        "phase_scores": phase_scores
    }


@api_router.get("/cognitive/blunder-context")
async def get_blunder_context(user: User = Depends(get_current_user)):
    """
    Get blunder context distribution - where do mistakes happen?
    
    Analyzes the position evaluation BEFORE each blunder to determine
    if user blunders more when winning, equal, or losing.
    
    Returns:
        winning: % of blunders that occurred in winning positions
        equal: % of blunders that occurred in equal positions  
        losing: % of blunders that occurred in losing positions
    """
    # Get recent analyses
    analyses = await db.game_analyses.find(
        {"user_id": user.user_id},
        {"_id": 0, "stockfish_analysis": 1, "user_color": 1}
    ).sort("created_at", -1).limit(20).to_list(20)
    
    context_counts = {
        "winning": 0,
        "equal": 0,
        "losing": 0
    }
    total_blunders = 0
    
    for analysis in analyses:
        sf = analysis.get("stockfish_analysis", {})
        user_color = analysis.get("user_color", "white")
        
        for move in sf.get("move_evaluations", []):
            cp_loss = abs(move.get("cp_loss", 0))
            if cp_loss < 100:  # Only count significant mistakes/blunders
                continue
            
            total_blunders += 1
            
            # Get evaluation BEFORE the blunder
            eval_before = move.get("eval_before", 0)
            
            # Adjust for user's perspective
            if user_color == "black":
                eval_before = -eval_before
            
            # Classify position context
            if eval_before >= 150:  # +1.5 or better = winning
                context_counts["winning"] += 1
            elif eval_before <= -150:  # -1.5 or worse = losing
                context_counts["losing"] += 1
            else:  # Between -1.5 and +1.5 = equal
                context_counts["equal"] += 1
    
    # Calculate percentages
    if total_blunders > 0:
        distribution = {
            "winning": round((context_counts["winning"] / total_blunders) * 100),
            "equal": round((context_counts["equal"] / total_blunders) * 100),
            "losing": round((context_counts["losing"] / total_blunders) * 100)
        }
        # Ensure they sum to 100 (handle rounding)
        diff = 100 - (distribution["winning"] + distribution["equal"] + distribution["losing"])
        distribution["equal"] += diff
    else:
        distribution = {"winning": 33, "equal": 34, "losing": 33}
    
    return {
        "distribution": distribution,
        "total_blunders": total_blunders,
        "games_analyzed": len(analyses)
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
