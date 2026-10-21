"""A piece is not pinned by something it can simply take.

Game 56b6c294, 2026-10-21. The story told the player "A pin you could have
played" for 13...Nxg5, whose better move was 13...Bxc3. The prover's pin was
the bishop on c3 against the b2 pawn and the a1 rook. White's reply is bxc3,
so there was never a pin. The real idea was Bxc3 bxc3 Nxc3, hitting the queen
on d1 and the bishop on e2. Measured that day: 388 of 1,457 stored missed_pin
labels rested on a front piece that could take the attacker.
"""
import chess

from services.aligned_tactic_puzzle_proof import (
    front_can_break_alignment,
    verify_created_alignment,
)
from services.cognitive_gap_subtypes import _pin_is_provable

# Game 56b6c294 before 13...Nxg5, Black to move.
GAME_FEN = "r2q1rk1/ppp2ppp/6b1/3pb1P1/4n2P/P1N1P3/1PP1BP2/R1BQ1RK1 b - - 0 13"
# Nimzo-Indian before 3...Bb4: the c3 knight will be truly pinned to the king.
NIMZO_FEN = "rnbqkb1r/pppp1ppp/4pn2/8/2PP4/2N5/PP2PPPP/R1BQKBNR b KQkq - 1 3"
# Bb3 skewers the queen on d5 to the rook on g8. The queen can take b3, but
# the bishop is defended by the a2 and c2 pawns.
SKEWER_DEFENDED = "6rk/8/8/3q4/B7/8/P1P4K/8 w - - 0 1"
SKEWER_UNDEFENDED = "6rk/8/8/3q4/B7/8/7K/8 w - - 0 1"


def test_the_game_position_is_not_a_pin():
    board = chess.Board(GAME_FEN)
    assert verify_created_alignment(board, "Bxc3", "pin") is None
    assert _pin_is_provable(board, board.parse_san("Bxc3")) is False


def test_the_pawn_really_can_take_the_bishop():
    board = chess.Board(GAME_FEN)
    board.push_san("Bxc3")
    assert front_can_break_alignment(
        board, chess.parse_square("c3"), chess.parse_square("b2"))


def test_a_real_pin_is_still_found():
    """Positive control: the fix must not switch pins off."""
    board = chess.Board(NIMZO_FEN)
    proof = verify_created_alignment(board, "Bb4", "pin")
    assert proof is not None
    assert (proof["front_square"], proof["rear_square"]) == ("c3", "e1")


def test_a_skewer_the_front_queen_could_only_take_at_a_loss_stays():
    board = chess.Board(SKEWER_DEFENDED)
    proof = verify_created_alignment(board, "Bb3", "skewer")
    assert proof is not None
    assert (proof["front_square"], proof["rear_square"]) == ("d5", "g8")


def test_a_skewer_the_front_queen_can_simply_take_is_not_one():
    board = chess.Board(SKEWER_UNDEFENDED)
    assert verify_created_alignment(board, "Bb3", "skewer") is None
