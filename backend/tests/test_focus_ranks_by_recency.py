"""The focus must name what the player is doing lately, not their whole history.

The picker summed lifetime event counts with no sense of when, so a blunder from
two hundred games ago weighed exactly as much as yesterday's. The one thing we
tell a player to work on could not tell a one-off from a habit.

`pattern_decay_service` has computed the recency-weighted version since long
before this, and eight services used it. The picker did not.

Measured over every game on production 2026-09-26: ranking by recency changes
the focus TOPIC for 14 of 57 users (25%), against 1 of 53 for the best
board-motif detector promotion available.
"""
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from services.pattern_decay_service import DECAY_RATE  # noqa: E402
from services.primary_weakness_picker import (  # noqa: E402
    DECAY_WINDOW_GAMES,
    _SEVERITY_WEIGHT,
    _recency_weights,
)


class _Cursor:
    def __init__(self, docs):
        self._docs = docs

    def sort(self, *_args, **_kwargs):
        return self

    async def to_list(self, length=None):
        return self._docs[:length] if length else self._docs


class _Games:
    def __init__(self, docs):
        self.docs = docs
        self.last_query = None
        self.last_sort = None

    def find(self, query, _projection=None):
        self.last_query = query
        return _Cursor(self.docs)


class _DB:
    def __init__(self, docs):
        self.games = _Games(docs)


@pytest.mark.asyncio
async def test_the_newest_game_weighs_one_and_older_games_less():
    db = _DB([{"game_id": "g0"}, {"game_id": "g1"}, {"game_id": "g2"}])
    weights = await _recency_weights(db, "u1")
    assert weights["g0"] == 1.0
    assert weights["g1"] == pytest.approx(DECAY_RATE)
    assert weights["g2"] == pytest.approx(DECAY_RATE ** 2)
    assert weights["g0"] > weights["g1"] > weights["g2"]


@pytest.mark.asyncio
async def test_it_orders_by_the_typed_date_not_the_legacy_string():
    """`date_played` holds ISO timestamps, chess.com's dotted 2026.04.15 and
    nothing for coach games, and "." sorts above "-" in ASCII -- so a string
    sort puts every dotted date after every timestamp whatever day it names.
    That put 407 games on the wrong side of 15 focus windows."""
    db = _DB([{"game_id": "g0"}])
    await _recency_weights(db, "u1")
    assert "played_at_utc" in db.games.last_query
    assert "date_played" not in db.games.last_query


@pytest.mark.asyncio
async def test_only_analysed_games_count():
    db = _DB([{"game_id": "g0"}])
    await _recency_weights(db, "u1")
    assert db.games.last_query.get("is_analyzed") is True


@pytest.mark.asyncio
async def test_a_game_outside_the_window_is_absent_not_tiny():
    """The decay model's own behaviour: past the window it is history, not a
    habit. Present-with-a-tiny-weight would let a long-ago streak outvote this
    week simply by being numerous."""
    db = _DB([{"game_id": "g%d" % i} for i in range(DECAY_WINDOW_GAMES + 10)])
    weights = await _recency_weights(db, "u1")
    assert len(weights) == DECAY_WINDOW_GAMES
    assert "g%d" % (DECAY_WINDOW_GAMES + 5) not in weights


@pytest.mark.asyncio
async def test_a_player_with_no_dated_games_gets_no_weights():
    """The caller falls back to the lifetime total in that case, rather than
    dropping the topic: stale beats silent."""
    assert await _recency_weights(_DB([]), "u1") == {}


def test_recent_evidence_outranks_older_evidence_of_the_same_size():
    """The arithmetic the ranking turns on, stated directly: the same number of
    events weighs more when they are recent."""
    weight = _SEVERITY_WEIGHT.get("moderate", 1.0)
    recent = sum(weight * DECAY_RATE ** i for i in range(3))
    older = sum(weight * DECAY_RATE ** i for i in range(10, 13))
    assert recent > older


def test_a_long_dead_habit_can_lose_to_a_smaller_live_one():
    """The whole point. Twelve events, all of them ten or more games ago,
    against four in the last four games."""
    weight = _SEVERITY_WEIGHT.get("moderate", 1.0)
    dead = sum(weight * DECAY_RATE ** i for i in range(10, 22)
               if i < DECAY_WINDOW_GAMES)
    live = sum(weight * DECAY_RATE ** i for i in range(4))
    assert live > dead, "a live habit must outrank a dead one"
