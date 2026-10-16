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

import chess
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from services.both_sides_review import (
    BLUNDER_CP,
    PUNISHED_CP,
    RESCUED_SHARE,
    SCHEMA_VERSION,
    card_from_review,
    last_game_card,
    mate_reply_cost,
)


def _review(his, theirs, *, whose="theirs", reply_cost=None, his_turns=30, his_turns_lost=0):
    return {
        "schema_version": SCHEMA_VERSION,
        "depth": 12,
        "his_moves": 30,
        "their_moves": 30,
        "his_mean_cp": his,
        "their_mean_cp": theirs,
        "his_blunders": 1,
        "their_blunders": 2,
        "reply_cost": reply_cost,
        "his_turns": his_turns,
        "his_turns_lost": his_turns_lost,
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


def test_going_straight_at_it_is_only_said_when_he_actually_did():
    """It used to be said whenever the biggest error was theirs. Measured over
    30 games that fired 16 times and was true 12 -- so one time in four he was
    congratulated for a punishment he never played."""
    took = card_from_review(
        _review(37, 74, reply_cost=0), won=True, lost=False, termination="x")
    missed = card_from_review(
        _review(37, 74, reply_cost=1030), won=True, lost=False, termination="x")
    assert "straight at it" in took["detail"]
    assert "straight at it" not in missed["detail"]
    assert took["punished"] is True and missed["punished"] is False
    # The chance was still theirs to give, and saying so costs him nothing.
    assert "went wrong" in missed["detail"]


def test_mating_them_counts_as_going_straight_at_it():
    """The eval loop stops at game over, so a mate delivered one move after
    their mistake had no cost recorded -- and the card stayed silent about the
    best answer a player can possibly give. Measured on his own record this
    was the difference on a real game: 41...Kh7, and he mated.

    Back-rank mate: Black to move and mated, so the mate was White's.
    """
    mated = chess.Board("3Q2k1/5ppp/8/8/8/8/5PPP/6K1 b - - 0 30")
    assert mated.is_checkmate()

    # his mistake is the second-to-last ply, he mates on the last
    assert mate_reply_cost(mated, chess.WHITE, 60, 58) == 0

    # ...but only then. Each of these is a reason NOT to credit him:
    assert mate_reply_cost(mated, chess.BLACK, 60, 58) is None   # HE was mated
    assert mate_reply_cost(mated, chess.WHITE, 60, 50) is None   # mate came later
    quiet = chess.Board("4r1k1/pp3ppp/2n5/3p4/3q4/3B4/2PQ1PPP/3K3R b - - 6 30")
    assert not quiet.is_checkmate()
    assert mate_reply_cost(quiet, chess.WHITE, 60, 58) is None   # no mate at all


def test_a_missing_reply_cost_never_becomes_praise():
    """An older cached review has no `reply_cost`. Silence must read as "not
    established", never as "he did it"."""
    card = card_from_review(
        _review(37, 74, reply_cost=None), won=True, lost=False, termination="x")
    assert card["punished"] is False
    assert "straight at it" not in card["detail"]


def test_the_punish_window_is_named_not_scattered():
    assert PUNISHED_CP == 30


def test_a_game_he_was_lost_in_is_not_told_as_his_steadiness():
    """He was the steadier player in a game he was losing for half of. Telling
    him he was the steadier player describes a game he did not play."""
    rescued = card_from_review(
        _review(37, 74, reply_cost=0, his_turns=30, his_turns_lost=17),
        won=True, lost=False, termination="x")
    assert rescued["state"] == "rescued"
    assert "steadier" not in rescued["headline"].lower()
    # Told as what they did, not as what he failed to do.
    for word in ("losing", "lost", "blunder", "mistake"):
        assert word not in rescued["headline"].lower()


def test_an_ordinary_win_is_not_called_a_rescue():
    ordinary = card_from_review(
        _review(37, 74, reply_cost=0, his_turns=30, his_turns_lost=2),
        won=True, lost=False, termination="x")
    assert ordinary["state"] == "sharper"


def test_the_rescue_share_sits_on_the_gap_in_his_record():
    # 0,...,27% then 55,55% over 30 games: anything in this range splits them.
    assert 0.30 <= RESCUED_SHARE <= 0.50


def test_the_claim_matches_what_was_measured():
    """Mean cp loss is how much he gave away, not how well he found things.
    "Sharper" claims the second; the card is only entitled to the first."""
    for args in (
        dict(won=True, lost=False, termination="x"),
        dict(won=False, lost=True, termination="timeout"),
    ):
        card = card_from_review(_review(37, 74), **args)
        assert "sharper" not in card["headline"].lower()
        assert "steadier" in card["headline"].lower()


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
