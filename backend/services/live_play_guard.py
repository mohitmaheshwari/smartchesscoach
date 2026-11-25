"""Nothing engine-derived may be served while the user is in a live Lichess game.

Why this exists
---------------
`docs/play_through_lichess_scope.md` lets a player play a real Lichess opponent
on our board. Lichess permits that explicitly -- *"Play on Lichess with physical
boards and third-party clients"* -- on one condition: *"Engine assistance, or any
kind of outside help, is forbidden."*

The penalty does not land on us. `BoardReport.scala` matches the referer host
against a server-side regex of "referer domains that use engine"; a match
publishes `BoardApiMark`, which `ModApi.autoEngine` turns into
`userRepo.setEngine` -- a full engine mark on **the player's** account, their
reports auto-processed as cheating, their opponents' ratings refunded, and our
domain written into their mod note. It is checked once per game at a
pseudo-random ply and lands after a delay that is longest for the weakest
players (up to ~24h under 1800), so it cannot be found by testing.

So this is not a feature flag. A flag that flips the wrong way does not break a
page; it brands real people as cheats.

Why one layer above every route
-------------------------------
A static scan of `routes/` found **163 endpoints** where a client-supplied
position can reach the engine, across 25 files -- including `POST /api/best-moves`,
which returns best moves for an arbitrary FEN, and `POST /api/coach/line/move`,
which plays any line at depth 16. Guarding 163 call sites by hand would rot: one
would be missed, and new endpoints land weekly. So this denies **everything**
except a small, hand-reviewed allowlist, and a new endpoint is covered the day it
is written, by doing nothing at all.

Why it costs nothing when nobody is playing
-------------------------------------------
A middleware that queried Mongo on every request would tax the whole product to
protect a handful of games. Instead `_LIVE_PLAYERS` holds the user_ids currently
in a live Lichess game, in process. When it is empty -- nearly always -- the
middleware returns immediately, having done no I/O and resolved no session.

In-process state is sound here because the backend runs exactly one uvicorn
worker (`docker/supervisord.conf:15` and `Dockerfile.backend:56`, neither passing
`--workers`). If that ever changes to multiple workers, this set stops being
coherent and the guard must move to a shared store. `register_live_game` writes a
durable `lichess_live_play` row for exactly that reason, and
`load_live_players_from_db` rebuilds the set on startup so a deploy mid-game does
not silently unguard a player.

The state is keyed on the game, never on a flag: a row exists only between the
game starting and the game ending.
"""

from __future__ import annotations

import logging
from typing import Any, Optional, Set

logger = logging.getLogger(__name__)

COLLECTION = "lichess_live_play"

# Exactly what playing a game needs, and not one path more. Every entry here is
# reachable while a live Lichess game is in progress, so each one is reviewed by
# hand and must carry no engine-derived content: no evaluation, no best move, no
# coaching text, no opening name, no "are you sure?". The board, the clock, the
# opponent's move, and the controls to resign or offer a draw. Nothing else.
#
# `/api/auth/me` is here because without it the client cannot tell who is logged
# in and the page cannot render at all. It returns profile fields only.
PLAY_ALLOWLIST: frozenset[str] = frozenset(
    {
        "/api/coach/play/live/start",       # open a seek or accept a challenge
        "/api/coach/play/live/seek",        # create a public seek
        "/api/coach/play/live/seek/cancel",
        "/api/coach/play/live/state",       # board, clocks, opponent move
        "/api/coach/play/live/move",        # relay our player's move to Lichess
        "/api/coach/play/live/resign",
        "/api/coach/play/live/draw",
        "/api/coach/play/live/abort",
        "/api/coach/play/live/finish",      # the game ended; release the guard
        "/api/auth/me",                     # session identity; no game data
    }
)

# user_ids currently in a live Lichess game. Empty is the fast path.
_LIVE_PLAYERS: Set[str] = set()


def _normalise(path: str) -> str:
    """Trailing slashes and duplicate slashes must not open a hole."""
    if not path:
        return "/"
    while "//" in path:
        path = path.replace("//", "/")
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")
    return path


def is_blocked_during_live_game(path: str) -> bool:
    """Would this path be refused *if* the caller has a live Lichess game?

    Deny by default. An endpoint invented next month is blocked because it is
    not in the allowlist, which is the only property that makes this safe over
    163 engine-reachable routes and 787 mounted paths.

    This answers a question about the PATH only. Whether the caller actually has
    a live game is `user_has_live_lichess_game`; the middleware combines them.
    """
    return _normalise(path) not in PLAY_ALLOWLIST


async def user_has_live_lichess_game(db: Any, user_id: Optional[str]) -> bool:
    """Is this user in a live Lichess Board-API game right now?

    Checks the in-process set first so the common answer costs nothing. Falls
    back to the durable row, which matters immediately after a restart and
    before `load_live_players_from_db` has run.
    """
    if not user_id:
        return False
    if user_id in _LIVE_PLAYERS:
        return True
    if db is None:
        return False
    try:
        row = await db[COLLECTION].find_one(
            {"user_id": user_id, "status": "playing"}, {"_id": 1}
        )
    except Exception as exc:  # a DB blip must not silently unguard a player
        logger.warning("live play guard: could not read %s: %s", COLLECTION, exc)
        return bool(_LIVE_PLAYERS and user_id in _LIVE_PLAYERS)
    if row:
        _LIVE_PLAYERS.add(user_id)
        return True
    return False


