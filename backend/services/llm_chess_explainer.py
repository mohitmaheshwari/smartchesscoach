"""
LLM Chess Explainer Service

Generates human-readable explanations for chess mistakes using LLM.
The LLM receives COMPLETE chess context to prevent hallucination:
- FEN position
- Actual moves (played and best)
- Engine evaluation numbers
- PV lines from Stockfish
- Opening name (from lichess API)
- Move number and game phase

The LLM's job is ONLY to explain the provided facts - NOT to analyze chess.
"""

import os
import logging
import httpx
import chess
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Lichess opening API for opening detection
LICHESS_OPENING_API = "https://explorer.lichess.ovh/masters"


async def get_opening_name(fen: str) -> Optional[str]:
    """
    Get the opening name from Lichess opening explorer.
    Returns None if position is not in the opening book.
    """
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                LICHESS_OPENING_API,
                params={"fen": fen}
            )
            if response.status_code == 200:
                data = response.json()
                opening = data.get("opening")
                if opening:
                    return f"{opening.get('eco', '')} {opening.get('name', '')}".strip()
    except Exception as e:
        logger.warning(f"Could not fetch opening name: {e}")
    return None


def get_game_phase(fen: str) -> str:
    """Determine game phase from position."""
    board = chess.Board(fen)
    
    # Count material
    queens = len(board.pieces(chess.QUEEN, chess.WHITE)) + len(board.pieces(chess.QUEEN, chess.BLACK))
    rooks = len(board.pieces(chess.ROOK, chess.WHITE)) + len(board.pieces(chess.ROOK, chess.BLACK))
    minors = (len(board.pieces(chess.BISHOP, chess.WHITE)) + len(board.pieces(chess.BISHOP, chess.BLACK)) +
              len(board.pieces(chess.KNIGHT, chess.WHITE)) + len(board.pieces(chess.KNIGHT, chess.BLACK)))
    
    total_pieces = queens * 9 + rooks * 5 + minors * 3
    
    if total_pieces >= 28:
        return "opening"
    elif total_pieces >= 14:
        return "middlegame"
    else:
        return "endgame"


def format_pv_line(moves: List[str], max_moves: int = 6) -> str:
    """Format PV line for display."""
    if not moves:
        return "N/A"
    return " ".join(moves[:max_moves]) + ("..." if len(moves) > max_moves else "")


