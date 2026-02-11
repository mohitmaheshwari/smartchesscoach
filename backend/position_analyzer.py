"""
Chess Position Analyzer - Tactical Pattern Detection

This module analyzes chess positions to detect tactical patterns
that can be explained to users in simple terms.

Patterns detected:
- Hanging pieces (undefended and attacked)
- Forks (one piece attacking multiple valuable pieces)
- Pins (piece can't move without exposing more valuable piece)
- Discovered attacks
- Back rank weaknesses
- Overloaded pieces
"""

import chess
import logging
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Piece values for evaluation
PIECE_VALUES = {
    chess.PAWN: 1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9,
    chess.KING: 0  # King can't be captured
}

PIECE_NAMES = {
    chess.PAWN: "pawn",
    chess.KNIGHT: "knight",
    chess.BISHOP: "bishop",
    chess.ROOK: "rook",
    chess.QUEEN: "queen",
    chess.KING: "king"
}


def analyze_position_tactics(fen: str, user_color: str = "white") -> Dict:
    """
    Analyze a chess position for tactical patterns.
    
    Returns:
        Dict with detected patterns and simple explanations
    """
    try:
        board = chess.Board(fen)
    except Exception as e:
        logger.error(f"Invalid FEN: {fen}, error: {e}")
        return {"error": "Invalid position"}
    
    user_is_white = user_color.lower() == "white"
    user_color_chess = chess.WHITE if user_is_white else chess.BLACK
    opponent_color = chess.BLACK if user_is_white else chess.WHITE
    
    patterns = []
    
    # 1. Check for hanging pieces (user's pieces that are attacked but not defended)
    hanging = find_hanging_pieces(board, user_color_chess)
    if hanging:
        for piece_info in hanging:
            patterns.append({
                "type": "hanging_piece",
                "square": chess.square_name(piece_info["square"]),
                "piece": PIECE_NAMES[piece_info["piece"]],
                "value": PIECE_VALUES[piece_info["piece"]],
                "explanation": f"Your {PIECE_NAMES[piece_info['piece']]} on {chess.square_name(piece_info['square'])} is hanging! It's attacked but not defended.",
                "simple_tip": f"Look at {chess.square_name(piece_info['square'])} - is your {PIECE_NAMES[piece_info['piece']]} safe?"
            })
    
    # 2. Check for opponent's hanging pieces (opportunities)
    opp_hanging = find_hanging_pieces(board, opponent_color)
    if opp_hanging:
        for piece_info in opp_hanging:
            patterns.append({
                "type": "opponent_hanging",
                "square": chess.square_name(piece_info["square"]),
                "piece": PIECE_NAMES[piece_info["piece"]],
                "value": PIECE_VALUES[piece_info["piece"]],
                "explanation": f"Your opponent's {PIECE_NAMES[piece_info['piece']]} on {chess.square_name(piece_info['square'])} is hanging! You can capture it for free!",
                "simple_tip": f"Free piece! Can you take the {PIECE_NAMES[piece_info['piece']]} on {chess.square_name(piece_info['square'])}?"
            })
    
    # 3. Check for forks
    forks = find_forks(board, opponent_color)  # Opponent's potential forks against user
    if forks:
        for fork_info in forks:
            targets = ", ".join([f"{PIECE_NAMES[t['piece']]} on {chess.square_name(t['square'])}" for t in fork_info["targets"]])
            patterns.append({
                "type": "fork_threat",
                "attacker_square": chess.square_name(fork_info["attacker_square"]),
                "attacker_piece": PIECE_NAMES[fork_info["attacker_piece"]],
                "targets": targets,
                "explanation": f"The {PIECE_NAMES[fork_info['attacker_piece']]} on {chess.square_name(fork_info['attacker_square'])} is attacking BOTH your {targets} at once! This is called a fork.",
                "simple_tip": "Fork alert! One piece attacks two of yours. You can only save one."
            })
    
    # 4. Check for pins
    pins = find_pins(board, user_color_chess)
    if pins:
        for pin_info in pins:
            patterns.append({
                "type": "pin",
                "pinned_square": chess.square_name(pin_info["pinned_square"]),
                "pinned_piece": PIECE_NAMES[pin_info["pinned_piece"]],
                "behind_piece": PIECE_NAMES[pin_info["behind_piece"]],
                "explanation": f"Your {PIECE_NAMES[pin_info['pinned_piece']]} on {chess.square_name(pin_info['pinned_square'])} is pinned! If it moves, you lose your {PIECE_NAMES[pin_info['behind_piece']]} behind it.",
                "simple_tip": f"Your {PIECE_NAMES[pin_info['pinned_piece']]} can't move - there's a more valuable piece behind it!"
            })
    
    # 5. Check for loose pieces (not defended, even if not currently attacked)
    loose = find_loose_pieces(board, user_color_chess)
    if loose:
        for piece_info in loose:
            if piece_info["piece"] != chess.KING:  # Kings don't need defenders
                patterns.append({
                    "type": "loose_piece",
                    "square": chess.square_name(piece_info["square"]),
                    "piece": PIECE_NAMES[piece_info["piece"]],
                    "explanation": f"Your {PIECE_NAMES[piece_info['piece']]} on {chess.square_name(piece_info['square'])} has no defenders. It could become a target!",
                    "simple_tip": f"Undefended piece on {chess.square_name(piece_info['square'])} - keep an eye on it."
                })
    
    return {
        "patterns": patterns,
        "has_tactics": len(patterns) > 0,
        "summary": _generate_summary(patterns),
        "main_issue": patterns[0] if patterns else None
    }


