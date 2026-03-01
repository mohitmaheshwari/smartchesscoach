"""
CPR Engine - Cognitive Performance Rating (Step 4)

Computes a player's cognitive performance during a coach session.
CPR measures HOW you think, not just the quality of moves.

CPR Components:
1. Decision Quality - Accuracy of moves
2. Time Management - Appropriate time usage
3. Threat Awareness - Response to opponent's threats
4. Emotional Control - Absence of tilt/panic behaviors
5. Focus Consistency - Stable performance throughout game

CPR Scale: 0-100
- 90-100: Elite cognitive control
- 75-89: Strong mental game
- 60-74: Developing awareness
- 40-59: Needs improvement
- 0-39: Significant issues

CPR Change after session indicates learning/improvement.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from datetime import datetime, timezone
from enum import Enum

from .live_behavior_extractor import BehaviorType, BehaviorSeverity


class CPRComponent(str, Enum):
    """Components that make up CPR"""
    DECISION_QUALITY = "decision_quality"
    TIME_MANAGEMENT = "time_management"
    THREAT_AWARENESS = "threat_awareness"
    EMOTIONAL_CONTROL = "emotional_control"
    FOCUS_CONSISTENCY = "focus_consistency"


# Weights for CPR components (must sum to 1.0)
CPR_WEIGHTS = {
    CPRComponent.DECISION_QUALITY: 0.30,
    CPRComponent.TIME_MANAGEMENT: 0.15,
    CPRComponent.THREAT_AWARENESS: 0.25,
    CPRComponent.EMOTIONAL_CONTROL: 0.20,
    CPRComponent.FOCUS_CONSISTENCY: 0.10
}

# Behavior impact on CPR components
BEHAVIOR_IMPACTS = {
    # Negative behaviors
    BehaviorType.IMPULSE_MOVE: {
        CPRComponent.DECISION_QUALITY: -15,
        CPRComponent.EMOTIONAL_CONTROL: -10,
        CPRComponent.TIME_MANAGEMENT: -5
    },
    BehaviorType.THREAT_IGNORED: {
        CPRComponent.THREAT_AWARENESS: -20,
        CPRComponent.DECISION_QUALITY: -10
    },
    BehaviorType.PANIC_DEFENSE: {
        CPRComponent.EMOTIONAL_CONTROL: -15,
        CPRComponent.FOCUS_CONSISTENCY: -10
    },
    BehaviorType.RAPID_STREAK: {
        CPRComponent.EMOTIONAL_CONTROL: -20,
        CPRComponent.TIME_MANAGEMENT: -10,
        CPRComponent.FOCUS_CONSISTENCY: -15
    },
    BehaviorType.TIME_PRESSURE_MISTAKE: {
        CPRComponent.TIME_MANAGEMENT: -15,
        CPRComponent.DECISION_QUALITY: -10
    },
    BehaviorType.REPEATED_MISTAKE: {
        CPRComponent.FOCUS_CONSISTENCY: -20,
        CPRComponent.DECISION_QUALITY: -15
    },
    
    # Positive behaviors
    BehaviorType.CALCULATED_SACRIFICE: {
        CPRComponent.DECISION_QUALITY: +10,
        CPRComponent.THREAT_AWARENESS: +5
    },
    BehaviorType.POSITIONAL_PATIENCE: {
        CPRComponent.TIME_MANAGEMENT: +10,
        CPRComponent.FOCUS_CONSISTENCY: +5
    },
    BehaviorType.TACTICAL_ALERTNESS: {
        CPRComponent.THREAT_AWARENESS: +15,
        CPRComponent.DECISION_QUALITY: +10
    },
    BehaviorType.THREAT_ADDRESSED: {
        CPRComponent.THREAT_AWARENESS: +10,
        CPRComponent.FOCUS_CONSISTENCY: +5
    },
    BehaviorType.ACCURATE_UNDER_PRESSURE: {
        CPRComponent.EMOTIONAL_CONTROL: +15,
        CPRComponent.DECISION_QUALITY: +10,
        CPRComponent.TIME_MANAGEMENT: +5
    }
}


@dataclass
class CPRResult:
    """Result of CPR calculation"""
    overall_cpr: float
    components: Dict[str, float]
    component_details: Dict[str, Dict]
    behavior_impact_summary: Dict[str, int]
    interpretation: str
    recommendations: List[str]
    
    def to_dict(self) -> Dict:
        return {
            "overall_cpr": round(self.overall_cpr, 1),
            "components": {k: round(v, 1) for k, v in self.components.items()},
            "component_details": self.component_details,
            "behavior_impact_summary": self.behavior_impact_summary,
            "interpretation": self.interpretation,
            "recommendations": self.recommendations
        }


class CPREngine:
    """
    Computes Cognitive Performance Rating from session data.
    
    CPR = weighted average of component scores, each starting at 70
    and modified by behavioral events during the session.
    """
    
    BASE_SCORE = 70  # Starting score for each component
    MIN_SCORE = 0
    MAX_SCORE = 100
    
    def __init__(self):
        self.component_scores = {c: self.BASE_SCORE for c in CPRComponent}
        self.component_modifiers = {c: [] for c in CPRComponent}
    
    def compute_cpr(
        self,
        behavior_events: List[Dict],
        move_count: int,
        accuracy_percentage: float = 70.0,
        avg_time_per_move: float = 10.0,
        time_control_base: float = 900.0,
        blunders: int = 0,
        mistakes: int = 0,
        guardian_overrides: int = 0
    ) -> CPRResult:
        """
        Compute CPR from session data.
        
        Args:
            behavior_events: List of behavior event dicts from LiveBehaviorExtractor
            move_count: Total moves made by player
            accuracy_percentage: Overall move accuracy (0-100)
            avg_time_per_move: Average seconds per move
            time_control_base: Base time in seconds (e.g., 900 for 15+10)
            blunders: Number of blunders
            mistakes: Number of mistakes
            guardian_overrides: Times player ignored guardian warnings
        
        Returns:
            CPRResult with overall score and breakdown
        """
        # Reset scores
        self.component_scores = {c: self.BASE_SCORE for c in CPRComponent}
        self.component_modifiers = {c: [] for c in CPRComponent}
        
        # 1. Apply accuracy bonus/penalty to decision quality
        accuracy_modifier = (accuracy_percentage - 70) * 0.5  # -35 to +15 range
        self._apply_modifier(
            CPRComponent.DECISION_QUALITY,
            accuracy_modifier,
            "Move accuracy"
        )
        
        # 2. Apply blunder penalty
        blunder_penalty = blunders * -10
        if blunder_penalty:
            self._apply_modifier(
                CPRComponent.DECISION_QUALITY,
                blunder_penalty,
                f"{blunders} blunder(s)"
            )
        
        # 3. Apply time management score
        ideal_time = time_control_base / 40  # Ideal avg time per move
        time_diff = abs(avg_time_per_move - ideal_time) / ideal_time
        time_modifier = -min(time_diff * 20, 20)  # Up to -20 for poor time management
        if avg_time_per_move < 2 and move_count > 10:
            time_modifier -= 10  # Penalty for rushing
        self._apply_modifier(
            CPRComponent.TIME_MANAGEMENT,
            time_modifier,
            "Time usage pattern"
        )
        
        # 4. Apply guardian override penalty
        if guardian_overrides > 0:
            override_penalty = guardian_overrides * -8
            self._apply_modifier(
                CPRComponent.EMOTIONAL_CONTROL,
                override_penalty,
                f"Ignored {guardian_overrides} guardian warning(s)"
            )
        
        # 5. Apply behavior event impacts
        behavior_summary = {}
        for event in behavior_events:
            behavior_type = BehaviorType(event["behavior_type"])
            severity = BehaviorSeverity(event["severity"])
            
            # Track for summary
            behavior_summary[behavior_type.value] = behavior_summary.get(behavior_type.value, 0) + 1
            
            # Apply impacts
            if behavior_type in BEHAVIOR_IMPACTS:
                severity_multiplier = {
                    BehaviorSeverity.HIGH: 1.5,
                    BehaviorSeverity.MEDIUM: 1.0,
                    BehaviorSeverity.LOW: 0.5
                }.get(severity, 1.0)
                
                for component, impact in BEHAVIOR_IMPACTS[behavior_type].items():
                    adjusted_impact = impact * severity_multiplier
                    self._apply_modifier(
                        component,
                        adjusted_impact,
                        f"{behavior_type.value} ({severity.value})"
                    )
        
        # 6. Calculate component scores (clamped)
        final_components = {}
        component_details = {}
        
        for component in CPRComponent:
            score = self.component_scores[component]
            score = max(self.MIN_SCORE, min(self.MAX_SCORE, score))
            final_components[component.value] = score
            component_details[component.value] = {
                "base": self.BASE_SCORE,
                "final": score,
                "modifiers": self.component_modifiers[component]
            }
        
        # 7. Calculate weighted overall CPR
        overall_cpr = sum(
            final_components[c.value] * weight
            for c, weight in CPR_WEIGHTS.items()
        )
        
        # 8. Generate interpretation and recommendations
        interpretation = self._get_interpretation(overall_cpr)
        recommendations = self._get_recommendations(final_components, behavior_summary)
        
        return CPRResult(
            overall_cpr=overall_cpr,
            components=final_components,
            component_details=component_details,
            behavior_impact_summary=behavior_summary,
            interpretation=interpretation,
            recommendations=recommendations
        )
    
    def _apply_modifier(self, component: CPRComponent, value: float, reason: str):
        """Apply a modifier to a component score"""
        self.component_scores[component] += value
        self.component_modifiers[component].append({
            "value": round(value, 1),
            "reason": reason
        })
    
    def _get_interpretation(self, cpr: float) -> str:
        """Get text interpretation of CPR score"""
        if cpr >= 90:
            return "Elite cognitive control. You're thinking at a very high level."
        elif cpr >= 75:
            return "Strong mental game. Good awareness and emotional control."
        elif cpr >= 60:
            return "Developing well. Focus on the areas highlighted below."
        elif cpr >= 40:
            return "Room for improvement. Consider slowing down and thinking more deliberately."
        else:
            return "Significant issues detected. Focus on fundamentals before speed."
    
    def _get_recommendations(
        self,
        components: Dict[str, float],
        behaviors: Dict[str, int]
    ) -> List[str]:
        """Generate personalized recommendations"""
        recommendations = []
        
        # Find lowest components
        sorted_components = sorted(components.items(), key=lambda x: x[1])
        
        for comp_name, score in sorted_components[:2]:  # Top 2 weaknesses
            if score < 60:
                if comp_name == CPRComponent.DECISION_QUALITY.value:
                    recommendations.append(
                        "Focus on calculating variations more carefully before moving."
                    )
                elif comp_name == CPRComponent.TIME_MANAGEMENT.value:
                    recommendations.append(
                        "Work on balancing speed with accuracy. Don't rush critical positions."
                    )
                elif comp_name == CPRComponent.THREAT_AWARENESS.value:
                    recommendations.append(
                        "Before each move, check what your opponent is threatening."
                    )
                elif comp_name == CPRComponent.EMOTIONAL_CONTROL.value:
                    recommendations.append(
                        "When you feel frustrated, take a breath. Avoid rapid moves."
                    )
                elif comp_name == CPRComponent.FOCUS_CONSISTENCY.value:
                    recommendations.append(
                        "Maintain concentration throughout. Don't relax after gaining advantage."
                    )
        
        # Behavior-specific recommendations
        if behaviors.get(BehaviorType.IMPULSE_MOVE.value, 0) >= 2:
            recommendations.append(
                "You made several impulsive moves. Try counting to 3 before each move."
            )
        
        if behaviors.get(BehaviorType.RAPID_STREAK.value, 0) >= 1:
            recommendations.append(
                "Detected rapid move streak. When you notice this, pause and reset."
            )
        
        if behaviors.get(BehaviorType.THREAT_IGNORED.value, 0) >= 1:
            recommendations.append(
                "Practice the 'check for threats' habit before making your move."
            )
        
        return recommendations[:3]  # Max 3 recommendations


def compute_session_cpr(
    behavior_events: List[Dict],
    session_stats: Dict
) -> Dict:
    """
    Convenience function to compute CPR for a session.
    
    Args:
        behavior_events: List of behavior event dicts
        session_stats: Dict with move_count, accuracy, blunders, etc.
    
    Returns:
        CPR result as dict
    """
    engine = CPREngine()
    result = engine.compute_cpr(
        behavior_events=behavior_events,
        move_count=session_stats.get("move_count", 0),
        accuracy_percentage=session_stats.get("accuracy", 70.0),
        avg_time_per_move=session_stats.get("avg_time_per_move", 10.0),
        time_control_base=session_stats.get("time_control_base", 900.0),
        blunders=session_stats.get("blunders", 0),
        mistakes=session_stats.get("mistakes", 0),
        guardian_overrides=session_stats.get("guardian_overrides", 0)
    )
    return result.to_dict()
