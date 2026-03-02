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
from config import STOCKFISH_DEPTH

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
JOB_TIMEOUT_MINUTES = 5  # Reduced timeout for stuck jobs (was 10)
HEARTBEAT_INTERVAL = 30  # Seconds between heartbeat updates

# Graceful shutdown flag
shutdown_requested = False
last_heartbeat = time.time()


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
        "started_at": {"$lt": timeout_threshold}
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
                        "error": f"Timed out after {JOB_TIMEOUT_MINUTES} minutes (max retries exceeded)",
                        "failed_at": datetime.now(timezone.utc)
                    }
                }
            )
            db.games.update_one(
                {"game_id": game_id},
                {"$set": {"analysis_status": "failed"}}
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
                        "worker_id": None,
                        "last_reset_at": datetime.now(timezone.utc),
                        "reset_reason": f"Timeout after {JOB_TIMEOUT_MINUTES} min (attempt {retry_count + 1})"
                    },
                    "$inc": {"retry_count": 1}
                }
            )
            db.games.update_one(
                {"game_id": game_id},
                {"$set": {"analysis_status": "queued"}}
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
            {"$set": {"last_heartbeat": datetime.now(timezone.utc)}}
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
                "started_at": datetime.now(timezone.utc)
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
        
        # Update game status to show it's being processed
        db.games.update_one(
            {"game_id": game_id},
            {"$set": {"analysis_status": "processing"}}
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
                "avg_cp_loss": sf_stats.get("avg_cp_loss", 0),
                "move_evaluations": move_evaluations
            },
            # NEW: Behavioral interpretation summary
            "interpretation": interpretation_summary if interpretation_summary else {},
            "analysis_depth": STOCKFISH_DEPTH,
            "analyzed_at": datetime.now(timezone.utc),
            "created_at": datetime.now(timezone.utc),
            "analysis_duration_seconds": elapsed,
            "worker_id": WORKER_ID,
            "engine_version": "P2.3"  # Track version for future migrations
        }
        
        # Upsert analysis (update if exists, insert if not)
        db.game_analyses.update_one(
            {"game_id": game_id, "user_id": user_id},
            {"$set": analysis_doc},
            upsert=True
        )
        
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
                "duration_seconds": elapsed
            }}
        )
        
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
                "error": error_message[:500],  # Limit error message length
                "failed_at": datetime.now(timezone.utc)
            },
            "$inc": {"retry_count": 1}
        }
    )
    
    # IMPORTANT: Update game status so frontend doesn't show "processing" forever
    db.games.update_one(
        {"game_id": game_id},
        {"$set": {"analysis_status": "failed"}}
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


if __name__ == "__main__":
    run_worker()
