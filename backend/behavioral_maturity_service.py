"""
Behavioral Maturity Layer

Makes coaching adapt based on:
- User experience level (NOT rating)
- Pattern recurrence
- Responsiveness to past corrections
- Improvement velocity

This is what makes ChessGuru feel intelligent instead of scripted.

Maturity Levels:
- NOVICE: More explanation, fewer questions, clear step-by-step
- DEVELOPING: Balanced A + C, one discovery question
- DISCIPLINED: Ask more, explain less, slightly challenge
- ADVANCED: Mostly discovery, rare lecture, challenge depth
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timezone, timedelta
from enum import Enum


class BehavioralMaturity(str, Enum):
    """User's behavioral maturity level - NOT based on rating"""
    NOVICE = "Novice"
    DEVELOPING = "Developing"
    DISCIPLINED = "Disciplined"
    ADVANCED = "Advanced"


class CoachToneMode(str, Enum):
    """How the coach should frame responses"""
    EXPLAIN_MORE = "ExplainMore"
    BALANCED = "Balanced"
    CHALLENGE_MORE = "ChallengeMore"


# Maturity to tone mapping
MATURITY_TONE_MAP = {
    BehavioralMaturity.NOVICE: CoachToneMode.EXPLAIN_MORE,
    BehavioralMaturity.DEVELOPING: CoachToneMode.BALANCED,
    BehavioralMaturity.DISCIPLINED: CoachToneMode.CHALLENGE_MORE,
    BehavioralMaturity.ADVANCED: CoachToneMode.CHALLENGE_MORE,
}


@dataclass
class MaturityMetrics:
    """Metrics used to calculate behavioral maturity"""
    theme_improvement_delta: float  # % change in theme mistakes
    repeated_issue_frequency: float  # How often same issue repeats
    cpr_stability: float  # 0-1, how stable is CPR over time
    deep_session_completion_rate: float  # % of started sessions completed
    drill_completion_rate: float  # % of assigned drills completed
    games_analyzed: int
    correct_reflection_rate: float  # How often reflections show understanding
    
    def to_dict(self) -> Dict:
        return {
            "theme_improvement_delta": round(self.theme_improvement_delta, 2),
            "repeated_issue_frequency": round(self.repeated_issue_frequency, 2),
            "cpr_stability": round(self.cpr_stability, 2),
            "deep_session_completion_rate": round(self.deep_session_completion_rate, 2),
            "drill_completion_rate": round(self.drill_completion_rate, 2),
            "games_analyzed": self.games_analyzed,
            "correct_reflection_rate": round(self.correct_reflection_rate, 2)
        }


@dataclass
class ToneConfig:
    """Configuration for how coach should speak based on maturity"""
    emotion_intensity: str  # "direct_firm" | "calm" | "observational" | "minimal"
    max_lines: int  # Max lines in micro coaching
    use_questions: bool  # Whether to ask discovery questions
    explanation_depth: str  # "detailed" | "moderate" | "brief" | "minimal"
    challenge_level: str  # "none" | "light" | "moderate" | "strong"
    
    def to_dict(self) -> Dict:
        return {
            "emotion_intensity": self.emotion_intensity,
            "max_lines": self.max_lines,
            "use_questions": self.use_questions,
            "explanation_depth": self.explanation_depth,
            "challenge_level": self.challenge_level
        }


# Tone configurations by maturity level
TONE_CONFIGS = {
    BehavioralMaturity.NOVICE: ToneConfig(
        emotion_intensity="direct_firm",
        max_lines=4,
        use_questions=False,
        explanation_depth="detailed",
        challenge_level="none"
    ),
    BehavioralMaturity.DEVELOPING: ToneConfig(
        emotion_intensity="calm",
        max_lines=3,
        use_questions=True,  # Optional
        explanation_depth="moderate",
        challenge_level="light"
    ),
    BehavioralMaturity.DISCIPLINED: ToneConfig(
        emotion_intensity="observational",
        max_lines=2,
        use_questions=True,
        explanation_depth="brief",
        challenge_level="moderate"
    ),
    BehavioralMaturity.ADVANCED: ToneConfig(
        emotion_intensity="minimal",
        max_lines=2,
        use_questions=True,
        explanation_depth="minimal",
        challenge_level="strong"
    )
}


