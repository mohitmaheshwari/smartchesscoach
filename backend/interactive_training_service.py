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
    from chess_verification_layer import get_critical_facts
    
    logger.info(f"Getting puzzles for user: {user_id}")
    
    # Query games that have been analyzed (have stockfish data)
    # First, get games from the game_analyses collection directly
    analyses = await db.game_analyses.find({"user_id": user_id}).sort("created_at", -1).limit(20).to_list(20)
    
    logger.info(f"Found {len(analyses)} analyses for user")
    
    puzzles = []
    
    for analysis in analyses:
        game_id = analysis.get("game_id")
        
        # Get game info
        game = await db.games.find_one({"game_id": game_id})
        if not game:
            logger.warning(f"Game not found: {game_id}")
            continue
            
        sf_analysis = analysis.get("stockfish_analysis", {})
        moves = sf_analysis.get("move_evaluations", [])
        user_color = game.get("user_color", "white")
        
        logger.info(f"Game {game_id}: {len(moves)} moves")
        
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
                    "id": f"{game_id}_{move_number}",
                    "fen": fen,
                    "user_move": user_move,
                    "correct_move": best_move,
                    "move_number": move_number,
                    "cp_loss": cp_loss,
                    "game_id": game_id,
                    "opponent": game.get("opponent_name") or game.get("black_player") or "Unknown",
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
    Validate user's answer to a puzzle using DETERMINISTIC Stockfish analysis.
    
    Returns smart feedback with:
    - Whether the move was correct, good, acceptable, or bad
    - Stockfish evaluation of both moves
    - Clear explanation of WHY the best move is better
    """
    from stockfish_service import StockfishEngine
    
    try:
        board = chess.Board(fen)
    except Exception as e:
        logger.error(f"Invalid FEN: {fen}, error: {e}")
        return {"correct": False, "message": "Invalid position", "next_action": "skip"}
    
    # Normalize and parse moves
    try:
        user_move_obj = board.parse_san(user_answer)
        user_move_uci = user_move_obj.uci()
        user_move_san = board.san(user_move_obj)
    except Exception:
        return {
            "correct": False,
            "message": f"Invalid move: {user_answer}",
            "next_action": "retry"
        }
    
    try:
        correct_move_obj = board.parse_san(correct_move)
        correct_move_uci = correct_move_obj.uci()
        correct_move_san = board.san(correct_move_obj)
    except Exception:
        logger.error(f"Invalid correct move: {correct_move}")
        correct_move_san = correct_move
        correct_move_obj = None
    
    # Check if exact match
    is_exact_match = correct_move_obj and user_move_obj == correct_move_obj
    
    # Use Stockfish to evaluate BOTH moves
    engine = StockfishEngine()
    
    # Evaluate position BEFORE move
    eval_before, mate_before = engine.evaluate_position(board, depth=16)
    
    # Get best move from engine
    best_move_uci = engine.get_best_move(board, depth=16)
    
    # Evaluate position AFTER user's move
    board_after_user = board.copy()
    board_after_user.push(user_move_obj)
    eval_after_user, mate_after_user = engine.evaluate_position(board_after_user, depth=16)
    
    # Evaluate position AFTER correct move
    board_after_correct = board.copy()
    if correct_move_obj:
        board_after_correct.push(correct_move_obj)
    eval_after_correct, mate_after_correct = engine.evaluate_position(board_after_correct, depth=16)
    
    engine.close()
    
    # Calculate evaluation differences
    # Positive = good for current player, negative = bad
    is_white_to_move = board.turn == chess.WHITE
    
    # Adjust evaluations based on whose turn
    if not is_white_to_move:
        eval_before = -eval_before
        eval_after_user = -eval_after_user
        eval_after_correct = -eval_after_correct
    
    # User move quality (how much eval changed)
    user_move_delta = eval_after_user - eval_before
    correct_move_delta = eval_after_correct - eval_before
    
    # How does user's move compare to the best move?
    move_diff = eval_after_correct - eval_after_user  # Positive = correct was better
    
    # Classify user's move
    if is_exact_match or move_diff <= 10:
        move_quality = "perfect"
        quality_text = "Perfect!"
    elif move_diff <= 30:
        move_quality = "excellent" 
        quality_text = "Excellent move!"
    elif move_diff <= 80:
        move_quality = "good"
        quality_text = "Good move, but there's a better one."
    elif move_diff <= 150:
        move_quality = "acceptable"
        quality_text = "Acceptable, but you missed the best."
    elif move_diff <= 300:
        move_quality = "inaccuracy"
        quality_text = "Inaccuracy - this loses some advantage."
    elif move_diff <= 500:
        move_quality = "mistake"
        quality_text = "Mistake - this significantly worsens your position."
    else:
        move_quality = "blunder"
        quality_text = "Blunder - this throws away the game!"
    
    # Check for mate sequences
    if mate_after_correct and mate_after_correct > 0:
        correct_has_mate = True
        correct_mate_in = mate_after_correct
    else:
        correct_has_mate = False
        correct_mate_in = None
    
    if mate_after_user and mate_after_user > 0:
        user_has_mate = True
        user_mate_in = mate_after_user
    elif mate_after_user and mate_after_user < 0:
        # User's move allows opponent to have mate!
        user_has_mate = False
        user_allows_mate = -mate_after_user
    else:
        user_has_mate = False
        user_allows_mate = None
    
    # Generate explanation
    def format_eval(cp):
        if cp >= 100:
            return f"+{cp/100:.1f}"
        elif cp <= -100:
            return f"{cp/100:.1f}"
        elif cp > 0:
            return f"+{cp/100:.2f}"
        else:
            return f"{cp/100:.2f}"
    
    # Build smart explanation
    if is_exact_match or move_quality in ["perfect", "excellent"]:
        explanation = f"Your move {user_move_san} is correct! "
        if correct_has_mate:
            explanation += f"It leads to checkmate in {correct_mate_in}."
        else:
            explanation += f"Evaluation: {format_eval(eval_after_user)}"
        is_correct = True
    else:
        explanation = f"The best move is {correct_move_san}. "
        
        # Explain WHY it's better
        if correct_has_mate:
            explanation += f"It forces checkmate in {correct_mate_in}! "
        
        if 'user_allows_mate' in dir() and user_allows_mate:
            explanation += f"Your move {user_move_san} allows mate in {user_allows_mate}! "
        elif move_diff > 0:
            explanation += f"Your move {user_move_san} is {format_eval(move_diff)} pawns worse. "
        
        # Add tactical explanation
        if move_diff > 300:
            explanation += "You may have missed a tactic or left a piece hanging."
        elif move_diff > 100:
            explanation += "Look for forcing moves: checks, captures, and threats."
        
        is_correct = move_quality in ["perfect", "excellent", "good"]
    
    result = {
        "correct": is_correct,
        "move_quality": move_quality,
        "quality_text": quality_text,
        "message": quality_text,
        "user_move": user_move_san,
        "correct_move": correct_move_san,
        "explanation": explanation,
        "eval_user_move": format_eval(eval_after_user),
        "eval_correct_move": format_eval(eval_after_correct),
        "eval_diff": round(move_diff),
        "next_action": "continue" if is_correct else "learn"
    }
    
    # Record this attempt
    await db.training_attempts.insert_one({
        "user_id": user_id,
        "puzzle_id": puzzle_id,
        "user_answer": user_move_san,
        "correct_answer": correct_move_san,
        "was_correct": is_correct,
        "move_quality": move_quality,
        "eval_diff": round(move_diff),
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

# Load ECO to opening name mapping
ECO_OPENINGS = {}
try:
    import json
    with open("data/eco_openings.json", "r") as f:
        ECO_OPENINGS = json.load(f)
    # Remove metadata keys
    ECO_OPENINGS = {k: v for k, v in ECO_OPENINGS.items() if not k.startswith("_")}
except Exception as e:
    logger.warning(f"Could not load ECO openings: {e}")


def get_opening_name_from_eco(eco_or_name: str) -> str:
    """
    Convert ECO code to proper opening name.
    If already a name or not found, return as-is.
    """
    if not eco_or_name:
        return "Unknown Opening"
    
    # Check if it's an ECO code (e.g., "B01", "C50")
    eco_code = eco_or_name.strip().upper()
    
    # Direct lookup
    if eco_code in ECO_OPENINGS:
        return ECO_OPENINGS[eco_code]
    
    # Try without trailing digits for broader match (e.g., "C50" -> "C5" -> check C50-C59)
    if len(eco_code) >= 2 and eco_code[0].isalpha() and eco_code[1:].isdigit():
        # It looks like an ECO code, return the name from dictionary or formatted code
        return ECO_OPENINGS.get(eco_code, eco_or_name)
    
    # If it doesn't look like an ECO code, it might already be a name
    return eco_or_name


async def get_user_openings(db, user_id: str) -> List[Dict]:
    """
    Analyze user's games to find their most played openings.
    Maps ECO codes to proper opening names.
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
        raw_name = opening.get("_id") or ""
        # Map ECO code to proper name
        display_name = get_opening_name_from_eco(raw_name)
        eco_code = raw_name if raw_name and len(raw_name) <= 3 and raw_name[0].isalpha() else None
        
        result.append({
            "name": display_name,
            "eco": eco_code,
            "key": display_name.lower().replace(" ", "_").replace("'", "").replace("-", "_"),
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
