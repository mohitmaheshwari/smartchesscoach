"""Who was the better player in the game he just finished.

Everything the product knows about a game today comes from one side of the
board: `move_evaluations` holds his moves and nobody has ever run the engine
over his opponent's. Measured on one account, that is 21,827 opponent
half-moves stored in full in the PGNs and zero of them evaluated.

That absence is why the home page could only ever say what he did wrong. It
could not say whether he was the better player, whether the opponent handed
him the game, or whether the board or the clock decided it -- and on his
lichess record the biggest swing in a game is more often the opponent's
mistake than his.

So this evaluates both sides of ONE game: the last one he played. Every
position once, from the mover's point of view, which gives the cost of every
move on both sides from a single pass:

    cp_loss(move i) = eval_before(mover) - eval_after(mover)

Cached per game, because the answer for a finished game never changes.
"""
from __future__ import annotations

import asyncio
import io
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, Mapping, Optional

import chess
import chess.pgn

logger = logging.getLogger(__name__)

SCHEMA_VERSION = "both_sides_review.v1"
CACHE_COLLECTION = "game_both_sides"

# Depth 12 is enough to say which of two club players held together better.
# It is NOT the depth to judge one move by; the turning point it reports is a
# pointer to a moment, not a verdict on a move.
DEPTH = 12
# Beyond this the game is decided and differences are noise, so a lost queen
# in a lost position does not swamp the average.
CLAMP = 1500
# A bound on the work one page load can cause.
MAX_PLIES = 160
BLUNDER_CP = 200

_TIME_CONTROL_TAG = re.compile(r'\[TimeControl "([^"]+)"\]')


def _clamp(value: int) -> int:
    return max(-CLAMP, min(CLAMP, value))


def review_both_sides(pgn: str, user_color: str) -> Optional[Dict[str, Any]]:
    """Evaluate every position once and return both players' costs.

    Synchronous and engine-bound: call it through a thread, never on the event
    loop.
    """
    from stockfish_service import StockfishEngine

    try:
        game = chess.pgn.read_game(io.StringIO(str(pgn or "")))
    except Exception:
        return None
    if game is None:
        return None
    moves = list(game.mainline_moves())
    if len(moves) < 10:
        return None
    moves = moves[:MAX_PLIES]
    colour = chess.WHITE if str(user_color) == "white" else chess.BLACK

    evals = []
    with StockfishEngine() as engine:
        board = game.board()
        for move in [None] + moves:
            if move is not None:
                board.push(move)
            if board.is_game_over():
                evals.append(None)
                break
            score, mate = engine.evaluate_position(board, depth=DEPTH)
            if mate is not None:
                evals.append(CLAMP if mate > 0 else -CLAMP)
            else:
                evals.append(_clamp(int(score)))

    his: list = []
    theirs: list = []
    turning: Optional[Dict[str, Any]] = None
    board = game.board()
    for index, move in enumerate(moves):
        if index + 1 >= len(evals) or evals[index] is None or evals[index + 1] is None:
            break
        mover = board.turn
        sign = 1 if mover == chess.WHITE else -1
        loss = max(0, sign * evals[index] - sign * evals[index + 1])
        try:
            san = board.san(move)
        except Exception:
            break
        mine = mover == colour
        (his if mine else theirs).append(loss)
        if turning is None or loss > turning["cost"]:
            turning = {
                "move_number": board.fullmove_number,
                "san": san,
                "whose": "his" if mine else "theirs",
                "fen_before": board.fen(),
                "cost": loss,
                "board_orientation": "white" if colour == chess.WHITE else "black",
            }
        board.push(move)

    if len(his) < 5 or len(theirs) < 5:
        return None
    return {
        "schema_version": SCHEMA_VERSION,
        "depth": DEPTH,
        "his_moves": len(his),
        "their_moves": len(theirs),
        "his_mean_cp": round(sum(his) / len(his), 1),
        "their_mean_cp": round(sum(theirs) / len(theirs), 1),
        "his_blunders": sum(1 for x in his if x >= BLUNDER_CP),
        "their_blunders": sum(1 for x in theirs if x >= BLUNDER_CP),
        "turning_point": turning,
    }


