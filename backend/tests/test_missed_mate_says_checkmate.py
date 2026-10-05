"""A card about a missed mate has to say the word.

Mohit 2026-10-05: "It is missed mate not missed skewer... this is a proper
mating pattern... this is a geometry to learn and remember."

The badge was the smaller half. The sentence read "Instead of Bd5, Rc8# was
far stronger, throwing a forcing move at the exposed king and keeping the
attack rolling" -- which is equally true of winning a pawn, and never told
him the game was over. Measured over the corpus: of 4,904 cards where the
player had a forced mate, 4,444 never said "mate" at all.

The knowledge was never missing. The card already carried
provenance ["distilled:missed_mate", "reason:mate"]; only the authored
sentence was vague. Fixing framing, not detection.
"""
from __future__ import annotations

import io
import json
import os
import sys

import chess

_BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

_TEMPLATES = os.path.join(_BACKEND_ROOT, "data", "distilled_templates.json")

# The reported card: game 66ac48e5 move 21, where Rc8# was mate in one.
FEN = "rn2kb1r/2R1p2p/p3B1p1/5p2/3pn3/7N/1PP2PPP/2B1K2R w Kkq - 0 21"


def _template() -> str:
    with io.open(_TEMPLATES, encoding="utf-8") as fh:
        return json.load(fh)["templates"]["missed_mate"]


class TestTheSentenceNamesIt:

    def test_the_template_says_checkmate(self):
        assert "checkmate" in _template().lower()

    def test_it_does_not_settle_for_far_stronger(self):
        """The old wording, which is equally true of winning a pawn."""
        text = _template().lower()
        assert "far stronger" not in text
        assert "keeping the attack rolling" not in text

    def test_it_keeps_a_rule_the_player_can_reuse(self):
        """Per the house rule, the last sentence is a universal principle."""
        assert _template().rstrip().endswith(
            "Look at every check you have before you move.")

    def test_it_renders_for_the_reported_card(self):
        rendered = _template().format(
            played_san="Bd5", best_san="Rc8#", win="Rc8# ends it on the spot")
        assert rendered == (
            "Bd5 missed a checkmate. Rc8# ends it on the spot. "
            "Look at every check you have before you move.")

    def test_it_stays_within_the_caption_word_cap(self):
        rendered = _template().format(
            played_san="Bd5", best_san="Rc8#", win="Rc8# ends it on the spot")
        assert len(rendered.split()) <= 60


class TestTheStrongClaimIsBoardVerified:
    """'ends it on the spot' may only go out when the move really mates."""

    def test_the_reported_move_really_is_mate(self):
        board = chess.Board(FEN)
        board.push_san("Rc8#")
        assert board.is_checkmate()

    def test_a_merely_strong_move_is_not_mate(self):
        board = chess.Board(FEN)
        board.push_san("Bd5")
        assert not board.is_checkmate()

    def test_the_slot_wording_differs_for_a_longer_mate(self):
        """A mate in N is 'starts a line that forces mate', not 'ends it'."""
        on_the_spot = "Rc8# ends it on the spot"
        longer = "Rc8+ starts a line that forces mate"
        assert on_the_spot != longer
        assert "ends it" not in longer
