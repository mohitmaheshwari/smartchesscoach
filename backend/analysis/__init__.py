"""
Analysis package - Chess analysis services

Contains:
- intent_recognition_service: Deterministic intent detection for coaching
- intent_quality_calibrator: Human coach judgment calibration
"""

from .intent_recognition_service import (
    recognize_intent,
    recognize_intents_for_game,
    IntentResult,
    IntentType,
    IntentQuality,
    get_game_phase,
    get_king_zone,
)

from .intent_quality_calibrator import (
    calibrate_intent_quality,
    calibrate_with_forcing_context,
    build_coach_sentence,
    CalibratedIntentResult,
    CalibratedQuality,
    PositionPressure,
    classify_pressure,
    calculate_timing_score,
)

__all__ = [
    # Intent Recognition
    "recognize_intent",
    "recognize_intents_for_game",
    "IntentResult",
    "IntentType",
    "IntentQuality",
    "get_game_phase",
    "get_king_zone",
    # Intent Calibration
    "calibrate_intent_quality",
    "calibrate_with_forcing_context",
    "build_coach_sentence",
    "CalibratedIntentResult",
    "CalibratedQuality",
    "PositionPressure",
    "classify_pressure",
    "calculate_timing_score",
]
