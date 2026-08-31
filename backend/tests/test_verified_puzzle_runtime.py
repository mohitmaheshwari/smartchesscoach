import asyncio
import inspect

from services import verified_puzzle_runtime as runtime
from services.verified_puzzle_admission import (
    ADMISSION_VERSION,
    AdmissionStatus,
    AdmissionVerdict,
)


START = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"


def _admission(accepted=("e2e4",), *, specific=False, **overrides):
    values = {
        "status": AdmissionStatus.SPECIFIC if specific else AdmissionStatus.GENERIC,
        "reason_codes": (
            "specific_proof_verified" if specific else "generic_answer_verified",
        ),
        "source_kind": "canonical_test",
        "source_fingerprint": "a" * 64,
        "analysis_fingerprint": "b" * 64,
        "reconstructed_fen": START,
        "played_move_uci": "e2e4",
        "acceptable_moves_uci": tuple(accepted),
        "concept_id": "tactic.fork" if specific else None,
        "broad_category": "missed_tactic" if specific else None,
        "detector_id": "candidate_fork" if specific else None,
        "detector_version": "v1" if specific else None,
        "verifier_id": "independent_fork" if specific else None,
        "verifier_version": "v1" if specific else None,
        "quality_id": "tactic:fork_with_stored_payoff" if specific else None,
        "quality_grade": "plan" if specific else None,
        "detector_facts": ({"candidate": True},) if specific else (),
        "verifier_facts": ({"verified": True},) if specific else (),
    }
    values.update(overrides)
    return AdmissionVerdict(**values).to_document()


def _resolved(accepted=("e2e4",), *, specific=False):
    return {
        "fen": START,
        "best_move_san": "e4",
        "best_move_uci": "e2e4",
        "pattern_type": "calculation_depth",
        "verified_admission": _admission(accepted, specific=specific),
    }


def test_grade_uses_frozen_answer_set_and_not_client_claims():
    correct = runtime.grade_resolved_puzzle(_resolved(), "e2e4")
    wrong = runtime.grade_resolved_puzzle(_resolved(), "d2d4")

    assert correct["correct"] is True
    assert correct["quality"] == "best"
    assert wrong["correct"] is False
    assert wrong["quality"] == "mistake"
    assert correct["source"] == "verified_stored_evidence"


def test_generic_grade_cannot_repeat_an_unverified_legacy_weakness():
    puzzle = _resolved()
    puzzle["pattern_type"] = "king_safety"

    result = runtime.grade_resolved_puzzle(puzzle, "e2e4")

    assert result["pattern_type"] == "calculation_depth"
    assert result["recovery_weakness"] is None


def test_broad_grade_uses_only_the_verified_broad_category():
    puzzle = _resolved()
    puzzle["verified_admission"] = _admission(
        status=AdmissionStatus.BROAD,
        reason_codes=("broad_category_verified",),
        broad_category="missed_tactic",
    )
    puzzle["pattern_type"] = "king_safety"

    result = runtime.grade_resolved_puzzle(puzzle, "e2e4")

    assert result["pattern_type"] == "missed_tactic"
    assert result["recovery_weakness"] == "missed_tactic"


def test_shadow_specific_alternative_is_not_player_gradeable():
    puzzle = _resolved(("e2e4", "d2d4"), specific=True)
    puzzle["verified_admission"] = _admission(
        ("e2e4", "d2d4"),
        specific=True,
        concept_id="piece_safety.simple_hang",
        broad_category="piece_safety",
        detector_id="simple_hang_candidate",
        verifier_id="simple_hang_independent_verifier",
        quality_id="gap:piece_safety:simple_hang",
        quality_grade="shadow",
    )
    result = runtime.grade_resolved_puzzle(puzzle, "d2d4")

    assert result == {
        "quality": "invalid",
        "feedback": "This puzzle needs verification.",
    }


def test_grade_rejects_illegal_move_and_unversioned_row():
    assert runtime.grade_resolved_puzzle(_resolved(), "e7e5")["quality"] == "invalid"
    assert runtime.grade_resolved_puzzle({"fen": START}, "e2e4")["quality"] == "invalid"


def test_stored_primary_move_must_belong_to_the_accepted_set():
    puzzle = _resolved(("d2d4",))

    assert runtime.stored_verdict_is_structurally_current(puzzle) is False
    assert runtime.grade_resolved_puzzle(puzzle, "d2d4")["quality"] == "invalid"


