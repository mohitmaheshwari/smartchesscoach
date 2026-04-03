"""
Player Routes
=============

Handles player profile, progress, weaknesses, training, and blunder intelligence.

Endpoints:
- GET /progress/coaching-report - Coaching-oriented progress report
- GET /progress/journey - Trajectory data for progress page
- GET /progress - Progress metrics (rating, accuracy, blunders, habits)
- GET /progress/v2 - NEW Progress page with badges, coach assessment, before/after
- GET /badges - Badge scores
- GET /badges/{badge_key}/details - Badge drill-down
- GET /patterns - Mistake patterns
- GET /profile - Player coaching profile
- POST /profile/recalculate - Recalculate profile stats
- GET /profile/weaknesses - Top weaknesses with decay
- GET /profile/strengths - Player strengths
- PATCH /profile/preferences - Update coaching preferences
- GET /weakness-categories - Predefined weakness categories
- POST /profile/challenge-result - Record challenge result
- GET /loss-streak-status - Loss streak / Plateau Breaker check
- GET /blind-spots - Recurring turning point patterns
- GET /training-recommendations - AI training recommendations
- GET /rating/trajectory - Rating prediction and trajectory
- GET /training/time-management - Time management analysis
- GET /training/fast-thinking - Calculation speed analysis
- GET /training/puzzles - Personalized puzzles from mistakes
- POST /training/puzzles/{puzzle_index}/solve - Submit puzzle solution
- GET /progress/player-profile - Player coaching narrative profile
- GET /progress/evolution - Rolling window evolution data
- GET /progress/openings - Opening performance evolution
- GET /positional-insight/{structure_id} - Pawn structure deep dive
- GET /knowledge-base/structures - All pawn structures
- GET /knowledge-base/imbalances - All strategic imbalances
- GET /weakness-ranking - Dominant weakness ranking
- GET /win-state - Win-state blunder analysis
- GET /heatmap - Mistake heatmap
- POST /drill/positions - Pattern drill positions
- GET /rating-impact - Rating impact estimate
- GET /identity - Chess identity profile
- GET /mission - Current mission
- GET /milestones - Achievement milestones
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
import logging
import json

logger = logging.getLogger(__name__)

# Create router for player endpoints
router = APIRouter(tags=["Player"])

# Database reference - will be set by server.py
db = None

# LLM function reference - will be set by server.py
call_llm_fn = None


def set_db(database):
    """Set the database reference for player routes"""
    global db
    db = database


def set_llm(llm_fn):
    """Set the LLM function reference for player routes"""
    global call_llm_fn
    call_llm_fn = llm_fn


# Import User model and get_current_user from auth routes
from routes.auth import User, get_current_user

# Import from config
from config import DEFAULT_RATING

# Import Player Profile service
from player_profile_service import (
    get_or_create_profile,
    record_challenge_result,
    WEAKNESS_CATEGORIES,
    LearningStyle,
    CoachingTone
)

# Import Rating & Training service
from rating_service import (
    predict_rating_trajectory,
    calculate_improvement_velocity,
    analyze_time_usage,
    generate_calculation_analysis,
    fetch_platform_ratings
)

# Import Blunder Intelligence service
from blunder_intelligence_service import (
    get_dominant_weakness_ranking,
    get_win_state_analysis,
    get_mistake_heatmap,
    estimate_rating_impact,
    get_identity_profile,
    get_mission,
    check_milestones,
    get_drill_positions
)


# ==================== PYDANTIC MODELS ====================

class UpdateCoachingPreferencesRequest(BaseModel):
    learning_style: Optional[str] = None  # "concise" or "detailed"
    coaching_tone: Optional[str] = None   # "firm", "encouraging", "balanced"


class RecordChallengeResultRequest(BaseModel):
    weakness_category: str
    weakness_subcategory: str
    success: bool
    puzzle_id: Optional[str] = None


class DrillRequest(BaseModel):
    """Request for drill positions"""
    pattern: Optional[str] = None  # Behavioral pattern to filter by
    state: Optional[str] = None  # Game state: "winning", "equal", "losing"
    limit: int = 5


# ==================== PROGRESS ROUTES ====================


@router.get("/progress/coaching-report")
async def get_coaching_progress_report(user: User = Depends(get_current_user)):
    """
    Coaching-oriented progress report.
    Tracks weakness control, habits evolution, phase understanding, review impact.
    """
    from services.progress_report_service import build_coaching_report
    report = await build_coaching_report(db, user.user_id)
    return report


@router.get("/progress/journey")
async def get_progress_journey(user: User = Depends(get_current_user)):
    """
    Progress V2 — trajectory data for the reimagined progress page.
    Returns: accuracy journey (per-game), biggest shift, still leaking area, win rate trend.
    """
    # Get per-game accuracy + blunders chronologically
    analyses = await db.game_analyses.find(
        {"user_id": user.user_id},
        {"_id": 0, "game_id": 1, "stockfish_analysis.accuracy": 1, "stockfish_analysis.blunders": 1,
         "stockfish_analysis.mistakes": 1, "created_at": 1}
    ).sort("created_at", 1).to_list(100)

    games = await db.games.find(
        {"user_id": user.user_id, "is_analyzed": True},
        {"_id": 0, "game_id": 1, "result": 1, "user_color": 1, "opponent_name": 1,
         "white_player": 1, "black_player": 1, "imported_at": 1}
    ).sort("imported_at", 1).to_list(100)

    game_lookup = {g["game_id"]: g for g in games}

    # Build journey points
    journey = []
    for a in analyses:
        gid = a.get("game_id", "")
        sf = a.get("stockfish_analysis", {})
        acc = sf.get("accuracy")
        if acc is None:
            continue
        g = game_lookup.get(gid, {})
        user_color = g.get("user_color", "white")
        result = g.get("result", "")
        user_won = (result == "1-0" and user_color == "white") or (result == "0-1" and user_color == "black")
        is_draw = "1/2" in result

        opp = g.get("opponent_name") or (g.get("white_player") if user_color == "black" else g.get("black_player")) or ""
        journey.append({
            "game_id": gid,
            "accuracy": round(acc, 1),
            "blunders": sf.get("blunders", 0),
            "mistakes": sf.get("mistakes", 0),
            "result": "W" if user_won else ("D" if is_draw else "L"),
            "opponent": opp[:12],
        })

    # Thinking score history from thinking_scores
    scores = await db.thinking_scores.find(
        {"user_id": user.user_id},
        {"_id": 0, "game_id": 1, "habit_scores": 1, "calculated_at": 1}
    ).sort("calculated_at", 1).to_list(100)

    # Build dimension trends (from thinking_scores habit_scores)
    dimensions = {}  # {dimension: [scores over time]}
    for s in scores:
        hs = s.get("habit_scores", {})
        for dim, data in hs.items():
            if isinstance(data, dict) and "score" in data:
                if dim not in dimensions:
                    dimensions[dim] = []
                dimensions[dim].append(data["score"])

    # Find biggest shift (most improved dimension in last 10 vs prev 10)
    biggest_shift = None
    still_leaking = None
    best_delta = 0
    worst_stagnant = None

    for dim, vals in dimensions.items():
        if len(vals) < 5:
            continue
        recent = vals[-min(10, len(vals)):]
        older = vals[:-len(recent)] if len(vals) > len(recent) else vals[:len(vals)//2]
        if not older:
            continue
        recent_avg = sum(recent) / len(recent)
        older_avg = sum(older) / len(older)
        delta = recent_avg - older_avg
        pct = (delta / max(older_avg, 1)) * 100

        readable = dim.replace("_", " ").title()
        if delta > best_delta:
            best_delta = delta
            biggest_shift = {
                "dimension": readable,
                "from_score": round(older_avg, 1),
                "to_score": round(recent_avg, 1),
                "delta_pct": round(pct),
            }
        if abs(delta) < 3 and recent_avg < 50:
            if worst_stagnant is None or recent_avg < worst_stagnant["score"]:
                worst_stagnant = {"dimension": readable, "score": round(recent_avg, 1), "games_stuck": len(vals)}

    still_leaking = worst_stagnant

    # Win rate trend (last 10 vs prev 10)
    recent_games = journey[-10:] if len(journey) >= 10 else journey
    prev_games = journey[-20:-10] if len(journey) >= 20 else journey[:max(len(journey)//2, 1)]
    recent_wins = sum(1 for g in recent_games if g["result"] == "W")
    recent_losses = sum(1 for g in recent_games if g["result"] == "L")
    prev_wins = sum(1 for g in prev_games if g["result"] == "W")
    prev_losses = sum(1 for g in prev_games if g["result"] == "L")

    win_trend = {
        "recent": {"wins": recent_wins, "losses": recent_losses, "total": len(recent_games)},
        "previous": {"wins": prev_wins, "losses": prev_losses, "total": len(prev_games)},
        "improving": recent_wins > prev_wins,
    }

    # Current accuracy
    recent_acc = [g["accuracy"] for g in journey[-10:]] if journey else []
    current_accuracy = round(sum(recent_acc) / len(recent_acc), 1) if recent_acc else 0

    return {
        "journey": journey,
        "current_accuracy": current_accuracy,
        "games_analyzed": len(journey),
        "biggest_shift": biggest_shift,
        "still_leaking": still_leaking,
        "win_trend": win_trend,
    }


@router.get("/progress")
async def get_progress_metrics(user: User = Depends(get_current_user)):
    """
    Get progress metrics for the /progress page.
    Shows rating, accuracy, blunders, and habit trends.
    """
    user_doc = await db.users.find_one({"user_id": user.user_id}, {"_id": 0})

    # Fetch rating data
    rating_data = {"current": None, "change": 0, "peak": None, "habit_correlation": None}

    # Check both field naming conventions
    chess_com_user = user_doc.get("chesscom_username") or user_doc.get("chess_com_username")
    lichess_user = user_doc.get("lichess_username")

    if chess_com_user or lichess_user:
        try:
            ratings = await fetch_platform_ratings(chess_com_user, lichess_user)
            if ratings:
                # Get rating from chess_com or lichess
                platform_data = ratings.get("chess_com") or ratings.get("lichess") or {}
                for category in ["rapid", "blitz", "bullet"]:
                    rating_val = platform_data.get(category)
                    if rating_val:
                        rating_data["current"] = rating_val
                        rating_data["peak"] = rating_val  # We don't have historical peak easily
                        break
        except Exception as e:
            logger.warning(f"Failed to fetch ratings: {e}")

    # Get recent analyses for accuracy and blunders
    recent_analyses = await db.game_analyses.find(
        {"user_id": user.user_id},
        {"_id": 0, "accuracy": 1, "blunders": 1, "mistakes": 1, "created_at": 1,
         "stockfish_failed": 1, "stockfish_analysis": 1}
    ).sort("created_at", -1).limit(20).to_list(20)

    # Filter out analyses where Stockfish failed - only use accurate data
    valid_analyses = [a for a in recent_analyses if not a.get("stockfish_failed", False)]

    # Calculate accuracy trend (only from valid Stockfish analyses)
    accuracy_data = {"current": None, "previous": None, "trend": "stable"}
    if valid_analyses:
        # Get accuracy from stockfish_analysis if available, else top-level
        def get_accuracy(a):
            sf = a.get("stockfish_analysis", {})
            if sf and sf.get("accuracy"):
                return sf.get("accuracy")
            return a.get("accuracy", 0)

        recent_10 = [get_accuracy(a) for a in valid_analyses[:10] if get_accuracy(a) > 0]
        previous_10 = [get_accuracy(a) for a in valid_analyses[10:20] if get_accuracy(a) > 0]

        if recent_10:
            accuracy_data["current"] = round(sum(recent_10) / len(recent_10), 1)
        if previous_10:
            accuracy_data["previous"] = round(sum(previous_10) / len(previous_10), 1)

        if accuracy_data["current"] and accuracy_data["previous"]:
            diff = accuracy_data["current"] - accuracy_data["previous"]
            if diff > 2:
                accuracy_data["trend"] = "improving"
            elif diff < -2:
                accuracy_data["trend"] = "worsening"

    # Helper to count blunders from Stockfish data
    def get_blunders_count(a):
        sf = a.get("stockfish_analysis", {})
        evals = sf.get("move_evaluations", [])
        return sum(1 for m in evals if m.get("evaluation") == "blunder")

    # Calculate blunder trend (only from valid Stockfish analyses)
    blunders_data = {"avg_per_game": None, "total": 0, "trend": "stable"}
    if valid_analyses:
        recent_blunders = [get_blunders_count(a) for a in valid_analyses[:10]]
        previous_blunders = [get_blunders_count(a) for a in valid_analyses[10:20]]

        if recent_blunders:
            blunders_data["total"] = sum(recent_blunders)
            blunders_data["avg_per_game"] = round(sum(recent_blunders) / len(recent_blunders), 1)

        if recent_blunders and previous_blunders:
            recent_avg = sum(recent_blunders) / len(recent_blunders)
            prev_avg = sum(previous_blunders) / len(previous_blunders)
            if recent_avg < prev_avg - 0.3:
                blunders_data["trend"] = "improving"
            elif recent_avg > prev_avg + 0.3:
                blunders_data["trend"] = "worsening"

    # Track how many valid vs failed analyses
    valid_count = len(valid_analyses)
    len(recent_analyses) - valid_count

    # Get habits from profile
    profile = await db.player_profiles.find_one(
        {"user_id": user.user_id},
        {"_id": 0}
    )

    habits = []
    resolved_habits = []

    if profile:
        top_weaknesses = profile.get("top_weaknesses", [])
        for i, w in enumerate(top_weaknesses[:5]):
            habits.append({
                "name": w.get("subcategory", "").replace("_", " ").title(),
                "category": w.get("category", ""),
                "occurrences_recent": w.get("occurrences", 0),
                "trend": "stable",  # Could calculate from history
                "is_active": i == 0  # Only first one is active
            })

        # Get resolved weaknesses
        resolved = profile.get("resolved_weaknesses", [])
        for r in resolved[:5]:
            resolved_habits.append({
                "name": r.get("name", ""),
                "message": f"Fixed: {r.get('name', '')}",
                "resolved_at": r.get("resolved_at")
            })

        # Also include habits resolved via PDR rotation
        rotated_habits = profile.get("resolved_habits", [])
        for r in rotated_habits:
            stats = r.get("final_stats", {})
            resolved_habits.append({
                "name": r.get("habit", "").replace("_", " ").title(),
                "message": f"Mastered via reflection ({stats.get('correct_attempts', 0)}/{stats.get('total_attempts', 0)} correct)",
                "resolved_at": r.get("resolved_at")
            })

    # Get PDR reflection stats for habits
    from habit_rotation_service import get_all_habit_statuses
    habit_statuses = await get_all_habit_statuses(db, user.user_id)

    # Enrich habits with reflection stats
    for habit in habits:
        habit_name_lower = habit["name"].lower().replace(" ", "_")
        for status in habit_statuses:
            if status.get("habit", "").lower() == habit_name_lower:
                habit["reflection_stats"] = {
                    "correct": status.get("correct_attempts", 0),
                    "total": status.get("total_attempts", 0),
                    "consecutive": status.get("consecutive_correct", 0),
                    "status": status.get("status", "active")
                }
                break

    # Correlate rating to habit if possible
    if rating_data.get("change") and rating_data["change"] > 0 and habits:
        rating_data["habit_correlation"] = f"Reduced {habits[0]['name'].lower()} may have contributed."

    # Check for any failed analyses that need retry
    failed_analyses = await db.game_analyses.find(
        {"user_id": user.user_id, "stockfish_failed": True},
        {"_id": 0, "game_id": 1}
    ).to_list(10)

    failed_game_ids = [f["game_id"] for f in failed_analyses]

    return {
        "rating": rating_data,
        "accuracy": accuracy_data,
        "blunders": blunders_data,
        "habits": habits,
        "resolved_habits": resolved_habits,
        "failed_analyses": failed_game_ids,
        "failed_analysis_count": len(failed_game_ids),
        "valid_analysis_count": valid_count,
        "total_analysis_count": len(recent_analyses)
    }


@router.get("/progress/v2")
async def get_progress_v2(user: User = Depends(get_current_user)):
    """
    NEW Progress Page - Chess DNA Badges + Coach Assessment + Before/After Comparison

    Returns:
    - Coach's honest assessment (not just stats)
    - Rating reality (framed constructively)
    - 8 skill badges with trends
    - Proof from games
    - Memorable rules
    - Next 10 games plan
    - Before Coach vs After Coach comparison (stats AND patterns)
    """
    from coach_assessment_service import generate_full_progress_data
    from baseline_service import (
        get_or_create_baseline,
        get_baseline_patterns,
        calculate_current_stats,
        calculate_progress,
        calculate_pattern_snapshot,
        compare_patterns,
        MIN_GAMES_FOR_BASELINE
    )

    try:
        progress_data = await generate_full_progress_data(db, user.user_id)

        # Add Before/After Coach comparison
        all_analyses = await db.game_analyses.find(
            {"user_id": user.user_id}
        ).sort("created_at", -1).to_list(200)

        all_games = await db.games.find(
            {"user_id": user.user_id}
        ).sort("imported_at", -1).to_list(200)

        # Get or create baseline (snapshot from when user started)
        baseline = await get_or_create_baseline(db, user.user_id, all_analyses, all_games)

        # Get baseline patterns (weaknesses, blunder context from first games)
        baseline_patterns = await get_baseline_patterns(db, user.user_id)

        # If baseline exists but patterns don't (legacy user), create patterns now
        if baseline and not baseline_patterns:
            baseline_analyses = sorted(all_analyses, key=lambda x: x.get('created_at', ''))[:MIN_GAMES_FOR_BASELINE]
            baseline_games = sorted(all_games, key=lambda x: x.get('imported_at', ''))[:MIN_GAMES_FOR_BASELINE]
            baseline_patterns = calculate_pattern_snapshot(baseline_analyses, baseline_games)

            # Save it for future use
            await db.users.update_one(
                {'user_id': user.user_id},
                {'$set': {'baseline_patterns': baseline_patterns}}
            )

        # Calculate current stats from recent 25 games
        recent_analyses = all_analyses[:25] if len(all_analyses) > 25 else all_analyses
        recent_games = all_games[:25] if len(all_games) > 25 else all_games
        current_stats = calculate_current_stats(recent_analyses, recent_games)

        # Calculate current patterns
        current_patterns = calculate_pattern_snapshot(recent_analyses, recent_games) if recent_analyses else None

        # Calculate progress (stats comparison)
        comparison = None
        if baseline and current_stats:
            comparison = calculate_progress(baseline, current_stats)

        # Calculate pattern comparison (weaknesses comparison)
        pattern_comparison = None
        if baseline_patterns and current_patterns:
            pattern_comparison = compare_patterns(baseline_patterns, current_patterns)

        # Add to response
        progress_data['coaching_comparison'] = {
            'has_baseline': baseline is not None,
            'games_until_baseline': max(0, MIN_GAMES_FOR_BASELINE - len(all_analyses)) if not baseline else 0,
            'baseline': baseline,
            'current': current_stats,
            'progress': comparison,
            # NEW: Pattern data for Before/After tabs
            'baseline_patterns': baseline_patterns,
            'current_patterns': current_patterns,
            'pattern_comparison': pattern_comparison
        }

        return progress_data
    except Exception as e:
        logger.error(f"Progress v2 error: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate progress data")


@router.get("/badges")
async def get_chess_badges(user: User = Depends(get_current_user)):
    """Get just the badge scores for quick display"""
    from badge_service import calculate_all_badges, get_badge_history, calculate_badge_trends

    try:
        badges = await calculate_all_badges(db, user.user_id)
        history = await get_badge_history(db, user.user_id)
        trends = calculate_badge_trends(badges, history)

        # Add trends to badges
        for key in badges.get("badges", {}):
            badges["badges"][key]["trend"] = trends.get(key, "stable")

        return badges
    except Exception as e:
        logger.error(f"Badges error: {e}")
        raise HTTPException(status_code=500, detail="Failed to calculate badges")



@router.get("/badges/{badge_key}/details")
async def get_badge_details_endpoint(badge_key: str, user: User = Depends(get_current_user)):
    """
    Get detailed drill-down for a specific badge.

    Returns:
    - Badge score and insight
    - Last 5 relevant games with specific moves
    - Each move includes FEN for board display (fen_after shows position AFTER the move)
    - Badge-specific commentary adjusted for user's rating level
    """
    from badge_service import get_badge_details, BADGES

    if badge_key not in BADGES:
        raise HTTPException(status_code=400, detail=f"Unknown badge: {badge_key}")

    try:
        # Get user's rating for rating-appropriate explanations
        user_doc = await db.users.find_one({"user_id": user.user_id}, {"_id": 0, "rating": 1})
        user_rating = user_doc.get("rating", 1200) if user_doc else 1200

        details = await get_badge_details(db, user.user_id, badge_key, user_rating)
        return details
    except Exception as e:
        logger.error(f"Badge details error for {badge_key}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get badge details")



# ==================== WEAKNESS/PATTERN ROUTES ====================

@router.get("/patterns")
async def get_patterns(user: User = Depends(get_current_user)):
    """Get all mistake patterns for the current user"""
    patterns = await db.mistake_patterns.find(
        {"user_id": user.user_id},
        {"_id": 0}
    ).sort("occurrences", -1).to_list(50)
    return patterns

# ==================== PLAYER PROFILE ROUTES ====================

@router.get("/profile")
async def get_player_profile(user: User = Depends(get_current_user)):
    """Get the player's coaching profile"""
    profile = await get_or_create_profile(db, user.user_id, user.name)
    return profile

