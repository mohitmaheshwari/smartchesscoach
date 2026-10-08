"""The chance is the unit, and no authored string carries a number.

docs/chances_not_games_scope.md
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from services.chances_reading import (  # noqa: E402
    MIN_CHANCES, MIN_CHANCES_PER_SHAPE, SHAPE_WORDS, WEAKEST_LINE,
    build_reading,
)


def _stored(chances, took, by_pattern=None):
    return {"chances": chances, "took": took, "by_pattern": by_pattern or {}}


def test_too_few_chances_says_nothing():
    card = build_reading(_stored(MIN_CHANCES - 1, 0))
    assert card["measured"] is False
    assert "headline" not in card


def test_missing_document_says_nothing():
    assert build_reading(None)["measured"] is False
    assert build_reading({})["measured"] is False


def test_a_shape_without_its_own_evidence_is_not_named():
    """One chance at forcing the king is not a finding about a player."""
    card = build_reading(_stored(400, 200, {
        "pin": {"chances": 200, "took": 80},
        "force_the_king": {"chances": 1, "took": 0},
    }))
    assert card["weakest"]["shape"] == "pin"
    thin = [s for s in card["shapes"] if s["shape"] == "force_the_king"][0]
    assert thin["judgeable"] is False


def test_weakest_is_the_lowest_share_with_enough_evidence():
    card = build_reading(_stored(600, 300, {
        "free_piece": {"chances": 200, "took": 180},
        "pin": {"chances": 200, "took": 90},
        "skewer": {"chances": 200, "took": 60},
    }))
    assert card["weakest"]["shape"] == "skewer"
    assert card["weakest_line"] == WEAKEST_LINE["skewer"]


def test_shapes_are_ordered_strongest_first():
    card = build_reading(_stored(600, 300, {
        "skewer": {"chances": 200, "took": 60},
        "free_piece": {"chances": 200, "took": 180},
        "pin": {"chances": 200, "took": 90},
    }))
    shares = [s["share"] for s in card["shapes"]]
    assert shares == sorted(shares, reverse=True)


def test_no_authored_string_contains_a_number():
    """Counts ride in their own fields so the surface can decide."""
    card = build_reading(_stored(600, 300, {
        "pin": {"chances": 300, "took": 90},
        "skewer": {"chances": 300, "took": 200},
    }))
    strings = [card["headline"], card.get("weakest_line") or ""]
    strings += [s["label"] for s in card["shapes"]]
    strings += list(SHAPE_WORDS.values()) + list(WEAKEST_LINE.values())
    for text in strings:
        assert not re.search(r"[0-9%]", text), "shows a number: %r" % text


def test_headline_moves_with_the_share():
    low = build_reading(_stored(100, 10))["headline"]
    mid = build_reading(_stored(100, 50))["headline"]
    high = build_reading(_stored(100, 90))["headline"]
    assert low != mid != high
    assert len({low, mid, high}) == 3


def test_practice_is_left_for_the_caller():
    """The service cannot know whether a drill has positions behind it."""
    assert build_reading(_stored(100, 50))["practice"] is None


def test_the_per_shape_bar_is_never_above_one():
    card = build_reading(_stored(100, 100, {"pin": {"chances": 100, "took": 100}}))
    assert card["shapes"][0]["share"] == 1.0


def test_shape_evidence_bar_is_stated_not_inferred():
    assert MIN_CHANCES_PER_SHAPE > MIN_CHANCES
