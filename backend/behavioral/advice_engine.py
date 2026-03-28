"""
Advice Engine Module

Registry-based rule engine for evaluating coach advice compliance.

Each rule implements:
- evaluate(facts, history, params) -> AdviceResult

AdviceResult contains:
- outcome: FOLLOWED | VIOLATED | NA
- applicable: bool (was the rule relevant to this game?)
- evidence: dict (proof of outcome)
- severity_weight: int (inherited from advice, used for weighted learning velocity)

Rules:
- OPENING_REPEAT_PIECE: Don't move same piece twice in opening
- TIME_PANIC: Don't make fast moves under time pressure
- HANGING_PIECE: Don't leave pieces undefended
- EARLY_QUEEN: Don't develop queen before minor pieces
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from abc import ABC, abstractmethod
import uuid
from datetime import datetime, timezone


@dataclass
class AdviceResult:
    """Result of evaluating a single advice rule"""
    outcome: str  # FOLLOWED | VIOLATED | NA
    applicable: bool  # Was the rule relevant to this game?
    evidence: Dict[str, Any]
    severity_weight: int  # Inherited from advice
    
    def to_dict(self):
        return {
            "outcome": self.outcome,
            "applicable": self.applicable,
            "evidence": self.evidence,
            "severity_weight": self.severity_weight
        }


class AdviceRule(ABC):
    """Abstract base class for advice rules"""
    
    @abstractmethod
    def evaluate(self, facts, history: List[Dict], params: Dict) -> AdviceResult:
        """
        Evaluate if the advice was followed in this game.
        
        Args:
            facts: BehaviorFeatures from feature_extractor
            history: List of recent game analyses
            params: Rule-specific parameters from advice.rule_params
            
        Returns:
            AdviceResult with outcome, applicability, evidence, and severity_weight
        """
        pass


class OpeningRepeatPieceRule(AdviceRule):
    """
    Rule: Don't move the same piece twice in the opening.
    
    Applicable: When user plays opening moves (moves 1-10)
    Followed: If repeat_piece_moves <= max_repeats (default 1)
    Violated: If repeat_piece_moves > max_repeats
    """
    
    def evaluate(self, facts, history: List[Dict], params: Dict) -> AdviceResult:
        max_repeats = params.get("max_repeats", 1)
        severity = params.get("severity_weight", 3)
        
        repeats = facts.repeat_piece_moves
        
        # Check applicability - did user play opening moves?
        if facts.total_moves < 5:
            return AdviceResult(
                outcome="NA",
                applicable=False,
                evidence={"reason": "Game too short to evaluate opening"},
                severity_weight=severity
            )
        
        # Rule is applicable
        if repeats <= max_repeats:
            return AdviceResult(
                outcome="FOLLOWED",
                applicable=True,
                evidence={"repeat_piece_moves": repeats, "max_allowed": max_repeats},
                severity_weight=severity
            )
        else:
            return AdviceResult(
                outcome="VIOLATED",
                applicable=True,
                evidence={"repeat_piece_moves": repeats, "max_allowed": max_repeats},
                severity_weight=severity
            )


class TimePanicRule(AdviceRule):
    """
    Rule: Under time pressure, slow down and choose the safest move.
    
    Applicable: When game had time pressure (clock < 30s at any point)
    Followed: If no blunders occurred during time pressure
    Violated: If blunders occurred during time pressure
    """
    
    def evaluate(self, facts, history: List[Dict], params: Dict) -> AdviceResult:
        severity = params.get("severity_weight", 4)
        
        # Check if game had time pressure
        if not facts.has_clock_data:
            return AdviceResult(
                outcome="NA",
                applicable=False,
                evidence={"reason": "No clock data available"},
                severity_weight=severity
            )
        
        # Check time pressure index
        if facts.time_pressure_index < 0.3:
            return AdviceResult(
                outcome="NA",
                applicable=False,
                evidence={"reason": "No significant time pressure in this game", 
                         "time_pressure_index": round(facts.time_pressure_index, 2)},
                severity_weight=severity
            )
        
        # Time pressure existed - check for blunders/tilt
        if facts.tilt_index >= 0.4 or (facts.time_pressure_index >= 0.5 and facts.blunder_count >= 2):
            return AdviceResult(
                outcome="VIOLATED",
                applicable=True,
                evidence={
                    "time_pressure_index": round(facts.time_pressure_index, 2),
                    "tilt_index": round(facts.tilt_index, 2),
                    "blunders_under_pressure": facts.blunder_count,
                    "collapse_move": facts.collapse_move
                },
                severity_weight=severity
            )
        else:
            return AdviceResult(
                outcome="FOLLOWED",
                applicable=True,
                evidence={
                    "time_pressure_index": round(facts.time_pressure_index, 2),
                    "tilt_index": round(facts.tilt_index, 2),
                    "maintained_composure": True
                },
                severity_weight=severity
            )


class HangingPieceRule(AdviceRule):
    """
    Rule: Check for hanging pieces before every move.
    
    Applicable: Always (unless game is very short)
    Followed: If no pieces were left hanging (no TACTICAL_BLINDNESS tag)
    Violated: If pieces were left hanging
    """
    
    def evaluate(self, facts, history: List[Dict], params: Dict) -> AdviceResult:
        severity = params.get("severity_weight", 4)
        
        if facts.total_moves < 10:
            return AdviceResult(
                outcome="NA",
                applicable=False,
                evidence={"reason": "Game too short to evaluate"},
                severity_weight=severity
            )
        
        # Check for tactical blindness (hanging pieces)
        tactical_blindness = facts.leak_tags_last_game.get("TACTICAL_BLINDNESS", 0)
        big_blunders = facts.blunder_count
        
        if tactical_blindness >= 1 or big_blunders >= 2:
            return AdviceResult(
                outcome="VIOLATED",
                applicable=True,
                evidence={
                    "tactical_blindness_count": tactical_blindness,
                    "big_blunders": big_blunders,
                    "first_blunder_move": facts.first_blunder_move
                },
                severity_weight=severity
            )
        else:
            return AdviceResult(
                outcome="FOLLOWED",
                applicable=True,
                evidence={
                    "tactical_blindness_count": 0,
                    "clean_game": True
                },
                severity_weight=severity
            )


class EarlyQueenRule(AdviceRule):
    """
    Rule: Develop minor pieces before bringing out the queen.
    
    Applicable: When user plays opening moves
    Followed: If early_queen_moves <= max_queen_moves (default 1)
    Violated: If early_queen_moves > max_queen_moves
    """
    
    def evaluate(self, facts, history: List[Dict], params: Dict) -> AdviceResult:
        max_queen_moves = params.get("max_queen_moves", 1)
        severity = params.get("severity_weight", 2)
        
        queen_moves = facts.early_queen_moves
        
        if facts.total_moves < 5:
            return AdviceResult(
                outcome="NA",
                applicable=False,
                evidence={"reason": "Game too short to evaluate opening"},
                severity_weight=severity
            )
        
        if queen_moves <= max_queen_moves:
            return AdviceResult(
                outcome="FOLLOWED",
                applicable=True,
                evidence={"early_queen_moves": queen_moves, "max_allowed": max_queen_moves},
                severity_weight=severity
            )
        else:
            return AdviceResult(
                outcome="VIOLATED",
                applicable=True,
                evidence={"early_queen_moves": queen_moves, "max_allowed": max_queen_moves},
                severity_weight=severity
            )


class OpeningWanderRule(AdviceRule):
    """
    Rule: Stick to your opening plan.
    
    Applicable: When user plays opening moves
    Followed: If plan_discipline score >= threshold
    Violated: If plan_discipline score < threshold
    """
    
    def evaluate(self, facts, history: List[Dict], params: Dict) -> AdviceResult:
        threshold = params.get("threshold", 0.6)
        severity = params.get("severity_weight", 3)
        
        if facts.total_moves < 10:
            return AdviceResult(
                outcome="NA",
                applicable=False,
                evidence={"reason": "Game too short to evaluate opening plan"},
                severity_weight=severity
            )
        
        plan_score = facts.opening_plan_score
        
        if plan_score >= threshold:
            return AdviceResult(
                outcome="FOLLOWED",
                applicable=True,
                evidence={
                    "plan_score": round(plan_score, 2),
                    "threshold": threshold,
                    "plan_signal": facts.plan_signal
                },
                severity_weight=severity
            )
        else:
            return AdviceResult(
                outcome="VIOLATED",
                applicable=True,
                evidence={
                    "plan_score": round(plan_score, 2),
                    "threshold": threshold,
                    "plan_signal": facts.plan_signal,
                    "plan_break_move": facts.plan_break_move
                },
                severity_weight=severity
            )


class ConversionRule(AdviceRule):
    """
    Rule: When ahead, don't throw the advantage.
    
    Applicable: When user had a winning position
    Followed: If no CONVERSION_ISSUE tag
    Violated: If CONVERSION_ISSUE tag present
    """
    
    def evaluate(self, facts, history: List[Dict], params: Dict) -> AdviceResult:
        severity = params.get("severity_weight", 4)
        
        # Check if conversion was relevant
        conversion_issue = facts.leak_tags_last_game.get("CONVERSION_ISSUE", 0)
        
        # Check if user ever had a winning position from evidence
        had_winning_position = any(
            e.get("type") == "conversion" or e.get("eval_before", 0) > 1.5
            for e in facts.evidence
        )
        
        # Also check error_moves for winning positions
        if not had_winning_position:
            for error in facts.error_moves:
                if error.get("eval_before", 0) > 1.5:
                    had_winning_position = True
                    break
        
        if not had_winning_position and conversion_issue == 0:
            return AdviceResult(
                outcome="NA",
                applicable=False,
                evidence={"reason": "No winning advantage to convert in this game"},
                severity_weight=severity
            )
        
        if conversion_issue >= 1:
            return AdviceResult(
                outcome="VIOLATED",
                applicable=True,
                evidence={"threw_winning_position": True, "conversion_issue_count": conversion_issue},
                severity_weight=severity
            )
        else:
            return AdviceResult(
                outcome="FOLLOWED",
                applicable=True,
                evidence={"maintained_advantage": True},
                severity_weight=severity
            )


# ==================== RULE REGISTRY ====================

ADVICE_RULES: Dict[str, AdviceRule] = {
    "OPENING_REPEAT_PIECE": OpeningRepeatPieceRule(),
    "TIME_PANIC": TimePanicRule(),
    "HANGING_PIECE": HangingPieceRule(),
    "EARLY_QUEEN": EarlyQueenRule(),
    "OPENING_WANDER": OpeningWanderRule(),
    "CONVERSION_ISSUE": ConversionRule(),
}


# ==================== ADVICE TEXT TEMPLATES ====================

ADVICE_TEMPLATES = {
    "OPENING_REPEAT_PIECE": "Avoid moving the same piece twice in the opening. Develop all minor pieces first.",
    "TIME_PANIC": "When under 30 seconds, pause and choose the safest move. Don't rush.",
    "HANGING_PIECE": "Before every move, check: is anything hanging? Scan the whole board.",
    "EARLY_QUEEN": "Develop knights and bishops before bringing out the queen.",
    "OPENING_WANDER": "Stick to your opening plan. Don't deviate unless forced.",
    "CONVERSION_ISSUE": "When ahead, simplify and trade pieces. Don't overpress.",
}


# ==================== LEAK TAG TO RULE MAPPING ====================

LEAK_TO_RULE = {
    "OPENING_WANDER": "OPENING_WANDER",
    "TACTICAL_BLINDNESS": "HANGING_PIECE",
    "TIME_PANIC": "TIME_PANIC",
    "CONVERSION_ISSUE": "CONVERSION_ISSUE",
}


# ==================== ENGINE CLASS ====================

class AdviceEngine:
    """
    Central engine for evaluating advice compliance.
    """
    
    @staticmethod
    def evaluate_advice(
        advice: Dict,
        facts,
        history: List[Dict]
    ) -> AdviceResult:
        """
        Evaluate a single advice against game facts.
        
        Args:
            advice: Advice document from DB
            facts: BehaviorFeatures
            history: Recent game analyses
            
        Returns:
            AdviceResult
        """
        rule_code = advice.get("rule_code")
        rule_params = advice.get("rule_params", {})
        severity = advice.get("severity", 3)
        
        # Add severity to params
        rule_params["severity_weight"] = severity
        
        rule = ADVICE_RULES.get(rule_code)
        if not rule:
            return AdviceResult(
                outcome="NA",
                applicable=False,
                evidence={"error": f"Unknown rule_code: {rule_code}"},
                severity_weight=severity
            )
        
        return rule.evaluate(facts, history, rule_params)
    
    @staticmethod
    def evaluate_all(
        advice_list: List[Dict],
        facts,
        history: List[Dict]
    ) -> List[Dict]:
        """
        Evaluate all active advice for a user.
        
        Returns list of evaluation results with advice metadata.
        """
        results = []
        
        for advice in advice_list:
            result = AdviceEngine.evaluate_advice(advice, facts, history)
            results.append({
                "advice_id": advice.get("advice_id"),
                "rule_code": advice.get("rule_code"),
                "text": advice.get("text"),
                **result.to_dict()
            })
        
        return results
    
    @staticmethod
    def should_create_advice(
        rule_code: str,
        leak_trends: Dict,
        active_advice: List[Dict]
    ) -> bool:
        """
        Check if auto-advice should be created for a leak pattern.
        
        Rules:
        - Leak appeared >= 3 times in last 5 games
        - No active advice exists for this rule_code
        - Max 3 active advice
        """
        # Check max active advice
        if len(active_advice) >= 3:
            return False
        
        # Check if advice already exists
        existing_codes = {a.get("rule_code") for a in active_advice}
        if rule_code in existing_codes:
            return False
        
        # Check leak frequency
        trend = leak_trends.get(rule_code, {})
        games_with_tag = trend.get("games_with_tag", 0)
        
        return games_with_tag >= 3
    
    @staticmethod
    def create_advice_for_leak(
        user_id: str,
        rule_code: str
    ) -> Dict:
        """
        Create a new advice document for a detected leak pattern.
        """
        return {
            "advice_id": str(uuid.uuid4()),
            "user_id": user_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "text": ADVICE_TEMPLATES.get(rule_code, f"Work on {rule_code}"),
            "category": _get_category_for_rule(rule_code),
            "rule_code": rule_code,
            "rule_params": {},
            "severity": _get_severity_for_rule(rule_code),
            "status": "ACTIVE"
        }


def _get_category_for_rule(rule_code: str) -> str:
    """Map rule code to category"""
    categories = {
        "OPENING_REPEAT_PIECE": "opening",
        "TIME_PANIC": "time_management",
        "HANGING_PIECE": "tactics",
        "EARLY_QUEEN": "opening",
        "OPENING_WANDER": "opening",
        "CONVERSION_ISSUE": "conversion",
    }
    return categories.get(rule_code, "general")


def _get_severity_for_rule(rule_code: str) -> int:
    """Get default severity for rule (1-5)"""
    severities = {
        "OPENING_REPEAT_PIECE": 3,
        "TIME_PANIC": 4,
        "HANGING_PIECE": 4,
        "EARLY_QUEEN": 2,
        "OPENING_WANDER": 3,
        "CONVERSION_ISSUE": 4,
    }
    return severities.get(rule_code, 3)
