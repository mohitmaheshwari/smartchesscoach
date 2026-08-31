from pathlib import Path

import chess

from services.back_rank_mate_puzzle_proof import (
    BACK_RANK_MATE_QUALITY_ID,
    build_back_rank_mate_proof,
)
from services.verified_puzzle_admission import AdmissionStatus
from services.verified_puzzle_builder import build_position_verdict


def test_exact_back_rank_proof_stays_broad_until_promotion():
    fen = "6k1/5ppp/8/8/8/8/8/4R1K1 w - - 0 1"
    board = chess.Board(fen)
    proof = build_back_rank_mate_proof(board, "e1e2", "e1e8", 500)

    assert proof is not None
    assert proof.verifier.verified is True
    assert proof.detector.concept_id == "tactic.back_rank_mate"

    verdict = build_position_verdict(
        source_kind="canonical_test",
        source_ref="back-rank-mate",
        move_evaluation={
            "fen_before": fen,
            "move": "e1e2",
            "best_move_uci": "e1e8",
            "best_move_san": "Re8#",
            "cp_loss": 500,
            "pv_after_best": ["Re8#"],
        },
        broad_category="missed_tactic",
    )
    assert verdict.status == AdmissionStatus.BROAD
    assert verdict.quality_id == BACK_RANK_MATE_QUALITY_ID
    assert verdict.concept_id is None
    assert "specific_proof_unauthorized" in verdict.reason_codes


def test_mate_on_home_rank_by_knight_is_not_called_back_rank_mate():
    board = chess.Board("6k1/5ppp/8/8/8/5N2/8/6K1 w - - 0 1")
    # This is only a shape guard: an absent/illegal heavy mating move cannot
    # receive the narrow label.
    assert build_back_rank_mate_proof(board, "f3e5", "f3g5", 500) is None


def test_back_rank_proof_has_no_runtime_engine_llm_or_network_dependency():
    source = (
        Path(__file__).resolve().parents[1]
        / "services"
        / "back_rank_mate_puzzle_proof.py"
    ).read_text(encoding="utf-8")
    forbidden = ("StockfishEngine", "stockfish_service", "call_llm", "httpx", "requests.")
    assert not any(token in source for token in forbidden)
