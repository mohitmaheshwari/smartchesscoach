import asyncio
import copy
from datetime import datetime, timezone

import pytest

from services import verified_puzzle_attempt_service as attempt_service
from services.concept_mastery_service import reduce_lesson_results_shadow
from services.learning_evidence_ledger import (
    build_shadow_learning_event,
    store_shadow_lesson_results,
)
from services.personal_curriculum import (
    ApplicationOutcome,
    AttemptKind,
    ContractViolation,
    EvidenceSourceType,
    LessonResult,
    StudentState,
)
from services.review_learning_adapter import application_results_from_observations
from services.verified_puzzle_admission import AdmissionStatus, AdmissionVerdict


NOW = datetime(2026, 9, 2, 9, 30, tzinfo=timezone.utc)
FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
SUBMISSION_A = "12345678-1234-4234-8234-1234567890ab"
SUBMISSION_B = "87654321-4321-4321-8321-ba0987654321"


class _UpdateResult:
    def __init__(self, upserted_id=None):
        self.upserted_id = upserted_id


class _MemoryCollection:
    def __init__(self):
        self.documents = {}
        self.update_calls = []

    async def find_one(self, query, _projection=None):
        if "_id" in query:
            value = self.documents.get(query["_id"])
            return copy.deepcopy(value) if value is not None else None
        for value in self.documents.values():
            if all(value.get(key) == expected for key, expected in query.items()):
                return copy.deepcopy(value)
        return None

    async def update_one(self, query, update, upsert=False):
        self.update_calls.append((copy.deepcopy(query), copy.deepcopy(update), upsert))
        if isinstance(update, list):
            key = query["session_id"]
            created = key not in self.documents
            document = self.documents.setdefault(
                key,
                {
                    "_id": key,
                    "session_id": key,
                    "events": [],
                },
            )
            additions = (
                update[0]["$set"]["events"]["$concatArrays"][1]["$filter"]["input"]
            )
            existing = {
                event.get("idempotency_key") for event in document.get("events", [])
            }
            document["events"].extend(
                copy.deepcopy(event)
                for event in additions
                if event.get("idempotency_key") not in existing
            )
            if additions:
                first = additions[0]
                document.setdefault("user_id", first.get("lesson_result", {}).get("user_id"))
                document.setdefault("skill_id", first.get("skill_id"))
            return _UpdateResult(key if created and upsert else None)

        key = query.get("_id")
        if "$setOnInsert" in update:
            if key in self.documents:
                return _UpdateResult()
            document = copy.deepcopy(update["$setOnInsert"])
            document.setdefault("_id", key)
            self.documents[key] = document
            return _UpdateResult(key if upsert else None)
        if "$set" in update:
            if key not in self.documents:
                if not upsert:
                    return _UpdateResult()
                self.documents[key] = {"_id": key}
            self.documents[key].update(copy.deepcopy(update["$set"]))
            return _UpdateResult(key if upsert else None)
        raise AssertionError(f"unsupported test update: {update}")


class _Db:
    def __init__(self):
        self.puzzle_attempts = _MemoryCollection()
        self.puzzle_recovery_credits = _MemoryCollection()
        self.learning_sessions = _MemoryCollection()


async def _fixed_rating(_db, _user_id):
    return {
        "rating": 1187,
        "source": "recent_game_median",
        "platform": "chess.com",
        "sample_games": 3,
        "as_of": "2026-09-01T12:00:00+00:00",
    }, None


def _specific_puzzle():
    verdict = AdmissionVerdict(
        status=AdmissionStatus.SPECIFIC,
        reason_codes=("specific_proof_verified",),
        source_kind="analyzed_game",
        source_fingerprint="a" * 64,
        analysis_fingerprint="b" * 64,
        reconstructed_fen=FEN,
        played_move_uci="a2a3",
        acceptable_moves_uci=("e2e4",),
        concept_id="piece_safety.destination_safety_exact",
        broad_category="piece_safety",
        detector_id="piece_safety.destination_safety_exact",
        detector_version="piece_safety.destination_safety_exact.v1",
        verifier_id="destination_safety_exchange_verifier",
        verifier_version="v1",
        quality_id="gap:piece_safety:destination_safety_exact",
        quality_grade="plan",
        detector_facts=({"piece": "pawn", "square": "e2"},),
        verifier_facts=({"piece": "pawn", "square": "e2"},),
    ).to_document()
    return {
        "puzzle_id": "game-1_m1",
        "fen": FEN,
        "best_move_uci": "e2e4",
        "best_move_san": "e4",
        "source": "your_game",
        "verified_admission": verdict,
    }


