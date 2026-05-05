"""
Chess Brain - Detector Registry
================================

The DetectorRegistry manages all pattern detectors:
- Tactical detectors (forks, pins, hanging pieces, etc.)
- Strategic detectors (pawn structure, piece activity, etc.)
- Meta/Behavioral detectors (time trouble, tilt, etc.)

Each detector is a function that takes a position and returns
a DetectorResult. The registry runs relevant detectors based
on context and aggregates results into the PositionInsightObject.

V1 Detectors:
- 10 Tactical: fork, pin, hanging_piece, trapped_piece, back_rank,
               missed_mate, discovery, skewer, overload, removal
- 5 Strategic: isolated_pawn, passed_pawn, knight_outpost, 
               rook_activity, king_safety
- 3 Behavioral: time_trouble, impulse_move, tilt_detected
"""

import chess
import logging
from typing import Dict, List, Callable, Optional, Any, Tuple
from dataclasses import dataclass

from .schemas import DetectorResult
from .enums import (
    TacticalPattern,
    StrategicConcept,
    BehavioralPattern,
    MistakeCategory,
    GamePhase
)

logger = logging.getLogger(__name__)


# Type for detector functions
DetectorFunc = Callable[[chess.Board, str, str, Dict[str, Any]], DetectorResult]


@dataclass
class RegisteredDetector:
    """A detector registered with the registry."""
    detector_id: str
    name: str
    category: MistakeCategory
    pattern_type: str  # TacticalPattern, StrategicConcept, or BehavioralPattern value
    detector_func: DetectorFunc
    priority: int = 50  # Higher = run first
    requires_best_move: bool = False  # Needs Stockfish analysis
    phase_relevant: List[GamePhase] = None  # None = all phases


