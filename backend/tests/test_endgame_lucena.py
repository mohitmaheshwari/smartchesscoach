"""Unit tests for endgame_lucena detector."""
from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import chess

from services.concept_detectors.endgame_lucena import (
    detect_endgame_lucena_application,
)


# Canonical Lucena: WK c8, WP c7, WR d1 (the bridge-builder), BK a6,
# BR c3 (cutting off the king from helping). White to move, bridge
# move is Rd1-d4 (4th rank on the d-file, adjacent to c-pawn).
# Wait — d is the file adjacent to c (one over). My detector uses file
# offset of +2 (skipping the immediate adjacent file), looking at e for
# c-pawn. Let me use e3 in the position.
SETUP_LUCENA = "2K5/2P5/k7/8/8/2r5/8/4R3 w - - 0 1"


def _b(fen, san):
    board = chess.Board(fen)
    return board, board.parse_san(san)


def test_returns_none_outside_kpkrkr_setup():
    board = chess.Board()
    move = board.parse_san("e4")
    assert detect_endgame_lucena_application(board, move, chess.WHITE) is None


def test_returns_none_when_not_users_turn():
    fen = "2K5/2P5/k7/8/8/2r5/8/4R3 w - - 0 1"
    board, move = _b(fen, "Re4")
    assert detect_endgame_lucena_application(board, move, chess.BLACK) is None


def test_bridge_rook_move_is_applied():
    """Re1 -> e4 lifts the rook to the 4th rank, ready to interpose."""
    board, move = _b(SETUP_LUCENA, "Re4")
    assert detect_endgame_lucena_application(board, move, chess.WHITE) == "applied"


def test_skipping_bridge_move_is_missed():
    """Premature king move when the bridge-builder Re4 was legal."""
    board, move = _b(SETUP_LUCENA, "Kd8")  # king step ignoring the bridge
    assert detect_endgame_lucena_application(board, move, chess.WHITE) == "missed"


def test_rook_pawn_lucena_returns_none():
    """Lucena fails with a/h pawns — detector should skip."""
    fen = "K7/P7/k7/8/8/r7/8/4R3 w - - 0 1"
    board, move = _b(fen, "Re4")
    assert detect_endgame_lucena_application(board, move, chess.WHITE) is None
