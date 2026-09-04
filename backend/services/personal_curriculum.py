"""Default-off Personal Curriculum contracts.

Phase 3 deliberately stops before database adapters or player-facing routes.
This module accepts already-normalized evidence candidates, validates the
signed product gates, and emits one deterministic public decision. It does not
rank raw Mongo records, copy lesson content, or write a mastery verdict.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import os
from typing import Any, Dict, Mapping, Optional, Tuple

from services.detector_quality import QualitySurface, is_authorized


FEATURE_FLAG = "PERSONAL_CURRICULUM_ENABLED"
CURRICULUM_SCHEMA_VERSION = "personal_curriculum.v1"
LESSON_RESULT_SCHEMA_VERSION = "lesson_result.v1"
PIC_SKILL_ID = "piece_safety_simple_hang"
PIC_CONTENT_KIND = "concept"
PIC_CONTENT_ID = "piece_safety.simple_hang"
PIC_CANONICAL_SOURCE = "personal_curriculum.piece_safety.v1"
PIC_LESSON_ID = "pic-piece-safety-v1"
_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})


class ContractViolation(ValueError):
    """Raised when an adapter attempts to overstate curriculum evidence."""


class CurriculumOutcome(str, Enum):
    OBSERVE = "observe"
    REPAIR = "repair"
    EXPAND = "expand"
    CONTINUE = "continue"
    REVIEW = "review"
    APPLY = "apply"


class StudentState(str, Enum):
    NEW = "new"
    LEARNING = "learning"
    CAN_DO_WITH_HELP = "can_do_with_help"
    CAN_DO_ALONE = "can_do_alone"
    USED_IN_GAMES = "used_in_games"
    RELIABLE = "reliable"


class EvidenceStatus(str, Enum):
    TRUSTWORTHY = "trustworthy"
    SPARSE = "sparse"
    STALE = "stale"
    CONFLICTING = "conflicting"
    NOT_MEASURED = "not_measured"


class LessonCapability(str, Enum):
    DIAGNOSTIC = "diagnostic"
    TEACH = "teach"
    GUIDED_PRACTICE = "guided_practice"
    INDEPENDENT_PRACTICE = "independent_practice"
    REVIEW = "review"
    COACHED_APPLICATION = "coached_application"


class AttemptKind(str, Enum):
    EXPLANATION = "explanation"
    GUIDED = "guided"
    INDEPENDENT = "independent"
    REVIEW = "review"
    APPLICATION = "application"


class AssistanceKind(str, Enum):
    HINT = "hint"
    CORRECTION = "correction"
    GUIDED_LINE = "guided_line"
    ANSWER_REVEALED = "answer_revealed"


class ApplicationOutcome(str, Enum):
    NOT_MEASURED = "not_measured"
    APPLIED = "applied"
    MISSED = "missed"
    DID_NOT_OCCUR = "did_not_occur"
    UNCLEAR = "unclear"


def personal_curriculum_enabled(
    env: Optional[Mapping[str, str]] = None,
) -> bool:
    """Return the default-off backend flag state."""
    source = os.environ if env is None else env
    return str(source.get(FEATURE_FLAG, "false")).strip().lower() in _TRUE_VALUES


def _require_text(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ContractViolation(f"{field_name} must be non-empty text")


def _iso_utc(value: datetime) -> str:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ContractViolation("timestamps must be timezone-aware datetimes")
    return value.isoformat()


def _application_claim_authorized(quality_id: Optional[str]) -> bool:
    return bool(
        quality_id
        and is_authorized(str(quality_id), QualitySurface.MASTERY)
    )


@dataclass(frozen=True)
class CurriculumDestination:
    """A route to canonical content; never a copy of the lesson itself."""

    href: str
    medium: str
    capability: LessonCapability
    content_kind: str
    content_id: str
    canonical_source: str

    def __post_init__(self) -> None:
        _require_text(self.href, "destination.href")
        if not self.href.startswith("/"):
            raise ContractViolation("destination.href must be an app-relative route")
        _require_text(self.medium, "destination.medium")
        _require_text(self.content_kind, "destination.content_kind")
        _require_text(self.content_id, "destination.content_id")
        _require_text(self.canonical_source, "destination.canonical_source")
        if not isinstance(self.capability, LessonCapability):
            raise ContractViolation("destination.capability must be a LessonCapability")

    def public_dict(self) -> Dict[str, str]:
        return {
            "href": self.href,
            "medium": self.medium,
            "capability": self.capability.value,
            "lesson_kind": self.content_kind,
            "lesson_id": self.content_id,
        }


@dataclass(frozen=True)
class CurriculumCandidate:
    """One already-selected candidate plus private evidence provenance."""

    outcome: CurriculumOutcome
    student_state: StudentState
    title: str
    reason: str
    evidence_summary: str
    evidence_status: EvidenceStatus
    destination: CurriculumDestination
    evidence_owner: str
    evidence_ref: Optional[str] = None
    detector_quality_id: Optional[str] = None

    def __post_init__(self) -> None:
        if not isinstance(self.outcome, CurriculumOutcome):
            raise ContractViolation("outcome must be a CurriculumOutcome")
        if not isinstance(self.student_state, StudentState):
            raise ContractViolation("student_state must be a StudentState")
        if not isinstance(self.evidence_status, EvidenceStatus):
            raise ContractViolation("evidence_status must be an EvidenceStatus")
        if not isinstance(self.destination, CurriculumDestination):
            raise ContractViolation("destination must be a CurriculumDestination")
        for field_name in ("title", "reason", "evidence_summary", "evidence_owner"):
            _require_text(getattr(self, field_name), field_name)

        if self.student_state == StudentState.RELIABLE:
            raise ContractViolation(
                "Reliable is not available until its delayed-recall and "
                "application thresholds are data-locked"
            )
        if (
            self.outcome in (CurriculumOutcome.REPAIR, CurriculumOutcome.APPLY)
            and self.evidence_status != EvidenceStatus.TRUSTWORTHY
        ):
            raise ContractViolation(
                "Repair and application decisions require trustworthy evidence"
            )
        if (
            self.outcome == CurriculumOutcome.APPLY
            or self.student_state == StudentState.USED_IN_GAMES
        ) and not _application_claim_authorized(self.detector_quality_id):
            raise ContractViolation(
                "Application claims require a Plan-grade opportunity detector"
            )

    @property
    def content_identity(self) -> Tuple[str, str]:
        return (
            self.destination.content_kind,
            self.destination.content_id,
        )

    def public_dict(self) -> Dict[str, Any]:
        """Return the player-response shape without internal evidence IDs."""
        return {
            "outcome": self.outcome.value,
            "state": self.student_state.value,
            "title": self.title,
            "reason": self.reason,
            "evidence": self.evidence_summary,
            "destination": self.destination.public_dict(),
        }


@dataclass(frozen=True)
class ComposedCurriculumDecision:
    primary: CurriculumCandidate
    generated_at: datetime
    review: Optional[CurriculumCandidate] = None

    def __post_init__(self) -> None:
        if not isinstance(self.primary, CurriculumCandidate):
            raise ContractViolation("primary must be a CurriculumCandidate")
        _iso_utc(self.generated_at)
        if self.review is not None:
            if not isinstance(self.review, CurriculumCandidate):
                raise ContractViolation("review must be a CurriculumCandidate")
            if self.review.outcome != CurriculumOutcome.REVIEW:
                raise ContractViolation(
                    "the optional secondary item must have the review outcome"
                )
            if self.review.content_identity == self.primary.content_identity:
                raise ContractViolation(
                    "primary and review cannot point to the same lesson"
                )

    def public_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": CURRICULUM_SCHEMA_VERSION,
            "generated_at": _iso_utc(self.generated_at),
            "primary": self.primary.public_dict(),
            "review": self.review.public_dict() if self.review else None,
            "plan_rules": {
                "primary_items": 1,
                "maximum_review_items": 1,
                "explore_replaces_plan": False,
            },
        }


def build_curriculum_decision(
    primary: CurriculumCandidate,
    *,
    generated_at: datetime,
    review: Optional[CurriculumCandidate] = None,
) -> Dict[str, Any]:
    """Pure contract builder used by stateless probes and future adapters."""
    return ComposedCurriculumDecision(
        primary=primary,
        review=review,
        generated_at=generated_at,
    ).public_dict()


def compose_personal_curriculum(
    primary: CurriculumCandidate,
    *,
    generated_at: datetime,
    review: Optional[CurriculumCandidate] = None,
    env: Optional[Mapping[str, str]] = None,
) -> Optional[Dict[str, Any]]:
    """Default-off entry point. Flag-off callers receive no replacement."""
    if not personal_curriculum_enabled(env):
        return None
    return build_curriculum_decision(
        primary,
        review=review,
        generated_at=generated_at,
    )


def resolve_endgame_destination(
    content_ref: str,
    *,
    capability: LessonCapability,
) -> CurriculumDestination:
    """Resolve an endgame reference through its canonical owner."""
    from services.endgame_theory_service import resolve_content_ref

    resolved = resolve_content_ref(content_ref)
    if not resolved:
        raise ContractViolation(
            f"unknown canonical endgame content reference: {content_ref}"
        )
    return CurriculumDestination(
        href=resolved["href"],
        medium="lesson",
        capability=capability,
        content_kind="endgame",
        content_id=resolved["lesson_id"],
        canonical_source=resolved["canonical_source"],
    )


@dataclass(frozen=True)
class LessonResult:
    """Shared evidence event emitted by future lesson adapters."""

    content_kind: str
    content_id: str
    canonical_source: str
    attempt_kind: AttemptKind
    occurred_at: datetime
    correct: Optional[bool] = None
    assistance: Tuple[AssistanceKind, ...] = ()
    position_id: Optional[str] = None
    board_verified: bool = False
    distinct_position: bool = False
    application_outcome: ApplicationOutcome = ApplicationOutcome.NOT_MEASURED
    detector_quality_id: Optional[str] = None
    source_event_id: Optional[str] = None

    def __post_init__(self) -> None:
        for field_name in ("content_kind", "content_id", "canonical_source"):
            _require_text(getattr(self, field_name), field_name)
        if not isinstance(self.attempt_kind, AttemptKind):
            raise ContractViolation("attempt_kind must be an AttemptKind")
        if not isinstance(self.application_outcome, ApplicationOutcome):
            raise ContractViolation(
                "application_outcome must be an ApplicationOutcome"
            )
        _iso_utc(self.occurred_at)
        if any(not isinstance(item, AssistanceKind) for item in self.assistance):
            raise ContractViolation("assistance entries must be AssistanceKind values")
        if self.source_event_id is not None:
            _require_text(self.source_event_id, "source_event_id")
        if self.attempt_kind in (
            AttemptKind.GUIDED,
            AttemptKind.INDEPENDENT,
            AttemptKind.REVIEW,
        ):
            _require_text(self.position_id or "", "position_id")
        if self.attempt_kind == AttemptKind.APPLICATION:
            if self.correct is not None:
                raise ContractViolation(
                    "application evidence uses application_outcome, not correct"
                )
            if self.application_outcome == ApplicationOutcome.NOT_MEASURED:
                raise ContractViolation(
                    "application attempts require an explicit opportunity outcome"
                )
        elif self.application_outcome != ApplicationOutcome.NOT_MEASURED:
            raise ContractViolation(
                "only application attempts may carry an application outcome"
            )

    def earned_state(self) -> Optional[StudentState]:
        """Return only the state this single event can honestly prove."""
        if self.attempt_kind == AttemptKind.EXPLANATION:
            return StudentState.LEARNING

        if self.attempt_kind == AttemptKind.APPLICATION:
            if (
                self.application_outcome == ApplicationOutcome.APPLIED
                and _application_claim_authorized(self.detector_quality_id)
            ):
                return StudentState.USED_IN_GAMES
            return None

        if self.correct is not True:
            return StudentState.LEARNING

        if self.attempt_kind == AttemptKind.GUIDED:
            return StudentState.CAN_DO_WITH_HELP

        if self.assistance:
            return StudentState.CAN_DO_WITH_HELP

        if self.board_verified and self.distinct_position:
            return StudentState.CAN_DO_ALONE

        return StudentState.LEARNING

    def event_dict(self) -> Dict[str, Any]:
        earned = self.earned_state()
        return {
            "schema_version": LESSON_RESULT_SCHEMA_VERSION,
            "lesson": {
                "kind": self.content_kind,
                "id": self.content_id,
                "canonical_source": self.canonical_source,
            },
            "attempt": {
                "kind": self.attempt_kind.value,
                "correct": self.correct,
                "assistance": [item.value for item in self.assistance],
                "position_id": self.position_id,
                "board_verified": self.board_verified,
                "distinct_position": self.distinct_position,
            },
            "application": {
                "outcome": self.application_outcome.value,
                "detector_quality_id": self.detector_quality_id,
                "plan_authorized": _application_claim_authorized(
                    self.detector_quality_id
                ),
            },
            "occurred_at": _iso_utc(self.occurred_at),
            "source_event_id": self.source_event_id,
            "earned_state": earned.value if earned else None,
        }

    @classmethod
    def from_event_dict(cls, payload: Mapping[str, Any]) -> "LessonResult":
        """Rehydrate stored evidence and reject forged earned-state claims."""
        if payload.get("schema_version") != LESSON_RESULT_SCHEMA_VERSION:
            raise ContractViolation("unsupported lesson result schema")
        lesson = payload.get("lesson")
        attempt = payload.get("attempt")
        application = payload.get("application")
        if not all(isinstance(item, Mapping) for item in (lesson, attempt, application)):
            raise ContractViolation("lesson result sections are incomplete")
        occurred_at = str(payload.get("occurred_at") or "")
        try:
            parsed_at = datetime.fromisoformat(occurred_at.replace("Z", "+00:00"))
        except (TypeError, ValueError) as exc:
            raise ContractViolation("lesson result occurred_at is invalid") from exc
        try:
            result = cls(
                content_kind=str(lesson.get("kind") or ""),
                content_id=str(lesson.get("id") or ""),
                canonical_source=str(lesson.get("canonical_source") or ""),
                attempt_kind=AttemptKind(str(attempt.get("kind") or "")),
                occurred_at=parsed_at,
                correct=attempt.get("correct"),
                assistance=tuple(
                    AssistanceKind(str(item))
                    for item in (attempt.get("assistance") or [])
                ),
                position_id=attempt.get("position_id"),
                board_verified=bool(attempt.get("board_verified")),
                distinct_position=bool(attempt.get("distinct_position")),
                application_outcome=ApplicationOutcome(
                    str(application.get("outcome") or "")
                ),
                detector_quality_id=application.get("detector_quality_id"),
                source_event_id=payload.get("source_event_id"),
            )
        except (TypeError, ValueError) as exc:
            raise ContractViolation("lesson result enum value is invalid") from exc
        earned = result.earned_state()
        recomputed = earned.value if earned else None
        if payload.get("earned_state") != recomputed:
            raise ContractViolation("stored earned_state does not match evidence")
        return result
