"""
UNIFIED CHESS VERIFICATION LAYER

This is the SINGLE SOURCE OF TRUTH for all position analysis in the app.
ALL services that need to analyze chess positions MUST use this layer.

Why this exists:
- Multiple services were creating their own chess.Board instances
- Different services used different analysis logic
- Some services missed critical patterns (like checkmate!)
- LLM explanations were based on inconsistent data

What this provides:
1. Safe FEN parsing with error handling
2. Priority-ordered analysis (checkmate > tactics > positional)
3. Consistent data format for LLM prompts
4. Verified facts that can't be hallucinated

USAGE:
    from chess_verification_layer import verify_position, verify_move, get_critical_facts
    
    # For any position analysis
    facts = verify_position(fen)
    
    # For move comparison (user move vs best move)
    analysis = verify_move(fen, user_move, best_move)
    
    # For LLM-ready data (what to tell the LLM)
    llm_context = get_critical_facts(fen, user_move, best_move, cp_loss)
"""

import chess
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

# ============================================================================
# CONSTANTS
# ============================================================================

PIECE_VALUES = {
    chess.PAWN: 1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9,
    chess.KING: 100  # Very high - can't actually lose king
}

PIECE_NAMES = {
    chess.PAWN: "pawn",
    chess.KNIGHT: "knight",
    chess.BISHOP: "bishop",
    chess.ROOK: "rook",
    chess.QUEEN: "queen",
    chess.KING: "king"
}


class CriticalPattern(Enum):
    """Ordered by severity - checkmate patterns ALWAYS come first"""
    ALLOWS_MATE_IN_1 = "allows_mate_in_1"
    ALLOWS_MATE_IN_2 = "allows_mate_in_2"
    MISSES_MATE_IN_1 = "misses_mate_in_1"
    MISSES_MATE_IN_2 = "misses_mate_in_2"
    HANGS_QUEEN = "hangs_queen"
    HANGS_ROOK = "hangs_rook"
    HANGS_PIECE = "hangs_piece"
    WALKS_INTO_FORK = "walks_into_fork"
    WALKS_INTO_PIN = "walks_into_pin"
    MISSES_FORK = "misses_fork"
    MISSES_PIN = "misses_pin"
    POSITIONAL_ERROR = "positional_error"


# ============================================================================
# SAFE FEN PARSING
# ============================================================================

def safe_board(fen: str) -> Optional[chess.Board]:
    """
    Safely create a chess.Board from FEN.
    Returns None if FEN is invalid.
    """
    try:
        board = chess.Board(fen)
        return board
    except Exception as e:
        logger.error(f"Invalid FEN: {fen}, error: {e}")
        return None


def safe_move(board: chess.Board, move_san: str) -> Optional[chess.Move]:
    """
    Safely parse a SAN move.
    Returns None if move is invalid.
    """
    try:
        return board.parse_san(move_san)
    except (ValueError, chess.IllegalMoveError, chess.InvalidMoveError, chess.AmbiguousMoveError) as e:
        logger.warning(f"Invalid move {move_san}: {e}")
        return None


# ============================================================================
# CHECKMATE DETECTION (PRIORITY 0 - MOST CRITICAL)
# ============================================================================

def check_mate_in_1(board: chess.Board) -> Optional[str]:
    """
    Check if the side to move has mate in 1.
    Returns the mating move in SAN, or None.
    """
    for move in board.legal_moves:
        test = board.copy()
        test.push(move)
        if test.is_checkmate():
            return board.san(move)
    return None


def check_allows_mate_in_1(board: chess.Board) -> Optional[str]:
    """
    Check if opponent can mate in 1 on their next move.
    Returns the mating move in SAN, or None.
    """
    for move in board.legal_moves:
        test = board.copy()
        test.push(move)
        if test.is_checkmate():
            return board.san(move)
    return None


