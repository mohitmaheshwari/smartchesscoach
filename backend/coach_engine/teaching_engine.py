"""
Teaching Engine - Main Orchestrator

Combines:
- Wisdom Library (rules)
- Piece Metrics (position analysis)
- Rule Validator (two-gate system)
- De-duplication logic
- Output formatting

Strict no-hallucination policy enforced.
"""

import chess
import uuid
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone
from dataclasses import asdict

from .models import (
    CoachEvent, CoachingOutput, TeachingLevel, ReasonType,
    TRIGGER_THRESHOLDS, MAX_RULE_PER_GAME, MAX_RULE_MAIN_LESSON
)
from .wisdom_library import get_wisdom_library
from .piece_metrics import PieceMetricsAnalyzer
from .rule_validator import RuleValidator, ValidationResult, StockfishAnalysis, determine_teaching_level


class TeachingEngine:
    """
    Main teaching engine that orchestrates all components.
    
    Flow:
    1. Receive move + SF analysis
    2. Determine teaching level from eval delta
    3. Find applicable rules via two-gate validation
    4. Apply de-duplication
    5. Generate coaching output
    6. Log event for telemetry
    """
    
    def __init__(self, user_id: str, user_rating: int = 1200):
        self.user_id = user_id
        self.user_rating = user_rating
        self.library = get_wisdom_library()
        
        # De-duplication state
        self.rules_triggered_this_game: Dict[str, int] = {}  # rule_id -> count
        self.rule_history: List[Dict] = []  # Recent rule triggers across games
        
        # Event log
        self.events: List[CoachEvent] = []
    
    def process_move(
        self,
        board: chess.Board,
        user_move: chess.Move,
        user_color: chess.Color,
        sf_analysis: StockfishAnalysis,
        move_number: int,
        game_history: List[chess.Move] = None,
    ) -> Optional[CoachingOutput]:
        """
        Process a user move and generate coaching output if applicable.
        
        Returns None if:
        - Move is good (no teaching needed)
        - No rule matches with high enough confidence
        - De-duplication filters it out
        """
        
        # 1. Determine teaching level from eval delta
        level = determine_teaching_level(sf_analysis.delta_cp)
        
        # If move is fine, no teaching needed
        if level == TeachingLevel.OBSERVE and sf_analysis.delta_cp > -50:
            return None
        
        # 2. Find applicable rules
        validator = RuleValidator(board, user_color)
        applicable_rules = validator.find_applicable_rules(
            user_move, sf_analysis, move_number, game_history
        )
        
        # 3. If no rules match, engine-only feedback (no hallucination)
        if not applicable_rules:
            return self._generate_engine_only_output(
                board, user_move, sf_analysis, level
            )
        
        # 4. Apply de-duplication
        best_rule = self._select_rule_with_dedup(applicable_rules)
        
        if not best_rule:
            return self._generate_engine_only_output(
                board, user_move, sf_analysis, level
            )
        
        # 5. Generate coaching output
        output = self._generate_coaching_output(
            board, user_move, sf_analysis, best_rule, level
        )
        
        # 6. Log event
        self._log_event(board, user_move, sf_analysis, output, move_number, best_rule)
        
        # 7. Update de-duplication state
        self._update_dedup_state(best_rule.rule_id)
        
        return output
    
    def _select_rule_with_dedup(
        self, 
        applicable_rules: List[ValidationResult]
    ) -> Optional[ValidationResult]:
        """
        Select the best rule after applying de-duplication.
        
        Rules:
        - Same rule_id can trigger at most once per game as "teach"
        - Same rule_id cannot be main lesson more than N times in last 10 games
        """
        
        for rule in applicable_rules:
            # Check per-game limit
            if self.rules_triggered_this_game.get(rule.rule_id, 0) >= MAX_RULE_PER_GAME:
                continue
            
            # Check cross-game limit for main lessons
            recent_count = sum(
                1 for h in self.rule_history[-10:]
                if h.get("rule_id") == rule.rule_id and h.get("was_main_lesson")
            )
            
            if recent_count >= MAX_RULE_MAIN_LESSON:
                # Can still use as observation, not full teaching
                rule.confidence *= 0.5  # Reduce to observation level
            
            return rule
        
        return None
    
    def _generate_coaching_output(
        self,
        board: chess.Board,
        user_move: chess.Move,
        sf_analysis: StockfishAnalysis,
        validation: ValidationResult,
        level: TeachingLevel,
    ) -> CoachingOutput:
        """
        Generate coaching output following the strict contract:
        1. 1 sentence diagnosis (board-grounded)
        2. Your move vs SF move (delta required)
        3. 1 concrete reason
        4. 1 short rule
        """
        
        rule = self.library.get_rule(validation.rule_id)
        user_move_san = board.san(user_move)
        
        # Parse SF move
        try:
            sf_move = chess.Move.from_uci(sf_analysis.best_move)
            sf_move_san = board.san(sf_move)
        except:
            sf_move_san = sf_analysis.best_move
        
        # Build highlights
        highlights = self._build_highlights(validation.evidence)
        
        # Determine confidence and language
        confidence = validation.confidence
        if not sf_analysis.is_stable:
            confidence *= 0.8
        
        return CoachingOutput(
            diagnosis=validation.diagnosis,
            your_move=user_move_san,
            your_eval=sf_analysis.eval_after,
            sf_move=sf_move_san,
            sf_eval=sf_analysis.best_move_eval,
            delta_cp=sf_analysis.delta_cp,
            reason=rule.reason_type if rule else ReasonType.PIECE_ACTIVITY,
            reason_detail=validation.contrastive_reason or "Engine prefers a different approach",
            memorable_rule=rule.memorable_rule if rule else "",
            rule_id=validation.rule_id,
            level=level,
            confidence=confidence,
            highlights=highlights,
            question=self._get_question_if_pause(rule, level),
        )
    
    def _generate_engine_only_output(
        self,
        board: chess.Board,
        user_move: chess.Move,
        sf_analysis: StockfishAnalysis,
        level: TeachingLevel,
    ) -> Optional[CoachingOutput]:
        """
        Generate engine-only feedback when no rule matches.
        This is the "no creativity" fallback - just show SF preference.
        """
        
        # Only show if the mistake is significant
        if abs(sf_analysis.delta_cp) < 80:
            return None
        
        user_move_san = board.san(user_move)
        
        try:
            sf_move = chess.Move.from_uci(sf_analysis.best_move)
            sf_move_san = board.san(sf_move)
        except:
            sf_move_san = sf_analysis.best_move
        
        # Minimal, factual diagnosis
        if sf_analysis.delta_cp <= -250:
            diagnosis = "This move loses significant advantage."
        elif sf_analysis.delta_cp <= -120:
            diagnosis = "The engine prefers a different approach here."
        else:
            diagnosis = "A small inaccuracy."
        
        return CoachingOutput(
            diagnosis=diagnosis,
            your_move=user_move_san,
            your_eval=sf_analysis.eval_after,
            sf_move=sf_move_san,
            sf_eval=sf_analysis.best_move_eval,
            delta_cp=sf_analysis.delta_cp,
            reason=ReasonType.PIECE_ACTIVITY,
            reason_detail="Engine analysis",
            memorable_rule="",  # No rule - engine only
            rule_id=None,
            level=level,
            confidence=0.5,  # Lower confidence for engine-only
            highlights={},
        )
    
    def _build_highlights(self, evidence: Dict) -> Dict[str, str]:
        """Build board highlights from evidence"""
        highlights = {}
        
        # Highlight key squares from evidence
        if "bishop_square" in evidence:
            highlights[evidence["bishop_square"]] = "yellow"  # Piece being discussed
        if "pawn_square" in evidence:
            highlights[evidence["pawn_square"]] = "red"  # Blocking piece
        if "rook_square" in evidence:
            highlights[evidence["rook_square"]] = "yellow"
        if "worst_square" in evidence:
            highlights[evidence["worst_square"]] = "orange"
        if "square" in evidence:
            highlights[evidence["square"]] = "red"  # Problem square
        
        return highlights
    
    def _get_question_if_pause(self, rule, level: TeachingLevel) -> Optional[Dict]:
        """Get MCQ question if this is a pause-level mistake"""
        if level not in [TeachingLevel.PAUSE, TeachingLevel.BLUNDER]:
            return None
        
        if rule and rule.followup_questions:
            return rule.followup_questions[0]
        
        return None
    
    def _log_event(
        self,
        board: chess.Board,
        user_move: chess.Move,
        sf_analysis: StockfishAnalysis,
        output: CoachingOutput,
        move_number: int,
        validation: ValidationResult,
    ):
        """Log coaching event for telemetry and Lab replay"""
        
        event = CoachEvent(
            move_number=move_number,
            fen=board.fen(),
            user_move=user_move.uci(),
            best_move=sf_analysis.best_move,
            eval_before=sf_analysis.eval_before,
            eval_after=sf_analysis.eval_after,
            delta_cp=sf_analysis.delta_cp,
            rule_id=validation.rule_id if validation else None,
            level=output.level,
            question=output.question,
            coach_message_id=str(uuid.uuid4()),
            coach_message=output.to_chat_message(),
            highlights=list(output.highlights.keys()),
            created_at=datetime.now(timezone.utc),
        )
        
        self.events.append(event)
    
    def _update_dedup_state(self, rule_id: str):
        """Update de-duplication state after using a rule"""
        self.rules_triggered_this_game[rule_id] = (
            self.rules_triggered_this_game.get(rule_id, 0) + 1
        )
        
        self.rule_history.append({
            "rule_id": rule_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "was_main_lesson": True,
        })
        
        # Keep only last 20 entries
        if len(self.rule_history) > 20:
            self.rule_history = self.rule_history[-20:]
    
    def get_events(self) -> List[CoachEvent]:
        """Get all logged events for this session"""
        return self.events
    
    def get_events_as_dict(self) -> List[Dict]:
        """Get events as serializable dicts"""
        return [asdict(e) for e in self.events]
    
    def reset_game_state(self):
        """Reset per-game state (call at start of new game)"""
        self.rules_triggered_this_game = {}
    
    def load_rule_history(self, history: List[Dict]):
        """Load rule history from database (for cross-game dedup)"""
        self.rule_history = history


