"""
Pre-Move Guardian - Intercept blunders before they happen

This is the highest priority intelligence layer for Play With Coach.
The key differentiator: Stop bad moves BEFORE they are made.

Requirements:
- Fast (<100ms response time)
- Deterministic (no randomness, no LLM)
- Lightweight heuristics (no deep engine search)

Risk Detection Categories:
1. HANGING_PIECE - Moving a piece leaves another piece undefended
2. BLUNDER_INTO_TACTIC - Moving into a fork, pin, or skewer
3. IGNORE_THREAT - Not addressing opponent's immediate threat
4. MATERIAL_LOSS - Losing material unfavorably (bad trade)
5. BACK_RANK_WEAKNESS - Creating or ignoring back rank threats
6. KING_SAFETY - Weakening king position dangerously

Intervention Levels:
- BLOCK: Move is stopped, user must acknowledge
- WARN: Warning shown but move allowed after confirmation
- SUGGEST: Subtle hint, no blocking
"""

import chess
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Dict, Any, Tuple
import time


class RiskLevel(str, Enum):
    """Risk level for a move"""
    CRITICAL = "critical"  # Immediate material loss, must block
    HIGH = "high"          # Serious mistake, should warn
    MEDIUM = "medium"      # Suboptimal, suggest alternative
    LOW = "low"            # Minor inaccuracy
    NONE = "none"          # No issues detected


class RiskType(str, Enum):
    """Type of risk detected"""
    HANGING_PIECE = "hanging_piece"
    BLUNDER_INTO_TACTIC = "blunder_into_tactic"
    IGNORE_THREAT = "ignore_threat"
    MATERIAL_LOSS = "material_loss"
    BACK_RANK_WEAKNESS = "back_rank_weakness"
    KING_SAFETY = "king_safety"
    TRAPPED_PIECE = "trapped_piece"


class InterventionType(str, Enum):
    """How to intervene"""
    BLOCK = "block"      # Stop the move
    WARN = "warn"        # Show warning, allow override
    SUGGEST = "suggest"  # Subtle suggestion
    NONE = "none"        # No intervention


@dataclass
class GuardianResult:
    """Result from the pre-move guardian"""
    should_intervene: bool
    intervention_type: InterventionType
    risk_level: RiskLevel
    risk_type: Optional[RiskType]
    message: str
    explanation: str
    alternative_moves: List[str]  # Better moves to suggest
    details: Dict[str, Any]       # Additional context
    processing_time_ms: float
    
    def to_dict(self) -> Dict:
        return {
            "should_intervene": self.should_intervene,
            "intervention_type": self.intervention_type.value,
            "risk_level": self.risk_level.value,
            "risk_type": self.risk_type.value if self.risk_type else None,
            "message": self.message,
            "explanation": self.explanation,
            "alternative_moves": self.alternative_moves,
            "details": self.details,
            "processing_time_ms": self.processing_time_ms
        }


# Piece values for material calculations
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


