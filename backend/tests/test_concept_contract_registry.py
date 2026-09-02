from __future__ import annotations

import json

import pytest

from scripts.report_coach_detector_capabilities import build_report
from services.concept_contract_registry import (
    BindingStatus,
    ConceptCapability,
    ConceptContract,
    ContentReference,
    ContractIndexViolation,
    DetectorBinding,
    build_concept_contract_index,
    complete_coaching_system_enabled,
)
from services.engine2_skill_builder import get_skill_tree_snapshot


PHASE0_UNMAPPED = {
    "concept_central_pawn_break",
    "concept_knight_outpost",
    "concept_luft",
    "concept_prophylactic_king_tuck",
    "concept_rook_open_file",
    "concept_rook_seventh",
    "opening_castling",
    "opening_center",
    "opening_development_with_tempo",
    "opening_sound_deviation",
}


def test_complete_coaching_composition_is_default_off():
    assert complete_coaching_system_enabled({}) is False
    assert complete_coaching_system_enabled({"COMPLETE_COACHING_SYSTEM_V1_ENABLED": "false"}) is False
    assert complete_coaching_system_enabled({"COMPLETE_COACHING_SYSTEM_V1_ENABLED": "true"}) is True


def test_index_is_generated_from_current_owners_and_read_only():
    index = build_concept_contract_index()

    assert len(index.contracts) == 77
    assert len(index.detector_bindings) == 48
    assert index.contracts["opening_london_white"].content.content_id == "london_system"
    assert index.resolve("london_system", domain="opening").concept_id == "opening_london_white"
    assert index.resolve("opposition", domain="endgame").concept_id == "endgame_opposition"
    with pytest.raises(TypeError):
        index.contracts["invented"] = index.contracts["opening_london_white"]


def test_skill_tree_snapshot_cannot_mutate_the_canonical_cache():
    snapshot = get_skill_tree_snapshot()
    snapshot["skills"]["opening_london_white"]["content_ref"] = "corrupted"

    assert (
        get_skill_tree_snapshot()["skills"]["opening_london_white"]["content_ref"]
        == "london_system"
    )


def test_phase0_mapping_gaps_are_explicit_and_new_or_stale_waivers_fail():
    index = build_concept_contract_index()

    assert set(index.unmapped_detector_ids) == PHASE0_UNMAPPED
    index.assert_valid(allowed_unmapped_detector_ids=PHASE0_UNMAPPED)
    with pytest.raises(ContractIndexViolation, match="unmapped detector ids"):
        index.assert_valid()
    with pytest.raises(ContractIndexViolation, match="stale allowed-unmapped"):
        index.assert_valid(
            allowed_unmapped_detector_ids=PHASE0_UNMAPPED | {"already_fixed"}
        )


def test_existing_capability_report_uses_the_same_generated_join():
    index = build_concept_contract_index()
    report = build_report()

    assert report["summary"]["registered_detectors"] == len(index.detector_bindings)
    assert set(report["mapping_gaps"]) == set(index.unmapped_detector_ids)
    opening = index.detector_bindings["opening_play"]
    report_row = next(
        row for row in report["detectors"] if row["detector_id"] == "opening_play"
    )
    assert report_row["target_skill_ids"] == list(opening.target_concept_ids)
    assert report_row["content_ids"] == list(opening.content_ids)


def test_research_detectors_do_not_gain_player_authority_from_registration():
    index = build_concept_contract_index()
    london = index.contracts["opening_london_white"]

    assert ConceptCapability.RESEARCH_ONLY in london.capabilities
    assert ConceptCapability.CAPTION not in london.capabilities
    assert ConceptCapability.PLAN not in london.capabilities
    assert london.opportunity_contract_refs == ()
    assert all(
        not binding.allowed_surfaces
        for binding in index.detector_bindings.values()
    )
    assert all(
        ConceptCapability.MASTERY not in contract.capabilities
        for contract in index.contracts.values()
    )


def test_lesson_capability_requires_a_versioned_grader():
    with pytest.raises(ContractIndexViolation, match="versioned grader"):
        ConceptContract(
            concept_id="x",
            aliases=("x",),
            domain="concept",
            curriculum_stage=0,
            prerequisites=(),
            content=ContentReference("concept", "x", "canonical"),
            detector_ids=(),
            detector_quality_ids=(),
            allowed_surfaces=(),
            capabilities=(ConceptCapability.CURRICULUM,),
            lesson_capabilities=("teach",),
            grader_ref=None,
            grader_contract_version=None,
            opportunity_contract_refs=(),
            evidence_limitations=(),
        )


def test_unauthorized_surface_cannot_be_written_into_a_binding():
    with pytest.raises(ContractIndexViolation, match="not authorized"):
        DetectorBinding(
            detector_id="x",
            detector_ref="tests.detector",
            quality_id="gap:piece_safety:simple_hang",
            quality_grade="caption",
            target_concept_ids=("x",),
            content_ids=("x",),
            allowed_surfaces=("plan",),
            opportunity_contract_version=None,
            evidence_ref="evidence",
            limitations=(),
            status=BindingStatus.BOUND,
        )


def test_contract_shape_can_reference_but_cannot_copy_chess_content():
    assert set(ContentReference.__dataclass_fields__) == {
        "kind", "content_id", "source_ref"
    }
    forbidden = {"fen", "moves", "answers", "caption", "explanation"}
    assert forbidden.isdisjoint(ConceptContract.__dataclass_fields__)

    document = build_concept_contract_index().to_document()
    encoded = json.dumps(document, sort_keys=True)
    assert '"fen"' not in encoded
    assert '"moves"' not in encoded
    assert '"answers"' not in encoded
