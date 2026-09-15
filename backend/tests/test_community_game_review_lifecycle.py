from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

import services.coach_selected_review_service as service
import services.review_learning_adapter as learning_adapter


class Collection:
    def __init__(self, rows=None):
        self.rows = [dict(row) for row in (rows or [])]

    async def find_one(self, query, _projection=None, **_kwargs):
        return next(
            (
                dict(row)
                for row in self.rows
                if all(row.get(key) == value for key, value in query.items())
            ),
            None,
        )

    async def update_one(self, query, update):
        for row in self.rows:
            if not all(row.get(key) == value for key, value in query.items()):
                continue
            for key, value in update.get("$set", {}).items():
                if "." not in key:
                    row[key] = value
                    continue
                parent, child = key.split(".", 1)
                row.setdefault(parent, {})[child] = value
            return SimpleNamespace(modified_count=1)
        return SimpleNamespace(modified_count=0)


class Database:
    def __init__(self, rows):
        self.collections = {
            service.COLLECTION: Collection(rows),
            "users": Collection([
                {"user_id": "learner-1", "role": "admin"},
            ]),
        }

    def __getitem__(self, name):
        return self.collections.setdefault(name, Collection())

    def __getattr__(self, name):
        return self[name]


def _study():
    return {
        "study_id": "study-1",
        "plan": {
            "plan_id": "plan-1",
            "input_fingerprint": "fingerprint-1",
            "chapters": [
                {"event_id": "event-1"},
                {"event_id": "event-2"},
            ],
        },
    }


def _document():
    return {
        "prescription_id": "prescription-1",
        "user_id": "learner-1",
        "game_id": "study-1",
        "study_id": "study-1",
        "source_kind": "community",
        "state": "started",
        "is_active": True,
        "interaction_progress": {},
    }


@pytest.fixture
def community_lifecycle(monkeypatch):
    recorded_reach_events = []

    async def access(*_args, **_kwargs):
        return SimpleNamespace(enabled=True)

    async def load(*_args, **_kwargs):
        return _study()

    async def record_reach(_db, _user_id, **kwargs):
        recorded_reach_events.append(kwargs)
        return True

    monkeypatch.setattr(service, "get_complete_coaching_access", access)
    monkeypatch.setattr(service, "load_admitted_study", load)
    monkeypatch.setattr(service, "record_phase8_reach_event", record_reach)
    monkeypatch.setattr(service, "community_visible_enabled", lambda _env=None: True)
    monkeypatch.setattr(
        service,
        "community_visible_for_operability_role",
        lambda role, _env=None: role in {"admin", "super_admin"},
    )
    db = Database([_document()])
    db.recorded_reach_events = recorded_reach_events
    return db


@pytest.mark.asyncio
async def test_initial_community_study_is_answer_hidden(
    community_lifecycle, monkeypatch
):
    def public(_study_document):
        return {
            "study_id": "study-1",
            "chapters": [
                {
                    "event_id": "event-1",
                    "interaction": {
                        "question": "What danger decides this move?",
                        "options": [
                            {"id": "one", "label": "One"},
                            {"id": "two", "label": "Two"},
                        ],
                        "hint_available": True,
                    },
                }
            ],
        }

    monkeypatch.setattr(service, "project_visible_study", public)
    result = await service.get_community_study(
        community_lifecycle, "learner-1", "prescription-1"
    )
    serialized = repr(result)
    assert "correct_option_id" not in serialized
    assert "demonstration" not in serialized
    assert "explanation" not in serialized
    assert "hint" not in result["chapters"][0]["interaction"]
    assert result["chapters"][0]["interaction"]["hint_available"] is True
    assert result["progress"] == {}
    assert result["hints"] == {}
    assert result["reveals"] == {}


