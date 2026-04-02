"""
Chess Brain - Lesson Selection Engine
======================================

The CORE of pedagogical decision-making.

This engine:
1. Takes a PositionInsightObject (all detected patterns)
2. Generates multiple LessonCandidates
3. Scores each candidate using weighted formula
4. Applies anti-spam controls
5. Selects the single best lesson to teach

The formula:
  Score = (Severity * 0.4) + (Clarity * 0.3) + (Player_Relevance * 0.3)
          * Priority_Multiplier * Freshness

Higher score wins. Ties broken by:
1. Teaching mode priority
2. Detector confidence
3. Random (to add variety)
"""

import logging
import uuid
from typing import Dict, List, Optional

from .schemas import (
    PositionInsightObject,
    LessonCandidate,
    SelectedLesson,
    DetectorResult,
    MistakeFingerprint,
    LessonMemory
)
from .enums import (
    TeachingMode,
    MoveQuality,
    LessonPriority,
    ExplanationType,
    TacticalPattern,
    StrategicConcept,
    GamePhase
)

logger = logging.getLogger(__name__)


# Teaching mode priority (for tie-breaking)
TEACHING_MODE_PRIORITY = {
    TeachingMode.IMMEDIATE_MISTAKE_CORRECTION: 100,
    TeachingMode.TACTICAL_PATTERN_TEACHING: 90,
    TeachingMode.HABIT_BREAKTHROUGH: 85,
    TeachingMode.ENDGAME_TECHNIQUE: 80,
    TeachingMode.STRATEGIC_CONCEPT_TEACHING: 70,
    TeachingMode.OPENING_GUIDANCE: 60,
    TeachingMode.POSITIVE_REINFORCEMENT: 50,
}


