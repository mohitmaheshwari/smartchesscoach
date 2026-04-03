from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, Request, Body
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta
import logging, uuid

router = APIRouter(tags=["Coach Advanced"])
db = None
call_llm_fn = None

def set_db(database):
    global db
    db = database

def set_llm(llm_fn):
    global call_llm_fn
    call_llm_fn = llm_fn

from routes.auth import get_current_user, User

logger = logging.getLogger(__name__)


# ==================== RICH COACH AUDIT ====================

@router.get("/coach/rich-audit/{game_id}")
async def get_rich_coach_audit(game_id: str, user: User = Depends(get_current_user)):
    """
    Get a comprehensive, coach-like audit of a game.

    Combines ALL available data:
    - Game analysis (Stockfish)
    - Cognitive gap history (from reflections)
    - Pattern recurrence data
    - Skill trends
    - Historical baseline comparison

    Returns a rich narrative with specific insights and a targeted plan.
    """
    from rich_coach_audit_service import generate_rich_coach_audit

    return await generate_rich_coach_audit(db, user.user_id, game_id)


@router.get("/coach/rich-audit-latest")
async def get_latest_rich_audit(user: User = Depends(get_current_user)):
    """
    Get rich coach audit for the user's most recently played game.
    """
    from rich_coach_audit_service import generate_rich_coach_audit

    # Get the latest game
    latest_game = await db.games.find_one(
        {"user_id": user.user_id},
        {"_id": 0, "game_id": 1}
    )

    if not latest_game:
        return {"error": "No games found", "has_audit": False}

    return await generate_rich_coach_audit(db, user.user_id, latest_game["game_id"])


# ==================== REWARD EVENT FEED ====================

@router.get("/rewards/feed")
async def get_reward_feed(limit: int = 20, user: User = Depends(get_current_user)):
    """
    Get user's recent reward events.
    Used for reward feed/history display.
    """
    events = await db.reward_events.find(
        {"user_id": user.user_id}
    ).sort("created_at", -1).limit(limit).to_list(limit)

    # Clean up for response
    result = []
    for event in events:
        result.append({
            "event_id": event.get("event_id"),
            "event_type": event.get("event_type"),
            "source": event.get("source"),
            "message_id": event.get("message_id"),
            "created_at": event.get("created_at"),
            "seen": event.get("seen", False),
        })

    # Count unseen
    unseen_count = sum(1 for e in result if not e["seen"])

    return {
        "events": result,
        "unseen_count": unseen_count,
        "total": len(result),
    }

@router.post("/rewards/mark-seen")
async def mark_rewards_seen(user: User = Depends(get_current_user)):
    """Mark all reward events as seen."""
    await db.reward_events.update_many(
        {"user_id": user.user_id, "seen": False},
        {"$set": {"seen": True}}
    )
    return {"status": "ok"}

@router.get("/rewards/stats")
async def get_reward_stats(user: User = Depends(get_current_user)):
    """
    Get reward statistics for the user.
    Used for weekly proof card and progress display.
    """
    # Get reflections for stats
    reflections = await db.reflection_sessions.find(
        {"user_id": user.user_id}
    ).sort("created_at", -1).limit(50).to_list(50)

    total_reflections = len(reflections)
    fresh_reflections = sum(1 for r in reflections if r.get("is_fresh"))
    avg_completion_time = 0
    if reflections:
        times = [r.get("completed_in_seconds", 0) for r in reflections if r.get("completed_in_seconds", 0) > 0]
        if times:
            avg_completion_time = sum(times) / len(times)

    # Intent distribution
    intent_counts = {}
    for r in reflections:
        intent = r.get("intent", "unknown")
        intent_counts[intent] = intent_counts.get(intent, 0) + 1

    # Tag usage
    tag_usage = {}
    for r in reflections:
        for tag in r.get("selected_quick_tags", []):
            tag_usage[tag] = tag_usage.get(tag, 0) + 1

    # Gap types
    gap_types = {}
    for r in reflections:
        gap = r.get("awareness_gap_type", "unknown")
        gap_types[gap] = gap_types.get(gap, 0) + 1

    return {
        "total_reflections": total_reflections,
        "fresh_reflections": fresh_reflections,
        "fresh_rate": fresh_reflections / total_reflections if total_reflections > 0 else 0,
        "avg_completion_time_sec": round(avg_completion_time, 1),
        "intent_distribution": intent_counts,
        "tag_usage": dict(sorted(tag_usage.items(), key=lambda x: x[1], reverse=True)[:10]),
        "gap_type_distribution": gap_types,
    }

@router.get("/rewards/post-loss-message")
async def get_post_loss_message_endpoint(game_id: str, user: User = Depends(get_current_user)):
    """
    Get post-loss recovery message for a specific game.
    Returns personalized, rating-adaptive messaging.
    """
    from adaptive_profile_engine import get_adaptive_profile_sync
    from reward_message_service import get_post_loss_message

    # Get user's profile for rating
    profile = await db.player_profiles.find_one({"user_id": user.user_id})
    rating = profile.get("estimated_rating", 1200) if profile else 1200

    # Get the game to check main pattern
    analysis = await db.game_analyses.find_one({"game_id": game_id, "user_id": user.user_id})

    # Find the main pattern from the game
    focus_label = "Critical Position Focus"  # Default
    minutes = 5

    if analysis:
        # Try to find the main mistake pattern
        blunders = analysis.get("stockfish_analysis", {}).get("move_evaluations", [])
        for move in blunders:
            eval_type = move.get("evaluation")
            if hasattr(eval_type, 'value'):
                eval_type = eval_type.value
            if eval_type in ["blunder", "mistake"]:
                # Use the first major mistake as focus
                thinking_pattern = move.get("thinking_pattern")
                if thinking_pattern:
                    focus_label = thinking_pattern.replace("_", " ").title()
                break

    # Get adaptive profile for this rating
    adaptive_profile = get_adaptive_profile_sync(rating)
    minutes = adaptive_profile.get("mission_minutes_target", 5)

    # Get the message
    message = get_post_loss_message(rating, focus_label, minutes)

    return message


# ==================== COACH HOME ROUTES ====================

@router.get("/coach/fresh-loss")
async def get_fresh_loss(user: User = Depends(get_current_user)):
    """
    Check if user has a fresh loss (within last 2 hours) that needs recovery.
    Returns the loss details and recommended recovery path.
    """
    from datetime import datetime, timezone, timedelta
    from adaptive_profile_engine import get_adaptive_profile_sync

    # Look for games in last 2 hours marked as loss
    two_hours_ago = datetime.now(timezone.utc) - timedelta(hours=2)

    recent_loss = await db.game_analyses.find_one(
        {
            "user_id": user.user_id,
            "result": "loss",
            "analyzed_at": {"$gte": two_hours_ago}
        },
        sort=[("analyzed_at", -1)]
    )

    if not recent_loss:
        return {"has_fresh_loss": False}

    # Get the main mistake pattern from this game
    focus_label = "Critical moment"
    blunders = recent_loss.get("stockfish_analysis", {}).get("move_evaluations", [])

    for move in blunders:
        eval_type = move.get("evaluation")
        if hasattr(eval_type, 'value'):
            eval_type = eval_type.value
        if eval_type in ["blunder", "mistake"]:
            thinking_pattern = move.get("thinking_pattern")
            if thinking_pattern:
                focus_label = thinking_pattern.replace("_", " ").title()
            break

    # Get user rating for adaptive timing
    profile = await db.player_profiles.find_one({"user_id": user.user_id})
    rating = profile.get("estimated_rating", 1200) if profile else 1200
    adaptive = get_adaptive_profile_sync(rating)
    minutes = adaptive.get("mission_minutes_target", 6)

    return {
        "has_fresh_loss": True,
        "game_id": str(recent_loss.get("game_id")),
        "focus_label": focus_label,
        "estimated_minutes": minutes,
        "opponent": recent_loss.get("opponent"),
        "time_since_loss_minutes": int((datetime.now(timezone.utc) - recent_loss.get("analyzed_at", datetime.now(timezone.utc))).total_seconds() / 60)
    }

@router.get("/coach/weekly-proof")
async def get_weekly_proof(user: User = Depends(get_current_user)):
    """
    Get weekly proof summary - wins, improvements, streaks.
    Used for the compact weekly proof card on Coach Home.
    """
    from datetime import datetime, timezone, timedelta

    one_week_ago = datetime.now(timezone.utc) - timedelta(days=7)

    # Count wins this week
    wins = await db.game_analyses.count_documents({
        "user_id": user.user_id,
        "result": "win",
        "analyzed_at": {"$gte": one_week_ago}
    })

    # Count completed missions this week
    missions_completed = await db.behavioral_missions.count_documents({
        "user_id": user.user_id,
        "status": "completed",
        "completed_at": {"$gte": one_week_ago}
    })

    # Check for improving patterns (from focus_mastery collection)
    improving_pattern = None
    mastery_doc = await db.focus_mastery.find_one({"user_id": user.user_id})
    if mastery_doc:
        patterns = mastery_doc.get("patterns", {})
        for pattern_name, pattern_data in patterns.items():
            if pattern_data.get("trend") == "improving":
                improving_pattern = pattern_name.replace("_", " ").title()
                break

    # Get streak
    streak_days = 0
    streak_doc = await db.user_streaks.find_one({"user_id": user.user_id})
    if streak_doc:
        streak_days = streak_doc.get("current_streak", 0)

    return {
        "wins": wins,
        "missions_completed": missions_completed,
        "leak_reduced": improving_pattern,
        "streak_days": streak_days
    }

@router.get("/coach/home-intelligence")
async def get_home_intelligence_endpoint(user: User = Depends(get_current_user)):
    """
    Get comprehensive home intelligence data for the Coach Home page.
    Returns development phase, focus capacity, and actionable advice.
    """
    from home_intelligence_service import get_home_intelligence

    data = await get_home_intelligence(db, user.user_id)
    return data


# ==================== COACH STATE - SINGLE SOURCE OF TRUTH ====================

@router.get("/coach/game-summary/{game_id}")
async def get_game_summary_endpoint(game_id: str, user: User = Depends(get_current_user)):
    """Get GameCoachSummary for a specific game"""
    from coach_state_service import CoachStateService

    service = CoachStateService(db)
    summary = await service.get_game_coach_summary(game_id)

    if not summary:
        return {"has_summary": False, "game_id": game_id}

    if summary.user_id != user.user_id:
        raise HTTPException(status_code=403, detail="Not your game")

    return {
        "has_summary": True,
        **summary.to_dict()
    }


@router.post("/coach/generate-summary/{game_id}")
async def generate_game_summary_endpoint(game_id: str, user: User = Depends(get_current_user)):
    """
    Manually trigger GameCoachSummary generation for a game.

    Normally this happens automatically after analysis completes.
    """
    from coach_state_service import CoachStateService, generate_game_coach_summary

    # Get game analysis
    analysis = await db.game_analyses.find_one({
        "game_id": game_id,
        "user_id": user.user_id
    })

    if not analysis:
        raise HTTPException(status_code=404, detail="Game analysis not found")

    # Get current coach state
    service = CoachStateService(db)
    state = await service.get_coach_state(user.user_id)

    if not state:
        state = await service.initialize_coach_state(user.user_id)

    # Generate summary
    summary = await generate_game_coach_summary(
        db=db,
        game_id=game_id,
        user_id=user.user_id,
        game_analysis=analysis,
        coach_state=state
    )

    return summary.to_dict()


