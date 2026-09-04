"""Phase 4 shadow learner-evidence loop tests."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import importlib.util
import inspect
import json
from pathlib import Path

import pytest

from services.concept_mastery_service import reduce_review_learning_shadow
from services.personal_curriculum import (
    ApplicationOutcome,
    AttemptKind,
    ContractViolation,
    LessonResult,
    PIC_CANONICAL_SOURCE,
    PIC_CONTENT_ID,
    PIC_CONTENT_KIND,
    StudentState,
)
from services.review_learning_adapter import (
    application_results_from_observations,
    build_shadow_learning_event,
    lesson_result_from_guided_pic_practice,
    lesson_result_from_review_reflection,
    store_shadow_lesson_results,
    store_shadow_lesson_results_sync,
)


NOW = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)


def _reflection_document(**event_overrides):
    event = {
        "event_id": "game:17:piece_safety.simple_hang:allowed",
        "concept_id": "piece_safety.simple_hang",
        "content_ref": PIC_CONTENT_ID,
        "canonical_source": PIC_CANONICAL_SOURCE,
        "quality_id": "gap:piece_safety:simple_hang",
        "quality_grade": "plan",
        "outcome": "allowed",
    }
    event.update(event_overrides)
    return {
        "reflection_kind": "game_review_event",
        "event": event,
        "response": {
            "submitted_at": NOW.isoformat(),
            "answered_before_reveal": True,
            "selected_option_id": "not_sure",
        },
    }


def test_review_reflection_proves_learning_only():
    result = lesson_result_from_review_reflection(_reflection_document())
    assert result.attempt_kind == AttemptKind.EXPLANATION
    assert result.earned_state() == StudentState.LEARNING
    assert result.content_id == PIC_CONTENT_ID
    assert result.source_event_id.startswith("game:")


def test_reflection_never_guesses_missing_canonical_content():
    with pytest.raises(ContractViolation, match="canonical content"):
        lesson_result_from_review_reflection(
            _reflection_document(content_ref=None)
        )


def test_reflection_rejects_wrong_canonical_content_or_missing_origin():
    with pytest.raises(ContractViolation, match="unsupported"):
        lesson_result_from_review_reflection(
            _reflection_document(content_ref="endgame.opposition")
        )
    with pytest.raises(ContractViolation, match="source event"):
        lesson_result_from_review_reflection(
            _reflection_document(event_id="")
        )


def test_guided_practice_cannot_receive_independent_credit():
    correct = lesson_result_from_guided_pic_practice(
        session_id="s",
        item_id="p",
        interaction_id="i",
        occurred_at=NOW,
        correct=True,
    )
    wrong = lesson_result_from_guided_pic_practice(
        session_id="s",
        item_id="p",
        interaction_id="j",
        occurred_at=NOW,
        correct=False,
    )
    assert correct.earned_state() == StudentState.CAN_DO_WITH_HELP
    assert wrong.earned_state() == StudentState.LEARNING
    assert correct.distinct_position is False
    assert correct.assistance


def test_application_adapter_accepts_only_current_verified_positive_misses():
    results = application_results_from_observations(
        game_id="g",
        occurred_at=NOW,
        observations=(
            {
                "schema_version": 17,
                "missed_pattern": "piece_safety",
                "subtype": "simple_hang",
                "ply": 17,
            },
            {
                "schema_version": 15,
                "missed_pattern": "piece_safety",
                "subtype": "simple_hang",
                "ply": 19,
            },
            {
                "schema_version": 17,
                "missed_pattern": "piece_safety",
                "subtype": "threat_ignored",
                "ply": 21,
            },
            {
                "schema_version": 17,
                "piece_safety_decision": {
                    "eligible": True,
                    "outcome": "handled",
                },
                "ply": 23,
            },
        ),
    )
    assert len(results) == 1
    assert results[0].application_outcome == ApplicationOutcome.MISSED
    assert results[0].earned_state() is None
    assert results[0].source_event_id == "move_observation:g:17"


def test_shadow_event_is_deterministic_and_visible_ineligible():
    result = lesson_result_from_review_reflection(_reflection_document())
    first = build_shadow_learning_event(result, origin="review")
    second = build_shadow_learning_event(result, origin="review")
    assert first == second
    assert first["evidence_eligible"] is False
    assert first["rollout_mode"] == "shadow"
    assert first["shadow_earned_state"] == "learning"


def test_shadow_event_requires_traceable_source_identity():
    result = LessonResult(
        content_kind=PIC_CONTENT_KIND,
        content_id=PIC_CONTENT_ID,
        canonical_source=PIC_CANONICAL_SOURCE,
        attempt_kind=AttemptKind.EXPLANATION,
        occurred_at=NOW,
    )
    with pytest.raises(ContractViolation, match="source_event_id"):
        build_shadow_learning_event(result, origin="review")


def test_lesson_result_rehydration_rejects_forged_state():
    result = lesson_result_from_review_reflection(_reflection_document())
    payload = result.event_dict()
    assert LessonResult.from_event_dict(payload) == result
    payload["earned_state"] = "used_in_games"
    with pytest.raises(ContractViolation, match="does not match"):
        LessonResult.from_event_dict(payload)


def test_shadow_reducer_uses_existing_lesson_result_states_without_reliable():
    explanation = build_shadow_learning_event(
        lesson_result_from_review_reflection(_reflection_document()),
        origin="review",
    )
    guided = build_shadow_learning_event(
        lesson_result_from_guided_pic_practice(
            session_id="s",
            item_id="p",
            interaction_id="i",
            occurred_at=NOW,
            correct=True,
        ),
        origin="guided",
    )
    independent = build_shadow_learning_event(
        LessonResult(
            content_kind=PIC_CONTENT_KIND,
            content_id=PIC_CONTENT_ID,
            canonical_source=PIC_CANONICAL_SOURCE,
            attempt_kind=AttemptKind.INDEPENDENT,
            occurred_at=NOW,
            correct=True,
            position_id="new-position",
            board_verified=True,
            distinct_position=True,
            source_event_id="independent:new-position",
        ),
        origin="independent",
    )
    projection = reduce_review_learning_shadow(
        (explanation, guided, independent)
    )
    assert projection["state"] == "can_do_alone"
    assert projection["state"] != "reliable"
    assert projection["visible_mastery_changed"] is False


def test_plan_authorized_applied_event_can_reach_used_in_games_in_shadow():
    application = build_shadow_learning_event(
        LessonResult(
            content_kind=PIC_CONTENT_KIND,
            content_id=PIC_CONTENT_ID,
            canonical_source=PIC_CANONICAL_SOURCE,
            attempt_kind=AttemptKind.APPLICATION,
            occurred_at=NOW,
            application_outcome=ApplicationOutcome.APPLIED,
            detector_quality_id="gap:piece_safety:simple_hang",
            source_event_id="application:g:17",
        ),
        origin="external_game",
    )
    projection = reduce_review_learning_shadow((application,))
    assert projection["state"] == "used_in_games"
    assert projection["visible_mastery_changed"] is False


def test_duplicate_source_event_is_counted_once():
    event = build_shadow_learning_event(
        lesson_result_from_review_reflection(_reflection_document()),
        origin="review",
    )
    projection = reduce_review_learning_shadow((event, dict(event)))
    assert projection["evidence"]["accepted_events"] == 1
    assert projection["evidence"]["rejected_events"] == 1


class _AsyncCollection:
    def __init__(self):
        self.calls = []

    async def update_one(self, query, update, upsert=False):
        self.calls.append((query, update, upsert))


class _SyncCollection:
    def __init__(self):
        self.calls = []

    def update_one(self, query, update, upsert=False):
        self.calls.append((query, update, upsert))


def test_async_and_sync_storage_use_one_atomic_pipeline_and_dedupe_batch():
    event = build_shadow_learning_event(
        lesson_result_from_review_reflection(_reflection_document()),
        origin="review",
    )
    async_collection = _AsyncCollection()
    receipt = asyncio.run(
        store_shadow_lesson_results(
            async_collection,
            user_id="u",
            events=(event, dict(event)),
        )
    )
    assert receipt["candidate_events"] == 1
    assert len(async_collection.calls) == 1
    assert isinstance(async_collection.calls[0][1], list)
    assert async_collection.calls[0][2] is True

    sync_collection = _SyncCollection()
    store_shadow_lesson_results_sync(
        sync_collection,
        user_id="u",
        events=(event, dict(event)),
    )
    assert len(sync_collection.calls) == 1
    assert isinstance(sync_collection.calls[0][1], list)


def test_adapter_has_no_detector_engine_llm_or_new_collection_dependency():
    import services.review_learning_adapter as module

    source = inspect.getsource(module).lower()
    forbidden = (
        "import chess",
        "stockfish",
        "pymongo",
        "motor",
        "openai",
        "anthropic",
        "requests",
        "httpx",
    )
    assert all(token not in source for token in forbidden)
    assert "collection.update_one" in source
    assert "create_collection" not in source


def test_all_three_runtime_chokepoints_use_the_shared_adapter():
    root = Path(__file__).parents[2]
    reflection = (root / "backend" / "routes" / "reflect.py").read_text(
        encoding="utf-8"
    )
    teaching = (
        root / "backend" / "services" / "teaching_engine.py"
    ).read_text(encoding="utf-8")
    worker = (root / "backend" / "analysis_worker.py").read_text(
        encoding="utf-8"
    )
    assert "lesson_result_from_review_reflection" in reflection
    assert "lesson_result_from_guided_pic_practice" in teaching
    assert "application_results_from_observations" in worker
    assert "visible_mastery_changed" not in reflection


class _ReadCollection:
    def __init__(self, documents):
        self.documents = documents

    def find(self, query, projection):
        return list(self.documents)


class _ReadDb:
    def __init__(self, sessions, games):
        self.learning_sessions = _ReadCollection(sessions)
        self.games = _ReadCollection(games)


def test_phase4_measurement_is_aggregate_read_only_and_identifier_free():
    root = Path(__file__).parents[2]
    script_path = (
        root
        / "backend"
        / "scripts"
        / "measure_personalized_game_review_phase4.py"
    )
    spec = importlib.util.spec_from_file_location(
        "measure_personalized_game_review_phase4", script_path
    )
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)

    event = build_shadow_learning_event(
        lesson_result_from_review_reflection(_reflection_document()),
        origin="review",
    )
    output = module.build_aggregate_comparison(
        _ReadDb(
            sessions=(
                {
                    "user_id": "private-user-id",
                    "skill_id": "piece_safety_simple_hang",
                    "events": [event],
                },
            ),
            games=(),
        )
    )
    assert output["read_only"] is True
    assert output["database_writes"] == 0
    assert output["rollout"]["visible_mastery_changed"] is False
    assert output["counts"]["accepted_shadow_events"] == 1
    assert "private-user-id" not in json.dumps(output)
