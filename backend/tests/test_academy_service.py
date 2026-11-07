"""The academy pilot's report: every claim is a board fact, and no digit reaches a family.

docs/academy_pilot_scope.md. The positions are real moves from Mohit's games of
the week of 2026-11-02, the same ones the sample page shows, each re-checked on
the board when it was picked.
"""
from __future__ import annotations

import os
import re
import sys
from datetime import date, datetime, timezone

import chess
import pytest

_BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

from services import academy_service as svc  # noqa: E402

# Knight jumps to f4; the rook on d4 takes it and nothing guards f4.
KNIGHT_HANG = "2n3k1/5r1p/4ppN1/3p4/3r2P1/pP6/P4PP1/1K5R w - - 0 31"
# Queen to g4; the bishop on c8 takes it.
QUEEN_HANG = "r1bq1rk1/pp3p1p/2nb4/3p2p1/5N2/1B4Q1/PPP2PPP/R1B2RK1 w - - 0 15"
# Qc7 looks like a hang but the rook on c1 recaptures: an even queen trade. The
# stored caption called it a lost queen; the board check must stay silent.
QUEEN_TRADE = "1rb1k2r/3qn2p/4ppp1/2Qp4/3P4/pP3NP1/P4PP1/1KR4R w k - 7 23"
# A knight on f3 attacked by a pawn on e4; Nd4 saves it.
SAVE = "6k1/8/8/8/4p3/5N2/8/6K1 w - - 0 1"


def _obs(fen, uci, quality="mistake", game="g1", ply=1, color="white", before=None, after=None):
    return {"fen_before": fen, "move_uci": uci, "execution_quality": quality, "game_id": game,
            "ply": ply, "color": color, "eval_before": before, "eval_after": after}


# ---------------------------------------------------------------------------
# the board checks
# ---------------------------------------------------------------------------
def test_a_knight_moved_where_a_rook_takes_it_for_free():
    e = svc.read_move(_obs(KNIGHT_HANG, "g6f4"))
    assert e["kind"] == "left_takeable"
    assert (e["piece"], e["attacker"], e["square"], e["free"]) == ("knight", "rook", "f4", True)
    assert e["attacker_uci"] == "d4f4"


def test_a_queen_moved_where_a_bishop_takes_it():
    e = svc.read_move(_obs(QUEEN_HANG, "g3g4"))
    assert (e["kind"], e["piece"], e["attacker"]) == ("left_takeable", "queen", "bishop")


def test_an_even_trade_is_not_called_a_lost_piece():
    """Negative control: the stored card said the queen was lost on c7."""
    assert svc.read_move(_obs(QUEEN_TRADE, "c5c7")) is None


def test_a_good_move_is_never_a_habit():
    assert svc.read_move(_obs(KNIGHT_HANG, "g6f4", quality="good")) is None


def test_a_saved_piece_is_a_good_moment():
    e = svc.read_move(_obs(SAVE, "f3d4", quality="best"))
    assert (e["kind"], e["piece"], e["attacker"]) == ("saved_piece", "knight", "pawn")


def test_a_good_move_that_leaves_the_piece_is_no_good_moment():
    assert svc.read_move(_obs(SAVE, "g1g2", quality="good")) is None


def test_a_piece_left_under_attack_is_its_own_habit():
    e = svc.read_move(_obs(SAVE, "g1g2", quality="mistake"))
    assert (e["kind"], e["piece"], e["attacker"]) == ("left_attacked", "knight", "pawn")


def test_an_illegal_stored_move_reads_as_nothing():
    assert svc.read_move(_obs(SAVE, "a1a8")) is None
    assert svc.read_move(_obs("not a fen", "e2e4")) is None


def test_the_better_move_is_shown_only_when_it_is_safe():
    assert svc.safe_better_move(KNIGHT_HANG, "g6h4") == "g6h4"
    assert svc.safe_better_move(KNIGHT_HANG, "g6f4") is None
    assert svc.safe_better_move(KNIGHT_HANG, None) is None


