from __future__ import annotations

import inspect

import chess
import pytest

from services.piece_safety_puzzle_proof import (
    PIECE_SAFETY_QUALITY_ID,
    build_piece_safety_proof,
)
from services.verified_puzzle_admission import (
    AdmissionStatus,
    PuzzleCandidate,
    StoredAnalysisEvidence,
    adjudicate_puzzle,
)


MOVED_HANG_FEN = "r1b1kbnr/pp3ppp/8/q1pPp3/2BnP3/2N1B3/PP3PPP/R2QK1NR w KQkq - 2 8"
OTHER_HANG_FEN = "rnbqk2r/1p2bppp/p2ppn2/2p1P3/2B5/P1NP1N2/1PP2PPP/R1BQK2R b KQkq - 0 7"
PAWN_ONLY_FEN = "7k/7b/8/8/8/8/3P4/7K w - - 0 1"


def test_moved_piece_hang_produces_matching_independent_proof():
    bundle = build_piece_safety_proof(
        chess.Board(MOVED_HANG_FEN), "Bxd4", "f4", 470
    )

    assert bundle is not None
    assert bundle.quality_id == PIECE_SAFETY_QUALITY_ID
    assert bundle.verifier.verified
    assert bundle.detector.detector_id != bundle.verifier.verifier_id
    assert bundle.detector.calculation_id != bundle.verifier.calculation_id
    assert bundle.detector.facts[0]["piece"] == "bishop"
    assert bundle.detector.facts[0]["square"] == "d4"
    assert bundle.verifier.facts[0]["material_loss_cp"] >= 150


def test_other_piece_exposure_is_proved_not_only_destination_square():
    bundle = build_piece_safety_proof(
        chess.Board(OTHER_HANG_FEN), "O-O", "dxe5", 494
    )

    assert bundle is not None
    assert bundle.verifier.verified
    assert bundle.detector.counterfactual["subtype"] == "other_piece"
    assert any(fact["square"] == "f6" for fact in bundle.verifier.facts)


def test_low_consequence_or_pawn_only_case_abstains():
    assert build_piece_safety_proof(
        chess.Board(MOVED_HANG_FEN), "Bxd4", "f4", 99
    ) is None


@pytest.mark.parametrize("bad_loss", [-470, float("nan"), float("inf"), "bad"])
def test_invalid_cp_loss_fails_closed_before_specific_admission(bad_loss):
    assert build_piece_safety_proof(
        chess.Board(MOVED_HANG_FEN), "Bxd4", "f4", bad_loss
    ) is None
    assert build_piece_safety_proof(
        chess.Board(PAWN_ONLY_FEN), "Kg1", "d4", 200
    ) is None


def test_verified_bundle_stays_broad_until_blind_quality_promotion():
    bundle = build_piece_safety_proof(
        chess.Board(MOVED_HANG_FEN), "Bxd4", "f4", 470
    )
    assert bundle is not None

    verdict = adjudicate_puzzle(PuzzleCandidate(
        source_kind="canonical_test",
        source_ref="piece-safety-gold",
        source_position_fen=MOVED_HANG_FEN,
        stored_fen=MOVED_HANG_FEN,
        played_move="Bxd4",
        analysis=StoredAnalysisEvidence(
            played_move="Bxd4", best_move="f4", cp_loss=470
        ),
        broad_category="piece_safety",
        quality_id=bundle.quality_id,
        detector_proof=bundle.detector,
        verifier_proof=bundle.verifier,
    ))

    assert verdict.status == AdmissionStatus.BROAD
    assert verdict.concept_id is None
    assert verdict.broad_category == "piece_safety"
    assert verdict.acceptable_moves_uci == ("f2f4",)


def test_piece_safety_proof_runtime_has_no_stockfish_llm_or_network_call():
    import services.piece_safety_puzzle_proof as module

    source = inspect.getsource(module).lower()
    forbidden = (
        "import stockfish", "chess.engine", "call_llm", "openai",
        "anthropic", "requests.", "httpx", "subprocess",
    )
    assert not [token for token in forbidden if token in source]
