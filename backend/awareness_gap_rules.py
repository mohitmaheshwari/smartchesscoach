"""
Awareness Gap Rules - Deterministic Gap Detection
=================================================
Version: v1
Rules for detecting the gap between user's perception and reality.
No LLM - purely rule-based.
"""

from typing import Dict, List, Optional
from reflect_constants import (
    AwarenessGapType, Intent, Confidence, QuickTagId,
    RatingBand, get_rating_band, ADAPTIVE_DEFAULTS, RewardTone
)
from reflect_predicates import BoardFacts
import logging

logger = logging.getLogger(__name__)


# ============================================
# GAP DETECTION RULES
# ============================================
# Each rule has:
# - conditions: what must be true
# - gap_type: resulting gap type
# - reason_codes: for analytics
# - headline_template: by rating band

GAP_RULES = [
    # RULE 1: Confidence Gap - Very sure but missed forcing
    {
        "rule_id": "confidence_gap_forcing",
        "priority": 10,
        "conditions": {
            "confidence": [Confidence.VERY_SURE],
            "facts": ["opponent_has_forcing_move", "user_ignored_forcing"],
            "categories": ["ignored_opponent_forcing", "missed_forcing_move"],
        },
        "gap_type": AwarenessGapType.CONFIDENCE_GAP,
        "reason_codes": ["forcing_reply_exists", "high_confidence", "missed_threat"],
        "headlines": {
            "default": "You were very sure, but there was a forcing reply you missed.",
            "advanced": "High confidence before full threat scan — common pattern.",
        },
        "focus_recommendation": "Opponent Threat Awareness",
    },
    
    # RULE 2: Confidence Gap - Sure but piece left hanging
    {
        "rule_id": "confidence_gap_hanging",
        "priority": 9,
        "conditions": {
            "confidence": [Confidence.VERY_SURE, Confidence.SOMEWHAT_SURE],
            "facts": ["user_piece_left_hanging"],
            "categories": ["missed_forcing_move"],
        },
        "gap_type": AwarenessGapType.CONFIDENCE_GAP,
        "reason_codes": ["piece_left_hanging", "confidence_mismatch"],
        "headlines": {
            "default": "You felt sure, but your piece was left unprotected.",
            "advanced": "Confidence didn't match the piece safety calculation.",
        },
        "focus_recommendation": "Piece Safety",
    },
    
    # RULE 3: Panic Pattern - Time pressure + guessing + miss
    {
        "rule_id": "panic_pattern",
        "priority": 8,
        "conditions": {
            "confidence": [Confidence.GUESSING],
            "facts": ["time_pressure_detected"],
            "categories": None,  # Any category
        },
        "gap_type": AwarenessGapType.PANIC_PATTERN,
        "reason_codes": ["time_pressure", "guessing", "rushed_decision"],
        "headlines": {
            "default": "This looks like a time-pressure decision, not a calculation miss.",
            "advanced": "Time pressure forced a guess — separate issue from calculation.",
        },
        "focus_recommendation": "Time Pressure Stabilization",
    },
    
    # RULE 4: Phantom Threat - Aligned when user recognizes non-threat
    {
        "rule_id": "phantom_aligned",
        "priority": 7,
        "conditions": {
            "tags_selected": [QuickTagId.DEFENDED_NON_THREAT.value, QuickTagId.FELT_DANGER.value],
            "facts": ["user_defended_phantom_threat"],
            "categories": ["phantom_threat"],
        },
        "gap_type": AwarenessGapType.ALIGNED,
        "reason_codes": ["recognized_phantom", "good_self_awareness"],
        "headlines": {
            "default": "Good awareness. You correctly noticed you defended a non-threat.",
            "advanced": "Accurate self-diagnosis — you overreacted to perceived danger.",
        },
        "focus_recommendation": "Threat Prioritization",
    },
    
    # RULE 5: Missed Forcing - Attack intent but ignored threat
    {
        "rule_id": "attack_ignored_threat",
        "priority": 8,
        "conditions": {
            "intent": [Intent.ATTACK, Intent.WIN_MATERIAL],
            "facts": ["user_attacked_instead_of_defending", "opponent_has_forcing_move"],
            "categories": ["ignored_opponent_forcing"],
        },
        "gap_type": AwarenessGapType.IGNORED_FORCING,
        "reason_codes": ["attack_before_scan", "ignored_counterplay"],
        "headlines": {
            "default": "You were attacking, but opponent had a stronger reply.",
            "advanced": "Attack mode before completing threat scan.",
        },
        "focus_recommendation": "Threat Check Before Attack",
    },
    
    # RULE 6: Defensive Intent but missed active option
    {
        "rule_id": "defense_missed_active",
        "priority": 6,
        "conditions": {
            "intent": [Intent.DEFEND, Intent.AVOID_THREAT],
            "facts": ["simple_tactic_missed", "best_move_wins_material"],
            "categories": ["missed_forcing_move", "critical_moment_drift"],
        },
        "gap_type": AwarenessGapType.MISSED_FORCING,
        "reason_codes": ["defense_mode", "missed_active_option"],
        "headlines": {
            "default": "You were defending, but had a stronger active move available.",
            "advanced": "Defense mode blocked seeing the forcing continuation.",
        },
        "focus_recommendation": "Active Before Passive",
    },
    
    # RULE 7: Aligned - Honest "not sure" with complex position
    {
        "rule_id": "honest_not_sure",
        "priority": 5,
        "conditions": {
            "confidence": [Confidence.GUESSING],
            "tags_selected": [QuickTagId.NOT_SURE.value],
            "categories": None,
        },
        "gap_type": AwarenessGapType.ALIGNED,
        "reason_codes": ["honest_uncertainty", "good_self_awareness"],
        "headlines": {
            "default": "Honest answer. Recognizing uncertainty is valuable data.",
            "advanced": "Good self-awareness — we'll build clearer pattern recognition.",
        },
        "focus_recommendation": None,  # No specific focus
    },
    
    # RULE 8: General forcing miss
    {
        "rule_id": "general_forcing_miss",
        "priority": 4,
        "conditions": {
            "facts": ["simple_tactic_missed"],
            "categories": ["missed_forcing_move"],
        },
        "gap_type": AwarenessGapType.MISSED_FORCING,
        "reason_codes": ["missed_tactic"],
        "headlines": {
            "default": "You missed a forcing move (check or winning capture).",
            "advanced": "Forcing move scan incomplete.",
        },
        "focus_recommendation": "Forcing Move Awareness",
    },
]


