"""
Mistake Explanation Service - Educational Commentary for Chess Mistakes

Architecture:
- Our Chess Logic (Tags/Rules) → determines WHY the move is bad
- GPT → only writes the human-readable commentary based on those tags

This is a HYBRID approach:
1. Deterministic Analysis: We use mistake_classifier.py to identify WHAT happened
2. LLM Commentary: GPT takes these facts and writes an educational explanation

GPT DOES NOT:
- Decide if a move is a blunder/mistake/inaccuracy (Stockfish does)
- Identify tactical patterns (mistake_classifier does)
- Invent chess variations (we provide the engine lines)

GPT ONLY:
- Transforms structured tags into readable English
- Provides educational context ("in positions like this...")
- Suggests thinking habits to avoid the mistake
"""

import logging
from typing import Dict, Optional
import chess

from mistake_classifier import (
    MistakeType, GamePhase,
    find_hanging_pieces, find_forks, find_pins, find_skewers,
    find_discovered_attacks, find_overloaded_defenders,
    detect_walked_into_fork, detect_walked_into_pin,
    detect_missed_fork, detect_missed_pin,
    determine_phase, get_material_count
)

logger = logging.getLogger(__name__)


# ============================================
# EXPLANATION TEMPLATES - What each mistake type means
# ============================================

MISTAKE_TEMPLATES = {
    # Tactical pattern mistakes - Coach-style feedback
    "hanging_piece": {
        "short": "Piece left unprotected",
        "pattern": "That piece was left without backup. It happens to everyone!",
        "thinking_habit": "Quick tip: Before each move, do a 'safety scan' - which of your pieces are unguarded?",
        "severity": "material_loss"
    },
    "material_blunder": {
        "short": "Material slipped away",
        "pattern": "This one gave away some material. It's a great learning moment.",
        "thinking_habit": "Try this: After deciding your move, pause and ask 'What can they take next?'",
        "severity": "material_loss"
    },
    "walked_into_fork": {
        "short": "Double attack incoming",
        "pattern": "Two of your pieces ended up vulnerable to the same attack. Classic trap!",
        "thinking_habit": "Knight squares are sneaky - always check if they can hit two targets at once.",
        "severity": "tactical"
    },
    "walked_into_pin": {
        "short": "Created a pin situation",
        "pattern": "Your pieces lined up in a way that created a pin. Happens to the best of us!",
        "thinking_habit": "Watch out for pieces lining up on same files, ranks, or diagonals.",
        "severity": "tactical"
    },
    "walked_into_skewer": {
        "short": "Skewer opportunity given",
        "pattern": "A valuable piece ended up in front of another on the same line.",
        "thinking_habit": "Keep your heavy pieces (Queen, Rooks) spread out to avoid skewers.",
        "severity": "tactical"
    },
    "walked_into_discovered_attack": {
        "short": "Discovered attack set up",
        "pattern": "The opponent got to 'unmask' a hidden attacker. Tricky pattern!",
        "thinking_habit": "Look for enemy pieces that could reveal another attacker when they move.",
        "severity": "tactical"
    },
    "missed_fork": {
        "short": "Missed a fork",
        "pattern": "You had a chance to fork two pieces but played something else.",
        "thinking_habit": "Before each move, scan for fork opportunities.",
        "severity": "missed_tactic"
    },
    "missed_pin": {
        "short": "Missed a pin",
        "pattern": "You could have pinned an opponent's piece but didn't see it.",
        "thinking_habit": "Look for chances to immobilize pieces by pinning them.",
        "severity": "missed_tactic"
    },
    "missed_skewer": {
        "short": "Missed a skewer",
        "pattern": "You had a skewer available but didn't find it.",
        "thinking_habit": "When pieces line up, check for skewer potential.",
        "severity": "missed_tactic"
    },
    "missed_discovered_attack": {
        "short": "Missed a discovered attack",
        "pattern": "Moving one piece could have revealed an attack from another.",
        "thinking_habit": "Check if your pieces can 'unmask' attacks.",
        "severity": "missed_tactic"
    },
    "missed_winning_tactic": {
        "short": "Missed winning tactic",
        "pattern": "A winning tactical shot was available.",
        "thinking_habit": "Checks, captures, threats - scan in that order.",
        "severity": "missed_tactic"
    },
    "ignored_threat": {
        "short": "Ignored opponent's threat",
        "pattern": "Your opponent had a threat that you didn't address.",
        "thinking_habit": "Always ask: 'What is my opponent threatening?'",
        "severity": "threat_blindness"
    },
    
    # Positional/conversion mistakes
    "blunder_when_ahead": {
        "short": "Threw away the win",
        "pattern": "You were winning but relaxed and made a critical error.",
        "thinking_habit": "When ahead, play like you're still equal. Stay focused.",
        "severity": "conversion"
    },
    "failed_conversion": {
        "short": "Failed to convert advantage",
        "pattern": "You had a winning position but couldn't finish the game.",
        "thinking_habit": "In winning positions, simplify and trade down carefully.",
        "severity": "conversion"
    },
    
    # Phase-specific mistakes
    "opening_inaccuracy": {
        "short": "Opening inaccuracy",
        "pattern": "This move doesn't follow opening principles.",
        "thinking_habit": "Develop pieces, control center, castle early.",
        "severity": "positional"
    },
    "positional_drift": {
        "short": "Positional drift",
        "pattern": "Small inaccuracies accumulated, losing your advantage.",
        "thinking_habit": "Every few moves, reassess: What's the plan?",
        "severity": "positional"
    },
    "king_safety_error": {
        "short": "King safety issue",
        "pattern": "Your king became vulnerable.",
        "thinking_habit": "Keep your king safe - castle early and protect it.",
        "severity": "positional"
    },
    
    # Time-related
    "time_pressure_blunder": {
        "short": "Time pressure blunder",
        "pattern": "Under time pressure, you made a mistake.",
        "thinking_habit": "Budget time better in complex positions.",
        "severity": "time_management"
    },
    
    # Default/generic
    "inaccuracy": {
        "short": "Inaccuracy",
        "pattern": "A slightly imprecise move.",
        "thinking_habit": "Look for the most purposeful move each turn.",
        "severity": "minor"
    },
    "good_move": {
        "short": "Good move",
        "pattern": "Solid choice.",
        "thinking_habit": None,
        "severity": "none"
    },
}


