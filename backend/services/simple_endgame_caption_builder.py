"""
Simple Endgame Caption Builder — Deterministic, local, no Claude.

Analyzes endgame moves using correct principle checks.
Uses verified chess logic, not heuristics.
CRITICAL: Every caption must be backed by Stockfish evaluation.
"""

import logging
import chess
from typing import Dict, Optional
from services.endgame_detectors.promotion_threat_correct import (
    detect_promotion_threat_move,
    build_promotion_threat_caption,
    identify_promotion_threats,
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
    MANDATORY: All captions must be verified against Stockfish evaluation.

    Args:
        fen: Position FEN
        move_san: Move SAN
        eval_before: Eval before move (from Stockfish)
        eval_after: Eval after move (from Stockfish)
        best_move_san: Best move if different

    Returns:
        {
            "caption": "explanation",
            "principles": ["principle1", ...],
            "quality_score": 0.7,
            "method": "deterministic",
            "verified": True/False
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

    # GATE 1: Only proceed if Stockfish shows real cp_loss
    if cp_loss < 100:
        # Move is not a real mistake by engine standards
        return _fallback_caption(move_san, best_move_san, cp_loss)

    # PRIMARY DETECTOR: Promotion Threats
    promotion_detection = detect_promotion_threat_move(board, move, user_color)

    if promotion_detection:
        # GATE 2: Verify threat is consistent with Stockfish eval
        threats = identify_promotion_threats(board, user_color)
        if not _is_threat_consistent_with_eval(
            board, move, user_color, threats, promotion_detection, cp_loss
        ):
            # Detection fired but eval doesn't support the threat as reason
            return _fallback_caption(move_san, best_move_san, cp_loss)

        # GATE 3: Build caption only if verification passes
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

            quality_score = 0.85 if cp_loss > 150 else 0.80

            return {
                "caption": caption_result,
                "principles": principles,
                "quality_score": quality_score,
                "method": "deterministic",
                "verified": True,
            }

    # FALLBACK: If no promotion threats detected, use eval-based caption
    return _fallback_caption(move_san, best_move_san, cp_loss)


def _is_threat_consistent_with_eval(
    board: chess.Board,
    move: chess.Move,
    user_color: chess.Color,
    threats: list,
    detection: str,
    cp_loss: int,
) -> bool:
    """
    Verify that the detected threat is consistent with Stockfish evaluation.

    A threat is consistent if:
    1. There ARE threats close to promotion (< 3 moves)
    2. The detection type matches the eval severity
    3. cp_loss is significant enough for the threat level

    Returns True only if threat explains the cp_loss meaningfully.
    """
    if not threats:
        return False

    # Filter for immediate threats (within 3 moves)
    immediate_threats = [t for t in threats if t["moves_to_promotion"] <= 3]
    if not immediate_threats:
        return False

    # Check threat severity vs cp_loss
    if detection == "allows":
        # Allowing a promotion threat should show significant cp_loss
        # (at least 75cp, since pawn promotion is major threat)
        return cp_loss >= 75

    elif detection == "defends":
        # Defending against threat should improve position
        # (positive cp_loss means we gained, but eval_after should be better than eval_before)
        # This case is for good moves, so we'd see cp_loss < 0 or small
        return cp_loss < 50  # Only caption defensive moves if they don't lose material

    elif detection == "maintains":
        # Maintaining defense should hold position
        return cp_loss < 75

    return False


def _fallback_caption(move_san: str, best_move_san: Optional[str], cp_loss: float) -> Dict:
    """Fallback caption when no principles detect or verification fails"""
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
        "verified": False,
    }
