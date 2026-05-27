"""
V5 LLM Narrator Service
========================

Lightweight LLM service for generating concise, memorable coaching narratives.

Key Principles:
1. LLM is ONLY a language translator - all chess logic comes from existing layers
2. Output must be under 20 words per move
3. Focus on the PLAN, not just the move
4. Make it memorable (user should remember this forever)

Routes through llm_service.call_llm. Defaults to gpt-4o-mini (cheapest);
swap to Claude by setting V5_NARRATOR_MODEL=claude-sonnet-4-6.
"""

import logging
from typing import Dict, List, Optional
from dotenv import load_dotenv

# Mohit 2026-05-27: ZERO LLM in coaching (review included). This module
# no longer imports call_llm — every function is deterministic. The
# `narrative` field is composed verbatim from the V5 plan's
# coach-authored strings (current_problem / better_approach). Per
# [[one-source-of-truth-for-coaching]].

load_dotenv()
logger = logging.getLogger(__name__)


async def generate_concise_narrative(
    move_san: str,
    plan_data: Dict,
    phase: str,
    severity: str,
    is_user_move: bool
) -> str:
    """
    Generate a concise (under 20 words) coaching narrative using LLM.

    Args:
        move_san: The move in SAN notation
        plan_data: Structured plan from V5 service containing:
            - goal: What we're trying to achieve
            - current_problem: Why current move doesn't achieve it
            - consequence: What happens after
            - better_approach: What to do instead
            - transferable_learning: The concept
        phase: "opening" | "middlegame" | "endgame"
        severity: "good" | "inaccuracy" | "mistake" | "blunder"
        is_user_move: True if this is user's move

    Returns:
        Concise narrative string (under 20 words)
    """
    # Mohit 2026-05-27: ZERO LLM in coaching, review included. The
    # narrator is now deterministic-only — it returns the plan_data
    # strings (current_problem / better_approach) verbatim via
    # _generate_fallback_narrative. Those strings are already
    # coach-authored by the deterministic V5 plan generator, so no LLM
    # rewrite is needed. Per [[one-source-of-truth-for-coaching]].
    #
    # (The function stays async + keeps its signature so the V5 service
    # call site at game_decryption_v5_service.py:3790 is unchanged.)
    return _generate_fallback_narrative(move_san, plan_data, severity)


async def generate_opponent_narrative(
    move_san: str,
    eval_swing: int,
    user_color: str,
    weak_squares: List[str]
) -> tuple:
    """Opponent-move narrative — DETERMINISTIC (Mohit 2026-05-27, zero
    LLM in coaching). Delegates to _fallback_opponent_narrative.
    (No production callers today; kept for signature stability.)"""
    return _fallback_opponent_narrative(move_san, eval_swing, weak_squares)


async def generate_good_move_praise(
    move_san: str,
    concept_applied: Optional[str],
    is_best_move: bool,
    phase: str
) -> str:
    """Good-move praise — DETERMINISTIC (Mohit 2026-05-27, zero LLM).
    Delegates to _fallback_good_move. (No production callers today.)"""
    return _fallback_good_move(move_san, concept_applied, is_best_move)


def _generate_fallback_narrative(move_san: str, plan_data: Dict, severity: str) -> str:
    """Deterministic fallback when the LLM isn't available.

    Uses plan_data.current_problem verbatim if present — it's the same
    ground-truth string the LLM would have rewritten. NO hardcoded
    pattern-based prefixes ("Your bishop needs an open diagonal…"): those
    were template lies that prepended a generic claim regardless of whether
    the actual problem was about diagonals.

    Updated 2026-05-19: when no concrete plan data exists (problem +
    better both empty), returns "" instead of hollow severity-only
    strings ("X was a blunder.", "X wasn't the best here."). Per audit
    1519831c surfaced 9,870 hollow-narrative violations in the corpus,
    same root cause as Parth's R12 empty-WHY (caption_rules.py fixed
    in 9b991160) — honest silence > fluffy template
    ([[no-hollow-coverage]]). The V5 caption pipeline (caption field)
    still provides a caption for these moves; suppressing the narrator
    here leaves the user with the V5-caption-only path, not no text.
    Callers already handle empty strings via `if narrative:` check.
    """
    problem = (plan_data.get("current_problem") or "").strip() if plan_data else ""
    better = (plan_data.get("better_approach") or "").strip() if plan_data else ""

    if problem:
        if move_san and move_san in problem:
            return problem
        return f"{move_san}: {problem}" if move_san else problem

    if better:
        return f"{move_san} — {better}" if move_san else better

    # No concrete data — return empty to signal "suppress narrative,
    # fall through to V5 caption pipeline."
    return ""


def _fallback_opponent_narrative(move_san: str, eval_swing: int, weak_squares: List[str]) -> tuple:
    """Fallback for opponent move narrative.

    Voice updated 2026-05-19 per Agent-1 voice audit + patient-academic
    calibration: no exclamation marks, no "blundered with X!" theatrics.
    Observational, concrete.
    """
    if eval_swing > 150:
        narrative = f"Opponent's {move_san} drops material."
        plan = f"Target the weakness{': ' + ', '.join(weak_squares[:2]) if weak_squares else ''}."
    elif eval_swing > 50:
        narrative = f"Opponent's {move_san} is slightly inaccurate."
        plan = "Look for ways to take advantage."
    else:
        narrative = f"Opponent played {move_san}."
        plan = "Check: what does this threaten? What did it weaken?"

    return narrative, plan


def _fallback_good_move(move_san: str, concept_applied: Optional[str], is_best_move: bool) -> str:
    """Fallback for good move praise.

    Voice updated 2026-05-19 per Agent-1 voice audit: no "You found
    the best move!" exclamations. Patient academic acknowledgment
    only — coach voice trusts the student.
    """
    if is_best_move:
        if concept_applied:
            return f"{move_san} — correct. Good {concept_applied.replace('_', ' ')}."
        return f"{move_san} — correct. Engine's pick."

    if concept_applied:
        return f"Solid — good {concept_applied.replace('_', ' ')}."

    return f"Good — {move_san}."


async def generate_narratives_batch(moves_data: List[Dict]) -> Dict[int, str]:
    """Batch narratives — DETERMINISTIC (Mohit 2026-05-27, zero LLM).
    Each narrative is the deterministic _generate_fallback_narrative
    output. (No production callers today.)"""
    return {
        i: _generate_fallback_narrative(
            m.get("move_san", ""),
            m.get("plan"),
            m.get("severity", "good"),
        )
        for i, m in enumerate(moves_data)
    }
