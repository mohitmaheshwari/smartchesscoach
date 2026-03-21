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



def _diagnose_illegal_move(board: chess.Board, move_san: str) -> str:
    """
    Explain WHY a move is illegal in human-friendly terms.
    
    Common reasons:
    - Target square has your own piece
    - Piece can't reach that square (wrong movement pattern)
    - No piece of that type exists
    - Move would leave king in check
    """
    piece_names = {
        chess.KING: "King", chess.QUEEN: "Queen", chess.ROOK: "Rook",
        chess.BISHOP: "Bishop", chess.KNIGHT: "Knight", chess.PAWN: "Pawn"
    }
    
    # Parse the move components
    move_str = move_san.strip().replace("+", "").replace("#", "")
    # Determine piece type
    if move_str[0] in "KQRBN":
        piece_char = move_str[0]
        piece_type = {"K": chess.KING, "Q": chess.QUEEN, "R": chess.ROOK,
                      "B": chess.BISHOP, "N": chess.KNIGHT}[piece_char]
        rest = move_str[1:]
    else:
        piece_char = "P"
        piece_type = chess.PAWN
        rest = move_str
    
    piece_name = piece_names.get(piece_type, piece_char)
    
    # Try to extract target square
    rest_clean = rest.replace("x", "")
    target_sq_name = None
    if len(rest_clean) >= 2:
        candidate = rest_clean[-2:]
        if candidate[0] in "abcdefgh" and candidate[1] in "12345678":
            target_sq_name = candidate
    
    if not target_sq_name:
        return f"'{move_san}' is not a valid move notation."
    
    try:
        target_sq = chess.parse_square(target_sq_name)
    except ValueError:
        return f"'{move_san}' is not a valid move notation."
    
    player_color = board.turn
    target_piece = board.piece_at(target_sq)
    
    # Check: is your own piece on the target square?
    if target_piece and target_piece.color == player_color:
        own_piece_name = piece_names.get(target_piece.piece_type, "piece")
        return f"'{move_san}' is not legal — your own {own_piece_name.lower()} is on {target_sq_name}."
    
    # Check: does the player have this piece type?
    player_pieces_of_type = list(board.pieces(piece_type, player_color))
    if not player_pieces_of_type:
        return f"'{move_san}' is not legal — you don't have a {piece_name.lower()} on the board."
    
    # Check: can any piece of this type reach the target?
    can_reach = False
    for from_sq in player_pieces_of_type:
        test_move = chess.Move(from_sq, target_sq)
        # For promotions
        if piece_type == chess.PAWN and chess.square_rank(target_sq) in (0, 7):
            test_move = chess.Move(from_sq, target_sq, promotion=chess.QUEEN)
        if test_move in board.legal_moves:
            can_reach = True
            break
    
    if not can_reach:
        # More specific: is the square unreachable or would it leave king in check?
        if len(player_pieces_of_type) == 1:
            from_sq = player_pieces_of_type[0]
            # Check if the move would be pseudo-legal (ignoring check)
            test_move = chess.Move(from_sq, target_sq)
            if test_move in board.pseudo_legal_moves:
                return f"'{move_san}' is not legal — it would leave your king in check."
            else:
                return f"'{move_san}' is not legal — your {piece_name.lower()} on {chess.square_name(from_sq)} can't reach {target_sq_name}."
        else:
            # Multiple pieces of this type
            reasons = []
            for from_sq in player_pieces_of_type:
                sq_name = chess.square_name(from_sq)
                test_move = chess.Move(from_sq, target_sq)
                if test_move in board.pseudo_legal_moves:
                    reasons.append(f"{piece_name} on {sq_name} can't move there (would leave king in check)")
                else:
                    reasons.append(f"{piece_name} on {sq_name} can't reach {target_sq_name}")
            return f"'{move_san}' is not legal — " + "; ".join(reasons) + "."
    
    return f"'{move_san}' is not a legal move in this position."



