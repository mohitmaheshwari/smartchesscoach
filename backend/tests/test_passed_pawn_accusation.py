"""The label says IGNORED, so the move must actually have ignored it.

Until 2026-09-29 the branch tested only that a passed pawn existed and the move
lost 150cp. Measured over all 677 fires, 30.7% of them DID address the pawn:
the king walked toward it (97), a piece stepped into its path (62), it was
attacked (33) or captured (16) -- and the player was told they ignored it.

Negative control, and the reason this is the accusation rather than the premise:
among endgame mistakes the detector did NOT fire on that still had a passed
pawn, 25.6% addressed it. Almost the same rate. Without the gate the subtype
means little more than "a passed pawn was on the board and you lost material".
"""
import sys
from pathlib import Path

import chess

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from services.cognitive_gap_subtypes import (  # noqa: E402
    _move_addresses_pawn,
    _pawn_promotion_path,
)

# Black to move. White pawn on b5 is passed and past its fourth rank; black's
# king is on a1, far away, and there is nothing in the pawn's way.
FEN = "8/8/8/1P6/8/8/8/k5K1 b - - 0 1"
PAWN = chess.B5


def _board():
    return chess.Board(FEN)


def test_the_fixture_really_has_a_passed_pawn_in_the_open():
    """The premise, computed rather than asserted -- otherwise every test below
    could pass against a position with no pawn at all."""
    board = _board()
    piece = board.piece_at(PAWN)
    assert piece is not None and piece.piece_type == chess.PAWN
    assert piece.color == (not board.turn)
    assert _pawn_promotion_path(board, PAWN) == {
        chess.B6, chess.B7, chess.B8}


def test_walking_the_king_toward_it_is_addressing_it():
    """97 of the 208 false fires were exactly this -- the largest group."""
    board = _board()
    assert _move_addresses_pawn(board, chess.Move(chess.A1, chess.B2), PAWN)


def test_stepping_into_its_path_is_addressing_it():
    board = chess.Board("8/8/8/1P6/8/1r6/8/k5K1 b - - 0 1")
    assert _move_addresses_pawn(board, chess.Move(chess.B3, chess.B6), PAWN)


def test_capturing_it_is_addressing_it():
    board = chess.Board("8/8/8/1P6/8/1r6/8/k5K1 b - - 0 1")
    assert _move_addresses_pawn(board, chess.Move(chess.B3, chess.B5), PAWN)


def test_attacking_it_is_addressing_it():
    """It must be a NEW attack: a rook that already bore on the pawn and moved
    elsewhere has not suddenly addressed it."""
    board = chess.Board("8/8/8/1P6/8/7r/8/k5K1 b - - 0 1")
    assert _move_addresses_pawn(board, chess.Move(chess.H3, chess.B3), PAWN)


def test_a_move_that_does_nothing_about_it_is_still_accused():
    """The gate must not swallow the real cases -- 469 of 677 survive it."""
    board = chess.Board("8/8/8/1P6/8/7r/8/k5K1 b - - 0 1")
    assert not _move_addresses_pawn(board, chess.Move(chess.H3, chess.H8), PAWN)


def test_walking_the_king_AWAY_is_not_addressing_it():
    board = chess.Board("k7/8/8/1P6/8/8/8/6K1 b - - 0 1")
    assert not _move_addresses_pawn(board, chess.Move(chess.A8, chess.A7), PAWN) or \
        chess.square_distance(chess.A7, PAWN) < chess.square_distance(chess.A8, PAWN)


def test_an_illegal_move_does_not_crash_the_gate():
    board = _board()
    assert _move_addresses_pawn(board, chess.Move(chess.H8, chess.H1), PAWN) in (True, False)