@router.get("/coach/theme-stats")
async def get_theme_stats_endpoint(user: User = Depends(get_current_user)):
    """
    Get improvement statistics for user's active theme.

    For Progress page "Coach Focus This Week" block:
    - theme name
    - micro rules
    - improvement trend (mistakes before vs after)
    """
    from coach_state_service import CoachStateService

    service = CoachStateService(db)
    state = await service.get_coach_state(user.user_id)

    if not state:
        return {"has_theme": False}

    stats = await service.get_theme_improvement_stats(user.user_id, state.active_theme)

    return {
        "has_theme": True,
        "active_theme": state.active_theme.value,
        "theme_display": state.active_theme.value.replace("_", " "),
        "theme_reason": state.theme_reason,
        "micro_rules": state.micro_rules,
        "games_on_theme": state.games_on_theme,
        "days_on_theme": (datetime.now(timezone.utc) - state.theme_started_at).days,
        "improvement_stats": stats
    }


# ==================== BEHAVIORAL MATURITY ROUTES ====================

@router.get("/coach/analytics/maturity-progression")
async def get_maturity_progression(user: User = Depends(get_current_user)):
    """
    Get full maturity progression history.

    Shows the user's journey from Novice -> Developing -> Disciplined -> Advanced
    """
    from coach_analytics_service import get_analytics_service

    analytics = get_analytics_service(db)
    progression = await analytics.get_maturity_progression(user.user_id)
    return {"progression": progression}


# ==================== DEEP COACHING SESSION ROUTES ====================

@router.get("/coach/deep-session/check")
async def check_deep_session_trigger(user: User = Depends(get_current_user)):
    """
    Check if a deep coaching session should be triggered.

    Returns:
    - should_trigger: bool
    - reason: why (scheduled/game_threshold/regression/etc)
    - message: banner text for UI
    """
    from deep_session_service import DeepSessionService

    service = DeepSessionService(db)
    result = await service.should_trigger_deep_session(user.user_id)
    return result


@router.post("/coach/deep-session/start")
async def start_deep_session(
    request: Dict = Body(default={}),
    user: User = Depends(get_current_user)
):
    """
    Start a new deep coaching session.

    Optional body: { "trigger": "manual" }
    """
    from deep_session_service import DeepSessionService, DeepSessionTrigger

    trigger_str = request.get("trigger", "manual")
    try:
        trigger = DeepSessionTrigger(trigger_str)
    except:
        trigger = DeepSessionTrigger.MANUAL

    service = DeepSessionService(db)
    session = await service.start_session(user.user_id, trigger)

    # Return session with step 1 content
    content = service.get_step_content(session, 1)

    return {
        "session_id": session.session_id,
        "current_step": session.current_step,
        "total_steps": 6,
        "content": content
    }


@router.get("/coach/deep-session/{session_id}")
async def get_deep_session(session_id: str, user: User = Depends(get_current_user)):
    """Get current deep session state and content"""
    from deep_session_service import DeepSessionService

    service = DeepSessionService(db)
    session = await service.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.user_id != user.user_id:
        raise HTTPException(status_code=403, detail="Not your session")

    content = service.get_step_content(session, session.current_step)

    return {
        "session_id": session.session_id,
        "current_step": session.current_step,
        "total_steps": 6,
        "completed": session.completed,
        "theme": session.theme,
        "content": content
    }


@router.post("/coach/deep-session/{session_id}/reflection")
async def submit_deep_session_reflection(
    session_id: str,
    request: Dict = Body(...),
    user: User = Depends(get_current_user)
):
    """
    Submit reflection answer (step 2 -> step 3).

    Body: { "answer": "momentum" }
    """
    from deep_session_service import DeepSessionService

    answer = request.get("answer")
    if not answer:
        raise HTTPException(status_code=400, detail="answer required")

    service = DeepSessionService(db)
    session = await service.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.user_id != user.user_id:
        raise HTTPException(status_code=403, detail="Not your session")

    session = await service.submit_reflection(session_id, answer)
    content = service.get_step_content(session, session.current_step)

    return {
        "session_id": session.session_id,
        "current_step": session.current_step,
        "content": content
    }


@router.post("/coach/deep-session/{session_id}/advance")
async def advance_deep_session(session_id: str, user: User = Depends(get_current_user)):
    """Advance to next step"""
    from deep_session_service import DeepSessionService

    service = DeepSessionService(db)
    session = await service.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.user_id != user.user_id:
        raise HTTPException(status_code=403, detail="Not your session")

    session = await service.advance_step(session_id)
    content = service.get_step_content(session, session.current_step)

    return {
        "session_id": session.session_id,
        "current_step": session.current_step,
        "content": content
    }


@router.post("/coach/deep-session/{session_id}/complete")
async def complete_deep_session(session_id: str, user: User = Depends(get_current_user)):
    """
    Complete the deep session.

    Updates CoachState with new micro rule and schedules next session.
    """
    from deep_session_service import DeepSessionService

    service = DeepSessionService(db)
    session = await service.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.user_id != user.user_id:
        raise HTTPException(status_code=403, detail="Not your session")

    session = await service.complete_session(session_id)

    return {
        "success": True,
        "session_id": session.session_id,
        "completed": True,
        "micro_rule_assigned": session.micro_rule_assigned,
        "next_session_due": session.completed_at + timedelta(days=7) if session.completed_at else None
    }


@router.get("/coach/deep-session/improvement-check")
async def check_post_session_improvement(user: User = Depends(get_current_user)):
    """
    Check if user improved after completing a deep session.

    Returns message for Home page if improvement detected:
    "You handled threat verification better in your last game."
    """
    from deep_session_service import check_post_session_improvement as check_improvement

    result = await check_improvement(db, user.user_id)
    return result or {"show_improvement": False}


# ==================== COACH MODE ROUTES ====================

@router.post("/coach/start-session")
async def start_coach_session(
    data: dict,
    user: User = Depends(get_current_user)
):
    """Start a play session - user is going to play"""
    from coach_session_service import start_play_session
    platform = data.get("platform", "chess.com")
    result = await start_play_session(db, user.user_id, platform)
    return result


@router.post("/coach/end-session")
async def end_coach_session(user: User = Depends(get_current_user)):
    """End play session - user finished playing, find and analyze their game"""
    from coach_session_service import end_play_session
    result = await end_play_session(db, user.user_id)
    return result


@router.get("/coach/analysis-status/{game_id}")
async def get_analysis_status(game_id: str, user: User = Depends(get_current_user)):
    """Poll for analysis completion and get real feedback"""
    from coach_session_service import _build_game_feedback

    # Check if analysis exists
    analysis = await db.game_analyses.find_one(
        {"game_id": game_id, "user_id": user.user_id},
        {"_id": 0, "blunders": 1, "mistakes": 1, "best_moves": 1, "identified_weaknesses": 1}
    )

    if not analysis:
        # Check queue status
        queue_item = await db.analysis_queue.find_one(
            {"game_id": game_id},
            {"_id": 0, "status": 1}
        )
        if queue_item and queue_item.get("status") == "failed":
            return {"status": "failed", "message": "Analysis failed. Try importing again."}
        return {"status": "pending", "message": "Still analyzing..."}

    # Get game details
    game = await db.games.find_one(
        {"game_id": game_id},
        {"_id": 0, "opponent": 1, "result": 1}
    )

    # Get dominant habit
    profile = await db.player_profiles.find_one(
        {"user_id": user.user_id},
        {"_id": 0, "top_weaknesses": 1}
    )
    dominant_habit = None
    if profile and profile.get("top_weaknesses"):
        w = profile["top_weaknesses"][0]
        dominant_habit = w.get("subcategory", str(w)) if isinstance(w, dict) else str(w)

    feedback = _build_game_feedback(analysis, dominant_habit, game or {})

    return {
        "status": "complete",
        "feedback": feedback
    }


@router.get("/coach/session-status")
async def get_coach_session_status(user: User = Depends(get_current_user)):
    """Get current session status"""
    from coach_session_service import get_session_status
    return await get_session_status(db, user.user_id)


class ReflectionResult(BaseModel):
    """Track PDR reflection results"""
    game_id: str
    move_number: int
    move_correct: bool
    reason_correct: Optional[bool] = None
    user_move: str
    best_move: str


@router.post("/coach/track-reflection")
async def track_reflection(result: ReflectionResult, user: User = Depends(get_current_user)):
    """Track PDR reflection results for stats"""
    reflection_doc = {
        "user_id": user.user_id,
        "game_id": result.game_id,
        "move_number": result.move_number,
        "move_correct": result.move_correct,
        "reason_correct": result.reason_correct,
        "user_move": result.user_move,
        "best_move": result.best_move,
        "created_at": datetime.now(timezone.utc).isoformat()
    }

    await db.reflection_results.insert_one(reflection_doc)

    # Update user's reflection stats
    await db.users.update_one(
        {"user_id": user.user_id},
        {
            "$inc": {
                "total_reflections": 1,
                "correct_reflections": 1 if result.move_correct else 0
            }
        }
    )

    # Check for habit rotation after tracking
    from habit_rotation_service import update_habit_after_reflection
    rotation_result = await update_habit_after_reflection(db, user.user_id, result.game_id, result.move_correct)

    response = {"status": "tracked"}
    if rotation_result and rotation_result.get("rotated"):
        response["habit_rotated"] = True
        response["rotation_info"] = rotation_result

    return response


@router.get("/coach/habits")
async def get_habit_statuses(user: User = Depends(get_current_user)):
    """Get all habit statuses for the user."""
    from habit_rotation_service import get_all_habit_statuses
    statuses = await get_all_habit_statuses(db, user.user_id)
    return {"habits": statuses}


@router.post("/coach/check-habit-rotation")
async def check_habit_rotation(user: User = Depends(get_current_user)):
    """Manually check if habit should be rotated."""
    from habit_rotation_service import check_and_rotate_habit
    result = await check_and_rotate_habit(db, user.user_id)
    return result


# ==================== WEEKLY SUMMARY + ADMIN ====================

@router.get("/user/weekly-summary")
async def get_weekly_summary(user: User = Depends(get_current_user)):
    """Get user's weekly summary data."""
    from weekly_summary_service import generate_weekly_summary_data
    summary = await generate_weekly_summary_data(db, user.user_id)
    return summary


@router.post("/user/send-weekly-summary")
async def send_weekly_summary_to_user(user: User = Depends(get_current_user)):
    """Send weekly summary email to current user."""
    from weekly_summary_service import send_single_weekly_summary
    result = await send_single_weekly_summary(db, user.user_id)
    return result


@router.post("/admin/send-all-weekly-summaries")
async def send_all_weekly_summaries(user: User = Depends(get_current_user)):
    """Admin endpoint to trigger weekly summaries for all users."""
    # Simple admin check - in production, use proper admin auth
    from weekly_summary_service import send_weekly_summaries
    result = await send_weekly_summaries(db)
    return result


@router.post("/admin/backfill-openings")
async def backfill_openings(user: User = Depends(get_current_user)):
    """
    Backfill opening info for all games that don't have it.
    This extracts ECO code, opening name from PGN headers.
    """
    from journey_service import backfill_opening_info
    updated = await backfill_opening_info(db, user.user_id)
    return {"success": True, "games_updated": updated}


