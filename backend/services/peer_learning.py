"""
Peer-Learning Services
======================

Two data-driven surfaces, verified viable by
scripts/validate_peer_learning.py:

  1. graduation_insight  — "you're improving" OR "users who improved
                           from your level did X"
  2. opening_benchmark   — "your opening-knowledge mistakes are above
                           your rating band's average"

Each returns {has_data: bool, ...} so the UI can hide cards cleanly
when a user doesn't have enough data.
"""

from __future__ import annotations

import logging
import re
from collections import Counter, defaultdict
from statistics import mean
from typing import Dict, List, Optional

from services.opening_normalizer import normalize_opening

logger = logging.getLogger(__name__)

GRADUATE_IMPROVEMENT_THRESHOLD = 0.25  # need ≥25% blunder-rate drop to count
MIN_GAMES_FOR_TRAJECTORY = 20          # min games before we'll judge
GAP_OPENING_KNOWLEDGE = "opening_knowledge"


# ── Rating helpers ────────────────────────────────────────────────────

BANDS = [
    ("<1000", 0, 999),
    ("1000-1199", 1000, 1199),
    ("1200-1399", 1200, 1399),
    ("1400-1599", 1400, 1599),
    ("1600+", 1600, 9999),
]


def _band_for(rating: int) -> str:
    if not rating or rating <= 0:
        return "no_rating"
    for name, lo, hi in BANDS:
        if lo <= rating <= hi:
            return name
    return "no_rating"


async def _resolve_rating(db, user_id: str) -> int:
    """Pull the user's current_rating (backfilled from PGNs). Returns 0 when missing."""
    profile = await db.player_profiles.find_one(
        {"user_id": user_id},
        {"_id": 0, "current_rating": 1, "chesscom_stats.rating": 1, "lichess_stats.rating": 1},
    )
    if profile:
        for key in ("current_rating",):
            v = profile.get(key)
            if isinstance(v, (int, float)) and v > 0:
                return int(v)
        for path in (("chesscom_stats", "rating"), ("lichess_stats", "rating")):
            parent = profile.get(path[0]) or {}
            v = parent.get(path[1])
            if isinstance(v, (int, float)) and v > 0:
                return int(v)
    return 0


# ── 1. Graduation insight ────────────────────────────────────────────

async def get_graduation_insight(db, user_id: str) -> Dict:
    """
    Classify the user as GRADUATE / STRUGGLER / NEW:
      - GRADUATE: ≥20 games AND blunder rate dropped ≥25% over time
      - STRUGGLER: ≥20 games AND no measurable improvement
      - NEW: <20 games — no data yet

    For strugglers, mine the fleet's graduates to report what they
    worked on — concrete "users who improved from your level did X"
    rather than vague advice.
    """
    empty = {"has_data": False, "status": "new", "headline": "", "subline": "", "training_weakness": None}

    # Pull user's games timeline + blunder counts
    user_games = await db.games.find(
        {"user_id": user_id, "is_analyzed": True},
        {"_id": 0, "game_id": 1, "imported_at": 1},
    ).sort("imported_at", 1).to_list(500)
    if len(user_games) < MIN_GAMES_FOR_TRAJECTORY:
        return empty

    first_half_count, second_half_count = await _blunder_halves(db, user_id, user_games)
    if first_half_count["games"] == 0 or second_half_count["games"] == 0:
        return empty

    first_rate = first_half_count["blunders"] / first_half_count["games"]
    second_rate = second_half_count["blunders"] / second_half_count["games"]

    if first_rate == 0:
        return empty  # can't compute improvement from zero

    # Graduate path
    if second_rate < first_rate * (1 - GRADUATE_IMPROVEMENT_THRESHOLD):
        improvement_pct = int((1 - second_rate / first_rate) * 100)
        return {
            "has_data": True,
            "status": "graduate",
            "headline": f"You're improving — blunder rate down {improvement_pct}%.",
            "subline": (
                f"First {first_half_count['games']} games: {first_rate:.1f} blunders each. "
                f"Recent {second_half_count['games']} games: {second_rate:.1f}. Keep going."
            ),
            "first_half_rate": round(first_rate, 2),
            "second_half_rate": round(second_rate, 2),
            "improvement_pct": improvement_pct,
            "training_weakness": None,  # no CTA for graduates — just celebrate
        }

    # Struggler path — mine fleet graduates to surface a concrete roadmap
    fleet_graduates = await _fleet_graduate_paths(db)
    if not fleet_graduates:
        return {
            "has_data": True,
            "status": "struggler",
            "headline": f"{len(user_games)} games played, no measurable improvement yet.",
            "subline": "Stick with it — consistency matters more than intensity.",
            "training_weakness": None,
        }

    # Which cognitive_gap did graduates fix most? Look at aggregate drops.
    top_fixed_gap, times_fixed = _top_fixed_gap_across_graduates(fleet_graduates)
    gap_human = (top_fixed_gap or "").replace("_", " ")
    # Honest copy: we scan ALL fleet users for graduates, not band-matched
    # users. Don't claim "from your level" — that would require rating-band
    # filtering which we don't do here (thin data at 55 users). Say what's
    # actually true instead.
    users_word = "user" if len(fleet_graduates) == 1 else "users"
    return {
        "has_data": True,
        "status": "struggler",
        "headline": (
            f"{len(fleet_graduates)} {users_word} in the community improved "
            f"their blunder rate over recent games."
        ),
        "subline": (
            f"Their biggest shared win: fewer {gap_human} mistakes."
            if top_fixed_gap else
            "Their shared path: more games + targeted puzzles over 30+ days."
        ),
        "training_weakness": top_fixed_gap,
        "graduate_count": len(fleet_graduates),
    }


