"""
Thinking Coach Service
======================

Teaches players HOW to think, not just WHAT to play.

This service generates:
1. Thought process walkthroughs - How a strong player thinks in this position
2. Principle-based feedback - Connects mistakes to fundamental principles
3. Pattern mindset prompts - Questions based on position characteristics
4. Behavioral interventions - Specific thinking habits based on diagnosed patterns

The goal is to transform knowledge into active thinking habits.
"""

import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum
import chess

logger = logging.getLogger(__name__)


class ThinkingPhase(str, Enum):
    """Phases of the thinking process."""
    ASSESS_THREATS = "assess_threats"
    CHECK_KING_SAFETY = "check_king_safety"
    IDENTIFY_TARGETS = "identify_targets"
    CALCULATE_TACTICS = "calculate_tactics"
    EVALUATE_STRUCTURE = "evaluate_structure"
    CHOOSE_PLAN = "choose_plan"
    VERIFY_MOVE = "verify_move"


@dataclass
class ThinkingStep:
    """A step in the thinking process."""
    phase: ThinkingPhase
    question: str
    observation: str
    conclusion: str
    importance: str  # "critical", "important", "contextual"


THINKING_PROCESS_TEMPLATES = {
    "opening": {
        "phases": [
            ThinkingPhase.ASSESS_THREATS,
            ThinkingPhase.CHECK_KING_SAFETY,
            ThinkingPhase.CHOOSE_PLAN
        ],
        "focus": "development and center control"
    },
    "middlegame": {
        "phases": [
            ThinkingPhase.ASSESS_THREATS,
            ThinkingPhase.CHECK_KING_SAFETY,
            ThinkingPhase.IDENTIFY_TARGETS,
            ThinkingPhase.CALCULATE_TACTICS,
            ThinkingPhase.CHOOSE_PLAN,
            ThinkingPhase.VERIFY_MOVE
        ],
        "focus": "tactics and planning"
    },
    "endgame": {
        "phases": [
            ThinkingPhase.ASSESS_THREATS,
            ThinkingPhase.EVALUATE_STRUCTURE,
            ThinkingPhase.CHOOSE_PLAN
        ],
        "focus": "king activity and pawn structure"
    }
}


PHASE_QUESTIONS = {
    ThinkingPhase.ASSESS_THREATS: {
        "question": "What is my opponent threatening?",
        "follow_ups": [
            "Is any of my pieces attacked?",
            "Is there a tactical threat (fork, pin, skewer)?",
            "What was the idea behind my opponent's last move?"
        ]
    },
    ThinkingPhase.CHECK_KING_SAFETY: {
        "question": "Is my king safe?",
        "follow_ups": [
            "Are there any back-rank weaknesses?",
            "Can my opponent open lines toward my king?",
            "Do I need to defend or can I attack?"
        ]
    },
    ThinkingPhase.IDENTIFY_TARGETS: {
        "question": "What are the weaknesses in my opponent's position?",
        "follow_ups": [
            "Are there any undefended pieces?",
            "Are there weak pawns or squares?",
            "Is the enemy king exposed?"
        ]
    },
    ThinkingPhase.CALCULATE_TACTICS: {
        "question": "Are there any forcing moves?",
        "follow_ups": [
            "Can I give check?",
            "Can I win material?",
            "Are there any in-between moves (zwischenzug)?"
        ]
    },
    ThinkingPhase.EVALUATE_STRUCTURE: {
        "question": "What does the pawn structure tell me?",
        "follow_ups": [
            "Which pieces are best for this structure?",
            "Are there outposts for my pieces?",
            "What is the long-term plan?"
        ]
    },
    ThinkingPhase.CHOOSE_PLAN: {
        "question": "What is my plan for the next few moves?",
        "follow_ups": [
            "What pieces need to be improved?",
            "Which squares should I control?",
            "How do I make progress?"
        ]
    },
    ThinkingPhase.VERIFY_MOVE: {
        "question": "Does my chosen move leave any weaknesses?",
        "follow_ups": [
            "What will my opponent's best reply be?",
            "Does it blunder anything?",
            "Is there a better move I'm missing?"
        ]
    }
}


