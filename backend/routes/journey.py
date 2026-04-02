"""
Journey Routes
==============

Handles journey dashboard, account linking, sync, and progress tracking.

Endpoints:
- GET /journey - Get journey dashboard data
- GET /journey/comprehensive - Get comprehensive chess journey
- GET /journey/weekly-assessment - Get weekly assessment paragraph
- GET /journey/weakness-trends - Get weakness trend data
- POST /journey/link-account - Link Chess.com or Lichess account
- GET /journey/linked-accounts - Get linked accounts
- POST /journey/unlink-account - Unlink a chess account
- POST /journey/sync-now - Trigger manual game sync
- GET /journey/intelligence - Get comprehensive journey intelligence
- GET /journey/v2 - Get data for Journey page (TREND)
- GET /sync-status - Get game sync status
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

# Create router for journey endpoints
router = APIRouter(tags=["Journey"])

# Database reference - will be set by server.py
db = None
# Sync status reference - will be set by server.py
_sync_status = None
QUICK_SYNC_INTERVAL_SECONDS = 300  # Default, will be updated by server.py

def set_db(database):
    """Set the database reference for journey routes"""
    global db
    db = database

def set_sync_status(sync_status_ref, interval_seconds):
    """Set the sync status reference and interval"""
    global _sync_status, QUICK_SYNC_INTERVAL_SECONDS
    _sync_status = sync_status_ref
    QUICK_SYNC_INTERVAL_SECONDS = interval_seconds

# Import User model and get_current_user from auth routes
from routes.auth import User, get_current_user

# Import journey services
from journey_service import (
    generate_journey_dashboard_data,
    fetch_recent_chesscom_games,
    fetch_recent_lichess_games
)
from chess_journey_service import get_chess_journey
from player_profile_service import get_or_create_profile


# ==================== MODELS ====================

class LinkAccountRequest(BaseModel):
    platform: str  # "chess.com" or "lichess"
    username: str


class UnlinkAccountRequest(BaseModel):
    platform: str  # "chess.com" or "lichess"


# ==================== ENDPOINTS ====================

@router.get("/journey")
async def get_journey_dashboard(user: User = Depends(get_current_user)):
    """
    Get Journey Dashboard data - proves learning over time.
    
    This is the primary surface where coaching results appear.
    No manual analysis required - games are analyzed automatically.
    """
    global db
    
    # Get player profile
    profile = await db.player_profiles.find_one(
        {"user_id": user.user_id},
        {"_id": 0}
    )
    
    if not profile:
        # Create profile if doesn't exist
        profile = await get_or_create_profile(db, user.user_id, user.name)
    
    # Generate dashboard data
    dashboard = await generate_journey_dashboard_data(db, user.user_id, profile)
    
    return dashboard


@router.get("/journey/comprehensive")
async def get_comprehensive_journey(user: User = Depends(get_current_user)):
    """
    Get comprehensive chess journey data.
    
    Returns:
    - Rating progression over time
    - Phase mastery (Opening, Middlegame, Endgame)
    - Improvement metrics (then vs now)
    - Habit journey (conquered, in progress, needs attention)
    - Opening repertoire with win rates
    - Weekly summary and insights
    """
    global db
    journey = await get_chess_journey(db, user.user_id)
    return journey


@router.get("/journey/weekly-assessment")
async def get_weekly_assessment(user: User = Depends(get_current_user)):
    """Get coach's weekly assessment paragraph"""
    global db
    from journey_service import generate_weekly_assessment
    
    profile = await db.player_profiles.find_one(
        {"user_id": user.user_id},
        {"_id": 0}
    )
    
    if not profile:
        return {
            "assessment": "Link your Chess.com or Lichess account to start your coaching journey.",
            "games_analyzed": 0
        }
    
    recent_analyses = await db.game_analyses.find(
        {"user_id": user.user_id},
        {"_id": 0, "_cqs_internal": 0}
    ).sort("created_at", -1).limit(5).to_list(5)
    
    improvement_trend = profile.get("improvement_trend", "stuck")
    
    return {
        "assessment": generate_weekly_assessment(profile, recent_analyses, improvement_trend),
        "games_analyzed": profile.get("games_analyzed_count", 0),
        "improvement_trend": improvement_trend
    }


