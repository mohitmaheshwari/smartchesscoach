"""Admin Opening Feedback Manager routes."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ValidationError

from routes.auth import User, get_current_user

router = APIRouter(prefix="/admin/openings", tags=["Admin Openings"])

db = None


def set_db(database):
    global db
    db = database


class OpeningFeedbackSchema(BaseModel):
    opening_key: str
    opening_name: str
    identity: str
    difficulty: str
    core_concepts: List[str]
    plans: Dict[str, List[str]]
    traps: List[Dict[str, Any]]
    common_mistakes: List[Dict[str, Any]]
    ideas_tab: List[Dict[str, str]]
    adaptive_layers: Dict[str, Any]
    coach_voice_lines: List[str]


class OpeningFeedbackSaveRequest(BaseModel):
    feedback: Dict[str, Any]


class OpeningFeedbackValidateRequest(BaseModel):
    feedback: Dict[str, Any]


def _ensure_authenticated_admin(user: User) -> None:
    # Development-stage behavior requested by user: current logged-in user can use it.
    if not user.user_id:
        raise HTTPException(status_code=403, detail="Admin access denied")


@router.get("")
async def list_opening_feedback(user: User = Depends(get_current_user)):
    _ensure_authenticated_admin(user)

    docs = await db.opening_feedback.find({}, {"_id": 0, "opening_key": 1, "opening_name": 1, "updated_at": 1}).sort("opening_key", 1).to_list(500)
    return {"openings": docs, "count": len(docs)}


@router.get("/{opening_key}")
async def get_opening_feedback(opening_key: str, user: User = Depends(get_current_user)):
    _ensure_authenticated_admin(user)

    doc = await db.opening_feedback.find_one({"opening_key": opening_key}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Opening feedback not found")
    return doc


@router.post("/validate")
async def validate_opening_feedback(request: OpeningFeedbackValidateRequest, user: User = Depends(get_current_user)):
    _ensure_authenticated_admin(user)

    try:
        validated = OpeningFeedbackSchema(**request.feedback)
    except ValidationError as exc:
        return {
            "valid": False,
            "errors": exc.errors(),
        }

    return {
        "valid": True,
        "normalized": validated.model_dump(),
    }


@router.post("/save")
async def save_opening_feedback(request: OpeningFeedbackSaveRequest, user: User = Depends(get_current_user)):
    _ensure_authenticated_admin(user)

    try:
        validated = OpeningFeedbackSchema(**request.feedback)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail={"message": "Invalid opening feedback JSON", "errors": exc.errors()})

    now = datetime.now(timezone.utc)
    payload = validated.model_dump()
    opening_key = payload["opening_key"]

    existing = await db.opening_feedback.find_one({"opening_key": opening_key}, {"_id": 0})
    if existing:
        version_doc = {
            "opening_key": opening_key,
            "opening_name": existing.get("opening_name"),
            "feedback": existing.get("feedback"),
            "versioned_at": now,
            "versioned_by": user.user_id,
        }
        await db.opening_feedback_versions.insert_one(version_doc)

    doc = {
        "opening_key": opening_key,
        "opening_name": payload["opening_name"],
        "feedback": payload,
        "updated_at": now,
        "updated_by": user.user_id,
    }
    if not existing:
        doc["created_at"] = now
        doc["created_by"] = user.user_id

    await db.opening_feedback.update_one(
        {"opening_key": opening_key},
        {"$set": doc},
        upsert=True,
    )

    return {
        "status": "saved",
        "opening_key": opening_key,
        "opening_name": payload["opening_name"],
        "has_previous_version": existing is not None,
        "updated_at": now,
    }