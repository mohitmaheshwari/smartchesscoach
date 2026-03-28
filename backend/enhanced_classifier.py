"""
Enhanced Mistake Classifier

This module wraps the deterministic mistake classifier with learned rules.
It checks learned rules first, then falls back to the hardcoded classifier.

This enables the self-learning pattern recognition system to improve
classification accuracy over time based on user feedback.
"""

import logging
from typing import Dict, List, Optional, Any

from mistake_classifier import (
    classify_mistake as classify_mistake_hardcoded,
    ClassifiedMistake,
    MistakeType,
    MistakeContext,
    GamePhase
)

logger = logging.getLogger(__name__)

# Global service instance (lazy-loaded)
_auto_correction_service = None


async def get_service():
    """Get or create the auto-correction service"""
    global _auto_correction_service
    if _auto_correction_service is None:
        from services.pattern_learning.auto_correction_service import AutoCorrectionService
        _auto_correction_service = AutoCorrectionService()
        await _auto_correction_service.initialize()
    return _auto_correction_service


async def classify_mistake_enhanced(
    fen_before: str,
    fen_after: str,
    move_played: str,
    best_move: str,
    eval_before: float,
    eval_after: float,
    user_color: str,
    move_number: int,
    threat: Optional[str] = None,
    pv_after_played: Optional[List[str]] = None,
    use_learned_rules: bool = True
) -> Dict:
    """
    Enhanced mistake classification that checks learned rules first.
    
    Args:
        fen_before: FEN before the move
        fen_after: FEN after the move
        move_played: The move that was played
        best_move: Stockfish's recommended move
        eval_before: Eval before move in centipawns
        eval_after: Eval after move in centipawns
        user_color: "white" or "black"
        move_number: Move number
        threat: Optional threat description
        pv_after_played: Principal variation after played move
        use_learned_rules: Whether to check learned rules first
        
    Returns:
        Dict with classification result including:
        - mistake_type: The classification type
        - explanation: The explanation (may be from learned rule)
        - confidence: Confidence score
        - is_learned: Whether this came from a learned rule
        - rule_id: ID of the learned rule (if applicable)
    """
    result = {
        "is_learned": False,
        "rule_id": None,
        "correction_used": False
    }
    
    # Calculate eval drop in pawns
    eval_drop_pawns = abs(eval_before - eval_after) / 100
    if user_color.lower() == "black":
        eval_drop_pawns = -eval_drop_pawns
    
    # Step 1: Check for existing correction (fastest path)
    if use_learned_rules and pv_after_played:
        try:
            service = await get_service()
            
            # Get hardcoded classification first to check if there's a correction
            hardcoded = classify_mistake_hardcoded(
                fen_before=fen_before,
                fen_after=fen_after,
                move_played=move_played,
                best_move=best_move,
                eval_before=eval_before,
                eval_after=eval_after,
                user_color=user_color,
                move_number=move_number,
                threat=threat,
                pv_after_played=pv_after_played
            )
            
            # Check for correction for this pattern
            correction = await service.get_correction_for_position(
                position_fen=fen_before,
                move_played=move_played,
                pv_after_played=pv_after_played,
                system_classification=hardcoded.mistake_type.value
            )
            
            if correction:
                # Use corrected classification
                result["is_learned"] = True
                result["correction_used"] = True
                result["mistake_type"] = correction.get("tactical_motif", hardcoded.mistake_type.value)
                result["explanation"] = correction.get("corrected_explanation", "")
                result["confidence"] = 0.95  # High confidence for verified corrections
                result["context"] = _context_to_dict(hardcoded.context)
                result["eval_before"] = hardcoded.eval_before
                result["eval_after"] = hardcoded.eval_after
                result["eval_drop"] = hardcoded.eval_drop
                result["move_played"] = hardcoded.move_played
                result["best_move"] = hardcoded.best_move
                result["pattern_details"] = hardcoded.pattern_details
                
                logger.info(f"Using correction for {hardcoded.mistake_type.value} -> {result['mistake_type']}")
                return result
                
        except Exception as e:
            logger.debug(f"Error checking corrections: {e}")
    
    # Step 2: Check learned rules
    if use_learned_rules and pv_after_played:
        try:
            service = await get_service()
            
            learned = await service.classify_with_learned_rules(
                position_fen=fen_before,
                move_played=move_played,
                pv_after_played=pv_after_played,
                eval_drop=eval_drop_pawns,
                best_move=best_move,
                user_color=user_color
            )
            
            if learned and learned.confidence >= 0.7:
                # Use learned rule classification
                result["is_learned"] = True
                result["rule_id"] = learned.rule_id
                result["mistake_type"] = learned.pattern
                result["explanation"] = learned.explanation
                result["confidence"] = learned.confidence
                result["matched_signals"] = learned.matched_signals
                
                # Still get context from hardcoded classifier
                hardcoded = classify_mistake_hardcoded(
                    fen_before=fen_before,
                    fen_after=fen_after,
                    move_played=move_played,
                    best_move=best_move,
                    eval_before=eval_before,
                    eval_after=eval_after,
                    user_color=user_color,
                    move_number=move_number,
                    threat=threat,
                    pv_after_played=pv_after_played
                )
                
                result["context"] = _context_to_dict(hardcoded.context)
                result["eval_before"] = hardcoded.eval_before
                result["eval_after"] = hardcoded.eval_after
                result["eval_drop"] = hardcoded.eval_drop
                result["move_played"] = hardcoded.move_played
                result["best_move"] = hardcoded.best_move
                result["pattern_details"] = hardcoded.pattern_details
                
                logger.info(f"Using learned rule {learned.rule_id}: {learned.pattern}")
                return result
                
        except Exception as e:
            logger.debug(f"Error checking learned rules: {e}")
    
    # Step 3: Fall back to hardcoded classifier
    hardcoded = classify_mistake_hardcoded(
        fen_before=fen_before,
        fen_after=fen_after,
        move_played=move_played,
        best_move=best_move,
        eval_before=eval_before,
        eval_after=eval_after,
        user_color=user_color,
        move_number=move_number,
        threat=threat,
        pv_after_played=pv_after_played
    )
    
    result["mistake_type"] = hardcoded.mistake_type.value
    result["explanation"] = hardcoded.pattern_details.get("reason", "")
    result["confidence"] = 1.0  # Hardcoded rules have full confidence
    result["context"] = _context_to_dict(hardcoded.context)
    result["eval_before"] = hardcoded.eval_before
    result["eval_after"] = hardcoded.eval_after
    result["eval_drop"] = hardcoded.eval_drop
    result["move_played"] = hardcoded.move_played
    result["best_move"] = hardcoded.best_move
    result["pattern_details"] = hardcoded.pattern_details
    result["hanging_piece"] = hardcoded.hanging_piece
    result["threat"] = hardcoded.threat
    
    return result


