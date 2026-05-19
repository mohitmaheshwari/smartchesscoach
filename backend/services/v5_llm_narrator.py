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

import json
import os
import logging
from typing import Dict, List, Optional
from dotenv import load_dotenv

from llm_service import call_llm
from services.coach_voice_prompt import with_coach_voice

load_dotenv()
logger = logging.getLogger(__name__)

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
NARRATOR_MODEL = os.environ.get("V5_NARRATOR_MODEL", "gpt-4o-mini")


def _llm_available() -> bool:
    """True if the API key for the configured NARRATOR_MODEL is present."""
    if NARRATOR_MODEL.startswith("claude"):
        return bool(ANTHROPIC_API_KEY)
    return bool(OPENAI_API_KEY)

# System prompt for concise narrative generation.
#
# Role: LLM is a REWRITER, not an author. It receives a grounded plan
# (what went wrong + better move, both derived from Stockfish upstream)
# and outputs the same truth in warmer coach voice. It does not invent.
NARRATOR_SYSTEM_PROMPT = """You are a friendly chess coach rewriting a short critique in natural voice.

You will be given:
- The move the player made (in chess notation)
- The problem with that move (one sentence of ground truth)
- What they should have played instead (often names a specific move)

Your job: REWRITE this in warm coach voice, as one short sentence.

HARD RULES — violating these fails the task:
1. MAX 15 words total.
2. DO NOT introduce any move, piece, square, tactic, or chess concept that is NOT in the input.
   If the input doesn't name Bxb5, you MUST NOT name Bxb5.
   If the input doesn't say "fork", you MUST NOT say "fork".
   Invent nothing.
3. Keep the exact move names and ideas from the input — just rephrase the WORDS.
4. No engine language (eval, centipawns, accuracy).
5. No catchy rhymes or invented hooks ("Knights on the rim are dim" etc.) unless
   the input literally already makes that point.
6. If the input is already natural, output it essentially unchanged.

Output ONLY the rewritten sentence. No quotes, no labels, no JSON."""


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
    if not _llm_available():
        return _generate_fallback_narrative(move_san, plan_data, severity)

    # Build the grounded context. Only pass what the upstream plan
    # actually contains — no invented fields, no assumptions. If plan_data
    # is empty, the LLM has nothing to rewrite; we go straight to fallback.
    if not plan_data:
        return _generate_fallback_narrative(move_san, plan_data, severity)

    problem = (plan_data.get("current_problem") or "").strip()
    better = (plan_data.get("better_approach") or "").strip()

    if not problem and not better:
        return _generate_fallback_narrative(move_san, plan_data, severity)

    lines = [f"Move played: {move_san}"]
    if problem:
        lines.append(f"Problem: {problem}")
    if better:
        lines.append(f"What was better: {better}")

    user_prompt = (
        "\n".join(lines)
        + "\n\nRewrite the critique above as one short coach-voice sentence. "
        "Use only the moves and ideas already named. Do not add anything."
    )

    try:
        response = await call_llm(
            system_message=with_coach_voice(NARRATOR_SYSTEM_PROMPT),
            user_message=user_prompt,
            model=NARRATOR_MODEL,
            max_tokens=120,
        )

        narrative = response.strip().strip('"').strip("'")

        # Hard length cap — anything over 25 words means the LLM ignored the
        # constraint and probably invented something. Drop to fallback in
        # that case; don't try to truncate a paragraph-hallucination.
        words = narrative.split()
        if len(words) > 25:
            logger.debug(f"LLM narrator output too long ({len(words)} words) — using fallback")
            return _generate_fallback_narrative(move_san, plan_data, severity)

        return narrative

    except Exception as e:
        logger.error(f"LLM narrator error: {e}")
        return _generate_fallback_narrative(move_san, plan_data, severity)


async def generate_opponent_narrative(
    move_san: str,
    eval_swing: int,
    user_color: str,
    weak_squares: List[str]
) -> tuple:
    """
    Generate narrative for opponent's move from user's perspective.

    Returns:
        (narrative, your_plan_now)
    """
    if not _llm_available():
        return _fallback_opponent_narrative(move_san, eval_swing, weak_squares)

    if eval_swing > 150:
        situation = "Opponent blundered"
    elif eval_swing > 50:
        situation = "Opponent made a small mistake"
    else:
        situation = "Normal move"

    user_prompt = f"""Opponent played: {move_san}
Situation: {situation}
User plays: {user_color}
{f'Weak squares created: {", ".join(weak_squares)}' if weak_squares else ''}

Generate TWO things (each under 15 words):
1. What this move did (from user's perspective)
2. What user's plan should be now

Format: Line 1 = observation, Line 2 = plan"""

    try:
        response = await call_llm(
            system_message=with_coach_voice("Be concise and actionable. Max 15 words per line."),
            user_message=user_prompt,
            model=NARRATOR_MODEL,
            max_tokens=120,
        )

        lines = response.strip().split("\n")
        narrative = lines[0].strip() if lines else f"Opponent played {move_san}."
        plan = lines[1].strip() if len(lines) > 1 else None

        return narrative, plan

    except Exception as e:
        logger.error(f"LLM opponent narrator error: {e}")
        return _fallback_opponent_narrative(move_san, eval_swing, weak_squares)


