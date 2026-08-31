"""Shared teaching-engine contract tests for the PIC piece-safety lesson."""

import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.teaching_engine import (
    PIC_LESSON_TYPE,
    exit_lesson,
    get_pic_piece_safety_lesson,
    process_lesson_move,
    start_lesson,
)


def _matches(doc, query):
    for key, expected in query.items():
        if key == "events.idempotency_key":
            values = [event.get("idempotency_key") for event in doc.get("events", [])]
            if "$ne" in expected and expected["$ne"] in values:
                return False
            continue
        actual = doc.get(key)
        if isinstance(expected, dict) and "$in" in expected:
            if actual not in expected["$in"]:
                return False
        elif actual != expected:
            return False
    return True


class _Write:
    def __init__(self, modified_count=1):
        self.modified_count = modified_count


class _LearningSessions:
    def __init__(self):
        self.docs = []

    async def find_one(self, query, projection=None, sort=None):
        matches = [doc for doc in self.docs if _matches(doc, query)]
        if sort:
            matches.sort(key=lambda doc: doc.get(sort[0][0]), reverse=sort[0][1] < 0)
        return copy.deepcopy(matches[0]) if matches else None

    async def insert_one(self, doc):
        stored = copy.deepcopy(doc)
        stored["_id"] = f"session-{len(self.docs) + 1}"
        doc["_id"] = stored["_id"]
        self.docs.append(stored)
        return _Write()

    async def update_one(self, query, update):
        for doc in self.docs:
            if not _matches(doc, query):
                continue
            doc.update(copy.deepcopy(update.get("$set") or {}))
            for key, value in (update.get("$push") or {}).items():
                doc.setdefault(key, []).append(copy.deepcopy(value))
            return _Write(1)
        return _Write(0)


class _CoachSessions:
    async def find_one(self, query):
        return None


class _DB:
    def __init__(self):
        self.learning_sessions = _LearningSessions()
        self.coach_sessions = _CoachSessions()


def _puzzle(puzzle_id, source):
    return {
        "puzzle_id": puzzle_id,
        "fen": "8/8/8/8/8/8/4K3/7k w - - 0 1",
        "best_move_san": "Kf3",
        "source": source,
        "source_game_id": "g1" if source == "own_game" else None,
        "difficulty": "easy",
    }


@pytest.fixture
def puzzle_supply(monkeypatch):
    async def _supply(db, user_id, pattern, limit, *, private=False):
        assert private is True
        return {
            "own_puzzles": [_puzzle("own-1", "own_game")],
            "community_puzzles": [_puzzle("community-1", "community")],
        }

    monkeypatch.setattr(
        "services.puzzle_extraction_service.get_pattern_training_puzzles",
        _supply,
    )


@pytest.mark.asyncio
async def test_pic_lesson_is_own_game_first_resumable_and_never_mastery_eligible(
    puzzle_supply,
):
    db = _DB()
    started = await start_lesson(
        db,
        "pic-session-1",
        "user-1",
        PIC_LESSON_TYPE,
        {"limit": 2},
    )
    assert started["current_item"]["item_id"] == "own-1"
    assert "best_move_san" not in started["current_item"]
    assert started["mastery_eligible"] is False
    assert [item["item_id"] for item in db.learning_sessions.docs[0]["items"]] == [
        "own-1",
        "community-1",
    ]

    paused = await exit_lesson(db, "pic-session-1", "pause")
    assert paused["status"] == "paused"
    resumed = await start_lesson(
        db,
        "unused-new-id",
        "user-1",
        PIC_LESSON_TYPE,
        {"limit": 1},
    )
    assert resumed["session_id"] == "pic-session-1"
    assert resumed["status"] == "active"


@pytest.mark.asyncio
async def test_pic_move_is_graded_once_through_shared_dispatcher(
    puzzle_supply,
    monkeypatch,
):
    async def _resolve(db, puzzle_id, *, user_id=None):
        assert puzzle_id == "own-1"
        assert user_id == "user-1"
        return {"puzzle_id": puzzle_id}

    def _grade(puzzle, played_uci):
        assert puzzle == {"puzzle_id": "own-1"}
        assert played_uci == "e2f3"
        return {
            "correct": True,
            "quality": "best",
            "feedback": "Correct.",
            "best_move_san": "Kf3",
        }

    monkeypatch.setattr(
        "services.verified_puzzle_runtime.resolve_verified_puzzle",
        _resolve,
    )
    monkeypatch.setattr(
        "services.verified_puzzle_runtime.grade_resolved_puzzle",
        _grade,
    )
    db = _DB()
    await start_lesson(
        db,
        "pic-session-2",
        "user-1",
        PIC_LESSON_TYPE,
        {"limit": 1},
    )
    first = await process_lesson_move(
        db,
        "pic-session-2",
        "e2f3",
        interaction_id="move-1",
    )
    duplicate = await process_lesson_move(
        db,
        "pic-session-2",
        "e2f3",
        interaction_id="move-1",
    )
    assert first == duplicate
    assert first["correct"] is True
    assert first["complete"] is True
    answer_events = [
        event for event in db.learning_sessions.docs[0]["events"]
        if event["event_type"] == "answer_submitted"
    ]
    assert len(answer_events) == 1
    assert answer_events[0]["evidence_eligible"] is False
    assert answer_events[0]["rejection_reason"] == "assisted_verified_practice"


@pytest.mark.asyncio
async def test_pic_reader_enforces_user_ownership(puzzle_supply):
    db = _DB()
    await start_lesson(
        db,
        "pic-session-3",
        "user-1",
        PIC_LESSON_TYPE,
        {"limit": 1},
    )
    assert (
        await get_pic_piece_safety_lesson(db, "user-2", "pic-session-3")
    ) == {"error": "Session not found"}
