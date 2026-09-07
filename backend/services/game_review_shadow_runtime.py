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

import chess

from services.caption_pipeline import MoveTeachingDecision
from services.caption_facts import (
    HIDDEN_OPPORTUNITY_COMPOSER_VERSION,
    LegalMaterialLossCause,
    VerifiedLineCause,
    build_verified_hidden_opportunity,
)
from services.exact_endgame_service import ExactEndgameCause
from services.detector_quality import QualitySurface, gap_quality_id
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
from services.rating_resolver import (
    caption_suppress_threshold_cp,
    get_rating_band,
)


SHADOW_RUNTIME_VERSION = "personalized_game_review_shadow_runtime.v1"
MINIMUM_SIMPLE_HANG_SCHEMA = 16
SIMPLE_HANG_PATTERN = "piece_safety"
SIMPLE_HANG_SUBTYPE = "simple_hang"
VERIFIED_CAUSE_QUALITY_ID = "review:verified_single_game_cause"
EXACT_ENDGAME_CAUSE_QUALITY_ID = "review:exact_endgame_result_change"
HIDDEN_OPPORTUNITY_SHADOW_VERSION = "hidden_opportunity_shadow_runtime.v1"
HIDDEN_OPPORTUNITY_CONCEPT_ID = "calculation.verified_stored_line"
HIDDEN_OPPORTUNITY_STATUSES = frozenset({
    "candidate",
    "below_rating_threshold",
    "missing_actor_rating",
    "missing_stored_evidence",
    "invalid_stored_evidence",
    "not_proved",
})


def _has_current_deriver_identity(observation: Mapping[str, Any]) -> bool:
    return observation.get("deriver_identity") == current_deriver_identity()


def evaluate_hidden_opportunity_shadow(
    *,
    game_id: str,
    ply: int,
    move_number: int,
    actor: EventActor | str,
    actor_rating: Optional[int],
    fen_before: str,
    played_san: str,
    best_move_san: str,
    pv_after_played: Sequence[Any],
    pv_after_best: Sequence[Any],
    cp_loss: Any,
) -> Dict[str, Any]:
    """Evaluate one stored position without granting a visible surface.

    The canonical composer owns all chess inference. This adapter only applies
    the existing rating-aware significance gate and records enough typed
    evidence to measure incidence. Every outcome is explicit so a zero count
    cannot hide missing ratings or incomplete stored continuations.
    """
    try:
        event_actor = (
            actor if isinstance(actor, EventActor) else EventActor(str(actor))
        )
    except ValueError:
        return {"status": "invalid_stored_evidence"}

    try:
        rating = int(actor_rating) if actor_rating is not None else 0
    except (TypeError, ValueError):
        rating = 0
    if rating <= 0:
        return {"status": "missing_actor_rating"}

    if (
        not isinstance(game_id, str)
        or not game_id.strip()
        or not isinstance(ply, int)
        or ply < 1
        or not isinstance(move_number, int)
        or move_number < 1
        or not isinstance(fen_before, str)
        or not fen_before.strip()
        or not isinstance(played_san, str)
        or not played_san.strip()
        or not isinstance(best_move_san, str)
        or not best_move_san.strip()
        or not isinstance(pv_after_played, (tuple, list))
        or not isinstance(pv_after_best, (tuple, list))
    ):
        return {"status": "missing_stored_evidence"}
    try:
        loss = max(0, int(float(cp_loss)))
    except (TypeError, ValueError):
        return {"status": "missing_stored_evidence"}
    if loss < caption_suppress_threshold_cp(rating):
        return {"status": "below_rating_threshold"}
    try:
        board = chess.Board(fen_before)
        board.parse_san(played_san)
        board.parse_san(best_move_san)
    except Exception:
        return {"status": "invalid_stored_evidence"}

    try:
        proof = build_verified_hidden_opportunity(
            fen_before=fen_before,
            played_san=played_san,
            best_move_san=best_move_san,
            pv_after_played=list(pv_after_played),
            pv_after_best=list(pv_after_best),
            cp_loss=loss,
        )
    except Exception:
        return {"status": "invalid_stored_evidence"}
    if proof is None:
        return {"status": "not_proved"}

    event = TeachableEvent(
        event_id=(
            f"{game_id}:{ply}:hidden_opportunity:"
            f"{proof.fingerprint[:16]}"
        ),
        move=MoveReference(
            ply=int(ply),
            number=int(move_number),
            san=played_san,
            actor=event_actor,
        ),
        concept=ConceptReference(concept_id=HIDDEN_OPPORTUNITY_CONCEPT_ID),
        outcome=EventOutcome.MISSED,
        opportunity=OpportunityEvidence(eligible=True),
        evidence=EventEvidence(
            quality_id=proof.quality_id,
            source_version=(
                f"{HIDDEN_OPPORTUNITY_SHADOW_VERSION}+"
                f"{HIDDEN_OPPORTUNITY_COMPOSER_VERSION}"
            ),
            provenance=(
                f"stored_move_evaluation:{game_id}:{ply}",
                f"hidden_opportunity_proof:{proof.fingerprint}",
            ),
            final_verified=True,
        ),
        teaching=TeachingReference(),
        requested_surface=QualitySurface.DIAGNOSTIC,
        reflection_eligible=False,
    )
    if event.player_authorized:
        raise ReviewContractViolation(
            "Hidden Opportunity Shadow evidence cannot authorize a player"
        )
    return {
        "status": "candidate",
        "candidate": {
            "schema_version": HIDDEN_OPPORTUNITY_SHADOW_VERSION,
            "actor_rating_band": get_rating_band(rating),
            "selection_features": {
                "cp_loss": loss,
                "ply": int(ply),
                "actor": event_actor.value,
            },
            "event": event.contract_dict(),
            "proof": proof.contract_dict(),
        },
    }


