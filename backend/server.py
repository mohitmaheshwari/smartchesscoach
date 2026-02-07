from fastapi import FastAPI, APIRouter, HTTPException, Request, Response, Depends, BackgroundTasks
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timezone, timedelta
import httpx
import re
import io

# Import RAG service
from rag_service import (
    build_rag_context,
    create_game_embeddings,
    create_pattern_embedding,
    create_analysis_embedding,
    process_user_games_for_rag
)

# Import Player Profile service
from player_profile_service import (
    get_or_create_profile,
    update_profile_after_analysis,
    record_challenge_result,
    build_profile_context_for_prompt,
    build_explanation_prompt_contract,
    validate_explanation,
    categorize_weakness,
    normalize_weakness_key,
    WEAKNESS_CATEGORIES,
    LearningStyle,
    CoachingTone
)

# Import Coach Quality Score system (internal only)
from cqs_service import (
    calculate_cqs,
    get_stricter_prompt_constraints,
    should_accept_after_regenerations,
    log_cqs_result,
    MAX_REGENERATIONS
)

# Import Journey Dashboard service
from journey_service import (
    generate_journey_dashboard_data,
    run_background_sync,
    fetch_recent_chesscom_games,
    fetch_recent_lichess_games,
    select_games_for_analysis
)

# Import Rating & Training service
from rating_service import (
    predict_rating_trajectory,
    calculate_improvement_velocity,
    calculate_performance_rating,
    analyze_time_usage,
    generate_training_session,
    generate_calculation_analysis,
    fetch_platform_ratings
)

# Import Stockfish engine service
from stockfish_service import (
    analyze_game_with_stockfish,
    get_position_evaluation,
    get_best_moves_for_position
)

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# LLM Key
EMERGENT_LLM_KEY = os.environ.get('EMERGENT_LLM_KEY', '')

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ==================== MODELS ====================

class User(BaseModel):
    model_config = ConfigDict(extra="ignore")
    user_id: str
    email: str
    name: str
    picture: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    chess_com_username: Optional[str] = None
    lichess_username: Optional[str] = None

class UserSession(BaseModel):
    model_config = ConfigDict(extra="ignore")
    user_id: str
    session_token: str
    expires_at: datetime
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class Game(BaseModel):
    model_config = ConfigDict(extra="ignore")
    game_id: str = Field(default_factory=lambda: f"game_{uuid.uuid4().hex[:12]}")
    user_id: str
    platform: str  # "chess.com" or "lichess"
    pgn: str
    white_player: str
    black_player: str
    result: str
    time_control: Optional[str] = None
    date_played: Optional[str] = None
    opening: Optional[str] = None
    user_color: str  # "white" or "black"
    imported_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    is_analyzed: bool = False

class GameCreate(BaseModel):
    platform: str
    pgn: str
    white_player: str
    black_player: str
    result: str
    time_control: Optional[str] = None
    date_played: Optional[str] = None
    opening: Optional[str] = None
    user_color: str

class MistakePattern(BaseModel):
    model_config = ConfigDict(extra="ignore")
    pattern_id: str = Field(default_factory=lambda: f"pattern_{uuid.uuid4().hex[:12]}")
    user_id: str
    category: str  # "tactical", "positional", "endgame", "opening", "time_management"
    subcategory: str  # "pinning", "center_control", "one_move_blunder", etc.
    description: str
    occurrences: int = 1
    game_ids: List[str] = []
    first_seen: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_seen: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class GameAnalysis(BaseModel):
    model_config = ConfigDict(extra="ignore")
    analysis_id: str = Field(default_factory=lambda: f"analysis_{uuid.uuid4().hex[:12]}")
    game_id: str
    user_id: str
    commentary: List[Dict[str, Any]] = []  # [{move_number, move, comment, evaluation}]
    blunders: int = 0
    mistakes: int = 0
    inaccuracies: int = 0
    best_moves: int = 0
    overall_summary: str = ""
    identified_patterns: List[str] = []  # pattern_ids
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class ImportGamesRequest(BaseModel):
    platform: str
    username: str

class AnalyzeGameRequest(BaseModel):
    game_id: str
    force: bool = False  # Force re-analysis even if already analyzed

class ConnectPlatformRequest(BaseModel):
    platform: str
    username: str

# ==================== AUTH HELPERS ====================

async def get_current_user(request: Request) -> User:
    """Get current user from session token in cookie or Authorization header"""
    session_token = request.cookies.get("session_token")
    
    if not session_token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            session_token = auth_header.split(" ")[1]
    
    if not session_token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    session_doc = await db.user_sessions.find_one(
        {"session_token": session_token},
        {"_id": 0}
    )
    
    if not session_doc:
        raise HTTPException(status_code=401, detail="Invalid session")
    
    expires_at = session_doc["expires_at"]
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Session expired")
    
    user_doc = await db.users.find_one(
        {"user_id": session_doc["user_id"]},
        {"_id": 0}
    )
    
    if not user_doc:
        raise HTTPException(status_code=401, detail="User not found")
    
    return User(**user_doc)

# ==================== AUTH ROUTES ====================

