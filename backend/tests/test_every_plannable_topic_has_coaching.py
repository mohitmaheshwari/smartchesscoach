"""A topic that can be chosen must have something to say when it is.

time_management became plannable on 2026-09-26 and had no entry in _ONE_ACTION,
so every player on it read the generic fallback -- "Play one game today. Let's
see what it shows us." -- while holding hundreds of measured clock events. It
reached 8 users, including Mohit, who saw it on his own home page.

Nothing errored. The dict has a fallback, which is exactly why a missing entry
is silent.
"""
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from services import detector_quality as dq  # noqa: E402
from services.home_coach_conversation import (  # noqa: E402
    _FALLBACK_ACTION,
    _ONE_ACTION,
    get_player_safe_focus_copy,
)


def _plannable_topics():
    return sorted({
        quality_id.split(":")[1]
        for quality_id, auth in dq.explicit_authorizations().items()
        if quality_id.startswith("gap:") and auth.grade is dq.QualityGrade.PLAN
    })


def test_every_plannable_topic_has_an_authored_action():
    """The fallback is for topics nobody can be assigned, not for live ones."""
    missing = [t for t in _plannable_topics() if t not in _ONE_ACTION]
    assert not missing, (
        "these topics can be chosen as a focus but have no authored coaching "
        "line, so their players get the generic fallback: %s" % missing
    )


def test_no_plannable_topic_falls_back():
    for topic in _plannable_topics():
        copy = get_player_safe_focus_copy(topic)
        assert copy["reason"] != _FALLBACK_ACTION, topic
        assert copy["title"], topic


def test_the_clock_action_is_about_the_clock_not_the_board():
    """The first behavioural focus. Its action must not read like a board
    pattern, or it teaches the wrong thing entirely."""
    action = _ONE_ACTION["time_management"].lower()
    assert "time" in action or "clock" in action
    for board_word in ("piece", "king is", "capture", "hanging"):
        assert board_word not in action, board_word


def test_no_authored_action_carries_a_number():
    """Published text: simple English, no numbers."""
    import re

    for topic, action in _ONE_ACTION.items():
        assert not re.search(r"\d", action), (topic, action)
        assert "%" not in action, topic
