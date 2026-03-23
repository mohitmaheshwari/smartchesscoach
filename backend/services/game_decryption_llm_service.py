"""
Game Decryption LLM Service
============================

LLM-powered coaching narratives for chess moves.
Uses GPT-4.1-mini for the best balance of reasoning, tone, accuracy, and cost.

Architecture:
- Called ONLY for mistakes + key moments (eval_loss > 30cp)
- Good moves stay rule-based (short praise)
- Opening moves use JSON knowledge base
- Single LLM call per game (batch all mistakes together)

Output format per move:
{
    "narrative": str,           # Flowing coach story (THE HOOK)
    "position_breakdown": {
        "your_intent": str,
        "opponent_counterplay": str,
        "hidden_problem": str
    },
    "mistake_analysis": {
        "type": "strategic|tactical|calculation|impatience",
        "why_it_fails": str,
        "severity": "inaccuracy|mistake|blunder"
    },
    "better_plan": {
        "move": str,
        "idea": str,
        "what_happens_next": str
    },
    "thinking_gap": str,        # THE MOAT
    "principle": str,           # Position-specific, NOT generic
    "confidence": "low|medium|high"
}
"""

import json
import os
import uuid
import logging
import asyncio
from typing import Dict, List, Optional
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY", "")

COACH_SYSTEM_PROMPT = """You are a strong chess coach (2000+ Elo).

Your job is NOT to explain moves.
Your job is to train how the user should THINK.

Rules:
1. Avoid generic advice (no "control center", "develop pieces" unless directly relevant to THIS position)
2. Always connect explanation to THIS exact position
3. Write like a human coach — not like an AI or textbook
4. Be slightly critical but constructive
5. Focus on why the move fails, not just what it does
6. Show opponent's idea clearly
7. When suggesting a better move, explain what happens next (1-2 moves ahead)
8. Identify the thinking mistake behind the move

Tone:
- Natural, conversational
- Slightly sharp ("This looks natural, but it fails because...")
- Insightful, not preachy
- No fluff, no filler

IMPORTANT: Return ONLY valid JSON. No markdown, no backticks, no explanation outside the JSON."""


def _build_moves_prompt(
    moves_to_analyze: List[Dict],
    game_context: Dict
) -> str:
    """Build the user prompt for the LLM with all move context."""
    opening_name = game_context.get("opening_name", "Unknown")
    user_color = game_context.get("user_color", "white")
    opening_context = game_context.get("opening_context", "")
    pgn_short = game_context.get("pgn_short", "")

    prompt = f"""Analyze the following chess moves from a game.

Game Info:
- Opening: {opening_name}
- Player: {user_color}
- Moves: {pgn_short}
{f"- Opening Context: {opening_context}" if opening_context else ""}

For each move below, return structured coaching JSON.

For MISTAKES/BLUNDERS (eval_loss > 100cp): Provide FULL analysis with all fields.
For INACCURACIES (eval_loss 30-100cp): Provide medium analysis — narrative, thinking_gap, better_plan.
For opponent moves included for context: Provide only a short narrative (1-2 sentences).

Moves to analyze:
"""

    for i, move_data in enumerate(moves_to_analyze):
        move_san = move_data["move_san"]
        is_user = move_data["is_user_move"]
        cp_loss = move_data.get("cp_loss", 0)
        best_move = move_data.get("best_move", "")
        eval_before = move_data.get("eval_before", 0)
        eval_after = move_data.get("eval_after", 0)
        phase = move_data.get("phase", "middlegame")
        move_number = move_data.get("move_number", 0)
        role = "USER" if is_user else "OPP"
        severity = move_data.get("severity", "")
        opening_hint = move_data.get("opening_hint", "")

        prompt += f"""
{i+1}. Move {move_number}. {move_san} [{role}, {severity.upper() if severity else 'CONTEXT'}]
   Phase: {phase}, Eval: {eval_before}→{eval_after}cp (loss:{cp_loss}cp), Best: {best_move}
{f"   Note: {opening_hint}" if opening_hint else ""}"""

    prompt += f"""
Return a JSON array with exactly {len(moves_to_analyze)} objects, one per move above, in order.

Each object MUST have these fields:
{{
  "move_san": "the move",
  "narrative": "flowing coach story — THIS is the most important field",
  "position_breakdown": {{
    "your_intent": "what the player was likely trying to do",
    "opponent_counterplay": "what the opponent gets from this",
    "hidden_problem": "the non-obvious issue with this move"
  }},
  "mistake_analysis": {{
    "type": "strategic|tactical|calculation|impatience",
    "why_it_fails": "concrete reason tied to this position",
    "severity": "inaccuracy|mistake|blunder"
  }},
  "better_plan": {{
    "move": "the better move",
    "idea": "why it's better",
    "what_happens_next": "1-2 moves of continuation"
  }},
  "thinking_gap": "the thinking mistake — what question they didn't ask",
  "principle": "position-specific takeaway — NOT generic",
  "confidence": "low|medium|high"
}}

For opponent/context moves or low-severity moves, set non-applicable fields to null.
Return ONLY the JSON array. No other text."""

    return prompt


