"""
Position Explainer Service

Generates human-readable explanations for chess mistakes by analyzing:
1. Opening principles (development, center control, king safety)
2. Tactical patterns (hanging pieces, forks, pins, discovered attacks)
3. Positional concepts (pawn structure, piece activity, weak squares)
4. Threat detection (what opponent is threatening)

This is NOT an LLM - it's rule-based chess pattern recognition.
"""

import chess
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# OPENING PRINCIPLES (moves 1-15)
# =============================================================================

OPENING_PRINCIPLES = {
    "develop_pieces": "Develop your knights and bishops before moving the same piece twice",
    "control_center": "Control the center with pawns (e4/d4 or e5/d5) and pieces",
    "castle_early": "Castle early to protect your king and connect your rooks",
    "dont_move_queen_early": "Don't bring your queen out too early - it can be chased",
    "connect_rooks": "Develop all pieces so your rooks can see each other",
    "dont_move_same_piece": "Don't move the same piece twice in the opening without a good reason",
    "dont_grab_pawns": "Don't waste time grabbing pawns at the cost of development",
}

# Common opening mistake patterns
OPENING_MISTAKES = {
    "queen_early": {
        "condition": lambda board, move: move.piece_type == chess.QUEEN and len(list(board.move_stack)) < 10,
        "explanation": "Moving the queen too early allows your opponent to develop with tempo by attacking it.",
        "rule": "Keep your queen safe until you've developed your minor pieces."
    },
    "same_piece_twice": {
        "condition": lambda board, move, history: _moved_same_piece_twice(board, move, history),
        "explanation": "You moved the same piece twice in the opening, losing development time.",
        "rule": "Develop a new piece instead of moving the same one twice."
    },
    "neglect_development": {
        "condition": lambda board, move: _is_neglecting_development(board, move),
        "explanation": "You have undeveloped pieces while making pawn moves or shuffling pieces.",
        "rule": "Develop knights and bishops before advancing pawns past the 4th rank."
    },
    "weakening_king": {
        "condition": lambda board, move: _is_weakening_king_safety(board, move),
        "explanation": "This pawn move weakens your king's safety.",
        "rule": "Don't push pawns in front of your castled king without a clear plan."
    },
}


def _moved_same_piece_twice(board: chess.Board, move: chess.Move, history: List[chess.Move]) -> bool:
    """Check if this piece was moved before in the opening."""
    if len(history) < 2:
        return False
    
    # Look through recent moves for the same piece
    piece_origin_square = move.from_square
    for prev_move in history[-6:]:  # Last 3 moves by this player
        if prev_move.to_square == piece_origin_square:
            return True
    return False


def _is_neglecting_development(board: chess.Board, move: chess.Move) -> bool:
    """Check if player is making non-developing moves with undeveloped pieces."""
    color = board.turn
    
    # Count undeveloped minor pieces
    undeveloped = 0
    
    for sq in [chess.B1, chess.G1, chess.C1, chess.F1] if color == chess.WHITE else [chess.B8, chess.G8, chess.C8, chess.F8]:
        piece = board.piece_at(sq)
        if piece and piece.color == color and piece.piece_type in [chess.KNIGHT, chess.BISHOP]:
            undeveloped += 1
    
    # If we have 2+ undeveloped pieces and this move doesn't develop
    if undeveloped >= 2:
        moving_piece = board.piece_at(move.from_square)
        if moving_piece and moving_piece.piece_type == chess.PAWN:
            # Check if pawn move is past 4th rank
            to_rank = chess.square_rank(move.to_square)
            if (color == chess.WHITE and to_rank > 3) or (color == chess.BLACK and to_rank < 4):
                return True
    
    return False


