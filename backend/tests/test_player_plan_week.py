"""The plan's week: the Sunday verdict on last week's step and the next step.
services/player_plan_week.py. Pure functions, no database."""
import re
from datetime import datetime, timedelta, timezone

from services import player_plan_week as ppw

MODERN = "rnbqk1nr/ppp1ppbp/3p2p1/8/2BPP3/5N2/PPP2PPP/RNBQK2R b KQkq - 1 4"
KEY = "opening:black:g6 Bg7:Bg4"


def _rows(with_habit):
    rows = [{"move": "g6", "fen_before": "x b - - 0 1"}, {"move": "Bg7", "fen_before": "x b - - 0 2"}]
    rows.append({"move": "Bg4" if with_habit else "Nf6", "fen_before": MODERN})
    return rows


def test_opening_verdict_is_exact():
    games = [{"game_id": f"g{i}", "user_color": "black"} for i in range(3)]
    clean = {g["game_id"]: _rows(False) for g in games}
    assert ppw.opening_verdict(KEY, games, clean)["status"] == "kept"
    slipped = {**clean, "g1": _rows(True)}
    assert ppw.opening_verdict(KEY, games, slipped)["status"] == "not_yet"
    # Reaching the line once is not enough to call it kept.
    assert ppw.opening_verdict(KEY, games[:1], clean)["status"] == "no_chance"
    # White games and other lines do not count as chances.
    white = [{"game_id": "w", "user_color": "white"}]
    assert ppw.opening_verdict(KEY, white, {"w": _rows(False)})["measured"]["reached"] == 0


def test_habit_verdict_needs_evidence_since_the_step_started():
    qid = "gap:missed_tactic:missed_fork"
    games = [{"game_id": f"g{i}"} for i in range(20)]
    base = {"rate": 0.5, "hit_games": 8}
    assert ppw.habit_verdict(f"habit:{qid}", None, base, games, [])["status"] == "kept"
    few = ppw.habit_verdict(f"habit:{qid}", None, base, games[:3], [])
    assert few["status"] == "no_chance"   # too few games to tell
    hits = [{"game_id": f"g{i}", "missed_pattern": "missed_tactic", "subtype": "missed_fork"} for i in range(10)]
    assert ppw.habit_verdict(f"habit:{qid}", None, base, games, hits)["status"] == "not_yet"


def test_decide_moves_on_only_after_kept():
    steps = [{"key": "a"}, {"key": "b"}, {"key": "c"}]
    prev = {"step_key": "a", "step": {"key": "a"}}
    assert ppw.decide(prev, {"status": "not_yet"}, steps, [])["key"] == "a"
    assert ppw.decide(prev, {"status": "no_chance"}, steps, [])["key"] == "a"
    assert ppw.decide(prev, {"status": "kept"}, steps, ["a"])["key"] == "b"
    # A kept step is skipped later too.
    assert ppw.decide(prev, {"status": "kept"}, steps, ["a", "b"])["key"] == "c"
    # A repeated step that fell out of the top three still comes back from its snapshot.
    assert ppw.decide({"step_key": "z", "step": {"key": "z", "title": "old"}}, {"status": "not_yet"}, steps, [])["title"] == "old"
    assert ppw.decide(None, None, steps, [])["key"] == "a"


def test_apply_week_fixes_the_step_first_and_says_last_week_in_words():
    plan = {"steps": [{"key": "a", "this_week": True}, {"key": "b"}, {"key": "c"}]}
    row = {"step_key": "b", "step": {"key": "b"}, "verdict": {"status": "kept"}}
    out = ppw.apply_week(plan, row)
    assert [s["key"] for s in out["steps"]] == ["b", "a", "c"]
    assert out["steps"][0]["this_week"] and not out["steps"][1].get("this_week")
    assert out["last_week"]["status"] == "kept" and not re.search(r"\d", out["last_week"]["words"])


def test_build_row_carries_the_start_and_baseline_while_repeating():
    now = datetime(2026, 11, 16, 9, tzinfo=timezone.utc)
    started = datetime(2026, 11, 9, tzinfo=timezone.utc)
    prev = {"week_start": "2026-11-09", "step_key": KEY, "step": {"key": KEY}, "step_started": started, "baseline": None}
    games = [{"game_id": "g1", "user_color": "black", "is_analyzed": True,
              "played_at_utc": started + timedelta(days=2)}]
    plan = {"steps": [{"key": KEY, "title": "Your opening as Black"}, {"key": "habit:x"}]}
    row = ppw.build_row("u", "2026-11-16", plan, prev, [], games, {"g1": _rows(True)}, [], None, now)
    assert row["verdict"]["status"] == "not_yet" and row["step_key"] == KEY and row["step_started"] == started
    nothing = ppw.build_row("u", "2026-11-16", {"steps": []}, prev, [], games, {}, [], None, now)
    assert nothing is None
