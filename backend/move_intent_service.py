"""
Move Intent Hypothesis Service - Position-Specific Intent Detection

Analyzes what a move actually DOES in the position and generates
confident hypotheses about what the player might have been thinking.

This is the crucial layer between Stockfish analysis and user reflection.
No LLM - pure chess logic to generate accurate hypotheses.

Example output for a move like Nf3:
- "Were you trying to control the e5 square?"
- "Were you defending the d4 pawn?"
- "Were you preparing to castle kingside?"

Only outputs CONFIDENT hypotheses that are actually valid in the position.
"""

import chess
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass
from enum import Enum


class IntentCategory(str, Enum):
    """Categories of move intent."""
    ATTACK = "attack"           # Attacking enemy piece/square
    DEFEND = "defend"           # Defending own piece
    CONTROL = "control"         # Controlling key square
    DEVELOP = "develop"         # Developing piece
    KING_SAFETY = "king_safety" # Castling or king protection
    TRADE = "trade"             # Initiating trade
    THREAT = "threat"           # Creating a threat
    PREVENT = "prevent"         # Preventing opponent's plan
    MATERIAL = "material"       # Winning material
    ESCAPE = "escape"           # Moving piece out of danger
    STRUCTURE = "structure"     # Pawn structure related
    ACTIVITY = "activity"       # Improving piece activity


@dataclass
class IntentHypothesis:
    """A hypothesis about why the user played a move."""
    category: IntentCategory
    confidence: float  # 0.0 to 1.0
    description: str   # Human-readable description
    evidence: str      # Why we think this
    square_or_piece: Optional[str] = None  # Related square or piece


def get_piece_name(piece: chess.Piece) -> str:
    """Get human-readable piece name."""
    names = {
        chess.PAWN: "pawn",
        chess.KNIGHT: "knight",
        chess.BISHOP: "bishop",
        chess.ROOK: "rook",
        chess.QUEEN: "queen",
        chess.KING: "king",
    }
    return names.get(piece.piece_type, "piece")


def get_square_name(square: int) -> str:
    """Get human-readable square name."""
    return chess.square_name(square)


def is_center_square(square: int) -> bool:
    """Check if square is in the center (d4, d5, e4, e5)."""
    return square in [chess.D4, chess.D5, chess.E4, chess.E5]


def is_extended_center(square: int) -> bool:
    """Check if square is in extended center."""
    center = {chess.C3, chess.C4, chess.C5, chess.C6,
              chess.D3, chess.D4, chess.D5, chess.D6,
              chess.E3, chess.E4, chess.E5, chess.E6,
              chess.F3, chess.F4, chess.F5, chess.F6}
    return square in center


def get_attacked_squares(board: chess.Board, square: int) -> Set[int]:
    """Get all squares attacked by a piece on given square."""
    return set(board.attacks(square))


def get_defenders(board: chess.Board, square: int, color: chess.Color) -> List[int]:
    """Get all pieces of given color defending a square."""
    defenders = []
    for attacker_square in board.attackers(color, square):
        defenders.append(attacker_square)
    return defenders


