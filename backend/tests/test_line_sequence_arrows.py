"""Draw the whole idea when the payoff lands two moves later.

Mohit 2026-09-26: "could have also drawn a line between rook and bishop, as
rook takes it up... i would love to do that for moves that shows the
complete line." And then, on being told the replies would not be drawn:
"can we have the replies in different colors?"

He was right to push. Without the reply, the rook arrow describes a path
that is BLOCKED on the board in front of the player by their own knight --
a picture true only two plies from now, which is the bug this file spent
2026-09-22 removing. With the reply drawn in a subordinate colour the three
arrows read as an order of events instead of a claim about the board.
"""
from __future__ import annotations

import sys
from pathlib import Path

import chess

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from services.caption_pipeline import _line_sequence_arrows  # noqa: E402

# After Black's Rae8. White knight d5 blocks White's own rook on d1, and the
# bishop on d6 has nothing defending it. Engine best is Nf6+ at +411.
POSITION = "4rrk1/pp3ppp/3bb3/3N4/4P3/5N2/PPP2PPP/2KR3R w - - 7 18"
LINE = ["Nf6+", "gxf6", "Rxd6", "Bc8", "Rd4", "Re6"]


def _arrows(pv, fen=POSITION, **kw):
    return _line_sequence_arrows(chess.Board(fen), pv, **kw)


def _tuples(arrows):
    return [(a["from"], a["to"], a["color"]) for a in arrows]


class TestTheSequence:
    def test_draws_move_reply_and_payoff_in_order(self):
        assert _tuples(_arrows(LINE)) == [
            ("d5", "f6", "blue"),      # the move you play
            ("g7", "f6", "palegrey"),  # their forced reply
            ("d1", "d6", "green"),     # the point: the rook gets the bishop
        ]

    def test_the_reply_is_visually_subordinate(self):
        # Not the same colour as our moves. Mohit asked for this explicitly,
        # and it is what stops the three arrows reading as one position.
        colours = {a["from"]: a["color"] for a in _arrows(LINE)}
        assert colours["g7"] == "palegrey"
        assert colours["d5"] != "palegrey"
        assert colours["d1"] != "palegrey"

    def test_the_payoff_is_the_one_that_stands_out(self):
        arrows = _arrows(LINE)
        assert arrows[-1]["color"] == "green"
        assert arrows[-1]["to"] == "d6"

    def test_it_stops_at_the_payoff_not_at_the_end_of_the_line(self):
        # The line runs six plies; the idea is complete after three.
        assert len(_arrows(LINE)) == 3

    def test_every_arrow_is_tagged_teach_or_the_filter_drops_it(self):
        assert all(a.get("teach") is True for a in _arrows(LINE))


class TestWhenItStaysQuiet:
    def test_an_immediate_capture_is_left_to_the_single_move_builders(self):
        # 78 of 198 measured cards win material on our first move. A second
        # picture there competes with the one already drawn.
        assert _arrows(["Nxd6", "Rxd6", "Rxd6"]) == []

    def test_a_line_that_never_captures_draws_nothing(self):
        assert _arrows(["Rhe1", "Rfe8", "Rd3"]) == []

    def test_an_illegal_line_abstains_instead_of_raising(self):
        assert _arrows(["Qxh7"]) == []
        assert _arrows(["not a move"]) == []

    def test_empty_and_missing_inputs(self):
        assert _arrows([]) == []
        assert _arrows(None) == []
        assert _line_sequence_arrows(None, LINE) == []


class TestClutter:
    def test_it_is_capped(self):
        # Mohit killed a 14-arrow picture once; this must not rebuild it.
        arrows = _arrows(LINE, max_arrows=2)
        assert len(arrows) <= 2

    def test_a_long_run_of_trades_does_not_become_wallpaper(self):
        # Our first capture ends it whatever follows.
        assert len(_arrows(LINE + ["Rd8", "Rxd8", "Nxd8"])) == 3

    def test_an_unparseable_tail_costs_the_tail_not_the_picture(self):
        # The first version returned [] here: one bad move late in the line
        # discarded three plies that had already verified. A Stockfish PV is
        # legal by construction, but a truncated one should degrade.
        assert _tuples(_arrows(LINE[:3] + ["Qxz9", "Rxa8"])) == [
            ("d5", "f6", "blue"),
            ("g7", "f6", "palegrey"),
            ("d1", "d6", "green"),
        ]
