from __future__ import annotations

import pytest

from services.concept_mastery_tracker import extract_concept_outcomes_from_events
from services.pattern_event_logger import build_event, deduplicate_events, replace_events_for_game


@pytest.fixture(autouse=True)
def strict_tracker_rollout(monkeypatch):
    from services import detector_quality

    # Switches the strict path on for these tests only. Production leaves it
    # off (see test_production_default_is_the_legacy_read), so nothing here
    # should be read as evidence that the strict path is live.
    monkeypatch.setenv("MASTERY_STRICT_EVIDENCE", "true")
    # These tests cover event provenance and dedup, not the authorization
    # table, so authorization is stubbed open to keep them independent of it.
    monkeypatch.setattr(detector_quality, "is_authorized", lambda *args, **kwargs: True)


BASE = {
    "user_id": "u1",
    "game_id": "g1",
    "move_number": 12,
    "move_san": "Qd5",
    "best_move_san": "Qd5",
    "cp_loss": 0,
    "fen_before": "4k3/8/8/8/8/8/8/4K2Q w - - 0 1",
    "detector_versions": {"v5_coaching": 103},
}


def verified_event(*, pattern_id="queen_fork", outcome="hit", **overrides):
    kwargs = {
        **BASE,
        "pattern_id": pattern_id,
        "outcome": outcome,
        "tracker_eligible": True,
        "authority": "verified_caption_principle",
        "quality_id": "principle:TAC_FORK_PATTERN",
        "detector_version": "v5_coaching:103",
        "verifier_version": "caption_pipeline.verify_then_ship.v1",
    }
    kwargs.update(overrides)
    return build_event(**kwargs)


def test_legacy_event_resolves_alias_but_is_neutral_by_default():
    event = build_event(pattern_id="queen_fork", outcome="hit", **BASE)
    assert event["pattern_id"] == "queen_fork"
    assert event["concept_id"] == "TAC_FORK_PATTERN"
    assert event["tracker_eligible"] is False
    assert event["proof"]["quality_id"] == "principle:TAC_FORK_PATTERN"
    assert len(event["proof"]["fingerprint"]) == 64
    assert extract_concept_outcomes_from_events([event]) == {}


def test_unknown_event_is_neutral_even_if_caller_marks_it_eligible():
    event = build_event(
        pattern_id="MID_ROOK_OPEN_FILE",
        concept_id="MID_ROOK_OPEN_FILE",
        outcome="unknown",
        tracker_eligible=True,
        **BASE,
    )
    assert event["opportunity"] is True
    assert event["tracker_eligible"] is False
    assert extract_concept_outcomes_from_events([event]) == {}


def test_mastery_ignores_ineligible_and_miss_wins_conflict():
    hit = verified_event()
    blocked_miss = build_event(
        pattern_id="queen_fork",
        outcome="miss",
        tracker_eligible=False,
        **BASE,
    )
    assert extract_concept_outcomes_from_events([hit, blocked_miss]) == {
        "TAC_FORK_PATTERN": "hit"
    }

    eligible_miss = verified_event(outcome="miss")
    assert extract_concept_outcomes_from_events([hit, eligible_miss]) == {
        "TAC_FORK_PATTERN": "miss"
    }


def test_deduplication_uses_canonical_identity_and_miss_precedence():
    hit = verified_event()
    miss = verified_event(
        pattern_id="TAC_FORK_PATTERN",
        concept_id="TAC_FORK_PATTERN",
        outcome="miss",
    )
    deduped = deduplicate_events([hit, miss])
    assert len(deduped) == 1
    assert deduped[0]["outcome"] == "miss"
    assert deduped[0]["proof"]["authority"] == "verified_caption_principle"


def test_deduplication_keeps_verified_event_over_legacy_tie():
    legacy = build_event(pattern_id="queen_fork", outcome="miss", **BASE)
    direct = verified_event(outcome="miss")
    deduped = deduplicate_events([legacy, direct])
    assert len(deduped) == 1
    assert deduped[0]["tracker_eligible"] is True
    assert deduped[0]["proof"]["authority"] == "verified_caption_principle"


class _EventCursor:
    def __init__(self, events):
        self.events = events

    async def to_list(self, length=None):
        return list(self.events)


class _EventCollection:
    def __init__(self, events):
        self.events = events

    def find(self, query, projection):
        return _EventCursor(self.events)


