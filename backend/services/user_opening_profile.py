"""
Per-user opening profile — the connecting layer that powers opening
teaching across all three surfaces (Lab review, Play with Coach,
/openings page).

Architecture (locked 2026-05-19): each surface pulls the SAME opening-
identity data — what the user actually plays, win rates, recurring
traps, recent games. Stored once, surfaced everywhere. Same shape as
the Phase-2 memory pattern for tactics: per-user history aggregated
into ONE place, then referenced from many surfaces.

V1 scope (this commit): aggregate from existing `games` + `game_
analyses` collections. No deviation-detection yet — that's Component 2
(Lab integration) which depends on this foundation.

Schema persisted to db.user_opening_profiles:
{
  "user_id":               str,
  "version":               int,   # USER_OPENING_PROFILE_VERSION
  "computed_at":           datetime,
  "total_analyzed_games":  int,

  "white": {
    "total_games":    int,
    "openings": [
      {
        "name":         str,         # raw opening name from games.opening
        "eco_prefix":   str | None,  # first letter+digit of ECO if any
        "games":        int,
        "wins":         int,
        "losses":       int,
        "draws":        int,
        "win_rate":     float,       # wins / games
        "recent_game_ids": List[str], # latest 10 for click-through
      },
      ...  # sorted by `games` desc
    ],
  },
  "black": { ... same shape ... },

  "trap_exposure": {
    # From game_analyses.trap_fires gold-class aggregation
    "by_trap": [
      {"trap_name": str, "gold": int, "celebration": int, "lucky": int, "warning": int},
      ...  # sorted by total desc
    ],
  },
}
"""

from __future__ import annotations

import logging
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

USER_OPENING_PROFILE_VERSION = 2  # v2: added family normalization (real-prod test surfaced raw-name fragmentation)


# Base opening families — match by prefix. Real-prod test 2026-05-19
# surfaced that raw opening names from Chess.com PGN are super
# fragmented ("Sicilian Defense Bowdler Attack 2...Nc6" treated as
# separate opening from "Sicilian Defense Bowdler Attack"). This list
# collapses ~95% of variations to their base family for sensible
# top-N display.
#
# Order matters: longer names FIRST so "Queens Gambit Declined" wins
# over "Queens Gambit" when matching.
_BASE_OPENING_FAMILIES = [
    # Closed games (D/E)
    "Queens Gambit Declined", "Queens Gambit Accepted", "Queens Gambit",
    "Kings Indian Defense", "Nimzo Indian Defense", "Bogo Indian Defense",
    "Queens Indian Defense", "Grunfeld Defense", "Slav Defense",
    "Catalan Opening", "London System", "Trompowsky Attack",
    "Torre Attack", "Colle System",
    # Open games (C)
    "Italian Game", "Ruy Lopez", "Petroff Defense", "Petrov Defense",
    "Scotch Game", "Vienna Game", "Kings Gambit", "Bishops Opening",
    "Center Game", "Four Knights Game", "Three Knights Game",
    "Philidor Defense", "Latvian Gambit", "Damiano Defense",
    "Russian Game",
    # Semi-open (B)
    "Sicilian Defense", "Caro Kann Defense", "French Defense",
    "Pirc Defense", "Modern Defense", "Scandinavian Defense",
    "Alekhine Defense", "Owen Defense",
    # Flank (A)
    "English Opening", "Reti Opening", "Bird Opening",
    "Kings Indian Attack", "Polish Opening", "Sokolsky Opening",
    "Larsen Opening", "Old Benoni Defense", "Benoni Defense",
    "Dutch Defense", "Budapest Gambit", "Englund Gambit",
]


def _normalize_opening_family(raw_name: Optional[str]) -> str:
    """Collapse a fragmented opening name to its base family.

    "Sicilian Defense Bowdler Attack 2...Nc6"  → "Sicilian Defense"
    "Caro Kann Defense 2.Nf3 d5"               → "Caro Kann Defense"
    "Italian Game: Two Knights Defense"        → "Italian Game"
    "Some Unknown Opening Variation"           → "Some Unknown Opening Variation"
                                                  (no match — keep raw)
    """
    if not raw_name:
        return "Unknown"
    name = raw_name.strip()
    for base in _BASE_OPENING_FAMILIES:
        if name == base or name.startswith(base + " ") or name.startswith(base + ":"):
            return base
    # No family match — keep raw (still useful for click-through).
    return name


