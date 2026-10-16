"""A clock focus has to know which time control the flag falls in.

Measured on one account: his flag falls in 33% of 180+2 games, 29% of 300+3,
21% of 600+0 and 5% of 900+10. Those are four different situations and only
some of them are about how he uses a clock -- the rest are about which control
he sits down to. A card that says "work on time management" without that split
cannot choose an action, and puzzles cannot train clock use in any case.

Two things this pins:

  * `games.time_control` does NOT hold the control. On that account every
    value was the platform category -- "rapid", "blitz", "untimed" -- while
    the PGN tag held 600, 300+3 and 180+2. Reading the field alone makes a
    ten-minute game and a three-minute game indistinguishable.
  * when a longer control he already plays loses the flag at less than half
    the rate, the card says so instead of promising practice.
"""
import asyncio
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from services.personal_curriculum import (
    _parse_time_control,
    _repair_candidate,
    clock_control_profile,
)


class _FakeCursor:
    def __init__(self, rows):
        self._rows = rows

    async def to_list(self, _limit):
        return list(self._rows)


class _FakeGames:
    def __init__(self, rows):
        self._rows = rows

    def aggregate(self, _pipeline):
        return _FakeCursor(self._rows)


class _FakeDb:
    def __init__(self, rows):
        self.games = _FakeGames(rows)


def _rows(control, games, timeout_losses, *, pgn_tag=True):
    out = []
    for i in range(games):
        lost_on_time = i < timeout_losses
        row = {
            "user_color": "white",
            "result": "0-1" if lost_on_time else "1-0",
            "termination": "timeout" if lost_on_time else "checkmate",
            "platform": "chess.com",
        }
        if pgn_tag:
            row["tag"] = {"captures": [control]}
        else:
            row["time_control"] = control
        out.append(row)
    return out


def _profile(rows):
    return asyncio.get_event_loop().run_until_complete(
        clock_control_profile(_FakeDb(rows), "u1")
    )


def test_the_category_string_is_not_a_time_control():
    """"rapid" and "blitz" carry no clock information at all."""
    for category in ("rapid", "blitz", "untimed", "", None):
        assert _parse_time_control(category) == (None, 0)


def test_the_pgn_tag_forms_parse():
    assert _parse_time_control("600") == (600, 0)
    assert _parse_time_control("300+3") == (300, 3)
    assert _parse_time_control("180+2") == (180, 2)


def test_the_control_is_read_from_the_pgn_tag():
    profile = _profile(_rows("300+3", 20, 6))
    assert [c["control"] for c in profile["controls"]] == ["300+3"]
    assert profile["controls"][0]["timeout_share_of_games"] == 30.0


def test_the_stored_field_is_used_when_the_tag_is_missing():
    """Some older imports did put the real control in `time_control`."""
    profile = _profile(_rows("900+10", 20, 1, pgn_tag=False))
    assert [c["control"] for c in profile["controls"]] == ["900+10"]


def test_controls_with_too_few_games_are_not_reported():
    profile = _profile(_rows("600+0", 40, 8) + _rows("180+2", 3, 3))
    assert [c["control"] for c in profile["controls"]] == ["600+0"]


def test_a_longer_control_that_halves_the_rate_is_surfaced():
    profile = _profile(_rows("600+0", 100, 21) + _rows("900+10", 20, 1))
    assert profile["most_played"]["control"] == "600+0"
    assert profile["lowest_timeout_control"]["control"] == "900+10"
    assert profile["a_longer_control_would_help"] is True


def test_a_longer_control_that_does_not_halve_it_is_not_surfaced():
    profile = _profile(_rows("600+0", 100, 21) + _rows("900+10", 20, 3))
    assert profile["a_longer_control_would_help"] is False


def test_a_shorter_control_is_never_offered_as_the_fix():
    """Even if the short control happens to look kinder in his record."""
    profile = _profile(_rows("600+0", 100, 30) + _rows("180+2", 20, 1))
    assert profile["lowest_timeout_control"]["control"] == "180+2"
    assert profile["a_longer_control_would_help"] is False


def _clock_focus():
    return {
        "topic_key": "time_management",
        "baseline_metric": {"occurrence_count": 231},
        "focus_id": "f-clock",
    }


def test_a_clock_card_names_the_control_rather_than_promising_practice():
    profile = _profile(_rows("600+0", 100, 21) + _rows("900+10", 20, 1))
    candidate = _repair_candidate(_clock_focus(), profile)
    just = candidate.public_dict()["justification"]
    assert "not a lesson" in just["why_activity"]
    assert "time control" in just["why_activity"]
    assert just["observed"]["clock_profile"]["a_longer_control_would_help"] is True


def test_a_clock_card_without_a_better_control_keeps_the_ordinary_wording():
    profile = _profile(_rows("600+0", 100, 21))
    candidate = _repair_candidate(_clock_focus(), profile)
    just = candidate.public_dict()["justification"]
    assert "not a lesson" not in just["why_activity"]
    # the evidence still travels, so the choice can be inspected
    assert just["observed"]["clock_profile"]["controls"][0]["control"] == "600+0"


def test_a_board_topic_never_gets_the_clock_wording():
    profile = _profile(_rows("600+0", 100, 21) + _rows("900+10", 20, 1))
    focus = {
        "topic_key": "piece_safety",
        "baseline_metric": {"occurrence_count": 252},
        "focus_id": "f-ps",
    }
    just = _repair_candidate(focus, profile).public_dict()["justification"]
    assert "not a lesson" not in just["why_activity"]
    assert "clock_profile" not in just["observed"]