@router.get("/journey/weakness-trends")
async def get_weakness_trends(user: User = Depends(get_current_user)):
    """Get weakness trend data - shows if habits are improving"""
    global db
    from journey_service import calculate_weakness_trend
    
    profile = await db.player_profiles.find_one(
        {"user_id": user.user_id},
        {"_id": 0}
    )
    
    if not profile:
        return {"trends": [], "message": "Not enough data yet"}
    
    # Get recent analyses
    recent_analyses = await db.game_analyses.find(
        {"user_id": user.user_id},
        {"_id": 0, "weaknesses": 1, "identified_weaknesses": 1}
    ).sort("created_at", -1).limit(10).to_list(10)
    
    top_weaknesses = profile.get("top_weaknesses", [])[:5]
    recent_5 = recent_analyses[:5]
    previous_5 = recent_analyses[5:10]
    
    trends = []
    for w in top_weaknesses:
        weakness_key = f"{w.get('category', '')}:{w.get('subcategory', '')}"
        trend_data = calculate_weakness_trend(weakness_key, recent_5, previous_5)
        
        trends.append({
            "name": w.get("subcategory", "").replace("_", " "),
            "category": w.get("category", ""),
            **trend_data
        })
    
    return {"trends": trends}


@router.post("/journey/link-account")
async def link_chess_account(req: LinkAccountRequest, user: User = Depends(get_current_user)):
    """
    Link Chess.com or Lichess account for automatic game tracking.
    Only ONE account per platform can be linked at a time.
    """
    global db
    
    platform = req.platform.lower()
    username = req.username.strip()
    
    if platform not in ["chess.com", "lichess"]:
        raise HTTPException(status_code=400, detail="Invalid platform. Use 'chess.com' or 'lichess'")
    
    if not username:
        raise HTTPException(status_code=400, detail="Username is required")
    
    # Check if user already has a linked account for this platform
    user_doc = await db.users.find_one({"user_id": user.user_id})
    if user_doc:
        existing_chesscom = user_doc.get("chess_com_username") or user_doc.get("chesscom_username")
        existing_lichess = user_doc.get("lichess_username")
        
        if platform == "chess.com" and existing_chesscom:
            if existing_chesscom.lower() != username.lower():
                raise HTTPException(
                    status_code=400, 
                    detail=f"You already have a linked Chess.com account ({existing_chesscom}). Please unlink it first before linking a new account."
                )
        elif platform == "lichess" and existing_lichess:
            if existing_lichess.lower() != username.lower():
                raise HTTPException(
                    status_code=400,
                    detail=f"You already have a linked Lichess account ({existing_lichess}). Please unlink it first before linking a new account."
                )
    
    # Validate account exists
    if platform == "chess.com":
        games = await fetch_recent_chesscom_games(username)
        if not games and games != []:
            raise HTTPException(status_code=404, detail=f"Chess.com user '{username}' not found")
        update_field = "chess_com_username"  # Standardized field name
    else:
        games = await fetch_recent_lichess_games(username)
        update_field = "lichess_username"
    
    # Update user record
    await db.users.update_one(
        {"user_id": user.user_id},
        {"$set": {
            update_field: username,
            "last_game_sync": None  # Trigger initial sync
        }}
    )
    
    return {
        "message": "Account linked successfully! We'll import your games from the last 3 months and auto-analyze up to 3 games per day.",
        "platform": platform,
        "username": username,
        "import_info": {
            "period": "Last 3 months",
            "auto_analysis_limit": "3 games per day",
            "sync_frequency": "Every 4 hours"
        }
    }


