"""A king standing next to a defended man does not chase it.

`_must_move` decides whether a piece is obliged to move, and FORCES_RETREAT
speaks off that decision ("after X, Y chases your rook"). Its last test asks
whether the cheapest attacker is worth less than the man:

    cheapest = min(PIECE_VALUE_CP[...] for s in attackers)
    return cheapest < PIECE_VALUE_CP[piece]

`PIECE_VALUE_CP[chess.KING]` is 0 -- correct where it was defined, since SEE
caps before a king capture (caption_facts.py:121), and wrong here, because
min() then returns 0 and 0 is less than every piece value. So every man a king
merely stood beside was declared obliged to move.

Found on a real line: after Re6 Qxf5 gxf5 Kf7 the rook on e6 was reported as
having to move because the enemy king "attacks" it -- while Kxe6 is illegal,
the rook being defended twice. A king can only take an UNDEFENDED man.

The negative control is the second class below, and it is the one that matters:
a king really does chase a LOOSE piece, and it must keep doing so. A fix that
simply ignored king attackers would silence that.
"""
from __future__ import annotations

import sys
from pathlib import Path

import chess

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.punishment_resolver import _must_move  # noqa: E402


class TestADefendedManIsNotChasedByAKing:
    def test_rook_defended_twice_beside_the_enemy_king(self):
        """Black Re6, White Kf7 adjacent, and Black's own Ke8+Nd8... the rook
        is defended, so Kxe6 is illegal and nothing is chased."""
        board = chess.Board("4k3/4RK2/8/8/8/8/8/8 w - - 0 1")
        # White rook on e7, White king f7 -- own piece, so flip: use a black
        # rook defended by the black king, with the white king alongside.
        board = chess.Board("8/4rk2/5K2/8/8/8/8/8 w - - 0 1")
        assert board.piece_at(chess.E7).piece_type == chess.ROOK
        # the white king attacks e7; the black king on f7 defends it
        assert chess.F6 in board.attackers(chess.WHITE, chess.E7)
        assert board.attackers(chess.BLACK, chess.E7)
        assert _must_move(board, chess.E7, chess.BLACK) is False

    def test_the_capture_really_is_illegal_there(self):
        """The fixture has to mean what the test claims, or it proves nothing."""
        board = chess.Board("8/4rk2/5K2/8/8/8/8/8 b - - 0 1")
        board.turn = chess.WHITE
        assert chess.Move(chess.F6, chess.E7) not in board.legal_moves


class TestAKingStillChasesALoosePiece:
    """The negative control. Ignoring king attackers outright would break this."""

    def test_undefended_rook_beside_the_enemy_king_must_move(self):
        board = chess.Board("8/4r3/5K2/8/7k/8/8/8 b - - 0 1")
        assert not board.attackers(chess.BLACK, chess.E7)
        assert chess.F6 in board.attackers(chess.WHITE, chess.E7)
        assert _must_move(board, chess.E7, chess.BLACK) is True


class TestTheOtherRoutesStillWork:
    def test_a_king_in_check_always_must_move(self):
        board = chess.Board("4k3/8/8/8/8/8/8/4R2K b - - 0 1")
        assert _must_move(board, chess.E8, chess.BLACK) is True

    def test_a_cheaper_piece_attacking_a_dearer_one_still_fires(self):
        """A pawn poking a knight: outranked on value, so it must move."""
        board = chess.Board("4k3/8/8/4n3/3P4/8/8/4K3 b - - 0 1")
        assert chess.D4 in board.attackers(chess.WHITE, chess.E5)
        assert _must_move(board, chess.E5, chess.BLACK) is True

    def test_more_attackers_than_defenders_still_fires(self):
        board = chess.Board("4k3/8/8/4n3/8/4R3/4R3/4K3 b - - 0 1")
        assert len(board.attackers(chess.WHITE, chess.E5)) > \
            len(board.attackers(chess.BLACK, chess.E5))
        assert _must_move(board, chess.E5, chess.BLACK) is True
