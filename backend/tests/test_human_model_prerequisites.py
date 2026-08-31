"""The Phase 0 parsers must never invent a value or mis-order a date."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.backfill_human_model_prerequisites import (  # noqa: E402
    build_update,
    normalise_date,
    parse_clocks_seconds,
    parse_elos,
    player_opponent_elo,
)

PGN = (
    '[Event "Rated Rapid game"]\n'
    '[White "alice"]\n[Black "bob"]\n'
    '[WhiteElo "1268"]\n[BlackElo "1143"]\n'
    '[TimeControl "600+0"]\n\n'
    '1. e4 { [%clk 0:09:57] } e5 { [%clk 0:09:55] } '
    '2. Nf3 { [%clk 0:09:41] } Nc6 { [%clk 0:09:30] } *'
)


def test_parses_both_elo_tags():
    assert parse_elos(PGN) == {"White": 1268, "Black": 1143}


def test_player_and_opponent_follow_user_colour():
    assert player_opponent_elo(PGN, "white") == (1268, 1143)
    assert player_opponent_elo(PGN, "black") == (1143, 1268)


def test_junk_elo_tags_are_rejected():
    assert parse_elos('[WhiteElo "99999"]') == {}
    assert parse_elos('[WhiteElo "0"]') == {}
    assert parse_elos("no tags here") == {}


def test_missing_pgn_yields_no_elo():
    assert player_opponent_elo("", "white") == (None, None)
    assert player_opponent_elo(None, "white") == (None, None)


def test_clocks_parsed_in_game_order_as_seconds():
    assert parse_clocks_seconds(PGN) == [597, 595, 581, 570]


def test_clock_handles_hours_and_fractional_seconds():
    assert parse_clocks_seconds("[%clk 1:00:00]") == [3600]
    assert parse_clocks_seconds("[%clk 0:00:09.7]") == [9]


def test_absent_clocks_give_empty_list():
    assert parse_clocks_seconds("1. e4 e5") == []


def test_dotted_dates_normalise_to_iso():
    assert normalise_date("2026.03.31") == "2026-03-31"
    assert normalise_date("2026-04-17") == "2026-04-17"


def test_the_ordering_bug_this_field_exists_to_fix():
    # Raw strings compare wrongly: "." is ASCII 46, "-" is 45, so EVERY
    # dotted date sorts after EVERY dashed one -- March lands after April.
    assert "2026.03.31" > "2026-04-17"
    # Normalised, March correctly precedes April.
    assert normalise_date("2026.03.31") < normalise_date("2026-04-17")


def test_unparseable_dates_return_none_rather_than_a_guess():
    for value in (None, "", "not a date", "31/03/2026", "2026-13-45"):
        assert normalise_date(value) is None


def test_datetime_objects_are_accepted():
    from datetime import datetime
    assert normalise_date(datetime(2026, 3, 31, 14, 0)) == "2026-03-31"


def test_stored_rating_wins_over_pgn_tag():
    fields, stats = build_update({
        "pgn": PGN, "user_color": "white",
        "user_rating": 1300, "date_played": "2026-04-17",
    })
    assert fields["human_model.player_elo"] == 1300      # not 1268
    assert stats["elo_player_from_store"] == 1
    assert fields["human_model.opponent_elo"] == 1143    # gap filled from PGN
    assert stats["elo_opponent_from_pgn"] == 1


def test_gaps_are_filled_from_the_pgn():
    fields, stats = build_update({
        "pgn": PGN, "user_color": "black", "date_played": "2026.03.31",
    })
    assert fields["human_model.player_elo"] == 1143
    assert fields["human_model.opponent_elo"] == 1268
    assert fields["human_model.clocks_s"] == [597, 595, 581, 570]
    assert fields["date_played_iso"] == "2026-03-31"
    assert stats["date_reformatted"] == 1


def test_original_date_field_is_never_written():
    fields, _ = build_update({"pgn": PGN, "user_color": "white",
                              "date_played": "2026.03.31"})
    assert "date_played" not in fields          # only date_played_iso is set


def test_row_with_nothing_usable_produces_no_write():
    fields, stats = build_update({"pgn": "", "user_color": "white",
                                  "date_played": None})
    assert fields is None
    assert stats["elo_player_missing"] == 1
    assert stats["date_unparseable"] == 1


def test_player_clock_series_deinterleaves_the_two_sides():
    from scripts.backfill_human_model_prerequisites import player_clock_series
    plies = [908, 909, 916, 918, 925, 926]      # real row: tc 900+10
    assert player_clock_series(plies, "white") == [908, 916, 925]
    assert player_clock_series(plies, "black") == [909, 918, 926]


def test_clock_may_ascend_under_increment():
    from scripts.backfill_human_model_prerequisites import player_clock_series
    series = player_clock_series([908, 909, 916, 918, 925, 926], "white")
    assert series == sorted(series)              # increment adds time; not a bug


def test_clock_fraction_is_normalised_and_clamped():
    from scripts.backfill_human_model_prerequisites import clock_fraction
    fr = clock_fraction([450, 900, 225, 900], "white", base_seconds=900)
    assert fr == [0.5, 0.25]
    assert clock_fraction([1800], "white", base_seconds=900) == [1.0]   # clamped
    assert clock_fraction([100], "white", base_seconds=0) == []
