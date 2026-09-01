"""Default-off and evidence-contract tests for the PIC focus projection."""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.focus_bridge import (
    _instruction_fields_eligible,
    _pic_fields_eligible,
    get_pic_focus_projection,
)


class _AsyncRows:
    def __init__(self, rows):
        self.rows = rows

    async def to_list(self, length=None):
        return list(self.rows[:length] if length else self.rows)

    def __aiter__(self):
        self._iterator = iter(self.rows)
        return self

    async def __anext__(self):
        try:
            return next(self._iterator)
        except StopIteration:
            raise StopAsyncIteration


class _ObservationCursor(_AsyncRows):
    def sort(self, *args):
        return self

    def limit(self, length):
        self.rows = self.rows[:length]
        return self


class _Observations:
    def __init__(self, diagnosis_count=2, decisions=6, misses=1):
        self.diagnosis_count = diagnosis_count
        self.decisions = decisions
        self.misses = misses
        self.queries = []

    async def count_documents(self, query):
        self.queries.append(query)
        return self.diagnosis_count

    def find(self, query, projection=None):
        self.queries.append(query)
        return _ObservationCursor([
            {"game_id": "g1", "move_number": 8, "move_san": "Ng5"}
        ])

    def aggregate(self, pipeline):
        self.queries.append(pipeline[0]["$match"])
        return _AsyncRows([
            {"decisions": self.decisions, "misses": self.misses}
        ])


class _Users:
    def __init__(self, role):
        self.role = role

    async def find_one(self, query, projection=None):
        return {"role": self.role}


class _Games:
    def __init__(self, rows=None):
        self.rows = list(rows or [])

    async def distinct(self, field, query):
        return ["g1"]

    def find(self, query, projection=None):
        return _AsyncRows(self.rows)


class _LearningSessions:
    def find(self, query, projection=None):
        return _AsyncRows([])


class _DB:
    def __init__(self, role="admin"):
        self.users = _Users(role)
        self.games = _Games()
        self.learning_sessions = _LearningSessions()
        self.move_observations = _Observations()


FOCUS = {
    "topic_key": "piece_safety",
    "started_at": "2026-08-01T00:00:00+00:00",
    "instruction_id": "inst-1",
    "instruction_text": "Before moving, ask what changed after their move.",
    "proof_eligibility": "verified",
    "evidence_summary": {
        "baseline": {"decisions": 20, "misses": 4, "handled": 16}
    },
}


@pytest.fixture(autouse=True)
def _clean_pic_env(monkeypatch):
    monkeypatch.delenv("PERSONAL_IMPROVEMENT_CYCLE_ENABLED", raising=False)
    monkeypatch.delenv("PERSONAL_IMPROVEMENT_CYCLE_ROLES", raising=False)
    yield


@pytest.mark.asyncio
async def test_flag_off_returns_none_without_touching_db():
    assert await get_pic_focus_projection(None, "u1", focus=FOCUS) is None


@pytest.mark.asyncio
async def test_flag_on_still_fails_closed_for_real_user(monkeypatch):
    monkeypatch.setenv("PERSONAL_IMPROVEMENT_CYCLE_ENABLED", "true")
    assert await get_pic_focus_projection(_DB(role="user"), "u1", focus=FOCUS) is None


@pytest.mark.asyncio
async def test_admin_projection_uses_only_see_backed_and_exact_fact(monkeypatch):
    monkeypatch.setenv("PERSONAL_IMPROVEMENT_CYCLE_ENABLED", "true")
    db = _DB(role="admin")
    projection = await get_pic_focus_projection(db, "u1", focus=FOCUS)

    assert projection["enabled"] is True
    assert projection["eligible"] is True
    assert projection["evidence"]["verdict"] == "measurement_pending"
    assert projection["evidence"]["baseline"]["misses"] == 4
    assert projection["evidence"]["since_focus"] == {
        "decisions": 6,
        "misses": 1,
        "handled": 5,
    }
    assert projection["learner_state"]["label"] == "Learning"
    assert any(q.get("schema_version") == {"$gte": 16} for q in db.move_observations.queries if isinstance(q, dict))
    assert any(q.get("piece_safety_decision.version") == "piece_safety.d_live.v1" for q in db.move_observations.queries if isinstance(q, dict))


@pytest.mark.asyncio
async def test_exact_plan_focus_uses_v18_fact_and_normalized_game_dates(monkeypatch):
    monkeypatch.setenv("PERSONAL_IMPROVEMENT_CYCLE_ENABLED", "true")
    db = _DB(role="admin")
    db.games = _Games([
        {"game_id": "old", "date_played": "2026.07.31"},
        {"game_id": "new", "date_played": "2026.08.02"},
    ])
    focus = {
        **FOCUS,
        "focus_kind": "piece_safety/destination_safety_exact",
        "detector_quality_id": "gap:piece_safety:destination_safety_exact",
    }
    projection = await get_pic_focus_projection(db, "u1", focus=focus)

    assert projection["focus_kind"] == "piece_safety/destination_safety_exact"
    assert projection["diagnosis"]["detector_id"] == (
        "piece_safety.destination_safety_exact.v1"
    )
    assert projection["evidence"]["proof_detector_id"] == (
        "piece_safety.destination_safety_exact.v1"
    )
    exact_queries = [
        query for query in db.move_observations.queries
        if isinstance(query, dict)
        and "destination_safety_exact.version" in query
    ]
    assert exact_queries
    assert all(query["schema_version"] == {"$gte": 18} for query in exact_queries)
    assert any(query.get("game_id") == {"$in": ["new"]} for query in exact_queries)


def test_pic_flag_can_authorize_same_canonical_instruction(monkeypatch):
    monkeypatch.setenv("PERSONAL_IMPROVEMENT_CYCLE_ENABLED", "true")
    assert _pic_fields_eligible("admin") is True
    assert _instruction_fields_eligible("admin") is True
    assert _pic_fields_eligible("user") is False
