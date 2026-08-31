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
    apply_diagnosis_to_training,
    diagnostic_supersedes_after,
    # V2 (curated diagnostic_pool + consequence grading)
    CONCEPT_PRIORITY,
    CONCEPT_LABEL,
    TIER_RATING,
    VERDICT_SYMBOL,
    DiagnosticGrader,
    DIAGNOSTIC_GRADE_VERSION,
    UnverifiedDiagnosticMove,
    next_tier,
    concept_done,
    concept_level,
    apply_diagnosis_v2_to_training,
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
# V2 helpers — curated diagnostic_pool, staircase tiers, consequence
# grading. V2 activates when the offline-curated pool exists
# (scripts/build_diagnostic_pool.py); otherwise the legacy 20-puzzle
# community_puzzles flow below still runs.
# ─────────────────────────────────────────────────────────────────────

V2_POOL_MIN = 20  # pool docs required before we trust the v2 flow

_grader = DiagnosticGrader()

_TIER_FALLBACK = {
    "low": ["low", "mid", "high"],
    "mid": ["mid", "high", "low"],
    "high": ["high", "mid", "low"],
}


async def _v2_pool_ready() -> bool:
    try:
        return await db.diagnostic_pool.count_documents({
            "pool_version": 2,
            "grade_version": DIAGNOSTIC_GRADE_VERSION,
            "grade_fingerprint": {"$exists": True},
            "step_grades.0": {"$exists": True},
        }) >= V2_POOL_MIN
    except Exception:
        return False


async def _v2_pick_puzzle(concept: str, tier: str, used_ids: List[str]) -> Optional[Dict[str, Any]]:
    """Pick an unused pool puzzle for (concept, tier). Prefers the exact
    tier (primary before reserve), then falls back to adjacent tiers."""
    for t in _TIER_FALLBACK.get(tier, ["mid", "high", "low"]):
        for reserve in (False, True):
            doc = await db.diagnostic_pool.find_one(
                {
                    "concept": concept,
                    "tier": t,
                    "reserve": reserve,
                    "puzzle_id": {"$nin": used_ids or []},
                },
                {"_id": 0},
            )
            if doc:
                return doc
    return None


def _v2_n_user_moves(pool_doc: Dict[str, Any]) -> int:
    return (len(pool_doc.get("moves") or []) + 1) // 2


def _v2_is_multi_move(pool_doc: Dict[str, Any]) -> bool:
    return pool_doc.get("concept") == "calculation" and _v2_n_user_moves(pool_doc) > 1


def _v2_puzzle_payload(pool_doc: Dict[str, Any], *, fen: Optional[str] = None,
                       step: int = 0) -> Dict[str, Any]:
    """Client-safe puzzle view — no solution, no multipv, no rating."""
    fen = fen or pool_doc["fen"]
    try:
        side = "white" if chess.Board(fen).turn == chess.WHITE else "black"
    except Exception:
        side = "white"
    multi = _v2_is_multi_move(pool_doc)
    return {
        "puzzle_id": pool_doc["puzzle_id"],
        "concept": pool_doc["concept"],
        "concept_label": CONCEPT_LABEL.get(pool_doc["concept"], pool_doc["concept"]),
        "fen": fen,
        "side_to_move": side,
        "multi_move": multi,
        "total_steps": _v2_n_user_moves(pool_doc) if multi else 1,
        "step": step + 1,
    }


def _v2_overall_verdict(step_verdicts: List[str]) -> str:
    """Aggregate a multi-move walk: any MISSING → MISSING, else any
    PARTIAL → PARTIAL, else UNDERSTOOD."""
    if "MISSING" in step_verdicts:
        return "MISSING"
    if "PARTIAL" in step_verdicts:
        return "PARTIAL"
    return "UNDERSTOOD"


