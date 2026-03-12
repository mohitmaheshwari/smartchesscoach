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
from typing import Optional, Dict
import logging

logger = logging.getLogger(__name__)

# Create router for lab endpoints
router = APIRouter(tags=["Lab"])

# Database reference - will be set by server.py
db = None

# LLM function reference - will be set by server.py
call_llm = None

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
    
    return {
        "game_id": game_id,
        "user_color": user_color,
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
