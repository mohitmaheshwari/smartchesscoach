"""A teaching script may not say anything the position does not support.

The whole argument for this content type is that its claims are computed
rather than rephrased, so a false sentence here is worse than a false caption
elsewhere: it is the one thing we tell people cannot happen.

All three failures below came out of the FIRST row the generator ever wrote,
on a real game, and are fixed:

    1k6/8/1p6/7P/8/6P1/1r1R3K/8 b - - 0 48

  1. It is a ROOK endgame. _bare_race stripped both rooks off, solved the
     king-and-pawn position left behind, and the script stated that result
     as a fact about the game in front of the student: "Strip the board down
     to the king and the running pawn and count: the king is in time." The
     position it described never existed.
  2. Maia put 99.7% of 1180-rated players on the only move. Technically an
     only-move position; pedagogically worthless.
  3. With every alternative under 1%, the script still named one, and said
     "About 0 in 100 players rated 1180 play it here."
"""

from __future__ import annotations

import sys
from pathlib import Path

import chess
import pytest

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from services.teaching_script_builder import (  # noqa: E402
    DefenderTry,
    MoveVerdict,
    TeachingTree,
    _bare_race,
    render_script,
)

ROOK_ENDGAME = "1k6/8/1p6/7P/8/6P1/1r1R3K/8 b - - 0 48"
REAL_RACE = "8/p5k1/8/8/5K2/8/8/8 b - - 0 1"


def test_the_counting_beat_never_fires_on_a_position_with_pieces():
    # The exact position that shipped the false sentence.
    assert _bare_race(chess.Board(ROOK_ENDGAME), None) is None


def test_it_still_fires_on_a_genuine_king_and_pawn_race():
    # ...and the fix must not silence the beat where it is the actual lesson.
    race = _bare_race(chess.Board(REAL_RACE), None)
    assert race is not None
    assert race["proof"] == "exhaustive"
    assert race["result"] == "the king is in time"


def test_a_queen_on_the_board_is_not_a_pawn_race_either():
    # Guards the general case, not just rooks.
    with_queen = chess.Board("8/p5k1/8/8/5K2/8/8/5Q2 b - - 0 1")
    assert _bare_race(with_queen, None) is None


def _tree(alternatives):
    return TeachingTree(
        fen=REAL_RACE,
        side_to_move="black",
        men=3,
        proof="exhaustive",
        only_move=MoveVerdict("Kf6", "g7f6", "wins", "exact", human_pct=99.7),
        alternatives=alternatives,
        defender_tries=[DefenderTry("Ke4", "exact", "Ke6", 1, 8, True, "")],
        main_line="1...Kf6 2. Ke4 Ke6",
        bare_race=None,
    )


def test_no_tempting_move_is_named_when_nobody_plays_one():
    # Every alternative under the 5% floor: the beat is dropped rather than
    # naming a move "about 0 in 100 players" choose.
    beats = render_script(
        _tree([
            MoveVerdict("Kf7", "g7f7", "draws", "exact", human_pct=0.1),
            MoveVerdict("Kh7", "g7h7", "draws", "exact", human_pct=0.0),
        ]),
        rating=1180,
    )
    kinds = [b["beat"] for b in beats]
    assert "tempting" not in kinds
    assert "the move" in kinds          # the lesson itself still renders
    for b in beats:
        assert "0 in 100" not in b["text"]


def test_a_tempting_move_is_named_when_people_really_do_play_it():
    beats = render_script(
        _tree([
            MoveVerdict("a5", "a7a5", "draws", "exact", human_pct=17.9),
            MoveVerdict("Kh7", "g7h7", "draws", "exact", human_pct=0.2),
        ]),
        rating=1400,
    )
    tempting = [b for b in beats if b["beat"] == "tempting"]
    assert len(tempting) == 1
    assert "a5" in tempting[0]["text"]
    assert "18 in 100" in tempting[0]["text"]


def test_nothing_is_claimed_about_counting_when_there_is_no_race():
    # With bare_race None, no beat may mention counting or the king arriving.
    beats = render_script(_tree([]), rating=1180)
    joined = " ".join(b["text"] for b in beats).lower()
    assert "strip the board" not in joined
    assert "the king is in time" not in joined


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
