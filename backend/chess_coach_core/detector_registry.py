"""
Detector Registry
=================

All pattern detectors organized into 3 classes:
- TACTICAL: Immediate concrete punishments (fork, pin, hanging piece)
- STRATEGIC: Quiet positional truths (weak center, poor development)
- META: Selection helpers (is_forcing, is_teachable, is_single_lesson)

Each detector returns DetectorResult with confidence score.
"""

import chess
import logging
from typing import Dict, List, Callable, Optional, Tuple
from dataclasses import dataclass

from .schemas import DetectorResult, DetectorClass

logger = logging.getLogger(__name__)


# =============================================================================
# DETECTOR REGISTRY
# =============================================================================

class DetectorRegistry:
    """
    Central registry for all detectors.
    Detectors are registered by class and can be run in bulk.
    """
    
    def __init__(self):
        self.tactical_detectors: Dict[str, Callable] = {}
        self.strategic_detectors: Dict[str, Callable] = {}
        self.meta_detectors: Dict[str, Callable] = {}
        
        # Register all built-in detectors
        self._register_tactical_detectors()
        self._register_strategic_detectors()
        self._register_meta_detectors()
    
    def _register_tactical_detectors(self):
        """Register the 10 tactical detectors"""
        self.tactical_detectors = {
            "fork": detect_fork,
            "pin": detect_pin,
            "skewer": detect_skewer,
            "discovered_attack": detect_discovered_attack,
            "double_attack": detect_double_attack,
            "hanging_piece": detect_hanging_piece,
            "mate_threat": detect_mate_threat,
            "overloaded_defender": detect_overloaded_defender,
            "trapped_piece": detect_trapped_piece,
            "zwischenzug": detect_zwischenzug,
        }
    
    def _register_strategic_detectors(self):
        """Register the 10 strategic detectors"""
        self.strategic_detectors = {
            "weak_center": detect_weak_center,
            "poor_development": detect_poor_development,
            "rook_inactivity": detect_rook_inactivity,
            "king_safety_risk": detect_king_safety_risk,
            "bad_pawn_structure": detect_bad_pawn_structure,
            "open_file_control": detect_open_file_control,
            "piece_activity_loss": detect_piece_activity_loss,
            "weak_square": detect_weak_square,
            "pawn_break_opportunity": detect_pawn_break_opportunity,
            "bishop_pair_advantage": detect_bishop_pair_advantage,
        }
    
    def _register_meta_detectors(self):
        """Register meta detectors (teachability helpers)"""
        self.meta_detectors = {
            "is_forcing_position": detect_is_forcing,
            "is_quiet_position": detect_is_quiet,
            "is_opening_in_book": detect_is_opening_book,
            "is_known_trap_nearby": detect_trap_nearby,
            "is_single_clear_lesson": detect_single_lesson,
            "is_multi_cause_position": detect_multi_cause,
            "is_endgame_principle_position": detect_endgame_principle,
        }
    
    def run_all_detectors(
        self, 
        board: chess.Board, 
        played_move: Optional[chess.Move],
        best_move: Optional[chess.Move],
        eval_before: int,
        eval_after: int,
        context: Dict
    ) -> Tuple[List[DetectorResult], List[DetectorResult], List[DetectorResult]]:
        """
        Run all detectors and return results grouped by class.
        """
        tactical_results = []
        strategic_results = []
        meta_results = []
        
        # Run tactical detectors
        for name, detector in self.tactical_detectors.items():
            try:
                result = detector(board, played_move, best_move, eval_before, eval_after, context)
                result.detector_class = DetectorClass.TACTICAL
                tactical_results.append(result)
            except Exception as e:
                logger.warning(f"Tactical detector {name} failed: {e}")
                tactical_results.append(DetectorResult(
                    detector_name=name,
                    detected=False,
                    confidence=0.0,
                    detector_class=DetectorClass.TACTICAL
                ))
        
        # Run strategic detectors
        for name, detector in self.strategic_detectors.items():
            try:
                result = detector(board, played_move, best_move, eval_before, eval_after, context)
                result.detector_class = DetectorClass.STRATEGIC
                strategic_results.append(result)
            except Exception as e:
                logger.warning(f"Strategic detector {name} failed: {e}")
                strategic_results.append(DetectorResult(
                    detector_name=name,
                    detected=False,
                    confidence=0.0,
                    detector_class=DetectorClass.STRATEGIC
                ))
        
        # Run meta detectors
        for name, detector in self.meta_detectors.items():
            try:
                result = detector(board, played_move, best_move, eval_before, eval_after, context)
                result.detector_class = DetectorClass.META
                meta_results.append(result)
            except Exception as e:
                logger.warning(f"Meta detector {name} failed: {e}")
                meta_results.append(DetectorResult(
                    detector_name=name,
                    detected=False,
                    confidence=0.0,
                    detector_class=DetectorClass.META
                ))
        
        return tactical_results, strategic_results, meta_results


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

PIECE_VALUES = {
    chess.PAWN: 1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9,
    chess.KING: 0  # King is invaluable but not counted in material
}