class DetectorRegistry:
    """
    Central registry for all pattern detectors.
    
    Usage:
        registry = DetectorRegistry()
        results = registry.run_all(board, user_move, best_move, context)
    """
    
    def __init__(self):
        self._tactical_detectors: Dict[str, RegisteredDetector] = {}
        self._strategic_detectors: Dict[str, RegisteredDetector] = {}
        self._behavioral_detectors: Dict[str, RegisteredDetector] = {}
        
        # Register all V1 detectors
        self._register_v1_detectors()
    
    def _register_v1_detectors(self):
        """Register the V1 detector set."""
        # === TACTICAL DETECTORS ===
        self.register_tactical(
            "fork_detector",
            "Fork Pattern Detector",
            TacticalPattern.MISSED_FORK.value,
            detect_fork,
            priority=90,
            requires_best_move=True
        )
        
        self.register_tactical(
            "pin_detector", 
            "Pin Pattern Detector",
            TacticalPattern.MISSED_PIN.value,
            detect_pin,
            priority=85,
            requires_best_move=True
        )
        
        self.register_tactical(
            "hanging_piece_detector",
            "Hanging Piece Detector",
            TacticalPattern.HANGING_PIECE.value,
            detect_hanging_piece,
            priority=95  # High priority - common issue
        )
        
        self.register_tactical(
            "trapped_piece_detector",
            "Trapped Piece Detector", 
            TacticalPattern.TRAPPED_PIECE.value,
            detect_trapped_piece,
            priority=70
        )
        
        self.register_tactical(
            "back_rank_detector",
            "Back Rank Threat Detector",
            TacticalPattern.MISSED_BACK_RANK.value,
            detect_back_rank,
            priority=80,
            requires_best_move=True
        )
        
        self.register_tactical(
            "mate_detector",
            "Missed Mate Detector",
            TacticalPattern.MISSED_MATE.value,
            detect_missed_mate,
            priority=100,  # Highest - most important
            requires_best_move=True
        )
        
        self.register_tactical(
            "discovery_detector",
            "Discovery Attack Detector",
            TacticalPattern.MISSED_DISCOVERY.value,
            detect_discovery,
            priority=75,
            requires_best_move=True
        )
        
        self.register_tactical(
            "skewer_detector",
            "Skewer Pattern Detector",
            TacticalPattern.MISSED_SKEWER.value,
            detect_skewer,
            priority=70,
            requires_best_move=True
        )
        
        self.register_tactical(
            "overload_detector",
            "Overloaded Piece Detector",
            TacticalPattern.MISSED_OVERLOAD.value,
            detect_overload,
            priority=65,
            requires_best_move=True
        )
        
        self.register_tactical(
            "removal_detector",
            "Removal of Guard Detector",
            TacticalPattern.MISSED_REMOVAL.value,
            detect_removal,
            priority=65,
            requires_best_move=True
        )
        
        # === STRATEGIC DETECTORS ===
        self.register_strategic(
            "isolated_pawn_detector",
            "Isolated Pawn Detector",
            StrategicConcept.ISOLATED_PAWN.value,
            detect_isolated_pawn,
            priority=60
        )
        
        self.register_strategic(
            "passed_pawn_detector",
            "Passed Pawn Detector",
            StrategicConcept.PASSED_PAWN.value,
            detect_passed_pawn,
            priority=70,
            phase_relevant=[GamePhase.LATE_MIDDLEGAME, GamePhase.EARLY_ENDGAME, 
                           GamePhase.ENDGAME, GamePhase.DEEP_ENDGAME]
        )
        
        self.register_strategic(
            "knight_outpost_detector",
            "Knight Outpost Detector",
            StrategicConcept.KNIGHT_OUTPOST.value,
            detect_knight_outpost,
            priority=50,
            phase_relevant=[GamePhase.EARLY_MIDDLEGAME, GamePhase.MIDDLEGAME,
                           GamePhase.LATE_MIDDLEGAME]
        )
        
        self.register_strategic(
            "rook_activity_detector",
            "Rook Activity Detector",
            StrategicConcept.ROOK_ACTIVITY.value,
            detect_rook_activity,
            priority=55
        )
        
        self.register_strategic(
            "king_safety_detector",
            "King Safety Detector",
            StrategicConcept.KING_SAFETY.value,
            detect_king_safety,
            priority=80,
            phase_relevant=[GamePhase.OPENING, GamePhase.EARLY_MIDDLEGAME,
                           GamePhase.MIDDLEGAME, GamePhase.LATE_MIDDLEGAME]
        )
        
        # === BEHAVIORAL DETECTORS ===
        self.register_behavioral(
            "time_trouble_detector",
            "Time Trouble Detector",
            BehavioralPattern.TIME_TROUBLE.value,
            detect_time_trouble,
            priority=90
        )
        
        self.register_behavioral(
            "impulse_move_detector",
            "Impulse Move Detector",
            BehavioralPattern.IMPULSE_MOVE.value,
            detect_impulse_move,
            priority=85
        )
        
        self.register_behavioral(
            "tilt_detector",
            "Tilt Detection",
            BehavioralPattern.TILT_DETECTED.value,
            detect_tilt,
            priority=80
        )
    
    def register_tactical(
        self,
        detector_id: str,
        name: str,
        pattern_type: str,
        func: DetectorFunc,
        priority: int = 50,
        requires_best_move: bool = False,
        phase_relevant: List[GamePhase] = None
    ):
        """Register a tactical pattern detector."""
        self._tactical_detectors[detector_id] = RegisteredDetector(
            detector_id=detector_id,
            name=name,
            category=MistakeCategory.TACTICAL,
            pattern_type=pattern_type,
            detector_func=func,
            priority=priority,
            requires_best_move=requires_best_move,
            phase_relevant=phase_relevant
        )
    
    def register_strategic(
        self,
        detector_id: str,
        name: str,
        pattern_type: str,
        func: DetectorFunc,
        priority: int = 50,
        requires_best_move: bool = False,
        phase_relevant: List[GamePhase] = None
    ):
        """Register a strategic concept detector."""
        self._strategic_detectors[detector_id] = RegisteredDetector(
            detector_id=detector_id,
            name=name,
            category=MistakeCategory.STRATEGIC,
            pattern_type=pattern_type,
            detector_func=func,
            priority=priority,
            requires_best_move=requires_best_move,
            phase_relevant=phase_relevant
        )
    
    def register_behavioral(
        self,
        detector_id: str,
        name: str,
        pattern_type: str,
        func: DetectorFunc,
        priority: int = 50,
        requires_best_move: bool = False,
        phase_relevant: List[GamePhase] = None
    ):
        """Register a behavioral pattern detector."""
        self._behavioral_detectors[detector_id] = RegisteredDetector(
            detector_id=detector_id,
            name=name,
            category=MistakeCategory.BEHAVIORAL,
            pattern_type=pattern_type,
            detector_func=func,
            priority=priority,
            requires_best_move=requires_best_move,
            phase_relevant=phase_relevant
        )
    
    def run_all(
        self,
        board: chess.Board,
        user_move: str,
        best_move: str,
        context: Dict[str, Any]
    ) -> Tuple[List[DetectorResult], List[DetectorResult], List[DetectorResult]]:
        """
        Run all registered detectors and return results.
        
        Args:
            board: Position BEFORE the user's move
            user_move: User's move in SAN notation
            best_move: Stockfish best move in SAN notation
            context: Additional context (time_spent, time_remaining, 
                    game_phase, consecutive_blunders, etc.)
        
        Returns:
            Tuple of (tactical_results, strategic_results, behavioral_results)
        """
        game_phase = context.get("game_phase", GamePhase.MIDDLEGAME)
        has_best_move = bool(best_move)
        
        tactical_results = []
        strategic_results = []
        behavioral_results = []
        
        # Run tactical detectors (sorted by priority)
        for det in sorted(
            self._tactical_detectors.values(),
            key=lambda x: x.priority,
            reverse=True
        ):
            if det.requires_best_move and not has_best_move:
                continue
            if det.phase_relevant and game_phase not in det.phase_relevant:
                continue
            
            try:
                result = det.detector_func(board, user_move, best_move, context)
                if result.detected:
                    tactical_results.append(result)
            except Exception as e:
                logger.warning(f"Detector {det.detector_id} failed: {e}")
        
        # Run strategic detectors
        for det in sorted(
            self._strategic_detectors.values(),
            key=lambda x: x.priority,
            reverse=True
        ):
            if det.requires_best_move and not has_best_move:
                continue
            if det.phase_relevant and game_phase not in det.phase_relevant:
                continue
            
            try:
                result = det.detector_func(board, user_move, best_move, context)
                if result.detected:
                    strategic_results.append(result)
            except Exception as e:
                logger.warning(f"Detector {det.detector_id} failed: {e}")
        
        # Run behavioral detectors
        for det in sorted(
            self._behavioral_detectors.values(),
            key=lambda x: x.priority,
            reverse=True
        ):
            try:
                result = det.detector_func(board, user_move, best_move, context)
                if result.detected:
                    behavioral_results.append(result)
            except Exception as e:
                logger.warning(f"Detector {det.detector_id} failed: {e}")
        
        return tactical_results, strategic_results, behavioral_results
    
    def run_tactical_only(
        self,
        board: chess.Board,
        user_move: str,
        best_move: str,
        context: Dict[str, Any]
    ) -> List[DetectorResult]:
        """Run only tactical detectors."""
        results, _, _ = self.run_all(board, user_move, best_move, context)
        return results
    
    def get_detector(self, detector_id: str) -> Optional[RegisteredDetector]:
        """Get a specific detector by ID."""
        return (
            self._tactical_detectors.get(detector_id) or
            self._strategic_detectors.get(detector_id) or
            self._behavioral_detectors.get(detector_id)
        )


# ==============================================================================
# TACTICAL DETECTORS
# ==============================================================================

def detect_fork(
    board: chess.Board,
    user_move: str,
    best_move: str,
    context: Dict[str, Any]
) -> DetectorResult:
    """
    Detect if the best move was a fork that user missed.
    A fork attacks two or more valuable pieces simultaneously.
    """
    result = DetectorResult(
        detector_id="fork_detector",
        detected=False,
        pattern_type=TacticalPattern.MISSED_FORK.value,
        category=MistakeCategory.TACTICAL.value
    )
    
    if not best_move or user_move == best_move:
        return result
    
    try:
        move = board.parse_san(best_move)
        board_after = board.copy()
        board_after.push(move)
        
        # Get the piece that moved
        piece = board_after.piece_at(move.to_square)
        if not piece:
            return result
        
        attacker_color = piece.color
        
        # Find what this piece attacks
        attacked_squares = board_after.attacks(move.to_square)
        valuable_targets = []
        target_pieces = []
        
        for sq in attacked_squares:
            target = board_after.piece_at(sq)
            if target and target.color != attacker_color:
                # Value the target
                piece_values = {
                    chess.KING: 100,
                    chess.QUEEN: 9,
                    chess.ROOK: 5,
                    chess.BISHOP: 3,
                    chess.KNIGHT: 3,
                    chess.PAWN: 1
                }
                value = piece_values.get(target.piece_type, 0)
                if value >= 3:  # At least minor piece
                    valuable_targets.append((sq, target, value))
                    target_pieces.append(chess.piece_name(target.piece_type))
        
        # Fork = attacking 2+ valuable pieces
        if len(valuable_targets) >= 2:
            total_value = sum(v[2] for v in valuable_targets)
            target_squares = [chess.square_name(v[0]) for v in valuable_targets]
            
            result.detected = True
            result.confidence = min(1.0, total_value / 15)  # Scale by value
            result.details = {
                "attacker": chess.piece_name(piece.piece_type),
                "attacker_square": chess.square_name(move.to_square),
                "targets": target_pieces,
                "target_squares": target_squares,
                "total_value": total_value
            }
            result.key_squares = [chess.square_name(move.to_square)] + target_squares
            result.teaching_hook = f"{chess.piece_name(piece.piece_type).title()} fork attacks {' and '.join(target_pieces)}"
    
    except Exception as e:
        logger.debug(f"Fork detection error: {e}")
    
    return result


