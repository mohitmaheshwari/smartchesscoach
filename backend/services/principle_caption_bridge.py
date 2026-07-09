"""
Bridge between principle-based caption system and game_decryption_v5.

Enhances default captions with principle-based explanations for endgame mistakes.
Used during caption rendering to upgrade eval-driven captions to principle-driven.
"""

import logging
from typing import Optional, Dict, Any
import asyncio

logger = logging.getLogger(__name__)


async def enhance_caption_with_principles(
    caption_payload: Dict[str, Any],
    fen_before: str,
    move_san: str,
    eval_before: int,
    eval_after: int,
    best_move_san: Optional[str],
    phase: str,
    cp_loss: float,
) -> Dict[str, Any]:
    """
    Enhance a caption with principle-based explanation if applicable.

    Strategy:
    1. Only enhance endgame blunders (cp_loss > 150, phase == "endgame")
    2. Try to generate principle-based caption
    3. Compare with default caption
    4. Use principle-based if quality_score > 0.75 and has 2+ principles
    5. Fall back to default if principle caption fails or lower quality

    Args:
        caption_payload: Existing caption dict {"caption": str, "rule_name": str, ...}
        fen_before: Position FEN before move
        move_san: Move in SAN notation
        eval_before: Evaluation before move (cp)
        eval_after: Evaluation after move (cp)
        best_move_san: Best move if different
        phase: Game phase ("opening", "middlegame", "endgame")
        cp_loss: Centipawn loss

    Returns:
        Enhanced caption_payload (modified in-place or returned with principle caption)
    """

    # Gate 1: Only enhance significant endgame mistakes
    if phase != "endgame" or cp_loss < 150:
        return caption_payload

    # Gate 2: Don't over-apply (don't enhance if caption is already good)
    existing_caption = caption_payload.get("caption", "").strip()
    if not existing_caption or len(existing_caption) < 20:
        # Caption is empty or too short — worth trying to enhance
        pass
    elif "rule of" in existing_caption.lower() or "opposition" in existing_caption.lower():
        # Caption already mentions principles — don't re-enhance
        return caption_payload

    # Gate 3: Try principle-based generation
    try:
        from services.principle_based_caption_generator import generate_principle_based_caption

        principle_result = await generate_principle_based_caption(
            fen=fen_before,
            move_san=move_san,
            eval_before=eval_before,
            eval_after=eval_after,
            best_move_san=best_move_san,
        )

        # Gate 4: Quality check — only use if principle-based is better
        principle_caption = principle_result.get("caption", "").strip()
        principles = principle_result.get("principles", [])
        quality_score = principle_result.get("quality_score", 0)

        # Require 2+ principles and quality score >= 0.75
        if len(principles) >= 2 and quality_score >= 0.75 and principle_caption:
            logger.info(
                f"[principle-caption] Enhanced {move_san}: "
                f"quality={quality_score:.2f}, principles={principles}"
            )

            # Enhance caption_payload
            caption_payload["caption"] = principle_caption
            caption_payload["rule_name"] = (
                (caption_payload.get("rule_name") or "") + "→PRINCIPLE_ENHANCED"
            )

            # Track which principles were applied
            caption_payload["principles_applied"] = principles

            return caption_payload
        else:
            logger.debug(
                f"[principle-caption] Skipped {move_san}: "
                f"quality={quality_score:.2f} (need ≥0.75), "
                f"principles={len(principles)} (need ≥2)"
            )

    except Exception as e:
        logger.debug(f"[principle-caption] Generation failed for {move_san}: {e}")

    # Fallback: return unchanged caption_payload
    return caption_payload


async def should_enhance_caption(
    phase: str,
    severity: str,
    cp_loss: float,
    position_type: Optional[str] = None,
) -> bool:
    """
    Quick gate: should we even try to enhance this caption?

    Returns True if:
    - Phase is endgame
    - Severity is mistake/blunder
    - cp_loss > 150
    """
    if phase != "endgame":
        return False

    if severity not in ("mistake", "blunder", "opp_mistake", "opp_blunder"):
        return False

    if cp_loss < 150:
        return False

    return True
