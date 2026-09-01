from datetime import datetime, timezone

import pytest

from services.primary_weakness_picker import close_focus


class _Collection:
    def __init__(self):
        self.update = None

    async def update_one(self, query, update):
        self.update = (query, update)


class _DB:
    def __init__(self):
        self.collection = _Collection()

    def __getitem__(self, _name):
        return self.collection


@pytest.mark.asyncio
async def test_pic_hold_preserves_bson_time_and_21_day_backstop():
    db = _DB()
    focus = {
        "_id": "focus-1",
        "cycle_version": 1,
        "locked_until": datetime.now(timezone.utc),
        "calendar_backstop_days": 21,
    }
    await close_focus(
        db,
        focus,
        {
            "resolution": "measurement_pending",
            "action": "hold",
            "current_metric": None,
        },
    )
    update = db.collection.update[1]["$set"]
    assert isinstance(update["updated_at"], datetime)
    assert isinstance(update["locked_until"], datetime)
    assert 20 <= (update["locked_until"] - update["updated_at"]).days <= 21


@pytest.mark.asyncio
async def test_legacy_hold_preserves_iso_string_storage():
    db = _DB()
    focus = {"_id": "focus-2", "locked_until": "2026-09-01T00:00:00+00:00"}
    await close_focus(
        db,
        focus,
        {"resolution": "stuck", "action": "extend", "current_metric": None},
    )
    update = db.collection.update[1]["$set"]
    assert isinstance(update["updated_at"], str)
    assert isinstance(update["locked_until"], str)