def detect_pin(
    board: chess.Board,
    user_move: str,
    best_move: str,
    context: Dict[str, Any]
) -> DetectorResult:
    """
    Detect if the best move creates a pin that user missed.
    A pin restricts a piece because moving it would expose a more valuable piece.
    """
    result = DetectorResult(
        detector_id="pin_detector",
        detected=False,
        pattern_type=TacticalPattern.MISSED_PIN.value,
        category=MistakeCategory.TACTICAL.value
    )
    
    if not best_move or user_move == best_move:
        return result
    
    try:
        move = board.parse_san(best_move)
        piece = board.piece_at(move.from_square)

        # Pins are created by sliding pieces (bishop, rook, queen).
        if not piece or piece.piece_type not in [chess.BISHOP, chess.ROOK, chess.QUEEN]:
            return result

        board_after = board.copy()
        board_after.push(move)
        attacker_sq = move.to_square
        attacker_color = piece.color

        # Iterate the actual sliding-piece directions. The previous
        # implementation iterated chess.BB_RAYS[sq] which returns 64
        # bitboards of squares-between-this-and-other, not directions —
        # geometrically wrong, so the detector never fired.
        if piece.piece_type == chess.BISHOP:
            directions = [(1, 1), (1, -1), (-1, 1), (-1, -1)]
        elif piece.piece_type == chess.ROOK:
            directions = [(0, 1), (0, -1), (1, 0), (-1, 0)]
        else:  # QUEEN
            directions = [
                (0, 1), (0, -1), (1, 0), (-1, 0),
                (1, 1), (1, -1), (-1, 1), (-1, -1),
            ]

        piece_values = {
            chess.KING: 100, chess.QUEEN: 9, chess.ROOK: 5,
            chess.BISHOP: 3, chess.KNIGHT: 3, chess.PAWN: 1,
        }

        attacker_file = chess.square_file(attacker_sq)
        attacker_rank = chess.square_rank(attacker_sq)

        for df, dr in directions:
            front = None
            back = None
            f, r = attacker_file + df, attacker_rank + dr
            while 0 <= f <= 7 and 0 <= r <= 7:
                sq = chess.square(f, r)
                p = board_after.piece_at(sq)
                if p:
                    if front is None:
                        front = (sq, p)
                    else:
                        back = (sq, p)
                        break
                f += df
                r += dr

            if not (front and back):
                continue
            if front[1].color == attacker_color or back[1].color == attacker_color:
                continue

            front_val = piece_values.get(front[1].piece_type, 0)
            back_val = piece_values.get(back[1].piece_type, 0)
            if back_val <= front_val:
                continue

            # Real pin: attacker → enemy front piece → enemy more-valuable
            # back piece. Front piece is "pinned" — moving it exposes back.
            result.detected = True
            result.confidence = 0.9
            result.details = {
                "pinning_piece": chess.piece_name(piece.piece_type),
                "pinned_piece": chess.piece_name(front[1].piece_type),
                "pinned_square": chess.square_name(front[0]),
                "back_piece": chess.piece_name(back[1].piece_type),
                "back_square": chess.square_name(back[0]),
                # Legacy field names some old templates may still read.
                "attacker": chess.piece_name(piece.piece_type),
                "target": chess.piece_name(front[1].piece_type),
                "protected_piece": chess.piece_name(back[1].piece_type),
            }
            result.key_squares = [
                chess.square_name(attacker_sq),
                chess.square_name(front[0]),
                chess.square_name(back[0]),
            ]
            result.teaching_hook = (
                f"Pin the {chess.piece_name(front[1].piece_type)} "
                f"to the {chess.piece_name(back[1].piece_type)}"
            )
            return result

    except Exception as e:
        logger.debug(f"Pin detection error: {e}")

    return result


def detect_hanging_piece(
    board: chess.Board,
    user_move: str,
    best_move: str,
    context: Dict[str, Any]
) -> DetectorResult:
    """
    Detect if user's move left a piece hanging (undefended and attacked).
    This is one of the most common tactical errors.
    """
    result = DetectorResult(
        detector_id="hanging_piece_detector",
        detected=False,
        pattern_type=TacticalPattern.HANGING_PIECE.value,
        category=MistakeCategory.TACTICAL.value
    )
    
    try:
        move = board.parse_san(user_move)
        board_after = board.copy()
        board_after.push(move)
        
        # User just moved, now it's opponent's turn
        user_color = not board_after.turn  # Color of the player who just moved
        
        hanging_pieces = []
        
        for sq in chess.SQUARES:
            piece = board_after.piece_at(sq)
            if piece and piece.color == user_color and piece.piece_type != chess.KING:
                # Check if attacked and undefended
                is_attacked = board_after.is_attacked_by(not user_color, sq)
                is_defended = board_after.is_attacked_by(user_color, sq)
                
                if is_attacked and not is_defended:
                    piece_values = {
                        chess.QUEEN: 9,
                        chess.ROOK: 5,
                        chess.BISHOP: 3,
                        chess.KNIGHT: 3,
                        chess.PAWN: 1
                    }
                    value = piece_values.get(piece.piece_type, 0)
                    hanging_pieces.append((sq, piece, value))
        
        if hanging_pieces:
            # Find the most valuable hanging piece
            worst = max(hanging_pieces, key=lambda x: x[2])
            
            result.detected = True
            result.confidence = min(1.0, worst[2] / 5)
            result.details = {
                "hanging_piece": chess.piece_name(worst[1].piece_type),
                "hanging_square": chess.square_name(worst[0]),
                "piece_value": worst[2],
                "all_hanging": [
                    {"piece": chess.piece_name(p[1].piece_type), 
                     "square": chess.square_name(p[0])}
                    for p in hanging_pieces
                ]
            }
            result.key_squares = [chess.square_name(worst[0])]
            result.teaching_hook = f"The {chess.piece_name(worst[1].piece_type)} on {chess.square_name(worst[0])} is hanging"
    
    except Exception as e:
        logger.debug(f"Hanging piece detection error: {e}")
    
    return result


