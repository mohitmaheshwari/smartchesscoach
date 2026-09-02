"""Semantic compatibility contract for resumable teaching sessions.

Cosmetic copy is intentionally excluded.  Chess content, grading, diagnosis,
proof, or assigned experimental form changes create a new fingerprint.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
from typing import Dict, Optional, Tuple


SCHEMA_VERSION = "lesson_session_compatibility.v1"


class SessionCompatibilityViolation(ValueError):
    pass


class ResumeAction(str, Enum):
    RESUME_CURRENT = "resume_current"
    FINISH_FROZEN = "finish_frozen"
    SUPERSEDE_AND_RESTART = "supersede_and_restart"


@dataclass(frozen=True)
class LessonCompatibilityDescriptor:
    lesson_kind: str
    lesson_id: str
    content_revision: str
    grader_version: str
    assigned_form: str
    diagnostic_version: Optional[str] = None
    proof_contract_version: Optional[str] = None
    cosmetic_revision: Optional[str] = None
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        required = (
            self.lesson_kind,
            self.lesson_id,
            self.content_revision,
            self.grader_version,
            self.assigned_form,
        )
        if not all(isinstance(value, str) and value.strip() for value in required):
            raise SessionCompatibilityViolation(
                "lesson identity, content, grader, and assigned form are required"
            )
        for value in (self.diagnostic_version, self.proof_contract_version):
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise SessionCompatibilityViolation(
                    "optional semantic versions must be absent or non-empty"
                )

    def semantic_payload(self) -> Dict[str, Optional[str]]:
        return {
            "schema_version": self.schema_version,
            "lesson_kind": self.lesson_kind,
            "lesson_id": self.lesson_id,
            "content_revision": self.content_revision,
            "grader_version": self.grader_version,
            "diagnostic_version": self.diagnostic_version,
            "proof_contract_version": self.proof_contract_version,
            "assigned_form": self.assigned_form,
        }

    @property
    def fingerprint(self) -> str:
        encoded = json.dumps(
            self.semantic_payload(), sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def changed_dimensions(
        self,
        other: "LessonCompatibilityDescriptor",
    ) -> Tuple[str, ...]:
        left = self.semantic_payload()
        right = other.semantic_payload()
        return tuple(sorted(key for key in left if left[key] != right[key]))

    def is_compatible_with(
        self,
        other: "LessonCompatibilityDescriptor",
    ) -> bool:
        return self.fingerprint == other.fingerprint


@dataclass(frozen=True)
class ResumeDecision:
    action: ResumeAction
    stored_fingerprint: str
    current_fingerprint: str
    changed_dimensions: Tuple[str, ...]
    reason: str


def decide_resume_action(
    stored: LessonCompatibilityDescriptor,
    current: LessonCompatibilityDescriptor,
    *,
    frozen_version_available: bool,
) -> ResumeDecision:
    changed = stored.changed_dimensions(current)
    if not changed:
        action = ResumeAction.RESUME_CURRENT
        reason = "semantic_contract_unchanged"
    elif frozen_version_available:
        action = ResumeAction.FINISH_FROZEN
        reason = "semantic_contract_changed_frozen_version_available"
    else:
        action = ResumeAction.SUPERSEDE_AND_RESTART
        reason = "semantic_contract_changed_no_safe_frozen_version"
    return ResumeDecision(
        action=action,
        stored_fingerprint=stored.fingerprint,
        current_fingerprint=current.fingerprint,
        changed_dimensions=changed,
        reason=reason,
    )