# ---------------------------------------------------------------------------
# a week
# ---------------------------------------------------------------------------
def _game(gid, outcome="loss", day="2026-11-03", color="white"):
    return {"game_id": gid, "outcome": outcome, "played_day": day,
            "played_at": f"{day}T10:00:00", "user_color": color, "opponent_rating": 1350}


def test_one_slip_is_not_a_habit():
    week = svc.summarise_week([_game("g1")], [_obs(KNIGHT_HANG, "g6f4", game="g1")])
    assert week["habit"] is None


def test_a_habit_in_two_games_is_named_with_one_board_per_game():
    games = [_game("g1"), _game("g2", day="2026-11-04")]
    obs = [_obs(KNIGHT_HANG, "g6f4", game="g1", ply=61), _obs(QUEEN_HANG, "g3g4", game="g2", ply=29),
           _obs(KNIGHT_HANG, "g6f4", game="g1", ply=63)]
    week = svc.summarise_week(games, obs)
    assert week["habit"]["id"] == "piece_left_takeable"
    assert week["habit"]["games"] == 2 and week["habit"]["events"] == 3
    assert [e["game_id"] for e in week["habit"]["evidence"]] == ["g2", "g1"]


def test_the_slip_is_from_winning_in_a_game_not_won():
    games = [_game("g1", outcome="loss"), _game("g2", outcome="win")]
    obs = [_obs(KNIGHT_HANG, "g6f4", game="g1", before=520, after=-40),
           _obs(QUEEN_HANG, "g3g4", game="g2", before=900, after=-500)]
    slip = svc.summarise_week(games, obs)["homework"]
    assert slip["game_id"] == "g1" and slip["played_san"] == "Nf4"


def test_evaluations_are_turned_round_for_black():
    # White-relative -400 is +400 for black: winning, then a slip to -300.
    fen = "6k1/8/8/8/4P3/2n5/8/6K1 b - - 0 1"
    games = [_game("g1", outcome="draw", color="black")]
    obs = [_obs(fen, "c3d5", game="g1", color="black", before=-400, after=300)]
    assert svc.summarise_week(games, obs)["homework"]["color"] == "black"
    obs_wrong_way = [_obs(fen, "c3d5", game="g1", color="black", before=400, after=-300)]
    assert svc.summarise_week(games, obs_wrong_way)["homework"] is None


@pytest.mark.parametrize("now_events,prev_events,expected", [
    (1, 4, "less"), (4, 4, "same"), (6, 5, "same"), (5, 2, "more"), (3, 0, "new"),
])
def test_trend_compares_rates(now_events, prev_events, expected):
    habit = {"id": "piece_left_takeable", "rate": now_events / 10}
    prev = {"games": {"analysed": 10}, "habit_counts": {"piece_left_takeable": {"events": prev_events}}}
    assert svc.trend(habit, 10, prev) == expected


def test_trend_says_not_enough_with_few_games():
    habit = {"id": "piece_left_takeable", "rate": 0.5}
    prev = {"games": {"analysed": 4}, "habit_counts": {}}
    assert svc.trend(habit, 10, prev) == "not_enough"
    assert svc.trend(habit, 4, {"games": {"analysed": 10}}) == "not_enough"


# ---------------------------------------------------------------------------
# words
# ---------------------------------------------------------------------------
def _full_week():
    games = [_game("g1"), _game("g2", day="2026-11-04"), _game("g3", outcome="win", day="2026-11-05")]
    obs = [_obs(KNIGHT_HANG, "g6f4", game="g1", before=500, after=-60),
           _obs(QUEEN_HANG, "g3g4", game="g2"),
           _obs(SAVE, "f3d4", quality="best", game="g3")]
    return svc.summarise_week(games, obs)


