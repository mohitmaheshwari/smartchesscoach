"""
INTEGRATION LAYER for Active Recall

Wires active_recall_service into the /v5/interactive-feedback endpoint.

Call this AFTER coaching decision is made to add active recall Q&A options.
"""

import logging

logger = logging.getLogger(__name__)


async def enrich_coaching_with_active_recall(
    db,
    coaching_response: dict,
    fen_before: str,
    user_move_san: str,
    best_move_san: str,
    cognitive_gap: str,
    user_rating: int,
    cp_loss: int = 0,
    user_id: str = None
) -> dict:
    """
    Add active recall options to coaching response if verification passes.

    Input: coaching_response from build_move_teaching_decision()
    Output: coaching_response with 'active_recall' field added (or None if skipped)

    Example:
        coaching_response = {
            "narrative": "Nf3 looks safe but centralizing is stronger",
            "severity": "mistake",
            ...
        }

        enriched = await enrich_coaching_with_active_recall(
            db=db,
            coaching_response=coaching_response,
            fen_before=fen,
            user_move_san="Nf3",
            best_move_san="Nd5",
            cognitive_gap="centralization",
            user_rating=1300
        )

        # enriched now has:
        coaching_response['active_recall'] = {
            "ranking": { ... },
            "concept": { ... }
        }
    """

    try:
        from active_recall_service import generate_active_recall

        # Generate active recall (returns None if verification fails)
        active_recall = await generate_active_recall(
            db=db,
            fen=fen_before,
            user_move_san=user_move_san,
            best_move_san=best_move_san,
            cognitive_gap=cognitive_gap,
            user_rating=user_rating,
            cp_loss=cp_loss
        )

        # Add to response (None means skip, frontend will just show coaching text)
        coaching_response['active_recall'] = active_recall

        if active_recall:
            logger.info(f"[AR-Integration] Active recall added for {cognitive_gap}")
        else:
            logger.debug(f"[AR-Integration] Skipped active recall (verification failed)")

        return coaching_response

    except Exception as e:
        logger.error(f"[AR-Integration] Error enriching coaching: {e}")
        # Don't fail the entire coaching flow - just skip active recall
        coaching_response['active_recall'] = None
        return coaching_response


async def record_active_recall_response(
    db,
    user_id: str,
    session_id: str,
    move_index: int,
    cognitive_gap: str,
    ranking_response: dict,  # { selected_index: int, correct_index: int }
    concept_response: dict,  # { selected_index: int, correct_index: int }
) -> dict:
    """
    Record user's response to active recall questions for learning analytics.

    Called from frontend after user submits ranking + concept answers.

    Returns learning checkpoint for spaced repetition service to use.
    """

    try:
        from active_recall_service import record_active_recall_response as record_response

        checkpoint = await record_response(
            db=db,
            user_id=user_id,
            session_id=session_id,
            move_index=move_index,
            cognitive_gap=cognitive_gap,
            ranking_response=ranking_response.get('selected_index'),
            ranking_correct_index=ranking_response.get('correct_index'),
            concept_response=concept_response.get('selected_index'),
            concept_correct_index=concept_response.get('correct_index'),
        )

        logger.info(f"[AR-Integration] Recorded: {cognitive_gap} -> {checkpoint['combined_score']}")
        return checkpoint

    except Exception as e:
        logger.error(f"[AR-Integration] Error recording response: {e}")
        return None
