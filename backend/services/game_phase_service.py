"""
Game Phase Calculator - Stockfish-Style Phase Detection

Calculates game phase as a continuous 0-100 scale based on remaining material.
NOT discrete "opening/middlegame/endgame" but a SLIDER.

Phase Values:
- Queen: 4
- Rook: 2
- Bishop: 1
- Knight: 1
- Pawn: 0
- King: 0

Max Phase = 24 (all pieces on board)
Phase decreases as pieces are traded.

Usage:
    calculator = GamePhaseCalculator()
    phase = calculator.calculate_phase(board)
    # Returns: {"phase_percent": 45, "phase_label": "middlegame", ...}
"""

import chess
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class PhaseLabel(str, Enum):
    """Game phase labels for coaching context."""
    OPENING = "opening"
    EARLY_MIDDLEGAME = "early_middlegame"
    MIDDLEGAME = "middlegame"
    LATE_MIDDLEGAME = "late_middlegame"
    EARLY_ENDGAME = "early_endgame"
    ENDGAME = "endgame"
    DEEP_ENDGAME = "deep_endgame"


class EndgameType(str, Enum):
    """Specific endgame classifications for targeted coaching."""
    # Pure pawn endgames
    KING_PAWN_VS_KING = "king_pawn_vs_king"
    PAWN_ENDGAME = "pawn_endgame"
    PAWN_RACE = "pawn_race"
    
    # Rook endgames
    ROOK_ENDGAME = "rook_endgame"
    ROOK_PAWN_VS_ROOK = "rook_pawn_vs_rook"
    ROOK_VS_PAWNS = "rook_vs_pawns"
    
    # Minor piece endgames
    BISHOP_ENDGAME = "bishop_endgame"
    KNIGHT_ENDGAME = "knight_endgame"
    BISHOP_VS_KNIGHT = "bishop_vs_knight"
    OPPOSITE_COLOR_BISHOPS = "opposite_color_bishops"
    SAME_COLOR_BISHOPS = "same_color_bishops"
    TWO_BISHOPS_VS_KNIGHT = "two_bishops_vs_knight"
    
    # Queen endgames
    QUEEN_ENDGAME = "queen_endgame"
    QUEEN_VS_ROOK = "queen_vs_rook"
    QUEEN_VS_TWO_ROOKS = "queen_vs_two_rooks"
    
    # Mixed endgames
    ROOK_AND_MINOR_VS_ROOK = "rook_and_minor_vs_rook"
    ROOK_VS_MINOR = "rook_vs_minor"
    
    # Complex/Other
    COMPLEX_ENDGAME = "complex_endgame"
    NOT_ENDGAME = "not_endgame"


@dataclass
class PhaseInfo:
    """Complete phase information for a position."""
    raw_phase: int              # 0-24 (material-based)
    endgame_weight: float       # 0.0-1.0 (0=opening, 1=endgame)
    phase_percent: int          # 0-100 (0=opening, 100=endgame)
    phase_label: PhaseLabel     # Discrete label for coaching
    opening_weight: float       # 1.0-0.0 (inverse of endgame)
    
    # Additional context
    is_in_opening_book: bool = False    # Set externally
    is_endgame: bool = False            # True if in endgame phase
    endgame_type: EndgameType = EndgameType.NOT_ENDGAME
    material_balance: int = 0           # Material balance (positive = white ahead)
    
    # Piece counts for context
    white_material: Dict[str, int] = None
    black_material: Dict[str, int] = None


