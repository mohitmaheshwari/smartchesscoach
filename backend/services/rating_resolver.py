"""
Canonical rating resolver.

The user/profile schema has accumulated several rating fields over time:
  users.assessed_rating       — from onboarding self-assessment
  users.detected_rating       — pulled from chess.com / lichess at connect
  users.lichess_rating        — separate lichess-specific rating
  users.skill_level           — bucketed level
  users.rating_source         — which of the above should win
  player_profiles.current_rating — most-recent value used by the coach

There's no single canonical accessor today, so different services pick
different fields. This module is the one source of truth: import
`get_current_rating(user, profile)` everywhere a "current rating"
is needed.

Resolution order (first non-None wins):
  1) player_profiles.current_rating  (most recently computed value)
  2) users[users.rating_source]      (explicitly preferred source)
  3) users.detected_rating           (platform-imported value)
  4) users.lichess_rating
  5) users.assessed_rating           (self-assessment)
  6) DEFAULT_RATING from config      (1200)
"""
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

    # 1) profile.current_rating (most authoritative — re-derived per game)
    pr = profile.get("current_rating")
    if isinstance(pr, (int, float)) and pr > 0:
        return int(pr)

    # 2) users[rating_source] — if the user explicitly told us which one to use
    src = user.get("rating_source")
    if src and src in user:
        v = user.get(src)
        if isinstance(v, (int, float)) and v > 0:
            return int(v)

    # 3-5) fall through preferred order
    for field in ("detected_rating", "lichess_rating", "assessed_rating"):
        v = user.get(field)
        if isinstance(v, (int, float)) and v > 0:
            return int(v)

    return int(DEFAULT_RATING)


def get_rating_band(rating: int) -> str:
    """Return the rating-band key matching deterministic_coach_service.RATING_BANDS."""
    if rating < 1000:
        return "beginner_low"
    if rating < 1400:
        return "beginner_high"
    if rating < 1800:
        return "intermediate"
    return "advanced"