class _ForbiddenAnalysisCollection:
    async def find_one(self, *args, **kwargs):
        raise AssertionError("legacy V5 fallback must not run for explicit neutral events")


class _NeutralEventDb:
    def __init__(self, events):
        self.user_pattern_events = _EventCollection(events)
        self.game_analyses = _ForbiddenAnalysisCollection()


@pytest.mark.asyncio
async def test_explicit_unknown_event_slice_does_not_fall_back_to_v5():
    from services.concept_mastery_tracker import update_user_mastery_for_game

    unknown = build_event(
        pattern_id="MID_ROOK_OPEN_FILE",
        concept_id="MID_ROOK_OPEN_FILE",
        outcome="unknown",
        **BASE,
    )
    summary = await update_user_mastery_for_game(
        _NeutralEventDb([unknown]), "u1", "g1"
    )
    assert summary["neutral_event_count"] == 1
    assert summary["clean_count"] == 0
    assert summary["violated_count"] == 0

@pytest.mark.asyncio
async def test_empty_event_slice_does_not_infer_mastery_from_v5():
    from services.concept_mastery_tracker import update_user_mastery_for_game

    summary = await update_user_mastery_for_game(
        _NeutralEventDb([]), "u1", "g1"
    )
    assert summary["neutral_event_count"] == 0
    assert summary["clean_count"] == 0
    assert summary["violated_count"] == 0


def test_deduplication_never_lets_ineligible_miss_hide_verified_hit():
    hit = verified_event(outcome="hit")
    legacy_miss = build_event(pattern_id="queen_fork", outcome="miss", **BASE)
    deduped = deduplicate_events([hit, legacy_miss])
    assert len(deduped) == 1
    assert deduped[0]["outcome"] == "hit"
    assert deduped[0]["tracker_eligible"] is True


class _WritableEventCollection:
    def __init__(self):
        self.deleted = []
        self.inserted = []

    async def create_index(self, *args, **kwargs):
        return None

    async def delete_many(self, query):
        self.deleted.append(query)

    async def insert_many(self, events, ordered=False):
        self.inserted.extend(events)


class _WritableEventDb:
    def __init__(self):
        self.user_pattern_events = _WritableEventCollection()


@pytest.mark.asyncio
async def test_empty_replacement_clears_stale_game_events():
    db = _WritableEventDb()
    inserted = await replace_events_for_game(db, "u1", "g1", [])
    assert inserted == 0
    assert db.user_pattern_events.deleted == [{"user_id": "u1", "game_id": "g1"}]
    assert db.user_pattern_events.inserted == []

class _NoEventReadCollection:
    def find(self, *args, **kwargs):
        raise AssertionError("strict event ledger must stay off during legacy rollout")


class _LegacyAnalysisCollection:
    async def find_one(self, *args, **kwargs):
        return {"decryption_v5_data": []}


class _EmptyAsyncCursor:
    def __aiter__(self):
        return self

    async def __anext__(self):
        raise StopAsyncIteration


class _EmptyConceptCollection:
    def find(self, *args, **kwargs):
        return _EmptyAsyncCursor()


class _LegacyRolloutDb:
    def __init__(self):
        self.user_pattern_events = _NoEventReadCollection()
        self.game_analyses = _LegacyAnalysisCollection()
        self.user_concept_understanding = _EmptyConceptCollection()


@pytest.mark.asyncio
async def test_rollout_off_preserves_legacy_v5_mastery_path(monkeypatch):
    from services.concept_mastery_tracker import update_user_mastery_for_game

    monkeypatch.setenv("MASTERY_STRICT_EVIDENCE", "false")
    summary = await update_user_mastery_for_game(_LegacyRolloutDb(), "u1", "g1")
    assert summary["neutral_event_count"] == 0
    assert summary["clean_count"] == 0
    assert summary["violated_count"] == 0


def test_current_quality_demotion_makes_event_neutral(monkeypatch):
    from services import detector_quality

    monkeypatch.setattr(detector_quality, "is_authorized", lambda *args, **kwargs: False)
    event = verified_event()
    assert event["tracker_eligible"] is False
    assert extract_concept_outcomes_from_events([event]) == {}


def test_diagnostic_principle_observation_cannot_change_mastery():
    event = verified_event(authority="caption_principle_observation")
    assert extract_concept_outcomes_from_events([event]) == {}
