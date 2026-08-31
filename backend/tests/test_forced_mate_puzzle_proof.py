from pathlib import Path

import chess

from services.forced_mate_puzzle_proof import (
    FORCED_MATE_QUALITY_ID,
    build_forced_mate_proof,
)
from services.verified_puzzle_admission import AdmissionStatus
from services.verified_puzzle_builder import build_position_verdict


MATE_BOARD = "6k1/5ppp/8/8/8/8/5PPP/R6K w - - 0 1"


def test_mate_in_one_is_independently_replayed():
    proof = build_forced_mate_proof(
        chess.Board(MATE_BOARD), "Ra8", (), 500
    )
    assert proof is not None
    assert proof.verifier.verified is True
    assert proof.detector.concept_id == "tactic.mate_in_one"


def test_forced_mate_pv_may_include_or_omit_best_move():
    board = chess.Board(MATE_BOARD)
    included = build_forced_mate_proof(
        board, "Kg1", ("Kg1", "Kh8", "Ra8#"), 300
    )
    omitted = build_forced_mate_proof(
        board, "Kg1", ("Kh8", "Ra8#"), 300
    )
    assert included is not None and included.verifier.verified
    assert omitted is not None and omitted.verifier.verified
    assert included.detector.concept_id == "tactic.forced_mate"


def test_marker_free_uci_line_is_recognized_only_by_terminal_mate():
    proof = build_forced_mate_proof(
        chess.Board(MATE_BOARD),
        "h1g1",
        ("g8h8", "a1a8"),
        300,
    )
    assert proof is not None
    assert proof.verifier.verified is True
    assert proof.detector.concept_id == "tactic.forced_mate"


def test_mate_marker_with_illegal_line_fails_independent_verification():
    proof = build_forced_mate_proof(
        chess.Board(MATE_BOARD), "Kg1", ("Kg1", "Qa5", "Ra8#"), 300
    )
    assert proof is not None
    assert proof.verifier.verified is False


def test_shared_builder_keeps_verified_mate_broad_until_promotion():
    non_back_rank_mate = "7k/8/5KQ1/8/8/8/8/8 w - - 0 1"
    verdict = build_position_verdict(
        source_kind="mate_fixture",
        source_ref="mate-1",
        move_evaluation={
            "fen_before": non_back_rank_mate,
            "move": "Qg5",
            "best_move_san": "Qg7#",
            "cp_loss": 500,
            "pv_after_best": [],
        },
        broad_category="missed_tactic",
    )
    assert verdict.status == AdmissionStatus.BROAD
    assert verdict.quality_id == FORCED_MATE_QUALITY_ID
    assert verdict.concept_id is None
    assert "specific_proof_unauthorized" in verdict.reason_codes


def test_forced_mate_proof_has_no_runtime_engine_llm_or_network_dependency():
    source = (
        Path(__file__).resolve().parents[1]
        / "services"
        / "forced_mate_puzzle_proof.py"
    ).read_text(encoding="utf-8")
    forbidden = (
        "StockfishEngine",
        "stockfish_service",
        "call_llm",
        "httpx",
        "requests.",
    )
    assert not any(token in source for token in forbidden)
