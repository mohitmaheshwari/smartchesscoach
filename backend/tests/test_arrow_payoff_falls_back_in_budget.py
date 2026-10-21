"""A payoff we cannot draw must not erase one we can.

Mohit 2026-10-21, on move 21 Kd1 of game 8c491e16: "why it didn't build the
punishment line?? i remember, we had arrows built around punishment line and
this is a clear fork between king and knight by queen" -- and then "i clearly
remember it was drawn before but our code changes, somehow removed it."

He was right on both counts, and a worktree at 8dc27745^ proved the second:
that card used to draw three arrows -- a3->a1, d1->e2, and a darkred a1->d4 --
which is exactly the fork. Qa1+ attacks the king on d1 AND the knight on d4,
and Qxd4 collects it.

What broke it was not the chooser's taste but its REACH. 12-ply re-analysis
made the stored line long enough that find_line_payoff could see a bigger
prize further out -- Nxh1 at index 10, winning a rook, net +600 against the
fork's +300 -- and it ranks by net, so it chose index 10. That sits past the
8-arrow budget, the `payoff >= max_arrows` guard fired, and a card with a
perfectly drawable fork at index 2 drew nothing at all.

The guard itself is right: half a plan whose payoff cannot be shown is worse
than the single honest arrow it displaces. The bug was treating "the best
payoff is out of reach" as "there is no payoff", when the same chooser run
over the drawable prefix finds one.

Measured over 1,500 games, user mistakes with a 9+ ply line: 7,097 such
lines, 4,522 drew before, 4,701 draw after -- 179 restored, 0 lost.
"""
import sys
from pathlib import Path

import chess

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from services.caption_pipeline import (  # noqa: E402
    _line_sequence_arrows,
    find_line_payoff,
)

# The reference card, with the line exactly as it is stored.
FEN_BEFORE = "rn4k1/pp3ppp/8/3p4/3NnB2/q4Q2/2PK1PPP/5B1R w - - 0 21"
PLAYED = "Kd1"
PV = ["Qa1+", "Ke2", "Qxd4", "Qe3", "Nc6", "Qxd4", "Nxd4+",
      "Kd3", "Nxf2+", "Kxd4", "Nxh1", "Be3"]
MAX_ARROWS = 8


def _board_after_played() -> chess.Board:
    board = chess.Board(FEN_BEFORE)
    board.push_san(PLAYED)
    return board


def test_the_move_really_is_a_fork():
    """The control, asserted off the board so a wrong fix cannot hide behind
    a wrong premise. Qa1+ hits the king and the knight at once."""
    board = _board_after_played()
    move = board.parse_san("Qa1+")
    after = board.copy()
    after.push(move)

    assert after.is_check()
    hit = {chess.square_name(sq) for sq in after.attacks(chess.A1)
           if after.piece_at(sq) and after.piece_at(sq).color == chess.WHITE}
    assert "d1" in hit, "the king is not attacked -- fixture is wrong"
    assert "d4" in hit, "the knight is not attacked -- fixture is wrong"


def test_the_punishment_line_is_drawn():
    """THE REGRESSION. This returned [] and the card showed no arrows at all."""
    arrows = _line_sequence_arrows(
        _board_after_played(), PV, max_arrows=MAX_ARROWS, line_is_ours=False)
    assert arrows, "the punishment line drew nothing"


def test_the_fork_itself_is_one_of_the_arrows():
    """a1->d4 is the queen collecting the knight. If the picture does not
    contain it, the drawing is not of the fork."""
    arrows = _line_sequence_arrows(
        _board_after_played(), PV, max_arrows=MAX_ARROWS, line_is_ours=False)
    pairs = {(a["from"], a["to"]) for a in arrows}
    assert ("a3", "a1") in pairs, "the queen's move to a1 is missing"
    assert ("a1", "d4") in pairs, "the fork's capture is missing"


def test_the_opponents_plan_is_painted_as_theirs():
    """line_is_ours=False, so their moves are red and the payoff darkred --
    never the green that means 'your payoff'. Guards the inversion fix."""
    arrows = _line_sequence_arrows(
        _board_after_played(), PV, max_arrows=MAX_ARROWS, line_is_ours=False)
    colours = {a["color"] for a in arrows}
    assert "green" not in colours, "a punishment card painted the player's colour"
    assert "red" in colours or "darkred" in colours


def test_nothing_is_drawn_past_the_budget():
    """The guard that still has to hold: never draw more than the budget."""
    arrows = _line_sequence_arrows(
        _board_after_played(), PV, max_arrows=MAX_ARROWS, line_is_ours=False)
    assert len(arrows) <= MAX_ARROWS


def test_a_line_with_no_payoff_at_all_still_draws_nothing():
    """The fallback must not become 'draw something regardless'. Five quiet
    developing moves have no payoff anywhere, in budget or out of it, and
    that is the case the original guard was added for -- Mohit's "what is
    this arrow??" on move 5 of 413fcce2."""
    board = chess.Board()
    for san in ("e4", "e5", "Nf3", "Nc6", "Bb5"):
        board.push_san(san)
    quiet = ["a6", "Ba4", "Nf6", "O-O", "Be7"]
    assert _line_sequence_arrows(board, quiet, max_arrows=MAX_ARROWS) == []


def test_a_short_line_is_unaffected():
    """85% of stored lines used to be 4 plies. The fallback only engages when
    the first choice is past the budget, so short lines must be byte-identical."""
    short = PV[:5]
    arrows = _line_sequence_arrows(
        _board_after_played(), short, max_arrows=MAX_ARROWS, line_is_ours=False)
    assert len(arrows) == 3
    assert arrows[-1]["color"] == "darkred"
    assert (arrows[-1]["from"], arrows[-1]["to"]) == ("a1", "d4")
