import asyncio
import inspect

from services import community_training_service as service
from services.skill_puzzle_extraction import grade_skill_puzzle_attempt
from services.verified_puzzle_admission import (
    AdmissionStatus,
    AdmissionVerdict,
)


class _Aggregate:
    async def to_list(self, _limit):
        return []


class _Collection:
    def __init__(self, document=None):
        self.document = document
        self.inserted = []
        self.updated = []

    async def find_one(self, _query, _projection=None):
        return self.document

    async def insert_one(self, document):
        self.inserted.append(document)

    async def update_one(self, query, update, **_kwargs):
        self.updated.append((query, update))
        return type("UpdateResult", (), {
            "upserted_id": "new-credit" if _kwargs.get("upsert") else None,
        })()

    def aggregate(self, _pipeline):
        return _Aggregate()


class _Db:
    def __init__(self, position):
        self.community_training_positions = _Collection(position)
        self.training_solve_attempts = _Collection()
        self.player_profiles = _Collection(None)
        self.puzzle_attempts = _Collection()
        self.puzzle_recovery_credits = _Collection()


def _position(accepted_moves):
    admission = AdmissionVerdict(
        status=AdmissionStatus.GENERIC,
        reason_codes=("generic_answer_verified",),
        source_kind="canonical_test",
        source_fingerprint="a" * 64,
        analysis_fingerprint="b" * 64,
        reconstructed_fen=(
            "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        ),
        played_move_uci="a2a3",
        acceptable_moves_uci=tuple(accepted_moves),
        concept_id=None,
        broad_category=None,
        detector_id=None,
        detector_version=None,
        verifier_id=None,
        verifier_version=None,
        quality_id=None,
        quality_grade=None,
    ).to_document()
    return {
        "position_id": "game-1_m1",
        "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        "best_move_san": "e4",
        "best_move_uci": "e2e4",
        "user_move_san": "a3",
        "pattern_type": "calculation_depth",
        "attempts": 0,
        "solves": 0,
        "pv_after_best": ["e7e5", "g1f3"],
        "pv_after_played": ["d7d5"],
        "verified_admission": admission,
    }


def test_solve_uses_stored_answer_set_and_stored_reply():
    db = _Db(_position(["e2e4"]))

    result = asyncio.run(
        service.record_solve_attempt(db, "user-1", "game-1_m1", "d4")
    )

    assert result["solved"] is False
    assert result["near_miss"] is False
    assert result["your_move_analysis"]["opponent_punishes"]["move"] == "d5"
    assert result["coaching_feedback"]["source"] == "verified_deterministic"
    assert db.training_solve_attempts.inserted[0]["solved"] is False


def test_unproved_alternative_is_not_accepted():
    db = _Db(_position(["e2e4"]))

    result = asyncio.run(
        service.record_solve_attempt(db, "user-1", "game-1_m1", "d4")
    )

    assert result["solved"] is False


def test_direct_community_grader_preserves_own_game_context():
    position = _position(["e2e4"])
    position["source_user_id"] = "user-1"
    db = _Db(position)

    result = asyncio.run(
        service.record_solve_attempt(db, "user-1", "game-1_m1", "e4")
    )

    assert result["coaching_feedback"]["source"] == "verified_deterministic"
    assert "own game" in result["coaching_feedback"]["feedback"].lower()


def test_generic_correct_solve_does_not_write_named_recovery_credit():
    position = _position(["e2e4"])
    position["pattern_type"] = "king_safety"
    db = _Db(position)

    result = asyncio.run(
        service.record_solve_attempt(db, "user-1", "game-1_m1", "e4")
    )

    assert result["solved"] is True
    assert db.puzzle_recovery_credits.updated == []
    assert db.puzzle_attempts.inserted[0]["weakness_type"] is None


def test_enforced_solve_rejects_incomplete_verdict_without_writing(monkeypatch):
    monkeypatch.setenv("VERIFIED_PUZZLE_ADMISSION_ENFORCED", "true")
    position = _position(["e2e4"])
    position["verified_admission"].pop("analysis_fingerprint")
    db = _Db(position)

    result = asyncio.run(
        service.record_solve_attempt(db, "user-1", "game-1_m1", "e4")
    )

    assert result == {"error": "This position is being checked and is not ready yet."}
    assert db.training_solve_attempts.inserted == []


def test_training_runtime_has_no_engine_or_llm_entry_point():
    source = inspect.getsource(service)
    assert "_get_stockfish_candidates" not in source
    assert "StockfishEngine" not in source
    assert "call_llm" not in source


def test_enforced_feed_rejects_unversioned_and_quarantined_rows(monkeypatch):
    monkeypatch.setenv("VERIFIED_PUZZLE_ADMISSION_ENFORCED", "true")
    good = _position(["e2e4"])
    quarantine = _position(["e2e4"])
    quarantine["position_id"] = "bad"
    quarantine["approved"] = False

    result = service._servable_positions([{}, quarantine, good], "calculation_depth", 10)

    assert [row["position_id"] for row in result] == ["game-1_m1"]


def test_stored_pv_parser_ignores_non_moves_and_returns_legal_reply():
    import chess

    board = chess.Board()
    board.push_uci("d2d4")
    assert service._first_legal_pv_move(board, [None, {"uci": "d7d5"}]) == "d5"


def test_shadow_skill_grading_fails_closed_until_promotion():
    admission = AdmissionVerdict(
        status=AdmissionStatus.SPECIFIC,
        reason_codes=("specific_proof_verified",),
        source_kind="canonical_test",
        source_fingerprint="a" * 64,
        analysis_fingerprint="b" * 64,
        reconstructed_fen=(
            "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        ),
        played_move_uci="a2a3",
        concept_id="endgame_rule_of_square",
        broad_category="endgame_technique",
        detector_id="canonical_rule_candidate",
        detector_version="v1",
        verifier_id="independent_race_verifier",
        verifier_version="v1",
        quality_id="curriculum:endgame_exact_position",
        quality_grade="plan",
        detector_facts=({"content_id": "king_and_pawn/square_rule"},),
        verifier_facts=({"content_id": "king_and_pawn/square_rule"},),
        acceptable_moves_uci=("e2e4",),
    ).to_document()

    correct = grade_skill_puzzle_attempt(
        fen_before="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        move_uci="e2e4",
        skill_id="endgame_rule_of_square",
        verified_admission=admission,
    )
    unrelated = grade_skill_puzzle_attempt(
        fen_before="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        move_uci="e2e4",
        skill_id="endgame_opposition",
        verified_admission=admission,
    )

    assert correct["correct"] is False
    assert correct["verdict"] == "unavailable"
    assert unrelated["correct"] is False
    assert unrelated["verdict"] == "unavailable"


def test_enforced_skill_grading_rejects_legacy_detector_fallback(monkeypatch):
    monkeypatch.setenv("VERIFIED_PUZZLE_ADMISSION_ENFORCED", "true")

    result = grade_skill_puzzle_attempt(
        fen_before="8/8/8/8/8/8/4P3/4K2k w - - 0 1",
        move_uci="e2e4",
        skill_id="endgame_rule_of_square",
    )

    assert result["correct"] is False
    assert result["verdict"] == "unavailable"
