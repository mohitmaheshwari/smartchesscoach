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
                "opponent_name": 1,
                "time_control": 1,
                "platform": 1,
                "date_played": 1,
                "analysis": {
                    "blunders": "$analysis.blunders",
                    "mistakes": "$analysis.mistakes",
                    "accuracy": {"$ifNull": ["$analysis.stockfish_analysis.accuracy", "$analysis.accuracy"]},
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
            except ValueError:
                analysis_time = now - timedelta(hours=24)
        elif analysis_time is None:
            analysis_time = now - timedelta(hours=24)
        
        if analysis_time.tzinfo is None:
            analysis_time = analysis_time.replace(tzinfo=timezone.utc)
        
        hours_ago = (now - analysis_time).total_seconds() / 3600
        
        # Determine opponent - check opponent_name first, then white/black_player
        user_color = game.get("user_color", "white")
        opponent = game.get("opponent_name")
        if not opponent:
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
    # Count games that have un-reflected critical moments
    count = len([g for g in games if g.get("blunders", 0) + g.get("mistakes", 0) > g.get("reflected_moments", 0)])
    return count


async def get_game_moments(db, user_id: str, game_id: str) -> List[Dict]:
    """
    Get critical moments from a game for reflection.
    Returns positions with blunders/mistakes that need user reflection.
    
    FILTERING RULES:
    1. Skip opening phase (moves 1-8) unless it's a major blunder (>200 cp)
    2. Only include blunders and mistakes (not inaccuracies)
    3. Require minimum centipawn loss to filter out theoretical preferences
    4. Limit to most critical moments (max 6 per game)
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
    
    # Filtering thresholds
    OPENING_PHASE_END = 8  # First 8 moves are "opening"
    OPENING_BLUNDER_THRESHOLD = 200  # Only flag opening moves if >200cp loss
    MIDDLEGAME_MIN_CP_LOSS = 50  # Minimum cp loss to consider for reflection
    
    moment_idx = 0
    for comment in commentary:
        eval_type = comment.get("evaluation", "")
        
        # Only include blunders and mistakes (skip inaccuracies - too minor)
        if eval_type not in ["blunder", "mistake"]:
            continue
            
        move_num = comment.get("move_number", 0)
        sf_data = sf_map.get(move_num, {})
        cp_loss = sf_data.get("cp_loss", 0)
        
        # Skip opening moves unless they're major blunders
        if move_num <= OPENING_PHASE_END:
            if cp_loss < OPENING_BLUNDER_THRESHOLD:
                logger.debug(f"Skipping move {move_num} - opening phase with only {cp_loss}cp loss")
                continue
        
        # Skip moves with very small cp loss (theoretical preferences, not mistakes)
        if cp_loss < MIDDLEGAME_MIN_CP_LOSS:
            logger.debug(f"Skipping move {move_num} - cp loss {cp_loss} below threshold")
            continue
        
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
            "cp_loss": cp_loss,
            "threat_line": sf_data.get("threat"),
            "feedback": comment.get("feedback", ""),
            "already_reflected": moment_idx in reflected_indices
        })
        moment_idx += 1
    
    # Sort by severity (highest cp_loss first) and limit to top 6
    moments.sort(key=lambda m: m["cp_loss"], reverse=True)
    moments = moments[:6]
    
    # Re-index after filtering
    for i, m in enumerate(moments):
        m["moment_index"] = i
    
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
    
    CRITICAL: Uses verified position analysis to prevent LLM hallucinations.
    """
    from llm_service import call_llm
    from position_analysis_service import generate_verified_insight, analyze_move
    
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
    
    # Get VERIFIED facts about what actually happened
    verified = generate_verified_insight(moment_fen, user_move, best_move, eval_change)
    user_analysis = verified.get("user_move_analysis", {})
    best_analysis = verified.get("best_move_analysis", {})
    
    # Build factual description of what each move does
    user_move_facts = []
    best_move_facts = []
    
    # User move facts (skip if move couldn't be parsed)
    if not user_analysis.get("error"):
        if user_analysis.get("is_capture"):
            user_move_facts.append(f"captures the {user_analysis.get('captured_piece')}")
        if user_analysis.get("is_check"):
            user_move_facts.append("gives check")
        if user_analysis.get("attacks_after_move"):
            attacks = [f"{a['piece']} on {a['square']}" for a in user_analysis["attacks_after_move"]]
            user_move_facts.append(f"attacks: {', '.join(attacks)}")
        if user_analysis.get("defends_after_move"):
            defends = [f"{d['piece']} on {d['square']}" for d in user_analysis["defends_after_move"][:2]]
            user_move_facts.append(f"defends: {', '.join(defends)}")
    
    # Best move facts (skip if move couldn't be parsed)
    if not best_analysis.get("error"):
        if best_analysis.get("is_capture"):
            best_move_facts.append(f"captures the {best_analysis.get('captured_piece')}")
        if best_analysis.get("is_check"):
            best_move_facts.append("gives check")
        if best_analysis.get("attacks_after_move"):
            attacks = [f"{a['piece']} on {a['square']}" for a in best_analysis["attacks_after_move"]]
            best_move_facts.append(f"attacks: {', '.join(attacks)}")
        if best_analysis.get("defends_after_move"):
            defends = [f"{d['piece']} on {d['square']}" for d in best_analysis["defends_after_move"][:2]]
            best_move_facts.append(f"defends: {', '.join(defends)}")
    else:
        best_move_facts.append("(analysis unavailable - engine suggested this move)")
    
    user_move_desc = "; ".join(user_move_facts) if user_move_facts else "repositions piece (no attacks or captures)"
    best_move_desc = "; ".join(best_move_facts) if best_move_facts else "repositions piece (no attacks or captures)"
    
    # Log the verified facts for debugging
    logger.info(f"Reflection analysis - User move {user_move}: {user_move_desc}")
    logger.info(f"Reflection analysis - Best move {best_move}: {best_move_desc}")
    
    # Generate awareness gap analysis using LLM with VERIFIED FACTS
    try:
        analysis_prompt = f"""Analyze this chess reflection. You must use ONLY the verified facts below.

VERIFIED FACTS FROM POSITION ANALYSIS:
- User played: {user_move}
  Effect: {user_move_desc}
- Better move was: {best_move}  
  Effect: {best_move_desc}
- Evaluation lost: {abs(eval_change):.1f} pawns

USER'S STATED THINKING:
"{user_thought}"

RULES (CRITICAL - VIOLATION CAUSES HARM):
1. ONLY mention attacks/captures/defends that are listed in "Effect" above
2. If "Effect" says "repositions piece" - do NOT claim it attacks or captures anything
3. Never say a move "attacks" something unless that attack is explicitly listed
4. Compare user's thinking to the verified effects, not to imagined chess logic

Respond in JSON:
{{
    "has_gap": true/false,
    "engine_insight": "Describe what happened using ONLY the effects listed above (2 sentences max)",
    "gap_type": "tactical_blindness" | "positional_misunderstanding" | "calculation_error" | "none",
    "training_hint": "Training suggestion if gap exists (1 sentence, or null)",
    "acknowledgment": "What the user correctly identified (1 sentence)"
}}
}}"""

        response = await call_llm(
            system_message="You are a chess coach. CRITICAL: You can ONLY reference attacks, captures, or defends that are explicitly listed in the VERIFIED FACTS. If something is not listed, it does not exist. Never invent chess logic.",
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
    
    # CRITICAL: Process reflection impact on training
    # This makes reflections actually affect what you train
    try:
        from reflection_training_service import process_reflection_impact
        gap_type = gap_analysis.get("gap_type") if gap_analysis else None
        training_impact = await process_reflection_impact(
            db,
            user_id,
            user_thought,
            tags=[],  # Tags could be extracted from user_thought
            gap_type=gap_type
        )
        logger.info(f"Reflection impact: {training_impact}")
    except Exception as e:
        logger.error(f"Error processing training impact: {e}")
        training_impact = None
    
    # Return awareness gap if detected
    if gap_analysis and gap_analysis.get("has_gap"):
        result = {
            "awareness_gap": {
                "engine_insight": gap_analysis.get("engine_insight", ""),
                "gap_type": gap_analysis.get("gap_type", ""),
                "training_hint": gap_analysis.get("training_hint"),
                "acknowledgment": gap_analysis.get("acknowledgment", "")
            }
        }
        # Add training impact info
        if training_impact and training_impact.get("suggestion"):
            result["training_suggestion"] = training_impact["suggestion"]
        return result
    
    return {"awareness_gap": None}


async def mark_game_reflected(db, user_id: str, game_id: str) -> Dict:
    """Mark a game as fully reflected on."""
    await db.game_analyses.update_one(
        {"game_id": game_id, "user_id": user_id},
        {"$set": {"fully_reflected": True, "reflected_at": datetime.now(timezone.utc).isoformat()}}
    )
    return {"status": "ok"}


def generate_contextual_tags(fen: str, user_move: str, best_move: str, eval_change: float) -> Dict:
    """
    Generate contextual quick-tag options based on chess position analysis.
    
    PRINCIPLE: Only generate tags we can genuinely infer from the position.
    If we can't understand user's intent, say so honestly.
    
    Returns:
        {
            "tags": ["I wanted to attack the knight on e4", ...],
            "could_not_infer": bool,  # True if we couldn't understand intent
            "inferred_intent": str or None  # Primary inferred intent
        }
    """
    from position_analysis_service import parse_position, analyze_move
    
    tags = []
    inferred_intent = None
    could_not_infer = False
    
    try:
        # Analyze the position
        position = parse_position(fen)
        if "error" in position:
            return {"tags": [], "could_not_infer": True, "reason": "Invalid position"}
        
        # Analyze what the user's move actually does
        user_analysis = analyze_move(fen, user_move)
        if "error" in user_analysis:
            return {"tags": [], "could_not_infer": True, "reason": "Could not analyze move"}
        
        # Analyze what the best move does (for comparison)
        best_analysis = analyze_move(fen, best_move) if best_move else {}
        
        piece_moved = user_analysis.get("piece_moved", "piece")
        
        # === Generate tags based on WHAT THE MOVE ACTUALLY DOES ===
        
        # 1. If it's a capture
        if user_analysis.get("is_capture"):
            captured = user_analysis.get("captured_piece", "piece")
            tags.append(f"I wanted to capture the {captured}")
            inferred_intent = f"capture the {captured}"
        
        # 2. If it gives check
        if user_analysis.get("is_check"):
            tags.append("I was trying to give check")
            if not inferred_intent:
                inferred_intent = "give check"
        
        # 3. What it attacks after the move
        attacks = user_analysis.get("attacks_after_move", [])
        valuable_attacks = []
        
        for attack in attacks:
            target_piece = attack.get("piece", "piece")
            target_sq = attack.get("square", "")
            
            # Check for attacks on valuable pieces
            if target_piece in ["knight", "bishop", "rook", "queen"]:
                tag = f"I wanted to attack the {target_piece} on {target_sq}"
                if tag not in tags:
                    tags.append(tag)
                    valuable_attacks.append(target_sq)
                    if not inferred_intent:
                        inferred_intent = f"attack the {target_piece} on {target_sq}"
            
            # Check for attacks on weak squares (f7/f2 - common mating patterns)
            elif target_sq in ["f7", "f2"]:
                tag = "I was attacking the weak f7/f2 square"
                if tag not in tags:
                    tags.append(tag)
                    valuable_attacks.append(target_sq)
                    if not inferred_intent:
                        inferred_intent = "attack the weak pawn on f7"
            
            # Check for attacks on e5/e4 (center pawns)  
            elif target_piece == "pawn" and target_sq in ["e4", "e5", "d4", "d5"]:
                tag = f"I was putting pressure on the center pawn on {target_sq}"
                if tag not in tags and len(tags) < 3:
                    tags.append(tag)
        
        # 4. What it defends (only add if not dominated by attacks)
        defends = user_analysis.get("defends_after_move", [])
        if defends and len(valuable_attacks) == 0:
            defended_piece = defends[0].get("piece", "piece")
            defended_sq = defends[0].get("square", "")
            tags.append(f"I was defending my {defended_piece} on {defended_sq}")
        
        # 5. If there's a hanging piece nearby user might have been worried about
        hanging = position.get("hanging_pieces", [])
        user_color = "white" if "w" in fen.split()[1] else "black"
        
        # Check opponent's hanging pieces (potential targets user saw)
        opponent_hanging = [h for h in hanging if h.get("color") != user_color]
        if opponent_hanging:
            piece = opponent_hanging[0].get("piece", "piece")
            sq = opponent_hanging[0].get("square", "")
            tag = f"I saw the {piece} on {sq} was undefended"
            if tag not in tags:
                tags.append(tag)
        
        # 6. Check what threat the best move addresses that user missed
        if best_analysis and not best_analysis.get("error"):
            best_attacks = best_analysis.get("attacks_after_move", [])
            user_attack_squares = {a.get("square") for a in attacks}
            
            for best_attack in best_attacks:
                target_piece = best_attack.get("piece", "piece")
                target_sq = best_attack.get("square", "")
                if target_sq not in user_attack_squares and target_piece in ["knight", "bishop", "rook", "queen", "king"]:
                    # User missed this target - they might have been unaware
                    tag = f"I didn't notice the {target_piece} on {target_sq}"
                    if tag not in tags:
                        tags.append(tag)
                    break  # Only add one "didn't notice" tag
        
        # 7. Development move (if no clear tactical intent)
        if not tags:
            if piece_moved in ["knight", "bishop"]:
                tags.append(f"I was developing my {piece_moved}")
                inferred_intent = f"develop the {piece_moved}"
            elif piece_moved == "pawn":
                tags.append("I was trying to control space")
                inferred_intent = "control space"
            else:
                tags.append(f"I was repositioning my {piece_moved}")
                inferred_intent = f"reposition the {piece_moved}"
        
        # === If we couldn't infer anything meaningful ===
        if not tags:
            could_not_infer = True
        
        # Limit to top 5 most relevant tags
        tags = tags[:5]
        
        return {
            "tags": tags,
            "could_not_infer": could_not_infer,
            "inferred_intent": inferred_intent
        }
        
    except Exception as e:
        logger.error(f"Error generating contextual tags: {e}")
        return {
            "tags": [],
            "could_not_infer": True,
            "reason": str(e)
        }
