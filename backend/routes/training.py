"""
Training Routes
===============

Handles all training-related functionality including:
- Spaced repetition cards and sessions
- Puzzle training
- Weakness-based prescribed training
- Opening training
- Trick/trap training
- Progress tracking

This is a large module - ~60 endpoints covering all training features.
"""

from fastapi import APIRouter, HTTPException, Depends, Body
from pydantic import BaseModel
from typing import Optional, List, Dict
import logging
import os
import uuid

logger = logging.getLogger(__name__)

# Create router for training endpoints
router = APIRouter(prefix="/training", tags=["Training"])

# Database reference - will be set by server.py
db = None

def set_db(database):
    """Set the database reference for training routes"""
    global db
    db = database


# Import User model and get_current_user from auth routes
from routes.auth import User, get_current_user


async def _require_pic_training_user(user: User):
    from services.focus_bridge import get_pic_focus_projection

    projection = await get_pic_focus_projection(db, user.user_id)
    if not projection or not projection.get("eligible"):
        raise HTTPException(
            status_code=409,
            detail="An eligible PIC piece-safety focus is required",
        )
    return projection


async def _require_personalized_teaching_user(user: User):
    """Keep the new delivery path inside the existing role allowlist."""
    from services.personal_curriculum import personalized_teaching_eligible

    role = getattr(user, "role", None)
    if not role:
        user_doc = await db.users.find_one(
            {"user_id": user.user_id},
            {"_id": 0, "role": 1},
        )
        role = (user_doc or {}).get("role")
    if not personalized_teaching_eligible(role):
        raise HTTPException(status_code=404, detail="Lesson not found")
    return role


async def _require_home_diagnostic_user(user: User):
    """Require the default-off flag, exact focus, and explicit enrollment."""
    await _require_personalized_teaching_user(user)
    from services.destination_safety_detector import QUALITY_ID
    from services.detector_quality import QualitySurface, is_authorized
    from services.focus_bridge import get_active_focus_bundle
    from services.personal_curriculum import home_replay_diagnostic_enabled

    if not home_replay_diagnostic_enabled(os.environ):
        raise HTTPException(status_code=404, detail="Lesson not found")
    user_doc = await db.users.find_one(
        {"user_id": user.user_id},
        {"_id": 0, "feature_flags": 1},
    )
    enrollment = ((user_doc or {}).get("feature_flags") or {}).get(
        "home_replay_diagnostic"
    ) or {}
    if enrollment.get("enabled") is not True:
        raise HTTPException(status_code=404, detail="Lesson not found")
    focus = await get_active_focus_bundle(db, user.user_id)
    if (
        not focus
        or focus.get("detector_quality_id") != QUALITY_ID
        or not is_authorized(QUALITY_ID, QualitySurface.PLAN)
    ):
        raise HTTPException(status_code=409, detail="Verified focus is required")
    return focus


def _raise_pic_lesson_error(result: Dict):
    if result.get("error"):
        status = 404 if result["error"] == "Session not found" else 409
        raise HTTPException(status_code=status, detail=result["error"])
    return result

# Import training services (from mistake_card_service)
from mistake_card_service import (
    get_training_session,
    get_due_cards,
    get_card_by_id,
    record_card_attempt,
    generate_why_question,
    get_user_habit_progress,
    get_training_stats,
    set_active_habit,
    HABIT_DEFINITIONS
)


# ==================== MODELS ====================

class CardAttemptRequest(BaseModel):
    card_id: str
    played_uci: str
    submission_id: Optional[str] = None


class SetActiveHabitRequest(BaseModel):
    habit_key: str


class PuzzleAttemptRequest(BaseModel):
    puzzle_id: str
    played_uci: str
    time_taken_ms: Optional[int] = None
    moves_tried: Optional[List[str]] = []
    submission_id: Optional[str] = None


class PICLessonStartRequest(BaseModel):
    limit: int = 5


class PICLessonMoveRequest(BaseModel):
    session_id: str
    move: str
    interaction_id: Optional[str] = None


class PICLessonPauseRequest(BaseModel):
    session_id: str
    choice: str = "pause"


class PersonalizedLessonStartRequest(BaseModel):
    content_kind: str
    content_id: str
    skill_id: Optional[str] = None
    limit: int = 5
    player_color: Optional[str] = None
    variation: Optional[str] = None
    mode: Optional[str] = None
    review: bool = False


