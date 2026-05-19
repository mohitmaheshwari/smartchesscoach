"""
Analysis Worker - Separate Process for Stockfish Analysis

This worker runs independently from the web server and processes
game analysis jobs from the MongoDB queue.

Architecture:
┌──────────────┐       ┌──────────────┐       ┌──────────────┐
│  Web Server  │──────▶│  MongoDB     │──────▶│   Worker     │
│  (fast API)  │ queue │  (queue)     │ poll  │  (Stockfish) │
└──────────────┘       └──────────────┘       └──────────────┘

Benefits:
- Web server never blocks on Stockfish
- Can run multiple workers for parallelism
- Scales independently from web traffic
- Failed analyses don't crash the web server

Usage:
    python analysis_worker.py

Environment:
    MONGO_URL - MongoDB connection string
    DB_NAME - Database name
"""

import os
import sys
import time
import signal
import logging
import traceback
from datetime import datetime, timezone, timedelta
from pymongo import MongoClient
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from stockfish_service import analyze_game_with_stockfish
from services.trap_scanner import scan_pgn_for_traps, TRAP_SCANNER_VERSION
from services.user_opening_profile import (
    compute_opening_profile, persist_opening_profile,
)
from config import STOCKFISH_DEPTH
from analysis.intent_recognition_service import recognize_intent, get_game_phase
from analysis.intent_quality_calibrator import calibrate_with_forcing_context, build_full_intent_explanation

# Focus Lock compliance (Step 9)
from coach_state.focus_lock_service import (
    calculate_compliance,
    update_lock_after_game,
    calculate_compliance_trend,
    focus_lock_from_db,
    focus_lock_to_db,
    should_trigger_deep_session,
    create_cycle_log,
    create_focus_lock,
)

# Module Trigger Service (Step 10)
from coach_state.module_trigger_service import (
    detect_module_for_game,
    check_auto_lock_condition,
    create_injection_record,
    get_focus_lock_lesson_for_module,
)

# Configure logging with more detail
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(funcName)s:%(lineno)d] %(message)s'
)
logger = logging.getLogger('analysis_worker')

# Configuration
POLL_INTERVAL = 2  # Seconds between queue checks
MAX_RETRIES = 3    # Max retries for failed analysis
WORKER_ID = f"worker-{os.getpid()}"
JOB_TIMEOUT_MINUTES = 10
HEARTBEAT_INTERVAL = 30  # Seconds between heartbeat updates

# Graceful shutdown flag
shutdown_requested = False
last_heartbeat = time.time()


def _queue_error_payload(message: str) -> dict:
    now = datetime.now(timezone.utc)
    return {
        "last_error": message[:500],
        "last_error_at": now,
        "updated_at": now,
    }


def calculate_turning_point_sync(move_evals, user_color, user_rating):
    """
    Calculate the true turning point of the game.
    
    Logic: Find the move with LARGEST EVAL DROP where opponent played accurately after.
    This identifies "the move that lost the game" rather than frustration blunders.
    """
    if not move_evals:
        return None
    
    def user_eval(eval_val, color):
        """Convert eval to user's perspective"""
        if eval_val is None:
            return 0
        return eval_val if color == "white" else -eval_val
    
    def is_user_move(move_num, user_clr):
        """Check if this move number belongs to user"""
        if user_clr == "white":
            return move_num % 2 == 1
        return move_num % 2 == 0
    
    turning_point_candidates = []
    
    for i, m in enumerate(move_evals):
        move_num = m.get("move_number", i + 1)
        
        if not is_user_move(move_num, user_color):
            continue
        
        eval_before = user_eval(m.get("eval_before"), user_color)
        eval_after = user_eval(m.get("eval_after"), user_color)
        cp_loss = abs(m.get("cp_loss", 0))
        eval_drop = eval_before - eval_after
        
        if cp_loss < 150:
            continue
        
        remaining_moves = move_evals[i + 1:]
        if not remaining_moves:
            continue
        
        # Check opponent's play in next 5 moves
        opponent_moves_checked = 0
        opponent_mistakes_immediate = 0
        max_user_recovery = eval_after
        
        for future_m in remaining_moves:
            future_move_num = future_m.get("move_number", 0)
            future_cp_loss = abs(future_m.get("cp_loss", 0))
            future_eval = user_eval(future_m.get("eval_after"), user_color)
            
            if future_eval > max_user_recovery:
                max_user_recovery = future_eval
            
            if not is_user_move(future_move_num, user_color):
                opponent_moves_checked += 1
                if future_cp_loss >= 100:
                    opponent_mistakes_immediate += 1
                if opponent_moves_checked >= 5:
                    break
        
        never_recovered = max_user_recovery < -150
        opponent_played_well_after = opponent_mistakes_immediate <= 1
        
        if never_recovered and opponent_played_well_after:
            # Categorize the turning point
            threat = m.get("threat", "")
            threat_lower = threat.lower() if threat else ""
            
            # Determine category
            category = "positional_mistake"
            category_label = "Positional Mistake"
            pattern_name = "Strategic Error"
            
            if "fork" in threat_lower:
                category, category_label, pattern_name = "tactical_blindness", "Tactical Blindness", "Fork"
            elif "pin" in threat_lower:
                category, category_label, pattern_name = "tactical_blindness", "Tactical Blindness", "Pin"
            elif "battery" in threat_lower or ("queen" in threat_lower and "bishop" in threat_lower):
                category, category_label, pattern_name = "piece_coordination", "Piece Coordination", "Queen + Bishop Battery"
            elif "mate" in threat_lower or "checkmate" in threat_lower:
                category, category_label, pattern_name = "king_safety", "King Safety Neglect", "Mate Threat"
            elif "hanging" in threat_lower or "undefended" in threat_lower:
                category, category_label, pattern_name = "one_move_blunder", "One-Move Blunder", "Hanging Piece"
            elif "back rank" in threat_lower:
                category, category_label, pattern_name = "king_safety", "King Safety Neglect", "Back Rank Weakness"
            elif cp_loss >= 400:
                category, category_label, pattern_name = "one_move_blunder", "One-Move Blunder", "Major Oversight"
            
            turning_point_candidates.append({
                "move_number": move_num,
                "move": m.get("move"),
                "best_move": m.get("best_move"),
                "eval_before": m.get("eval_before"),
                "eval_after": m.get("eval_after"),
                "cp_loss": cp_loss,
                "eval_drop": eval_drop,
                "fen_before": m.get("fen_before"),
                "threat": threat,
                "category": category,
                "category_label": category_label,
                "pattern_name": pattern_name,
                "training_focus": {
                    "tactical_blindness": "tactics",
                    "threat_ignorance": "threat_awareness",
                    "piece_coordination": "piece_coordination",
                    "king_safety": "king_safety",
                    "one_move_blunder": "blunder_check",
                    "positional_mistake": "positional"
                }.get(category, "general")
            })
    
    if turning_point_candidates:
        return max(turning_point_candidates, key=lambda x: x["eval_drop"])
    
    return None


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    global shutdown_requested
    logger.info(f"Received signal {signum}, shutting down gracefully...")
    shutdown_requested = True