def detect_trapped_piece(
    board: chess.Board,
    user_move: str,
    best_move: str,
    context: Dict[str, Any]
) -> DetectorResult:
    """Detect if user moved a piece into a trap where it can't escape."""
    result = DetectorResult(
        detector_id="trapped_piece_detector",
        detected=False,
        pattern_type=TacticalPattern.TRAPPED_PIECE.value,
        category=MistakeCategory.TACTICAL.value
    )
    
    try:
        move = board.parse_san(user_move)
        piece = board.piece_at(move.from_square)
        
        if not piece or piece.piece_type in [chess.PAWN, chess.KING]:
            return result
        
        board_after = board.copy()
        board_after.push(move)
        
        moved_piece = board_after.piece_at(move.to_square)
        if not moved_piece:
            return result
        
        # Count legal moves for this piece
        legal_escapes = 0
        for legal_move in board_after.legal_moves:
            if legal_move.from_square == move.to_square:
                legal_escapes += 1
        
        # Check if the piece is attacked
        is_attacked = board_after.is_attacked_by(not moved_piece.color, move.to_square)
        
        # Trapped = attacked with no safe squares
        if is_attacked and legal_escapes == 0:
            result.detected = True
            result.confidence = 0.9
            result.details = {
                "trapped_piece": chess.piece_name(moved_piece.piece_type),
                "trapped_square": chess.square_name(move.to_square),
                "legal_escapes": 0
            }
            result.key_squares = [chess.square_name(move.to_square)]
            result.teaching_hook = f"The {chess.piece_name(moved_piece.piece_type)} is trapped!"
    
    except Exception as e:
        logger.debug(f"Trapped piece detection error: {e}")
    
    return result


def detect_back_rank(
    board: chess.Board,
    user_move: str,
    best_move: str,
    context: Dict[str, Any]
) -> DetectorResult:
    """Detect back rank mate threat or missed back rank mate."""
    result = DetectorResult(
        detector_id="back_rank_detector",
        detected=False,
        pattern_type=TacticalPattern.MISSED_BACK_RANK.value,
        category=MistakeCategory.TACTICAL.value
    )
    
    if not best_move or user_move == best_move:
        return result
    
    try:
        move = board.parse_san(best_move)
        board_after = board.copy()
        board_after.push(move)
        
        # Check if this leads to back rank mate
        if board_after.is_checkmate():
            # Find where the king is
            loser = board_after.turn  # The side that got mated
            king_sq = board_after.king(loser)
            king_rank = chess.square_rank(king_sq)
            
            # Back rank is rank 0 for black, rank 7 for white
            if (loser == chess.WHITE and king_rank == 0) or \
               (loser == chess.BLACK and king_rank == 7):
                result.detected = True
                result.confidence = 1.0
                result.details = {
                    "mate_move": best_move,
                    "king_square": chess.square_name(king_sq),
                    "pattern": "back_rank_mate"
                }
                result.key_squares = [chess.square_name(king_sq), chess.square_name(move.to_square)]
                result.teaching_hook = "Back rank mate was available!"
    
    except Exception as e:
        logger.debug(f"Back rank detection error: {e}")
    
    return result


def detect_missed_mate(
    board: chess.Board,
    user_move: str,
    best_move: str,
    context: Dict[str, Any]
) -> DetectorResult:
    """Detect if user missed a checkmate in 1 or 2 moves."""
    result = DetectorResult(
        detector_id="mate_detector",
        detected=False,
        pattern_type=TacticalPattern.MISSED_MATE.value,
        category=MistakeCategory.TACTICAL.value
    )
    
    if not best_move or user_move == best_move:
        return result
    
    try:
        move = board.parse_san(best_move)
        board_after = board.copy()
        board_after.push(move)
        
        # Check for mate in 1
        if board_after.is_checkmate():
            result.detected = True
            result.confidence = 1.0
            result.details = {
                "mate_in": 1,
                "mate_move": best_move
            }
            result.teaching_hook = f"Checkmate in one with {best_move}!"
            return result
        
        # Check for mate in 2 (look at all responses and see if we can mate)
        if board_after.is_check():
            mate_found = False
            for response in board_after.legal_moves:
                board_2 = board_after.copy()
                board_2.push(response)
                
                for final_move in board_2.legal_moves:
                    board_3 = board_2.copy()
                    board_3.push(final_move)
                    
                    if board_3.is_checkmate():
                        mate_found = True
                        result.detected = True
                        result.confidence = 0.9
                        result.details = {
                            "mate_in": 2,
                            "first_move": best_move
                        }
                        result.teaching_hook = f"Mate in 2 starting with {best_move}"
                        break
                if mate_found:
                    break
    
    except Exception as e:
        logger.debug(f"Mate detection error: {e}")
    
    return result