class PreMoveGuardian:
    """
    Pre-move guardian that intercepts potentially bad moves.
    
    Uses lightweight heuristics for fast detection (<100ms).
    No deep engine search, no LLM calls.
    """
    
    def __init__(self, remaining_interventions: int = 3):
        """
        Initialize guardian.
        
        Args:
            remaining_interventions: How many times we can interrupt per game.
                                    Don't spam the user with warnings.
        """
        self.remaining_interventions = remaining_interventions
    
    def evaluate_move(
        self,
        fen: str,
        move_san: str,
        user_color: str,
        stockfish_eval_before: float = None,
        stockfish_eval_after: float = None
    ) -> GuardianResult:
        """
        Evaluate a move before it's made.
        
        IMPORTANT: Stockfish evaluation is the PRIMARY check.
        Heuristics are only used when Stockfish confirms the move is bad.
        # If Stockfish says a move is fine, we DON'T intervene - it's a good move!
        
        Args:
            fen: Current position in FEN
            move_san: Move in SAN notation (e.g., "Nf3", "Bxe5")
            user_color: "white" or "black"
            stockfish_eval_before: Eval before move (optional, will use heuristics if None)
            stockfish_eval_after: Eval after move (optional)
        
        Returns:
            GuardianResult with intervention decision
        """
        start_time = time.time()
        
        try:
            board = chess.Board(fen)
            move = board.parse_san(move_san)
        except Exception as e:
            return GuardianResult(
                should_intervene=False,
                intervention_type=InterventionType.NONE,
                risk_level=RiskLevel.NONE,
                risk_type=None,
                message="",
                explanation="",
                alternative_moves=[],
                details={"error": str(e)},
                processing_time_ms=(time.time() - start_time) * 1000
            )
        
        # CRITICAL: If we're in check, the user MUST address it
        # Don't warn about anything else - they have no choice
        if board.is_check():
            processing_time = (time.time() - start_time) * 1000
            return GuardianResult(
                should_intervene=False,
                intervention_type=InterventionType.NONE,
                risk_level=RiskLevel.NONE,
                risk_type=None,
                message="",
                explanation="",
                alternative_moves=[],
                details={"in_check": True, "note": "User is in check, must address it"},
                processing_time_ms=processing_time
            )
        
        # === STOCKFISH-FIRST APPROACH ===
        # If we have Stockfish evaluations, use them as the PRIMARY arbiter
        # Only intervene if Stockfish says the move loses significant value
        
        if stockfish_eval_before is not None and stockfish_eval_after is not None:
            # Normalize for color (positive = good for user)
            if user_color == "black":
                eval_before = -stockfish_eval_before
                eval_after = -stockfish_eval_after
            else:
                eval_before = stockfish_eval_before
                eval_after = stockfish_eval_after
            
            eval_drop = eval_before - eval_after
            
            # If eval doesn't drop significantly, the move is FINE
            # Even if heuristics flag something, Stockfish knows better!
            if eval_drop < 0.5:
                # Move is good or neutral - no intervention needed
                processing_time = (time.time() - start_time) * 1000
                
                # Check if this was a capture that looks risky but engine approves
                is_capture = board.is_capture(move)
                captured_piece = board.piece_at(move.to_square) if is_capture else None
                
                # If they captured a defended piece but engine says it's fine
                if is_capture and captured_piece:
                    board_copy = board.copy()
                    board_copy.push(move)
                    if board_copy.is_attacked_by(not board.turn, move.to_square):
                        # Captured defended piece, engine approves
                        return GuardianResult(
                            should_intervene=False,
                            intervention_type=InterventionType.NONE,
                            risk_level=RiskLevel.NONE,
                            risk_type=None,
                            message="",
                            explanation="",
                            alternative_moves=[],
                            details={
                                "good_trade": True,
                                "note": ""  # No message needed for normal trades
                            },
                            processing_time_ms=processing_time
                        )
                
                return GuardianResult(
                    should_intervene=False,
                    intervention_type=InterventionType.NONE,
                    risk_level=RiskLevel.NONE,
                    risk_type=None,
                    message="",
                    explanation="",
                    alternative_moves=[],
                    details={"stockfish_approved": True},
                    processing_time_ms=processing_time
                )
            
            # Significant eval drop - this IS a mistake
            # Now use heuristics to explain WHY it's bad
            # Only CRITICAL for catastrophic drops (queen loss / mate threat)
            # Smaller mistakes get handled by Socratic coaching after the move
            if eval_drop >= 4.0:
                risk_level = RiskLevel.CRITICAL  # Losing queen or getting mated
            elif eval_drop >= 2.0:
                risk_level = RiskLevel.HIGH      # Big mistake — but let Socratic teach
            else:
                risk_level = RiskLevel.MEDIUM    # Normal mistake — Socratic handles it
        
        # === HEURISTIC FALLBACK ===
        # When no Stockfish data, use heuristics (less accurate)
        
        # Run all risk detectors
        risks = []
        
        # 1. Check for hanging pieces after the move
        hanging_risk = self._detect_hanging_piece(board, move)
        if hanging_risk:
            risks.append(hanging_risk)
        
        # 2. Check if ignoring opponent's threat
        ignore_risk = self._detect_ignored_threat(board, move)
        if ignore_risk:
            risks.append(ignore_risk)
        
        # 3. Check for bad material trades
        trade_risk = self._detect_bad_trade(board, move)
        if trade_risk:
            risks.append(trade_risk)
        
        # 4. Check for tactical blunders (moving into forks/pins)
        tactic_risk = self._detect_tactical_blunder(board, move)
        if tactic_risk:
            risks.append(tactic_risk)
        
        # 5. Check king safety
        king_risk = self._detect_king_danger(board, move)
        if king_risk:
            risks.append(king_risk)
        
        processing_time = (time.time() - start_time) * 1000
        
        # No risks found
        if not risks:
            return GuardianResult(
                should_intervene=False,
                intervention_type=InterventionType.NONE,
                risk_level=RiskLevel.NONE,
                risk_type=None,
                message="",
                explanation="",
                alternative_moves=[],
                details={},
                processing_time_ms=processing_time
            )
        
        # Get highest priority risk
        highest_risk = max(risks, key=lambda r: self._risk_priority(r["level"]))
        
        # Determine intervention based on risk level and remaining interventions
        should_intervene, intervention_type = self._decide_intervention(
            highest_risk["level"]
        )
        
        # Get alternative moves
        alternatives = self._suggest_alternatives(board, move, highest_risk)
        
        return GuardianResult(
            should_intervene=should_intervene,
            intervention_type=intervention_type,
            risk_level=highest_risk["level"],
            risk_type=highest_risk["type"],
            message=highest_risk["message"],
            explanation=highest_risk["explanation"],
            alternative_moves=alternatives,
            details=highest_risk.get("details", {}),
            processing_time_ms=processing_time
        )
    
    def _detect_hanging_piece(
        self,
        board: chess.Board,
        move: chess.Move
    ) -> Optional[Dict]:
        """
        Detect if the move leaves a piece hanging (undefended and attackable).
        
        IMPORTANT: If the move is a capture that wins material, we should NOT
        warn about the moving piece being "hanging" - that's expected and fine.
        Example: Bishop takes Rook, Bishop is now "hanging" but you're up 2 points.
        """
        our_color = board.turn
        
        # Check if this is a capture
        is_capture = board.is_capture(move)
        captured_piece = board.piece_at(move.to_square) if is_capture else None
        moving_piece = board.piece_at(move.from_square)
        
        if not moving_piece:
            return None
        
        # Calculate net material if this is a capture and piece gets recaptured
        moving_value = PIECE_VALUES[moving_piece.piece_type]
        captured_value = PIECE_VALUES[captured_piece.piece_type] if captured_piece else 0
        
        # Make the move temporarily
        board_copy = board.copy()
        board_copy.push(move)
        
        # If the user is giving check, don't warn about hanging pieces
        # (forcing moves are often justified even if they leave pieces hanging)
        if board_copy.is_check():
            return None
        
        # Check the piece that just moved - is it hanging?
        if board_copy.is_attacked_by(not our_color, move.to_square):
            if not board_copy.is_attacked_by(our_color, move.to_square):
                # The moving piece is now hanging
                # But if it captured something valuable, the "hanging" is fine
                net_trade = captured_value - moving_value
                
                if net_trade >= 0:
                    # We captured equal or better material, so being "hanging" is okay
                    # Example: Bishop takes Rook = +2, worth it even if bishop hangs
                    return None
                
                # If we captured something but are losing on the trade, warn
                if is_capture and net_trade < -1:
                    moving_name = PIECE_NAMES[moving_piece.piece_type]
                    captured_name = PIECE_NAMES[captured_piece.piece_type]
                    
                    level = RiskLevel.HIGH if net_trade <= -2 else RiskLevel.MEDIUM
                    
                    return {
                        "type": RiskType.MATERIAL_LOSS,
                        "level": level,
                        "message": f"Bad trade! Your {moving_name} can be recaptured.",
                        "explanation": f"After taking the {captured_name}, your {moving_name} is hanging. Net loss: {abs(net_trade)} points.",
                        "details": {
                            "hanging_square": chess.square_name(move.to_square),
                            "piece": moving_name,
                            "value": moving_value,
                            "captured_value": captured_value,
                            "net_trade": net_trade
                        }
                    }
        
        # Check all OTHER pieces (not the one that just moved)
        for square in chess.SQUARES:
            if square == move.to_square:
                continue  # Already handled above
            
            piece = board_copy.piece_at(square)
            if piece and piece.color == our_color:
                # Skip pawns (usually not critical)
                if piece.piece_type == chess.PAWN:
                    continue
                
                # Was this piece defended before the move but is now hanging?
                was_defended = board.is_attacked_by(our_color, square)
                was_attacked = board.is_attacked_by(not our_color, square)
                
                is_now_defended = board_copy.is_attacked_by(our_color, square)
                is_now_attacked = board_copy.is_attacked_by(not our_color, square)
                
                # Only warn if the move CAUSED the piece to become hanging
                # (was defended or not attacked before, is now hanging)
                if is_now_attacked and not is_now_defended:
                    if was_defended or not was_attacked:
                        piece_value = PIECE_VALUES[piece.piece_type]
                        piece_name = PIECE_NAMES[piece.piece_type]
                        
                        # Critical if it's a major piece
                        if piece_value >= 5:
                            level = RiskLevel.CRITICAL
                        elif piece_value >= 3:
                            level = RiskLevel.HIGH
                        else:
                            level = RiskLevel.MEDIUM
                        
                        return {
                            "type": RiskType.HANGING_PIECE,
                            "level": level,
                            "message": f"This move leaves your {piece_name} on {chess.square_name(square)} hanging!",
                            "explanation": f"After this move, your {piece_name} becomes undefended and can be captured.",
                            "details": {
                                "hanging_square": chess.square_name(square),
                                "piece": piece_name,
                                "value": piece_value
                            }
                        }
        
        return None
    
    def _detect_ignored_threat(
        self,
        board: chess.Board,
        move: chess.Move
    ) -> Optional[Dict]:
        """
        Detect if we're ignoring an immediate threat from opponent.
        
        NOTE: This function is ONLY called if we're not in check 
        (check is handled at the top of evaluate_move).
        """
        our_color = board.turn
        
        # Find our pieces that are currently attacked
        threatened_pieces = []
        for square in chess.SQUARES:
            piece = board.piece_at(square)
            if piece and piece.color == our_color:
                if board.is_attacked_by(not our_color, square):
                    # Is it defended adequately?
                    defenders = len(list(board.attackers(our_color, square)))
                    attackers = len(list(board.attackers(not our_color, square)))
                    
                    # Only consider it a threat if undefended or underdefended
                    if attackers > defenders or (attackers > 0 and defenders == 0):
                        threatened_pieces.append({
                            "square": square,
                            "piece": piece,
                            "value": PIECE_VALUES[piece.piece_type]
                        })
        
        if not threatened_pieces:
            return None
        
        # Check if the move addresses any threat
        move_from = move.from_square
        move_to = move.to_square
        
        # Get highest value threat
        highest_threat = max(threatened_pieces, key=lambda x: x["value"])
        
        # Does this move address the threat?
        
        # 1. Move the threatened piece?
        if move_from == highest_threat["square"]:
            return None  # Threat addressed by moving the piece
        
        # 2. Capture the attacker?
        # Check if we're capturing a piece that was attacking our threatened piece
        if board.is_capture(move):
            captured_square = move_to
            # Was the captured piece an attacker of our threatened piece?
            attackers_of_threat = list(board.attackers(not our_color, highest_threat["square"]))
            if captured_square in attackers_of_threat:
                return None  # Threat addressed by capturing attacker
        
        # 3. Block the attack? (for sliding pieces)
        # Check if our move interposes between attacker and threatened piece
        # This is complex, so we'll do a simple check: after the move, is the piece still threatened?
        board_after = board.copy()
        board_after.push(move)
        
        # Is the threatened piece still under attack after our move?
        if not board_after.is_attacked_by(not our_color, highest_threat["square"]):
            return None  # Threat addressed (blocked or other)
        
        # Is it now defended after our move?
        defenders_after = len(list(board_after.attackers(our_color, highest_threat["square"])))
        attackers_after = len(list(board_after.attackers(not our_color, highest_threat["square"])))
        if defenders_after >= attackers_after:
            return None  # Threat addressed by defending
        
        # 4. Create a bigger threat? (discovered attack, check, etc.)
        if board_after.is_check():
            return None  # Giving check is usually justified
        
        # If we have a high-value piece under threat and didn't address it
        if highest_threat["value"] >= 3:
            piece_name = PIECE_NAMES[highest_threat["piece"].piece_type]
            square_name = chess.square_name(highest_threat["square"])
            
            level = RiskLevel.HIGH if highest_threat["value"] >= 5 else RiskLevel.MEDIUM
            
            return {
                "type": RiskType.IGNORE_THREAT,
                "level": level,
                "message": f"Your {piece_name} on {square_name} is under attack!",
                "explanation": f"Opponent can capture your {piece_name}. Consider defending or moving it first.",
                "details": {
                    "threatened_square": square_name,
                    "piece": piece_name,
                    "value": highest_threat["value"]
                }
            }
        
        return None
    
    def _detect_bad_trade(
        self,
        board: chess.Board,
        move: chess.Move
    ) -> Optional[Dict]:
        """
        Detect if the move results in a bad material trade.
        """
        # Is this a capture?
        if not board.is_capture(move):
            return None
        
        captured_piece = board.piece_at(move.to_square)
        moving_piece = board.piece_at(move.from_square)
        
        if not captured_piece or not moving_piece:
            return None
        
        captured_value = PIECE_VALUES[captured_piece.piece_type]
        moving_value = PIECE_VALUES[moving_piece.piece_type]
        
        # After the capture, is our piece recapturable?
        board_after = board.copy()
        board_after.push(move)
        
        if board_after.is_attacked_by(not board.turn, move.to_square):
            # We're capturing but can be recaptured
            # Is it a bad trade?
            net_value = captured_value - moving_value
            
            if net_value < -1:  # Losing more than a pawn
                moving_name = PIECE_NAMES[moving_piece.piece_type]
                captured_name = PIECE_NAMES[captured_piece.piece_type]
                
                level = RiskLevel.HIGH if net_value <= -2 else RiskLevel.MEDIUM
                
                return {
                    "type": RiskType.MATERIAL_LOSS,
                    "level": level,
                    "message": f"Bad trade! Losing {moving_name} for {captured_name}.",
                    "explanation": f"After capturing the {captured_name}, your {moving_name} can be recaptured. You lose {abs(net_value)} points of material.",
                    "details": {
                        "moving_piece": moving_name,
                        "captured_piece": captured_name,
                        "net_value": net_value
                    }
                }
        
        return None
    
    def _detect_tactical_blunder(
        self,
        board: chess.Board,
        move: chess.Move
    ) -> Optional[Dict]:
        """
        Detect if the move walks into a tactic (fork, pin, skewer).
        This is a simplified check - not exhaustive.
        """
        board_after = board.copy()
        board_after.push(move)
        
        our_color = board.turn
        opponent_color = not our_color
        
        # Check if opponent has a knight that can fork us
        for square in chess.SQUARES:
            piece = board_after.piece_at(square)
            if piece and piece.color == opponent_color and piece.piece_type == chess.KNIGHT:
                # What can this knight attack in one move?
                attacked_high_value = []
                for knight_move in board_after.legal_moves:
                    if knight_move.from_square == square:
                        target = knight_move.to_square
                        # What pieces are around this target?
                        # Check if multiple high-value pieces are in knight-attack range
                        for attack_sq in board_after.attacks(target):
                            attacked_piece = board_after.piece_at(attack_sq)
                            if attacked_piece and attacked_piece.color == our_color:
                                if PIECE_VALUES[attacked_piece.piece_type] >= 5:  # Queen or Rook
                                    attacked_high_value.append(attack_sq)
                
                # This is a simplified fork detection
                # Full implementation would be more complex
        
        return None  # Simplified - return None for now
    
    def _detect_king_danger(
        self,
        board: chess.Board,
        move: chess.Move
    ) -> Optional[Dict]:
        """
        Detect if the move puts the king in danger.
        """
        board_after = board.copy()
        board_after.push(move)
        
        our_color = board.turn
        our_king_square = board_after.king(our_color)
        
        if our_king_square is None:
            return None
        
        # How many pieces are attacking our king after the move?
        attackers = list(board_after.attackers(not our_color, our_king_square))
        
        # This shouldn't happen (would be illegal), but check anyway
        if len(attackers) > 0:
            return {
                "type": RiskType.KING_SAFETY,
                "level": RiskLevel.CRITICAL,
                "message": "This move puts your king in check!",
                "explanation": "Your king would be attacked after this move.",
                "details": {"attackers": len(attackers)}
            }
        
        # Check for weakened king safety (e.g., moved pawn in front of castled king)
        # This is complex heuristic, simplified for now
        
        return None
    
    def _risk_priority(self, level: RiskLevel) -> int:
        """Get numeric priority for risk level"""
        priorities = {
            RiskLevel.CRITICAL: 5,
            RiskLevel.HIGH: 4,
            RiskLevel.MEDIUM: 3,
            RiskLevel.LOW: 2,
            RiskLevel.NONE: 1
        }
        return priorities.get(level, 0)
    
    def _decide_intervention(
        self,
        risk_level: RiskLevel
    ) -> Tuple[bool, InterventionType]:
        """
        Decide whether to intervene based on risk level and remaining interventions.

        Philosophy: The Socratic coaching system (fundamentals checklist) teaches
        from mistakes AFTER they happen. The guardian should only block truly
        catastrophic blunders (losing a queen for nothing, back rank mate).
        For smaller mistakes (hanging a minor piece, missing a tactic), let the
        student make the mistake and learn from the Socratic question that follows.
        """
        if self.remaining_interventions <= 0:
            return False, InterventionType.NONE

        if risk_level == RiskLevel.CRITICAL:
            # Catastrophic: losing queen, getting mated — still block
            return True, InterventionType.WARN
        else:
            # HIGH, MEDIUM, LOW — let the Socratic system teach from the mistake
            return False, InterventionType.NONE
    
    def _suggest_alternatives(
        self,
        board: chess.Board,
        bad_move: chess.Move,
        risk: Dict
    ) -> List[str]:
        """
        Suggest alternative moves that avoid the detected risk.
        """
        alternatives = []
        
        risk_type = risk["type"]
        
        if risk_type == RiskType.HANGING_PIECE:
            # Suggest moves that defend the hanging piece
            hanging_square = chess.parse_square(risk["details"]["hanging_square"])
            
            for move in board.legal_moves:
                if move == bad_move:
                    continue
                
                # Does this move defend the hanging piece?
                board_test = board.copy()
                board_test.push(move)
                
                # Is the piece now defended?
                piece = board_test.piece_at(hanging_square)
                if piece and board_test.is_attacked_by(board.turn, hanging_square):
                    alternatives.append(board.san(move))
                    if len(alternatives) >= 2:
                        break
        
        elif risk_type == RiskType.IGNORE_THREAT:
            # Suggest moves that address the threat
            threatened_square = chess.parse_square(risk["details"]["threatened_square"])
            
            for move in board.legal_moves:
                if move == bad_move:
                    continue
                
                # Does this move address the threat?
                if move.from_square == threatened_square:
                    # Moving the threatened piece
                    alternatives.append(board.san(move))
                    if len(alternatives) >= 2:
                        break
        
        return alternatives[:3]  # Max 3 alternatives
    
    def consume_intervention(self):
        """Call this when an intervention is shown to the user"""
        self.remaining_interventions = max(0, self.remaining_interventions - 1)


