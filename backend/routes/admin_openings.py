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

    from services.opening_theory_json_service import get_all_opening_keys, get_opening_theory, get_available_variations
    
    openings = []
    for key in get_all_opening_keys():
        theory = get_opening_theory(key)
        if not theory:
            continue
        variations = get_available_variations(key)
        total_variations = len(variations)
        max_depth = max((v["total_moves"] for v in variations), default=0)
        
        openings.append({
            "opening_key": key,
            "opening_name": theory.get("name", key.replace("_", " ").title()),
            "sources": ["json_theory"],
            "updated_at": None,
            "variations_count": total_variations,
            "max_depth": max_depth,
            "eco_prefix": theory.get("eco_prefix", []),
        })
    
    openings.sort(key=lambda x: x["opening_name"])
    return {"openings": openings, "count": len(openings)}


@router.get("/{opening_key}")
async def get_opening_feedback(opening_key: str, user: User = Depends(get_current_user)):
    _ensure_authenticated_admin(user)

    from services.opening_theory_json_service import get_opening_theory, get_available_variations, get_variation_lesson_moves
    from services.verified_opening_traps import get_verified_traps_for_opening
    
    theory = get_opening_theory(opening_key)
    if not theory:
        raise HTTPException(status_code=404, detail="Opening not found in theory database")
    
    variations = get_available_variations(opening_key)
    traps = get_verified_traps_for_opening(opening_key)
    
    # Build variation details
    variation_details = []
    for var in variations:
        lesson = get_variation_lesson_moves(opening_key, var["key"])
        if lesson:
            variation_details.append({
                "key": var["key"],
                "name": var["name"],
                "total_moves": var["total_moves"],
                "moves": lesson["moves"],
                "white_plan": lesson.get("white_plan", ""),
                "black_plan": lesson.get("black_plan", ""),
                "critical_positions": lesson.get("critical_positions", {}),
            })
    
    # Build trap details
    trap_details = []
    for trap in traps:
        trap_details.append({
            "name": trap.name,
            "description": trap.explanation,
            "difficulty": trap.difficulty,
            "victim_color": trap.victim_color,
        })
    
    return {
        "opening_key": opening_key,
        "opening_name": theory.get("name", opening_key),
        "feedback": {
            "opening_key": opening_key,
            "opening_name": theory.get("name", opening_key),
            "eco_prefix": theory.get("eco_prefix", []),
            "main_line": theory.get("main_line", []),
            "white_plan": theory.get("white_plan", ""),
            "black_plan": theory.get("black_plan", ""),
            "common_learnings": theory.get("common_learnings", []),
            "variations": variation_details,
            "traps": trap_details,
            "critical_positions": theory.get("critical_positions", {}),
        },
        "source": "json_theory",
        "updated_at": None,
    }


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