def detect_discovery(
    board: chess.Board,
    user_move: str,
    best_move: str,
    context: Dict[str, Any]
) -> DetectorResult:
    """Detect discovered attack patterns."""
    result = DetectorResult(
        detector_id="discovery_detector",
        detected=False,
        pattern_type=TacticalPattern.MISSED_DISCOVERY.value,
        category=MistakeCategory.TACTICAL.value
    )
    
    if not best_move or user_move == best_move:
        return result
    
    try:
        move = board.parse_san(best_move)
        
        # Get what piece moves and what's behind it
        moving_piece = board.piece_at(move.from_square)
        if not moving_piece:
            return result
        
        # Check if there's a sliding piece behind in any direction
        for attacker_sq in chess.SQUARES:
            attacker = board.piece_at(attacker_sq)
            if not attacker:
                continue
            if attacker.color != moving_piece.color:
                continue
            if attacker.piece_type not in [chess.BISHOP, chess.ROOK, chess.QUEEN]:
                continue
            
            # Check if moving piece was blocking this attacker
            attacks_before = board.attacks(attacker_sq)
            if move.from_square not in attacks_before:
                continue
            
            # Now check what opens up after the move
            board_after = board.copy()
            board_after.push(move)
            attacks_after = board_after.attacks(attacker_sq)
            
            # New attacks that weren't possible before
            new_attacks = attacks_after - attacks_before
            
            for target_sq in new_attacks:
                target = board_after.piece_at(target_sq)
                if target and target.color != attacker.color:
                    piece_values = {chess.QUEEN: 9, chess.ROOK: 5, 
                                   chess.BISHOP: 3, chess.KNIGHT: 3}
                    if target.piece_type in piece_values:
                        result.detected = True
                        result.confidence = 0.85
                        result.details = {
                            "discovered_attacker": chess.piece_name(attacker.piece_type),
                            "target": chess.piece_name(target.piece_type),
                            "target_square": chess.square_name(target_sq)
                        }
                        result.teaching_hook = "Discovered attack on the " + chess.piece_name(target.piece_type)
                        return result
    
    except Exception as e:
        logger.debug(f"Discovery detection error: {e}")
    
    return result


def detect_skewer(
    board: chess.Board,
    user_move: str,
    best_move: str,
    context: Dict[str, Any]
) -> DetectorResult:
    """
    Detect skewer patterns (reverse pin - valuable piece forced to move, exposing less valuable piece).
    A skewer attacks a valuable piece, forcing it to move and exposing a piece behind it.
    """
    result = DetectorResult(
        detector_id="skewer_detector",
        detected=False,
        pattern_type=TacticalPattern.MISSED_SKEWER.value,
        category=MistakeCategory.TACTICAL.value
    )
    
    if not best_move or user_move == best_move:
        return result
    
    try:
        move = board.parse_san(best_move)
        board_after = board.copy()
        board_after.push(move)
        
        # Get the attacking piece
        attacker = board_after.piece_at(move.to_square)
        if not attacker:
            return result
        
        # Only long-range pieces (bishop, rook, queen) can skewer
        if attacker.piece_type not in [chess.BISHOP, chess.ROOK, chess.QUEEN]:
            return result
        
        attacker_color = attacker.color
        attacker_square = move.to_square
        
        # Get squares along the attack line from the attacker
        attacked_squares = board_after.attacks(attacker_square)
        
        # Piece values for comparison
        piece_values = {
            chess.KING: 100,
            chess.QUEEN: 9,
            chess.ROOK: 5,
            chess.BISHOP: 3,
            chess.KNIGHT: 3,
            chess.PAWN: 1
        }
        
        # Look for skewer pattern: valuable piece in front, less valuable behind
        for front_square in attacked_squares:
            front_piece = board_after.piece_at(front_square)
            if not front_piece or front_piece.color == attacker_color:
                continue
            
            front_value = piece_values.get(front_piece.piece_type, 0)
            if front_value < 3:  # Front piece must be at least a minor piece
                continue
            
            # Get the direction from attacker to front piece
            file_diff = chess.square_file(front_square) - chess.square_file(attacker_square)
            rank_diff = chess.square_rank(front_square) - chess.square_rank(attacker_square)
            
            # Normalize to get direction
            if file_diff != 0:
                file_step = 1 if file_diff > 0 else -1
            else:
                file_step = 0
            
            if rank_diff != 0:
                rank_step = 1 if rank_diff > 0 else -1
            else:
                rank_step = 0
            
            # Check squares behind the front piece in the same direction
            current_file = chess.square_file(front_square) + file_step
            current_rank = chess.square_rank(front_square) + rank_step
            
            while 0 <= current_file <= 7 and 0 <= current_rank <= 7:
                behind_square = chess.square(current_file, current_rank)
                behind_piece = board_after.piece_at(behind_square)
                
                if behind_piece:
                    if behind_piece.color != attacker_color:
                        # Found potential skewer target
                        behind_value = piece_values.get(behind_piece.piece_type, 0)
                        
                        # Skewer: front piece is valuable and will move, exposing behind piece
                        # Typically front value >= behind value (king/queen in front, rook/piece behind)
                        if behind_value >= 1:  # Any piece worth taking
                            result.detected = True
                            result.confidence = min(1.0, (front_value + behind_value) / 15)
                            result.details = {
                                "attacker": chess.piece_name(attacker.piece_type),
                                "attacker_square": chess.square_name(attacker_square),
                                "front_piece": chess.piece_name(front_piece.piece_type),
                                "front_square": chess.square_name(front_square),
                                "behind_piece": chess.piece_name(behind_piece.piece_type),
                                "behind_square": chess.square_name(behind_square),
                                "front_value": front_value,
                                "behind_value": behind_value
                            }
                            result.key_squares = [
                                chess.square_name(attacker_square),
                                chess.square_name(front_square),
                                chess.square_name(behind_square)
                            ]
                            result.teaching_hook = f"Skewer: {chess.piece_name(attacker.piece_type)} attacks {chess.piece_name(front_piece.piece_type)}, winning {chess.piece_name(behind_piece.piece_type)}"
                            return result
                    break  # Hit a piece, stop checking this line
                
                # Move to next square in the direction
                current_file += file_step
                current_rank += rank_step
    
    except Exception as e:
        logger.debug(f"Skewer detection error: {e}")
    
    return result