def evaluate_move_for_guardian(
    fen: str,
    move_san: str,
    user_color: str,
    remaining_interventions: int = 3
) -> Dict:
    """
    Convenience function to evaluate a move.
    
    Args:
        fen: Current position
        move_san: Move to evaluate
        user_color: "white" or "black"
        remaining_interventions: How many warnings left this game
    
    Returns:
        Dict with guardian result
    """
    guardian = PreMoveGuardian(remaining_interventions)
    result = guardian.evaluate_move(fen, move_san, user_color)
    return result.to_dict()


# =============================================================================
# ENFORCEMENT LADDER (Progressive Strictness)
# Escalates friction based on repeated mistakes in the same game
# =============================================================================

class EnforcementLevel(Enum):
    """Escalating enforcement levels based on repeat count."""
    WARNING = 1          # "Check opponent threat"
    STRONG_WARNING = 2   # "You are repeating your mistake"
    CHECKBOX_REQUIRED = 3  # Force acknowledgment
    SOFT_BLOCK = 4       # "Try a different move"
    ALLOW_WITH_PENALTY = 5  # Allow but mark for streak

@dataclass
class EnforcementResult:
    """Result of enforcement ladder evaluation."""
    level: EnforcementLevel
    should_block: bool
    requires_checkbox: bool
    message: str
    explanation: str
    repeat_count: int
    risk_type: Optional[RiskType]
    
    def to_dict(self) -> Dict:
        return {
            "enforcement_level": self.level.value,
            "enforcement_name": self.level.name,
            "should_block": self.should_block,
            "requires_checkbox": self.requires_checkbox,
            "message": self.message,
            "explanation": self.explanation,
            "repeat_count": self.repeat_count,
            "risk_type": self.risk_type.value if self.risk_type else None
        }