@router.get("/journey/linked-accounts")
async def get_linked_accounts(user: User = Depends(get_current_user)):
    """Get user's linked chess accounts"""
    global db
    
    user_doc = await db.users.find_one(
        {"user_id": user.user_id},
        {"_id": 0, "chess_com_username": 1, "chesscom_username": 1, "lichess_username": 1}
    )
    
    if not user_doc:
        return {"chess_com": None, "lichess": None}
    
    # Support both field names for backward compatibility
    chess_com = user_doc.get("chess_com_username") or user_doc.get("chesscom_username")
    
    return {
        "chess_com": chess_com,
        "lichess": user_doc.get("lichess_username")
    }


@router.post("/journey/unlink-account")
async def unlink_chess_account(req: UnlinkAccountRequest, user: User = Depends(get_current_user)):
    """
    Unlink a Chess.com or Lichess account.
    This does NOT delete imported games, but stops future syncing.
    """
    global db
    
    platform = req.platform.lower()
    
    if platform not in ["chess.com", "lichess"]:
        raise HTTPException(status_code=400, detail="Invalid platform. Use 'chess.com' or 'lichess'")
    
    if platform == "chess.com":
        # Remove both field variants for safety
        await db.users.update_one(
            {"user_id": user.user_id},
            {"$unset": {"chess_com_username": "", "chesscom_username": ""}}
        )
    else:
        await db.users.update_one(
            {"user_id": user.user_id},
            {"$unset": {"lichess_username": ""}}
        )
    
    return {
        "message": f"{platform} account unlinked successfully",
        "platform": platform
    }


@router.post("/journey/sync-now")
async def trigger_game_sync(background_tasks: BackgroundTasks, user: User = Depends(get_current_user)):
    """
    Manually trigger game sync for the current user.
    Runs the sync immediately in the background.
    """
    global db
    from journey_service import sync_user_games
    
    user_doc = await db.users.find_one(
        {"user_id": user.user_id},
        {"_id": 0}
    )
    
    if not user_doc:
        raise HTTPException(status_code=404, detail="User not found")
    
    has_linked = user_doc.get("chesscom_username") or user_doc.get("chess_com_username") or user_doc.get("lichess_username")
    if not has_linked:
        raise HTTPException(status_code=400, detail="No chess accounts linked. Link an account first.")
    
    # Run sync in background
    async def do_sync():
        try:
            count = await sync_user_games(db, user.user_id, user_doc)
            logger.info(f"Manual sync for user {user.user_id}: {count} games synced")
        except Exception as e:
            logger.error(f"Manual sync error for {user.user_id}: {e}")
    
    background_tasks.add_task(do_sync)
    
    return {"message": "Game sync started. New games will appear shortly."}


@router.get("/sync-status")
async def get_sync_status(user: User = Depends(get_current_user)):
    """
    Get the current game sync status including countdown to next sync.
    Used by frontend to display sync timer.
    """
    global _sync_status, QUICK_SYNC_INTERVAL_SECONDS
    
    now = datetime.now(timezone.utc)
    
    # Calculate seconds until next sync
    next_sync_in_seconds = 0
    if _sync_status and _sync_status.get("next_sync_at"):
        try:
            next_sync = datetime.fromisoformat(_sync_status["next_sync_at"].replace('Z', '+00:00'))
            diff = (next_sync - now).total_seconds()
            next_sync_in_seconds = max(0, int(diff))
        except:
            next_sync_in_seconds = QUICK_SYNC_INTERVAL_SECONDS
    
    return {
        "is_syncing": _sync_status.get("is_syncing", False) if _sync_status else False,
        "last_sync_at": _sync_status.get("last_sync_at") if _sync_status else None,
        "next_sync_in_seconds": next_sync_in_seconds,
        "sync_interval_seconds": QUICK_SYNC_INTERVAL_SECONDS,
        "games_found_last_sync": _sync_status.get("games_found_last_sync", 0) if _sync_status else 0
    }