async def _v2_start_session(user_id: str) -> Dict[str, Any]:
    """Create a fresh v2 session on the first concept at the mid tier."""
    concept = CONCEPT_PRIORITY[0]
    first = await _v2_pick_puzzle(concept, "mid", [])
    if not first:
        return {"status": "no_pool"}

    now = datetime.now(timezone.utc).isoformat()
    await db.diagnostic_sessions.insert_one({
        "user_id": user_id,
        "version": 2,
        "status": "in_progress",
        "started_at": now,
        "completed_at": None,
        "concept_order": list(CONCEPT_PRIORITY),
        "concept_index": 0,
        "concept_progress": {},
        "attempts": [],
        "used_puzzle_ids": [first["puzzle_id"]],
        "current": {
            "puzzle_id": first["puzzle_id"],
            "concept": concept,
            "tier": first["tier"],
            "move_idx": 0,
            "fen_current": first["fen"],
            "step_verdicts": [],
        },
    })
    return {
        "status": "in_progress",
        "version": 2,
        "current_index": 1,
        "concepts_total": len(CONCEPT_PRIORITY),
        "puzzle": _v2_puzzle_payload(first),
    }


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

    out = {
        "status": session.get("status", "in_progress"),
        "analyzed_game_count": analyzed,
        "attempts_so_far": len(session.get("attempts", [])),
        "total_puzzles": len(session.get("puzzle_ids", [])),
        "started_at": session.get("started_at"),
        "completed_at": session.get("completed_at"),
    }
    if session.get("version") == 2:
        progress = session.get("concept_progress", {})
        out["version"] = 2
        out["total_puzzles"] = None  # adaptive length (20-30)
        out["concepts_total"] = len(session.get("concept_order", CONCEPT_PRIORITY))
        out["concepts_completed"] = sum(
            1 for p in progress.values() if p.get("done")
        )
    return out


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

    # V2 resume: hand back the current puzzle mid-session.
    if existing and existing.get("version") == 2:
        cur = existing.get("current") or {}
        pool_doc = await db.diagnostic_pool.find_one(
            {"puzzle_id": cur.get("puzzle_id")}, {"_id": 0}
        )
        if pool_doc:
            return {
                "status": "in_progress",
                "version": 2,
                "current_index": len(existing.get("attempts", [])) + 1,
                "concepts_total": len(existing.get("concept_order", CONCEPT_PRIORITY)),
                "puzzle": _v2_puzzle_payload(
                    pool_doc,
                    fen=cur.get("fen_current"),
                    step=cur.get("move_idx", 0),
                ),
            }
        # Pool doc vanished (pool rebuilt mid-session) — abandon and restart.
        await db.diagnostic_sessions.update_one(
            {"user_id": user.user_id, "status": "in_progress"},
            {"$set": {"status": "abandoned"}},
        )
        existing = None

    # V2 fresh start whenever the curated pool is ready.
    if not existing and await _v2_pool_ready():
        started = await _v2_start_session(user.user_id)
        if started.get("status") == "in_progress":
            return started
        # pool unusable after all — fall through to legacy below

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


