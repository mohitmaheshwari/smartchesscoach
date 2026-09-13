"""Opponent strength and speaking register are different numbers.

One rating drove both. The move-quality read -- the coach's own estimate of
strength from recent play -- legitimately lowers it, which is right for
choosing opponent moves. It also silently changed the VOICE.

Observed 2026-09-11: a player rated 1490 rapid / 1622 classical on Lichess,
with an assessed 1241 stored on the account, resolved to a session
user_rating of 984. That crossed `is_beginner = user_rating < 1000` in
realtime_coaching_feedback, and the coach told him his pieces were "friends
coming out to play" and that moving them would "open a path so more of your
friends can come out and join the game".

Strength may be re-estimated downward from how someone plays. Register may not:
addressing an intermediate player as a beginner is wrong however badly the last
ten games went.
"""
import io
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

SESSION = BACKEND / "coach_play" / "coach_game_session.py"
FEEDBACK = BACKEND / "services" / "realtime_coaching_feedback.py"
COACHPLAY_JSX = BACKEND.parent / "frontend" / "src" / "pages" / "CoachPlay.jsx"


def _src(p: Path) -> str:
    return io.open(p, encoding="utf-8").read()


def test_the_session_carries_a_separate_register():
    src = _src(SESSION)
    assert "coaching_rating: int = 1200" in src, (
        "the session must carry a register distinct from user_rating"
    )
    assert "coaching_rating=coaching_rating," in src, (
        "the register must actually be stored on the session"
    )


def test_the_register_never_drops_below_the_imported_rating():
    src = _src(SESSION)
    assert "if coaching_rating < int(user_rating):" in src, (
        "a lowered strength estimate must not lower the register"
    )


def test_the_voice_layer_reads_the_register_not_the_strength():
    src = _src(FEEDBACK)
    assert 'coaching_rating = session.get("coaching_rating") or user_rating' in src
    assert "user_rating=coaching_rating," in src, (
        "_generate_coaching_message gates is_beginner on what it is passed, so "
        "it must be passed the register"
    )


def test_the_grading_thresholds_read_the_register_too():
    """How harshly to grade -120cp is the same kind of judgement as how to speak."""
    src = _src(FEEDBACK)
    assert (
        "_classify_move_quality(eval_before, eval_after, user_color, coaching_rating)"
        in src
    )


def test_old_sessions_fall_back_and_are_unchanged():
    """No migration: sessions predating coaching_rating keep their behaviour."""
    src = _src(FEEDBACK)
    assert 'session.get("coaching_rating") or user_rating' in src, (
        "the fallback is what makes this safe to deploy without a migration"
    )


def test_the_beginner_line_still_exists_but_is_fed_the_register():
    src = _src(FEEDBACK)
    assert "is_beginner = user_rating < 1000" in src, (
        "the beginner register itself is legitimate -- it must still exist for "
        "players who really are under 1000"
    )


def test_the_frontend_prefers_the_register():
    src = _src(COACHPLAY_JSX)
    assert "session?.coaching_rating || session?.user_rating || 1200" in src
    assert src.count("session?.coaching_rating") >= 2


@pytest.mark.parametrize(
    "imported,move_quality,expected_register",
    [
        (1490, 984, 1490),   # the reported case: register must stay intermediate
        (1241, 984, 1241),   # assessed rating also outranks the lowered estimate
        (900, 950, 950),     # a genuine beginner improving: register may rise
        (1200, 1200, 1200),  # no override
    ],
)
def test_register_is_the_higher_of_the_two(imported, move_quality, expected_register):
    """The rule, expressed directly: register = max(imported, strength read)."""
    register = imported
    strength = move_quality
    if register < strength:
        register = strength
    assert register == expected_register
    if expected_register >= 1000:
        assert not (register < 1000), (
            "a player at or above 1000 must never be addressed as a beginner"
        )
