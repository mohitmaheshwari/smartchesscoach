"""
Lab Routes
==========

Handles the Lab page functionality - deep game analysis with pattern tracking.

Endpoints:
- GET /lab/{game_id} - Get comprehensive lab page data
- GET /lab/{game_id}/mistake/{move_number}/context - Get pattern context for a mistake
- POST /explain-mistake - Generate educational explanation for a mistake
- GET /lab/{game_id}/deep-strategy - Deep strategic analysis with tags and theory
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, Dict, List
import logging

logger = logging.getLogger(__name__)

# Create router for lab endpoints
router = APIRouter(tags=["Lab"])

# Database reference - will be set by server.py
db = None

# LLM function reference - will be set by server.py
call_llm = None


def analyze_opening_performance(move_evaluations: List[Dict], user_color: str) -> Dict:
    """
    Analyze how well the user played the opening phase (first 10-15 moves).
    
    Returns:
    - played_well: bool - True if no significant mistakes in opening
    - mistakes_in_opening: int - Number of mistakes (cp_loss >= 100) in opening
    - inaccuracies_in_opening: int - Number of inaccuracies (50 <= cp_loss < 100)
    - first_mistake_move: int | None - Move number of first mistake
    - first_mistake_details: dict | None - Details of first mistake
    - opening_accuracy: float - Percentage of good moves in opening
    - verdict: str - "excellent", "good", "needs_work", "poor"
    """
    OPENING_MOVES = 15  # Consider first 15 moves as opening
    MISTAKE_THRESHOLD = 100  # centipawns
    INACCURACY_THRESHOLD = 50
    
    result = {
        "played_well": True,
        "mistakes_in_opening": 0,
        "inaccuracies_in_opening": 0,
        "first_mistake_move": None,
        "first_mistake_details": None,
        "opening_accuracy": 100.0,
        "verdict": "excellent",
        "opening_moves_analyzed": 0
    }
    
    if not move_evaluations:
        return result
    
    good_moves = 0
    total_opening_moves = 0
    
    for m in move_evaluations:
        move_num = m.get("move_number", 0)
        
        # Only analyze opening moves for the user's color
        if move_num > OPENING_MOVES:
            break
        
        # Check if this is user's move
        is_user_move = (
            (user_color == "white" and move_num % 2 == 1) or
            (user_color == "black" and move_num % 2 == 0)
        )
        
        if not is_user_move:
            continue
        
        total_opening_moves += 1
        cp_loss = abs(m.get("cp_loss", 0))
        
        if cp_loss >= MISTAKE_THRESHOLD:
            result["mistakes_in_opening"] += 1
            result["played_well"] = False
            
            if result["first_mistake_move"] is None:
                result["first_mistake_move"] = move_num
                result["first_mistake_details"] = {
                    "move_number": move_num,
                    "your_move": m.get("move", ""),
                    "best_move": m.get("best_move", ""),
                    "cp_loss": cp_loss,
                    "fen": m.get("fen_before", "")
                }
        elif cp_loss >= INACCURACY_THRESHOLD:
            result["inaccuracies_in_opening"] += 1
        else:
            good_moves += 1
    
    result["opening_moves_analyzed"] = total_opening_moves
    
    if total_opening_moves > 0:
        result["opening_accuracy"] = round((good_moves / total_opening_moves) * 100, 1)
    
    # Determine verdict
    if result["mistakes_in_opening"] == 0 and result["inaccuracies_in_opening"] <= 1:
        result["verdict"] = "excellent"
    elif result["mistakes_in_opening"] == 0 and result["inaccuracies_in_opening"] <= 2:
        result["verdict"] = "good"
    elif result["mistakes_in_opening"] <= 1:
        result["verdict"] = "needs_work"
    else:
        result["verdict"] = "poor"
    
    return result


def set_db(database):
    """Set the database reference for lab routes"""
    global db
    db = database

def set_llm(llm_func):
    """Set the LLM function reference for lab routes"""
    global call_llm
    call_llm = llm_func


# Import User model and get_current_user from auth routes
from routes.auth import User, get_current_user

# Import helper functions
from blunder_intelligence_service import (
    get_lab_data,
    get_lab_data_async,
    find_similar_pattern_games
)

from pattern_context_service import (
    build_pattern_history,
    get_pattern_context_for_mistake,
    get_game_pattern_summary,
)

from mistake_explanation_service import (
    generate_mistake_explanation,
    analyze_mistake_position,
    get_quick_explanation
)

from services.turning_point_explainer import (
    get_turning_point_explainer,
    TurningPointExplanation
)

# Import Coach Personality Service for personalized language
from services.coach_personality import (
    get_player_level,
    get_level_display_name,
    get_level_emoji,
    get_personalized_coaching_context,
    CoachLanguage,
    CoachVoice,
    PlayerLevel
)

# Import Chess Understanding Service for multi-dimensional analysis
from services.chess_understanding import (
    get_chess_understanding,
    update_chess_understanding,
    get_coaching_context_from_understanding,
    UnderstandingBasedCoaching,
    ChessUnderstanding
)


# ==================== MODELS ====================

class MistakeExplanationRequest(BaseModel):
    """Request for on-demand mistake explanation"""
    fen_before: str
    move: str
    best_move: str
    cp_loss: int
    user_color: str
    move_number: Optional[int] = None


# ==================== ENDPOINTS ====================

@router.get("/lab/{game_id}")
async def get_lab_page_data(game_id: str, user: User = Depends(get_current_user)):
    """
    Get data for the Lab page (DETAIL - What actually happened)
    
    Returns:
    - Core lesson of the game
    - Evidence-based game strategy
    - Full analysis data
    - Similar games (Behavior Memory)
    - Pattern context (longitudinal tracking)
    
    Note: Now uses learned rules for more accurate mistake explanations.
    """
    global db
    
    analysis = await db.game_analyses.find_one({
        "game_id": game_id,
        "user_id": user.user_id
    })
    
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    
    # Get game data for metadata
    game = await db.games.find_one({
        "game_id": game_id,
        "user_id": user.user_id
    })
    
    # Remove MongoDB _id
    if "_id" in analysis:
        del analysis["_id"]
    if game and "_id" in game:
        del game["_id"]
    
    # Use async version with learned rules support
    try:
        lab_data = await get_lab_data_async(analysis, game)
    except Exception as e:
        logger.warning(f"Async lab data failed, falling back to sync: {e}")
        lab_data = get_lab_data(analysis, game)
    
    # Get all analyses and games for pattern tracking
    all_analyses = await db.game_analyses.find(
        {"user_id": user.user_id},
        {"_id": 0}
    ).to_list(100)
    
    # Include more fields for rich pattern context
    all_games = await db.games.find(
        {"user_id": user.user_id},
        {"_id": 0, "game_id": 1, "user_color": 1, "white_player": 1, "black_player": 1, 
         "opponent_name": 1, "result": 1, "imported_at": 1,
         "white_rating": 1, "black_rating": 1, "time_control": 1, 
         "opening": 1, "opening_name": 1, "eco": 1}
    ).to_list(100)
    
    # Add similar games (Behavior Memory)
    similar_games = find_similar_pattern_games(analysis, all_analyses, all_games)
    lab_data["similar_games"] = similar_games
    
    # Add pattern context (longitudinal tracking) - THE GOLDEN INFORMATION with SPECIFIC insights
    pattern_history = build_pattern_history(user.user_id, all_analyses, all_games)
    game_pattern_summary = get_game_pattern_summary(analysis, pattern_history, all_games, game)
    
    lab_data["pattern_context"] = {
        "summary": game_pattern_summary,
        "history": {
            "most_recurring": pattern_history.get("most_recurring"),
            "improving_patterns": pattern_history.get("improving_patterns", []),
            "fixed_patterns": pattern_history.get("fixed_patterns", []),
        },
        # Global vulnerability insights
        "global_insights": {
            "rating_vulnerable": pattern_history.get("rating_vulnerable"),
            "time_vulnerable": pattern_history.get("time_vulnerable"),
            "opening_triggers": pattern_history.get("opening_triggers", []),
        }
    }
    
    # ADD: Biggest blunder with SPECIFIC threat info
    sf_analysis = analysis.get("stockfish_analysis", {})
    move_evals = sf_analysis.get("move_evaluations", [])
    
    biggest_blunder = None
    for m in move_evals:
        cp_loss = abs(m.get("cp_loss", 0))
        if cp_loss >= 100:  # At least 1 pawn loss
            if biggest_blunder is None or cp_loss > abs(biggest_blunder.get("cp_loss", 0)):
                biggest_blunder = {
                    "move_number": m.get("move_number"),
                    "move": m.get("move"),
                    "best_move": m.get("best_move"),
                    "cp_loss": m.get("cp_loss"),
                    "threat": m.get("threat"),  # THE SPECIFIC THREAT
                    "fen_before": m.get("fen_before"),
                    "eval_before": m.get("eval_before"),
                    "eval_after": m.get("eval_after"),
                    "pv_after_best": m.get("pv_after_best", [])[:4],
                    "is_checkmate_level": cp_loss >= 9000  # 99+ pawns = checkmate
                }
    
    lab_data["biggest_blunder"] = biggest_blunder
    lab_data["blunders"] = sf_analysis.get("blunders", 0)
    lab_data["mistakes"] = sf_analysis.get("mistakes", 0)
    
    # ADD: Turning Point - where the game was TRULY decided
    # Logic: Find the move with largest eval drop that made recovery impossible
    # Not just "first time going negative" but "the move that lost the game"
    user_color = game.get("user_color", "white") if game else "white"
    
    # Get user's rating from game for adaptive explanation
    user_rating = 1200  # Default
    if game:
        if user_color == "white":
            user_rating = game.get("white_rating") or 1200
        else:
            user_rating = game.get("black_rating") or 1200
    
    turning_point = None
    missed_recovery = None
    
    if move_evals:
        # Track eval from user's perspective (positive = good for user)
        def user_eval(eval_val, color):
            """Convert eval to user's perspective"""
            if eval_val is None:
                return 0
            return eval_val if color == "white" else -eval_val
        
        def is_user_move(move_num, user_clr):
            """Check if this move number belongs to user"""
            if user_clr == "white":
                return move_num % 2 == 1
            return move_num % 2 == 0
        
        # ============================================================
        # TURNING POINT LOGIC v3
        # ============================================================
        # True turning point = the mistake with LARGEST EVAL DROP where:
        # 1. Opponent played accurately in the NEXT 5 moves (not all remaining)
        # 2. User never recovered after
        #
        # Key insight from user:
        # - Move 27 dropped ~2 pawns, but opponent made mistakes between 27-31
        # - Move 31 dropped ~4 pawns, then opponent played Qf2, accurate to end
        # - Move 31 is the TRUE turning point (largest drop + opponent accurate)
        # ============================================================
        
        turning_point_candidates = []
        
        for i, m in enumerate(move_evals):
            move_num = m.get("move_number", i + 1)
            
            # Only consider user's moves
            if not is_user_move(move_num, user_color):
                continue
            
            eval_before = user_eval(m.get("eval_before"), user_color)
            eval_after = user_eval(m.get("eval_after"), user_color)
            cp_loss = abs(m.get("cp_loss", 0))
            eval_drop = eval_before - eval_after  # How much user's position worsened
            
            # Must be a significant mistake (150+ cp loss)
            if cp_loss < 150:
                continue
            
            # Check IMMEDIATE aftermath (next 5 opponent moves only)
            # This prevents early small mistakes from qualifying just because
            # opponent played well at the END of the game
            remaining_moves = move_evals[i + 1:]
            if not remaining_moves:
                continue
            
            # Check opponent's play in next 5 moves (not entire game)
            opponent_moves_checked = 0
            opponent_mistakes_immediate = 0
            max_user_recovery = eval_after
            
            for future_m in remaining_moves:
                future_move_num = future_m.get("move_number", 0)
                future_cp_loss = abs(future_m.get("cp_loss", 0))
                future_eval = user_eval(future_m.get("eval_after"), user_color)
                
                # Track user's max recovery
                if future_eval > max_user_recovery:
                    max_user_recovery = future_eval
                
                # Check opponent's immediate moves (next 5 only)
                if not is_user_move(future_move_num, user_color):
                    opponent_moves_checked += 1
                    if future_cp_loss >= 100:  # Opponent mistake
                        opponent_mistakes_immediate += 1
                    
                    # Only check next 5 opponent moves
                    if opponent_moves_checked >= 5:
                        break
            
            # User never recovered if they stayed below -150
            never_recovered = max_user_recovery < -150
            
            # Opponent played accurately = at most 1 mistake in next 5 moves
            opponent_played_well_after = opponent_mistakes_immediate <= 1
            
            if never_recovered and opponent_played_well_after:
                turning_point_candidates.append({
                    "move_number": move_num,
                    "move": m.get("move"),
                    "best_move": m.get("best_move"),
                    "eval_before": m.get("eval_before"),
                    "eval_after": m.get("eval_after"),
                    "cp_loss": cp_loss,
                    "eval_drop": eval_drop,
                    "fen_before": m.get("fen_before"),
                    "threat": m.get("threat"),
                    "index": i,
                    "opponent_mistakes_immediate": opponent_mistakes_immediate,
                    "max_recovery_attempt": max_user_recovery
                })
        
        # Pick the turning point with LARGEST EVAL DROP (not earliest!)
        # This is the move that ACTUALLY decided the game
        if turning_point_candidates:
            turning_point_data = max(turning_point_candidates, key=lambda x: x["eval_drop"])
            
            # Use the adaptive explainer for rich, rating-aware explanation
            explainer = get_turning_point_explainer()
            try:
                import asyncio
                explanation = asyncio.get_event_loop().run_until_complete(
                    explainer.explain(
                        fen=turning_point_data.get("fen_before", ""),
                        user_move=turning_point_data.get("move", ""),
                        best_move=turning_point_data.get("best_move", ""),
                        cp_loss=int(turning_point_data.get("eval_drop", 0)),
                        user_rating=user_rating,
                        threat=turning_point_data.get("threat"),
                        eval_before=turning_point_data.get("eval_before"),
                        eval_after=turning_point_data.get("eval_after")
                    )
                )
                
                turning_point = {
                    "move_number": turning_point_data["move_number"],
                    "move": turning_point_data.get("move", ""),
                    "best_move": turning_point_data.get("best_move", ""),
                    "eval_before": turning_point_data["eval_before"],
                    "eval_after": turning_point_data["eval_after"],
                    "eval_drop": turning_point_data["eval_drop"],
                    "fen_before": turning_point_data["fen_before"],
                    "type": "true_turning_point",
                    # Rich, adaptive explanation
                    "description": explanation.main_text,
                    "missed_idea": explanation.missed_idea,
                    "opponent_idea": explanation.opponent_idea,
                    "thinking_error": explanation.thinking_error,
                    "training_tip": explanation.training_tip,
                    "severity": explanation.severity
                }
            except Exception as e:
                logger.warning(f"Explainer failed, using basic explanation: {e}")
                # Fallback to basic explanation
                eval_drop = turning_point_data.get("eval_drop", 0)
                threat = turning_point_data.get("threat", "")
                
                if eval_drop >= 400:
                    severity = "This move gave away the game."
                elif eval_drop >= 200:
                    severity = "This mistake was too big to recover from."
                else:
                    severity = "After this, the position became very difficult."
                
                behavioral_insight = ""
                if threat:
                    behavioral_insight = f" {threat}"
                
                turning_point = {
                    "move_number": turning_point_data["move_number"],
                    "move": turning_point_data.get("move", ""),
                    "best_move": turning_point_data.get("best_move", ""),
                    "eval_before": turning_point_data["eval_before"],
                    "eval_after": turning_point_data["eval_after"],
                    "eval_drop": eval_drop,
                    "fen_before": turning_point_data["fen_before"],
                    "type": "true_turning_point",
                    "description": f"{severity}{behavioral_insight}"
                }
        
        # Find missed recovery opportunities (DIFFERENT from turning point)
        # This is for moments BEFORE the turning point where user could have saved it
        turning_point_move = turning_point["move_number"] if turning_point else 9999
        
        for i, m in enumerate(move_evals):
            move_num = m.get("move_number", i + 1)
            
            # Only consider user's moves
            if not is_user_move(move_num, user_color):
                continue
            
            # Skip if this IS the turning point
            if move_num >= turning_point_move:
                continue
            
            eval_before = user_eval(m.get("eval_before"), user_color)
            cp_loss = abs(m.get("cp_loss", 0))
            
            # User was losing but not hopeless (-100 to -400)
            # AND this is before the turning point
            if eval_before < -100 and eval_before > -400:
                # Made a significant mistake
                if cp_loss >= 150:
                    # Check if best move would have equalized/improved
                    potential_eval = eval_before + cp_loss
                    if potential_eval > -50:  # Best move would have helped significantly
                        missed_recovery = {
                            "move_number": move_num,
                            "move": m.get("move"),
                            "best_move": m.get("best_move"),
                            "eval_before": m.get("eval_before"),
                            "eval_after": m.get("eval_after"),
                            "fen_before": m.get("fen_before"),
                            "type": "missed_recovery",
                            "description": f"You were behind but had a chance to fight back with {m.get('best_move')}."
                        }
                        break  # Take the first missed recovery
    
    lab_data["turning_point"] = turning_point
    lab_data["missed_recovery"] = missed_recovery
    
    return lab_data


