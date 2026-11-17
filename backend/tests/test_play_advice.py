"""Home behaviour line and clock advice (services/play_advice.py).

docs/home_behaviour_and_clock_scope.md. The 3+2 case mirrors Mohit's
measured record: 35% at 3+2, 54% at 5+3, most 3+2 losses on time.
"""
from datetime import datetime, timedelta, timezone

from services import play_advice as pa

T0 = datetime(2026, 6, 1, tzinfo=timezone.utc)


def _rows(clock, wins, losses, on_time, start=0, analysed=False, prefix="g"):
    out = []
    for i in range(wins + losses):
        loss = i >= wins
        out.append({"clock": clock, "out": "loss" if loss else "win", "on_time": loss and (i - wins) < on_time,
                    "at": T0 + timedelta(hours=start + i), "game_id": f"{prefix}{start + i}", "analysed": analysed})
    return out


def _interleave(rows):
    """Spread wins and losses evenly in time so both halves look alike."""
    wins = [r for r in rows if r["out"] == "win"]
    losses = [r for r in rows if r["out"] == "loss"]
    start = min(r["at"] for r in rows)
    n, n_loss = len(rows), len(losses)
    merged = [losses.pop() if (k * n_loss) % n < n_loss else wins.pop() for k in range(n)]
    for k, r in enumerate(merged):
        r["at"] = start + timedelta(hours=k)
    return merged


def test_a_clock_that_goes_badly_on_the_clock_is_named_with_the_one_to_play_instead():
    three_two = _interleave(_rows((180, 2), 28, 52, 30, start=0))
    five_three = _interleave(_rows((300, 3), 94, 80, 30, start=1000))
    advice = pa.clock_advice(three_two + five_three)
    assert advice["clocks"] == ["3+2"] and advice["instead"] == "5+3"
    assert advice["headline"] == "Your 3+2 games go badly, mostly on the clock."
    assert advice["detail"] == "Your 5+3 games go better. Play 5+3 instead."


def test_no_advice_when_the_losses_are_not_on_the_clock():
    rows = _interleave(_rows((180, 2), 28, 52, 10)) + _interleave(_rows((300, 3), 94, 80, 30, start=1000))
    assert pa.clock_advice(rows) is None


def test_no_advice_when_the_player_has_grown_out_of_it():
    # Bad first half, fine second half: Mohit's 2+1 (17% then 50%).
    early = _rows((120, 1), 2, 10, 8, start=0)
    late = _rows((120, 1), 6, 6, 3, start=100)
    rows = early + late + _interleave(_rows((300, 3), 94, 80, 30, start=1000))
    assert pa.clock_advice(rows) is None


def test_no_advice_when_the_mistakes_there_are_clearly_worse():
    three_two = _interleave(_rows((180, 2), 28, 52, 30, analysed=True, prefix="a"))
    five_three = _interleave(_rows((300, 3), 94, 80, 30, start=1000, analysed=True, prefix="b"))
    per_game = {r["game_id"]: (4, 40) for r in three_two}
    per_game.update({r["game_id"]: (1, 40) for r in five_three})
    rows = three_two + five_three
    assert pa.ids_for_mistake_check(rows)
    assert pa.clock_advice(rows, pa.slips_from(per_game)) is None
    same = {gid: (2, 40) for gid in per_game}
    assert pa.clock_advice(rows, pa.slips_from(same))["clocks"] == ["3+2"]


def test_too_few_games_says_nothing_and_reads_nothing():
    rows = _interleave(_rows((180, 2), 2, 12, 10)) + _interleave(_rows((300, 3), 94, 80, 30, start=1000))
    assert pa.clock_advice(rows) is None
    assert pa.ids_for_mistake_check(rows) == []


def test_clock_rows_read_pgn_clocks_and_skipped_bullet_records():
    games = [{"game_id": "x", "pgn": '[TimeControl "180+2"]', "result": "0-1", "user_color": "white",
              "termination": "Black won on time", "is_analyzed": True, "played_at_utc": T0}]
    skipped = [{"base_seconds": 120, "increment_seconds": 1, "result": "loss", "ending": "time", "rated": True},
               {"base_seconds": 60, "increment_seconds": 0, "result": "win", "ending": "mate", "rated": False}]
    rows = pa.clock_rows(games, skipped)
    assert [(r["clock"], r["out"], r["on_time"]) for r in rows] == [((180, 2), "loss", True), ((120, 1), "loss", True)]
    assert [pa.clock_name(*c) for c in [(180, 2), (30, 0), (60, 0), (900, 10)]] == ["3+2", "½+0", "1+0", "15+10"]


def _move(n, ev, quality, opp=False):
    return {"move_number": n, "eval_before": ev, "evaluation": quality, "is_opponent_move": opp, "move": f"m{n}"}


def test_behaviour_names_a_won_position_that_slipped_with_the_mistake_after_the_mistake():
    game = {"game_id": "g", "user_color": "black", "result": "1-0", "termination": "White won by resignation"}
    # Black's side: +4 at move 20 (eval -400 from White), then a blunder and a mistake two moves later.
    rows = [_move(20, -400, "good"), _move(21, -380, "blunder"), _move(22, 50, "good"), _move(23, 80, "mistake")]
    line = pa.behaviour_line(game, rows)
    assert line["kind"] == "winning_chain"
    assert line["headline"] == "You were winning, and then one mistake brought another."


def test_behaviour_on_time_while_winning_and_silence_on_a_clean_win():
    lost = {"game_id": "g", "user_color": "white", "result": "0-1", "termination": "Black won on time"}
    assert pa.behaviour_line(lost, [_move(30, 450, "good")])["kind"] == "winning_clock"
    won = {"game_id": "g", "user_color": "white", "result": "1-0", "termination": "White won by checkmate"}
    assert pa.behaviour_line(won, [_move(30, 450, "good"), _move(31, 600, "good")]) is None


def test_a_mistake_far_after_the_blunder_is_not_a_chain():
    game = {"game_id": "g", "user_color": "white", "result": "1-0", "termination": "x"}
    rows = [_move(10, 0, "blunder")] + [_move(10 + k, 0, "good") for k in range(1, 6)] + [_move(16, 0, "mistake")]
    assert pa.behaviour_line(game, rows) is None
