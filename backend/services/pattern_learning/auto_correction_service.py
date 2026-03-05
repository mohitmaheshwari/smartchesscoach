"""
Auto-Correction Service

The main orchestrator for the self-learning pattern recognition system.
This service:
1. Receives user feedback on wrong explanations
2. Triggers the pattern learner AI
3. Validates and stores new rules
4. Provides real-time corrected explanations
5. Enables cross-user learning

Usage:
    service = AutoCorrectionService()
    
    # Submit feedback and get immediate correction
    result = await service.submit_feedback_and_correct(
        user_id="user123",
        position_fen="...",
        move_played="Nf3",
        system_classification="MISSED_TRAP",
        system_explanation="You could have trapped...",
        correct_classification="WALKED_INTO_FORK",
        user_explanation="The pawn forks my pieces",
        pv_after_played=["e5d4", "d4c3"]
    )
    
    # result contains:
    # - corrected_explanation (immediate fix)
    # - learning_status (whether a rule was generated)
    # - pattern_id (for tracking)
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

from .learning_db import LearningDB
from .feedback_collector import FeedbackCollector, UserFeedback
from .pattern_learner import PatternLearner, LearnedRule
from .rule_validator import RuleValidator, ValidationResult
from .rule_executor import RuleExecutor, ClassificationResult

logger = logging.getLogger(__name__)


class AutoCorrectionService:
    """
    Main service for the self-learning pattern recognition system.
    
    Provides:
    1. Real-time correction when users flag wrong explanations
    2. Background learning of new classification rules
    3. Cross-user propagation of corrections
    """
    
    def __init__(self, api_key: str = None, auto_approve_threshold: float = 0.85):
        """
        Initialize the auto-correction service.
        
        Args:
            api_key: OpenAI API key (optional, reads from env if not provided)
            auto_approve_threshold: Confidence threshold for auto-approving rules
        """
        self.db = LearningDB()
        self.collector = FeedbackCollector(self.db)
        self.learner = PatternLearner(api_key)
        self.validator = RuleValidator(self.db, auto_approve_threshold=auto_approve_threshold)
        self.executor = RuleExecutor(self.db)
        
        self._initialized = False
    
    async def initialize(self):
        """Initialize the service (load rules, etc.)"""
        if not self._initialized:
            await self.executor.load_rules()
            self._initialized = True
            logger.info("AutoCorrectionService initialized")
    
    async def submit_feedback_and_correct(
        self,
        user_id: str,
        position_fen: str,
        move_played: str,
        system_classification: str,
        system_explanation: str,
        correct_classification: str,
        user_explanation: str = "",
        move_san: str = "",
        eval_before: float = 0.0,
        eval_after: float = 0.0,
        best_move: str = "",
        pv_after_played: List[str] = None,
        game_id: str = "",
        move_number: int = 0,
        user_color: str = "white"
    ) -> Dict:
        """
        Submit feedback and get immediate correction.
        
        This is the main entry point. It:
        1. Stores the feedback
        2. Checks for existing corrections
        3. Generates a corrected explanation immediately
        4. Queues rule learning in background
        
        Returns:
            {
                "success": True,
                "feedback_id": "fb_xxx",
                "corrected_explanation": "The actual explanation...",
                "pattern": "WALKED_INTO_FORK",
                "learning_status": "queued" | "correction_exists" | "rule_generated",
                "rule_id": "lr_xxx" (if rule was generated)
            }
        """
        await self.initialize()
        
        # Create feedback object
        feedback = self.collector.create_feedback(
            user_id=user_id,
            position_fen=position_fen,
            move_played=move_played,
            system_classification=system_classification,
            system_explanation=system_explanation,
            correct_classification=correct_classification,
            user_explanation=user_explanation,
            move_san=move_san,
            eval_before=eval_before,
            eval_after=eval_after,
            best_move=best_move,
            pv_after_played=pv_after_played,
            game_id=game_id,
            move_number=move_number,
            user_color=user_color
        )
        
        # Validate feedback
        is_valid, error = self.collector.validate_feedback(feedback)
        if not is_valid:
            return {
                "success": False,
                "error": error
            }
        
        # Store feedback
        feedback_id = await self.collector.submit(feedback)
        
        # Check for existing correction
        signature = self.collector.extract_tactical_signature(feedback)
        existing_correction = await self.db.find_correction(signature)
        
        if existing_correction:
            # Use existing correction
            return {
                "success": True,
                "feedback_id": feedback_id,
                "corrected_explanation": existing_correction.get("corrected_explanation", ""),
                "pattern": correct_classification,
                "learning_status": "correction_exists",
                "correction_use_count": existing_correction.get("use_count", 0) + 1
            }
        
        # Generate immediate correction using AI
        corrected = await self._generate_immediate_correction(feedback.to_dict())
        
        # Store the correction for future use
        correction_data = {
            "correction_id": f"corr_{uuid.uuid4().hex[:12]}",
            "tactical_motif": correct_classification,
            "attacker_piece": self._extract_attacker_piece(pv_after_played, position_fen),
            "is_sequential": len(pv_after_played or []) > 1,
            "corrected_explanation": corrected.get("explanation", ""),
            "source_feedback_id": feedback_id,
            "stockfish_validated": True  # We trust PV data
        }
        await self.db.store_correction(correction_data)
        
        # Try to generate and validate a rule
        rule_result = await self._try_generate_rule(feedback.to_dict())
        
        result = {
            "success": True,
            "feedback_id": feedback_id,
            "corrected_explanation": corrected.get("explanation", ""),
            "pattern": correct_classification,
            "learning_status": "queued"
        }
        
        if rule_result and rule_result.get("rule_id"):
            result["learning_status"] = "rule_generated"
            result["rule_id"] = rule_result["rule_id"]
            result["rule_status"] = rule_result.get("status", "pending_review")
        
        return result
    
    async def _generate_immediate_correction(self, feedback: Dict) -> Dict:
        """Generate an immediate corrected explanation"""
        try:
            corrected = await self.learner.generate_corrected_explanation(feedback)
            if corrected:
                return {"explanation": corrected}
        except Exception as e:
            logger.error(f"Error generating correction: {e}")
        
        # Fallback to simple correction based on pattern
        pattern = feedback.get("correct_classification", "tactical error")
        return {
            "explanation": f"This was a {pattern.lower().replace('_', ' ')}. "
                          f"{feedback.get('user_explanation', '')}"
        }
    
    async def _try_generate_rule(self, feedback: Dict) -> Optional[Dict]:
        """Try to generate and validate a new rule from feedback"""
        try:
            # Analyze the feedback
            analysis = await self.learner.analyze_feedback(feedback)
            if "error" in analysis:
                logger.debug(f"Analysis failed: {analysis['error']}")
                return None
            
            # Generate a rule
            rule = await self.learner.generate_rule(feedback, analysis)
            if not rule:
                return None
            
            # Store the rule
            await self.db.store_rule(rule.to_dict())
            
            # Validate the rule
            validation = await self.validator.validate_rule(rule.to_dict())
            
            if validation.auto_approved:
                # Auto-approve and activate
                await self.validator.approve_rule(rule.rule_id, "auto")
                await self.executor.reload_rules()
                return {
                    "rule_id": rule.rule_id,
                    "status": "active",
                    "auto_approved": True
                }
            elif validation.is_valid:
                # Flag for review
                await self.validator.flag_for_review(
                    rule.rule_id, 
                    validation.recommendation
                )
                return {
                    "rule_id": rule.rule_id,
                    "status": "pending_review",
                    "needs_review": True
                }
            else:
                # Reject
                await self.validator.reject_rule(
                    rule.rule_id,
                    validation.rejection_reason
                )
                return {
                    "rule_id": rule.rule_id,
                    "status": "rejected",
                    "reason": validation.rejection_reason
                }
                
        except Exception as e:
            logger.error(f"Error generating rule: {e}")
            return None
    
    def _extract_attacker_piece(self, pv: List[str], fen: str) -> str:
        """Extract the attacking piece from PV"""
        if not pv or not fen:
            return "unknown"
        
        try:
            import chess
            board = chess.Board(fen)
            
            # Parse first PV move
            move_str = pv[0]
            if len(move_str) >= 4:
                move = chess.Move.from_uci(move_str)
            else:
                move = board.parse_san(move_str)
            
            piece = board.piece_at(move.from_square)
            if piece:
                return chess.piece_name(piece.piece_type)
        except Exception:
            pass
        
        return "unknown"
    
    async def classify_with_learned_rules(
        self,
        position_fen: str,
        move_played: str,
        pv_after_played: List[str],
        eval_drop: float,
        best_move: str = None,
        user_color: str = "white"
    ) -> Optional[ClassificationResult]:
        """
        Classify a move using learned rules.
        
        Call this before the hardcoded classifier to check if a learned
        rule can provide better classification.
        """
        await self.initialize()
        
        return self.executor.classify(
            position_fen=position_fen,
            move_played=move_played,
            pv_after_played=pv_after_played,
            eval_drop=eval_drop,
            best_move=best_move,
            user_color=user_color
        )
    
    async def get_correction_for_position(
        self,
        position_fen: str,
        move_played: str,
        pv_after_played: List[str],
        system_classification: str
    ) -> Optional[Dict]:
        """
        Check if we have a correction for this position/pattern.
        
        Use this to intercept classifications before displaying to user.
        """
        await self.initialize()
        
        # Build signature
        signature = {
            "tactical_motif": system_classification,
            "attacker_piece": self._extract_attacker_piece(pv_after_played, position_fen),
            "is_sequential": len(pv_after_played or []) > 1
        }
        
        return await self.db.find_correction(signature)
    
    async def approve_rule(self, rule_id: str, approved_by: str = "admin"):
        """Manually approve a rule pending review"""
        await self.validator.approve_rule(rule_id, approved_by)
        await self.executor.reload_rules()
    
    async def reject_rule(self, rule_id: str, reason: str):
        """Manually reject a rule"""
        await self.validator.reject_rule(rule_id, reason)
    
    async def get_pending_rules(self) -> List[Dict]:
        """Get rules pending human review"""
        return await self.validator.get_rules_pending_review()
    
    async def get_system_stats(self) -> Dict:
        """Get overall system statistics"""
        feedback_stats = await self.db.get_feedback_stats()
        rules_stats = await self.db.get_rules_stats()
        correction_stats = await self.db.get_correction_stats()
        
        return {
            "feedback": feedback_stats,
            "rules": rules_stats,
            "corrections": correction_stats,
            "loaded_rules": self.executor.get_rules_summary()
        }
    
    async def track_classification_feedback(
        self,
        rule_id: str,
        was_correct: bool
    ):
        """Track whether a classification was correct (for rule accuracy)"""
        await self.executor.track_rule_usage(rule_id, was_correct)
    
    async def deprecate_low_accuracy_rules(self, threshold: float = 0.7):
        """Deprecate rules that have fallen below accuracy threshold"""
        low_accuracy = await self.db.get_low_accuracy_rules(threshold)
        
        for rule in low_accuracy:
            await self.db.update_rule_status(
                rule.get("rule_id"),
                "deprecated",
                f"Accuracy fell below {threshold}: {rule.get('stats', {}).get('accuracy_rate', 0)}"
            )
            logger.info(f"Deprecated rule {rule.get('rule_id')} due to low accuracy")
        
        # Reload rules without deprecated ones
        await self.executor.reload_rules()
        
        return len(low_accuracy)


# Global instance for easy access
_service_instance: Optional[AutoCorrectionService] = None


def get_auto_correction_service() -> AutoCorrectionService:
    """Get the global auto-correction service instance"""
    global _service_instance
    if _service_instance is None:
        _service_instance = AutoCorrectionService()
    return _service_instance
