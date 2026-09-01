"""
Canonical rating resolver.

The user/profile schema has accumulated several rating fields over time:
  users.assessed_rating       — from onboarding self-assessment
  users.detected_rating       — pulled from chess.com / lichess at connect
  users.lichess_rating        — separate lichess-specific rating
  users.skill_level           — bucketed level
  users.rating_source         — which of the above should win
  player_profiles.current_rating — most-recent value used by the coach

There's no single canonical stored field, so this module is the source of
truth. Product code with database access must use ``get_coaching_rating`` or
``resolve_coaching_rating``. ``get_current_rating`` remains the synchronous
fallback for pure helpers and migration compatibility.

Synchronous fallback resolution order (first non-None wins):
  1) users[users.rating_source]      (explicitly preferred source)
  2) player_profiles.current_rating  (legacy computed fallback)
  3) users.detected_rating           (platform-imported value)
  4) users.lichess_rating
  5) users.assessed_rating           (self-assessment)
  6) DEFAULT_RATING from config      (1200)
"""
from datetime import datetime, timezone
import re
from statistics import median
from typing import Optional, Any, Dict

try:
    from config import DEFAULT_RATING  # backend/config.py
except Exception:
    DEFAULT_RATING = 1200


def get_current_rating(user: Optional[Dict[str, Any]] = None,
                       profile: Optional[Dict[str, Any]] = None) -> int:
    """Resolve the user's current rating from whatever fields are populated.

    Always returns an int. Never raises. Pass whichever of (user, profile)
    you already have loaded; missing args are treated as empty dicts.

    Why this exists: see module docstring + memory/single_source_of_truth.
    """
    user = user or {}
    profile = profile or {}

    # 1) The user's explicitly selected platform/source always wins.
    src = user.get("rating_source")
    if src and src in user:
        v = user.get(src)
        if isinstance(v, (int, float)) and v > 0:
            return int(v)
    normalized_source = str(src or "").lower().replace("_", "")
    if "lichess" in normalized_source:
        value = user.get("lichess_rating")
        if isinstance(value, (int, float)) and value > 0:
            return int(value)
    if "chess.com" in normalized_source or "chesscom" in normalized_source:
        value = user.get("detected_rating")
        if isinstance(value, (int, float)) and value > 0:
            return int(value)

    # 2) Legacy computed profile fallback. The async coaching resolver prefers
    # dated game evidence; this remains for callers without database access.
    pr = profile.get("current_rating")
    if isinstance(pr, (int, float)) and pr > 0:
        return int(pr)

    # 3-5) fall through preferred order
    for field in ("detected_rating", "lichess_rating", "assessed_rating"):
        v = user.get(field)
        if isinstance(v, (int, float)) and v > 0:
            return int(v)

    return int(DEFAULT_RATING)


COACHING_RATING_WINDOW_GAMES = 3


