"""
Scoring Engine Module

Converts behavioral features into 0-100 scores with labels.
"""

from typing import Dict


class ScoreItem:
    """A single behavioral dimension score"""
    def __init__(self, score: int, label: str, why: str, evidence_refs: list = None):
        self.score = score
        self.label = label
        self.why = why
        self.evidence_refs = evidence_refs or []
    
    def to_dict(self):
        return {
            "score": self.score,
            "label": self.label,
            "why": self.why,
            "evidence_refs": self.evidence_refs
        }


def score_behavior(features) -> Dict[str, ScoreItem]:
    """
    Convert features into 0-100 scores with labels.
    """
    scorecard = {}
    
    # Plan Discipline
    plan_score = round(features.opening_plan_score * 100)
    plan_why = _get_plan_why(features)
    scorecard["plan_discipline"] = ScoreItem(
        score=plan_score,
        label=labelize(plan_score),
        why=plan_why,
        evidence_refs=[e for e in features.evidence if e.get("type") in ["repeat_piece", "early_queen", "plan_break"]]
    )
    
    # Decision Stability
    stability_raw = 1 - (0.55 * features.time_pressure_index + 0.45 * features.tilt_index)
    stability_score = round(max(0, min(1, stability_raw)) * 100)
    stability_why = _get_stability_why(features, stability_score)
    scorecard["decision_stability"] = ScoreItem(
        score=stability_score,
        label=labelize(stability_score),
        why=stability_why,
        evidence_refs=[e for e in features.evidence if e.get("type") in ["time_pressure", "tilt", "collapse"]]
    )
    
    # Pattern Persistence
    persistence_score = _score_persistence(features.leak_tags_last_game, features.leak_trends)
    persistence_why = _get_persistence_why(persistence_score)
    scorecard["pattern_persistence"] = ScoreItem(
        score=persistence_score,
        label=labelize(persistence_score),
        why=persistence_why,
        evidence_refs=[]
    )
    
    # Coach Compliance (P1 - placeholder)
    scorecard["coach_compliance"] = ScoreItem(
        score=60,
        label="Mixed",
        why="Advice tracking coming soon",
        evidence_refs=[]
    )
    
    # Learning Velocity (P1 - placeholder)
    scorecard["learning_velocity"] = ScoreItem(
        score=60,
        label="Mixed",
        why="Learning velocity tracking coming soon",
        evidence_refs=[]
    )
    
    return scorecard


def _get_plan_why(features) -> str:
    """Get explanation for plan discipline score"""
    if features.plan_signal == "STUCK_TO_PLAN":
        return "Development stayed clean throughout opening"
    elif features.plan_signal == "ABANDONED":
        if features.repeat_piece_moves > 0:
            return f"Moved same piece {features.repeat_piece_moves}x in opening"
        return "Opening plan broke early"
    return "Opening could be more focused"


def _get_stability_why(features, score: int) -> str:
    """Get explanation for decision stability score"""
    if score >= 70:
        return "Stable decision-making throughout"
    elif features.tilt_index >= 0.4:
        return "Errors escalated after first mistake"
    elif features.time_pressure_index >= 0.5:
        return "Time pressure affected decisions"
    return "Decision stability needs attention"


def _get_persistence_why(score: int) -> str:
    """Get explanation for pattern persistence score"""
    if score >= 70:
        return "No recurring negative patterns"
    elif score >= 50:
        return "Some patterns repeating"
    return "Same issues keep appearing"


def _score_persistence(leak_tags: Dict[str, int], leak_trends: Dict[str, Dict]) -> int:
    """Score pattern persistence"""
    from .feature_extractor import NEGATIVE_LEAK_TAGS
    
    penalty = 0
    
    for tag in NEGATIVE_LEAK_TAGS:
        penalty += min(25, leak_tags.get(tag, 0) * 15)
        if leak_trends.get(tag, {}).get("avg", 0) >= 0.6:
            penalty += 10
    
    return max(0, 80 - penalty)


def labelize(score: int) -> str:
    """Convert score to label"""
    if score >= 80:
        return "Excellent"
    elif score >= 65:
        return "Good"
    elif score >= 45:
        return "Mixed"
    return "Concern"
