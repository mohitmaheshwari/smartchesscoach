"""
Mission Generation Service - Dopamine Engine Core
==================================================
Version: v1
Deterministic mission generation based on user's mistakes and training history.
No LLM - pure rule-based selection.
"""

from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone, timedelta
from reflect_constants import (
    RatingBand, get_rating_band, ADAPTIVE_DEFAULTS,
    RewardEventType
)
import uuid
import logging

logger = logging.getLogger(__name__)


# ============================================
# MISSION TYPES
# ============================================
MISSION_TYPES = {
    "recognition_positions": {
        "label": "Pattern Recognition",
        "description": "Identify the correct response in similar positions",
        "goal_type": "positions",
    },
    "drill_sequence": {
        "label": "Drill Practice",
        "description": "Practice the correct continuation",
        "goal_type": "drills",
    },
    "reflect_and_drill": {
        "label": "Reflect & Drill",
        "description": "Reflect on your mistake, then practice",
        "goal_type": "mixed",
    },
}


# ============================================
# PATTERN TO FOCUS MAPPING
# ============================================
PATTERN_FOCUS_MAP = {
    "ignored_opponent_forcing": {
        "focus_label": "Opponent Threat Awareness",
        "micro_protocol": [
            "Before moving, scan opponent's checks",
            "Look for opponent's captures",
            "Ask: Can opponent hurt me here?",
        ],
    },
    "missed_forcing_move": {
        "focus_label": "Forcing Move Awareness",
        "micro_protocol": [
            "Check all captures first",
            "Look for checks",
            "Find the most forcing option",
        ],
    },
    "phantom_threat": {
        "focus_label": "Threat Prioritization",
        "micro_protocol": [
            "Ask: Is this threat real?",
            "Count attackers vs defenders",
            "Check if defense is needed",
        ],
    },
    "advantage_mismanagement": {
        "focus_label": "Advantage Conversion",
        "micro_protocol": [
            "Don't rush when ahead",
            "Look for safe improving moves",
            "Avoid unnecessary risks",
        ],
    },
    "critical_moment_drift": {
        "focus_label": "Critical Position Focus",
        "micro_protocol": [
            "Slow down at key moments",
            "Compare candidate moves",
            "Check your first instinct",
        ],
    },
    "structural_misjudgment": {
        "focus_label": "Positional Understanding",
        "micro_protocol": [
            "Consider pawn structure",
            "Think about piece activity",
            "Look for long-term consequences",
        ],
    },
}


# ============================================
# DIFFICULTY PRESETS BY RATING BAND
# ============================================
DIFFICULTY_PRESETS = {
    RatingBand.BAND_A: {
        "positions": 4,
        "success_threshold": 3,
        "hints_allowed": 2,
        "time_per_position": None,  # No time pressure
    },
    RatingBand.BAND_B: {
        "positions": 5,
        "success_threshold": 3,
        "hints_allowed": 1,
        "time_per_position": None,
    },
    RatingBand.BAND_C: {
        "positions": 5,
        "success_threshold": 4,
        "hints_allowed": 1,
        "time_per_position": 60,  # Optional
    },
    RatingBand.BAND_D: {
        "positions": 6,
        "success_threshold": 5,
        "hints_allowed": 0,
        "time_per_position": 45,
    },
    RatingBand.BAND_E: {
        "positions": 8,
        "success_threshold": 6,
        "hints_allowed": 0,
        "time_per_position": 30,
    },
}


