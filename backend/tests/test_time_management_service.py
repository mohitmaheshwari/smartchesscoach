"""A clock focus must be backed by the clock, or stay silent.

/training/pattern/time_collapse rendered an empty puzzle board while Progress
called time discipline the player's number one focus. The focus was right --
144 of 783 games lost on the clock -- but puzzles are the wrong intervention,
so there was nothing to show. These tests pin the arithmetic that replaces it.

See docs/time_management_practice_scope.md.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.time_management_service import (
    LONG_THINK_SECONDS,
    MIN_GAMES_FOR_PROFILE,
    build_time_profile,
    extract_own_move_times,
    _user_lost_on_time,
)


def _pgn(white_clocks, black_clocks):
    """Build a PGN whose stamps alternate White, Black."""
    moves = []
    for i, (w, b) in enumerate(zip(white_clocks, black_clocks), start=1):
        moves.append(f"{i}. e4 {{[%clk {w}]}} e5 {{[%clk {b}]}}")
    return " ".join(moves)


def _game(white_clocks, black_clocks, *, color="white", result="0-1",
          termination="timeout", tc="900+0", gid="g1"):
    return {
        "game_id": gid,
        "pgn": _pgn(white_clocks, black_clocks),
        "user_color": color,
        "result": result,
        "termination": termination,
        "time_control": tc,
    }


def test_move_times_are_the_drop_between_own_readings():
    # White: 900 -> 890 -> 860 means 10s then 30s.
    times = extract_own_move_times(
        _pgn(["0:15:00", "0:14:50", "0:14:20"], ["0:15:00", "0:14:59", "0:14:58"]),
        user_is_white=True,
        time_control="900+0",
    )
    assert times == [10.0, 30.0]


def test_increment_is_added_back():
    # With +10, a reading that only dropped 5s means 15s were actually spent.
    times = extract_own_move_times(
        _pgn(["0:15:00", "0:14:55"], ["0:15:00", "0:14:00"]),
        user_is_white=True,
        time_control="900+10",
    )
    assert times == [15.0]


def test_black_reads_the_other_half_of_the_stamps():
    times = extract_own_move_times(
        _pgn(["0:15:00", "0:14:00"], ["0:15:00", "0:14:40"]),
        user_is_white=False,
        time_control="900+0",
    )
    assert times == [20.0]


def test_a_timeout_win_is_not_a_timeout_loss():
    # Results are stored as '1-0'/'0-1' and must be read against colour. A
    # substring search for "time" finds nothing -- a real mistake made while
    # building this.
    assert _user_lost_on_time(
        {"termination": "timeout", "result": "1-0", "user_color": "black"}) is True
    assert _user_lost_on_time(
        {"termination": "timeout", "result": "0-1", "user_color": "black"}) is False
    assert _user_lost_on_time(
        {"termination": "checkmate", "result": "1-0", "user_color": "black"}) is False


def test_stays_silent_without_enough_clock_data():
    profile = build_time_profile([_game(
        ["0:15:00"] * 9, ["0:15:00"] * 9)])
    assert profile["eligible"] is False
    assert profile["reason"] == "not_enough_clock_data"


def _slow_game(gid):
    """A game where one move eats 120s and the rest are quick."""
    w = ["0:15:00", "0:14:55", "0:12:55", "0:12:50", "0:12:45", "0:12:40",
         "0:12:35", "0:12:30", "0:12:25", "0:12:20", "0:12:15"]
    b = ["0:15:00"] * len(w)
    return _game(w, b, gid=gid)


def test_profile_reports_the_long_think_and_where_it_landed():
    profile = build_time_profile([_slow_game(f"g{i}") for i in range(MIN_GAMES_FOR_PROFILE)])
    assert profile["eligible"] is True
    assert profile["timeout_losses"] == MIN_GAMES_FOR_PROFILE
    assert profile["timeout_loss_rate_pct"] == 100.0
    # The 120s think is the 2nd own move.
    assert profile["worst_think_seconds"] == 120
    assert profile["avg_longest_think_seconds"] == 120
    assert profile["long_thinks_per_game"] == 1.0
    assert profile["longest_think_phase"]["moves_1_10"] == MIN_GAMES_FOR_PROFILE
    assert profile["burn_moments"], "the burn moment is the curriculum for V3"
    assert profile["burn_moments"][0]["seconds"] == 120


def test_ordinary_play_is_not_reported_as_a_long_think():
    steady = ["0:15:00"] + [f"0:14:{60 - 5*i:02d}" for i in range(1, 11)]
    games = [_game(steady, ["0:15:00"] * len(steady), gid=f"s{i}")
             for i in range(MIN_GAMES_FOR_PROFILE)]
    profile = build_time_profile(games)
    assert profile["eligible"] is True
    assert profile["long_thinks_per_game"] == 0.0
    assert profile["worst_think_seconds"] < LONG_THINK_SECONDS
    assert profile["burn_moments"] == []
