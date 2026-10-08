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
    _OPENINGS,
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
    # `x is not None or True` can never fail, so the original form of this test
    # asserted nothing -- and it was hiding a false premise: ["e4", "e5"] is
    # not in the table at all, so the call it made returns None. Assert against
    # a line the table actually holds.
    assert (recognize_opening_from_history(["e4", "c5"]) or {}).get("name") == "sicilian"
    assert recognize_opening_from_history([]) is None


def test_a_sequence_outside_the_book_is_not_named():
    assert recognize_opening_from_history(["e4", "e5"]) is None
    assert recognize_opening_from_history(["h4", "h5"]) is None


def test_every_book_line_names_itself():
    """The positive control: tightening must not strand an entry.

    A ply condition can silence real openings as easily as false ones, and a
    table entry that can never fire again would be invisible -- no error, just
    an opening that stops being named. Walk the whole table.
    """
    unreachable = [
        entry["name"] for entry in _OPENINGS
        if (recognize_opening_from_history(list(entry["moves"])) or {}).get("name")
        != entry["name"]
    ]
    assert unreachable == [], f"book lines that can never fire: {unreachable}"


# The real SAN history of the reported game (66ac48e5), which plays Qxd5 at
# plies 4, 23 and 24. The continuation above is hand-written and never pushed
# through a board; this one is the game Mohit was looking at.
REPORTED_GAME = [
    "e4", "d5", "exd5", "Qxd5", "Nc3", "Qd8", "d4", "a6", "Bc4", "b5",
    "Bb3", "b4", "Ne4", "f5", "Qf3", "Bb7", "Qh5+", "g6", "Qe2", "Bxe4",
    "Qc4", "Bd5", "Qxd5",
]


def test_the_reported_game_is_named_only_at_ply_4():
    named = recognize_opening_from_history(REPORTED_GAME[:4]) or {}
    assert named.get("name") == "scandinavian_main"
    assert recognize_opening_from_history(list(REPORTED_GAME)) is None


def test_the_misnamed_move_was_white_taking_a_bishop():
    """Pin down that the caption's own words were false here.

    It read "Black recaptures with the queen" and named a target on c3. Both
    are wrong for this position, so if anyone restores the name-only match
    this fails on the substance rather than on a None check.
    """
    import chess

    board = chess.Board()
    for san in REPORTED_GAME[:-1]:
        board.push_san(san)
    assert board.turn == chess.WHITE, "it is White to move, not Black"
    captured = board.piece_at(chess.D5)
    assert captured is not None and captured.piece_type == chess.BISHOP
    assert captured.color == chess.BLACK, "White's queen takes a BLACK bishop"
    assert board.piece_at(chess.C3) is None, "the caption's target on c3 is empty"


def test_match_length_always_reaches_the_end_of_the_history():
    """The invariant that replaced the last-SAN string comparison."""
    for i in range(1, len(REPORTED_GAME) + 1):
        result = recognize_opening_from_history(REPORTED_GAME[:i])
        if result is not None:
            assert result["match_length"] == i, (
                f"ply {i} ({REPORTED_GAME[i - 1]}) was named {result['name']} "
                f"from a {result['match_length']}-ply line"
            )
