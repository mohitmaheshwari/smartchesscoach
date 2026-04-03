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
from typing import Optional
from datetime import datetime, timezone
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
    """Detailed view of a specific user."""
    target = await db.users.find_one({"user_id": target_user_id}, {"_id": 0})
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    target["role"] = target.get("role", "user")

    # Game stats
    game_count = await db.games.count_documents({"user_id": target_user_id})
    analysis_count = await db.game_analyses.count_documents({"user_id": target_user_id})

    # Opening progress
    opening_progress = []
    async for op in db.user_opening_progress.find({"user_id": target_user_id}, {"_id": 0}).limit(10):
        opening_progress.append(op)

    # Player habits
    habits = await db.player_habits.find_one({"user_id": target_user_id}, {"_id": 0})

    # Recent games
    recent_games = []
    async for g in db.games.find({"user_id": target_user_id}, {"_id": 0, "game_id": 1, "opening": 1, "result": 1, "user_color": 1, "date_played": 1, "platform": 1}).sort("imported_at", -1).limit(10):
        recent_games.append(g)

    # Feedback from this user
    user_feedback = []
    async for fb in db.move_feedback.find({"user_id": target_user_id}, {"_id": 0}).sort("created_at", -1).limit(10):
        fb["id"] = str(fb.get("feedback_id", ""))
        user_feedback.append(fb)

    return {
        "user": target,
        "game_count": game_count,
        "analysis_count": analysis_count,
        "opening_progress": opening_progress,
        "habits": habits,
        "recent_games": recent_games,
        "feedback": user_feedback,
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
