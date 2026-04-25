"""
Opening Fit Recommender
=======================

Combines three signals to recommend openings to play more / avoid:
  1. Actual win rate per opening (from opening_report_card)
  2. User's established weakness patterns (from game_mirror)
  3. Curated per-opening characteristics (data/opening_demands.json)

Output: a coach-voice "play more" / "avoid for now" list, scaled by
the user's rating so the same logic works for a 1200 or an 1800.

Honest gating:
  • Need ≥3 games in an opening before we'll claim a win-rate signal
  • Need at least 5 total analyzed games before we'll show recommendations
  • If we have no data on a curated opening, we skip it — never invent

Scoring (rating-aware):

    fit = (winrate - baseline) * 0.5
         - sum(weakness_penalty(rating) for gap in user_gaps
                                          if gap in opening.punishes)
         - theory_penalty(rating, opening.theory_burden)

    weakness_penalty(rating) = 0.20 * (1 + (1500 - rating) / 1000)
        # 1200 → 0.26 (heavy)   1800 → 0.14 (light)   2000+ → 0.10
    theory_penalty(rating, burden) = 0.3 * burden * max(0, (1500 - rating) / 1000)
        # 1200, burden 0.8 → 0.072   1500+ → 0 regardless of burden
"""

from __future__ import annotations

import json
import logging
import os
from functools import lru_cache
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_DEMANDS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "opening_demands.json",
)

# Minimum games before we'll claim a fit verdict on any opening.
MIN_GAMES_PER_OPENING = 3
# Minimum total analyzed games before we surface ANY recommendation.
MIN_TOTAL_GAMES = 5
# Default rating when none is known. Bias toward neutral so we don't
# over-penalize — better to under-warn than mis-warn.
DEFAULT_RATING = 1500


@lru_cache(maxsize=1)
def _load_demands() -> Dict[str, Dict]:
    try:
        with open(_DEMANDS_PATH, encoding="utf-8") as f:
            data = json.load(f)
        # Drop the _meta entry — it's documentation, not a real opening.
        return {k: v for k, v in data.items() if not k.startswith("_")}
    except Exception as e:
        logger.warning(f"could not load opening_demands: {e}")
        return {}


def _weakness_penalty(rating: int) -> float:
    """Per-matching-pattern penalty. Heavier for lower-rated players
    because their weaknesses cost them more in real games."""
    return 0.20 * (1.0 + (1500 - rating) / 1000.0)


def _theory_penalty(rating: int, theory_burden: float) -> float:
    """How much the opening's memorization cost hurts THIS user.
    Zero above 1500; scales linearly below."""
    if rating >= 1500:
        return 0.0
    return 0.3 * theory_burden * (1500 - rating) / 1000.0


def _voice_reason(
    fit: float,
    user_gaps_matching: List[str],
    demand: Dict,
    user_winrate: float,
    baseline: float,
) -> str:
    """Build the per-opening one-line reason the user sees."""
    rewards = demand.get("rewards_descriptor") or "your style"
    pct = int(round(user_winrate * 100))
    if fit > 0.05:
        if user_winrate - baseline >= 0.10:
            return f"{pct}% wins · rewards {rewards}"
        return f"rewards {rewards}"
    if fit < -0.05:
        if user_gaps_matching:
            from services.game_mirror import _PATTERN_VOICE
            gap_voice = _PATTERN_VOICE.get(
                user_gaps_matching[0], {}
            ).get("noun") or user_gaps_matching[0].replace("_", " ")
            return (
                f"{pct}% wins · your {gap_voice} pattern keeps getting "
                f"punished here"
            )
        return f"{pct}% wins · poor fit for your current play"
    return f"{pct}% wins · neutral fit"


async def build_opening_fit(db, user_id: str) -> Dict:
    """Top-level: return ranked play_more + avoid lists for the user.

    Returns:
      {
        "has_data": bool,
        "rating_used": int,
        "play_more": [{opening_key, name, color, fit, win_rate,
                       games_played, reason}, ...],
        "avoid":     [...],
      }
    """
    empty = {
        "has_data": False,
        "rating_used": DEFAULT_RATING,
        "play_more": [],
        "avoid": [],
    }

    demands = _load_demands()
    if not demands:
        return empty

    # Reuse the existing opening report card — gives us per-opening
    # win rates by color in the canonical-family name space.
    from services.opening_report_card import get_user_opening_report
    report = await get_user_opening_report(db, user_id)
    if not report.get("has_data") or report.get("total_games", 0) < MIN_TOTAL_GAMES:
        return empty

    total_games = report.get("total_games", 0)
    overall_wins = 0
    for entry in report.get("all_openings_flat") or []:
        overall_wins += entry.get("wins", 0)
    baseline_winrate = (overall_wins / total_games) if total_games else 0.5

    # Established patterns drive the weakness penalties.
    from services.game_mirror import get_established_patterns
    user_gaps, _ = await get_established_patterns(db, user_id)

    # User rating — pull the same way coach_play does (most-recent
    # PGN-derived rating, falling back to default).
    rating = DEFAULT_RATING
    try:
        from services.coach_memory import get_user_rating_from_games
        rating_data = await get_user_rating_from_games(db, user_id)
        rating = int(rating_data.get("rating", DEFAULT_RATING))
    except Exception as e:
        logger.debug(f"rating lookup fallback for {user_id}: {e}")

    # Map canonical opening names → curriculum keys, then to demands.
    from services.opening_normalizer import curriculum_key_for_opening

    # Build a {curriculum_key: per-color stats} dict from the report.
    user_stats_by_key: Dict[str, Dict] = {}
    for color in ("white", "black"):
        for canonical_name, stats in (report.get(f"as_{color}") or {}).items():
            key = curriculum_key_for_opening(canonical_name, color)
            if not key:
                continue
            if key in demands:
                user_stats_by_key[key] = {
                    "games": stats.get("games", 0),
                    "win_rate": stats.get("win_rate", 0.0),
                    "color": color,
                    "canonical": canonical_name,
                }

    if not user_stats_by_key:
        return empty

    # Score each (opening_key, color) the user has actually played.
    scored: List[Dict] = []
    for opening_key, stats in user_stats_by_key.items():
        games = stats["games"]
        if games < MIN_GAMES_PER_OPENING:
            continue  # too thin to claim a fit verdict
        demand = demands[opening_key]

        win_rate = stats["win_rate"]
        winrate_signal = (win_rate - baseline_winrate) * 0.5

        matching = [g for g in user_gaps if g in (demand.get("punishes") or [])]
        weakness_score = _weakness_penalty(rating) * len(matching)
        theory_score = _theory_penalty(rating, demand.get("theory_burden", 0.0))

        fit = winrate_signal - weakness_score - theory_score

        scored.append({
            "opening_key": opening_key,
            "name": demand.get("name") or stats["canonical"],
            "color": stats["color"],
            "fit": round(fit, 3),
            "win_rate": round(win_rate, 3),
            "games_played": games,
            "matching_gaps": matching,
            "reason": _voice_reason(
                fit, matching, demand, win_rate, baseline_winrate,
            ),
            "theory_burden": demand.get("theory_burden"),
        })

    if not scored:
        return empty

    scored.sort(key=lambda e: -e["fit"])
    play_more = [e for e in scored if e["fit"] > 0.05][:3]
    avoid = sorted(
        [e for e in scored if e["fit"] < -0.05],
        key=lambda e: e["fit"],
    )[:2]

    return {
        "has_data": bool(play_more or avoid),
        "rating_used": rating,
        "play_more": play_more,
        "avoid": avoid,
    }
