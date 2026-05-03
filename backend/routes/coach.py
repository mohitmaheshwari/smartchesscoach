"""
Coach Routes
============

Handles all coach-related functionality including:
- Coach state and analytics
- Play with Coach mode
- Deep session management
- Coach memory and summaries
- Maturity tracking
- Focus lock

This is a large module covering the AI coaching features.
"""

from fastapi import APIRouter, HTTPException, Depends, Body
from pydantic import BaseModel
from typing import Optional, List, Dict
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

# Create router for coach endpoints
router = APIRouter(prefix="/coach", tags=["Coach"])

# Database reference - will be set by server.py
db = None

# LLM function reference
call_llm = None

def set_db(database):
    """Set the database reference for coach routes"""
    global db
    db = database

def set_llm(llm_func):
    """Set the LLM function reference"""
    global call_llm
    call_llm = llm_func


# Import User model and get_current_user from auth routes
from routes.auth import User, get_current_user


# ==================== MODELS ====================

class CoachMoveRequest(BaseModel):
    session_id: str
    move: str
    thinking_time_ms: Optional[int] = None


class CoachFeedbackRequest(BaseModel):
    session_id: str
    move_number: int
    feedback_type: str  # helpful, not_helpful, wrong
    comment: Optional[str] = ""


# ==================== CORE STATE ENDPOINTS ====================

@router.get("/state")
async def get_coach_state(user: User = Depends(get_current_user)):
    """
    Get current coach state including:
    - Active focus area
    - Session status
    - Maturity level
    """
    global db
    
    user_doc = await db.users.find_one({"user_id": user.user_id})
    if not user_doc:
        return {"state": "new_user", "focus": None}
    
    # Get active focus
    focus_lock = await db.focus_locks.find_one({
        "user_id": user.user_id,
        "active": True
    })
    
    # Get maturity
    maturity = await db.coach_maturity.find_one({"user_id": user.user_id})
    
    return {
        "state": "active",
        "focus": focus_lock.get("focus_type") if focus_lock else None,
        "maturity_level": maturity.get("level", 1) if maturity else 1,
        "rating": user_doc.get("assessed_rating", 1200)
    }


# /today and /habits moved to routes/coach_advanced.py


# ==================== MEMORY & SUMMARIES ====================

@router.get("/memory-summary")
async def get_memory_summary(user: User = Depends(get_current_user)):
    """
    Get coach's memory of the user - what patterns have been observed.
    """
    global db
    
    # Get recent analyses
    analyses = await db.game_analyses.find(
        {"user_id": user.user_id},
        {"_id": 0}
    ).sort("created_at", -1).limit(20).to_list(20)
    
    # Aggregate patterns
    patterns = {}
    for analysis in analyses:
        for blunder in analysis.get("blunders", []):
            category = blunder.get("mistake_category", "unknown")
            patterns[category] = patterns.get(category, 0) + 1
    
    # Sort by frequency
    sorted_patterns = sorted(patterns.items(), key=lambda x: x[1], reverse=True)
    
    return {
        "games_analyzed": len(analyses),
        "top_patterns": sorted_patterns[:5],
        "total_patterns": len(patterns)
    }


# /game-summary/{game_id} moved to routes/coach_advanced.py


# ==================== MISTAKE EXPLANATION ====================

class ExplainMistakeRequest(BaseModel):
    fen_before: str
    played_move: str = ""  # SAN notation
    played_move_uci: str
    best_move: str = ""  # SAN notation
    best_move_uci: str
    eval_before: int = 0
    eval_after: int = 0
    move_number: int = 1
    pv_after_played: List[str] = []
    pv_after_best: List[str] = []
    user_color: str = "white"


@router.post("/explain-mistake")
async def explain_mistake_endpoint(request: ExplainMistakeRequest):
    """
    Generate a human-readable explanation for why a move was a mistake.
    
    Parses ACTUAL Stockfish PV lines - NO LLM, no hallucination.
    
    The explanation comes from:
    1. Parsing each move in the PV line
    2. Detecting captures, checks, material changes
    3. Mapping patterns to golden rules
    4. Generating clear English from parsed data
    """
    from services.line_parser import explain_line
    
    try:
        # Calculate eval loss
        eval_loss = abs(request.eval_after - request.eval_before)
        
        explanation = explain_line(
            fen_before=request.fen_before,
            played_move=request.played_move,
            played_move_uci=request.played_move_uci,
            best_move=request.best_move,
            best_move_uci=request.best_move_uci,
            pv_after_played=request.pv_after_played,
            pv_after_best=request.pv_after_best,
            eval_loss=eval_loss
        )
        
        return explanation
    except Exception as e:
        logger.error(f"Error explaining mistake: {e}")
        return {
            "headline": "Analysis unavailable",
            "explanation": "Could not analyze this position. Please try another move.",
            "rule": "Review the suggested move to understand what was missed.",
            "arrows": [],
            "category": "unknown"
        }


# ==================== THEORY DATABASE (Admin) ====================

@router.get("/theory/stats")
async def get_theory_stats():
    """Get statistics about the theory database."""
    from services.chess_theory_service import get_theory_service
    
    service = get_theory_service()
    return {
        "stats": service.get_theory_stats(),
        "status": "ok"
    }


@router.get("/theory/openings")
async def get_opening_patterns():
    """Get all opening theory patterns (admin view)."""
    from services.chess_theory_service import get_theory_service
    
    service = get_theory_service()
    return {
        "patterns": service.get_all_opening_patterns(),
        "count": len(service.get_all_opening_patterns())
    }


@router.get("/theory/endgames")
async def get_endgame_patterns():
    """Get all endgame theory patterns (admin view)."""
    from services.chess_theory_service import get_theory_service
    
    service = get_theory_service()
    return {
        "patterns": service.get_all_endgame_patterns(),
        "count": len(service.get_all_endgame_patterns())
    }


@router.get("/theory/tactical")
async def get_tactical_patterns():
    """Get all tactical patterns (admin view)."""
    from services.chess_theory_service import get_theory_service
    
    service = get_theory_service()
    return {
        "patterns": service.get_all_tactical_patterns(),
        "count": len(service.get_all_tactical_patterns())
    }


@router.get("/theory/rules")
async def get_positional_rules():
    """Get all positional rules / golden rules (admin view)."""
    from services.chess_theory_service import get_theory_service

    service = get_theory_service()
    return {
        "rules": service.get_all_positional_rules(),
        "count": len(service.get_all_positional_rules())
    }


@router.get("/trap-intelligence")
async def get_trap_intelligence(user: User = Depends(get_current_user)):
    """
    Return the user's trap encounter intelligence — which opening traps
    they've hit in their games, which they executed, which they fell for.

    Powers the Lab-page "Trap Intelligence" card. Returns `has_data: False`
    when the user has no trap encounters (card is hidden by the frontend).
    """
    from services.trap_intelligence import get_user_trap_intelligence
    global db

    try:
        result = await get_user_trap_intelligence(db, user.user_id)
        return result
    except Exception as e:
        logger.warning(f"trap-intelligence failed for {user.user_id}: {e}")
        return {"has_data": False, "top_insight": None, "all_insights": [], "total_encounters": 0}


@router.get("/opening-report")
async def get_opening_report(user: User = Depends(get_current_user)):
    """
    Per-user opening repertoire report — games/wins/losses/accuracy
    grouped by canonical opening + color. Identifies the one opening
    where the user is frequently losing.
    """
    from services.opening_report_card import get_user_opening_report
    global db

    try:
        return await get_user_opening_report(db, user.user_id)
    except Exception as e:
        logger.warning(f"opening-report failed for {user.user_id}: {e}")
        return {
            "has_data": False, "total_games": 0,
            "as_white": {}, "as_black": {},
            "problem_opening": None, "all_openings_flat": [],
        }


@router.get("/graduation-insight")
async def get_graduation(user: User = Depends(get_current_user)):
    """
    Per-user graduation classifier. Returns 'graduate' (celebrate — blunder
    rate dropped ≥25%), 'struggler' (≥20 games, no improvement — surface
    fleet graduate paths), or 'new' (hidden).
    """
    from services.peer_learning import get_graduation_insight
    global db

    try:
        return await get_graduation_insight(db, user.user_id)
    except Exception as e:
        logger.warning(f"graduation-insight failed for {user.user_id}: {e}")
        return {"has_data": False, "status": "new", "headline": "", "subline": ""}


@router.get("/mirror-session")
async def mirror_session(user: User = Depends(get_current_user)):
    """Return the current open Mirror window — same data the home page
    Evidence section uses, but exposed as a dedicated endpoint so the
    Lab session panel can render without coupling to /home/coach-home.

    Side-effect-free. The window is only closed (snapshot persisted +
    pointer advanced) when the frontend POSTs /coach/mirror-engaged.
    """
    from services.game_mirror import build_game_mirror
    global db
    try:
        mirror = await build_game_mirror(db, user.user_id)
        return mirror or {"window_size": 0, "game_ids": [], "story": ""}
    except Exception as e:
        logger.warning(f"mirror-session failed for {user.user_id}: {e}")
        return {"window_size": 0, "game_ids": [], "story": ""}


class MirrorEngagedRequest(BaseModel):
    reason: str  # "lab_open" | "game_open" | "train_click" | "opening_click"


@router.post("/mirror-engaged")
async def mirror_engaged(
    body: MirrorEngagedRequest,
    user: User = Depends(get_current_user),
):
    """Frontend pings this when the user takes an action that proves
    they engaged with the Mirror's call-out: opens Lab session view,
    clicks through to a specific game, clicks a Train CTA, etc.

    We snapshot the current window's state so the next Mirror can ask
    "did the flagged pattern actually disappear?" — then advance the
    pointer so the next window is fresh.

    Idempotent — calling this when there's nothing in the window just
    advances opened_at without snapshotting.
    """
    from services.game_mirror import build_game_mirror
    from services.mirror_engagement import close_window
    global db

    try:
        # Compute the current window's contents so we can persist the
        # exact patterns_flagged snapshot. We re-use build_game_mirror
        # so frontend and snapshot see the same state.
        mirror = await build_game_mirror(db, user.user_id)
        if not mirror:
            await close_window(
                db, user.user_id,
                closed_reason=body.reason,
                game_ids=[],
                patterns_flagged=[],
                outcomes={"won": 0, "lost": 0, "drawn": 0},
            )
            return {"closed": True, "snapshotted": False}

        await close_window(
            db, user.user_id,
            closed_reason=body.reason,
            game_ids=mirror.get("game_ids") or [],
            patterns_flagged=mirror.get("patterns_repeated") or [],
            outcomes=mirror.get("outcomes") or {},
        )
        return {
            "closed": True,
            "snapshotted": True,
            "game_count": mirror.get("window_size"),
            "patterns_snapshotted": mirror.get("patterns_repeated") or [],
        }
    except Exception as e:
        logger.warning(f"mirror-engaged failed for {user.user_id}: {e}")
        return {"closed": False, "error": "internal"}


@router.get("/opening-fit")
async def get_opening_fit(user: User = Depends(get_current_user)):
    """Per-user opening fit: which openings to play more, which to
    avoid for now. Combines win rate + Mirror's weakness patterns +
    per-opening theory burden, scaled by the user's rating so the
    same logic works for a 1200 or an 1800.
    """
    from services.opening_fit import build_opening_fit
    global db
    try:
        return await build_opening_fit(db, user.user_id)
    except Exception as e:
        logger.warning(f"opening-fit failed for {user.user_id}: {e}")
        return {"has_data": False, "rating_used": 1500,
                "play_more": [], "avoid": []}


@router.get("/opening-benchmark")
async def get_opening_benchmark(user: User = Depends(get_current_user)):
    """
    Compare user's opening_knowledge mistake share vs their rating band
    average. Only surfaces when user is meaningfully above band avg.
    """
    from services.peer_learning import get_opening_benchmark_insight
    global db

    try:
        return await get_opening_benchmark_insight(db, user.user_id)
    except Exception as e:
        logger.warning(f"opening-benchmark failed for {user.user_id}: {e}")
        return {"has_data": False, "user_pct": 0, "band_pct": 0, "band": ""}


@router.get("/repeat-mistakes")
async def get_repeat_mistakes(user: User = Depends(get_current_user)):
    """
    Cross-game repeat-mistake detection — identifies recurring mistake
    patterns (same cognitive gap, same piece type, same phase) across
    ≥3 distinct games. The "you do this every time" signal.
    """
    from services.repeat_mistake_detector import get_user_repeat_mistakes
    global db

    try:
        return await get_user_repeat_mistakes(db, user.user_id)
    except Exception as e:
        logger.warning(f"repeat-mistakes failed for {user.user_id}: {e}")
        return {
            "has_data": False, "top_pattern": None,
            "all_patterns": [], "total_games_analyzed": 0,
        }


@router.post("/theory/reload")
async def reload_theory():
    """Reload theory database from JSON (after admin edits)."""
    from services.chess_theory_service import get_theory_service
    
    service = get_theory_service()
    service.reload_theory()
    
    return {
        "status": "reloaded",
        "stats": service.get_theory_stats()
    }


# ==================== PATTERN MEMORY ====================

@router.get("/patterns/summary")
async def get_patterns_summary(user: User = Depends(get_current_user)):
    """
    Get aggregated pattern summary for Pattern Memory feature.
    
    This is the core "confrontation" data:
    - "You've ignored opponent threats 23 times in your last 20 games"
    - "Overall: 113 times"
    
    Returns:
        {
            "patterns": [
                {
                    "pattern_type": "ignore_threat",
                    "label": "Ignoring Opponent Threats",
                    "total_count": 113,
                    "recent_count": 23,
                    "recent_games": 20,
                    "severity": "critical",
                    "sample_games": ["game_abc", ...]
                },
                ...
            ],
            "total_games_analyzed": 50,
            "worst_pattern": "ignore_threat"
        }
    """
    global db
    from services.pattern_memory_service import get_pattern_summary
    
    try:
        summary = await get_pattern_summary(db, user.user_id)
        return summary
    except Exception as e:
        logger.error(f"Error getting pattern summary: {e}")
        return {
            "patterns": [],
            "total_games_analyzed": 0,
            "worst_pattern": None,
            "error": str(e)
        }