def _parse_game_datetime(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if not value:
        return None
    raw = str(value).strip().replace("Z", "+00:00")
    # Historic imports use YYYY.MM.DD. Replace only those date separators;
    # replacing every dot corrupts valid fractional-second ISO timestamps.
    if re.match(r"^\d{4}\.\d{2}\.\d{2}", raw):
        raw = raw[:10].replace(".", "-") + raw[10:]
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        try:
            parsed = datetime.fromisoformat(raw[:10])
        except ValueError:
            return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _normalized_platform(value: Any) -> str:
    raw = str(value or "unknown").strip().lower().replace("_", "")
    if "lichess" in raw:
        return "lichess"
    if "chess.com" in raw or "chesscom" in raw:
        return "chess.com"
    return raw or "unknown"


async def resolve_coaching_rating(
    db,
    user_id: str,
    *,
    user: Optional[Dict[str, Any]] = None,
    profile: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Resolve a stable, platform-correct rating with provenance.

    The selected platform follows ``users.rating_source`` when it names a
    platform. Within that platform, the median of the three most recent dated
    game ratings is used. The three-game window won the 2026-09-01 production
    bake-off for next-game error while remaining much less jumpy than one game.
    """
    user = user or await db.users.find_one({"user_id": user_id}) or {}
    profile = profile or await db.player_profiles.find_one(
        {"user_id": user_id}
    ) or {}
    projection = {
        "_id": 0,
        "date_played": 1,
        "platform": 1,
        "source": 1,
        "user_rating": 1,
        "user_rating_at_time": 1,
        "user_color": 1,
        "white_rating": 1,
        "black_rating": 1,
        "white": 1,
        "black": 1,
        "pgn": 1,
    }
    games = await db.games.find({"user_id": user_id}, projection).to_list(
        length=5000
    )
    by_platform: Dict[str, list[tuple[datetime, int]]] = {}
    for game in games:
        played_at = _parse_game_datetime(game.get("date_played"))
        rating = resolve_game_user_rating(game).get("rating")
        if played_at is None or rating is None:
            continue
        platform = _normalized_platform(game.get("platform") or game.get("source"))
        by_platform.setdefault(platform, []).append((played_at, int(rating)))
    for sequence in by_platform.values():
        sequence.sort(key=lambda row: row[0], reverse=True)

    preferred = _normalized_platform(user.get("rating_source"))
    if preferred not in by_platform:
        preferred = ""
    if not preferred and by_platform:
        preferred = max(
            by_platform,
            key=lambda platform: by_platform[platform][0][0],
        )
    if preferred:
        sequence = by_platform[preferred]
        sample = sequence[:COACHING_RATING_WINDOW_GAMES]
        return {
            "rating": int(median([rating for _, rating in sample])),
            "source": "recent_game_median",
            "platform": preferred,
            "sample_games": len(sample),
            "as_of": sequence[0][0].isoformat(),
        }

    return {
        "rating": get_current_rating(user, profile),
        "source": "stored_fallback",
        "platform": None,
        "sample_games": 0,
        "as_of": None,
    }


async def get_coaching_rating(
    db,
    user_id: str,
    *,
    user: Optional[Dict[str, Any]] = None,
    profile: Optional[Dict[str, Any]] = None,
) -> int:
    return int((await resolve_coaching_rating(
        db, user_id, user=user, profile=profile
    ))["rating"])


def _positive_int(value: Any) -> Optional[int]:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def get_game_side_ratings(game: Optional[Dict[str, Any]]) -> Dict[str, Optional[int]]:
    """Return authoritative white/black ratings stored on one game.

    Unlike `get_current_rating`, this never supplies DEFAULT_RATING. Missing
    historical evidence must stay missing so rating-aware corpus behavior does
    not silently degrade into a guessed band.
    """
    game = game or {}
    white = _positive_int(game.get("white_rating"))
    black = _positive_int(game.get("black_rating"))

    white_obj = game.get("white")
    black_obj = game.get("black")
    if white is None and isinstance(white_obj, dict):
        white = _positive_int(white_obj.get("rating"))
    if black is None and isinstance(black_obj, dict):
        black = _positive_int(black_obj.get("rating"))

    pgn = str(game.get("pgn") or "")
    if pgn and (white is None or black is None):
        white_match = re.search(r'\[WhiteElo "(\d+)"\]', pgn)
        black_match = re.search(r'\[BlackElo "(\d+)"\]', pgn)
        if white is None and white_match:
            white = _positive_int(white_match.group(1))
        if black is None and black_match:
            black = _positive_int(black_match.group(1))

    return {"white": white, "black": black}


def resolve_game_user_rating(game: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Resolve the user's rating at game time with provenance.

    Precedence: explicit user_rating → side-specific stored/API rating → PGN
    header. Returns `{rating: None, source: "unknown"}` instead of 1200 when
    no authoritative value exists.
    """
    game = game or {}
    direct = _positive_int(game.get("user_rating"))
    if direct is None:
        direct = _positive_int(game.get("user_rating_at_time"))
    if direct is not None:
        return {"rating": direct, "source": "stored_user_rating"}

    color = str(game.get("user_color") or "").lower()
    if color not in ("white", "black"):
        return {"rating": None, "source": "unknown"}

    explicit_side = _positive_int(game.get(f"{color}_rating"))
    if explicit_side is not None:
        return {"rating": explicit_side, "source": f"{color}_rating"}

    side_obj = game.get(color)
    if isinstance(side_obj, dict):
        api_rating = _positive_int(side_obj.get("rating"))
        if api_rating is not None:
            return {"rating": api_rating, "source": f"{color}_api_rating"}

    pgn = str(game.get("pgn") or "")
    header = "WhiteElo" if color == "white" else "BlackElo"
    match = re.search(rf'\[{header} "(\d+)"\]', pgn)
    if match:
        return {"rating": int(match.group(1)), "source": f"pgn_{header.lower()}"}
    return {"rating": None, "source": "unknown"}


def get_game_user_rating(game: Optional[Dict[str, Any]]) -> Optional[int]:
    """Convenience accessor for the authoritative per-game rating or None."""
    return resolve_game_user_rating(game)["rating"]


def get_rating_band(rating: int) -> str:
    """Return the rating-band key. Derives from deterministic_coach_service.
    RATING_BANDS (the locked band definition) so the boundaries can never
    drift; falls back to the mirrored constants if that import fails."""
    try:
        from deterministic_coach_service import RATING_BANDS
        for key, band in RATING_BANDS.items():
            if band["min"] <= rating <= band["max"]:
                return key
    except Exception:
        pass
    if rating < 1000:
        return "beginner_low"
    if rating < 1400:
        return "beginner_high"
    if rating < 1800:
        return "intermediate"
    return "advanced"


# ── Band-keyed domain tables (Q1 unification, 2026-07-14) ──────────────────
# These tables used to live as inline if/elif ladders inside caption_pipeline
# and realtime_coaching_feedback — the same band boundaries re-typed per file,
# one edit away from divergence. The VALUES are unchanged (behavior-
# preserving); only the definition moved here, keyed by the canonical bands.

# Review-caption suppression: below this cp_loss (and with no concrete tactic),
# a sub-threshold inaccuracy is NOT framed as a mistake for this band.
CAPTION_SUPPRESS_CP = {
    "beginner_low": 150,   # beginners: only flag blunders
    "beginner_high": 75,   # improving: flag mistakes
    "intermediate": 50,    # intermediate: flag bigger inaccuracies
    "advanced": 30,        # advanced: flag subtle inaccuracies
}


def caption_suppress_threshold_cp(rating: int) -> int:
    r = DEFAULT_RATING if rating is None else int(rating)
    return CAPTION_SUPPRESS_CP[get_rating_band(r)]


# Live move classification (PWC realtime feedback): cp-change cutoffs per band.
MOVE_CLASSIFY_THRESHOLDS = {
    "beginner_low": {"excellent": 20, "good": -30, "inaccuracy": -150, "mistake": -300},
    "beginner_high": {"excellent": 20, "good": -20, "inaccuracy": -75, "mistake": -200},
    "intermediate": {"excellent": 20, "good": -10, "inaccuracy": -50, "mistake": -150},
    "advanced": {"excellent": 10, "good": -5, "inaccuracy": -30, "mistake": -100},
}


def move_classification_thresholds(rating: int) -> Dict[str, int]:
    r = DEFAULT_RATING if rating is None else int(rating)
    return MOVE_CLASSIFY_THRESHOLDS[get_rating_band(r)]
