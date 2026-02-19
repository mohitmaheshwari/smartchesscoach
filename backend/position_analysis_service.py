"""
Chess Position Analysis Service

This module provides ACCURATE position analysis by:
1. Parsing FEN to understand piece placement
2. Using chess.js logic to determine what moves actually do
3. Using Stockfish for tactical insights
4. Providing verified facts to LLM prompts
5. Validating LLM output against position reality

CRITICAL: Never trust LLM to interpret chess positions directly.
Always provide it with pre-computed facts.
"""

import chess
import chess.engine
from typing import Dict, List, Optional, Tuple
import os
import logging
import asyncio

logger = logging.getLogger(__name__)

# Stockfish path
STOCKFISH_PATH = os.environ.get("STOCKFISH_PATH", "/usr/games/stockfish")


def parse_position(fen: str) -> Dict:
    """
    Parse a FEN string and extract all relevant position facts.
    Returns a dictionary of verifiable facts about the position.
    """
    try:
        board = chess.Board(fen)
    except Exception as e:
        logger.error(f"Invalid FEN: {fen}, error: {e}")
        return {"error": "Invalid FEN"}
    
    facts = {
        "fen": fen,
        "side_to_move": "White" if board.turn == chess.WHITE else "Black",
        "is_check": board.is_check(),
        "is_checkmate": board.is_checkmate(),
        "is_stalemate": board.is_stalemate(),
        "pieces": {},
        "white_pieces": [],
        "black_pieces": [],
        "attacked_squares": {},
        "hanging_pieces": [],
        "threats": [],
    }
    
    # Map pieces to squares
    piece_names = {
        chess.PAWN: "pawn",
        chess.KNIGHT: "knight", 
        chess.BISHOP: "bishop",
        chess.ROOK: "rook",
        chess.QUEEN: "queen",
        chess.KING: "king"
    }
    
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if piece:
            square_name = chess.square_name(square)
            color = "white" if piece.color == chess.WHITE else "black"
            piece_type = piece_names[piece.piece_type]
            
            facts["pieces"][square_name] = {
                "type": piece_type,
                "color": color,
                "symbol": piece.symbol()
            }
            
            if piece.color == chess.WHITE:
                facts["white_pieces"].append(f"{piece_type} on {square_name}")
            else:
                facts["black_pieces"].append(f"{piece_type} on {square_name}")
    
    # Find attacked squares for each side
    for color in [chess.WHITE, chess.BLACK]:
        color_name = "white" if color == chess.WHITE else "black"
        attacked = []
        for square in chess.SQUARES:
            if board.is_attacked_by(color, square):
                attacked.append(chess.square_name(square))
        facts["attacked_squares"][color_name] = attacked
    
    # Find hanging pieces (pieces that are attacked but not defended)
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if piece:
            square_name = chess.square_name(square)
            own_color = piece.color
            enemy_color = not own_color
            
            is_attacked = board.is_attacked_by(enemy_color, square)
            is_defended = board.is_attacked_by(own_color, square)
            
            if is_attacked and not is_defended:
                color = "white" if own_color == chess.WHITE else "black"
                facts["hanging_pieces"].append({
                    "piece": piece_names[piece.piece_type],
                    "square": square_name,
                    "color": color
                })
    
    return facts


