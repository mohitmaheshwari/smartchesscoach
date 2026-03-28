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
    get_lab_data_async,
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
    ReflectionStyle,
    get_reflection_style,
    get_rating_band,
    INTENT_BY_RATING,
    INTENT_LABELS,
)
from quick_tag_registry import generate_quick_tags
from awareness_gap_rules import evaluate_awareness_gap
from adaptive_profile_engine import get_adaptive_profile, get_adaptive_profile_sync
from reward_message_service import get_reward_message, get_post_loss_message, generate_weekly_proof
from reflect_predicates import BoardFacts

# === TIME ANALYSIS SERVICE ===
from time_analysis_service import (
    extract_time_data_from_pgn,
    get_time_context_for_move,
    analyze_time_management,
)

# === COACH PERSONALITY SERVICE ===
from services.coach_personality import (
    get_player_level,
    get_level_display_name,
    get_level_emoji,
    get_personalized_coaching_context,
    CoachLanguage,
    CoachVoice,
    PlayerLevel
)

# === MISSION ENGINE IMPORTS ===
from mission_generation_service import (
    generate_daily_mission,
    start_mission,
    complete_mission,
    PATTERN_FOCUS_MAP,
)

# === FOCUS MASTERY SERVICE ===
from focus_mastery_service import (
    get_user_focus_mastery,
    calculate_pattern_mastery,
    get_pattern_drill_positions,
    FOCUS_PATTERNS,
)

# === MOVE INTENT SERVICE (Position-specific hypotheses) ===
from move_intent_service import (
    analyze_move_intent,
    get_move_intent_summary,
)

# === COGNITIVE GAP SERVICE (Precise diagnosis) ===
from cognitive_gap_service import (
    analyze_cognitive_gap,
    get_coaching_message,
    CognitiveGap,
)

# === COGNITIVE GAP INTELLIGENCE SERVICE (Full tracking & training) ===
from cognitive_gap_intelligence_service import (
    persist_cognitive_gap,
    check_recurrence_alerts,
    get_all_recurring_patterns,
    get_drills_for_gap,
    get_recommended_drills,
    get_gap_progress,
    get_gap_summary,
    analyze_plan_quality,
    update_training_from_gaps,
    COGNITIVE_GAP_CONFIG,
)

# === BREAKTHROUGH & PLATEAU DETECTION SERVICE (Step 8) ===
from coach_state.breakthrough_service import (
    get_breakthrough_signal_for_user,
    BreakthroughSignal,
    WindowMetrics,
    build_window_metrics,
)

# === FOCUS LOCK SERVICE (Step 9) ===
from coach_state.focus_lock_service import (
    create_focus_lock,
    calculate_compliance,
    update_lock_after_game,
    calculate_compliance_trend,
    focus_lock_from_db,
    focus_lock_to_db,
    get_lock_ui_state,
    should_activate_lock,
    should_trigger_deep_session,
    FocusLock,
    RULE_DESCRIPTIONS,
    DEFAULT_LOCK_GAMES,
)

# === THEORY MODULES (Step 10) ===
from coach_state.theory_modules import (
    ALL_MODULES,
    get_module,
    get_modules_for_rating,
)
from coach_state.module_trigger_service import (
    get_module_injection_stats,
)

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Initialize modular routes with database reference
from routes import auth as auth_routes
from routes import feedback as feedback_routes
auth_routes.set_db(db)
feedback_routes.set_db(db)

# LLM Key
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY', '')

# Global variable to track the background task
_background_sync_task = None
_quick_sync_task = None
_analysis_queue_fallback_task = None

