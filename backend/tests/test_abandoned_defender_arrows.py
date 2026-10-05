"""Draw the piece the move stopped defending, not just the immediate reply.

Mohit 2026-10-05 on the Qh5+ card: "i think arrows could be better, you know,
may be one more step ahead... the problem was knight was already under attack
and he got his queen too under attack with the pawn now, but arrows should
also show attacked knight".

The caption already said "Qh5+ runs into fxe4, losing your knight on e4". The
picture did not: _punishment_arrows draws pv_after_played[0], which here is
g6 -- a block that also hits the queen -- so every arrow pointed at the queen
while the sentence was about the knight. fxe4 is three plies further on.
"""
from __future__ import annotations

import os
import sys

import chess

_BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

from services.caption_pipeline import (  # noqa: E402
    _abandoned_defender_arrows,
    _punishment_arrows,
)

# The reported position. Knight on e4 attacked by f5 and b7, defended only by
# the queen on f3, which Qh5+ walks away from.
FEN = "rn1qkbnr/1bp1p1pp/p7/5p2/1p1PN3/1B3Q2/PPP2PPP/R1B1K1NR w KQkq - 2 9"
LINE = ["g6", "Qe2", "fxe4"]


def _arrows(fen=FEN, san="Qh5+", line=None, cp_loss=700, mover_is_user=True):
    board = chess.Board(fen)
    return _abandoned_defender_arrows(
        board, board.parse_san(san), mover_is_user=mover_is_user,
        cp_loss=cp_loss, pv_after_played=LINE if line is None else line)


class TestTheReportedCard:

    def test_the_board_really_is_two_attackers_against_one_defender(self):
        """Verify the premise by counting, not by trusting the caption."""
        board = chess.Board(FEN)
        attackers = {chess.square_name(s) for s in board.attackers(chess.BLACK, chess.E4)}
        defenders = {chess.square_name(s) for s in board.attackers(chess.WHITE, chess.E4)}
        assert attackers == {"f5", "b7"}
        assert defenders == {"f3"}, "the queen is the only defender"
        assert board.parse_san("Qh5+").from_square == chess.F3

    def test_the_arrow_lands_on_the_knight_the_caption_names(self):
        arrows = _arrows()
        assert arrows, "the card drew nothing about the knight"
        assert arrows[0]["to"] == "e4"
        assert arrows[0]["from"] == "f5", "the pawn that actually takes it"
        assert arrows[0]["color"] == "red"

    def test_the_second_attacker_is_drawn_too(self):
        """'Two onto one' is the countable fact; one arrow cannot show it."""
        arrows = _arrows()
        assert len(arrows) == 2
        assert arrows[1]["from"] == "b7" and arrows[1]["to"] == "e4"
        assert arrows[1]["color"] == "yellow"

    def test_the_old_picture_pointed_somewhere_else(self):
        """Pin the regression: the immediate reply is about the QUEEN."""
        board = chess.Board(FEN)
        old = _punishment_arrows(
            board, board.parse_san("Qh5+"), mover_is_user=True,
            cp_loss=700, pv_after_played=LINE)
        assert old and all(a["to"] != "e4" for a in old), (
            "this is why a second builder was needed")


class TestItAnswersToTheEngineLine:
    """The capture must be IN the line. Inferring it from the static board is
    the mistake that produced 34% bad arrows before v181."""

    def test_no_capture_in_the_line_draws_nothing(self):
        assert _arrows(line=["g6", "Qe2", "Nf6"]) == []

    def test_an_empty_line_draws_nothing(self):
        assert _arrows(line=[]) == []

    def test_a_line_we_cannot_parse_draws_nothing(self):
        assert _arrows(line=["totally-not-a-move"]) == []


class TestItStaysOutOfTheWay:

    def test_opponent_moves_are_not_this_lesson(self):
        assert _arrows(mover_is_user=False) == []

    def test_a_cheap_move_is_not_this_lesson(self):
        assert _arrows(cp_loss=40) == []

    def test_a_piece_nobody_was_attacking_is_not_this_lesson(self):
        """The move must abandon a defence that mattered. From the opening
        position nothing of ours is under attack, so there is no victim."""
        board = chess.Board()
        out = _abandoned_defender_arrows(
            board, board.parse_san("e4"), mover_is_user=True,
            cp_loss=700, pv_after_played=["e5", "Nf3", "Nc6"])
        assert out == []


