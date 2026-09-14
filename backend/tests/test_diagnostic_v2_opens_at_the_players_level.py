"""The level a player tells us has to change what they are shown.

Onboarding asks a player with no account to place themselves and stores it as
`assessed_rating`. That answer was wired to `_difficulty_order_for`, which
orders the three *difficulty* buckets of the legacy pool.

Then the v2 adaptive pool went live. v2 is *tiered* (low/mid/high), not
difficulty-bucketed, so it never calls that function -- and it opened every
session with a hardcoded "mid", for every concept. The question was still
asked, the answer still stored, and nothing downstream read it.

That is the failure this file exists to prevent: a question whose answer
changes nothing is worse than not asking, because it costs the player trust
as well as time. Measured on the legacy flow, new players got 12% of the
FIRST position right and 62% were gone by the fifth.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

import routes.diagnostic as rd
from routes.settings import SELF_ASSESSED_LEVELS


@pytest.fixture(autouse=True)
def _rating(monkeypatch):
    """Let each test state the rating the resolver would return."""
    holder = {"rating": 1200}

    async def fake_rating(db, user_id, **kwargs):
        if holder["rating"] is None:
            raise RuntimeError("no rating anywhere")
        return holder["rating"]

    import services.rating_resolver as rr
    monkeypatch.setattr(rr, "get_coaching_rating", fake_rating)
    return holder


def _tier(user_id="u1"):
    return asyncio.run(rd._v2_opening_tier(user_id))


def test_a_beginner_does_not_open_on_a_1600_position(_rating):
    _rating["rating"] = SELF_ASSESSED_LEVELS["learning_moves"]
    assert _tier() == "low"
    _rating["rating"] = SELF_ASSESSED_LEVELS["know_rules"]
    assert _tier() == "low"


def test_an_experienced_player_does_not_open_on_the_easiest(_rating):
    _rating["rating"] = SELF_ASSESSED_LEVELS["experienced"]
    assert _tier() == "high"


def test_every_answer_maps_to_a_real_tier(_rating):
    for level, rating in SELF_ASSESSED_LEVELS.items():
        _rating["rating"] = rating
        assert _tier() in {"low", "mid", "high"}, level


def test_the_answer_actually_changes_where_they_start(_rating):
    """Asking has to move something, or it is theatre."""
    tiers = {}
    for level, rating in SELF_ASSESSED_LEVELS.items():
        _rating["rating"] = rating
        tiers[level] = _tier()
    assert tiers["learning_moves"] != tiers["experienced"], tiers
    assert len(set(tiers.values())) >= 2, tiers


def test_the_start_never_goes_down_as_the_player_claims_more(_rating):
    rank = {"low": 0, "mid": 1, "high": 2}
    seen = []
    for rating in sorted(SELF_ASSESSED_LEVELS.values()):
        _rating["rating"] = rating
        seen.append(rank[_tier()])
    assert seen == sorted(seen), seen


def test_knowing_nothing_keeps_the_old_behaviour(_rating):
    """No signal must be no worse than before, never an error."""
    _rating["rating"] = None  # resolver raises
    assert _tier() == "mid"


def test_no_concept_snaps_back_to_a_hardcoded_mid():
    """Opening at the right tier only for question one is not a fix.

    A ten-concept run that resets to "mid" at each concept boundary puts the
    player back in the wrong place nine more times.
    """
    source = (BACKEND / "routes" / "diagnostic.py").read_text(encoding="utf-8")
    start = source.index("async def _v2_start_session")
    end = source.index("async def", start + 10)
    assert '_v2_pick_puzzle(concept, "mid"' not in source[start:end], (
        "the session must open at the player's tier"
    )
    # The concept-advance loop must carry the session's opening tier.
    assert 'next_concept, opening_tier, used_ids' in source, (
        "a new concept must open at the tier this player started on"
    )
    assert '_v2_pick_puzzle(next_concept, "mid"' not in source


def test_the_session_records_where_it_opened():
    """Without it stored, later concepts have nothing to read."""
    source = (BACKEND / "routes" / "diagnostic.py").read_text(encoding="utf-8")
    assert '"opening_tier": tier' in source
