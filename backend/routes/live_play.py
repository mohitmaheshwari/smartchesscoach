"""Play vs Human: a real Lichess opponent, on our board.

Mohit, 2026-11-25: *"a separate section inside play with coach, play vs human,
something and then shows lichess board"*. This is the backend for that section.

Every path here is in `services/live_play_guard.PLAY_ALLOWLIST`, which is the
only reason they keep working while the game is live -- the guard refuses every
other `/api` path for that user until the game ends. So these handlers carry a
special obligation: **nothing they return may be engine-derived.** No
evaluation, no best move, no "are you sure?", no opening name, no coaching
sentence. The board, the clocks, the opponent, the controls. That is the whole
contract, and breaking it would get the player's own Lichess account marked as
an engine user.

If you add a field to any response here, ask whether a player could use it to
choose a move. If yes, it does not belong in this file.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException

from routes.auth import User, get_current_user
from services import lichess_board_play as play
from services.lichess_board_play import LichessPlayError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/coach/play/live", tags=["Play vs Human"])

db = None

# Playing requires a token that carries this scope. Tokens issued before
# 2026-11-25 only have "preference:read email:read", so those users must
# reconnect once -- see routes/oauth.py.
REQUIRED_SCOPE = "board:play"


def set_db(database):
    global db
    db = database


async def _user_doc(user: User) -> dict:
    if db is None:
        raise HTTPException(status_code=503, detail="Database not ready")
    doc = await db.users.find_one({"user_id": user.user_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="User not found")
    return doc


def _token_or_reconnect(doc: dict) -> str:
    """The Lichess token, or a 409 that tells the client to reconnect.

    A 409 rather than a 401: the user IS authenticated with us, they simply
    have not granted Lichess the permission to move pieces on their behalf.
    The frontend turns this into one "Reconnect Lichess to play" button.
    """
    token = (doc.get("lichess_token") or "").strip()
    if not token:
        raise HTTPException(
            status_code=409,
            detail={
                "reason": "lichess_not_connected",
                "message": "Connect your Lichess account to play here.",
            },
        )
    scopes = (doc.get("lichess_scopes") or "").split()
    if REQUIRED_SCOPE not in scopes:
        raise HTTPException(
            status_code=409,
            detail={
                "reason": "needs_board_play_scope",
                "message": (
                    "Reconnect your Lichess account once to let ChessGuru make "
                    "your moves. Nothing else changes."
                ),
            },
        )
    return token


@router.get("/state")
async def live_state(user: User = Depends(get_current_user)):
    """The board, as it stands. Polled by the client while playing.

    Returns `playing: false` with no game rather than a 404, because "no game"
    is the normal resting state of this surface, not an error.
    """
    game = play.current_game(user.user_id)
    seek = play.current_seek(user.user_id)

    if game is None:
        return {
            "playing": False,
            "seeking": seek is not None,
            "seek": {
                "time_control": seek.time_control,
                "rated": seek.rated,
                "created_at": seek.created_at,
            }
            if seek
            else None,
        }

    payload = game.as_payload()
    # The stream dies with the process. The game does not: it is still live on
    # Lichess, so say so honestly instead of pretending the board is current.
    payload["reconnecting"] = (not payload["stream_alive"]) and not payload["finished"]
    return {"playing": True, "seeking": False, "game": payload}


@router.get("/time-controls")
async def time_controls():
    """What we offer, and why nothing faster.

    Not in the guard's allowlist on purpose: it is only needed before a game
    starts, so it must not be reachable during one.
    """
    return {
        "options": list(play.TIME_CONTROLS.keys()),
        "default": play.DEFAULT_TIME_CONTROL,
        "default_rated": play.DEFAULT_RATED,
        "note": (
            "Lichess allows Rapid and slower for games played through other "
            "apps, so these are the three we offer."
        ),
    }


@router.post("/seek")
async def live_seek(
    time_control: str = Body(play.DEFAULT_TIME_CONTROL, embed=True),
    rated: bool = Body(play.DEFAULT_RATED, embed=True),
    user: User = Depends(get_current_user),
):
    """Join the Lichess pool and wait for a human opponent."""
    doc = await _user_doc(user)
    token = _token_or_reconnect(doc)
    try:
        seek = await play.start_seek(db, user.user_id, token, time_control, rated)
    except LichessPlayError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {
        "seeking": True,
        "time_control": seek.time_control,
        "rated": seek.rated,
        "message": "Looking for an opponent on Lichess…",
    }


@router.post("/start")
async def live_start(
    time_control: str = Body(play.DEFAULT_TIME_CONTROL, embed=True),
    rated: bool = Body(play.DEFAULT_RATED, embed=True),
    user: User = Depends(get_current_user),
):
    """Alias for /seek, kept because the allowlist names both.

    The client calls whichever reads better in its own flow; starting a game
    and seeking one are the same act in a pool pairing.
    """
    return await live_seek(time_control=time_control, rated=rated, user=user)


@router.post("/seek/cancel")
async def live_seek_cancel(user: User = Depends(get_current_user)):
    await play.cancel_seek(user.user_id)
    return {"seeking": False}


@router.post("/move")
async def live_move(
    uci: str = Body(..., embed=True),
    user: User = Depends(get_current_user),
):
    """Relay our player's own move to Lichess. Nothing is suggested here."""
    doc = await _user_doc(user)
    token = _token_or_reconnect(doc)
    uci = (uci or "").strip()
    if not (4 <= len(uci) <= 5) or not uci.isalnum():
        raise HTTPException(status_code=400, detail="That is not a move.")
    try:
        await play.play_move(user.user_id, token, uci)
    except LichessPlayError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    game = play.current_game(user.user_id)
    return {"ok": True, "game": game.as_payload() if game else None}


