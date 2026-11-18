"""Play any line on the review board (docs/play_any_line_scope.md).

POST /api/coach/line/move   one student move and the engine's answer, with
                            words from board facts (services/line_board.py).
                            Fast: two engine searches.
POST /api/coach/line/why    the why button's sentence for a student move the
                            first call called a mistake. Slow (seconds), so it
                            is its own call and the reply never waits for it.

A line must start from a position the game reached: the endpoint is a coach
for the player's own games, not a free engine for any position.
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Deque, Dict, List, Optional

import chess
import chess.engine
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from routes.auth import User, get_current_user
from services.access_scope import user_scope_filter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/coach/line", tags=["line-board"])

db = None

# Depth for the reply and the verdict. Set from the 2026-11-18 timing run
# (docs/play_any_line_scope.md, section 8).
LINE_BOARD_DEPTH = int(os.environ.get("LINE_BOARD_DEPTH", "16"))
LINE_BOARD_HASH_MB = int(os.environ.get("LINE_BOARD_HASH_MB", "64"))
# Per-user engine requests per minute, both calls together. The box is shared
# with the website and two analysis workers.
LINE_BOARD_PER_MINUTE = int(os.environ.get("LINE_BOARD_PER_MINUTE", "30"))
# A line longer than this is refused: nobody reads forty moves of words.
MAX_LINE_PLIES = 40

_recent: Dict[str, Deque[float]] = defaultdict(deque)


def set_db(database):
    global db
    db = database


def _allow(user_id: str) -> bool:
    now = time.monotonic()
    q = _recent[user_id]
    while q and now - q[0] > 60:
        q.popleft()
    if len(q) >= LINE_BOARD_PER_MINUTE:
        return False
    q.append(now)
    return True


class ClientEval(BaseModel):
    """Stockfish's answer from the student's browser (section 10 of the scope).

    Scores are centipawns from the side to move; a mate is +-(10000 - n).
    """
    engine: str = Field(default="", max_length=40)
    best: str = Field(max_length=5)                 # best move before the student's move, UCI
    best_cp: int
    second_cp: Optional[int] = None                 # the next-best move's score (MultiPV 2)
    after_cp: Optional[int] = None                  # after the student's move, side to move
    pv_after: List[str] = Field(default_factory=list, max_length=16)  # reply first, UCI
    depth_before: Optional[int] = None
    depth_after: Optional[int] = None


class LineMove(BaseModel):
    game_id: str
    start_fen: str
    moves: List[str] = Field(default_factory=list)
    # None = "Best move here": the engine's best is played as the student's move.
    move: Optional[str] = None
    client_eval: Optional[ClientEval] = None


async def _game_and_rating(user: User, game_id: str):
    fields = {"_id": 0, "game_id": 1, "user_id": 1, "pgn": 1, "user_color": 1, "user_plays_as": 1}
    game = await db.games.find_one({"game_id": game_id, **user_scope_filter(user)}, fields)
    if not game:
        # An academy coach on a student's game, after the parent agreed
        # (routes/academy_games.py). "your" in the words stays the student.
        from routes.academy_games import staff_may_read_game
        other = await db.games.find_one({"game_id": game_id}, fields)
        if other and await staff_may_read_game(db, user, other.get("user_id")):
            game = other
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    rating = None
    try:
        from services.rating_resolver import resolve_coaching_rating
        rating = (await resolve_coaching_rating(db, game.get("user_id") or user.user_id)).get("rating")
    except Exception:                                   # noqa: BLE001
        logger.debug("line board: rating unavailable for %s", game_id, exc_info=True)
    color = (game.get("user_color") or game.get("user_plays_as") or "white").lower()
    return game, rating, (chess.WHITE if color == "white" else chess.BLACK)


def _check_line(game: dict, body: LineMove) -> None:
    from services.line_board import game_positions, position_in_game
    if len(body.moves) > MAX_LINE_PLIES:
        raise HTTPException(status_code=400, detail="Line too long")
    if not position_in_game(body.start_fen, game_positions(game.get("pgn") or "")):
        raise HTTPException(status_code=400, detail="The line must start from a position of this game")


def _engine() -> chess.engine.SimpleEngine:
    from config import STOCKFISH_PATH
    eng = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)
    # threads=1 so the same line gives the same answer twice.
    eng.configure({"Threads": 1, "Hash": LINE_BOARD_HASH_MB})
    return eng


async def _record(user: User, game_id: str, body: LineMove, kind: str, out: dict) -> None:
    try:
        await db.line_board_events.insert_one({
            "user_id": user.user_id, "game_id": game_id, "kind": kind,
            "start_fen": body.start_fen, "moves": list(body.moves), "move": body.move,
            "student": (out.get("student") or {}).get("san") if kind == "move" else None,
            "class": (out.get("student") or {}).get("class") if kind == "move" else None,
            "shown": {
                "student": (out.get("student") or {}).get("text") if kind == "move" else None,
                "reply": (out.get("reply") or {}).get("text") if kind == "move" else None,
                "count": out.get("count_text") if kind == "move" else None,
                "why": out.get("text") if kind == "why" else None,
            },
            "found": out.get("found") if kind == "why" else None,
            "engine": out.get("engine") if kind == "move" else None,
            "at": datetime.now(timezone.utc),
        })
    except Exception:                                   # noqa: BLE001
        logger.debug("line board: event not recorded", exc_info=True)


def _from_browser(body: LineMove, *, user_color, rating, notation) -> dict:
    from services.line_board import ClientAnswers, LineError, replay, step
    ce = body.client_eval
    board, _ = replay(body.start_fen, body.moves)
    if body.move is None:
        try:
            move = chess.Move.from_uci(ce.best)
        except ValueError as exc:
            raise LineError("bad best move from the browser") from exc
        if move not in board.legal_moves:
            raise LineError("the browser's best move is not legal here")
    else:
        try:
            move = board.parse_san(body.move)
        except ValueError as exc:
            raise LineError(f"illegal move: {body.move}") from exc
    after = board.copy()
    after.push(move)
    answers = ClientAnswers(board.fen(), ce.best, ce.best_cp, ce.second_cp,
                            None if after.is_game_over() else after.fen(), ce.pv_after, ce.after_cp)
    out = step(answers, body.start_fen, body.moves, body.move, user_color=user_color,
               rating=rating, depth=0, notation=notation).to_dict()
    out["engine"] = f"browser:{ce.engine}"[:48]
    return out


@router.post("/move")
async def line_move(body: LineMove, user: User = Depends(get_current_user)):
    from services.line_board import LineError, step  # noqa: F401

    game, rating, user_color = await _game_and_rating(user, body.game_id)
    _check_line(game, body)
    if not _allow(user.user_id):
        raise HTTPException(status_code=429, detail="Too many moves at once. Wait a moment.")
    notation = rating is None or int(rating) >= 1000   # player_coach_file: notation off under 1000

    def _run():
        with _engine() as eng:
            return step(eng, body.start_fen, body.moves, body.move, user_color=user_color,
                        rating=rating, depth=LINE_BOARD_DEPTH, notation=notation).to_dict()

    out = None
    if body.client_eval is not None:
        # The browser already searched: words only, no server engine.
        try:
            out = _from_browser(body, user_color=user_color, rating=rating, notation=notation)
        except LineError as exc:
            logger.info("line board: browser eval refused (%s); using the server engine", exc)
            out = None
    try:
        if out is None:
            out = await asyncio.to_thread(_run)
            out["engine"] = "server"
    except LineError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:                                   # noqa: BLE001
        logger.exception("line board move failed for %s", body.game_id)
        raise HTTPException(status_code=503, detail="The engine is busy. Try again.")
    await _record(user, body.game_id, body, "move", out)
    return out


@router.post("/why")
async def line_why(body: LineMove, user: User = Depends(get_current_user)):
    """The why button's own engine and words, for a move off the game line.

    `found: false` is a real answer: the board has already shown the move and
    the reply; nothing is invented to fill the gap.
    """
    from services.line_board import LineError, replay
    from services.why_differential import explain, to_response

    if not body.move:
        raise HTTPException(status_code=400, detail="Which move?")
    game, rating, user_color = await _game_and_rating(user, body.game_id)
    _check_line(game, body)
    if not _allow(user.user_id):
        raise HTTPException(status_code=429, detail="Too many moves at once. Wait a moment.")
    try:
        board, _ = replay(body.start_fen, body.moves)
        board.parse_san(body.move)
    except (LineError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    fen_before = board.fen()
    mover_is_user = board.turn == user_color

    try:
        result = await asyncio.to_thread(explain, fen_before, body.move,
                                         mover_is_user=mover_is_user, rating=rating)
    except Exception:                                   # noqa: BLE001
        logger.exception("line board why failed for %s", body.game_id)
        result = None
    if not result or not result.get("found"):
        out = {"found": False,
               "reason": (result or {}).get("reason") or "engine_error",
               "better_move": (result or {}).get("better_move")}
        await _record(user, body.game_id, body, "why", out)
        return out
    out = to_response(result)
    from routes.coach import _attach_words
    await _attach_words(out, out.get("facts"), rating=rating)
    out["played_san"] = body.move
    out["fen_before"] = fen_before
    await _record(user, body.game_id, body, "why", out)
    return out