class GamePhaseCalculator:
    """
    Calculates game phase as a continuous 0-100 scale.
    Based on Stockfish's phase calculation method.
    """
    
    # Phase contribution per piece type
    PHASE_VALUES = {
        chess.QUEEN: 4,
        chess.ROOK: 2,
        chess.BISHOP: 1,
        chess.KNIGHT: 1,
        chess.PAWN: 0,
        chess.KING: 0
    }
    
    # Maximum phase (all pieces on board)
    # 2 Queens (8) + 4 Rooks (8) + 4 Bishops (4) + 4 Knights (4) = 24
    MAX_PHASE = 24
    
    def calculate_phase(self, board: chess.Board) -> PhaseInfo:
        """
        Calculate comprehensive phase information for a position.
        
        Args:
            board: chess.Board object
            
        Returns:
            PhaseInfo with all phase-related data
        """
        # Count pieces and phase value
        white_material = self._count_material(board, chess.WHITE)
        black_material = self._count_material(board, chess.BLACK)
        
        # Calculate total phase value
        current_phase = 0
        for square in chess.SQUARES:
            piece = board.piece_at(square)
            if piece:
                current_phase += self.PHASE_VALUES.get(piece.piece_type, 0)
        
        # Calculate weights
        endgame_weight = (self.MAX_PHASE - current_phase) / self.MAX_PHASE
        endgame_weight = max(0.0, min(1.0, endgame_weight))  # Clamp
        phase_percent = int(endgame_weight * 100)
        opening_weight = 1.0 - endgame_weight
        
        # Determine phase label (more granular than simple 3-phase)
        phase_label = self._get_phase_label(phase_percent)
        
        # Detect endgame type if in endgame
        endgame_type = EndgameType.NOT_ENDGAME
        is_endgame = phase_percent >= 50
        if is_endgame:
            endgame_type = self._classify_endgame(board, white_material, black_material)
        
        # Calculate material balance
        piece_values = {"Q": 9, "R": 5, "B": 3, "N": 3, "P": 1}
        white_value = sum(count * piece_values.get(piece, 0) for piece, count in white_material.items())
        black_value = sum(count * piece_values.get(piece, 0) for piece, count in black_material.items())
        material_balance = white_value - black_value
        
        return PhaseInfo(
            raw_phase=current_phase,
            endgame_weight=endgame_weight,
            phase_percent=phase_percent,
            phase_label=phase_label,
            opening_weight=opening_weight,
            is_endgame=is_endgame,
            endgame_type=endgame_type,
            material_balance=material_balance,
            white_material=white_material,
            black_material=black_material
        )
    
    def _count_material(self, board: chess.Board, color: chess.Color) -> Dict[str, int]:
        """Count pieces for a color."""
        material = {
            "Q": 0, "R": 0, "B": 0, "N": 0, "P": 0
        }
        
        piece_map = {
            chess.QUEEN: "Q",
            chess.ROOK: "R",
            chess.BISHOP: "B",
            chess.KNIGHT: "N",
            chess.PAWN: "P"
        }
        
        for square in chess.SQUARES:
            piece = board.piece_at(square)
            if piece and piece.color == color:
                key = piece_map.get(piece.piece_type)
                if key:
                    material[key] += 1
        
        return material
    
    def _get_phase_label(self, phase_percent: int) -> PhaseLabel:
        """Get granular phase label from percentage."""
        if phase_percent < 15:
            return PhaseLabel.OPENING
        elif phase_percent < 30:
            return PhaseLabel.EARLY_MIDDLEGAME
        elif phase_percent < 45:
            return PhaseLabel.MIDDLEGAME
        elif phase_percent < 60:
            return PhaseLabel.LATE_MIDDLEGAME
        elif phase_percent < 75:
            return PhaseLabel.EARLY_ENDGAME
        elif phase_percent < 90:
            return PhaseLabel.ENDGAME
        else:
            return PhaseLabel.DEEP_ENDGAME
    
    def _classify_endgame(
        self, 
        board: chess.Board, 
        white: Dict[str, int], 
        black: Dict[str, int]
    ) -> EndgameType:
        """
        Classify the specific endgame type.
        Each type requires different coaching!
        """
        # Total pieces (excluding kings and pawns)
        total = {
            "Q": white["Q"] + black["Q"],
            "R": white["R"] + black["R"],
            "B": white["B"] + black["B"],
            "N": white["N"] + black["N"],
            "P": white["P"] + black["P"]
        }
        
        total_pieces = total["Q"] + total["R"] + total["B"] + total["N"]
        total_minors = total["B"] + total["N"]
        
        # ============================================
        # PAWN ENDGAMES (no pieces, only pawns)
        # ============================================
        if total_pieces == 0:
            if total["P"] == 0:
                return EndgameType.PAWN_ENDGAME  # K vs K (rare, drawn)
            elif total["P"] == 1:
                return EndgameType.KING_PAWN_VS_KING
            else:
                return EndgameType.PAWN_RACE
        
        # ============================================
        # QUEEN ENDGAMES
        # ============================================
        if total["Q"] >= 1 and total["R"] == 0 and total_minors == 0:
            if total["Q"] == 2:
                return EndgameType.QUEEN_ENDGAME
            elif total["Q"] == 1:
                return EndgameType.QUEEN_ENDGAME
        
        # Queen vs Rook
        if total["Q"] == 1 and total["R"] == 1 and total_minors == 0:
            return EndgameType.QUEEN_VS_ROOK
        
        # Queen vs Two Rooks
        if total["Q"] == 1 and total["R"] == 2 and total_minors == 0:
            return EndgameType.QUEEN_VS_TWO_ROOKS
        
        # ============================================
        # ROOK ENDGAMES
        # ============================================
        if total["R"] >= 1 and total["Q"] == 0:
            # Pure rook endgame
            if total_minors == 0:
                if total["P"] == 1:
                    return EndgameType.ROOK_PAWN_VS_ROOK
                return EndgameType.ROOK_ENDGAME
            
            # Rook + minor vs Rook
            if total["R"] == 2 and total_minors == 1:
                return EndgameType.ROOK_AND_MINOR_VS_ROOK
            
            # Rook vs minor piece
            if total["R"] == 1 and total_minors == 1:
                return EndgameType.ROOK_VS_MINOR
        
        # ============================================
        # MINOR PIECE ENDGAMES
        # ============================================
        if total["Q"] == 0 and total["R"] == 0:
            # Bishop endgames
            if total["B"] >= 1 and total["N"] == 0:
                if total["B"] == 2:
                    # Check for opposite color
                    if self._has_opposite_color_bishops(board):
                        return EndgameType.OPPOSITE_COLOR_BISHOPS
                    else:
                        return EndgameType.SAME_COLOR_BISHOPS
                return EndgameType.BISHOP_ENDGAME
            
            # Knight endgames
            if total["N"] >= 1 and total["B"] == 0:
                return EndgameType.KNIGHT_ENDGAME
            
            # Bishop vs Knight
            if total["B"] == 1 and total["N"] == 1:
                return EndgameType.BISHOP_VS_KNIGHT
            
            # Two bishops vs knight
            if total["B"] == 2 and total["N"] == 1:
                return EndgameType.TWO_BISHOPS_VS_KNIGHT
        
        # ============================================
        # COMPLEX ENDGAME (doesn't fit clean categories)
        # ============================================
        return EndgameType.COMPLEX_ENDGAME
    
    def _has_opposite_color_bishops(self, board: chess.Board) -> bool:
        """Check if the bishops are on opposite colors."""
        white_bishop_square = None
        black_bishop_square = None
        
        for square in chess.SQUARES:
            piece = board.piece_at(square)
            if piece and piece.piece_type == chess.BISHOP:
                if piece.color == chess.WHITE:
                    white_bishop_square = square
                else:
                    black_bishop_square = square
        
        if white_bishop_square is None or black_bishop_square is None:
            return False
        
        # Check square colors (light squares have (file + rank) % 2 == 0)
        white_on_light = (chess.square_file(white_bishop_square) + 
                         chess.square_rank(white_bishop_square)) % 2 == 0
        black_on_light = (chess.square_file(black_bishop_square) + 
                         chess.square_rank(black_bishop_square)) % 2 == 0
        
        return white_on_light != black_on_light


