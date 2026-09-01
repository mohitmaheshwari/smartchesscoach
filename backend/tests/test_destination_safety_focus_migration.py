from datetime import datetime

import pytest

from scripts.migrate_destination_safety_focus import (
    FOCUS_KIND,
    INSTRUCTION,
    _eligible_update,
)


class _Rows:
    def __init__(self, rows):
        self.rows = rows

    async def to_list(self, length=None):
        return list(self.rows)


class _Games:
    async def count_documents(self, _query):
        return 12


class _Observations:
    def __init__(self, fires):
        self.fires = fires

    async def count_documents(self, _query):
        return self.fires

    def aggregate(self, _pipeline):
        return _Rows([{"decisions": 10, "misses": 4}])


class _DB:
    def __init__(self, fires):
        self.games = _Games()
        self.move_observations = _Observations(fires)


FOCUS = {
    "_id": "focus-1",
    "user_id": "u1",
    "topic_key": "piece_safety",
    "detector_quality_id": "gap:piece_safety:simple_hang",
}


@pytest.mark.asyncio
async def test_migration_builds_exact_plan_focus_from_eligible_evidence():
    candidate = await _eligible_update(_DB(fires=4), FOCUS)
    assert candidate["eligible"] is True
    update = candidate["update"]
    assert update["focus_kind"] == FOCUS_KIND
    assert update["detector_quality_id"] == (
        "gap:piece_safety:destination_safety_exact"
    )
    assert update["detector_quality_grade"] == "plan"
    assert update["instruction_text"] == INSTRUCTION
    assert update["instruction_version"] == 2
    assert update["baseline_metric"]["value"] == 0.333
    assert update["review_after_measured_games"] == 3
    assert update["calendar_backstop_days"] == 21
    assert isinstance(update["started_at"], datetime)
    assert isinstance(update["locked_until"], datetime)


@pytest.mark.asyncio
async def test_migration_refuses_below_locked_recurrence_floor():
    candidate = await _eligible_update(_DB(fires=2), FOCUS)
    assert candidate["eligible"] is False
    assert "update" not in candidate


@pytest.mark.asyncio
async def test_migration_is_idempotent_and_never_restarts_exact_focus():
    exact_focus = {
        **FOCUS,
        "focus_kind": FOCUS_KIND,
        "detector_quality_id": "gap:piece_safety:destination_safety_exact",
    }
    candidate = await _eligible_update(_DB(fires=99), exact_focus)
    assert candidate["eligible"] is False
    assert candidate["reason"] == "already_migrated"
    assert "update" not in candidate
