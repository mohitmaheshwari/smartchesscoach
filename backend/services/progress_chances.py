"""What came up in a player's games, and what they did with it.

docs/progress_page_scope.md. Written 2026-11-27 after /progress was found to
be off for every single user: the live access gate returned enabled=0 across
all 139, so 49 people saw "Nothing you learned has disappeared" and 90 saw
"Your progress will show here".

The page is rebuilt on `move_observations` for two reasons.

1. It needs no flag. The old page's only source was the phase-8 projection,
   behind `complete_coaching_access`. The roll-up in
   `player_coach_files.behaviour_axes` is no better for this purpose: it is
   built only for the seven `BETWEEN_GAMES_USERS` ids, so reading it would
   rebuild the same gate problem. These counts are computed live, for
   anybody.

2. It has a denominator. Every row is "n of the m chances that actually came
   up", never a score, an index or a percentage of nothing. A rate out of
   chances stays honest in a week when it does not move, which a verdict
   does not.

What is deliberately NOT here:

- "Getting better". `player_coach_habit.change_state` compares the newest 20
  games with the previous 40 at one-sided p<0.10, so declaring a habit gone
  needs (1 - rate)**20 < 0.10 -- 22 clean games for a habit in 10% of games,
  45 for one in 5%. Anything rarer than about 1 game in 9 can never read as
  improved, while "worse" needs only three occurrences. Nothing here says
  better, worse, improving or mastered.

- "Found it when it mattered" (found_best_in_critical / was_critical_moment).
  Measured by the coaching session over 53 users with 200+ critical moments:
  r = +0.50 against rating, the strongest single axis on this corpus -- so
  the data is good and the absolute framing is the problem. The whole human
  range is 1.7% to 13.1% and even 1600+ players find 8.6%, so "you found it
  7 times in 100" reads as "you are bad at chess" to everybody while giving
  them nothing to do. It belongs relative to level, or coach-side. It is
  counted here, and the API does not return it.

Cost: one `$group` over the user's own observations. Measured by the
coaching session on the heaviest user (27,932 observations) over the ssh
tunnel: 243ms, against 9,324ms to fetch the documents instead. The last-10
window is computed INSIDE the same group with `$cond`, rather than as a
second query, because `move_observations` (765,780 documents) has no
`(user_id, game_id)` compound index and a windowed fetch of 244 documents
measured 2,212ms. One pass, one index, both columns.
"""

import asyncio
from typing import Any, Dict, List, Optional

# How many of the newest analysed games the "recently" column covers.
RECENT_GAMES = 10

# "Punished their mistake" offers roughly 0.7 chances a game, so ten games
# give about seven. Seven chances must not be drawn as a rate, so this axis
# is all-time only -- the API returns no recent window for it at all.
ALL_TIME_ONLY = {"punished"}


def _rate(took: int, chances: int) -> Optional[float]:
    return None if not chances else round(took / chances, 4)


async def recent_game_ids(db, user_id: str, limit: int = RECENT_GAMES) -> List[str]:
    """The newest analysed games, newest first."""
    rows = await (
        db.games.find(
            {"user_id": user_id, "is_analyzed": True},
            {"_id": 0, "game_id": 1},
        )
        .sort("imported_at", -1)
        .limit(limit)
        .to_list(limit)
    )
    return [r["game_id"] for r in rows if r.get("game_id")]


def _sum_if(condition: Any) -> Dict[str, Any]:
    return {"$sum": {"$cond": [condition, 1, 0]}}


def _both(condition: Any, recent: Any) -> Dict[str, Any]:
    return {"$sum": {"$cond": [{"$and": [recent, condition]}, 1, 0]}}


