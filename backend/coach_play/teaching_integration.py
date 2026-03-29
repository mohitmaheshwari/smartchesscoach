"""
Coach Engine Integration - Bridges new teaching engine with existing Play with Coach

This module integrates the new Stockfish-validated teaching engine
with the existing coach_play system.

The flow:
1. Existing coaching_triggers.py decides WHEN to speak
2. This module enhances the message with wisdom-based explanations
3. Output includes: diagnosis, reason, memorable rule (from wisdom library)
"""

import chess
from typing import Dict, Optional, Any
import logging

from coach_engine.teaching_engine import TeachingEngine, create_teaching_engine
from coach_engine.rule_validator import StockfishAnalysis
from coach_engine.models import TeachingLevel, CoachingOutput

logger = logging.getLogger(__name__)


# Cache engines per user to maintain de-duplication state
_engine_cache: Dict[str, TeachingEngine] = {}


def get_teaching_engine(user_id: str, user_rating: int = 1200) -> TeachingEngine:
    """Get or create teaching engine for a user"""
    if user_id not in _engine_cache:
        _engine_cache[user_id] = create_teaching_engine(user_id, user_rating)
    return _engine_cache[user_id]


def reset_engine_for_new_game(user_id: str):
    """Reset engine state when starting a new game"""
    if user_id in _engine_cache:
        _engine_cache[user_id].reset_game_state()


def enhance_coaching_message(
    fen: str,
    user_move_uci: str,
    user_color: str,
    eval_before: float,
    eval_after: float,
    best_move_uci: str,
    best_move_eval: float,
    move_number: int,
    user_id: str,
    user_rating: int = 1200,
    is_pv_stable: bool = True,
) -> Optional[Dict[str, Any]]:
    """
    Enhance a coaching moment with wisdom-based explanation.
    
    Called after coaching_triggers decides the coach should speak.
    Returns enhanced message with rule-based explanation if applicable.
    
    Returns None if:
    - No matching rule found
    - De-duplication filters it out
    
    Returns dict with:
    - diagnosis: 1 sentence board-grounded explanation
    - your_move: User's move
    - sf_move: Better move
    - delta_cp: Eval difference
    - reason: Concrete reason from allowed set
    - memorable_rule: Short rule to remember
    - rule_id: Which rule triggered (for telemetry)
    - level: teach/pause/blunder
    - confidence: 0-1
    - highlights: Squares to highlight on board
    - question: MCQ if pause-level
    """
    
    try:
        board = chess.Board(fen)
        user_move = chess.Move.from_uci(user_move_uci)
        color = chess.WHITE if user_color.lower() == "white" else chess.BLACK
        
        # Calculate delta from user's perspective
        if color == chess.WHITE:
            delta_cp = int((eval_after - eval_before) * 100)
        else:
            delta_cp = int((eval_before - eval_after) * 100)  # Flip for black
        
        sf_analysis = StockfishAnalysis(
            eval_before=eval_before,
            eval_after=eval_after,
            delta_cp=delta_cp,
            best_move=best_move_uci,
            best_move_eval=best_move_eval,
            pv_line=[best_move_uci],
            depth=20,
            is_stable=is_pv_stable,
        )
        
        engine = get_teaching_engine(user_id, user_rating)
        output = engine.process_move(
            board=board,
            user_move=user_move,
            user_color=color,
            sf_analysis=sf_analysis,
            move_number=move_number,
        )
        
        if not output:
            return None
        
        return {
            "diagnosis": output.diagnosis,
            "your_move": output.your_move,
            "sf_move": output.sf_move,
            "delta_cp": output.delta_cp,
            "reason": output.reason.value,
            "reason_detail": output.reason_detail,
            "memorable_rule": output.memorable_rule,
            "rule_id": output.rule_id,
            "level": output.level.value,
            "confidence": output.confidence,
            "highlights": output.highlights,
            "question": output.question,
            "chat_message": output.to_chat_message(),
            "observation_message": output.to_observation() if output.level == TeachingLevel.OBSERVE else None,
        }
        
    except Exception as e:
        logger.error(f"Error enhancing coaching message: {e}")
        return None


def get_wisdom_for_position(
    fen: str,
    user_color: str,
    user_rating: int = 1200,
) -> Dict[str, Any]:
    """
    Get relevant wisdom rules for a position (before move is made).
    
    Used for proactive coaching hints.
    Returns list of potentially relevant rules based on position features.
    """
    from coach_engine.piece_metrics import PieceMetricsAnalyzer
    from coach_engine.wisdom_library import get_wisdom_library
    
    board = chess.Board(fen)
    color = chess.WHITE if user_color.lower() == "white" else chess.BLACK
    analyzer = PieceMetricsAnalyzer(board)
    library = get_wisdom_library()
    
    hints = []
    
    # Check for common position features that suggest rules
    position_metrics = analyzer.analyze()
    
    # Not castled and move 8+?
    move_count = len(board.move_stack)
    if move_count >= 14 and not (position_metrics.white_castled if color == chess.WHITE else position_metrics.black_castled):
        rule = library.get_rule("DELAYED_CASTLING")
        if rule:
            hints.append({
                "rule_id": rule.rule_id,
                "hint": "Consider castling to secure your king.",
                "priority": 8,
            })
    
    # Blocked bishop?
    for sq in chess.SQUARES:
        piece = board.piece_at(sq)
        if piece and piece.piece_type == chess.BISHOP and piece.color == color:
            blocking_info = analyzer.get_bishop_blocking_info(sq)
            if blocking_info and blocking_info["blocked_by_own_pawn"]:
                if blocking_info.get("usable_squares", 10) <= 4:
                    hints.append({
                        "rule_id": "BLOCKED_BISHOP_BY_OWN_PAWN",
                        "hint": f"Your bishop on {chess.square_name(sq)} has limited mobility.",
                        "priority": 5,
                    })
                    break
    
    # Open file without rook?
    open_files, _, _ = analyzer.get_open_files()
    if open_files:
        has_rook_on_open = False
        for sq in chess.SQUARES:
            piece = board.piece_at(sq)
            if piece and piece.piece_type == chess.ROOK and piece.color == color:
                if chess.FILE_NAMES[chess.square_file(sq)] in open_files:
                    has_rook_on_open = True
                    break
        
        if not has_rook_on_open:
            hints.append({
                "rule_id": "OPEN_FILE_ROOK_UNUSED",
                "hint": f"The {open_files[0]}-file is open. Consider using it.",
                "priority": 4,
            })
    
    return {
        "hints": sorted(hints, key=lambda x: -x["priority"])[:2],  # Max 2 hints
        "position_features": {
            "is_closed": position_metrics.is_closed_position,
            "castled": position_metrics.white_castled if color == chess.WHITE else position_metrics.black_castled,
            "open_files": open_files,
            "development_lead": position_metrics.development_lead,
        }
    }
