"""A focus must be able to finish.

Before this, check_focus_outcome returned five verdicts and close_focus ended
the focus for two. Measured over all 531 outcome checks ever recorded:
no_data 55.2%, measurement_pending 19.0%, stuck 11.5% -- 85.7% extended. Of
284 focus documents ever written, not one closed because the player fixed the
thing.

The visible cost: promoting three detectors reached zero users, because
pick_next_focus refuses while an active focus exists and all 52 active
focuses predated the promotion.
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from services.primary_weakness_picker import (  # noqa: E402
    FOCUS_MAX_DAYS,
    close_focus,
)


class _Coll:
    def __init__(self):
        self.updates = []

    async def update_one(self, where, update):
        self.updates.append((where, update))


class _DB:
    def __init__(self):
        self.coll = _Coll()

    def __getitem__(self, _name):
        return self.coll


def _focus(age_days, **extra):
    started = datetime.now(timezone.utc) - timedelta(days=age_days)
    row = {"_id": "f1", "user_id": "u1", "topic_key": "piece_safety",
           "started_at": started, "locked_until": started, "cycle_version": 1}
    row.update(extra)
    return row


EXTEND = {"resolution": "stuck", "action": "extend", "delta_pct": 2.0,
          "current_metric": {"value": 1.0}}


@pytest.mark.asyncio
async def test_a_young_focus_still_extends():
    db = _DB()
    await close_focus(db, _focus(FOCUS_MAX_DAYS - 1), dict(EXTEND))
    sets = db.coll.updates[0][1]["$set"]
    assert "status" not in sets, "a focus inside the box must not be closed"
    assert "locked_until" in sets


@pytest.mark.asyncio
async def test_past_the_box_it_ends_even_when_stuck():
    db = _DB()
    await close_focus(db, _focus(FOCUS_MAX_DAYS + 1), dict(EXTEND))
    sets = db.coll.updates[0][1]["$set"]
    assert sets["status"] == "completed"
    assert sets["resolution"] == "time_boxed"
    assert sets["next_action"] == "repick"
    assert "locked_until" not in sets, "a closed focus must not be extended too"


@pytest.mark.asyncio
async def test_no_data_and_pending_are_boxed_too():
    """These are 74% of all checks between them. If the box only caught
    "stuck" it would miss three quarters of the jam."""
    for resolution in ("no_data", "measurement_pending"):
        db = _DB()
        await close_focus(db, _focus(FOCUS_MAX_DAYS + 5),
                          {"resolution": resolution, "action": "extend",
                           "delta_pct": None, "current_metric": None})
        assert db.coll.updates[0][1]["$set"]["status"] == "completed", resolution


@pytest.mark.asyncio
async def test_time_boxed_is_not_reported_as_improved():
    """It says we stopped working on this, NOT that the player fixed it.
    Collapsing the two would turn every quiet stall into a fake success."""
    db = _DB()
    await close_focus(db, _focus(FOCUS_MAX_DAYS + 2), dict(EXTEND))
    sets = db.coll.updates[0][1]["$set"]
    assert sets["resolution"] != "improved"
    assert sets["resolution"] == "time_boxed"


@pytest.mark.asyncio
async def test_a_real_success_still_closes_on_its_own_terms():
    db = _DB()
    await close_focus(db, _focus(3), {"resolution": "improved",
                                      "action": "celebrate", "delta_pct": -40.0,
                                      "current_metric": {"value": 0.5}})
    sets = db.coll.updates[0][1]["$set"]
    assert sets["status"] == "completed"
    assert sets["resolution"] == "improved"


@pytest.mark.asyncio
async def test_a_focus_with_no_start_date_is_not_boxed_by_accident():
    """No started_at means no age, and guessing one would close focuses at
    random. It keeps extending, which is the safe direction."""
    db = _DB()
    row = _focus(99)
    row["started_at"] = None
    await close_focus(db, row, dict(EXTEND))
    assert "status" not in db.coll.updates[0][1]["$set"]


@pytest.mark.asyncio
async def test_an_iso_string_start_date_is_understood():
    """Older rows store started_at as a string, not a BSON datetime."""
    db = _DB()
    row = _focus(FOCUS_MAX_DAYS + 3)
    row["started_at"] = row["started_at"].isoformat()
    row["cycle_version"] = None
    await close_focus(db, row, dict(EXTEND))
    assert db.coll.updates[0][1]["$set"]["status"] == "completed"
