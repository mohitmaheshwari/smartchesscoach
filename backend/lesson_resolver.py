"""
Lesson Resolver - Canonical Lesson Identification

This module is the SINGLE SOURCE OF TRUTH for lesson resolution.
It sits between CRS selection and narrative engine:

    CRS selection → lesson_resolver.resolve(...) → narrative_engine

PHILOSOPHY:
- ONE lesson per game (not multiple)
- lesson_key is DETERMINISTIC (never derived from text)
- lesson_key is NEVER nullable for corrective strategies
- For positive coaching: explicitly "positive_stability"

The resolver produces:
- lesson_key: Canonical identifier (stable, never changes with wording)
- lesson_category: Broader grouping (for UI/filtering)
- lesson_intensity: 0.0-1.0 (how critical this lesson is)

This enables:
- Memory cooldowns
- Cross-game pattern tracking
- Analytics and dashboards
"""

from typing import Optional, Tuple, Dict
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# LESSON CATEGORIES
# =============================================================================

class LessonCategory(str, Enum):
    """Broad lesson categories for UI grouping"""
    THREAT_AWARENESS = "threat_awareness"      # Opponent threats
    CALCULATION = "calculation"                # Depth and accuracy
    PIECE_SAFETY = "piece_safety"              # Hanging pieces, safety
    POSITION_CONTROL = "position_control"      # Turning points, structure
    CONVERSION = "conversion"                  # When ahead, simplification
    DEFENSE = "defense"                        # Defensive thinking
    DISCIPLINE = "discipline"                  # Positive habits
    PATTERN_RECOGNITION = "pattern_recognition"# Recurring patterns


# =============================================================================
# LESSON KEY DEFINITIONS - Single Source of Truth
# =============================================================================

# Format: (cognitive_gap, selection_reason) → (lesson_key, category, base_intensity)
LESSON_REGISTRY: Dict[Tuple[Optional[str], str], Tuple[str, LessonCategory, float]] = {
    # ===========================================
    # THREAT AWARENESS LESSONS
    # ===========================================
    ("THREAT_BLINDNESS", "pattern_event"): ("verify_opponent_threats", LessonCategory.THREAT_AWARENESS, 0.8),
    ("THREAT_BLINDNESS", "tactical_error"): ("verify_opponent_threats", LessonCategory.THREAT_AWARENESS, 0.7),
    ("threat_blindness", "pattern_event"): ("verify_opponent_threats", LessonCategory.THREAT_AWARENESS, 0.8),
    ("threat_blindness", "tactical_error"): ("verify_opponent_threats", LessonCategory.THREAT_AWARENESS, 0.7),
    
    # ===========================================
    # CALCULATION LESSONS
    # ===========================================
    ("TACTICAL_OVERSIGHT", "pattern_event"): ("calculate_forcing_moves", LessonCategory.CALCULATION, 0.85),
    ("TACTICAL_OVERSIGHT", "tactical_error"): ("calculate_forcing_moves", LessonCategory.CALCULATION, 0.75),
    ("tactical_oversight", "pattern_event"): ("calculate_forcing_moves", LessonCategory.CALCULATION, 0.85),
    ("tactical_oversight", "tactical_error"): ("calculate_forcing_moves", LessonCategory.CALCULATION, 0.75),
    
    ("CALCULATION_DEPTH", "pattern_event"): ("calculate_one_move_deeper", LessonCategory.CALCULATION, 0.8),
    ("CALCULATION_DEPTH", "tactical_error"): ("calculate_one_move_deeper", LessonCategory.CALCULATION, 0.7),
    ("calculation_depth", "pattern_event"): ("calculate_one_move_deeper", LessonCategory.CALCULATION, 0.8),
    ("calculation_depth", "tactical_error"): ("calculate_one_move_deeper", LessonCategory.CALCULATION, 0.7),
    
    # ===========================================
    # PIECE SAFETY LESSONS
    # ===========================================
    ("HANGING_PIECE_BLINDNESS", "pattern_event"): ("check_piece_safety", LessonCategory.PIECE_SAFETY, 0.85),
    ("HANGING_PIECE_BLINDNESS", "tactical_error"): ("check_piece_safety", LessonCategory.PIECE_SAFETY, 0.75),
    ("hanging_piece_blindness", "pattern_event"): ("check_piece_safety", LessonCategory.PIECE_SAFETY, 0.85),
    ("hanging_piece_blindness", "tactical_error"): ("check_piece_safety", LessonCategory.PIECE_SAFETY, 0.75),
    
    # ===========================================
    # POSITION CONTROL LESSONS
    # ===========================================
    ("POSITIONAL_MISREAD", "turning_point"): ("reassess_position_after_changes", LessonCategory.POSITION_CONTROL, 0.75),
    ("POSITIONAL_MISREAD", "pattern_event"): ("reassess_position_after_changes", LessonCategory.POSITION_CONTROL, 0.7),
    ("positional_misread", "turning_point"): ("reassess_position_after_changes", LessonCategory.POSITION_CONTROL, 0.75),
    ("positional_misread", "pattern_event"): ("reassess_position_after_changes", LessonCategory.POSITION_CONTROL, 0.7),
    
    # Generic turning point
    (None, "turning_point"): ("maintain_position_control", LessonCategory.POSITION_CONTROL, 0.65),
    ("", "turning_point"): ("maintain_position_control", LessonCategory.POSITION_CONTROL, 0.65),
    
    # ===========================================
    # CONVERSION LESSONS (When Ahead)
    # ===========================================
    ("PREMATURE_ACTION", "turning_point"): ("patience_when_ahead", LessonCategory.CONVERSION, 0.8),
    ("PREMATURE_ACTION", "pattern_event"): ("patience_when_ahead", LessonCategory.CONVERSION, 0.85),
    ("premature_action", "turning_point"): ("patience_when_ahead", LessonCategory.CONVERSION, 0.8),
    ("premature_action", "pattern_event"): ("patience_when_ahead", LessonCategory.CONVERSION, 0.85),
    
    (None, "advantage_squander"): ("simplify_when_winning", LessonCategory.CONVERSION, 0.75),
    ("", "advantage_squander"): ("simplify_when_winning", LessonCategory.CONVERSION, 0.75),
    
    # ===========================================
    # DEFENSE LESSONS
    # ===========================================
    ("DEFENSIVE_LAPSE", "tactical_error"): ("prioritize_defense", LessonCategory.DEFENSE, 0.75),
    ("DEFENSIVE_LAPSE", "pattern_event"): ("prioritize_defense", LessonCategory.DEFENSE, 0.8),
    ("defensive_lapse", "tactical_error"): ("prioritize_defense", LessonCategory.DEFENSE, 0.75),
    ("defensive_lapse", "pattern_event"): ("prioritize_defense", LessonCategory.DEFENSE, 0.8),
    
    # ===========================================
    # TACTICAL FINISHES
    # ===========================================
    (None, "missed_mate"): ("check_forcing_finishes", LessonCategory.CALCULATION, 0.9),
    ("", "missed_mate"): ("check_forcing_finishes", LessonCategory.CALCULATION, 0.9),
    
    # ===========================================
    # POSITIVE COACHING (Discipline Reinforcement)
    # ===========================================
    (None, "positive_coaching"): ("positive_stability", LessonCategory.DISCIPLINE, 0.3),
    ("", "positive_coaching"): ("positive_stability", LessonCategory.DISCIPLINE, 0.3),
    (None, "no_critical_moves"): ("positive_stability", LessonCategory.DISCIPLINE, 0.2),
    ("", "no_critical_moves"): ("positive_stability", LessonCategory.DISCIPLINE, 0.2),
}