@api_router.post("/auth/session")
async def create_session(request: Request, response: Response):
    """Exchange session_id for session_token"""
    body = await request.json()
    session_id = body.get("session_id")
    
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id required")
    
    async with httpx.AsyncClient() as client_http:
        resp = await client_http.get(
            "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data",
            headers={"X-Session-ID": session_id}
        )
        
        if resp.status_code != 200:
            raise HTTPException(status_code=401, detail="Invalid session_id")
        
        data = resp.json()
    
    user_id = f"user_{uuid.uuid4().hex[:12]}"
    session_token = data.get("session_token", f"session_{uuid.uuid4().hex}")
    
    existing_user = await db.users.find_one({"email": data["email"]}, {"_id": 0})
    
    if existing_user:
        user_id = existing_user["user_id"]
        await db.users.update_one(
            {"user_id": user_id},
            {"$set": {
                "name": data["name"],
                "picture": data.get("picture")
            }}
        )
    else:
        user_doc = {
            "user_id": user_id,
            "email": data["email"],
            "name": data["name"],
            "picture": data.get("picture"),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "chess_com_username": None,
            "lichess_username": None
        }
        await db.users.insert_one(user_doc)
    
    await db.user_sessions.delete_many({"user_id": user_id})
    
    session_doc = {
        "user_id": user_id,
        "session_token": session_token,
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.user_sessions.insert_one(session_doc)
    
    response.set_cookie(
        key="session_token",
        value=session_token,
        httponly=True,
        secure=True,
        samesite="none",
        path="/",
        max_age=7 * 24 * 60 * 60
    )
    
    user_doc = await db.users.find_one({"user_id": user_id}, {"_id": 0})
    return user_doc

@api_router.get("/auth/me")
async def get_me(user: User = Depends(get_current_user)):
    """Get current user profile"""
    return user.model_dump()

@api_router.post("/auth/logout")
async def logout(request: Request, response: Response):
    """Logout and clear session"""
    session_token = request.cookies.get("session_token")
    if session_token:
        await db.user_sessions.delete_many({"session_token": session_token})
    
    response.delete_cookie(key="session_token", path="/")
    return {"message": "Logged out successfully"}

class MobileAuthRequest(BaseModel):
    """Request for mobile Google authentication"""
    access_token: str

@api_router.post("/auth/google/mobile")
async def mobile_google_auth(request: MobileAuthRequest):
    """
    Authenticate mobile users with Google access token.
    Fetches user info from Google and creates/updates user.
    """
    # Validate access token is not empty
    if not request.access_token or not request.access_token.strip():
        raise HTTPException(status_code=401, detail="Access token is required")
    
    try:
        # Verify and get user info from Google
        async with httpx.AsyncClient() as client_http:
            resp = await client_http.get(
                "https://www.googleapis.com/oauth2/v2/userinfo",
                headers={"Authorization": f"Bearer {request.access_token}"}
            )
            
            if resp.status_code != 200:
                raise HTTPException(status_code=401, detail="Invalid Google access token")
            
            google_data = resp.json()
        
        email = google_data.get("email")
        name = google_data.get("name", email.split("@")[0])
        picture = google_data.get("picture")
        
        if not email:
            raise HTTPException(status_code=400, detail="Email not provided by Google")
        
        # Create or update user
        user_id = f"user_{uuid.uuid4().hex[:12]}"
        session_token = f"mobile_session_{uuid.uuid4().hex}"
        
        existing_user = await db.users.find_one({"email": email}, {"_id": 0})
        
        if existing_user:
            user_id = existing_user["user_id"]
            await db.users.update_one(
                {"user_id": user_id},
                {"$set": {
                    "name": name,
                    "picture": picture,
                    "last_login": datetime.now(timezone.utc).isoformat()
                }}
            )
        else:
            user_doc = {
                "user_id": user_id,
                "email": email,
                "name": name,
                "picture": picture,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "chess_com_username": None,
                "lichess_username": None
            }
            await db.users.insert_one(user_doc)
        
        # Create session
        await db.user_sessions.delete_many({"user_id": user_id})
        
        session_doc = {
            "user_id": user_id,
            "session_token": session_token,
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "is_mobile": True
        }
        await db.user_sessions.insert_one(session_doc)
        
        user_doc = await db.users.find_one({"user_id": user_id}, {"_id": 0})
        
        return {
            "user": user_doc,
            "session_token": session_token
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Mobile auth error: {e}")
        raise HTTPException(status_code=500, detail="Authentication failed")

class DemoLoginRequest(BaseModel):
    """Request for demo login (testing only)"""
    email: str

@api_router.post("/auth/demo-login")
async def demo_login(request: DemoLoginRequest):
    """
    Demo login for testing the mobile app without Google OAuth.
    Creates or logs in a user with the provided email.
    """
    email = request.email.strip().lower()
    
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="Valid email required")
    
    # Create user ID from email
    user_id = f"demo_{email.replace('@', '_').replace('.', '_')}"
    session_token = f"demo_session_{uuid.uuid4().hex}"
    name = email.split("@")[0].title()
    
    # Check if user exists
    existing_user = await db.users.find_one({"email": email}, {"_id": 0})
    
    if existing_user:
        user_id = existing_user["user_id"]
        await db.users.update_one(
            {"user_id": user_id},
            {"$set": {"last_login": datetime.now(timezone.utc).isoformat()}}
        )
    else:
        user_doc = {
            "user_id": user_id,
            "email": email,
            "name": name,
            "picture": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "chess_com_username": None,
            "lichess_username": None,
            "is_demo": True
        }
        await db.users.insert_one(user_doc)
    
    # Create session
    await db.user_sessions.delete_many({"user_id": user_id})
    
    session_doc = {
        "user_id": user_id,
        "session_token": session_token,
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "is_demo": True
    }
    await db.user_sessions.insert_one(session_doc)
    
    user_doc = await db.users.find_one({"user_id": user_id}, {"_id": 0})
    
    logger.info(f"Demo login: {email}")
    
    return {
        "user": user_doc,
        "session_token": session_token
    }

# ==================== PLATFORM CONNECTION ROUTES ====================

@api_router.post("/connect-platform")
async def connect_platform(req: ConnectPlatformRequest, user: User = Depends(get_current_user)):
    """Connect Chess.com or Lichess username to user profile"""
    platform = req.platform.lower()
    username = req.username.strip()
    
    if platform == "chess.com":
        async with httpx.AsyncClient() as client_http:
            resp = await client_http.get(f"https://api.chess.com/pub/player/{username}")
            if resp.status_code != 200:
                raise HTTPException(status_code=400, detail="Chess.com username not found")
        
        await db.users.update_one(
            {"user_id": user.user_id},
            {"$set": {"chess_com_username": username}}
        )
    elif platform == "lichess":
        async with httpx.AsyncClient() as client_http:
            resp = await client_http.get(f"https://lichess.org/api/user/{username}")
            if resp.status_code != 200:
                raise HTTPException(status_code=400, detail="Lichess username not found")
        
        await db.users.update_one(
            {"user_id": user.user_id},
            {"$set": {"lichess_username": username}}
        )
    else:
        raise HTTPException(status_code=400, detail="Invalid platform")
    
    return {"message": f"Connected {platform} account: {username}"}

# ==================== GAME IMPORT ROUTES ====================

def parse_pgn_games(pgn_text: str, platform: str, user_username: str) -> List[Dict]:
    """Parse PGN text and extract games"""
    games = []
    current_game = {}
    moves = []
    in_moves = False
    
    for line in pgn_text.split('\n'):
        line = line.strip()
        if not line:
            if current_game and moves:
                current_game['pgn_moves'] = ' '.join(moves)
                games.append(current_game)
                current_game = {}
                moves = []
                in_moves = False
            continue
        
        if line.startswith('['):
            match = re.match(r'\[(\w+)\s+"(.*)"\]', line)
            if match:
                key, value = match.groups()
                current_game[key.lower()] = value
                in_moves = False
        else:
            in_moves = True
            moves.append(line)
    
    if current_game and moves:
        current_game['pgn_moves'] = ' '.join(moves)
        games.append(current_game)
    
    parsed_games = []
    for g in games:
        white = g.get('white', 'Unknown')
        black = g.get('black', 'Unknown')
        user_color = 'white' if white.lower() == user_username.lower() else 'black'
        
        full_pgn = ""
        for key, value in g.items():
            if key != 'pgn_moves':
                full_pgn += f'[{key.capitalize()} "{value}"]\n'
        full_pgn += f'\n{g.get("pgn_moves", "")}'
        
        parsed_games.append({
            'platform': platform,
            'pgn': full_pgn,
            'white_player': white,
            'black_player': black,
            'result': g.get('result', '*'),
            'time_control': g.get('timecontrol', g.get('event', '')),
            'date_played': g.get('date', g.get('utcdate', '')),
            'opening': g.get('opening', g.get('eco', '')),
            'user_color': user_color
        })
    
    return parsed_games

@api_router.post("/import-games")
async def import_games(req: ImportGamesRequest, user: User = Depends(get_current_user)):
    """Import games from Chess.com or Lichess"""
    platform = req.platform.lower()
    username = req.username.strip()
    
    games_to_import = []
    
    if platform == "chess.com":
        async with httpx.AsyncClient(timeout=30.0) as client_http:
            archives_resp = await client_http.get(
                f"https://api.chess.com/pub/player/{username}/games/archives"
            )
            if archives_resp.status_code != 200:
                raise HTTPException(status_code=400, detail="Could not fetch Chess.com archives")
            
            archives = archives_resp.json().get("archives", [])
            recent_archives = archives[-3:] if len(archives) > 3 else archives
            
            for archive_url in recent_archives:
                try:
                    pgn_url = archive_url + "/pgn"
                    pgn_resp = await client_http.get(pgn_url)
                    if pgn_resp.status_code == 200:
                        parsed = parse_pgn_games(pgn_resp.text, "chess.com", username)
                        games_to_import.extend(parsed[:20])
                except Exception as e:
                    logger.error(f"Error fetching archive: {e}")
                    continue
    
    elif platform == "lichess":
        async with httpx.AsyncClient(timeout=30.0) as client_http:
            resp = await client_http.get(
                f"https://lichess.org/api/games/user/{username}",
                params={"max": 30, "pgnInJson": False},
                headers={"Accept": "application/x-chess-pgn"}
            )
            if resp.status_code != 200:
                raise HTTPException(status_code=400, detail="Could not fetch Lichess games")
            
            parsed = parse_pgn_games(resp.text, "lichess", username)
            games_to_import.extend(parsed)
    
    else:
        raise HTTPException(status_code=400, detail="Invalid platform")
    
    imported_count = 0
    for game_data in games_to_import[:30]:
        existing = await db.games.find_one({
            "user_id": user.user_id,
            "pgn": game_data['pgn']
        })
        if existing:
            continue
        
        game = Game(
            user_id=user.user_id,
            **game_data
        )
        doc = game.model_dump()
        doc['imported_at'] = doc['imported_at'].isoformat()
        await db.games.insert_one(doc)
        imported_count += 1
    
    # GAMIFICATION: Award XP for importing games
    if imported_count > 0:
        try:
            for _ in range(imported_count):
                await add_xp(user.user_id, "game_imported")
                await increment_stat(user.user_id, "games_imported")
            
            # First game achievement
            if imported_count >= 1:
                await check_and_award_achievements(user.user_id, "games_imported", imported_count)
            
            await update_streak(user.user_id)
        except Exception as gam_err:
            logger.warning(f"Gamification update error (non-critical): {gam_err}")
    
    return {"imported": imported_count, "total_found": len(games_to_import)}

@api_router.get("/games")
async def get_games(user: User = Depends(get_current_user)):
    """Get all games for the current user"""
    games = await db.games.find(
        {"user_id": user.user_id},
        {"_id": 0}
    ).sort("imported_at", -1).to_list(100)
    return games

@api_router.get("/games/{game_id}")
async def get_game(game_id: str, user: User = Depends(get_current_user)):
    """Get a specific game with player names and termination reason"""
    import re
    
    game = await db.games.find_one(
        {"game_id": game_id, "user_id": user.user_id},
        {"_id": 0}
    )
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    
    # Extract player names from PGN if not already present
    pgn = game.get("pgn", "")
    if pgn:
        white_match = re.search(r'\[White "([^"]+)"\]', pgn)
        black_match = re.search(r'\[Black "([^"]+)"\]', pgn)
        game["white_player"] = white_match.group(1) if white_match else "White"
        game["black_player"] = black_match.group(1) if black_match else "Black"
        
        # Also try to extract termination from PGN if not stored
        if not game.get("termination"):
            term_match = re.search(r'\[Termination "([^"]+)"\]', pgn)
            if term_match:
                game["termination"] = term_match.group(1).lower()
    else:
        game["white_player"] = "White"
        game["black_player"] = "Black"
    
    # Generate human-readable termination text
    termination = game.get("termination", "")
    user_color = game.get("user_color", "white")
    result = game.get("result", "")
    
    # Determine if user won or lost
    if user_color == "white":
        user_won = result == "1-0"
    else:
        user_won = result == "0-1"
    
    termination_text = ""
    if termination == "timeout":
        termination_text = "You lost on time" if not user_won else "Opponent lost on time"
    elif termination == "resigned":
        termination_text = "You resigned" if not user_won else "Opponent resigned"
    elif termination == "checkmated":
        termination_text = "You got checkmated" if not user_won else "You checkmated opponent"
    elif termination == "won":
        termination_text = "You won" if user_won else "You lost"
    elif termination == "stalemate":
        termination_text = "Draw by stalemate"
    elif termination == "repetition":
        termination_text = "Draw by repetition"
    elif termination == "insufficient_material":
        termination_text = "Draw - insufficient material"
    elif termination == "draw_agreed":
        termination_text = "Draw by agreement"
    
    game["termination_text"] = termination_text
    
    return game

# ==================== AI ANALYSIS ROUTES ====================

async def get_user_mistake_context(user_id: str) -> str:
    """Get user's mistake history for AI context"""
    patterns = await db.mistake_patterns.find(
        {"user_id": user_id},
        {"_id": 0}
    ).sort("occurrences", -1).to_list(10)
    
    if not patterns:
        return "This is a new player with no previous mistake history."
    
    context_parts = ["Here are the player's recurring mistakes:"]
    for p in patterns:
        days_ago = (datetime.now(timezone.utc) - datetime.fromisoformat(p['last_seen'].replace('Z', '+00:00') if isinstance(p['last_seen'], str) else p['last_seen'].isoformat())).days if isinstance(p.get('last_seen'), (str, datetime)) else 0
        context_parts.append(
            f"- {p['subcategory']} ({p['category']}): seen {p['occurrences']} times, "
            f"last occurrence {days_ago} days ago. {p['description']}"
        )
    
    return "\n".join(context_parts)

@api_router.post("/analyze-game")
async def analyze_game(req: AnalyzeGameRequest, background_tasks: BackgroundTasks, user: User = Depends(get_current_user)):
    """Analyze a game with Stockfish engine + AI coaching using PlayerProfile + RAG"""
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    import json
    
    game = await db.games.find_one(
        {"game_id": req.game_id, "user_id": user.user_id},
        {"_id": 0}
    )
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    
    existing_analysis = await db.game_analyses.find_one(
        {"game_id": req.game_id},
        {"_id": 0}
    )
    
    # If force re-analysis, delete old analysis first
    if existing_analysis and req.force:
        await db.game_analyses.delete_one({"game_id": req.game_id})
        existing_analysis = None
        logger.info(f"Force re-analysis requested for game {req.game_id}")
    
    if existing_analysis:
        return existing_analysis
    
    # ============ STEP 0: STOCKFISH ENGINE ANALYSIS (ACCURATE MOVE EVALUATION) ============
    logger.info(f"Running Stockfish analysis for game {req.game_id}")
    user_color = game.get('user_color', 'white')
    
    try:
        stockfish_result = analyze_game_with_stockfish(
            game['pgn'], 
            user_color=user_color,
            depth=18  # Good balance of speed and accuracy
        )
        
        if not stockfish_result.get("success"):
            logger.error(f"Stockfish analysis failed: {stockfish_result.get('error')}")
            stockfish_result = None
    except Exception as e:
        logger.error(f"Stockfish analysis error: {e}")
        stockfish_result = None
    
    # Extract Stockfish evaluations for GPT context
    stockfish_context = ""
    stockfish_move_data = []
    if stockfish_result and stockfish_result.get("success"):
        user_stats = stockfish_result.get("user_stats", {})
        moves = stockfish_result.get("moves", [])
        
        # Build context for GPT
        stockfish_context = f"""
=== STOCKFISH ENGINE ANALYSIS (DEPTH 18) ===
Player: {user_color}
Accuracy: {user_stats.get('accuracy', 0)}%
Blunders: {user_stats.get('blunders', 0)}
Mistakes: {user_stats.get('mistakes', 0)}  
Inaccuracies: {user_stats.get('inaccuracies', 0)}
Best Moves: {user_stats.get('best_moves', 0)}
Excellent Moves: {user_stats.get('excellent_moves', 0)}
Average CP Loss: {user_stats.get('avg_cp_loss', 0)}

=== MOVE-BY-MOVE ENGINE EVALUATION ===
"""
        # Include significant moves (blunders, mistakes, inaccuracies)
        significant_moves = [m for m in moves if m.get('evaluation') in ['blunder', 'mistake', 'inaccuracy']]
        for m in significant_moves[:10]:  # Limit to top 10 bad moves
            eval_type = m.get('evaluation', 'unknown')
            # Handle both string and enum types
            if hasattr(eval_type, 'value'):
                eval_type = eval_type.value
            stockfish_context += f"""
Move {m.get('move_number')}: {m.get('move')} ({eval_type.upper()})
- CP Loss: {m.get('cp_loss', 0)} centipawns
- Best was: {m.get('best_move')}
- Eval before: {m.get('eval_before', 0)/100:.1f} → after: {m.get('eval_after', 0)/100:.1f}
"""
        stockfish_move_data = moves
        logger.info(f"Stockfish: {user_stats.get('blunders', 0)} blunders, {user_stats.get('mistakes', 0)} mistakes, {user_stats.get('accuracy', 0)}% accuracy")
    
    # Step 1: Get or create PlayerProfile (FIRST-CLASS requirement)
    logger.info(f"Loading PlayerProfile for user {user.user_id}")
    profile = await get_or_create_profile(db, user.user_id, user.name)
    
    # Step 2: Build RAG context (SUPPORTS memory, doesn't define habits)
    logger.info(f"Building RAG context for game {req.game_id}")
    rag_context = await build_rag_context(db, user.user_id, game)
    
    # Step 3: Get user's first name
    first_name = user.name.split()[0] if user.name else "friend"
    
    # Step 4: Build explicit memory context for coach
    top_weaknesses = profile.get("top_weaknesses", [])[:3]
    improvement_trend = profile.get("improvement_trend", "stuck")
    games_analyzed = profile.get("games_analyzed_count", 0)
    
    # Build memory call-out strings
    memory_callouts = []
    for w in top_weaknesses:
        subcat = w.get("subcategory", "").replace("_", " ")
        count = w.get("occurrence_count", 0)
        if count >= 3:
            memory_callouts.append(f"- {subcat}: seen {count} times before")
        elif count >= 2:
            memory_callouts.append(f"- {subcat}: this happened before")
    
    memory_section = ""
    if memory_callouts:
        memory_section = "COACH MEMORY (reference these when relevant):\n" + "\n".join(memory_callouts)
    
    # Build improvement awareness
    improvement_note = ""
    if improvement_trend == "improving":
        improvement_note = "STATUS: Student is IMPROVING. Acknowledge progress."
    elif improvement_trend == "regressing":
        improvement_note = "STATUS: Student needs support. Be encouraging, focus on basics."
    else:
        improvement_note = "STATUS: Student is steady. Gentle push to improve."
    
    system_prompt = f"""You are an experienced chess coach with a warm, calm teaching style.

Your approach:
- Patient, principle-driven, supportive
- Focus on thinking habits, not moves
- Simple English, short sentences
- Sound like a mentor, not a commentator
- Use Indian warmth sparingly (max once in summary, e.g., "Well done" not "Beta" repeatedly)

IMPORTANT: I have already analyzed this game with Stockfish (world's best chess engine).
The engine data below is ACCURATE - trust it completely for move evaluations.
Your job is to provide COACHING INSIGHT on WHY these mistakes happen and HOW to fix them.

{stockfish_context}

{first_name} played as {game['user_color']} in this game.
Games analyzed together: {games_analyzed}

{memory_section}

{improvement_note}

=== COACHING RULES ===

1. MEMORY REFERENCE (builds trust)
   - If current mistake matches a known weakness, mention it briefly
   - Example: "We've seen this pattern before."
   - Keep it to 1 sentence, non-judgmental

2. HABIT-FIRST EXPLANATIONS  
   - Explain "what thinking habit caused this" not "what move was wrong"
   - One thinking error per mistake
   - Advice must apply to future games

3. COACH TONE
   - Warm but professional
   - Use Indian warmth sparingly (max once in summary)
   - Avoid: "Great job!", "Amazing!", "Brilliant!"
   - Prefer: "Good", "Solid", "Well played", "This needs work"

4. CRITICAL: CONSISTENCY RULE
   - If move is "good" or "solid" → NO negative thinking_pattern
   - If move is "good" or "solid" → thinking_pattern must be "solid_thinking" or null
   - Negative patterns ONLY for mistakes/blunders/inaccuracies

5. CONCEPTUAL GUIDANCE (no engine moves)
   - ❌ "Better: Play d5 earlier"
   - ✅ "Consider: Challenge the center with a pawn break"
   - ✅ "Think about: Developing before attacking"
   - Keep suggestions conceptual, applicable to any game

=== OUTPUT FORMAT (STRICT JSON) ===
{{
    "commentary": [
        {{
            "move_number": 5,
            "move": "h6",
            "evaluation": "inaccuracy",
            "intent": "What you were thinking (1 short sentence)",
            "feedback": "Coach feedback (1-2 sentences max)",
            "consider": "Conceptual suggestion, not a specific move (null if move was good)",
            "memory_note": "Brief memory reference if this matches past weakness (null otherwise)",
            "details": {{
                "thinking_pattern": "ONLY for mistakes: rushing, tunnel_vision, hope_chess, etc. For good moves: solid_thinking or null",
                "habit_note": "Why this thinking happens (null for good moves)",
                "rule": "A principle for future games"
            }}
        }}
    ],
    "blunders": 0,
    "mistakes": 0, 
    "inaccuracies": 0,
    "best_moves": 0,
    "summary_p1": "2 sentences: Overall game assessment - what went well, where discipline showed.",
    "summary_p2": "2 sentences: The one habit to focus on + instruction for next game.",
    "improvement_note": "One sentence about progress trend (null if no data)",
    "identified_weaknesses": [
        {{
            "category": "tactical",
            "subcategory": "pin_blindness",
            "habit_description": "What thinking pattern caused this",
            "practice_tip": "What to practice"
        }}
    ],
    "identified_strengths": [
        {{
            "category": "tactical", 
            "subcategory": "good_development",
            "description": "What they did well"
        }}
    ],
    "best_move_suggestions": [
        {{
            "move_number": 15,
            "best_move": "Nf3",
            "reason": "Controls the center and prepares castling"
        }}
    ],
    "focus_this_week": "The ONE habit to work on",
    "voice_script": "30-second calm spoken summary"
}}

=== STRICT RULES ===
1. NO engine language: no "stockfish", no centipawns, no "+0.5"
2. NO flashy commentary: no "Amazing!", "Brilliant!", "What a blunder!"
3. ONE lesson per mistake only
4. "Good/solid" moves NEVER get negative thinking_pattern
5. "consider" field must be CONCEPTUAL, not "play Nf3"
6. Keep everything SHORT - coaches don't over-explain
7. Memory references are factual, never shaming
8. STRENGTHS must be POSITIVE patterns only (e.g., "good_development", "solid_defense", "active_pieces")
   NEVER list weaknesses as strengths. If no clear strength, leave empty array.
9. For key blunders/mistakes, suggest the best_move that would have been better

Evaluations: "blunder", "mistake", "inaccuracy", "good", "solid", "neutral"
"""

    try:
        # CQS: Track regeneration attempts
        cqs_scores = []
        best_analysis_data = None
        best_cqs_result = None
        has_memory = len(memory_callouts) > 0
        
        for attempt in range(MAX_REGENERATIONS + 1):
            # Build prompt with stricter constraints on regeneration
            current_prompt = system_prompt
            if attempt > 0:
                stricter_rules = get_stricter_prompt_constraints(attempt)
                current_prompt = system_prompt + "\n" + stricter_rules
                logger.info(f"CQS: Regenerating analysis for {req.game_id}, attempt {attempt + 1}")
            
            chat = LlmChat(
                api_key=EMERGENT_LLM_KEY,
                session_id=f"analysis_{req.game_id}_{attempt}",
                system_message=current_prompt
            ).with_model("openai", "gpt-5.2")
            
            user_message = UserMessage(text=f"Please analyze this game:\n\n{game['pgn']}")
            response = await chat.send_message(user_message)
        
            response_clean = response.strip()
            if response_clean.startswith("```json"):
                response_clean = response_clean[7:]
            if response_clean.startswith("```"):
                response_clean = response_clean[3:]
            if response_clean.endswith("```"):
                response_clean = response_clean[:-3]
            
            try:
                analysis_data = json.loads(response_clean)
            except json.JSONDecodeError as e:
                logger.error(f"JSON parse error on attempt {attempt + 1}: {e}")
                continue
            
            # CQS: Evaluate quality
            cqs_result = calculate_cqs(
                analysis_data,
                has_memory=has_memory,
                memory_callouts=memory_callouts
            )
            cqs_scores.append(cqs_result["total_score"])
            
            # Log the result (internal only)
            log_cqs_result(req.game_id, cqs_result, attempt + 1, not cqs_result["should_regenerate"])
            
            # Keep track of best result
            if best_analysis_data is None or cqs_result["total_score"] > best_cqs_result["total_score"]:
                best_analysis_data = analysis_data
                best_cqs_result = cqs_result
            
            # Check if we should accept
            if not cqs_result["should_regenerate"]:
                break
            
            # If this is the last attempt, we'll use the best one
            if attempt >= MAX_REGENERATIONS:
                break
        
        # Use the best analysis data
        analysis_data = best_analysis_data
        cqs_result = best_cqs_result
        
        # Validate explanations against contract
        validated_commentary = []
        for item in analysis_data.get("commentary", []):
            explanation = item.get("explanation", {})
            if explanation:
                is_valid, errors = validate_explanation(explanation)
                if not is_valid:
                    logger.warning(f"Explanation validation failed: {errors}")
                    # Fix common issues
                    if len(explanation.get("thinking_error", "")) < 10:
                        explanation["thinking_error"] = "Move was made without full board awareness"
                    if len(explanation.get("one_repeatable_rule", "")) < 10:
                        explanation["one_repeatable_rule"] = "Always scan the whole board before moving"
            validated_commentary.append(item)
        
        # Map weaknesses to predefined categories with full details
        categorized_weaknesses = []
        for w in analysis_data.get("identified_weaknesses", []) or analysis_data.get("identified_patterns", []):
            cat, subcat = categorize_weakness(
                w.get("category", "tactical"),
                w.get("subcategory", "one_move_blunders")
            )
            categorized_weaknesses.append({
                "category": cat,
                "subcategory": subcat,
                "description": w.get("description", ""),
                "advice": w.get("advice", ""),
                "display_name": subcat.replace("_", " ").title()
            })
        
        # STOCKFISH is the ONLY source of truth for move evaluation
        # GPT is ONLY for commentary text, never for blunder/mistake counts
        sf_stats = stockfish_result.get("user_stats", {}) if stockfish_result else {}
        
        # Check if Stockfish analysis was successful
        stockfish_valid = stockfish_result and stockfish_result.get("success", False)
        stockfish_has_data = sf_stats.get("accuracy", 0) > 0 or len(stockfish_result.get("moves", [])) > 0 if stockfish_result else False
        
        if not stockfish_valid or not stockfish_has_data:
            # Stockfish failed - log warning and mark analysis as incomplete
            logger.warning(f"Stockfish analysis failed for game {req.game_id}. Analysis will be marked as incomplete.")
            analysis_incomplete = True
        else:
            analysis_incomplete = False
        
        analysis = GameAnalysis(
            game_id=req.game_id,
            user_id=user.user_id,
            commentary=validated_commentary,
            blunders=sf_stats.get("blunders", 0),
            mistakes=sf_stats.get("mistakes", 0),
            inaccuracies=sf_stats.get("inaccuracies", 0),
            best_moves=sf_stats.get("best_moves", 0),
            overall_summary=analysis_data.get("overall_summary", ""),
            identified_patterns=[]  # Legacy field - will also store full data separately
        )
        
        # Store voice script and key lesson for future use
        voice_script = analysis_data.get("voice_script", analysis_data.get("voice_script_summary", ""))
        focus_week = analysis_data.get("focus_this_week", analysis_data.get("key_lesson", ""))
        
        # Update mistake_patterns collection (legacy support for pattern IDs)
        for pattern_data in categorized_weaknesses:
            existing_pattern = await db.mistake_patterns.find_one({
                "user_id": user.user_id,
                "category": pattern_data["category"],
                "subcategory": pattern_data["subcategory"]
            })
            
            if existing_pattern:
                await db.mistake_patterns.update_one(
                    {"pattern_id": existing_pattern["pattern_id"]},
                    {
                        "$inc": {"occurrences": 1},
                        "$push": {"game_ids": req.game_id},
                        "$set": {"last_seen": datetime.now(timezone.utc).isoformat()}
                    }
                )
                analysis.identified_patterns.append(existing_pattern["pattern_id"])
            else:
                new_pattern = MistakePattern(
                    user_id=user.user_id,
                    category=pattern_data["category"],
                    subcategory=pattern_data["subcategory"],
                    description=pattern_data.get("description", ""),
                    game_ids=[req.game_id]
                )
                pattern_doc = new_pattern.model_dump()
                pattern_doc['first_seen'] = pattern_doc['first_seen'].isoformat()
                pattern_doc['last_seen'] = pattern_doc['last_seen'].isoformat()
                await db.mistake_patterns.insert_one(pattern_doc)
                pattern_doc.pop('_id', None)
                analysis.identified_patterns.append(new_pattern.pattern_id)
        
        analysis_doc = analysis.model_dump()
        analysis_doc['created_at'] = analysis_doc['created_at'].isoformat()
        
        # Store full data for frontend display
        analysis_doc['weaknesses'] = categorized_weaknesses
        analysis_doc['identified_weaknesses'] = categorized_weaknesses
        analysis_doc['strengths'] = analysis_data.get("identified_strengths", [])
        analysis_doc['focus_this_week'] = focus_week
        analysis_doc['key_lesson'] = focus_week  # Backward compatibility
        analysis_doc['voice_script_summary'] = voice_script
        analysis_doc['summary_p1'] = analysis_data.get("summary_p1", "")
        analysis_doc['summary_p2'] = analysis_data.get("summary_p2", "")
        analysis_doc['improvement_note'] = analysis_data.get("improvement_note", "")
        
        # Use Stockfish best move suggestions (accurate) - merge with GPT's reasoning
        stockfish_best_moves = []
        if stockfish_move_data:
            for m in stockfish_move_data:
                # Get evaluation type safely
                eval_type = m.get('evaluation', 'unknown')
                if hasattr(eval_type, 'value'):
                    eval_type = eval_type.value
                    
                if eval_type in ['blunder', 'mistake'] and m.get('best_move'):
                    stockfish_best_moves.append({
                        "move_number": m.get('move_number'),
                        "played_move": m.get('move'),
                        "best_move": m.get('best_move'),
                        "cp_loss": m.get('cp_loss', 0),
                        "evaluation": eval_type,
                        "reason": f"Engine analysis shows this loses {m.get('cp_loss', 0)/100:.1f} pawns"
                    })
        analysis_doc['best_move_suggestions'] = stockfish_best_moves or analysis_data.get("best_move_suggestions", [])
        
        # Store Stockfish accuracy and detailed move analysis
        if stockfish_result and stockfish_result.get("success"):
            analysis_doc['stockfish_analysis'] = {
                "accuracy": sf_stats.get("accuracy", 0),
                "avg_cp_loss": sf_stats.get("avg_cp_loss", 0),
                "excellent_moves": sf_stats.get("excellent_moves", 0),
                "move_evaluations": stockfish_move_data
            }
        
        # CQS: Store internal metadata (NEVER exposed to users)
        analysis_doc['_cqs_internal'] = {
            "score": cqs_result["total_score"],
            "breakdown": cqs_result["breakdown"],
            "quality_level": cqs_result["quality_level"],
            "regeneration_attempts": len(cqs_scores),
            "all_scores": cqs_scores
        }
        
        await db.game_analyses.insert_one(analysis_doc)
        
        await db.games.update_one(
            {"game_id": req.game_id},
            {"$set": {"is_analyzed": True}}
        )
        
        # Remove _id before returning
        analysis_doc.pop('_id', None)
        
        # IMPORTANT: Remove internal CQS data before returning to user
        analysis_doc.pop('_cqs_internal', None)
        
        # Step 5: UPDATE PLAYER PROFILE (CRITICAL - happens after every game)
        logger.info(f"Updating PlayerProfile for user {user.user_id}")
        background_tasks.add_task(
            update_profile_after_analysis,
            db,
            user.user_id,
            req.game_id,
            analysis_data.get("blunders", 0),
            analysis_data.get("mistakes", 0),
            analysis_data.get("best_moves", 0),
            categorized_weaknesses,
            analysis_data.get("identified_strengths", [])
        )
        
        # Create RAG embeddings in background (RAG supports memory, doesn't define habits)
        background_tasks.add_task(create_game_embeddings, db, game, user.user_id)
        background_tasks.add_task(create_analysis_embedding, db, analysis_doc, game, user.user_id)
        
        # GAMIFICATION: Award XP for game analysis
        try:
            await add_xp(user.user_id, "game_analyzed")
            await increment_stat(user.user_id, "games_analyzed")
            
            # Bonus XP for high accuracy
            accuracy = sf_stats.get("accuracy", 0)
            if accuracy >= 90:
                await add_xp(user.user_id, "accuracy_90_plus")
            await update_best_accuracy(user.user_id, accuracy)
            
            # Award for no blunders
            if sf_stats.get("blunders", 0) == 0:
                await add_xp(user.user_id, "no_blunders")
                await increment_stat(user.user_id, "no_blunders_games")
            
            # Update streak
            await update_streak(user.user_id)
        except Exception as gam_err:
            logger.warning(f"Gamification update error (non-critical): {gam_err}")
        
        for pattern_data in categorized_weaknesses:
            pattern = await db.mistake_patterns.find_one({
                "user_id": user.user_id,
                "category": pattern_data["category"],
                "subcategory": pattern_data["subcategory"]
            }, {"_id": 0})
            if pattern:
                background_tasks.add_task(create_pattern_embedding, db, pattern, user.user_id)
        
        return analysis_doc
        
    except Exception as e:
        logger.error(f"Analysis error: {e}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

@api_router.get("/analysis/{game_id}")
async def get_analysis(game_id: str, user: User = Depends(get_current_user)):
    """Get analysis for a specific game"""
    analysis = await db.game_analyses.find_one(
        {"game_id": game_id, "user_id": user.user_id},
        {"_id": 0, "_cqs_internal": 0}  # Exclude internal CQS data
    )
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return analysis

# ==================== VOICE COACHING (TTS) ROUTES ====================

class TTSRequest(BaseModel):
    text: str
    voice: str = "onyx"  # Male coach voice - deep, authoritative

@api_router.post("/tts/generate")
async def generate_speech(req: TTSRequest, user: User = Depends(get_current_user)):
    """Generate speech audio from text using OpenAI TTS"""
    from emergentintegrations.llm.openai import OpenAITextToSpeech
    
    if not req.text or len(req.text.strip()) == 0:
        raise HTTPException(status_code=400, detail="Text is required")
    
    # Limit text length (OpenAI TTS limit is 4096 chars)
    text = req.text[:4000]
    
    try:
        tts = OpenAITextToSpeech(api_key=EMERGENT_LLM_KEY)
        
        # Generate speech as base64 for easy frontend use
        audio_base64 = await tts.generate_speech_base64(
            text=text,
            model="tts-1",  # Standard quality for faster response
            voice=req.voice,
            speed=1.0
        )
        
        return {
            "audio_base64": audio_base64,
            "format": "mp3",
            "voice": req.voice
        }
        
    except Exception as e:
        logger.error(f"TTS generation error: {e}")
        raise HTTPException(status_code=500, detail=f"Voice generation failed: {str(e)}")

@api_router.post("/tts/analysis-summary/{game_id}")
async def generate_analysis_voice(game_id: str, user: User = Depends(get_current_user)):
    """Generate voice coaching for a game analysis summary"""
    from emergentintegrations.llm.openai import OpenAITextToSpeech
    
    # Get the analysis
    analysis = await db.game_analyses.find_one(
        {"game_id": game_id, "user_id": user.user_id},
        {"_id": 0}
    )
    
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    
    # Check if we already have cached audio
    if analysis.get("voice_audio_base64"):
        return {
            "audio_base64": analysis["voice_audio_base64"],
            "format": "mp3",
            "voice": "onyx",
            "cached": True
        }
    
    # Build the voice script
    summary = analysis.get("overall_summary", "")
    key_lesson = analysis.get("key_lesson", "")
    
    # Create a natural speaking script
    voice_script = summary
    if key_lesson:
        voice_script += f" And here's the key lesson from this game: {key_lesson}"
    
    if not voice_script:
        raise HTTPException(status_code=400, detail="No summary available for voice generation")
    
    try:
        tts = OpenAITextToSpeech(api_key=EMERGENT_LLM_KEY)
        
        audio_base64 = await tts.generate_speech_base64(
            text=voice_script[:4000],
            model="tts-1",
            voice="onyx",  # Male coach voice
            speed=0.95  # Slightly slower for coaching clarity
        )
        
        # Cache the audio in the database
        await db.game_analyses.update_one(
            {"game_id": game_id},
            {"$set": {"voice_audio_base64": audio_base64}}
        )
        
        return {
            "audio_base64": audio_base64,
            "format": "mp3",
            "voice": "onyx",
            "cached": False
        }
        
    except Exception as e:
        logger.error(f"TTS analysis voice error: {e}")
        raise HTTPException(status_code=500, detail=f"Voice generation failed: {str(e)}")

class MoveVoiceRequest(BaseModel):
    game_id: str
    move_index: int

@api_router.post("/tts/move-explanation")
async def generate_move_voice(req: MoveVoiceRequest, user: User = Depends(get_current_user)):
    """Generate voice explanation for a specific move"""
    from emergentintegrations.llm.openai import OpenAITextToSpeech
    
    analysis = await db.game_analyses.find_one(
        {"game_id": req.game_id, "user_id": user.user_id},
        {"_id": 0}
    )
    
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    
    commentary = analysis.get("commentary", [])
    if req.move_index < 0 or req.move_index >= len(commentary):
        raise HTTPException(status_code=400, detail="Invalid move index")
    
    move = commentary[req.move_index]
    
    # Build voice script for this move
    parts = []
    
    move_num = move.get("move_number", "")
    move_name = move.get("move", "")
    parts.append(f"Move {move_num}, {move_name}.")
    
    if move.get("player_intention"):
        parts.append(f"I see what you were going for: {move['player_intention']}")
    
    if move.get("coach_response"):
        parts.append(move["coach_response"])
    elif move.get("comment"):
        parts.append(move["comment"])
    
    if move.get("better_move"):
        parts.append(f"A better option was {move['better_move']}.")
    
    explanation = move.get("explanation", {})
    if explanation.get("one_repeatable_rule"):
        parts.append(f"Remember: {explanation['one_repeatable_rule']}")
    
    voice_script = " ".join(parts)
    
    if not voice_script:
        raise HTTPException(status_code=400, detail="No explanation available for this move")
    
    try:
        tts = OpenAITextToSpeech(api_key=EMERGENT_LLM_KEY)
        
        audio_base64 = await tts.generate_speech_base64(
            text=voice_script[:4000],
            model="tts-1",
            voice="onyx",
            speed=0.95
        )
        
        return {
            "audio_base64": audio_base64,
            "format": "mp3",
            "voice": "onyx",
            "move_number": move_num
        }
        
    except Exception as e:
        logger.error(f"TTS move voice error: {e}")
        raise HTTPException(status_code=500, detail=f"Voice generation failed: {str(e)}")

# ==================== JOURNEY DASHBOARD ROUTES ====================

@api_router.get("/journey")
async def get_journey_dashboard(user: User = Depends(get_current_user)):
    """
    Get Journey Dashboard data - proves learning over time.
    
    This is the primary surface where coaching results appear.
    No manual analysis required - games are analyzed automatically.
    """
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

@api_router.get("/journey/weekly-assessment")
async def get_weekly_assessment(user: User = Depends(get_current_user)):
    """Get coach's weekly assessment paragraph"""
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

@api_router.get("/journey/weakness-trends")
async def get_weakness_trends(user: User = Depends(get_current_user)):
    """Get weakness trend data - shows if habits are improving"""
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

class LinkAccountRequest(BaseModel):
    platform: str  # "chess.com" or "lichess"
    username: str

@api_router.post("/journey/link-account")
async def link_chess_account(req: LinkAccountRequest, user: User = Depends(get_current_user)):
    """
    Link Chess.com or Lichess account for automatic game tracking.
    This enables silent background analysis.
    """
    platform = req.platform.lower()
    username = req.username.strip()
    
    if platform not in ["chess.com", "lichess"]:
        raise HTTPException(status_code=400, detail="Invalid platform. Use 'chess.com' or 'lichess'")
    
    if not username:
        raise HTTPException(status_code=400, detail="Username is required")
    
    # Validate account exists
    if platform == "chess.com":
        games = await fetch_recent_chesscom_games(username)
        if not games and games != []:
            raise HTTPException(status_code=404, detail=f"Chess.com user '{username}' not found")
        update_field = "chesscom_username"
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

@api_router.get("/journey/linked-accounts")
async def get_linked_accounts(user: User = Depends(get_current_user)):
    """Get user's linked chess accounts"""
    user_doc = await db.users.find_one(
        {"user_id": user.user_id},
        {"_id": 0, "chesscom_username": 1, "lichess_username": 1}
    )
    
    if not user_doc:
        return {"chess_com": None, "lichess": None}
    
    return {
        "chess_com": user_doc.get("chesscom_username"),
        "lichess": user_doc.get("lichess_username")
    }

@api_router.post("/journey/sync-now")
async def trigger_game_sync(background_tasks: BackgroundTasks, user: User = Depends(get_current_user)):
    """
    Manually trigger game sync for the current user.
    Runs the sync immediately in the background.
    """
    from journey_service import sync_user_games
    
    user_doc = await db.users.find_one(
        {"user_id": user.user_id},
        {"_id": 0}
    )
    
    if not user_doc:
        raise HTTPException(status_code=404, detail="User not found")
    
    has_linked = user_doc.get("chesscom_username") or user_doc.get("lichess_username")
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

# ==================== COACH MODE ROUTES ====================

@api_router.post("/coach/start-session")
async def start_coach_session(
    data: dict,
    user: User = Depends(get_current_user)
):
    """Start a play session - user is going to play"""
    from coach_session_service import start_play_session
    platform = data.get("platform", "chess.com")
    result = await start_play_session(db, user.user_id, platform)
    return result


@api_router.post("/coach/end-session")
async def end_coach_session(user: User = Depends(get_current_user)):
    """End play session - user finished playing, find and analyze their game"""
    from coach_session_service import end_play_session
    result = await end_play_session(db, user.user_id)
    return result


@api_router.get("/coach/analysis-status/{game_id}")
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


@api_router.get("/coach/session-status")
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


@api_router.post("/coach/track-reflection")
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


@api_router.get("/coach/habits")
async def get_habit_statuses(user: User = Depends(get_current_user)):
    """Get all habit statuses for the user."""
    from habit_rotation_service import get_all_habit_statuses
    statuses = await get_all_habit_statuses(db, user.user_id)
    return {"habits": statuses}


@api_router.post("/coach/check-habit-rotation")
async def check_habit_rotation(user: User = Depends(get_current_user)):
    """Manually check if habit should be rotated."""
    from habit_rotation_service import check_and_rotate_habit
    result = await check_and_rotate_habit(db, user.user_id)
    return result


@api_router.get("/user/weekly-summary")
async def get_weekly_summary(user: User = Depends(get_current_user)):
    """Get user's weekly summary data."""
    from weekly_summary_service import generate_weekly_summary_data
    summary = await generate_weekly_summary_data(db, user.user_id)
    return summary


@api_router.post("/user/send-weekly-summary")
async def send_weekly_summary_to_user(user: User = Depends(get_current_user)):
    """Send weekly summary email to current user."""
    from weekly_summary_service import send_single_weekly_summary
    result = await send_single_weekly_summary(db, user.user_id)
    return result


@api_router.post("/admin/send-all-weekly-summaries")
async def send_all_weekly_summaries(user: User = Depends(get_current_user)):
    """Admin endpoint to trigger weekly summaries for all users."""
    # Simple admin check - in production, use proper admin auth
    from weekly_summary_service import send_weekly_summaries
    result = await send_weekly_summaries(db)
    return result


@api_router.get("/coach/today")
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
    correction = None
    if top_weaknesses:
        top = top_weaknesses[0]
        subcategory = top.get("subcategory", "").replace("_", " ").title()
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
            context = f"This appeared in {recent_count} of your last {total_recent} games."
        else:
            context = f"This has occurred {occurrences} times in your recent games."
        
        correction = {
            "title": subcategory,
            "context": context,
            "severity": "This remains your biggest rating leak." if occurrences > 5 else "Focus here to see improvement."
        }
    
    # ===== SECTION 2: KEEP DOING THIS (Reinforcement) =====
    reinforcement = None
    
    # Check for strengths in profile
    strengths = profile.get("strengths", []) if profile else []
    improving_areas = profile.get("improving_areas", []) if profile else []
    
    # Look for genuine improvement or strength
    if improving_areas:
        area = improving_areas[0]
        reinforcement = {
            "title": area.get("name", "Positional Play").replace("_", " ").title(),
            "context": "Recent games show improvement here.",
            "trend": "Earlier this was unstable — now improving."
        }
    elif strengths:
        strength = strengths[0] if isinstance(strengths[0], dict) else {"name": strengths[0]}
        reinforcement = {
            "title": strength.get("name", "Solid Play").replace("_", " ").title(),
            "context": "You've maintained consistency in this area.",
            "trend": "Keep this discipline."
        }
    else:
        # Check recent analyses for any positive signals
        recent_blunders = [a.get("blunders", 0) for a in recent_analyses[:3]]
        if recent_blunders and sum(recent_blunders) == 0:
            reinforcement = {
                "title": "Clean Calculation",
                "context": "Your last few games had no major blunders.",
                "trend": "This focus is paying off."
            }
        elif len(recent_analyses) >= 2:
            # Default neutral reinforcement
            reinforcement = {
                "title": "Steady Progress",
                "context": "You maintained discipline this week.",
                "trend": "Consistency builds long-term strength."
            }
    
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
    
    # ===== SECTION 0: PERSONALIZED DECISION RECONSTRUCTION (PDR) =====
    # Transform passive analysis into active cognitive training
    pdr = None
    
    try:
        import chess
        import chess.pgn
        import io
        import random
        from pdr_service import get_refutation, generate_idea_chain_explanation, get_simple_refutation_fallback, generate_why_options
        
        # Get dominant habit for preference
        dominant_habit = None
        if top_weaknesses:
            dominant_habit = top_weaknesses[0].get("subcategory", "").lower()
        
        # Get recent game analyses with mistakes
        recent_with_mistakes = await db.game_analyses.find(
            {
                "user_id": user.user_id,
                "blunders": {"$gt": 0}
            },
            {"_id": 0, "game_id": 1, "commentary": 1, "blunders": 1, "user_color": 1, 
             "identified_weaknesses": 1, "weaknesses": 1}
        ).sort("created_at", -1).limit(10).to_list(10)
        
        # Collect all valid mistakes, categorized by habit alignment
        habit_aligned_mistakes = []
        other_mistakes = []
        
        for analysis in recent_with_mistakes:
            commentary = analysis.get("commentary", [])
            if not commentary:
                continue
            
            # Check if this analysis has the dominant habit
            weaknesses = analysis.get("identified_weaknesses", []) or analysis.get("weaknesses", [])
            has_dominant_habit = False
            if dominant_habit and weaknesses:
                for w in weaknesses:
                    if isinstance(w, dict):
                        if dominant_habit in str(w.get("subcategory", "")).lower():
                            has_dominant_habit = True
                            break
                    elif isinstance(w, str) and dominant_habit in w.lower():
                        has_dominant_habit = True
                        break
            
            for move_data in commentary:
                eval_type = str(move_data.get("evaluation", "")).lower()
                if eval_type in ["blunder", "mistake"]:
                    user_move = move_data.get("move")
                    best_move = move_data.get("best_move") or move_data.get("consider")
                    if user_move and best_move and user_move != best_move:
                        mistake_entry = {
                            "analysis": analysis,
                            "move_data": move_data
                        }
                        if has_dominant_habit:
                            habit_aligned_mistakes.append(mistake_entry)
                        else:
                            other_mistakes.append(mistake_entry)
        
        # Prefer habit-aligned mistakes (70% chance if available)
        all_mistakes = []
        if habit_aligned_mistakes and random.random() < 0.7:
            all_mistakes = habit_aligned_mistakes
        else:
            all_mistakes = habit_aligned_mistakes + other_mistakes
        
        # Randomly select one mistake
        if all_mistakes:
            random.shuffle(all_mistakes)
            selected = all_mistakes[0]
            analysis = selected["analysis"]
            move_data = selected["move_data"]
            
            move_number = move_data.get("move_number", 1)
            user_move = move_data.get("move")
            best_move = move_data.get("best_move") or move_data.get("consider")
            
            # Get the game with full details
            game = await db.games.find_one(
                {"game_id": analysis.get("game_id")},
                {"_id": 0, "pgn": 1, "user_color": 1, "opponent": 1, "platform": 1, 
                 "date": 1, "time_control": 1, "result": 1, "url": 1, "white": 1, "black": 1}
            )
            
            if game and game.get("pgn"):
                try:
                    pgn_io = io.StringIO(game["pgn"])
                    chess_game = chess.pgn.read_game(pgn_io)
                    if chess_game:
                        board = chess_game.board()
                        current_move = 0
                        target_half_move = (move_number - 1) * 2
                        
                        user_color = game.get("user_color") or analysis.get("user_color", "white")
                        if user_color == "black":
                            target_half_move += 1
                        
                        for node in chess_game.mainline():
                            if current_move >= target_half_move:
                                break
                            board.push(node.move)
                            current_move += 1
                        
                        fen = board.fen()
                        player_to_move = "white" if board.turn else "black"
                        
                        # Get refutation for wrong answer
                        refutation = get_refutation(fen, user_move)
                        if not refutation:
                            refutation = get_simple_refutation_fallback(fen, user_move, best_move)
                        
                        # Generate idea chain for wrong answer
                        idea_chain = None
                        if refutation:
                            idea_chain = await generate_idea_chain_explanation(
                                fen, user_move, best_move, refutation, db
                            )
                        
                        # Generate "why" options for correct answer verification
                        why_options = await generate_why_options(fen, best_move, user_move, refutation, db)
                        
                        # Only TWO candidates: user's move and best move
                        candidates = [
                            {"move": best_move, "is_best": True, "is_user_move": False},
                            {"move": user_move, "is_best": False, "is_user_move": True}
                        ]
                        random.shuffle(candidates)
                        
                        # Build game context
                        opponent = game.get("opponent") or (
                            game.get("black") if user_color == "white" else game.get("white")
                        )
                        platform = game.get("platform", "chess.com")
                        game_date = game.get("date", "")
                        time_control = game.get("time_control", "")
                        result = game.get("result", "")
                        
                        # Build game URL for full analysis link
                        game_url = game.get("url", "")
                        if not game_url and platform:
                            # Construct URL if not stored
                            game_id_str = str(analysis.get("game_id", ""))
                            if "chess.com" in platform.lower():
                                game_url = f"https://www.chess.com/game/live/{game_id_str}"
                            elif "lichess" in platform.lower():
                                game_url = f"https://lichess.org/{game_id_str}"
                        
                        pdr = {
                            "fen": fen,
                            "player_color": player_to_move,
                            "candidates": candidates,
                            "user_original_move": user_move,
                            "best_move": best_move,
                            "game_id": analysis.get("game_id"),
                            "move_number": move_number,
                            "refutation": refutation,
                            "idea_chain": idea_chain,
                            "why_options": why_options,
                            # Game context
                            "game_context": {
                                "opponent": opponent,
                                "platform": platform,
                                "date": game_date,
                                "time_control": time_control,
                                "result": result,
                                "game_url": game_url,
                                "analysis_url": f"/game/{analysis.get('game_id')}"
                            }
                        }
                        
                except Exception as e:
                    logger.warning(f"PDR extraction error: {e}")
                
    except Exception as e:
        logger.error(f"Error building PDR: {e}")
        pdr = None
    
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
    
    # Blunders per game trend
    recent_10 = recent_analyses[:10] if recent_analyses else []
    older_10 = recent_analyses[10:20] if len(recent_analyses) > 10 else []
    
    if recent_10:
        recent_blunders = sum(a.get("blunders", 0) for a in recent_10) / len(recent_10)
        if older_10:
            older_blunders = sum(a.get("blunders", 0) for a in older_10) / len(older_10)
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
    # Get the most recently PLAYED game that has been analyzed
    last_game = None
    
    # First get the most recent analyzed game - SORTED by imported_at
    most_recent_games = await db.games.find(
        {"user_id": user.user_id, "is_analyzed": True},
        {"_id": 0, "game_id": 1, "result": 1, "user_color": 1, "time_control": 1, 
         "platform": 1, "url": 1, "pgn": 1, "termination": 1}
    ).sort("imported_at", -1).limit(1).to_list(1)
    
    most_recent_game = most_recent_games[0] if most_recent_games else None
    
    if most_recent_game:
        # Get the analysis for this specific game
        last_analysis = await db.game_analyses.find_one(
            {"game_id": most_recent_game.get("game_id"), "user_id": user.user_id},
            {"_id": 0, "blunders": 1, "mistakes": 1, "accuracy": 1, "commentary": 1, "identified_weaknesses": 1}
        )
        
        if last_analysis:
            blunders = last_analysis.get("blunders", 0)
            mistakes = last_analysis.get("mistakes", 0)
            accuracy = last_analysis.get("accuracy", 0)
            
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
            draw = "1/2" in result
            
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
            
            # Find the critical mistake from this game's commentary
            critical_moment = None
            commentary = last_analysis.get("commentary", [])
            for move_data in commentary:
                eval_type = str(move_data.get("evaluation", "")).lower()
                if eval_type in ["blunder", "mistake"]:
                    critical_moment = {
                        "move_number": move_data.get("move_number"),
                        "move": move_data.get("move"),
                        "best_move": move_data.get("best_move") or move_data.get("consider"),
                        "explanation": move_data.get("explanation", "")[:150]
                    }
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
                if critical_moment:
                    comment = f"One blunder on move {critical_moment['move_number']}. {critical_moment['explanation'][:80]}..."
                elif repeated_habit:
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
                "critical_moment": critical_moment
            }
    
    return {
        "has_data": True,
        "pdr": pdr,
        "coach_note": coach_note,
        "light_stats": light_stats,
        "next_game_plan": next_game_plan,
        "session_status": session_status,
        "last_game": last_game,
        "rule": rule
    }


@api_router.get("/progress")
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
        {"_id": 0, "accuracy": 1, "blunders": 1, "mistakes": 1, "created_at": 1}
    ).sort("created_at", -1).limit(20).to_list(20)
    
    # Calculate accuracy trend
    accuracy_data = {"current": None, "previous": None, "trend": "stable"}
    if recent_analyses:
        recent_10 = [a.get("accuracy", 0) for a in recent_analyses[:10] if a.get("accuracy")]
        previous_10 = [a.get("accuracy", 0) for a in recent_analyses[10:20] if a.get("accuracy")]
        
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
    
    # Calculate blunder trend
    blunders_data = {"avg_per_game": None, "total": 0, "trend": "stable"}
    if recent_analyses:
        recent_blunders = [a.get("blunders", 0) for a in recent_analyses[:10]]
        previous_blunders = [a.get("blunders", 0) for a in recent_analyses[10:20]]
        
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
    
    return {
        "rating": rating_data,
        "accuracy": accuracy_data,
        "blunders": blunders_data,
        "habits": habits,
        "resolved_habits": resolved_habits
    }


