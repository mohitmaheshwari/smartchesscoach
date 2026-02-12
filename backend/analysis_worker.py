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

# Graceful shutdown flag
shutdown_requested = False


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    global shutdown_requested
    logger.info(f"Received signal {signum}, shutting down gracefully...")
    shutdown_requested = True


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
