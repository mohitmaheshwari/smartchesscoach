"""The focus trend has to count the subtype the focus is actually about.

`dominant_subtype` is read from the focus document and nothing has ever
written it: 0 of 48 active weakness focuses carry the field. For the eight
time_management users that made the card read zero and render nothing; for the
other forty it silently counted the whole pattern instead of the focused
subtype.

These lock the derivation so a document written before the field existed still
works, and so a future writer of the field wins over the derivation.
"""
from __future__ import annotations

from services.focus_recall_stats import _dominant_subtype_of


def test_the_stamped_quality_id_is_used_when_the_field_is_missing():
    """This is the real shape on production: no dominant_subtype, but the
    picker stamped what it chose into detector_quality_id."""
    focus = {
        "topic_key": "time_management",
        "detector_quality_id": "gap:time_management:chronic_timeout",
        "subtype_histogram": {
            "chronic_timeout": {"count": 159},
            "time_pressure_blunder": {"count": 52},
            "slow_paralysis": {"count": 24},
        },
    }
    assert _dominant_subtype_of(focus) == "chronic_timeout"


def test_an_explicit_field_wins_over_the_derivation():
    """If something ever starts writing it, that is the authority."""
    focus = {
        "dominant_subtype": "slow_paralysis",
        "detector_quality_id": "gap:time_management:chronic_timeout",
    }
    assert _dominant_subtype_of(focus) == "slow_paralysis"


def test_the_histogram_is_the_fallback_when_there_is_no_stamped_id():
    focus = {
        "topic_key": "piece_safety",
        "subtype_histogram": {
            "destination_safety_exact": {"count": 193},
            "simple_hang": {"count": 42},
        },
    }
    assert _dominant_subtype_of(focus) == "destination_safety_exact"


def test_the_noise_buckets_do_not_win_on_volume():
    """small_slip outnumbers everything and teaches nothing. The shared helper
    in focus_bridge already knows that; this proves we inherit it rather than
    reimplementing the rule."""
    focus = {
        "topic_key": "piece_safety",
        "subtype_histogram": {
            "small_slip": {"count": 6073},
            "destination_safety_exact": {"count": 193},
        },
    }
    assert _dominant_subtype_of(focus) == "destination_safety_exact"


def test_a_malformed_quality_id_falls_through_rather_than_returning_junk():
    focus = {
        "topic_key": "king_safety",
        "detector_quality_id": "gap:king_safety",          # two parts, not three
        "subtype_histogram": {"ignored_king_attack": {"count": 183}},
    }
    assert _dominant_subtype_of(focus) == "ignored_king_attack"


def test_a_quality_id_from_another_namespace_is_not_treated_as_a_subtype():
    focus = {
        "topic_key": "piece_safety",
        "detector_quality_id": "review:verified_single_game_cause",
        "subtype_histogram": {"destination_safety_exact": {"count": 12}},
    }
    assert _dominant_subtype_of(focus) == "destination_safety_exact"


def test_nothing_to_go_on_returns_nothing_rather_than_guessing():
    assert _dominant_subtype_of({"topic_key": "piece_safety"}) is None
    assert _dominant_subtype_of({}) is None


# ── chronic_timeout is counted over games, not moves ─────────────────

from services.game_outcome import lost_on_time


def test_a_game_lost_on_time_counts():
    assert lost_on_time({"termination": "timeout", "result": "1-0",
                         "user_color": "black"}) is True
    assert lost_on_time({"termination": "timeout", "result": "0-1",
                         "user_color": "white"}) is True


def test_a_game_WON_on_time_does_not_count():
    """The opponent flagging is not the player's clock problem. This is the
    comparison game_outcome exists for -- reading 0-1 as a loss for everybody
    once picked a game the player had won for 46% of users."""
    assert lost_on_time({"termination": "timeout", "result": "0-1",
                         "user_color": "black"}) is False
    assert lost_on_time({"termination": "timeout", "result": "1-0",
                         "user_color": "white"}) is False


def test_losing_some_other_way_does_not_count_as_a_clock_problem():
    assert lost_on_time({"termination": "resignation", "result": "1-0",
                         "user_color": "black"}) is False
    assert lost_on_time({"termination": "checkmate", "result": "1-0",
                         "user_color": "black"}) is False


def test_a_missing_termination_is_not_a_timeout():
    assert lost_on_time({"result": "1-0", "user_color": "black"}) is False
    assert lost_on_time({}) is False
