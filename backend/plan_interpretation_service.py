"""
Plan Interpretation Service

This module interprets user's board moves to understand their ACTUAL intent.
It does NOT use LLM to guess - it uses chess analysis to determine what moves do.

Key principle: If user plays Bd3 attacking a knight, they wanted to attack/exchange the knight.
Don't let LLM make up "I wanted to support my center" nonsense.
"""

import chess
from typing import Dict, List, Optional
from position_analysis_service import parse_position, analyze_move
import logging

logger = logging.getLogger(__name__)


# Intent patterns based on what moves actually do
INTENT_PATTERNS = {
    "attacking_piece": {
        "pattern": "attack",
        "description": "I was trying to attack {target_piece} on {target_square}",
        "behavioral_tag": "aggressive_intent",
    },
    "exchanging_piece": {
        "pattern": "exchange", 
        "description": "I wanted to exchange my {piece} for their {target_piece}",
        "behavioral_tag": "simplification_intent",
    },
    "defending_piece": {
        "pattern": "defend",
        "description": "I was trying to defend my {defended_piece} on {defended_square}",
        "behavioral_tag": "defensive_intent",
    },
    "removing_threat": {
        "pattern": "remove_threat",
        "description": "I was worried about {threat_piece} on {threat_square} - it looked dangerous",
        "behavioral_tag": "threat_awareness",
    },
    "developing": {
        "pattern": "develop",
        "description": "I was developing my {piece} to a better square",
        "behavioral_tag": "development_intent",
    },
    "capturing": {
        "pattern": "capture",
        "description": "I captured the {captured_piece} on {capture_square}",
        "behavioral_tag": "material_intent",
    },
    "giving_check": {
        "pattern": "check",
        "description": "I was giving check with my {piece}",
        "behavioral_tag": "attacking_intent",
    },
}


def interpret_single_move(fen: str, move_san: str) -> Dict:
    """
    Interpret what a single move does and infer user intent.
    This is based on VERIFIED chess analysis, not LLM guessing.
    """
    analysis = analyze_move(fen, move_san)
    position = parse_position(fen)
    
    if "error" in analysis:
        return {"error": analysis["error"]}
    
    intents = []
    
    piece_moved = analysis.get("piece_moved", "piece")
    from_sq = analysis.get("from_square", "")
    to_sq = analysis.get("to_square", "")
    
    # Check if it's a capture
    if analysis.get("is_capture"):
        captured = analysis.get("captured_piece", "piece")
        intents.append({
            "type": "capturing",
            "description": f"I captured the {captured} on {to_sq}",
            "behavioral_tag": "material_intent",
            "target": captured,
            "target_square": to_sq,
        })
    
    # Check if it gives check
    if analysis.get("is_check"):
        intents.append({
            "type": "giving_check",
            "description": f"I was giving check with my {piece_moved}",
            "behavioral_tag": "attacking_intent",
            "piece": piece_moved,
        })
    
    # Check what pieces it attacks after the move
    attacks = analysis.get("attacks_after_move", [])
    for attack in attacks:
        target_piece = attack.get("piece", "piece")
        target_sq = attack.get("square", "")
        
        # Determine if this is attacking a valuable piece
        piece_value = {"pawn": 1, "knight": 3, "bishop": 3, "rook": 5, "queen": 9, "king": 100}
        target_value = piece_value.get(target_piece, 0)
        
        if target_value >= 3:  # Knight or better
            intents.append({
                "type": "attacking_piece",
                "description": f"I was trying to attack the {target_piece} on {target_sq}",
                "behavioral_tag": "aggressive_intent",
                "target": target_piece,
                "target_square": target_sq,
                "importance": "high" if target_value >= 5 else "medium",
            })
        elif target_value > 0:
            intents.append({
                "type": "attacking_piece", 
                "description": f"I was putting pressure on the {target_piece} on {target_sq}",
                "behavioral_tag": "pressure_intent",
                "target": target_piece,
                "target_square": target_sq,
                "importance": "low",
            })
    
    # Check what it defends
    defends = analysis.get("defends_after_move", [])
    for defend in defends:
        defended_piece = defend.get("piece", "piece")
        defended_sq = defend.get("square", "")
        intents.append({
            "type": "defending_piece",
            "description": f"I was defending my {defended_piece} on {defended_sq}",
            "behavioral_tag": "defensive_intent",
            "defended_piece": defended_piece,
            "defended_square": defended_sq,
        })
    
    # If no clear intent found, it's likely a developing/repositioning move
    if not intents:
        intents.append({
            "type": "developing",
            "description": f"I was repositioning my {piece_moved} to {to_sq}",
            "behavioral_tag": "development_intent",
            "piece": piece_moved,
        })
    
    return {
        "move": move_san,
        "piece_moved": piece_moved,
        "from": from_sq,
        "to": to_sq,
        "intents": intents,
        "primary_intent": intents[0] if intents else None,
    }


