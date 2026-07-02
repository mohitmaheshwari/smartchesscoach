"""
Primary Strength Picker — parallel to primary_weakness_picker.

Picks ONE signature strength per user, based on the cohort baselines
(`cohort_baselines_service`). A rate is only a strength if the user is
≥ +0.5σ above their band's mean. Otherwise we say NOTHING — better to
stay silent than to fake a strength (the same anti-pattern that hit
piece_safety this morning).

Storage: same `user_active_focus` collection as weaknesses, with
`type: "strength"`. One active strength per user.

Also picks a signature tactical pattern: the pattern where their
per-move execution rate is ≥ 2× cohort mean AND they've executed it at
least 5 times.
"""
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from services.cohort_baselines_service import (
    get_all_baselines_for_band, z_score, METRICS, TACTICAL_PATTERNS,
)
from services.move_observation_deriver import aggregate_user_signals
from services.primary_weakness_picker import (
    _classify_band, _resolve_user_rating, _get_cohort_signals,
    _classify_rating_confidence, MIN_ANALYZED_GAMES,
)


COLLECTION = "user_active_focus"   # shared with weakness picker

MIN_Z_FOR_STRENGTH = 0.5           # rate must be at least +0.5σ above mean
MIN_PATTERN_EXECUTIONS = 5         # must have actually executed ≥5 times
MIN_PATTERN_MULTIPLE = 2.0         # rate must be ≥2× cohort mean


# Human labels for each metric (used in the narrative)
_METRIC_LABEL = {
    "critical_find_rate":   "Best-move accuracy in critical moments",
    "threat_response_rate": "Threat awareness",
    "blunder_punish_rate":  "Punishing opponent blunders",
    "best_move_rate":       "Overall move accuracy",
    "brilliant_rate":       "Brilliant moves",
    "blunder_rate":         "Low blunder rate",
    "mistake_rate":         "Low mistake rate",
}

_PATTERN_LABEL = {
    "free_piece":            "Spotting loose material",
    "double_attack_line":    "Double attacks",
    "open_long_line":        "Long-range piece play",
    "hidden_attack":         "Hidden attacks",
    "rook_fork":             "Rook forks",
    "knight_fork":           "Knight forks",
    "pin":                   "Pin tactics",
    "tired_defender":        "Overloaded-defender tactics",
    "weak_squares":          "Exploiting weak squares",
    "in_between_move":       "Zwischenzug",
    "free_pawn":             "Winning free pawns",
    "pawn_hole_fianchetto":  "Fianchetto-hole play",
}


def _user_rate_from_signals(sig: Dict[str, Any], metric: str) -> float:
    """Recompute the user's own value for a given metric from their signals."""
    total = sig.get("total_user_moves", 0) or 1
    ex = sig.get("execution_dist", {})
    if metric == "critical_find_rate":
        return sig.get("critical_find_rate") or 0.0
    if metric == "threat_response_rate":
        return sig.get("threat_response_rate") or 0.0
    if metric == "blunder_punish_rate":
        return sig.get("blunder_punish_rate") or 0.0
    if metric == "best_move_rate":
        return ex.get("best", 0) / total
    if metric == "brilliant_rate":
        return ex.get("brilliant", 0) / total
    if metric == "blunder_rate":
        return ex.get("blunder", 0) / total
    if metric == "mistake_rate":
        return ex.get("mistake", 0) / total
    if metric.startswith("pattern_"):
        # e.g. pattern_free_piece_rate
        pat = metric[len("pattern_"):-len("_rate")]
        return (sig.get("tactical_pattern_executed_counts") or {}).get(pat, 0) / total
    return 0.0


async def _fallback_band_for_expert(db) -> str:
    """Experts don't have a baseline (too few users). Compare against
    advanced band as a floor — a real expert strength will still show up."""
    advanced = await get_all_baselines_for_band(db, "advanced")
    if advanced:
        return "advanced"
    # Even advanced isn't populated → fall back to intermediate
    return "intermediate"


