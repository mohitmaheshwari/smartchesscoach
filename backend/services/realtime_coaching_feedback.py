"""
Realtime Coaching Feedback Service
===================================

This service generates comprehensive, human-like coaching feedback
after each user move on the CoachPlay page.

The feedback includes:
1. Assessment of the user's move (quality, what it achieved)
2. What the best move was and why
3. Explanation of the coach's counter-move
4. Personalized language based on player's understanding profile

This is NOT a chatty analysis - it's a focused teaching moment
like a human coach sitting across from you.

Author: Built for truly personalized real-time coaching
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import logging
import chess

logger = logging.getLogger(__name__)


@dataclass
class MoveFeedback:
    """Comprehensive feedback for a single move"""
    # User's move assessment
    user_move: str
    user_move_quality: str  # "excellent", "good", "inaccuracy", "mistake", "blunder"
    user_move_eval_change: float  # centipawn change (negative = bad)
    
    # Best move explanation
    best_move: str
    best_move_explanation: str  # What the best move achieves
    pv_after_best: List[str]  # Best continuation
    
    # Coach's response
    coach_move: str
    coach_move_explanation: str  # Why the coach played this
    
    # Main coaching message (conversational, human-like)
    coaching_message: str
    
    # Optional: Specific tactical/positional elements
    threats_after_user_move: List[str]  # What opponent can now do
    missed_opportunities: List[str]  # What user could have done
    
    # Personalization
    relates_to_weakness: Optional[str]  # If this relates to a known weakness
    encouragement: Optional[str]  # For good moves
    
    # Trap suggestion
    trap_suggestion: Optional[Dict] = None  # If a trap is available from this position
    
    def to_dict(self) -> Dict:
        result = {
            "user_move": self.user_move,
            "user_move_quality": self.user_move_quality,
            "user_move_eval_change": self.user_move_eval_change,
            "best_move": self.best_move,
            "best_move_explanation": self.best_move_explanation,
            "pv_after_best": self.pv_after_best,
            "coach_move": self.coach_move,
            "coach_move_explanation": self.coach_move_explanation,
            "coaching_message": self.coaching_message,
            "threats_after_user_move": self.threats_after_user_move,
            "missed_opportunities": self.missed_opportunities,
            "relates_to_weakness": self.relates_to_weakness,
            "encouragement": self.encouragement
        }
        if self.trap_suggestion:
            result["trap_suggestion"] = self.trap_suggestion
        return result


def _get_piece_name(piece: chess.Piece) -> str:
    """Get human-readable piece name"""
    names = {
        chess.PAWN: "pawn",
        chess.KNIGHT: "knight",
        chess.BISHOP: "bishop",
        chess.ROOK: "rook",
        chess.QUEEN: "queen",
        chess.KING: "king"
    }
    return names.get(piece.piece_type, "piece")


def _square_name(square: int) -> str:
    """Get algebraic square name"""
    return chess.square_name(square)


def _analyze_move_tactically(
    board_before: chess.Board,
    user_move_uci: str,
    best_move_uci: str,
    user_color: chess.Color
) -> Dict[str, Any]:
    """
    Analyze what the user's move and best move achieve tactically.
    Returns specific piece-square analysis.
    """
    result = {
        "user_move_captures": None,
        "best_move_captures": None,
        "user_move_attacks": [],
        "best_move_attacks": [],
        "threats_created": [],
        "threats_missed": []
    }
    
    try:
        user_move = chess.Move.from_uci(user_move_uci)
        best_move = chess.Move.from_uci(best_move_uci)
        
        # What user's move captures
        if board_before.is_capture(user_move):
            captured_piece = board_before.piece_at(user_move.to_square)
            if captured_piece:
                result["user_move_captures"] = _get_piece_name(captured_piece)
        
        # What best move captures
        if board_before.is_capture(best_move):
            captured_piece = board_before.piece_at(best_move.to_square)
            if captured_piece:
                result["best_move_captures"] = _get_piece_name(captured_piece)
        
        # Analyze position after user's move
        board_after_user = board_before.copy()
        board_after_user.push(user_move)
        
        # What threats exist against user after their move
        for move in board_after_user.legal_moves:
            if board_after_user.is_capture(move):
                target_piece = board_after_user.piece_at(move.to_square)
                if target_piece and target_piece.color == user_color:
                    threat = f"{_get_piece_name(board_after_user.piece_at(move.from_square))} takes {_get_piece_name(target_piece)} on {_square_name(move.to_square)}"
                    if threat not in result["threats_created"]:
                        result["threats_created"].append(threat)
        
        # What attacks best move creates
        board_after_best = board_before.copy()
        board_after_best.push(best_move)
        
        moving_piece = board_before.piece_at(best_move.from_square)
        if moving_piece:
            # Check what this piece now attacks
            for square in board_after_best.attacks(best_move.to_square):
                target = board_after_best.piece_at(square)
                if target and target.color != user_color:
                    attack = f"attacks {_get_piece_name(target)} on {_square_name(square)}"
                    result["best_move_attacks"].append(attack)
        
    except Exception as e:
        logger.warning(f"Tactical analysis error: {e}")
    
    return result


def _classify_move_quality(eval_before: float, eval_after: float, user_color: str) -> str:
    """Classify move quality based on evaluation change"""
    # Calculate from user's perspective
    if user_color == "white":
        change = eval_after - eval_before  # Positive = good for white
    else:
        change = eval_before - eval_after  # Negative eval is good for black
    
    cp_change = change * 100  # Convert to centipawns
    
    if cp_change >= 20:
        return "excellent"  # User improved position
    elif cp_change >= -10:
        return "good"
    elif cp_change >= -50:
        return "inaccuracy"
    elif cp_change >= -150:
        return "mistake"
    else:
        return "blunder"


def _generate_coaching_message(
    user_move: str,
    quality: str,
    best_move: str,
    tactical_analysis: Dict,
    coach_move: str,
    understanding_context: Optional[Dict] = None
) -> str:
    """
    Generate a human-like coaching message.
    This is the main conversational feedback.
    """
    messages = []
    
    # Assess user's move
    if quality == "excellent":
        messages.append(f"Great move with {user_move}!")
        return " ".join(messages)
    
    elif quality == "good":
        messages.append(f"{user_move} is a reasonable choice.")
        if best_move != user_move:
            messages.append(f"{best_move} was slightly more accurate.")
        return " ".join(messages)
    
    elif quality == "inaccuracy":
        # Check if user_move is same as best_move (edge case)
        if user_move == best_move:
            messages.append(f"{user_move} was fine, but the position needed more precision.")
        else:
            messages.append(f"{user_move} is okay, but {best_move} was better here.")
        
        # Add specific reason if available
        if tactical_analysis.get("best_move_captures") and user_move != best_move:
            messages.append(f"With {best_move} you could have won the {tactical_analysis['best_move_captures']}.")
        elif tactical_analysis.get("best_move_attacks") and user_move != best_move:
            attacks = tactical_analysis["best_move_attacks"][:2]
            if attacks:
                messages.append(f"{best_move} {', '.join(attacks)}.")
    
    elif quality == "mistake":
        messages.append(f"That {user_move} lets some advantage slip.")
        
        if tactical_analysis.get("threats_created"):
            threat = tactical_analysis["threats_created"][0]
            messages.append(f"Now I can play {threat}.")
        
        if user_move != best_move:
            messages.append(f"{best_move} was the move to find.")
    
    elif quality == "blunder":
        messages.append(f"Oh, {user_move} is a tough one.")
        
        if tactical_analysis.get("best_move_captures"):
            messages.append(f"You could have won material with {best_move} (takes the {tactical_analysis['best_move_captures']}).")
        elif tactical_analysis.get("threats_created"):
            threat = tactical_analysis["threats_created"][0]
            messages.append(f"That allows {threat}.")
        else:
            messages.append(f"The position really needed {best_move}.")
    
    # Add note about coach's response
    if coach_move:
        if quality in ["mistake", "blunder"]:
            messages.append(f"I'll play {coach_move} to take advantage.")
        else:
            messages.append(f"I respond with {coach_move}.")
    
    # Add personalization based on understanding
    if understanding_context:
        weakness = understanding_context.get("primary_weakness", "")
        if weakness and weakness.lower() in ["tactical vision", "consistency"]:
            if quality in ["mistake", "blunder"]:
                messages.append("Take your time and check all captures.")
    
    return " ".join(messages)


async def generate_move_feedback(
    db,
    session_id: str,
    move_number: int,
    user_id: str
) -> Optional[MoveFeedback]:
    """
    Generate comprehensive feedback for a specific move in a session.
    
    Args:
        db: Database connection
        session_id: Coach play session ID
        move_number: Which user move to analyze (1-indexed)
        user_id: User ID for personalization
    
    Returns:
        MoveFeedback object with all analysis
    """
    from services.chess_understanding import get_chess_understanding, get_coaching_context_from_understanding
    
    # Get session
    session = await db.coach_sessions.find_one({"session_id": session_id}, {"_id": 0})
    if not session:
        return None
    
    move_history = session.get("move_history", [])
    user_color = session.get("user_color", "white")
    
    # Find the user's move at move_number
    user_move_data = None
    coach_move_data = None
    user_move_idx = 0
    
    for i, m in enumerate(move_history):
        if m.get("by") == "player":
            user_move_idx += 1
            if user_move_idx == move_number:
                user_move_data = m
                # Coach's response is the next move
                if i + 1 < len(move_history) and move_history[i + 1].get("by") == "coach":
                    coach_move_data = move_history[i + 1]
                break
    
    if not user_move_data:
        return None
    
    # Extract data
    user_move = user_move_data.get("move", "")
    fen_before = user_move_data.get("fen_before", "")
    eval_before = user_move_data.get("eval_before", 0)
    eval_after = user_move_data.get("eval_after", 0)
    best_move = user_move_data.get("best_move", user_move)
    
    coach_move = coach_move_data.get("move", "") if coach_move_data else ""
    
    # Classify quality
    quality = _classify_move_quality(eval_before, eval_after, user_color)
    
    # Tactical analysis
    tactical = {}
    if fen_before and user_move:
        try:
            board = chess.Board(fen_before)
            user_move_uci = user_move_data.get("uci", "")
            best_move_uci = ""
            
            # Parse best move to UCI
            if best_move:
                try:
                    best_move_obj = board.parse_san(best_move)
                    best_move_uci = best_move_obj.uci()
                except chess.InvalidMoveError:
                    pass
            
            if user_move_uci and best_move_uci:
                user_chess_color = chess.WHITE if user_color == "white" else chess.BLACK
                tactical = _analyze_move_tactically(board, user_move_uci, best_move_uci, user_chess_color)
        except Exception as e:
            logger.warning(f"Tactical analysis failed: {e}")
    
    # Get player understanding for personalization
    understanding_context = None
    try:
        understanding = await get_chess_understanding(db, user_id)
        understanding_context = get_coaching_context_from_understanding(understanding)
    except Exception as e:
        logger.warning(f"Could not get understanding context: {e}")
    
    # Generate main coaching message
    coaching_message = _generate_coaching_message(
        user_move=user_move,
        quality=quality,
        best_move=best_move,
        tactical_analysis=tactical,
        coach_move=coach_move,
        understanding_context=understanding_context
    )
    
    # Generate best move explanation
    best_move_explanation = ""
    if best_move and best_move != user_move:
        if tactical.get("best_move_captures"):
            best_move_explanation = f"Wins the {tactical['best_move_captures']}"
        elif tactical.get("best_move_attacks"):
            best_move_explanation = f"Creates pressure: {', '.join(tactical['best_move_attacks'][:2])}"
        else:
            best_move_explanation = "Maintains better position"
    
    # Generate coach move explanation
    coach_explanation = ""
    if coach_move:
        if quality in ["mistake", "blunder"] and tactical.get("threats_created"):
            coach_explanation = "Takes advantage of the error"
        else:
            coach_explanation = "Continues development"
    
    # Check if relates to known weakness
    relates_to = None
    if understanding_context:
        weakness = understanding_context.get("primary_weakness", "")
        if weakness:
            if "tactical" in weakness.lower() and quality in ["mistake", "blunder"]:
                relates_to = f"This relates to your {weakness} - keep practicing!"
            elif "consistency" in weakness.lower() and quality in ["mistake", "blunder"]:
                relates_to = "Stay focused - you know better than this!"
    
    # Encouragement for good moves
    encouragement = None
    if quality in ["excellent", "good"]:
        encouragement = "Keep it up!" if quality == "good" else "That's the move!"
    
    # Check if a trap is available from this position
    trap_suggestion = None
    try:
        from services.trap_library import get_trap_for_position
        
        # Get the move history as SAN moves
        san_history = [m.get("move") for m in move_history if m.get("move")]
        trap_data = get_trap_for_position(san_history)
        
        if trap_data and trap_data.get("moves_until_trap", 999) <= 4:
            # A trap is within reach!
            trap_suggestion = {
                "name": trap_data.get("name"),
                "description": trap_data.get("description"),
                "setup_remaining": trap_data.get("setup_remaining", []),
                "moves_until_trap": trap_data.get("moves_until_trap", 0),
                "result_type": trap_data.get("result_type"),
                "opening_key": trap_data.get("opening_key")
            }
    except Exception as e:
        logger.warning(f"Error checking for traps: {e}")
    
    return MoveFeedback(
        user_move=user_move,
        user_move_quality=quality,
        user_move_eval_change=(eval_after - eval_before) * 100,
        best_move=best_move,
        best_move_explanation=best_move_explanation,
        pv_after_best=user_move_data.get("pv_after_best", [])[:4],
        coach_move=coach_move,
        coach_move_explanation=coach_explanation,
        coaching_message=coaching_message,
        threats_after_user_move=tactical.get("threats_created", [])[:3],
        missed_opportunities=tactical.get("best_move_attacks", [])[:3],
        relates_to_weakness=relates_to,
        encouragement=encouragement,
        trap_suggestion=trap_suggestion
    )


async def get_last_move_feedback(db, session_id: str, user_id: str) -> Optional[Dict]:
    """
    Get feedback for the most recent user move in a session.
    This is the main API for the frontend.
    """
    # Get session to find last move number
    session = await db.coach_sessions.find_one({"session_id": session_id}, {"_id": 0})
    if not session:
        return None
    
    move_history = session.get("move_history", [])
    
    # Count user moves
    user_move_count = sum(1 for m in move_history if m.get("by") == "player")
    
    if user_move_count == 0:
        return None
    
    # Generate feedback for the last user move
    feedback = await generate_move_feedback(db, session_id, user_move_count, user_id)
    
    if feedback:
        return feedback.to_dict()
    
    return None