@router.get("/patterns/top")
async def get_top_patterns_endpoint(
    limit: int = 3,
    user: User = Depends(get_current_user)
):
    """
    Get user's top N worst patterns for dashboard display.
    
    Simple endpoint for the "Your Patterns" dashboard section.
    Returns patterns sorted by severity and count.
    """
    global db
    from services.pattern_memory_service import get_top_patterns
    
    try:
        patterns = await get_top_patterns(db, user.user_id, limit)
        return {"patterns": patterns}
    except Exception as e:
        logger.error(f"Error getting top patterns: {e}")
        return {"patterns": [], "error": str(e)}


@router.get("/patterns/for-mistake/{cognitive_gap}")
async def get_pattern_for_mistake_endpoint(
    cognitive_gap: str,
    user: User = Depends(get_current_user)
):
    """
    Get pattern data for a specific cognitive gap/mistake type.
    
    Used on the review page when showing a mistake:
    "You've made this mistake 23 times in your last 20 games. Overall: 113 times."
    
    Args:
        cognitive_gap: The cognitive gap type (e.g., "ignore_threat", "tactical_oversight")
    
    Returns:
        Pattern data with confrontation message, or null if not found.
    """
    global db
    from services.pattern_memory_service import get_pattern_for_mistake
    
    try:
        pattern = await get_pattern_for_mistake(db, user.user_id, cognitive_gap)
        return {"pattern": pattern}
    except Exception as e:
        logger.error(f"Error getting pattern for mistake: {e}")
        return {"pattern": None, "error": str(e)}


# ==================== GAME DECRYPTION ====================

class FeedbackRequest(BaseModel):
    """Request model for submitting coaching feedback."""
    game_id: str
    move_number: int
    fen: str
    coach_explanation: str
    user_feedback: str  # "not_helpful" or "helpful"
    user_correction: Optional[str] = None  # User's suggested correction
    is_user_move: bool = True


@router.get("/decryption/{game_id}")
async def get_game_decryption(
    game_id: str,
    user: User = Depends(get_current_user)
):
    """
    Get the complete move-by-move coaching decryption for a game.
    
    This data is pre-computed during analysis and stored in game_analyses.
    Returns coaching narratives for every move in the game.
    
    Returns:
        {
            "decryption_data": [
                {
                    "move_number": 1,
                    "is_user_move": true,
                    "move_san": "e4",
                    "phase": "opening",
                    "what_happened": "Advanced the king pawn two squares",
                    "move_idea": "Fighting for central control",
                    "opponent_last_idea": null,
                    "your_focus": "Focus on developing pieces...",
                    "is_mistake": false,
                    ...
                },
                ...
            ],
            "summary": {
                "total_moves": 45,
                "mistakes": 3,
                "key_moments": [...],
                "overall_message": "..."
            }
        }
    """
    global db
    
    try:
        logger.info(f"[DECRYPTION] Looking for analysis for game_id: {game_id}")
        analysis = await db.game_analyses.find_one(
            {"game_id": game_id},
            {"_id": 0, "game_id": 1, "decryption_data": 1, "decryption_summary": 1, "decryption_generated_at": 1}
        )
        
        logger.info(f"[DECRYPTION] Analysis query result: {analysis}")
        
        if not analysis or "game_id" not in analysis:
            # Debug: count total documents
            total = await db.game_analyses.count_documents({})
            logger.info(f"[DECRYPTION] Total game_analyses documents: {total}")
            return {"error": "Game analysis not found", "decryption_data": None}
        
        if not analysis.get("decryption_data"):
            # Check if generation is already in progress
            if analysis.get("decryption_generating"):
                return {
                    "decryption_data": None,
                    "status": "generating",
                    "message": "Your game is being analyzed by the coach. This takes about 30 seconds..."
                }
            
            # Kick off background generation
            logger.info(f"[DECRYPTION] No decryption_data, starting background generation")
            
            full_analysis = await db.game_analyses.find_one(
                {"game_id": game_id}, {"_id": 0}
            )
            game = await db.games.find_one(
                {"game_id": game_id},
                {"_id": 0, "pgn": 1, "user_color": 1, "user_plays_as": 1}
            )
            
            if full_analysis and game:
                # Mark as generating
                await db.game_analyses.update_one(
                    {"game_id": game_id},
                    {"$set": {"decryption_generating": True}}
                )
                
                import asyncio
                
                async def _background_generate():
                    try:
                        from services.game_decryption_service import (
                            generate_game_decryption, generate_game_summary,
                            detect_opening_from_pgn, get_opening_data
                        )
                        user_color = game.get("user_color") or game.get("user_plays_as", "white")
                        pgn = game.get("pgn", "")
                        move_evaluations = full_analysis.get("stockfish_analysis", {}).get("move_evaluations", [])
                        
                        loop = asyncio.get_event_loop()
                        decryption_data = await loop.run_in_executor(
                            None, generate_game_decryption, pgn, user_color, move_evaluations
                        )
                        
                        if decryption_data:
                            opening_name, eco_code = detect_opening_from_pgn(pgn)
                            opening_data = get_opening_data(eco_code, opening_name)
                            decryption_summary = generate_game_summary(decryption_data, user_color, opening_data)
                            
                            from datetime import datetime, timezone
                            await db.game_analyses.update_one(
                                {"game_id": game_id},
                                {"$set": {
                                    "decryption_data": decryption_data,
                                    "decryption_summary": decryption_summary,
                                    "decryption_generated_at": datetime.now(timezone.utc).isoformat(),
                                    "decryption_generating": False
                                }}
                            )
                            logger.info(f"[DECRYPTION] Background generation complete for {game_id}")
                        else:
                            await db.game_analyses.update_one(
                                {"game_id": game_id},
                                {"$set": {"decryption_generating": False}}
                            )
                    except Exception as e:
                        logger.error(f"[DECRYPTION] Background generation failed: {e}")
                        await db.game_analyses.update_one(
                            {"game_id": game_id},
                            {"$set": {"decryption_generating": False}}
                        )
                
                asyncio.create_task(_background_generate())
                
                return {
                    "decryption_data": None,
                    "status": "generating",
                    "message": "Your game is being analyzed by the coach. This takes about 30 seconds..."
                }
            
            return {
                "error": "Decryption data not available. Game may need re-analysis.",
                "decryption_data": None,
                "needs_reanalysis": True
            }
        
        return {
            "decryption_data": analysis.get("decryption_data", []),
            "summary": analysis.get("decryption_summary", {}),
            "generated_at": analysis.get("decryption_generated_at")
        }
        
    except Exception as e:
        logger.error(f"Error getting game decryption: {e}")
        return {"error": str(e), "decryption_data": None}