@router.get("/lab/{game_id}/mistake/{move_number}/context")
async def get_mistake_pattern_context(game_id: str, move_number: int, user: User = Depends(get_current_user)):
    """
    Get pattern context for a specific mistake in a game.
    Shows if this pattern has occurred before and in which games.
    
    THE GOLDEN INFORMATION:
    - "You made this same mistake in 3 other games"
    - "You did this against opponent X too"  
    - "You FIXED this! Compare to your game vs Y"
    """
    global db
    
    # Get the analysis for this game
    analysis = await db.game_analyses.find_one({
        "game_id": game_id,
        "user_id": user.user_id
    })
    
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    
    # Find the specific mistake
    sf = analysis.get("stockfish_analysis", {})
    evals = sf.get("move_evaluations", [])
    
    mistake = None
    for e in evals:
        if e.get("move_number") == move_number and e.get("evaluation") in ["blunder", "mistake"]:
            mistake = {
                "move_number": e.get("move_number"),
                "move": e.get("move"),
                "threat": e.get("threat"),
                "cp_loss": e.get("cp_loss"),
                "phase": e.get("phase"),
                "eval_before": e.get("eval_before"),
                "eval_after": e.get("eval_after"),
            }
            break
    
    if not mistake:
        return {"context": None, "message": "No mistake found at this move"}
    
    # Get all analyses and games for pattern history with rich context
    all_analyses = await db.game_analyses.find(
        {"user_id": user.user_id},
        {"_id": 0}
    ).to_list(100)
    
    all_games = await db.games.find(
        {"user_id": user.user_id},
        {"_id": 0, "game_id": 1, "user_color": 1, "white_player": 1, "black_player": 1, 
         "opponent_name": 1, "result": 1, "imported_at": 1,
         "white_rating": 1, "black_rating": 1, "time_control": 1,
         "opening": 1, "opening_name": 1, "eco": 1}
    ).to_list(100)
    
    # Build pattern history and get SPECIFIC context
    pattern_history = build_pattern_history(user.user_id, all_analyses, all_games)
    context = get_pattern_context_for_mistake(mistake, game_id, pattern_history, all_games)
    
    return {
        "mistake": mistake,
        "context": context,
    }


