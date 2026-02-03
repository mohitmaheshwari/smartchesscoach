"""
Automatic Game Sync & Analysis Service

Handles:
1. Background polling for new games from Chess.com/Lichess
2. Smart game selection (prefer rapid/classical, skip bullet)
3. Silent auto-analysis (max 1-2 games/user/day)
4. Journey Dashboard data generation
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
import httpx

logger = logging.getLogger(__name__)

# Configuration
SYNC_INTERVAL_HOURS = 12  # Poll every 12 hours
MAX_GAMES_PER_DAY = 2     # Analyze max 2 games per user per day
MIN_GAME_MOVES = 10       # Skip games with fewer moves
PREFERRED_TIME_CONTROLS = ["rapid", "classical", "correspondence"]
SKIP_TIME_CONTROLS = ["bullet", "ultrabullet"]


async def fetch_recent_chesscom_games(username: str, since_timestamp: int = None) -> List[Dict]:
    """Fetch recent games from Chess.com API"""
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            # Get current month's games
            now = datetime.now(timezone.utc)
            url = f"https://api.chess.com/pub/player/{username}/games/{now.year}/{now.month:02d}"
            
            response = await client.get(url, headers={"User-Agent": "ChessCoachAI/1.0"})
            
            if response.status_code != 200:
                logger.warning(f"Chess.com API returned {response.status_code} for {username}")
                return []
            
            data = response.json()
            games = data.get("games", [])
            
            # Filter by timestamp if provided
            if since_timestamp:
                games = [g for g in games if g.get("end_time", 0) > since_timestamp]
            
            return games
            
    except Exception as e:
        logger.error(f"Error fetching Chess.com games for {username}: {e}")
        return []


async def fetch_recent_lichess_games(username: str, since_timestamp: int = None) -> List[Dict]:
    """Fetch recent games from Lichess API"""
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            params = {
                "max": 20,
                "pgnInJson": "true",
                "clocks": "false",
                "evals": "false"
            }
            
            if since_timestamp:
                params["since"] = since_timestamp * 1000  # Lichess uses milliseconds
            
            url = f"https://lichess.org/api/games/user/{username}"
            response = await client.get(
                url, 
                params=params,
                headers={
                    "Accept": "application/x-ndjson",
                    "User-Agent": "ChessCoachAI/1.0"
                }
            )
            
            if response.status_code != 200:
                logger.warning(f"Lichess API returned {response.status_code} for {username}")
                return []
            
            # Parse NDJSON
            games = []
            for line in response.text.strip().split("\n"):
                if line:
                    import json
                    games.append(json.loads(line))
            
            return games
            
    except Exception as e:
        logger.error(f"Error fetching Lichess games for {username}: {e}")
        return []


def should_analyze_game(game: Dict, platform: str) -> bool:
    """
    Determine if a game should be auto-analyzed.
    
    Criteria:
    - Prefer rapid/classical
    - Skip bullet/ultrabullet
    - Skip very short games (<10 moves)
    - Prefer rated games
    """
    if platform == "chess.com":
        time_class = game.get("time_class", "").lower()
        
        # Skip bullet
        if time_class in SKIP_TIME_CONTROLS:
            return False
        
        # Prefer rapid/classical
        if time_class in PREFERRED_TIME_CONTROLS:
            return True
        
        # Check move count (rough estimate from PGN)
        pgn = game.get("pgn", "")
        move_count = pgn.count(".")
        if move_count < MIN_GAME_MOVES:
            return False
        
        return True
        
    elif platform == "lichess":
        speed = game.get("speed", "").lower()
        
        # Skip bullet
        if speed in SKIP_TIME_CONTROLS:
            return False
        
        # Check move count
        moves = game.get("moves", "").split()
        if len(moves) < MIN_GAME_MOVES * 2:  # Each move is half-move
            return False
        
        # Prefer rated
        return game.get("rated", False)
    
    return False


def select_games_for_analysis(games: List[Dict], platform: str, max_games: int = MAX_GAMES_PER_DAY) -> List[Dict]:
    """
    Select the best games to analyze from a list.
    
    Priority:
    1. Rapid/Classical games
    2. Longer games
    3. More recent games
    """
    # Filter eligible games
    eligible = [g for g in games if should_analyze_game(g, platform)]
    
    if not eligible:
        return []
    
    # Sort by preference (most recent first for now)
    if platform == "chess.com":
        eligible.sort(key=lambda g: g.get("end_time", 0), reverse=True)
    elif platform == "lichess":
        eligible.sort(key=lambda g: g.get("lastMoveAt", 0), reverse=True)
    
    return eligible[:max_games]


# ==================== JOURNEY DASHBOARD DATA ====================

def calculate_weakness_trend(
    weakness_key: str,
    recent_games: List[Dict],  # Last 5 games
    previous_games: List[Dict]  # Previous 5 games (6-10)
) -> Dict[str, Any]:
    """
    Calculate trend for a specific weakness.
    
    Returns:
    {
        "occurrences_recent": 3,
        "occurrences_previous": 5,
        "trend": "improving" | "stable" | "worsening"
    }
    """
    recent_count = 0
    previous_count = 0
    
    for game in recent_games:
        weaknesses = game.get("weaknesses", [])
        for w in weaknesses:
            key = f"{w.get('category', '')}:{w.get('subcategory', '')}"
            if key == weakness_key:
                recent_count += 1
    
    for game in previous_games:
        weaknesses = game.get("weaknesses", [])
        for w in weaknesses:
            key = f"{w.get('category', '')}:{w.get('subcategory', '')}"
            if key == weakness_key:
                previous_count += 1
    
    # Determine trend
    if recent_count < previous_count:
        trend = "improving"
    elif recent_count > previous_count:
        trend = "worsening"
    else:
        trend = "stable"
    
    return {
        "occurrences_recent": recent_count,
        "occurrences_previous": previous_count,
        "trend": trend
    }


def generate_weekly_assessment(
    profile: Dict[str, Any],
    recent_analyses: List[Dict],
    improvement_trend: str
) -> str:
    """
    Generate the coach's weekly assessment paragraph.
    
    Rules:
    - 3-5 sentences max
    - Include: 1 improvement, 1 active habit, 1 focus
    - No chess notation
    - No engine language
    """
    games_count = profile.get("games_analyzed_count", 0)
    top_weaknesses = profile.get("top_weaknesses", [])
    strengths = profile.get("strengths", [])
    
    # Not enough data
    if games_count < 5:
        return "We're still getting to know your game. Play a few more games and I'll have more specific guidance for you."
    
    sentences = []
    
    # Improvement mention
    if improvement_trend == "improving":
        sentences.append("Your recent games show real progress.")
    elif strengths:
        strength = strengths[0]
        strength_name = strength.get("subcategory", "").replace("_", " ")
        sentences.append(f"Your {strength_name} continues to be solid.")
    else:
        sentences.append("Your game is developing steadily.")
    
    # Active habit mention
    if top_weaknesses:
        top_weakness = top_weaknesses[0]
        weakness_name = top_weakness.get("subcategory", "").replace("_", " ")
        score = top_weakness.get("decayed_score", 0)
        
        if score > 3:
            sentences.append(f"We're still working on {weakness_name} - it's showing up regularly.")
        else:
            sentences.append(f"The {weakness_name} pattern is appearing less often now.")
    
    # Focus for next games
    if len(top_weaknesses) > 0:
        focus_weakness = top_weaknesses[0]
        focus_name = focus_weakness.get("subcategory", "").replace("_", " ")
        sentences.append(f"Next focus: keep watching for {focus_name} tendencies.")
    else:
        sentences.append("Keep playing thoughtfully and the patterns will emerge.")
    
    return " ".join(sentences)


def get_current_focus_areas(profile: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Get the 2-3 most important habits to focus on.
    
    Returns list of:
    {
        "name": "pin blindness",
        "status": "improving" | "stable" | "needs_attention"
    }
    """
    top_weaknesses = profile.get("top_weaknesses", [])[:3]
    focus_areas = []
    
    for w in top_weaknesses:
        name = w.get("subcategory", "").replace("_", " ")
        score = w.get("decayed_score", 0)
        occurrence_count = w.get("occurrence_count", 0)
        
        # Determine status based on score decay
        if score < occurrence_count * 0.5:
            status = "improving"
        elif score > occurrence_count * 0.8:
            status = "needs_attention"
        else:
            status = "stable"
        
        focus_areas.append({
            "name": name,
            "category": w.get("category", ""),
            "status": status
        })
    
    return focus_areas


