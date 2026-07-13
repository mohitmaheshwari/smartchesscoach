"""
Prescription Tracking Service
============================

Handles baseline metric calculation, improvement tracking, and auto-close logic
for active training prescriptions.

Philosophy:
- baseline_metric = cp_loss in the gap BEFORE training starts
- current_metric = cp_loss in the gap AFTER training starts (or last 7 days)
- improvement_pct = (baseline - current) / baseline * 100
- Auto-close when improvement >= 50%

The coaching loop: User identifies gap → Training starts → System tracks improvement →
Automatically recognizes mastery → Closes plan → Next focus
"""

import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

# Thresholds for auto-close
IMPROVEMENT_THRESHOLD_FOR_CLOSE = 0.50  # 50% improvement triggers auto-close
MIN_GAMES_AFTER_TRAINING = 3  # Need at least 3 games to calculate improvement
MIN_BASELINE_GAMES = 2  # Need at least 2 games in gap for valid baseline


async def calculate_baseline_metric(
    db,
    user_id: str,
    cognitive_gap: str,
) -> Tuple[float, int]:
    """
    Calculate baseline metric: total cp_loss in the cognitive_gap before training.

    Returns:
        (baseline_cp_loss: float, games_count: int)
        - baseline_cp_loss: sum of all cp_loss in this gap from all user games
        - games_count: number of games where this gap appeared

    Edge cases:
        - No games in gap → (0.0, 0)
        - No analyses yet → (0.0, 0)
    """
    try:
        # Fetch all user games
        games = await db.games.find({"user_id": user_id}).to_list(None)
        if not games:
            logger.info(f"No games found for user {user_id}")
            return (0.0, 0)

        game_ids = [g["game_id"] for g in games]

        # Fetch all analyses for these games
        analyses = await db.game_analyses.find(
            {"game_id": {"$in": game_ids}}
        ).to_list(None)

        # Sum cp_loss for moves in this cognitive_gap
        total_cp_loss = 0.0
        games_with_gap = set()

        for analysis in analyses:
            moves = analysis.get("stockfish_analysis", {}).get("move_evaluations", [])
            for move in moves:
                # Only count user mistakes (not opponent moves)
                if move.get("is_opponent_move"):
                    continue

                gap = move.get("cognitive_gap")
                cp_loss = move.get("cp_loss", 0)

                if gap == cognitive_gap and cp_loss > 0:
                    total_cp_loss += cp_loss
                    game_id = analysis.get("game_id")
                    if game_id:
                        games_with_gap.add(game_id)

        games_count = len(games_with_gap)
        logger.info(
            f"Baseline for user {user_id} gap {cognitive_gap}: "
            f"cp_loss={total_cp_loss} from {games_count} games"
        )

        return (total_cp_loss, games_count)

    except Exception as e:
        logger.error(f"Error calculating baseline metric: {e}")
        return (0.0, 0)


async def calculate_current_metric(
    db,
    user_id: str,
    cognitive_gap: str,
    started_at: datetime,
    days_window: int = 7,
) -> Tuple[float, int]:
    """
    Calculate current metric: cp_loss in the gap AFTER training started.

    Args:
        user_id: user identifier
        cognitive_gap: the gap being trained on
        started_at: when training started
        days_window: look back this many days (default 7)

    Returns:
        (current_cp_loss: float, games_count: int)
        - current_cp_loss: sum of cp_loss in this gap from games after training start
        - games_count: number of games in the window
    """
    try:
        # Fetch user games after training started
        cutoff_date = started_at.isoformat() if isinstance(started_at, datetime) else started_at

        games = await db.games.find({
            "user_id": user_id,
            "date_played": {"$gte": cutoff_date}
        }).to_list(None)

        if not games:
            logger.info(f"No games after training start for user {user_id}")
            return (0.0, 0)

        game_ids = [g["game_id"] for g in games]

        # Fetch analyses
        analyses = await db.game_analyses.find(
            {"game_id": {"$in": game_ids}}
        ).to_list(None)

        # Sum cp_loss in this gap
        total_cp_loss = 0.0
        games_with_gap = set()

        for analysis in analyses:
            moves = analysis.get("stockfish_analysis", {}).get("move_evaluations", [])
            for move in moves:
                if move.get("is_opponent_move"):
                    continue

                gap = move.get("cognitive_gap")
                cp_loss = move.get("cp_loss", 0)

                if gap == cognitive_gap and cp_loss > 0:
                    total_cp_loss += cp_loss
                    game_id = analysis.get("game_id")
                    if game_id:
                        games_with_gap.add(game_id)

        games_count = len(games_with_gap)
        logger.info(
            f"Current metric for user {user_id} gap {cognitive_gap}: "
            f"cp_loss={total_cp_loss} from {games_count} games"
        )

        return (total_cp_loss, games_count)

    except Exception as e:
        logger.error(f"Error calculating current metric: {e}")
        return (0.0, 0)


