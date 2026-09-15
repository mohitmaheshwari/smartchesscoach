from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from scripts import admit_reviewed_community_game_studies as admission
from scripts import build_community_game_study_review_packet as builder
from services import community_game_study_service as study_service


BACKEND = Path(__file__).resolve().parents[1]
SOURCE_PATH = (
    BACKEND / "data/detector_gold/community_game_study_neutral_review_v3.json"
)
SEALED_PATH = (
    BACKEND / "data/corpus_snapshots/community_game_study_admissions_v3.json"
)


def _file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _packet():
    source = json.loads(SOURCE_PATH.read_text(encoding="utf-8"))
    sealed = json.loads(SEALED_PATH.read_text(encoding="utf-8"))
    source["schema_version"] = builder.SCHEMA_VERSION
    sealed["review_packet_schema_version"] = builder.SCHEMA_VERSION
    for record in sealed["records"]:
        study = record["study"]
        study["schema_version"] = study_service.SCHEMA_VERSION
        study["admission_policy_version"] = (
            study_service.ADMISSION_POLICY_VERSION
        )
        study["plan"]["safe_projection_version"] = (
            study_service.SAFE_PROJECTION_VERSION
        )
    reviewed = deepcopy(source)
    for case in reviewed["cases"]:
        case["reviewer_response"] = {
            "schema_version": builder.REVIEW_RESPONSE_SCHEMA_VERSION,
            "would_assign_to_a_player_in_this_band": True,
            "chapter_verdicts": [
                {
                    "chapter_index": index,
                    "move_number": chapter["move_number"],
                    "move_san": chapter["move_san"],
                    "verdict": "correct_and_teachable",
                    "headline_is_pattern_geometry_or_idea_led": True,
                    "demonstration_legally_proves_visible_claim": True,
                    "critical_false_claim": False,
                    "why": "The position and legal line prove this lesson.",
                }
                for index, chapter in enumerate(case["chapters"])
            ],
            "whole_game_story_is_coherent": True,
            "repeats_primary_principle_as_separate_chapters": False,
            "most_memorable_chapter_number": case["chapters"][0]["move_number"],
            "notes": "Independent fixture review.",
        }
    reviewed["independent_review"] = {
        "reviewer": "Independent test reviewer",
        "reviewed_on": "2026-09-15",
        "source_packet_sha256": _file_sha(SOURCE_PATH),
        "method": "Legally replayed every displayed line.",
        "blinding_holds": True,
    }
    return source, reviewed, sealed


def _evaluate(source, reviewed, sealed):
    return admission.evaluate_packets(
        source=source,
        reviewed=reviewed,
        admission_packet=sealed,
        source_sha256=_file_sha(SOURCE_PATH),
        reviewed_sha256=admission._value_sha256(reviewed),
        admission_sha256=_file_sha(SEALED_PATH),
        expected_source_sha256=_file_sha(SOURCE_PATH),
    )


def test_exact_bound_review_passes_and_builds_admitted_documents():
    source, reviewed, sealed = _packet()
    gate = _evaluate(source, reviewed, sealed)
    assert gate["cases"] == len(source["cases"])
    assert gate["chapters"] == sum(
        len(case["chapters"]) for case in source["cases"]
    )
    assert gate["critical_false_claims"] == 0
    assert gate["admitted_studies"] == gate["cases"]
    assert set(gate["proof_answer_positions"]) == {"0", "1"}
    documents = admission.admission_documents(gate)
    assert len(documents) == gate["cases"]
    assert {document["status"] for document in documents} == {"admitted"}
    assert all(
        document["independent_admission"]["source_packet_sha256"]
        == _file_sha(SOURCE_PATH)
        for document in documents
    )


def test_review_cannot_change_a_headline_or_any_non_review_content():
    source, reviewed, sealed = _packet()
    reviewed["cases"][0]["chapters"][0]["headline"] = "Tampered headline"
    with pytest.raises(
        admission.AdmissionError, match="outside reviewer_response"
    ):
        _evaluate(source, reviewed, sealed)


def test_one_critical_false_claim_blocks_the_entire_release():
    source, reviewed, sealed = _packet()
    reviewed["cases"][0]["reviewer_response"]["chapter_verdicts"][0][
        "critical_false_claim"
    ] = True
    with pytest.raises(
        admission.AdmissionError, match="critical_false_claim"
    ):
        _evaluate(source, reviewed, sealed)


def test_teachability_gate_is_a_rate_not_a_raw_count():
    source, reviewed, sealed = _packet()
    verdicts = [
        row
        for case in reviewed["cases"]
        for row in case["reviewer_response"]["chapter_verdicts"]
    ]
    for row in verdicts[: len(verdicts) // 2]:
        row["verdict"] = "correct_but_not_teachable"
    with pytest.raises(
        admission.AdmissionError, match="rate did not beat 71.8"
    ):
        _evaluate(source, reviewed, sealed)


def test_fixed_correct_answer_position_blocks_the_entire_release(monkeypatch):
    source, reviewed, sealed = _packet()
    monkeypatch.setattr(
        admission,
        "guided_answer_position_indices",
        lambda study: tuple(0 for _ in study["plan"]["chapters"]),
    )
    with pytest.raises(admission.AdmissionError, match="one fixed option position"):
        _evaluate(source, reviewed, sealed)


def test_sealed_selection_must_match_the_blinded_packet():
    source, reviewed, sealed = _packet()
    sealed["selection_fingerprint_sha256"] = "0" * 64
    with pytest.raises(
        admission.AdmissionError, match="selection fingerprint"
    ):
        _evaluate(source, reviewed, sealed)


def test_apply_plan_is_stable_and_refuses_terminal_or_silent_demotion():
    source, reviewed, sealed = _packet()
    gate = _evaluate(source, reviewed, sealed)
    first = admission.build_apply_plan(gate, [])
    second = admission.build_apply_plan(gate, [])
    assert first["plan_fingerprint"] == second["plan_fingerprint"]
    assert first["scope"]["admitted"] == gate["cases"]

    study_id = first["documents"][0]["study_id"]
    with pytest.raises(admission.AdmissionError, match="terminal study"):
        admission.build_apply_plan(
            gate,
            [{"study_id": study_id, "status": "quarantined"}],
        )

    demoted = deepcopy(gate)
    demoted["admitted_case_ids"] = demoted["admitted_case_ids"][1:]
    with pytest.raises(admission.AdmissionError, match="silently demote"):
        admission.build_apply_plan(
            demoted,
            [{"study_id": study_id, "status": "admitted"}],
        )
