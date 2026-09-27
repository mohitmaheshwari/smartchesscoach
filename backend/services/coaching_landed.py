"""Did the coaching reach the player, and did he do anything about it?

docs/two_layer_coaching_scope.md, signed off 2026-09-28.

Every other detector in this product measures the player's chess. This one
measures whether OUR coaching arrived. Without it, "the coaching failed" and "he
never heard it" are the same row in the database -- which is the state that 326
focus documents and zero resolutions leaves us in.

Measured over every focus ever written, 2026-09-27:

    told something (a focus with a start date)        54 players
    came back and played 3+ games since               39
    practised anything since                          29
    the named pattern moved:        11 better, 9 worse, 14 flat

Three completely different failures, currently invisible as one:

    never came back            re-engagement -- nothing to do with chess
    came back, never practised the ask was wrong, too hard, or unseen
    practised, nothing moved   THE DIAGNOSIS WAS WRONG
    practised, it moved        say so -- never yet said by this product

The point is not the aggregate. It is that these four demand four different
responses, and today we cannot tell which one we are looking at.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

# Fewer than this since we spoke and the player has not really had a chance to
# show us anything. Taken from the funnel measurement above, where it separated
# 15 players who effectively left from 39 who came back.
MIN_GAMES_SINCE = 3

# How much the named pattern's rate must move to count as movement. Provisional:
# the measured median change across 34 players was -3%, so anything inside a
# tenth is indistinguishable from doing nothing at this sample size. Revisit when
# there are more closed focuses than the 34 this was drawn from.
MOVED_FRACTION = 0.10

NEVER_RETURNED = "never_returned"
CAME_BACK_UNPRACTISED = "came_back_unpractised"
NOT_YET_MEASURABLE = "not_yet_measurable"
PRACTISED_NO_CHANGE = "practised_no_change"
PRACTISED_AND_MOVED = "practised_and_moved"
PRACTISED_AND_WORSE = "practised_and_worse"

# What each verdict means for US, which is the whole reason to record it. These
# are notes to the team, never shown to a player.
MEANS = {
    NEVER_RETURNED: "re-engagement problem; nothing here is about chess",
    CAME_BACK_UNPRACTISED: "the ask was wrong, too hard, or never seen",
    NOT_YET_MEASURABLE: "not enough either side yet; say nothing",
    PRACTISED_NO_CHANGE: "the diagnosis was wrong -- this is the one to act on",
    PRACTISED_AND_MOVED: "it worked; tell the player",
    PRACTISED_AND_WORSE: "it worked against them; stop and look",
}


def landing_stage(
    games_since: int,
    practice_events: int,
    rate_before: Optional[float],
    rate_after: Optional[float],
) -> str:
    """Which of the four failures (or the success) this player is in.

    Order matters and is not arbitrary: each stage gates the next, because a
    player who never came back cannot have practised, and one who never
    practised cannot tell us whether the diagnosis was right.
    """
    if (games_since or 0) < MIN_GAMES_SINCE:
        return NEVER_RETURNED
    if (practice_events or 0) <= 0:
        return CAME_BACK_UNPRACTISED
    if rate_before is None or rate_after is None or not rate_before:
        return NOT_YET_MEASURABLE
    delta = (rate_after - rate_before) / rate_before
    if delta <= -MOVED_FRACTION:
        return PRACTISED_AND_MOVED
    if delta >= MOVED_FRACTION:
        return PRACTISED_AND_WORSE
    return PRACTISED_NO_CHANGE


def _as_datetime(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None


async def evaluate_landing(db, focus: Dict[str, Any]) -> Dict[str, Any]:
    """The landing record for one focus.

    Splits on `played_at_utc`, the typed date, never on the `date_played`
    string: that holds ISO timestamps, chess.com's dotted `2026.04.15` and
    nothing for coach games, and "." sorts above "-" in ASCII, so a string
    comparison puts every dotted date after every timestamp whatever day it
    names. That already put 407 games on the wrong side of 15 focus windows.
    """
    user_id = focus.get("user_id")
    topic = focus.get("topic_key")
    since = _as_datetime(focus.get("started_at"))
    if not user_id or not since:
        return {"stage": NOT_YET_MEASURABLE, "reason": "focus has no start date"}

    after_ids = [d["game_id"] for d in await db.games.find(
        {"user_id": user_id, "is_analyzed": True,
         "played_at_utc": {"$gte": since}},
        {"_id": 0, "game_id": 1}).to_list(length=5000)]
    before_ids = [d["game_id"] for d in await db.games.find(
        {"user_id": user_id, "is_analyzed": True,
         "played_at_utc": {"$lt": since}},
        {"_id": 0, "game_id": 1}).to_list(length=5000)]

    practice = 0
    for collection, field in (("puzzle_attempts", "created_at"),
                              ("learning_sessions", "created_at")):
        try:
            practice += await db[collection].count_documents(
                {"user_id": user_id, field: {"$gte": since}})
        except Exception:
            # A stored string date will not compare against a datetime. Counting
            # zero is wrong in the safe direction -- it reports "never
            # practised", which asks a human to look rather than claiming the
            # diagnosis failed.
            pass

    async def rate(game_ids):
        if not game_ids or not topic:
            return None
        n = await db.move_observations.count_documents(
            {"user_id": user_id, "missed_pattern": topic,
             "game_id": {"$in": list(game_ids)}})
        return n / len(game_ids)

    before, after = await rate(before_ids), await rate(after_ids)
    stage = landing_stage(len(after_ids), practice, before, after)
    return {
        "schema_version": "coaching_landed.v1",
        "stage": stage,
        "means": MEANS.get(stage),
        "user_id": user_id,
        "topic_key": topic,
        "games_since": len(after_ids),
        "practice_events": practice,
        # internal only, never rendered: rates are numbers
        "_rate_before": before,
        "_rate_after": after,
    }
