"""Unit tests for mate_kr_vs_k detector."""
from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import chess

from services.concept_detectors.mate_kr_vs_k import (
    detect_mate_kr_vs_k_application,
)


# Classic R-mate. Black: Ka8 (in the corner). White: Ka6 (in opposition,
# controls a7/b7/b6), Rh1. White to move — Rh8# mates: rook reaches
# the 8th rank, attacks the king, and every escape (a7/b7/b8) is
# covered by the king or the rook itself.
SETUP_R_MATE = "k7/8/K7/8/8/8/8/7R w - - 0 1"

# Grind position: K+R vs K, no mate-in-1 yet.
SETUP_GRIND = "4k3/8/8/8/8/8/8/R3K3 w - - 0 1"


def test_returns_none_when_not_users_turn():
    board = chess.Board(SETUP_R_MATE)
    move = board.parse_san("Rh8#")
    assert detect_mate_kr_vs_k_application(board, move, chess.BLACK) is None


def test_returns_none_when_opponent_has_other_pieces():
    fen = "7k/p7/6K1/8/8/8/8/7R w - - 0 1"
    board = chess.Board(fen)
    move = board.parse_san("Rh7+")
    assert detect_mate_kr_vs_k_application(board, move, chess.WHITE) is None


def test_returns_none_when_user_has_no_rook():
    # User has K+Q, not K+R. KQvK detector handles this, not KRvK.
    fen = "7k/8/6K1/8/8/8/8/3Q4 w - - 0 1"
    board = chess.Board(fen)
    move = board.parse_san("Qd8#")
    assert detect_mate_kr_vs_k_application(board, move, chess.WHITE) is None


def test_rh8_mate_is_applied():
    board = chess.Board(SETUP_R_MATE)
    move = board.parse_san("Rh8#")
    assert detect_mate_kr_vs_k_application(board, move, chess.WHITE) == "applied"


def test_applies_when_user_has_extra_pawn():
    fen = "k7/8/K7/4P3/8/8/8/7R w - - 0 1"
    board = chess.Board(fen)
    move = board.parse_san("Rh8#")
    assert detect_mate_kr_vs_k_application(board, move, chess.WHITE) == "applied"


def test_missing_mate_in_one_is_missed():
    board = chess.Board(SETUP_R_MATE)
    move = board.parse_san("Rb1")  # quiet shuffle, not mate
    assert detect_mate_kr_vs_k_application(board, move, chess.WHITE) == "missed"


def test_slow_grind_move_is_not_graded():
    board = chess.Board(SETUP_GRIND)
    move = board.parse_san("Ra5")  # confining move, no immediate mate
    assert detect_mate_kr_vs_k_application(board, move, chess.WHITE) is None