def _strings(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for k, v in obj.items():
            if k not in ("fen", "arrows", "ring", "orientation", "kind"):
                yield from _strings(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _strings(v)


def test_the_report_has_every_section_of_the_sample():
    out = svc.render_report(_full_week(), child_name="Rohan", coach_name="Coach Priya",
                            coach_note="Rohan is quick and brave.")
    kinds = [s["kind"] for s in out["sections"]]
    assert kinds == ["week", "habit", "good", "homework", "question", "note"]
    habit = out["sections"][1]
    assert habit["headline"] == "Rohan moves a piece to a square where it can be taken."
    assert habit["boards"][0]["caption"] == "The queen moved here. Their bishop could take it for free."


@pytest.mark.parametrize("week", [_full_week(), svc.summarise_week([], [])])
def test_no_digit_ever_reaches_a_family(week):
    out = svc.render_report(week, child_name="Rohan", coach_name="Coach Priya")
    for text in _strings(out):
        assert not re.search(r"\d", text), text
        assert "%" not in text


def test_family_sentences_stay_short_and_plain():
    out = svc.render_report(_full_week(), child_name="Rohan", coach_name="Coach Priya")
    jargon = ("material", "tempo", "initiative", "blunder", "cognitive", "brain", "iq ")
    for text in _strings(out):
        for term in jargon:
            assert term not in text.lower(), (term, text)
        for sentence in [s for s in re.split(r"[.?!]", text) if s.strip()]:
            assert len(sentence.split()) <= 13, sentence


def test_an_empty_week_says_so_plainly():
    out = svc.render_report(svc.summarise_week([], []), child_name="Rohan")
    assert out["sections"][0]["lines"] == ["Rohan did not play this week."]
    assert out["sections"][1]["headline"] == "No habit stood out this week."


def test_the_coach_sees_why_a_child_needs_them():
    given = {"consent": {"status": "given"}, "lichess_username": "x"}
    assert svc.needs_coach({"consent": {"status": "pending"}}, None, "none") == "Waiting for the parent to agree"
    assert svc.needs_coach(given, {"games": {"count": 0}}, "none") == "No games to read"
    assert svc.needs_coach(given, {"games": {"count": 4, "analysed": 4}, "trend": "more"}, "none") == "Getting worse"
    assert svc.needs_coach(given, {"games": {"count": 4, "analysed": 4}, "homework": {"fen": "x"}}, "not_started") == "Homework not started"
    assert svc.needs_coach(given, {"games": {"count": 4, "analysed": 4}}, "none") is None


def test_a_class_topic_needs_two_children():
    one = {"habit": {"id": "piece_left_takeable"}}
    assert svc.class_topic([one, None]) is None
    topic = svc.class_topic([one, one, {"habit": {"id": "piece_left_attacked"}}])
    assert topic["headline"] == "Check the new square before you move."
    assert topic["line"].startswith("Two children")


# ---------------------------------------------------------------------------
# plumbing
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("raw,expected", [
    ("98765 43210", "919876543210"), ("+91 98765-43210", "919876543210"),
    ("09876543210", "919876543210"), ("0044 7700 900123", "447700900123"),
    ("12345", None), ("", None),
])
def test_phone_numbers(raw, expected):
    assert svc.normalise_phone(raw) == expected


def test_whatsapp_link_fills_the_number_and_text():
    link = svc.whatsapp_link("919876543210", "Hello & welcome")
    assert link == "https://wa.me/919876543210?text=Hello%20%26%20welcome"


def test_the_week_starts_on_monday_in_india():
    # Sunday 20:00 UTC is Monday 01:30 in India.
    assert svc.week_start(datetime(2026, 11, 8, 20, 0, tzinfo=timezone.utc)) == date(2026, 11, 9)
    begin, end = svc.week_bounds_utc(date(2026, 11, 9))
    assert begin == datetime(2026, 11, 8, 18, 30) and end == datetime(2026, 11, 15, 18, 30)


@pytest.mark.parametrize("fen,color,pawns,expected", [
    (KNIGHT_HANG, "white", 3.0, "kept"), (KNIGHT_HANG, "white", -3.0, "lost"),
    (KNIGHT_HANG, "white", 0.5, "held"), (KNIGHT_HANG, "black", 3.0, "lost"),
    ("7k/6Q1/6K1/8/8/8/8/8 b - - 0 1", "white", None, "kept"),
    ("7k/8/6K1/8/8/8/8/6Q1 b - - 0 1", "white", None, "held"),
    ("7k/5Q2/6K1/8/8/8/8/8 b - - 0 1", "white", None, "drawn"),
])
def test_homework_verdict(fen, color, pawns, expected):
    assert svc.homework_verdict(chess.Board(fen), color, pawns) == expected


def test_imported_but_unread_games_are_not_called_clean():
    week = svc.summarise_week([_game("g1"), _game("g2")], [])
    out = svc.render_report(week, child_name="Rohan")
    assert out["sections"][1]["headline"] == "The games are still being read."
    given = {"consent": {"status": "given"}, "lichess_username": "x"}
    assert svc.needs_coach(given, week, "none") is None


@pytest.mark.parametrize("games, line", [
    ({"count": 1, "days": 1, "wins": 0, "losses": 1}, "The game was a loss. That is normal while learning."),
    ({"count": 1, "days": 1, "wins": 1, "losses": 0}, "The game was a win."),
    ({"count": 1, "days": 1, "wins": 0, "losses": 0}, "The game was a draw."),
    ({"count": 2, "days": 1, "wins": 1, "losses": 1}, "Wins and losses were about even."),
])
def test_the_week_line_is_true_of_the_games_played(games, line):
    out = svc.render_report({"games": games}, child_name="Asha")
    assert out["sections"][0]["lines"][1] == line


def test_class_words_have_no_digits_and_name_what_was_learnt():
    week = {"games": {"count": 0}, "classes": {
        "learnt": ["how the rook moves", "how the bishop moves"], "practised": ["the queen"], "all_done": True}}
    out = svc.render_report(week, child_name="Asha")
    text = " ".join(" ".join([s.get("headline", "")] + s.get("lines", [])) for s in out["sections"])
    assert not re.search(r"\d", text)
    assert "Asha learnt how the rook moves and how the bishop moves." in text
    assert out["sections"][-1]["headline"] == "Can you show me what you learnt in class?"


def test_a_child_with_lessons_and_no_account_does_not_need_the_coach():
    student = {"consent": {"status": "given"}}
    assert svc.needs_coach(student, {"games": {"count": 0}}, "none") == "No lessons this week"
    assert svc.needs_coach(student, None, "none") == "No lessons this week"
    busy = {"games": {"count": 0}, "classes": {"learnt": ["how the rook moves"]}}
    assert svc.needs_coach(student, busy, "none") is None
    done = {"games": {"count": 0}, "classes": {"all_done": True}}
    assert svc.needs_coach(student, done, "none") == "Finished the lessons. Set up a class game"


def test_unread_games_with_a_lesson_can_still_be_reported():
    assert svc.report_blocked({"games": {"count": 2, "analysed": 0}})
    assert svc.report_blocked({"games": {"count": 2, "analysed": 1}}) is None
    assert svc.report_blocked({"games": {"count": 2, "analysed": 0},
                               "classes": {"learnt": ["how the rook moves"]}}) is None
    assert svc.report_blocked({"games": {"count": 0}}) is None


def test_a_lessons_only_report_does_not_say_games_in_its_footer():
    week = {"games": {"count": 0}, "classes": {"learnt": ["how the rook moves"]}}
    assert "class" in svc.render_report(week, child_name="Asha")["footer"]
    assert "games" in svc.render_report({"games": {"count": 2, "analysed": 2}}, child_name="Asha")["footer"]