# ==================== COACH TODAY ====================

@router.get("/coach/today")
async def get_coach_today(user: User = Depends(get_current_user)):
    """
    Get today's coaching focus - structured as:
    0. Reflection Moment (critical position from recent game)
    1. Correct This (ONE dominant habit)
    2. Keep Doing This (ONE strength/improvement)
    3. Remember This Rule (carry-forward principle)
    """
    import sys
    print(f"[COACH] API called for user {user.user_id}", file=sys.stderr)

    # Get player profile first - this is the source of truth
    profile = await db.player_profiles.find_one(
        {"user_id": user.user_id},
        {"_id": 0}
    )

    # Check if we have any analyses
    analysis_count = await db.game_analyses.count_documents({"user_id": user.user_id})

    # If no profile and no analyses, prompt to link account
    if not profile and analysis_count == 0:
        user_doc = await db.users.find_one({"user_id": user.user_id}, {"_id": 0})
        has_account = bool(user_doc.get("chess_com_username") or user_doc.get("lichess_username"))

        if not has_account:
            return {
                "has_data": False,
                "message": "Link your chess account to get started"
            }
        return {
            "has_data": False,
            "message": "Analyzing your games..."
        }

    # Get recent analyses for context
    recent_analyses = await db.game_analyses.find(
        {"user_id": user.user_id},
        {"_id": 0, "game_id": 1, "blunders": 1, "mistakes": 1, "accuracy": 1, "created_at": 1,
         "identified_weaknesses": 1, "strengths": 1, "weaknesses": 1}
    ).sort("created_at", -1).limit(10).to_list(10)

    # Get top weakness as the correction
    top_weaknesses = profile.get("top_weaknesses", []) if profile else []

    # ===== SECTION 1: CORRECT THIS =====
    if top_weaknesses:
        top = top_weaknesses[0]
        top.get("subcategory", "").replace("_", " ").title()
        occurrences = top.get("occurrence_count", 0)

        # Calculate recent frequency
        recent_count = 0
        total_recent = min(5, len(recent_analyses))
        for analysis in recent_analyses[:5]:
            weaknesses = analysis.get("identified_weaknesses", []) or analysis.get("weaknesses", [])
            if isinstance(weaknesses, list):
                for w in weaknesses:
                    if isinstance(w, dict):
                        if top.get("subcategory", "").lower() in str(w.get("subcategory", "")).lower():
                            recent_count += 1
                            break
                    elif isinstance(w, str) and top.get("subcategory", "").lower() in w.lower():
                        recent_count += 1
                        break

        # Build context message
        if recent_count > 0 and total_recent > 0:
            pass
        else:
            pass


    # ===== SECTION 2: KEEP DOING THIS (Reinforcement) =====

    # Check for strengths in profile
    strengths = profile.get("strengths", []) if profile else []
    improving_areas = profile.get("improving_areas", []) if profile else []

    # Look for genuine improvement or strength
    if improving_areas:
        area = improving_areas[0]
        {
            "title": area.get("name", "Positional Play").replace("_", " ").title(),
            "context": "Recent games show improvement here.",
            "trend": "Earlier this was unstable — now improving."
        }
    elif strengths:
        strength = strengths[0] if isinstance(strengths[0], dict) else {"name": strengths[0]}
        {
            "title": strength.get("name", "Solid Play").replace("_", " ").title(),
            "context": "You've maintained consistency in this area.",
            "trend": "Keep this discipline."
        }
    else:
        # Check recent analyses for any positive signals
        # Use stockfish_analysis.move_evaluations for accurate counts
        def get_blunders(a):
            sf = a.get("stockfish_analysis", {})
            evals = sf.get("move_evaluations", [])
            return sum(1 for m in evals if m.get("evaluation") == "blunder")

        recent_blunders = [get_blunders(a) for a in recent_analyses[:3]]
        if recent_blunders and sum(recent_blunders) == 0:
            pass
        elif len(recent_analyses) >= 2:
            # Default neutral reinforcement
            pass

    # ===== SECTION 3: REMEMBER THIS RULE =====
    habit_rules = {
        "one_move_blunders": "Before every move, ask:\n\"What can my opponent capture if I play this?\"",
        "one_move_blunder": "Before every move, ask:\n\"What can my opponent capture if I play this?\"",
        "premature_queen_moves": "Develop knights and bishops before your queen.\nEarly queen moves invite attacks.",
        "time_trouble": "Use at least 10 seconds on each move.\nSpeed without thought is wasted calculation.",
        "missed_tactics": "On every opponent move, check for loose pieces first.\nTactics hide in plain sight.",
        "weak_endgame": "In king and pawn endings, activate your king immediately.\nThe king is a fighting piece in endgames.",
        "opening_mistakes": "Control the center with pawns.\nDevelop pieces toward the center.",
        "piece_activity": "If a piece hasn't moved, find a square for it.\nPassive pieces lose games.",
        "king_safety": "Castle early unless you have a specific reason not to.\nAn exposed king invites disaster.",
        "exposing_own_king": "Before moving, check if it weakens your king's protection.\nKing safety is non-negotiable.",
        "pawn_structure": "Avoid doubled pawns unless you get clear compensation.\nPawn structure shapes the entire game.",
        "calculation_errors": "Calculate forcing moves first: checks, captures, threats.\nForcing moves narrow the possibilities.",
    }

    rule = None
    if top_weaknesses:
        subcategory_key = top_weaknesses[0].get("subcategory", "").lower().replace(" ", "_")
        rule = habit_rules.get(subcategory_key)

    if not rule:
        rule = "Before every move, pause and ask:\n\"Is this move safe? What is my opponent's threat?\""

    # ===== COACH'S NOTE (2 lines max, emotional framing) =====
    coach_note = None
    if top_weaknesses:
        habit_name = top_weaknesses[0].get("subcategory", "").replace("_", " ").lower()
        occurrences = top_weaknesses[0].get("occurrence_count", 0)

        if occurrences > 10:
            coach_note = {
                "line1": "Your positions are generally fine.",
                "line2": f"Games are slipping due to {habit_name}. One fix, big improvement."
            }
        elif occurrences > 5:
            coach_note = {
                "line1": "You're playing solid chess.",
                "line2": f"Focus on eliminating {habit_name} and you'll see results."
            }
        else:
            coach_note = {
                "line1": "Good progress this week.",
                "line2": "Keep the discipline. Small improvements compound."
            }
    else:
        coach_note = {
            "line1": "Let's build a strong foundation.",
            "line2": "Play mindfully. I'll help identify what to work on."
        }

    # ===== LIGHT STATS (2-3 stats with trends) =====
    light_stats = []

    # Helper to count blunders from Stockfish data
    def count_blunders_sf(a):
        sf = a.get("stockfish_analysis", {})
        evals = sf.get("move_evaluations", [])
        return sum(1 for m in evals if m.get("evaluation") == "blunder")

    # Blunders per game trend
    recent_10 = recent_analyses[:10] if recent_analyses else []
    older_10 = recent_analyses[10:20] if len(recent_analyses) > 10 else []

    if recent_10:
        recent_blunders = sum(count_blunders_sf(a) for a in recent_10) / len(recent_10)
        if older_10:
            older_blunders = sum(count_blunders_sf(a) for a in older_10) / len(older_10)
            trend = "down" if recent_blunders < older_blunders else ("up" if recent_blunders > older_blunders else "stable")
            light_stats.append({
                "label": "Blunders / game",
                "value": f"{older_blunders:.1f} → {recent_blunders:.1f}",
                "trend": trend
            })
        else:
            light_stats.append({
                "label": "Blunders / game",
                "value": f"{recent_blunders:.1f}",
                "trend": "stable"
            })

    # NOTE: Rating intentionally NOT shown in Coach mode (Option C)
    # Rating is available on Progress page only - keeps Coach mode discipline-focused

    # Reflection success rate
    user_doc = await db.users.find_one({"user_id": user.user_id}, {"_id": 0})
    total_reflections = user_doc.get("total_reflections", 0) if user_doc else 0
    correct_reflections = user_doc.get("correct_reflections", 0) if user_doc else 0

    if total_reflections >= 3:
        success_rate = correct_reflections / total_reflections
        trend = "up" if success_rate >= 0.6 else ("down" if success_rate < 0.4 else "stable")
        light_stats.append({
            "label": "Reflection success",
            "value": f"{correct_reflections}/{total_reflections}",
            "trend": trend
        })

    # ===== NEXT GAME PLAN (1-2 lines) =====
    next_game_plan = None
    if top_weaknesses:
        habit = top_weaknesses[0].get("subcategory", "").lower()

        plans = {
            "one_move_blunders": "Before each move, pause and ask: What can my opponent do if I play this?",
            "premature_queen_moves": "First 10 moves: develop knights and bishops before the queen.",
            "time_trouble": "After move 15, use at least 10 seconds per move. No rushing.",
            "missed_tactics": "Each opponent move, check: Are any of my pieces loose?",
            "weak_endgame": "When queens come off, activate your king immediately.",
            "opening_mistakes": "Focus on controlling the center. e4/d4 pawns, then develop pieces.",
            "exposing_own_king": "Before making a move, check if it weakens your king's safety.",
        }

        next_game_plan = plans.get(habit, "Play slowly. Check opponent's threats before each move.")
    else:
        next_game_plan = "Focus on one thing: pause before each move and ask what your opponent wants."

    # ===== SESSION STATUS =====
    from coach_session_service import get_session_status
    session_status = await get_session_status(db, user.user_id)

    # ===== LAST GAME SUMMARY =====
    # CRITICAL: Only show games with REAL Stockfish analysis
    # See /app/backend/DATA_MODEL.md for schema details
    #
    # DATA MODEL:
    # - stockfish_analysis.move_evaluations: Array of Stockfish evals (SOURCE OF TRUTH)
    # - stockfish_analysis.accuracy: Real accuracy from Stockfish
    # - commentary: GPT text only, NOT source of truth for stats
    # - Top-level blunders/mistakes: MAY BE STALE, don't use
    #
    # A game is PROPERLY analyzed if:
    # 1. stockfish_analysis.move_evaluations exists AND has >= 3 items
    # 2. stockfish_failed is NOT True
    last_game = None

    recent_analyses = await db.game_analyses.find(
        {
            "user_id": user.user_id,
            "stockfish_failed": {"$ne": True},
            # CRITICAL: Must check nested path, NOT top-level
            "stockfish_analysis.move_evaluations": {"$exists": True, "$not": {"$size": 0}}
        },
        {"_id": 0, "game_id": 1, "blunders": 1, "mistakes": 1, "accuracy": 1,
         "commentary": 1, "identified_weaknesses": 1, "stockfish_analysis": 1}
    ).sort("created_at", -1).limit(5).to_list(5)

    # Find the first one that has actual analysis data
    last_analysis = None
    most_recent_game = None

    for analysis in recent_analyses:
        # Verify it has real Stockfish data
        sf_data = analysis.get("stockfish_analysis", {})
        move_evals = sf_data.get("move_evaluations", [])
        if len(move_evals) >= 3:  # At least 3 moves evaluated by Stockfish
            # Get the corresponding game
            game = await db.games.find_one(
                {"game_id": analysis.get("game_id"), "user_id": user.user_id},
                {"_id": 0, "game_id": 1, "result": 1, "user_color": 1, "time_control": 1,
                 "platform": 1, "url": 1, "pgn": 1, "termination": 1}
            )
            if game:
                most_recent_game = game
                last_analysis = analysis
                break

    if most_recent_game and last_analysis:
            # CRITICAL: Get stats from stockfish_analysis, NOT top-level fields
            # See /app/backend/DATA_MODEL.md
            sf_data = last_analysis.get("stockfish_analysis", {})
            move_evals = sf_data.get("move_evaluations", [])

            # Count from Stockfish move_evaluations (SOURCE OF TRUTH)
            blunders = sum(1 for m in move_evals if m.get("evaluation") == "blunder")
            mistakes = sum(1 for m in move_evals if m.get("evaluation") == "mistake")
            accuracy = sf_data.get("accuracy", 0) or 0

            # Get opponent name from PGN
            user_color = most_recent_game.get("user_color", "white")
            opponent = "Opponent"

            if most_recent_game.get("pgn"):
                import re
                pgn = most_recent_game["pgn"]
                white_match = re.search(r'\[White "([^"]+)"\]', pgn)
                black_match = re.search(r'\[Black "([^"]+)"\]', pgn)
                if white_match and black_match:
                    if user_color == "white":
                        opponent = black_match.group(1)
                    else:
                        opponent = white_match.group(1)

            # Determine win/loss from user's perspective
            result = most_recent_game.get("result", "")
            if user_color == "white":
                won = result == "1-0"
                lost = result == "0-1"
            else:
                won = result == "0-1"
                lost = result == "1-0"

            # Check if repeated habit
            repeated_habit = False
            habit_name = top_weaknesses[0].get("subcategory", "") if top_weaknesses else ""
            weaknesses = last_analysis.get("identified_weaknesses", [])
            if habit_name and weaknesses:
                for w in weaknesses:
                    w_name = w.get("subcategory", str(w)) if isinstance(w, dict) else str(w)
                    if habit_name.lower() in w_name.lower():
                        repeated_habit = True
                        break

            # Get termination reason
            termination = most_recent_game.get("termination", "")

            # Generate human-readable termination text
            termination_text = ""
            if termination == "timeout":
                termination_text = "lost on time" if lost else "opponent timed out"
            elif termination == "resigned":
                termination_text = "resigned" if lost else "opponent resigned"
            elif termination == "checkmated":
                termination_text = "checkmated" if lost else "checkmate"
            elif termination == "won":
                termination_text = ""
            elif termination == "stalemate":
                termination_text = "stalemate"

            # Generate coach comment based on actual game outcome
            if blunders == 0:
                if won:
                    comment = "Clean win! No blunders. This is the discipline we want."
                elif lost:
                    if termination == "timeout":
                        comment = "You lost on time but played clean — no blunders. Time management is the issue here."
                    elif termination == "resigned":
                        comment = "You resigned but had no blunders. Was there a tactical shot you missed?"
                    else:
                        comment = "You lost but played clean — no blunders. Sometimes chess is like that."
                else:
                    comment = "Solid draw, no blunders. Good focus."
            elif blunders == 1:
                if repeated_habit:
                    comment = f"One blunder — same pattern: {habit_name.replace('_', ' ')}. Let's fix this."
                else:
                    comment = "One slip-up. Let's see what happened."
            else:
                if repeated_habit:
                    comment = f"{blunders} blunders, including your old pattern. We need to work on this."
                else:
                    comment = f"{blunders} blunders. Rough game — let's review."

            last_game = {
                "opponent": opponent,
                "result": "Won" if won else ("Lost" if lost else "Draw"),
                "termination": termination_text,
                "time_control": most_recent_game.get("time_control"),
                "stats": {
                    "blunders": blunders,
                    "mistakes": mistakes,
                    "accuracy": accuracy
                },
                "comment": comment,
                "repeated_habit": repeated_habit,
                "game_id": most_recent_game.get("game_id"),
                "external_url": most_recent_game.get("url"),
                "has_full_analysis": True
            }

    # ===== OPENING DISCIPLINE (Play This Today / Rating Leak / Wisdom) =====
    opening_discipline = None

    try:
        # Get all analyzed games with opening data
        games_with_openings = await db.games.find(
            {"user_id": user.user_id, "is_analyzed": True},
            {"_id": 0, "game_id": 1, "user_color": 1, "result": 1, "pgn": 1}
        ).to_list(100)

        if games_with_openings and len(games_with_openings) >= 3:
            import re
            from collections import defaultdict

            # Load ECO openings for name lookup
            eco_openings = {}
            try:
                import json
                with open("data/eco_openings.json", "r") as f:
                    eco_openings = json.load(f)
            except Exception:
                pass

            # Track opening stats by color
            white_openings = defaultdict(lambda: {"wins": 0, "losses": 0, "draws": 0, "total": 0})
            black_openings = defaultdict(lambda: {"wins": 0, "losses": 0, "draws": 0, "total": 0})

            for game in games_with_openings:
                pgn = game.get("pgn", "")
                user_color = game.get("user_color", "white")
                result = game.get("result", "")

                # Extract opening from ECO code
                eco_match = re.search(r'\[ECO "([^"]+)"\]', pgn)
                opening_match = re.search(r'\[Opening "([^"]+)"\]', pgn)

                opening_name = "Unknown Opening"
                if opening_match:
                    opening_name = opening_match.group(1)
                elif eco_match:
                    eco = eco_match.group(1)
                    opening_name = eco_openings.get(eco, eco)

                # Simplify opening name (remove variations)
                opening_name = opening_name.split(":")[0].split(",")[0].strip()

                # Skip unknown openings
                if opening_name == "Unknown Opening":
                    continue

                # Determine win/loss/draw
                if user_color == "white":
                    won = result == "1-0"
                    lost = result == "0-1"
                else:
                    won = result == "0-1"
                    lost = result == "1-0"

                # Track stats
                if user_color == "white":
                    stats = white_openings[opening_name]
                else:
                    stats = black_openings[opening_name]
                stats["total"] += 1
                if won:
                    stats["wins"] += 1
                elif lost:
                    stats["losses"] += 1
                else:
                    stats["draws"] += 1

            # Calculate win rates and find best/worst
            def calc_win_rate(stats):
                if stats["total"] == 0:
                    return 0
                return round((stats["wins"] / stats["total"]) * 100)

            # Best opening as White (min 3 games)
            best_white = None
            best_white_rate = 0
            for opening, stats in white_openings.items():
                if stats["total"] >= 3:
                    rate = calc_win_rate(stats)
                    if rate > best_white_rate:
                        best_white_rate = rate
                        best_white = {"name": opening, "win_rate": rate, "games": stats["total"], "wins": stats["wins"]}

            # Best opening as Black (min 3 games)
            best_black = None
            best_black_rate = 0
            for opening, stats in black_openings.items():
                if stats["total"] >= 3:
                    rate = calc_win_rate(stats)
                    if rate > best_black_rate:
                        best_black_rate = rate
                        best_black = {"name": opening, "win_rate": rate, "games": stats["total"], "wins": stats["wins"]}

            # Worst openings (rating leaks) - min 3 games, <40% win rate
            rating_leaks = []
            all_openings = {}
            for opening, stats in white_openings.items():
                all_openings[f"white_{opening}"] = {"opening": opening, "color": "white", "stats": stats}
            for opening, stats in black_openings.items():
                all_openings[f"black_{opening}"] = {"opening": opening, "color": "black", "stats": stats}

            for key, data in all_openings.items():
                stats = data["stats"]
                if stats["total"] >= 3:
                    rate = calc_win_rate(stats)
                    if rate < 40:
                        rating_leaks.append({
                            "name": data["opening"],
                            "color": data["color"],
                            "win_rate": rate,
                            "games": stats["total"],
                            "wins": stats["wins"]
                        })
            rating_leaks.sort(key=lambda x: x["win_rate"])

            # Opening wisdom - coaching tips for best openings
            opening_wisdom = []

            # Tips based on opening names
            opening_tips = {
                "Italian": {
                    "tip": "Castle early, then prepare d4 push. Build pressure before attacking.",
                    "key_idea": "Control the center with pieces, not just pawns."
                },
                "Sicilian": {
                    "tip": "As Black, counterattack on the queenside. Don't be passive.",
                    "key_idea": "Pawn breaks with ...b5 or ...d5 are your weapons."
                },
                "Queen's Gambit": {
                    "tip": "Control d5. If Black captures, recapture with the knight or bishop.",
                    "key_idea": "Space advantage in the center leads to attacking chances."
                },
                "London": {
                    "tip": "Develop bishop to f4 before playing e3. Keep flexibility.",
                    "key_idea": "Solid structure, but don't be too passive."
                },
                "Caro-Kann": {
                    "tip": "Your light-squared bishop is your strength. Don't trade it easily.",
                    "key_idea": "Solid pawn structure compensates for slightly less space."
                },
                "French": {
                    "tip": "Break with ...c5 early. Your c8 bishop is the problem piece.",
                    "key_idea": "The pawn chain defines the game. Attack its base."
                },
                "King's Indian": {
                    "tip": "Kingside attack with ...f5 is your main plan. Don't delay.",
                    "key_idea": "Let White have the center, then undermine it."
                },
                "Ruy Lopez": {
                    "tip": "The bishop on b5 is not attacking a6. It's preparing for long-term pressure.",
                    "key_idea": "Patience. This opening rewards slow maneuvering."
                },
                "Scandinavian": {
                    "tip": "After ...Qd8 or ...Qa5, develop quickly. Don't move the queen again.",
                    "key_idea": "Early queen move costs time. Make up for it with rapid development."
                },
                "Pirc": {
                    "tip": "Let White build a big center, then strike with ...c5 or ...e5.",
                    "key_idea": "Hypermodern approach - control from the flanks."
                },
                "Scotch": {
                    "tip": "Open game means tactics. Calculate before every move.",
                    "key_idea": "Development speed is everything in open positions."
                },
                "English": {
                    "tip": "Flexible system. Control c4 and prepare to strike in the center.",
                    "key_idea": "Delay committing your pawns. Keep options open."
                },
                "Dutch": {
                    "tip": "The f5 pawn is your attacking spearhead. Protect it.",
                    "key_idea": "Kingside attack, but watch for Bg5 pins."
                }
            }

            # Add wisdom for best openings
            if best_white:
                for pattern, tips in opening_tips.items():
                    if pattern.lower() in best_white["name"].lower():
                        opening_wisdom.append({
                            "opening": best_white["name"],
                            "color": "white",
                            "tip": tips["tip"],
                            "key_idea": tips["key_idea"]
                        })
                        break
                else:
                    opening_wisdom.append({
                        "opening": best_white["name"],
                        "color": "white",
                        "tip": "Control the center. Develop pieces toward active squares.",
                        "key_idea": "Opening principles matter more than memorization."
                    })

            if best_black:
                for pattern, tips in opening_tips.items():
                    if pattern.lower() in best_black["name"].lower():
                        opening_wisdom.append({
                            "opening": best_black["name"],
                            "color": "black",
                            "tip": tips["tip"],
                            "key_idea": tips["key_idea"]
                        })
                        break
                else:
                    opening_wisdom.append({
                        "opening": best_black["name"],
                        "color": "black",
                        "tip": "Equalize first. Look for counterplay once you're developed.",
                        "key_idea": "Don't rush. Solid play leads to opportunities."
                    })

            opening_discipline = {
                "has_data": True,
                "play_this_today": {
                    "white": best_white,
                    "black": best_black,
                    "message": "Stay with what works. Master one opening before learning another."
                },
                "rating_leaks": rating_leaks[:2] if rating_leaks else [],
                "leak_message": "Avoid these until your middlegame habits are fixed." if rating_leaks else None,
                "wisdom": opening_wisdom[:2] if opening_wisdom else [],
                "total_openings_analyzed": len(white_openings) + len(black_openings)
            }
    except Exception as e:
        import traceback
        print(f"[COACH] Opening discipline error: {e}", file=sys.stderr)
        traceback.print_exc()
        opening_discipline = None

    return {
        "has_data": True,
        "coach_note": coach_note,
        "light_stats": light_stats,
        "next_game_plan": next_game_plan,
        "session_status": session_status,
        "last_game": last_game,
        "rule": rule,
        "opening_discipline": opening_discipline
    }


