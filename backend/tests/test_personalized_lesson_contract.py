import asyncio
from copy import deepcopy

from services.curriculum_content_validator import (
    validate_personalized_lesson_descriptor,
)
from services.endgame_theory_service import get_all_categories
from services.opening_curriculum_engine import get_available_openings
from services.personalized_lesson_adapter import (
    personalized_lesson_source_ref,
    resolve_personalized_lesson,
)
from trick_library_service import get_all_traps


class _NoDB:
    pass


def _resolve(kind, content_id, params=None):
    return asyncio.run(resolve_personalized_lesson(
        _NoDB(),
        "offline-contract-user",
        content_kind=kind,
        content_id=content_id,
        params=params,
    ))


def test_every_published_canonical_lesson_passes_workspace_contract():
    descriptors = []
    for opening in get_available_openings():
        descriptors.append(_resolve(
            "opening",
            opening["key"],
            {"player_color": opening["color"]},
        ))
    for trap in get_all_traps():
        descriptors.append(_resolve(
            "trap",
            trap["key"],
            {"mode": "avoidance"},
        ))
    for category in get_all_categories():
        for lesson in category["lessons"]:
            descriptors.append(_resolve("endgame", lesson["lesson_id"]))

    counts = {
        kind: sum(item["kind"] == kind for item in descriptors)
        for kind in ("opening", "trap", "endgame")
    }
    assert counts == {"opening": 41, "trap": 36, "endgame": 20}
    for descriptor in descriptors:
        result = validate_personalized_lesson_descriptor(descriptor)
        assert result.publishable, result.as_dict()
        assert personalized_lesson_source_ref(
            descriptor["kind"], descriptor["id"]
        ) == descriptor["canonical_source"]


def test_every_personalized_trap_family_passes_workspace_contract():
    from services.engine2_skill_builder import (
        get_skill_node,
        list_skills_by_kind,
        reload_tree,
    )

    reload_tree()
    for skill_id in list_skills_by_kind("trap_set"):
        node = get_skill_node(skill_id)
        descriptor = _resolve(
            "trap_set",
            node["content_ref"],
            {"skill_id": skill_id},
        )
        result = validate_personalized_lesson_descriptor(descriptor)
        assert result.publishable, result.as_dict()
        assert personalized_lesson_source_ref(
            descriptor["kind"], descriptor["id"]
        ) == descriptor["canonical_source"]


def test_contract_rejects_public_answers_duplicate_positions_and_fake_transfer():
    descriptor = _resolve("opening", "london_system", {"player_color": "white"})
    broken = deepcopy(descriptor)
    broken["items"][1]["fen"] = broken["items"][0]["fen"]
    broken["items"][1].pop("_expected_uci", None)
    broken["items"][1]["_expected_reason"] = "not_a_choice"
    result = validate_personalized_lesson_descriptor(broken)
    codes = {issue.code for issue in result.issues}

    assert "personalized.position_duplicate" in codes
    assert "personalized.private_answer_missing" in codes
    assert "personalized.expected_reason_missing" in codes


def test_single_position_lesson_cannot_claim_independent_transfer():
    descriptor = _resolve("opening", "london_system", {"player_color": "white"})
    broken = deepcopy(descriptor)
    broken["items"] = [broken["items"][0]]
    broken["items"][0]["stage"] = "transfer"
    broken["mastery_capability"] = "guided"
    result = validate_personalized_lesson_descriptor(broken)

    assert not result.publishable
    assert any(
        issue.code == "personalized.guided_claims_transfer"
        for issue in result.issues
    )