# ==================== HELPER FUNCTIONS ====================

def create_teaching_engine(user_id: str, user_rating: int = 1200) -> TeachingEngine:
    """Factory function to create a teaching engine"""
    return TeachingEngine(user_id, user_rating)


def process_single_move(
    fen: str,
    user_move_uci: str,
    user_color: str,
    sf_eval_before: float,
    sf_eval_after: float,
    sf_best_move: str,
    sf_best_eval: float,
    move_number: int,
    user_id: str = "test_user",
) -> Optional[Dict]:
    """
    Convenience function to process a single move.
    Returns coaching output as dict or None.
    """
    board = chess.Board(fen)
    user_move = chess.Move.from_uci(user_move_uci)
    color = chess.WHITE if user_color.lower() == "white" else chess.BLACK
    
    sf_analysis = StockfishAnalysis(
        eval_before=sf_eval_before,
        eval_after=sf_eval_after,
        delta_cp=int((sf_eval_after - sf_eval_before) * 100),
        best_move=sf_best_move,
        best_move_eval=sf_best_eval,
        pv_line=[sf_best_move],
        depth=20,
        is_stable=True,
    )
    
    engine = create_teaching_engine(user_id)
    output = engine.process_move(
        board, user_move, color, sf_analysis, move_number
    )
    
    if output:
        return {
            "diagnosis": output.diagnosis,
            "your_move": output.your_move,
            "sf_move": output.sf_move,
            "delta_cp": output.delta_cp,
            "reason": output.reason.value,
            "reason_detail": output.reason_detail,
            "memorable_rule": output.memorable_rule,
            "rule_id": output.rule_id,
            "level": output.level.value,
            "confidence": output.confidence,
            "chat_message": output.to_chat_message(),
            "highlights": output.highlights,
        }
    
    return None
