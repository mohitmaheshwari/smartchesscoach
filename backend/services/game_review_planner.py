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
from services.caption_facts import (
    TEACHING_OPPORTUNITY_PROOF_VERSION,
    TEACHING_OPPORTUNITY_QUALITY_IDS,
)
from services.game_review_contracts import (
    ChapterRole,
    GameTeachingPlan,
    PlanChapter,
    ReviewContractViolation,
    ReviewNextAction,
    TeachableEvent,
    event_index,
)


PLANNER_VERSION = "personalized_game_review_planner.v2"
SHADOW_FORMULA = "D_teaching_then_critical"
QUALITY_V2_FORMULA = "E_transition_then_teaching"
SHADOW_MOMENT_CAP = 3
SHADOW_REFLECTION_QUESTION_BUDGET = 1
TEACHING_OPPORTUNITY_SHADOW_SCHEMA_VERSION = (
    "teaching_opportunity_shadow_summary.v3"
)


@dataclass(frozen=True)
class PlannerEventFeatures:
    event_id: str
    was_critical_moment: bool
    cp_loss: float
    decisiveness_changed: bool = False
    stayed_winning: bool = False
    mover_winprob_delta: float = 0.0

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
        if not isinstance(self.decisiveness_changed, bool):
            raise ReviewContractViolation("decisiveness_changed must be boolean")
        if not isinstance(self.stayed_winning, bool):
            raise ReviewContractViolation("stayed_winning must be boolean")
        if not isinstance(self.mover_winprob_delta, (int, float)):
            raise ReviewContractViolation("mover_winprob_delta must be numeric")


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
                or event.teaching.visual.relationship_arrows
            )
        )
    )


def _rank_key(
    event: TeachableEvent,
    features: PlannerEventFeatures,
    formula_id: str,
) -> Tuple[float, ...]:
    if formula_id == SHADOW_FORMULA:
        return (
            float(_teaching_completeness(event)),
            float(features.was_critical_moment),
            float(features.cp_loss),
            float(-event.move.ply),
        )
    if formula_id == QUALITY_V2_FORMULA:
        return (
            float(features.decisiveness_changed),
            float(not features.stayed_winning),
            float(_teaching_completeness(event)),
            max(0.0, -float(features.mover_winprob_delta)),
            float(features.cp_loss),
            float(-event.move.ply),
        )
    raise ReviewContractViolation("unknown review ranking formula")


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
    if event.outcome.value == "allowed":
        return ChapterRole.MISSED_OPPORTUNITY
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


def build_teaching_opportunity_shadow_summary(
    rows: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    """Validate and deduplicate internal opportunity renderings.

    This is ordering/aggregation only. Chess truth remains owned by the
    typed cause and comparison contracts. The first occurrence of an exact
    story key is the anchor. Consecutive mate proofs for the same side are one
    episode, preventing one forcing sequence from appearing as several lessons.
    """
    accepted = []
    seen_story_keys = set()
    raw_by_family = {
        family: 0 for family in TEACHING_OPPORTUNITY_QUALITY_IDS
    }
    deduplicated_by_family = {
        family: 0 for family in TEACHING_OPPORTUNITY_QUALITY_IDS
    }
    previous_mate_ply: Optional[int] = None
    previous_mate_payoff_side: Optional[str] = None
    for row in rows:
        if not isinstance(row, Mapping):
            raise ReviewContractViolation(
                "teaching-opportunity shadow row must be a mapping"
            )
        family = str(row.get("family") or "")
        quality_id = str(row.get("quality_id") or "")
        story_key = str(row.get("story_key") or "")
        actor = str(row.get("actor") or "")
        cause_kind = str(row.get("cause_kind") or "")
        source_ply = row.get("source_ply")
        proof = row.get("proof")
        display = row.get("display")
        if (
            row.get("schema_version")
            != "teaching_opportunity_comparison.v3"
            or row.get("rollout_mode") != "shadow"
            or family not in TEACHING_OPPORTUNITY_QUALITY_IDS
            or quality_id != TEACHING_OPPORTUNITY_QUALITY_IDS[family]
            or not story_key
            or not isinstance(proof, Mapping)
            or proof.get("authority")
            != "caption_facts.build_verified_teaching_opportunities"
            or proof.get("version") != TEACHING_OPPORTUNITY_PROOF_VERSION
            or not isinstance(display, Mapping)
            or display.get("authorized") is not False
            or actor not in {"player", "opponent"}
            or cause_kind not in {
                "missed_forced_mate",
                "allowed_forced_mate",
                "exchange_sequence",
                "immediate_material_loss",
                "missed_material_opportunity",
            }
            or not isinstance(source_ply, int)
            or isinstance(source_ply, bool)
            or source_ply < 1
            or any(
                len(value) != 64
                or any(char not in "0123456789abcdef" for char in value)
                for value in (
                    story_key,
                    str(row.get("opportunity_fingerprint") or ""),
                    str(row.get("cause_fingerprint") or ""),
                )
            )
        ):
            raise ReviewContractViolation(
                "teaching-opportunity Shadow contract is invalid"
            )
        raw_by_family[family] += 1
        same_mate_episode = False
        if family == "forced_mate_story":
            payoff_side = (
                actor
                if cause_kind == "missed_forced_mate"
                else ("opponent" if actor == "player" else "player")
            )
            same_mate_episode = bool(
                previous_mate_ply is not None
                and source_ply == previous_mate_ply + 1
                and payoff_side == previous_mate_payoff_side
            )
            previous_mate_ply = source_ply
            previous_mate_payoff_side = payoff_side
        if story_key in seen_story_keys or same_mate_episode:
            deduplicated_by_family[family] += 1
            continue
        seen_story_keys.add(story_key)
        accepted.append(dict(row))

    payload = {
        "schema_version": TEACHING_OPPORTUNITY_SHADOW_SCHEMA_VERSION,
        "rollout_mode": "shadow",
        "raw_count": len(rows),
        "candidate_count": len(accepted),
        "deduplicated_count": len(rows) - len(accepted),
        "raw_by_family": raw_by_family,
        "deduplicated_by_family": deduplicated_by_family,
        "candidates": accepted,
    }
    payload["fingerprint"] = hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()
    return payload


def build_shadow_game_teaching_plan(
    *,
    game_id: str,
    events: Sequence[TeachableEvent],
    features: Mapping[str, PlannerEventFeatures],
    generated_at: datetime,
    next_actions: Optional[Mapping[str, ReviewNextAction]] = None,
    recurring_event_ids: Sequence[str] = (),
    formula_id: str = SHADOW_FORMULA,
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
        key=lambda item: _rank_key(item[0], item[1], formula_id),
        reverse=True,
    )
    selected_ranked = ranked[:SHADOW_MOMENT_CAP]
    if not selected_ranked:
        return ShadowPlannerResult(
            plan=None,
            formula_id=formula_id,
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
    elif len(selected) == 2:
        game_arc = (
            "I found two moments worth studying in this game. "
            "Each is supported on its own."
        )
    else:
        game_arc = (
            "I found three moments worth studying in this game. "
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
        f"{game_id}:{PLANNER_VERSION}:{formula_id}:"
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
        formula_id=formula_id,
        selected_event_ids=selected_ids,
        selected_reflection_event_ids=reflection_ids,
        rejected_event_ids=tuple(rejected),
    )
