"""The solved filter must be applied by the QUERY, not after it.

Measured on prod 2026-10-04: every one of the 22 community rows the lesson
fetched for the deploy gate's user was already solved, so the lesson got zero
candidates and 409'd -- with 3,228 matching positions sitting behind those 22.
`solve_rate` is 0.0 on every row in that pool, so the sort is entirely tied and
`.limit()` returns an arbitrary window; it is not even the same window at limit
22 as at limit 500.

Fetching deeper would only move the cliff, because the solved set grows every
time the player succeeds. The filter has to be in the query so the limit applies
to rows that can actually be served.

These tests use a recording fake rather than a database. They assert the
exclusion reaches the query and that it names the right field per collection --
`_id` for community_puzzles, whose ids are ObjectIds, and `position_id` for the
coach pool, whose ids are strings. Getting that pairing wrong would exclude
nothing while looking correct.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from bson import ObjectId

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

import services.puzzle_extraction_service as pes  # noqa: E402


class _Cursor:
    def __init__(self, rows):
        self._rows = rows

    def sort(self, *args, **kwargs):
        self._sort = args
        return self

    def limit(self, _n):
        return self

    def __aiter__(self):
        async def gen():
            for row in self._rows:
                yield row
        return gen()


class _Collection:
    def __init__(self, recorder, name):
        self._recorder = recorder
        self._name = name

    def find(self, query=None, projection=None):
        self._recorder.append((self._name, dict(query or {})))
        return _Cursor([])

    async def count_documents(self, *_a, **_k):
        return 0


class _FakeDb:
    """Records every query it is asked for and returns nothing."""

    def __init__(self):
        self.queries = []
        self._solved = []

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        if name == "puzzle_attempts":
            return _AttemptsCollection(self._solved)
        return _Collection(self.queries, name)

    def __getitem__(self, name):
        return getattr(self, name)


class _AttemptsCollection:
    def __init__(self, solved):
        self._solved = solved

    def find(self, *_a, **_k):
        return _Cursor([{"puzzle_id": pid} for pid in self._solved])


@pytest.fixture
def fake(monkeypatch):
    async def _no_decay(*_a, **_k):
        return {}
    monkeypatch.setattr(pes, "refresh_user_pattern_decay", _no_decay,
                        raising=False)
    monkeypatch.setattr(
        "services.pattern_decay_service.refresh_user_pattern_decay",
        _no_decay, raising=False)
    return _FakeDb()


def _queries_for(fake, collection):
    return [q for name, q in fake.queries if name == collection]


@pytest.mark.asyncio
async def test_community_puzzles_excludes_solved_object_ids(fake):
    solved = ObjectId()
    fake._solved.extend([str(solved), "coach_not_an_objectid"])
    await pes.get_pattern_training_puzzles(fake, "u1", "piece_safety", 12)

    community = [q for q in _queries_for(fake, "community_puzzles")
                 if q.get("shared_by") == {"$ne": "u1"}]
    assert community, "the community branch never ran"
    clause = community[0].get("_id")
    assert clause and "$nin" in clause, (
        "solved positions are not excluded by the query; the limit will apply "
        "to rows that cannot be served")
    assert solved in clause["$nin"]
    # The non-ObjectId id belongs to the other pool and must not be smuggled in
    # here, where it would match nothing and quietly do nothing.
    assert all(isinstance(v, ObjectId) for v in clause["$nin"])


@pytest.mark.asyncio
async def test_coach_pool_excludes_solved_by_position_id(fake):
    fake._solved.append("game_abc_m14")
    await pes.get_pattern_training_puzzles(fake, "u1", "piece_safety", 12)

    coach = _queries_for(fake, "community_training_positions")
    assert coach, "the coach pool branch never ran"
    filtered = [q for q in coach if "position_id" in q]
    assert filtered, (
        "the coach pool fetch does not exclude solved positions, so its limit "
        "applies to rows that cannot be served")
    assert filtered[0]["position_id"]["$nin"] == ["game_abc_m14"]


@pytest.mark.asyncio
async def test_no_exclusion_clause_when_nothing_is_solved(fake):
    """A new player must not get an empty `$nin`, which some drivers treat as
    matching nothing at all."""
    await pes.get_pattern_training_puzzles(fake, "u1", "piece_safety", 12)
    for _name, query in fake.queries:
        for field in ("_id", "position_id"):
            clause = query.get(field)
            if isinstance(clause, dict) and "$nin" in clause:
                assert clause["$nin"], (
                    "%s got an empty $nin for a player with no solves" % field)


@pytest.mark.asyncio
async def test_sort_has_a_tiebreaker(fake):
    """solve_rate is 0.0 across the whole pool, so a sort on it alone leaves
    the order to the planner and it changes with the limit."""
    captured = {}

    class _SortRecordingCursor(_Cursor):
        def sort(self, *args, **kwargs):
            captured.setdefault("sorts", []).append(args)
            return self

    def _find(self, query=None, projection=None):
        self._recorder.append((self._name, dict(query or {})))
        return _SortRecordingCursor([])

    _Collection.find = _find
    try:
        await pes.get_pattern_training_puzzles(fake, "u1", "piece_safety", 12)
    finally:
        _Collection.find = _Collection.__dict__["find"]

    sorts = captured.get("sorts") or []
    keyed = [s[0] for s in sorts if s and isinstance(s[0], list)]
    assert keyed, "no sort used a key list, so none can carry a tiebreaker"
    assert any(len(k) > 1 for k in keyed), (
        "every sort is on a single key; a fully tied pool then comes back in "
        "whatever order the planner picks")
