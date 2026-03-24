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

# System prompt for concise narrative generation
NARRATOR_SYSTEM_PROMPT = """You are a FUN, MEMORABLE chess coach. Your students NEVER forget what you teach because you make it STICK.

YOUR STYLE:
- Talk like a friendly human, NOT a textbook
- Use SIMPLE words a 12-year-old understands
- Give pieces PERSONALITY:
  • Knights are "Naughty Knights" when they wander without a plan
  • Bishops are "Slicey Bois" - they love open diagonals
  • Rooks are "Tower Power" - they need open files
  • The Queen is "Your Majesty" - powerful but needs protection
  • Pawns are "Little Soldiers" - slow but they control space
- Create HOOKS that stick in memory:
  • "Knights on the rim are dim!" (bad knight placement)
  • "Castle early, sleep safely!" (king safety)
  • "Develop before you attack!" (opening principles)
  • "Loose pieces drop off!" (hanging pieces)

RULES:
1. MAX 15 words
2. Sound like a FRIEND teaching chess, not a computer
3. Use ONE memorable phrase or hook per move
4. Make it FUN - they should SMILE and learn
5. If there's a tactic, give it a fun name

EXAMPLE OUTPUTS:
- "Naughty Knight wandered off! Now Nb5 forks your pawn. Knights need a job!"
- "Tower Power! Rook on the open file = trouble for them."
- "Castle early, sleep safely! Your king thanks you."
- "Oops! Loose piece = free piece. Always check who's undefended."

Return ONLY the coaching text. No quotes, no JSON."""


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
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        import uuid
        
        # Build context for LLM
        context_parts = []
        
        if plan_data:
            if plan_data.get("current_problem"):
                context_parts.append(f"Problem: {plan_data['current_problem']}")
            if plan_data.get("consequence"):
                context_parts.append(f"What happens: {plan_data['consequence']}")
            if plan_data.get("better_approach"):
                context_parts.append(f"Better: {plan_data['better_approach']}")
            if plan_data.get("transferable_learning"):
                context_parts.append(f"Learning: {plan_data['transferable_learning']}")
        
        user_prompt = f"""Move: {move_san}
Phase: {phase}
Severity: {severity}
{'User move' if is_user_move else 'Opponent move'}

Context:
{chr(10).join(context_parts)}

Generate a MEMORABLE coaching sentence (max 20 words) that captures the key insight."""

        chat_instance = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"narrator-{uuid.uuid4().hex[:8]}",
            system_message=NARRATOR_SYSTEM_PROMPT
        )
        chat_instance.with_model("openai", "gpt-4.1-mini")
        
        response = await chat_instance.send_message(UserMessage(text=user_prompt))
        
        narrative = response.strip().strip('"').strip("'")
        
        # Ensure under 20 words
        words = narrative.split()
        if len(words) > 25:  # Allow some buffer
            narrative = " ".join(words[:20]) + "..."
        
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
        from emergentintegrations.llm.chat import LlmChat, UserMessage
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
        from emergentintegrations.llm.chat import LlmChat, UserMessage
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
    """Fallback when LLM is unavailable - still make it FUN and MEMORABLE."""
    if not plan_data:
        if severity == "blunder":
            return f"Ouch! {move_san} hurts. Big oops here!"
        elif severity == "mistake":
            return f"Hmm, {move_san} isn't great. Let's see why..."
        elif severity == "inaccuracy":
            return f"{move_san} - not bad, but there's a sneakier move!"
        return f"{move_san}."
    
    # Use the plan data to create a fun narrative
    problem = plan_data.get("current_problem", "")
    
    # Make it memorable based on what went wrong
    if "knight" in problem.lower():
        return f"Naughty Knight alert! {problem[:50]}"
    elif "bishop" in problem.lower():
        return f"Slicey Boi wants freedom! {problem[:50]}"
    elif "pawn" in problem.lower():
        return f"Little Soldier needs backup! {problem[:50]}"
    elif "king" in problem.lower():
        return f"King safety first! {problem[:50]}"
    else:
        return f"{move_san} - {problem[:60]}" if problem else f"{move_san} needs a rethink."


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
        from emergentintegrations.llm.chat import LlmChat, UserMessage
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
