"""A sacrifice has to show what it buys — in the words and on the board.

Mohit 2026-10-02, on "Opponent's b5 is a serious mistake. Play Bxf7+ — it wins
a pawn", drawn as a single arrow into f7: "no why again, also it showed me to
sacrifice my bishop, should show me a complete line if theory that is real
coaching, you know?"

Two defects in one card, on
`rnbqkbnr/2p1pppp/p7/1p6/2BP4/2N5/PPP2PPP/R1BQK1NR w KQkq - 0 6`:

  * f7 is guarded only by the king on e8, so static_exchange_eval scored it
    +100 "free" and the reason called a bishop sacrifice a won pawn.
    legal_exchange_gain, which plays Kxf7 out, says -200.
  * the single-move picture drew the bishop going to f7 and stopped, which is
    a player giving away a bishop for a pawn. The point is two plies later:
    Qf3+ hits the king AND the undefended rook on a8.

Everything below is computed from the board. Nothing reads caption text.
"""
import chess

from services.caption_facts import (
    PIECE_VALUE_CP, _recommended_move_why, legal_exchange_gain,
    static_exchange_eval,
)
from services.caption_pipeline import _line_sequence_arrows

AFTER_B5 = "rnbqkbnr/2p1pppp/p7/1p6/2BP4/2N5/PPP2PPP/R1BQK1NR w KQkq - 0 6"
# As stored on the card: [our reply, their forced answer, our point, ...]
STORED_PV = ["Bxf7+", "Kxf7", "Qf3+", "Nf6"]


class TestItIsReallyASacrifice:
    """The premise, proved, so the rest of the file is not testing a fiction."""

    def test_f7_is_guarded_only_by_the_king(self):
        board = chess.Board(AFTER_B5)
        defenders = {chess.square_name(s) for s in board.attackers(chess.BLACK, chess.F7)}
        assert defenders == {"e8"}

    def test_see_calls_it_free_and_the_king_aware_check_does_not(self):
        board = chess.Board(AFTER_B5)
        move = board.parse_san("Bxf7+")
        assert static_exchange_eval(board, chess.F7, chess.WHITE) > 0
        assert legal_exchange_gain(board, chess.F7, chess.WHITE, first_move=move) < 0

    def test_the_rook_on_a8_really_is_loose_after_the_check(self):
        board = chess.Board(AFTER_B5)
        for san in STORED_PV[:3]:
            board.push(board.parse_san(san))
        assert board.is_check()
        rook = board.piece_at(chess.A8)
        assert rook is not None and rook.piece_type == chess.ROOK
        assert rook.color == chess.BLACK
        assert not board.attackers(chess.BLACK, chess.A8), "nothing defends it"
        assert chess.A8 in board.attacks(chess.F3), "the queen hits it from f3"


class TestTheReason:
    def test_it_no_longer_calls_a_sacrifice_a_won_pawn(self):
        board = chess.Board(AFTER_B5)
        why = _recommended_move_why(
            board, board.parse_san("Bxf7+"), line=STORED_PV[1:]
        ) or ""
        assert "wins a pawn" not in why

    def test_it_names_the_check_and_the_loose_rook(self):
        board = chess.Board(AFTER_B5)
        why = _recommended_move_why(
            board, board.parse_san("Bxf7+"), line=STORED_PV[1:]
        ) or ""
        assert "Qf3+" in why and "rook on a8" in why

    def test_without_a_line_it_claims_no_payoff(self):
        board = chess.Board(AFTER_B5)
        why = _recommended_move_why(board, board.parse_san("Bxf7+")) or ""
        assert "a8" not in why, "no line means no claim about a8"

    def test_an_ordinary_free_capture_is_unaffected(self):
        board = chess.Board("4k3/8/8/3n4/8/8/8/3QK3 w - - 0 1")
        assert _recommended_move_why(board, board.parse_san("Qxd5")) == "wins material"


class TestThePicture:
    def test_the_whole_line_is_drawn_with_the_reply_in_its_own_colour(self):
        arrows = _line_sequence_arrows(chess.Board(AFTER_B5), STORED_PV)
        assert [(a["from"], a["to"], a["color"]) for a in arrows] == [
            ("c4", "f7", "blue"),       # your sacrifice
            ("e8", "f7", "palegrey"),   # their forced reply
            ("d1", "f3", "green"),      # the point
        ]

    def test_the_picture_ends_on_the_payoff_not_on_their_move(self):
        arrows = _line_sequence_arrows(chess.Board(AFTER_B5), STORED_PV)
        assert arrows and arrows[-1]["color"] == "green"

    def test_a_long_line_is_not_truncated_mid_sequence(self):
        """A 12-ply PV once walked to a payoff past the four arrows drawn, so
        the picture ended on the opponent's move with no payoff at all."""
        long_pv = STORED_PV + ["Qxa8", "Bb7", "Qf3", "e6", "Nf3", "Bd6"]
        arrows = _line_sequence_arrows(chess.Board(AFTER_B5), long_pv)
        assert arrows[-1]["color"] == "green"
        assert len(arrows) <= 4

    def test_a_line_that_is_not_a_sacrifice_still_abstains_early(self):
        # Our first move wins material outright: the single-move builders
        # already say it, so the sequence picture must stay out of the way.
        board = chess.Board("4k3/8/8/3n4/8/8/8/3QK3 w - - 0 1")
        assert _line_sequence_arrows(board, ["Qxd5", "Ke7", "Qd1", "Kf6"]) == []
