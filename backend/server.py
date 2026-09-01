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

# Import coaching system initialization
from services.coaching_model import initialize_coaching_system

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


async def focus_outcome_loop():
    """2026-07-03: Runs daily to check every active focus whose locked_until
    has arrived. Fires check_focus_outcome → close_focus which writes
    resolution=improved/regressed/stuck to the focus doc. HomePage banners
    key off this."""
    from services.primary_weakness_picker import check_focus_outcome, close_focus, COLLECTION
    from datetime import datetime, timezone

    await asyncio.sleep(300)  # wait 5 min after startup before first pass
    while True:
        try:
            now = datetime.now(timezone.utc)
            now_iso = now.isoformat()
            n_processed = 0
            n_improved = 0
            n_regressed = 0
            n_stuck = 0
            async for f in db[COLLECTION].find({
                "type": "weakness", "status": "active",
                "$or": [
                    {"locked_until": {"$type": "date", "$lte": now}},
                    {"locked_until": {"$type": "string", "$lte": now_iso}},
                ],
            }):
                try:
                    outcome = await check_focus_outcome(db, f)
                    await close_focus(db, f, outcome)
                    if outcome.get("resolution") == "improved":
                        n_improved += 1
                    elif outcome.get("resolution") == "regressed":
                        n_regressed += 1
                    elif outcome.get("resolution") == "stuck":
                        n_stuck += 1
                    n_processed += 1
                except Exception as e:
                    logger.warning(f"focus_outcome_loop: error on {f.get('user_id')}: {e}")
            if n_processed:
                logger.info(
                    f"focus_outcome_loop: processed {n_processed} focuses "
                    f"(improved={n_improved} regressed={n_regressed} stuck={n_stuck})"
                )
        except Exception as e:
            logger.error(f"focus_outcome_loop error: {e}")
        # Run once every 6 hours
        await asyncio.sleep(6 * 3600)


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
        logger.debug("Analysis queue fallback: Stockfish unavailable locally (skipping background game analysis loop).")
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

async def daily_digest_loop():
    """Post-game digest emails (docs/activation_scope.md). Fires once per UTC
    day at DIGEST_SEND_HOUR_UTC (default 02:00 UTC = 07:30 IST), after the
    overnight sync/analysis has done its work. Mode via DIGEST_EMAILS_MODE
    (dry|pilot|live) read at send time — flip in .env, no rebuild."""
    import os as _os
    last_sent_date = None
    while True:
        try:
            now = datetime.now(timezone.utc)
            send_hour = int(_os.environ.get("DIGEST_SEND_HOUR_UTC", "2"))
            if now.hour == send_hour and last_sent_date != now.date():
                from services.digest_email_service import run_daily_digest
                result = await run_daily_digest(db)
                logger.info(f"[digest] daily run: {result}")

                # Diagnostic pool health check (2026-08-05 residency review):
                # the diagnostic silently degrades to a lower-quality legacy
                # fallback if this ever drops below routes/diagnostic.py's
                # V2_POOL_MIN -- don't wait for a user to notice a broken
                # "Find the best move in undefined" screen.
                try:
                    from routes.diagnostic import V2_POOL_MIN
                    pool_count = await db.diagnostic_pool.count_documents({})
                    if pool_count < V2_POOL_MIN:
                        logger.error(
                            f"[HEALTH-CHECK] diagnostic_pool has {pool_count} docs, "
                            f"below V2_POOL_MIN={V2_POOL_MIN} -- diagnostic will "
                            f"silently fall back to the legacy, non-concept-aware "
                            f"flow. Re-run scripts/build_diagnostic_pool.py."
                        )
                except Exception as _pool_check_err:
                    logger.warning(f"[HEALTH-CHECK] diagnostic_pool check failed: {_pool_check_err}")

                last_sent_date = now.date()
        except Exception as e:
            logger.error(f"daily_digest_loop error: {e}")
        await asyncio.sleep(1200)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _background_sync_task, _quick_sync_task, _analysis_queue_fallback_task

    # Initialize coaching system (creates collections and seeds training plans)
    try:
        await initialize_coaching_system(db)
    except Exception as e:
        logger.error(f"Error initializing coaching system: {e}")

    try:
        from services.game_review_validation_service import ensure_validation_indexes
        await ensure_validation_indexes(db)
    except Exception as e:
        logger.error(f"Error initializing Game Review validation indexes: {e}")

    _background_sync_task = asyncio.create_task(background_sync_loop())
    logger.info("Background sync scheduler started (6 hour interval)")

    asyncio.create_task(daily_digest_loop())
    logger.info("Daily digest scheduler started (mode=%s)" % os.environ.get("DIGEST_EMAILS_MODE", "dry"))

    _quick_sync_task = asyncio.create_task(quick_sync_loop())
    logger.info("Quick sync started (5 minute interval)")

    _analysis_queue_fallback_task = asyncio.create_task(analysis_queue_fallback_loop())
    logger.info("Analysis queue fallback processor started")

    # 2026-07-03: Focus-outcome check runs every 6h to fire improved/regressed
    # resolutions so HomePage banners have live source of truth.
    _focus_outcome_task = asyncio.create_task(focus_outcome_loop())
    logger.info("Focus-outcome scheduler started (6 hour interval)")

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
    return {
        "status": "healthy",
        "database": "connected",
        # 2026-08-07: plumbed so verify_deployment.py's commit-match check
        # can confirm the deployed container is actually the commit we
        # think we shipped. "unknown" until the image is built with
        # --build-arg GIT_COMMIT=$(git rev-parse HEAD) — see Dockerfile.
        "git_commit": os.environ.get("GIT_COMMIT", "unknown"),
    }


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
from routes import daily_fix as daily_fix_routes
from routes import settings as settings_routes
from routes import openings as openings_routes
from routes import admin_openings as admin_openings_routes
from routes import streak as streak_routes

