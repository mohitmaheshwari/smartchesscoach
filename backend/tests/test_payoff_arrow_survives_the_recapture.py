"""A green payoff arrow has to survive the recapture.

Mohit 2026-10-18, on a card that said "Play Qd3" and drew a green arrow from
d3 to h7:

    "why our system build this arrow for plan??"

The arrow claimed h7 was winnable. It is not. White's two attackers (Qd3, Ng5)
do outnumber the one piece that can take back (Nf6 -- the king on g8 is aimed
at h7 but Kxh7 is illegal while the queen covers it), and yet the sequence
loses: Nxh7 Nxh7 Qxh7+ Kxh7 and White is a queen down. The engine's line from
that position (Rfd8, a5, Nf5) never goes near h7, and the card's own verdict
read "neither, material 0".

The arrow came from static_exchange_eval, which skips kings in recapture
sequences by convention, so a square the enemy king guards reads as free.
legal_exchange_gain plays the captures out with the king included.

The sentence beside it -- "which only their knight defends" -- is left alone
on purpose, and these tests pin that too. It states a COUNT, which is true the
moment the move is made and stays true whatever the opponent answers. The
green arrow states a PAYOFF, so it is the one that has to survive the reply.
A legal_exchange_gain gate was tried on the sentence once before and Stockfish
refused 18 of 40 sampled claims; the comment at the count branch records it.
"""
import sys
from pathlib import Path

import chess

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.caption_facts import (  # noqa: E402
    legal_exchange_gain,
    static_exchange_eval,
)
from services.caption_pipeline import _reply_attack_arrows  # noqa: E402

# Mohit's board, with Black to move: they play Rac8 and the card recommends
# Qd3 in reply.
BEFORE = "r4rk1/1bq1nppp/1p2pn2/1B1p2N1/PB1P4/8/2P2PPP/R2QR1K1 b - - 0 1"


def _after_rac8():
    board = chess.Board(BEFORE)
    board.push_san("Rac8")
    return board


def _arrows():
    board = chess.Board(BEFORE)
    played = board.parse_san("Rac8")
    return _reply_attack_arrows(board, played, "Qd3")


class TestTheTwoEvaluatorsDisagreeAboutH7:
    """This is the gap the arrow fell through."""

    def _after_qd3(self):
        board = _after_rac8()
        board.push_san("Qd3")
        return board

    def test_king_blind_see_calls_h7_a_free_pawn(self):
        after = self._after_qd3()
        assert static_exchange_eval(after, chess.H7, chess.WHITE) >= 100

    def test_but_playing_it_out_wins_nothing(self):
        after = self._after_qd3()
        probe = after.copy()
        probe.turn = chess.WHITE
        assert (legal_exchange_gain(probe, chess.H7, chess.WHITE) or 0) < 100

    def test_and_the_recapture_that_refutes_it_is_legal(self):
        """Nxh7 Nxh7 and the knight on f6 really can take back."""
        after = self._after_qd3()
        probe = after.copy()
        probe.turn = chess.WHITE
        probe.push_san("Nxh7")
        assert any(
            m.from_square == chess.F6 and m.to_square == chess.H7
            for m in probe.legal_moves
        )

    def test_while_the_king_genuinely_cannot(self):
        """So the count sentence beside the arrow is true, not a second bug."""
        after = self._after_qd3()
        probe = after.copy()
        probe.turn = chess.WHITE
        probe.push_san("Nxh7")
        assert not any(
            m.from_square == chess.G8 and m.to_square == chess.H7
            for m in probe.legal_moves
        ), "Qd3 covers h7, so Kxh7 is illegal"


class TestSoNoArrowIsDrawnToIt:
    def test_h7_gets_no_payoff_arrow(self):
        for arrow in _arrows():
            assert arrow.get("to") != "h7", (
                f"drew a payoff arrow to h7: {arrow}"
            )

    def test_and_the_cost_of_that_is_a_card_with_no_picture(self):
        """h7 was the only target, so this card now draws nothing.

        That is this builder's "right-or-silent" rule working as written: the
        blue move arrow is only emitted alongside a target, a check or a
        winning capture. It is honest and it is a real cost -- Mohit has
        objected to a blank card before ("also, no arrow here, why the hell").
        Pinned here so that if the floor is ever changed to draw the
        recommended move on its own, this test says so out loud rather than
        quietly going green.
        """
        assert _arrows() == []


class TestTheSacrificeGapIsUntouched:
    """static_exchange_eval must stay king-blind: the distance between it and
    legal_exchange_gain is how test_sacrifice_line recognises a sacrifice.
    Changing SEE itself broke four tests."""

    FEN = "rnbqkbnr/2p1pppp/p7/1p6/2BP4/2N5/PPP2PPP/R1BQK1NR w KQkq - 0 1"

    def test_see_still_calls_bxf7_free(self):
        board = chess.Board(self.FEN)
        assert static_exchange_eval(board, chess.F7, chess.WHITE) > 0

    def test_while_the_king_aware_check_still_refuses_it(self):
        board = chess.Board(self.FEN)
        move = board.parse_san("Bxf7+")
        assert (
            legal_exchange_gain(board, chess.F7, chess.WHITE, first_move=move)
            < 0
        )