def _lesson_result(
    *,
    skill_id="skill-a",
    source_event_id="source-1",
    evidence_complete=True,
):
    limitations = () if evidence_complete else ("assistance_not_measured",)
    return LessonResult(
        content_kind="concept",
        content_id=skill_id,
        canonical_source="test.skill",
        content_version="v1",
        skill_id=skill_id,
        primary_skill_id=skill_id,
        attempt_kind=AttemptKind.INDEPENDENT,
        occurred_at=NOW,
        correct=True,
        position_id="position-1",
        board_verified=True,
        distinct_position=True,
        source_event_id=source_event_id,
        evidence_complete=evidence_complete,
        evidence_limitations=limitations,
        assistance_measured=evidence_complete,
    )


def test_incomplete_lesson_evidence_cannot_prove_independent_or_application():
    incomplete = _lesson_result(evidence_complete=False)
    applied = LessonResult(
        content_kind="concept",
        content_id="skill-a",
        canonical_source="test.skill",
        content_version="v1",
        skill_id="skill-a",
        attempt_kind=AttemptKind.APPLICATION,
        occurred_at=NOW,
        application_outcome=ApplicationOutcome.APPLIED,
        source_type=EvidenceSourceType.ORGANIC_GAME,
        detector_quality_id="gap:piece_safety:destination_safety_exact",
        source_event_id="game:1",
        evidence_complete=False,
        evidence_limitations=("opportunity_comparability_not_proven",),
    )

    assert incomplete.earned_state() == StudentState.LEARNING
    assert applied.earned_state() is None
    with pytest.raises(ContractViolation):
        LessonResult(
            content_kind="concept",
            content_id="skill-a",
            canonical_source="test.skill",
            content_version="v1",
            skill_id="skill-a",
            attempt_kind=AttemptKind.INDEPENDENT,
            occurred_at=NOW,
            correct=True,
            position_id="position-1",
            evidence_complete=False,
        )


def test_lesson_result_v2_round_trips_attempt_rating_and_proof_provenance():
    result = LessonResult(
        content_kind="concept",
        content_id="skill-a",
        canonical_source="test.skill",
        content_version="v1",
        skill_id="skill-a",
        attempt_kind=AttemptKind.INDEPENDENT,
        occurred_at=NOW,
        correct=True,
        position_id="position-1",
        attempt_id="attempt-1",
        response_move_uci="e2e4",
        response_time_ms=4123,
        first_answer=True,
        retry_index=0,
        assistance_measured=False,
        evidence_complete=False,
        evidence_limitations=("assistance_not_measured",),
        rating=1187,
        rating_source="recent_game_median",
        rating_platform="chess.com",
        rating_sample_games=3,
        rating_as_of="2026-09-01T12:00:00+00:00",
        admission_version="verified_puzzle_admission.v2",
        admission_fingerprint="c" * 64,
        proof_contract_version="verified_puzzle_admission.v2",
        source_event_id="attempt:1",
    )

    payload = result.event_dict()
    restored = LessonResult.from_event_dict(payload)

    assert restored.event_dict() == payload
    assert restored.rating == 1187
    assert restored.admission_fingerprint == "c" * 64
    assert restored.earned_state() == StudentState.LEARNING


