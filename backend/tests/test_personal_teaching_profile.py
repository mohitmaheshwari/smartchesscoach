from __future__ import annotations

import asyncio
import copy

from services.personal_teaching_profile import (
    build_personal_teaching_profile,
    derive_personal_teaching_profile,
)


LESSON = {
    "kind": "concept",
    "id": "piece_safety",
    "canonical_source": "backend/data/theory/tactical_patterns.json",
    "content_version": "1",
}


def test_sparse_evidence_asks_a_diagnostic_and_invents_no_learner_type():
    result = derive_personal_teaching_profile(
        skill_id="piece_safety",
        canonical_lesson=LESSON,
    )

    assert result["mode"] == "diagnostic_required"
    assert result["first_stage"] == "diagnose"
    assert "do not know yet" in result["why_now"]
    assert result["anchors"] == []
    assert result["honesty"]["permanent_learner_type"] is None


def test_current_misconception_outranks_stale_skill_history():
    result = derive_personal_teaching_profile(
        skill_id="piece_safety",
        canonical_lesson=LESSON,
        current_interaction={
            "event_id": "event-now",
            "misconception": "missed_defender",
        },
        coach_memory={
            "learning": {
                "skills": [{
                    "skill_id": "piece_safety",
                    "seen": 9,
                    "correct": 4,
                    "wrong": 2,
                }]
            }
        },
    )

    assert result["mode"] == "personalized"
    assert result["anchors"][0]["type"] == "current_misconception"
    assert result["anchors"][0]["provenance"] == {
        "owner": "current_learning_interaction",
        "ref": "event-now",
        "strength": "direct",
    }
    assert "missed defender" in result["why_now"]


def test_delivery_can_change_while_canonical_truth_stays_identical():
    first = derive_personal_teaching_profile(
        skill_id="piece_safety",
        canonical_lesson=LESSON,
    )
    second = derive_personal_teaching_profile(
        skill_id="piece_safety",
        canonical_lesson=LESSON,
        active_focus={"focus_id": "f1", "topic_key": "piece_safety"},
    )

    assert first["canonical_lesson"] == second["canonical_lesson"] == LESSON
    assert first["why_now"] != second["why_now"]
    assert second["honesty"]["chess_truth_adapted"] is False


def test_successful_help_is_remembered_per_skill_not_globally():
    result = derive_personal_teaching_profile(
        skill_id="piece_safety",
        canonical_lesson=LESSON,
        coach_memory={
            "learning": {
                "skills": [{
                    "skill_id": "piece_safety",
                    "seen": 1,
                    "evidence": [{
                        "requested_help": "show_on_board",
                        "correct": True,
                    }],
                }]
            }
        },
        player_profile={"learning_style": "visual"},
    )

    assert result["delivery"]["preferred_help"] == "show_on_board"
    assert "learning_style" not in str(result)


class _ReadOnlyCollection:
    def __init__(self, doc=None):
        self.doc = copy.deepcopy(doc)
        self.write_calls = 0

    async def find_one(self, query, projection=None, **kwargs):
        return copy.deepcopy(self.doc)

    async def update_one(self, *args, **kwargs):
        self.write_calls += 1
        raise AssertionError("teaching profile must not write")


class _DB:
    def __init__(self):
        self.coach_memory = _ReadOnlyCollection({
            "learning": {
                "skills": [{"skill_id": "piece_safety", "seen": 2}]
            }
        })
        self.player_profiles = _ReadOnlyCollection({"rating": 1100})
        self.chess_understanding = _ReadOnlyCollection({})
        self.user_opening_progress = _ReadOnlyCollection({})
        self.learning_sessions = _ReadOnlyCollection(None)


def test_async_builder_reads_existing_owners_and_performs_no_writes(monkeypatch):
    async def no_focus(db, user_id):
        return None

    monkeypatch.setattr(
        "services.focus_bridge.get_active_focus_bundle",
        no_focus,
    )
    db = _DB()
    result = asyncio.run(
        build_personal_teaching_profile(
            db,
            "u1",
            skill_id="piece_safety",
            canonical_lesson=LESSON,
        )
    )

    assert result["mode"] == "personalized"
    for collection in (
        db.coach_memory,
        db.player_profiles,
        db.chess_understanding,
        db.user_opening_progress,
        db.learning_sessions,
    ):
        assert collection.write_calls == 0


def test_async_builder_remembers_latest_help_and_misconception_for_this_skill(
    monkeypatch,
):
    async def no_focus(db, user_id):
        return None

    monkeypatch.setattr(
        "services.focus_bridge.get_active_focus_bundle",
        no_focus,
    )
    db = _DB()
    db.learning_sessions = _ReadOnlyCollection({
        "events": [{
            "event_id": "prior-answer",
            "event_type": "answer_submitted",
            "attempt": {
                "correct": True,
                "misconception": "activity_before_safety",
                "reasoning_consistent": False,
                "requested_help": ["show_on_board"],
            },
        }],
    })

    result = asyncio.run(build_personal_teaching_profile(
        db,
        "u1",
        skill_id="piece_safety",
        canonical_lesson=LESSON,
    ))

    assert result["why_now"].startswith(
        "Your last answer shows that you chose activity before checking"
    )
    assert result["delivery"]["preferred_help"] == "show_on_board"
    assert result["anchors"][0]["provenance"]["ref"] == "prior-answer"
