"""
Coach Moment Selector - Teaching Moment Selection Engine

Selects the most coaching-relevant move from a game, not just the
biggest engine mistake.

Principle: Coaches surface learning opportunities, not damage reports.

Uses Coaching Relevance Score (CRS):
  CRS = BehaviorScore + TurningPointScore + TacticalScore + ContextScore

This replaces simple "highest cp_loss" selection.
"""

import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

from position_context_service import (
    derive_position_context,
    compute_context_score,
    PositionState
)

logger = logging.getLogger(__name__)


class SelectionReason(str, Enum):
    """Why a move was selected as the teaching moment"""
    PATTERN_EVENT = "pattern_event"       # Recurring behavioral error
    TURNING_POINT = "turning_point"       # Game-deciding moment
    TACTICAL_ERROR = "tactical_error"     # Significant material/eval loss
    MISSED_MATE = "missed_mate"           # Failed to see forced mate
    ADVANTAGE_SQUANDER = "advantage_squander"  # Lost winning position


@dataclass
class CRSBreakdown:
    """Detailed breakdown of Coaching Relevance Score"""
    behavior_score: float = 0.0
    turning_point_score: float = 0.0
    tactical_score: float = 0.0
    context_score: float = 0.0
    total: float = 0.0
    
    def to_dict(self) -> Dict:
        return {
            "behavior": round(self.behavior_score, 1),
            "turning_point": round(self.turning_point_score, 1),
            "tactical": round(self.tactical_score, 1),
            "context": round(self.context_score, 1),
            "total": round(self.total, 1)
        }


@dataclass
class ScoredMove:
    """A critical move with its coaching relevance score"""
    move_number: int
    move_uci: str
    fen_before: str
    fen_after: str
    cp_loss: int
    eval_swing: int
    evaluation: str
    cognitive_gap: Optional[str]
    critical_reason: Optional[str]
    pattern_frequency: int = 0
    
    # Scoring
    crs: CRSBreakdown = field(default_factory=CRSBreakdown)
    selection_reason: Optional[str] = None
    
    # Position context
    position_context: Dict = field(default_factory=dict)
    
    # Move data for explanation
    pv_after_played: List[str] = field(default_factory=list)
    pv_after_best: List[str] = field(default_factory=list)
    threat: Optional[str] = None
    best_move: Optional[str] = None
    gap_evidence: str = ""
    coaching_focus: str = ""
    
    def to_dict(self) -> Dict:
        return {
            "move_number": self.move_number,
            "move_uci": self.move_uci,
            "fen_before": self.fen_before,
            "fen_after": self.fen_after,
            "cp_loss": self.cp_loss,
            "eval_swing": self.eval_swing,
            "evaluation": self.evaluation,
            "cognitive_gap": self.cognitive_gap,
            "critical_reason": self.critical_reason,
            "pattern_frequency": self.pattern_frequency,
            "crs": self.crs.to_dict(),
            "selection_reason": self.selection_reason,
            "position_context": self.position_context,
            "pv_after_played": self.pv_after_played,
            "pv_after_best": self.pv_after_best,
            "threat": self.threat,
            "best_move": self.best_move,
            "gap_evidence": self.gap_evidence,
            "coaching_focus": self.coaching_focus
        }


@dataclass
class SelectionResult:
    """Result of coaching moment selection"""
    selected_move: ScoredMove
    selection_score: float
    selection_reason: str
    runner_up_moves: List[Dict]  # Top 2-3 alternatives
    total_critical_moves: int
    selection_factors: List[str]
    
    def to_dict(self) -> Dict:
        return {
            "selected_move": self.selected_move.to_dict(),
            "selection_score": round(self.selection_score, 1),
            "selection_reason": self.selection_reason,
            "runner_up_moves": self.runner_up_moves,
            "total_critical_moves": self.total_critical_moves,
            "selection_factors": self.selection_factors
        }


