"""
Games Routes
============

Handles game import, listing, and basic operations.

Endpoints:
- POST /import-games - Import games from Chess.com/Lichess
- GET /games - List user's games  
- GET /games/analyzed - List analyzed games
- GET /games/{game_id} - Get single game details
- GET /games/{game_id}/analysis-status - Get analysis status
- POST /games/{game_id}/reanalyze - Re-run analysis on a game
- GET /games/blunders - Get all blunders
- GET /games/best-moves - Get all best moves
- POST /games/sync - Sync games from platforms
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone
import logging
import re

logger = logging.getLogger(__name__)

# Create router for games endpoints
router = APIRouter(prefix="/games", tags=["Games"])

# Database reference - will be set by server.py
db = None

def set_db(database):
    """Set the database reference for games routes"""
    global db
    db = database


# Import User model and get_current_user from auth routes
from routes.auth import User, get_current_user


# ==================== MODELS ====================

class ImportGamesRequest(BaseModel):
    platform: str  # "chess.com" or "lichess"
    username: str
    num_games: Optional[int] = 20


class SyncGamesRequest(BaseModel):
    platform: Optional[str] = None  # If None, sync all linked platforms


# ==================== ENDPOINTS ====================

@router.get("")
async def get_games(user: User = Depends(get_current_user)):
    """Get all games for the current user"""
    global db
    
    games = await db.games.find(
        {"user_id": user.user_id},
        {"_id": 0}
    ).sort("imported_at", -1).to_list(100)
    return games


@router.get("/analyzed")
async def get_analyzed_games(user: User = Depends(get_current_user)):
    """Get list of all analyzed games with summary stats"""
    global db
    
    games = await db.games.find(
        {"user_id": user.user_id, "is_analyzed": True},
        {"_id": 0, "game_id": 1, "result": 1, "user_color": 1, "user_result": 1,
         "white_player": 1, "black_player": 1, "platform": 1, "imported_at": 1}
    ).sort("imported_at", -1).to_list(50)
    
    result = []
    for game in games:
        # Get analysis for this game
        analysis = await db.game_analyses.find_one(
            {"game_id": game["game_id"]},
            {"_id": 0, "accuracy": 1, "blunders": 1, "mistakes": 1, "best_moves": 1, "stockfish_analysis": 1}
        )
        
        # Determine opponent
        user_color = game.get("user_color", "white")
        opponent = game.get("black_player") if user_color == "white" else game.get("white_player")
        
        # Get accuracy from stockfish_analysis if available
        accuracy = 0
        if analysis:
            sf = analysis.get("stockfish_analysis", {})
            accuracy = sf.get("accuracy", analysis.get("accuracy", 0))
        
        result.append({
            "game_id": game["game_id"],
            "opponent": opponent or "Unknown",
            "result": game.get("user_result", "unknown"),
            "accuracy": round(accuracy, 1) if accuracy else 0,
            "blunders": analysis.get("blunders", 0) if analysis else 0,
            "mistakes": analysis.get("mistakes", 0) if analysis else 0,
            "best_moves": analysis.get("best_moves", 0) if analysis else 0,
            "platform": game.get("platform", "chess.com")
        })
    
    return {"games": result, "total": len(result)}


@router.get("/blunders")
async def get_all_blunders(user: User = Depends(get_current_user)):
    """Get all blunders from user's games with position and explanation"""
    global db
    
    # Get all analyzed games
    analyses = await db.game_analyses.find(
        {"user_id": user.user_id},
        {"_id": 0, "game_id": 1, "commentary": 1, "stockfish_analysis": 1}
    ).to_list(100)
    
    blunders = []
    for analysis in analyses:
        commentary = analysis.get("commentary", [])
        sf_analysis = analysis.get("stockfish_analysis", {})
        move_evals = sf_analysis.get("move_evaluations", [])
        
        # Create a map of move_number to FEN
        fen_map = {m.get("move_number"): m.get("fen_before") for m in move_evals}
        
        for move in commentary:
            if move.get("evaluation") in ["blunder", "mistake"]:
                move_num = move.get("move_number")
                # Try to get FEN from stockfish data
                fen = fen_map.get(move_num, "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")
                
                blunders.append({
                    "game_id": analysis["game_id"],
                    "move_number": move_num,
                    "move": move.get("move"),
                    "evaluation": move.get("evaluation"),
                    "fen": fen,
                    "feedback": move.get("feedback", ""),
                    "consider": move.get("consider", ""),
                    "threat": move.get("details", {}).get("threat_line"),
                    "thinking_pattern": move.get("details", {}).get("thinking_pattern")
                })
    
    # Sort by most recent (game_id contains timestamp info)
    blunders.sort(key=lambda x: x["game_id"], reverse=True)
    
    return {"blunders": blunders[:50], "total": len(blunders)}