# Principle mappings - connect mistakes to fundamental principles
MISTAKE_TO_PRINCIPLE = {
    "hanging_piece": {
        "principle": "Safety First",
        "explanation": "Before every move, check if any of your pieces become undefended.",
        "thinking_habit": "Before finalizing your move, scan the board: 'Is everything still protected?'"
    },
    "missed_tactic": {
        "principle": "Checks, Captures, Threats",
        "explanation": "Always look for forcing moves - checks, captures, and threats - before quiet moves.",
        "thinking_habit": "Start each turn by asking: 'Are there any checks? Any captures that win material?'"
    },
    "positional_error": {
        "principle": "Piece Activity",
        "explanation": "Every move should improve your position. Aimless moves let your opponent take over.",
        "thinking_habit": "Ask: 'What does this move accomplish? Does it improve a piece or weaken my opponent?'"
    },
    "time_trouble": {
        "principle": "Time Management",
        "explanation": "Don't spend all your time on one move. Trust your preparation.",
        "thinking_habit": "Set time milestones: Move 10 by 50%, Move 20 by 70% of your time."
    },
    "overconfidence": {
        "principle": "Respect the Position",
        "explanation": "Even winning positions require careful play. Don't relax until checkmate.",
        "thinking_habit": "Ask yourself: 'What's the worst my opponent can do right now?'"
    },
    "defensive_lapse": {
        "principle": "Defense is Offense",
        "explanation": "Good defense creates counterattacking opportunities.",
        "thinking_habit": "When defending, look for active defensive moves that create threats."
    },
    "development_neglect": {
        "principle": "Develop with Purpose",
        "explanation": "Every piece should join the fight. Undeveloped pieces can't help you.",
        "thinking_habit": "In the opening, ask: 'How many pieces have I developed? Can I castle?'"
    },
    "king_safety_neglect": {
        "principle": "King Safety is Priority",
        "explanation": "Your king is your most valuable piece. Keep it safe before anything else.",
        "thinking_habit": "Before any aggressive move, check: 'Is my king safe from counterattack?'"
    }
}


# Behavioral interventions based on diagnosed patterns
BEHAVIORAL_INTERVENTIONS = {
    "hope_chess": {
        "diagnosis": "Playing moves without checking opponent responses",
        "intervention": "After each candidate move, ALWAYS ask: 'What is my opponent's best reply?'",
        "practice_rule": "Never play a move until you've considered at least one opponent response."
    },
    "impulsive_play": {
        "diagnosis": "Moving too quickly without proper analysis",
        "intervention": "Before every move, count to 5 and verify your move doesn't blunder.",
        "practice_rule": "Use 'blunder check': Is anything hanging after this move?"
    },
    "tunnel_vision": {
        "diagnosis": "Focusing on one part of the board while ignoring threats elsewhere",
        "intervention": "Scan the ENTIRE board before finalizing your move.",
        "practice_rule": "Look at all your opponent's pieces before moving."
    },
    "passive_play": {
        "diagnosis": "Making defensive moves without creating counterplay",
        "intervention": "Even when defending, look for active moves that create threats.",
        "practice_rule": "Ask: 'Is there a way to defend while also threatening something?'"
    },
    "overextension": {
        "diagnosis": "Attacking without enough support or development",
        "intervention": "Before attacking, count how many pieces are supporting vs defending.",
        "practice_rule": "Don't attack with fewer than 3 pieces participating."
    },
    "material_obsession": {
        "diagnosis": "Grabbing material at the cost of position or king safety",
        "intervention": "Before capturing, ask: 'What am I giving up to take this?'",
        "practice_rule": "Position and initiative often matter more than a pawn."
    }
}


