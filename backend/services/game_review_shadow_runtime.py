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
from services.caption_facts import LegalMaterialLossCause, VerifiedLineCause
from services.exact_endgame_service import ExactEndgameCause
from services.detector_quality import QualitySurface, gap_quality_id
from services.game_review_contracts import (
    EventActor,
    EventOutcome,
    TeachableEvent,
    personalized_review_quality_v2_enabled,
)
from services.game_review_event_adapter import (
    MoveEventContext,
    adapt_move_teaching_decision,
)
from services.game_review_planner import (
    QUALITY_V2_FORMULA,
    SHADOW_FORMULA,
    PlannerEventFeatures,
    build_shadow_game_teaching_plan,
)
from services.move_observation_deriver import (
    SCHEMA_VERSION,
    current_deriver_identity,
    derive_observations_for_game,
)
from services.personal_curriculum import PIC_CANONICAL_SOURCE, PIC_CONTENT_ID


SHADOW_RUNTIME_VERSION = "personalized_game_review_shadow_runtime.v1"
MINIMUM_SIMPLE_HANG_SCHEMA = 16
SIMPLE_HANG_PATTERN = "piece_safety"
SIMPLE_HANG_SUBTYPE = "simple_hang"
VERIFIED_CAUSE_QUALITY_ID = "review:verified_single_game_cause"
EXACT_ENDGAME_CAUSE_QUALITY_ID = "review:exact_endgame_result_change"


def _has_current_deriver_identity(observation: Mapping[str, Any]) -> bool:
    return observation.get("deriver_identity") == current_deriver_identity()


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
    env: Optional[Mapping[str, str]] = None,
) -> Optional[Tuple[TeachableEvent, PlannerEventFeatures]]:
    """Adapt one verified positive diagnosis; fail closed for everything else."""
    if personalized_review_quality_v2_enabled(env) and not _has_current_deriver_identity(
        observation
    ):
        return None
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
            quality_v2_requested=bool(
                personalized_review_quality_v2_enabled(env)
                and isinstance(decision.cause, LegalMaterialLossCause)
            ),
            source_version=(
                f"{SHADOW_RUNTIME_VERSION}+move_observation.v"
                f"{int(observation.get('schema_version') or SCHEMA_VERSION)}+"
                f"{current_deriver_identity()['manifest_sha256'][:12]}"
            ),
        ),
    )
    features = PlannerEventFeatures(
        event_id=event.event_id,
        was_critical_moment=bool(observation.get("was_critical_moment")),
        cp_loss=max(0.0, float(observation.get("cp_loss") or 0)),
        decisiveness_changed=bool(
            decision.teaching_meta.decisiveness_changed
        ),
        stayed_winning=bool(decision.teaching_meta.stayed_winning),
        mover_winprob_delta=float(
            decision.teaching_meta.mover_winprob_delta or 0.0
        ),
    )
    return event, features


def adapt_verified_cause_event(
    *,
    decision: MoveTeachingDecision,
    game_id: str,
    ply: int,
    move_number: int,
    san: str,
    env: Optional[Mapping[str, str]] = None,
) -> Optional[Tuple[TeachableEvent, PlannerEventFeatures]]:
    """Adapt one position-specific cause; never diagnose recurrence/mastery."""
    if not personalized_review_quality_v2_enabled(env):
        return None
    if not isinstance(
        decision.cause,
        (LegalMaterialLossCause, VerifiedLineCause, ExactEndgameCause),
    ):
        return None
    central_provenance = tuple(
        str(item)
        for item in decision.explanation.provenance
        if str(item).strip()
    )
    if isinstance(decision.cause, LegalMaterialLossCause):
        concept_id = "calculation.legal_material_loss"
        quality_id = VERIFIED_CAUSE_QUALITY_ID
    elif isinstance(decision.cause, VerifiedLineCause):
        concept_id = "calculation.verified_stored_line"
        quality_id = VERIFIED_CAUSE_QUALITY_ID
    else:
        concept_id = "endgame.exact_result_change"
        quality_id = EXACT_ENDGAME_CAUSE_QUALITY_ID
    event = adapt_move_teaching_decision(
        decision,
        MoveEventContext(
            game_id=game_id,
            ply=ply,
            move_number=move_number,
            san=san,
            actor=EventActor.USER,
            concept_id=concept_id,
            outcome=EventOutcome.MISSED,
            quality_id=quality_id,
            provenance=(
                f"typed_cause:{decision.cause.fingerprint}",
            ) + central_provenance,
            opportunity_eligible=True,
            requested_surface=QualitySurface.CAPTION,
            reflection_requested=not isinstance(decision.cause, ExactEndgameCause),
            quality_v2_requested=True,
            source_version=f"{SHADOW_RUNTIME_VERSION}+verified_cause.v1",
        ),
    )
    features = PlannerEventFeatures(
        event_id=event.event_id,
        was_critical_moment=bool(decision.teaching_meta.decisiveness_changed),
        cp_loss=max(0.0, float(decision.debug_facts.get("cp_loss") or 0)),
        decisiveness_changed=bool(decision.teaching_meta.decisiveness_changed),
        stayed_winning=bool(decision.teaching_meta.stayed_winning),
        mover_winprob_delta=float(
            decision.teaching_meta.mover_winprob_delta or 0.0
        ),
    )
    return event, features


def adapt_review_event(
    *,
    decision: MoveTeachingDecision,
    observation: Mapping[str, Any],
    game_id: str,
    ply: int,
    move_number: int,
    san: str,
    env: Optional[Mapping[str, str]] = None,
) -> Optional[Tuple[TeachableEvent, PlannerEventFeatures]]:
    """One runtime admission seam for current Review events."""
    if personalized_review_quality_v2_enabled(env) and not _has_current_deriver_identity(
        observation
    ):
        return None
    simple = adapt_simple_hang_event(
        decision=decision,
        observation=observation,
        game_id=game_id,
        ply=ply,
        move_number=move_number,
        san=san,
        env=env,
    )
    if simple is not None and (
        not personalized_review_quality_v2_enabled(env)
        or isinstance(decision.cause, LegalMaterialLossCause)
    ):
        return simple
    verified = adapt_verified_cause_event(
        decision=decision,
        game_id=game_id,
        ply=ply,
        move_number=move_number,
        san=san,
        env=env,
    )
    return verified or simple


def build_shadow_storage_payload(
    *,
    game_id: str,
    events: Sequence[TeachableEvent],
    features: Mapping[str, PlannerEventFeatures],
    generated_at: datetime,
    source_v5_version: int,
    env: Optional[Mapping[str, str]] = None,
) -> Dict[str, Any]:
    """Serialize an auditable shadow result, including honest no-plan cases."""
    result = build_shadow_game_teaching_plan(
        game_id=game_id,
        events=events,
        features=features,
        generated_at=generated_at,
        formula_id=(
            QUALITY_V2_FORMULA
            if personalized_review_quality_v2_enabled(env)
            else SHADOW_FORMULA
        ),
    )
    return {
        "schema_version": "personalized_game_review.shadow_plan.v1",
        "generated_at": generated_at.isoformat(),
        "source_v5_version": int(source_v5_version),
        "observation_schema_version": SCHEMA_VERSION,
        "deriver_identity": current_deriver_identity(),
        **result.contract_dict(),
    }
