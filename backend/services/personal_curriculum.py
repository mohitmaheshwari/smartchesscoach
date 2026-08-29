"""Default-off Personal Curriculum contracts and Phase 4 read adapter.

The pure contracts validate the signed evidence rules. The Phase 4 adapter
composes those contracts from existing focus, knowledge, lesson, and memory
owners; it never copies lesson content or writes a mastery verdict.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
import os
from typing import Any, Dict, Mapping, Optional, Tuple

from services.detector_quality import QualitySurface, is_authorized


FEATURE_FLAG = "PERSONAL_CURRICULUM_ENABLED"
CURRICULUM_SCHEMA_VERSION = "personal_curriculum.v1"
LESSON_RESULT_SCHEMA_VERSION = "lesson_result.v1"
CURRICULUM_SURFACE_SCHEMA_VERSION = "personal_curriculum.surface.v1"
ROLLOUT_ROLES_ENV = "PERSONAL_CURRICULUM_ROLES"
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


def personal_curriculum_rollout_roles(
    env: Optional[Mapping[str, str]] = None,
) -> set[str]:
    source = os.environ if env is None else env
    raw = str(source.get(ROLLOUT_ROLES_ENV, "admin,super_admin"))
    return {role.strip() for role in raw.split(",") if role.strip()}


def personal_curriculum_eligible(
    user_role: Optional[str],
    env: Optional[Mapping[str, str]] = None,
) -> bool:
    return (
        personal_curriculum_enabled(env)
        and bool(user_role)
        and user_role in personal_curriculum_rollout_roles(env)
    )


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
        identity = "|".join((
            self.primary.outcome.value,
            self.primary.destination.content_kind,
            self.primary.destination.content_id,
            self.review.destination.content_id if self.review else "",
        ))
        decision_id = "pcv1:" + hashlib.sha256(
            identity.encode("utf-8")
        ).hexdigest()[:16]
        return {
            "schema_version": CURRICULUM_SCHEMA_VERSION,
            "decision_id": decision_id,
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


def _focus_occurrence_count(focus: Mapping[str, Any]) -> int:
    sources = (
        focus.get("baseline_metric") or {},
        ((focus.get("evidence_summary") or {}).get("baseline") or {}),
    )
    for source in sources:
        for key in ("occurrence_count", "count", "misses", "value"):
            value = source.get(key) if isinstance(source, Mapping) else None
            if isinstance(value, (int, float)):
                return max(0, int(value))
    return 0


def _repair_candidate(focus: Mapping[str, Any]) -> Optional[CurriculumCandidate]:
    topic_key = str(focus.get("topic_key") or "").strip()
    occurrence_count = _focus_occurrence_count(focus)
    if not topic_key or occurrence_count < 3:
        return None
    label = str(
        focus.get("topic_label")
        or topic_key.replace("_", " ").title()
    )
    reason = str(
        focus.get("coaching_narrative")
        or "This has appeared several times in your recent games."
    )
    return CurriculumCandidate(
        outcome=CurriculumOutcome.REPAIR,
        student_state=StudentState.LEARNING,
        title=label,
        reason=reason,
        evidence_summary="I found this in several of your recent games.",
        evidence_status=EvidenceStatus.TRUSTWORTHY,
        destination=CurriculumDestination(
            href=f"/training/pattern/{topic_key}",
            medium="puzzles",
            capability=LessonCapability.GUIDED_PRACTICE,
            content_kind="concept",
            content_id=topic_key,
            canonical_source="user_active_focus via services/focus_bridge.py",
        ),
        evidence_owner="user_active_focus via services/focus_bridge.py",
        evidence_ref=str(focus.get("focus_id") or "") or None,
        detector_quality_id=(
            str(focus.get("detector_quality_id"))
            if focus.get("detector_quality_id")
            else None
        ),
    )


def _knowledge_destination(
    focus: Mapping[str, Any],
    action: Mapping[str, Any],
) -> CurriculumDestination:
    kind = str(focus.get("e2_kind") or focus.get("kind") or "concept")
    content_ref = str(focus.get("content_ref") or "")
    if kind == "endgame":
        return resolve_endgame_destination(
            content_ref,
            capability=LessonCapability.TEACH,
        )
    return CurriculumDestination(
        href=str(action.get("href") or "/play-with-coach"),
        medium=str(action.get("medium") or "lesson"),
        capability=LessonCapability.TEACH,
        content_kind=kind,
        content_id=str(focus.get("skill_id") or content_ref),
        canonical_source="backend/data/coaching/skill_tree.json",
    )


def _knowledge_candidate(
    focus: Mapping[str, Any],
    *,
    band_name: str,
) -> CurriculumCandidate:
    from services.today_composer import _action_for_band

    stats = focus.get("stats") or {}
    seen = max(0, int(stats.get("seen") or 0))
    failed = max(0, int(stats.get("failed") or 0))
    if seen:
        reason = (
            "This has started to show up in your games. "
            "Now is a good time to learn it."
        )
        evidence = "I have seen this once or twice, and now is a good time to work on it."
        evidence_status = EvidenceStatus.SPARSE
    else:
        reason = (
            "This is a useful next idea for your level. "
            "I have not seen enough of it in your games to judge it yet."
        )
        evidence = (
            "I am suggesting it because it helps at your level, "
            "not because you made a mistake."
        )
        evidence_status = EvidenceStatus.NOT_MEASURED
    if failed:
        reason = (
            "This has started to cause trouble in your games. "
            "Let us learn it before it becomes a habit."
        )
    action = _action_for_band(band_name, dict(focus))
    return CurriculumCandidate(
        outcome=CurriculumOutcome.EXPAND,
        student_state=StudentState.LEARNING if seen else StudentState.NEW,
        title=str(focus.get("label") or "Your next chess idea"),
        reason=reason,
        evidence_summary=evidence,
        evidence_status=evidence_status,
        destination=_knowledge_destination(focus, action),
        evidence_owner="coach_memory.learning.skills",
        evidence_ref=str(focus.get("skill_id") or "") or None,
    )


def _observe_candidate(analyzed_games: int) -> CurriculumCandidate:
    remaining = max(1, 5 - analyzed_games)
    reason = (
        f"Play or import {remaining} more game"
        f"{'' if remaining == 1 else 's'} so I can choose from your own play."
    )
    return CurriculumCandidate(
        outcome=CurriculumOutcome.OBSERVE,
        student_state=StudentState.NEW,
        title="Let me learn how you play",
        reason=reason,
        evidence_summary=(
            "I have not seen enough of your games to choose a personal lesson yet."
        ),
        evidence_status=EvidenceStatus.SPARSE,
        destination=CurriculumDestination(
            href="/play-with-coach",
            medium="live_game",
            capability=LessonCapability.DIAGNOSTIC,
            content_kind="diagnostic",
            content_id="coached_game",
            canonical_source="coach game session",
        ),
        evidence_owner="games",
    )


def _evidence_watermark(
    primary: CurriculumCandidate,
    *,
    analyzed_games: int,
    focus: Optional[Mapping[str, Any]],
    knowledge: Optional[Mapping[str, Any]],
) -> str:
    payload = {
        "outcome": primary.outcome.value,
        "content": primary.content_identity,
        "games": min(analyzed_games, 5),
        "focus_id": (focus or {}).get("focus_id"),
        "focus_started": (focus or {}).get("started_at"),
        "focus_count": _focus_occurrence_count(focus or {}),
        "knowledge_stats": (knowledge or {}).get("stats") or {},
    }
    encoded = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:20]


async def _persist_active_plan(
    db,
    user_id: str,
    *,
    decision: Mapping[str, Any],
    primary: CurriculumCandidate,
    evidence_watermark: str,
    now: datetime,
) -> Dict[str, Any]:
    from services.coach_memory import get_or_create_memory

    await get_or_create_memory(db, user_id)
    memory_doc = await db.coach_memory.find_one(
        {"user_id": user_id},
        {"_id": 0, "learning.active_curriculum": 1},
    )
    existing = (
        ((memory_doc or {}).get("learning") or {}).get("active_curriculum")
        or {}
    )
    selected_at = (
        existing.get("selected_at")
        if (
            existing.get("decision_id") == decision["decision_id"]
            and existing.get("evidence_watermark") == evidence_watermark
        )
        else _iso_utc(now)
    )
    reference = {
        "decision_id": decision["decision_id"],
        "outcome": primary.outcome.value,
        "content_kind": primary.destination.content_kind,
        "content_id": primary.destination.content_id,
        "selected_at": selected_at,
        "evidence_watermark": evidence_watermark,
        "resume_destination": primary.destination.href,
    }
    if existing != reference:
        await db.coach_memory.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "learning.active_curriculum": reference,
                    "updated_at": _iso_utc(now),
                }
            },
        )
    return reference


async def build_player_curriculum(
    db,
    user_id: str,
    *,
    generated_at: Optional[datetime] = None,
    env: Optional[Mapping[str, str]] = None,
) -> Dict[str, Any]:
    """Compose the one read-only Phase 4 decision shared by Home and Learn."""
    now = generated_at or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ContractViolation("generated_at must be timezone-aware")

    user_doc = await db.users.find_one(
        {"user_id": user_id},
        {"_id": 0, "role": 1},
    )
    role = (user_doc or {}).get("role")
    if not personal_curriculum_enabled(env):
        return {
            "enabled": False,
            "schema_version": CURRICULUM_SURFACE_SCHEMA_VERSION,
            "rollout": {"eligible": False, "reason": "flag_disabled"},
        }
    if not personal_curriculum_eligible(role, env):
        return {
            "enabled": False,
            "schema_version": CURRICULUM_SURFACE_SCHEMA_VERSION,
            "rollout": {"eligible": False, "reason": "role_not_enabled"},
        }

    analyzed_games = await db.games.count_documents(
        {"user_id": user_id, "is_analyzed": True}
    )
    focus = None
    knowledge = None
    primary = None
    if analyzed_games >= 5:
        from services.focus_bridge import get_active_focus_bundle
        from services.today_composer import (
            _detect_band,
            pick_knowledge_focus,
        )

        focus = await get_active_focus_bundle(db, user_id)
        primary = _repair_candidate(focus or {})
        knowledge = await pick_knowledge_focus(db, user_id)
        if primary is None and knowledge is not None:
            primary = _knowledge_candidate(
                knowledge,
                band_name=await _detect_band(db, user_id),
            )
    if primary is None:
        primary = _observe_candidate(analyzed_games)

    decision = build_curriculum_decision(primary, generated_at=now)
    naturally_next = None
    if primary.outcome == CurriculumOutcome.REPAIR and knowledge is not None:
        next_candidate = _knowledge_candidate(
            knowledge,
            band_name=str((focus or {}).get("rating_band") or "beginner_high"),
        )
        naturally_next = {
            "title": next_candidate.title,
            "reason": "We will return to this after your current focus.",
            "destination": next_candidate.destination.public_dict(),
        }

    watermark = _evidence_watermark(
        primary,
        analyzed_games=analyzed_games,
        focus=focus,
        knowledge=knowledge,
    )
    active_plan = await _persist_active_plan(
        db,
        user_id,
        decision=decision,
        primary=primary,
        evidence_watermark=watermark,
        now=now,
    )
    return {
        "enabled": True,
        "schema_version": CURRICULUM_SURFACE_SCHEMA_VERSION,
        "decision": decision,
        "naturally_next": naturally_next,
        "active_plan": {
            "decision_id": active_plan["decision_id"],
            "selected_at": active_plan["selected_at"],
        },
        "rollout": {"eligible": True, "reason": "enabled_for_role"},
    }


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