def ensure_stockfish_installed():
    """
    Check if Stockfish is installed, and install it if not.
    Returns True if Stockfish is available, False otherwise.
    """
    from config import STOCKFISH_PATH
    
    # Check if stockfish exists at configured path
    if os.path.exists(STOCKFISH_PATH):
        logger.info(f"Stockfish found at {STOCKFISH_PATH}")
        return True
    
    # Also check via 'which' command
    try:
        import subprocess
        result = subprocess.run(['which', 'stockfish'], capture_output=True, text=True)
        if result.returncode == 0:
            found_path = result.stdout.strip()
            logger.info(f"Stockfish found at {found_path}")
            return True
    except Exception as e:
        logger.warning(f"Could not run 'which stockfish': {e}")
    
    # Stockfish not found - try to install it
    logger.warning("Stockfish not found. Attempting to install...")
    
    try:
        import subprocess
        
        # Update apt and install stockfish
        logger.info("Running: apt-get update && apt-get install -y stockfish")
        result = subprocess.run(
            ['sudo', 'apt-get', 'update'],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode != 0:
            logger.error(f"apt-get update failed: {result.stderr}")
            return False
        
        result = subprocess.run(
            ['sudo', 'apt-get', 'install', '-y', 'stockfish'],
            capture_output=True,
            text=True,
            timeout=120
        )
        
        if result.returncode == 0:
            logger.info("Stockfish installed successfully!")
            return True
        else:
            logger.error(f"Failed to install Stockfish: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        logger.error("Timeout while installing Stockfish")
        return False
    except Exception as e:
        logger.error(f"Error installing Stockfish: {e}")
        return False


def cleanup_stuck_jobs(db):
    """
    Find and reset jobs that have been stuck in 'processing' state for too long.
    This handles cases where the worker crashed mid-analysis.
    """
    timeout_threshold = datetime.now(timezone.utc) - timedelta(minutes=JOB_TIMEOUT_MINUTES)
    
    # Find stuck jobs
    stuck_jobs = db.analysis_queue.find({
        "status": "processing",
        "$or": [
            {"last_heartbeat": {"$lt": timeout_threshold}},
            {
                "last_heartbeat": {"$exists": False},
                "started_at": {"$lt": timeout_threshold}
            }
        ]
    })
    
    stuck_count = 0
    for job in stuck_jobs:
        game_id = job.get("game_id")
        started_at = job.get("started_at")
        retry_count = job.get("retry_count", 0)
        worker_id = job.get("worker_id", "unknown")
        
        logger.warning(f"Found stuck job: {game_id} (worker: {worker_id}, started: {started_at}, retries: {retry_count})")
        
        if retry_count >= MAX_RETRIES:
            # Mark as permanently failed
            db.analysis_queue.update_one(
                {"game_id": game_id},
                {
                    "$set": {
                        "status": "failed",
                        "failed_at": datetime.now(timezone.utc),
                        "failure_reason": "retry_exhausted_timeout",
                        "retrying": False,
                        **_queue_error_payload(
                            f"Timed out after {JOB_TIMEOUT_MINUTES} minutes while processing (max retries exceeded)"
                        )
                    }
                }
            )
            db.games.update_one(
                {"game_id": game_id},
                {"$set": {
                    "analysis_status": "failed",
                    "analysis_error": f"Timed out after {JOB_TIMEOUT_MINUTES} minutes while processing"
                }}
            )
            logger.error(f"Job {game_id} permanently failed after {MAX_RETRIES} retries")
        else:
            # Reset to pending for retry
            db.analysis_queue.update_one(
                {"game_id": game_id},
                {
                    "$set": {
                        "status": "pending",
                        "started_at": None,
                        "last_heartbeat": None,
                        "worker_id": None,
                        "last_reset_at": datetime.now(timezone.utc),
                        "reset_reason": f"Timeout after {JOB_TIMEOUT_MINUTES} min (attempt {retry_count + 1})",
                        "retrying": True,
                        "last_retry_at": datetime.now(timezone.utc),
                        **_queue_error_payload(
                            f"Analysis worker timed out after {JOB_TIMEOUT_MINUTES} minutes. Retrying attempt {retry_count + 1} of {MAX_RETRIES}."
                        )
                    },
                    "$inc": {"retry_count": 1}
                }
            )
            db.games.update_one(
                {"game_id": game_id},
                {"$set": {"analysis_status": "retrying", "analysis_error": None}}
            )
            logger.info(f"Reset stuck job {game_id} for retry (attempt {retry_count + 1}/{MAX_RETRIES})")
        
        stuck_count += 1
    
    if stuck_count > 0:
        logger.info(f"Cleaned up {stuck_count} stuck jobs")


def get_database():
    """Connect to MongoDB"""
    mongo_url = os.environ.get('MONGO_URL')
    db_name = os.environ.get('DB_NAME', 'chess_coach')
    
    if not mongo_url:
        raise ValueError("MONGO_URL environment variable not set")
    
    client = MongoClient(mongo_url)
    return client[db_name]


def update_job_heartbeat(db, game_id):
    """Update job heartbeat to indicate worker is still alive"""
    global last_heartbeat
    current_time = time.time()
    
    if current_time - last_heartbeat >= HEARTBEAT_INTERVAL:
        db.analysis_queue.update_one(
            {"game_id": game_id, "status": "processing"},
            {"$set": {
                "last_heartbeat": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            }}
        )
        last_heartbeat = current_time
        logger.debug(f"Updated heartbeat for {game_id}")


def claim_next_job(db):
    """
    Atomically claim the next pending job from the queue.
    Uses findOneAndUpdate to prevent race conditions with multiple workers.
    
    Returns:
        The job document if found, None otherwise
    """
    job = db.analysis_queue.find_one_and_update(
        {
            "status": "pending",
            # Optional: Add retry logic for failed jobs
            "$or": [
                {"retry_count": {"$exists": False}},
                {"retry_count": {"$lt": MAX_RETRIES}}
            ]
        },
        {
            "$set": {
                "status": "processing",
                "worker_id": WORKER_ID,
                "started_at": datetime.now(timezone.utc),
                "last_heartbeat": datetime.now(timezone.utc),
                "retrying": False,
                "updated_at": datetime.now(timezone.utc)
            }
        },
        sort=[("queued_at", 1)],  # FIFO - oldest first
        return_document=True
    )
    return job


def update_player_profile_sync(db, user_id: str, game_id: str, blunders: int, mistakes: int, best_moves: int, move_evaluations: list):
    """
    Synchronous version of profile update for the analysis worker.
    Updates player stats and recalculates top weaknesses.
    """
    try:
        current_time = datetime.now(timezone.utc)
        
        profile = db.player_profiles.find_one({"user_id": user_id})
        if not profile:
            logger.warning(f"No profile found for user {user_id} - skipping profile update")
            return
        
        # Update game counts
        games_analyzed = profile.get("games_analyzed_count", 0) + 1
        total_blunders = profile.get("total_blunders", 0) + blunders
        total_mistakes = profile.get("total_mistakes", 0) + mistakes
        total_best_moves = profile.get("total_best_moves", 0) + best_moves
        
        # Extract weaknesses from move evaluations (only actual blunders)
        identified_weaknesses = []
        for m in move_evaluations:
            eval_type = m.get("evaluation")
            cp_loss = m.get("cp_loss", 0)
            
            # Only count actual blunders as one-move blunders (not mistakes or inaccuracies)
            if eval_type == "blunder" and 150 <= cp_loss <= 600:
                identified_weaknesses.append({
                    "category": "tactical",
                    "subcategory": "one_move_blunder"
                })
            elif eval_type == "blunder" and cp_loss > 600:
                identified_weaknesses.append({
                    "category": "tactical", 
                    "subcategory": "complex_tactical_miss"
                })
        
        # Update weakness tracking
        current_weaknesses = profile.get("top_weaknesses", [])
        
        # Count new weaknesses
        weakness_counts = {}
        for w in identified_weaknesses:
            key = f"{w['category']}:{w['subcategory']}"
            weakness_counts[key] = weakness_counts.get(key, 0) + 1
        
        # Update existing weaknesses or add new ones
        for key, count in weakness_counts.items():
            category, subcategory = key.split(":")
            found = False
            for w in current_weaknesses:
                if w.get("category") == category and w.get("subcategory") == subcategory:
                    w["occurrence_count"] = w.get("occurrence_count", 0) + count
                    w["last_occurrence"] = current_time.isoformat()
                    # Recalculate decayed score
                    w["decayed_score"] = round(w["occurrence_count"] * 1.0, 2)  # Simple score for now
                    found = True
                    break
            
            if not found:
                current_weaknesses.append({
                    "category": category,
                    "subcategory": subcategory,
                    "occurrence_count": count,
                    "first_occurrence": current_time.isoformat(),
                    "last_occurrence": current_time.isoformat(),
                    "decayed_score": round(count * 1.0, 2)
                })
        
        # Sort by decayed score
        current_weaknesses.sort(key=lambda x: x.get("decayed_score", 0), reverse=True)
        
        # Keep top 10
        top_weaknesses = current_weaknesses[:10]
        
        # Update profile
        db.player_profiles.update_one(
            {"user_id": user_id},
            {"$set": {
                "games_analyzed_count": games_analyzed,
                "total_blunders": total_blunders,
                "total_mistakes": total_mistakes,
                "total_best_moves": total_best_moves,
                "top_weaknesses": top_weaknesses,
                "last_updated": current_time.isoformat()
            }}
        )
        
        logger.info(f"Updated profile for {user_id}: {games_analyzed} games, {len(identified_weaknesses)} new weaknesses tracked")
        
    except Exception as e:
        logger.error(f"Failed to update profile for {user_id}: {e}")


def update_player_identity_sync(db, user_id: str, game_result: str, moves_analysis: list, rating_after: int = None):
    """
    Synchronous version of PlayerIdentity update for the analysis worker.
    Updates the player identity document which powers the Deep Memory / Coach Memory tab.
    
    NOTE: Uses 'player_identities' collection (plural) to match PlayerIdentityService.COLLECTION
    """
    try:
        from services.player_identity import BlunderType, GamePhase as IdentityGamePhase
        
        current_time = datetime.now(timezone.utc)
        
        # Use player_identities (plural) - this is what PlayerIdentityService uses
        COLLECTION = "player_identities"
        
        # Get or create identity document
        identity = db[COLLECTION].find_one({"user_id": user_id})
        
        if not identity:
            # Create new identity
            identity = {
                "user_id": user_id,
                "games_analyzed": 0,
                "total_wins": 0,
                "total_losses": 0,
                "total_draws": 0,
                "consecutive_wins": 0,
                "consecutive_losses": 0,
                "current_rating": rating_after or 1200,
                "peak_rating": rating_after or 1200,
                "style_profile": {
                    "primary_style": "developing",
                    "confidence": 0.0,
                    "tactical_tendency": 0.5,
                    "positional_tendency": 0.5,
                    "aggressive_tendency": 0.5,
                    "defensive_tendency": 0.5
                },
                "blunder_taxonomy": {
                    "by_type": {},
                    "by_phase": {},
                    "most_common_type": None,
                    "worst_phase": None,
                    "trend": "unknown"
                },
                "created_at": current_time.isoformat(),
                "updated_at": current_time.isoformat()
            }
            db[COLLECTION].insert_one(identity)
        
        # Update basic stats
        games_analyzed = identity.get("games_analyzed", 0) + 1
        
        # Update win/loss/draw counts
        total_wins = identity.get("total_wins", 0)
        total_losses = identity.get("total_losses", 0)
        total_draws = identity.get("total_draws", 0)
        consecutive_wins = identity.get("consecutive_wins", 0)
        consecutive_losses = identity.get("consecutive_losses", 0)
        
        if game_result == "win" or "1-0" in game_result:
            total_wins += 1
            consecutive_wins += 1
            consecutive_losses = 0
        elif game_result == "loss" or "0-1" in game_result:
            total_losses += 1
            consecutive_losses += 1
            consecutive_wins = 0
        else:
            total_draws += 1
            consecutive_wins = 0
            consecutive_losses = 0
        
        # Analyze blunders
        blunder_by_type = identity.get("blunder_taxonomy", {}).get("by_type", {})
        blunder_by_phase = identity.get("blunder_taxonomy", {}).get("by_phase", {})
        
        for move in moves_analysis:
            cp_loss = move.get("cp_loss", 0)
            if cp_loss >= 100:  # Mistake or blunder
                # Classify phase
                move_num = move.get("move_number", 1)
                if move_num <= 12:
                    phase = "opening"
                elif move_num <= 30:
                    phase = "middlegame"
                else:
                    phase = "endgame"
                
                blunder_by_phase[phase] = blunder_by_phase.get(phase, 0) + 1
                
                # Classify type based on cp_loss
                if cp_loss >= 300:
                    blunder_type = "tactical_oversight"
                elif cp_loss >= 200:
                    blunder_type = "calculation_error"
                else:
                    blunder_type = "positional_error"
                
                blunder_by_type[blunder_type] = blunder_by_type.get(blunder_type, 0) + 1
        
        # Find most common blunder type and worst phase
        most_common_type = max(blunder_by_type.keys(), key=lambda k: blunder_by_type[k]) if blunder_by_type else None
        worst_phase = max(blunder_by_phase.keys(), key=lambda k: blunder_by_phase[k]) if blunder_by_phase else None
        
        # Update rating
        current_rating = identity.get("current_rating", 1200)
        peak_rating = identity.get("peak_rating", 1200)
        if rating_after:
            current_rating = rating_after
            if rating_after > peak_rating:
                peak_rating = rating_after
        
        # Calculate style confidence based on games analyzed
        style_confidence = min(0.9, games_analyzed / 50)
        
        # Update the document
        db[COLLECTION].update_one(
            {"user_id": user_id},
            {"$set": {
                "games_analyzed": games_analyzed,
                "total_wins": total_wins,
                "total_losses": total_losses,
                "total_draws": total_draws,
                "consecutive_wins": consecutive_wins,
                "consecutive_losses": consecutive_losses,
                "current_rating": current_rating,
                "peak_rating": peak_rating,
                "style_profile.confidence": style_confidence,
                "blunder_taxonomy.by_type": blunder_by_type,
                "blunder_taxonomy.by_phase": blunder_by_phase,
                "blunder_taxonomy.most_common_type": most_common_type,
                "blunder_taxonomy.worst_phase": worst_phase,
                "updated_at": current_time.isoformat()
            }}
        )
        
        logger.info(f"[IDENTITY] Updated player identity for {user_id}: {games_analyzed} games, {consecutive_losses} consecutive losses")
        
    except Exception as e:
        logger.error(f"[IDENTITY] Failed to update identity for {user_id}: {e}")
        traceback.print_exc()


def process_job(db, job):
    """
    Process a single analysis job.
    
    Args:
        db: MongoDB database connection
        job: The job document from analysis_queue
    
    Returns:
        True if successful, False otherwise
    """
    game_id = job.get("game_id")
    user_id = job.get("user_id")
    retry_count = job.get("retry_count", 0)
    
    logger.info(f"[START] Processing game {game_id} for user {user_id} (attempt {retry_count + 1}/{MAX_RETRIES})")
    
    try:
        # Get the game data
        game = db.games.find_one({"game_id": game_id})
        
        if not game:
            logger.error(f"[ERROR] Game {game_id} not found in database")
            mark_job_failed(db, game_id, "Game not found")
            return False
        
        pgn = game.get("pgn")
        if not pgn:
            logger.error(f"[ERROR] Game {game_id} has no PGN data")
            mark_job_failed(db, game_id, "No PGN data")
            return False
        
        user_color = game.get("user_color", "white")
        
        # Get user's rating for this game (used for module detection)
        if user_color == "white":
            user_rating = game.get("white_rating") or game.get("white", {}).get("rating", 1200)
        else:
            user_rating = game.get("black_rating") or game.get("black", {}).get("rating", 1200)
        user_rating = int(user_rating) if user_rating else 1200
        
        # Update game status to show it's being processed
        db.games.update_one(
            {"game_id": game_id},
            {"$set": {"analysis_status": "processing", "analysis_error": None}}
        )
        
        # Run Stockfish analysis (this is the slow part!)
        logger.info(f"[STOCKFISH] Starting analysis for {game_id} (depth={STOCKFISH_DEPTH})...")
        start_time = time.time()
        
        try:
            stockfish_result = analyze_game_with_stockfish(
                pgn,
                user_color=user_color,
                depth=STOCKFISH_DEPTH
            )
        except Exception as sf_error:
            logger.error(f"[STOCKFISH ERROR] {game_id}: {sf_error}")
            logger.error(traceback.format_exc())
            mark_job_failed(db, game_id, f"Stockfish error: {str(sf_error)[:200]}")
            return False
        
        elapsed = time.time() - start_time
        logger.info(f"[STOCKFISH] Completed for {game_id} in {elapsed:.1f}s")
        
        # Update heartbeat after long operation
        update_job_heartbeat(db, game_id)
        
        if not stockfish_result or not stockfish_result.get("success"):
            error_msg = stockfish_result.get("error", "Unknown error") if stockfish_result else "Analysis returned None"
            logger.error(f"[VALIDATION] Stockfish analysis failed for {game_id}: {error_msg}")
            mark_job_failed(db, game_id, error_msg)
            return False
        
        # Extract stats
        sf_stats = stockfish_result.get("user_stats", {})
        move_evaluations = stockfish_result.get("moves", [])
        
        # VALIDATION: Ensure analysis is complete and valid
        accuracy = sf_stats.get("accuracy", 0)
        total_moves = len(move_evaluations)
        blunders = sf_stats.get("blunders", 0)
        mistakes = sf_stats.get("mistakes", 0)
        best_moves = sf_stats.get("best_moves", 0)
        
        # Check if analysis appears valid
        is_valid_analysis = True
        validation_error = None
        
        if total_moves < 5:
            is_valid_analysis = False
            validation_error = f"Too few moves analyzed ({total_moves})"
        elif accuracy == 0 and blunders == 0 and mistakes == 0 and best_moves == 0:
            # All zeros is suspicious - likely failed analysis
            is_valid_analysis = False
            validation_error = "Analysis returned all zeros - likely incomplete"
        
        if not is_valid_analysis:
            logger.error(f"[VALIDATION] Failed for {game_id}: {validation_error}")
            mark_job_failed(db, game_id, validation_error)
            return False
        
        logger.info(f"[VALIDATION] Passed for {game_id}: {total_moves} moves, {accuracy}% accuracy, {blunders} blunders")
        
        # =========================================================================
        # PHASE 2: BEHAVIORAL INTERPRETATION (NEW)
        # Run AFTER Stockfish to identify coaching-relevant patterns
        # =========================================================================
        logger.info(f"[INTERPRET] Starting behavioral interpretation for {game_id}...")
        
        try:
            from analysis_interpreter import interpret_game_analysis
            
            enriched_moves, interpretation_summary = interpret_game_analysis(
                move_evaluations,
                user_color=user_color
            )
            
            # Merge interpretation back into move evaluations
            for i, move in enumerate(move_evaluations):
                if i < len(enriched_moves):
                    enriched = enriched_moves[i]
                    move["cognitive_gap"] = enriched.get("cognitive_gap")
                    move["is_critical"] = enriched.get("is_critical", False)
                    move["critical_reason"] = enriched.get("critical_reason")
                    move["gap_confidence"] = enriched.get("gap_confidence", 0)
                    move["gap_evidence"] = enriched.get("gap_evidence", "")
                    move["coaching_focus"] = enriched.get("coaching_focus", "")
            
            critical_count = interpretation_summary.get("critical_moves", 0)
            primary_issue = interpretation_summary.get("primary_issue", "none")
            
            logger.info(f"[INTERPRET] Completed: {critical_count} critical moves, primary issue: {primary_issue}")
            
        except Exception as interp_error:
            # Non-fatal - continue without interpretation
            logger.warning(f"[INTERPRET] Failed (non-fatal): {interp_error}")
            interpretation_summary = {}
        
        # Update heartbeat after interpretation
        update_job_heartbeat(db, game_id)
        
        # =========================================================================
        # PHASE 3: INTENT RECOGNITION (Step 6 - Runtime integration, no DB persist)
        # Detects player intent and calibrates quality with human coach judgment
        # =========================================================================
        logger.info(f"[INTENT] Starting intent recognition for {game_id}...")
        
        try:
            import chess
            import json
            
            intent_enriched_count = 0
            for i, move_eval in enumerate(move_evaluations):
                # Only process user moves with errors (learning moments)
                if not move_eval.get("is_user_move", False):
                    continue
                
                # Skip moves without meaningful cp_loss
                cp_loss = move_eval.get("cp_loss", 0)
                if cp_loss < 30:  # Only process moves with some loss
                    continue
                
                fen_before = move_eval.get("fen_before", "")
                move_uci = move_eval.get("move_uci", "")
                best_move_uci = move_eval.get("engine_best_move", "")
                eval_before = move_eval.get("score_before", 0)
                eval_after = move_eval.get("score_after", 0)
                
                # Detect game phase
                try:
                    board = chess.Board(fen_before)
                    phase = get_game_phase(board)
                    
                    # Get piece type for special rules (e.g., queen early)
                    move = chess.Move.from_uci(move_uci) if move_uci else None
                    piece = board.piece_at(move.from_square) if move else None
                    piece_type = None
                    if piece:
                        piece_type = {
                            chess.PAWN: "pawn",
                            chess.KNIGHT: "knight",
                            chess.BISHOP: "bishop",
                            chess.ROOK: "rook",
                            chess.QUEEN: "queen",
                            chess.KING: "king"
                        }.get(piece.piece_type)
                except (ValueError, AttributeError):
                    phase = "middlegame"
                    piece_type = None
                
                # Get opponent PV for threat detection
                opponent_pv = None
                if i > 0:
                    prev_eval = move_evaluations[i - 1]
                    opponent_pv = prev_eval.get("engine_pv", [])
                
                # Step 1: Recognize intent (deterministic)
                intent_result = recognize_intent(
                    fen_before=fen_before,
                    move_uci=move_uci,
                    best_move_uci=best_move_uci,
                    eval_before=eval_before,
                    eval_after=eval_after,
                    player_color_str=user_color,
                    pv_after_best=opponent_pv,
                    cognitive_gap=move_eval.get("cognitive_gap")
                )
                
                # Step 2: Calibrate quality with human coach judgment
                calibrated = calibrate_with_forcing_context(
                    intent_type=intent_result.intent_type,
                    cp_loss=cp_loss,
                    eval_before=eval_before,
                    user_color=user_color,
                    phase=phase,
                    move_uci=move_uci,
                    best_move_uci=best_move_uci,
                    board_fen=fen_before
                )
                
                # Step 3: Build full explanation sentence
                intent_sentence = build_full_intent_explanation(
                    intent_description=intent_result.intent_description,
                    calibrated_quality=calibrated.calibrated_quality,
                    intent_type=intent_result.intent_type,
                    pressure=calibrated.pressure,
                    phase=phase,
                    piece_type=piece_type
                )
                
                # Attach intent fields to move evaluation (will be persisted with analysis doc)
                move_eval["intent_type"] = intent_result.intent_type
                move_eval["intent_confidence"] = intent_result.intent_confidence
                move_eval["intent_quality"] = calibrated.calibrated_quality
                move_eval["intent_description"] = intent_result.intent_description
                move_eval["intent_sentence"] = intent_sentence
                move_eval["intent_pressure"] = calibrated.pressure
                move_eval["intent_timing_score"] = calibrated.timing_score
                
                intent_enriched_count += 1
                
                # Log structured JSON for debugging (user's archetype testing)
                logger.info(f"[INTENT] Move {move_eval.get('move_number', i)}: " + json.dumps({
                    "move_uci": move_uci,
                    "cp_loss": cp_loss,
                    "phase": phase,
                    "piece_type": piece_type,
                    "intent_type": intent_result.intent_type,
                    "calibrated_quality": calibrated.calibrated_quality,
                    "pressure": calibrated.pressure,
                    "timing_score": calibrated.timing_score,
                    "intent_sentence": intent_sentence
                }))
            
            logger.info(f"[INTENT] Completed: {intent_enriched_count} moves enriched with intent recognition")
            
        except Exception as intent_error:
            # Non-fatal - continue without intent recognition
            logger.warning(f"[INTENT] Failed (non-fatal): {intent_error}")
            logger.exception("Intent recognition error details:")
        
        # Update heartbeat after intent recognition
        update_job_heartbeat(db, game_id)

        # =========================================================================
        # PHASE 4: CCT DISCIPLINE (Checks, Captures, Threats)
        # Tags every USER move with whether it was a forcing move,
        # whether forcing options were available, and whether the
        # engine's best was forcing. Aggregate goes on the game record
        # so coaching surfaces can reward forcing-move discipline as a
        # strength, not just penalize the missed killer.
        # =========================================================================
        cct_aggregate = {}
        held_initiative_summary = {"count": 0, "best_segment": None}
        held_initiative_segments = []
        try:
            from services.cct_detector import (
                tag_moves_with_cct,
                compute_cct_aggregate,
                detect_held_initiative_segments,
                summarize_held_initiative,
            )

            # Build best-move-by-ply list from the Stockfish output
            # (move_evaluations covers both sides; we want each ply).
            best_san_by_ply = []
            for me in move_evaluations:
                # move_evaluations may use 'best_move_san' or 'best_move' depending on path
                best_san_by_ply.append(
                    me.get("best_move_san") or me.get("best_move") or None
                )

            tagged_user_moves = tag_moves_with_cct(
                pgn, user_color=user_color, best_moves_san=best_san_by_ply
            )

            # Merge CCT tags back into move_evaluations matched by ply.
            # Tagged moves are user-only — pull them onto the right
            # entries in move_evaluations.
            tagged_by_ply = {t["ply"]: t for t in tagged_user_moves}
            for i, me in enumerate(move_evaluations):
                t = tagged_by_ply.get(i)
                if not t:
                    continue
                me["cct_is_check"] = t.get("is_check", False)
                me["cct_is_capture"] = t.get("is_capture", False)
                me["cct_creates_threat"] = t.get("creates_threat", False)
                me["cct_forcing"] = t.get("forcing", False)
                me["cct_had_forcing_options"] = t.get("had_forcing_options", False)
                me["cct_best_was_forcing"] = t.get("best_was_forcing", False)
                me["cct_played_forcing_when_best_was_forcing"] = t.get(
                    "played_forcing_when_best_was_forcing", False
                )

            cct_aggregate = compute_cct_aggregate(tagged_user_moves)

            # Phase 3: held-initiative-after-miss detection.
            # Surfaces moments where the user missed THE best forcing
            # move but kept the discipline and didn't collapse — the
            # pattern that today's analyzer treats only as a blunder.
            held_initiative_segments = detect_held_initiative_segments(
                tagged_user_moves, move_evaluations
            )
            held_initiative_summary = summarize_held_initiative(
                held_initiative_segments
            )

            logger.info(
                f"[CCT] {game_id}: score={cct_aggregate.get('cct_score')} "
                f"correct={cct_aggregate.get('cct_correct')}/"
                f"{cct_aggregate.get('cct_decisions')}, "
                f"max_streak={cct_aggregate.get('cct_max_streak')}, "
                f"held_initiative_segments={held_initiative_summary['count']}"
            )

        except Exception as cct_error:
            # Non-fatal — CCT tags are additive, no fallback needed
            logger.warning(f"[CCT] Failed (non-fatal): {cct_error}")

        # Update heartbeat after CCT pass
        update_job_heartbeat(db, game_id)

        # Create/update analysis record
        analysis_doc = {
            "game_id": game_id,
            "user_id": user_id,
            "stockfish_analysis": {
                "accuracy": sf_stats.get("accuracy", 0),
                "blunders": sf_stats.get("blunders", 0),
                "mistakes": sf_stats.get("mistakes", 0),
                "inaccuracies": sf_stats.get("inaccuracies", 0),
                "best_moves": sf_stats.get("best_moves", 0),
                "excellent_moves": sf_stats.get("excellent_moves", 0),
                "brilliant_moves": sf_stats.get("brilliant_moves", 0),
                "sacrifices": sf_stats.get("sacrifices", 0),
                "avg_cp_loss": sf_stats.get("avg_cp_loss", 0),
                "move_evaluations": move_evaluations
            },
            # NEW: Behavioral interpretation summary
            "interpretation": interpretation_summary if interpretation_summary else {},
            # NEW: CCT discipline aggregate (Checks/Captures/Threats).
            # Empty dict when computation failed; coaching surfaces
            # treat that as "no signal" and stay silent.
            "cct": cct_aggregate,
            # NEW: Held-initiative-after-miss segments. Each entry
            # names the missed-best ply, the missed move, and the
            # forcing-move window that followed. Used by game review
            # narrative to say "you missed Qh7 mate but kept giving
            # checks until Rxe1 landed" instead of just penalizing
            # the missed mate.
            "cct_held_initiative": held_initiative_summary,
            "cct_held_initiative_segments": held_initiative_segments,
            "analysis_depth": STOCKFISH_DEPTH,
            "analyzed_at": datetime.now(timezone.utc),
            "created_at": datetime.now(timezone.utc),
            "analysis_duration_seconds": elapsed,
            "worker_id": WORKER_ID,
            "engine_version": "P2.4"  # Step 6: Intent Recognition Layer
        }

        # Trap-library scan (41 named traps from data/traps.json).
        # SAN-prefix match → fire list classified by gold/celebration/lucky/
        # warning per [[surface-teaching-gold-proactively]]. Persisted as
        # trap_fires + trap_fires_version so Lab page / Pattern Training /
        # clickable-rule pages can read pre-computed fires without
        # re-running the scanner on every page load.
        # Cheap (~5-30ms per PGN), no Stockfish needed.
        try:
            analysis_doc["trap_fires"] = scan_pgn_for_traps(pgn, user_color)
            analysis_doc["trap_fires_version"] = TRAP_SCANNER_VERSION
        except Exception as trap_err:
            logger.warning(f"[traps] scan failed (non-fatal): {trap_err}")
            analysis_doc["trap_fires"] = []
            analysis_doc["trap_fires_version"] = TRAP_SCANNER_VERSION

        # V5 detector fires (Path A per worker-side-detector-migration —
        # only decryption_v5_data + version are written eagerly here;
        # the downstream pipeline cct/habits/truth_line continues to be
        # lazy-generated in routes/coach.py on first Lab/Reflect read).
        # Calls the existing async V5 service via a temporary motor
        # client so detector logic isn't duplicated. Slowest worker step
        # (~3-10s incl. LLM narrative) — runs after Stockfish + traps.
        try:
            import asyncio
            from motor.motor_asyncio import AsyncIOMotorClient
            from services.game_decryption_v5_service import (
                generate_game_decryption_v5, V5_COACHING_VERSION,
            )

            mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
            db_name = os.environ.get("DB_NAME", "chess_coach")

            async def _run_v5_for_new_game():
                async_client = AsyncIOMotorClient(mongo_url)
                async_db = async_client[db_name]
                try:
                    return await generate_game_decryption_v5(
                        pgn, user_color, move_evaluations, user_id, async_db
                    )
                finally:
                    async_client.close()

            v5_data = asyncio.run(_run_v5_for_new_game())
            if v5_data:
                analysis_doc["decryption_v5_data"] = v5_data
                analysis_doc["decryption_v5_version"] = V5_COACHING_VERSION
                analysis_doc["decryption_v5_generated_at"] = datetime.now(timezone.utc).isoformat()
                logger.info(f"[V5] Generated {len(v5_data)} move records for {game_id}")
            else:
                logger.warning(f"[V5] Empty result for {game_id} (non-fatal)")
        except Exception as v5_err:
            logger.warning(f"[V5] Generation failed (non-fatal, falls back to lazy regen on read): {v5_err}")
            # Don't set fields — leaves them absent, lazy regen will fill on first read

        # Upsert analysis (update if exists, insert if not)
        db.game_analyses.update_one(
            {"game_id": game_id, "user_id": user_id},
            {"$set": analysis_doc},
            upsert=True
        )

        # Per-user opening profile refresh (Phase-3 Component 1).
        # The newly-analyzed game is now in the corpus; recompute the
        # user's opening identity so Lab / Play-with-Coach / /openings
        # see the latest. Async + isolated client per the existing
        # worker pattern; cheap (~50-200ms total for typical users).
        try:
            import asyncio as _asyncio
            from motor.motor_asyncio import AsyncIOMotorClient as _AsyncMotor
            _mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
            _db_name = os.environ.get("DB_NAME", "chess_coach")

            async def _refresh_opening_profile():
                _client = _AsyncMotor(_mongo_url)
                _db = _client[_db_name]
                try:
                    _profile = await compute_opening_profile(_db, user_id)
                    await persist_opening_profile(_db, _profile)
                finally:
                    _client.close()

            _asyncio.run(_refresh_opening_profile())
            logger.info(f"[opening-profile] refreshed for {user_id}")
        except Exception as _op_err:
            logger.warning(f"[opening-profile] refresh failed (non-fatal): {_op_err}")

        # Update game status
        db.games.update_one(
            {"game_id": game_id},
            {"$set": {
                "is_analyzed": True,
                "analysis_status": "completed",
                "analyzed_at": datetime.now(timezone.utc)
            }}
        )
        
        # Mark job as completed
        db.analysis_queue.update_one(
            {"game_id": game_id},
            {"$set": {
                "status": "completed",
                "completed_at": datetime.now(timezone.utc),
                "duration_seconds": elapsed,
                "updated_at": datetime.now(timezone.utc),
                "retrying": False,
                "last_error": None,
                "last_error_at": None
            }}
        )
        
        # =========================================================================
        # TERMINATION-BASED WEAKNESS DETECTION
        # Timeout / abandonment losses are behavioral weaknesses, not chess ones
        # =========================================================================
        try:
            termination = game.get("termination", "unknown")
            game_result = game.get("result", "")
            user_lost = (game_result == "0-1" and user_color == "white") or (game_result == "1-0" and user_color == "black")

            if user_lost and termination in ("timeout", "abandonment"):
                termination_gap = "time_management" if termination == "timeout" else "game_abandonment"
                # Add as a game-level cognitive gap so the pattern tracking picks it up
                db.game_analyses.update_one(
                    {"game_id": game_id, "user_id": user_id},
                    {"$set": {
                        "termination_weakness": termination_gap,
                        "termination": termination,
                    }}
                )
                logger.info(f"[TERMINATION] {game_id}: {termination} loss → {termination_gap} weakness tagged")

                # Also inject into community_puzzles pattern tracking
                try:
                    from services.pattern_memory_service import record_pattern_occurrence
                    record_pattern_occurrence(db, user_id, termination_gap, game_id)
                except Exception:
                    pass
            else:
                # Store termination even for non-weakness cases (for display)
                db.game_analyses.update_one(
                    {"game_id": game_id, "user_id": user_id},
                    {"$set": {"termination": termination}}
                )
        except Exception as term_err:
            logger.warning(f"[TERMINATION] Failed: {term_err}")

        # Update player profile with new stats
        update_player_profile_sync(
            db, 
            user_id, 
            game_id,
            blunders,
            mistakes,
            best_moves,
            move_evaluations
        )
        
        # =========================================================================
        # PHASE 3.3b: UPDATE STRENGTH PROFILE
        # Tracks what user is GOOD at (tactics, calculation, positional, etc.)
        # =========================================================================
        try:
            from services.strength_profile_service import build_strength_profile_sync
            build_strength_profile_sync(db, user_id, max_games=30)
            logger.info(f"[STRENGTH] Updated strength profile for {user_id}")
        except Exception as strength_err:
            logger.warning(f"[STRENGTH] Failed to update (non-fatal): {strength_err}")

        # =========================================================================
        # PHASE 3.4: CALCULATE AND STORE TURNING POINT
        # For blind spots tracking on home page
        # =========================================================================
        try:
            turning_point = calculate_turning_point_sync(
                move_evaluations,
                user_color,
                game.get("white_rating") or game.get("black_rating") or 1200
            )
            if turning_point:
                db.game_analyses.update_one(
                    {"game_id": game_id, "user_id": user_id},
                    {"$set": {"turning_point": turning_point}}
                )
                logger.info(f"[TURNING_POINT] Stored turning point at move {turning_point.get('move_number')}")
        except Exception as tp_err:
            logger.warning(f"[TURNING_POINT] Failed to calculate: {tp_err}")
        
        # =========================================================================
        # PHASE 3.5: UPDATE PLAYER IDENTITY (DeepMemory)
        # This updates the PlayerIdentity document which powers the Memory tab
        # =========================================================================
        try:
            update_player_identity_sync(
                db,
                user_id,
                game_result=game.get("result", "unknown"),
                moves_analysis=move_evaluations,
                rating_after=user_rating
            )
        except Exception as identity_err:
            # Non-fatal - log but don't fail the analysis
            logger.warning(f"[IDENTITY] Failed to update player identity: {identity_err}")
        
        # =========================================================================
        # PHASE 4: FOCUS LOCK COMPLIANCE UPDATE (Step 9)
        # After game analysis + profile update, check for active focus lock
        # and update compliance state immediately (no async delay)
        # =========================================================================
        try:
            update_focus_lock_compliance(db, user_id, move_evaluations)
        except Exception as lock_err:
            # Non-fatal - log but don't fail the analysis
            logger.warning(f"[FOCUS LOCK] Failed to update compliance: {lock_err}")
        
        # =========================================================================
        # PHASE 5: MODULE TRIGGER DETECTION (Step 10)
        # Detect which theory module applies to this game
        # Auto-lock if 3+ triggers with high confidence
        # =========================================================================
        try:
            detect_and_inject_module(db, user_id, game_id, user_rating)
        except Exception as module_err:
            # Non-fatal - log but don't fail the analysis
            logger.warning(f"[MODULE TRIGGER] Failed to detect module: {module_err}")
        
        # =========================================================================
        # PHASE 5.5: CURRICULUM BRAIN — pick prescription from this game
        # This runs Engine 1 (fix your mess) on imported games too, not just
        # Play-with-Coach games. The prescription gets stored in coach_memory
        # so the home page and next session know what to focus on.
        # =========================================================================
        try:
            import asyncio
            from motor.motor_asyncio import AsyncIOMotorClient

            mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
            db_name = os.environ.get("DB_NAME", "chess_coach")

            async def _run_curriculum_for_imported_game():
                from services.coach_memory import (
                    get_or_create_memory, update_memory_after_game
                )
                from services.postgame_analysis import _pick_prescription

                async_client = AsyncIOMotorClient(mongo_url)
                async_db = async_client[db_name]
                try:
                    # Get coach memory + persistent weaknesses
                    memory = await get_or_create_memory(async_db, user_id)
                    current_focus = memory.learning.current_focus
                    persistent = []
                    for habit in memory.weaknesses:
                        if not habit.is_good and habit.detection_count >= 3:
                            persistent.append({
                                "habit_id": habit.habit_id,
                                "name": habit.name,
                                "detection_count": habit.detection_count,
                                "improving": habit.improving,
                            })
                    persistent.sort(key=lambda h: h["detection_count"], reverse=True)

                    # Build lightweight mistake objects from move_evaluations
                    # (enough for _pick_prescription keyword matching)
                    class _M:
                        def __init__(self, sev, cp, expl):
                            self.severity = sev
                            self.evaluation_change = -cp / 100.0 if cp else 0
                            self.explanation = expl or ""
                            self.mistake_type = None
                            self.tactical_pattern = None

                    mistakes_for_prescription = []
                    for mv in move_evaluations:
                        evaluation = (mv.get("evaluation") or "").lower()
                        if evaluation in ("blunder", "mistake", "inaccuracy"):
                            mistakes_for_prescription.append(_M(
                                evaluation,
                                mv.get("cp_loss", 0),
                                mv.get("explanation", "") or mv.get("reason", "")
                            ))

                    game_result_str = (game.get("result") or "").lower()
                    if game_result_str in ("1-0",):
                        result_for_brain = "win" if user_color == "white" else "loss"
                    elif game_result_str in ("0-1",):
                        result_for_brain = "win" if user_color == "black" else "loss"
                    else:
                        result_for_brain = "draw"

                    # Run the curriculum brain
                    prescription, ptype, preason = _pick_prescription(
                        mistakes=mistakes_for_prescription,
                        habit_violations=[],  # Imported games don't have HabitViolation objects
                        game_result=result_for_brain,
                        endgame_type=None,
                        endgame_lesson_needed=None,
                        user_rating=user_rating,
                        current_focus=current_focus,
                        phase_analysis=None,
                        opening_to_learn=None,
                        opening_played=None,
                        persistent_weaknesses=persistent,
                    )

                    if prescription:
                        logger.info(
                            f"[CURRICULUM] Imported game prescription: {prescription} "
                            f"({ptype}) — {preason}"
                        )
                        # Engine 2: distill mistake_types + was_winning from the evals
                        mt_list = [m.tactical_pattern for m in mistakes_for_prescription
                                   if getattr(m, "tactical_pattern", None)]
                        was_winning_flag = any(
                            (mv.get("evaluation_score", 0) or 0) > 150
                            for mv in move_evaluations
                        )
                        # Persist via update_memory_after_game
                        await update_memory_after_game(
                            db=async_db,
                            user_id=user_id,
                            game_result=result_for_brain,
                            accuracy=accuracy or 0,
                            blunders=blunders,
                            mistakes=mistakes,
                            habits_violated=[],
                            habits_improved=[],
                            opening_played=game.get("opening_name") or game.get("opening"),
                            endgame_reached=len(move_evaluations) > 80,
                            performance_rating=user_rating,
                            coach_prescription=prescription,
                            prescription_type=ptype,
                            mistake_types=mt_list,
                            was_winning=was_winning_flag,
                        )
                        # Bust the Lab cache so the new focus shows immediately
                        try:
                            await async_db.coaching_cache.delete_one({"user_id": user_id})
                        except Exception:
                            pass
                finally:
                    async_client.close()

            loop = asyncio.new_event_loop()
            loop.run_until_complete(_run_curriculum_for_imported_game())
            loop.close()
        except Exception as curr_err:
            logger.warning(f"[CURRICULUM] Failed on imported game (non-fatal): {curr_err}")

        # =========================================================================
        # PHASE 6: THINKING SCORE CALCULATION
        # Calculate and store thinking scores for this game
        # =========================================================================
        try:
            from services.thinking_score import calculate_game_thinking_scores
            
            # Build analysis dict for thinking score calculation
            analysis_for_score = {
                "game_id": game_id,
                "move_evaluations": move_evaluations,
                "critical_moments": []  # Will be populated from analysis if available
            }
            
            # Calculate thinking scores
            thinking_scores = calculate_game_thinking_scores(analysis_for_score, user_color)
            thinking_scores["user_id"] = user_id
            thinking_scores["game_id"] = game_id
            
            # Store thinking scores
            db.thinking_scores.update_one(
                {"user_id": user_id, "game_id": game_id},
                {"$set": thinking_scores},
                upsert=True
            )
            
            logger.info(f"[THINKING SCORE] Calculated for {game_id}: {thinking_scores.get('overall_score', 0):.1f}")
        except Exception as ts_err:
            # Non-fatal - log but don't fail the analysis
            logger.warning(f"[THINKING SCORE] Failed to calculate: {ts_err}")
        
        # =========================================================================
        # PHASE 7: DATA FRESHNESS - Refresh all aggregated data
        # This ensures all pages show consistent, up-to-date information
        # =========================================================================
        try:
            from services.data_freshness import refresh_all_user_data
            refresh_result = refresh_all_user_data(db, user_id)
            logger.info(f"[DATA REFRESH] Refreshed all data for {user_id}: {refresh_result.get('updates', {})}")
        except Exception as refresh_err:
            # Non-fatal - log but don't fail the analysis
            logger.warning(f"[DATA REFRESH] Failed to refresh: {refresh_err}")
        
        # =========================================================================
        # PHASE 8: STREAK UPDATE (Mistake-Free Streak - Backend Truth)
        # Updates user's streak based on focus mistake detection
        # This is the SOURCE OF TRUTH - frontend does NOT update streaks
        # =========================================================================
        try:
            from services.mistake_streak_service import update_streak_from_analysis
            
            game_metadata = {
                "result": game.get("result"),
                "user_rating": user_rating,
                "opponent_rating": game.get("opponent_rating"),
                "time_control": game.get("time_control")
            }
            
            streak_result = update_streak_from_analysis(
                db=db,
                user_id=user_id,
                game_id=game_id,
                move_evaluations=move_evaluations,
                user_color=user_color,
                game_metadata=game_metadata
            )
            
            if streak_result.get("streak_changed"):
                result_type = streak_result.get("postgame_result", {}).get("result", "unknown")
                logger.info(f"[STREAK] Updated for {user_id}: {result_type}")
            else:
                logger.info("[STREAK] Game skipped (not valid for streak)")
            
            # =====================================================================
            # AUTO-DETECT FOCUS: If user has no focus set, detect from patterns
            # This ensures focus is ONLY set from real detected patterns
            # =====================================================================
            user_streak = db.users.find_one({"user_id": user_id}, {"streak_data": 1})
            current_focus = user_streak.get("streak_data", {}).get("current_focus_mistake") if user_streak else None
            
            if current_focus is None:
                # Get identity to find most common blunder type
                identity = db.player_identities.find_one({"user_id": user_id})
                if identity:
                    blunder_by_type = identity.get("blunder_taxonomy", {}).get("by_type", {})
                    most_common = identity.get("blunder_taxonomy", {}).get("most_common_type")
                    
                    # Only set focus if we have actual data (count > 0)
                    if most_common and blunder_by_type.get(most_common, 0) > 0:
                        # Map blunder type to streak focus type
                        blunder_to_focus = {
                            "tactical_error": "THREAT_VERIFICATION",
                            "positional_error": "STOPPED_CALCULATION_EARLY",
                            "time_trouble": "FORCING_BLIND",
                            "opening_mistake": "FORCING_BLIND",
                            "endgame_error": "TACTICAL_MISS",
                            "blunder": "THREAT_VERIFICATION",
                            "missed_win": "TACTICAL_MISS",
                            "missed_tactic": "TACTICAL_MISS",
                            "hanging_piece": "HANGING_PIECE"
                        }
                        
                        focus_type = blunder_to_focus.get(most_common, "THREAT_VERIFICATION")
                        
                        db.users.update_one(
                            {"user_id": user_id},
                            {"$set": {"streak_data.current_focus_mistake": focus_type}},
                            upsert=True
                        )
                        logger.info(f"[FOCUS] Auto-detected focus for {user_id}: {most_common} -> {focus_type}")
                
        except Exception as streak_err:
            # Non-fatal - log but don't fail the analysis
            logger.warning(f"[STREAK] Failed to update: {streak_err}")
        
        # =========================================================================
        # PHASE 9: GAME DECRYPTION (Move-by-Move Coaching Narratives)
        # Generates coaching explanations for EVERY move in the game.
        # This is stored once during analysis and loaded instantly on Lab page.
        # =========================================================================
        try:
            from services.game_decryption_service import (
                generate_game_decryption, generate_game_summary,
                detect_opening_from_pgn, get_opening_data
            )
            
            logger.info(f"[DECRYPTION] Generating move-by-move coaching for {game_id}...")
            
            # Add move_index to each evaluation for lookup
            for idx, eval_data in enumerate(move_evaluations):
                eval_data["move_index"] = idx
            
            decryption_data = generate_game_decryption(
                pgn=pgn,
                user_color=user_color,
                move_evaluations=move_evaluations
            )
            
            if decryption_data:
                # V3: Pass opening data for richer summary with opening introduction
                opening_name_d, eco_code_d = detect_opening_from_pgn(pgn)
                opening_data_d = get_opening_data(eco_code_d, opening_name_d)
                decryption_summary = generate_game_summary(decryption_data, user_color, opening_data_d)
                
                # Store in analysis document
                db.game_analyses.update_one(
                    {"game_id": game_id, "user_id": user_id},
                    {"$set": {
                        "decryption_data": decryption_data,
                        "decryption_summary": decryption_summary,
                        "decryption_generated_at": datetime.now(timezone.utc).isoformat()
                    }}
                )
                logger.info(f"[DECRYPTION] Generated {len(decryption_data)} move narratives for {game_id}")
            else:
                logger.warning(f"[DECRYPTION] No data generated for {game_id}")
                
        except Exception as decrypt_err:
            # Non-fatal - log but don't fail the analysis
            logger.warning(f"[DECRYPTION] Failed to generate: {decrypt_err}")
            import traceback
            traceback.print_exc()
        
        # ============ COMMUNITY TRAINING POSITIONS ============
        # Extract training-worthy positions for the community pool
        try:
            import asyncio
            from services.community_training_service import extract_training_positions
            from motor.motor_asyncio import AsyncIOMotorClient
            
            mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
            db_name = os.environ.get("DB_NAME", "chess_coach")
            async_client = AsyncIOMotorClient(mongo_url)
            async_db = async_client[db_name]
            
            loop = asyncio.new_event_loop()
            positions = loop.run_until_complete(
                extract_training_positions(async_db, game_id, user_id)
            )
            loop.close()
            async_client.close()
            
            if positions:
                logger.info(f"[TRAINING] Extracted {len(positions)} training positions for {game_id}")
        except Exception as train_err:
            logger.warning(f"[TRAINING] Position extraction failed (non-critical): {train_err}")
        
        logger.info(f"[SUCCESS] Analyzed game {game_id} (accuracy: {accuracy}%, duration: {elapsed:.1f}s)")
        return True
        
    except Exception as e:
        logger.exception(f"[EXCEPTION] Error processing game {game_id}: {e}")
        mark_job_failed(db, game_id, str(e)[:500])
        return False


def mark_job_failed(db, game_id, error_message):
    """Mark a job as failed and update retry count"""
    logger.warning(f"[FAIL] Marking job {game_id} as failed: {error_message[:100]}")
    
    db.analysis_queue.update_one(
        {"game_id": game_id},
        {
            "$set": {
                "status": "failed",
                "failed_at": datetime.now(timezone.utc),
                "failure_reason": "analysis_error",
                "retrying": False,
                **_queue_error_payload(error_message)
            },
            "$inc": {"retry_count": 1}
        }
    )
    
    # IMPORTANT: Update game status so frontend doesn't show "processing" forever
    db.games.update_one(
        {"game_id": game_id},
        {"$set": {"analysis_status": "failed", "analysis_error": error_message[:500]}}
    )


def run_worker():
    """Main worker loop"""
    logger.info(f"Starting analysis worker {WORKER_ID}")
    logger.info(f"Stockfish depth: {STOCKFISH_DEPTH}")
    logger.info(f"Poll interval: {POLL_INTERVAL}s")
    logger.info(f"Job timeout: {JOB_TIMEOUT_MINUTES} minutes")
    logger.info(f"Max retries: {MAX_RETRIES}")
    
    # Set up signal handlers for graceful shutdown
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    # Step 1: Ensure Stockfish is installed
    if not ensure_stockfish_installed():
        logger.error("Cannot start worker - Stockfish is not available")
        sys.exit(1)
    
    # Step 2: Connect to MongoDB
    try:
        db = get_database()
        logger.info("Connected to MongoDB")
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {e}")
        sys.exit(1)
    
    # Step 3: Clean up any stuck jobs from previous runs
    logger.info("Checking for stuck jobs...")
    cleanup_stuck_jobs(db)
    
    jobs_processed = 0
    jobs_failed = 0
    last_cleanup = time.time()
    last_stats_log = time.time()
    CLEANUP_INTERVAL = 60  # Run cleanup every minute (reduced from 5 minutes)
    STATS_LOG_INTERVAL = 300  # Log stats every 5 minutes
    
    while not shutdown_requested:
        try:
            current_time = time.time()
            
            # Periodically clean up stuck jobs (more frequently now)
            if current_time - last_cleanup > CLEANUP_INTERVAL:
                cleanup_stuck_jobs(db)
                last_cleanup = current_time
            
            # Log stats periodically
            if current_time - last_stats_log > STATS_LOG_INTERVAL:
                pending_count = db.analysis_queue.count_documents({"status": "pending"})
                processing_count = db.analysis_queue.count_documents({"status": "processing"})
                logger.info(f"[STATS] Processed: {jobs_processed}, Failed: {jobs_failed}, Pending: {pending_count}, Processing: {processing_count}")
                last_stats_log = current_time
            
            # Try to claim a job
            job = claim_next_job(db)
            
            if job:
                success = process_job(db, job)
                jobs_processed += 1
                
                if success:
                    logger.info(f"[COMPLETE] Job done. Total processed: {jobs_processed}")
                else:
                    jobs_failed += 1
                    logger.warning(f"[FAILED] Job failed. Total processed: {jobs_processed}, failed: {jobs_failed}")
            else:
                # No jobs available, wait before polling again
                time.sleep(POLL_INTERVAL)
                
        except Exception as e:
            logger.exception(f"[WORKER ERROR] Unexpected error in main loop: {e}")
            time.sleep(POLL_INTERVAL)
    
    logger.info(f"Worker shutting down. Total jobs processed: {jobs_processed}, failed: {jobs_failed}")


# =============================================================================
# FOCUS LOCK COMPLIANCE UPDATE (Step 9)
# =============================================================================

def update_focus_lock_compliance(db, user_id: str, move_evaluations: list):
    """
    Update focus lock compliance after game analysis.
    
    Called immediately after game analysis completes.
    Uses the same move_evaluations from Stockfish analysis (no re-analysis).
    
    Flow:
    1. Check if user has an active focus lock
    2. If active, calculate compliance for this game
    3. Update lock state (games_completed, compliance_score)
    4. Check for completion/extension/strict mode
    5. Persist updated state immediately
    """
    # Step 1: Get user's coach_state with focus_lock
    coach_state = db.coach_states.find_one(
        {"user_id": user_id},
        {"focus_lock": 1, "_id": 0}
    )
    
    if not coach_state:
        logger.debug(f"[FOCUS LOCK] No coach_state for user {user_id}")
        return
    
    focus_lock_doc = coach_state.get("focus_lock")
    if not focus_lock_doc:
        logger.debug(f"[FOCUS LOCK] No active focus lock for user {user_id}")
        return
    
    # Rebuild FocusLock from DB
    lock = focus_lock_from_db(focus_lock_doc)
    if not lock:
        logger.debug(f"[FOCUS LOCK] Failed to parse focus lock for user {user_id}")
        return
    
    # Check if lock is active (not completed/failed)
    if lock.state in ("COMPLETED", "FAILED", "NONE"):
        logger.debug(f"[FOCUS LOCK] Lock not active (state={lock.state}) for user {user_id}")
        return
    
    logger.info(f"[FOCUS LOCK] Processing compliance for user {user_id}, lesson={lock.lesson_key}")
    
    # Step 2: Calculate compliance using the same move_evaluations
    compliance = calculate_compliance(lock.lesson_key, move_evaluations)
    logger.info(f"[FOCUS LOCK] Compliance result: score={compliance.compliance_score:.2f}, "
                f"opportunities={compliance.total_opportunities}, missed={compliance.missed_count}")
    
    # Step 3: Determine trend from existing compliance scores
    all_scores = lock.compliance_scores + [compliance.compliance_score]
    trend = calculate_compliance_trend(all_scores)
    logger.info(f"[FOCUS LOCK] Compliance trend: {trend}")
    
    # Step 4: Update lock state
    updated_lock = update_lock_after_game(lock, compliance, trend)
    logger.info(f"[FOCUS LOCK] Updated state: {updated_lock.state}, "
                f"games={updated_lock.games_completed}/{updated_lock.games_required}, "
                f"avg_compliance={updated_lock.average_compliance:.2f}")
    
    # Step 5: Persist updated state immediately
    db.coach_states.update_one(
        {"user_id": user_id},
        {"$set": {"focus_lock": focus_lock_to_db(updated_lock)}}
    )
    
    # Step 6: Check if we need to trigger deep session
    if should_trigger_deep_session(updated_lock):
        logger.info(f"[FOCUS LOCK] Triggering deep session for user {user_id} (failed_cycles={updated_lock.failed_cycles})")
        # Set a flag for deep session trigger
        db.coach_states.update_one(
            {"user_id": user_id},
            {"$set": {"pending_deep_session": {
                "trigger": "focus_lock_failure",
                "lesson_key": updated_lock.lesson_key,
                "failed_cycles": updated_lock.failed_cycles,
                "created_at": datetime.now(timezone.utc).isoformat()
            }}}
        )
    
    # Step 7: Log terminal states for analytics (silent, internal)
    if updated_lock.state in ("COMPLETED", "FAILED"):
        cycle_log = create_cycle_log(user_id, updated_lock)
        db.focus_lock_analytics.insert_one(cycle_log.to_dict())
        logger.info(f"[FOCUS LOCK ANALYTICS] Logged cycle: user={user_id}, outcome={cycle_log.outcome}, "
                    f"compliance={cycle_log.final_compliance:.2f}, strict_mode={cycle_log.strict_mode_triggered}")
    
    logger.info(f"[FOCUS LOCK] Compliance update complete for user {user_id}")


# =============================================================================
# MODULE TRIGGER DETECTION (Step 10)
# =============================================================================

def detect_and_inject_module(db, user_id: str, game_id: str, user_rating: int):
    """
    Detect which theory module applies to this game and inject it.
    
    Auto-lock if:
    - 3+ triggers in last 10 games
    - High confidence (≥300cp swing)
    - No active focus lock
    """
    # Get the game analysis
    analysis = db.game_analyses.find_one(
        {"game_id": game_id},
        {"_id": 0, "lesson_key": 1, "core_lesson": 1, "stockfish_analysis": 1, 
         "game_phase": 1, "dominant_lesson_key": 1}
    )
    
    if not analysis:
        logger.debug(f"[MODULE TRIGGER] No analysis found for game {game_id}")
        return
    
    # Get recent injections for cooldown check
    recent_injections = list(db.module_injections.find(
        {"user_id": user_id},
        {"_id": 0}
    ).sort("injected_at", -1).limit(20))
    
    # Detect module
    trigger = detect_module_for_game(analysis, user_rating, recent_injections)
    
    if not trigger.triggered:
        logger.debug(f"[MODULE TRIGGER] No module triggered for game {game_id}")
        return
    
    logger.info(f"[MODULE TRIGGER] Detected module {trigger.module_key} for user {user_id} "
                f"(confidence={trigger.confidence}, cp_loss={trigger.evidence_cp_loss})")
    
    # Check for active focus lock
    coach_state = db.coach_states.find_one(
        {"user_id": user_id},
        {"focus_lock": 1, "_id": 0}
    )
    
    has_active_lock = False
    if coach_state and coach_state.get("focus_lock"):
        lock = focus_lock_from_db(coach_state.get("focus_lock"))
        if lock and lock.state not in ("COMPLETED", "FAILED", "NONE"):
            has_active_lock = True
    
    # Get recent triggers for auto-lock check
    recent_triggers = list(db.module_injections.find(
        {"user_id": user_id},
        {"_id": 0, "module_key": 1}
    ).sort("injected_at", -1).limit(10))
    
    # Check auto-lock condition
    should_auto_lock, trigger_count = check_auto_lock_condition(
        trigger.module_key,
        trigger.confidence,
        recent_triggers,
        has_active_lock
    )
    
    trigger.trigger_count_in_window = trigger_count
    trigger.should_auto_lock = should_auto_lock
    
    # Create and store injection record
    injection = create_injection_record(user_id, game_id, trigger, should_auto_lock)
    db.module_injections.insert_one(injection.to_dict())
    
    # Store trigger on the game analysis for Lab page
    db.game_analyses.update_one(
        {"game_id": game_id},
        {"$set": {"module_trigger": trigger.to_dict()}}
    )
    
    logger.info(f"[MODULE TRIGGER] Injected module {trigger.module_key} for game {game_id}")
    
    # Auto-lock if conditions met
    if should_auto_lock:
        focus_lesson = get_focus_lock_lesson_for_module(trigger.module_key)
        if focus_lesson:
            new_lock = create_focus_lock(focus_lesson, games=5)
            
            db.coach_states.update_one(
                {"user_id": user_id},
                {
                    "$set": {
                        "focus_lock": focus_lock_to_db(new_lock),
                        "focus_lock_activated_at": datetime.now(timezone.utc).isoformat(),
                        "focus_lock_trigger": {
                            "source": "auto_module_trigger",
                            "module_key": trigger.module_key,
                            "trigger_count": trigger_count,
                            "game_id": game_id,
                        }
                    }
                },
                upsert=True
            )
            
            logger.info(f"[MODULE TRIGGER] Auto-locked user {user_id} on {focus_lesson} "
                        f"(triggered by {trigger.module_key}, count={trigger_count})")


if __name__ == "__main__":
    run_worker()