def analyze_mistake_position(fen_before: str, move_played: str, best_move: str, 
                              cp_loss: int, user_color: str) -> Dict:
    """
    Analyze a mistake position to determine what went wrong.
    
    Returns structured tags that can be turned into an explanation.
    This is 100% DETERMINISTIC - no LLM involved.
    
    Args:
        fen_before: FEN position before the mistake
        move_played: The move the user played (SAN notation)
        best_move: The engine's best move (SAN notation)
        cp_loss: Centipawn loss (always positive)
        user_color: "white" or "black"
    
    Returns:
        Dict with tags describing the mistake
    """
    try:
        board = chess.Board(fen_before)
    except (ValueError, chess.InvalidFenError):
        return {
            "mistake_type": "inaccuracy",
            "details": {},
            "phase": "unknown",
            "error": "Invalid FEN"
        }
    
    color = chess.WHITE if user_color == "white" else chess.BLACK
    opponent = not color
    
    # Determine game phase
    phase = determine_phase(board)
    
    # Get position context
    was_in_check = board.is_check()
    
    # Eval context
    # Positive cp_loss means user lost centipawns
    severity = "minor"
    if cp_loss >= 300:
        severity = "blunder"
    elif cp_loss >= 100:
        severity = "mistake"
    elif cp_loss >= 50:
        severity = "inaccuracy"
    
    # Play the user's move to see the resulting position
    board_after = board.copy()
    try:
        board_after.push_san(move_played)
    except (ValueError, chess.IllegalMoveError, chess.InvalidMoveError):
        return {
            "mistake_type": "inaccuracy",
            "details": {},
            "phase": phase.value if hasattr(phase, 'value') else str(phase),
            "severity": severity,
            "error": "Could not parse move"
        }
    
    # Check for tactical patterns
    mistake_type = "inaccuracy"  # Default
    details = {}
    
    # 1. Check if walked into a fork
    walked_into_fork = detect_walked_into_fork(board, board_after, color)
    if walked_into_fork:
        mistake_type = "walked_into_fork"
        details["fork"] = walked_into_fork
    
    # 2. Check if walked into a pin
    if mistake_type == "inaccuracy":
        walked_into_pin = detect_walked_into_pin(board, board_after, color)
        if walked_into_pin:
            mistake_type = "walked_into_pin"
            details["pin"] = walked_into_pin
    
    # 3. Check for hanging pieces after the move
    if mistake_type == "inaccuracy":
        hanging = find_hanging_pieces(board_after, color)
        if hanging:
            highest_value = max(h["value"] for h in hanging)
            if highest_value >= 3:  # At least a minor piece
                mistake_type = "hanging_piece"
                details["hanging"] = hanging[0]
    
    # 4. Check if missed a fork with the best move
    if mistake_type == "inaccuracy" and best_move:
        missed_fork = detect_missed_fork(board, best_move, color)
        if missed_fork:
            mistake_type = "missed_fork"
            details["missed_fork"] = missed_fork
    
    # 5. Check if missed a pin with the best move
    if mistake_type == "inaccuracy" and best_move:
        missed_pin = detect_missed_pin(board, best_move, color)
        if missed_pin:
            mistake_type = "missed_pin"
            details["missed_pin"] = missed_pin
    
    # 6. Check for opponent threats that were ignored
    if mistake_type == "inaccuracy":
        # Get opponent's threatening moves BEFORE user's move
        board_opponent_turn = board.copy()
        board_opponent_turn.turn = opponent
        
        # Check if opponent can now execute a threat
        opponent_forks = find_forks(board_after, opponent)
        if opponent_forks and opponent_forks[0].get("includes_king") or (opponent_forks and opponent_forks[0].get("total_value", 0) >= 8):
            mistake_type = "ignored_threat"
            details["threat"] = f"Opponent has {opponent_forks[0]['attacker_piece']} fork"
    
    # 7. Determine if it's a conversion failure (was ahead, now not)
    # This would need eval_before which we don't have in this function
    # So we'll mark it based on phase and severity
    if severity == "blunder" and phase == GamePhase.ENDGAME:
        if mistake_type == "inaccuracy":
            mistake_type = "failed_conversion"
    
    # 8. Phase-specific defaults
    if mistake_type == "inaccuracy":
        if phase == GamePhase.OPENING and cp_loss >= 50:
            mistake_type = "opening_inaccuracy"
        elif cp_loss >= 50:
            mistake_type = "positional_drift"
    
    return {
        "mistake_type": mistake_type,
        "details": details,
        "phase": phase.value if hasattr(phase, 'value') else str(phase),
        "severity": severity,
        "was_in_check": was_in_check
    }


