"""
Reflection Service - Handles the time-sensitive reflection flow.

This service manages:
1. Identifying games needing reflection (recently analyzed, not yet reflected)
2. Extracting critical moments from games for reflection
3. Processing user reflections and identifying awareness gaps
4. Linking reflections to training recommendations
"""

from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


async def get_games_needing_reflection(db, user_id: str, limit: int = 5) -> List[Dict]:
    """
    Get games that need reflection - recently analyzed but not yet reflected on.
    Prioritizes most recent games (memory freshness).
    """
    # Find analyzed games that haven't been fully reflected on
    pipeline = [
        {
            "$match": {
                "user_id": user_id,
                "is_analyzed": True
            }
        },
        {
            "$lookup": {
                "from": "game_analyses",
                "localField": "game_id",
                "foreignField": "game_id",
                "as": "analysis"
            }
        },
        {
            "$unwind": {
                "path": "$analysis",
                "preserveNullAndEmptyArrays": True
            }
        },
        {
            "$lookup": {
                "from": "reflections",
                "let": {"gid": "$game_id"},
                "pipeline": [
                    {"$match": {"$expr": {"$eq": ["$game_id", "$$gid"]}}},
                    {"$count": "total"}
                ],
                "as": "reflection_count"
            }
        },
        {
            "$addFields": {
                "reflected_moments": {
                    "$ifNull": [{"$arrayElemAt": ["$reflection_count.total", 0]}, 0]
                }
            }
        },
        # Only get games with critical moments that need reflection
        {
            "$match": {
                "$or": [
                    {"analysis.blunders": {"$gt": 0}},
                    {"analysis.mistakes": {"$gt": 0}}
                ]
            }
        },
        {
            "$sort": {"analysis.created_at": -1}
        },
        {
            "$limit": limit
        },
        {
            "$project": {
                "_id": 0,
                "game_id": 1,
                "user_color": 1,
                "result": 1,
                "white_player": 1,
                "black_player": 1,
                "time_control": 1,
                "platform": 1,
                "date_played": 1,
                "analysis": {
                    "blunders": "$analysis.blunders",
                    "mistakes": "$analysis.mistakes",
                    "accuracy": "$analysis.accuracy",
                    "created_at": "$analysis.created_at"
                },
                "reflected_moments": 1
            }
        }
    ]
    
    games = await db.games.aggregate(pipeline).to_list(limit)
    
    # Calculate hours ago and format response
    result = []
    now = datetime.now(timezone.utc)
    
    for game in games:
        # Calculate time since analysis
        analysis_time = game.get("analysis", {}).get("created_at")
        if isinstance(analysis_time, str):
            try:
                analysis_time = datetime.fromisoformat(analysis_time.replace('Z', '+00:00'))
            except:
                analysis_time = now - timedelta(hours=24)
        elif analysis_time is None:
            analysis_time = now - timedelta(hours=24)
        
        if analysis_time.tzinfo is None:
            analysis_time = analysis_time.replace(tzinfo=timezone.utc)
        
        hours_ago = (now - analysis_time).total_seconds() / 3600
        
        # Determine opponent
        user_color = game.get("user_color", "white")
        opponent = game.get("black_player") if user_color == "white" else game.get("white_player")
        
        # Determine user result
        raw_result = game.get("result", "")
        if user_color == "white":
            user_result = "win" if raw_result == "1-0" else ("loss" if raw_result == "0-1" else "draw")
        else:
            user_result = "win" if raw_result == "0-1" else ("loss" if raw_result == "1-0" else "draw")
        
        result.append({
            "game_id": game["game_id"],
            "user_color": user_color,
            "opponent_name": opponent or "Opponent",
            "result": user_result,
            "time_control": game.get("time_control", ""),
            "platform": game.get("platform", ""),
            "accuracy": game.get("analysis", {}).get("accuracy", 0),
            "blunders": game.get("analysis", {}).get("blunders", 0),
            "mistakes": game.get("analysis", {}).get("mistakes", 0),
            "hours_ago": round(hours_ago, 1),
            "reflected_moments": game.get("reflected_moments", 0)
        })
    
    return result


async def get_pending_reflection_count(db, user_id: str) -> int:
    """Get count of games needing reflection."""
    games = await get_games_needing_reflection(db, user_id, limit=20)
    # Only count games with un-reflected critical moments
    count = sum(1 for g in games if g.get("blunders", 0) + g.get("mistakes", 0) > g.get("reflected_moments", 0))
    return count