async def _blunder_halves(db, user_id: str, games_sorted: List[Dict]) -> tuple:
    """Return (first_half, second_half) stats — games count + total blunders each."""
    mid = len(games_sorted) // 2
    first_ids = [g["game_id"] for g in games_sorted[:mid] if g.get("game_id")]
    second_ids = [g["game_id"] for g in games_sorted[mid:] if g.get("game_id")]

    first_blunders = 0
    second_blunders = 0
    async for a in db.game_analyses.find(
        {"user_id": user_id, "game_id": {"$in": first_ids}},
        {"_id": 0, "stockfish_analysis.blunders": 1},
    ):
        first_blunders += (a.get("stockfish_analysis") or {}).get("blunders") or 0
    async for a in db.game_analyses.find(
        {"user_id": user_id, "game_id": {"$in": second_ids}},
        {"_id": 0, "stockfish_analysis.blunders": 1},
    ):
        second_blunders += (a.get("stockfish_analysis") or {}).get("blunders") or 0

    return (
        {"games": len(first_ids), "blunders": first_blunders},
        {"games": len(second_ids), "blunders": second_blunders},
    )


async def _fleet_graduate_paths(db) -> List[Dict]:
    """Find fleet-wide graduates and their cognitive-gap change patterns."""
    graduates: List[Dict] = []
    users = await db.users.find({}, {"_id": 0, "user_id": 1}).to_list(1000)

    for u in users:
        uid = u.get("user_id")
        if not uid:
            continue
        games = await db.games.find(
            {"user_id": uid, "is_analyzed": True},
            {"_id": 0, "game_id": 1, "imported_at": 1, "user_color": 1},
        ).sort("imported_at", 1).to_list(200)
        if len(games) < MIN_GAMES_FOR_TRAJECTORY:
            continue

        first_stats, second_stats = await _blunder_halves(db, uid, games)
        if first_stats["games"] == 0 or second_stats["games"] == 0:
            continue
        fr = first_stats["blunders"] / first_stats["games"]
        sr = second_stats["blunders"] / second_stats["games"]
        if fr == 0 or sr >= fr * (1 - GRADUATE_IMPROVEMENT_THRESHOLD):
            continue

        # Per-half cognitive_gap distribution
        mid = len(games) // 2
        first_ids = [g["game_id"] for g in games[:mid] if g.get("game_id")]
        second_ids = [g["game_id"] for g in games[mid:] if g.get("game_id")]
        first_gaps = await _gap_counts(db, uid, first_ids, games)
        second_gaps = await _gap_counts(db, uid, second_ids, games)

        # Which gap dropped most (absolute count)
        gap_drops: Dict[str, int] = {}
        all_gaps = set(first_gaps.keys()) | set(second_gaps.keys())
        for g in all_gaps:
            drop = first_gaps.get(g, 0) - second_gaps.get(g, 0)
            if drop > 0:
                gap_drops[g] = drop

        graduates.append({
            "user_id": uid,
            "games_total": len(games),
            "first_rate": fr,
            "second_rate": sr,
            "gap_drops": gap_drops,
        })

    return graduates


async def _gap_counts(db, user_id: str, game_ids: List[str], games_meta: List[Dict]) -> Counter:
    """Count cognitive_gap occurrences on the user's critical moves across the given games."""
    meta_by_id = {g["game_id"]: g for g in games_meta if g.get("game_id")}
    counts: Counter = Counter()
    async for a in db.game_analyses.find(
        {"user_id": user_id, "game_id": {"$in": game_ids}},
        {"_id": 0, "game_id": 1, "stockfish_analysis.move_evaluations": 1},
    ):
        gid = a.get("game_id")
        m = meta_by_id.get(gid, {})
        user_is_white = (m.get("user_color") or "white") == "white"
        sf = a.get("stockfish_analysis") or {}
        for ev in sf.get("move_evaluations") or []:
            cp = ev.get("cp_loss") or 0
            if cp < 100:
                continue
            fen = ev.get("fen_before") or ""
            parts = fen.split(" ")
            side = parts[1] if len(parts) > 1 else ""
            if side in ("w", "b"):
                if (side == "w") != user_is_white:
                    continue
            gap = ev.get("cognitive_gap") or ""
            if gap:
                counts[gap] += 1
    return counts


