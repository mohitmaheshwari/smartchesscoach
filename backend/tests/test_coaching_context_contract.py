"""Contract tests for the default-off canonical coaching context."""

import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.focus_bridge import (
    build_coaching_context,
    coaching_context_visible_in_mode,
    coaching_session_payload_for_mode,
    validate_coaching_context,
)


class _Collection:
    def __init__(self, doc=None):
        self.doc = doc

    async def find_one(self, query, projection=None):
        return dict(self.doc) if self.doc else None


class _Cursor:
    def __init__(self, rows):
        self.rows = list(rows)

    async def to_list(self, length=None):
        return list(self.rows if length is None else self.rows[:length])


class _Observations:
    def __init__(self, rows=None):
        self.rows = list(rows or [])
        self.queries = []

    def find(self, query, projection=None):
        self.queries.append((query, projection))
        return _Cursor(self.rows)


class _DB:
    def __init__(self, focus=None, role="admin", observations=None):
        self.user_active_focus = _Collection(focus)
        self.users = _Collection({"role": role})
        self.move_observations = _Observations(observations)

    def __getitem__(self, name):
        return getattr(self, name)


PRIMARY = {
    "_id": "focus-1",
    "user_id": "u1",
    "type": "weakness",
    "status": "active",
    "topic_key": "piece_safety",
    "coaching_label": "Keeping your pieces safe",
    "coaching_narrative": "Your loose pieces are costing you games.",
    "detector_quality_id": "gap:piece_safety:simple_hang",
    "instruction_id": "instruction-1",
    "instruction_text": "Before every move, ask: can this piece be taken?",
    "instruction_version": 1,
    "runners_up": [],
}


@pytest.fixture(autouse=True)
def _flags(monkeypatch):
    monkeypatch.delenv("COACHING_CONTEXT_V1_ENABLED", raising=False)
    monkeypatch.delenv("PERSONAL_IMPROVEMENT_CYCLE_ENABLED", raising=False)
    monkeypatch.setenv("PWC_SURVIVING_INSTRUCTION_ENABLED", "true")
    # These tests exercise the cross-surface contract after a detector has
    # been promoted. Production simple_hang is deliberately Shadow now, so
    # grant only this synthetic fixture Plan authority inside this test file.
    import services.detector_quality as quality
    real_is_authorized = quality.is_authorized
    real_can_influence = quality.can_influence
    test_quality_id = "gap:piece_safety:simple_hang"
    monkeypatch.setattr(
        quality,
        "is_authorized",
        lambda quality_id, surface: (
            True if quality_id == test_quality_id
            else real_is_authorized(quality_id, surface)
        ),
    )
    monkeypatch.setattr(
        quality,
        "can_influence",
        lambda quality_id, surface: (
            True if quality_id == test_quality_id
            else real_can_influence(quality_id, surface)
        ),
    )


def _run(awaitable):
    return asyncio.run(awaitable)


def test_flag_off_is_none_and_does_not_touch_db():
    assert _run(build_coaching_context(None, "u1", surface="home")) is None


def test_no_focus_is_explicit_and_never_uses_a_rival_fallback(monkeypatch):
    monkeypatch.setenv("COACHING_CONTEXT_V1_ENABLED", "true")
    context = _run(build_coaching_context(_DB(), "u1", surface="home"))

    assert validate_coaching_context(context) == context
    assert context["schema_version"] == "coaching_context.v1"
    assert context["state"] == "no_focus"
    assert context["primary_focus"] is None
    assert context["supporting_focuses"] == []
    assert context["evidence"]["verdict"] == "insufficient_evidence"
    assert context["rollout"] == {"eligible": True, "reason": "enabled"}


def test_context_flag_alone_can_read_the_stored_instruction(monkeypatch):
    monkeypatch.setenv("COACHING_CONTEXT_V1_ENABLED", "true")
    monkeypatch.delenv("PWC_SURVIVING_INSTRUCTION_ENABLED", raising=False)
    monkeypatch.delenv("PERSONAL_IMPROVEMENT_CYCLE_ENABLED", raising=False)

    context = _run(
        build_coaching_context(_DB(PRIMARY), "u1", surface="home")
    )

    assert context["state"] == "primary_only"
    assert context["primary_focus"]["instruction_id"] == "instruction-1"
    assert context["primary_focus"]["instruction_text"] == PRIMARY["instruction_text"]


