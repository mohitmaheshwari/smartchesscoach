"""
Analysis Interpreter Service - Behavioral Pattern Detection Layer

This service runs AFTER Stockfish analysis to interpret WHY the player
made their decisions. It transforms raw engine data into coaching insights.

Pipeline position:
  Stockfish → [raw moves] → THIS SERVICE → [interpreted moves] → Storage

Key principle: Engine analysis (what happened) is separate from
behavioral interpretation (why it happened).
"""

import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from cognitive_gap_service import (
    CognitiveGap,
    analyze_cognitive_gap,
    find_hanging_pieces,
    find_threats
)

logger = logging.getLogger(__name__)


# Canonical cognitive-gap taxonomy used by the Lab / Home / Training surfaces
# and keyed into COACHING_DIAGNOSIS in routes/training_advanced.py. The older
# CognitiveGap enum used different string values (e.g. "hanging_piece_blindness"
# instead of "piece_safety"), which caused downstream lookups to miss and the
# prod pool to collapse into just 2 tags. All new classifier output emits
# these canonical strings.
GAP_PIECE_SAFETY       = "piece_safety"
GAP_IGNORE_THREAT      = "ignore_threat"
GAP_CALCULATION_DEPTH  = "calculation_depth"
GAP_MISSED_TACTIC      = "missed_tactic"
GAP_TACTICAL_OVERSIGHT = "tactical_oversight"
GAP_KING_SAFETY        = "king_safety"
GAP_PAWN_STRUCTURE     = "pawn_structure"
GAP_PIECE_ACTIVITY     = "piece_activity"
GAP_OPENING_KNOWLEDGE  = "opening_knowledge"
GAP_ENDGAME_TECHNIQUE  = "endgame_technique"


def _count_non_king_pieces(fen: str) -> int:
    """Piece count on the board excluding kings — used to detect endgame phase."""
    if not fen:
        return 32
    try:
        board_part = fen.split(" ", 1)[0]
        return sum(1 for ch in board_part if ch.isalpha() and ch not in "Kk")
    except Exception:
        return 32


def _is_pawn_move(move_uci: str, fen_before: str) -> bool:
    """True if the played move was a pawn move (from the side to move's POV)."""
    if not move_uci or len(move_uci) < 4 or not fen_before:
        return False
    try:
        import chess
        board = chess.Board(fen_before)
        mv = chess.Move.from_uci(move_uci)
        piece = board.piece_at(mv.from_square)
        return piece is not None and piece.piece_type == chess.PAWN
    except Exception:
        return False


def _king_under_attack(fen_before: str, user_is_side_to_move: bool = True) -> bool:
    """Rough check: is the side-to-move's king under immediate attack or highly exposed?"""
    if not fen_before:
        return False
    try:
        import chess
        board = chess.Board(fen_before)
        if board.is_check():
            return True
        king_sq = board.king(board.turn)
        if king_sq is None:
            return False
        # Count opponent attackers on squares adjacent to the king
        opp = not board.turn
        adj = chess.SquareSet(chess.BB_KING_ATTACKS[king_sq])
        attacker_count = sum(1 for sq in adj if board.attackers(opp, sq))
        return attacker_count >= 2
    except Exception:
        return False


def _best_move_is_forcing(best_move_san: str) -> bool:
    """Captures, checks, mate — the forcing-move family that defines 'missed tactic'."""
    if not best_move_san:
        return False
    return any(ch in best_move_san for ch in ("x", "+", "#"))


class CriticalReason(str, Enum):
    """Why a move is marked critical for coaching"""
    TACTICAL_ERROR = "tactical_error"       # cp_loss >= 100 or blunder
    TURNING_POINT = "turning_point"         # eval swing >= 120
    PATTERN_EVENT = "pattern_event"         # behavioral pattern detected
    MISSED_MATE = "missed_mate"             # had mate, didn't take it
    POSITIONAL_COLLAPSE = "positional_collapse"  # gradual position decay


@dataclass
class InterpretedMove:
    """Move with behavioral interpretation added"""
    move_number: int
    move_uci: str
    fen_before: str
    fen_after: str
    cp_loss: int
    eval_swing: int
    is_turning_point: bool
    evaluation: str  # good/mistake/blunder etc
    
    # Behavioral interpretation (NEW)
    cognitive_gap: Optional[str] = None
    is_critical: bool = False
    critical_reason: Optional[str] = None
    gap_confidence: float = 0.0
    gap_evidence: str = ""
    coaching_focus: str = ""


