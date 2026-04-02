"""
Advanced Chess Brain Detectors
==============================

This module contains:
1. Additional Strategic Detectors (15 new)
2. Endgame Concept Detectors (8 new)
3. Concept Hierarchy/Graph for teaching depth

These extend the base detectors in detector_registry.py
"""

import chess
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

from .detector_registry import DetectorResult
from .enums import StrategicConcept, MistakeCategory, GamePhase

logger = logging.getLogger(__name__)


# ==============================================================================
# CONCEPT HIERARCHY / GRAPH
# ==============================================================================

@dataclass
class ConceptNode:
    """A node in the concept hierarchy graph."""
    name: str
    parent: Optional[str] = None
    children: List[str] = field(default_factory=list)
    clarity_score: float = 0.5  # How easy is this concept to see/understand (0-1)
    teaching_priority: int = 50  # Base priority for lesson selection
    prerequisites: List[str] = field(default_factory=list)  # Concepts to learn first
    related: List[str] = field(default_factory=list)  # Related concepts


class ConceptGraph:
    """
    The Concept Graph organizes ~80 chess concepts into a teachable hierarchy.
    
    This enables:
    1. Teaching at the right level of abstraction
    2. Building from simple to complex concepts
    3. Relating similar patterns together
    """
    
    def __init__(self):
        self.nodes: Dict[str, ConceptNode] = {}
        self._build_graph()
    
    def _build_graph(self):
        """Build the complete concept hierarchy."""
        
        # === TACTICAL CONCEPTS (Root: "tactics") ===
        self._add_node("tactics", clarity_score=0.9, teaching_priority=90)
        
        # Fork hierarchy
        self._add_node("fork", parent="tactics", clarity_score=0.85, teaching_priority=85,
                      children=["knight_fork", "queen_fork", "pawn_fork", "bishop_fork", "rook_fork"])
        self._add_node("knight_fork", parent="fork", clarity_score=0.9, teaching_priority=90,
                      related=["outpost", "centralization"])
        self._add_node("queen_fork", parent="fork", clarity_score=0.85, teaching_priority=80)
        self._add_node("pawn_fork", parent="fork", clarity_score=0.95, teaching_priority=85)
        self._add_node("bishop_fork", parent="fork", clarity_score=0.8, teaching_priority=75)
        self._add_node("rook_fork", parent="fork", clarity_score=0.75, teaching_priority=70)
        
        # Pin hierarchy
        self._add_node("pin", parent="tactics", clarity_score=0.8, teaching_priority=85,
                      children=["absolute_pin", "relative_pin"])
        self._add_node("absolute_pin", parent="pin", clarity_score=0.85, teaching_priority=90,
                      related=["king_safety"])
        self._add_node("relative_pin", parent="pin", clarity_score=0.7, teaching_priority=75)
        
        # Skewer hierarchy
        self._add_node("skewer", parent="tactics", clarity_score=0.75, teaching_priority=80,
                      prerequisites=["pin"])
        
        # Discovery hierarchy
        self._add_node("discovery", parent="tactics", clarity_score=0.7, teaching_priority=80,
                      children=["discovered_attack", "discovered_check", "double_check"])
        self._add_node("discovered_attack", parent="discovery", clarity_score=0.75, teaching_priority=75)
        self._add_node("discovered_check", parent="discovery", clarity_score=0.8, teaching_priority=85)
        self._add_node("double_check", parent="discovery", clarity_score=0.85, teaching_priority=90,
                      related=["checkmate_patterns"])
        
        # Removal of defender
        self._add_node("removal_of_defender", parent="tactics", clarity_score=0.65, teaching_priority=75,
                      children=["capture_defender", "deflection", "decoy"],
                      prerequisites=["hanging_piece"])
        self._add_node("capture_defender", parent="removal_of_defender", clarity_score=0.8, teaching_priority=80)
        self._add_node("deflection", parent="removal_of_defender", clarity_score=0.6, teaching_priority=70)
        self._add_node("decoy", parent="removal_of_defender", clarity_score=0.55, teaching_priority=65)
        
        # Overloading
        self._add_node("overload", parent="tactics", clarity_score=0.6, teaching_priority=70,
                      prerequisites=["piece_coordination"])
        
        # Back rank
        self._add_node("back_rank", parent="tactics", clarity_score=0.85, teaching_priority=90,
                      related=["king_safety", "rook_activity"])
        
        # Hanging pieces
        self._add_node("hanging_piece", parent="tactics", clarity_score=0.95, teaching_priority=95)
        self._add_node("trapped_piece", parent="tactics", clarity_score=0.8, teaching_priority=85)
        
        # === STRATEGIC CONCEPTS (Root: "strategy") ===
        self._add_node("strategy", clarity_score=0.6, teaching_priority=70)
        
        # Pawn structure hierarchy
        self._add_node("pawn_structure", parent="strategy", clarity_score=0.7, teaching_priority=75,
                      children=["isolated_pawn", "doubled_pawns", "backward_pawn", 
                               "passed_pawn", "pawn_chain", "pawn_majority", "pawn_islands"])
        self._add_node("isolated_pawn", parent="pawn_structure", clarity_score=0.8, teaching_priority=80,
                      related=["weak_squares", "outpost"])
        self._add_node("doubled_pawns", parent="pawn_structure", clarity_score=0.85, teaching_priority=75)
        self._add_node("backward_pawn", parent="pawn_structure", clarity_score=0.65, teaching_priority=70)
        self._add_node("passed_pawn", parent="pawn_structure", clarity_score=0.85, teaching_priority=90,
                      related=["endgame_technique"])
        self._add_node("pawn_chain", parent="pawn_structure", clarity_score=0.7, teaching_priority=65)
        self._add_node("pawn_majority", parent="pawn_structure", clarity_score=0.75, teaching_priority=70,
                      related=["passed_pawn"])
        self._add_node("pawn_islands", parent="pawn_structure", clarity_score=0.7, teaching_priority=60)
        
        # Piece placement hierarchy
        self._add_node("piece_placement", parent="strategy", clarity_score=0.65, teaching_priority=70,
                      children=["outpost", "bad_bishop", "good_bishop", "rook_activity", 
                               "centralization", "piece_coordination"])
        self._add_node("outpost", parent="piece_placement", clarity_score=0.75, teaching_priority=80,
                      prerequisites=["isolated_pawn", "weak_squares"])
        self._add_node("bad_bishop", parent="piece_placement", clarity_score=0.7, teaching_priority=75)
        self._add_node("good_bishop", parent="piece_placement", clarity_score=0.7, teaching_priority=70)
        self._add_node("rook_activity", parent="piece_placement", clarity_score=0.8, teaching_priority=85,
                      children=["open_file", "seventh_rank", "rook_lift"])
        self._add_node("open_file", parent="rook_activity", clarity_score=0.85, teaching_priority=85)
        self._add_node("seventh_rank", parent="rook_activity", clarity_score=0.8, teaching_priority=80)
        self._add_node("rook_lift", parent="rook_activity", clarity_score=0.6, teaching_priority=60)
        self._add_node("centralization", parent="piece_placement", clarity_score=0.85, teaching_priority=80)
        self._add_node("piece_coordination", parent="piece_placement", clarity_score=0.55, teaching_priority=65)
        
        # Positional themes
        self._add_node("positional_themes", parent="strategy", clarity_score=0.5, teaching_priority=60,
                      children=["space_advantage", "weak_squares", "king_safety", "prophylaxis"])
        self._add_node("space_advantage", parent="positional_themes", clarity_score=0.65, teaching_priority=70)
        self._add_node("weak_squares", parent="positional_themes", clarity_score=0.6, teaching_priority=75,
                      related=["outpost", "bad_bishop"])
        self._add_node("king_safety", parent="positional_themes", clarity_score=0.85, teaching_priority=90)
        self._add_node("prophylaxis", parent="positional_themes", clarity_score=0.4, teaching_priority=55,
                      prerequisites=["piece_coordination", "weak_squares"])
        
        # Planning
        self._add_node("planning", parent="strategy", clarity_score=0.45, teaching_priority=55,
                      children=["pawn_break", "minority_attack", "piece_exchange"])
        self._add_node("pawn_break", parent="planning", clarity_score=0.6, teaching_priority=65)
        self._add_node("minority_attack", parent="planning", clarity_score=0.5, teaching_priority=55)
        self._add_node("piece_exchange", parent="planning", clarity_score=0.65, teaching_priority=60)
        
        # === ENDGAME CONCEPTS (Root: "endgame") ===
        self._add_node("endgame", clarity_score=0.7, teaching_priority=75)
        
        # King and pawn endgames
        self._add_node("king_pawn_endgame", parent="endgame", clarity_score=0.75, teaching_priority=85,
                      children=["opposition", "key_squares", "triangulation", "zugzwang"])
        self._add_node("opposition", parent="king_pawn_endgame", clarity_score=0.8, teaching_priority=90)
        self._add_node("key_squares", parent="king_pawn_endgame", clarity_score=0.7, teaching_priority=80)
        self._add_node("triangulation", parent="king_pawn_endgame", clarity_score=0.55, teaching_priority=65,
                      prerequisites=["opposition"])
        self._add_node("zugzwang", parent="king_pawn_endgame", clarity_score=0.6, teaching_priority=70)
        
        # Rook endgames
        self._add_node("rook_endgame", parent="endgame", clarity_score=0.65, teaching_priority=80,
                      children=["lucena", "philidor", "rook_behind_passer", "active_king"])
        self._add_node("lucena", parent="rook_endgame", clarity_score=0.7, teaching_priority=85)
        self._add_node("philidor", parent="rook_endgame", clarity_score=0.7, teaching_priority=85)
        self._add_node("rook_behind_passer", parent="rook_endgame", clarity_score=0.8, teaching_priority=80)
        self._add_node("active_king", parent="rook_endgame", clarity_score=0.85, teaching_priority=90,
                      related=["king_activity"])
        
        # Other endgames
        self._add_node("bishop_endgame", parent="endgame", clarity_score=0.6, teaching_priority=70,
                      children=["opposite_bishops", "same_color_bishops"])
        self._add_node("opposite_bishops", parent="bishop_endgame", clarity_score=0.75, teaching_priority=75)
        self._add_node("same_color_bishops", parent="bishop_endgame", clarity_score=0.65, teaching_priority=65)
        
        self._add_node("knight_endgame", parent="endgame", clarity_score=0.6, teaching_priority=65)
        
        # Fortress concept
        self._add_node("fortress", parent="endgame", clarity_score=0.5, teaching_priority=60)
        
        # Outside passed pawn
        self._add_node("outside_passed_pawn", parent="endgame", clarity_score=0.75, teaching_priority=80,
                      related=["passed_pawn"])
        
        # === OPENING PRINCIPLES (Root: "opening") ===
        self._add_node("opening", clarity_score=0.85, teaching_priority=80)
        
        self._add_node("development", parent="opening", clarity_score=0.9, teaching_priority=90,
                      children=["develop_knights_before_bishops", "dont_move_same_piece_twice",
                               "castle_early", "connect_rooks"])
        self._add_node("develop_knights_before_bishops", parent="development", clarity_score=0.85)
        self._add_node("dont_move_same_piece_twice", parent="development", clarity_score=0.9)
        self._add_node("castle_early", parent="development", clarity_score=0.95, teaching_priority=95)
        self._add_node("connect_rooks", parent="development", clarity_score=0.8)
        
        self._add_node("center_control", parent="opening", clarity_score=0.85, teaching_priority=90)
        self._add_node("piece_activity", parent="opening", clarity_score=0.8, teaching_priority=80)
    
    def _add_node(self, name: str, parent: str = None, clarity_score: float = 0.5,
                  teaching_priority: int = 50, children: List[str] = None,
                  prerequisites: List[str] = None, related: List[str] = None):
        """Add a concept node to the graph."""
        self.nodes[name] = ConceptNode(
            name=name,
            parent=parent,
            children=children or [],
            clarity_score=clarity_score,
            teaching_priority=teaching_priority,
            prerequisites=prerequisites or [],
            related=related or []
        )
    
    def get_concept(self, name: str) -> Optional[ConceptNode]:
        """Get a concept by name."""
        return self.nodes.get(name)
    
    def get_parent_chain(self, name: str) -> List[str]:
        """Get all ancestors of a concept."""
        chain = []
        current = name
        while current:
            node = self.nodes.get(current)
            if node and node.parent:
                chain.append(node.parent)
                current = node.parent
            else:
                break
        return chain
    
    def get_children(self, name: str) -> List[str]:
        """Get direct children of a concept."""
        node = self.nodes.get(name)
        return node.children if node else []
    
    def get_related(self, name: str) -> List[str]:
        """Get related concepts."""
        node = self.nodes.get(name)
        return node.related if node else []
    
    def get_teaching_order(self, concepts: List[str]) -> List[str]:
        """
        Sort concepts by teaching order (prerequisites first, then clarity).
        Used to determine which concept to teach first.
        """
        # Score each concept
        def score(name):
            node = self.nodes.get(name)
            if not node:
                return 0
            # Higher clarity = easier to teach first
            # Higher priority = more important
            return node.clarity_score * 0.6 + (node.teaching_priority / 100) * 0.4
        
        return sorted(concepts, key=score, reverse=True)


