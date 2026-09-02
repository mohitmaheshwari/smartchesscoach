from __future__ import annotations

from dataclasses import replace

import pytest

from services.lesson_session_compatibility import (
    LessonCompatibilityDescriptor,
    ResumeAction,
    SessionCompatibilityViolation,
    decide_resume_action,
)


def _descriptor(**changes) -> LessonCompatibilityDescriptor:
    values = {
        "lesson_kind": "concept",
        "lesson_id": "piece_safety.simple_hang",
        "content_revision": "content.v1",
        "grader_version": "grader.v2",
        "diagnostic_version": "diagnostic.v2",
        "proof_contract_version": "proof.v1",
        "assigned_form": "a",
        "cosmetic_revision": "copy.v1",
    }
    values.update(changes)
    return LessonCompatibilityDescriptor(**values)


def test_fingerprint_is_stable_and_ignores_cosmetic_copy_changes():
    first = _descriptor(cosmetic_revision="copy.v1")
    second = _descriptor(cosmetic_revision="copy.v99")

    assert first.fingerprint == second.fingerprint
    assert first.changed_dimensions(second) == ()
    assert first.is_compatible_with(second) is True


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("lesson_kind", "endgame"),
        ("lesson_id", "king_and_pawn/opposition"),
        ("content_revision", "content.v2"),
        ("grader_version", "grader.v3"),
        ("diagnostic_version", "diagnostic.v3"),
        ("proof_contract_version", "proof.v2"),
        ("assigned_form", "b"),
    ],
)
def test_every_semantic_change_invalidates_resume(field, replacement):
    stored = _descriptor()
    current = replace(stored, **{field: replacement})

    assert stored.fingerprint != current.fingerprint
    assert field in stored.changed_dimensions(current)
    assert stored.is_compatible_with(current) is False


def test_compatible_session_resumes_current_contract():
    stored = _descriptor()
    decision = decide_resume_action(
        stored, _descriptor(cosmetic_revision="new-copy"),
        frozen_version_available=False,
    )
    assert decision.action == ResumeAction.RESUME_CURRENT
    assert decision.changed_dimensions == ()


def test_changed_session_finishes_frozen_version_when_available():
    stored = _descriptor()
    decision = decide_resume_action(
        stored,
        replace(stored, proof_contract_version="proof.v2"),
        frozen_version_available=True,
    )
    assert decision.action == ResumeAction.FINISH_FROZEN
    assert decision.changed_dimensions == ("proof_contract_version",)


def test_changed_session_supersedes_when_frozen_version_is_unavailable():
    stored = _descriptor()
    decision = decide_resume_action(
        stored,
        replace(stored, grader_version="grader.v3"),
        frozen_version_available=False,
    )
    assert decision.action == ResumeAction.SUPERSEDE_AND_RESTART
    assert decision.reason == "semantic_contract_changed_no_safe_frozen_version"


def test_empty_semantic_version_is_rejected():
    with pytest.raises(SessionCompatibilityViolation, match="optional semantic"):
        _descriptor(proof_contract_version="")