# ==================== WEAKNESS/PATTERN ROUTES ====================

@api_router.get("/patterns")
async def get_patterns(user: User = Depends(get_current_user)):
    """Get all mistake patterns for the current user"""
    patterns = await db.mistake_patterns.find(
        {"user_id": user.user_id},
        {"_id": 0}
    ).sort("occurrences", -1).to_list(50)
    return patterns

# ==================== PLAYER PROFILE ROUTES ====================

@api_router.get("/profile")
async def get_player_profile(user: User = Depends(get_current_user)):
    """Get the player's coaching profile"""
    profile = await get_or_create_profile(db, user.user_id, user.name)
    return profile

@api_router.get("/profile/weaknesses")
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

@api_router.get("/profile/strengths")
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

class UpdateCoachingPreferencesRequest(BaseModel):
    learning_style: Optional[str] = None  # "concise" or "detailed"
    coaching_tone: Optional[str] = None   # "firm", "encouraging", "balanced"

@api_router.patch("/profile/preferences")
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

@api_router.get("/weakness-categories")
async def get_weakness_categories():
    """Get all predefined weakness categories"""
    return {"categories": WEAKNESS_CATEGORIES}

class RecordChallengeResultRequest(BaseModel):
    weakness_category: str
    weakness_subcategory: str
    success: bool
    puzzle_id: Optional[str] = None

