from __future__ import annotations

import inspect

import chess

from services.detector_quality import QualitySurface, is_authorized
from services.verified_puzzle_admission import (
    AdmissionReason,
    AdmissionStatus,
    DetectorProof,
    PuzzleCandidate,
    StoredAnalysisEvidence,
    VerifierProof,
    adjudicate_puzzle,
    stored_verdict_is_structurally_current,
)


PGN = """[Event "Contract test"]
[Result "*"]

1. e4 e5 2. Nf3 Nc6 *
"""
START_FEN = chess.Board().fen()


def _candidate(**overrides):
    values = {
        "source_kind": "imported_game",
        "source_ref": "redacted-test-source",
        "source_pgn": PGN,
        "source_ply": 0,
        "stored_fen": START_FEN,
        "played_move": "e4",
        "analysis": StoredAnalysisEvidence(
            played_move="e4", best_move="e4", cp_loss=0
        ),
    }
    values.update(overrides)
    return PuzzleCandidate(**values)


def _proofs(
    *,
    detector_move="e4",
    verifier_move="e4",
    verifier_verified=True,
    same_calculation=False,
):
    detector = DetectorProof(
        concept_id="piece_safety.simple_hang",
        family="piece_safety",
        detector_id="observation.simple_hang",
        detector_version="v17",
        calculation_id="candidate.before_after",
        acceptable_moves=(detector_move,),
        facts=({"piece": "pawn", "square": "e4"},),
    )
    verifier = VerifierProof(
        concept_id="piece_safety.simple_hang",
        verifier_id="legal_exchange_verifier",
        verifier_version="v1",
        calculation_id=(
            "candidate.before_after" if same_calculation else "legal_reply_tree"
        ),
        verified=verifier_verified,
        acceptable_moves=(verifier_move,),
        facts=({"legal": True},),
    )
    return detector, verifier


def test_valid_stored_answer_becomes_generic_without_concept_proof():
    verdict = adjudicate_puzzle(_candidate())

    assert verdict.status == AdmissionStatus.GENERIC
    assert verdict.reason_codes == (AdmissionReason.GENERIC_ANSWER_VERIFIED.value,)
    assert verdict.acceptable_moves_uci == ("e2e4",)
    assert verdict.concept_id is None
    assert "caption_concept_id" not in verdict.to_document()


def test_caption_grade_fact_stays_broad_and_cannot_become_prompt_identity():
    detector, verifier = _proofs()
    verdict = adjudicate_puzzle(_candidate(
        broad_category="piece_safety",
        quality_id="gap:piece_safety:simple_hang",
        detector_proof=detector,
        verifier_proof=verifier,
    ))

    assert verdict.status == AdmissionStatus.BROAD
    assert verdict.concept_id is None
    # Caption facts may explain a completed attempt, but the Prompt-grade
    # concept identity remains absent from the drill contract.
    assert not is_authorized("gap:piece_safety:simple_hang", QualitySurface.PROMPT)
    assert verdict.quality_grade == "caption"
    assert verdict.caption_concept_id == "piece_safety.simple_hang"
    assert verdict.to_document()["caption_concept_id"] == (
        "piece_safety.simple_hang"
    )
    assert verdict.reason_codes == (
        AdmissionReason.CAPTION_PROOF_VERIFIED.value,
        AdmissionReason.BROAD_CATEGORY_VERIFIED.value,
    )
    assert verdict.detector_id != verdict.verifier_id
    assert verdict.detector_facts == ({"piece": "pawn", "square": "e4"},)
    assert verdict.verifier_facts == ({"legal": True},)


def test_unknown_detector_fails_closed_to_broad_even_when_proof_matches():
    detector, verifier = _proofs()
    verdict = adjudicate_puzzle(_candidate(
        broad_category="piece_safety",
        quality_id="unknown:unreviewed",
        detector_proof=detector,
        verifier_proof=verifier,
    ))

    assert verdict.status == AdmissionStatus.BROAD
    assert verdict.concept_id is None
    assert AdmissionReason.SPECIFIC_PROOF_UNAUTHORIZED.value in verdict.reason_codes


def test_detector_cannot_verify_itself_with_same_calculation():
    detector, verifier = _proofs(same_calculation=True)
    verdict = adjudicate_puzzle(_candidate(
        broad_category="piece_safety",
        quality_id="gap:piece_safety:simple_hang",
        detector_proof=detector,
        verifier_proof=verifier,
    ))

    assert verdict.status == AdmissionStatus.BROAD
    assert AdmissionReason.SPECIFIC_PROOF_MISMATCH.value in verdict.reason_codes


