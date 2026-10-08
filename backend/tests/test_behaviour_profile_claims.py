"""The balanced line may only claim what the middle band licenses.

Mohit, 2026-10-04: the one player on prod who receives this line has a
conversion rate in the third quartile -- 0.357 against a median of 0.33 -- and
68 of his analysed timeout losses were positions he was winning. The sentence
told him he finishes the games he should.

A trait inside the middle half means we are NOT SPEAKING about it. It never
means the flattering end is true. These tests pin that distinction, because it
is a wording mistake and a wording mistake never fails anything by itself.
"""
from __future__ import annotations

import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from services.behaviour_profile import (  # noqa: E402
    CUTS, MIN_MOVES, MIN_TIMED_MOVES, SENTENCES, build_profile, describe,
)


def _mid(key):
    low, high = CUTS[key]
    return (low + high) / 2.0


def _all_middle():
    return {key: _mid(key) for key in CUTS}


def _balanced_sentence():
    profile = build_profile(_all_middle(), moves=MIN_MOVES + 1,
                            timed_moves=MIN_TIMED_MOVES + 1,
                            samples={k: 10_000 for k in CUTS})
    lines = profile["lines"]
    assert len(lines) == 1 and lines[0]["trait"] == "balanced", lines
    return lines[0]["sentence"]


def test_balanced_line_makes_no_claim_about_finishing_games():
    sentence = _balanced_sentence().lower()
    for phrase in ("finish", "convert", "close it out", "see it through"):
        assert phrase not in sentence, (
            "the balanced line claims something about conversion (%r) while "
            "the conversion trait was never at an end" % phrase)


def test_balanced_line_does_not_reuse_a_trait_sentence():
    """Any trait's own wording appearing here is that trait being asserted
    without having crossed its cut."""
    sentence = _balanced_sentence().lower()
    for key, ends in SENTENCES.items():
        for end, text in ends.items():
            # Compare on the distinctive tail of each authored sentence rather
            # than the whole string, so a near-identical rewrite is caught too.
            tail = text.lower().rstrip(".").split(",")[-1].strip()
            if len(tail) < 18:
                continue
            assert tail not in sentence, (
                "the balanced line repeats the %s/%s sentence" % (key, end))


def test_a_trait_at_an_end_still_speaks():
    """Positive control: if nothing could ever speak, the tests above would
    pass on an empty profile and mean nothing."""
    traits = _all_middle()
    traits["throws_away_won_games"] = CUTS["throws_away_won_games"][1] + 0.05
    lines = describe(traits, {k: 10_000 for k in CUTS})
    assert any(line["trait"] == "throws_away_won_games" and line["end"] == "high"
               for line in lines), lines


def test_third_quartile_conversion_is_not_called_balanced_and_praised():
    """The exact shape of the live case: conversion worse than the median but
    below the cut. Silence is correct; praise is not."""
    traits = _all_middle()
    traits["throws_away_won_games"] = 0.357
    profile = build_profile(traits, moves=MIN_MOVES + 1,
                            timed_moves=MIN_TIMED_MOVES + 1,
                            samples={k: 10_000 for k in CUTS})
    joined = " ".join(line["sentence"] for line in profile["lines"]).lower()
    assert "finish" not in joined and "convert" not in joined, joined


def test_error_rate_is_measured_and_has_no_sentence():
    """Documents a real hole rather than asserting it is fine: error_rate has
    a cut and no wording, so it is computed for everyone and shown to nobody.
    If someone authors a sentence for it, this test should be deleted."""
    assert "error_rate" in CUTS
    assert "error_rate" not in SENTENCES, (
        "error_rate now has wording -- delete this test and check it renders")
