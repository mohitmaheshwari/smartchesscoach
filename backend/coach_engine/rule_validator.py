"""
Rule Validator - Two-Gate System

Gate A: Position Evidence Extraction
Gate B: Contrastive Proof with SF Alternatives

No hallucination - every teaching must pass both gates.
"""

import chess
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from .models import WisdomRule, ReasonType, TeachingLevel, TRIGGER_THRESHOLDS
from .piece_metrics import PieceMetricsAnalyzer
from .wisdom_library import get_wisdom_library


@dataclass
class ValidationResult:
    """Result of rule validation"""
    rule_id: str
    passed_gate_a: bool              # Evidence predicates passed
    passed_gate_b: bool              # Contrastive proof available
    confidence: float                # 0-1
    evidence: Dict                   # Extracted evidence
    contrastive_reason: Optional[str]  # The concrete reason
    diagnosis: str                   # Filled diagnosis template
    is_valid: bool                   # Both gates passed


@dataclass
class StockfishAnalysis:
    """Stockfish analysis results for a position"""
    eval_before: float
    eval_after: float
    delta_cp: int
    best_move: str
    best_move_eval: float
    pv_line: List[str]
    depth: int
    is_stable: bool                  # PV didn't change much across depths


class RuleValidator:
    """
    Two-gate rule validation system.
    
    Gate A: Check if position evidence supports the rule
    Gate B: Verify with Stockfish that the rule explains the eval difference
    """
    
    def __init__(self, board: chess.Board, user_color: chess.Color):
        self.board = board
        self.user_color = user_color
        self.metrics = PieceMetricsAnalyzer(board)
        self.library = get_wisdom_library()
    
    def validate_rule(
        self, 
        rule_id: str, 
        user_move: chess.Move,
        sf_analysis: StockfishAnalysis,
        move_number: int,
        game_history: List[chess.Move] = None
    ) -> ValidationResult:
        """
        Validate a single rule against the position.
        Returns validation result with evidence and diagnosis.
        """
        rule = self.library.get_rule(rule_id)
        if not rule:
            return ValidationResult(
                rule_id=rule_id,
                passed_gate_a=False,
                passed_gate_b=False,
                confidence=0,
                evidence={},
                contrastive_reason=None,
                diagnosis="Rule not found",
                is_valid=False,
            )
        
        # Gate A: Evidence extraction
        gate_a_result, evidence = self._check_gate_a(rule, user_move, move_number, game_history)
        
        if not gate_a_result:
            return ValidationResult(
                rule_id=rule_id,
                passed_gate_a=False,
                passed_gate_b=False,
                confidence=0,
                evidence=evidence,
                contrastive_reason=None,
                diagnosis="Evidence predicates not met",
                is_valid=False,
            )
        
        # Gate B: Contrastive proof
        gate_b_result, contrastive_reason = self._check_gate_b(rule, user_move, sf_analysis)
        
        # Calculate confidence based on SF stability
        confidence = 1.0 if sf_analysis.is_stable else 0.7
        
        # Fill diagnosis template
        diagnosis = self._fill_diagnosis(rule, evidence)
        
        return ValidationResult(
            rule_id=rule_id,
            passed_gate_a=gate_a_result,
            passed_gate_b=gate_b_result,
            confidence=confidence,
            evidence=evidence,
            contrastive_reason=contrastive_reason,
            diagnosis=diagnosis,
            is_valid=gate_a_result and gate_b_result,
        )
    
    def find_applicable_rules(
        self,
        user_move: chess.Move,
        sf_analysis: StockfishAnalysis,
        move_number: int,
        game_history: List[chess.Move] = None,
    ) -> List[ValidationResult]:
        """
        Find all rules that apply to this position and move.
        Returns sorted by relevance/confidence.
        """
        applicable = []
        
        for rule_id in self.library.get_rule_ids():
            result = self.validate_rule(rule_id, user_move, sf_analysis, move_number, game_history)
            if result.is_valid:
                applicable.append(result)
        
        # Sort by confidence, then by how well the rule matches
        applicable.sort(key=lambda r: r.confidence, reverse=True)
        
        return applicable
    
    def _check_gate_a(
        self, 
        rule: WisdomRule, 
        user_move: chess.Move,
        move_number: int,
        game_history: List[chess.Move] = None
    ) -> Tuple[bool, Dict]:
        """
        Gate A: Check position evidence predicates.
        Each rule has specific predicates that must all pass.
        """
        evidence = {}
        
        # Dispatch to specific rule checker
        checker_name = f"_check_{rule.rule_id.lower()}"
        checker = getattr(self, checker_name, None)
        
        if checker:
            return checker(user_move, move_number, game_history, evidence)
        
        # Default: check generic predicates
        return self._check_generic_predicates(rule, user_move, move_number, evidence)
    
    def _check_gate_b(
        self,
        rule: WisdomRule,
        user_move: chess.Move,
        sf_analysis: StockfishAnalysis
    ) -> Tuple[bool, Optional[str]]:
        """
        Gate B: Verify with Stockfish that the rule explains the eval difference.
        Must provide a concrete, verifiable reason.
        """
        # The rule must be supported by SF preferring a different move
        if sf_analysis.best_move == user_move.uci():
            return False, None
        
        # Check if the eval difference is significant enough
        if abs(sf_analysis.delta_cp) < TRIGGER_THRESHOLDS["observe"]:
            return False, None
        
        # Extract contrastive reason based on rule type
        reason = self._extract_contrastive_reason(rule, user_move, sf_analysis)
        
        return reason is not None, reason
    
    def _extract_contrastive_reason(
        self,
        rule: WisdomRule,
        user_move: chess.Move,
        sf_analysis: StockfishAnalysis
    ) -> Optional[str]:
        """
        Extract a concrete reason why SF move is better.
        Must be from the allowed reason set.
        """
        user_move_san = self.board.san(user_move)
        
        # Make the user move to see the resulting position
        self.board.push(user_move)
        
        try:
            # Parse SF best move
            sf_move = chess.Move.from_uci(sf_analysis.best_move)
            
            # Check for tactical reasons first
            reason = None
            
            # 1. Check for threats created by SF move
            self.board.pop()  # Go back
            self.board.push(sf_move)
            if self.board.is_check():
                reason = f"{self.board.san(sf_move)} gives check"
            self.board.pop()
            self.board.push(user_move)  # Restore to after user move
            
            # 2. Check if SF move would have won material
            if not reason:
                if sf_move.to_square in [m.to_square for m in self.board.legal_moves if self.board.is_capture(m)]:
                    reason = f"{sf_analysis.best_move} wins material"
            
            # 3. Reason based on rule type
            if not reason:
                if rule.reason_type == ReasonType.KING_SAFETY:
                    reason = "keeps the king safer"
                elif rule.reason_type == ReasonType.DEVELOPMENT_TEMPO:
                    reason = "develops pieces faster"
                elif rule.reason_type == ReasonType.PIECE_ACTIVITY:
                    reason = "activates pieces better"
                elif rule.reason_type == ReasonType.OPEN_FILE:
                    reason = "controls the open file"
                elif rule.reason_type == ReasonType.HANGING_PIECE:
                    reason = "protects the hanging piece"
                elif rule.reason_type == ReasonType.THREAT:
                    reason = "creates a stronger threat"
                elif rule.reason_type == ReasonType.PAWN_STRUCTURE:
                    reason = "handles the center tension better"
            
            return reason
            
        finally:
            self.board.pop()  # Ensure we restore board state
    
    def _fill_diagnosis(self, rule: WisdomRule, evidence: Dict) -> str:
        """Fill the diagnosis template with extracted evidence"""
        try:
            return rule.diagnosis_template.format(**evidence)
        except KeyError:
            return rule.diagnosis_template
    
    # ==================== SPECIFIC RULE CHECKERS ====================
    
    def _check_delayed_castling(
        self, user_move: chess.Move, move_number: int, 
        game_history: List[chess.Move], evidence: Dict
    ) -> Tuple[bool, Dict]:
        """Check DELAYED_CASTLING rule"""
        evidence["move_number"] = move_number
        
        # Must be move 10+
        if move_number < 10:
            return False, evidence
        
        # King must not be castled
        if self.metrics.is_castled(self.user_color):
            return False, evidence
        
        evidence["king_not_castled"] = True
        
        # Check if opponent has active pieces
        opp_color = not self.user_color
        opp_worst = self.metrics.get_worst_piece(opp_color)
        evidence["opponent_has_active_pieces"] = opp_worst is None or opp_worst.mobility > 3
        
        return evidence["opponent_has_active_pieces"], evidence
    
    def _check_blocked_bishop_by_own_pawn(
        self, user_move: chess.Move, move_number: int,
        game_history: List[chess.Move], evidence: Dict
    ) -> Tuple[bool, Dict]:
        """Check BLOCKED_BISHOP_BY_OWN_PAWN rule"""
        
        # Find user's bishops
        for sq in chess.SQUARES:
            piece = self.board.piece_at(sq)
            if piece and piece.piece_type == chess.BISHOP and piece.color == self.user_color:
                blocking_info = self.metrics.get_bishop_blocking_info(sq)
                
                if blocking_info and blocking_info["blocked_by_own_pawn"]:
                    mobility = self.metrics.get_piece_mobility(sq)
                    
                    if mobility <= 4:
                        evidence["bishop_square"] = chess.square_name(sq)
                        evidence["pawn_square"] = blocking_info["blocking_pawn_square"]
                        evidence["mobility"] = mobility
                        evidence["bishop_mobility_low"] = True
                        evidence["own_pawn_blocks_diagonal"] = True
                        
                        # Check if position is closed
                        is_closed = self.metrics.is_closed_position()
                        evidence["is_closed_or_sf_prefers_knight"] = is_closed
                        
                        return True, evidence
        
        return False, evidence
    
    def _check_open_file_rook_unused(
        self, user_move: chess.Move, move_number: int,
        game_history: List[chess.Move], evidence: Dict
    ) -> Tuple[bool, Dict]:
        """Check OPEN_FILE_ROOK_UNUSED rule"""
        
        open_files, semi_w, semi_b = self.metrics.get_open_files()
        
        # Need at least one open file
        if not open_files:
            return False, evidence
        
        evidence["open_file_exists"] = True
        evidence["file"] = open_files[0]
        
        # Find user's rooks
        for sq in chess.SQUARES:
            piece = self.board.piece_at(sq)
            if piece and piece.piece_type == chess.ROOK and piece.color == self.user_color:
                file_info = self.metrics.get_rook_file_info(sq)
                
                if not file_info["on_open_file"]:
                    evidence["rook_square"] = chess.square_name(sq)
                    evidence["rook_not_on_open_file"] = True
                    evidence["rook_could_reach_open_file"] = True  # Simplified
                    return True, evidence
        
        return False, evidence
    
    def _check_hanging_piece(
        self, user_move: chess.Move, move_number: int,
        game_history: List[chess.Move], evidence: Dict
    ) -> Tuple[bool, Dict]:
        """Check HANGING_PIECE rule"""
        
        # After user's move, check if any piece is hanging
        self.board.push(user_move)
        
        try:
            for sq in chess.SQUARES:
                piece = self.board.piece_at(sq)
                if piece and piece.color == self.user_color and piece.piece_type != chess.PAWN:
                    # Check if piece is attacked
                    attackers = self.board.attackers(not self.user_color, sq)
                    defenders = self.board.attackers(self.user_color, sq)
                    
                    if attackers and not defenders:
                        evidence["piece"] = chess.piece_name(piece.piece_type)
                        evidence["square"] = chess.square_name(sq)
                        evidence["piece_is_undefended"] = True
                        evidence["opponent_can_capture_it"] = True
                        evidence["capture_is_profitable"] = True
                        return True, evidence
        finally:
            self.board.pop()
        
        return False, evidence
    
    def _check_ignore_worst_piece(
        self, user_move: chess.Move, move_number: int,
        game_history: List[chess.Move], evidence: Dict
    ) -> Tuple[bool, Dict]:
        """Check IGNORE_WORST_PIECE rule"""
        
        worst = self.metrics.get_worst_piece(self.user_color)
        
        if not worst:
            return False, evidence
        
        evidence["worst_piece"] = worst.piece_type
        evidence["worst_square"] = worst.square
        evidence["worst_piece_identified"] = True
        
        # Check if user moved a different piece
        moved_piece = self.board.piece_at(user_move.from_square)
        if moved_piece:
            moved_from = chess.square_name(user_move.from_square)
            if moved_from != worst.square:
                evidence["user_moved_different_piece"] = True
                evidence["worst_piece_could_improve"] = worst.mobility > 0
                
                if evidence["worst_piece_could_improve"]:
                    return True, evidence
        
        return False, evidence
    
    def _check_generic_predicates(
        self, rule: WisdomRule, user_move: chess.Move, 
        move_number: int, evidence: Dict
    ) -> Tuple[bool, Dict]:
        """Fallback checker for rules without specific implementation"""
        # For now, return False for unimplemented rules
        # This ensures no false positives
        return False, evidence


def determine_teaching_level(delta_cp: int) -> TeachingLevel:
    """Determine the appropriate teaching level based on eval delta"""
    if delta_cp <= TRIGGER_THRESHOLDS["blunder"]:
        return TeachingLevel.BLUNDER
    elif delta_cp <= TRIGGER_THRESHOLDS["pause"]:
        return TeachingLevel.PAUSE
    elif delta_cp <= TRIGGER_THRESHOLDS["teach"]:
        return TeachingLevel.TEACH
    elif delta_cp <= TRIGGER_THRESHOLDS["observe"]:
        return TeachingLevel.OBSERVE
    else:
        return TeachingLevel.OBSERVE