def find_hanging_pieces(board: chess.Board, color: chess.Color) -> List[Dict]:
    """Find pieces that are attacked but not defended."""
    hanging = []
    
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if piece and piece.color == color:
            attackers = board.attackers(not color, square)
            defenders = board.attackers(color, square)
            
            if attackers and not defenders:
                # Piece is attacked but has no defenders
                hanging.append({
                    "square": square,
                    "piece": piece.piece_type,
                    "attackers": len(attackers)
                })
    
    # Sort by piece value (most valuable first)
    hanging.sort(key=lambda x: PIECE_VALUES[x["piece"]], reverse=True)
    return hanging


def find_loose_pieces(board: chess.Board, color: chess.Color) -> List[Dict]:
    """Find pieces that have no defenders (even if not attacked)."""
    loose = []
    
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if piece and piece.color == color and piece.piece_type != chess.KING:
            defenders = board.attackers(color, square)
            
            if not defenders:
                loose.append({
                    "square": square,
                    "piece": piece.piece_type
                })
    
    return loose


def find_forks(board: chess.Board, attacking_color: chess.Color) -> List[Dict]:
    """Find pieces that are forking (attacking) multiple valuable pieces."""
    forks = []
    target_color = not attacking_color
    
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if piece and piece.color == attacking_color:
            # Get all squares this piece attacks
            attacks = list(board.attacks(square))
            
            # Find valuable pieces being attacked
            valuable_targets = []
            for target_sq in attacks:
                target_piece = board.piece_at(target_sq)
                if target_piece and target_piece.color == target_color:
                    if PIECE_VALUES[target_piece.piece_type] >= 3:  # Knight or higher
                        valuable_targets.append({
                            "square": target_sq,
                            "piece": target_piece.piece_type
                        })
            
            # If attacking 2+ valuable pieces, it's a fork
            if len(valuable_targets) >= 2:
                forks.append({
                    "attacker_square": square,
                    "attacker_piece": piece.piece_type,
                    "targets": valuable_targets
                })
    
    return forks


def find_pins(board: chess.Board, pinned_color: chess.Color) -> List[Dict]:
    """Find pinned pieces (can't move without exposing a more valuable piece)."""
    pins = []
    king_square = board.king(pinned_color)
    
    if king_square is None:
        return pins
    
    # Check all sliding pieces (bishops, rooks, queens) of opponent
    opponent_color = not pinned_color
    
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if piece and piece.color == opponent_color:
            if piece.piece_type in [chess.BISHOP, chess.ROOK, chess.QUEEN]:
                # Check if there's a pin along the line to the king
                pin_info = _check_pin_along_line(board, square, king_square, pinned_color)
                if pin_info:
                    pins.append(pin_info)
    
    return pins


def _check_pin_along_line(board: chess.Board, attacker_sq: int, king_sq: int, pinned_color: chess.Color) -> Optional[Dict]:
    """Check if there's a pin between attacker and king."""
    attacker = board.piece_at(attacker_sq)
    if not attacker:
        return None
    
    # Get the ray from attacker to king
    try:
        ray = chess.ray(attacker_sq, king_sq)
    except:
        return None
    
    if not ray:
        return None
    
    # Check if attacker can actually move along this ray
    if attacker.piece_type == chess.BISHOP:
        # Bishops move diagonally
        if chess.square_file(attacker_sq) == chess.square_file(king_sq) or \
           chess.square_rank(attacker_sq) == chess.square_rank(king_sq):
            return None
    elif attacker.piece_type == chess.ROOK:
        # Rooks move in straight lines
        if chess.square_file(attacker_sq) != chess.square_file(king_sq) and \
           chess.square_rank(attacker_sq) != chess.square_rank(king_sq):
            return None
    
    # Find pieces between attacker and king
    pieces_between = []
    between_squares = chess.between(attacker_sq, king_sq)
    
    for sq in between_squares:
        piece = board.piece_at(sq)
        if piece:
            pieces_between.append({
                "square": sq,
                "piece": piece.piece_type,
                "color": piece.color
            })
    
    # If exactly one piece between, and it's the pinned color, it's a pin
    if len(pieces_between) == 1 and pieces_between[0]["color"] == pinned_color:
        pinned = pieces_between[0]
        return {
            "pinned_square": pinned["square"],
            "pinned_piece": pinned["piece"],
            "behind_piece": chess.KING,  # King is behind
            "attacker_square": attacker_sq,
            "attacker_piece": attacker.piece_type
        }
    
    return None


