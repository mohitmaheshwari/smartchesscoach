"""
Historical Re-Analysis Job Worker

Re-analyzes historical games using the latest behavioral analysis engine.

CRITICAL CONSTRAINTS:
1. historical_mode=True: Does NOT mutate advice lifecycle
   - No auto-create advice
   - No auto-resolve advice
   - No auto-archive advice
   
2. Idempotent: Running twice produces same result
   - Same idempotency_key returns existing job
   - Skips games already analyzed with current engine_version

3. Rate limited: 300ms sleep between games

4. Safe: Max 1 RUNNING job per user, max 50 games per run
"""

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, Optional, List
from dataclasses import dataclass, asdict

from config import ENGINE_VERSION, REANALYSIS_CONFIG

logger = logging.getLogger(__name__)


@dataclass
class ReanalysisJob:
    """Reanalysis job data structure"""
    job_id: str
    user_id: str
    status: str  # PENDING | RUNNING | DONE | FAILED
    created_at: str
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    
    # Scope
    total_games: int = 0
    processed_games: int = 0
    skipped_games: int = 0
    failed_games: int = 0
    last_game_id_processed: Optional[str] = None
    
    # Idempotency
    idempotency_key: str = ""
    engine_version: str = ENGINE_VERSION
    
    # Error tracking
    last_error: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return asdict(self)


async def enqueue_reanalysis(
    db,
    user_id: str,
    engine_version: str = None
) -> ReanalysisJob:
    """
    Enqueue a reanalysis job for a user.
    
    Idempotent: Returns existing job if one is already PENDING or RUNNING.
    """
    engine_version = engine_version or ENGINE_VERSION
    idempotency_key = f"reanalysis:{user_id}:{engine_version}"
    
    # Check for existing job (idempotent)
    existing = await db.reanalysis_jobs.find_one({
        "idempotency_key": idempotency_key,
        "status": {"$in": ["PENDING", "RUNNING"]}
    })
    
    if existing:
        logger.info(f"Returning existing job {existing['job_id']} for user {user_id}")
        return _job_from_doc(existing)
    
    # Create new job
    job = ReanalysisJob(
        job_id=str(uuid.uuid4()),
        user_id=user_id,
        status="PENDING",
        created_at=datetime.now(timezone.utc).isoformat(),
        idempotency_key=idempotency_key,
        engine_version=engine_version
    )
    
    await db.reanalysis_jobs.insert_one(job.to_dict())
    logger.info(f"Created reanalysis job {job.job_id} for user {user_id}")
    
    return job


async def run_reanalysis_job(db, job_id: str) -> ReanalysisJob:
    """
    Run a reanalysis job.
    
    CRITICAL: Uses historical_mode=True to prevent advice mutation.
    """
    from behavioral_analyzer_service import generate_behavioral_report
    
    # Load job
    job_doc = await db.reanalysis_jobs.find_one({"job_id": job_id})
    if not job_doc:
        raise ValueError(f"Job {job_id} not found")
    
    job = _job_from_doc(job_doc)
    
    # Check if already running for this user
    running_count = await db.reanalysis_jobs.count_documents({
        "user_id": job.user_id,
        "status": "RUNNING",
        "job_id": {"$ne": job_id}
    })
    
    if running_count > 0:
        logger.warning(f"Another job already running for user {job.user_id}")
        return job
    
    # Mark as RUNNING
    job.status = "RUNNING"
    job.started_at = datetime.now(timezone.utc).isoformat()
    await _save_job(db, job)
    
    try:
        # Load user's games (most recent first)
        max_games = REANALYSIS_CONFIG.get("max_games_per_run", 50)
        games = await db.games.find(
            {"user_id": job.user_id}
        ).sort("played_at", -1).limit(max_games).to_list(max_games)
        
        job.total_games = len(games)
        await _save_job(db, job)
        
        sleep_ms = REANALYSIS_CONFIG.get("sleep_between_games_ms", 300)
        
        for game in games:
            game_id = game.get("game_id")
            
            try:
                # Check if already analyzed with current engine version
                existing_report = await db.behavioral_reports.find_one({
                    "user_id": job.user_id,
                    "game_id": game_id,
                    "engine_version": job.engine_version
                })
                
                if existing_report:
                    job.skipped_games += 1
                    logger.debug(f"Skipping game {game_id} - already analyzed with {job.engine_version}")
                    continue
                
                # Re-analyze with historical_mode=True
                # This prevents advice lifecycle mutations
                report = await generate_behavioral_report(
                    db,
                    job.user_id,
                    game_id,
                    historical_mode=True  # CRITICAL: No advice mutations
                )
                
                if report and not report.get("error"):
                    # Store the report with engine version
                    await _store_behavioral_report(db, job.user_id, game_id, report, job.engine_version)
                    job.processed_games += 1
                else:
                    job.failed_games += 1
                    job.last_error = report.get("error", "Unknown error")
                
                job.last_game_id_processed = game_id
                await _save_job(db, job)
                
            except Exception as e:
                job.failed_games += 1
                job.last_error = str(e)
                logger.error(f"Error reanalyzing game {game_id}: {e}")
                await _save_job(db, job)
            
            # Rate limit
            await asyncio.sleep(sleep_ms / 1000)
        
        job.status = "DONE"
        job.finished_at = datetime.now(timezone.utc).isoformat()
        
    except Exception as e:
        job.status = "FAILED"
        job.last_error = str(e)
        job.finished_at = datetime.now(timezone.utc).isoformat()
        logger.error(f"Job {job_id} failed: {e}")
    
    await _save_job(db, job)
    logger.info(f"Job {job_id} completed: {job.status} - processed {job.processed_games}, skipped {job.skipped_games}, failed {job.failed_games}")
    
    return job