# ==================== FOCUS + DISCIPLINE + ADAPTIVE + FOCUS PLAN ====================

@router.get("/focus")
async def get_focus_page_data(user: User = Depends(get_current_user)):
    """
    Get data for the Focus page (TODAY - What to focus on NOW)

    Returns:
    - ONE dominant weakness
    - ONE mission (scaled by rating tier)
    - Opening Guidance (what's working, what to pause)
    - Rating impact estimate
    """
    from blunder_intelligence_service import get_focus_data

    # Get analyses
    analyses = await db.game_analyses.find(
        {"user_id": user.user_id}
    ).sort("created_at", -1).limit(50).to_list(50)

    # Get more games for opening guidance (need at least 4 per opening)
    games = await db.games.find(
        {"user_id": user.user_id},
        {"_id": 0, "game_id": 1, "opening": 1, "pgn": 1, "user_color": 1, "result": 1, "date": 1}
    ).sort("date", -1).limit(100).to_list(100)

    # Extract user's rating from recent games
    user_rating = None
    for game in games[:10]:
        pgn = game.get("pgn", "")
        user_color = game.get("user_color", "white")

        import re
        if user_color == "white":
            match = re.search(r'\[WhiteElo "(\d+)"\]', pgn)
        else:
            match = re.search(r'\[BlackElo "(\d+)"\]', pgn)

        if match:
            user_rating = int(match.group(1))
            break

    focus_data = get_focus_data(analyses, games, user_rating=user_rating)

    return focus_data


