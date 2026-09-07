"""Locks for player-accepted reflection evidence.

The correctness gate for this feature is negative: a cause the player did not
describe must never be attributed to them. Most of these tests assert that
nothing is stored.
"""
from datetime import datetime, timezone

import pytest

from quick_tag_registry import (
    PREDICATE_TO_FUNDAMENTAL,
    SELF_REPORTED_STATE_TAGS,
    TAG_DEFINITIONS,
    UNMAPPED_PREDICATES,
    resolve_accepted_cause,
)
from services.accepted_cause_service import (
    SOURCE,
    build_accepted_cause_document,
    store_accepted_cause,
    summarize_accepted_causes,
)


def _reflection(option_id, *, event_id="e1", game_id="g1", reflection_id="grr_x"):
    return {
        "reflection_id": reflection_id,
        "game_id": game_id,
        "event": {"event_id": event_id, "concept_id": "piece_safety.simple_hang",
                  "quality_id": "gap:piece_safety:simple_hang"},
        "response": {"selected_option_id": option_id, "answered_before_reveal": True},
    }


# ---------------------------------------------------------------- vocabulary

def test_every_fundamental_is_a_topic_the_picker_can_actually_write():
    """The map must target the WRITABLE topic universe, not observed data.

    The 7 topic_key values visible in user_active_focus today are a snapshot.
    primary_weakness_picker can write the 11 IMPACT_TABLE_BY_BAND keys plus
    time_management. A map built on the snapshot silently stops matching the
    first time a new topic is picked.
    """
    from services.primary_weakness_picker import IMPACT_TABLE_BY_BAND

    universe = set(IMPACT_TABLE_BY_BAND["intermediate"]) | {"time_management"}
    assert set(PREDICATE_TO_FUNDAMENTAL.values()) <= universe


def test_every_predicate_is_either_mapped_or_explicitly_unmapped():
    """No predicate may be silently forgotten."""
    declared = set()
    for config in TAG_DEFINITIONS.values():
        declared |= {str(p) for p in (config.get("predicates") or [])}
    assert declared == set(PREDICATE_TO_FUNDAMENTAL) | set(UNMAPPED_PREDICATES)


@pytest.mark.parametrize("option_id", ["not_sure", "none_of_these"])
def test_a_non_answer_never_becomes_a_cause(option_id):
    """Declining to answer is not evidence about the player's chess.

    This is the worst failure the feature could have, and it is not
    hypothetical: of the reflections that existed when this was scoped, one in
    three was `not_sure`.
    """
    resolved = resolve_accepted_cause(option_id)
    assert resolved["tier"] == "non_answer"
    assert resolved["fundamental"] is None
    assert build_accepted_cause_document(_reflection(option_id), user_id="u1") is None


def test_predicate_absence_is_not_the_test_for_self_reported_state():
    """Seven tags carry no predicate; two of them are the escape ids.

    Using "has no predicate" as the tier test would file both refusals as
    self-reported causes.
    """
    predicate_less = {
        str(getattr(tag, "value", tag))
        for tag, config in TAG_DEFINITIONS.items()
        if not (config.get("predicates") or [])
    }
    assert len(predicate_less) == 7
    assert SELF_REPORTED_STATE_TAGS < predicate_less
    assert predicate_less - SELF_REPORTED_STATE_TAGS == {"not_sure", "none_of_these"}


@pytest.mark.parametrize("option_id", sorted(SELF_REPORTED_STATE_TAGS))
def test_self_reported_states_are_stored_but_carry_no_fundamental(option_id):
    """Recorded and shown, never measured."""
    document = build_accepted_cause_document(_reflection(option_id), user_id="u1")
    assert document is not None
    assert document["tier"] == "self_reported_state"
    assert document["fundamental"] is None


def test_an_unknown_option_id_misses_safely():
    """selected_option_id is validated only for membership in the shown list,
    never as a real QuickTagId, so a stale client can send anything."""
    assert resolve_accepted_cause("not_a_real_tag_id") is None
    assert resolve_accepted_cause("") is None
    assert resolve_accepted_cause(None) is None
    assert build_accepted_cause_document(
        _reflection("not_a_real_tag_id"), user_id="u1"
    ) is None