def check_mate_in_2(board: chess.Board, limit: int = 50) -> bool:
    """
    Check if the side to move has a forced mate in 2.
    Limited search for performance.
    Returns True if mate in 2 exists.
    """
    moves_checked = 0
    for move1 in board.legal_moves:
        if moves_checked > limit:
            return False
        moves_checked += 1
        
        test1 = board.copy()
        test1.push(move1)
        
        if test1.is_checkmate():
            continue  # This is mate in 1, not 2
        
        # Check if ALL opponent responses lead to mate
        all_lead_to_mate = True
        for opp_response in test1.legal_moves:
            test2 = test1.copy()
            test2.push(opp_response)
            
            # Now check if we have mate
            has_mate = False
            for final_move in test2.legal_moves:
                test3 = test2.copy()
                test3.push(final_move)
                if test3.is_checkmate():
                    has_mate = True
                    break
            
            if not has_mate:
                all_lead_to_mate = False
                break
        
        if all_lead_to_mate and test1.legal_moves:
            return True
    
    return False


# ============================================================================
# TACTICAL PATTERN DETECTION
# ============================================================================

def detect_hanging_pieces(board: chess.Board, color: chess.Color) -> List[Dict]:
    """
    Find all hanging pieces (attacked but undefended) for a color.
    """
    hanging = []
    opponent = not color
    
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if piece and piece.color == color:
            attackers = board.attackers(opponent, square)
            defenders = board.attackers(color, square)
            
            if attackers and not defenders:
                hanging.append({
                    "square": chess.square_name(square),
                    "piece": PIECE_NAMES.get(piece.piece_type, "piece"),
                    "value": PIECE_VALUES.get(piece.piece_type, 0),
                    "attackers": len(attackers)
                })
    
    # Sort by value (most valuable first)
    hanging.sort(key=lambda x: -x["value"])
    return hanging


def detect_forks(board: chess.Board, color: chess.Color) -> List[Dict]:
    """
    Find all fork opportunities for a color.
    A fork is when one piece attacks 2+ valuable pieces.
    """
    forks = []
    
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if piece and piece.color == color:
            # What does this piece attack?
            attacked_pieces = []
            for target in chess.SQUARES:
                if board.is_attacked_by(color, target):
                    target_piece = board.piece_at(target)
                    if target_piece and target_piece.color != color:
                        # Check if THIS piece attacks it
                        attackers = board.attackers(color, target)
                        if square in attackers:
                            attacked_pieces.append({
                                "square": chess.square_name(target),
                                "piece": PIECE_NAMES.get(target_piece.piece_type, "piece"),
                                "value": PIECE_VALUES.get(target_piece.piece_type, 0)
                            })
            
            # A fork needs 2+ targets with combined value > attacker
            if len(attacked_pieces) >= 2:
                total_value = sum(t["value"] for t in attacked_pieces)
                attacker_value = PIECE_VALUES.get(piece.piece_type, 0)
                if total_value > attacker_value:
                    forks.append({
                        "attacker": PIECE_NAMES.get(piece.piece_type),
                        "attacker_square": chess.square_name(square),
                        "targets": attacked_pieces,
                        "total_value": total_value
                    })
    
    return forks


def detect_pins(board: chess.Board, color: chess.Color) -> List[Dict]:
    """
    Find all pins against a color.
    A pin is when a piece can't move because it would expose a more valuable piece.
    """
    pins = []
    opponent = not color
    king_square = board.king(color)
    
    if king_square is None:
        return pins
    
    # Check for pins along ranks, files, and diagonals
    for attacker_square in chess.SQUARES:
        attacker = board.piece_at(attacker_square)
        if not attacker or attacker.color != opponent:
            continue
        
        # Only bishops, rooks, queens can pin
        if attacker.piece_type not in [chess.BISHOP, chess.ROOK, chess.QUEEN]:
            continue
        
        # Check if there's exactly one piece between attacker and king
        between = list(chess.SquareSet.between(attacker_square, king_square))
        pieces_between = [s for s in between if board.piece_at(s)]
        
        if len(pieces_between) == 1:
            pinned_square = pieces_between[0]
            pinned_piece = board.piece_at(pinned_square)
            if pinned_piece and pinned_piece.color == color:
                pins.append({
                    "pinned_piece": PIECE_NAMES.get(pinned_piece.piece_type),
                    "pinned_square": chess.square_name(pinned_square),
                    "attacker": PIECE_NAMES.get(attacker.piece_type),
                    "attacker_square": chess.square_name(attacker_square),
                    "pinned_to": "king"
                })
    
    return pins


# ============================================================================
# MAIN VERIFICATION FUNCTIONS
# ============================================================================

