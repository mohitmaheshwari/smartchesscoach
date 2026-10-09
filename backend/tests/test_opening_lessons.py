"""An opening mistake, named as the opening it belongs to.

Mohit 2026-10-10 on 2...Bg4 in a Philidor, badged "inaccuracy" at 51cp with
no reason given: "it should be captioned in as an opening teaching... which
opening, what's better in this opening... a theory to remember".

Two designs were measured and thrown away before this one, and the tests keep
both failures pinned so neither comes back.
"""
from __future__ import annotations

import os
import sys

_BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

from services.opening_lessons import (  # noqa: E402
    lookup_opening,
    name_the_opening,
)

# Bishop's Opening, Black to move at move 6, a5 played and h6 recommended.
BERLIN_FEN = "r1bqk2r/ppp2ppp/2np1n2/2b1p1B1/2B1P3/2NP1N2/PPP2PPP/R2QK2R b KQkq - 0 6"
BERLIN_CAPTION = "You played a5; h6 was stronger — it attacks the bishop on g5."


class TestItDecoratesRatherThanReplaces:
    """The second failed design wrote its own caption and dropped the reason:
    "h6 was stronger -- it attacks the bishop on g5" became "h6 is the move
    here". A name is not worth a why."""

    def test_the_reason_survives(self):
        out = name_the_opening(BERLIN_CAPTION, BERLIN_FEN, 6, "h6",
                               "Bishops Opening Berlin Defense")
        assert out is not None
        assert "it attacks the bishop on g5" in out.caption

    def test_and_the_opening_leads(self):
        out = name_the_opening(BERLIN_CAPTION, BERLIN_FEN, 6, "h6",
                               "Bishops Opening Berlin Defense")
        assert out.caption.startswith("In the Bishops Opening Berlin Defense,")

    def test_a_caption_opening_with_a_move_keeps_its_capital(self):
        """Lowercasing the first character turned "Ne4 lets Qf3 attack..."
        into "ne4 lets Qf3 attack..."."""
        out = name_the_opening("Ne4 lets Qf3 attack the knight on e4. Nbd7 was better.",
                               "rnbqkb1r/pp2pppp/2p5/3p4/3Pn3/5N2/PPP1PPPP/RNBQKB1R w KQkq - 0 5",
                               5, "Nbd7", "Scandinavian Defense")
        if out is not None:
            assert "Ne4" in out.caption and "ne4" not in out.caption

    def test_it_declines_when_the_caption_names_no_better_move(self):
        """Nothing to anchor the lesson to."""
        assert name_the_opening("A calm move that keeps your position solid.",
                                BERLIN_FEN, 6, "h6",
                                "Bishops Opening Berlin Defense") is None

    def test_it_declines_past_the_opening(self):
        assert name_the_opening(BERLIN_CAPTION, BERLIN_FEN, 30, "h6",
                                "Bishops Opening Berlin Defense") is None

    def test_it_does_not_say_the_opening_twice(self):
        out = name_the_opening("In the Bishops Opening Berlin Defense, h6 was stronger.",
                               BERLIN_FEN, 6, "h6", "Bishops Opening Berlin Defense")
        assert out is None


class TestColourGatesTheProseAndNotTheName:
    """The FIRST failed design attached the entry's golden_rules directly and
    served "c6 holds d5 without locking in the bishop" -- Black's rule -- on
    White's Bf4 in a Slav. The fix was a colour gate; the mistake was then
    applying that gate to the opening's NAME, which belongs to both players.
    It rejected 884 of 2,798 otherwise-matchable cards."""

    def test_authored_prose_is_refused_to_the_wrong_side(self):
        assert lookup_opening("Slav Defense 3.Bf4", True, needs_our_side=True) is None

    def test_but_the_name_is_available_to_both(self):
        white = lookup_opening("Italian Game Two Knights Defense", True)
        black = lookup_opening("Italian Game Two Knights Defense", False)
        assert white is not None and black is not None
        assert white["name"] == black["name"]

    def test_the_slav_entry_really_is_written_for_black(self):
        """If this ever flips, the gate above is testing nothing."""
        entry = lookup_opening("Slav Defense 3.Bf4", True)
        assert entry is not None and entry.get("color") == "black"


class TestTheLongestNameWins:
    """"Italian Game Two Knights" must not match the bare "Italian Game"
    entry when the specific one exists."""

    def test_a_specific_variation_beats_the_family(self):
        entry = lookup_opening("Italian Game Two Knights Defense", False)
        assert entry is not None
        assert "italian" in entry["key"].lower()


class TestItSurvivesJunk:

    def test_no_opening_name(self):
        assert name_the_opening(BERLIN_CAPTION, BERLIN_FEN, 6, "h6", None) is None

    def test_an_unknown_opening(self):
        assert name_the_opening(BERLIN_CAPTION, BERLIN_FEN, 6, "h6",
                                "Completely Invented Opening") is None

    def test_a_broken_fen(self):
        assert name_the_opening(BERLIN_CAPTION, "not a fen", 6, "h6",
                                "Bishops Opening Berlin Defense") is None

    def test_an_empty_caption(self):
        assert name_the_opening("", BERLIN_FEN, 6, "h6",
                                "Bishops Opening Berlin Defense") is None
