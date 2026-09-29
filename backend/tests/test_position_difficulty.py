"""The base rate has to separate positions, or it is not worth carrying.

The test that matters is the one that would fail if difficulty turned out to be
flat: a table where every cell reads about the average buys nothing, and
shipping it would let a detector claim a position was hard when it was not.
"""
from __future__ import annotations

import pytest

from services.position_difficulty import (
    BY_PHASE_EVAL, DIFFICULTY, HARD, MIN_CELL_N, OVERALL, ROUTINE, TESTING,
    band_of, base_rate, difficulty_class, phase_of, relative_error,
)


def test_the_table_actually_separates_positions():
    """145x between the hardest and easiest cell. If this ever collapses
    toward 1, the conditioning has stopped meaning anything."""
    rates = [r for r, n in DIFFICULTY.values() if n >= MIN_CELL_N]
    assert max(rates) / min(rates) > 20, "difficulty is flat; it buys nothing"


def test_answering_a_threat_is_the_hard_case():
    quiet = base_rate("middlegame", 0, has_threat=False)[0]
    sharp = base_rate("middlegame", 0, has_threat=True)[0]
    assert sharp > quiet * 10
    assert difficulty_class("middlegame", 0, False) == ROUTINE
    assert difficulty_class("middlegame", 0, True) == HARD


def test_the_middle_class_exists_and_is_not_an_empty_bucket():
    """A threat early on, before anyone has anything to play for, is the honest
    middle case -- 0.0538, and it carries about a quarter of all captions."""
    assert difficulty_class("opening", 0, True) == TESTING


def test_a_lost_position_is_easy_because_nothing_is_left_to_lose():
    """Not because the moves are simple -- because expected points have already
    bottomed out. This is the same fact `headroom` carries."""
    assert difficulty_class("middlegame", -900, False) == ROUTINE
    assert base_rate("endgame", -900, False)[0] < 0.01


# ── the fallback ──────────────────────────────────────────────────────

def test_every_cell_in_this_table_has_enough_behind_it():
    """v1 had seven cells under the bar, the smallest holding nine positions.
    Dropping is_critical merged them away and the thinnest cell now holds 427,
    so nothing in v2 falls back on thinness. The machinery stays for the next
    refit, which may well produce one."""
    thin = {k: n for k, (_, n) in DIFFICULTY.items() if n < MIN_CELL_N}
    assert not thin, "thin cells are being used as base rates: %s" % thin


def test_a_cell_with_enough_behind_it_is_used_directly():
    rate, n, source = base_rate("opening", 0, False)
    assert source == "cell"
    assert n > 100000


def test_an_unknown_phase_falls_all_the_way_back_rather_than_guessing():
    rate, n, source = base_rate("nonsense", 0, False)
    assert source == "overall"
    assert rate == OVERALL


# ── bands and phases ──────────────────────────────────────────────────

def test_bands_are_read_from_the_players_own_side():
    assert band_of(-900) == "losing"
    assert band_of(-300) == "worse"
    assert band_of(0) == "level"
    assert band_of(300) == "better"
    assert band_of(900) == "winning"
    assert band_of(None) == "level"


def test_band_edges_do_not_fall_through():
    for cp in (-600, -200, 200, 600):
        assert band_of(cp) in {"losing", "worse", "level", "better", "winning"}
    assert band_of(-600) == "worse"
    assert band_of(600) == "winning"


def test_phase_defaults_to_middlegame_when_the_move_number_is_missing():
    assert phase_of(None) == "middlegame"
    assert phase_of(8) == "opening"
    assert phase_of(30) == "middlegame"
    assert phase_of(60) == "endgame"


# ── the comparison that decides what gets raised ──────────────────────

def test_a_typical_mistake_in_a_hard_position_is_not_remarkable():
    """The point of the module: cost alone cannot tell these apart."""
    rate, _, _ = base_rate("middlegame", 0, True)
    assert relative_error(rate, "middlegame", 0, True) == pytest.approx(1.0)


def test_the_same_cost_means_very_different_things_in_two_positions():
    # Read the cost off the hard cell rather than hardcoding one: a literal
    # here is a transcription of the table and breaks on every refit.
    cost = base_rate("middlegame", 0, True)[0]
    in_a_hard_spot = relative_error(cost, "middlegame", 0, True)
    out_of_nowhere = relative_error(cost, "opening", 0, False)
    assert in_a_hard_spot == pytest.approx(1.0, abs=0.01)
    assert out_of_nowhere > 20
    assert out_of_nowhere > in_a_hard_spot * 10


def test_no_actual_loss_returns_nothing_rather_than_a_guess():
    assert relative_error(None, "middlegame", 0, True) is None


def test_the_module_returns_classes_and_never_prose():
    """Coaching words live in the caption layer, which is the one place they
    are written. A sentence escaping from here is a second source of truth."""
    value = difficulty_class("middlegame", 0, True)
    assert value in {ROUTINE, TESTING, HARD}
    assert " " not in value