def verify_position(fen: str) -> Dict:
    """
    Verify and analyze a chess position.
    Returns all facts about the position that can be used for explanations.
    
    This is the PRIMARY entry point for position analysis.
    """
    board = safe_board(fen)
    if board is None:
        return {"error": "Invalid FEN", "valid": False}
    
    side_to_move = chess.WHITE if board.turn else chess.BLACK
    opponent = not side_to_move
    
    result = {
        "valid": True,
        "fen": fen,
        "side_to_move": "white" if board.turn else "black",
        "is_check": board.is_check(),
        "is_checkmate": board.is_checkmate(),
        "is_stalemate": board.is_stalemate(),
        
        # Checkmate detection (CRITICAL)
        "mate_in_1": check_mate_in_1(board),
        "opponent_mate_in_1": None,  # Will check after opponent moves
        
        # Tactical patterns
        "hanging_pieces": detect_hanging_pieces(board, side_to_move),
        "opponent_hanging": detect_hanging_pieces(board, opponent),
        "our_forks": detect_forks(board, side_to_move),
        "opponent_forks": detect_forks(board, opponent),
        "pins_on_us": detect_pins(board, side_to_move),
        "pins_on_opponent": detect_pins(board, opponent),
    }
    
    return result


def verify_move(fen: str, move_san: str, best_move_san: str = None, cp_loss: int = 0) -> Dict:
    """
    Verify what happens when a specific move is played.
    Compares to best move if provided.
    
    Returns analysis of:
    - What the move actually does
    - What it allows opponent to do
    - What was missed (if best_move provided)
    """
    board = safe_board(fen)
    if board is None:
        return {"error": "Invalid FEN", "valid": False}
    
    move = safe_move(board, move_san)
    if move is None:
        return {"error": f"Invalid move: {move_san}", "valid": False}
    
    user_color = board.turn
    opponent_color = not user_color
    
    # Analyze before the move
    before_analysis = {
        "is_check": board.is_check(),
        "our_mate_in_1": check_mate_in_1(board),
    }
    
    # Play the move
    moving_piece = board.piece_at(move.from_square)
    captured_piece = board.piece_at(move.to_square)
    
    board.push(move)
    
    # CRITICAL: Check what opponent can do now
    opponent_has_mate_in_1 = check_mate_in_1(board)  # From opponent's perspective
    
    # Check for immediate problems
    critical_issues = []
    
    if opponent_has_mate_in_1:
        critical_issues.append({
            "type": CriticalPattern.ALLOWS_MATE_IN_1.value,
            "severity": "decisive",
            "detail": f"Allows {opponent_has_mate_in_1} which is checkmate!",
            "mating_move": opponent_has_mate_in_1
        })
    
    # Check if user missed mate
    if best_move_san and before_analysis["our_mate_in_1"]:
        if before_analysis["our_mate_in_1"] == best_move_san:
            critical_issues.append({
                "type": CriticalPattern.MISSES_MATE_IN_1.value,
                "severity": "decisive",
                "detail": f"Missed {best_move_san} which is checkmate!",
                "mating_move": best_move_san
            })
    
    # Check for hanging pieces after our move
    our_hanging = detect_hanging_pieces(board, user_color)
    if our_hanging:
        most_valuable = our_hanging[0]
        if most_valuable["value"] >= 9:
            critical_issues.append({
                "type": CriticalPattern.HANGS_QUEEN.value,
                "severity": "major",
                "detail": f"Queen on {most_valuable['square']} is now hanging"
            })
        elif most_valuable["value"] >= 5:
            critical_issues.append({
                "type": CriticalPattern.HANGS_ROOK.value,
                "severity": "major",
                "detail": f"Rook on {most_valuable['square']} is now hanging"
            })
        elif most_valuable["value"] >= 3:
            critical_issues.append({
                "type": CriticalPattern.HANGS_PIECE.value,
                "severity": "moderate",
                "detail": f"{most_valuable['piece'].title()} on {most_valuable['square']} is now hanging"
            })
    
    # Check for forks opponent can now do
    opponent_forks = detect_forks(board, opponent_color)
    if opponent_forks:
        best_fork = max(opponent_forks, key=lambda f: f["total_value"])
        targets = ", ".join([t["piece"] for t in best_fork["targets"]])
        critical_issues.append({
            "type": CriticalPattern.WALKS_INTO_FORK.value,
            "severity": "moderate",
            "detail": f"Opponent's {best_fork['attacker']} can fork: {targets}"
        })
    
    result = {
        "valid": True,
        "move": move_san,
        "piece_moved": PIECE_NAMES.get(moving_piece.piece_type) if moving_piece else None,
        "is_capture": captured_piece is not None,
        "captured": PIECE_NAMES.get(captured_piece.piece_type) if captured_piece else None,
        "gives_check": board.is_check(),
        "cp_loss": cp_loss,
        
        # CRITICAL: What's wrong with this move?
        "critical_issues": critical_issues,
        "most_critical": critical_issues[0] if critical_issues else None,
        
        # Tactical state after move
        "our_hanging_pieces": our_hanging,
        "opponent_can_fork": bool(opponent_forks),
    }
    
    return result