# Create global instance
CONCEPT_GRAPH = ConceptGraph()


# ==============================================================================
# ADDITIONAL STRATEGIC DETECTORS
# ==============================================================================

def detect_doubled_pawns(
    board: chess.Board,
    user_move: str,
    best_move: str,
    context: Dict[str, Any]
) -> DetectorResult:
    """Detect doubled pawns and their strategic implications."""
    result = DetectorResult(
        detector_id="doubled_pawns_detector",
        detected=False,
        pattern_type=StrategicConcept.DOUBLED_PAWNS.value,
        category=MistakeCategory.STRATEGIC.value
    )
    
    try:
        move = board.parse_san(user_move)
        board_after = board.copy()
        board_after.push(move)
        
        user_color = not board_after.turn
        
        # Find doubled pawns for user
        doubled_files = []
        
        for file_idx in range(8):
            pawns_on_file = 0
            pawn_ranks = []
            
            for rank_idx in range(8):
                sq = chess.square(file_idx, rank_idx)
                piece = board_after.piece_at(sq)
                if piece and piece.piece_type == chess.PAWN and piece.color == user_color:
                    pawns_on_file += 1
                    pawn_ranks.append(rank_idx)
            
            if pawns_on_file >= 2:
                doubled_files.append({
                    "file": chess.FILE_NAMES[file_idx],
                    "count": pawns_on_file,
                    "ranks": pawn_ranks
                })
        
        if doubled_files:
            result.detected = True
            result.confidence = min(0.9, 0.5 + len(doubled_files) * 0.2)
            result.details = {
                "doubled_files": doubled_files,
                "total_doubled": sum(d["count"] - 1 for d in doubled_files)
            }
            result.teaching_hook = "Doubled pawns are weak - they can't protect each other"
            result.key_squares = [f"{d['file']}2" for d in doubled_files]  # Simplified
    
    except Exception as e:
        logger.debug(f"Doubled pawns detection error: {e}")
    
    return result