@router.post("/explain-mistake")
async def explain_mistake(req: MistakeExplanationRequest, user: User = Depends(get_current_user)):
    """
    Generate an educational explanation for a specific mistake.
    
    This endpoint:
    1. Uses deterministic chess rules to identify WHAT went wrong
    2. Uses GPT to write a human-readable explanation of WHY
    
    GPT does NOT analyze chess - it only writes commentary based on our analysis.
    """
    global call_llm
    
    move_data = {
        "fen_before": req.fen_before,
        "move": req.move,
        "best_move": req.best_move,
        "cp_loss": req.cp_loss,
        "user_color": req.user_color,
        "move_number": req.move_number
    }
    
    try:
        # Generate the explanation (uses LLM for commentary)
        explanation = await generate_mistake_explanation(move_data, call_llm)
        return explanation
    except Exception as e:
        logger.error(f"Error generating mistake explanation: {e}")
        # Return a fallback explanation based on templates
        analysis = analyze_mistake_position(
            req.fen_before, req.move, req.best_move, req.cp_loss, req.user_color
        )
        return {
            "explanation": get_quick_explanation(
                analysis.get("mistake_type", "inaccuracy"),
                analysis.get("details", {})
            ),
            "mistake_type": analysis.get("mistake_type", "inaccuracy"),
            "short_label": "Mistake",
            "thinking_habit": None,
            "severity": analysis.get("severity", "minor"),
            "phase": analysis.get("phase", "middlegame"),
            "details": analysis.get("details", {})
        }