async def generate_good_move_praise(
    move_san: str,
    concept_applied: Optional[str],
    is_best_move: bool,
    phase: str
) -> str:
    """
    Generate praise for a good move. Keep it short and genuine.
    """
    if not _llm_available():
        return _fallback_good_move(move_san, concept_applied, is_best_move)

    context = f"Move: {move_san}\nPhase: {phase}\n"
    if is_best_move:
        context += "This was the BEST move in the position!\n"
    if concept_applied:
        context += f"User demonstrated understanding of: {concept_applied.replace('_', ' ')}"

    user_prompt = f"""{context}

Generate a SHORT (max 10 words) genuine praise that feels human, not robotic.
Don't say "great move" or "well done" - be more specific."""

    try:
        response = await call_llm(
            system_message=with_coach_voice("Praise for a good move. Max 10 words. Be specific, not robotic."),
            user_message=user_prompt,
            model=NARRATOR_MODEL,
            max_tokens=80,
        )
        return response.strip().strip('"').strip("'")

    except Exception as e:
        logger.error(f"LLM good move error: {e}")
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
    """Fallback for opponent move narrative."""
    if eval_swing > 150:
        narrative = f"Your opponent blundered with {move_san}!"
        plan = f"Target the weakness{': ' + ', '.join(weak_squares[:2]) if weak_squares else ''}."
    elif eval_swing > 50:
        narrative = f"Opponent's {move_san} is slightly inaccurate."
        plan = "Look for ways to take advantage."
    else:
        narrative = f"Opponent played {move_san}."
        plan = "Check: what does this threaten? What did it weaken?"

    return narrative, plan


def _fallback_good_move(move_san: str, concept_applied: Optional[str], is_best_move: bool) -> str:
    """Fallback for good move praise."""
    if is_best_move:
        if concept_applied:
            return f"You found the best move! Great {concept_applied.replace('_', ' ')}."
        return f"You found the best move! {move_san} is exactly right."

    if concept_applied:
        return f"Solid — good {concept_applied.replace('_', ' ')}."

    return f"Good — {move_san}."


async def generate_narratives_batch(moves_data: List[Dict]) -> Dict[int, str]:
    """
    Generate narratives for multiple moves in a single batch.

    Returns: Dict mapping move_index to narrative
    """
    if not _llm_available():
        return {
            i: _generate_fallback_narrative(
                m.get("move_san", ""),
                m.get("plan"),
                m.get("severity", "good")
            )
            for i, m in enumerate(moves_data)
        }

    moves_context = []
    for i, m in enumerate(moves_data):
        plan = m.get("plan", {}) or {}
        moves_context.append(f"""
Move {i+1}: {m.get('move_san', '')}
Severity: {m.get('severity', 'good')}
Problem: {plan.get('current_problem', 'N/A')}
Consequence: {plan.get('consequence', 'N/A')}
Better: {plan.get('better_approach', 'N/A')}
Learning: {plan.get('transferable_learning', 'N/A')}
""")

    user_prompt = f"""Generate a MEMORABLE coaching sentence for each move below.
CRITICAL: Maximum 20 words each. Make each one stick in memory.

{chr(10).join(moves_context)}

Return as JSON: {{"1": "narrative for move 1", "2": "narrative for move 2", ...}}"""

    try:
        response = await call_llm(
            system_message=with_coach_voice(NARRATOR_SYSTEM_PROMPT + "\n\nReturn ONLY valid JSON."),
            user_message=user_prompt,
            model=NARRATOR_MODEL,
            max_tokens=1024,
        )

        try:
            narratives = json.loads(response.strip())
            return {int(k) - 1: v for k, v in narratives.items()}
        except json.JSONDecodeError:
            logger.warning("Failed to parse batch response, falling back")
            return {
                i: _generate_fallback_narrative(
                    m.get("move_san", ""),
                    m.get("plan"),
                    m.get("severity", "good")
                )
                for i, m in enumerate(moves_data)
            }

    except Exception as e:
        logger.error(f"Batch narrative error: {e}")
        return {
            i: _generate_fallback_narrative(
                m.get("move_san", ""),
                m.get("plan"),
                m.get("severity", "good")
            )
            for i, m in enumerate(moves_data)
        }