def detect_backward_pawn(
    board: chess.Board,
    user_move: str,
    best_move: str,
    context: Dict[str, Any]
) -> DetectorResult:
    """Detect backward pawns - pawns that can't be supported by other pawns."""
    result = DetectorResult(
        detector_id="backward_pawn_detector",
        detected=False,
        pattern_type=StrategicConcept.BACKWARD_PAWN.value,
        category=MistakeCategory.STRATEGIC.value
    )
    
    try:
        move = board.parse_san(user_move)
        board_after = board.copy()
        board_after.push(move)
        
        user_color = not board_after.turn
        backward_pawns = []
        
        for sq in chess.SQUARES:
            piece = board_after.piece_at(sq)
            if piece and piece.piece_type == chess.PAWN and piece.color == user_color:
                file = chess.square_file(sq)
                rank = chess.square_rank(sq)
                
                # Check adjacent files for supporting pawns
                has_support = False
                for adj_file in [file - 1, file + 1]:
                    if 0 <= adj_file <= 7:
                        # Look for pawns that could support (same rank or behind)
                        for check_rank in range(rank + 1 if user_color == chess.WHITE else 0, 
                                                8 if user_color == chess.WHITE else rank):
                            check_sq = chess.square(adj_file, check_rank)
                            check_piece = board_after.piece_at(check_sq)
                            if check_piece and check_piece.piece_type == chess.PAWN and check_piece.color == user_color:
                                has_support = True
                                break
                    if has_support:
                        break
                
                # Check if the square in front is controlled by enemy pawn
                front_rank = rank + 1 if user_color == chess.WHITE else rank - 1
                if 0 <= front_rank <= 7:
                    blocked_by_enemy = False
                    for adj_file in [file - 1, file + 1]:
                        if 0 <= adj_file <= 7:
                            control_sq = chess.square(adj_file, front_rank)
                            control_piece = board_after.piece_at(control_sq)
                            if control_piece and control_piece.piece_type == chess.PAWN and control_piece.color != user_color:
                                blocked_by_enemy = True
                    
                    if not has_support and blocked_by_enemy:
                        backward_pawns.append({
                            "square": chess.square_name(sq),
                            "file": chess.FILE_NAMES[file]
                        })
        
        if backward_pawns:
            result.detected = True
            result.confidence = 0.7
            result.details = {"backward_pawns": backward_pawns}
            result.key_squares = [p["square"] for p in backward_pawns]
            result.teaching_hook = "Backward pawns are targets - they can't advance safely"
    
    except Exception as e:
        logger.debug(f"Backward pawn detection error: {e}")
    
    return result


def detect_bad_bishop(
    board: chess.Board,
    user_move: str,
    best_move: str,
    context: Dict[str, Any]
) -> DetectorResult:
    """Detect bad bishops - bishops blocked by their own pawns."""
    result = DetectorResult(
        detector_id="bad_bishop_detector",
        detected=False,
        pattern_type=StrategicConcept.BAD_BISHOP.value,
        category=MistakeCategory.STRATEGIC.value
    )
    
    try:
        move = board.parse_san(user_move)
        board_after = board.copy()
        board_after.push(move)
        
        user_color = not board_after.turn
        
        # Find user's bishops
        for sq in chess.SQUARES:
            piece = board_after.piece_at(sq)
            if piece and piece.piece_type == chess.BISHOP and piece.color == user_color:
                # Determine bishop color (light or dark squares)
                bishop_on_light = (chess.square_file(sq) + chess.square_rank(sq)) % 2 == 1
                
                # Count pawns on same color squares
                pawns_blocking = 0
                total_pawns = 0
                
                for pawn_sq in chess.SQUARES:
                    pawn_piece = board_after.piece_at(pawn_sq)
                    if pawn_piece and pawn_piece.piece_type == chess.PAWN and pawn_piece.color == user_color:
                        total_pawns += 1
                        pawn_on_light = (chess.square_file(pawn_sq) + chess.square_rank(pawn_sq)) % 2 == 1
                        if pawn_on_light == bishop_on_light:
                            pawns_blocking += 1
                
                if total_pawns > 0 and pawns_blocking >= 3:  # At least 3 pawns blocking
                    result.detected = True
                    result.confidence = min(0.9, 0.5 + pawns_blocking * 0.1)
                    result.details = {
                        "bishop_square": chess.square_name(sq),
                        "bishop_on_light": bishop_on_light,
                        "pawns_blocking": pawns_blocking,
                        "total_pawns": total_pawns
                    }
                    result.key_squares = [chess.square_name(sq)]
                    result.teaching_hook = "This bishop is blocked by its own pawns"
                    break
    
    except Exception as e:
        logger.debug(f"Bad bishop detection error: {e}")
    
    return result


