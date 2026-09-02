import json
from pathlib import Path

import pytest

from services.destination_safety_detector import (
    QUALITY_ID,
    build_destination_safety_reason_bundle,
)
from services.teaching_reason_contracts import ReasonContractViolation


GOLD_PATH = (
    Path(__file__).parents[1]
    / "data"
    / "detector_gold"
    / "home_teaching_case_v2_v1.json"
)


def _gold_cases():
    return json.loads(GOLD_PATH.read_text(encoding="utf-8"))["cases"]


@pytest.mark.parametrize("case", _gold_cases(), ids=lambda case: case["case_id"])
def test_reason_bundle_matches_adjudicated_gold(case):
    bundle = build_destination_safety_reason_bundle(case["fen"], case["move_uci"])

    assert bundle.target_result == case["target_status"]
    assert bundle.safety_kind == case["safety_kind"]
    assert [component.kind for component in bundle.components] == case["expected_components"]
    assert bundle.proof.quality_id == QUALITY_ID
    assert bundle.proof.authority == "dual_legal_exchange"


def test_approved_rook_case_teaches_the_actual_board_connections():
    case = _gold_cases()[0]
    bundle = build_destination_safety_reason_bundle(case["fen"], case["move_uci"])
    components = {component.kind: component for component in bundle.components}

    assert bundle.move_san == "R3d2"
    assert components["incoming_threat"].prompt == (
        "Which of your rooks did the queen on c2 attack?"
    )
    assert components["incoming_threat"].facts["attacked_squares"] == ["d1", "d3"]
    assert components["destination_safety"].prompt == (
        "After R3d2, can Black win your rook on d2 immediately?"
    )
    assert components["counterattack"].success_text == (
        "R3d2 also attacks the queen on c2."
    )
    calculation = components["one_recapture_calculation"]
    assert calculation.prompt == "If Black plays Qxd2, what happens next?"
    assert calculation.facts["recapture_san"] == "Rxd2"


def test_public_question_contains_no_answer_or_detector_provenance():
    case = _gold_cases()[0]
    bundle = build_destination_safety_reason_bundle(case["fen"], case["move_uci"])
    public = bundle.question(0)
    rendered = json.dumps(public, sort_keys=True)

    for forbidden in (
        "accepted_choice_ids",
        "facts",
        "success_text",
        "correction_text",
        "quality_id",
        "detector_version",
        "proof",
    ):
        assert forbidden not in rendered
    assert public["progress"] == {"current": 1, "total": 4}


def test_component_grading_is_ordered_and_question_bound():
    case = _gold_cases()[0]
    bundle = build_destination_safety_reason_bundle(case["fen"], case["move_uci"])
    first = bundle.components[0]
    correct_choice = first.accepted_choice_ids[0]

    result = bundle.grade_component(
        index=0,
        question_id=first.question_id,
        selected_choice_id=correct_choice,
    )
    assert result["correct"] is True
    assert result["kind"] == "incoming_threat"

    with pytest.raises(ReasonContractViolation):
        bundle.grade_component(
            index=0,
            question_id=bundle.components[1].question_id,
            selected_choice_id=correct_choice,
        )


def test_side_to_move_wording_names_white_when_black_has_moved():
    bundle = build_destination_safety_reason_bundle(
        "r3k3/1B6/8/8/8/8/8/4K3 b - - 0 1",
        "a8a1",
    )
    destination = next(
        component for component in bundle.components
        if component.kind == "destination_safety"
    )

    assert "can White" in destination.prompt
    assert "can Black" not in destination.prompt


def test_unsupported_piece_fails_closed_without_questions():
    case = _gold_cases()[-1]
    bundle = build_destination_safety_reason_bundle(case["fen"], case["move_uci"])

    assert bundle.target_result == "unmeasured"
    assert bundle.components == ()
    assert bundle.question(0) is None