# ============================================================================
# TONE TEMPLATES BY MATURITY
# ============================================================================

# Same mistake, different framing
TONE_TEMPLATES = {
    "threat_scan_failure": {
        BehavioralMaturity.NOVICE: {
            "emotion": "Before attacking, you must check opponent forcing moves. You skipped this step.",
            "explanation": "Every time you want to attack, stop and ask: 'What checks, captures, or threats do they have?' This is non-negotiable.",
            "cta": "Practice this rule in your next game."
        },
        BehavioralMaturity.DEVELOPING: {
            "emotion": "You attacked quickly here.",
            "explanation": "What forcing moves did you check before committing?",
            "cta": "Next time, pause and scan."
        },
        BehavioralMaturity.DISCIPLINED: {
            "emotion": "You paused longer this time. That's progress.",
            "explanation": "Now refine the scan. Did you check all forcing replies?",
            "cta": "Keep building this habit."
        },
        BehavioralMaturity.ADVANCED: {
            "emotion": "Would this attack survive their best defensive resource?",
            "explanation": "",
            "cta": ""
        }
    },
    "rushed_when_ahead": {
        BehavioralMaturity.NOVICE: {
            "emotion": "You were winning, then you rushed. This is a pattern we need to break.",
            "explanation": "When ahead, there is no need to attack. Trade pieces, improve your worst piece, simplify. The win will come.",
            "cta": "In your next winning position, slow down deliberately."
        },
        BehavioralMaturity.DEVELOPING: {
            "emotion": "Victory felt close, and something shifted.",
            "explanation": "What was the rush? The position was already good.",
            "cta": "Practice patience in winning positions."
        },
        BehavioralMaturity.DISCIPLINED: {
            "emotion": "You held longer this time before committing.",
            "explanation": "Could you have simplified instead of attacking?",
            "cta": "Refine the conversion technique."
        },
        BehavioralMaturity.ADVANCED: {
            "emotion": "Was the attack necessary, or was simplification cleaner?",
            "explanation": "",
            "cta": ""
        }
    },
    "calculation_stopped_early": {
        BehavioralMaturity.NOVICE: {
            "emotion": "You saw part of the idea but stopped calculating too early.",
            "explanation": "When you see a promising move, force yourself to check one more move. What is their best reply? What do you play after that?",
            "cta": "Adopt the rule: 'One more move.'"
        },
        BehavioralMaturity.DEVELOPING: {
            "emotion": "The idea was right. The calculation stopped short.",
            "explanation": "Did you check their strongest reply?",
            "cta": "Build the habit of going one move deeper."
        },
        BehavioralMaturity.DISCIPLINED: {
            "emotion": "You calculated further this time.",
            "explanation": "Where did the line get uncomfortable? That's where to push.",
            "cta": "Keep extending your calculation horizon."
        },
        BehavioralMaturity.ADVANCED: {
            "emotion": "What was the critical defensive resource you might have missed?",
            "explanation": "",
            "cta": ""
        }
    },
    "piece_left_undefended": {
        BehavioralMaturity.NOVICE: {
            "emotion": "That piece was hanging. You moved without checking if it was safe.",
            "explanation": "Before every piece move, ask: 'Is my piece safe on this square?' Count attackers vs defenders.",
            "cta": "Make this check automatic."
        },
        BehavioralMaturity.DEVELOPING: {
            "emotion": "A piece was left undefended.",
            "explanation": "Did you count attackers vs defenders?",
            "cta": "Build the safety habit."
        },
        BehavioralMaturity.DISCIPLINED: {
            "emotion": "You're catching more of these. This one slipped through.",
            "explanation": "What distracted you from the safety check?",
            "cta": "Stay consistent."
        },
        BehavioralMaturity.ADVANCED: {
            "emotion": "What made this piece look safe when it wasn't?",
            "explanation": "",
            "cta": ""
        }
    }
}


