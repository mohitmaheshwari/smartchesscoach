"""
Move-Quality Rating — the coach's own read of a player's strength.

WHY this exists (docs/move_quality_rating_scope.md, Mohit 2026-07-06):
Move-quality is the only signal that measures a player's *chess* — not their
internet, their clock, or their focus. A chess.com/lichess rating is contaminated
by timeouts and distraction, so it isn't "real" strength for a coaching product.

WHAT it is, honestly (all decided from data, not guessed):
  - Metric: the existing per-game `accuracy` (Lichess formula from ACPL). A fancy
    error-rate composite was tried and did NOT beat accuracy (LOOCV 281 vs 264),
    so we don't build it.
  - Recency: a MOVE-WEIGHTED exponential decay (half-life ~30 games). A hard
    10-15 game window swings ±600 game-to-game; half-life 30 settles jitter to
    ~15/game while still tracking a real multi-week climb.
  - Output: a BAND, never a point. MAE is ~230 in the 600-1500 band, and the
    absolute value is methodology-sensitive (~±350), so we show `~low–high`.
  - Range of validity: authoritative for ~600-1500 (ChessGuru's market). Every
    move-level metric SATURATES above ~1500-1600 (a real 1755 reads ~1290 on
    30k moves), so above that the caller should defer to the imported rating.

This module is PURE + deterministic (accuracy in, band out) — no engine, no LLM.
Intended to be computed periodically (e.g. after each analysed game) and cached,
not recomputed on every PWC start.
"""
from __future__ import annotations

import math
import os
from typing import Any, Dict, List, Optional

# ── Constants (data-locked 2026-07-06) ──────────────────────────────────────
HALF_LIFE_GAMES = 30           # recency: older games fade by half every 30 games
MIN_GAMES = 5                  # below this we don't show a rating (too little data)
MAP_SLOPE = 70.5               # rating = SLOPE * move_weighted_accuracy + INTERCEPT
MAP_INTERCEPT = -3154          #   (re-fit on 47 known-rating users, move-weighted)
RATING_MIN, RATING_MAX = 100, 2600
SATURATION_CEILING = 1600      # above this, move-quality can't resolve — defer to imported

FLAG = "PWC_MOVE_QUALITY_RATING"


def enabled() -> bool:
    """Feature flag — default OFF; flipped on at deploy."""
    return os.environ.get(FLAG, "false").lower() == "true"


def _map_accuracy_to_rating(acc: float) -> int:
    r = MAP_SLOPE * acc + MAP_INTERCEPT
    return int(round(max(RATING_MIN, min(RATING_MAX, r))))


def _band_halfwidth(n_games: int) -> int:
    """Honest range around the point estimate. Wider when we have less data —
    at the MIN_GAMES floor the number is genuinely rough. Never narrower than the
    metric's real error (~150) so we don't fake precision."""
    if n_games < 15:
        return 250
    if n_games < 40:
        return 175
    return 150


def move_quality_from_series(games: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Pure core. `games` = list of {date, accuracy, weight} (weight = game length,
    e.g. move count). Returns the rating band, or None if under MIN_GAMES.

    Move-weighted EWMA of accuracy with half-life HALF_LIFE_GAMES, processed in
    date order (oldest -> newest), so the final value is the recency-weighted
    current form."""
    usable = [g for g in games if g.get("accuracy") is not None and (g.get("weight") or 0) > 0]
    if len(usable) < MIN_GAMES:
        return None

    usable.sort(key=lambda g: g.get("date") or "")
    lam = 0.5 ** (1.0 / HALF_LIFE_GAMES)
    w_sum = 0.0
    s_sum = 0.0
    for g in usable:
        wt = float(g["weight"])
        w_sum = lam * w_sum + wt
        s_sum = lam * s_sum + wt * float(g["accuracy"])
    weighted_acc = s_sum / w_sum

    rating = _map_accuracy_to_rating(weighted_acc)
    hw = _band_halfwidth(len(usable))
    low = max(RATING_MIN, rating - hw)
    high = min(RATING_MAX, rating + hw)
    return {
        "rating": rating,                 # point estimate (internal / calibration)
        "range_low": low,
        "range_high": high,
        "display": f"~{low}–{high}",  # the user-facing BAND (never a bare point)
        "weighted_accuracy": round(weighted_acc, 1),
        "games": len(usable),
        "half_life_games": HALF_LIFE_GAMES,
        # Above the ceiling move-quality saturates; caller should prefer imported.
        "saturated": rating >= SATURATION_CEILING,
    }


async def compute_move_quality_rating(db, user_id: str) -> Optional[Dict[str, Any]]:
    """Fetch the user's analysed games (accuracy + length + date) and score them.
    Returns the band dict, or None if under MIN_GAMES / no data.

    Length weight = number of stored move_evaluations (a game-length proxy);
    fetched via $size so we don't transfer the move arrays."""
    cursor = db.game_analyses.aggregate([
        {"$match": {"user_id": user_id}},
        {"$project": {
            "game_id": 1,
            "accuracy": "$stockfish_analysis.accuracy",
            "weight": {"$size": {"$ifNull": ["$stockfish_analysis.move_evaluations", []]}},
        }},
    ])
    accs: Dict[str, Dict[str, Any]] = {}
    async for d in cursor:
        if d.get("accuracy") is not None and (d.get("weight") or 0) > 0:
            accs[d["game_id"]] = {"accuracy": d["accuracy"], "weight": d["weight"]}
    if len(accs) < MIN_GAMES:
        return None

    games: List[Dict[str, Any]] = []
    async for g in db.games.find(
        {"user_id": user_id, "game_id": {"$in": list(accs.keys())}},
        {"game_id": 1, "end_time": 1, "pgn": 1},
    ):
        rec = accs[g["game_id"]]
        date = g.get("end_time")
        if not date:
            m = _re_utc(g.get("pgn") or "")
            date = m or ""
        games.append({"date": str(date), "accuracy": rec["accuracy"], "weight": rec["weight"]})
    return move_quality_from_series(games)


def _re_utc(pgn: str) -> Optional[str]:
    import re
    m = re.search(r'\[UTCDate "([\d.]+)"\].*?\[UTCTime "([\d:]+)"\]', pgn, re.S)
    return (m.group(1) + " " + m.group(2)) if m else None