def _is_weakening_king_safety(board: chess.Board, move: chess.Move) -> bool:
    """Check if a pawn move weakens king safety."""
    moving_piece = board.piece_at(move.from_square)
    if not moving_piece or moving_piece.piece_type != chess.PAWN:
        return False
    
    color = board.turn
    king_sq = board.king(color)
    if not king_sq:
        return False
    
    king_file = chess.square_file(king_sq)
    pawn_file = chess.square_file(move.from_square)
    
    # Check if pawn is near king (within 1 file)
    if abs(king_file - pawn_file) <= 1:
        # Check if king has castled (king on g/h or a/b files)
        if king_file >= 5 or king_file <= 2:  # Castled position
            return True
    
    return False


# =============================================================================
# TACTICAL PATTERNS
# =============================================================================

@dataclass
class TacticalThreat:
    """Represents a tactical threat on the board."""
    threat_type: str  # "hanging", "fork", "pin", "skewer", "discovered", "back_rank"
    target_squares: List[str]
    attacker_square: str
    explanation: str
    arrow: Tuple[str, str, str]  # from, to, color


def detect_hanging_pieces(board: chess.Board, color: chess.Color) -> List[TacticalThreat]:
    """Find pieces that are attacked but not defended."""
    threats = []
    
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if not piece or piece.color != color:
            continue
        
        # Skip pawns for now (hanging pieces usually refers to pieces)
        if piece.piece_type == chess.PAWN:
            continue
        
        # Check if attacked
        attackers = board.attackers(not color, square)
        if not attackers:
            continue
        
        # Check if defended
        defenders = board.attackers(color, square)
        
        # Get piece values
        piece_value = _piece_value(piece.piece_type)
        
        # Find lowest value attacker
        min_attacker_value = min(_piece_value(board.piece_at(sq).piece_type) for sq in attackers)
        
        # Hanging if no defenders OR if attacker value < piece value
        if not defenders or min_attacker_value < piece_value:
            attacker_sq = list(attackers)[0]
            threats.append(TacticalThreat(
                threat_type="hanging",
                target_squares=[chess.square_name(square)],
                attacker_square=chess.square_name(attacker_sq),
                explanation=f"Your {chess.piece_name(piece.piece_type)} on {chess.square_name(square)} is undefended and can be captured.",
                arrow=(chess.square_name(attacker_sq), chess.square_name(square), "red")
            ))
    
    return threats


def detect_forks(board: chess.Board, color: chess.Color) -> List[TacticalThreat]:
    """Find potential fork opportunities for opponent."""
    threats = []
    opponent = not color
    
    # Check knight forks
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if piece and piece.piece_type == chess.KNIGHT and piece.color == opponent:
            # See what this knight attacks
            attacked = []
            for target in board.attacks(square):
                target_piece = board.piece_at(target)
                if target_piece and target_piece.color == color and target_piece.piece_type in [chess.QUEEN, chess.ROOK, chess.KING]:
                    attacked.append(target)
            
            if len(attacked) >= 2:
                threats.append(TacticalThreat(
                    threat_type="fork",
                    target_squares=[chess.square_name(sq) for sq in attacked],
                    attacker_square=chess.square_name(square),
                    explanation=f"The knight on {chess.square_name(square)} is forking your pieces!",
                    arrow=(chess.square_name(square), chess.square_name(attacked[0]), "red")
                ))
    
    return threats


def detect_pins(board: chess.Board, color: chess.Color) -> List[TacticalThreat]:
    """Find pinned pieces."""
    threats = []
    king_sq = board.king(color)
    if not king_sq:
        return threats
    
    # Check all opponent's sliding pieces
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if not piece or piece.color == color:
            continue
        
        if piece.piece_type not in [chess.BISHOP, chess.ROOK, chess.QUEEN]:
            continue
        
        # Check if there's a piece between this attacker and our king
        ray = _get_ray_between(square, king_sq)
        if not ray:
            continue
        
        pieces_in_ray = []
        for sq in ray:
            p = board.piece_at(sq)
            if p:
                pieces_in_ray.append((sq, p))
        
        # If exactly one piece in ray and it's ours, it's pinned
        if len(pieces_in_ray) == 1 and pieces_in_ray[0][1].color == color:
            pinned_sq, pinned_piece = pieces_in_ray[0]
            threats.append(TacticalThreat(
                threat_type="pin",
                target_squares=[chess.square_name(pinned_sq)],
                attacker_square=chess.square_name(square),
                explanation=f"Your {chess.piece_name(pinned_piece.piece_type)} on {chess.square_name(pinned_sq)} is pinned to your king.",
                arrow=(chess.square_name(square), chess.square_name(pinned_sq), "red")
            ))
    
    return threats