def test_lesson_result_rejects_malformed_chess_and_boolean_evidence_fields():
    base = {
        "content_kind": "concept",
        "content_id": "skill-a",
        "canonical_source": "test.skill",
        "content_version": "v1",
        "skill_id": "skill-a",
        "attempt_kind": AttemptKind.INDEPENDENT,
        "occurred_at": NOW,
        "correct": True,
        "position_id": "position-1",
    }

    with pytest.raises(ContractViolation):
        LessonResult(**base, response_move_uci="knight-to-f3")
    with pytest.raises(ContractViolation):
        LessonResult(**{**base, "correct": "true"})
    with pytest.raises(ContractViolation):
        LessonResult(**base, response_time_ms=True)
    with pytest.raises(ContractViolation):
        LessonResult(**base, retry_index=True)
    with pytest.raises(ContractViolation):
        LessonResult(**base, rating=True, rating_source="profile")

    payload = LessonResult(**base).event_dict()
    payload["attempt"]["evidence_complete"] = "false"
    with pytest.raises(ContractViolation):
        LessonResult.from_event_dict(payload)

    payload = LessonResult(**base).event_dict()
    payload["attempt"]["evidence_limitations"] = "not-an-array"
    with pytest.raises(ContractViolation):
        LessonResult.from_event_dict(payload)


def test_generic_ledger_deduplicates_atomically_and_isolates_skills():
    collection = _MemoryCollection()
    first = build_shadow_learning_event(_lesson_result(), origin="test")
    duplicate = copy.deepcopy(first)

    asyncio.run(
        store_shadow_lesson_results(
            collection,
            user_id="user-1",
            events=(first, duplicate),
        )
    )
    asyncio.run(
        store_shadow_lesson_results(
            collection,
            user_id="user-1",
            events=(first,),
        )
    )

    assert len(collection.documents) == 1
    session = next(iter(collection.documents.values()))
    assert session["skill_id"] == "skill-a"
    assert len(session["events"]) == 1

    other = build_shadow_learning_event(
        _lesson_result(skill_id="skill-b", source_event_id="source-2"),
        origin="test",
    )
    with pytest.raises(ContractViolation):
        asyncio.run(
            store_shadow_lesson_results(
                collection,
                user_id="user-1",
                events=(first, other),
            )
        )
    forged = copy.deepcopy(first)
    forged["skill_id"] = "skill-b"
    with pytest.raises(ContractViolation):
        asyncio.run(
            store_shadow_lesson_results(
                collection,
                user_id="user-1",
                events=(forged,),
            )
        )


def test_shadow_reducer_rejects_malformed_cross_skill_duplicate_and_forged_state():
    valid = build_shadow_learning_event(_lesson_result(), origin="test")
    duplicate_source = build_shadow_learning_event(
        _lesson_result(source_event_id="source-1"),
        origin="another-origin",
    )
    cross_skill = build_shadow_learning_event(
        _lesson_result(skill_id="skill-b", source_event_id="source-2"),
        origin="test",
    )
    forged = copy.deepcopy(valid)
    forged["lesson_result"]["earned_state"] = "used_in_games"
    malformed = {
        "event_type": "lesson_result",
        "rollout_mode": "shadow",
        "lesson_result": {},
    }

    projection = reduce_lesson_results_shadow(
        (valid, duplicate_source, cross_skill, forged, malformed),
        skill_id="skill-a",
    )

    assert projection["state"] == "can_do_alone"
    assert projection["visible_mastery_changed"] is False
    assert projection["evidence"]["accepted_events"] == 1
    assert projection["evidence"]["rejected_events"] == 4


def test_exact_game_opportunities_keep_handled_missed_and_absent_distinct():
    def observation(ply, **fact):
        return {
            "schema_version": 18,
            "ply": ply,
            "destination_safety_exact": {
                "version": "piece_safety.destination_safety_exact.v1",
                **fact,
            },
        }

    rows = (
        observation(1, derivation_status="ok", eligible=True, outcome="handled"),
        observation(
            2,
            derivation_status="ok",
            eligible=True,
            outcome="miss",
            fires=True,
        ),
        observation(3, derivation_status="ok", eligible=False, outcome="ineligible"),
        observation(4, derivation_status="unavailable", eligible=False),
    )
    legacy = application_results_from_observations(
        game_id="game-1",
        observations=rows,
        occurred_at=NOW,
        include_handled=False,
    )
    expanded = application_results_from_observations(
        game_id="game-1",
        observations=rows,
        occurred_at=NOW,
        include_handled=True,
    )

    assert [item.application_outcome for item in legacy] == [
        ApplicationOutcome.MISSED
    ]
    assert [item.application_outcome for item in expanded] == [
        ApplicationOutcome.APPLIED,
        ApplicationOutcome.MISSED,
    ]
    assert [item.evidence_ref for item in expanded] == ["game-1:1", "game-1:2"]


