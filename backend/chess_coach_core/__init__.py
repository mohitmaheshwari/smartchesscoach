# Chess Coach Core - The Pedagogy Engine
# This is the deterministic coaching brain of ChessGuru

from .schemas import (
    PositionInsight,
    LessonCandidate,
    TeachingMode,
    DetectorResult,
    GamePhase,
    LessonMemory,
)
from .detector_registry import DetectorRegistry
from .lesson_engine import LessonEngine
from .explanation_builder import ExplanationBuilder
