"""Real rating curves since a player joined.

The two rules worth a test: the strip always carries its denominator, and
it never leaks who the players are.
"""

import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services import rating_journeys as rj  # noqa: E402


class _Cursor:
    def __init__(self, rows):
        self._rows = rows

    def sort(self, *_a, **_k):
        return self

    def limit(self, n):
        self._rows = self._rows[:n]
        return self

    async def to_list(self, _n):
        return self._rows

    def __aiter__(self):
        async def gen():
            for r in self._rows:
                yield r

        return gen()


class _Users:
    def __init__(self, rows):
        self._rows = rows

    def find(self, *_a, **_k):
        return _Cursor(list(self._rows))


class _Games:
    def __init__(self, by_user):
        self._by_user = by_user

    def find(self, query, *_a, **_k):
        return _Cursor(list(self._by_user.get(query.get("user_id"), [])))


class _DB:
    def __init__(self, users, games):
        self.users = _Users(users)
        self.games = _Games(games)


def _ratings(values):
    return [{"user_rating": v} for v in values]


def test_parses_a_string_created_at():
    """users.created_at is an ISO STRING and games.played_at_utc is a naive
    datetime. Treating the string as unparseable returned zero of
    everything, which has exactly the shape of a real finding."""
    got = rj._parse("2026-02-10T10:33:38.275473+00:00")
    assert isinstance(got, datetime)
    assert got.tzinfo is None          # comparable with a naive played_at_utc
    assert rj._parse(datetime(2026, 3, 1, tzinfo=timezone.utc)).tzinfo is None
    assert rj._parse(None) is None
    assert rj._parse("not a date") is None


def test_counts_the_fallers_as_well_as_the_risers():
    db = _DB(
        users=[{"user_id": f"u{i}", "created_at": "2026-01-01T00:00:00+00:00"} for i in range(3)],
        games={
            "u0": _ratings(list(range(1000, 1030))),   # up
            "u1": _ratings(list(range(1200, 1170, -1))),  # down
            "u2": _ratings([1100] * 30),               # flat
        },
    )
    out = asyncio.run(rj.build_rating_journeys(db))

    assert out["counts"]["measurable"] == 3
    assert out["counts"]["up"] == 1
    assert out["counts"]["down"] == 1
    assert out["counts"]["flat"] == 1


def test_a_player_with_too_few_games_is_counted_not_shown():
    db = _DB(
        users=[{"user_id": "u0", "created_at": "2026-01-01T00:00:00+00:00"}],
        games={"u0": _ratings([1000, 1100, 1200])},   # 3 < MIN_GAMES
    )
    out = asyncio.run(rj.build_rating_journeys(db))

    assert out["journeys"] == []
    assert out["counts"]["too_few_games"] == 1
    assert out["counts"]["measurable"] == 0


def test_it_returns_nothing_that_identifies_anybody():
    """A chess.com handle is public, but printing it beside our product
    name asserts this person uses ChessGuru. No consent field exists."""
    import json

    db = _DB(
        users=[{"user_id": "user_secret", "created_at": "2026-01-01T00:00:00+00:00"}],
        games={"user_secret": _ratings(list(range(900, 940)))},
    )
    out = asyncio.run(rj.build_rating_journeys(db))

    text = json.dumps(out)
    assert "user_secret" not in text
    for field in ["user_id", "username", "handle", "avatar", "name"]:
        assert field not in text


def test_the_curve_is_sampled_but_keeps_both_ends():
    db = _DB(
        users=[{"user_id": "u0", "created_at": "2026-01-01T00:00:00+00:00"}],
        games={"u0": _ratings(list(range(800, 1600)))},
    )
    out = asyncio.run(rj.build_rating_journeys(db))
    curve = out["journeys"][0]["curve"]

    assert len(curve) == rj.CURVE_POINTS
    assert curve[0] == 800
    assert curve[-1] == 1599
    assert out["journeys"][0]["delta"] == 799


def test_the_strip_is_capped_but_the_counts_are_not():
    db = _DB(
        users=[{"user_id": f"u{i}", "created_at": "2026-01-01T00:00:00+00:00"} for i in range(20)],
        games={f"u{i}": _ratings(list(range(1000, 1030 + i))) for i in range(20)},
    )
    out = asyncio.run(rj.build_rating_journeys(db))

    assert len(out["journeys"]) == rj.STRIP_SIZE
    assert out["counts"]["measurable"] == 20       # the denominator is everybody
    # biggest gain first
    deltas = [j["delta"] for j in out["journeys"]]
    assert deltas == sorted(deltas, reverse=True)
