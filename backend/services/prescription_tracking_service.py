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
MIN_GAMES_AFTER_TRAINING = 3  # Need at least 3 analyzed games to calculate improvement
MIN_BASELINE_GAMES = 3  # Need at least 3 analyzed games for a valid baseline
BASELINE_MAX_GAMES = 20  # Baseline window: last N analyzed games before training


def _normalize_game_date(date_played) -> Optional[str]:
    """Games store date_played as '2026.03.01' (chess.com PGN) or ISO strings.
    Normalize to a lexicographically-comparable 'YYYY-MM-DD'."""
    if not date_played:
        return None
    s = str(date_played).replace(".", "-")[:10]
    return s if len(s) == 10 else None


async def calculate_gap_rate(
    db,
    user_id: str,
    cognitive_gap: str,
    before_date: Optional[str] = None,
    after_date: Optional[str] = None,
    max_games: Optional[int] = None,
) -> Tuple[float, int]:
    """Per-game average cp_loss in a cognitive gap over a date window.

    THE metric for prescription tracking (2026-07-14 fix). The old version
    compared a lifetime SUM against a 7-day SUM — a bigger history guaranteed
    ">50% improvement" the moment 3 games existed, so auto-close measured
    window size, not skill. This one is a rate: total gap cp_loss divided by
    the number of ANALYZED games in the window (all analyzed games, not just
    games where the gap appeared — incidence dropping must lower the rate).

    Returns (avg_cp_loss_per_analyzed_game, analyzed_games_count).
    """
    try:
        games = await db.games.find(
            {"user_id": user_id},
            {"_id": 0, "game_id": 1, "date_played": 1},
        ).to_list(None)

        windowed = []
        for g in games:
            d = _normalize_game_date(g.get("date_played"))
            if not d:
                continue
            if before_date and d >= before_date:
                continue
            if after_date and d < after_date:
                continue
            windowed.append((d, g["game_id"]))

        if not windowed:
            return (0.0, 0)

        # Most recent first; cap the window (baselines use the last N games).
        windowed.sort(reverse=True)
        if max_games:
            windowed = windowed[:max_games]
        game_ids = [gid for _, gid in windowed]

        analyses = await db.game_analyses.find(
            {"game_id": {"$in": game_ids}},
            {"_id": 0, "game_id": 1, "stockfish_analysis.move_evaluations": 1},
        ).to_list(None)

        analyzed_count = len(analyses)
        if analyzed_count == 0:
            return (0.0, 0)

        total_cp_loss = 0.0
        for analysis in analyses:
            moves = analysis.get("stockfish_analysis", {}).get("move_evaluations", [])
            for move in moves:
                if move.get("is_opponent_move"):
                    continue
                if move.get("cognitive_gap") == cognitive_gap and (move.get("cp_loss") or 0) > 0:
                    total_cp_loss += move["cp_loss"]

        return (total_cp_loss / analyzed_count, analyzed_count)

    except Exception as e:
        logger.error(f"Error calculating gap rate: {e}")
        return (0.0, 0)


def _started_date(started_at) -> Optional[str]:
    """Prescription started_at (datetime or ISO string) -> 'YYYY-MM-DD'."""
    try:
        if isinstance(started_at, datetime):
            return started_at.date().isoformat()
        return str(started_at)[:10] if started_at else None
    except Exception:
        return None


