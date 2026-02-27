"""
Difficulty Policy Module

Determines mission difficulty based on learner_type, stagnation, confidence,
and recent game performance.

Difficulty Levels:
- EASY: Reduced friction, enforce 1 rule only
- STANDARD: Balanced challenge
- HARD: Full challenge (only for proven adapters)

HARD Guardrails:
- Must be FAST_ADAPTER
- Must have confidence >= 0.7
- Must NOT be in stagnation
- Must NOT have 2+ recent severe collapses
"""

from typing import List, Dict, Optional
from dataclasses import dataclass


@dataclass
class DifficultyResult:
    """Result of difficulty computation"""
    difficulty: str  # EASY | STANDARD | HARD
    reason: str
    guardrail_triggered: Optional[str] = None
    
    def to_dict(self):
        return {
            "difficulty": self.difficulty,
            "reason": self.reason,
            "guardrail_triggered": self.guardrail_triggered
        }


def choose_difficulty(
    learner_type: str,
    stagnation: bool,
    confidence: float,
    recent_games: List[Dict] = None,
    consecutive_hard_failures: int = 0
) -> DifficultyResult:
    """
    Choose mission difficulty based on user's learning profile.
    
    Args:
        learner_type: FAST_ADAPTER | STEADY | TRYING_BUT_STUCK | NOT_APPLYING
        stagnation: Whether user is stuck in same problem loop
        confidence: 0-1 confidence score
        recent_games: Last 3 game analyses (for collapse detection)
        consecutive_hard_failures: Number of consecutive HARD mission failures
        
    Returns:
        DifficultyResult with difficulty level and reasoning
    """
    from engine_config import DIFFICULTY_CONFIG
    
    # Check for difficulty decay (2+ consecutive HARD failures)
    if consecutive_hard_failures >= 2:
        return DifficultyResult(
            difficulty="STANDARD",
            reason="Downgraded after 2 consecutive HARD mission failures",
            guardrail_triggered="DIFFICULTY_DECAY"
        )
    
    # Low confidence = always EASY
    if confidence < 0.5:
        return DifficultyResult(
            difficulty="EASY",
            reason="Low confidence in analysis — starting gentle",
            guardrail_triggered="LOW_CONFIDENCE"
        )
    
    # NOT_APPLYING = always EASY (reduce friction)
    if learner_type == "NOT_APPLYING":
        return DifficultyResult(
            difficulty="EASY",
            reason="Focus on applying one rule at a time",
            guardrail_triggered=None
        )
    
    # TRYING_BUT_STUCK
    if learner_type == "TRYING_BUT_STUCK":
        if stagnation:
            return DifficultyResult(
                difficulty="EASY",
                reason="Simplifying to break the stuck pattern",
                guardrail_triggered="STAGNATION_SIMPLIFY"
            )
        return DifficultyResult(
            difficulty="STANDARD",
            reason="Building consistency",
            guardrail_triggered=None
        )
    
    # STEADY
    if learner_type == "STEADY":
        return DifficultyResult(
            difficulty="STANDARD",
            reason="Maintaining steady progress",
            guardrail_triggered=None
        )
    
    # FAST_ADAPTER - check HARD eligibility
    if learner_type == "FAST_ADAPTER":
        # Check stagnation guardrail
        if stagnation:
            return DifficultyResult(
                difficulty="STANDARD",
                reason="Stagnation detected — capping difficulty",
                guardrail_triggered="STAGNATION_CAP"
            )
        
        # Check confidence guardrail
        hard_min_confidence = DIFFICULTY_CONFIG.get("hard_min_confidence", 0.7)
        if confidence < hard_min_confidence:
            return DifficultyResult(
                difficulty="STANDARD",
                reason=f"Confidence {confidence:.0%} below {hard_min_confidence:.0%} threshold",
                guardrail_triggered="CONFIDENCE_CAP"
            )
        
        # Check recent collapses guardrail
        recent_collapses = _count_recent_collapses(recent_games or [])
        max_collapses = DIFFICULTY_CONFIG.get("hard_max_recent_collapses", 1)
        
        if recent_collapses > max_collapses:
            return DifficultyResult(
                difficulty="STANDARD",
                reason=f"{recent_collapses} recent collapses — stabilizing first",
                guardrail_triggered="RECENT_COLLAPSE_CAP"
            )
        
        # All guardrails passed — HARD is allowed
        return DifficultyResult(
            difficulty="HARD",
            reason="Consistent adapter with stable recent play",
            guardrail_triggered=None
        )
    
    # Default fallback
    return DifficultyResult(
        difficulty="STANDARD",
        reason="Default difficulty",
        guardrail_triggered=None
    )


def _count_recent_collapses(recent_games: List[Dict]) -> int:
    """
    Count severe collapses in recent games.
    
    A collapse is defined as:
    - game_quality_bucket == "BAD", OR
    - tilt_index > 0.6
    
    This is more meaningful than just "loss" — we care about HOW they lost.
    """
    from engine_config import DIFFICULTY_CONFIG
    
    collapse_count = 0
    tilt_threshold = DIFFICULTY_CONFIG.get("collapse_tilt_threshold", 0.6)
    bad_bucket = DIFFICULTY_CONFIG.get("collapse_quality_bucket", "BAD")
    
    for game in recent_games[:3]:  # Only last 3
        debug = game.get("debug", {})
        
        # Check for quality bucket
        quality = debug.get("game_quality", "")
        if quality == bad_bucket:
            collapse_count += 1
            continue
        
        # Check for tilt
        tilt = debug.get("tilt_index", 0)
        if tilt > tilt_threshold:
            collapse_count += 1
            continue
    
    return collapse_count


def get_difficulty_cap(user_profile: Dict) -> str:
    """
    Get the current difficulty cap for a user based on their mission history.
    
    Returns "HARD", "STANDARD", or "EASY"
    """
    consecutive_hard_failures = user_profile.get("consecutive_hard_failures", 0)
    
    if consecutive_hard_failures >= 2:
        return "STANDARD"
    
    return "HARD"


def update_difficulty_decay(
    user_profile: Dict,
    mission_difficulty: str,
    mission_succeeded: bool
) -> Dict:
    """
    Update difficulty decay counters after mission completion.
    
    Returns updated profile fields.
    """
    consecutive_hard_failures = user_profile.get("consecutive_hard_failures", 0)
    
    if mission_difficulty == "HARD":
        if mission_succeeded:
            # Reset on success
            consecutive_hard_failures = 0
        else:
            # Increment on failure
            consecutive_hard_failures += 1
    else:
        # Non-HARD missions don't affect the counter
        pass
    
    return {
        "consecutive_hard_failures": consecutive_hard_failures,
        "last_mission_difficulty": mission_difficulty,
        "last_mission_succeeded": mission_succeeded
    }
