from pathlib import Path

import chess

from services import free_piece_puzzle_proof as proof_module
from services.free_piece_puzzle_proof import (
    FREE_PIECE_QUALITY_ID,
    build_free_piece_proof,
)
from services.verified_puzzle_admission import AdmissionStatus
from services.verified_puzzle_builder import build_position_verdict


FREE_ROOK_FEN = "7k/5r2/8/8/2B5/8/8/7K w - - 0 1"


def test_exact_unrecapturable_minor_or_larger_capture_is_verified():
    proof = build_free_piece_proof(
        chess.Board(FREE_ROOK_FEN), "Bb3", "Bxf7", 200
    )
    assert proof is not None
    assert proof.verifier.verified is True
    assert proof.detector.concept_id == "tactic.free_piece"
    assert proof.verifier.facts[0]["captured_piece"] == "rook"
    assert proof.verifier.facts[0]["recaptures"] == ()


def test_candidate_cannot_self_verify_when_a_legal_recapture_exists(monkeypatch):
    defended = chess.Board("6k1/5r2/8/8/2B5/8/8/7K w - - 0 1")
    monkeypatch.setattr(
        proof_module,
        "detect_free_piece",
        lambda _board: [{
            "mover": "c4",
            "targets": ["f7"],
            "executing_move": "c4f7",
        }],
    )
    proof = build_free_piece_proof(defended, "Bb3", "Bxf7+", 200)
    assert proof is not None
    assert proof.verifier.verified is False


def test_shared_builder_keeps_verified_free_piece_broad_until_promotion():
    verdict = build_position_verdict(
        source_kind="free_piece_fixture",
        source_ref="free-rook",
        move_evaluation={
            "fen_before": FREE_ROOK_FEN,
            "move": "Bb3",
            "best_move_san": "Bxf7",
            "cp_loss": 200,
        },
        broad_category="missed_tactic",
    )
    assert verdict.status == AdmissionStatus.BROAD
    assert verdict.quality_id == FREE_PIECE_QUALITY_ID
    assert verdict.acceptable_moves_uci == ("c4f7",)
    assert verdict.concept_id is None
    assert "specific_proof_unauthorized" in verdict.reason_codes


def test_free_piece_proof_requires_meaningful_stored_consequence():
    assert build_free_piece_proof(
        chess.Board(FREE_ROOK_FEN), "Bb3", "Bxf7", 99
    ) is None


def test_free_piece_proof_has_no_runtime_engine_llm_or_network_dependency():
    source = (
        Path(__file__).resolve().parents[1]
        / "services"
        / "free_piece_puzzle_proof.py"
    ).read_text(encoding="utf-8")
    forbidden = (
        "StockfishEngine",
        "stockfish_service",
        "call_llm",
        "httpx",
        "requests.",
    )
    assert not any(token in source for token in forbidden)
