"""Product events have somewhere to land.

Forty-odd funnel events have been fired from the frontend for months and every
one was a no-op: `track()` guards on `window.posthog`, nothing calls
`posthog.init()`, there is no project key in the built bundle and no POSTHOG
env on the server. Nothing a player did was ever recorded, which is why every
behavioural question this week had to be answered by reconstructing intent
from database side-effects -- and why several could not be answered at all.

The sink is our own collection. The vocabulary of allowed events and prop keys
already has an owner in frontend/src/lib/analytics.js; this layer deliberately
does not copy it, and enforces SHAPE instead.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from routes.product_events import (
    MAX_EVENTS_PER_BATCH,
    MAX_PROPS,
    MAX_VALUE_LENGTH,
    _clean_batch,
    _clean_props,
    _clean_value,
)


def test_a_normal_event_survives_intact():
    batch = _clean_batch([
        {"event": "diagnostic_first_answer",
         "props": {"puzzle_number": 1, "is_correct": False}},
    ])
    assert batch == [
        {"event": "diagnostic_first_answer",
         "props": {"puzzle_number": 1, "is_correct": False}},
    ]


def test_scalars_only():
    # Nested structures are where free text and PII hide.
    assert _clean_value({"nested": "object"}) is None
    assert _clean_value(["a", "list"]) is None
    assert _clean_value(None) is None
    assert _clean_value(True) is True
    assert _clean_value(12) == 12
    assert _clean_value(1.5) == 1.5
    assert _clean_value("text") == "text"


def test_long_values_are_truncated_not_rejected():
    long = "x" * (MAX_VALUE_LENGTH + 500)
    assert len(_clean_value(long)) == MAX_VALUE_LENGTH


def test_an_oversized_batch_is_capped():
    events = [{"event": f"e{i}", "props": {}} for i in range(MAX_EVENTS_PER_BATCH + 40)]
    assert len(_clean_batch(events)) == MAX_EVENTS_PER_BATCH


def test_too_many_props_are_capped():
    props = {f"k{i}": i for i in range(MAX_PROPS + 30)}
    assert len(_clean_props(props)) == MAX_PROPS


def test_junk_is_dropped_rather_than_raising():
    # A malformed beacon must never cost a player their action.
    assert _clean_batch("not a list") == []
    assert _clean_batch([None, 3, "x"]) == []
    assert _clean_batch([{"props": {"a": 1}}]) == []   # no event name
    assert _clean_props("not a dict") == {}


def test_an_event_with_no_props_is_still_recorded():
    assert _clean_batch([{"event": "funnel_landing_viewed"}]) == [
        {"event": "funnel_landing_viewed", "props": {}}
    ]


def test_the_endpoint_never_fails_the_caller():
    """Even with a database that throws, the player's action still completes."""
    import routes.product_events as pe

    class _Broken:
        async def insert_many(self, *a, **k):
            raise RuntimeError("mongo is down")

    class _DB:
        def __getitem__(self, name):
            return _Broken()

    class _Request:
        cookies = {}
        headers = {}

    original = pe.db
    pe.db = _DB()
    try:
        result = asyncio.run(
            pe.record_product_events(
                pe.EventBatch(events=[{"event": "funnel_home_viewed"}]),
                _Request(),
            )
        )
        assert result == {"stored": 0}
    finally:
        pe.db = original


def test_an_anonymous_visitor_is_recorded_not_rejected():
    """The landing page fires before anyone signs in.

    get_current_user raises 401 for an anonymous caller, and that part of the
    funnel is exactly what we cannot currently see, so the 401 is swallowed
    and the event is stored with user_id None.
    """
    import routes.product_events as pe

    stored = {}

    class _Collection:
        async def insert_many(self, documents, ordered=True):
            stored["documents"] = documents

    class _DB:
        def __getitem__(self, name):
            return _Collection()

    class _Request:
        cookies = {}
        headers = {}

    original = pe.db
    pe.db = _DB()
    try:
        result = asyncio.run(
            pe.record_product_events(
                pe.EventBatch(events=[{"event": "funnel_landing_viewed"}]),
                _Request(),
            )
        )
    finally:
        pe.db = original

    assert result == {"stored": 1}
    document = stored["documents"][0]
    assert document["event"] == "funnel_landing_viewed"
    assert document["anonymous"] is True
    assert document["user_id"] is None
    assert document["occurred_at"] is not None
