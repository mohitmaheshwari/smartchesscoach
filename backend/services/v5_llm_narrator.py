"""
V5 LLM Narrator Service
========================

Lightweight LLM service for generating concise, memorable coaching narratives.

Key Principles:
1. LLM is ONLY a language translator - all chess logic comes from existing layers
2. Output must be under 20 words per move
3. Focus on the PLAN, not just the move
4. Make it memorable (user should remember this forever)

Uses GPT-4.1-mini via emergentintegrations.
"""

import json
import os
import logging
from typing import Dict, List, Optional
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY", "")

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
    if not EMERGENT_LLM_KEY:
        logger.warning("No EMERGENT_LLM_KEY, using fallback narrative")
        return _generate_fallback_narrative(move_san, plan_data, severity)
    
    try:
        from llm_helper import LlmChat, UserMessage
        import uuid
        
        # Build the grounded context. Only pass what the upstream plan
        # actually contains — no invented fields, no assumptions. If plan_data
        # is empty, the LLM has nothing to rewrite; we go straight to fallback.
        if not plan_data:
            return _generate_fallback_narrative(move_san, plan_data, severity)

        problem = (plan_data.get("current_problem") or "").strip()
        better = (plan_data.get("better_approach") or "").strip()

        if not problem and not better:
            return _generate_fallback_narrative(move_san, plan_data, severity)

        # Construct the input plan as a plain sentence or two. The LLM's job
        # is to restate THIS, not to add to it.
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

        chat_instance = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"narrator-{uuid.uuid4().hex[:8]}",
            system_message=NARRATOR_SYSTEM_PROMPT
        )
        chat_instance.with_model("openai", "gpt-4.1-mini")

        response = await chat_instance.send_message(UserMessage(text=user_prompt))

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
    if not EMERGENT_LLM_KEY:
        return _fallback_opponent_narrative(move_san, eval_swing, weak_squares)
    
    try:
        from llm_helper import LlmChat, UserMessage
        import uuid
        
        # Determine situation
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

        chat_instance = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"opp-narrator-{uuid.uuid4().hex[:8]}",
            system_message="You are a chess coach. Be concise and actionable. Max 15 words per line."
        )
        chat_instance.with_model("openai", "gpt-4.1-mini")
        
        response = await chat_instance.send_message(UserMessage(text=user_prompt))
        
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
    if not EMERGENT_LLM_KEY:
        return _fallback_good_move(move_san, concept_applied, is_best_move)
    
    try:
        from llm_helper import LlmChat, UserMessage
        import uuid
        
        context = f"Move: {move_san}\nPhase: {phase}\n"
        if is_best_move:
            context += "This was the BEST move in the position!\n"
        if concept_applied:
            context += f"User demonstrated understanding of: {concept_applied.replace('_', ' ')}"
        
        user_prompt = f"""{context}

Generate a SHORT (max 10 words) genuine praise that feels human, not robotic.
Don't say "great move" or "well done" - be more specific."""

        chat_instance = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"praise-{uuid.uuid4().hex[:8]}",
            system_message="You are a warm but honest chess coach. Be concise."
        )
        chat_instance.with_model("openai", "gpt-4.1-mini")
        
        response = await chat_instance.send_message(UserMessage(text=user_prompt))
        
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
    """
    problem = (plan_data.get("current_problem") or "").strip() if plan_data else ""
    better = (plan_data.get("better_approach") or "").strip() if plan_data else ""

    # If we have a concrete problem sentence, use it as-is. It was built
    # upstream from Stockfish's best_move — trusting that is safer than
    # prepending speculative hooks.
    if problem:
        # Keep it short. If the problem already names the move, we don't
        # need to prefix with move_san again.
        if move_san and move_san in problem:
            return problem
        return f"{move_san}: {problem}" if move_san else problem

    # No problem text — fall through to a severity-only acknowledgement.
    if better:
        return f"{move_san} — {better}" if move_san else better
    if severity == "blunder":
        return f"{move_san} was a blunder."
    if severity == "mistake":
        return f"{move_san} wasn't the best here."
    if severity == "inaccuracy":
        return f"{move_san} — a small inaccuracy."
    return f"{move_san}."


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


# Batch processing for efficiency
async def generate_narratives_batch(moves_data: List[Dict]) -> Dict[int, str]:
    """
    Generate narratives for multiple moves in a single batch.
    
    This is more efficient than calling the LLM for each move individually.
    Returns: Dict mapping move_index to narrative
    """
    if not EMERGENT_LLM_KEY:
        # Return fallback for all
        return {
            i: _generate_fallback_narrative(
                m.get("move_san", ""),
                m.get("plan"),
                m.get("severity", "good")
            )
            for i, m in enumerate(moves_data)
        }
    
    try:
        from llm_helper import LlmChat, UserMessage
        import uuid
        
        # Build batch prompt
        moves_context = []
        for i, m in enumerate(moves_data):
            plan = m.get("plan", {})
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

        chat_instance = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"batch-narrator-{uuid.uuid4().hex[:8]}",
            system_message=NARRATOR_SYSTEM_PROMPT + "\n\nReturn ONLY valid JSON."
        )
        chat_instance.with_model("openai", "gpt-4.1-mini")
        
        response = await chat_instance.send_message(UserMessage(text=user_prompt))
        
        # Parse JSON response
        try:
            narratives = json.loads(response.strip())
            return {int(k)-1: v for k, v in narratives.items()}
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
