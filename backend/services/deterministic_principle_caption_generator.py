"""
Deterministic Principle Caption Generator — Generate captions using detector results.

Replaces Claude dependency with fast, deterministic logic.
Runs locally without any API calls.
"""

import logging
from typing import Dict, Optional, List
import chess

logger = logging.getLogger(__name__)


async def generate_principle_caption_from_detectors(
    fen: str,
    move_san: str,
    eval_before: int,
    eval_after: int,
    best_move_san: Optional[str],
    detector_results: Dict[str, Optional[str]],
) -> dict:
    """
    Generate a principle-based caption using detector results.

    Args:
        fen: Position FEN
        move_san: Move in SAN
        eval_before: Evaluation before move
        eval_after: Evaluation after move
        best_move_san: Best move if different
        detector_results: Output from run_detectors_on_move()
                         {
                           "rule_of_square": "applies"|"violates"|None,
                           "critical_piece": "applies"|"violates"|None,
                           ...
                         }

    Returns:
        {
            "caption": "principle-based explanation",
            "principles": ["rule_of_square", "critical_piece"],
            "quality_score": 0.85,
            "method": "deterministic"
        }
    """

    cp_loss = eval_before - eval_after
    board = chess.Board(fen)

    # Extract which principles fired
    principles_applied = []
    violations = []

    for detector_name, result in detector_results.items():
        if result == "applies":
            principles_applied.append(detector_name)
        elif result == "violates":
            violations.append(detector_name)

    # Build caption from principles
    if not principles_applied and not violations:
        # No principles detected
        return _fallback_caption(move_san, best_move_san, cp_loss)

    caption = _build_caption_from_principles(
        move_san=move_san,
        principles_applied=principles_applied,
        violations=violations,
        best_move_san=best_move_san,
        fen=fen,
        board=board,
    )

    # Quality scoring
    all_principles = principles_applied + violations
    quality_score = min(0.95, 0.5 + len(all_principles) * 0.25)

    return {
        "caption": caption,
        "principles": all_principles,
        "quality_score": quality_score,
        "method": "deterministic",
    }


def _build_caption_from_principles(
    move_san: str,
    principles_applied: List[str],
    violations: List[str],
    best_move_san: Optional[str],
    fen: str,
    board: chess.Board,
) -> str:
    """Build narrative caption from detector principles"""

    lines = []

    # Lead with violation if exists
    if violations:
        if "rule_of_square" in violations:
            lines.append(
                f"{move_san} violates the rule of the square — your king can't catch "
                f"the opponent's pawn."
            )
        if "critical_piece" in violations:
            lines.append(f"{move_san} abandons a critical defensive piece.")
        if "promotion_threat" in violations:
            lines.append(f"{move_san} allows the opponent's pawn to promote.")

    # Add applied principles
    if principles_applied:
        if "rule_of_square" in principles_applied:
            lines.append(
                f"Good: Your king moves into the square — you can catch the pawn."
            )
        if "critical_piece" in principles_applied:
            lines.append(
                f"Your piece maintains its critical defensive role."
            )
        if "promotion_threat" in principles_applied:
            lines.append(
                f"You control the promotion square."
            )

    # Add better move suggestion
    if best_move_san and violations:
        lines.append(f"Play {best_move_san} instead.")

    if not lines:
        return f"{move_san} is evaluated at {abs(eval_before - best_move_san if best_move_san else '')} centipawns."

    return " ".join(lines)


def _fallback_caption(move_san: str, best_move_san: Optional[str], cp_loss: float) -> dict:
    """Fallback caption when no principles detect"""
    if cp_loss >= 300:
        caption = f"{move_san} is a blunder (loses ~{int(cp_loss)} centipawns)."
    elif cp_loss >= 150:
        caption = f"{move_san} is a mistake."
    elif cp_loss >= 50:
        caption = f"{move_san} is inaccurate."
    else:
        caption = f"{move_san} is reasonable."

    if best_move_san:
        caption += f" {best_move_san} was better."

    return {
        "caption": caption,
        "principles": [],
        "quality_score": 0.4,
        "method": "fallback",
    }