# Sync status tracking with thread-safe lock
_sync_lock = asyncio.Lock()
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
    global _sync_status, _sync_lock
    from journey_service import sync_user_games
    
    # Wait 1 minute before first check (let app stabilize)
    async with _sync_lock:
        _sync_status["next_sync_at"] = (datetime.now(timezone.utc) + timedelta(seconds=60)).isoformat()
    await asyncio.sleep(60)
    
    while True:
        try:
            async with _sync_lock:
                _sync_status["is_syncing"] = True
                _sync_status["last_sync_at"] = datetime.now(timezone.utc).isoformat()
            logger.info("Quick sync: Checking for new games...")
            
            # Get all users with linked chess accounts (support both field naming conventions)
            users = await db.users.find({
                "$or": [
                    {"chess_com_username": {"$exists": True, "$ne": None, "$ne": ""}},
                    {"chesscom_username": {"$exists": True, "$ne": None, "$ne": ""}},
                    {"lichess_username": {"$exists": True, "$ne": None, "$ne": ""}}
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
            
            async with _sync_lock:
                _sync_status["games_found_last_sync"] = total_synced
                _sync_status["is_syncing"] = False
            
            if total_synced > 0:
                logger.info(f"Quick sync: Found and queued {total_synced} new games")
            else:
                logger.debug("Quick sync: No new games found")
                
        except Exception as e:
            logger.error(f"Quick sync loop error: {e}")
            async with _sync_lock:
                _sync_status["is_syncing"] = False
        
        # Calculate next sync time
        async with _sync_lock:
            _sync_status["next_sync_at"] = (datetime.now(timezone.utc) + timedelta(seconds=QUICK_SYNC_INTERVAL_SECONDS)).isoformat()
        
        # Wait 5 minutes before next check
        await asyncio.sleep(QUICK_SYNC_INTERVAL_SECONDS)


def _run_analysis_queue_fallback_cycle():
    """Fallback queue processor.

    If the dedicated analysis worker is not running, this keeps queued games
    moving by claiming at most one job and processing it in a background thread.
    It also reuses the worker's stuck-job cleanup rules.
    """
    from analysis_worker import claim_next_job, cleanup_stuck_jobs, ensure_stockfish_installed, get_database, process_job

    if not ensure_stockfish_installed():
        logger.error("Analysis queue fallback processor cannot run because Stockfish is unavailable")
        return

    sync_db = get_database()
    cleanup_stuck_jobs(sync_db)

    processing_count = sync_db.analysis_queue.count_documents({"status": "processing"})
    if processing_count > 0:
        return

    job = claim_next_job(sync_db)
    if not job:
        return

    logger.info(f"Fallback queue processor claimed game {job.get('game_id')}")
    process_job(sync_db, job)


async def analysis_queue_fallback_loop():
    """Keep the analysis queue moving even when no separate worker process is running."""
    await asyncio.sleep(15)

    while True:
        try:
            await asyncio.to_thread(_run_analysis_queue_fallback_cycle)
        except Exception as e:
            logger.error(f"Analysis queue fallback loop error: {e}")

        await asyncio.sleep(15)

# Lifespan context manager (replaces deprecated on_event)
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for FastAPI.
    Handles startup and shutdown events.
    """
    global _background_sync_task, _quick_sync_task, _analysis_queue_fallback_task
    
    # === STARTUP ===
    # Start the background sync loop (every 6 hours)
    _background_sync_task = asyncio.create_task(background_sync_loop())
    logger.info("Background sync scheduler started (6 hour interval)")
    
    # Start quick sync loop (every 5 minutes for real-time game monitoring)
    _quick_sync_task = asyncio.create_task(quick_sync_loop())
    logger.info("Quick sync started (5 minute interval for real-time monitoring)")

    # Start fallback analysis queue processor
    _analysis_queue_fallback_task = asyncio.create_task(analysis_queue_fallback_loop())
    logger.info("Analysis queue fallback processor started")
    
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

    if _analysis_queue_fallback_task:
        _analysis_queue_fallback_task.cancel()
        try:
            await _analysis_queue_fallback_task
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
    role: Optional[str] = "user"

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

# ==================== COACH MEMORY HELPERS ====================

async def compute_recurring_pattern_context(
    db, 
    user_id: str, 
    current_game_id: str,
    stockfish_eval: list,
    blunders: list
) -> dict:
    """
    Compute recurring pattern context for the coach memory.
    
    Returns information like:
    - "This is the 3rd game this week with threat blindness"
    - "You've had this pattern 5 times in the last 10 games"
    - Whether this pattern is improving or worsening
    
    This is what makes the coach feel like it REMEMBERS.
    """
    from datetime import timedelta
    from collections import Counter
    
    # Determine the primary pattern in THIS game
    current_pattern = None
    pattern_context = {
        "has_recurring": False,
        "pattern_name": None,
        "occurrence_count_week": 0,
        "occurrence_count_month": 0,
        "trend": "stable",  # improving, worsening, stable
        "coach_memory_line": None,  # The actual text to show
        "games_with_pattern": [],
    }
    
    # Classify the mistakes in this game
    game_patterns = []
    for m in stockfish_eval:
        if m.get("evaluation") in ["blunder", "mistake"]:
            cp_loss = m.get("cp_loss", 0)
            eval_before = m.get("eval_before", 0)
            
            if cp_loss >= 150:
                if eval_before > 1.0:  # Was winning
                    game_patterns.append("blunder_when_winning")
                elif eval_before < -1.0:  # Was losing
                    game_patterns.append("blunder_when_losing")
                else:
                    game_patterns.append("blunder_in_equal_position")
    
    # Also check for threat blindness from blunders
    for b in blunders:
        cat = b.get("mistake_category", "")
        if "ignored_opponent" in cat or "forcing" in cat.lower():
            game_patterns.append("threat_blindness")
    
    if not game_patterns:
        return pattern_context
    
    # Find the dominant pattern in this game
    pattern_counts = Counter(game_patterns)
    current_pattern, _ = pattern_counts.most_common(1)[0]
    pattern_context["pattern_name"] = current_pattern
    
    # Now check historical data - how often has this pattern appeared?
    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)
    
    # Get all recent analyses
    recent_analyses = await db.game_analyses.find(
        {
            "user_id": user_id,
            "game_id": {"$ne": current_game_id}  # Exclude current game
        },
        {"game_id": 1, "stockfish_analysis": 1, "blunders": 1, "created_at": 1, "analyzed_at": 1}
    ).sort("created_at", -1).limit(50).to_list(50)
    
    week_count = 0
    month_count = 0
    games_with_pattern = []
    
    for a in recent_analyses:
        # Check if this game has the same pattern
        sf = a.get("stockfish_analysis", {})
        game_blunders = a.get("blunders", [])
        game_date = a.get("analyzed_at") or a.get("created_at")
        
        has_pattern = False
        for m in sf.get("move_evaluations", []):
            if m.get("evaluation") in ["blunder", "mistake"]:
                cp_loss = m.get("cp_loss", 0)
                eval_before = m.get("eval_before", 0)
                
                if current_pattern == "blunder_when_winning" and eval_before > 1.0 and cp_loss >= 150:
                    has_pattern = True
                    break
                elif current_pattern == "blunder_when_losing" and eval_before < -1.0 and cp_loss >= 150:
                    has_pattern = True
                    break
                elif current_pattern == "blunder_in_equal_position" and abs(eval_before) <= 1.0 and cp_loss >= 150:
                    has_pattern = True
                    break
        
        # Check for threat blindness
        if current_pattern == "threat_blindness":
            for b in game_blunders:
                cat = b.get("mistake_category", "")
                if "ignored_opponent" in cat or "forcing" in cat.lower():
                    has_pattern = True
                    break
        
        if has_pattern:
            games_with_pattern.append(a.get("game_id"))
            
            # Check if within time windows
            if game_date:
                if isinstance(game_date, str):
                    try:
                        game_date = datetime.fromisoformat(game_date.replace('Z', '+00:00'))
                    except:
                        game_date = None
                
                if game_date:
                    if game_date > week_ago:
                        week_count += 1
                    if game_date > month_ago:
                        month_count += 1
    
    pattern_context["occurrence_count_week"] = week_count
    pattern_context["occurrence_count_month"] = month_count
    pattern_context["games_with_pattern"] = games_with_pattern[:5]  # Last 5 game IDs
    
    # Determine if this is a recurring pattern (3+ times in a week)
    if week_count >= 2:
        pattern_context["has_recurring"] = True
        
        # Compute trend (compare last 2 weeks)
        # Simplified: if week_count is higher than usual, it's worsening
        if week_count >= 4:
            pattern_context["trend"] = "worsening"
        elif week_count <= 1 and month_count >= 4:
            pattern_context["trend"] = "improving"
    
    # Generate the coach memory line
    pattern_labels = {
        "blunder_when_winning": "losing focus when ahead",
        "blunder_when_losing": "panicking when behind",
        "blunder_in_equal_position": "missing threats in balanced positions",
        "threat_blindness": "missing opponent threats",
    }
    
    pattern_label = pattern_labels.get(current_pattern, current_pattern.replace("_", " "))
    
    if week_count >= 3:
        pattern_context["coach_memory_line"] = f"This is familiar. You've had {week_count} games this week with {pattern_label}."
    elif week_count >= 1:
        pattern_context["coach_memory_line"] = f"I've seen this before. {pattern_label.capitalize()} appeared {week_count + 1} times recently."
    elif month_count >= 3:
        pattern_context["coach_memory_line"] = f"This pattern has come up {month_count} times this month."
    else:
        pattern_context["coach_memory_line"] = None
    
    return pattern_context


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
    d = user.model_dump()
    d["role"] = user.role or "user"
    return d

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
    
    # ECO code to opening name mapping
    ECO_TO_OPENING = {
        "A00": "Uncommon Opening", "A01": "Nimzowitsch-Larsen Attack", "A04": "Reti Opening",
        "A10": "English Opening", "A20": "English Opening", "A40": "Queen's Pawn Game",
        "A45": "Indian Defense", "A80": "Dutch Defense",
        "B00": "Uncommon King's Pawn", "B01": "Scandinavian Defense", "B02": "Alekhine's Defense",
        "B06": "Modern Defense", "B07": "Pirc Defense", "B10": "Caro-Kann Defense",
        "B20": "Sicilian Defense", "B21": "Sicilian Defense", "B22": "Sicilian Defense",
        "B23": "Sicilian Defense", "B27": "Sicilian Defense", "B30": "Sicilian Defense",
        "B40": "Sicilian Defense", "B50": "Sicilian Defense", "B90": "Sicilian Najdorf",
        "C00": "French Defense", "C01": "French Defense", "C02": "French Defense",
        "C10": "French Defense", "C20": "King's Pawn Game", "C21": "Danish Gambit",
        "C24": "Bishop's Opening", "C25": "Vienna Game", "C30": "King's Gambit",
        "C40": "King's Knight Opening", "C41": "Philidor Defense", "C42": "Petrov Defense",
        "C44": "Scotch Game", "C45": "Scotch Game", "C46": "Three Knights Game",
        "C47": "Four Knights Game", "C50": "Italian Game", "C51": "Evans Gambit",
        "C52": "Evans Gambit", "C53": "Italian Game", "C54": "Italian Game", "C55": "Two Knights Defense",
        "C60": "Ruy Lopez", "C61": "Ruy Lopez", "C62": "Ruy Lopez", "C63": "Ruy Lopez",
        "C64": "Ruy Lopez", "C65": "Ruy Lopez", "C70": "Ruy Lopez", "C80": "Ruy Lopez",
        "D00": "Queen's Pawn Game", "D02": "London System", "D04": "Colle System",
        "D06": "Queen's Gambit", "D10": "Slav Defense", "D20": "Queen's Gambit Accepted",
        "D30": "Queen's Gambit Declined", "D35": "Queen's Gambit Declined",
        "D37": "Queen's Gambit Declined", "D50": "Queen's Gambit Declined",
        "E00": "Indian Defense", "E10": "Queen's Indian Defense", "E12": "Queen's Indian Defense",
        "E20": "Nimzo-Indian Defense", "E30": "Nimzo-Indian Defense",
        "E60": "King's Indian Defense", "E70": "King's Indian Defense",
        "E80": "King's Indian Defense", "E90": "King's Indian Defense",
    }
    
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
        
        # Get opening name - prefer Opening header, fall back to ECO mapping
        opening_name = g.get('opening', '')
        eco_code = g.get('eco', '')
        
        if not opening_name and eco_code:
            # Try exact match first, then prefix match
            opening_name = ECO_TO_OPENING.get(eco_code)
            if not opening_name:
                eco_prefix = eco_code[:2] + "0" if len(eco_code) >= 2 else eco_code
                opening_name = ECO_TO_OPENING.get(eco_prefix, f"ECO {eco_code}")
        
        parsed_games.append({
            'platform': platform,
            'pgn': full_pgn,
            'white_player': white,
            'black_player': black,
            'result': g.get('result', '*'),
            'time_control': g.get('timecontrol', g.get('event', '')),
            'date_played': g.get('date', g.get('utcdate', '')),
            'opening': opening_name or eco_code,  # Store opening name, fall back to ECO
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

# NOTE: /games, /games/analyzed, /games/blunders endpoints moved to routes/games.py


# NOTE: /training/one-move-blunders moved to routes/training.py

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
        
        # ============ COMMUNITY TRAINING POSITIONS ============
        # Auto-extract training-worthy positions for the community pool
        try:
            from services.community_training_service import extract_training_positions
            background_tasks.add_task(
                extract_training_positions, db, req.game_id, user.user_id
            )
        except Exception as extract_err:
            logger.warning(f"Community position extraction failed (non-critical): {extract_err}")
        
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


@api_router.get("/analysis/{game_id}/enriched")
async def get_enriched_analysis(game_id: str, user: User = Depends(get_current_user)):
    """
    Get analysis enriched with human coach layer.
    
    Returns the standard analysis PLUS:
    - Behavioral tags (WHY the mistake happened)
    - Cross-game pattern connections
    - Coach voice summary
    - Specific moment insights
    """
    from services.human_coach_layer import enrich_game_analysis
    
    # Get base analysis
    analysis = await db.game_analyses.find_one(
        {"game_id": game_id, "user_id": user.user_id},
        {"_id": 0, "_cqs_internal": 0}
    )
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    
    # Enrich with human coach layer
    try:
        enriched = await enrich_game_analysis(db, game_id, user.user_id, analysis)
        return enriched
    except Exception as e:
        logger.warning(f"Failed to enrich analysis: {e}")
        # Return base analysis if enrichment fails
        return analysis


@api_router.get("/memory/patterns")
async def get_memory_patterns(user: User = Depends(get_current_user)):
    """
    Get aggregated patterns across all games for the Memory tab.
    
    Returns:
    - Category breakdown (what types of mistakes)
    - Top weaknesses with examples (clickable links to games)
    - Accuracy trend over recent games
    """
    from services.human_coach_layer import get_aggregated_patterns
    
    try:
        patterns = await get_aggregated_patterns(db, user.user_id)
        return patterns
    except Exception as e:
        logger.error(f"Failed to get memory patterns: {e}")
        return {
            "total_games": 0,
            "category_breakdown": {},
            "top_weaknesses": [],
            "accuracy_trend": [],
            "has_enough_data": False,
            "error": str(e)
        }


@api_router.get("/analysis/{game_id}/opening-fundamentals")
async def get_opening_fundamentals(game_id: str, user: User = Depends(get_current_user)):
    """
    Analyze a game's opening for fundamental principle violations.
    
    This teaches players the THINKING PROCESS, not just answers:
    - Did they castle early?
    - Did they develop before attacking?
    - Did they control the center?
    - Did they move the same piece twice?
    
    Each violation comes with:
    - What the principle is
    - Why it matters
    - What to THINK before each move (the habit to build)
    """
    from services.opening_fundamentals_checker import analyze_opening_fundamentals
    
    # Get the game
    game = await db.games.find_one(
        {"game_id": game_id, "user_id": user.user_id},
        {"_id": 0, "pgn": 1, "user_color": 1, "result": 1}
    )
    
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    
    # Parse moves from PGN
    try:
        import chess.pgn
        import io
        pgn_io = io.StringIO(game.get("pgn", ""))
        parsed_game = chess.pgn.read_game(pgn_io)
        
        if parsed_game:
            moves = [move.san() for move in parsed_game.mainline()]
        else:
            moves = []
    except Exception as e:
        logger.warning(f"Failed to parse PGN: {e}")
        moves = []
    
    if not moves:
        return {
            "error": "Could not parse game moves",
            "violations": [],
            "adherences": [],
            "score": 0
        }
    
    # Analyze opening fundamentals
    result = analyze_opening_fundamentals(
        moves=moves,
        user_color=game.get("user_color", "white"),
        game_result=game.get("result")
    )
    
    return result


# ==================== THINKING COACH ROUTES ====================

class ThoughtProcessRequest(BaseModel):
    fen: str
    best_move: str
    played_move: Optional[str] = None
    position_context: Optional[Dict] = None

@api_router.post("/thinking-coach/walkthrough")
async def get_thought_process_walkthrough(req: ThoughtProcessRequest, user: User = Depends(get_current_user)):
    """
    Generate a step-by-step thought process walkthrough for a position.
    
    Shows HOW a strong player would think through this position.
    This is the core of the "Thinking Coach" feature.
    """
    from services.thinking_coach import generate_thought_process_walkthrough
    
    result = generate_thought_process_walkthrough(
        fen=req.fen,
        best_move=req.best_move,
        played_move=req.played_move,
        position_context=req.position_context
    )
    
    return result


class PrincipleBasedFeedbackRequest(BaseModel):
    mistake_type: str
    fen: str
    move_played: str
    best_move: str

@api_router.post("/thinking-coach/principle-feedback")
async def get_principle_based_feedback(req: PrincipleBasedFeedbackRequest, user: User = Depends(get_current_user)):
    """
    Connect a mistake to a fundamental chess principle.
    
    Instead of just "this was wrong", explains WHY and gives a thinking habit.
    """
    from services.thinking_coach import get_principle_based_feedback
    
    result = get_principle_based_feedback(
        mistake_type=req.mistake_type,
        fen=req.fen,
        move_played=req.move_played,
        best_move=req.best_move
    )
    
    return result


class BehavioralInterventionRequest(BaseModel):
    behavioral_pattern: str
    examples: Optional[List[Dict]] = None

@api_router.post("/thinking-coach/behavioral-intervention")
async def get_behavioral_intervention(req: BehavioralInterventionRequest, user: User = Depends(get_current_user)):
    """
    Get a specific intervention for a diagnosed behavioral pattern.
    
    Returns actionable thinking habits to break bad patterns like hope_chess, impulsive_play, etc.
    """
    from services.thinking_coach import get_behavioral_intervention
    
    result = get_behavioral_intervention(
        behavioral_pattern=req.behavioral_pattern,
        examples=req.examples
    )
    
    return result


class MindsetPromptRequest(BaseModel):
    fen: str
    position_characteristics: Optional[Dict] = None

@api_router.post("/thinking-coach/mindset-prompt")
async def get_position_mindset_prompt(req: MindsetPromptRequest, user: User = Depends(get_current_user)):
    """
    Generate mindset prompts based on position characteristics.
    
    E.g., "This position has a weak back rank. What should you be looking for?"
    """
    from services.thinking_coach import get_position_mindset_prompt
    
    result = get_position_mindset_prompt(
        fen=req.fen,
        position_characteristics=req.position_characteristics
    )
    
    return result


class PreMoveChecklistRequest(BaseModel):
    move_number: int
    has_castled: bool = False
    developed_pieces: int = 0
    player_weaknesses: Optional[List[str]] = None

@api_router.get("/thinking-coach/pre-move-checklist")
async def get_pre_move_checklist(
    move_number: int,
    has_castled: bool = False,
    developed_pieces: int = 0,
    user: User = Depends(get_current_user)
):
    """
    Get a pre-move checklist for the player based on current game state.
    
    Reinforces good thinking habits before each move.
    """
    from services.thinking_coach import get_pre_move_checklist
    
    # Get player's known weaknesses from identity
    player_weaknesses = []
    try:
        identity = await db.player_identities.find_one(
            {"user_id": user.user_id},
            {"_id": 0, "behavioral_patterns": 1}
        )
        if identity and identity.get("behavioral_patterns"):
            # Extract pattern names
            player_weaknesses = [p.get("pattern") for p in identity["behavioral_patterns"] if p.get("pattern")]
    except:
        pass
    
    result = get_pre_move_checklist(
        move_number=move_number,
        has_castled=has_castled,
        developed_pieces=developed_pieces,
        player_weaknesses=player_weaknesses
    )
    
    return {
        "checklist": result,
        "player_weaknesses": player_weaknesses
    }


# ==================== THINKING SCORE ROUTES ====================

@api_router.get("/thinking-score")
async def get_user_thinking_score(user: User = Depends(get_current_user)):
    """
    Get the user's overall thinking score and progress.
    
    The score is calculated from REAL game analysis data - it measures
    how well the player applies thinking habits based on their actual mistakes.
    """
    from services.thinking_score import calculate_thinking_progress, get_weakest_habits
    
    # Get or calculate thinking scores from recent games
    thinking_scores = await db.thinking_scores.find(
        {"user_id": user.user_id},
        {"_id": 0}
    ).sort("calculated_at", -1).limit(20).to_list(20)
    
    if not thinking_scores:
        # No scores calculated yet - try to calculate from existing analyses
        return {
            "has_data": False,
            "message": "No thinking scores calculated yet. Play and analyze some games first.",
            "overall_score": None,
            "progress": None,
            "recommendations": []
        }
    
    # Calculate progress from scores
    progress = calculate_thinking_progress(thinking_scores)
    
    # Get recommendations for weakest areas
    recommendations = get_weakest_habits(progress, top_n=2) if progress.get("has_enough_data") else []
    
    return {
        "has_data": True,
        "overall_score": progress.get("overall_score"),
        "overall_trend": progress.get("overall_trend"),
        "overall_change": progress.get("overall_change"),
        "habit_progress": progress.get("habit_progress", {}),
        "games_analyzed": progress.get("games_analyzed", 0),
        "recommendations": recommendations,
        "explanation": _get_score_explanation(progress.get("overall_score", 0))
    }


def _get_score_explanation(score: float) -> str:
    """Generate explanation for overall thinking score."""
    if score >= 90:
        return "Excellent! You're applying strong thinking habits consistently."
    elif score >= 80:
        return "Great thinking process. Focus on your weak areas to reach mastery."
    elif score >= 70:
        return "Good foundation. The thinking checklist will help you improve further."
    elif score >= 60:
        return "Room for improvement. Slow down and apply the thinking process on each move."
    else:
        return "Focus on the basics: check threats, verify moves, keep king safe."


@api_router.post("/thinking-score/calculate/{game_id}")
async def calculate_game_thinking_score(game_id: str, user: User = Depends(get_current_user)):
    """
    Calculate thinking score for a specific game.
    
    This analyzes the game's move evaluations to determine which
    thinking habits were followed or violated.
    """
    from services.thinking_score import calculate_game_thinking_scores
    
    # Get the game analysis
    analysis = await db.game_analyses.find_one(
        {"game_id": game_id},
        {"_id": 0, "stockfish_analysis": 1, "game_id": 1}
    )
    
    if not analysis:
        return {"error": "Game analysis not found", "game_id": game_id}
    
    # Extract move_evaluations from stockfish_analysis
    stockfish_analysis = analysis.get("stockfish_analysis", {})
    move_evaluations = stockfish_analysis.get("move_evaluations", [])
    
    # Get user color for this game
    game = await db.games.find_one(
        {"game_id": game_id},
        {"_id": 0, "user_color": 1}
    )
    user_color = game.get("user_color", "white") if game else "white"
    
    # Build analysis dict for thinking score calculation
    analysis_for_score = {
        "game_id": game_id,
        "move_evaluations": move_evaluations,
        "critical_moments": []
    }
    
    # Calculate scores
    scores = calculate_game_thinking_scores(analysis_for_score, user_color)
    scores["user_id"] = user.user_id
    scores["game_id"] = game_id
    
    # Store the scores
    await db.thinking_scores.update_one(
        {"user_id": user.user_id, "game_id": game_id},
        {"$set": scores},
        upsert=True
    )
    
    return scores


@api_router.get("/thinking-score/history")
async def get_thinking_score_history(
    limit: int = 10,
    user: User = Depends(get_current_user)
):
    """
    Get thinking score history for recent games.
    
    Shows how scores have changed over time.
    """
    scores = await db.thinking_scores.find(
        {"user_id": user.user_id},
        {"_id": 0}
    ).sort("calculated_at", -1).limit(limit).to_list(limit)
    
    return {
        "scores": scores,
        "count": len(scores)
    }


@api_router.get("/thinking-score/recommendations")
async def get_thinking_recommendations(user: User = Depends(get_current_user)):
    """
    Get personalized thinking habit recommendations.
    
    Based on analysis of recent games, identifies the weakest
    thinking habits and provides actionable advice.
    """
    from services.thinking_score import calculate_thinking_progress, get_weakest_habits
    
    # Get recent thinking scores
    thinking_scores = await db.thinking_scores.find(
        {"user_id": user.user_id},
        {"_id": 0}
    ).sort("calculated_at", -1).limit(10).to_list(10)
    
    if len(thinking_scores) < 2:
        return {
            "has_data": False,
            "message": "Analyze more games to get personalized recommendations",
            "recommendations": [
                {
                    "habit": "general",
                    "habit_label": "Thinking Process",
                    "priority": "medium",
                    "recommendation": "Use the Pre-Move Checklist during your games to build good habits.",
                    "checklist_item": "Did I follow my thinking process?",
                    "icon": "🧠"
                }
            ]
        }
    
    progress = calculate_thinking_progress(thinking_scores)
    recommendations = get_weakest_habits(progress, top_n=3)
    
    return {
        "has_data": True,
        "overall_score": progress.get("overall_score"),
        "recommendations": recommendations
    }


@api_router.get("/principles/opening")
async def get_opening_principles():
    """
    Get all opening principles with their teachings.
    
    This is the "curriculum" - what a player needs to learn
    to improve their opening play.
    """
    from services.opening_fundamentals_checker import get_all_principles
    return {
        "principles": get_all_principles(),
        "recommendation": "Focus on one principle at a time. Master it before moving to the next."
    }


# ==================== DATA FRESHNESS ROUTES ====================

@api_router.post("/data/refresh")
async def refresh_user_data(user: User = Depends(get_current_user)):
    """
    Manually trigger a refresh of all aggregated user data.
    
    This recalculates:
    - Player identity (Memory tab, coaching context)
    - Journey stats (milestones, streaks)
    - Player profile (dashboard stats)
    - Thinking scores
    
    Call this after importing games or if data seems stale.
    """
    from services.data_freshness import refresh_all_user_data
    
    # Use synchronous DB connection for the service
    from pymongo import MongoClient
    import os
    
    sync_client = MongoClient(os.environ.get('MONGO_URL'))
    sync_db = sync_client[os.environ.get('DB_NAME', 'test_database')]
    
    result = refresh_all_user_data(sync_db, user.user_id)
    
    sync_client.close()
    
    return result


@api_router.get("/data/status")
async def get_data_status(user: User = Depends(get_current_user)):
    """
    Get the freshness status of user data across all collections.
    """
    status = {}
    
    # Check player_identity
    identity = await db.player_identities.find_one(
        {"user_id": user.user_id},
        {"_id": 0, "updated_at": 1, "games_analyzed": 1}
    )
    status["player_identity"] = {
        "exists": identity is not None,
        "games_analyzed": identity.get("games_analyzed") if identity else 0,
        "updated_at": identity.get("updated_at") if identity else None
    }
    
    # Check player_profile
    profile = await db.player_profiles.find_one(
        {"user_id": user.user_id},
        {"_id": 0, "updated_at": 1, "games_analyzed": 1}
    )
    status["player_profile"] = {
        "exists": profile is not None,
        "games_analyzed": profile.get("games_analyzed") if profile else 0,
        "updated_at": profile.get("updated_at") if profile else None
    }
    
    # Check thinking scores
    score_count = await db.thinking_scores.count_documents({"user_id": user.user_id})
    status["thinking_scores"] = {
        "count": score_count
    }
    
    # Check total games vs analyzed
    total_games = await db.games.count_documents({"user_id": user.user_id})
    game_ids = [g["game_id"] async for g in db.games.find({"user_id": user.user_id}, {"_id": 0, "game_id": 1})]
    analyzed_games = await db.game_analyses.count_documents({"game_id": {"$in": game_ids}})
    
    status["games"] = {
        "total": total_games,
        "analyzed": analyzed_games,
        "pending": total_games - analyzed_games
    }
    
    return status


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

# NOTE: Journey routes moved to routes/journey.py:
# - GET /journey
# - GET /journey/comprehensive
# - GET /journey/weekly-assessment
# - GET /journey/weakness-trends
# - POST /journey/link-account
# - GET /journey/linked-accounts
# - POST /journey/unlink-account
# - POST /journey/sync-now
# - GET /sync-status

# ==================== REFLECTION ROUTES ====================

from reflect_service import (
    get_games_needing_reflection,
    get_pending_reflection_count,
    get_game_moments,
    process_reflection,
    mark_game_reflected,
    generate_contextual_tags
)

# NOTE: Reflect endpoints moved to routes/reflect.py:
# - GET /reflect/pending
# - GET /reflect/pending/count
# - GET /reflect/game/{game_id}/moments
# - POST /reflect/submit
# - POST /reflect/game/{game_id}/complete
# - POST /reflect/moment/contextual-tags
# - POST /reflect/explain-moment
# - GET /reflect/v1/profile
# - POST /reflect/v1/quick-tags
# - POST /reflect/v1/submit
# - GET /reflect/v1/post-loss/{game_id}


# NOTE: /training/data-driven moved to routes/training.py

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


# NOTE: Reflect V1 endpoints moved to routes/reflect.py
# - MomentExplanationRequest, ReflectEngineTagsRequest, ReflectSessionSubmitRequest models
# - POST /reflect/explain-moment
# - GET /reflect/v1/profile
# - POST /reflect/v1/quick-tags  
# - POST /reflect/v1/submit

# ==================== TIME ANALYSIS ENDPOINTS ====================

@api_router.get("/games/{game_id}/time-analysis")
async def get_game_time_analysis(game_id: str, user: User = Depends(get_current_user)):
    """
    Get time analysis for a game - time spent on each move, time pressure detection.
    
    Uses clock data from PGN to provide insights like:
    - "You spent only 3 seconds on move 23 - a rushed decision"
    - "You played 8 moves under time pressure"
    """
    game = await db.games.find_one(
        {"game_id": game_id, "user_id": user.user_id},
        {"_id": 0, "pgn": 1, "user_color": 1}
    )
    
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    
    pgn = game.get("pgn", "")
    user_color = game.get("user_color", "white")
    
    # Extract time data from PGN
    time_data = extract_time_data_from_pgn(pgn)
    
    if not time_data.get("has_time_data"):
        return {"has_time_data": False, "message": "No clock data available for this game"}
    
    # Add time management analysis
    time_management = analyze_time_management(time_data, user_color)
    
    return {
        "has_time_data": True,
        "initial_time": time_data.get("initial_time"),
        "increment": time_data.get("increment"),
        "total_moves": time_data.get("total_moves"),
        "user_profile": time_data.get(f"{user_color}_profile"),
        "time_pressure_moves": time_data.get("time_pressure_moves"),
        "rushed_moves": time_data.get("rushed_moves"),
        "time_management": time_management,
        "moves": time_data.get("moves"),  # Full move-by-move time data
    }


@api_router.get("/games/{game_id}/move/{move_number}/time-context")
async def get_move_time_context(game_id: str, move_number: int, user: User = Depends(get_current_user)):
    """
    Get time context for a specific move.
    
    Used in reflection to understand if a mistake was due to:
    - Time pressure (< 30s remaining)
    - Rushed decision (< 5s spent)
    - Normal thinking time
    """
    game = await db.games.find_one(
        {"game_id": game_id, "user_id": user.user_id},
        {"_id": 0, "pgn": 1, "user_color": 1}
    )
    
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    
    pgn = game.get("pgn", "")
    user_color = game.get("user_color", "white")
    
    # Extract time data
    time_data = extract_time_data_from_pgn(pgn)
    
    if not time_data.get("has_time_data"):
        return {"has_data": False, "message": "No clock data available"}
    
    # Get context for specific move
    context = get_time_context_for_move(time_data, move_number, user_color)
    
    return context


# ==================== MOVE INTENT HYPOTHESES ====================

@api_router.get("/games/{game_id}/move/{move_number}/intent-hypotheses")
async def get_move_intent_hypotheses(game_id: str, move_number: int, user: User = Depends(get_current_user)):
    """
    Get position-specific hypotheses about why the user played their move.
    
    This is the crucial layer between Stockfish analysis and user reflection.
    Analyzes the actual position to generate confident hypotheses like:
    - "Were you trying to control the e5 square?"
    - "Were you defending the d4 pawn?"
    
    Only returns CONFIDENT hypotheses that are actually valid in the position.
    """
    # Get the game analysis to find the move
    analysis = await db.game_analyses.find_one(
        {"game_id": game_id, "user_id": user.user_id},
        {"_id": 0}
    )
    
    if not analysis:
        raise HTTPException(status_code=404, detail="Game analysis not found")
    
    # Find the move evaluation
    sf = analysis.get("stockfish_analysis", {})
    evals = sf.get("move_evaluations", [])
    
    target_eval = None
    for ev in evals:
        if ev.get("move_number") == move_number:
            target_eval = ev
            break
    
    if not target_eval:
        raise HTTPException(status_code=404, detail="Move not found in analysis")
    
    fen_before = target_eval.get("fen_before")
    user_move = target_eval.get("move")
    best_move = target_eval.get("best_move")
    
    if not fen_before or not user_move:
        return {"hypotheses": [], "message": "Insufficient data for analysis"}
    
    # Get the intent summary with hypotheses
    intent_summary = get_move_intent_summary(fen_before, user_move, best_move)
    
    # Also get time context if available
    game = await db.games.find_one(
        {"game_id": game_id, "user_id": user.user_id},
        {"_id": 0, "pgn": 1, "user_color": 1}
    )
    
    time_context = None
    if game and game.get("pgn"):
        from time_analysis_service import extract_time_data_from_pgn, get_time_context_for_move
        time_data = extract_time_data_from_pgn(game["pgn"])
        if time_data.get("has_time_data"):
            time_context = get_time_context_for_move(time_data, move_number, game.get("user_color", "white"))
    
    return {
        "move_number": move_number,
        "user_move": user_move,
        "best_move": best_move,
        "fen_before": fen_before,
        "intent_summary": intent_summary,
        "hypotheses": intent_summary.get("hypotheses", []),
        "primary_intent": intent_summary.get("primary_intent"),
        "time_context": time_context,
    }


# ==================== COGNITIVE GAP ANALYSIS ====================

class CognitiveGapRequest(BaseModel):
    """Request body for cognitive gap analysis."""
    user_stated_plan: Optional[str] = None
    user_hypothesis_category: Optional[str] = None
    user_confidence: Optional[str] = None

@api_router.post("/games/{game_id}/move/{move_number}/analyze-gap")
async def analyze_move_cognitive_gap(
    game_id: str, 
    move_number: int, 
    request: CognitiveGapRequest,
    user: User = Depends(get_current_user)
):
    """
    Analyze the cognitive gap for a specific move.
    
    This is the CRITICAL endpoint that determines WHY the user made a mistake.
    Uses the user's stated plan + position analysis to give precise diagnosis.
    
    Returns:
        - primary_gap: The main cognitive error type
        - confidence: How sure we are about this diagnosis  
        - evidence: Concrete proof from the position
        - explanation: Human-readable explanation
        - coaching_focus: What to work on
    """
    # Get game analysis
    analysis = await db.game_analyses.find_one(
        {"game_id": game_id, "user_id": user.user_id},
        {"_id": 0}
    )
    
    if not analysis:
        raise HTTPException(status_code=404, detail="Game analysis not found")
    
    # Find the move evaluation
    sf = analysis.get("stockfish_analysis", {})
    evals = sf.get("move_evaluations", [])
    
    target_eval = None
    for ev in evals:
        if ev.get("move_number") == move_number:
            target_eval = ev
            break
    
    if not target_eval:
        raise HTTPException(status_code=404, detail="Move not found in analysis")
    
    fen_before = target_eval.get("fen_before")
    user_move = target_eval.get("move")
    best_move = target_eval.get("best_move")
    eval_before = target_eval.get("eval_before", 0)
    eval_after = target_eval.get("eval_after", 0)
    threat = target_eval.get("threat")
    
    if not fen_before or not user_move or not best_move:
        return {"error": "Insufficient data for analysis"}
    
    # Get time context
    game = await db.games.find_one(
        {"game_id": game_id, "user_id": user.user_id},
        {"_id": 0, "pgn": 1, "user_color": 1}
    )
    
    time_spent = None
    clock_remaining = None
    
    if game and game.get("pgn"):
        from time_analysis_service import extract_time_data_from_pgn, get_time_context_for_move
        time_data = extract_time_data_from_pgn(game["pgn"])
        if time_data.get("has_time_data"):
            tc = get_time_context_for_move(time_data, move_number, game.get("user_color", "white"))
            if tc.get("has_data"):
                time_spent = tc.get("time_spent")
                clock_remaining = tc.get("clock_after")
    
    # Perform cognitive gap analysis
    gap_result = analyze_cognitive_gap(
        fen_before=fen_before,
        user_move_san=user_move,
        best_move_san=best_move,
        eval_before=eval_before,
        eval_after=eval_after,
        threat_description=threat,
        user_stated_plan=request.user_stated_plan,
        user_hypothesis_category=request.user_hypothesis_category,
        time_spent_seconds=time_spent,
        clock_remaining_seconds=clock_remaining,
        user_confidence=request.user_confidence,
    )
    
    # Add coaching message
    coaching_message = get_coaching_message(gap_result)
    
    # ENHANCEMENT: For positional misreads and generic gaps, get POSITION-SPECIFIC insights
    if gap_result.get("primary_gap") in ["positional_misread", "calculation_depth", "wrong_plan"]:
        try:
            from services.position_strategy_analyzer import generate_move_specific_insight
            pv_after_best = target_eval.get("pv_after_best", [])
            # cp_loss can be directly from stockfish or calculated
            cp_loss_val = target_eval.get("cp_loss", 0)
            if not cp_loss_val and eval_before is not None and eval_after is not None:
                cp_loss_val = abs(int((eval_before - eval_after) * 100))
            user_color = game.get("user_color", "white") if game else "white"
            
            logger.info(f"Position-specific insight: threat={threat}, cp_loss={cp_loss_val}, user_move={user_move}, best_move={best_move}")
            
            specific_insight = generate_move_specific_insight(
                fen_before=fen_before,
                user_move=user_move,
                best_move=best_move,
                pv_after_best=pv_after_best,
                cp_loss=cp_loss_val,
                user_color=user_color,
                threat=threat
            )
            
            # Override generic explanation with position-specific one
            if specific_insight and not specific_insight.get("error"):
                # Build a better explanation
                what_missed = specific_insight.get("what_you_missed", "")
                what_best_achieves = specific_insight.get("what_best_move_achieves", "")
                why_wrong = specific_insight.get("why_your_move_was_wrong", "")
                
                # Create concise, specific explanation
                if what_missed and what_best_achieves:
                    gap_result["explanation"] = f"{what_missed}. {best_move} would have {what_best_achieves.lower() if what_best_achieves[0].isupper() else what_best_achieves}."
                elif what_best_achieves:
                    gap_result["explanation"] = f"{best_move} {what_best_achieves.lower() if what_best_achieves[0].isupper() else what_best_achieves}. {why_wrong}"
                
                # Add position-specific coaching focus
                if specific_insight.get("the_idea_you_should_learn"):
                    gap_result["coaching_focus"] = specific_insight["the_idea_you_should_learn"]
                
                # Add how to spot this
                if specific_insight.get("how_to_spot_this"):
                    gap_result["how_to_spot"] = specific_insight["how_to_spot_this"]
                    
                logger.info(f"Enhanced positional misread with specific insight: {gap_result['explanation'][:100]}")
        except Exception as e:
            logger.warning(f"Could not enhance with position-specific insight: {e}")
    
    # PHASE 1: Persist the cognitive gap for tracking
    await persist_cognitive_gap(
        db=db,
        user_id=user.user_id,
        game_id=game_id,
        move_number=move_number,
        gap_analysis=gap_result,
        user_plan=request.user_stated_plan,
        user_confidence=request.user_confidence,
    )
    
    # PHASE 2: Check for recurrence alerts
    recurrence_alert = await check_recurrence_alerts(db, user.user_id, gap_result.get("primary_gap", "unclear"))
    
    return {
        "move_number": move_number,
        "user_move": user_move,
        "best_move": best_move,
        "cp_loss": abs(eval_before - eval_after),
        "gap_analysis": gap_result,
        "coaching_message": coaching_message,
        "time_context": {
            "time_spent": time_spent,
            "clock_remaining": clock_remaining,
        } if time_spent else None,
        "recurrence_alert": recurrence_alert,
    }


# NOTE: Cognitive gap endpoints moved to routes/cognitive.py:
# - GET /cognitive-gaps/summary
# - GET /cognitive-gaps/progress
# - GET /cognitive-gaps/recurring
# - GET /cognitive-gaps/plan-quality
# - GET /drills/recommended
# - GET /drills/from-gap/{gap_type}
# - POST /cognitive-gaps/sync-training

# ==================== RICH COACH AUDIT ====================

@api_router.get("/coach/rich-audit/{game_id}")
async def get_rich_coach_audit(game_id: str, user: User = Depends(get_current_user)):
    """
    Get a comprehensive, coach-like audit of a game.
    
    Combines ALL available data:
    - Game analysis (Stockfish)
    - Cognitive gap history (from reflections)
    - Pattern recurrence data
    - Skill trends
    - Historical baseline comparison
    
    Returns a rich narrative with specific insights and a targeted plan.
    """
    from rich_coach_audit_service import generate_rich_coach_audit
    
    return await generate_rich_coach_audit(db, user.user_id, game_id)


@api_router.get("/coach/rich-audit-latest")
async def get_latest_rich_audit(user: User = Depends(get_current_user)):
    """
    Get rich coach audit for the user's most recently played game.
    """
    from rich_coach_audit_service import generate_rich_coach_audit
    
    # Get the latest game
    latest_game = await db.games.find_one(
        {"user_id": user.user_id},
        {"_id": 0, "game_id": 1}
    )
    
    if not latest_game:
        return {"error": "No games found", "has_audit": False}
    
    return await generate_rich_coach_audit(db, user.user_id, latest_game["game_id"])


# NOTE: /journey/intelligence moved to routes/journey.py

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

@api_router.get("/coach/home-intelligence")
async def get_home_intelligence_endpoint(user: User = Depends(get_current_user)):
    """
    Get comprehensive home intelligence data for the Coach Home page.
    Returns development phase, focus capacity, and actionable advice.
    """
    from home_intelligence_service import get_home_intelligence
    
    data = await get_home_intelligence(db, user.user_id)
    return data


# ==================== COACH STATE - SINGLE SOURCE OF TRUTH ====================


# NOTE: /coach/state moved to routes/coach.py


# NOTE: /coach/last-game-summary, /coach/memory-summary moved to routes/coach.py

@api_router.get("/coach/game-summary/{game_id}")
async def get_game_summary_endpoint(game_id: str, user: User = Depends(get_current_user)):
    """Get GameCoachSummary for a specific game"""
    from coach_state_service import CoachStateService
    
    service = CoachStateService(db)
    summary = await service.get_game_coach_summary(game_id)
    
    if not summary:
        return {"has_summary": False, "game_id": game_id}
    
    if summary.user_id != user.user_id:
        raise HTTPException(status_code=403, detail="Not your game")
    
    return {
        "has_summary": True,
        **summary.to_dict()
    }


@api_router.post("/coach/generate-summary/{game_id}")
async def generate_game_summary_endpoint(game_id: str, user: User = Depends(get_current_user)):
    """
    Manually trigger GameCoachSummary generation for a game.
    
    Normally this happens automatically after analysis completes.
    """
    from coach_state_service import CoachStateService, generate_game_coach_summary
    
    # Get game analysis
    analysis = await db.game_analyses.find_one({
        "game_id": game_id,
        "user_id": user.user_id
    })
    
    if not analysis:
        raise HTTPException(status_code=404, detail="Game analysis not found")
    
    # Get current coach state
    service = CoachStateService(db)
    state = await service.get_coach_state(user.user_id)
    
    if not state:
        state = await service.initialize_coach_state(user.user_id)
    
    # Generate summary
    summary = await generate_game_coach_summary(
        db=db,
        game_id=game_id,
        user_id=user.user_id,
        game_analysis=analysis,
        coach_state=state
    )
    
    return summary.to_dict()


@api_router.get("/coach/theme-stats")
async def get_theme_stats_endpoint(user: User = Depends(get_current_user)):
    """
    Get improvement statistics for user's active theme.
    
    For Progress page "Coach Focus This Week" block:
    - theme name
    - micro rules
    - improvement trend (mistakes before vs after)
    """
    from coach_state_service import CoachStateService
    
    service = CoachStateService(db)
    state = await service.get_coach_state(user.user_id)
    
    if not state:
        return {"has_theme": False}
    
    stats = await service.get_theme_improvement_stats(user.user_id, state.active_theme)
    
    return {
        "has_theme": True,
        "active_theme": state.active_theme.value,
        "theme_display": state.active_theme.value.replace("_", " "),
        "theme_reason": state.theme_reason,
        "micro_rules": state.micro_rules,
        "games_on_theme": state.games_on_theme,
        "days_on_theme": (datetime.now(timezone.utc) - state.theme_started_at).days,
        "improvement_stats": stats
    }


# ==================== BEHAVIORAL MATURITY ROUTES ====================


# NOTE: /coach/maturity endpoints moved to routes/coach.py


# NOTE: /coach/analytics/summary, /coach/analytics/theme-history moved to routes/coach.py

@api_router.get("/coach/analytics/maturity-progression")
async def get_maturity_progression(user: User = Depends(get_current_user)):
    """
    Get full maturity progression history.
    
    Shows the user's journey from Novice -> Developing -> Disciplined -> Advanced
    """
    from coach_analytics_service import get_analytics_service
    
    analytics = get_analytics_service(db)
    progression = await analytics.get_maturity_progression(user.user_id)
    return {"progression": progression}



# ==================== DEEP COACHING SESSION ROUTES ====================

@api_router.get("/coach/deep-session/check")
async def check_deep_session_trigger(user: User = Depends(get_current_user)):
    """
    Check if a deep coaching session should be triggered.
    
    Returns:
    - should_trigger: bool
    - reason: why (scheduled/game_threshold/regression/etc)
    - message: banner text for UI
    """
    from deep_session_service import DeepSessionService
    
    service = DeepSessionService(db)
    result = await service.should_trigger_deep_session(user.user_id)
    return result


@api_router.post("/coach/deep-session/start")
async def start_deep_session(
    request: Dict = Body(default={}),
    user: User = Depends(get_current_user)
):
    """
    Start a new deep coaching session.
    
    Optional body: { "trigger": "manual" }
    """
    from deep_session_service import DeepSessionService, DeepSessionTrigger
    
    trigger_str = request.get("trigger", "manual")
    try:
        trigger = DeepSessionTrigger(trigger_str)
    except:
        trigger = DeepSessionTrigger.MANUAL
    
    service = DeepSessionService(db)
    session = await service.start_session(user.user_id, trigger)
    
    # Return session with step 1 content
    content = service.get_step_content(session, 1)
    
    return {
        "session_id": session.session_id,
        "current_step": session.current_step,
        "total_steps": 6,
        "content": content
    }


@api_router.get("/coach/deep-session/{session_id}")
async def get_deep_session(session_id: str, user: User = Depends(get_current_user)):
    """Get current deep session state and content"""
    from deep_session_service import DeepSessionService
    
    service = DeepSessionService(db)
    session = await service.get_session(session_id)
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.user_id != user.user_id:
        raise HTTPException(status_code=403, detail="Not your session")
    
    content = service.get_step_content(session, session.current_step)
    
    return {
        "session_id": session.session_id,
        "current_step": session.current_step,
        "total_steps": 6,
        "completed": session.completed,
        "theme": session.theme,
        "content": content
    }


@api_router.post("/coach/deep-session/{session_id}/reflection")
async def submit_deep_session_reflection(
    session_id: str,
    request: Dict = Body(...),
    user: User = Depends(get_current_user)
):
    """
    Submit reflection answer (step 2 → step 3).
    
    Body: { "answer": "momentum" }
    """
    from deep_session_service import DeepSessionService
    
    answer = request.get("answer")
    if not answer:
        raise HTTPException(status_code=400, detail="answer required")
    
    service = DeepSessionService(db)
    session = await service.get_session(session_id)
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.user_id != user.user_id:
        raise HTTPException(status_code=403, detail="Not your session")
    
    session = await service.submit_reflection(session_id, answer)
    content = service.get_step_content(session, session.current_step)
    
    return {
        "session_id": session.session_id,
        "current_step": session.current_step,
        "content": content
    }


@api_router.post("/coach/deep-session/{session_id}/advance")
async def advance_deep_session(session_id: str, user: User = Depends(get_current_user)):
    """Advance to next step"""
    from deep_session_service import DeepSessionService
    
    service = DeepSessionService(db)
    session = await service.get_session(session_id)
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.user_id != user.user_id:
        raise HTTPException(status_code=403, detail="Not your session")
    
    session = await service.advance_step(session_id)
    content = service.get_step_content(session, session.current_step)
    
    return {
        "session_id": session.session_id,
        "current_step": session.current_step,
        "content": content
    }


@api_router.post("/coach/deep-session/{session_id}/complete")
async def complete_deep_session(session_id: str, user: User = Depends(get_current_user)):
    """
    Complete the deep session.
    
    Updates CoachState with new micro rule and schedules next session.
    """
    from deep_session_service import DeepSessionService
    
    service = DeepSessionService(db)
    session = await service.get_session(session_id)
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.user_id != user.user_id:
        raise HTTPException(status_code=403, detail="Not your session")
    
    session = await service.complete_session(session_id)
    
    return {
        "success": True,
        "session_id": session.session_id,
        "completed": True,
        "micro_rule_assigned": session.micro_rule_assigned,
        "next_session_due": session.completed_at + timedelta(days=7) if session.completed_at else None
    }


@api_router.get("/coach/deep-session/improvement-check")
async def check_post_session_improvement(user: User = Depends(get_current_user)):
    """
    Check if user improved after completing a deep session.
    
    Returns message for Home page if improvement detected:
    "You handled threat verification better in your last game."
    """
    from deep_session_service import check_post_session_improvement as check_improvement
    
    result = await check_improvement(db, user.user_id)
    return result or {"show_improvement": False}


# NOTE: Behavioral routes moved to routes/behavioral.py:
# - GET /behavioral/analyze/{game_id}
# - GET /behavioral/last-report
# - POST /behavioral/reanalysis/enqueue
# - GET /behavioral/reanalysis/status
# - POST /behavioral/mission/start
# - POST /behavioral/mission/complete
# - GET /behavioral/mission/active
# - GET /behavioral/mission/history
# - GET /behavioral/mission/last-result

# NOTE: Mission routes moved to routes/missions.py:
# - GET /missions/today
# - POST /missions/{mission_id}/start
# - GET /missions/{mission_id}/positions
# - POST /missions/generate-fix
# - POST /missions/{mission_id}/step
# - POST /missions/{mission_id}/complete
# - GET /missions/history
# - GET /missions/focus-mastery


# Helper functions for missions (used by routes/missions.py)
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


def get_sample_drill_positions(focus_pattern: str, count: int = 5) -> list:
    """
    Generate sample drill positions for training when no user-specific positions exist.
    These are common tactical patterns matching the focus area.
    """
    # Sample positions by pattern - real tactical puzzles
    SAMPLE_POSITIONS = {
        "ignored_opponent_forcing": [
            {"fen": "r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 4 4",
             "best_move": "Qxf7+", "explanation": "White can win material - what threat did Black ignore?"},
            {"fen": "r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 2 3",
             "best_move": "Ng5", "explanation": "Look for forcing moves against f7."},
        ],
        "missed_forcing_move": [
            {"fen": "rnbqkb1r/pppp1ppp/5n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R b KQkq - 3 3",
             "best_move": "Nc6", "explanation": "Develop while defending - what threat must Black see?"},
        ],
        "critical_moment_drift": [
            {"fen": "r2qkb1r/ppp2ppp/2n1bn2/3pp3/2B1P3/2NP1N2/PPP2PPP/R1BQK2R w KQkq - 0 6",
             "best_move": "exd5", "explanation": "Critical position - find the strongest continuation."},
        ],
    }
    
    positions = SAMPLE_POSITIONS.get(focus_pattern, SAMPLE_POSITIONS.get("critical_moment_drift", []))
    
    result = []
    for i, pos in enumerate(positions[:count]):
        result.append({
            "position_id": f"sample_{focus_pattern}_{i}",
            "game_id": "sample",
            "fen": pos["fen"],
            "best_move": pos["best_move"],
            "explanation": pos["explanation"],
            "category": focus_pattern,
            "type": "sample",
        })
    
    return result


# NOTE: GET /reflect/v1/post-loss/{game_id} moved to routes/reflect.py

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


@api_router.post("/admin/backfill-openings")
async def backfill_openings(user: User = Depends(get_current_user)):
    """
    Backfill opening info for all games that don't have it.
    This extracts ECO code, opening name from PGN headers.
    """
    from journey_service import backfill_opening_info
    updated = await backfill_opening_info(db, user.user_id)
    return {"success": True, "games_updated": updated}


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


# NOTE: /training/session, /training/due-cards, /training/attempt, /training/progress, /training/set-habit, /training/habits moved to routes/training.py


@api_router.get("/progress/journey")
async def get_progress_journey(user: User = Depends(get_current_user)):
    """
    Progress V2 — trajectory data for the reimagined progress page.
    Returns: accuracy journey (per-game), biggest shift, still leaking area, win rate trend.
    """
    # Get per-game accuracy + blunders chronologically
    analyses = await db.game_analyses.find(
        {"user_id": user.user_id},
        {"_id": 0, "game_id": 1, "stockfish_analysis.accuracy": 1, "stockfish_analysis.blunders": 1,
         "stockfish_analysis.mistakes": 1, "created_at": 1}
    ).sort("created_at", 1).to_list(100)

    games = await db.games.find(
        {"user_id": user.user_id, "is_analyzed": True},
        {"_id": 0, "game_id": 1, "result": 1, "user_color": 1, "opponent_name": 1,
         "white_player": 1, "black_player": 1, "imported_at": 1}
    ).sort("imported_at", 1).to_list(100)

    game_lookup = {g["game_id"]: g for g in games}

    # Build journey points
    journey = []
    for a in analyses:
        gid = a.get("game_id", "")
        sf = a.get("stockfish_analysis", {})
        acc = sf.get("accuracy")
        if acc is None:
            continue
        g = game_lookup.get(gid, {})
        user_color = g.get("user_color", "white")
        result = g.get("result", "")
        user_won = (result == "1-0" and user_color == "white") or (result == "0-1" and user_color == "black")
        is_draw = "1/2" in result

        opp = g.get("opponent_name") or (g.get("white_player") if user_color == "black" else g.get("black_player")) or ""
        journey.append({
            "game_id": gid,
            "accuracy": round(acc, 1),
            "blunders": sf.get("blunders", 0),
            "mistakes": sf.get("mistakes", 0),
            "result": "W" if user_won else ("D" if is_draw else "L"),
            "opponent": opp[:12],
        })

    # Thinking score history from thinking_scores
    scores = await db.thinking_scores.find(
        {"user_id": user.user_id},
        {"_id": 0, "game_id": 1, "habit_scores": 1, "calculated_at": 1}
    ).sort("calculated_at", 1).to_list(100)

    # Build dimension trends (from thinking_scores habit_scores)
    dimensions = {}  # {dimension: [scores over time]}
    for s in scores:
        hs = s.get("habit_scores", {})
        for dim, data in hs.items():
            if isinstance(data, dict) and "score" in data:
                if dim not in dimensions:
                    dimensions[dim] = []
                dimensions[dim].append(data["score"])

    # Find biggest shift (most improved dimension in last 10 vs prev 10)
    biggest_shift = None
    still_leaking = None
    best_delta = 0
    worst_stagnant = None

    for dim, vals in dimensions.items():
        if len(vals) < 5:
            continue
        recent = vals[-min(10, len(vals)):]
        older = vals[:-len(recent)] if len(vals) > len(recent) else vals[:len(vals)//2]
        if not older:
            continue
        recent_avg = sum(recent) / len(recent)
        older_avg = sum(older) / len(older)
        delta = recent_avg - older_avg
        pct = (delta / max(older_avg, 1)) * 100

        readable = dim.replace("_", " ").title()
        if delta > best_delta:
            best_delta = delta
            biggest_shift = {
                "dimension": readable,
                "from_score": round(older_avg, 1),
                "to_score": round(recent_avg, 1),
                "delta_pct": round(pct),
            }
        if abs(delta) < 3 and recent_avg < 50:
            if worst_stagnant is None or recent_avg < worst_stagnant["score"]:
                worst_stagnant = {"dimension": readable, "score": round(recent_avg, 1), "games_stuck": len(vals)}

    still_leaking = worst_stagnant

    # Win rate trend (last 10 vs prev 10)
    recent_games = journey[-10:] if len(journey) >= 10 else journey
    prev_games = journey[-20:-10] if len(journey) >= 20 else journey[:max(len(journey)//2, 1)]
    recent_wins = sum(1 for g in recent_games if g["result"] == "W")
    recent_losses = sum(1 for g in recent_games if g["result"] == "L")
    prev_wins = sum(1 for g in prev_games if g["result"] == "W")
    prev_losses = sum(1 for g in prev_games if g["result"] == "L")

    win_trend = {
        "recent": {"wins": recent_wins, "losses": recent_losses, "total": len(recent_games)},
        "previous": {"wins": prev_wins, "losses": prev_losses, "total": len(prev_games)},
        "improving": recent_wins > prev_wins,
    }

    # Current accuracy
    recent_acc = [g["accuracy"] for g in journey[-10:]] if journey else []
    current_accuracy = round(sum(recent_acc) / len(recent_acc), 1) if recent_acc else 0

    # ── CHESS DNA ──
    chess_dna = None
    try:
        identity = await db.player_identities.find_one({"user_id": user.user_id}, {"_id": 0})
        if identity:
            taxonomy = identity.get("blunder_taxonomy", {})
            by_type = taxonomy.get("by_type", taxonomy) if isinstance(taxonomy, dict) else {}
            worst = max(by_type.items(), key=lambda x: x[1], default=("", 0)) if by_type else ("", 0)
            chess_dna = {
                "archetype": identity.get("play_style", "Developing"),
                "worst_pattern": worst[0].replace("_", " ").title() if worst[0] else None,
                "worst_count": worst[1] if worst[0] else 0,
            }
    except Exception:
        pass

    # ── DANGER ZONES (patterns getting worse) ──
    danger_zones = []
    try:
        from services.pattern_memory_service import get_top_patterns
        patterns = await get_top_patterns(db, user.user_id, limit=3)
        for p in patterns:
            danger_zones.append({
                "label": p.get("label", ""),
                "pattern_type": p.get("pattern_type", ""),
                "recent_count": p.get("recent_count", 0),
                "severity": p.get("severity", ""),
            })
    except Exception:
        pass

    # ── BLUNDER TREND ──
    recent_blunders = sum(g.get("blunders", 0) for g in journey[-10:]) if journey else 0
    prev_blunders = sum(g.get("blunders", 0) for g in journey[-20:-10]) if len(journey) > 10 else 0
    recent_bl_avg = round(recent_blunders / min(len(journey[-10:]), 10), 1) if journey else 0
    prev_bl_avg = round(prev_blunders / max(len(journey[-20:-10]), 1), 1) if len(journey) > 10 else 0

    return {
        "journey": journey,
        "current_accuracy": current_accuracy,
        "games_analyzed": len(journey),
        "biggest_shift": biggest_shift,
        "still_leaking": still_leaking,
        "win_trend": win_trend,
        "chess_dna": chess_dna,
        "danger_zones": danger_zones,
        "blunder_trend": {
            "recent_avg": recent_bl_avg,
            "prev_avg": prev_bl_avg,
            "getting_worse": recent_bl_avg > prev_bl_avg + 0.3,
        },
    }


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

@api_router.post("/profile/recalculate")
async def recalculate_profile_stats(user: User = Depends(get_current_user)):
    """
    Recalculate player profile stats from all game analyses.
    Use this to fix stale/out-of-sync profile data.
    """
    from datetime import datetime, timezone
    
    user_id = user.user_id
    current_time = datetime.now(timezone.utc)
    
    # Get all game analyses for user
    analyses = await db.game_analyses.find(
        {"user_id": user_id},
        {"_id": 0, "game_id": 1, "stockfish_analysis": 1, "analyzed_at": 1}
    ).to_list(1000)
    
    if not analyses:
        return {"error": "No analyzed games found", "games_count": 0}
    
    # Calculate totals
    total_blunders = 0
    total_mistakes = 0
    total_best_moves = 0
    total_inaccuracies = 0
    
    weakness_counts = {}
    
    for analysis in analyses:
        sf = analysis.get("stockfish_analysis", {})
        total_blunders += sf.get("blunders", 0)
        total_mistakes += sf.get("mistakes", 0)
        total_best_moves += sf.get("best_moves", 0)
        total_inaccuracies += sf.get("inaccuracies", 0)
        
        # Extract weaknesses from move evaluations
        for m in sf.get("move_evaluations", []):
            eval_type = m.get("evaluation")
            cp_loss = m.get("cp_loss", 0)
            
            # Only count actual blunders as one-move blunders (not mistakes or inaccuracies)
            if eval_type == "blunder" and 150 <= cp_loss <= 600:
                key = "tactical:one_move_blunder"
                weakness_counts[key] = weakness_counts.get(key, 0) + 1
            elif eval_type == "blunder" and cp_loss > 600:
                key = "tactical:complex_tactical_miss"
                weakness_counts[key] = weakness_counts.get(key, 0) + 1
    
    # Build top weaknesses list
    top_weaknesses = []
    for key, count in sorted(weakness_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
        category, subcategory = key.split(":")
        top_weaknesses.append({
            "category": category,
            "subcategory": subcategory,
            "occurrence_count": count,
            "last_occurrence": current_time.isoformat(),
            "decayed_score": round(count * 1.0, 2)
        })
    
    # Update profile
    await db.player_profiles.update_one(
        {"user_id": user_id},
        {"$set": {
            "games_analyzed_count": len(analyses),
            "total_blunders": total_blunders,
            "total_mistakes": total_mistakes,
            "total_best_moves": total_best_moves,
            "total_inaccuracies": total_inaccuracies,
            "top_weaknesses": top_weaknesses,
            "last_updated": current_time.isoformat(),
            "last_recalculated": current_time.isoformat()
        }}
    )
    
    return {
        "success": True,
        "games_analyzed": len(analyses),
        "total_blunders": total_blunders,
        "total_mistakes": total_mistakes,
        "total_best_moves": total_best_moves,
        "top_weaknesses": top_weaknesses[:3]
    }

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


# NOTE: Settings routes moved to routes/settings.py:
# - GET /settings/email-notifications
# - PUT /settings/email-notifications
# - POST /settings/test-email
# - GET /onboarding/status
# - POST /settings/profile
# - POST /settings/link-account


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


# NOTE: Push notification routes moved to routes/notifications.py:
# - POST /notifications/register-device
# - DELETE /notifications/unregister-device

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


@api_router.get("/lab-coach-pick")
async def get_lab_coach_pick(user: User = Depends(get_current_user)):
    """
    Smart game picker for the Lab page.
    Returns the most educational unreviewed game + reason + all games with reviewed status.
    
    Priority:
    1. Recurring pattern (same mistake in multiple games)
    2. Thrown game (was winning, lost)
    3. Single decisive blunder (one teachable moment)
    Skip: clean wins, already reviewed games
    """
    # Get all analyzed games with analysis data
    games = await db.games.find(
        {"user_id": user.user_id, "is_analyzed": True},
        {"_id": 0}
    ).sort("imported_at", -1).to_list(100)

    analyses_cursor = db.game_analyses.find(
        {"user_id": user.user_id},
        {"_id": 0, "game_id": 1, "stockfish_analysis.blunders": 1, "stockfish_analysis.mistakes": 1,
         "stockfish_analysis.move_evaluations": 1, "stockfish_analysis.accuracy": 1}
    )
    analyses = {a["game_id"]: a async for a in analyses_cursor}

    # Build enriched game list
    enriched = []
    for g in games:
        gid = g.get("game_id", "")
        a = analyses.get(gid, {})
        sf = a.get("stockfish_analysis", {})
        evals = sf.get("move_evaluations", [])
        uc = g.get("user_color", "white")
        result = g.get("result", "")
        user_won = (result == "1-0" and uc == "white") or (result == "0-1" and uc == "black")
        is_draw = "1/2" in result
        blunders = sf.get("blunders", 0)
        mistakes = sf.get("mistakes", 0)
        accuracy = sf.get("accuracy", 0)
        reviewed = g.get("reviewed", False)
        review_status = g.get("review_status", "not_started")  # not_started, in_progress, reviewed

        # Check if was winning (eval > +2 from user's perspective at any point)
        was_winning = False
        max_advantage = 0
        for e in evals:
            ev = e.get("eval_before", 0)
            user_ev = ev if uc == "white" else -ev
            if user_ev > max_advantage:
                max_advantage = user_ev
            if user_ev > 200:
                was_winning = True

        # Count cognitive gaps for pattern matching
        cognitive_gaps = []
        for e in evals:
            gap = e.get("cognitive_gap", "")
            if gap and e.get("cp_loss", 0) >= 100:
                cognitive_gaps.append(gap)

        opp = g.get("opponent_name") or (g.get("white_player") if uc == "black" else g.get("black_player")) or ""

        enriched.append({
            "game_id": gid,
            "opponent": opp,
            "result": "W" if user_won else ("D" if is_draw else "L"),
            "user_color": uc,
            "blunders": blunders,
            "mistakes": mistakes,
            "accuracy": round(accuracy, 1) if accuracy else 0,
            "reviewed": reviewed,
            "review_status": review_status,
            "was_winning": was_winning,
            "max_advantage": round(max_advantage / 100, 1),
            "cognitive_gaps": cognitive_gaps,
            "opening": g.get("opening", ""),
            "summary_headline": g.get("summary", {}).get("headline") if isinstance(g.get("summary"), dict) else None,
        })

    # ── SMART PICK: find the best unreviewed game ──
    unreviewed = [g for g in enriched if not g["reviewed"]]
    pick = None
    pick_reason = ""

    if unreviewed:
        # Count pattern frequency across all games
        pattern_counts = {}
        for g in enriched:
            for gap in g["cognitive_gaps"]:
                pattern_counts[gap] = pattern_counts.get(gap, 0) + 1

        # Priority 1: Recurring pattern (game has a pattern that appears 3+ times across games)
        for g in unreviewed:
            if g["result"] == "W" and g["blunders"] == 0:
                continue  # skip clean wins
            for gap in g["cognitive_gaps"]:
                if pattern_counts.get(gap, 0) >= 3:
                    pick = g
                    readable = gap.replace("_", " ")
                    pick_reason = f"You've made this mistake ({readable}) {pattern_counts[gap]} times. Let's fix it here."
                    break
            if pick:
                break

        # Priority 2: Thrown game (was winning, lost)
        if not pick:
            for g in unreviewed:
                if g["result"] == "L" and g["was_winning"]:
                    pick = g
                    pick_reason = f"You were +{g['max_advantage']} and threw it. This is where rating points go to die."
                    break

        # Priority 3: Loss with single decisive blunder
        if not pick:
            for g in unreviewed:
                if g["result"] == "L" and g["blunders"] >= 1:
                    pick = g
                    pick_reason = f"{g['blunders']} blunder{'s' if g['blunders'] > 1 else ''} decided this game. One lesson to learn."
                    break

        # Fallback: any unreviewed loss
        if not pick:
            for g in unreviewed:
                if g["result"] == "L":
                    pick = g
                    pick_reason = "Your coach thinks this game has something to teach you."
                    break

        # Last resort: any unreviewed game
        if not pick and unreviewed:
            pick = unreviewed[0]
            pick_reason = "Start with your most recent game."

    # Verdict strip
    recent = enriched[:15]
    wins = sum(1 for g in recent if g["result"] == "W")
    losses = sum(1 for g in recent if g["result"] == "L")
    blunder_losses = sum(1 for g in recent if g["result"] == "L" and g["blunders"] >= 1)
    throws = sum(1 for g in recent if g["result"] == "L" and g["was_winning"])

    insight = ""
    if throws >= 2:
        insight = f"{throws} games thrown from winning positions. That's where your rating is leaking."
    elif blunder_losses >= 3:
        insight = f"{blunder_losses} losses from blunders — you're not being outplayed, you're beating yourself."
    elif wins > losses * 2:
        insight = "Strong form. Keep the momentum."
    elif losses > wins:
        insight = "Rough stretch. Review losses, don't just play more."
    else:
        insight = "Steady form. Room to sharpen."

    return {
        "pick": pick,
        "pick_reason": pick_reason,
        "verdict": {"wins": wins, "losses": losses, "total": len(recent), "insight": insight},
        "games": enriched,
        "reviewed_count": sum(1 for g in enriched if g["reviewed"]),
        "total_count": len(enriched),
    }


@api_router.post("/lab-mark-reviewed/{game_id}")
async def mark_game_reviewed(game_id: str, status: str = "reviewed", user: User = Depends(get_current_user)):
    """Mark a game as reviewed or in-progress."""
    from datetime import datetime as dt, timezone as tz
    update = {}
    if status == "reviewed":
        update = {"reviewed": True, "review_status": "reviewed", "reviewed_at": dt.now(tz.utc).isoformat()}
    elif status == "in_progress":
        # Only set in_progress if not already reviewed
        existing = await db.games.find_one({"game_id": game_id, "user_id": user.user_id}, {"reviewed": 1, "_id": 0})
        if existing and existing.get("reviewed"):
            return {"success": True, "status": "already_reviewed"}
        update = {"review_status": "in_progress", "review_started_at": dt.now(tz.utc).isoformat()}
    else:
        update = {"reviewed": True, "review_status": "reviewed", "reviewed_at": dt.now(tz.utc).isoformat()}
    
    result = await db.games.update_one(
        {"game_id": game_id, "user_id": user.user_id},
        {"$set": update}
    )
    return {"success": result.modified_count > 0, "status": status}


@api_router.get("/dashboard-stats")
async def get_dashboard_stats(user: User = Depends(get_current_user)):
    """Get dashboard statistics including player profile for the current user"""
    total_games = await db.games.count_documents({"user_id": user.user_id})
    
    # Use game_analyses count as the source of truth for analyzed games
    # (more accurate than games.is_analyzed which can get out of sync)
    analyzed_games = await db.game_analyses.count_documents({"user_id": user.user_id})
    
    # Count games in queue / retry / failed states
    active_queued_games = await db.analysis_queue.count_documents({
        "user_id": user.user_id,
        "status": {"$in": ["pending", "processing"]}
    })
    queued_games = await db.analysis_queue.count_documents({
        "user_id": user.user_id,
        "status": {"$in": ["pending", "processing", "failed"]}
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
        {"user_id": user.user_id, "status": {"$in": ["pending", "processing", "failed"]}},
        {
            "_id": 0,
            "game_id": 1,
            "status": 1,
            "queued_at": 1,
            "started_at": 1,
            "retry_count": 1,
            "last_error": 1,
            "last_error_at": 1,
            "retrying": 1,
            "failed_at": 1,
        }
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
            game["started_at"] = queue_info.get("started_at")
            game["retry_count"] = queue_info.get("retry_count", 0)
            game["last_error"] = queue_info.get("last_error")
            game["last_error_at"] = queue_info.get("last_error_at")
            game["retrying"] = queue_info.get("retrying", False)
            game["failed_at"] = queue_info.get("failed_at")
            in_queue_list.append(game)
        elif game.get("is_analyzed"):
            analysis = await db.game_analyses.find_one(
                {"game_id": game_id, "user_id": user.user_id},
                {"_id": 0, "stockfish_analysis.accuracy": 1, "stockfish_analysis.move_evaluations": 1,
                 "stockfish_analysis.blunders": 1, "stockfish_analysis.mistakes": 1,
                 "game_summary": 1}
            )
            if analysis:
                sf = analysis.get("stockfish_analysis", {})
                accuracy = sf.get("accuracy", 0)
                move_evals = sf.get("move_evaluations", [])
                game["accuracy"] = accuracy
                game["blunders"] = sf.get("blunders", 0)
                game["mistakes"] = sf.get("mistakes", 0)
                
                # Include rich game summary if available
                game_summary = analysis.get("game_summary")
                if game_summary:
                    game["summary"] = game_summary.get("display", {})
                    game["key_mistakes"] = game_summary.get("key_mistakes", [])[:2]  # Top 2 for list
                    game["problem_phase"] = game_summary.get("problem_phase")
                    game["tags"] = game_summary.get("tags", [])
                
                # Set opponent name for display
                user_color = game.get("user_color", "white")
                if user_color == "white":
                    game["opponent"] = game.get("black_player", "Opponent")
                else:
                    game["opponent"] = game.get("white_player", "Opponent")
                
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
    
    # Note: analyzed_games was already set correctly using game_analyses.count_documents()
    # The analyzed_list here only contains games from the recent 100 games query
    # which may not include all historically analyzed games
    
    # Build recent_games for backward compatibility (top 10 of all games)
    recent_games = all_games[:10]
    
    analyses = await db.game_analyses.find(
        {"user_id": user.user_id},
        {"_id": 0, "blunders": 1, "mistakes": 1, "best_moves": 1, "stockfish_analysis": 1}
    ).to_list(500)
    
    # Sum stats - check both top-level fields and stockfish_analysis (prefer stockfish_analysis)
    total_blunders = 0
    total_mistakes = 0
    total_best_moves = 0
    
    for a in analyses:
        sf = a.get('stockfish_analysis', {})
        # Prefer Stockfish analysis if available, otherwise use top-level
        total_blunders += sf.get('blunders', 0) or a.get('blunders', 0)
        total_mistakes += sf.get('mistakes', 0) or a.get('mistakes', 0)
        total_best_moves += sf.get('best_moves', 0) or a.get('best_moves', 0)
    
    # Build response with profile data
    response = {
        "total_games": total_games,
        "analyzed_games": analyzed_games,
        "queued_games": len(in_queue_list),
        "active_queue_games": active_queued_games,
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


@api_router.post("/migrate-game-summaries")
async def migrate_game_summaries(user: User = Depends(get_current_user)):
    """
    Migrate existing games to include rich summaries.
    Call this once to backfill summaries for games that have V5 data.
    """
    try:
        from services.game_summary_service import migrate_existing_summaries
        stats = await migrate_existing_summaries(db, user.user_id, limit=50)
        return {
            "success": True,
            "message": f"Migrated {stats['updated']} games",
            "stats": stats
        }
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        return {"success": False, "error": str(e)}


# ─── USER THOUGHTS (Reflection integration) ─────────────────────────────────

class ThoughtSubmission(BaseModel):
    move_number: int
    fen: str = ""
    thought_text: str


@api_router.post("/games/{game_id}/thought")
async def save_user_thought(
    game_id: str,
    data: ThoughtSubmission,
    user: User = Depends(get_current_user)
):
    """
    Save user's thought for a specific move ("What were you thinking?").
    This helps build cognitive gap analysis.
    """
    try:
        thought_doc = {
            "game_id": game_id,
            "user_id": user.user_id,
            "move_number": data.move_number,
            "fen": data.fen,
            "thought_text": data.thought_text,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        
        # Upsert - one thought per move per game
        await db.user_thoughts.update_one(
            {"game_id": game_id, "user_id": user.user_id, "move_number": data.move_number},
            {"$set": thought_doc},
            upsert=True
        )
        
        return {"success": True, "message": "Thought saved"}
    except Exception as e:
        logger.error(f"Failed to save thought: {e}")
        raise HTTPException(status_code=500, detail="Failed to save thought")


@api_router.get("/games/{game_id}/thoughts")
async def get_user_thoughts(
    game_id: str,
    user: User = Depends(get_current_user)
):
    """
    Get all user thoughts for a game.
    """
    try:
        thoughts = await db.user_thoughts.find(
            {"game_id": game_id, "user_id": user.user_id},
            {"_id": 0}
        ).to_list(100)
        
        return {"thoughts": thoughts}
    except Exception as e:
        logger.error(f"Failed to get thoughts: {e}")
        return {"thoughts": []}


# ─── PLAN ANALYSIS (Cognitive Gap Detection) ────────────────────────────────

class PlanAnalysisRequest(BaseModel):
    fen: str  # Position before user's move
    user_move: str  # The move user played
    plan_moves: List[str]  # User's intended continuation
    plan_reasoning: str = ""  # User's text explanation


@api_router.post("/analyze-plan")
async def analyze_user_plan_endpoint(
    data: PlanAnalysisRequest,
    user: User = Depends(get_current_user)
):
    """
    Analyze user's intended plan to identify where their calculation failed.
    
    Compares user's planned line with Stockfish's best responses to find
    the exact move where calculation broke down and identify the cognitive gap.
    """
    try:
        from services.plan_analysis_service import analyze_user_plan
        from dataclasses import asdict
        
        analysis = await analyze_user_plan(
            fen=data.fen,
            user_move=data.user_move,
            user_plan_moves=data.plan_moves,
            user_plan_reasoning=data.plan_reasoning
        )
        
        return {
            "success": True,
            "analysis": asdict(analysis)
        }
        
    except Exception as e:
        logger.error(f"Plan analysis failed: {e}")
        return {
            "success": False,
            "error": str(e)
        }


# ─── LOSS STREAK / PLATEAU BREAKER TRIGGER ──────────────────────────────────

@api_router.get("/loss-streak-status")
async def get_loss_streak_status(user: User = Depends(get_current_user)):
    """
    Check if user is on a losing streak and should be shown the Plateau Breaker.
    
    Trigger conditions:
    - 3+ consecutive losses
    
    Returns:
    - show_plateau_breaker: bool
    - consecutive_losses: int
    - last_games: summary of recent results
    """
    try:
        # Get last 10 games sorted by date (most recent first)
        games = await db.games.find(
            {"user_id": user.user_id},
            {"_id": 0, "game_id": 1, "result": 1, "user_color": 1, "played_at": 1}
        ).sort("played_at", -1).to_list(10)
        
        if not games:
            return {
                "show_plateau_breaker": False,
                "consecutive_losses": 0,
                "message": "No games found",
                "last_games": []
            }
        
        # Count consecutive losses from most recent
        consecutive_losses = 0
        last_games_summary = []
        
        for game in games:
            result = game.get("result", "")
            user_color = game.get("user_color", "white")
            
            # Determine if user won, lost, or drew
            is_white_win = result == "1-0"
            is_black_win = result == "0-1"
            is_draw = result == "1/2-1/2"
            
            user_won = (user_color == "white" and is_white_win) or (user_color == "black" and is_black_win)
            user_lost = (user_color == "white" and is_black_win) or (user_color == "black" and is_white_win)
            
            game_summary = {
                "game_id": game.get("game_id"),
                "result": "win" if user_won else "loss" if user_lost else "draw"
            }
            last_games_summary.append(game_summary)
            
            # Count streak (only consecutive losses from the start)
            if len(last_games_summary) <= 5:  # Only check last 5 for streak
                if user_lost and consecutive_losses == len(last_games_summary) - 1:
                    consecutive_losses += 1
                elif not user_lost and consecutive_losses == len(last_games_summary) - 1:
                    # Streak broken - stop counting
                    pass
        
        # Trigger Plateau Breaker after 3+ consecutive losses
        show_plateau_breaker = consecutive_losses >= 3
        
        # Build message
        if consecutive_losses >= 3:
            message = f"You've lost {consecutive_losses} games in a row. Time to identify what's going wrong."
        elif consecutive_losses == 2:
            message = "Two losses in a row. One more and we need to talk."
        elif consecutive_losses == 1:
            message = "Shake off that last loss."
        else:
            message = "You're doing fine. Keep playing!"
        
        return {
            "show_plateau_breaker": show_plateau_breaker,
            "consecutive_losses": consecutive_losses,
            "message": message,
            "last_games": last_games_summary[:5]
        }
        
    except Exception as e:
        logger.error(f"Loss streak check failed: {e}")
        return {
            "show_plateau_breaker": False,
            "consecutive_losses": 0,
            "message": "Could not check loss streak",
            "last_games": []
        }


@api_router.get("/blind-spots")
async def get_blind_spots(user: User = Depends(get_current_user)):
    """
    Get user's blind spots - recurring turning point patterns across games.
    
    Returns categorized patterns that cost the user games, for home page display.
    """
    
    # Get recent game analyses with turning points
    analyses = await db.game_analyses.find(
        {"user_id": user.user_id},
        {"_id": 0, "game_id": 1, "turning_point": 1, "stockfish_analysis": 1}
    ).sort("analyzed_at", -1).to_list(20)
    
    if not analyses:
        return {
            "blind_spots": [],
            "total_games_analyzed": 0,
            "games_with_turning_points": 0
        }
    
    # Count turning point categories
    category_counts = {}
    pattern_examples = {}
    games_with_tp = 0
    
    for analysis in analyses:
        tp = analysis.get("turning_point")
        if not tp:
            continue
            
        games_with_tp += 1
        category = tp.get("category", "unknown")
        category_label = tp.get("category_label", category.replace("_", " ").title())
        pattern_name = tp.get("pattern_name", "")
        
        if category not in category_counts:
            category_counts[category] = {
                "count": 0,
                "label": category_label,
                "patterns": [],
                "game_ids": []
            }
        
        category_counts[category]["count"] += 1
        category_counts[category]["game_ids"].append(analysis.get("game_id"))
        
        if pattern_name and pattern_name not in category_counts[category]["patterns"]:
            category_counts[category]["patterns"].append(pattern_name)
    
    # Sort by count and build response
    sorted_categories = sorted(
        category_counts.items(),
        key=lambda x: x[1]["count"],
        reverse=True
    )
    
    # Training focus mapping
    training_focus_map = {
        "tactical_blindness": "tactics",
        "threat_ignorance": "threat_awareness",
        "positional_mistake": "positional",
        "calculation_error": "calculation",
        "piece_coordination": "piece_coordination",
        "king_safety": "king_safety",
        "one_move_blunder": "blunder_check"
    }
    
    blind_spots = []
    for category, data in sorted_categories[:5]:  # Top 5 blind spots
        # Generate description based on patterns
        patterns_str = ", ".join(data["patterns"][:3]) if data["patterns"] else "various patterns"
        
        blind_spots.append({
            "category": category,
            "label": data["label"],
            "count": data["count"],
            "total_games": len(analyses),
            "percentage": round(data["count"] / len(analyses) * 100),
            "patterns": data["patterns"][:3],
            "description": f"Lost {data['count']} games to {patterns_str.lower()}",
            "training_focus": training_focus_map.get(category, "general"),
            "severity": "high" if data["count"] >= 3 else "medium" if data["count"] >= 2 else "low"
        })
    
    return {
        "blind_spots": blind_spots,
        "total_games_analyzed": len(analyses),
        "games_with_turning_points": games_with_tp
    }


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

# NOTE: Opening repertoire endpoint moved to routes/openings.py

# NOTE: Notification routes moved to routes/notifications.py:
# - GET /notifications
# - POST /notifications/{notification_id}/read
# - POST /notifications/read-all

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


@api_router.post("/training/openings/{opening_key}/quiz/submit")
async def submit_opening_quiz(opening_key: str, request: Request, user: User = Depends(get_current_user)):
    """
    Submit quiz answers and get score with feedback.
    """
    data = await request.json()
    answers = data.get("answers", [])
    
    from opening_trainer_service import get_opening_quiz, OPENINGS_DATABASE
    from services.coach_memory import update_memory_after_game
    
    opening = OPENINGS_DATABASE.get(opening_key)
    if not opening:
        raise HTTPException(status_code=404, detail="Opening not found")
    
    # Get questions to compare answers
    questions = await get_opening_quiz(db, user.user_id, opening_key)
    
    # Score the quiz
    results = []
    correct_count = 0
    total = len(questions)
    
    for i, q in enumerate(questions):
        user_answer = answers[i] if i < len(answers) else None
        
        is_correct = False
        if q["type"] == "position":
            # Check if user found the winning move
            is_correct = user_answer and user_answer.lower() == q["correct_move"].lower()
        elif q["type"] == "concept":
            # Check if answer is in the options
            is_correct = user_answer in q.get("options", [q["correct_answer"]])
        elif q["type"] == "move_order":
            # Check if user got the main line
            is_correct = user_answer and user_answer.lower().replace(" ", "") == q["correct_answer"].lower().replace(" ", "")
        
        if is_correct:
            correct_count += 1
        
        results.append({
            "question_index": i,
            "type": q["type"],
            "user_answer": user_answer,
            "correct_answer": q.get("correct_move") or q.get("correct_answer"),
            "is_correct": is_correct,
            "explanation": q.get("explanation", "")
        })
    
    # Calculate score and mastery level
    score = (correct_count / total * 100) if total > 0 else 0
    
    if score >= 90:
        mastery_feedback = "Excellent! You've mastered this opening."
        new_level = "mastered"
    elif score >= 70:
        mastery_feedback = "Good job! Keep practicing the traps."
        new_level = "practiced"
    elif score >= 50:
        mastery_feedback = "Getting there. Focus on the key ideas."
        new_level = "learning"
    else:
        mastery_feedback = "This opening needs more study. Let's practice it in games!"
        new_level = "introduced"
    
    # Update user progress
    await db.user_opening_progress.update_one(
        {"user_id": user.user_id, "opening_name": opening["name"]},
        {
            "$set": {
                "last_quiz_score": score,
                "last_quiz_date": datetime.now(timezone.utc).isoformat(),
                "mastery_level": new_level
            },
            "$push": {
                "quiz_scores": {
                    "score": score,
                    "date": datetime.now(timezone.utc).isoformat(),
                    "questions_count": total,
                    "correct_count": correct_count
                }
            }
        },
        upsert=True
    )
    
    return {
        "opening": opening_key,
        "opening_name": opening["name"],
        "score": score,
        "correct": correct_count,
        "total": total,
        "mastery_level": new_level,
        "mastery_feedback": mastery_feedback,
        "results": results
    }


@api_router.get("/training/opening-progress")
async def get_opening_progress(user: User = Depends(get_current_user)):
    """
    Get combined opening progress: coach lessons + real game stats.
    Used by Lab page Habits tab to show complete opening journey.
    """
    from opening_trainer_service import get_user_opening_stats
    
    # Get coach lesson progress
    coach_progress = await db.user_opening_progress.find(
        {"user_id": user.user_id},
        {"_id": 0}
    ).to_list(50)
    
    # Get real game stats
    real_stats = await get_user_opening_stats(db, user.user_id)
    
    # Create lookup by name
    real_stats_by_name = {}
    for stat in real_stats:
        name_key = stat.get("name", "").lower().strip()
        real_stats_by_name[name_key] = stat
    
    # Combine the data
    combined = []
    seen_openings = set()
    
    # First, add all coach-taught openings with their real game stats
    for progress in coach_progress:
        opening_name = progress.get("opening_name", "")
        name_key = opening_name.lower().strip()
        seen_openings.add(name_key)
        
        # Find matching real game stats
        real = real_stats_by_name.get(name_key, {})
        
        # Get loss phase data
        loss_phases = progress.get("loss_phases", {})
        total_losses = progress.get("total_losses", 0)
        dominant_loss_phase = None
        if loss_phases and total_losses > 0:
            # Find which phase has the most losses
            max_losses = 0
            for phase, count in loss_phases.items():
                if count > max_losses:
                    max_losses = count
                    dominant_loss_phase = phase
        
        combined.append({
            "opening_name": opening_name,
            "mastery_level": progress.get("mastery_level", "unknown"),
            "times_practiced": progress.get("times_practiced", 0),
            "times_applied_in_games": progress.get("times_applied_in_games", 0),  # Theory applied tracking
            "correct_applications": progress.get("correct_applications", 0),
            "last_practiced": progress.get("last_practiced_at"),
            "last_quiz_score": progress.get("last_quiz_score"),
            "coach_taught": True,
            "real_games": real.get("games_played", 0),
            "real_win_rate": real.get("win_rate", 0),
            "real_accuracy": real.get("avg_accuracy", 0),
            "needs_work": real.get("games_played", 0) > 2 and real.get("win_rate", 0) < 50,
            "loss_phases": loss_phases,  # {"opening": 2, "middlegame": 5, "endgame": 1}
            "total_losses": total_losses,
            "dominant_loss_phase": dominant_loss_phase  # "middlegame" - where user loses most
        })
    
    # Add openings played in real games but not taught by coach
    for stat in real_stats:
        name_key = stat.get("name", "").lower().strip()
        if name_key not in seen_openings and stat.get("games_played", 0) >= 2:
            combined.append({
                "opening_name": stat.get("name", "Unknown"),
                "mastery_level": "unknown",
                "times_practiced": 0,
                "coach_taught": False,
                "real_games": stat.get("games_played", 0),
                "real_win_rate": stat.get("win_rate", 0),
                "real_accuracy": stat.get("avg_accuracy", 0),
                "needs_work": stat.get("win_rate", 0) < 50
            })
    
    # Sort: needs_work first, then by real_games
    combined.sort(key=lambda x: (-int(x.get("needs_work", False)), -x.get("real_games", 0)))
    
    return {
        "progress": combined,
        "total_taught": len([c for c in combined if c.get("coach_taught")]),
        "total_learned": len([c for c in combined if c.get("mastery_level") in ["mastered", "comfortable", "practiced"]]),
        "total_played": len([c for c in combined if c.get("real_games", 0) > 0]),
        "needs_attention": len([c for c in combined if c.get("needs_work")])
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
# OPENING TRAINING LAB ENDPOINTS - MOVED TO routes/openings.py
# ============================================================================


# ============================================================================
# TRICK TRAINING ENDPOINTS
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
# HOME: PATTERN PRESCRIPTION
# ============================================================================


@api_router.get("/home/dashboard-v2")
async def get_home_dashboard_v2(user: User = Depends(get_current_user)):
    """
    V2 Home Dashboard — everything the reimagined home page needs in one call.
    Returns: last battle (critical position + FEN), chess DNA, #1 pattern to fix, contextual action.
    """
    from services.game_coach_summary import compute_game_summary, compute_game_memory

    result = {
        "last_battle": None,
        "chess_dna": None,
        "one_thing_to_fix": None,
        "context_action": None,
        "accuracy": 0,
        "games_analyzed": 0,
    }

    try:
        # Get last analyzed game
        last_game = await db.games.find_one(
            {"user_id": user.user_id, "is_analyzed": True},
            {"_id": 0}
        , sort=[("imported_at", -1)])

        if not last_game:
            result["context_action"] = {"type": "import", "label": "Import your first game", "href": "/import"}
            return result

        game_id = last_game.get("game_id")
        user_color = last_game.get("user_color", "white")
        game_result = last_game.get("result", "")
        import re
        pgn = last_game.get("pgn", "")
        elo_tag = "WhiteElo" if user_color == "white" else "BlackElo"
        m = re.search(rf'\[{elo_tag} "(\d+)"\]', pgn)
        user_rating = int(m.group(1)) if m else 0

        # Get analysis
        analysis = await db.game_analyses.find_one(
            {"game_id": game_id, "user_id": user.user_id},
            {"_id": 0, "stockfish_analysis.move_evaluations": 1}
        )

        if analysis:
            evals = analysis.get("stockfish_analysis", {}).get("move_evaluations", [])

            # Find the critical moment (worst user move)
            if evals:
                user_is_white = user_color == "white"
                user_moves = []
                for i, ev in enumerate(evals):
                    is_user = (i % 2 == 0 and user_is_white) or (i % 2 == 1 and not user_is_white)
                    if is_user and ev.get("cp_loss", 0) >= 100:
                        user_moves.append(ev)

                if user_moves:
                    worst = max(user_moves, key=lambda x: x.get("cp_loss", 0))
                    result["last_battle"] = {
                        "game_id": game_id,
                        "opponent": last_game.get("opponent_name") or (last_game.get("white_player") if user_color == "black" else last_game.get("black_player")),
                        "result": game_result,
                        "user_color": user_color,
                        "fen": worst.get("fen_before", ""),
                        "your_move": worst.get("move", ""),
                        "best_move": worst.get("best_move", ""),
                        "cp_loss": worst.get("cp_loss", 0),
                        "move_number": worst.get("move_number", 0),
                    }

                # Compute summary + memory
                summary = compute_game_summary(evals, game_result, user_color, last_game.get("opening", ""))
                memory = await compute_game_memory(db, user.user_id, summary, user_rating)

                result["chess_dna"] = {
                    "archetype": memory.get("identity", {}).get("archetype", "Developing"),
                    "before_line": memory.get("identity", {}).get("before_line", ""),
                    "after_line": memory.get("identity", {}).get("after_line", ""),
                    "diagnosis": summary.get("diagnosis", ""),
                    "root_cause": summary.get("root_cause", ""),
                }

                # Impact projection as the "one thing to fix"
                impact = memory.get("impact", {})
                if impact.get("estimated_rating_gain", 0) > 0:
                    result["one_thing_to_fix"] = {
                        "pattern": impact.get("pattern_name", ""),
                        "stat_line": impact.get("stat_line", ""),
                        "fix_line": impact.get("fix_line", ""),
                        "diff_line": impact.get("diff_line", ""),
                        "severity": impact.get("severity", ""),
                        "rating_gain": impact.get("estimated_rating_gain", 0),
                    }

        # Accuracy from profile
        profile = await db.player_profiles.find_one({"user_id": user.user_id}, {"_id": 0})
        if profile:
            result["accuracy"] = profile.get("average_accuracy", 0)

        # Games count
        result["games_analyzed"] = await db.games.count_documents({"user_id": user.user_id, "is_analyzed": True})

        # Contextual action
        user_won = (game_result == "1-0" and user_color == "white") or (game_result == "0-1" and user_color == "black")
        if not user_won and "1/2" not in game_result:
            result["context_action"] = {"type": "review_loss", "label": "Review this loss", "href": f"/game/{game_id}"}
        else:
            result["context_action"] = {"type": "play", "label": "Play another game", "href": "/play-with-coach"}

        # ── STREAK ──
        recent_games = await db.games.find(
            {"user_id": user.user_id, "is_analyzed": True},
            {"_id": 0, "result": 1, "user_color": 1}
        ).sort("imported_at", -1).limit(20).to_list(20)

        streak_type = None
        streak_count = 0
        for g in recent_games:
            res = g.get("result", "")
            uc = g.get("user_color", "white")
            won = (res == "1-0" and uc == "white") or (res == "0-1" and uc == "black")
            draw = "1/2" in res
            r = "W" if won else ("D" if draw else "L")
            if streak_type is None:
                streak_type = r
            if r == streak_type:
                streak_count += 1
            else:
                break

        result["streak"] = {"type": streak_type or "none", "count": streak_count}

        # ── PATTERNS (top 3 with trend) ──
        from services.pattern_memory_service import get_top_patterns
        patterns = await get_top_patterns(db, user.user_id, limit=3)
        result["patterns"] = [
            {
                "label": p.get("label", ""),
                "pattern_type": p.get("pattern_type", ""),
                "recent_count": p.get("recent_count", 0),
                "total_count": p.get("total_count", 0),
                "severity": p.get("severity", ""),
            }
            for p in patterns
        ]

    except Exception as e:
        logger.error(f"Home dashboard V2 error: {e}")

    return result


@api_router.get("/home/pattern-prescription")
async def get_pattern_prescription(
    user: User = Depends(get_current_user)
):
    """
    Get the user's top recurring patterns with matching training position counts.
    For the Home page: "You've missed forks 4 times → 3 fork positions waiting in Training"
    """
    from services.pattern_memory_service import get_top_patterns
    from services.community_training_service import get_community_position_count
    
    patterns = await get_top_patterns(db, user.user_id, limit=3)
    
    # For each pattern, count available training positions
    prescriptions = []
    for p in patterns:
        pattern_type = p["pattern_type"]
        
        # Count unsolved positions of this pattern type for the user
        solved_ids = set()
        solved = await db.training_solve_attempts.find(
            {"user_id": user.user_id, "pattern_type": pattern_type, "solved": True},
            {"position_id": 1, "_id": 0}
        ).to_list(100)
        solved_ids = {s["position_id"] for s in solved}
        
        # Count available unsolved positions
        query = {"pattern_type": pattern_type}
        if solved_ids:
            query["position_id"] = {"$nin": list(solved_ids)}
        
        available = await db.community_training_positions.count_documents(query)
        
        prescriptions.append({
            "pattern_type": pattern_type,
            "label": p["label"],
            "recent_count": p["recent_count"],
            "total_count": p["total_count"],
            "severity": p["severity"],
            "training_positions_available": available,
        })
    
    return {"prescriptions": prescriptions}


# ============================================================================
# COMMUNITY INTELLIGENCE TRAINING
# ============================================================================

@api_router.post("/training/extract-positions/{game_id}")
async def extract_training_positions_endpoint(
    game_id: str,
    user: User = Depends(get_current_user)
):
    """Extract training-worthy positions from a V5 decrypted game."""
    from services.community_training_service import extract_training_positions
    positions = await extract_training_positions(db, game_id, user.user_id)
    return {
        "extracted": len(positions),
        "game_id": game_id,
        "positions": [{"position_id": p["position_id"], "pattern_type": p["pattern_type"], "cp_loss": p["cp_loss"]} for p in positions]
    }


@api_router.get("/training/community-feed")
async def get_training_feed_endpoint(
    limit: int = 10,
    pattern: Optional[str] = None,
    user: User = Depends(get_current_user)
):
    """Get mixed training feed: own positions + community positions. Optionally filter by pattern_type."""
    from services.community_training_service import get_training_feed
    return await get_training_feed(db, user.user_id, limit, pattern_filter=pattern)


class SolveAttemptRequest(BaseModel):
    position_id: str
    user_move: str
    time_taken_seconds: int = 0


@api_router.post("/training/solve-attempt")
async def record_solve_attempt_endpoint(
    data: SolveAttemptRequest,
    user: User = Depends(get_current_user)
):
    """Record a training position solve attempt."""
    from services.community_training_service import record_solve_attempt
    return await record_solve_attempt(
        db, user.user_id, data.position_id, data.user_move, data.time_taken_seconds
    )


@api_router.get("/training/pattern-stats")
async def get_pattern_stats_endpoint(
    user: User = Depends(get_current_user)
):
    """Get user's pattern-level solve stats."""
    from services.community_training_service import get_user_pattern_stats
    stats = await get_user_pattern_stats(db, user.user_id)
    return {"patterns": stats}


@api_router.get("/training/community-count")
async def get_community_count_endpoint():
    """Get total community training positions count."""
    from services.community_training_service import get_community_position_count
    count = await get_community_position_count(db)
    return {"count": count}


# ============================================================================
# ENDGAME LESSONS
# ============================================================================

@api_router.get("/endgames/categories")
async def get_endgame_categories():
    """Return all endgame categories and lessons."""
    from services.endgame_theory_service import get_all_categories
    return {"categories": get_all_categories()}


@api_router.get("/endgames/lesson/{category_key}/{lesson_key}")
async def get_endgame_lesson(category_key: str, lesson_key: str):
    """Return a specific endgame lesson with positions (no answers)."""
    from services.endgame_theory_service import get_lesson
    lesson = get_lesson(category_key, lesson_key)
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found")
    return lesson


class EndgameCheckMoveRequest(BaseModel):
    category_key: str
    lesson_key: str
    position_index: int
    user_move_uci: str


@api_router.post("/endgames/check-move")
async def check_endgame_move(req: EndgameCheckMoveRequest):
    """Check if the user's move is correct for the given endgame position."""
    from services.endgame_theory_service import check_move
    result = check_move(req.category_key, req.lesson_key, req.position_index, req.user_move_uci)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


# ============================================================================
# ADMIN & FEEDBACK SYSTEM
# ============================================================================

@api_router.get("/progress/player-profile")
async def get_player_profile_endpoint(user: User = Depends(get_current_user)):
    """Get player's coaching narrative profile."""
    from services.player_profile_service import get_player_profile
    profile = await get_player_profile(db, user.user_id)
    return profile


async def require_admin(user: User = Depends(get_current_user)):
    """Dependency that requires super_admin or admin role."""
    if user.role not in ("super_admin", "admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


async def require_super_admin(user: User = Depends(get_current_user)):
    """Dependency that requires super_admin role."""
    if user.role != "super_admin":
        raise HTTPException(status_code=403, detail="Super admin access required")
    return user


# --- Admin Overview ---

@api_router.get("/admin/overview")
async def admin_overview(user: User = Depends(require_admin)):
    """Platform overview stats for admin dashboard."""
    from datetime import timedelta
    now = datetime.now(timezone.utc)
    seven_days_ago = (now - timedelta(days=7)).isoformat()
    thirty_days_ago = (now - timedelta(days=30)).isoformat()

    total_users = await db.users.count_documents({})
    total_games = await db.games.count_documents({})
    total_analyses = await db.game_analyses.count_documents({})

    # Active users (users who have games in last 7d/30d)
    recent_sessions_7d = await db.user_sessions.distinct(
        "user_id", {"created_at": {"$gte": seven_days_ago}}
    )
    recent_sessions_30d = await db.user_sessions.distinct(
        "user_id", {"created_at": {"$gte": thirty_days_ago}}
    )

    # Community training pool
    community_positions = await db.community_training_positions.count_documents({})

    # Feedback counts
    feedback_pending = await db.move_feedback.count_documents({"status": "pending"})
    feedback_total = await db.move_feedback.count_documents({})

    # Recent signups (last 5)
    recent_users = []
    async for u in db.users.find({}, {"_id": 0, "user_id": 1, "name": 1, "email": 1, "created_at": 1, "role": 1}).sort("created_at", -1).limit(5):
        recent_users.append(u)

    return {
        "total_users": total_users,
        "active_7d": len(recent_sessions_7d),
        "active_30d": len(recent_sessions_30d),
        "total_games": total_games,
        "total_analyses": total_analyses,
        "community_positions": community_positions,
        "feedback_pending": feedback_pending,
        "feedback_total": feedback_total,
        "recent_users": recent_users,
    }


# --- User Management ---

@api_router.get("/admin/users")
async def admin_list_users(
    search: str = None,
    role: str = None,
    sort_by: str = "created_at",
    limit: int = 50,
    skip: int = 0,
    user: User = Depends(require_admin),
):
    """List all users with optional search/filter."""
    query = {}
    if search:
        query["$or"] = [
            {"name": {"$regex": search, "$options": "i"}},
            {"email": {"$regex": search, "$options": "i"}},
            {"user_id": {"$regex": search, "$options": "i"}},
        ]
    if role:
        query["role"] = role

    users_list = []
    async for u in db.users.find(query, {"_id": 0}).sort(sort_by, -1).skip(skip).limit(limit):
        # Add game count
        game_count = await db.games.count_documents({"user_id": u["user_id"]})
        u["game_count"] = game_count
        u["role"] = u.get("role", "user")
        users_list.append(u)

    total = await db.users.count_documents(query)
    return {"users": users_list, "total": total}


@api_router.get("/admin/users/{target_user_id}")
async def admin_user_detail(target_user_id: str, user: User = Depends(require_admin)):
    """Detailed view of a specific user."""
    target = await db.users.find_one({"user_id": target_user_id}, {"_id": 0})
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    target["role"] = target.get("role", "user")

    # Game stats
    game_count = await db.games.count_documents({"user_id": target_user_id})
    analysis_count = await db.game_analyses.count_documents({"user_id": target_user_id})

    # Opening progress
    opening_progress = []
    async for op in db.user_opening_progress.find({"user_id": target_user_id}, {"_id": 0}).limit(10):
        opening_progress.append(op)

    # Player habits
    habits = await db.player_habits.find_one({"user_id": target_user_id}, {"_id": 0})

    # Recent games
    recent_games = []
    async for g in db.games.find({"user_id": target_user_id}, {"_id": 0, "game_id": 1, "opening": 1, "result": 1, "user_color": 1, "date_played": 1, "platform": 1}).sort("imported_at", -1).limit(10):
        recent_games.append(g)

    # Feedback from this user
    user_feedback = []
    async for fb in db.move_feedback.find({"user_id": target_user_id}, {"_id": 0}).sort("created_at", -1).limit(10):
        fb["id"] = str(fb.get("feedback_id", ""))
        user_feedback.append(fb)

    return {
        "user": target,
        "game_count": game_count,
        "analysis_count": analysis_count,
        "opening_progress": opening_progress,
        "habits": habits,
        "recent_games": recent_games,
        "feedback": user_feedback,
    }


class CreateUserRequest(BaseModel):
    name: str
    email: str
    rating: int = 1200
    role: str = "user"


@api_router.post("/admin/users")
async def admin_create_user(req: CreateUserRequest, user: User = Depends(require_super_admin)):
    """Create a new user (super_admin only)."""
    existing = await db.users.find_one({"email": req.email}, {"_id": 0})
    if existing:
        raise HTTPException(status_code=409, detail="User with this email already exists")

    new_user = {
        "user_id": f"user_{uuid.uuid4().hex[:12]}",
        "email": req.email,
        "name": req.name,
        "rating": req.rating,
        "role": req.role,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.users.insert_one(new_user)
    new_user.pop("_id", None)
    return {"message": "User created", "user": new_user}


class ChangeRoleRequest(BaseModel):
    role: str  # "user", "admin", "super_admin"


@api_router.patch("/admin/users/{target_user_id}/role")
async def admin_change_role(target_user_id: str, req: ChangeRoleRequest, user: User = Depends(require_super_admin)):
    """Change a user's role (super_admin only)."""
    if req.role not in ("user", "admin", "super_admin"):
        raise HTTPException(status_code=400, detail="Invalid role")
    if target_user_id == user.user_id and req.role != "super_admin":
        raise HTTPException(status_code=400, detail="Cannot remove your own super_admin role")

    result = await db.users.update_one(
        {"user_id": target_user_id},
        {"$set": {"role": req.role}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    return {"message": f"Role updated to {req.role}"}


# --- Feedback Queue ---

class FlagMoveRequest(BaseModel):
    source: str  # "lab" or "coach"
    game_id: Optional[str] = None
    session_id: Optional[str] = None
    move_number: Optional[int] = None
    fen: str
    move_san: Optional[str] = None
    coaching_text: Optional[str] = None
    user_note: str
    # Developer-grade diagnostic fields
    severity: Optional[str] = None
    cp_loss: Optional[int] = None
    best_move: Optional[str] = None
    eval_before: Optional[float] = None
    eval_after: Optional[float] = None
    phase: Optional[str] = None
    component: Optional[str] = None
    concept_id: Optional[str] = None
    goal: Optional[str] = None
    consequence: Optional[str] = None
    better_approach: Optional[str] = None
    your_plan_now: Optional[str] = None
    # Extended debug fields
    transferable_learning: Optional[str] = None
    pv_after_played: Optional[str] = None
    candidate_moves: Optional[str] = None
    opening_name: Optional[str] = None


@api_router.post("/feedback/flag")
async def flag_move(req: FlagMoveRequest, user: User = Depends(get_current_user)):
    """User flags a move's coaching as incorrect or unhelpful."""
    feedback_doc = {
        "feedback_id": f"fb_{uuid.uuid4().hex[:12]}",
        "user_id": user.user_id,
        "user_name": user.name,
        "user_rating": None,
        "source": req.source,
        "game_id": req.game_id,
        "session_id": req.session_id,
        "move_number": req.move_number,
        "fen": req.fen,
        "move_san": req.move_san,
        "coaching_text": req.coaching_text,
        "user_note": req.user_note,
        "status": "pending",
        "admin_notes": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        # Developer diagnostic data
        "diagnostics": {
            "severity": req.severity,
            "cp_loss": req.cp_loss,
            "best_move": req.best_move,
            "eval_before": req.eval_before,
            "eval_after": req.eval_after,
            "phase": req.phase,
            "component": req.component,
            "concept_id": req.concept_id,
            "goal": req.goal,
            "consequence": req.consequence,
            "better_approach": req.better_approach,
            "your_plan_now": req.your_plan_now,
            "transferable_learning": req.transferable_learning,
            "pv_after_played": req.pv_after_played,
            "candidate_moves": req.candidate_moves,
            "opening_name": req.opening_name,
        }
    }

    # Try to get user rating
    user_doc = await db.users.find_one({"user_id": user.user_id}, {"_id": 0, "rating": 1})
    if user_doc:
        feedback_doc["user_rating"] = user_doc.get("rating")

    await db.move_feedback.insert_one(feedback_doc)
    feedback_doc.pop("_id", None)
    return {"message": "Feedback submitted", "feedback_id": feedback_doc["feedback_id"]}


@api_router.get("/admin/feedback")
async def admin_list_feedback(
    status: str = None,
    source: str = None,
    limit: int = 50,
    skip: int = 0,
    user: User = Depends(require_admin),
):
    """List feedback queue for admins."""
    query = {}
    if status:
        query["status"] = status
    if source:
        query["source"] = source

    feedback_list = []
    async for fb in db.move_feedback.find(query, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit):
        feedback_list.append(fb)

    total = await db.move_feedback.count_documents(query)
    pending = await db.move_feedback.count_documents({"status": "pending"})
    return {"feedback": feedback_list, "total": total, "pending": pending}


class UpdateFeedbackRequest(BaseModel):
    status: str  # "acknowledged", "valid", "dismissed"
    admin_notes: Optional[str] = None


@api_router.patch("/admin/feedback/{feedback_id}")
async def admin_update_feedback(feedback_id: str, req: UpdateFeedbackRequest, user: User = Depends(require_admin)):
    """Update feedback status (admin)."""
    if req.status not in ("pending", "acknowledged", "valid", "dismissed"):
        raise HTTPException(status_code=400, detail="Invalid status")

    update = {
        "$set": {
            "status": req.status,
            "reviewed_by": user.user_id,
            "reviewed_at": datetime.now(timezone.utc).isoformat(),
        }
    }
    if req.admin_notes:
        update["$set"]["admin_notes"] = req.admin_notes

    result = await db.move_feedback.update_one({"feedback_id": feedback_id}, update)
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Feedback not found")
    return {"message": f"Feedback marked as {req.status}"}


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


# NOTE: /journey/v2 moved to routes/journey.py

# ============================================
# ROLLING EVOLUTION ENDPOINTS (New Progress System)
# ============================================

@api_router.get("/progress/evolution")
async def get_progress_evolution(user: User = Depends(get_current_user)):
    """
    Get rolling window evolution data.
    
    Replaces baseline-based progress with continuous improvement tracking:
    - macro: 25 vs 25 games (monthly trend)
    - medium: 10 vs 10 games (bi-weekly trend)
    - micro: 5 vs 5 games (weekly trend)
    
    Returns:
    - Window metrics for each granularity
    - Delta (change) between windows
    - Trend assessment
    """
    from services.rolling_evolution_service import get_rolling_evolution
    return await get_rolling_evolution(db, user.user_id)


@api_router.get("/progress/openings")
async def get_opening_evolution(user: User = Depends(get_current_user)):
    """
    Get opening performance evolution.
    
    Shows:
    - Openings you're improving in
    - Openings not working for you
    - Recommendations
    
    Compares last 25 games vs previous 25 games.
    """
    from services.opening_evolution_service import get_user_opening_evolution
    return await get_user_opening_evolution(db, user.user_id, window_size=25)


# NOTE: /lab/{game_id} moved to routes/lab.py
# NOTE: /lab/{game_id}/mistake/{move_number}/context moved to routes/lab.py
# NOTE: MistakeExplanationRequest and /explain-mistake moved to routes/lab.py

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


# ============================================
# COACHING PUZZLE ENDPOINTS - Prescribed Training
# ============================================


# NOTE: /training/prescribed/{weakness}, /training/puzzle-attempt, /training/weekly-plan moved to routes/training.py

@api_router.get("/training/progress")
async def get_training_progress(user: User = Depends(get_current_user)):
    """
    Get user's training progress and improvement metrics.
    
    Shows:
    - Puzzles solved by weakness type
    - Solve rates over time
    - Improvement trends
    """
    # Get puzzle attempts
    attempts = await db.puzzle_attempts.find(
        {"user_id": user.user_id}
    ).sort("attempted_at", -1).limit(100).to_list(100)
    
    if not attempts:
        return {
            "has_data": False,
            "message": "No training data yet. Start solving puzzles!"
        }
    
    # Group by weakness pattern
    by_weakness = {}
    for attempt in attempts:
        pattern = attempt.get("weakness_pattern", "unknown")
        if pattern not in by_weakness:
            by_weakness[pattern] = {"total": 0, "solved": 0, "times": []}
        by_weakness[pattern]["total"] += 1
        if attempt.get("solved"):
            by_weakness[pattern]["solved"] += 1
        if attempt.get("time_taken"):
            by_weakness[pattern]["times"].append(attempt["time_taken"])
    
    # Calculate stats
    progress = {}
    for pattern, data in by_weakness.items():
        progress[pattern] = {
            "total_attempts": data["total"],
            "solved": data["solved"],
            "solve_rate": round(data["solved"] / data["total"] * 100, 1) if data["total"] > 0 else 0,
            "avg_time": round(sum(data["times"]) / len(data["times"]), 1) if data["times"] else None
        }
    
    return {
        "has_data": True,
        "progress_by_weakness": progress,
        "total_puzzles_solved": sum(d["solved"] for d in by_weakness.values()),
        "total_attempts": sum(d["total"] for d in by_weakness.values())
    }


# NOTE: /lab/{game_id}/deep-strategy moved to routes/lab.py

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


# NOTE: Additional notification endpoints moved to routes/notifications.py:
# - GET /notifications
# - POST /notifications/read
# - POST /notifications/{notification_id}/dismiss
# - GET /notifications/push-payload/{notification_id}

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
# NOTE: /games/{game_id}/reanalyze, /games/{game_id}/analysis-status moved to routes/games.py

@api_router.get("/analysis-queue")
async def get_analysis_queue_status(user: User = Depends(get_current_user)):
    """Get all games in the analysis queue for the current user"""
    queue_items = await db.analysis_queue.find(
        {"user_id": user.user_id, "status": {"$in": ["pending", "processing", "failed"]}},
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


# NOTE: Cognitive patterns API moved to routes/cognitive.py:
# - GET /cognitive/journey
# - GET /cognitive/patterns
# - GET /cognitive/weaknesses
# - GET /cognitive/training-priority
# - POST /cognitive/focus/activate
# - GET /cognitive/focus/status
# - GET /cognitive/focus/progress
# - GET /cognitive/tsi
# - GET /cognitive/trend
# - GET /cognitive/phase-insight
# - GET /cognitive/blunder-context


def _is_common_opening_move(move_san: str) -> bool:
    """
    Check if a move is a common mainline opening move.
    We don't want to say "This is part of the Italian Game" for h6!
    """
    # Common first moves (very mainline)
    mainline_moves = {
        # Pawn moves
        "e4", "d4", "c4", "Nf3", "g3", "e3", "d3", "c3",
        "e5", "d5", "c5", "c6", "e6", "d6",
        # Knight development
        "Nc3", "Nc6", "Nf6",
        # Bishop development
        "Bc4", "Bb5", "Be2", "Bd3", "Bg2", "Bc5", "Bb4", "Be7", "Bf5", "Bg4",
        # Castling
        "O-O", "O-O-O",
        # Queen moves (rare but valid)
        "Qd2",
    }
    
    # Edge pawn moves are NOT common opening theory
    if move_san in ["h3", "h4", "h6", "a3", "a4", "a6", "Rh3", "Ra3"]:
        return False
    
    # Check against common moves
    return move_san in mainline_moves



def _get_coach_move_explanation(move_san: str, fen_before: str, fen_after: str, move_number: int) -> str:
    """
    Generate POSITION-SPECIFIC explanation for coach's move.
    No more generic "develops pieces toward the center" for h6!
    """
    import chess
    
    try:
        board_before = chess.Board(fen_before)
        
        # Parse the move to understand what it does
        chess_move = board_before.parse_san(move_san)
        from_sq = chess_move.from_square
        to_sq = chess_move.to_square
        piece = board_before.piece_at(from_sq)
        
        if piece is None:
            return f"I played {move_san}."
        
        # Is it a pawn move?
        if piece.piece_type == chess.PAWN:
            # Pawn moves - be specific
            file = chess.square_file(to_sq)
            rank = chess.square_rank(to_sq)
            
            if file in [0, 7]:  # a or h file
                # Edge pawn - don't claim center development!
                if rank in [2, 5]:  # h3/a3 or h6/a6
                    return f"I played {move_san}. This prepares a potential retreat square for my bishop or prevents your pieces from using that square."
                else:
                    return f"I played {move_san}. A flank pawn move."
            elif file in [3, 4]:  # d or e file - center pawns
                return f"I played {move_san}. Fighting for the center."
            elif file in [2, 5]:  # c or f file
                return f"I played {move_san}. Supporting my central control."
            else:
                return f"I played {move_san}."
        
        # Is it castling?
        if board_before.is_castling(chess_move):
            if board_before.is_kingside_castling(chess_move):
                return f"I played {move_san}. Castling kingside - my king is now safe and my rook is ready for action."
            else:
                return f"I played {move_san}. Castling queenside - my king is tucked away and my rook eyes the center."
        
        # Knight moves
        if piece.piece_type == chess.KNIGHT:
            central_squares = [chess.D4, chess.D5, chess.E4, chess.E5, chess.C4, chess.C5, chess.F4, chess.F5]
            development_squares = [chess.F3, chess.C3, chess.F6, chess.C6]  # Natural development squares
            if to_sq in central_squares:
                return f"I played {move_san}. The knight is powerful in the center - it controls many squares from here."
            elif to_sq in development_squares:
                return f"I played {move_san}. Developing the knight to its natural square - knights should be developed early."
            else:
                return f"I played {move_san}. Repositioning my knight."
        
        # Bishop moves
        if piece.piece_type == chess.BISHOP:
            # Check if it's a fianchetto
            if to_sq in [chess.G2, chess.B2, chess.G7, chess.B7]:
                return f"I played {move_san}. Fianchettoing my bishop - it will be powerful on this diagonal."
            elif to_sq in [chess.C4, chess.F4, chess.C5, chess.F5]:
                return f"I played {move_san}. Active bishop pointing at your position."
            else:
                return f"I played {move_san}. Developing my bishop."
        
        # Queen moves
        if piece.piece_type == chess.QUEEN:
            if move_number <= 5:
                return f"I played {move_san}. An early queen move - can you punish it?"
            else:
                return f"I played {move_san}. The queen enters the game."
        
        # Rook moves
        if piece.piece_type == chess.ROOK:
            file = chess.square_file(to_sq)
            if file in [3, 4]:  # d or e file
                return f"I played {move_san}. Centralizing my rook on an open file."
            else:
                return f"I played {move_san}."
        
        # Default
        return f"I played {move_san}."
        
    except Exception as e:
        logger.warning(f"Error generating coach move explanation: {e}")
        return f"I played {move_san}."


def _get_teaching_explanation(move_san: str, fen_before: str, fen_after: str, move_number: int) -> str:
    """
    Generate TEACHING-FOCUSED explanation for coach's move.
    
    Key difference: We're not an opponent saying "I played X"
    We're a TEACHER explaining concepts: "Watch this...", "See how...", "Notice..."
    """
    import chess
    
    try:
        board_before = chess.Board(fen_before)
        
        # Parse the move
        chess_move = board_before.parse_san(move_san)
        from_sq = chess_move.from_square
        to_sq = chess_move.to_square
        piece = board_before.piece_at(from_sq)
        
        if piece is None:
            return f"See this {move_san}? Think about what it's preparing."
        
        piece_names = {
            chess.PAWN: "pawn",
            chess.KNIGHT: "knight", 
            chess.BISHOP: "bishop",
            chess.ROOK: "rook",
            chess.QUEEN: "queen",
            chess.KING: "king"
        }
        piece_name = piece_names.get(piece.piece_type, "piece")
        
        # Is it a pawn move?
        if piece.piece_type == chess.PAWN:
            file = chess.square_file(to_sq)
            rank = chess.square_rank(to_sq)
            
            if file in [3, 4]:  # d or e file - center pawns
                return f"Watch this {move_san} - fighting for the center. What squares does this pawn control now?"
            elif file in [2, 5]:  # c or f file
                return f"This {move_san} supports the center. Can you see how it helps control d4/e4?"
            elif rank in [2, 5]:  # h3/a3 or h6/a6
                return f"This {move_san} is a useful waiting move. What do you think it prevents?"
            else:
                return f"See this pawn move {move_san}? Every pawn move changes the structure permanently."
        
        # Is it castling?
        if board_before.is_castling(chess_move):
            if board_before.is_kingside_castling(chess_move):
                return "Castling kingside! The king is now safe, and the rook is ready to join the fight. Have you castled yet?"
            else:
                return "Castling queenside! This is aggressive - the rook immediately eyes the center. Be ready for action!"
        
        # Knight moves
        if piece.piece_type == chess.KNIGHT:
            central_squares = [chess.D4, chess.D5, chess.E4, chess.E5, chess.C4, chess.C5, chess.F4, chess.F5]
            development_squares = [chess.F3, chess.C3, chess.F6, chess.C6]
            
            if to_sq in central_squares:
                return f"Look at this knight on {chess.square_name(to_sq)}! From the center, a knight controls up to 8 squares. What does it threaten?"
            elif to_sq in development_squares:
                return f"Knight to {chess.square_name(to_sq)} - this is a natural developing move. Notice it's heading toward the center?"
            else:
                return f"Watch this knight maneuver to {chess.square_name(to_sq)}. Knights need good outposts - squares where they can't be chased away."
        
        # Bishop moves  
        if piece.piece_type == chess.BISHOP:
            if to_sq in [chess.G2, chess.B2, chess.G7, chess.B7]:
                return f"Fianchetto! The bishop on this diagonal is a long-range sniper. See how it controls the whole diagonal?"
            elif to_sq in [chess.C4, chess.F4, chess.C5, chess.F5]:
                return f"Active bishop! It's pointing right at your position. What targets can you see?"
            else:
                return f"Developing the bishop. Bishops are strongest on long, open diagonals."
        
        # Queen moves
        if piece.piece_type == chess.QUEEN:
            if move_number <= 5:
                return f"Early queen move! Usually risky - can you think of ways to attack it and gain time?"
            else:
                return f"The queen joins the attack. This is the most powerful piece - watch where it points!"
        
        # Rook moves
        if piece.piece_type == chess.ROOK:
            file = chess.square_file(to_sq)
            if file in [3, 4]:  # d or e file
                return f"Rook to the center! Rooks love open files. Is there an open file for your rook too?"
            else:
                return f"The rook is repositioning. Rooks are most powerful on open files and the 7th rank."
        
        # Default
        return f"See this {move_san}? Think about what it accomplishes. What's the idea?"
        
    except Exception as e:
        logger.warning(f"Error generating teaching explanation: {e}")
        return f"Watch this move - {move_san}. What do you think it's preparing?"



# =============================================================================
# PLAY WITH COACH API - P2 Feature
# =============================================================================

@api_router.post("/coach/play/start")
async def start_play_with_coach(
    request: Dict = Body(...),
    user: User = Depends(get_current_user)
):
    """
    Start a new Play With Coach session.
    
    Body:
    - user_color: "white" or "black" (default: "white")
    - time_control: Time format like "15+10" (default: "15+10" rapid)
    - starting_fen: Custom starting position (optional, for practice mode)
    - practice_mode: Whether this is practice mode (optional)
    - source_game_id: Game ID this practice is from (optional)
    
    Returns:
    - session_id: Unique session ID
    - session: Full session state
    - current_fen: Current board position
    - is_player_turn: Whether it's the player's turn
    - evaluation: Position evaluation for eval bar
    """
    from coach_play import start_coach_session
    from coach_play.coach_opponent import CoachOpponent
    
    user_color = request.get("user_color", "white")
    time_control = request.get("time_control", "15+10")
    starting_fen = request.get("starting_fen", None)
    practice_mode = request.get("practice_mode", False)
    source_game_id = request.get("source_game_id", None)
    
    # Validate user_color
    if user_color not in ["white", "black"]:
        raise HTTPException(status_code=400, detail="user_color must be 'white' or 'black'")
    
    try:
        session = await start_coach_session(
            db=db,
            user_id=user.user_id,
            user_color=user_color,
            time_control=time_control,
            starting_fen=starting_fen,
            practice_mode=practice_mode,
            source_game_id=source_game_id
        )
        
        # Get initial evaluation
        opponent = CoachOpponent(user_rating=session.user_rating)
        eval_score, mate_in = await opponent.get_evaluation(session.current_fen)
        
        # Determine whose turn it is based on FEN
        fen_parts = session.current_fen.split(' ')
        to_move = fen_parts[1] if len(fen_parts) > 1 else 'w'
        is_player_turn = (to_move == 'w' and user_color == 'white') or (to_move == 'b' and user_color == 'black')
        
        message = f"Game started! You are playing {user_color}."
        if practice_mode:
            message = f"Practice mode! Playing from a position in your game. You are {user_color}."
        
        # Get memory-aware welcome message from Coach Memory + Human Coach
        welcome_message = message
        coaching_context = {}
        opening_guidance = None
        
        try:
            # Get coaching context from memory
            from services.coach_memory import get_coaching_context, get_personalized_greeting
            from services.opening_mastery import suggest_opening_for_session
            
            coaching_context = await get_coaching_context(db, user.user_id)
            personalized_greeting = await get_personalized_greeting(db, user.user_id)
            
            # ALWAYS suggest an opening to learn at game start (proactive teaching)
            if not practice_mode:
                opening_guidance = await suggest_opening_for_session(
                    db, user.user_id, user_color, session.user_rating
                )
                
                if opening_guidance:
                    # Store the opening guidance in the session for teaching
                    await db.coach_sessions.update_one(
                        {"session_id": session.session_id},
                        {"$set": {
                            "opening_to_teach": opening_guidance["opening_key"],
                            "opening_teaching_moves": opening_guidance["full_moves"],
                            "opening_teaching_index": 0,
                            "opening_teaching_active": True,
                            "suggested_trap": opening_guidance.get("suggested_trap"),
                            "available_traps": opening_guidance.get("traps", [])
                        }}
                    )
                    
                    # Build the welcome message with opening guidance
                    welcome_message = f"{personalized_greeting}\n\n{opening_guidance['teaching_message']}"
                    
                    # Add first move guidance if it's user's turn
                    if is_player_turn:
                        first_move = opening_guidance["first_moves"][0] if opening_guidance["first_moves"] else None
                        if first_move:
                            welcome_message += f"\n\nYour first move: Play **{first_move}** to start."
                else:
                    welcome_message = personalized_greeting
                    if coaching_context.get("focus_suggestion"):
                        welcome_message += f" {coaching_context['focus_suggestion']}."
            else:
                # Practice mode - use standard personalized greeting
                welcome_message = personalized_greeting
                
                # Add focus suggestion if available
                if coaching_context.get("focus_suggestion"):
                    welcome_message += f" {coaching_context['focus_suggestion']}."
            
            # Surface any recurring patterns
            if coaching_context.get("watch_for"):
                top_weakness = coaching_context["watch_for"][0] if coaching_context["watch_for"] else None
                if top_weakness and top_weakness["count"] >= 3:
                    welcome_message += f"\n\nRemember: Watch out for {top_weakness['name']} - let's work on that today!"
            
            # Try Human Coach as fallback/enhancement
            try:
                from services.human_coach_service import create_human_coach
                coach = await create_human_coach(db, user.user_id, session.user_rating)
                human_welcome = await coach.get_welcome_message()
                
                # Use human coach message if it's more personal
                if len(human_welcome) > len(welcome_message):
                    welcome_message = human_welcome
                    
                if starting_fen:
                    memory_note = await coach.surface_relevant_memory(current_fen=starting_fen)
                    if memory_note:
                        welcome_message = f"{welcome_message}\n\n{memory_note}"
            except Exception as e:
                logger.warning(f"Human coach welcome failed: {e}")
                
        except Exception as e:
            logger.warning(f"Coach memory greeting failed: {e}")
            welcome_message = message
        
        return {
            "success": True,
            "session_id": session.session_id,
            "session": session.to_dict(),
            "current_fen": session.current_fen,
            "is_player_turn": is_player_turn,
            "message": welcome_message,
            "evaluation": {
                "score": eval_score,
                "mate_in": mate_in
            },
            "practice_mode": practice_mode
        }
    except Exception as e:
        logger.error(f"Error starting coach session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post("/coach/play/move")
async def make_coach_play_move(
    request: Dict = Body(...),
    user: User = Depends(get_current_user)
):
    """
    Make a move in the Play With Coach session.
    
    Flow:
    1. User's move is validated and recorded (FAST)
    2. Returns immediately - coach will respond async
    3. Background: Analyze → Generate message → Make coach move
    4. Frontend polls for messages and coach move
    
    Body:
    - session_id: Session ID
    - move: Move in SAN notation (e.g., "e4", "Nf3", "O-O")
    - time_spent: Time spent on this move in seconds (optional)
    
    Returns:
    - success: bool
    - user_move_recorded: True if move was valid
    - current_fen: Position after user's move
    - awaiting_coach: True (coach will respond async)
    """
    import asyncio
    from coach_play.coach_game_session import CoachGameSession, SessionStatus
    import chess
    from datetime import datetime, timezone
    
    session_id = request.get("session_id")
    move = request.get("move")
    time_spent = request.get("time_spent", 0.0)
    
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required")
    if not move:
        raise HTTPException(status_code=400, detail="move is required")
    
    # Get session
    session_doc = await db.coach_sessions.find_one({"session_id": session_id})
    if not session_doc:
        raise HTTPException(status_code=404, detail="Session not found")
    if session_doc.get("user_id") != user.user_id:
        raise HTTPException(status_code=403, detail="Not your session")
    
    # Store context - ensure FEN is never null
    fen_before = session_doc.get("current_fen")
    if not fen_before:
        # Fall back to fen_history or default
        fen_history = session_doc.get("fen_history", [])
        if fen_history:
            fen_before = fen_history[-1]
        else:
            fen_before = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
    user_rating = session_doc.get("user_rating", 1200)
    user_color = session_doc.get("user_color", "white")
    
    # Validate and record user's move ONLY (fast)
    try:
        board = chess.Board(fen_before)
        chess_move = board.parse_san(move)
        
        # Record user's move
        board.push(chess_move)
        fen_after_user = board.fen()
        
        move_history = session_doc.get("move_history", [])
        move_number = len([m for m in move_history if m.get("by") == "player"]) + 1
        
        # Add user's move to history
        move_history.append({
            "move": move,
            "uci": chess_move.uci(),
            "by": "player",
            "fen_before": fen_before,
            "fen_after": fen_after_user,
            "time_spent": time_spent,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
        action_revision = session_doc.get("action_revision", 0) + 1

        # Update session with user's move (coach move pending)
        await db.coach_sessions.update_one(
            {"session_id": session_id},
            {"$set": {
                "current_fen": fen_after_user,
                "move_history": move_history,
                "coach_move_pending": True,
                "action_revision": action_revision
            }}
        )
        
        # Check if game is over after user's move
        game_over = board.is_game_over()
        result = None
        if game_over:
            if board.is_checkmate():
                result = "win"  # User checkmated opponent
            elif board.is_stalemate() or board.is_insufficient_material():
                result = "draw"
        
        # Fire background task: analyze → message → coach move
        asyncio.create_task(
            _process_move_and_respond(
                session_id=session_id,
                user_move=move,
                fen_before=fen_before,
                fen_after_user=fen_after_user,
                user_rating=user_rating,
                user_color=user_color,
                move_number=move_number,
                game_over=game_over,
                expected_action_revision=action_revision
            )
        )
        
        return {
            "success": True,
            "user_move_recorded": True,
            "move": move,
            "current_fen": fen_after_user,
            "awaiting_coach": not game_over,
            "game_over": game_over,
            "result": result
        }
        
    except chess.InvalidMoveError:
        raise HTTPException(status_code=400, detail="Invalid move")
    except chess.AmbiguousMoveError:
        raise HTTPException(status_code=400, detail="Ambiguous move - please be more specific")
    except Exception as e:
        logger.error(f"Error processing move: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _classify_move(eval_before: float, eval_after: float, user_color: str) -> str:
    """Classify a move as blunder, mistake, inaccuracy, or good based on centipawn loss."""
    # Calculate centipawn loss from user's perspective
    if user_color == "white":
        cp_loss = (eval_before - eval_after) * 100  # Positive means user lost eval
    else:
        cp_loss = (eval_after - eval_before) * 100  # For black, eval going down is good
    
    if cp_loss >= 300:
        return "blunder"
    elif cp_loss >= 100:
        return "mistake"
    elif cp_loss >= 50:
        return "inaccuracy"
    else:
        return "good"


async def _process_move_and_respond(
    session_id: str,
    user_move: str,
    fen_before: str,
    fen_after_user: str,
    user_rating: int,
    user_color: str,
    move_number: int,
    game_over: bool,
    expected_action_revision: int,
):
    """
    Background task: Analyze user's move, generate message, then make coach's move.
    
    Order:
    1. Analyze user's move with Stockfish
    2. Generate coach message if triggered
    3. Make coach's responding move
    4. Store everything for frontend to poll
    """
    from coach_play.coach_commentary import get_quick_analysis, generate_coach_chat_message
    from coach_play.coaching_triggers import should_coach_speak
    from coach_play.coach_opponent import CoachOpponent
    from datetime import datetime, timezone
    import chess

    async def _is_current_revision() -> bool:
        current_doc = await db.coach_sessions.find_one(
            {"session_id": session_id},
            {"_id": 0, "action_revision": 1},
        )
        return bool(current_doc) and current_doc.get("action_revision", 0) == expected_action_revision
    
    try:
        # Step 1: Quick analysis of user's move
        analysis = await get_quick_analysis(
            fen_before=fen_before,
            move_san=user_move,
            fen_after=fen_after_user,
            user_color=user_color,
            move_number=move_number
        )
        
        # Step 2: Check if coach should comment
        trigger = should_coach_speak(
            user_rating=user_rating,
            move_san=user_move,
            eval_before=analysis["eval_before"],
            eval_after=analysis["eval_after"],
            is_best_move=analysis["is_best_move"],
            is_candidate=analysis["is_candidate"],
            best_move_san=analysis["best_move"],
            phase=analysis["phase"],
            move_number=move_number,
            opening_name=analysis.get("opening_name")
        )
        
        # === CRITICAL: Store evaluations in move_history for post-game analysis ===
        if not await _is_current_revision():
            logger.info(f"Skipping stale coach task for session {session_id}")
            return

        session_doc = await db.coach_sessions.find_one({"session_id": session_id})
        if session_doc:
            move_history = session_doc.get("move_history", [])
            # Find and update the last user move with evaluations
            for i in range(len(move_history) - 1, -1, -1):
                if move_history[i].get("move") == user_move and move_history[i].get("by") == "player":
                    move_history[i]["eval_before"] = analysis.get("eval_before", 0)
                    move_history[i]["eval_after"] = analysis.get("eval_after", 0)
                    move_history[i]["is_best_move"] = analysis.get("is_best_move", False)
                    move_history[i]["best_move"] = analysis.get("best_move")
                    move_history[i]["evaluation"] = _classify_move(
                        analysis.get("eval_before", 0),
                        analysis.get("eval_after", 0),
                        user_color
                    )
                    break
            
            # Store evaluations list for post-game analysis
            evaluations = session_doc.get("evaluations", [])
            evaluations.append({
                "move_number": move_number,
                "move": user_move,
                "by": "player",
                "score": analysis.get("eval_after", 0),
                "eval_before": analysis.get("eval_before", 0),
                "eval_after": analysis.get("eval_after", 0),
                "best_move": analysis.get("best_move")
            })
            
            await db.coach_sessions.update_one(
                {"session_id": session_id},
                {"$set": {
                    "move_history": move_history,
                    "evaluations": evaluations
                }}
            )
            
            # === OPENING TEACHING: Advance teaching index if correct move played ===
            if session_doc.get("opening_teaching_active"):
                teaching_moves = session_doc.get("opening_teaching_moves", [])
                teaching_index = session_doc.get("opening_teaching_index", 0)
                
                if teaching_index < len(teaching_moves):
                    expected_move = teaching_moves[teaching_index]
                    # Check if user played the expected opening move
                    if user_move.lower().replace("+", "").replace("#", "") == expected_move.lower().replace("+", "").replace("#", ""):
                        # Correct move! Advance the teaching index by 2 (user move + upcoming coach move)
                        new_index = teaching_index + 2
                        
                        if new_index >= len(teaching_moves):
                            # Opening identifying sequence complete
                            # But DON'T say "completed" if we have deep variations to teach
                            opening_obj = None
                            try:
                                from coach_engine.opening_plans import get_opening_by_moves
                                session_d = await db.coach_sessions.find_one({"session_id": session_id})
                                mh = session_d.get("move_history", []) if session_d else []
                                all_m = [m.get("move", "") for m in mh if m.get("move")]
                                opening_obj = get_opening_by_moves(all_m)
                            except Exception:
                                pass
                            
                            has_deep_variations = opening_obj and getattr(opening_obj, 'variations', None)
                            
                            await db.coach_sessions.update_one(
                                {"session_id": session_id},
                                {"$set": {
                                    "opening_teaching_active": False,
                                    "opening_teaching_complete": True,
                                    "opening_teaching_index": new_index
                                }}
                            )
                            
                            # Only show completion if no deep variations exist
                            if not has_deep_variations:
                                await db.coach_messages.insert_one({
                                    "session_id": session_id,
                                    "type": "coach",
                                    "message": f"Excellent! You've completed the opening! Now let's play freely. Remember the key ideas we learned!",
                                    "trigger": "opening_complete",
                                    "created_at": datetime.now(timezone.utc),
                                    "read": False
                                })
                        else:
                            await db.coach_sessions.update_one(
                                {"session_id": session_id},
                                {"$set": {"opening_teaching_index": new_index}}
                            )
        
        # Step 3: MOVE-BY-MOVE COACHING for opening phase
        # During opening, ALWAYS generate a commentary message (not trigger-dependent)
        opening_commentary_sent = False
        if move_number <= 15:
            try:
                if not await _is_current_revision():
                    logger.info(f"Skipping stale opening commentary for session {session_id}")
                    return
                from services.move_by_move_coach import generate_move_commentary
                from coach_engine.opening_plans import build_opening_coaching_context
                
                session_doc = await db.coach_sessions.find_one({"session_id": session_id})
                move_history = session_doc.get("move_history", []) if session_doc else []
                all_moves_san = [m.get("move", "") for m in move_history if m.get("move")]
                
                opening_plan = build_opening_coaching_context(all_moves_san)
                
                commentary = generate_move_commentary(
                    fen_before=fen_before,
                    fen_after=fen_after_user,
                    move_san=user_move,
                    move_by="user",
                    all_moves=all_moves_san,
                    user_color=user_color,
                    user_rating=user_rating,
                    opening_plan=opening_plan,
                    eval_before=analysis.get("eval_before", 0),
                    eval_after=analysis.get("eval_after", 0),
                    is_best_move=analysis.get("is_best_move", True),
                    best_move_san=analysis.get("best_move", ""),
                )
                
                if commentary.message:
                    msg_doc = {
                        "session_id": session_id,
                        "type": "coach",
                        "message": commentary.message,
                        "trigger": "opening_teaching",
                        "move": user_move,
                        "move_number": move_number,
                        "created_at": datetime.now(timezone.utc),
                        "read": False,
                        "move_quality": commentary.move_quality,
                        "teaching_type": commentary.teaching_type,
                    }
                    if commentary.question:
                        msg_doc["question"] = {"prompt": commentary.question}
                    if commentary.trap_warning:
                        msg_doc["trap_warning"] = commentary.trap_warning
                    if commentary.next_hint:
                        msg_doc["next_hint"] = commentary.next_hint
                    if commentary.pattern_note:
                        msg_doc["pattern_note"] = commentary.pattern_note
                    
                    await db.coach_messages.insert_one(msg_doc)
                    opening_commentary_sent = True
            except Exception as e:
                logger.warning(f"Move-by-move coaching failed: {e}")
        
        # Step 4: Generate and store message if triggered (skip if opening commentary already sent)
        if trigger.should_speak and not opening_commentary_sent:
            if not await _is_current_revision():
                logger.info(f"Skipping stale triggered coaching for session {session_id}")
                return
            # First, try to get wisdom-based explanation
            from coach_play.teaching_integration import enhance_coaching_message
            
            wisdom_enhanced = None
            try:
                # Get session to find user_id
                session_doc = await db.coach_sessions.find_one({"session_id": session_id})
                user_id = session_doc.get("user_id", "unknown") if session_doc else "unknown"
                
                # Parse user move to UCI
                import chess
                board = chess.Board(fen_before)
                chess_move = board.parse_san(user_move)
                
                wisdom_enhanced = enhance_coaching_message(
                    fen=fen_before,
                    user_move_uci=chess_move.uci(),
                    user_color=user_color,
                    eval_before=analysis["eval_before"],
                    eval_after=analysis["eval_after"],
                    best_move_uci=analysis.get("best_move_uci", ""),
                    best_move_eval=analysis.get("best_move_eval", analysis["eval_before"]),
                    move_number=move_number,
                    user_id=user_id,
                    user_rating=user_rating,
                )
            except Exception as e:
                logger.warning(f"Wisdom enhancement failed: {e}")
            
            # Use wisdom-based message if available, otherwise fall back to LLM
            if wisdom_enhanced and wisdom_enhanced.get("rule_id"):
                # Wisdom-based coaching message
                coach_message = wisdom_enhanced.get("chat_message", "")
                rule_id = wisdom_enhanced.get("rule_id")
                memorable_rule = wisdom_enhanced.get("memorable_rule", "")
                highlights = wisdom_enhanced.get("highlights", {})
                question = wisdom_enhanced.get("question")
                teaching_level = wisdom_enhanced.get("level", "teach")
                
                await db.coach_messages.insert_one({
                    "session_id": session_id,
                    "type": "coach",
                    "message": coach_message,
                    "trigger": trigger.trigger_type.value,
                    "move": user_move,
                    "move_number": move_number,
                    "created_at": datetime.now(timezone.utc),
                    "read": False,
                    # Wisdom-based enhancements
                    "rule_id": rule_id,
                    "memorable_rule": memorable_rule,
                    "highlights": highlights,
                    "question": question,
                    "teaching_level": teaching_level,
                    "is_wisdom_based": True,
                })
            else:
                # Use SOCRATIC ENGINE for human-like coaching
                # Never give the answer first - guide them to discover
                from services.human_coach_service import get_socratic_response
                
                eval_before = analysis.get("eval_before", 0)
                eval_after = analysis.get("eval_after", 0)
                best_move = analysis.get("best_move", "")
                delta = int((eval_after - eval_before) * 100)
                
                # Determine position type for Socratic engine
                if abs(delta) >= 200:
                    position_type = "blunder"
                elif abs(delta) >= 100:
                    position_type = "mistake"
                elif analysis.get("missed_tactic"):
                    position_type = "missed_tactic"
                else:
                    position_type = "strategic"
                
                # Get Socratic response with emotional adaptation
                try:
                    # Get session for emotional context
                    session_doc = await db.coach_sessions.find_one({"session_id": session_id})
                    
                    # Build emotional context from session
                    emotional_context = None
                    if session_doc:
                        move_history = session_doc.get("move_history", [])
                        blunders_count = sum(1 for m in move_history if m.get("classification") == "BLUNDER")
                        emotional_context = {
                            "blunders_this_game": blunders_count
                        }
                    
                    socratic_response = await get_socratic_response(
                        db=db,
                        user_id=session_doc.get("user_id") if session_doc else "unknown",
                        user_rating=user_rating,
                        fen=fen_before,
                        move_played=user_move,
                        best_move=best_move,
                        eval_loss=abs(delta),
                        emotional_context=emotional_context
                    )
                    
                    coach_message = socratic_response.get("message", "")
                    
                    # Store Socratic dialogue context for continuing the conversation
                    dialogue_context = {
                        "dialogue_id": socratic_response.get("dialogue_id"),
                        "fen": fen_before,
                        "move_played": user_move,
                        "best_move": best_move,
                        "hints_given": 0
                    }
                    
                    await db.coach_messages.insert_one({
                        "session_id": session_id,
                        "type": "coach",
                        "message": coach_message,
                        "trigger": trigger.trigger_type.value,
                        "move": user_move,
                        "move_number": move_number,
                        "created_at": datetime.now(timezone.utc),
                        "read": False,
                        "is_socratic": True,
                        "socratic_dialogue": dialogue_context,
                        "emotional_state": socratic_response.get("emotional_state"),
                        "expects_response": socratic_response.get("expects_response", True),
                        "pattern_connection": socratic_response.get("pattern_connection"),
                        # MEMORY INSIGHTS - makes coach feel human
                        "memory_insight": socratic_response.get("memory_insight"),
                        "focus_note": socratic_response.get("focus_note"),
                        "games_together": socratic_response.get("games_together", 0),
                    })
                    
                except Exception as e:
                    logger.warning(f"Socratic engine failed, using fallback: {e}")
                    # Fallback to simple Socratic-style message
                    if abs(delta) >= 200:
                        coach_message = f"Interesting choice with {user_move}. What were you trying to achieve?"
                    elif abs(delta) >= 100:
                        coach_message = f"Let me ask about {user_move} - what was your thinking there?"
                    else:
                        coach_message = f"Good thinking with {user_move}! What's your plan from here?"
                    
                    await db.coach_messages.insert_one({
                        "session_id": session_id,
                        "type": "coach",
                        "message": coach_message,
                        "trigger": trigger.trigger_type.value,
                        "move": user_move,
                        "move_number": move_number,
                        "created_at": datetime.now(timezone.utc),
                        "read": False,
                        "is_wisdom_based": False,
                        "is_factual_fallback": True,
                    })
        
        # Step 3.5: Proactive teaching for GOOD moves and consequence detection
        # Even if trigger didn't fire, we can praise good moves or warn about consequences
        if not trigger.should_speak:
            try:
                if not await _is_current_revision():
                    logger.info(f"Skipping stale proactive teaching for session {session_id}")
                    return
                from coach_engine.question_system import (
                    generate_move_praise_question,
                    detect_long_term_consequences
                )
                import chess
                
                board = chess.Board(fen_after_user)
                
                # Check if it was a best/candidate move - praise it!
                if analysis.get("is_best_move") and move_number >= 4:
                    question = generate_move_praise_question(user_move, is_best=True)
                    await db.coach_messages.insert_one({
                        "session_id": session_id,
                        "type": "coach",
                        "message": question.text,
                        "trigger": "praise",
                        "move": user_move,
                        "move_number": move_number,
                        "created_at": datetime.now(timezone.utc),
                        "read": False,
                        "is_praise": True,
                        "question": question.to_dict() if question.options else None,
                    })
                
                # Check for long-term consequences (pawn structure, castling rights)
                elif move_number >= 6:
                    board_before = chess.Board(fen_before)
                    chess_move = board_before.parse_san(user_move)
                    board_before.push(chess_move)
                    
                    user_chess_color = chess.WHITE if user_color == "white" else chess.BLACK
                    consequence = detect_long_term_consequences(
                        board_before, user_chess_color, chess_move
                    )
                    
                    if consequence:
                        await db.coach_messages.insert_one({
                            "session_id": session_id,
                            "type": "coach",
                            "message": consequence,
                            "trigger": "consequence",
                            "move": user_move,
                            "move_number": move_number,
                            "created_at": datetime.now(timezone.utc),
                            "read": False,
                            "is_consequence_warning": True,
                        })
            except Exception as e:
                logger.warning(f"Proactive teaching failed: {e}")
        
        # Step 4: Make coach's responding move (if game not over)
        if not game_over:
            if not await _is_current_revision():
                logger.info(f"Skipping stale coach reply for session {session_id}")
                return
            session_doc = await db.coach_sessions.find_one({"session_id": session_id})
            if session_doc:
                board = chess.Board(fen_after_user)
                
                # === NEW: Check for opening and offer interactive teaching ===
                move_history = session_doc.get("move_history", [])
                user_id = session_doc.get("user_id", "unknown")
                
                # Only check in opening phase (first 12 moves per side)
                if len(move_history) <= 24 and not session_doc.get("opening_offer_shown"):
                    try:
                        from services.opening_teaching_integration import check_opening_and_offer_teaching
                        
                        opening_offer = await check_opening_and_offer_teaching(
                            db=db,
                            session_id=session_id,
                            move_history=move_history,
                            user_color=user_color,
                            user_id=user_id
                        )
                        
                        if opening_offer:
                            # Store the teaching offer as a coach message
                            await db.coach_messages.insert_one({
                                "session_id": session_id,
                                "type": "opening_teaching_offer",
                                "message": opening_offer["message"],
                                "trigger": "opening_detected",
                                "opening_name": opening_offer["opening_name"],
                                "opening_key": opening_offer["opening_key"],
                                "options": opening_offer["options"],
                                "trap_name": opening_offer.get("trap_name"),
                                "created_at": datetime.now(timezone.utc),
                                "read": False,
                            })
                            logger.info(f"Opening detected: {opening_offer['opening_name']} - offered teaching")
                    except Exception as e:
                        logger.warning(f"Opening detection failed: {e}")
                
                # === ENDGAME DETECTION ===
                # Check if we've entered an endgame and offer teaching
                if len(move_history) > 24 and not session_doc.get("endgame_offer_shown"):
                    try:
                        from services.endgame_teaching import check_endgame_and_offer_teaching
                        
                        endgame_offer = await check_endgame_and_offer_teaching(
                            db=db,
                            session_id=session_id,
                            current_fen=fen_after_user,
                            user_id=user_id,
                            user_color=user_color
                        )
                        
                        if endgame_offer:
                            await db.coach_messages.insert_one({
                                "session_id": session_id,
                                "type": "endgame_teaching_offer",
                                "message": endgame_offer["message"],
                                "trigger": "endgame_detected",
                                "endgame_type": endgame_offer["endgame_type"],
                                "lesson_name": endgame_offer["lesson_name"],
                                "key_concepts": endgame_offer["key_concepts"],
                                "options": endgame_offer["options"],
                                "created_at": datetime.now(timezone.utc),
                                "read": False,
                            })
                            logger.info(f"Endgame detected: {endgame_offer['lesson_name']} - offered teaching")
                    except Exception as e:
                        logger.warning(f"Endgame detection failed: {e}")
                
                # Get student weaknesses from their profile (if available)
                student_weaknesses = session_doc.get("student_weaknesses", [])
                teaching_focus = session_doc.get("teaching_focus", None)
                
                # Get move history for opening guidance
                move_history = session_doc.get("move_history", [])
                move_history_san = [m.get("move") for m in move_history if m.get("move")]
                
                # Get user's color (coach plays opposite)
                user_color = session_doc.get("user_color", "white")
                
                # Use Pedagogical Opponent with Teaching Move Selector
                from coach_play.coach_opponent import PedagogicalOpponent
                opponent = PedagogicalOpponent(
                    user_rating=user_rating,
                    teaching_mode="balanced",
                    student_weaknesses=student_weaknesses,
                    teaching_focus=teaching_focus,
                    move_history=move_history_san,  # Pass move history for opening guidance
                    user_color=user_color  # Pass user's color for correct opening guidance
                )
                coach_move = await opponent.get_move(fen_after_user)
                teaching_context = opponent.get_teaching_context()
                
                if coach_move:
                    chess_move = board.parse_san(coach_move)
                    board.push(chess_move)
                    fen_after_coach = board.fen()
                    
                    # CRITICAL: Fetch FRESH move_history that includes evaluations we just stored
                    if not await _is_current_revision():
                        logger.info(f"Skipping stale coach move application for session {session_id}")
                        return
                    fresh_session = await db.coach_sessions.find_one({"session_id": session_id})
                    move_history = fresh_session.get("move_history", []) if fresh_session else []
                    move_history.append({
                        "move": coach_move,
                        "uci": chess_move.uci(),
                        "by": "coach",
                        "fen_before": fen_after_user,
                        "fen_after": fen_after_coach,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "teaching_goal": teaching_context.get("teaching_goal"),
                        "is_best_move": teaching_context.get("is_best_move", True)
                    })
                    
                    # Check if game over after coach move
                    coach_game_over = board.is_game_over()
                    coach_result = None
                    status = "active"
                    if coach_game_over:
                        status = "completed"
                        if board.is_checkmate():
                            coach_result = "loss"  # Coach checkmated user
                        else:
                            coach_result = "draw"
                    
                    # Get new evaluation
                    eval_score, mate_in = await opponent.get_evaluation(fen_after_coach)
                    
                    # === OPENING DETECTION AFTER COACH'S MOVE ===
                    # This enables immediate detection for openings where the coach makes the defining move
                    # (e.g., 1.e4 for French Defense: coach plays e4, user will play e6)
                    if not coach_game_over and len(move_history) <= 24 and not session_doc.get("opening_offer_shown"):
                        try:
                            from services.opening_teaching_integration import check_opening_and_offer_teaching
                            
                            # Get updated move history (including coach's move)
                            all_moves_for_detection = [m.get("move", "") for m in move_history]
                            
                            opening_offer = await check_opening_and_offer_teaching(
                                db=db,
                                session_id=session_id,
                                move_history=all_moves_for_detection,
                                user_color=user_color,
                                user_id=session_doc.get("user_id", "unknown")
                            )
                            
                            if opening_offer:
                                # Store the teaching offer as a coach message
                                await db.coach_messages.insert_one({
                                    "session_id": session_id,
                                    "type": "opening_teaching_offer",
                                    "message": opening_offer["message"],
                                    "trigger": "opening_detected",
                                    "opening_name": opening_offer["opening_name"],
                                    "opening_key": opening_offer["opening_key"],
                                    "options": opening_offer["options"],
                                    "trap_name": opening_offer.get("trap_name"),
                                    "created_at": datetime.now(timezone.utc),
                                    "read": False,
                                })
                                logger.info(f"Opening detected after coach move: {opening_offer['opening_name']}")
                                
                                # Mark as shown so we don't show again
                                await db.coach_sessions.update_one(
                                    {"session_id": session_id},
                                    {"$set": {"opening_offer_shown": True}}
                                )
                        except Exception as e:
                            logger.warning(f"Opening detection after coach move failed: {e}")
                    
                    # === TEACHING: Generate coach's teaching message ===
                    coach_move_number = len(move_history) // 2
                    if not coach_game_over:
                        try:
                            from services.move_by_move_coach import generate_move_commentary
                            from coach_engine.opening_plans import build_opening_coaching_context
                            
                            all_moves = [m.get("move", "") for m in move_history]
                            opening_plan = build_opening_coaching_context(all_moves)
                            
                            # Use move-by-move coach for opening moves
                            if coach_move_number <= 15:
                                commentary = generate_move_commentary(
                                    fen_before=fen_after_user,
                                    fen_after=fen_after_coach,
                                    move_san=coach_move,
                                    move_by="coach",
                                    all_moves=all_moves,
                                    user_color=user_color,
                                    user_rating=user_rating,
                                    opening_plan=opening_plan,
                                )
                                
                                msg_text = commentary.message
                                trigger_type = "opening_teaching"
                                
                                if msg_text:
                                    msg_doc = {
                                        "session_id": session_id,
                                        "type": "coach",
                                        "message": msg_text,
                                        "trigger": trigger_type,
                                        "move": coach_move,
                                        "move_number": coach_move_number,
                                        "is_coach_move": True,
                                        "created_at": datetime.now(timezone.utc),
                                        "read": False,
                                        "teaching_type": commentary.teaching_type,
                                    }
                                    if commentary.question:
                                        msg_doc["question"] = {"prompt": commentary.question}
                                    if commentary.trap_warning:
                                        msg_doc["trap_warning"] = commentary.trap_warning
                                    if commentary.next_hint:
                                        msg_doc["next_hint"] = commentary.next_hint
                                    
                                    # Include opening info
                                    if opening_plan:
                                        msg_doc["opening_key"] = opening_plan.get("key")
                                        msg_doc["opening_name"] = opening_plan.get("name")
                                    
                                    await db.coach_messages.insert_one(msg_doc)
                            else:
                                # Fall back to Active Teaching Engine for middlegame+
                                from services.active_teaching_engine import generate_teaching_feedback
                                
                                feedback = generate_teaching_feedback(
                                    fen=fen_after_coach,
                                    last_move_uci=chess_move.uci(),
                                    student_rating=user_rating,
                                    phase="after_coach_move",
                                    student_color=user_color,
                                    move_context={
                                        "teaching_goal": teaching_context.get("teaching_goal", "natural_play"),
                                        "why_instructive": teaching_context.get("why_instructive", ""),
                                        "concept_taught": teaching_context.get("concept_taught", ""),
                                        "student_challenge": teaching_context.get("student_challenge", ""),
                                        "move_san": coach_move,
                                        "game_phase": teaching_context.get("teaching_content", {}).get("game_phase", "middlegame")
                                    }
                                )
                                
                                if not feedback.get("error") and feedback.get("message"):
                                    await db.coach_messages.insert_one({
                                        "session_id": session_id,
                                        "type": "coach",
                                        "message": feedback["message"],
                                        "trigger": "teaching",
                                        "move": coach_move,
                                        "move_number": coach_move_number,
                                        "is_coach_move": True,
                                        "created_at": datetime.now(timezone.utc),
                                        "read": False,
                                        "concept": feedback.get("concept"),
                                        "hints": feedback.get("hints", []),
                                    })
                        except Exception as e:
                            logger.warning(f"Opening teaching generation failed: {e}")
                    
                    # === NEW: INTELLIGENT POSITION COACHING ===
                    # Offer position-based coaching when not in opening/endgame teaching
                    # This connects all our analysis systems to provide contextual suggestions
                    if not coach_game_over:
                        try:
                            # Only offer if no opening/endgame teaching was triggered this session
                            should_offer_position_coaching = (
                                not session_doc.get("opening_teaching_active") and
                                not session_doc.get("position_coaching_offered") and
                                len(move_history) >= 12  # After ~6 moves per side
                            )
                            
                            if should_offer_position_coaching:
                                from services.intelligent_position_coach import analyze_position_and_suggest
                                
                                # Analyze the current position
                                position_coaching = await analyze_position_and_suggest(
                                    board=board,  # Board after coach's move
                                    move_history=move_history_san + [coach_move],
                                    user_color=user_color,
                                    user_id=session_doc.get("user_id", "unknown"),
                                    db=db
                                )
                                
                                if position_coaching:
                                    # Store the position coaching offer as a message
                                    await db.coach_messages.insert_one({
                                        "session_id": session_id,
                                        "type": "position_coaching",
                                        "message": position_coaching.get("main_idea", ""),
                                        "trigger": "position_analysis",
                                        "structure_name": position_coaching.get("structure_name"),
                                        "structure_type": position_coaching.get("structure_type"),
                                        "game_phase": position_coaching.get("game_phase"),
                                        "key_characteristics": position_coaching.get("key_characteristics", []),
                                        "strategic_plans": position_coaching.get("strategic_plans", []),
                                        "tactical_features": position_coaching.get("tactical_features", {}),
                                        "tactical_insights": position_coaching.get("tactical_insights", []),
                                        "teaching_points": position_coaching.get("teaching_points", []),
                                        "critical_squares": position_coaching.get("critical_squares", []),
                                        "options": position_coaching.get("options", []),
                                        "created_at": datetime.now(timezone.utc),
                                        "read": False,
                                    })
                                    
                                    # Mark that we've offered position coaching
                                    await db.coach_sessions.update_one(
                                        {"session_id": session_id},
                                        {"$set": {"position_coaching_offered": True}}
                                    )
                                    
                                    logger.info(f"Position coaching offered: {position_coaching.get('structure_name')} ({position_coaching.get('game_phase')})")
                        except Exception as e:
                            logger.warning(f"Intelligent position coaching failed: {e}")
                    
                    # Update session
                    await db.coach_sessions.update_one(
                        {"session_id": session_id},
                        {"$set": {
                            "current_fen": fen_after_coach,
                            "move_history": move_history,
                            "coach_move_pending": False,
                            "last_coach_move": {
                                "move": coach_move,
                                "uci": chess_move.uci(),
                                "timestamp": datetime.now(timezone.utc).isoformat()
                            },
                            "status": status,
                            "result": coach_result,
                            "evaluation": {"score": eval_score, "mate_in": mate_in}
                        }}
                    )
                else:
                    # No valid move (shouldn't happen)
                    await db.coach_sessions.update_one(
                        {"session_id": session_id},
                        {"$set": {"coach_move_pending": False}}
                    )
        else:
            # Game was over after user's move
            await db.coach_sessions.update_one(
                {"session_id": session_id},
                {"$set": {"coach_move_pending": False}}
            )
            
            # === UPDATE COACH MEMORY AFTER GAME ===
            try:
                from services.coach_memory import update_memory_after_game
                from phase_theory_service import detect_game_phase
                
                session_doc = await db.coach_sessions.find_one({"session_id": session_id})
                if session_doc:
                    # Determine result from user's perspective
                    result = "draw"
                    loss_phase = None
                    if game_over:
                        import chess
                        board = chess.Board(fen_after_user)
                        if board.is_checkmate():
                            # User delivered checkmate
                            result = "win"
                        else:
                            # User lost - determine phase
                            result = "loss"
                            # Get move count to determine phase
                            move_count = len(session_doc.get("move_history", []))
                            move_number = (move_count // 2) + 1
                            loss_phase = detect_game_phase(board, move_number)
                            logger.info(f"Game lost in {loss_phase} phase (move {move_number})")
                    
                    await update_memory_after_game(
                        db=db,
                        user_id=session_doc.get("user_id"),
                        game_result=result,
                        accuracy=0,  # Would need move-by-move analysis
                        blunders=0,
                        mistakes=0,
                        habits_violated=[],
                        habits_improved=[],
                        opening_played=session_doc.get("detected_opening"),
                        endgame_reached=session_doc.get("endgame_offer_shown", False),
                        performance_rating=session_doc.get("user_rating", 1200),
                        loss_phase=loss_phase
                    )
                    logger.info(f"Updated coach memory after game {session_id}")
            except Exception as e:
                logger.warning(f"Failed to update coach memory: {e}")
            
    except Exception as e:
        logger.error(f"Background move processing failed: {e}")
        # Mark as no longer pending even on error
        await db.coach_sessions.update_one(
            {"session_id": session_id},
            {"$set": {"coach_move_pending": False}}
        )


@api_router.get("/coach/play/messages/{session_id}")
async def get_coach_messages(
    session_id: str,
    user: User = Depends(get_current_user)
):
    """
    Poll for new coach messages.
    Frontend calls this periodically to get coach commentary.
    
    Returns unread messages and marks them as read.
    """
    from datetime import datetime, timezone
    
    # Verify session belongs to user
    session_doc = await db.coach_sessions.find_one({"session_id": session_id})
    if not session_doc:
        raise HTTPException(status_code=404, detail="Session not found")
    if session_doc.get("user_id") != user.user_id:
        raise HTTPException(status_code=403, detail="Not your session")
    
    # Get unread messages
    cursor = db.coach_messages.find({
        "session_id": session_id,
        "read": False
    }).sort("created_at", 1)
    
    messages = []
    message_ids = []
    
    async for msg in cursor:
        msg_data = {
            "id": str(msg["_id"]),  # Include message ID for feedback!
            "type": msg.get("type", "coach"),
            "message": msg.get("message", ""),
            "trigger": msg.get("trigger"),
            "move": msg.get("move"),
            "move_number": msg.get("move_number"),
            "timestamp": msg.get("created_at").isoformat() if msg.get("created_at") else None
        }
        
        # Include opening teaching offer fields
        if msg.get("type") == "opening_teaching_offer":
            msg_data["opening_name"] = msg.get("opening_name")
            msg_data["opening_key"] = msg.get("opening_key")
            msg_data["options"] = msg.get("options")
            msg_data["trap_name"] = msg.get("trap_name")
        
        # Include endgame teaching offer fields
        if msg.get("type") == "endgame_teaching_offer":
            msg_data["endgame_type"] = msg.get("endgame_type")
            msg_data["lesson_name"] = msg.get("lesson_name")
            msg_data["key_concepts"] = msg.get("key_concepts")
            msg_data["options"] = msg.get("options")
        
        # Include position coaching fields
        if msg.get("type") == "position_coaching":
            msg_data["structure_name"] = msg.get("structure_name")
            msg_data["structure_type"] = msg.get("structure_type")
            msg_data["game_phase"] = msg.get("game_phase")
            msg_data["key_characteristics"] = msg.get("key_characteristics")
            msg_data["strategic_plans"] = msg.get("strategic_plans")
            msg_data["tactical_features"] = msg.get("tactical_features")
            msg_data["tactical_insights"] = msg.get("tactical_insights")
            msg_data["teaching_points"] = msg.get("teaching_points")
            msg_data["critical_squares"] = msg.get("critical_squares")
            msg_data["options"] = msg.get("options")
        
        messages.append(msg_data)
        message_ids.append(msg["_id"])
    
    # Mark as read
    if message_ids:
        await db.coach_messages.update_many(
            {"_id": {"$in": message_ids}},
            {"$set": {"read": True}}
        )
    
    return {
        "success": True,
        "messages": messages,
        "count": len(messages)
    }


@api_router.post("/coach/play/undo")
async def undo_coach_play_move(
    request: Dict = Body(...),
    user: User = Depends(get_current_user)
):
    """Undo the user's last move in Play with Coach.

    Normal play: rewinds the user's move and any derived coach reply.
    Teaching mode: rewinds the user's last lesson move and any auto-played reply.
    """
    from datetime import datetime
    import chess
    from coach_play.coach_game_session import get_session_state

    session_id = request.get("session_id")
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required")

    session_doc = await db.coach_sessions.find_one({"session_id": session_id})
    if not session_doc:
        raise HTTPException(status_code=404, detail="Session not found")
    if session_doc.get("user_id") != user.user_id:
        raise HTTPException(status_code=403, detail="Not your session")
    if session_doc.get("status") != "active":
        raise HTTPException(status_code=400, detail="Undo is only available while the game is active")

    teaching_data = session_doc.get("teaching_data") or {}
    teaching_moves = teaching_data.get("trap_moves") or teaching_data.get("main_line_moves") or []
    teaching_is_active = bool(
        session_doc.get("teaching_mode")
        and teaching_moves
        and teaching_data.get("teaching_fen")
        and session_doc.get("current_fen") == teaching_data.get("teaching_fen")
    )

    if session_doc.get("teaching_mode") and teaching_is_active:
        from services.opening_teaching_integration import undo_teaching_move

        result = await undo_teaching_move(db, session_id)
        if not result.get("error"):
            return result

        logger.warning(
            f"Teaching undo failed for session {session_id}; falling back to normal undo: {result.get('error')}"
        )
        await db.coach_sessions.update_one(
            {"session_id": session_id},
            {"$set": {"teaching_mode": None, "teaching_data": {}, "teaching_opening": None}},
        )
        session_doc["teaching_mode"] = None
        session_doc["teaching_data"] = {}

    if session_doc.get("teaching_mode") and not teaching_is_active:
        await db.coach_sessions.update_one(
            {"session_id": session_id},
            {"$set": {"teaching_mode": None, "teaching_data": {}, "teaching_opening": None}},
        )
        session_doc["teaching_mode"] = None
        session_doc["teaching_data"] = {}

    move_history = session_doc.get("move_history", [])
    last_player_index = next(
        (index for index in range(len(move_history) - 1, -1, -1) if move_history[index].get("by") == "player"),
        None,
    )
    if last_player_index is None:
        raise HTTPException(status_code=400, detail="No player move available to undo")

    last_player_move = move_history[last_player_index]
    restored_fen = last_player_move.get("fen_before") or "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
    truncated_history = move_history[:last_player_index]
    previous_coach_move = next(
        (move for move in reversed(truncated_history) if move.get("by") == "coach"),
        None,
    )
    previous_player_count = sum(1 for move in truncated_history if move.get("by") == "player")

    updated_session_fields = {
        "current_fen": restored_fen,
        "move_history": truncated_history,
        "evaluations": [
            evaluation
            for evaluation in session_doc.get("evaluations", [])
            if evaluation.get("move_number", 0) <= previous_player_count
        ],
        "coach_move_pending": False,
        "last_coach_move": previous_coach_move,
        "status": "active",
        "result": None,
        "action_revision": session_doc.get("action_revision", 0) + 1,
        "opening_offer_shown": False,
        "detected_opening": None,
    }

    teaching_moves = session_doc.get("opening_teaching_moves", [])
    if teaching_moves:
        rewound_teaching_index = min(session_doc.get("opening_teaching_index", 0), len(truncated_history))
        updated_session_fields.update({
            "opening_teaching_index": rewound_teaching_index,
            "opening_teaching_active": rewound_teaching_index < len(teaching_moves),
            "opening_teaching_complete": rewound_teaching_index >= len(teaching_moves),
        })

    await db.coach_sessions.update_one(
        {"session_id": session_id},
        {"$set": updated_session_fields},
    )

    move_timestamp = last_player_move.get("timestamp")
    cutoff_time = None
    if move_timestamp:
        try:
            cutoff_time = datetime.fromisoformat(move_timestamp)
        except ValueError:
            cutoff_time = None

    if cutoff_time is not None:
        await db.coach_messages.delete_many({
            "session_id": session_id,
            "created_at": {"$gte": cutoff_time},
        })
        await db.coach_feedback.delete_many({
            "session_id": session_id,
            "created_at": {"$gte": cutoff_time},
        })

    state = await get_session_state(db, session_id)
    if not state:
        raise HTTPException(status_code=500, detail="Failed to rebuild state after undo")

    board = chess.Board(restored_fen)
    is_white_turn = board.turn == chess.WHITE
    is_player_turn = (is_white_turn and session_doc.get("user_color") == "white") or (
        (not is_white_turn) and session_doc.get("user_color") == "black"
    )

    state.update({
        "success": True,
        "mode": "game",
        "message": f"Undid your last move: {last_player_move.get('move')}",
        "undone_move": last_player_move.get("move"),
        "undone_move_number": last_player_move.get("move_number", previous_player_count + 1),
        "is_player_turn": is_player_turn,
    })
    return state


@api_router.post("/coach/play/reflect")
async def get_coach_reflection_feedback(
    request: Dict = Body(...),
    user: User = Depends(get_current_user)
):
    """
    Get Socratic coaching feedback after a move.
    
    This is the heart of the interactive coaching system.
    User explains WHY they played a move, coach compares to reality.
    
    Body:
    - session_id: Session ID
    - move_index: Index of the move to reflect on (from move_history)
    - user_reasoning: User's explanation for why they played the move
    
    Returns:
    - main_message: Primary coaching feedback
    - reasoning_feedback: Response to user's stated reasoning
    - position_insight: What was actually important
    - improvement_tip: What to look for next time (if applicable)
    - move_quality: "brilliant", "great", "good", "okay", "inaccuracy", "mistake", "blunder"
    - encouragement: Whether the response is encouraging
    - opening_name: Opening name if in opening phase
    - was_best_move: Whether user found the best move
    """
    from coach_play.coach_commentary import get_coach_feedback
    
    session_id = request.get("session_id")
    move_index = request.get("move_index")
    user_reasoning = request.get("user_reasoning", "")
    
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required")
    if move_index is None:
        raise HTTPException(status_code=400, detail="move_index is required")
    if not user_reasoning:
        raise HTTPException(status_code=400, detail="user_reasoning is required - tell the coach why you played this move!")
    
    # Verify session belongs to user
    session_doc = await db.coach_sessions.find_one({"session_id": session_id})
    if not session_doc:
        raise HTTPException(status_code=404, detail="Session not found")
    if session_doc.get("user_id") != user.user_id:
        raise HTTPException(status_code=403, detail="Not your session")
    
    # Get the move from history
    move_history = session_doc.get("move_history", [])
    if move_index < 0 or move_index >= len(move_history):
        raise HTTPException(status_code=400, detail="Invalid move_index")
    
    move_data = move_history[move_index]
    
    # Only allow reflection on user's own moves
    if move_data.get("by") != "player":
        raise HTTPException(status_code=400, detail="Can only reflect on your own moves")
    
    # Get position info
    fen_before = move_data.get("fen_before")
    move_san = move_data.get("move")
    fen_after = move_data.get("fen_after")
    
    # Calculate move number (accounting for both players)
    move_number = (move_index // 2) + 1
    
    try:
        # Get coach feedback using the Socratic commentary system
        feedback = await get_coach_feedback(
            fen_before=fen_before,
            move_san=move_san,
            fen_after=fen_after,
            user_reasoning=user_reasoning,
            user_color=session_doc.get("user_color", "white"),
            move_number=move_number
        )
        
        return {
            "success": True,
            "move": move_san,
            "move_index": move_index,
            **feedback
        }
        
    except Exception as e:
        logger.error(f"Error getting coach feedback: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post("/coach/play/chat")
async def coach_chat_message(
    request: Dict = Body(...),
    user: User = Depends(get_current_user)
):
    """
    Send a message to the coach and get a PERSONALIZED response.
    
    Unlike chess.com, our coach:
    - Knows your past games and mistakes
    - References similar situations from your history (DETERMINISTIC retrieval)
    - Gives plan-based advice, not just engine moves
    
    Returns:
    - response: Personalized coaching response
    - suggestion_arrow: UCI coords for arrow if suggesting a move
    - position_plan: Strategic plan for the position
    - personal_insight: Reference to past games/patterns
    - pattern_match: DETERMINISTIC pattern retrieval result (for verification)
    """
    from coach_play.coach_commentary import generate_response_to_user, CoachCommentary
    from coach_play.personalized_coach import get_personalized_coaching
    
    session_id = request.get("session_id")
    message = request.get("message", "").strip()
    
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required")
    if not message:
        raise HTTPException(status_code=400, detail="message is required")
    
    # Get session
    session_doc = await db.coach_sessions.find_one({"session_id": session_id})
    if not session_doc:
        raise HTTPException(status_code=404, detail="Session not found")
    if session_doc.get("user_id") != user.user_id:
        raise HTTPException(status_code=403, detail="Not your session")
    
    try:
        current_fen = session_doc.get("current_fen")
        move_history = session_doc.get("move_history", [])
        user_color = session_doc.get("user_color", "white")
        user_rating = session_doc.get("user_rating", 1200)
        
        # Get the last move for context
        user_moves = [m for m in move_history if m.get("by") == "player"]
        last_user_move = user_moves[-1] if user_moves else None
        last_move = last_user_move.get("move", "") if last_user_move else ""
        
        # Build move_analysis for deterministic pattern matching
        move_analysis = None
        if last_user_move and last_user_move.get("fen_before"):
            # Analyze the last move to detect potential pattern
            coach = CoachCommentary()
            try:
                analysis = await coach.analyze_move(
                    last_user_move.get("fen_before"),
                    last_user_move.get("move"),
                    last_user_move.get("fen_after", current_fen)
                )
                move_analysis = {
                    "cp_loss": int(analysis.eval_loss * 100),
                    "best_move": analysis.best_move_san,
                    "quality": analysis.quality.value
                }
            except:
                pass
        
        # Determine phase
        coach = CoachCommentary()
        position = await coach.analyze_position(current_fen)
        phase = position.phase
        
        # Get personalized context from user's history
        # NOW INCLUDES DETERMINISTIC PATTERN RETRIEVAL
        personal_data = await get_personalized_coaching(
            db=db,
            user_id=user.user_id,
            current_fen=current_fen,
            last_move=last_move,
            phase=phase,
            user_color=user_color,
            move_analysis=move_analysis  # Pass for pattern matching
        )
        
        # Generate response with personalization
        result = await generate_response_to_user(
            user_message=message,
            current_fen=current_fen,
            move_history=move_history,
            user_color=user_color,
            user_rating=user_rating,
            personal_context=personal_data.get("personal_context"),
            position_plan=personal_data.get("position_plan")
        )
        
        return {
            "success": True,
            "response": result.get("response", ""),
            "suggestion_arrow": result.get("suggestion_arrow"),
            "move_quality": result.get("move_quality"),
            "best_move": result.get("best_move"),
            "missed_tactic": result.get("missed_tactic"),
            "position_plan": personal_data.get("position_plan"),
            "personal_insight": personal_data.get("personal_context", {}).get("similar_mistake"),
            # VERIFICATION: Expose pattern match for testing
            "pattern_match": personal_data.get("pattern_match")
        }
        
    except Exception as e:
        logger.error(f"Error in coach chat: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post("/coach/play/evaluate")
async def evaluate_coach_play_move(
    request: Dict = Body(...),
    user: User = Depends(get_current_user)
):
    """
    Evaluate a move BEFORE making it - Pre-Move Guardian.
    
    This is the key differentiator: Stop bad moves before they happen.
    Returns intervention info if the move is risky.
    
    IMPORTANT: Uses Stockfish as the PRIMARY arbiter.
    If Stockfish says a move is fine, we DON'T warn - it's tactical awareness!
    
    Body:
    - session_id: Session ID
    - move: Move in SAN notation to evaluate
    
    Returns:
    - should_intervene: Whether to show warning to user
    - intervention_type: "block", "warn", "suggest", or "none"
    - risk_level: "critical", "high", "medium", "low", "none"
    - risk_type: Type of risk (hanging_piece, ignore_threat, etc.)
    - message: Short warning message
    - explanation: Detailed explanation
    - alternative_moves: Better moves to suggest
    - remaining_interventions: How many warnings left this game
    - tactical_awareness: True if move was good despite looking risky
    """
    import chess
    from stockfish_service import StockfishEngine
    
    session_id = request.get("session_id")
    move = request.get("move")
    
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required")
    if not move:
        raise HTTPException(status_code=400, detail="move is required")
    
    # Verify session belongs to user - check both collections
    session_doc = await db.coach_sessions.find_one({"session_id": session_id})
    if not session_doc:
        # Also check play_sessions collection (alternative play endpoint)
        session_doc = await db.play_sessions.find_one({"session_id": session_id})
    
    if not session_doc:
        raise HTTPException(status_code=404, detail="Session not found")
    if session_doc.get("user_id") != user.user_id:
        raise HTTPException(status_code=403, detail="Not your session")
    if session_doc.get("status") != "active":
        raise HTTPException(status_code=400, detail="Session not active")
    
    current_fen = session_doc.get("current_fen")
    user_color = session_doc.get("user_color")
    
    # === STOCKFISH-FIRST EVALUATION ===
    # Get evaluation BEFORE and AFTER the move
    eval_before = None
    eval_after = None
    
    try:
        engine = StockfishEngine()
        engine.start()
        
        try:
            # Evaluate position BEFORE the move
            board_before = chess.Board(current_fen)
            eval_before_cp, _ = engine.evaluate_position(board_before, depth=12)
            eval_before = eval_before_cp / 100.0  # Convert centipawns to pawns
            
            # Apply the move and evaluate AFTER
            chess_move = board_before.parse_san(move)
            board_before.push(chess_move)
            
            eval_after_cp, _ = engine.evaluate_position(board_before, depth=12)
            eval_after = eval_after_cp / 100.0
            
        finally:
            engine.stop()
            
    except Exception as e:
        logger.warning(f"Stockfish evaluation failed: {e}")
        # Continue with heuristics-only if Stockfish fails
    
    # Import the guardian with Stockfish support
    from coach_play.pre_move_guardian import PreMoveGuardian
    
    guardian = PreMoveGuardian(session_doc.get("remaining_interventions", 3))
    guardian_result = guardian.evaluate_move(
        fen=current_fen,
        move_san=move,
        user_color=user_color,
        stockfish_eval_before=eval_before,
        stockfish_eval_after=eval_after
    )
    
    result = guardian_result.to_dict()
    result["remaining_interventions"] = session_doc.get("remaining_interventions", 3)
    
    # Add good trade indicator if applicable (no praise message for normal trades)
    details = result.get("details", {})
    if details.get("good_trade"):
        result["good_trade"] = True
        # No message - trades don't need commentary
    elif details.get("stockfish_approved"):
        result["stockfish_approved"] = True
    
    return result


@api_router.post("/coach/play/move/confirm")
async def confirm_risky_move(
    request: Dict = Body(...),
    user: User = Depends(get_current_user)
):
    """
    Confirm a risky move after user acknowledges the warning.
    
    This is called after evaluate returns should_intervene=True
    and the user explicitly confirms they want to make the move anyway.
    
    Uses the same async flow as /coach/play/move:
    1. Record user's move immediately
    2. Fire background task for coach analysis and response
    3. Return immediately with awaiting_coach=True
    
    Body:
    - session_id: Session ID
    - move: Move in SAN notation
    - time_spent: Time spent on move (seconds)
    - risk_acknowledged: Risk type that was acknowledged
    
    Returns:
    Same as /coach/play/move but also:
    - intervention_consumed: Whether an intervention was used
    """
    import asyncio
    import chess
    
    session_id = request.get("session_id")
    move = request.get("move")
    time_spent = request.get("time_spent", 0.0)
    risk_acknowledged = request.get("risk_acknowledged", "")
    
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required")
    if not move:
        raise HTTPException(status_code=400, detail="move is required")
    
    # Verify session belongs to user
    session_doc = await db.coach_sessions.find_one({"session_id": session_id})
    if not session_doc:
        raise HTTPException(status_code=404, detail="Session not found")
    if session_doc.get("user_id") != user.user_id:
        raise HTTPException(status_code=403, detail="Not your session")
    
    # Record that user overrode the warning
    remaining_interventions = session_doc.get("remaining_interventions", 3)
    if risk_acknowledged:
        override_record = {
            "move": move,
            "risk_type": risk_acknowledged,
            "fen": session_doc.get("current_fen"),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        # Update session to record override and decrement interventions
        await db.coach_sessions.update_one(
            {"session_id": session_id},
            {
                "$push": {"guardian_overrides": override_record},
                "$inc": {"remaining_interventions": -1}
            }
        )
        remaining_interventions = max(0, remaining_interventions - 1)
    
    # Use the same async flow as /coach/play/move
    fen_before = session_doc.get("current_fen")
    user_rating = session_doc.get("user_rating", 1200)
    user_color = session_doc.get("user_color", "white")
    
    try:
        board = chess.Board(fen_before)
        chess_move = board.parse_san(move)
        
        # Record user's move
        board.push(chess_move)
        fen_after_user = board.fen()
        
        move_history = session_doc.get("move_history", [])
        move_number = len([m for m in move_history if m.get("by") == "player"]) + 1
        
        # Add user's move to history
        move_history.append({
            "move": move,
            "uci": chess_move.uci(),
            "by": "player",
            "fen_before": fen_before,
            "fen_after": fen_after_user,
            "time_spent": time_spent,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "guardian_override": bool(risk_acknowledged)
        })
        
        # Update session with user's move (coach move pending)
        await db.coach_sessions.update_one(
            {"session_id": session_id},
            {"$set": {
                "current_fen": fen_after_user,
                "move_history": move_history,
                "coach_move_pending": True
            }}
        )
        
        # Check if game is over after user's move
        game_over = board.is_game_over()
        result = None
        if game_over:
            if board.is_checkmate():
                result = "win"
            elif board.is_stalemate() or board.is_insufficient_material():
                result = "draw"
        
        # Fire background task: analyze → message → coach move
        asyncio.create_task(
            _process_move_and_respond(
                session_id=session_id,
                user_move=move,
                fen_before=fen_before,
                fen_after_user=fen_after_user,
                user_rating=user_rating,
                user_color=user_color,
                move_number=move_number,
                game_over=game_over
            )
        )
        
        return {
            "success": True,
            "user_move_recorded": True,
            "move": move,
            "current_fen": fen_after_user,
            "awaiting_coach": not game_over,
            "game_over": game_over,
            "result": result,
            "intervention_consumed": bool(risk_acknowledged),
            "remaining_interventions": remaining_interventions
        }
        
    except chess.InvalidMoveError:
        raise HTTPException(status_code=400, detail="Invalid move")
    except chess.AmbiguousMoveError:
        raise HTTPException(status_code=400, detail="Ambiguous move - please be more specific")
    except Exception as e:
        logger.error(f"Error confirming risky move: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/coach/play/state/{session_id}")
async def get_coach_play_state(
    session_id: str,
    user: User = Depends(get_current_user)
):
    """
    Get current state of a Play With Coach session.
    
    Returns:
    - session: Full session state
    - current_fen: Current board position
    - is_player_turn: Whether it's the player's turn
    - legal_moves: List of legal moves in SAN notation
    - move_count: Number of moves played
    - game_over: Whether the game has ended
    """
    from coach_play import get_session_state
    
    # Verify session belongs to user
    session_doc = await db.coach_sessions.find_one({"session_id": session_id})
    if not session_doc:
        raise HTTPException(status_code=404, detail="Session not found")
    if session_doc.get("user_id") != user.user_id:
        raise HTTPException(status_code=403, detail="Not your session")
    
    state = await get_session_state(db, session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return state


@api_router.get("/coach/play/feedback/{session_id}")
async def get_coach_play_move_feedback(
    session_id: str,
    user: User = Depends(get_current_user)
):
    """
    Get comprehensive coaching feedback for the last move made.
    
    This is the key endpoint for real-time teaching - returns:
    - Assessment of user's move quality
    - Best move explanation
    - Coach's response explanation
    - Personalized coaching message
    
    Returns:
    - feedback: Complete MoveFeedback object
    """
    from services.realtime_coaching_feedback import get_last_move_feedback
    
    # Verify session belongs to user
    session_doc = await db.coach_sessions.find_one({"session_id": session_id})
    if not session_doc:
        raise HTTPException(status_code=404, detail="Session not found")
    if session_doc.get("user_id") != user.user_id:
        raise HTTPException(status_code=403, detail="Not your session")
    
    feedback = await get_last_move_feedback(db, session_id, user.user_id)
    
    return {"feedback": feedback}


@api_router.post("/coach/play/end")
async def end_coach_play_session(
    request: Dict = Body(...),
    user: User = Depends(get_current_user)
):
    """
    End a Play With Coach session (resign, abort).
    
    Body:
    - session_id: Session ID
    - reason: Reason for ending ("resigned", "abandoned")
    
    Returns:
    - success: bool
    - session: Final session state
    - summary: Game summary
    """
    from coach_play import end_coach_session
    
    session_id = request.get("session_id")
    reason = request.get("reason", "resigned")
    
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required")
    
    # Verify session belongs to user
    session_doc = await db.coach_sessions.find_one({"session_id": session_id})
    if not session_doc:
        raise HTTPException(status_code=404, detail="Session not found")
    if session_doc.get("user_id") != user.user_id:
        raise HTTPException(status_code=403, detail="Not your session")
    
    try:
        result = await end_coach_session(
            db=db,
            session_id=session_id,
            reason=reason
        )
        
        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("error", "End failed"))
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error ending session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post("/coach/play/explain-position")
async def explain_current_position(
    request: Dict = Body(...),
    user: User = Depends(get_current_user)
):
    """
    On-demand position explanation - "Coach, explain my position!"
    
    Uses the intelligent position coaching system to provide
    detailed analysis of the current position including:
    - Pawn structure identification
    - Strategic plans for the user's color
    - Tactical features and warnings
    - Key squares and piece activity
    
    Body:
    - session_id: Session ID
    
    Returns:
    - explanation: Detailed position explanation
    - structure: Pawn structure information
    - plans: Strategic plans for the user
    - tactical: Tactical features
    - tips: Coaching tips
    """
    from services.intelligent_position_coach import analyze_position_and_suggest
    
    session_id = request.get("session_id")
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required")
    
    # Get session
    session_doc = await db.coach_sessions.find_one({"session_id": session_id})
    if not session_doc:
        raise HTTPException(status_code=404, detail="Session not found")
    if session_doc.get("user_id") != user.user_id:
        raise HTTPException(status_code=403, detail="Not your session")
    
    try:
        import chess
        
        # Set up the board
        board = chess.Board(session_doc.get("current_fen", chess.STARTING_FEN))
        move_history = session_doc.get("move_history", [])
        user_color = session_doc.get("user_color", "white")
        
        # Get full position analysis (skip the "already offered" check)
        position_analysis = await analyze_position_and_suggest(
            board=board,
            move_history=[m.get("move", "") for m in move_history],
            user_color=user_color,
            user_id=user.user_id,
            db=db,
            skip_if_opening_offered=False  # Always provide analysis on-demand
        )
        
        if not position_analysis:
            # Fallback: provide basic position info
            from services.position_strategy_analyzer import analyze_position_deeply
            
            deep_analysis = analyze_position_deeply(board.fen(), user_color)
            
            return {
                "success": True,
                "explanation": {
                    "summary": f"You're in a {_get_game_phase_description(board, len(move_history))} position.",
                    "main_idea": "Look for tactical opportunities and make sure all your pieces are active.",
                    "structure_name": "Complex Position",
                    "game_phase": _get_game_phase_description(board, len(move_history)),
                },
                "tactical": {
                    "threats": len(deep_analysis.get("threats", [])),
                    "opportunities": deep_analysis.get("threats", [])[:3],
                    "undefended_pieces": deep_analysis.get("piece_activity", {}).get("undefended", [])
                },
                "tips": [
                    "Make sure all your pieces are on active squares",
                    "Look for any tactical patterns",
                    "Consider your opponent's threats"
                ]
            }
        
        # Return full analysis
        return {
            "success": True,
            "explanation": {
                "summary": position_analysis.get("main_idea", ""),
                "main_idea": position_analysis.get("main_idea", ""),
                "structure_name": position_analysis.get("structure_name"),
                "structure_type": position_analysis.get("structure_type"),
                "game_phase": position_analysis.get("game_phase"),
                "key_characteristics": position_analysis.get("key_characteristics", []),
            },
            "plans": position_analysis.get("strategic_plans", []),
            "tactical": position_analysis.get("tactical_features", {}),
            "insights": position_analysis.get("tactical_insights", []),
            "teaching_points": position_analysis.get("teaching_points", []),
            "critical_squares": position_analysis.get("critical_squares", []),
            "tips": _generate_position_tips(position_analysis, user_color)
        }
        
    except Exception as e:
        logger.error(f"Position explanation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to analyze position")


def _get_game_phase_description(board, move_count: int) -> str:
    """Get a human-readable game phase description."""
    import chess
    piece_count = sum(1 for sq in chess.SQUARES if board.piece_at(sq) and board.piece_at(sq).piece_type not in [chess.PAWN, chess.KING])
    
    if piece_count <= 4:
        return "endgame"
    elif piece_count <= 8:
        return "late middlegame"
    elif move_count < 15:
        return "opening"
    else:
        return "middlegame"


def _generate_position_tips(analysis: dict, user_color: str) -> list:
    """Generate actionable tips from position analysis."""
    tips = []
    
    tactical = analysis.get("tactical_features", {})
    if tactical.get("threats", 0) > 0:
        tips.append(f"You have {tactical['threats']} tactical opportunities - look for them!")
    
    if tactical.get("undefended_pieces", 0) > 0:
        tips.append(f"Warning: {tactical['undefended_pieces']} of your pieces are undefended")
    
    plans = analysis.get("strategic_plans", [])
    if plans:
        tips.append(f"Key plan: {plans[0].get('name', 'Unknown')}")
    
    critical_squares = analysis.get("critical_squares", [])
    if critical_squares:
        tips.append(f"Control these key squares: {', '.join(critical_squares[:3])}")
    
    if not tips:
        tips = [
            "Keep your pieces active",
            "Look for tactical patterns",
            "Consider your pawn structure"
        ]
    
    return tips[:4]


@api_router.post("/coach/play/analysis")
async def get_postgame_analysis(
    request: Dict = Body(...),
    user: User = Depends(get_current_user)
):
    """
    Get comprehensive post-game analysis.
    
    Includes:
    - Performance rating (estimated rating based on move quality)
    - Mistake breakdown with explanations
    - Habit check (comparing to known weaknesses)
    - Personalized recommendations
    - Coach summary and encouragement
    
    Body:
    - session_id: Session ID
    
    Returns:
    - PostGameAnalysis object with all components
    """
    from services.postgame_analysis import analyze_postgame
    from dataclasses import asdict
    
    session_id = request.get("session_id")
    
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required")
    
    # Get session data
    session_doc = await db.coach_sessions.find_one({"session_id": session_id})
    if not session_doc:
        raise HTTPException(status_code=404, detail="Session not found")
    if session_doc.get("user_id") != user.user_id:
        raise HTTPException(status_code=403, detail="Not your session")
    
    try:
        # Get evaluations from stored data
        evaluations = session_doc.get("evaluations", [])
        
        # Perform analysis
        analysis = await analyze_postgame(
            db=db,
            session_id=session_id,
            user_id=user.user_id,
            move_history=session_doc.get("move_history", []),
            evaluations=evaluations,
            game_result=session_doc.get("result", "draw"),
            user_rating=session_doc.get("user_rating", 1200),
            user_color=session_doc.get("user_color", "white"),
            time_controls=session_doc.get("time_controls")
        )
        
        # Convert to dict for JSON response - includes MEMORY INSIGHTS
        result = {
            "session_id": analysis.session_id,
            "game_result": analysis.game_result,
            "performance_rating": {
                "estimated": analysis.performance_rating.estimated_rating,
                "confidence": analysis.performance_rating.confidence,
                "vs_actual": analysis.performance_rating.comparison_to_actual,
                "factors": analysis.performance_rating.key_factors
            },
            "accuracy": analysis.accuracy_percentage,
            "mistakes": {
                "blunders": analysis.total_blunders,
                "mistakes": analysis.total_mistakes,
                "inaccuracies": analysis.total_inaccuracies,
                "details": [
                    {
                        "move_number": m.move_number,
                        "move": m.move_played,
                        "type": m.mistake_type.value,
                        "severity": m.severity,
                        "explanation": m.explanation,
                        "better_move": m.better_move
                    }
                    for m in analysis.mistakes[:5]
                ]
            },
            "habits": {
                "violations": [
                    {
                        "habit": v.habit_type.value,
                        "move_number": v.move_number,
                        "description": v.description
                    }
                    for v in analysis.habit_violations
                ],
                "improved": analysis.habits_improved,
                "still_weak": analysis.habits_still_weak
            },
            # MEMORY INSIGHTS - This is what makes the coach feel human
            "memory": {
                "games_together": analysis.games_together,
                "coach_knows_you": analysis.coach_knows_you,
                "insights": [
                    {
                        "type": insight.insight_type,
                        "message": insight.message,
                        "pattern": insight.pattern_name,
                        "count": insight.occurrence_count,
                        "improving": insight.is_improving
                    }
                    for insight in analysis.memory_insights
                ]
            },
            "recommendations": {
                "priority": analysis.priority_focus,
                "suggestions": analysis.training_suggestions,
                "opening_to_learn": analysis.opening_to_learn
            },
            "coach_summary": analysis.coach_summary,
            "encouragement": analysis.encouragement
        }
        
        return result
        
    except Exception as e:
        logger.error(f"Error generating post-game analysis: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/coach/play/active")
async def get_active_coach_sessions(
    user: User = Depends(get_current_user)
):
    """
    Get user's active Play With Coach sessions.
    
    Returns list of active sessions (usually just one).
    """
    sessions = await db.coach_sessions.find(
        {"user_id": user.user_id, "status": "active"},
        {"_id": 0}
    ).sort("created_at", -1).limit(5).to_list(5)
    
    return {
        "active_sessions": sessions,
        "count": len(sessions)
    }


@api_router.get("/coach/play/history")
async def get_coach_play_history(
    user: User = Depends(get_current_user),
    limit: int = 10
):
    """
    Get user's Play With Coach history.
    
    Returns completed and resigned sessions.
    """
    sessions = await db.coach_sessions.find(
        {
            "user_id": user.user_id,
            "status": {"$in": ["completed", "resigned", "abandoned"]}
        },
        {"_id": 0}
    ).sort("created_at", -1).limit(limit).to_list(limit)
    
    # Add summary stats
    wins = sum(1 for s in sessions if s.get("result") == "win")
    losses = sum(1 for s in sessions if s.get("result") == "loss")
    draws = sum(1 for s in sessions if s.get("result") == "draw")
    
    return {
        "sessions": sessions,
        "stats": {
            "total": len(sessions),
            "wins": wins,
            "losses": losses,
            "draws": draws
        }
    }


@api_router.get("/coach/play/identity")
async def get_player_identity(
    user: User = Depends(get_current_user)
):
    """
    Get user's cognitive identity profile (Step 5).
    
    Identity is built from behavioral patterns across multiple sessions.
    Requires minimum 3 sessions for meaningful identity.
    
    Returns:
    - identity_label: e.g., "The Calculator", "The Warrior"
    - identity_description: Narrative description
    - trait_snapshot: Current trait values
    - confidence: How confident we are (0-1)
    - narrative_timeline: Recent session narratives
    """
    identity = await db.player_identity.find_one(
        {"user_id": user.user_id},
        {"_id": 0}
    )
    
    if not identity:
        return {
            "has_identity": False,
            "message": "Play more games with coach to build your identity profile.",
            "sessions_needed": 3
        }
    
    return {
        "has_identity": True,
        "identity": identity
    }


@api_router.get("/coach/play/cpr/history")
async def get_cpr_history(
    user: User = Depends(get_current_user),
    limit: int = 10
):
    """
    Get user's CPR (Cognitive Performance Rating) history.
    
    Returns CPR scores from recent sessions.
    """
    sessions = await db.coach_sessions.find(
        {
            "user_id": user.user_id,
            "cpr_after": {"$exists": True, "$ne": None}
        },
        {"_id": 0, "session_id": 1, "cpr_after": 1, "created_at": 1, "result": 1}
    ).sort("created_at", -1).limit(limit).to_list(limit)
    
    cpr_scores = [s.get("cpr_after") for s in sessions if s.get("cpr_after")]
    
    return {
        "history": sessions,
        "average_cpr": sum(cpr_scores) / len(cpr_scores) if cpr_scores else None,
        "sessions_count": len(sessions)
    }


@api_router.get("/coach/play/behaviors/{session_id}")
async def get_session_behaviors(
    session_id: str,
    user: User = Depends(get_current_user)
):
    """
    Get behavioral events from a specific session.
    
    Returns detailed behavior analysis for review.
    """
    session_doc = await db.coach_sessions.find_one({"session_id": session_id})
    if not session_doc:
        raise HTTPException(status_code=404, detail="Session not found")
    if session_doc.get("user_id") != user.user_id:
        raise HTTPException(status_code=403, detail="Not your session")
    
    behavior_events = session_doc.get("behavior_events", [])
    
    # Categorize events
    positive = [e for e in behavior_events if e.get("behavior_type") in [
        "calculated_sacrifice", "positional_patience", "tactical_alertness",
        "threat_addressed", "accurate_under_pressure"
    ]]
    negative = [e for e in behavior_events if e.get("behavior_type") in [
        "impulse_move", "threat_ignored", "panic_defense",
        "rapid_streak", "time_pressure_mistake", "repeated_mistake"
    ]]
    
    return {
        "session_id": session_id,
        "total_events": len(behavior_events),
        "positive_behaviors": len(positive),
        "negative_behaviors": len(negative),
        "events": behavior_events,
        "summary": {
            "positive": positive,
            "negative": negative
        }
    }



@api_router.post("/coach/play/feedback")
async def submit_coach_feedback(
    request: Dict = Body(...),
    user: User = Depends(get_current_user)
):
    """
    Submit feedback on a coach message (for beta users).
    
    Body:
    - session_id: The game session ID
    - message_id: The coach message ID
    - feedback_type: "confusing" | "wrong" | "obvious" | "not_relevant" | "other"
    - comment: Optional user comment
    
    Returns:
    - success: True if feedback was recorded
    """
    session_id = request.get("session_id")
    message_id = request.get("message_id")
    feedback_type = request.get("feedback_type", "other")
    comment = request.get("comment", "")
    
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required")
    if not message_id:
        raise HTTPException(status_code=400, detail="message_id is required")
    
    # Validate feedback_type
    valid_types = ["confusing", "wrong", "obvious", "not_relevant", "helpful", "other"]
    if feedback_type not in valid_types:
        feedback_type = "other"
    
    # Get session to verify ownership and get context
    session_doc = await db.coach_sessions.find_one({"session_id": session_id})
    if not session_doc:
        raise HTTPException(status_code=404, detail="Session not found")
    if session_doc.get("user_id") != user.user_id:
        raise HTTPException(status_code=403, detail="Not your session")
    
    # Get the message for context
    message_doc = await db.coach_messages.find_one({"_id": message_id})
    message_context = {}
    if message_doc:
        message_context = {
            "message": message_doc.get("message", ""),
            "trigger": message_doc.get("trigger", ""),
            "move": message_doc.get("move", ""),
            "rule_id": message_doc.get("rule_id", ""),
            "is_wisdom_based": message_doc.get("is_wisdom_based", False),
        }
    
    # Store feedback
    from datetime import datetime, timezone
    await db.coach_feedback.insert_one({
        "user_id": user.user_id,
        "session_id": session_id,
        "message_id": message_id,
        "feedback_type": feedback_type,
        "comment": comment,
        "current_fen": session_doc.get("current_fen", ""),
        "message_context": message_context,
        "user_rating": session_doc.get("user_rating", 1200),
        "created_at": datetime.now(timezone.utc),
    })
    
    logger.info(f"Coach feedback recorded: type={feedback_type}, session={session_id}, message={message_id}")
    
    return {
        "success": True,
        "message": "Thank you for your feedback! It helps us improve the coach."
    }


# ========================================
# ENDGAME TEACHING ENDPOINTS
# ========================================

@api_router.post("/coach/play/endgame/start")
async def start_endgame_lesson(
    request: Dict = Body(...),
    user: User = Depends(get_current_user)
):
    """
    Start an interactive endgame lesson.
    
    Body:
    - session_id: Current game session
    - lesson_key: Key of the lesson to start (e.g., "queen_checkmate", "opposition")
    
    Returns lesson setup and first instruction.
    """
    from services.endgame_teaching import start_endgame_lesson as start_lesson
    
    session_id = request.get("session_id")
    lesson_key = request.get("lesson_key")
    
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required")
    if not lesson_key:
        raise HTTPException(status_code=400, detail="lesson_key is required")
    
    # Verify session
    session_doc = await db.coach_sessions.find_one({"session_id": session_id})
    if not session_doc:
        raise HTTPException(status_code=404, detail="Session not found")
    if session_doc.get("user_id") != user.user_id:
        raise HTTPException(status_code=403, detail="Not your session")
    
    result = await start_lesson(db, session_id, lesson_key)
    
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    
    return result


@api_router.post("/coach/play/endgame/move")
async def process_endgame_lesson_move(
    request: Dict = Body(...),
    user: User = Depends(get_current_user)
):
    """
    Process a move during endgame lesson.
    
    Body:
    - session_id: Current game session
    - move: Move played by user (SAN notation)
    """
    from services.endgame_teaching import process_endgame_teaching_move
    
    session_id = request.get("session_id")
    move = request.get("move")
    
    if not session_id or not move:
        raise HTTPException(status_code=400, detail="session_id and move are required")
    
    session_doc = await db.coach_sessions.find_one({"session_id": session_id})
    if not session_doc:
        raise HTTPException(status_code=404, detail="Session not found")
    if session_doc.get("user_id") != user.user_id:
        raise HTTPException(status_code=403, detail="Not your session")
    
    result = await process_endgame_teaching_move(db, session_id, move)
    
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    
    return result


# ========================================
# COACH MEMORY ENDPOINTS
# ========================================

@api_router.get("/coach/memory")
async def get_coach_memory(user: User = Depends(get_current_user)):
    """
    Get the coach's memory about the user.
    
    Returns insights, patterns, and personalized context.
    """
    from services.coach_memory import get_coaching_context, get_personalized_greeting
    
    context = await get_coaching_context(db, user.user_id)
    greeting = await get_personalized_greeting(db, user.user_id)
    
    return {
        "greeting": greeting,
        "context": context
    }


@api_router.post("/coach/memory/update")
async def update_coach_memory(
    request: Dict = Body(...),
    user: User = Depends(get_current_user)
):
    """
    Update coach memory after a game.
    
    Body:
    - session_id: Game session that just ended
    - game_result: "win", "loss", "draw"
    - accuracy: Accuracy percentage
    - blunders: Number of blunders
    - mistakes: Number of mistakes
    - habits_violated: List of habit IDs violated
    - habits_improved: List of habit IDs improved
    - opening_played: Opening name if identified
    - performance_rating: Estimated performance rating
    """
    from services.coach_memory import update_memory_after_game
    
    session_id = request.get("session_id")
    
    # Get session for context
    session_doc = await db.coach_sessions.find_one({"session_id": session_id})
    if session_doc and session_doc.get("user_id") != user.user_id:
        raise HTTPException(status_code=403, detail="Not your session")
    
    memory = await update_memory_after_game(
        db=db,
        user_id=user.user_id,
        game_result=request.get("game_result", "draw"),
        accuracy=request.get("accuracy", 0),
        blunders=request.get("blunders", 0),
        mistakes=request.get("mistakes", 0),
        habits_violated=request.get("habits_violated", []),
        habits_improved=request.get("habits_improved", []),
        opening_played=request.get("opening_played"),
        endgame_reached=request.get("endgame_reached", False),
        performance_rating=request.get("performance_rating", 1200)
    )
    
    return {
        "success": True,
        "insights": memory.last_game_insights,
        "patterns": memory.recurring_patterns,
        "games_played": memory.performance.games_played
    }



# ========================================
# PLAYER IDENTITY (DEEP MEMORY) ENDPOINTS
# ========================================

@api_router.get("/coach/deep-memory")
async def get_deep_memory(user: User = Depends(get_current_user)):
    """
    Get the deep memory profile for the user.
    
    This is the NEW 9/10 memory system that tracks:
    - Granular blunder taxonomy (WHY mistakes happen)
    - Playing style profile
    - Behavioral patterns (tilt, time management)
    - Opening repertoire
    - Learning velocity
    - Pattern history for "remember when..." coaching
    
    Returns the complete PlayerIdentity document.
    """
    # Get raw identity document to avoid enum validation issues
    identity_doc = await db.player_identities.find_one(
        {"user_id": user.user_id},
        {"_id": 0}
    )
    
    if not identity_doc:
        # Return empty state
        return {
            "has_data": False,
            "games_analyzed": 0,
            "identity": {"user_id": user.user_id},
            "summary": {
                "primary_style": "developing",
                "most_common_blunder": None,
                "blunder_trend": "stable",
                "worst_phase": None,
                "is_tilted": False,
                "priority_focus": None,
                "coach_notes": []
            }
        }
    
    games_analyzed = identity_doc.get("games_analyzed", 0)
    blunder_tax = identity_doc.get("blunder_taxonomy", {})
    style_prof = identity_doc.get("style_profile", {})
    behavioral = identity_doc.get("behavioral_profile", {})
    
    return {
        "has_data": games_analyzed > 0,
        "games_analyzed": games_analyzed,
        "identity": identity_doc,
        "summary": {
            "primary_style": style_prof.get("primary_style", "developing"),
            "most_common_blunder": blunder_tax.get("most_common_type"),
            "blunder_trend": blunder_tax.get("trend", "stable"),
            "worst_phase": blunder_tax.get("worst_phase"),
            "is_tilted": identity_doc.get("consecutive_losses", 0) >= 2,
            "priority_focus": identity_doc.get("priority_focus"),
            "coach_notes": identity_doc.get("coach_notes", [])
        }
    }


@api_router.get("/coach/deep-memory/blunder-profile")
async def get_blunder_profile(user: User = Depends(get_current_user)):
    """
    Get detailed blunder analysis for the user.
    
    Returns:
    - Blunder taxonomy breakdown
    - Most common mistakes by type, phase, piece
    - Time-related patterns
    - Trend analysis
    """
    from services.player_identity import PlayerIdentityService
    
    service = PlayerIdentityService(db)
    identity = await service.get_or_create(user.user_id)
    
    tax = identity.blunder_taxonomy
    
    return {
        "total_blunders": tax.total_blunders,
        "by_type": tax.by_type,
        "by_phase": tax.by_phase,
        "by_piece": tax.by_piece,
        "context_breakdown": {
            "when_winning": tax.when_winning,
            "when_equal": tax.when_equal,
            "when_losing": tax.when_losing
        },
        "time_patterns": {
            "under_time_pressure": tax.under_time_pressure,
            "impulse_moves": tax.impulse_moves
        },
        "trend": {
            "recent_rate": tax.recent_rate,
            "historical_rate": tax.historical_rate,
            "direction": tax.trend
        },
        "primary_weakness": tax.most_common_type.value if tax.most_common_type else None,
        "vulnerable_piece": tax.most_vulnerable_piece,
        "worst_phase": tax.worst_phase.value if tax.worst_phase else None
    }


@api_router.get("/coach/deep-memory/style")
async def get_style_profile(user: User = Depends(get_current_user)):
    """
    Get user's playing style analysis.
    """
    from services.player_identity import PlayerIdentityService
    
    service = PlayerIdentityService(db)
    identity = await service.get_or_create(user.user_id)
    
    style = identity.style_profile
    
    return {
        "primary_style": style.primary_style.value,
        "confidence": style.confidence,
        "metrics": {
            "aggression": style.aggression_score,
            "positional": style.positional_score,
            "tactical": style.tactical_score,
            "defensive": style.defensive_score
        },
        "opening_preferences": {
            "as_white": style.opening_as_white,
            "vs_e4": style.opening_as_black_vs_e4,
            "vs_d4": style.opening_as_black_vs_d4,
            "prefers_open_games": style.prefers_open_games
        },
        "piece_handling": {
            "preference": style.piece_preference.value,
            "trades_early": style.trades_pieces_early,
            "keeps_queens": style.keeps_queens
        },
        "endgame": {
            "comfort": style.endgame_comfort,
            "rook_skill": style.rook_endgame_skill,
            "pawn_skill": style.pawn_endgame_skill
        }
    }


@api_router.get("/coach/deep-memory/behavioral")
async def get_behavioral_profile(user: User = Depends(get_current_user)):
    """
    Get user's behavioral patterns.
    
    Includes tilt triggers, time management, post-blunder behavior.
    """
    from services.player_identity import PlayerIdentityService
    
    service = PlayerIdentityService(db)
    identity = await service.get_or_create(user.user_id)
    
    beh = identity.behavioral_profile
    
    return {
        "tilt": {
            "trigger": beh.tilt_trigger.value,
            "recovery_games": beh.tilt_recovery_games,
            "times_detected": beh.tilt_detected_count,
            "currently_tilted": identity.consecutive_losses >= 2,
            "losing_streak": identity.consecutive_losses
        },
        "time_management": {
            "avg_opening": beh.avg_move_time_opening,
            "avg_middlegame": beh.avg_move_time_middlegame,
            "avg_endgame": beh.avg_move_time_endgame,
            "time_trouble_frequency": beh.time_trouble_frequency,
            "rushes_when_winning": beh.rushes_in_winning_positions
        },
        "post_blunder": {
            "accuracy_after": beh.post_blunder_accuracy,
            "spiral_rate": beh.blunder_spiral_rate,
            "recovery": beh.recovery_capability
        },
        "emotional": {
            "worse_after_loss": beh.plays_worse_after_loss,
            "better_after_win": beh.plays_better_after_win,
            "consistency": beh.consistency_score
        },
        "session": {
            "first_game_accuracy": beh.first_game_accuracy,
            "fatigue_threshold": beh.fatigue_game_threshold,
            "best_time": beh.best_time_of_day
        }
    }


@api_router.get("/coach/deep-memory/pattern-history")
async def get_pattern_history(
    user: User = Depends(get_current_user),
    limit: int = 20
):
    """
    Get recent pattern history for "remember when..." coaching.
    
    Returns specific game references where patterns occurred.
    """
    # Get identity directly from DB to support both old and new format
    identity_doc = await db.player_identities.find_one(
        {"user_id": user.user_id},
        {"_id": 0, "pattern_history": 1}
    )
    
    if not identity_doc or not identity_doc.get("pattern_history"):
        return {
            "total_patterns": 0,
            "recent_patterns": [],
            "grouped_by_type": {},
            "most_recent_types": []
        }
    
    pattern_history = identity_doc.get("pattern_history", [])
    
    # Get most recent patterns
    recent = pattern_history[-limit:] if pattern_history else []
    
    # Handle both dict and object formats
    def pattern_to_dict(p):
        if isinstance(p, dict):
            return p
        elif hasattr(p, 'to_dict'):
            return p.to_dict()
        return {}
    
    recent_dicts = [pattern_to_dict(p) for p in reversed(recent)]
    
    # Group by type
    by_type = {}
    for p in recent_dicts:
        t = p.get("pattern_type", "unknown")
        if t not in by_type:
            by_type[t] = []
        by_type[t].append(p)
    
    return {
        "total_patterns": len(pattern_history),
        "recent_patterns": recent_dicts,
        "grouped_by_type": by_type,
        "most_recent_types": list(dict.fromkeys([p.get("pattern_type", "unknown") for p in recent_dicts]))[:5]
    }


@api_router.post("/coach/deep-memory/reset")
async def reset_deep_memory(user: User = Depends(get_current_user)):
    """
    Reset the deep memory system for the user.
    
    USE WITH CAUTION - this erases all learning history.
    """
    # Delete the player identity document
    result = await db.player_identities.delete_one({"user_id": user.user_id})
    
    return {
        "success": True,
        "deleted": result.deleted_count > 0,
        "message": "Deep memory has been reset. The coach will start fresh with you."
    }






@api_router.get("/coach/play/opening-plan")
async def get_opening_plan(
    session_id: str,
    user: User = Depends(get_current_user)
):
    """
    Get the current opening plan for a game session.
    
    Returns opening name, main ideas, and teaching points.
    """
    from coach_engine.opening_plans import get_opening_by_moves, OPENING_PLANS
    from coach_engine.lichess_explorer import get_opening_name
    
    session_doc = await db.coach_sessions.find_one({"session_id": session_id})
    if not session_doc:
        raise HTTPException(status_code=404, detail="Session not found")
    if session_doc.get("user_id") != user.user_id:
        raise HTTPException(status_code=403, detail="Not your session")
    
    # Get moves from history
    move_history = session_doc.get("move_history", [])
    moves = [m.get("move", "") for m in move_history if m.get("move")]
    
    # Try to identify opening from our database
    opening = get_opening_by_moves(moves)
    
    # Also check Lichess for opening name
    current_fen = session_doc.get("current_fen", "")
    lichess_name = ""
    try:
        lichess_name = await get_opening_name(current_fen)
    except:
        pass
    
    if opening:
        return {
            "success": True,
            "opening_name": opening.name,
            "lichess_name": lichess_name,
            "main_ideas": opening.main_ideas,
            "key_squares": opening.key_squares,
            "typical_mistakes": opening.typical_mistakes,
            "simple_explanation": opening.simple_explanation,
            "eco_codes": opening.eco_codes,
        }
    elif lichess_name:
        return {
            "success": True,
            "opening_name": lichess_name,
            "lichess_name": lichess_name,
            "main_ideas": [
                "Develop your knights and bishops",
                "Control the center",
                "Castle to protect your king"
            ],
            "key_squares": [],
            "typical_mistakes": [],
            "simple_explanation": f"This is the {lichess_name}. Focus on development and king safety.",
            "eco_codes": [],
        }
    else:
        return {
            "success": True,
            "opening_name": None,
            "lichess_name": None,
            "main_ideas": [
                "Develop your pieces",
                "Control the center",
                "Keep your king safe"
            ],
            "key_squares": [],
            "typical_mistakes": [],
            "simple_explanation": "Focus on basic opening principles.",
            "eco_codes": [],
        }



# ========================================
# OPENING TEACHING ENDPOINTS
# ========================================

@api_router.post("/coach/play/teaching/start")
async def start_opening_teaching(
    request: Dict = Body(...),
    user: User = Depends(get_current_user)
):
    """
    Start an interactive opening lesson during the game.
    
    Called when user clicks a teaching option (e.g., "Learn the Fried Liver").
    
    Body:
    - session_id: Current game session
    - lesson_type: "learn_trap" | "learn_main_line"
    
    Returns:
    - success: bool
    - mode: Teaching mode
    - instruction: First teaching step
    - teaching_fen: Position to display
    """
    from services.opening_teaching_integration import start_opening_lesson
    
    session_id = request.get("session_id")
    lesson_type = request.get("lesson_type", "learn_trap")
    
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required")
    
    # Verify session belongs to user
    session_doc = await db.coach_sessions.find_one({"session_id": session_id})
    if not session_doc:
        raise HTTPException(status_code=404, detail="Session not found")
    if session_doc.get("user_id") != user.user_id:
        raise HTTPException(status_code=403, detail="Not your session")
    
    result = await start_opening_lesson(db, session_id, user.user_id, lesson_type)
    
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    
    return result


@api_router.post("/coach/play/teaching/move")
async def process_teaching_move(
    request: Dict = Body(...),
    user: User = Depends(get_current_user)
):
    """
    Process a move during opening teaching mode.
    
    Validates the move, provides feedback, and advances the lesson.
    
    Body:
    - session_id: Current game session
    - move: Move played by user (SAN notation)
    
    Returns:
    - correct: bool
    - message: Feedback message
    - next_instruction: Next teaching step (if correct)
    - teaching_fen: Updated position
    """
    from services.opening_teaching_integration import process_teaching_move as process_move
    
    session_id = request.get("session_id")
    move = request.get("move")
    
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required")
    if not move:
        raise HTTPException(status_code=400, detail="move is required")
    
    # Verify session belongs to user
    session_doc = await db.coach_sessions.find_one({"session_id": session_id})
    if not session_doc:
        raise HTTPException(status_code=404, detail="Session not found")
    if session_doc.get("user_id") != user.user_id:
        raise HTTPException(status_code=403, detail="Not your session")
    
    result = await process_move(db, session_id, move)
    
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    
    return result


@api_router.post("/coach/play/teaching/exit")
async def exit_teaching_mode(
    request: Dict = Body(...),
    user: User = Depends(get_current_user)
):
    """
    Exit teaching mode after lesson completion.
    
    Body:
    - session_id: Current game session
    - choice: "continue_game" | "new_game" | "try_another"
    
    Returns:
    - action: What happens next
    - restored_fen: Position to return to (if continuing)
    """
    from services.opening_teaching_integration import exit_teaching_mode as exit_mode
    
    session_id = request.get("session_id")
    choice = request.get("choice", "continue_game")
    
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required")
    
    # Verify session belongs to user
    session_doc = await db.coach_sessions.find_one({"session_id": session_id})
    if not session_doc:
        raise HTTPException(status_code=404, detail="Session not found")
    if session_doc.get("user_id") != user.user_id:
        raise HTTPException(status_code=403, detail="Not your session")
    
    result = await exit_mode(db, session_id, choice)
    
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    
    return result


@api_router.post("/coach/play/teaching/skip")
async def skip_opening_offer(
    request: Dict = Body(...),
    user: User = Depends(get_current_user)
):
    """
    Skip the opening teaching offer (user chose "Just play").
    
    Body:
    - session_id: Current game session
    """
    session_id = request.get("session_id")
    
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required")
    
    # Verify session belongs to user
    session_doc = await db.coach_sessions.find_one({"session_id": session_id})
    if not session_doc:
        raise HTTPException(status_code=404, detail="Session not found")
    if session_doc.get("user_id") != user.user_id:
        raise HTTPException(status_code=403, detail="Not your session")
    
    # Mark as skipped so we don't show again
    await db.coach_sessions.update_one(
        {"session_id": session_id},
        {"$set": {"opening_offer_shown": True}}
    )
    
    return {"success": True, "message": "Got it! Let's play on."}




@api_router.get("/coach/breakthrough-signal")
async def get_breakthrough_signal(
    user: User = Depends(get_current_user)
):
    """
    Get the user's current breakthrough/plateau signal (Step 8).
    
    Computes on-demand from last 20 games + memory.
    Returns state, headline, message, and recommended action.
    
    Response schema:
    {
        "state": "PLATEAU|BREAKTHROUGH|CONFIDENCE_ILLUSION|TILT_RISK|STABLE_GROWTH|NORMAL",
        "confidence": 0.0-1.0,
        "headline": "string",
        "message": "string",
        "cta": {"label": "string", "action": "string", "payload": {}},
        "dominant_lesson_key": "string|null",
        "show_card": bool  # True if user has >= 10 analyzed games
    }
    """
    # Get user's recent analyzed games (up to 20)
    # Look for analyses with stockfish_analysis (indicates real analysis)
    recent_analyses = await db.game_analyses.find(
        {"user_id": user.user_id, "stockfish_analysis": {"$exists": True}},
        {"_id": 0, "game_id": 1, "result": 1, "user_color": 1, 
         "stockfish_analysis": 1, "game_coach_summary": 1, "analyzed_at": 1}
    ).sort("analyzed_at", -1).limit(20).to_list(20)
    
    # Check minimum games threshold
    if len(recent_analyses) < 10:
        return {
            "show_card": False,
            "state": "NORMAL",
            "confidence": 0.5,
            "headline": "Keep going. Stay consistent.",
            "message": "Play more games to unlock weekly coaching insights.",
            "cta": {"label": "Play Next Game", "action": "STANDARD_FLOW", "payload": {}},
            "dominant_lesson_key": None,
            "games_needed": 10 - len(recent_analyses)
        }
    
    # Build game data for signal computation
    recent_games = []
    lesson_keys = []
    
    for analysis in recent_analyses:
        sf = analysis.get("stockfish_analysis", {})
        summary = analysis.get("game_coach_summary", {})
        
        # Count blunders and mistakes from move evaluations
        move_evals = sf.get("move_evaluations", [])
        
        # Determine which moves are user's based on user_color
        user_color = analysis.get("user_color", "white")
        
        blunders = 0
        mistakes = 0
        total_cp_loss = 0
        user_move_count = 0
        
        for i, m in enumerate(move_evals):
            # Determine if this is user's move based on move number parity
            # White plays on odd move numbers (1, 3, 5...), Black on even (2, 4, 6...)
            move_num = m.get("move_number", i + 1)
            is_user_move = (user_color == "white" and move_num % 2 == 1) or \
                          (user_color == "black" and move_num % 2 == 0)
            
            if is_user_move:
                cp_loss = m.get("cp_loss", 0)
                total_cp_loss += cp_loss
                user_move_count += 1
                
                # Classify based on cp_loss thresholds
                if cp_loss >= 200:  # Blunder
                    blunders += 1
                elif cp_loss >= 100:  # Mistake
                    mistakes += 1
        
        # Calculate average cp_loss for user moves
        avg_cp = total_cp_loss / max(user_move_count, 1)
        
        # Determine result
        result = analysis.get("result", "draw")
        user_color = analysis.get("user_color", "white")
        if result == "1-0":
            game_result = "win" if user_color == "white" else "loss"
        elif result == "0-1":
            game_result = "win" if user_color == "black" else "loss"
        else:
            game_result = "draw"
        
        recent_games.append({
            "blunders": blunders,
            "mistakes": mistakes,
            "avg_cp_loss": avg_cp,
            "result": game_result,
        })
        
        # Get lesson key from summary
        lesson_key = summary.get("lesson_key") or summary.get("primary_issue")
        if lesson_key:
            lesson_keys.append(lesson_key)
    
    # Get coach state for maturity tier
    coach_state = await db.coach_states.find_one(
        {"user_id": user.user_id},
        {"_id": 0, "behavioral_maturity": 1, "good_game_streak": 1, 
         "recent_game_accuracies": 1, "milestones": 1}
    )
    
    maturity_tier = "Developing"
    good_game_streak = 0
    milestone_recent = False
    recent_accuracies = []
    
    if coach_state:
        maturity = coach_state.get("behavioral_maturity", {})
        maturity_tier = maturity.get("level", "Developing")
        good_game_streak = coach_state.get("good_game_streak", 0)
        recent_accuracies = coach_state.get("recent_game_accuracies", [])
        
        # Check for recent milestone (last 5 games)
        milestones = coach_state.get("milestones", [])
        if milestones:
            recent_milestones = [m for m in milestones[-5:] if m.get("achieved")]
            milestone_recent = len(recent_milestones) > 0
    
    # Detect improvement trajectory
    improvement_trajectory = "stable"
    if len(recent_accuracies) >= 5:
        first_half = recent_accuracies[:len(recent_accuracies)//2]
        second_half = recent_accuracies[len(recent_accuracies)//2:]
        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)
        diff = (avg_second - avg_first) / max(avg_first, 1) * 100
        if diff > 5:
            improvement_trajectory = "improving"
        elif diff < -5:
            improvement_trajectory = "declining"
    
    # Calculate consecutive losses
    consecutive_losses = 0
    for g in recent_games:
        if g["result"] == "loss":
            consecutive_losses += 1
        else:
            break
    
    # Find dominant lesson key and intensity
    dominant_lesson_key = None
    dominant_lesson_intensity = 0
    if lesson_keys:
        from collections import Counter
        lesson_counts = Counter(lesson_keys)
        dominant_lesson_key, count = lesson_counts.most_common(1)[0]
        # Intensity based on frequency
        dominant_lesson_intensity = 1 if count < 3 else (2 if count < 5 else 3)
    
    # Get signal
    signal = get_breakthrough_signal_for_user(
        recent_games=recent_games,
        lesson_keys=lesson_keys,
        consecutive_losses=consecutive_losses,
        good_game_streak=good_game_streak,
        milestone_recent=milestone_recent,
        dominant_lesson_key=dominant_lesson_key,
        dominant_lesson_intensity=dominant_lesson_intensity,
        improvement_trajectory=improvement_trajectory,
        discipline_improving=improvement_trajectory == "improving",
        maturity_tier=maturity_tier,
    )
    
    # Build CTA with action-specific payload
    cta_payload = {}
    if signal.state == "PLATEAU":
        cta_payload = {"force_theme": dominant_lesson_key}
    elif signal.state == "CONFIDENCE_ILLUSION":
        cta_payload = {"lock_lesson_key": dominant_lesson_key, "duration_games": 5}
    elif signal.state == "TILT_RISK":
        cta_payload = {"duration_games": 3, "lock_theme": True}
    
    # === ENHANCE WITH DEEP MEMORY INSIGHTS ===
    # If state is NORMAL, add personalized insights from PlayerIdentity
    enhanced_message = signal.coach_message
    enhanced_headline = signal.headline
    
    if signal.state == "NORMAL":
        try:
            from services.player_identity import PlayerIdentityService
            identity_service = PlayerIdentityService(db)
            identity = await identity_service.get_or_create(user.user_id)
            
            if identity.games_analyzed >= 5:
                insights = []
                
                # Blunder focus
                if identity.blunder_taxonomy.most_common_type:
                    blunder_type = identity.blunder_taxonomy.most_common_type.value.replace("_", " ")
                    insights.append(f"Your main weakness: {blunder_type}")
                
                # Phase focus
                if identity.blunder_taxonomy.worst_phase:
                    phase = identity.blunder_taxonomy.worst_phase.value
                    insights.append(f"Focus on: {phase} play")
                
                # Trend
                if identity.blunder_taxonomy.trend == "improving":
                    enhanced_headline = "Making progress!"
                    insights.append("Your blunder rate is decreasing")
                elif identity.blunder_taxonomy.trend == "worsening":
                    enhanced_headline = "Let's refocus."
                    insights.append("Blunder rate increasing - slow down")
                
                # Behavioral
                if identity.consecutive_losses >= 2:
                    enhanced_headline = "Take a breath."
                    insights.append(f"You've lost {identity.consecutive_losses} in a row")
                elif identity.consecutive_wins >= 3:
                    enhanced_headline = "On fire!"
                    insights.append(f"{identity.consecutive_wins}-game win streak!")
                
                # Build enhanced message
                if insights:
                    enhanced_message = " | ".join(insights)
        except Exception as e:
            logger.warning(f"Could not enhance signal with deep memory: {e}")
    
    return {
        "show_card": True,
        "state": signal.state,
        "confidence": signal.confidence,
        "headline": enhanced_headline,
        "message": enhanced_message,
        "cta": {
            "label": signal.cta,
            "action": signal.recommended_action,
            "payload": cta_payload
        },
        "dominant_lesson_key": signal.dominant_lesson_key
    }


# =============================================================================
# FOCUS LOCK ENDPOINTS (Step 9)
# =============================================================================

class FocusLockActivateRequest(BaseModel):
    """Request to activate a focus lock."""
    lesson_key: str
    games: int = DEFAULT_LOCK_GAMES


@api_router.get("/coach/focus-lock")
async def get_focus_lock(
    user: User = Depends(get_current_user)
):
    """
    Get the user's current focus lock state (Step 9).
    
    This is a READ-ONLY endpoint. Never computes compliance here.
    Returns computed state from DB.
    
    Response schema when lock is active:
    {
        "active": true,
        "lesson_key": "FORCING_BLIND",
        "rule_description": "...",
        "state": "ACTIVE|EXTENDED|STRICT|COMPLETED|FAILED",
        "headline": "...",
        "message": "...",
        "progress": {"completed": 2, "required": 5, "text": "2 of 5 games"},
        "compliance": {"average": 75, "color": "yellow", "text": "..."},
        "strict_mode": false,
        "cta": "Start Next Game",
        "should_trigger_deep_session": false
    }
    
    Response when no lock:
    {
        "active": false
    }
    """
    # Get coach state with focus lock
    coach_state = await db.coach_states.find_one(
        {"user_id": user.user_id},
        {"_id": 0, "focus_lock": 1}
    )
    
    if not coach_state or not coach_state.get("focus_lock"):
        return {"active": False}
    
    lock = focus_lock_from_db(coach_state.get("focus_lock"))
    if not lock:
        return {"active": False}
    
    # Get UI-ready state
    ui_state = get_lock_ui_state(lock)
    
    if not ui_state:
        return {"active": False}
    
    # Add deep session trigger flag
    ui_state["should_trigger_deep_session"] = should_trigger_deep_session(lock)
    ui_state["failed_cycles"] = lock.failed_cycles
    
    return ui_state


@api_router.post("/coach/focus-lock/activate")
async def activate_focus_lock(
    req: FocusLockActivateRequest,
    user: User = Depends(get_current_user)
):
    """
    Activate a focus lock for the user (Step 9).
    
    Guardrails - Reject activation if:
    - Lock already active
    - < 10 games analyzed
    - Breakthrough state active (BREAKTHROUGH or TILT_RISK in recovery)
    
    Only internal calls should hit this (triggered by breakthrough service).
    
    Request body:
    {
        "lesson_key": "FORCING_BLIND|STOPPED_CALCULATION_EARLY|THREAT_VERIFICATION",
        "games": 5  # Optional, default 5
    }
    """
    # Validate lesson_key
    valid_keys = ("FORCING_BLIND", "STOPPED_CALCULATION_EARLY", "THREAT_VERIFICATION")
    if req.lesson_key not in valid_keys:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid lesson_key. Must be one of: {valid_keys}"
        )
    
    # Check if user has enough analyzed games
    # Check for analyses with stockfish_analysis (indicates real analysis)
    analyzed_count = await db.game_analyses.count_documents({
        "user_id": user.user_id,
        "stockfish_analysis": {"$exists": True}
    })
    
    if analyzed_count < 10:
        raise HTTPException(
            status_code=400,
            detail=f"Need at least 10 analyzed games. You have {analyzed_count}."
        )
    
    # Get current coach state
    coach_state = await db.coach_states.find_one(
        {"user_id": user.user_id},
        {"_id": 0, "focus_lock": 1}
    )
    
    # Check if lock already active
    if coach_state and coach_state.get("focus_lock"):
        existing_lock = focus_lock_from_db(coach_state.get("focus_lock"))
        if existing_lock and existing_lock.state not in ("COMPLETED", "FAILED", "NONE"):
            raise HTTPException(
                status_code=400,
                detail=f"Focus lock already active for {existing_lock.lesson_key}. Complete current lock first."
            )
    
    # Create new focus lock
    new_lock = create_focus_lock(req.lesson_key, req.games)
    
    # Persist to DB (upsert coach_state if needed)
    await db.coach_states.update_one(
        {"user_id": user.user_id},
        {
            "$set": {
                "focus_lock": focus_lock_to_db(new_lock),
                "focus_lock_activated_at": datetime.now(timezone.utc).isoformat()
            }
        },
        upsert=True
    )
    
    logger.info(f"Focus lock activated for user {user.user_id}: {req.lesson_key} for {req.games} games")
    
    return {
        "status": "activated",
        "lesson_key": new_lock.lesson_key,
        "rule_description": RULE_DESCRIPTIONS.get(new_lock.lesson_key, ""),
        "games_required": new_lock.games_required,
        "headline": new_lock.headline,
        "message": new_lock.message
    }


@api_router.post("/coach/focus-lock/deactivate")
async def deactivate_focus_lock(
    user: User = Depends(get_current_user)
):
    """
    Force-deactivate a focus lock (admin/debug use only).
    
    Sets lock state to NONE.
    Logs as quit_mid_lock for analytics.
    """
    # Get existing lock before deactivating (for analytics)
    coach_state = await db.coach_states.find_one(
        {"user_id": user.user_id},
        {"_id": 0, "focus_lock": 1}
    )
    
    existing_lock = None
    if coach_state and coach_state.get("focus_lock"):
        existing_lock = focus_lock_from_db(coach_state.get("focus_lock"))
    
    result = await db.coach_states.update_one(
        {"user_id": user.user_id},
        {"$set": {"focus_lock": None}}
    )
    
    if result.modified_count > 0:
        # Log quit_mid_lock for analytics (if there was an active lock)
        if existing_lock and existing_lock.state not in ("COMPLETED", "FAILED", "NONE"):
            from coach_state.focus_lock_service import create_cycle_log
            cycle_log = create_cycle_log(user.user_id, existing_lock)
            await db.focus_lock_analytics.insert_one(cycle_log.to_dict())
            logger.info(f"[FOCUS LOCK ANALYTICS] Logged quit: user={user.user_id}, "
                        f"games_completed={existing_lock.games_completed}/{existing_lock.games_required}")
        
        logger.info(f"Focus lock deactivated for user {user.user_id}")
        return {"status": "deactivated"}
    else:
        return {"status": "no_lock_found"}


# =============================================================================
# THEORY MODULE ENDPOINTS (Step 10)
# =============================================================================

@api_router.get("/coach/module/{game_id}")
async def get_game_module(
    game_id: str,
    user: User = Depends(get_current_user)
):
    """
    Get the theory module trigger for a specific game (Step 10).
    
    Returns the detected module, rule, and evidence for the Lab page.
    
    Response schema:
    {
        "triggered": true,
        "module_key": "SIMPLIFY_WHEN_AHEAD",
        "module_name": "Simplify When Ahead",
        "category": "conversion",
        "rule": "Trade pieces, reduce counterplay.",
        "explanation": "...",
        "evidence_move": 23,
        "evidence_cp_loss": 388,
        "confidence": "high"
    }
    """
    # Get game analysis with module trigger
    analysis = await db.game_analyses.find_one(
        {"game_id": game_id, "user_id": user.user_id},
        {"_id": 0, "module_trigger": 1}
    )
    
    if not analysis or not analysis.get("module_trigger"):
        return {"triggered": False}
    
    return analysis.get("module_trigger")


@api_router.get("/coach/modules/stats")
async def get_module_stats(
    user: User = Depends(get_current_user)
):
    """
    Get module injection statistics for the user (Step 10).
    
    Returns aggregate stats on which modules have been triggered.
    """
    injections = await db.module_injections.find(
        {"user_id": user.user_id},
        {"_id": 0}
    ).to_list(100)
    
    stats = get_module_injection_stats(injections)
    return stats


@api_router.get("/coach/modules/all")
async def get_all_modules():
    """
    Get all available theory modules (Step 10).
    
    Returns the full list of 30 modules with their rules.
    """
    return {
        "count": len(ALL_MODULES),
        "modules": [m.to_dict() for m in ALL_MODULES.values()]
    }


# ==================== PATTERN LEARNING API ====================
# Self-learning pattern recognition system for improving coach accuracy

@api_router.post("/coach/pattern-learning/feedback")
async def submit_pattern_feedback(
    request: Dict = Body(...),
    user: User = Depends(get_current_user)
):
    """
    Submit feedback when a coach explanation is wrong.
    
    This triggers the self-learning system to:
    1. Store the feedback
    2. Generate a corrected explanation immediately
    3. Learn a new classification rule for similar positions
    
    Body:
    - position_fen: FEN of the position before the move
    - move_played: The move that was played (UCI or SAN)
    - move_san: SAN notation of the move (optional)
    - system_classification: What the system classified it as (e.g., "MISSED_TRAP")
    - system_explanation: The explanation the system gave
    - correct_classification: What it actually was (e.g., "WALKED_INTO_FORK")
    - user_explanation: User's explanation of what went wrong (optional)
    - eval_before: Eval before move in centipawns (optional)
    - eval_after: Eval after move in centipawns (optional)
    - best_move: What Stockfish recommends (optional)
    - pv_after_played: Principal variation after the played move (optional)
    - game_id: Game ID for context (optional)
    - move_number: Move number (optional)
    - user_color: "white" or "black" (optional)
    
    Returns:
    - success: True if feedback was processed
    - feedback_id: ID of the stored feedback
    - corrected_explanation: The corrected explanation to show the user
    - pattern: The correct pattern classification
    - learning_status: "queued", "correction_exists", or "rule_generated"
    """
    from services.pattern_learning.auto_correction_service import get_auto_correction_service
    
    service = get_auto_correction_service()
    
    result = await service.submit_feedback_and_correct(
        user_id=user.user_id,
        position_fen=request.get("position_fen", ""),
        move_played=request.get("move_played", ""),
        system_classification=request.get("system_classification", ""),
        system_explanation=request.get("system_explanation", ""),
        correct_classification=request.get("correct_classification", ""),
        user_explanation=request.get("user_explanation", ""),
        move_san=request.get("move_san", ""),
        eval_before=request.get("eval_before", 0.0),
        eval_after=request.get("eval_after", 0.0),
        best_move=request.get("best_move", ""),
        pv_after_played=request.get("pv_after_played", []),
        game_id=request.get("game_id", ""),
        move_number=request.get("move_number", 0),
        user_color=request.get("user_color", "white")
    )
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to process feedback"))
    
    logger.info(f"Pattern feedback submitted: {result.get('feedback_id')} - {result.get('learning_status')}")
    
    return result


@api_router.get("/coach/pattern-learning/my-feedback")
async def get_my_feedback(user: User = Depends(get_current_user)):
    """
    Get the current user's submitted feedback with corrections.
    
    Returns:
    - List of feedback submissions with status and corrections
    """
    feedback_list = []
    
    # Get user's feedback
    cursor = db.pattern_feedback.find(
        {"user_id": user.user_id}
    ).sort("created_at", -1).limit(50)
    
    async for doc in cursor:
        feedback_id = doc.get("feedback_id")
        
        # Get corresponding correction if exists
        correction = await db.verified_corrections.find_one(
            {"feedback_id": feedback_id},
            {"_id": 0}
        )
        
        feedback_list.append({
            "feedback_id": feedback_id,
            "created_at": doc.get("created_at"),
            "status": doc.get("status", "pending"),
            "position_fen": doc.get("position_fen"),
            "move_played": doc.get("move_played"),
            "best_move": doc.get("best_move"),
            "move_number": doc.get("move_number"),
            "game_id": doc.get("game_id"),
            "section_type": doc.get("section_type"),
            "system_classification": doc.get("system_classification"),
            "system_explanation": doc.get("system_explanation"),
            "correct_classification": doc.get("correct_classification"),
            "user_explanation": doc.get("user_explanation"),
            "correction": correction
        })
    
    return {"feedback": feedback_list, "count": len(feedback_list)}


@api_router.get("/coach/pattern-learning/stats")
async def get_pattern_learning_stats(user: User = Depends(get_current_user)):
    """
    Get statistics about the pattern learning system.
    
    Returns:
    - feedback: Feedback statistics (pending, processed, total)
    - rules: Rule statistics (by status, total triggers, accuracy)
    - corrections: Correction statistics (by motif, usage counts)
    - loaded_rules: Currently active rules summary
    """
    from services.pattern_learning.auto_correction_service import get_auto_correction_service
    
    service = get_auto_correction_service()
    stats = await service.get_system_stats()
    
    return stats


@api_router.get("/coach/pattern-learning/pending-rules")
async def get_pending_rules(user: User = Depends(get_current_user)):
    """
    Get rules pending human review.
    
    Use this to review and approve/reject learned rules.
    """
    from services.pattern_learning.auto_correction_service import get_auto_correction_service
    
    service = get_auto_correction_service()
    rules = await service.get_pending_rules()
    
    return {
        "count": len(rules),
        "rules": rules
    }


@api_router.post("/coach/pattern-learning/approve-rule")
async def approve_learned_rule(
    request: Dict = Body(...),
    user: User = Depends(get_current_user)
):
    """
    Approve a pending learned rule.
    
    Body:
    - rule_id: The rule ID to approve
    """
    from services.pattern_learning.auto_correction_service import get_auto_correction_service
    
    rule_id = request.get("rule_id")
    if not rule_id:
        raise HTTPException(status_code=400, detail="rule_id is required")
    
    service = get_auto_correction_service()
    await service.approve_rule(rule_id, approved_by=user.user_id)
    
    logger.info(f"Rule {rule_id} approved by {user.user_id}")
    
    return {
        "success": True,
        "message": f"Rule {rule_id} approved and activated"
    }


@api_router.post("/coach/pattern-learning/reject-rule")
async def reject_learned_rule(
    request: Dict = Body(...),
    user: User = Depends(get_current_user)
):
    """
    Reject a pending learned rule.
    
    Body:
    - rule_id: The rule ID to reject
    - reason: Reason for rejection
    """
    from services.pattern_learning.auto_correction_service import get_auto_correction_service
    
    rule_id = request.get("rule_id")
    reason = request.get("reason", "Rejected by admin")
    
    if not rule_id:
        raise HTTPException(status_code=400, detail="rule_id is required")
    
    service = get_auto_correction_service()
    await service.reject_rule(rule_id, reason)
    
    logger.info(f"Rule {rule_id} rejected by {user.user_id}: {reason}")
    
    return {
        "success": True,
        "message": f"Rule {rule_id} rejected"
    }


@api_router.post("/coach/pattern-learning/classify")
async def classify_with_learned_rules(
    request: Dict = Body(...),
    user: User = Depends(get_current_user)
):
    """
    Classify a move using learned rules.
    
    Use this to check if learned rules provide better classification
    than the hardcoded classifier.
    
    Body:
    - position_fen: FEN before the move
    - move_played: The move that was played
    - pv_after_played: Principal variation after the move
    - eval_drop: Evaluation drop in pawns
    - best_move: What Stockfish recommends (optional)
    - user_color: "white" or "black" (optional)
    
    Returns:
    - classification: The classification result (if found)
    - has_learned_rule: Whether a learned rule matched
    """
    from services.pattern_learning.auto_correction_service import get_auto_correction_service
    
    service = get_auto_correction_service()
    
    result = await service.classify_with_learned_rules(
        position_fen=request.get("position_fen", ""),
        move_played=request.get("move_played", ""),
        pv_after_played=request.get("pv_after_played", []),
        eval_drop=request.get("eval_drop", 0.0),
        best_move=request.get("best_move"),
        user_color=request.get("user_color", "white")
    )
    
    if result:
        return {
            "has_learned_rule": True,
            "classification": {
                "pattern": result.pattern,
                "confidence": result.confidence,
                "explanation": result.explanation,
                "rule_id": result.rule_id,
                "matched_signals": result.matched_signals
            }
        }
    
    return {
        "has_learned_rule": False,
        "classification": None
    }


@api_router.post("/coach/pattern-learning/track-accuracy")
async def track_rule_accuracy(
    request: Dict = Body(...),
    user: User = Depends(get_current_user)
):
    """
    Track whether a learned rule classification was correct.
    
    Use this after showing a classification to the user to
    update the rule's accuracy statistics.
    
    Body:
    - rule_id: The rule that was used
    - was_correct: True if the classification was correct
    """
    from services.pattern_learning.auto_correction_service import get_auto_correction_service
    
    rule_id = request.get("rule_id")
    was_correct = request.get("was_correct", True)
    
    if not rule_id:
        raise HTTPException(status_code=400, detail="rule_id is required")
    
    service = get_auto_correction_service()
    await service.track_classification_feedback(rule_id, was_correct)
    
    return {
        "success": True,
        "message": "Accuracy tracked"
    }


# Include the router in the main app
# Include modular routers FIRST to take precedence
from routes import auth as auth_routes
from routes import feedback as feedback_routes
from routes import games as games_routes
from routes import lab as lab_routes
from routes import reflect as reflect_routes
from routes import training as training_routes
from routes import coach as coach_routes
from routes import coach_play as coach_play_routes
from routes import journey as journey_routes
from routes import cognitive as cognitive_routes
from routes import behavioral as behavioral_routes
from routes import notifications as notifications_routes
from routes import missions as missions_routes
from routes import settings as settings_routes
from routes import openings as openings_routes
from routes import admin_openings as admin_openings_routes
from routes import streak as streak_routes

# Set database references for modular routers
games_routes.set_db(db)
lab_routes.set_db(db)
lab_routes.set_llm(call_llm)
reflect_routes.set_db(db)
training_routes.set_db(db)
coach_routes.set_db(db)
coach_routes.set_llm(call_llm)
journey_routes.set_db(db)
journey_routes.set_sync_status(_sync_status, QUICK_SYNC_INTERVAL_SECONDS)
cognitive_routes.set_db(db)
behavioral_routes.set_db(db)
notifications_routes.set_db(db)
missions_routes.set_db(db)
missions_routes.set_mission_services(
    generate_daily_mission_fn=generate_daily_mission,
    start_mission_fn=start_mission,
    complete_mission_fn=complete_mission,
    extract_drill_positions_fn=extract_drill_positions,
    get_sample_drill_positions_fn=get_sample_drill_positions,
    pattern_focus_map=PATTERN_FOCUS_MAP,
    reward_event_type=RewardEventType,
    get_reward_message_fn=get_reward_message
)
settings_routes.set_db(db)
openings_routes.set_db(db)
openings_routes.set_llm(call_llm)
admin_openings_routes.set_db(db)
coach_play_routes.set_db(db)
coach_play_routes.set_llm(call_llm)
streak_routes.set_db(db)

app.include_router(auth_routes.router, prefix="/api")
app.include_router(feedback_routes.router, prefix="/api")
app.include_router(games_routes.router, prefix="/api")
app.include_router(lab_routes.router, prefix="/api")
app.include_router(reflect_routes.router, prefix="/api")
app.include_router(training_routes.router, prefix="/api")
app.include_router(coach_routes.router, prefix="/api")
app.include_router(journey_routes.router, prefix="/api")
app.include_router(cognitive_routes.router, prefix="/api")
app.include_router(behavioral_routes.router, prefix="/api")
app.include_router(notifications_routes.router, prefix="/api")
app.include_router(missions_routes.router, prefix="/api")
app.include_router(settings_routes.router, prefix="/api")
app.include_router(openings_routes.router, prefix="/api")
app.include_router(admin_openings_routes.router, prefix="/api")
app.include_router(coach_play_routes.router, prefix="/api")
app.include_router(streak_routes.router, prefix="/api")

# Then include the legacy api_router
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Note: Background sync scheduler and lifespan events are defined at the top of this file