def get_piece_value(piece_type: int) -> int:
    return PIECE_VALUES.get(piece_type, 0)

def count_material(board: chess.Board, color: chess.Color) -> int:
    """Count material for one side"""
    total = 0
    for piece_type in [chess.PAWN, chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN]:
        total += len(board.pieces(piece_type, color)) * PIECE_VALUES[piece_type]
    return total

def get_attacked_pieces(board: chess.Board, attacker_square: int, color: chess.Color) -> List[Tuple[int, int]]:
    """Get list of (square, piece_type) attacked by piece at attacker_square"""
    attacked = []
    attacks = board.attacks(attacker_square)
    for sq in attacks:
        piece = board.piece_at(sq)
        if piece and piece.color != color:
            attacked.append((sq, piece.piece_type))
    return attacked

def is_piece_hanging(board: chess.Board, square: int) -> bool:
    """Check if piece at square is undefended and attacked"""
    piece = board.piece_at(square)
    if not piece:
        return False
    
    attackers = board.attackers(not piece.color, square)
    defenders = board.attackers(piece.color, square)
    
    if attackers and not defenders:
        return True
    
    # Also hanging if attacked by lower value piece
    if attackers:
        piece_value = get_piece_value(piece.piece_type)
        for attacker_sq in attackers:
            attacker = board.piece_at(attacker_sq)
            if attacker and get_piece_value(attacker.piece_type) < piece_value:
                if not defenders:
                    return True
    
    return False


# =============================================================================
# TACTICAL DETECTORS
# =============================================================================

def detect_fork(
    board: chess.Board,
    played_move: Optional[chess.Move],
    best_move: Optional[chess.Move],
    eval_before: int,
    eval_after: int,
    context: Dict
) -> DetectorResult:
    """
    Detect fork opportunity.
    A fork is when one piece attacks two or more valuable pieces.
    """
    result = DetectorResult(
        detector_name="fork",
        detected=False,
        confidence=0.0,
        detector_class=DetectorClass.TACTICAL
    )
    
    if not best_move:
        return result
    
    # Check if best move creates a fork
    test_board = board.copy()
    test_board.push(best_move)
    
    attacker_square = best_move.to_square
    attacker = test_board.piece_at(attacker_square)
    
    if not attacker:
        return result
    
    attacked = get_attacked_pieces(test_board, attacker_square, attacker.color)
    
    # Filter for valuable pieces (knight+ value)
    valuable_attacked = [(sq, pt) for sq, pt in attacked if get_piece_value(pt) >= 3]
    
    if len(valuable_attacked) >= 2:
        result.detected = True
        result.confidence = 0.90 if len(valuable_attacked) >= 2 else 0.75
        result.square = chess.square_name(attacker_square)
        result.pieces_involved = [chess.piece_name(pt) for _, pt in valuable_attacked]
        result.winning_move = best_move.uci()
        result.details = {
            "fork_type": chess.piece_name(attacker.piece_type) + "_fork",
            "targets": [chess.square_name(sq) for sq, _ in valuable_attacked],
            "num_targets": len(valuable_attacked)
        }
    
    return result


def detect_pin(
    board: chess.Board,
    played_move: Optional[chess.Move],
    best_move: Optional[chess.Move],
    eval_before: int,
    eval_after: int,
    context: Dict
) -> DetectorResult:
    """
    Detect pin opportunity.
    A pin is when a piece cannot move because it would expose a more valuable piece.
    """
    result = DetectorResult(
        detector_name="pin",
        detected=False,
        confidence=0.0,
        detector_class=DetectorClass.TACTICAL
    )
    
    # Check for existing pins or pin opportunities
    side_to_move = board.turn
    opponent = not side_to_move
    
    # Find opponent's king
    king_square = board.king(opponent)
    if king_square is None:
        return result
    
    # Check each of our sliding pieces for pin opportunities
    for piece_type in [chess.BISHOP, chess.ROOK, chess.QUEEN]:
        for attacker_sq in board.pieces(piece_type, side_to_move):
            # Get squares between attacker and king
            if piece_type == chess.BISHOP:
                if not _is_diagonal(attacker_sq, king_square):
                    continue
            elif piece_type == chess.ROOK:
                if not _is_straight(attacker_sq, king_square):
                    continue
            else:  # Queen
                if not (_is_diagonal(attacker_sq, king_square) or _is_straight(attacker_sq, king_square)):
                    continue
            
            # Count pieces between attacker and king
            between = chess.SquareSet(chess.between(attacker_sq, king_square))
            pieces_between = [sq for sq in between if board.piece_at(sq)]
            
            if len(pieces_between) == 1:
                pinned_sq = pieces_between[0]
                pinned_piece = board.piece_at(pinned_sq)
                if pinned_piece and pinned_piece.color == opponent:
                    result.detected = True
                    result.confidence = 0.85
                    result.square = chess.square_name(pinned_sq)
                    result.pieces_involved = [chess.piece_name(pinned_piece.piece_type), "king"]
                    result.details = {
                        "pin_type": "absolute" if piece_type in [chess.ROOK, chess.QUEEN] else "relative",
                        "pinned_piece": chess.piece_name(pinned_piece.piece_type),
                        "pinner": chess.square_name(attacker_sq)
                    }
                    return result
    
    return result


