"""
LLM Chess Explainer Service

Generates human-readable explanations for chess mistakes using LLM.
The LLM receives COMPLETE chess context to prevent hallucination:
- FEN position
- Actual moves (played and best)
- Engine evaluation numbers
- PV lines from Stockfish
- Opening detection from moves
- Move number and game phase

The LLM's job is ONLY to explain the provided facts - NOT to analyze chess.
"""

import os
import logging
import chess
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


# Common opening positions and their names (for when API fails)
KNOWN_OPENINGS = {
    # Italian Game positions
    "r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R": "Italian Game (C50)",
    "r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQ1RK1": "Italian Game (C50)",
    "r1bqk2r/pppp1ppp/2n2n2/2b1p3/2B1P3/5N2/PPPP1PPP/RNBQK2R": "Italian Game: Giuoco Piano (C53)",
    # Ruy Lopez
    "r1bqkbnr/pppp1ppp/2n5/1B2p3/4P3/5N2/PPPP1PPP/RNBQK2R": "Ruy Lopez (C60)",
    "r1bqkb1r/pppp1ppp/2n2n2/1B2p3/4P3/5N2/PPPP1PPP/RNBQK2R": "Ruy Lopez: Berlin Defense (C65)",
    # Sicilian
    "rnbqkbnr/pp1ppppp/8/2p5/4P3/8/PPPP1PPP/RNBQKBNR": "Sicilian Defense (B20)",
    "rnbqkbnr/pp1ppppp/8/2p5/4P3/5N2/PPPP1PPP/RNBQKB1R": "Sicilian Defense (B27)",
    # French
    "rnbqkbnr/pppp1ppp/4p3/8/4P3/8/PPPP1PPP/RNBQKBNR": "French Defense (C00)",
    # Caro-Kann
    "rnbqkbnr/pp1ppppp/2p5/8/4P3/8/PPPP1PPP/RNBQKBNR": "Caro-Kann Defense (B10)",
    # Queen's Gambit
    "rnbqkbnr/ppp1pppp/8/3p4/2PP4/8/PP2PPPP/RNBQKBNR": "Queen's Gambit (D06)",
    # London System
    "rnbqkb1r/ppp1pppp/5n2/3p4/3P1B2/5N2/PPP1PPPP/RN1QKB1R": "London System (D00)",
}

# Opening-specific theory and rules
OPENING_THEORY = {
    "Italian Game": {
        "d5_mistake": "In the Italian Game, playing d5 prematurely allows exd5, after which Black loses central control. The main line is d6, solidifying the center and preparing Bg4 or Be6.",
        "rule": "In the Italian Game, play d6 to support your center - don't rush d5."
    },
    "Ruy Lopez": {
        "a6_purpose": "In the Ruy Lopez, a6 is played to ask the bishop 'what are your intentions?' - forcing Ba4 or Bxc6.",
        "rule": "In the Ruy Lopez, a6 (Morphy Defense) is the main line - it challenges the bishop."
    },
    "Sicilian": {
        "d6_vs_d5": "In the Sicilian, Black typically plays d6 first, keeping the c5-pawn as a central outpost. d5 is often premature.",
        "rule": "In the Sicilian, control the center with pieces before pushing d5."
    },
    "French Defense": {
        "e5_chain": "In the French, Black's plan is to attack White's d4-e5 pawn chain with c5 and f6.",
        "rule": "In the French, attack the base of the pawn chain with c5."
    },
    "Caro-Kann": {
        "c6_support": "In the Caro-Kann, c6 supports a future d5 push, giving Black a solid center.",
        "rule": "In the Caro-Kann, c6 prepares d5 - this is the whole point of the opening."
    }
}


def detect_opening_from_fen(fen: str) -> Optional[str]:
    """
    Detect opening from FEN using local database.
    Returns opening name or None.
    """
    # Extract just the piece positions (first part of FEN)
    board_fen = fen.split()[0] if " " in fen else fen
    
    for known_fen, opening_name in KNOWN_OPENINGS.items():
        known_board = known_fen.split()[0] if " " in known_fen else known_fen
        if board_fen == known_board:
            return opening_name
    
    return None


def get_opening_theory_hint(opening_name: str, played_move: str, best_move: str) -> Optional[str]:
    """
    Get opening-specific theory if available.
    """
    if not opening_name:
        return None
    
    # Check for known theory hints
    for opening_key, theory in OPENING_THEORY.items():
        if opening_key.lower() in opening_name.lower():
            # Check if this is a d5 vs d6 situation
            if "d5" in played_move.lower() and "d6" in best_move.lower():
                if "d5_mistake" in theory:
                    return theory["d5_mistake"]
            return None
    
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
    opening_name = detect_opening_from_fen(fen_before)
    game_phase = get_game_phase(fen_before)
    eval_loss = abs(eval_after - eval_before)
    
    # Get opening theory hint if available
    theory_hint = get_opening_theory_hint(opening_name, played_move, best_move)
    
    # Determine whose perspective
    board = chess.Board(fen_before)
    side_to_move = "White" if board.turn == chess.WHITE else "Black"
    
    # Build theory context for LLM
    theory_context = ""
    if opening_name and theory_hint:
        theory_context = f"""
=== KNOWN OPENING THEORY ===
This is the {opening_name}.
VERIFIED THEORY: {theory_hint}
Use this theory in your explanation - it's from established opening books.
=== END THEORY ===
"""
    elif opening_name:
        theory_context = f"""
=== OPENING CONTEXT ===
This appears to be the {opening_name}.
If you know specific, DOCUMENTED theory about this position, mention it.
If you're not 100% sure of the theory, don't make it up - just explain tactically.
=== END OPENING CONTEXT ===
"""
    
    # Format the context for LLM
    context = f"""
CHESS POSITION ANALYSIS - EXPLAIN THIS TO THE PLAYER

You are explaining a chess mistake to a {user_color} player rated around 1200-1600.

{theory_context}

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
Based on the facts above, explain WHY {played_move} is worse than {best_move}.

GUIDELINES:
1. If VERIFIED THEORY is provided above, USE IT - start your explanation with the opening theory.
2. If opening context is provided but no verified theory, you MAY mention theory ONLY if you are 100% certain it's documented in standard opening books.
3. Be SPECIFIC - name the pieces, squares, and tactical threats.
4. Reference the PV lines to show the concrete consequence.
5. DO NOT invent theory. If unsure, explain purely tactically.

RESPOND IN THIS EXACT JSON FORMAT:
{{
    "headline": "Short 3-6 word title (specific, e.g., 'You gave up the center', 'Knight trapped on a5')",
    "explanation": "2-4 sentences. If there's opening theory, start with: 'In the [Opening], [theory].' Then explain the tactical consequence.",
    "rule": "One memorable rule. For openings, state the opening-specific principle if known.",
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
