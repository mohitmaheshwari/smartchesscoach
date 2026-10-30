"""Offline deterministic reasoning. No player route imports this package."""

from .contracts import ReasoningConfig
from .engine import explain_fen

__all__ = ["ReasoningConfig", "explain_fen"]
