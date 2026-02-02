from fastapi import FastAPI, APIRouter, HTTPException, Request, Response, Depends
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
    """Get a specific game"""
    game = await db.games.find_one(
        {"game_id": game_id, "user_id": user.user_id},
        {"_id": 0}
    )
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
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
async def analyze_game(req: AnalyzeGameRequest, user: User = Depends(get_current_user)):
    """Analyze a game with AI coaching"""
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    
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
    if existing_analysis:
        return existing_analysis
    
    mistake_context = await get_user_mistake_context(user.user_id)
    
    system_prompt = f"""You are a friendly, experienced chess coach who speaks like a human mentor, not a computer.
Your student is {user.name}. They played as {game['user_color']} in this game.

{mistake_context}

Your coaching style:
- Be conversational and encouraging, like a supportive coach
- Reference their past mistakes naturally: "Remember how we talked about watching for pins? Here's another example..."
- Use simple language, avoid engine-speak like "0.3 advantage"
- Focus on patterns they can learn, not just "this was bad"
- If they made the same type of mistake before, gently remind them
- Celebrate good moves genuinely
- Keep commentary concise but insightful

Analyze the game and provide:
1. A list of move-by-move commentary (focus on critical moments, not every move)
2. Count of blunders, mistakes, inaccuracies, and best moves
3. An overall summary (2-3 sentences) that sounds like a coach talking to them
4. Identify any mistake patterns (categories: tactical, positional, endgame, opening, time_management; 
   subcategories: pinning, forks, center_control, one_move_blunder, piece_activity, king_safety, pawn_structure, etc.)

Respond in JSON format:
{{
    "commentary": [
        {{"move_number": 1, "move": "e4", "comment": "...", "evaluation": "neutral"}},
        ...
    ],
    "blunders": 0,
    "mistakes": 0,
    "inaccuracies": 0,
    "best_moves": 0,
    "overall_summary": "...",
    "identified_patterns": [
        {{"category": "tactical", "subcategory": "pinning", "description": "..."}}
    ]
}}

Evaluations can be: "blunder", "mistake", "inaccuracy", "good", "excellent", "brilliant", "neutral"
"""

    try:
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"analysis_{req.game_id}",
            system_message=system_prompt
        ).with_model("openai", "gpt-5.2")
        
        user_message = UserMessage(text=f"Please analyze this game:\n\n{game['pgn']}")
        response = await chat.send_message(user_message)
        
        import json
        response_clean = response.strip()
        if response_clean.startswith("```json"):
            response_clean = response_clean[7:]
        if response_clean.startswith("```"):
            response_clean = response_clean[3:]
        if response_clean.endswith("```"):
            response_clean = response_clean[:-3]
        
        analysis_data = json.loads(response_clean)
        
        analysis = GameAnalysis(
            game_id=req.game_id,
            user_id=user.user_id,
            commentary=analysis_data.get("commentary", []),
            blunders=analysis_data.get("blunders", 0),
            mistakes=analysis_data.get("mistakes", 0),
            inaccuracies=analysis_data.get("inaccuracies", 0),
            best_moves=analysis_data.get("best_moves", 0),
            overall_summary=analysis_data.get("overall_summary", ""),
            identified_patterns=[]
        )
        
        for pattern_data in analysis_data.get("identified_patterns", []):
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
                analysis.identified_patterns.append(new_pattern.pattern_id)
        
        analysis_doc = analysis.model_dump()
        analysis_doc['created_at'] = analysis_doc['created_at'].isoformat()
        await db.game_analyses.insert_one(analysis_doc)
        
        await db.games.update_one(
            {"game_id": req.game_id},
            {"$set": {"is_analyzed": True}}
        )
        
        return analysis_doc
        
    except Exception as e:
        logger.error(f"Analysis error: {e}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

@api_router.get("/analysis/{game_id}")
async def get_analysis(game_id: str, user: User = Depends(get_current_user)):
    """Get analysis for a specific game"""
    analysis = await db.game_analyses.find_one(
        {"game_id": game_id, "user_id": user.user_id},
        {"_id": 0}
    )
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return analysis

# ==================== WEAKNESS/PATTERN ROUTES ====================

@api_router.get("/patterns")
async def get_patterns(user: User = Depends(get_current_user)):
    """Get all mistake patterns for the current user"""
    patterns = await db.mistake_patterns.find(
        {"user_id": user.user_id},
        {"_id": 0}
    ).sort("occurrences", -1).to_list(50)
    return patterns

@api_router.get("/dashboard-stats")
async def get_dashboard_stats(user: User = Depends(get_current_user)):
    """Get dashboard statistics for the current user"""
    total_games = await db.games.count_documents({"user_id": user.user_id})
    analyzed_games = await db.games.count_documents({"user_id": user.user_id, "is_analyzed": True})
    
    patterns = await db.mistake_patterns.find(
        {"user_id": user.user_id},
        {"_id": 0}
    ).sort("occurrences", -1).to_list(5)
    
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
    
    return {
        "total_games": total_games,
        "analyzed_games": analyzed_games,
        "top_patterns": patterns,
        "recent_games": recent_games,
        "stats": {
            "total_blunders": total_blunders,
            "total_mistakes": total_mistakes,
            "total_best_moves": total_best_moves
        }
    }

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

# ==================== BASIC ROUTES ====================

@api_router.get("/")
async def root():
    return {"message": "Chess Coach API"}

@api_router.get("/health")
async def health():
    return {"status": "healthy"}

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