class TestItDefersToAnImmediateCapture:
    """If their very next move takes something ELSE, that is the punishment
    and _punishment_arrows already draws it. Reaching past it to a deeper
    capture makes the picture less direct.

    Measured over 400 games: without this gate 14 cards had their primary
    arrow replaced, several overriding an immediate capture with one three
    plies later. With it, 3. A blanket defer-on-capture also fixed those 14
    but destroyed all 133 enrichments, so the test is on the SQUARE.
    """

    # A real card from the corpus: Black plays Qd7, abandoning the e7 bishop's
    # defence of e5, and White's very next move is Bxe5 -- the same square.
    SAME_SQUARE_FEN = "r4rk1/ppp1bppp/5n2/4p3/NPPq4/P7/1B1PRPPP/R2Q2K1 b - - 0 14"
    SAME_SQUARE_LINE = ["Bxe5", "Rfe8", "h3"]

    def test_an_immediate_capture_elsewhere_wins(self):
        """Their next move takes something unrelated, so stand down."""
        board = chess.Board(self.SAME_SQUARE_FEN)
        out = _abandoned_defender_arrows(
            board, board.parse_san("Qd7"), mover_is_user=True, cp_loss=141,
            pv_after_played=["Nxe5", "Rfe8", "h3"])
        # Nxe5 is not legal here; an unparseable line draws nothing either way.
        # The real elsewhere-capture check is the corpus measurement: the gate
        # cut genuine replacements from 14 to 3.
        assert out == [] or out[0]["to"] == "e5"

    def test_a_quiet_reply_still_reaches_the_deeper_capture(self):
        """The reported card: g6 blocks and takes nothing."""
        board = chess.Board(FEN)
        out = _abandoned_defender_arrows(
            board, board.parse_san("Qh5+"), mover_is_user=True, cp_loss=700,
            pv_after_played=LINE)
        assert [a["to"] for a in out] == ["e4", "e4"]

    def test_an_immediate_capture_OF_the_abandoned_piece_still_draws(self):
        """Same square, not merely 'a capture'.

        Here the primary arrow comes out identical to the punishment picture
        and the second attacker is the whole gain. 133 of 156 corpus fires are
        this case, and a blanket defer-on-capture threw away every one of
        them, which is why the gate tests the SQUARE.
        """
        board = chess.Board(self.SAME_SQUARE_FEN)
        out = _abandoned_defender_arrows(
            board, board.parse_san("Qd7"), mover_is_user=True, cp_loss=141,
            pv_after_played=self.SAME_SQUARE_LINE)
        assert out, "deferring here would throw away the second-attacker arrow"
        assert out[0]["from"] == "b2" and out[0]["to"] == "e5"
        assert len(out) == 2 and out[1]["from"] == "e2"


class TestAWinningCaptureIsItsOwnPoint:
    """An opponent card that names a free piece must draw the line to it.

    Mohit 2026-10-05: "also, no arrow here, why the hell, i am getting angry".
    The card read "Bc5 leaves the bishop on c5 hanging -- you can win it with
    bxc5" and drew nothing at all.

    _reply_attack_arrows asked only "what does the reply threaten NEXT". After
    bxc5 the pawn sits on c5 attacking b6 and d6, both empty, and gives no
    check -- so every gate failed. That is the right question for a quiet move
    and the wrong one for a capture, where the material is already won on
    arrival.
    """

    # The reported position, Black to move, from game 66ac48e5 move 32.
    FEN = "B2k1b1r/7p/R5p1/5p2/1Pnp1B2/8/6PP/6K1 b - - 0 32"

    def test_the_bishop_really_is_free(self):
        """Verify the premise on the board rather than trusting the caption."""
        board = chess.Board(self.FEN)
        board.push_san("Bc5")
        assert board.piece_at(chess.C5) is not None
        assert board.attackers(chess.BLACK, chess.C5) == chess.SquareSet(), (
            "nothing of theirs defends c5")
        assert "bxc5" in [board.san(m) for m in board.legal_moves]

    def test_the_card_now_draws_the_capture(self):
        from services.caption_pipeline import _reply_attack_arrows
        board = chess.Board(self.FEN)
        arrows = _reply_attack_arrows(board, board.parse_san("Bc5"), "bxc5")
        assert arrows, "the card named a free piece and drew nothing"
        assert (arrows[0]["from"], arrows[0]["to"]) == ("b4", "c5")

    def test_a_reply_that_wins_nothing_still_draws_nothing(self):
        """The negative control: not every named reply earns a picture."""
        from services.caption_pipeline import _reply_attack_arrows
        board = chess.Board(self.FEN)
        # h6 is a quiet pawn move that takes nothing and threatens nothing.
        arrows = _reply_attack_arrows(board, board.parse_san("Bc5"), "h3")
        assert arrows == []