# Deep session adaptation by maturity
DEEP_SESSION_CONFIG = {
    BehavioralMaturity.NOVICE: {
        "screens": 6,  # All screens
        "explanation_density": "full",
        "reflection_questions": 1,
        "skip_screens": []
    },
    BehavioralMaturity.DEVELOPING: {
        "screens": 6,
        "explanation_density": "moderate",
        "reflection_questions": 1,
        "skip_screens": []
    },
    BehavioralMaturity.DISCIPLINED: {
        "screens": 5,  # Skip long explanation
        "explanation_density": "brief",
        "reflection_questions": 1,
        "skip_screens": [4]  # Skip detailed teaching
    },
    BehavioralMaturity.ADVANCED: {
        "screens": 4,  # Shorter session
        "explanation_density": "minimal",
        "reflection_questions": 1,
        "skip_screens": [3, 4]  # Skip mirror and detailed teaching
    }
}


class BehavioralMaturityService:
    """
    Service for calculating and applying behavioral maturity.
    
    This adapts coaching based on user behavior, not rating.
    """
    
    # Configuration
    MIN_GAMES_FOR_ASSESSMENT = 5
    MIN_GAMES_BEFORE_LEVEL_CHANGE = 10
    SMOOTHING_WINDOW = 10  # Games to smooth over
    
    # Thresholds
    IMPROVEMENT_THRESHOLD_DISCIPLINED = 0.2  # 20% improvement
    IMPROVEMENT_THRESHOLD_DEVELOPING = 0.05  # 5% improvement
    REPEATED_ISSUE_THRESHOLD_NOVICE = 0.5  # 50% repetition rate
    CPR_STABILITY_THRESHOLD = 0.7
    
    def __init__(self, db):
        self.db = db
    
    async def calculate_maturity(self, user_id: str) -> Tuple[BehavioralMaturity, MaturityMetrics]:
        """
        Calculate user's behavioral maturity level.
        
        Run after every 5 analyzed games.
        Uses smoothing over last 10 games.
        """
        metrics = await self._gather_metrics(user_id)
        
        if metrics.games_analyzed < self.MIN_GAMES_FOR_ASSESSMENT:
            return BehavioralMaturity.NOVICE, metrics
        
        # Calculate maturity based on metrics
        maturity = self._determine_maturity(metrics)
        
        # Apply smoothing - don't change too aggressively
        current_maturity = await self._get_current_maturity(user_id)
        maturity = self._smooth_transition(current_maturity, maturity, metrics)
        
        return maturity, metrics
    
    async def _gather_metrics(self, user_id: str) -> MaturityMetrics:
        """Gather all metrics needed for maturity calculation"""
        
        # Get recent game summaries
        cursor = self.db.game_coach_summaries.find(
            {"user_id": user_id}
        ).sort("generated_at", -1).limit(self.SMOOTHING_WINDOW)
        
        summaries = []
        async for doc in cursor:
            summaries.append(doc)
        
        games_analyzed = len(summaries)
        
        if games_analyzed == 0:
            return MaturityMetrics(
                theme_improvement_delta=0.0,
                repeated_issue_frequency=0.0,
                cpr_stability=0.0,
                deep_session_completion_rate=0.0,
                drill_completion_rate=0.0,
                games_analyzed=0,
                correct_reflection_rate=0.0
            )
        
        # Calculate theme improvement delta
        theme_improvement = await self._calculate_theme_improvement(user_id, summaries)
        
        # Calculate repeated issue frequency
        repeated_frequency = self._calculate_repeated_issues(summaries)
        
        # Calculate CPR stability
        cpr_stability = await self._calculate_cpr_stability(user_id)
        
        # Calculate deep session completion rate
        deep_completion = await self._calculate_deep_session_completion(user_id)
        
        # Calculate drill completion rate (placeholder - would need drill tracking)
        drill_completion = 0.5  # Default middle value
        
        # Calculate correct reflection rate
        reflection_rate = await self._calculate_reflection_quality(user_id)
        
        return MaturityMetrics(
            theme_improvement_delta=theme_improvement,
            repeated_issue_frequency=repeated_frequency,
            cpr_stability=cpr_stability,
            deep_session_completion_rate=deep_completion,
            drill_completion_rate=drill_completion,
            games_analyzed=games_analyzed,
            correct_reflection_rate=reflection_rate
        )
    
    async def _calculate_theme_improvement(self, user_id: str, summaries: List) -> float:
        """Calculate improvement in theme mistakes"""
        if len(summaries) < 4:
            return 0.0
        
        mid = len(summaries) // 2
        recent = summaries[:mid]
        older = summaries[mid:]
        
        recent_theme_issues = sum(1 for s in recent if s.get("ties_to_active_theme"))
        older_theme_issues = sum(1 for s in older if s.get("ties_to_active_theme"))
        
        if older_theme_issues == 0:
            return 0.0
        
        # Positive = improvement (fewer issues)
        delta = (older_theme_issues - recent_theme_issues) / older_theme_issues
        return delta
    
    def _calculate_repeated_issues(self, summaries: List) -> float:
        """Calculate how often same primary issue repeats"""
        if len(summaries) < 2:
            return 0.0
        
        issues = [s.get("primary_issue") for s in summaries if s.get("primary_issue")]
        if not issues:
            return 0.0
        
        # Count consecutive repetitions
        repetitions = 0
        for i in range(1, len(issues)):
            if issues[i] == issues[i-1]:
                repetitions += 1
        
        return repetitions / (len(issues) - 1) if len(issues) > 1 else 0.0
    
    async def _calculate_cpr_stability(self, user_id: str) -> float:
        """Calculate CPR stability over recent sessions"""
        # Get CPR history
        cursor = self.db.coach_sessions.find(
            {"user_id": user_id, "cpr_score": {"$exists": True}}
        ).sort("created_at", -1).limit(10)
        
        cpr_scores = []
        async for doc in cursor:
            if doc.get("cpr_score"):
                cpr_scores.append(doc["cpr_score"])
        
        if len(cpr_scores) < 3:
            return 0.5  # Not enough data
        
        # Calculate variance
        mean = sum(cpr_scores) / len(cpr_scores)
        variance = sum((x - mean) ** 2 for x in cpr_scores) / len(cpr_scores)
        
        # Convert to stability score (lower variance = higher stability)
        # Normalize assuming max reasonable variance is ~400 (20 point swings)
        stability = max(0, 1 - (variance / 400))
        return stability
    
    async def _calculate_deep_session_completion(self, user_id: str) -> float:
        """Calculate rate of deep session completion"""
        total = await self.db.deep_sessions.count_documents({"user_id": user_id})
        completed = await self.db.deep_sessions.count_documents({
            "user_id": user_id, 
            "completed": True
        })
        
        if total == 0:
            return 0.5  # No sessions yet
        
        return completed / total
    
    async def _calculate_reflection_quality(self, user_id: str) -> float:
        """Calculate quality of reflection answers in deep sessions"""
        cursor = self.db.deep_sessions.find({
            "user_id": user_id,
            "completed": True,
            "reflection_answer": {"$exists": True}
        }).limit(5)
        
        # For now, any answer is considered "correct"
        # In future, could analyze answer quality
        count = 0
        async for doc in cursor:
            if doc.get("reflection_answer"):
                count += 1
        
        return min(1.0, count / 3) if count > 0 else 0.5
    
    def _determine_maturity(self, metrics: MaturityMetrics) -> BehavioralMaturity:
        """Determine maturity level from metrics"""
        
        # ADVANCED: High improvement, stable CPR, low repetition
        if (metrics.theme_improvement_delta > self.IMPROVEMENT_THRESHOLD_DISCIPLINED and
            metrics.cpr_stability > self.CPR_STABILITY_THRESHOLD and
            metrics.repeated_issue_frequency < 0.2):
            return BehavioralMaturity.ADVANCED
        
        # DISCIPLINED: Good improvement, reasonable stability
        if (metrics.theme_improvement_delta > self.IMPROVEMENT_THRESHOLD_DISCIPLINED and
            metrics.cpr_stability > 0.5):
            return BehavioralMaturity.DISCIPLINED
        
        # DEVELOPING: Some improvement, trying
        if (metrics.theme_improvement_delta > self.IMPROVEMENT_THRESHOLD_DEVELOPING or
            metrics.deep_session_completion_rate > 0.5):
            return BehavioralMaturity.DEVELOPING
        
        # NOVICE: High repetition or no improvement
        if (metrics.repeated_issue_frequency > self.REPEATED_ISSUE_THRESHOLD_NOVICE or
            metrics.theme_improvement_delta <= 0):
            return BehavioralMaturity.NOVICE
        
        # Default to DEVELOPING
        return BehavioralMaturity.DEVELOPING
    
    async def _get_current_maturity(self, user_id: str) -> Optional[BehavioralMaturity]:
        """Get user's current maturity from CoachState"""
        doc = await self.db.coach_states.find_one({"user_id": user_id})
        if doc and doc.get("behavioral_maturity_level"):
            try:
                return BehavioralMaturity(doc["behavioral_maturity_level"])
            except:
                pass
        return None
    
    def _smooth_transition(
        self, 
        current: Optional[BehavioralMaturity], 
        new: BehavioralMaturity,
        metrics: MaturityMetrics
    ) -> BehavioralMaturity:
        """Apply smoothing to prevent rapid maturity changes"""
        
        if current is None:
            return new
        
        # Don't allow jumping more than one level at a time
        levels = [
            BehavioralMaturity.NOVICE,
            BehavioralMaturity.DEVELOPING,
            BehavioralMaturity.DISCIPLINED,
            BehavioralMaturity.ADVANCED
        ]
        
        current_idx = levels.index(current)
        new_idx = levels.index(new)
        
        # Max one level change
        if new_idx > current_idx + 1:
            return levels[current_idx + 1]
        if new_idx < current_idx - 1:
            return levels[current_idx - 1]
        
        # Don't downgrade unless metrics clearly support it
        if new_idx < current_idx:
            if metrics.repeated_issue_frequency < 0.4 and metrics.theme_improvement_delta > -0.1:
                return current  # Keep current level
        
        return new
    
    def get_tone_config(self, maturity: BehavioralMaturity) -> ToneConfig:
        """Get tone configuration for maturity level"""
        return TONE_CONFIGS.get(maturity, TONE_CONFIGS[BehavioralMaturity.DEVELOPING])
    
    def get_deep_session_config(self, maturity: BehavioralMaturity) -> Dict:
        """Get deep session configuration for maturity level"""
        return DEEP_SESSION_CONFIG.get(maturity, DEEP_SESSION_CONFIG[BehavioralMaturity.DEVELOPING])
    
    def adapt_message(
        self, 
        issue_type: str, 
        maturity: BehavioralMaturity,
        base_emotion: str = None,
        base_explanation: str = None
    ) -> Dict[str, str]:
        """
        Adapt a coaching message based on maturity level.
        
        Same engine, different framing.
        """
        # Try to get template for this issue type
        issue_key = issue_type.lower().replace(" ", "_")
        templates = TONE_TEMPLATES.get(issue_key)
        
        if templates and maturity in templates:
            return templates[maturity]
        
        # Fall back to tone-based adaptation
        config = self.get_tone_config(maturity)
        
        adapted = {
            "emotion": base_emotion or "",
            "explanation": base_explanation or "",
            "cta": ""
        }
        
        # Adjust based on config
        if config.explanation_depth == "minimal":
            adapted["explanation"] = ""
        elif config.explanation_depth == "brief" and len(adapted["explanation"]) > 100:
            adapted["explanation"] = adapted["explanation"][:100] + "..."
        
        if config.use_questions and adapted["emotion"]:
            # Convert statement to question if possible
            if not adapted["emotion"].endswith("?"):
                adapted["emotion"] = adapted["emotion"].rstrip(".") + "?"
        
        return adapted
    
    async def calculate_theme_resistance(self, user_id: str) -> float:
        """
        Calculate theme resistance score.
        
        High score = issue persists despite coaching.
        This signals need for increased firmness.
        """
        # Get deep sessions for user
        sessions = await self.db.deep_sessions.find({
            "user_id": user_id,
            "completed": True
        }).sort("completed_at", -1).limit(3).to_list(length=3)
        
        if len(sessions) < 2:
            return 0.0
        
        # Check if same theme issues persist after sessions
        themes_addressed = set(s.get("theme") for s in sessions)
        
        # Get recent game summaries
        recent_summaries = await self.db.game_coach_summaries.find({
            "user_id": user_id
        }).sort("generated_at", -1).limit(5).to_list(length=5)
        
        # Count issues that match themes we've addressed
        persistent_issues = 0
        for s in recent_summaries:
            if s.get("ties_to_active_theme"):
                persistent_issues += 1
        
        # Resistance = issues persisting despite intervention
        resistance = persistent_issues / len(recent_summaries) if recent_summaries else 0.0
        return resistance
    
    async def calculate_improvement_velocity(self, user_id: str) -> float:
        """
        Calculate how fast user is improving.
        
        High velocity = rapid improvement
        Low velocity = slow/no improvement
        """
        # Get CPR scores over time
        cursor = self.db.coach_sessions.find({
            "user_id": user_id,
            "cpr_score": {"$exists": True}
        }).sort("created_at", 1).limit(20)
        
        cpr_scores = []
        async for doc in cursor:
            if doc.get("cpr_score"):
                cpr_scores.append(doc["cpr_score"])
        
        if len(cpr_scores) < 4:
            return 0.0
        
        # Calculate trend (simple linear regression slope)
        n = len(cpr_scores)
        x_mean = n / 2
        y_mean = sum(cpr_scores) / n
        
        numerator = sum((i - x_mean) * (y - y_mean) for i, y in enumerate(cpr_scores))
        denominator = sum((i - x_mean) ** 2 for i in range(n))
        
        if denominator == 0:
            return 0.0
        
        slope = numerator / denominator
        
        # Normalize: slope of 0.5 CPR per game = 0.5 velocity
        velocity = min(1.0, max(-1.0, slope))
        return velocity
    
    async def update_coach_state_maturity(self, user_id: str) -> Dict:
        """
        Update CoachState with maturity information.
        
        Should be called after every 5 analyzed games.
        """
        # Get current state for comparison
        current_state = await self.db.coach_states.find_one({"user_id": user_id})
        old_level = current_state.get("behavioral_maturity_level", "Novice") if current_state else "Novice"
        old_tone = current_state.get("coach_tone_mode", "ExplainMore") if current_state else "ExplainMore"
        old_velocity = current_state.get("improvement_velocity", 0.0) if current_state else 0.0
        
        # Calculate new maturity
        maturity, metrics = await self.calculate_maturity(user_id)
        tone_mode = MATURITY_TONE_MAP.get(maturity, CoachToneMode.BALANCED)
        
        resistance = await self.calculate_theme_resistance(user_id)
        velocity = await self.calculate_improvement_velocity(user_id)
        
        # Update CoachState
        await self.db.coach_states.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "behavioral_maturity_level": maturity.value,
                    "coach_tone_mode": tone_mode.value,
                    "theme_resistance_score": round(resistance, 2),
                    "improvement_velocity": round(velocity, 2),
                    "maturity_metrics": metrics.to_dict(),
                    "maturity_updated_at": datetime.now(timezone.utc).isoformat()
                }
            },
            upsert=True
        )
        
        # Log analytics events for transitions
        from coach_analytics_service import get_analytics_service
        analytics = get_analytics_service(self.db)
        
        # Log maturity transition if changed
        if maturity.value != old_level:
            reason = self._get_transition_reason(metrics, old_level, maturity.value)
            await analytics.log_maturity_transition(
                user_id=user_id,
                old_level=old_level,
                new_level=maturity.value,
                old_tone=old_tone,
                new_tone=tone_mode.value,
                metrics=metrics.to_dict(),
                reason=reason
            )
        
        # Log velocity change if significant (> 0.1 delta)
        if abs(velocity - old_velocity) > 0.1:
            learner_type = self._get_learner_type(velocity)
            await analytics.log_velocity_change(
                user_id=user_id,
                old_velocity=old_velocity,
                new_velocity=velocity,
                learner_type=learner_type
            )
        
        return {
            "maturity_level": maturity.value,
            "tone_mode": tone_mode.value,
            "theme_resistance": round(resistance, 2),
            "improvement_velocity": round(velocity, 2),
            "metrics": metrics.to_dict(),
            "transitioned": maturity.value != old_level
        }
    
    def _get_transition_reason(self, metrics: MaturityMetrics, old_level: str, new_level: str) -> str:
        """Generate a human-readable reason for maturity transition"""
        if new_level == "Advanced":
            return f"Consistent improvement ({metrics.theme_improvement_delta:.0%}) with stable performance"
        elif new_level == "Disciplined":
            return f"Improvement velocity up ({metrics.theme_improvement_delta:.0%}), fewer repeated issues"
        elif new_level == "Developing":
            return "Making progress, applying corrections more consistently"
        else:  # Novice
            return f"Issues recurring ({metrics.repeated_issue_frequency:.0%}), need more foundational work"
    
    def _get_learner_type(self, velocity: float) -> str:
        """Get learner type label from velocity"""
        if velocity >= 0.75:
            return "FAST_ADAPTER"
        elif velocity >= 0.55:
            return "STEADY"
        elif velocity >= 0.35:
            return "TRYING_BUT_STUCK"
        else:
            return "NOT_APPLYING"


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_adapted_coaching_message(
    issue_type: str,
    maturity: BehavioralMaturity,
    base_emotion: str,
    base_explanation: str
) -> Dict[str, str]:
    """
    Quick helper to adapt a coaching message.
    
    Example:
        message = get_adapted_coaching_message(
            "threat_scan_failure",
            BehavioralMaturity.DISCIPLINED,
            "You missed their threat.",
            "Check forcing moves before attacking."
        )
    """
    service = BehavioralMaturityService(None)  # DB not needed for this
    return service.adapt_message(issue_type, maturity, base_emotion, base_explanation)


def should_use_discovery_question(maturity: BehavioralMaturity) -> bool:
    """Should the coach ask a discovery question?"""
    config = TONE_CONFIGS.get(maturity, TONE_CONFIGS[BehavioralMaturity.DEVELOPING])
    return config.use_questions


def get_explanation_depth(maturity: BehavioralMaturity) -> str:
    """Get explanation depth for maturity level"""
    config = TONE_CONFIGS.get(maturity, TONE_CONFIGS[BehavioralMaturity.DEVELOPING])
    return config.explanation_depth
