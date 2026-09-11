"""A focus read must never return a strength.

`user_active_focus` stores both sides of the player model. Every read that
means "what is this player working on" has to exclude strengths, and
`focus_bridge` has owned that filter for a long time -- inlined twice.

The coach-selected Game Review selector then wrote its own query and left the
type clause out entirely:

    db.user_active_focus.find_one({"user_id": user_id, "status": "active"})

Measured on production 2026-09-11, across the 54 users with an active focus,
that returns:

    strength        39  (72%)
    weakness         7  (13%)
    no type field    8  (15%)

`focus_match` is the first sort key in `rank_candidates` and `focus_key` is
carried into the served payload, so for most users the coach would have chosen
a game -- and explained why it mattered -- on the strength of something they
are already good at. Confidently wrong is worse than not choosing.

Rows written before `type` existed are weaknesses by construction and are kept.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from services.coach_selected_review_service import _focus_key
from services.focus_bridge import ACTIVE_WEAKNESS_FILTER


class _FocusCollection:
    """Minimal find_one that honours $or / equality the way Mongo would."""

    def __init__(self, documents):
        self.documents = documents

    @staticmethod
    def _matches(document, query):
        for key, expected in query.items():
            if key == "$or":
                if not any(
                    _FocusCollection._matches(document, clause)
                    for clause in expected
                ):
                    return False
                continue
            if isinstance(expected, dict) and "$exists" in expected:
                if (key in document) != expected["$exists"]:
                    return False
                continue
            if document.get(key) != expected:
                return False
        return True

    async def find_one(self, query, projection=None):
        for document in self.documents:
            if self._matches(document, query):
                return dict(document)
        return None


class _DB:
    def __init__(self, documents):
        self.user_active_focus = _FocusCollection(documents)


def _focus(**overrides):
    document = {
        "user_id": "u1",
        "status": "active",
        "topic_key": "piece_safety",
    }
    document.update(overrides)
    return document


def test_the_filter_names_both_halves_of_the_rule():
    assert ACTIVE_WEAKNESS_FILTER == {
        "status": "active",
        "$or": [{"type": {"$exists": False}}, {"type": "weakness"}],
    }


def test_a_strength_is_never_returned_as_the_focus():
    db = _DB([_focus(type="strength", topic_key="king_safety")])
    assert asyncio.run(_focus_key(db, "u1")) == ""


def test_a_weakness_is_returned():
    db = _DB([_focus(type="weakness", topic_key="piece_safety")])
    assert asyncio.run(_focus_key(db, "u1")) == "piece_safety"


def test_a_legacy_row_without_a_type_is_still_a_weakness():
    db = _DB([_focus(topic_key="calculation_depth")])
    assert asyncio.run(_focus_key(db, "u1")) == "calculation_depth"


def test_a_strength_does_not_mask_a_real_weakness():
    # The failure that matters in production: the strength row happens to sort
    # first, so an unfiltered find_one never reaches the weakness behind it.
    db = _DB([
        _focus(type="strength", topic_key="king_safety"),
        _focus(type="weakness", topic_key="piece_safety"),
    ])
    assert asyncio.run(_focus_key(db, "u1")) == "piece_safety"


def test_no_active_focus_means_no_claimed_focus():
    # Degrades to "" rather than guessing, which drops rank_candidates through
    # to authorized richness and recency.
    db = _DB([_focus(status="retired", type="weakness")])
    assert asyncio.run(_focus_key(db, "u1")) == ""