class MissionGenerator:
    """
    Generates daily missions based on user's mistake patterns.
    Deterministic, rule-based, rating-adaptive.
    """
    
    def __init__(self, user_id: str, rating: int):
        self.user_id = user_id
        self.rating = rating
        self.rating_band = get_rating_band(rating)
        self.adaptive_config = ADAPTIVE_DEFAULTS.get(
            self.rating_band,
            ADAPTIVE_DEFAULTS[RatingBand.BAND_C]
        )
        self.difficulty = DIFFICULTY_PRESETS.get(
            self.rating_band,
            DIFFICULTY_PRESETS[RatingBand.BAND_C]
        )
    
    def compute_pattern_priority(
        self,
        pattern: str,
        repeat_count_14d: int,
        avg_severity: float,
        last_seen_at: datetime,
        last_trained_at: Optional[datetime],
        is_current_focus: bool,
        now: datetime,
    ) -> float:
        """
        Compute priority score for a mistake pattern.
        
        Formula:
        priority = 
          (repeat_count_14d * 0.30) +
          (avg_severity_norm * 0.25) +
          (recency_weight * 0.20) +
          (training_neglect_weight * 0.15) +
          (coach_focus_bonus * 0.10)
        """
        # Normalize repeat count (0-6 range → 0-1)
        repeat_norm = min(1.0, repeat_count_14d / 6.0)
        
        # Normalize severity (already 0-1 from cp_loss)
        severity_norm = min(1.0, avg_severity)
        
        # Recency weight (more recent = higher weight)
        days_since = (now - last_seen_at).days if last_seen_at else 14
        recency_weight = max(0, 1.0 - (days_since / 14.0))
        
        # Training neglect (higher if not trained recently)
        neglect_weight = 1.0
        if last_trained_at:
            days_since_training = (now - last_trained_at).days
            neglect_weight = min(1.0, days_since_training / 7.0)
        
        # Focus bonus
        focus_bonus = 0.10 if is_current_focus else 0.0
        
        priority = (
            repeat_norm * 0.30 +
            severity_norm * 0.25 +
            recency_weight * 0.20 +
            neglect_weight * 0.15 +
            focus_bonus
        )
        
        return round(priority, 3)
    
    def select_pattern(
        self,
        patterns: List[Dict],
        recent_missions: List[Dict],
        current_focus: Optional[str],
        post_loss_game: Optional[Dict] = None,
    ) -> Tuple[str, Dict]:
        """
        Select the best pattern for today's mission.
        
        Returns:
            (pattern_name, pattern_data)
        """
        now = datetime.now(timezone.utc)
        
        # If post-loss trigger exists, prioritize that game's main issue
        if post_loss_game:
            game_pattern = post_loss_game.get("main_pattern")
            if game_pattern and game_pattern in PATTERN_FOCUS_MAP:
                return game_pattern, PATTERN_FOCUS_MAP[game_pattern]
        
        # Score each pattern
        scored = []
        for p in patterns:
            pattern_name = p.get("pattern")
            if pattern_name not in PATTERN_FOCUS_MAP:
                continue
            
            priority = self.compute_pattern_priority(
                pattern=pattern_name,
                repeat_count_14d=p.get("repeat_count_14d", 0),
                avg_severity=p.get("avg_severity", 0.5),
                last_seen_at=p.get("last_seen_at", now - timedelta(days=7)),
                last_trained_at=p.get("last_trained_at"),
                is_current_focus=(pattern_name == current_focus),
                now=now,
            )
            
            scored.append((pattern_name, priority, p))
        
        if not scored:
            # Fallback to general improvement
            default_pattern = "critical_moment_drift"
            return default_pattern, PATTERN_FOCUS_MAP[default_pattern]
        
        # Sort by priority
        scored.sort(key=lambda x: x[1], reverse=True)
        
        # Check rotation rule: if same pattern used in last 2 missions and passed both
        top_pattern = scored[0][0]
        if len(recent_missions) >= 2:
            last_two = recent_missions[:2]
            same_pattern = all(m.get("focus_pattern") == top_pattern for m in last_two)
            both_passed = all(m.get("result") == "pass" for m in last_two)
            
            if same_pattern and both_passed and len(scored) > 1:
                # Rotate to next best pattern
                top_pattern = scored[1][0]
        
        return top_pattern, PATTERN_FOCUS_MAP[top_pattern]
    
    def build_mission(
        self,
        pattern: str,
        pattern_data: Dict,
        trigger_type: str,
        source_game_id: Optional[str] = None,
        metadata: Dict = None,
    ) -> Dict:
        """
        Build a complete mission document.
        """
        mission_id = f"mission_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc)
        
        # Get difficulty settings
        positions = self.difficulty["positions"]
        success_threshold = self.difficulty["success_threshold"]
        
        # Estimate time
        minutes = self.adaptive_config["mission_minutes_target"]
        
        return {
            "_id": mission_id,
            "mission_id": mission_id,
            "user_id": self.user_id,
            "mission_date": now.strftime("%Y-%m-%d"),
            "trigger_type": trigger_type,  # "daily" | "post_loss" | "relapse"
            "source_game_id": source_game_id,
            
            "focus_pattern": pattern,
            "focus_label": pattern_data["focus_label"],
            "micro_protocol": pattern_data["micro_protocol"],
            
            "goal_type": "recognition_positions",
            "goal_target": positions,
            "goal_success_threshold": success_threshold,
            
            "estimated_minutes": minutes,
            "difficulty_band": self.rating_band.value,
            
            "status": "pending",  # pending | active | completed | expired
            "started_at": None,
            "completed_at": None,
            "expires_at": (now + timedelta(hours=24)).isoformat(),
            
            "metadata": metadata or {},
            "created_at": now.isoformat(),
        }