# Fallback mapping when no specific match found
FALLBACK_LESSONS: Dict[str, Tuple[str, LessonCategory, float]] = {
    "pattern_event": ("recognize_thinking_patterns", LessonCategory.PATTERN_RECOGNITION, 0.6),
    "tactical_error": ("verify_before_committing", LessonCategory.CALCULATION, 0.65),
    "turning_point": ("critical_moment_awareness", LessonCategory.POSITION_CONTROL, 0.6),
    "missed_mate": ("check_forcing_finishes", LessonCategory.CALCULATION, 0.9),
    "advantage_squander": ("simplify_when_winning", LessonCategory.CONVERSION, 0.7),
    "positive_coaching": ("positive_stability", LessonCategory.DISCIPLINE, 0.3),
    "no_critical_moves": ("positive_stability", LessonCategory.DISCIPLINE, 0.2),
}


# =============================================================================
# LESSON METADATA
# =============================================================================

LESSON_DESCRIPTIONS = {
    "verify_opponent_threats": "Check opponent's forcing moves before committing",
    "calculate_forcing_moves": "Calculate all forcing sequences completely",
    "calculate_one_move_deeper": "Push calculation one move further than comfortable",
    "check_piece_safety": "Verify piece safety before and after moves",
    "reassess_position_after_changes": "Re-evaluate position after exchanges or structure changes",
    "patience_when_ahead": "Avoid rushing when holding an advantage",
    "prioritize_defense": "Address defensive needs before attacking",
    "check_forcing_finishes": "Look for forcing wins in advantageous positions",
    "maintain_position_control": "Keep position stable at critical moments",
    "simplify_when_winning": "Trade pieces, not pawns, when ahead",
    "recognize_thinking_patterns": "Notice recurring decision patterns",
    "verify_before_committing": "Double-check before executing plans",
    "critical_moment_awareness": "Recognize when positions become critical",
    "positive_stability": "Maintain disciplined thinking process",
}

# Cooldown in games (how many games before repeating this lesson)
LESSON_COOLDOWNS = {
    "verify_opponent_threats": 3,
    "calculate_forcing_moves": 3,
    "calculate_one_move_deeper": 4,
    "check_piece_safety": 3,
    "reassess_position_after_changes": 4,
    "patience_when_ahead": 3,
    "prioritize_defense": 3,
    "check_forcing_finishes": 2,  # Important - can repeat sooner
    "maintain_position_control": 4,
    "simplify_when_winning": 3,
    "recognize_thinking_patterns": 5,
    "verify_before_committing": 3,
    "critical_moment_awareness": 4,
    "positive_stability": 5,  # Don't over-praise
}


