from pathlib import Path

import chess

from services.fork_puzzle_proof import (
    FORK_QUALITY_ID,
    build_fork_proof,
)
from services.verified_puzzle_admission import AdmissionStatus
from services.verified_puzzle_builder import build_position_verdict


PAWN_FORK_FEN = (
    "rnb1k2r/pp3ppp/2pqpn2/3p4/3PP3/2PB1N2/"
    "P1P2PPP/1RBQ1RK1 w kq - 3 9"
)
PAYOFF_LINE = ("e5", "Qd7", "exf6")


def test_pawn_fork_requires_geometry_and_legal_material_payoff():
    proof = build_fork_proof(
        chess.Board(PAWN_FORK_FEN),
        "h3",
        "e5",
        PAYOFF_LINE,
        200,
    )
    assert proof is not None
    assert proof.verifier.verified is True
    assert proof.detector.concept_id == "tactic.pawn_fork"
    assert proof.verifier.facts[0]["targets"] == ("d6", "f6")
    assert proof.verifier.facts[0]["net_material_gain_cp"] == 300


def test_fork_shape_without_stored_payoff_does_not_self_verify():
    proof = build_fork_proof(
        chess.Board(PAWN_FORK_FEN),
        "h3",
        "e5",
        ("e5", "Qd7"),
        200,
    )
    assert proof is not None
    assert proof.verifier.verified is False


def test_illegal_stored_payoff_line_is_rejected():
    proof = build_fork_proof(
        chess.Board(PAWN_FORK_FEN),
        "h3",
        "e5",
        ("e5", "Qa5", "exf6"),
        200,
    )
    assert proof is not None
    assert proof.verifier.verified is False


def test_material_gain_elsewhere_does_not_prove_the_fork_paid_off():
    proof = build_fork_proof(
        chess.Board(PAWN_FORK_FEN),
        "h3",
        "e5",
        ("e5", "Qd7", "Bxh7"),
        200,
    )
    assert proof is not None
    assert proof.verifier.verified is False


def test_shared_builder_keeps_verified_fork_broad_until_promotion():
    verdict = build_position_verdict(
        source_kind="fork_fixture",
        source_ref="pawn-fork",
        move_evaluation={
            "fen_before": PAWN_FORK_FEN,
            "move": "h3",
            "best_move_san": "e5",
            "cp_loss": 200,
            "pv_after_best": list(PAYOFF_LINE),
        },
        broad_category="missed_tactic",
    )
    assert verdict.status == AdmissionStatus.BROAD
    assert verdict.quality_id == FORK_QUALITY_ID
    assert verdict.concept_id is None
    assert "specific_proof_unauthorized" in verdict.reason_codes


def test_fork_proof_has_no_runtime_engine_llm_or_network_dependency():
    source = (
        Path(__file__).resolve().parents[1]
        / "services"
        / "fork_puzzle_proof.py"
    ).read_text(encoding="utf-8")
    forbidden = (
        "StockfishEngine",
        "stockfish_service",
        "call_llm",
        "httpx",
        "requests.",
    )
    assert not any(token in source for token in forbidden)