@api_router.post("/profile/challenge-result")
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

# ==================== EMAIL NOTIFICATION SETTINGS ====================

class EmailNotificationSettings(BaseModel):
    game_analyzed: bool = True
    weekly_summary: bool = True
    weakness_alert: bool = True

@api_router.get("/settings/email-notifications")
async def get_email_notification_settings(user: User = Depends(get_current_user)):
    """Get user's email notification preferences"""
    user_doc = await db.users.find_one(
        {"user_id": user.user_id},
        {"_id": 0, "email_notifications": 1, "email": 1}
    )
    
    if not user_doc:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Default settings if not set
    default_settings = {
        "game_analyzed": True,
        "weekly_summary": True,
        "weakness_alert": True
    }
    
    return {
        "email": user_doc.get("email", ""),
        "notifications": user_doc.get("email_notifications", default_settings)
    }

@api_router.put("/settings/email-notifications")
async def update_email_notification_settings(
    settings: EmailNotificationSettings,
    user: User = Depends(get_current_user)
):
    """Update user's email notification preferences"""
    await db.users.update_one(
        {"user_id": user.user_id},
        {"$set": {
            "email_notifications": {
                "game_analyzed": settings.game_analyzed,
                "weekly_summary": settings.weekly_summary,
                "weakness_alert": settings.weakness_alert
            }
        }}
    )
    
    return {
        "message": "Email notification settings updated",
        "notifications": {
            "game_analyzed": settings.game_analyzed,
            "weekly_summary": settings.weekly_summary,
            "weakness_alert": settings.weakness_alert
        }
    }

