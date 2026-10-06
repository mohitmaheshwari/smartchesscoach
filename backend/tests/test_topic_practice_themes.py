"""A themed drill may only promise what the theme proves.

docs/home_session_scope.md

king_safety has 151 community puzzles and 341 coach positions and not one passes
verification: there is no king-safety prover, and none of those positions involve
mate, so they carry a classifier's opinion rather than evidence. Rather than
certify them anyway, practice comes from Lichess where the proof already exists.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from services.topic_practice_themes import (  # noqa: E402
    GENERIC_THEME_QUESTION, QUESTION_FOR_THEME, THEMES_FOR_TOPIC, blurb_for,
    mongo_query, question_for_themes, rating_window, themes_for,
)


def test_king_safety_does_not_borrow_attacking_themes():
    """backRankMate and kingsideAttack have huge supply and teach the OPPOSITE
    skill -- in both the solver is attacking a king, not defending one."""
    themes = set(themes_for("king_safety"))
    assert "backRankMate" not in themes
    assert "kingsideAttack" not in themes
    assert "defensiveMove" in themes


def test_every_topic_has_a_blurb_and_themes():
    for topic in THEMES_FOR_TOPIC:
        assert themes_for(topic), topic
        assert blurb_for(topic), topic


def test_an_unknown_topic_yields_no_query():
    assert themes_for("not_a_topic") == ()
    assert mongo_query("not_a_topic", 1200) == {}


def test_the_question_comes_from_the_theme():
    """A defensiveMove puzzle promises the answer is defensive and nothing about
    whose king is where. The first themed king_safety position served was a king
    and pawn endgame under the topic's question, 'Your king is the problem in
    this position', which was simply false about that board."""
    assert question_for_themes(["defensiveMove"]) == QUESTION_FOR_THEME["defensiveMove"]
    assert "king" not in question_for_themes(["defensiveMove"]).lower()


def test_several_themes_fall_back_rather_than_guess():
    """With two known themes the specific sentence might describe the other."""
    assert question_for_themes(["fork", "pin"]) == GENERIC_THEME_QUESTION


def test_an_unknown_theme_falls_back():
    assert question_for_themes(["someNewTheme"]) == GENERIC_THEME_QUESTION
    assert question_for_themes([]) == GENERIC_THEME_QUESTION
    assert question_for_themes(None) == GENERIC_THEME_QUESTION


def test_no_question_shows_a_number():
    for text in list(QUESTION_FOR_THEME.values()) + [GENERIC_THEME_QUESTION]:
        assert not re.search(r"[0-9%]", text), text


def test_the_rating_window_is_around_the_player():
    low, high = rating_window(1200)
    assert low < 1200 < high
    # A missing or junk rating must not produce an empty or absurd band.
    for junk in (None, "", "abc"):
        low, high = rating_window(junk)
        assert 600 <= low < high


def test_the_window_never_goes_below_the_corpus_floor():
    low, _ = rating_window(300)
    assert low >= 600


def test_the_query_filters_on_both_theme_and_rating():
    query = mongo_query("king_safety", 1200)
    assert "$in" in query["themes"]
    assert query["rating"]["$gte"] < query["rating"]["$lte"]