@router.post("/focus/next-mission")
async def get_next_mission(user: User = Depends(get_current_user)):
    """
    Mark current mission as completed and get a new mission.

    This endpoint is called when the user completes a mission and wants to
    get a new one. It stores the completion record and returns fresh focus data.
    """
    # Record mission completion
    await db.mission_completions.insert_one({
        "user_id": user.user_id,
        "completed_at": datetime.now(timezone.utc).isoformat()
    })

    # Increment completed missions count for the user
    await db.users.update_one(
        {"user_id": user.user_id},
        {"$inc": {"missions_completed": 1}}
    )

    return {"status": "ok", "message": "Mission marked as complete. Refresh to get your next mission."}


@router.get("/coach-review")
async def get_coach_review_data(user: User = Depends(get_current_user)):
    """
    Get personalized coach review of user's last game.

    This endpoint acts like a personal chess coach reviewing the student's most recent game:
    - Did they follow our opening suggestions?
    - Are they fixing the mistakes we identified?
    - Where did they improve? Where do they still struggle?
    - Personalized, factual feedback based on real data

    Returns:
    - Coach's personalized message
    - Performance comparison (vs their average)
    - Opening check (did they play what we suggested?)
    - Improvement highlights
    - Areas of concern
    """
    from coach_game_review_service import (
        get_coach_game_review,
        get_improvement_highlights,
        get_concern_areas
    )

    review_data = await get_coach_game_review(db, user.user_id, call_llm_fn)

    if review_data.get("has_review") and review_data.get("facts"):
        # Add highlights and concerns
        review_data["highlights"] = get_improvement_highlights(review_data["facts"])
        review_data["concerns"] = get_concern_areas(review_data["facts"])

    return review_data


@router.get("/discipline-check")
async def get_discipline_check_data(user: User = Depends(get_current_user)):
    """
    Get Discipline Check data for user's last game.

    This is a sharp, data-driven accountability check:
    - Did you follow opening advice?
    - Did you maintain composure when winning?
    - Decision Stability metric
    - Evidence-based verdict (no fluff)

    Returns compact card-based data with deterministic metrics.
    """
    from discipline_check_service import get_discipline_check
    return await get_discipline_check(db, user.user_id)


# =============================================================================
# ADAPTIVE PERFORMANCE COACH (NEW GOLD FEATURE - Focus Page v2)
# =============================================================================

@router.get("/adaptive-coach")
async def get_adaptive_coach_data_endpoint(user: User = Depends(get_current_user)):
    """
    Get Adaptive Performance Coach data for Focus page.

    This is the GM-style performance briefing system with 4 sections:
    1. Coach Diagnosis - Your Current Growth Priority (ONE primary leak)
    2. Next Game Plan - 5 domains (Opening, Middlegame, Tactical, Endgame, Time)
    3. Plan Audit - Last Game Execution Review (audit vs plan)
    4. Skill Signals - Live Performance Monitoring (trends)

    Rating-band aware:
    - 600-1000: Focus on Hanging Pieces
    - 1000-1600: Focus on Tactical Awareness
    - 1600-2000: Focus on Advantage Discipline
    - 2000+: Focus on Conversion Precision
    """
    from adaptive_coach_service import get_adaptive_coach_data

    data = await get_adaptive_coach_data(db, user.user_id)
    return data


@router.post("/adaptive-coach/audit-game/{game_id}")
async def audit_game_adaptive_coach(game_id: str, user: User = Depends(get_current_user)):
    """
    Audit a specific game against the current plan and update intensity levels.

    Called after game analysis completes to:
    1. Audit the game against the current plan
    2. Update intensity levels per domain (adaptive loop)
    3. Mark the plan as audited
    """
    from adaptive_coach_service import (
        audit_last_game_against_plan,
        update_intensity_after_audit
    )

    # Get game and analysis
    game = await db.games.find_one({"game_id": game_id, "user_id": user.user_id}, {"_id": 0})
    analysis = await db.game_analyses.find_one({"game_id": game_id, "user_id": user.user_id}, {"_id": 0})

    if not game or not analysis:
        return {"error": "Game or analysis not found"}

    # Get active plan
    active_plan = await db.user_adaptive_plans.find_one(
        {"user_id": user.user_id, "is_active": True},
        {"_id": 0}
    )

    if not active_plan:
        return {"error": "No active plan found"}

    # Audit the game
    audit_result = audit_last_game_against_plan(analysis, game, active_plan)

    # Update intensity levels
    intensity_update = await update_intensity_after_audit(db, user.user_id, audit_result)

    # Mark plan as audited
    await db.user_adaptive_plans.update_one(
        {"plan_id": active_plan["plan_id"]},
        {"$set": {"is_active": False, "is_audited": True, "audit_result": audit_result}}
    )

    return {
        "audit_result": audit_result,
        "intensity_update": intensity_update,
    }


# =============================================================================
# FOCUS PLAN (DETERMINISTIC PERSONALIZED COACHING)
# =============================================================================

@router.get("/focus-plan")
async def get_focus_plan(user: User = Depends(get_current_user)):
    """
    Get the complete Focus Plan for the user.

    This is the new deterministic personalized coaching system that:
    1. Computes Cost Scores per coaching bucket from last 25 games
    2. Selects Primary/Secondary focus deterministically
    3. Selects personalized openings based on usage + stability
    4. Generates mission positions from user's own games

    Same user + same inputs = same plan (deterministic)
    Different users + different inputs = different plan (personalized)

    Coaching Buckets:
    - PIECE_SAFETY: Hanging pieces
    - THREAT_AWARENESS: Missed opponent threats
    - TACTICAL_EXECUTION: Missed tactics
    - ADVANTAGE_DISCIPLINE: Failed conversion when ahead
    - OPENING_STABILITY: Weak first 10-12 moves
    - TIME_DISCIPLINE: Late-game blunders
    - ENDGAME_FUNDAMENTALS: Conversion failures
    """
    from focus_plan_service import get_focus_page_data

    data = await get_focus_page_data(db, user.user_id)
    return data


@router.post("/focus-plan/regenerate")
async def regenerate_focus_plan(user: User = Depends(get_current_user)):
    """
    Force regenerate the focus plan.

    Useful after importing new games or when user wants fresh analysis.
    """
    from focus_plan_service import generate_focus_plan

    plan = await generate_focus_plan(db, user.user_id, force_regenerate=True)
    return plan


@router.post("/focus-plan/mission/start")
async def start_mission_session(user: User = Depends(get_current_user)):
    """
    Start a new mission session for active time tracking.

    Returns a session_id for tracking interactions.
    Active time is only counted when user interacts within idle threshold (12 sec).
    """
    from focus_plan_service import start_mission_session as start_session

    # Get active plan
    plan = await db.focus_plans.find_one(
        {"user_id": user.user_id, "is_active": True},
        {"_id": 0}
    )

    if not plan:
        return {"error": "No active plan found"}

    session = await start_session(db, user.user_id, plan["plan_id"])
    return session


class MissionInteractionRequest(BaseModel):
    session_id: str
    event_type: str  # "position_attempted", "replay_step", "heartbeat"
    event_data: Optional[Dict[str, Any]] = None


@router.post("/focus-plan/mission/interaction")
async def record_mission_interaction(
    request: MissionInteractionRequest,
    user: User = Depends(get_current_user)
):
    """
    Record a mission interaction to track active time.

    Event types:
    - "position_attempted": User attempted a position (correct/incorrect in event_data)
    - "replay_step": User played a move in guided replay
    - "heartbeat": Keep session alive (call every 5-10 seconds)

    Active time is accumulated only when events come within idle_pause_seconds (12 sec).
    """
    from focus_plan_service import update_mission_interaction

    result = await update_mission_interaction(
        db,
        request.session_id,
        request.event_type,
        request.event_data
    )
    return result


@router.post("/focus-plan/mission/complete")
async def complete_mission(
    session_id: str,
    user: User = Depends(get_current_user)
):
    """
    Mark a mission as complete.

    Updates weekly progress and records completion.
    """
    from focus_plan_service import complete_mission as complete_mission_fn

    result = await complete_mission_fn(db, session_id)
    return result


@router.get("/focus-plan/bucket-breakdown")
async def get_bucket_breakdown(user: User = Depends(get_current_user)):
    """
    Get detailed breakdown of cost scores per bucket.

    Useful for debugging and showing users why they got their focus.
    Returns all bucket costs with example positions.
    """
    from focus_plan_service import compute_bucket_costs, get_rating_band, DEFAULT_GAME_WINDOW

    # Get user
    user_doc = await db.users.find_one({"user_id": user.user_id}, {"_id": 0})
    rating = user_doc.get("rating", 1200) if user_doc else 1200

    # Get games and analyses
    games = await db.games.find(
        {"user_id": user.user_id, "is_analyzed": True},
        {"_id": 0}
    ).sort("imported_at", -1).to_list(DEFAULT_GAME_WINDOW)

    game_ids = [g["game_id"] for g in games]
    analyses = await db.game_analyses.find(
        {"game_id": {"$in": game_ids}},
        {"_id": 0}
    ).to_list(DEFAULT_GAME_WINDOW)

    # Compute costs
    bucket_costs = compute_bucket_costs(analyses, games, rating)
    band = get_rating_band(rating)

    return {
        "rating": rating,
        "rating_band": band["label"],
        "allowed_buckets": band["allowed_buckets"],
        "bucket_costs": bucket_costs,
    }


