"""
Analysis package - Chess analysis services

Contains:
- intent_recognition_service: Deterministic intent detection for coaching
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

__all__ = [
    "recognize_intent",
    "recognize_intents_for_game",
    "IntentResult",
    "IntentType",
    "IntentQuality",
    "get_game_phase",
    "get_king_zone",
]
