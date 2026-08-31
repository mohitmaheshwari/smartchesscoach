from pathlib import Path

import chess

from services.discovered_attack_puzzle_proof import (
    DISCOVERED_ATTACK_QUALITY_ID,
    build_discovered_attack_proof,
)
from services.verified_puzzle_admission import AdmissionStatus
from services.verified_puzzle_builder import build_position_verdict


DISCOVERY_BOARD = "n5k1/8/8/8/8/8/B7/R5K1 w - - 0 1"


def test_vacated_ray_with_exact_stored_slider_payoff_is_verified():
    proof = build_discovered_attack_proof(
        chess.Board(DISCOVERY_BOARD),
        "Kh2",
        "Bb3+",
        ("Kh8", "Rxa8"),
        500,
    )
    assert proof is not None
    assert proof.verifier.verified is True
    assert proof.detector.concept_id == "tactic.discovered_attack"

    verdict = build_position_verdict(
        source_kind="canonical_test",
        source_ref="discovered-attack",
        move_evaluation={
            "fen_before": DISCOVERY_BOARD,
            "move": "Kh2",
            "best_move_san": "Bb3+",
            "cp_loss": 500,
            "pv_after_best": ["Kh8", "Rxa8"],
        },
        broad_category="missed_tactic",
    )
    assert verdict.status == AdmissionStatus.BROAD
    assert verdict.quality_id == DISCOVERED_ATTACK_QUALITY_ID
    assert verdict.concept_id is None
    assert "specific_proof_unauthorized" in verdict.reason_codes


def test_geometry_without_stored_target_capture_stays_unverified():
    proof = build_discovered_attack_proof(
        chess.Board(DISCOVERY_BOARD),
        "Kh2",
        "Bb3+",
        ("Kh8",),
        500,
    )
    assert proof is not None
    assert proof.verifier.verified is False


def test_moved_target_and_replacement_on_the_square_cannot_fake_payoff():
    board = chess.Board("nr4k1/8/8/8/8/8/B7/R5K1 w - - 0 1")
    proof = build_discovered_attack_proof(
        board,
        "Kh2",
        "Bb1",
        ("Nb6", "Kg2", "Ra8", "Rxa8"),
        500,
    )
    assert proof is not None
    assert proof.verifier.verified is False


def test_discovered_attack_proof_has_no_runtime_engine_llm_or_network_dependency():
    source = (
        Path(__file__).resolve().parents[1]
        / "services"
        / "discovered_attack_puzzle_proof.py"
    ).read_text(encoding="utf-8")
    forbidden = ("StockfishEngine", "stockfish_service", "call_llm", "httpx", "requests.")
    assert not any(token in source for token in forbidden)
