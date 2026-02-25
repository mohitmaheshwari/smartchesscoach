"""
Reflection Engine Constants & Enums
===================================
Version: v1
All reflection-related constants in one place.
Frontend reads from backend payload - no hardcoded values in React.
"""

from enum import Enum
from typing import List, Dict

# ============================================
# VERSION TRACKING
# ============================================
REFLECT_RULES_VERSION = "v1"
MISTAKE_CATEGORY_VERSION = "v1"

# ============================================
# INTENT OPTIONS (ordered for UI)
# Rating-adaptive: Different questions for different skill levels
# ============================================
class Intent(str, Enum):
    # Basic intents (all ratings)
    ATTACK = "attack"
    DEFEND = "defend"
    IMPROVE_PIECES = "improve_pieces"
    TRADE_SIMPLIFY = "trade_simplify"
    WIN_MATERIAL = "win_material"
    AVOID_THREAT = "avoid_threat"
    TIME_PANIC = "time_panic"
    NOT_SURE = "not_sure"
    
    # Advanced intents (1000+ only)
    PREPARE_ATTACK = "prepare_attack"  # Setting up for later
    PROPHYLAXIS = "prophylaxis"  # Preventing opponent's plan
    IMPROVE_WORST_PIECE = "improve_worst_piece"
    CREATE_WEAKNESS = "create_weakness"
    CONVERT_ADVANTAGE = "convert_advantage"

INTENT_LABELS = {
    Intent.ATTACK: "Attack",
    Intent.DEFEND: "Defend",
    Intent.IMPROVE_PIECES: "Develop / Improve piece",
    Intent.TRADE_SIMPLIFY: "Simplify / Trade",
    Intent.WIN_MATERIAL: "Win material",
    Intent.AVOID_THREAT: "Avoid a threat",
    Intent.TIME_PANIC: "Time pressure move",
    Intent.NOT_SURE: "Not sure",
    # Advanced
    Intent.PREPARE_ATTACK: "Preparing an attack",
    Intent.PROPHYLAXIS: "Stopping opponent's plan",
    Intent.IMPROVE_WORST_PIECE: "Activating my worst piece",
    Intent.CREATE_WEAKNESS: "Creating a weakness in opponent's camp",
    Intent.CONVERT_ADVANTAGE: "Converting my advantage",
}

# Rating-specific intent sets
INTENT_BY_RATING = {
    RatingBand.BAND_A: [  # 400-799: Keep it simple
        Intent.ATTACK,
        Intent.DEFEND,
        Intent.WIN_MATERIAL,
        Intent.TIME_PANIC,
        Intent.NOT_SURE,
    ],
    RatingBand.BAND_B: [  # 800-1099: Add development
        Intent.ATTACK,
        Intent.DEFEND,
        Intent.IMPROVE_PIECES,
        Intent.WIN_MATERIAL,
        Intent.AVOID_THREAT,
        Intent.TIME_PANIC,
        Intent.NOT_SURE,
    ],
    RatingBand.BAND_C: [  # 1100-1399: Full basic set
        Intent.ATTACK,
        Intent.DEFEND,
        Intent.IMPROVE_PIECES,
        Intent.TRADE_SIMPLIFY,
        Intent.WIN_MATERIAL,
        Intent.AVOID_THREAT,
        Intent.TIME_PANIC,
        Intent.NOT_SURE,
    ],
    RatingBand.BAND_D: [  # 1400-1699: Add advanced concepts
        Intent.ATTACK,
        Intent.DEFEND,
        Intent.IMPROVE_PIECES,
        Intent.TRADE_SIMPLIFY,
        Intent.WIN_MATERIAL,
        Intent.AVOID_THREAT,
        Intent.PREPARE_ATTACK,
        Intent.PROPHYLAXIS,
        Intent.TIME_PANIC,
        Intent.NOT_SURE,
    ],
    RatingBand.BAND_E: [  # 1700+: Full advanced set
        Intent.ATTACK,
        Intent.DEFEND,
        Intent.IMPROVE_PIECES,
        Intent.TRADE_SIMPLIFY,
        Intent.WIN_MATERIAL,
        Intent.AVOID_THREAT,
        Intent.PREPARE_ATTACK,
        Intent.PROPHYLAXIS,
        Intent.IMPROVE_WORST_PIECE,
        Intent.CREATE_WEAKNESS,
        Intent.CONVERT_ADVANTAGE,
        Intent.TIME_PANIC,
        Intent.NOT_SURE,
    ],
}

