"""Real rating curves since a player joined, for the public page.

Mohit pointed twice at Chessiro's "Since they joined" strip -- a row of real
players with a rating sparkline from the day they joined to now -- and said
we never built it. This is the data behind ours.

WHAT IS TRUE HERE, AND WHAT IS NOT. Measured on production 2026-11-27:

  139 users
   76  have no games at all since the day they signed up
    7  have fewer than ten
   55  are usable

  of those 55:  32 went up,  2 flat,  21 went DOWN

So a strip of winners is a real but SELECTED view: 38% of the players with
enough games to measure lost rating over the same period. The module
therefore always returns the full counts next to the curves, and the page
is expected to print them. A proof strip that cannot be checked against its
own denominator is an advertisement, not proof.

AND IT IS NOT A CLAIM ABOUT US. On 2026-11-26 one user's rating rose 337
points across 754 analysed games while their mistake rates barely moved
(memory: rating_rose_causes_flat). Most of these 139 accounts predate the
coaching features entirely. "Since they joined" is a true statement about
when the clock started, not about what moved the needle, and nothing here
may be worded as "because of ChessGuru".

ANONYMOUS BY DEFAULT. The reference shows handles and avatars. A chess.com
or Lichess handle is public, but publishing it NEXT TO our product name
states that this person uses ChessGuru, which they never agreed to. No
consent field exists on the user document -- I looked. So this returns no
handle, no avatar and no user id, and turning that on is Mohit's decision
to make with a consent flow behind it, not a default.
"""

import time
from typing import Any, Dict, List, Optional

# A curve needs enough games to be a curve rather than two points.
MIN_GAMES = 10
# How many points to draw. Any more is noise at sparkline size.
CURVE_POINTS = 24
# The strip shows this many. The counts beside it still describe all of them.
STRIP_SIZE = 8
# Recomputed at most this often: it is the same answer for every visitor and
# it reads every game of every user.
CACHE_SECONDS = 3600

_cache: Dict[str, Any] = {"at": 0.0, "value": None}


def _parse(value: Any):
    """users.created_at is an ISO string; games.played_at_utc is a naive
    datetime. Comparing the two without this returned zero of everything,
    which looks exactly like a real finding and was a bug."""
    from datetime import datetime

    if value is None:
        return None
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError:
            return None
    return value.replace(tzinfo=None) if getattr(value, "tzinfo", None) else value


def _curve(ratings: List[int], points: int = CURVE_POINTS) -> List[int]:
    """Evenly sampled, first and last always kept."""
    if len(ratings) <= points:
        return ratings
    step = (len(ratings) - 1) / (points - 1)
    return [ratings[round(i * step)] for i in range(points)]


async def build_rating_journeys(db) -> Dict[str, Any]:
    """Every user's rating from signup to their newest game."""
    rows: List[Dict[str, Any]] = []
    no_games = 0
    too_few = 0

    async for user in db.users.find({}, {"_id": 0, "user_id": 1, "created_at": 1}):
        joined = _parse(user.get("created_at"))
        if not joined:
            continue
        games = await (
            db.games.find(
                {
                    "user_id": user["user_id"],
                    "user_rating": {"$exists": True, "$ne": None},
                    "played_at_utc": {"$gte": joined},
                },
                {"_id": 0, "user_rating": 1},
            )
            .sort("played_at_utc", 1)
            .to_list(5000)
        )
        if not games:
            no_games += 1
            continue
        if len(games) < MIN_GAMES:
            too_few += 1
            continue
        ratings = [int(g["user_rating"]) for g in games]
        rows.append(
            {
                "games": len(ratings),
                "start": ratings[0],
                "end": ratings[-1],
                "delta": ratings[-1] - ratings[0],
                "curve": _curve(ratings),
            }
        )

    up = sum(1 for r in rows if r["delta"] > 0)
    down = sum(1 for r in rows if r["delta"] < 0)
    flat = len(rows) - up - down

    rows.sort(key=lambda r: -r["delta"])

    return {
        "schema_version": "rating_journeys.v1",
        # No handle, no avatar, no user id. See the note at the top.
        "journeys": rows[:STRIP_SIZE],
        # Always returned, so the page can state the denominator beside the
        # curves rather than showing winners alone.
        "counts": {
            "measurable": len(rows),
            "up": up,
            "flat": flat,
            "down": down,
            "no_games_since_joining": no_games,
            "too_few_games": too_few,
        },
    }


CACHE_COLLECTION = "public_cache"
CACHE_ID = "rating_journeys.v1"

_refreshing = False


async def _refresh(db) -> Dict[str, Any]:
    """Recompute and store. Also updates the in-process copy."""
    global _refreshing
    _refreshing = True
    try:
        value = await build_rating_journeys(db)
        await db[CACHE_COLLECTION].update_one(
            {"_id": CACHE_ID},
            {"$set": {"value": value, "at": time.time()}},
            upsert=True,
        )
        _cache["at"] = time.time()
        _cache["value"] = value
        return value
    finally:
        _refreshing = False


async def cached_rating_journeys(db, now: Optional[float] = None) -> Dict[str, Any]:
    """Never blocks a visitor on the full computation.

    It reads every game of every user, which measured 14,795ms over the ssh
    tunnel -- fine as an hourly job, unacceptable on a page load, and this
    is a PUBLIC page where the visitor has no reason to wait for us. So:
    serve whatever is stored, even if stale, and kick the recomputation off
    behind the response. The very first call after the collection is empty
    returns an empty strip rather than holding the request open; the page
    simply does not draw the strip that once.

    Persisted in Mongo rather than only in memory so a deploy does not send
    the next visitor back to the empty case.
    """
    import asyncio

    stamp = time.time() if now is None else now

    if _cache["value"] is not None and stamp - _cache["at"] < CACHE_SECONDS:
        return _cache["value"]

    stored = await db[CACHE_COLLECTION].find_one({"_id": CACHE_ID}, {"_id": 0})
    if stored and stored.get("value"):
        _cache["at"] = stored.get("at", 0.0)
        _cache["value"] = stored["value"]
        if stamp - _cache["at"] >= CACHE_SECONDS and not _refreshing:
            asyncio.create_task(_refresh(db))
        return _cache["value"]

    if not _refreshing:
        asyncio.create_task(_refresh(db))
    return {
        "schema_version": "rating_journeys.v1",
        "journeys": [],
        "counts": None,
        "warming": True,
    }