@pytest.mark.asyncio
async def test_server_owns_hint_prediction_watch_and_verified_replay(
    community_lifecycle, monkeypatch
):
    def reveal(_study_document, *, event_id, selected_option_id=None, include_hint=False):
        if include_hint:
            return {"event_id": event_id, "hint": "Follow the knight to d5."}
        return {
            "event_id": event_id,
            "selected_option_id": selected_option_id,
            "correct_option_id": "safe",
            "correct": selected_option_id == "safe",
            "headline": "The queen is left unprotected",
            "explanation": "The knight can take it.",
            "principle": "Check every capture.",
            "demonstration": {
                "kind": "played_refutation",
                "moves_san": ["Bg5", "Nxd5"],
            },
        }

    def replay(_study_document, *, event_id, played_move_uci):
        if played_move_uci != "c1g5":
            raise service.CommunityGameStudyError(
                "replay the key move from the shown line"
            )
        return {
            "event_id": event_id,
            "correct": True,
            "played_move_uci": played_move_uci,
            "expected_move_san": "Bg5",
        }

    monkeypatch.setattr(service, "reveal_study_chapter", reveal)
    monkeypatch.setattr(service, "verify_guided_replay_move", replay)
    db = community_lifecycle

    with pytest.raises(service.ReviewPrescriptionError, match="predict"):
        await service.record_community_chapter_action(
            db, "learner-1", "prescription-1",
            event_id="event-1", action="watch",
        )

    hint = await service.record_community_chapter_action(
        db, "learner-1", "prescription-1",
        event_id="event-1", action="hint",
    )
    assert hint["hint"] == "Follow the knight to d5."
    assert "correct_option_id" not in hint

    reveal_result = await service.record_community_chapter_action(
        db, "learner-1", "prescription-1",
        event_id="event-1", action="predict", selected_option_id="unsafe",
    )
    assert reveal_result["correct"] is False
    assert reveal_result["demonstration"]["moves_san"] == ["Bg5", "Nxd5"]

    second_prediction = await service.record_community_chapter_action(
        db, "learner-1", "prescription-1",
        event_id="event-1", action="predict", selected_option_id="safe",
    )
    assert second_prediction["selected_option_id"] == "unsafe"
    assert second_prediction["correct"] is False

    await service.record_community_chapter_action(
        db, "learner-1", "prescription-1",
        event_id="event-1", action="watch",
    )
    with pytest.raises(service.ReviewPrescriptionError, match="key move"):
        await service.record_community_chapter_action(
            db, "learner-1", "prescription-1",
            event_id="event-1", action="replay", played_move_uci="c1e3",
        )

    replayed = await service.record_community_chapter_action(
        db, "learner-1", "prescription-1",
        event_id="event-1", action="replay", played_move_uci="c1g5",
    )
    assert replayed["progress"]["replayed"] is True
    stored = db[service.COLLECTION].rows[0]["interaction_progress"]
    chapter_state = next(iter(stored.values()))
    assert chapter_state["replayed_move_uci"] == "c1g5"
    assert chapter_state["selected_option_id"] == "unsafe"
    assert chapter_state["correct"] is False
    assert {
        event["step"] for event in db.recorded_reach_events
    } == {
        "community_review_hint_used",
        "community_review_predicted",
        "community_review_revealed",
        "community_review_line_watched",
        "community_review_key_move_replayed",
    }


@pytest.mark.asyncio
async def test_completion_requires_every_chapter_then_rotates(
    community_lifecycle, monkeypatch
):
    db = community_lifecycle
    first_key = service.hashlib.sha256(b"event-1").hexdigest()[:20]
    second_key = service.hashlib.sha256(b"event-2").hexdigest()[:20]
    complete_state = {
        "predicted": True,
        "revealed": True,
        "watched": True,
        "replayed": True,
    }
    db[service.COLLECTION].rows[0]["interaction_progress"] = {
        first_key: dict(complete_state)
    }

    with pytest.raises(service.ReviewPrescriptionError, match="finish each"):
        await service.complete_prescription(
            db, "learner-1", "prescription-1", game_id="study-1"
        )

    db[service.COLLECTION].rows[0]["interaction_progress"][second_key] = dict(
        complete_state
    )

    async def next_recommendation(*_args, **_kwargs):
        return {
            "status": "empty",
            "prescription": None,
            "empty": {
                "primary_action": {
                    "label": "Play with Coach",
                    "href": "/play-with-coach",
                }
            },
        }

    async def record_learning(*_args, **_kwargs):
        return {
            "assisted_learning_recorded": True,
            "chapter_results": 2,
        }

    monkeypatch.setattr(service, "get_recommendation", next_recommendation)
    monkeypatch.setattr(
        learning_adapter,
        "store_community_walkthrough_results",
        record_learning,
    )
    result = await service.complete_prescription(
        db, "learner-1", "prescription-1", game_id="study-1"
    )
    assert result["status"] == "empty"
    assert db[service.COLLECTION].rows[0]["state"] == "completed"
    assert db[service.COLLECTION].rows[0]["is_active"] is False
    assert result["learning"]["assisted_learning_recorded"] is True
    assert result["learning"]["real_game_application"] == "not_measured"
    assert result["next_action"] == {
        "kind": "coach_action",
        "label": "Play with Coach",
        "href": "/play-with-coach",
    }
    assert db[service.COLLECTION].rows[0]["completion_next_action"] == (
        result["next_action"]
    )
    assert any(
        event["step"] == "community_review_completed"
        for event in db.recorded_reach_events
    )
    assert any(
        event["step"] == "community_review_next_action_linked"
        for event in db.recorded_reach_events
    )

    repeated = await service.complete_prescription(
        db, "learner-1", "prescription-1", game_id="study-1"
    )
    assert repeated["learning"] == result["learning"]
    assert repeated["next_action"] == result["next_action"]