@router.get("/best-moves")
async def get_all_best_moves(user: User = Depends(get_current_user)):
    """Get all best/excellent moves from user's games"""
    global db
    
    # Get all analyzed games
    analyses = await db.game_analyses.find(
        {"user_id": user.user_id},
        {"_id": 0, "game_id": 1, "commentary": 1, "stockfish_analysis": 1}
    ).to_list(100)
    
    best_moves = []
    for analysis in analyses:
        commentary = analysis.get("commentary", [])
        sf_analysis = analysis.get("stockfish_analysis", {})
        move_evals = sf_analysis.get("move_evaluations", [])
        
        # Create a map of move_number to data
        move_data_map = {m.get("move_number"): m for m in move_evals}
        
        # First, check commentary for best/excellent/good
        for move in commentary:
            if move.get("evaluation") in ["best", "excellent", "good"]:
                move_num = move.get("move_number")
                move_data = move_data_map.get(move_num, {})
                fen = move_data.get("fen_before", "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")
                
                best_moves.append({
                    "game_id": analysis["game_id"],
                    "move_number": move_num,
                    "move": move.get("move"),
                    "evaluation": move.get("evaluation"),
                    "fen": fen,
                    "feedback": move.get("feedback", ""),
                    "intent": move.get("intent", "")
                })
        
        # Also check stockfish evaluations for moves with very low cp_loss (excellent moves)
        for move_data in move_evals:
            cp_loss = move_data.get("cp_loss", 100)
            eval_type = move_data.get("evaluation", "")
            if hasattr(eval_type, "value"):
                eval_type = eval_type.value
            
            # Moves with < 5 centipawn loss are excellent
            if cp_loss <= 5 and eval_type not in ["blunder", "mistake", "inaccuracy"]:
                move_num = move_data.get("move_number")
                # Avoid duplicates
                if not any(m["game_id"] == analysis["game_id"] and m["move_number"] == move_num for m in best_moves):
                    best_moves.append({
                        "game_id": analysis["game_id"],
                        "move_number": move_num,
                        "move": move_data.get("move", ""),
                        "evaluation": "excellent" if cp_loss == 0 else "good",
                        "fen": move_data.get("fen_before", ""),
                        "feedback": f"Perfect move with {cp_loss} centipawn loss",
                        "intent": ""
                    })
    
    # Sort and limit
    best_moves.sort(key=lambda x: (x["game_id"], x["move_number"]), reverse=True)
    
    return {"best_moves": best_moves[:50], "total": len(best_moves)}


@router.get("/{game_id}")
async def get_game(game_id: str, user: User = Depends(get_current_user)):
    """Get a specific game with player names and termination reason"""
    global db
    
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
        
        # Extract ratings from PGN
        white_elo_match = re.search(r'\[WhiteElo "(\d+)"\]', pgn)
        black_elo_match = re.search(r'\[BlackElo "(\d+)"\]', pgn)
        if white_elo_match:
            game["white_rating"] = int(white_elo_match.group(1))
        if black_elo_match:
            game["black_rating"] = int(black_elo_match.group(1))
        
        # Also try to extract termination from PGN if not stored
        if not game.get("termination") or game.get("termination") == "unknown":
            term_match = re.search(r'\[Termination "([^"]+)"\]', pgn)
            if term_match:
                game["termination"] = term_match.group(1).lower()
            elif pgn.rstrip().endswith("#"):
                game["termination"] = "checkmate"
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
    
    # Normalize termination to our standard values
    term_lower = termination.lower() if termination else ""
    normalized = termination
    if "time" in term_lower or "timeout" in term_lower:
        normalized = "timeout"
    elif term_lower in ("checkmate", "checkmated", "mate") or "checkmate" in term_lower:
        normalized = "checkmate"
    elif term_lower in ("resignation", "resigned") or "resign" in term_lower:
        normalized = "resignation"
    elif "abandon" in term_lower:
        normalized = "abandonment"
    elif term_lower in ("stalemate",):
        normalized = "stalemate"
    elif term_lower in ("draw_agreement", "draw_agreed", "agreed") or "agreement" in term_lower:
        normalized = "draw_agreement"
    elif term_lower in ("repetition",):
        normalized = "repetition"
    elif term_lower in ("insufficient", "insufficient_material"):
        normalized = "insufficient"
    game["termination"] = normalized

    is_draw = "1/2" in result
    termination_text = ""
    if normalized == "timeout":
        termination_text = "Lost on time" if not user_won and not is_draw else "Opponent lost on time"
    elif normalized == "resignation":
        termination_text = "Resigned" if not user_won and not is_draw else "Opponent resigned"
    elif normalized == "checkmate":
        termination_text = "Checkmated" if not user_won and not is_draw else "Won by checkmate"
    elif normalized == "abandonment":
        termination_text = "Game abandoned" if not user_won else "Opponent abandoned"
    elif normalized == "stalemate":
        termination_text = "Stalemate"
    elif normalized == "draw_agreement":
        termination_text = "Draw by agreement"
    elif normalized == "repetition":
        termination_text = "Draw by repetition"
    elif normalized == "insufficient":
        termination_text = "Insufficient material"

    game["termination_text"] = termination_text
    
    return game


