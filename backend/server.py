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
async def analyze_game(req: AnalyzeGameRequest, background_tasks: BackgroundTasks, user: User = Depends(get_current_user)):
    """Analyze a game with AI coaching using PlayerProfile + RAG + Strict Explanation Contract"""
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
    if existing_analysis:
        return existing_analysis
    
    # Step 1: Get or create PlayerProfile (FIRST-CLASS requirement)
    logger.info(f"Loading PlayerProfile for user {user.user_id}")
    profile = await get_or_create_profile(db, user.user_id, user.name)
    profile_context = build_profile_context_for_prompt(profile)
    
    # Step 2: Build RAG context (SUPPORTS memory, doesn't define habits)
    logger.info(f"Building RAG context for game {req.game_id}")
    rag_context = await build_rag_context(db, user.user_id, game)
    
    # Step 3: Get strict explanation contract
    explanation_contract = build_explanation_prompt_contract()
    
    # Step 4: Build the coaching prompt with all context
    learning_style = profile.get("learning_style", "concise")
    coaching_tone = profile.get("coaching_tone", "encouraging")
    
    # Get user's first name for personal touch
    first_name = user.name.split()[0] if user.name else "friend"
    
    system_prompt = f"""You are a warm, wise chess coach - think of yourself like a supportive mentor who genuinely cares about {first_name}'s improvement.
They played as {game['user_color']} in this game.

{profile_context}

=== HISTORICAL CONTEXT (via RAG) ===
{rag_context}

=== YOUR COACHING PERSONALITY ===
- You speak like a human mentor, not a chess engine
- You understand what the player was TRYING to do, even when it didn't work
- You never make them feel stupid - instead, you show them they had the right idea but missed one detail
- You build their confidence by highlighting good intentions
- You use phrases like "I see what you were going for here...", "Good instinct to...", "The idea was right, but..."
- You connect mistakes to learnable patterns, not random blunders
- You occasionally ask rhetorical questions to make them think: "What if the knight wasn't protecting that square?"

=== PREDEFINED WEAKNESS CATEGORIES (USE ONLY THESE) ===
Tactical: one_move_blunders, pin_blindness, fork_misses, skewer_blindness, back_rank_weakness, discovered_attack_misses, removal_of_defender_misses
Strategic: center_control_neglect, poor_piece_activity, lack_of_plan, pawn_structure_damage, weak_square_creation, piece_coordination_issues  
King Safety: delayed_castling, exposing_own_king, king_walk_blunders, ignoring_king_safety_threats
Opening Principles: premature_queen_moves, neglecting_development, moving_same_piece_twice, ignoring_center_control, not_castling_early
Endgame Fundamentals: king_activity_neglect, pawn_race_errors, opposition_misunderstanding, rook_endgame_errors, stalemate_blunders
Psychological: impulsive_moves, tunnel_vision, hope_chess, time_trouble_blunders, resignation_too_early, overconfidence

=== OUTPUT FORMAT (STRICT JSON) ===
{{
    "commentary": [
        {{
            "move_number": 5,
            "move": "h6",
            "evaluation": "inaccuracy",
            "player_intention": "What was the player likely trying to do with this move",
            "coach_response": "A warm, conversational explanation (2-3 sentences) that acknowledges their intention but explains what went wrong. End with a question or insight.",
            "better_move": "Nf6 - developing while defending",
            "explanation": {{
                "thinking_error": "Defensive reflex when attack was available",
                "why_it_happened": "Saw the bishop eyeing g7 and reacted, but didn't check if there was a forcing move first",
                "what_to_focus_on_next_time": "Before playing a defensive pawn move, spend 5 seconds looking for checks or captures",
                "one_repeatable_rule": "Checks and captures before quiet moves"
            }}
        }}
    ],
    "blunders": 0,
    "mistakes": 0,
    "inaccuracies": 0,
    "best_moves": 0,
    "overall_summary": "A 3-4 sentence summary that sounds like a coach talking after the game. Start with what they did WELL, then gently mention the key learning point. End with encouragement for next time.",
    "identified_weaknesses": [
        {{
            "category": "tactical",
            "subcategory": "pin_blindness", 
            "description": "Human-readable description: what happened and why it matters",
            "advice": "One specific thing to practice"
        }}
    ],
    "identified_strengths": [
        {{
            "category": "tactical",
            "subcategory": "fork_awareness",
            "description": "What they did well"
        }}
    ],
    "key_lesson": "The ONE thing to remember from this game (make it memorable)",
    "voice_script_summary": "A 30-second speakable summary for voice coaching"
}}

=== CRITICAL RULES ===
1. Focus ONLY on critical moments (blunders, mistakes, brilliant moves) - not every move
2. For each mistake, ALWAYS include player_intention to show you understand what they were trying to do
3. coach_response must be warm and conversational, not clinical
4. Use ONLY predefined weakness categories - map to closest match
5. NO move lists (1.e4 e5 2.Nf3...) in explanations
6. NO engine language (centipawns, eval, +0.5)
7. overall_summary MUST start with something positive
8. key_lesson should be catchy and memorable

Current player's top weaknesses to watch for: {[w.get('subcategory', '').replace('_', ' ') for w in profile.get('top_weaknesses', [])[:3]]}

Evaluations: "blunder", "mistake", "inaccuracy", "good", "excellent", "brilliant", "neutral"
"""

    try:
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"analysis_{req.game_id}",
            system_message=system_prompt
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
        
        analysis_data = json.loads(response_clean)
        
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
        
        analysis = GameAnalysis(
            game_id=req.game_id,
            user_id=user.user_id,
            commentary=validated_commentary,
            blunders=analysis_data.get("blunders", 0),
            mistakes=analysis_data.get("mistakes", 0),
            inaccuracies=analysis_data.get("inaccuracies", 0),
            best_moves=analysis_data.get("best_moves", 0),
            overall_summary=analysis_data.get("overall_summary", ""),
            identified_patterns=[]  # Legacy field - will also store full data separately
        )
        
        # Store voice script and key lesson for future use
        voice_script = analysis_data.get("voice_script_summary", "")
        key_lesson = analysis_data.get("key_lesson", "")
        
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
        # Store full weakness data for frontend display
        analysis_doc['weaknesses'] = categorized_weaknesses  # NEW: Full data, not just IDs
        analysis_doc['strengths'] = analysis_data.get("identified_strengths", [])
        analysis_doc['key_lesson'] = key_lesson
        analysis_doc['voice_script_summary'] = voice_script
        await db.game_analyses.insert_one(analysis_doc)
        
        await db.games.update_one(
            {"game_id": req.game_id},
            {"$set": {"is_analyzed": True}}
        )
        
        # Remove _id before returning
        analysis_doc.pop('_id', None)
        
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

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
