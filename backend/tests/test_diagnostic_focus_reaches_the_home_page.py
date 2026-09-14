"""A player who answered the positions has a focus to show.

`user_active_focus` is game evidence. Its picker requires 10 analysed games,
and services/accepted_cause_service.py explains why a second writer into that
collection is unsafe: the one-active-row invariant is enforced by an unsorted
`find_one`, so a competing row makes "the user's focus" non-deterministic
across five consumers and leaks into Lab's Coach's-Pick.

So a diagnostic-only player can never have a row there, by design -- and
/coach/active-focus returned `has_focus: False` even after they answered
twenty positions and the diagnosis wrote a focus into coach_memory.

The fix is read-side: the endpoint falls back to that focus and says where it
came from. Nothing is written, and `provisional: True` keeps twenty puzzles
from being mistaken for board-verified evidence.

Reported 2026-09-14 (user_ed32375808ad): diagnostic complete with four scored
categories and coach_memory.learning.current_focus = "opening_knowledge",
while get_active_focus_bundle returned None and the home page had nothing.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

import routes.coach as coach_routes


class _Memory:
    def __init__(self, document):
        self.document = document

    async def find_one(self, query, projection=None):
        return dict(self.document) if self.document else None


class _DB:
    def __init__(self, document):
        self.coach_memory = _Memory(document)


def _fallback(document):
    original = getattr(coach_routes, "db", None)
    coach_routes.db = _DB(document)
    try:
        return asyncio.run(coach_routes._diagnostic_focus_fallback("u1"))
    finally:
        coach_routes.db = original


DIAGNOSTIC = {
    "learning": {"current_focus": "opening_knowledge",
                 "focus_source": "diagnostic"}
}


def test_the_diagnostic_focus_is_offered_when_there_is_no_proven_one():
    result = _fallback(DIAGNOSTIC)
    assert result is not None
    assert result["has_focus"] is True
    assert result["topic_key"] == "opening_knowledge"
    assert result["topic_label"] == "Opening knowledge"


def test_it_is_marked_provisional_and_says_where_it_came_from():
    # Twenty positions is not the same evidence as the player's own games,
    # and every caller has to be able to tell the difference.
    result = _fallback(DIAGNOSTIC)
    assert result["provisional"] is True
    assert result["focus_source"] == "diagnostic"
    assert "positions you played me" in result["evidence_note"]


def test_it_carries_no_metrics_it_has_not_measured():
    result = _fallback(DIAGNOSTIC)
    assert result["baseline_metric"] is None
    assert result["current_metric"] is None
    assert result["days_remaining"] is None
    assert result["runners_up"] == []


def test_a_focus_from_any_other_source_is_left_alone():
    # Only the diagnostic's own write is offered this way. A focus set by the
    # game-evidence path reaches the caller through the normal branch, and
    # must not be duplicated through here.
    assert _fallback({"learning": {"current_focus": "piece_safety",
                                   "focus_source": "games"}}) is None
    assert _fallback({"learning": {"current_focus": "piece_safety"}}) is None


def test_no_focus_means_no_claim():
    assert _fallback({"learning": {"current_focus": None,
                                   "focus_source": "diagnostic"}}) is None
    assert _fallback({"learning": {}}) is None
    assert _fallback(None) is None


def test_a_database_that_fails_does_not_break_the_page():
    class _Broken:
        async def find_one(self, *a, **k):
            raise RuntimeError("mongo is down")

    class _BrokenDB:
        coach_memory = _Broken()

    original = getattr(coach_routes, "db", None)
    coach_routes.db = _BrokenDB()
    try:
        assert asyncio.run(coach_routes._diagnostic_focus_fallback("u1")) is None
    finally:
        coach_routes.db = original