async def get_reanalysis_status(db, user_id: str) -> Optional[Dict]:
    """
    Get the status of the most recent reanalysis job for a user.
    """
    job_doc = await db.reanalysis_jobs.find_one(
        {"user_id": user_id},
        sort=[("created_at", -1)]
    )
    
    if not job_doc:
        return None
    
    job = _job_from_doc(job_doc)
    
    return {
        "job_id": job.job_id,
        "status": job.status,
        "processed_games": job.processed_games,
        "skipped_games": job.skipped_games,
        "total_games": job.total_games,
        "failed_games": job.failed_games,
        "engine_version": job.engine_version,
        "progress_percent": (job.processed_games + job.skipped_games) / max(job.total_games, 1) * 100,
        "created_at": job.created_at,
        "finished_at": job.finished_at
    }


async def _save_job(db, job: ReanalysisJob) -> None:
    """Save job to database"""
    await db.reanalysis_jobs.update_one(
        {"job_id": job.job_id},
        {"$set": job.to_dict()}
    )


async def _store_behavioral_report(
    db,
    user_id: str,
    game_id: str,
    report: Dict,
    engine_version: str
) -> None:
    """
    Store behavioral report with engine version.
    Upserts to avoid duplicates.
    """
    doc = {
        "user_id": user_id,
        "game_id": game_id,
        "engine_version": engine_version,
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "headline": report.get("headline"),
        "rich_insight": report.get("rich_insight"),
        "root_cause": report.get("root_cause"),
        "main_problem": report.get("main_problem"),
        "learning_velocity": report.get("learning_velocity"),
        "learner_type": report.get("learner_type"),
        "scorecard": report.get("scorecard"),
        "stagnation": report.get("stagnation"),
        "confidence": report.get("confidence"),
    }
    
    await db.behavioral_reports.update_one(
        {"user_id": user_id, "game_id": game_id},
        {"$set": doc},
        upsert=True
    )


def _job_from_doc(doc: Dict) -> ReanalysisJob:
    """Convert MongoDB document to ReanalysisJob"""
    return ReanalysisJob(
        job_id=doc.get("job_id"),
        user_id=doc.get("user_id"),
        status=doc.get("status"),
        created_at=doc.get("created_at"),
        started_at=doc.get("started_at"),
        finished_at=doc.get("finished_at"),
        total_games=doc.get("total_games", 0),
        processed_games=doc.get("processed_games", 0),
        skipped_games=doc.get("skipped_games", 0),
        failed_games=doc.get("failed_games", 0),
        last_game_id_processed=doc.get("last_game_id_processed"),
        idempotency_key=doc.get("idempotency_key", ""),
        engine_version=doc.get("engine_version", ENGINE_VERSION),
        last_error=doc.get("last_error"),
    )
