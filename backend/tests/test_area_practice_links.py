"""A row becomes a link only when something servable is behind it.

Mohit, 2026-10-04: "nothing is clickable for a drill". The card named six areas,
said "Needs work" against two, and sent the player nowhere.

The first version of the fix counted raw coach-pool rows and produced a link for
king_safety on the strength of 341 rows of which NONE pass verification -- the
dead link the module exists to prevent, rebuilt inside it. `verdict_serves_pattern`
is a Python-side check no Mongo clause can express, so a count can never stand in
for it. That is what these tests hold down.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

import services.area_practice_links as apl  # noqa: E402
from services.area_grades import AREAS, PHASES  # noqa: E402


@pytest.mark.asyncio
async def test_phases_never_link():
    """There is no middlegame drill, and one invented link for all three would
    be a button that lies about where it goes."""
    for key in PHASES:
        assert await apl.practice_link(None, "u1", key) is None


@pytest.mark.asyncio
async def test_every_area_is_either_routed_or_deliberately_not():
    """No area may fall through by accident: each is in a link table or in the
    named no-link list."""
    known = (set(apl._POOL_AREA_PATTERNS) | set(apl._STATIC_AREA_LINKS)
             | set(apl.NO_LINK_KEYS) | {"missed_tactic"})
    for key in AREAS:
        assert key in known, (
            "%r is neither routed nor listed as deliberately unrouted" % key)


@pytest.mark.asyncio
async def test_no_link_when_the_pool_has_nothing(monkeypatch):
    async def _empty(db, user_id, pattern):
        return False
    monkeypatch.setattr(apl, "_has_pool_supply", _empty)
    for key in apl._POOL_AREA_PATTERNS:
        if key == "missed_tactic":
            continue
        assert await apl.practice_link(None, "u1", key) is None, key


@pytest.mark.asyncio
async def test_link_when_the_pool_has_something(monkeypatch):
    """Positive control: with supply, the same keys must link. Without this the
    test above would pass on a function that never links at all."""
    async def _full(db, user_id, pattern):
        return True
    monkeypatch.setattr(apl, "_has_pool_supply", _full)
    link = await apl.practice_link(None, "u1", "piece_safety")
    assert link and link["href"] == "/training/pattern/piece_safety"


@pytest.mark.asyncio
async def test_supply_check_is_not_a_raw_count(monkeypatch):
    """The coach pool must be filtered by the verdict, not counted.

    A doc that exists but does not serve the pattern must NOT produce a link.
    """
    serving = {"calls": 0}

    class _Cursor:
        def __init__(self, rows):
            self._rows = rows

        def limit(self, _n):
            return self

        def __aiter__(self):
            async def gen():
                for row in self._rows:
                    yield row
            return gen()

    class _Coll:
        def __init__(self, rows):
            self._rows = rows

        def find(self, *_a, **_k):
            return _Cursor(self._rows)

        async def count_documents(self, *_a, **_k):
            return 0

    class _Db:
        community_puzzles = _Coll([])
        # One row that exists, is approved and complete, and does NOT serve.
        community_training_positions = _Coll([
            {"approved": True, "fen": "8/8/8/8/8/8/8/K6k w - - 0 1",
             "best_move_san": "Kb1", "verified_admission": {}},
        ])
        puzzle_attempts = _Coll([])

    def _never_serves(_doc, _pattern):
        serving["calls"] += 1
        return False

    monkeypatch.setattr(
        "services.puzzle_extraction_service.verdict_serves_pattern",
        _never_serves)
    assert await apl._has_pool_supply(_Db(), "u1", "king_safety") is False
    assert serving["calls"] > 0, (
        "the verdict check was never consulted; the supply check is counting "
        "rows again")