@router.get("/lab/{game_id}/deep-strategy")
async def get_deep_strategy_analysis(game_id: str, user: User = Depends(get_current_user)):
    """
    Generate deep, position-specific strategic analysis for a game.
    
    This is what a HUMAN COACH would tell you:
    - Not generic "trade pieces when ahead"
    - But specific: "Your knight on e6 could take the bishop on d4, winning material"
    - Shows WHAT you missed and WHY in each critical position
    
    Returns specific insights for each critical moment.
    """
    global db, call_llm
    
    from services.position_strategy_analyzer import (
        analyze_position_deeply,
        generate_move_specific_insight,
        generate_strategic_lesson
    )
    
    # Get game and analysis
    analysis = await db.game_analyses.find_one({
        "game_id": game_id,
        "user_id": user.user_id
    }, {"_id": 0})
    
    if not analysis:
        raise HTTPException(status_code=404, detail="Game analysis not found")
    
    game = await db.games.find_one({
        "game_id": game_id,
        "user_id": user.user_id
    }, {"_id": 0})
    
    user_color = game.get("user_color", "white") if game else "white"
    sf = analysis.get("stockfish_analysis", {})
    move_evaluations = sf.get("move_evaluations", [])
    
    # Get total moves for phase detection
    total_moves = len(move_evaluations) if move_evaluations else 40
    
    # Find critical moments (mistakes with cp_loss >= 100)
    critical_moments = []
    for i, m in enumerate(move_evaluations):
        cp_loss = abs(m.get("cp_loss", 0))
        if cp_loss >= 100:
            fen = m.get("fen_before", "")
            fen_after = m.get("fen_after", fen)  # Use fen_after if available
            user_move = m.get("move", "")
            best_move = m.get("best_move", "")
            pv = m.get("pv_after_best", [])
            move_num = m.get("move_number", 0)
            eval_before = m.get("eval_before", 0)
            eval_after = m.get("eval_after", eval_before - cp_loss)
            
            if fen and user_move and best_move:
                # Deep position analysis
                position_analysis = analyze_position_deeply(fen, user_color)
                
                # Get threat data if available
                threat = m.get("threat", "")
                
                # Specific insight for this mistake
                insight = generate_move_specific_insight(
                    fen, user_move, best_move, pv, cp_loss, user_color, threat
                )
                
                # Tag this moment with patterns
                from services.game_tagging_service import tag_critical_moment
                from services.tag_theory_mapping import enrich_moment_with_theories
                user_rating = game.get("user_rating", 1200) if game else 1200
                tags = tag_critical_moment(
                    move_number=move_num,
                    move_san=user_move,
                    fen_before=fen,
                    fen_after=fen_after,
                    cp_loss=cp_loss,
                    best_move=best_move,
                    pv_after=pv[:5] if pv else [],
                    user_rating=user_rating,
                    total_moves=total_moves,
                    eval_before=eval_before,
                    eval_after=eval_after
                )
                
                moment_data = {
                    "move_number": move_num,
                    "fen": fen,
                    "your_move": user_move,
                    "best_move": best_move,
                    "cp_loss": cp_loss,
                    "threat": threat,
                    "pv_after_best": pv[:4],  # First 4 moves of continuation
                    "position_analysis": position_analysis,
                    "insight": insight,
                    "tags": tags.to_dict() if tags else {},  # Add tags
                }
                
                # Enrich with theory recommendations
                moment_data = enrich_moment_with_theories(moment_data)
                
                critical_moments.append(moment_data)
    
    # Sort by move number (chronological order) - first mistake appears first
    critical_moments.sort(key=lambda x: x.get("move_number", 0))
    
    # Generate overall lesson
    lesson = generate_strategic_lesson(
        game or {},
        move_evaluations,
        user_color
    )
    
    # Get player profile for personalized coaching
    player_profile = await db.player_profiles.find_one({"user_id": user.user_id}, {"_id": 0})
    # Profile schema uses estimated_elo, not current_rating
    user_rating = player_profile.get("estimated_elo", player_profile.get("current_rating", 1200)) if player_profile else 1200
    games_played = player_profile.get("games_analyzed_count", player_profile.get("games_analyzed", 0)) if player_profile else 0
    
    # Get MULTI-DIMENSIONAL chess understanding
    chess_understanding = await get_chess_understanding(db, user.user_id)
    understanding_context = get_coaching_context_from_understanding(chess_understanding)
    
    # Get simple level for backwards compatibility
    coaching_context = get_personalized_coaching_context(user_rating, games_played)
    player_level = PlayerLevel(coaching_context["level"])
    
    # If we have critical moments, use LLM to generate human-readable explanations
    if critical_moments and len(critical_moments) > 0 and call_llm:
        try:
            # Use LLM with UNDERSTANDING-BASED voice, not just rating-based
            top_moment = critical_moments[0]
            
            # Build personalized prompt based on multi-dimensional understanding
            understanding_summary = f"""
PLAYER PROFILE:
- Overall: {chess_understanding.overall_understanding}
- Tactical Vision: {chess_understanding.tactical_vision.level.value} (score: {chess_understanding.tactical_vision.score:.0f}/100)
- Positional Sense: {chess_understanding.positional_sense.level.value} (score: {chess_understanding.positional_sense.score:.0f}/100)
- Consistency: {chess_understanding.consistency.level.value} (score: {chess_understanding.consistency.score:.0f}/100)
- Primary Strength: {chess_understanding.primary_strength}
- Primary Weakness: {chess_understanding.primary_weakness}
- Coaching Focus: {chess_understanding.coaching_focus}
"""
            
            # Get language style based on understanding
            language_style = understanding_context.get("language", {})
            analysis_style = understanding_context.get("analysis_style", {})
            
            voice_prefix = CoachVoice.get_prompt_prefix(player_level)
            
            prompt = f"""{voice_prefix}

{understanding_summary}

COACHING STYLE FOR THIS PLAYER:
- Tactical advice style: {language_style.get('tactical_advice', '')}
- Focus reminder: {language_style.get('focus_reminder', '')}
- Use jargon: {analysis_style.get('use_jargon', True)}
- Explain concepts: {analysis_style.get('explain_concepts', True)}

You are explaining a mistake to this specific student.
Be specific about THIS position, not generic advice.

POSITION (FEN): {top_moment['fen']}
THE STUDENT PLAYED: {top_moment['your_move']}
THE BEST MOVE WAS: {top_moment['best_move']}
CONTINUATION AFTER BEST: {' '.join(top_moment.get('pv_after_best', []))}
EVALUATION LOSS: {top_moment['cp_loss']} centipawns

Analysis found:
- Position type: {top_moment['insight'].get('position_type', '')}
- What best move achieves: {top_moment['insight'].get('what_best_move_achieves', '')}

Write a 2-3 sentence explanation that:
1. Names the specific pieces and squares involved
2. Explains what the student missed in THIS position
3. If their {chess_understanding.primary_weakness.lower()} is weak, relate to that
4. Adapt complexity to their understanding level

Be direct and specific to THIS position.
"""
            llm_explanation = await call_llm(prompt)
            if llm_explanation:
                critical_moments[0]["coach_explanation"] = llm_explanation
        except Exception as e:
            logger.error(f"Error generating LLM explanation: {e}")
    
    # Analyze opening performance for this specific game
    opening_performance = analyze_opening_performance(move_evaluations, user_color)
    
    # NEW: Analyze for trap patterns
    trap_analysis = None
    try:
        from services.trap_library import analyze_game_for_traps
        
        # Get the moves from the game
        game_moves = [m.get("move", "") for m in move_evaluations if m.get("move")]
        if game_moves:
            trap_analysis = analyze_game_for_traps(game_moves, user_color)
    except Exception as e:
        logger.error(f"Error analyzing traps: {e}")
    
    return {
        "game_id": game_id,
        "user_color": user_color,
        "game": {
            "opening": game.get("opening") if game else None,
            "opening_name": game.get("opening_name") if game else None,
            "eco": game.get("eco") if game else None,
            "opening_url": game.get("opening_url") if game else None,
            "result": game.get("result") if game else None,
            "opponent_name": game.get("opponent_name") if game else None
        },
        "opening_performance": opening_performance,
        "trap_analysis": trap_analysis,  # NEW: Trap detection results
        "critical_moments": critical_moments[:5],  # Top 5 moments
        "lesson": lesson,
        "total_mistakes": len(critical_moments),
        # Simple level (backwards compatibility)
        "player_level": coaching_context["level"],
        "player_level_display": coaching_context["level_display"],
        "player_level_emoji": coaching_context["level_emoji"],
        "coaching_voice": coaching_context["voice_style"],
        "player_rating": user_rating,
        "games_analyzed": games_played,
        # NEW: Multi-dimensional understanding
        "chess_understanding": {
            "overall": chess_understanding.overall_understanding,
            "primary_strength": chess_understanding.primary_strength,
            "primary_weakness": chess_understanding.primary_weakness,
            "coaching_focus": chess_understanding.coaching_focus,
            "dimensions": {
                "tactical_vision": {
                    "level": chess_understanding.tactical_vision.level.value,
                    "score": round(chess_understanding.tactical_vision.score, 1),
                    "weaknesses": chess_understanding.tactical_vision.specific_weaknesses
                },
                "positional_sense": {
                    "level": chess_understanding.positional_sense.level.value,
                    "score": round(chess_understanding.positional_sense.score, 1),
                    "weaknesses": chess_understanding.positional_sense.specific_weaknesses
                },
                "opening_knowledge": {
                    "level": chess_understanding.opening_knowledge.level.value,
                    "score": round(chess_understanding.opening_knowledge.score, 1)
                },
                "consistency": {
                    "level": chess_understanding.consistency.level.value,
                    "score": round(chess_understanding.consistency.score, 1),
                    "weaknesses": chess_understanding.consistency.specific_weaknesses
                }
            }
        }
    }