@pytest.mark.asyncio
async def test_start_and_server_authored_next_action_are_recorded(
    community_lifecycle,
    monkeypatch,
):
    db = community_lifecycle
    db[service.COLLECTION].rows[0]["state"] = "recommended"

    async def recommendation(*_args, **_kwargs):
        return {"status": "started", "prescription": {}}

    monkeypatch.setattr(service, "get_recommendation", recommendation)
    await service.start_prescription(
        db, "learner-1", "prescription-1"
    )
    assert any(
        event["step"] == "community_review_started"
        for event in db.recorded_reach_events
    )

    row = db[service.COLLECTION].rows[0]
    row.update({
        "state": "completed",
        "is_active": False,
        "completion_next_action": {
            "kind": "coach_action",
            "label": "Play with Coach",
            "href": "/play-with-coach",
        },
    })
    action = await service.follow_community_next_action(
        db, "learner-1", "prescription-1"
    )
    assert action == {
        "kind": "coach_action",
        "label": "Play with Coach",
        "href": "/play-with-coach",
    }
    assert any(
        event["step"] == "community_review_next_action_followed"
        for event in db.recorded_reach_events
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "href",
    (
        "https://evil.example/path",
        "//evil.example/path",
        "/admin",
        "/homepage",
        "/games-outside",
    ),
)
async def test_follow_next_action_rejects_untrusted_routes(
    community_lifecycle,
    href,
):
    row = community_lifecycle[service.COLLECTION].rows[0]
    row.update({
        "state": "completed",
        "is_active": False,
        "completion_next_action": {
            "kind": "coach_action",
            "label": "Leave ChessGuru",
            "href": href,
        },
    })
    with pytest.raises(service.ReviewPrescriptionError, match="no linked"):
        await service.follow_community_next_action(
            community_lifecycle, "learner-1", "prescription-1"
        )
    assert not any(
        event["step"] == "community_review_next_action_followed"
        for event in community_lifecycle.recorded_reach_events
    )


@pytest.mark.asyncio
async def test_visibility_pull_blocks_active_community_study(
    community_lifecycle, monkeypatch
):
    monkeypatch.setattr(service, "community_visible_enabled", lambda _env=None: False)
    with pytest.raises(service.ReviewPrescriptionError, match="visibility"):
        await service.get_community_study(
            community_lifecycle, "learner-1", "prescription-1"
        )


@pytest.mark.asyncio
async def test_ordinary_complete_access_user_cannot_enter_operability_cohort(
    community_lifecycle,
    monkeypatch,
):
    db = community_lifecycle
    db.users.rows[0]["role"] = "user"

    with pytest.raises(service.ReviewPrescriptionError, match="visibility"):
        await service.get_community_study(
            db, "learner-1", "prescription-1"
        )

    db[service.COLLECTION].rows[0]["state"] = "recommended"
    with pytest.raises(service.ReviewPrescriptionError, match="visibility"):
        await service.start_prescription(
            db, "learner-1", "prescription-1"
        )
    assert db[service.COLLECTION].rows[0]["state"] == "recommended"


@pytest.mark.asyncio
async def test_prescription_ownership_is_enforced(community_lifecycle):
    with pytest.raises(service.ReviewPrescriptionError, match="not found"):
        await service.get_community_study(
            community_lifecycle, "different-learner", "prescription-1"
        )


def test_learning_adapter_records_assisted_practice_not_transfer():
    study = {
        "study_id": "study-1",
        "admission_policy_version": "licensed_neutral_coherent_guided.v2",
        "plan": {
            "input_fingerprint": "f" * 64,
            "chapters": [
                {
                    "event_id": "event-1",
                    "concept_id": "piece_safety.destination_safety",
                    "quality_id": "gap:piece_safety:destination_safety_exact",
                }
            ],
        },
    }
    progress = {
        "opaque-key": {
            "event_id": "event-1",
            "hinted": True,
            "predicted": True,
            "revealed": True,
            "watched": True,
            "replayed": True,
            "correct": False,
            "selected_option_id": "activity_is_enough",
            "replayed_move_uci": "c1g5",
        }
    }
    results = learning_adapter.lesson_results_from_community_walkthrough(
        prescription_id="prescription-1",
        study=study,
        progress=progress,
        occurred_at=service._now(),
    )
    assert len(results) == 1
    result = results[0]
    assert result.attempt_kind.value == "guided"
    assert result.correct is True
    assert result.prediction_correct is False
    assert result.application_outcome.value == "not_measured"
    assert result.earned_state().value == "can_do_with_help"


def test_completion_route_branches_before_personal_game_mutation():
    route_source = (
        Path(__file__).parents[1] / "routes" / "training_advanced.py"
    ).read_text(encoding="utf-8")
    branch = route_source.index("if isinstance(community_learning, dict):")
    personal_attempts = route_source.index("attempts = await db.puzzle_attempts.find")
    personal_mutation = route_source.index("# 1. Mark game as reviewed")
    assert branch < personal_attempts < personal_mutation
    community_section = route_source[branch:personal_attempts]
    assert '"assisted_learning": "recorded"' in community_section
    assert '"real_game_application": "not_measured"' in community_section
    assert '"/game-review/recommendation/{prescription_id}/next-action"' in (
        route_source
    )
