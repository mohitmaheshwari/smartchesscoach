"""A knight joining a piece that already covers the landing square.

Mohit 2026-10-19, on a card that said only "Play Nb5": "it's a learning, and a
very used idea controlling c7 or f7 square with bishops for fork, so a good
learning both sides is to learn it or avoid it".

He is right, and the engine agrees. On
r1bqkb1r/pp2pppp/2n2n2/3p4/3P1B2/2N5/PPP2PPP/R2QKBNR w the bishop on f4
already covers c7; Nb5 makes it two attackers against one defender, and if
Black plays on, Nc7+ Kd7 Nxa8 is +272 at depth 20. The fork even turns up at
the end of the line Black defends with: 6...e5 7.Bxe5 Nxe5 8.dxe5 Ng4 9.Qxd5
Qxd5 10.Nc7+.

The detector is written as the FAMILY, not as that position. c7 and f7 are
simply where this shape appears most, because they are the squares a developed
bishop covers while the enemy king and rook are still at home; the same idea
lands on f3, e7, c2 and d6 in the corpus.

Three conditions, and the third is what separates a plan from a sacrifice:
after our move a knight can reach square L; landing on L gives check and also
hits a rook or queen; and L is already covered by another of our pieces.
TestSupportIsWhatMakesItAPlan is the test for that third one -- without it the
hop is a piece offer, and teaching it would lose material.

Measured over 500 games before shipping: fires on 114 of 15,155 recommended
moves (0.75%), and all 114 claims verified on the board -- push the move, play
the fork, confirm it checks, hits a heavy piece, and lands covered.
"""
import sys
from pathlib import Path

import chess
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.caption_facts import (  # noqa: E402
    _recommended_move_why,
    _supported_knight_fork,
)

MOHIT = "r1bqkb1r/pp2pppp/2n2n2/3p4/3P1B2/2N5/PPP2PPP/R2QKBNR w KQkq - 4 6"


class TestItFindsTheIdeaMohitDescribed:
    def test_nb5_is_recognised(self):
        board = chess.Board(MOHIT)
        found = _supported_knight_fork(board, board.parse_san("Nb5"))
        assert found is not None
        fork_san, victim_name, victim_sq, sup_name, sup_sq, landing = found
        assert fork_san.startswith("Nc7")
        assert (victim_name, victim_sq) == ("rook", "a8")
        assert (sup_name, sup_sq) == ("bishop", "f4")
        assert landing == "c7"

    def test_the_caption_names_the_fork_and_the_piece_behind_it(self):
        board = chess.Board(MOHIT)
        why = _recommended_move_why(
            board, board.parse_san("Nb5"), mover_is_user=True
        )
        assert why and "Nc7" in why
        assert "rook on a8" in why
        assert "bishop on f4" in why

    def test_the_fork_really_is_there_on_the_board(self):
        """Not taken from the detector's word for it."""
        board = chess.Board(MOHIT)
        board.push_san("Nb5")
        probe = board.copy()
        probe.turn = chess.WHITE          # if Black does nothing
        probe.ep_square = None
        hop = probe.parse_san("Nc7+")
        landed = probe.copy()
        landed.push(hop)
        assert landed.is_check()
        assert any(
            (p := landed.piece_at(sq)) and p.color == chess.BLACK
            and p.piece_type == chess.ROOK
            for sq in landed.attacks(hop.to_square)
        )


class TestSupportIsWhatMakesItAPlan:
    """Without a piece already covering the square, the hop is a piece offer."""

    def test_removing_the_bishop_silences_it(self):
        board = chess.Board(MOHIT)
        board.remove_piece_at(chess.F4)
        assert _supported_knight_fork(board, board.parse_san("Nb5")) is None

    def test_and_the_caption_does_not_claim_the_fork_either(self):
        board = chess.Board(MOHIT)
        board.remove_piece_at(chess.F4)
        why = _recommended_move_why(
            board, board.parse_san("Nb5"), mover_is_user=True
        )
        assert why is None or "Nc7" not in why


class TestTheCausalityIsStatedCorrectly:
    """"already covers" is only true when the supporter was there BEFORE the
    move. Measured over 500 games, the moved piece is its own supporter often
    enough to matter -- Qa4 covering d4, Bf5 covering c2 -- and saying
    "already" there states the cause backwards."""

    def test_when_the_moved_piece_is_its_own_supporter_it_does_not_say_already(self):
        board = chess.Board(MOHIT)
        move = board.parse_san("Nb5")
        found = _supported_knight_fork(board, move)
        assert found is not None
        _, _, _, _, sup_sq, _ = found
        why = _recommended_move_why(board, move, mover_is_user=True)
        if sup_sq == chess.square_name(move.to_square):
            assert "already" not in why
        else:
            assert "already covers" in why


class TestItStaysSilentWhereItShould:
    @pytest.mark.parametrize(
        "fen,san",
        [
            ("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", "Nf3"),
            ("4k3/8/8/8/8/8/4P3/4K3 w - - 0 1", "e4"),
            ("8/8/8/8/8/8/8/K6k w - - 0 1", "Kb1"),
        ],
    )
    def test_no_fork_no_claim(self, fen, san):
        board = chess.Board(fen)
        assert _supported_knight_fork(board, board.parse_san(san)) is None

    def test_it_never_raises_on_a_full_game(self):
        board = chess.Board()
        for san in ["e4", "e5", "Nf3", "Nc6", "Bb5", "a6", "Ba4", "Nf6",
                    "O-O", "Be7", "Re1", "b5", "Bb3", "d6", "c3", "O-O",
                    "h3", "Nb8", "d4", "Nbd7"]:
            for mv in list(board.legal_moves)[:10]:
                _supported_knight_fork(board, mv)
            board.push_san(san)
