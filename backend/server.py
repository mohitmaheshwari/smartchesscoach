"""
Smart Chess Coach API — Main Application
=========================================

This is the app shell. All endpoint logic lives in routes/*.py files.
This file handles: app creation, database setup, background tasks, CORS, and route registration.
"""

from fastapi import FastAPI, APIRouter
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import asyncio
from pathlib import Path
from datetime import datetime, timezone, timedelta

# Import centralized config
from config import (
    BACKGROUND_SYNC_INTERVAL_SECONDS, QUICK_SYNC_INTERVAL_SECONDS
)

# Import journey service for background sync
from journey_service import run_background_sync

# Import LLM service
from llm_service import call_llm, call_tts, get_provider_mode

# Import helpers that need to be injected into mission routes
from helpers.drill_helpers import extract_drill_positions, get_sample_drill_positions

# Import mission services for injection
from mission_generation_service import (
    generate_daily_mission,
    start_mission,
    complete_mission as complete_mission_service,
    PATTERN_FOCUS_MAP,
)
from reflect_constants import RewardEventType
from reward_message_service import get_reward_message

# ==================== SETUP ====================

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# LLM Key
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY', '')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
logger.info(f"Using LLM provider: {get_provider_mode()}")

# ==================== BACKGROUND TASKS ====================

_background_sync_task = None
_quick_sync_task = None
_analysis_queue_fallback_task = None

_sync_lock = asyncio.Lock()
_sync_status = {
    "last_sync_at": None,
    "next_sync_at": None,
    "is_syncing": False,
    "games_found_last_sync": 0
}


async def background_sync_loop():
    """Periodic background task to sync games for all users (every 6 hours)."""
    while True:
        try:
            logger.info("Starting background game sync...")
            synced_count = await run_background_sync(db)
            logger.info(f"Background sync completed: {synced_count} games synced")
        except Exception as e:
            logger.error(f"Background sync error: {e}")
        await asyncio.sleep(BACKGROUND_SYNC_INTERVAL_SECONDS)


async def quick_sync_loop():
    """Real-time game monitoring — checks for new games every 5 minutes."""
    global _sync_status, _sync_lock
    from journey_service import sync_user_games

    async with _sync_lock:
        _sync_status["next_sync_at"] = (datetime.now(timezone.utc) + timedelta(seconds=60)).isoformat()
    await asyncio.sleep(60)

    while True:
        try:
            async with _sync_lock:
                _sync_status["is_syncing"] = True
                _sync_status["last_sync_at"] = datetime.now(timezone.utc).isoformat()
            logger.info("Quick sync: Checking for new games...")

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

        async with _sync_lock:
            _sync_status["next_sync_at"] = (datetime.now(timezone.utc) + timedelta(seconds=QUICK_SYNC_INTERVAL_SECONDS)).isoformat()

        await asyncio.sleep(QUICK_SYNC_INTERVAL_SECONDS)


def _run_analysis_queue_fallback_cycle():
    """Fallback queue processor — keeps queued games moving if dedicated worker is down."""
    from analysis_worker import claim_next_job, cleanup_stuck_jobs, ensure_stockfish_installed, get_database, process_job

    if not ensure_stockfish_installed():
        logger.error("Analysis queue fallback: Stockfish unavailable")
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


# ==================== LIFESPAN ====================

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _background_sync_task, _quick_sync_task, _analysis_queue_fallback_task

    _background_sync_task = asyncio.create_task(background_sync_loop())
    logger.info("Background sync scheduler started (6 hour interval)")

    _quick_sync_task = asyncio.create_task(quick_sync_loop())
    logger.info("Quick sync started (5 minute interval)")

    _analysis_queue_fallback_task = asyncio.create_task(analysis_queue_fallback_loop())
    logger.info("Analysis queue fallback processor started")

    yield

    for task in [_background_sync_task, _quick_sync_task, _analysis_queue_fallback_task]:
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    client.close()
    logger.info("Application shutdown complete")


# ==================== APP CREATION ====================

app = FastAPI(
    title="Smart Chess Coach API",
    description="AI-Powered Chess Learning Platform with Stockfish Analysis and Personalized Coaching",
    version="1.0.0",
    lifespan=lifespan,
)

api_router = APIRouter(prefix="/api")


# ==================== ROOT ROUTES ====================

@api_router.get("/")
async def root():
    return {"message": "Smart Chess Coach API", "status": "running"}

@api_router.get("/health")
async def health():
    return {"status": "healthy", "database": "connected"}


app.include_router(api_router)


# ==================== REGISTER ALL ROUTE MODULES ====================

# --- Existing route modules (already extracted) ---
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

# --- NEW route modules (extracted in this refactor) ---
from routes import voice as voice_routes
from routes import gamification as gamification_routes
from routes import admin as admin_routes
from routes import thinking as thinking_routes
from routes import home as home_routes
from routes import interactive as interactive_routes
from routes import analysis as analysis_routes
from routes import player as player_routes
from routes import training_advanced as training_advanced_routes
from routes import coach_advanced as coach_advanced_routes
from routes import oauth as oauth_routes
from routes import public_seo as public_seo_routes
from routes import billing as billing_routes
from routes import reviewer as reviewer_routes


# ==================== INJECT DEPENDENCIES ====================

# Existing modules
auth_routes.set_db(db)
feedback_routes.set_db(db)
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
    complete_mission_fn=complete_mission_service,
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

# New modules
voice_routes.set_db(db)
voice_routes.set_tts(call_tts)
gamification_routes.set_db(db)
admin_routes.set_db(db)
thinking_routes.set_db(db)
home_routes.set_db(db)
interactive_routes.set_db(db)
interactive_routes.set_llm(call_llm)
analysis_routes.set_db(db)
analysis_routes.set_llm(call_llm)
player_routes.set_db(db)
player_routes.set_llm(call_llm)
training_advanced_routes.set_db(db)
training_advanced_routes.set_llm(call_llm)
coach_advanced_routes.set_db(db)
oauth_routes.init_db(db)
coach_advanced_routes.set_llm(call_llm)
billing_routes.set_db(db)
reviewer_routes.set_db(db)


# ==================== REGISTER ROUTERS ====================

# Existing route modules
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

# New route modules
app.include_router(voice_routes.router, prefix="/api")
app.include_router(gamification_routes.router, prefix="/api")
app.include_router(admin_routes.router, prefix="/api")
app.include_router(thinking_routes.router, prefix="/api")
app.include_router(home_routes.router, prefix="/api")
app.include_router(interactive_routes.router, prefix="/api")
app.include_router(analysis_routes.router, prefix="/api")
app.include_router(player_routes.router, prefix="/api")
app.include_router(training_advanced_routes.router, prefix="/api")
app.include_router(coach_advanced_routes.router, prefix="/api")
app.include_router(oauth_routes.router, prefix="/api")
app.include_router(public_seo_routes.router, prefix="/api")
app.include_router(billing_routes.router, prefix="/api")
app.include_router(reviewer_routes.router, prefix="/api")


# ==================== CORS ====================

FRONTEND_URL = os.environ.get('FRONTEND_URL', 'https://chessguru.ai')

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
