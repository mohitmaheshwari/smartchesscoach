"""Proof-carrying candidate contract for the PWC V2 conductor.

This replaces player-facing ``MessageCandidate`` after cutover. It does not
replace the opponent selector's ``CandidateMove``: choosing an engine move and
choosing what to teach are separate jobs.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Optional


class CandidateTiming(str, Enum):
    BEFORE_MOVE = "before_move"
    AFTER_MOVE = "after_move"
    AFTER_OPPONENT = "after_opponent"
    REQUESTED_HELP = "requested_help"
    POSTGAME = "postgame"


class CandidateUrgency(str, Enum):
    CONTEXT = "context"
    TEACHABLE = "teachable"
    IMPORTANT = "important"
    IMMEDIATE_DANGER = "immediate_danger"


class CandidateFocus(str, Enum):
    NONE = "none"
    HISTORICAL = "historical"
    SUPPORTING = "supporting"
    PRIMARY = "primary"


class CandidateNovelty(str, Enum):
    UNKNOWN = "unknown"
    REPEATED = "repeated"
    REINFORCEMENT = "reinforcement"
    NEW = "new"


def stable_candidate_id(
    *, turn_id: str, source: str, concept_key: str, claim: str
) -> str:
    """Return the one deterministic identity used by every candidate adapter."""
    digest = hashlib.sha256(
        f"{turn_id}|{source}|{concept_key}|{claim}".encode("utf-8")
    ).hexdigest()[:16]
    return f"pwc2c:{digest}"


@dataclass(frozen=True)
class CoachingCandidate:
    """One verified option submitted to the shadow/live conductor.

    The contract carries facts and proof. It never grants itself permission to
    render: only the conductor can select it, and only a later runtime may
    deliver that selection.
    """

    candidate_id: str
    turn_id: str
    source: str
    timing: CandidateTiming
    category: str
    concept_key: str
    claim: str
    transferable_instruction: Optional[str]
    urgency: CandidateUrgency
    focus_relevance: CandidateFocus
    novelty: CandidateNovelty
    assistance_level: Optional[int]
    proof_authority: str
    proof_references: tuple[str, ...]
    proof_verified: bool
    abstention_reason: Optional[str] = None
    game_phase: Optional[str] = None
    evidence: Mapping[str, Any] = field(default_factory=dict)
    visual: Mapping[str, Any] = field(default_factory=dict)

    def validation_errors(self) -> tuple[str, ...]:
        errors: list[str] = []
        for field_name in (
            "candidate_id",
            "turn_id",
            "source",
            "category",
            "concept_key",
            "claim",
            "proof_authority",
        ):
            if not str(getattr(self, field_name) or "").strip():
                errors.append(f"missing_{field_name}")
        if not self.proof_verified:
            errors.append("proof_not_verified")
        if not any(str(reference).strip() for reference in self.proof_references):
            errors.append("missing_proof_reference")
        if self.assistance_level is not None and not 0 <= self.assistance_level <= 4:
            errors.append("invalid_assistance_level")
        if self.timing != CandidateTiming.POSTGAME:
            for evidence_name in ("fen", "move", "source_version"):
                if not str(self.evidence.get(evidence_name) or "").strip():
                    errors.append(f"missing_evidence_{evidence_name}")
        if self.abstention_reason:
            errors.append("candidate_abstained")
        return tuple(errors)

    @property
    def admitted(self) -> bool:
        return not self.validation_errors()

    def to_document(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "turn_id": self.turn_id,
            "source": self.source,
            "timing": self.timing.value,
            "category": self.category,
            "concept_key": self.concept_key,
            "claim": self.claim,
            "transferable_instruction": self.transferable_instruction,
            "urgency": self.urgency.value,
            "focus_relevance": self.focus_relevance.value,
            "novelty": self.novelty.value,
            "assistance_level": self.assistance_level,
            "proof": {
                "authority": self.proof_authority,
                "references": list(self.proof_references),
                "verified": self.proof_verified,
            },
            "abstention_reason": self.abstention_reason,
            "game_phase": self.game_phase,
            "evidence": dict(self.evidence),
            "visual": dict(self.visual),
        }


__all__ = [
    "CandidateFocus",
    "CandidateNovelty",
    "CandidateTiming",
    "CandidateUrgency",
    "CoachingCandidate",
    "stable_candidate_id",
]