async def compute_prescription_progress(db, pres: Dict) -> Dict:
    """Single source of prescription-progress math, used by the progress
    endpoint, auto-close eligibility, and the worker trigger. Recomputes the
    baseline fresh (per-game rate over the last BASELINE_MAX_GAMES analyzed
    games BEFORE training started) so prescriptions created under the old
    sum-based metric self-heal instead of comparing incompatible numbers."""
    cognitive_gap = pres.get("issue_detected") or ""
    start_date = _started_date(pres.get("started_at"))
    result = {
        "cognitive_gap": cognitive_gap,
        "baseline_avg": 0.0,
        "baseline_games": 0,
        "current_avg": 0.0,
        "current_games": 0,
        "improvement": 0.0,
        "eligible": False,
        "reason": None,
    }
    if not cognitive_gap:
        result["reason"] = "no_cognitive_gap"
        return result
    if not start_date:
        result["reason"] = "not_started"
        return result

    baseline_avg, baseline_games = await calculate_gap_rate(
        db, pres["user_id"], cognitive_gap,
        before_date=start_date, max_games=BASELINE_MAX_GAMES,
    )
    current_avg, current_games = await calculate_gap_rate(
        db, pres["user_id"], cognitive_gap, after_date=start_date,
    )
    improvement = calculate_improvement_percentage(baseline_avg, current_avg)

    result.update({
        "baseline_avg": round(baseline_avg, 1),
        "baseline_games": baseline_games,
        "current_avg": round(current_avg, 1),
        "current_games": current_games,
        "improvement": improvement,
    })

    if baseline_games < MIN_BASELINE_GAMES or baseline_avg <= 0:
        result["reason"] = "invalid_baseline"
    elif current_games < MIN_GAMES_AFTER_TRAINING:
        result["reason"] = "insufficient_games_after_start"
    elif improvement < IMPROVEMENT_THRESHOLD_FOR_CLOSE:
        result["reason"] = "insufficient_improvement"
    else:
        result["eligible"] = True
    return result


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
    baseline_cp_loss: float = 0.0,  # kept for signature compat; recomputed internally
    started_at_str: str = "",
) -> Tuple[bool, Dict]:
    """Check if a prescription is eligible for auto-close.

    Delegates to compute_prescription_progress (the single source of the
    per-game-rate math). The stored baseline_metric is IGNORED — old
    prescriptions stored a lifetime SUM whose comparison was broken; the
    baseline is recomputed as a pre-start per-game rate every time.
    """
    try:
        pres = await db.user_coaching_prescriptions.find_one(
            {"prescription_id": prescription_id, "user_id": user_id},
            {"_id": 0}
        )
        if not pres:
            return (False, {"error": "Prescription not found"})

        progress = await compute_prescription_progress(db, pres)
        meta = {
            "baseline": progress["baseline_avg"],
            "baseline_games": progress["baseline_games"],
            "current": progress["current_avg"],
            "improvement": progress["improvement"],
            "games_trained": progress["current_games"],
            "threshold": IMPROVEMENT_THRESHOLD_FOR_CLOSE,
        }
        if progress["eligible"]:
            return (True, meta)
        meta["reason"] = progress["reason"]
        return (False, meta)

    except Exception as e:
        logger.error(f"Error checking auto-close eligibility: {e}")
        return (False, {"error": str(e)})


async def run_auto_close_for_user(db, user_id: str) -> List[Dict]:
    """Check every ACTIVE prescription for a user and auto-close the ones
    whose targeted gap has measurably improved (>=50% lower per-game rate
    over >=3 analyzed games). THE trigger wire (2026-07-14): called by the
    analysis worker after each game analysis and by POST /coaching/check-auto-close.
    On close: records final metrics AND notifies the user — the visible
    'you fixed it' moment the loop was missing.

    Returns a list of result dicts (one per active prescription).
    """
    results = []
    try:
        active = await db.user_coaching_prescriptions.find(
            {"user_id": user_id, "status": "active"}, {"_id": 0}
        ).to_list(None)

        for pres in active:
            progress = await compute_prescription_progress(db, pres)
            row = {
                "prescription_id": pres.get("prescription_id"),
                "cognitive_gap": progress["cognitive_gap"],
                "eligible": progress["eligible"],
                "improvement": progress["improvement"],
                "reason": progress["reason"],
                "action_taken": "none",
            }
            if progress["eligible"]:
                ok = await mark_prescription_complete(
                    db, pres["prescription_id"], user_id,
                    progress["baseline_avg"], progress["current_avg"],
                )
                if ok:
                    row["action_taken"] = "auto_closed"
                    gap_label = progress["cognitive_gap"].replace("_", " ").title()
                    pct = int(round(progress["improvement"] * 100))
                    try:
                        await db.notifications.insert_one({
                            "user_id": user_id,
                            "type": "prescription_completed",
                            "title": f"🎉 {gap_label} — trained and fixed",
                            "message": (
                                f"Your {gap_label} mistakes are down {pct}% per game "
                                f"since you started training it ({progress['current_games']} games measured). "
                                f"Plan complete — the coach will pick your next focus."
                            ),
                            "data": {
                                "prescription_id": pres.get("prescription_id"),
                                "improvement_pct": pct,
                                "games_measured": progress["current_games"],
                            },
                            "read": False,
                            "created_at": datetime.now(timezone.utc).isoformat(),
                        })
                    except Exception as notif_err:
                        logger.warning(f"Auto-close notification failed (non-fatal): {notif_err}")
                    logger.info(
                        f"[auto-close] {pres.get('prescription_id')} closed for {user_id}: "
                        f"{progress['cognitive_gap']} improved {pct}%"
                    )
            results.append(row)
    except Exception as e:
        logger.error(f"run_auto_close_for_user failed for {user_id}: {e}")
    return results


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