async def explain_mistake_with_llm(
    fen_before: str,
    played_move: str,  # SAN notation
    played_move_uci: str,
    best_move: str,  # SAN notation
    best_move_uci: str,
    eval_before: int,  # centipawns
    eval_after: int,  # centipawns
    move_number: int,
    pv_after_played: List[str],
    pv_after_best: List[str],
    user_color: str = "white"
) -> Dict[str, Any]:
    """
    Generate a human-readable explanation using LLM with complete chess context.
    
    The LLM receives all the facts and ONLY explains them - no hallucination.
    """
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    
    api_key = os.environ.get("EMERGENT_LLM_KEY")
    if not api_key:
        logger.error("EMERGENT_LLM_KEY not found")
        return _fallback_explanation(played_move, best_move, eval_before, eval_after)
    
    # Gather all context
    opening_name = await get_opening_name(fen_before)
    game_phase = get_game_phase(fen_before)
    eval_loss = abs(eval_after - eval_before)
    
    # Determine whose perspective
    board = chess.Board(fen_before)
    side_to_move = "White" if board.turn == chess.WHITE else "Black"
    
    # Format the context for LLM
    context = f"""
CHESS POSITION ANALYSIS - EXPLAIN THIS TO THE PLAYER

You are explaining a chess mistake to a {user_color} player rated around 1200-1600.

=== VERIFIED FACTS (from Stockfish engine) ===
Position (FEN): {fen_before}
Move number: {move_number}
Game phase: {game_phase}
{f"Opening: {opening_name}" if opening_name else "Opening: Unknown/Out of book"}
Side to move: {side_to_move}

PLAYED MOVE: {played_move} (UCI: {played_move_uci})
BEST MOVE: {best_move} (UCI: {best_move_uci})

Evaluation before move: {eval_before / 100:.1f} (positive = white advantage)
Evaluation after {played_move}: {eval_after / 100:.1f}
CENTIPAWN LOSS: {eval_loss} (about {eval_loss / 100:.1f} pawns)

Line after {played_move}: {format_pv_line(pv_after_played)}
Line after {best_move}: {format_pv_line(pv_after_best)}
=== END FACTS ===

YOUR TASK:
Based ONLY on the facts above, explain WHY {played_move} is worse than {best_move}.

Focus on:
1. What specific problem does {played_move} create? (loses material, weakens structure, allows tactic, gives up control, etc.)
2. What does {best_move} achieve that {played_move} doesn't?
3. If this is an opening position, what opening principle was violated?

DO NOT:
- Invent moves or lines not shown above
- Claim things you can't verify from the position
- Use vague phrases like "weakens your position" without saying HOW

RESPOND IN THIS EXACT JSON FORMAT:
{{
    "headline": "Short 3-6 word title (e.g., 'You gave up the center', 'Your knight is now trapped')",
    "explanation": "2-3 sentences explaining the specific problem. Reference the actual moves and lines.",
    "rule": "One memorable rule the player should remember (e.g., 'Don't trade center pawns without compensation')",
    "category": "opening" or "tactical" or "positional" or "endgame"
}}
"""

    try:
        chat = LlmChat(
            api_key=api_key,
            session_id=f"chess-explain-{move_number}",
            system_message="You are a chess coach explaining mistakes. You ONLY use the facts provided - never invent analysis. Be specific and direct."
        ).with_model("openai", "gpt-4o-mini")  # Using mini for speed, still good enough
        
        user_message = UserMessage(text=context)
        response = await chat.send_message(user_message)
        
        # Parse the JSON response
        import json
        import re
        
        # Extract JSON from response (handle markdown code blocks)
        json_match = re.search(r'\{[\s\S]*\}', response)
        if json_match:
            result = json.loads(json_match.group())
            
            # Add arrows (best move in green)
            result["arrows"] = [
                [best_move_uci[:2], best_move_uci[2:4], "green"]
            ]
            
            return result
        else:
            logger.warning(f"Could not parse LLM response: {response}")
            return _fallback_explanation(played_move, best_move, eval_before, eval_after)
            
    except Exception as e:
        logger.error(f"LLM explanation failed: {e}")
        return _fallback_explanation(played_move, best_move, eval_before, eval_after)


def _fallback_explanation(
    played_move: str,
    best_move: str,
    eval_before: int,
    eval_after: int
) -> Dict[str, Any]:
    """Fallback when LLM fails."""
    eval_loss = abs(eval_after - eval_before)
    return {
        "headline": "A better move was available",
        "explanation": f"Playing {played_move} instead of {best_move} cost about {eval_loss / 100:.1f} pawns of advantage. Review the suggested line to understand the difference.",
        "rule": "Always check what your opponent can do after your move.",
        "arrows": [],
        "category": "tactical"
    }


# Synchronous wrapper for use in non-async contexts
def explain_mistake_sync(
    fen_before: str,
    played_move: str,
    played_move_uci: str,
    best_move: str,
    best_move_uci: str,
    eval_before: int,
    eval_after: int,
    move_number: int,
    pv_after_played: List[str],
    pv_after_best: List[str],
    user_color: str = "white"
) -> Dict[str, Any]:
    """Synchronous wrapper."""
    import asyncio
    return asyncio.run(explain_mistake_with_llm(
        fen_before, played_move, played_move_uci, best_move, best_move_uci,
        eval_before, eval_after, move_number, pv_after_played, pv_after_best, user_color
    ))