def detect_space_advantage(
    board: chess.Board,
    user_move: str,
    best_move: str,
    context: Dict[str, Any]
) -> DetectorResult:
    """Detect space advantage based on pawn placement and controlled squares."""
    result = DetectorResult(
        detector_id="space_advantage_detector",
        detected=False,
        pattern_type=StrategicConcept.SPACE_ADVANTAGE.value,
        category=MistakeCategory.STRATEGIC.value
    )
    
    try:
        move = board.parse_san(user_move)
        board_after = board.copy()
        board_after.push(move)
        
        user_color = not board_after.turn
        
        # Calculate space for both sides
        # Space = squares controlled beyond the 4th rank
        user_space = 0
        opp_space = 0
        
        for sq in chess.SQUARES:
            rank = chess.square_rank(sq)
            
            # Count pawns advanced beyond 4th rank
            piece = board_after.piece_at(sq)
            if piece and piece.piece_type == chess.PAWN:
                if piece.color == chess.WHITE:
                    if rank >= 4:  # 5th rank or beyond
                        if piece.color == user_color:
                            user_space += 1
                        else:
                            opp_space += 1
                else:
                    if rank <= 3:  # 4th rank or beyond for black
                        if piece.color == user_color:
                            user_space += 1
                        else:
                            opp_space += 1
        
        # Also count controlled central squares
        central_squares = [chess.D4, chess.D5, chess.E4, chess.E5, 
                         chess.C4, chess.C5, chess.F4, chess.F5]
        
        for sq in central_squares:
            user_controls = board_after.is_attacked_by(user_color, sq)
            opp_controls = board_after.is_attacked_by(not user_color, sq)
            if user_controls and not opp_controls:
                user_space += 0.5
            elif opp_controls and not user_controls:
                opp_space += 0.5
        
        space_diff = user_space - opp_space
        
        if abs(space_diff) >= 2:
            result.detected = True
            result.confidence = min(0.9, 0.5 + abs(space_diff) * 0.1)
            result.details = {
                "user_space": user_space,
                "opponent_space": opp_space,
                "advantage": "user" if space_diff > 0 else "opponent",
                "magnitude": abs(space_diff)
            }
            if space_diff > 0:
                result.teaching_hook = "You have a space advantage - pieces have more room!"
            else:
                result.teaching_hook = "Opponent has more space - look for pawn breaks"
    
    except Exception as e:
        logger.debug(f"Space advantage detection error: {e}")
    
    return result


def detect_weak_squares(
    board: chess.Board,
    user_move: str,
    best_move: str,
    context: Dict[str, Any]
) -> DetectorResult:
    """Detect weak squares that can't be defended by pawns."""
    result = DetectorResult(
        detector_id="weak_squares_detector",
        detected=False,
        pattern_type=StrategicConcept.WEAK_SQUARES.value,
        category=MistakeCategory.STRATEGIC.value
    )
    
    try:
        move = board.parse_san(user_move)
        board_after = board.copy()
        board_after.push(move)
        
        user_color = not board_after.turn
        opp_color = not user_color
        
        # Find weak squares in user's camp (can't be defended by pawns)
        weak_squares = []
        
        # Focus on squares in user's half
        check_ranks = range(4) if user_color == chess.WHITE else range(4, 8)
        
        for sq in chess.SQUARES:
            if chess.square_rank(sq) not in check_ranks:
                continue
            
            file = chess.square_file(sq)
            rank = chess.square_rank(sq)
            
            # Check if any user pawn can defend this square
            can_defend = False
            
            for adj_file in [file - 1, file + 1]:
                if 0 <= adj_file <= 7:
                    # For white, pawns defend from below; for black, from above
                    if user_color == chess.WHITE:
                        check_ranks_for_pawn = range(0, rank)
                    else:
                        check_ranks_for_pawn = range(rank + 1, 8)
                    
                    for pawn_rank in check_ranks_for_pawn:
                        pawn_sq = chess.square(adj_file, pawn_rank)
                        piece = board_after.piece_at(pawn_sq)
                        if piece and piece.piece_type == chess.PAWN and piece.color == user_color:
                            can_defend = True
                            break
                if can_defend:
                    break
            
            # If opponent attacks it and we can't pawn-defend, it's weak
            if not can_defend and board_after.is_attacked_by(opp_color, sq):
                weak_squares.append(chess.square_name(sq))
        
        if len(weak_squares) >= 2:
            result.detected = True
            result.confidence = min(0.85, 0.5 + len(weak_squares) * 0.1)
            result.details = {"weak_squares": weak_squares[:5]}  # Limit to 5
            result.key_squares = weak_squares[:3]
            result.teaching_hook = "These squares can't be defended by pawns - they're targets"
    
    except Exception as e:
        logger.debug(f"Weak squares detection error: {e}")
    
    return result


def detect_open_file(
    board: chess.Board,
    user_move: str,
    best_move: str,
    context: Dict[str, Any]
) -> DetectorResult:
    """Detect open and semi-open files and their control."""
    result = DetectorResult(
        detector_id="open_file_detector",
        detected=False,
        pattern_type=StrategicConcept.OPEN_FILE.value,
        category=MistakeCategory.STRATEGIC.value
    )
    
    try:
        move = board.parse_san(user_move)
        board_after = board.copy()
        board_after.push(move)
        
        user_color = not board_after.turn
        
        open_files = []
        semi_open_files = []
        
        for file_idx in range(8):
            user_pawns = 0
            opp_pawns = 0
            user_rook_on_file = False
            opp_rook_on_file = False
            
            for rank_idx in range(8):
                sq = chess.square(file_idx, rank_idx)
                piece = board_after.piece_at(sq)
                if piece:
                    if piece.piece_type == chess.PAWN:
                        if piece.color == user_color:
                            user_pawns += 1
                        else:
                            opp_pawns += 1
                    elif piece.piece_type == chess.ROOK:
                        if piece.color == user_color:
                            user_rook_on_file = True
                        else:
                            opp_rook_on_file = True
            
            file_name = chess.FILE_NAMES[file_idx]
            
            if user_pawns == 0 and opp_pawns == 0:
                open_files.append({
                    "file": file_name,
                    "user_rook": user_rook_on_file,
                    "opp_rook": opp_rook_on_file
                })
            elif user_pawns == 0 and opp_pawns > 0:
                semi_open_files.append({
                    "file": file_name,
                    "user_rook": user_rook_on_file,
                    "target": True
                })
        
        if open_files or semi_open_files:
            result.detected = True
            result.confidence = 0.75
            result.details = {
                "open_files": open_files,
                "semi_open_files": semi_open_files
            }
            
            # Check if rooks are using the open files
            unused_open = [f for f in open_files if not f["user_rook"]]
            if unused_open:
                result.teaching_hook = f"The {unused_open[0]['file']}-file is open - put a rook there!"
            elif semi_open_files:
                result.teaching_hook = "Use semi-open files to attack opponent's pawns"
            else:
                result.teaching_hook = "Control the open file with your rook"
    
    except Exception as e:
        logger.debug(f"Open file detection error: {e}")
    
    return result


