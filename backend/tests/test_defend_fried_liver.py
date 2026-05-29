"""Unit tests for defend_fried_liver detector."""
from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import chess

from services.concept_detectors.defend_fried_liver import (
    detect_defend_fried_liver_application,
)


# Position after 1.e4 e5 2.Nf3 Nc6 3.Bc4 Nf6 4.Ng5 d5 5.exd5
# Black to move. Bc4 + Ng5 + Pd5 + Nf6 on the board.
SETUP_FEN = "r1bqkb1r/ppp2ppp/2n2n2/3Pp1N1/2B5/8/PPPP1PPP/RNBQK2R b KQkq - 0 5"


def _b(fen, san):
    board = chess.Board(fen)
    return board, board.parse_san(san)


# ─── scope guards ─────────────────────────────────────────────────────────────

def test_returns_none_when_user_is_white():
    board, move = _b(SETUP_FEN, "Nxd5")
    assert detect_defend_fried_liver_application(board, move, chess.WHITE) is None


def test_returns_none_when_no_bc4():
    fen = "r1bqkb1r/ppp2ppp/2n2n2/3Pp1N1/8/8/PPPPBPPP/RNBQK2R b KQkq - 0 5"
    board, move = _b(fen, "Nxd5")
    assert detect_defend_fried_liver_application(board, move, chess.BLACK) is None


def test_returns_none_when_no_ng5():
    fen = "r1bqkb1r/ppp2ppp/2n2n2/3Pp3/2B5/5N2/PPPP1PPP/RNBQK2R b KQkq - 0 5"
    board, move = _b(fen, "Nxd5")
    assert detect_defend_fried_liver_application(board, move, chess.BLACK) is None


def test_returns_none_when_no_pawn_on_d5():
    fen = "r1bqkb1r/ppp2ppp/2n2n2/4p1N1/2B5/8/PPPPPPPP/RNBQK2R b KQkq - 0 5"
    board, move = _b(fen, "a6")
    assert detect_defend_fried_liver_application(board, move, chess.BLACK) is None


def test_returns_none_when_past_move_seven():
    fen = "r1bqkb1r/ppp2ppp/2n2n2/3Pp1N1/2B5/8/PPPP1PPP/RNBQK2R b KQkq - 0 10"
    board, move = _b(fen, "Nxd5")
    assert detect_defend_fried_liver_application(board, move, chess.BLACK) is None


# ─── missed: the trap ─────────────────────────────────────────────────────────

def test_nxd5_walks_into_trap():
    board, move = _b(SETUP_FEN, "Nxd5")
    assert detect_defend_fried_liver_application(board, move, chess.BLACK) == "missed"


# ─── applied: canonical defenses ──────────────────────────────────────────────

def test_na5_is_applied():
    """Classical refutation — attacks the Bc4."""
    board, move = _b(SETUP_FEN, "Na5")
    assert detect_defend_fried_liver_application(board, move, chess.BLACK) == "applied"


def test_b5_is_applied():
    """Ulvestad / Fritz — also attacks the bishop."""
    board, move = _b(SETUP_FEN, "b5")
    assert detect_defend_fried_liver_application(board, move, chess.BLACK) == "applied"


def test_nd4_is_applied():
    """Sharp counter-attack."""
    board, move = _b(SETUP_FEN, "Nd4")
    assert detect_defend_fried_liver_application(board, move, chess.BLACK) == "applied"


def test_be7_is_applied():
    """Any non-Nxd5 move that doesn't capture on d5 is treated as a
    correct recognition of the trap — Be7 develops + side-steps."""
    board, move = _b(SETUP_FEN, "Be7")
    assert detect_defend_fried_liver_application(board, move, chess.BLACK) == "applied"
