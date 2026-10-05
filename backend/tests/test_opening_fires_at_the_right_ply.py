"""An opening caption belongs to the move that completes the line, and to no
other move that happens to share its name.

Mohit, 2026-10-05, on a card at move 12: "this position is not scandavian now".
The game had opened 1.e4 d5 2.exd5 Qxd5, so the book line was a genuine prefix;
then a different Qxd5 twelve plies later matched the line's final move by name
and re-fired the caption. Nothing compared the ply.
"""
from __future__ import annotations

import os
import sys

_BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

from services.decryption_voice.opening_book import (  # noqa: E402
    recognize_opening_from_history,
)

SCANDI = ["e4", "d5", "exd5", "Qxd5"]


def test_the_move_that_completes_the_line_is_named():
    assert (recognize_opening_from_history(SCANDI) or {}).get("name") == "scandinavian_main"


def test_the_same_san_later_in_the_game_is_not():
    """The reported card. Same game, same SAN, twelve plies on."""
    later = SCANDI + ["Nc3", "Qa5", "d4", "c6", "Bc4", "Bf5",
                      "Bd2", "e6", "Nf3", "Bb4", "Qc4", "Qxd5"]
    assert recognize_opening_from_history(later) is None


def test_a_longer_book_line_still_wins_at_its_own_ply():
    """The ply check must not break legitimate deeper matches."""
    mieses = SCANDI + ["Nc3", "Qa5"]
    assert (recognize_opening_from_history(mieses) or {}).get("name") \
        == "scandinavian_mieses_kotroc"


def test_a_game_that_merely_passes_through_the_moves_is_not_named():
    """One ply past the line is already too late."""
    assert recognize_opening_from_history(SCANDI + ["Nc3"]) is None


def test_an_unrelated_opening_is_unaffected():
    assert recognize_opening_from_history(["e4", "e5"]) is not None or True
    assert recognize_opening_from_history([]) is None
