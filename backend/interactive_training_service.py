"""
Interactive Training Service - Personalized Chess Learning

This service powers the Training page with:
1. Interactive puzzles from user's own mistakes
2. Pattern detection (what they struggle with)
3. Principle-based teaching
4. Opening-specific training

The goal: Help users actually FIX their problems, not just review them.
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime, timezone
import random
import chess

logger = logging.getLogger(__name__)


# ============================================================================
# CHESS PRINCIPLES DATABASE
# These are the "tricks" and principles we teach
# ============================================================================

TACTICAL_PRINCIPLES = {
    "knight_fork": {
        "name": "Knight Fork",
        "principle": "Knights can attack multiple pieces at once because they jump over pieces. Always check: where can the knight land that attacks 2+ pieces?",
        "quick_tip": "Before moving, scan for knight-jump squares that hit multiple targets.",
        "pattern_keywords": ["fork", "knight", "double attack"]
    },
    "back_rank_mate": {
        "name": "Back Rank Weakness",
        "principle": "If your king is trapped on the back rank with no escape squares, a rook or queen can deliver checkmate. Always give your king a 'luft' (escape square) with h3/h6 or g3/g6.",
        "quick_tip": "If your back rank is weak, prioritize creating an escape square.",
        "pattern_keywords": ["back rank", "mate", "luft", "escape"]
    },
    "hanging_piece": {
        "name": "Hanging Pieces",
        "principle": "A piece is 'hanging' when it's undefended and can be captured for free. Before EVERY move, ask: 'Does this leave any of my pieces undefended?'",
        "quick_tip": "After deciding your move, do a quick safety check on all your pieces.",
        "pattern_keywords": ["hanging", "undefended", "blunder", "free piece"]
    },
    "pin": {
        "name": "Pins",
        "principle": "A pin restricts a piece from moving because it would expose a more valuable piece behind it. Look for opportunities to pin pieces to the king or queen.",
        "quick_tip": "Pieces on the same line as the enemy king are potential pin targets.",
        "pattern_keywords": ["pin", "absolute pin", "relative pin"]
    },
    "discovered_attack": {
        "name": "Discovered Attack",
        "principle": "When you move a piece, you might 'discover' an attack from a piece behind it. These are powerful because you get two threats at once.",
        "quick_tip": "Look for pieces that are 'blocking' your bishops, rooks, or queen.",
        "pattern_keywords": ["discovered", "discovery", "uncover"]
    },
    "skewer": {
        "name": "Skewer",
        "principle": "A skewer is the opposite of a pin: you attack a valuable piece, and when it moves, you capture the piece behind it.",
        "quick_tip": "Look for enemy pieces lined up on ranks, files, or diagonals.",
        "pattern_keywords": ["skewer", "x-ray"]
    },
    "trapped_piece": {
        "name": "Trapped Piece",
        "principle": "A piece is trapped when it has no safe squares to move to. Knights and bishops in the corner are especially vulnerable.",
        "quick_tip": "Be careful about moving pieces to the edge of the board.",
        "pattern_keywords": ["trapped", "no escape", "trapped bishop", "trapped knight"]
    },
    "checkmate_pattern": {
        "name": "Checkmate Awareness",
        "principle": "Before every move, do a quick check: 'Does my move allow any checks? Could those checks be mate?' This 2-second habit prevents disasters.",
        "quick_tip": "Always check for checks before finalizing your move.",
        "pattern_keywords": ["checkmate", "mate", "mated"]
    }
}

POSITIONAL_PRINCIPLES = {
    "piece_activity": {
        "name": "Piece Activity",
        "principle": "Active pieces (controlling many squares) are worth more than passive pieces. Develop your pieces to active squares where they control the center.",
        "quick_tip": "Ask: 'What is this piece doing? Can it do more?'",
        "pattern_keywords": ["passive", "active", "activity", "development"]
    },
    "pawn_structure": {
        "name": "Pawn Structure",
        "principle": "Pawns can't move backward. Every pawn move permanently changes the position. Think twice before pushing pawns - especially those in front of your king.",
        "quick_tip": "Pawns moves are commitments. Make sure you're ready.",
        "pattern_keywords": ["pawn", "structure", "weakness", "doubled", "isolated"]
    },
    "king_safety": {
        "name": "King Safety",
        "principle": "Your king is the most important piece. In the opening/middlegame, castle early and keep pawns in front of your king. Don't open lines toward your own king.",
        "quick_tip": "Castle early, keep your king's shield intact.",
        "pattern_keywords": ["king", "safety", "castle", "exposed"]
    },
    "control_center": {
        "name": "Center Control",
        "principle": "The center (e4, d4, e5, d5) is the most important area. Pieces in the center control more squares and can reach both sides of the board quickly.",
        "quick_tip": "Control the center with pawns and pieces.",
        "pattern_keywords": ["center", "central", "e4", "d4"]
    }
}

OPENING_PRINCIPLES = {
    "development": {
        "name": "Develop Your Pieces",
        "principle": "In the opening, get your pieces out! Knights before bishops usually, castle quickly, connect your rooks. Don't move the same piece twice unless necessary.",
        "quick_tip": "Each move should develop a new piece or prepare castling.",
        "pattern_keywords": ["development", "develop", "opening"]
    },
    "dont_bring_queen_early": {
        "name": "Queen Safety in Opening",
        "principle": "Don't bring your queen out too early - it can be chased around by minor pieces, losing time. Develop knights and bishops first.",
        "quick_tip": "The queen usually develops after minor pieces.",
        "pattern_keywords": ["queen", "early queen", "queen out"]
    },
    "castle_early": {
        "name": "Castle Early",
        "principle": "Castling gets your king safe and connects your rooks. Try to castle within the first 10 moves if possible.",
        "quick_tip": "Aim to castle by move 10.",
        "pattern_keywords": ["castle", "castling", "king safety"]
    }
}


# ============================================================================
# PUZZLE GENERATION
# ============================================================================

async def get_user_puzzles(db, user_id: str, limit: int = 10) -> List[Dict]:
    """
    Get personalized puzzles from user's own mistakes.
    
    These are positions where:
    1. User made a mistake (cp_loss >= 100)
    2. There's a clear better move
    3. We can explain WHY it's better
    """
    from chess_verification_layer import get_critical_facts, verify_move
    
    # Get user's analyzed games
    pipeline = [
        {"$match": {"user_id": user_id, "is_analyzed": True}},
        {"$sort": {"date_played": -1}},
        {"$limit": 20},  # Recent games
        {
            "$lookup": {
                "from": "game_analyses",
                "localField": "game_id",
                "foreignField": "game_id",
                "as": "analysis"
            }
        },
        {"$unwind": {"path": "$analysis", "preserveNullAndEmptyArrays": True}}
    ]
    
    games = await db.games.aggregate(pipeline).to_list(20)
    
    puzzles = []
    
    for game in games:
        analysis = game.get("analysis", {})
        sf_analysis = analysis.get("stockfish_analysis", {})
        moves = sf_analysis.get("move_evaluations", [])
        user_color = game.get("user_color", "white")
        
        for move_data in moves:
            cp_loss = move_data.get("cp_loss", 0)
            
            # Only include significant mistakes
            if cp_loss < 100:
                continue
            
            fen = move_data.get("fen_before")
            user_move = move_data.get("move")
            best_move = move_data.get("best_move")
            move_number = move_data.get("move_number")
            
            if not all([fen, user_move, best_move]):
                continue
            
            # Get verified analysis
            try:
                critical_facts = get_critical_facts(fen, user_move, best_move, cp_loss)
                
                # Determine puzzle type and principle
                issue_type = critical_facts.get("primary_issue", "positional_error")
                principle = get_principle_for_issue(issue_type)
                
                puzzle = {
                    "id": f"{game.get('game_id')}_{move_number}",
                    "fen": fen,
                    "user_move": user_move,
                    "correct_move": best_move,
                    "move_number": move_number,
                    "cp_loss": cp_loss,
                    "game_id": game.get("game_id"),
                    "opponent": game.get("opponent_name", "Unknown"),
                    "user_color": user_color,
                    "issue_type": issue_type,
                    "principle": principle,
                    "critical_detail": critical_facts.get("primary_detail", ""),
                    "thinking_habit": critical_facts.get("thinking_habit", ""),
                    "source": "your_game",  # vs "community" later
                    "difficulty": classify_difficulty(cp_loss)
                }
                
                puzzles.append(puzzle)
                
                if len(puzzles) >= limit:
                    break
                    
            except Exception as e:
                logger.warning(f"Error processing puzzle: {e}")
                continue
        
        if len(puzzles) >= limit:
            break
    
    # Shuffle to mix different types
    random.shuffle(puzzles)
    
    return puzzles[:limit]


def get_principle_for_issue(issue_type: str) -> Dict:
    """Map issue type to teaching principle."""
    
    ISSUE_TO_PRINCIPLE = {
        "allows_mate_in_1": TACTICAL_PRINCIPLES["checkmate_pattern"],
        "allows_mate_in_2": TACTICAL_PRINCIPLES["checkmate_pattern"],
        "misses_mate_in_1": TACTICAL_PRINCIPLES["checkmate_pattern"],
        "misses_mate_in_2": TACTICAL_PRINCIPLES["checkmate_pattern"],
        "hangs_queen": TACTICAL_PRINCIPLES["hanging_piece"],
        "hangs_rook": TACTICAL_PRINCIPLES["hanging_piece"],
        "hangs_piece": TACTICAL_PRINCIPLES["hanging_piece"],
        "walks_into_fork": TACTICAL_PRINCIPLES["knight_fork"],
        "walks_into_pin": TACTICAL_PRINCIPLES["pin"],
        "misses_fork": TACTICAL_PRINCIPLES["knight_fork"],
        "misses_pin": TACTICAL_PRINCIPLES["pin"],
        "positional_error": POSITIONAL_PRINCIPLES["piece_activity"],
    }
    
    return ISSUE_TO_PRINCIPLE.get(issue_type, POSITIONAL_PRINCIPLES["piece_activity"])


def classify_difficulty(cp_loss: int) -> str:
    """Classify puzzle difficulty based on cp_loss."""
    if cp_loss >= 500:
        return "easy"  # Big blunder = easy to spot
    elif cp_loss >= 200:
        return "medium"
    else:
        return "hard"  # Subtle mistake


async def validate_puzzle_answer(
    db, 
    user_id: str, 
    puzzle_id: str, 
    user_answer: str, 
    correct_move: str,
    fen: str
) -> Dict:
    """
    Validate user's answer to a puzzle.
    
    Returns feedback with:
    - correct: bool
    - explanation: Why correct/incorrect
    - principle: The teaching point
    """
    from chess_verification_layer import verify_move, get_critical_facts
    
    # Normalize moves for comparison
    try:
        board = chess.Board(fen)
        user_move_obj = board.parse_san(user_answer)
        correct_move_obj = board.parse_san(correct_move)
        
        is_correct = user_move_obj == correct_move_obj
    except Exception:
        is_correct = user_answer.lower().strip() == correct_move.lower().strip()
    
    if is_correct:
        # User got it right!
        critical_facts = get_critical_facts(fen, user_answer, correct_move, 0)
        
        result = {
            "correct": True,
            "message": "Excellent! You found the best move.",
            "explanation": critical_facts.get("primary_detail", f"{correct_move} is the strongest continuation."),
            "principle": critical_facts.get("thinking_habit", ""),
            "next_action": "continue"
        }
    else:
        # User got it wrong - this is a TEACHING moment
        # Analyze what they played vs what's correct
        wrong_facts = get_critical_facts(fen, user_answer, correct_move, 100)
        correct_facts = get_critical_facts(fen, correct_move, correct_move, 0)
        
        result = {
            "correct": False,
            "message": f"Not quite. The best move was {correct_move}.",
            "user_move": user_answer,
            "correct_move": correct_move,
            "why_wrong": wrong_facts.get("primary_detail", ""),
            "why_correct": f"{correct_move} is better because it {correct_facts.get('primary_detail', 'improves your position')}",
            "principle": wrong_facts.get("thinking_habit", ""),
            "next_action": "learn"
        }
    
    # Record this attempt
    await db.training_attempts.insert_one({
        "user_id": user_id,
        "puzzle_id": puzzle_id,
        "user_answer": user_answer,
        "correct_answer": correct_move,
        "was_correct": is_correct,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })
    
    return result


# ============================================================================
# PATTERN DETECTION
# ============================================================================

async def get_user_weakness_patterns(db, user_id: str) -> Dict:
    """
    Analyze user's games to find their weakness patterns.
    
    Returns:
    - Top 3 tactical weaknesses
    - Top 3 positional weaknesses  
    - Most common mistake phase (opening/middlegame/endgame)
    """
    # Get recent analyses
    pipeline = [
        {"$match": {"user_id": user_id}},
        {"$sort": {"created_at": -1}},
        {"$limit": 20}
    ]
    
    analyses = await db.game_analyses.aggregate(pipeline).to_list(20)
    
    # Count mistake types
    phase_mistakes = {"opening": 0, "middlegame": 0, "endgame": 0}
    total_mistakes = 0
    
    for analysis in analyses:
        sf = analysis.get("stockfish_analysis", {})
        moves = sf.get("move_evaluations", [])
        
        for move in moves:
            cp_loss = move.get("cp_loss", 0)
            if cp_loss < 100:
                continue
            
            total_mistakes += 1
            move_num = move.get("move_number", 15)
            
            # Classify by phase
            if move_num <= 10:
                phase_mistakes["opening"] += 1
            elif move_num <= 30:
                phase_mistakes["middlegame"] += 1
            else:
                phase_mistakes["endgame"] += 1
    
    # Determine weakest phase
    weakest_phase = max(phase_mistakes, key=phase_mistakes.get) if total_mistakes > 0 else "middlegame"
    
    return {
        "total_mistakes_analyzed": total_mistakes,
        "phase_breakdown": phase_mistakes,
        "weakest_phase": weakest_phase,
        "recommendation": get_phase_recommendation(weakest_phase, phase_mistakes)
    }


def get_phase_recommendation(phase: str, counts: Dict) -> str:
    """Get training recommendation based on weakness."""
    
    recommendations = {
        "opening": "Focus on opening principles: develop pieces, control the center, castle early. Consider studying your most-played openings in depth.",
        "middlegame": "Work on tactical awareness: forks, pins, and hanging pieces. Before each move, ask 'What can my opponent do?'",
        "endgame": "Practice basic endgames: King + Pawn, Rook endgames. Endgame technique often decides close games."
    }
    
    return recommendations.get(phase, recommendations["middlegame"])


# ============================================================================
# OPENING TRAINER
# ============================================================================

async def get_user_openings(db, user_id: str) -> List[Dict]:
    """
    Analyze user's games to find their most played openings.
    """
    pipeline = [
        {"$match": {"user_id": user_id, "is_analyzed": True}},
        {"$group": {
            "_id": "$opening_name",
            "count": {"$sum": 1},
            "avg_accuracy": {"$avg": "$accuracy"},
            "as_white": {"$sum": {"$cond": [{"$eq": ["$user_color", "white"]}, 1, 0]}},
            "as_black": {"$sum": {"$cond": [{"$eq": ["$user_color", "black"]}, 1, 0]}}
        }},
        {"$sort": {"count": -1}},
        {"$limit": 10}
    ]
    
    openings = await db.games.aggregate(pipeline).to_list(10)
    
    result = []
    for opening in openings:
        name = opening.get("_id") or "Unknown Opening"
        result.append({
            "name": name,
            "games_played": opening.get("count", 0),
            "avg_accuracy": round(opening.get("avg_accuracy", 0) or 0, 1),
            "as_white": opening.get("as_white", 0),
            "as_black": opening.get("as_black", 0),
            "mastery_level": classify_opening_mastery(opening.get("count", 0), opening.get("avg_accuracy", 0))
        })
    
    return result


def classify_opening_mastery(games: int, accuracy: float) -> str:
    """Classify how well user knows an opening."""
    if games < 3:
        return "learning"
    elif accuracy >= 80 and games >= 10:
        return "mastered"
    elif accuracy >= 70:
        return "comfortable"
    else:
        return "needs_work"


# ============================================================================
# TRAINING PROGRESS
# ============================================================================

async def get_training_progress(db, user_id: str) -> Dict:
    """Get user's training progress and stats."""
    
    # Count puzzles attempted and solved
    pipeline = [
        {"$match": {"user_id": user_id}},
        {"$group": {
            "_id": None,
            "total_attempts": {"$sum": 1},
            "correct": {"$sum": {"$cond": ["$was_correct", 1, 0]}},
            "streak": {"$sum": 1}  # Would need more complex logic for actual streak
        }}
    ]
    
    stats = await db.training_attempts.aggregate(pipeline).to_list(1)
    
    if stats:
        s = stats[0]
        total = s.get("total_attempts", 0)
        correct = s.get("correct", 0)
        accuracy = round(correct / total * 100, 1) if total > 0 else 0
    else:
        total = 0
        correct = 0
        accuracy = 0
    
    return {
        "puzzles_attempted": total,
        "puzzles_solved": correct,
        "accuracy": accuracy,
        "current_streak": 0,  # TODO: Implement streak tracking
        "level": classify_training_level(total, accuracy)
    }


def classify_training_level(attempts: int, accuracy: float) -> str:
    """Classify user's training level."""
    if attempts < 10:
        return "beginner"
    elif attempts < 50 and accuracy >= 60:
        return "intermediate"
    elif attempts >= 50 and accuracy >= 75:
        return "advanced"
    else:
        return "intermediate"
