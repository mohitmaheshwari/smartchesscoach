"""The behavioural half of Mohit's drill rule may not invent a cause.

Mohit, 2026-11-27: "chess is just not calculation and tactics, chess is also
focus and behavioral tactics, so that's what we want to track."

Measured 2026-11-27 over 1,200 games and 5,466 eligible one-move piece-safety
decisions (base rate 8.29%), using the opportunities that went FINE as the
denominator:

    time pressure (<60s left)            14.68% vs  8.05%   1.82x
    unravelling (big error in last 3)    10.14% vs  7.56%   1.34x
    late game (move 31+)                 10.42% vs  7.99%   1.30x
    snap move (<= 1/3 his own pace)       6.02% vs  8.49%   0.71x

...and nothing at all covered 50.3% of the errors.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from services import player_behaviour_reading as pbr  # noqa: E402


def _row(ply, *, clock=600.0, move_no=10, cp=0):
    return {"game_id": "g1", "ply": ply, "move_number": move_no,
            "time_left_seconds": clock, "cp_loss": cp}


def test_a_low_clock_is_named():
    assert pbr.cause_for_move(_row(20, clock=30.0),
                              after_big_error=False) == "time_pressure"


def test_an_error_right_after_an_error_is_named_as_that():
    rows = [_row(10, cp=400), _row(12), _row(14)]
    assert pbr.prior_big_error(rows, 2) is True
    assert pbr.cause_for_move(rows[2], after_big_error=True) == "unravelling"


def test_an_old_error_does_not_count_as_unravelling():
    # Only the last UNRAVEL_PLIES moves. A mistake eight moves ago is not
    # the reason for this one.
    rows = [_row(2, cp=400)] + [_row(p) for p in range(4, 20, 2)]
    assert pbr.prior_big_error(rows, len(rows) - 1) is False


def test_late_in_the_game_is_named_when_nothing_stronger_applies():
    assert pbr.cause_for_move(_row(70, move_no=40),
                              after_big_error=False) == "late_game"


def test_the_strongest_measured_cause_wins_when_several_are_true():
    # Low clock (1.82x) outranks unravelling (1.34x) and late game (1.30x).
    # Naming all three would say nothing.
    assert pbr.cause_for_move(_row(70, clock=20.0, move_no=40),
                              after_big_error=True) == "time_pressure"


def test_moving_fast_is_never_a_cause():
    # THE REFUSED HYPOTHESIS. A snap move is measurably SAFER than a
    # considered one (6.02% against 8.49%, 0.71x). "Eyesight" and "he rushed"
    # are the same guess, and this is the third time the data has refused it:
    # the teaching triage carried a `rushed` rule that was backwards too.
    # If this test ever fails, someone has reintroduced it.
    assert "rushed" not in pbr.CAUSE_WORDS
    assert "snap" not in pbr.CAUSE_WORDS
    assert "eyesight" not in pbr.CAUSE_WORDS
    assert not any("rushed" in c or "snap" in c for c in pbr.CAUSE_ORDER)
    # A fast move with a full clock, early, after a clean move: no cause.
    fast = {**_row(8, clock=600.0, move_no=4), "time_spent_seconds": 0.2}
    assert pbr.cause_for_move(fast, after_big_error=False) == "not_explained"


def test_nothing_to_point_at_says_so():
    rows = {"g1": [_row(8, clock=600.0, move_no=4)]}
    got = pbr.reading(rows, [("g1", 8)])
    assert got["cause"] == "not_explained"
    assert got["measured"]["unexplained"] == 1


def test_a_cause_is_not_claimed_when_most_errors_are_unexplained():
    # Half the errors have no explanation at all in the real corpus, so a
    # thin cause must not speak for the whole set.
    rows = {"g1": [
        _row(2, clock=20.0),                      # time pressure
        _row(4, clock=600.0, move_no=4),          # nothing
        _row(6, clock=600.0, move_no=4),          # nothing
        _row(8, clock=600.0, move_no=4),          # nothing
    ]}
    got = pbr.reading(rows, [("g1", 2), ("g1", 4), ("g1", 6), ("g1", 8)])
    assert got["cause"] == "not_explained"
    assert got["measured"]["by_cause"]["time_pressure"] == 1
    assert got["measured"]["unexplained"] == 3


def test_a_dominant_cause_is_claimed():
    rows = {"g1": [_row(p, clock=25.0) for p in (2, 4, 6)]
                  + [_row(8, clock=600.0, move_no=4)]}
    got = pbr.reading(rows, [("g1", p) for p in (2, 4, 6, 8)])
    assert got["cause"] == "time_pressure"
    assert got["measured"]["errors"] == 4


def test_no_errors_reads_nothing():
    assert pbr.reading({"g1": [_row(2)]}, []) is None


def test_the_player_facing_words_carry_no_digits():
    # The plan's standing rule: counts live in `measured`.
    for title, text in pbr.CAUSE_WORDS.values():
        assert not any(ch.isdigit() for ch in title), title
        assert not any(ch.isdigit() for ch in text), text


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