@pytest.mark.parametrize("option_id", [
    "chose_attack_over_safety",   # user_attacked_instead_of_defending
    "attacked_ignored_threat",
    "chose_activity_over_safety",
    "defended_non_threat",        # user_defended_phantom_threat
    "following_opening",          # is_opening_phase
])
def test_deliberately_unmapped_predicates_produce_nothing(option_id):
    """Excluded rather than guessed, and it must stay that way.

    'I attacked and ignored his threat' says the player SAW the threat.
    Filing it under threat_awareness would assert they missed what they just
    told us they noticed.
    """
    assert resolve_accepted_cause(option_id) is None
    assert build_accepted_cause_document(_reflection(option_id), user_id="u1") is None


def test_the_canonical_mapping_holds():
    resolved = resolve_accepted_cause("thought_piece_safe")
    assert resolved["fundamental"] == "piece_safety"
    assert resolved["predicate"] == "user_piece_left_hanging"
    assert resolved["tier"] == "board_anchored"


# ---------------------------------------------------------------- document

def test_document_carries_provenance_and_everything_needed_to_measure_later():
    document = build_accepted_cause_document(
        _reflection("thought_piece_safe"),
        user_id="u1",
        now=datetime(2026, 9, 6, tzinfo=timezone.utc),
    )
    assert document["source"] == SOURCE == "player_accepted"
    assert document["fundamental"] == "piece_safety"
    for field in ("reflection_id", "event_id", "game_id", "selected_option_id",
                  "tier", "predicate", "answered_before_reveal"):
        assert document[field] not in (None, "")


def test_a_reflection_missing_its_identity_stores_nothing():
    broken = _reflection("thought_piece_safe")
    broken["event"]["event_id"] = ""
    assert build_accepted_cause_document(broken, user_id="u1") is None
    assert build_accepted_cause_document(
        _reflection("thought_piece_safe"), user_id=""
    ) is None


# ---------------------------------------------------------------- idempotency

class _FakeCollection:
    def __init__(self):
        self.calls = []

    async def update_one(self, query, update, upsert=False):
        self.calls.append((query, update, upsert))


@pytest.mark.asyncio
async def test_re_answering_replaces_rather_than_appends():
    """store_event_reflection upserts on reflection_id, so a re-answer
    overwrites the reflection. If the cause appended instead, a player
    changing their mind -- or any client retry -- would inflate their own
    weakness model."""
    collection = _FakeCollection()
    first = build_accepted_cause_document(_reflection("thought_piece_safe"), user_id="u1")
    second = build_accepted_cause_document(_reflection("missed_check"), user_id="u1")
    await store_accepted_cause(collection, first)
    await store_accepted_cause(collection, second)
    assert len(collection.calls) == 2
    keys = {call[0]["reflection_id"] for call in collection.calls}
    assert keys == {"grr_x"}, "both writes must target the same key"
    assert all(call[2] is True for call in collection.calls), "must upsert"


# ---------------------------------------------------------------- summary

def test_summary_counts_distinct_games_not_rows():
    """'You told us this twice' should mean two games, not two clicks."""
    docs = [
        {"source": SOURCE, "fundamental": "piece_safety", "game_id": "g1",
         "selected_option_id": "thought_piece_safe"},
        {"source": SOURCE, "fundamental": "piece_safety", "game_id": "g1",
         "selected_option_id": "thought_protected"},
        {"source": SOURCE, "fundamental": "piece_safety", "game_id": "g2",
         "selected_option_id": "thought_piece_safe"},
    ]
    summary = summarize_accepted_causes(docs)
    assert summary["piece_safety"]["accepted_games"] == 2
    assert summary["piece_safety"]["accepted_events"] == 3


def test_summary_ignores_rows_that_are_not_player_accepted():
    assert summarize_accepted_causes(
        [{"source": "detector_inferred", "fundamental": "piece_safety", "game_id": "g1"}]
    ) == {}


def test_summary_skips_self_reported_states():
    """They carry no fundamental and are never grouped as a measurable cause."""
    assert summarize_accepted_causes(
        [{"source": SOURCE, "fundamental": None, "game_id": "g1",
          "selected_option_id": "felt_danger"}]
    ) == {}