def _is_diagonal(sq1: int, sq2: int) -> bool:
    """Check if two squares are on the same diagonal"""
    file_diff = abs(chess.square_file(sq1) - chess.square_file(sq2))
    rank_diff = abs(chess.square_rank(sq1) - chess.square_rank(sq2))
    return file_diff == rank_diff and file_diff > 0


def _is_straight(sq1: int, sq2: int) -> bool:
    """Check if two squares are on the same file or rank"""
    same_file = chess.square_file(sq1) == chess.square_file(sq2)
    same_rank = chess.square_rank(sq1) == chess.square_rank(sq2)
    return (same_file or same_rank) and sq1 != sq2


def detect_skewer(
    board: chess.Board,
    played_move: Optional[chess.Move],
    best_move: Optional[chess.Move],
    eval_before: int,
    eval_after: int,
    context: Dict
) -> DetectorResult:
    """
    Detect skewer opportunity.
    A skewer is like a reverse pin - attacking a valuable piece that must move,
    exposing a less valuable piece behind it.
    """
    result = DetectorResult(
        detector_name="skewer",
        detected=False,
        confidence=0.0,
        detector_class=DetectorClass.TACTICAL
    )
    
    # Similar logic to pin but checking value ordering
    side_to_move = board.turn
    opponent = not side_to_move
    
    for piece_type in [chess.BISHOP, chess.ROOK, chess.QUEEN]:
        for attacker_sq in board.pieces(piece_type, side_to_move):
            attacks = board.attacks(attacker_sq)
            
            for attacked_sq in attacks:
                attacked_piece = board.piece_at(attacked_sq)
                if not attacked_piece or attacked_piece.color != opponent:
                    continue
                
                # Check for piece behind
                direction = _get_direction(attacker_sq, attacked_sq)
                if direction is None:
                    continue
                
                behind_sq = attacked_sq
                while True:
                    behind_sq = _next_square(behind_sq, direction)
                    if behind_sq is None:
                        break
                    
                    behind_piece = board.piece_at(behind_sq)
                    if behind_piece:
                        if behind_piece.color == opponent:
                            front_value = get_piece_value(attacked_piece.piece_type)
                            back_value = get_piece_value(behind_piece.piece_type)
                            
                            if front_value > back_value:
                                result.detected = True
                                result.confidence = 0.80
                                result.square = chess.square_name(attacked_sq)
                                result.pieces_involved = [
                                    chess.piece_name(attacked_piece.piece_type),
                                    chess.piece_name(behind_piece.piece_type)
                                ]
                                result.details = {
                                    "front_piece": chess.square_name(attacked_sq),
                                    "back_piece": chess.square_name(behind_sq)
                                }
                                return result
                        break
    
    return result


def _get_direction(from_sq: int, to_sq: int) -> Optional[Tuple[int, int]]:
    """Get direction vector from one square to another"""
    file_diff = chess.square_file(to_sq) - chess.square_file(from_sq)
    rank_diff = chess.square_rank(to_sq) - chess.square_rank(from_sq)
    
    if file_diff == 0 and rank_diff == 0:
        return None
    
    # Normalize to unit direction
    if file_diff != 0:
        file_diff = file_diff // abs(file_diff)
    if rank_diff != 0:
        rank_diff = rank_diff // abs(rank_diff)
    
    return (file_diff, rank_diff)


def _next_square(sq: int, direction: Tuple[int, int]) -> Optional[int]:
    """Get next square in direction"""
    file = chess.square_file(sq) + direction[0]
    rank = chess.square_rank(sq) + direction[1]
    
    if 0 <= file <= 7 and 0 <= rank <= 7:
        return chess.square(file, rank)
    return None


def detect_discovered_attack(
    board: chess.Board,
    played_move: Optional[chess.Move],
    best_move: Optional[chess.Move],
    eval_before: int,
    eval_after: int,
    context: Dict
) -> DetectorResult:
    """Detect discovered attack opportunity"""
    result = DetectorResult(
        detector_name="discovered_attack",
        detected=False,
        confidence=0.0,
        detector_class=DetectorClass.TACTICAL
    )
    
    if not best_move:
        return result
    
    # Check if best move creates a discovered attack
    from_sq = best_move.from_square
    moving_piece = board.piece_at(from_sq)
    
    if not moving_piece:
        return result
    
    side = moving_piece.color
    opponent = not side
    
    # Check if there's a sliding piece behind the moving piece
    for piece_type in [chess.BISHOP, chess.ROOK, chess.QUEEN]:
        for attacker_sq in board.pieces(piece_type, side):
            if attacker_sq == from_sq:
                continue
            
            # Is the moving piece between attacker and an opponent piece?
            between = chess.SquareSet(chess.between(attacker_sq, from_sq))
            if len(list(between)) > 0:
                continue  # Other pieces in the way
            
            # Check if moving the piece exposes an attack
            test_board = board.copy()
            test_board.push(best_move)
            
            new_attacks = test_board.attacks(attacker_sq)
            old_attacks = board.attacks(attacker_sq)
            
            # Find newly attacked valuable pieces
            for sq in new_attacks:
                if sq not in old_attacks:
                    target = test_board.piece_at(sq)
                    if target and target.color == opponent and get_piece_value(target.piece_type) >= 3:
                        result.detected = True
                        result.confidence = 0.85
                        result.winning_move = best_move.uci()
                        result.details = {
                            "discovered_attacker": chess.square_name(attacker_sq),
                            "target": chess.square_name(sq)
                        }
                        return result
    
    return result


