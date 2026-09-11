"""Truth, learning-state, and live-budget tests for Board Geometry."""

import copy
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import chess
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.board_geometry_service import (
    _shape_modules,
    build_pwc_moment,
    catalog,
    geometry_moments_for_move,
    get_session,
    grade_item,
    load_content,
)
from services.caption_facts import shared_attack_squares
from services.concept_mastery_service import get_board_geometry_mastery_projection
from services.teaching_engine import (
    BOARD_GEOMETRY_LESSON_TYPE,
    exit_lesson,
    process_lesson_action,
    start_lesson,
)


class _Write:
    def __init__(self, modified_count=1):
        self.modified_count = modified_count


class _Cursor:
    def __init__(self, docs):
        self.docs = [copy.deepcopy(doc) for doc in docs]

    def sort(self, *args, **kwargs):
        return self

    def limit(self, *args, **kwargs):
        return self

    def __aiter__(self):
        self._iter = iter(self.docs)
        return self

    async def __anext__(self):
        try:
            return next(self._iter)
        except StopIteration as exc:
            raise StopAsyncIteration from exc


def _matches(doc, query):
    for key, expected in query.items():
        if key == "$or":
            if not any(_matches(doc, clause) for clause in expected):
                return False
            continue
        if key == "events.idempotency_key":
            values = [event.get("idempotency_key") for event in doc.get("events", [])]
            if expected.get("$ne") in values:
                return False
            continue
        if key == "geometry_events.move_key":
            values = [event.get("move_key") for event in doc.get("geometry_events", [])]
            if expected.get("$ne") in values:
                return False
            continue
        actual = doc.get(key)
        if isinstance(expected, dict) and "$in" in expected:
            if actual not in expected["$in"]:
                return False
        elif isinstance(expected, dict) and "$exists" in expected:
            if bool(key in doc) != bool(expected["$exists"]):
                return False
        elif isinstance(expected, dict) and "$lt" in expected:
            if actual is None or actual >= expected["$lt"]:
                return False
        elif actual != expected:
            return False
    return True


def _set_path(doc, key, value):
    target = doc
    parts = key.split(".")
    for part in parts[:-1]:
        target = target.setdefault(part, {})
    target[parts[-1]] = copy.deepcopy(value)


class _LearningSessions:
    def __init__(self, docs=None):
        self.docs = [copy.deepcopy(doc) for doc in (docs or [])]

    def find(self, query, projection=None):
        return _Cursor([doc for doc in self.docs if _matches(doc, query)])

    async def find_one(self, query, projection=None, sort=None):
        found = [doc for doc in self.docs if _matches(doc, query)]
        return copy.deepcopy(found[0]) if found else None

    async def insert_one(self, doc):
        stored = copy.deepcopy(doc)
        stored["_id"] = f"learning-{len(self.docs) + 1}"
        doc["_id"] = stored["_id"]
        self.docs.append(stored)
        return _Write()

    async def update_one(self, query, update):
        for doc in self.docs:
            if not _matches(doc, query):
                continue
            for key, value in (update.get("$set") or {}).items():
                _set_path(doc, key, value)
            for key, value in (update.get("$push") or {}).items():
                doc.setdefault(key, []).append(copy.deepcopy(value))
            return _Write(1)
        return _Write(0)


class _ReadCollection:
    def __init__(self, docs=None):
        self.docs = docs or []

    def find(self, query, projection=None):
        return _Cursor(self.docs)


class _CoachSessions(_ReadCollection):
    def __init__(self, docs=None):
        super().__init__(docs)

    async def find_one(self, query, projection=None):
        found = [doc for doc in self.docs if _matches(doc, query)]
        return copy.deepcopy(found[0]) if found else None

    async def update_one(self, query, update):
        for doc in self.docs:
            if not _matches(doc, query):
                continue
            for key, amount in (update.get("$inc") or {}).items():
                doc[key] = int(doc.get(key) or 0) + amount
            for key, value in (update.get("$push") or {}).items():
                doc.setdefault(key, []).append(copy.deepcopy(value))
            return _Write(1)
        return _Write(0)


class _DB:
    def __init__(self, learning=None, coach=None):
        self.learning_sessions = _LearningSessions(learning)
        self.coach_sessions = _CoachSessions(coach)
        self.game_analyses = _ReadCollection([])


