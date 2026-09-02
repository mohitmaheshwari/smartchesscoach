"""Contract tests for the generic personalized lesson path."""

import asyncio
import copy

from services.teaching_engine import (
    PERSONALIZED_LESSON_TYPE,
    continue_home_diagnostic,
    get_personalized_lesson,
    process_lesson_move,
    request_personalized_help,
    start_lesson,
)
from services.destination_safety_detector import (
    QUALITY_ID as DESTINATION_SAFETY_QUALITY_ID,
    build_destination_safety_reason_bundle,
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
        self.fail_shadow_once = False

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

    async def update_one(self, query, update, **kwargs):
        if isinstance(update, list):
            if self.fail_shadow_once:
                self.fail_shadow_once = False
                raise RuntimeError("transient shadow write failure")
            session_id = query["session_id"]
            existing = next(
                (doc for doc in self.docs if doc.get("session_id") == session_id),
                None,
            )
            if existing is None:
                existing = {
                    "_id": f"session-{len(self.docs) + 1}",
                    "session_id": session_id,
                    "events": [],
                }
                self.docs.append(existing)
            additions = (
                update[0]["$set"]["events"]["$concatArrays"][1]["$filter"]["input"]
            )
            keys = {
                event.get("idempotency_key")
                for event in existing.get("events", [])
            }
            existing["events"].extend(
                copy.deepcopy(event)
                for event in additions
                if event.get("idempotency_key") not in keys
            )
            if additions:
                existing["skill_id"] = additions[0].get("skill_id")
                existing["lesson_type"] = "canonical_learning_shadow"
            return _Write(1)
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


def test_flag_on_personalized_answer_uses_generic_shadow_ledger_once(monkeypatch):
    monkeypatch.setenv("COMPLETE_COACHING_SYSTEM_V1_ENABLED", "true")
    _install(monkeypatch)
    db = _DB()
    _start(db)

    first = asyncio.run(process_lesson_move(
        db,
        "session-1",
        "e2f3",
        interaction_id="stable-move-1",
        reason_choice="keeps_piece_safe",
    ))
    retry = asyncio.run(process_lesson_move(
        db,
        "session-1",
        "e2f3",
        interaction_id="stable-move-1",
        reason_choice="keeps_piece_safe",
    ))

    assert first == retry
    operational = next(
        doc for doc in db.learning_sessions.docs
        if doc.get("lesson_type") == PERSONALIZED_LESSON_TYPE
    )
    shadow = next(
        doc for doc in db.learning_sessions.docs
        if doc.get("lesson_type") == "canonical_learning_shadow"
    )
    assert "lesson_result" not in operational["events"][-1]
    assert len(shadow["events"]) == 1
    assert shadow["events"][0]["origin"] == "personalized_lesson"


def test_personalized_retry_repairs_a_transient_shadow_write_failure(monkeypatch):
    monkeypatch.setenv("COMPLETE_COACHING_SYSTEM_V1_ENABLED", "true")
    _install(monkeypatch)
    db = _DB()
    _start(db)
    db.learning_sessions.fail_shadow_once = True

    first = asyncio.run(process_lesson_move(
        db,
        "session-1",
        "e2f3",
        interaction_id="repairable-move-1",
        reason_choice="keeps_piece_safe",
    ))
    assert first["complete"] is True
    assert not any(
        doc.get("lesson_type") == "canonical_learning_shadow"
        for doc in db.learning_sessions.docs
    )

    retry = asyncio.run(process_lesson_move(
        db,
        "session-1",
        "e2f3",
        interaction_id="repairable-move-1",
        reason_choice="keeps_piece_safe",
    ))

    shadow = next(
        doc for doc in db.learning_sessions.docs
        if doc.get("lesson_type") == "canonical_learning_shadow"
    )
    assert retry == first
    assert len(shadow["events"]) == 1


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


def _blind_descriptor_v2():
    first_fen = "3r1rk1/p2p1ppp/2p1p3/8/N3P3/1P1RPP2/P1q4P/3R2K1 w - - 0 1"
    second_fen = "4k3/8/8/8/8/8/1b6/R3K3 w - - 0 1"
    return {
        "kind": "concept",
        "id": "piece_safety",
        "skill_id": "piece_safety",
        "canonical_source": "test-only/home_teaching_case_v2",
        "content_version": "2.0.0-test",
        "delivery_mode": "blind_diagnostic",
        "diagnostic_version": "home_replay_diagnostic.v2",
        "pair_fingerprint": "pair-v2",
        "items": [
            {
                "item_id": "diagnostic-v2-own-game",
                "fen": first_fen,
                "orientation": "white",
                "stage": "diagnose",
                "source": "own_game",
                "source_ref": "private-game-id",
                "_diagnostic_quality_id": DESTINATION_SAFETY_QUALITY_ID,
            },
            {
                "item_id": "diagnostic-v2-transfer",
                "fen": second_fen,
                "orientation": "white",
                "stage": "transfer",
                "source": "verified_practice",
                "source_ref": "private-puzzle-id",
                "_diagnostic_quality_id": DESTINATION_SAFETY_QUALITY_ID,
            },
        ],
    }


def _install_blind_v2(monkeypatch):
    async def resolve(*args, **kwargs):
        return _blind_descriptor_v2()

    async def profile(*args, **kwargs):
        return {"mode": "diagnostic_required", "delivery": {}}

    async def grade(descriptor, item, move, **kwargs):
        bundle = build_destination_safety_reason_bundle(item["fen"], move)
        return {
            "correct": bundle.target_result == "pass",
            "target_result": bundle.target_result,
            "soundness": {"status": "sound", "reason": "verified_acceptable"},
            "feedback": "The move and its board relationships were verified.",
            "answer_san": None,
            "answer_uci": None,
            "grader_version": "home_replay_diagnostic.v2.test",
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


def _start_blind_v2(db, session_id="blind-v2"):
    return asyncio.run(start_lesson(
        db,
        session_id,
        "u1",
        PERSONALIZED_LESSON_TYPE,
        {
            "content_kind": "concept",
            "content_id": "piece_safety",
            "mode": "blind_diagnostic",
        },
    ))


def _answer_v2_position(db, session_id, move, *, prefix, miss_first=False):
    staged = asyncio.run(process_lesson_move(
        db, session_id, move, interaction_id=f"{prefix}-move"
    ))
    bundle = build_destination_safety_reason_bundle(
        staged["current_item"]["fen"], move
    )
    payload = staged
    answer_index = 0
    while payload.get("awaiting_reason"):
        question = payload["current_item"]["reason_question"]
        component = next(
            part for part in bundle.components
            if part.question_id == question["question_id"]
        )
        choice_id = component.accepted_choice_ids[0]
        if miss_first and answer_index == 0:
            choice_id = next(
                choice.choice_id for choice in component.choices
                if choice.choice_id not in component.accepted_choice_ids
            )
        payload = asyncio.run(process_lesson_move(
            db,
            session_id,
            move,
            interaction_id=f"{prefix}-reason-{answer_index}",
            reason_choice=choice_id,
            reason_component_id=question["question_id"],
        ))
        answer_index += 1
    return staged, payload, answer_index


def _assert_v2_public_payload_is_answer_hidden(value):
    forbidden = {
        "accepted_choice_ids",
        "facts",
        "proof",
        "quality_id",
        "detector_version",
        "verifier_version",
        "source_ref",
        "_diagnostic_quality_id",
    }
    if isinstance(value, dict):
        assert forbidden.isdisjoint(value.keys())
        for child in value.values():
            _assert_v2_public_payload_is_answer_hidden(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            _assert_v2_public_payload_is_answer_hidden(child)


def test_v2_reason_questions_are_sequential_persisted_and_answer_hidden(monkeypatch):
    _install_blind_v2(monkeypatch)
    db = _DB()
    started = _start_blind_v2(db)
    assert started["diagnostic_version"] == "home_replay_diagnostic.v2"

    staged = asyncio.run(process_lesson_move(
        db, "blind-v2", "d3d2", interaction_id="v2-stage"
    ))
    question = staged["current_item"]["reason_question"]
    assert question["prompt"] == "Which of your rooks did the queen on c2 attack?"
    assert question["progress"] == {"current": 1, "total": 4}
    _assert_v2_public_payload_is_answer_hidden(staged)

    refreshed = asyncio.run(get_personalized_lesson(db, "u1", "blind-v2"))
    assert refreshed["current_item"]["reason_question"] == question
    _assert_v2_public_payload_is_answer_hidden(refreshed)

    bundle = build_destination_safety_reason_bundle(
        staged["current_item"]["fen"], "d3d2"
    )
    first = bundle.components[0]
    next_payload = asyncio.run(process_lesson_move(
        db,
        "blind-v2",
        "d3d2",
        interaction_id="v2-first-reason",
        reason_choice=first.accepted_choice_ids[0],
        reason_component_id=first.question_id,
    ))
    assert next_payload["awaiting_reason"] is True
    assert next_payload["current_item"]["reason_question"]["progress"] == {
        "current": 2,
        "total": 4,
    }
    assert next_payload["current_index"] == 0


def test_v2_holds_connection_summary_before_opening_transfer_board(monkeypatch):
    _install_blind_v2(monkeypatch)
    db = _DB()
    _start_blind_v2(db, "blind-v2-summary")

    _, first, count = _answer_v2_position(
        db, "blind-v2-summary", "d3d2", prefix="first"
    )
    assert count == 4
    assert first["awaiting_continue"] is True
    assert first["current_index"] == 0
    assert first["next_item"] is None
    assert first["position_summary"]["title"] == "You saw the whole connection."
    assert len(first["position_summary"]["demonstrated"]) == 4
    assert first["position_summary"]["missing"] == []

    refreshed = asyncio.run(get_personalized_lesson(
        db, "u1", "blind-v2-summary"
    ))
    assert refreshed["awaiting_continue"] is True
    assert refreshed["current_item"] is None
    assert refreshed["position_summary"] == first["position_summary"]

    continued = asyncio.run(continue_home_diagnostic(
        db,
        "u1",
        "blind-v2-summary",
        interaction_id="continue-transfer",
    ))
    assert continued["awaiting_continue"] is False
    assert continued["current_index"] == 1
    assert continued["current_item"]["item_id"] == "diagnostic-v2-transfer"
    duplicate = asyncio.run(continue_home_diagnostic(
        db,
        "u1",
        "blind-v2-summary",
        interaction_id="continue-transfer",
    ))
    assert duplicate == continued


def test_v2_two_positions_complete_with_component_level_evidence(monkeypatch):
    _install_blind_v2(monkeypatch)
    db = _DB()
    _start_blind_v2(db, "blind-v2-complete")

    _, first, _ = _answer_v2_position(
        db,
        "blind-v2-complete",
        "d3d2",
        prefix="complete-first",
        miss_first=True,
    )
    assert first["awaiting_continue"] is True
    assert len(first["position_summary"]["missing"]) == 1
    asyncio.run(continue_home_diagnostic(
        db,
        "u1",
        "blind-v2-complete",
        interaction_id="complete-continue",
    ))

    _, final, count = _answer_v2_position(
        db, "blind-v2-complete", "a1a8", prefix="complete-second"
    )
    assert count == 2
    assert final["complete"] is True
    assert final["diagnostic_result"]["conclusion"] == "current_learning_need"
    outcomes = final["diagnostic_result"]["component_outcomes"]
    assert outcomes["incoming_threat"]["asked"] == 2
    assert outcomes["incoming_threat"]["demonstrated"] == 1
    assert outcomes["destination_safety"]["asked"] == 2
    assert outcomes["destination_safety"]["demonstrated"] == 2


def test_v2_unsupported_move_is_honestly_unmeasured_and_retryable(monkeypatch):
    _install_blind_v2(monkeypatch)
    db = _DB()
    started = _start_blind_v2(db, "blind-v2-unmeasured")
    # Replace only the test session's first board with a legal pawn move. The
    # runtime reason family deliberately does not claim to explain pawns yet.
    db.learning_sessions.docs[0]["descriptor"]["items"][0]["fen"] = (
        "4k3/8/8/8/8/8/4P3/4K3 w - - 0 1"
    )

    result = asyncio.run(process_lesson_move(
        db,
        "blind-v2-unmeasured",
        "e2e4",
        interaction_id="unsupported-pawn",
    ))
    assert started["current_index"] == 0
    assert result["measurement_status"] == "unmeasured"
    assert result["retry_move"] is True
    assert result["awaiting_reason"] is False
    assert result["current_index"] == 0