@api_router.post("/settings/test-email")
async def send_test_email(user: User = Depends(get_current_user)):
    """Send a test email to verify email configuration"""
    from email_service import send_email, is_email_configured
    
    if not is_email_configured():
        raise HTTPException(
            status_code=503, 
            detail="Email service not configured. Please add SENDGRID_API_KEY to environment."
        )
    
    user_doc = await db.users.find_one(
        {"user_id": user.user_id},
        {"_id": 0, "email": 1, "name": 1}
    )
    
    if not user_doc or not user_doc.get("email"):
        raise HTTPException(status_code=400, detail="No email address found for user")
    
    subject = "🎯 Chess Coach AI - Test Email"
    html_content = f"""
    <html>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
        <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
            <h2>✅ Email Test Successful!</h2>
            <p>Hey {user_doc.get('name', 'Chess Player')}!</p>
            <p>Great news - your email notifications are working correctly.</p>
            <p>You'll receive notifications when:</p>
            <ul>
                <li>New games are analyzed</li>
                <li>Weekly progress summaries are ready</li>
                <li>Recurring weaknesses are detected</li>
            </ul>
            <p>Keep improving your game! ♟️</p>
            <p><em>— Your Chess Coach</em></p>
        </div>
    </body>
    </html>
    """
    
    success = await send_email(user_doc["email"], subject, html_content)
    
    if success:
        return {"message": "Test email sent successfully", "email": user_doc["email"]}
    else:
        raise HTTPException(status_code=500, detail="Failed to send test email")