def test_content_has_four_complete_legal_modules():
    content = load_content()
    assert all(module["activity_count"] == 8 for module in catalog()["modules"])
    assert len(content["modules"]) == 4
    assert {module["family"] for module in content["modules"]} == {
        "knight", "pawn", "diagonal", "orthogonal"
    }
    for module in content["modules"]:
        assert len(module["activities"]) == 7
        assert chess.Board(module["flash"]["fen"]).is_valid()
        for item in module["activities"]:
            board = chess.Board(item["fen"])
            assert board.is_valid(), item["item_id"]
            for accepted in (item.get("expected") or {}).get("moves", []):
                assert board.parse_san(accepted) in board.legal_moves, item["item_id"]
                shapes = _shape_modules(item["fen"], accepted)
                assert any(
                    shape["family"] == module["family"] for shape in shapes
                ), item["item_id"]
            if item.get("stage") == "attack_map":
                own_non_king = [
                    square
                    for square, piece in board.piece_map().items()
                    if piece.color == board.turn and piece.piece_type != chess.KING
                ]
                assert len(own_non_king) == 1, item["item_id"]
                empty_attacks = {
                    chess.square_name(square)
                    for square in board.attacks(own_non_king[0])
                    if board.piece_at(square) is None
                }
                assert empty_attacks == set(item["expected"]["squares"]), item["item_id"]
            teaching_text = " ".join([
                item.get("prompt", ""),
                item.get("correct_feedback", ""),
            ]).lower()
            assert "centipawn" not in teaching_text
            assert "cp loss" not in teaching_text


def test_canonical_shared_square_primitive_handles_knights_and_pawn_direction():
    assert shared_attack_squares(["a8", "e8"], "knight") == ["c7"]
    assert shared_attack_squares(["c6", "e6"], "pawn", chess.WHITE) == ["d5"]
    assert shared_attack_squares(["c3", "e3"], "pawn", chess.BLACK) == ["d4"]


def test_selection_and_move_grading_are_exact_and_order_independent():
    targets = {
        "kind": "select_targets",
        "expected": {"squares": ["a8", "e8"]},
    }
    assert grade_item(targets, {"squares": ["e8", "a8"]}) is True
    assert grade_item(targets, {"squares": ["e8"]}) is False
    move = {
        "kind": "move",
        "fen": "r3k3/8/8/1N6/8/8/8/7K w - - 0 1",
        "expected": {"moves": ["Nc7+"]},
    }
    assert grade_item(move, {"move": "b5c7"}) is True
    assert grade_item(move, {"move": "Na3"}) is False


def test_allowed_missed_found_and_line_shapes_use_canonical_facts():
    fork_fen = "r3k3/8/8/1N6/8/8/8/7K w - - 0 1"
    found = geometry_moments_for_move({
        "fen_before": fork_fen,
        "move": "Nc7+",
        "cp_loss": 0,
        "evaluation": "good",
    })
    contradictory_quality = geometry_moments_for_move({
        "fen_before": fork_fen,
        "move": "Nc7+",
        "cp_loss": 200,
        "evaluation": "good",
    })
    explicit_inaccuracy = geometry_moments_for_move({
        "fen_before": fork_fen,
        "move": "Na3",
        "best_move": "Nc7+",
        "cp_loss": 120,
        "evaluation": "inaccuracy",
    })
    missed = geometry_moments_for_move({
        "fen_before": fork_fen,
        "move": "Na3",
        "best_move": "Nc7+",
        "cp_loss": 200,
        "evaluation": "mistake",
    })
    allowed_fen = "7k/8/8/8/1n6/8/7P/R3K3 w - - 0 1"
    board = chess.Board(allowed_fen)
    board.push_san("h3")
    allowed = geometry_moments_for_move({
        "fen_before": allowed_fen,
        "fen_after": board.fen(),
        "move": "h3",
        "best_move": "h4",
        "pv_after_played": ["Nc2+"],
        "cp_loss": 200,
        "evaluation": "mistake",
    })
    assert found[0]["moment_type"] == "found"
    assert not any(
        moment["moment_type"] == "found" for moment in contradictory_quality
    )
    assert not any(
        moment["moment_type"] == "missed" for moment in explicit_inaccuracy
    )
    assert missed[0]["moment_type"] == "missed"
    assert allowed[0]["moment_type"] == "allowed"
    pin = _shape_modules(
        "4k3/8/2n5/8/8/8/4B3/4K3 w - - 0 1", "Bb5"
    )
    assert pin[0]["family"] == "diagonal"
    assert pin[0]["kind"] == "pin"
    assert pin[0]["target_squares"] == ["c6", "e8"]