def _context_to_dict(context: MistakeContext) -> Dict:
    """Convert MistakeContext to dictionary"""
    return {
        "phase": context.phase.value,
        "was_ahead": context.was_ahead,
        "was_behind": context.was_behind,
        "was_equal": context.was_equal,
        "after_opponent_check": context.after_opponent_check,
        "opponent_had_threat": context.opponent_had_threat,
        "material_balance": context.material_balance,
        "move_number": context.move_number,
        "is_late_game": context.is_late_game,
        "user_color": context.user_color
    }


# Synchronous wrapper for backward compatibility
def classify_mistake_sync(
    fen_before: str,
    fen_after: str,
    move_played: str,
    best_move: str,
    eval_before: float,
    eval_after: float,
    user_color: str,
    move_number: int,
    threat: Optional[str] = None,
    pv_after_played: Optional[List[str]] = None
) -> ClassifiedMistake:
    """
    Synchronous version that uses only hardcoded rules.
    Use classify_mistake_enhanced for async with learned rules.
    """
    return classify_mistake_hardcoded(
        fen_before=fen_before,
        fen_after=fen_after,
        move_played=move_played,
        best_move=best_move,
        eval_before=eval_before,
        eval_after=eval_after,
        user_color=user_color,
        move_number=move_number,
        threat=threat,
        pv_after_played=pv_after_played
    )