@router.post("/decryption/feedback")
async def submit_coaching_feedback(
    request: FeedbackRequest,
    user: User = Depends(get_current_user)
):
    """
    Submit feedback on a coaching explanation.
    
    Users can mark explanations as "not helpful" and provide corrections.
    This data is stored for improving the coaching system.
    """
    global db
    
    try:
        feedback_doc = {
            "user_id": user.user_id,
            "game_id": request.game_id,
            "move_number": request.move_number,
            "fen": request.fen,
            "is_user_move": request.is_user_move,
            "coach_explanation": request.coach_explanation,
            "user_feedback": request.user_feedback,
            "user_correction": request.user_correction,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        
        await db.coaching_feedback.insert_one(feedback_doc)
        
        logger.info(f"Coaching feedback submitted for game {request.game_id}, move {request.move_number}")
        
        return {
            "success": True,
            "message": "Thank you for your feedback! This helps improve the coaching."
        }
        
    except Exception as e:
        logger.error(f"Error submitting coaching feedback: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/decryption/feedback/{game_id}")
async def get_feedback_for_game(
    game_id: str,
    user: User = Depends(get_current_user)
):
    """Get all feedback submitted for a game by the current user."""
    global db
    
    try:
        feedback_cursor = db.coaching_feedback.find(
            {"game_id": game_id, "user_id": user.user_id},
            {"_id": 0}
        )
        feedback_list = await feedback_cursor.to_list(100)
        
        return {"feedback": feedback_list}
        
    except Exception as e:
        logger.error(f"Error getting feedback: {e}")
        return {"feedback": [], "error": str(e)}


# ==================== DECRYPTION V5 (Thinking Simulator) ====================

@router.get("/decryption/v5/{game_id}")
async def get_game_decryption_v5(
    game_id: str,
    user: User = Depends(get_current_user)
):
    """
    Get V5 "Thinking Simulator" coaching for a game.
    
    V5 Key Features:
    - Coaches EVERY move (user + opponent)
    - Extracts PLANS (transferable knowledge, not just moves)
    - Tracks concept acknowledgment
    - Simple, 1200-friendly language
    
    Returns:
        {
            "decryption_data": [...],  # V5 coaching for each move
            "status": "complete" | "generating",
            "concepts_to_acknowledge": [...],  # Concepts with "I understand" buttons
        }
    """
    global db
    
    try:
        logger.info(f"[DECRYPTION V5] Looking for analysis for game_id: {game_id}")
        
        # Check for existing V5 data
        analysis = await db.game_analyses.find_one(
            {"game_id": game_id},
            {"_id": 0, "game_id": 1, "decryption_v5_data": 1, "decryption_v5_generated_at": 1, "decryption_v5_generating": 1, "decryption_v5_version": 1}
        )
        
        if not analysis or "game_id" not in analysis:
            return {"error": "Game analysis not found", "decryption_data": None}
        
        # Auto-regenerate if V5 coaching version is outdated
        from services.game_decryption_v5_service import V5_COACHING_VERSION
        stored_version = analysis.get("decryption_v5_version", 1)
        if analysis.get("decryption_v5_data") and stored_version < V5_COACHING_VERSION:
            logger.info(f"[DECRYPTION V5] Outdated coaching v{stored_version} → v{V5_COACHING_VERSION} for {game_id}, clearing for regeneration")
            await db.game_analyses.update_one(
                {"game_id": game_id},
                {"$unset": {"decryption_v5_data": "", "decryption_v5_generating": "", "decryption_v5_generated_at": ""}}
            )
            analysis["decryption_v5_data"] = None  # Force regeneration below
        
        # If V5 data exists, return it
        if analysis.get("decryption_v5_data"):
            # Get concepts that need acknowledgment
            concepts_to_acknowledge = []
            for move_data in analysis.get("decryption_v5_data", []):
                if move_data.get("needs_acknowledgment") and not move_data.get("already_acknowledged"):
                    if move_data.get("concept_id"):
                        concepts_to_acknowledge.append({
                            "concept_id": move_data["concept_id"],
                            "concept_type": move_data.get("concept_type"),
                            "move_number": move_data.get("move_number"),
                            "prompt": move_data.get("acknowledgment_prompt")
                        })
            
            return {
                "decryption_data": analysis.get("decryption_v5_data", []),
                "status": "complete",
                "generated_at": analysis.get("decryption_v5_generated_at"),
                "concepts_to_acknowledge": concepts_to_acknowledge,
                "habits_report": analysis.get("habits_report")
            }
        
        # Check if generation is in progress
        if analysis.get("decryption_v5_generating"):
            return {
                "decryption_data": None,
                "status": "generating",
                "message": "Your coach is analyzing every move. This takes about 45 seconds..."
            }
        
        # Start background generation
        full_analysis = await db.game_analyses.find_one(
            {"game_id": game_id}, {"_id": 0}
        )
        game = await db.games.find_one(
            {"game_id": game_id},
            {"_id": 0, "pgn": 1, "user_color": 1, "user_plays_as": 1}
        )
        
        if full_analysis and game:
            # Mark as generating
            await db.game_analyses.update_one(
                {"game_id": game_id},
                {"$set": {"decryption_v5_generating": True}}
            )
            
            import asyncio
            
            async def _background_generate_v5():
                try:
                    from services.game_decryption_v5_service import generate_game_decryption_v5
                    
                    user_color = game.get("user_color") or game.get("user_plays_as", "white")
                    pgn = game.get("pgn", "")
                    move_evaluations = full_analysis.get("stockfish_analysis", {}).get("move_evaluations", [])
                    
                    decryption_data = await generate_game_decryption_v5(
                        pgn, user_color, move_evaluations, user.user_id, db
                    )
                    
                    if decryption_data:
                        # Phase 5: surface CCT discipline as a top-level
                        # narrative line. When the analyzer detected
                        # held-initiative-after-miss segments OR a
                        # strong CCT streak, the line celebrates that
                        # specifically. When no CCT signal, returns None
                        # and the field stays empty — frontend treats
                        # null as "don't render."
                        cct_narrative = None
                        try:
                            from services.cct_voice import game_review_cct_line
                            cct_narrative = game_review_cct_line(
                                full_analysis.get("cct"),
                                full_analysis.get("cct_held_initiative"),
                            )
                        except Exception as cct_voice_err:
                            logger.warning(f"CCT narrative failed (non-fatal): {cct_voice_err}")

                        # Generate habits analysis for the game
                        habits_report = None
                        try:
                            from services.player_habits_service import analyze_game_habits, update_player_profile
                            
                            # Build move_history from decryption data for habits analysis
                            move_history_for_habits = []
                            for md in decryption_data:
                                if md.get("is_user_move"):
                                    move_history_for_habits.append({
                                        "by": "player",
                                        "move": md.get("move_san"),
                                        "time_spent": md.get("time_spent", 0),
                                        "evaluation": md.get("severity", "good"),
                                        "fen_before": md.get("fen_before")
                                    })
                            
                            habits_report = analyze_game_habits(
                                move_history=move_history_for_habits,
                                evaluations=move_evaluations,
                                behavior_events=[],
                                user_color=user_color
                            )
                            
                            # Update aggregate player profile
                            if habits_report:
                                await update_player_profile(db, user.user_id, habits_report)
                        except Exception as e:
                            logger.warning(f"Habits analysis failed (non-critical): {e}")
                        
                        await db.game_analyses.update_one(
                            {"game_id": game_id},
                            {"$set": {
                                "decryption_v5_data": decryption_data,
                                "decryption_v5_generated_at": datetime.now(timezone.utc).isoformat(),
                                "decryption_v5_generating": False,
                                "decryption_v5_version": V5_COACHING_VERSION,
                                "habits_report": habits_report,
                                "cct_narrative": cct_narrative,
                            }}
                        )
                        logger.info(f"[DECRYPTION V5] Background generation complete for {game_id}")
                        
                        # Compute and store game summary for Lab list
                        try:
                            from services.game_summary_service import compute_and_store_summary
                            await compute_and_store_summary(db, game_id, user.user_id)
                        except Exception as summary_err:
                            logger.warning(f"[GAME SUMMARY] Failed to compute summary: {summary_err}")
                    else:
                        await db.game_analyses.update_one(
                            {"game_id": game_id},
                            {"$set": {"decryption_v5_generating": False}}
                        )
                except Exception as e:
                    logger.error(f"[DECRYPTION V5] Background generation failed: {e}")
                    import traceback
                    traceback.print_exc()
                    await db.game_analyses.update_one(
                        {"game_id": game_id},
                        {"$set": {"decryption_v5_generating": False}}
                    )
            
            asyncio.create_task(_background_generate_v5())
            
            return {
                "decryption_data": None,
                "status": "generating",
                "message": "Your coach is analyzing every move. This takes about 45 seconds..."
            }
        
        return {
            "error": "Game data not available for V5 analysis.",
            "decryption_data": None
        }
        
    except Exception as e:
        logger.error(f"Error getting game decryption V5: {e}")
        import traceback
        traceback.print_exc()
        return {"error": str(e), "decryption_data": None}


class ConceptAcknowledgmentRequest(BaseModel):
    concept_id: str


@router.post("/decryption/acknowledge")
async def acknowledge_concept(
    request: ConceptAcknowledgmentRequest,
    user: User = Depends(get_current_user)
):
    """
    Mark a concept as understood by the user.
    
    Called when user clicks "I understand" button on a coaching insight.
    This affects future coaching - the coach won't explain this concept
    in detail again, just briefly reference it.
    """
    global db
    
    try:
        from services.game_decryption_v5_service import acknowledge_concept as ack_concept
        
        success = await ack_concept(db, user.user_id, request.concept_id)
        
        if success:
            logger.info(f"User {user.user_id} acknowledged concept: {request.concept_id}")
            return {
                "success": True,
                "message": "Got it! I'll remember you understand this concept."
            }
        else:
            return {
                "success": False,
                "message": "Concept not found or already acknowledged."
            }
        
    except Exception as e:
        logger.error(f"Error acknowledging concept: {e}")
        return {"success": False, "error": str(e)}


@router.get("/concepts/acknowledged")
async def get_acknowledged_concepts(
    user: User = Depends(get_current_user)
):
    """
    Get all concepts the user has acknowledged understanding.
    
    This shows what the user has learned over time.
    """
    global db
    
    try:
        cursor = db.user_concept_understanding.find(
            {"user_id": user.user_id, "acknowledged": True},
            {"_id": 0, "concept_id": 1, "concept_type": 1, "concept_text": 1, "acknowledged_at": 1}
        )
        concepts = await cursor.to_list(100)
        
        # Group by type
        by_type = {
            "opening": [],
            "endgame": [],
            "tactical": [],
            "positional": []
        }
        
        for c in concepts:
            ct = c.get("concept_type", "positional")
            if ct in by_type:
                by_type[ct].append(c)
        
        return {
            "total": len(concepts),
            "by_type": by_type,
            "concepts": concepts
        }
        
    except Exception as e:
        logger.error(f"Error getting acknowledged concepts: {e}")
        return {"total": 0, "by_type": {}, "concepts": [], "error": str(e)}


@router.get("/concepts/learning-progress")
async def get_learning_progress(
    user: User = Depends(get_current_user)
):
    """
    Get the user's learning progress - what they're getting better at.
    """
    global db
    
    try:
        from services.v5_learning_tracker import format_learning_summary_for_api
        
        summary = await format_learning_summary_for_api(db, user.user_id)
        return summary
        
    except ImportError:
        # Fallback to old method
        pipeline = [
            {"$match": {"user_id": user.user_id}},
            {"$group": {
                "_id": "$concept_type",
                "total_shown": {"$sum": "$shown_count"},
                "acknowledged": {"$sum": {"$cond": ["$acknowledged", 1, 0]}},
                "applied_correctly": {"$sum": "$applied_correctly_count"},
                "failed_to_apply": {"$sum": "$failed_to_apply_count"}
            }}
        ]
        
        stats = await db.user_concept_understanding.aggregate(pipeline).to_list(10)
        
        return {
            "summary": "Keep playing! Your coach is learning about you.",
            "stats": {},
            "by_type": {s["_id"]: s for s in stats}
        }
        
    except Exception as e:
        logger.error(f"Error getting learning progress: {e}")
        return {"summary": "", "stats": {}, "error": str(e)}


@router.get("/learning/insights")
async def get_learning_insights(
    user: User = Depends(get_current_user)
):
    """
    Get detailed learning insights including strengths and trends.
    """
    global db
    
    try:
        from services.v5_learning_tracker import get_learning_insights, get_user_strengths
        
        insights = await get_learning_insights(db, user.user_id)
        strengths = await get_user_strengths(db, user.user_id, limit=5)
        
        return {
            "message": insights.get("message", ""),
            "trend": insights.get("trend", "not_enough_data"),
            "stats": {
                "games_analyzed": insights.get("games_analyzed", 0),
                "best_move_rate": insights.get("overall_best_move_rate", 0),
                "concepts_learned": insights.get("concepts_learned", 0)
            },
            "strengths": strengths,
            "recent_accuracy": insights.get("recent_accuracy", [])
        }
        
    except Exception as e:
        logger.error(f"Error getting learning insights: {e}")
        return {"message": "Keep playing!", "stats": {}, "error": str(e)}
        
        # Get recent good moves (concepts applied)
        recent_good = await db.game_analyses.aggregate([
            {"$match": {"decryption_v5_data": {"$exists": True}}},
            {"$unwind": "$decryption_v5_data"},
            {"$match": {
                "decryption_v5_data.is_best_move": True,
                "decryption_v5_data.concept_applied": {"$ne": None}
            }},
            {"$group": {
                "_id": "$decryption_v5_data.concept_applied",
                "count": {"$sum": 1}
            }},
            {"$sort": {"count": -1}},
            {"$limit": 5}
        ]).to_list(5)
        
        return {
            "by_type": {s["_id"]: s for s in stats},
            "strengths": recent_good,
            "message": _generate_progress_message(stats, recent_good)
        }
        
    except Exception as e:
        logger.error(f"Error getting learning progress: {e}")
        return {"by_type": {}, "strengths": [], "error": str(e)}


def _generate_progress_message(stats: list, strengths: list) -> str:
    """Generate a personalized progress message."""
    if not stats:
        return "Keep playing! Your coach is learning about your chess understanding."
    
    total_ack = sum(s.get("acknowledged", 0) for s in stats)
    
    if total_ack == 0:
        return "You haven't acknowledged any concepts yet. Click 'I understand' when lessons are clear."
    
    if strengths:
        top = strengths[0]["_id"].replace("_", " ") if strengths[0]["_id"] else "good moves"
        return f"You're getting better at {top}! Keep it up."
    
    return f"You've learned {total_ack} concepts. Great progress!"


# ==================== MOVE Q&A ====================

class MoveQuestionRequest(BaseModel):
    fen: str
    question: str
    played_move: Optional[str] = None
    depth: int = 18


@router.post("/ask-move")
async def ask_move_question(request: MoveQuestionRequest):
    """
    Answer a question about a move, like "why Na5 and not Nf5?"

    Uses Stockfish to compare moves and explains the difference in coaching language.
    Also detects and logs the user's thinking pattern for personalization.
    """
    from services.move_qa_service import answer_move_question

    try:
        result = await answer_move_question(
            fen=request.fen,
            question=request.question,
            played_move=request.played_move,
            depth=request.depth
        )

        # Log the question as coaching data (non-blocking)
        if not result.get("error") and request.fen:
            try:
                from datetime import datetime, timezone
                await db.question_insights.insert_one({
                    "fen": request.fen,
                    "question": request.question,
                    "parsed_move": result.get("alternative_move"),
                    "comparison": result.get("comparison"),
                    "eval_difference": result.get("eval_difference"),
                    "thinking_pattern": result.get("thinking_pattern", {}).get("id", "unknown"),
                    "thinking_label": result.get("thinking_pattern", {}).get("label", "Unknown"),
                    "coaching_signal": result.get("thinking_pattern", {}).get("coaching_signal", "neutral"),
                    "severity": result.get("thinking_pattern", {}).get("severity", "unknown"),
                    "asked_at": datetime.now(timezone.utc).isoformat(),
                })
            except Exception as log_err:
                logger.warning(f"Failed to log question insight: {log_err}")

        return result
    except Exception as e:
        logger.error(f"Error answering move question: {e}")
        return {
            "error": "Could not process the question.",
            "details": str(e)
        }


@router.get("/last-game-summary")
async def get_last_game_summary(user: User = Depends(get_current_user)):
    """Get summary of the most recent game."""
    global db
    
    # Get most recent game
    game = await db.games.find_one(
        {"user_id": user.user_id},
        {"_id": 0}
    )
    
    if not game:
        return {"message": "No games found"}
    
    # Get analysis
    analysis = await db.game_analyses.find_one({
        "game_id": game["game_id"]
    }, {"_id": 0})
    
    return {
        "game_id": game["game_id"],
        "result": game.get("result"),
        "opponent": game.get("opponent_name", "Unknown"),
        "analysis_available": analysis is not None,
        "blunders": analysis.get("blunders", 0) if analysis else 0
    }


# ==================== MATURITY TRACKING ====================

@router.get("/maturity")
async def get_coach_maturity(user: User = Depends(get_current_user)):
    """Get user's coaching maturity level."""
    global db
    
    maturity = await db.coach_maturity.find_one({"user_id": user.user_id})
    
    if not maturity:
        return {
            "level": 1,
            "xp": 0,
            "next_level_xp": 100,
            "message": "Welcome! Let's start your chess journey."
        }
    
    return {
        "level": maturity.get("level", 1),
        "xp": maturity.get("xp", 0),
        "next_level_xp": maturity.get("next_level_xp", 100),
        "achievements": maturity.get("achievements", [])
    }


@router.post("/maturity/update")
async def update_coach_maturity(
    request: Dict = Body(...),
    user: User = Depends(get_current_user)
):
    """Update maturity based on activity."""
    global db
    
    xp_gained = request.get("xp", 10)
    activity = request.get("activity", "unknown")
    
    maturity = await db.coach_maturity.find_one({"user_id": user.user_id})
    
    if not maturity:
        maturity = {"user_id": user.user_id, "level": 1, "xp": 0, "next_level_xp": 100}
    
    new_xp = maturity.get("xp", 0) + xp_gained
    level = maturity.get("level", 1)
    next_level_xp = maturity.get("next_level_xp", 100)
    
    # Level up check
    leveled_up = False
    if new_xp >= next_level_xp:
        level += 1
        new_xp = new_xp - next_level_xp
        next_level_xp = int(next_level_xp * 1.5)
        leveled_up = True
    
    await db.coach_maturity.update_one(
        {"user_id": user.user_id},
        {"$set": {
            "level": level,
            "xp": new_xp,
            "next_level_xp": next_level_xp,
            "last_activity": activity,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }},
        upsert=True
    )
    
    return {
        "level": level,
        "xp": new_xp,
        "xp_gained": xp_gained,
        "leveled_up": leveled_up
    }


# Focus lock endpoints moved to routes/coach_advanced.py


# ==================== PLAY WITH COACH ====================
# NOTE: The main /play/start and /play/move endpoints are in server.py
# which has the full implementation with coach opponent, guardian, etc.
# The endpoints below were simplified duplicates that caused routing conflicts.
# They have been removed to ensure the full implementation is used.

# Legacy endpoints removed - use server.py's /coach/play/start and /coach/play/move


# /play/identity and /play/feedback moved to routes/coach_play.py


# ==================== ANALYTICS ====================

@router.get("/analytics/summary")
async def get_analytics_summary(user: User = Depends(get_current_user)):
    """Get summary analytics for the user."""
    global db
    
    # Count games
    total_games = await db.games.count_documents({"user_id": user.user_id})
    analyzed_games = await db.game_analyses.count_documents({"user_id": user.user_id})
    
    # Get reflection count
    reflections = await db.reflections.count_documents({"user_id": user.user_id})
    
    # Get puzzle stats
    puzzles_attempted = await db.puzzle_attempts.count_documents({"user_id": user.user_id})
    puzzles_correct = await db.puzzle_attempts.count_documents({
        "user_id": user.user_id,
        "correct": True
    })
    
    return {
        "total_games": total_games,
        "analyzed_games": analyzed_games,
        "reflections": reflections,
        "puzzles_attempted": puzzles_attempted,
        "puzzles_correct": puzzles_correct,
        "accuracy": round(puzzles_correct / puzzles_attempted * 100, 1) if puzzles_attempted > 0 else 0
    }


@router.get("/analytics/theme-history")
async def get_theme_history(user: User = Depends(get_current_user)):
    """Get history of themes/weaknesses worked on."""
    global db
    
    # Get puzzle attempts by weakness type
    pipeline = [
        {"$match": {"user_id": user.user_id}},
        {"$group": {
            "_id": "$weakness_type",
            "count": {"$sum": 1},
            "correct": {"$sum": {"$cond": ["$correct", 1, 0]}}
        }},
        {"$sort": {"count": -1}},
        {"$limit": 10}
    ]
    
    results = await db.puzzle_attempts.aggregate(pipeline).to_list(10)
    
    themes = []
    for r in results:
        if r["_id"]:
            themes.append({
                "theme": r["_id"],
                "attempts": r["count"],
                "correct": r["correct"],
                "accuracy": round(r["correct"] / r["count"] * 100, 1) if r["count"] > 0 else 0
            })
    
    return {"themes": themes}


# ==================== IDENTITY FORMATION LAYER ====================

@router.get("/identity/evolution")
async def get_identity_evolution(user: User = Depends(get_current_user)):
    """
    Get the user's identity evolution over time.
    
    Returns:
    - Current identity snapshot
    - Changes since last snapshot
    - Long-term trajectory
    - Milestones achieved
    """
    global db
    from services.identity_formation_service import compute_identity_evolution
    
    evolution = await compute_identity_evolution(db, user.user_id)
    return evolution


@router.get("/identity/snapshots")
async def get_identity_snapshots(
    limit: int = 12,
    user: User = Depends(get_current_user)
):
    """
    Get historical identity snapshots.
    
    Returns list of snapshots showing how identity evolved.
    """
    global db
    from services.identity_formation_service import get_snapshot_history
    
    snapshots = await get_snapshot_history(db, user.user_id, limit)
    
    return {
        "snapshots": [{
            "snapshot_id": s.get("snapshot_id"),
            "created_at": s.get("created_at"),
            "games_analyzed": s.get("games_analyzed"),
            "stability_label": s.get("stability_label"),
            "primary_leak": s.get("primary_leak"),
            "risk_style": s.get("risk_style"),
            "collapsed_summary": s.get("collapsed_summary"),
        } for s in snapshots],
        "count": len(snapshots)
    }


@router.post("/identity/snapshot")
async def create_manual_snapshot(user: User = Depends(get_current_user)):
    """
    Manually create an identity snapshot.
    
    Useful for marking a point in time (e.g., after completing training).
    """
    global db
    from player_identity_engine import compute_player_identity
    from services.identity_formation_service import create_identity_snapshot
    
    # Compute current identity
    identity = await compute_player_identity(db, user.user_id)
    
    if not identity.get("has_identity"):
        raise HTTPException(
            status_code=400, 
            detail="Not enough games to create identity snapshot"
        )
    
    # Create snapshot
    snapshot = await create_identity_snapshot(db, user.user_id, identity)
    
    return {
        "success": True,
        "snapshot_id": snapshot.get("snapshot_id"),
        "message": "Identity snapshot created"
    }


@router.get("/identity/trajectory")
async def get_identity_trajectory(user: User = Depends(get_current_user)):
    """
    Get the long-term trajectory of identity evolution.
    
    Shows overall direction: improving, declining, or stable.
    """
    global db
    from services.identity_formation_service import get_snapshot_history, compute_trajectory
    
    snapshots = await get_snapshot_history(db, user.user_id, limit=12)
    
    if len(snapshots) < 3:
        return {
            "has_trajectory": False,
            "reason": "Need at least 3 snapshots for trajectory analysis",
            "snapshots_available": len(snapshots)
        }
    
    trajectory = compute_trajectory(snapshots)
    
    return {
        "has_trajectory": True,
        **trajectory
    }


@router.get("/identity/insight")
async def get_identity_insight(user: User = Depends(get_current_user)):
    """
    Get a human-readable insight about identity evolution.
    
    Returns a single paragraph summarizing recent changes and trajectory.
    """
    global db
    from services.identity_formation_service import (
        compute_identity_evolution,
        generate_evolution_insight
    )
    
    evolution = await compute_identity_evolution(db, user.user_id)
    insight = generate_evolution_insight(evolution)
    
    return {
        "insight": insight,
        "has_evolution": evolution.get("has_evolution", False),
        "snapshot_count": evolution.get("snapshot_count", 0)
    }


@router.get("/behavioral-profile")
async def get_behavioral_profile(user: User = Depends(get_current_user)):
    """
    Get player's behavioral coaching profile.
    
    Returns:
        - Primary issue (impatient, hope_chess, lazy_checking, etc.)
        - All behavioral insights with coaching messages
        - Personalized process checklists
        - Coaching approach (gentle, direct, encouraging)
        - Progress narrative if available
    """
    global db
    from services.behavioral_coaching_layer import diagnose_player_behavior
    from services.player_identity import PlayerIdentityService
    
    # Get player identity
    identity_service = PlayerIdentityService(db)
    player_identity = await identity_service.get_player_identity(user.user_id)
    
    if not player_identity or player_identity.get("games_analyzed", 0) < 5:
        return {
            "has_profile": False,
            "message": "Play at least 5 games to get your behavioral profile",
            "games_analyzed": player_identity.get("games_analyzed", 0) if player_identity else 0
        }
    
    # Diagnose behavior
    profile = diagnose_player_behavior(player_identity)
    
    if not profile.primary_issue:
        return {
            "has_profile": True,
            "primary_issue": None,
            "message": "Great! No major behavioral patterns detected. Keep playing consistently.",
            "games_analyzed": player_identity.get("games_analyzed", 0)
        }
    
    # Convert to serializable format
    insights_data = []
    for insight in profile.all_insights:
        insights_data.append({
            "problem_type": insight.problem_type.value,
            "severity": insight.severity,
            "evidence": insight.evidence,
            "coaching_message": insight.coaching_message,
            "process_checklist": insight.process_checklist,
            "when_to_coach": insight.when_to_coach,
            "priority": insight.priority
        })
    
    return {
        "has_profile": True,
        "primary_issue": profile.primary_issue.value,
        "coaching_approach": profile.coaching_approach,
        "all_insights": insights_data,
        "custom_checklist": profile.custom_checklist,
        "games_analyzed": player_identity.get("games_analyzed", 0)
    }



@router.get("/identity/summary")
async def get_identity_summary(user: User = Depends(get_current_user)):
    """
    Get a summarized identity trajectory for UI display.
    
    Returns:
        - Current archetype (e.g., "The Calculating Attacker")
        - Stability and style labels
        - Trajectory direction
        - Comparative insight ("You used to be X, now you're Y")
        - Coaching moments
    """
    global db
    from services.identity_formation_service import get_identity_trajectory_summary
    
    summary = await get_identity_trajectory_summary(db, user.user_id)
    return summary




@router.post("/analyze/phase")
async def analyze_game_phase(
    request: dict,
    user: User = Depends(get_current_user)
):
    """
    Analyze game phase for a position.
    
    Request body:
        {"fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"}
    
    Returns:
        - Phase percentage (0=opening, 100=endgame)
        - Phase label (opening/middlegame/endgame)
        - Endgame type if applicable
        - Coaching priorities for this phase
        - Endgame-specific concepts and techniques
    """
    import chess
    from services.game_phase_service import GamePhaseCalculator, get_phase_coaching
    
    fen = request.get("fen", chess.STARTING_FEN)
    
    try:
        board = chess.Board(fen)
    except Exception as e:
        return {"error": f"Invalid FEN: {str(e)}"}
    
    calculator = GamePhaseCalculator()
    phase_info = calculator.calculate_phase(board)
    coaching = get_phase_coaching(phase_info)
    
    return {
        "phase_percent": phase_info.phase_percent,
        "phase_label": phase_info.phase_label.value,
        "endgame_weight": round(phase_info.endgame_weight, 2),
        "raw_phase": phase_info.raw_phase,
        "max_phase": 24,
        "white_material": phase_info.white_material,
        "black_material": phase_info.black_material,
        "coaching": coaching
    }



@router.post("/analyze/structure")
async def analyze_pawn_structure(
    request: dict,
    user: User = Depends(get_current_user)
):
    """
    Analyze pawn structure for a position.
    
    Request body:
        {"fen": "...", "for_color": "white"}
    
    Returns:
        - Structure type and name
        - Plans for both sides
        - Pawn features (isolated, doubled, passed, etc.)
        - Outposts and weak squares
        - Teaching content
    """
    import chess
    from services.pawn_structure_service import PawnStructureClassifier, get_structure_teaching
    
    fen = request.get("fen", chess.STARTING_FEN)
    for_color = request.get("for_color", "white")
    
    try:
        board = chess.Board(fen)
    except Exception as e:
        return {"error": f"Invalid FEN: {str(e)}"}
    
    classifier = PawnStructureClassifier()
    analysis = classifier.analyze(board)
    teaching = get_structure_teaching(analysis, for_color)
    
    return {
        "structure_type": analysis.structure_type.value,
        "structure_name": analysis.structure_name,
        "confidence": round(analysis.confidence, 2),
        "white_pawns": analysis.white_pawns,
        "black_pawns": analysis.black_pawns,
        "features": [
            {
                "type": f.type,
                "square": f.square,
                "color": f.color,
                "description": f.description,
                "is_weakness": f.is_weakness,
                "teaching_note": f.teaching_note
            }
            for f in analysis.features
        ],
        "isolated_pawns": analysis.isolated_pawns,
        "doubled_pawns": analysis.doubled_pawns,
        "passed_pawns": analysis.passed_pawns,
        "pawn_chains": analysis.pawn_chains,
        "outposts": analysis.outposts,
        "weak_squares": analysis.weak_squares,
        "white_plans": analysis.white_plans,
        "black_plans": analysis.black_plans,
        "teaching": teaching
    }


@router.post("/analyze/move-effect")
async def analyze_move_effect(
    request: dict,
    user: User = Depends(get_current_user)
):
    """
    Analyze the effects of a specific move.
    
    This is the core teaching API - explains WHY a move works.
    
    Request body:
        {"fen": "...", "move": "e2e4"}  (move in UCI format)
    
    Returns:
        - Main idea of the move
        - Teaching explanation
        - Threats created
        - Lines opened
        - Forcing nature
        - Follow-up suggestions
    """
    import chess
    from services.move_effect_analyzer import explain_move
    
    fen = request.get("fen", chess.STARTING_FEN)
    move_uci = request.get("move")
    
    if not move_uci:
        return {"error": "Move is required (in UCI format, e.g., 'e2e4')"}
    
    try:
        board = chess.Board(fen)
    except Exception as e:
        return {"error": f"Invalid FEN: {str(e)}"}
    
    result = explain_move(board, move_uci)
    return result


@router.post("/teaching/select-move")
async def select_teaching_move(
    request: dict,
    user: User = Depends(get_current_user)
):
    """
    Select an instructive move for the teaching coach to play.
    
    This is the heart of "play to teach" - the coach selects moves that
    CREATE LEARNING OPPORTUNITIES, not necessarily the strongest moves.
    
    Request body:
        {
            "fen": "...",                     # Current position
            "student_rating": 1200,           # Student's rating for calibration
            "student_weaknesses": ["tactics"], # Areas to focus on
            "teaching_focus": "piece_activity", # Specific concept to teach
            "game_phase": "middlegame"        # Current game phase
        }
    
    Returns:
        - Selected move with teaching goal
        - Why this move is instructive
        - Concept being taught
        - Challenge question for student
        - Teaching content (before/after explanations)
    """
    import chess
    from services.teaching_move_selector import select_teaching_move as select_move
    
    fen = request.get("fen", chess.STARTING_FEN)
    student_rating = request.get("student_rating", 1200)
    student_weaknesses = request.get("student_weaknesses", [])
    teaching_focus = request.get("teaching_focus")
    game_phase = request.get("game_phase", "middlegame")
    
    result = select_move(
        fen=fen,
        student_rating=student_rating,
        student_weaknesses=student_weaknesses,
        teaching_focus=teaching_focus,
        game_phase=game_phase
    )
    
    return result


@router.post("/teaching/feedback")
async def get_teaching_feedback(
    request: dict,
    user: User = Depends(get_current_user)
):
    """
    Generate real-time teaching feedback for a game moment.
    
    Uses Socratic questioning to guide student thinking.
    Adapts tone and complexity to student level.
    NOW INCLUDES: Behavioral coaching based on player's diagnosis!
    
    Request body:
        {
            "fen": "...",                     # Current position
            "last_move": "e2e4",              # Last move (UCI format, optional)
            "student_rating": 1200,           # Student's rating
            "phase": "before_student_move",   # Teaching phase
            "student_color": "white",         # Which color student plays
            "move_context": {                 # Optional context from move selector
                "teaching_goal": "tactics",
                "was_blunder": false,
                "last_move_time_ms": 1500,    # How long they thought
                ...
            }
        }
    
    Teaching phases:
        - game_start: Beginning of game
        - before_coach_move: Coach is about to play
        - after_coach_move: Coach just played
        - before_student_move: Student is thinking
        - after_student_move: Student just played
        - game_end: Game is over
    
    Returns:
        - Teaching message (possibly enhanced with behavioral coaching)
        - Feedback type (question, explanation, encouragement, etc.)
        - Related concept
        - Follow-up question
        - Hints
        - behavioral_coaching (if applicable)
    """
    from services.active_teaching_engine import generate_teaching_feedback
    from services.behavioral_coaching_layer import should_show_behavioral_coaching
    from services.player_identity import PlayerIdentityService
    import chess
    
    fen = request.get("fen", chess.STARTING_FEN)
    last_move = request.get("last_move")
    student_rating = request.get("student_rating", 1200)
    phase = request.get("phase", "before_student_move")
    student_color = request.get("student_color", "white")
    move_context = request.get("move_context", {})
    
    # Generate standard teaching feedback
    result = generate_teaching_feedback(
        fen=fen,
        last_move_uci=last_move,
        student_rating=student_rating,
        phase=phase,
        student_color=student_color,
        move_context=move_context
    )
    
    # === NEW: ADD BEHAVIORAL COACHING ===
    # Check if we should inject behavioral coaching based on player's profile
    try:
        # Get player identity
        identity_service = PlayerIdentityService(db)
        player_identity = await identity_service.get_player_identity(user.user_id)
        
        if player_identity and player_identity.get("games_analyzed", 0) >= 5:
            # Build game state for context
            game_state = {
                "eval_score": move_context.get("eval_score", 0),
                "last_move_time_ms": move_context.get("last_move_time_ms", 5000),
                "was_blunder": move_context.get("was_blunder", False),
                "position_type": move_context.get("position_type", "middlegame")
            }
            
            # Map teaching phase to behavioral context
            context_map = {
                "game_start": "at_game_start",
                "before_student_move": "before_move",
                "after_student_move": "after_move",
                "after_coach_move": "after_opponent_move"
            }
            behavioral_context = context_map.get(phase, "during_game")
            
            # Check if behavioral coaching should be shown
            should_show, coaching_message = should_show_behavioral_coaching(
                player_identity,
                behavioral_context,
                game_state
            )
            
            if should_show and coaching_message:
                # Inject behavioral coaching into the message
                # Prepend it so coach addresses behavioral issue first
                result["message"] = f"{coaching_message}\n\n{result['message']}"
                result["behavioral_coaching"] = True
                result["coaching_type"] = "behavioral"
                
                logger.info(f"Injected behavioral coaching for user {user.user_id} in phase {phase}")
            else:
                result["behavioral_coaching"] = False
        else:
            result["behavioral_coaching"] = False
            
    except Exception as e:
        # Don't let behavioral coaching errors break the main feedback
        logger.error(f"Error adding behavioral coaching: {e}")
        result["behavioral_coaching"] = False
    
    return result


@router.get("/teaching/structures")
async def list_all_structures(user: User = Depends(get_current_user)):
    """
    List all available pawn structures with basic info.
    
    Returns list of structures with name, type, main idea, and difficulty.
    """
    from services.structure_plan_database import get_all_structures
    
    structures = get_all_structures()
    return {"structures": structures, "count": len(structures)}


@router.post("/teaching/structure-plans")
async def get_structure_plans(
    request: dict,
    user: User = Depends(get_current_user)
):
    """
    Get strategic plans for a specific pawn structure.
    
    Request body:
        {
            "structure_type": "isolated_queen_pawn",
            "color": "white"
        }
    
    Returns:
        - Structure name and main idea
        - Plans with key moves, maneuvers, breaks
        - Teaching explanations
        - Common mistakes to avoid
        - Famous games for study
    """
    from services.structure_plan_database import get_structure_plans
    
    structure_type = request.get("structure_type", "")
    color = request.get("color", "white")
    
    if not structure_type:
        return {"error": "structure_type is required"}
    
    return get_structure_plans(structure_type, color)


@router.post("/analyze/position")
async def analyze_position_complete(
    request: dict,
    user: User = Depends(get_current_user)
):
    """
    Complete position analysis combining phase, structure, and teaching.
    
    Request body:
        {"fen": "...", "for_color": "white"}
    
    Returns:
        Combined analysis with phase, structure, and coaching
    """
    import chess
    from services.game_phase_service import GamePhaseCalculator, get_phase_coaching
    from services.pawn_structure_service import PawnStructureClassifier, get_structure_teaching
    
    fen = request.get("fen", chess.STARTING_FEN)
    for_color = request.get("for_color", "white")
    
    try:
        board = chess.Board(fen)
    except Exception as e:
        return {"error": f"Invalid FEN: {str(e)}"}
    
    # Phase analysis
    phase_calc = GamePhaseCalculator()
    phase_info = phase_calc.calculate_phase(board)
    phase_coaching = get_phase_coaching(phase_info)
    
    # Structure analysis
    structure_classifier = PawnStructureClassifier()
    structure_analysis = structure_classifier.analyze(board)
    structure_teaching = get_structure_teaching(structure_analysis, for_color)
    
    return {
        "fen": fen,
        "for_color": for_color,
        
        # Phase info
        "phase": {
            "percent": phase_info.phase_percent,
            "label": phase_info.phase_label.value,
            "endgame_type": phase_info.endgame_type.value if phase_info.phase_percent >= 50 else None
        },
        
        # Structure info
        "structure": {
            "type": structure_analysis.structure_type.value,
            "name": structure_analysis.structure_name,
            "confidence": round(structure_analysis.confidence, 2)
        },
        
        # Key features
        "features": {
            "isolated_pawns": structure_analysis.isolated_pawns,
            "passed_pawns": structure_analysis.passed_pawns,
            "outposts": structure_analysis.outposts,
            "weak_squares": structure_analysis.weak_squares
        },
        
        # Teaching content
        "teaching": {
            "phase_priorities": phase_coaching.get("priorities", [])[:3],
            "your_plans": structure_teaching["your_plans"][:3],
            "opponent_plans": structure_teaching["opponent_plans"][:2],
            "key_concepts": structure_teaching["key_concepts"][:2],
            "common_mistakes": structure_teaching["common_mistakes"][:2],
            "endgame_concepts": phase_coaching.get("endgame_concepts", [])[:2]
        }
    }


@router.post("/teaching/identify-opening")
async def identify_opening(
    request: dict,
    user: User = Depends(get_current_user)
):
    """
    Identify the opening from a list of moves.
    
    Request body:
        {"moves": ["e4", "e5", "Nf3", "Nc6", "Bc4"]}
    
    Returns:
        Opening identification with teaching content
    """
    from services.opening_teaching_db import OpeningTeachingDatabase
    
    moves = request.get("moves", [])
    
    if not moves:
        return {"error": "No moves provided"}
    
    db = OpeningTeachingDatabase()
    opening = db.identify_opening(moves)
    
    if not opening:
        return {
            "identified": False,
            "message": "Opening not identified yet - keep playing!"
        }
    
    return {
        "identified": True,
        "opening_id": opening.opening_id,
        "name": opening.name,
        "eco_code": opening.eco_code,
        "overview": opening.overview,
        "main_idea_white": opening.main_idea_white,
        "main_idea_black": opening.main_idea_black,
        "typical_plans_white": opening.typical_plans_white,
        "typical_plans_black": opening.typical_plans_black,
        "difficulty": opening.difficulty,
        "famous_games": opening.famous_games
    }


@router.post("/teaching/opening-move")
async def get_opening_move_teaching(
    request: dict,
    user: User = Depends(get_current_user)
):
    """
    Get teaching explanation for a specific move in an opening.
    
    Request body:
        {
            "moves": ["e4", "e5", "Nf3", "Nc6", "Bc4"],
            "move_number": 3,
            "move": "Bc4",
            "player_color": "white"
        }
    
    Returns:
        Teaching explanation for the move
    """
    from services.opening_teaching_db import OpeningTeachingDatabase
    
    moves = request.get("moves", [])
    move_number = request.get("move_number", 1)
    move = request.get("move", "")
    player_color = request.get("player_color", "white")
    
    if not moves or not move:
        return {"error": "moves and move are required"}
    
    db = OpeningTeachingDatabase()
    opening = db.identify_opening(moves)
    
    if not opening:
        return {"teaching": None, "opening_identified": False}
    
    teaching = db.get_move_teaching(opening.opening_id, move_number, move, player_color)
    
    return {
        "opening_identified": True,
        "opening_name": opening.name,
        "move": move,
        "move_number": move_number,
        "teaching": teaching,
        "overview": db.get_opening_overview(opening.opening_id, player_color)
    }


@router.post("/teaching/game-summary")
async def get_game_teaching_summary(
    request: dict,
    user: User = Depends(get_current_user)
):
    """
    Generate post-game teaching summary.
    
    Request body:
        {
            "session_id": "...",
            "result": "1-0",
            "student_color": "white",
            "moves": ["e4", "e5", ...],
            "concepts_taught": ["development", "tactics"],
            "mistakes": [{"move": "Nf6", "better": "d5"}],
            "good_moves": [{"move": "Bc4"}]
        }
    
    Returns:
        Structured lesson summary from the game
    """
    from services.conversational_coach import ConversationalCoach
    from services.opening_teaching_db import OpeningTeachingDatabase
    
    result = request.get("result", "1/2-1/2")
    student_color = request.get("student_color", "white")
    moves = request.get("moves", [])
    concepts = request.get("concepts_taught", [])
    mistakes = request.get("mistakes", [])
    good_moves = request.get("good_moves", [])
    user_rating = request.get("user_rating", 1200)
    
    # Create coach and populate context
    coach = ConversationalCoach(user.user_id, user_rating)
    coach.context.student_color = student_color
    coach.context.concepts_taught = concepts
    coach.context.mistakes_made = mistakes
    coach.context.good_moves = good_moves
    
    # Identify opening if possible
    db = OpeningTeachingDatabase()
    opening = db.identify_opening(moves)
    if opening:
        coach.context.opening_name = opening.name
    
    # Generate summary
    summary = coach.get_game_end_summary(result)
    
    # Build structured lesson
    lesson = {
        "summary": summary,
        "result_for_student": (
            "win" if (result == "1-0" and student_color == "white") or 
                     (result == "0-1" and student_color == "black") 
            else "loss" if result in ["1-0", "0-1"]
            else "draw"
        ),
        "concepts_covered": concepts,
        "opening_played": opening.name if opening else None,
        "good_moments": len(good_moves),
        "learning_opportunities": len(mistakes),
        "key_takeaways": []
    }
    
    # Generate key takeaways
    if mistakes:
        lesson["key_takeaways"].append("Check for tactics before every move")
    if concepts:
        lesson["key_takeaways"].append(f"Great practice with: {', '.join(concepts[:2])}")
    if opening:
        lesson["key_takeaways"].append(f"The {opening.name} is worth studying more")
    
    return lesson



# ==================== SOCRATIC ENGINE ====================

@router.post("/socratic/start")
async def start_socratic_dialogue(
    request: dict,
    user: User = Depends(get_current_user)
):
    """
    Start a Socratic dialogue about a position/move.
    
    The Socratic approach NEVER gives the answer first.
    Instead, it asks what the student was thinking and guides them to discover.
    
    Request body:
        {
            "fen": "...",           # Position before the move
            "move_played": "Nf3",   # What the student played (SAN)
            "best_move": "Bxh7+",   # What was objectively better (SAN)
            "eval_loss": 150,       # Centipawns lost (optional)
            "position_type": "blunder"  # blunder, mistake, missed_tactic, strategic
        }
    
    Returns:
        - dialogue_id: ID to continue the dialogue
        - opening_question: The first Socratic question (NOT the answer)
        - state: Current dialogue state
        - expects_response: True (waiting for student input)
    """
    from services.socratic_engine import create_socratic_dialogue
    
    fen = request.get("fen", "")
    move_played = request.get("move_played", "")
    best_move = request.get("best_move", "")
    eval_loss = request.get("eval_loss", 0)
    position_type = request.get("position_type", "blunder")
    
    if not fen or not move_played or not best_move:
        return {"error": "fen, move_played, and best_move are required"}
    
    # Get user rating for calibration
    user_doc = await db.users.find_one({"user_id": user.user_id})
    user_rating = user_doc.get("assessed_rating", 1200) if user_doc else 1200
    
    # Create the dialogue
    context, opening_question = create_socratic_dialogue(
        fen=fen,
        move_played=move_played,
        best_move=best_move,
        eval_loss=eval_loss,
        position_type=position_type,
        user_rating=user_rating
    )
    
    return {
        "dialogue_id": context.dialogue_id,
        "opening_question": opening_question.message,
        "state": opening_question.state.value,
        "expects_response": opening_question.expects_response,
        "response_type": opening_question.response_type
    }


@router.post("/socratic/respond")
async def continue_socratic_dialogue(
    request: dict,
    user: User = Depends(get_current_user)
):
    """
    Continue a Socratic dialogue with the student's response.
    
    The engine processes their response and either:
    - Celebrates if they discovered the answer
    - Acknowledges and redirects if they're off track
    - Encourages and hints if they're close
    - Guides to final discovery if they're very close
    
    Request body:
        {
            "dialogue_id": "abc123",    # From start endpoint
            "fen": "...",               # Original position
            "move_played": "Nf3",       # What they played
            "best_move": "Bxh7+",       # Best move
            "response": "I was trying to develop",  # Their text response OR move guess
            "hints_given": 0,           # How many hints so far
            "state": "awaiting_response"  # Current state
        }
    
    Returns:
        - message: Coach's response (question, hint, celebration, or reveal)
        - state: New dialogue state
        - expects_response: Whether waiting for more input
        - celebration: True if they found the answer
        - hint_level: Level of hint given (if any)
    """
    from services.socratic_engine import (
        DialogueContext, DialogueState, continue_dialogue
    )
    
    dialogue_id = request.get("dialogue_id", "")
    fen = request.get("fen", "")
    move_played = request.get("move_played", "")
    best_move = request.get("best_move", "")
    response = request.get("response", "")
    hints_given = request.get("hints_given", 0)
    state_str = request.get("state", "awaiting_response")
    
    if not response:
        return {"error": "response is required"}
    
    # Get user rating for calibration
    user_doc = await db.users.find_one({"user_id": user.user_id})
    user_rating = user_doc.get("assessed_rating", 1200) if user_doc else 1200
    
    # Reconstruct context (since dialogues aren't persisted across requests)
    try:
        state = DialogueState(state_str)
    except ValueError:
        state = DialogueState.AWAITING_RESPONSE
    
    # Create a context object to continue the dialogue
    context = DialogueContext(
        dialogue_id=dialogue_id,
        fen=fen,
        move_played=move_played,
        best_move=best_move,
        eval_loss=0,
        position_type="blunder",
        state=state,
        hints_given=hints_given,
        student_rating=user_rating
    )
    
    # Continue the dialogue
    result = continue_dialogue(context, response, user_rating)
    
    return {
        "message": result.message,
        "state": result.state.value,
        "expects_response": result.expects_response,
        "response_type": result.response_type,
        "celebration": result.celebration,
        "hint_level": result.hint_level.value if result.hint_level else None,
        "hints_given": context.hints_given,
        "choices": result.choices
    }


@router.post("/socratic/hint")
async def get_socratic_hint(
    request: dict,
    user: User = Depends(get_current_user)
):
    """
    Get the next progressive hint in a Socratic dialogue.
    
    Hints progress from subtle to specific:
    1. Subtle: "Think about piece activity..."
    2. Directional: "Look at the kingside"
    3. Specific: "What about the h7 square?"
    4. Almost answer: "What if Bishop went to h7?"
    
    Request body:
        {
            "dialogue_id": "abc123",
            "fen": "...",
            "move_played": "Nf3",
            "best_move": "Bxh7+",
            "hints_given": 1
        }
    
    Returns:
        - hint: The next progressive hint
        - hint_level: Level of hint (subtle, directional, specific, almost_answer)
        - state: New dialogue state (may be REVEAL if max hints reached)
    """
    from services.socratic_engine import SocraticEngine, DialogueContext, DialogueState
    
    fen = request.get("fen", "")
    move_played = request.get("move_played", "")
    best_move = request.get("best_move", "")
    hints_given = request.get("hints_given", 0)
    
    if not fen or not best_move:
        return {"error": "fen and best_move are required"}
    
    # Get user rating
    user_doc = await db.users.find_one({"user_id": user.user_id})
    user_rating = user_doc.get("assessed_rating", 1200) if user_doc else 1200
    
    # Create context
    context = DialogueContext(
        dialogue_id=request.get("dialogue_id", "hint"),
        fen=fen,
        move_played=move_played or "",
        best_move=best_move,
        eval_loss=0,
        position_type="blunder",
        state=DialogueState.HINT_PHASE,
        hints_given=hints_given,
        student_rating=user_rating
    )
    
    engine = SocraticEngine(user_rating)
    result = engine.get_next_hint(context)
    
    return {
        "hint": result.message,
        "hint_level": result.hint_level.value if result.hint_level else "subtle",
        "state": result.state.value,
        "expects_response": result.expects_response,
        "hints_given": context.hints_given
    }


@router.post("/socratic/reveal")
async def get_socratic_reveal(
    request: dict,
    user: User = Depends(get_current_user)
):
    """
    Reveal the answer after Socratic engagement.
    
    This should only be called AFTER the student has tried.
    The reveal is teaching-focused, not just "the answer was X".
    
    Request body:
        {
            "fen": "...",
            "move_played": "Nf3",
            "best_move": "Bxh7+",
            "eval_loss": 150,
            "hints_given": 2,
            "student_guesses": ["Qh5", "Bc4"]  # Optional: their previous guesses
        }
    
    Returns:
        - explanation: Teaching explanation of the best move
        - acknowledgment: Recognition of their effort
    """
    from services.socratic_engine import SocraticEngine, DialogueContext, DialogueState
    
    fen = request.get("fen", "")
    move_played = request.get("move_played", "")
    best_move = request.get("best_move", "")
    eval_loss = request.get("eval_loss", 0)
    hints_given = request.get("hints_given", 0)
    student_guesses = request.get("student_guesses", [])
    
    if not fen or not best_move:
        return {"error": "fen and best_move are required"}
    
    # Get user rating
    user_doc = await db.users.find_one({"user_id": user.user_id})
    user_rating = user_doc.get("assessed_rating", 1200) if user_doc else 1200
    
    # Create context
    context = DialogueContext(
        dialogue_id=request.get("dialogue_id", "reveal"),
        fen=fen,
        move_played=move_played or "",
        best_move=best_move,
        eval_loss=eval_loss,
        position_type="blunder",
        state=DialogueState.REVEAL,
        hints_given=hints_given,
        student_guesses=student_guesses,
        student_rating=user_rating
    )
    
    engine = SocraticEngine(user_rating)
    result = engine.get_reveal(context)
    
    return {
        "explanation": result.message,
        "state": result.state.value,
        "complete": True
    }


# Debug endpoint to test Socratic Engine
@router.post("/debug/test-socratic")
async def test_socratic_engine(
    request: dict,
    user: User = Depends(get_current_user)
):
    """
    Debug endpoint to test the full Socratic dialogue flow.
    
    Request body:
        {
            "fen": "r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 4 4",
            "move_played": "Nf3",
            "best_move": "Qxf7#"
        }
    
    Returns a sample dialogue showing how the Socratic approach works.
    """
    from services.socratic_engine import SocraticEngine, create_socratic_dialogue, continue_dialogue
    
    fen = request.get("fen", "r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 4 4")
    move_played = request.get("move_played", "Nf3")
    best_move = request.get("best_move", "Qxf7#")
    
    # Get user rating
    user_doc = await db.users.find_one({"user_id": user.user_id})
    user_rating = user_doc.get("assessed_rating", 1200) if user_doc else 1200
    
    # Start the dialogue
    context, opening_q = create_socratic_dialogue(
        fen=fen,
        move_played=move_played,
        best_move=best_move,
        eval_loss=0,
        position_type="missed_tactic",
        user_rating=user_rating
    )
    
    # Simulate a student response
    response1 = continue_dialogue(context, "I was just developing my knight", user_rating)
    
    # Get a hint
    engine = SocraticEngine(user_rating)
    engine.dialogues[context.dialogue_id] = context
    hint = engine.get_next_hint(context)
    
    # Get reveal
    reveal = engine.get_reveal(context)
    
    return {
        "demo_dialogue": [
            {
                "step": 1,
                "type": "opening_question",
                "message": opening_q.message,
                "state": opening_q.state.value
            },
            {
                "step": 2,
                "type": "student_response",
                "student_said": "I was just developing my knight",
                "coach_response": response1.message,
                "state": response1.state.value
            },
            {
                "step": 3,
                "type": "hint",
                "message": hint.message,
                "hint_level": hint.hint_level.value if hint.hint_level else None,
                "state": hint.state.value
            },
            {
                "step": 4,
                "type": "reveal",
                "message": reveal.message,
                "state": reveal.state.value
            }
        ],
        "philosophy": "The Socratic method never gives the answer first. It asks, guides, hints, and only reveals after engagement.",
        "position_info": {
            "fen": fen,
            "move_played": move_played,
            "best_move": best_move
        }
    }



# ==================== HUMAN COACH SERVICE ====================

@router.get("/human-coach/welcome")
async def get_human_coach_welcome(user: User = Depends(get_current_user)):
    """
    Get a personalized welcome message with memory.
    
    The coach remembers:
    - Last session and what was practiced
    - Recent results and streaks
    - Current focus area
    
    Returns:
        Personalized welcome message that shows the coach remembers the student.
    """
    from services.human_coach_service import create_human_coach
    
    # Get user rating
    user_doc = await db.users.find_one({"user_id": user.user_id})
    user_rating = user_doc.get("assessed_rating", 1200) if user_doc else 1200
    
    coach = await create_human_coach(db, user.user_id, user_rating)
    welcome = await coach.get_welcome_message()
    
    return {
        "message": welcome,
        "has_memory": coach.memory.total_sessions > 0,
        "total_sessions": coach.memory.total_sessions,
        "current_focus": coach.memory.current_focus,
        "streak": {
            "type": coach.memory.streak_type,
            "count": coach.memory.streak_count
        } if coach.memory.streak_type else None
    }


@router.get("/human-coach/memory")
async def get_coach_memory(user: User = Depends(get_current_user)):
    """
    Get what the coach remembers about the student.
    
    Returns:
        Memory object with session history, weaknesses, concepts, etc.
    """
    from services.human_coach_service import create_human_coach
    
    user_doc = await db.users.find_one({"user_id": user.user_id})
    user_rating = user_doc.get("assessed_rating", 1200) if user_doc else 1200
    
    coach = await create_human_coach(db, user.user_id, user_rating)
    memory = coach.memory
    
    return {
        "total_sessions": memory.total_sessions,
        "last_session_date": memory.last_session_date,
        "recent_results": memory.recent_results,
        "top_weaknesses": memory.top_weaknesses,
        "concepts_practiced": memory.concepts_practiced,
        "current_focus": memory.current_focus,
        "streak": {
            "type": memory.streak_type,
            "count": memory.streak_count
        } if memory.streak_type else None,
        "recurring_mistakes": memory.recurring_mistakes
    }


@router.post("/human-coach/emotional-state")
async def detect_emotional_state(
    request: dict,
    user: User = Depends(get_current_user)
):
    """
    Detect player's emotional state based on game signals.
    
    Request body:
        {
            "recent_results": ["win", "loss", "loss"],  # Recent game results
            "avg_move_time": 15.5,                       # Average seconds per move
            "blunders_this_game": 2,                     # Blunders in current game
            "time_since_last_move": 45                   # Seconds thinking on last move
        }
    
    Returns:
        Detected emotional state with coaching recommendations.
    """
    from services.human_coach_service import create_human_coach
    
    user_doc = await db.users.find_one({"user_id": user.user_id})
    user_rating = user_doc.get("assessed_rating", 1200) if user_doc else 1200
    
    coach = await create_human_coach(db, user.user_id, user_rating)
    
    state = coach.detect_emotional_state(
        recent_results=request.get("recent_results"),
        avg_move_time=request.get("avg_move_time", 0),
        blunders_this_game=request.get("blunders_this_game", 0),
        time_since_last_move=request.get("time_since_last_move", 0)
    )
    
    # Get adapted message
    adapted = coach.adapt_message_for_emotion("Let's continue.")
    
    return {
        "emotional_state": state.value,
        "should_offer_break": adapted.should_offer_break,
        "encouragement_level": adapted.encouragement_level,
        "tone_recommendation": adapted.tone,
        "sample_prefix": adapted.emotional_prefix,
        "sample_suffix": adapted.emotional_suffix
    }


@router.get("/human-coach/curriculum")
async def get_weekly_curriculum(user: User = Depends(get_current_user)):
    """
    Get a progressive weekly training plan based on weaknesses.
    
    Analyzes:
    - Recent game patterns
    - Identified weaknesses
    - What's been practiced already
    
    Returns:
        Focused training plan for the week.
    """
    from services.human_coach_service import create_human_coach
    
    user_doc = await db.users.find_one({"user_id": user.user_id})
    user_rating = user_doc.get("assessed_rating", 1200) if user_doc else 1200
    
    coach = await create_human_coach(db, user.user_id, user_rating)
    curriculum = await coach.generate_weekly_curriculum()
    
    return {
        "focus_area": curriculum.focus_area,
        "reason": curriculum.reason,
        "exercises": curriculum.exercises,
        "targets": {
            "games": curriculum.target_games,
            "puzzles": curriculum.target_puzzles,
            "sessions": curriculum.estimated_sessions
        },
        "concepts_to_practice": curriculum.concepts_to_practice,
        "motivation": curriculum.motivation_message
    }


@router.post("/human-coach/surface-memory")
async def surface_relevant_memory(
    request: dict,
    user: User = Depends(get_current_user)
):
    """
    Surface relevant memory for the current position/theme.
    
    Request body:
        {
            "current_fen": "...",           # Current position (optional)
            "current_theme": "fork",        # Current tactical theme (optional)
            "current_opening": "Italian"    # Current opening (optional)
        }
    
    Returns:
        Relevant memory connection if found.
    """
    from services.human_coach_service import create_human_coach
    
    user_doc = await db.users.find_one({"user_id": user.user_id})
    user_rating = user_doc.get("assessed_rating", 1200) if user_doc else 1200
    
    coach = await create_human_coach(db, user.user_id, user_rating)
    
    memory_msg = await coach.surface_relevant_memory(
        current_fen=request.get("current_fen", ""),
        current_theme=request.get("current_theme", ""),
        current_opening=request.get("current_opening", "")
    )
    
    return {
        "has_memory": memory_msg is not None,
        "message": memory_msg
    }


@router.post("/human-coach/mistake-response")
async def get_socratic_mistake_response(
    request: dict,
    user: User = Depends(get_current_user)
):
    """
    Get a human-like Socratic response to a mistake.
    
    Combines:
    - Socratic questioning (never gives answer first)
    - Emotional intelligence (adapts tone)
    - Memory (connects to past patterns)
    
    Request body:
        {
            "fen": "...",                   # Position before move
            "move_played": "Nf3",           # What they played
            "best_move": "Bxh7+",           # What was better
            "eval_loss": 150,               # Centipawns lost
            "position_type": "blunder",     # blunder, mistake, missed_tactic
            "emotional_context": {          # Optional
                "recent_results": ["loss", "loss"],
                "avg_move_time": 8,
                "blunders_this_game": 2
            }
        }
    
    Returns:
        Socratic dialogue with emotional adaptation.
    """
    from services.human_coach_service import get_socratic_response
    
    user_doc = await db.users.find_one({"user_id": user.user_id})
    user_rating = user_doc.get("assessed_rating", 1200) if user_doc else 1200
    
    response = await get_socratic_response(
        db=db,
        user_id=user.user_id,
        user_rating=user_rating,
        fen=request.get("fen", ""),
        move_played=request.get("move_played", ""),
        best_move=request.get("best_move", ""),
        eval_loss=request.get("eval_loss", 0),
        emotional_context=request.get("emotional_context")
    )
    
    return response


@router.post("/human-coach/session-summary")
async def get_session_summary(
    request: dict,
    user: User = Depends(get_current_user)
):
    """
    Get end-of-session summary with memory connection.
    
    Request body:
        {
            "session_result": "win",
            "concepts_covered": ["tactics", "development"],
            "mistakes_made": 3,
            "good_moves": 5
        }
    
    Returns:
        Summary that connects to long-term progress.
    """
    from services.human_coach_service import create_human_coach
    
    user_doc = await db.users.find_one({"user_id": user.user_id})
    user_rating = user_doc.get("assessed_rating", 1200) if user_doc else 1200
    
    coach = await create_human_coach(db, user.user_id, user_rating)
    
    summary = await coach.get_session_summary_with_memory(
        session_result=request.get("session_result", "draw"),
        concepts_covered=request.get("concepts_covered", []),
        mistakes_made=request.get("mistakes_made", 0),
        good_moves=request.get("good_moves", 0)
    )
    
    return {
        "summary": summary,
        "total_sessions": coach.memory.total_sessions + 1
    }



# ==================== OPENING MASTERY SYSTEM ====================

@router.get("/openings/available")
async def get_available_openings_list(user: User = Depends(get_current_user)):
    """
    Get list of all openings available to learn.
    
    Returns:
        List of openings with name, description, character, traps count.
    """
    from services.opening_mastery import get_available_openings
    
    return {"openings": get_available_openings()}


@router.get("/openings/{opening_key}")
async def get_opening_details_endpoint(
    opening_key: str,
    user: User = Depends(get_current_user)
):
    """
    Get full details of a specific opening.
    
    Returns:
        Opening details with variations, traps, key ideas.
    """
    from services.opening_mastery import get_opening_details
    
    details = get_opening_details(opening_key)
    if not details:
        raise HTTPException(status_code=404, detail="Opening not found")
    
    return details


@router.post("/openings/detect")
async def detect_opening_from_game(
    request: dict,
    user: User = Depends(get_current_user)
):
    """
    Detect which opening is being played from moves.
    
    Request body:
        {"moves": ["e4", "e5", "Nf3", "Nc6", "Bc4"]}
    
    Returns:
        Opening info if detected, with available teaching options.
    """
    from services.opening_mastery import detect_opening_from_moves, OpeningTeacher, get_user_opening_progress
    
    moves = request.get("moves", [])
    if not moves:
        return {"detected": False, "message": "No moves provided"}
    
    opening_info = detect_opening_from_moves(moves)
    if not opening_info:
        return {
            "detected": False,
            "message": "Opening not recognized yet. Keep playing!",
            "moves_played": len(moves)
        }
    
    # Check user's progress with this opening
    progress = await get_user_opening_progress(db, user.user_id, opening_info["opening_name"])
    
    # Get teaching introduction
    teacher = OpeningTeacher(opening_info["opening_key"], progress)
    intro = teacher.get_introduction()
    
    return {
        "detected": True,
        "opening": opening_info,
        "user_knows_opening": progress is not None and progress.mastery_level.value != "unknown",
        "teaching_options": intro.get("options", []),
        "introduction_message": intro.get("message", ""),
        "has_traps": opening_info.get("has_traps", False),
        "trap_names": opening_info.get("trap_names", [])
    }


@router.post("/openings/teach/start")
async def start_opening_teaching(
    request: dict,
    user: User = Depends(get_current_user)
):
    """
    Start teaching an opening (main line or trap).
    
    Request body:
        {
            "opening_key": "italian_game",
            "mode": "main_line" | "trap",
            "trap_index": 0  # Optional, for trap mode
        }
    
    Returns:
        Teaching session info with first instruction.
    """
    from services.opening_mastery import (
        OpeningTeacher, 
        get_user_opening_progress, 
        update_user_opening_progress,
        UserOpeningProgress,
        MasteryLevel
    )
    from datetime import datetime, timezone
    
    opening_key = request.get("opening_key")
    mode = request.get("mode", "main_line")
    trap_index = request.get("trap_index", 0)
    
    if not opening_key:
        raise HTTPException(status_code=400, detail="opening_key is required")
    
    # Get or create user progress
    progress = await get_user_opening_progress(db, user.user_id, opening_key)
    if not progress:
        # First time learning this opening
        from services.opening_feedback_admin_service import get_effective_opening_feedback
        
        # Try to get effective feedback first (static + admin override)
        effective_feedback = await get_effective_opening_feedback(db, opening_key)
        
        if effective_feedback:
            opening_name = effective_feedback.get("opening_name", opening_key)
        else:
            # Fallback to old OPENING_DATABASE
            from services.opening_mastery import OPENING_DATABASE
            opening_data = OPENING_DATABASE.get(opening_key)
            if not opening_data:
                raise HTTPException(status_code=404, detail="Opening not found")
            opening_name = opening_data.name
        
        progress = UserOpeningProgress(
            user_id=user.user_id,
            opening_name=opening_name,
            mastery_level=MasteryLevel.INTRODUCED,
            introduced_at=datetime.now(timezone.utc),
            last_practiced_at=datetime.now(timezone.utc),
            times_practiced=0,
            times_applied_in_games=0,
            correct_applications=0,
            traps_learned=[],
            variations_learned=[],
            quiz_scores=[],
            notes=""
        )
        await update_user_opening_progress(db, progress)
    
    # Create teacher and start teaching
    teacher = OpeningTeacher(opening_key, progress)
    
    if mode == "trap":
        result = teacher.start_trap_teaching(trap_index)
    else:
        result = teacher.start_main_line_teaching()
    
    return result


@router.post("/openings/teach/next-move")
async def get_next_teaching_move(
    request: dict,
    user: User = Depends(get_current_user)
):
    """
    Get the next move in the teaching sequence.
    
    Request body:
        {
            "opening_key": "italian_game",
            "mode": "main_line" | "trap",
            "current_move_index": 3
        }
    
    Returns:
        Next move instruction or completion message.
    """
    from services.opening_mastery import OpeningTeacher, get_user_opening_progress
    
    opening_key = request.get("opening_key")
    mode = request.get("mode", "main_line")
    move_index = request.get("current_move_index", 0)
    
    if not opening_key:
        raise HTTPException(status_code=400, detail="opening_key is required")
    
    progress = await get_user_opening_progress(db, user.user_id, opening_key)
    teacher = OpeningTeacher(opening_key, progress)
    
    # Start from the requested index
    if mode == "trap":
        teacher.start_trap_teaching()
        teacher.teaching_move_index = move_index
        return teacher._get_next_trap_move()
    else:
        teacher.start_main_line_teaching()
        teacher.teaching_move_index = move_index
        return teacher._get_next_teaching_move()


@router.get("/openings/progress")
async def get_user_opening_progress_list(user: User = Depends(get_current_user)):
    """
    Get all openings the user has learned or started learning.
    
    Returns:
        List of openings with mastery levels and stats.
    """
    from services.opening_mastery import get_all_user_openings
    
    openings = await get_all_user_openings(db, user.user_id)
    
    return {
        "openings_learned": openings,
        "total_openings_available": 5,  # Update as we add more
        "suggested_next": _suggest_next_opening(openings)
    }


def _suggest_next_opening(learned_openings: List[Dict]) -> Optional[str]:
    """Suggest the next opening to learn based on what user knows."""
    learned_names = {o["opening_name"].lower() for o in learned_openings}
    
    # Priority order for beginners
    priority = ["italian_game", "london_system", "queens_gambit", "sicilian_defense", "caro_kann"]
    
    for opening_key in priority:
        opening_name = opening_key.replace("_", " ").title()
        if opening_name.lower() not in learned_names:
            return opening_key
    
    return None


@router.post("/openings/quiz")
async def get_opening_quiz(
    request: dict,
    user: User = Depends(get_current_user)
):
    """
    Get a quiz question for an opening.
    
    Request body:
        {"opening_key": "italian_game"}
    
    Returns:
        Quiz question with answer (hidden until answered).
    """
    from services.opening_mastery import OpeningTeacher, get_user_opening_progress
    
    opening_key = request.get("opening_key")
    if not opening_key:
        raise HTTPException(status_code=400, detail="opening_key is required")
    
    progress = await get_user_opening_progress(db, user.user_id, opening_key)
    teacher = OpeningTeacher(opening_key, progress)
    
    quiz = teacher.get_quiz_question()
    
    # Store the answer separately so frontend can check
    return {
        "question": quiz.get("question"),
        "type": quiz.get("type"),
        "hint": quiz.get("hint"),
        "quiz_id": f"{opening_key}_{quiz.get('type')}_{hash(quiz.get('question', ''))}"
    }


@router.post("/openings/quiz/answer")
async def check_quiz_answer(
    request: dict,
    user: User = Depends(get_current_user)
):
    """
    Check a quiz answer.
    
    Request body:
        {
            "opening_key": "italian_game",
            "quiz_id": "...",
            "answer": "Nf3"
        }
    
    Returns:
        Whether answer was correct with explanation.
    """
    from services.opening_mastery import (
        OpeningTeacher, 
        get_user_opening_progress,
        update_user_opening_progress
    )
    from datetime import datetime, timezone
    
    opening_key = request.get("opening_key")
    user_answer = request.get("answer", "").strip()
    
    if not opening_key or not user_answer:
        raise HTTPException(status_code=400, detail="opening_key and answer are required")
    
    progress = await get_user_opening_progress(db, user.user_id, opening_key)
    teacher = OpeningTeacher(opening_key, progress)
    
    # Generate a new quiz to get the answer (simplified - in production store quiz state)
    quiz = teacher.get_quiz_question()
    correct_answer = quiz.get("answer", "")
    correct_answers = quiz.get("answers", [correct_answer])
    
    is_correct = user_answer.lower() in [a.lower() for a in correct_answers] if correct_answers else user_answer.lower() == correct_answer.lower()
    
    # Update progress with quiz result
    if progress:
        progress.quiz_scores.append({
            "question_type": quiz.get("type"),
            "correct": is_correct,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        progress.last_practiced_at = datetime.now(timezone.utc)
        await update_user_opening_progress(db, progress)
    
    return {
        "correct": is_correct,
        "correct_answer": correct_answer if not is_correct else None,
        "all_correct_answers": correct_answers if not is_correct else None,
        "message": "Correct! Well done!" if is_correct else f"Not quite. The answer is: {correct_answer}"
    }


@router.post("/openings/mark-practiced")
async def mark_opening_practiced(
    request: dict,
    user: User = Depends(get_current_user)
):
    """
    Mark an opening as practiced (after completing a teaching session).
    
    Request body:
        {
            "opening_key": "italian_game",
            "trap_learned": "Fried Liver Attack"  # Optional
        }
    
    Returns:
        Updated progress.
    """
    from services.opening_mastery import (
        get_user_opening_progress,
        update_user_opening_progress,
        MasteryLevel
    )
    from datetime import datetime, timezone
    
    opening_key = request.get("opening_key")
    trap_learned = request.get("trap_learned")
    
    if not opening_key:
        raise HTTPException(status_code=400, detail="opening_key is required")
    
    progress = await get_user_opening_progress(db, user.user_id, opening_key)
    if not progress:
        raise HTTPException(status_code=404, detail="Start learning this opening first")
    
    # Update progress
    progress.times_practiced += 1
    progress.last_practiced_at = datetime.now(timezone.utc)
    
    if progress.mastery_level == MasteryLevel.INTRODUCED:
        progress.mastery_level = MasteryLevel.LEARNING
    elif progress.times_practiced >= 3 and progress.mastery_level == MasteryLevel.LEARNING:
        progress.mastery_level = MasteryLevel.PRACTICED
    
    if trap_learned and trap_learned not in progress.traps_learned:
        progress.traps_learned.append(trap_learned)
    
    await update_user_opening_progress(db, progress)
    
    return {
        "success": True,
        "mastery_level": progress.mastery_level.value,
        "times_practiced": progress.times_practiced,
        "traps_learned": progress.traps_learned,
        "message": f"Great practice! You've practiced {progress.opening_name} {progress.times_practiced} times."
    }



# ==================== PERSONALIZED LEARNING PATH ====================

@router.get("/learning-path")
async def get_personalized_learning_path(user: User = Depends(get_current_user)):
    """
    Get a personalized learning path based on user's weaknesses, habits, and progress.
    
    This is the "smart coach" recommendation - what to work on today.
    """
    global db
    
    if db is None:
        raise HTTPException(status_code=500, detail="Database not initialized")
    
    user_id = user.user_id
    
    # Get user's memory (habits, weaknesses, progress)
    memory = await db.coach_memory.find_one({"user_id": user_id}, {"_id": 0})
    
    # Get recent games for pattern analysis
    recent_games = await db.games.find(
        {"user_id": user_id}
    ).sort("created_at", -1).limit(10).to_list(10)
    
    # Get understanding profile
    understanding = await db.chess_understanding.find_one(
        {"user_id": user_id}, {"_id": 0}
    )
    
    # Build learning path
    recommendations = []
    focus_areas = []
    
    # 1. Analyze weaknesses from memory
    if memory and memory.get("weaknesses"):
        for weakness in memory["weaknesses"][:3]:  # Top 3 weaknesses
            if weakness.get("detection_count", 0) >= 2:
                focus_areas.append({
                    "area": weakness.get("name", "Unknown"),
                    "priority": "high" if weakness.get("detection_count", 0) >= 5 else "medium",
                    "count": weakness.get("detection_count", 0),
                    "improving": weakness.get("improving", False)
                })
                
                # Generate recommendation
                recommendations.append({
                    "type": "weakness",
                    "title": f"Work on {weakness.get('name', 'this area')}",
                    "description": f"You've struggled with this {weakness.get('detection_count', 0)} times recently. Let's fix it!",
                    "action": "practice",
                    "priority": 1 if weakness.get("detection_count", 0) >= 5 else 2
                })
    
    # 2. Check for opening recommendations
    if understanding and understanding.get("opening_knowledge"):
        opening_data = understanding["opening_knowledge"]
        if opening_data.get("weak_openings"):
            for opening in opening_data["weak_openings"][:2]:
                recommendations.append({
                    "type": "opening",
                    "title": f"Practice the {opening}",
                    "description": "Your results in this opening need improvement. Visit the Opening Lab!",
                    "action": "opening_lab",
                    "priority": 2
                })
    
    # 3. Analyze recent game patterns
    if recent_games:
        blunder_count = 0
        missed_tactics = 0
        
        for game in recent_games:
            analysis = game.get("analysis", {})
            if analysis.get("blunders", 0) > 0:
                blunder_count += analysis["blunders"]
            if analysis.get("missed_tactics"):
                missed_tactics += len(analysis["missed_tactics"])
        
        if blunder_count >= 5:
            recommendations.append({
                "type": "tactics",
                "title": "Focus on calculation",
                "description": f"You've had {blunder_count} blunders in recent games. Slow down and check all captures!",
                "action": "play_with_coach",
                "priority": 1
            })
        
        if missed_tactics >= 3:
            recommendations.append({
                "type": "tactics",
                "title": "Tactics training needed",
                "description": f"You've missed {missed_tactics} tactical opportunities. Look for checks, captures, and attacks!",
                "action": "tactics",
                "priority": 2
            })
    
    # 4. Add positive reinforcement if improving
    improving_areas = []
    if memory and memory.get("weaknesses"):
        for weakness in memory["weaknesses"]:
            if weakness.get("improving"):
                improving_areas.append(weakness.get("name", "Unknown"))
    
    # 5. Generate today's focus
    todays_focus = None
    if recommendations:
        # Sort by priority
        recommendations.sort(key=lambda x: x.get("priority", 99))
        top_rec = recommendations[0]
        todays_focus = {
            "title": top_rec["title"],
            "description": top_rec["description"],
            "type": top_rec["type"]
        }
    else:
        todays_focus = {
            "title": "Keep practicing!",
            "description": "Play a game with the coach to identify areas to improve.",
            "type": "general"
        }
    
    return {
        "todays_focus": todays_focus,
        "focus_areas": focus_areas,
        "recommendations": recommendations[:5],  # Top 5 recommendations
        "improving_areas": improving_areas,
        "message": _generate_coach_message(focus_areas, improving_areas)
    }


def _generate_coach_message(focus_areas, improving_areas):
    """Generate a human-like coach message for the learning path."""
    import random
    
    if improving_areas:
        return random.choice([
            f"Great progress on {improving_areas[0]}! Keep it up, you're getting better.",
            f"I've noticed improvement in {improving_areas[0]}. Well done!",
            f"You're working hard and it shows! {improving_areas[0]} is getting better."
        ])
    elif focus_areas:
        top_focus = focus_areas[0]["area"]
        return random.choice([
            f"Dekho, let's focus on {top_focus} today. Small improvements add up!",
            f"Today's goal: work on {top_focus}. You've got this!",
            f"I noticed {top_focus} needs attention. Let's tackle it together!"
        ])
    else:
        return random.choice([
            "Looking good! Play a game with me to find what to work on.",
            "Ready to improve? Let's play and I'll find your weak spots!",
            "Come, let's play a game and see what we can improve."
        ])



@router.get("/memory-lane")
async def get_memory_lane(user: User = Depends(get_current_user)):
    """
    Get "Memory Lane" - specific game memories for the coach to reference.
    
    Returns memorable moments from past games that the coach can reference,
    making it feel like a human coach who remembers your games.
    """
    global db
    import random
    
    if db is None:
        raise HTTPException(status_code=500, detail="Database not initialized")
    
    user_id = user.user_id
    first_name = user.name.split()[0] if user.name else "friend"
    
    # Get recent analyzed games with mistakes
    recent_games = await db.game_analyses.find(
        {"user_id": user_id}
    ).sort("created_at", -1).limit(20).to_list(20)
    
    memories = []
    
    # 1. Find games with memorable mistakes
    for game in recent_games:
        game_date = game.get("created_at") or game.get("analyzed_at")
        if isinstance(game_date, str):
            try:
                from datetime import datetime
                game_date = datetime.fromisoformat(game_date.replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                continue
        
        # Calculate how long ago
        if game_date:
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc)
            if game_date.tzinfo is None:
                game_date = game_date.replace(tzinfo=timezone.utc)
            days_ago = (now - game_date).days
            
            if days_ago == 0:
                time_ref = "earlier today"
            elif days_ago == 1:
                time_ref = "yesterday"
            elif days_ago < 7:
                weekday = game_date.strftime("%A")
                time_ref = f"last {weekday}"
            elif days_ago < 14:
                time_ref = "last week"
            else:
                time_ref = f"{days_ago} days ago"
        else:
            time_ref = "recently"
        
        # Get blunders and mistakes - blunders can be an int or a list
        blunders = game.get("blunders", [])
        if isinstance(blunders, int):
            blunders = []  # Skip if it's just a count
        stockfish = game.get("stockfish_analysis", {})
        move_evals = stockfish.get("move_evaluations", [])
        
        # Find specific memorable mistakes from blunders list
        for mistake in (blunders[:2] if isinstance(blunders, list) else []):
            pattern = mistake.get("mistake_category", "")
            move = mistake.get("move_played", "")
            
            if pattern and move:
                # Generate Indian-English memory reference
                memory_templates = [
                    f"Arre {first_name}, remember {time_ref} when you played {move}? Same {pattern.replace('_', ' ')} pattern!",
                    f"Dekho, {time_ref} you had this same issue with {pattern.replace('_', ' ')}. You played {move} then too.",
                    f"I remember {time_ref} - you missed a similar tactic after {move}. Let's not repeat that!",
                    f"{first_name}, we've seen this before! {time_ref}, same {pattern.replace('_', ' ')} happened.",
                ]
                
                memories.append({
                    "type": "mistake_pattern",
                    "message": random.choice(memory_templates),
                    "game_id": game.get("game_id"),
                    "pattern": pattern,
                    "time_ref": time_ref,
                    "move": move
                })
        
        # Fallback: get memorable mistakes from move evaluations if no blunders list
        if not memories and move_evals:
            for eval in move_evals[:5]:
                if eval.get("evaluation") in ["blunder", "mistake"]:
                    move = eval.get("move", "")
                    cp_loss = eval.get("cp_loss", 0)
                    if move and cp_loss >= 100:
                        memory_templates = [
                            f"Remember {time_ref}? That {move} move cost you {cp_loss} centipawns. Let's be more careful!",
                            f"{first_name}, {time_ref} you played {move} and it was costly. Watch out for similar positions!",
                            f"Dekho {first_name}, {time_ref} you had a tough moment with {move}. Let's learn from it.",
                        ]
                        memories.append({
                            "type": "mistake_pattern",
                            "message": random.choice(memory_templates),
                            "game_id": game.get("game_id"),
                            "pattern": eval.get("evaluation"),
                            "time_ref": time_ref,
                            "move": move
                        })
                        break  # Only add one per game
    
    # 2. Find improvement moments
    if recent_games:
        # Look for games with good accuracy
        for game in recent_games[:5]:
            stockfish = game.get("stockfish_analysis", {})
            user_stats = stockfish.get("user_stats", {})
            accuracy = user_stats.get("accuracy", 0)
            
            if accuracy >= 85:
                game_date = game.get("created_at")
                if isinstance(game_date, str):
                    try:
                        game_date = datetime.fromisoformat(game_date.replace('Z', '+00:00'))
                        days_ago = (datetime.now(timezone.utc) - game_date.replace(tzinfo=timezone.utc)).days
                        if days_ago < 7:
                            time_ref = "this week" if days_ago > 1 else "recently"
                            memories.append({
                                "type": "good_game",
                                "message": f"Shabash {first_name}! Remember that {accuracy}% accuracy game {time_ref}? That's the level we're aiming for!",
                                "game_id": game.get("game_id"),
                                "accuracy": accuracy
                            })
                            break
                    except (ValueError, AttributeError):
                        pass
    
    # 3. Get recurring patterns from coach memory
    coach_memory = await db.coach_memory.find_one({"user_id": user_id}, {"_id": 0})
    if coach_memory:
        recurring = coach_memory.get("recurring_patterns", [])
        if recurring:
            pattern = recurring[0] if isinstance(recurring[0], str) else recurring[0].get("name", "")
            if pattern:
                memories.append({
                    "type": "recurring_pattern",
                    "message": f"Dekho {first_name}, you've had this {pattern.replace('_', ' ')} pattern multiple times. Today, let's break the habit!",
                    "pattern": pattern
                })
    
    # Limit to 3 most relevant memories
    return {
        "memories": memories[:3],
        "has_memories": len(memories) > 0,
        "coach_knows_you": len(recent_games) >= 3
    }



@router.get("/habit-challenge")
async def get_habit_challenge(user: User = Depends(get_current_user)):
    """
    Get "Breaking the Habit" challenge positions.
    
    Returns positions from user's past mistakes where they can practice
    finding the correct move. This is the ultimate personalized training.
    """
    global db
    import random
    import chess
    
    if db is None:
        raise HTTPException(status_code=500, detail="Database not initialized")
    
    user_id = user.user_id
    first_name = user.name.split()[0] if user.name else "friend"
    
    # Get analyzed games with stockfish data
    recent_games = await db.game_analyses.find(
        {"user_id": user_id, "stockfish_analysis": {"$exists": True}}
    ).sort("created_at", -1).limit(30).to_list(30)
    
    challenges = []
    patterns_seen = set()
    
    for game in recent_games:
        stockfish = game.get("stockfish_analysis", {})
        move_evals = stockfish.get("move_evaluations", [])
        user_color = game.get("user_color", "white")
        
        for eval_data in move_evals:
            # Find blunders and mistakes
            if eval_data.get("evaluation") not in ["blunder", "mistake"]:
                continue
            
            fen_before = eval_data.get("fen_before")
            best_move = eval_data.get("best_move")
            played_move = eval_data.get("move")
            cp_loss = eval_data.get("cp_loss", 0)
            
            if not fen_before or not best_move or cp_loss < 100:
                continue
            
            # Validate the position and move
            try:
                board = chess.Board(fen_before)
                # Verify best_move is legal
                try:
                    board.parse_san(best_move)
                except:
                    try:
                        board.parse_uci(best_move)
                    except:
                        continue
            except:
                continue
            
            # Create a unique pattern key to avoid duplicates
            pattern_key = f"{eval_data.get('evaluation')}_{played_move}"
            if pattern_key in patterns_seen:
                continue
            patterns_seen.add(pattern_key)
            
            # Generate challenge message in Indian-English
            challenge_messages = [
                f"Dekho {first_name}, this is where you played {played_move}. Can you find the better move?",
                f"Remember this position? You played {played_move} here. What should you have done?",
                f"Arre {first_name}! This position cost you {cp_loss} centipawns. Find the right move!",
                f"Let's fix this habit. You played {played_move} - what's stronger?",
            ]
            
            challenges.append({
                "challenge_id": f"habit_{game.get('game_id', 'unknown')}_{eval_data.get('move_number', 0)}",
                "fen": fen_before,
                "correct_move": best_move,
                "your_move": played_move,
                "cp_loss": cp_loss,
                "mistake_type": eval_data.get("evaluation"),
                "game_id": game.get("game_id"),
                "move_number": eval_data.get("move_number"),
                "user_color": user_color,
                "message": random.choice(challenge_messages),
                "hint": f"Think about what {played_move} allows your opponent to do...",
            })
            
            # Limit to 5 challenges per request
            if len(challenges) >= 5:
                break
        
        if len(challenges) >= 5:
            break
    
    # Shuffle to keep it fresh
    random.shuffle(challenges)
    
    return {
        "challenges": challenges[:5],
        "has_challenges": len(challenges) > 0,
        "total_mistakes_found": len(patterns_seen),
        "coach_message": f"Chalo {first_name}, let's break some bad habits! I found {len(challenges)} positions from your games where you can practice."
        if challenges else f"Great job {first_name}! Not many mistakes to practice. Keep playing and I'll find areas to improve."
    }


@router.post("/habit-challenge/check")
async def check_habit_challenge(
    request: Dict = Body(...),
    user: User = Depends(get_current_user)
):
    """
    Check if user's answer to a habit challenge is correct.
    
    Body:
    - challenge_id: The challenge ID
    - user_move: The move user played (SAN or UCI)
    - fen: The position FEN
    - correct_move: The correct move
    """
    global db
    import chess
    
    if db is None:
        raise HTTPException(status_code=500, detail="Database not initialized")
    
    request.get("challenge_id")
    user_move = request.get("user_move", "")
    fen = request.get("fen", "")
    correct_move = request.get("correct_move", "")
    
    if not user_move or not fen or not correct_move:
        raise HTTPException(status_code=400, detail="Missing required fields")
    
    first_name = user.name.split()[0] if user.name else "friend"
    
    try:
        board = chess.Board(fen)
        
        # Parse user move (try SAN first, then UCI)
        try:
            user_chess_move = board.parse_san(user_move)
            user_uci = user_chess_move.uci()
        except:
            try:
                user_chess_move = board.parse_uci(user_move)
                user_uci = user_move
            except:
                return {
                    "correct": False,
                    "message": f"Hmm, that move doesn't look valid. Try again, {first_name}!",
                    "correct_move": correct_move
                }
        
        # Parse correct move
        try:
            correct_chess_move = board.parse_san(correct_move)
            correct_uci = correct_chess_move.uci()
        except:
            try:
                correct_chess_move = board.parse_uci(correct_move)
                correct_uci = correct_move
            except:
                return {
                    "correct": False,
                    "message": "Something went wrong. Let's try another position.",
                    "correct_move": correct_move
                }
        
        # Check if moves match
        is_correct = user_uci == correct_uci
        
        if is_correct:
            success_messages = [
                f"Shabash {first_name}! That's exactly right! You're breaking the habit!",
                f"Perfect! You found {correct_move}. Keep this up!",
                f"Excellent {first_name}! This is how you improve - one position at a time.",
                f"Bahut accha! {correct_move} is the move. You're learning!",
            ]
            import random
            return {
                "correct": True,
                "message": random.choice(success_messages),
                "correct_move": correct_move
            }
        else:
            # Not correct - give encouragement
            wrong_messages = [
                f"Not quite, {first_name}. The best move was {correct_move}. Can you see why?",
                f"Close! But {correct_move} was stronger. Think about what it threatens.",
                f"Koi baat nahi! The answer was {correct_move}. Let's try the next one.",
                f"Good try! {correct_move} was the key move here. Onwards!",
            ]
            import random
            return {
                "correct": False,
                "message": random.choice(wrong_messages),
                "correct_move": correct_move,
                "your_move": user_move
            }
            
    except Exception as e:
        logger.error(f"Error checking habit challenge: {e}")
        return {
            "correct": False,
            "message": "Something went wrong. Let's try another position.",
            "correct_move": correct_move
        }