# =============================================================================
# LESSON RESULT - Immutable Output
# =============================================================================

@dataclass(frozen=True)
class LessonResolution:
    """
    Immutable result from lesson resolution.
    
    This is what gets persisted to GameCoachSummary.
    """
    lesson_key: str
    lesson_category: str
    lesson_intensity: float
    description: str
    cooldown_games: int
    
    def to_dict(self) -> Dict:
        return {
            "lesson_key": self.lesson_key,
            "lesson_category": self.lesson_category,
            "lesson_intensity": round(self.lesson_intensity, 2),
            "description": self.description,
            "cooldown_games": self.cooldown_games
        }


# =============================================================================
# PUBLIC API - resolve()
# =============================================================================

def resolve(
    cognitive_gap: Optional[str],
    selection_reason: str,
    crs_score: float = 0.0,
    is_positive_game: bool = False
) -> LessonResolution:
    """
    Resolve lesson from coaching selection data.
    
    This is the ONLY entry point for lesson resolution.
    
    Args:
        cognitive_gap: The identified cognitive gap (can be None)
        selection_reason: Why this moment was selected (e.g., "pattern_event", "tactical_error")
        crs_score: CRS score for intensity adjustment
        is_positive_game: Whether this is a positive coaching scenario
        
    Returns:
        LessonResolution with lesson_key, category, intensity, and metadata
        
    GUARANTEES:
        - lesson_key is NEVER None or empty for corrective strategies
        - lesson_key is "positive_stability" for positive coaching
        - intensity is 0.0-1.0
    """
    # Handle positive coaching explicitly
    if is_positive_game or selection_reason in ("positive_coaching", "no_critical_moves"):
        return LessonResolution(
            lesson_key="positive_stability",
            lesson_category=LessonCategory.DISCIPLINE.value,
            lesson_intensity=0.3,
            description=LESSON_DESCRIPTIONS["positive_stability"],
            cooldown_games=LESSON_COOLDOWNS["positive_stability"]
        )
    
    # Normalize inputs
    gap = cognitive_gap.strip() if cognitive_gap else None
    reason = selection_reason.strip().lower() if selection_reason else "tactical_error"
    
    # Build lookup key variants
    lookup_keys = [
        (gap, reason),
        (gap.upper() if gap else None, reason),
        (gap.lower() if gap else None, reason),
        (None, reason),
        ("", reason),
    ]
    
    # Try to find match
    result = None
    for key in lookup_keys:
        if key in LESSON_REGISTRY:
            result = LESSON_REGISTRY[key]
            break
    
    # Fallback
    if not result:
        if reason in FALLBACK_LESSONS:
            result = FALLBACK_LESSONS[reason]
        else:
            # Ultimate fallback - corrective always gets a lesson
            result = ("verify_before_committing", LessonCategory.CALCULATION, 0.65)
            logger.warning(f"Using ultimate fallback for gap={gap}, reason={reason}")
    
    lesson_key, category, base_intensity = result
    
    # Adjust intensity based on CRS score
    # Higher CRS = more critical = higher intensity
    if crs_score > 0:
        intensity_adjustment = min(0.2, crs_score / 500)
        final_intensity = min(1.0, base_intensity + intensity_adjustment)
    else:
        final_intensity = base_intensity
    
    return LessonResolution(
        lesson_key=lesson_key,
        lesson_category=category.value if isinstance(category, LessonCategory) else category,
        lesson_intensity=round(final_intensity, 2),
        description=LESSON_DESCRIPTIONS.get(lesson_key, "Apply careful thinking"),
        cooldown_games=LESSON_COOLDOWNS.get(lesson_key, 3)
    )


def get_lesson_cooldown(lesson_key: str) -> int:
    """Get cooldown period in games for a lesson"""
    return LESSON_COOLDOWNS.get(lesson_key, 3)


def get_lesson_description(lesson_key: str) -> str:
    """Get human-readable description of a lesson"""
    return LESSON_DESCRIPTIONS.get(lesson_key, "Apply careful thinking")


def get_lesson_category(lesson_key: str) -> str:
    """Get category for a lesson key"""
    for (_, _), (key, cat, _) in LESSON_REGISTRY.items():
        if key == lesson_key:
            return cat.value if isinstance(cat, LessonCategory) else cat
    return LessonCategory.CALCULATION.value


# =============================================================================
# TESTING UTILITIES
# =============================================================================

def validate_lesson_key(lesson_key: str) -> bool:
    """Check if a lesson key is valid"""
    return lesson_key in LESSON_DESCRIPTIONS


def get_all_lesson_keys() -> list:
    """Get all valid lesson keys"""
    return list(LESSON_DESCRIPTIONS.keys())
