from pathlib import Path

import chess

from services.removal_defender_puzzle_proof import (
    REMOVAL_QUALITY_ID,
    build_removal_defender_proof,
)
from services.verified_puzzle_admission import AdmissionStatus
from services.verified_puzzle_builder import build_position_verdict


REMOVAL_FEN = "4k3/7p/4b3/8/2r5/1B6/8/4R2K w - - 0 1"
PAYOFF_LINE = ("Rxe6+", "Kf7", "Bxc4")


def test_sole_defender_removal_exposes_and_wins_exact_target():
    proof = build_removal_defender_proof(
        chess.Board(REMOVAL_FEN),
        "Rd1",
        "Rxe6+",
        PAYOFF_LINE,
        300,
    )
    assert proof is not None and proof.verifier.verified
    assert proof.detector.concept_id == "tactic.removal_of_defender"
    assert proof.verifier.facts[0]["defender_square"] == "e6"
    assert proof.verifier.facts[0]["target_square"] == "c4"


def test_removing_guard_without_capturing_exposed_target_is_not_enough():
    proof = build_removal_defender_proof(
        chess.Board(REMOVAL_FEN),
        "Rd1",
        "Rxe6+",
        ("Rxe6+", "Kf7"),
        300,
    )
    assert proof is not None
    assert proof.verifier.verified is False


def test_exposed_target_cannot_move_away_before_the_claimed_payoff():
    board = chess.Board("6k1/7p/4b3/8/2r5/1B6/8/4R2K w - - 0 1")
    proof = build_removal_defender_proof(
        board,
        "Rd1",
        "Rxe6",
        ("Rc5", "Kg2"),
        300,
    )
    assert proof is not None
    assert proof.verifier.verified is False


def test_shared_builder_keeps_verified_removal_broad_until_promotion():
    verdict = build_position_verdict(
        source_kind="removal_fixture",
        source_ref="sole-guard",
        move_evaluation={
            "fen_before": REMOVAL_FEN,
            "move": "Rd1",
            "best_move_san": "Rxe6+",
            "cp_loss": 300,
            "pv_after_best": list(PAYOFF_LINE),
        },
        broad_category="missed_tactic",
    )
    assert verdict.status == AdmissionStatus.BROAD
    assert verdict.quality_id == REMOVAL_QUALITY_ID
    assert verdict.concept_id is None
    assert "specific_proof_unauthorized" in verdict.reason_codes


def test_removal_proof_has_no_runtime_engine_llm_or_network_dependency():
    source = (
        Path(__file__).resolve().parents[1]
        / "services"
        / "removal_defender_puzzle_proof.py"
    ).read_text(encoding="utf-8")
    forbidden = (
        "StockfishEngine",
        "stockfish_service",
        "call_llm",
        "httpx",
        "requests.",
    )
    assert not any(token in source for token in forbidden)