async def _call_llm_async(prompt: str) -> str:
    """Call the LLM and return the raw response text."""
    from emergentintegrations.llm.chat import LlmChat, UserMessage

    chat = LlmChat(
        api_key=EMERGENT_LLM_KEY,
        session_id=f"decryption-{uuid.uuid4().hex[:8]}",
        system_message=COACH_SYSTEM_PROMPT
    )
    chat.with_model("openai", "gpt-4.1-mini")

    user_message = UserMessage(text=prompt)
    response = await chat.send_message(user_message)
    return response


def _parse_llm_response(response_text: str, expected_count: int) -> List[Dict]:
    """Parse the LLM JSON response, handling common issues."""
    text = response_text.strip()

    # Strip markdown code blocks if present
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [ln for ln in lines if not ln.strip().startswith("```")]
        text = "\n".join(lines)

    # Try direct parse
    try:
        result = json.loads(text)
        if isinstance(result, list):
            return result
        if isinstance(result, dict):
            return [result]
    except json.JSONDecodeError:
        pass

    # Try to find JSON array in the text
    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end != -1:
        try:
            result = json.loads(text[start:end + 1])
            if isinstance(result, list):
                return result
        except json.JSONDecodeError:
            pass

    logger.error(f"[LLM] Failed to parse response: {text[:200]}...")
    return []


async def generate_llm_coaching_async(
    moves_to_analyze: List[Dict],
    game_context: Dict
) -> List[Dict]:
    """
    Generate LLM-powered coaching for a batch of moves.
    Splits into chunks of MAX_BATCH to avoid timeouts.
    """
    if not moves_to_analyze:
        return []

    if not EMERGENT_LLM_KEY:
        logger.warning("[LLM] No EMERGENT_LLM_KEY found, skipping LLM coaching")
        return []

    MAX_BATCH = 6
    all_results = []

    # Split into chunks
    chunks = [moves_to_analyze[i:i + MAX_BATCH] for i in range(0, len(moves_to_analyze), MAX_BATCH)]

    for chunk_idx, chunk in enumerate(chunks):
        prompt = _build_moves_prompt(chunk, game_context)

        try:
            logger.info(f"[LLM] Batch {chunk_idx + 1}/{len(chunks)}: {len(chunk)} moves")
            response_text = await _call_llm_async(prompt)
            logger.info(f"[LLM] Batch {chunk_idx + 1} response ({len(response_text)} chars)")

            coaching_data = _parse_llm_response(response_text, len(chunk))

            if len(coaching_data) != len(chunk):
                logger.warning(f"[LLM] Expected {len(chunk)} results, got {len(coaching_data)}")

            all_results.extend(coaching_data)

        except Exception as e:
            logger.error(f"[LLM] Batch {chunk_idx + 1} error: {e}")
            # Pad with empty dicts so indices still align
            all_results.extend([{} for _ in chunk])

    return all_results


def generate_llm_coaching_sync(
    moves_to_analyze: List[Dict],
    game_context: Dict
) -> List[Dict]:
    """Synchronous wrapper for the async LLM coaching generation."""
    try:
        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(
            generate_llm_coaching_async(moves_to_analyze, game_context)
        )
        loop.close()
        return result
    except RuntimeError:
        # Already in an event loop (shouldn't happen in worker, but safety net)
        logger.warning("[LLM] Already in event loop, creating nested task")
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(
                asyncio.run,
                generate_llm_coaching_async(moves_to_analyze, game_context)
            )
            return future.result(timeout=120)