def detect_overload(
    board: chess.Board,
    user_move: str,
    best_move: str,
    context: Dict[str, Any]
) -> DetectorResult:
    """
    Detect overloaded piece patterns.
    An overloaded piece is defending multiple pieces/squares and can't fulfill all duties.
    """
    result = DetectorResult(
        detector_id="overload_detector",
        detected=False,
        pattern_type=TacticalPattern.MISSED_OVERLOAD.value,
        category=MistakeCategory.TACTICAL.value
    )
    
    if not best_move or user_move == best_move:
        return result
    
    try:
        move = board.parse_san(best_move)
        board_after = board.copy()
        board_after.push(move)
        
        # Get the attacking side
        attacking_color = not board_after.turn
        defending_color = board_after.turn
        
        # Find pieces that are being attacked in the position after best_move
        attacked_piece_square = None
        
        # Check if best_move attacks a piece
        if move.to_square:
            # Check squares attacked by the moved piece
            moved_piece_attacks = board_after.attacks(move.to_square)
            
            for sq in moved_piece_attacks:
                piece_at_sq = board_after.piece_at(sq)
                if piece_at_sq and piece_at_sq.color == defending_color:
                    attacked_piece_square = sq
                    break
        
        if not attacked_piece_square:
            return result
        
        # Find what's defending the attacked piece
        defenders = []
        for defender_sq in chess.SQUARES:
            defender = board_after.piece_at(defender_sq)
            if not defender or defender.color != defending_color:
                continue
            
            # Check if this piece defends the attacked piece
            if board_after.is_attacked_by(defending_color, attacked_piece_square):
                defender_attacks = board_after.attacks(defender_sq)
                if attacked_piece_square in defender_attacks:
                    defenders.append((defender_sq, defender))
        
        # Check if any defender is overloaded (defending multiple pieces)
        for defender_sq, defender in defenders:
            defended_pieces = []
            defender_attacks = board_after.attacks(defender_sq)
            
            for sq in defender_attacks:
                piece = board_after.piece_at(sq)
                if piece and piece.color == defending_color and sq != defender_sq:
                    # Check if this piece is under attack
                    if board_after.is_attacked_by(attacking_color, sq):
                        defended_pieces.append((sq, piece))
            
            # Overload detected if defender is protecting 2+ pieces that are under attack
            if len(defended_pieces) >= 2:
                piece_values = {
                    chess.QUEEN: 9, chess.ROOK: 5,
                    chess.BISHOP: 3, chess.KNIGHT: 3, chess.PAWN: 1
                }
                
                total_value = sum(piece_values.get(p[1].piece_type, 0) for p in defended_pieces)
                
                result.detected = True
                result.confidence = min(1.0, len(defended_pieces) / 3.0)
                result.details = {
                    "defender": chess.piece_name(defender.piece_type),
                    "defender_square": chess.square_name(defender_sq),
                    "defended_count": len(defended_pieces),
                    "defended_pieces": [
                        {
                            "piece": chess.piece_name(p[1].piece_type),
                            "square": chess.square_name(p[0])
                        } for p in defended_pieces
                    ],
                    "total_value": total_value
                }
                result.key_squares = [chess.square_name(defender_sq)] + [
                    chess.square_name(p[0]) for p in defended_pieces
                ]
                
                defended_names = [chess.piece_name(p[1].piece_type) for p in defended_pieces[:2]]
                result.teaching_hook = f"{chess.piece_name(defender.piece_type)} is overloaded defending {' and '.join(defended_names)}"
                return result
    
    except Exception as e:
        logger.debug(f"Overload detection error: {e}")
    
    return result


def detect_removal(
    board: chess.Board,
    user_move: str,
    best_move: str,
    context: Dict[str, Any]
) -> DetectorResult:
    """
    Detect removal of the guard patterns.
    This tactic involves capturing or deflecting the piece defending a valuable target.
    """
    result = DetectorResult(
        detector_id="removal_detector",
        detected=False,
        pattern_type=TacticalPattern.MISSED_REMOVAL.value,
        category=MistakeCategory.TACTICAL.value
    )
    
    if not best_move or user_move == best_move:
        return result
    
    try:
        move = board.parse_san(best_move)
        board_before = board.copy()
        board_after = board.copy()
        board_after.push(move)
        
        attacking_color = not board_after.turn
        defending_color = board_after.turn
        
        # Piece values
        piece_values = {
            chess.QUEEN: 9, chess.ROOK: 5,
            chess.BISHOP: 3, chess.KNIGHT: 3, chess.PAWN: 1
        }
        
        # Check if best_move captures a piece (potential defender)
        if not move.to_square:
            return result
        
        # See what was on the target square before the move
        captured_piece = board_before.piece_at(move.to_square)
        
        if not captured_piece or captured_piece.color != defending_color:
            return result
        
        # Now check if removing this piece exposes other pieces
        # Look for pieces that were defended by the captured piece
        exposed_targets = []
        
        for sq in chess.SQUARES:
            piece = board_after.piece_at(sq)
            if not piece or piece.color != defending_color:
                continue
            
            # Check if this piece is now under attack after the capture
            is_attacked_after = board_after.is_attacked_by(attacking_color, sq)
            is_defended_after = board_after.is_attacked_by(defending_color, sq)
            
            # Check if it was defended before by the captured piece
            defender_attacks_before = board_before.attacks(move.to_square)
            was_defended_by_captured = sq in defender_attacks_before
            
            # If piece was defended by captured piece and is now hanging or weak
            if was_defended_by_captured and is_attacked_after:
                # Check if it's now hanging (attacked but not defended)
                if not is_defended_after or not board_after.is_defended(sq):
                    value = piece_values.get(piece.piece_type, 0)
                    if value >= 1:  # At least a pawn
                        exposed_targets.append((sq, piece, value))
        
        # If removing the defender exposes valuable pieces
        if exposed_targets:
            # Sort by value
            exposed_targets.sort(key=lambda x: x[2], reverse=True)
            best_target = exposed_targets[0]
            
            total_value = sum(t[2] for t in exposed_targets)
            
            result.detected = True
            result.confidence = min(1.0, total_value / 10.0)
            result.details = {
                "removed_defender": chess.piece_name(captured_piece.piece_type),
                "removed_square": chess.square_name(move.to_square),
                "exposed_piece": chess.piece_name(best_target[1].piece_type),
                "exposed_square": chess.square_name(best_target[0]),
                "exposed_value": best_target[2],
                "total_exposed": len(exposed_targets)
            }
            result.key_squares = [
                chess.square_name(move.to_square),
                chess.square_name(best_target[0])
            ]
            result.teaching_hook = f"Remove the {chess.piece_name(captured_piece.piece_type)} to win the {chess.piece_name(best_target[1].piece_type)}"
            return result
        
        # Alternative: Check for deflection (forcing the defender away)
        # If best_move forces a piece to move, exposing something else
        if board_after.is_check():
            # King must move, might expose other pieces
            king_sq = board_after.king(defending_color)
            # Check what the king was defending
            king_defends_before = board_before.attacks(king_sq)
            
            for sq in king_defends_before:
                piece = board_after.piece_at(sq)
                if piece and piece.color == defending_color:
                    # Check if now under attack
                    if board_after.is_attacked_by(attacking_color, sq):
                        value = piece_values.get(piece.piece_type, 0)
                        if value >= 3:  # Significant piece
                            result.detected = True
                            result.confidence = 0.8
                            result.details = {
                                "deflection_type": "check_deflection",
                                "removed_defender": "king",
                                "exposed_piece": chess.piece_name(piece.piece_type),
                                "exposed_square": chess.square_name(sq)
                            }
                            result.key_squares = [
                                chess.square_name(move.to_square),
                                chess.square_name(sq)
                            ]
                            result.teaching_hook = f"Check deflects the king, winning the {chess.piece_name(piece.piece_type)}"
                            return result
    
    except Exception as e:
        logger.debug(f"Removal detection error: {e}")
    
    return result