class AnalysisInterpreter:
    """
    Interprets raw Stockfish analysis to identify behavioral patterns.
    
    This is the bridge between engine truth and coaching insight.
    """
    
    def __init__(self, db=None):
        self.db = db
    
    def interpret_moves(
        self, 
        move_evaluations: List[Dict],
        user_color: str = "white"
    ) -> List[InterpretedMove]:
        """
        Process raw move evaluations and add behavioral interpretation.
        
        Args:
            move_evaluations: Raw moves from Stockfish analysis
            user_color: Which color the user played
            
        Returns:
            List of InterpretedMove with cognitive gap analysis
        """
        interpreted = []
        
        for move in move_evaluations:
            interpreted_move = self._interpret_single_move(move)
            interpreted.append(interpreted_move)
        
        # Second pass: detect patterns across moves
        self._detect_cross_move_patterns(interpreted)
        
        return interpreted
    
    def _interpret_single_move(self, move: Dict) -> InterpretedMove:
        """Interpret a single move for behavioral patterns"""
        
        cp_loss = move.get("cp_loss", 0)
        eval_swing = move.get("eval_swing", 0)
        is_turning_point = move.get("is_turning_point", False)
        evaluation = move.get("evaluation", "good")
        fen_before = move.get("fen_before", "")
        fen_after = move.get("fen_after", "")
        mate_info = move.get("mate_info")
        
        # Initialize interpretation
        cognitive_gap = None
        is_critical = False
        critical_reason = None
        gap_confidence = 0.0
        gap_evidence = ""
        coaching_focus = ""
        
        # TRIGGER 1: Tactical Severity (cp_loss >= 100)
        if cp_loss >= 100 or evaluation in ["blunder", "mistake"]:
            is_critical = True
            critical_reason = CriticalReason.TACTICAL_ERROR.value
            
            # Run cognitive gap analysis
            gap_result = self._analyze_gap(move)
            if gap_result:
                cognitive_gap = gap_result.get("primary_gap")
                gap_confidence = gap_result.get("confidence", 0.0)
                gap_evidence = gap_result.get("evidence", "")
                coaching_focus = gap_result.get("coaching_focus", "")
        
        # TRIGGER 2: Missed Mate
        if mate_info and mate_info.get("before") is not None:
            # Had mate before but maybe lost it
            mate_before = mate_info.get("before")
            mate_after = mate_info.get("after")
            
            if mate_before is not None and (mate_after is None or abs(mate_after) > abs(mate_before) + 2):
                is_critical = True
                critical_reason = CriticalReason.MISSED_MATE.value
                cognitive_gap = CognitiveGap.TACTICAL_OVERSIGHT.value
        
        # TRIGGER 3: Turning Point (eval swing >= 120)
        if is_turning_point and not is_critical:
            is_critical = True
            critical_reason = CriticalReason.TURNING_POINT.value
            
            # Analyze why momentum shifted
            gap_result = self._analyze_gap(move)
            if gap_result:
                cognitive_gap = gap_result.get("primary_gap")
                gap_confidence = gap_result.get("confidence", 0.0)
        
        # TRIGGER 4: Pattern Event (from cognitive gap detection)
        if not is_critical and fen_before:
            gap_result = self._analyze_gap(move)
            if gap_result and gap_result.get("is_behavior_event"):
                is_critical = True
                critical_reason = CriticalReason.PATTERN_EVENT.value
                cognitive_gap = gap_result.get("primary_gap")
                gap_confidence = gap_result.get("confidence", 0.0)
                gap_evidence = gap_result.get("evidence", "")
                coaching_focus = gap_result.get("coaching_focus", "")
        
        return InterpretedMove(
            move_number=move.get("move_number", 0),
            move_uci=move.get("move_uci", ""),
            fen_before=fen_before,
            fen_after=fen_after,
            cp_loss=cp_loss,
            eval_swing=eval_swing,
            is_turning_point=is_turning_point,
            evaluation=evaluation,
            cognitive_gap=cognitive_gap,
            is_critical=is_critical,
            critical_reason=critical_reason,
            gap_confidence=gap_confidence,
            gap_evidence=gap_evidence,
            coaching_focus=coaching_focus
        )
    
    def _analyze_gap(self, move: Dict) -> Optional[Dict]:
        """
        Classify the cognitive gap behind a critical move.

        Emits one of the canonical CLAUDE.md taxonomy strings (see GAP_*
        constants above). Priority-ordered: phase-specific gaps first
        (opening / endgame), then king/piece safety, then threat / tactic
        detectors, then pawn/piece framing, then a cp-loss fallback.
        Earlier detectors are more specific — they claim the move before
        generic buckets swallow it.
        """
        try:
            fen_before = move.get("fen_before", "")
            played_uci = move.get("move_uci", "")
            best_move_san = move.get("best_move", "")
            cp_loss = move.get("cp_loss", 0)
            evaluation = move.get("evaluation", "good")
            threat = move.get("threat")
            move_number = move.get("move_number", 0) or 0

            if not fen_before:
                return None

            piece_count = _count_non_king_pieces(fen_before)
            is_opening = move_number > 0 and move_number <= 10
            is_endgame = piece_count <= 12

            primary_gap = None
            confidence = 0.0
            evidence = ""
            coaching_focus = ""
            is_behavior_event = False

            # Phase-specific takes priority — these are MORE specific
            # explanations than the generic cp-loss fallback.
            if cp_loss >= 100 and is_opening:
                primary_gap = GAP_OPENING_KNOWLEDGE
                confidence = 0.7
                evidence = f"Opening move {move_number} lost {cp_loss}cp"
                coaching_focus = "Learn the ideas behind the opening, not just the moves"

            if primary_gap is None and cp_loss >= 100 and is_endgame:
                primary_gap = GAP_ENDGAME_TECHNIQUE
                confidence = 0.75
                evidence = f"Endgame slip cost {cp_loss}cp"
                coaching_focus = "Active king, passed pawns, clean technique"

            # King safety — run before hanging-piece so a checked/exposed
            # king claims the move.
            if primary_gap is None and cp_loss >= 100:
                try:
                    if _king_under_attack(fen_before):
                        primary_gap = GAP_KING_SAFETY
                        confidence = 0.8
                        evidence = "King under pressure here"
                        coaching_focus = "Check the king's safety before attacking"
                        is_behavior_event = True
                except Exception:
                    pass

            # Hanging piece → piece_safety (canonical CLAUDE.md name).
            if primary_gap is None:
                try:
                    hanging = find_hanging_pieces(fen_before)
                    if hanging:
                        primary_gap = GAP_PIECE_SAFETY
                        confidence = 0.8
                        evidence = f"Undefended piece on {hanging[0]}"
                        coaching_focus = "Scan for undefended pieces before moving"
                        is_behavior_event = True
                except Exception:
                    pass

            # Opponent had a real threat that was ignored.
            if primary_gap is None:
                try:
                    threats = find_threats(fen_before)
                    if threats and (threat or evaluation in ("blunder", "mistake")):
                        primary_gap = GAP_IGNORE_THREAT
                        confidence = 0.8
                        evidence = f"Opponent threat: {threat or 'unaddressed'}"
                        coaching_focus = "Name the threat before picking your move"
                        is_behavior_event = True
                except Exception:
                    pass

            # Best move was a forcing move (capture/check/mate) the player
            # didn't see — the classic "missed tactic".
            if primary_gap is None and cp_loss >= 150 and _best_move_is_forcing(best_move_san):
                primary_gap = GAP_MISSED_TACTIC
                confidence = 0.7
                evidence = f"Missed {best_move_san}"
                coaching_focus = "Scan checks, captures, threats every move"

            # Pawn move with lasting structural cost.
            if primary_gap is None and cp_loss >= 100 and _is_pawn_move(played_uci, fen_before):
                primary_gap = GAP_PAWN_STRUCTURE
                confidence = 0.6
                evidence = "Pawn move with lasting positional cost"
                coaching_focus = "Every pawn push is permanent — think before pushing"

            # Best move was a quiet piece repositioning → piece activity / coordination.
            if primary_gap is None and cp_loss >= 100 and best_move_san and not _best_move_is_forcing(best_move_san):
                if not _is_pawn_move(played_uci, fen_before):
                    primary_gap = GAP_PIECE_ACTIVITY
                    confidence = 0.55
                    evidence = f"A quieter move ({best_move_san}) improved piece coordination"
                    coaching_focus = "Look for moves that activate sleeping pieces"

            # cp-loss fallback — the generic buckets catch anything the
            # specific detectors above missed.
            if primary_gap is None:
                if evaluation == "blunder" and cp_loss >= 300:
                    primary_gap = GAP_TACTICAL_OVERSIGHT
                    confidence = 0.9
                    evidence = f"Lost {cp_loss} centipawns"
                    coaching_focus = "Pause for the opponent's best reply"
                elif evaluation == "mistake" and cp_loss >= 100:
                    primary_gap = GAP_CALCULATION_DEPTH
                    confidence = 0.7
                    evidence = "One move deeper was needed"
                    coaching_focus = "Calculate one move deeper"
                elif move.get("is_turning_point"):
                    primary_gap = GAP_CALCULATION_DEPTH
                    confidence = 0.5
                    evidence = "Position shifted here"
                    coaching_focus = "Re-evaluate after each exchange"
                    is_behavior_event = True

            if primary_gap:
                return {
                    "primary_gap": primary_gap,
                    "confidence": confidence,
                    "evidence": evidence,
                    "coaching_focus": coaching_focus,
                    "is_behavior_event": is_behavior_event
                }

            return None

        except Exception as e:
            logger.warning(f"Gap analysis failed: {e}")
            return None
    
    def _detect_cross_move_patterns(self, moves: List[InterpretedMove]):
        """
        Detect patterns that span multiple moves.
        
        Examples:
        - Repeated threat blindness
        - Gradual positional collapse
        - Time pressure pattern
        """
        # Count cognitive gaps to detect patterns
        gap_counts = {}
        
        for move in moves:
            if move.cognitive_gap:
                gap_counts[move.cognitive_gap] = gap_counts.get(move.cognitive_gap, 0) + 1
        
        # If same gap appears 3+ times, mark later occurrences as pattern events
        repeated_gaps = {gap for gap, count in gap_counts.items() if count >= 3}
        
        occurrence_count = {}
        for move in moves:
            if move.cognitive_gap in repeated_gaps:
                occurrence_count[move.cognitive_gap] = occurrence_count.get(move.cognitive_gap, 0) + 1
                
                # Mark as critical if this is 2nd+ occurrence
                if occurrence_count[move.cognitive_gap] >= 2 and not move.is_critical:
                    move.is_critical = True
                    move.critical_reason = CriticalReason.PATTERN_EVENT.value
                    move.gap_evidence = f"Repeated pattern ({occurrence_count[move.cognitive_gap]}x)"
    
    def get_critical_moves(self, interpreted_moves: List[InterpretedMove]) -> List[InterpretedMove]:
        """Extract only the critical moves for PV enrichment"""
        return [m for m in interpreted_moves if m.is_critical]
    
    def get_interpretation_summary(self, interpreted_moves: List[InterpretedMove]) -> Dict:
        """
        Generate a summary of behavioral patterns found.
        
        Returns:
            Summary dict with pattern counts and primary issues
        """
        total = len(interpreted_moves)
        critical = sum(1 for m in interpreted_moves if m.is_critical)
        
        # Count by reason
        reason_counts = {}
        for m in interpreted_moves:
            if m.critical_reason:
                reason_counts[m.critical_reason] = reason_counts.get(m.critical_reason, 0) + 1
        
        # Count by cognitive gap
        gap_counts = {}
        for m in interpreted_moves:
            if m.cognitive_gap:
                gap_counts[m.cognitive_gap] = gap_counts.get(m.cognitive_gap, 0) + 1
        
        # Find primary issue (most frequent gap)
        primary_issue = None
        max_count = 0
        for gap, count in gap_counts.items():
            if count > max_count:
                max_count = count
                primary_issue = gap
        
        return {
            "total_moves": total,
            "critical_moves": critical,
            "critical_percentage": round(critical / total * 100, 1) if total > 0 else 0,
            "reason_breakdown": reason_counts,
            "gap_breakdown": gap_counts,
            "primary_issue": primary_issue,
            "primary_issue_count": max_count
        }


