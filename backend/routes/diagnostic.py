"""
Diagnostic onboarding routes — 20-puzzle warm-up that doubles as a real
diagnosis when the user has no analyzed games OR while their imported
games are still being analyzed.

Spec: memory/project_diagnostic_onboarding_20_puzzles.md

Endpoints (all under /api/diagnostic, prefixed by api_router in server.py):
    GET  /diagnostic/status        - in_progress | complete | not_started
    POST /diagnostic/start         - select 20 puzzles, return puzzle #1
    POST /diagnostic/attempt       - record an attempt, return next puzzle
                                     or final diagnosis
    GET  /diagnostic/result        - full diagnosis (only when complete)
    POST /diagnostic/skip          - abandon the diagnostic without scoring
                                     (user opted out; we'll re-offer later)
"""

import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

import chess
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from routes.auth import User, get_current_user
from services.diagnostic_service import (
    select_diagnostic_puzzles,
    score_diagnostic,
    diagnostic_supersedes_after,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/diagnostic", tags=["Diagnostic"])

db = None


def set_db(database):
    global db
    db = database


# ─────────────────────────────────────────────────────────────────────
# Request models
# ─────────────────────────────────────────────────────────────────────


class AttemptRequest(BaseModel):
    puzzle_id: str
    user_move_san: str  # e.g. "Nxd3", "O-O", "e8=Q"


# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────


def _strip_puzzle_solution(puzzle: Dict[str, Any]) -> Dict[str, Any]:
    """Don't send best_move_san to the client until after the attempt
    is submitted. Returns a copy with the answer removed."""
    return {
        "puzzle_id": puzzle.get("puzzle_id"),
        "fen": puzzle.get("fen"),
        "user_color": puzzle.get("user_color"),
        "issue_type": puzzle.get("issue_type"),
        "difficulty": puzzle.get("difficulty"),
        "opening_name": puzzle.get("opening_name"),
        "move_number": puzzle.get("move_number"),
    }


def _check_move(fen: str, user_move_san: str, best_move_san: str) -> bool:
    """Move-equivalence check. We accept any move that parses to the
    same UCI as the puzzle's best_move_san. Variations in disambiguation
    (Nbd2 vs N1d2) shouldn't fail the user."""
    try:
        board = chess.Board(fen)
        user_uci = board.parse_san(user_move_san).uci()
        best_uci = board.parse_san(best_move_san).uci()
        return user_uci == best_uci
    except Exception:
        return False


async def _user_analyzed_game_count(user_id: str) -> int:
    """How many analyzed games does this user have? Used to decide
    whether the diagnostic should still be offered or whether
    real-game data already supersedes it."""
    return await db.game_analyses.count_documents({"user_id": user_id})


# ─────────────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────────────


@router.get("/status")
async def get_status(user: User = Depends(get_current_user)):
    """Return the user's diagnostic state.

    Status values:
      not_started       - never opened the diagnostic
      in_progress       - has an open session with attempts < 20
      complete          - finished one diagnostic
      superseded        - has 10+ analyzed games; diagnostic skipped
      skipped           - explicitly opted out (re-offer eligible)
    """
    analyzed = await _user_analyzed_game_count(user.user_id)
    if diagnostic_supersedes_after(analyzed):
        return {
            "status": "superseded",
            "analyzed_game_count": analyzed,
            "message": "Real game data is now driving your diagnosis.",
        }

    session = await db.diagnostic_sessions.find_one(
        {"user_id": user.user_id},
        {"_id": 0},
        sort=[("started_at", -1)],
    )
    if not session:
        return {"status": "not_started", "analyzed_game_count": analyzed}

    return {
        "status": session.get("status", "in_progress"),
        "analyzed_game_count": analyzed,
        "attempts_so_far": len(session.get("attempts", [])),
        "total_puzzles": len(session.get("puzzle_ids", [])),
        "started_at": session.get("started_at"),
        "completed_at": session.get("completed_at"),
    }


@router.post("/start")
async def start_diagnostic(user: User = Depends(get_current_user)):
    """Start (or resume) a diagnostic session.

    If the user already has an in_progress session, return the next
    unanswered puzzle from that session instead of creating a new one.
    """
    # Already-complete or superseded users get nothing new from /start
    analyzed = await _user_analyzed_game_count(user.user_id)
    if diagnostic_supersedes_after(analyzed):
        return {"status": "superseded", "message": "Real game data has taken over."}

    existing = await db.diagnostic_sessions.find_one(
        {"user_id": user.user_id, "status": "in_progress"},
        {"_id": 0},
    )
    if existing:
        attempts_so_far = len(existing.get("attempts", []))
        puzzle_ids = existing.get("puzzle_ids", [])
        if attempts_so_far < len(puzzle_ids):
            next_id = puzzle_ids[attempts_so_far]
            puzzle = await db.community_puzzles.find_one(
                {"_id": _to_objid(next_id)},
                {"_id": 0, "fen": 1, "user_color": 1, "issue_type": 1,
                 "difficulty": 1, "opening_name": 1, "move_number": 1},
            )
            if puzzle:
                puzzle["puzzle_id"] = next_id
                return {
                    "status": "in_progress",
                    "current_index": attempts_so_far + 1,
                    "total": len(puzzle_ids),
                    "puzzle": _strip_puzzle_solution(puzzle),
                }

    # No existing in-progress session, or it's broken — start fresh.
    picks = await select_diagnostic_puzzles(db, user.user_id)
    if not picks:
        # Pool too thin to give a meaningful diagnostic. Be honest, don't
        # ship a 5-puzzle quiz pretending to be a diagnosis.
        return {
            "status": "no_pool",
            "message": "We don't have enough puzzles in your range yet. We'll start your "
                       "diagnosis from your real games as they finish analyzing.",
        }

    now = datetime.now(timezone.utc).isoformat()
    puzzle_ids = [p["puzzle_id"] for p in picks]

    # Persist the question set up front so the user can leave and resume
    # without us picking different puzzles each visit.
    await db.diagnostic_sessions.insert_one({
        "user_id": user.user_id,
        "status": "in_progress",
        "started_at": now,
        "completed_at": None,
        "puzzle_ids": puzzle_ids,
        "attempts": [],
    })

    return {
        "status": "in_progress",
        "current_index": 1,
        "total": len(picks),
        "puzzle": _strip_puzzle_solution(picks[0]),
    }


@router.post("/attempt")
async def record_attempt(
    req: AttemptRequest,
    user: User = Depends(get_current_user),
):
    """Record a puzzle attempt. If this was the last puzzle, score the
    full session and return the diagnosis.
    """
    session = await db.diagnostic_sessions.find_one(
        {"user_id": user.user_id, "status": "in_progress"},
        {"_id": 0},
    )
    if not session:
        raise HTTPException(status_code=404, detail="No active diagnostic session.")

    puzzle_ids: List[str] = session.get("puzzle_ids", [])
    attempts_so_far: int = len(session.get("attempts", []))

    if attempts_so_far >= len(puzzle_ids):
        raise HTTPException(status_code=400, detail="Diagnostic already complete.")

    expected_id = puzzle_ids[attempts_so_far]
    if req.puzzle_id != expected_id:
        # Soft-correct: the user must be on the expected puzzle. Reject
        # out-of-order attempts rather than silently scoring them.
        raise HTTPException(
            status_code=400,
            detail=f"Puzzle order mismatch. Expected {expected_id}, got {req.puzzle_id}.",
        )

    puzzle = await db.community_puzzles.find_one(
        {"_id": _to_objid(req.puzzle_id)},
        {"_id": 0, "fen": 1, "best_move_san": 1, "issue_type": 1,
         "difficulty": 1},
    )
    if not puzzle:
        raise HTTPException(status_code=404, detail="Puzzle not found.")

    is_correct = _check_move(
        puzzle["fen"], req.user_move_san, puzzle["best_move_san"]
    )
    attempt_doc = {
        "puzzle_id": req.puzzle_id,
        "issue_type": puzzle.get("issue_type"),
        "difficulty": puzzle.get("difficulty"),
        "user_move_san": req.user_move_san,
        "best_move_san": puzzle["best_move_san"],
        "is_correct": is_correct,
        "attempted_at": datetime.now(timezone.utc).isoformat(),
    }

    await db.diagnostic_sessions.update_one(
        {"user_id": user.user_id, "status": "in_progress"},
        {"$push": {"attempts": attempt_doc}},
    )

    # Done?
    if attempts_so_far + 1 >= len(puzzle_ids):
        # Reload to get the full attempts list including the one we just
        # pushed, then score and persist the diagnosis.
        session = await db.diagnostic_sessions.find_one(
            {"user_id": user.user_id, "status": "in_progress"},
            {"_id": 0},
        )
        diagnosis = score_diagnostic(session.get("attempts", []))
        await db.diagnostic_sessions.update_one(
            {"user_id": user.user_id, "status": "in_progress"},
            {"$set": {
                "status": "complete",
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "diagnosis": diagnosis,
            }},
        )
        return {
            "status": "complete",
            "is_correct": is_correct,
            "best_move_san": puzzle["best_move_san"],
            "diagnosis": diagnosis,
        }

    # More to go: return the next puzzle (without its answer).
    next_id = puzzle_ids[attempts_so_far + 1]
    next_puzzle = await db.community_puzzles.find_one(
        {"_id": _to_objid(next_id)},
        {"_id": 0, "fen": 1, "user_color": 1, "issue_type": 1,
         "difficulty": 1, "opening_name": 1, "move_number": 1},
    )
    if next_puzzle:
        next_puzzle["puzzle_id"] = next_id
    return {
        "status": "in_progress",
        "is_correct": is_correct,
        "best_move_san": puzzle["best_move_san"],
        "current_index": attempts_so_far + 2,
        "total": len(puzzle_ids),
        "puzzle": _strip_puzzle_solution(next_puzzle) if next_puzzle else None,
    }


@router.get("/result")
async def get_result(user: User = Depends(get_current_user)):
    """Fetch the completed diagnosis. 404 if not complete."""
    session = await db.diagnostic_sessions.find_one(
        {"user_id": user.user_id, "status": "complete"},
        {"_id": 0},
        sort=[("completed_at", -1)],
    )
    if not session:
        raise HTTPException(status_code=404, detail="No completed diagnostic.")
    return {
        "diagnosis": session.get("diagnosis"),
        "completed_at": session.get("completed_at"),
        "total_puzzles": len(session.get("puzzle_ids", [])),
    }


@router.post("/skip")
async def skip_diagnostic(user: User = Depends(get_current_user)):
    """User opted out. Mark any in-progress session as skipped so we
    don't reuse the puzzle list; we'll re-offer later if they want."""
    res = await db.diagnostic_sessions.update_one(
        {"user_id": user.user_id, "status": "in_progress"},
        {"$set": {
            "status": "skipped",
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }},
    )
    return {"skipped": res.modified_count > 0}


# ─────────────────────────────────────────────────────────────────────
# Internal: tolerate either ObjectId or string puzzle_id storage
# ─────────────────────────────────────────────────────────────────────


def _to_objid(maybe_id: str):
    """community_puzzles uses ObjectId for _id. Selector returns the
    stringified form; convert back for the find_one query."""
    from bson import ObjectId
    try:
        return ObjectId(maybe_id)
    except Exception:
        # Some older puzzle docs may have string _id values. Fall back.
        return maybe_id
