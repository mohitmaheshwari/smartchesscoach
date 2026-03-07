"""
Reflect Routes
==============

Handles the Reflection Engine - post-game analysis and learning.

Core Endpoints:
- GET /reflect/pending - Get games needing reflection
- GET /reflect/pending/count - Get count for badge
- GET /reflect/game/{game_id}/moments - Get critical moments for reflection
- POST /reflect/submit - Submit reflection for a moment
- POST /reflect/game/{game_id}/complete - Mark game as reflected
- POST /reflect/moment/contextual-tags - Get AI-generated contextual tags
- POST /reflect/explain-moment - Get coach explanation for a moment

V1 Engine (Deterministic):
- GET /reflect/v1/profile - Get user's adaptive reflection profile
- POST /reflect/v1/quick-tags - Generate rating-adaptive quick tags
- POST /reflect/v1/submit - Submit V1 reflection session
- GET /reflect/v1/post-loss/{game_id} - Post-loss recovery screen
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timezone
import uuid
import logging

logger = logging.getLogger(__name__)

# Create router for reflect endpoints
router = APIRouter(prefix="/reflect", tags=["Reflect"])

# Database reference - will be set by server.py
db = None

def set_db(database):
    """Set the database reference for reflect routes"""
    global db
    db = database


# Import User model and get_current_user from auth routes
from routes.auth import User, get_current_user

# Import reflection services (note: these are in the backend root, not services/)
from reflect_service import (
    get_games_needing_reflection,
    get_pending_reflection_count,
    get_game_moments,
    process_reflection,
    mark_game_reflected,
    generate_contextual_tags
)

from position_analysis_service import (
    generate_verified_insight,
    build_llm_prompt_with_facts,
    validate_llm_output
)

# Reflection Engine V1 imports (scattered across modules)
from reflect_constants import (
    REFLECT_RULES_VERSION,
    RewardEventType,
    get_reflection_style,
    get_rating_band,
    INTENT_BY_RATING,
    INTENT_LABELS,
)
from quick_tag_registry import generate_quick_tags
from awareness_gap_rules import evaluate_awareness_gap
from adaptive_profile_engine import get_adaptive_profile, get_adaptive_profile_sync
from reward_message_service import get_reward_message, get_post_loss_message


# ==================== MODELS ====================

class ReflectionSubmission(BaseModel):
    game_id: str
    moment_index: int
    moment_fen: str
    user_thought: str
    user_move: str
    best_move: str
    eval_change: float = 0.0
    move_number: Optional[int] = None


class ContextualTagsRequest(BaseModel):
    """Request for generating contextual quick-tags based on position."""
    fen: str
    user_move: str
    best_move: str
    eval_change: float = 0.0


class MomentExplanationRequest(BaseModel):
    fen: str
    user_move: str
    best_move: str
    eval_change: float = 0.0
    type: str = "mistake"


class ReflectEngineTagsRequest(BaseModel):
    """Request for V1 quick tag generation"""
    fen: str
    user_move: str
    best_move: str
    mistake_category: str
    cp_loss: float = 0.0
    time_remaining_sec: Optional[int] = None
    move_number: int = 0


class ReflectSessionSubmitRequest(BaseModel):
    """Request to complete a reflection session"""
    game_id: str
    move_index: int
    fen: str
    user_move: str
    best_move: str
    mistake_category: str
    intent: str
    intent_confidence: str
    selected_quick_tags: List[str]
    auto_tag_candidates_shown: List[str] = []
    free_text: Optional[str] = ""
    cp_loss: float = 0.0
    time_remaining_sec: Optional[int] = None
    move_number: int = 0
    completed_in_seconds: int = 0
    game_ended_at: Optional[str] = None


# ==================== CORE ENDPOINTS ====================

@router.get("/pending")
async def get_pending_reflections(user: User = Depends(get_current_user)):
    """Get games that need reflection - most recent first."""
    global db
    games = await get_games_needing_reflection(db, user.user_id, limit=5)
    return {"games": games}


@router.get("/pending/count")
async def get_reflection_count(user: User = Depends(get_current_user)):
    """Get count of games needing reflection for badge display."""
    global db
    count = await get_pending_reflection_count(db, user.user_id)
    return {"count": count}


@router.get("/game/{game_id}/moments")
async def get_reflection_moments(game_id: str, user: User = Depends(get_current_user)):
    """Get critical moments from a game for reflection."""
    global db
    moments = await get_game_moments(db, user.user_id, game_id)
    return {"moments": moments}


@router.post("/submit")
async def submit_reflection(data: ReflectionSubmission, user: User = Depends(get_current_user)):
    """Submit a reflection for a critical moment."""
    global db
    result = await process_reflection(
        db,
        user.user_id,
        data.game_id,
        data.moment_index,
        data.moment_fen,
        data.user_thought,
        data.user_move,
        data.best_move,
        data.eval_change,
        data.move_number
    )
    return result


@router.post("/game/{game_id}/complete")
async def complete_game_reflection(game_id: str, user: User = Depends(get_current_user)):
    """Mark a game as fully reflected on."""
    global db
    result = await mark_game_reflected(db, user.user_id, game_id)
    return result


@router.post("/moment/contextual-tags")
async def get_contextual_tags_endpoint(data: ContextualTagsRequest, user: User = Depends(get_current_user)):
    """
    Generate contextual quick-tag options based on the actual chess position.
    Uses verified position analysis to infer what the user might have been thinking.
    """
    result = generate_contextual_tags(
        data.fen,
        data.user_move,
        data.best_move,
        data.eval_change
    )
    return result


@router.post("/explain-moment")
async def explain_moment(data: MomentExplanationRequest, user: User = Depends(get_current_user)):
    """
    Get a coach-style explanation of what happened at this moment.
    Uses VERIFIED position analysis - no LLM hallucinations.
    """
    from llm_service import call_llm
    
    try:
        # Step 1: Generate verified insights from actual position analysis
        verified = generate_verified_insight(
            data.fen,
            data.user_move,
            data.best_move,
            data.eval_change
        )
        
        # Step 2: Get LLM to elaborate on verified facts (optional enhancement)
        prompt = build_llm_prompt_with_facts(
            data.fen,
            data.user_move,
            data.best_move,
            data.eval_change
        )
        
        try:
            response = await call_llm(
                system_message="You are a supportive chess coach. ONLY use the verified facts provided. Never make up piece locations.",
                user_message=prompt,
                model="gpt-4o-mini"
            )
            
            import json
            response_clean = response.strip()
            if response_clean.startswith("```json"):
                response_clean = response_clean[7:]
            if response_clean.startswith("```"):
                response_clean = response_clean[3:]
            if response_clean.endswith("```"):
                response_clean = response_clean[:-3]
            
            llm_result = json.loads(response_clean)
            
            # Step 3: Validate LLM output against position facts
            is_valid, errors = validate_llm_output(
                json.dumps(llm_result), 
                verified["position_facts"]
            )
            
            if is_valid:
                return {
                    "impact": llm_result.get("impact", verified["verified_impact"]),
                    "better_plan": llm_result.get("better_plan", verified["verified_better_plan"]),
                    "verified": True
                }
            else:
                logger.warning(f"LLM validation failed: {errors}")
                return {
                    "impact": verified["verified_impact"],
                    "better_plan": verified["verified_better_plan"],
                    "verified": True,
                    "fallback": True
                }
                
        except Exception as llm_error:
            logger.error(f"LLM error: {llm_error}")
            return {
                "impact": verified["verified_impact"],
                "better_plan": verified["verified_better_plan"],
                "verified": True,
                "fallback": True
            }
            
    except Exception as e:
        logger.error(f"Error analyzing moment: {e}")
        return {
            "impact": f"Your move {data.user_move} wasn't the best in this position.",
            "better_plan": f"The move {data.best_move} was stronger here.",
            "error": True
        }


# ==================== V1 ENGINE ENDPOINTS ====================

@router.get("/v1/profile")
async def get_reflection_profile(user: User = Depends(get_current_user)):
    """
    Get user's adaptive reflection profile.
    Frontend uses this to configure UX - no hardcoded values in React.
    """
    global db
    
    # Get user's rating
    user_doc = await db.users.find_one({"user_id": user.user_id})
    rating = user_doc.get("assessed_rating", 1200) if user_doc else 1200
    
    profile = await get_adaptive_profile(user.user_id, rating, db)
    profile["rule_version"] = REFLECT_RULES_VERSION
    
    # Add rating-aware reflection style
    rating_band = get_rating_band(rating)
    reflection_style = get_reflection_style(rating)
    
    profile["reflection_style"] = reflection_style.value
    profile["rating_band"] = rating_band.value
    profile["rating"] = rating
    
    # Get rating-appropriate intent options
    intent_list = INTENT_BY_RATING.get(rating_band, INTENT_BY_RATING[get_rating_band(1200)])
    profile["intent_options"] = [
        {"value": i.value, "label": INTENT_LABELS.get(i, i.value)}
        for i in intent_list
    ]
    
    # Add plan-based questions for 1000+ players
    if rating >= 1000:
        profile["plan_questions"] = [
            "What was your plan in this position?",
            "What did you think your opponent would do?",
            "What candidate moves did you consider?",
        ]
        profile["show_plan_input"] = True
        profile["allow_board_moves"] = rating >= 1300
    else:
        profile["plan_questions"] = []
        profile["show_plan_input"] = False
        profile["allow_board_moves"] = False
    
    return profile


@router.post("/v1/quick-tags")
async def get_quick_tags_v1(data: ReflectEngineTagsRequest, user: User = Depends(get_current_user)):
    """
    Generate quick tags using the V1 deterministic engine.
    Tags are config-driven, predicate-backed, and rating-adaptive.
    """
    global db
    
    user_doc = await db.users.find_one({"user_id": user.user_id})
    rating = user_doc.get("assessed_rating", 1200) if user_doc else 1200
    
    result = generate_quick_tags(
        fen_before=data.fen,
        user_move=data.user_move,
        best_move=data.best_move,
        mistake_category=data.mistake_category,
        rating=rating,
        cp_loss=data.cp_loss,
        time_remaining_sec=data.time_remaining_sec,
        move_number=data.move_number,
    )
    
    profile = get_adaptive_profile_sync(rating)
    result["intent_options"] = profile["intent_options"]
    result["confidence_options"] = profile["confidence_options"]
    result["max_quick_tags"] = profile["max_quick_tags"]
    result["friction_budget_taps"] = profile["friction_budget_taps"]
    result["rule_version"] = REFLECT_RULES_VERSION
    
    return result


@router.post("/v1/submit")
async def submit_reflection_v1(data: ReflectSessionSubmitRequest, user: User = Depends(get_current_user)):
    """
    Submit a completed reflection session.
    Stores structured data, computes awareness gap, returns reward.
    """
    global db
    
    user_doc = await db.users.find_one({"user_id": user.user_id})
    rating = user_doc.get("assessed_rating", 1200) if user_doc else 1200
    
    # Compute awareness gap
    awareness_result = evaluate_awareness_gap(
        fen_before=data.fen,
        user_move=data.user_move,
        best_move=data.best_move,
        intent=data.intent,
        confidence=data.intent_confidence,
        selected_tags=data.selected_quick_tags,
        mistake_category=data.mistake_category,
        rating=rating,
        cp_loss=data.cp_loss,
        time_remaining_sec=data.time_remaining_sec,
        move_number=data.move_number,
    )
    
    # Build reflection session document
    reflection_id = f"r_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc)
    
    # Calculate freshness
    is_fresh = False
    hours_since_game = None
    if data.game_ended_at:
        try:
            game_time = datetime.fromisoformat(data.game_ended_at.replace("Z", "+00:00"))
            hours_since_game = (now - game_time).total_seconds() / 3600
            is_fresh = hours_since_game < 12
        except:
            pass
    
    reflection_doc = {
        "reflection_id": reflection_id,
        "user_id": user.user_id,
        "game_id": data.game_id,
        "move_index": data.move_index,
        "mistake_category": data.mistake_category,
        "mistake_category_version": "v1",
        "intent": data.intent,
        "intent_confidence": data.intent_confidence,
        "selected_quick_tags": data.selected_quick_tags,
        "auto_tag_candidates_shown": data.auto_tag_candidates_shown,
        "awareness_gap_type": awareness_result["gap_type"],
        "awareness_gap_reason_codes": awareness_result["reason_codes"],
        "awareness_gap_rule_id": awareness_result.get("rule_id"),
        "free_text": data.free_text or "",
        "completed_in_seconds": data.completed_in_seconds,
        "is_fresh": is_fresh,
        "hours_since_game": hours_since_game,
        "rule_version": REFLECT_RULES_VERSION,
        "created_at": now.isoformat(),
        "fen": data.fen,
        "user_move": data.user_move,
        "best_move": data.best_move,
        "cp_loss": data.cp_loss,
    }
    
    # Store reflection
    await db.reflection_sessions.insert_one(reflection_doc)
    
    # Also store in reflections collection for moment filtering
    await db.reflections.insert_one({
        "user_id": user.user_id,
        "game_id": data.game_id,
        "move_number": data.move_number,
        "moment_fen": data.fen,
        "reflection_id": reflection_id,
        "created_at": now.isoformat()
    })
    
    # Get reward message
    reward_event = RewardEventType.REFLECTION_COMPLETE
    if is_fresh and data.completed_in_seconds < 30:
        reward_event = RewardEventType.REFLECTION_CAPTURED_FAST
    elif data.intent_confidence == "guessing" and "not_sure" in data.selected_quick_tags:
        reward_event = RewardEventType.REFLECTION_HONEST_NOT_SURE
    elif awareness_result["gap_type"] == "confidence_gap":
        reward_event = RewardEventType.REFLECTION_CONFIDENCE_INSIGHT
    
    recent = await db.reward_events.find(
        {"user_id": user.user_id}
    ).sort("created_at", -1).limit(10).to_list(10)
    recent_ids = [r.get("message_id") for r in recent if r.get("message_id")]
    
    reward_message = get_reward_message(
        event_type=reward_event,
        rating=rating,
        context={"focus_label": awareness_result.get("focus_recommendation", "")},
        recent_message_ids=recent_ids,
    )
    
    # Store reward event
    if reward_message:
        await db.reward_events.insert_one({
            "event_id": f"e_{uuid.uuid4().hex[:12]}",
            "user_id": user.user_id,
            "event_type": reward_event.value,
            "source": "reflection",
            "payload": {"reflection_id": reflection_id, "gap_type": awareness_result["gap_type"]},
            "message_id": reward_message["message_id"],
            "created_at": now.isoformat(),
            "seen": False,
        })
    
    next_actions = [{"type": "next_moment", "label": "Next moment"}]
    if awareness_result.get("focus_recommendation"):
        next_actions.insert(0, {
            "type": "start_mission",
            "label": f"Train: {awareness_result['focus_recommendation']}",
            "focus": awareness_result["focus_recommendation"],
        })
    
    return {
        "reflection_status": "completed",
        "reflection_id": reflection_id,
        "awareness_result": {
            "type": awareness_result["gap_type"],
            "headline": awareness_result["headline"],
            "focus_recommendation": awareness_result.get("focus_recommendation"),
        },
        "coach_message": reward_message["text"] if reward_message else "Good. Reflection captured.",
        "next_actions": next_actions,
        "rule_version": REFLECT_RULES_VERSION,
        "completed_in_seconds": data.completed_in_seconds,
        "is_fresh": is_fresh,
        "freshness_badge": "Fresh Memory" if is_fresh else None,
    }


@router.get("/v1/post-loss/{game_id}")
async def get_post_loss_recovery(game_id: str, user: User = Depends(get_current_user)):
    """
    Get post-loss recovery screen data.
    Shows after a loss to convert pain into training.
    """
    global db
    from recurring_pattern_service import compute_recurring_pattern_context
    
    game = await db.games.find_one({"game_id": game_id, "user_id": user.user_id})
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    
    analysis = await db.game_analyses.find_one({"game_id": game_id})
    if not analysis:
        raise HTTPException(status_code=404, detail="Game not analyzed yet")
    
    user_doc = await db.users.find_one({"user_id": user.user_id})
    rating = user_doc.get("assessed_rating", 1200) if user_doc else 1200
    
    blunders = analysis.get("blunders", [])
    mistakes = analysis.get("mistakes", [])
    stockfish_eval = analysis.get("stockfish_analysis", {}).get("move_evaluations", [])
    
    main_issue = "Critical position focus"
    critical_moment = None
    main_category = None
    
    # Compute recurring pattern context
    recurring_pattern = await compute_recurring_pattern_context(
        db, user.user_id, game_id, stockfish_eval, blunders
    )
    
    # Find main issue
    if blunders:
        categories = [b.get("mistake_category", "unknown") for b in blunders if b.get("mistake_category")]
        if categories:
            from collections import Counter
            main_category = Counter(categories).most_common(1)[0][0]
            main_issue = {
                "ignored_opponent_forcing": "Opponent Threat Awareness",
                "missed_forcing_move": "Forcing Move Awareness",
                "phantom_threat": "Threat Prioritization",
                "advantage_mismanagement": "Advantage Conversion",
                "critical_moment_drift": "Critical Position Focus",
                "structural_misjudgment": "Pawn Structure Judgment",
            }.get(main_category, main_category.replace("_", " ").title())
        
        worst_blunder = max(blunders, key=lambda b: abs(b.get("eval_change", 0)))
        critical_moment = {
            "fen": worst_blunder.get("fen"),
            "user_move": worst_blunder.get("user_move"),
            "best_move": worst_blunder.get("best_move"),
            "eval_change": worst_blunder.get("eval_change"),
            "move_number": worst_blunder.get("move_number"),
        }
    elif mistakes:
        worst_mistake = max(mistakes, key=lambda m: abs(m.get("eval_change", 0)))
        critical_moment = {
            "fen": worst_mistake.get("fen"),
            "user_move": worst_mistake.get("user_move"),
            "best_move": worst_mistake.get("best_move"),
            "eval_change": worst_mistake.get("eval_change"),
            "move_number": worst_mistake.get("move_number"),
        }
    elif stockfish_eval:
        for move in stockfish_eval:
            eval_type = move.get("evaluation")
            if hasattr(eval_type, 'value'):
                eval_type = eval_type.value
            if eval_type in ["blunder", "mistake"]:
                critical_moment = {
                    "fen": move.get("fen"),
                    "user_move": move.get("san"),
                    "best_move": move.get("best_move"),
                    "eval_change": move.get("eval_delta"),
                    "move_number": move.get("move_number"),
                }
                break
    
    profile = get_adaptive_profile_sync(rating)
    minutes = profile["mission_minutes_target"]
    message = get_post_loss_message(rating, main_issue, minutes)
    
    return {
        "game_id": game_id,
        "result": game.get("result", "loss"),
        "opponent_name": game.get("opponent_name", "Opponent"),
        "user_color": game.get("user_color", "white"),
        "main_issue": main_issue,
        "headline": message.get("headline", "Let's fix this moment."),
        "estimated_minutes": minutes,
        "critical_moment": critical_moment,
        "has_pending_reflection": len(blunders) + len(mistakes) > 0,
        "blunder_count": len(blunders),
        "mistake_count": len(mistakes),
        "recurring_pattern": recurring_pattern,
    }
