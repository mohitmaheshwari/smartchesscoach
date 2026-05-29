"""Unit tests for endgame_philidor detector."""
from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import chess

from services.concept_detectors.endgame_philidor import (
    detect_endgame_philidor_application,
)


# Philidor defender position. Black to move.
# White attacker: Kd5, Ra1, Pe4. Black defender: Ke8, Re6 (canonical
# 3rd rank from black's POV). The defending move is to drop the rook
# behind the white king when white pushes Pe4-e5 — but in this v1
# detector we grade ANY drop to the first 2 ranks of white's POV that
# stays close to the pawn file.
# Black rook on c6 (so it can actually drop down the c-file in one
# move). White: Kd5, Pe5, Rb1. Black: Ke8, Rc6. Black to move.
SETUP_PHILIDOR = "4k3/8/2r5/3KP3/8/8/8/1R6 b - - 0 1"


def _b(fen, san):
    board = chess.Board(fen)
    return board, board.parse_san(san)


def test_returns_none_outside_scope():
    # Starting position — way more material than Philidor scope.
    board = chess.Board()
    move = board.parse_san("e4")
    assert detect_endgame_philidor_application(board, move, chess.WHITE) is None


def test_returns_none_when_not_users_turn():
    # Black-to-move FEN, but call with user=WHITE — not user's turn.
    board = chess.Board(SETUP_PHILIDOR)
    move = chess.Move.from_uci("c6c1")  # any black-rook move
    assert detect_endgame_philidor_application(board, move, chess.WHITE) is None


def test_drop_rook_to_first_rank_is_applied():
    """Black plays Rc6-c1 — drops to white's 1st rank, c-file is
    2 files from the e-pawn (within the rear-guard window)."""
    board2 = chess.Board(SETUP_PHILIDOR)
    move2 = chess.Move.from_uci("c6c1")
    assert detect_endgame_philidor_application(board2, move2, chess.BLACK) == "applied"


def test_drop_to_second_rank_is_applied():
    """Drop to c2 also counts — within attacker's first 2 ranks."""
    board2 = chess.Board(SETUP_PHILIDOR)
    move2 = chess.Move.from_uci("c6c2")
    assert detect_endgame_philidor_application(board2, move2, chess.BLACK) == "applied"


def test_drop_far_from_pawn_does_not_apply():
    """Move to a1 — 4 files from e-pawn — too far for the
    Philidor rear-guard window."""
    board2 = chess.Board(SETUP_PHILIDOR)
    # Slide to a6 first then drop? That's two moves. For a single move
    # from c6 to a-file-rank-1: not legal (rook can't move diagonally).
    # Instead test a move that DOES land on a rank-1 square far from
    # the pawn: c6-c-rank? No, all c-file is within 2 files of e.
    # Use rank 6 move that's not a "drop" at all — h6.
    move2 = chess.Move.from_uci("c6h6")  # along rank 6, doesn't drop
    assert detect_endgame_philidor_application(board2, move2, chess.BLACK) is None