async def pick_signature_strength(db, user_id: str) -> Optional[Dict[str, Any]]:
    """Returns the single strongest signal for a user, or None if nothing
    beats the +0.5σ threshold."""
    n_games = await db.games.count_documents({"user_id": user_id, "is_analyzed": True})
    if n_games < MIN_ANALYZED_GAMES:
        return None

    signals, n_obs = await _get_cohort_signals(db, user_id)
    if n_obs == 0:
        return None

    rating = await _resolve_user_rating(db, user_id)
    band = _classify_band(rating)

    # Get baselines for this band; if band has no baselines, fall back
    baselines = await get_all_baselines_for_band(db, band)
    used_band = band
    used_fallback = False
    if not baselines:
        used_band = await _fallback_band_for_expert(db)
        baselines = await get_all_baselines_for_band(db, used_band)
        used_fallback = True
    if not baselines:
        return None

    # Score every metric — rate strengths + pattern strengths
    candidates = []

    # Rate metrics (critical_find, blunder_punish, etc.)
    for metric, direction in METRICS.items():
        base = baselines.get(metric)
        if not base or base["stddev"] <= 0:
            continue
        val = _user_rate_from_signals(signals, metric)
        z = z_score(val, base["mean"], base["stddev"], direction=direction)
        if z < MIN_Z_FOR_STRENGTH:
            continue
        candidates.append({
            "kind": "rate",
            "metric": metric,
            "label": _METRIC_LABEL.get(metric, metric),
            "user_value": round(val, 4),
            "cohort_mean": base["mean"],
            "cohort_stddev": base["stddev"],
            "z_score": z,
            "direction": direction,
            "sort_key": z,
        })

    # Tactical pattern executions — need ≥MIN_PATTERN_EXECUTIONS AND rate ≥2× cohort
    total = signals.get("total_user_moves", 0) or 1
    pat_counts = signals.get("tactical_pattern_executed_counts") or {}
    for pat in TACTICAL_PATTERNS:
        n_exec = pat_counts.get(pat, 0)
        if n_exec < MIN_PATTERN_EXECUTIONS:
            continue
        metric_key = f"pattern_{pat}_rate"
        base = baselines.get(metric_key)
        if not base or base["mean"] <= 0:
            continue
        user_rate = n_exec / total
        multiple = user_rate / base["mean"] if base["mean"] > 0 else 0
        if multiple < MIN_PATTERN_MULTIPLE:
            continue
        # z-score for ranking against other patterns
        stddev = base["stddev"] or (base["mean"] * 0.5)   # safe fallback for pattern
        z = z_score(user_rate, base["mean"], stddev, "higher_better")
        candidates.append({
            "kind": "pattern",
            "metric": metric_key,
            "pattern": pat,
            "label": _PATTERN_LABEL.get(pat, pat.replace("_", " ").title()),
            "user_value": round(user_rate, 4),
            "user_count": n_exec,
            "cohort_mean": base["mean"],
            "multiple_of_cohort": round(multiple, 2),
            "z_score": z,
            "direction": "higher_better",
            "sort_key": z,
        })

    if not candidates:
        return None

    # Prefer rate strengths over pattern strengths — rates are holistic
    # and their z-scores are computed against 30+ user baselines, so they
    # don't inflate the way pattern z-scores do against small cohorts.
    # Only fall through to a pattern winner if NO rate metric hits ≥1.0σ.
    rates = [c for c in candidates if c["kind"] == "rate"]
    patterns = [c for c in candidates if c["kind"] == "pattern"]
    rates.sort(key=lambda c: -c["sort_key"])
    patterns.sort(key=lambda c: -c["multiple_of_cohort"])  # pattern → use multiple, not z

    if rates and rates[0]["z_score"] >= 1.0:
        winner = rates[0]
        candidates = rates + patterns  # rates first, patterns as runners-up
    else:
        # Combined ranking; rates first when tied
        candidates = sorted(candidates, key=lambda c: (-c["sort_key"], c["kind"] != "rate"))
        winner = candidates[0]
    winner["rating"] = rating
    winner["band"] = band
    winner["baseline_band"] = used_band
    winner["baseline_fallback"] = used_fallback
    winner["runners_up"] = [
        {"kind": c["kind"], "label": c["label"], "z_score": c["z_score"]}
        for c in candidates[1:4]
    ]
    winner["narrative"] = _build_narrative(winner)
    return winner


def _build_narrative(strength: Dict[str, Any]) -> str:
    """Evidence-driven strength narrative — NO templating about band, just data."""
    if strength["kind"] == "rate":
        user_pct = round(100 * strength["user_value"], 1)
        cohort_pct = round(100 * strength["cohort_mean"], 1)
        z = strength["z_score"]
        label = strength["label"]
        band_label = strength["baseline_band"]
        band_note = f" vs the {band_label} band" + (
            " (fallback — expert baseline needs more users)" if strength.get("baseline_fallback") else ""
        )
        return (f"{label}: you land at {user_pct}%, "
                f"vs the cohort average of {cohort_pct}% at your rating"
                f"{band_note}. That's +{round(z, 1)}σ — a real signature.")
    else:
        label = strength["label"]
        n = strength["user_count"]
        multiple = strength["multiple_of_cohort"]
        return (f"{label}: you've executed this pattern {n} times, "
                f"at {multiple}× the rate of other players at your level. "
                f"You see this motif when it appears on the board.")


async def assign_strength(db, user_id: str) -> Optional[Dict[str, Any]]:
    """Pick + persist as a strength focus alongside the weakness."""
    picked = await pick_signature_strength(db, user_id)
    if not picked:
        return None
    now = datetime.now(timezone.utc)
    focus = {
        "user_id": user_id,
        "type": "strength",
        "status": "active",
        "kind": picked["kind"],
        "metric_key": picked["metric"],
        "label": picked["label"],
        "narrative": picked["narrative"],
        "user_value": picked["user_value"],
        "cohort_mean": picked.get("cohort_mean"),
        "cohort_stddev": picked.get("cohort_stddev"),
        "multiple_of_cohort": picked.get("multiple_of_cohort"),
        "z_score": picked["z_score"],
        "rating_band": picked["band"],
        "rating_used": picked["rating"],
        "baseline_band": picked["baseline_band"],
        "baseline_fallback": picked["baseline_fallback"],
        "runners_up": picked.get("runners_up", []),
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
    }
    # Upsert — replace any existing active strength (idempotent)
    await db[COLLECTION].update_one(
        {"user_id": user_id, "type": "strength", "status": "active"},
        {"$set": focus},
        upsert=True,
    )
    return focus