@router.get("/{game_id}/analysis-status")
async def get_game_analysis_status(game_id: str, user: User = Depends(get_current_user)):
    """Get the current analysis status for a specific game"""
    global db
    
    game = await db.games.find_one(
        {"game_id": game_id, "user_id": user.user_id},
        {"_id": 0, "is_analyzed": 1, "analysis_status": 1}
    )
    
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    
    # Check queue for progress info
    queue_item = await db.analysis_queue.find_one(
        {"game_id": game_id},
        {"_id": 0, "status": 1, "created_at": 1, "queued_at": 1, "started_at": 1, "failed_at": 1, "retry_count": 1, "last_error": 1, "last_error_at": 1, "retrying": 1}
    )
    
    if game.get("is_analyzed"):
        return {"status": "analyzed"}
    
    if queue_item:
        return {
            "status": queue_item.get("status", "unknown"),
            "queued_at": queue_item.get("queued_at") or queue_item.get("created_at"),
            "started_at": queue_item.get("started_at"),
            "failed_at": queue_item.get("failed_at"),
            "retry_count": queue_item.get("retry_count", 0),
            "last_error": queue_item.get("last_error"),
            "last_error_at": queue_item.get("last_error_at"),
            "retrying": queue_item.get("retrying", False),
        }
    
    return {"status": "not_analyzed"}


@router.post("/{game_id}/reanalyze")
async def reanalyze_game(
    game_id: str,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user)
):
    """
    Queue a game for re-analysis. This is for games that were imported
    but not properly analyzed.
    """
    global db
    
    # Verify game exists and belongs to user
    game = await db.games.find_one(
        {"game_id": game_id, "user_id": user.user_id},
        {"_id": 0}
    )
    
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    
    # Check if already in queue
    existing_queue = await db.analysis_queue.find_one(
        {"game_id": game_id, "status": {"$in": ["pending", "processing"]}}
    )
    
    if existing_queue:
        return {
            "success": True,
            "status": "already_queued",
            "message": "Game is already queued for analysis"
        }
    
    # Add to queue (or update existing entry)
    queue_item = {
        "game_id": game_id,
        "user_id": user.user_id,
        "status": "pending",
        "queued_at": datetime.now(timezone.utc),
        "priority": 1,  # User-requested re-analysis gets priority
        "retry_count": 0,
        "last_error": None,
        "last_error_at": None,
        "retrying": False,
        "started_at": None,
        "last_heartbeat": None,
    }
    
    # Use upsert to avoid duplicate entries - update existing or create new
    await db.analysis_queue.update_one(
        {"game_id": game_id, "user_id": user.user_id},
        {"$set": queue_item},
        upsert=True
    )
    
    # Update game status - set is_analyzed to False so it shows in queue
    await db.games.update_one(
        {"game_id": game_id},
        {"$set": {"analysis_status": "queued", "is_analyzed": False, "analysis_error": None}}
    )
    
    # NOTE: Analysis is now handled by the separate analysis_worker.py process
    # The worker polls the analysis_queue collection and processes pending jobs
    # This keeps the web server fast and responsive
    
    logger.info(f"Game {game_id} queued for analysis (worker will process)")
    
    return {
        "success": True,
        "status": "queued",
        "message": "Game queued for analysis. The analysis worker will process it shortly."
    }



@router.post("/{game_id}/regenerate-coaching")
async def regenerate_coaching(
    game_id: str,
    user: User = Depends(get_current_user)
):
    """
    Regenerate V5 coaching narratives for a game.
    Clears cached V5 decryption data so it regenerates with latest logic.
    Does NOT re-run Stockfish — just the coaching layer.
    """
    global db
    
    # Verify game belongs to user
    game = await db.games.find_one(
        {"game_id": game_id, "user_id": user.user_id},
        {"_id": 0, "game_id": 1}
    )
    
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    
    # Clear V5 coaching cache from game_analysis
    result = await db.game_analysis.update_one(
        {"game_id": game_id},
        {"$unset": {
            "decryption_v5_data": "",
            "decryption_v5_generating": "",
            "decryption_generated_at": ""
        }}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="No analysis found for this game")
    
    logger.info(f"Cleared V5 coaching cache for game {game_id} — will regenerate on next view")
    
    return {
        "success": True,
        "message": "Coaching cleared. Open the game in The Lab to regenerate with improved logic."
    }
