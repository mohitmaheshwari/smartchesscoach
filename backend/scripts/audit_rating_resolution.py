"""Read-only bake-off for the canonical coaching-rating projection.

Game ratings are ordered by normalized played date and kept within one
platform. Rolling medians predict the next observed rating; lower absolute
error and lower estimator movement are preferred. No database writes occur and
no game identifiers are emitted.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import json
import os
from statistics import median
from typing import Any, Dict, Optional

from pymongo import MongoClient

from services.rating_resolver import resolve_game_user_rating


WINDOWS = (3, 5, 10, 20)


def _parse_date(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if not value:
        return None
    raw = str(value).strip().replace(".", "-").replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        try:
            parsed = datetime.fromisoformat(raw[:10])
        except ValueError:
            return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _percentile(values: list[float], p: float) -> Optional[float]:
    if not values:
        return None
    ordered = sorted(values)
    index = (len(ordered) - 1) * p
    low = int(index)
    high = min(low + 1, len(ordered) - 1)
    fraction = index - low
    return round(ordered[low] * (1 - fraction) + ordered[high] * fraction, 2)


def _summary(values: list[float]) -> Dict[str, Any]:
    return {
        "n": len(values),
        "median": _percentile(values, 0.5),
        "p75": _percentile(values, 0.75),
        "p90": _percentile(values, 0.9),
        "mean": round(sum(values) / len(values), 2) if values else None,
    }


def _platform(game: Dict[str, Any]) -> str:
    return str(game.get("platform") or game.get("source") or "unknown").lower()


def build_report(db, *, target_email: str) -> Dict[str, Any]:
    projection = {
        "_id": 0,
        "user_id": 1,
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
    by_user_platform: Dict[tuple[str, str], list[tuple[datetime, int]]] = defaultdict(list)
    coverage = defaultdict(int)
    for game in db.games.find({}, projection):
        coverage["games_scanned"] += 1
        user_id = str(game.get("user_id") or "")
        played_at = _parse_date(game.get("date_played"))
        resolved = resolve_game_user_rating(game)
        rating = resolved.get("rating")
        if not user_id or played_at is None or rating is None:
            coverage["games_without_usable_date_and_rating"] += 1
            continue
        coverage["rated_dated_games"] += 1
        by_user_platform[(user_id, _platform(game))].append((played_at, int(rating)))

    errors = {window: [] for window in WINDOWS}
    movements = {window: [] for window in WINDOWS}
    predictions = {window: 0 for window in WINDOWS}
    for sequence in by_user_platform.values():
        sequence.sort(key=lambda row: row[0])
        ratings = [row[1] for row in sequence]
        for window in WINDOWS:
            previous_estimate: Optional[float] = None
            for index in range(window, len(ratings)):
                estimate = float(median(ratings[index - window:index]))
                errors[window].append(abs(estimate - ratings[index]))
                predictions[window] += 1
                if previous_estimate is not None:
                    movements[window].append(abs(estimate - previous_estimate))
                previous_estimate = estimate

    user = db.users.find_one(
        {"email": {"$regex": f"^{target_email}$", "$options": "i"}},
        {"_id": 0, "user_id": 1, "email": 1, "detected_rating": 1,
         "lichess_rating": 1, "assessed_rating": 1, "rating_source": 1},
    ) or {}
    uid = str(user.get("user_id") or "")
    profile = db.player_profiles.find_one(
        {"user_id": uid}, {"_id": 0, "current_rating": 1}
    ) or {}
    available = []
    for (user_id, platform), sequence in by_user_platform.items():
        if user_id != uid or not sequence:
            continue
        sequence.sort(key=lambda row: row[0], reverse=True)
        available.append((sequence[0][0], platform, sequence))
    available.sort(reverse=True, key=lambda row: row[0])
    target: Dict[str, Any] = {
        "email": target_email,
        "profile_current_rating": profile.get("current_rating"),
        "detected_rating": user.get("detected_rating"),
        "lichess_rating": user.get("lichess_rating"),
        "assessed_rating": user.get("assessed_rating"),
        "rating_source": user.get("rating_source"),
        "recent_platform": None,
        "latest_game_rating": None,
        "latest_game_date": None,
        "rolling_medians": {},
        "platforms": {},
    }
    for latest_date, platform, sequence in available:
        ratings = [rating for _, rating in sequence]
        target["platforms"][platform] = {
            "latest_game_rating": ratings[0],
            "latest_game_date": latest_date.date().isoformat(),
            "rated_games": len(ratings),
            "rolling_medians": {
                str(window): int(median(ratings[:window]))
                for window in WINDOWS
                if len(ratings) >= window
            },
        }
    if available:
        latest_date, platform, sequence = available[0]
        ratings = [rating for _, rating in sequence]
        target.update({
            "recent_platform": platform,
            "latest_game_rating": ratings[0],
            "latest_game_date": latest_date.date().isoformat(),
            "rated_games_on_recent_platform": len(ratings),
            "rolling_medians": {
                str(window): int(median(ratings[:window]))
                for window in WINDOWS
                if len(ratings) >= window
            },
        })

    return {
        "audit": "canonical_rating_resolution_bakeoff",
        "read_only": True,
        "coverage": dict(coverage),
        "user_platform_sequences": len(by_user_platform),
        "candidates": {
            str(window): {
                "next_game_absolute_error": _summary(errors[window]),
                "estimate_step_change": _summary(movements[window]),
                "predictions": predictions[window],
            }
            for window in WINDOWS
        },
        "target_account": target,
    }


def main() -> int:
    client = MongoClient(os.environ["MONGO_URL"], serverSelectionTimeoutMS=10_000)
    try:
        report = build_report(
            client[os.environ.get("DB_NAME", "chess_coach")],
            target_email="bhutramohit@gmail.com",
        )
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