def detect_seventh_rank(
    board: chess.Board,
    user_move: str,
    best_move: str,
    context: Dict[str, Any]
) -> DetectorResult:
    """Detect rook on 7th rank opportunities."""
    result = DetectorResult(
        detector_id="seventh_rank_detector",
        detected=False,
        pattern_type=StrategicConcept.SEVENTH_RANK.value,
        category=MistakeCategory.STRATEGIC.value
    )
    
    try:
        move = board.parse_san(user_move)
        board_after = board.copy()
        board_after.push(move)
        
        user_color = not board_after.turn
        seventh_rank = 6 if user_color == chess.WHITE else 1
        
        rooks_on_seventh = []
        potential_targets = []
        
        for file_idx in range(8):
            sq = chess.square(file_idx, seventh_rank)
            piece = board_after.piece_at(sq)
            
            if piece and piece.piece_type == chess.ROOK and piece.color == user_color:
                rooks_on_seventh.append(chess.square_name(sq))
            
            # Check for targets (opponent pawns on 7th/2nd rank)
            target_piece = board_after.piece_at(sq)
            if target_piece and target_piece.piece_type == chess.PAWN and target_piece.color != user_color:
                potential_targets.append(chess.square_name(sq))
        
        # Also check if king is trapped on back rank
        opp_king_sq = board_after.king(not user_color)
        opp_king_rank = chess.square_rank(opp_king_sq) if opp_king_sq else -1
        king_on_back_rank = (opp_king_rank == 7 if user_color == chess.WHITE else opp_king_rank == 0)
        
        if rooks_on_seventh:
            result.detected = True
            result.confidence = 0.85
            result.details = {
                "rooks_on_seventh": rooks_on_seventh,
                "targets": potential_targets,
                "king_trapped": king_on_back_rank
            }
            result.key_squares = rooks_on_seventh
            if king_on_back_rank:
                result.teaching_hook = "Rook on 7th rank! King is trapped on back rank"
            else:
                result.teaching_hook = "Rook on 7th rank attacks pawns and restricts the king"
        elif potential_targets and not rooks_on_seventh:
            # Opportunity missed
            result.detected = True
            result.confidence = 0.6
            result.teaching_hook = "The 7th rank has targets - consider putting a rook there"
    
    except Exception as e:
        logger.debug(f"Seventh rank detection error: {e}")
    
    return result


def detect_pawn_majority(
    board: chess.Board,
    user_move: str,
    best_move: str,
    context: Dict[str, Any]
) -> DetectorResult:
    """Detect pawn majorities on queenside or kingside."""
    result = DetectorResult(
        detector_id="pawn_majority_detector",
        detected=False,
        pattern_type=StrategicConcept.PAWN_MAJORITY.value,
        category=MistakeCategory.STRATEGIC.value
    )
    
    try:
        move = board.parse_san(user_move)
        board_after = board.copy()
        board_after.push(move)
        
        user_color = not board_after.turn
        
        # Count pawns on each wing
        user_kingside = 0
        user_queenside = 0
        opp_kingside = 0
        opp_queenside = 0
        
        for sq in chess.SQUARES:
            piece = board_after.piece_at(sq)
            if piece and piece.piece_type == chess.PAWN:
                file = chess.square_file(sq)
                is_kingside = file >= 4  # e-h files
                
                if piece.color == user_color:
                    if is_kingside:
                        user_kingside += 1
                    else:
                        user_queenside += 1
                else:
                    if is_kingside:
                        opp_kingside += 1
                    else:
                        opp_queenside += 1
        
        kingside_majority = user_kingside - opp_kingside
        queenside_majority = user_queenside - opp_queenside
        
        if abs(kingside_majority) >= 2 or abs(queenside_majority) >= 2:
            result.detected = True
            result.confidence = 0.7
            
            if kingside_majority >= 2:
                result.details = {
                    "side": "kingside",
                    "user_pawns": user_kingside,
                    "opp_pawns": opp_kingside,
                    "advantage": "user"
                }
                result.teaching_hook = "You have a kingside pawn majority - push to create a passed pawn!"
            elif queenside_majority >= 2:
                result.details = {
                    "side": "queenside",
                    "user_pawns": user_queenside,
                    "opp_pawns": opp_queenside,
                    "advantage": "user"
                }
                result.teaching_hook = "Queenside pawn majority! Use it in the endgame"
            elif kingside_majority <= -2:
                result.details = {"side": "kingside", "advantage": "opponent"}
                result.teaching_hook = "Opponent has kingside majority - watch for their pawn advance"
            else:
                result.details = {"side": "queenside", "advantage": "opponent"}
                result.teaching_hook = "Opponent has queenside majority - be ready to defend"
    
    except Exception as e:
        logger.debug(f"Pawn majority detection error: {e}")
    
    return result


def detect_piece_coordination(
    board: chess.Board,
    user_move: str,
    best_move: str,
    context: Dict[str, Any]
) -> DetectorResult:
    """Detect how well pieces work together."""
    result = DetectorResult(
        detector_id="piece_coordination_detector",
        detected=False,
        pattern_type=StrategicConcept.PIECE_COORDINATION.value,
        category=MistakeCategory.STRATEGIC.value
    )
    
    try:
        move = board.parse_san(user_move)
        board_after = board.copy()
        board_after.push(move)
        
        user_color = not board_after.turn
        
        # Find user's pieces
        pieces = []
        for sq in chess.SQUARES:
            piece = board_after.piece_at(sq)
            if piece and piece.color == user_color and piece.piece_type != chess.PAWN:
                pieces.append((sq, piece))
        
        # Count mutual defenses
        mutual_defenses = 0
        for sq1, piece1 in pieces:
            for sq2, piece2 in pieces:
                if sq1 != sq2:
                    if sq2 in board_after.attacks(sq1):
                        mutual_defenses += 1
        
        # Count jointly attacked squares (especially central)
        central = [chess.D4, chess.D5, chess.E4, chess.E5]
        joint_attacks = 0
        for sq in central:
            attackers = 0
            for piece_sq, _ in pieces:
                if sq in board_after.attacks(piece_sq):
                    attackers += 1
            if attackers >= 2:
                joint_attacks += 1
        
        coordination_score = mutual_defenses * 0.3 + joint_attacks * 0.5
        
        if coordination_score < 1.0 and len(pieces) >= 3:
            result.detected = True
            result.confidence = 0.6
            result.details = {
                "mutual_defenses": mutual_defenses,
                "joint_attacks": joint_attacks,
                "coordination_score": coordination_score
            }
            result.teaching_hook = "Your pieces aren't working together - coordinate them!"
        elif coordination_score >= 2.0:
            result.detected = True
            result.confidence = 0.7
            result.details = {"coordination_score": coordination_score}
            result.teaching_hook = "Good piece coordination - they support each other"
    
    except Exception as e:
        logger.debug(f"Piece coordination detection error: {e}")
    
    return result


# ==============================================================================
# ENDGAME CONCEPT DETECTORS
# ==============================================================================

