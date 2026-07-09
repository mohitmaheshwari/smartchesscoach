"""
Simple Endgame Caption Builder — Deterministic, local, no Claude.

Analyzes endgame moves using correct principle checks.
Uses verified chess logic, not heuristics.
"""

import logging
import chess
from typing import Dict, Optional
from services.endgame_detectors.promotion_threat_correct import (
    detect_promotion_threat_move,
    build_promotion_threat_caption,
)

logger = logging.getLogger(__name__)


async def build_endgame_caption(
    fen: str,
    move_san: str,
    eval_before: int,
    eval_after: int,
    best_move_san: Optional[str],
) -> Dict:
    """
    Build principle-based endgame caption without Claude.

    Uses correct chess logic to detect promotion threats and defenses.

    Args:
        fen: Position FEN
        move_san: Move SAN
        eval_before: Eval before move
        eval_after: Eval after move
        best_move_san: Best move if different

    Returns:
        {
            "caption": "explanation",
            "principles": ["principle1", ...],
            "quality_score": 0.7,
            "method": "deterministic"
        }
    """

    try:
        board = chess.Board(fen)
    except:
        return _fallback_caption(move_san, best_move_san, eval_before - eval_after)

    # Find the move
    move = None
    for m in board.legal_moves:
        if board.san(m) == move_san:
            move = m
            break

    if not move:
        return _fallback_caption(move_san, best_move_san, eval_before - eval_after)

    cp_loss = eval_before - eval_after
    user_color = board.turn  # User's color is who's turn it is BEFORE the move

    # PRIMARY DETECTOR: Promotion Threats
    promotion_detection = detect_promotion_threat_move(board, move, user_color)

    if promotion_detection:
        # Use the promotion threat caption
        caption_result = build_promotion_threat_caption(
            board=board,
            move=move,
            move_san=move_san,
            user_color=user_color,
            detection=promotion_detection,
            eval_before=eval_before,
            eval_after=eval_after,
        )

        if caption_result:
            principles = []
            if promotion_detection == "allows":
                principles.append("allows_promotion")
            elif promotion_detection == "defends":
                principles.append("promotion_defense")
            elif promotion_detection == "maintains":
                principles.append("maintains_defense")

            quality_score = 0.80 if cp_loss > 100 else 0.70

            return {
                "caption": caption_result,
                "principles": principles,
                "quality_score": quality_score,
                "method": "deterministic",
            }

    # FALLBACK: If no promotion threats detected, use eval-based caption
    return _fallback_caption(move_san, best_move_san, cp_loss)


def _fallback_caption(move_san: str, best_move_san: Optional[str], cp_loss: float) -> Dict:
    """Fallback caption when no principles detect"""
    if cp_loss >= 300:
        caption = f"{move_san} is a blunder."
    elif cp_loss >= 150:
        caption = f"{move_san} is a serious mistake."
    elif cp_loss >= 50:
        caption = f"{move_san} is not best."
    else:
        caption = f"{move_san} is played."

    if best_move_san:
        caption += f" {best_move_san} was better."

    return {
        "caption": caption,
        "principles": [],
        "quality_score": 0.3,
        "method": "fallback",
    }
