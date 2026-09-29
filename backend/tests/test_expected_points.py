"""The scale has to behave like game points, not like centipawns.

The tests that matter here are the ones that would have caught the two things
the measurement actually found: that the curve has a ceiling below 1.0, and
that an even position is not worth half a point to these players. A logistic
passes neither.
"""
from __future__ import annotations

import pytest

from services.expected_points import (
    CEILING, EP_TABLE, EVEN, FLOOR,
    expected_points, ep_loss, headroom,
)


def test_the_curve_never_goes_backwards():
    """A better position is never worth fewer points."""
    last = -1.0
    for cp in range(-1600, 1601, 25):
        value = expected_points(cp)
        assert value >= last - 1e-9, "dipped at %d" % cp
        last = value


def test_a_won_position_is_not_worth_a_whole_point():
    """The measured ceiling is 0.873: these players throw one game in eight away.

    This is the assertion a fitted logistic fails, and it is the reason the
    module ships a table.
    """
    assert CEILING < 0.90
    assert expected_points(1500) == pytest.approx(CEILING)
    assert expected_points(9999) == pytest.approx(CEILING)


def test_a_lost_position_is_not_worth_nothing():
    assert FLOOR > 0.05
    assert expected_points(-1500) == pytest.approx(FLOOR)
    assert expected_points(-9999) == pytest.approx(FLOOR)


def test_an_even_position_is_not_half_a_point():
    """0.475, because this population loses rather more than it wins."""
    assert EVEN == pytest.approx(0.4746, abs=1e-4)
    assert expected_points(0) < 0.5


def test_it_interpolates_between_the_measured_buckets():
    low, high = EP_TABLE[200], EP_TABLE[250]
    middle = expected_points(225)
    assert low < middle < high
    assert middle == pytest.approx((low + high) / 2, abs=1e-6)


def test_a_missing_evaluation_returns_nothing_rather_than_a_guess():
    assert expected_points(None) is None
    assert ep_loss(None, 100) is None
    assert ep_loss(100, None) is None
    assert headroom(None) is None


# ── what the move cost ────────────────────────────────────────────────

def test_the_same_centipawn_loss_costs_different_amounts():
    """The whole point of the module, in one assertion.

    200 centipawns from level, and 200 centipawns from a position already lost.
    Under the old scale these are one event.
    """
    from_level = ep_loss(0, -200)
    from_lost = ep_loss(-1000, -1200)
    assert from_level > 0.08
    assert from_lost < 0.01
    assert from_level > from_lost * 10


def test_a_small_centipawn_loss_from_level_is_not_small():
    """60 centipawns is under every threshold we ship, and costs real points."""
    assert ep_loss(30, -30) > 0.03


def test_improving_the_position_costs_nothing_rather_than_a_negative():
    assert ep_loss(0, 300) == 0.0
    assert ep_loss(-200, 200) == 0.0


def test_throwing_away_a_won_game_is_the_most_expensive_thing_there_is():
    collapse = ep_loss(900, -100)
    assert collapse > 0.40
    assert collapse > ep_loss(0, -400)


# ── mate ──────────────────────────────────────────────────────────────

def test_mate_is_not_a_large_number_of_centipawns():
    assert expected_points(None, mate_in=3) == pytest.approx(CEILING)
    assert expected_points(None, mate_in=-3) == pytest.approx(FLOOR)
    # mate distance wins over any evaluation passed alongside it
    assert expected_points(-500, mate_in=2) == pytest.approx(CEILING)


def test_a_delivered_mate_banks_the_whole_point():
    """mate_in == 0 is the one case that really is worth 1.0: it is over."""
    assert expected_points(None, mate_in=0) == 1.0


def test_walking_into_mate_from_a_winning_position_is_scored_as_a_collapse():
    assert ep_loss(600, None, mate_after=-1) > 0.60


# ── headroom ──────────────────────────────────────────────────────────

def test_headroom_is_largest_when_winning_and_nil_when_lost():
    assert headroom(900) > 0.70
    assert headroom(-1300) < 0.01
    assert headroom(900) > headroom(0) > headroom(-600)


def test_a_mistake_in_a_hopeless_position_has_nothing_left_to_cost():
    """The 16.4% of our current fires that land here stop being raised."""
    assert ep_loss(-1200, -1400) < 0.01
    assert headroom(-1200) < 0.01