# --- NEW route modules (extracted in this refactor) ---
from routes import voice as voice_routes
from routes import gamification as gamification_routes
from routes import admin as admin_routes
from routes import move_evaluation as move_evaluation_routes
from routes import caption_authoring as caption_authoring_routes
from routes import thinking as thinking_routes
from routes import home as home_routes
from routes import interactive as interactive_routes
from routes import analysis as analysis_routes
from routes import player as player_routes
from routes import training_advanced as training_advanced_routes
from routes import coach_advanced as coach_advanced_routes
from routes import coaching as coaching_routes
from routes import coaching_patterns as coaching_patterns_routes
from routes import oauth as oauth_routes
from routes import public_seo as public_seo_routes
from routes import billing as billing_routes
from routes import reviewer as reviewer_routes
from routes import diagnostic as diagnostic_routes
from routes import behavior_study as behavior_study_routes


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
daily_fix_routes.set_db(db)
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
coach_advanced_routes.set_llm(call_llm)
coaching_routes.set_db(db)
coaching_patterns_routes.set_db(db)
oauth_routes.init_db(db)
billing_routes.set_db(db)
reviewer_routes.set_db(db)
diagnostic_routes.set_db(db)
behavior_study_routes.set_db(db)


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
app.include_router(daily_fix_routes.router, prefix="/api")
app.include_router(settings_routes.router, prefix="/api")
app.include_router(openings_routes.router, prefix="/api")
app.include_router(admin_openings_routes.router, prefix="/api")
app.include_router(coach_play_routes.router, prefix="/api")
app.include_router(streak_routes.router, prefix="/api")

# New route modules
app.include_router(voice_routes.router, prefix="/api")
app.include_router(gamification_routes.router, prefix="/api")
app.include_router(admin_routes.router, prefix="/api")
caption_authoring_routes.set_db(db)
app.include_router(caption_authoring_routes.router, prefix="/api")
app.include_router(thinking_routes.router, prefix="/api")
app.include_router(home_routes.router, prefix="/api")
app.include_router(interactive_routes.router, prefix="/api")
app.include_router(analysis_routes.router, prefix="/api")

# Move evaluation routes (Stockfish-based teaching captions)
move_evaluation_routes.set_db(db)
app.include_router(move_evaluation_routes.router, prefix="/api")
app.include_router(player_routes.router, prefix="/api")
app.include_router(training_advanced_routes.router, prefix="/api")
app.include_router(coach_advanced_routes.router, prefix="/api")
app.include_router(coaching_routes.router, prefix="/api")
app.include_router(oauth_routes.router, prefix="/api")
app.include_router(public_seo_routes.router, prefix="/api")
app.include_router(billing_routes.router, prefix="/api")
app.include_router(reviewer_routes.router, prefix="/api")
app.include_router(diagnostic_routes.router, prefix="/api")
app.include_router(behavior_study_routes.router, prefix="/api")
app.include_router(coaching_patterns_routes.router, prefix="/api")


# ==================== CORS ====================

FRONTEND_URL = os.environ.get('FRONTEND_URL', 'https://chessguru.ai')

ALLOWED_ORIGINS = [
    FRONTEND_URL,
    "https://chessguru.ai",
    "https://www.chessguru.ai",
    "http://localhost:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:3001",
]

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