@router.get("/focus-plan/last-game-audit")
async def get_last_game_audit(user: User = Depends(get_current_user)):
    """
    Audit the user's last game against their active focus plan.

    Returns:
    - rules_audit: List of rules with Executed/Partial/Missed status
    - overall_alignment: Overall alignment status
    - violations: Key moments that didn't align with the focus
    - good_moments: Moments that showed good execution
    """
    from focus_plan_service import get_focus_page_data, audit_last_game

    # Use get_focus_page_data to ensure plan is generated/active
    data = await get_focus_page_data(db, user.user_id)
    plan = data.get("plan")

    if not plan:
        return {"error": "No plan available", "has_audit": False}

    audit = await audit_last_game(db, user.user_id, plan)
    return audit


# ==================== COACHING LOOP ====================

@router.get("/round-preparation")
async def get_round_preparation(user: User = Depends(get_current_user)):
    """
    Get Round Preparation (Next Game Plan).

    This is the coach's plan for the user's next game.
    Generated using the DETERMINISTIC ADAPTIVE COACH system.

    Inputs used:
    - Rating band (granular: 600-1000, 1000-1400, 1400-1800, 1800+)
    - Last 25 games fundamentals profile
    - Weakness patterns with evidence
    - Opening stability recommendations
    - Domain history (consecutive misses/executions)
    - Critical insights from last game's mistakes

    Intensity (1-5) adjusts per domain based on consecutive failures.
    """
    from deterministic_coach_service import generate_round_preparation

    plan = await generate_round_preparation(db, user.user_id)

    # Remove audit fields for preparation view (they should be empty anyway)
    for card in plan.get("cards", []):
        card["audit"] = {"status": None, "data_points": [], "evidence": [], "coach_note": None}

    return plan


@router.get("/plan-audit")
async def get_plan_audit_data(user: User = Depends(get_current_user)):
    """
    Get Plan Audit (Last Game vs Previous Plan).

    Evaluates the user's last analyzed game against the plan we gave them.
    This is NOT a game summary - it's compliance evaluation.

    Uses DETERMINISTIC ADAPTIVE COACH for:
    - Rating-band adjusted thresholds
    - Evidence-backed audit items (links to specific moves)
    - Deterministic coach notes

    Returns the audited PlanCard with status (executed/partial/missed) for each domain.
    """
    from deterministic_coach_service import generate_plan_audit

    result = await generate_plan_audit(db, user.user_id)
    return result


@router.post("/coaching-loop/audit-game/{game_id}")
async def audit_specific_game(game_id: str, user: User = Depends(get_current_user)):
    """
    Manually trigger audit for a specific game.

    This is called after game analysis completes to:
    1. Audit the game against the current plan
    2. Generate a new plan for the next game (adaptive loop continues)
    """
    from deterministic_coach_service import (
        audit_game_against_plan,
        generate_round_preparation
    )

    # Get the active plan
    active_plan = await db.user_plans.find_one(
        {"user_id": user.user_id, "is_active": True, "is_audited": False},
        {"_id": 0}
    )

    if not active_plan:
        # Generate a plan first
        active_plan = await generate_round_preparation(db, user.user_id)

    # Get game and analysis
    game = await db.games.find_one({"game_id": game_id, "user_id": user.user_id}, {"_id": 0})
    analysis = await db.game_analyses.find_one({"game_id": game_id, "user_id": user.user_id}, {"_id": 0})

    if not game or not analysis:
        return {"error": "Game or analysis not found"}

    # Audit the game
    audited_plan = audit_game_against_plan(active_plan, game, analysis)

    # Update plan in database
    await db.user_plans.update_one(
        {"plan_id": active_plan["plan_id"]},
        {"$set": audited_plan}
    )

    # Generate new plan (adaptive loop continues)
    new_plan = await generate_round_preparation(db, user.user_id)

    return {
        "audited_plan": audited_plan,
        "new_plan": new_plan
    }


@router.post("/coaching-loop/regenerate-plan")
async def regenerate_plan(user: User = Depends(get_current_user)):
    """
    Force regenerate the user's plan.

    Use this if the user wants a fresh plan without auditing.
    Uses the DETERMINISTIC ADAPTIVE COACH system.
    """
    from deterministic_coach_service import generate_round_preparation

    # Invalidate existing active plans
    await db.user_plans.update_many(
        {"user_id": user.user_id, "is_active": True},
        {"$set": {"is_active": False}}
    )

    # Generate fresh plan
    plan = await generate_round_preparation(db, user.user_id)

    return plan


@router.get("/coaching-loop/profile")
async def get_coaching_loop_profile(user: User = Depends(get_current_user)):
    """
    Get the user's full coaching profile.

    Returns all the inputs used for DETERMINISTIC ADAPTIVE COACH:
    - Rating band (granular: 600-1000, 1000-1400, 1400-1800, 1800+)
    - Fundamentals profile (last 25 games)
    - Weakness patterns with evidence
    - Opening stability recommendations
    - Domain history (consecutive misses/executions)
    - Training block with intensity (1-5)
    """
    from deterministic_coach_service import get_coaching_profile

    profile = await get_coaching_profile(db, user.user_id)
    return profile


# ==================== AUTO-COACH ====================

@router.get("/coach/commentary/{game_id}")
async def get_coach_commentary(game_id: str, user: User = Depends(get_current_user)):
    """
    Get or generate coaching commentary for a game.
    """
    from subscription_service import has_feature_access
    from auto_coach_service import generate_and_save_commentary

    # Check if user has LLM commentary access
    has_access = await has_feature_access(db, user.user_id, "llm_commentary")

    if not has_access:
        return {
            "commentary": None,
            "access_denied": True,
            "message": "Upgrade to Pro for AI coaching commentary"
        }

    # Get analysis
    analysis = await db.game_analyses.find_one(
        {"game_id": game_id, "user_id": user.user_id},
        {"_id": 0}
    )

    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")

    # Check if commentary already exists
    if analysis.get("coach_commentary"):
        return {
            "commentary": analysis["coach_commentary"],
            "generated_at": analysis.get("coach_commentary_generated_at"),
            "cached": True
        }

    # Get game data
    game = await db.games.find_one(
        {"game_id": game_id, "user_id": user.user_id},
        {"_id": 0}
    )

    # Generate commentary
    commentary = await generate_and_save_commentary(db, analysis, game)

    if commentary:
        return {
            "commentary": commentary,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "cached": False
        }

    return {
        "commentary": None,
        "error": "Failed to generate commentary"
    }


@router.post("/coach/trigger-analysis/{game_id}")
async def trigger_auto_coach_analysis(
    game_id: str,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user)
):
    """
    Trigger auto-coach analysis for a specific game.
    This generates deterministic summary + LLM commentary + notification.
    """
    from subscription_service import can_analyze_game, has_feature_access, increment_analysis_count
    from auto_coach_service import build_deterministic_summary, generate_and_save_commentary, get_quick_notification_message
    from notification_service import notify_game_analyzed

    # Check analysis limit
    can_do = await can_analyze_game(db, user.user_id)
    if not can_do["allowed"]:
        return can_do

    # Get analysis and game
    analysis = await db.game_analyses.find_one(
        {"game_id": game_id, "user_id": user.user_id},
        {"_id": 0}
    )

    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")

    game = await db.games.find_one(
        {"game_id": game_id, "user_id": user.user_id},
        {"_id": 0}
    )

    # Build deterministic summary
    summary = build_deterministic_summary(analysis, game)

    # Generate notification message
    notification_message = get_quick_notification_message(summary)

    # Create notification
    await notify_game_analyzed(
        db,
        user.user_id,
        game_id,
        notification_message,
        summary["result"]
    )

    # Generate LLM commentary in background if user has access
    has_llm_access = await has_feature_access(db, user.user_id, "llm_commentary")
    if has_llm_access:
        background_tasks.add_task(generate_and_save_commentary, db, analysis, game)

    # Increment analysis count
    await increment_analysis_count(db, user.user_id)

    return {
        "success": True,
        "summary": summary,
        "notification": notification_message,
        "llm_commentary_queued": has_llm_access
    }


# ==================== BREAKTHROUGH SIGNAL ====================

