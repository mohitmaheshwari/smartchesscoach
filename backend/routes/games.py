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
from services.access_scope import user_scope_filter
from db_filters import ACTIVE_GAMES_FILTER


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
    """Get all games for the current user (or all users if reviewer)."""
    global db

    games = await db.games.find(
        {**user_scope_filter(user), **ACTIVE_GAMES_FILTER},
        {"_id": 0}
    ).sort("imported_at", -1).to_list(200 if user.is_reviewer else 100)
    return games


@router.get("/analyzed")
async def get_analyzed_games(user: User = Depends(get_current_user)):
    """Get list of all analyzed games with summary stats."""
    global db

    games = await db.games.find(
        {"is_analyzed": True, **user_scope_filter(user), **ACTIVE_GAMES_FILTER},
        {"_id": 0, "game_id": 1, "result": 1, "user_color": 1, "user_result": 1,
         "white_player": 1, "black_player": 1, "platform": 1, "imported_at": 1,
         "user_id": 1}
    ).sort("imported_at", -1).to_list(200 if user.is_reviewer else 50)
    
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
            "platform": game.get("platform", "chess.com"),
            # Surface owner_user_id so the frontend can label cross-user
            # games when a reviewer is browsing.
            "owner_user_id": game.get("user_id"),
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
        {"game_id": game_id, **user_scope_filter(user)},
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
        {"game_id": game_id, **user_scope_filter(user)},
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
        {"game_id": game_id, **user_scope_filter(user)},
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
        {"game_id": game_id, **user_scope_filter(user)},
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
        {"game_id": game_id, **user_scope_filter(user)},
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