def test_same_submission_is_one_attempt_one_credit_and_one_event(monkeypatch):
    monkeypatch.setenv("COMPLETE_COACHING_SYSTEM_V1_ENABLED", "true")
    monkeypatch.setattr(attempt_service, "_rating_snapshot", _fixed_rating)
    db = _Db()
    puzzle = _specific_puzzle()

    first = asyncio.run(
        attempt_service.record_verified_puzzle_attempt(
            db,
            user_id="user-1",
            puzzle_id="game-1_m1",
            puzzle=puzzle,
            played_uci="e2e4",
            submission_id=SUBMISSION_A,
        )
    )
    retry = asyncio.run(
        attempt_service.record_verified_puzzle_attempt(
            db,
            user_id="user-1",
            puzzle_id="game-1_m1",
            puzzle=puzzle,
            played_uci="e2e4",
            submission_id=SUBMISSION_A,
        )
    )

    assert first["attempt_id"] == retry["attempt_id"]
    assert first["duplicate"] is False
    assert retry["duplicate"] is True
    assert first["recovery_credit_awarded"] is True
    assert retry["recovery_credit_awarded"] is True
    assert first["recovery_credit_claimed_now"] is True
    assert retry["recovery_credit_claimed_now"] is False
    assert len(db.puzzle_attempts.documents) == 1
    assert len(db.puzzle_recovery_credits.documents) == 1
    sessions = list(db.learning_sessions.documents.values())
    assert len(sessions) == 1
    assert len(sessions[0]["events"]) == 1


def test_different_submission_ids_create_distinct_attempts(monkeypatch):
    monkeypatch.setenv("COMPLETE_COACHING_SYSTEM_V1_ENABLED", "true")
    monkeypatch.setattr(attempt_service, "_rating_snapshot", _fixed_rating)
    db = _Db()
    puzzle = _specific_puzzle()

    for submission_id in (SUBMISSION_A, SUBMISSION_B):
        result = asyncio.run(
            attempt_service.record_verified_puzzle_attempt(
                db,
                user_id="user-1",
                puzzle_id="game-1_m1",
                puzzle=puzzle,
                played_uci="e2e4",
                submission_id=submission_id,
            )
        )
        assert result["quality"] == "best"

    assert len(db.puzzle_attempts.documents) == 2
    assert len(db.puzzle_recovery_credits.documents) == 1
    session = next(iter(db.learning_sessions.documents.values()))
    assert len(session["events"]) == 2


def test_submission_identity_cannot_be_reused_for_a_different_answer(monkeypatch):
    monkeypatch.setenv("COMPLETE_COACHING_SYSTEM_V1_ENABLED", "true")
    monkeypatch.setattr(attempt_service, "_rating_snapshot", _fixed_rating)
    db = _Db()
    puzzle = _specific_puzzle()

    first = asyncio.run(
        attempt_service.record_verified_puzzle_attempt(
            db,
            user_id="user-1",
            puzzle_id="game-1_m1",
            puzzle=puzzle,
            played_uci="d2d4",
            submission_id=SUBMISSION_A,
        )
    )
    conflict = asyncio.run(
        attempt_service.record_verified_puzzle_attempt(
            db,
            user_id="user-1",
            puzzle_id="game-1_m1",
            puzzle=puzzle,
            played_uci="e2e4",
            submission_id=SUBMISSION_A,
        )
    )

    assert first["correct"] is False
    assert conflict["quality"] == "invalid"
    assert conflict["shadow_event_emitted"] is False
    assert len(db.puzzle_attempts.documents) == 1
    assert len(db.puzzle_recovery_credits.documents) == 0


