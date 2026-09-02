"""Non-lossy storage contract for independently verified chess claims.

Claim collection and presentation selection are deliberately separate.  This
module contains no detector, chess-content, engine, or caption logic.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
from types import MappingProxyType
from typing import Any, Callable, Dict, Iterable, Mapping, Optional, Tuple

from services.detector_quality import (
    QualitySurface,
    grade_for,
    is_authorized,
)


SCHEMA_VERSION = "verified_claim_set.v1"


class VerifiedClaimViolation(ValueError):
    """Raised when a claim lacks independent, versioned provenance."""


def _stable_hash(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), default=str
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    return value


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_plain(item) for item in value]
    return value


@dataclass(frozen=True)
class ClaimEligibility:
    explanation: bool
    plan: bool
    mastery: bool
    research_only: bool


@dataclass(frozen=True)
class VerifiedClaim:
    position_fingerprint: str
    claim_type: str
    actor: str
    move_uci: str
    objective_consequence: str
    detector_id: str
    detector_version: str
    verifier_id: str
    verifier_version: str
    quality_id: str
    provenance_ref: str
    ply: Optional[int] = None
    before_state: Mapping[str, Any] = field(default_factory=dict)
    after_state: Mapping[str, Any] = field(default_factory=dict)
    involved_pieces: Tuple[str, ...] = ()
    involved_squares: Tuple[str, ...] = ()
    legal_continuation: Tuple[str, ...] = ()
    facts: Tuple[Mapping[str, Any], ...] = ()
    opportunity_contract_version: Optional[str] = None
    verified: bool = True
    claim_id: str = field(init=False)

    def __post_init__(self) -> None:
        required = (
            self.position_fingerprint,
            self.claim_type,
            self.actor,
            self.move_uci,
            self.objective_consequence,
            self.detector_id,
            self.detector_version,
            self.verifier_id,
            self.verifier_version,
            self.quality_id,
            self.provenance_ref,
        )
        if not all(isinstance(value, str) and value.strip() for value in required):
            raise VerifiedClaimViolation("verified claims require complete provenance")
        if not self.verified:
            raise VerifiedClaimViolation("unverified candidates cannot enter a claim set")
        if self.detector_id == self.verifier_id:
            raise VerifiedClaimViolation("detector and verifier must be independent")
        if self.ply is not None and (not isinstance(self.ply, int) or self.ply < 0):
            raise VerifiedClaimViolation("ply must be a non-negative integer")
        object.__setattr__(self, "before_state", _freeze(self.before_state))
        object.__setattr__(self, "after_state", _freeze(self.after_state))
        object.__setattr__(self, "facts", tuple(_freeze(item) for item in self.facts))
        object.__setattr__(self, "involved_pieces", tuple(self.involved_pieces))
        object.__setattr__(self, "involved_squares", tuple(self.involved_squares))
        object.__setattr__(self, "legal_continuation", tuple(self.legal_continuation))
        object.__setattr__(self, "claim_id", _stable_hash(self.identity_payload()))

    @property
    def eligibility(self) -> ClaimEligibility:
        explanation = is_authorized(self.quality_id, QualitySurface.CAPTION)
        plan = is_authorized(self.quality_id, QualitySurface.PLAN)
        # Phase 0 found no locked post-lesson transfer rule.  Carry a claimed
        # opportunity version as evidence, but do not let an arbitrary string
        # manufacture mastery. Phase 2 must introduce the reviewed opportunity
        # registry before this can ever become true.
        mastery = False
        return ClaimEligibility(
            explanation=explanation,
            plan=plan,
            mastery=mastery,
            research_only=not (explanation or plan or mastery),
        )

    def identity_payload(self) -> Dict[str, Any]:
        return {
            "position_fingerprint": self.position_fingerprint,
            "claim_type": self.claim_type,
            "actor": self.actor,
            "ply": self.ply,
            "move_uci": self.move_uci,
            "before_state": _plain(self.before_state),
            "after_state": _plain(self.after_state),
            "involved_pieces": list(self.involved_pieces),
            "involved_squares": list(self.involved_squares),
            "legal_continuation": list(self.legal_continuation),
            "objective_consequence": self.objective_consequence,
            "detector_id": self.detector_id,
            "detector_version": self.detector_version,
            "verifier_id": self.verifier_id,
            "verifier_version": self.verifier_version,
            "quality_id": self.quality_id,
            "provenance_ref": self.provenance_ref,
            "facts": _plain(self.facts),
            "opportunity_contract_version": self.opportunity_contract_version,
        }

    def to_document(self) -> Dict[str, Any]:
        eligibility = self.eligibility
        return {
            **self.identity_payload(),
            "claim_id": self.claim_id,
            "verified": True,
            "quality_grade": grade_for(self.quality_id).value,
            "eligibility": {
                "explanation": eligibility.explanation,
                "plan": eligibility.plan,
                "mastery": eligibility.mastery,
                "research_only": eligibility.research_only,
            },
        }


@dataclass(frozen=True)
class VerifiedClaimSet:
    position_fingerprint: str
    claims: Tuple[VerifiedClaim, ...] = ()
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.position_fingerprint, str) or not self.position_fingerprint:
            raise VerifiedClaimViolation("claim set requires a position fingerprint")
        unique: Dict[str, VerifiedClaim] = {}
        for claim in self.claims:
            if not isinstance(claim, VerifiedClaim):
                raise VerifiedClaimViolation("claim sets accept only VerifiedClaim values")
            if claim.position_fingerprint != self.position_fingerprint:
                raise VerifiedClaimViolation("a claim belongs to a different position")
            unique.setdefault(claim.claim_id, claim)
        object.__setattr__(
            self,
            "claims",
            tuple(sorted(unique.values(), key=lambda item: item.claim_id)),
        )

    @classmethod
    def from_claims(
        cls,
        position_fingerprint: str,
        claims: Iterable[VerifiedClaim],
    ) -> "VerifiedClaimSet":
        return cls(position_fingerprint, tuple(claims))

    def with_claim(self, claim: VerifiedClaim) -> "VerifiedClaimSet":
        return VerifiedClaimSet.from_claims(
            self.position_fingerprint, (*self.claims, claim)
        )

    def eligible_for(self, surface: QualitySurface | str) -> Tuple[VerifiedClaim, ...]:
        requested = QualitySurface(surface)
        if requested == QualitySurface.DIAGNOSTIC:
            raise VerifiedClaimViolation(
                "DIAGNOSTIC is internal research, not claim publication"
            )
        return tuple(
            claim for claim in self.claims
            if (
                claim.eligibility.explanation
                if requested == QualitySurface.CAPTION
                else claim.eligibility.plan
                if requested == QualitySurface.PLAN
                else claim.eligibility.mastery
                if requested == QualitySurface.MASTERY
                else is_authorized(claim.quality_id, requested)
            )
        )

    def to_document(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "position_fingerprint": self.position_fingerprint,
            "claims": [claim.to_document() for claim in self.claims],
            "claim_count": len(self.claims),
        }


def select_primary_claim(
    claim_set: VerifiedClaimSet,
    rank: Callable[[VerifiedClaim], Any],
    *,
    surface: QualitySurface | str = QualitySurface.CAPTION,
) -> Optional[VerifiedClaim]:
    """Select presentation without deleting or rewriting collected truth."""
    candidates = claim_set.eligible_for(surface)
    if not candidates:
        return None
    return max(candidates, key=lambda item: (rank(item), item.claim_id))
