"""
Config Package

Centralized configuration for the chess coaching backend.
"""

from .engine_config import (
    ENGINE_VERSION,
    REANALYSIS_CONFIG,
    DIFFICULTY_CONFIG,
)

__all__ = [
    "ENGINE_VERSION",
    "REANALYSIS_CONFIG",
    "DIFFICULTY_CONFIG",
]
