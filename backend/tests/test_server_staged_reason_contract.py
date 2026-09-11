"""A lesson item may keep its reason question on the server.

Endgame lessons used to ship a reason question inside the descriptor, with
generic choices authored before anyone knew which move the player would pick
("It uses the rule for this ending", "It gives check, so it must be best").
Those were replaced by a server-staged question that can be specific to the
move actually chosen -- "What is Kc3 preparing?" -- which means the descriptor
no longer carries `reason_prompt`, `reason_choices` or `_expected_reason`.

`validate_personalized_lesson_descriptor` still demanded all three, so the
producer moved and the contract did not. Measured on the commit that made the
change: 20 of 20 endgame lessons came back unpublishable, against 0 of 20
before it, including the one lesson the change was written to fix.

The guarantee the contract exists to protect is unchanged and is pinned below:
the player is never handed the answer, and grading stays server-owned.
"""
from __future__ import annotations

import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from services.curriculum_content_validator import (
    validate_personalized_lesson_descriptor,
)
from services.endgame_theory_service import get_all_categories

FEN = "7k/8/8/8/8/8/1PK5/8 w - - 0 1"


def _descriptor(**item_overrides):
    item = {
        "item_id": "item-1",
        "fen": FEN,
        "prompt": "Find the move that walks your King toward a target square.",
        "source": "canonical_endgame",
        "source_ref": "king_and_pawn/key_squares",
        "board_verified": True,
        "stage": "guide",
        "_expected_uci": "c2d3",
    }
    item.update(item_overrides)
    return {
        "kind": "endgame",
        "id": "king_and_pawn/key_squares",
        "skill_id": "endgame:king_and_pawn/key_squares",
        "title": "Key squares",
        "rule": "Walk the King to a target square before pushing the pawn.",
        "canonical_source": "endgame_theory_tree.json",
        "content_version": "v1",
        "mastery_capability": "guided",
        "items": [item],
    }


def _codes(record):
    return {issue["code"] for issue in record.as_dict()["issues"]}


def test_a_server_staged_item_needs_no_descriptor_side_reason():
    record = validate_personalized_lesson_descriptor(
        _descriptor(server_staged_reasoning=True)
    )
    assert record.publishable, record.as_dict()


def test_an_ordinary_item_still_has_to_carry_its_reason():
    # The relaxation is scoped to staged items. Without the flag the three
    # fields are still mandatory -- otherwise this change would have quietly
    # dropped the requirement for every lesson kind.
    record = validate_personalized_lesson_descriptor(_descriptor())
    codes = _codes(record)
    assert not record.publishable
    assert "personalized.item_field_missing" in codes
    assert "personalized.reason_choices_missing" in codes
    assert "personalized.expected_reason_missing" in codes


def test_a_staged_item_may_not_also_ship_the_answer():
    # Staging the question server-side is only worth anything if the answer
    # stops travelling to the client.
    record = validate_personalized_lesson_descriptor(
        _descriptor(
            server_staged_reasoning=True,
            reason_choices=[
                {"id": "reach_c4", "label": "Reach c4."},
                {"id": "not_sure", "label": "I am not sure yet."},
            ],
            _expected_reason="reach_c4",
        )
    )
    assert not record.publishable
    assert "personalized.staged_reason_leaks_answer" in _codes(record)


def test_a_staged_item_still_needs_a_server_owned_grading_path():
    record = validate_personalized_lesson_descriptor(
        _descriptor(server_staged_reasoning=True, _expected_uci="")
    )
    assert not record.publishable
    assert "personalized.private_answer_missing" in _codes(record)


def test_every_endgame_lesson_is_publishable_again():
    # The regression this file exists for: all 20, not just the edited one.
    sys.path.insert(0, str(BACKEND / "tests"))
    from test_personalized_lesson_contract import _resolve

    unpublishable = []
    total = 0
    for category in get_all_categories():
        for lesson in category["lessons"]:
            total += 1
            record = validate_personalized_lesson_descriptor(
                _resolve("endgame", lesson["lesson_id"])
            )
            if not record.publishable:
                unpublishable.append((lesson["lesson_id"], _codes(record)))
    assert total == 20
    assert not unpublishable, unpublishable