@router.get("/{game_id}/coach-review")
async def get_game_coach_review(game_id: str, user: User = Depends(get_current_user)):
    """
    Comprehensive game review using the coaching engine.
    Replaces V5 narratives with: fundamentals, phase analysis, opening awareness, position commentary.
    """
    import chess

    game = await db.games.find_one(
        {"game_id": game_id, **user_scope_filter(user)}, {"_id": 0}
    )
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    analysis = await db.game_analyses.find_one(
        {"game_id": game_id}, {"_id": 0}
    )
    if not analysis:
        raise HTTPException(status_code=404, detail="Game not analyzed yet")

    user_color = game.get("user_color", "white")
    evals = analysis.get("stockfish_analysis", {}).get("move_evaluations", [])
    opening_name = game.get("opening", "")

    result = {
        "game_id": game_id,
        "opening": opening_name,
        "user_color": user_color,
        "result": game.get("result", ""),
    }

    # ─── 1. PHASE ANALYSIS ───
    try:
        total_user_moves = len([e for e in evals if True])  # all moves
        opening_evals = [e for e in evals if (e.get("move_number", 0) or 0) <= 12]
        middle_evals = [e for e in evals if 12 < (e.get("move_number", 0) or 0) <= 30]
        end_evals = [e for e in evals if (e.get("move_number", 0) or 0) > 30]

        def _phase_stats(move_evals, name):
            if not move_evals:
                return None
            bl = sum(1 for e in move_evals if (e.get("cp_loss", 0) or 0) >= 300)
            ms = sum(1 for e in move_evals if 100 <= (e.get("cp_loss", 0) or 0) < 300)
            total = len(move_evals)
            acc = round(max(0, (1 - (bl + ms) / total)) * 100) if total > 0 else 0
            return {
                "name": name, "moves": total, "blunders": bl, "mistakes": ms,
                "accuracy": acc,
                "verdict": "Clean" if bl == 0 and ms == 0
                    else f"{bl} blunder{'s' if bl != 1 else ''}" if bl > 0
                    else f"{ms} inaccurac{'ies' if ms != 1 else 'y'}",
            }

        result["phases"] = {
            "opening": _phase_stats(opening_evals, "Opening"),
            "middlegame": _phase_stats(middle_evals, "Middlegame"),
            "endgame": _phase_stats(end_evals, "Endgame"),
        }
    except Exception as e:
        logger.warning(f"Phase analysis failed: {e}")

    # ─── 2. OPENING AWARENESS ───
    try:
        from services.opening_mastery_tracker import OPENING_MOVE_IDEAS, OPENING_BRANCH_DATA
        from services.verified_opening_traps import get_all_for_opening

        # Match opening name to key
        opening_key = None
        for key in OPENING_MOVE_IDEAS:
            name = key.replace("_", " ")
            if name in opening_name.lower() or opening_name.lower().replace("'", "").replace("'", "") in name:
                opening_key = key
                break

        opening_info = None
        if opening_key:
            ideas = OPENING_MOVE_IDEAS.get(opening_key, [])

            # Find where user deviated from theory
            deviation_move = None
            moves_in_theory = 0
            pgn = game.get("pgn", "")
            if pgn:
                # Extract moves from PGN
                import re as _re
                move_text = _re.sub(r'\{[^}]*\}', '', pgn)  # Remove comments
                move_text = _re.sub(r'\[.*?\]\s*', '', move_text)  # Remove headers
                move_text = _re.sub(r'\d+\.+\s*', '', move_text)  # Remove move numbers
                game_moves = [m.strip() for m in move_text.split() if m.strip() and m.strip() not in ("1-0", "0-1", "1/2-1/2", "*")]

                for i, idea in enumerate(ideas):
                    if i >= len(game_moves):
                        break
                    played = game_moves[i].replace("+", "").replace("#", "").lower()
                    expected = idea["move"].replace("+", "").replace("#", "").lower()
                    if played == expected:
                        moves_in_theory += 1
                    else:
                        deviation_move = {
                            "ply": i,
                            "played": game_moves[i],
                            "expected": idea["move"],
                            "idea": idea.get("idea", ""),
                        }
                        break

            # Branch info
            branch_data = None
            if opening_key in OPENING_BRANCH_DATA:
                bd = OPENING_BRANCH_DATA[opening_key]
                branch_data = {
                    "branch_point": bd["branch_point"],
                    "branches": [{"name": v["name"], "branch_move": v["branch_move"]}
                                 for v in bd["branches"].values()],
                }

            # Traps — check if setup was reached AND if trap was sprung
            traps_matched = []
            traps = get_all_for_opening(opening_key)
            if traps and pgn:
                for trap in traps:
                    setup = trap.setup_moves
                    full_line = trap.full_line

                    # Check if game moves match the setup
                    if len(game_moves) < len(setup):
                        continue
                    setup_match = all(
                        game_moves[j].replace("+", "").replace("#", "").lower() ==
                        setup[j].replace("+", "").replace("#", "").lower()
                        for j in range(len(setup))
                    )
                    if not setup_match:
                        continue

                    # Setup was reached — now check if the trap was sprung
                    # The trap_move is the key move AFTER the setup
                    trap_sprung = False
                    trap_avoided = False
                    if len(full_line) > len(setup) and len(game_moves) > len(setup):
                        # The move after setup in the full line is the trap move
                        expected_trap = full_line[len(setup)].replace("+", "").replace("#", "").lower()
                        actual_played = game_moves[len(setup)].replace("+", "").replace("#", "").lower()
                        if actual_played == expected_trap:
                            trap_sprung = True
                        else:
                            trap_avoided = True
                    elif len(game_moves) == len(setup):
                        # Game reached the setup but stopped — trap was set up but not yet sprung
                        pass

                    # Who was the victim?
                    victim_is_user = trap.victim_color == user_color
                    trap_for_user = trap.trap_for == user_color

                    trap_entry = {
                        "name": trap.name,
                        "explanation": trap.explanation,
                        "refutation": trap.refutation,
                        "trap_move": trap.trap_move,
                        "victim_color": trap.victim_color,
                        "sprung": trap_sprung,
                        "avoided": trap_avoided,
                    }

                    if trap_sprung and victim_is_user:
                        trap_entry["story"] = f"You fell into the {trap.name}. {trap.refutation}"
                    elif trap_sprung and trap_for_user:
                        trap_entry["story"] = f"You played the {trap.name} and it worked!"
                    elif trap_avoided and victim_is_user:
                        trap_entry["story"] = f"You avoided the {trap.name}. Good awareness."
                    elif trap_avoided and trap_for_user:
                        trap_entry["story"] = f"You set up the {trap.name} but your opponent didn't fall for it."
                    else:
                        trap_entry["story"] = f"The {trap.name} position was reached in this game."

                    traps_matched.append(trap_entry)

            opening_info = {
                "key": opening_key,
                "name": opening_name,
                "moves_in_theory": moves_in_theory,
                "total_theory_moves": len(ideas),
                "deviation": deviation_move,
                "branches": branch_data,
                "traps": traps_matched,
            }

        result["opening_analysis"] = opening_info
    except Exception as e:
        logger.warning(f"Opening awareness failed: {e}")

    # ─── 3. KEY MOMENTS WITH POSITION COMMENTARY ───
    try:
        from services.position_intelligence import read_board_like_a_coach

        key_moments = []
        for e in evals:
            cp_loss = e.get("cp_loss", 0) or 0
            if cp_loss < 100:
                continue  # Only show mistakes/blunders

            fen = e.get("fen_before", "")
            if not fen:
                continue

            # Position commentary for this moment. Pass best_move_san so
            # the commentary can't advertise a capture the best move
            # never makes (Mohit's h2-pawn misfire across Qf3+, Qxd1+,
            # Qxh2 — 2026-05-19).
            commentary = None
            try:
                commentary = read_board_like_a_coach(
                    fen, user_color, 1200,
                    best_move_san=e.get("best_move") or None,
                )
            except Exception:
                pass

            moment = {
                "move_number": e.get("move_number"),
                "move": e.get("move", ""),
                "best_move": e.get("best_move", ""),
                # fen is the position BEFORE the mistake — needed so the
                # frontend can drop the user into interactive solve mode
                # for this exact moment.
                "fen": fen,
                "pv_after_best": e.get("pv_after_best") or [],
                "cp_loss": cp_loss,
                "severity": "blunder" if cp_loss >= 300 else "mistake",
                "phase": "opening" if (e.get("move_number", 0) or 0) <= 12
                    else "endgame" if (e.get("move_number", 0) or 0) > 30
                    else "middlegame",
                "cognitive_gap": e.get("cognitive_gap", ""),
                "commentary": {
                    "summary": commentary.get("summary", "") if commentary else "",
                    "plan": commentary.get("plan", "") if commentary else "",
                    "observations": commentary.get("observations", [])[:3] if commentary else [],
                } if commentary else None,
            }
            key_moments.append(moment)

        # Sort by cp_loss, take top 5
        key_moments.sort(key=lambda m: -m["cp_loss"])
        result["key_moments"] = key_moments[:5]
    except Exception as e:
        logger.warning(f"Key moments failed: {e}")

    # ─── 4. FUNDAMENTALS SNAPSHOT (at key moments) ───
    try:
        from services.fundamentals_evaluator import evaluate_fundamentals

        # Build move history from evals
        move_history = []
        for e in evals:
            move_history.append({
                "move": e.get("move", ""),
                "by": "player" if e.get("is_user_move", True) else "coach",
                "fen_before": e.get("fen_before", ""),
                "fen_after": e.get("fen_after", ""),
                "eval_before": (e.get("eval_before", 0) or 0) / 100 if e.get("eval_before") else None,
                "eval_after": (e.get("eval_after", 0) or 0) / 100 if e.get("eval_after") else None,
            })

        # Evaluate at the end of each phase
        phase_fundamentals = {}
        for phase_name, phase_evals in [("opening", opening_evals), ("middlegame", middle_evals), ("endgame", end_evals)]:
            if not phase_evals:
                continue
            last_eval = phase_evals[-1]
            fen = last_eval.get("fen_after") or last_eval.get("fen_before", "")
            if fen:
                try:
                    board = chess.Board(fen)
                    # Use moves up to this point
                    phase_end_idx = evals.index(last_eval) + 1
                    partial_history = move_history[:phase_end_idx]
                    fund = evaluate_fundamentals(board, partial_history, user_color)
                    # Only include non-perfect fundamentals (interesting ones)
                    interesting = [f for f in fund.get("fundamentals", []) if f.get("progress", 100) < 100]
                    phase_fundamentals[phase_name] = interesting[:4]
                except Exception:
                    pass

        result["fundamentals"] = phase_fundamentals
    except Exception as e:
        logger.warning(f"Fundamentals failed: {e}")

    # ─── 5. BEHAVIORAL SUMMARY ───
    try:
        # Count behavior patterns
        gap_counts = {}
        for e in evals:
            gap = e.get("cognitive_gap", "")
            if gap and (e.get("cp_loss", 0) or 0) >= 80:
                gap_counts[gap] = gap_counts.get(gap, 0) + 1

        BEHAVIOR_LABELS = {
            "ignore_threat": "Missed opponent's threats",
            "piece_safety": "Left pieces undefended",
            "calculation_depth": "Didn't calculate deep enough",
            "missed_tactic": "Missed winning tactics",
            "tactical_oversight": "Didn't check opponent's reply",
            "king_safety": "King safety neglected",
        }

        behaviors = []
        for gap, count in sorted(gap_counts.items(), key=lambda x: -x[1]):
            behaviors.append({
                "behavior": gap,
                "label": BEHAVIOR_LABELS.get(gap, gap.replace("_", " ").title()),
                "count": count,
            })

        result["behaviors"] = behaviors[:3]
    except Exception as e:
        logger.warning(f"Behavioral summary failed: {e}")

    # ─── 6. PATTERN CONTEXT (cross-game) ───
    try:
        # How many times has the top behavior occurred across recent games?
        if result.get("behaviors"):
            top_behavior = result["behaviors"][0]["behavior"]
            recent_games = await db.game_analyses.find(
                {"user_id": user.user_id},
                {"_id": 0, "game_id": 1, "stockfish_analysis.move_evaluations.cognitive_gap": 1,
                 "stockfish_analysis.move_evaluations.cp_loss": 1}
            ).sort("created_at", -1).limit(20).to_list(20)

            games_with_pattern = 0
            games_without = 0
            recent_clean_streak = 0
            for rg in recent_games:
                rg_evals = rg.get("stockfish_analysis", {}).get("move_evaluations", [])
                has_pattern = any(
                    e.get("cognitive_gap") == top_behavior and (e.get("cp_loss", 0) or 0) >= 100
                    for e in rg_evals
                )
                if has_pattern:
                    games_with_pattern += 1
                    if games_without == recent_clean_streak:
                        recent_clean_streak = games_without
                    games_without = 0
                else:
                    games_without += 1

            result["pattern_context"] = {
                "behavior": top_behavior,
                "label": result["behaviors"][0]["label"],
                "games_with": games_with_pattern,
                "games_checked": len(recent_games),
                "recent_clean_streak": recent_clean_streak,
                "is_recurring": games_with_pattern >= 3,
                "is_improving": recent_clean_streak >= 2,
            }
    except Exception as e:
        logger.warning(f"Pattern context failed: {e}")

    # ─── 7. COACHING SESSION DATA (for guided review) ───
    try:
        # Get the user's focus rule
        from services.focus_engine import get_user_focus, FOCUS_RULES
        focus = await get_user_focus(db, user.user_id)

        # Determine which rule to show for the top behavior
        behavior_key = result.get("behaviors", [{}])[0].get("behavior", "") if result.get("behaviors") else ""
        BEHAVIOR_TO_CLUSTER = {
            "calculation_depth": "calculation", "tactical_oversight": "calculation",
            "ignore_threat": "threat_awareness", "piece_safety": "threat_awareness",
            "positional_misread": "planning",
        }
        cluster = BEHAVIOR_TO_CLUSTER.get(behavior_key, "calculation")
        rule_config = FOCUS_RULES.get(cluster, FOCUS_RULES.get("calculation", {}))

        # Phase-specific opening text
        phases = result.get("phases", {})
        opening_p = phases.get("opening")
        middle_p = phases.get("middlegame")
        endgame_p = phases.get("endgame")

        if opening_p and opening_p.get("accuracy", 100) < 60:
            phase_story = "The game went wrong early — your opening had problems."
        elif middle_p and middle_p.get("accuracy", 100) < 50:
            phase_story = "Your opening was fine, but the middlegame is where it fell apart."
        elif endgame_p and endgame_p.get("accuracy", 100) < 50:
            phase_story = "You played well until the endgame, then it collapsed."
        elif opening_p and opening_p.get("accuracy", 0) >= 80 and middle_p and middle_p.get("accuracy", 0) >= 80:
            phase_story = "You played well throughout. Clean game."
        else:
            phase_story = "A game with some key lessons."

        # Get the primary moment for interactive play
        primary_moment = None
        if result.get("key_moments"):
            pm = result["key_moments"][0]
            primary_moment = {
                "fen": pm.get("fen_before") if pm.get("fen_before") else None,
                "move_number": pm.get("move_number"),
                "your_move": pm.get("move"),
                "best_move": pm.get("best_move"),
                "threat": None,
                "phase": pm.get("phase"),
                "commentary": pm.get("commentary", {}).get("summary", ""),
            }
            # Find the threat from the eval data
            for e in evals:
                if e.get("move_number") == pm.get("move_number") and e.get("move") == pm.get("move"):
                    primary_moment["threat"] = e.get("threat", "")
                    break

        result["session"] = {
            "phase_story": phase_story,
            "primary_moment": primary_moment,
            "rule": rule_config.get("rule", "Think before you move."),
            "rule_name": rule_config.get("name", ""),
            "focus_cluster": cluster,
            "game_result": game.get("result", ""),
            "opponent": (game.get("white_player") if user_color == "black" else game.get("black_player")) or "Opponent",
            "opening_name": opening_name,
        }
    except Exception as e:
        logger.warning(f"Session data failed: {e}")

    return result