async def _v2_record_attempt(user_id: str, session: Dict[str, Any], req: AttemptRequest) -> Dict[str, Any]:
    """V2 attempt: consequence-grade the move, walk multi-move lines,
    apply the consistency gate + tier staircase, and either serve the
    next puzzle or close the session with a diagnosis."""
    cur = session.get("current") or {}
    if req.puzzle_id != cur.get("puzzle_id"):
        raise HTTPException(
            status_code=400,
            detail=f"Puzzle mismatch. Expected {cur.get('puzzle_id')}, got {req.puzzle_id}.",
        )
    puzzle = await db.diagnostic_pool.find_one(
        {"puzzle_id": req.puzzle_id}, {"_id": 0}
    )
    if not puzzle:
        raise HTTPException(status_code=404, detail="Puzzle not found in pool.")

    concept: str = cur.get("concept") or puzzle["concept"]
    tier: str = cur.get("tier") or puzzle["tier"]
    move_idx: int = cur.get("move_idx", 0)
    fen_current: str = cur.get("fen_current") or puzzle["fen"]
    step_verdicts: List[str] = list(cur.get("step_verdicts") or [])
    moves: List[str] = puzzle.get("moves") or []
    n_user_moves = _v2_n_user_moves(puzzle)
    is_multi = _v2_is_multi_move(puzzle)
    solution_uci = moves[move_idx * 2] if move_idx * 2 < len(moves) else moves[0]

    try:
        graded = _grader._grade_move_consequence(
            req.user_move_san,
            puzzle,
            fen_current,
            solution_uci,
        )
    except UnverifiedDiagnosticMove as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    step_verdicts.append(graded["verdict"])

    # ── multi-move walk (calculation): continue the line only while the
    # user is EXACTLY on the solution — an equivalent-but-different move
    # still counts, but the stored line no longer applies, so we stop.
    more_steps = (move_idx + 1) < n_user_moves
    if is_multi and more_steps and graded["verdict"] == "UNDERSTOOD" and graded["is_exact"]:
        board = chess.Board(fen_current)
        board.push(chess.Move.from_uci(moves[move_idx * 2]))  # user's (solution) move
        opp_reply_san = None
        opp_idx = move_idx * 2 + 1
        if opp_idx < len(moves):
            opp_mv = chess.Move.from_uci(moves[opp_idx])
            opp_reply_san = board.san(opp_mv)
            board.push(opp_mv)
        new_fen = board.fen()
        await db.diagnostic_sessions.update_one(
            {"user_id": user_id, "status": "in_progress"},
            {"$set": {
                "current.move_idx": move_idx + 1,
                "current.fen_current": new_fen,
                "current.step_verdicts": step_verdicts,
            }},
        )
        return {
            "status": "in_progress",
            "puzzle_number": len(session.get("attempts", [])) + 1,
            "concept": concept,
            "verdict": None,  # puzzle not finished yet
            "step_verdict": graded["verdict"],
            "explanation": graded["explanation"],
            "cp_loss": graded["cp_loss"],
            "multi_move": {
                "step": move_idx + 2,
                "total_steps": n_user_moves,
                "opponent_reply_san": opp_reply_san,
                "fen": new_fen,
            },
            "adaptive_triggered": False,
            "puzzle": _v2_puzzle_payload(puzzle, fen=new_fen, step=move_idx + 1),
        }

    # ── puzzle finished: aggregate, record, staircase, gate ──────────
    verdict = _v2_overall_verdict(step_verdicts)
    attempt_doc = {
        "puzzle_id": puzzle["puzzle_id"],
        "concept": concept,
        "tier": tier,
        "puzzle_rating": puzzle.get("puzzle_rating"),
        "user_move_san": graded["user_move_san"],
        "solution_san": graded["solution_san"],
        "verdict": verdict,
        "step_verdicts": step_verdicts if is_multi else None,
        "cp_loss": graded["cp_loss"],
        "explanation": graded["explanation"],
        "attempted_at": datetime.now(timezone.utc).isoformat(),
    }

    progress = session.get("concept_progress", {})
    prog = progress.get(concept) or {"verdicts": [], "tiers": [], "tier_current": "mid", "done": False}
    prog["verdicts"] = list(prog.get("verdicts", [])) + [verdict]
    prog["tiers"] = list(prog.get("tiers", [])) + [tier]
    prog["tier_current"] = next_tier(tier, verdict)
    done, adaptive = concept_done(prog["verdicts"])
    prog["done"] = done
    if done:
        prog["level"] = concept_level(prog["verdicts"])
    progress[concept] = prog

    concept_index = session.get("concept_index", 0)
    concept_order = session.get("concept_order", list(CONCEPT_PRIORITY))
    used_ids = list(session.get("used_puzzle_ids", []))

    # Pick what comes next: adaptive/staircase puzzle in this concept,
    # or the next concept's opener at mid tier.
    next_puzzle = None
    next_concept = concept
    next_tier_name = prog["tier_current"]
    if not done:
        next_puzzle = await _v2_pick_puzzle(concept, next_tier_name, used_ids)
        if not next_puzzle:
            # Pool exhausted for this concept — close it with what we have.
            prog["done"] = True
            prog["level"] = concept_level(prog["verdicts"])
            done, adaptive = True, False
    if done and not next_puzzle:
        while concept_index + 1 < len(concept_order) and not next_puzzle:
            concept_index += 1
            next_concept = concept_order[concept_index]
            next_tier_name = "mid"
            next_puzzle = await _v2_pick_puzzle(next_concept, "mid", used_ids)

    base_update = {
        "concept_progress": progress,
        "concept_index": concept_index,
        # Raw fact, not an interpretation (2026-08-05 residency review):
        # a bare timestamp of the last recorded attempt. Dormancy itself
        # is derived from this at reporting time with whatever cutoff is
        # current -- never stored as a status, so changing the cutoff
        # later costs nothing and loses no information.
        "last_activity_at": datetime.now(timezone.utc).isoformat(),
    }

    # ── session complete ─────────────────────────────────────────────
    if not next_puzzle:
        await db.diagnostic_sessions.update_one(
            {"user_id": user_id, "status": "in_progress"},
            {"$push": {"attempts": attempt_doc}, "$set": base_update},
        )
        final_session = await db.diagnostic_sessions.find_one(
            {"user_id": user_id, "status": "in_progress"}, {"_id": 0}
        )
        diagnosis = await apply_diagnosis_v2_to_training(db, user_id, final_session)
        await db.diagnostic_sessions.update_one(
            {"user_id": user_id, "status": "in_progress"},
            {"$set": {
                "status": "complete",
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "diagnosis": diagnosis,
            }},
        )
        return {
            "status": "complete",
            "puzzle_number": len(session.get("attempts", [])) + 1,
            "concept": concept,
            "verdict": verdict,
            "explanation": graded["explanation"],
            "cp_loss": graded["cp_loss"],
            "best_move_san": graded["solution_san"],
            "concept_progress": {
                concept: prog_symbols(prog),
                "tier_after": TIER_RATING.get(prog["tier_current"], 1200),
            },
            "adaptive_triggered": False,
            "diagnosis": diagnosis,
        }

    # ── more puzzles: persist and serve the next one ─────────────────
    used_ids.append(next_puzzle["puzzle_id"])
    base_update.update({
        "used_puzzle_ids": used_ids,
        "current": {
            "puzzle_id": next_puzzle["puzzle_id"],
            "concept": next_concept,
            "tier": next_puzzle["tier"],
            "move_idx": 0,
            "fen_current": next_puzzle["fen"],
            "step_verdicts": [],
        },
    })
    await db.diagnostic_sessions.update_one(
        {"user_id": user_id, "status": "in_progress"},
        {"$push": {"attempts": attempt_doc}, "$set": base_update},
    )
    return {
        "status": "in_progress",
        "puzzle_number": len(session.get("attempts", [])) + 1,
        "concept": concept,
        "verdict": verdict,
        "explanation": graded["explanation"],
        "cp_loss": graded["cp_loss"],
        "best_move_san": graded["solution_san"],
        "concept_progress": {
            concept: prog_symbols(prog),
            "tier_after": TIER_RATING.get(prog["tier_current"], 1200),
        },
        "adaptive_triggered": adaptive,
        "current_index": len(session.get("attempts", [])) + 2,
        "puzzle": _v2_puzzle_payload(next_puzzle),
    }