async def get_game_moments(db, user_id: str, game_id: str) -> List[Dict]:
    """
    Get critical moments from a game for reflection.
    Returns positions with blunders/mistakes that need user reflection.
    """
    # Get the game analysis
    analysis = await db.game_analyses.find_one(
        {"game_id": game_id, "user_id": user_id},
        {"_id": 0}
    )
    
    if not analysis:
        return []
    
    # Get existing reflections for this game
    existing_reflections = await db.reflections.find(
        {"game_id": game_id, "user_id": user_id},
        {"_id": 0, "moment_index": 1}
    ).to_list(100)
    reflected_indices = {r.get("moment_index") for r in existing_reflections}
    
    # Extract critical moments from analysis
    moments = []
    commentary = analysis.get("commentary", [])
    stockfish_data = analysis.get("stockfish_analysis", {})
    move_evals = stockfish_data.get("move_evaluations", [])
    
    # Create a lookup map for stockfish data
    sf_map = {m.get("move_number"): m for m in move_evals}
    
    moment_idx = 0
    for comment in commentary:
        eval_type = comment.get("evaluation", "")
        if eval_type in ["blunder", "mistake", "inaccuracy"]:
            move_num = comment.get("move_number")
            sf_data = sf_map.get(move_num, {})
            
            # Get FEN position before the move
            fen = sf_data.get("fen_before", "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")
            
            moments.append({
                "moment_index": moment_idx,
                "move_number": move_num,
                "type": eval_type,
                "fen": fen,
                "user_move": comment.get("move", ""),
                "best_move": sf_data.get("best_move", ""),
                "eval_before": sf_data.get("eval_before", 0),
                "eval_after": sf_data.get("eval_after", 0),
                "eval_change": (sf_data.get("eval_after", 0) - sf_data.get("eval_before", 0)) / 100,
                "cp_loss": sf_data.get("cp_loss", 0),
                "threat_line": sf_data.get("threat"),
                "feedback": comment.get("feedback", ""),
                "already_reflected": moment_idx in reflected_indices
            })
            moment_idx += 1
    
    # Filter out already reflected moments (optional - could show them greyed out instead)
    # For now, return all moments so user can see progress
    return moments


async def process_reflection(
    db, 
    user_id: str, 
    game_id: str, 
    moment_index: int,
    moment_fen: str,
    user_thought: str,
    user_move: str,
    best_move: str,
    eval_change: float
) -> Dict:
    """
    Process a user's reflection on a critical moment.
    Compares user's thought process with the actual situation.
    Returns awareness gap if detected.
    """
    from llm_service import call_llm
    
    # Save the reflection
    reflection_doc = {
        "user_id": user_id,
        "game_id": game_id,
        "moment_index": moment_index,
        "moment_fen": moment_fen,
        "user_thought": user_thought,
        "user_move": user_move,
        "best_move": best_move,
        "eval_change": eval_change,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    # Generate awareness gap analysis using LLM
    try:
        analysis_prompt = f"""Analyze this chess reflection and identify if there's an awareness gap.

Position FEN: {moment_fen}
User played: {user_move}
Better move was: {best_move}
Evaluation change: {eval_change:.1f} pawns

USER'S REFLECTION on what they were thinking:
"{user_thought}"

Your task:
1. Determine if the user's reflection shows they understood what went wrong
2. If there's an awareness gap (they missed something), explain it simply
3. Suggest a training focus if appropriate

Respond in JSON format:
{{
    "has_gap": true/false,
    "engine_insight": "What actually happened in the position (2 sentences max)",
    "gap_type": "tactical_blindness" | "positional_misunderstanding" | "calculation_error" | "pattern_missed" | "time_pressure" | "none",
    "training_hint": "Specific training recommendation if gap exists (1 sentence, or null)",
    "acknowledgment": "Brief validation of what they did recognize (1 sentence)"
}}"""

        response = await call_llm(
            system_message="You are a chess coach analyzing a student's reflection. Be supportive but honest.",
            user_message=analysis_prompt,
            model="gpt-4o-mini"
        )
        
        import json
        response_clean = response.strip()
        if response_clean.startswith("```json"):
            response_clean = response_clean[7:]
        if response_clean.startswith("```"):
            response_clean = response_clean[3:]
        if response_clean.endswith("```"):
            response_clean = response_clean[:-3]
        
        gap_analysis = json.loads(response_clean)
        reflection_doc["gap_analysis"] = gap_analysis
        
    except Exception as e:
        logger.error(f"Error analyzing reflection: {e}")
        gap_analysis = None
    
    # Save to database
    await db.reflections.insert_one(reflection_doc)
    
    # Update user's reflection stats
    await db.users.update_one(
        {"user_id": user_id},
        {
            "$inc": {"total_reflections": 1},
            "$set": {"last_reflection_at": datetime.now(timezone.utc).isoformat()}
        }
    )
    
    # Return awareness gap if detected
    if gap_analysis and gap_analysis.get("has_gap"):
        return {
            "awareness_gap": {
                "engine_insight": gap_analysis.get("engine_insight", ""),
                "gap_type": gap_analysis.get("gap_type", ""),
                "training_hint": gap_analysis.get("training_hint"),
                "acknowledgment": gap_analysis.get("acknowledgment", "")
            }
        }
    
    return {"awareness_gap": None}


async def mark_game_reflected(db, user_id: str, game_id: str) -> Dict:
    """Mark a game as fully reflected on."""
    await db.game_analyses.update_one(
        {"game_id": game_id, "user_id": user_id},
        {"$set": {"fully_reflected": True, "reflected_at": datetime.now(timezone.utc).isoformat()}}
    )
    return {"status": "ok"}
