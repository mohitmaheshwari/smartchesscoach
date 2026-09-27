"""Four different failures must not look like one.

326 focus documents, zero resolutions, and no way to tell "the coaching failed"
from "he never heard it". Measured over every focus ever written, 2026-09-27:

    told something                      54 players
    came back and played 3+ games       39
    practised anything since            29
    the named pattern moved:  11 better, 9 worse, 14 flat
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from services.coaching_landed import (  # noqa: E402
    CAME_BACK_UNPRACTISED,
    MEANS,
    MIN_GAMES_SINCE,
    MOVED_FRACTION,
    NEVER_RETURNED,
    NOT_YET_MEASURABLE,
    PRACTISED_AND_MOVED,
    PRACTISED_AND_WORSE,
    PRACTISED_NO_CHANGE,
    evaluate_landing,
    landing_stage,
)


def test_a_player_who_never_came_back_is_not_a_coaching_failure():
    """15 of 54 were in this state. Blaming the diagnosis for them would send us
    rewriting detectors to fix a re-engagement problem."""
    assert landing_stage(MIN_GAMES_SINCE - 1, 0, 1.0, 1.0) == NEVER_RETURNED
    assert "re-engagement" in MEANS[NEVER_RETURNED]


def test_coming_back_without_practising_is_its_own_verdict():
    """10 of 54. They heard us and did nothing, which is a problem with the ASK,
    not with the diagnosis behind it."""
    assert landing_stage(20, 0, 1.0, 1.0) == CAME_BACK_UNPRACTISED
    assert "ask" in MEANS[CAME_BACK_UNPRACTISED]


def test_practising_with_no_movement_blames_the_diagnosis():
    """The one that matters. He did the work and nothing changed, so what we
    told him to work on was wrong."""
    stage = landing_stage(20, 5, 1.0, 1.0)
    assert stage == PRACTISED_NO_CHANGE
    assert "diagnosis was wrong" in MEANS[stage]


def test_improvement_is_a_fall_in_the_rate():
    """The rate counts MISTAKES per game, so down is better. Getting this
    backwards would congratulate the players who got worse."""
    assert landing_stage(20, 5, 1.0, 1.0 - MOVED_FRACTION * 2) == PRACTISED_AND_MOVED
    assert landing_stage(20, 5, 1.0, 1.0 + MOVED_FRACTION * 2) == PRACTISED_AND_WORSE


def test_a_small_wobble_is_not_movement():
    """The measured median change across 34 players was -3%, so anything inside
    a tenth is indistinguishable from doing nothing."""
    assert landing_stage(20, 5, 1.0, 0.97) == PRACTISED_NO_CHANGE
    assert landing_stage(20, 5, 1.0, 1.03) == PRACTISED_NO_CHANGE


def test_no_baseline_means_no_verdict():
    """A player with no games before the focus cannot be compared. Saying
    anything here would be a claim built on one side of a comparison."""
    assert landing_stage(20, 5, None, 0.5) == NOT_YET_MEASURABLE
    assert landing_stage(20, 5, 0.0, 0.5) == NOT_YET_MEASURABLE


def test_the_stages_gate_in_order():
    """Each stage is only reachable once the previous one passed. A player who
    never returned must not be judged on a rate."""
    assert landing_stage(0, 99, 1.0, 0.1) == NEVER_RETURNED
    assert landing_stage(99, 0, 1.0, 0.1) == CAME_BACK_UNPRACTISED


def test_every_stage_carries_what_it_means_for_us():
    """A verdict without an action is a dashboard. Each one names the response."""
    for stage in (NEVER_RETURNED, CAME_BACK_UNPRACTISED, NOT_YET_MEASURABLE,
                  PRACTISED_NO_CHANGE, PRACTISED_AND_MOVED, PRACTISED_AND_WORSE):
        assert MEANS.get(stage), stage


# ---- the DB path -------------------------------------------------------

class _Cursor:
    def __init__(self, docs):
        self._docs = docs

    async def to_list(self, length=None):
        return self._docs[:length] if length else self._docs


class _Games:
    def __init__(self, before, after):
        self.before, self.after = before, after
        self.queries = []

    def find(self, query, _projection=None):
        self.queries.append(query)
        cond = (query.get("played_at_utc") or {})
        if "$gte" in cond:
            return _Cursor([{"game_id": g} for g in self.after])
        return _Cursor([{"game_id": g} for g in self.before])


class _Counting:
    def __init__(self, n):
        self.n = n

    async def count_documents(self, _query):
        return self.n


class _DB:
    """Practice is summed across TWO collections, so the stub must tell them
    apart. An earlier version returned the same counter for both and the service
    correctly doubled it -- the stub was wrong, not the code."""

    def __init__(self, before, after, puzzles, observations, lessons=0):
        self.games = _Games(before, after)
        self.move_observations = _Counting(observations)
        self._counts = {"puzzle_attempts": _Counting(puzzles),
                        "learning_sessions": _Counting(lessons)}

    def __getitem__(self, name):
        return self._counts.get(name, _Counting(0))


def _focus(days_ago=30):
    return {"user_id": "u1", "topic_key": "piece_safety",
            "started_at": datetime.now(timezone.utc) - timedelta(days=days_ago)}


@pytest.mark.asyncio
async def test_it_splits_on_the_typed_date_not_the_legacy_string():
    """`date_played` holds three incompatible shapes and "." sorts above "-" in
    ASCII, which already put 407 games on the wrong side of 15 focus windows."""
    db = _DB(["b1"], ["a1", "a2", "a3"], 4, 10)
    await evaluate_landing(db, _focus())
    assert all("played_at_utc" in q for q in db.games.queries)
    assert not any("date_played" in q for q in db.games.queries)


@pytest.mark.asyncio
async def test_a_focus_with_no_start_date_is_refused():
    """Guessing a start date would fabricate the window the whole verdict rests
    on."""
    result = await evaluate_landing(_DB([], [], 0, 0), {"user_id": "u1"})
    assert result["stage"] == NOT_YET_MEASURABLE


@pytest.mark.asyncio
async def test_the_record_keeps_rates_internal():
    """The no-numbers rule: a rate may never be rendered."""
    db = _DB(["b1", "b2"], ["a1", "a2", "a3"], 2, 6)
    record = await evaluate_landing(db, _focus())
    for key, value in record.items():
        if isinstance(value, float):
            assert key.startswith("_"), key


@pytest.mark.asyncio
async def test_it_reaches_a_verdict_on_a_full_record():
    db = _DB(["b1", "b2"], ["a1", "a2", "a3"], 2, 6)
    record = await evaluate_landing(db, _focus())
    assert record["stage"] in (PRACTISED_AND_MOVED, PRACTISED_AND_WORSE,
                               PRACTISED_NO_CHANGE)
    assert record["games_since"] == 3
    assert record["practice_events"] == 2
    assert record["means"]


@pytest.mark.asyncio
async def test_practice_counts_puzzles_AND_lessons():
    """Either one is evidence he did something. Counting only puzzles would send
    a player who did lessons into "never practised" and blame the ask."""
    puzzles_only = _DB(["b1"], ["a1", "a2", "a3"], 3, 6, lessons=0)
    lessons_only = _DB(["b1"], ["a1", "a2", "a3"], 0, 6, lessons=3)
    assert (await evaluate_landing(puzzles_only, _focus()))["practice_events"] == 3
    assert (await evaluate_landing(lessons_only, _focus()))["practice_events"] == 3
    assert (await evaluate_landing(lessons_only, _focus()))["stage"]         != CAME_BACK_UNPRACTISED
