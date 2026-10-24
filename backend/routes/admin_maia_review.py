"""See the move Stockfish wants beside the move a human would actually play.

Mohit, after watching a card draw Stockfish's Kh2 on a position where a 1200
takes the knight: "can you build a page on chessguru, so I can see those
games and then what stockfish suggest and what maia2 suggest, you know so we
can build this feature well?"

Read-only, and it serves a collection that `scripts/maia_likely_moves_local.py`
fills from Mohit's own machine. Nothing here runs Maia2: the model needs
~800 MB resident and the box is 0.8 GB short of comfortable until mongodb is
capped and matrimonial moves off, so the page shows what the local run has
already written.

What a row means, and it is worth being exact because the whole value is in
the gap between two numbers:

    played_san          what was actually played. Its cp_loss is under 50 --
                        these are positions where NOTHING WENT WRONG.
    best_move_san       Stockfish's move, from the stored analysis.
    likely_move_san     what Maia2 says a player of THIS rating would choose,
                        with the probability it gives, and what Stockfish says
                        that move costs.

So a row is a position the player walked past. Measured over 50 games: 1.4 a
game, the likely move played by a median 39% of peers (max 89%) and costing a
median 178 cp.

Maia2 itself was validated before any of this: over 92 games and 5,871 plies
it names the move actually played 52.2% of the time, in both rating bands
present. One move in two out of about thirty legal ones.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import chess
from fastapi import APIRouter, Depends, Query

from routes.admin import require_admin
from routes.auth import User

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Admin"])
db = None

COLLECTION = "maia_likely_moves"


def set_db(database):
    global db
    db = database


def _uci(fen: str, san: Optional[str]) -> Optional[str]:
    """SAN to a from/to pair the board can draw.

    Returns None rather than raising: a row whose move will not parse should
    lose its arrow, not take the page down.
    """
    if not san:
        return None
    try:
        board = chess.Board(fen)
        move = board.parse_san(str(san))
        return move.uci()
    except Exception:
        return None


@router.get("/admin/maia-review/results")
async def maia_results(user: User = Depends(require_admin)) -> Dict[str, Any]:
    """The shape of what the local run has produced so far."""
    coll = db[COLLECTION]
    total = await coll.count_documents({})
    if not total:
        return {"total": 0, "games": 0, "users": [], "buckets": {}}

    rows = await coll.find(
        {}, {"_id": 0, "likely_move_pct": 1, "likely_move_cp_loss": 1,
             "game_id": 1, "source_user_id": 1}).to_list(20000)
    pcts = sorted(float(r.get("likely_move_pct") or 0) for r in rows)
    cps = sorted(int(r.get("likely_move_cp_loss") or 0) for r in rows)

    def at(values, q):
        return values[min(len(values) - 1, int(len(values) * q))] if values else 0

    # Bucketed by how tempting the move is -- the number that decides whether
    # a position is worth asking about at all.
    buckets = {"80%+": 0, "60-79%": 0, "40-59%": 0, "under 40%": 0}
    for p in pcts:
        if p >= 80:
            buckets["80%+"] += 1
        elif p >= 60:
            buckets["60-79%"] += 1
        elif p >= 40:
            buckets["40-59%"] += 1
        else:
            buckets["under 40%"] += 1

    return {
        "total": total,
        "games": len({r.get("game_id") for r in rows}),
        "users": sorted({r.get("source_user_id") for r in rows if r.get("source_user_id")}),
        "pct_median": at(pcts, 0.5),
        "pct_p90": at(pcts, 0.9),
        "pct_max": pcts[-1] if pcts else 0,
        "cp_median": at(cps, 0.5),
        "cp_p90": at(cps, 0.9),
        "buckets": buckets,
    }


@router.get("/admin/maia-review/positions")
async def maia_positions(
    user: User = Depends(require_admin),
    limit: int = Query(40, ge=1, le=200),
    skip: int = Query(0, ge=0),
    sort: str = Query("pct", pattern="^(pct|cp|recent)$"),
    min_pct: float = Query(0.0, ge=0, le=100),
) -> Dict[str, Any]:
    """The positions themselves, newest or most tempting first.

    Sorted by how LIKELY the human move is by default, not by what it costs.
    A move 89% of players make for 137 cp teaches more than one 22% make for
    494 cp, because almost nobody meets the second.
    """
    coll = db[COLLECTION]
    query: Dict[str, Any] = {}
    if min_pct:
        query["likely_move_pct"] = {"$gte": min_pct}

    order = {"pct": [("likely_move_pct", -1)],
             "cp": [("likely_move_cp_loss", -1)],
             "recent": [("created_at", -1)]}[sort]

    rows = await coll.find(query, {"_id": 0}).sort(order).skip(skip).limit(
        limit).to_list(limit)

    # The game each position came from, so the page can link to the review.
    game_ids = sorted({r.get("game_id") for r in rows if r.get("game_id")})
    games: Dict[str, Dict[str, Any]] = {}
    if game_ids:
        async for g in db.games.find(
                {"game_id": {"$in": game_ids}},
                {"_id": 0, "game_id": 1, "white": 1, "black": 1,
                 "platform": 1, "played_at": 1, "result": 1,
                 "white_rating": 1, "black_rating": 1}):
            games[g["game_id"]] = g

    out: List[Dict[str, Any]] = []
    for r in rows:
        fen = r.get("fen") or ""
        side = "white"
        try:
            side = "white" if chess.Board(fen).turn == chess.WHITE else "black"
        except Exception:
            pass
        game = games.get(r.get("game_id")) or {}
        out.append({
            **r,
            "side_to_move": side,
            "played_uci": _uci(fen, r.get("played_san")),
            "best_uci": _uci(fen, r.get("best_move_san")),
            # The likely move already has a stored uci; recompute only if the
            # run did not write one.
            "likely_uci": r.get("likely_move_uci") or _uci(
                fen, r.get("likely_move_san")),
            "game": {
                "platform": game.get("platform"),
                "played_at": str(game.get("played_at") or ""),
                "result": game.get("result"),
                "white": game.get("white"),
                "black": game.get("black"),
            },
        })

    return {"positions": out, "count": len(out),
            "total": await coll.count_documents(query)}
