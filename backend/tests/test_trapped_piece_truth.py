"""Regression tests for canonical trapped-piece truth and Chess Brain adapter."""

from __future__ import annotations

import inspect

import chess

from services.board_concepts import newly_trapped_pieces, trapped_pieces
from services.chess_brain.detector_registry import (
    TRAPPED_PIECE_MIN_CP_LOSS,
    detect_trapped_piece,
    get_detector_registry,
)
from services.concept_attribution import _trapped_own_piece


CLASSIC_TRAP_FEN = "n6R/8/8/B3k3/8/8/8/4K3 b - - 0 1"
CAPTURE_ESCAPE_FEN = "n6R/8/1R6/B3k3/8/8/8/4K3 b - - 0 1"
UNRELATED_HANG_FEN = "n6R/8/8/4k3/3q4/8/8/3RK3 b - - 0 1"
MOVE_CAUSALITY_FEN = (
    "3rkb1r/2p3p1/p7/Qp2p3/2b5/4B3/P1q2KPP/4R2R w k - 0 23"
)
MATE_FEN = "r5k1/ppp2p2/5Q1P/3p4/3P2Pr/1qP1P2P/3K4/3R3R w - - 0 32"


def test_classic_attacked_knight_with_no_safe_escape_is_trapped():
    board = chess.Board(CLASSIC_TRAP_FEN)

    facts = trapped_pieces(board, chess.BLACK)

    assert facts == [
        {
            "concept": "trapped_piece",
            "square": "a8",
            "piece": "knight",
            "color": "black",
            "cost_cp": 320,
        }
    ]


def test_profitable_capture_and_trade_is_a_safe_escape():
    board = chess.Board(CAPTURE_ESCAPE_FEN)

    # Nxb6 trades the knight for a rook. The knight can be recaptured, but
    # calling that a trapped loss ignores the material it collected.
    assert "Nxb6" in [
        board.san(move)
        for move in board.legal_moves
        if move.from_square == chess.A8
    ]
    assert trapped_pieces(board, chess.BLACK) == []


def test_unrelated_hanging_piece_does_not_poison_escape_safety():
    board = chess.Board(UNRELATED_HANG_FEN)

    # The queen on d4 is loose, but the knight on a8 can still reach safety.
    # Trapped-piece truth must follow the named knight, not global material.
    assert trapped_pieces(board, chess.BLACK) == []


def test_newly_trapped_fact_is_move_causal():
    board = chess.Board(MOVE_CAUSALITY_FEN)

    played = newly_trapped_pieces(board, board.parse_san("Bd2"))
    engine = newly_trapped_pieces(board, board.parse_san("Kg1"))

    assert played and played[0]["square"] == "d2"
    assert engine == []
    assert _trapped_own_piece(board, board.parse_san("Bd2")) is not None


def test_chess_brain_fires_only_when_best_avoids_significant_new_trap():
    board = chess.Board(MOVE_CAUSALITY_FEN)

    result = detect_trapped_piece(
        board,
        "Bd2",
        "Kg1",
        {"cp_loss": 9287},
    )

    assert result.detected is True
    assert result.details == {
        "trapped_piece": "bishop",
        "trapped_square": "d2",
        "cost_cp": 330,
        "avoidable_with": "Kg1",
    }


def test_chess_brain_abstains_without_engine_consequence():
    board = chess.Board(MOVE_CAUSALITY_FEN)

    assert TRAPPED_PIECE_MIN_CP_LOSS == 100
    assert detect_trapped_piece(
        board,
        "Bd2",
        "Kg1",
        {"cp_loss": 20},
    ).detected is False
    assert detect_trapped_piece(
        board,
        "Bd2",
        "Kg1",
        {},
    ).detected is False


def test_chess_brain_does_not_call_checkmate_a_trapped_queen():
    board = chess.Board(MATE_FEN)

    result = detect_trapped_piece(
        board,
        "Qg7#",
        "Qg7#",
        {"cp_loss": 500},
    )

    assert result.detected is False


def test_chess_brain_registration_requires_engine_best_move():
    registered = get_detector_registry().get_detector("trapped_piece_detector")

    assert registered is not None
    assert registered.requires_best_move is True


def test_chess_brain_is_an_adapter_not_another_mobility_recognizer():
    source = inspect.getsource(detect_trapped_piece)

    assert "newly_trapped_pieces" in source
    assert "legal_escapes" not in source
    assert "for legal_move in board_after.legal_moves" not in source
