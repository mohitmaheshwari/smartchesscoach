"""The week, the rhythm, and the two session readings that must not both fire.

docs/chances_not_games_scope.md
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from services.chess_habit_reading import (  # noqa: E402
    MIN_PER_SESSION_SLOT, MIN_PRIOR_WEEKS, MIN_WEEK_CHANCES, build_habits,
    results_fade, rhythm, session_curve, week_vs_usual,
)

FOUR_USUAL = [(100, 50)] * 4


def test_a_quiet_week_says_nothing():
    assert week_vs_usual((MIN_WEEK_CHANCES - 1, 5), FOUR_USUAL) is None


def test_no_history_means_no_comparison():
    assert week_vs_usual((100, 50), [(100, 50)] * (MIN_PRIOR_WEEKS - 1)) is None


def test_a_normal_week_is_called_normal():
    out = week_vs_usual((100, 50), FOUR_USUAL)
    assert out["verdict"] == "same"


def test_a_better_and_worse_week_are_distinguished():
    assert week_vs_usual((100, 70), FOUR_USUAL)["verdict"] == "better"
    assert week_vs_usual((100, 30), FOUR_USUAL)["verdict"] == "worse"


def test_rhythm_describes_and_never_scolds():
    for days in (28, 20, 10, 2):
        out = rhythm(days, 3)
        assert out and out["line"]
        assert not re.search(r"should|must|need to|lazy", out["line"], re.I)


def test_rhythm_says_nothing_when_nothing_was_played():
    assert rhythm(0, None) is None


def test_session_curve_needs_evidence_on_both_sides():
    thin = (MIN_PER_SESSION_SLOT - 1, 10)
    assert session_curve(thin, (500, 200)) is None
    assert session_curve((500, 300), thin) is None


def test_session_curve_refuses_an_unstable_fade():
    """Measured: half the players with enough games have a curve that flips."""
    early, later = (500, 300), (500, 200)      # a 20 point fade
    assert session_curve(early, later, halves=[20.0, 19.0]) is not None
    assert session_curve(early, later, halves=[20.0, 2.0]) is None


def test_results_fade_requires_the_contrast():
    """Its whole sentence is "results fall away but your eye does not". With
    conversion fading too there is no contrast and no sentence."""
    early, later = (500, 300), (500, 200)
    assert results_fade(early, later, conversion_fade=1.7) is not None
    assert results_fade(early, later, conversion_fade=20.0) is None
    assert results_fade(early, later, conversion_fade=None) is None


def test_the_two_session_readings_can_never_both_fire():
    """results_fade needs conversion flat; session_curve needs it fading."""
    early, later = (500, 300), (500, 200)
    for conversion in (1.0, 5.0, 12.0, 30.0):
        a = session_curve(early, later) if conversion >= 8.0 else None
        b = results_fade(early, later, conversion_fade=conversion)
        assert not (a and b)


def test_no_line_shows_a_number():
    lines = []
    w = week_vs_usual((100, 50), FOUR_USUAL)
    r = rhythm(20, 4)
    f = results_fade((500, 300), (500, 200), conversion_fade=1.0)
    for part in (w, r, f):
        if not part:
            continue
        lines += [v for k, v in part.items() if isinstance(v, str)]
    assert lines
    for text in lines:
        assert not re.search(r"[0-9%]", text), "shows a number: %r" % text


def test_build_habits_orders_week_then_rhythm_then_session():
    out = build_habits(
        week_vs_usual((100, 50), FOUR_USUAL),
        rhythm(20, 4),
        None,
        results_fade((500, 300), (500, 200), conversion_fade=1.0),
    )
    assert [l["kind"] for l in out["lines"]] == ["week", "rhythm", "results"]


def test_build_habits_is_empty_when_nothing_qualifies():
    out = build_habits(None, None, None, None)
    assert out["measured"] is False and out["lines"] == []
