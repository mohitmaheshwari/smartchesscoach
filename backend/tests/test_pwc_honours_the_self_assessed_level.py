"""Play with Coach has to hear the answer onboarding just collected.

Onboarding asks a player with no Chess.com or Lichess account where they are
with chess and stores it as `assessed_rating` + `rating_source`. The canonical
resolver reads it. Play with Coach did not: it resolved strength through
`get_user_rating_from_games`, which reads synced games and platform profiles
only, and returned a hard-coded 1200 when it found neither.

So the player that question exists for -- no account, no games -- got:

  - an opponent calibrated to 1200, and
  - the 1200 speaking register, because the beginner voice is gated on
    `user_rating < 1000` in realtime_coaching_feedback.

Someone who had just said "I'm still learning how the pieces move" was handed
a 1200 opponent and addressed as an intermediate. Their answer was on file the
whole time.

The games read still wins whenever it finds anything. Self-assessment is only
consulted where the alternative was a blind default.
"""
from __future__ import annotations

import asyncio
import io
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

SESSION = BACKEND / "coach_play" / "coach_game_session.py"


def _src(path: Path) -> str:
    return io.open(path, encoding="utf-8").read()


# --- what the resolver actually returns -------------------------------------

class _One:
    def __init__(self, doc):
        self.doc = doc

    async def find_one(self, *a, **k):
        return self.doc


class _Games:
    def __init__(self, rows):
        self.rows = rows

    def find(self, *a, **k):
        return self

    async def to_list(self, *a, **k):
        return list(self.rows)


class _DB:
    def __init__(self, user, games=()):
        self.users = _One(user)
        self.player_profiles = _One(None)
        self.games = _Games(games)


def _rating(db):
    from services.rating_resolver import get_coaching_rating
    return int(asyncio.run(get_coaching_rating(db, "u1")))


def test_the_answer_survives_all_the_way_to_a_number():
    """Each answer must resolve to its own rating, not a shared default."""
    seen = {}
    for level, stored in (
        ("learning_moves", 500), ("know_rules", 800),
        ("plays_regularly", 1200), ("experienced", 1600),
    ):
        db = _DB({"user_id": "u1", "rating_source": "assessed_rating",
                  "assessed_rating": stored})
        seen[level] = _rating(db)
    assert seen == {"learning_moves": 500, "know_rules": 800,
                    "plays_regularly": 1200, "experienced": 1600}, seen


def test_a_beginners_answer_lands_under_the_beginner_threshold():
    """The register is gated on < 1000, so this is the whole point.

    A 500 that resolves to 1200 is not a smaller number -- it is a different
    voice. `realtime_coaching_feedback` sets `is_beginner = user_rating < 1000`.
    """
    db = _DB({"user_id": "u1", "rating_source": "assessed_rating",
              "assessed_rating": 500})
    assert _rating(db) < 1000


def test_a_real_platform_rating_is_never_overridden_by_self_assessment():
    """Somebody who plays online has better evidence than their own guess."""
    games = [
        {"platform": "lichess", "date_played": "2026-09-01T00:00:00+00:00",
         "user_rating": 1500, "user_color": "white"},
        {"platform": "lichess", "date_played": "2026-09-02T00:00:00+00:00",
         "user_rating": 1520, "user_color": "white"},
        {"platform": "lichess", "date_played": "2026-09-03T00:00:00+00:00",
         "user_rating": 1480, "user_color": "white"},
    ]
    db = _DB({"user_id": "u1", "rating_source": "lichess",
              "assessed_rating": 500}, games)
    assert _rating(db) > 1000, "games must outrank the self-assessment"


# --- where Play with Coach consults it --------------------------------------

def test_play_with_coach_falls_back_to_the_assessed_level():
    src = _src(SESSION)
    assert "from services.rating_resolver import get_coaching_rating" in src, (
        "the session must be able to reach the canonical resolver"
    )
    assert "rating_source = 'self_assessed'" in src


def test_it_is_consulted_only_when_the_games_read_found_nothing():
    """Narrowed on purpose: this must not change an existing player.

    The canonical resolver already prefers games, but gating on 'default' here
    means the fallback cannot alter what someone with real game history gets.
    """
    src = _src(SESSION)
    assert "if rating_source == 'default':" in src


def test_the_register_is_computed_after_the_fallback_not_before():
    """Otherwise the opponent adapts and the voice does not.

    `coaching_rating` is what gates the beginner register. If it were assigned
    from `user_rating` before the fallback ran, a beginner would get a 500
    opponent and still be spoken to as a 1200 -- which is the more damaging
    half of the original bug.
    """
    src = _src(SESSION)
    fallback = src.index("if rating_source == 'default':")
    register = src.index("coaching_rating = int(user_rating)")
    assert fallback < register, (
        "the self-assessed rating must be resolved before the register is set"
    )


def test_a_broken_lookup_never_stops_a_game_starting():
    """Starting a game matters more than calibrating it perfectly."""
    src = _src(SESSION)
    block = src[src.index("if rating_source == 'default':"):]
    block = block[:block.index("coaching_rating = int(user_rating)")]
    assert "except Exception" in block, (
        "the fallback must not be able to break session creation"
    )
