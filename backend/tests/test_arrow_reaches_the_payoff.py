"""The arrows stop on the move that WINS material, not the first capture.

Mohit, 2026-10-16, on move 24 of 8c491e16: "my point there was to show the
mistake with arrows, why the arrow didn't show the fork part?"

Position r5k1/pp3ppp/2n5/3p4/3qnB2/5Q2/2P2PPP/4KB1R w - - 2 24, played Bd3,
engine line Qa1+ Qd1 Qxd1+ Kxd1 Nxf2+ Ke1 Nxh1.

Three things each stopped the picture one move short of the point:

1. `_line_sequence_arrows` kept its own payoff loop that took the FIRST
   capture by the line's owner. That is Qxd1+, a queen trade answered by
   Kxd1 -- so the card drew three arrows ending dark-red on a trade.
2. `find_line_payoff` had the right idea (a net test "to stop a queen TRADE
   reading as winning a queen") but summed only up to the capture itself,
   never including the reply that pays for it.
3. The arrow budget was 5, and the real payoff, Nxh1, sits at index 6.
"""
import sys
from pathlib import Path

import chess

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.caption_pipeline import (  # noqa: E402
    _line_sequence_arrows, describe_line_steps, find_line_payoff,
    walk_engine_line,
)

FEN = "r5k1/pp3ppp/2n5/3p4/3qnB2/5Q2/2P2PPP/4KB1R w - - 2 24"
LINE = ["Qa1+", "Qd1", "Qxd1+", "Kxd1", "Nxf2+", "Ke1", "Nxh1",
        "Bb5", "Nd4", "Bd7", "Rd8", "Bg4"]


def _after_played():
    b = chess.Board(FEN)
    b.push_san("Bd3")
    return b


def test_a_recaptured_queen_is_not_the_payoff():
    """Qxd1+ grabs the biggest piece on the line and is answered by Kxd1."""
    board = _after_played()
    found = find_line_payoff(board, walk_engine_line(board, LINE), 8)
    assert found is not None
    idx, _kind = found
    assert LINE[idx] == "Nxh1", f"payoff landed on {LINE[idx]}"


def test_the_arrows_run_through_to_the_rook():
    arrows = _line_sequence_arrows(_after_played(), LINE, line_is_ours=False)
    assert arrows, "a line with a real payoff must draw something"
    last = arrows[-1]
    assert (last["from"], last["to"]) == ("f2", "h1"), arrows
    assert last["color"] == "darkred", last


def test_every_arrow_has_a_sentence_to_print():
    """The card joins steps to arrows by from/to and prints only the pairs,
    so a short step list leaves the payoff arrow unexplained."""
    arrows = _line_sequence_arrows(_after_played(), LINE, line_is_ours=False)
    steps = describe_line_steps(FEN, "Bd3", LINE)
    by = {f"{s['from']}{s['to']}" for s in steps}
    missing = [a for a in arrows if f"{a['from']}{a['to']}" not in by]
    assert not missing, f"arrows with no sentence: {missing}"


def test_the_fork_is_named_in_the_printed_sentences():
    arrows = _line_sequence_arrows(_after_played(), LINE, line_is_ours=False)
    steps = describe_line_steps(FEN, "Bd3", LINE)
    by = {f"{s['from']}{s['to']}": s for s in steps}
    told = [by[f"{a['from']}{a['to']}"] for a in arrows
            if f"{a['from']}{a['to']}" in by]
    assert any("forks" in s["text"] for s in told), [s["text"] for s in told]


def test_a_plain_trade_still_draws_nothing():
    """The guard that matters: a line whose only capture is answered must
    not paint a payoff. Rxe8 Rxe8 is an even swap."""
    fen = "4r1k1/5ppp/8/8/8/8/5PPP/4R1K1 w - - 0 1"
    board = chess.Board(fen)
    board.push_san("Kf1")                      # a quiet user move
    found = find_line_payoff(board, walk_engine_line(board, ["Rxe1+", "Kxe1"]), 8)
    assert found is None or found[0] != 0, found
