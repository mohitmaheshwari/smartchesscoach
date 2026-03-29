"""
Endgame Teaching System
=======================

Provides interactive endgame lessons including:
1. Basic Checkmates (K+Q, K+R, K+2B, K+B+N)
2. King and Pawn Endgames (Opposition, Key Squares, Rule of the Square)
3. Rook Endgames (Lucena Position, Philidor Position)
4. Common Endgame Patterns and Techniques

The system detects when we're in an endgame and offers relevant teaching.
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import logging
import chess

logger = logging.getLogger(__name__)


class EndgameType(str, Enum):
    """Types of endgames"""
    KING_PAWN = "king_pawn"              # K+P vs K
    KING_QUEEN = "king_queen"            # K+Q vs K
    KING_ROOK = "king_rook"              # K+R vs K  
    KING_TWO_ROOKS = "king_two_rooks"    # K+2R vs K
    ROOK_ENDGAME = "rook_endgame"        # R+P vs R etc
    QUEEN_ENDGAME = "queen_endgame"      # Q vs Q with pawns
    BISHOP_ENDGAME = "bishop_endgame"    # B vs B
    KNIGHT_ENDGAME = "knight_endgame"    # N vs N
    OPPOSITE_BISHOPS = "opposite_bishops" # Opposite color bishops
    BASIC_CHECKMATE = "basic_checkmate"   # Basic mating patterns


@dataclass
class EndgameLesson:
    """An endgame lesson with interactive teaching"""
    name: str
    endgame_type: EndgameType
    description: str
    key_concepts: List[str]
    setup_fen: str  # Starting position for the lesson
    solution_moves: List[str]  # Moves to demonstrate the technique
    explanations: Dict[int, str]  # Move number -> explanation
    common_mistakes: List[str]
    practice_positions: List[str] = field(default_factory=list)  # Additional FENs to practice


# Endgame Lessons Database
ENDGAME_LESSONS = {
    # Basic Checkmates
    "queen_checkmate": EndgameLesson(
        name="Queen Checkmate",
        endgame_type=EndgameType.KING_QUEEN,
        description="Learn to checkmate with King and Queen against a lone King.",
        key_concepts=[
            "Use the Queen to restrict the enemy King",
            "Push the enemy King to the edge of the board",
            "Bring your King closer to help",
            "Avoid stalemate!"
        ],
        setup_fen="8/8/8/4k3/8/8/4Q3/4K3 w - - 0 1",
        solution_moves=["Qe3+", "Kd5", "Kd2", "Kc4", "Qd3+", "Kb4", "Qc3+", "Ka4", "Kc2", "Kb5", "Kb3", "Ka6", "Qb4", "Ka7", "Kc4", "Ka6", "Kc5", "Ka7", "Kc6", "Ka8", "Qb7#"],
        explanations={
            0: "Start by checking the King to push it back.",
            2: "Bring your King into the action - it needs to help!",
            4: "Keep restricting the enemy King's squares.",
            12: "The enemy King is running out of space.",
            20: "Checkmate! The King is trapped on the edge."
        },
        common_mistakes=[
            "Don't stalemate! Always leave the enemy King a square (until checkmate)",
            "Don't rush - bring your King to help",
            "Use checks strategically, not randomly"
        ]
    ),
    
    "rook_checkmate": EndgameLesson(
        name="Rook Checkmate",
        endgame_type=EndgameType.KING_ROOK,
        description="Learn to checkmate with King and Rook against a lone King.",
        key_concepts=[
            "Cut off the enemy King with the Rook",
            "Use your King to push the enemy King back",
            "The 'box' technique - shrink the enemy King's space",
            "Opposition is key!"
        ],
        setup_fen="8/8/8/4k3/8/8/4R3/4K3 w - - 0 1",
        solution_moves=["Re4+", "Kd5", "Kd2", "Kc5", "Kd3", "Kb5", "Kc3", "Kc5", "Re5+", "Kd6", "Kd4", "Kc6", "Re6+", "Kb5", "Kc3", "Ka5", "Kb3", "Kb5", "Re5+", "Ka6", "Kc4", "Kb6", "Kd5", "Ka6", "Kc6", "Ka7", "Re7+", "Ka8", "Kc7", "Rb7#"],
        explanations={
            0: "Check to push the King back and cut it off.",
            2: "Now bring your King into the fight!",
            8: "The 'box' is getting smaller - enemy King has less space.",
            20: "Opposition! Your King faces the enemy King.",
            29: "Checkmate! Rook delivers the final blow."
        },
        common_mistakes=[
            "The Rook alone can't checkmate - your King must help",
            "Don't give pointless checks - improve your King's position",
            "Watch out for stalemate in the corner"
        ]
    ),
    
    # King and Pawn Endgames
    "opposition": EndgameLesson(
        name="The Opposition",
        endgame_type=EndgameType.KING_PAWN,
        description="Master the key concept of Opposition in King and Pawn endgames.",
        key_concepts=[
            "Opposition: Kings face each other with one square between",
            "The side NOT to move has the opposition (advantage)",
            "Use opposition to force the enemy King aside",
            "Critical for promoting pawns"
        ],
        setup_fen="8/8/8/3k4/8/3K4/3P4/8 w - - 0 1",
        solution_moves=["Ke3", "Ke5", "d4+", "Kd5", "Kd3", "Kd6", "Kd4", "Ke6", "Kc5", "Kd7", "Kd5", "Ke7", "Ke5", "Kd7", "d5", "Ke7", "d6+", "Kd7", "Kd5", "Kd8", "Kc6", "Kc8", "d7+", "Kd8", "Kd6"],
        explanations={
            0: "First, we need to get our King in front of the pawn.",
            2: "Push the pawn to gain space.",
            6: "We have the opposition! Enemy King must move aside.",
            14: "Key position - our King is in front of the pawn.",
            24: "With opposition, the pawn will promote!"
        },
        common_mistakes=[
            "Don't push the pawn too early - King goes first!",
            "Losing the opposition often means a draw",
            "Always try to get your King IN FRONT of the pawn"
        ]
    ),
    
    "rule_of_square": EndgameLesson(
        name="Rule of the Square",
        endgame_type=EndgameType.KING_PAWN,
        description="Learn when your King can catch a passed pawn.",
        key_concepts=[
            "Draw a square from the pawn to the promotion square",
            "If your King can step INTO the square, it catches the pawn",
            "Count carefully - one wrong square loses!",
            "Diagonal moves are just as fast as straight moves"
        ],
        setup_fen="8/8/1p6/8/8/8/6K1/8 w - - 0 1",
        solution_moves=["Kf3", "b5", "Ke4", "b4", "Kd5", "b3", "Kc4", "b2", "Kc3", "b1=Q"],
        explanations={
            0: "The pawn is on b6. Draw a square b6-b1-g1-g6. Can our King enter?",
            2: "We're inside the square! We can catch the pawn.",
            6: "Racing to catch the pawn...",
            9: "We caught it! The King reaches the pawn in time."
        },
        common_mistakes=[
            "Don't forget: the square is drawn from the PAWN, not the King",
            "Count the squares carefully before deciding to chase",
            "Remember: King moves diagonally just as fast!"
        ]
    ),
    
    # Rook Endgames
    "lucena_position": EndgameLesson(
        name="Lucena Position (Building a Bridge)",
        endgame_type=EndgameType.ROOK_ENDGAME,
        description="The most important rook endgame technique - the Bridge.",
        key_concepts=[
            "Rook + Pawn vs Rook is often won with the Lucena technique",
            "The King hides behind the pawn from checks",
            "Build a 'bridge' with your Rook to block enemy checks",
            "This wins 95% of Rook + Pawn vs Rook positions"
        ],
        setup_fen="1K1k4/1P6/8/8/8/8/r7/4R3 w - - 0 1",
        solution_moves=["Re4", "Ra1", "Kc7", "Rc1+", "Kb6", "Rb1+", "Kc6", "Rc1+", "Kb5", "Rb1+", "Rb4", "Rxb4+", "Kxb4"],
        explanations={
            0: "First, move the Rook to the 4th rank to prepare the bridge.",
            2: "Now step out with the King.",
            4: "Black checks, but we keep moving the King down.",
            10: "The Bridge! Rook blocks the check, pawn will promote."
        },
        common_mistakes=[
            "Don't try to promote immediately - build the bridge first",
            "The Rook on the 4th rank is key to blocking checks",
            "Be patient - this technique always works"
        ]
    ),
    
    "philidor_position": EndgameLesson(
        name="Philidor Position (The Drawing Technique)",
        endgame_type=EndgameType.ROOK_ENDGAME,
        description="Learn how to draw Rook + Pawn vs Rook from the defending side.",
        key_concepts=[
            "Keep your Rook on the 6th rank (3rd rank for Black)",
            "This prevents the enemy King from advancing",
            "When the pawn advances to the 6th, go to the back rank",
            "Check from behind - infinite checks draw!"
        ],
        setup_fen="8/8/8/4k3/4P3/8/8/R3K3 b - - 0 1",
        solution_moves=["Kd6", "Ke2", "Ke5", "Ke3", "Ra6", "Kd3", "Kd6", "e5", "Ra1", "Kd4", "Rd1+", "Ke4", "Re1+"],
        explanations={
            0: "Black's King stays in front of the pawn.",
            4: "Rook to the 6th rank - the key defensive position!",
            7: "When the pawn advances, Rook goes to the back rank.",
            10: "Now we check from behind - White can't escape!"
        },
        common_mistakes=[
            "Don't let your King get pushed to the side",
            "Keep the Rook on the 6th until the pawn moves there",
            "From behind, you have infinite checking distance"
        ]
    )
}


def detect_endgame_type(board: chess.Board) -> Optional[EndgameType]:
    """
    Detect what type of endgame we're in based on material.
    
    Returns:
        EndgameType if we're in a recognized endgame, None otherwise
    """
    # Count material
    white_pieces = {
        'Q': len(board.pieces(chess.QUEEN, chess.WHITE)),
        'R': len(board.pieces(chess.ROOK, chess.WHITE)),
        'B': len(board.pieces(chess.BISHOP, chess.WHITE)),
        'N': len(board.pieces(chess.KNIGHT, chess.WHITE)),
        'P': len(board.pieces(chess.PAWN, chess.WHITE))
    }
    black_pieces = {
        'Q': len(board.pieces(chess.QUEEN, chess.BLACK)),
        'R': len(board.pieces(chess.ROOK, chess.BLACK)),
        'B': len(board.pieces(chess.BISHOP, chess.BLACK)),
        'N': len(board.pieces(chess.KNIGHT, chess.BLACK)),
        'P': len(board.pieces(chess.PAWN, chess.BLACK))
    }
    
    total_white = sum(white_pieces.values())
    total_black = sum(black_pieces.values())
    total_pieces = total_white + total_black
    
    # Not an endgame if too much material (more than 6 pieces excluding kings)
    if total_pieces > 6:
        return None
    
    # K+Q vs K
    if (white_pieces['Q'] == 1 and total_white == 1 and total_black == 0) or \
       (black_pieces['Q'] == 1 and total_black == 1 and total_white == 0):
        return EndgameType.KING_QUEEN
    
    # K+R vs K
    if (white_pieces['R'] == 1 and total_white == 1 and total_black == 0) or \
       (black_pieces['R'] == 1 and total_black == 1 and total_white == 0):
        return EndgameType.KING_ROOK
    
    # K+P vs K (simple pawn endgame)
    if total_pieces <= 2 and (white_pieces['P'] > 0 or black_pieces['P'] > 0):
        return EndgameType.KING_PAWN
    
    # Rook endgame (both sides have rooks)
    if white_pieces['R'] >= 1 and black_pieces['R'] >= 1 and \
       white_pieces['Q'] == 0 and black_pieces['Q'] == 0:
        return EndgameType.ROOK_ENDGAME
    
    # Queen endgame
    if white_pieces['Q'] >= 1 and black_pieces['Q'] >= 1:
        return EndgameType.QUEEN_ENDGAME
    
    return None


def get_relevant_lesson(endgame_type: EndgameType, board: chess.Board) -> Optional[EndgameLesson]:
    """Get the most relevant lesson for the current position."""
    
    if endgame_type == EndgameType.KING_QUEEN:
        return ENDGAME_LESSONS.get("queen_checkmate")
    
    elif endgame_type == EndgameType.KING_ROOK:
        return ENDGAME_LESSONS.get("rook_checkmate")
    
    elif endgame_type == EndgameType.KING_PAWN:
        return ENDGAME_LESSONS.get("opposition")  # Start with opposition
    
    elif endgame_type == EndgameType.ROOK_ENDGAME:
        # Check material to determine which lesson
        white_pawns = len(board.pieces(chess.PAWN, chess.WHITE))
        black_pawns = len(board.pieces(chess.PAWN, chess.BLACK))
        
        # If one side has a pawn advantage, suggest Lucena (winning) or Philidor (defending)
        if white_pawns > black_pawns or black_pawns > white_pawns:
            return ENDGAME_LESSONS.get("lucena_position")
        
    return None


async def check_endgame_and_offer_teaching(
    db,
    session_id: str,
    current_fen: str,
    user_id: str,
    user_color: str
) -> Optional[Dict]:
    """
    Check if we're in an endgame and offer relevant teaching.
    
    Returns:
        Dict with teaching offer if in endgame, None otherwise
    """
    board = chess.Board(current_fen)
    
    # Get session to check if we've already offered endgame teaching
    session_doc = await db.coach_sessions.find_one({"session_id": session_id})
    if not session_doc:
        return None
    
    # Skip if already shown endgame offer
    if session_doc.get("endgame_offer_shown"):
        return None
    
    # Detect endgame type
    endgame_type = detect_endgame_type(board)
    if not endgame_type:
        return None
    
    # Get relevant lesson
    lesson = get_relevant_lesson(endgame_type, board)
    if not lesson:
        return None
    
    logger.info(f"Endgame detected: {endgame_type.value}, suggesting lesson: {lesson.name}")
    
    # Build teaching offer
    options = [
        {
            "id": "learn_technique",
            "label": f"📚 Learn {lesson.name}",
            "description": "Interactive lesson on this endgame technique"
        },
        {
            "id": "show_key_concepts",
            "label": "💡 Show me the key ideas",
            "description": "Quick summary of what to know"
        },
        {
            "id": "just_play",
            "label": "⚔️ Let me try myself",
            "description": "Continue playing without lesson"
        }
    ]
    
    # Mark that we've shown the offer
    await db.coach_sessions.update_one(
        {"session_id": session_id},
        {"$set": {"endgame_offer_shown": True, "detected_endgame": endgame_type.value}}
    )
    
    return {
        "type": "endgame_teaching_offer",
        "endgame_type": endgame_type.value,
        "lesson_name": lesson.name,
        "message": f"We're in a {lesson.name.lower()} position! This is a crucial endgame technique. Would you like to learn it?",
        "description": lesson.description,
        "key_concepts": lesson.key_concepts,
        "options": options
    }


async def start_endgame_lesson(
    db,
    session_id: str,
    lesson_key: str
) -> Dict:
    """
    Start an interactive endgame lesson.
    """
    lesson = ENDGAME_LESSONS.get(lesson_key)
    if not lesson:
        return {"error": "Lesson not found"}
    
    session_doc = await db.coach_sessions.find_one({"session_id": session_id})
    if not session_doc:
        return {"error": "Session not found"}
    
    # Store teaching state
    teaching_data = {
        "lesson_key": lesson_key,
        "lesson_name": lesson.name,
        "current_move_index": 0,
        "solution_moves": lesson.solution_moves,
        "explanations": lesson.explanations,
        "setup_fen": lesson.setup_fen,
        "teaching_fen": lesson.setup_fen,
        "original_fen": session_doc.get("current_fen"),
        "original_move_history": session_doc.get("move_history", [])
    }
    
    await db.coach_sessions.update_one(
        {"session_id": session_id},
        {"$set": {
            "teaching_mode": "endgame",
            "teaching_data": teaching_data,
            "current_fen": lesson.setup_fen
        }}
    )
    
    # Get first instruction
    first_explanation = lesson.explanations.get(0, "Let's begin the lesson.")
    
    return {
        "success": True,
        "mode": "endgame",
        "lesson_name": lesson.name,
        "description": lesson.description,
        "key_concepts": lesson.key_concepts,
        "common_mistakes": lesson.common_mistakes,
        "teaching_fen": lesson.setup_fen,
        "instruction": {
            "message": first_explanation,
            "expected_move": lesson.solution_moves[0] if lesson.solution_moves else None,
            "total_moves": len(lesson.solution_moves)
        }
    }


async def process_endgame_teaching_move(
    db,
    session_id: str,
    user_move: str
) -> Dict:
    """Process a move during endgame teaching mode."""
    import chess
    
    session_doc = await db.coach_sessions.find_one({"session_id": session_id})
    if not session_doc:
        return {"error": "Session not found"}
    
    teaching_data = session_doc.get("teaching_data", {})
    current_index = teaching_data.get("current_move_index", 0)
    solution_moves = teaching_data.get("solution_moves", [])
    explanations = teaching_data.get("explanations", {})
    
    if current_index >= len(solution_moves):
        return {"complete": True, "message": "Lesson complete!"}
    
    expected_move = solution_moves[current_index]
    
    # Check if correct (case-insensitive, ignore check symbols)
    user_clean = user_move.lower().replace("+", "").replace("#", "").replace("x", "")
    expected_clean = expected_move.lower().replace("+", "").replace("#", "").replace("x", "")
    
    if user_clean != expected_clean:
        return {
            "correct": False,
            "expected_move": expected_move,
            "message": f"Not quite! The correct move is {expected_move}.",
            "hint": explanations.get(current_index, "Think about the key concepts.")
        }
    
    # Correct! Update position
    current_fen = teaching_data.get("teaching_fen")
    board = chess.Board(current_fen)
    
    try:
        move = board.parse_san(expected_move)
        board.push(move)
        new_fen = board.fen()
    except Exception as e:
        logger.error(f"Error applying move: {e}")
        return {"error": str(e)}
    
    new_index = current_index + 1
    teaching_data["current_move_index"] = new_index
    teaching_data["teaching_fen"] = new_fen
    
    await db.coach_sessions.update_one(
        {"session_id": session_id},
        {"$set": {
            "teaching_data": teaching_data,
            "current_fen": new_fen
        }}
    )
    
    # Check if complete
    if new_index >= len(solution_moves):
        lesson = ENDGAME_LESSONS.get(teaching_data.get("lesson_key"))
        return {
            "complete": True,
            "message": "Excellent! You've completed the lesson!",
            "summary": lesson.description if lesson else "",
            "key_concepts": lesson.key_concepts if lesson else []
        }
    
    # Get next instruction
    next_explanation = explanations.get(new_index, "Continue with the technique.")
    next_move = solution_moves[new_index]
    
    return {
        "correct": True,
        "message": "Correct!",
        "explanation": next_explanation,
        "next_instruction": {
            "message": next_explanation,
            "expected_move": next_move,
            "progress": f"{new_index}/{len(solution_moves)}"
        },
        "teaching_fen": new_fen
    }
