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
from collections import defaultdict
from functools import lru_cache
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Opening-phase cutoff comes from the theory_tree we already have:
# `data/coaching/opening_theory_tree.json` records `main_line` (the
# canonical SAN sequence to identify the opening) and `variations`
# (deeper continuations). Real book depth = main_line + deepest
# variation continuation. Divided by 2 to get user-side plies.
# Falls back to a default when the opening isn't in the theory tree.

_THEORY_TREE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "coaching",
    "opening_theory_tree.json",
)
_OPENING_PHASE_DEFAULT_PLIES = 8  # average of computed depths


@lru_cache(maxsize=1)
def _load_theory_tree() -> Dict:
    try:
        with open(_THEORY_TREE_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return {k: v for k, v in data.items() if not k.startswith("_")}
    except Exception as e:
        logger.warning(f"could not load opening_theory_tree: {e}")
        return {}


@lru_cache(maxsize=1)
def _book_depth_user_plies_by_key() -> Dict[str, int]:
    """For each opening_key in the theory_tree, compute the book depth
    in USER plies = (main_line + deepest variation continuation) // 2,
    rounded UP so the cutoff is generous (user wants the opening
    phase to include the FULL book, not be cut early)."""
    tree = _load_theory_tree()
    out: Dict[str, int] = {}
    for key, data in tree.items():
        main = len(data.get("main_line") or [])
        deepest_var = 0
        for v in (data.get("variations") or {}).values():
            if isinstance(v, dict):
                cont = v.get("continuation") or v.get("moves_from_parent") or []
                deepest_var = max(deepest_var, len(cont))
        total_plies = main + deepest_var
        # Round UP for the user side, since variation depth maps loosely
        # to total plies and we'd rather include the last book move than
        # exclude it.
        out[key] = max(4, (total_plies + 1) // 2)
    return out

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
    phase_signal: float = 0.0,
    phase_avg: Optional[float] = None,
    phase_baseline: Optional[float] = None,
) -> str:
    """Build the per-opening one-line reason the user sees.

    Truth-discipline: only claim the opening is the problem when the
    opening-phase metric actually says so (phase_signal < 0). When the
    opening is fine but the user's whole-game record is bad, name what
    we actually see: the opening phase is fine, the losses come later.
    """
    rewards = demand.get("rewards_descriptor") or "your style"
    pct = int(round(user_winrate * 100))

    # Positive fit → recommend.
    if fit > 0.05:
        if user_winrate - baseline >= 0.10:
            return f"{pct}% wins · rewards {rewards}"
        return f"rewards {rewards}"

    # Negative fit → explain WHY honestly.
    if fit < -0.05:
        # Opening phase IS measurably worse than baseline.
        if phase_signal < -0.2 and phase_avg is not None and phase_baseline is not None:
            gap_cp = round(phase_avg - phase_baseline)
            base_msg = (
                f"{pct}% wins · opening phase {gap_cp}cp worse "
                f"than your usual"
            )
            if user_gaps_matching:
                from services.game_mirror import _PATTERN_VOICE
                gap_voice = _PATTERN_VOICE.get(
                    user_gaps_matching[0], {}
                ).get("noun") or user_gaps_matching[0].replace("_", " ")
                return f"{base_msg} ({gap_voice} likely showing here)"
            return base_msg

        # Opening phase is FINE — the problem is elsewhere in the game.
        # Don't blame the opening when the data doesn't support it.
        if phase_signal >= -0.2:
            return (
                f"{pct}% wins · opening itself is fine — losses come "
                f"after the opening"
            )

        # Fallback (no phase data).
        return f"{pct}% wins · poor fit overall"

    return f"{pct}% wins · neutral fit"


async def _opening_phase_cp_by_family(db, user_id: str) -> Tuple[Dict[str, Tuple[float, int]], float]:
    """For each canonical opening family the user has played, compute
    the user's average cp_loss per move in the first N user plies of
    each game — where N depends on that opening's theory_burden so the
    cutoff scales with actual chess theory depth.

    Returns ({canonical_name: (avg_cp_per_move, n_games)}, baseline_avg).
    `baseline_avg` is the user's overall average opening-phase cp_loss
    across all families — the comparison point.

    `move_evaluations` stores ONE entry per user ply (verified earlier),
    so moves[:N] gives us user plies 1..N for that game.
    """
    from services.opening_normalizer import (
        normalize_opening,
        curriculum_key_for_opening,
    )

    demands = _load_demands()

    games = await db.games.find(
        {
            "user_id": user_id,
            "is_analyzed": True,
            "termination": {"$not": {"$regex": "abandon", "$options": "i"}},
        },
        {"_id": 0, "game_id": 1, "opening": 1, "user_color": 1},
    ).to_list(500)
    if not games:
        return {}, 0.0

    games_by_id = {g["game_id"]: g for g in games if g.get("game_id")}
    if not games_by_id:
        return {}, 0.0

    # Helper: resolve a game's per-game opening cutoff in user plies
    # from the theory_tree's actual main_line + variation depth. This
    # uses real chess data, not subjective buckets — Italian's depth
    # comes out around 7 plies, Sicilian Defense's around 9, etc.
    book_depth_map = _book_depth_user_plies_by_key()

    def _cutoff_for_game(g: Dict) -> int:
        canon = normalize_opening(g.get("opening"))
        color = (g.get("user_color") or "white").lower()
        key = curriculum_key_for_opening(canon, color)
        if not key:
            return _OPENING_PHASE_DEFAULT_PLIES
        # Strip color suffix when looking up theory tree (which uses
        # uncolored keys like "italian_game").
        base_key = key.replace("_black", "").replace("_white", "")
        return book_depth_map.get(base_key, _OPENING_PHASE_DEFAULT_PLIES)

    per_game_avg: Dict[str, float] = {}
    async for a in db.game_analyses.find(
        {"user_id": user_id, "game_id": {"$in": list(games_by_id.keys())}},
        {"_id": 0, "game_id": 1, "stockfish_analysis.move_evaluations": 1},
    ):
        gid = a.get("game_id")
        game = games_by_id.get(gid)
        if not game:
            continue
        cutoff = _cutoff_for_game(game)
        moves = (a.get("stockfish_analysis") or {}).get("move_evaluations") or []
        opening_moves = moves[:cutoff]
        cp_losses = [
            abs(m.get("cp_loss") or 0)
            for m in opening_moves
            if (m.get("cp_loss") is not None and abs(m.get("cp_loss") or 0) < 3000)
        ]
        if cp_losses:
            per_game_avg[gid] = sum(cp_losses) / len(cp_losses)

    if not per_game_avg:
        return {}, 0.0

    # Group per-game avg by canonical opening family.
    by_family: Dict[str, List[float]] = defaultdict(list)
    for gid, avg in per_game_avg.items():
        canon = normalize_opening(games_by_id[gid].get("opening"))
        if canon == "Other":
            continue
        by_family[canon].append(avg)

    family_avg = {
        fam: (sum(vals) / len(vals), len(vals))
        for fam, vals in by_family.items()
    }

    # Baseline: average across all per-game opening-phase cp_loss values.
    all_vals = list(per_game_avg.values())
    baseline = sum(all_vals) / len(all_vals) if all_vals else 0.0
    return family_avg, baseline


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

    # Opening-phase performance per family — the corrected "is this
    # opening actually a problem for me?" signal. Whole-game win rate
    # conflated middlegame/endgame losses into "Italian is bad for you."
    # This isolates the opening phase itself.
    phase_by_family, phase_baseline = await _opening_phase_cp_by_family(db, user_id)

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

        # Opening-phase signal — the honest "is the opening itself a
        # problem?" measure. Positive when the user plays this opening
        # MORE accurately than their personal baseline; negative when
        # they play it WORSE. Scaled by 50 so a 50cp gap maps to ~1.0.
        canon = stats.get("canonical")
        phase_signal = 0.0
        phase_avg = None
        phase_n = 0
        if canon and canon in phase_by_family and phase_baseline > 0:
            phase_avg, phase_n = phase_by_family[canon]
            phase_signal = (phase_baseline - phase_avg) / 50.0
            # Clamp so a single noisy opening can't dominate the score.
            phase_signal = max(-1.0, min(1.0, phase_signal))

        matching = [g for g in user_gaps if g in (demand.get("punishes") or [])]
        weakness_score = _weakness_penalty(rating) * len(matching)
        theory_score = _theory_penalty(rating, demand.get("theory_burden", 0.0))

        # Fit blends opening-phase performance (primary) with whole-game
        # win rate (secondary tiebreaker). The phase signal carries 0.5
        # weight; the win-rate signal weighs 0.25 — half of what it was
        # before — since whole-game results are not a clean opening
        # quality measure.
        fit = (
            phase_signal * 0.5
            + winrate_signal * 0.5
            - weakness_score
            - theory_score
        )

        # Display name correction. Some openings' name implies a side
        # (e.g., "Sicilian Defense" — black plays the defense). When the
        # user's color doesn't match the opening's natural side, prefix
        # with "vs " so we don't say "Sicilian Defense (white)" to a
        # player who's actually playing 1.e4 against a Sicilian.
        natural_color = (demand.get("color") or "").lower()
        display_name = demand.get("name") or stats["canonical"]
        if natural_color and natural_color != stats["color"]:
            # Strip a trailing "(Black side)" / "(White side)" if our
            # data already captures it, then prefix "vs ".
            base = display_name.split("(")[0].strip()
            display_name = f"vs {base}"

        scored.append({
            "opening_key": opening_key,
            "name": display_name,
            "color": stats["color"],
            "fit": round(fit, 3),
            "win_rate": round(win_rate, 3),
            "games_played": games,
            "matching_gaps": matching,
            "phase_avg_cp": round(phase_avg, 1) if phase_avg is not None else None,
            "phase_baseline_cp": round(phase_baseline, 1) if phase_baseline else None,
            "phase_signal": round(phase_signal, 3),
            "reason": _voice_reason(
                fit, matching, demand, win_rate, baseline_winrate,
                phase_signal=phase_signal,
                phase_avg=phase_avg,
                phase_baseline=phase_baseline,
            ),
            "theory_burden": demand.get("theory_burden"),
        })

    if not scored:
        return empty

    scored.sort(key=lambda e: -e["fit"])
    play_more = [e for e in scored if e["fit"] > 0.05][:3]

    # Avoid list. Three independent gates:
    #   1. Negative fit (the score itself says "not great")
    #   2. Below-baseline whole-game win rate (you're losing more here
    #      than your overall play would predict)
    #   3. Opening-phase signal is actually negative — the opening
    #      ITSELF is where things go wrong, not just the middlegame.
    # Without #3, we'd say "avoid Italian — losing 70%" when the
    # opening phase is actually fine; that's just bad whole-game play
    # and a different conversation.
    avoid = sorted(
        [
            e for e in scored
            if e["fit"] < -0.05
            and e["win_rate"] < baseline_winrate
            and (e.get("phase_signal") or 0) < -0.05
        ],
        key=lambda e: e["fit"],
    )[:2]

    return {
        "has_data": bool(play_more or avoid),
        "rating_used": rating,
        "play_more": play_more,
        "avoid": avoid,
    }


async def opening_in_avoid_list(db, user_id: str, opening_key: str) -> bool:
    """Returns True if `opening_key` is currently in the user's "avoid"
    recommendations — used by Play-with-Coach to suppress force-offering
    teaching for openings the user shouldn't be grinding right now.

    Honest gating: if we have no fit data (cold start, too few games),
    returns False so the existing offer flow remains intact.
    """
    if not opening_key:
        return False
    try:
        fit = await build_opening_fit(db, user_id)
    except Exception as e:
        logger.debug(f"opening_in_avoid_list lookup failed: {e}")
        return False
    if not fit.get("has_data"):
        return False
    return any(
        (o.get("opening_key") == opening_key)
        for o in (fit.get("avoid") or [])
    )
