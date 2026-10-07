"""The coach must be able to say why it chose this topic, or say nothing.

Mohit, 2026-10-07: the card gave no reason to care. His own version carried a
number -- "I found this pattern in 4 of your last 7 games" -- and the standing
rule is no numbers. The stored narrative is worse: "235 events across 800 games.
68% of them (159 events) are games lost on time."

So the why is built from the SHAPE of the evidence, not its size.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from services.focus_why import (  # noqa: E402
    DOMINANT_SHARE, LEAD, WHY_BY_SUBTYPE, build_why,
)


def _focus(histogram):
    return {"topic_key": "piece_safety", "subtype_histogram": histogram}


def test_a_dominant_subtype_gets_its_own_sentence():
    why = build_why(_focus({"destination_safety_exact": {"count": 9},
                            "simple_hang": {"count": 1}}))
    assert why["subtype"] == "destination_safety_exact"
    assert why["line"] == WHY_BY_SUBTYPE["destination_safety_exact"]


def test_a_genuinely_mixed_focus_says_nothing():
    """"Most of it is one thing" must not be said when it is three things."""
    assert build_why(_focus({"destination_safety_exact": {"count": 4},
                             "simple_hang": {"count": 4},
                             "tactical_seq_loss": {"count": 4}})) is None


def test_the_dominance_bar_is_a_majority():
    assert DOMINANT_SHARE >= 0.5


def test_an_unauthored_subtype_says_nothing_rather_than_something_vague():
    """A vague why reads like the product is guessing, which is worse than
    none."""
    assert build_why(_focus({"some_new_subtype": {"count": 99}})) is None


def test_a_missing_or_empty_histogram_says_nothing():
    assert build_why(None) is None
    assert build_why({}) is None
    assert build_why(_focus({})) is None
    assert build_why(_focus({"destination_safety_exact": {"count": 0}})) is None


def test_a_bare_count_histogram_also_works():
    """Some documents store the count directly rather than under `count`."""
    why = build_why(_focus({"chronic_timeout": 7, "slow_paralysis": 1}))
    assert why and why["subtype"] == "chronic_timeout"


def test_no_sentence_contains_a_number():
    for text in list(WHY_BY_SUBTYPE.values()) + [LEAD]:
        assert not re.search(r"[0-9%]", text), text


def test_no_sentence_uses_jargon_the_audience_will_not_have():
    """Target is 600-1500. These sentences describe the board, not the label."""
    banned = ("centipawn", "cp", "detector", "subtype", "heuristic", "eval")
    for text in WHY_BY_SUBTYPE.values():
        lowered = text.lower()
        for word in banned:
            assert not re.search(r"\b%s\b" % word, lowered), (word, text)


def test_every_authored_sentence_describes_the_board():
    """Each one has to say what happened on the board, so it ends in a full
    sentence rather than a label."""
    for subtype, text in WHY_BY_SUBTYPE.items():
        assert text.endswith("."), subtype
        assert len(text.split()) >= 6, subtype