def build_pipeline(user_id: str, recent_ids: List[str]) -> List[Dict[str, Any]]:
    """One pass over this user's observations, both windows at once."""
    # `$in` against a literal array; an empty list is a constant false, which
    # is what we want for a player with no analysed games yet.
    recent = {"$in": ["$game_id", recent_ids]} if recent_ids else False

    safety_eligible = {"$eq": ["$destination_safety_exact.eligible", True]}
    # `fires` is the MISS: the piece was left where it could be taken.
    safety_missed = {"$eq": ["$destination_safety_exact.fires", True]}
    answered = {"$eq": ["$responded_to_threat", True]}
    ignored = {"$eq": ["$ignored_opponent_threat", True]}
    punished = {"$eq": ["$punished_opponent_blunder", True]}
    missed_punish = {"$eq": ["$missed_opponent_blunder", True]}

    return [
        {"$match": {"user_id": user_id}},
        {
            "$group": {
                "_id": None,
                "observations": {"$sum": 1},
                "safety_chances": _sum_if(safety_eligible),
                "safety_missed": _sum_if(safety_missed),
                "threat_answered": _sum_if(answered),
                "threat_ignored": _sum_if(ignored),
                "punish_took": _sum_if(punished),
                "punish_missed": _sum_if(missed_punish),
                "recent_safety_chances": _both(safety_eligible, recent),
                "recent_safety_missed": _both(safety_missed, recent),
                "recent_threat_answered": _both(answered, recent),
                "recent_threat_ignored": _both(ignored, recent),
            }
        },
    ]


def _axis(key: str, label: str, took: int, chances: int,
          recent_took: Optional[int], recent_chances: Optional[int]) -> Dict[str, Any]:
    axis = {
        "key": key,
        "label": label,
        "took": took,
        "chances": chances,
        "rate": _rate(took, chances),
    }
    if key not in ALL_TIME_ONLY:
        axis["recent"] = {
            "took": recent_took or 0,
            "chances": recent_chances or 0,
            "rate": _rate(recent_took or 0, recent_chances or 0),
        }
    return axis


async def build_progress_chances(db, user_id: str) -> Dict[str, Any]:
    """Three axes, each as n of the m chances that came up."""
    # The games count does not depend on the window, so it rides alongside
    # rather than adding a third round trip. Measured on the heaviest user
    # in production (85,341 observations, 2,387 games) over the ssh tunnel,
    # which is an upper bound: three sequential queries were 2,231ms.
    recent_ids, analysed_games = await asyncio.gather(
        recent_game_ids(db, user_id),
        db.games.count_documents({"user_id": user_id, "is_analyzed": True}),
    )
    cursor = db.move_observations.aggregate(build_pipeline(user_id, recent_ids))
    rows = await cursor.to_list(1)
    row = rows[0] if rows else {}

    safety_chances = row.get("safety_chances", 0)
    safety_missed = row.get("safety_missed", 0)
    recent_safety_chances = row.get("recent_safety_chances", 0)
    recent_safety_missed = row.get("recent_safety_missed", 0)

    answered = row.get("threat_answered", 0)
    ignored = row.get("threat_ignored", 0)
    recent_answered = row.get("recent_threat_answered", 0)
    recent_ignored = row.get("recent_threat_ignored", 0)

    punished = row.get("punish_took", 0)
    missed_punish = row.get("punish_missed", 0)

    axes = [
        # Kept safe = the eligible decisions where the detector did NOT fire.
        _axis(
            "piece_safety",
            "Kept your pieces safe",
            safety_chances - safety_missed,
            safety_chances,
            recent_safety_chances - recent_safety_missed,
            recent_safety_chances,
        ),
        _axis(
            "threats",
            "Answered their threat",
            answered,
            answered + ignored,
            recent_answered,
            recent_answered + recent_ignored,
        ),
        _axis(
            "punished",
            "Punished their mistake",
            punished,
            punished + missed_punish,
            None,
            None,
        ),
    ]

    return {
        "schema_version": "progress_chances.v1",
        # No flag of any kind. The whole point of this module.
        "enabled": True,
        "analysed_games": analysed_games,
        "recent_games": len(recent_ids),
        "observations": row.get("observations", 0),
        "axes": axes,
        # Said out loud rather than inferred from empty rows: a player with
        # no analysed games has no chances, not a score of zero.
        "has_evidence": bool(row.get("observations")),
    }