def _stored_move_san(
    board: chess.Board,
    *tokens: Any,
) -> Optional[str]:
    for token in tokens:
        text = str(token or "").strip()
        if not text:
            continue
        try:
            move = chess.Move.from_uci(text)
            if move in board.legal_moves:
                return board.san(move)
        except ValueError:
            pass
        try:
            return board.san(board.parse_san(text))
        except (AssertionError, ValueError):
            continue
    return None


def stored_row_matches_played_move(
    *,
    row: Mapping[str, Any],
    fen_before: str,
    played_san: str,
) -> bool:
    """Require exact position and played-move alignment for a stored row."""
    if " ".join(str(row.get("fen_before") or "").split()[:4]) != (
        " ".join(str(fen_before or "").split()[:4])
    ):
        return False
    try:
        board = chess.Board(fen_before)
    except (TypeError, ValueError):
        return False
    stored_san = _stored_move_san(
        board,
        row.get("move_uci"),
        row.get("move"),
        row.get("move_san"),
        row.get("played_move"),
    )
    actual_san = _stored_move_san(board, played_san)
    return bool(stored_san and actual_san and stored_san == actual_san)


def evaluate_hidden_opportunity_stored_row(
    *,
    game_id: str,
    user_color: str,
    side_ratings: Mapping[str, Optional[int]],
    row: Mapping[str, Any],
) -> Dict[str, Any]:
    """Normalize one stored engine row into the canonical Shadow adapter."""
    fen_before = str(row.get("fen_before") or "")
    try:
        board = chess.Board(fen_before)
    except (TypeError, ValueError):
        return {"status": "invalid_stored_evidence"}
    normalized_user_color = str(user_color or "").strip().lower()
    if normalized_user_color not in {"white", "black"}:
        return {"status": "invalid_stored_evidence"}
    played_san = _stored_move_san(
        board,
        row.get("move_uci"),
        row.get("move"),
        row.get("move_san"),
        row.get("played_move"),
    )
    best_move_san = _stored_move_san(
        board,
        row.get("best_move_uci"),
        row.get("best_move"),
        row.get("best_move_san"),
    )
    if not played_san or not best_move_san:
        return {"status": "missing_stored_evidence"}
    mover_color = "white" if board.turn == chess.WHITE else "black"
    return evaluate_hidden_opportunity_shadow(
        game_id=game_id,
        ply=board.ply() + 1,
        move_number=board.fullmove_number,
        actor=(
            EventActor.USER
            if mover_color == normalized_user_color
            else EventActor.OPPONENT
        ),
        actor_rating=side_ratings.get(mover_color),
        fen_before=fen_before,
        played_san=played_san,
        best_move_san=best_move_san,
        pv_after_played=row.get("pv_after_played") or [],
        pv_after_best=row.get("pv_after_best") or [],
        cp_loss=row.get("cp_loss"),
    )


def build_hidden_opportunity_shadow_summary(
    evaluations: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    """Build the stored, unranked census for one game."""
    status_counts = {status: 0 for status in sorted(HIDDEN_OPPORTUNITY_STATUSES)}
    candidates = []
    for evaluation in evaluations:
        status = str(evaluation.get("status") or "")
        if status not in HIDDEN_OPPORTUNITY_STATUSES:
            raise ReviewContractViolation(
                "unknown Hidden Opportunity Shadow evaluation status"
            )
        status_counts[status] += 1
        if status == "candidate":
            candidate = evaluation.get("candidate")
            if not isinstance(candidate, Mapping):
                raise ReviewContractViolation(
                    "candidate status requires a typed candidate"
                )
            event = candidate.get("event") or {}
            proof = candidate.get("proof") or {}
            fingerprint = str(proof.get("fingerprint") or "")
            if (
                (event.get("display") or {}).get("authorized") is not False
                or (event.get("display") or {}).get("requested_surface")
                != QualitySurface.DIAGNOSTIC.value
                or (event.get("evidence") or {}).get("quality_id")
                != proof.get("quality_id")
                or (event.get("evidence") or {}).get("final_verified")
                is not True
                or not fingerprint
                or (
                    f"hidden_opportunity_proof:{fingerprint}"
                    not in ((event.get("evidence") or {}).get("provenance") or [])
                )
            ):
                raise ReviewContractViolation(
                    "Hidden Opportunity candidate breaks its Shadow contract"
                )
            candidates.append(dict(candidate))

    return {
        "schema_version": HIDDEN_OPPORTUNITY_SHADOW_VERSION,
        "composer_version": HIDDEN_OPPORTUNITY_COMPOSER_VERSION,
        "rollout_mode": "shadow",
        "ranking_formula": None,
        "positions_seen": len(evaluations),
        "above_threshold_positions": (
            status_counts["candidate"]
            + status_counts["not_proved"]
            + status_counts["invalid_stored_evidence"]
        ),
        "candidate_count": len(candidates),
        "status_counts": status_counts,
        "candidates": candidates,
    }


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
    hidden_opportunity_evaluations: Sequence[Mapping[str, Any]] = (),
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
        "hidden_opportunities": build_hidden_opportunity_shadow_summary(
            hidden_opportunity_evaluations
        ),
        **result.contract_dict(),
    }