# ============================================
# ENDGAME TEACHING DATABASE
# ============================================

ENDGAME_PRINCIPLES = {
    
    EndgameType.KING_PAWN_VS_KING: {
        "name": "King + Pawn vs King",
        "difficulty": "fundamental",
        "key_concepts": [
            "Opposition - kings face each other with one square between, whoever moves loses",
            "Key squares - the squares in front of the pawn that the attacking king must control",
            "Rule of the Square - can the defending king catch the pawn?"
        ],
        "techniques": [
            "Triangulation - waste a move to give opponent the move",
            "Shoulder check - use king to push enemy king away",
            "Opposition at critical moment"
        ],
        "winning_method": "Control key squares with your king BEFORE pushing the pawn",
        "drawing_method": "Get opposition when defender, stay in the 'square' of the pawn",
        "common_mistakes": [
            "Pushing pawn too fast without king support",
            "Not understanding opposition",
            "Allowing stalemate when winning"
        ],
        "famous_examples": ["Philidor 1777"]
    },
    
    EndgameType.ROOK_ENDGAME: {
        "name": "Rook Endgame",
        "difficulty": "intermediate",
        "key_concepts": [
            "Rook belongs BEHIND passed pawns (yours OR opponent's)",
            "Active rook beats passive rook - activity is everything",
            "Cut off the enemy king from the action",
            "7th rank is paradise for rooks",
            "Rook + pawn vs Rook is usually drawn with correct defense"
        ],
        "techniques": [
            "Lucena Position - the winning technique with rook + pawn vs rook",
            "Philidor Position - the drawing technique for the defender",
            "Building a bridge - shelter your king from checks",
            "Back rank defense"
        ],
        "winning_method": "Activate your rook, cut off enemy king, push passed pawns",
        "drawing_method": "Philidor defense - keep rook on 3rd rank, then check from behind",
        "common_mistakes": [
            "Passive rook defending from the side",
            "Not activating king early enough",
            "Trading into lost pawn endgame",
            "Not knowing Lucena/Philidor positions"
        ],
        "famous_examples": ["Lucena 1497", "Philidor 1777", "Capablanca's technique"]
    },
    
    EndgameType.OPPOSITE_COLOR_BISHOPS: {
        "name": "Opposite Color Bishops",
        "difficulty": "intermediate",
        "key_concepts": [
            "Often DRAWN even with 1-2 extra pawns!",
            "Your bishop can never attack their pawns (different colors)",
            "Attacker needs pawns on BOTH sides of the board",
            "Defender should blockade pawns on squares of their bishop"
        ],
        "techniques": [
            "Fortress - create an unbreakable blockade",
            "Two weaknesses principle - attack both flanks",
            "Wrong rook pawn - some positions are drawn regardless"
        ],
        "winning_method": "Create passed pawns on BOTH sides, stretch the defense",
        "drawing_method": "Set up fortress, blockade on your bishop's color",
        "common_mistakes": [
            "Assuming extra pawn wins easily",
            "Not creating second weakness when attacking",
            "Giving up bishop for wrong reasons"
        ],
        "famous_examples": ["Many GM draws from won positions"]
    },
    
    EndgameType.BISHOP_VS_KNIGHT: {
        "name": "Bishop vs Knight",
        "difficulty": "intermediate",
        "key_concepts": [
            "Bishop is better in OPEN positions (long diagonals)",
            "Knight is better in CLOSED positions (can jump over pawns)",
            "Bishop can control both sides simultaneously",
            "Knight needs outposts (protected squares)"
        ],
        "techniques": [
            "If you have bishop: open the position, don't let pawns get blocked",
            "If you have knight: keep pawns fixed, find strong outpost squares"
        ],
        "winning_method": "Exploit the advantage of your piece type",
        "common_mistakes": [
            "Not adjusting pawn structure to your piece",
            "Trading into worse endgame",
            "Placing pawns on same color as your bishop"
        ],
        "famous_examples": ["Capablanca's technique games"]
    },
    
    EndgameType.PAWN_RACE: {
        "name": "Pawn Race",
        "difficulty": "fundamental",
        "key_concepts": [
            "COUNT THE MOVES - who queens first?",
            "Can you queen WITH CHECK? (huge advantage)",
            "After both queen, who has the better queen position?",
            "Sometimes you queen but still lose!"
        ],
        "techniques": [
            "Precise counting of tempi",
            "Checking distance with king",
            "Queen + pawn vs Queen technique"
        ],
        "winning_method": "Queen first, or queen with check, or get better queen position",
        "common_mistakes": [
            "Miscounting by one move",
            "Forgetting about checks after queening",
            "Not considering queen vs queen position"
        ]
    },
    
    EndgameType.QUEEN_ENDGAME: {
        "name": "Queen Endgame",
        "difficulty": "advanced",
        "key_concepts": [
            "Perpetual check is always a resource",
            "King safety matters even in endgame",
            "Queen + pawn vs Queen is very difficult to win",
            "Centralized queen is powerful"
        ],
        "techniques": [
            "Setting up perpetual check threats",
            "Using checks to gain tempo for pawn advance",
            "Shelter your king while attacking"
        ],
        "common_mistakes": [
            "Allowing perpetual check when winning",
            "King too exposed",
            "Trading queens into lost pawn endgame"
        ]
    },
    
    EndgameType.KNIGHT_ENDGAME: {
        "name": "Knight Endgame",
        "difficulty": "intermediate",
        "key_concepts": [
            "Knight is SHORT-RANGE - takes time to cross board",
            "Knight can't lose tempo (always changes square color)",
            "Outposts are critical for knights",
            "Knight struggles against passed rook pawns"
        ],
        "techniques": [
            "Centralize knight",
            "Create outpost squares",
            "Avoid passed rook pawns if you have knight"
        ],
        "common_mistakes": [
            "Knight stuck on edge of board",
            "Not using king actively",
            "Allowing passed rook pawn"
        ]
    },
    
    EndgameType.COMPLEX_ENDGAME: {
        "name": "Complex Endgame",
        "difficulty": "advanced",
        "key_concepts": [
            "Activity is usually more important than material",
            "King activation is critical",
            "Create passed pawns",
            "Coordinate your pieces"
        ],
        "techniques": [
            "Calculate concrete variations",
            "Look for simplification to known endgame types"
        ]
    }
}