def interpret_plan(fen: str, moves: List[str], context: Dict = None) -> Dict:
    """
    Interpret a sequence of moves (user's plan) and understand their intent.
    
    Args:
        fen: Starting position
        moves: List of moves in SAN notation
        context: Optional context like user_move (what they actually played) and best_move
    
    Returns:
        Structured interpretation of the user's plan
    """
    if not moves:
        return {"error": "No moves provided"}
    
    try:
        board = chess.Board(fen)
    except Exception as e:
        return {"error": f"Invalid FEN: {e}"}
    
    interpretations = []
    current_fen = fen
    
    for move_san in moves:
        interp = interpret_single_move(current_fen, move_san)
        if "error" not in interp:
            interpretations.append(interp)
            
            # Update position for next move
            try:
                board = chess.Board(current_fen)
                move = board.parse_san(move_san)
                board.push(move)
                current_fen = board.fen()
            except Exception:
                break
    
    if not interpretations:
        return {"error": "Could not interpret any moves"}
    
    # Combine interpretations into a coherent thought
    all_intents = []
    for interp in interpretations:
        all_intents.extend(interp.get("intents", []))
    
    # Generate natural language thought based on ACTUAL intents
    thought_parts = []
    behavioral_tags = set()
    
    for interp in interpretations:
        primary = interp.get("primary_intent")
        if primary:
            thought_parts.append(primary["description"])
            behavioral_tags.add(primary["behavioral_tag"])
    
    # Build the final thought
    if thought_parts:
        thought = ". ".join(thought_parts) + "."
    else:
        thought = f"I was thinking about playing: {' '.join(moves)}"
    
    # Add context about WHY if we have the user's actual move and best move
    if context:
        user_move = context.get("user_move")
        best_move = context.get("best_move")
        
        if user_move and best_move:
            # Check if user was demonstrating a threat they were worried about
            first_move = moves[0] if moves else ""
            
            # Analyze what the first move attacks
            first_analysis = interpret_single_move(fen, first_move)
            first_primary = first_analysis.get("primary_intent", {})
            
            if first_primary.get("type") == "attacking_piece":
                target = first_primary.get("target", "piece")
                target_sq = first_primary.get("target_square", "")
                
                # Check if user was worried about this piece
                # If their actual move (user_move) also interacts with this piece, they were likely worried about it
                user_analysis = interpret_single_move(fen, user_move)
                user_attacks = [a.get("target_square") for a in user_analysis.get("intents", []) 
                               if a.get("type") == "attacking_piece"]
                
                if target_sq in user_attacks:
                    # User was worried about this piece - their move AND their plan both target it
                    thought = f"I was worried about the {target} on {target_sq} - it looked dangerous to me. " + thought
                    behavioral_tags.add("threat_concern")
    
    return {
        "moves": moves,
        "interpretations": interpretations,
        "thought": thought,
        "behavioral_tags": list(behavioral_tags),
        "all_intents": all_intents,
        "verified": True,  # This is based on actual chess analysis, not LLM
    }


def generate_reflection_from_plan(
    fen: str, 
    plan_moves: List[str],
    user_move: str,
    best_move: str,
    eval_change: float = 0.0
) -> Dict:
    """
    Generate a reflection from the user's demonstrated plan.
    This combines:
    1. What the user's plan moves actually do (verified)
    2. How it relates to their actual move
    3. What behavioral pattern this represents
    
    Returns a reflection suitable for training analysis.
    """
    # Interpret the plan
    context = {
        "user_move": user_move,
        "best_move": best_move,
        "eval_change": eval_change,
    }
    
    plan_interpretation = interpret_plan(fen, plan_moves, context)
    
    if "error" in plan_interpretation:
        return {
            "thought": f"I was thinking about: {' '.join(plan_moves)}",
            "behavioral_tags": ["unknown_intent"],
            "verified": False,
        }
    
    # Also analyze what the user actually played
    user_analysis = interpret_single_move(fen, user_move)
    user_intent = user_analysis.get("primary_intent", {})
    
    # Combine into final reflection
    thought = plan_interpretation.get("thought", "")
    behavioral_tags = plan_interpretation.get("behavioral_tags", [])
    
    # Add context about the actual move
    if user_intent:
        user_intent_desc = user_intent.get("description", "")
        if user_intent_desc and user_intent_desc not in thought:
            thought = thought + f" My actual move {user_move}: {user_intent_desc}."
            behavioral_tags.append(user_intent.get("behavioral_tag", ""))
    
    # Add evaluation context
    if eval_change < -1:
        thought = thought + f" But this cost me about {abs(eval_change):.1f} pawns."
    
    return {
        "thought": thought,
        "behavioral_tags": list(set(behavioral_tags)),
        "plan_interpretation": plan_interpretation,
        "user_move_interpretation": user_analysis,
        "verified": True,
    }