def analyze_move(fen: str, move_san: str) -> Dict:
    """
    Analyze what a specific move does in the position.
    Returns MEANINGFUL facts - not just raw data.
    
    CRITICAL: Only include facts that are SIGNIFICANT:
    - Attacks on UNDEFENDED pieces (hanging)
    - Attacks that create WINNING tactics (forks, pins)
    - Defenses of pieces that NEEDED defending
    - Checkmate threats
    """
    try:
        board = chess.Board(fen)
        move = board.parse_san(move_san)
    except Exception as e:
        logger.error(f"Error parsing move {move_san} in {fen}: {e}")
        return {"error": f"Could not parse move: {move_san}"}
    
    from_square = chess.square_name(move.from_square)
    to_square = chess.square_name(move.to_square)
    
    moving_piece = board.piece_at(move.from_square)
    captured_piece = board.piece_at(move.to_square)
    
    piece_names = {
        chess.PAWN: "pawn",
        chess.KNIGHT: "knight",
        chess.BISHOP: "bishop", 
        chess.ROOK: "rook",
        chess.QUEEN: "queen",
        chess.KING: "king"
    }
    
    piece_values = {
        chess.PAWN: 1,
        chess.KNIGHT: 3,
        chess.BISHOP: 3,
        chess.ROOK: 5,
        chess.QUEEN: 9,
        chess.KING: 100
    }
    
    analysis = {
        "move": move_san,
        "from_square": from_square,
        "to_square": to_square,
        "piece_moved": piece_names.get(moving_piece.piece_type, "piece") if moving_piece else "unknown",
        "is_capture": captured_piece is not None,
        "captured_piece": piece_names.get(captured_piece.piece_type) if captured_piece else None,
        "capture_value": piece_values.get(captured_piece.piece_type, 0) if captured_piece else 0,
        "is_check": False,
        "is_checkmate": False,
        "attacks_after_move": [],  # Only MEANINGFUL attacks (hanging pieces, high value)
        "defends_after_move": [],  # Only pieces that NEEDED defending
        "creates_threat": None,  # Main tactical threat created
        "new_threats": [],
    }
    
    # Make the move and analyze the resulting position
    board.push(move)
    
    analysis["is_check"] = board.is_check()
    analysis["is_checkmate"] = board.is_checkmate()
    
    # Get the color that just moved
    moving_color = not board.turn  # After push, turn flipped
    opponent_color = board.turn
    
    # What does the piece attack after moving? (ONLY meaningful attacks)
    piece_after = board.piece_at(move.to_square)
    if piece_after:
        meaningful_attacks = []
        
        for target_square in chess.SQUARES:
            target_piece = board.piece_at(target_square)
            if target_piece and target_piece.color != piece_after.color:
                # Check if this attack is from the moved piece
                attackers = board.attackers(moving_color, target_square)
                if move.to_square in attackers:
                    target_name = chess.square_name(target_square)
                    target_type = piece_names.get(target_piece.piece_type, "piece")
                    target_value = piece_values.get(target_piece.piece_type, 0)
                    
                    # Check if target is UNDEFENDED (hanging)
                    defenders = board.attackers(opponent_color, target_square)
                    is_hanging = len(defenders) == 0
                    
                    # Only include MEANINGFUL attacks:
                    # 1. Attacks on hanging pieces (any value)
                    # 2. Attacks on high-value pieces (queen, rook)
                    
                    if is_hanging and target_value >= 1:
                        meaningful_attacks.append({
                            "square": target_name,
                            "piece": target_type,
                            "is_hanging": True,
                            "value": target_value
                        })
                    elif target_value >= 5:  # Always mention attacks on queen/rook
                        meaningful_attacks.append({
                            "square": target_name,
                            "piece": target_type,
                            "is_hanging": is_hanging,
                            "value": target_value
                        })
        
        # Sort by value (most valuable first) and limit
        meaningful_attacks.sort(key=lambda x: (-x["value"], -int(x["is_hanging"])))
        analysis["attacks_after_move"] = meaningful_attacks[:3]  # Top 3 most important
    
    # What does this piece now defend? (ONLY pieces that NEEDED defending)
    if piece_after:
        meaningful_defenses = []
        
        for friendly_square in chess.SQUARES:
            friendly_piece = board.piece_at(friendly_square)
            if friendly_piece and friendly_piece.color == moving_color and friendly_square != move.to_square:
                # Check if this piece is being attacked
                attackers = board.attackers(opponent_color, friendly_square)
                if attackers:
                    # Check if we're now defending it
                    defenders = board.attackers(moving_color, friendly_square)
                    if move.to_square in defenders:
                        friendly_name = chess.square_name(friendly_square)
                        friendly_type = piece_names.get(friendly_piece.piece_type, "piece")
                        
                        # Was it previously undefended (we saved it)?
                        # Remove our new piece from defenders to check
                        other_defenders = [d for d in defenders if d != move.to_square]
                        was_hanging = len(other_defenders) == 0
                        
                        meaningful_defenses.append({
                            "square": friendly_name,
                            "piece": friendly_type,
                            "was_hanging": was_hanging,
                            "value": piece_values.get(friendly_piece.piece_type, 0)
                        })
        
        # Only include pieces that were ACTUALLY under attack
        # Sort by value and limit
        meaningful_defenses.sort(key=lambda x: (-x["value"], -int(x["was_hanging"])))
        analysis["defends_after_move"] = meaningful_defenses[:2]  # Top 2
    
    # Check for main tactical threat created
    if analysis["is_checkmate"]:
        analysis["creates_threat"] = "checkmate"
    elif analysis["is_check"]:
        analysis["creates_threat"] = "check"
    elif analysis["attacks_after_move"]:
        best_attack = analysis["attacks_after_move"][0]
        if best_attack["is_hanging"]:
            analysis["creates_threat"] = f"wins {best_attack['piece']} on {best_attack['square']}"
    
    board.pop()  # Undo move
    
    return analysis