def _is_win(result: Optional[str], user_color: str) -> bool:
    if not result:
        return False
    if user_color == "white" and result == "1-0":
        return True
    if user_color == "black" and result == "0-1":
        return True
    return False


def _is_loss(result: Optional[str], user_color: str) -> bool:
    if not result:
        return False
    if user_color == "white" and result == "0-1":
        return True
    if user_color == "black" and result == "1-0":
        return True
    return False


def _is_draw(result: Optional[str]) -> bool:
    return result in ("1/2-1/2", "½-½", "draw")


def _eco_prefix(eco: Optional[str]) -> Optional[str]:
    """Return the leading letter+digit of an ECO code (e.g. 'C42' → 'C4').

    Useful for grouping sub-variations (C42, C43, C45 all part of the
    same family at the C4* prefix level). V1 uses this for display only;
    no actual grouping yet.
    """
    if not eco or len(eco) < 2:
        return None
    return eco[:2].upper()


def _build_color_summary(games_by_opening: Dict[str, List[Dict]], user_color: str) -> Dict[str, Any]:
    """For a single color, aggregate games by opening family with win-rate.

    The key in games_by_opening is the normalized family name. Each
    game in the list carries its `raw_opening` so we can also surface
    the top variations within the family for click-through precision.
    """
    summary: List[Dict[str, Any]] = []
    for family_name, game_list in games_by_opening.items():
        wins = sum(1 for g in game_list if _is_win(g.get("result"), user_color))
        losses = sum(1 for g in game_list if _is_loss(g.get("result"), user_color))
        draws = sum(1 for g in game_list if _is_draw(g.get("result")))
        total = len(game_list)

        # Most common ECO prefix across these games (most are the same).
        eco_counter = Counter(g.get("eco_prefix") for g in game_list if g.get("eco_prefix"))
        dominant_eco = eco_counter.most_common(1)[0][0] if eco_counter else None

        # Top variations within this family — surfaces the specific
        # sub-lines the user is actually playing.
        variation_counter = Counter(
            g.get("raw_opening") for g in game_list if g.get("raw_opening")
        )
        top_variations = [
            {"name": name, "games": n}
            for name, n in variation_counter.most_common(5)
            if name != family_name  # don't surface the family as its own variation
        ]

        # Newest-first by occurred_at (None falls to end).
        sorted_games = sorted(
            game_list,
            key=lambda g: g.get("occurred_at") or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )
        recent_ids = [g["game_id"] for g in sorted_games[:10] if g.get("game_id")]

        summary.append({
            "name": family_name,
            "eco_prefix": dominant_eco,
            "games": total,
            "wins": wins,
            "losses": losses,
            "draws": draws,
            "win_rate": round(wins / total, 3) if total else 0.0,
            "top_variations": top_variations,
            "recent_game_ids": recent_ids,
        })

    # Sort by frequency (most played first).
    summary.sort(key=lambda o: (-o["games"], o["name"]))

    return {
        "total_games": sum(o["games"] for o in summary),
        "openings": summary,
    }


def _build_trap_exposure(per_trap_buckets: Dict[str, Counter]) -> Dict[str, Any]:
    """Aggregate trap exposure: per trap name, count of gold/celebration/
    lucky/warning encounters across all the user's analyzed games."""
    out_list: List[Dict[str, Any]] = []
    for trap_name, classes in per_trap_buckets.items():
        out_list.append({
            "trap_name": trap_name,
            "gold": classes.get("gold", 0),
            "celebration": classes.get("celebration", 0),
            "lucky": classes.get("lucky", 0),
            "warning": classes.get("warning", 0),
            "total": sum(classes.values()),
        })
    out_list.sort(key=lambda t: (-t["total"], t["trap_name"]))
    return {"by_trap": out_list}


