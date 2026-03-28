"""
Chess Understanding Service - Multi-Dimensional Player Analysis
================================================================

This replaces the simplistic "rating = level" approach with a nuanced
understanding of what the player ACTUALLY knows about chess.

A 1200 player could be:
- A beginner who got lucky
- A 1600 player on a bad streak who still UNDERSTANDS chess
- Someone who knows theory but blunders under time pressure
- Someone who wins on tricks but has zero positional understanding

DIMENSIONS OF CHESS UNDERSTANDING:
1. Tactical Vision - Can they spot tactics? At what depth?
2. Positional Sense - Do they understand weak squares, pawn structure?
3. Opening Knowledge - Do they know theory? Follow principles?
4. Endgame Technique - Can they convert? Know basic patterns?
5. Calculation Ability - How deep can they calculate accurately?
6. Pattern Recognition - Do they recognize standard motifs?
7. Time Management - Do they use time well or blunder in time trouble?
8. Consistency - Variance between their best and worst moves

COACHING ADAPTATION:
Instead of "you're a beginner, here's simple advice", we say:
- "Your tactics are sharp, but your endgames need work"
- "You know opening theory, but you're missing simple tactics"
- "You understand positional chess, but you calculate too fast"

Author: Built for truly personalized coaching
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timezone
from enum import Enum
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# UNDERSTANDING LEVELS (Per Dimension)
# =============================================================================

class UnderstandingLevel(str, Enum):
    """Level of understanding in a specific dimension"""
    UNAWARE = "unaware"           # Doesn't know this exists
    AWARE = "aware"               # Knows it exists but can't apply
    LEARNING = "learning"         # Sometimes applies correctly
    COMPETENT = "competent"       # Usually applies correctly
    PROFICIENT = "proficient"     # Applies well, understands nuances
    EXPERT = "expert"             # Deep understanding, can teach others
    MASTER = "master"             # Exceptional, creative applications


# Numeric values for calculations
LEVEL_SCORES = {
    UnderstandingLevel.UNAWARE: 0,
    UnderstandingLevel.AWARE: 1,
    UnderstandingLevel.LEARNING: 2,
    UnderstandingLevel.COMPETENT: 3,
    UnderstandingLevel.PROFICIENT: 4,
    UnderstandingLevel.EXPERT: 5,
    UnderstandingLevel.MASTER: 6,
}


# =============================================================================
# CHESS UNDERSTANDING MODEL
# =============================================================================

@dataclass
class DimensionAssessment:
    """Assessment of a single dimension of chess understanding"""
    level: UnderstandingLevel
    score: float  # 0-100 for granularity
    confidence: float  # 0-1, how confident we are in this assessment
    evidence_count: int  # How many data points support this
    trend: str  # "improving", "stable", "declining"
    specific_strengths: List[str] = field(default_factory=list)
    specific_weaknesses: List[str] = field(default_factory=list)
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> Dict:
        return {
            "level": self.level.value,
            "score": self.score,
            "confidence": self.confidence,
            "evidence_count": self.evidence_count,
            "trend": self.trend,
            "specific_strengths": self.specific_strengths,
            "specific_weaknesses": self.specific_weaknesses,
            "last_updated": self.last_updated.isoformat()
        }
    
    @classmethod
    def from_dict(cls, d: Dict) -> 'DimensionAssessment':
        return cls(
            level=UnderstandingLevel(d.get("level", "learning")),
            score=d.get("score", 50),
            confidence=d.get("confidence", 0.5),
            evidence_count=d.get("evidence_count", 0),
            trend=d.get("trend", "stable"),
            specific_strengths=d.get("specific_strengths", []),
            specific_weaknesses=d.get("specific_weaknesses", []),
            last_updated=datetime.fromisoformat(d["last_updated"]) if isinstance(d.get("last_updated"), str) else datetime.now(timezone.utc)
        )


@dataclass
class ChessUnderstanding:
    """Complete multi-dimensional chess understanding profile"""
    user_id: str
    
    # Core dimensions
    tactical_vision: DimensionAssessment = None
    positional_sense: DimensionAssessment = None
    opening_knowledge: DimensionAssessment = None
    endgame_technique: DimensionAssessment = None
    calculation_ability: DimensionAssessment = None
    pattern_recognition: DimensionAssessment = None
    time_management: DimensionAssessment = None
    consistency: DimensionAssessment = None
    
    # Derived metrics
    overall_understanding: str = "developing"  # Not a simple average, but a holistic assessment
    primary_strength: str = ""
    primary_weakness: str = ""
    coaching_focus: str = ""  # What the coach should emphasize
    
    # Context
    games_analyzed: int = 0
    opponent_avg_rating: int = 0
    performance_vs_expectation: str = "as_expected"  # "above", "below", "as_expected"
    
    # Metadata
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def __post_init__(self):
        """Initialize default assessments if not provided"""
        default = DimensionAssessment(
            level=UnderstandingLevel.LEARNING,
            score=50,
            confidence=0.1,
            evidence_count=0,
            trend="stable"
        )
        if self.tactical_vision is None:
            self.tactical_vision = default
        if self.positional_sense is None:
            self.positional_sense = default
        if self.opening_knowledge is None:
            self.opening_knowledge = default
        if self.endgame_technique is None:
            self.endgame_technique = default
        if self.calculation_ability is None:
            self.calculation_ability = default
        if self.pattern_recognition is None:
            self.pattern_recognition = default
        if self.time_management is None:
            self.time_management = default
        if self.consistency is None:
            self.consistency = default
    
    def to_dict(self) -> Dict:
        return {
            "user_id": self.user_id,
            "tactical_vision": self.tactical_vision.to_dict() if self.tactical_vision else None,
            "positional_sense": self.positional_sense.to_dict() if self.positional_sense else None,
            "opening_knowledge": self.opening_knowledge.to_dict() if self.opening_knowledge else None,
            "endgame_technique": self.endgame_technique.to_dict() if self.endgame_technique else None,
            "calculation_ability": self.calculation_ability.to_dict() if self.calculation_ability else None,
            "pattern_recognition": self.pattern_recognition.to_dict() if self.pattern_recognition else None,
            "time_management": self.time_management.to_dict() if self.time_management else None,
            "consistency": self.consistency.to_dict() if self.consistency else None,
            "overall_understanding": self.overall_understanding,
            "primary_strength": self.primary_strength,
            "primary_weakness": self.primary_weakness,
            "coaching_focus": self.coaching_focus,
            "games_analyzed": self.games_analyzed,
            "opponent_avg_rating": self.opponent_avg_rating,
            "performance_vs_expectation": self.performance_vs_expectation,
            "created_at": self.created_at.isoformat(),
            "last_updated": self.last_updated.isoformat()
        }
    
    @classmethod
    def from_dict(cls, d: Dict) -> 'ChessUnderstanding':
        return cls(
            user_id=d["user_id"],
            tactical_vision=DimensionAssessment.from_dict(d["tactical_vision"]) if d.get("tactical_vision") else None,
            positional_sense=DimensionAssessment.from_dict(d["positional_sense"]) if d.get("positional_sense") else None,
            opening_knowledge=DimensionAssessment.from_dict(d["opening_knowledge"]) if d.get("opening_knowledge") else None,
            endgame_technique=DimensionAssessment.from_dict(d["endgame_technique"]) if d.get("endgame_technique") else None,
            calculation_ability=DimensionAssessment.from_dict(d["calculation_ability"]) if d.get("calculation_ability") else None,
            pattern_recognition=DimensionAssessment.from_dict(d["pattern_recognition"]) if d.get("pattern_recognition") else None,
            time_management=DimensionAssessment.from_dict(d["time_management"]) if d.get("time_management") else None,
            consistency=DimensionAssessment.from_dict(d["consistency"]) if d.get("consistency") else None,
            overall_understanding=d.get("overall_understanding", "developing"),
            primary_strength=d.get("primary_strength", ""),
            primary_weakness=d.get("primary_weakness", ""),
            coaching_focus=d.get("coaching_focus", ""),
            games_analyzed=d.get("games_analyzed", 0),
            opponent_avg_rating=d.get("opponent_avg_rating", 0),
            performance_vs_expectation=d.get("performance_vs_expectation", "as_expected"),
            created_at=datetime.fromisoformat(d["created_at"]) if isinstance(d.get("created_at"), str) else datetime.now(timezone.utc),
            last_updated=datetime.fromisoformat(d["last_updated"]) if isinstance(d.get("last_updated"), str) else datetime.now(timezone.utc)
        )


# =============================================================================
# UNDERSTANDING CALCULATOR
# =============================================================================

class UnderstandingCalculator:
    """
    Calculates chess understanding from player profile data.
    
    This is where the magic happens - turning raw game data into
    meaningful understanding assessments.
    """
    
    @staticmethod
    def calculate_tactical_vision(profile: Dict) -> DimensionAssessment:
        """
        Assess tactical vision from blunder patterns and tactical successes.
        
        Indicators:
        - Missed forks, pins, skewers (negative)
        - Complex tactical misses vs simple ones
        - Successful tactical combinations found
        - Accuracy on tactical positions
        """
        weaknesses = profile.get("top_weaknesses", [])
        total_blunders = profile.get("total_blunders", 0)
        total_best_moves = profile.get("total_best_moves", 0)
        games = profile.get("games_analyzed_count", 0) or profile.get("games_analyzed", 0)
        
        # Count tactical weaknesses
        tactical_misses = 0
        one_move_blunders = 0
        complex_misses = 0
        
        for w in weaknesses:
            subcat = w.get("subcategory", "")
            count = w.get("occurrence_count", 0)
            if "one_move" in subcat or "simple" in subcat:
                one_move_blunders += count
            if "tactical" in subcat or "complex" in subcat:
                tactical_misses += count
                if "complex" in subcat:
                    complex_misses += count
        
        # Calculate score (0-100)
        if games == 0:
            return DimensionAssessment(
                level=UnderstandingLevel.LEARNING,
                score=50,
                confidence=0.1,
                evidence_count=0,
                trend="stable",
                specific_weaknesses=["Not enough games analyzed"]
            )
        
        # Blunders per game (lower is better)
        blunders_per_game = total_blunders / games if games > 0 else 0
        best_moves_per_game = total_best_moves / games if games > 0 else 0
        
        # One-move blunders are especially bad for tactical vision
        one_move_ratio = one_move_blunders / games if games > 0 else 0
        
        # Score calculation
        # Start at 70 (competent baseline)
        score = 70
        
        # Penalize for blunders per game
        score -= min(30, blunders_per_game * 20)  # Up to -30 for >1.5 blunders/game
        
        # Penalize heavily for one-move blunders (shows lack of basic vision)
        score -= min(25, one_move_ratio * 30)  # Up to -25 for frequent simple misses
        
        # Reward for best moves
        score += min(20, best_moves_per_game * 2)  # Up to +20 for finding good moves
        
        # Clamp score
        score = max(10, min(95, score))
        
        # Determine level from score
        if score >= 85:
            level = UnderstandingLevel.EXPERT
        elif score >= 70:
            level = UnderstandingLevel.PROFICIENT
        elif score >= 55:
            level = UnderstandingLevel.COMPETENT
        elif score >= 40:
            level = UnderstandingLevel.LEARNING
        elif score >= 25:
            level = UnderstandingLevel.AWARE
        else:
            level = UnderstandingLevel.UNAWARE
        
        # Identify specific issues
        specific_weaknesses = []
        if one_move_blunders > games * 0.5:
            specific_weaknesses.append("Frequently misses simple one-move tactics")
        if complex_misses > games * 0.3:
            specific_weaknesses.append("Struggles with complex tactical sequences")
        
        specific_strengths = []
        if best_moves_per_game > 10:
            specific_strengths.append("Finds strong moves consistently")
        
        return DimensionAssessment(
            level=level,
            score=score,
            confidence=min(0.9, games / 50),  # More games = more confidence
            evidence_count=games,
            trend="stable",  # Would need historical data to determine
            specific_strengths=specific_strengths,
            specific_weaknesses=specific_weaknesses
        )
    
    @staticmethod
    def calculate_positional_sense(profile: Dict) -> DimensionAssessment:
        """
        Assess positional understanding.
        
        Indicators:
        - Pawn structure handling
        - Piece activity in quiet positions
        - Strategic blunders vs tactical ones
        - Control of key squares
        """
        weaknesses = profile.get("top_weaknesses", [])
        strengths = profile.get("strengths", [])
        games = profile.get("games_analyzed_count", 0) or profile.get("games_analyzed", 0)
        
        # Look for positional indicators in strengths/weaknesses
        positional_strength_count = 0
        positional_weakness_count = 0
        
        for s in strengths:
            cat = s.get("category", "")
            subcat = s.get("subcategory", "")
            if "positional" in cat or "development" in subcat or "structure" in subcat:
                positional_strength_count += s.get("evidence_count", 1)
        
        for w in weaknesses:
            cat = w.get("category", "")
            subcat = w.get("subcategory", "")
            if "positional" in cat or "structure" in subcat or "pawn" in subcat:
                positional_weakness_count += w.get("occurrence_count", 1)
        
        if games == 0:
            return DimensionAssessment(
                level=UnderstandingLevel.LEARNING,
                score=50,
                confidence=0.1,
                evidence_count=0,
                trend="stable"
            )
        
        # Calculate score
        score = 60  # Baseline
        
        # Adjust based on evidence
        strength_ratio = positional_strength_count / games if games > 0 else 0
        weakness_ratio = positional_weakness_count / games if games > 0 else 0
        
        score += min(25, strength_ratio * 50)
        score -= min(30, weakness_ratio * 40)
        
        score = max(10, min(95, score))
        
        # Determine level
        if score >= 80:
            level = UnderstandingLevel.PROFICIENT
        elif score >= 60:
            level = UnderstandingLevel.COMPETENT
        elif score >= 40:
            level = UnderstandingLevel.LEARNING
        else:
            level = UnderstandingLevel.AWARE
        
        specific_strengths = []
        specific_weaknesses = []
        
        if positional_strength_count > 20:
            specific_strengths.append("Good piece development")
        if positional_weakness_count > games * 0.3:
            specific_weaknesses.append("Needs work on pawn structure awareness")
        
        return DimensionAssessment(
            level=level,
            score=score,
            confidence=min(0.8, games / 50),
            evidence_count=games,
            trend="stable",
            specific_strengths=specific_strengths,
            specific_weaknesses=specific_weaknesses
        )
    
    @staticmethod
    def calculate_opening_knowledge(profile: Dict) -> DimensionAssessment:
        """
        Assess opening knowledge.
        
        Indicators:
        - Opening trap frequency
        - Deviation from theory
        - Opening principle adherence
        - Repertoire depth
        """
        weaknesses = profile.get("top_weaknesses", [])
        strengths = profile.get("strengths", [])
        games = profile.get("games_analyzed_count", 0) or profile.get("games_analyzed", 0)
        
        opening_issues = 0
        opening_strengths = 0
        
        for w in weaknesses:
            subcat = w.get("subcategory", "")
            if "opening" in subcat or "trap" in subcat or "principle" in subcat:
                opening_issues += w.get("occurrence_count", 1)
        
        for s in strengths:
            subcat = s.get("subcategory", "")
            if "opening" in subcat or "development" in subcat or "principle" in subcat:
                opening_strengths += s.get("evidence_count", 1)
        
        if games == 0:
            return DimensionAssessment(
                level=UnderstandingLevel.LEARNING,
                score=50,
                confidence=0.1,
                evidence_count=0,
                trend="stable"
            )
        
        score = 65
        
        issue_ratio = opening_issues / games if games > 0 else 0
        strength_ratio = opening_strengths / games if games > 0 else 0
        
        score -= min(35, issue_ratio * 100)
        score += min(25, strength_ratio * 50)
        
        score = max(10, min(95, score))
        
        if score >= 75:
            level = UnderstandingLevel.PROFICIENT
        elif score >= 55:
            level = UnderstandingLevel.COMPETENT
        elif score >= 35:
            level = UnderstandingLevel.LEARNING
        else:
            level = UnderstandingLevel.AWARE
        
        return DimensionAssessment(
            level=level,
            score=score,
            confidence=min(0.8, games / 30),
            evidence_count=games,
            trend="stable",
            specific_strengths=["Follows opening principles"] if opening_strengths > 10 else [],
            specific_weaknesses=["Falls for opening traps"] if opening_issues > games * 0.1 else []
        )
    
    @staticmethod
    def calculate_consistency(profile: Dict) -> DimensionAssessment:
        """
        Assess consistency - variance between best moves and blunders.
        
        A player who plays brilliancies but also blunders a lot is inconsistent.
        This often indicates: knows chess but loses focus/patience.
        """
        total_blunders = profile.get("total_blunders", 0)
        total_mistakes = profile.get("total_mistakes", 0)
        total_best_moves = profile.get("total_best_moves", 0)
        games = profile.get("games_analyzed_count", 0) or profile.get("games_analyzed", 0)
        habits = profile.get("habits", [])
        
        if games == 0:
            return DimensionAssessment(
                level=UnderstandingLevel.LEARNING,
                score=50,
                confidence=0.1,
                evidence_count=0,
                trend="stable"
            )
        
        # Calculate variance ratio
        # High best_moves with high blunders = inconsistent
        # (Variables used for documentation/future expansion)
        
        # Inconsistency metric: how much blunders vs best moves
        total_moves = total_best_moves + total_mistakes + total_blunders
        if total_moves == 0:
            inconsistency = 0.5
        else:
            # If blunders are a high percentage relative to best moves, inconsistent
            inconsistency = total_blunders / (total_best_moves + 1)
        
        # Check for tunnel_vision or impulsive habits
        has_focus_issue = False
        for habit in habits:
            if habit.get("name") in ["tunnel_vision", "impulsive", "time_trouble"]:
                has_focus_issue = True
                break
        
        # Score calculation
        score = 70
        
        # Penalize for inconsistency
        score -= min(40, inconsistency * 100)
        
        # Penalize for focus habits
        if has_focus_issue:
            score -= 15
        
        score = max(10, min(95, score))
        
        if score >= 75:
            level = UnderstandingLevel.PROFICIENT
        elif score >= 55:
            level = UnderstandingLevel.COMPETENT
        elif score >= 35:
            level = UnderstandingLevel.LEARNING
        else:
            level = UnderstandingLevel.AWARE
        
        specific_weaknesses = []
        if has_focus_issue:
            specific_weaknesses.append("Focus/concentration issues leading to errors")
        if inconsistency > 0.3:
            specific_weaknesses.append("High variance between best and worst moves")
        
        return DimensionAssessment(
            level=level,
            score=score,
            confidence=min(0.9, games / 30),
            evidence_count=games,
            trend="stable",
            specific_strengths=["Plays consistently when focused"] if score > 60 else [],
            specific_weaknesses=specific_weaknesses
        )
    
    @staticmethod
    def calculate_from_profile(profile: Dict) -> ChessUnderstanding:
        """
        Calculate complete chess understanding from a player profile.
        """
        user_id = profile.get("user_id", "unknown")
        games = profile.get("games_analyzed_count", 0) or profile.get("games_analyzed", 0)
        
        # Calculate each dimension
        tactical = UnderstandingCalculator.calculate_tactical_vision(profile)
        positional = UnderstandingCalculator.calculate_positional_sense(profile)
        opening = UnderstandingCalculator.calculate_opening_knowledge(profile)
        consistency = UnderstandingCalculator.calculate_consistency(profile)
        
        # For dimensions we don't have specific data for, estimate from general performance
        avg_score = (tactical.score + positional.score + opening.score + consistency.score) / 4
        
        endgame = DimensionAssessment(
            level=UnderstandingLevel.LEARNING,
            score=avg_score * 0.9,  # Slightly lower as endgames are usually weaker
            confidence=0.3,
            evidence_count=games,
            trend="stable",
            specific_weaknesses=["Endgame technique needs more data"]
        )
        
        calculation = DimensionAssessment(
            level=tactical.level,  # Usually correlated with tactical vision
            score=tactical.score * 0.95,
            confidence=tactical.confidence * 0.8,
            evidence_count=games,
            trend="stable"
        )
        
        pattern_rec = DimensionAssessment(
            level=tactical.level,
            score=(tactical.score + positional.score) / 2,
            confidence=0.5,
            evidence_count=games,
            trend="stable"
        )
        
        time_mgmt = DimensionAssessment(
            level=consistency.level,
            score=consistency.score,
            confidence=0.4,
            evidence_count=games,
            trend="stable"
        )
        
        # Determine primary strength and weakness
        dimensions = {
            "Tactical Vision": tactical.score,
            "Positional Sense": positional.score,
            "Opening Knowledge": opening.score,
            "Consistency": consistency.score
        }
        
        primary_strength = max(dimensions, key=dimensions.get)
        primary_weakness = min(dimensions, key=dimensions.get)
        
        # Determine overall understanding
        avg = sum(dimensions.values()) / len(dimensions)
        if avg >= 75:
            overall = "proficient"
        elif avg >= 60:
            overall = "competent"
        elif avg >= 45:
            overall = "developing"
        elif avg >= 30:
            overall = "learning"
        else:
            overall = "beginning"
        
        # Determine coaching focus
        # Focus on the weakest area that has enough confidence
        coaching_focus = f"Focus on improving {primary_weakness.lower()}"
        
        return ChessUnderstanding(
            user_id=user_id,
            tactical_vision=tactical,
            positional_sense=positional,
            opening_knowledge=opening,
            endgame_technique=endgame,
            calculation_ability=calculation,
            pattern_recognition=pattern_rec,
            time_management=time_mgmt,
            consistency=consistency,
            overall_understanding=overall,
            primary_strength=primary_strength,
            primary_weakness=primary_weakness,
            coaching_focus=coaching_focus,
            games_analyzed=games,
            opponent_avg_rating=profile.get("opponent_avg_rating", 0),
            performance_vs_expectation="as_expected"
        )


# =============================================================================
# COACHING LANGUAGE ADAPTER (Based on Understanding)
# =============================================================================

class UnderstandingBasedCoaching:
    """
    Adapts coaching language based on multi-dimensional understanding,
    not just overall level.
    """
    
    @staticmethod
    def get_dimension_specific_language(understanding: ChessUnderstanding) -> Dict[str, str]:
        """
        Generate coaching language that's specific to the player's understanding profile.
        """
        tactical = understanding.tactical_vision
        consistency = understanding.consistency
        # positional_sense available for future use
        
        # Adapt based on tactical vision
        if tactical.score < 40:
            tactical_tone = "simple_patient"
            tactical_advice = "Let's check all captures and checks before moving."
        elif tactical.score < 60:
            tactical_tone = "building"
            tactical_advice = "Look for tactical patterns - forks, pins, discovered attacks."
        elif tactical.score < 80:
            tactical_tone = "refining"
            tactical_advice = "Calculate the full sequence before committing."
        else:
            tactical_tone = "peer"
            tactical_advice = "Verify your calculation."
        
        # Adapt based on consistency
        if consistency.score < 40:
            focus_reminder = "Take your time. One move at a time."
            patience_level = "high"
        elif consistency.score < 60:
            focus_reminder = "Stay focused."
            patience_level = "moderate"
        else:
            focus_reminder = ""
            patience_level = "low"
        
        # Build the personalized coaching context
        return {
            "tactical_tone": tactical_tone,
            "tactical_advice": tactical_advice,
            "focus_reminder": focus_reminder,
            "patience_level": patience_level,
            "primary_focus": understanding.coaching_focus,
            "acknowledge_strength": f"Your {understanding.primary_strength.lower()} is solid.",
            "work_on": f"Let's work on your {understanding.primary_weakness.lower()}."
        }
    
    @staticmethod
    def get_mistake_feedback(understanding: ChessUnderstanding, mistake_type: str) -> Dict[str, str]:
        """
        Generate mistake feedback that's relevant to the player's understanding.
        """
        tactical = understanding.tactical_vision
        consistency = understanding.consistency
        
        # If they're tactically strong but inconsistent, the feedback is different
        if tactical.score > 70 and consistency.score < 50:
            return {
                "header": "Focus slip",
                "message": "You know better. This was a concentration error, not a knowledge gap.",
                "try_again": "Reset. Look again.",
                "tone": "direct_knowing"
            }
        
        # If they're tactically weak
        if tactical.score < 40:
            return {
                "header": "Learning opportunity",
                "message": "This pattern is tricky. Let me show you what to look for.",
                "try_again": "Let's try again. Check all captures first.",
                "tone": "patient_teaching"
            }
        
        # Default
        return {
            "header": "Not quite",
            "message": "There was a better move. See what you missed.",
            "try_again": "Try again.",
            "tone": "balanced"
        }
    
    @staticmethod
    def get_correct_feedback(understanding: ChessUnderstanding) -> Dict[str, str]:
        """
        Generate praise that acknowledges the player's level.
        """
        tactical = understanding.tactical_vision
        
        if tactical.score > 80:
            return {
                "header": "As expected",
                "message": "Correct.",
                "tone": "peer"
            }
        elif tactical.score > 60:
            return {
                "header": "Well done",
                "message": "You found it. Good calculation.",
                "tone": "approving"
            }
        elif tactical.score > 40:
            return {
                "header": "Nice!",
                "message": "Good job! You're improving.",
                "tone": "encouraging"
            }
        else:
            return {
                "header": "Excellent!",
                "message": "That's exactly right! Great work finding that!",
                "tone": "celebratory"
            }
    
    @staticmethod
    def get_position_analysis_style(understanding: ChessUnderstanding) -> Dict[str, Any]:
        """
        Determine how detailed and what style of position analysis to provide.
        """
        overall_score = (
            understanding.tactical_vision.score +
            understanding.positional_sense.score
        ) / 2
        
        if overall_score < 35:
            return {
                "depth": "basic",
                "use_jargon": False,
                "explain_concepts": True,
                "show_variations": 1,
                "focus": "key_squares_pieces"
            }
        elif overall_score < 55:
            return {
                "depth": "moderate",
                "use_jargon": True,  # With brief explanations
                "explain_concepts": True,
                "show_variations": 2,
                "focus": "plans_ideas"
            }
        elif overall_score < 75:
            return {
                "depth": "detailed",
                "use_jargon": True,
                "explain_concepts": False,  # They know the concepts
                "show_variations": 3,
                "focus": "evaluation_nuances"
            }
        else:
            return {
                "depth": "concise",
                "use_jargon": True,
                "explain_concepts": False,
                "show_variations": 1,  # Just the key line
                "focus": "critical_moves_only"
            }


# =============================================================================
# API FUNCTIONS
# =============================================================================

async def get_chess_understanding(db, user_id: str) -> ChessUnderstanding:
    """
    Get or calculate chess understanding for a user.
    """
    # Check if we have a cached understanding
    cached = await db.chess_understanding.find_one({"user_id": user_id}, {"_id": 0})
    if cached:
        return ChessUnderstanding.from_dict(cached)
    
    # Get player profile
    profile = await db.player_profiles.find_one({"user_id": user_id}, {"_id": 0})
    if not profile:
        # Return default understanding
        return ChessUnderstanding(user_id=user_id)
    
    # Calculate understanding
    understanding = UnderstandingCalculator.calculate_from_profile(profile)
    
    # Cache it
    await db.chess_understanding.update_one(
        {"user_id": user_id},
        {"$set": understanding.to_dict()},
        upsert=True
    )
    
    return understanding


async def update_chess_understanding(db, user_id: str) -> ChessUnderstanding:
    """
    Force recalculation of chess understanding.
    """
    profile = await db.player_profiles.find_one({"user_id": user_id}, {"_id": 0})
    if not profile:
        return ChessUnderstanding(user_id=user_id)
    
    understanding = UnderstandingCalculator.calculate_from_profile(profile)
    
    await db.chess_understanding.update_one(
        {"user_id": user_id},
        {"$set": understanding.to_dict()},
        upsert=True
    )
    
    return understanding


def get_coaching_context_from_understanding(understanding: ChessUnderstanding) -> Dict[str, Any]:
    """
    Get complete coaching context from understanding.
    """
    language = UnderstandingBasedCoaching.get_dimension_specific_language(understanding)
    analysis_style = UnderstandingBasedCoaching.get_position_analysis_style(understanding)
    
    return {
        "understanding": understanding.to_dict(),
        "language": language,
        "analysis_style": analysis_style,
        "overall_level": understanding.overall_understanding,
        "primary_strength": understanding.primary_strength,
        "primary_weakness": understanding.primary_weakness,
        "coaching_focus": understanding.coaching_focus
    }