class EnforcementLadder:
    """
    Tracks repeated mistakes in a game and escalates enforcement.
    
    Escalation Logic:
    - 1st occurrence: Warning
    - 2nd occurrence: Strong warning  
    - 3rd occurrence: Checkbox required ("I checked opponent threats")
    - 4th occurrence: Soft block ("Try a different move")
    - 5th+: Allow but mark as ignored warning (streak penalty)
    
    Risk Severity Modifier:
    - CRITICAL risk: Escalate by +1 level
    - HIGH risk at repeat 2+: Also escalate by +1
    """
    
    # Mapping of risk types to user-facing categories
    RISK_CATEGORIES = {
        RiskType.HANGING_PIECE: "hanging_piece",
        RiskType.IGNORE_THREAT: "ignore_threat", 
        RiskType.MATERIAL_LOSS: "bad_trade",
        RiskType.BLUNDER_INTO_TACTIC: "tactical_blunder",
        RiskType.KING_SAFETY: "king_danger"
    }
    
    # Messages per enforcement level
    MESSAGES = {
        EnforcementLevel.WARNING: {
            "ignore_threat": "What is your opponent threatening?",
            "hanging_piece": "Is your piece safe after this move?",
            "bad_trade": "Are you sure about this trade?",
            "tactical_blunder": "Is there a tactic you're missing?",
            "king_danger": "Is your king safe?",
            "default": "Check your move carefully."
        },
        EnforcementLevel.STRONG_WARNING: {
            "ignore_threat": "You are repeating your mistake. What is your opponent threatening?",
            "hanging_piece": "You are leaving pieces hanging again. Stop and check.",
            "bad_trade": "You made a bad trade earlier. Think again.",
            "tactical_blunder": "You missed a tactic before. Look harder.",
            "king_danger": "Your king was in danger before. Check again.",
            "default": "You are repeating your mistake."
        },
        EnforcementLevel.CHECKBOX_REQUIRED: {
            "ignore_threat": "I have checked what my opponent is threatening.",
            "hanging_piece": "I have verified my piece is safe.",
            "bad_trade": "I understand this trade and accept it.",
            "tactical_blunder": "I have looked for tactics.",
            "king_danger": "I have verified my king is safe.",
            "default": "I have checked my move."
        },
        EnforcementLevel.SOFT_BLOCK: {
            "default": "You've been warned multiple times. Try a different move."
        },
        EnforcementLevel.ALLOW_WITH_PENALTY: {
            "default": "You ignored the warning. This will affect your streak."
        }
    }
    
    def __init__(self):
        """Initialize with empty mistake tracking."""
        self.mistake_counts: Dict[str, int] = {}  # category -> count
        self.total_warnings_shown = 0
        self.ignored_warnings = 0
    
    def track_mistake(self, risk_type: RiskType) -> None:
        """Track a mistake occurrence."""
        category = self.RISK_CATEGORIES.get(risk_type, "default")
        self.mistake_counts[category] = self.mistake_counts.get(category, 0) + 1
    
    def get_repeat_count(self, risk_type: RiskType) -> int:
        """Get how many times this mistake type has occurred."""
        category = self.RISK_CATEGORIES.get(risk_type, "default")
        return self.mistake_counts.get(category, 0)
    
    def evaluate_enforcement(
        self,
        guardian_result: GuardianResult
    ) -> Optional[EnforcementResult]:
        """
        Evaluate what enforcement level applies based on guardian result and history.
        
        Args:
            guardian_result: Result from PreMoveGuardian.evaluate_move()
        
        Returns:
            EnforcementResult if enforcement needed, None if move is fine
        """
        if not guardian_result.should_intervene:
            return None
        
        risk_type = guardian_result.risk_type
        risk_level = guardian_result.risk_level
        
        if not risk_type:
            return None
        
        # Get repeat count BEFORE incrementing (this is the Nth occurrence)
        repeat_count = self.get_repeat_count(risk_type) + 1
        
        # Calculate base enforcement level
        base_level = min(repeat_count, 5)
        
        # Apply risk severity modifier
        if risk_level == RiskLevel.CRITICAL:
            base_level = min(base_level + 1, 5)
        elif risk_level == RiskLevel.HIGH and repeat_count >= 2:
            base_level = min(base_level + 1, 5)
        
        # Map to enforcement level
        enforcement_level = EnforcementLevel(base_level)
        
        # Determine behavior
        should_block = enforcement_level == EnforcementLevel.SOFT_BLOCK
        requires_checkbox = enforcement_level == EnforcementLevel.CHECKBOX_REQUIRED
        
        # Get appropriate message
        category = self.RISK_CATEGORIES.get(risk_type, "default")
        level_messages = self.MESSAGES.get(enforcement_level, {})
        message = level_messages.get(category, level_messages.get("default", ""))
        
        # Build explanation based on level
        if enforcement_level == EnforcementLevel.WARNING:
            explanation = guardian_result.explanation
        elif enforcement_level == EnforcementLevel.STRONG_WARNING:
            explanation = f"This is the {repeat_count}{'st' if repeat_count == 1 else 'nd' if repeat_count == 2 else 'rd' if repeat_count == 3 else 'th'} time this game. {guardian_result.explanation}"
        elif enforcement_level == EnforcementLevel.CHECKBOX_REQUIRED:
            explanation = f"You must confirm you've checked before proceeding. {guardian_result.explanation}"
        elif enforcement_level == EnforcementLevel.SOFT_BLOCK:
            explanation = f"You've been warned {repeat_count} times about this. Find a better move."
        else:
            explanation = "Warning ignored. This mistake will count against your streak."
        
        return EnforcementResult(
            level=enforcement_level,
            should_block=should_block,
            requires_checkbox=requires_checkbox,
            message=message,
            explanation=explanation,
            repeat_count=repeat_count,
            risk_type=risk_type
        )
    
    def record_warning_shown(self, risk_type: RiskType) -> None:
        """Record that a warning was shown (call after showing to user)."""
        self.track_mistake(risk_type)
        self.total_warnings_shown += 1
    
    def record_warning_ignored(self) -> None:
        """Record that user proceeded despite warning."""
        self.ignored_warnings += 1
    
    def get_game_summary(self) -> Dict:
        """Get summary for post-game analysis."""
        return {
            "mistake_counts": self.mistake_counts.copy(),
            "total_warnings_shown": self.total_warnings_shown,
            "ignored_warnings": self.ignored_warnings,
            "warning_compliance_rate": round(
                (self.total_warnings_shown - self.ignored_warnings) / max(1, self.total_warnings_shown) * 100,
                1
            )
        }