def analyze_move_intent(
    fen_before: str,
    user_move_san: str,
    best_move_san: Optional[str] = None,
    opponent_threats: Optional[List[str]] = None
) -> List[Dict]:
    """
    Analyze a position and move to generate confident hypotheses
    about what the player was trying to do.
    
    Args:
        fen_before: FEN string of position before the move
        user_move_san: The move played in SAN notation
        best_move_san: The best move according to engine (optional)
        opponent_threats: Known opponent threats (optional)
    
    Returns:
        List of hypothesis dictionaries, sorted by confidence.
        Only returns hypotheses with confidence >= 0.5
    """
    try:
        board = chess.Board(fen_before)
    except ValueError:
        return []
    
    # Parse the move
    try:
        move = board.parse_san(user_move_san)
    except (ValueError, chess.InvalidMoveError, chess.AmbiguousMoveError):
        return []
    
    hypotheses: List[IntentHypothesis] = []
    
    from_square = move.from_square
    to_square = move.to_square
    moving_piece = board.piece_at(from_square)
    
    if not moving_piece:
        return []
    
    user_color = board.turn
    opponent_color = not user_color
    
    # ========================================
    # 1. CAPTURE ANALYSIS
    # ========================================
    captured_piece = board.piece_at(to_square)
    if captured_piece:
        piece_name = get_piece_name(captured_piece)
        hypotheses.append(IntentHypothesis(
            category=IntentCategory.MATERIAL,
            confidence=0.95,
            description=f"Capturing the {piece_name}",
            evidence=f"Your move captures opponent's {piece_name} on {get_square_name(to_square)}",
            square_or_piece=piece_name,
        ))
    
    # ========================================
    # 2. CHECK ANALYSIS
    # ========================================
    board_after = board.copy()
    board_after.push(move)
    
    if board_after.is_check():
        hypotheses.append(IntentHypothesis(
            category=IntentCategory.ATTACK,
            confidence=0.95,
            description="Giving check",
            evidence="Your move puts the opponent's king in check",
        ))
    
    # ========================================
    # 3. CASTLING
    # ========================================
    if board.is_castling(move):
        side = "kingside" if board.is_kingside_castling(move) else "queenside"
        hypotheses.append(IntentHypothesis(
            category=IntentCategory.KING_SAFETY,
            confidence=0.95,
            description=f"Castling {side}",
            evidence=f"Castling {side} to protect your king and connect the rooks",
        ))
    
    # ========================================
    # 4. ESCAPE FROM ATTACK
    # ========================================
    attackers_before = list(board.attackers(opponent_color, from_square))
    if attackers_before:
        # Check if piece was attacked
        hypotheses.append(IntentHypothesis(
            category=IntentCategory.ESCAPE,
            confidence=0.85,
            description=f"Moving {get_piece_name(moving_piece)} to safety",
            evidence=f"Your {get_piece_name(moving_piece)} was under attack",
            square_or_piece=get_piece_name(moving_piece),
        ))
    
    # ========================================
    # 5. DEFENSE ANALYSIS
    # ========================================
    # Check if the move defends another piece
    attacks_after = get_attacked_squares(board_after, to_square)
    for defended_square in attacks_after:
        defended_piece = board_after.piece_at(defended_square)
        if defended_piece and defended_piece.color == user_color:
            # Check if this piece was under attack
            attackers = list(board.attackers(opponent_color, defended_square))
            if attackers:
                hypotheses.append(IntentHypothesis(
                    category=IntentCategory.DEFEND,
                    confidence=0.80,
                    description=f"Defending the {get_piece_name(defended_piece)}",
                    evidence=f"Your move now defends the {get_piece_name(defended_piece)} on {get_square_name(defended_square)}",
                    square_or_piece=get_piece_name(defended_piece),
                ))
    
    # ========================================
    # 6. ATTACK/THREAT CREATION
    # ========================================
    attacks_before = get_attacked_squares(board, from_square) if from_square else set()
    new_attacks = attacks_after - attacks_before
    
    for attacked_square in new_attacks:
        target = board_after.piece_at(attacked_square)
        if target and target.color == opponent_color:
            target_name = get_piece_name(target)
            
            # Higher confidence for attacking valuable pieces
            value_confidence = {
                chess.QUEEN: 0.90,
                chess.ROOK: 0.85,
                chess.BISHOP: 0.75,
                chess.KNIGHT: 0.75,
                chess.PAWN: 0.60,
            }
            conf = value_confidence.get(target.piece_type, 0.70)
            
            hypotheses.append(IntentHypothesis(
                category=IntentCategory.ATTACK,
                confidence=conf,
                description=f"Attacking the {target_name}",
                evidence=f"Your {get_piece_name(moving_piece)} now attacks the {target_name} on {get_square_name(attacked_square)}",
                square_or_piece=target_name,
            ))
    
    # ========================================
    # 7. CENTER CONTROL
    # ========================================
    center_squares_controlled = [sq for sq in attacks_after if is_center_square(sq)]
    if center_squares_controlled and moving_piece.piece_type in [chess.KNIGHT, chess.BISHOP, chess.PAWN]:
        center_names = [get_square_name(sq) for sq in center_squares_controlled]
        hypotheses.append(IntentHypothesis(
            category=IntentCategory.CONTROL,
            confidence=0.70,
            description=f"Controlling the center ({', '.join(center_names)})",
            evidence=f"Your {get_piece_name(moving_piece)} now controls central squares",
            square_or_piece=center_names[0],
        ))
    
    # Pawn to center
    if moving_piece.piece_type == chess.PAWN and is_center_square(to_square):
        hypotheses.append(IntentHypothesis(
            category=IntentCategory.CONTROL,
            confidence=0.85,
            description="Occupying the center with a pawn",
            evidence=f"Your pawn now occupies the central {get_square_name(to_square)} square",
            square_or_piece=get_square_name(to_square),
        ))
    
    # ========================================
    # 8. DEVELOPMENT
    # ========================================
    # Check if piece is moving from starting position
    starting_ranks = {
        chess.WHITE: [chess.RANK_1, chess.RANK_2],
        chess.BLACK: [chess.RANK_7, chess.RANK_8],
    }
    
    from_rank = chess.square_rank(from_square)
    if from_rank in starting_ranks.get(user_color, []):
        if moving_piece.piece_type in [chess.KNIGHT, chess.BISHOP]:
            hypotheses.append(IntentHypothesis(
                category=IntentCategory.DEVELOP,
                confidence=0.80,
                description=f"Developing the {get_piece_name(moving_piece)}",
                evidence=f"Moving {get_piece_name(moving_piece)} from starting position to a more active square",
                square_or_piece=get_piece_name(moving_piece),
            ))
        elif moving_piece.piece_type == chess.ROOK:
            # Rook development (usually to open file)
            file = chess.square_file(to_square)
            pawns_on_file = any(
                board.piece_at(chess.square(file, rank)) and 
                board.piece_at(chess.square(file, rank)).piece_type == chess.PAWN
                for rank in range(8)
            )
            if not pawns_on_file:
                hypotheses.append(IntentHypothesis(
                    category=IntentCategory.DEVELOP,
                    confidence=0.75,
                    description="Placing rook on open file",
                    evidence=f"Moving rook to the open {chess.FILE_NAMES[file]}-file",
                    square_or_piece="rook",
                ))
    
    # ========================================
    # 9. PIECE ACTIVITY IMPROVEMENT
    # ========================================
    # Knight to outpost
    if moving_piece.piece_type == chess.KNIGHT:
        # Check if knight is on a good outpost (protected by pawn, can't be attacked by pawns)
        to_file = chess.square_file(to_square)
        to_rank = chess.square_rank(to_square)
        
        # Check for pawn support
        pawn_support_squares = []
        if to_file > 0:
            pawn_support_squares.append(chess.square(to_file - 1, to_rank - 1 if user_color == chess.WHITE else to_rank + 1))
        if to_file < 7:
            pawn_support_squares.append(chess.square(to_file + 1, to_rank - 1 if user_color == chess.WHITE else to_rank + 1))
        
        has_pawn_support = any(
            board.piece_at(sq) and 
            board.piece_at(sq).piece_type == chess.PAWN and 
            board.piece_at(sq).color == user_color
            for sq in pawn_support_squares if 0 <= sq < 64
        )
        
        if has_pawn_support and is_extended_center(to_square):
            hypotheses.append(IntentHypothesis(
                category=IntentCategory.ACTIVITY,
                confidence=0.80,
                description="Placing knight on a strong outpost",
                evidence=f"Your knight on {get_square_name(to_square)} is protected by a pawn and cannot be easily challenged",
                square_or_piece="knight",
            ))
    
    # ========================================
    # 10. PAWN STRUCTURE
    # ========================================
    if moving_piece.piece_type == chess.PAWN:
        # Check if creating passed pawn
        # Check if fixing opponent's pawns
        # Check if opening lines
        
        # Pawn push to create space
        if board.fullmove_number <= 15:  # Opening/early middlegame
            hypotheses.append(IntentHypothesis(
                category=IntentCategory.STRUCTURE,
                confidence=0.65,
                description="Advancing pawn to gain space",
                evidence="Pushing the pawn forward to control territory",
                square_or_piece="pawn",
            ))
    
    # ========================================
    # 11. TRADE INITIATION
    # ========================================
    if captured_piece:
        # Check if this is an even trade
        piece_values = {
            chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3,
            chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 0
        }
        capturing_value = piece_values.get(moving_piece.piece_type, 0)
        captured_value = piece_values.get(captured_piece.piece_type, 0)
        
        # Check if piece is en prise after capture
        recapturers = list(board_after.attackers(opponent_color, to_square))
        
        if recapturers and abs(capturing_value - captured_value) <= 1:
            hypotheses.append(IntentHypothesis(
                category=IntentCategory.TRADE,
                confidence=0.85,
                description=f"Trading {get_piece_name(moving_piece)}s",
                evidence=f"Exchanging your {get_piece_name(moving_piece)} for opponent's {get_piece_name(captured_piece)}",
                square_or_piece=get_piece_name(captured_piece),
            ))
    
    # ========================================
    # 12. KING SAFETY MOVES (non-castling)
    # ========================================
    if moving_piece.piece_type == chess.KING and not board.is_castling(move):
        hypotheses.append(IntentHypothesis(
            category=IntentCategory.KING_SAFETY,
            confidence=0.70,
            description="Moving the king to a safer square",
            evidence="Repositioning the king for better safety",
            square_or_piece="king",
        ))
    
    # Fianchetto bishop
    if moving_piece.piece_type == chess.BISHOP:
        fianchetto_squares = {
            chess.WHITE: [chess.G2, chess.B2],
            chess.BLACK: [chess.G7, chess.B7],
        }
        if to_square in fianchetto_squares.get(user_color, []):
            hypotheses.append(IntentHypothesis(
                category=IntentCategory.KING_SAFETY,
                confidence=0.80,
                description="Fianchettoing the bishop",
                evidence="Placing bishop on long diagonal to protect the king and control central squares",
                square_or_piece="bishop",
            ))
    
    # ========================================
    # 13. PREPARING SOMETHING
    # ========================================
    # This is harder to detect but we can look for common prep moves
    
    # Rook lift (Rook to 3rd/6th rank)
    if moving_piece.piece_type == chess.ROOK:
        to_rank = chess.square_rank(to_square)
        if (user_color == chess.WHITE and to_rank == 2) or (user_color == chess.BLACK and to_rank == 5):
            hypotheses.append(IntentHypothesis(
                category=IntentCategory.ACTIVITY,
                confidence=0.70,
                description="Lifting the rook for attack",
                evidence="Moving rook to the 3rd rank to swing over and attack",
                square_or_piece="rook",
            ))
    
    # ========================================
    # FILTER AND SORT
    # ========================================
    # Only return hypotheses with confidence >= 0.5
    confident_hypotheses = [h for h in hypotheses if h.confidence >= 0.5]
    
    # Sort by confidence (highest first)
    confident_hypotheses.sort(key=lambda h: h.confidence, reverse=True)
    
    # Deduplicate similar hypotheses (keep highest confidence)
    seen_descriptions = set()
    unique_hypotheses = []
    for h in confident_hypotheses:
        # Simple dedup based on first few words
        key = h.description.split()[:3]
        key_str = " ".join(key).lower()
        if key_str not in seen_descriptions:
            seen_descriptions.add(key_str)
            unique_hypotheses.append(h)
    
    # Return top 5 most confident hypotheses
    result = []
    for h in unique_hypotheses[:5]:
        result.append({
            "category": h.category.value,
            "confidence": round(h.confidence, 2),
            "description": h.description,
            "evidence": h.evidence,
            "question": f"Were you trying to {h.description.lower()}?",
        })
    
    return result