def test_flag_on_still_preserves_legacy_path_for_ineligible_role(monkeypatch):
    monkeypatch.setenv("COACHING_CONTEXT_V1_ENABLED", "true")

    context = _run(
        build_coaching_context(_DB(PRIMARY, role="user"), "u1", surface="home")
    )

    assert context is None


def test_authorized_primary_is_identical_on_all_core_surfaces(monkeypatch):
    monkeypatch.setenv("COACHING_CONTEXT_V1_ENABLED", "true")
    db = _DB(PRIMARY)

    contexts = [
        _run(build_coaching_context(db, "u1", surface=surface))
        for surface in ("home", "review", "training", "coach_play")
    ]

    identities = {
        (
            item["primary_focus"]["focus_id"],
            item["primary_focus"]["instruction_id"],
            item["primary_focus"]["instruction_text"],
        )
        for item in contexts
    }
    assert identities == {
        (
            "focus-1",
            "instruction-1",
            "Before every move, ask: can this piece be taken?",
        )
    }
    assert {item["surface"] for item in contexts} == {
        "home", "review", "training", "coach_play"
    }


def test_support_is_strictly_authorized_and_capped_at_one(monkeypatch):
    monkeypatch.setenv("COACHING_CONTEXT_V1_ENABLED", "true")
    focus = dict(PRIMARY)
    focus["runners_up"] = [
        {
            "topic": "king_safety",
            "coaching_label": "King safety",
            "detector_quality_id": "gap:king_safety:king_in_center",
            "evidence_count": 9,
        },
        {
            "topic": "time_management",
            "coaching_label": "Using your clock",
            "detector_quality_id": "gap:time_management:impulsive_critical",
            "evidence_count": 8,
        },
    ]

    import services.detector_quality as quality
    real_is_authorized = quality.is_authorized
    monkeypatch.setattr(
        quality,
        "is_authorized",
        lambda quality_id, surface: (
            quality_id == "gap:king_safety:king_in_center"
            or real_is_authorized(quality_id, surface)
        ),
    )

    context = _run(build_coaching_context(_DB(focus), "u1", surface="review"))

    assert context["state"] == "primary_with_support"
    assert context["supporting_focuses"] == [
        {
            "topic_key": "king_safety",
            "label": "King safety",
            "detector_quality_id": "gap:king_safety:king_in_center",
            "evidence_count": 9,
        }
    ]


def test_unknown_primary_fails_closed_even_when_global_quality_gate_is_off(monkeypatch):
    monkeypatch.setenv("COACHING_CONTEXT_V1_ENABLED", "true")
    focus = dict(PRIMARY, detector_quality_id="gap:piece_safety:unreviewed")

    context = _run(build_coaching_context(_DB(focus), "u1", surface="home"))

    assert context["state"] == "no_focus"
    assert context["primary_focus"] is None
    # The lower-level focus reader already removes unauthorized documents, so
    # this layer sees the same safe shape as a user with no active focus.
    assert context["rollout"]["reason"] == "enabled"


def test_missing_instruction_is_evidence_pending_not_invented(monkeypatch):
    monkeypatch.setenv("COACHING_CONTEXT_V1_ENABLED", "true")
    focus = dict(PRIMARY)
    focus.pop("instruction_id")
    focus.pop("instruction_text")

    context = _run(build_coaching_context(_DB(focus), "u1", surface="training"))

    assert context["state"] == "evidence_pending"
    assert context["primary_focus"]["instruction_id"] is None
    assert context["next_action"]["type"] == "review"
    assert "verified instruction" in context["evidence"]["message"].lower()