class CoachMomentSelector:
    """
    Selects the most coaching-relevant moment from a game.
    
    Uses CRS (Coaching Relevance Score) to rank critical moves
    and select the best teaching opportunity.
    """
    
    # CRS Weights (tuned for coaching relevance)
    BEHAVIOR_BASE = 100       # Base score for pattern events
    BEHAVIOR_FREQUENCY_MULT = 15  # Bonus per occurrence
    TURNING_POINT_MULT = 0.6  # Multiplier for eval swing
    TACTICAL_MULT = 0.4       # Multiplier for cp_loss
    MISSED_MATE_BONUS = 150   # Bonus for missed short mates
    
    def __init__(self):
        pass
    
    def select_teaching_moment(
        self,
        moves: List[Dict],
        user_color: str,
        game_result: str = None
    ) -> Optional[SelectionResult]:
        """
        Select the most coaching-relevant move from a game.
        
        Args:
            moves: List of enriched move evaluations
            user_color: "white" or "black"
            game_result: "1-0", "0-1", "1/2-1/2"
            
        Returns:
            SelectionResult with selected move and alternatives
        """
        # Step 1: Filter to critical moves only
        critical_moves = [m for m in moves if m.get("is_critical", False)]
        
        if not critical_moves:
            logger.info("No critical moves found in game")
            return None
        
        # Step 2: Count pattern frequencies for behavior scoring
        pattern_counts = self._count_patterns(critical_moves)
        
        # Step 3: Score each critical move
        scored_moves = []
        for move in critical_moves:
            scored = self._score_move(move, user_color, pattern_counts, game_result)
            scored_moves.append(scored)
        
        # Step 4: Sort by total CRS (descending)
        scored_moves.sort(key=lambda m: m.crs.total, reverse=True)
        
        # Step 5: Apply special overrides (missed mate always surfaces)
        scored_moves = self._apply_overrides(scored_moves)
        
        # Step 6: Select winner and compile result
        winner = scored_moves[0]
        runner_ups = [m.to_dict() for m in scored_moves[1:4]]  # Top 3 alternatives
        
        # Determine selection reason
        selection_reason = self._determine_selection_reason(winner)
        winner.selection_reason = selection_reason
        
        # Compile factors that contributed to selection
        factors = self._get_selection_factors(winner)
        
        return SelectionResult(
            selected_move=winner,
            selection_score=winner.crs.total,
            selection_reason=selection_reason,
            runner_up_moves=runner_ups,
            total_critical_moves=len(critical_moves),
            selection_factors=factors
        )
    
    def _count_patterns(self, moves: List[Dict]) -> Dict[str, int]:
        """Count occurrences of each cognitive gap type"""
        counts = {}
        for move in moves:
            gap = move.get("cognitive_gap")
            if gap:
                counts[gap] = counts.get(gap, 0) + 1
        return counts
    
    def _score_move(
        self,
        move: Dict,
        user_color: str,
        pattern_counts: Dict[str, int],
        game_result: str
    ) -> ScoredMove:
        """
        Compute CRS for a single move.
        
        CRS = BehaviorScore + TurningPointScore + TacticalScore + ContextScore
        """
        # Extract move data
        move_number = move.get("move_number", 0)
        move_uci = move.get("move_uci", "")
        fen_before = move.get("fen_before", "")
        fen_after = move.get("fen_after", "")
        cp_loss = move.get("cp_loss", 0)
        eval_swing = move.get("eval_swing", 0)
        evaluation = move.get("evaluation", "")
        cognitive_gap = move.get("cognitive_gap")
        critical_reason = move.get("critical_reason")
        
        # Get or compute position context
        position_context = move.get("position_context", {})
        if not position_context:
            eval_before = move.get("eval_before", 0)
            eval_after = move.get("eval_after", 0)
            mate_info = move.get("mate_info", {})
            mate_before = mate_info.get("before") if mate_info else None
            mate_after = mate_info.get("after") if mate_info else None
            
            context = derive_position_context(
                eval_before, eval_after, user_color,
                mate_before, mate_after
            )
            position_context = context.to_dict()
        
        # Initialize scores
        behavior_score = 0.0
        turning_point_score = 0.0
        tactical_score = 0.0
        context_score = 0.0
        
        # Get pattern frequency for this gap
        pattern_frequency = pattern_counts.get(cognitive_gap, 0) if cognitive_gap else 0
        
        # =====================================================================
        # 1. BEHAVIOR SCORE (Most important for coaching)
        # =====================================================================
        if critical_reason == "pattern_event" or pattern_frequency >= 2:
            behavior_score = self.BEHAVIOR_BASE + (pattern_frequency * self.BEHAVIOR_FREQUENCY_MULT)
        elif cognitive_gap:
            # Some behavior signal even without full pattern
            behavior_score = 30 + (pattern_frequency * 10)
        
        # =====================================================================
        # 2. TURNING POINT SCORE
        # =====================================================================
        if move.get("is_turning_point") or eval_swing >= 120:
            # Cap at 300 to prevent outliers from dominating
            turning_point_score = min(eval_swing, 300) * self.TURNING_POINT_MULT
        
        # =====================================================================
        # 3. TACTICAL SCORE
        # =====================================================================
        # Scale by cp_loss but don't let it dominate
        tactical_score = cp_loss * self.TACTICAL_MULT
        
        # Bonus for blunders (high confidence teaching moment)
        if evaluation == "blunder":
            tactical_score += 30
        elif evaluation == "mistake":
            tactical_score += 15
        
        # =====================================================================
        # 4. CONTEXT SCORE (from position context)
        # =====================================================================
        if position_context.get("result_flipped"):
            context_score += 70
        elif position_context.get("advantage_lost"):
            context_score += 50
        elif position_context.get("pressure_released"):
            context_score += 30
        
        if position_context.get("is_decisive_moment"):
            context_score += 20
        
        # Bonus if this move aligns with game result
        if game_result:
            user_lost = (
                (user_color == "white" and game_result == "0-1") or
                (user_color == "black" and game_result == "1-0")
            )
            if user_lost and position_context.get("advantage_lost"):
                context_score += 25  # This might be THE moment they lost
        
        # =====================================================================
        # 5. MISSED MATE BONUS (Special case)
        # =====================================================================
        mate_info = move.get("mate_info", {})
        if mate_info and mate_info.get("before") is not None:
            mate_in = abs(mate_info.get("before", 99))
            if mate_in <= 5:
                tactical_score += self.MISSED_MATE_BONUS
        
        # Calculate total
        total = behavior_score + turning_point_score + tactical_score + context_score
        
        crs = CRSBreakdown(
            behavior_score=behavior_score,
            turning_point_score=turning_point_score,
            tactical_score=tactical_score,
            context_score=context_score,
            total=total
        )
        
        return ScoredMove(
            move_number=move_number,
            move_uci=move_uci,
            fen_before=fen_before,
            fen_after=fen_after,
            cp_loss=cp_loss,
            eval_swing=eval_swing,
            evaluation=evaluation,
            cognitive_gap=cognitive_gap,
            critical_reason=critical_reason,
            pattern_frequency=pattern_frequency,
            crs=crs,
            position_context=position_context,
            pv_after_played=move.get("pv_after_played", []),
            pv_after_best=move.get("pv_after_best", []),
            threat=move.get("threat"),
            best_move=move.get("best_move"),
            gap_evidence=move.get("gap_evidence", ""),
            coaching_focus=move.get("coaching_focus", "")
        )
    
    def _apply_overrides(self, scored_moves: List[ScoredMove]) -> List[ScoredMove]:
        """
        Apply special selection rules.
        
        Rule: Missed mate in ≤3 always surfaces (coaches never skip this).
        """
        for move in scored_moves:
            # Check for short missed mate
            if move.critical_reason == "missed_mate":
                # Boost to top if short mate
                move.crs.total += 500
        
        # Re-sort after override
        scored_moves.sort(key=lambda m: m.crs.total, reverse=True)
        return scored_moves
    
    def _determine_selection_reason(self, move: ScoredMove) -> str:
        """Determine the primary reason this move was selected"""
        crs = move.crs
        
        # Check which component contributed most
        scores = [
            (crs.behavior_score, SelectionReason.PATTERN_EVENT.value),
            (crs.turning_point_score, SelectionReason.TURNING_POINT.value),
            (crs.tactical_score, SelectionReason.TACTICAL_ERROR.value),
            (crs.context_score, SelectionReason.ADVANTAGE_SQUANDER.value)
        ]
        
        # If behavior dominates, it's a pattern event
        if crs.behavior_score >= 100:
            return SelectionReason.PATTERN_EVENT.value
        
        # If missed mate
        if move.critical_reason == "missed_mate":
            return SelectionReason.MISSED_MATE.value
        
        # Otherwise, highest contributor
        scores.sort(reverse=True)
        return scores[0][1]
    
    def _get_selection_factors(self, move: ScoredMove) -> List[str]:
        """Get human-readable factors that led to selection"""
        factors = []
        
        if move.crs.behavior_score >= 100:
            factors.append(f"recurring_pattern_{move.pattern_frequency}x")
        
        if move.crs.turning_point_score >= 100:
            factors.append("game_turning_point")
        
        if move.position_context.get("result_flipped"):
            factors.append("result_changed")
        
        if move.position_context.get("advantage_lost"):
            factors.append("advantage_squandered")
        
        if move.evaluation == "blunder":
            factors.append("blunder")
        
        if move.critical_reason == "missed_mate":
            factors.append("missed_forced_mate")
        
        if move.cognitive_gap:
            factors.append(f"gap_{move.cognitive_gap}")
        
        return factors if factors else ["tactical_significance"]


# ============================================================================
# CONVENIENCE FUNCTION
# ============================================================================

def select_teaching_moment(
    moves: List[Dict],
    user_color: str,
    game_result: str = None
) -> Optional[Dict]:
    """
    Convenience function to select the coaching moment.
    
    Args:
        moves: List of enriched move evaluations
        user_color: "white" or "black"  
        game_result: "1-0", "0-1", "1/2-1/2"
        
    Returns:
        Selection result as dict, or None if no critical moves
    """
    selector = CoachMomentSelector()
    result = selector.select_teaching_moment(moves, user_color, game_result)
    
    if result:
        return result.to_dict()
    return None
