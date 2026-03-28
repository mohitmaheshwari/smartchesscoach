"""
Reflection Predicates - Board Fact Detection
=============================================
Version: v1
Deterministic predicates that analyze board state.
Each predicate returns True/False based on position facts.
Used by Quick Tag Registry and Awareness Gap Rules.
"""

import chess
from typing import Dict, Optional, Tuple, List, Any
import logging

logger = logging.getLogger(__name__)


def safe_parse_fen(fen: str) -> Optional[chess.Board]:
    """Safely parse FEN, return None if invalid."""
    try:
        board = chess.Board(fen)
        return board
    except Exception as e:
        logger.warning(f"Invalid FEN: {fen}, error: {e}")
        return None


def safe_parse_move(board: chess.Board, move_san: str) -> Optional[chess.Move]:
    """Safely parse SAN move, return None if invalid."""
    try:
        return board.parse_san(move_san)
    except Exception as e:
        logger.warning(f"Invalid move: {move_san}, error: {e}")
        return None


class BoardFacts:
    """
    Container for all board facts relevant to reflection.
    Computed once per position, used by multiple systems.
    """
    
    def __init__(
        self,
        fen_before: str,
        user_move: str,
        best_move: str,
        cp_loss: float = 0,
        time_remaining_sec: Optional[int] = None,
        move_number: int = 0
    ):
        self.fen_before = fen_before
        self.user_move = user_move
        self.best_move = best_move
        self.cp_loss = cp_loss
        self.time_remaining_sec = time_remaining_sec
        self.move_number = move_number
        
        # Parse board
        self.board = safe_parse_fen(fen_before)
        self.user_move_obj = None
        self.best_move_obj = None
        
        if self.board:
            self.user_move_obj = safe_parse_move(self.board, user_move)
            self.best_move_obj = safe_parse_move(self.board, best_move) if best_move else None
        
        # Compute all facts once
        self._compute_facts()
    
    def _compute_facts(self):
        """Compute all relevant facts about the position."""
        if not self.board or not self.user_move_obj:
            self._set_default_facts()
            return
        
        # Game phase
        self.is_opening = self.move_number <= 12
        self.is_middlegame = 12 < self.move_number <= 35
        self.is_endgame = self.move_number > 35
        
        # Time pressure
        self.time_pressure = self.time_remaining_sec is not None and self.time_remaining_sec < 60
        self.severe_time_pressure = self.time_remaining_sec is not None and self.time_remaining_sec < 30
        
        # Before user's move
        self.user_in_check_before = self.board.is_check()
        self.user_color = self.board.turn
        self.opponent_color = not self.user_color
        
        # Opponent threats before move
        self._compute_opponent_threats()
        
        # What user's move does
        self._compute_user_move_effects()
        
        # What best move would have done
        self._compute_best_move_effects()
        
        # Comparisons
        self._compute_comparisons()
    
    def _set_default_facts(self):
        """Set default values when position can't be parsed."""
        self.is_opening = False
        self.is_middlegame = True
        self.is_endgame = False
        self.time_pressure = False
        self.severe_time_pressure = False
        self.user_in_check_before = False
        self.user_color = chess.WHITE
        self.opponent_color = chess.BLACK
        
        # Opponent threats
        self.opponent_has_check = False
        self.opponent_has_capture = False
        self.opponent_has_forcing_move = False
        self.opponent_threat_squares = set()
        self.opponent_attacking_pieces = []
        
        # User move effects
        self.user_move_is_capture = False
        self.user_move_gives_check = False
        self.user_piece_becomes_hanging = False
        self.user_creates_threat = False
        self.user_attacks_hanging = False
        
        # Best move effects
        self.best_move_is_capture = False
        self.best_move_gives_check = False
        self.best_move_wins_material = False
        self.best_attacks_hanging = False
        
        # Comparisons
        self.user_chose_attack_over_defense = False
        self.user_ignored_forcing = False
        self.user_defended_non_threat = False
        self.simple_forcing_missed = False
    
    def _compute_opponent_threats(self):
        """Compute what threats opponent has."""
        self.opponent_has_check = False
        self.opponent_has_capture = False
        self.opponent_has_forcing_move = False
        self.opponent_threat_squares = set()
        self.opponent_attacking_pieces = []
        
        if not self.board:
            return
            
        # Simulate opponent's turn
        test_board = self.board.copy()
        test_board.turn = self.opponent_color
        
        for move in test_board.legal_moves:
            # Check if gives check to user
            test_board.push(move)
            if test_board.is_check():
                self.opponent_has_check = True
            test_board.pop()
            
            # Check if captures user's piece
            if test_board.is_capture(move):
                self.opponent_has_capture = True
                captured_square = move.to_square
                self.opponent_threat_squares.add(chess.square_name(captured_square))
        
        self.opponent_has_forcing_move = self.opponent_has_check or self.opponent_has_capture
    
    def _compute_user_move_effects(self):
        """Compute what user's move does."""
        self.user_move_is_capture = False
        self.user_move_gives_check = False
        self.user_piece_becomes_hanging = False
        self.user_creates_threat = False
        self.user_attacks_hanging = False
        
        if not self.board or not self.user_move_obj:
            return
        
        # Is it a capture?
        self.user_move_is_capture = self.board.is_capture(self.user_move_obj)
        
        # Apply move and check effects
        board_after = self.board.copy()
        board_after.push(self.user_move_obj)
        
        # Does it give check?
        self.user_move_gives_check = board_after.is_check()
        
        # Is the moved piece now hanging?
        to_square = self.user_move_obj.to_square
        attackers = board_after.attackers(self.opponent_color, to_square)
        defenders = board_after.attackers(self.user_color, to_square)
        self.user_piece_becomes_hanging = len(attackers) > 0 and len(defenders) == 0
        
        # Does user attack any opponent piece?
        for square in chess.SQUARES:
            piece = board_after.piece_at(square)
            if piece and piece.color == self.opponent_color:
                if board_after.is_attacked_by(self.user_color, square):
                    self.user_creates_threat = True
                    # Check if that piece is hanging (undefended)
                    defenders = board_after.attackers(self.opponent_color, square)
                    if len(defenders) == 0:
                        self.user_attacks_hanging = True
    
    def _compute_best_move_effects(self):
        """Compute what best move would have done."""
        self.best_move_is_capture = False
        self.best_move_gives_check = False
        self.best_move_wins_material = False
        self.best_attacks_hanging = False
        
        if not self.board or not self.best_move_obj:
            return
        
        # Is best move a capture?
        self.best_move_is_capture = self.board.is_capture(self.best_move_obj)
        
        # Apply best move
        board_after = self.board.copy()
        board_after.push(self.best_move_obj)
        
        # Does best move give check?
        self.best_move_gives_check = board_after.is_check()
        
        # Does best move attack hanging piece?
        to_square = self.best_move_obj.to_square
        for square in chess.SQUARES:
            piece = board_after.piece_at(square)
            if piece and piece.color == self.opponent_color:
                if board_after.is_attacked_by(self.user_color, square):
                    defenders = board_after.attackers(self.opponent_color, square)
                    if len(defenders) == 0:
                        self.best_attacks_hanging = True
        
        # Estimate if best move wins material
        if self.best_move_is_capture:
            captured = self.board.piece_at(self.best_move_obj.to_square)
            if captured and captured.piece_type in [chess.QUEEN, chess.ROOK, chess.BISHOP, chess.KNIGHT]:
                self.best_move_wins_material = True
    
    def _compute_comparisons(self):
        """Compare user's choice vs best move."""
        # User chose attack when they should have defended
        self.user_chose_attack_over_defense = (
            self.user_creates_threat and 
            self.opponent_has_forcing_move and 
            not self.user_move_is_capture
        )
        
        # User ignored opponent's forcing move
        self.user_ignored_forcing = (
            self.opponent_has_forcing_move and 
            not self.user_in_check_before and
            self.cp_loss > 100
        )
        
        # User defended something that wasn't under threat
        # (approximation - if user didn't capture and didn't attack, they likely defended)
        self.user_defended_non_threat = (
            not self.user_move_is_capture and
            not self.user_creates_threat and
            not self.opponent_has_forcing_move and
            self.cp_loss > 100
        )
        
        # Simple forcing move missed (check or winning capture)
        self.simple_forcing_missed = (
            (self.best_move_gives_check or self.best_move_wins_material) and
            not self.user_move_gives_check and
            not self.user_move_is_capture
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Export facts as dictionary for storage/debugging."""
        return {
            "is_opening": self.is_opening,
            "is_middlegame": self.is_middlegame,
            "is_endgame": self.is_endgame,
            "time_pressure": self.time_pressure,
            "severe_time_pressure": self.severe_time_pressure,
            "user_in_check_before": self.user_in_check_before,
            "opponent_has_check": self.opponent_has_check,
            "opponent_has_capture": self.opponent_has_capture,
            "opponent_has_forcing_move": self.opponent_has_forcing_move,
            "user_move_is_capture": self.user_move_is_capture,
            "user_move_gives_check": self.user_move_gives_check,
            "user_piece_becomes_hanging": self.user_piece_becomes_hanging,
            "user_creates_threat": self.user_creates_threat,
            "user_attacks_hanging": self.user_attacks_hanging,
            "best_move_is_capture": self.best_move_is_capture,
            "best_move_gives_check": self.best_move_gives_check,
            "best_move_wins_material": self.best_move_wins_material,
            "best_attacks_hanging": self.best_attacks_hanging,
            "user_chose_attack_over_defense": self.user_chose_attack_over_defense,
            "user_ignored_forcing": self.user_ignored_forcing,
            "user_defended_non_threat": self.user_defended_non_threat,
            "simple_forcing_missed": self.simple_forcing_missed,
        }


# ============================================
# PREDICATE FUNCTIONS (used by tag registry)
# ============================================

def opponent_has_immediate_check(facts: BoardFacts) -> bool:
    """Opponent had check available after user's move."""
    return facts.opponent_has_check


def opponent_has_winning_capture(facts: BoardFacts) -> bool:
    """Opponent had a winning capture available."""
    return facts.opponent_has_capture


def user_was_in_check(facts: BoardFacts) -> bool:
    """User was in check before making move."""
    return facts.user_in_check_before


def time_pressure_detected(facts: BoardFacts) -> bool:
    """User had less than 60 seconds."""
    return facts.time_pressure


def severe_time_pressure(facts: BoardFacts) -> bool:
    """User had less than 30 seconds."""
    return facts.severe_time_pressure


def user_piece_left_hanging(facts: BoardFacts) -> bool:
    """User's moved piece is now hanging."""
    return facts.user_piece_becomes_hanging


def is_opening_phase(facts: BoardFacts) -> bool:
    """Move is in opening phase (moves 1-12)."""
    return facts.is_opening


def user_attacked_instead_of_defending(facts: BoardFacts) -> bool:
    """User chose to attack while under threat."""
    return facts.user_chose_attack_over_defense


def user_ignored_forcing_reply(facts: BoardFacts) -> bool:
    """User ignored opponent's forcing move."""
    return facts.user_ignored_forcing


def user_defended_phantom_threat(facts: BoardFacts) -> bool:
    """User defended something that wasn't threatened."""
    return facts.user_defended_non_threat


def simple_tactic_missed(facts: BoardFacts) -> bool:
    """Best move was a simple check or winning capture."""
    return facts.simple_forcing_missed


def best_move_attacks_hanging(facts: BoardFacts) -> bool:
    """Best move would have attacked a hanging piece."""
    return facts.best_attacks_hanging


# ============================================
# PREDICATE REGISTRY (for config lookup)
# ============================================
PREDICATE_REGISTRY = {
    "opponent_has_immediate_check": opponent_has_immediate_check,
    "opponent_has_winning_capture": opponent_has_winning_capture,
    "user_was_in_check": user_was_in_check,
    "time_pressure_detected": time_pressure_detected,
    "severe_time_pressure": severe_time_pressure,
    "user_piece_left_hanging": user_piece_left_hanging,
    "is_opening_phase": is_opening_phase,
    "user_attacked_instead_of_defending": user_attacked_instead_of_defending,
    "user_ignored_forcing_reply": user_ignored_forcing_reply,
    "user_defended_phantom_threat": user_defended_phantom_threat,
    "simple_tactic_missed": simple_tactic_missed,
    "best_move_attacks_hanging": best_move_attacks_hanging,
}


def evaluate_predicate(predicate_name: str, facts: BoardFacts) -> bool:
    """Evaluate a predicate by name."""
    predicate_fn = PREDICATE_REGISTRY.get(predicate_name)
    if predicate_fn:
        try:
            return predicate_fn(facts)
        except Exception as e:
            logger.warning(f"Predicate {predicate_name} failed: {e}")
            return False
    return False
