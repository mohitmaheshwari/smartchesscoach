"""The card that says who was the better player.

Everything the product knew about a game came from his moves alone. This is
the first thing that reads the opponent's, so the tests are mostly about not
saying more than two averages can support:

  * no engine figure reaches the player -- the numbers justify the sentence,
    they are not the sentence
  * the clock state is the rare one and must not fire on an ordinary loss
  * a cache that cannot be written must not cost him the card
"""
import asyncio
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from services.both_sides_review import (
    BLUNDER_CP,
    SCHEMA_VERSION,
    card_from_review,
    last_game_card,
)


def _review(his, theirs, *, whose="theirs"):
    return {
        "schema_version": SCHEMA_VERSION,
        "depth": 12,
        "his_moves": 30,
        "their_moves": 30,
        "his_mean_cp": his,
        "their_mean_cp": theirs,
        "his_blunders": 1,
        "their_blunders": 2,
        "turning_point": {
            "move_number": 18,
            "san": "Qf3+",
            "whose": whose,
            "fen_before": "r4rk1/6pp/bpp2q2/p2pN3/1b1P4/1Q1BP1P1/PP2KP1P/R4R2 b - - 2 18",
            "cost": 542,
            "board_orientation": "white",
        },
    }


def test_sharper_and_won():
    card = card_from_review(_review(37, 74), won=True, lost=False, termination="resignation")
    assert card["state"] == "sharper"
    assert card["decided_by"] == "board"


def test_the_clock_state_needs_both_sharper_and_a_flag_fall():
    card = card_from_review(_review(44, 79), won=False, lost=True, termination="timeout")
    assert card["state"] == "clock"
    assert card["decided_by"] == "clock"
    assert "clock" in card["headline"].lower()


def test_a_timeout_he_was_losing_anyway_is_not_the_clock_card():
    """Most of his timeout losses are games he was also playing worse in.
    Calling those "the clock ended it" would make the rare card meaningless."""
    card = card_from_review(_review(90, 55), won=False, lost=True, termination="timeout")
    assert card["state"] == "outplayed"
    assert card["decided_by"] == "clock"  # true of the game
    assert "clock" not in card["headline"].lower()  # but not the story


def test_a_timeout_he_won_is_still_decided_by_the_clock():
    """His last real game ended on his opponent's flag. Recording that as
    "board" made the field a statement about him rather than about the game."""
    card = card_from_review(_review(37, 74), won=True, lost=False, termination="timeout")
    assert card["decided_by"] == "clock"
    assert card["state"] == "sharper"  # but the clock is not the story
    assert "clock" not in card["headline"].lower()


def test_being_sharper_and_not_winning_is_its_own_state():
    card = card_from_review(_review(50, 80), won=False, lost=True, termination="resignation")
    assert card["state"] == "sharper_no_win"


def test_outplayed_reads_as_what_they_did_not_as_a_tally():
    card = card_from_review(_review(85, 45), won=False, lost=True, termination="resignation")
    assert card["state"] == "outplayed"
    for word in ("blunder", "mistake", "error", "wrong move"):
        assert word not in card["headline"].lower()


def test_no_number_ever_reaches_the_player():
    for args in (
        dict(won=True, lost=False, termination="resignation"),
        dict(won=False, lost=True, termination="timeout"),
        dict(won=False, lost=True, termination="resignation"),
    ):
        card = card_from_review(_review(44, 79), **args)
        for field in ("headline", "detail"):
            assert not any(ch.isdigit() for ch in card[field]), (args, card[field])


def test_the_turning_point_being_theirs_changes_the_sentence():
    his = card_from_review(_review(37, 74, whose="his"), won=True, lost=False, termination="x")
    theirs = card_from_review(_review(37, 74, whose="theirs"), won=True, lost=False, termination="x")
    assert his["detail"] != theirs["detail"]
    assert theirs["turning_point_is_theirs"] is True
    assert his["turning_point_is_theirs"] is False


# ---- the async path, with fakes ----

class _Games:
    def __init__(self, game):
        self._game = game

    async def find_one(self, _q, _p=None, sort=None):
        return self._game


class _Cache:
    def __init__(self, stored=None, writable=True):
        self.stored = stored
        self.writable = writable
        self.writes = 0

    async def find_one(self, _q, _p=None):
        return {"review": self.stored} if self.stored else None

    async def update_one(self, _q, _u, upsert=False):
        if not self.writable:
            raise RuntimeError("read-only replica")
        self.writes += 1


class _Db:
    def __init__(self, game, cache):
        self.games = _Games(game)
        self.game_both_sides = cache


GAME = {
    "game_id": "g1", "pgn": "1. e4 e5 *", "user_color": "white",
    "result": "1-0", "termination": "resignation", "platform": "lichess",
    "played_at_utc": "2026-10-16", "url": "https://lichess.org/abc",
}


def _run(db):
    return asyncio.get_event_loop().run_until_complete(last_game_card(db, "u1"))


def test_a_cached_review_is_not_recomputed():
    cache = _Cache(stored=_review(37, 74))
    card = _run(_Db(GAME, cache))
    assert card["state"] == "sharper"
    assert cache.writes == 0
    assert card["measured"]["his_mean_cp"] == 37


def test_an_unwritable_cache_still_returns_the_card(monkeypatch):
    import services.both_sides_review as mod

    monkeypatch.setattr(mod, "review_both_sides", lambda *_a, **_k: _review(37, 74))
    card = _run(_Db(GAME, _Cache(stored=None, writable=False)))
    assert card is not None and card["state"] == "sharper"


def test_no_game_means_no_card_rather_than_an_empty_one():
    assert _run(_Db(None, _Cache())) is None


def test_the_measured_block_is_present_for_review_but_separate_from_the_copy():
    card = _run(_Db(GAME, _Cache(stored=_review(44, 79))))
    assert set(card["measured"]) >= {"his_mean_cp", "their_mean_cp", "depth"}
    assert "his_mean_cp" not in card["headline"]


def test_the_blunder_threshold_is_named_not_scattered():
    assert BLUNDER_CP == 200