def _get_ray_between(sq1: int, sq2: int) -> Optional[List[int]]:
    """Get squares between two squares on a line (if they're on a line)."""
    file1, rank1 = chess.square_file(sq1), chess.square_rank(sq1)
    file2, rank2 = chess.square_file(sq2), chess.square_rank(sq2)
    
    df = file2 - file1
    dr = rank2 - rank1
    
    # Must be on same file, rank, or diagonal
    if df != 0 and dr != 0 and abs(df) != abs(dr):
        return None
    
    # Normalize direction
    df = 0 if df == 0 else df // abs(df)
    dr = 0 if dr == 0 else dr // abs(dr)
    
    squares = []
    f, r = file1 + df, rank1 + dr
    while (f, r) != (file2, rank2):
        squares.append(chess.square(f, r))
        f += df
        r += dr
    
    return squares if squares else None


def _piece_value(piece_type: int) -> int:
    """Get material value of piece."""
    values = {
        chess.PAWN: 100,
        chess.KNIGHT: 300,
        chess.BISHOP: 320,
        chess.ROOK: 500,
        chess.QUEEN: 900,
        chess.KING: 10000,
    }
    return values.get(piece_type, 0)


# =============================================================================
# MAIN EXPLANATION GENERATOR
# =============================================================================

def explain_mistake(
    fen_before: str,
    played_move_uci: str,
    best_move_uci: str,
    eval_before: int,
    eval_after: int,
    move_number: int,
    pv_after_best: List[str] = None
) -> Dict[str, Any]:
    """
    Generate a human-readable explanation for why a move was a mistake.
    
    Returns:
        {
            "headline": "Short title",
            "explanation": "Detailed explanation",
            "rule": "The principle to remember",
            "arrows": [(from, to, color), ...],
            "category": "opening|tactical|positional"
        }
    """
    board = chess.Board(fen_before)
    
    try:
        played_move = chess.Move.from_uci(played_move_uci)
        best_move = chess.Move.from_uci(best_move_uci)
    except ValueError:
        return _default_explanation(eval_before, eval_after)
    
    color = board.turn
    eval_loss = abs(eval_after - eval_before)
    
    arrows = []
    
    # =================================================================
    # 1. CHECK OPENING PRINCIPLES (moves 1-15)
    # =================================================================
    if move_number <= 15:
        opening_issue = _check_opening_principles(board, played_move, best_move, move_number)
        if opening_issue:
            # Add arrow showing best move
            arrows.append((chess.square_name(best_move.from_square), 
                          chess.square_name(best_move.to_square), "green"))
            return {
                **opening_issue,
                "arrows": arrows,
                "category": "opening"
            }
    
    # =================================================================
    # 2. CHECK FOR TACTICAL MISTAKES
    # =================================================================
    
    # Make the played move and check what threats exist
    board.push(played_move)
    
    # Check for hanging pieces we just created
    hanging = detect_hanging_pieces(board, color)
    if hanging:
        threat = hanging[0]
        arrows.append(threat.arrow)
        arrows.append((chess.square_name(best_move.from_square), 
                      chess.square_name(best_move.to_square), "green"))
        return {
            "headline": "You left a piece undefended",
            "explanation": threat.explanation,
            "rule": "Before every move, check: Is my piece safe after this move?",
            "arrows": arrows,
            "category": "tactical"
        }
    
    # Check for forks
    forks = detect_forks(board, color)
    if forks:
        threat = forks[0]
        arrows.append(threat.arrow)
        arrows.append((chess.square_name(best_move.from_square), 
                      chess.square_name(best_move.to_square), "green"))
        return {
            "headline": "You allowed a fork",
            "explanation": threat.explanation + " The best move prevented this.",
            "rule": "Check if opponent's pieces can attack two of yours at once.",
            "arrows": arrows,
            "category": "tactical"
        }
    
    # Check for pins
    pins = detect_pins(board, color)
    if pins:
        threat = pins[0]
        arrows.append(threat.arrow)
        arrows.append((chess.square_name(best_move.from_square), 
                      chess.square_name(best_move.to_square), "green"))
        return {
            "headline": "You got pinned",
            "explanation": threat.explanation,
            "rule": "Watch for diagonal and straight lines between your pieces and king.",
            "arrows": arrows,
            "category": "tactical"
        }
    
    board.pop()  # Undo the played move
    
    # =================================================================
    # 3. CHECK IF BEST MOVE WAS A TACTIC WE MISSED
    # =================================================================
    
    board.push(best_move)
    
    # Was best move a capture?
    if best_move.to_square in [m.to_square for m in board.legal_moves if board.is_capture(m)]:
        arrows.append((chess.square_name(best_move.from_square), 
                      chess.square_name(best_move.to_square), "green"))
        return {
            "headline": "You missed a winning capture",
            "explanation": "The best move was capturing material. You had a free or winning capture available.",
            "rule": "Before every move, check: Can I capture something good?",
            "arrows": arrows,
            "category": "tactical"
        }
    
    # Was best move giving check?
    if board.is_check():
        arrows.append((chess.square_name(best_move.from_square), 
                      chess.square_name(best_move.to_square), "green"))
        return {
            "headline": "You missed a check",
            "explanation": "The best move was a check, which would have given you tempo or won material.",
            "rule": "Always look for checks first - they force your opponent to respond.",
            "arrows": arrows,
            "category": "tactical"
        }
    
    board.pop()
    
    # =================================================================
    # 4. ANALYZE THE PV TO UNDERSTAND THE CONSEQUENCE
    # =================================================================
    if pv_after_best and len(pv_after_best) >= 2:
        consequence = _analyze_pv_consequence(board, best_move, pv_after_best)
        if consequence:
            arrows.append((chess.square_name(best_move.from_square), 
                          chess.square_name(best_move.to_square), "green"))
            return {
                **consequence,
                "arrows": arrows,
                "category": "tactical"
            }
    
    # =================================================================
    # 5. GENERIC EXPLANATION BASED ON EVAL LOSS
    # =================================================================
    arrows.append((chess.square_name(best_move.from_square), 
                  chess.square_name(best_move.to_square), "green"))
    
    if eval_loss >= 300:
        return {
            "headline": "This move loses significant material",
            "explanation": "Your move allowed your opponent to gain a big advantage. The best move maintained your position.",
            "rule": "Calculate your opponent's best reply before making your move.",
            "arrows": arrows,
            "category": "tactical"
        }
    elif eval_loss >= 150:
        return {
            "headline": "This move weakens your position",
            "explanation": "Your move gave your opponent an advantage. Look at the suggested line to see why.",
            "rule": "Ask yourself: What does my opponent want to do next?",
            "arrows": arrows,
            "category": "positional"
        }
    else:
        return {
            "headline": "A more accurate move was available",
            "explanation": "Your move was okay, but there was a better option. Study the suggested line.",
            "rule": "Look for moves that improve your position AND create threats.",
            "arrows": arrows,
            "category": "positional"
        }


