from pathlib import Path

import chess

from services.trapped_piece_puzzle_proof import (
    TRAPPED_PIECE_QUALITY_ID,
    build_trapped_piece_proof,
)
from services.verified_puzzle_admission import AdmissionStatus
from services.verified_puzzle_builder import build_position_verdict


MOVE_CAUSALITY_FEN = (
    "3rkb1r/2p3p1/p7/Qp2p3/2b5/4B3/P1q2KPP/4R2R w k - 0 23"
)


def test_every_escape_loses_and_best_avoids_the_trapped_bishop():
    proof = build_trapped_piece_proof(
        chess.Board(MOVE_CAUSALITY_FEN), "Bd2", "Kg1", 9287
    )
    assert proof is not None
    assert proof.verifier.verified is True
    assert proof.detector.concept_id == "piece_safety.trapped_piece"

    verdict = build_position_verdict(
        source_kind="canonical_test",
        source_ref="trapped-bishop",
        move_evaluation={
            "fen_before": MOVE_CAUSALITY_FEN,
            "move": "Bd2",
            "best_move_san": "Kg1",
            "cp_loss": 9287,
        },
        broad_category="piece_safety",
    )
    assert verdict.status == AdmissionStatus.BROAD
    assert verdict.quality_id == TRAPPED_PIECE_QUALITY_ID
    assert verdict.concept_id is None
    assert "specific_proof_unauthorized" in verdict.reason_codes


def test_low_consequence_does_not_become_a_trapped_piece_lesson():
    assert build_trapped_piece_proof(
        chess.Board(MOVE_CAUSALITY_FEN), "Bd2", "Kg1", 20
    ) is None


def test_trapped_piece_proof_has_no_runtime_engine_llm_or_network_dependency():
    source = (
        Path(__file__).resolve().parents[1]
        / "services"
        / "trapped_piece_puzzle_proof.py"
    ).read_text(encoding="utf-8")
    forbidden = ("StockfishEngine", "stockfish_service", "call_llm", "httpx", "requests.")
    assert not any(token in source for token in forbidden)
