"""Showing your working: serve a position, take a line, grade it.

docs/calculation_test_scope.md.

THE ANSWER IS NEVER SENT TO THE CLIENT. The position goes out with no line and
no best move, because a test whose answer is in the payload measures nothing.
The sound line is looked up again at submit time from the server's own copy.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException

from routes.auth import User, get_current_user
from services.calculation_test import grade_line, pick_test_positions

router = APIRouter()

# Injected by server.py at startup, the same way every other router here gets
# its handle. There is no `db` module to import from.
db = None


def set_db(database):
    global db
    db = database

ATTEMPTS = "calculation_test_attempts"
# Three while the test is being validated. The scope's second check is that it
# agrees with itself across positions, and that needs more than one. Production
# should ask for one and offer a second only when the first is ambiguous --
# with no clock these take real thinking and three will be abandoned.
VALIDATION_COUNT = 3


@router.get("/calculation-test/positions")
async def get_positions(count: int = VALIDATION_COUNT,
                        user: User = Depends(get_current_user)) -> Dict[str, Any]:
    """Positions from this player's own games, with no answers attached."""
    from stockfish_service import StockfishEngine

    count = max(1, min(int(count or 1), 5))
    try:
        with StockfishEngine() as wrapper:
            picked = await pick_test_positions(db, user.user_id, count=count,
                                               engine=wrapper.engine)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Engine unavailable: %s" % exc)

    if not picked:
        # Saying so is the honest answer. A player with no position worth being
        # tested on should not be handed a made-up one.
        return {"positions": [], "reason": "no position from your games needs "
                                           "working out yet"}

    return {"positions": [{
        "position_id": "%s:%s" % (item["game_id"], item["move_number"]),
        "fen": item["fen"],
        "game_id": item["game_id"],
        "move_number": item["move_number"],
        "you_played": item.get("you_played"),
        # How deep it goes is told, because stopping short and going wrong are
        # different failures and a player cannot avoid the first without
        # knowing how far to look.
        "needs_half_moves": item.get("required_depth"),
    } for item in picked]}


@router.post("/calculation-test/submit")
async def submit_line(payload: Dict[str, Any] = Body(...),
                      user: User = Depends(get_current_user)) -> Dict[str, Any]:
    """Grade a line the player worked out, and keep it."""
    from stockfish_service import StockfishEngine

    position_id = str(payload.get("position_id") or "")
    moves: List[str] = [str(m) for m in (payload.get("moves") or []) if str(m).strip()]
    verdict: Optional[str] = payload.get("verdict")
    if not position_id or ":" not in position_id:
        raise HTTPException(status_code=400, detail="position_id is required")
    if not moves:
        raise HTTPException(status_code=400, detail="enter at least one move")

    game_id, _, move_number = position_id.rpartition(":")
    doc = await db.game_analyses.find_one(
        {"game_id": game_id},
        {"_id": 0, "stockfish_analysis.move_evaluations": 1})
    if not doc:
        raise HTTPException(status_code=404, detail="that position is not available")

    fen = None
    for mv in (doc.get("stockfish_analysis") or {}).get("move_evaluations") or []:
        if str(mv.get("move_number")) == move_number and not mv.get("is_opponent_move"):
            fen = mv.get("fen_before")
            break
    if not fen:
        raise HTTPException(status_code=404, detail="that position is not available")

    try:
        with StockfishEngine() as wrapper:
            graded = grade_line(fen, moves, wrapper.engine, verdict=verdict)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Engine unavailable: %s" % exc)

    # Save after EVERY position rather than at the end of a set. If someone is
    # asked for three and does one, the one is kept.
    await db[ATTEMPTS].insert_one({
        "user_id": user.user_id,
        "position_id": position_id,
        "game_id": game_id,
        "move_number": move_number,
        "fen": fen,
        "submitted": moves,
        "verdict": verdict,
        "found_the_idea": graded.get("found_the_idea"),
        "sound_through": graded.get("sound_through"),
        "required_depth": graded.get("required_depth"),
        "stopped_early": graded.get("stopped_early"),
        "judged_the_end": graded.get("judged_the_end"),
        "created_at": datetime.now(timezone.utc),
    })
    return graded


@router.get("/calculation-test/mine")
async def my_attempts(user: User = Depends(get_current_user)) -> Dict[str, Any]:
    """What this player has done, for the validation checks and for them.

    No sentence is written here yet. The scope requires three measurements to
    pass before anything is claimed from these, and inventing the copy first is
    how a number becomes a story nobody checked.
    """
    rows = await db[ATTEMPTS].find(
        {"user_id": user.user_id}, {"_id": 0}
    ).sort("created_at", -1).to_list(50)
    return {"attempts": rows, "count": len(rows)}
