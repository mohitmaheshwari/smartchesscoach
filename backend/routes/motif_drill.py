"""The pin and skewer drill: serve positions, take a move, grade it.

docs/pin_skewer_drill_scope.md.

THE ANSWER IS NEVER SENT TO THE CLIENT. Positions go out with the question and
nothing else; the answer is looked up again here at submit time. Same rule as
the calculation test, for the same reason -- a drill whose answer is in the
payload trains nothing.
"""
from __future__ import annotations

import random
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Depends, HTTPException

from routes.auth import User, get_current_user
from services.motif_drill_service import (
    MOTIFS, drill_supply, get_drill_positions, get_themed_positions, grade,
    grade_themed,
)

router = APIRouter()

# Injected by server.py at startup, the same way every other router here gets
# its handle. There is no `db` module to import from.
db = None


def set_db(database):
    global db
    db = database


@router.get("/training/motif-drill/{motif}")
async def positions(motif: str, count: int = 10,
                    user: User = Depends(get_current_user)) -> Dict[str, Any]:
    """Drill positions for one motif. His own games first, then community,
    then Lichess."""
    if str(motif).lower() not in MOTIFS:
        raise HTTPException(status_code=404, detail="No drill for that motif.")
    count = max(1, min(int(count or 1), 20))
    result = await get_drill_positions(db, user.user_id, motif, limit=count)
    if not result.get("ok"):
        raise HTTPException(status_code=404, detail="No drill for that motif.")

    # Shuffled per position so the expected reason never sits first on screen.
    # The spec stores it first, and that order must not reach the player.
    rng = random.Random()
    for position in result["positions"]:
        options = list(position.get("reason_options") or ())
        rng.shuffle(options)
        position["reason_options"] = options
    return result


@router.post("/training/motif-drill/attempt")
async def attempt(payload: Dict[str, Any] = Body(...),
                  user: User = Depends(get_current_user)) -> Dict[str, Any]:
    """Grade one move. The answer is revealed only in this response."""
    position_id = str(payload.get("position_id") or "")
    move_uci = str(payload.get("move_uci") or "")
    reason_id: Optional[str] = payload.get("reason_id") or None
    if not position_id or not move_uci:
        raise HTTPException(status_code=400,
                            detail="position_id and move_uci are required.")
    result = await grade(db, user.user_id, position_id, move_uci, reason_id)
    if not result.get("ok"):
        raise HTTPException(status_code=400,
                            detail="That position could not be graded.")
    return result


@router.get("/training/motif-drill-supply")
async def supply(user: User = Depends(get_current_user)) -> Dict[str, Any]:
    """How many tagged positions exist. For the operator; no player sees this."""
    return {"ok": True, "supply": await drill_supply(db)}


@router.get("/training/theme/{topic}")
async def themed_positions(topic: str, count: int = 10,
                           user: User = Depends(get_current_user)) -> Dict[str, Any]:
    """Practice for a topic our own games cannot prove.

    docs/home_session_scope.md. `king_safety` has 151 community puzzles and 341
    coach positions and not one passes verification -- there is no king-safety
    prover and none of those positions involve mate. These come from Lichess,
    where the proof already exists, at the player's own level.
    """
    count = max(1, min(int(count or 1), 20))
    result = await get_themed_positions(db, user.user_id, topic, limit=count)
    if not result.get("ok"):
        raise HTTPException(status_code=404, detail="No practice for that topic.")

    rng = random.Random()
    for position in result["positions"]:
        options = list(position.get("reason_options") or ())
        rng.shuffle(options)
        position["reason_options"] = options
    return result


@router.post("/training/theme/attempt")
async def themed_attempt(payload: Dict[str, Any] = Body(...),
                         user: User = Depends(get_current_user)) -> Dict[str, Any]:
    """Grade one themed attempt. The answer is revealed only here."""
    position_id = str(payload.get("position_id") or "")
    move_uci = str(payload.get("move_uci") or "")
    if not position_id or not move_uci:
        raise HTTPException(status_code=400,
                            detail="position_id and move_uci are required.")
    result = await grade_themed(db, user.user_id, position_id, move_uci,
                                payload.get("reason_id") or None)
    if not result.get("ok"):
        raise HTTPException(status_code=400,
                            detail="That position could not be graded.")
    return result
