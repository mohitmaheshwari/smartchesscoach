"""Unit tests for endgame_opposition detector."""
from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import chess

from services.concept_detectors.endgame_opposition import (
    detect_endgame_opposition_application,
)


def _b(fen, san):
    board = chess.Board(fen)
    return board, board.parse_san(san)


# ─── scope guards ─────────────────────────────────────────────────────────────

def test_returns_none_outside_kp_endgame():
    # Middlegame with full piece complement.
    board = chess.Board()
    move = board.parse_san("e4")
    assert detect_endgame_opposition_application(board, move, chess.WHITE) is None


def test_returns_none_when_not_users_turn():
    # Black king e6, white king e4 — already in opposition. White to
    # move (Ke4 is locked by opposition). User=BLACK so it's not the
    # user's turn. Use a pawn push (always legal here) as the move arg.
    fen = "8/8/4k3/8/4K3/8/3P4/8 w - - 0 1"
    board, move = _b(fen, "d3")
    assert detect_endgame_opposition_application(board, move, chess.BLACK) is None


def test_returns_none_when_already_in_opposition():
    # White Ke3, Black Ke5: already in direct opposition (file e, ranks
    # 3 and 5, exactly 2 apart). Don't fire.
    fen = "8/8/8/4k3/8/4K3/3P4/8 w - - 0 1"
    board, move = _b(fen, "d3")  # any non-king move
    assert detect_endgame_opposition_application(board, move, chess.WHITE) is None


# ─── applied: seizing opposition ─────────────────────────────────────────────

def test_seizing_opposition_is_applied():
    # White Ke4, Black Ke6 (kings 2 squares apart on e-file = direct
    # opposition already), with white to move — already in opposition,
    # skip this. Instead use a position where white CAN seize.
    # White Kd3, Black Ke5 + d-pawn for context. White to move.
    # Kd4 puts kings on d4 and e5 — adjacent diagonally, NOT opposition.
    # Better: White Ke3, Black Ke5 — already opposition. Let's set up:
    # White Kd4, Black Ke6 — kings 2 apart on diagonal, not opposition.
    # White moves Kd5 — now white K on d5, black K on e6. Adjacent
    # diagonally, NOT opposition.
    # Use: White Ke2, Black Ke4 + e-pawn for ENV. White plays Ke3 — puts
    # kings on e3 and e4. That's adjacent (1 square apart), not 2 squares.
    # Want: kings 2 squares apart on same file or rank AFTER move.
    # White Kd3, Black Ke5. White plays Ke3 — white K e3, black K e5.
    # Same file e, 2 apart. Opposition. APPLIED.
    fen = "8/8/8/4k3/8/3K4/4P3/8 w - - 0 1"
    board, move = _b(fen, "Ke3")
    assert detect_endgame_opposition_application(board, move, chess.WHITE) == "applied"


# ─── missed ──────────────────────────────────────────────────────────────────

def test_missing_opposition_when_king_move_available_is_missed():
    # Same starting position — white could play Ke3 (opposition) but
    # instead plays Kc3 (sideways shuffle).
    fen = "8/8/8/4k3/8/3K4/4P3/8 w - - 0 1"
    board, move = _b(fen, "Kc3")
    assert detect_endgame_opposition_application(board, move, chess.WHITE) == "missed"


# ─── not graded ──────────────────────────────────────────────────────────────

def test_pawn_move_is_not_graded():
    # Same position — user plays a pawn move instead of a king move.
    # Lots of correct K+P endgame play involves pawn pushes; don't
    # penalise the player.
    fen = "8/8/8/4k3/8/3K4/4P3/8 w - - 0 1"
    board, move = _b(fen, "e3")
    assert detect_endgame_opposition_application(board, move, chess.WHITE) is None


def test_king_move_without_available_opposition_is_not_graded():
    # Kings far apart, no king move seizes opposition. Don't grade.
    fen = "8/8/8/8/8/8/8/k3K3 w - - 0 1"  # kings on e1 and a1 (4 apart)
    board, move = _b(fen, "Ke2")
    assert detect_endgame_opposition_application(board, move, chess.WHITE) is None
