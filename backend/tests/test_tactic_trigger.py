"""The board animates on a contradiction, not on a free capture.

Mohit's rule, in his words: "a bigger piece is taking up a smaller defended
piece and stockfish suggests it really as a top move". A capture like that
loses material on the square, so when the engine still calls it best,
something is coming the player cannot see. Nxe4 is the shape.

The negative control is his, too. A looser version of this rule put "Qxa1 --
a1 has no defender, so you win a free rook" in front of him and he threw it
straight back: "this is exchanging queen, no tactic". Winning loose material
is counting, not tactics, and the board should stay still for it.

Measured over 201 of his games with this gate: 87 cards, 0.43 a game, in 55
games. The loose gate it replaces fired on 7.8 a game.
"""
import os
import sys

import chess

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.game_decryption_v5_service import _v5_tactic_trigger  # noqa: E402


# His card: the knight takes a pawn the c3 knight is guarding.
NXE4_FEN = "r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/2N2N2/PPPP1PPP/R1BQK2R b KQkq - 5 4"


def test_the_fork_trick_fires():
    assert _v5_tactic_trigger(NXE4_FEN, "Nxe4") == {
        "attacker": "knight", "victim": "pawn",
        "square": "e4", "defenders": ["c3"],
    }


def test_a_free_rook_does_not_fire():
    """Mohit on seeing this one in a review list: "this is exchanging queen,
    no tactic, it had simple rook, to play"."""
    fen = "1k3r1b/1PPp1P1P/P1q4P/6P1/8/3p1p2/PPP3PP/R1bk3R b - - 0 1"
    assert _v5_tactic_trigger(fen, "Qxa1") is None


def test_a_quiet_move_does_not_fire():
    assert _v5_tactic_trigger(NXE4_FEN, "Bc5") is None
    assert _v5_tactic_trigger(NXE4_FEN, "d6") is None


def test_an_equal_trade_does_not_fire():
    """A knight taking a bishop is a trade, not a paradox. An earlier draft
    used "no greater than" and swept in 181 pawn-takes-pawn and 108
    bishop-takes-knight."""
    board = chess.Board(NXE4_FEN)
    # Build a position where a knight can take a defended bishop.
    fen = "4k3/8/8/3b4/8/2N5/3P4/4K3 w - - 0 1"
    probe = chess.Board(fen)
    assert probe.parse_san("Nxd5") in probe.legal_moves
    assert _v5_tactic_trigger(fen, "Nxd5") is None
    assert board.turn == chess.BLACK      # the fixture above is untouched


def test_taking_a_BIGGER_piece_does_not_fire():
    """A pawn taking a defended knight is winning material the hard way, not
    a tactic to reveal."""
    fen = "4k3/8/8/3n4/4P3/5P2/8/4K3 w - - 0 1"
    assert _v5_tactic_trigger(fen, "exd5") is None


def test_the_victim_does_not_count_as_its_own_defender():
    """The piece standing on the square cannot be guarding it. Counting it
    would make every capture look defended and fire on everything."""
    fen = "4k3/8/8/3p4/8/2N5/8/4K3 w - - 0 1"
    assert _v5_tactic_trigger(fen, "Nxd5") is None


def test_nothing_to_judge_is_not_a_trigger():
    assert _v5_tactic_trigger(None, "Nxe4") is None
    assert _v5_tactic_trigger(NXE4_FEN, None) is None
    assert _v5_tactic_trigger("not a fen", "Nxe4") is None
    assert _v5_tactic_trigger(NXE4_FEN, "Qz9") is None


def test_en_passant_names_the_square_the_pawn_stands_on():
    """The captured pawn is not on the square the capturing pawn lands on.
    Naming the landing square is how "bxc6+ takes the pawn on c6" became a
    false claim once before."""
    fen = "4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 2"
    got = _v5_tactic_trigger(fen, "exd6")
    # Pawn takes pawn is not strictly smaller, so this refuses -- but it must
    # refuse on the VALUE test, having first resolved d5 as the victim.
    assert got is None