def interpret_game_analysis(
    move_evaluations: List[Dict],
    user_color: str = "white",
    db=None
) -> Tuple[List[Dict], Dict]:
    """
    Convenience function to interpret a full game analysis.
    
    Args:
        move_evaluations: Raw moves from Stockfish
        user_color: Player's color
        db: Optional database connection
        
    Returns:
        (enriched_moves, summary)
    """
    from position_context_service import enrich_moves_with_context
    
    interpreter = AnalysisInterpreter(db)
    interpreted = interpreter.interpret_moves(move_evaluations, user_color)
    summary = interpreter.get_interpretation_summary(interpreted)
    
    # Convert back to dict format for storage
    enriched_moves = []
    for i, m in enumerate(interpreted):
        # Get original move data for fields we don't have in InterpretedMove
        orig = move_evaluations[i] if i < len(move_evaluations) else {}
        
        enriched = {
            "move_number": m.move_number,
            "move": orig.get("move", ""),
            "move_uci": m.move_uci,
            "fen_before": m.fen_before,
            "fen_after": m.fen_after,
            "cp_loss": m.cp_loss,
            "eval_before": orig.get("eval_before", 0),
            "eval_after": orig.get("eval_after", 0),
            "eval_swing": m.eval_swing,
            "is_turning_point": m.is_turning_point,
            "evaluation": m.evaluation,
            "cognitive_gap": m.cognitive_gap,
            "is_critical": m.is_critical,
            "critical_reason": m.critical_reason,
            "gap_confidence": m.gap_confidence,
            "gap_evidence": m.gap_evidence,
            "coaching_focus": m.coaching_focus,
            # Preserve original fields
            "best_move": orig.get("best_move"),
            "best_move_uci": orig.get("best_move_uci"),
            "is_best": orig.get("is_best", False),
            "mate_info": orig.get("mate_info"),
            "pv_after_played": orig.get("pv_after_played", []),
            "pv_after_best": orig.get("pv_after_best", []),
            "threat": orig.get("threat")
        }
        enriched_moves.append(enriched)
    
    # Add position context to all moves
    enriched_moves = enrich_moves_with_context(enriched_moves, user_color)
    
    return enriched_moves, summary