def detect_double_attack(
    board: chess.Board,
    played_move: Optional[chess.Move],
    best_move: Optional[chess.Move],
    eval_before: int,
    eval_after: int,
    context: Dict
) -> DetectorResult:
    """Detect double attack (different from fork - two pieces attack one target)"""
    result = DetectorResult(
        detector_name="double_attack",
        detected=False,
        confidence=0.0,
        detector_class=DetectorClass.TACTICAL
    )
    
    # This overlaps with fork but is distinct - two attackers on one target
    # For V1, we'll use fork detector for multiple attacks
    # This detector focuses on coordination attacks
    
    return result


def detect_hanging_piece(
    board: chess.Board,
    played_move: Optional[chess.Move],
    best_move: Optional[chess.Move],
    eval_before: int,
    eval_after: int,
    context: Dict
) -> DetectorResult:
    """Detect hanging (undefended and attacked) piece"""
    result = DetectorResult(
        detector_name="hanging_piece",
        detected=False,
        confidence=0.0,
        detector_class=DetectorClass.TACTICAL
    )
    
    side_to_move = board.turn
    opponent = not side_to_move
    
    # Check opponent's pieces for hanging
    for piece_type in [chess.QUEEN, chess.ROOK, chess.BISHOP, chess.KNIGHT, chess.PAWN]:
        for sq in board.pieces(piece_type, opponent):
            if is_piece_hanging(board, sq):
                result.detected = True
                result.confidence = 0.95  # Very clear tactical fact
                result.square = chess.square_name(sq)
                result.pieces_involved = [chess.piece_name(piece_type)]
                result.details = {
                    "hanging_piece": chess.piece_name(piece_type),
                    "square": chess.square_name(sq),
                    "value": get_piece_value(piece_type)
                }
                return result
    
    # Also check if user's move left their own piece hanging
    if played_move:
        test_board = board.copy()
        # Board already has move played, so check our pieces
        for piece_type in [chess.QUEEN, chess.ROOK, chess.BISHOP, chess.KNIGHT, chess.PAWN]:
            for sq in board.pieces(piece_type, side_to_move):
                if is_piece_hanging(board, sq):
                    result.detected = True
                    result.confidence = 0.95
                    result.square = chess.square_name(sq)
                    result.pieces_involved = [chess.piece_name(piece_type)]
                    result.details = {
                        "user_left_hanging": True,
                        "hanging_piece": chess.piece_name(piece_type),
                        "square": chess.square_name(sq)
                    }
                    return result
    
    return result


def detect_mate_threat(
    board: chess.Board,
    played_move: Optional[chess.Move],
    best_move: Optional[chess.Move],
    eval_before: int,
    eval_after: int,
    context: Dict
) -> DetectorResult:
    """Detect checkmate threat"""
    result = DetectorResult(
        detector_name="mate_threat",
        detected=False,
        confidence=0.0,
        detector_class=DetectorClass.TACTICAL
    )
    
    # Check if there's mate in 1-2 moves
    if board.is_checkmate():
        result.detected = True
        result.confidence = 1.0
        result.details = {"mate_in": 0, "type": "checkmate"}
        return result
    
    # Check for mate in 1
    for move in board.legal_moves:
        test_board = board.copy()
        test_board.push(move)
        if test_board.is_checkmate():
            result.detected = True
            result.confidence = 0.95
            result.winning_move = move.uci()
            result.details = {"mate_in": 1, "mating_move": move.uci()}
            return result
    
    return result


def detect_overloaded_defender(
    board: chess.Board,
    played_move: Optional[chess.Move],
    best_move: Optional[chess.Move],
    eval_before: int,
    eval_after: int,
    context: Dict
) -> DetectorResult:
    """Detect overloaded defender"""
    result = DetectorResult(
        detector_name="overloaded_defender",
        detected=False,
        confidence=0.0,
        detector_class=DetectorClass.TACTICAL
    )
    
    # Complex detection - for V1, return basic result
    # Full implementation would check if one piece defends multiple threats
    
    return result


