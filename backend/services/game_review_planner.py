"""Deterministic Phase 3 whole-game planner, shadow only.

The selected formula, cap, and question budget are measured shadow settings
from the 2026-09-01 production bake-off. They are not visible-release locks.
This service consumes authorized TeachableEvent values and explicit stored
features. It performs no chess inference and never stitches causal prose.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

from services.detector_quality import QualitySurface
from services.game_review_contracts import (
    ChapterRole,
    GameTeachingPlan,
    PlanChapter,
    ReviewContractViolation,
    ReviewNextAction,
    TeachableEvent,
    event_index,
)


PLANNER_VERSION = "personalized_game_review_planner.v1"
SHADOW_FORMULA = "D_teaching_then_critical"
SHADOW_MOMENT_CAP = 2
SHADOW_REFLECTION_QUESTION_BUDGET = 1


@dataclass(frozen=True)
class PlannerEventFeatures:
    event_id: str
    was_critical_moment: bool
    cp_loss: float

    def __post_init__(self) -> None:
        if not isinstance(self.event_id, str) or not self.event_id.strip():
            raise ReviewContractViolation("planner feature event_id is required")
        if not isinstance(self.was_critical_moment, bool):
            raise ReviewContractViolation(
                "was_critical_moment must be boolean"
            )
        if not isinstance(self.cp_loss, (int, float)) or self.cp_loss < 0:
            raise ReviewContractViolation(
                "planner cp_loss must be a non-negative number"
            )


@dataclass(frozen=True)
class ShadowPlannerResult:
    plan: Optional[GameTeachingPlan]
    formula_id: str
    selected_event_ids: Tuple[str, ...]
    selected_reflection_event_ids: Tuple[str, ...]
    rejected_event_ids: Tuple[str, ...]

    def contract_dict(self) -> Dict[str, Any]:
        return {
            "planner_version": PLANNER_VERSION,
            "rollout_mode": "shadow",
            "formula_id": self.formula_id,
            "moment_cap": SHADOW_MOMENT_CAP,
            "reflection_question_budget": (
                SHADOW_REFLECTION_QUESTION_BUDGET
            ),
            "selected_event_ids": list(self.selected_event_ids),
            "selected_reflection_event_ids": list(
                self.selected_reflection_event_ids
            ),
            "rejected_event_ids": list(self.rejected_event_ids),
            "plan": self.plan.contract_dict() if self.plan else None,
        }


def _teaching_completeness(event: TeachableEvent) -> int:
    return (
        int(bool(event.teaching.caption.strip()))
        + int(bool(event.teaching.principle.strip()))
        + int(
            bool(
                event.teaching.visual.arrows
                or event.teaching.visual.highlights
            )
        )
    )


def _rank_key(
    event: TeachableEvent,
    features: PlannerEventFeatures,
) -> Tuple[float, ...]:
    """Measured Formula D: completeness, critical, loss, then earliest."""
    return (
        float(_teaching_completeness(event)),
        float(features.was_critical_moment),
        float(features.cp_loss),
        float(-event.move.ply),
    )


def _chapter_role(
    event: TeachableEvent,
    recurring_event_ids: frozenset[str],
) -> ChapterRole:
    if event.event_id in recurring_event_ids:
        if not event.evidence.authorizes(QualitySurface.PLAN):
            raise ReviewContractViolation(
                "recurring chapters require Plan-grade evidence"
            )
        return ChapterRole.RECURRING_CONNECTION
    if event.outcome.value in ("demonstrated", "answered", "neutralized"):
        return ChapterRole.DEMONSTRATED_KNOWLEDGE
    if event.outcome.value == "missed":
        return ChapterRole.MISSED_OPPORTUNITY
    if event.outcome.value == "introduced":
        return ChapterRole.KNOWLEDGE_GAP
    return ChapterRole.TURNING_POINT


def _fingerprint(events: Sequence[TeachableEvent]) -> str:
    payload = [event.contract_dict() for event in events]
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_shadow_game_teaching_plan(
    *,
    game_id: str,
    events: Sequence[TeachableEvent],
    features: Mapping[str, PlannerEventFeatures],
    generated_at: datetime,
    next_actions: Optional[Mapping[str, ReviewNextAction]] = None,
    recurring_event_ids: Sequence[str] = (),
) -> ShadowPlannerResult:
    """Build the measured shadow candidate without inventing causality."""
    if not isinstance(game_id, str) or not game_id.strip():
        raise ReviewContractViolation("planner game_id is required")
    index = event_index(events)
    feature_ids = set(features)
    unknown_features = feature_ids - set(index)
    if unknown_features:
        raise ReviewContractViolation(
            "planner features reference unknown events"
        )
    recurring = frozenset(recurring_event_ids)
    if recurring - set(index):
        raise ReviewContractViolation(
            "recurring evidence references unknown events"
        )

    eligible = []
    rejected = []
    for event in events:
        feature = features.get(event.event_id)
        if (
            not event.player_authorized
            or feature is None
            or feature.event_id != event.event_id
            or not (
                event.teaching.caption.strip()
                or event.teaching.principle.strip()
            )
        ):
            rejected.append(event.event_id)
            continue
        eligible.append((event, feature))

    ranked = sorted(
        eligible,
        key=lambda item: _rank_key(item[0], item[1]),
        reverse=True,
    )
    selected_ranked = ranked[:SHADOW_MOMENT_CAP]
    if not selected_ranked:
        return ShadowPlannerResult(
            plan=None,
            formula_id=SHADOW_FORMULA,
            selected_event_ids=(),
            selected_reflection_event_ids=(),
            rejected_event_ids=tuple(rejected),
        )

    # Rank chooses importance; chapter order follows the actual game.
    selected = sorted(
        (item[0] for item in selected_ranked),
        key=lambda event: event.move.ply,
    )
    selected_ids = tuple(event.event_id for event in selected)
    reflection_ids = tuple(
        event.event_id
        for event, _ in selected_ranked
        if event.reflection_eligible
    )[:SHADOW_REFLECTION_QUESTION_BUDGET]

    chapters = tuple(
        PlanChapter(
            event_id=event.event_id,
            role=_chapter_role(event, recurring),
            content_ref=event.concept.content_ref,
            canonical_source=event.concept.canonical_source,
        )
        for event in selected
    )
    if len(selected) == 1:
        game_arc = "I found one moment worth studying in this game."
    else:
        game_arc = (
            "I found two moments worth studying in this game. "
            "Each is supported on its own."
        )

    top_ranked_event = selected_ranked[0][0]
    takeaway = (
        top_ranked_event.teaching.principle.strip()
        or top_ranked_event.teaching.caption.strip()
    )
    action = None
    for event, _ in selected_ranked:
        candidate = (next_actions or {}).get(event.event_id)
        if (
            candidate is not None
            and event.evidence.authorizes(QualitySurface.PLAN)
        ):
            action = candidate
            break

    fingerprint = _fingerprint(selected)
    plan_id_seed = (
        f"{game_id}:{PLANNER_VERSION}:{SHADOW_FORMULA}:"
        f"{SHADOW_MOMENT_CAP}:{fingerprint}"
    ).encode("utf-8")
    plan = GameTeachingPlan(
        plan_id=f"grp_{hashlib.sha256(plan_id_seed).hexdigest()[:20]}",
        generated_at=generated_at,
        input_fingerprint=fingerprint,
        opening_text="I watched how this game unfolded.",
        game_arc=game_arc,
        chapters=chapters,
        takeaway=takeaway,
        next_action=action,
        rollout_mode="shadow",
    )
    plan.validate_against(index)
    return ShadowPlannerResult(
        plan=plan,
        formula_id=SHADOW_FORMULA,
        selected_event_ids=selected_ids,
        selected_reflection_event_ids=reflection_ids,
        rejected_event_ids=tuple(rejected),
    )
