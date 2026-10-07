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

def _loop_source() -> str:
    """The real loop body. Asserted against directly.

    This file used to keep a MIRROR of the selector the loop builds, and the
    mirror went stale the moment the loop changed: it still appended a lock
    clause under render while the code had stopped doing so, so the test would
    have passed while asserting the opposite of the truth. A copy of the thing
    under test is not a test of it.
    """
    import inspect

    import server
    return inspect.getsource(server.focus_outcome_loop)


def test_neither_mode_filters_the_selector_on_the_lock():
    """Render mode used to add a due clause to the SELECTOR.

    That meant enabling it stopped measuring the 27 of 53 focuses whose lock
    had not expired -- they would have gone dark at exactly the moment the
    measurement started being used. Measuring early costs nothing; only
    CLOSING early is harmful, so only closing is gated.
    """
    src = _loop_source()
    selector_part = src[src.index("selector = {"):src.index("async for f in")]
    assert "locked_until" not in selector_part, selector_part
    assert "append" not in selector_part, "no mode may narrow the selector"


def test_the_daily_observation_is_recorded_in_both_modes():
    """It used to be the shadow's *alternative* to closing, so turning render
    on would have silently ended the series -- 21 consecutive days deep, and
    the only per-focus history that exists anywhere. A closure gives one
    point; the chain needs a trajectory."""
    src = _loop_source()
    record = src.index("_record_shadow_outcome(")
    gate = src.index("if not render")
    assert record < gate, "the observation must be written before the render gate"


def test_closing_requires_both_render_and_a_due_lock():
    src = _loop_source()
    assert "if not render or not is_due:" in src, src[src.index("if not render"):][:120]
    gate = src.index("if not render or not is_due:")
    close = src.index("close_focus(db, f, outcome)")
    assert gate < close, "close_focus must sit behind the gate"


def test_both_modes_exclude_strength_focuses():
    """39 of the 92 active rows on production are `type: "strength"` and carry
    a null `locked_until`. They are excluded by type, not by the lock -- a
    pre-sprint audit misread that as 39 weakness focuses being invisible."""
    src = _loop_source()
    assert '"type": "weakness"' in src


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

def test_the_log_line_does_not_lie_about_the_mode():
    """`n_shadowed` counts every measured focus in BOTH modes now, so the old
    single message would have printed "nothing rendered; the flag is off"
    while the flag was on. A log that lies is worse than no log; that exact
    shape cost real time in a deploy script that reported the docroot
    untouched while deleting it."""
    src = _loop_source()
    split = src.index("elif n_shadowed:")
    on_msg, off_msg = src[:split], src[split:]
    # the off path must still say so
    assert "is off" in off_msg, off_msg
    # the render path must not, and must report what it actually did
    render_msg = on_msg[on_msg.rindex("if render:"):]
    assert "is off" not in render_msg, render_msg
    assert "closed" in render_msg, render_msg
    assert "not due yet" in render_msg, render_msg
