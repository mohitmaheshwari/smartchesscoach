"""Chronology must not depend on which importer wrote the row.

`date_played` holds two formats, and "2026." sorts AFTER "2026-" (0x2E > 0x2D),
so a lexical sort interleaves them: one user's 807 games ordered from
2026-04-17 to 2026.03.31, a maximum earlier than the minimum. Separately,
`date_played_iso` is written only by a one-off backfill, so a Mongo descending
sort on it drops the ~1,200 rows that lack the field to the end -- which made
time_management_service read a window ending 2026-08-30 and miss the player's
155 newest games.

Both failures are silent. They return wrong answers, not errors.
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.game_dates import (
    game_played_at,
    parse_game_date,
    sort_games_by_played_at,
    undated_count,
)


def test_parses_the_importer_iso_form_with_time():
    parsed = parse_game_date("2026-08-30T13:51:45+00:00")
    assert parsed == datetime(2026, 8, 30, 13, 51, 45, tzinfo=timezone.utc)


def test_parses_the_pgn_form():
    assert parse_game_date("2026.03.31") == datetime(2026, 3, 31, tzinfo=timezone.utc)


def test_parses_the_date_only_iso_form():
    assert parse_game_date("2026-08-30") == datetime(2026, 8, 30, tzinfo=timezone.utc)


def test_a_naive_datetime_is_treated_as_utc():
    assert parse_game_date(datetime(2026, 8, 30)).tzinfo is timezone.utc


def test_placeholders_and_junk_return_none_rather_than_a_guess():
    for value in ("????.??.??", "", None, "not a date", "0000.00.00", "1900-01-01"):
        assert parse_game_date(value) is None, value


def test_mixed_formats_order_correctly():
    # The exact failure: lexically "2026.03.31" > "2026-04-17", so a string
    # sort claims the March game is the newest.
    games = [
        {"game_id": "april", "date_played": "2026-04-17T18:53:44+00:00"},
        {"game_id": "march", "date_played": "2026.03.31"},
        {"game_id": "may", "date_played": "2026-05-02T09:00:00+00:00"},
    ]
    assert [g["game_id"] for g in sort_games_by_played_at(games)] == ["may", "april", "march"]
    lexical = sorted(games, key=lambda g: g["date_played"], reverse=True)
    assert lexical[0]["game_id"] == "march", "the bug this guards against"


def test_a_game_without_the_backfilled_field_is_not_dropped_to_the_end():
    # date_played_iso is absent on ~1,200 games; those are often the NEWEST.
    games = [
        {"game_id": "old_backfilled", "date_played": "2026-01-05T10:00:00+00:00",
         "date_played_iso": "2026-01-05"},
        {"game_id": "new_no_iso", "date_played": "2026-09-09T10:00:00+00:00"},
    ]
    assert sort_games_by_played_at(games)[0]["game_id"] == "new_no_iso"


def test_prefers_the_field_that_carries_a_time():
    # date_played_iso is date-only, so it cannot order games within a day.
    game = {"date_played": "2026-08-30T13:51:45+00:00", "date_played_iso": "2026-08-30"}
    assert game_played_at(game).hour == 13


def test_falls_back_when_the_importer_field_is_unusable():
    game = {"date_played": "????.??.??", "date_played_iso": "2026-08-30"}
    assert game_played_at(game) == datetime(2026, 8, 30, tzinfo=timezone.utc)


def test_undated_games_are_dropped_and_counted_not_defaulted():
    games = [
        {"game_id": "ok", "date_played": "2026-05-02T09:00:00+00:00"},
        {"game_id": "bad", "date_played": "????.??.??"},
    ]
    assert [g["game_id"] for g in sort_games_by_played_at(games)] == ["ok"]
    assert undated_count(games) == 1
