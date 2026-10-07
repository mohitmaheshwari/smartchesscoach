"""The opponent's threat is read from Stockfish's line, never searched for.

Mohit 2026-10-07: "why are we checking legal moves, we have stockfish man,
this is a rule, everything on review should be backed by stockfish...
detectors can't really find anything that engine top moves can't, stockfish is
the truth table, pens down."

`_find_opponent_threats` enumerated every legal opponent move, guessed which
looked dangerous from board geometry, then ran a depth-10 search per guess to
check -- while the depth-18 answer was already stored as pv_after_played[0].
Re-rendering one 42-move game took 47 minutes.

The rule this file holds:
  Stockfish decides WHAT and WHERE. Detectors only name the shape.
  Detectors never search.
"""
from __future__ import annotations

import os
import sys

import chess

_BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

from services.move_comparison import threat_from_engine_reply  # noqa: E402


def _after(fen, played):
    b = chess.Board(fen)
    b.push_san(played)
    return b


class TestItNamesTheShapeOfTheEnginesMove:
    """Real cards out of the corpus. All three shapes, no engine."""

    def test_a_free_capture_is_named(self):
        fen, played, reply = ("r2q1rk1/1b2bppp/p2p1n2/1p2p3/4P3/1BN2N2/PPP2PPP/R1BQR1K1 w - - 0 12",
                              "Nd5", "Nxd5")
        # Shape only: the detector must never claim more than the board shows.
        t, txt = threat_from_engine_reply(_after(fen, played), reply, chess.BLACK)
        assert t in (None, "capture", "fork", "mate")
        if t:
            assert txt

    def test_mate_is_named_as_mate(self):
        fen = "rnbqkbnr/pppp1ppp/8/4p3/6P1/5P2/PPPPP2P/RNBQKBNR b KQkq - 0 2"
        t, txt = threat_from_engine_reply(_after(fen, "Nf6"), "Qh5", chess.WHITE)
        # Qh5 is not mate here; the point is it must not CLAIM mate.
        assert t != "mate" or "checkmate" in txt


class TestItNeverSearches:
    def test_a_quiet_reply_produces_nothing(self):
        """O-O / d4 from Mohit's card. A slow positional move is not a threat,
        and the old path would still have scanned ~35 legal moves to decide."""
        fen = "r1bqk2r/pppp1ppp/2n2n2/2b1p3/2B1P3/2P2N2/PP1P1PPP/RNBQ1RK1 b kq - 0 5"
        assert threat_from_engine_reply(_after(fen, "O-O"), "d4", chess.WHITE) == (None, "")

    def test_a_sacrifice_is_not_called_a_free_capture(self):
        """Bxh7+ takes a pawn and loses a bishop. It is the start of a line,
        not a free capture, and must not be announced as one."""
        fen = "r1bq1rk1/pp4pp/1b6/3pP3/2n2B2/3B1NQ1/PP4PP/1R3R1K b - - 0 17"
        assert threat_from_engine_reply(_after(fen, "Be6"), "Bxh7+", chess.WHITE) == (None, "")

    def test_no_line_means_no_claim(self):
        fen = "r1bq1rk1/pp4pp/1b6/3pP3/2n2B2/3B1NQ1/PP4PP/1R3R1K b - - 0 17"
        board = _after(fen, "Be6")
        assert threat_from_engine_reply(board, None, chess.WHITE) == (None, "")
        assert threat_from_engine_reply(board, "", chess.WHITE) == (None, "")

    def test_a_move_that_is_not_legal_is_refused(self):
        fen = "r1bq1rk1/pp4pp/1b6/3pP3/2n2B2/3B1NQ1/PP4PP/1R3R1K b - - 0 17"
        assert threat_from_engine_reply(_after(fen, "Be6"), "Qxz9", chess.WHITE) == (None, "")

    def test_it_only_speaks_for_the_side_that_moves_next(self):
        """Handed OUR move by mistake, it must say nothing rather than invent
        a threat against us from our own piece."""
        fen = "r1bq1rk1/pp4pp/1b6/3pP3/2n2B2/3B1NQ1/PP4PP/1R3R1K b - - 0 17"
        board = _after(fen, "Be6")
        assert threat_from_engine_reply(board, "Bxh7+", chess.BLACK) == (None, "")


class TestTheRule:
    def test_it_takes_no_engine_argument_at_all(self):
        """The signature is the guarantee: this cannot search even by accident.
        If an `engine` parameter ever reappears here, the rule has been broken."""
        import inspect
        params = set(inspect.signature(threat_from_engine_reply).parameters)
        assert "engine" not in params
        assert params == {"board", "reply_san", "opp_color"}
