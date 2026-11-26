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


# ---------------------------------------------------------------------------
# The triage. Mohit, 2026-11-26: "even best players like Magnus can sometimes
# let a piece undefended... human coaches don't give you exercise when you
# blunder something from eyesight, because they know you know this."
# ---------------------------------------------------------------------------

from services.teaching_script_builder import (  # noqa: E402
    candidate_positions_from_pgn,
    triage,
)


def test_a_fast_move_is_still_teachable():
    # This test asserted the opposite until 2026-11-26. The rule was that a
    # quick move meant they knew it and slipped, so no lesson. Measured over
    # 44,580 big errors, a 0-1s error is a knowledge gap 21.7% of the time
    # against 6.8% at 30s+ -- fast errors are three times MORE likely to be
    # genuine ignorance, because moving instantly means not noticing there
    # was anything to think about. The old rule withheld teaching from the
    # players who needed it most.
    v = triage({"think_seconds": 1.4, "clock_seconds": 400.0})
    assert v["verdict"] == "knowledge_gap"
    assert v["cause"] != "rushed"


def test_a_move_in_time_trouble_is_not_a_knowledge_gap():
    v = triage({"think_seconds": 20.0, "clock_seconds": 18.0})
    assert v["verdict"] == "execution_failure"
    assert v["cause"] == "time_pressure"


def test_what_their_own_rating_already_finds_is_not_taught():
    # The Magnus case: the concept is known at this level, so a drill on it
    # is the thing that makes a competent player leave.
    v = triage({"think_seconds": 30.0, "clock_seconds": 500.0},
               band_solve_pct=88.0)
    assert v["verdict"] == "execution_failure"
    assert v["cause"] == "known_by_their_level"


def test_time_to_think_and_their_level_does_not_find_it_is_teachable():
    v = triage({"think_seconds": 42.0, "clock_seconds": 600.0},
               band_solve_pct=31.0)
    assert v["verdict"] == "knowledge_gap"


def test_no_evidence_either_way_stays_teachable():
    # Withholding a lesson on no evidence helps nobody.
    v = triage({"think_seconds": None, "clock_seconds": None})
    assert v["verdict"] == "unclear"


PGN_WITH_CLOCKS = """[Event "rated rapid game"]
[TimeControl "900+10"]
[Result "*"]

1. e4 {[%clk 0:15:08]} 1... e5 {[%clk 0:15:05]} 2. Nf3 {[%clk 0:15:14]} 2... Nc6 {[%clk 0:14:20]} *
"""


def test_the_clock_and_the_think_time_are_read_off_the_pgn():
    # Without these the triage has nothing to go on, and every mistake looks
    # like ignorance.
    cands = candidate_positions_from_pgn(PGN_WITH_CLOCKS, user_color="white",
                                         max_men=32)
    assert len(cands) == 4
    # Black's second move: 15:05 -> 14:20 is 45s spent, plus the 10s increment.
    black_second = cands[3]
    assert black_second["clock_seconds"] == pytest.approx(860.0)
    assert black_second["think_seconds"] == pytest.approx(55.0)
    # The first move of each side has no previous reading, so no think time.
    assert cands[0]["think_seconds"] is None


def test_a_pgn_without_clocks_still_produces_candidates():
    plain = '[Result "*"]\n\n1. e4 e5 2. Nf3 *\n'
    cands = candidate_positions_from_pgn(plain, user_color="white", max_men=32)
    assert len(cands) == 3
    assert all(c["clock_seconds"] is None for c in cands)