class PersonalizedLessonRespondRequest(BaseModel):
    session_id: str
    move: str
    interaction_id: Optional[str] = None
    reason_choice: Optional[str] = None
    reason_component_id: Optional[str] = None


class PersonalizedLessonHelpRequest(BaseModel):
    session_id: str
    action: str
    interaction_id: Optional[str] = None


class PersonalizedLessonPauseRequest(BaseModel):
    session_id: str
    choice: str = "pause"


class HomeDiagnosticStartRequest(BaseModel):
    limit: int = 20


class HomeDiagnosticContinueRequest(BaseModel):
    session_id: str
    interaction_id: Optional[str] = None


# ==================== PERSONAL IMPROVEMENT CYCLE ====================

@router.post("/pic/session/start")
async def start_pic_training_session(
    request: PICLessonStartRequest,
    user: User = Depends(get_current_user),
):
    """Start or resume the verified, own-game-first piece-safety lesson."""
    projection = await _require_pic_training_user(user)
    from services.teaching_engine import PIC_LESSON_TYPE, start_lesson

    proof_detector_id = (
        (projection.get("evidence") or {}).get("proof_detector_id")
    )

    result = await start_lesson(
        db,
        str(uuid.uuid4()),
        user.user_id,
        PIC_LESSON_TYPE,
        {
            "limit": request.limit,
            "proof_detector_id": proof_detector_id,
        },
    )
    return _raise_pic_lesson_error(result)


@router.get("/pic/session")
async def get_pic_training_session(user: User = Depends(get_current_user)):
    """Return the user's current PIC lesson without exposing another user."""
    await _require_pic_training_user(user)
    from services.teaching_engine import get_pic_piece_safety_lesson

    result = await get_pic_piece_safety_lesson(db, user.user_id)
    return _raise_pic_lesson_error(result)


@router.post("/pic/session/move")
async def submit_pic_training_move(
    request: PICLessonMoveRequest,
    user: User = Depends(get_current_user),
):
    """Grade one move through the canonical teaching dispatcher."""
    await _require_pic_training_user(user)
    owned = await db.learning_sessions.find_one(
        {"session_id": request.session_id, "user_id": user.user_id},
        {"_id": 1},
    )
    if not owned:
        raise HTTPException(status_code=404, detail="Session not found")
    from services.teaching_engine import process_lesson_move

    result = await process_lesson_move(
        db,
        request.session_id,
        request.move,
        interaction_id=request.interaction_id,
    )
    return _raise_pic_lesson_error(result)


@router.post("/pic/session/pause")
async def pause_pic_training_session(
    request: PICLessonPauseRequest,
    user: User = Depends(get_current_user),
):
    """Pause or exit a PIC lesson while preserving its frozen items."""
    await _require_pic_training_user(user)
    owned = await db.learning_sessions.find_one(
        {"session_id": request.session_id, "user_id": user.user_id},
        {"_id": 1},
    )
    if not owned:
        raise HTTPException(status_code=404, detail="Session not found")
    from services.teaching_engine import exit_lesson

    result = await exit_lesson(db, request.session_id, request.choice)
    return _raise_pic_lesson_error(result)


# ==================== PERSONALIZED CURRICULUM TEACHING ====================

@router.post("/personalized/session/start")
async def start_personalized_training_session(
    request: PersonalizedLessonStartRequest,
    user: User = Depends(get_current_user),
):
    await _require_personalized_teaching_user(user)
    from services.teaching_engine import PERSONALIZED_LESSON_TYPE, start_lesson

    result = await start_lesson(
        db,
        str(uuid.uuid4()),
        user.user_id,
        PERSONALIZED_LESSON_TYPE,
        request.model_dump(exclude_none=True),
    )
    return _raise_pic_lesson_error(result)


@router.get("/personalized/session")
async def get_personalized_training_session(
    session_id: Optional[str] = None,
    user: User = Depends(get_current_user),
):
    await _require_personalized_teaching_user(user)
    from services.teaching_engine import get_personalized_lesson

    result = await get_personalized_lesson(db, user.user_id, session_id)
    return _raise_pic_lesson_error(result)


