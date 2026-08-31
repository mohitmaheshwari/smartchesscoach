from __future__ import annotations

import asyncio
from copy import deepcopy

import pytest
from fastapi import HTTPException

from services.focus_engine import record_puzzle_completion
from services.opening_library_service import update_learning_progress
from services.puzzle_extraction_service import verified_puzzle_admission_enforced


class _FocusUsers:
    def __init__(self):
        self.document = {
            "user_id": "u1",
            "focus": {
                "puzzles_completed": 0,
                "puzzles_required": 3,
                "completed_puzzle_ids": [],
                "training_locked": True,
            },
        }

    async def find_one(self, _query, _projection=None):
        return {"focus": deepcopy(self.document["focus"])}

    async def find_one_and_update(
        self, query, update, projection=None, return_document=None
    ):
        puzzle_id = query["focus.completed_puzzle_ids"]["$ne"]
        completed = self.document["focus"]["completed_puzzle_ids"]
        if puzzle_id in completed:
            return None
        completed.append(puzzle_id)
        self.document["focus"]["puzzles_completed"] += 1
        return {"focus": deepcopy(self.document["focus"])}

    async def update_one(self, _query, update):
        locked = update.get("$set", {}).get("focus.training_locked")
        if locked is not None:
            self.document["focus"]["training_locked"] = locked


class _FocusDb:
    def __init__(self):
        self.users = _FocusUsers()


def test_focus_unlock_counts_each_verified_puzzle_once():
    db = _FocusDb()
    first = asyncio.run(record_puzzle_completion(db, "u1", "p1"))
    repeat = asyncio.run(record_puzzle_completion(db, "u1", "p1"))
    second = asyncio.run(record_puzzle_completion(db, "u1", "p2"))

    assert first["puzzles_completed"] == 1
    assert repeat["puzzles_completed"] == 1
    assert repeat["already_counted"] is True
    assert second["puzzles_completed"] == 2


class _OpeningProgress:
    def __init__(self):
        self.document = None

    async def update_one(self, query, update, upsert=False):
        created = self.document is None
        if created:
            self.document = {}
            self.document.update(update.get("$setOnInsert", {}))
        self.document.update(query)
        self.document.update(update.get("$set", {}))
        for key, value in update.get("$inc", {}).items():
            self.document[key] = self.document.get(key, 0) + value

    async def find_one(self, _query):
        return deepcopy(self.document)


class _OpeningDb:
    def __init__(self):
        self.opening_learning_progress = _OpeningProgress()


def test_browser_opening_completion_records_exposure_not_mastery():
    db = _OpeningDb()
    result = asyncio.run(update_learning_progress(
        db,
        "u1",
        "italian_game",
        main_line_progress=999,
        trap_learned="everything",
        practiced=True,
    ))
    stored = db.opening_learning_progress.document

    assert result["evidence_status"] == "seen_only"
    assert result["mastery_level"] == "unknown"
    assert stored["mastery_level"] == "unknown"
    assert stored["lesson_views"] == 1
    assert "main_line_progress" not in stored
    assert "times_practiced" not in stored
    assert "traps_learned" not in stored


def test_verified_admission_is_fail_closed_by_default(monkeypatch):
    monkeypatch.delenv("VERIFIED_PUZZLE_ADMISSION_ENFORCED", raising=False)
    assert verified_puzzle_admission_enforced() is True


def test_game_review_grader_accepts_only_server_resolvable_inputs():
    from routes.lab import MoveEvaluationRequest

    fields = getattr(MoveEvaluationRequest, "model_fields", None)
    if fields is None:
        fields = MoveEvaluationRequest.__fields__
    assert set(fields) == {"puzzle_id", "user_move"}


def test_mission_completion_contract_has_no_browser_score():
    from routes.missions import MissionCompleteRequest

    fields = getattr(MissionCompleteRequest, "model_fields", None)
    if fields is None:
        fields = MissionCompleteRequest.__fields__
    assert set(fields) == set()


class _MissionCollection:
    def __init__(self, document):
        self.document = deepcopy(document)
        self.updates = []

    async def find_one(self, query, _projection=None):
        if all(self.document.get(key) == value for key, value in query.items()):
            return deepcopy(self.document)
        return None

    async def update_one(self, query, update, **_kwargs):
        self.updates.append((deepcopy(query), deepcopy(update)))
        self.document.update(update.get("$set", {}))


class _MissionScoreDb:
    def __init__(self):
        self.behavioral_missions = _MissionCollection({
            "mission_id": "m1",
            "user_id": "u1",
            "goal_success_threshold": 2,
            "focus_label": "Piece safety",
        })
        self.mission_sessions = _MissionCollection({
            "session_id": "s1",
            "mission_id": "m1",
            "user_id": "u1",
            "score": {"attempted": 3, "correct": 1},
        })


def test_mission_service_ignores_forged_client_score():
    from mission_generation_service import complete_mission

    db = _MissionScoreDb()
    result = asyncio.run(complete_mission(
        mission_id="m1",
        session_id="s1",
        user_id="u1",
        score={"attempted": 99, "correct": 99},
        db=db,
    ))

    assert result["result"] == "fail"
    assert result["score"]["correct"] == 1
    assert db.behavioral_missions.document["result"] == "fail"


class _NoAssignmentCollection:
    async def find_one(self, _query, _projection=None):
        return None


class _NoAssignmentDb:
    def __init__(self):
        self.daily_fix_assignments = _NoAssignmentCollection()


def _user():
    from routes.auth import User

    return User(user_id="u1", email="u@example.com", name="User")


def test_daily_fix_cannot_complete_without_server_assignment(monkeypatch):
    from routes import daily_fix

    monkeypatch.setattr(daily_fix, "db", _NoAssignmentDb())
    with pytest.raises(HTTPException) as exc:
        asyncio.run(daily_fix.daily_fix_complete(user=_user()))
    assert exc.value.status_code == 409


def test_legacy_browser_success_and_llm_review_routes_are_retired():
    from routes import lab, player

    with pytest.raises(HTTPException) as challenge_exc:
        asyncio.run(player.record_challenge_result_endpoint(None, user=_user()))
    assert challenge_exc.value.status_code == 410

    with pytest.raises(HTTPException) as review_exc:
        asyncio.run(lab.get_coach_review("g1", user=_user()))
    assert review_exc.value.status_code == 410
