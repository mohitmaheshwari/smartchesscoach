"""Contract tests for the generic personalized lesson path."""

import asyncio
import copy

from services.teaching_engine import (
    PERSONALIZED_LESSON_TYPE,
    get_personalized_lesson,
    process_lesson_move,
    request_personalized_help,
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


class _Collection:
    def __init__(self):
        self.docs = []

    async def find_one(self, query, projection=None, sort=None):
        matches = [doc for doc in self.docs if _matches(doc, query)]
        if sort:
            matches.sort(
                key=lambda doc: doc.get(sort[0][0]),
                reverse=sort[0][1] < 0,
            )
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
        self.learning_sessions = _Collection()
        self.coach_sessions = _CoachSessions()


def _descriptor():
    return {
        "kind": "concept",
        "id": "piece_safety",
        "skill_id": "piece_safety",
        "title": "Undefended pieces",
        "rule": "Check every piece before moving.",
        "intro": "A loose piece gives the opponent a free target.",
        "canonical_source": "backend/data/theory/tactical_patterns.json",
        "content_version": "2.0.0",
        "items": [{
            "item_id": "p1",
            "fen": "8/8/8/8/8/8/4K3/7k w - - 0 1",
            "orientation": "white",
            "prompt": "Which move keeps the piece safe?",
            "reason_prompt": "What did you check?",
            "reason_choices": [
                {"id": "keeps_piece_safe", "label": "My pieces stay safe."},
                {"id": "looks_active", "label": "It looks active."},
            ],
            "_expected_reason": "keeps_piece_safe",
            "stage": "transfer",
            "source": "verified_practice",
            "source_ref": "p1",
            "board_verified": True,
            "_expected_san": "Kf3",
        }],
    }


def _install(monkeypatch, *, correct=True):
    async def resolve(*args, **kwargs):
        return _descriptor()

    async def profile(*args, **kwargs):
        return {
            "mode": "diagnostic_required",
            "why_now": "Show me what you notice, and I will start there.",
            "delivery": {"preferred_help": None},
        }

    async def grade(*args, **kwargs):
        return {
            "correct": correct,
            "feedback": "Good scan." if correct else "Check the destination.",
            "answer_san": "Kf3",
            "answer_uci": "e2f3",
            "grader_version": "test.v1",
        }

    monkeypatch.setattr(
        "services.personalized_lesson_adapter.resolve_personalized_lesson",
        resolve,
    )
    monkeypatch.setattr(
        "services.personal_teaching_profile.build_personal_teaching_profile",
        profile,
    )
    monkeypatch.setattr(
        "services.personalized_lesson_adapter.grade_personalized_move",
        grade,
    )


def _start(db):
    return asyncio.run(start_lesson(
        db,
        "session-1",
        "u1",
        PERSONALIZED_LESSON_TYPE,
        {"content_kind": "concept", "content_id": "piece_safety"},
    ))


def test_public_session_hides_answer_and_preserves_personal_why(monkeypatch):
    _install(monkeypatch)
    db = _DB()
    started = _start(db)

    assert started["current_item"]["stage"] == "transfer"
    assert "_expected_san" not in started["current_item"]
    assert started["teaching_profile"]["mode"] == "diagnostic_required"
    assert started["stage"] == "diagnose"
    assert started["learner_state"]["real_game_evidence"] == "not_measured"


def test_let_me_try_keeps_independent_credit_and_is_idempotent(monkeypatch):
    _install(monkeypatch)
    db = _DB()
    _start(db)
    asyncio.run(request_personalized_help(
        db,
        "u1",
        "session-1",
        "let_me_try",
        "help-1",
    ))
    first = asyncio.run(process_lesson_move(
        db,
        "session-1",
        "e2f3",
        interaction_id="move-1",
        reason_choice="keeps_piece_safe",
    ))
    duplicate = asyncio.run(process_lesson_move(
        db,
        "session-1",
        "e2f3",
        interaction_id="move-1",
    ))

    assert first == duplicate
    assert first["earned_state"] == "can_do_alone"
    assert first["complete"] is True


def test_board_hint_caps_credit_at_with_help(monkeypatch):
    _install(monkeypatch)
    db = _DB()
    _start(db)
    asyncio.run(request_personalized_help(
        db,
        "u1",
        "session-1",
        "show_on_board",
        "help-2",
    ))
    result = asyncio.run(process_lesson_move(
        db,
        "session-1",
        "e2f3",
        interaction_id="move-2",
        reason_choice="keeps_piece_safe",
    ))

    assert result["earned_state"] == "can_do_with_help"


def test_server_checked_reason_blocks_lucky_independent_move(monkeypatch):
    _install(monkeypatch)
    db = _DB()
    _start(db)
    result = asyncio.run(
        __import__(
            "services.teaching_engine",
            fromlist=["process_personalized_move"],
        ).process_personalized_move(
            db,
            "session-1",
            "e2f3",
            interaction_id="move-3",
            reason_choice="looks_active",
        )
    )

    assert result["correct"] is True
    assert result["earned_state"] == "learning"
    assert result["reasoning_consistent"] is False
    assert result["misconception"] == "activity_before_safety"
    assert "active-looking move" in result["corrective_action"]


def test_missing_reason_cannot_claim_independent_proof(monkeypatch):
    _install(monkeypatch)
    db = _DB()
    _start(db)
    result = asyncio.run(process_lesson_move(
        db,
        "session-1",
        "e2f3",
        interaction_id="move-without-reason",
    ))

    assert result["correct"] is True
    assert result["earned_state"] == "learning"


def test_wrong_transfer_never_reveals_answer(monkeypatch):
    _install(monkeypatch, correct=False)
    db = _DB()
    _start(db)
    result = asyncio.run(process_lesson_move(
        db,
        "session-1",
        "e2e3",
        interaction_id="move-4",
    ))

    assert result["correct"] is False
    assert result["answer_san"] is None
    assert result["misconception"] == "piece_left_unsafe"
    assert result["next_stage"] == "contrast"


def test_session_reader_enforces_user_ownership(monkeypatch):
    _install(monkeypatch)
    db = _DB()
    _start(db)

    result = asyncio.run(get_personalized_lesson(db, "u2", "session-1"))
    assert result == {"error": "Session not found"}


def test_review_session_uses_answer_hidden_retain_stage(monkeypatch):
    _install(monkeypatch)
    db = _DB()
    started = asyncio.run(start_lesson(
        db,
        "review-1",
        "u1",
        PERSONALIZED_LESSON_TYPE,
        {
            "content_kind": "concept",
            "content_id": "piece_safety",
            "review": True,
        },
    ))

    assert started["stage"] == "retain"
    assert "_expected_san" not in started["current_item"]
    result = asyncio.run(process_lesson_move(
        db,
        "review-1",
        "e2f3",
        interaction_id="review-answer",
        reason_choice="keeps_piece_safe",
    ))

    assert result["earned_state"] == "can_do_alone"
    assert result["complete"] is True


def _blind_descriptor():
    descriptor = _descriptor()
    first = copy.deepcopy(descriptor["items"][0])
    first.update({"item_id": "diagnostic-position-1", "stage": "diagnose"})
    second = copy.deepcopy(first)
    second.update({"item_id": "diagnostic-position-2", "stage": "transfer"})
    descriptor.update({
        "items": [first, second],
        "delivery_mode": "blind_diagnostic",
        "diagnostic_version": "home_replay_diagnostic.v1",
        "pair_fingerprint": "pair-1",
    })
    return descriptor


def _install_blind(monkeypatch):
    async def resolve(*args, **kwargs):
        return _blind_descriptor()

    async def profile(*args, **kwargs):
        return {"mode": "diagnostic_required", "delivery": {}}

    async def grade(*args, **kwargs):
        return {
            "correct": True,
            "target_result": "pass",
            "soundness": {"status": "sound", "reason": "verified_acceptable"},
            "feedback": "The decision holds up.",
            "answer_san": None,
            "answer_uci": None,
            "grader_version": "home_replay_diagnostic.v1",
        }

    monkeypatch.setattr(
        "services.personalized_lesson_adapter.resolve_personalized_lesson", resolve
    )
    monkeypatch.setattr(
        "services.personal_teaching_profile.build_personal_teaching_profile", profile
    )
    monkeypatch.setattr(
        "services.personalized_lesson_adapter.grade_personalized_move", grade
    )


def _assert_forbidden_keys_absent(value):
    forbidden = {
        "title", "rule", "intro", "canonical_source", "content_version",
        "source_ref", "reason_choices", "answer_san", "answer_uci",
        "pair_fingerprint", "quality_id", "detector_version",
    }
    if isinstance(value, dict):
        assert forbidden.isdisjoint(value.keys())
        for child in value.values():
            _assert_forbidden_keys_absent(child)
    elif isinstance(value, list):
        for child in value:
            _assert_forbidden_keys_absent(child)


def test_blind_diagnostic_move_precedes_reason_and_completes_two_positions(monkeypatch):
    _install_blind(monkeypatch)
    db = _DB()
    started = asyncio.run(start_lesson(
        db,
        "blind-1",
        "u1",
        PERSONALIZED_LESSON_TYPE,
        {"content_kind": "concept", "content_id": "piece_safety", "mode": "blind_diagnostic"},
    ))

    assert started["delivery_mode"] == "blind_diagnostic"
    assert started["awaiting_reason"] is False
    assert "lesson" not in started
    _assert_forbidden_keys_absent(started)

    staged = asyncio.run(process_lesson_move(
        db, "blind-1", "e2f3", interaction_id="stage-1"
    ))
    assert staged["awaiting_reason"] is True
    assert staged["current_item"]["reason_choices"]
    duplicate = asyncio.run(process_lesson_move(
        db, "blind-1", "e2f3", interaction_id="stage-1"
    ))
    assert duplicate == staged

    first = asyncio.run(process_lesson_move(
        db,
        "blind-1",
        "e2f3",
        interaction_id="answer-1",
        reason_choice="keeps_piece_safe",
    ))
    assert first["current_index"] == 1
    assert first["complete"] is False
    assert first["target_result"] == "pass"

    resumed = asyncio.run(get_personalized_lesson(db, "u1", "blind-1"))
    assert resumed["current_item"]["item_id"] == "diagnostic-position-2"
    assert resumed["awaiting_reason"] is False

    asyncio.run(process_lesson_move(
        db, "blind-1", "e2f3", interaction_id="stage-2"
    ))
    final = asyncio.run(process_lesson_move(
        db,
        "blind-1",
        "e2f3",
        interaction_id="answer-2",
        reason_choice="keeps_piece_safe",
    ))
    assert final["complete"] is True
    assert final["diagnostic_result"]["conclusion"] == "controlled_transfer"
    assert final["diagnostic_result"]["real_game_evidence"] == "not_measured"


def test_blind_refresh_after_move_reveals_only_reason_options(monkeypatch):
    _install_blind(monkeypatch)
    db = _DB()
    asyncio.run(start_lesson(
        db,
        "blind-refresh",
        "u1",
        PERSONALIZED_LESSON_TYPE,
        {"content_kind": "concept", "content_id": "piece_safety", "mode": "blind_diagnostic"},
    ))
    asyncio.run(process_lesson_move(
        db, "blind-refresh", "e2f3", interaction_id="staged"
    ))

    resumed = asyncio.run(get_personalized_lesson(db, "u1", "blind-refresh"))
    assert resumed["awaiting_reason"] is True
    assert resumed["pending_move_uci"] == "e2f3"
    assert resumed["current_item"]["reason_choices"]
    assert "lesson" not in resumed


def test_blind_unmeasured_soundness_never_awards_learning_credit(monkeypatch):
    _install_blind(monkeypatch)

    async def unmeasured_grade(*args, **kwargs):
        return {
            "correct": True,
            "target_result": "pass",
            "soundness": {"status": "unmeasured", "reason": "engine_unavailable"},
            "feedback": "I cannot verify the whole move fairly yet.",
            "answer_san": None,
            "answer_uci": None,
            "grader_version": "home_replay_diagnostic.v1",
        }

    monkeypatch.setattr(
        "services.personalized_lesson_adapter.grade_personalized_move",
        unmeasured_grade,
    )
    db = _DB()
    asyncio.run(start_lesson(
        db,
        "blind-unmeasured",
        "u1",
        PERSONALIZED_LESSON_TYPE,
        {"content_kind": "concept", "content_id": "piece_safety", "mode": "blind_diagnostic"},
    ))
    asyncio.run(process_lesson_move(
        db, "blind-unmeasured", "e2f3", interaction_id="stage-u1"
    ))
    first = asyncio.run(process_lesson_move(
        db,
        "blind-unmeasured",
        "e2f3",
        interaction_id="answer-u1",
        reason_choice="keeps_piece_safe",
    ))

    assert first["target_result"] == "pass"
    assert first["soundness"]["status"] == "unmeasured"
    assert first["earned_state"] == "learning"
    assert first["highest_earned_state"] == "learning"
