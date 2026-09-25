from __future__ import annotations

from datetime import datetime, timezone

import pytest

from services.pattern_progress_aggregator import get_user_pattern_progress


@pytest.fixture(autouse=True)
def strict_tracker_rollout(monkeypatch):
    monkeypatch.setenv("DETECTOR_QUALITY_GATE_ENFORCED", "true")

class _AggregateCollection:
    def __init__(self):
        self.pipeline = None

    def aggregate(self, pipeline):
        self.pipeline = pipeline

        async def rows():
            yield {
                "_id": "TAC_FORK_PATTERN",
                "hit_count": 2,
                "miss_count": 1,
                "first_seen_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
                "last_seen_at": datetime(2026, 1, 2, tzinfo=timezone.utc),
                "distinct_games": ["g1", "g2"],
                "game_events": [
                    {"game_id": "g2", "created_at": datetime(2026, 1, 2, tzinfo=timezone.utc)},
                    {"game_id": "g1", "created_at": datetime(2026, 1, 1, tzinfo=timezone.utc)},
                ],
            }

        return rows()


class _Db:
    def __init__(self):
        self.user_pattern_events = _AggregateCollection()


@pytest.mark.asyncio
async def test_progress_reads_only_authorized_events_and_groups_canonical_id():
    db = _Db()
    result = await get_user_pattern_progress(db, "u1")
    match = db.user_pattern_events.pipeline[0]["$match"]
    group_id = db.user_pattern_events.pipeline[1]["$group"]["_id"]
    assert match["user_id"] == "u1"
    assert match["tracker_eligible"] is True
    assert match["proof.authority"] == "verified_caption_principle"
    assert "gap:piece_safety:simple_hang" in match["proof.quality_id"]["$in"]
    assert group_id == {"$ifNull": ["$concept_id", "$pattern_id"]}
    assert result["patterns"][0]["pattern_id"] == "TAC_FORK_PATTERN"
    assert result["patterns"][0]["concept_id"] == "TAC_FORK_PATTERN"
    assert result["patterns"][0]["accuracy_pct"] == 67

@pytest.mark.asyncio
async def test_rollout_off_preserves_legacy_pattern_aggregation(monkeypatch):
    monkeypatch.setenv("DETECTOR_QUALITY_GATE_ENFORCED", "false")
    db = _Db()
    await get_user_pattern_progress(db, "u1")
    assert db.user_pattern_events.pipeline[0]["$match"] == {"user_id": "u1"}
    assert db.user_pattern_events.pipeline[1]["$group"]["_id"] == "$pattern_id"
