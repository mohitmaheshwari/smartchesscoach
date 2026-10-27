"""An imported game is identified by the platform's id, and the sync watermark
comes from the games the API returned -- never from the wall clock.

Both rules exist because of measured loss on a real account (2026-10-19,
user_8b599930d7ef, lichess `bhutramohit`):

* 7 of 61 games eligible by our own filters since Oct 1 were absent from the
  database -- 11% of everything played.
* The user's last game started 08:10:15 and ended 08:21:34. The sync ran at
  08:14:28 while it was still being played, so the API (which does not return
  in-progress games) returned only the previous game -- and the code then
  stamped `last_game_sync = now()` = 08:14:28. Lichess's `since` filters on
  when a game STARTED, so 08:10:15 now sits behind the watermark. Verified
  live: `since=08:14:28` returns nothing at all, `since=08:00:00` still
  returns the game. It could never be fetched again.
* 13 of the same user's 127 lichess games were stored TWICE, 11 of the pairs
  sharing an `imported_at` to the second -- two concurrent syncs each passing
  a check-then-act existence test. The two copies of `Jl8C0lUw` held PGNs of
  880 and 2675 bytes (one fetched without clocks), so the old `{"pgn": pgn}`
  dedup clause could not have matched them either, and both were analysed.
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from journey_service import (  # noqa: E402
    chesscom_archive_months,
    extract_platform_game_id,
    newest_fetch_marker,
    platform_identity_from_pgn,
    select_games_for_analysis,
)

UTC = timezone.utc


def _at(*args) -> datetime:
    return datetime(*args, tzinfo=UTC)


def _ms(*args) -> int:
    return int(_at(*args).timestamp() * 1000)


# ---------------------------------------------------------------- identity

def test_lichess_game_id_is_taken_from_the_payload():
    assert extract_platform_game_id({"id": "9cGrvqvz"}, "lichess") == "9cGrvqvz"


def test_chesscom_game_id_is_parsed_from_the_live_url():
    game = {"url": "https://www.chess.com/game/live/139284756201"}
    assert extract_platform_game_id(game, "chess.com") == "139284756201"


def test_chesscom_daily_games_are_recognised_too():
    game = {"url": "https://www.chess.com/game/daily/588123456"}
    assert extract_platform_game_id(game, "chess.com") == "588123456"


def test_an_unrecognisable_url_yields_no_id_rather_than_a_guess():
    """A wrong id is worse than none: it would collide two different games on
    the unique index. No id means the row simply is not covered by it."""
    assert extract_platform_game_id({"url": "https://www.chess.com/home"}, "chess.com") is None
    assert extract_platform_game_id({}, "chess.com") is None
    assert extract_platform_game_id({}, "lichess") is None
    assert extract_platform_game_id({"id": ""}, "lichess") is None


def test_the_two_stored_copies_of_one_game_resolve_to_the_same_identity():
    """The real duplicate pair. Their PGNs differ in length, so only a
    platform id can tell they are one game."""
    short_copy = {"id": "Jl8C0lUw", "pgn": "x" * 880}
    long_copy = {"id": "Jl8C0lUw", "pgn": "y" * 2675}
    assert (extract_platform_game_id(short_copy, "lichess")
            == extract_platform_game_id(long_copy, "lichess")
            == "Jl8C0lUw")


def test_the_manual_import_reads_the_same_identity_off_the_pgn():
    """POST /import-games holds only the PGN. It stored no id and no url, so 53
    of its 67 games on 2026-10-26 were second copies. The id and url it now
    reads must be the ones the sync stores for the same game."""
    live = '[Site "Chess.com"]\n[Link "https://www.chess.com/game/live/186001639478"]'
    assert platform_identity_from_pgn(live, "chess.com") == (
        extract_platform_game_id({"url": "https://www.chess.com/game/live/186001639478"}, "chess.com"),
        "https://www.chess.com/game/live/186001639478")
    daily = '[Site "Chess.com"]\n[Link "https://www.chess.com/game/daily/588123456"]'
    assert platform_identity_from_pgn(daily, "chess.com") == (
        "588123456", "https://www.chess.com/game/daily/588123456")
    assert platform_identity_from_pgn('[Site "https://lichess.org/fQMZOvey"]', "lichess") == (
        "fQMZOvey", "https://lichess.org/fQMZOvey")


def test_a_pgn_without_a_game_link_yields_no_identity():
    assert platform_identity_from_pgn('[Site "Chess.com"]', "chess.com") == (None, None)
    assert platform_identity_from_pgn("", "lichess") == (None, None)


# ---------------------------------------------------------------- watermark

def test_the_marker_is_the_newest_game_the_api_returned():
    games = [
        {"createdAt": _ms(2026, 10, 19, 8, 4, 33)},
        {"createdAt": _ms(2026, 10, 19, 5, 8, 52)},
    ]
    marker = newest_fetch_marker(games, "lichess")
    assert marker == int(_at(2026, 10, 19, 8, 4, 33).timestamp())


def test_an_in_progress_game_stays_inside_the_next_window():
    """THE REGRESSION. At 08:14:28 the API returns only TEnwZaFK, because
    9cGrvqvz (started 08:10:15) is still being played. The marker must land at
    or below 08:10:15, or that game is lost forever."""
    returned_at_sync_time = [{"createdAt": _ms(2026, 10, 19, 8, 4, 33)}]
    in_progress_started = int(_at(2026, 10, 19, 8, 10, 15).timestamp())
    sync_ran_at = int(_at(2026, 10, 19, 8, 14, 28).timestamp())

    marker = newest_fetch_marker(returned_at_sync_time, "lichess")

    assert marker < in_progress_started, "watermark jumped past a live game"
    assert marker < sync_ran_at, "watermark used the clock, not the data"


def test_nothing_returned_means_the_watermark_does_not_move():
    """None tells the caller to leave the watermark alone. Advancing it on an
    empty response is exactly how a live game gets skipped."""
    assert newest_fetch_marker([], "lichess") is None
    assert newest_fetch_marker([], "chess.com") is None


def test_each_platform_reads_the_field_its_own_filter_reads():
    """Lichess `since` compares createdAt (milliseconds); the chess.com fetch
    filters on end_time (seconds). A marker read from the wrong field is a
    watermark in the wrong units."""
    assert newest_fetch_marker([{"end_time": 1792397668}], "chess.com") == 1792397668
    assert newest_fetch_marker([{"createdAt": 1792397668000}], "lichess") == 1792397668
    # chess.com payloads carry no createdAt, and vice versa.
    assert newest_fetch_marker([{"createdAt": 1792397668000}], "chess.com") is None
    assert newest_fetch_marker([{"end_time": 1792397668}], "lichess") is None


def test_junk_timestamps_are_ignored_rather_than_trusted():
    games = [{"createdAt": None}, {"createdAt": 0}, {"createdAt": "yesterday"},
             {"createdAt": _ms(2026, 10, 19, 8, 4, 33)}]
    assert newest_fetch_marker(games, "lichess") == int(_at(2026, 10, 19, 8, 4, 33).timestamp())


# ------------------------------------------------------- import vs analysis

def _lichess_game(gid: str, finished_at: datetime) -> dict:
    return {"id": gid, "speed": "blitz", "rated": True,
            "moves": " ".join(["e4"] * 40), "lastMoveAt": int(finished_at.timestamp() * 1000)}


def test_import_is_uncapped_while_analysis_stays_capped():
    """The per-sync cap used to decide both. At 3 games a day a player who
    plays ten had seven dropped unseen, and the watermark advanced past them."""
    games = [_lichess_game(f"g{i}", _at(2026, 10, 19, 8, i)) for i in range(10)]

    assert len(select_games_for_analysis(games, "lichess", max_games=None)) == 10
    assert len(select_games_for_analysis(games, "lichess", max_games=3)) == 3


def test_the_platform_filters_still_exclude_what_we_never_want():
    """Uncapped is not unfiltered. Bullet stays skipped by design."""
    keep = _lichess_game("keep", _at(2026, 10, 19, 8, 0))
    bullet = dict(_lichess_game("bullet", _at(2026, 10, 19, 8, 1)), speed="bullet")
    unrated = dict(_lichess_game("unrated", _at(2026, 10, 19, 8, 2)), rated=False)
    stub = dict(_lichess_game("stub", _at(2026, 10, 19, 8, 3)), moves="e4 e5")

    kept = select_games_for_analysis([keep, bullet, unrated, stub], "lichess", max_games=None)
    assert [g["id"] for g in kept] == ["keep"]


# -------------------------------------------------- chess.com month archives

def test_a_month_boundary_still_reads_the_month_that_just_ended():
    """On the 1st the new archive is near-empty. Reading only it loses every
    late-month game not yet imported."""
    months = chesscom_archive_months(
        int(_at(2026, 10, 29).timestamp()), _at(2026, 11, 1, 3, 0))
    assert months == [(2026, 10), (2026, 11)]


def test_a_year_rollover_is_a_month_boundary_like_any_other():
    months = chesscom_archive_months(
        int(_at(2026, 12, 30).timestamp()), _at(2027, 1, 2))
    assert months == [(2026, 12), (2027, 1)]


def test_a_watermark_inside_the_current_month_reads_one_archive():
    months = chesscom_archive_months(
        int(_at(2026, 11, 1, 1, 0).timestamp()), _at(2026, 11, 1, 3, 0))
    assert months == [(2026, 11)]


def test_the_current_month_is_always_read_however_stale_the_watermark():
    """Walking forward from a stale watermark stranded the sync in old
    archives and never reached the games the player just played."""
    now = _at(2026, 11, 1, 3, 0)
    two_years_back = int((now - timedelta(days=730)).timestamp())
    for since in (two_years_back, int(_at(2026, 10, 29).timestamp()), None):
        months = chesscom_archive_months(since, now)
        assert months[-1] == (2026, 11), f"current month missing for since={since}"
        assert months == sorted(months), "archives must be read oldest-first"