@router.post("/personalized/session/respond")
async def respond_to_personalized_training(
    request: PersonalizedLessonRespondRequest,
    user: User = Depends(get_current_user),
):
    await _require_personalized_teaching_user(user)
    owned = await db.learning_sessions.find_one(
        {"session_id": request.session_id, "user_id": user.user_id},
        {"_id": 1},
    )
    if not owned:
        raise HTTPException(status_code=404, detail="Session not found")
    from services.teaching_engine import process_personalized_move

    result = await process_personalized_move(
        db,
        request.session_id,
        request.move,
        interaction_id=request.interaction_id,
        reason_choice=request.reason_choice,
        reason_component_id=request.reason_component_id,
    )
    return _raise_pic_lesson_error(result)


@router.post("/personalized/session/help")
async def help_with_personalized_training(
    request: PersonalizedLessonHelpRequest,
    user: User = Depends(get_current_user),
):
    await _require_personalized_teaching_user(user)
    from services.teaching_engine import request_personalized_help

    result = await request_personalized_help(
        db,
        user.user_id,
        request.session_id,
        request.action,
        interaction_id=request.interaction_id,
    )
    return _raise_pic_lesson_error(result)


@router.post("/personalized/session/pause")
async def pause_personalized_training(
    request: PersonalizedLessonPauseRequest,
    user: User = Depends(get_current_user),
):
    await _require_personalized_teaching_user(user)
    owned = await db.learning_sessions.find_one(
        {"session_id": request.session_id, "user_id": user.user_id},
        {"_id": 1},
    )
    if not owned:
        raise HTTPException(status_code=404, detail="Session not found")
    from services.teaching_engine import exit_lesson

    result = await exit_lesson(db, request.session_id, request.choice)
    return _raise_pic_lesson_error(result)


@router.get("/personalized/session/{session_id}/evidence")
async def get_personalized_training_evidence(
    session_id: str,
    user: User = Depends(get_current_user),
):
    await _require_personalized_teaching_user(user)
    session = await db.learning_sessions.find_one(
        {
            "session_id": session_id,
            "user_id": user.user_id,
            "lesson_type": "personalized_curriculum",
        },
        {
            "_id": 0,
            "session_id": 1,
            "skill_id": 1,
            "highest_earned_state": 1,
            "events": 1,
        },
    )
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    evidence = []
    for event in session.get("events") or []:
        if event.get("event_type") != "answer_submitted":
            continue
        evidence.append({
            "event_id": event.get("event_id"),
            "occurred_at": event.get("occurred_at"),
            "lesson": event.get("lesson"),
            "attempt": event.get("attempt"),
            "application": event.get("application"),
            "provenance": event.get("provenance"),
            "earned_state": event.get("earned_state"),
        })
    return {
        "session_id": session_id,
        "skill_id": session.get("skill_id"),
        "highest_earned_state": (
            session.get("highest_earned_state") or "learning"
        ),
        "real_game_evidence": "not_measured",
        "retention_evidence": "not_measured",
        "evidence": evidence,
    }


# ==================== HOME REPLAY DIAGNOSTIC ====================

@router.post("/personalized/diagnostic/start")
async def start_home_replay_diagnostic(
    request: HomeDiagnosticStartRequest,
    user: User = Depends(get_current_user),
):
    await _require_home_diagnostic_user(user)
    from services.teaching_engine import PERSONALIZED_LESSON_TYPE, start_lesson

    result = await start_lesson(
        db,
        str(uuid.uuid4()),
        user.user_id,
        PERSONALIZED_LESSON_TYPE,
        {
            "content_kind": "concept",
            "content_id": "piece_safety",
            "mode": "blind_diagnostic",
            "limit": max(2, min(request.limit, 20)),
        },
    )
    return _raise_pic_lesson_error(result)


@router.get("/personalized/diagnostic")
async def get_home_replay_diagnostic(user: User = Depends(get_current_user)):
    await _require_home_diagnostic_user(user)
    session = await db.learning_sessions.find_one(
        {
            "user_id": user.user_id,
            "lesson_type": "personalized_curriculum",
            "delivery_mode": "blind_diagnostic",
        },
        sort=[("updated_at", -1)],
    )
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    from services.teaching_engine import _public_personalized_session

    return _public_personalized_session(session)


async def _owned_home_diagnostic(user: User, session_id: str):
    session = await db.learning_sessions.find_one(
        {
            "session_id": session_id,
            "user_id": user.user_id,
            "delivery_mode": "blind_diagnostic",
        },
        {"_id": 1},
    )
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")


