"""
Cohort Baselines Service — computes per-rating-band averages + stddev for
observation-derived signals, so downstream services (Primary Strength
Picker, coach messaging) can answer "is this rate a REAL strength, or
just their number?"

Bands are the same as primary_weakness_picker.RATING_BANDS.

Storage: `cohort_baselines` collection, one doc per (band, metric):
    {
      "band": "beginner",
      "metric": "blunder_punish_rate",
      "mean": 0.542,
      "stddev": 0.13,
      "n_users": 12,
      "computed_at": "2026-07-02T..."
    }

Only users with ≥10 analyzed games are included in the baseline —
consistent with the picker's MIN_ANALYZED_GAMES gate.
"""
import statistics
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from services.move_observation_deriver import aggregate_user_signals
from services.primary_weakness_picker import (
    _classify_band, RATING_BANDS,
)
from services.rating_resolver import get_coaching_rating


COLLECTION = "cohort_baselines"

# Metrics we compute band-level baselines for. Direction: "higher_better"
# means a high value is a strength; "lower_better" means low is strength.
METRICS: Dict[str, str] = {
    "critical_find_rate":    "higher_better",
    "threat_response_rate":  "higher_better",
    "blunder_punish_rate":   "higher_better",
    "best_move_rate":        "higher_better",
    "brilliant_rate":        "higher_better",
    "blunder_rate":          "lower_better",
    "mistake_rate":          "lower_better",
}

# Top tactical patterns we also baseline (as executions per user move)
TACTICAL_PATTERNS: List[str] = [
    "free_piece", "double_attack_line", "open_long_line", "hidden_attack",
    "rook_fork", "knight_fork", "pin", "tired_defender",
    "weak_squares", "in_between_move", "free_pawn", "pawn_hole_fianchetto",
]

MIN_ANALYZED_GAMES = 10
MIN_USERS_PER_BAND = 3   # need ≥3 users in a band to trust the mean


async def ensure_indexes(db) -> None:
    coll = db[COLLECTION]
    await coll.create_index([("band", 1), ("metric", 1)], unique=True)


async def _iter_user_metrics(db) -> List[Tuple[str, Dict[str, float]]]:
    """Compute per-user metrics for every eligible user.

    Returns list of (band, metrics_dict). One entry per user.
    """
    out: List[Tuple[str, Dict[str, float]]] = []

    async for u in db.users.find({}, {"user_id": 1}):
        uid = u["user_id"]
        n_games = await db.games.count_documents({"user_id": uid, "is_analyzed": True})
        if n_games < MIN_ANALYZED_GAMES:
            continue

        # Resolve rating + band
        user_doc = await db.users.find_one({"user_id": uid}) or {}
        profile_doc = await db.player_profiles.find_one({"user_id": uid}) or {}
        rating = await get_coaching_rating(
            db, uid, user=user_doc, profile=profile_doc
        )
        band = _classify_band(rating)

        # Pull observations (cap at 25000 — matches picker)
        obs = await db.move_observations.find({"user_id": uid}).to_list(length=25000)
        if not obs:
            continue
        sig = aggregate_user_signals(obs)
        total = sig.get("total_user_moves", 0) or 1

        ex = sig.get("execution_dist", {})
        metrics: Dict[str, float] = {
            "critical_find_rate":   sig.get("critical_find_rate") or 0.0,
            "threat_response_rate": sig.get("threat_response_rate") or 0.0,
            "blunder_punish_rate":  sig.get("blunder_punish_rate") or 0.0,
            "best_move_rate":       ex.get("best", 0) / total,
            "brilliant_rate":       ex.get("brilliant", 0) / total,
            "blunder_rate":         ex.get("blunder", 0) / total,
            "mistake_rate":         ex.get("mistake", 0) / total,
        }
        # Tactical pattern execution rates
        pat_counts = sig.get("tactical_pattern_executed_counts") or {}
        for pat in TACTICAL_PATTERNS:
            metrics[f"pattern_{pat}_rate"] = pat_counts.get(pat, 0) / total

        out.append((band, metrics))

    return out


def _band_baselines(per_user: List[Tuple[str, Dict[str, float]]]) -> Dict[str, Dict[str, Dict[str, float]]]:
    """Group by band, compute mean + stddev for each metric.

    Returns: {band: {metric: {"mean": .., "stddev": .., "n_users": ..}}}
    """
    by_band: Dict[str, List[Dict[str, float]]] = {b: [] for b in RATING_BANDS}
    for band, metrics in per_user:
        by_band[band].append(metrics)

    out: Dict[str, Dict[str, Dict[str, float]]] = {}
    for band, users in by_band.items():
        if len(users) < MIN_USERS_PER_BAND:
            continue
        out[band] = {}
        # Union of all metric keys observed
        keys = set()
        for u in users:
            keys.update(u.keys())
        for metric in keys:
            vals = [u.get(metric, 0.0) for u in users]
            mean = sum(vals) / len(vals)
            stddev = statistics.pstdev(vals) if len(vals) > 1 else 0.0
            out[band][metric] = {
                "mean": round(mean, 4),
                "stddev": round(stddev, 4),
                "n_users": len(users),
            }
    return out


async def compute_and_store(db) -> Dict[str, Any]:
    """Full recompute across all users. Idempotent."""
    await ensure_indexes(db)
    per_user = await _iter_user_metrics(db)
    baselines = _band_baselines(per_user)

    now = datetime.now(timezone.utc).isoformat()
    written = 0
    from pymongo import UpdateOne
    ops = []
    for band, metrics in baselines.items():
        for metric, stats in metrics.items():
            ops.append(UpdateOne(
                {"band": band, "metric": metric},
                {"$set": {
                    "band": band,
                    "metric": metric,
                    **stats,
                    "direction": METRICS.get(metric, "higher_better"),
                    "computed_at": now,
                }},
                upsert=True,
            ))
            written += 1
    if ops:
        await db[COLLECTION].bulk_write(ops, ordered=False)

    return {
        "users_included": len(per_user),
        "bands_computed": list(baselines.keys()),
        "metrics_written": written,
        "computed_at": now,
    }


async def get_baseline(db, band: str, metric: str) -> Optional[Dict[str, Any]]:
    """Look up one baseline entry."""
    return await db[COLLECTION].find_one({"band": band, "metric": metric})


async def get_all_baselines_for_band(db, band: str) -> Dict[str, Dict[str, float]]:
    """All baselines for one band. Returns {metric: {mean, stddev, ...}}."""
    out = {}
    async for d in db[COLLECTION].find({"band": band}):
        out[d["metric"]] = {
            "mean": d["mean"],
            "stddev": d["stddev"],
            "n_users": d.get("n_users"),
            "direction": d.get("direction"),
        }
    return out


def z_score(value: float, mean: float, stddev: float, direction: str = "higher_better") -> float:
    """Compute a signed z-score. For lower_better metrics, invert so a
    high z-score always means 'better than average'."""
    if stddev <= 0:
        return 0.0
    z = (value - mean) / stddev
    if direction == "lower_better":
        z = -z
    return round(z, 3)