def card_from_review(
    review: Mapping[str, Any],
    *,
    won: bool,
    lost: bool,
    termination: str,
) -> Dict[str, Any]:
    """Turn the two numbers into the one sentence he reads.

    No figure reaches him. The engine numbers justify the sentence; they are
    not the sentence, and a player told "your average loss was 63 centipawns"
    has been given arithmetic rather than coaching.
    """
    sharper = review["his_mean_cp"] < review["their_mean_cp"]
    flagged = lost and str(termination) == "timeout"
    turning = review.get("turning_point") or {}
    theirs = turning.get("whose") == "theirs"

    if sharper and flagged:
        # The rare and expensive one: he earned it and the clock took it.
        state = "clock"
        headline = "You outplayed them. The clock ended it."
        detail = (
            "You were the steadier player here and your flag fell with the "
            "game still yours."
        )
    elif sharper and won:
        state = "sharper"
        headline = "You were the sharper player in that one."
        detail = (
            "They went wrong and you went straight at it."
            if theirs
            else "You kept it together better than they did."
        )
    elif sharper:
        state = "sharper_no_win"
        headline = "You were the steadier player, and it got away."
        detail = "Worth a look at where it turned."
    elif review["his_mean_cp"] == review["their_mean_cp"]:
        state = "even"
        headline = "Hard to separate you two."
        detail = "Neither of you gave much away."
    else:
        state = "outplayed"
        headline = "They held together better than you did."
        detail = (
            "They handed you something early and it did not survive."
            if theirs
            else "They gave you less to work with than you gave them."
        )
    return {
        "state": state,
        "headline": headline,
        "detail": detail,
        "decided_by": "clock" if flagged else "board",
        "turning_point_is_theirs": bool(theirs),
    }


async def last_game_card(db, user_id: str) -> Optional[Dict[str, Any]]:
    """The card for his most recent finished game, computing it once."""
    game = await db.games.find_one(
        {
            "user_id": user_id,
            "played_at_utc": {"$ne": None},
            "platform": {"$ne": "coach"},
            "pgn": {"$nin": [None, ""]},
        },
        {
            "_id": 0,
            "game_id": 1,
            "pgn": 1,
            "user_color": 1,
            "result": 1,
            "termination": 1,
            "platform": 1,
            "played_at_utc": 1,
            "opponent_name": 1,
            "url": 1,
        },
        sort=[("played_at_utc", -1)],
    )
    if not game:
        return None

    cache = getattr(db, CACHE_COLLECTION, None)
    review = None
    if cache is not None:
        cached = await cache.find_one(
            {"game_id": game["game_id"], "schema_version": SCHEMA_VERSION},
            {"_id": 0, "review": 1},
        )
        if cached:
            review = cached.get("review")
    if review is None:
        try:
            review = await asyncio.to_thread(
                review_both_sides, game.get("pgn"), str(game.get("user_color"))
            )
        except Exception:
            logger.exception("both-sides review failed for %s", game.get("game_id"))
            return None
        if review is None:
            return None
        if cache is not None:
            try:
                await cache.update_one(
                    {"game_id": game["game_id"]},
                    {
                        "$set": {
                            "game_id": game["game_id"],
                            "user_id": user_id,
                            "schema_version": SCHEMA_VERSION,
                            "review": review,
                            "computed_at": datetime.now(timezone.utc),
                        }
                    },
                    upsert=True,
                )
            except Exception:
                # A cache that cannot be written must not cost him the card.
                logger.warning("could not cache both-sides review", exc_info=True)

    colour = str(game.get("user_color"))
    result = str(game.get("result") or "")
    won = (result == "1-0" and colour == "white") or (result == "0-1" and colour == "black")
    lost = (result == "1-0" and colour == "black") or (result == "0-1" and colour == "white")
    card = card_from_review(
        review, won=won, lost=lost, termination=str(game.get("termination") or "")
    )
    card.update(
        {
            "schema_version": SCHEMA_VERSION,
            "game_id": game.get("game_id"),
            "game_url": game.get("url"),
            "platform": game.get("platform"),
            "played_at": game.get("played_at_utc"),
            "result": "won" if won else "lost" if lost else "drew",
            "turning_point": review.get("turning_point"),
            # For a reviewer and for tests. The UI does not render these.
            "measured": {
                "his_mean_cp": review["his_mean_cp"],
                "their_mean_cp": review["their_mean_cp"],
                "his_blunders": review["his_blunders"],
                "their_blunders": review["their_blunders"],
                "depth": review["depth"],
                "counted_by": "both sides of the PGN, evaluated here",
            },
        }
    )
    return card
