"""
Move Question Service

Allows users to ask questions like "why Na5 and not Nf5?" 
and get Stockfish-based explanations.

Flow:
1. Parse the question to extract the alternative move
2. Get Stockfish evaluation of both moves
3. Compare and explain the difference
"""

import chess
import chess.engine
import asyncio
from typing import Dict, Any, List, Optional, Tuple
import logging
import os
import re

logger = logging.getLogger(__name__)

# Stockfish path
STOCKFISH_PATH = os.environ.get("STOCKFISH_PATH", "/usr/games/stockfish")


def parse_move_question(question: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Parse a question like "why Na5 and not Nf5?" to extract moves.
    
    Returns: (played_move, alternative_move)
    """
    # Keep original case for moves
    q = question.strip()
    
    # SAN move pattern - handles Nf3, Be7, exd5, O-O, Qxh7+, etc.
    move_pattern = r'([KQRBN]?[a-h]?[1-8]?x?[a-h][1-8](?:=[QRBN])?[+#]*|O-O-O|O-O|0-0-0|0-0)'
    
    # Pattern 1: "why X and not Y"
    match = re.search(rf'why\s+{move_pattern}\s+(?:and\s+)?not\s+{move_pattern}', q, re.IGNORECASE)
    if match:
        return match.group(1), match.group(2)
    
    # Pattern 2: "why not Y instead of X"
    match = re.search(rf'why\s+not\s+{move_pattern}\s+instead\s+of\s+{move_pattern}', q, re.IGNORECASE)
    if match:
        return match.group(2), match.group(1)
    
    # Pattern 3: "what about Y" or "why not Y"
    match = re.search(rf'(?:what\s+about|why\s+not)\s+{move_pattern}', q, re.IGNORECASE)
    if match:
        return None, match.group(1)
    
    # Pattern 4: Just a move "Nf5?" or "Be7"
    match = re.search(rf'^{move_pattern}\s*\??$', q, re.IGNORECASE)
    if match:
        return None, match.group(1)
    
    return None, None


async def analyze_move_with_stockfish(
    fen: str, 
    move_san: str, 
    depth: int = 18
) -> Optional[Dict[str, Any]]:
    """
    Analyze a specific move with Stockfish.
    
    Returns evaluation and best continuation.
    """
    try:
        board = chess.Board(fen)
        
        # Parse the move
        try:
            move = board.parse_san(move_san)
        except (ValueError, chess.IllegalMoveError, chess.AmbiguousMoveError) as e:
            logger.warning(f"Could not parse move {move_san}: {e}")
            return None
        
        if move not in board.legal_moves:
            return None
        
        # Make the move
        board.push(move)
        
        # Run Stockfish
        transport, engine = await chess.engine.popen_uci(STOCKFISH_PATH)
        
        try:
            # Get evaluation and best line
            info = await engine.analyse(board, chess.engine.Limit(depth=depth))
            
            score = info.get("score")
            pv = info.get("pv", [])
            
            # Convert score to centipawns
            if score:
                if score.is_mate():
                    cp = 10000 if score.relative.mate() > 0 else -10000
                    mate_in = score.relative.mate()
                else:
                    cp = score.relative.score()
                    mate_in = None
            else:
                cp = 0
                mate_in = None
            
            # Convert PV to SAN
            pv_san = []
            temp_board = board.copy()
            for pv_move in pv[:6]:
                try:
                    pv_san.append(temp_board.san(pv_move))
                    temp_board.push(pv_move)
                except Exception:
                    break
            
            return {
                "move": move_san,
                "eval_cp": cp,
                "mate_in": mate_in,
                "pv": pv_san,
                "fen_after": board.fen()
            }
            
        finally:
            await engine.quit()
            
    except Exception as e:
        logger.error(f"Stockfish analysis error: {e}")
        return None


async def answer_move_question(
    fen: str,
    question: str,
    played_move: Optional[str] = None,
    depth: int = 18
) -> Dict[str, Any]:
    """
    Answer a question like "why Na5 and not Nf5?"
    
    Args:
        fen: Position before the move
        question: User's question
        played_move: The move that was played (optional, can be extracted from question)
        depth: Stockfish analysis depth
    
    Returns:
        {
            "answer": "Explanation of why...",
            "played_analysis": {...},
            "alternative_analysis": {...},
            "comparison": {...}
        }
    """
    # Parse the question
    q_played, q_alternative = parse_move_question(question)
    
    # Use provided played_move if question didn't have it
    if not q_played and played_move:
        q_played = played_move
    
    if not q_alternative:
        return {
            "error": "Could not understand the question. Try: 'Why Na5 and not Nf5?' or 'What about Nf5?'",
            "parsed_played": q_played,
            "parsed_alternative": None
        }
    
    # Validate moves on the board
    board = chess.Board(fen)
    
    # Check if alternative move is legal
    try:
        alt_move = board.parse_san(q_alternative)
        if alt_move not in board.legal_moves:
            return {
                "error": f"{q_alternative} is not a legal move in this position.",
                "legal_moves": [board.san(m) for m in list(board.legal_moves)[:10]]
            }
    except (ValueError, chess.IllegalMoveError, chess.AmbiguousMoveError):
        return {
            "error": f"Could not understand the move '{q_alternative}'.",
            "legal_moves": [board.san(m) for m in list(board.legal_moves)[:10]]
        }
    
    # Analyze both moves
    analyses = {}
    
    if q_played:
        played_analysis = await analyze_move_with_stockfish(fen, q_played, depth)
        if played_analysis:
            analyses["played"] = played_analysis
    
    alt_analysis = await analyze_move_with_stockfish(fen, q_alternative, depth)
    if alt_analysis:
        analyses["alternative"] = alt_analysis
    
    # Generate comparison and answer
    if "played" in analyses and "alternative" in analyses:
        played_eval = analyses["played"]["eval_cp"]
        alt_eval = analyses["alternative"]["eval_cp"]
        
        # Note: Evals are from opponent's perspective after the move
        # So more negative = better for the player who moved
        diff = alt_eval - played_eval
        
        if abs(diff) < 30:
            comparison = "roughly equal"
            verdict = f"Both {q_played} and {q_alternative} are about equally good here."
        elif diff > 0:
            # Alternative is worse (higher eval for opponent)
            comparison = "worse"
            pawns_diff = abs(diff) / 100
            verdict = f"{q_alternative} is about {pawns_diff:.1f} pawns worse than {q_played}."
        else:
            # Alternative is better (lower eval for opponent)
            comparison = "better"
            pawns_diff = abs(diff) / 100
            verdict = f"Actually, {q_alternative} might be slightly better! It's about {pawns_diff:.1f} pawns better than {q_played}."
        
        # Build detailed answer
        answer_parts = [verdict]
        
        # Explain why played move is good
        if q_played and "played" in analyses:
            pv_played = analyses["played"]["pv"]
            if pv_played:
                answer_parts.append(f"After {q_played}, the line continues: {' '.join(pv_played[:4])}.")
        
        # Explain what's wrong with alternative
        if comparison == "worse":
            pv_alt = analyses["alternative"]["pv"]
            if pv_alt:
                answer_parts.append(f"After {q_alternative}, your opponent can play {pv_alt[0]}, leading to: {' '.join(pv_alt[:4])}.")
                
                # Try to explain WHY it's worse
                if alt_analysis.get("mate_in"):
                    answer_parts.append(f"This leads to checkmate in {abs(alt_analysis['mate_in'])} moves!")
                elif abs(diff) >= 300:
                    answer_parts.append("This loses material.")
                elif abs(diff) >= 100:
                    answer_parts.append("This gives your opponent a significant advantage.")
        
        return {
            "question": question,
            "answer": " ".join(answer_parts),
            "played_move": q_played,
            "alternative_move": q_alternative,
            "comparison": comparison,
            "eval_difference": diff,
            "played_analysis": analyses.get("played"),
            "alternative_analysis": analyses.get("alternative")
        }
    
    elif "alternative" in analyses:
        # Only have alternative analysis
        alt_eval = analyses["alternative"]["eval_cp"]
        pv_alt = analyses["alternative"]["pv"]
        
        answer = f"After {q_alternative}, the evaluation is {alt_eval/100:.1f}."
        if pv_alt:
            answer += f" The line continues: {' '.join(pv_alt[:4])}."
        
        return {
            "question": question,
            "answer": answer,
            "alternative_move": q_alternative,
            "alternative_analysis": analyses.get("alternative")
        }
    
    return {
        "error": "Could not analyze the moves.",
        "question": question
    }


# Synchronous wrapper
def answer_move_question_sync(
    fen: str,
    question: str,
    played_move: Optional[str] = None,
    depth: int = 18
) -> Dict[str, Any]:
    """Synchronous wrapper for answer_move_question."""
    return asyncio.run(answer_move_question(fen, question, played_move, depth))
