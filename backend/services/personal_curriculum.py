"""Default-off Personal Curriculum contracts and Phase 4 read adapter.

The pure contracts validate the signed evidence rules. The Phase 4 adapter
composes those contracts from existing focus, knowledge, lesson, and memory
owners; it never copies lesson content or writes a mastery verdict.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from enum import Enum
import hashlib
import json
import os
from typing import Any, Dict, Mapping, Optional, Tuple
from urllib.parse import urlencode

from services.detector_quality import QualitySurface, is_authorized


FEATURE_FLAG = "PERSONAL_CURRICULUM_ENABLED"
PERSONALIZED_TEACHING_FEATURE_FLAG = "PERSONALIZED_TEACHING_ENABLED"
CURRICULUM_SCHEMA_VERSION = "personal_curriculum.v1"
LESSON_RESULT_SCHEMA_VERSION = "lesson_result.v2"
CURRICULUM_SURFACE_SCHEMA_VERSION = "personal_curriculum.surface.v1"
HOME_DIAGNOSTIC_SCHEMA_VERSION = "home_replay_diagnostic.result.v1"
HOME_DIAGNOSTIC_FEATURE_FLAG = "HOME_REPLAY_DIAGNOSTIC_ENABLED"
ROLLOUT_ROLES_ENV = "PERSONAL_CURRICULUM_ROLES"
PIC_SKILL_ID = "piece_safety_simple_hang"

PIC_CONTENT_KIND = "concept"

PIC_CONTENT_ID = "piece_safety.simple_hang"

PIC_CANONICAL_SOURCE = "personal_curriculum.piece_safety.v1"

# Version of the canonical PIC concept identity above. LessonResult v2
# requires the content version to travel with every evidence event so stored
# attempts cannot silently attach to a later lesson revision.
PIC_CONTENT_VERSION = "1"

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


class TeachingStage(str, Enum):
    DIAGNOSE = "diagnose"
    NOTICE = "notice"
    EXPLAIN = "explain"
    CONTRAST = "contrast"
    GUIDE = "guide"
    RECALL = "recall"
    MIX = "mix"
    TRANSFER = "transfer"
    APPLY = "apply"
    RETAIN = "retain"


class HelpAction(str, Enum):
    SHOW_ON_BOARD = "show_on_board"
    ASK_ONE_QUESTION = "ask_one_question"
    LET_ME_TRY = "let_me_try"


class EvidenceSourceType(str, Enum):
    LESSON = "lesson"
    MIXED_DRILL = "mixed_drill"
    COACHED_APPLICATION = "coached_application"
    ORGANIC_GAME = "organic_game"


class HomeDiagnosticConclusion(str, Enum):
    CONTROLLED_TRANSFER = "controlled_transfer"
    FAMILIAR_POSITION_ONLY = "familiar_position_only"
    PROMPTED_RECOGNITION = "prompted_recognition"
    CURRENT_LEARNING_NEED = "current_learning_need"
    NO_CONCLUSION = "no_conclusion"


@dataclass(frozen=True)
class HomeDiagnosticResult:
    conclusion: HomeDiagnosticConclusion
    target_results: Tuple[str, str]
    separate_soundness_issue: bool
    next_action: str
    real_game_evidence: str = "not_measured"
    schema_version: str = HOME_DIAGNOSTIC_SCHEMA_VERSION

    def public_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "conclusion": self.conclusion.value,
            "target_results": list(self.target_results),
            "separate_soundness_issue": self.separate_soundness_issue,
            "next_action": self.next_action,
            "real_game_evidence": self.real_game_evidence,
        }


def derive_home_diagnostic_result(
    attempts: Tuple[Mapping[str, Any], Mapping[str, Any]],
) -> HomeDiagnosticResult:
    """Map exactly two answer-hidden attempts to one bounded conclusion."""
    if len(attempts) != 2:
        raise ContractViolation("home diagnostic requires exactly two attempts")
    targets = tuple(str(item.get("target_result") or "unmeasured") for item in attempts)
    soundness = tuple(
        str((item.get("soundness") or {}).get("status") or "unmeasured")
        for item in attempts
    )
    separate_issue = "serious_problem" in soundness
    if any(value not in {"pass", "fail"} for value in targets) or any(
        value not in {"sound", "serious_problem"} for value in soundness
    ):
        conclusion = HomeDiagnosticConclusion.NO_CONCLUSION
    else:
        helped = any(bool(item.get("substantive_help")) for item in attempts)
        reasons = tuple(item.get("reasoning_consistent") for item in attempts)
        if targets == ("pass", "pass") and helped:
            conclusion = HomeDiagnosticConclusion.PROMPTED_RECOGNITION
        elif targets == ("pass", "pass") and reasons == (True, True):
            conclusion = HomeDiagnosticConclusion.CONTROLLED_TRANSFER
        elif targets[0] == "pass" and (
            targets[1] == "fail" or reasons[1] is not True
        ):
            conclusion = HomeDiagnosticConclusion.FAMILIAR_POSITION_ONLY
        else:
            conclusion = HomeDiagnosticConclusion.CURRENT_LEARNING_NEED
    actions = {
        HomeDiagnosticConclusion.CONTROLLED_TRANSFER: "quiet_coached_application",
        HomeDiagnosticConclusion.FAMILIAR_POSITION_ONLY: "teach_reusable_board_signal",
        HomeDiagnosticConclusion.PROMPTED_RECOGNITION: "build_pre_move_trigger",
        HomeDiagnosticConclusion.CURRENT_LEARNING_NEED: "teach_board_relationship",
        HomeDiagnosticConclusion.NO_CONCLUSION: "preserve_existing_home_action",
    }
    return HomeDiagnosticResult(
        conclusion=conclusion,
        target_results=(targets[0], targets[1]),
        separate_soundness_issue=separate_issue,
        next_action=actions[conclusion],
    )


def personal_curriculum_enabled(
    env: Optional[Mapping[str, str]] = None,
) -> bool:
    """Return the default-off backend flag state."""
    source = os.environ if env is None else env
    return str(source.get(FEATURE_FLAG, "false")).strip().lower() in _TRUE_VALUES


def personalized_teaching_enabled(
    env: Optional[Mapping[str, str]] = None,
) -> bool:
    """Return the separate default-off personalized-delivery flag state."""
    source = os.environ if env is None else env
    return (
        str(source.get(PERSONALIZED_TEACHING_FEATURE_FLAG, "false"))
        .strip()
        .lower()
        in _TRUE_VALUES
    )


def home_replay_diagnostic_enabled(
    env: Optional[Mapping[str, str]] = None,
) -> bool:
    source = os.environ if env is None else env
    return (
        str(source.get(HOME_DIAGNOSTIC_FEATURE_FLAG, "false"))
        .strip()
        .lower()
        in _TRUE_VALUES
    )


async def _count_later_exact_misses(
    db,
    user_id: str,
    completed_at: Any,
) -> int:
    """Count exact misses in games played after the diagnostic.

    Observation ``derived_at`` is intentionally not used: an old game may be
    reprocessed after the diagnostic and must not be presented as a new miss.
    Dates with day-only precision are accepted only when strictly later, so a
    same-day game remains unmeasured rather than becoming a false claim.
    """
    observations = getattr(db, "move_observations", None)
    games = getattr(db, "games", None)
    if observations is None or games is None or not completed_at:
        return 0
    cursor = observations.find(
        {
            "user_id": user_id,
            "schema_version": {"$gte": 18},
            "destination_safety_exact.version": (
                "piece_safety.destination_safety_exact.v1"
            ),
            "destination_safety_exact.fires": True,
        },
        {"_id": 0, "game_id": 1},
    )
    rows = await cursor.to_list(length=5000)
    game_ids = sorted({str(row.get("game_id")) for row in rows if row.get("game_id")})
    if not game_ids:
        return 0
    game_rows = await games.find(
        {"user_id": user_id, "game_id": {"$in": game_ids}},
        {"_id": 0, "game_id": 1, "date_played": 1},
    ).to_list(length=len(game_ids))
    from services.prescription_tracking_service import _normalize_game_date

    completed_day = _normalize_game_date(completed_at)
    if not completed_day:
        return 0
    later_ids = {
        str(game.get("game_id"))
        for game in game_rows
        if _normalize_game_date(game.get("date_played"))
        and _normalize_game_date(game.get("date_played")) > completed_day
    }
    return len(later_ids)


async def _home_replay_diagnostic_projection(
    db,
    user_id: str,
    primary: "CurriculumCandidate",
    *,
    env: Optional[Mapping[str, str]] = None,
) -> Optional[Dict[str, Any]]:
    from services.destination_safety_detector import QUALITY_ID

    if (
        not home_replay_diagnostic_enabled(env)
        or primary.detector_quality_id != QUALITY_ID
        or not is_authorized(QUALITY_ID, QualitySurface.PLAN)
    ):
        return None
    users = getattr(db, "users", None)
    if users is None:
        return None
    user = await users.find_one({"user_id": user_id}, {"_id": 0, "feature_flags": 1})
    enrollment = ((user or {}).get("feature_flags") or {}).get(
        "home_replay_diagnostic"
    ) or {}
    if enrollment.get("enabled") is not True:
        return None

    sessions = getattr(db, "learning_sessions", None)
    if sessions is None:
        return None
    session = await sessions.find_one(
        {
            "user_id": user_id,
            "lesson_type": "personalized_curriculum",
            "delivery_mode": "blind_diagnostic",
        },
        sort=[("updated_at", -1)],
    )
    if session:
        from services.teaching_engine import _public_personalized_session

        public = _public_personalized_session(session)
        state = (
            "result"
            if session.get("status") == "completed"
            else "reflection"
            if public.get("awaiting_reason")
            else "active"
        )
        if session.get("status") == "completed" and session.get("completed_at"):
            later_misses = await _count_later_exact_misses(
                db,
                user_id,
                session.get("completed_at"),
            )
            if later_misses:
                diagnostic_result = dict(public.get("diagnostic_result") or {})
                diagnostic_result.update({
                    "real_game_evidence": "missed",
                    "next_action": "return_to_board_relationship",
                })
                public["diagnostic_result"] = diagnostic_result
                state = "later_miss"
        return {
            "enabled": True,
            "state": state,
            "session": public,
        }

    from services.personalized_lesson_adapter import (
        LessonUnavailable,
        resolve_personalized_lesson,
    )
    try:
        # Preflight only. The actual pair is frozen atomically at session start.
        await resolve_personalized_lesson(
            db,
            user_id,
            content_kind="concept",
            content_id="piece_safety",
            params={"mode": "blind_diagnostic", "limit": 20},
        )
    except LessonUnavailable:
        return None
    return {
        "enabled": True,
        "state": "ready",
        "start": {
            "content_kind": "concept",
            "content_id": "piece_safety",
            "mode": "blind_diagnostic",
        },
    }


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


def personalized_teaching_eligible(
    user_role: Optional[str],
    env: Optional[Mapping[str, str]] = None,
) -> bool:
    """Personalized delivery never widens the Personal Curriculum rollout."""
    return (
        personal_curriculum_eligible(user_role, env)
        and personalized_teaching_enabled(env)
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
    # topic_label and coaching_narrative belong to the legacy FocusCard and
    # can contain internal percentages, corpus counts, and detector language.
    # Curriculum surfaces consume the reviewed player projection instead.
    from services.home_coach_conversation import get_player_safe_focus_copy
    player_copy = get_player_safe_focus_copy(topic_key)
    return CurriculumCandidate(
        outcome=CurriculumOutcome.REPAIR,
        student_state=StudentState.LEARNING,
        title=player_copy["title"],
        reason=player_copy["reason"],
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
    if kind in {"endgame", "mate_pattern"}:
        return resolve_endgame_destination(
            content_ref,
            capability=LessonCapability.TEACH,
        )
    canonical_source = {
        "opening": "backend/data/opening_curriculum.json",
        "trap": "backend/data/traps.json",
        "trap_set": "backend/data/traps.json",
        "concept": "backend/data/theory/tactical_patterns.json",
    }.get(kind, "backend/data/coaching/skill_tree.json")
    return CurriculumDestination(
        href=str(action.get("href") or "/play-with-coach"),
        medium=str(action.get("medium") or "lesson"),
        capability=LessonCapability.TEACH,
        content_kind=kind,
        content_id=str(content_ref or focus.get("skill_id")),
        canonical_source=canonical_source,
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


def _personalized_candidate(
    candidate: CurriculumCandidate,
) -> CurriculumCandidate:
    """Route a supported canonical lesson through the shared workspace."""
    destination = candidate.destination
    if destination.content_kind not in {
        "concept",
        "opening",
        "trap",
        "trap_set",
        "endgame",
    }:
        return candidate
    from services.personalized_lesson_adapter import (
        supports_personalized_lesson_identity,
    )

    if not supports_personalized_lesson_identity(
        destination.content_kind,
        destination.content_id,
    ):
        return candidate
    query = urlencode({
        "personalized": "1",
        "kind": destination.content_kind,
        "lesson": destination.content_id,
    })
    return replace(
        candidate,
        destination=replace(
            destination,
            href=f"/training?{query}",
            medium="personalized_lesson",
        ),
    )


async def _with_latest_lesson_state(
    db,
    user_id: str,
    candidate: CurriculumCandidate,
) -> CurriculumCandidate:
    """Project only the highest state an exact personalized lesson proved."""
    sessions = getattr(db, "learning_sessions", None)
    if sessions is None:
        return candidate
    latest = await sessions.find_one(
        {
            "user_id": user_id,
            "lesson_type": "personalized_curriculum",
            "content_kind": candidate.destination.content_kind,
            "content_id": candidate.destination.content_id,
        },
        {
            "_id": 0,
            "highest_earned_state": 1,
            "updated_at": 1,
        },
        sort=[("updated_at", -1)],
    )
    if not latest:
        return candidate
    allowed = {
        StudentState.LEARNING,
        StudentState.CAN_DO_WITH_HELP,
        StudentState.CAN_DO_ALONE,
    }
    try:
        proved = StudentState(str(latest.get("highest_earned_state") or ""))
    except ValueError:
        return candidate
    if proved not in allowed:
        return candidate
    rank = {
        StudentState.NEW: 0,
        StudentState.LEARNING: 1,
        StudentState.CAN_DO_WITH_HELP: 2,
        StudentState.CAN_DO_ALONE: 3,
    }
    if rank.get(proved, 0) <= rank.get(candidate.student_state, 0):
        return candidate
    return replace(candidate, student_state=proved)


def _stored_datetime(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


async def _due_personalized_review(
    db,
    user_id: str,
    *,
    analyzed_games: int,
    now: datetime,
) -> Optional[CurriculumCandidate]:
    sessions = getattr(db, "learning_sessions", None)
    if sessions is None:
        return None
    latest = await sessions.find_one(
        {
            "user_id": user_id,
            "lesson_type": "personalized_curriculum",
            "status": "completed",
        },
        {
            "_id": 0,
            "content_kind": 1,
            "content_id": 1,
            "skill_id": 1,
            "highest_earned_state": 1,
            "descriptor": 1,
            "completed_at": 1,
            "analyzed_games_at_completion": 1,
        },
        sort=[("completed_at", -1)],
    )
    if not latest:
        return None
    try:
        state = StudentState(str(latest.get("highest_earned_state") or ""))
    except ValueError:
        return None
    if state not in {StudentState.CAN_DO_WITH_HELP, StudentState.CAN_DO_ALONE}:
        return None

    baseline = latest.get("analyzed_games_at_completion")
    games_since = (
        max(0, analyzed_games - int(baseline))
        if isinstance(baseline, (int, float))
        else 0
    )
    completed_at = _stored_datetime(latest.get("completed_at"))
    elapsed = (now - completed_at) if completed_at else timedelta(0)
    game_due = games_since >= 3
    backstop_due = elapsed >= timedelta(days=21)
    if not game_due and not backstop_due:
        return None

    descriptor = latest.get("descriptor") or {}
    kind = str(latest.get("content_kind") or descriptor.get("kind") or "")
    lesson_id = str(latest.get("content_id") or descriptor.get("id") or "")
    canonical_source = str(descriptor.get("canonical_source") or "")
    if not kind or not lesson_id or not canonical_source:
        return None
    query = urlencode({
        "personalized": "1",
        "kind": kind,
        "lesson": lesson_id,
        "review": "1",
    })
    if game_due:
        reason = (
            f"You have played {games_since} analyzed games since this lesson. "
            "Let us see whether you can find the idea again without help."
        )
        evidence = (
            "The review is due because you have new game evidence since the lesson."
        )
        evidence_status = EvidenceStatus.TRUSTWORTHY
    else:
        reason = (
            "It has been at least 21 days. This is a check-in, not proof from "
            "new games."
        )
        evidence = "No new game evidence is being claimed for this check-in."
        evidence_status = EvidenceStatus.STALE
    return CurriculumCandidate(
        outcome=CurriculumOutcome.REVIEW,
        student_state=state,
        title=str(descriptor.get("title") or "Review your lesson"),
        reason=reason,
        evidence_summary=evidence,
        evidence_status=evidence_status,
        destination=CurriculumDestination(
            href=f"/training?{query}",
            medium="personalized_lesson",
            capability=LessonCapability.REVIEW,
            content_kind=kind,
            content_id=lesson_id,
            canonical_source=canonical_source,
        ),
        evidence_owner="learning_sessions",
        evidence_ref=str(latest.get("skill_id") or lesson_id),
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

    personalized_enabled = personalized_teaching_eligible(role, env)
    if personalized_enabled:
        primary = _personalized_candidate(primary)
        primary = await _with_latest_lesson_state(db, user_id, primary)

    review_candidate = None
    if personalized_enabled:
        review_candidate = await _due_personalized_review(
            db,
            user_id,
            analyzed_games=analyzed_games,
            now=now,
        )
        if review_candidate and review_candidate.content_identity == primary.content_identity:
            primary = review_candidate
            review_candidate = None

    decision = build_curriculum_decision(
        primary,
        generated_at=now,
        review=review_candidate,
    )
    naturally_next = None
    if primary.outcome == CurriculumOutcome.REPAIR and knowledge is not None:
        next_candidate = _knowledge_candidate(
            knowledge,
            band_name=str((focus or {}).get("rating_band") or "beginner_high"),
        )
        if personalized_enabled:
            next_candidate = _personalized_candidate(next_candidate)
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
    teaching_profile = None
    if personalized_enabled and primary.outcome != CurriculumOutcome.OBSERVE:
        from services.personal_teaching_profile import (
            build_personal_teaching_profile,
        )

        teaching_profile = await build_personal_teaching_profile(
            db,
            user_id,
            skill_id=primary.destination.content_id,
            canonical_lesson={
                "kind": primary.destination.content_kind,
                "id": primary.destination.content_id,
                "canonical_source": primary.destination.canonical_source,
                "content_version": "resolved_at_session_start",
            },
        )
    home_diagnostic = await _home_replay_diagnostic_projection(
        db,
        user_id,
        primary,
        env=env,
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
        "personalized_teaching": {
            "enabled": personalized_enabled,
            "profile": teaching_profile,
        },
        "home_diagnostic": home_diagnostic,
    }


@dataclass(frozen=True)
class LessonResult:
    """Shared evidence event emitted by future lesson adapters."""

    content_kind: str
    content_id: str
    canonical_source: str
    content_version: str
    attempt_kind: AttemptKind
    occurred_at: datetime
    skill_id: Optional[str] = None
    primary_skill_id: Optional[str] = None
    stage: Optional[TeachingStage] = None
    correct: Optional[bool] = None
    assistance: Tuple[AssistanceKind, ...] = ()
    requested_help: Tuple[HelpAction, ...] = ()
    position_id: Optional[str] = None
    board_verified: bool = False
    distinct_position: bool = False
    prediction_correct: Optional[bool] = None
    reason_choice: Optional[str] = None
    reasoning_consistent: Optional[bool] = None
    misconception: Optional[str] = None
    corrective_action: Optional[str] = None
    source_type: EvidenceSourceType = EvidenceSourceType.LESSON
    application_outcome: ApplicationOutcome = ApplicationOutcome.NOT_MEASURED
    detector_quality_id: Optional[str] = None
    detector_version: Optional[str] = None
    grader_version: Optional[str] = None
    evidence_owner: Optional[str] = None
    evidence_ref: Optional[str] = None
    time_control: Optional[str] = None
    under_time_pressure: Optional[bool] = None
    source_event_id: Optional[str] = None

    def __post_init__(self) -> None:
        for field_name in (
            "content_kind",
            "content_id",
            "canonical_source",
            "content_version",
        ):
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
        if any(not isinstance(item, HelpAction) for item in self.requested_help):
            raise ContractViolation("requested_help entries must be HelpAction values")
        if self.stage is not None and not isinstance(self.stage, TeachingStage):
            raise ContractViolation("stage must be a TeachingStage")
        if not isinstance(self.source_type, EvidenceSourceType):
            raise ContractViolation("source_type must be an EvidenceSourceType")
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
            if self.source_type not in (
                EvidenceSourceType.COACHED_APPLICATION,
                EvidenceSourceType.ORGANIC_GAME,
            ):
                raise ContractViolation(
                    "application attempts must preserve coached or organic source"
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

        effective_help = tuple(
            item for item in self.requested_help
            if item != HelpAction.LET_ME_TRY
        )
        if self.assistance or effective_help:
            return StudentState.CAN_DO_WITH_HELP

        if self.reasoning_consistent is False:
            return StudentState.LEARNING

        if self.board_verified and self.distinct_position:
            return StudentState.CAN_DO_ALONE

        return StudentState.LEARNING

    def event_dict(self) -> Dict[str, Any]:
        earned = self.earned_state()
        stage = self.stage or {
            AttemptKind.EXPLANATION: TeachingStage.EXPLAIN,
            AttemptKind.GUIDED: TeachingStage.GUIDE,
            AttemptKind.INDEPENDENT: TeachingStage.TRANSFER,
            AttemptKind.REVIEW: TeachingStage.RETAIN,
            AttemptKind.APPLICATION: TeachingStage.APPLY,
        }[self.attempt_kind]
        return {
            "schema_version": LESSON_RESULT_SCHEMA_VERSION,
            "lesson": {
                "kind": self.content_kind,
                "id": self.content_id,
                "canonical_source": self.canonical_source,
                "content_version": self.content_version,
                "skill_id": self.skill_id or self.content_id,
                "primary_skill_id": self.primary_skill_id or self.skill_id or self.content_id,
            },
            "attempt": {
                "kind": self.attempt_kind.value,
                "stage": stage.value,
                "correct": self.correct,
                "assistance": [item.value for item in self.assistance],
                "requested_help": [item.value for item in self.requested_help],
                "position_id": self.position_id,
                "board_verified": self.board_verified,
                "distinct_position": self.distinct_position,
                "prediction_correct": self.prediction_correct,
                "reason_choice": self.reason_choice,
                "reasoning_consistent": self.reasoning_consistent,
                "misconception": self.misconception,
                "corrective_action": self.corrective_action,
                "grader_version": self.grader_version,
            },
            "application": {
                "outcome": self.application_outcome.value,
                "source_type": self.source_type.value,
                "detector_quality_id": self.detector_quality_id,
                "detector_version": self.detector_version,
                "plan_authorized": _application_claim_authorized(
                    self.detector_quality_id
                ),
                "time_control": self.time_control,
                "under_time_pressure": self.under_time_pressure,
            },
            "provenance": {
                "owner": self.evidence_owner,
                "ref": self.evidence_ref,
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
            provenance = payload.get("provenance")
            if not isinstance(provenance, Mapping):
                provenance = {}
            result = cls(
                content_kind=str(lesson.get("kind") or ""),
                content_id=str(lesson.get("id") or ""),
                canonical_source=str(lesson.get("canonical_source") or ""),
                content_version=str(lesson.get("content_version") or ""),
                skill_id=lesson.get("skill_id"),
                primary_skill_id=lesson.get("primary_skill_id"),
                attempt_kind=AttemptKind(str(attempt.get("kind") or "")),
                occurred_at=parsed_at,
                stage=TeachingStage(str(attempt.get("stage") or "")),
                correct=attempt.get("correct"),
                assistance=tuple(
                    AssistanceKind(str(item))
                    for item in (attempt.get("assistance") or [])
                ),
                requested_help=tuple(
                    HelpAction(str(item))
                    for item in (attempt.get("requested_help") or [])
                ),
                position_id=attempt.get("position_id"),
                board_verified=bool(attempt.get("board_verified")),
                distinct_position=bool(attempt.get("distinct_position")),
                prediction_correct=attempt.get("prediction_correct"),
                reason_choice=attempt.get("reason_choice"),
                reasoning_consistent=attempt.get("reasoning_consistent"),
                misconception=attempt.get("misconception"),
                corrective_action=attempt.get("corrective_action"),
                grader_version=attempt.get("grader_version"),
                source_type=EvidenceSourceType(
                    str(application.get("source_type") or "")
                ),
                application_outcome=ApplicationOutcome(
                    str(application.get("outcome") or "")
                ),
                detector_quality_id=application.get("detector_quality_id"),
                detector_version=application.get("detector_version"),
                evidence_owner=provenance.get("owner"),
                evidence_ref=provenance.get("ref"),
                time_control=application.get("time_control"),
                under_time_pressure=application.get("under_time_pressure"),
                source_event_id=payload.get("source_event_id"),
            )
        except (TypeError, ValueError) as exc:
            raise ContractViolation("lesson result enum value is invalid") from exc
        earned = result.earned_state()
        recomputed = earned.value if earned else None
        if payload.get("earned_state") != recomputed:
            raise ContractViolation("stored earned_state does not match evidence")
        return result