def _top_fixed_gap_across_graduates(graduates: List[Dict]) -> tuple:
    """Across all graduates, which cognitive_gap shows the largest aggregate drop?"""
    aggregate: Counter = Counter()
    for grad in graduates:
        for gap, drop in (grad.get("gap_drops") or {}).items():
            aggregate[gap] += drop
    if not aggregate:
        return (None, 0)
    top, total = aggregate.most_common(1)[0]
    return (top, total)


# ── 3. Opening knowledge benchmark ───────────────────────────────────

async def get_opening_benchmark_insight(db, user_id: str) -> Dict:
    """
    Compare the user's % of opening_knowledge mistakes to their rating
    band's average. Only ships this insight if the user is above band avg
    (i.e. there's actually a gap to close).
    """
    empty = {"has_data": False, "user_pct": 0, "band_pct": 0, "band": "", "training_weakness": None}

    # Get user's rating band
    rating = await _resolve_rating(db, user_id)
    band = _band_for(rating)
    if band in ("no_rating", "1400-1599"):
        # Skip thinly-populated or no-rating users
        return empty

    # User's opening_knowledge %
    user_total, user_opening = await _gap_share(db, user_id, GAP_OPENING_KNOWLEDGE)
    if user_total < 30:
        return empty  # not enough mistakes to compute a rate

    # Band average — aggregate across all users in this band (excluding user)
    users_in_band = await _users_in_band(db, band)
    users_in_band.discard(user_id)
    if len(users_in_band) < 3:
        return empty

    band_total = 0
    band_opening = 0
    for uid in users_in_band:
        t, ok = await _gap_share(db, uid, GAP_OPENING_KNOWLEDGE)
        band_total += t
        band_opening += ok
    if band_total < 50:
        return empty

    user_pct = user_opening / user_total * 100
    band_pct = band_opening / band_total * 100

    # Only surface a card if the user is meaningfully worse
    if user_pct <= band_pct + 2:  # within 2 pp of band average — don't flag
        return empty

    delta_pct = int(round(user_pct - band_pct))
    return {
        "has_data": True,
        "user_pct": round(user_pct, 1),
        "band_pct": round(band_pct, 1),
        "band": band,
        "training_weakness": GAP_OPENING_KNOWLEDGE,
        "headline": (
            f"Your opening-theory mistakes are {delta_pct} points above your band's average."
        ),
        "subline": (
            f"{user_pct:.1f}% of your mistakes are about opening knowledge "
            f"vs {band_pct:.1f}% for other {band} players. Learning your lines closes this gap."
        ),
    }


async def _gap_share(db, user_id: str, gap_name: str) -> tuple:
    """For a user, return (total_mistakes, mistakes_with_that_gap)."""
    total = 0
    matched = 0
    # Need user_color per game to filter to user moves
    games = {g["game_id"]: g for g in await db.games.find(
        {"user_id": user_id, "is_analyzed": True},
        {"_id": 0, "game_id": 1, "user_color": 1},
    ).to_list(500)}

    async for a in db.game_analyses.find(
        {"user_id": user_id},
        {"_id": 0, "game_id": 1, "stockfish_analysis.move_evaluations": 1},
    ):
        gid = a.get("game_id")
        meta = games.get(gid, {})
        user_is_white = (meta.get("user_color") or "white") == "white"
        sf = a.get("stockfish_analysis") or {}
        for ev in sf.get("move_evaluations") or []:
            cp = ev.get("cp_loss") or 0
            if cp < 100:
                continue
            fen = ev.get("fen_before") or ""
            parts = fen.split(" ")
            side = parts[1] if len(parts) > 1 else ""
            if side in ("w", "b"):
                if (side == "w") != user_is_white:
                    continue
            total += 1
            if (ev.get("cognitive_gap") or "") == gap_name:
                matched += 1
    return (total, matched)


async def _users_in_band(db, band: str) -> set:
    """All user_ids whose resolved rating falls in `band`."""
    users = await db.users.find({}, {"_id": 0, "user_id": 1}).to_list(1000)
    out: set = set()
    for u in users:
        uid = u.get("user_id")
        if not uid:
            continue
        r = await _resolve_rating(db, uid)
        if _band_for(r) == band:
            out.add(uid)
    return out