def detect_opposition(
    board: chess.Board,
    user_move: str,
    best_move: str,
    context: Dict[str, Any]
) -> DetectorResult:
    """Detect opposition in king and pawn endgames."""
    result = DetectorResult(
        detector_id="opposition_detector",
        detected=False,
        pattern_type="opposition",
        category=MistakeCategory.STRATEGIC.value
    )
    
    try:
        # Check if it's a king+pawn endgame
        piece_count = 0
        for sq in chess.SQUARES:
            piece = board.piece_at(sq)
            if piece and piece.piece_type not in [chess.KING, chess.PAWN]:
                piece_count += 1
        
        if piece_count > 0:  # Not a pure K+P endgame
            return result
        
        board_after = board.copy()
        move = board.parse_san(user_move)
        board_after.push(move)
        
        white_king = board_after.king(chess.WHITE)
        black_king = board_after.king(chess.BLACK)
        
        if not white_king or not black_king:
            return result
        
        # Calculate distance between kings
        wk_file = chess.square_file(white_king)
        wk_rank = chess.square_rank(white_king)
        bk_file = chess.square_file(black_king)
        bk_rank = chess.square_rank(black_king)
        
        file_diff = abs(wk_file - bk_file)
        rank_diff = abs(wk_rank - bk_rank)
        
        # Direct opposition: same file/rank, 2 squares apart
        has_direct_opposition = (file_diff == 0 and rank_diff == 2) or (rank_diff == 0 and file_diff == 2)
        
        # Diagonal opposition
        has_diagonal_opposition = file_diff == 2 and rank_diff == 2
        
        user_color = not board_after.turn  # Color that just moved
        has_opposition = has_direct_opposition or has_diagonal_opposition
        
        # Who has the opposition? The side NOT to move has it
        user_has_opposition = has_opposition and board_after.turn != user_color
        
        if has_opposition:
            result.detected = True
            result.confidence = 0.85
            result.details = {
                "type": "direct" if has_direct_opposition else "diagonal",
                "user_has_opposition": user_has_opposition,
                "white_king": chess.square_name(white_king),
                "black_king": chess.square_name(black_king)
            }
            result.key_squares = [chess.square_name(white_king), chess.square_name(black_king)]
            
            if user_has_opposition:
                result.teaching_hook = "You have the opposition! The enemy king must give way"
            else:
                result.teaching_hook = "Opponent has opposition - try to gain it back"
    
    except Exception as e:
        logger.debug(f"Opposition detection error: {e}")
    
    return result


def detect_zugzwang(
    board: chess.Board,
    user_move: str,
    best_move: str,
    context: Dict[str, Any]
) -> DetectorResult:
    """Detect zugzwang positions where any move worsens the position."""
    result = DetectorResult(
        detector_id="zugzwang_detector",
        detected=False,
        pattern_type="zugzwang",
        category=MistakeCategory.STRATEGIC.value
    )
    
    try:
        # Zugzwang is most common in endgames
        game_phase = context.get("game_phase", GamePhase.MIDDLEGAME)
        if game_phase not in [GamePhase.ENDGAME, GamePhase.DEEP_ENDGAME, GamePhase.EARLY_ENDGAME]:
            return result
        
        board_after = board.copy()
        move = board.parse_san(user_move)
        board_after.push(move)
        
        # Count pieces
        piece_count = sum(1 for sq in chess.SQUARES if board_after.piece_at(sq))
        
        if piece_count > 8:  # Too many pieces for typical zugzwang
            return result
        
        # Check if opponent has very few legal moves
        legal_moves = list(board_after.legal_moves)
        
        if len(legal_moves) <= 3 and len(legal_moves) > 0:
            # Few moves available - potential zugzwang
            result.detected = True
            result.confidence = 0.5 + (3 - len(legal_moves)) * 0.15
            result.details = {
                "opponent_moves": len(legal_moves),
                "piece_count": piece_count
            }
            result.teaching_hook = "Opponent has very few moves - potential zugzwang!"
    
    except Exception as e:
        logger.debug(f"Zugzwang detection error: {e}")
    
    return result


def detect_outside_passed_pawn(
    board: chess.Board,
    user_move: str,
    best_move: str,
    context: Dict[str, Any]
) -> DetectorResult:
    """Detect outside passed pawns which are powerful in endgames."""
    result = DetectorResult(
        detector_id="outside_passed_pawn_detector",
        detected=False,
        pattern_type="outside_passed_pawn",
        category=MistakeCategory.STRATEGIC.value
    )
    
    try:
        board_after = board.copy()
        move = board.parse_san(user_move)
        board_after.push(move)
        
        user_color = not board_after.turn
        
        # Find all passed pawns
        passed_pawns = []
        
        for sq in chess.SQUARES:
            piece = board_after.piece_at(sq)
            if piece and piece.piece_type == chess.PAWN and piece.color == user_color:
                file = chess.square_file(sq)
                rank = chess.square_rank(sq)
                
                # Check if it's passed (no enemy pawns ahead or on adjacent files)
                is_passed = True
                check_ranks = range(rank + 1, 8) if user_color == chess.WHITE else range(0, rank)
                
                for check_file in [file - 1, file, file + 1]:
                    if 0 <= check_file <= 7:
                        for check_rank in check_ranks:
                            check_sq = chess.square(check_file, check_rank)
                            check_piece = board_after.piece_at(check_sq)
                            if check_piece and check_piece.piece_type == chess.PAWN and check_piece.color != user_color:
                                is_passed = False
                                break
                    if not is_passed:
                        break
                
                if is_passed:
                    passed_pawns.append({
                        "square": chess.square_name(sq),
                        "file": file,
                        "rank": rank
                    })
        
        if passed_pawns:
            # Determine if any are "outside" (on the wing)
            outside_pawns = [p for p in passed_pawns if p["file"] <= 1 or p["file"] >= 6]
            
            if outside_pawns:
                result.detected = True
                result.confidence = 0.85
                result.details = {
                    "outside_passed": outside_pawns,
                    "total_passed": len(passed_pawns)
                }
                result.key_squares = [p["square"] for p in outside_pawns]
                result.teaching_hook = "Outside passed pawn! It pulls the enemy king away"
            elif passed_pawns:
                result.detected = True
                result.confidence = 0.7
                result.details = {"passed_pawns": passed_pawns}
                result.key_squares = [p["square"] for p in passed_pawns[:2]]
                result.teaching_hook = "Passed pawns are strong - push them in the endgame!"
    
    except Exception as e:
        logger.debug(f"Outside passed pawn detection error: {e}")
    
    return result