def calculate_improvement_percentage(
    baseline_cp_loss: float,
    current_cp_loss: float,
) -> float:
    """
    Calculate improvement percentage.

    Formula: (baseline - current) / baseline * 100

    Edge cases:
        - baseline == 0 → 0.0 (no baseline, can't measure)
        - baseline < current → 0.0 (regression, no improvement)
        - baseline >= current → positive improvement
    """
    if baseline_cp_loss <= 0:
        return 0.0

    improvement = (baseline_cp_loss - current_cp_loss) / baseline_cp_loss
    return max(0.0, improvement)  # Cap at 0 (no negative improvement)


async def check_auto_close_eligibility(
    db,
    prescription_id: str,
    user_id: str,
    baseline_cp_loss: float,
    started_at_str: str,
) -> Tuple[bool, Dict]:
    """
    Check if a prescription is eligible for auto-close.

    Criteria:
        1. Baseline must be valid (>0 and from >= 2 games)
        2. Started >= 3 games ago
        3. Current improvement >= 50%

    Returns:
        (should_close: bool, metadata: dict with details)
    """
    try:
        # Parse started_at
        started_at = datetime.fromisoformat(started_at_str.replace('Z', '+00:00'))
        now = datetime.now(timezone.utc)
        days_since_start = (now - started_at).days

        # Get prescription data to find cognitive_gap
        pres = await db.user_coaching_prescriptions.find_one(
            {"prescription_id": prescription_id, "user_id": user_id},
            {"_id": 0}
        )

        if not pres:
            return (False, {"error": "Prescription not found"})

        cognitive_gap = pres.get("issue_detected")  # The gap being trained
        if not cognitive_gap:
            return (False, {"error": "No cognitive gap in prescription"})

        # Check minimum time elapsed (at least 3 games since start)
        current_cp, games_count = await calculate_current_metric(
            db, user_id, cognitive_gap, started_at
        )

        if games_count < MIN_GAMES_AFTER_TRAINING:
            return (False, {
                "reason": "insufficient_games_after_start",
                "games": games_count,
                "min_required": MIN_GAMES_AFTER_TRAINING,
            })

        # Check baseline validity
        if baseline_cp_loss <= 0:
            return (False, {
                "reason": "invalid_baseline",
                "baseline": baseline_cp_loss,
            })

        # Calculate improvement
        improvement = calculate_improvement_percentage(baseline_cp_loss, current_cp)

        if improvement >= IMPROVEMENT_THRESHOLD_FOR_CLOSE:
            return (True, {
                "baseline": baseline_cp_loss,
                "current": current_cp,
                "improvement": improvement,
                "days_since_start": days_since_start,
                "games_trained": games_count,
            })
        else:
            return (False, {
                "reason": "insufficient_improvement",
                "improvement": improvement,
                "threshold": IMPROVEMENT_THRESHOLD_FOR_CLOSE,
                "baseline": baseline_cp_loss,
                "current": current_cp,
            })

    except Exception as e:
        logger.error(f"Error checking auto-close eligibility: {e}")
        return (False, {"error": str(e)})


async def mark_prescription_complete(
    db,
    prescription_id: str,
    user_id: str,
    baseline_cp_loss: float,
    current_cp_loss: float,
) -> bool:
    """
    Mark a prescription as completed and record final metrics.

    Returns:
        bool: True if update succeeded
    """
    try:
        now = datetime.now(timezone.utc)
        improvement = calculate_improvement_percentage(baseline_cp_loss, current_cp_loss)

        result = await db.user_coaching_prescriptions.update_one(
            {
                "prescription_id": prescription_id,
                "user_id": user_id,
            },
            {
                "$set": {
                    "status": "completed",
                    "completed_at": now.isoformat(),
                    "current_metric": current_cp_loss,
                    "improvement_pct": improvement,
                    "updated_at": now.isoformat(),
                }
            }
        )

        if result.modified_count > 0:
            logger.info(
                f"Prescription {prescription_id} marked complete. "
                f"Improvement: {improvement*100:.1f}%"
            )
            return True
        else:
            logger.warning(f"No prescription found to update: {prescription_id}")
            return False

    except Exception as e:
        logger.error(f"Error marking prescription complete: {e}")
        return False
