"""
Adaptive Profile Engine
=======================
Version: v1
Generates adaptive profile for user based on rating, stability, and performance.
All UX decisions read from this profile - no hardcoded checks in UI.
"""

from typing import Dict, Optional
from reflect_constants import (
    RatingBand, StabilityBand, ReflectionMode, RewardTone,
    get_rating_band, get_stability_band, ADAPTIVE_DEFAULTS,
    get_intent_options, get_confidence_options
)
import logging

logger = logging.getLogger(__name__)


class AdaptiveProfile:
    """
    User's adaptive profile for the current session.
    Controls all UX decisions.
    """
    
    def __init__(
        self,
        rating: int,
        tsi: float = 75.0,
        recent_mission_success_rate: float = 0.7,
        recent_reflection_rate: float = 0.5,
        recent_puzzle_accuracy: float = 0.6,
    ):
        self.rating = rating
        self.tsi = tsi
        self.recent_mission_success_rate = recent_mission_success_rate
        self.recent_reflection_rate = recent_reflection_rate
        self.recent_puzzle_accuracy = recent_puzzle_accuracy
        
        # Compute bands
        self.rating_band = get_rating_band(rating)
        self.stability_band = get_stability_band(tsi)
        
        # Get base config
        self.base_config = ADAPTIVE_DEFAULTS.get(
            self.rating_band,
            ADAPTIVE_DEFAULTS[RatingBand.BAND_C]
        )
        
        # Compute adjustments
        self._compute_adjustments()
    
    def _compute_adjustments(self):
        """Compute performance-based adjustments."""
        # Adjust success target based on recent performance
        self.success_target_adjustment = 0
        if self.recent_mission_success_rate > 0.85:
            self.success_target_adjustment = 0.05  # Make slightly harder
        elif self.recent_mission_success_rate < 0.50:
            self.success_target_adjustment = -0.10  # Make easier
        
        # Adjust mission length based on stability
        self.mission_length_adjustment = 0
        if self.stability_band == StabilityBand.VOLATILE:
            self.mission_length_adjustment = -2  # Shorter missions
        elif self.stability_band == StabilityBand.CHAOTIC:
            self.mission_length_adjustment = -3  # Even shorter
        elif self.stability_band == StabilityBand.STABLE:
            self.mission_length_adjustment = 1  # Can handle longer
        
        # Adjust reflection depth
        self.reflection_friction_budget = self.base_config["friction_budget_taps"]
        if self.recent_reflection_rate < 0.3:
            # User struggles with reflection - make it easier
            self.reflection_friction_budget = max(2, self.reflection_friction_budget - 1)
    
    def to_dict(self) -> Dict:
        """Export profile for API response."""
        base = self.base_config.copy()
        
        # Apply adjustments
        adjusted_success_target = max(0.50, min(0.90, 
            base["success_target"] + self.success_target_adjustment
        ))
        
        adjusted_mission_minutes = max(3, min(15,
            base["mission_minutes_target"] + self.mission_length_adjustment
        ))
        
        return {
            # Rating info
            "rating": self.rating,
            "rating_band": self.rating_band.value,
            "rating_band_label": self._get_band_label(),
            
            # Stability info
            "tsi": self.tsi,
            "stability_band": self.stability_band.value,
            
            # Reflection config
            "reflection_mode": base["reflection_mode"].value,
            "max_quick_tags": base["max_quick_tags"],
            "friction_budget_taps": self.reflection_friction_budget,
            "show_advanced_labels": base["show_advanced_labels"],
            
            # Mission config
            "mission_minutes_target": adjusted_mission_minutes,
            "mission_steps": base["mission_steps"],
            "success_target": adjusted_success_target,
            
            # Reward config
            "reward_tone": base["reward_tone"].value,
            "streak_style": base["streak_style"],
            
            # Performance data used
            "recent_mission_success_rate": self.recent_mission_success_rate,
            "recent_reflection_rate": self.recent_reflection_rate,
            
            # Intent and confidence options (for frontend)
            "intent_options": get_intent_options(),
            "confidence_options": get_confidence_options(),
        }
    
    def _get_band_label(self) -> str:
        """Human-readable band label."""
        labels = {
            RatingBand.BAND_A: "Beginner",
            RatingBand.BAND_B: "Developing",
            RatingBand.BAND_C: "Intermediate",
            RatingBand.BAND_D: "Advanced",
            RatingBand.BAND_E: "Expert",
        }
        return labels.get(self.rating_band, "Intermediate")


async def get_adaptive_profile(
    user_id: str,
    rating: int,
    db,
) -> Dict:
    """
    Build adaptive profile for user.
    Fetches recent performance data from DB.
    """
    # Defaults
    tsi = 75.0
    mission_success_rate = 0.7
    reflection_rate = 0.5
    puzzle_accuracy = 0.6
    
    try:
        # Get TSI from training profile or cognitive data
        training_profile = await db.training_profiles.find_one({"user_id": user_id})
        if training_profile and "tsi" in training_profile:
            tsi = training_profile.get("tsi", 75.0)
        
        # Get recent mission success rate
        recent_missions = await db.mission_sessions.find(
            {"user_id": user_id}
        ).sort("ended_at", -1).limit(10).to_list(10)
        
        if recent_missions:
            passed = sum(1 for m in recent_missions if m.get("score", {}).get("result") == "pass")
            mission_success_rate = passed / len(recent_missions)
        
        # Get recent reflection rate
        recent_reflections = await db.reflection_sessions.find(
            {"user_id": user_id}
        ).sort("created_at", -1).limit(20).to_list(20)
        
        # Count how many pending moments got reflections
        if recent_reflections:
            completed = sum(1 for r in recent_reflections if r.get("completed_in_seconds", 0) > 0)
            reflection_rate = min(1.0, completed / len(recent_reflections))
        
        # Get puzzle accuracy
        puzzle_progress = await db.puzzle_progress.find_one({"user_id": user_id})
        if puzzle_progress:
            total = puzzle_progress.get("puzzles_attempted", 0)
            correct = puzzle_progress.get("puzzles_correct", 0)
            if total > 0:
                puzzle_accuracy = correct / total
    
    except Exception as e:
        logger.warning(f"Error fetching adaptive data: {e}")
    
    # Build profile
    profile = AdaptiveProfile(
        rating=rating,
        tsi=tsi,
        recent_mission_success_rate=mission_success_rate,
        recent_reflection_rate=reflection_rate,
        recent_puzzle_accuracy=puzzle_accuracy,
    )
    
    return profile.to_dict()


def get_adaptive_profile_sync(
    rating: int,
    tsi: float = 75.0,
    mission_success_rate: float = 0.7,
    reflection_rate: float = 0.5,
) -> Dict:
    """
    Synchronous version for use in non-async contexts.
    """
    profile = AdaptiveProfile(
        rating=rating,
        tsi=tsi,
        recent_mission_success_rate=mission_success_rate,
        recent_reflection_rate=reflection_rate,
    )
    return profile.to_dict()
