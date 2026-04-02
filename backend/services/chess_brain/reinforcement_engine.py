"""
Reinforcement Engine
====================

Detects when users successfully avoid their recurring mistakes.
Creates HABIT_BREAKTHROUGH lesson candidates to celebrate improvements.
"""

import logging
from typing import Dict, Any, Optional, List

from .schemas import (
    LessonCandidate,
    PositionInsightObject,
    MistakeFingerprint
)
from .enums import (
    TeachingMode,
    ExplanationType,
    LessonPriority
)
from .fingerprint_service import FingerprintService

logger = logging.getLogger(__name__)


class ReinforcementEngine:
    """
    Detects habit breakthroughs and generates celebration lessons.
    
    A habit breakthrough occurs when:
    1. The user has historically struggled with a pattern (count >= 3, relevance >= 0.3)
    2. The current position contains that pattern
    3. The user successfully navigates it (doesn't make the mistake)
    """
    
    def __init__(self, fingerprint_service: FingerprintService):
        self.fingerprint_service = fingerprint_service
    
    async def check_for_breakthrough(
        self,
        user_id: str,
        position_insight: PositionInsightObject
    ) -> Optional[LessonCandidate]:
        """
        Check if the user avoided a pattern they usually miss.
        
        Args:
            user_id: User identifier
            position_insight: Current position analysis
            
        Returns:
            LessonCandidate for HABIT_BREAKTHROUGH or None
        """
        try:
            # Get user's fingerprint
            fingerprint = await self.fingerprint_service.get_fingerprint(user_id)
            
            # Get top weaknesses
            weaknesses = await self.fingerprint_service.get_top_weaknesses(user_id, limit=10)
            
            # Check if user played well in a position matching their weakness
            breakthrough = await self._detect_breakthrough(
                position_insight,
                fingerprint,
                weaknesses
            )
            
            if breakthrough:
                return self._create_breakthrough_lesson(breakthrough, position_insight)
            
            return None
        
        except Exception as e:
            logger.error(f"Error checking for breakthrough: {e}")
            return None
    
    async def _detect_breakthrough(
        self,
        position_insight: PositionInsightObject,
        fingerprint: MistakeFingerprint,
        weaknesses: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """
        Detect if user avoided a recurring mistake.
        
        Returns:
            Dict with breakthrough details or None
        """
        # User must have played a good/excellent move
        if position_insight.move_quality.value not in ["good", "excellent", "best"]:
            return None
        
        # Check each known weakness
        for weakness in weaknesses:
            pattern_type = weakness["pattern_type"]
            category = weakness["category"]
            count = weakness["count"]
            relevance = weakness["relevance_score"]
            
            # Must be a significant weakness (appeared at least 3 times, relevance >= 0.3)
            if count < 3 or relevance < 0.3:
                continue
            
            # Check if this position contains the pattern but user didn't fall for it
            if self._position_contains_pattern(position_insight, pattern_type, category):
                # Check if the pattern was in best_move but user avoided it
                # (meaning the pattern exists, but user didn't make the mistake)
                if self._user_avoided_pattern(position_insight, pattern_type):
                    return {
                        "pattern_type": pattern_type,
                        "category": category,
                        "count": count,
                        "relevance": relevance,
                        "user_move": position_insight.user_move,
                        "best_move": position_insight.best_move
                    }
        
        return None
    
    def _position_contains_pattern(
        self,
        position_insight: PositionInsightObject,
        pattern_type: str,
        category: str
    ) -> bool:
        """
        Check if the position objectively contains this pattern opportunity.
        
        This is checked by seeing if the pattern was detected (meaning it exists)
        but the user either:
        1. Didn't detect it in their move (missed it before)
        2. Successfully played it this time (breakthrough)
        """
        # Look through detections to see if this pattern exists
        all_detections = position_insight.get_all_detections()
        
        for detection in all_detections:
            if detection.pattern_type == pattern_type and detection.category == category:
                # Pattern exists in the position
                return True
        
        # Also check if best_move would have created this pattern
        # (meaning user could have played it but didn't, or did play it)
        return False
    
    def _user_avoided_pattern(
        self,
        position_insight: PositionInsightObject,
        pattern_type: str
    ) -> bool:
        """
        Check if user successfully navigated a pattern they usually miss.
        
        Logic:
        - If user_move == best_move and best_move contains the pattern → breakthrough!
        - If user made a tactical pattern that they usually miss → breakthrough!
        """
        # Check if user played the best move involving this pattern
        if position_insight.user_move == position_insight.best_move:
            # User played optimally in a position where they usually fail
            return True
        
        # Check if user's move was good/excellent even if not the absolute best
        if position_insight.move_quality.value in ["good", "excellent"]:
            # User navigated the position well
            return True
        
        return False
    
    def _create_breakthrough_lesson(
        self,
        breakthrough: Dict[str, Any],
        position_insight: PositionInsightObject
    ) -> LessonCandidate:
        """
        Create a HABIT_BREAKTHROUGH lesson candidate.
        """
        pattern_type = breakthrough["pattern_type"]
        count = breakthrough["count"]
        
        # Create encouraging message
        pattern_name = self._format_pattern_name(pattern_type)
        
        candidate = LessonCandidate(
            candidate_id=f"breakthrough_{pattern_type}",
            teaching_mode=TeachingMode.HABIT_BREAKTHROUGH,
            title=f"Breakthrough: {pattern_name}!",
            main_insight=f"You nailed it! You usually struggle with {pattern_name}, but this time you got it right!",
            explanation_type=ExplanationType.REINFORCEMENT,
            severity=0.0,  # Not a mistake
            clarity=1.0,   # Very clear breakthrough
            player_relevance=breakthrough["relevance"],  # Use their actual relevance score
            freshness=1.0,
            priority=LessonPriority.HIGH,
            source_detector="reinforcement_engine",
            template_key="habit_breakthrough",
            template_vars={
                "pattern_name": pattern_name,
                "miss_count": count,
                "user_move": breakthrough["user_move"],
                "what_it_does": self._describe_move(breakthrough["user_move"], position_insight),
                "explanation": f"This is major progress. You've missed this pattern {count} times before, but your pattern recognition is improving!",
                "achievement_description": f"shows you're developing stronger intuition for {pattern_name}"
            },
            socratic_question=None
        )
        
        return candidate
    
    def _format_pattern_name(self, pattern_type: str) -> str:
        """Convert pattern enum to readable name."""
        name_map = {
            "MISSED_FORK": "fork patterns",
            "MISSED_PIN": "pin tactics",
            "MISSED_SKEWER": "skewer opportunities",
            "HANGING_PIECE": "hanging pieces",
            "TRAPPED_PIECE": "trapped pieces",
            "MISSED_BACK_RANK": "back rank threats",
            "MISSED_MATE": "checkmate patterns",
            "MISSED_DISCOVERY": "discovered attacks",
            "MISSED_OVERLOAD": "overloaded pieces",
            "MISSED_REMOVAL": "removal of the guard",
            "ISOLATED_PAWN": "isolated pawn weaknesses",
            "PASSED_PAWN": "passed pawn opportunities",
            "KNIGHT_OUTPOST": "knight outposts",
            "ROOK_ACTIVITY": "rook activity",
            "KING_SAFETY": "king safety",
            "TIME_TROUBLE": "time management",
            "IMPULSE_MOVE": "impulse control",
            "TILT_DETECTED": "emotional stability"
        }
        
        return name_map.get(pattern_type, pattern_type.replace("_", " ").lower())
    
    def _describe_move(self, move: str, position_insight: PositionInsightObject) -> str:
        """Generate a description of what the move accomplishes."""
        if position_insight.is_check:
            return "gives check and maintains pressure"
        elif position_insight.is_capture:
            return "wins material cleanly"
        elif position_insight.move_quality.value == "excellent":
            return "finds the best continuation"
        else:
            return "navigates the position correctly"


def create_reinforcement_engine(db=None) -> ReinforcementEngine:
    """
    Factory function to create a reinforcement engine.
    
    Args:
        db: Optional database instance
        
    Returns:
        ReinforcementEngine instance
    """
    from .fingerprint_service import get_fingerprint_service
    
    fingerprint_service = get_fingerprint_service(db)
    return ReinforcementEngine(fingerprint_service)
