"""
Chess Brain Integration
========================

Integrates the Chess Brain deterministic coaching engine
with the existing /coach/play/move endpoint.

This module provides:
- get_chess_brain_feedback: Get coaching from Chess Brain
- merge_with_existing_feedback: Combine with existing feedback sources
"""

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


async def get_chess_brain_feedback(
    db,
    fen_before: str,
    user_move: str,
    user_id: str,
    session_id: str,
    stockfish_analysis: Dict[str, Any],
    user_color: str,
    move_number: int,
    time_spent: Optional[float] = None,
    time_remaining: Optional[float] = None,
    consecutive_blunders: int = 0,
    opening_name: Optional[str] = None,
    opening_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get coaching feedback from the Chess Brain deterministic engine.
    
    This is the primary entry point for the new coaching system.
    
    Args:
        db: Database connection
        fen_before: Position before user's move
        user_move: User's move in SAN notation
        user_id: User identifier
        session_id: Coach session identifier
        stockfish_analysis: Pre-computed Stockfish analysis
        user_color: "white" or "black"
        move_number: Current move number
        time_spent: Seconds spent on this move
        time_remaining: Remaining clock time
        consecutive_blunders: Number of blunders in a row
        opening_name: If in known opening
        opening_key: Opening identifier
    
    Returns:
        Dictionary with coaching feedback compatible with frontend:
        - coaching_message: Main insight text
        - user_move_quality: "excellent", "good", "inaccuracy", "mistake", "blunder"
        - best_move: The Stockfish best move
        - best_move_explanation: Why the best move is better
        - socratic_question: Question to ask user (if any)
        - encouragement: Positive message (if any)
        - teaching_mode: Which of the 7 modes this uses
        - highlight_squares: Squares to highlight on board
    """
    try:
        from services.chess_brain import ChessBrain
        
        brain = ChessBrain(db)
        
        output = await brain.analyze_move(
            fen_before=fen_before,
            user_move=user_move,
            user_id=user_id,
            session_id=session_id,
            stockfish_analysis=stockfish_analysis,
            time_spent=time_spent,
            time_remaining=time_remaining,
            consecutive_blunders=consecutive_blunders,
            opening_name=opening_name,
            opening_key=opening_key
        )
        
        # Convert to frontend-compatible format
        return {
            "coaching_message": output.coaching_message,
            "user_move_quality": output.move_quality.value,
            "quality": output.move_quality.value,  # Alias for frontend compatibility
            "best_move": output.best_move,
            "best_move_explanation": output.selected_lesson.better_move_explanation or "",
            "socratic_question": output.socratic_question,
            "encouragement": output.encouragement,
            "quality_badge": output.quality_badge,
            "teaching_mode": output.teaching_mode.value,
            "highlight_squares": output.highlight_squares,
            # Additional lesson info
            "main_insight": output.selected_lesson.main_insight,
            "why_section": output.selected_lesson.why_section,
            "next_idea": output.selected_lesson.next_idea,
            "lesson_title": output.selected_lesson.title,
            # Metadata
            "is_chess_brain": True,
            "candidates_evaluated": output.candidates_evaluated,
            "winning_score": output.winning_score,
            "cp_loss": output.cp_loss
        }
        
    except Exception as e:
        logger.error(f"Chess Brain feedback failed: {e}")
        # Return fallback
        return {
            "coaching_message": f"You played {user_move}. Let's see what happens.",
            "user_move_quality": "neutral",
            "quality": "neutral",
            "best_move": stockfish_analysis.get("best_move", user_move),
            "is_chess_brain": False,
            "error": str(e)
        }


def merge_feedback_sources(
    chess_brain_feedback: Dict[str, Any],
    socratic_feedback: Optional[Dict[str, Any]] = None,
    wisdom_feedback: Optional[Dict[str, Any]] = None,
    memory_context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Merge feedback from multiple coaching sources.
    
    Priority:
    1. Chess Brain (deterministic, most reliable)
    2. Wisdom-based coaching (rule-based)
    3. Socratic feedback (dialogue-based)
    4. Memory context (personalization)
    
    Returns combined feedback dictionary.
    """
    # Start with Chess Brain as base
    result = dict(chess_brain_feedback)
    
    # Add memory references if available
    if memory_context:
        if memory_context.get("memory_reference"):
            result["memory_reference"] = memory_context["memory_reference"]
        if memory_context.get("pattern_connection"):
            result["pattern_connection"] = memory_context["pattern_connection"]
        if memory_context.get("is_recurring"):
            result["is_recurring"] = memory_context["is_recurring"]
    
    # Add wisdom rule if more specific
    if wisdom_feedback and wisdom_feedback.get("rule_id"):
        result["wisdom_rule_id"] = wisdom_feedback["rule_id"]
        result["memorable_rule"] = wisdom_feedback.get("memorable_rule")
    
    # Add Socratic dialogue context if available
    if socratic_feedback:
        if socratic_feedback.get("dialogue_id"):
            result["dialogue_id"] = socratic_feedback["dialogue_id"]
        # Prefer Socratic question if Chess Brain didn't provide one
        if not result.get("socratic_question") and socratic_feedback.get("question"):
            result["socratic_question"] = socratic_feedback["question"]
    
    return result


async def build_coaching_feedback(
    db,
    session_id: str,
    user_id: str,
    fen_before: str,
    user_move: str,
    stockfish_analysis: Dict[str, Any],
    user_color: str,
    move_number: int,
    user_rating: int,
    **kwargs
) -> Dict[str, Any]:
    """
    Build complete coaching feedback for a move.
    
    This is the main integration point that combines:
    - Chess Brain deterministic analysis
    - Memory/personalization
    - Session context
    
    Returns a complete feedback dictionary ready for the frontend.
    """
    # 1. Get Chess Brain feedback
    chess_brain = await get_chess_brain_feedback(
        db=db,
        fen_before=fen_before,
        user_move=user_move,
        user_id=user_id,
        session_id=session_id,
        stockfish_analysis=stockfish_analysis,
        user_color=user_color,
        move_number=move_number,
        **kwargs
    )
    
    # 2. Get memory context (for personalization)
    memory_context = None
    try:
        from services.coach_memory import get_realtime_pattern_context
        
        # Determine mistake type from quality
        quality = chess_brain.get("user_move_quality", "neutral")
        if quality in ["blunder", "mistake"]:
            mistake_type = "tactical_miss"  # Default
            if chess_brain.get("teaching_mode") == "tactical_pattern_teaching":
                mistake_type = "missed_tactic"
            
            memory_context = await get_realtime_pattern_context(
                db=db,
                user_id=user_id,
                mistake_type=mistake_type
            )
    except Exception as e:
        logger.warning(f"Memory context retrieval failed: {e}")
    
    # 3. Merge sources
    result = merge_feedback_sources(
        chess_brain_feedback=chess_brain,
        memory_context=memory_context
    )
    
    # 4. Add session context
    result["session_id"] = session_id
    result["move_number"] = move_number
    result["user_rating"] = user_rating
    
    return result


# Convenience functions for common scenarios

def get_quality_emoji(quality: str) -> str:
    """Get appropriate emoji for move quality."""
    emojis = {
        "brilliant": "!",
        "excellent": "+",
        "good": "",
        "inaccuracy": "?!",
        "mistake": "?",
        "blunder": "??"
    }
    return emojis.get(quality, "")


def get_indian_english_message(template: str, **kwargs) -> str:
    """
    Add Indian-English flavor to coaching messages.
    
    This is optional polishing - the core message comes from Chess Brain.
    """
    # Simple word substitutions for Indian-English feel
    replacements = {
        "Let's": "Chalo",
        "Great!": "Bahut accha!",
        "Good job": "Shabash",
        "Hmm": "Dekho",
        "I see": "Achcha",
        "right?": "na?",
        "you know": "dekho na",
    }
    
    result = template
    for eng, hindi in replacements.items():
        # Only replace occasionally for natural feel
        if eng in result:
            # Use Hindi version sometimes
            import random
            if random.random() < 0.3:  # 30% chance
                result = result.replace(eng, hindi, 1)
    
    return result.format(**kwargs)
