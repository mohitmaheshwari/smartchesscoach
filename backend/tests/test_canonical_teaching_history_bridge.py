from __future__ import annotations

import asyncio
import copy
from datetime import datetime, timezone

from services.concept_mastery_service import (
    get_learning_shadow_projection,
    reduce_lesson_results_shadow,
)
from services.learning_evidence_ledger import build_shadow_learning_event
from services.personal_curriculum import (
    AssistanceKind,
    AttemptKind,
    EvidenceSourceType,
    HelpAction,
    LessonResult,
)
from services.personal_teaching_profile import derive_personal_teaching_profile


NOW = datetime(2026, 9, 5, 8, 0, tzinfo=timezone.utc)
IDENTITY = (
    "concept",
    "piece_safety",
    "backend/data/theory/tactical_patterns.json",
)
LESSON = {
    "kind": IDENTITY[0],
    "id": IDENTITY[1],
    "canonical_source": IDENTITY[2],
    "content_version": "1",
}


def _result(
    *,
    source_event_id: str,
    attempt_kind: AttemptKind,
    correct: bool | None,
    position_id: str | None = None,
    assistance=(),
    requested_help=(),
    skill_id: str = "piece_safety",
    canonical_source: str = IDENTITY[2],
) -> LessonResult:
    return LessonResult(
        content_kind="concept",
        content_id="piece_safety",
        canonical_source=canonical_source,
        content_version="1",
        skill_id=skill_id,
        primary_skill_id=skill_id,
        attempt_kind=attempt_kind,
        occurred_at=NOW,
        correct=correct,
        position_id=position_id,
        board_verified=bool(position_id),
        distinct_position=attempt_kind == AttemptKind.INDEPENDENT,
        assistance=tuple(assistance),
        requested_help=tuple(requested_help),
        source_type=EvidenceSourceType.LESSON,
        source_event_id=source_event_id,
    )


def test_reducer_summarizes_help_outcomes_and_next_unassisted_evidence():
    guided = build_shadow_learning_event(
        _result(
            source_event_id="guided-1",
            attempt_kind=AttemptKind.GUIDED,
            correct=True,
            position_id="position-1",
            assistance=(AssistanceKind.HINT,),
            requested_help=(HelpAction.SHOW_ON_BOARD,),
        ),
        origin="lesson",
    )

    projection = reduce_lesson_results_shadow(
        [guided],
        skill_id="piece_safety",
        required_content_identity=IDENTITY,
    )

    assert projection["state"] == "can_do_with_help"
    assert projection["next_evidence"] == "unassisted_transfer"
    assert projection["visible_mastery_changed"] is False
    assert projection["evidence"]["by_outcome"] == {"correct": 1}
    assert projection["evidence"]["assistance"] == {
        "assisted": 1,
        "unassisted": 0,
        "unknown": 0,
    }
    assert projection["evidence"]["successful_help"] == "show_on_board"
    assert projection["evidence"]["latest_event"]["ref"] == "guided-1"


def test_unassisted_transfer_requests_real_game_application_not_mastery():
    independent = build_shadow_learning_event(
        _result(
            source_event_id="transfer-1",
            attempt_kind=AttemptKind.INDEPENDENT,
            correct=True,
            position_id="fresh-position",
        ),
        origin="lesson",
    )

    projection = reduce_lesson_results_shadow(
        [independent],
        skill_id="piece_safety",
        required_content_identity=IDENTITY,
    )

    assert projection["state"] == "can_do_alone"
    assert projection["next_evidence"] == "real_game_application"
    assert projection["visible_mastery_changed"] is False
    assert projection["evidence"]["assistance"]["unassisted"] == 1


def test_profile_prefers_validated_history_to_legacy_counter():
    projection = {
        "state": "can_do_with_help",
        "next_evidence": "unassisted_transfer",
        "visible_mastery_changed": False,
        "evidence": {
            "accepted_events": 1,
            "successful_help": "ask_one_question",
            "latest_event": {"ref": "guided-1"},
        },
    }

    result = derive_personal_teaching_profile(
        skill_id="piece_safety",
        canonical_lesson=LESSON,
        learning_projection=projection,
        coach_memory={
            "learning": {
                "skills": [{"skill_id": "piece_safety", "seen": 20, "wrong": 8}]
            }
        },
    )

    assert result["why_now"].startswith(
        "You solved this after one guiding question"
    )
    assert result["schema_version"] == "personal_teaching_profile.v2"
    assert result["first_stage"] == "transfer"
    assert result["next_evidence"] == "unassisted_transfer"
    assert result["delivery"]["preferred_help"] == "ask_one_question"
    assert [anchor["type"] for anchor in result["anchors"]] == [
        "canonical_learning_history"
    ]
    assert result["honesty"]["visible_mastery_changed"] is False


def test_current_answer_still_outranks_older_canonical_history():
    result = derive_personal_teaching_profile(
        skill_id="piece_safety",
        canonical_lesson=LESSON,
        current_interaction={
            "event_id": "answer-now",
            "misconception": "activity_before_safety",
            "requested_help": "let_me_try",
        },
        learning_projection={
            "state": "can_do_alone",
            "next_evidence": "real_game_application",
            "evidence": {
                "accepted_events": 1,
                "latest_event": {"ref": "older-transfer"},
            },
        },
    )

    assert result["anchors"][0]["type"] == "current_misconception"
    assert result["why_now"].startswith("Your last answer shows")
    assert result["first_stage"] == "explain"
    assert result["next_evidence"] == "guided_practice"
    assert result["delivery"]["preferred_help"] == "let_me_try"


class _Cursor:
    def __init__(self, rows):
        self._rows = iter(copy.deepcopy(rows))

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return next(self._rows)
        except StopIteration as exc:
            raise StopAsyncIteration from exc


class _Sessions:
    def __init__(self, rows):
        self.rows = rows
        self.query = None
        self.write_calls = 0

    def find(self, query, projection=None):
        self.query = copy.deepcopy(query)
        return _Cursor(self.rows)

    async def update_one(self, *args, **kwargs):
        self.write_calls += 1
        raise AssertionError("projection must remain read-only")


class _Db:
    def __init__(self, rows):
        self.learning_sessions = _Sessions(rows)


def test_async_projection_joins_aliases_and_rejects_wrong_content_identity():
    alias_event = build_shadow_learning_event(
        _result(
            source_event_id="alias-transfer",
            attempt_kind=AttemptKind.INDEPENDENT,
            correct=True,
            position_id="fresh-position",
            skill_id="piece_safety_simple_hang",
        ),
        origin="lesson",
    )
    wrong_content = build_shadow_learning_event(
        _result(
            source_event_id="wrong-content",
            attempt_kind=AttemptKind.INDEPENDENT,
            correct=True,
            position_id="other-position",
            canonical_source="another/source.json",
        ),
        origin="lesson",
    )
    db = _Db([{"events": [alias_event, wrong_content]}])

    projection = asyncio.run(get_learning_shadow_projection(
        db,
        "user-1",
        skill_id="piece_safety",
        compatible_skill_ids=("piece_safety_simple_hang",),
        required_content_identity=IDENTITY,
    ))

    assert db.learning_sessions.query == {
        "user_id": "user-1",
        "skill_id": {
            "$in": ["piece_safety", "piece_safety_simple_hang"]
        },
    }
    assert projection["state"] == "can_do_alone"
    assert projection["evidence"]["accepted_events"] == 1
    assert projection["evidence"]["rejected_events"] == 1
    assert db.learning_sessions.write_calls == 0
