"""
Caption Pipeline with Stockfish Verification

Wraps caption_pipeline.build_move_teaching_decision() with a verification layer
that ensures ONLY Stockfish-backed facts generate captions.

Every detected fact must pass Gate 1 (cp_loss significant) and Gate 2 (fact matches eval).

Usage:
    from services.caption_pipeline_verified import build_move_teaching_decision_verified

    result = await build_move_teaching_decision_verified(inputs, state)
    # result.decision has "verified" flag on caption
"""

import logging
from typing import Any, Dict, Optional, Tuple
from dataclasses import dataclass, replace

from services.caption_pipeline import (
    build_move_teaching_decision,
    MoveInputs,
    CrossMoveState,
    MoveTeachingDecision,
)
from services.caption_facts_verified import extract_facts_verified

logger = logging.getLogger(__name__)

# Feature flag: enable Stockfish verification layer
CAPTION_VERIFICATION_ENABLED = True


def build_move_teaching_decision_verified(
    inputs: MoveInputs,
    state: CrossMoveState,
) -> Tuple[MoveTeachingDecision, CrossMoveState]:
    """
    Build move teaching decision with Stockfish verification gates.

    Same interface as build_move_teaching_decision, but ensures:
      1. cp_loss is significant (>= 100)
      2. Detected facts match Stockfish eval
      3. Every caption has "verified" flag

    Returns (decision, new_state) where:
      - decision.caption is only shown if decision.caption_verified == True
      - decision.caption_verified == False means silence or fallback-only
    """

    if not CAPTION_VERIFICATION_ENABLED:
        # Fallback to original pipeline
        return build_move_teaching_decision(inputs, state)

    # Get original decision
    decision, new_state = build_move_teaching_decision(inputs, state)

    # Verify the facts that generated this caption
    try:
        verified_facts = extract_facts_verified(
            fen_before=inputs.fen_before,
            played_san=inputs.played_san,
            best_move_san=inputs.best_move_san,
            eval_before_cp=inputs.eval_before_cp,
            eval_after_cp=inputs.eval_after_cp,
            pv_after_played=list(inputs.pv_after_played) if inputs.pv_after_played else None,
            pv_after_best=list(inputs.pv_after_best) if inputs.pv_after_best else None,
            move_history_san=list(inputs.move_history_san) if inputs.move_history_san else None,
            full_move_number=int(inputs.full_move_number or 0),
        )

        is_verified = verified_facts.get("verified", False)
        verification_reason = verified_facts.get("verification_reason", "verified")

        # Add verification metadata to decision
        verified_decision = _add_verification_to_decision(
            decision,
            is_verified,
            verification_reason,
        )

        return verified_decision, new_state

    except Exception as e:
        logger.exception(f"[caption_verification] verification failed: {e}")
        # On error, mark as unverified but return caption anyway
        verified_decision = _add_verification_to_decision(
            decision,
            False,
            f"verification_error: {str(e)[:50]}",
        )
        return verified_decision, new_state


def _add_verification_to_decision(
    decision: MoveTeachingDecision,
    is_verified: bool,
    reason: str,
) -> MoveTeachingDecision:
    """Add verification flag to decision metadata."""

    # Enhance the decision's metadata
    metadata = dict(decision.metadata or {})
    metadata["caption_verified"] = is_verified
    metadata["verification_reason"] = reason

    # Return modified decision
    return replace(
        decision,
        metadata=metadata,
    )


def filter_unverified_captions(decision: MoveTeachingDecision) -> Optional[str]:
    """
    Filter caption based on verification flag.

    Returns:
      - caption if verified
      - None if not verified (silence)
    """
    metadata = decision.metadata or {}
    is_verified = metadata.get("caption_verified", True)

    if not is_verified:
        return None  # Silence

    return decision.caption  # Show caption
