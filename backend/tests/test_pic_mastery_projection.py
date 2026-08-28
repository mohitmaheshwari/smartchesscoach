"""Canonical PIC learner-state reducer tests."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.concept_mastery_service import reduce_pic_mastery


def test_diagnosis_begins_learning_without_claiming_a_checkpoint():
    state = reduce_pic_mastery([], diagnosed=True)
    assert state["label"] == "Learning"
    assert state["current_demonstrated_checkpoint"] == 0
    assert state["highest_demonstrated_checkpoint"] == 0


def test_assisted_verified_practice_only_introduces_skill():
    state = reduce_pic_mastery([
        {"event_type": "lesson_started", "occurred_at": "2026-08-01"},
        {
            "event_type": "answer_submitted",
            "occurred_at": "2026-08-01T00:01:00Z",
            "checkpoint_candidate": 4,
            "result": "correct",
            "evidence_eligible": False,
            "rejection_reason": "assisted_verified_practice",
        },
    ])
    assert state["label"] == "Learning"
    assert state["current_demonstrated_checkpoint"] == 1
    assert state["highest_demonstrated_checkpoint"] == 1
    assert state["evidence"]["rejected_events"] == 1


def test_delayed_recall_promotes_then_can_demote_current_not_highest():
    events = [{
        "event_type": "checkpoint",
        "occurred_at": "2026-08-02",
        "checkpoint": 7,
        "stage": "delayed_recall",
        "result": "passed",
        "evidence_eligible": True,
    }]
    remembered = reduce_pic_mastery(events)
    assert remembered["label"] == "Remembered"
    assert remembered["current_demonstrated_checkpoint"] == 7

    events.append({
        "event_type": "checkpoint",
        "occurred_at": "2026-08-10",
        "checkpoint": 7,
        "stage": "delayed_recall",
        "result": "failed",
        "evidence_eligible": True,
        "demotion_eligible": True,
        "last_redemonstrated_checkpoint": 6,
    })
    refreshed = reduce_pic_mastery(events)
    assert refreshed["label"] == "Learning"
    assert refreshed["refresh_needed"] is True
    assert refreshed["current_demonstrated_checkpoint"] == 6
    assert refreshed["highest_demonstrated_checkpoint"] == 7


def test_game_proof_requires_explicit_eligibility():
    unverified = reduce_pic_mastery([{
        "event_type": "external_game_evidence",
        "checkpoint_candidate": 8,
        "result": "handled",
        "evidence_eligible": False,
    }], diagnosed=True)
    assert unverified["label"] == "Learning"

    proven = reduce_pic_mastery([{
        "event_type": "external_game_evidence",
        "checkpoint_candidate": 8,
        "result": "handled",
        "evidence_eligible": True,
    }])
    assert proven["label"] == "Proven in games"


def test_single_game_miss_never_demotes_without_locked_repeat_rule():
    state = reduce_pic_mastery([
        {
            "event_type": "checkpoint",
            "occurred_at": "2026-08-01",
            "checkpoint": 8,
            "result": "handled",
            "evidence_eligible": True,
        },
        {
            "event_type": "external_game_evidence",
            "occurred_at": "2026-08-02",
            "checkpoint": 8,
            "stage": "external_focus_game",
            "result": "miss",
            "evidence_eligible": True,
            "demotion_eligible": True,
            "proof_rule_locked": False,
            "repeated_verified_misses": False,
        },
    ])
    assert state["label"] == "Proven in games"
    assert state["refresh_needed"] is False