# ==============================================================================
# STRATEGIC DETECTORS  
# ==============================================================================

def detect_isolated_pawn(
    board: chess.Board,
    user_move: str,
    best_move: str,
    context: Dict[str, Any]
) -> DetectorResult:
    """Detect isolated pawn creation or exploitation."""
    result = DetectorResult(
        detector_id="isolated_pawn_detector",
        detected=False,
        pattern_type=StrategicConcept.ISOLATED_PAWN.value,
        category=MistakeCategory.STRATEGIC.value
    )
    
    try:
        move = board.parse_san(user_move)
        board_after = board.copy()
        board_after.push(move)
        
        user_color = not board_after.turn
        
        # Check for isolated pawns
        isolated_pawns = []
        
        for sq in chess.SQUARES:
            piece = board_after.piece_at(sq)
            if piece and piece.piece_type == chess.PAWN and piece.color == user_color:
                file = chess.square_file(sq)
                
                # Check adjacent files for friendly pawns
                has_neighbor = False
                for adj_file in [file - 1, file + 1]:
                    if 0 <= adj_file <= 7:
                        for rank in range(8):
                            adj_sq = chess.square(adj_file, rank)
                            adj_piece = board_after.piece_at(adj_sq)
                            if adj_piece and adj_piece.piece_type == chess.PAWN and adj_piece.color == user_color:
                                has_neighbor = True
                                break
                    if has_neighbor:
                        break
                
                if not has_neighbor:
                    isolated_pawns.append(chess.square_name(sq))
        
        if isolated_pawns:
            result.detected = True
            result.confidence = 0.7
            result.details = {
                "isolated_pawns": isolated_pawns
            }
            result.key_squares = isolated_pawns
            if len(isolated_pawns) == 1:
                result.teaching_hook = f"Isolated pawn on {isolated_pawns[0]}"
            else:
                result.teaching_hook = "Multiple isolated pawns"
    
    except Exception as e:
        logger.debug(f"Isolated pawn detection error: {e}")
    
    return result


def detect_passed_pawn(
    board: chess.Board,
    user_move: str,
    best_move: str,
    context: Dict[str, Any]
) -> DetectorResult:
    """Detect passed pawn creation or advancement."""
    result = DetectorResult(
        detector_id="passed_pawn_detector",
        detected=False,
        pattern_type=StrategicConcept.PASSED_PAWN.value,
        category=MistakeCategory.STRATEGIC.value
    )
    
    try:
        move = board.parse_san(user_move)
        board_after = board.copy()
        board_after.push(move)
        
        user_color = not board_after.turn
        enemy_color = board_after.turn
        
        passed_pawns = []
        
        for sq in chess.SQUARES:
            piece = board_after.piece_at(sq)
            if piece and piece.piece_type == chess.PAWN and piece.color == user_color:
                file = chess.square_file(sq)
                rank = chess.square_rank(sq)
                
                # Check if no enemy pawns can block or capture
                is_passed = True
                
                # Direction depends on color
                if user_color == chess.WHITE:
                    check_ranks = range(rank + 1, 8)
                else:
                    check_ranks = range(rank - 1, -1, -1)
                
                for check_file in [file - 1, file, file + 1]:
                    if 0 <= check_file <= 7:
                        for check_rank in check_ranks:
                            check_sq = chess.square(check_file, check_rank)
                            check_piece = board_after.piece_at(check_sq)
                            if check_piece and check_piece.piece_type == chess.PAWN and check_piece.color == enemy_color:
                                is_passed = False
                                break
                    if not is_passed:
                        break
                
                if is_passed:
                    passed_pawns.append({
                        "square": chess.square_name(sq),
                        "rank": rank
                    })
        
        if passed_pawns:
            result.detected = True
            result.confidence = 0.8
            result.details = {
                "passed_pawns": passed_pawns
            }
            result.key_squares = [p["square"] for p in passed_pawns]
            
            # Teaching hook based on advancement
            most_advanced = max(passed_pawns, key=lambda p: p["rank"] if user_color == chess.WHITE else 7 - p["rank"])
            result.teaching_hook = f"Passed pawn on {most_advanced['square']} - push it!"
    
    except Exception as e:
        logger.debug(f"Passed pawn detection error: {e}")
    
    return result


def detect_knight_outpost(
    board: chess.Board,
    user_move: str,
    best_move: str,
    context: Dict[str, Any]
) -> DetectorResult:
    """Detect knight outpost opportunities."""
    result = DetectorResult(
        detector_id="knight_outpost_detector",
        detected=False,
        pattern_type=StrategicConcept.KNIGHT_OUTPOST.value,
        category=MistakeCategory.STRATEGIC.value
    )
    
    # V1: Basic outpost detection
    # An outpost is a square that can't be attacked by enemy pawns
    
    return result


def detect_rook_activity(
    board: chess.Board,
    user_move: str,
    best_move: str,
    context: Dict[str, Any]
) -> DetectorResult:
    """Detect rook placement issues or opportunities."""
    result = DetectorResult(
        detector_id="rook_activity_detector",
        detected=False,
        pattern_type=StrategicConcept.ROOK_ACTIVITY.value,
        category=MistakeCategory.STRATEGIC.value
    )
    
    try:
        board_after = board.copy()
        move = board.parse_san(user_move)
        board_after.push(move)
        
        user_color = not board_after.turn
        
        # Check if rooks are on open files
        rook_positions = []
        
        for sq in chess.SQUARES:
            piece = board_after.piece_at(sq)
            if piece and piece.piece_type == chess.ROOK and piece.color == user_color:
                file = chess.square_file(sq)
                
                # Count pawns on this file
                pawns_on_file = 0
                for rank in range(8):
                    file_sq = chess.square(file, rank)
                    file_piece = board_after.piece_at(file_sq)
                    if file_piece and file_piece.piece_type == chess.PAWN:
                        pawns_on_file += 1
                
                rook_positions.append({
                    "square": chess.square_name(sq),
                    "file": chess.FILE_NAMES[file],
                    "pawns_on_file": pawns_on_file,
                    "is_open": pawns_on_file == 0,
                    "is_half_open": pawns_on_file == 1
                })
        
        # Check if rooks could be better placed
        inactive_rooks = [r for r in rook_positions if r["pawns_on_file"] > 1]
        
        if inactive_rooks:
            result.detected = True
            result.confidence = 0.6
            result.details = {
                "rook_positions": rook_positions,
                "inactive_rooks": inactive_rooks
            }
            result.teaching_hook = "Rooks belong on open files!"
    
    except Exception as e:
        logger.debug(f"Rook activity detection error: {e}")
    
    return result


