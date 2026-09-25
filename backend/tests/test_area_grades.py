"""Lock the area grades to their rules."""
import re
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from services.area_grades import (  # noqa: E402
    AREAS,
    GRADES,
    LABELS,
    MIN_GAMES,
    PHASES,
    counts_from_observations,
    grade_areas,
    grade_for_rate,
)


def test_each_area_is_graded_against_its_own_band():
    """The whole point. 0.4 mistakes a game is better than most players at
    piece safety and worse than most at endgame technique, so one number must
    not produce one grade."""
    assert grade_for_rate("piece_safety", 0.4) == "Excellent"
    assert grade_for_rate("endgame_technique", 0.4) == "Needs work"


def test_grades_run_the_right_way_round():
    """These count mistakes, so fewer is better."""
    assert grade_for_rate("king_safety", 0.10) == "Excellent"
    assert grade_for_rate("king_safety", 0.75) == "Good"
    assert grade_for_rate("king_safety", 0.85) == "Fair"
    assert grade_for_rate("king_safety", 2.00) == "Needs work"


def test_too_few_games_is_not_a_grade():
    """A player with three games has shown us nothing. Scoring that as
    Excellent is the bug the thinking-habits card just had to fix."""
    out = grade_areas({}, games_played=MIN_GAMES - 1)
    assert out["measured"] is False
    assert all(r["grade"] is None and r["measured"] is False
               for r in out["areas"] + out["phases"])


def test_zero_mistakes_with_enough_games_is_excellent():
    out = grade_areas({}, games_played=40)
    assert all(r["grade"] == "Excellent" for r in out["areas"])


def test_every_area_and_phase_is_covered():
    out = grade_areas({"piece_safety": 10}, games_played=20)
    assert {r["key"] for r in out["areas"]} == set(AREAS)
    assert {r["key"] for r in out["phases"]} == set(PHASES)


def test_worst_comes_first():
    counts = {"piece_safety": 0, "king_safety": 100, "missed_tactic": 0,
              "opening_knowledge": 0, "endgame_technique": 0,
              "tactical_oversight": 0}
    out = grade_areas(counts, games_played=20)
    assert out["areas"][0]["key"] == "king_safety"
    assert out["areas"][0]["grade"] == "Needs work"


def test_no_number_is_ever_rendered():
    """Mohit's standing rule for anything published. The rate picks the
    grade; it never appears in a field meant for a screen."""
    out = grade_areas({"piece_safety": 33}, games_played=20)
    for row in out["areas"] + out["phases"]:
        for field in ("label", "grade"):
            value = row.get(field)
            if isinstance(value, str):
                assert not re.search(r"\d", value), (field, value)
                assert "%" not in value


def test_internal_numbers_are_underscored():
    """Anything a screen must not print is named so it is obvious."""
    out = grade_areas({"piece_safety": 5}, games_played=20)
    for row in out["areas"]:
        for key, value in row.items():
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                assert key.startswith("_"), key


def test_labels_are_plain_english():
    JARGON = ("material", "prophylaxis", "tempo", "zwischenzug", "fianchetto",
              "outpost", "counterplay", "compensation", "cognitive")
    for label in LABELS.values():
        low = label.lower()
        for term in JARGON:
            assert term not in low, (term, label)
        assert len(label.split()) <= 5, label


def test_grade_vocabulary_is_fixed():
    """Four grades, and "Needs work" rather than "Poor" -- it says the same
    thing without reading as a verdict on the person."""
    assert GRADES == ("Excellent", "Good", "Fair", "Needs work")


def test_counts_read_only_mistakes_and_blunders():
    observations = [
        {"execution_quality": "blunder", "missed_pattern": "king_safety",
         "phase": "middlegame"},
        {"execution_quality": "mistake", "missed_pattern": "king_safety",
         "phase": "opening"},
        {"execution_quality": "good", "missed_pattern": "king_safety",
         "phase": "opening"},
        {"execution_quality": "inaccuracy", "missed_pattern": "piece_safety",
         "phase": "endgame"},
    ]
    counts = counts_from_observations(observations)
    assert counts["king_safety"] == 2
    assert counts.get("piece_safety") is None
    assert counts["opening"] == 1
    assert counts["middlegame"] == 1