def detect_king_activity(
    board: chess.Board,
    user_move: str,
    best_move: str,
    context: Dict[str, Any]
) -> DetectorResult:
    """Detect king activity in endgames."""
    result = DetectorResult(
        detector_id="king_activity_detector",
        detected=False,
        pattern_type="king_activity",
        category=MistakeCategory.STRATEGIC.value
    )
    
    try:
        game_phase = context.get("game_phase", GamePhase.MIDDLEGAME)
        if game_phase not in [GamePhase.ENDGAME, GamePhase.DEEP_ENDGAME, GamePhase.EARLY_ENDGAME, 
                             GamePhase.LATE_MIDDLEGAME]:
            return result
        
        board_after = board.copy()
        move = board.parse_san(user_move)
        board_after.push(move)
        
        user_color = not board_after.turn
        user_king = board_after.king(user_color)
        
        if not user_king:
            return result
        
        king_file = chess.square_file(user_king)
        king_rank = chess.square_rank(user_king)
        
        # Calculate king centrality
        center_distance = abs(king_file - 3.5) + abs(king_rank - 3.5)
        
        # In endgame, active king should be central
        is_active = center_distance <= 3
        
        # Check if king moved in the last move (for future use)
        # moved_piece = board.piece_at(move.from_square)
        # king_moved = moved_piece and moved_piece.piece_type == chess.KING
        
        if game_phase in [GamePhase.ENDGAME, GamePhase.DEEP_ENDGAME]:
            result.detected = True
            if is_active:
                result.confidence = 0.75
                result.details = {
                    "king_square": chess.square_name(user_king),
                    "centrality": 7 - center_distance,
                    "status": "active"
                }
                result.teaching_hook = "Good! Active king is key in endgames"
            else:
                result.confidence = 0.7
                result.details = {
                    "king_square": chess.square_name(user_king),
                    "status": "passive"
                }
                result.teaching_hook = "Activate your king! It's a strong piece in endgames"
            
            result.key_squares = [chess.square_name(user_king)]
    
    except Exception as e:
        logger.debug(f"King activity detection error: {e}")
    
    return result


def detect_rook_endgame_principles(
    board: chess.Board,
    user_move: str,
    best_move: str,
    context: Dict[str, Any]
) -> DetectorResult:
    """Detect rook endgame principles (Lucena, Philidor, rook behind passer)."""
    result = DetectorResult(
        detector_id="rook_endgame_detector",
        detected=False,
        pattern_type="rook_endgame",
        category=MistakeCategory.STRATEGIC.value
    )
    
    try:
        board_after = board.copy()
        move = board.parse_san(user_move)
        board_after.push(move)
        
        # Check if it's a rook endgame
        rooks = 0
        other_pieces = 0
        for sq in chess.SQUARES:
            piece = board_after.piece_at(sq)
            if piece and piece.piece_type not in [chess.KING, chess.PAWN]:
                if piece.piece_type == chess.ROOK:
                    rooks += 1
                else:
                    other_pieces += 1
        
        if rooks == 0 or other_pieces > 0:  # Not a rook endgame
            return result
        
        user_color = not board_after.turn
        
        # Find passed pawns and rook positions
        passed_pawns = []
        user_rook_sq = None
        
        for sq in chess.SQUARES:
            piece = board_after.piece_at(sq)
            if piece:
                if piece.piece_type == chess.ROOK and piece.color == user_color:
                    user_rook_sq = sq
                elif piece.piece_type == chess.PAWN:
                    # Check if passed
                    file = chess.square_file(sq)
                    rank = chess.square_rank(sq)
                    is_passed = True
                    opp_color = not piece.color
                    
                    check_ranks = range(rank + 1, 8) if piece.color == chess.WHITE else range(0, rank)
                    for cf in [file - 1, file, file + 1]:
                        if 0 <= cf <= 7:
                            for cr in check_ranks:
                                csq = chess.square(cf, cr)
                                cp = board_after.piece_at(csq)
                                if cp and cp.piece_type == chess.PAWN and cp.color == opp_color:
                                    is_passed = False
                                    break
                        if not is_passed:
                            break
                    
                    if is_passed:
                        passed_pawns.append((sq, piece.color))
        
        if user_rook_sq and passed_pawns:
            # Check if rook is behind passed pawn
            for pawn_sq, pawn_color in passed_pawns:
                pawn_file = chess.square_file(pawn_sq)
                rook_file = chess.square_file(user_rook_sq)
                rook_rank = chess.square_rank(user_rook_sq)
                pawn_rank = chess.square_rank(pawn_sq)
                
                if pawn_file == rook_file:
                    # Rook on same file as passer
                    if pawn_color == user_color:
                        # Our passer
                        behind = (user_color == chess.WHITE and rook_rank < pawn_rank) or \
                                (user_color == chess.BLACK and rook_rank > pawn_rank)
                        if behind:
                            result.detected = True
                            result.confidence = 0.85
                            result.details = {
                                "principle": "rook_behind_own_passer",
                                "rook": chess.square_name(user_rook_sq),
                                "passer": chess.square_name(pawn_sq)
                            }
                            result.teaching_hook = "Rook behind passed pawn - excellent placement!"
                            result.key_squares = [chess.square_name(user_rook_sq), chess.square_name(pawn_sq)]
                    else:
                        # Enemy passer - should be in front
                        in_front = (user_color == chess.WHITE and rook_rank > pawn_rank) or \
                                  (user_color == chess.BLACK and rook_rank < pawn_rank)
                        if in_front:
                            result.detected = True
                            result.confidence = 0.8
                            result.details = {
                                "principle": "rook_blocking_passer",
                                "rook": chess.square_name(user_rook_sq),
                                "passer": chess.square_name(pawn_sq)
                            }
                            result.teaching_hook = "Good! Rook stops the passed pawn from advancing"
        
        if not result.detected and rooks >= 1:
            # General rook endgame advice
            result.detected = True
            result.confidence = 0.5
            result.details = {"rooks": rooks, "passed_pawns": len(passed_pawns)}
            result.teaching_hook = "Rook endgames: activate your king and rook, create passed pawns"
    
    except Exception as e:
        logger.debug(f"Rook endgame detection error: {e}")
    
    return result


def detect_fortress(
    board: chess.Board,
    user_move: str,
    best_move: str,
    context: Dict[str, Any]
) -> DetectorResult:
    """Detect fortress positions where the defender can hold a draw."""
    result = DetectorResult(
        detector_id="fortress_detector",
        detected=False,
        pattern_type="fortress",
        category=MistakeCategory.STRATEGIC.value
    )
    
    try:
        game_phase = context.get("game_phase", GamePhase.MIDDLEGAME)
        if game_phase not in [GamePhase.ENDGAME, GamePhase.DEEP_ENDGAME]:
            return result
        
        board_after = board.copy()
        move = board.parse_san(user_move)
        board_after.push(move)
        
        # Count material
        material = {chess.WHITE: 0, chess.BLACK: 0}
        piece_values = {chess.QUEEN: 9, chess.ROOK: 5, chess.BISHOP: 3, chess.KNIGHT: 3, chess.PAWN: 1}
        
        for sq in chess.SQUARES:
            piece = board_after.piece_at(sq)
            if piece and piece.piece_type in piece_values:
                material[piece.color] += piece_values[piece.piece_type]
        
        user_color = not board_after.turn
        material_diff = material[user_color] - material[not user_color]
        
        # Fortress typically when defending side is down material but position is drawable
        if material_diff < -3:  # User is down material
            # Check for common fortress patterns
            user_king = board_after.king(user_color)
            if user_king:
                king_file = chess.square_file(user_king)
                king_rank = chess.square_rank(user_king)
                
                # King in corner with bishop that doesn't control corner color
                is_corner = (king_file in [0, 7] and king_rank in [0, 7])
                
                if is_corner:
                    result.detected = True
                    result.confidence = 0.6
                    result.details = {
                        "material_down": abs(material_diff),
                        "king_in_corner": True
                    }
                    result.teaching_hook = "Look for fortress! Sometimes you can hold a draw"
    
    except Exception as e:
        logger.debug(f"Fortress detection error: {e}")
    
    return result