async def generate_daily_mission(
    user_id: str,
    rating: int,
    db,
    post_loss_game: Optional[Dict] = None,
    trigger_type: Optional[str] = None,
    source_game_id: Optional[str] = None,
    force_pattern: Optional[str] = None,
) -> Dict:
    """
    Main entry point for generating today's mission.
    
    Args:
        user_id: User ID
        rating: User's rating
        db: Database connection
        post_loss_game: Game dict if triggered by loss
        trigger_type: Override trigger type ("daily", "post_loss", "relapse")
        source_game_id: Override source game ID
        force_pattern: Force a specific pattern (for post-loss recovery)
    """
    generator = MissionGenerator(user_id, rating)
    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")
    
    # Check if mission already exists for today (only for daily missions)
    if not force_pattern:
        existing = await db.behavioral_missions.find_one({
            "user_id": user_id,
            "mission_date": today,
            "status": {"$in": ["pending", "active"]},
        })
        
        if existing:
            return existing
    
    # Get recent patterns from game analyses
    recent_analyses = await db.game_analyses.find({
        "user_id": user_id,
        "analyzed_at": {"$gte": (now - timedelta(days=14)).isoformat()},
    }).to_list(50)
    
    # Aggregate patterns
    pattern_stats = {}
    for analysis in recent_analyses:
        for blunder in analysis.get("blunders", []):
            cat = blunder.get("mistake_category")
            if cat:
                if cat not in pattern_stats:
                    pattern_stats[cat] = {
                        "pattern": cat,
                        "repeat_count_14d": 0,
                        "severities": [],
                        "last_seen_at": None,
                    }
                pattern_stats[cat]["repeat_count_14d"] += 1
                pattern_stats[cat]["severities"].append(abs(blunder.get("cp_loss", 100)) / 500)
                analyzed_at = analysis.get("analyzed_at")
                if analyzed_at:
                    try:
                        at = datetime.fromisoformat(analyzed_at.replace("Z", "+00:00"))
                        if not pattern_stats[cat]["last_seen_at"] or at > pattern_stats[cat]["last_seen_at"]:
                            pattern_stats[cat]["last_seen_at"] = at
                    except:
                        pass
    
    # Calculate averages
    patterns = []
    for cat, stats in pattern_stats.items():
        stats["avg_severity"] = sum(stats["severities"]) / len(stats["severities"]) if stats["severities"] else 0.5
        patterns.append(stats)
    
    # Get recent missions for rotation check
    recent_missions = await db.behavioral_missions.find({
        "user_id": user_id,
    }).sort("created_at", -1).limit(10).to_list(10)
    
    # Get current focus from training profile
    training_profile = await db.training_profiles.find_one({"user_id": user_id})
    current_focus = training_profile.get("current_focus_pattern") if training_profile else None
    
    # Select pattern (or use forced pattern)
    if force_pattern and force_pattern in PATTERN_FOCUS_MAP:
        pattern = force_pattern
        pattern_data = PATTERN_FOCUS_MAP[force_pattern]
    else:
        pattern, pattern_data = generator.select_pattern(
            patterns=patterns,
            recent_missions=recent_missions,
            current_focus=current_focus,
            post_loss_game=post_loss_game,
        )
    
    # Determine trigger type (use override if provided)
    final_trigger_type = trigger_type or ("post_loss" if post_loss_game else "daily")
    final_source_game_id = source_game_id or (post_loss_game.get("game_id") if post_loss_game else None)
    
    # Build mission
    mission = generator.build_mission(
        pattern=pattern,
        pattern_data=pattern_data,
        trigger_type=final_trigger_type,
        source_game_id=final_source_game_id,
        metadata={
            "pattern_priority": generator.compute_pattern_priority(
                pattern=pattern,
                repeat_count_14d=pattern_stats.get(pattern, {}).get("repeat_count_14d", 0),
                avg_severity=pattern_stats.get(pattern, {}).get("avg_severity", 0.5),
                last_seen_at=pattern_stats.get(pattern, {}).get("last_seen_at", now - timedelta(days=7)),
                last_trained_at=None,
                is_current_focus=(pattern == current_focus),
                now=now,
            ),
        },
    )
    
    # Store mission
    await db.behavioral_missions.insert_one(mission)
    
    return mission