def test_detector_and_verifier_answer_disagreement_downgrades():
    detector, verifier = _proofs(detector_move="e4", verifier_move="d4")
    verdict = adjudicate_puzzle(_candidate(
        broad_category="opening",
        quality_id="gap:piece_safety:simple_hang",
        detector_proof=detector,
        verifier_proof=verifier,
    ))

    assert verdict.status == AdmissionStatus.BROAD
    assert AdmissionReason.ANSWER_SET_MISMATCH.value in verdict.reason_codes


def test_disagreeing_detector_answer_never_enters_accepted_set():
    detector, verifier = _proofs(detector_move="d4", verifier_move="c4")
    verdict = adjudicate_puzzle(_candidate(
        broad_category="opening",
        quality_id="gap:piece_safety:simple_hang",
        detector_proof=detector,
        verifier_proof=verifier,
    ))

    assert verdict.status == AdmissionStatus.BROAD
    assert verdict.acceptable_moves_uci == ("e2e4",)


def test_specific_proof_requires_both_sides_to_name_the_same_answer():
    detector, verifier = _proofs(verifier_move="")
    verdict = adjudicate_puzzle(_candidate(
        broad_category="piece_safety",
        quality_id="gap:piece_safety:simple_hang",
        detector_proof=detector,
        verifier_proof=verifier,
    ))

    assert verdict.status == AdmissionStatus.BROAD
    assert AdmissionReason.ANSWER_SET_MISMATCH.value in verdict.reason_codes


def test_specific_proof_must_include_the_stored_best_move():
    detector, verifier = _proofs(detector_move="d4", verifier_move="d4")
    verdict = adjudicate_puzzle(_candidate(
        broad_category="piece_safety",
        quality_id="gap:piece_safety:simple_hang",
        detector_proof=detector,
        verifier_proof=verifier,
    ))

    assert verdict.status == AdmissionStatus.BROAD
    assert verdict.acceptable_moves_uci == ("e2e4",)
    assert AdmissionReason.ANSWER_SET_MISMATCH.value in verdict.reason_codes


def test_wrong_source_move_is_quarantined_not_relabelled():
    verdict = adjudicate_puzzle(_candidate(played_move="d4"))

    assert verdict.status == AdmissionStatus.QUARANTINE
    assert verdict.reason_codes == (AdmissionReason.SOURCE_MOVE_MISMATCH.value,)


def test_stored_board_mismatch_is_quarantined():
    board = chess.Board()
    board.push_san("e4")
    verdict = adjudicate_puzzle(_candidate(stored_fen=board.fen()))

    assert verdict.status == AdmissionStatus.QUARANTINE
    assert verdict.reason_codes == (AdmissionReason.STORED_FEN_MISMATCH.value,)


def test_illegal_best_move_is_quarantined():
    verdict = adjudicate_puzzle(_candidate(
        analysis=StoredAnalysisEvidence(
            played_move="e4", best_move="e5", cp_loss=0
        )
    ))

    assert verdict.status == AdmissionStatus.QUARANTINE
    assert verdict.reason_codes == (AdmissionReason.BEST_MOVE_ILLEGAL.value,)


def test_no_answer_or_verified_acceptable_set_is_quarantined():
    verdict = adjudicate_puzzle(_candidate(
        analysis=StoredAnalysisEvidence(played_move="e4", cp_loss=0)
    ))

    assert verdict.status == AdmissionStatus.QUARANTINE
    assert verdict.reason_codes == (AdmissionReason.NO_VERIFIED_ANSWER.value,)


def test_fen_clock_fields_do_not_create_false_source_mismatch():
    altered_clocks = START_FEN.rsplit(" ", 2)[0] + " 42 99"
    verdict = adjudicate_puzzle(_candidate(stored_fen=altered_clocks))

    assert verdict.status == AdmissionStatus.GENERIC


def test_same_inputs_produce_same_fingerprints_and_document():
    first = adjudicate_puzzle(_candidate()).to_document()
    second = adjudicate_puzzle(_candidate()).to_document()

    assert first == second


def test_persisted_contract_accepts_generated_verdict_and_rejects_tampering():
    document = adjudicate_puzzle(_candidate()).to_document()
    puzzle = {"fen": START_FEN, "verified_admission": document}
    assert stored_verdict_is_structurally_current(puzzle) is True

    tampered = {"fen": START_FEN, "verified_admission": dict(document)}
    tampered["verified_admission"]["acceptable_moves_uci"] = ["e7e5"]
    assert stored_verdict_is_structurally_current(tampered) is False


def test_runtime_core_has_no_engine_llm_or_network_dependency():
    import services.verified_puzzle_admission as module

    source = inspect.getsource(module).lower()
    forbidden = (
        "import stockfish",
        "chess.engine",
        "call_llm",
        "openai",
        "anthropic",
        "requests.",
        "httpx",
        "subprocess",
    )
    assert not [token for token in forbidden if token in source]
