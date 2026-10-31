"""Reasoning and evidence-to-model tools.

Offline unless stated: explain_fen, locate_reply_dependency, build_position_evidence
and propose_evidence_reasoning are run by scripts only. `differential.explain_move`
is the one entry point a player route reaches, through services/why_differential.py
behind WHY_DIFFERENTIAL_ENABLED (the why button, 2026-10-31).
"""

from .contracts import ReasoningConfig
from .engine import explain_fen
from .counterfactual import locate_reply_dependency
from .differential import explain_move
from .evidence import build_position_evidence
from .evidence_words import propose_evidence_reasoning

__all__ = ["ReasoningConfig", "explain_fen", "explain_move", "locate_reply_dependency",
           "build_position_evidence", "propose_evidence_reasoning"]
