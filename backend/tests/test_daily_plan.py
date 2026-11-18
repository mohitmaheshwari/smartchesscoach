"""Today's tasks (services/daily_plan.py, docs/daily_coach_plan_scope.md)."""
from datetime import date, datetime, timezone

from services import daily_plan as dp

TODAY = date(2026, 11, 18)
NOW = datetime(2026, 11, 18, 10, tzinfo=timezone.utc)


def _file(**extra):
    base = {
        "rating": 1250,
        "plan": {"steps": [{
            "key": "habit:piece_safety:x", "title": "Leaving a piece where it can be taken",
            "work": {"find": [{"ref": "g1:12", "url": "/game/g1?move=12"}, {"ref": "g2:20", "url": "/game/g2?move=20"}],
                     "play": [{"ref": "g1:12", "fen": "8/8/8/8/8/8/8/K6k w - - 0 1", "user_color": "white",
                               "source_game_id": "g1"}]},
        }]},
        "traps": {"could_set": [{"key": "italian-game#0", "name": "Fried Liver", "school_url": "/learn/traps/italian-game-0",
                                 "practice_url": "/play-with-coach?trap=fried"}]},
        "clock_advice": {"clocks": ["3+2"], "instead": "5+3"},
        "last_game": {"game_id": "g9", "clean": False, "review_url": "/game/g9?move=30"},
    }
    base.update(extra)
    return base


def _day(day, tasks, size="normal"):
    return {"day": day, "size": size, "tasks": tasks}


def test_a_day_runs_fix_new_look_back_play_and_fix_is_the_next_undone_plan_work():
    week = {"done": {"habit:piece_safety:x": {"find": ["g1:12"], "play": []}}}
    tasks = dp.build_tasks(_file(), week, [], TODAY)
    assert [t["slot"] for t in tasks] == ["fix", "new", "play"]
    assert tasks[0]["ref"] == "g2:20" and tasks[0]["url"] == "/game/g2?move=20"
    assert tasks[1]["kind"] == "theme" and tasks[1]["id"] == "theme:back_rank_mate"
    assert tasks[2]["title"] == "Two games at 5+3."


def test_kinds_take_turns_and_nothing_done_comes_back():
    yesterday = _day("2026-11-17", [{"slot": "new", "kind": "theme", "id": "theme:back_rank_mate",
                                     "done_at": NOW, "topic": "theme-back_rank_mate", "title": "Back-rank mate"}])
    tasks = dp.build_tasks(_file(), {}, [yesterday], TODAY)
    new = next(t for t in tasks if t["slot"] == "new")
    assert new["kind"] == "trap" and new["id"] == "trap:italian-game#0"
    # The day after, a theme again, and not the one already done.
    trap_day = _day("2026-11-18", [{"slot": "new", "kind": "trap", "id": "trap:italian-game#0", "done_at": NOW,
                                    "title": "A trap: Fried Liver", "url": "/learn/traps/italian-game-0"}])
    tasks = dp.build_tasks(_file(), {}, [yesterday, trap_day], date(2026, 11, 19))
    new = next(t for t in tasks if t["slot"] == "new")
    assert new["kind"] == "theme" and new["id"] == "theme:smothered_mate"


def test_an_idea_not_done_is_offered_again():
    served = _day("2026-11-16", [{"slot": "new", "kind": "theme", "id": "theme:back_rank_mate"}])
    other = _day("2026-11-17", [{"slot": "new", "kind": "trap", "id": "trap:x"}])
    new = next(t for t in dp.build_tasks(_file(), {}, [served, other], TODAY) if t["slot"] == "new")
    assert new["id"] == "theme:back_rank_mate"


def test_look_back_three_days_after_learning_then_ten():
    learned = _day("2026-11-15", [{"slot": "new", "kind": "theme", "id": "theme:fork", "done_at": NOW,
                                   "topic": "theme-fork", "title": "Fork"}])
    look = dp.pick_look_back([learned], TODAY)
    assert look["of"] == "theme:fork" and look["count"] == 1 and look["title"] == "Look back: fork."
    assert "Sunday" in look["text"]
    first_look = _day("2026-11-18", [{"slot": "look_back", "of": "theme:fork", "done_at": NOW}])
    assert dp.pick_look_back([learned, first_look], date(2026, 11, 20)) is None
    assert dp.pick_look_back([learned, first_look], date(2026, 11, 25))["of"] == "theme:fork"


def test_no_plan_falls_back_to_the_last_game_and_no_clock_to_a_coach_game():
    tasks = dp.build_tasks(_file(plan=None, clock_advice=None, traps=None), {}, [], TODAY)
    assert tasks[0]["id"] == "fix:last:g9"
    assert tasks[-1]["id"] == "play:coach"


def test_proofs_tick_puzzles_games_and_plan_work():
    tasks = dp.build_tasks(_file(), {}, [], TODAY)
    new = next(t for t in tasks if t["slot"] == "new")
    changed = dp.apply_proofs(tasks, {new["topic"]: dp.THEME_PUZZLES - 1}, {"5+3": 1}, {}, NOW)
    assert not changed
    week = {"done": {"habit:piece_safety:x": {"find": ["g1:12"]}}}
    assert dp.apply_proofs(tasks, {new["topic"]: dp.THEME_PUZZLES}, {"5+3": 2}, week, NOW)
    assert all(t.get("done_at") for t in tasks)


def test_size_shows_a_prefix_and_the_week_never_counts_misses():
    doc = _day("2026-11-18", [{"id": "a", "done_at": NOW}, {"id": "b", "done_at": NOW}, {"id": "c"}], size="short")
    assert dp.day_state(doc) == "done"
    doc["size"] = "normal"
    assert dp.day_state(doc) == "part"
    out = dp.payload(doc, [(d, "none") for d in dp.week_days(TODAY)], TODAY)
    assert [t["id"] for t in out["tasks"]] == ["a", "b", "c"] and not out["all_done"]
    assert [w["label"] for w in out["week"]][0] == "Mon" and sum(w["today"] for w in out["week"]) == 1


def test_themes_follow_the_ladder_and_skip_ones_far_below_the_player():
    low = [c["id"] for c in dp.theme_candidates(900, set())]
    high = [c["id"] for c in dp.theme_candidates(1900, set())]
    assert low[0] == "theme:back_rank_mate"
    assert "theme:mate_in_one" not in high and "theme:quiet_move" in high


def test_a_player_under_six_hundred_still_gets_the_easiest_ideas():
    from services.topic_practice_themes import rating_window

    assert rating_window(298) == (600, 850)
    assert dp.theme_candidates(298, set())[0]["id"] == "theme:back_rank_mate"


def test_clock_of_reads_the_pgn_tag():
    assert dp.clock_of('[TimeControl "300+3"]') == "5+3"
    assert dp.clock_of("no tag") is None
