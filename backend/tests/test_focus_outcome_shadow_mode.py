"""Shadow mode must measure everything and render nothing.

No focus has ever completed a cycle on production, so there is no history to
pick a terminal-state rule from -- how many extensions, or how many days,
before a user is told "we could not gather enough comparable games". Shadow
mode collects that distribution without putting a first-ever verdict in front
of anyone.

Two properties matter and both are asserted here:

  1. with rendering off, `close_focus` is NEVER called, so no focus document
     changes and nothing reaches a user;
  2. with rendering off the loop measures EVERY active weakness focus, not
     only those whose lock expired -- on 2026-09-17 every active lock was
     still in the future, so a due-only pass would have collected nothing for
     a fortnight.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv("FOCUS_OUTCOME_RENDER_ENABLED", raising=False)


def _flag():
    import server
    return server.focus_outcome_render_enabled()


def test_render_is_off_by_default():
    assert _flag() is False


@pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes", "on", "On"])
def test_render_flag_accepts_the_usual_truthy_spellings(monkeypatch, value):
    monkeypatch.setenv("FOCUS_OUTCOME_RENDER_ENABLED", value)
    assert _flag() is True


@pytest.mark.parametrize("value", ["", "0", "false", "no", "off", "maybe"])
def test_anything_else_leaves_render_off(monkeypatch, value):
    monkeypatch.setenv("FOCUS_OUTCOME_RENDER_ENABLED", value)
    assert _flag() is False


# --- selection ------------------------------------------------------------

def _selector(render: bool, now: datetime):
    """Mirror of the selector the loop builds, kept in one place."""
    now_iso = now.isoformat()
    type_clause = {"$or": [{"type": {"$exists": False}}, {"type": "weakness"}]}
    due_clause = {"$or": [
        {"locked_until": {"$type": "date", "$lte": now}},
        {"locked_until": {"$type": "string", "$lte": now_iso}},
    ]}
    selector = {"status": "active", "$and": [type_clause]}
    if render:
        selector["$and"].append(due_clause)
    return selector


def test_shadow_mode_does_not_filter_on_the_lock():
    now = datetime.now(timezone.utc)
    clauses = _selector(render=False, now=now)["$and"]
    assert len(clauses) == 1, "shadow mode must not restrict to due focuses"
    assert "locked_until" not in str(clauses)


def test_render_mode_still_only_takes_due_focuses():
    now = datetime.now(timezone.utc)
    clauses = _selector(render=True, now=now)["$and"]
    assert len(clauses) == 2
    assert "locked_until" in str(clauses)


def test_both_modes_exclude_strength_focuses():
    """39 of the 92 active rows on production are `type: "strength"` and carry
    a null `locked_until`. They are excluded by type, not by the lock -- a
    pre-sprint audit misread that as 39 weakness focuses being invisible."""
    now = datetime.now(timezone.utc)
    for render in (True, False):
        s = str(_selector(render, now))
        assert "'type': 'weakness'" in s or '"type": "weakness"' in s


# --- the due flag recorded alongside each shadow row -----------------------

def _is_due(lock, now):
    """Exercises the real implementation, not a copy of it."""
    import server
    return server._lock_is_due(lock, now, now.isoformat())


def test_due_flag_handles_both_stored_lock_types():
    """`locked_until` is a BSON date on 43 rows and an ISO string on 10."""
    now = datetime(2026, 9, 17, 12, 0, tzinfo=timezone.utc)
    past, future = now - timedelta(days=1), now + timedelta(days=1)
    assert _is_due(past, now) is True
    assert _is_due(future, now) is False
    assert _is_due(past.isoformat(), now) is True
    assert _is_due(future.isoformat(), now) is False


def test_a_naive_bson_date_does_not_explode():
    """Motor returns BSON dates NAIVE. Comparing one against an aware `now`
    raises TypeError, and inside the loop's per-focus try/except that becomes
    a logged warning and a silently skipped focus -- the shadow would collect
    nothing while looking healthy. This exact class already broke a deploy
    here once."""
    now = datetime(2026, 9, 17, 12, 0, tzinfo=timezone.utc)
    naive_past = datetime(2026, 9, 16, 12, 0)     # no tzinfo, as Motor returns
    naive_future = datetime(2026, 9, 18, 12, 0)
    assert _is_due(naive_past, now) is True
    assert _is_due(naive_future, now) is False


def test_a_null_lock_is_not_due():
    assert _is_due(None, datetime.now(timezone.utc)) is False
