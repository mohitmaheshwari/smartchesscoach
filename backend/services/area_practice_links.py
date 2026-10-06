"""Where a player can go to practise each area of their game.

Mohit, 2026-10-04, looking at the "Where you stand" card: *"nothing is clickable
for a drill"*. The card named six areas and two of them said "Needs work", and
there was nowhere to go from any of them.

A LINK IS ONLY ADDED WHEN THERE IS SOMETHING BEHIND IT. Measured 2026-09: 20 of
48 players had a focus whose practice button led to an empty page -- 12 on
king_safety and 8 on time_management. A dead button is worse than no button,
because the player spends a click to be told nothing is there. So each area is
checked for real, unsolved supply for THIS player before it becomes a link.

The supply check is a count, not a fetch: it asks whether at least one servable
position exists, and stops. It deliberately uses the same verified clause the
lesson itself uses, so the card cannot promise what the lesson would refuse.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from bson import ObjectId

# Areas whose practice comes from the verified puzzle pools, with the pattern
# name each one is stored under. The card's key and the pool's name are not
# always the same word, and resolving it here stops a caller guessing.
_POOL_AREA_PATTERNS: Dict[str, str] = {
    "piece_safety": "piece_safety",
    "king_safety": "king_safety",
    "missed_tactic": "missed_tactic",
    "tactical_oversight": "tactical_oversight",
}

# Areas whose practice is authored content rather than positions from games.
# These have no per-player supply to check -- the lessons are always there --
# so they link unconditionally.
_STATIC_AREA_LINKS: Dict[str, Dict[str, str]] = {
    "opening_knowledge": {"href": "/openings", "label": "Study your openings"},
}

# Phases are a reading, not a trainable area: there is no "middlegame drill",
# and inventing one link for all three would be a button that lies about what
# it does. Named here so the absence reads as a decision.
NO_LINK_KEYS = ("opening", "middlegame", "endgame", "endgame_technique")

# How far into the coach pool we look before concluding there is nothing
# servable. Bounded so a dead area costs one page a fixed scan rather than a
# full-collection walk; an area whose first few hundred rows all fail
# verification is not one we can honestly offer today.
_SCAN_CAP = 200


async def _has_pool_supply(db, user_id: str, pattern: str) -> bool:
    """Is there at least one verified, unsolved position for this pattern?"""
    try:
        from services.puzzle_extraction_service import verified_mongo_clause
    except Exception:
        return False

    solved_object_ids = []
    solved_strings = []
    async for row in db.puzzle_attempts.find(
            {"user_id": user_id, "correct": True}, {"_id": 0, "puzzle_id": 1}):
        value = row.get("puzzle_id")
        if not value:
            continue
        solved_strings.append(str(value))
        try:
            solved_object_ids.append(ObjectId(str(value)))
        except Exception:
            continue

    query: Dict[str, Any] = {
        "issue_type": pattern, "approved": True,
        **verified_mongo_clause(pattern),
    }
    if solved_object_ids:
        query["_id"] = {"$nin": solved_object_ids}
    if await db.community_puzzles.count_documents(query, limit=1):
        return True

    # The coach-game pool is the larger of the two and carries its own
    # vocabulary, so it is asked separately rather than folded in above.
    #
    # A COUNT IS NOT ENOUGH HERE and the first version of this file got it
    # wrong. `verdict_serves_pattern` is a Python-side check that no Mongo
    # clause can express, so counting raw rows said "supply exists" for
    # king_safety on the strength of 341 rows of which none serve -- which is
    # the dead link this module was written to prevent, rebuilt inside it.
    # Measured 2026-10-04: king_safety has 151 community puzzles and 341 coach
    # positions and ZERO of either pass verification; the same is true of
    # tactical_oversight.
    try:
        from services.puzzle_extraction_service import (
            GAP_TO_PWC_PATTERNS, verdict_serves_pattern,
        )
    except Exception:
        return False
    for pattern_type in (GAP_TO_PWC_PATTERNS.get(pattern) or ()):
        pool_query: Dict[str, Any] = {"pattern_type": pattern_type}
        if solved_strings:
            pool_query["position_id"] = {"$nin": solved_strings}
        # Capped: this answers "is there one in the first _SCAN_CAP", not "is
        # there one anywhere". An area whose first few hundred rows all fail
        # verification is not an area we can honestly offer today.
        async for candidate in db.community_training_positions.find(
                pool_query, {"_id": 0, "approved": 1, "verified_admission": 1,
                             "fen": 1, "best_move_san": 1}
        ).limit(_SCAN_CAP):
            if candidate.get("approved") is False:
                continue
            if not candidate.get("fen") or not candidate.get("best_move_san"):
                continue
            if verdict_serves_pattern(candidate, pattern):
                return True
    return False


async def practice_link(db, user_id: str, key: str) -> Optional[Dict[str, str]]:
    """Where this player can practise this area, or None to stay plain text."""
    if key in NO_LINK_KEYS:
        return None
    if key in _STATIC_AREA_LINKS:
        return dict(_STATIC_AREA_LINKS[key])

    # Spotting tactics has a drill built for the shapes this player actually
    # misses, which beats the generic tactic pool when it is available.
    if key == "missed_tactic":
        try:
            from services.motif_drill_service import practice_offer
            offer = await practice_offer(db, user_id)
        except Exception:
            offer = None
        if offer:
            return {"href": offer["href"], "label": offer["label"]}

    pattern = _POOL_AREA_PATTERNS.get(key)
    if not pattern:
        return None
    if await _has_pool_supply(db, user_id, pattern):
        return {"href": "/training/pattern/%s" % pattern, "label": "Practise this"}

    # Our own games cannot always prove a topic. `king_safety` has 151
    # community puzzles and 341 coach positions and not one passes
    # verification, because there is no king-safety prover and none of them
    # involve mate -- they carry a classifier's opinion, not evidence.
    #
    # Rather than certify them anyway, serve positions that already carry
    # proof. See services/topic_practice_themes.py for which themes are
    # allowed for which topic, and which obvious-looking ones are not.
    from services.topic_practice_themes import mongo_query

    query = mongo_query(pattern, await _rating_of(db, user_id))
    if query and await db.lichess_puzzles.count_documents(query, limit=1):
        return {"href": "/training/theme/%s" % pattern, "label": "Practise this"}
    return None


async def _rating_of(db, user_id: str):
    """The player's own rating, for choosing a difficulty band."""
    profile = await db.player_profiles.find_one(
        {"user_id": user_id}, {"_id": 0, "current_rating": 1})
    if profile and profile.get("current_rating"):
        return profile["current_rating"]
    game = await db.games.find_one(
        {"user_id": user_id, "user_rating": {"$ne": None}},
        {"_id": 0, "user_rating": 1}, sort=[("played_at_utc", -1)])
    return (game or {}).get("user_rating")


async def attach_practice_links(db, user_id: str, payload: Dict[str, Any]
                                ) -> Dict[str, Any]:
    """Add `practice` to every row that has somewhere real to send the player."""
    for group in ("areas", "phases"):
        for row in payload.get(group) or ():
            if not isinstance(row, dict):
                continue
            link = await practice_link(db, user_id, str(row.get("key") or ""))
            if link:
                row["practice"] = link
    return payload