def detect_trapped_piece(
    board: chess.Board,
    played_move: Optional[chess.Move],
    best_move: Optional[chess.Move],
    eval_before: int,
    eval_after: int,
    context: Dict
) -> DetectorResult:
    """Detect trapped piece with no escape squares"""
    result = DetectorResult(
        detector_name="trapped_piece",
        detected=False,
        confidence=0.0,
        detector_class=DetectorClass.TACTICAL
    )
    
    opponent = not board.turn
    
    # Check opponent's valuable pieces for being trapped
    for piece_type in [chess.QUEEN, chess.ROOK, chess.BISHOP, chess.KNIGHT]:
        for sq in board.pieces(piece_type, opponent):
            # Count escape squares
            escape_squares = 0
            piece = board.piece_at(sq)
            
            # Temporarily remove the piece to check where it could go
            for move in board.legal_moves:
                if move.from_square == sq:
                    escape_squares += 1
            
            # If piece is attacked and has no/few escapes
            attackers = board.attackers(board.turn, sq)
            if attackers and escape_squares <= 1:
                result.detected = True
                result.confidence = 0.80
                result.square = chess.square_name(sq)
                result.pieces_involved = [chess.piece_name(piece_type)]
                result.details = {
                    "trapped_piece": chess.piece_name(piece_type),
                    "escape_squares": escape_squares
                }
                return result
    
    return result


def detect_zwischenzug(
    board: chess.Board,
    played_move: Optional[chess.Move],
    best_move: Optional[chess.Move],
    eval_before: int,
    eval_after: int,
    context: Dict
) -> DetectorResult:
    """Detect zwischenzug (intermediate move) opportunity"""
    result = DetectorResult(
        detector_name="zwischenzug",
        detected=False,
        confidence=0.0,
        detector_class=DetectorClass.TACTICAL
    )
    
    # Complex detection - check if there's a forcing intermediate move
    # For V1, return basic result
    
    return result


# =============================================================================
# STRATEGIC DETECTORS
# =============================================================================

def detect_weak_center(
    board: chess.Board,
    played_move: Optional[chess.Move],
    best_move: Optional[chess.Move],
    eval_before: int,
    eval_after: int,
    context: Dict
) -> DetectorResult:
    """Detect weak center control"""
    result = DetectorResult(
        detector_name="weak_center",
        detected=False,
        confidence=0.0,
        detector_class=DetectorClass.STRATEGIC
    )
    
    center_squares = [chess.E4, chess.D4, chess.E5, chess.D5]
    side_to_move = board.turn
    
    # Count center control
    our_control = 0
    their_control = 0
    
    for sq in center_squares:
        our_attackers = len(board.attackers(side_to_move, sq))
        their_attackers = len(board.attackers(not side_to_move, sq))
        
        our_control += our_attackers
        their_control += their_attackers
        
        # Bonus for pawns on center squares
        piece = board.piece_at(sq)
        if piece and piece.piece_type == chess.PAWN:
            if piece.color == side_to_move:
                our_control += 2
            else:
                their_control += 2
    
    if their_control > our_control + 2:
        result.detected = True
        result.confidence = min(0.70 + (their_control - our_control) * 0.05, 0.90)
        result.details = {
            "our_control": our_control,
            "their_control": their_control,
            "deficit": their_control - our_control
        }
    
    return result