# ============================================
# REFLECTION MODE BY RATING
# ============================================
class ReflectionStyle(str, Enum):
    SIMPLE_TAP = "simple_tap"  # 400-999: Just tap options
    PLAN_TEXT = "plan_text"  # 1000-1299: Type your plan
    PLAN_BOARD = "plan_board"  # 1300+: Show plan on board + explain

# ============================================
# CONFIDENCE OPTIONS
# ============================================
class Confidence(str, Enum):
    VERY_SURE = "very_sure"
    SOMEWHAT_SURE = "somewhat_sure"
    GUESSING = "guessing"

CONFIDENCE_LABELS = {
    Confidence.VERY_SURE: "Very sure",
    Confidence.SOMEWHAT_SURE: "Somewhat sure",
    Confidence.GUESSING: "Guessing / fast move",
}

# ============================================
# AWARENESS GAP TYPES
# ============================================
class AwarenessGapType(str, Enum):
    ALIGNED = "aligned"                     # User's perception matches reality
    CONFIDENCE_GAP = "confidence_gap"       # High confidence but missed forcing
    PANIC_PATTERN = "panic_pattern"         # Low confidence + time pressure
    MISSED_FORCING = "missed_forcing"       # Didn't see opponent's threat
    IGNORED_FORCING = "ignored_forcing"     # Saw but dismissed threat
    PHANTOM_THREAT = "phantom_threat"       # Defended non-threat
    PARTIAL_ALIGNMENT = "partial_alignment" # Some awareness, some gap
    UNCLEAR = "unclear"                     # Couldn't determine

# ============================================
# RATING BANDS (for adaptive behavior)
# ============================================
class RatingBand(str, Enum):
    BAND_A = "A"  # 500-799
    BAND_B = "B"  # 800-1099
    BAND_C = "C"  # 1100-1399
    BAND_D = "D"  # 1400-1699
    BAND_E = "E"  # 1700-2000+

RATING_BAND_RANGES = {
    RatingBand.BAND_A: (0, 799),
    RatingBand.BAND_B: (800, 1099),
    RatingBand.BAND_C: (1100, 1399),
    RatingBand.BAND_D: (1400, 1699),
    RatingBand.BAND_E: (1700, 3000),
}

def get_rating_band(rating: int) -> RatingBand:
    """Get rating band from numeric rating."""
    for band, (low, high) in RATING_BAND_RANGES.items():
        if low <= rating <= high:
            return band
    return RatingBand.BAND_C  # Default to middle

# ============================================
# STABILITY BANDS (from TSI)
# ============================================
class StabilityBand(str, Enum):
    STABLE = "stable"         # TSI 85-100
    MODERATE = "moderate"     # TSI 70-84
    VOLATILE = "volatile"     # TSI 55-69
    CHAOTIC = "chaotic"       # TSI < 55

def get_stability_band(tsi: float) -> StabilityBand:
    """Get stability band from TSI score."""
    if tsi >= 85:
        return StabilityBand.STABLE
    elif tsi >= 70:
        return StabilityBand.MODERATE
    elif tsi >= 55:
        return StabilityBand.VOLATILE
    return StabilityBand.CHAOTIC

# ============================================
# REFLECTION UX MODES (by rating band)
# ============================================
class ReflectionMode(str, Enum):
    ULTRA_QUICK = "ultra_quick"  # Band A: 2 taps max
    QUICK = "quick"              # Band B/C: 3-4 taps
    STANDARD = "standard"        # Band D/E: 4-6 taps

# ============================================
# REWARD TONE (by rating band)
# ============================================
class RewardTone(str, Enum):
    ENCOURAGEMENT = "encouragement"     # Beginners - supportive
    PATTERN_PROGRESS = "pattern_progress"  # Intermediate - pattern focus
    PRECISION = "precision"              # Advanced - respect + precision

# ============================================
# REWARD EVENT TYPES
# ============================================
class RewardEventType(str, Enum):
    # Reflection rewards
    REFLECTION_CAPTURED_FAST = "reflection_captured_fast"
    REFLECTION_HONEST_NOT_SURE = "reflection_honest_not_sure"
    REFLECTION_CONFIDENCE_INSIGHT = "reflection_confidence_insight"
    REFLECTION_COMPLETE = "reflection_complete"
    
    # Process rewards
    PROCESS_THREAT_SCAN = "process_threat_scan"
    PROCESS_SLOWED_DOWN = "process_slowed_down"
    PROCESS_CHECKLIST_USED = "process_checklist_used"
    
    # Pattern rewards
    PATTERN_RECOGNIZED = "pattern_recognized"
    PATTERN_CAUGHT_REPEAT = "pattern_caught_repeat"
    
    # Recovery rewards
    RECOVERY_GOOD_RESET = "recovery_good_reset"
    
    # Mission rewards
    MISSION_STARTED = "mission_started"
    MISSION_COMPLETE_PASS = "mission_complete_pass"
    MISSION_COMPLETE_FAIL = "mission_complete_fail"