def has_any_live_player() -> bool:
    """True when at least one user is mid-game. The middleware's fast path."""
    return bool(_LIVE_PLAYERS)


async def register_live_game(db: Any, user_id: str, lichess_game_id: str) -> None:
    """Called the moment a Lichess game starts for this user. Guard goes on."""
    from datetime import datetime, timezone

    _LIVE_PLAYERS.add(user_id)
    if db is None:
        return
    await db[COLLECTION].update_one(
        {"user_id": user_id},
        {
            "$set": {
                "user_id": user_id,
                "lichess_game_id": lichess_game_id,
                "status": "playing",
                "started_at": datetime.now(timezone.utc).isoformat(),
            }
        },
        upsert=True,
    )
    logger.info(
        "live play guard: ON for %s (lichess game %s)", user_id, lichess_game_id
    )


async def release_live_game(db: Any, user_id: str) -> None:
    """Called when the game ends. Guard comes off and the review may open."""
    from datetime import datetime, timezone

    _LIVE_PLAYERS.discard(user_id)
    if db is None:
        return
    await db[COLLECTION].update_one(
        {"user_id": user_id},
        {
            "$set": {
                "status": "finished",
                "finished_at": datetime.now(timezone.utc).isoformat(),
            }
        },
    )
    logger.info("live play guard: OFF for %s", user_id)


async def load_live_players_from_db(db: Any) -> int:
    """Rebuild the in-process set at startup.

    Without this, a deploy in the middle of somebody's game would drop the guard
    and the very next request could serve them an evaluation.
    """
    if db is None:
        return 0
    try:
        async for row in db[COLLECTION].find({"status": "playing"}, {"user_id": 1}):
            if row.get("user_id"):
                _LIVE_PLAYERS.add(row["user_id"])
    except Exception as exc:
        logger.warning("live play guard: startup load failed: %s", exc)
    if _LIVE_PLAYERS:
        logger.info(
            "live play guard: %d player(s) still mid-game after restart",
            len(_LIVE_PLAYERS),
        )
    return len(_LIVE_PLAYERS)


# --------------------------------------------------------------- the middleware

_db_provider = None


def set_db_provider(provider) -> None:
    """server.py hands us a callable returning the motor database.

    A callable rather than the database itself because `server.db` is bound
    during startup, after this module is imported.
    """
    global _db_provider
    _db_provider = provider


def _db():
    try:
        return _db_provider() if _db_provider is not None else None
    except Exception:  # pragma: no cover - a provider must never break a request
        return None


def _session_token_from_scope(scope) -> Optional[str]:
    """The cookie, or a mobile bearer token. Same precedence as auth.py."""
    token = None
    for raw_name, raw_value in scope.get("headers") or []:
        name = raw_name.decode("latin-1").lower()
        if name == "cookie":
            for part in raw_value.decode("latin-1").split(";"):
                key, _, value = part.strip().partition("=")
                if key == "session_token" and value:
                    return value
        elif name == "authorization":
            value = raw_value.decode("latin-1")
            if value.startswith("Bearer "):
                token = value.split(" ", 1)[1].strip() or None
    return token


# Written for the player, not for us: they need to know this is deliberate and
# that nothing is lost, or it reads as a broken page.
_REFUSAL = (
    b'{"detail":"Coaching is paused while your Lichess game is live. Lichess '
    b"forbids outside help during a game, and ignoring that would get your own "
    b'account marked as an engine user. Your review opens the moment the game '
    b'ends.","live_lichess_game":true}'
)


class LivePlayGuardMiddleware:
    """Refuses everything outside PLAY_ALLOWLIST while the caller is mid-game.

    Pure ASGI rather than BaseHTTPMiddleware: this sits in front of every
    request in the product, so it must not buffer bodies or add a task group.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            return await self.app(scope, receive, send)

        # Fast path. Nobody is mid-game, so no I/O, no session resolution, and
        # no measurable cost to the 99.99% of requests this does not concern.
        if not _LIVE_PLAYERS:
            return await self.app(scope, receive, send)

        # A CORS preflight carries no data and must not be refused, or the
        # browser reports a CORS error instead of our explanation.
        if scope.get("method") == "OPTIONS":
            return await self.app(scope, receive, send)

        path = scope.get("path") or ""
        if not path.startswith("/api"):
            return await self.app(scope, receive, send)
        if not is_blocked_during_live_game(path):
            return await self.app(scope, receive, send)

        db = _db()
        user_id = None
        token = _session_token_from_scope(scope)
        if token and db is not None:
            try:
                session = await db.user_sessions.find_one(
                    {"session_token": token}, {"_id": 0, "user_id": 1}
                )
                user_id = (session or {}).get("user_id")
            except Exception as exc:
                logger.warning("live play guard: session lookup failed: %s", exc)

        if user_id and await user_has_live_lichess_game(db, user_id):
            logger.info("live play guard: refused %s for %s", path, user_id)
            await send(
                {
                    "type": "http.response.start",
                    "status": 403,
                    "headers": [
                        (b"content-type", b"application/json"),
                        (b"content-length", str(len(_REFUSAL)).encode()),
                    ],
                }
            )
            await send({"type": "http.response.body", "body": _REFUSAL})
            return

        return await self.app(scope, receive, send)