def build_explanation_prompt(analysis: Dict, move_data: Dict) -> str:
    """
    Build a prompt for GPT to generate the educational explanation.
    
    GPT's job is ONLY to write readable commentary - NOT to analyze chess.
    We provide all the facts, GPT makes them readable.
    """
    mistake_type = analysis.get("mistake_type", "inaccuracy")
    template = MISTAKE_TEMPLATES.get(mistake_type, MISTAKE_TEMPLATES["inaccuracy"])
    details = analysis.get("details", {})
    phase = analysis.get("phase", "middlegame")
    
    # Build the context for GPT
    context_parts = []
    
    # Move info
    context_parts.append(f"Move played: {move_data.get('move', '?')}")
    context_parts.append(f"Better move: {move_data.get('best_move', '?')}")
    context_parts.append(f"Centipawn loss: {move_data.get('cp_loss', 0)}")
    context_parts.append(f"Game phase: {phase}")
    
    # Pattern-specific details
    if mistake_type == "walked_into_fork" and details.get("fork"):
        fork = details["fork"]
        targets = fork.get("targets", [])
        target_desc = " and ".join([f"{t['piece']} on {t['square']}" for t in targets[:2]])
        context_parts.append(f"TACTICAL PATTERN: User walked into a {fork.get('attacker_piece', 'knight')} fork attacking {target_desc}")
    
    elif mistake_type == "walked_into_pin" and details.get("pin"):
        pin = details["pin"]
        context_parts.append(f"TACTICAL PATTERN: User created a pin - {pin.get('pinned_piece', 'piece')} is now pinned to the {pin.get('pinned_to', 'king')}")
    
    elif mistake_type == "hanging_piece" and details.get("hanging"):
        hanging = details["hanging"]
        context_parts.append(f"TACTICAL PATTERN: Left {hanging.get('piece', 'piece')} on {hanging.get('square', '?')} undefended")
    
    elif mistake_type == "missed_fork" and details.get("missed_fork"):
        fork = details["missed_fork"]
        targets = fork.get("targets", [])
        target_desc = " and ".join([f"{t['piece']}" for t in targets[:2]])
        context_parts.append(f"MISSED TACTIC: Could have forked {target_desc} with {fork.get('attacker_piece', 'knight')}")
    
    elif mistake_type == "missed_pin" and details.get("missed_pin"):
        pin = details["missed_pin"]
        context_parts.append(f"MISSED TACTIC: Could have pinned {pin.get('pinned_piece', 'piece')} to the {pin.get('pinned_to', 'king')}")
    
    elif mistake_type == "ignored_threat" and details.get("threat"):
        context_parts.append(f"IGNORED THREAT: {details['threat']}")
    
    # Template info
    context_parts.append(f"MISTAKE CATEGORY: {template['short']}")
    context_parts.append(f"PATTERN: {template['pattern']}")
    if template.get("thinking_habit"):
        context_parts.append(f"THINKING HABIT TO BUILD: {template['thinking_habit']}")
    
    context_str = "\n".join(context_parts)
    
    prompt = f"""You are a chess coach writing an educational explanation for a student's mistake.

FACTS ABOUT THIS MISTAKE (these are ACCURATE - do not contradict them):
{context_str}

YOUR TASK:
Write 2-3 sentences explaining WHY this move was a mistake and what the student should learn.

RULES:
1. Use simple, clear English (8th grade reading level)
2. Focus on the THINKING ERROR, not just the move
3. Be supportive, not harsh
4. Use the specific pattern/tactic information provided
5. End with a concrete tip the student can use in future games
6. Do NOT mention centipawns, engine scores, or technical jargon
7. Keep it under 60 words

Write the explanation now (no preamble, just the explanation):"""
    
    return prompt