def get_resolved_habits(profile: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Get habits that are no longer major issues.
    
    Criteria:
    - Score dropped significantly
    - No occurrences in recent games
    - Was previously a top weakness
    """
    # This would need historical data to properly track
    # For now, we check challenge success rate
    
    resolved = []
    challenge_success = profile.get("weakness_challenge_success", {})
    
    for weakness_key, stats in challenge_success.items():
        attempts = stats.get("attempts", 0)
        successes = stats.get("successes", 0)
        
        if attempts >= 5 and successes / attempts > 0.7:
            # Extract name from key
            parts = weakness_key.split(":")
            name = parts[1] if len(parts) > 1 else weakness_key
            name = name.replace("_", " ")
            
            resolved.append({
                "name": name,
                "message": f"{name.title()} is no longer a major issue in your recent games."
            })
    
    return resolved[:3]  # Max 3


def get_reinforced_strengths(profile: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Get strengths that are being consistently demonstrated.
    """
    strengths = profile.get("strengths", [])[:3]
    
    return [
        {
            "name": s.get("subcategory", "").replace("_", " "),
            "category": s.get("category", ""),
            "evidence_count": s.get("evidence_count", 0)
        }
        for s in strengths
    ]


async def generate_journey_dashboard_data(
    db,
    user_id: str,
    profile: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Generate all data needed for the Journey Dashboard.
    """
    games_analyzed = profile.get("games_analyzed_count", 0)
    improvement_trend = profile.get("improvement_trend", "stuck")
    
    # Get recent analyses for trend calculation
    recent_analyses = await db.game_analyses.find(
        {"user_id": user_id},
        {"_id": 0, "_cqs_internal": 0}
    ).sort("created_at", -1).limit(10).to_list(10)
    
    # Calculate weakness trends
    weakness_trends = []
    top_weaknesses = profile.get("top_weaknesses", [])[:5]
    
    recent_5 = recent_analyses[:5]
    previous_5 = recent_analyses[5:10]
    
    for w in top_weaknesses:
        weakness_key = f"{w.get('category', '')}:{w.get('subcategory', '')}"
        trend_data = calculate_weakness_trend(weakness_key, recent_5, previous_5)
        
        weakness_trends.append({
            "name": w.get("subcategory", "").replace("_", " "),
            "category": w.get("category", ""),
            **trend_data
        })
    
    # Determine dashboard mode based on game count
    if games_analyzed < 5:
        mode = "onboarding"
    elif games_analyzed < 10:
        mode = "early"
    elif games_analyzed < 20:
        mode = "developing"
    else:
        mode = "established"
    
    return {
        "mode": mode,
        "games_analyzed": games_analyzed,
        "weekly_assessment": generate_weekly_assessment(profile, recent_analyses, improvement_trend),
        "focus_areas": get_current_focus_areas(profile),
        "weakness_trends": weakness_trends,
        "resolved_habits": get_resolved_habits(profile) if mode == "established" else [],
        "strengths": get_reinforced_strengths(profile),
        "improvement_trend": improvement_trend,
        "last_updated": datetime.now(timezone.utc).isoformat()
    }


# ==================== AUTO-ANALYSIS ====================

async def auto_analyze_game(db, user_id: str, game_doc: Dict) -> Optional[Dict]:
    """
    Automatically analyze a game with AI coaching.
    Returns the analysis document or None if analysis fails/skipped.
    """
    import os
    import json
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    from player_profile_service import get_or_create_profile, update_profile_after_analysis
    from rag_service import build_rag_context
    from cqs_service import evaluate_analysis_quality, get_stricter_prompt_constraints
    
    EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY", "")
    if not EMERGENT_LLM_KEY:
        logger.error("EMERGENT_LLM_KEY not configured - skipping auto-analysis")
        return None
    
    game_id = game_doc.get("game_id")
    pgn = game_doc.get("pgn", "")
    user_color = game_doc.get("user_color", "white")
    
    if not pgn or len(pgn) < 50:
        logger.warning(f"Game {game_id} has invalid PGN - skipping analysis")
        return None
    
    # Check if already analyzed
    existing = await db.game_analyses.find_one({"game_id": game_id})
    if existing:
        logger.info(f"Game {game_id} already analyzed - skipping")
        return None
    
    try:
        # Get user info
        user_doc = await db.users.find_one({"user_id": user_id}, {"_id": 0, "name": 1})
        user_name = user_doc.get("name", "Player") if user_doc else "Player"
        first_name = user_name.split()[0] if user_name else "friend"
        
        # Get profile
        profile = await get_or_create_profile(db, user_id, user_name)
        # Note: RAG context can be built here for future use if needed
        
        # Build memory context
        top_weaknesses = profile.get("top_weaknesses", [])[:3]
        games_analyzed = profile.get("games_analyzed_count", 0)
        
        memory_callouts = []
        for w in top_weaknesses:
            subcat = w.get("subcategory", "").replace("_", " ")
            count = w.get("occurrence_count", 0)
            if count >= 2:
                memory_callouts.append(f"- {subcat}: seen {count} times before")
        
        memory_section = ""
        if memory_callouts:
            memory_section = "COACH MEMORY:\n" + "\n".join(memory_callouts)
        
        # Simplified system prompt for auto-analysis
        system_prompt = f"""You are an experienced chess coach analyzing a game.

{first_name} played as {user_color}. Games analyzed: {games_analyzed}

{memory_section}

Respond with ONLY valid JSON:
{{
    "game_summary": "2-3 sentence summary",
    "blunders": <number>,
    "mistakes": <number>,
    "best_moves": <number>,
    "move_by_move": [
        {{
            "move_number": 1,
            "move": "e4",
            "evaluation": "good|solid|neutral|inaccuracy|mistake|blunder",
            "thinking_pattern": "What was the thinking here",
            "lesson": "Brief lesson if mistake",
            "consider": "What to consider instead"
        }}
    ],
    "identified_weaknesses": [
        {{"category": "tactical", "subcategory": "fork_blindness", "habit_description": "Description"}}
    ],
    "identified_strengths": [
        {{"category": "positional", "subcategory": "good_development", "description": "What they did well"}}
    ],
    "best_move_suggestions": [
        {{"move_number": 10, "best_move": "Nf3", "reason": "Why this was better"}}
    ],
    "focus_this_week": "One thing to work on",
    "voice_script": "30-second spoken summary"
}}

RULES:
- NO engine language (stockfish, centipawns, +0.5)
- Keep explanations SHORT
- Strengths must be POSITIVE (good_development, solid_defense) - NEVER list weaknesses as strengths
- For blunders, suggest the best_move
"""
        
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"auto_analysis_{game_id}",
            system_message=system_prompt
        ).with_model("openai", "gpt-5.2")
        
        user_message = UserMessage(text=f"Analyze this game:\n\n{pgn}")
        response = await chat.a_send_message(user_message)
        
        # Parse response
        response_text = response.text.strip()
        if response_text.startswith("```"):
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]
        
        analysis_data = json.loads(response_text)
        
        # Create analysis document
        analysis_doc = {
            "analysis_id": f"analysis_{game_id}",
            "game_id": game_id,
            "user_id": user_id,
            "game_summary": analysis_data.get("game_summary", ""),
            "blunders": analysis_data.get("blunders", 0),
            "mistakes": analysis_data.get("mistakes", 0),
            "best_moves": analysis_data.get("best_moves", 0),
            "move_by_move": analysis_data.get("move_by_move", []),
            "weaknesses": analysis_data.get("identified_weaknesses", []),
            "identified_weaknesses": analysis_data.get("identified_weaknesses", []),
            "strengths": analysis_data.get("identified_strengths", []),
            "best_move_suggestions": analysis_data.get("best_move_suggestions", []),
            "focus_this_week": analysis_data.get("focus_this_week", ""),
            "voice_script_summary": analysis_data.get("voice_script", ""),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "auto_analyzed": True
        }
        
        await db.game_analyses.insert_one(analysis_doc)
        
        # Mark game as analyzed
        await db.games.update_one(
            {"game_id": game_id},
            {"$set": {"is_analyzed": True}}
        )
        
        # Update player profile
        await update_profile_after_analysis(
            db,
            user_id,
            game_id,
            analysis_data.get("blunders", 0),
            analysis_data.get("mistakes", 0),
            analysis_data.get("best_moves", 0),
            analysis_data.get("identified_weaknesses", []),
            analysis_data.get("identified_strengths", [])
        )
        
        logger.info(f"Auto-analysis complete for game {game_id}")
        return analysis_doc
        
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse AI response for game {game_id}: {e}")
        return None
    except Exception as e:
        logger.error(f"Auto-analysis error for game {game_id}: {e}")
        return None


# ==================== BACKGROUND SYNC JOB ====================

def extract_pgn_from_chesscom_game(game: Dict, username: str) -> Optional[str]:
    """Extract PGN from Chess.com game data"""
    pgn = game.get("pgn", "")
    if not pgn:
        return None
    return pgn


def extract_pgn_from_lichess_game(game: Dict, username: str) -> Optional[str]:
    """Extract PGN from Lichess game data (with pgn field from API)"""
    pgn = game.get("pgn", "")
    if not pgn:
        # Build PGN from moves if pgn not directly available
        moves = game.get("moves", "")
        if not moves:
            return None
        
        # Build basic PGN
        headers = []
        if game.get("id"):
            headers.append(f'[Site "https://lichess.org/{game.get("id")}"]')
        if game.get("players"):
            white = game.get("players", {}).get("white", {}).get("user", {}).get("name", "?")
            black = game.get("players", {}).get("black", {}).get("user", {}).get("name", "?")
            headers.append(f'[White "{white}"]')
            headers.append(f'[Black "{black}"]')
        if game.get("opening"):
            headers.append(f'[Opening "{game.get("opening", {}).get("name", "")}"]')
        
        pgn = "\n".join(headers) + "\n\n" + moves
    
    return pgn


def determine_user_color(game: Dict, platform: str, username: str) -> str:
    """Determine which color the user played"""
    if platform == "chess.com":
        white_player = game.get("white", {}).get("username", "").lower()
        return "white" if white_player == username.lower() else "black"
    else:  # lichess
        white_player = game.get("players", {}).get("white", {}).get("user", {}).get("name", "").lower()
        return "white" if white_player == username.lower() else "black"


async def sync_user_games(db, user_id: str, user_doc: Dict) -> int:
    """
    Sync and auto-analyze games for a single user.
    Returns number of games analyzed.
    """
    import uuid
    
    chesscom_username = user_doc.get("chesscom_username")
    lichess_username = user_doc.get("lichess_username")
    
    # Get last sync timestamp
    last_sync = user_doc.get("last_game_sync")
    if last_sync:
        if isinstance(last_sync, str):
            last_sync = datetime.fromisoformat(last_sync.replace('Z', '+00:00'))
        since_timestamp = int(last_sync.timestamp())
    else:
        # First sync - get games from last 7 days
        since_timestamp = int((datetime.now(timezone.utc) - timedelta(days=7)).timestamp())
    
    games_to_analyze = []
    
    # Fetch from Chess.com
    if chesscom_username:
        chesscom_games = await fetch_recent_chesscom_games(chesscom_username, since_timestamp)
        selected = select_games_for_analysis(chesscom_games, "chess.com", 1)
        for g in selected:
            games_to_analyze.append({"game": g, "platform": "chess.com", "username": chesscom_username})
    
    # Fetch from Lichess
    if lichess_username:
        lichess_games = await fetch_recent_lichess_games(lichess_username, since_timestamp)
        selected = select_games_for_analysis(lichess_games, "lichess", 1)
        for g in selected:
            games_to_analyze.append({"game": g, "platform": "lichess", "username": lichess_username})
    
    # Limit total games per sync
    games_to_analyze = games_to_analyze[:MAX_GAMES_PER_DAY]
    
    analyzed_count = 0
    
    for item in games_to_analyze:
        try:
            game_data = item["game"]
            platform = item["platform"]
            username = item["username"]
            
            # Generate unique identifier based on game URL
            if platform == "chess.com":
                game_url = game_data.get("url", "")
                pgn = extract_pgn_from_chesscom_game(game_data, username)
            else:
                game_id = game_data.get("id", "")
                game_url = f"https://lichess.org/{game_id}"
                pgn = extract_pgn_from_lichess_game(game_data, username)
            
            if not pgn:
                logger.warning(f"No PGN found for game from {platform}")
                continue
            
            # Check if already imported by URL or PGN
            existing = await db.games.find_one({
                "$or": [
                    {"url": game_url, "user_id": user_id},
                    {"pgn": pgn, "user_id": user_id}
                ]
            })
            if existing:
                continue
            
            # Determine user's color
            user_color = determine_user_color(game_data, platform, username)
            
            # Create game record
            game_doc = {
                "game_id": str(uuid.uuid4()),
                "user_id": user_id,
                "platform": platform,
                "username": username,
                "pgn": pgn,
                "url": game_url,
                "user_color": user_color,
                "imported_at": datetime.now(timezone.utc).isoformat(),
                "auto_synced": True  # Mark as auto-synced
            }
            
            # Extract additional metadata
            if platform == "chess.com":
                game_doc["time_control"] = game_data.get("time_class", "")
                game_doc["result"] = game_data.get("pgn", "").split("[Result ")[1].split("]")[0].strip('"') if "[Result " in game_data.get("pgn", "") else ""
            else:
                game_doc["time_control"] = game_data.get("speed", "")
                game_doc["result"] = game_data.get("status", "")
            
            await db.games.insert_one(game_doc)
            logger.info(f"Auto-synced game {game_doc['game_id']} for user {user_id} from {platform}")
            
            # Auto-analyze the game with AI
            try:
                analysis_result = await auto_analyze_game(db, user_id, game_doc)
                if analysis_result:
                    logger.info(f"Auto-analyzed game {game_doc['game_id']} successfully")
                    analyzed_count += 1
                else:
                    logger.warning(f"Auto-analysis skipped for game {game_doc['game_id']}")
            except Exception as analysis_error:
                logger.error(f"Auto-analysis failed for game {game_doc['game_id']}: {analysis_error}")
                # Game is still imported even if analysis fails
            
        except Exception as e:
            logger.error(f"Error auto-syncing game for {user_id}: {e}")
    
    # Update last sync timestamp
    await db.users.update_one(
        {"user_id": user_id},
        {"$set": {"last_game_sync": datetime.now(timezone.utc).isoformat()}}
    )
    
    # Send email notification if games were synced and user has email notifications enabled
    if analyzed_count > 0:
        try:
            from email_service import send_game_analyzed_notification, is_email_configured
            
            if is_email_configured():
                # Check if user has email notifications enabled
                email_prefs = user_doc.get("email_notifications", {})
                if email_prefs.get("game_analyzed", True):  # Default to True
                    user_email = user_doc.get("email")
                    user_name = user_doc.get("name", "Chess Player")
                    platform_name = "Chess.com" if chesscom_username else "Lichess"
                    
                    await send_game_analyzed_notification(
                        user_email=user_email,
                        user_name=user_name,
                        games_count=analyzed_count,
                        platform=platform_name,
                        key_insights=[]  # Can be populated with actual insights later
                    )
        except Exception as e:
            logger.warning(f"Failed to send email notification: {e}")
    
    return analyzed_count


async def run_background_sync(db):
    """
    Background job to sync games for all users with linked accounts.
    Should be called periodically (every 6-12 hours).
    """
    # Find users with linked accounts
    users = await db.users.find({
        "$or": [
            {"chesscom_username": {"$exists": True, "$ne": None}},
            {"lichess_username": {"$exists": True, "$ne": None}}
        ]
    }).to_list(1000)
    
    total_analyzed = 0
    
    for user_doc in users:
        try:
            count = await sync_user_games(db, user_doc["user_id"], user_doc)
            total_analyzed += count
        except Exception as e:
            logger.error(f"Error syncing games for user {user_doc['user_id']}: {e}")
    
    logger.info(f"Background sync complete: {total_analyzed} games analyzed for {len(users)} users")
    return total_analyzed