@router.post("/resign")
async def live_resign(user: User = Depends(get_current_user)):
    doc = await _user_doc(user)
    token = _token_or_reconnect(doc)
    try:
        await play.resign(user.user_id, token)
    except LichessPlayError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"ok": True}


@router.post("/abort")
async def live_abort(user: User = Depends(get_current_user)):
    """Only legal in the first moves; Lichess decides, and we relay its answer."""
    doc = await _user_doc(user)
    token = _token_or_reconnect(doc)
    try:
        await play.abort(user.user_id, token)
    except LichessPlayError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"ok": True}


@router.post("/draw")
async def live_draw(
    accept: bool = Body(True, embed=True),
    user: User = Depends(get_current_user),
):
    """Offer or accept a draw (accept=false declines a pending offer)."""
    doc = await _user_doc(user)
    token = _token_or_reconnect(doc)
    try:
        await play.handle_draw(user.user_id, token, accept)
    except LichessPlayError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"ok": True}


@router.get("/review/{lichess_game_id}")
async def live_review(
    lichess_game_id: str,
    user: User = Depends(get_current_user),
):
    """Where did the game we just played end up in our own library?

    This is what makes the sealed panel real. It is deliberately **not** in the
    guard's allowlist, so it cannot be reached while the game is live -- the
    panel stays sealed by the same structural rule as everything else, not by
    the frontend choosing to be polite. After `/finish` the guard is off and
    this answers.

    Returns the id only. The review itself is rendered by the existing
    `/game/:gameId` page, which is the one place that knows how.
    """
    if db is None:
        raise HTTPException(status_code=503, detail="Database not ready")
    game = await db.games.find_one(
        {"user_id": user.user_id, "platform_game_id": lichess_game_id},
        {"_id": 0, "game_id": 1, "is_analyzed": 1},
    )
    if not game:
        # The watcher imports a finished Lichess game within seconds, but
        # "not yet" is a normal answer here, not an error.
        return {"ready": False, "imported": False}
    return {
        "ready": bool(game.get("is_analyzed")),
        "imported": True,
        "game_id": game.get("game_id"),
        "review_url": f"/game/{game.get('game_id')}",
    }


@router.post("/finish")
async def live_finish(user: User = Depends(get_current_user)):
    """Leave the finished game and hand the player back to the rest of the app.

    This is what releases the guard from the client's side. It refuses while the
    game is still playable, because that is the one request that would let
    somebody open an evaluation mid-game: resign or finish first.
    """
    game = play.current_game(user.user_id)
    if game and not game.finished:
        raise HTTPException(
            status_code=409,
            detail=(
                "Your game is still live on Lichess. Finish or resign it first — "
                "your review opens the moment it ends."
            ),
        )
    game_id: Optional[str] = game.game_id if game else None
    await play.forget(db, user.user_id)
    return {"ok": True, "finished_game_id": game_id}