async def generate_mistake_explanation(move_data: Dict, llm_call_func) -> Dict:
    """
    Generate an educational explanation for a mistake.
    
    This is the main entry point for the service.
    
    Args:
        move_data: Dict containing:
            - fen_before: FEN position before move
            - move: The move played (SAN)
            - best_move: The better move (SAN)
            - cp_loss: Centipawn loss
            - user_color: "white" or "black"
        llm_call_func: Async function to call LLM (from llm_service)
    
    Returns:
        Dict with:
            - explanation: Human-readable explanation
            - mistake_type: Category of mistake
            - thinking_habit: Suggestion for improvement
            - details: Tactical details if applicable
    """
    # Step 1: Deterministic analysis
    analysis = analyze_mistake_position(
        fen_before=move_data.get("fen_before", ""),
        move_played=move_data.get("move", ""),
        best_move=move_data.get("best_move", ""),
        cp_loss=move_data.get("cp_loss", 0),
        user_color=move_data.get("user_color", "white")
    )
    
    mistake_type = analysis.get("mistake_type", "inaccuracy")
    template = MISTAKE_TEMPLATES.get(mistake_type, MISTAKE_TEMPLATES["inaccuracy"])
    
    # Step 2: Generate explanation with LLM
    prompt = build_explanation_prompt(analysis, move_data)
    
    try:
        explanation = await llm_call_func(
            system_message="You are a friendly chess coach. Write short, educational explanations.",
            user_message=prompt,
            model="gpt-4o-mini"
        )
        explanation = explanation.strip()
    except Exception as e:
        logger.error(f"LLM call failed: {e}")
        # Fallback to template-based explanation
        explanation = f"{template['pattern']} {template.get('thinking_habit', '')}"
    
    return {
        "explanation": explanation,
        "mistake_type": mistake_type,
        "short_label": template.get("short", "Mistake"),
        "thinking_habit": template.get("thinking_habit"),
        "severity": analysis.get("severity", "minor"),
        "phase": analysis.get("phase", "middlegame"),
        "details": analysis.get("details", {})
    }


def get_quick_explanation(mistake_type: str, details: Dict = None) -> str:
    """
    Get a quick template-based explanation without LLM call.
    Use this for bulk operations or when LLM is unavailable.
    """
    template = MISTAKE_TEMPLATES.get(mistake_type, MISTAKE_TEMPLATES["inaccuracy"])
    
    explanation = template["pattern"]
    
    # Add specific details if available
    if details:
        if mistake_type == "walked_into_fork" and details.get("fork"):
            fork = details["fork"]
            targets = fork.get("targets", [])
            if targets:
                target_desc = " and ".join([t['piece'] for t in targets[:2]])
                explanation = f"Your move allowed opponent's {fork.get('attacker_piece', 'knight')} to fork your {target_desc}."
        
        elif mistake_type == "hanging_piece" and details.get("hanging"):
            hanging = details["hanging"]
            explanation = f"Your {hanging.get('piece', 'piece')} on {hanging.get('square', '')} was left undefended."
        
        elif mistake_type == "missed_fork" and details.get("missed_fork"):
            fork = details["missed_fork"]
            targets = fork.get("targets", [])
            if targets:
                target_desc = " and ".join([t['piece'] for t in targets[:2]])
                explanation = f"You could have forked {target_desc} with your {fork.get('attacker_piece', 'knight')}!"
    
    return explanation