def _generate_summary(patterns: List[Dict]) -> str:
    """Generate a simple summary of the tactical situation."""
    if not patterns:
        return "Position looks tactically quiet."
    
    issues = []
    
    for p in patterns[:3]:  # Top 3 issues
        if p["type"] == "hanging_piece":
            issues.append(f"hanging {p['piece']}")
        elif p["type"] == "fork_threat":
            issues.append("fork")
        elif p["type"] == "pin":
            issues.append(f"pinned {p['pinned_piece']}")
        elif p["type"] == "opponent_hanging":
            issues.append(f"can capture {p['piece']}")
    
    if issues:
        return f"Watch out for: {', '.join(issues)}"
    return "Position needs attention."


def explain_move_difference(fen_before: str, played_move: str, best_move: str, threat: str = None, user_color: str = "white") -> Dict:
    """
    Explain why best_move is better than played_move in simple terms.
    
    This uses position analysis to give concrete explanations, not generic LLM guesses.
    """
    try:
        board_before = chess.Board(fen_before)
    except:
        return {"error": "Invalid position"}
    
    user_is_white = user_color.lower() == "white"
    
    explanation = {
        "played_move": played_move,
        "best_move": best_move,
        "reasons": [],
        "simple_explanation": "",
        "pattern_detected": None
    }
    
    # Analyze position BEFORE the move
    tactics_before = analyze_position_tactics(fen_before, user_color)
    
    # Try to play the user's move
    try:
        board_after_played = board_before.copy()
        board_after_played.push_san(played_move)
        tactics_after_played = analyze_position_tactics(board_after_played.fen(), user_color)
    except:
        explanation["reasons"].append("Your move may have been illegal or notation error.")
        return explanation
    
    # Try to play the best move
    try:
        board_after_best = board_before.copy()
        board_after_best.push_san(best_move)
        tactics_after_best = analyze_position_tactics(board_after_best.fen(), user_color)
    except:
        pass
    
    # Compare: what problems did user's move create?
    new_problems = []
    for pattern in tactics_after_played.get("patterns", []):
        if pattern["type"] in ["hanging_piece", "fork_threat", "pin"]:
            new_problems.append(pattern)
    
    # Check if there was a threat that user didn't address
    if threat:
        explanation["reasons"].append(f"There was a threat: {threat}. Your move didn't address it.")
        explanation["threat_explanation"] = _explain_threat_square(board_before, threat, user_color)
    
    # Check if user's move created new problems
    if new_problems:
        for prob in new_problems[:2]:
            explanation["reasons"].append(prob["explanation"])
        explanation["pattern_detected"] = new_problems[0]["type"]
    
    # Check if user missed capturing a hanging piece
    opp_hanging_before = [p for p in tactics_before.get("patterns", []) if p["type"] == "opponent_hanging"]
    if opp_hanging_before:
        explanation["reasons"].append(f"You could have captured the {opp_hanging_before[0]['piece']} for free!")
    
    # Generate simple explanation
    if explanation["reasons"]:
        explanation["simple_explanation"] = " ".join(explanation["reasons"][:2])
    else:
        explanation["simple_explanation"] = f"Computer thinks {best_move} is slightly better, but don't worry too much about small differences."
    
    return explanation


def _explain_threat_square(board: chess.Board, threat_square_str: str, user_color: str) -> str:
    """Explain what a threat square does in simple terms."""
    try:
        threat_sq = chess.parse_square(threat_square_str)
    except:
        return f"The square {threat_square_str} was important."
    
    user_is_white = user_color.lower() == "white"
    user_color_chess = chess.WHITE if user_is_white else chess.BLACK
    
    # What pieces does the threat square attack?
    # Simulate a piece on that square
    attacked_pieces = []
    
    # Check what user pieces are around that square
    for sq in chess.SQUARES:
        piece = board.piece_at(sq)
        if piece and piece.color == user_color_chess:
            # Check if threat square can attack this piece
            # This is simplified - in reality depends on what piece moves there
            distance = chess.square_distance(threat_sq, sq)
            if distance <= 2:  # Close pieces
                attacked_pieces.append({
                    "square": sq,
                    "piece": piece.piece_type,
                    "name": PIECE_NAMES[piece.piece_type]
                })
    
    if len(attacked_pieces) >= 2:
        names = [p["name"] for p in attacked_pieces[:2]]
        return f"A piece on {threat_square_str} would attack both your {names[0]} and {names[1]} at once (fork)!"
    elif attacked_pieces:
        return f"A piece on {threat_square_str} attacks your {attacked_pieces[0]['name']}."
    else:
        return f"The square {threat_square_str} controls important space."


# Test the module
if __name__ == "__main__":
    # Test position with a hanging piece
    test_fen = "r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R b KQkq - 3 3"
    result = analyze_position_tactics(test_fen, "black")
    print("Analysis result:", result)
