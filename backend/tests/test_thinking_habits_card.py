"""Only habits that can separate two players are allowed to speak.

Measured on 59 players 2026-10-05. Three of the five habits put more than half
the population at exactly 100 -- king_safety 52%, patience 56%, tactical_vision
55% -- and those three were also the ones whose readings disagreed with the
area grades for the same user. One rule removes all three and both
contradictions: a habit whose median sits at the ceiling cannot speak.
"""
from __future__ import annotations

import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from services.thinking_habits_card import (  # noqa: E402
    CUTS, SATURATED_AND_SILENT, SENTENCES, build_card, eligible_habits,
)


def _progress(**scores):
    return {habit: {"current_score": value} for habit, value in scores.items()}


def test_a_saturated_habit_never_speaks():
    """Even at a rock-bottom score, because the measure cannot separate anyone."""
    card = build_card(_progress(king_safety=1.0, patience=1.0,
                                tactical_vision=1.0))
    assert card["measured"] is False
    assert card["lines"] == []


def test_the_silent_habits_are_named_with_a_reason():
    for habit, reason in SATURATED_AND_SILENT.items():
        assert habit not in CUTS, "%s is both silent and allowed to speak" % habit
        assert reason, "%s is silent with no reason recorded" % habit


def test_a_habit_below_its_cut_speaks():
    habit = "threat_awareness"
    card = build_card(_progress(**{habit: CUTS[habit] - 1}))
    assert card["measured"] is True
    assert [line["habit"] for line in card["lines"]] == [habit]


def test_a_habit_above_its_cut_is_silent():
    habit = "threat_awareness"
    card = build_card(_progress(**{habit: CUTS[habit] + 0.1}))
    assert card["measured"] is False


def test_a_missing_or_null_score_never_speaks():
    """The old card turned a null into a confident zero. It cannot now."""
    assert build_card({})["measured"] is False
    assert build_card(None)["measured"] is False
    assert build_card({"threat_awareness": {"current_score": None}})["measured"] is False
    assert build_card({"threat_awareness": {}})["measured"] is False


def test_every_eligible_habit_has_wording():
    for habit in eligible_habits():
        words = SENTENCES.get(habit)
        assert words, "%s can speak and has no sentence" % habit
        for field in ("headline", "body", "next"):
            assert words.get(field), "%s has no %s" % (habit, field)


def test_no_sentence_shows_a_number():
    """This card was the only one on /progress rendering a number."""
    import re
    for habit, words in SENTENCES.items():
        for field, text in words.items():
            assert not re.search(r"[0-9%]", text), (
                "%s.%s shows a number to the player: %r" % (habit, field, text))


def test_worst_measured_habit_leads():
    """The headline of the card is the first line, so order is not cosmetic."""
    card = build_card(_progress(threat_awareness=1.0, move_verification=1.0))
    assert [line["habit"] for line in card["lines"]][0] == "threat_awareness"


def test_cuts_are_below_the_ceiling():
    """A cut at 100 would let a saturated habit through the front door."""
    for habit, cut in CUTS.items():
        assert cut < 99.9, "%s has a cut at the ceiling" % habit
