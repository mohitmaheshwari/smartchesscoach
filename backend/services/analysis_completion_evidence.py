"""Canonical observation and learning-evidence completion for analyzed games.

Both imported games and completed Play With Coach games already own a stored
analysis.  This module is the one additive chokepoint that turns that stored
analysis into move observations and source-aware learning evidence.  It does
not run an engine, define a chess detector, choose a focus, or own mastery.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Mapping, Optional, Tuple

from services.concept_contract_registry import complete_coaching_system_enabled
from services.focus_bridge import DESTINATION_SAFETY_FACT_VERSION
from services.focus_game_service import summarize_pic_observations
from services.personal_curriculum import AssistanceKind, EvidenceSourceType
from services.review_learning_adapter import (
    application_results_from_observations,
    build_shadow_learning_event,
    store_shadow_lesson_results,
    store_shadow_lesson_results_sync,
)


COMPLETION_VERSION = "analysis_completion_evidence.v1"
PWC_EVIDENCE_MODES = frozenset(
    {"practice_assisted", "checkpoint_unassisted", "just_play"}
)
DESTINATION_SAFETY_QUALITY_ID = (
    "gap:piece_safety:destination_safety_exact"
)


@dataclass(frozen=True)
class AnalysisEvidenceContext:
    source_type: EvidenceSourceType
    origin: str
    evidence_mode: str
    assistance: Tuple[AssistanceKind, ...] = ()
    assistance_measured: bool = True
    focus_id: Optional[str] = None
    instruction_id: Optional[str] = None

    def __post_init__(self) -> None:
        if self.source_type not in (
            EvidenceSourceType.ORGANIC_GAME,
            EvidenceSourceType.COACHED_APPLICATION,
        ):
            raise ValueError("analysis evidence source must be organic or coached")
        if not str(self.origin or "").strip():
            raise ValueError("analysis evidence origin is required")
        if not str(self.evidence_mode or "").strip():
            raise ValueError("analysis evidence mode is required")
        if any(not isinstance(item, AssistanceKind) for item in self.assistance):
            raise ValueError("analysis evidence assistance is invalid")
        if not isinstance(self.assistance_measured, bool):
            raise ValueError("assistance_measured must be boolean")


def external_game_context() -> AnalysisEvidenceContext:
    """Preserve the existing imported-game identity and event keys."""
    return AnalysisEvidenceContext(
        source_type=EvidenceSourceType.ORGANIC_GAME,
        origin="external_game_observation",
        evidence_mode="ordinary_play",
    )


def effective_pwc_evidence_mode(
    requested_mode: Any,
    *,
    game_mode: str,
    has_verified_focus: bool,
) -> str:
    """Fail closed when a session cannot honestly be a focus checkpoint."""
    requested = str(requested_mode or "").strip()
    if requested not in PWC_EVIDENCE_MODES:
        requested = "practice_assisted" if game_mode == "coach" else "just_play"
    if requested == "practice_assisted" and game_mode != "coach":
        return "just_play"
    if requested == "checkpoint_unassisted" and (
        game_mode != "play" or not has_verified_focus
    ):
        return "just_play"
    return requested


def pwc_checkpoint_focus_available(primary: Mapping[str, Any]) -> bool:
    return bool(
        primary.get("focus_id")
        and primary.get("instruction_id")
        and primary.get("detector_quality_id")
        == DESTINATION_SAFETY_QUALITY_ID
    )


def pwc_game_context(session: Mapping[str, Any]) -> AnalysisEvidenceContext:
    primary = ((session.get("coaching_context") or {}).get("primary_focus") or {})
    mode = effective_pwc_evidence_mode(
        session.get("evidence_mode"),
        game_mode=str(session.get("game_mode") or "coach"),
        has_verified_focus=pwc_checkpoint_focus_available(primary),
    )
    assistance = (
        (AssistanceKind.GUIDED_LINE,)
        if mode == "practice_assisted"
        else ()
    )
    return AnalysisEvidenceContext(
        source_type=EvidenceSourceType.COACHED_APPLICATION,
        origin=f"pwc_{mode}_observation",
        evidence_mode=mode,
        assistance=assistance,
        assistance_measured=True,
        focus_id=str(primary.get("focus_id") or "") or None,
        instruction_id=str(primary.get("instruction_id") or "") or None,
    )


def _prepare(
    *,
    user_id: str,
    game: Mapping[str, Any],
    analysis: Mapping[str, Any],
    context: AnalysisEvidenceContext,
) -> Dict[str, Any]:
    from services.move_observation_deriver import derive_observations_for_game

    game_id = str(game.get("game_id") or "")
    user_color = str(game.get("user_color") or "")
    if not user_id or not game_id or user_color not in {"white", "black"}:
        raise ValueError("analysis completion requires user, game and user color")
    stockfish_analysis = analysis.get("stockfish_analysis") or {}
    observations = derive_observations_for_game(
        stockfish_analysis=stockfish_analysis,
        game_id=game_id,
        user_id=user_id,
        user_color=user_color,
        decryption_v5_data=analysis.get("decryption_v5_data"),
    )
    results = application_results_from_observations(
        game_id=game_id,
        observations=observations,
        occurred_at=(
            game.get("date_played")
            or game.get("imported_at")
            or analysis.get("analyzed_at")
            or analysis.get("created_at")
            or datetime.now(timezone.utc)
        ),
        include_handled=complete_coaching_system_enabled(),
        source_type=context.source_type,
        assistance=context.assistance,
        assistance_measured=context.assistance_measured,
    )
    events = [
        build_shadow_learning_event(result, origin=context.origin)
        for result in results
    ]
    summary = summarize_pic_observations(
        observations,
        proof_detector_id=DESTINATION_SAFETY_FACT_VERSION,
    )
    return {
        "game_id": game_id,
        "observations": observations,
        "events": events,
        "summary": summary,
    }


def _marker(prepared: Mapping[str, Any], context: AnalysisEvidenceContext) -> Dict[str, Any]:
    return {
        "version": COMPLETION_VERSION,
        "idempotency_key": (
            f"{COMPLETION_VERSION}:{prepared['game_id']}:{context.origin}"
        ),
        "source_type": context.source_type.value,
        "evidence_mode": context.evidence_mode,
        "assisted": bool(context.assistance),
        "assistance_measured": context.assistance_measured,
        "observations": len(prepared["observations"]),
        "application_events": len(prepared["events"]),
        "summary": dict(prepared["summary"]),
        "completed_at": datetime.now(timezone.utc),
    }


def _pwc_envelope(
    prepared: Mapping[str, Any], context: AnalysisEvidenceContext
) -> Optional[Dict[str, Any]]:
    if context.source_type != EvidenceSourceType.COACHED_APPLICATION:
        return None
    return {
        "version": 1,
        "idempotency_key": (
            f"pwc:{prepared['game_id']}:move-observation-v18:"
            f"{context.evidence_mode}"
        ),
        "focus_id": context.focus_id,
        "instruction_id": context.instruction_id,
        "environment": "coach",
        "evidence_mode": context.evidence_mode,
        "assisted": bool(context.assistance),
        "proof_detector_id": DESTINATION_SAFETY_FACT_VERSION,
        "summary": dict(prepared["summary"]),
        "mastery_eligible": False,
        "resolution_eligible": context.evidence_mode == "checkpoint_unassisted",
        "verdict": (
            "checkpoint_measured"
            if context.evidence_mode == "checkpoint_unassisted"
            else (
                "practice_recorded"
                if context.evidence_mode == "practice_assisted"
                else "discovery_only"
            )
        ),
        "measured_at": datetime.now(timezone.utc),
    }


def complete_analyzed_game_evidence_sync(
    db: Any,
    *,
    user_id: str,
    game: Mapping[str, Any],
    analysis: Mapping[str, Any],
    context: Optional[AnalysisEvidenceContext] = None,
) -> Dict[str, Any]:
    """Synchronous worker entrypoint; safe to call repeatedly."""
    context = context or external_game_context()
    prepared = _prepare(
        user_id=user_id,
        game=game,
        analysis=analysis,
        context=context,
    )
    for observation in prepared["observations"]:
        db.move_observations.update_one(
            {
                "user_id": observation["user_id"],
                "game_id": observation["game_id"],
                "move_number": observation["move_number"],
            },
            {"$set": observation},
            upsert=True,
        )

    focus_envelope = None
    if context.source_type == EvidenceSourceType.ORGANIC_GAME:
        from services.focus_game_service import record_pic_game_evidence_sync

        focus_envelope = record_pic_game_evidence_sync(
            db, user_id, dict(game), prepared["observations"]
        )
    if prepared["events"]:
        store_shadow_lesson_results_sync(
            db.learning_sessions,
            user_id=user_id,
            events=prepared["events"],
        )

    marker = _marker(prepared, context)
    db.games.update_one(
        {"user_id": user_id, "game_id": prepared["game_id"]},
        {"$set": {"analysis_evidence_completion": marker}},
    )
    return {
        **marker,
        "observations_data": prepared["observations"],
        "focus_envelope": focus_envelope,
        "pwc_evidence": _pwc_envelope(prepared, context),
    }


async def complete_analyzed_game_evidence(
    db: Any,
    *,
    user_id: str,
    game: Mapping[str, Any],
    analysis: Mapping[str, Any],
    context: AnalysisEvidenceContext,
) -> Dict[str, Any]:
    """Async Play With Coach entrypoint; safe to call repeatedly."""
    prepared = _prepare(
        user_id=user_id,
        game=game,
        analysis=analysis,
        context=context,
    )
    for observation in prepared["observations"]:
        await db.move_observations.update_one(
            {
                "user_id": observation["user_id"],
                "game_id": observation["game_id"],
                "move_number": observation["move_number"],
            },
            {"$set": observation},
            upsert=True,
        )
    if prepared["events"]:
        await store_shadow_lesson_results(
            db.learning_sessions,
            user_id=user_id,
            events=prepared["events"],
        )

    marker = _marker(prepared, context)
    await db.games.update_one(
        {"user_id": user_id, "game_id": prepared["game_id"]},
        {"$set": {"analysis_evidence_completion": marker}},
    )
    return {
        **marker,
        "observations_data": prepared["observations"],
        "focus_envelope": None,
        "pwc_evidence": _pwc_envelope(prepared, context),
    }


__all__ = [
    "AnalysisEvidenceContext",
    "COMPLETION_VERSION",
    "PWC_EVIDENCE_MODES",
    "complete_analyzed_game_evidence",
    "complete_analyzed_game_evidence_sync",
    "effective_pwc_evidence_mode",
    "external_game_context",
    "pwc_checkpoint_focus_available",
    "pwc_game_context",
]