async def compute_opening_profile(db, user_id: str) -> Dict[str, Any]:
    """Aggregate per-user opening identity from `games` + `game_analyses`.

    Cheap: one query against games, one against game_analyses, both
    indexed on user_id. ~50-200ms for users with hundreds of games.

    Returns the full profile dict. Caller persists if desired.
    """
    if not user_id:
        return _empty_profile()

    by_color_opening: Dict[str, Dict[str, List[Dict]]] = {
        "white": defaultdict(list),
        "black": defaultdict(list),
    }

    # Pull the user's analyzed games. Project only the fields we need.
    cursor = db.games.find(
        {"user_id": user_id, "is_analyzed": True},
        {
            "_id": 0,
            "game_id": 1,
            "user_color": 1,
            "result": 1,
            "opening": 1,
            "opening_name": 1,   # some older docs use opening_name
            "eco": 1,
            "eco_code": 1,
            "ended_at": 1,
            "imported_at": 1,
            "created_at": 1,
        },
    )

    total_games = 0
    async for g in cursor:
        color = (g.get("user_color") or "").lower()
        if color not in ("white", "black"):
            continue

        raw_opening = g.get("opening") or g.get("opening_name") or "Unknown"
        family = _normalize_opening_family(raw_opening)
        eco_raw = g.get("eco") or g.get("eco_code")
        occurred_at = (
            g.get("ended_at")
            or g.get("imported_at")
            or g.get("created_at")
        )

        # Bucket by the NORMALIZED family name (not raw). The raw name
        # is kept as a sub-detail for click-through precision.
        by_color_opening[color][family].append({
            "game_id": g.get("game_id"),
            "result": g.get("result"),
            "eco_prefix": _eco_prefix(eco_raw),
            "raw_opening": raw_opening,
            "occurred_at": occurred_at,
        })
        total_games += 1

    # Trap exposure from game_analyses.trap_fires
    per_trap_buckets: Dict[str, Counter] = defaultdict(Counter)
    try:
        ta_cursor = db.game_analyses.find(
            {"user_id": user_id, "trap_fires": {"$exists": True, "$ne": []}},
            {"_id": 0, "trap_fires": 1},
        )
        async for a in ta_cursor:
            for f in a.get("trap_fires") or []:
                tname = f.get("trap_name") or "Unknown"
                gc = f.get("gold_class") or "none"
                per_trap_buckets[tname][gc] += 1
    except Exception as e:
        logger.warning(f"[opening_profile] trap aggregate failed (non-fatal): {e}")

    return {
        "user_id": user_id,
        "version": USER_OPENING_PROFILE_VERSION,
        "computed_at": datetime.now(timezone.utc),
        "total_analyzed_games": total_games,
        "white": _build_color_summary(by_color_opening["white"], "white"),
        "black": _build_color_summary(by_color_opening["black"], "black"),
        "trap_exposure": _build_trap_exposure(per_trap_buckets),
    }


def _empty_profile() -> Dict[str, Any]:
    return {
        "user_id": "",
        "version": USER_OPENING_PROFILE_VERSION,
        "computed_at": datetime.now(timezone.utc),
        "total_analyzed_games": 0,
        "white": {"total_games": 0, "openings": []},
        "black": {"total_games": 0, "openings": []},
        "trap_exposure": {"by_trap": []},
    }


async def persist_opening_profile(db, profile: Dict[str, Any]) -> bool:
    """Upsert the profile into db.user_opening_profiles. Returns True on
    success. Best-effort — failure is non-fatal for callers."""
    uid = profile.get("user_id")
    if not uid:
        return False
    try:
        await db.user_opening_profiles.update_one(
            {"user_id": uid},
            {"$set": profile},
            upsert=True,
        )
        return True
    except Exception as e:
        logger.warning(f"[opening_profile] persist failed for {uid} (non-fatal): {e}")
        return False


async def get_opening_profile(db, user_id: str, max_staleness_seconds: int = 3600) -> Optional[Dict[str, Any]]:
    """Read the cached profile. If older than max_staleness_seconds OR
    missing, recompute + persist + return fresh. Reads return None only
    when user_id is empty.
    """
    if not user_id:
        return None
    try:
        cached = await db.user_opening_profiles.find_one(
            {"user_id": user_id},
            {"_id": 0},
        )
        if cached:
            ts = cached.get("computed_at")
            if isinstance(ts, datetime):
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                age = (datetime.now(timezone.utc) - ts).total_seconds()
                if age <= max_staleness_seconds and cached.get("version") == USER_OPENING_PROFILE_VERSION:
                    return cached
    except Exception as e:
        logger.warning(f"[opening_profile] read failed (non-fatal): {e}")

    # Stale, missing, or read failed → recompute.
    profile = await compute_opening_profile(db, user_id)
    await persist_opening_profile(db, profile)
    return profile


async def ensure_opening_profile_indexes(db) -> None:
    """Create indexes on user_opening_profiles. Idempotent."""
    try:
        await db.user_opening_profiles.create_index("user_id", unique=True)
    except Exception as e:
        logger.warning(f"[opening_profile] index creation failed (non-fatal): {e}")