def detect_poor_development(
    board: chess.Board,
    played_move: Optional[chess.Move],
    best_move: Optional[chess.Move],
    eval_before: int,
    eval_after: int,
    context: Dict
) -> DetectorResult:
    """Detect poor piece development in opening/early middlegame"""
    result = DetectorResult(
        detector_name="poor_development",
        detected=False,
        confidence=0.0,
        detector_class=DetectorClass.STRATEGIC
    )
    
    move_number = context.get("move_number", 0)
    if move_number > 15:  # Only relevant in opening
        return result
    
    side_to_move = board.turn
    
    # Count developed pieces
    developed = 0
    
    # Knights developed (not on b1/g1 for white, b8/g8 for black)
    start_knight_squares = [chess.B1, chess.G1] if side_to_move == chess.WHITE else [chess.B8, chess.G8]
    for sq in board.pieces(chess.KNIGHT, side_to_move):
        if sq not in start_knight_squares:
            developed += 1
    
    # Bishops developed (not on c1/f1 for white)
    start_bishop_squares = [chess.C1, chess.F1] if side_to_move == chess.WHITE else [chess.C8, chess.F8]
    for sq in board.pieces(chess.BISHOP, side_to_move):
        if sq not in start_bishop_squares:
            developed += 1
    
    # King castled counts as development
    king_sq = board.king(side_to_move)
    if side_to_move == chess.WHITE:
        if king_sq in [chess.G1, chess.C1]:
            developed += 1
    else:
        if king_sq in [chess.G8, chess.C8]:
            developed += 1
    
    # After move 8, should have at least 3 pieces developed
    expected = min(move_number // 3, 4)
    
    if developed < expected:
        result.detected = True
        result.confidence = 0.65 + (expected - developed) * 0.10
        result.details = {
            "pieces_developed": developed,
            "expected": expected,
            "move_number": move_number
        }
    
    return result


def detect_rook_inactivity(
    board: chess.Board,
    played_move: Optional[chess.Move],
    best_move: Optional[chess.Move],
    eval_before: int,
    eval_after: int,
    context: Dict
) -> DetectorResult:
    """Detect inactive rooks in middlegame/endgame"""
    result = DetectorResult(
        detector_name="rook_inactivity",
        detected=False,
        confidence=0.0,
        detector_class=DetectorClass.STRATEGIC
    )
    
    move_number = context.get("move_number", 0)
    if move_number < 12:  # Too early to judge
        return result
    
    side_to_move = board.turn
    
    # Check if rooks are on starting squares or trapped
    start_rook_squares = [chess.A1, chess.H1] if side_to_move == chess.WHITE else [chess.A8, chess.H8]
    
    inactive_rooks = 0
    for sq in board.pieces(chess.ROOK, side_to_move):
        if sq in start_rook_squares:
            inactive_rooks += 1
        else:
            # Check if rook has open file or rank
            mobility = len(list(board.attacks(sq)))
            if mobility <= 4:
                inactive_rooks += 1
    
    if inactive_rooks >= 1:
        result.detected = True
        result.confidence = 0.60 + inactive_rooks * 0.15
        result.details = {
            "inactive_rooks": inactive_rooks
        }
    
    return result


def detect_king_safety_risk(
    board: chess.Board,
    played_move: Optional[chess.Move],
    best_move: Optional[chess.Move],
    eval_before: int,
    eval_after: int,
    context: Dict
) -> DetectorResult:
    """Detect king safety issues"""
    result = DetectorResult(
        detector_name="king_safety_risk",
        detected=False,
        confidence=0.0,
        detector_class=DetectorClass.STRATEGIC
    )
    
    side_to_move = board.turn
    king_sq = board.king(side_to_move)
    
    if king_sq is None:
        return result
    
    risk_score = 0
    
    # Check pawn shield
    king_file = chess.square_file(king_sq)
    king_rank = chess.square_rank(king_sq)
    
    shield_rank = king_rank + 1 if side_to_move == chess.WHITE else king_rank - 1
    if 0 <= shield_rank <= 7:
        for f in [king_file - 1, king_file, king_file + 1]:
            if 0 <= f <= 7:
                shield_sq = chess.square(f, shield_rank)
                piece = board.piece_at(shield_sq)
                if not piece or piece.piece_type != chess.PAWN or piece.color != side_to_move:
                    risk_score += 1
    
    # Check if king is in center (not castled) after move 10
    move_number = context.get("move_number", 0)
    if move_number > 10:
        if side_to_move == chess.WHITE and king_sq == chess.E1:
            risk_score += 2
        elif side_to_move == chess.BLACK and king_sq == chess.E8:
            risk_score += 2
    
    # Check attackers near king
    adjacent_squares = board.attacks(king_sq)
    for sq in adjacent_squares:
        attackers = board.attackers(not side_to_move, sq)
        risk_score += len(attackers) * 0.5
    
    if risk_score >= 3:
        result.detected = True
        result.confidence = min(0.50 + risk_score * 0.10, 0.90)
        result.details = {
            "risk_score": risk_score,
            "king_square": chess.square_name(king_sq)
        }
    
    return result


def detect_bad_pawn_structure(
    board: chess.Board,
    played_move: Optional[chess.Move],
    best_move: Optional[chess.Move],
    eval_before: int,
    eval_after: int,
    context: Dict
) -> DetectorResult:
    """Detect pawn structure weaknesses"""
    result = DetectorResult(
        detector_name="bad_pawn_structure",
        detected=False,
        confidence=0.0,
        detector_class=DetectorClass.STRATEGIC
    )
    
    side_to_move = board.turn
    
    issues = []
    
    # Check for doubled pawns
    for file in range(8):
        pawns_on_file = 0
        for rank in range(8):
            sq = chess.square(file, rank)
            piece = board.piece_at(sq)
            if piece and piece.piece_type == chess.PAWN and piece.color == side_to_move:
                pawns_on_file += 1
        if pawns_on_file >= 2:
            issues.append(f"doubled_pawns_{chess.FILE_NAMES[file]}")
    
    # Check for isolated pawns
    for file in range(8):
        has_pawn = False
        for rank in range(8):
            sq = chess.square(file, rank)
            piece = board.piece_at(sq)
            if piece and piece.piece_type == chess.PAWN and piece.color == side_to_move:
                has_pawn = True
                break
        
        if has_pawn:
            # Check adjacent files
            has_neighbor = False
            for adj_file in [file - 1, file + 1]:
                if 0 <= adj_file <= 7:
                    for rank in range(8):
                        sq = chess.square(adj_file, rank)
                        piece = board.piece_at(sq)
                        if piece and piece.piece_type == chess.PAWN and piece.color == side_to_move:
                            has_neighbor = True
                            break
            
            if not has_neighbor:
                issues.append(f"isolated_pawn_{chess.FILE_NAMES[file]}")
    
    if issues:
        result.detected = True
        result.confidence = min(0.55 + len(issues) * 0.12, 0.85)
        result.details = {
            "issues": issues,
            "num_issues": len(issues)
        }
    
    return result


def detect_open_file_control(
    board: chess.Board,
    played_move: Optional[chess.Move],
    best_move: Optional[chess.Move],
    eval_before: int,
    eval_after: int,
    context: Dict
) -> DetectorResult:
    """Detect open file control opportunity"""
    result = DetectorResult(
        detector_name="open_file_control",
        detected=False,
        confidence=0.0,
        detector_class=DetectorClass.STRATEGIC
    )
    
    # Find open files (no pawns)
    open_files = []
    for file in range(8):
        has_pawn = False
        for rank in range(8):
            sq = chess.square(file, rank)
            piece = board.piece_at(sq)
            if piece and piece.piece_type == chess.PAWN:
                has_pawn = True
                break
        if not has_pawn:
            open_files.append(file)
    
    if not open_files:
        return result
    
    side_to_move = board.turn
    
    # Check if we have rooks not on open files
    for sq in board.pieces(chess.ROOK, side_to_move):
        rook_file = chess.square_file(sq)
        if rook_file not in open_files:
            result.detected = True
            result.confidence = 0.65
            result.details = {
                "open_files": [chess.FILE_NAMES[f] for f in open_files],
                "rook_not_on_open_file": chess.square_name(sq)
            }
            return result
    
    return result


def detect_piece_activity_loss(
    board: chess.Board,
    played_move: Optional[chess.Move],
    best_move: Optional[chess.Move],
    eval_before: int,
    eval_after: int,
    context: Dict
) -> DetectorResult:
    """Detect loss of piece activity from played move"""
    result = DetectorResult(
        detector_name="piece_activity_loss",
        detected=False,
        confidence=0.0,
        detector_class=DetectorClass.STRATEGIC
    )
    
    # Would need to compare mobility before/after move
    # For V1, return basic result
    
    return result


def detect_weak_square(
    board: chess.Board,
    played_move: Optional[chess.Move],
    best_move: Optional[chess.Move],
    eval_before: int,
    eval_after: int,
    context: Dict
) -> DetectorResult:
    """Detect weak squares that can be exploited"""
    result = DetectorResult(
        detector_name="weak_square",
        detected=False,
        confidence=0.0,
        detector_class=DetectorClass.STRATEGIC
    )
    
    # Complex detection - for V1, return basic result
    return result


def detect_pawn_break_opportunity(
    board: chess.Board,
    played_move: Optional[chess.Move],
    best_move: Optional[chess.Move],
    eval_before: int,
    eval_after: int,
    context: Dict
) -> DetectorResult:
    """Detect pawn break opportunity"""
    result = DetectorResult(
        detector_name="pawn_break_opportunity",
        detected=False,
        confidence=0.0,
        detector_class=DetectorClass.STRATEGIC
    )
    
    # For V1, return basic result
    return result


def detect_bishop_pair_advantage(
    board: chess.Board,
    played_move: Optional[chess.Move],
    best_move: Optional[chess.Move],
    eval_before: int,
    eval_after: int,
    context: Dict
) -> DetectorResult:
    """Detect bishop pair advantage"""
    result = DetectorResult(
        detector_name="bishop_pair_advantage",
        detected=False,
        confidence=0.0,
        detector_class=DetectorClass.STRATEGIC
    )
    
    side_to_move = board.turn
    opponent = not side_to_move
    
    our_bishops = len(list(board.pieces(chess.BISHOP, side_to_move)))
    their_bishops = len(list(board.pieces(chess.BISHOP, opponent)))
    
    if our_bishops == 2 and their_bishops < 2:
        result.detected = True
        result.confidence = 0.70
        result.details = {
            "advantage": "bishop_pair",
            "our_bishops": our_bishops,
            "their_bishops": their_bishops
        }
    
    return result


# =============================================================================
# META DETECTORS
# =============================================================================

def detect_is_forcing(
    board: chess.Board,
    played_move: Optional[chess.Move],
    best_move: Optional[chess.Move],
    eval_before: int,
    eval_after: int,
    context: Dict
) -> DetectorResult:
    """Detect if position is forcing (checks, captures, threats)"""
    result = DetectorResult(
        detector_name="is_forcing_position",
        detected=False,
        confidence=0.0,
        detector_class=DetectorClass.META
    )
    
    # Position is forcing if there are checks or major captures available
    is_check = board.is_check()
    
    forcing_moves = 0
    for move in board.legal_moves:
        if board.is_capture(move):
            captured = board.piece_at(move.to_square)
            if captured and get_piece_value(captured.piece_type) >= 3:
                forcing_moves += 1
        
        test_board = board.copy()
        test_board.push(move)
        if test_board.is_check():
            forcing_moves += 1
    
    if is_check or forcing_moves >= 2:
        result.detected = True
        result.confidence = 0.85
        result.details = {
            "is_check": is_check,
            "forcing_moves": forcing_moves
        }
    
    return result


def detect_is_quiet(
    board: chess.Board,
    played_move: Optional[chess.Move],
    best_move: Optional[chess.Move],
    eval_before: int,
    eval_after: int,
    context: Dict
) -> DetectorResult:
    """Detect if position is quiet (good for strategic teaching)"""
    result = DetectorResult(
        detector_name="is_quiet_position",
        detected=False,
        confidence=0.0,
        detector_class=DetectorClass.META
    )
    
    is_check = board.is_check()
    
    # Count forcing moves available
    forcing_moves = 0
    for move in board.legal_moves:
        if board.is_capture(move):
            captured = board.piece_at(move.to_square)
            if captured and get_piece_value(captured.piece_type) >= 3:
                forcing_moves += 1
    
    # Small eval change indicates quiet
    eval_change = abs(eval_after - eval_before)
    
    if not is_check and forcing_moves <= 1 and eval_change < 50:
        result.detected = True
        result.confidence = 0.75
        result.details = {
            "forcing_moves": forcing_moves,
            "eval_change": eval_change
        }
    
    return result


def detect_is_opening_book(
    board: chess.Board,
    played_move: Optional[chess.Move],
    best_move: Optional[chess.Move],
    eval_before: int,
    eval_after: int,
    context: Dict
) -> DetectorResult:
    """Detect if still in opening book"""
    result = DetectorResult(
        detector_name="is_opening_in_book",
        detected=False,
        confidence=0.0,
        detector_class=DetectorClass.META
    )
    
    opening_name = context.get("opening_name")
    move_number = context.get("move_number", 0)
    
    if opening_name and move_number <= 12:
        result.detected = True
        result.confidence = 0.90 if move_number <= 8 else 0.70
        result.details = {
            "opening_name": opening_name,
            "move_number": move_number
        }
    
    return result


def detect_trap_nearby(
    board: chess.Board,
    played_move: Optional[chess.Move],
    best_move: Optional[chess.Move],
    eval_before: int,
    eval_after: int,
    context: Dict
) -> DetectorResult:
    """Detect if a known trap is nearby"""
    result = DetectorResult(
        detector_name="is_known_trap_nearby",
        detected=False,
        confidence=0.0,
        detector_class=DetectorClass.META
    )
    
    trap_available = context.get("trap_available", False)
    trap_risk = context.get("trap_risk", False)
    trap_name = context.get("trap_name")
    
    if trap_available or trap_risk:
        result.detected = True
        result.confidence = 0.85
        result.details = {
            "trap_name": trap_name,
            "trap_available": trap_available,
            "trap_risk": trap_risk
        }
    
    return result


def detect_single_lesson(
    board: chess.Board,
    played_move: Optional[chess.Move],
    best_move: Optional[chess.Move],
    eval_before: int,
    eval_after: int,
    context: Dict
) -> DetectorResult:
    """Detect if there's a single clear lesson (high teachability)"""
    result = DetectorResult(
        detector_name="is_single_clear_lesson",
        detected=False,
        confidence=0.0,
        detector_class=DetectorClass.META
    )
    
    # This would be computed after running other detectors
    # For now, use eval loss as proxy
    eval_loss = abs(eval_after - eval_before)
    
    # Clear tactical mistake
    if eval_loss >= 100 and eval_loss <= 400:
        result.detected = True
        result.confidence = 0.80
        result.details = {
            "eval_loss": eval_loss,
            "reason": "clear_mistake"
        }
    
    return result


def detect_multi_cause(
    board: chess.Board,
    played_move: Optional[chess.Move],
    best_move: Optional[chess.Move],
    eval_before: int,
    eval_after: int,
    context: Dict
) -> DetectorResult:
    """Detect if position has multiple causes (harder to teach)"""
    result = DetectorResult(
        detector_name="is_multi_cause_position",
        detected=False,
        confidence=0.0,
        detector_class=DetectorClass.META
    )
    
    # This would be computed after running other detectors
    # Multiple tactical and strategic issues make teaching harder
    
    return result


def detect_endgame_principle(
    board: chess.Board,
    played_move: Optional[chess.Move],
    best_move: Optional[chess.Move],
    eval_before: int,
    eval_after: int,
    context: Dict
) -> DetectorResult:
    """Detect if endgame principle applies"""
    result = DetectorResult(
        detector_name="is_endgame_principle_position",
        detected=False,
        confidence=0.0,
        detector_class=DetectorClass.META
    )
    
    # Check material for endgame
    total_material = count_material(board, chess.WHITE) + count_material(board, chess.BLACK)
    
    # Endgame threshold
    if total_material <= 20:
        result.detected = True
        result.confidence = 0.80
        
        # Detect specific endgame type
        white_pawns = len(list(board.pieces(chess.PAWN, chess.WHITE)))
        black_pawns = len(list(board.pieces(chess.PAWN, chess.BLACK)))
        
        endgame_type = "general"
        if total_material <= 10:
            if white_pawns + black_pawns > 0:
                endgame_type = "pawn_endgame"
            else:
                endgame_type = "piece_endgame"
        
        result.details = {
            "total_material": total_material,
            "endgame_type": endgame_type
        }
    
    return result