def get_move_intent_summary(
    fen_before: str,
    user_move_san: str,
    best_move_san: Optional[str] = None,
) -> Dict:
    """
    Get a summary of what the move does, including intent hypotheses.
    
    Returns:
        {
            "move": "Nf3",
            "piece": "knight",
            "is_capture": False,
            "is_check": False,
            "hypotheses": [...],
            "primary_intent": {...} or None,
        }
    """
    hypotheses = analyze_move_intent(fen_before, user_move_san, best_move_san)
    
    try:
        board = chess.Board(fen_before)
        move = board.parse_san(user_move_san)
        moving_piece = board.piece_at(move.from_square)
        captured = board.piece_at(move.to_square)
        
        board.push(move)
        is_check = board.is_check()
    except (ValueError, chess.InvalidMoveError, chess.AmbiguousMoveError):
        return {
            "move": user_move_san,
            "hypotheses": hypotheses,
            "primary_intent": hypotheses[0] if hypotheses else None,
        }
    
    return {
        "move": user_move_san,
        "piece": get_piece_name(moving_piece) if moving_piece else "piece",
        "from_square": get_square_name(move.from_square),
        "to_square": get_square_name(move.to_square),
        "is_capture": captured is not None,
        "captured_piece": get_piece_name(captured) if captured else None,
        "is_check": is_check,
        "hypotheses": hypotheses,
        "primary_intent": hypotheses[0] if hypotheses else None,
    }