@pytest.mark.asyncio
async def test_shared_teaching_dispatcher_resumes_and_deduplicates_actions():
    db = _DB()
    started = await start_lesson(
        db,
        "geometry-session-1",
        "user-1",
        BOARD_GEOMETRY_LESSON_TYPE,
        {"module_id": "knight_shared_square"},
    )
    assert started["display_stage"] == "flash"
    flash = await process_lesson_action(
        db,
        started["session_id"],
        "user-1",
        {"action": "continue"},
        interaction_id="flash-1",
    )
    duplicate = await process_lesson_action(
        db,
        started["session_id"],
        "user-1",
        {"action": "continue"},
        interaction_id="flash-1",
    )
    assert flash == duplicate
    assert flash["display_stage"] == "activity"
    paused = await exit_lesson(db, started["session_id"], "pause")
    assert paused["status"] == "paused"
    resumed = await start_lesson(
        db,
        "unused-session",
        "user-1",
        BOARD_GEOMETRY_LESSON_TYPE,
        {"module_id": "knight_shared_square"},
    )
    assert resumed["session_id"] == started["session_id"]
    assert resumed["status"] == "active"


@pytest.mark.asyncio
async def test_reveal_advances_as_assisted_learning_without_earning_evidence():
    db = _DB()
    started = await start_lesson(
        db,
        "geometry-session-reveal",
        "user-1",
        BOARD_GEOMETRY_LESSON_TYPE,
        {"module_id": "knight_shared_square"},
    )
    await process_lesson_action(
        db,
        started["session_id"],
        "user-1",
        {"action": "continue"},
        interaction_id="flash-reveal",
    )
    revealed = await process_lesson_action(
        db,
        started["session_id"],
        "user-1",
        {"action": "reveal"},
        interaction_id="reveal-1",
    )
    assert revealed["revealed"] is True
    assert revealed["advance"] is True
    resumed = await get_session(db, "user-1", started["session_id"])
    assert resumed["current_index"] == 1
    event = db.learning_sessions.docs[0]["events"][-1]
    assert event["evidence_eligible"] is False
    assert event["rejection_reason"] == "answer_revealed"


@pytest.mark.asyncio
async def test_mastery_is_remembered_then_proven_only_after_a_verified_found_event():
    db = _DB(
        learning=[{
            "user_id": "user-1",
            "lesson_type": BOARD_GEOMETRY_LESSON_TYPE,
            "module_id": "knight_shared_square",
            "status": "completed",
            "independent_passed": True,
        }],
        coach=[{
            "user_id": "user-1",
            "geometry_events": [{
                "payload": {
                    "module_id": "knight_shared_square",
                    "moment_type": "found",
                }
            }],
        }],
    )
    projection = await get_board_geometry_mastery_projection(db, "user-1")
    knight = projection["modules"]["knight_shared_square"]
    assert knight["state"] == "proven_in_games"
    assert knight["verified_game_applications"] == 1


@pytest.mark.asyncio
async def test_mastery_exposes_due_delayed_recall_separately():
    db = _DB(learning=[{
        "user_id": "user-1",
        "lesson_type": BOARD_GEOMETRY_LESSON_TYPE,
        "module_id": "pawn_fork_v",
        "mode": "learning",
        "status": "completed",
        "independent_passed": True,
        "delayed_available_at": datetime.now(timezone.utc) - timedelta(minutes=1),
    }])
    projection = await get_board_geometry_mastery_projection(db, "user-1")
    pawn = projection["modules"]["pawn_fork_v"]
    assert pawn["state"] == "remembered"
    assert pawn["delayed_due"] is True
    assert pawn["delayed_recall_passed"] is False