# ============================================
# QUICK TAG IDs (stable identifiers)
# ============================================
class QuickTagId(str, Enum):
    # General tags
    PLAYED_FAST = "played_fast"
    TIME_PRESSURE = "time_pressure"
    NOT_SURE = "not_sure"
    
    # Threat-related
    MISSED_CHECK = "missed_check"
    MISSED_CAPTURE = "missed_capture"
    MISSED_THREAT = "missed_threat"
    THOUGHT_HAD_TIME = "thought_had_time"
    
    # Piece safety
    THOUGHT_PIECE_SAFE = "thought_piece_safe"
    THOUGHT_PROTECTED = "thought_protected"
    
    # Attack/Defense
    CHOSE_ATTACK_OVER_SAFETY = "chose_attack_over_safety"
    ATTACKED_IGNORED_THREAT = "attacked_ignored_threat"
    DEFENDED_NON_THREAT = "defended_non_threat"
    
    # Position evaluation
    THOUGHT_WINNING = "thought_winning"
    FELT_DANGER = "felt_danger"
    WANTED_TO_FINISH = "wanted_to_finish"
    
    # Opening
    FOLLOWING_OPENING = "following_opening"
    
    # Advanced (Band D/E only)
    UNDERESTIMATED_COUNTERPLAY = "underestimated_counterplay"
    RUSHED_CONVERSION = "rushed_conversion"
    IGNORED_FORCING_SEQUENCE = "ignored_forcing_sequence"
    CHOSE_ACTIVITY_OVER_SAFETY = "chose_activity_over_safety"

# ============================================
# ADAPTIVE PROFILE DEFAULTS (by band)
# ============================================
ADAPTIVE_DEFAULTS = {
    RatingBand.BAND_A: {
        "reflection_mode": ReflectionMode.ULTRA_QUICK,
        "max_quick_tags": 4,
        "mission_minutes_target": 4,
        "mission_steps": {"reflect": 1, "puzzles": 2},
        "reward_tone": RewardTone.ENCOURAGEMENT,
        "success_target": 0.65,
        "streak_style": "gentle",
        "show_advanced_labels": False,
        "friction_budget_taps": 2,
    },
    RatingBand.BAND_B: {
        "reflection_mode": ReflectionMode.QUICK,
        "max_quick_tags": 5,
        "mission_minutes_target": 6,
        "mission_steps": {"reflect": 1, "puzzles": 3},
        "reward_tone": RewardTone.PATTERN_PROGRESS,
        "success_target": 0.70,
        "streak_style": "gentle",
        "show_advanced_labels": False,
        "friction_budget_taps": 3,
    },
    RatingBand.BAND_C: {
        "reflection_mode": ReflectionMode.QUICK,
        "max_quick_tags": 6,
        "mission_minutes_target": 7,
        "mission_steps": {"reflect": 1, "puzzles": 3},
        "reward_tone": RewardTone.PATTERN_PROGRESS,
        "success_target": 0.75,
        "streak_style": "standard",
        "show_advanced_labels": False,
        "friction_budget_taps": 4,
    },
    RatingBand.BAND_D: {
        "reflection_mode": ReflectionMode.STANDARD,
        "max_quick_tags": 6,
        "mission_minutes_target": 9,
        "mission_steps": {"reflect": 1, "puzzles": 4},
        "reward_tone": RewardTone.PRECISION,
        "success_target": 0.78,
        "streak_style": "standard",
        "show_advanced_labels": True,
        "friction_budget_taps": 5,
    },
    RatingBand.BAND_E: {
        "reflection_mode": ReflectionMode.STANDARD,
        "max_quick_tags": 7,
        "mission_minutes_target": 10,
        "mission_steps": {"reflect": 1, "puzzles": 5},
        "reward_tone": RewardTone.PRECISION,
        "success_target": 0.80,
        "streak_style": "consistency",
        "show_advanced_labels": True,
        "friction_budget_taps": 6,
    },
}

# ============================================
# HELPER: Get all intent options for frontend
# ============================================
def get_intent_options() -> List[Dict]:
    """Return intent options for frontend rendering."""
    return [
        {"id": intent.value, "label": INTENT_LABELS[intent]}
        for intent in Intent
    ]

# ============================================
# HELPER: Get confidence options for frontend
# ============================================
def get_confidence_options() -> List[Dict]:
    """Return confidence options for frontend rendering."""
    return [
        {"id": conf.value, "label": CONFIDENCE_LABELS[conf]}
        for conf in Confidence
    ]
