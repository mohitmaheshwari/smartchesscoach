"""
Cognitive Routes
================

Handles cognitive gap analysis, thinking patterns, and training recommendations.

Endpoints:
- GET /cognitive-gaps/summary - Get cognitive gap summary
- GET /cognitive-gaps/progress - Get cognitive gap progress over time
- GET /cognitive-gaps/recurring - Get recurring patterns
- GET /cognitive-gaps/plan-quality - Analyze plan quality
- POST /cognitive-gaps/sync-training - Sync training from gaps
- GET /cognitive/journey - Journey page cognitive tracker
- GET /cognitive/patterns - Get aggregated cognitive patterns
- GET /cognitive/weaknesses - Get prioritized weaknesses
- GET /cognitive/training-priority - Get training prioritization
- POST /cognitive/focus/activate - Activate focus module
- GET /cognitive/focus/status - Get focus module status
- GET /cognitive/focus/progress - Get focus progress
- GET /cognitive/tsi - Get thinking stability index
- GET /cognitive/trend - Get TSI trend data
- GET /cognitive/phase-insight - Get phase stability insight
- GET /cognitive/blunder-context - Get blunder context distribution
"""

from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

# Create router for cognitive endpoints
router = APIRouter(tags=["Cognitive"])

# Database reference - will be set by server.py
db = None

def set_db(database):
    """Set the database reference for cognitive routes"""
    global db
    db = database


# Import User model and get_current_user from auth routes
from routes.auth import User, get_current_user

# Import cognitive services
from cognitive_gap_intelligence_service import (
    get_gap_summary,
    get_gap_progress,
    get_all_recurring_patterns,
    analyze_plan_quality,
    get_recommended_drills,
    get_drills_for_gap,
    update_training_from_gaps,
    COGNITIVE_GAP_CONFIG
)


# ==================== COGNITIVE GAP INTELLIGENCE API ====================

@router.get("/cognitive-gaps/summary")
async def get_cognitive_gap_summary(user: User = Depends(get_current_user)):
    """
    Get a quick summary of user's cognitive gap status.
    Used for dashboard display.
    """
    global db
    return await get_gap_summary(db, user.user_id)


@router.get("/cognitive-gaps/progress")
async def get_cognitive_gap_progress(weeks: int = 8, user: User = Depends(get_current_user)):
    """
    Get cognitive gap progress over time.
    Shows trends: improving, worsening, or stable.
    """
    global db
    return await get_gap_progress(db, user.user_id, weeks)


@router.get("/cognitive-gaps/recurring")
async def get_recurring_patterns(min_occurrences: int = 3, user: User = Depends(get_current_user)):
    """
    Get all recurring cognitive gap patterns.
    Returns patterns that occurred 3+ times in the last 7 days.
    """
    global db
    return {
        "patterns": await get_all_recurring_patterns(db, user.user_id, min_occurrences),
    }


@router.get("/cognitive-gaps/plan-quality")
async def get_plan_quality_analysis(user: User = Depends(get_current_user)):
    """
    Analyze the quality of user's plans over time.
    Tracks plan specificity, accuracy, and improvement.
    """
    global db
    return await analyze_plan_quality(db, user.user_id)


@router.get("/drills/recommended")
async def get_recommended_drills_endpoint(user: User = Depends(get_current_user)):
    """
    Get personalized drill recommendations based on cognitive gap history.
    Prioritizes high severity gaps and recurring patterns.
    """
    global db
    return await get_recommended_drills(db, user.user_id)


@router.get("/drills/from-gap/{gap_type}")
async def get_drills_from_gap(gap_type: str, count: int = 5, user: User = Depends(get_current_user)):
    """
    Get drill positions targeting a specific cognitive gap type.
    Uses user's own mistakes when available.
    """
    global db
    if gap_type not in COGNITIVE_GAP_CONFIG:
        raise HTTPException(status_code=400, detail=f"Unknown gap type: {gap_type}")
    
    return await get_drills_for_gap(db, user.user_id, gap_type, count)


@router.post("/cognitive-gaps/sync-training")
async def sync_gap_training(user: User = Depends(get_current_user)):
    """
    Update training focus based on accumulated cognitive gaps.
    Call this to ensure training reflects your actual weaknesses.
    """
    global db
    return await update_training_from_gaps(db, user.user_id)


# ==================== COGNITIVE PATTERNS API ====================

@router.get("/cognitive/journey")
async def get_cognitive_journey(user: User = Depends(get_current_user)):
    """
    Journey Page - 3-Tab Cognitive Progress Tracker (Master Spec v4)
    
    Tab A (Now): Snapshot - 5 items + directive
    Tab B (Journey): 4 stat rows + 4 cognitive rows + directive
    Tab C (Trend): Headline + shifts + evidence + directive
    
    INTEGRATES: Stat Interpretation Engine + Coach Voice Generator
    """
    global db
    from journey_engine import compute_journey
    
    # Get analyzed games - include ALL games for the user
    all_analyses = await db.game_analyses.find(
        {"user_id": user.user_id},
        {"_id": 0, "stockfish_analysis": 1, "created_at": 1, "user_color": 1, "game_id": 1, "user_result": 1}
    ).sort("created_at", -1).to_list(100)
    
    # Compute journey with integrated engines
    result = compute_journey(all_games=all_analyses)
    
    return result


