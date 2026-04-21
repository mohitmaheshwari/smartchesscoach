"""
Player Performance — compute which openings / patterns the user plays WELL.

Feeds the coaching pipeline's "personal strength" gate: if the user has a
strong historical record in an opening, we don't override their choices with
generic principles. A Scandinavian player with a 70% win rate playing Qxd5 +
Qa5 isn't "violating minors-before-queen" — they're following their weapon.

Precedence in the critique chain:
    best move match       → no critique
    tactical / walked-into → always critique
    opening book match    → skip principle critique
    STRONG PERSONAL RECORD → skip principle critique  ← this module
    principle-demand fires → critique

This module only looks at historical games. It does NOT decide what to say —
it returns a set of opening identifiers the user performs well in.
"""

import logging
import time
from typing import Set, Optional, Dict, Tuple

logger = logging.getLogger(__name__)


# Simple in-memory cache: (user_id) → (timestamp, strong_set, name_map)
# Computing this touches 50+ game docs; caching avoids per-move DB hits.
_CACHE: Dict[str, Tuple[float, Set[str], Dict[str, float]]] = {}
_CACHE_TTL_SEC = 600  # 10 minutes — player's record doesn't change mid-session


# Thresholds
DEFAULT_MIN_GAMES = 5          # need at least this many games to trust the signal
DEFAULT_MIN_WIN_RATE = 0.55    # 55% W/L ignoring draws
RECENT_GAMES_WINDOW = 40       # only look at the last N games — old games don't reflect current strength


import re

# Aliases: normalized synonym → canonical name used elsewhere in the system.
# Handles cases where chess.com / Lichess / internal name diverge.
_OPENING_ALIASES = {
    "center counter defense": "scandinavian defense",
    "center counter": "scandinavian defense",
    "center counter game": "scandinavian defense",
    "spanish opening": "ruy lopez",
    "spanish game": "ruy lopez",
    "giuoco piano": "italian game",
    "zukertort opening": "queens pawn",
    "reti opening": "reti",
    "english": "english opening",
    "kings indian": "kings indian defense",
    "queens indian": "queens indian defense",
    "nimzo indian": "nimzo indian defense",
    "nimzo-indian": "nimzo indian defense",
}

# Words dropped as standalone terms (but only when they leave a non-empty name).
# We keep "defense"/"attack" etc. because "Scandinavian Defense" is the real
# name; but we strip them in aliases where they're redundant.
_ECO_RE = re.compile(r"^[A-E]\d{2}\s+")   # e.g. "B01 Scandinavian Defense"
_WS_RE = re.compile(r"\s+")


def _normalize_opening(raw: Optional[str]) -> str:
    """Normalize a free-form opening string for comparison.

    Handles:
      'Scandinavian Defense'                           -> 'scandinavian defense'
      'scandinavian_defense'                           -> 'scandinavian defense'
      'Scandinavian Defense: Mieses-Kotroc Variation'  -> 'scandinavian defense'
      'Scandinavian, Mieses-Kotroc'                    -> 'scandinavian'
      'B01 Scandinavian Defense'                       -> 'scandinavian defense' (ECO stripped)
      'Center Counter Defense'                         -> 'scandinavian defense' (alias)
      ''/None                                          -> ''
    """
    if not raw:
        return ""
    s = str(raw).replace("_", " ").strip()

    # Strip leading ECO code ("B01 ", "A45 ", etc.)
    s = _ECO_RE.sub("", s)

    # Drop variation suffix on either colon OR comma
    for sep in (":", ","):
        if sep in s:
            s = s.split(sep, 1)[0]

    # Normalize dashes (e.g. "Sicilian-Najdorf" → "Sicilian Najdorf") and
    # remove apostrophes (King's → Kings) for reliable aliasing.
    s = s.replace("-", " ").replace("'", "")
    s = _WS_RE.sub(" ", s).strip().lower()

    # Apply aliases — "Center Counter" becomes the canonical "Scandinavian Defense"
    return _OPENING_ALIASES.get(s, s)


async def get_strong_openings(
    db,
    user_id: str,
    *,
    min_games: int = DEFAULT_MIN_GAMES,
    min_win_rate: float = DEFAULT_MIN_WIN_RATE,
) -> Set[str]:
    """Return the set of normalized opening names the user plays well.

    "Plays well" = played in >= min_games games and has >= min_win_rate W ratio
    (ignoring draws in the denominator).

    Result is CACHED per user for 10 min. Cheap to call per-move after warmup.
    Returns an empty set on any failure — safe default: don't suppress critique
    if we can't prove strength.
    """
    if not user_id or db is None:
        return set()

    now = time.monotonic()
    cached = _CACHE.get(user_id)
    if cached and (now - cached[0]) < _CACHE_TTL_SEC:
        return cached[1]

    try:
        # Fetch recent games only — results shift over time
        cursor = db.games.find(
            {"user_id": user_id},
            {"_id": 0, "opening": 1, "result": 1, "user_color": 1, "platform": 1},
        ).sort("imported_at", -1).limit(RECENT_GAMES_WINDOW)

        # Group by normalized opening name
        stats: Dict[str, Dict[str, int]] = {}
        async for g in cursor:
            op = _normalize_opening(g.get("opening"))
            if not op:
                continue
            bucket = stats.setdefault(op, {"wins": 0, "losses": 0, "draws": 0, "total": 0})
            bucket["total"] += 1
            result = g.get("result", "")
            user_color = g.get("user_color", "white")
            # game.result is stored as "1-0" / "0-1" / "1/2-1/2" or "win"/"loss"/"draw"
            if result in ("win", "W"):
                bucket["wins"] += 1
            elif result in ("loss", "L"):
                bucket["losses"] += 1
            elif result in ("draw", "D", "1/2-1/2"):
                bucket["draws"] += 1
            elif result == "1-0":
                if user_color == "white":
                    bucket["wins"] += 1
                else:
                    bucket["losses"] += 1
            elif result == "0-1":
                if user_color == "black":
                    bucket["wins"] += 1
                else:
                    bucket["losses"] += 1

        strong: Set[str] = set()
        rate_map: Dict[str, float] = {}
        for op, b in stats.items():
            decisive = b["wins"] + b["losses"]
            if b["total"] < min_games:
                continue
            if decisive == 0:
                continue
            wr = b["wins"] / decisive
            rate_map[op] = wr
            if wr >= min_win_rate:
                strong.add(op)

        _CACHE[user_id] = (now, strong, rate_map)
        if strong:
            logger.info(
                f"[PLAYER-PERF] user {user_id[:8]} strong openings: "
                f"{[(o, round(rate_map[o], 2)) for o in strong]}"
            )
        return strong

    except Exception as e:
        logger.debug(f"[PLAYER-PERF] compute failed for {user_id}: {e}")
        return set()