def evaluate_with_enforcement(
    fen: str,
    move_san: str,
    user_color: str,
    enforcement_ladder: EnforcementLadder,
    remaining_interventions: int = 3,
    stockfish_eval_before: float = None,
    stockfish_eval_after: float = None
) -> Dict:
    """
    Evaluate a move with enforcement ladder escalation.
    
    Args:
        fen: Current position
        move_san: Move to evaluate
        user_color: "white" or "black"
        enforcement_ladder: EnforcementLadder instance tracking this game
        remaining_interventions: How many base warnings left
        stockfish_eval_before: Optional eval before move
        stockfish_eval_after: Optional eval after move
    
    Returns:
        Dict with guardian result + enforcement data
    """
    guardian = PreMoveGuardian(remaining_interventions)
    guardian_result = guardian.evaluate_move(
        fen, move_san, user_color,
        stockfish_eval_before=stockfish_eval_before,
        stockfish_eval_after=stockfish_eval_after
    )
    
    result = guardian_result.to_dict()
    
    # Apply enforcement ladder
    enforcement = enforcement_ladder.evaluate_enforcement(guardian_result)
    
    if enforcement:
        result["enforcement"] = enforcement.to_dict()
        result["should_intervene"] = True  # Override if enforcement requires
        
        # Update intervention type based on enforcement
        if enforcement.should_block:
            result["intervention_type"] = InterventionType.BLOCK.value
        elif enforcement.requires_checkbox:
            result["intervention_type"] = "CHECKBOX"  # New type
        
        # Use enforcement message if stronger
        if enforcement.level.value >= EnforcementLevel.STRONG_WARNING.value:
            result["message"] = enforcement.message
            result["explanation"] = enforcement.explanation
    
    return result