@router.post("/profile/recalculate")
async def recalculate_profile_stats(user: User = Depends(get_current_user)):
    """
    Recalculate player profile stats from all game analyses.
    Use this to fix stale/out-of-sync profile data.
    """
    from datetime import datetime, timezone

    user_id = user.user_id
    current_time = datetime.now(timezone.utc)

    # Get all game analyses for user
    analyses = await db.game_analyses.find(
        {"user_id": user_id},
        {"_id": 0, "game_id": 1, "stockfish_analysis": 1, "analyzed_at": 1}
    ).to_list(1000)

    if not analyses:
        return {"error": "No analyzed games found", "games_count": 0}

    # Calculate totals
    total_blunders = 0
    total_mistakes = 0
    total_best_moves = 0
    total_inaccuracies = 0

    weakness_counts = {}

    for analysis in analyses:
        sf = analysis.get("stockfish_analysis", {})
        total_blunders += sf.get("blunders", 0)
        total_mistakes += sf.get("mistakes", 0)
        total_best_moves += sf.get("best_moves", 0)
        total_inaccuracies += sf.get("inaccuracies", 0)

        # Extract weaknesses from move evaluations
        for m in sf.get("move_evaluations", []):
            eval_type = m.get("evaluation")
            cp_loss = m.get("cp_loss", 0)

            # Only count actual blunders as one-move blunders (not mistakes or inaccuracies)
            if eval_type == "blunder" and 150 <= cp_loss <= 600:
                key = "tactical:one_move_blunder"
                weakness_counts[key] = weakness_counts.get(key, 0) + 1
            elif eval_type == "blunder" and cp_loss > 600:
                key = "tactical:complex_tactical_miss"
                weakness_counts[key] = weakness_counts.get(key, 0) + 1

    # Build top weaknesses list
    top_weaknesses = []
    for key, count in sorted(weakness_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
        category, subcategory = key.split(":")
        top_weaknesses.append({
            "category": category,
            "subcategory": subcategory,
            "occurrence_count": count,
            "last_occurrence": current_time.isoformat(),
            "decayed_score": round(count * 1.0, 2)
        })

    # Update profile
    await db.player_profiles.update_one(
        {"user_id": user_id},
        {"$set": {
            "games_analyzed_count": len(analyses),
            "total_blunders": total_blunders,
            "total_mistakes": total_mistakes,
            "total_best_moves": total_best_moves,
            "total_inaccuracies": total_inaccuracies,
            "top_weaknesses": top_weaknesses,
            "last_updated": current_time.isoformat(),
            "last_recalculated": current_time.isoformat()
        }}
    )

    return {
        "success": True,
        "games_analyzed": len(analyses),
        "total_blunders": total_blunders,
        "total_mistakes": total_mistakes,
        "total_best_moves": total_best_moves,
        "top_weaknesses": top_weaknesses[:3]
    }

@router.get("/profile/weaknesses")
async def get_ranked_weaknesses(user: User = Depends(get_current_user)):
    """Get player's top weaknesses with time decay applied"""
    profile = await db.player_profiles.find_one(
        {"user_id": user.user_id},
        {"_id": 0}
    )

    if not profile:
        return {"top_weaknesses": [], "message": "No profile found. Analyze some games first."}

    return {
        "top_weaknesses": profile.get("top_weaknesses", [])[:5],
        "improvement_trend": profile.get("improvement_trend", "stuck"),
        "games_analyzed": profile.get("games_analyzed_count", 0)
    }

@router.get("/profile/strengths")
async def get_player_strengths(user: User = Depends(get_current_user)):
    """Get player's identified strengths"""
    profile = await db.player_profiles.find_one(
        {"user_id": user.user_id},
        {"_id": 0}
    )

    if not profile:
        return {"strengths": [], "message": "No profile found. Analyze some games first."}

    return {
        "strengths": profile.get("strengths", []),
        "estimated_level": profile.get("estimated_level", "intermediate"),
        "estimated_elo": profile.get("estimated_elo", 1200)
    }

@router.get("/profile/strength-profile")
async def get_strength_profile(user: User = Depends(get_current_user)):
    """
    Get comprehensive strength profile — what the user is GOOD at.

    Returns per-domain scores (0-100):
    - tactical_vision: brilliant moves, sacrifices, tactical accuracy
    - calculation_depth: deep calculation, defense under pressure
    - positional_sense: quiet position accuracy, middlegame quality
    - endgame_technique: endgame accuracy
    - opening_knowledge: opening accuracy
    - pressure_handling: performance when winning/losing/equal

    Each domain includes a score, estimated rating, and evidence.
    """
    from services.strength_profile_service import build_strength_profile_for_user

    profile = await build_strength_profile_for_user(db, user.user_id, max_games=30)

    return profile


@router.patch("/profile/preferences")
async def update_coaching_preferences(
    req: UpdateCoachingPreferencesRequest,
    user: User = Depends(get_current_user)
):
    """Update coaching preferences (user override)"""
    update_data = {"last_updated": datetime.now(timezone.utc).isoformat()}

    if req.learning_style:
        if req.learning_style not in [LearningStyle.CONCISE.value, LearningStyle.DETAILED.value]:
            raise HTTPException(status_code=400, detail="Invalid learning_style. Use 'concise' or 'detailed'")
        update_data["learning_style"] = req.learning_style

    if req.coaching_tone:
        if req.coaching_tone not in [CoachingTone.FIRM.value, CoachingTone.ENCOURAGING.value, CoachingTone.BALANCED.value]:
            raise HTTPException(status_code=400, detail="Invalid coaching_tone. Use 'firm', 'encouraging', or 'balanced'")
        update_data["coaching_tone"] = req.coaching_tone

    await db.player_profiles.update_one(
        {"user_id": user.user_id},
        {"$set": update_data}
    )

    return {"message": "Preferences updated", "updated": update_data}

@router.get("/weakness-categories")
async def get_weakness_categories():
    """Get all predefined weakness categories"""
    return {"categories": WEAKNESS_CATEGORIES}

@router.post("/profile/challenge-result")
async def record_challenge_result_endpoint(
    req: RecordChallengeResultRequest,
    user: User = Depends(get_current_user)
):
    """Record a challenge result and potentially resolve weakness"""
    result = await record_challenge_result(
        db,
        user.user_id,
        req.weakness_category,
        req.weakness_subcategory,
        req.success
    )

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return result


# ==================== LOSS STREAK + BLIND SPOTS + RECOMMENDATIONS ====================


@router.get("/loss-streak-status")
async def get_loss_streak_status(user: User = Depends(get_current_user)):
    """
    Check if user is on a losing streak and should be shown the Plateau Breaker.

    Trigger conditions:
    - 3+ consecutive losses

    Returns:
    - show_plateau_breaker: bool
    - consecutive_losses: int
    - last_games: summary of recent results
    """
    try:
        # Get last 10 games sorted by date (most recent first)
        games = await db.games.find(
            {"user_id": user.user_id},
            {"_id": 0, "game_id": 1, "result": 1, "user_color": 1, "played_at": 1}
        ).sort("played_at", -1).to_list(10)

        if not games:
            return {
                "show_plateau_breaker": False,
                "consecutive_losses": 0,
                "message": "No games found",
                "last_games": []
            }

        # Count consecutive losses from most recent
        consecutive_losses = 0
        last_games_summary = []

        for game in games:
            result = game.get("result", "")
            user_color = game.get("user_color", "white")

            # Determine if user won, lost, or drew
            is_white_win = result == "1-0"
            is_black_win = result == "0-1"

            user_won = (user_color == "white" and is_white_win) or (user_color == "black" and is_black_win)
            user_lost = (user_color == "white" and is_black_win) or (user_color == "black" and is_white_win)

            game_summary = {
                "game_id": game.get("game_id"),
                "result": "win" if user_won else "loss" if user_lost else "draw"
            }
            last_games_summary.append(game_summary)

            # Count streak (only consecutive losses from the start)
            if len(last_games_summary) <= 5:  # Only check last 5 for streak
                if user_lost and consecutive_losses == len(last_games_summary) - 1:
                    consecutive_losses += 1
                elif not user_lost and consecutive_losses == len(last_games_summary) - 1:
                    # Streak broken - stop counting
                    pass

        # Trigger Plateau Breaker after 3+ consecutive losses
        show_plateau_breaker = consecutive_losses >= 3

        # Build message
        if consecutive_losses >= 3:
            message = f"You've lost {consecutive_losses} games in a row. Time to identify what's going wrong."
        elif consecutive_losses == 2:
            message = "Two losses in a row. One more and we need to talk."
        elif consecutive_losses == 1:
            message = "Shake off that last loss."
        else:
            message = "You're doing fine. Keep playing!"

        return {
            "show_plateau_breaker": show_plateau_breaker,
            "consecutive_losses": consecutive_losses,
            "message": message,
            "last_games": last_games_summary[:5]
        }

    except Exception as e:
        logger.error(f"Loss streak check failed: {e}")
        return {
            "show_plateau_breaker": False,
            "consecutive_losses": 0,
            "message": "Could not check loss streak",
            "last_games": []
        }


@router.get("/blind-spots")
async def get_blind_spots(user: User = Depends(get_current_user)):
    """
    Get user's blind spots - recurring turning point patterns across games.

    Returns categorized patterns that cost the user games, for home page display.
    """

    # Get recent game analyses with turning points
    analyses = await db.game_analyses.find(
        {"user_id": user.user_id},
        {"_id": 0, "game_id": 1, "turning_point": 1, "stockfish_analysis": 1}
    ).sort("analyzed_at", -1).to_list(20)

    if not analyses:
        return {
            "blind_spots": [],
            "total_games_analyzed": 0,
            "games_with_turning_points": 0
        }

    # Count turning point categories
    category_counts = {}
    games_with_tp = 0

    for analysis in analyses:
        tp = analysis.get("turning_point")
        if not tp:
            continue

        games_with_tp += 1
        category = tp.get("category", "unknown")
        category_label = tp.get("category_label", category.replace("_", " ").title())
        pattern_name = tp.get("pattern_name", "")

        if category not in category_counts:
            category_counts[category] = {
                "count": 0,
                "label": category_label,
                "patterns": [],
                "game_ids": []
            }

        category_counts[category]["count"] += 1
        category_counts[category]["game_ids"].append(analysis.get("game_id"))

        if pattern_name and pattern_name not in category_counts[category]["patterns"]:
            category_counts[category]["patterns"].append(pattern_name)

    # Sort by count and build response
    sorted_categories = sorted(
        category_counts.items(),
        key=lambda x: x[1]["count"],
        reverse=True
    )

    # Training focus mapping
    training_focus_map = {
        "tactical_blindness": "tactics",
        "threat_ignorance": "threat_awareness",
        "positional_mistake": "positional",
        "calculation_error": "calculation",
        "piece_coordination": "piece_coordination",
        "king_safety": "king_safety",
        "one_move_blunder": "blunder_check"
    }

    blind_spots = []
    for category, data in sorted_categories[:5]:  # Top 5 blind spots
        # Generate description based on patterns
        patterns_str = ", ".join(data["patterns"][:3]) if data["patterns"] else "various patterns"

        blind_spots.append({
            "category": category,
            "label": data["label"],
            "count": data["count"],
            "total_games": len(analyses),
            "percentage": round(data["count"] / len(analyses) * 100),
            "patterns": data["patterns"][:3],
            "description": f"Lost {data['count']} games to {patterns_str.lower()}",
            "training_focus": training_focus_map.get(category, "general"),
            "severity": "high" if data["count"] >= 3 else "medium" if data["count"] >= 2 else "low"
        })

    return {
        "blind_spots": blind_spots,
        "total_games_analyzed": len(analyses),
        "games_with_turning_points": games_with_tp
    }


@router.get("/training-recommendations")
async def get_training_recommendations(user: User = Depends(get_current_user)):
    """Get AI-generated training recommendations based on weaknesses"""

    patterns = await db.mistake_patterns.find(
        {"user_id": user.user_id},
        {"_id": 0}
    ).sort("occurrences", -1).to_list(10)

    if not patterns:
        return {
            "recommendations": [
                {
                    "title": "Import Your Games",
                    "description": "Start by importing games from Chess.com or Lichess to get personalized recommendations.",
                    "priority": "high"
                }
            ]
        }

    patterns_text = "\n".join([
        f"- {p['subcategory']} ({p['category']}): {p['occurrences']} occurrences - {p['description']}"
        for p in patterns
    ])

    system_message = """You are a chess coach creating a personalized training plan.
Based on the player's mistake patterns, suggest 3-5 specific training exercises.
Be specific and actionable. Respond in JSON format:
{
    "recommendations": [
        {"title": "...", "description": "...", "priority": "high/medium/low", "estimated_time": "15 mins"}
    ]
}"""

    try:
        response = await call_llm_fn(
            system_message=system_message,
            user_message=f"Create training recommendations for a player with these weakness patterns:\n{patterns_text}",
            model="gpt-4o-mini"
        )

        response_clean = response.strip()
        if response_clean.startswith("```json"):
            response_clean = response_clean[7:]
        if response_clean.startswith("```"):
            response_clean = response_clean[3:]
        if response_clean.endswith("```"):
            response_clean = response_clean[:-3]

        return json.loads(response_clean)

    except Exception as e:
        logger.error(f"Recommendation error: {e}")
        return {
            "recommendations": [
                {
                    "title": "Practice Tactical Puzzles",
                    "description": "Based on your patterns, focus on tactical awareness exercises.",
                    "priority": "high"
                }
            ]
        }

# ==================== RATING & TRAINING ENDPOINTS ====================

@router.get("/rating/trajectory")
async def get_rating_trajectory(user: User = Depends(get_current_user)):
    """
    Get rating prediction and trajectory for the user.
    Includes platform ratings, projected ratings, and time to milestones.
    """
    # Get user data
    user_doc = await db.users.find_one({"user_id": user.user_id}, {"_id": 0})
    chess_com_username = user_doc.get("chess_com_username")
    lichess_username = user_doc.get("lichess_username")

    # Fetch platform ratings
    platform_ratings = await fetch_platform_ratings(chess_com_username, lichess_username)

    # Get current best rating
    current_rating = DEFAULT_RATING  # Default
    rating_source = "estimated"

    if platform_ratings.get('chess_com', {}).get('rapid'):
        current_rating = platform_ratings['chess_com']['rapid']
        rating_source = "chess_com_rapid"
    elif platform_ratings.get('lichess', {}).get('rapid'):
        current_rating = platform_ratings['lichess']['rapid']
        rating_source = "lichess_rapid"
    elif platform_ratings.get('chess_com', {}).get('blitz'):
        current_rating = platform_ratings['chess_com']['blitz']
        rating_source = "chess_com_blitz"
    elif platform_ratings.get('lichess', {}).get('blitz'):
        current_rating = platform_ratings['lichess']['blitz']
        rating_source = "lichess_blitz"

    # Get game analyses for improvement velocity
    analyses = await db.game_analyses.find(
        {"user_id": user.user_id},
        {"_id": 0, "blunders": 1, "mistakes": 1, "best_moves": 1, "analyzed_at": 1}
    ).to_list(50)

    # Calculate improvement velocity
    velocity = calculate_improvement_velocity(analyses)

    # Get weaknesses
    profile = await db.player_profiles.find_one(
        {"user_id": user.user_id},
        {"_id": 0, "top_weaknesses": 1, "estimated_elo": 1}
    )
    weaknesses = profile.get("top_weaknesses", []) if profile else []

    # If we don't have platform rating, use profile estimate
    if rating_source == "estimated" and profile:
        current_rating = profile.get("estimated_elo", 1200)

    # Generate trajectory prediction
    trajectory = predict_rating_trajectory(current_rating, velocity, weaknesses)

    return {
        "platform_ratings": platform_ratings,
        "current_rating": current_rating,
        "rating_source": rating_source,
        "improvement_velocity": velocity,
        "trajectory": trajectory,
        "linked_accounts": {
            "chess_com": chess_com_username,
            "lichess": lichess_username
        }
    }

@router.get("/training/time-management")
async def get_time_management_analysis(user: User = Depends(get_current_user)):
    """
    Analyze time management patterns from recent games.
    Shows clock usage, time trouble patterns, and recommendations.
    """
    # Get recent games with PGN
    games = await db.games.find(
        {"user_id": user.user_id},
        {"_id": 0, "pgn": 1, "user_color": 1, "time_control": 1, "result": 1}
    ).sort("imported_at", -1).to_list(30)

    if not games:
        return {
            "has_data": False,
            "message": "Import some games first to analyze your time management."
        }

    # Analyze time usage
    analysis = analyze_time_usage(games, user.user_id)

    return analysis

@router.get("/training/fast-thinking")
async def get_fast_thinking_analysis(user: User = Depends(get_current_user)):
    """
    Get analysis of calculation speed and pattern recognition.
    Includes tips for thinking faster and spotting tactics.
    """
    # Get analyses with move-by-move data
    analyses = await db.game_analyses.find(
        {"user_id": user.user_id},
        {"_id": 0, "move_by_move": 1, "analyzed_at": 1}
    ).sort("analyzed_at", -1).to_list(20)

    # Generate calculation analysis
    calc_analysis = generate_calculation_analysis(analyses)

    # Get weaknesses for targeted tips
    profile = await db.player_profiles.find_one(
        {"user_id": user.user_id},
        {"_id": 0, "top_weaknesses": 1}
    )
    weaknesses = profile.get("top_weaknesses", []) if profile else []

    # Add weakness-specific tips
    if weaknesses and calc_analysis.get("has_data"):
        top_weakness = weaknesses[0].get('subcategory', '')
        calc_analysis["focus_weakness"] = top_weakness
        calc_analysis["weakness_tip"] = f"Focus on spotting {top_weakness.replace('_', ' ')} patterns faster"

    return calc_analysis


@router.get("/training/puzzles")
async def get_training_puzzles(
    limit: int = 10,
    user: User = Depends(get_current_user)
):
    """
    Get personalized puzzles from user's own mistakes.
    """
    from interactive_training_service import get_user_puzzles

    puzzles = await get_user_puzzles(db, user.user_id, limit)

    return {
        "puzzles": puzzles,
        "total": len(puzzles),
        "source": "your_games"
    }

@router.post("/training/puzzles/{puzzle_index}/solve")
async def submit_puzzle_solution(
    puzzle_index: int,
    solution: str,
    time_taken_seconds: int,
    user: User = Depends(get_current_user)
):
    """
    Submit a puzzle solution and track progress.
    """
    # Record puzzle attempt
    puzzle_attempt = {
        "user_id": user.user_id,
        "puzzle_index": puzzle_index,
        "solution_submitted": solution,
        "time_taken_seconds": time_taken_seconds,
        "attempted_at": datetime.now(timezone.utc).isoformat()
    }

    await db.puzzle_attempts.insert_one(puzzle_attempt)

    # Update profile stats
    await db.player_profiles.update_one(
        {"user_id": user.user_id},
        {
            "$inc": {
                "puzzles_attempted": 1,
                "total_puzzle_time_seconds": time_taken_seconds
            }
        },
        upsert=True
    )

    return {
        "message": "Solution recorded",
        "time_taken_seconds": time_taken_seconds
    }


# ==================== PROGRESS PLAYER PROFILE ====================


@router.get("/progress/player-profile")
async def get_player_profile_endpoint(user: User = Depends(get_current_user)):
    """Get player's coaching narrative profile."""
    from services.player_profile_service import get_player_profile
    profile = await get_player_profile(db, user.user_id)
    return profile


# ==================== PROGRESS EVOLUTION + KNOWLEDGE BASE ====================


@router.get("/progress/evolution")
async def get_progress_evolution(user: User = Depends(get_current_user)):
    """
    Get rolling window evolution data.

    Replaces baseline-based progress with continuous improvement tracking:
    - macro: 25 vs 25 games (monthly trend)
    - medium: 10 vs 10 games (bi-weekly trend)
    - micro: 5 vs 5 games (weekly trend)

    Returns:
    - Window metrics for each granularity
    - Delta (change) between windows
    - Trend assessment
    """
    from services.rolling_evolution_service import get_rolling_evolution
    return await get_rolling_evolution(db, user.user_id)


@router.get("/progress/openings")
async def get_opening_evolution(user: User = Depends(get_current_user)):
    """
    Get opening performance evolution.

    Shows:
    - Openings you're improving in
    - Openings not working for you
    - Recommendations

    Compares last 25 games vs previous 25 games.
    """
    from services.opening_evolution_service import get_user_opening_evolution
    return await get_user_opening_evolution(db, user.user_id, window_size=25)


@router.get("/positional-insight/{structure_id}")
async def get_structure_deep_dive(structure_id: str, user: User = Depends(get_current_user)):
    """
    Get detailed positional insight for a specific pawn structure.

    Returns complete knowledge base entry with:
    - Plans for both sides
    - Typical errors
    - Conversion patterns
    - Key squares and piece placement
    """
    try:
        from positional_coaching_service import get_structure_deep_dive as get_deep_dive
        deep_dive = get_deep_dive(structure_id, "white")  # Color context added dynamically

        if not deep_dive:
            raise HTTPException(status_code=404, detail="Structure not found in knowledge base")

        return deep_dive
    except ImportError:
        raise HTTPException(status_code=500, detail="Positional coaching service not available")


@router.get("/knowledge-base/structures")
async def get_all_structures(user: User = Depends(get_current_user)):
    """
    Get summary of all pawn structures in the knowledge base.
    """
    try:
        from positional_coaching_service import get_all_structures_summary
        return {"structures": get_all_structures_summary()}
    except ImportError:
        raise HTTPException(status_code=500, detail="Knowledge base not available")


@router.get("/knowledge-base/imbalances")
async def get_all_imbalances(user: User = Depends(get_current_user)):
    """
    Get summary of all strategic imbalances in the knowledge base.
    """
    try:
        from positional_coaching_service import get_all_imbalances_summary
        return {"imbalances": get_all_imbalances_summary()}
    except ImportError:
        raise HTTPException(status_code=500, detail="Knowledge base not available")


# ==================== BLUNDER INTELLIGENCE ====================


@router.get("/weakness-ranking")
async def get_weakness_ranking(user: User = Depends(get_current_user)):
    """
    Get dominant weakness ranking.

    Returns:
    - #1 Rating Killer
    - Secondary Weakness
    - Stable Strength
    """
    analyses = await db.game_analyses.find(
        {"user_id": user.user_id}
    ).sort("created_at", -1).limit(15).to_list(15)

    return get_dominant_weakness_ranking(analyses)


@router.get("/win-state")
async def get_win_state(user: User = Depends(get_current_user)):
    """
    Get win-state analysis.

    Returns when blunders happen:
    - When winning (with evidence)
    - When equal (with evidence)
    - When losing (with evidence)
    """
    analyses = await db.game_analyses.find(
        {"user_id": user.user_id}
    ).sort("created_at", -1).limit(15).to_list(15)

    games = await db.games.find(
        {"user_id": user.user_id}
    ).sort("imported_at", -1).limit(15).to_list(15)

    # Remove MongoDB _id
    for game in games:
        if "_id" in game:
            del game["_id"]

    return get_win_state_analysis(analyses, games)


@router.get("/heatmap")
async def get_heatmap(user: User = Depends(get_current_user)):
    """
    Get mistake heatmap data.

    Returns:
    - Squares where mistakes occurred
    - Board region analysis
    - Hot squares
    """
    analyses = await db.game_analyses.find(
        {"user_id": user.user_id}
    ).sort("created_at", -1).limit(15).to_list(15)

    return get_mistake_heatmap(analyses)


@router.post("/drill/positions")
async def get_drill_positions_endpoint(req: DrillRequest, user: User = Depends(get_current_user)):
    """
    Get positions for Pattern Drill Mode.

    Returns positions where user made mistakes, for training.
    Filter by:
    - pattern: Behavioral pattern (e.g., "attacks_before_checking_threats")
    - state: Game state when blunder occurred ("winning", "equal", "losing")
    """
    analyses = await db.game_analyses.find(
        {"user_id": user.user_id}
    ).sort("created_at", -1).limit(20).to_list(20)

    games = await db.games.find(
        {"user_id": user.user_id}
    ).sort("date", -1).limit(20).to_list(20)

    # Remove MongoDB _id
    for game in games:
        if "_id" in game:
            del game["_id"]

    positions = get_drill_positions(
        analyses,
        games,
        pattern=req.pattern,
        state=req.state,
        limit=req.limit
    )

    return {
        "positions": positions,
        "total": len(positions),
        "pattern": req.pattern,
        "state": req.state
    }


@router.get("/rating-impact")
async def get_rating_impact(user: User = Depends(get_current_user)):
    """
    Get rating impact estimate.

    Returns:
    - Potential rating gain if dominant weakness fixed
    - Confidence level
    """
    analyses = await db.game_analyses.find(
        {"user_id": user.user_id}
    ).sort("created_at", -1).limit(15).to_list(15)

    return estimate_rating_impact(analyses)


@router.get("/identity")
async def get_identity(user: User = Depends(get_current_user)):
    """
    Get chess identity profile.

    Returns:
    - Identity label (e.g., "Aggressive but careless")
    - Description
    """
    analyses = await db.game_analyses.find(
        {"user_id": user.user_id}
    ).sort("created_at", -1).limit(15).to_list(15)

    return get_identity_profile(analyses)


@router.get("/mission")
async def get_current_mission(user: User = Depends(get_current_user)):
    """
    Get current mission based on weakness + rating tier.

    Mission Engine - 3 Layer Architecture:
    Layer 1: Weakness Type → Determines THEME
    Layer 2: Rating Tier → Adjusts DIFFICULTY
    Layer 3: Mission Difficulty → Actual challenge
    """
    analyses = await db.game_analyses.find(
        {"user_id": user.user_id}
    ).sort("created_at", -1).limit(15).to_list(15)

    # Get user's rating from recent games
    user_rating = None
    recent_games = await db.games.find(
        {"user_id": user.user_id, "is_analyzed": True}
    ).sort("imported_at", -1).limit(5).to_list(5)

    for game in recent_games:
        pgn = game.get("pgn", "")
        user_color = game.get("user_color", "white")

        # Extract user's rating from PGN
        import re
        if user_color == "white":
            match = re.search(r'\[WhiteElo "(\d+)"\]', pgn)
        else:
            match = re.search(r'\[BlackElo "(\d+)"\]', pgn)

        if match:
            user_rating = int(match.group(1))
            break

    return get_mission(analyses, user_rating=user_rating)


@router.get("/milestones")
async def get_milestones(user: User = Depends(get_current_user)):
    """
    Get achievement milestones.

    Returns list of achieved and available milestones.
    """
    analyses = await db.game_analyses.find(
        {"user_id": user.user_id}
    ).sort("created_at", -1).limit(50).to_list(50)

    # Get user stats for milestone tracking
    user_stats = await db.user_stats.find_one({"user_id": user.user_id})

    return {
        "achieved": check_milestones(analyses, user_stats),
        "total_games": len(analyses)
    }