# ==================== PUSH NOTIFICATIONS ====================

class RegisterDeviceRequest(BaseModel):
    push_token: str
    platform: str  # 'ios' or 'android'

@api_router.post("/notifications/register-device")
async def register_push_device(request: RegisterDeviceRequest, user: User = Depends(get_current_user)):
    """Register a device for push notifications"""
    await db.users.update_one(
        {"user_id": user.user_id},
        {
            "$set": {
                "push_token": request.push_token,
                "push_platform": request.platform,
                "push_registered_at": datetime.now(timezone.utc).isoformat()
            }
        }
    )
    return {"message": "Device registered for push notifications"}

@api_router.delete("/notifications/unregister-device")
async def unregister_push_device(user: User = Depends(get_current_user)):
    """Unregister device from push notifications"""
    await db.users.update_one(
        {"user_id": user.user_id},
        {
            "$unset": {
                "push_token": "",
                "push_platform": "",
                "push_registered_at": ""
            }
        }
    )
    return {"message": "Device unregistered from push notifications"}

async def send_push_notification(user_id: str, title: str, body: str, data: dict = None):
    """
    Send push notification to a user via Expo Push API.
    This is called when games are analyzed, etc.
    """
    import httpx
    
    user_doc = await db.users.find_one(
        {"user_id": user_id},
        {"_id": 0, "push_token": 1, "email_notifications": 1}
    )
    
    if not user_doc or not user_doc.get("push_token"):
        return False
    
    push_token = user_doc["push_token"]
    
    # Check if user has notifications enabled
    email_prefs = user_doc.get("email_notifications", {})
    if not email_prefs.get("game_analyzed", True):
        return False
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://exp.host/--/api/v2/push/send",
                json={
                    "to": push_token,
                    "title": title,
                    "body": body,
                    "data": data or {},
                    "sound": "default",
                    "channelId": "analysis",
                },
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                logger.info(f"Push notification sent to user {user_id}")
                return True
            else:
                logger.warning(f"Push notification failed: {response.text}")
                return False
    except Exception as e:
        logger.error(f"Failed to send push notification: {e}")
        return False

