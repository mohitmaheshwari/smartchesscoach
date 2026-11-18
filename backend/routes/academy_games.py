"""An academy coach opens a student's games (docs/play_any_line_scope.md,
"Coach pages").

GET /api/academy/student/{student_id}/games            the child's recent games
GET /api/academy/student/{student_id}/game/{game_id}   one game, to replay on
                                                        the coach board

Who may read: the academy's owner, its coaches, and site admins -- the same
rule as every other academy read (routes.academy._student_for) -- and only
after the parent has agreed, like every other read of the child's games. The
coach board plays lines through /api/coach/line/*, which accepts the same
rule through `staff_may_read_game` below.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException

from routes.auth import User, get_current_user

router = APIRouter(prefix="/academy", tags=["academy"])

db = None

RECENT_GAMES = 20


def set_db(database):
    global db
    db = database


def _consented(student: Dict[str, Any]) -> bool:
    return (student.get("consent") or {}).get("status") == "given" and bool(student.get("child_user_id"))


async def staff_may_read_game(database, user: User, game_user_id: Optional[str]) -> bool:
    """True when `user` is staff of the academy of the child who owns the game,
    and the parent has agreed. Used by the line board for coach access."""
    if not game_user_id:
        return False
    from services import academy_service as svc
    student = await database[svc.STUDENTS].find_one(
        {"child_user_id": game_user_id, "deleted_at": None},
        {"_id": 0, "academy_id": 1, "consent": 1, "child_user_id": 1})
    if not student or not _consented(student):
        return False
    if getattr(user, "role", None) in ("admin", "super_admin"):
        return True
    staff = await database[svc.STAFF].find_one(
        {"academy_id": student["academy_id"], "user_id": user.user_id}, {"_id": 1})
    return staff is not None


@router.get("/student/{student_id}/games")
async def student_games(student_id: str, user: User = Depends(get_current_user)):
    from routes.academy import _student_for
    from services.game_outcome import user_outcome

    student = await _student_for(user, student_id)
    if not _consented(student):
        return {"enabled": False, "reason": "consent", "games": []}
    rows = await db.games.find(
        {"user_id": student["child_user_id"]},
        {"_id": 0, "game_id": 1, "result": 1, "user_color": 1, "played_at_utc": 1,
         "opponent_name": 1, "opponent_rating": 1, "is_analyzed": 1, "platform": 1},
    ).sort("played_at_utc", -1).limit(RECENT_GAMES).to_list(RECENT_GAMES)
    games = []
    for g in rows:
        played = g.get("played_at_utc")
        games.append({
            "game_id": g["game_id"],
            "outcome": user_outcome(g),
            "user_color": g.get("user_color"),
            "opponent_name": g.get("opponent_name"),
            "played_at": played.isoformat() if hasattr(played, "isoformat") else None,
        })
    return {"enabled": True, "games": games}


@router.get("/student/{student_id}/game/{game_id}")
async def student_game(student_id: str, game_id: str, user: User = Depends(get_current_user)):
    from routes.academy import _student_for

    student = await _student_for(user, student_id)
    if not _consented(student):
        raise HTTPException(403, "The parent has not agreed yet.")
    game = await db.games.find_one(
        {"game_id": game_id, "user_id": student["child_user_id"]},
        {"_id": 0, "game_id": 1, "pgn": 1, "user_color": 1, "opponent_name": 1, "result": 1})
    if not game or not game.get("pgn"):
        raise HTTPException(404, "Game not found")
    return {
        "game_id": game["game_id"],
        "pgn": game["pgn"],
        "user_color": game.get("user_color") or "white",
        "opponent_name": game.get("opponent_name"),
        "student_name": student.get("display_name"),
    }
