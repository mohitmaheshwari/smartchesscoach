"""Lock the punish-rate line to its rules.

Two of these are Mohit's standing instructions rather than mechanics: no
number ever reaches the player, and the line is never a failure tally.
"""
import re
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from services.punish_rate_coaching import (  # noqa: E402
    LOWER_QUARTILE,
    MIN_CHANCES,
    UPPER_QUARTILE,
    band_for,
    punish_counts_from_observations,
    punish_rate_line,
)


def test_no_digit_ever_reaches_the_player():
    """No number in any rendered string. Percentages turn coaching into a
    report card; the audience is 600-1500."""
    for taken, total in ((3, 20), (11, 20), (16, 20)):
        out = punish_rate_line(taken, total)
        assert out is not None
        for field in ("headline", "habit", "text"):
            assert not re.search(r"\d", out[field]), (field, out[field])
            assert "%" not in out[field]


def test_every_band_has_its_own_words():
    seen = {punish_rate_line(t, 20)["headline"] for t in (3, 11, 16)}
    assert len(seen) == 3


def test_bands_follow_the_measured_quartiles():
    assert band_for(LOWER_QUARTILE - 0.01) == "low"
    assert band_for(LOWER_QUARTILE + 0.01) == "mid"
    assert band_for(UPPER_QUARTILE - 0.01) == "mid"
    assert band_for(UPPER_QUARTILE + 0.01) == "high"


def test_silent_until_there_is_a_pattern():
    """One missed chance is an incident. The line needs a habit behind it."""
    assert punish_rate_line(1, MIN_CHANCES - 1) is None
    assert punish_rate_line(5, MIN_CHANCES) is not None


def test_nonsense_input_is_refused_not_rendered():
    assert punish_rate_line(30, 20) is None
    assert punish_rate_line(-1, 20) is None


def test_the_habit_is_the_same_for_everyone():
    """The spread between players is small, so the transferable instruction
    does not change with the band -- only the opening clause does."""
    habits = {punish_rate_line(t, 20)["habit"] for t in (3, 11, 16)}
    assert len(habits) == 1


def test_never_a_failure_tally():
    for taken, total in ((3, 20), (11, 20), (16, 20)):
        text = punish_rate_line(taken, total)["text"].lower()
        for banned in ("missed", "failed", "times", "you lost"):
            assert banned not in text, (banned, text)


def test_counts_recomputed_not_trusted():
    """Rows written before 2026-09-25 used a stricter bar, counting a
    good-but-not-best move as failing to punish. The count is rebuilt from
    execution_quality and cp_loss."""
    observations = [
        # stored as missed, but it was a good move that cost almost nothing
        {"missed_opponent_blunder": True, "execution_quality": "good", "cp_loss": 10},
        {"punished_opponent_blunder": True, "execution_quality": "best", "cp_loss": 0},
        {"missed_opponent_blunder": True, "execution_quality": "blunder", "cp_loss": 400},
        # not a chance at all: neither flag set
        {"execution_quality": "good", "cp_loss": 5},
    ]
    counts = punish_counts_from_observations(observations)
    assert counts == {"chances_taken": 2, "chances_total": 3}