def compare_moves(fen: str, user_move: str, best_move: str) -> Dict:
    """
    Compare the user's move with the best move.
    Returns factual differences between the two moves.
    """
    user_analysis = analyze_move(fen, user_move)
    best_analysis = analyze_move(fen, best_move)
    
    comparison = {
        "user_move": user_analysis,
        "best_move": best_analysis,
        "differences": []
    }
    
    # Compare captures
    if best_analysis.get("is_capture") and not user_analysis.get("is_capture"):
        comparison["differences"].append(
            f"The better move {best_move} captures the {best_analysis['captured_piece']}, while {user_move} doesn't capture anything"
        )
    
    # Compare attacks
    user_attacks = set(a["piece"] for a in user_analysis.get("attacks_after_move", []))
    best_attacks = set(a["piece"] for a in best_analysis.get("attacks_after_move", []))
    
    missed_attacks = best_attacks - user_attacks
    if missed_attacks:
        comparison["differences"].append(
            f"{best_move} attacks {', '.join(missed_attacks)} that {user_move} doesn't"
        )
    
    # Compare checks
    if best_analysis.get("is_check") and not user_analysis.get("is_check"):
        comparison["differences"].append(f"{best_move} gives check, while {user_move} doesn't")
    
    return comparison


async def get_stockfish_analysis(fen: str, depth: int = 15) -> Dict:
    """
    Get Stockfish analysis for the position.
    Returns evaluation and best moves with explanations.
    """
    try:
        transport, engine = await chess.engine.popen_uci(STOCKFISH_PATH)
        board = chess.Board(fen)
        
        # Get evaluation
        info = await engine.analyse(board, chess.engine.Limit(depth=depth))
        
        score = info.get("score")
        if score:
            if score.is_mate():
                eval_str = f"Mate in {score.relative.mate()}"
            else:
                cp = score.relative.score()
                eval_str = f"{cp/100:+.2f}" if cp else "0.00"
        else:
            eval_str = "0.00"
        
        # Get best move
        best_move = info.get("pv", [None])[0]
        best_move_san = board.san(best_move) if best_move else None
        
        await engine.quit()
        
        return {
            "evaluation": eval_str,
            "best_move": best_move_san,
            "depth": depth
        }
    except Exception as e:
        logger.error(f"Stockfish error: {e}")
        return {"error": str(e)}


def generate_verified_insight(
    fen: str,
    user_move: str,
    best_move: str,
    eval_change: float
) -> Dict:
    """
    Generate a verified insight about the position based on FACTS, not LLM hallucination.
    This creates a factual description that can be trusted.
    
    CRITICAL: Uses chess_verification_layer for consistent checkmate detection.
    """
    # Import the unified verification layer
    from chess_verification_layer import verify_move, get_critical_facts, safe_board, check_mate_in_1
    
    position = parse_position(fen)
    user_analysis = analyze_move(fen, user_move)
    best_analysis = analyze_move(fen, best_move)
    comparison = compare_moves(fen, user_move, best_move)
    
    # CRITICAL: Use the unified verification layer for checkmate detection
    critical_facts = get_critical_facts(fen, user_move, best_move, abs(int(eval_change * 100)))
    
    # Build factual insights
    insights = {
        "position_facts": position,
        "user_move_analysis": user_analysis,
        "best_move_analysis": best_analysis,
        "comparison": comparison,
        "verified_impact": "",
        "verified_better_plan": "",
        "critical_issue": critical_facts.get("primary_issue"),
        "thinking_habit": critical_facts.get("thinking_habit"),
    }
    
    # PRIORITY 0: If there's a checkmate issue, that's THE explanation
    primary_issue = critical_facts.get("primary_issue", "")
    if "mate" in primary_issue:
        insights["verified_impact"] = critical_facts.get("primary_detail", "")
        insights["verified_better_plan"] = critical_facts.get("thinking_habit", "")
        return insights
    
    # Generate verified impact statement
    impact_parts = []
    
    # What did the user move do?
    if user_analysis.get("is_capture"):
        impact_parts.append(f"Your move {user_move} captured the {user_analysis['captured_piece']}.")
    else:
        impact_parts.append(f"Your move {user_move} moved your {user_analysis['piece_moved']} to {user_analysis['to_square']}.")
    
    # What does the user move attack?
    if user_analysis.get("attacks_after_move"):
        attacks = [f"{a['piece']} on {a['square']}" for a in user_analysis["attacks_after_move"]]
        impact_parts.append(f"This attacks the {', '.join(attacks)}.")
    
    # What's the problem with this move?
    if eval_change < -1:
        impact_parts.append(f"However, this loses about {abs(eval_change):.1f} pawns worth of advantage.")
    elif eval_change < -0.5:
        impact_parts.append(f"This is slightly inaccurate, costing about {abs(eval_change):.1f} pawns.")
    
    insights["verified_impact"] = " ".join(impact_parts)
    
    # Generate verified better plan
    better_parts = []
    
    if best_analysis.get("error"):
        # Move couldn't be parsed - provide limited insight
        better_parts.append(f"The engine suggests {best_move} as a better alternative.")
    elif best_analysis.get("is_capture"):
        better_parts.append(f"{best_move} would have captured the {best_analysis['captured_piece']}.")
    else:
        better_parts.append(f"{best_move} moves the {best_analysis.get('piece_moved', 'piece')} to {best_analysis.get('to_square', 'a new square')}.")
    
    if best_analysis.get("attacks_after_move"):
        attacks = [f"{a['piece']} on {a['square']}" for a in best_analysis["attacks_after_move"]]
        better_parts.append(f"This would attack the {', '.join(attacks)}.")
    
    if best_analysis.get("is_check"):
        better_parts.append("This also gives check!")
    
    # Add comparison differences
    for diff in comparison.get("differences", []):
        better_parts.append(diff + ".")
    
    insights["verified_better_plan"] = " ".join(better_parts)
    
    return insights


