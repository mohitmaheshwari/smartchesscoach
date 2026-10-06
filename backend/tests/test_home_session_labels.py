"""No number and no jargon reaches a player through a focus label.

docs/home_session_scope.md

Measured on prod 2026-10-06: 30 of 52 active focus documents have a number in
`coaching_label` -- "Piece safety (100% critical)", "Time management (90%
critical)". That field is already live and it is not safe to render. `topic_key`
and `topic_label` are clean.

A strength document is shaped differently again: it carries `label` ("Low
blunder rate") and no topic_key at all, so reading the weakness fields returned
an empty label for all 39 players who have a strength.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from services.home_session import clean_label  # noqa: E402


def test_a_label_with_a_number_is_refused():
    assert clean_label("Piece safety (100% critical)") == ""
    assert clean_label("Time management (90% critical)") == ""


def test_it_falls_through_to_the_first_clean_candidate():
    assert clean_label("Piece safety (100% critical)", "piece_safety") == "piece safety"


def test_underscores_become_spaces():
    assert clean_label("time_management") == "time management"


def test_nothing_clean_means_no_label_rather_than_a_bad_one():
    assert clean_label(None, "", "99%") == ""


def test_a_real_strength_label_survives():
    assert clean_label("Low blunder rate") == "Low blunder rate"


def test_no_candidate_ever_leaks_a_digit():
    for candidate in ("Piece safety (100% critical)", "90%", "x1", "1", "50 percent"):
        assert not re.search(r"[0-9%]", clean_label(candidate, "fallback"))