@pytest.mark.asyncio
async def test_pwc_surfaces_once_but_keeps_later_verified_observations(monkeypatch):
    async def _eligible(db, user_id):
        return {"knight_shared_square"}

    monkeypatch.setenv("PWC_BOARD_GEOMETRY", "true")
    monkeypatch.setattr(
        "services.board_geometry_service.eligible_modules", _eligible
    )
    fork_fen = "r3k3/8/8/1N6/8/8/8/7K w - - 0 1"
    first = {
        "move": "Na3",
        "move_number": 1,
        "by": "player",
        "fen_before": fork_fen,
        "fen_after": fork_fen,
    }
    session = {
        "_id": "coach-1",
        "session_id": "coach-session-1",
        "user_id": "user-1",
        "geometry_focus_module": "knight_shared_square",
        "move_history": [first],
        "geometry_last_user_evidence": {
            **first,
            "best_move": "Nc7+",
            "cp_loss": 200,
            "evaluation": "mistake",
        },
    }
    db = _DB(coach=[session])
    stored = db.coach_sessions.docs[0]
    first_payload = await build_pwc_moment(db, stored)
    assert first_payload["surfaced"] is True
    assert stored["geometry_prompt_count"] == 1
    stored["geometry_events"][0]["outcome"] = "skip"

    second = {**first, "move_number": 2}
    stored["move_history"].append(second)
    stored["geometry_last_user_evidence"] = {
        **second,
        "best_move": "Nc7+",
        "cp_loss": 200,
        "evaluation": "mistake",
    }
    assert await build_pwc_moment(db, stored) is None
    assert stored["geometry_prompt_count"] == 1
    assert len(stored["geometry_events"]) == 2
    assert stored["geometry_events"][1]["surfaced"] is False
    assert stored["geometry_events"][1]["outcome"] == "observed"


@pytest.mark.asyncio
async def test_pwc_waits_for_the_exact_completed_move_verdict(monkeypatch):
    monkeypatch.setenv("PWC_BOARD_GEOMETRY", "true")
    fork_fen = "r3k3/8/8/1N6/8/8/8/7K w - - 0 1"
    move = {
        "move": "Na3",
        "by": "player",
        "fen_before": fork_fen,
        "fen_after": fork_fen,
    }
    session = {
        "_id": "coach-race",
        "session_id": "coach-race",
        "user_id": "user-1",
        "geometry_focus_module": "knight_shared_square",
        "geometry_focus_verified": True,
        "move_history": [move],
        "geometry_last_user_evidence": {
            **move,
            "move_number": 2,
            "best_move": "Nc7+",
            "cp_loss": 200,
            "evaluation": "mistake",
        },
    }
    db = _DB(coach=[session])
    assert await build_pwc_moment(db, db.coach_sessions.docs[0]) is None
    assert db.coach_sessions.docs[0].get("geometry_events") is None

    db.coach_sessions.docs[0]["geometry_last_user_evidence"]["move_number"] = 1
    db.coach_sessions.docs[0]["geometry_last_user_evidence"].pop("evaluation")
    assert await build_pwc_moment(db, db.coach_sessions.docs[0]) is None
    assert db.coach_sessions.docs[0].get("geometry_events") is None


@pytest.mark.asyncio
async def test_pwc_needs_explicit_focus_and_records_prompt_collisions_silently(monkeypatch):
    async def _eligible(db, user_id):
        return {"knight_shared_square"}

    monkeypatch.setenv("PWC_BOARD_GEOMETRY", "true")
    monkeypatch.setattr(
        "services.board_geometry_service.eligible_modules", _eligible
    )
    fork_fen = "r3k3/8/8/1N6/8/8/8/7K w - - 0 1"
    move = {
        "move": "Na3",
        "move_number": 1,
        "by": "player",
        "fen_before": fork_fen,
        "fen_after": fork_fen,
    }
    base = {
        "_id": "coach-focus",
        "session_id": "coach-focus",
        "user_id": "user-1",
        "move_history": [move],
        "geometry_last_user_evidence": {
            **move,
            "best_move": "Nc7+",
            "cp_loss": 200,
            "evaluation": "mistake",
        },
    }
    unfocused_db = _DB(coach=[base])
    assert await build_pwc_moment(unfocused_db, unfocused_db.coach_sessions.docs[0]) is None
    assert unfocused_db.coach_sessions.docs[0].get("geometry_events") is None

    focused = {**copy.deepcopy(base), "geometry_focus_module": "knight_shared_square"}
    focused_db = _DB(coach=[focused])
    stored = focused_db.coach_sessions.docs[0]
    assert await build_pwc_moment(focused_db, stored, allow_surface=False) is None
    assert stored.get("geometry_prompt_count", 0) == 0
    assert stored["geometry_events"][0]["outcome"] == "observed"