@router.post("/personalized/diagnostic/respond")
async def respond_to_home_replay_diagnostic(
    request: PersonalizedLessonRespondRequest,
    user: User = Depends(get_current_user),
):
    await _require_home_diagnostic_user(user)
    await _owned_home_diagnostic(user, request.session_id)
    from services.teaching_engine import process_personalized_move

    result = await process_personalized_move(
        db,
        request.session_id,
        request.move,
        interaction_id=request.interaction_id,
        reason_choice=request.reason_choice,
        reason_component_id=request.reason_component_id,
    )
    return _raise_pic_lesson_error(result)


@router.post("/personalized/diagnostic/continue")
async def continue_home_replay_diagnostic(
    request: HomeDiagnosticContinueRequest,
    user: User = Depends(get_current_user),
):
    await _require_home_diagnostic_user(user)
    await _owned_home_diagnostic(user, request.session_id)
    from services.teaching_engine import continue_home_diagnostic

    result = await continue_home_diagnostic(
        db,
        user.user_id,
        request.session_id,
        interaction_id=request.interaction_id,
    )
    return _raise_pic_lesson_error(result)


@router.post("/personalized/diagnostic/help")
async def help_with_home_replay_diagnostic(
    request: PersonalizedLessonHelpRequest,
    user: User = Depends(get_current_user),
):
    await _require_home_diagnostic_user(user)
    await _owned_home_diagnostic(user, request.session_id)
    from services.teaching_engine import request_personalized_help

    result = await request_personalized_help(
        db,
        user.user_id,
        request.session_id,
        request.action,
        interaction_id=request.interaction_id,
    )
    return _raise_pic_lesson_error(result)


@router.post("/personalized/diagnostic/pause")
async def pause_home_replay_diagnostic(
    request: PersonalizedLessonPauseRequest,
    user: User = Depends(get_current_user),
):
    await _require_home_diagnostic_user(user)
    await _owned_home_diagnostic(user, request.session_id)
    from services.teaching_engine import exit_lesson

    result = await exit_lesson(db, request.session_id, request.choice)
    return _raise_pic_lesson_error(result)


# ==================== CORE SESSION ENDPOINTS ====================

@router.get("/session")
async def get_training_session_endpoint(user: User = Depends(get_current_user)):
    """
    Get the current training session.
    Returns either:
    - Post-Game Debrief (if user just played a game)
    - Daily Training (cards due for review)
    - All Caught Up (no cards due)
    """
    global db
    session = await get_training_session(db, user.user_id)
    from services.verified_puzzle_runtime import public_puzzle_payload
    return public_puzzle_payload(session or {})


@router.get("/due-cards")
async def get_due_cards_endpoint(user: User = Depends(get_current_user), limit: int = 5):
    """Get cards due for review today."""
    global db
    cards = await get_due_cards(db, user.user_id, limit=limit)
    from services.verified_puzzle_runtime import public_puzzle_payload
    return {
        "cards": [public_puzzle_payload(card) for card in cards],
        "count": len(cards),
    }


