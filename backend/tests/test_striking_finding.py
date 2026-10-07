"""A finding has to earn its place, and only one is ever shown.

Mohit, 2026-10-07: the data on the home page was not worth reading. A weekly
summary is something a player can work out for themselves; a finding is
something they cannot.

These tests hold the bars that stop a finding being a coincidence, and the rule
that the page shows exactly one.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from services.striking_finding import (  # noqa: E402
    MIN_EVENTS, MIN_SHARE, choose_finding, one_family_dominates,
    results_fade_in_a_sitting, spell, won_games_lost_on_time,
)


def test_too_few_games_is_not_a_finding():
    assert won_games_lost_on_time(MIN_EVENTS - 1, 100) is None


def test_a_small_share_is_not_a_finding():
    """Losing a couple of won games on time is ordinary chess."""
    assert won_games_lost_on_time(6, 1000) is None


def test_a_real_case_speaks_and_carries_the_count():
    out = won_games_lost_on_time(71, 160)
    assert out and "71" in out["headline"]
    assert out["evidence"]["winning"] == 71


def test_small_counts_are_spelled_and_large_ones_are_not():
    """Spelling keeps it reading like speech; past twenty the digit hits harder."""
    assert spell(10) == "ten"
    assert spell(96) == "96"
    assert "ten games" in won_games_lost_on_time(10, 20)["headline"]


def test_the_number_is_a_count_of_games_and_never_a_rate():
    """Counts are allowed here on purpose. Rates and percentages are not."""
    for winning, total in ((71, 160), (10, 20), (96, 205)):
        text = " ".join(
            str(v) for k, v in won_games_lost_on_time(winning, total).items()
            if k != "evidence")
        assert "%" not in text
        for token in re.findall(r"\d+", text):
            assert int(token) == winning, text


def test_a_flat_session_is_not_a_fade():
    assert results_fade_in_a_sitting(None) is None
    assert results_fade_in_a_sitting(1.7) is None
    assert results_fade_in_a_sitting(13.9) is not None


def test_one_family_needs_both_dominance_and_weakness():
    strong_alignment = [
        {"shape": "pin", "chances": 400, "took": 360, "share": 0.9, "judgeable": True},
        {"shape": "skewer", "chances": 400, "took": 360, "share": 0.9, "judgeable": True},
        {"shape": "fork", "chances": 100, "took": 50, "share": 0.5, "judgeable": True},
    ]
    # Dominant but NOT weak -- they take it more than anything else.
    assert one_family_dominates(strong_alignment) is None

    weak_alignment = [
        {"shape": "free_piece", "chances": 200, "took": 166, "share": 0.83, "judgeable": True},
        {"shape": "pin", "chances": 500, "took": 220, "share": 0.44, "judgeable": True},
        {"shape": "skewer", "chances": 400, "took": 168, "share": 0.42, "judgeable": True},
    ]
    assert one_family_dominates(weak_alignment) is not None


def test_a_shape_without_evidence_cannot_carry_the_finding():
    thin = [
        {"shape": "free_piece", "chances": 200, "took": 166, "share": 0.83, "judgeable": True},
        {"shape": "pin", "chances": 500, "took": 220, "share": 0.44, "judgeable": False},
        {"shape": "skewer", "chances": 400, "took": 168, "share": 0.42, "judgeable": False},
    ]
    assert one_family_dominates(thin) is None


def test_exactly_one_finding_is_returned():
    """Two findings on a page is a report again."""
    a = won_games_lost_on_time(71, 160)
    b = results_fade_in_a_sitting(13.9)
    out = choose_finding([a, b])
    assert out["kind"] == "won_games_lost_on_time"
    assert choose_finding([None, None]) is None


def test_the_order_is_strongest_first():
    only_fade = choose_finding([None, results_fade_in_a_sitting(13.9), None])
    assert only_fade["kind"] == "results_fade"


def test_the_bars_are_stated_not_implied():
    assert MIN_EVENTS >= 5 and 0 < MIN_SHARE < 1