def _check_opening_principles(
    board: chess.Board, 
    played_move: chess.Move, 
    best_move: chess.Move,
    move_number: int
) -> Optional[Dict[str, Any]]:
    """Check if an opening principle was violated."""
    color = board.turn
    moving_piece = board.piece_at(played_move.from_square)
    
    if not moving_piece:
        return None
    
    # Count development
    developed_minors = _count_developed_pieces(board, color)
    
    # Check: Queen out too early?
    if moving_piece.piece_type == chess.QUEEN and developed_minors < 3:
        return {
            "headline": "Queen out too early",
            "explanation": "Moving your queen early allows your opponent to attack it while developing their pieces. You lose time defending it.",
            "rule": "Develop knights and bishops before bringing out your queen."
        }
    
    # Check: Moving same piece twice?
    if move_number <= 10:
        move_history = list(board.move_stack)
        for i in range(len(move_history) - 2, -1, -2):  # Every other move (same color)
            if i < 0:
                break
            prev_move = move_history[i]
            if prev_move.to_square == played_move.from_square:
                piece_name = chess.piece_name(moving_piece.piece_type)
                return {
                    "headline": f"Moving the same {piece_name} twice",
                    "explanation": "You're moving the same piece twice in the opening. Meanwhile, your opponent develops new pieces.",
                    "rule": "Develop a NEW piece instead of moving one that's already developed."
                }
    
    # Check: Pawn grabbing instead of developing?
    if moving_piece.piece_type == chess.PAWN and developed_minors < 3:
        target_piece = board.piece_at(played_move.to_square)
        if target_piece:  # Capture
            return {
                "headline": "Grabbing pawns instead of developing",
                "explanation": "Capturing this pawn wastes time. Your opponent gains development advantage.",
                "rule": "Development is more important than winning a pawn in the opening."
            }
    
    # Check: Not castling when you should?
    if move_number >= 8 and _can_castle(board, color) and not _is_castling(played_move):
        if best_move and _is_castling(best_move):
            return {
                "headline": "Time to castle",
                "explanation": "Your king is still in the center. Castle to safety before your opponent opens lines against it.",
                "rule": "Castle early to protect your king and activate your rook."
            }
    
    return None