def generate_thought_process_walkthrough(
    fen: str,
    best_move: str,
    played_move: str = None,
    player_level: str = "intermediate",
    position_context: Dict = None
) -> Dict[str, Any]:
    """
    Generate a step-by-step thought process walkthrough for a position.
    
    Shows how a strong player would think through this position.
    """
    board = chess.Board(fen)
    
    # Determine game phase
    piece_count = len(board.piece_map())
    move_number = board.fullmove_number
    
    if move_number <= 10:
        phase = "opening"
    elif piece_count > 14:
        phase = "middlegame"
    else:
        phase = "endgame"
    
    template = THINKING_PROCESS_TEMPLATES[phase]
    walkthrough = []
    
    # Generate thinking steps based on the position
    for thinking_phase in template["phases"]:
        phase_data = PHASE_QUESTIONS[thinking_phase]
        
        step = {
            "phase": thinking_phase.value,
            "question": phase_data["question"],
            "observation": _analyze_position_for_phase(board, thinking_phase, position_context),
            "follow_up": phase_data["follow_ups"][0] if phase_data["follow_ups"] else None
        }
        walkthrough.append(step)
    
    # Generate the conclusion - why the best move is best
    conclusion = _generate_conclusion(board, best_move, played_move, walkthrough)
    
    return {
        "phase": phase,
        "focus": template["focus"],
        "walkthrough": walkthrough,
        "conclusion": conclusion,
        "best_move": best_move,
        "played_move": played_move,
        "key_takeaway": _generate_key_takeaway(walkthrough, played_move, best_move)
    }


def _analyze_position_for_phase(board: chess.Board, phase: ThinkingPhase, context: Dict = None) -> str:
    """Generate observation for a thinking phase based on the position."""
    
    if phase == ThinkingPhase.ASSESS_THREATS:
        # Look for attacks
        threats = []
        for square, piece in board.piece_map().items():
            if piece.color != board.turn:
                attackers = board.attackers(board.turn, square)
                if attackers:
                    threats.append(f"{chess.piece_name(piece.piece_type)} on {chess.square_name(square)} is attacked")
        
        if threats:
            return f"I see: {'; '.join(threats[:2])}"
        return "No immediate threats from my opponent."
    
    elif phase == ThinkingPhase.CHECK_KING_SAFETY:
        king_square = board.king(board.turn)
        if king_square:
            attackers = board.attackers(not board.turn, king_square)
            if board.has_castling_rights(board.turn):
                return "My king hasn't castled yet - I should consider castling soon."
            elif len(attackers) > 0:
                return "My king is under attack - I need to deal with this first!"
            else:
                return "My king seems reasonably safe for now."
        return "Checking king safety..."
    
    elif phase == ThinkingPhase.IDENTIFY_TARGETS:
        targets = []
        for square, piece in board.piece_map().items():
            if piece.color != board.turn:
                defenders = board.attackers(not board.turn, square)
                if len(defenders) == 0:
                    targets.append(f"undefended {chess.piece_name(piece.piece_type)} on {chess.square_name(square)}")
        
        if targets:
            return f"Potential targets: {', '.join(targets[:2])}"
        return "Looking for weaknesses in opponent's position..."
    
    elif phase == ThinkingPhase.CALCULATE_TACTICS:
        checks = [m for m in board.legal_moves if board.gives_check(m)]
        captures = [m for m in board.legal_moves if board.is_capture(m)]
        
        if checks:
            return f"I can give check with {len(checks)} move(s) - let me calculate..."
        if captures:
            return f"There are {len(captures)} capture(s) to consider."
        return "No immediate forcing moves - focusing on positional play."
    
    elif phase == ThinkingPhase.EVALUATE_STRUCTURE:
        # Simple pawn structure assessment
        white_pawns = len([s for s, p in board.piece_map().items() if p.piece_type == chess.PAWN and p.color])
        black_pawns = len([s for s, p in board.piece_map().items() if p.piece_type == chess.PAWN and not p.color])
        return f"Pawn structure: {'balanced' if abs(white_pawns - black_pawns) <= 1 else 'imbalanced'}. Looking for outposts and weak squares..."
    
    elif phase == ThinkingPhase.CHOOSE_PLAN:
        return "Based on my analysis, I need to formulate a plan that improves my worst-placed piece or creates a concrete threat."
    
    elif phase == ThinkingPhase.VERIFY_MOVE:
        return "Before I play my chosen move, let me double-check it doesn't leave anything hanging."
    
    return "Analyzing position..."