@router.get("/coach/breakthrough-signal")
async def get_breakthrough_signal(
    user: User = Depends(get_current_user)
):
    """
    Get the user's current breakthrough/plateau signal (Step 8).

    Computes on-demand from last 20 games + memory.
    Returns state, headline, message, and recommended action.

    Response schema:
    {
        "state": "PLATEAU|BREAKTHROUGH|CONFIDENCE_ILLUSION|TILT_RISK|STABLE_GROWTH|NORMAL",
        "confidence": 0.0-1.0,
        "headline": "string",
        "message": "string",
        "cta": {"label": "string", "action": "string", "payload": {}},
        "dominant_lesson_key": "string|null",
        "show_card": bool  # True if user has >= 10 analyzed games
    }
    """
    from coach_state.breakthrough_service import get_breakthrough_signal_for_user

    # Get user's recent analyzed games (up to 20)
    # Look for analyses with stockfish_analysis (indicates real analysis)
    recent_analyses = await db.game_analyses.find(
        {"user_id": user.user_id, "stockfish_analysis": {"$exists": True}},
        {"_id": 0, "game_id": 1, "result": 1, "user_color": 1,
         "stockfish_analysis": 1, "game_coach_summary": 1, "analyzed_at": 1}
    ).sort("analyzed_at", -1).limit(20).to_list(20)

    # Check minimum games threshold
    if len(recent_analyses) < 10:
        return {
            "show_card": False,
            "state": "NORMAL",
            "confidence": 0.5,
            "headline": "Keep going. Stay consistent.",
            "message": "Play more games to unlock weekly coaching insights.",
            "cta": {"label": "Play Next Game", "action": "STANDARD_FLOW", "payload": {}},
            "dominant_lesson_key": None,
            "games_needed": 10 - len(recent_analyses)
        }

    # Build game data for signal computation
    recent_games = []
    lesson_keys = []

    for analysis in recent_analyses:
        sf = analysis.get("stockfish_analysis", {})
        summary = analysis.get("game_coach_summary", {})

        # Count blunders and mistakes from move evaluations
        move_evals = sf.get("move_evaluations", [])

        # Determine which moves are user's based on user_color
        user_color = analysis.get("user_color", "white")

        blunders = 0
        mistakes = 0
        total_cp_loss = 0
        user_move_count = 0

        for i, m in enumerate(move_evals):
            # Determine if this is user's move based on move number parity
            # White plays on odd move numbers (1, 3, 5...), Black on even (2, 4, 6...)
            move_num = m.get("move_number", i + 1)
            is_user_move = (user_color == "white" and move_num % 2 == 1) or \
                          (user_color == "black" and move_num % 2 == 0)

            if is_user_move:
                cp_loss = m.get("cp_loss", 0)
                total_cp_loss += cp_loss
                user_move_count += 1

                # Classify based on cp_loss thresholds
                if cp_loss >= 200:  # Blunder
                    blunders += 1
                elif cp_loss >= 100:  # Mistake
                    mistakes += 1

        # Calculate average cp_loss for user moves
        avg_cp = total_cp_loss / max(user_move_count, 1)

        # Determine result
        result = analysis.get("result", "draw")
        user_color = analysis.get("user_color", "white")
        if result == "1-0":
            game_result = "win" if user_color == "white" else "loss"
        elif result == "0-1":
            game_result = "win" if user_color == "black" else "loss"
        else:
            game_result = "draw"

        recent_games.append({
            "blunders": blunders,
            "mistakes": mistakes,
            "avg_cp_loss": avg_cp,
            "result": game_result,
        })

        # Get lesson key from summary
        lesson_key = summary.get("lesson_key") or summary.get("primary_issue")
        if lesson_key:
            lesson_keys.append(lesson_key)

    # Get coach state for maturity tier
    coach_state = await db.coach_states.find_one(
        {"user_id": user.user_id},
        {"_id": 0, "behavioral_maturity": 1, "good_game_streak": 1,
         "recent_game_accuracies": 1, "milestones": 1}
    )

    maturity_tier = "Developing"
    good_game_streak = 0
    milestone_recent = False
    recent_accuracies = []

    if coach_state:
        maturity = coach_state.get("behavioral_maturity", {})
        maturity_tier = maturity.get("level", "Developing")
        good_game_streak = coach_state.get("good_game_streak", 0)
        recent_accuracies = coach_state.get("recent_game_accuracies", [])

        # Check for recent milestone (last 5 games)
        milestones = coach_state.get("milestones", [])
        if milestones:
            recent_milestones = [m for m in milestones[-5:] if m.get("achieved")]
            milestone_recent = len(recent_milestones) > 0

    # Detect improvement trajectory
    improvement_trajectory = "stable"
    if len(recent_accuracies) >= 5:
        first_half = recent_accuracies[:len(recent_accuracies)//2]
        second_half = recent_accuracies[len(recent_accuracies)//2:]
        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)
        diff = (avg_second - avg_first) / max(avg_first, 1) * 100
        if diff > 5:
            improvement_trajectory = "improving"
        elif diff < -5:
            improvement_trajectory = "declining"

    # Calculate consecutive losses
    consecutive_losses = 0
    for g in recent_games:
        if g["result"] == "loss":
            consecutive_losses += 1
        else:
            break

    # Find dominant lesson key and intensity
    dominant_lesson_key = None
    dominant_lesson_intensity = 0
    if lesson_keys:
        from collections import Counter
        lesson_counts = Counter(lesson_keys)
        dominant_lesson_key, count = lesson_counts.most_common(1)[0]
        # Intensity based on frequency
        dominant_lesson_intensity = 1 if count < 3 else (2 if count < 5 else 3)

    # Get signal
    signal = get_breakthrough_signal_for_user(
        recent_games=recent_games,
        lesson_keys=lesson_keys,
        consecutive_losses=consecutive_losses,
        good_game_streak=good_game_streak,
        milestone_recent=milestone_recent,
        dominant_lesson_key=dominant_lesson_key,
        dominant_lesson_intensity=dominant_lesson_intensity,
        improvement_trajectory=improvement_trajectory,
        discipline_improving=improvement_trajectory == "improving",
        maturity_tier=maturity_tier,
    )

    # Build CTA with action-specific payload
    cta_payload = {}
    if signal.state == "PLATEAU":
        cta_payload = {"force_theme": dominant_lesson_key}
    elif signal.state == "CONFIDENCE_ILLUSION":
        cta_payload = {"lock_lesson_key": dominant_lesson_key, "duration_games": 5}
    elif signal.state == "TILT_RISK":
        cta_payload = {"duration_games": 3, "lock_theme": True}

    # === ENHANCE WITH DEEP MEMORY INSIGHTS ===
    # If state is NORMAL, add personalized insights from PlayerIdentity
    enhanced_message = signal.coach_message
    enhanced_headline = signal.headline

    if signal.state == "NORMAL":
        try:
            from services.player_identity import PlayerIdentityService
            identity_service = PlayerIdentityService(db)
            identity = await identity_service.get_or_create(user.user_id)

            if identity.games_analyzed >= 5:
                insights = []

                # Blunder focus
                if identity.blunder_taxonomy.most_common_type:
                    blunder_type = identity.blunder_taxonomy.most_common_type.value.replace("_", " ")
                    insights.append(f"Your main weakness: {blunder_type}")

                # Phase focus
                if identity.blunder_taxonomy.worst_phase:
                    phase = identity.blunder_taxonomy.worst_phase.value
                    insights.append(f"Focus on: {phase} play")

                # Trend
                if identity.blunder_taxonomy.trend == "improving":
                    enhanced_headline = "Making progress!"
                    insights.append("Your blunder rate is decreasing")
                elif identity.blunder_taxonomy.trend == "worsening":
                    enhanced_headline = "Let's refocus."
                    insights.append("Blunder rate increasing - slow down")

                # Behavioral
                if identity.consecutive_losses >= 2:
                    enhanced_headline = "Take a breath."
                    insights.append(f"You've lost {identity.consecutive_losses} in a row")
                elif identity.consecutive_wins >= 3:
                    enhanced_headline = "On fire!"
                    insights.append(f"{identity.consecutive_wins}-game win streak!")

                # Build enhanced message
                if insights:
                    enhanced_message = " | ".join(insights)
        except Exception as e:
            logger.warning(f"Could not enhance signal with deep memory: {e}")

    return {
        "show_card": True,
        "state": signal.state,
        "confidence": signal.confidence,
        "headline": enhanced_headline,
        "message": enhanced_message,
        "cta": {
            "label": signal.cta,
            "action": signal.recommended_action,
            "payload": cta_payload
        },
        "dominant_lesson_key": signal.dominant_lesson_key
    }


# =============================================================================
# FOCUS LOCK ENDPOINTS (Step 9)
# =============================================================================

class FocusLockActivateRequest(BaseModel):
    """Request to activate a focus lock."""
    lesson_key: str
    games: int = 5  # Will be overridden below after import


# Import focus lock constants and functions
from coach_state.focus_lock_service import (
    create_focus_lock,
    focus_lock_from_db,
    focus_lock_to_db,
    get_lock_ui_state,
    should_trigger_deep_session,
    RULE_DESCRIPTIONS,
    DEFAULT_LOCK_GAMES,
)

# Update the default for games field
FocusLockActivateRequest.model_fields["games"].default = DEFAULT_LOCK_GAMES


@router.get("/coach/focus-lock")
async def get_focus_lock(
    user: User = Depends(get_current_user)
):
    """
    Get the user's current focus lock state (Step 9).

    This is a READ-ONLY endpoint. Never computes compliance here.
    Returns computed state from DB.

    Response schema when lock is active:
    {
        "active": true,
        "lesson_key": "FORCING_BLIND",
        "rule_description": "...",
        "state": "ACTIVE|EXTENDED|STRICT|COMPLETED|FAILED",
        "headline": "...",
        "message": "...",
        "progress": {"completed": 2, "required": 5, "text": "2 of 5 games"},
        "compliance": {"average": 75, "color": "yellow", "text": "..."},
        "strict_mode": false,
        "cta": "Start Next Game",
        "should_trigger_deep_session": false
    }

    Response when no lock:
    {
        "active": false
    }
    """
    # Get coach state with focus lock
    coach_state = await db.coach_states.find_one(
        {"user_id": user.user_id},
        {"_id": 0, "focus_lock": 1}
    )

    if not coach_state or not coach_state.get("focus_lock"):
        return {"active": False}

    lock = focus_lock_from_db(coach_state.get("focus_lock"))
    if not lock:
        return {"active": False}

    # Get UI-ready state
    ui_state = get_lock_ui_state(lock)

    if not ui_state:
        return {"active": False}

    # Add deep session trigger flag
    ui_state["should_trigger_deep_session"] = should_trigger_deep_session(lock)
    ui_state["failed_cycles"] = lock.failed_cycles

    return ui_state


@router.post("/coach/focus-lock/activate")
async def activate_focus_lock(
    req: FocusLockActivateRequest,
    user: User = Depends(get_current_user)
):
    """
    Activate a focus lock for the user (Step 9).

    Guardrails - Reject activation if:
    - Lock already active
    - < 10 games analyzed
    - Breakthrough state active (BREAKTHROUGH or TILT_RISK in recovery)

    Only internal calls should hit this (triggered by breakthrough service).

    Request body:
    {
        "lesson_key": "FORCING_BLIND|STOPPED_CALCULATION_EARLY|THREAT_VERIFICATION",
        "games": 5  # Optional, default 5
    }
    """
    # Validate lesson_key
    valid_keys = ("FORCING_BLIND", "STOPPED_CALCULATION_EARLY", "THREAT_VERIFICATION")
    if req.lesson_key not in valid_keys:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid lesson_key. Must be one of: {valid_keys}"
        )

    # Check if user has enough analyzed games
    # Check for analyses with stockfish_analysis (indicates real analysis)
    analyzed_count = await db.game_analyses.count_documents({
        "user_id": user.user_id,
        "stockfish_analysis": {"$exists": True}
    })

    if analyzed_count < 10:
        raise HTTPException(
            status_code=400,
            detail=f"Need at least 10 analyzed games. You have {analyzed_count}."
        )

    # Get current coach state
    coach_state = await db.coach_states.find_one(
        {"user_id": user.user_id},
        {"_id": 0, "focus_lock": 1}
    )

    # Check if lock already active
    if coach_state and coach_state.get("focus_lock"):
        existing_lock = focus_lock_from_db(coach_state.get("focus_lock"))
        if existing_lock and existing_lock.state not in ("COMPLETED", "FAILED", "NONE"):
            raise HTTPException(
                status_code=400,
                detail=f"Focus lock already active for {existing_lock.lesson_key}. Complete current lock first."
            )

    # Create new focus lock
    new_lock = create_focus_lock(req.lesson_key, req.games)

    # Persist to DB (upsert coach_state if needed)
    await db.coach_states.update_one(
        {"user_id": user.user_id},
        {
            "$set": {
                "focus_lock": focus_lock_to_db(new_lock),
                "focus_lock_activated_at": datetime.now(timezone.utc).isoformat()
            }
        },
        upsert=True
    )

    logger.info(f"Focus lock activated for user {user.user_id}: {req.lesson_key} for {req.games} games")

    return {
        "status": "activated",
        "lesson_key": new_lock.lesson_key,
        "rule_description": RULE_DESCRIPTIONS.get(new_lock.lesson_key, ""),
        "games_required": new_lock.games_required,
        "headline": new_lock.headline,
        "message": new_lock.message
    }