# ============================================
# PHASE-SPECIFIC COACHING PRIORITIES
# ============================================

PHASE_COACHING = {
    
    PhaseLabel.OPENING: {
        "priorities": [
            "Develop pieces toward the center",
            "Control central squares (e4, d4, e5, d5)",
            "Castle early for king safety",
            "Don't move the same piece twice",
            "Connect your rooks"
        ],
        "avoid": [
            "Moving pawns too much",
            "Bringing queen out early",
            "Neglecting development for attacks",
            "Moving edge pawns (a, h) without reason"
        ],
        "weights": {
            "king_safety": 1.0,
            "development": 1.0,
            "center_control": 0.9,
            "king_activity": 0.0,
            "pawn_structure": 0.5
        }
    },
    
    PhaseLabel.EARLY_MIDDLEGAME: {
        "priorities": [
            "Complete development if not done",
            "Formulate a plan based on pawn structure",
            "Improve worst-placed piece",
            "Look for tactical opportunities"
        ],
        "weights": {
            "king_safety": 0.9,
            "development": 0.7,
            "tactics": 0.8,
            "piece_activity": 0.8,
            "king_activity": 0.1
        }
    },
    
    PhaseLabel.MIDDLEGAME: {
        "priorities": [
            "Tactics - look for forks, pins, skewers every move",
            "Piece activity - no piece should be passive",
            "Pawn structure - don't create unnecessary weaknesses",
            "Attack weaknesses in opponent's position",
            "Create threats"
        ],
        "weights": {
            "king_safety": 0.8,
            "tactics": 1.0,
            "piece_activity": 0.9,
            "pawn_structure": 0.7,
            "king_activity": 0.2
        }
    },
    
    PhaseLabel.LATE_MIDDLEGAME: {
        "priorities": [
            "Consider pawn structure for upcoming endgame",
            "Create passed pawns if possible",
            "Trade pieces if ahead in material",
            "Keep pieces if attacking"
        ],
        "weights": {
            "king_safety": 0.6,
            "tactics": 0.9,
            "piece_activity": 0.8,
            "pawn_structure": 0.8,
            "king_activity": 0.4
        }
    },
    
    PhaseLabel.EARLY_ENDGAME: {
        "priorities": [
            "Activate your king! It's a fighting piece now",
            "Create or support passed pawns",
            "Improve piece activity",
            "Calculate pawn races"
        ],
        "weights": {
            "king_safety": 0.4,
            "king_activity": 0.8,
            "passed_pawns": 0.8,
            "piece_activity": 0.8
        }
    },
    
    PhaseLabel.ENDGAME: {
        "priorities": [
            "King activity is CRITICAL",
            "Passed pawns - create and push them",
            "Rooks belong behind passed pawns",
            "Calculate precisely"
        ],
        "weights": {
            "king_safety": 0.2,
            "king_activity": 1.0,
            "passed_pawns": 1.0,
            "piece_activity": 0.8
        }
    },
    
    PhaseLabel.DEEP_ENDGAME: {
        "priorities": [
            "Know your theoretical positions (Lucena, Philidor, etc.)",
            "Opposition in pawn endgames",
            "Precise calculation is everything",
            "Watch for stalemate tricks"
        ],
        "weights": {
            "king_activity": 1.0,
            "passed_pawns": 1.0,
            "technique": 1.0
        }
    }
}


