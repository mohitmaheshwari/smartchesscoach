"""Play a real Lichess opponent on our board (docs/play_through_lichess_scope.md).

What this is
------------
A thin, honest client for the Lichess **Board API**, plus the per-user state of
one live game. Lichess permits exactly this -- *"Play on Lichess with physical
boards and third-party clients"* -- on one condition: *"Engine assistance, or
any kind of outside help, is forbidden."*

So this module deliberately contains **no engine, no evaluation and no coaching
text**. It moves pieces and reports the board. The structural guarantee that
nothing else can reach the player mid-game lives in `live_play_guard.py`, and
this module is what turns that guard on and off: `register_live_game` the moment
Lichess says a game started, `release_live_game` the moment it is over.

Why polling and not a socket to the browser
-------------------------------------------
Lichess streams ndjson. We consume that stream in a background task and keep the
latest board in memory; the browser polls `/api/coach/play/live/state`, which is
one of the ten paths the guard allows. That matches how the rest of Play with
Coach already works (move-feedback is polled), so the frontend needs no new
transport, and it means a dropped browser tab cannot lose the game -- the task
keeps the Lichess stream alive regardless.

In-process state is sound because the backend runs exactly one uvicorn worker
(`docker/supervisord.conf:15`, `Dockerfile.backend:56`, neither passing
`--workers`). A restart loses the stream tasks, which is why
`live_play_guard.load_live_players_from_db` re-arms the guard at startup and why
`state()` reports `reconnecting` rather than claiming the game is gone: the game
still exists on Lichess and the player can finish it there.

Time controls
-------------
The Board API restricts pool seeks to Rapid, Classical and Correspondence --
*"Time controls: Rapid, Classical and Correspondence only"*. We offer 10+0, 10+5
and 15+10, which is the same set Chessiro ships, and refuse anything faster
rather than letting Lichess refuse it for us.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx

from services.live_play_guard import register_live_game, release_live_game

logger = logging.getLogger(__name__)

LICHESS = "https://lichess.org"

# Identify us honestly. If we ever break the fair-play rule, Lichess must be
# able to find us -- and we must never look like a client trying to hide.
# Deliberately carries no user identity: not a username, not an email.
USER_AGENT = "ChessGuru/1.0 (+https://chessguru.ai)"

# Rapid only. The Board API's own restriction, and the safe reading of it.
TIME_CONTROLS: Dict[str, Dict[str, int]] = {
    "10+0": {"time": 10, "increment": 0},
    "10+5": {"time": 10, "increment": 5},
    "15+10": {"time": 15, "increment": 10},
}
DEFAULT_TIME_CONTROL = "10+5"


class LichessPlayError(Exception):
    """Something Lichess refused, phrased for the player."""


@dataclass
class LiveGame:
    """One live Lichess game, as our board needs to see it. No engine data."""

    user_id: str
    game_id: str
    color: str = "white"            # the colour OUR player has
    initial_fen: str = "startpos"
    moves: str = ""                 # space-separated UCI, as Lichess sends it
    status: str = "started"
    winner: Optional[str] = None
    white_time_ms: Optional[int] = None
    black_time_ms: Optional[int] = None
    opponent: Dict[str, Any] = field(default_factory=dict)
    rated: bool = False
    speed: Optional[str] = None
    draw_offer_from: Optional[str] = None
    started_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    last_event_at: Optional[str] = None
    stream_alive: bool = False

    @property
    def finished(self) -> bool:
        return self.status not in ("started", "created")

    def board_fen(self) -> str:
        """Current position, derived from the moves Lichess has sent."""
        import chess

        board = (
            chess.Board()
            if self.initial_fen in ("startpos", "", None)
            else chess.Board(self.initial_fen)
        )
        for uci in (self.moves or "").split():
            try:
                board.push_uci(uci)
            except ValueError:
                logger.warning(
                    "live play: Lichess sent a move we cannot replay (%s in %s)",
                    uci,
                    self.game_id,
                )
                break
        return board.fen()

    def our_turn(self) -> bool:
        plies = len((self.moves or "").split())
        return (plies % 2 == 0) == (self.color == "white")

    def as_payload(self) -> Dict[str, Any]:
        """Exactly what the board needs, and nothing a coach would say."""
        return {
            "game_id": self.game_id,
            "color": self.color,
            "fen": self.board_fen(),
            "moves": self.moves,
            "status": self.status,
            "winner": self.winner,
            "finished": self.finished,
            "our_turn": (not self.finished) and self.our_turn(),
            "white_time_ms": self.white_time_ms,
            "black_time_ms": self.black_time_ms,
            "opponent": self.opponent,
            "rated": self.rated,
            "speed": self.speed,
            "draw_offer_from": self.draw_offer_from,
            "stream_alive": self.stream_alive,
            "lichess_url": f"{LICHESS}/{self.game_id}",
            "started_at": self.started_at,
        }


@dataclass
class SeekState:
    """A pending pool seek. Alive only while its HTTP connection is held open."""

    user_id: str
    time_control: str
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    cancelled: bool = False


# user_id -> state. Single worker, so these are coherent.
_GAMES: Dict[str, LiveGame] = {}
_SEEKS: Dict[str, SeekState] = {}
_TASKS: Dict[str, List[asyncio.Task]] = {}


def current_game(user_id: str) -> Optional[LiveGame]:
    return _GAMES.get(user_id)


def current_seek(user_id: str) -> Optional[SeekState]:
    return _SEEKS.get(user_id)


def _headers(token: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {token}", "User-Agent": USER_AGENT}


def _track(user_id: str, task: asyncio.Task) -> None:
    _TASKS.setdefault(user_id, []).append(task)
    task.add_done_callback(
        lambda t: _TASKS.get(user_id, []).remove(t)
        if t in _TASKS.get(user_id, [])
        else None
    )


def _cancel_tasks(user_id: str) -> None:
    for task in list(_TASKS.get(user_id, [])):
        task.cancel()
    _TASKS.pop(user_id, None)


# ------------------------------------------------------------------ the streams


async def _consume_ndjson(response: httpx.Response):
    """Yield parsed objects from a Lichess ndjson stream, skipping keep-alives."""
    async for line in response.aiter_lines():
        line = line.strip()
        if not line:          # Lichess sends blank lines as keep-alives
            continue
        try:
            yield json.loads(line)
        except json.JSONDecodeError:
            logger.warning("live play: unparseable stream line: %r", line[:120])


async def _run_game_stream(db: Any, user_id: str, token: str, game_id: str) -> None:
    """Follow one game to its end, updating our board and the guard."""
    url = f"{LICHESS}/api/board/game/stream/{game_id}"
    try:
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream("GET", url, headers=_headers(token)) as response:
                if response.status_code != 200:
                    logger.warning(
                        "live play: game stream %s refused (%s)",
                        game_id,
                        response.status_code,
                    )
                    return
                game = _GAMES.get(user_id)
                if game:
                    game.stream_alive = True
                async for event in _consume_ndjson(response):
                    _apply_game_event(user_id, event)
                    game = _GAMES.get(user_id)
                    if game and game.finished:
                        await _finish(db, user_id)
                        return
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        logger.warning("live play: game stream %s dropped: %s", game_id, exc)
    finally:
        game = _GAMES.get(user_id)
        if game:
            game.stream_alive = False


def _apply_game_event(user_id: str, event: Dict[str, Any]) -> None:
    game = _GAMES.get(user_id)
    if not game:
        return
    kind = event.get("type")
    game.last_event_at = datetime.now(timezone.utc).isoformat()

    if kind == "gameFull":
        game.initial_fen = event.get("initialFen") or "startpos"
        game.rated = bool(event.get("rated"))
        game.speed = event.get("speed")
        # Colour is NOT re-derived here. The gameStart event already told us
        # which side we have, and `gameFull` identifies players by Lichess id,
        # which we would have to resolve separately. Trusting one source beats
        # two that can disagree about which end of the board we are on.
        state = event.get("state") or {}
        _apply_state(game, state)
    elif kind == "gameState":
        _apply_state(game, event)
    elif kind == "chatLine":
        # Deliberately ignored. Opponent chat is outside help by any reading,
        # and we are not relaying it into a coaching surface.
        return


def _apply_state(game: LiveGame, state: Dict[str, Any]) -> None:
    game.moves = state.get("moves", game.moves) or ""
    game.status = state.get("status", game.status) or game.status
    game.winner = state.get("winner", game.winner)
    if state.get("wtime") is not None:
        game.white_time_ms = state.get("wtime")
    if state.get("btime") is not None:
        game.black_time_ms = state.get("btime")
    if state.get("wdraw"):
        game.draw_offer_from = "white"
    elif state.get("bdraw"):
        game.draw_offer_from = "black"
    else:
        game.draw_offer_from = None


async def _run_event_stream(db: Any, user_id: str, token: str) -> None:
    """Watch for our own game starting, then follow it.

    This is the only reliable way to learn the game id of a pool pairing: the
    seek response itself carries nothing.
    """
    url = f"{LICHESS}/api/stream/event"
    try:
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream("GET", url, headers=_headers(token)) as response:
                if response.status_code != 200:
                    logger.warning(
                        "live play: event stream refused for %s (%s)",
                        user_id,
                        response.status_code,
                    )
                    return
                async for event in _consume_ndjson(response):
                    kind = event.get("type")
                    if kind == "gameStart":
                        info = event.get("game") or {}
                        await _begin(db, user_id, token, info)
                        return                  # the game stream takes over
                    if kind == "gameFinish":
                        await _finish(db, user_id)
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        logger.warning("live play: event stream dropped for %s: %s", user_id, exc)


async def _begin(db: Any, user_id: str, token: str, info: Dict[str, Any]) -> None:
    """A real opponent is paired. Guard ON before anything else happens."""
    game_id = info.get("gameId") or info.get("id")
    if not game_id:
        logger.warning("live play: gameStart with no game id for %s", user_id)
        return

    opponent = dict(info.get("opponent") or {})
    game = LiveGame(
        user_id=user_id,
        game_id=game_id,
        color=info.get("color") or "white",
        initial_fen=info.get("fen") or "startpos",
        rated=bool(info.get("rated")),
        speed=info.get("speed"),
        opponent=opponent,
    )
    _GAMES[user_id] = game
    _SEEKS.pop(user_id, None)

    # Before the board can render anything, the engine is closed for this user.
    await register_live_game(db, user_id, game_id)
    logger.info(
        "live play: %s started lichess game %s as %s vs %s",
        user_id,
        game_id,
        game.color,
        opponent.get("username", "?"),
    )

    _track(user_id, asyncio.create_task(_run_game_stream(db, user_id, token, game_id)))


async def _finish(db: Any, user_id: str) -> None:
    """The game is over. Guard OFF, so the review can open."""
    game = _GAMES.get(user_id)
    await release_live_game(db, user_id)
    if game:
        logger.info(
            "live play: %s finished lichess game %s (%s)",
            user_id,
            game.game_id,
            game.status,
        )


# ------------------------------------------------------------------ the actions


async def start_seek(db: Any, user_id: str, token: str, time_control: str) -> SeekState:
    """Join the Lichess pool and wait for a human.

    The seek lives only as long as its HTTP connection: *"Keep the connection
    open to keep the seek active... If the client closes the connection, the
    seek is canceled."* So the connection is held by a background task, and
    cancelling the seek means cancelling that task.
    """
    if time_control not in TIME_CONTROLS:
        raise LichessPlayError(
            f"{time_control} is not offered here. Lichess allows Rapid and slower "
            "for this kind of game, so pick 10+0, 10+5 or 15+10."
        )
    existing = _GAMES.get(user_id)
    if existing and not existing.finished:
        raise LichessPlayError("You already have a game in progress.")

    _cancel_tasks(user_id)
    seek = SeekState(user_id=user_id, time_control=time_control)
    _SEEKS[user_id] = seek

    # Event stream first, then the seek: the pairing can happen instantly, and
    # Lichess's own docs warn that otherwise you miss the gameStart event.
    _track(user_id, asyncio.create_task(_run_event_stream(db, user_id, token)))
    await asyncio.sleep(0)  # let the event stream get as far as connecting
    _track(user_id, asyncio.create_task(_hold_seek(user_id, token, time_control)))
    logger.info("live play: %s seeking a %s game", user_id, time_control)
    return seek


async def _hold_seek(user_id: str, token: str, time_control: str) -> None:
    config = TIME_CONTROLS[time_control]
    data = {
        "time": str(config["time"]),
        "increment": str(config["increment"]),
        "rated": "false",          # casual until the player asks otherwise
        "variant": "standard",
    }
    try:
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream(
                "POST", f"{LICHESS}/api/board/seek",
                headers=_headers(token), data=data,
            ) as response:
                if response.status_code == 429:
                    logger.warning("live play: seek rate-limited for %s", user_id)
                    _SEEKS.pop(user_id, None)
                    return
                if response.status_code != 200:
                    body = (await response.aread())[:200]
                    logger.warning(
                        "live play: seek refused for %s (%s) %r",
                        user_id, response.status_code, body,
                    )
                    _SEEKS.pop(user_id, None)
                    return
                # The body carries nothing; holding it open IS the seek.
                async for _ in response.aiter_lines():
                    pass
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        logger.info("live play: seek for %s ended: %s", user_id, exc)
    finally:
        seek = _SEEKS.get(user_id)
        if seek and not _GAMES.get(user_id):
            _SEEKS.pop(user_id, None)


async def cancel_seek(user_id: str) -> None:
    seek = _SEEKS.pop(user_id, None)
    if seek:
        seek.cancelled = True
    _cancel_tasks(user_id)
    logger.info("live play: %s cancelled the seek", user_id)


async def _board_post(token: str, path: str) -> Dict[str, Any]:
    url = f"{LICHESS}/api/board/game/{path}"
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(url, headers=_headers(token))
    if response.status_code == 200:
        return {"ok": True}
    detail = ""
    try:
        detail = (response.json() or {}).get("error") or ""
    except Exception:
        detail = (response.text or "")[:160]
    raise LichessPlayError(detail or f"Lichess refused that ({response.status_code}).")


async def play_move(user_id: str, token: str, uci: str) -> Dict[str, Any]:
    game = _GAMES.get(user_id)
    if not game or game.finished:
        raise LichessPlayError("There is no game in progress.")
    result = await _board_post(token, f"{game.game_id}/move/{uci}")
    # Do not guess the new position: the stream is the source of truth, and it
    # arrives in milliseconds. Guessing is how a board drifts out of sync.
    return result


async def resign(user_id: str, token: str) -> Dict[str, Any]:
    game = _GAMES.get(user_id)
    if not game:
        raise LichessPlayError("There is no game in progress.")
    return await _board_post(token, f"{game.game_id}/resign")


async def abort(user_id: str, token: str) -> Dict[str, Any]:
    game = _GAMES.get(user_id)
    if not game:
        raise LichessPlayError("There is no game in progress.")
    return await _board_post(token, f"{game.game_id}/abort")


async def handle_draw(user_id: str, token: str, accept: bool) -> Dict[str, Any]:
    game = _GAMES.get(user_id)
    if not game:
        raise LichessPlayError("There is no game in progress.")
    return await _board_post(
        token, f"{game.game_id}/draw/{'yes' if accept else 'no'}"
    )


async def forget(db: Any, user_id: str) -> None:
    """Drop our copy of a finished game and make sure the guard is off."""
    _cancel_tasks(user_id)
    _SEEKS.pop(user_id, None)
    game = _GAMES.pop(user_id, None)
    await release_live_game(db, user_id)
    if game and not game.finished:
        logger.warning(
            "live play: %s abandoned %s while still playable; it continues on "
            "lichess.org",
            user_id,
            game.game_id,
        )