@router.get("/card/{card_id}")
async def get_training_card(card_id: str, user: User = Depends(get_current_user)):
    """Get a specific training card."""
    global db
    card = await get_card_by_id(db, card_id, user.user_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    from services.verified_puzzle_runtime import public_puzzle_payload
    return public_puzzle_payload(card)


@router.post("/attempt")
async def record_training_attempt(req: CardAttemptRequest, user: User = Depends(get_current_user)):
    """
    Record an attempt on a training card.
    Updates spaced repetition schedule based on correctness.
    """
    global db
    card = await get_card_by_id(db, req.card_id, user.user_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    next_review = str(card.get("next_review") or "")
    if card.get("last_reviewed") and next_review:
        try:
            due_at = datetime.fromisoformat(next_review.replace("Z", "+00:00"))
            if due_at > datetime.now(timezone.utc):
                raise HTTPException(status_code=409, detail="This card is not due yet")
        except ValueError:
            raise HTTPException(status_code=409, detail="This card needs evidence repair")
    puzzle_id = f"{card.get('game_id')}_m{card.get('move_number')}"
    from services.verified_puzzle_attempt_service import record_verified_puzzle_attempt
    from services.verified_puzzle_runtime import resolve_verified_puzzle
    puzzle = await resolve_verified_puzzle(db, puzzle_id, user_id=user.user_id)
    if not puzzle:
        raise HTTPException(status_code=409, detail="This card needs verified evidence")
    grade = await record_verified_puzzle_attempt(
        db,
        user_id=user.user_id,
        puzzle_id=puzzle_id,
        puzzle=puzzle,
        played_uci=req.played_uci,
        attempt_context="mistake_card",
        submission_id=req.submission_id,
    )
    if grade.get("quality") == "invalid":
        raise HTTPException(status_code=400, detail=grade.get("feedback"))
    result = await record_card_attempt(
        db,
        req.card_id,
        user.user_id,
        bool(grade.get("correct")),
    )
    if result.get("error"):
        raise HTTPException(status_code=404, detail=result["error"])
    return {
        **result,
        "correct": bool(grade.get("correct")),
        "feedback": grade.get("feedback"),
        "best_move_san": grade.get("best_move_san"),
        "best_move_uci": grade.get("best_move_uci"),
        "recovery_credit_awarded": grade.get("recovery_credit_awarded", False),
    }


@router.get("/card/{card_id}/why")
async def get_why_question_for_card(card_id: str, user: User = Depends(get_current_user)):
    """
    Get a Socratic "Why is this move better?" question for a card.
    Used after the user answers correctly to deepen understanding.
    """
    global db
    card = await get_card_by_id(db, card_id, user.user_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    
    why_data = await generate_why_question(db, card)
    return why_data


@router.get("/progress")
async def get_training_progress(user: User = Depends(get_current_user)):
    """Get user's habit mastery progress."""
    global db
    progress = await get_user_habit_progress(db, user.user_id)
    stats = await get_training_stats(db, user.user_id)
    return {
        "habits": progress,
        "stats": stats
    }


@router.post("/set-habit")
async def set_training_habit(req: SetActiveHabitRequest, user: User = Depends(get_current_user)):
    """Manually set the active habit to focus on."""
    global db
    result = await set_active_habit(db, user.user_id, req.habit_key)
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.get("/habits")
async def get_available_habits(user: User = Depends(get_current_user)):
    """Get all available habit definitions."""
    return {"habits": HABIT_DEFINITIONS}


# ==================== PRESCRIBED TRAINING ====================

@router.get("/prescribed/{weakness}")
async def get_prescribed_training_endpoint(
    weakness: str,
    num_puzzles: int = 10,
    user: User = Depends(get_current_user)
):
    """
    Get puzzles prescribed for a specific weakness.

    Pass `current` to use whatever the curriculum brain has set as
    coach_memory.learning.current_focus (keeps every screen aligned).

    This is the IMPROVEMENT engine:
    - Takes diagnosed weakness (e.g., "missed_threat")
    - Returns puzzles with COACHING context
    - Includes puzzles from user's own games!
    """
    global db
    from services.coaching_puzzle_service import CoachingPuzzleService
    from services.focus_bridge import get_active_focus_bundle

    # Read the canonical focus even when the URL contains its explicit topic;
    # Home/Training links use `/piece_safety`, while older callers use
    # `/current`. Both must carry the same exact detector identity.
    active_focus = await get_active_focus_bundle(db, user.user_id)
    resolved_focus = None
    if weakness in ("current", "auto", "focus"):
        resolved_focus = active_focus
        if resolved_focus and resolved_focus.get("topic_key"):
            weakness = resolved_focus["topic_key"]
        else:
            # No focus known yet — safe default for beginners
            weakness = "piece_safety"
    elif active_focus and active_focus.get("topic_key") == weakness:
        resolved_focus = active_focus

    puzzle_service = CoachingPuzzleService(db)

    # Auto-backfill community_puzzles from user's own games if they have none
    # yet. This used to only fire on /pattern-puzzles but since the training
    # surface consolidated, it needs to be here too. Safe to run on every
    # call — cheap no-op when puzzles already exist.
    try:
        from services.puzzle_extraction_service import backfill_puzzles_for_user
        own_count = await db.community_puzzles.count_documents(
            {"shared_by": user.user_id}
        )
        if own_count == 0:
            await backfill_puzzles_for_user(db, user.user_id)
    except Exception as _backfill_err:
        # Non-fatal: if backfill fails, still serve whatever puzzles we can.
        logger.debug(f"Auto-backfill skipped for {user.user_id}: {_backfill_err}")

    # Get user's rating for difficulty calibration
    from services.rating_resolver import get_coaching_rating
    user_rating = await get_coaching_rating(db, user.user_id)

    # Set rating range for puzzles (user rating +/- 200)
    rating_range = (max(600, user_rating - 200), user_rating + 200)

    # Personalization signals — fed into puzzle framing (not filtering).
    # Same signals the live coach uses; reused here so framing is consistent.
    _strong = set()
    _style = {}
    try:
        from services.player_performance import get_strong_openings, get_player_style
        _strong = await get_strong_openings(db, user.user_id)
        _style = await get_player_style(db, user.user_id)
    except Exception:
        pass

    result = await puzzle_service.get_prescribed_training(
        user_id=user.user_id,
        weakness_pattern=weakness,
        num_puzzles=num_puzzles,
        rating_range=rating_range,
        strong_openings=_strong,
        player_style=_style,
        required_quality_id=(
            resolved_focus.get("detector_quality_id") if resolved_focus else None
        ),
    )

    if resolved_focus:
        result["active_focus"] = resolved_focus

    from services.verified_puzzle_runtime import public_puzzle_payload
    result["puzzles"] = [
        public_puzzle_payload(puzzle) for puzzle in result.get("puzzles") or []
    ]

    return result


@router.post("/puzzle-attempt")
async def record_puzzle_attempt_endpoint(
    request: Dict = Body(...),
    user: User = Depends(get_current_user)
):
    """Record an attempt on a training puzzle."""
    global db
    from datetime import datetime, timezone

    puzzle_id = request.get("puzzle_id")
    played_uci = (request.get("played_uci") or "").strip()
    time_taken_ms = request.get("time_taken_ms")
    moves_tried = request.get("moves_tried", [])
    if not puzzle_id or not played_uci:
        raise HTTPException(status_code=400, detail="puzzle_id and played_uci are required")
    from services.verified_puzzle_attempt_service import record_verified_puzzle_attempt
    from services.verified_puzzle_runtime import resolve_verified_puzzle
    resolved = await resolve_verified_puzzle(db, puzzle_id, user_id=user.user_id)
    if not resolved:
        raise HTTPException(status_code=404, detail="puzzle is not ready for training")
    server_grade = await record_verified_puzzle_attempt(
        db,
        user_id=user.user_id,
        puzzle_id=puzzle_id,
        puzzle=resolved,
        played_uci=played_uci,
        time_taken_ms=time_taken_ms,
        moves_tried=moves_tried,
        # Context is server-owned provenance, not a client-selected identity
        # namespace that could be varied to bypass retry deduplication.
        attempt_context="training",
        submission_id=request.get("submission_id"),
    )
    if server_grade.get("quality") == "invalid":
        raise HTTPException(status_code=400, detail=server_grade.get("feedback"))
    correct = bool(server_grade.get("correct"))
    quality = server_grade.get("quality")

    # A correct solve is recovery credit — refresh the persisted decay state
    # immediately so training visibly moves prioritization (Lab pick, and any
    # consumer of db.user_pattern_decay) without waiting for the next game
    # analysis. Fail-open: recording the attempt never depends on this.
    if server_grade.get("recovery_credit_claimed_now"):
        try:
            from services.pattern_decay_service import refresh_user_pattern_decay
            await refresh_user_pattern_decay(db, user.user_id)
        except Exception as decay_err:
            import logging
            logging.getLogger(__name__).warning(
                f"decay refresh after puzzle solve failed (non-fatal): {decay_err}")

    return {
        "success": True,
        "correct": correct,
        "quality": quality,
        "recovery_credit_awarded": server_grade.get("recovery_credit_awarded", False),
        "message": "Attempt recorded",
        # Released only after a real server-graded attempt. No answer or proof
        # material is present in the pre-attempt puzzle payload.
        "best_move_san": server_grade.get("best_move_san"),
        "best_move_uci": server_grade.get("best_move_uci"),
        "feedback": server_grade.get("feedback"),
        "coaching_feedback": server_grade.get("coaching_feedback"),
        "pattern_type": server_grade.get("pattern_type"),
    }


@router.post("/evaluate-puzzle-move")
async def evaluate_puzzle_move_endpoint(
    request: Dict = Body(...),
    user: User = Depends(get_current_user)
):
    """Grade a move from the puzzle's frozen verified answer set.

    The client supplies only puzzle_id + played_uci. FEN, label, answer and
    correctness are resolved server-side; no Stockfish or LLM runs here.
    """
    puzzle_id = (request.get("puzzle_id") or "").strip()
    played_uci = (request.get("played_uci") or "").strip()
    if not puzzle_id or not played_uci:
        raise HTTPException(status_code=400, detail="puzzle_id and played_uci are required")

    from services.verified_puzzle_runtime import (
        grade_resolved_puzzle,
        resolve_verified_puzzle,
    )
    puzzle = await resolve_verified_puzzle(db, puzzle_id, user_id=user.user_id)
    if not puzzle:
        raise HTTPException(status_code=404, detail="puzzle is not ready for training")
    return grade_resolved_puzzle(puzzle, played_uci)


@router.post("/reveal-puzzle")
async def reveal_puzzle_endpoint(
    request: Dict = Body(...),
    user: User = Depends(get_current_user),
):
    """Reveal only after an explicit user action; a reveal earns no credit."""
    puzzle_id = (request.get("puzzle_id") or "").strip()
    if not puzzle_id:
        raise HTTPException(status_code=400, detail="puzzle_id is required")
    from datetime import datetime, timezone
    import chess
    from services.verified_puzzle_runtime import resolve_verified_puzzle

    puzzle = await resolve_verified_puzzle(db, puzzle_id, user_id=user.user_id)
    if not puzzle:
        raise HTTPException(status_code=404, detail="puzzle is not ready for training")
    verdict = puzzle.get("verified_admission") or {}
    accepted = tuple(verdict.get("acceptable_moves_uci") or ())
    primary = puzzle.get("best_move_uci") or (accepted[0] if accepted else "")
    try:
        board = chess.Board(puzzle.get("fen"))
        move = chess.Move.from_uci(primary)
        if move not in board.legal_moves:
            raise ValueError("illegal answer")
        san = board.san(move)
    except (TypeError, ValueError):
        raise HTTPException(status_code=409, detail="This puzzle needs evidence repair")
    await db.puzzle_reveals.insert_one({
        "user_id": user.user_id,
        "puzzle_id": puzzle_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    return {"best_move_uci": primary, "best_move_san": san}


# ==================== ONE-MOVE BLUNDERS ====================

@router.get("/one-move-blunders")
async def get_one_move_blunders(user: User = Depends(get_current_user)):
    """
    Get one-move blunders as training puzzles.
    These are positions where you made a move that allowed immediate tactics.
    """
    global db
    
    # Get all analyzed games with stockfish data
    analyses = await db.game_analyses.find(
        {"user_id": user.user_id},
        {"_id": 0, "game_id": 1, "stockfish_analysis": 1}
    ).to_list(100)
    
    # Get solved puzzle IDs
    solved = await db.puzzle_attempts.find(
        {"user_id": user.user_id, "correct": True},
        {"puzzle_id": 1}
    ).to_list(500)
    solved_puzzle_ids = {s["puzzle_id"] for s in solved}
    
    one_move_blunders = []
    for analysis in analyses:
        source_game = await db.games.find_one(
            {"game_id": analysis.get("game_id"), "user_id": user.user_id},
            {"_id": 0},
        )
        if not source_game:
            continue
        sf = analysis.get("stockfish_analysis", {})
        evals = sf.get("move_evaluations", [])
        
        for m in evals:
            # Looking for moves where opponent has immediate tactic after
            cp_loss = abs(m.get("cp_loss", 0))
            pv = m.get("pv_after_best", [])
            
            # One-move blunder = big loss where opponent's reply is decisive
            if cp_loss >= 200 and len(pv) >= 1:
                from services.verified_puzzle_admission import AdmissionStatus
                from services.verified_puzzle_builder import build_imported_game_verdict
                verdict = build_imported_game_verdict(
                    game=source_game,
                    move_evaluation=m,
                    broad_category=m.get("cognitive_gap") or None,
                )
                if verdict.status == AdmissionStatus.QUARANTINE:
                    continue
                puzzle_id = f"{analysis['game_id']}_m{m.get('move_number')}"
                
                # Skip already solved
                if puzzle_id in solved_puzzle_ids:
                    continue
                
                one_move_blunders.append({
                    "puzzle_id": puzzle_id,
                    "game_id": analysis["game_id"],
                    "fen": m.get("fen_before", ""),
                    "your_move": m.get("move", ""),
                    "solution": [m.get("best_move_uci") or m.get("best_move", "")],
                    "solution_san": m.get("best_move_san") or m.get("best_move", ""),
                    "cp_loss": cp_loss,
                    "move_number": m.get("move_number"),
                    "source": "your_game",
                    "pattern_type": verdict.broad_category or "calculation_depth",
                    "verified_admission": verdict.to_document(),
                })
    
    # Sort by cp_loss (worst blunders first)
    one_move_blunders.sort(key=lambda x: abs(x["cp_loss"]), reverse=True)
    
    from services.verified_puzzle_runtime import public_puzzle_payload
    return {
        "puzzles": [public_puzzle_payload(p) for p in one_move_blunders[:30]],
        "total": len(one_move_blunders),
        "solved_count": len(solved_puzzle_ids),
        "source": "stockfish_analysis"
    }


# ==================== DATA-DRIVEN TRAINING ====================

@router.get("/data-driven")
async def get_data_driven_training(user: User = Depends(get_current_user)):
    """
    Get personalized training based on user's actual game weaknesses.
    This analyzes recent games to find recurring patterns.
    """
    global db
    
    # Get recent analyses
    analyses = await db.game_analyses.find(
        {"user_id": user.user_id},
        {"_id": 0}
    ).sort("created_at", -1).limit(20).to_list(20)

    # Aggregate weakness patterns from real per-move cognitive_gap tags —
    # the old logic here read analysis["blunders"], a top-level array field
    # never populated on any real document (same bug fixed 2026-07-22 in
    # mission_generation_service.py), so this always returned nothing.
    from mission_generation_service import build_pattern_stats_from_analyses
    pattern_stats = build_pattern_stats_from_analyses(analyses)
    weakness_counts = {cat: stats["repeat_count_14d"] for cat, stats in pattern_stats.items()}

    # Sort by frequency
    sorted_weaknesses = sorted(
        weakness_counts.items(),
        key=lambda x: x[1],
        reverse=True
    )
    
    # Build training recommendations
    recommendations = []
    for weakness, count in sorted_weaknesses[:5]:
        recommendations.append({
            "weakness": weakness,
            "occurrences": count,
            "training_type": "prescribed",
            "priority": "high" if count >= 3 else "medium"
        })
    
    return {
        "recommendations": recommendations,
        "games_analyzed": len(analyses),
        "total_weaknesses_found": len(weakness_counts)
    }


# ==================== WEEKLY PLAN ====================

@router.get("/weekly-plan")
async def get_weekly_training_plan(user: User = Depends(get_current_user)):
    """
    Get personalized weekly training plan based on weaknesses.
    """
    global db
    
    # Get user's top weaknesses
    user_doc = await db.users.find_one({"user_id": user.user_id})
    weaknesses = user_doc.get("top_weaknesses", []) if user_doc else []
    
    # Get recent training activity
    recent_attempts = await db.puzzle_attempts.find(
        {"user_id": user.user_id},
        {"_id": 0}
    ).sort("created_at", -1).limit(50).to_list(50)
    
    # Calculate accuracy per weakness
    weakness_stats = {}
    for attempt in recent_attempts:
        weakness = attempt.get("weakness_type", "unknown")
        if weakness not in weakness_stats:
            weakness_stats[weakness] = {"correct": 0, "total": 0}
        weakness_stats[weakness]["total"] += 1
        if attempt.get("correct"):
            weakness_stats[weakness]["correct"] += 1
    
    # Build weekly plan
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    plan = []
    
    for i, day in enumerate(days):
        if i < len(weaknesses):
            weakness = weaknesses[i % len(weaknesses)] if weaknesses else "tactics"
            stats = weakness_stats.get(weakness, {"correct": 0, "total": 0})
            accuracy = (stats["correct"] / stats["total"] * 100) if stats["total"] > 0 else 0
            
            plan.append({
                "day": day,
                "focus": weakness,
                "puzzles_target": 5,
                "current_accuracy": round(accuracy, 1),
                "completed": False
            })
        else:
            plan.append({
                "day": day,
                "focus": "review",
                "puzzles_target": 3,
                "completed": False
            })
    
    return {
        "plan": plan,
        "weaknesses": weaknesses,
        "stats": weakness_stats
    }
