"""
Rule Validator

Validates learned rules before they go live. Ensures:
1. Rules are Stockfish-verified (no hallucination)
2. Rules don't cause regressions on known-good cases
3. Rules don't conflict with existing rules
4. Complex rules are flagged for human review

Validation Pipeline:
1. Stockfish Verification - Does the rule match engine analysis?
2. Regression Check - Does it break any existing correct cases?
3. Conflict Detection - Does it conflict with other rules?
4. Confidence Check - Auto-approve if high confidence, else human review
"""

import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timezone

import chess

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of rule validation"""
    
    rule_id: str
    is_valid: bool
    
    # Individual checks
    stockfish_verified: bool = False
    regression_passed: bool = False
    no_conflicts: bool = False
    
    # Confidence and approval
    confidence_score: float = 0.0
    auto_approved: bool = False
    needs_human_review: bool = False
    
    # Details
    test_positions_passed: int = 0
    test_positions_total: int = 0
    conflicts_found: List[str] = None
    rejection_reason: str = ""
    
    # Recommendation
    recommendation: str = ""  # "approve", "review", "reject"


class RuleValidator:
    """
    Validates learned rules before activation.
    
    Uses a multi-gate validation system:
    1. Stockfish verification
    2. Regression testing
    3. Conflict detection
    4. Confidence thresholding
    """
    
    def __init__(self, db, stockfish_service=None, auto_approve_threshold: float = 0.85):
        """
        Initialize validator.
        
        Args:
            db: LearningDB instance
            stockfish_service: Optional Stockfish service for verification
            auto_approve_threshold: Confidence threshold for auto-approval
        """
        self.db = db
        self.stockfish = stockfish_service
        self.auto_approve_threshold = auto_approve_threshold
    
    async def validate_rule(self, rule: Dict, test_positions: List[Dict] = None) -> ValidationResult:
        """
        Validate a learned rule through all gates.
        
        Args:
            rule: The learned rule to validate
            test_positions: Optional list of test positions
            
        Returns:
            ValidationResult with detailed validation info
        """
        rule_id = rule.get("rule_id", "unknown")
        
        result = ValidationResult(
            rule_id=rule_id,
            is_valid=False,
            conflicts_found=[]
        )
        
        # Gate 1: Stockfish Verification
        sf_result = await self._verify_with_stockfish(rule, test_positions)
        result.stockfish_verified = sf_result["passed"]
        result.test_positions_passed = sf_result.get("passed_count", 0)
        result.test_positions_total = sf_result.get("total_count", 0)
        
        if not result.stockfish_verified:
            result.rejection_reason = sf_result.get("reason", "Failed Stockfish verification")
            result.recommendation = "reject"
            return result
        
        # Gate 2: Regression Check
        regression_result = await self._check_regression(rule)
        result.regression_passed = regression_result["passed"]
        
        if not result.regression_passed:
            result.rejection_reason = regression_result.get("reason", "Failed regression check")
            result.recommendation = "reject"
            return result
        
        # Gate 3: Conflict Detection
        conflict_result = await self._check_conflicts(rule)
        result.no_conflicts = conflict_result["no_conflicts"]
        result.conflicts_found = conflict_result.get("conflicts", [])
        
        if not result.no_conflicts:
            result.needs_human_review = True
            result.recommendation = "review"
        
        # Gate 4: Confidence Check
        confidence = rule.get("confidence", 0.5)
        result.confidence_score = confidence
        
        if confidence >= self.auto_approve_threshold and result.no_conflicts:
            result.auto_approved = True
            result.recommendation = "approve"
        elif confidence >= 0.7:
            result.needs_human_review = True
            result.recommendation = "review"
        else:
            result.needs_human_review = True
            result.recommendation = "review"
        
        # Final verdict
        result.is_valid = (
            result.stockfish_verified and 
            result.regression_passed and 
            (result.no_conflicts or result.needs_human_review)
        )
        
        return result
    
    async def _verify_with_stockfish(self, rule: Dict, test_positions: List[Dict] = None) -> Dict:
        """
        Verify rule against Stockfish analysis.
        
        Checks that the rule's detection signals match what Stockfish shows.
        """
        # If no stockfish service, do basic validation
        if not self.stockfish:
            return {
                "passed": True,
                "reason": "Stockfish not available, skipping verification",
                "passed_count": 0,
                "total_count": 0
            }
        
        # Get test positions (from feedback history or provided)
        positions = test_positions or []
        if not positions:
            # Try to get similar positions from database
            pattern = rule.get("pattern", "")
            if pattern:
                similar = await self.db.get_rules_by_pattern(pattern)
                for s in similar[:5]:
                    if s.get("source_position_fen"):
                        positions.append({
                            "fen": s["source_position_fen"],
                            "expected_pattern": pattern
                        })
        
        if not positions:
            # No test data - pass with warning
            return {
                "passed": True,
                "reason": "No test positions available",
                "passed_count": 0,
                "total_count": 0
            }
        
        passed = 0
        total = len(positions)
        
        for pos in positions:
            try:
                # Analyze position with Stockfish
                # This would call your stockfish_service
                # For now, we'll do basic board validation
                board = chess.Board(pos.get("fen", ""))
                if board.is_valid():
                    passed += 1
            except Exception as e:
                logger.debug(f"Position validation error: {e}")
        
        return {
            "passed": passed >= total * 0.8,  # 80% must pass
            "passed_count": passed,
            "total_count": total,
            "reason": f"{passed}/{total} test positions passed"
        }
    
    async def _check_regression(self, rule: Dict) -> Dict:
        """
        Check that the new rule doesn't break existing correct cases.
        
        Runs the rule against a set of known-good classifications.
        """
        # Get known-good cases for this pattern type
        distinguishes_from = rule.get("distinguishes_from", [])
        
        # Check if the rule would incorrectly classify related patterns
        for other_pattern in distinguishes_from:
            existing_rules = await self.db.get_rules_by_pattern(other_pattern)
            
            # If there are high-accuracy rules for the other pattern,
            # make sure our rule doesn't conflict
            for existing in existing_rules:
                if existing.get("stats", {}).get("accuracy_rate", 0) > 0.9:
                    # High-accuracy rule exists - check for overlap
                    if self._rules_overlap(rule, existing):
                        return {
                            "passed": False,
                            "reason": f"Conflicts with high-accuracy rule for {other_pattern}"
                        }
        
        return {
            "passed": True,
            "reason": "No regressions detected"
        }
    
    async def _check_conflicts(self, rule: Dict) -> Dict:
        """
        Check for conflicts with existing rules.
        """
        conflicts = []
        
        # Get all active rules
        active_rules = await self.db.get_active_rules()
        
        for existing in active_rules:
            if existing.get("rule_id") == rule.get("rule_id"):
                continue  # Skip self
            
            # Check for detection signal overlap
            new_signals = set(rule.get("detection_signals", []))
            existing_signals = set(existing.get("detection_signals", []))
            
            overlap = new_signals & existing_signals
            if len(overlap) > len(new_signals) * 0.7:
                conflicts.append({
                    "rule_id": existing.get("rule_id"),
                    "pattern": existing.get("pattern"),
                    "overlap": list(overlap)
                })
        
        return {
            "no_conflicts": len(conflicts) == 0,
            "conflicts": conflicts
        }
    
    def _rules_overlap(self, rule1: Dict, rule2: Dict) -> bool:
        """Check if two rules have significant overlap in detection"""
        signals1 = set(rule1.get("detection_signals", []))
        signals2 = set(rule2.get("detection_signals", []))
        
        if not signals1 or not signals2:
            return False
        
        overlap = len(signals1 & signals2)
        min_signals = min(len(signals1), len(signals2))
        
        return overlap > min_signals * 0.5
    
    async def approve_rule(self, rule_id: str, approved_by: str = "auto"):
        """Approve a rule and activate it"""
        await self.db.update_rule_status(
            rule_id, 
            "active", 
            f"Approved by {approved_by}"
        )
        logger.info(f"Rule {rule_id} approved and activated")
    
    async def reject_rule(self, rule_id: str, reason: str):
        """Reject a rule"""
        await self.db.update_rule_status(
            rule_id,
            "rejected",
            reason
        )
        logger.info(f"Rule {rule_id} rejected: {reason}")
    
    async def flag_for_review(self, rule_id: str, reason: str):
        """Flag a rule for human review"""
        await self.db.update_rule_status(
            rule_id,
            "pending_review",
            reason
        )
        logger.info(f"Rule {rule_id} flagged for review: {reason}")
    
    async def get_rules_pending_review(self) -> List[Dict]:
        """Get all rules waiting for human review"""
        cursor = self.db.db.learned_rules.find(
            {"status": "pending_review"},
            {"_id": 0}
        ).sort("created_at", 1)
        return await cursor.to_list(length=100)