def get_critical_facts(fen: str, user_move: str, best_move: str, cp_loss: int) -> Dict:
    """
    Get the critical facts about a position for LLM context.
    
    This is what you pass to the LLM to generate explanations.
    The LLM should ONLY narrate these facts, not analyze the position.
    
    Returns a dict with:
    - primary_issue: The most important thing (e.g., "allowed mate in 1")
    - explanation_facts: List of verified facts to include
    - severity: How bad was this move
    - thinking_habit: What habit would prevent this
    """
    analysis = verify_move(fen, user_move, best_move, cp_loss)
    
    if not analysis.get("valid"):
        return {
            "primary_issue": "unknown",
            "explanation_facts": ["Could not analyze position"],
            "severity": "unknown",
            "thinking_habit": None
        }
    
    # Get the most critical issue
    most_critical = analysis.get("most_critical")
    
    if most_critical:
        issue_type = most_critical["type"]
        
        # Map issue types to thinking habits
        THINKING_HABITS = {
            CriticalPattern.ALLOWS_MATE_IN_1.value: "Before EVERY move, check: Does this allow any checks? Can those checks be mate?",
            CriticalPattern.ALLOWS_MATE_IN_2.value: "When your king is exposed, look at ALL opponent checks before moving.",
            CriticalPattern.MISSES_MATE_IN_1.value: "Every move, scan: Do I have any checks? Is any check also checkmate?",
            CriticalPattern.MISSES_MATE_IN_2.value: "When you have active pieces near the king, ALWAYS check for mate patterns.",
            CriticalPattern.HANGS_QUEEN.value: "After deciding your move, check: Is my queen safe? Is it defended?",
            CriticalPattern.HANGS_ROOK.value: "After deciding your move, verify your rooks are not hanging.",
            CriticalPattern.HANGS_PIECE.value: "Before playing, check: Does this leave any piece undefended?",
            CriticalPattern.WALKS_INTO_FORK.value: "Check where opponent's knights can jump to - can they hit 2 pieces?",
            CriticalPattern.WALKS_INTO_PIN.value: "Be aware of open lines to your king - pieces can get pinned.",
        }
        
        return {
            "primary_issue": issue_type,
            "primary_detail": most_critical.get("detail", ""),
            "explanation_facts": [most_critical.get("detail", "")] + 
                                [i.get("detail", "") for i in analysis.get("critical_issues", [])[1:3]],
            "severity": most_critical.get("severity", "moderate"),
            "thinking_habit": THINKING_HABITS.get(issue_type),
            "mating_move": most_critical.get("mating_move")
        }
    
    # No critical tactical issue - probably positional
    return {
        "primary_issue": CriticalPattern.POSITIONAL_ERROR.value,
        "primary_detail": f"This move lost {cp_loss} centipawns - a positional inaccuracy",
        "explanation_facts": [
            f"Move played: {user_move}",
            f"Better move: {best_move}",
            f"Evaluation drop: {cp_loss} centipawns"
        ],
        "severity": "minor" if cp_loss < 100 else "moderate",
        "thinking_habit": "Compare candidate moves: What does each accomplish? What does each allow?"
    }


# ============================================================================
# CONSISTENCY CHECK - For auditing
# ============================================================================

def audit_position_analysis(fen: str, user_move: str, best_move: str, cp_loss: int) -> Dict:
    """
    Full audit of position analysis for debugging.
    Use this to verify all analysis is consistent.
    """
    return {
        "position": verify_position(fen),
        "move_analysis": verify_move(fen, user_move, best_move, cp_loss),
        "llm_context": get_critical_facts(fen, user_move, best_move, cp_loss)
    }
