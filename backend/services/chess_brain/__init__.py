"""
Chess Brain - Deterministic Coaching Engine
============================================

The core of personalized chess coaching. This engine separates:
1. Chess Truth (Stockfish, rules, patterns) 
2. Pedagogical Decisions (what to teach, how to teach)

Architecture:
- PositionInsightObject: Collected data about a position
- DetectorRegistry: Manages tactical/strategic/meta detectors
- LessonSelectionEngine: Scores and selects best teaching moment
- TeachingModes: 7 distinct coaching approaches

This is a DETERMINISTIC engine - no LLM for chess logic.
LLM is only used as optional language polish at the end.

Usage:
    from services.chess_brain import ChessBrain, analyze_with_chess_brain
    
    brain = ChessBrain(db)
    coaching = await brain.analyze_move(fen, move, user_id, session_id)
"""

from .enums import (
    TeachingMode,
    GamePhase,
    MistakeCategory,
    TacticalPattern,
    StrategicConcept,
    BehavioralPattern,
    LessonPriority,
    MoveQuality,
    ExplanationType
)

from .schemas import (
    PositionInsightObject,
    LessonCandidate,
    SelectedLesson,
    MistakeFingerprint,
    LessonMemory,
    DetectorResult
)

from .detector_registry import (
    DetectorRegistry,
    get_detector_registry
)

from .lesson_selection_engine import (
    LessonSelectionEngine,
    select_best_lesson
)

from .chess_brain import (
    ChessBrain,
    ChessBrainOutput,
    analyze_with_chess_brain
)

from .integration import (
    get_chess_brain_feedback,
    build_coaching_feedback,
    merge_feedback_sources
)

__all__ = [
    # Main classes
    'ChessBrain',
    'ChessBrainOutput',
    'DetectorRegistry',
    'LessonSelectionEngine',
    
    # Convenience functions
    'analyze_with_chess_brain',
    'get_chess_brain_feedback',
    'build_coaching_feedback',
    'merge_feedback_sources',
    'select_best_lesson',
    'get_detector_registry',
    
    # Enums
    'TeachingMode',
    'GamePhase', 
    'MistakeCategory',
    'TacticalPattern',
    'StrategicConcept',
    'BehavioralPattern',
    'LessonPriority',
    'MoveQuality',
    'ExplanationType',
    
    # Schemas
    'PositionInsightObject',
    'LessonCandidate',
    'SelectedLesson',
    'MistakeFingerprint',
    'LessonMemory',
    'DetectorResult'
]
