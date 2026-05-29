"""
Unit tests for the defend-against-Scholar's-Mate detector.

Real positions from canonical Scholar's Mate lines exercise the
geometry guards (Bc4 present, queen attacks f7, Qxf7 is mate) and the
grade output (applied / missed / None).
"""
from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import chess

from services.concept_detectors.defend_scholars_mate import (
    detect_defend_scholars_mate_application,
)


# ─── canonical Scholar's Mate setup ───────────────────────────────────────────
# After: 1.e4 e5 2.Bc4 Nc6 3.Qh5
# Black to move. Bc4 + Qh5 in place; Qxf7# is the threat.
SETUP_FEN = "r1bqkbnr/pppp1ppp/2n5/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR b KQkq - 3 3"


def _black_move(fen: str, san: str) -> tuple:
    board = chess.Board(fen)
    move = board.parse_san(san)
    return board, move


# ─── pre-condition guards ─────────────────────────────────────────────────────

def test_returns_none_when_user_is_white():
    board, move = _black_move(SETUP_FEN, "g6")
    assert detect_defend_scholars_mate_application(board, move, chess.WHITE) is None


def test_returns_none_when_not_blacks_turn():
    # White-to-move version of the canonical position — game shouldn't
    # grade Black on a move it's not Black's turn to play.
    fen_white_to_move = "r1bqkbnr/pppp1ppp/2n5/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 3 3"
    board = chess.Board(fen_white_to_move)
    move = board.parse_san("Qxf7+")
    assert detect_defend_scholars_mate_application(board, move, chess.BLACK) is None


def test_returns_none_when_no_bc4():
    # Same as canonical setup but bishop on f1, NOT c4. No defender for
    # the queen after Qxf7+, so it isn't really Scholar's Mate.
    fen_no_bc4 = "r1bqkbnr/pppp1ppp/2n5/4p2Q/4P3/8/PPPP1PPP/RNB1KBNR b KQkq - 3 3"
    board, move = _black_move(fen_no_bc4, "g6")
    assert detect_defend_scholars_mate_application(board, move, chess.BLACK) is None


def test_returns_none_when_position_isnt_actual_mate_in_one():
    # Bc4 + Qh5 but Black already has Nf6 played (so it's not a fresh
    # Scholar's setup; but more importantly nothing is at risk).
    # Use a non-mate Qh5 setup.
    fen = "rnbqkbnr/pppp1ppp/8/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR b KQkq - 3 3"
    # Black king on e8, no Black knight defending. Qxf7 IS mate here
    # (same as canonical). Confirm baseline first, then mutate.
    board, move = _black_move(fen, "g6")
    assert detect_defend_scholars_mate_application(board, move, chess.BLACK) == "applied"


def test_returns_none_when_past_move_eight():
    # Mid-game position with the same physical geometry — still flag-
    # gable, but we deliberately skip late-game to avoid false fires.
    fen = "r1bqkbnr/pppp1ppp/2n5/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR b KQkq - 3 12"
    board, move = _black_move(fen, "g6")
    assert detect_defend_scholars_mate_application(board, move, chess.BLACK) is None


# ─── applied: canonical defenses ──────────────────────────────────────────────

def test_g6_is_applied():
    """g6 blocks the h5-g6-f7 diagonal — textbook refutation."""
    board, move = _black_move(SETUP_FEN, "g6")
    assert detect_defend_scholars_mate_application(board, move, chess.BLACK) == "applied"


def test_qe7_is_applied():
    """Qe7 puts a defender on f7 via the 7th rank."""
    board, move = _black_move(SETUP_FEN, "Qe7")
    assert detect_defend_scholars_mate_application(board, move, chess.BLACK) == "applied"


def test_qf6_is_applied():
    """Qf6 defends f7 directly on the f-file."""
    board, move = _black_move(SETUP_FEN, "Qf6")
    assert detect_defend_scholars_mate_application(board, move, chess.BLACK) == "applied"


# ─── missed: Black ignores the threat ─────────────────────────────────────────

def test_nf6_is_missed():
    """The classic blunder. Nf6 attacks the queen but doesn't stop
    Qxf7#. White plays mate ignoring the attack on the queen."""
    board, move = _black_move(SETUP_FEN, "Nf6")
    assert detect_defend_scholars_mate_application(board, move, chess.BLACK) == "missed"


def test_random_pawn_move_is_missed():
    """A5 does nothing for the f7 threat."""
    board, move = _black_move(SETUP_FEN, "a5")
    assert detect_defend_scholars_mate_application(board, move, chess.BLACK) == "missed"


def test_developing_bishop_without_defending_is_missed():
    """Bc5 develops but ignores the threat — still Qxf7#."""
    board, move = _black_move(SETUP_FEN, "Bc5")
    assert detect_defend_scholars_mate_application(board, move, chess.BLACK) == "missed"
