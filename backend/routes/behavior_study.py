"""
Behavior Validation Study Routes — Week 4-16 infrastructure
============================================================

Endpoints for the 12-week study proving that puzzle training reduces mistakes:
- /study/opt-in — User opts into the study
- /study/baseline — Capture current mistake rate (Week 5)
- /study/progress — Check enrollment + window dates
- /study/results — Analysis results (Week 16)
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, Dict
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/study", tags=["behavior-study"])

# Global db reference (will be set by server.py)
db = None


def set_db(_db):
    """Inject database connection from server.py"""
    global db
    db = _db


# Import dependencies
from routes.coach_play import get_current_user, User


class StudyOptInRequest(BaseModel):
    pattern: str  # piece_safety, missed_tactic, king_safety, time_pressure, calculation_depth


@router.post("/opt-in")
async def opt_in_to_study(
    request: StudyOptInRequest,
    user: User = Depends(get_current_user),
):
    """
    User opts into behavior validation study.

    Creates entry in study_participants collection with:
    - user_id, pattern (assigned focus)
    - status: "enrolled"
    - opted_in_at: timestamp
    - window dates (baseline, intervention, outcome)

    Response: enrollment confirmation with pattern + timeline
    """
    pattern = request.pattern
    valid_patterns = [
        "piece_safety",
        "missed_tactic",
        "king_safety",
        "time_pressure",
        "calculation_depth",
    ]
    if pattern not in valid_patterns:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid pattern. Must be one of: {', '.join(valid_patterns)}",
        )

    # Check if user already enrolled
    existing = await db.study_participants.find_one({"user_id": user.user_id})
    if existing:
        return {
            "status": "already_enrolled",
            "pattern": existing.get("pattern"),
            "opted_in_at": existing.get("opted_in_at"),
        }

    # Create enrollment record
    enrollment = {
        "user_id": user.user_id,
        "pattern": pattern,
        "status": "enrolled",
        "opted_in_at": datetime.now(timezone.utc),
        "baseline_window": {
            "start": "2026-01-27",
            "end": "2026-01-31",
            "description": "Week 5: Measure current mistake rate",
        },
        "intervention_window": {
            "start": "2026-02-01",
            "end": "2026-03-26",
            "description": "Weeks 6-15: Puzzle training on assigned pattern",
        },
        "outcome_window": {
            "start": "2026-03-27",
            "end": "2026-04-02",
            "description": "Week 16: Measure new mistake rate",
        },
    }

    await db.study_participants.insert_one(enrollment)

    logger.info(f"[STUDY] User {user.user_id} enrolled in study for pattern={pattern}")

    return {
        "status": "enrolled",
        "pattern": pattern,
        "message": f"You're enrolled! Focus on {pattern} puzzles during {enrollment['intervention_window']['description']}",
        "windows": enrollment,
    }


@router.get("/progress")
async def check_study_progress(user: User = Depends(get_current_user)):
    """
    Check user's study enrollment status + timeline.

    Returns:
    - enrolled: true/false
    - pattern: assigned focus (if enrolled)
    - windows: baseline/intervention/outcome dates
    - current_phase: which phase we're in now
    """
    enrollment = await db.study_participants.find_one({"user_id": user.user_id})

    if not enrollment:
        return {
            "enrolled": False,
            "message": "You're not enrolled in the study yet. Check your email for an invitation!",
        }

    now = datetime.now(timezone.utc).date()
    baseline_start = datetime.fromisoformat(enrollment["baseline_window"]["start"]).date()
    baseline_end = datetime.fromisoformat(enrollment["baseline_window"]["end"]).date()
    intervention_start = datetime.fromisoformat(enrollment["intervention_window"]["start"]).date()
    intervention_end = datetime.fromisoformat(enrollment["intervention_window"]["end"]).date()
    outcome_start = datetime.fromisoformat(enrollment["outcome_window"]["start"]).date()
    outcome_end = datetime.fromisoformat(enrollment["outcome_window"]["end"]).date()

    # Determine current phase
    if now < baseline_start:
        current_phase = "not_started"
    elif baseline_start <= now <= baseline_end:
        current_phase = "baseline_measurement"
    elif intervention_start <= now <= intervention_end:
        current_phase = "intervention"
    elif outcome_start <= now <= outcome_end:
        current_phase = "outcome_measurement"
    else:
        current_phase = "completed"

    return {
        "enrolled": True,
        "pattern": enrollment["pattern"],
        "opted_in_at": enrollment["opted_in_at"],
        "current_phase": current_phase,
        "windows": {
            "baseline": enrollment["baseline_window"],
            "intervention": enrollment["intervention_window"],
            "outcome": enrollment["outcome_window"],
        },
    }


@router.post("/baseline-snapshot")
async def record_baseline_snapshot(
    user: User = Depends(get_current_user),
):
    """
    Record baseline mistake rate for enrolled user (Week 5 task).

    Computes mistake rate in their assigned pattern over last 50 games.
    Stores snapshot in study_baseline collection.

    Returns:
    - pattern: assigned focus
    - baseline_window: dates used
    - mistake_rate: pct (e.g., 2.67%)
    - n_games, n_moves, n_mistakes: raw counts
    - status: "recorded" or "not_enrolled"
    """
    enrollment = await db.study_participants.find_one({"user_id": user.user_id})

    if not enrollment:
        raise HTTPException(status_code=403, detail="User not enrolled in study")

    pattern = enrollment["pattern"]
    baseline_start = enrollment["baseline_window"]["start"]
    baseline_end = enrollment["baseline_window"]["end"]

    # Get games in baseline window
    games = await db.games.find(
        {
            "user_id": user.user_id,
            "is_analyzed": True,
            "date_played": {
                "$gte": f"{baseline_start}T00:00:00+00:00",
                "$lte": f"{baseline_end}T23:59:59+00:00",
            },
        },
        {"_id": 0, "game_id": 1},
    ).limit(50).to_list(None)

    game_ids = [g["game_id"] for g in games]

    if not game_ids:
        raise HTTPException(
            status_code=400,
            detail=f"No games found in baseline window ({baseline_start} to {baseline_end})",
        )

    # Count mistakes in assigned pattern
    analyses = await db.game_analyses.find({"game_id": {"$in": game_ids}}).to_list(None)

    n_mistakes = 0
    n_user_moves = 0

    for analysis in analyses:
        for move_eval in analysis.get("stockfish_analysis", {}).get("move_evaluations", []):
            # Count user moves only (not opponent)
            if move_eval.get("is_opponent_move"):
                continue

            n_user_moves += 1

            # Count mistakes in assigned pattern
            if (
                move_eval.get("cognitive_gap") == pattern
                and move_eval.get("classification") in ["mistake", "blunder"]
            ):
                n_mistakes += 1

    mistake_rate_pct = (n_mistakes / n_user_moves * 100) if n_user_moves > 0 else 0.0

    # Store baseline snapshot
    baseline_record = {
        "user_id": user.user_id,
        "pattern": pattern,
        "window": {
            "start": baseline_start,
            "end": baseline_end,
        },
        "measurements": {
            "n_games": len(game_ids),
            "n_user_moves": n_user_moves,
            "n_mistakes": n_mistakes,
            "mistake_rate_pct": round(mistake_rate_pct, 2),
        },
        "recorded_at": datetime.now(timezone.utc),
    }

    await db.study_baseline.insert_one(baseline_record)

    logger.info(
        f"[STUDY] Baseline recorded for {user.user_id} pattern={pattern} "
        f"rate={mistake_rate_pct:.2f}%"
    )

    return {
        "status": "recorded",
        "pattern": pattern,
        "baseline_window": baseline_record["window"],
        **baseline_record["measurements"],
    }


@router.post("/outcome-snapshot")
async def record_outcome_snapshot(
    user: User = Depends(get_current_user),
):
    """
    Record outcome (post-training) mistake rate (Week 16 task).

    Computes mistake rate in assigned pattern over next 50 games after intervention.
    Stores snapshot in study_outcome collection.
    Computes improvement: (baseline_rate - outcome_rate) / baseline_rate × 100%

    Returns:
    - pattern, outcome_window, mistake_rate, n_games, n_moves, n_mistakes
    - baseline_rate, improvement_pct, improvement_status (success/failure/inconclusive)
    """
    enrollment = await db.study_participants.find_one({"user_id": user.user_id})

    if not enrollment:
        raise HTTPException(status_code=403, detail="User not enrolled in study")

    baseline = await db.study_baseline.find_one({"user_id": user.user_id})

    if not baseline:
        raise HTTPException(
            status_code=400,
            detail="Baseline snapshot not found. Must record baseline first (Week 5).",
        )

    pattern = enrollment["pattern"]
    outcome_start = enrollment["outcome_window"]["start"]
    outcome_end = enrollment["outcome_window"]["end"]

    # Get games in outcome window
    games = await db.games.find(
        {
            "user_id": user.user_id,
            "is_analyzed": True,
            "date_played": {
                "$gte": f"{outcome_start}T00:00:00+00:00",
                "$lte": f"{outcome_end}T23:59:59+00:00",
            },
        },
        {"_id": 0, "game_id": 1},
    ).limit(50).to_list(None)

    game_ids = [g["game_id"] for g in games]

    if len(game_ids) < 30:
        raise HTTPException(
            status_code=400,
            detail=f"Only {len(game_ids)} games found in outcome window (need ≥30)",
        )

    # Count mistakes in assigned pattern
    analyses = await db.game_analyses.find({"game_id": {"$in": game_ids}}).to_list(None)

    n_mistakes = 0
    n_user_moves = 0

    for analysis in analyses:
        for move_eval in analysis.get("stockfish_analysis", {}).get("move_evaluations", []):
            if move_eval.get("is_opponent_move"):
                continue

            n_user_moves += 1

            if (
                move_eval.get("cognitive_gap") == pattern
                and move_eval.get("classification") in ["mistake", "blunder"]
            ):
                n_mistakes += 1

    outcome_rate_pct = (n_mistakes / n_user_moves * 100) if n_user_moves > 0 else 0.0
    baseline_rate_pct = baseline["measurements"]["mistake_rate_pct"]

    # Compute improvement
    if baseline_rate_pct > 0:
        improvement_pct = (
            (baseline_rate_pct - outcome_rate_pct) / baseline_rate_pct * 100
        )
    else:
        improvement_pct = 0.0

    # Determine status
    if improvement_pct >= 20:
        improvement_status = "success"
    elif improvement_pct >= 0:
        improvement_status = "partial"
    else:
        improvement_status = "regression"

    # Store outcome snapshot
    outcome_record = {
        "user_id": user.user_id,
        "pattern": pattern,
        "window": {
            "start": outcome_start,
            "end": outcome_end,
        },
        "measurements": {
            "n_games": len(game_ids),
            "n_user_moves": n_user_moves,
            "n_mistakes": n_mistakes,
            "mistake_rate_pct": round(outcome_rate_pct, 2),
        },
        "baseline_rate_pct": baseline_rate_pct,
        "improvement_pct": round(improvement_pct, 2),
        "improvement_status": improvement_status,
        "recorded_at": datetime.now(timezone.utc),
    }

    await db.study_outcome.insert_one(outcome_record)

    # Update enrollment status
    await db.study_participants.update_one(
        {"user_id": user.user_id},
        {"$set": {"status": "completed", "outcome_recorded_at": datetime.now(timezone.utc)}},
    )

    logger.info(
        f"[STUDY] Outcome recorded for {user.user_id} pattern={pattern} "
        f"baseline={baseline_rate_pct:.2f}% → outcome={outcome_rate_pct:.2f}% "
        f"improvement={improvement_pct:.1f}% status={improvement_status}"
    )

    return {
        "status": "recorded",
        "pattern": pattern,
        "outcome_window": outcome_record["window"],
        "baseline_rate_pct": baseline_rate_pct,
        **outcome_record["measurements"],
        "improvement_pct": improvement_pct,
        "improvement_status": improvement_status,
        "message": {
            "success": "🎉 Success! Your training worked—you reduced that mistake.",
            "partial": "Good progress! You're improving.",
            "regression": "No improvement yet. Keep training—patterns take time.",
        }.get(improvement_status),
    }
