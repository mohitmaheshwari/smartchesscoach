"""Evidence gates around canonical positional recognizers."""
from __future__ import annotations

import chess

from services.concept_detectors._runner import run_detectors_for_move
from services.concept_detectors.positional_patterns import (
    detect_luft_application,
)


LUFT_FEN = "rnbq1rk1/pppp1ppp/4pn2/8/8/8/PPPPPPPP/RNBQ1RK1 w - - 0 9"


def test_luft_requires_exact_stored_best_move():
    board = chess.Board(LUFT_FEN)
    move = board.parse_san("h3")
    assert detect_luft_application(
        board,
        move,
        chess.WHITE,
        move_number=9,
        best_move_uci=move.uci(),
    ) == "applied"
    assert detect_luft_application(
        board,
        move,
        chess.WHITE,
        move_number=9,
        best_move_uci="a2a3",
    ) is None
    assert detect_luft_application(
        board, move, chess.WHITE, move_number=9
    ) is None


def test_positional_candidates_remain_shadow_in_product_runner(monkeypatch):
    monkeypatch.setenv("DETECTOR_QUALITY_GATE_ENFORCED", "true")
    board = chess.Board(LUFT_FEN)
    move = board.parse_san("h3")
    product = run_detectors_for_move(
        board,
        move,
        chess.WHITE,
        move_number=9,
        best_move_uci=move.uci(),
    )
    shadow = run_detectors_for_move(
        board,
        move,
        chess.WHITE,
        move_number=9,
        best_move_uci=move.uci(),
        include_shadow=True,
    )
    assert ("concept_luft", "applied") not in product
    assert ("concept_luft", "applied") in shadow


def test_missing_move_number_cannot_create_positional_evidence():
    board = chess.Board(LUFT_FEN)
    move = board.parse_san("h3")
    assert detect_luft_application(
        board,
        move,
        chess.WHITE,
        best_move_uci=move.uci(),
    ) is None