class AwarenessGapEngine:
    """
    Engine for detecting awareness gaps.
    Deterministic, rule-based, rating-adaptive.
    """
    
    def __init__(self, rating: int):
        self.rating = rating
        self.rating_band = get_rating_band(rating)
        self.adaptive_config = ADAPTIVE_DEFAULTS.get(
            self.rating_band,
            ADAPTIVE_DEFAULTS[RatingBand.BAND_C]
        )
    
    def evaluate(
        self,
        facts: BoardFacts,
        intent: str,
        confidence: str,
        selected_tags: List[str],
        mistake_category: str,
    ) -> Dict:
        """
        Evaluate the gap between user perception and reality.
        
        Returns:
            {
                "gap_type": "confidence_gap",
                "reason_codes": [...],
                "headline": "...",
                "focus_recommendation": "...",
                "rule_id": "...",
            }
        """
        board_facts = facts.to_dict()
        
        # Evaluate rules in priority order
        for rule in sorted(GAP_RULES, key=lambda r: r["priority"], reverse=True):
            if self._rule_matches(rule, board_facts, intent, confidence, selected_tags, mistake_category):
                return self._build_result(rule)
        
        # Default: partial alignment
        return {
            "gap_type": AwarenessGapType.PARTIAL_ALIGNMENT.value,
            "reason_codes": ["no_strong_match"],
            "headline": "Good start. We captured useful data for your training.",
            "focus_recommendation": self._category_to_focus(mistake_category),
            "rule_id": "default_partial",
        }
    
    def _rule_matches(
        self,
        rule: Dict,
        board_facts: Dict,
        intent: str,
        confidence: str,
        selected_tags: List[str],
        mistake_category: str,
    ) -> bool:
        """Check if a rule matches the current situation."""
        conditions = rule["conditions"]
        
        # Check intent condition
        if "intent" in conditions:
            valid_intents = [i.value if hasattr(i, 'value') else i for i in conditions["intent"]]
            if intent not in valid_intents:
                return False
        
        # Check confidence condition
        if "confidence" in conditions:
            valid_confs = [c.value if hasattr(c, 'value') else c for c in conditions["confidence"]]
            if confidence not in valid_confs:
                return False
        
        # Check facts conditions (all must be true)
        if "facts" in conditions:
            for fact_name in conditions["facts"]:
                if not board_facts.get(fact_name, False):
                    return False
        
        # Check category conditions
        if "categories" in conditions and conditions["categories"] is not None:
            if mistake_category not in conditions["categories"]:
                return False
        
        # Check selected tags (any match)
        if "tags_selected" in conditions:
            required_tags = conditions["tags_selected"]
            if not any(tag in selected_tags for tag in required_tags):
                return False
        
        return True
    
    def _build_result(self, rule: Dict) -> Dict:
        """Build result from matched rule."""
        # Get headline based on rating band
        if self.adaptive_config.get("show_advanced_labels", False):
            headline = rule["headlines"].get("advanced", rule["headlines"]["default"])
        else:
            headline = rule["headlines"]["default"]
        
        return {
            "gap_type": rule["gap_type"].value,
            "reason_codes": rule["reason_codes"],
            "headline": headline,
            "focus_recommendation": rule.get("focus_recommendation"),
            "rule_id": rule["rule_id"],
        }
    
    def _category_to_focus(self, category: str) -> str:
        """Map mistake category to focus area."""
        mapping = {
            "ignored_opponent_forcing": "Opponent Threat Awareness",
            "missed_forcing_move": "Forcing Move Awareness",
            "phantom_threat": "Threat Prioritization",
            "advantage_mismanagement": "Advantage Conversion",
            "critical_moment_drift": "Critical Position Focus",
            "structural_misjudgment": "Positional Understanding",
        }
        return mapping.get(category, "General Improvement")


def evaluate_awareness_gap(
    fen_before: str,
    user_move: str,
    best_move: str,
    intent: str,
    confidence: str,
    selected_tags: List[str],
    mistake_category: str,
    rating: int,
    cp_loss: float = 0,
    time_remaining_sec: Optional[int] = None,
    move_number: int = 0,
) -> Dict:
    """
    Main entry point for awareness gap evaluation.
    Called after user completes reflection.
    """
    # Build board facts
    facts = BoardFacts(
        fen_before=fen_before,
        user_move=user_move,
        best_move=best_move,
        cp_loss=cp_loss,
        time_remaining_sec=time_remaining_sec,
        move_number=move_number,
    )
    
    # Evaluate gap
    engine = AwarenessGapEngine(rating=rating)
    return engine.evaluate(
        facts=facts,
        intent=intent,
        confidence=confidence,
        selected_tags=selected_tags,
        mistake_category=mistake_category,
    )