def invalidate_cache(user_id: str):
    """Drop the cached result for a user. Call after a game ends so the next
    call reflects the latest data. Not strictly required — the 10 min TTL will
    catch up on its own."""
    _CACHE.pop(user_id, None)
    _STYLE_CACHE.pop(user_id, None)


# ─────────────────────────────────────────────────────────────────────────────
# Player style (attacking / positional / tactical / defensive)
# ─────────────────────────────────────────────────────────────────────────────
# Pulled from `player_identities.style_profile`, updated by analysis_worker.
# Used as another "trust signal" in the critique pipeline: moves that match
# the user's established style shouldn't be lectured on generic principles.

_STYLE_CACHE: Dict[str, Tuple[float, Dict]] = {}
_STYLE_MIN_CONFIDENCE = 0.3    # need enough signal to trust the style label
_STYLE_DOMINANT_THRESHOLD = 0.6  # a tendency >= this counts as "the user's style"


async def get_player_style(db, user_id: str) -> Dict:
    """Return the user's style profile. Empty dict if unavailable or too noisy.

    Shape of returned dict (all optional keys):
        {
            "primary_style": "attacking",         # from analysis_worker
            "confidence": 0.6,
            "aggressive_tendency": 0.7,
            "positional_tendency": 0.3,
            "tactical_tendency": 0.65,
            "defensive_tendency": 0.25,
            "is_attacking": True,                 # derived convenience flag
            "is_positional": False,
        }

    Falls back to {} silently — callers should treat empty as "no style data,
    don't use the style gate."
    """
    if not user_id or db is None:
        return {}

    now = time.monotonic()
    cached = _STYLE_CACHE.get(user_id)
    if cached and (now - cached[0]) < _CACHE_TTL_SEC:
        return cached[1]

    try:
        identity = await db.player_identities.find_one(
            {"user_id": user_id},
            {"_id": 0, "style_profile": 1, "games_analyzed": 1},
        )
        if not identity:
            _STYLE_CACHE[user_id] = (now, {})
            return {}

        style = identity.get("style_profile") or {}
        confidence = float(style.get("confidence") or 0.0)
        if confidence < _STYLE_MIN_CONFIDENCE:
            _STYLE_CACHE[user_id] = (now, {})
            return {}

        agg = float(style.get("aggressive_tendency") or 0.5)
        pos = float(style.get("positional_tendency") or 0.5)
        tac = float(style.get("tactical_tendency") or 0.5)
        def_ = float(style.get("defensive_tendency") or 0.5)

        result = {
            "primary_style": style.get("primary_style", ""),
            "confidence": confidence,
            "aggressive_tendency": agg,
            "positional_tendency": pos,
            "tactical_tendency": tac,
            "defensive_tendency": def_,
            "is_attacking": agg >= _STYLE_DOMINANT_THRESHOLD or tac >= _STYLE_DOMINANT_THRESHOLD,
            "is_positional": pos >= _STYLE_DOMINANT_THRESHOLD or def_ >= _STYLE_DOMINANT_THRESHOLD,
        }
        _STYLE_CACHE[user_id] = (now, result)
        logger.info(
            f"[PLAYER-PERF] user {user_id[:8]} style: primary={result['primary_style']} "
            f"attacking={result['is_attacking']} positional={result['is_positional']}"
        )
        return result
    except Exception as e:
        logger.debug(f"[PLAYER-PERF] style fetch failed for {user_id}: {e}")
        return {}


def is_strong_opening(opening_name: Optional[str], strong_set: Set[str]) -> bool:
    """Check whether a detected opening name matches the user's strong set.

    The detected name (e.g. "Scandinavian Defense") is normalized and compared
    against the stored normalized set. Substring match also counts so that
    more-specific detections ("Scandinavian Defense: Main Line") still hit the
    parent opening.
    """
    if not opening_name or not strong_set:
        return False
    normalized = _normalize_opening(opening_name)
    if normalized in strong_set:
        return True
    # Substring: if detected is a prefix of a strong one, or vice versa
    for s in strong_set:
        if s and (s in normalized or normalized in s):
            return True
    return False