async def analyze_move_with_stockfish(
    fen: str, 
    move_san: Optional[str], 
    depth: int = 18
) -> Optional[Dict[str, Any]]:
    """
    Analyze a specific move with Stockfish, or get the engine's best move.
    
    If move_san is None, analyzes the position directly (engine's best).
    Returns evaluation and best continuation.
    """
    try:
        board = chess.Board(fen)
        
        if move_san is not None:
            # Parse and play the user's move
            try:
                move = board.parse_san(move_san)
            except (ValueError, chess.IllegalMoveError, chess.AmbiguousMoveError) as e:
                logger.warning(f"Could not parse move {move_san}: {e}")
                return None
            
            if move not in board.legal_moves:
                return None
            
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
                    if pv_move not in temp_board.pseudo_legal_moves:
                        break
                    pv_san.append(temp_board.san(pv_move))
                    temp_board.push(pv_move)
                except Exception:
                    break
            
            return {
                "move": move_san,
                "eval_cp": cp,
                "mate_in": mate_in,
                "pv": pv_san,
                "fen_after": board.fen(),
                "best_move": pv_san[0] if pv_san and move_san is None else None,
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
    
    # Check if alternative move is legal — with detailed WHY explanation
    try:
        alt_move = board.parse_san(q_alternative)
        if alt_move not in board.legal_moves:
            return {
                "error": f"{q_alternative} is not a legal move in this position.",
                "legal_moves": [board.san(m) for m in list(board.legal_moves)[:10]]
            }
    except (ValueError, chess.IllegalMoveError, chess.AmbiguousMoveError):
        reason = _diagnose_illegal_move(board, q_alternative)
        
        # Get legal moves for that piece type
        piece_char = q_alternative[0].upper() if q_alternative[0].upper() in "KQRBN" else "P"
        piece_type_map = {"K": chess.KING, "Q": chess.QUEEN, "R": chess.ROOK, "B": chess.BISHOP, "N": chess.KNIGHT, "P": chess.PAWN}
        piece_type = piece_type_map.get(piece_char)
        
        legal_for_piece = []
        if piece_type:
            for move in board.legal_moves:
                piece = board.piece_at(move.from_square)
                if piece and piece.piece_type == piece_type:
                    legal_for_piece.append(board.san(move))
        
        error_msg = reason
        if legal_for_piece:
            error_msg += f" Legal {piece_char} moves: {', '.join(legal_for_piece[:8])}"
        
        return {
            "error": error_msg,
            "legal_moves": [board.san(m) for m in list(board.legal_moves)[:10]],
            "legal_piece_moves": legal_for_piece[:10] if legal_for_piece else None
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

    # Import coaching answer generator
    from services.coaching_answer import (
        generate_coaching_answer,
        detect_thinking_pattern,
        analyze_move_character,
    )

    # Generate comparison and answer
    if "played" in analyses and "alternative" in analyses:
        played_eval = analyses["played"]["eval_cp"]
        alt_eval = analyses["alternative"]["eval_cp"]

        diff = alt_eval - played_eval

        if abs(diff) < 30:
            comparison = "roughly equal"
        elif diff > 0:
            comparison = "worse"
        else:
            comparison = "better"

        # Coaching-quality answer
        answer = generate_coaching_answer(
            user_move=q_alternative,
            better_move=q_played,
            user_analysis=analyses["alternative"],
            better_analysis=analyses["played"],
            board=board,
            eval_diff=diff,
        )

        # Detect thinking pattern
        move_char = analyze_move_character(board, q_alternative)
        thinking = detect_thinking_pattern(
            board=board,
            user_move_san=q_alternative,
            better_move_san=q_played,
            move_char=move_char,
            eval_diff=diff,
        )

        return {
            "question": question,
            "answer": answer,
            "played_move": q_played,
            "alternative_move": q_alternative,
            "comparison": comparison,
            "eval_difference": diff,
            "thinking_pattern": thinking,
            "played_analysis": analyses.get("played"),
            "alternative_analysis": analyses.get("alternative"),
        }

    elif "alternative" in analyses:
        alt_eval = analyses["alternative"]["eval_cp"]

        # Try to get engine's best move for meaningful comparison
        real_diff = 0
        best_move_san = None
        best_analysis = None
        try:
            best_result = await analyze_move_with_stockfish(fen, None, depth)
            if best_result:
                best_eval = best_result.get("eval_cp", 0)
                real_diff = alt_eval - best_eval
                best_move_san = best_result.get("best_move")
                best_analysis = best_result
        except Exception as e:
            logger.warning(f"Could not get engine best for comparison: {e}")

        answer = generate_coaching_answer(
            user_move=q_alternative,
            better_move=best_move_san,
            user_analysis=analyses["alternative"],
            better_analysis=best_analysis,
            board=board,
            eval_diff=real_diff,
        )

        move_char = analyze_move_character(board, q_alternative)
        thinking = detect_thinking_pattern(
            board=board,
            user_move_san=q_alternative,
            better_move_san=best_move_san,
            move_char=move_char,
            eval_diff=real_diff,
        )

        return {
            "question": question,
            "answer": answer,
            "alternative_move": q_alternative,
            "thinking_pattern": thinking,
            "alternative_analysis": analyses.get("alternative"),
        }

    return {
        "error": "Could not analyze the moves.",
        "question": question,
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
