"""Default-off contracts for the Personalized Game Review Coach.

Phase 1 is deliberately inert: this module defines immutable values and pure
serializers only. It does not read MongoDB, select chess events, write learner
state, change an API response, or render UI. Future adapters must supply facts
from ``MoveTeachingDecision`` and canonical content services.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import os
import re
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

from services.detector_quality import (
    QualityGrade,
    QualitySurface,
    grade_for,
    is_authorized,
)
from services.caption_facts import (
    LegalMaterialLossCause,
    ReviewTeachingCause,
    VerifiedLineCause,
)


FEATURE_FLAG = "PERSONALIZED_GAME_REVIEW_COACH_ENABLED"
QUALITY_V2_FEATURE_FLAG = "PERSONALIZED_GAME_REVIEW_QUALITY_V2_ENABLED"
ROLLOUT_MODE_FLAG = "PERSONALIZED_GAME_REVIEW_COACH_ROLLOUT"
USER_FEATURE_FLAG = "personalized_game_review_coach"
CONTRACT_SCHEMA_VERSION = "personalized_game_review.v1"
_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
_ROLLOUT_MODES = frozenset({"validation", "all"})
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class ReviewContractViolation(ValueError):
    """Raised when a contract could overstate or leak coaching evidence."""


class ReviewPresentationMode(str, Enum):
    LEGACY = "legacy"
    PERSONALIZED = "personalized"


@dataclass(frozen=True)
class ReviewRolloutAccess:
    """Effective rollout state for one authenticated user."""

    enabled: bool
    comparison_allowed: bool
    rollout_mode: str


def personalized_game_review_access(
    user_doc: Optional[Mapping[str, Any]],
    env: Optional[Mapping[str, str]] = None,
) -> ReviewRolloutAccess:
    """Resolve master switch + existing per-user feature-flag authority."""
    source = os.environ if env is None else env
    rollout_mode = str(
        source.get(ROLLOUT_MODE_FLAG, "validation")
    ).strip().lower()
    if rollout_mode not in _ROLLOUT_MODES:
        rollout_mode = "invalid"

    master_enabled = personalized_game_review_enabled(source)
    user_flags = (
        (user_doc or {}).get("feature_flags") or {}
    ).get(USER_FEATURE_FLAG) or {}
    user_enabled = bool(
        isinstance(user_flags, Mapping) and user_flags.get("enabled") is True
    )
    enabled = bool(
        master_enabled
        and rollout_mode in _ROLLOUT_MODES
        and (rollout_mode == "all" or user_enabled)
    )
    comparison_allowed = bool(
        enabled
        and user_enabled
        and isinstance(user_flags, Mapping)
        and user_flags.get("validation_compare") is True
    )
    return ReviewRolloutAccess(
        enabled=enabled,
        comparison_allowed=comparison_allowed,
        rollout_mode=rollout_mode,
    )


def resolve_review_presentation_mode(
    access: ReviewRolloutAccess,
    requested_mode: Optional[str] = None,
) -> ReviewPresentationMode:
    """Honor a comparison mode only for explicitly approved validators."""
    if requested_mode is not None:
        try:
            requested = ReviewPresentationMode(str(requested_mode).strip().lower())
        except ValueError as exc:
            raise ReviewContractViolation("unknown review presentation mode") from exc
        if not access.comparison_allowed:
            raise ReviewContractViolation(
                "review comparison is not enabled for this account"
            )
        return requested
    return (
        ReviewPresentationMode.PERSONALIZED
        if access.enabled
        else ReviewPresentationMode.LEGACY
    )


class EventActor(str, Enum):
    USER = "user"
    OPPONENT = "opponent"


class EventOutcome(str, Enum):
    DEMONSTRATED = "demonstrated"
    MISSED = "missed"
    ALLOWED = "allowed"
    ANSWERED = "answered"
    NEUTRALIZED = "neutralized"
    INTRODUCED = "introduced"
    SILENT = "silent"


class ChapterRole(str, Enum):
    TURNING_POINT = "turning_point"
    DEMONSTRATED_KNOWLEDGE = "demonstrated_knowledge"
    OPPONENT_PLAN = "opponent_plan"
    MISSED_OPPORTUNITY = "missed_opportunity"
    KNOWLEDGE_GAP = "knowledge_gap"
    RECURRING_CONNECTION = "recurring_connection"
    REFLECTION = "reflection"


_PLAN_GRADE_ROLES = frozenset({ChapterRole.RECURRING_CONNECTION})


def personalized_game_review_enabled(
    env: Optional[Mapping[str, str]] = None,
) -> bool:
    """Return the default-off flag state without caching environment values."""
    source = os.environ if env is None else env
    return str(source.get(FEATURE_FLAG, "false")).strip().lower() in _TRUE_VALUES


def personalized_review_quality_v2_enabled(
    env: Optional[Mapping[str, str]] = None,
) -> bool:
    """Quality V2 is independently default-off under the existing master."""
    source = os.environ if env is None else env
    return bool(
        personalized_game_review_enabled(source)
        and str(source.get(QUALITY_V2_FEATURE_FLAG, "false")).strip().lower()
        in _TRUE_VALUES
    )


def _require_text(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ReviewContractViolation(f"{field_name} must be non-empty text")


def _optional_text(value: Optional[str], field_name: str) -> None:
    if value is not None:
        _require_text(value, field_name)


def _iso_utc(value: datetime) -> str:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ReviewContractViolation(
            "timestamps must be timezone-aware datetimes"
        )
    return value.isoformat()


@dataclass(frozen=True)
class MoveReference:
    ply: int
    number: int
    san: str
    actor: EventActor

    def __post_init__(self) -> None:
        if not isinstance(self.ply, int) or self.ply < 1:
            raise ReviewContractViolation("move.ply must be a positive integer")
        if not isinstance(self.number, int) or self.number < 1:
            raise ReviewContractViolation("move.number must be a positive integer")
        _require_text(self.san, "move.san")
        if not isinstance(self.actor, EventActor):
            raise ReviewContractViolation("move.actor must be an EventActor")

    def contract_dict(self) -> Dict[str, Any]:
        return {
            "ply": self.ply,
            "number": self.number,
            "san": self.san,
            "actor": self.actor.value,
        }


@dataclass(frozen=True)
class ConceptReference:
    concept_id: str
    content_ref: Optional[str] = None
    canonical_source: Optional[str] = None

    def __post_init__(self) -> None:
        _require_text(self.concept_id, "concept.id")
        _optional_text(self.content_ref, "concept.content_ref")
        _optional_text(self.canonical_source, "concept.canonical_source")
        if bool(self.content_ref) != bool(self.canonical_source):
            raise ReviewContractViolation(
                "content_ref and canonical_source must be supplied together"
            )

    def contract_dict(self) -> Dict[str, Optional[str]]:
        return {
            "id": self.concept_id,
            "content_ref": self.content_ref,
            "canonical_source": self.canonical_source,
        }


@dataclass(frozen=True)
class OpportunityEvidence:
    eligible: bool
    before: Optional[str] = None
    after: Optional[str] = None

    def __post_init__(self) -> None:
        if not isinstance(self.eligible, bool):
            raise ReviewContractViolation("opportunity.eligible must be boolean")
        _optional_text(self.before, "opportunity.before")
        _optional_text(self.after, "opportunity.after")

    def contract_dict(self) -> Dict[str, Any]:
        return {
            "eligible": self.eligible,
            "before": self.before,
            "after": self.after,
        }


@dataclass(frozen=True)
class EventEvidence:
    """Provenance plus authorization; the registry remains the grade owner."""

    quality_id: str
    source_version: str
    provenance: Tuple[str, ...]
    final_verified: bool

    def __post_init__(self) -> None:
        _require_text(self.quality_id, "evidence.quality_id")
        _require_text(self.source_version, "evidence.source_version")
        if not isinstance(self.provenance, tuple):
            raise ReviewContractViolation("evidence.provenance must be a tuple")
        if not self.provenance:
            raise ReviewContractViolation("evidence.provenance cannot be empty")
        for item in self.provenance:
            _require_text(item, "evidence.provenance entry")
        if not isinstance(self.final_verified, bool):
            raise ReviewContractViolation("evidence.final_verified must be boolean")

    @property
    def grade(self) -> QualityGrade:
        return grade_for(self.quality_id)

    def authorizes(self, surface: QualitySurface) -> bool:
        if not self.final_verified:
            return False
        return is_authorized(self.quality_id, surface)

    def contract_dict(self) -> Dict[str, Any]:
        return {
            "quality_id": self.quality_id,
            "grade": self.grade.value,
            "source_version": self.source_version,
            "provenance": list(self.provenance),
            "final_verified": self.final_verified,
            "authorized_surfaces": {
                "caption": self.authorizes(QualitySurface.CAPTION),
                "plan": self.authorizes(QualitySurface.PLAN),
                "mastery": self.authorizes(QualitySurface.MASTERY),
            },
        }


class RelationshipArrowRole(str, Enum):
    THREAT = "threat"
    SAFE_MOVE = "safe_move"
    OPPORTUNITY = "opportunity"


@dataclass(frozen=True)
class RelationshipArrow:
    origin: str
    destination: str
    role: RelationshipArrowRole

    def __post_init__(self) -> None:
        _require_text(self.origin, "relationship arrow origin")
        _require_text(self.destination, "relationship arrow destination")
        if not isinstance(self.role, RelationshipArrowRole):
            raise ReviewContractViolation("relationship arrow role is invalid")

    def contract_dict(self) -> Dict[str, str]:
        return {
            "from": self.origin,
            "to": self.destination,
            "role": self.role.value,
        }


@dataclass(frozen=True)
class VisualReference:
    arrows: Tuple[Tuple[str, str], ...] = ()
    highlights: Tuple[str, ...] = ()
    relationship_arrows: Tuple[RelationshipArrow, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.arrows, tuple) or not isinstance(
            self.highlights, tuple
        ):
            raise ReviewContractViolation("visual collections must be tuples")
        for arrow in self.arrows:
            if not isinstance(arrow, tuple) or len(arrow) != 2:
                raise ReviewContractViolation(
                    "each visual arrow must be an origin/destination tuple"
                )
            _require_text(arrow[0], "visual arrow origin")
            _require_text(arrow[1], "visual arrow destination")
        for square in self.highlights:
            _require_text(square, "visual highlight")
        if not isinstance(self.relationship_arrows, tuple) or any(
            not isinstance(item, RelationshipArrow)
            for item in self.relationship_arrows
        ):
            raise ReviewContractViolation(
                "relationship_arrows must contain RelationshipArrow values"
            )

    def contract_dict(self) -> Dict[str, Any]:
        payload = {
            "arrows": [list(arrow) for arrow in self.arrows],
            "highlights": list(self.highlights),
        }
        if self.relationship_arrows:
            payload["relationship_arrows"] = [
                item.contract_dict() for item in self.relationship_arrows
            ]
        return payload


@dataclass(frozen=True)
class TeachingReference:
    """Move-specific output only; canonical lesson content stays referenced."""

    caption: str = ""
    principle: str = ""
    visual: VisualReference = VisualReference()
    headline: str = ""
    practical_lead: str = ""
    cause_fingerprint: str = ""

    def __post_init__(self) -> None:
        if any(
            not isinstance(value, str)
            for value in (
                self.caption,
                self.principle,
                self.headline,
                self.practical_lead,
                self.cause_fingerprint,
            )
        ):
            raise ReviewContractViolation("teaching strings must be text")
        if not isinstance(self.visual, VisualReference):
            raise ReviewContractViolation("teaching.visual must be VisualReference")

    @property
    def is_empty(self) -> bool:
        return not (
            self.caption.strip()
            or self.principle.strip()
            or self.visual.arrows
            or self.visual.highlights
        )

    def contract_dict(self) -> Dict[str, Any]:
        payload = {
            "caption": self.caption,
            "principle": self.principle,
            "visual": self.visual.contract_dict(),
        }
        if self.headline:
            payload["headline"] = self.headline
        if self.practical_lead:
            payload["practical_lead"] = self.practical_lead
        if self.cause_fingerprint:
            if not _SHA256_RE.fullmatch(self.cause_fingerprint):
                raise ReviewContractViolation("cause_fingerprint must be SHA-256")
            payload["cause_fingerprint"] = self.cause_fingerprint
        return payload


class PracticalFrameKind(str, Enum):
    STAYED_WINNING = "stayed_winning"
    STATE_CHANGED = "state_changed"
    MATERIAL_MISSED = "material_missed"
    NEUTRAL = "neutral"


@dataclass(frozen=True)
class PracticalFrame:
    kind: PracticalFrameKind
    state_before: str
    state_after: str
    headline: str
    lead: str
    source: str = "caption_pipeline.practical_severity"

    def __post_init__(self) -> None:
        if not isinstance(self.kind, PracticalFrameKind):
            raise ReviewContractViolation("practical kind is invalid")
        for name in ("state_before", "state_after", "headline", "lead", "source"):
            _require_text(getattr(self, name), f"practical.{name}")

    def contract_dict(self) -> Dict[str, str]:
        return {
            "kind": self.kind.value,
            "state_before": self.state_before,
            "state_after": self.state_after,
            "headline": self.headline,
            "lead": self.lead,
            "source": self.source,
        }


@dataclass(frozen=True)
class TeachableEvent:
    """One immutable, authorized-or-shadow statement about a game moment."""

    event_id: str
    move: MoveReference
    concept: ConceptReference
    outcome: EventOutcome
    opportunity: OpportunityEvidence
    evidence: EventEvidence
    teaching: TeachingReference
    requested_surface: QualitySurface
    cause: Optional[ReviewTeachingCause] = None
    practical: Optional[PracticalFrame] = None
    reflection_eligible: bool = False

    def __post_init__(self) -> None:
        _require_text(self.event_id, "event_id")
        if not isinstance(self.move, MoveReference):
            raise ReviewContractViolation("move must be MoveReference")
        if not isinstance(self.concept, ConceptReference):
            raise ReviewContractViolation("concept must be ConceptReference")
        if not isinstance(self.outcome, EventOutcome):
            raise ReviewContractViolation("outcome must be EventOutcome")
        if not isinstance(self.opportunity, OpportunityEvidence):
            raise ReviewContractViolation("opportunity must be OpportunityEvidence")
        if not isinstance(self.evidence, EventEvidence):
            raise ReviewContractViolation("evidence must be EventEvidence")
        if not isinstance(self.teaching, TeachingReference):
            raise ReviewContractViolation("teaching must be TeachingReference")
        if self.cause is not None and not isinstance(
            self.cause, (LegalMaterialLossCause, VerifiedLineCause)
        ):
            raise ReviewContractViolation("cause must be a supported ReviewTeachingCause")
        if self.practical is not None and not isinstance(
            self.practical, PracticalFrame
        ):
            raise ReviewContractViolation("practical must be PracticalFrame")
        if bool(self.cause) != bool(self.practical):
            raise ReviewContractViolation(
                "cause and practical frame must be supplied together"
            )
        if not isinstance(self.requested_surface, QualitySurface):
            raise ReviewContractViolation(
                "requested_surface must be a QualitySurface"
            )
        if self.requested_surface not in (
            QualitySurface.DIAGNOSTIC,
            QualitySurface.CAPTION,
            QualitySurface.PLAN,
        ):
            raise ReviewContractViolation(
                "review events may request diagnostic, caption, or plan surfaces"
            )
        if not isinstance(self.reflection_eligible, bool):
            raise ReviewContractViolation("reflection_eligible must be boolean")

        if self.outcome == EventOutcome.SILENT:
            if self.requested_surface != QualitySurface.DIAGNOSTIC:
                raise ReviewContractViolation(
                    "silent events are diagnostic-only"
                )
            if self.reflection_eligible or not self.teaching.is_empty:
                raise ReviewContractViolation(
                    "silent events cannot teach or ask reflection"
                )
        elif self.requested_surface == QualitySurface.DIAGNOSTIC:
            if self.reflection_eligible:
                raise ReviewContractViolation(
                    "diagnostic-only events cannot ask reflection"
                )
        elif not self.evidence.authorizes(self.requested_surface):
            raise ReviewContractViolation(
                f"{self.evidence.quality_id} is not authorized for "
                f"{self.requested_surface.value}"
            )

        if self.reflection_eligible and not self.evidence.authorizes(
            QualitySurface.CAPTION
        ):
            raise ReviewContractViolation(
                "reflection requires Caption-grade verified evidence"
            )
        if self.cause is not None:
            if not self.evidence.authorizes(QualitySurface.CAPTION):
                raise ReviewContractViolation(
                    "V2 cause projection requires Caption-grade evidence"
                )
            if self.teaching.cause_fingerprint != self.cause.fingerprint:
                raise ReviewContractViolation(
                    "teaching and cause fingerprints disagree"
                )
            if (
                self.teaching.headline != self.practical.headline
                or self.teaching.practical_lead != self.practical.lead
            ):
                raise ReviewContractViolation(
                    "teaching and practical framing disagree"
                )
            if isinstance(self.cause, LegalMaterialLossCause):
                expected = (
                    RelationshipArrow(
                        self.cause.attacker.square,
                        self.cause.affected.square,
                        RelationshipArrowRole.THREAT,
                    ),
                    RelationshipArrow(
                        self.cause.best_move_from,
                        self.cause.best_move_to,
                        RelationshipArrowRole.SAFE_MOVE,
                    ),
                )
            else:
                expected = tuple(
                    RelationshipArrow(
                        item.origin,
                        item.destination,
                        RelationshipArrowRole(item.role),
                    )
                    for item in self.cause.relationships
                )
            if self.teaching.visual.relationship_arrows != expected:
                raise ReviewContractViolation(
                    "relationship arrows disagree with the cause"
                )

    @property
    def player_authorized(self) -> bool:
        return (
            self.outcome != EventOutcome.SILENT
            and self.requested_surface != QualitySurface.DIAGNOSTIC
            and self.evidence.authorizes(self.requested_surface)
        )

    def contract_dict(self) -> Dict[str, Any]:
        payload = {
            "schema_version": CONTRACT_SCHEMA_VERSION,
            "event_id": self.event_id,
            "move": self.move.contract_dict(),
            "concept": self.concept.contract_dict(),
            "outcome": self.outcome.value,
            "opportunity": self.opportunity.contract_dict(),
            "evidence": self.evidence.contract_dict(),
            "teaching": self.teaching.contract_dict(),
            "display": {
                "requested_surface": self.requested_surface.value,
                "authorized": self.player_authorized,
                "reflection_eligible": self.reflection_eligible,
            },
        }
        if self.cause is not None:
            payload["cause"] = self.cause.contract_dict()
            payload["practical"] = self.practical.contract_dict()
        return payload

    def player_dict(self) -> Dict[str, Any]:
        if not self.player_authorized:
            raise ReviewContractViolation(
                "shadow or silent events cannot be serialized for a player"
            )
        return self.contract_dict()


@dataclass(frozen=True)
class ReflectionOption:
    option_id: str
    label: str
    diagnosis_tag: Optional[str] = None

    def __post_init__(self) -> None:
        _require_text(self.option_id, "reflection option id")
        _require_text(self.label, "reflection option label")
        _optional_text(self.diagnosis_tag, "reflection diagnosis tag")

    def public_dict(self) -> Dict[str, str]:
        return {"id": self.option_id, "label": self.label}


@dataclass(frozen=True)
class ReflectionPrompt:
    prompt_id: str
    event_id: str
    question: str
    options: Tuple[ReflectionOption, ...]
    source_version: str

    def __post_init__(self) -> None:
        for field_name in ("prompt_id", "event_id", "question", "source_version"):
            _require_text(getattr(self, field_name), field_name)
        if not isinstance(self.options, tuple) or not self.options:
            raise ReviewContractViolation("reflection options must be a non-empty tuple")
        if any(not isinstance(item, ReflectionOption) for item in self.options):
            raise ReviewContractViolation(
                "reflection options must contain ReflectionOption values"
            )
        option_ids = tuple(item.option_id for item in self.options)
        if len(option_ids) != len(set(option_ids)):
            raise ReviewContractViolation("reflection option IDs must be unique")
        for required in ("not_sure", "none_of_these"):
            if required not in option_ids:
                raise ReviewContractViolation(
                    f"reflection options must include {required}"
                )

    @property
    def option_ids(self) -> Tuple[str, ...]:
        return tuple(item.option_id for item in self.options)

    def public_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": CONTRACT_SCHEMA_VERSION,
            "prompt_id": self.prompt_id,
            "event_id": self.event_id,
            "question": self.question,
            "options": [item.public_dict() for item in self.options],
            "input_mode": "options_only",
            "source_version": self.source_version,
        }


@dataclass(frozen=True)
class PlayerReflection:
    prompt_id: str
    event_id: str
    shown_option_ids: Tuple[str, ...]
    selected_option_id: str
    elapsed_ms: int
    answered_before_reveal: bool
    submitted_at: datetime

    def __post_init__(self) -> None:
        for field_name in ("prompt_id", "event_id", "selected_option_id"):
            _require_text(getattr(self, field_name), field_name)
        if not isinstance(self.shown_option_ids, tuple) or not self.shown_option_ids:
            raise ReviewContractViolation(
                "shown_option_ids must be a non-empty tuple"
            )
        if len(self.shown_option_ids) != len(set(self.shown_option_ids)):
            raise ReviewContractViolation("shown option IDs must be unique")
        if self.selected_option_id not in self.shown_option_ids:
            raise ReviewContractViolation(
                "selected option must have been shown"
            )
        if not isinstance(self.elapsed_ms, int) or self.elapsed_ms < 0:
            raise ReviewContractViolation("elapsed_ms must be a non-negative integer")
        if not isinstance(self.answered_before_reveal, bool):
            raise ReviewContractViolation(
                "answered_before_reveal must be boolean"
            )
        _iso_utc(self.submitted_at)

    def validate_against(self, prompt: ReflectionPrompt) -> None:
        if self.prompt_id != prompt.prompt_id or self.event_id != prompt.event_id:
            raise ReviewContractViolation(
                "reflection response does not match its prompt"
            )
        if self.shown_option_ids != prompt.option_ids:
            raise ReviewContractViolation(
                "stored shown options must exactly match the prompt"
            )

    def event_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": CONTRACT_SCHEMA_VERSION,
            "prompt_id": self.prompt_id,
            "event_id": self.event_id,
            "shown_option_ids": list(self.shown_option_ids),
            "selected_option_id": self.selected_option_id,
            "elapsed_ms": self.elapsed_ms,
            "answered_before_reveal": self.answered_before_reveal,
            "submitted_at": _iso_utc(self.submitted_at),
        }


@dataclass(frozen=True)
class PlanChapter:
    event_id: str
    role: ChapterRole
    content_ref: Optional[str] = None
    canonical_source: Optional[str] = None

    def __post_init__(self) -> None:
        _require_text(self.event_id, "chapter.event_id")
        if not isinstance(self.role, ChapterRole):
            raise ReviewContractViolation("chapter.role must be ChapterRole")
        _optional_text(self.content_ref, "chapter.content_ref")
        _optional_text(self.canonical_source, "chapter.canonical_source")
        if bool(self.content_ref) != bool(self.canonical_source):
            raise ReviewContractViolation(
                "chapter content_ref and canonical_source must be supplied together"
            )

    @property
    def required_surface(self) -> QualitySurface:
        if self.role in _PLAN_GRADE_ROLES:
            return QualitySurface.PLAN
        return QualitySurface.CAPTION

    def contract_dict(self) -> Dict[str, Optional[str]]:
        return {
            "event_id": self.event_id,
            "role": self.role.value,
            "content_ref": self.content_ref,
            "canonical_source": self.canonical_source,
        }


@dataclass(frozen=True)
class ReviewNextAction:
    source_event_id: str
    href: str
    action_kind: str
    content_kind: str
    content_id: str
    canonical_source: str

    def __post_init__(self) -> None:
        for field_name in (
            "source_event_id",
            "href",
            "action_kind",
            "content_kind",
            "content_id",
            "canonical_source",
        ):
            _require_text(getattr(self, field_name), f"next_action.{field_name}")
        if not self.href.startswith("/") or self.href.startswith("//"):
            raise ReviewContractViolation(
                "next_action.href must be an app-relative route"
            )

    def contract_dict(self) -> Dict[str, str]:
        return {
            "source_event_id": self.source_event_id,
            "href": self.href,
            "action_kind": self.action_kind,
            "content_kind": self.content_kind,
            "content_id": self.content_id,
            "canonical_source": self.canonical_source,
        }


@dataclass(frozen=True)
class GameTeachingPlan:
    """A game-level story containing references, never copied lesson bodies."""

    plan_id: str
    generated_at: datetime
    input_fingerprint: str
    opening_text: str
    game_arc: str
    chapters: Tuple[PlanChapter, ...]
    takeaway: str
    next_action: Optional[ReviewNextAction] = None
    rollout_mode: str = "shadow"

    def __post_init__(self) -> None:
        for field_name in ("plan_id", "opening_text", "game_arc", "takeaway"):
            _require_text(getattr(self, field_name), field_name)
        _iso_utc(self.generated_at)
        if not isinstance(self.input_fingerprint, str) or not _SHA256_RE.fullmatch(
            self.input_fingerprint
        ):
            raise ReviewContractViolation(
                "input_fingerprint must be a lowercase SHA-256 hex digest"
            )
        if not isinstance(self.chapters, tuple) or not self.chapters:
            raise ReviewContractViolation("plan chapters must be a non-empty tuple")
        if any(not isinstance(item, PlanChapter) for item in self.chapters):
            raise ReviewContractViolation("chapters must contain PlanChapter values")
        event_ids = tuple(item.event_id for item in self.chapters)
        if len(event_ids) != len(set(event_ids)):
            raise ReviewContractViolation("a plan cannot repeat the same event")
        if self.next_action is not None and not isinstance(
            self.next_action, ReviewNextAction
        ):
            raise ReviewContractViolation(
                "next_action must be ReviewNextAction or None"
            )
        if self.rollout_mode != "shadow":
            raise ReviewContractViolation(
                "Phase 1 plans must remain in shadow mode"
            )

    def validate_against(
        self,
        events: Mapping[str, TeachableEvent],
    ) -> None:
        for chapter in self.chapters:
            event = events.get(chapter.event_id)
            if event is None:
                raise ReviewContractViolation(
                    f"unknown chapter event: {chapter.event_id}"
                )
            if not event.evidence.authorizes(chapter.required_surface):
                raise ReviewContractViolation(
                    f"{chapter.event_id} lacks {chapter.required_surface.value} "
                    "authorization for its chapter role"
                )
            if not event.player_authorized:
                raise ReviewContractViolation(
                    f"{chapter.event_id} is diagnostic-only and cannot enter a plan"
                )

        if self.next_action is not None:
            if self.next_action.source_event_id not in {
                chapter.event_id for chapter in self.chapters
            }:
                raise ReviewContractViolation(
                    "next action must come from a selected chapter event"
                )
            event = events.get(self.next_action.source_event_id)
            if event is None:
                raise ReviewContractViolation(
                    "next action references an unknown event"
                )
            if not event.evidence.authorizes(QualitySurface.PLAN):
                raise ReviewContractViolation(
                    "a prescribed next action requires Plan-grade evidence"
                )

    def contract_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": CONTRACT_SCHEMA_VERSION,
            "plan_id": self.plan_id,
            "generated_at": _iso_utc(self.generated_at),
            "input_fingerprint": self.input_fingerprint,
            "opening": self.opening_text,
            "game_arc": self.game_arc,
            "chapters": [item.contract_dict() for item in self.chapters],
            "takeaway": self.takeaway,
            "next_action": (
                self.next_action.contract_dict() if self.next_action else None
            ),
            "rollout_mode": self.rollout_mode,
        }


def maybe_attach_game_teaching_plan(
    legacy_response: Dict[str, Any],
    plan: GameTeachingPlan,
    *,
    events: Mapping[str, TeachableEvent],
    env: Optional[Mapping[str, str]] = None,
) -> Dict[str, Any]:
    """Pure parity boundary; flag-off returns the original object unchanged."""
    if not personalized_game_review_enabled(env):
        return legacy_response
    plan.validate_against(events)
    augmented = dict(legacy_response)
    augmented["game_teaching_plan"] = plan.contract_dict()
    return augmented


def event_index(events: Sequence[TeachableEvent]) -> Dict[str, TeachableEvent]:
    """Create a deterministic event index and reject duplicate identities."""
    result: Dict[str, TeachableEvent] = {}
    for event in events:
        if not isinstance(event, TeachableEvent):
            raise ReviewContractViolation("event index accepts TeachableEvent values")
        if event.event_id in result:
            raise ReviewContractViolation(f"duplicate event_id: {event.event_id}")
        result[event.event_id] = event
    return result