def test_invalid_or_missing_submission_identity_never_becomes_learning_evidence(
    monkeypatch,
):
    monkeypatch.setenv("COMPLETE_COACHING_SYSTEM_V1_ENABLED", "true")
    monkeypatch.setattr(attempt_service, "_rating_snapshot", _fixed_rating)
    puzzle = _specific_puzzle()
    invalid_db = _Db()
    missing_db = _Db()

    invalid = asyncio.run(
        attempt_service.record_verified_puzzle_attempt(
            invalid_db,
            user_id="user-1",
            puzzle_id="game-1_m1",
            puzzle=puzzle,
            played_uci="e2e4",
            submission_id="not-a-uuid",
        )
    )
    missing = asyncio.run(
        attempt_service.record_verified_puzzle_attempt(
            missing_db,
            user_id="user-1",
            puzzle_id="game-1_m1",
            puzzle=puzzle,
            played_uci="e2e4",
        )
    )

    assert invalid["quality"] == "invalid"
    assert invalid_db.puzzle_attempts.documents == {}
    assert missing["idempotency_proven"] is False
    assert missing["shadow_event_emitted"] is False
    assert len(missing_db.puzzle_attempts.documents) == 1
    assert missing_db.learning_sessions.documents == {}


def test_invalid_time_and_client_move_history_cannot_corrupt_attempt_evidence(
    monkeypatch,
):
    monkeypatch.setattr(attempt_service, "_rating_snapshot", _fixed_rating)
    puzzle = _specific_puzzle()
    invalid_db = _Db()
    valid_db = _Db()

    invalid = asyncio.run(
        attempt_service.record_verified_puzzle_attempt(
            invalid_db,
            user_id="user-1",
            puzzle_id="game-1_m1",
            puzzle=puzzle,
            played_uci="e2e4",
            time_taken_ms=True,
            submission_id=SUBMISSION_A,
        )
    )
    valid = asyncio.run(
        attempt_service.record_verified_puzzle_attempt(
            valid_db,
            user_id="user-1",
            puzzle_id="game-1_m1",
            puzzle=puzzle,
            played_uci="e2e4",
            time_taken_ms=2500,
            moves_tried=["d2d4", "I already knew the answer"],
            submission_id=SUBMISSION_A,
        )
    )
    stored = next(iter(valid_db.puzzle_attempts.documents.values()))

    assert invalid["quality"] == "invalid"
    assert invalid_db.puzzle_attempts.documents == {}
    assert valid["quality"] == "best"
    assert stored["moves_tried"] == ["e2e4"]
    assert stored["measurement"]["response_time_source"] == "client_reported"


def test_attempt_copies_server_rating_admission_and_unknown_assistance(monkeypatch):
    monkeypatch.setenv("COMPLETE_COACHING_SYSTEM_V1_ENABLED", "false")
    monkeypatch.setattr(attempt_service, "_rating_snapshot", _fixed_rating)
    db = _Db()
    puzzle = _specific_puzzle()

    result = asyncio.run(
        attempt_service.record_verified_puzzle_attempt(
            db,
            user_id="user-1",
            puzzle_id="game-1_m1",
            puzzle=puzzle,
            played_uci="e2e4",
            submission_id=SUBMISSION_A,
        )
    )
    document = next(iter(db.puzzle_attempts.documents.values()))

    assert result["shadow_event_emitted"] is False
    assert document["rating"] == {
        "value": 1187,
        "source": "recent_game_median",
        "platform": "chess.com",
        "sample_games": 3,
        "as_of": "2026-09-01T12:00:00+00:00",
    }
    assert (
        document["admission"]["verdict_fingerprint"]
        == puzzle["verified_admission"]["verdict_fingerprint"]
    )
    assert document["measurement"]["assistance"] == "not_measured"
    assert document["measurement"]["evidence_complete"] is False
    assert "assistance_and_reveal_state_not_measured" in (
        document["measurement"]["evidence_limitations"]
    )
