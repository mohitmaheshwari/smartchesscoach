"""Offline reasoning and evidence-to-model tools. No player route imports these."""

from .contracts import ReasoningConfig
from .engine import explain_fen
from .evidence import build_position_evidence
from .evidence_words import propose_evidence_reasoning

__all__ = ["ReasoningConfig", "explain_fen", "build_position_evidence", "propose_evidence_reasoning"]