def _generate_conclusion(board: chess.Board, best_move: str, played_move: str, walkthrough: List) -> str:
    """Generate conclusion about why the best move is best."""
    
    try:
        move = board.parse_san(best_move)
        is_capture = board.is_capture(move)
        gives_check = board.gives_check(move)
        
        reasons = []
        if gives_check:
            reasons.append("it gives check")
        if is_capture:
            piece = board.piece_at(move.to_square)
            if piece:
                reasons.append(f"it wins the {chess.piece_name(piece.piece_type)}")
        
        if not reasons:
            # It's a positional move
            reasons.append("it improves my position")
        
        base = f"The best move is {best_move} because {' and '.join(reasons)}."
        
        if played_move and played_move != best_move:
            base += f" The move {played_move} was played instead."
        
        return base
    except Exception:
        return f"The best move in this position is {best_move}."


def _generate_key_takeaway(walkthrough: List, played_move: str, best_move: str) -> str:
    """Generate a memorable takeaway from this thinking process."""
    
    if played_move and played_move != best_move:
        return "Remember: Always verify your move doesn't leave weaknesses before playing it."
    return "Good chess comes from systematic thinking - follow the process!"


def get_principle_based_feedback(
    mistake_type: str,
    fen: str,
    move_played: str,
    best_move: str
) -> Dict[str, Any]:
    """
    Connect a mistake to a fundamental principle.
    
    Instead of just saying "this was wrong", explain WHY and give a thinking habit.
    """
    principle_data = MISTAKE_TO_PRINCIPLE.get(mistake_type, MISTAKE_TO_PRINCIPLE["positional_error"])
    
    return {
        "principle": principle_data["principle"],
        "explanation": principle_data["explanation"],
        "thinking_habit": principle_data["thinking_habit"],
        "applied_to_position": f"In this position, {principle_data['explanation'].lower().replace('.', '')} The move {move_played} violated this principle.",
        "what_to_do_instead": f"Before playing {move_played}, you should have asked: '{principle_data['thinking_habit']}' This would have led you to find {best_move}."
    }


def get_behavioral_intervention(
    behavioral_pattern: str,
    examples: List[Dict] = None
) -> Dict[str, Any]:
    """
    Get a specific intervention for a diagnosed behavioral pattern.
    
    Returns actionable thinking habits to break bad patterns.
    """
    intervention_data = BEHAVIORAL_INTERVENTIONS.get(
        behavioral_pattern, 
        BEHAVIORAL_INTERVENTIONS["hope_chess"]
    )
    
    result = {
        "pattern": behavioral_pattern,
        "diagnosis": intervention_data["diagnosis"],
        "intervention": intervention_data["intervention"],
        "practice_rule": intervention_data["practice_rule"],
        "examples": []
    }
    
    if examples:
        result["examples"] = examples[:3]  # Limit to 3 examples
    
    return result


