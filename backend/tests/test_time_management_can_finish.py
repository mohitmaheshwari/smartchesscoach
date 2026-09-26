"""A time-management focus must be measurable, or it can never end.

The topic was switched off in code, not missing:

    _TIME_MANAGEMENT_OUTCOME_CHECK_FIXED = False
    # 18 of 38 active weakness-locks were permanently wedged on
    # time_management, extending 7 more days on every check with no way out.

The cause: `_topic_rates` measures a topic by counting `move_observations` with
that `missed_pattern`, and `missed_pattern` is NEVER "time_management" -- zero
rows of 550,000. So the outcome check returned `measurement_pending` for ever.

The 28-day time box removed the wedge but is not a measure: it closes a focus
as `time_boxed`, never as `improved`, so the player is told we are moving on and
never told they got better.
"""
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from services.primary_weakness_picker import (  # noqa: E402
    TIME_MANAGEMENT_FLAGS,
    _time_management_rates,
)


class _Cursor:
    def __init__(self, docs):
        self._docs = docs

    def __aiter__(self):
        async def gen():
            for doc in self._docs:
                yield doc
        return gen()


class _Games:
    def __init__(self, docs):
        self.docs = docs
        self.last_query = None

    def find(self, query, _projection=None):
        self.last_query = query
        ids = set((query.get("game_id") or {}).get("$in") or [])
        return _Cursor([d for d in self.docs if d.get("game_id") in ids])


class _Obs:
    def __init__(self, rows):
        self.rows = rows
        self.last_query = None

    async def count_documents(self, query):
        self.last_query = query
        ids = set((query.get("game_id") or {}).get("$in") or [])
        flags = set((query.get("time_flag") or {}).get("$in") or [])
        return sum(1 for r in self.rows
                   if r["game_id"] in ids and r["time_flag"] in flags)


class _DB:
    def __init__(self, obs_rows, game_docs):
        self.move_observations = _Obs(obs_rows)
        self.games = _Games(game_docs)


def _timeout(game_id, lost=True):
    return {"game_id": game_id, "termination": "timeout",
            "user_color": "white", "result": "0-1" if lost else "1-0"}


@pytest.mark.asyncio
async def test_it_measures_where_topic_rates_returns_nothing():
    db = _DB([{"game_id": "a", "time_flag": "time_pressure_blunder"}],
             [_timeout("a")])
    rates = await _time_management_rates(db, "u1", ["a"], ["a"])
    assert rates is not None
    before, _after = rates
    assert before["name"] == "time_management_per_game"
    assert before["occurrence_count"] == 2   # one flag, one timeout loss


@pytest.mark.asyncio
async def test_a_timeout_the_player_WON_is_not_clock_damage():
    """`termination` says the game ended on the clock, not whose clock. Around
    half of them are wins, and counting those would tell a player their time
    management is failing on the games they won by it."""
    db = _DB([], [_timeout("a", lost=False)])
    before, _ = await _time_management_rates(db, "u1", ["a"], ["a"])
    assert before["occurrence_count"] == 0


@pytest.mark.asyncio
async def test_a_timeout_the_player_LOST_counts():
    db = _DB([], [_timeout("a", lost=True)])
    before, _ = await _time_management_rates(db, "u1", ["a"], ["a"])
    assert before["occurrence_count"] == 1


@pytest.mark.asyncio
async def test_moving_fast_is_not_counted_as_a_time_problem():
    """Measured across 42 players: mistakes are LESS rushed than ordinary moves
    (13.2% against 23.5%), and not one player makes their mistakes faster than
    their usual pace. Speed explains a move; it is not a trait, and scoring the
    topic on it would tell almost everyone something untrue."""
    assert "snap_decision" not in TIME_MANAGEMENT_FLAGS
    db = _DB([{"game_id": "a", "time_flag": "snap_decision"}], [])
    before, _ = await _time_management_rates(db, "u1", ["a"], ["a"])
    assert before["occurrence_count"] == 0


@pytest.mark.asyncio
async def test_both_halves_are_counted_the_same_way():
    """If the two windows were counted differently, the gate alone would read
    as improvement."""
    rows = [{"game_id": "old", "time_flag": "slow_paralysis"},
            {"game_id": "new", "time_flag": "slow_paralysis"}]
    db = _DB(rows, [])
    before, after = await _time_management_rates(db, "u1", ["old"], ["new"])
    assert before["value"] == after["value"] == 1.0


@pytest.mark.asyncio
async def test_improvement_is_visible_as_a_lower_rate():
    rows = [{"game_id": "o1", "time_flag": "time_pressure_blunder"},
            {"game_id": "o2", "time_flag": "time_pressure_blunder"}]
    db = _DB(rows, [])
    before, after = await _time_management_rates(db, "u1", ["o1", "o2"], ["n1", "n2"])
    assert before["value"] == 1.0
    assert after["value"] == 0.0


@pytest.mark.asyncio
async def test_an_empty_window_is_unmeasured_not_zero():
    """No games is not "they stopped doing it"."""
    assert await _time_management_rates(_DB([], []), "u1", [], ["a"]) is None


def test_the_topic_is_enabled_again():
    source = (BACKEND_ROOT / "services" / "primary_weakness_picker.py").read_text(
        encoding="utf-8")
    assert "_TIME_MANAGEMENT_OUTCOME_CHECK_FIXED = True" in source


def test_the_outcome_check_routes_this_topic_to_its_own_measure():
    """The whole failure was a topic with no branch. If the dispatch stops
    naming it, it silently goes back to measurement_pending for ever."""
    source = (BACKEND_ROOT / "services" / "primary_weakness_picker.py").read_text(
        encoding="utf-8")
    assert 'elif topic == "time_management":' in source
    assert "_time_management_rates(db, user_id, before_ids, after_ids)" in source