class LessonSelectionEngine:
    """
    Selects the best lesson to teach from a PositionInsightObject.
    
    Usage:
        engine = LessonSelectionEngine()
        lesson = engine.select_lesson(
            position_insight,
            fingerprint,
            lesson_memory
        )
    """
    
    def __init__(self, score_weights: Optional[Dict[str, float]] = None):
        """
        Initialize with optional custom scoring weights.
        
        Default weights:
        - severity: 0.4 (how bad was the mistake?)
        - clarity: 0.3 (how clear is this to teach?)
        - relevance: 0.3 (how relevant to this player?)
        """
        self.weights = score_weights or {
            "severity": 0.4,
            "clarity": 0.3,
            "relevance": 0.3
        }
    
    def select_lesson(
        self,
        insight: PositionInsightObject,
        fingerprint: Optional[MistakeFingerprint] = None,
        memory: Optional[LessonMemory] = None
    ) -> SelectedLesson:
        """
        Main entry point - select the best lesson for this position.
        
        Args:
            insight: Complete position analysis from detectors
            fingerprint: User's mistake profile (for relevance scoring)
            memory: Session memory (for anti-spam)
        
        Returns:
            SelectedLesson ready to render to user
        """
        # 1. Generate all lesson candidates
        candidates = self._generate_candidates(insight, fingerprint, memory)
        
        if not candidates:
            # Fallback: generate basic acknowledgment
            return self._generate_fallback_lesson(insight)
        
        # 2. Score each candidate
        scored = [(c, c.calculate_score(self.weights)) for c in candidates]
        
        # 3. Sort by score (descending), then by teaching mode priority
        scored.sort(key=lambda x: (
            x[1],  # Score
            TEACHING_MODE_PRIORITY.get(x[0].teaching_mode, 0)
        ), reverse=True)
        
        # 4. Select winner
        winner, score = scored[0]
        
        # 5. Record in memory (if provided)
        if memory and winner.source_detector:
            memory.record_taught(
                winner.source_detector,
                winner.title,
                insight.move_number
            )
        
        # 6. Build final lesson
        return self._build_selected_lesson(winner, insight, score, len(candidates))
    
    def _generate_candidates(
        self,
        insight: PositionInsightObject,
        fingerprint: Optional[MistakeFingerprint],
        memory: Optional[LessonMemory]
    ) -> List[LessonCandidate]:
        """Generate all potential lesson candidates from detections."""
        candidates = []
        
        # === MISTAKE-BASED CANDIDATES ===
        if insight.move_quality in [MoveQuality.BLUNDER, MoveQuality.MISTAKE]:
            # Always generate immediate mistake correction candidate
            candidates.append(self._create_mistake_candidate(insight, fingerprint))
            
            # Add tactical pattern if detected
            for detection in insight.tactical_detections:
                if detection.detected:
                    candidate = self._create_tactical_candidate(
                        detection, insight, fingerprint, memory
                    )
                    if candidate:
                        candidates.append(candidate)
        
        # === INACCURACY CANDIDATES (lower priority) ===
        elif insight.move_quality == MoveQuality.INACCURACY:
            # Only tactical if very clear
            for detection in insight.tactical_detections:
                if detection.detected and detection.confidence >= 0.8:
                    candidate = self._create_tactical_candidate(
                        detection, insight, fingerprint, memory
                    )
                    if candidate:
                        candidate.priority = LessonPriority.NORMAL
                        candidates.append(candidate)
        
        # === STRATEGIC CANDIDATES ===
        for detection in insight.strategic_detections:
            if detection.detected:
                candidate = self._create_strategic_candidate(
                    detection, insight, fingerprint, memory
                )
                if candidate:
                    candidates.append(candidate)
        
        # === POSITIVE REINFORCEMENT ===
        if insight.move_quality in [MoveQuality.EXCELLENT, MoveQuality.BRILLIANT]:
            candidates.append(self._create_reinforcement_candidate(insight))
        
        # === OPENING GUIDANCE ===
        if insight.in_opening_book or insight.game_phase == GamePhase.OPENING:
            candidate = self._create_opening_candidate(insight)
            if candidate:
                candidates.append(candidate)
        
        # === ENDGAME TECHNIQUE ===
        if insight.game_phase in [GamePhase.ENDGAME, GamePhase.DEEP_ENDGAME]:
            candidate = self._create_endgame_candidate(insight)
            if candidate:
                candidates.append(candidate)
        
        # === HABIT BREAKTHROUGH ===
        if fingerprint:
            candidate = self._check_breakthrough(insight, fingerprint)
            if candidate:
                candidates.append(candidate)
        
        # Apply freshness scores from memory
        if memory:
            for candidate in candidates:
                if candidate.source_detector:
                    candidate.freshness = memory.get_freshness_score(
                        candidate.source_detector,
                        insight.move_number
                    )
        
        return candidates
    
    def _create_mistake_candidate(
        self,
        insight: PositionInsightObject,
        fingerprint: Optional[MistakeFingerprint]
    ) -> LessonCandidate:
        """Create candidate for immediate mistake correction."""
        
        severity = self._calculate_severity(insight)
        clarity = 0.8  # Mistakes are generally clear to explain
        relevance = 0.5  # Default relevance
        
        if fingerprint:
            # Check if this type of mistake is recurring
            # (Would need pattern mapping here)
            relevance = 0.7  # Assume medium relevance for now
        
        return LessonCandidate(
            candidate_id=str(uuid.uuid4())[:8],
            teaching_mode=TeachingMode.IMMEDIATE_MISTAKE_CORRECTION,
            title="Move Correction",
            main_insight=f"That {insight.user_move} was {insight.move_quality.value}",
            explanation_type=ExplanationType.WHY_BAD,
            severity=severity,
            clarity=clarity,
            player_relevance=relevance,
            priority=LessonPriority.HIGH if severity > 0.7 else LessonPriority.NORMAL,
            template_key="mistake_correction",
            template_vars={
                "user_move": insight.user_move,
                "best_move": insight.best_move,
                "cp_loss": insight.cp_loss,
                "quality": insight.move_quality.value
            }
        )
    
    def _create_tactical_candidate(
        self,
        detection: DetectorResult,
        insight: PositionInsightObject,
        fingerprint: Optional[MistakeFingerprint],
        memory: Optional[LessonMemory]
    ) -> Optional[LessonCandidate]:
        """Create candidate for tactical pattern teaching."""
        
        # Check memory for anti-spam
        if memory and not memory.can_teach(detection.detector_id, insight.move_number):
            return None
        
        severity = detection.confidence * 0.9  # High confidence = high severity
        clarity = 0.85  # Tactics are clear to teach
        relevance = 0.5
        
        if fingerprint and detection.pattern_type:
            relevance = fingerprint.get_relevance_score(
                detection.pattern_type,
                detection.category or "tactical"
            )
        
        return LessonCandidate(
            candidate_id=str(uuid.uuid4())[:8],
            teaching_mode=TeachingMode.TACTICAL_PATTERN_TEACHING,
            title=self._get_pattern_title(detection.pattern_type),
            main_insight=detection.teaching_hook or f"You missed a {detection.pattern_type}",
            explanation_type=ExplanationType.PATTERN,
            severity=severity,
            clarity=clarity,
            player_relevance=relevance,
            priority=LessonPriority.HIGH,
            source_detector=detection.detector_id,
            detector_result=detection,
            template_key=f"tactical_{detection.pattern_type}",
            template_vars={
                "pattern": detection.pattern_type,
                "details": detection.details,
                "best_move": insight.best_move
            },
            socratic_question=self._get_socratic_question(detection)
        )
    
    def _create_strategic_candidate(
        self,
        detection: DetectorResult,
        insight: PositionInsightObject,
        fingerprint: Optional[MistakeFingerprint],
        memory: Optional[LessonMemory]
    ) -> Optional[LessonCandidate]:
        """Create candidate for strategic concept teaching."""
        
        if memory and not memory.can_teach(detection.detector_id, insight.move_number):
            return None
        
        severity = detection.confidence * 0.6  # Strategic = lower urgency
        clarity = 0.7  # Strategic concepts take more explanation
        relevance = 0.4
        
        if fingerprint and detection.pattern_type:
            relevance = fingerprint.get_relevance_score(
                detection.pattern_type,
                detection.category or "strategic"
            )
        
        return LessonCandidate(
            candidate_id=str(uuid.uuid4())[:8],
            teaching_mode=TeachingMode.STRATEGIC_CONCEPT_TEACHING,
            title=self._get_concept_title(detection.pattern_type),
            main_insight=detection.teaching_hook or f"Strategic point: {detection.pattern_type}",
            explanation_type=ExplanationType.CONCEPT,
            severity=severity,
            clarity=clarity,
            player_relevance=relevance,
            priority=LessonPriority.NORMAL,
            source_detector=detection.detector_id,
            detector_result=detection,
            template_key=f"strategic_{detection.pattern_type}",
            template_vars={
                "concept": detection.pattern_type,
                "details": detection.details
            }
        )
    
    def _create_reinforcement_candidate(
        self,
        insight: PositionInsightObject
    ) -> LessonCandidate:
        """Create candidate for positive reinforcement."""
        
        return LessonCandidate(
            candidate_id=str(uuid.uuid4())[:8],
            teaching_mode=TeachingMode.POSITIVE_REINFORCEMENT,
            title="Great Move!",
            main_insight=f"{insight.user_move} is excellent",
            explanation_type=ExplanationType.WHY_GOOD,
            severity=0.3,  # Low severity - not a teaching priority
            clarity=0.9,
            player_relevance=0.6,
            priority=LessonPriority.LOW,
            template_key="positive_reinforcement",
            template_vars={
                "user_move": insight.user_move,
                "quality": insight.move_quality.value
            }
        )
    
    def _create_opening_candidate(
        self,
        insight: PositionInsightObject
    ) -> Optional[LessonCandidate]:
        """Create candidate for opening guidance."""
        
        if not insight.opening_name:
            return None
        
        return LessonCandidate(
            candidate_id=str(uuid.uuid4())[:8],
            teaching_mode=TeachingMode.OPENING_GUIDANCE,
            title=f"Opening: {insight.opening_name}",
            main_insight=f"This is the {insight.opening_name}",
            explanation_type=ExplanationType.CONCEPT,
            severity=0.4,
            clarity=0.8,
            player_relevance=0.5,
            priority=LessonPriority.NORMAL,
            template_key="opening_guidance",
            template_vars={
                "opening_name": insight.opening_name,
                "opening_key": insight.opening_key,
                "is_trap": insight.is_known_trap,
                "trap_name": insight.trap_name
            }
        )
    
    def _create_endgame_candidate(
        self,
        insight: PositionInsightObject
    ) -> Optional[LessonCandidate]:
        """Create candidate for endgame technique teaching."""
        
        # Only if there's something specific to teach
        if not insight.strategic_detections:
            return None
        
        return LessonCandidate(
            candidate_id=str(uuid.uuid4())[:8],
            teaching_mode=TeachingMode.ENDGAME_TECHNIQUE,
            title="Endgame Technique",
            main_insight="Key endgame principles apply here",
            explanation_type=ExplanationType.CONCEPT,
            severity=0.5,
            clarity=0.7,
            player_relevance=0.6,
            priority=LessonPriority.NORMAL,
            template_key="endgame_technique",
            template_vars={
                "phase": insight.game_phase.value,
                "phase_percent": insight.phase_percent
            }
        )
    
    def _check_breakthrough(
        self,
        insight: PositionInsightObject,
        fingerprint: MistakeFingerprint
    ) -> Optional[LessonCandidate]:
        """Check if user avoided a recurring mistake - celebration time!"""
        
        # This would need to compare current position type
        # with fingerprint to detect avoided patterns
        # V1: Basic implementation
        
        return None
    
    def _calculate_severity(self, insight: PositionInsightObject) -> float:
        """Calculate severity score based on move quality and cp loss."""
        base_severity = {
            MoveQuality.BLUNDER: 1.0,
            MoveQuality.MISTAKE: 0.8,
            MoveQuality.INACCURACY: 0.5,
            MoveQuality.GOOD: 0.2,
            MoveQuality.EXCELLENT: 0.1,
            MoveQuality.BRILLIANT: 0.1
        }
        
        severity = base_severity.get(insight.move_quality, 0.5)
        
        # Adjust by cp loss
        if insight.cp_loss > 500:
            severity = min(1.0, severity + 0.2)
        elif insight.cp_loss > 300:
            severity = min(1.0, severity + 0.1)
        
        # Adjust if was winning
        if insight.was_winning and insight.move_quality in [MoveQuality.BLUNDER, MoveQuality.MISTAKE]:
            severity = min(1.0, severity + 0.1)
        
        return severity
    
    def _get_pattern_title(self, pattern_type: str) -> str:
        """Get human-readable title for a tactical pattern."""
        titles = {
            TacticalPattern.MISSED_FORK.value: "Fork Attack",
            TacticalPattern.MISSED_PIN.value: "Pin Pattern",
            TacticalPattern.MISSED_SKEWER.value: "Skewer Attack",
            TacticalPattern.MISSED_DISCOVERY.value: "Discovered Attack",
            TacticalPattern.MISSED_BACK_RANK.value: "Back Rank Threat",
            TacticalPattern.MISSED_MATE.value: "Checkmate Pattern",
            TacticalPattern.HANGING_PIECE.value: "Hanging Piece",
            TacticalPattern.TRAPPED_PIECE.value: "Trapped Piece",
        }
        return titles.get(pattern_type, pattern_type.replace("_", " ").title())
    
    def _get_concept_title(self, concept_type: str) -> str:
        """Get human-readable title for a strategic concept."""
        titles = {
            StrategicConcept.ISOLATED_PAWN.value: "Isolated Pawn",
            StrategicConcept.PASSED_PAWN.value: "Passed Pawn",
            StrategicConcept.KNIGHT_OUTPOST.value: "Knight Outpost",
            StrategicConcept.ROOK_ACTIVITY.value: "Rook Activity",
            StrategicConcept.KING_SAFETY.value: "King Safety",
        }
        return titles.get(concept_type, concept_type.replace("_", " ").title())
    
    def _get_socratic_question(self, detection: DetectorResult) -> Optional[str]:
        """Generate Socratic question for a detection."""
        questions = {
            TacticalPattern.MISSED_FORK.value: "Do you see which piece could attack two targets at once?",
            TacticalPattern.MISSED_PIN.value: "Can you find a way to restrict a piece?",
            TacticalPattern.HANGING_PIECE.value: "Is everything defended after your move?",
            TacticalPattern.MISSED_MATE.value: "Is there a forcing sequence here?",
        }
        return questions.get(detection.pattern_type)
    
    def _build_selected_lesson(
        self,
        candidate: LessonCandidate,
        insight: PositionInsightObject,
        score: float,
        candidate_count: int
    ) -> SelectedLesson:
        """Build the final SelectedLesson from the winning candidate."""
        
        # Build explanation from template (V1: basic generation)
        explanation = self._render_explanation(candidate, insight)
        why_section = self._render_why_section(candidate, insight)
        next_idea = self._render_next_idea(candidate, insight)
        
        # Build encouragement based on teaching mode
        encouragement = self._get_encouragement(candidate.teaching_mode, insight.move_quality)
        
        # Get highlight squares from detector result
        highlight_squares = []
        if candidate.detector_result:
            highlight_squares = candidate.detector_result.key_squares
        
        # Quality badge
        quality_badge = self._get_quality_badge(insight.move_quality)
        
        return SelectedLesson(
            teaching_mode=candidate.teaching_mode,
            title=candidate.title,
            main_insight=candidate.main_insight,
            explanation=explanation,
            why_section=why_section,
            next_idea=next_idea,
            socratic_question=candidate.socratic_question,
            better_move=insight.best_move if insight.user_move != insight.best_move else None,
            better_move_explanation=self._get_better_move_explanation(insight) if insight.user_move != insight.best_move else None,
            highlight_squares=highlight_squares,
            quality_badge=quality_badge,
            encouragement=encouragement,
            score=score,
            candidate_count=candidate_count
        )
    
    def _render_explanation(
        self,
        candidate: LessonCandidate,
        insight: PositionInsightObject
    ) -> str:
        """Render the main explanation text."""
        
        # V1: Template-based generation
        # In V2: Use template library with variations
        
        if candidate.teaching_mode == TeachingMode.IMMEDIATE_MISTAKE_CORRECTION:
            cp_loss = abs(insight.cp_loss)
            if cp_loss > 300:
                return f"This {insight.user_move} loses significant advantage. Better was {insight.best_move}."
            else:
                return f"While {insight.user_move} is playable, {insight.best_move} was more accurate."
        
        elif candidate.teaching_mode == TeachingMode.TACTICAL_PATTERN_TEACHING:
            if candidate.detector_result:
                hook = candidate.detector_result.teaching_hook
                if hook:
                    return hook
            return f"There was a tactical opportunity with {insight.best_move}."
        
        elif candidate.teaching_mode == TeachingMode.POSITIVE_REINFORCEMENT:
            return f"Excellent choice! {insight.user_move} is strong here."
        
        elif candidate.teaching_mode == TeachingMode.OPENING_GUIDANCE:
            return f"We're in the {insight.opening_name}."
        
        return candidate.main_insight
    
    def _render_why_section(
        self,
        candidate: LessonCandidate,
        insight: PositionInsightObject
    ) -> Optional[str]:
        """Render the optional 'Why?' section."""
        
        if candidate.teaching_mode in [TeachingMode.IMMEDIATE_MISTAKE_CORRECTION,
                                       TeachingMode.TACTICAL_PATTERN_TEACHING]:
            if insight.threats_after:
                return f"After your move, opponent threatens: {', '.join(insight.threats_after[:2])}"
        
        return None
    
    def _render_next_idea(
        self,
        candidate: LessonCandidate,
        insight: PositionInsightObject
    ) -> Optional[str]:
        """Render the 'What to think about next' hint."""
        
        if candidate.teaching_mode == TeachingMode.TACTICAL_PATTERN_TEACHING:
            return "Always check for forcing moves: checks, captures, attacks."
        
        if candidate.teaching_mode == TeachingMode.STRATEGIC_CONCEPT_TEACHING:
            return "Think about your long-term plan."
        
        return None
    
    def _get_encouragement(
        self,
        mode: TeachingMode,
        quality: MoveQuality
    ) -> Optional[str]:
        """Get appropriate encouragement text."""
        
        if quality == MoveQuality.EXCELLENT:
            return "Great chess!"
        elif quality == MoveQuality.BRILLIANT:
            return "Brilliant! You're playing like a pro!"
        elif quality in [MoveQuality.BLUNDER, MoveQuality.MISTAKE]:
            return "Don't worry - we learn from these moments."
        
        return None
    
    def _get_quality_badge(self, quality: MoveQuality) -> Optional[str]:
        """Get quality badge text for UI."""
        badges = {
            MoveQuality.BRILLIANT: "Brilliant!",
            MoveQuality.EXCELLENT: "Excellent",
            MoveQuality.GOOD: "Good",
            MoveQuality.INACCURACY: "Inaccuracy",
            MoveQuality.MISTAKE: "Mistake",
            MoveQuality.BLUNDER: "Blunder"
        }
        return badges.get(quality)
    
    def _get_better_move_explanation(self, insight: PositionInsightObject) -> str:
        """Generate explanation for why the best move is better."""
        
        if insight.pv_after_best:
            pv = " ".join(insight.pv_after_best[:3])
            return f"With {insight.best_move}, the idea is {pv}..."
        
        return f"{insight.best_move} maintains better position."
    
    def _generate_fallback_lesson(self, insight: PositionInsightObject) -> SelectedLesson:
        """Generate a basic lesson when no candidates are available."""
        
        if insight.move_quality in [MoveQuality.EXCELLENT, MoveQuality.BRILLIANT]:
            return SelectedLesson(
                teaching_mode=TeachingMode.POSITIVE_REINFORCEMENT,
                title="Good Move",
                main_insight=f"{insight.user_move} is solid",
                explanation=f"Good choice! {insight.user_move} keeps you in the game.",
                encouragement="Keep playing confidently!",
                quality_badge=self._get_quality_badge(insight.move_quality),
                score=0.3,
                candidate_count=0
            )
        
        if insight.move_quality == MoveQuality.GOOD:
            return SelectedLesson(
                teaching_mode=TeachingMode.POSITIVE_REINFORCEMENT,
                title="Solid Move",
                main_insight=f"{insight.user_move} is reasonable",
                explanation=f"That's a sensible move. Let's see how your opponent responds.",
                quality_badge=self._get_quality_badge(insight.move_quality),
                score=0.25,
                candidate_count=0
            )
        
        return SelectedLesson(
            teaching_mode=TeachingMode.IMMEDIATE_MISTAKE_CORRECTION,
            title="Move Analysis",
            main_insight=f"You played {insight.user_move}",
            explanation="Let's see how the game develops.",
            score=0.1,
            candidate_count=0
        )


# ==============================================================================
# CONVENIENCE FUNCTIONS
# ==============================================================================

def select_best_lesson(
    insight: PositionInsightObject,
    fingerprint: Optional[MistakeFingerprint] = None,
    memory: Optional[LessonMemory] = None
) -> SelectedLesson:
    """
    Convenience function to select the best lesson.
    
    Usage:
        lesson = select_best_lesson(position_insight)
    """
    engine = LessonSelectionEngine()
    return engine.select_lesson(insight, fingerprint, memory)
