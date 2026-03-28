"""
Lesson Key Mapping - Canonical identifiers for coaching lessons

Maps (cognitive_gap, selection_reason) → lesson_key

This enables:
- Deterministic lesson tracking
- Cooldown management
- Cross-game pattern detection
- Memory continuity

Lesson keys are stable identifiers that don't change with text variations.
"""

from typing import Optional, Tuple


# =============================================================================
# LESSON KEY DEFINITIONS
# =============================================================================

# Format: (cognitive_gap, selection_reason) → lesson_key
# cognitive_gap can be None for non-pattern selections

LESSON_KEY_MAP = {
    # Threat-related lessons
    ("THREAT_BLINDNESS", "pattern_event"): "verify_opponent_threats",
    ("THREAT_BLINDNESS", "tactical_error"): "verify_opponent_threats",
    ("threat_blindness", "pattern_event"): "verify_opponent_threats",
    ("threat_blindness", "tactical_error"): "verify_opponent_threats",
    
    # Tactical oversight lessons
    ("TACTICAL_OVERSIGHT", "pattern_event"): "calculate_forcing_moves",
    ("TACTICAL_OVERSIGHT", "tactical_error"): "calculate_forcing_moves",
    ("tactical_oversight", "pattern_event"): "calculate_forcing_moves",
    ("tactical_oversight", "tactical_error"): "calculate_forcing_moves",
    
    # Calculation depth lessons
    ("CALCULATION_DEPTH", "pattern_event"): "calculate_one_move_deeper",
    ("CALCULATION_DEPTH", "tactical_error"): "calculate_one_move_deeper",
    ("calculation_depth", "pattern_event"): "calculate_one_move_deeper",
    ("calculation_depth", "tactical_error"): "calculate_one_move_deeper",
    
    # Hanging piece lessons
    ("HANGING_PIECE_BLINDNESS", "pattern_event"): "check_piece_safety",
    ("HANGING_PIECE_BLINDNESS", "tactical_error"): "check_piece_safety",
    ("hanging_piece_blindness", "pattern_event"): "check_piece_safety",
    ("hanging_piece_blindness", "tactical_error"): "check_piece_safety",
    
    # Positional lessons
    ("POSITIONAL_MISREAD", "turning_point"): "reassess_position_after_changes",
    ("POSITIONAL_MISREAD", "pattern_event"): "reassess_position_after_changes",
    ("positional_misread", "turning_point"): "reassess_position_after_changes",
    ("positional_misread", "pattern_event"): "reassess_position_after_changes",
    
    # Premature action lessons
    ("PREMATURE_ACTION", "turning_point"): "patience_when_ahead",
    ("PREMATURE_ACTION", "pattern_event"): "patience_when_ahead",
    ("premature_action", "turning_point"): "patience_when_ahead",
    ("premature_action", "pattern_event"): "patience_when_ahead",
    
    # Defensive lessons
    ("DEFENSIVE_LAPSE", "tactical_error"): "prioritize_defense",
    ("DEFENSIVE_LAPSE", "pattern_event"): "prioritize_defense",
    ("defensive_lapse", "tactical_error"): "prioritize_defense",
    ("defensive_lapse", "pattern_event"): "prioritize_defense",
    
    # Missed mate
    (None, "missed_mate"): "check_forcing_finishes",
    ("", "missed_mate"): "check_forcing_finishes",
    
    # Turning point (generic)
    (None, "turning_point"): "maintain_position_control",
    ("", "turning_point"): "maintain_position_control",
    
    # Advantage squander
    (None, "advantage_squander"): "simplify_when_winning",
    ("", "advantage_squander"): "simplify_when_winning",
}

# Fallback mapping when no specific match found
FALLBACK_LESSON_KEYS = {
    "pattern_event": "recognize_thinking_patterns",
    "tactical_error": "verify_before_committing",
    "turning_point": "critical_moment_awareness",
    "missed_mate": "check_forcing_finishes",
    "advantage_squander": "simplify_when_winning",
    "positive_coaching": "maintain_discipline",
    "no_critical_moves": "maintain_discipline",
}


# =============================================================================
# LESSON METADATA
# =============================================================================

# Human-readable descriptions for each lesson
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
    "maintain_discipline": "Continue applying consistent thinking process",
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
    "maintain_discipline": 5,
}


# =============================================================================
# PUBLIC API
# =============================================================================

def derive_lesson_key(
    cognitive_gap: Optional[str],
    selection_reason: str
) -> str:
    """
    Derive canonical lesson_key from cognitive_gap and selection_reason.
    
    Args:
        cognitive_gap: The identified cognitive gap (can be None)
        selection_reason: Why this moment was selected for coaching
        
    Returns:
        Canonical lesson key string
    """
    # Normalize inputs
    gap = cognitive_gap.strip() if cognitive_gap else None
    reason = selection_reason.strip().lower() if selection_reason else ""
    
    # Try exact match
    key = (gap, reason)
    if key in LESSON_KEY_MAP:
        return LESSON_KEY_MAP[key]
    
    # Try with uppercase gap
    if gap:
        key_upper = (gap.upper(), reason)
        if key_upper in LESSON_KEY_MAP:
            return LESSON_KEY_MAP[key_upper]
        
        key_lower = (gap.lower(), reason)
        if key_lower in LESSON_KEY_MAP:
            return LESSON_KEY_MAP[key_lower]
    
    # Try None gap
    key_none = (None, reason)
    if key_none in LESSON_KEY_MAP:
        return LESSON_KEY_MAP[key_none]
    
    # Fallback by selection reason
    if reason in FALLBACK_LESSON_KEYS:
        return FALLBACK_LESSON_KEYS[reason]
    
    # Ultimate fallback
    return "verify_before_committing"


def get_lesson_cooldown(lesson_key: str) -> int:
    """Get cooldown period in games for a lesson"""
    return LESSON_COOLDOWNS.get(lesson_key, 3)


def get_lesson_description(lesson_key: str) -> str:
    """Get human-readable description of a lesson"""
    return LESSON_DESCRIPTIONS.get(lesson_key, "Apply careful thinking")