# ==============================================================================
# REGISTRATION FUNCTION
# ==============================================================================

def register_advanced_detectors(registry):
    """Register all advanced detectors with the main registry."""
    
    # Strategic detectors
    registry.register_strategic(
        "doubled_pawns_detector",
        "Doubled Pawns Detector",
        StrategicConcept.DOUBLED_PAWNS.value,
        detect_doubled_pawns,
        priority=70,
        phase_relevant=[GamePhase.MIDDLEGAME, GamePhase.LATE_MIDDLEGAME, GamePhase.EARLY_ENDGAME]
    )
    
    registry.register_strategic(
        "backward_pawn_detector",
        "Backward Pawn Detector",
        StrategicConcept.BACKWARD_PAWN.value,
        detect_backward_pawn,
        priority=65,
        phase_relevant=[GamePhase.MIDDLEGAME, GamePhase.LATE_MIDDLEGAME]
    )
    
    registry.register_strategic(
        "bad_bishop_detector",
        "Bad Bishop Detector",
        StrategicConcept.BAD_BISHOP.value,
        detect_bad_bishop,
        priority=60,
        phase_relevant=[GamePhase.MIDDLEGAME, GamePhase.LATE_MIDDLEGAME, GamePhase.EARLY_ENDGAME]
    )
    
    registry.register_strategic(
        "space_advantage_detector",
        "Space Advantage Detector",
        StrategicConcept.SPACE_ADVANTAGE.value,
        detect_space_advantage,
        priority=70,
        phase_relevant=[GamePhase.EARLY_MIDDLEGAME, GamePhase.MIDDLEGAME]
    )
    
    registry.register_strategic(
        "weak_squares_detector",
        "Weak Squares Detector",
        StrategicConcept.WEAK_SQUARES.value,
        detect_weak_squares,
        priority=75,
        phase_relevant=[GamePhase.MIDDLEGAME, GamePhase.LATE_MIDDLEGAME]
    )
    
    registry.register_strategic(
        "open_file_detector",
        "Open File Detector",
        StrategicConcept.OPEN_FILE.value,
        detect_open_file,
        priority=80,
        phase_relevant=[GamePhase.MIDDLEGAME, GamePhase.LATE_MIDDLEGAME, GamePhase.EARLY_ENDGAME]
    )
    
    registry.register_strategic(
        "seventh_rank_detector",
        "Seventh Rank Detector",
        StrategicConcept.SEVENTH_RANK.value,
        detect_seventh_rank,
        priority=75,
        phase_relevant=[GamePhase.MIDDLEGAME, GamePhase.LATE_MIDDLEGAME, GamePhase.EARLY_ENDGAME]
    )
    
    registry.register_strategic(
        "pawn_majority_detector",
        "Pawn Majority Detector",
        StrategicConcept.PAWN_MAJORITY.value,
        detect_pawn_majority,
        priority=65,
        phase_relevant=[GamePhase.LATE_MIDDLEGAME, GamePhase.EARLY_ENDGAME, GamePhase.ENDGAME]
    )
    
    registry.register_strategic(
        "piece_coordination_detector",
        "Piece Coordination Detector",
        StrategicConcept.PIECE_COORDINATION.value,
        detect_piece_coordination,
        priority=55,
        phase_relevant=[GamePhase.MIDDLEGAME, GamePhase.LATE_MIDDLEGAME]
    )
    
    # Endgame detectors (using strategic category for now)
    registry.register_strategic(
        "opposition_detector",
        "Opposition Detector",
        "opposition",
        detect_opposition,
        priority=85,
        phase_relevant=[GamePhase.ENDGAME, GamePhase.DEEP_ENDGAME]
    )
    
    registry.register_strategic(
        "zugzwang_detector",
        "Zugzwang Detector",
        "zugzwang",
        detect_zugzwang,
        priority=70,
        phase_relevant=[GamePhase.ENDGAME, GamePhase.DEEP_ENDGAME]
    )
    
    registry.register_strategic(
        "outside_passed_pawn_detector",
        "Outside Passed Pawn Detector",
        "outside_passed_pawn",
        detect_outside_passed_pawn,
        priority=80,
        phase_relevant=[GamePhase.LATE_MIDDLEGAME, GamePhase.EARLY_ENDGAME, GamePhase.ENDGAME]
    )
    
    registry.register_strategic(
        "king_activity_detector",
        "King Activity Detector",
        "king_activity",
        detect_king_activity,
        priority=85,
        phase_relevant=[GamePhase.LATE_MIDDLEGAME, GamePhase.EARLY_ENDGAME, GamePhase.ENDGAME, GamePhase.DEEP_ENDGAME]
    )
    
    registry.register_strategic(
        "rook_endgame_detector",
        "Rook Endgame Detector",
        "rook_endgame",
        detect_rook_endgame_principles,
        priority=80,
        phase_relevant=[GamePhase.EARLY_ENDGAME, GamePhase.ENDGAME, GamePhase.DEEP_ENDGAME]
    )
    
    registry.register_strategic(
        "fortress_detector",
        "Fortress Detector",
        "fortress",
        detect_fortress,
        priority=60,
        phase_relevant=[GamePhase.ENDGAME, GamePhase.DEEP_ENDGAME]
    )
    
    logger.info("Registered 15 advanced detectors (9 strategic + 6 endgame)")


# ==============================================================================
# HELPER: GET CONCEPT INFO
# ==============================================================================

def get_concept_info(concept_name: str) -> Optional[Dict]:
    """Get detailed info about a chess concept from the graph."""
    node = CONCEPT_GRAPH.get_concept(concept_name)
    if not node:
        return None
    
    return {
        "name": node.name,
        "parent": node.parent,
        "children": node.children,
        "clarity_score": node.clarity_score,
        "teaching_priority": node.teaching_priority,
        "prerequisites": node.prerequisites,
        "related": node.related,
        "parent_chain": CONCEPT_GRAPH.get_parent_chain(concept_name)
    }


def get_best_teaching_concept(detected_concepts: List[str]) -> Optional[str]:
    """
    Given multiple detected concepts, return the best one to teach.
    Uses clarity score and teaching priority.
    """
    if not detected_concepts:
        return None
    
    return CONCEPT_GRAPH.get_teaching_order(detected_concepts)[0]