def detect_king_safety(
    board: chess.Board,
    user_move: str,
    best_move: str,
    context: Dict[str, Any]
) -> DetectorResult:
    """Detect king safety issues."""
    result = DetectorResult(
        detector_id="king_safety_detector",
        detected=False,
        pattern_type=StrategicConcept.KING_SAFETY.value,
        category=MistakeCategory.STRATEGIC.value
    )
    
    try:
        move = board.parse_san(user_move)
        board_after = board.copy()
        board_after.push(move)
        
        user_color = not board_after.turn
        king_sq = board_after.king(user_color)
        
        if not king_sq:
            return result
        
        # Check king safety factors
        king_file = chess.square_file(king_sq)
        king_rank = chess.square_rank(king_sq)
        
        safety_issues = []
        
        # Check if castled
        is_castled = king_file in [6, 2]  # g1/g8 or c1/c8 after castling
        
        # Check pawn shield
        shield_squares = []
        if user_color == chess.WHITE:
            shield_ranks = [king_rank + 1] if king_rank < 7 else []
        else:
            shield_ranks = [king_rank - 1] if king_rank > 0 else []
        
        for r in shield_ranks:
            for f in [king_file - 1, king_file, king_file + 1]:
                if 0 <= f <= 7:
                    shield_squares.append(chess.square(f, r))
        
        missing_shield = 0
        for sq in shield_squares:
            piece = board_after.piece_at(sq)
            if not piece or piece.piece_type != chess.PAWN or piece.color != user_color:
                missing_shield += 1
        
        if missing_shield >= 2 and not is_castled:
            safety_issues.append("weak_pawn_shield")
        
        # Check attackers near king
        attackers_near = 0
        for sq in chess.SQUARES:
            piece = board_after.piece_at(sq)
            if piece and piece.color != user_color:
                # Check if piece attacks squares near king
                attacks = board_after.attacks(sq)
                for near_sq in [king_sq] + list(chess.SquareSet(chess.BB_KING_ATTACKS[king_sq])):
                    if near_sq in attacks:
                        attackers_near += 1
                        break
        
        if attackers_near >= 3:
            safety_issues.append("many_attackers")
        
        if safety_issues:
            result.detected = True
            result.confidence = 0.7
            result.details = {
                "king_square": chess.square_name(king_sq),
                "is_castled": is_castled,
                "missing_shield": missing_shield,
                "attackers_near": attackers_near,
                "issues": safety_issues
            }
            result.key_squares = [chess.square_name(king_sq)]
            result.teaching_hook = "King safety needs attention"
    
    except Exception as e:
        logger.debug(f"King safety detection error: {e}")
    
    return result


# ==============================================================================
# BEHAVIORAL DETECTORS
# ==============================================================================

def detect_time_trouble(
    board: chess.Board,
    user_move: str,
    best_move: str,
    context: Dict[str, Any]
) -> DetectorResult:
    """Detect if user is in time trouble."""
    result = DetectorResult(
        detector_id="time_trouble_detector",
        detected=False,
        pattern_type=BehavioralPattern.TIME_TROUBLE.value,
        category=MistakeCategory.BEHAVIORAL.value
    )
    
    time_remaining = context.get("time_remaining")
    
    if time_remaining is not None and time_remaining < 60:
        result.detected = True
        result.confidence = 1.0 if time_remaining < 30 else 0.8
        result.details = {
            "time_remaining": time_remaining,
            "severity": "critical" if time_remaining < 30 else "warning"
        }
        result.teaching_hook = f"Only {int(time_remaining)} seconds left!"
    
    return result


def detect_impulse_move(
    board: chess.Board,
    user_move: str,
    best_move: str,
    context: Dict[str, Any]
) -> DetectorResult:
    """Detect very fast moves that might be impulsive."""
    result = DetectorResult(
        detector_id="impulse_move_detector",
        detected=False,
        pattern_type=BehavioralPattern.IMPULSE_MOVE.value,
        category=MistakeCategory.BEHAVIORAL.value
    )
    
    time_spent = context.get("time_spent")
    move_number = context.get("move_number", 1)
    
    # Impulse threshold varies by phase
    threshold = 2.0 if move_number > 10 else 1.0
    
    if time_spent is not None and time_spent < threshold and move_number > 5:
        result.detected = True
        result.confidence = 0.9 if time_spent < 1.0 else 0.7
        result.details = {
            "time_spent": time_spent,
            "threshold": threshold,
            "move_number": move_number
        }
        result.teaching_hook = "Quick move - did you check for threats?"
    
    return result


def detect_tilt(
    board: chess.Board,
    user_move: str,
    best_move: str,
    context: Dict[str, Any]
) -> DetectorResult:
    """Detect if user might be tilting (multiple blunders in a row)."""
    result = DetectorResult(
        detector_id="tilt_detector",
        detected=False,
        pattern_type=BehavioralPattern.TILT_DETECTED.value,
        category=MistakeCategory.BEHAVIORAL.value
    )
    
    consecutive_blunders = context.get("consecutive_blunders", 0)
    
    if consecutive_blunders >= 2:
        result.detected = True
        result.confidence = min(1.0, consecutive_blunders / 3)
        result.details = {
            "consecutive_blunders": consecutive_blunders
        }
        result.teaching_hook = "Let's slow down and refocus"
    
    return result


# ==============================================================================
# GLOBAL REGISTRY INSTANCE
# ==============================================================================

# Create a singleton registry instance
_registry_instance = None

def get_detector_registry() -> DetectorRegistry:
    """Get the global detector registry instance."""
    global _registry_instance
    if _registry_instance is None:
        _registry_instance = DetectorRegistry()
        
        # Register advanced detectors (strategic + endgame)
        try:
            from .advanced_detectors import register_advanced_detectors
            register_advanced_detectors(_registry_instance)
        except Exception as e:
            logger.warning(f"Could not register advanced detectors: {e}")
    
    return _registry_instance
