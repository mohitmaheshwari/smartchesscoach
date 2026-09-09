from __future__ import annotations

from datetime import datetime, timezone

import pytest

from services.pattern_progress_aggregator import get_user_pattern_progress


@pytest.fixture(autouse=True)
def strict_tracker_rollout(monkeypatch):
    # MASTERY_STRICT_EVIDENCE, not DETECTOR_QUALITY_GATE_ENFORCED: the latter
    # is already true in production, where the strict match selects nothing.
    # These tests describe the strict path we can switch on, so they switch
    # it on explicitly instead of inheriting a production default.
    monkeypatch.setenv("MASTERY_STRICT_EVIDENCE", "true")

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
    # Derived from the authorization table rather than hardcoded: a gap that
    # gets demoted (simple_hang was) must not leave a green test behind.
    from services.detector_quality import (
        QualitySurface,
        explicit_authorizations,
        is_authorized,
    )

    expected = [
        q for q in explicit_authorizations()
        if is_authorized(q, QualitySurface.MASTERY)
    ]
    assert match["proof.quality_id"]["$in"] == expected
    assert expected, "no MASTERY-grade quality ids: the strict read would be empty"
    assert group_id == {"$ifNull": ["$concept_id", "$pattern_id"]}
    assert result["patterns"][0]["pattern_id"] == "TAC_FORK_PATTERN"
    assert result["patterns"][0]["concept_id"] == "TAC_FORK_PATTERN"
    assert result["patterns"][0]["accuracy_pct"] == 67

@pytest.mark.asyncio
async def test_rollout_off_preserves_legacy_pattern_aggregation(monkeypatch):
    monkeypatch.setenv("MASTERY_STRICT_EVIDENCE", "false")
    db = _Db()
    await get_user_pattern_progress(db, "u1")
    assert db.user_pattern_events.pipeline[0]["$match"] == {"user_id": "u1"}
    assert db.user_pattern_events.pipeline[1]["$group"]["_id"] == "$pattern_id"


@pytest.mark.asyncio
async def test_production_default_is_the_legacy_read(monkeypatch):
    """The default must stay legacy while events carry no proof.

    On 2026-09-09 every one of the 110,224 stored events lacked
    proof.authority, so a strict read returns nothing for all 60 users with
    history. If this test ever fails, the switch was flipped before the
    events were backfilled and the progress page is about to go blank.
    """
    monkeypatch.delenv("MASTERY_STRICT_EVIDENCE", raising=False)
    db = _Db()
    await get_user_pattern_progress(db, "u1")
    assert db.user_pattern_events.pipeline[0]["$match"] == {"user_id": "u1"}
