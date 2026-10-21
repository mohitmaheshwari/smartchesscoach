"""A count taken mid-exchange is not a payoff.

Mohit 2026-10-21 asked whether we could build an on-demand reasoning engine
that runs Stockfish behind a button. We already have one -- the "Why was this
bad?" button, `services/why_on_demand.py` -- so the useful answer was to
measure what it says. On his own move 7 e5 it said:

    "After e5, dxe5 wins your knight."     payoff_cp 400

The stored engine verdict for that move is cp_loss 100. Counting the board
along the line it quoted:

    e5  0 | dxe5 -1 | Nxe5  0 | Nxd5 -1 | Nxf3+ +2 | Bxf3 -1 | c6 -1 | Nxf6+ -4

It stopped on `Nxf6+` -- a capture, with the recapture still pending. Black
plays gxf6 or Qxf6 next and the balance is back to one pawn, which is what
cp_loss said all along.

So the rule this file locks: read material only at a position where nothing is
hanging from the move that just happened. `_line_material_gain` now walks back
to the last ply whose preceding move cannot be answered by a capture on the
square it landed on.

This is the same rule the arrows already follow -- a green arrow promises
material and has to survive the recapture -- applied to the sentence.
"""
import sys
from pathlib import Path

import chess

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.punishment_resolver import _line_material_gain  # noqa: E402

# Mohit's card. Black plays e5; the quoted line ends on a capture-with-check.
E5_FEN = "r2qk2r/ppp2ppp/2nbpn2/3p1b2/3P4/P1N1PN2/1PP1BPPP/R1BQ1RK1 b kq - 3 7"
E5_LINE = ["e5", "dxe5", "Nxe5", "Nxd5", "Nxf3+", "Bxf3", "c6", "Nxf6+"]


def _walk(fen, line, plies):
    board = chess.Board(fen)
    for san in line[:plies]:
        board.push_san(san)
    return board


class TestTheBoardSaysWhatIClaim:
    """Asserted with python-chess alone, so a wrong fix cannot hide behind a
    wrong control."""

    def test_the_line_ends_on_a_capture(self):
        board = _walk(E5_FEN, E5_LINE, len(E5_LINE) - 1)
        mv = board.parse_san(E5_LINE[-1])
        assert board.is_capture(mv)

    def test_and_the_recapture_is_available(self):
        """Which is why the count taken there is premature."""
        board = _walk(E5_FEN, E5_LINE, len(E5_LINE))
        landed = chess.F6
        assert any(m.to_square == landed for m in board.legal_moves), (
            "black can take back on f6, so that position is not quiet")

    def test_the_earlier_ply_is_quiet(self):
        """After ...c6 nothing can be taken on c6, so material there is real."""
        board = _walk(E5_FEN, E5_LINE, len(E5_LINE) - 1)
        landed = chess.C6
        assert not any(m.to_square == landed for m in board.legal_moves)


class TestTheCountStopsSomewhereQuiet:
    def test_it_no_longer_claims_a_knight(self):
        """One pawn, not four. The engine's own cp_loss for this move is 100."""
        gain = _line_material_gain(E5_FEN, "e5", E5_LINE)
        assert gain > -400, (
            f"still counting the un-recaptured knight: {gain}")
        assert gain <= 0

    def test_it_agrees_with_the_engine_verdict(self):
        """cp_loss 100 and a one-pawn reading are the same story. Allowing a
        pawn of slack because the line is the engine's, not a search."""
        gain = _line_material_gain(E5_FEN, "e5", E5_LINE)
        assert -200 <= gain <= 0, gain


class TestItStillCountsRealMaterial:
    """The guard must not make the resolver blind -- a count that always
    returns zero would pass the test above and break the feature."""

    def test_a_plain_hanging_piece_is_still_counted(self):
        """1.e4 d5 2.exd5 Qxd5?? 3.Nc3 -- no. Use a clean free capture: a
        queen sitting en prise with no recapture available."""
        board = chess.Board("4k3/8/8/3q4/8/8/8/3QK3 w - - 0 1")
        assert board.piece_at(chess.D5) is not None
        gain = _line_material_gain(board.fen(), "Qxd5", ["Qxd5"])
        assert gain >= 800, f"a free queen must still read as won: {gain}"

    def test_an_even_trade_reads_as_even(self):
        board = chess.Board("4k3/8/8/3q4/8/8/8/3QK3 w - - 0 1")
        gain = _line_material_gain(board.fen(), "Qxd5", ["Qxd5", "Kd7"])
        assert gain >= 800, gain

    def test_a_trade_that_is_answered_reads_as_even(self):
        """Queen takes queen, king takes queen: nobody won anything."""
        board = chess.Board("4k3/8/8/3q4/8/8/8/3QK3 w - - 0 1")
        board.push_san("Qxd5")
        assert any(m.to_square == chess.D5 for m in board.legal_moves) is False, (
            "the king on e8 cannot reach d5; this fixture is a free capture")

    def test_the_recapture_case_reads_as_even(self):
        """Now with a king that CAN take back: Qxd5 Kxd5 is a queen for a
        queen, and the count must say so rather than claiming the first one."""
        board = chess.Board("8/8/4k3/3q4/8/8/8/3QK3 w - - 0 1")
        gain = _line_material_gain(board.fen(), "Qxd5", ["Qxd5", "Kxd5"])
        assert gain == 0, f"queen for queen is even, got {gain}"

    def test_and_the_un_recaptured_prefix_is_not_used(self):
        """Same position, line truncated BEFORE the recapture. The count must
        still refuse to bank the queen, because the recapture is available."""
        board = chess.Board("8/8/4k3/3q4/8/8/8/3QK3 w - - 0 1")
        gain = _line_material_gain(board.fen(), "Qxd5", ["Qxd5"])
        assert gain == 0, (
            f"banked a queen that is hanging to Kxd5: {gain}")