@api_router.get("/dashboard-stats")
async def get_dashboard_stats(user: User = Depends(get_current_user)):
    """Get dashboard statistics including player profile for the current user"""
    total_games = await db.games.count_documents({"user_id": user.user_id})
    analyzed_games = await db.games.count_documents({"user_id": user.user_id, "is_analyzed": True})
    
    # Get player profile for coaching context
    profile = await db.player_profiles.find_one(
        {"user_id": user.user_id},
        {"_id": 0}
    )
    
    # Get top weaknesses from profile (with decay) instead of raw patterns
    top_weaknesses = []
    if profile:
        top_weaknesses = profile.get("top_weaknesses", [])[:5]
    else:
        # Fallback to legacy patterns if no profile
        patterns = await db.mistake_patterns.find(
            {"user_id": user.user_id},
            {"_id": 0}
        ).sort("occurrences", -1).to_list(5)
        top_weaknesses = patterns
    
    recent_games = await db.games.find(
        {"user_id": user.user_id},
        {"_id": 0}
    ).sort("imported_at", -1).to_list(5)
    
    analyses = await db.game_analyses.find(
        {"user_id": user.user_id},
        {"_id": 0}
    ).to_list(100)
    
    total_blunders = sum(a.get('blunders', 0) for a in analyses)
    total_mistakes = sum(a.get('mistakes', 0) for a in analyses)
    total_best_moves = sum(a.get('best_moves', 0) for a in analyses)
    
    # Build response with profile data
    response = {
        "total_games": total_games,
        "analyzed_games": analyzed_games,
        "top_weaknesses": top_weaknesses,
        "recent_games": recent_games,
        "stats": {
            "total_blunders": total_blunders,
            "total_mistakes": total_mistakes,
            "total_best_moves": total_best_moves
        }
    }
    
    # Add profile summary if available
    if profile:
        response["profile_summary"] = {
            "estimated_level": profile.get("estimated_level", "intermediate"),
            "estimated_elo": profile.get("estimated_elo", 1200),
            "improvement_trend": profile.get("improvement_trend", "stuck"),
            "strengths": profile.get("strengths", [])[:3],
            "learning_style": profile.get("learning_style", "concise"),
            "coaching_tone": profile.get("coaching_tone", "encouraging"),
            "challenges_solved": profile.get("challenges_solved", 0),
            "challenges_attempted": profile.get("challenges_attempted", 0)
        }
    
    return response

@api_router.get("/training-recommendations")
async def get_training_recommendations(user: User = Depends(get_current_user)):
    """Get AI-generated training recommendations based on weaknesses"""
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    
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
    
    try:
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"recommendations_{user.user_id}",
            system_message="""You are a chess coach creating a personalized training plan.
Based on the player's mistake patterns, suggest 3-5 specific training exercises.
Be specific and actionable. Respond in JSON format:
{
    "recommendations": [
        {"title": "...", "description": "...", "priority": "high/medium/low", "estimated_time": "15 mins"}
    ]
}"""
        ).with_model("openai", "gpt-5.2")
        
        response = await chat.send_message(UserMessage(
            text=f"Create training recommendations for a player with these weakness patterns:\n{patterns_text}"
        ))
        
        import json
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

@api_router.get("/rating/trajectory")
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
    current_rating = 1200  # Default
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

@api_router.get("/training/time-management")
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

@api_router.get("/training/fast-thinking")
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

@api_router.get("/training/puzzles")
async def get_training_puzzles(user: User = Depends(get_current_user), count: int = 5):
    """
    Get personalized puzzles based on weaknesses.
    Puzzles are selected to target the player's specific weak areas.
    """
    # Get weaknesses
    profile = await db.player_profiles.find_one(
        {"user_id": user.user_id},
        {"_id": 0, "top_weaknesses": 1}
    )
    weaknesses = profile.get("top_weaknesses", []) if profile else []
    
    # Generate training session
    session = generate_training_session(weaknesses, count)
    
    return session

@api_router.post("/training/puzzles/{puzzle_index}/solve")
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

# ==================== STOCKFISH POSITION ANALYSIS ====================

class PositionAnalysisRequest(BaseModel):
    fen: str
    depth: int = 18

@api_router.post("/analyze-position")
async def analyze_position(req: PositionAnalysisRequest, user: User = Depends(get_current_user)):
    """
    Analyze a single position using Stockfish.
    Returns evaluation and best moves.
    """
    try:
        result = get_position_evaluation(req.fen, depth=req.depth)
        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("error", "Analysis failed"))
        return result
    except Exception as e:
        logger.error(f"Position analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/best-moves")
