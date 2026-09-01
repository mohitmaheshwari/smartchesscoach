import pytest

from services.rating_resolver import (
    get_current_rating,
    resolve_coaching_rating,
)


class _Cursor:
    def __init__(self, rows):
        self.rows = rows

    async def to_list(self, length=None):
        return list(self.rows if length is None else self.rows[:length])


class _Collection:
    def __init__(self, rows):
        self.rows = rows

    async def find_one(self, query):
        return next((row for row in self.rows if row.get("user_id") == query.get("user_id")), None)

    def find(self, query, projection=None):
        return _Cursor([
            row for row in self.rows
            if row.get("user_id") == query.get("user_id")
        ])


class _DB:
    def __init__(self, games, user, profile=None):
        self.games = _Collection(games)
        self.users = _Collection([user])
        self.player_profiles = _Collection([profile or {"user_id": user["user_id"]}])


def _game(date, rating, platform):
    return {
        "user_id": "u1",
        "date_played": date,
        "user_rating": rating,
        "platform": platform,
    }


@pytest.mark.asyncio
async def test_selected_platform_wins_over_newer_other_platform():
    games = [
        _game("2026.08.29", 887, "chess.com"),
        _game("2026.08.28", 901, "chess.com"),
        _game("2026.08.27", 880, "chess.com"),
        _game("2026-08-31T10:00:00Z", 1334, "lichess"),
    ]
    user = {"user_id": "u1", "rating_source": "chess.com", "detected_rating": 1241}
    result = await resolve_coaching_rating(_DB(games, user), "u1", user=user)
    assert result == {
        "rating": 887,
        "source": "recent_game_median",
        "platform": "chess.com",
        "sample_games": 3,
        "as_of": "2026-08-29T00:00:00+00:00",
    }


@pytest.mark.asyncio
async def test_malformed_lexicographic_order_cannot_choose_an_older_game():
    games = [
        _game("2026.04.01", 1175, "chess.com"),
        _game("2026-08-31T10:00:00Z", 900, "chess.com"),
        _game("2026-08-30", 910, "chess.com"),
    ]
    user = {"user_id": "u1", "rating_source": "chess.com"}
    result = await resolve_coaching_rating(_DB(games, user), "u1", user=user)
    assert result["rating"] == 910
    assert result["as_of"].startswith("2026-08-31")


@pytest.mark.asyncio
async def test_fractional_second_iso_timestamp_is_preserved():
    games = [
        _game("2026-08-31T09:00:00.250Z", 1000, "chess.com"),
        _game("2026-08-31T10:00:00.500Z", 900, "chess.com"),
        _game("2026-08-30", 1100, "chess.com"),
        _game("2026-08-29", 1500, "chess.com"),
    ]
    result = await resolve_coaching_rating(
        _DB(games, {"user_id": "u1", "rating_source": "chess.com"}),
        "u1",
    )
    assert result["rating"] == 1000
    assert result["as_of"] == "2026-08-31T10:00:00.500000+00:00"


def test_named_platform_source_maps_to_its_fallback_field():
    assert get_current_rating(
        {"rating_source": "chess.com", "detected_rating": 887},
        {"current_rating": 1199},
    ) == 887
    assert get_current_rating(
        {"rating_source": "lichess", "lichess_rating": 1334}, {}
    ) == 1334