def get_position_mindset_prompt(
    fen: str,
    position_characteristics: Dict = None
) -> Dict[str, Any]:
    """
    Generate mindset prompts based on position characteristics.
    
    E.g., "This position has a weak back rank. What should you be looking for?"
    """
    board = chess.Board(fen)
    prompts = []
    
    # Check for tactical themes
    if position_characteristics:
        if position_characteristics.get("back_rank_weakness"):
            prompts.append({
                "theme": "Back Rank Weakness",
                "prompt": "The back rank is weak. What checks or threats might exploit this?",
                "what_to_look_for": ["Back rank mate threats", "Rook lifts to the back rank", "Diversionary tactics"]
            })
        
        if position_characteristics.get("undefended_pieces"):
            prompts.append({
                "theme": "Loose Pieces",
                "prompt": "There are undefended pieces. How can you exploit them?",
                "what_to_look_for": ["Double attacks", "Discovered attacks", "Removing the defender"]
            })
        
        if position_characteristics.get("king_exposed"):
            prompts.append({
                "theme": "King Safety",
                "prompt": "The enemy king looks exposed. Is there a forcing sequence?",
                "what_to_look_for": ["Checks with tempo", "Opening lines toward the king", "Sacrifices to expose the king"]
            })
        
        if position_characteristics.get("pawn_break_available"):
            prompts.append({
                "theme": "Pawn Break",
                "prompt": "A pawn break is available. What does it achieve?",
                "what_to_look_for": ["Opening files for rooks", "Creating passed pawns", "Activating pieces"]
            })
    
    # Generic prompts based on piece positions
    if board.has_castling_rights(board.turn) and board.fullmove_number > 6:
        prompts.append({
            "theme": "Development",
            "prompt": "You still have castling rights. Should you castle now?",
            "what_to_look_for": ["King safety", "Rook activation", "Whether castling is safe"]
        })
    
    # If no specific prompts, give general middlegame prompt
    if not prompts:
        prompts.append({
            "theme": "General Assessment",
            "prompt": "Assess this position. What are your best pieces? Worst pieces?",
            "what_to_look_for": ["Piece activity", "Pawn structure", "King safety on both sides"]
        })
    
    return {
        "fen": fen,
        "prompts": prompts[:2],  # Limit to 2 prompts
        "recommended_thinking_time": 30 if len(prompts) > 1 else 15
    }


def get_pre_move_checklist(
    move_number: int,
    has_castled: bool,
    developed_pieces: int,
    player_weaknesses: List[str] = None
) -> List[Dict[str, Any]]:
    """
    Generate a pre-move checklist based on game state and player weaknesses.
    
    Returns prioritized checklist items for the player to consider before moving.
    """
    checklist = []
    
    # Phase-based checks
    if move_number <= 10:  # Opening
        if not has_castled and move_number >= 5:
            checklist.append({
                "id": "castle_check",
                "question": "Can I castle this move?",
                "priority": "high" if move_number >= 8 else "medium",
                "explanation": "Castling protects your king and activates your rook"
            })
        
        if developed_pieces < 3:
            checklist.append({
                "id": "development_check",
                "question": "Is there a piece I haven't developed?",
                "priority": "medium",
                "explanation": "Develop all minor pieces before attacking"
            })
        
        if move_number <= 5:
            checklist.append({
                "id": "center_check",
                "question": "Am I fighting for the center?",
                "priority": "low",
                "explanation": "Central control gives your pieces more power"
            })
    
    # Always include threat check
    if move_number >= 3:
        checklist.append({
            "id": "threat_check",
            "question": "What is my opponent threatening?",
            "priority": "high" if move_number > 10 else "medium",
            "explanation": "Always check opponent's threats before moving"
        })
    
    # Player-specific checks based on weaknesses
    if player_weaknesses:
        if "hope_chess" in player_weaknesses:
            checklist.insert(0, {
                "id": "response_check",
                "question": "What will my opponent do after this?",
                "priority": "high",
                "explanation": "You tend to play moves without considering responses",
                "is_personal": True
            })
        
        if "hanging_pieces" in player_weaknesses:
            checklist.insert(0, {
                "id": "blunder_check",
                "question": "Does this move leave anything undefended?",
                "priority": "high",
                "explanation": "Always verify nothing is hanging before moving",
                "is_personal": True
            })
    
    # Limit to top 3 most relevant
    return sorted(checklist, key=lambda x: {"high": 0, "medium": 1, "low": 2}[x["priority"]])[:3]