def _count_developed_pieces(board: chess.Board, color: chess.Color) -> int:
    """Count knights and bishops that have moved from their starting squares."""
    developed = 0
    starting_squares = {
        chess.WHITE: [chess.B1, chess.G1, chess.C1, chess.F1],
        chess.BLACK: [chess.B8, chess.G8, chess.C8, chess.F8],
    }
    
    for sq in starting_squares[color]:
        piece = board.piece_at(sq)
        if not piece or piece.color != color:
            developed += 1  # Piece has moved from starting square
    
    return developed


def _can_castle(board: chess.Board, color: chess.Color) -> bool:
    """Check if castling is still possible."""
    if color == chess.WHITE:
        return board.has_kingside_castling_rights(chess.WHITE) or board.has_queenside_castling_rights(chess.WHITE)
    else:
        return board.has_kingside_castling_rights(chess.BLACK) or board.has_queenside_castling_rights(chess.BLACK)


def _is_castling(move: chess.Move) -> bool:
    """Check if a move is castling."""
    return chess.square_name(move.from_square) in ['e1', 'e8'] and \
           chess.square_name(move.to_square) in ['g1', 'c1', 'g8', 'c8']


def _analyze_pv_consequence(
    board: chess.Board, 
    best_move: chess.Move, 
    pv: List[str]
) -> Optional[Dict[str, Any]]:
    """Analyze the PV to understand what the best move achieves."""
    try:
        temp_board = board.copy()
        temp_board.push(best_move)
        
        for move_uci in pv[:4]:  # Look at first 4 moves of PV
            try:
                move = chess.Move.from_uci(move_uci)
                if move not in temp_board.legal_moves:
                    # Try SAN
                    move = temp_board.parse_san(move_uci)
                temp_board.push(move)
            except (ValueError, chess.InvalidMoveError):
                break
        
        # Check if we won material
        # Check if we created a strong threat
        # Check if we improved piece placement
        
        # For now, return None and let generic handler deal with it
        return None
    except (ValueError, chess.InvalidMoveError):
        return None


def _default_explanation(eval_before: int, eval_after: int) -> Dict[str, Any]:
    """Fallback explanation."""
    eval_loss = abs(eval_after - eval_before)
    return {
        "headline": "A better move was available",
        "explanation": f"This move lost about {eval_loss // 100} pawns worth of advantage.",
        "rule": "Calculate your opponent's best reply before committing to a move.",
        "arrows": [],
        "category": "tactical"
    }
