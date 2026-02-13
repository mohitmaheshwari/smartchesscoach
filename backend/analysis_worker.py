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
from datetime import datetime, timezone
from pymongo import MongoClient
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from stockfish_service import analyze_game_with_stockfish
from config import STOCKFISH_DEPTH

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('analysis_worker')

# Configuration
POLL_INTERVAL = 2  # Seconds between queue checks
MAX_RETRIES = 3    # Max retries for failed analysis
WORKER_ID = f"worker-{os.getpid()}"
JOB_TIMEOUT_MINUTES = 10  # Timeout for stuck jobs

# Graceful shutdown flag
shutdown_requested = False


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
            logger.warning(f"Job {game_id} permanently failed after {MAX_RETRIES} retries")
        else:
            # Reset to pending for retry
            db.analysis_queue.update_one(
                {"game_id": game_id},
                {
                    "$set": {
                        "status": "pending",
                        "started_at": None,
                        "worker_id": None
                    },
                    "$inc": {"retry_count": 1}
                }
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
    
    logger.info(f"Processing game {game_id} for user {user_id}")
    
    try:
        # Get the game data
        game = db.games.find_one({"game_id": game_id})
        
        if not game:
            logger.error(f"Game {game_id} not found in database")
            mark_job_failed(db, game_id, "Game not found")
            return False
        
        pgn = game.get("pgn")
        if not pgn:
            logger.error(f"Game {game_id} has no PGN data")
            mark_job_failed(db, game_id, "No PGN data")
            return False
        
        user_color = game.get("user_color", "white")
        
        # Run Stockfish analysis (this is the slow part!)
        logger.info(f"Starting Stockfish analysis (depth={STOCKFISH_DEPTH})...")
        start_time = time.time()
        
        stockfish_result = analyze_game_with_stockfish(
            pgn,
            user_color=user_color,
            depth=STOCKFISH_DEPTH
        )
        
        elapsed = time.time() - start_time
        logger.info(f"Stockfish analysis completed in {elapsed:.1f}s")
        
        if not stockfish_result or not stockfish_result.get("success"):
            error_msg = stockfish_result.get("error", "Unknown error") if stockfish_result else "Analysis returned None"
            logger.error(f"Stockfish analysis failed: {error_msg}")
            mark_job_failed(db, game_id, error_msg)
            return False
        
        # Extract stats
        sf_stats = stockfish_result.get("user_stats", {})
        move_evaluations = stockfish_result.get("moves", [])
        
        # VALIDATION: Ensure analysis is complete and valid
        # A valid analysis must have:
        # 1. At least some move evaluations
        # 2. A non-zero accuracy (unless it's genuinely 0% which is extremely rare)
        # 3. Total moves analyzed > 0
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
            logger.error(f"Analysis validation failed for {game_id}: {validation_error}")
            mark_job_failed(db, game_id, validation_error)
            return False
        
        logger.info(f"Analysis validated: {total_moves} moves, {accuracy}% accuracy")
        
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
            "analysis_depth": STOCKFISH_DEPTH,
            "analyzed_at": datetime.now(timezone.utc),
            "analysis_duration_seconds": elapsed,
            "worker_id": WORKER_ID
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
        
        logger.info(f"Successfully analyzed game {game_id} (accuracy: {sf_stats.get('accuracy', 0)}%)")
        return True
        
    except Exception as e:
        logger.exception(f"Error processing game {game_id}: {e}")
        mark_job_failed(db, game_id, str(e))
        return False


def mark_job_failed(db, game_id, error_message):
    """Mark a job as failed and update retry count"""
    db.analysis_queue.update_one(
        {"game_id": game_id},
        {
            "$set": {
                "status": "failed",
                "error": error_message,
                "failed_at": datetime.now(timezone.utc)
            },
            "$inc": {"retry_count": 1}
        }
    )
    
    db.games.update_one(
        {"game_id": game_id},
        {"$set": {"analysis_status": "failed"}}
    )


def run_worker():
    """Main worker loop"""
    logger.info(f"Starting analysis worker {WORKER_ID}")
    logger.info(f"Stockfish depth: {STOCKFISH_DEPTH}")
    logger.info(f"Poll interval: {POLL_INTERVAL}s")
    
    # Set up signal handlers for graceful shutdown
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        db = get_database()
        logger.info("Connected to MongoDB")
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {e}")
        sys.exit(1)
    
    # Test Stockfish availability
    try:
        from config import STOCKFISH_PATH
        if not os.path.exists(STOCKFISH_PATH):
            logger.error(f"Stockfish not found at {STOCKFISH_PATH}")
            sys.exit(1)
        logger.info(f"Stockfish found at {STOCKFISH_PATH}")
    except Exception as e:
        logger.error(f"Failed to verify Stockfish: {e}")
        sys.exit(1)
    
    jobs_processed = 0
    
    while not shutdown_requested:
        try:
            # Try to claim a job
            job = claim_next_job(db)
            
            if job:
                success = process_job(db, job)
                jobs_processed += 1
                
                if success:
                    logger.info(f"Job completed. Total processed: {jobs_processed}")
                else:
                    logger.warning(f"Job failed. Total processed: {jobs_processed}")
            else:
                # No jobs available, wait before polling again
                time.sleep(POLL_INTERVAL)
                
        except Exception as e:
            logger.exception(f"Worker error: {e}")
            time.sleep(POLL_INTERVAL)
    
    logger.info(f"Worker shutting down. Total jobs processed: {jobs_processed}")


if __name__ == "__main__":
    run_worker()