@router.get("/cognitive/patterns")
async def get_cognitive_patterns(user: User = Depends(get_current_user)):
    """
    Get aggregated cognitive patterns from user's games.
    
    Returns:
    - patterns: Dict of cognitive categories with frequency, severity, trend
    - thinking_stability_index: 0-100 score
    - tsi_trend: improving/worsening/stable
    """
    global db
    from cognitive_patterns_service import aggregate_cognitive_patterns
    
    result = await aggregate_cognitive_patterns(db, user.user_id)
    return result


@router.get("/cognitive/weaknesses")
async def get_prioritized_weaknesses_api(user: User = Depends(get_current_user)):
    """
    Get prioritized list of cognitive weaknesses.
    
    Only includes patterns that cross the threshold.
    Used by Training page for prescription.
    """
    global db
    from cognitive_patterns_service import get_prioritized_weaknesses
    
    weaknesses = await get_prioritized_weaknesses(db, user.user_id)
    return {"weaknesses": weaknesses}


@router.get("/cognitive/training-priority")
async def get_training_priority(user: User = Depends(get_current_user)):
    """
    Get training content prioritization based on user's weaknesses.
    
    Returns:
    - primary_focus: Main weakness to address
    - secondary_focus: Additional weaknesses
    - puzzle_priority_order: Types of puzzles to prioritize
    - trap_priority_order: Types of traps to prioritize
    - general_drills: If no specific weakness, show general drills
    """
    global db
    from cognitive_patterns_service import (
        get_prioritized_weaknesses,
        get_training_prioritization
    )
    
    weaknesses = await get_prioritized_weaknesses(db, user.user_id)
    prioritization = get_training_prioritization(weaknesses)
    
    return prioritization


@router.post("/cognitive/focus/activate")
async def activate_focus(
    data: dict,
    user: User = Depends(get_current_user)
):
    """
    Activate a focus module for the user.
    
    Body: { "category": "missed_forcing_move" }
    
    Starts audit tracking for next 5 games.
    """
    global db
    from cognitive_patterns_service import activate_focus_module
    
    category = data.get("category")
    if not category:
        raise HTTPException(400, "category is required")
    
    result = await activate_focus_module(db, user.user_id, category)
    return result


@router.get("/cognitive/focus/status")
async def get_focus_status(user: User = Depends(get_current_user)):
    """
    Get current focus module status.
    """
    global db
    from cognitive_patterns_service import get_focus_module_status
    
    status = await get_focus_module_status(db, user.user_id)
    if not status:
        return {"active": False}
    
    return {
        "active": True,
        "category": status.get("active_category"),
        "activated_at": status.get("activated_at")
    }


@router.get("/cognitive/focus/progress")
async def get_focus_progress(user: User = Depends(get_current_user)):
    """
    Evaluate progress on active focus module.
    
    Compares baseline (10 games before) vs audit window (5 games after).
    """
    global db
    from cognitive_patterns_service import evaluate_focus_progress
    
    progress = await evaluate_focus_progress(db, user.user_id)
    if not progress:
        return {"active": False, "message": "No focus module active"}
    
    return progress


@router.get("/cognitive/tsi")
async def get_thinking_stability_index(user: User = Depends(get_current_user)):
    """
    Get Thinking Stability Index.
    
    Simple derived metric showing overall thinking stability.
    """
    global db
    from cognitive_patterns_service import aggregate_cognitive_patterns
    
    result = await aggregate_cognitive_patterns(db, user.user_id, num_games=20)
    
    return {
        "thinking_stability_index": result.get("thinking_stability_index", 100),
        "trend": result.get("tsi_trend", "stable"),
        "games_analyzed": result.get("games_analyzed", 0)
    }


@router.get("/cognitive/trend")
async def get_cognitive_trend(user: User = Depends(get_current_user)):
    """
    Get TSI trend data for last 30 games.
    
    Returns array of {game_num, value} for charting.
    """
    global db
    
    # Get analyses for last 30 games
    analyses = await db.game_analyses.find(
        {"user_id": user.user_id},
        {"_id": 0, "stockfish_analysis": 1, "created_at": 1}
    ).sort("created_at", -1).limit(30).to_list(30)
    
    if not analyses:
        return {"data": []}
    
    # Calculate rolling TSI for each game window
    trend_data = []
    analyses.reverse()  # Oldest first
    
    for i in range(len(analyses)):
        # Use a sliding window of up to 5 games
        window_start = max(0, i - 4)
        window = analyses[window_start:i + 1]
        
        # Simple TSI approximation based on mistake severity in window
        total_mistakes = 0
        total_severity = 0
        
        for analysis in window:
            sf = analysis.get("stockfish_analysis", {})
            for move in sf.get("move_evaluations", []):
                cp_loss = abs(move.get("cp_loss", 0))
                if cp_loss >= 50:  # Significant mistake
                    total_mistakes += 1
                    total_severity += min(1.0, cp_loss / 300)
        
        # Calculate TSI for this window (100 = perfect, 0 = very bad)
        if total_mistakes > 0:
            avg_severity = total_severity / total_mistakes
            # Normalize: assume max 5 mistakes per game at 0.5 severity
            normalized = min(1.0, (total_mistakes * avg_severity) / (len(window) * 2.5))
            tsi = max(0, min(100, int(100 - normalized * 100)))
        else:
            tsi = 100
        
        trend_data.append({
            "game_num": i + 1,
            "value": tsi
        })
    
    return {"data": trend_data}