@router.post("/coach/focus-lock/deactivate")
async def deactivate_focus_lock(
    user: User = Depends(get_current_user)
):
    """
    Force-deactivate a focus lock (admin/debug use only).

    Sets lock state to NONE.
    Logs as quit_mid_lock for analytics.
    """
    # Get existing lock before deactivating (for analytics)
    coach_state = await db.coach_states.find_one(
        {"user_id": user.user_id},
        {"_id": 0, "focus_lock": 1}
    )

    existing_lock = None
    if coach_state and coach_state.get("focus_lock"):
        existing_lock = focus_lock_from_db(coach_state.get("focus_lock"))

    result = await db.coach_states.update_one(
        {"user_id": user.user_id},
        {"$set": {"focus_lock": None}}
    )

    if result.modified_count > 0:
        # Log quit_mid_lock for analytics (if there was an active lock)
        if existing_lock and existing_lock.state not in ("COMPLETED", "FAILED", "NONE"):
            from coach_state.focus_lock_service import create_cycle_log
            cycle_log = create_cycle_log(user.user_id, existing_lock)
            await db.focus_lock_analytics.insert_one(cycle_log.to_dict())
            logger.info(f"[FOCUS LOCK ANALYTICS] Logged quit: user={user.user_id}, "
                        f"games_completed={existing_lock.games_completed}/{existing_lock.games_required}")

        logger.info(f"Focus lock deactivated for user {user.user_id}")
        return {"status": "deactivated"}
    else:
        return {"status": "no_lock_found"}


# =============================================================================
# THEORY MODULE ENDPOINTS (Step 10)
# =============================================================================

from coach_state.theory_modules import ALL_MODULES
from coach_state.module_trigger_service import get_module_injection_stats


@router.get("/coach/module/{game_id}")
async def get_game_module(
    game_id: str,
    user: User = Depends(get_current_user)
):
    """
    Get the theory module trigger for a specific game (Step 10).

    Returns the detected module, rule, and evidence for the Lab page.

    Response schema:
    {
        "triggered": true,
        "module_key": "SIMPLIFY_WHEN_AHEAD",
        "module_name": "Simplify When Ahead",
        "category": "conversion",
        "rule": "Trade pieces, reduce counterplay.",
        "explanation": "...",
        "evidence_move": 23,
        "evidence_cp_loss": 388,
        "confidence": "high"
    }
    """
    # Get game analysis with module trigger
    analysis = await db.game_analyses.find_one(
        {"game_id": game_id, "user_id": user.user_id},
        {"_id": 0, "module_trigger": 1}
    )

    if not analysis or not analysis.get("module_trigger"):
        return {"triggered": False}

    return analysis.get("module_trigger")


@router.get("/coach/modules/stats")
async def get_module_stats(
    user: User = Depends(get_current_user)
):
    """
    Get module injection statistics for the user (Step 10).

    Returns aggregate stats on which modules have been triggered.
    """
    injections = await db.module_injections.find(
        {"user_id": user.user_id},
        {"_id": 0}
    ).to_list(100)

    stats = get_module_injection_stats(injections)
    return stats


@router.get("/coach/modules/all")
async def get_all_modules():
    """
    Get all available theory modules (Step 10).

    Returns the full list of 30 modules with their rules.
    """
    return {
        "count": len(ALL_MODULES),
        "modules": [m.to_dict() for m in ALL_MODULES.values()]
    }


# ==================== PATTERN LEARNING API ====================
# Self-learning pattern recognition system for improving coach accuracy

@router.post("/coach/pattern-learning/feedback")
async def submit_pattern_feedback(
    request: Dict = Body(...),
    user: User = Depends(get_current_user)
):
    """
    Submit feedback when a coach explanation is wrong.

    This triggers the self-learning system to:
    1. Store the feedback
    2. Generate a corrected explanation immediately
    3. Learn a new classification rule for similar positions

    Body:
    - position_fen: FEN of the position before the move
    - move_played: The move that was played (UCI or SAN)
    - move_san: SAN notation of the move (optional)
    - system_classification: What the system classified it as (e.g., "MISSED_TRAP")
    - system_explanation: The explanation the system gave
    - correct_classification: What it actually was (e.g., "WALKED_INTO_FORK")
    - user_explanation: User's explanation of what went wrong (optional)
    - eval_before: Eval before move in centipawns (optional)
    - eval_after: Eval after move in centipawns (optional)
    - best_move: What Stockfish recommends (optional)
    - pv_after_played: Principal variation after the played move (optional)
    - game_id: Game ID for context (optional)
    - move_number: Move number (optional)
    - user_color: "white" or "black" (optional)

    Returns:
    - success: True if feedback was processed
    - feedback_id: ID of the stored feedback
    - corrected_explanation: The corrected explanation to show the user
    - pattern: The correct pattern classification
    - learning_status: "queued", "correction_exists", or "rule_generated"
    """
    from services.pattern_learning.auto_correction_service import get_auto_correction_service

    service = get_auto_correction_service()

    result = await service.submit_feedback_and_correct(
        user_id=user.user_id,
        position_fen=request.get("position_fen", ""),
        move_played=request.get("move_played", ""),
        system_classification=request.get("system_classification", ""),
        system_explanation=request.get("system_explanation", ""),
        correct_classification=request.get("correct_classification", ""),
        user_explanation=request.get("user_explanation", ""),
        move_san=request.get("move_san", ""),
        eval_before=request.get("eval_before", 0.0),
        eval_after=request.get("eval_after", 0.0),
        best_move=request.get("best_move", ""),
        pv_after_played=request.get("pv_after_played", []),
        game_id=request.get("game_id", ""),
        move_number=request.get("move_number", 0),
        user_color=request.get("user_color", "white")
    )

    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to process feedback"))

    logger.info(f"Pattern feedback submitted: {result.get('feedback_id')} - {result.get('learning_status')}")

    return result


@router.get("/coach/pattern-learning/my-feedback")
async def get_my_feedback(user: User = Depends(get_current_user)):
    """
    Get the current user's submitted feedback with corrections.

    Returns:
    - List of feedback submissions with status and corrections
    """
    feedback_list = []

    # Get user's feedback
    cursor = db.pattern_feedback.find(
        {"user_id": user.user_id}
    ).sort("created_at", -1).limit(50)

    async for doc in cursor:
        feedback_id = doc.get("feedback_id")

        # Get corresponding correction if exists
        correction = await db.verified_corrections.find_one(
            {"feedback_id": feedback_id},
            {"_id": 0}
        )

        feedback_list.append({
            "feedback_id": feedback_id,
            "created_at": doc.get("created_at"),
            "status": doc.get("status", "pending"),
            "position_fen": doc.get("position_fen"),
            "move_played": doc.get("move_played"),
            "best_move": doc.get("best_move"),
            "move_number": doc.get("move_number"),
            "game_id": doc.get("game_id"),
            "section_type": doc.get("section_type"),
            "system_classification": doc.get("system_classification"),
            "system_explanation": doc.get("system_explanation"),
            "correct_classification": doc.get("correct_classification"),
            "user_explanation": doc.get("user_explanation"),
            "correction": correction
        })

    return {"feedback": feedback_list, "count": len(feedback_list)}


@router.get("/coach/pattern-learning/stats")
async def get_pattern_learning_stats(user: User = Depends(get_current_user)):
    """
    Get statistics about the pattern learning system.

    Returns:
    - feedback: Feedback statistics (pending, processed, total)
    - rules: Rule statistics (by status, total triggers, accuracy)
    - corrections: Correction statistics (by motif, usage counts)
    - loaded_rules: Currently active rules summary
    """
    from services.pattern_learning.auto_correction_service import get_auto_correction_service

    service = get_auto_correction_service()
    stats = await service.get_system_stats()

    return stats


@router.get("/coach/pattern-learning/pending-rules")
async def get_pending_rules(user: User = Depends(get_current_user)):
    """
    Get rules pending human review.

    Use this to review and approve/reject learned rules.
    """
    from services.pattern_learning.auto_correction_service import get_auto_correction_service

    service = get_auto_correction_service()
    rules = await service.get_pending_rules()

    return {
        "count": len(rules),
        "rules": rules
    }


@router.post("/coach/pattern-learning/approve-rule")
async def approve_learned_rule(
    request: Dict = Body(...),
    user: User = Depends(get_current_user)
):
    """
    Approve a pending learned rule.

    Body:
    - rule_id: The rule ID to approve
    """
    from services.pattern_learning.auto_correction_service import get_auto_correction_service

    rule_id = request.get("rule_id")
    if not rule_id:
        raise HTTPException(status_code=400, detail="rule_id is required")

    service = get_auto_correction_service()
    await service.approve_rule(rule_id, approved_by=user.user_id)

    logger.info(f"Rule {rule_id} approved by {user.user_id}")

    return {
        "success": True,
        "message": f"Rule {rule_id} approved and activated"
    }


@router.post("/coach/pattern-learning/reject-rule")
async def reject_learned_rule(
    request: Dict = Body(...),
    user: User = Depends(get_current_user)
):
    """
    Reject a pending learned rule.

    Body:
    - rule_id: The rule ID to reject
    - reason: Reason for rejection
    """
    from services.pattern_learning.auto_correction_service import get_auto_correction_service

    rule_id = request.get("rule_id")
    reason = request.get("reason", "Rejected by admin")

    if not rule_id:
        raise HTTPException(status_code=400, detail="rule_id is required")

    service = get_auto_correction_service()
    await service.reject_rule(rule_id, reason)

    logger.info(f"Rule {rule_id} rejected by {user.user_id}: {reason}")

    return {
        "success": True,
        "message": f"Rule {rule_id} rejected"
    }


@router.post("/coach/pattern-learning/classify")
async def classify_with_learned_rules(
    request: Dict = Body(...),
    user: User = Depends(get_current_user)
):
    """
    Classify a move using learned rules.

    Use this to check if learned rules provide better classification
    than the hardcoded classifier.

    Body:
    - position_fen: FEN before the move
    - move_played: The move that was played
    - pv_after_played: Principal variation after the move
    - eval_drop: Evaluation drop in pawns
    - best_move: What Stockfish recommends (optional)
    - user_color: "white" or "black" (optional)

    Returns:
    - classification: The classification result (if found)
    - has_learned_rule: Whether a learned rule matched
    """
    from services.pattern_learning.auto_correction_service import get_auto_correction_service

    service = get_auto_correction_service()

    result = await service.classify_with_learned_rules(
        position_fen=request.get("position_fen", ""),
        move_played=request.get("move_played", ""),
        pv_after_played=request.get("pv_after_played", []),
        eval_drop=request.get("eval_drop", 0.0),
        best_move=request.get("best_move"),
        user_color=request.get("user_color", "white")
    )

    if result:
        return {
            "has_learned_rule": True,
            "classification": {
                "pattern": result.pattern,
                "confidence": result.confidence,
                "explanation": result.explanation,
                "rule_id": result.rule_id,
                "matched_signals": result.matched_signals
            }
        }

    return {
        "has_learned_rule": False,
        "classification": None
    }


@router.post("/coach/pattern-learning/track-accuracy")
async def track_rule_accuracy(
    request: Dict = Body(...),
    user: User = Depends(get_current_user)
):
    """
    Track whether a learned rule classification was correct.

    Use this after showing a classification to the user to
    update the rule's accuracy statistics.

    Body:
    - rule_id: The rule that was used
    - was_correct: True if the classification was correct
    """
    from services.pattern_learning.auto_correction_service import get_auto_correction_service

    rule_id = request.get("rule_id")
    was_correct = request.get("was_correct", True)

    if not rule_id:
        raise HTTPException(status_code=400, detail="rule_id is required")

    service = get_auto_correction_service()
    await service.track_classification_feedback(rule_id, was_correct)

    return {
        "success": True,
        "message": "Accuracy tracked"
    }