def test_review_adapter_includes_only_exact_plan_authorized_focus_moves(monkeypatch):
    monkeypatch.setenv("COACHING_CONTEXT_V1_ENABLED", "true")
    observations = [
        {
            "game_id": "g1",
            "move_number": 12,
            "move_san": "Qd5",
            "missed_pattern": "piece_safety",
            "subtype": "simple_hang",
            "severity": "blunder",
        },
        {
            "game_id": "g1",
            "move_number": 19,
            "move_san": "Ra2",
            "missed_pattern": "piece_safety",
            "subtype": "generic_oversight",
            "severity": "mistake",
        },
    ]

    db = _DB(PRIMARY, observations=observations)
    context = _run(
        build_coaching_context(
            db,
            "u1",
            surface="review",
            game_id="g1",
        )
    )

    review = context["surface_context"]
    assert review["game_id"] == "g1"
    assert review["focus_evidence_state"] == "observed"
    assert review["primary_matches"] == [
        {
            "move_number": 12,
            "move_san": "Qd5",
            "severity": "blunder",
            "topic_key": "piece_safety",
            "subtype": "simple_hang",
            "detector_quality_id": "gap:piece_safety:simple_hang",
        }
    ]
    assert review["supporting_matches"] == []
    query, _ = db.move_observations.queries[0]
    assert query == {"user_id": "u1", "game_id": "g1"}
    assert "fixed" not in review["message"].lower()


def test_review_no_match_explicitly_says_it_is_not_proof_of_improvement(monkeypatch):
    monkeypatch.setenv("COACHING_CONTEXT_V1_ENABLED", "true")

    context = _run(
        build_coaching_context(
            _DB(PRIMARY, observations=[]),
            "u1",
            surface="review",
            game_id="g2",
        )
    )

    review = context["surface_context"]
    assert review["focus_evidence_state"] == "not_observed"
    assert review["primary_matches"] == []
    assert "does not mean the problem is fixed" in review["message"].lower()


def test_training_adapter_carries_one_exact_assignment(monkeypatch):
    monkeypatch.setenv("COACHING_CONTEXT_V1_ENABLED", "true")

    context = _run(
        build_coaching_context(_DB(PRIMARY), "u1", surface="training")
    )

    assignment = context["surface_context"]["assignment"]
    assert assignment == {
        "type": "focus_practice",
        "focus_id": "focus-1",
        "instruction_id": "instruction-1",
        "instruction_text": "Before every move, ask: can this piece be taken?",
        "href": "/training/pattern/piece_safety",
        "label": "Practise this check",
    }


def test_validator_rejects_more_than_one_support():
    invalid = {
        "schema_version": "coaching_context.v1",
        "context_id": "ccv1:f:i:1",
        "surface": "home",
        "state": "primary_with_support",
        "primary_focus": {"focus_id": "f"},
        "supporting_focuses": [{"topic_key": "a"}, {"topic_key": "b"}],
        "elective": None,
        "evidence": {"eligibility": "verified", "verdict": "measurement_pending"},
        "learner_projection": None,
        "next_action": {"type": "practice", "href": "/training", "label": "Practise"},
        "rollout": {"eligible": True, "reason": "enabled"},
        "surface_context": None,
    }

    with pytest.raises(ValueError, match="at most one"):
        validate_coaching_context(invalid)


def test_coach_mode_shows_context_but_play_mode_keeps_live_play_clean():
    context = {"schema_version": "coaching_context.v1", "context_id": "ctx-1"}

    assert coaching_context_visible_in_mode(context, "coach") is context
    assert coaching_context_visible_in_mode(context, "play") is None


def test_play_mode_browser_session_hides_snapshots_but_keeps_stored_input_unchanged():
    stored = {
        "session_id": "s1",
        "coaching_context": {"context_id": "ctx-1"},
        "mission_scoreboard": {"instruction_id": "instruction-1"},
        "session_focus": {"topic_key": "piece_safety"},
        "session_goal": {"text": "check the piece"},
        "session_greeting": {"text": "same focus"},
    }

    visible = coaching_session_payload_for_mode(stored, "play")

    assert visible["session_id"] == "s1"
    assert all(
        visible[field] is None
        for field in (
            "coaching_context",
            "mission_scoreboard",
            "session_focus",
            "session_goal",
            "session_greeting",
        )
    )
    assert stored["coaching_context"] == {"context_id": "ctx-1"}