@router.get("/{game_id}/pattern-misses")
async def get_game_pattern_misses(
    game_id: str, user: User = Depends(get_current_user)
):
    """v72 (2026-05-23) — Per-game pattern-miss list for the Review UI.
    Reads the user_pattern_events collection filtered to (user, game),
    groups by pattern_id, and decorates each with human_name + family
    from the catalog. UI surface: "Patterns missed in this game."
    """
    from services.pattern_catalog import get_pattern

    # Ensure the game belongs to the requesting user (scope filter).
    game = await db.games.find_one(
        {"game_id": game_id, **user_scope_filter(user)}, {"_id": 0, "user_id": 1}
    )
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    # v73 (2026-05-23): also breaks out hits via outcome=="hit". Per-
    # game view shows both so the user sees "you hit the queen-fork
    # pattern on m12 but missed it on m18" instead of only misses.
    pipeline = [
        {"$match": {"user_id": user.user_id, "game_id": game_id}},
        {"$group": {
            "_id": "$pattern_id",
            "hit_count":  {"$sum": {"$cond": [{"$eq": ["$outcome", "hit"]},  1, 0]}},
            "miss_count": {"$sum": {"$cond": [{"$eq": ["$outcome", "miss"]}, 1, 0]}},
            "moves": {"$push": {
                "move_number":   "$move_number",
                "move_san":      "$move_san",
                "best_move_san": "$best_move_san",
                "cp_loss":       "$cp_loss",
                "outcome":       "$outcome",
            }},
        }},
        {"$sort": {"miss_count": -1, "hit_count": -1}},
    ]

    patterns = []
    async for row in db.user_pattern_events.aggregate(pipeline):
        pid = row.get("_id") or ""
        cat = get_pattern(pid) or {}
        patterns.append({
            "pattern_id": pid,
            "human_name": cat.get("human_name") or pid,
            "short_description": cat.get("short_description"),
            "family": cat.get("family"),
            "hit_count":  int(row.get("hit_count") or 0),
            "miss_count": int(row.get("miss_count") or 0),
            "moves": row.get("moves") or [],
        })

    return {
        "game_id": game_id,
        "patterns": patterns,
        "total_hits":   sum(p["hit_count"]  for p in patterns),
        "total_misses": sum(p["miss_count"] for p in patterns),
    }


@router.get("/{game_id}/board-summary")
async def get_game_board_summary(
    game_id: str, user: User = Depends(get_current_user)
):
    """Game-wide board-state trends for the Review section (P5 — Mohit
    2026-05-23). Runs the per-move board_state_describer across every
    user position in decryption_v5_data and surfaces patterns that
    persisted across multiple moves ("opponent had pieces aimed at
    your king across 8 moves") — insights the user cannot get from
    any single-position caption.

    Returns: {user_move_count, trends: [{fact_id, label, ...}]}.
    """
    game = await db.games.find_one(
        {"game_id": game_id, **user_scope_filter(user)}, {"_id": 0, "user_color": 1}
    )
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    analysis = await db.game_analyses.find_one(
        {"game_id": game_id}, {"_id": 0, "decryption_v5_data": 1}
    )
    if not analysis:
        raise HTTPException(status_code=404, detail="Game not analyzed yet")

    decryption_data = analysis.get("decryption_v5_data") or []
    if not decryption_data:
        return {"user_move_count": 0, "trends": []}

    from services.board_state_game_summary import compute_game_summary

    return compute_game_summary(
        decryption_v5_data=decryption_data,
        user_color=game.get("user_color") or "white",
    )