def prog_symbols(prog: Dict[str, Any]) -> List[str]:
    return [VERDICT_SYMBOL.get(v, "?") for v in prog.get("verdicts", [])]


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

    if session.get("version") == 2:
        return await _v2_record_attempt(user.user_id, session, req)

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

    from services.verified_puzzle_runtime import (
        grade_resolved_puzzle,
        resolve_verified_puzzle,
    )

    puzzle = await resolve_verified_puzzle(
        db,
        req.puzzle_id,
        user_id=user.user_id,
    )
    if not puzzle:
        raise HTTPException(
            status_code=409,
            detail="This diagnostic position needs verification before use.",
        )

    try:
        board = chess.Board(puzzle["fen"])
        played = DiagnosticGrader.parse_user_move(board, req.user_move_san)
        if played is None:
            raise ValueError("illegal move")
    except (KeyError, ValueError):
        raise HTTPException(status_code=400, detail="That move is not legal here.")
    graded = grade_resolved_puzzle(puzzle, played.uci())
    if graded.get("quality") == "invalid":
        raise HTTPException(status_code=409, detail=graded.get("feedback"))
    is_correct = bool(graded.get("correct"))
    attempt_doc = {
        "puzzle_id": req.puzzle_id,
        "issue_type": puzzle.get("issue_type"),
        "difficulty": puzzle.get("difficulty"),
        "user_move_san": req.user_move_san,
        "best_move_san": graded.get("best_move_san"),
        "is_correct": is_correct,
        "attempted_at": datetime.now(timezone.utc).isoformat(),
    }

    await db.diagnostic_sessions.update_one(
        {"user_id": user.user_id, "status": "in_progress"},
        {"$push": {"attempts": attempt_doc}, "$set": {"last_activity_at": attempt_doc["attempted_at"]}},
    )

    # Done?
    if attempts_so_far + 1 >= len(puzzle_ids):
        # Reload to get the full attempts list including the one we just
        # pushed, then score and persist the diagnosis.
        session = await db.diagnostic_sessions.find_one(
            {"user_id": user.user_id, "status": "in_progress"},
            {"_id": 0},
        )
        # Score AND feed the result into the same weakness pipeline game
        # analysis uses, so the cold-start user's training/home personalize.
        diagnosis = await apply_diagnosis_to_training(
            db, user.user_id, session.get("attempts", [])
        )
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
            "best_move_san": graded.get("best_move_san"),
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
        "best_move_san": graded.get("best_move_san"),
        "current_index": attempts_so_far + 2,
        "total": len(puzzle_ids),
        "puzzle": _strip_puzzle_solution(next_puzzle) if next_puzzle else None,
    }


@router.post("/exit")
async def exit_diagnostic(user: User = Depends(get_current_user)):
    """User left the diagnostic early. Score whatever they solved and STILL
    build their profile from it (partial run nudges the profile, per scope)."""
    session = await db.diagnostic_sessions.find_one(
        {"user_id": user.user_id, "status": "in_progress"}, {"_id": 0},
    )
    if not session:
        raise HTTPException(status_code=404, detail="No diagnostic in progress.")
    if session.get("version") == 2:
        diagnosis = await apply_diagnosis_v2_to_training(db, user.user_id, session)
    else:
        diagnosis = await apply_diagnosis_to_training(
            db, user.user_id, session.get("attempts", [])
        )
    await db.diagnostic_sessions.update_one(
        {"user_id": user.user_id, "status": "in_progress"},
        {"$set": {
            "status": "complete",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "diagnosis": diagnosis,
            "exited_early": True,
        }},
    )
    return {"status": "complete", "diagnosis": diagnosis, "exited_early": True}


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
    total = (
        len(session.get("attempts", []))
        if session.get("version") == 2
        else len(session.get("puzzle_ids", []))
    )
    return {
        "diagnosis": session.get("diagnosis"),
        "completed_at": session.get("completed_at"),
        "total_puzzles": total,
        "version": session.get("version", 1),
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
