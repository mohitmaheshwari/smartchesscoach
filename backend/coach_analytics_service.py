"""
Coach Analytics Service - Observability for Coaching Engine

Tracks and logs:
- Theme switches
- Deep session triggers
- Behavioral maturity transitions

This provides the observability layer to understand how the coaching
engine is adapting to each user's behavior over time.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Optional, Any
from enum import Enum

logger = logging.getLogger(__name__)


class AnalyticsEventType(str, Enum):
    """Types of coaching analytics events"""
    THEME_SWITCH = "theme_switch"
    DEEP_SESSION_TRIGGERED = "deep_session_triggered"
    DEEP_SESSION_COMPLETED = "deep_session_completed"
    DEEP_SESSION_ABANDONED = "deep_session_abandoned"
    MATURITY_TRANSITION = "maturity_transition"
    COACH_STATE_INITIALIZED = "coach_state_initialized"
    GAME_COACH_SUMMARY_GENERATED = "game_coach_summary_generated"
    RESISTANCE_INCREASE = "resistance_increase"
    VELOCITY_CHANGE = "velocity_change"
    LESSON_ASSIGNED = "lesson_assigned"  # New: tracks lesson assignments for memory


class CoachAnalyticsService:
    """
    Service for logging and tracking coaching analytics events.
    
    All events are stored in the `coach_analytics` collection for analysis.
    """
    
    def __init__(self, db):
        self.db = db
    
    async def log_event(
        self,
        user_id: str,
        event_type: AnalyticsEventType,
        event_data: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Log a coaching analytics event.
        
        Args:
            user_id: The user this event belongs to
            event_type: Type of event (from AnalyticsEventType enum)
            event_data: Event-specific data
            metadata: Optional additional metadata
            
        Returns:
            The inserted event ID
        """
        event = {
            "user_id": user_id,
            "event_type": event_type.value,
            "event_data": event_data,
            "metadata": metadata or {},
            "timestamp": datetime.now(timezone.utc),
            "engine_version": "P2.3"  # Track which engine version generated this
        }
        
        result = await self.db.coach_analytics.insert_one(event)
        
        # Log to application logs as well for real-time observability
        logger.info(f"[ANALYTICS] {event_type.value} | user={user_id} | data={event_data}")
        
        return str(result.inserted_id)
    
    async def log_theme_switch(
        self,
        user_id: str,
        old_theme: str,
        new_theme: str,
        reason: str,
        confidence_before: float,
        confidence_after: float,
        games_on_old_theme: int,
        trigger_source: str = "auto"
    ) -> str:
        """
        Log a theme switch event.
        
        Args:
            old_theme: Previous theme (e.g., "ThreatVerification")
            new_theme: New theme (e.g., "ConversionDiscipline")
            reason: Why the switch happened
            confidence_before: Confidence level before switch
            confidence_after: Confidence level after switch
            games_on_old_theme: Number of games on the old theme
            trigger_source: What triggered the switch ("auto", "deep_session", "manual")
        """
        event_data = {
            "old_theme": old_theme,
            "new_theme": new_theme,
            "reason": reason,
            "confidence_before": round(confidence_before, 2),
            "confidence_after": round(confidence_after, 2),
            "games_on_old_theme": games_on_old_theme,
            "trigger_source": trigger_source
        }
        
        return await self.log_event(
            user_id=user_id,
            event_type=AnalyticsEventType.THEME_SWITCH,
            event_data=event_data
        )
    
    async def log_deep_session_triggered(
        self,
        user_id: str,
        session_id: str,
        theme: str,
        trigger_reason: str,
        games_since_last: int,
        theme_confidence: float
    ) -> str:
        """
        Log when a deep session is triggered.
        
        Args:
            session_id: The deep session ID
            theme: Current coaching theme
            trigger_reason: Why the session was triggered ("scheduled", "game_threshold", etc.)
            games_since_last: Number of games since last deep session
            theme_confidence: Current confidence level
        """
        event_data = {
            "session_id": session_id,
            "theme": theme,
            "trigger_reason": trigger_reason,
            "games_since_last": games_since_last,
            "theme_confidence": round(theme_confidence, 2)
        }
        
        return await self.log_event(
            user_id=user_id,
            event_type=AnalyticsEventType.DEEP_SESSION_TRIGGERED,
            event_data=event_data
        )
    
    async def log_deep_session_completed(
        self,
        user_id: str,
        session_id: str,
        theme: str,
        duration_seconds: int,
        reflection_answer: Optional[str],
        micro_rule_assigned: str
    ) -> str:
        """
        Log when a deep session is completed.
        """
        event_data = {
            "session_id": session_id,
            "theme": theme,
            "duration_seconds": duration_seconds,
            "has_reflection": reflection_answer is not None,
            "micro_rule_assigned": micro_rule_assigned
        }
        
        return await self.log_event(
            user_id=user_id,
            event_type=AnalyticsEventType.DEEP_SESSION_COMPLETED,
            event_data=event_data
        )
    
    async def log_deep_session_abandoned(
        self,
        user_id: str,
        session_id: str,
        theme: str,
        step_abandoned_at: int,
        time_elapsed_seconds: int
    ) -> str:
        """
        Log when a deep session is abandoned.
        """
        event_data = {
            "session_id": session_id,
            "theme": theme,
            "step_abandoned_at": step_abandoned_at,
            "time_elapsed_seconds": time_elapsed_seconds
        }
        
        return await self.log_event(
            user_id=user_id,
            event_type=AnalyticsEventType.DEEP_SESSION_ABANDONED,
            event_data=event_data
        )
    
    async def log_maturity_transition(
        self,
        user_id: str,
        old_level: str,
        new_level: str,
        old_tone: str,
        new_tone: str,
        metrics: Dict[str, float],
        reason: str
    ) -> str:
        """
        Log a behavioral maturity level transition.
        
        Args:
            old_level: Previous maturity level ("Novice", "Developing", etc.)
            new_level: New maturity level
            old_tone: Previous tone mode ("ExplainMore", "Balanced", etc.)
            new_tone: New tone mode
            metrics: The metrics that drove this transition
            reason: Human-readable reason for the transition
        """
        event_data = {
            "old_level": old_level,
            "new_level": new_level,
            "old_tone": old_tone,
            "new_tone": new_tone,
            "metrics": metrics,
            "reason": reason,
            "direction": "upgrade" if self._is_upgrade(old_level, new_level) else "downgrade"
        }
        
        return await self.log_event(
            user_id=user_id,
            event_type=AnalyticsEventType.MATURITY_TRANSITION,
            event_data=event_data
        )
    
    async def log_game_coach_summary(
        self,
        user_id: str,
        game_id: str,
        primary_issue: str,
        confidence: str,
        ties_to_theme: bool,
        current_theme: str
    ) -> str:
        """
        Log when a game coach summary is generated.
        """
        event_data = {
            "game_id": game_id,
            "primary_issue": primary_issue,
            "confidence": confidence,
            "ties_to_theme": ties_to_theme,
            "current_theme": current_theme
        }
        
        return await self.log_event(
            user_id=user_id,
            event_type=AnalyticsEventType.GAME_COACH_SUMMARY_GENERATED,
            event_data=event_data
        )
    
    async def log_resistance_increase(
        self,
        user_id: str,
        theme: str,
        old_resistance: float,
        new_resistance: float,
        consecutive_failures: int
    ) -> str:
        """
        Log when theme resistance score increases (user not applying corrections).
        """
        event_data = {
            "theme": theme,
            "old_resistance": round(old_resistance, 2),
            "new_resistance": round(new_resistance, 2),
            "resistance_delta": round(new_resistance - old_resistance, 2),
            "consecutive_failures": consecutive_failures
        }
        
        return await self.log_event(
            user_id=user_id,
            event_type=AnalyticsEventType.RESISTANCE_INCREASE,
            event_data=event_data
        )
    
    async def log_velocity_change(
        self,
        user_id: str,
        old_velocity: float,
        new_velocity: float,
        learner_type: str
    ) -> str:
        """
        Log when improvement velocity changes significantly.
        """
        event_data = {
            "old_velocity": round(old_velocity, 2),
            "new_velocity": round(new_velocity, 2),
            "velocity_delta": round(new_velocity - old_velocity, 2),
            "learner_type": learner_type,
            "direction": "improving" if new_velocity > old_velocity else "declining"
        }
        
        return await self.log_event(
            user_id=user_id,
            event_type=AnalyticsEventType.VELOCITY_CHANGE,
            event_data=event_data
        )
    
    async def log_lesson_assigned(
        self,
        user_id: str,
        game_id: str,
        lesson_key: str,
        lesson_category: str,
        lesson_intensity: float,
        narrative_strategy: str,
        selection_reason: str,
        crs_score: float
    ) -> str:
        """
        Log when a lesson is assigned to a game.
        
        This creates an audit trail for tuning thresholds and debugging
        memory behavior later.
        
        Args:
            user_id: The user this lesson is for
            game_id: The game this lesson came from
            lesson_key: Canonical lesson identifier
            lesson_category: Lesson category (threat_awareness, calculation, etc.)
            lesson_intensity: 0.0-1.0 intensity score
            narrative_strategy: Which coaching strategy was used
            selection_reason: Why this moment was selected (pattern_event, etc.)
            crs_score: CRS score of the selected moment
        """
        event_data = {
            "game_id": game_id,
            "lesson_key": lesson_key,
            "lesson_category": lesson_category,
            "lesson_intensity": round(lesson_intensity, 2),
            "narrative_strategy": narrative_strategy,
            "selection_reason": selection_reason,
            "crs_score": round(crs_score, 1)
        }
        
        return await self.log_event(
            user_id=user_id,
            event_type=AnalyticsEventType.LESSON_ASSIGNED,
            event_data=event_data
        )
    
    def _is_upgrade(self, old_level: str, new_level: str) -> bool:
        """Check if a maturity transition is an upgrade"""
        levels = ["Novice", "Developing", "Disciplined", "Advanced"]
        try:
            old_idx = levels.index(old_level)
            new_idx = levels.index(new_level)
            return new_idx > old_idx
        except ValueError:
            return False
    
    # =========================================================================
    # QUERY METHODS
    # =========================================================================
    
    async def get_user_analytics_summary(self, user_id: str, days: int = 30) -> Dict:
        """
        Get analytics summary for a user.
        
        Returns counts and trends for the last N days.
        """
        from datetime import timedelta
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        
        # Count events by type
        pipeline = [
            {"$match": {"user_id": user_id, "timestamp": {"$gte": cutoff}}},
            {"$group": {"_id": "$event_type", "count": {"$sum": 1}}}
        ]
        
        cursor = self.db.coach_analytics.aggregate(pipeline)
        counts = {}
        async for doc in cursor:
            counts[doc["_id"]] = doc["count"]
        
        # Get latest maturity transition
        latest_maturity = await self.db.coach_analytics.find_one(
            {"user_id": user_id, "event_type": AnalyticsEventType.MATURITY_TRANSITION.value},
            sort=[("timestamp", -1)]
        )
        
        # Get latest theme switch
        latest_theme_switch = await self.db.coach_analytics.find_one(
            {"user_id": user_id, "event_type": AnalyticsEventType.THEME_SWITCH.value},
            sort=[("timestamp", -1)]
        )
        
        return {
            "period_days": days,
            "event_counts": counts,
            "total_events": sum(counts.values()),
            "latest_maturity_transition": latest_maturity["event_data"] if latest_maturity else None,
            "latest_theme_switch": latest_theme_switch["event_data"] if latest_theme_switch else None
        }
    
    async def get_theme_switch_history(self, user_id: str, limit: int = 10) -> list:
        """Get recent theme switches for a user"""
        cursor = self.db.coach_analytics.find(
            {"user_id": user_id, "event_type": AnalyticsEventType.THEME_SWITCH.value},
            {"_id": 0, "event_data": 1, "timestamp": 1}
        ).sort("timestamp", -1).limit(limit)
        
        results = []
        async for doc in cursor:
            doc["event_data"]["timestamp"] = doc["timestamp"].isoformat()
            results.append(doc["event_data"])
        
        return results
    
    async def get_maturity_progression(self, user_id: str) -> list:
        """Get full maturity progression history for a user"""
        cursor = self.db.coach_analytics.find(
            {"user_id": user_id, "event_type": AnalyticsEventType.MATURITY_TRANSITION.value},
            {"_id": 0, "event_data": 1, "timestamp": 1}
        ).sort("timestamp", 1)  # Oldest first for progression view
        
        results = []
        async for doc in cursor:
            doc["event_data"]["timestamp"] = doc["timestamp"].isoformat()
            results.append(doc["event_data"])
        
        return results


# ============================================================================
# INTEGRATION HELPERS
# ============================================================================

def get_analytics_service(db) -> CoachAnalyticsService:
    """Factory function to create analytics service"""
    return CoachAnalyticsService(db)