@router.get("/journey/intelligence")
async def get_journey_intelligence(user: User = Depends(get_current_user)):
    """
    Get comprehensive journey intelligence for the user.
    
    Returns all 8 sections:
    1. Identity Snapshot
    2. Growth Delta
    3. Rating Ceiling Model
    4. Pattern Engine
    5. Phase Discipline
    6. Fundamentals Snapshot
    7. Opening Snapshot
    8. Momentum Trend
    
    All computed deterministically from game data - no LLM required.
    """
    global db
    from journey_intelligence_service import compute_journey_intelligence
    
    logger.info(f"Journey intelligence requested for user: {user.user_id}")
    return await compute_journey_intelligence(db, user.user_id)


@router.get("/journey/v2")
async def get_journey_page_data(user: User = Depends(get_current_user)):
    """
    Get data for the Journey page (TREND - How you're evolving)
    
    Returns:
    - Baseline vs Current progress tracking
    - Baseline patterns (weaknesses from first games)
    - Current patterns (weaknesses from recent games)
    - Pattern comparison (improvement/regression per weakness)
    - Weakness ranking (not equal badges)
    - Win-state analysis
    - Identity profile
    """
    global db
    from baseline_service import (
        get_or_create_baseline,
        get_baseline_patterns,
        calculate_current_stats,
        calculate_progress,
        calculate_pattern_snapshot,
        compare_patterns,
        MIN_GAMES_FOR_BASELINE
    )
    
    # Import calculate_all_badges and get_journey_data from server
    # These are defined in server.py and not extracted yet
    from server import calculate_all_badges, get_journey_data
    
    # Get ALL analyses for baseline calculation
    all_analyses = await db.game_analyses.find(
        {"user_id": user.user_id}
    ).sort("created_at", -1).to_list(200)
    
    # Get last 25 games for current stats
    analyses = all_analyses[:25] if len(all_analyses) > 25 else all_analyses
    
    # Get ALL games for baseline, last 25 for current
    all_games = await db.games.find(
        {"user_id": user.user_id}
    ).sort("imported_at", -1).to_list(200)
    
    games = all_games[:25] if len(all_games) > 25 else all_games
    
    # Get or create baseline profile
    baseline = await get_or_create_baseline(db, user.user_id, all_analyses, all_games)
    
    # Get baseline patterns (weaknesses from first games)
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
    current_stats = calculate_current_stats(analyses, games)
    
    # Calculate current patterns
    current_patterns = calculate_pattern_snapshot(analyses, games) if analyses else None
    
    # Calculate progress if baseline exists
    progress = None
    if baseline and current_stats:
        progress = calculate_progress(baseline, current_stats)
    
    # Calculate pattern comparison
    pattern_comparison = None
    if baseline_patterns and current_patterns:
        pattern_comparison = compare_patterns(baseline_patterns, current_patterns)
    
    # Get existing badge data
    badge_data = await calculate_all_badges(db, user.user_id)
    
    journey_data = get_journey_data(analyses, games, badge_data)
    
    # Add baseline and progress tracking
    journey_data['baseline'] = baseline
    journey_data['current_stats'] = current_stats
    journey_data['progress'] = progress
    journey_data['has_baseline'] = baseline is not None
    journey_data['games_until_baseline'] = max(0, MIN_GAMES_FOR_BASELINE - len(all_analyses)) if not baseline else 0
    
    # Add pattern data for Before/After tabs
    journey_data['baseline_patterns'] = baseline_patterns
    journey_data['current_patterns'] = current_patterns
    journey_data['pattern_comparison'] = pattern_comparison
    
    return journey_data


@router.get("/evolution/rolling")
async def get_rolling_evolution(user: User = Depends(get_current_user)):
    """
    Get rolling evolution data using equal window comparison.
    
    Compares recent 25 games vs previous 25 games.
    This is the PROPER way to track evolution - equal windows, continuous.
    
    Returns:
    - recent: Stats for last 25 games
    - previous: Stats for games 26-50
    - changes: What improved/declined between windows
    - overall: Overall direction (improving/declining/stable)
    """
    global db
    from baseline_service import calculate_rolling_evolution
    
    # Get all analyses
    all_analyses = await db.game_analyses.find(
        {"user_id": user.user_id}
    ).sort("created_at", -1).to_list(200)
    
    evolution = calculate_rolling_evolution(all_analyses)
    
    return evolution