async def start_mission(mission_id: str, user_id: str, db) -> Dict:
    """Start a mission session."""
    now = datetime.now(timezone.utc)
    
    # Update mission status
    await db.behavioral_missions.update_one(
        {"mission_id": mission_id, "user_id": user_id},
        {"$set": {"status": "active", "started_at": now.isoformat()}}
    )
    
    # Create session
    session_id = f"ms_{uuid.uuid4().hex[:12]}"
    session = {
        "session_id": session_id,
        "mission_id": mission_id,
        "user_id": user_id,
        "steps": [],
        "score": {
            "attempted": 0,
            "correct": 0,
            "process_points": 0,
            "result": None,
        },
        "reward_events": [],
        "started_at": now.isoformat(),
        "ended_at": None,
    }
    
    await db.mission_sessions.insert_one(session)
    
    return {"session_id": session_id, "mission_id": mission_id, "status": "started"}


async def complete_mission(
    mission_id: str,
    session_id: str,
    user_id: str,
    score: Dict,
    db,
) -> Dict:
    """Complete a mission and calculate result."""
    now = datetime.now(timezone.utc)
    
    # Get mission for threshold
    mission = await db.behavioral_missions.find_one({"mission_id": mission_id})
    if not mission:
        return {"error": "Mission not found"}
    
    threshold = mission.get("goal_success_threshold", 3)
    correct = score.get("correct", 0)
    passed = correct >= threshold
    
    # Update mission
    await db.behavioral_missions.update_one(
        {"mission_id": mission_id},
        {"$set": {
            "status": "completed",
            "completed_at": now.isoformat(),
            "result": "pass" if passed else "fail",
        }}
    )
    
    # Update session
    await db.mission_sessions.update_one(
        {"session_id": session_id},
        {"$set": {
            "ended_at": now.isoformat(),
            "score": {**score, "result": "pass" if passed else "fail"},
        }}
    )
    
    # Update focus mastery
    pattern = mission.get("focus_pattern")
    if pattern:
        mastery_id = f"fm_{user_id}_{pattern}"
        mastery_delta = 8 if passed else 3
        
        await db.focus_mastery.update_one(
            {"mastery_id": mastery_id, "user_id": user_id},
            {
                "$inc": {"mastery_score": mastery_delta},
                "$push": {"recent_mission_results": {"$each": ["pass" if passed else "fail"], "$slice": -10}},
                "$set": {"updated_at": now.isoformat(), "pattern": pattern},
            },
            upsert=True,
        )
    
    return {
        "mission_id": mission_id,
        "result": "pass" if passed else "fail",
        "score": score,
        "threshold": threshold,
        "focus_label": mission.get("focus_label"),
    }
