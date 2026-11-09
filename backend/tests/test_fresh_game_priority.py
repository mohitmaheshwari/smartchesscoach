"""A just-finished synced game is analysed as a live game, and the home page
shows the game played last, not the one imported last.

2026-11-09: Mohit's lichess game, finished minutes earlier, was queued at
priority 9 behind 46 jobs, and the home page kept showing an older game
because it sorted by import time.
"""
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from journey_service import FRESH_GAME_WINDOW, LIVE_GAME_PRIORITY, is_fresh_game  # noqa: E402

NOW = datetime(2026, 11, 9, 12, 0, tzinfo=timezone.utc)


def test_a_game_that_started_minutes_ago_is_fresh():
    assert is_fresh_game(NOW - timedelta(minutes=20), now=NOW)


def test_the_window_edge_is_fresh_and_just_past_it_is_not():
    assert is_fresh_game(NOW - FRESH_GAME_WINDOW, now=NOW)
    assert not is_fresh_game(NOW - FRESH_GAME_WINDOW - timedelta(seconds=1), now=NOW)


def test_an_old_game_imported_late_is_not_fresh():
    # A backfill or re-fetch imports old games today; they must not jump the queue.
    assert not is_fresh_game(NOW - timedelta(days=40), now=NOW)


def test_mongo_naive_datetimes_are_read_as_utc():
    # pymongo returns BSON dates as naive UTC datetimes.
    assert is_fresh_game((NOW - timedelta(minutes=5)).replace(tzinfo=None), now=NOW)


def test_missing_or_untyped_start_time_is_not_fresh():
    assert not is_fresh_game(None, now=NOW)
    assert not is_fresh_game("2026-11-09T11:50:00+00:00", now=NOW)


def test_a_start_time_in_the_future_is_not_fresh():
    assert not is_fresh_game(NOW + timedelta(minutes=10), now=NOW)


def test_live_priority_sits_above_routine_sync_and_below_first_sync():
    assert 9 < LIVE_GAME_PRIORITY < 20


def test_the_sync_raises_a_fresh_game_to_live_priority():
    src = open(os.path.join(os.path.dirname(__file__), "..", "journey_service.py"), encoding="utf-8").read()
    assert 'is_fresh_game(game_doc.get("played_at_utc"))' in src
    assert '"priority": _priority,' in src


def test_home_picks_the_last_game_and_streak_by_play_time():
    src = open(os.path.join(os.path.dirname(__file__), "..", "routes", "home.py"), encoding="utf-8").read()
    assert 'LAST_PLAYED_SORT = [("played_at_utc", -1), ("imported_at", -1)]' in src
    assert src.count("LAST_PLAYED_SORT") >= 3  # definition, last game, streak