def test_current_version_alone_cannot_masquerade_as_verified():
    incomplete = {
        "fen": START,
        "verified_admission": {
            "admission_version": ADMISSION_VERSION,
            "status": "generic",
            "acceptable_moves_uci": ["e2e4"],
        },
    }
    assert runtime.stored_verdict_is_structurally_current(incomplete) is False
    assert runtime.grade_resolved_puzzle(incomplete, "e2e4")["quality"] == "invalid"


def test_specific_verdict_requires_independent_named_proof_identities():
    incomplete = _resolved(specific=True)
    incomplete["verified_admission"] = _admission(
        specific=True,
        detector_id="same",
        verifier_id="same",
    )
    assert runtime.stored_verdict_is_structurally_current(incomplete) is False


def test_specific_verdict_cannot_outlive_quality_authorization():
    puzzle = _resolved(specific=True)
    puzzle["verified_admission"] = _admission(
        specific=True,
        concept_id="tactic.unknown",
        quality_id="unknown:not_authorized",
        quality_grade="shadow",
    )

    assert runtime.stored_verdict_is_structurally_current(puzzle) is False


def test_legal_answer_tampering_invalidates_content_bound_verdict():
    puzzle = _resolved()
    puzzle["verified_admission"]["acceptable_moves_uci"] = ["d2d4"]
    puzzle["best_move_uci"] = "d2d4"
    puzzle["best_move_san"] = "d4"

    assert runtime.stored_verdict_is_structurally_current(puzzle) is False
    assert runtime.grade_resolved_puzzle(puzzle, "d2d4")["quality"] == "invalid"


def test_public_payload_recursively_removes_answers_and_proof_internals():
    public = runtime.public_puzzle_payload({
        "puzzle_id": "p1",
        "fen": START,
        "best_move_uci": "e2e4",
        "nested": {
            "solution": ["e2e4"],
            "answer_hint": "e4",
            "safe_context": "Find a developing move.",
        },
        "verified_admission": _admission(),
    })

    assert public == {
        "puzzle_id": "p1",
        "fen": START,
        "nested": {"safe_context": "Find a developing move."},
    }


class _Collection:
    def __init__(self, document):
        self.document = document

    async def find_one(self, _query, _projection=None):
        return self.document


class _Db:
    community_training_positions = _Collection(None)
    community_puzzles = _Collection(None)
    games = _Collection({
        "game_id": "g",
        "user_id": "u",
        "user_color": "white",
        "pgn": '[Result "*"]\n\n1. d4 d5 *',
    })
    game_analyses = _Collection({
        "game_id": "g",
        "user_id": "u",
        "stockfish_analysis": {
            "move_evaluations": [{
                "move_number": 1,
                "fen_before": START,
                "move": "d4",
                "best_move": "e4",
                "best_move_uci": "e2e4",
                "cp_loss": 120,
            }]
        },
    })
    lichess_puzzles = _Collection(None)


def test_dynamic_own_game_id_reconstructs_canonical_pgn():
    puzzle = asyncio.run(
        runtime.resolve_verified_puzzle(_Db(), "g_m1", user_id="u")
    )

    assert puzzle is not None
    assert puzzle["verified_admission"]["status"] == "generic"
    assert puzzle["best_move_uci"] == "e2e4"


def test_pool_resolution_preserves_server_owned_personal_context():
    own = _resolved()
    own["shared_by"] = "user-1"
    community = _resolved()
    community["shared_by"] = "someone-else"

    own_result = asyncio.run(
        runtime._resolve_pool_row(None, own, user_id="user-1")
    )
    community_result = asyncio.run(
        runtime._resolve_pool_row(None, community, user_id="user-1")
    )

    assert own_result["source"] == "your_game"
    assert community_result.get("source") != "your_game"


def test_pool_resolution_never_overrides_a_prior_quality_rejection():
    rejected = _resolved()
    rejected["approved"] = False

    result = asyncio.run(runtime._resolve_pool_row(None, rejected, user_id="user-1"))

    assert result is None


def test_runtime_module_has_no_engine_llm_or_network_entry_point():
    source = inspect.getsource(runtime)
    for forbidden in (
        "StockfishEngine",
        "_get_stockfish_candidates",
        "call_llm",
        "requests.",
        "httpx.",
    ):
        assert forbidden not in source
