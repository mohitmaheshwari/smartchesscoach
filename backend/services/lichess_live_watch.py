"""Notice a Lichess game the moment it ends, instead of up to five minutes later.

Why this exists
---------------
`quick_sync_loop` polls every 5 minutes, so a player who has just lost waits
between 0 and 5 minutes for us to even learn the game happened, then ~1.4
minutes for Stockfish. Measured on prod 2026-11-25, the fast path was 5.1 /
8.2 / 9.1 / 12.4 / 22.3 minutes from last move to imported. The review lands
long after the player has stopped caring.

This watcher closes the detection half. Lichess publishes a free, unauthenticated
endpoint whose entire purpose is this:

    GET /api/users/status?ids=a,b,c&withGameIds=true

and its own documentation says "This API is very fast and cheap on lichess
side. So you can call it quite often (like once every 5 seconds). Use it to
track players and know when they're connected on lichess and playing games."
It returns a `playingId` per user. When that id disappears or changes, that
game is over, and we can fetch it immediately -- a finished game exports with
no delay (the documented 3-move delay applies only while a game is playable).

What it deliberately does NOT do
--------------------------------
1. It does not import anything. On a finished game it calls the existing
   `sync_user_games`, which already owns fetching, de-duplication, storage and
   queueing. The watcher only changes *when* that runs, so there is one import
   path, not two.
2. It needs no OAuth and no new scope. Only the `lichess_username` we already
   store. That matters because the alternative -- `challenge:read` plus
   `/api/stream/event` -- is sub-second but requires every existing user to
   re-authorise, and almost nobody returns to click a reconnect button.
3. It never plays, and nothing here may ever surface coaching during a live
   game. Playing through Lichess means `board:play`, where any engine-derived
   hint is cheating and Lichess auto-marks *our users* as engine cheaters by
   referer domain. See memory/project_lichess_board_api_forbids_in_game_coaching.md.

Degradation: if Lichess is unreachable, rate-limits us, or omits a user, the
watcher simply learns nothing this cycle and the 5-minute loop still catches
the game. It is an accelerator, never the only path.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Awaitable, Callable, Dict, List, Optional, Sequence

logger = logging.getLogger(__name__)

LICHESS_STATUS_URL = "https://lichess.org/api/users/status"

# Lichess caps `ids` at 100 per request and rejects the rest.
MAX_IDS_PER_REQUEST = 100

# Generic client name, as Lichess asks ("Requests missing an appropriate
# User-Agent header may be rejected or rate limited"). It carries no user
# identity -- never put an account, email or username in here.
USER_AGENT = "ChessCoachAI/1.0"

# Don't re-sync the same user more often than this however many games they
# finish. One sync already pulls every game since the last watermark.
PER_USER_SYNC_COOLDOWN_SECONDS = 60


class WatchState:
    """What we last saw each player doing. Lives in memory on purpose.

    A restart loses it, and the only cost is that the first cycle after a
    restart treats everyone as "not previously playing", so a game that ended
    during the restart is picked up by the 5-minute loop instead. Persisting
    this would buy nothing and add a collection.
    """

    def __init__(self) -> None:
        # lichess username (lowercased, as Lichess returns it) -> game id
        self.playing: Dict[str, Optional[str]] = {}
        # lichess username -> monotonic clock of the last sync we fired
        self.last_sync_at: Dict[str, float] = {}

    def games_that_just_ended(
        self, statuses: Sequence[dict]
    ) -> List[str]:
        """Usernames whose game ended since the previous cycle.

        `statuses` is Lichess's reply. A user it does not return is left
        untouched: absence is not evidence a game finished, and guessing would
        fire a pointless sync every cycle for anyone we cannot see.
        """
        finished: List[str] = []
        for entry in statuses:
            if not isinstance(entry, dict):
                continue
            name = (entry.get("id") or entry.get("name") or "").lower()
            if not name:
                continue
            current = entry.get("playingId") if entry.get("playing") else None
            previous = self.playing.get(name)
            # A changed id means one game ended and another began; that still
            # means a finished game we have not fetched.
            if previous and previous != current:
                finished.append(name)
            self.playing[name] = current
        return finished

    def may_sync(self, name: str, now: Optional[float] = None) -> bool:
        now = time.monotonic() if now is None else now
        last = self.last_sync_at.get(name)
        if last is not None and (now - last) < PER_USER_SYNC_COOLDOWN_SECONDS:
            return False
        self.last_sync_at[name] = now
        return True


def _chunk(items: Sequence[str], size: int) -> List[List[str]]:
    return [list(items[i : i + size]) for i in range(0, len(items), size)]


async def lichess_usernames(db) -> Dict[str, dict]:
    """Lowercased lichess username -> the user document.

    `$nin` rather than `{"$ne": None, "$ne": ""}`: the latter is one dict with
    a duplicate key, so Python keeps only the last pair and the None test is
    dropped. That exact bug is what made this feature look necessary in the
    first place (see tests/test_a_dict_literal_never_repeats_a_key.py).
    """
    out: Dict[str, dict] = {}
    cursor = db.users.find(
        {"lichess_username": {"$nin": [None, ""]}},
        {"_id": 0, "user_id": 1, "lichess_username": 1, "chess_com_username": 1,
         "chesscom_username": 1, "last_game_sync": 1,
         "last_game_sync_lichess": 1, "last_game_sync_chesscom": 1},
    )
    for doc in await cursor.to_list(1000):
        name = (doc.get("lichess_username") or "").strip().lower()
        if name:
            out[name] = doc
    return out


async def fetch_statuses(
    usernames: Sequence[str],
    http_get: Callable[..., Awaitable],
) -> List[dict]:
    """One `users/status` call per chunk, strictly sequentially.

    Lichess's rule is "Only make one request at a time", so these are awaited
    in turn rather than gathered.
    """
    statuses: List[dict] = []
    for chunk in _chunk(usernames, MAX_IDS_PER_REQUEST):
        try:
            response = await http_get(
                LICHESS_STATUS_URL,
                params={"ids": ",".join(chunk), "withGameIds": "true"},
                headers={"User-Agent": USER_AGENT},
            )
        except Exception as exc:  # network, timeout, DNS -- never fatal
            logger.warning("lichess live watch: status call failed: %s", exc)
            continue
        status_code = getattr(response, "status_code", 200)
        if status_code == 429:
            logger.warning("lichess live watch: rate limited, backing off a cycle")
            return statuses
        if status_code != 200:
            logger.warning("lichess live watch: status %s", status_code)
            continue
        try:
            body = response.json()
        except Exception as exc:
            logger.warning("lichess live watch: unreadable reply: %s", exc)
            continue
        if isinstance(body, list):
            statuses.extend(body)
    return statuses


async def run_cycle(db, state: WatchState, http_get, sync_user_games) -> int:
    """One pass. Returns how many users we fired a sync for."""
    users = await lichess_usernames(db)
    if not users:
        return 0

    statuses = await fetch_statuses(sorted(users), http_get)
    if not statuses:
        return 0

    fired = 0
    for name in state.games_that_just_ended(statuses):
        doc = users.get(name)
        if doc is None or not state.may_sync(name):
            continue
        try:
            await sync_user_games(db, doc["user_id"], doc)
            fired += 1
            logger.info(
                "lichess live watch: %s finished a game, synced immediately", name
            )
        except Exception as exc:
            # The 5-minute loop will retry this user; do not kill the cycle.
            logger.error("lichess live watch: sync failed for %s: %s", name, exc)
    return fired


async def live_watch_loop(db, interval_seconds: int) -> None:
    """Forever. Never raises, so a bad cycle cannot take the loop down."""
    import httpx

    from journey_service import sync_user_games

    state = WatchState()
    # Let the app settle, and let quick_sync_loop take the first pass.
    await asyncio.sleep(30)

    logger.info(
        "lichess live watch: started, polling every %ss", interval_seconds
    )
    async with httpx.AsyncClient(timeout=15) as client:
        while True:
            try:
                await run_cycle(db, state, client.get, sync_user_games)
            except Exception as exc:
                logger.error("lichess live watch: cycle error: %s", exc)
            await asyncio.sleep(interval_seconds)
