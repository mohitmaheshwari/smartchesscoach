"""Runtime bridge for the Phase 3 personalized review shadow plan.

This module does not decide chess truth. It reuses the canonical observation
deriver and adapts the exact ``MoveTeachingDecision`` produced by V5. The
current-schema, Caption-authorized ``simple_hang`` signal may anchor a verified
single-game chapter and reflection. It cannot claim recurrence, prescribe a
next action, or affect mastery until separately promoted to Plan grade.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

from services.caption_pipeline import MoveTeachingDecision
from services.detector_quality import QualitySurface, gap_quality_id
from services.game_review_contracts import EventActor, EventOutcome, TeachableEvent
from services.game_review_event_adapter import (
    MoveEventContext,
    adapt_move_teaching_decision,
)
from services.game_review_planner import (
    PlannerEventFeatures,
    build_shadow_game_teaching_plan,
)
from services.move_observation_deriver import SCHEMA_VERSION, derive_observations_for_game
from services.personal_curriculum import PIC_CANONICAL_SOURCE, PIC_CONTENT_ID


SHADOW_RUNTIME_VERSION = "personalized_game_review_shadow_runtime.v1"
MINIMUM_SIMPLE_HANG_SCHEMA = 16
SIMPLE_HANG_PATTERN = "piece_safety"
SIMPLE_HANG_SUBTYPE = "simple_hang"


def derive_current_review_observations(
    *,
    game_id: str,
    user_id: str,
    user_color: str,
    pgn: str,
    move_evaluations: Sequence[Mapping[str, Any]],
    opponent_move_evaluations: Sequence[Mapping[str, Any]] = (),
) -> Dict[int, Dict[str, Any]]:
    """Run the existing observation authority in memory; perform no writes."""
    observations = derive_observations_for_game(
        stockfish_analysis={
            "move_evaluations": list(move_evaluations),
            "opponent_move_evaluations": list(opponent_move_evaluations),
        },
        game_id=game_id,
        user_id=user_id,
        user_color=user_color,
        decryption_v5_data=None,
        pgn=pgn,
    )
    return {
        int(item["move_number"]): item
        for item in observations
        if item.get("move_number") is not None
    }


def adapt_simple_hang_event(
    *,
    decision: MoveTeachingDecision,
    observation: Mapping[str, Any],
    game_id: str,
    ply: int,
    move_number: int,
    san: str,
) -> Optional[Tuple[TeachableEvent, PlannerEventFeatures]]:
    """Adapt one verified positive diagnosis; fail closed for everything else."""
    if int(observation.get("schema_version") or 0) < MINIMUM_SIMPLE_HANG_SCHEMA:
        return None
    pattern = str(observation.get("missed_pattern") or "")
    subtype = str(observation.get("subtype") or "")
    if pattern != SIMPLE_HANG_PATTERN or subtype != SIMPLE_HANG_SUBTYPE:
        return None

    quality_id = gap_quality_id(pattern, subtype)
    central_provenance = tuple(
        str(item)
        for item in decision.explanation.provenance
        if str(item).strip()
    )
    event = adapt_move_teaching_decision(
        decision,
        MoveEventContext(
            game_id=game_id,
            ply=ply,
            move_number=move_number,
            san=san,
            actor=EventActor.USER,
            concept_id="piece_safety.simple_hang",
            content_ref=PIC_CONTENT_ID,
            canonical_source=PIC_CANONICAL_SOURCE,
            outcome=EventOutcome.ALLOWED,
            quality_id=quality_id,
            provenance=(f"move_observation:{game_id}:{ply}",) + central_provenance,
            opportunity_eligible=True,
            requested_surface=QualitySurface.CAPTION,
            reflection_requested=True,
            source_version=(
                f"{SHADOW_RUNTIME_VERSION}+move_observation.v"
                f"{int(observation.get('schema_version') or SCHEMA_VERSION)}"
            ),
        ),
    )
    features = PlannerEventFeatures(
        event_id=event.event_id,
        was_critical_moment=bool(observation.get("was_critical_moment")),
        cp_loss=max(0.0, float(observation.get("cp_loss") or 0)),
    )
    return event, features


def build_shadow_storage_payload(
    *,
    game_id: str,
    events: Sequence[TeachableEvent],
    features: Mapping[str, PlannerEventFeatures],
    generated_at: datetime,
    source_v5_version: int,
) -> Dict[str, Any]:
    """Serialize an auditable shadow result, including honest no-plan cases."""
    result = build_shadow_game_teaching_plan(
        game_id=game_id,
        events=events,
        features=features,
        generated_at=generated_at,
    )
    return {
        "schema_version": "personalized_game_review.shadow_plan.v1",
        "generated_at": generated_at.isoformat(),
        "source_v5_version": int(source_v5_version),
        "observation_schema_version": SCHEMA_VERSION,
        **result.contract_dict(),
    }
