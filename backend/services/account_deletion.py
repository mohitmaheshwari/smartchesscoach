"""Delete everything held for one account.

Used when a parent stops, when a coach removes a child, and when an adult
deletes their own account. The promise is the same in all three, so there is
one sweep.

Every collection is swept by `user_id`, because new collections keep appearing
and a list of the ones that matter would fall behind. Two exceptions, each for
a stated reason:

  * NOT_USER_DATA is skipped. `lichess_puzzles` is 4.1 million public puzzles
    with no `user_id` and no index on it, so sweeping it took over 200 seconds
    (measured 2026-11-07) and that was the whole wait a parent saw after
    pressing "stop and delete".
  * The shared pools name their source another way. `user_id` never matches
    them, so a deleted player's positions stayed behind, with their first name,
    until they were added here.
"""
from __future__ import annotations

import logging
from typing import Iterable, Optional

logger = logging.getLogger(__name__)

NOT_USER_DATA = frozenset({"lichess_puzzles"})

# collection -> the fields that say who a row came from
SOURCE_FIELDS = {
    "community_training_positions": ("source_user_id",),
    "community_puzzles": ("shared_by",),
}

MAX_GAMES = 50000


async def delete_user_rows(db, user_id: str, keep: Optional[Iterable[str]] = None) -> None:
    """Remove every row of this account and then the account itself.

    `keep` names collections that are the caller's to tidy (the academy keeps
    its own staff and student rows). Anything that fails is logged and the
    sweep carries on, so one odd collection cannot leave the rest behind.
    """
    keep = set(keep or ()) | {"users"} | NOT_USER_DATA
    rows = await db.games.find({"user_id": user_id}, {"_id": 0, "game_id": 1}).to_list(MAX_GAMES)
    game_ids = [g["game_id"] for g in rows]
    # Stop syncing first, so nothing arrives while the sweep runs.
    await db.users.update_one({"user_id": user_id},
                              {"$unset": {"lichess_username": "", "chess_com_username": "",
                                          "chesscom_username": ""}})
    if game_ids:
        await db.game_analyses.delete_many({"game_id": {"$in": game_ids}})
        await db.analysis_queue.delete_many({"game_id": {"$in": game_ids}})
    for name, fields in SOURCE_FIELDS.items():
        for field in fields:
            await db[name].delete_many({field: user_id})
        if game_ids:
            await db[name].delete_many({"source_game_id": {"$in": game_ids}})
    for name in await db.list_collection_names():
        if name.startswith("system.") or name in keep:
            continue
        try:
            await db[name].delete_many({"user_id": user_id})
        except Exception as exc:  # a view or capped collection must not stop the rest
            logger.warning("account sweep skipped %s: %s", name, exc)
    await db.users.delete_one({"user_id": user_id})
