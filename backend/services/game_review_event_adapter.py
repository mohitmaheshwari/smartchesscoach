"""Pure Phase 2 projection from central move decisions to review events.

This module deliberately has no board parser, engine, detector, database, or
LLM dependency. The caller must provide the detector/content identity and the
opportunity evidence that produced the already-canonical
``MoveTeachingDecision``. That prevents Review from becoming a second chess
reasoning pipeline.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional, Tuple

from services.caption_pipeline import MoveTeachingDecision
from services.detector_quality import QualitySurface
from services.game_review_contracts import (
    ConceptReference,
    EventActor,
    EventEvidence,
    EventOutcome,
    MoveReference,
    OpportunityEvidence,
    ReviewContractViolation,
    TeachableEvent,
    TeachingReference,
    VisualReference,
    personalized_game_review_enabled,
)


PHASE2_SOURCE_VERSION = "game_review_event_adapter.v1"


@dataclass(frozen=True)
class MoveEventContext:
    """Explicit upstream evidence needed to project one move decision."""

    game_id: str
    ply: int
    move_number: int
    san: str
    actor: EventActor
    concept_id: str
    outcome: EventOutcome
    quality_id: str
    provenance: Tuple[str, ...]
    opportunity_eligible: bool
    opportunity_before: Optional[str] = None
    opportunity_after: Optional[str] = None
    content_ref: Optional[str] = None
    canonical_source: Optional[str] = None
    requested_surface: QualitySurface = QualitySurface.CAPTION
    reflection_requested: bool = False
    source_version: str = PHASE2_SOURCE_VERSION

    def __post_init__(self) -> None:
        for field_name in (
            "game_id",
            "san",
            "concept_id",
            "quality_id",
            "source_version",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ReviewContractViolation(f"context.{field_name} is required")
        if not isinstance(self.provenance, tuple) or not self.provenance:
            raise ReviewContractViolation("context.provenance must be a non-empty tuple")
        if self.quality_id.startswith("gap:") and not any(
            item.startswith("move_observation:") for item in self.provenance
        ):
            raise ReviewContractViolation(
                "gap events require an upstream move_observation provenance reference"
            )
        if bool(self.content_ref) != bool(self.canonical_source):
            raise ReviewContractViolation(
                "context content_ref and canonical_source must be supplied together"
            )


def _validate_central_identity(
    decision: MoveTeachingDecision,
    context: MoveEventContext,
) -> None:
    """Reject a caller that relabels central shape/principle evidence."""
    if context.quality_id.startswith("shape:"):
        expected = context.quality_id.split(":", 1)[1]
        if decision.teaching_meta.shape_pattern_id != expected:
            raise ReviewContractViolation(
                "shape quality_id does not match MoveTeachingDecision"
            )
    if context.quality_id.startswith("principle:"):
        expected = context.quality_id.split(":", 1)[1]
        if decision.teaching_meta.principle_id_used != expected:
            raise ReviewContractViolation(
                "principle quality_id does not match MoveTeachingDecision"
            )


def _visual(decision: MoveTeachingDecision) -> VisualReference:
    arrows = []
    for arrow in decision.visual.arrows:
        origin = arrow.get("from") if isinstance(arrow, Mapping) else None
        destination = arrow.get("to") if isinstance(arrow, Mapping) else None
        if origin and destination:
            arrows.append((str(origin), str(destination)))
    highlights = tuple(
        str(square) for square in decision.visual.highlight_squares if square
    )
    return VisualReference(arrows=tuple(arrows), highlights=highlights)


def adapt_move_teaching_decision(
    decision: MoveTeachingDecision,
    context: MoveEventContext,
) -> TeachableEvent:
    """Project central typed output without reinterpreting the chess position."""
    if not isinstance(decision, MoveTeachingDecision):
        raise ReviewContractViolation("decision must be MoveTeachingDecision")
    if not isinstance(context, MoveEventContext):
        raise ReviewContractViolation("context must be MoveEventContext")
    _validate_central_identity(decision, context)

    explanation = decision.explanation
    caption = (explanation.board_explanation or decision.text.caption or "").strip()
    principle = (
        explanation.transferable_instruction
        or decision.teaching_meta.principle_cue
        or ""
    ).strip()
    final_verified = bool(explanation.final_verified and not decision.should_skip)
    usable = bool(caption or principle or decision.visual.arrows or decision.visual.highlight_squares)

    evidence = EventEvidence(
        quality_id=context.quality_id,
        source_version=context.source_version,
        provenance=context.provenance,
        final_verified=final_verified,
    )

    if not final_verified or not usable:
        outcome = EventOutcome.SILENT
        surface = QualitySurface.DIAGNOSTIC
        teaching = TeachingReference()
        reflection_eligible = False
    else:
        outcome = context.outcome
        surface = context.requested_surface
        if surface != QualitySurface.DIAGNOSTIC and not evidence.authorizes(surface):
            surface = QualitySurface.DIAGNOSTIC
        teaching = TeachingReference(
            caption=caption,
            principle=principle,
            visual=_visual(decision),
        )
        reflection_eligible = bool(
            context.reflection_requested
            and surface != QualitySurface.DIAGNOSTIC
            and evidence.authorizes(QualitySurface.CAPTION)
        )

    return TeachableEvent(
        event_id=(
            f"{context.game_id}:{context.ply}:{context.concept_id}:"
            f"{outcome.value}"
        ),
        move=MoveReference(
            ply=context.ply,
            number=context.move_number,
            san=context.san,
            actor=context.actor,
        ),
        concept=ConceptReference(
            concept_id=context.concept_id,
            content_ref=context.content_ref,
            canonical_source=context.canonical_source,
        ),
        outcome=outcome,
        opportunity=OpportunityEvidence(
            eligible=context.opportunity_eligible,
            before=context.opportunity_before,
            after=context.opportunity_after,
        ),
        evidence=evidence,
        teaching=teaching,
        requested_surface=surface,
        reflection_eligible=reflection_eligible,
    )


def maybe_attach_phase2_review_fields(
    legacy_response: Dict[str, Any],
    *,
    stored_moves: Optional[Tuple[Mapping[str, Any], ...]] = None,
    env: Optional[Mapping[str, str]] = None,
) -> Dict[str, Any]:
    """Expose precomputed Phase 2 fields; flag-off preserves object and bytes."""
    if not personalized_game_review_enabled(env):
        return legacy_response

    def stored_event_is_authorized(event: Mapping[str, Any]) -> bool:
        display = event.get("display")
        evidence = event.get("evidence")
        if not isinstance(display, Mapping) or not isinstance(evidence, Mapping):
            return False
        surface = display.get("requested_surface")
        authorized_surfaces = evidence.get("authorized_surfaces")
        return bool(
            event.get("outcome") != EventOutcome.SILENT.value
            and surface in (QualitySurface.CAPTION.value, QualitySurface.PLAN.value)
            and display.get("authorized")
            and evidence.get("final_verified")
            and isinstance(authorized_surfaces, Mapping)
            and authorized_surfaces.get(surface)
        )

    events = []
    prompts = []
    source_moves = (
        stored_moves
        if stored_moves is not None
        else tuple(legacy_response.get("decryption_data") or [])
    )
    for move in source_moves:
        if not isinstance(move, Mapping):
            continue
        event = move.get("teachable_event")
        if isinstance(event, Mapping) and stored_event_is_authorized(event):
            events.append(dict(event))
            prompt = move.get("reflection_prompt")
            if (
                (display := event.get("display"))
                and display.get("reflection_eligible")
                and isinstance(prompt, Mapping)
                and prompt.get("event_id") == event.get("event_id")
            ):
                prompts.append(dict(prompt))

    sanitized_moves = []
    for move in legacy_response.get("decryption_data") or []:
        if not isinstance(move, Mapping):
            sanitized_moves.append(move)
            continue
        clean_move = dict(move)
        clean_move.pop("teachable_event", None)
        clean_move.pop("reflection_prompt", None)
        sanitized_moves.append(clean_move)

    augmented = dict(legacy_response)
    augmented["decryption_data"] = sanitized_moves
    augmented["teachable_events"] = events
    augmented["reflection_prompts"] = prompts
    return augmented


_CHAPTER_ROLES = frozenset(
    {
        "turning_point",
        "demonstrated_knowledge",
        "opponent_plan",
        "missed_opportunity",
        "knowledge_gap",
        "recurring_connection",
        "reflection",
    }
)


def _safe_stored_plan(
    envelope: Mapping[str, Any],
    events: Tuple[Mapping[str, Any], ...],
) -> Optional[Dict[str, Any]]:
    """Fail closed unless every stored chapter still has authorization."""
    if envelope.get("rollout_mode") != "shadow":
        return None
    plan = envelope.get("plan")
    if not isinstance(plan, Mapping):
        return None
    required_text = ("plan_id", "opening", "game_arc", "takeaway")
    if any(not str(plan.get(field) or "").strip() for field in required_text):
        return None
    if (
        plan.get("schema_version") != "personalized_game_review.v1"
        or plan.get("rollout_mode") != "shadow"
    ):
        return None

    event_index = {
        str(event.get("event_id") or ""): event
        for event in events
        if event.get("event_id")
    }
    raw_chapters = plan.get("chapters")
    if not isinstance(raw_chapters, list) or not raw_chapters:
        return None
    if any(not isinstance(item, Mapping) for item in raw_chapters):
        return None
    chapter_ids = [str(item.get("event_id") or "") for item in raw_chapters]
    if not all(chapter_ids) or len(chapter_ids) != len(set(chapter_ids)):
        return None
    if chapter_ids != list(envelope.get("selected_event_ids") or []):
        return None

    chapters = []
    for raw in raw_chapters:
        event = event_index.get(str(raw.get("event_id") or ""))
        role = str(raw.get("role") or "")
        if event is None or role not in _CHAPTER_ROLES:
            return None
        surfaces = (event.get("evidence") or {}).get("authorized_surfaces") or {}
        required_surface = (
            "plan" if role == "recurring_connection" else "caption"
        )
        if not surfaces.get(required_surface):
            return None
        concept = event.get("concept") or {}
        if (
            raw.get("content_ref") != concept.get("content_ref")
            or raw.get("canonical_source") != concept.get("canonical_source")
        ):
            return None
        chapters.append({
            "event_id": raw["event_id"],
            "role": role,
            "content_ref": raw.get("content_ref"),
            "canonical_source": raw.get("canonical_source"),
        })

    next_action = plan.get("next_action")
    safe_action = None
    if next_action is not None:
        if not isinstance(next_action, Mapping):
            return None
        source_id = str(next_action.get("source_event_id") or "")
        source_event = event_index.get(source_id)
        href = str(next_action.get("href") or "")
        if (
            source_id not in set(chapter_ids)
            or source_event is None
            or not href.startswith("/")
            or href.startswith("//")
            or not (
                (source_event.get("evidence") or {})
                .get("authorized_surfaces", {})
                .get("plan")
            )
        ):
            return None
        action_fields = (
            "action_kind",
            "content_kind",
            "content_id",
            "canonical_source",
        )
        if any(not str(next_action.get(field) or "").strip() for field in action_fields):
            return None
        safe_action = {
            "source_event_id": source_id,
            "href": href,
            **{field: next_action[field] for field in action_fields},
        }

    return {
        "schema_version": plan["schema_version"],
        "plan_id": plan["plan_id"],
        "opening": plan["opening"],
        "game_arc": plan["game_arc"],
        "chapters": chapters,
        "takeaway": plan["takeaway"],
        "next_action": safe_action,
        "rollout_mode": "shadow",
    }


def maybe_attach_phase5_review_fields(
    legacy_response: Dict[str, Any],
    *,
    stored_moves: Tuple[Mapping[str, Any], ...],
    stored_plan: Optional[Mapping[str, Any]],
    env: Optional[Mapping[str, str]] = None,
) -> Dict[str, Any]:
    """Expose one internally consistent plan; otherwise keep legacy UI."""
    if not personalized_game_review_enabled(env):
        return legacy_response
    augmented = maybe_attach_phase2_review_fields(
        legacy_response,
        stored_moves=stored_moves,
        env=env,
    )
    if not isinstance(stored_plan, Mapping):
        return augmented
    safe_plan = _safe_stored_plan(
        stored_plan,
        tuple(augmented.get("teachable_events") or []),
    )
    if safe_plan is not None:
        augmented["game_teaching_plan"] = safe_plan
    return augmented