@router.get("/cognitive/phase-insight")
async def get_phase_insight(user: User = Depends(get_current_user)):
    """
    Get phase stability insight.
    
    Returns most stable and most unstable phases.
    """
    global db
    
    # Get recent analyses
    analyses = await db.game_analyses.find(
        {"user_id": user.user_id},
        {"_id": 0, "stockfish_analysis": 1}
    ).sort("created_at", -1).limit(20).to_list(20)
    
    phase_mistakes = {
        "opening": {"count": 0, "severity": 0},
        "middlegame": {"count": 0, "severity": 0},
        "endgame": {"count": 0, "severity": 0}
    }
    
    for analysis in analyses:
        sf = analysis.get("stockfish_analysis", {})
        for move in sf.get("move_evaluations", []):
            cp_loss = abs(move.get("cp_loss", 0))
            if cp_loss >= 50:
                phase = move.get("phase", "middlegame")
                if phase in phase_mistakes:
                    phase_mistakes[phase]["count"] += 1
                    phase_mistakes[phase]["severity"] += min(1.0, cp_loss / 300)
    
    # Calculate weighted score per phase
    phase_scores = {}
    for phase, data in phase_mistakes.items():
        if data["count"] > 0:
            phase_scores[phase] = data["count"] * (data["severity"] / data["count"])
        else:
            phase_scores[phase] = 0
    
    # Find most unstable and most stable
    sorted_phases = sorted(phase_scores.items(), key=lambda x: x[1], reverse=True)
    
    most_unstable = sorted_phases[0][0].capitalize() if sorted_phases else "Middlegame"
    most_stable = sorted_phases[-1][0].capitalize() if sorted_phases else "Endgame"
    
    return {
        "most_unstable": most_unstable,
        "most_stable": most_stable,
        "phase_scores": phase_scores
    }


@router.get("/cognitive/blunder-context")
async def get_blunder_context(user: User = Depends(get_current_user)):
    """
    Get blunder context distribution - where do mistakes happen?
    
    Analyzes the position evaluation BEFORE each blunder to determine
    if user blunders more when winning, equal, or losing.
    
    Returns:
        winning: % of blunders that occurred in winning positions
        equal: % of blunders that occurred in equal positions  
        losing: % of blunders that occurred in losing positions
    """
    global db
    
    # Get recent analyses
    analyses = await db.game_analyses.find(
        {"user_id": user.user_id},
        {"_id": 0, "stockfish_analysis": 1, "user_color": 1}
    ).sort("created_at", -1).limit(20).to_list(20)
    
    context_counts = {
        "winning": 0,
        "equal": 0,
        "losing": 0
    }
    total_blunders = 0
    
    for analysis in analyses:
        sf = analysis.get("stockfish_analysis", {})
        user_color = analysis.get("user_color", "white")
        
        for move in sf.get("move_evaluations", []):
            cp_loss = abs(move.get("cp_loss", 0))
            if cp_loss < 100:  # Only count significant mistakes/blunders
                continue
            
            total_blunders += 1
            
            # Get evaluation BEFORE the blunder
            eval_before = move.get("eval_before", 0)
            
            # Adjust for user's perspective
            if user_color == "black":
                eval_before = -eval_before
            
            # Classify position context
            if eval_before >= 150:  # +1.5 or better = winning
                context_counts["winning"] += 1
            elif eval_before <= -150:  # -1.5 or worse = losing
                context_counts["losing"] += 1
            else:  # Between -1.5 and +1.5 = equal
                context_counts["equal"] += 1
    
    # Calculate percentages
    if total_blunders > 0:
        distribution = {
            "winning": round((context_counts["winning"] / total_blunders) * 100),
            "equal": round((context_counts["equal"] / total_blunders) * 100),
            "losing": round((context_counts["losing"] / total_blunders) * 100)
        }
        # Ensure they sum to 100 (handle rounding)
        diff = 100 - (distribution["winning"] + distribution["equal"] + distribution["losing"])
        distribution["equal"] += diff
    else:
        distribution = {"winning": 33, "equal": 34, "losing": 33}
    
    return {
        "distribution": distribution,
        "total_blunders": total_blunders,
        "games_analyzed": len(analyses)
    }