def build_llm_prompt_with_facts(
    fen: str,
    user_move: str, 
    best_move: str,
    eval_change: float
) -> str:
    """
    Build an LLM prompt that includes verified position facts.
    The LLM should ONLY elaborate on these facts, not make up new ones.
    """
    insights = generate_verified_insight(fen, user_move, best_move, eval_change)
    
    user_analysis = insights["user_move_analysis"]
    best_analysis = insights["best_move_analysis"]
    position = insights["position_facts"]
    
    # Build piece list for context
    white_pieces = ", ".join(position.get("white_pieces", [])[:10])
    black_pieces = ", ".join(position.get("black_pieces", [])[:10])
    
    prompt = f"""You are a chess coach explaining a position to a student. 

CRITICAL: Only use the VERIFIED FACTS below. Do NOT make up piece locations or moves.

=== VERIFIED POSITION FACTS ===
Side to move: {position.get('side_to_move')}
White pieces: {white_pieces}
Black pieces: {black_pieces}

=== WHAT THE STUDENT'S MOVE ({user_move}) ACTUALLY DOES ===
- Moves: {user_analysis.get('piece_moved')} from {user_analysis.get('from_square')} to {user_analysis.get('to_square')}
- Captures: {user_analysis.get('captured_piece') or 'nothing'}
- After this move, it attacks: {[f"{a['piece']} on {a['square']}" for a in user_analysis.get('attacks_after_move', [])] or 'nothing significant'}
- Gives check: {user_analysis.get('is_check')}

=== WHAT THE BETTER MOVE ({best_move}) DOES ===
- Moves: {best_analysis.get('piece_moved')} from {best_analysis.get('from_square')} to {best_analysis.get('to_square')}
- Captures: {best_analysis.get('captured_piece') or 'nothing'}
- After this move, it attacks: {[f"{a['piece']} on {a['square']}" for a in best_analysis.get('attacks_after_move', [])] or 'nothing significant'}
- Gives check: {best_analysis.get('is_check')}

=== EVALUATION CHANGE ===
The student's move cost approximately {abs(eval_change):.1f} pawns of advantage.

Based ONLY on these verified facts, write a friendly 2-sentence explanation for:
1. "impact": What happened because of the student's move (use the actual facts above)
2. "better_plan": What the better move achieves (use the actual facts above)

Respond in JSON format:
{{"impact": "...", "better_plan": "..."}}

Remember: ONLY mention pieces and squares that are in the verified facts above. Do not hallucinate."""

    return prompt


def validate_llm_output(llm_output: str, position_facts: Dict) -> Tuple[bool, List[str]]:
    """
    Validate LLM output against position facts.
    Returns (is_valid, list_of_errors).
    """
    errors = []
    
    # Extract piece mentions from LLM output
    piece_patterns = ["knight", "bishop", "rook", "queen", "king", "pawn"]
    square_pattern = r'[a-h][1-8]'
    
    import re
    
    # Find all square references in the output
    mentioned_squares = re.findall(square_pattern, llm_output.lower())
    
    # Check if mentioned squares have pieces (if claimed)
    pieces = position_facts.get("pieces", {})
    
    for square in mentioned_squares:
        # This is a basic check - we could make it more sophisticated
        if square not in pieces:
            # Check if the output claims there's a piece there
            for piece_type in piece_patterns:
                if f"{piece_type} on {square}" in llm_output.lower():
                    errors.append(f"LLM incorrectly mentioned {piece_type} on {square} - no piece there")
    
    return len(errors) == 0, errors
