from __future__ import annotations

import asyncio
import copy
from datetime import datetime, timezone

from services.learning_evidence_ledger import build_shadow_learning_event
from services.personal_curriculum import AttemptKind, LessonResult
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

OPENING_LESSON = {
    "kind": "opening",
    "id": "london_system",
    "canonical_source": "backend/data/opening_curriculum.json",
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


def test_content_ref_joins_exact_canonical_skill_history():
    result = derive_personal_teaching_profile(
        skill_id="london_system",
        canonical_lesson=OPENING_LESSON,
        coach_memory={
            "learning": {
                "skills": [{
                    "skill_id": "opening_london_white",
                    "seen": 3,
                    "wrong": 1,
                }]
            }
        },
    )

    assert result["skill_id"] == "opening_london_white"
    assert result["mode"] == "personalized"
    assert any(
        anchor["type"] == "exact_skill_history"
        for anchor in result["anchors"]
    )


class _ReadOnlyCollection:
    def __init__(self, doc=None):
        self.doc = copy.deepcopy(doc)
        self.write_calls = 0
        self.last_query = None

    async def find_one(self, query, projection=None, **kwargs):
        self.last_query = copy.deepcopy(query)
        return copy.deepcopy(self.doc)

    def find(self, query, projection=None, **kwargs):
        self.last_query = copy.deepcopy(query)
        rows = [] if self.doc is None else [copy.deepcopy(self.doc)]

        class _Cursor:
            def __init__(self, values):
                self.values = iter(values)

            def __aiter__(self):
                return self

            async def __anext__(self):
                try:
                    return next(self.values)
                except StopIteration as exc:
                    raise StopAsyncIteration from exc

        return _Cursor(rows)

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


def test_async_builder_reads_legacy_session_alias_for_canonical_skill(monkeypatch):
    async def no_focus(db, user_id):
        return None

    monkeypatch.setattr(
        "services.focus_bridge.get_active_focus_bundle",
        no_focus,
    )
    db = _DB()
    db.coach_memory = _ReadOnlyCollection({
        "learning": {
            "skills": [{"skill_id": "opening_london_white", "seen": 2}]
        }
    })
    db.learning_sessions = _ReadOnlyCollection(None)

    result = asyncio.run(build_personal_teaching_profile(
        db,
        "u1",
        skill_id="opening_london_white",
        canonical_lesson=OPENING_LESSON,
    ))

    aliases = db.learning_sessions.last_query["skill_id"]["$in"]
    assert "opening_london_white" in aliases
    assert "london_system" in aliases
    assert result["skill_id"] == "opening_london_white"
    assert result["mode"] == "personalized"


def test_async_builder_uses_validated_lesson_result_history(monkeypatch):
    async def no_focus(db, user_id):
        return None

    monkeypatch.setattr(
        "services.focus_bridge.get_active_focus_bundle",
        no_focus,
    )
    db = _DB()
    db.coach_memory = _ReadOnlyCollection({
        "learning": {
            "skills": [{"skill_id": "piece_safety", "seen": 9, "wrong": 4}]
        }
    })
    result_event = build_shadow_learning_event(
        LessonResult(
            content_kind="concept",
            content_id="piece_safety",
            canonical_source="backend/data/theory/tactical_patterns.json",
            content_version="1",
            skill_id="piece_safety",
            primary_skill_id="piece_safety",
            attempt_kind=AttemptKind.INDEPENDENT,
            occurred_at=datetime(2026, 9, 5, tzinfo=timezone.utc),
            correct=True,
            position_id="fresh-position",
            board_verified=True,
            distinct_position=True,
            source_event_id="transfer-proof",
        ),
        origin="test",
    )
    db.learning_sessions = _ReadOnlyCollection({"events": [result_event]})

    result = asyncio.run(build_personal_teaching_profile(
        db,
        "u1",
        skill_id="piece_safety",
        canonical_lesson=LESSON,
    ))

    assert result["why_now"].startswith(
        "You solved a fresh position without help"
    )
    assert result["next_evidence"] == "real_game_application"
    assert result["anchors"][0]["provenance"]["ref"] == "transfer-proof"
    assert all(
        anchor["type"] != "exact_skill_history"
        for anchor in result["anchors"]
    )
