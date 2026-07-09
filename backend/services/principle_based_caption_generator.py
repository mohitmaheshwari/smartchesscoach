"""
Principle-based caption generator — integrates classifier + Claude analyzer.

This is the main entry point that takes a move and generates a principle-driven
caption by:
1. Classifying the position
2. Extracting threats and critical pieces
3. Using Claude to generate explanation
4. Verifying quality
"""

import logging
from typing import Optional
import chess

from services.endgame_classifier import classify_position, EndgameInfo
from services.claude_endgame_analyzer import analyze_endgame_move

logger = logging.getLogger(__name__)


async def generate_principle_based_caption(
    fen: str,
    move_san: str,
    eval_before: int,
    eval_after: int,
    best_move_san: Optional[str] = None,
) -> dict:
    """
    Generate a principle-based caption for a move.

    Args:
        fen: Position FEN
        move_san: Move in SAN notation (e.g., "Rf3+")
        eval_before: Evaluation before move
        eval_after: Evaluation after move
        best_move_san: Best move if different

    Returns:
        {
            "caption": "full explanation",
            "position_type": "K+R vs K+P",
            "principles": ["rule_of_square", "critical_piece"],
            "quality_score": 0.85
        }
    """

    try:
        # Parse position
        board = chess.Board(fen)

        # Step 1: Classify position
        position_info: EndgameInfo = classify_position(board)

        # Only use Claude for endgames with significant eval loss
        cp_loss = eval_before - eval_after
        if cp_loss < 100 or not position_info.is_theoretical_endgame:
            # Use fallback for small losses or non-endgames
            return _fallback_caption(move_san, best_move_san, cp_loss, position_info.position_type)

        # Step 2: Analyze with Claude
        explanation = await analyze_endgame_move(
            fen=fen,
            move_san=move_san,
            position_type=position_info.position_type,
            critical_pieces=position_info.critical_pieces,
            threats=position_info.threats,
            eval_before=eval_before,
            eval_after=eval_after,
            best_move_san=best_move_san,
        )

        # Step 3: Verify quality (must mention principles)
        principles = _extract_principles(explanation)
        quality_score = 0.85 if len(principles) >= 2 else 0.7

        # Step 4: Return result
        return {
            "caption": explanation,
            "position_type": position_info.position_type,
            "principles": principles,
            "quality_score": quality_score,
            "method": "claude_analyzed",
        }

    except Exception as e:
        logger.error(f"Principle-based caption generation failed: {e}")
        return {
            "caption": f"{move_san} is not the best move.",
            "position_type": "unknown",
            "principles": [],
            "quality_score": 0.3,
            "method": "fallback_error",
        }


def _fallback_caption(move_san: str, best_move_san: Optional[str], cp_loss: int, position_type: str) -> dict:
    """Generate a simple caption when Claude is not used"""
    if cp_loss >= 300:
        caption = f"{move_san} loses significant advantage (blunder)."
    elif cp_loss >= 150:
        caption = f"{move_san} is a serious mistake."
    elif cp_loss >= 100:
        caption = f"{move_san} is a mistake."
    elif cp_loss >= 50:
        caption = f"{move_san} is not ideal."
    else:
        caption = f"{move_san} is slightly inaccurate."

    if best_move_san:
        caption += f" Better: {best_move_san}."

    return {
        "caption": caption,
        "position_type": position_type,
        "principles": [],
        "quality_score": 0.4,
        "method": "fallback_simple",
    }


def _extract_principles(explanation: str) -> list:
    """Extract principle keywords from explanation"""
    principles = []
    keywords = {
        "rule of the square": "rule_of_square",
        "rule of square": "rule_of_square",
        "opposition": "opposition",
        "critical piece": "critical_piece",
        "promotion": "promotion_threat",
        "pawn promotes": "promotion_threat",
        "rook activity": "piece_activity",
        "king activity": "king_activity",
        "tempo": "tempo",
        "zugzwang": "zugzwang",
        "defend": "defense",
        "defend against": "defense",
    }

    explanation_lower = explanation.lower()
    for keyword, principle in keywords.items():
        if keyword in explanation_lower and principle not in principles:
            principles.append(principle)

    return principles
