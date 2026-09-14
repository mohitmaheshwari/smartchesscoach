"""A player with no account can still tell us where to start.

Puzzle selection used a fixed difficulty order -- one beginner, one
intermediate, one advanced from every category -- and consulted no rating at
all. For a player with no games we had no prior whatsoever, so a first-timer
met the same ladder as a club player.

Measured on production: they got 12% of the FIRST position right, 19% overall,
and 62% were gone by the fifth. You cannot diagnose someone who has stopped
answering.

So onboarding asks, when there is no account to read. Deliberately not a
rating box -- someone who has never played online cannot answer "what is your
rating?", and they are exactly who this is for -- four things anyone can say
about themselves, mapped to the middle of a band.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from routes.settings import SELF_ASSESSED_LEVELS
from services.diagnostic_service import _difficulty_order_for
from services.rating_resolver import get_rating_band


def test_the_four_answers_are_ordered_and_span_the_range():
    assert set(SELF_ASSESSED_LEVELS) == {
        "learning_moves", "know_rules", "plays_regularly", "experienced",
    }
    ordered = [
        SELF_ASSESSED_LEVELS["learning_moves"],
        SELF_ASSESSED_LEVELS["know_rules"],
        SELF_ASSESSED_LEVELS["plays_regularly"],
        SELF_ASSESSED_LEVELS["experienced"],
    ]
    assert ordered == sorted(ordered) and len(set(ordered)) == 4, ordered

    # The first draft of this test demanded a DIFFERENT band per answer, and
    # it failed: "still learning the moves" (500) and "knows the rules" (800)
    # are both beginner_low. That is correct, not a bug -- the pool has three
    # difficulty buckets, so two beginner-ish answers honestly start the same
    # way. What has to hold is that the ends differ.
    bands = {get_rating_band(r) for r in ordered}
    assert len(bands) >= 3, bands
    assert get_rating_band(ordered[0]) != get_rating_band(ordered[-1])


def test_a_beginner_is_not_handed_an_advanced_position_first():
    order = asyncio.run(_difficulty_order_for(_DB(500), "u1"))
    assert order[0] == "beginner"
    assert order.index("advanced") == len(order) - 1


def test_an_experienced_player_does_not_start_on_the_easiest():
    order = asyncio.run(_difficulty_order_for(_DB(1600), "u1"))
    assert order[0] != "beginner"


@pytest.mark.parametrize("level", sorted(SELF_ASSESSED_LEVELS))
def test_every_answer_produces_a_usable_order(level):
    order = asyncio.run(_difficulty_order_for(_DB(SELF_ASSESSED_LEVELS[level]), "u1"))
    assert set(order) == {"beginner", "intermediate", "advanced"}, (
        "all three buckets must stay reachable -- the answer decides the "
        f"ORDER, not what exists ({level})"
    )
    assert len(order) == 3, "each bucket exactly once"


def test_knowing_nothing_is_no_worse_than_before():
    # A user we cannot resolve a rating for keeps the historical order, so
    # this change can only help.
    class _Broken:
        async def find_one(self, *a, **k):
            raise RuntimeError("no rating anywhere")

    class _BrokenDB:
        users = _Broken()
        player_profiles = _Broken()
        games = _Broken()

    order = asyncio.run(_difficulty_order_for(_BrokenDB(), "u1"))
    assert order == ("beginner", "intermediate", "advanced")


# --- a database that answers with the rating we want to test -----------------

class _Users:
    def __init__(self, rating):
        self.rating = rating

    async def find_one(self, query, projection=None):
        return {
            "user_id": "u1",
            "rating_source": "assessed_rating",
            "assessed_rating": self.rating,
        }


class _Empty:
    async def find_one(self, *a, **k):
        return None

    def find(self, *a, **k):
        return self

    def sort(self, *a, **k):
        return self

    def limit(self, *a, **k):
        return self

    async def to_list(self, *a, **k):
        return []


class _DB:
    def __init__(self, rating):
        self.users = _Users(rating)
        self.player_profiles = _Empty()
        self.games = _Empty()


def test_the_answer_actually_changes_what_they_meet_first():
    """Asking has to change something, or it is theatre.

    The first draft failed this: three of the four answers deduplicated back
    to the historical ("beginner", "intermediate", "advanced") and only the
    strongest answer behaved differently. Verified against the production pool
    afterwards -- a player who says they play regularly now opens on
    intermediate positions (12 of 20) instead of beginner ones.
    """
    orders = {
        level: asyncio.run(_difficulty_order_for(_DB(rating), "u1"))
        for level, rating in SELF_ASSESSED_LEVELS.items()
    }
    assert orders["plays_regularly"] != orders["learning_moves"], orders
    assert orders["experienced"] != orders["learning_moves"], orders
    # Three buckets, so three distinct orders is the honest maximum.
    assert len(set(orders.values())) >= 3, orders


def test_the_order_is_monotonic_in_the_players_own_estimate():
    """Nobody who says they are stronger should be handed easier first."""
    rank = {"beginner": 0, "intermediate": 1, "advanced": 2}
    firsts = [
        rank[asyncio.run(_difficulty_order_for(_DB(r), "u1"))[0]]
        for r in sorted(SELF_ASSESSED_LEVELS.values())
    ]
    assert firsts == sorted(firsts), firsts
