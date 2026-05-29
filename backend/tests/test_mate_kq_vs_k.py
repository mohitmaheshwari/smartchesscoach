"""Unit tests for mate_kq_vs_k detector.

Exercises the scope guards, the canonical mating moves, and the
mate-in-1 "missed" path.
"""
from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import chess

from services.concept_detectors.mate_kq_vs_k import (
    detect_mate_kq_vs_k_application,
)


# ─── canonical positions ──────────────────────────────────────────────────────
# White: Kg6, Qf7. Black: Kh8. White to move — Qg7# is mate.
SETUP_MATE_IN_ONE = "7k/5Q2/6K1/8/8/8/8/8 w - - 0 1"

# White: Ke6, Qh1. Black: Kg8. White to move — many possible moves,
# Qh7+/Qg2 etc; canonical mate-in-1 is Qh7#? Let me pick a known
# mate-in-1 position. White: Ka1, Qa7. Black: Ka8. Qxa8#? No, blocked.
# Use: White Kg6 + Qb7, Black Kh8. Qb7-h7# (Qh7#).
SETUP_BACK_RANK_M1 = "7k/1Q6/6K1/8/8/8/8/8 w - - 0 1"

# Grind position: White K+Q vs lone K, no mate-in-1, but a "good
# confining move" exists.
SETUP_GRIND = "4k3/8/8/8/8/8/3Q4/4K3 w - - 0 1"


# ─── pre-condition guards ────────────────────────────────────────────────────

def test_returns_none_when_not_users_turn():
    board = chess.Board(SETUP_MATE_IN_ONE)
    move = board.parse_san("Qg7#")
    # Detector called with user=BLACK on a white-to-move position.
    assert detect_mate_kq_vs_k_application(board, move, chess.BLACK) is None


def test_returns_none_when_opponent_has_other_pieces():
    # Lone king + an extra pawn ≠ "lone king" — opponent still has more
    # than just the king, so the canonical K+Q vs K technique isn't the
    # right test.
    fen = "7k/p7/6K1/8/8/8/3Q4/8 w - - 0 1"
    board = chess.Board(fen)
    move = board.parse_san("Qd8")
    assert detect_mate_kq_vs_k_application(board, move, chess.WHITE) is None


def test_returns_none_when_user_has_no_queen():
    # User has K+R+P (no Q). Opponent is lone K. Detector is specifically
    # about the Queen-mate technique; we don't fire on R+P mates.
    fen = "7k/P7/6K1/8/8/8/8/4R3 w - - 0 1"
    board = chess.Board(fen)
    move = board.parse_san("Re8")
    assert detect_mate_kq_vs_k_application(board, move, chess.WHITE) is None


# ─── applied ─────────────────────────────────────────────────────────────────

def test_qg7_mate_is_applied():
    board = chess.Board(SETUP_MATE_IN_ONE)
    move = board.parse_san("Qg7#")
    assert detect_mate_kq_vs_k_application(board, move, chess.WHITE) == "applied"


def test_qh7_mate_is_applied():
    board = chess.Board(SETUP_BACK_RANK_M1)
    move = board.parse_san("Qh7#")
    assert detect_mate_kq_vs_k_application(board, move, chess.WHITE) == "applied"


def test_applies_when_user_has_extra_material():
    """Extra pawn / piece on user's side doesn't block the detector —
    the technique still applies as long as opponent is lone king."""
    # White K+Q+P vs lone Black K. Qg7# still works.
    fen = "7k/5Q2/6K1/4P3/8/8/8/8 w - - 0 1"
    board = chess.Board(fen)
    move = board.parse_san("Qg7#")
    assert detect_mate_kq_vs_k_application(board, move, chess.WHITE) == "applied"


# ─── missed ──────────────────────────────────────────────────────────────────

def test_missing_mate_in_one_is_missed():
    """Mate-in-1 was Qg7#; instead user shuffles the queen elsewhere."""
    board = chess.Board(SETUP_MATE_IN_ONE)
    move = board.parse_san("Qf2")  # quiet, definitely not mate
    assert detect_mate_kq_vs_k_application(board, move, chess.WHITE) == "missed"


# ─── grinding (not graded) ───────────────────────────────────────────────────

def test_slow_grind_move_is_not_graded():
    """No mate-in-1 in this position; the technique requires several
    moves. We don't grade mid-grind moves to avoid hostile false-misses."""
    board = chess.Board(SETUP_GRIND)
    move = board.parse_san("Qd5")  # confines king, no immediate mate
    assert detect_mate_kq_vs_k_application(board, move, chess.WHITE) is None