async def get_best_moves(req: PositionAnalysisRequest, num_moves: int = 3, user: User = Depends(get_current_user)):
    """
    Get the top N best moves for a position using Stockfish.
    Useful for showing alternatives.
    """
    try:
        result = get_best_moves_for_position(req.fen, num_moves=num_moves, depth=req.depth)
        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("error", "Analysis failed"))
        return result
    except Exception as e:
        logger.error(f"Best moves analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== BASIC ROUTES ====================

@api_router.get("/")
async def root():
    return {"message": "Chess Coach API"}

@api_router.get("/health")
async def health():
    return {"status": "healthy"}

# ==================== CHALLENGE/PUZZLE ROUTES ====================

class GeneratePuzzleRequest(BaseModel):
    pattern_id: Optional[str] = None
    category: str = "tactical"
    subcategory: str = "general"

@api_router.post("/generate-puzzle")
async def generate_puzzle(req: GeneratePuzzleRequest, user: User = Depends(get_current_user)):
    """Generate a puzzle based on user's weakness pattern from PlayerProfile"""
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    import json
    
    # Get player profile for context
    profile = await db.player_profiles.find_one(
        {"user_id": user.user_id},
        {"_id": 0}
    )
    
    # Determine which weakness to target
    weakness_context = ""
    target_category = req.category
    target_subcategory = req.subcategory
    
    if req.pattern_id:
        # Use specified pattern
        pattern = await db.mistake_patterns.find_one(
            {"pattern_id": req.pattern_id, "user_id": user.user_id},
            {"_id": 0}
        )
        if pattern:
            target_category, target_subcategory = categorize_weakness(
                pattern.get("category", "tactical"),
                pattern.get("subcategory", "one_move_blunders")
            )
            weakness_context = f"The player struggles with: {target_subcategory.replace('_', ' ')} ({target_category}). {pattern.get('description', '')}"
    elif profile and profile.get("top_weaknesses"):
        # Use top weakness from profile
        top_weakness = profile["top_weaknesses"][0]
        target_category = top_weakness.get("category", "tactical")
        target_subcategory = top_weakness.get("subcategory", "one_move_blunders")
        weakness_context = f"Player's #1 weakness: {target_subcategory.replace('_', ' ')} ({target_category}). Score: {top_weakness.get('decayed_score', 1)}"
    else:
        weakness_context = f"Focus on {req.subcategory.replace('_', ' ')} in the {req.category} category."
    
    # Get player level for difficulty calibration
    player_level = "intermediate"
    if profile:
        player_level = profile.get("estimated_level", "intermediate")
    
    system_prompt = f"""You are a chess puzzle creator. Create a tactical puzzle for training.

Player Level: {player_level.upper()}
Target Weakness: {weakness_context}

Create a puzzle that specifically targets this weakness. The puzzle should:
1. Have a clear winning move or sequence
2. Be instructive for the specific weakness
3. Difficulty appropriate for {player_level} level ({"1 move" if player_level == "beginner" else "1-3 moves"})

Respond in JSON format ONLY:
{{
    "title": "Short descriptive title",
    "description": "Brief description of what to look for",
    "fen": "Valid FEN position string",
    "player_color": "white" or "black",
    "solution_san": "The correct move in SAN notation (e.g., Nxf7)",
    "solution": [{{"from": "e4", "to": "f7"}}],
    "hint": "A subtle hint without giving away the answer",
    "theme": "{target_subcategory}",
    "explanation": {{
        "thinking_error": "What thinking error does this puzzle train against",
        "one_repeatable_rule": "The rule this puzzle teaches"
    }}
}}

Make sure the FEN is valid and the solution is correct for that position."""

    try:
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"puzzle_{user.user_id}_{uuid.uuid4().hex[:8]}",
            system_message=system_prompt
        ).with_model("openai", "gpt-5.2")
        
        response = await chat.send_message(UserMessage(
            text=f"Generate a {target_category} puzzle focusing on {target_subcategory.replace('_', ' ')}"
        ))
        
        response_clean = response.strip()
        if response_clean.startswith("```json"):
            response_clean = response_clean[7:]
        if response_clean.startswith("```"):
            response_clean = response_clean[3:]
        if response_clean.endswith("```"):
            response_clean = response_clean[:-3]
        
        puzzle = json.loads(response_clean)
        
        # Store puzzle with target weakness for feedback loop
        puzzle_doc = {
            "puzzle_id": f"puzzle_{uuid.uuid4().hex[:12]}",
            "user_id": user.user_id,
            "pattern_id": req.pattern_id,
            "target_category": target_category,
            "target_subcategory": target_subcategory,
            "solved": None,  # Will be updated when user submits result
            "solve_time_seconds": None,
            **puzzle,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        await db.puzzles.insert_one(puzzle_doc)
        puzzle_doc.pop('_id', None)
        
        return puzzle_doc
        
    except Exception as e:
        logger.error(f"Puzzle generation error: {e}")
        # Return a fallback puzzle with proper tracking fields
        fallback_puzzle = {
            "puzzle_id": f"puzzle_{uuid.uuid4().hex[:12]}",
            "user_id": user.user_id,
            "target_category": target_category,
            "target_subcategory": target_subcategory,
            "title": "Tactical Training",
            "description": f"Find the best move in this {target_subcategory.replace('_', ' ')} position",
            "fen": "r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 4 4",
            "player_color": "white",
            "solution_san": "Qxf7#",
            "solution": [{"from": "h5", "to": "f7"}],
            "hint": "Look for a forcing move that attacks multiple pieces",
            "theme": target_subcategory,
            "explanation": {
                "thinking_error": "Missing forcing moves that end the game",
                "one_repeatable_rule": "Always check for checkmate threats first"
            },
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        await db.puzzles.insert_one(fallback_puzzle)
        fallback_puzzle.pop('_id', None)
        return fallback_puzzle

# ==================== GAMIFICATION ROUTES ====================

from gamification_service import (
    get_user_progress,
    add_xp,
    update_streak,
    increment_stat,
    update_best_accuracy,
    get_user_achievements,
    check_and_award_achievements,
    claim_daily_reward,
    get_leaderboard,
    LEVELS,
    ACHIEVEMENTS,
    XP_REWARDS
)

@api_router.get("/gamification/progress")
async def get_progress(user: User = Depends(get_current_user)):
    """Get user's XP, level, streak, and stats"""
    progress = await get_user_progress(user.user_id)
    return progress

@api_router.get("/gamification/achievements")
async def get_achievements(user: User = Depends(get_current_user)):
    """Get all achievements with unlock status"""
    achievements = await get_user_achievements(user.user_id)
    return achievements

@api_router.post("/gamification/daily-reward")
async def claim_daily(user: User = Depends(get_current_user)):
    """Claim daily login reward and update streak"""
    result = await claim_daily_reward(user.user_id)
    return result

@api_router.get("/gamification/leaderboard")
async def leaderboard(limit: int = 20, user: User = Depends(get_current_user)):
    """Get XP leaderboard"""
    leaders = await get_leaderboard(limit)
    return {"leaderboard": leaders}

@api_router.get("/gamification/levels")
async def get_levels():
    """Get all level definitions (public endpoint)"""
    return {"levels": LEVELS}

@api_router.get("/gamification/achievement-definitions")
async def get_achievement_definitions():
    """Get all achievement definitions (public endpoint)"""
    return {"achievements": ACHIEVEMENTS}

@api_router.get("/gamification/xp-rewards")
async def get_xp_rewards():
    """Get XP reward values (public endpoint)"""
    return {"rewards": XP_REWARDS}

# ==================== OPENING REPERTOIRE ROUTES ====================

from opening_service import analyze_opening_repertoire

@api_router.get("/openings/repertoire")
async def get_opening_repertoire(user: User = Depends(get_current_user)):
    """
    Analyze user's opening repertoire from all their games.
    Returns detailed stats, problem areas, and personalized coaching.
    """
    result = await analyze_opening_repertoire(db, user.user_id)
    return result

# ==================== NOTIFICATIONS ROUTES ====================

@api_router.get("/notifications")
async def get_notifications(limit: int = 20, unread_only: bool = False, user: User = Depends(get_current_user)):
    """Get user's in-app notifications"""
    query = {"user_id": user.user_id}
    if unread_only:
        query["read"] = False
    
    notifications = await db.notifications.find(
        query,
        {"_id": 0}
    ).sort("created_at", -1).limit(limit).to_list(limit)
    
    # Count unread
    unread_count = await db.notifications.count_documents({"user_id": user.user_id, "read": False})
    
    return {
        "notifications": notifications,
        "unread_count": unread_count
    }

@api_router.post("/notifications/{notification_id}/read")
async def mark_notification_read(notification_id: str, user: User = Depends(get_current_user)):
    """Mark a notification as read"""
    result = await db.notifications.update_one(
        {"user_id": user.user_id, "notification_id": notification_id},
        {"$set": {"read": True}}
    )
    return {"success": result.modified_count > 0}

@api_router.post("/notifications/read-all")
async def mark_all_notifications_read(user: User = Depends(get_current_user)):
    """Mark all notifications as read"""
    result = await db.notifications.update_many(
        {"user_id": user.user_id, "read": False},
        {"$set": {"read": True}}
    )
    return {"success": True, "updated": result.modified_count}

# ==================== RAG MANAGEMENT ROUTES ====================

@api_router.post("/rag/process-games")
async def process_games_for_rag(background_tasks: BackgroundTasks, user: User = Depends(get_current_user)):
    """Process all user games to create RAG embeddings"""
    # Start processing in background
    background_tasks.add_task(process_user_games_for_rag, db, user.user_id, 100)
    
    return {
        "message": "RAG processing started in background",
        "status": "processing"
    }

@api_router.get("/rag/status")
async def get_rag_status(user: User = Depends(get_current_user)):
    """Get RAG processing status for user"""
    game_embeddings = await db.game_embeddings.count_documents({"user_id": user.user_id})
    pattern_embeddings = await db.pattern_embeddings.count_documents({"user_id": user.user_id})
    analysis_embeddings = await db.analysis_embeddings.count_documents({"user_id": user.user_id})
    total_games = await db.games.count_documents({"user_id": user.user_id})
    total_patterns = await db.mistake_patterns.count_documents({"user_id": user.user_id})
    total_analyses = await db.game_analyses.count_documents({"user_id": user.user_id})
    
    return {
        "total_games": total_games,
        "game_embeddings": game_embeddings,
        "total_patterns": total_patterns,
        "pattern_embeddings": pattern_embeddings,
        "total_analyses": total_analyses,
        "analysis_embeddings": analysis_embeddings,
        "rag_coverage": {
            "games": f"{(game_embeddings / max(total_games * 4, 1)) * 100:.1f}%",  # 4 chunks per game
            "patterns": f"{(pattern_embeddings / max(total_patterns, 1)) * 100:.1f}%",
            "analyses": f"{(analysis_embeddings / max(total_analyses, 1)) * 100:.1f}%"
        }
    }

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== BACKGROUND SYNC SCHEDULER ====================
import asyncio

# Global variable to track the background task
_background_sync_task = None
BACKGROUND_SYNC_INTERVAL_SECONDS = 6 * 60 * 60  # 6 hours

async def background_sync_loop():
    """
    Periodic background task to sync games for all users.
    Runs every 6 hours.
    """
    while True:
        try:
            logger.info("Starting background game sync...")
            synced_count = await run_background_sync(db)
            logger.info(f"Background sync completed: {synced_count} games synced")
        except Exception as e:
            logger.error(f"Background sync error: {e}")
        
        # Wait for next sync interval
        await asyncio.sleep(BACKGROUND_SYNC_INTERVAL_SECONDS)

@app.on_event("startup")
async def startup_event():
    """Start background tasks on app startup"""
    global _background_sync_task
    
    # Start the background sync loop
    _background_sync_task = asyncio.create_task(background_sync_loop())
    logger.info("Background sync scheduler started")

@app.on_event("shutdown")
async def shutdown_db_client():
    global _background_sync_task
    
    # Cancel background task
    if _background_sync_task:
        _background_sync_task.cancel()
        try:
            await _background_sync_task
        except asyncio.CancelledError:
            pass
    
    client.close()
