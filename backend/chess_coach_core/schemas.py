"""
Chess Coach Core Schemas
========================

The canonical data structures for the pedagogy engine.

Key Principles:
1. All chess truth is deterministic (no LLM decisions)
2. Teaching mode is assigned at candidate creation
3. Every detection carries confidence
4. Single lesson per moment
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum
from datetime import datetime


# =============================================================================
# ENUMS
# =============================================================================

class GamePhase(str, Enum):
    """Determined by material + position, not just move number"""
    OPENING = "opening"
    MIDDLEGAME = "middlegame"
    ENDGAME = "endgame"


class TeachingMode(str, Enum):
    """The 7 teaching modes - assigned at candidate creation"""
    IMMEDIATE_MISTAKE_CORRECTION = "immediate_mistake_correction"
    TACTICAL_PATTERN_TEACHING = "tactical_pattern_teaching"
    STRATEGIC_CONCEPT_TEACHING = "strategic_concept_teaching"
    OPENING_GUIDANCE = "opening_guidance"
    TRAP_ALERT = "trap_alert"
    REINFORCEMENT = "reinforcement"
    ENDGAME_PRINCIPLE = "endgame_principle"


class DetectorClass(str, Enum):
    """3 classes of detectors"""
    TACTICAL = "tactical"      # Immediate concrete punishments
    STRATEGIC = "strategic"    # Quiet positional truths
    META = "meta"              # Selection helpers (teachability)


class LessonCategory(str, Enum):
    """Broad lesson categories"""
    TACTICS = "tactics"
    STRATEGY = "strategy"
    OPENING = "opening"
    ENDGAME = "endgame"
    DEFENSE = "defense"
    CALCULATION = "calculation"


# =============================================================================
# DETECTOR RESULT
# =============================================================================

@dataclass
class DetectorResult:
    """Result from a single detector"""
    detector_name: str
    detected: bool
    confidence: float  # 0.0 to 1.0 - CRITICAL for lesson selection
    detector_class: DetectorClass
    details: Dict[str, Any] = field(default_factory=dict)
    
    # For tactical detectors - the concrete threat/opportunity
    square: Optional[str] = None
    pieces_involved: List[str] = field(default_factory=list)
    winning_move: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            "detector_name": self.detector_name,
            "detected": self.detected,
            "confidence": round(self.confidence, 2),
            "detector_class": self.detector_class.value,
            "details": self.details,
            "square": self.square,
            "pieces_involved": self.pieces_involved,
            "winning_move": self.winning_move,
        }


# =============================================================================
# POSITION INSIGHT OBJECT
# =============================================================================

@dataclass
class PositionInsight:
    """
    Single source of chess facts for a position.
    NO opinions, NO coaching text - just deterministic truth.
    """
    # Position data
    fen: str
    move_number: int
    side_to_move: str  # "white" or "black"
    game_phase: GamePhase
    
    # Move data
    played_move: Optional[str] = None
    best_move: Optional[str] = None
    principal_variation: List[str] = field(default_factory=list)
    
    # Evaluation
    eval_before_cp: int = 0
    eval_after_cp: int = 0
    eval_loss_cp: int = 0
    quality_label: str = "unknown"  # "brilliant", "good", "inaccuracy", "mistake", "blunder"
    
    # Opening context
    opening_eco: Optional[str] = None
    opening_name: Optional[str] = None
    in_opening_book: bool = False
    
    # Detected patterns (from detector registry)
    tactical_detections: List[DetectorResult] = field(default_factory=list)
    strategic_detections: List[DetectorResult] = field(default_factory=list)
    meta_detections: List[DetectorResult] = field(default_factory=list)
    
    # Material
    material_balance: int = 0  # Positive = white ahead
    white_material: int = 0
    black_material: int = 0
    
    # King safety
    white_king_safety: str = "safe"  # "safe", "slightly_exposed", "dangerous"
    black_king_safety: str = "safe"
    
    # Trap context
    known_trap_available: bool = False
    known_trap_risk: bool = False
    trap_name: Optional[str] = None
    
    def get_all_detections(self) -> List[DetectorResult]:
        """Get all positive detections"""
        all_detections = []
        for d in self.tactical_detections + self.strategic_detections + self.meta_detections:
            if d.detected:
                all_detections.append(d)
        return all_detections
    
    def get_highest_confidence_tactical(self) -> Optional[DetectorResult]:
        """Get the tactical detection with highest confidence"""
        positives = [d for d in self.tactical_detections if d.detected]
        if not positives:
            return None
        return max(positives, key=lambda x: x.confidence)
    
    def is_forcing_position(self) -> bool:
        """Check if meta detector flagged as forcing"""
        for d in self.meta_detections:
            if d.detector_name == "is_forcing_position" and d.detected:
                return True
        return False
    
    def is_good_teaching_moment(self) -> bool:
        """Check if meta detector flagged as teachable"""
        for d in self.meta_detections:
            if d.detector_name == "is_single_clear_lesson" and d.detected:
                return True
        return False
    
    def to_dict(self) -> Dict:
        return {
            "fen": self.fen,
            "move_number": self.move_number,
            "side_to_move": self.side_to_move,
            "game_phase": self.game_phase.value,
            "played_move": self.played_move,
            "best_move": self.best_move,
            "principal_variation": self.principal_variation,
            "eval_before_cp": self.eval_before_cp,
            "eval_after_cp": self.eval_after_cp,
            "eval_loss_cp": self.eval_loss_cp,
            "quality_label": self.quality_label,
            "opening_eco": self.opening_eco,
            "opening_name": self.opening_name,
            "in_opening_book": self.in_opening_book,
            "tactical_detections": [d.to_dict() for d in self.tactical_detections if d.detected],
            "strategic_detections": [d.to_dict() for d in self.strategic_detections if d.detected],
            "meta_detections": [d.to_dict() for d in self.meta_detections if d.detected],
            "material_balance": self.material_balance,
            "white_king_safety": self.white_king_safety,
            "black_king_safety": self.black_king_safety,
            "known_trap_available": self.known_trap_available,
            "known_trap_risk": self.known_trap_risk,
            "trap_name": self.trap_name,
        }


# =============================================================================
# LESSON CANDIDATE
# =============================================================================

@dataclass
class LessonCandidate:
    """
    A potential lesson to teach.
    Teaching mode is assigned HERE at creation, not later.
    """
    # Identity
    lesson_id: str
    lesson_key: str  # Canonical key for tracking (e.g., "missed_fork")
    lesson_category: LessonCategory
    teaching_mode: TeachingMode  # ASSIGNED AT CREATION
    
    # Source detection
    source_detector: str
    detector_confidence: float
    
    # Scoring inputs (for lesson selection engine)
    severity: float = 0.0        # How costly (0-1)
    clarity: float = 0.0         # How clearly explainable (0-1)
    player_relevance: float = 0.0  # How relevant to this user (0-1)
    teachability: float = 0.0    # Can user absorb this now (0-1)
    recurrence: float = 0.0      # Has this repeated enough (0-1)
    novelty: float = 0.0         # Under-taught recently (0-1)
    phase_relevance: float = 0.0 # Fits current game phase (0-1)
    curriculum_fit: float = 0.0  # Aligns with learning path (0-1)
    
    # Final score (computed by selection engine)
    raw_score: float = 0.0
    confidence_adjusted_score: float = 0.0
    final_score: float = 0.0  # After penalties
    
    # Penalties applied
    repetition_penalty: float = 0.0
    overload_penalty: float = 0.0
    
    # Payload for explanation builder
    payload: Dict[str, Any] = field(default_factory=dict)
    
    # UI hints
    requires_interrupt: bool = False
    supports_visual_overlay: bool = False
    template_key: str = ""
    
    def compute_raw_score(self) -> float:
        """Weighted scoring formula"""
        self.raw_score = (
            self.severity * 0.28 +
            self.clarity * 0.17 +
            self.player_relevance * 0.16 +
            self.teachability * 0.14 +
            self.recurrence * 0.10 +
            self.novelty * 0.05 +
            self.phase_relevance * 0.05 +
            self.curriculum_fit * 0.05
        )
        return self.raw_score
    
    def compute_final_score(self) -> float:
        """Apply confidence and penalties"""
        self.confidence_adjusted_score = self.raw_score * self.detector_confidence
        self.final_score = self.confidence_adjusted_score - (
            self.repetition_penalty * 0.10 +
            self.overload_penalty * 0.08
        )
        return self.final_score
    
    def to_dict(self) -> Dict:
        return {
            "lesson_id": self.lesson_id,
            "lesson_key": self.lesson_key,
            "lesson_category": self.lesson_category.value,
            "teaching_mode": self.teaching_mode.value,
            "source_detector": self.source_detector,
            "detector_confidence": round(self.detector_confidence, 2),
            "severity": round(self.severity, 2),
            "clarity": round(self.clarity, 2),
            "player_relevance": round(self.player_relevance, 2),
            "teachability": round(self.teachability, 2),
            "final_score": round(self.final_score, 3),
            "requires_interrupt": self.requires_interrupt,
            "template_key": self.template_key,
            "payload": self.payload,
        }


# =============================================================================
# LESSON MEMORY (Short-Term - Within Game)
# =============================================================================

@dataclass
class LessonMemory:
    """
    Short-term coaching context within a game.
    Prevents spam, enables escalation, tracks interrupts.
    """
    session_id: str
    
    # Recent lessons (for anti-spam)
    recent_lessons: List[str] = field(default_factory=list)  # Last N lesson_keys
    recent_modes: List[str] = field(default_factory=list)    # Last N teaching modes
    recent_themes: List[str] = field(default_factory=list)   # Last N themes
    
    # Limits
    interrupts_this_game: int = 0
    max_interrupts: int = 6
    
    # Cooldowns
    same_theme_limit: int = 2
    same_mode_limit: int = 3
    cooldown_moves: int = 4
    last_interrupt_move: int = 0
    
    # Escalation tracking (for "you keep missing forks")
    theme_occurrence_count: Dict[str, int] = field(default_factory=dict)
    
    def can_interrupt(self, current_move: int) -> bool:
        """Check if we can interrupt now"""
        if self.interrupts_this_game >= self.max_interrupts:
            return False
        if current_move - self.last_interrupt_move < self.cooldown_moves:
            return False
        return True
    
    def get_repetition_penalty(self, lesson_key: str, theme: str, mode: str) -> float:
        """Calculate penalty for repetition"""
        penalty = 0.0
        
        # Same theme recently
        if theme in self.recent_themes[-self.same_theme_limit:]:
            penalty += 0.25
        
        # Same mode recently
        if mode in self.recent_modes[-self.same_mode_limit:]:
            penalty += 0.15
        
        # Exact same lesson
        if lesson_key in self.recent_lessons[-3:]:
            penalty += 0.35
        
        return penalty
    
    def record_lesson(self, lesson_key: str, theme: str, mode: str, move_number: int, was_interrupt: bool):
        """Record a lesson was given"""
        self.recent_lessons.append(lesson_key)
        self.recent_themes.append(theme)
        self.recent_modes.append(mode)
        
        # Keep last 10
        self.recent_lessons = self.recent_lessons[-10:]
        self.recent_themes = self.recent_themes[-10:]
        self.recent_modes = self.recent_modes[-10:]
        
        # Track occurrence for escalation
        self.theme_occurrence_count[theme] = self.theme_occurrence_count.get(theme, 0) + 1
        
        if was_interrupt:
            self.interrupts_this_game += 1
            self.last_interrupt_move = move_number
    
    def get_escalation_level(self, theme: str) -> int:
        """How many times has this theme appeared? For escalating coaching."""
        return self.theme_occurrence_count.get(theme, 0)
    
    def to_dict(self) -> Dict:
        return {
            "session_id": self.session_id,
            "recent_lessons": self.recent_lessons,
            "recent_themes": self.recent_themes,
            "interrupts_this_game": self.interrupts_this_game,
            "theme_occurrence_count": self.theme_occurrence_count,
        }


# =============================================================================
# PLAYER CONTEXT (For Lesson Selection)
# =============================================================================

@dataclass
class PlayerContext:
    """Player-specific context for lesson selection"""
    player_id: str
    rating: int
    experience_band: str  # "beginner", "intermediate", "advanced"
    
    # From mistake fingerprint
    top_tactical_weakness: Optional[str] = None
    top_strategic_weakness: Optional[str] = None
    top_behavioral_weakness: Optional[str] = None
    
    # Strengths
    strengths: List[str] = field(default_factory=list)
    
    # Preferences
    verbosity_preference: str = "normal"  # "minimal", "normal", "detailed"
    
    # Learning stage
    current_focus: Optional[str] = None
    concept_ceiling: str = "basic_tactics"  # What concepts they can absorb
    
    def can_learn_concept(self, concept_level: str) -> bool:
        """Check if player can absorb this concept level"""
        levels = ["basic_tactics", "advanced_tactics", "basic_strategy", "advanced_strategy"]
        try:
            player_level = levels.index(self.concept_ceiling)
            concept_idx = levels.index(concept_level)
            return concept_idx <= player_level
        except ValueError:
            return True
