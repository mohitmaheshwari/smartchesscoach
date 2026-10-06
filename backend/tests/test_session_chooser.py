"""The chooser must actually choose. docs/home_session_scope.md

The failure to watch for is not a wrong answer, it is the same answer for
everybody every day — a chooser that always says IMPROVE has not chosen
anything. These tests pin the order and the refusals that make the decision
real.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from services.session_chooser import (  # noqa: E402
    APPRECIATE, BRILLIANT_RECENT_GAMES, CHALLENGE, IMPROVE,
    MAX_CLEAN_GAMES_TO_CELEBRATE, MIN_CLEAN_GAMES, appreciation_key,
    build_blocks, choose, total_minutes,
)

FOCUS = {"topic_key": "time_management", "coaching_label": "Time management"}
CLEAN = {"piece_safety": {"state": "fading", "clean_streak": 4}}
GOOD = {"fen": "8/8/8/8/8/8/8/K6k w - - 0 1", "move_san": "Rxg2+", "games_ago": 2}


def test_a_quiet_pattern_leads_over_the_focus():
    """Someone who just did something right is told so first."""
    out = choose(patterns=CLEAN, focus=FOCUS, focus_has_practice=True)
    assert out["mode"] == APPRECIATE
    assert out["why"] == "clean_pattern"


def test_a_long_clean_run_is_old_news():
    """Appreciation is an EVENT. A pattern quiet for ages must not lead every
    day — measured, celebrating any currently-quiet pattern gave APPRECIATE to
    49 of 70 players and IMPROVE to 4."""
    old = {"piece_safety": {"state": "fading", "clean_streak": 12}}
    assert choose(patterns=old, focus=FOCUS, focus_has_practice=True)["mode"] == IMPROVE


def test_an_appreciation_is_shown_once_then_retires():
    first = choose(patterns=CLEAN, focus=FOCUS, focus_has_practice=True)
    assert first["mode"] == APPRECIATE
    key = appreciation_key(first["evidence"])
    second = choose(patterns=CLEAN, focus=FOCUS, focus_has_practice=True,
                    already_shown=[key])
    assert second["mode"] == IMPROVE


def test_the_key_names_the_thing_not_the_moment():
    """Two different quiet patterns are two different things to celebrate."""
    a = appreciation_key({"kind": "clean_pattern", "pattern": "piece_safety"})
    b = appreciation_key({"kind": "clean_pattern", "pattern": "king_safety"})
    assert a != b
    assert appreciation_key({"kind": "good_move", "fen": "x"}) != a


def test_a_short_clean_run_is_not_a_claim():
    short = {"piece_safety": {"state": "fading", "clean_streak": MIN_CLEAN_GAMES - 1}}
    out = choose(patterns=short, focus=FOCUS, focus_has_practice=True)
    assert out["mode"] == IMPROVE


def test_an_active_pattern_never_appreciates():
    active = {"piece_safety": {"state": "active", "clean_streak": 9}}
    assert choose(patterns=active, focus=FOCUS, focus_has_practice=True)["mode"] == IMPROVE


def test_a_good_move_can_lead_when_no_pattern_has_gone_quiet():
    out = choose(good_move=GOOD, focus=FOCUS, focus_has_practice=True)
    assert out["mode"] == APPRECIATE
    assert out["why"] == "good_move"


def test_an_old_good_move_is_history_not_news():
    stale = dict(GOOD, games_ago=BRILLIANT_RECENT_GAMES + 1)
    assert choose(good_move=stale, focus=FOCUS, focus_has_practice=True)["mode"] == IMPROVE


def test_a_focus_with_no_practice_falls_through_to_challenge():
    """king_safety has zero verified positions; a mode that cannot be acted on
    is not a mode."""
    out = choose(focus=FOCUS, focus_has_practice=False)
    assert out["mode"] == CHALLENGE
    assert out["why"] == "focus_without_practice"


def test_no_focus_at_all_still_gives_the_player_something():
    out = choose()
    assert out["mode"] == CHALLENGE
    assert out["why"] == "no_focus"


def test_the_decision_is_always_explainable():
    for kwargs in ({"patterns": CLEAN}, {"good_move": GOOD},
                   {"focus": FOCUS, "focus_has_practice": True}, {}):
        out = choose(**kwargs)
        assert out["why"], "a decision with no reason is a random number"
        assert out["evidence"]["headline"]


def test_an_appreciate_day_still_contains_work():
    """A day that only celebrates teaches nothing."""
    out = choose(patterns=CLEAN, focus=FOCUS, focus_has_practice=True)
    blocks = build_blocks(out["mode"], out["evidence"], FOCUS, True)
    kinds = [b["kind"] for b in blocks]
    assert kinds[0] == APPRECIATE
    assert IMPROVE in kinds and CHALLENGE in kinds


def test_blocks_never_offer_practice_that_does_not_exist():
    blocks = build_blocks(CHALLENGE, {"line": ""}, FOCUS, focus_has_practice=False)
    assert all(b["kind"] != IMPROVE for b in blocks)


def test_minutes_are_the_only_number_shown():
    out = choose(patterns=CLEAN, focus=FOCUS, focus_has_practice=True)
    blocks = build_blocks(out["mode"], out["evidence"], FOCUS, True)
    assert total_minutes(blocks) > 0
    for block in blocks:
        for field in ("title", "detail"):
            assert not re.search(r"[0-9%]", str(block.get(field) or "")), block
    for field in ("headline", "line"):
        assert not re.search(r"[0-9%]", str(out["evidence"].get(field) or ""))


def test_discover_is_not_a_mode():
    """Held back deliberately: 192k deflection puzzles, zero authored lessons."""
    modes = set()
    for kwargs in ({"patterns": CLEAN}, {"good_move": GOOD},
                   {"focus": FOCUS, "focus_has_practice": True}, {}):
        modes.add(choose(**kwargs)["mode"])
    assert modes <= {APPRECIATE, IMPROVE, CHALLENGE}
    assert "discover" not in modes
