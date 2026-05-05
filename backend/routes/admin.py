"""
Admin Routes
=============

Handles admin dashboard, user management, and feedback queue.

Endpoints:
- GET /admin/overview - Platform overview stats
- GET /admin/users - List all users
- GET /admin/users/{target_user_id} - User detail view
- POST /admin/users - Create a new user (super_admin only)
- PATCH /admin/users/{target_user_id}/role - Change user role (super_admin only)
- POST /feedback/flag - Flag a move's coaching as incorrect
- GET /admin/feedback - List feedback queue
- PATCH /admin/feedback/{feedback_id} - Update feedback status
- GET /admin/feedback/export - Export feedback as JSON
- GET /admin/feedback/download/{filename} - Download exported feedback file
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List, Dict
from datetime import datetime, timezone, timedelta
import os
import uuid
import logging

logger = logging.getLogger(__name__)

# Create router for admin endpoints
router = APIRouter(tags=["Admin"])

# Database reference - will be set by server.py
db = None

def set_db(database):
    """Set the database reference for admin routes"""
    global db
    db = database


# Import User model and get_current_user from auth routes
from routes.auth import User, get_current_user


# ==================== AUTH DEPENDENCIES ====================

async def require_admin(user: User = Depends(get_current_user)):
    """Dependency that requires super_admin or admin role."""
    if user.role not in ("super_admin", "admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


async def require_super_admin(user: User = Depends(get_current_user)):
    """Dependency that requires super_admin role."""
    if user.role != "super_admin":
        raise HTTPException(status_code=403, detail="Super admin access required")
    return user


# ==================== MODELS ====================

class CreateUserRequest(BaseModel):
    name: str
    email: str
    rating: int = 1200
    role: str = "user"


class ChangeRoleRequest(BaseModel):
    role: str  # "user", "admin", "super_admin"


class FlagMoveRequest(BaseModel):
    source: str  # "lab" or "coach"
    game_id: Optional[str] = None
    session_id: Optional[str] = None
    move_number: Optional[int] = None
    fen: str
    move_san: Optional[str] = None
    coaching_text: Optional[str] = None
    user_note: str
    # Developer-grade diagnostic fields
    severity: Optional[str] = None           # good/inaccuracy/mistake/blunder
    cp_loss: Optional[int] = None            # centipawn loss
    best_move: Optional[str] = None          # what Stockfish recommended
    eval_before: Optional[float] = None      # eval before the move
    eval_after: Optional[float] = None       # eval after the move
    phase: Optional[str] = None              # opening/middlegame/endgame
    component: Optional[str] = None          # which UI component (V5CoachingCard, DecryptionV5, etc.)
    concept_id: Optional[str] = None         # coaching concept that was shown
    goal: Optional[str] = None               # V5 coaching goal text
    consequence: Optional[str] = None        # V5 coaching consequence text
    better_approach: Optional[str] = None    # V5 coaching better_approach text
    your_plan_now: Optional[str] = None      # V5 your_plan_now text


class UpdateFeedbackRequest(BaseModel):
    status: str  # "acknowledged", "valid", "dismissed"
    admin_notes: Optional[str] = None


# ==================== ADMIN OVERVIEW ====================

@router.get("/admin/overview")
async def admin_overview(user: User = Depends(require_admin)):
    """Platform overview stats for admin dashboard."""
    from datetime import timedelta
    now = datetime.now(timezone.utc)
    seven_days_ago = (now - timedelta(days=7)).isoformat()
    thirty_days_ago = (now - timedelta(days=30)).isoformat()

    total_users = await db.users.count_documents({})
    total_games = await db.games.count_documents({})
    total_analyses = await db.game_analyses.count_documents({})

    # Active users (users who have games in last 7d/30d)
    recent_sessions_7d = await db.user_sessions.distinct(
        "user_id", {"created_at": {"$gte": seven_days_ago}}
    )
    recent_sessions_30d = await db.user_sessions.distinct(
        "user_id", {"created_at": {"$gte": thirty_days_ago}}
    )

    # Community training pool
    community_positions = await db.community_training_positions.count_documents({})

    # Feedback counts
    feedback_pending = await db.move_feedback.count_documents({"status": "pending"})
    feedback_total = await db.move_feedback.count_documents({})

    # Recent signups (last 5)
    recent_users = []
    async for u in db.users.find({}, {"_id": 0, "user_id": 1, "name": 1, "email": 1, "created_at": 1, "role": 1}).sort("created_at", -1).limit(5):
        recent_users.append(u)

    return {
        "total_users": total_users,
        "active_7d": len(recent_sessions_7d),
        "active_30d": len(recent_sessions_30d),
        "total_games": total_games,
        "total_analyses": total_analyses,
        "community_positions": community_positions,
        "feedback_pending": feedback_pending,
        "feedback_total": feedback_total,
        "recent_users": recent_users,
    }


# ==================== USER MANAGEMENT ====================

@router.get("/admin/users")
async def admin_list_users(
    search: str = None,
    role: str = None,
    sort_by: str = "created_at",
    limit: int = 50,
    skip: int = 0,
    user: User = Depends(require_admin),
):
    """List all users with optional search/filter."""
    query = {}
    if search:
        query["$or"] = [
            {"name": {"$regex": search, "$options": "i"}},
            {"email": {"$regex": search, "$options": "i"}},
            {"user_id": {"$regex": search, "$options": "i"}},
        ]
    if role:
        query["role"] = role

    users_list = []
    async for u in db.users.find(query, {"_id": 0}).sort(sort_by, -1).skip(skip).limit(limit):
        # Add game count
        game_count = await db.games.count_documents({"user_id": u["user_id"]})
        u["game_count"] = game_count
        u["role"] = u.get("role", "user")
        users_list.append(u)

    total = await db.users.count_documents(query)
    return {"users": users_list, "total": total}


@router.get("/admin/users/{target_user_id}")
async def admin_user_detail(target_user_id: str, user: User = Depends(require_admin)):
    """Detailed view of a specific user — rich debugging view."""
    target = await db.users.find_one({"user_id": target_user_id}, {"_id": 0})
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    target["role"] = target.get("role", "user")

    # ── Game stats ──
    game_count = await db.games.count_documents({"user_id": target_user_id})
    analysis_count = await db.game_analyses.count_documents({"user_id": target_user_id})

    games_by_platform = {}
    for plat in ("chess.com", "lichess", "coach"):
        n = await db.games.count_documents({"user_id": target_user_id, "platform": plat})
        if n:
            games_by_platform[plat] = n

    # Termination mix (quality read — how many abandoned vs real)
    termination_mix = {}
    async for row in db.games.aggregate([
        {"$match": {"user_id": target_user_id, "is_analyzed": True}},
        {"$group": {"_id": "$termination", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]):
        key = row["_id"] or "unknown"
        termination_mix[key] = row["count"]

    # ── Three rating signals ──
    rating_signals = {
        "platform_reported": {"chesscom": None, "lichess": None},
        "pgn_inferred": None,
        "performance_rated": None,
    }
    profile = await db.player_profiles.find_one({"user_id": target_user_id}, {"_id": 0})
    if profile:
        rating_signals["platform_reported"]["chesscom"] = (
            (profile.get("chesscom_stats") or {}).get("rating") or profile.get("chesscom_rating")
        )
        rating_signals["platform_reported"]["lichess"] = (
            (profile.get("lichess_stats") or {}).get("rating") or profile.get("lichess_rating")
        )

    try:
        from services.coach_memory import get_user_rating_from_games
        pgn_rating = await get_user_rating_from_games(db, target_user_id)
        rating_signals["pgn_inferred"] = pgn_rating
    except Exception:
        pass

    memory = await db.coach_memory.find_one({"user_id": target_user_id}, {"_id": 0})
    if memory:
        perf = memory.get("performance") or {}
        rating_signals["performance_rated"] = {
            "best": perf.get("best_performance_rating", 0),
            "worst": perf.get("worst_performance_rating", 0),
            "games_played": perf.get("games_played", 0),
            "avg_accuracy": round(perf.get("avg_accuracy", 0), 1),
            "improvement_rate": round(perf.get("improvement_rate", 0), 2),
        }

    # ── Engine 1: curriculum brain ──
    engine1 = None
    if memory:
        learning = memory.get("learning") or {}
        weaknesses = memory.get("weaknesses") or []
        weaknesses.sort(key=lambda w: w.get("detection_count", 0), reverse=True)
        recent_presc = []
        async for p in db.postgame_analyses.find(
            {"user_id": target_user_id, "coach_prescription": {"$exists": True, "$ne": None}},
            {"coach_prescription": 1, "prescription_type": 1, "prescription_reason": 1,
             "game_result": 1, "created_at": 1, "accuracy": 1, "blunders": 1, "_id": 0}
        ).sort("created_at", -1).limit(5):
            recent_presc.append(p)
        engine1 = {
            "current_focus": learning.get("current_focus"),
            "suggested_next": learning.get("suggested_next", []),
            "top_weaknesses": [
                {
                    "habit_id": w.get("habit_id"),
                    "name": w.get("name"),
                    "detection_count": w.get("detection_count", 0),
                    "improving": w.get("improving", False),
                    "last_detected": w.get("last_detected"),
                }
                for w in weaknesses[:5]
            ],
            "recent_prescriptions": recent_presc,
        }

    # ── Engine 2: skill tree ──
    engine2 = None
    if memory:
        learning = memory.get("learning") or {}
        skills_raw = learning.get("skills") or []
        skills = sorted(skills_raw, key=lambda s: -s.get("seen", 0))[:12]
        # Normalize outcomes for display
        skill_rows = []
        for s in skills:
            outcomes = (s.get("outcomes") or [])[-5:]
            skill_rows.append({
                "skill_id": s.get("skill_id"),
                "seen": s.get("seen", 0),
                "correct": s.get("correct", 0),
                "wrong": s.get("wrong", 0),
                "outcomes": outcomes,
                "learned": bool(s.get("learned_at")),
            })
        next_skill = None
        try:
            from services.engine2_skill_builder import pick_next_skill
            from services.coach_memory import get_or_create_memory
            mem_obj = await get_or_create_memory(db, target_user_id)
            rating = mem_obj.performance.best_performance_rating or 1000
            next_skill = pick_next_skill(mem_obj, rating)
        except Exception:
            pass
        engine2 = {
            "skills": skill_rows,
            "concepts_mastered": learning.get("concepts_mastered", []),
            "openings_learned": learning.get("openings_learned", []),
            "traps_learned": learning.get("traps_learned", []),
            "endgames_learned": learning.get("endgames_learned", []),
            "next_pick": next_skill,
        }

    # ── Engagement ──
    engagement = {
        "coach_sessions": await db.coach_sessions.count_documents({"user_id": target_user_id}),
        "coach_sessions_completed": await db.coach_sessions.count_documents(
            {"user_id": target_user_id, "status": "completed"}
        ),
        "coach_messages": await db.coach_messages.count_documents({"user_id": target_user_id}),
        "puzzle_attempts": await db.puzzle_attempts.count_documents({"user_id": target_user_id}),
        "puzzle_solved": await db.puzzle_attempts.count_documents(
            {"user_id": target_user_id, "correct": True}
        ),
        "notifications_sent": await db.notifications.count_documents({"user_id": target_user_id}),
    }
    last_session = await db.coach_sessions.find_one(
        {"user_id": target_user_id}, sort=[("created_at", -1)],
        projection={"created_at": 1, "_id": 0}
    )
    engagement["last_active"] = (last_session or {}).get("created_at")

    # ── Opening progress ──
    opening_progress = []
    async for op in db.user_opening_progress.find({"user_id": target_user_id}, {"_id": 0}).limit(10):
        opening_progress.append(op)

    # ── Player habits ──
    habits = await db.player_habits.find_one({"user_id": target_user_id}, {"_id": 0})

    # ── Recent games ──
    recent_games = []
    async for g in db.games.find(
        {"user_id": target_user_id},
        {"_id": 0, "game_id": 1, "opening": 1, "result": 1, "user_color": 1,
         "date_played": 1, "platform": 1, "termination": 1, "is_analyzed": 1,
         "imported_at": 1}
    ).sort("imported_at", -1).limit(15):
        recent_games.append(g)

    # ── User feedback ──
    user_feedback = []
    async for fb in db.move_feedback.find({"user_id": target_user_id}, {"_id": 0}).sort("created_at", -1).limit(10):
        fb["id"] = str(fb.get("feedback_id", ""))
        user_feedback.append(fb)

    # ── Gap diagnostics ──
    gaps = []
    if not memory:
        gaps.append("No coach_memory — no game has been analyzed for this user yet.")
    else:
        perf = memory.get("performance") or {}
        if not perf.get("best_performance_rating"):
            gaps.append("performance.best_performance_rating is 0 — run --backfill to set it from PGN Elo.")
        learning = memory.get("learning") or {}
        if not learning.get("current_focus") and analysis_count > 0:
            gaps.append("No current_focus despite analyzed games — curriculum brain may not have run. "
                        "Check analysis_worker PHASE 5.5.")
        if not (learning.get("skills") or []) and analysis_count >= 5:
            gaps.append(f"No Engine 2 skill attempts recorded. "
                        f"Run: python scripts/backfill_engine2_skills.py {target_user_id} --limit 25 --reset")
    if game_count > 0 and analysis_count == 0:
        gaps.append("Games imported but none analyzed — check the analysis queue.")
    if termination_mix:
        bad = sum(v for k, v in termination_mix.items() if k in ("abandonment", "abandoned", "aborted", "unknown"))
        if bad and bad / max(analysis_count, 1) > 0.4:
            gaps.append(f"{bad}/{analysis_count} analyzed games have no real termination — "
                        "many may be abandoned, skewing signals.")

    return {
        "user": target,
        "game_count": game_count,
        "analysis_count": analysis_count,
        "games_by_platform": games_by_platform,
        "termination_mix": termination_mix,
        "rating_signals": rating_signals,
        "engine1": engine1,
        "engine2": engine2,
        "engagement": engagement,
        "opening_progress": opening_progress,
        "habits": habits,
        "recent_games": recent_games,
        "feedback": user_feedback,
        "gaps": gaps,
    }


@router.post("/admin/users")
async def admin_create_user(req: CreateUserRequest, user: User = Depends(require_super_admin)):
    """Create a new user (super_admin only)."""
    existing = await db.users.find_one({"email": req.email}, {"_id": 0})
    if existing:
        raise HTTPException(status_code=409, detail="User with this email already exists")

    new_user = {
        "user_id": f"user_{uuid.uuid4().hex[:12]}",
        "email": req.email,
        "name": req.name,
        "rating": req.rating,
        "role": req.role,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.users.insert_one(new_user)
    new_user.pop("_id", None)
    return {"message": "User created", "user": new_user}


@router.patch("/admin/users/{target_user_id}/role")
async def admin_change_role(target_user_id: str, req: ChangeRoleRequest, user: User = Depends(require_super_admin)):
    """Change a user's role (super_admin only)."""
    if req.role not in ("user", "admin", "super_admin"):
        raise HTTPException(status_code=400, detail="Invalid role")
    if target_user_id == user.user_id and req.role != "super_admin":
        raise HTTPException(status_code=400, detail="Cannot remove your own super_admin role")

    result = await db.users.update_one(
        {"user_id": target_user_id},
        {"$set": {"role": req.role}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    return {"message": f"Role updated to {req.role}"}


# ==================== USER ACTIVITY TIMELINE ====================


def _to_iso(val):
    """Normalise timestamp-ish values to an ISO string. Returns None on failure."""
    if val is None:
        return None
    if isinstance(val, datetime):
        d = val if val.tzinfo else val.replace(tzinfo=timezone.utc)
        return d.isoformat()
    if isinstance(val, str):
        try:
            d = datetime.fromisoformat(val.replace("Z", "+00:00"))
            d = d if d.tzinfo else d.replace(tzinfo=timezone.utc)
            return d.isoformat()
        except Exception:
            return val  # return as-is, frontend can try to parse
    return None


def _parse_ts(val):
    if val is None:
        return None
    if isinstance(val, datetime):
        return val if val.tzinfo else val.replace(tzinfo=timezone.utc)
    if isinstance(val, str):
        try:
            d = datetime.fromisoformat(val.replace("Z", "+00:00"))
            return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
        except Exception:
            return None
    return None


@router.get("/admin/users/{target_user_id}/activity")
async def admin_user_activity(
    target_user_id: str,
    limit: int = 100,
    days: Optional[int] = None,
    user: User = Depends(require_admin),
):
    """
    Chronological activity timeline for a user — stitches events from
    games, game_analyses, coach_sessions, postgame_analyses,
    puzzle_attempts, user_opening_progress, notifications.

    Each event: { ts, ts_iso, type, summary, detail?, game_id?, session_id? }.
    Newest first.
    """
    # Ensure target exists
    target = await db.users.find_one({"user_id": target_user_id}, {"_id": 0, "user_id": 1})
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    since = None
    if days:
        since = datetime.now(timezone.utc) - timedelta(days=days)

    events: List[dict] = []

    # ── Games imported ──
    q = {"user_id": target_user_id}
    if since:
        q["imported_at"] = {"$gte": since.isoformat()}
    async for g in db.games.find(
        q, {"_id": 0, "game_id": 1, "opening": 1, "result": 1, "user_color": 1,
            "platform": 1, "imported_at": 1, "termination": 1}
    ).sort("imported_at", -1).limit(500):
        ts = _parse_ts(g.get("imported_at"))
        if not ts:
            continue
        r = (g.get("result") or "").lower()
        uc = (g.get("user_color") or "").lower()
        if r in ("1-0", "0-1"):
            outcome = "won" if (r == "1-0" and uc == "white") or (r == "0-1" and uc == "black") else "lost"
        elif r in ("1/2-1/2", "draw", "d"): outcome = "drew"
        elif r in ("win", "w"): outcome = "won"
        elif r in ("loss", "l"): outcome = "lost"
        else: outcome = "played"
        events.append({
            "ts": ts,
            "ts_iso": _to_iso(ts),
            "type": "game",
            "summary": f"{outcome} a game — {g.get('opening') or 'unknown opening'} [{g.get('platform') or '?'}]",
            "detail": f"termination: {g.get('termination', '?')}",
            "game_id": g.get("game_id"),
        })

    # ── Game analyses ──
    q = {"user_id": target_user_id}
    if since:
        q["created_at"] = {"$gte": since.isoformat()}
    async for a in db.game_analyses.find(
        q, {"_id": 0, "game_id": 1, "created_at": 1,
            "stockfish_analysis.accuracy": 1,
            "stockfish_analysis.blunders": 1,
            "stockfish_analysis.mistakes": 1}
    ).sort("created_at", -1).limit(500):
        ts = _parse_ts(a.get("created_at"))
        if not ts:
            continue
        sf = a.get("stockfish_analysis") or {}
        events.append({
            "ts": ts,
            "ts_iso": _to_iso(ts),
            "type": "analysis",
            "summary": (
                f"game analyzed — accuracy {sf.get('accuracy', '?')}%, "
                f"{sf.get('blunders', 0)} blunders, {sf.get('mistakes', 0)} mistakes"
            ),
            "game_id": a.get("game_id"),
        })

    # ── Coach sessions ──
    q = {"user_id": target_user_id}
    if since:
        q["created_at"] = {"$gte": since.isoformat()}
    async for s in db.coach_sessions.find(
        q, {"_id": 0, "session_id": 1, "created_at": 1, "completed_at": 1,
            "status": 1, "result": 1, "opponent": 1, "focus": 1}
    ).sort("created_at", -1).limit(200):
        start = _parse_ts(s.get("created_at"))
        end = _parse_ts(s.get("completed_at"))
        if start:
            events.append({
                "ts": start,
                "ts_iso": _to_iso(start),
                "type": "coach",
                "summary": "started Play-with-Coach session" + (
                    f" (focus: {s['focus']})" if s.get("focus") else ""),
                "session_id": s.get("session_id"),
            })
        if end and s.get("status") == "completed":
            events.append({
                "ts": end,
                "ts_iso": _to_iso(end),
                "type": "coach",
                "summary": f"completed Play-with-Coach — {s.get('result') or 'finished'}",
                "session_id": s.get("session_id"),
            })

    # ── Prescriptions ──
    q = {"user_id": target_user_id, "coach_prescription": {"$exists": True, "$ne": None}}
    if since:
        q["created_at"] = {"$gte": since.isoformat()}
    async for p in db.postgame_analyses.find(
        q, {"_id": 0, "coach_prescription": 1, "prescription_reason": 1,
            "prescription_type": 1, "game_result": 1, "created_at": 1}
    ).sort("created_at", -1).limit(200):
        ts = _parse_ts(p.get("created_at"))
        if not ts:
            continue
        events.append({
            "ts": ts,
            "ts_iso": _to_iso(ts),
            "type": "prescription",
            "summary": (
                f"coach prescribed: {p.get('coach_prescription')} "
                f"({p.get('prescription_type', 'pattern')}) after {p.get('game_result', '?')}"
            ),
            "detail": p.get("prescription_reason", ""),
        })

    # ── Puzzle attempts ──
    sample = await db.puzzle_attempts.find_one({"user_id": target_user_id}, {"attempted_at": 1, "created_at": 1})
    if sample:
        time_field = "attempted_at" if sample.get("attempted_at") else "created_at"
        q = {"user_id": target_user_id}
        if since:
            q[time_field] = {"$gte": since.isoformat()}
        async for a in db.puzzle_attempts.find(
            q, {"_id": 0, "correct": 1, "weakness_type": 1,
                "attempted_at": 1, "created_at": 1}
        ).sort(time_field, -1).limit(200):
            ts = _parse_ts(a.get(time_field))
            if not ts:
                continue
            solved = "solved" if a.get("correct") else "missed"
            w = a.get("weakness_type") or ""
            events.append({
                "ts": ts,
                "ts_iso": _to_iso(ts),
                "type": "puzzle",
                "summary": f"{solved} a {w} puzzle" if w else f"{solved} a puzzle",
            })

    # ── Opening progress changes ──
    q = {"user_id": target_user_id}
    if since:
        q["updated_at"] = {"$gte": since.isoformat()}
    async for op in db.user_opening_progress.find(
        q, {"_id": 0, "opening_name": 1, "games_played": 1,
            "mastery_level": 1, "updated_at": 1}
    ).sort("updated_at", -1).limit(50):
        ts = _parse_ts(op.get("updated_at"))
        if not ts:
            continue
        events.append({
            "ts": ts,
            "ts_iso": _to_iso(ts),
            "type": "opening",
            "summary": (
                f"opening progress: {op.get('opening_name', '?')} — "
                f"{op.get('games_played', 0)} games, mastery {op.get('mastery_level', 0)}%"
            ),
        })

    # ── Sort newest first, trim, strip raw ts ──
    events.sort(key=lambda e: e["ts"], reverse=True)
    events = events[:max(1, min(limit, 500))]
    for e in events:
        del e["ts"]

    # Counts by type for the summary row
    counts: Dict[str, int] = {}
    for e in events:
        counts[e["type"]] = counts.get(e["type"], 0) + 1

    return {
        "user_id": target_user_id,
        "events": events,
        "counts": counts,
        "total_returned": len(events),
        "window_days": days,
    }


# ==================== FEEDBACK QUEUE ====================

@router.post("/feedback/flag")
async def flag_move(req: FlagMoveRequest, user: User = Depends(get_current_user)):
    """User flags a move's coaching as incorrect or unhelpful."""
    feedback_doc = {
        "feedback_id": f"fb_{uuid.uuid4().hex[:12]}",
        "user_id": user.user_id,
        "user_name": user.name,
        "user_rating": None,
        "source": req.source,
        "game_id": req.game_id,
        "session_id": req.session_id,
        "move_number": req.move_number,
        "fen": req.fen,
        "move_san": req.move_san,
        "coaching_text": req.coaching_text,
        "user_note": req.user_note,
        "status": "pending",
        "admin_notes": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        # Developer diagnostic data
        "diagnostics": {
            "severity": req.severity,
            "cp_loss": req.cp_loss,
            "best_move": req.best_move,
            "eval_before": req.eval_before,
            "eval_after": req.eval_after,
            "phase": req.phase,
            "component": req.component,
            "concept_id": req.concept_id,
            "goal": req.goal,
            "consequence": req.consequence,
            "better_approach": req.better_approach,
            "your_plan_now": req.your_plan_now,
        }
    }

    # Try to get user rating
    user_doc = await db.users.find_one({"user_id": user.user_id}, {"_id": 0, "rating": 1})
    if user_doc:
        feedback_doc["user_rating"] = user_doc.get("rating")

    await db.move_feedback.insert_one(feedback_doc)
    feedback_doc.pop("_id", None)
    return {"message": "Feedback submitted", "feedback_id": feedback_doc["feedback_id"]}


@router.get("/admin/feedback")
async def admin_list_feedback(
    status: str = None,
    source: str = None,
    limit: int = 50,
    skip: int = 0,
    user: User = Depends(require_admin),
):
    """List feedback queue for admins."""
    query = {}
    if status:
        query["status"] = status
    if source:
        query["source"] = source

    feedback_list = []
    async for fb in db.move_feedback.find(query, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit):
        feedback_list.append(fb)

    total = await db.move_feedback.count_documents(query)
    pending = await db.move_feedback.count_documents({"status": "pending"})
    return {"feedback": feedback_list, "total": total, "pending": pending}


@router.patch("/admin/feedback/{feedback_id}")
async def admin_update_feedback(feedback_id: str, req: UpdateFeedbackRequest, user: User = Depends(require_admin)):
    """Update feedback status (admin)."""
    if req.status not in ("pending", "acknowledged", "valid", "dismissed"):
        raise HTTPException(status_code=400, detail="Invalid status")

    update = {
        "$set": {
            "status": req.status,
            "reviewed_by": user.user_id,
            "reviewed_at": datetime.now(timezone.utc).isoformat(),
        }
    }
    if req.admin_notes:
        update["$set"]["admin_notes"] = req.admin_notes

    result = await db.move_feedback.update_one({"feedback_id": feedback_id}, update)
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Feedback not found")
    return {"message": f"Feedback marked as {req.status}"}


@router.get("/admin/feedback/export")
async def admin_export_feedback(
    status: str = None,
    source: str = None,
    user: User = Depends(require_admin),
):
    """Export all feedback as a downloadable JSON file for developer handoff."""
    query = {}
    if status and status != "all":
        query["status"] = status
    if source and source != "all":
        query["source"] = source

    items = []
    async for fb in db.move_feedback.find(query, {"_id": 0}).sort("created_at", -1):
        diag = fb.get("diagnostics") or {}
        item = {
            "feedback_id": fb.get("feedback_id"),
            "page": fb.get("source", "unknown"),
            "issue": fb.get("user_note", ""),
            "coaching_text_flagged": fb.get("coaching_text"),
            "severity": diag.get("severity") or "unknown",
            "status": fb.get("status", "pending"),
            "user": fb.get("user_name") or fb.get("user_id"),
            "user_rating": fb.get("user_rating"),
            "created_at": fb.get("created_at"),
            "position": {
                "fen": fb.get("fen"),
                "move_san": fb.get("move_san"),
                "move_number": fb.get("move_number"),
                "best_move": diag.get("best_move"),
                "cp_loss": diag.get("cp_loss"),
                "eval_before": diag.get("eval_before"),
                "eval_after": diag.get("eval_after"),
                "phase": diag.get("phase"),
            },
            "context": {
                "game_id": fb.get("game_id"),
                "session_id": fb.get("session_id"),
                "component": diag.get("component"),
                "concept_id": diag.get("concept_id"),
                "goal": diag.get("goal"),
                "consequence": diag.get("consequence"),
                "better_approach": diag.get("better_approach"),
                "your_plan_now": diag.get("your_plan_now"),
            },
            "admin_notes": fb.get("admin_notes"),
            "reviewed_by": fb.get("reviewed_by"),
            "reviewed_at": fb.get("reviewed_at"),
        }
        items.append(item)

    import json as json_lib
    export_data = {
        "export_version": "1.0",
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "filters": {"status": status or "all", "source": source or "all"},
        "total": len(items),
        "feedback": items,
    }

    # Write file to disk
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S")
    filename = f"feedback-export-{today}.json"
    export_dir = os.path.join(os.path.dirname(__file__), "..", "exports")
    os.makedirs(export_dir, exist_ok=True)
    filepath = os.path.join(export_dir, filename)
    with open(filepath, "w") as f:
        json_lib.dump(export_data, f, indent=2, ensure_ascii=False)

    return {"file_url": f"/admin/feedback/download/{filename}", "filename": filename, "total": len(items)}


@router.get("/admin/feedback/download/{filename}")
async def admin_download_feedback_file(filename: str):
    """Serve an exported feedback JSON file."""
    from fastapi.responses import FileResponse
    export_dir = os.path.join(os.path.dirname(__file__), "..", "exports")
    filepath = os.path.join(export_dir, filename)
    if not os.path.exists(filepath) or ".." in filename:
        raise HTTPException(status_code=404, detail="Export file not found")
    return FileResponse(
        path=filepath,
        filename=filename,
        media_type="application/octet-stream",
    )


# ==================== DECRYPTION REVIEW QUEUE ====================
# Auto-flagged moments from game_analyses.decryption_block.moments[]
# where confidence < 0.8. The coach reviews each, writes an override
# string, and the override is logged to coach_overrides for offline
# improvement work — no live patching of player-facing data.

class DecryptionOverrideRequest(BaseModel):
    game_id: str
    move_number: int
    move_san: str
    override_text: str
    coach_note: Optional[str] = None


@router.get("/admin/decryption-review")
async def admin_decryption_review(
    limit: int = 100,
    skip: int = 0,
    include_overridden: bool = False,
    user: User = Depends(require_admin),
):
    """List moments flagged for review (confidence < 0.8) across all games."""
    pipeline = [
        {"$match": {"decryption_block.moments": {"$exists": True, "$ne": []}}},
        {"$unwind": "$decryption_block.moments"},
        {"$match": {"decryption_block.moments.needs_review": True}},
        {"$project": {
            "_id": 0,
            "game_id": 1,
            "user_id": 1,
            "moment": "$decryption_block.moments",
        }},
        {"$sort": {"moment.confidence": 1, "game_id": 1}},
        {"$skip": skip},
        {"$limit": limit},
    ]
    rows = []
    async for doc in db.game_analyses.aggregate(pipeline):
        m = doc.get("moment") or {}
        rows.append({
            "game_id": doc.get("game_id"),
            "user_id": doc.get("user_id"),
            "move_number": m.get("move_number"),
            "move_san": m.get("move_san"),
            "move_uci": m.get("move_uci"),
            "fen_before": m.get("fen_before"),
            "fen_after": m.get("fen_after"),
            "cp_loss": m.get("cp_loss"),
            "severity": m.get("severity"),
            "source": m.get("source"),
            "attempts": m.get("attempts"),
            "text": m.get("text"),
            "confidence": m.get("confidence"),
            "confidence_breakdown": m.get("confidence_breakdown"),
            "candidates": m.get("candidates") or [],
            "best_move_san": next(
                (c.get("san") for c in (m.get("candidates") or []) if c.get("isCorrect")),
                None,
            ),
        })

    # Total count of flagged moments (for pagination UI).
    total_pipeline = [
        {"$match": {"decryption_block.moments": {"$exists": True, "$ne": []}}},
        {"$unwind": "$decryption_block.moments"},
        {"$match": {"decryption_block.moments.needs_review": True}},
        {"$count": "total"},
    ]
    total = 0
    async for d in db.game_analyses.aggregate(total_pipeline):
        total = d.get("total", 0)

    # Mark which rows already have an override.
    if rows:
        keys = [
            (r["game_id"], r["move_number"], r["move_san"])
            for r in rows
        ]
        override_map = {}
        async for ov in db.coach_overrides.find(
            {"game_id": {"$in": [k[0] for k in keys]}},
            {"_id": 0, "game_id": 1, "move_number": 1, "move_san": 1, "override_text": 1, "created_at": 1},
        ):
            override_map[(ov["game_id"], ov["move_number"], ov["move_san"])] = ov
        for r in rows:
            ov = override_map.get((r["game_id"], r["move_number"], r["move_san"]))
            if ov:
                r["override"] = {
                    "text": ov.get("override_text"),
                    "created_at": ov.get("created_at"),
                }
            else:
                r["override"] = None

    if not include_overridden:
        rows = [r for r in rows if not r.get("override")]

    return {"items": rows, "total": total}


@router.post("/admin/decryption-review/override")
async def admin_save_decryption_override(
    req: DecryptionOverrideRequest,
    user: User = Depends(require_admin),
):
    """Save the coach's override for one flagged moment.

    Logs to coach_overrides only — does NOT patch the live moment text.
    Overrides feed offline improvement work (write a missing template,
    refine the prompt, etc.). Re-saving the same key updates the
    existing override.
    """
    text = (req.override_text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="override_text required")

    # Pull the original moment so we capture full context.
    analysis = await db.game_analyses.find_one(
        {"game_id": req.game_id},
        {"_id": 0, "user_id": 1, "decryption_block": 1},
    )
    if not analysis:
        raise HTTPException(status_code=404, detail="game_analyses not found")

    moments = ((analysis.get("decryption_block") or {}).get("moments") or [])
    target = next(
        (m for m in moments
         if m.get("move_number") == req.move_number and m.get("move_san") == req.move_san),
        None,
    )
    if not target:
        raise HTTPException(status_code=404, detail="moment not found")

    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "game_id": req.game_id,
        "user_id": analysis.get("user_id"),
        "move_number": req.move_number,
        "move_san": req.move_san,
        "move_uci": target.get("move_uci"),
        "fen_before": target.get("fen_before"),
        "fen_after": target.get("fen_after"),
        "cp_loss": target.get("cp_loss"),
        "severity": target.get("severity"),
        "source": target.get("source"),
        "pattern_type": (
            target.get("source", "").split(":", 1)[1]
            if target.get("source", "").startswith("template:") else None
        ),
        "best_move_san": next(
            (c.get("san") for c in (target.get("candidates") or []) if c.get("isCorrect")),
            None,
        ),
        "original_text": target.get("text"),
        "override_text": text,
        "coach_note": req.coach_note,
        "confidence": target.get("confidence"),
        "confidence_breakdown": target.get("confidence_breakdown"),
        "coach_user_id": user.user_id,
        "coach_email": getattr(user, "email", None),
        "updated_at": now,
    }

    # Upsert keyed on (game_id, move_number, move_san).
    res = await db.coach_overrides.update_one(
        {
            "game_id": req.game_id,
            "move_number": req.move_number,
            "move_san": req.move_san,
        },
        {
            "$set": doc,
            "$setOnInsert": {
                "override_id": f"ov_{uuid.uuid4().hex[:12]}",
                "created_at": now,
            },
        },
        upsert=True,
    )
    return {
        "saved": True,
        "created": res.upserted_id is not None,
        "game_id": req.game_id,
        "move_number": req.move_number,
        "move_san": req.move_san,
    }


@router.get("/admin/decryption-review/overrides")
async def admin_list_decryption_overrides(
    limit: int = 100,
    skip: int = 0,
    user: User = Depends(require_admin),
):
    """List all saved overrides — the dataset to fix templates/prompts from."""
    rows = []
    async for ov in db.coach_overrides.find({}, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit):
        rows.append(ov)
    total = await db.coach_overrides.count_documents({})
    return {"items": rows, "total": total}