def get_phase_coaching(phase_info: PhaseInfo) -> Dict:
    """
    Get appropriate coaching content for the current phase.
    
    Args:
        phase_info: PhaseInfo object from calculate_phase()
        
    Returns:
        Dict with coaching priorities, weights, and endgame info if applicable
    """
    coaching = PHASE_COACHING.get(phase_info.phase_label, {})
    
    result = {
        "phase_percent": phase_info.phase_percent,
        "phase_label": phase_info.phase_label.value,
        "priorities": coaching.get("priorities", []),
        "avoid": coaching.get("avoid", []),
        "weights": coaching.get("weights", {})
    }
    
    # Add endgame-specific coaching if in endgame
    if phase_info.phase_percent >= 50 and phase_info.endgame_type != EndgameType.NOT_ENDGAME:
        endgame_coaching = ENDGAME_PRINCIPLES.get(phase_info.endgame_type, {})
        result["endgame_type"] = phase_info.endgame_type.value
        result["endgame_name"] = endgame_coaching.get("name", "Complex Endgame")
        result["endgame_concepts"] = endgame_coaching.get("key_concepts", [])
        result["endgame_techniques"] = endgame_coaching.get("techniques", [])
        result["endgame_mistakes"] = endgame_coaching.get("common_mistakes", [])
        result["winning_method"] = endgame_coaching.get("winning_method", "")
        result["drawing_method"] = endgame_coaching.get("drawing_method", "")
    
    return result



# Convenience function for backward compatibility
def get_game_phase(fen_or_board) -> Dict:
    """
    Get game phase information from a FEN string or chess.Board.
    
    Convenience wrapper around GamePhaseCalculator.
    
    Args:
        fen_or_board: FEN string or chess.Board object
        
    Returns:
        Dict with phase_label, phase_percent, is_endgame, etc.
    """
    import chess
    
    if isinstance(fen_or_board, str):
        board = chess.Board(fen_or_board)
    else:
        board = fen_or_board
    
    calculator = GamePhaseCalculator()
    phase_info = calculator.calculate_phase(board)
    
    return {
        "phase_label": phase_info.phase_label.value,
        "phase_percent": phase_info.phase_percent,
        "is_endgame": phase_info.is_endgame,
        "endgame_type": phase_info.endgame_type.value if phase_info.endgame_type else None,
        "material_balance": phase_info.material_balance
    }