class MoveEvaluationRequest(BaseModel):
    """Request to evaluate a move in a critical moment."""
    fen: str
    user_move: str  # UCI format (e.g., "e2e4")
    best_move: str  # SAN format (e.g., "Nf3")
    original_move: Optional[str] = None  # What the user originally played (SAN)
    eval_before: Optional[float] = None  # Eval before the position
    eval_after_best: Optional[float] = None  # Eval after best move


class MoveEvaluationResponse(BaseModel):
    """Response with move quality assessment."""
    quality: str  # "best", "excellent", "good", "okay", "inaccuracy", "mistake", "blunder"
    symbol: str  # "check", "warning", "close"
    is_correct: bool  # Whether to count as "correct" for practice
    cp_loss: Optional[int] = None
    message: str
    comparison_to_original: Optional[str] = None  # "better", "same", "worse"
    feedback: str  # Detailed coaching feedback


@router.post("/lab/evaluate-move", response_model=MoveEvaluationResponse)
async def evaluate_practice_move(request: MoveEvaluationRequest):
    """
    Evaluate a user's move attempt in practice mode.
    
    Provides nuanced feedback beyond just "correct/incorrect":
    - "best": Perfect! Same as engine recommendation
    - "excellent": Within 10cp of best - great find!
    - "good": Within 25cp - solid move
    - "okay": Within 50cp - playable but not ideal
    - "inaccuracy": 50-100cp loss - needs improvement
    - "mistake": 100-200cp loss - significant error
    - "blunder": >200cp loss - major error
    
    Also compares to what the user originally played in the game.
    """
    import chess
    
    try:
        board = chess.Board(request.fen)
        
        # Parse user's move
        try:
            from_sq = request.user_move[:2]
            to_sq = request.user_move[2:4]
            promotion = request.user_move[4] if len(request.user_move) > 4 else None
            
            user_move_obj = board.find_move(
                chess.parse_square(from_sq),
                chess.parse_square(to_sq),
                promotion=chess.Piece.from_symbol(promotion).piece_type if promotion else None
            )
            user_move_san = board.san(user_move_obj)
        except Exception as e:
            logger.warning(f"Could not parse user move: {e}")
            return MoveEvaluationResponse(
                quality="invalid",
                symbol="close",
                is_correct=False,
                message="Invalid move",
                feedback="That move isn't legal in this position.",
                cp_loss=None
            )
        
        # Parse best move to get UCI
        try:
            best_move_obj = board.parse_san(request.best_move)
            best_move_uci = best_move_obj.uci()
        except Exception as e:
            logger.warning(f"Could not parse best move: {e}")
            best_move_uci = None
        
        # Check if it's the best move
        user_move_uci = user_move_obj.uci()
        is_best = user_move_uci == best_move_uci
        
        if is_best:
            return MoveEvaluationResponse(
                quality="best",
                symbol="check",
                is_correct=True,
                cp_loss=0,
                message="Perfect!",
                comparison_to_original="better" if request.original_move and request.original_move != request.best_move else "same",
                feedback=f"Excellent! {user_move_san} is the best move in this position."
            )
        
        # For non-best moves, we need to estimate quality
        # If we have evaluations, use them. Otherwise, use heuristics.
        
        # Heuristic-based evaluation when we don't have engine evals
        # Without Stockfish, we use tactical heuristics and be more generous
        
        # Default values
        quality = "okay"  # Default to okay if we can't determine a problem
        cp_loss = 30  # Default small penalty for not being best
        symbol = "warning"
        is_correct = False  # Not best, so not "correct" by default
        feedback = f"{user_move_san} is playable, but {request.best_move} was stronger here."
        
        # Make the user's move and check for tactical problems
        board_after = board.copy()
        board_after.push(user_move_obj)
        
        # Get piece information
        piece_moved = board.piece_at(user_move_obj.from_square)
        piece_value = {"p": 1, "n": 3, "b": 3, "r": 5, "q": 9, "k": 0}.get(
            piece_moved.symbol().lower(), 0
        ) if piece_moved else 0
        
        # Check if it's a capture
        is_capture = board.is_capture(user_move_obj)
        captured_piece = board.piece_at(user_move_obj.to_square)
        captured_value = {"p": 1, "n": 3, "b": 3, "r": 5, "q": 9, "k": 0}.get(
            captured_piece.symbol().lower(), 0
        ) if captured_piece else 0
        
        # Check for checks
        gives_check = board_after.is_check()
        
        # Check if user's piece is immediately hanging after the move
        # After the move, it's the opponent's turn, so we check if THEY attack our piece
        opponent_color = board_after.turn  # After our move, it's opponent's turn
        our_color = not board_after.turn   # Our color (we just moved)
        
        is_piece_hanging = board_after.is_attacked_by(
            opponent_color, 
            user_move_obj.to_square
        )
        
        # Check if the piece is also defended by our pieces
        is_defended = board_after.is_attacked_by(
            our_color,
            user_move_obj.to_square
        )
        
        # === Evaluate move quality ===
        
        # GREAT MOVES: Giving check is almost always good
        if gives_check:
            quality = "good"
            symbol = "check"
            is_correct = True
            cp_loss = 15
            feedback = f"{user_move_san} gives check! A forcing move, though {request.best_move} was technically stronger."
        
        # GOOD MOVES: Good captures (winning or equal material)
        elif is_capture and captured_value >= piece_value:
            if not is_piece_hanging or is_defended:
                quality = "good"
                symbol = "check"
                is_correct = True
                cp_loss = 20
                feedback = f"{user_move_san} is a reasonable capture. {request.best_move} was slightly better."
            else:
                quality = "okay"
                symbol = "warning"
                is_correct = False
                cp_loss = 40
                feedback = f"{user_move_san} captures but leaves your piece vulnerable. {request.best_move} was safer."
        
        # BAD MOVES: Hanging a piece without compensation
        elif is_piece_hanging and not is_defended and piece_value > captured_value:
            if piece_value >= 5:  # Rook or Queen
                quality = "blunder"
                symbol = "close"
                cp_loss = piece_value * 100
                feedback = f"{user_move_san} hangs your {piece_moved.symbol().upper()}! It can be captured for free."
            elif piece_value >= 3:  # Knight or Bishop
                quality = "mistake"
                symbol = "close"
                cp_loss = piece_value * 100
                feedback = f"{user_move_san} loses your {piece_moved.symbol().upper()} - it's undefended after this move."
            else:  # Pawn
                quality = "inaccuracy"
                symbol = "warning"
                is_correct = False
                cp_loss = 50
                feedback = f"{user_move_san} loses a pawn. Small material but {request.best_move} was better."
        
        # OKAY MOVES: Developing moves, pawn moves, etc.
        elif piece_moved and piece_moved.piece_type in [chess.KNIGHT, chess.BISHOP]:
            # Developing a minor piece is usually okay
            quality = "okay"
            symbol = "warning"
            is_correct = False
            cp_loss = 25
            feedback = f"{user_move_san} develops your piece. Decent, but {request.best_move} was more accurate."
        
        elif piece_moved and piece_moved.piece_type == chess.PAWN:
            # Pawn moves - generally okay unless obviously bad
            if is_piece_hanging and not is_defended:
                quality = "inaccuracy"
                symbol = "warning"
                cp_loss = 60
                feedback = f"{user_move_san} leaves your pawn vulnerable. {request.best_move} was safer."
            else:
                quality = "okay"
                symbol = "warning"
                is_correct = False
                cp_loss = 30
                feedback = f"{user_move_san} is a reasonable pawn move, but {request.best_move} was stronger."
        
        # Default: It's playable but not best
        
        # Compare to original move if provided
        comparison = None
        if request.original_move:
            if user_move_san == request.original_move:
                comparison = "same"
                feedback = f"You played the same move again. Try to find something better - look for {request.best_move}."
            elif quality in ["best", "excellent", "good"]:
                comparison = "better"
                feedback = f"Nice improvement! {user_move_san} is better than your original {request.original_move}."
            else:
                comparison = "worse"
        
        return MoveEvaluationResponse(
            quality=quality,
            symbol=symbol,
            is_correct=is_correct,
            cp_loss=cp_loss,
            message={
                "best": "Perfect!",
                "excellent": "Excellent!",
                "good": "Good move!",
                "okay": "Okay move",
                "inaccuracy": "Inaccuracy",
                "mistake": "Mistake",
                "blunder": "Blunder!"
            }.get(quality, ""),
            comparison_to_original=comparison,
            feedback=feedback
        )
        
    except Exception as e:
        logger.error(f"Error evaluating move: {e}")
        raise HTTPException(status_code=500, detail=str(e))
