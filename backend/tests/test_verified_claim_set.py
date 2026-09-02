from __future__ import annotations

import pytest

from services.detector_quality import QualitySurface
from services.verified_claim_set import (
    VerifiedClaim,
    VerifiedClaimSet,
    VerifiedClaimViolation,
    select_primary_claim,
)


POSITION = "position-fingerprint"


def _claim(
    claim_type: str,
    quality_id: str,
    *,
    opportunity_contract_version: str | None = None,
    facts=(),
) -> VerifiedClaim:
    return VerifiedClaim(
        position_fingerprint=POSITION,
        claim_type=claim_type,
        actor="student",
        ply=24,
        move_uci="d3d2",
        before_state={"rook": "defended"},
        after_state={"rook": "undefended"},
        involved_pieces=("white rook", "black queen"),
        involved_squares=("d3", "d2", "c2"),
        legal_continuation=("c2d2",),
        objective_consequence="the queen can take the rook",
        detector_id=f"detector.{claim_type}",
        detector_version="v1",
        verifier_id=f"verifier.{claim_type}",
        verifier_version="v1",
        quality_id=quality_id,
        provenance_ref="stored-analysis:probe",
        facts=facts,
        opportunity_contract_version=opportunity_contract_version,
    )


def test_all_independently_verified_claims_survive_collection():
    caption = _claim("piece_safety", "gap:piece_safety:simple_hang")
    fork_caption = _claim("fork", "tactic:fork_with_stored_payoff")
    claims = VerifiedClaimSet.from_claims(POSITION, (caption, fork_caption))

    assert {item.claim_type for item in claims.claims} == {"piece_safety", "fork"}
    assert len(claims.eligible_for(QualitySurface.CAPTION)) == 2
    assert claims.to_document()["claim_count"] == 2


def test_primary_selection_does_not_erase_other_true_claims():
    first = _claim("piece_safety", "gap:piece_safety:simple_hang")
    second = _claim(
        "destination_safety",
        "gap:piece_safety:destination_safety_exact",
        opportunity_contract_version="destination_safety.v1",
    )
    claims = VerifiedClaimSet.from_claims(POSITION, (first, second))

    selected = select_primary_claim(
        claims,
        lambda claim: 10 if claim.claim_type == "destination_safety" else 1,
    )
    assert selected == second
    assert len(claims.claims) == 2
    assert {item.claim_id for item in claims.claims} == {
        first.claim_id, second.claim_id
    }


def test_unregistered_opportunity_version_cannot_manufacture_mastery():
    without_contract = _claim(
        "destination_safety",
        "gap:piece_safety:destination_safety_exact",
    )
    with_contract = _claim(
        "destination_safety",
        "gap:piece_safety:destination_safety_exact",
        opportunity_contract_version="destination_safety.v1",
        facts=({"variant": "with-contract"},),
    )

    assert without_contract.eligibility.plan is True
    assert without_contract.eligibility.mastery is False
    assert with_contract.eligibility.plan is True
    assert with_contract.eligibility.mastery is False
    assert with_contract.to_document()["opportunity_contract_version"] == (
        "destination_safety.v1"
    )


def test_fork_claim_is_caption_only_after_evidence_promotion():
    claim = _claim("fork", "tactic:fork_with_stored_payoff")
    assert claim.eligibility.research_only is False
    assert claim.eligibility.explanation is True
    assert claim.eligibility.plan is False
    assert claim.eligibility.mastery is False


def test_claim_identity_is_deterministic_and_exact_duplicates_collapse():
    left = _claim(
        "piece_safety",
        "gap:piece_safety:simple_hang",
        facts=({"a": 1, "b": 2},),
    )
    right = _claim(
        "piece_safety",
        "gap:piece_safety:simple_hang",
        facts=({"b": 2, "a": 1},),
    )
    claims = VerifiedClaimSet.from_claims(POSITION, (left, right))

    assert left.claim_id == right.claim_id
    assert len(claims.claims) == 1


def test_unverified_or_self_verified_claims_are_rejected():
    kwargs = dict(
        position_fingerprint=POSITION,
        claim_type="piece_safety",
        actor="student",
        move_uci="d3d2",
        objective_consequence="rook is lost",
        detector_id="same",
        detector_version="v1",
        verifier_id="same",
        verifier_version="v1",
        quality_id="gap:piece_safety:simple_hang",
        provenance_ref="stored",
    )
    with pytest.raises(VerifiedClaimViolation, match="independent"):
        VerifiedClaim(**kwargs)
    kwargs["verifier_id"] = "independent"
    kwargs["verified"] = False
    with pytest.raises(VerifiedClaimViolation, match="unverified"):
        VerifiedClaim(**kwargs)


def test_frozen_claim_facts_and_internal_diagnostic_cannot_leak():
    claim = _claim("piece_safety", "gap:piece_safety:simple_hang")
    with pytest.raises(TypeError):
        claim.before_state["rook"] = "changed"
    claims = VerifiedClaimSet.from_claims(POSITION, (claim,))
    with pytest.raises(VerifiedClaimViolation, match="internal research"):
        claims.eligible_for(QualitySurface.DIAGNOSTIC)
