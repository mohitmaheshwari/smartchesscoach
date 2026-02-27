"""
Learning Velocity Calculator

Computes how fast a user is applying coaching advice and improving.

Formula (weighted):
    weighted_follow_rate = 
        sum(severity_weight for FOLLOWED and applicable) /
        sum(severity_weight for applicable)
    
    base_velocity = 
        0.5 * weighted_follow_rate +
        0.3 * improvement_trend +
        0.2 * stability_trend
    
    P1.7 Addition (smoothed):
        mission_adjustment = avg(last 3 mission validation scores) * 0.2
        velocity = 0.8 * previous_velocity + 0.2 * (base_velocity + mission_adjustment)

Learner Types:
    >= 0.75: FAST_ADAPTER
    >= 0.55: STEADY
    >= 0.35: TRYING_BUT_STUCK
    < 0.35: NOT_APPLYING
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta


@dataclass
class LearningVelocityResult:
    """Result of learning velocity calculation"""
    velocity: float  # 0.0 - 1.0
    learner_type: str  # FAST_ADAPTER | STEADY | TRYING_BUT_STUCK | NOT_APPLYING
    weighted_follow_rate: float
    improvement_trend: float
    stability_trend: float
    mission_adjustment: float  # P1.7: Mission validation contribution
    advice_stats: Dict
    confidence: float  # How reliable is this calculation
    
    def to_dict(self):
        return {
            "velocity": round(self.velocity, 2),
            "learner_type": self.learner_type,
            "weighted_follow_rate": round(self.weighted_follow_rate, 2),
            "improvement_trend": round(self.improvement_trend, 2),
            "stability_trend": round(self.stability_trend, 2),
            "mission_adjustment": round(self.mission_adjustment, 2),
            "advice_stats": self.advice_stats,
            "confidence": round(self.confidence, 2)
        }


def compute_learning_velocity(
    applications: List[Dict],
    leak_trends: Dict,
    games_count: int = 10,
    previous_velocity: float = None,
    mission_validations: List[Dict] = None
) -> LearningVelocityResult:
    """
    Compute learning velocity from advice applications and mission validations.
    
    Args:
        applications: List of advice_applications (most recent first)
        leak_trends: Dict of leak tag trends from feature_extractor
        games_count: Number of games to consider
        previous_velocity: Previous velocity for smoothing (P1.7)
        mission_validations: Recent mission validation scores (P1.7)
        
    Returns:
        LearningVelocityResult with velocity, learner_type, and stats
    """
    # Filter to applicable applications
    applicable = [a for a in applications if a.get("applicable", False)]
    
    if not applicable:
        return LearningVelocityResult(
            velocity=0.5,  # Neutral when no data
            learner_type="STEADY",
            weighted_follow_rate=0.5,
            improvement_trend=0.5,
            stability_trend=0.5,
            mission_adjustment=0.0,
            advice_stats={
                "total_applications": 0,
                "applicable": 0,
                "followed": 0,
                "violated": 0
            },
            confidence=0.1
        )
    
    # 1. Compute weighted follow rate
    weighted_follow_rate = _compute_weighted_follow_rate(applicable)
    
    # 2. Compute improvement trend (from leak trends)
    improvement_trend = _compute_improvement_trend(leak_trends)
    
    # 3. Compute stability trend (from time panic specifically)
    stability_trend = _compute_stability_trend(leak_trends)
    
    # 4. Compute base velocity
    base_velocity = (
        0.5 * weighted_follow_rate +
        0.3 * improvement_trend +
        0.2 * stability_trend
    )
    
    # 5. P1.7: Add mission validation adjustment
    mission_adjustment = _compute_mission_adjustment(mission_validations)
    
    # 6. P1.7: Apply smoothing if previous velocity exists
    if previous_velocity is not None:
        # Smoothed: 0.8 * previous + 0.2 * (base + mission_adjustment)
        velocity = (
            0.8 * previous_velocity + 
            0.2 * (base_velocity + mission_adjustment)
        )
    else:
        velocity = base_velocity + mission_adjustment
    
    # Clamp to 0-1
    velocity = max(0.0, min(1.0, velocity))
    
    # 7. Classify learner type
    learner_type = _classify_learner(velocity)
    
    # 8. Compute confidence
    confidence = min(1.0, len(applicable) / 15)
    
    # 9. Stats
    followed_count = sum(1 for a in applicable if a.get("outcome") == "FOLLOWED")
    violated_count = sum(1 for a in applicable if a.get("outcome") == "VIOLATED")
    
    return LearningVelocityResult(
        velocity=velocity,
        learner_type=learner_type,
        weighted_follow_rate=weighted_follow_rate,
        improvement_trend=improvement_trend,
        stability_trend=stability_trend,
        mission_adjustment=mission_adjustment,
        advice_stats={
            "total_applications": len(applications),
            "applicable": len(applicable),
            "followed": followed_count,
            "violated": violated_count,
            "follow_ratio": f"{followed_count}/{len(applicable)}"
        },
        confidence=confidence
    )


def _compute_mission_adjustment(mission_validations: List[Dict]) -> float:
    """
    Compute learning velocity adjustment from mission validation scores.
    
    P1.7: avg(last 3 validation scores) * 0.2
    
    Returns adjustment value (0 to 0.2)
    """
    if not mission_validations:
        return 0.0
    
    scores = [m.get("validation_score", 0) for m in mission_validations[:3]]
    if not scores:
        return 0.0
    
    avg_score = sum(scores) / len(scores)
    return avg_score * 0.2


def _compute_weighted_follow_rate(applicable: List[Dict]) -> float:
    """
    Compute weighted follow rate based on severity.
    
    weighted_follow_rate = 
        sum(severity_weight for FOLLOWED) /
        sum(severity_weight for all applicable)
    """
    total_weight = 0
    followed_weight = 0
    
    for app in applicable:
        severity = app.get("severity_weight", 3)
        total_weight += severity
        
        if app.get("outcome") == "FOLLOWED":
            followed_weight += severity
    
    if total_weight == 0:
        return 0.5
    
    return followed_weight / total_weight


def _compute_improvement_trend(leak_trends: Dict) -> float:
    """
    Compute improvement trend from leak tag slopes.
    
    Positive slope = worsening
    Negative slope = improving
    
    Returns 0.0 (worsening) to 1.0 (improving)
    """
    if not leak_trends:
        return 0.5
    
    # Get slopes from key leak tags
    key_tags = ["TACTICAL_BLINDNESS", "OPENING_WANDER", "TIME_PANIC", "CONVERSION_ISSUE"]
    slopes = []
    
    for tag in key_tags:
        trend = leak_trends.get(tag, {})
        slope = trend.get("slope", 0)
        if slope != 0:
            slopes.append(slope)
    
    if not slopes:
        return 0.5
    
    # Average slope (negative = improving)
    avg_slope = sum(slopes) / len(slopes)
    
    # Convert to 0-1 scale (inverted: negative slope = higher score)
    # Slope typically ranges from -1 to +1
    improvement = 0.5 - (avg_slope * 0.5)
    
    return max(0.0, min(1.0, improvement))


def _compute_stability_trend(leak_trends: Dict) -> float:
    """
    Compute stability trend specifically from TIME_PANIC.
    
    Time panic is weighted heavily because it affects everything else.
    """
    time_panic = leak_trends.get("TIME_PANIC", {})
    
    avg = time_panic.get("avg", 0)
    games_with_tag = time_panic.get("games_with_tag", 0)
    
    # Lower avg and fewer games with tag = better stability
    if avg == 0 and games_with_tag == 0:
        return 0.8  # Good stability
    
    # Normalize: avg typically 0-1, games_with_tag typically 0-10
    stability = 1.0 - min(1.0, (avg * 0.6 + (games_with_tag / 10) * 0.4))
    
    return max(0.0, min(1.0, stability))


def _classify_learner(velocity: float) -> str:
    """Classify learner type based on velocity"""
    if velocity >= 0.75:
        return "FAST_ADAPTER"
    elif velocity >= 0.55:
        return "STEADY"
    elif velocity >= 0.35:
        return "TRYING_BUT_STUCK"
    else:
        return "NOT_APPLYING"


# ==================== ADVICE LIFECYCLE ====================

async def check_advice_resolution(
    db,
    advice_id: str,
    consecutive_followed: int = 4
) -> bool:
    """
    Check if advice should be resolved (auto-archived).
    
    Rule: If followed for 4 consecutive applicable games, resolve.
    """
    # Get recent applications for this advice
    applications = await db.advice_applications.find(
        {"advice_id": advice_id, "applicable": True}
    ).sort("evaluated_at", -1).limit(consecutive_followed).to_list(consecutive_followed)
    
    if len(applications) < consecutive_followed:
        return False
    
    # Check if all are FOLLOWED
    return all(a.get("outcome") == "FOLLOWED" for a in applications)


async def resolve_advice(db, advice_id: str) -> None:
    """Mark advice as resolved"""
    await db.coach_advice.update_one(
        {"advice_id": advice_id},
        {"$set": {
            "status": "RESOLVED",
            "resolved_at": datetime.now(timezone.utc).isoformat()
        }}
    )


async def get_consecutive_follows(db, advice_id: str) -> int:
    """Get count of consecutive followed applications"""
    applications = await db.advice_applications.find(
        {"advice_id": advice_id, "applicable": True}
    ).sort("evaluated_at", -1).limit(10).to_list(10)
    
    count = 0
    for app in applications:
        if app.get("outcome") == "FOLLOWED":
            count += 1
        else:
            break
    
    return count


async def get_active_advice_count(db, user_id: str) -> int:
    """Get count of active advice for a user"""
    return await db.coach_advice.count_documents({
        "user_id": user_id,
        "status": "ACTIVE"
    })


async def archive_lowest_severity_resolved(db, user_id: str) -> None:
    """
    Archive the lowest severity resolved advice to make room for new advice.
    Called when user has 3+ active advice.
    """
    # Find resolved advice, lowest severity first
    resolved = await db.coach_advice.find_one(
        {"user_id": user_id, "status": "RESOLVED"},
        sort=[("severity", 1)]
    )
    
    if resolved:
        await db.coach_advice.update_one(
            {"advice_id": resolved["advice_id"]},
            {"$set": {"status": "ARCHIVED"}}
        )


# ==================== COMPLIANCE SCORE ====================

def compute_compliance_score(applications: List[Dict]) -> int:
    """
    Compute a 0-100 compliance score from applications.
    
    Weighted by severity and recency.
    """
    if not applications:
        return 60  # Neutral
    
    applicable = [a for a in applications if a.get("applicable", False)]
    if not applicable:
        return 60
    
    # Weight by recency (more recent = higher weight)
    total_score = 0
    total_weight = 0
    
    for i, app in enumerate(applicable):
        recency_weight = max(0.5, 1.0 - (i * 0.1))  # 1.0 for most recent
        severity = app.get("severity_weight", 3)
        weight = recency_weight * severity
        
        if app.get("outcome") == "FOLLOWED":
            total_score += weight * 100
        elif app.get("outcome") == "VIOLATED":
            total_score += weight * 0
        else:
            total_score += weight * 50  # NA gets neutral
        
        total_weight += weight
    
    if total_weight == 0:
        return 60
    
    return int(total_score / total_weight)
