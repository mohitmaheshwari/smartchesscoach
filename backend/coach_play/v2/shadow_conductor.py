"""Read-only PWC V2 conductor bake-off.

All policies receive the exact same admitted candidates. Their winners are
stored for review but never returned as player-facing decisions. The numeric
maps below are experimental candidates, not production thresholds.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping, Optional

from .contracts import (
    CandidateFocus,
    CandidateNovelty,
    CandidateTiming,
    CandidateUrgency,
    CoachingCandidate,
)

SHADOW_SCHEMA_VERSION = "pwc_v2_shadow.v1"
SHADOW_POLICY_VERSION = "pwc_v2_policy_bakeoff.v1"
UNIFIED_V1_ADAPTER_VERSION = "pwc_v2_adapter.unified_v1.v1"
SHADOW_POLICIES = (
    "safety_focus_lexicographic",
    "expected_learning_value",
    "phase_guarded",
)

_URGENCY_RANK = {
    CandidateUrgency.CONTEXT: 0,
    CandidateUrgency.TEACHABLE: 1,
    CandidateUrgency.IMPORTANT: 2,
    CandidateUrgency.IMMEDIATE_DANGER: 3,
}
_FOCUS_RANK = {
    CandidateFocus.NONE: 0,
    CandidateFocus.HISTORICAL: 1,
    CandidateFocus.SUPPORTING: 2,
    CandidateFocus.PRIMARY: 3,
}
_NOVELTY_RANK = {
    CandidateNovelty.REPEATED: 0,
    CandidateNovelty.REINFORCEMENT: 1,
    CandidateNovelty.NEW: 2,
}


def _stable_candidate_id(
    *, turn_id: str, source: str, concept_key: str, claim: str
) -> str:
    digest = hashlib.sha256(
        f"{turn_id}|{source}|{concept_key}|{claim}".encode("utf-8")
    ).hexdigest()[:16]
    return f"pwc2c:{digest}"


def candidate_from_unified_decision(
    *,
    turn_id: str,
    decision: Mapping[str, Any],
    engine_evidence: Mapping[str, Any],
    fen_before: str,
    uci: str,
    assistance_level: Optional[int] = None,
    game_phase: Optional[str] = None,
) -> Optional[CoachingCandidate]:
    """Adapt only an already-verified Unified V1 visible decision."""
    layer = str(decision.get("layer") or "silent")
    if layer not in {"advisory", "critical_interrupt"}:
        return None
    proof = decision.get("proof") or {}
    claim = str(decision.get("text") or "").strip()
    proof_verified = bool(
        proof.get("caption_verified") and engine_evidence.get("eval_valid")
    )

    if game_phase is None:
        try:
            from services.game_phase_service import get_game_phase

            game_phase = str(get_game_phase(fen_before).get("phase_label") or "")
        except Exception:
            game_phase = None

    concept_key = str(
        decision.get("conceptKey") or decision.get("category") or ""
    ).strip()
    category = str(decision.get("category") or concept_key).strip()
    rule_name = str(proof.get("rule_name") or "").strip()
    abstention_reasons = []
    if not proof.get("caption_verified"):
        abstention_reasons.append("caption_not_verified")
    if not engine_evidence.get("eval_valid"):
        abstention_reasons.append("engine_evidence_invalid")
    if not rule_name:
        abstention_reasons.append("caption_rule_missing")
    candidate = CoachingCandidate(
        candidate_id=_stable_candidate_id(
            turn_id=turn_id,
            source=str(decision.get("source") or "pwc_unified_v1"),
            concept_key=concept_key,
            claim=claim,
        ),
        turn_id=turn_id,
        source=str(decision.get("source") or "pwc_unified_v1"),
        timing=(
            CandidateTiming.BEFORE_MOVE
            if layer == "critical_interrupt"
            else CandidateTiming.AFTER_MOVE
        ),
        category=category,
        concept_key=concept_key,
        claim=claim,
        transferable_instruction=(
            str(decision.get("instruction") or "").strip() or None
        ),
        urgency=(
            CandidateUrgency.IMMEDIATE_DANGER
            if layer == "critical_interrupt"
            else CandidateUrgency.IMPORTANT
        ),
        focus_relevance=(
            CandidateFocus.PRIMARY
            if decision.get("focusMatch")
            else CandidateFocus.NONE
        ),
        novelty=CandidateNovelty.NEW,
        assistance_level=assistance_level,
        proof_authority="caption_pipeline",
        proof_references=((rule_name,) if rule_name else ()),
        proof_verified=proof_verified,
        abstention_reason=(";".join(abstention_reasons) or None),
        game_phase=game_phase,
        evidence={
            "fen": fen_before,
            "move": uci,
            "source_version": UNIFIED_V1_ADAPTER_VERSION,
            "move_quality": engine_evidence.get("move_quality"),
            "cp_loss": engine_evidence.get("cp_loss"),
            "best_move": engine_evidence.get("best_move"),
            "eval_valid": bool(engine_evidence.get("eval_valid")),
        },
        visual={
            "arrows": list(decision.get("arrows") or []),
            "highlight_squares": list(decision.get("highlightSquares") or []),
        },
    )
    # Return rejected visible candidates too: the packet builder records their
    # abstention reasons while still excluding them from every policy winner.
    return candidate


def build_shadow_packet_from_unified_response(
    *,
    turn_id: str,
    live_response: Mapping[str, Any],
    engine_evidence: Mapping[str, Any],
    fen_before: str,
    uci: str,
    assistance_level: Optional[int] = None,
    created_at: Optional[str] = None,
) -> dict[str, Any]:
    """Adapt a live response without mutating or decorating that response."""
    decision = live_response.get("coachingDecision") or {}
    visual = live_response.get("visual") or {}
    candidate = candidate_from_unified_decision(
        turn_id=turn_id,
        decision={
            **decision,
            "arrows": list(visual.get("arrows") or []),
            "highlightSquares": list(visual.get("highlightSquares") or []),
        },
        engine_evidence=engine_evidence,
        fen_before=fen_before,
        uci=uci,
        assistance_level=assistance_level,
    )
    return build_shadow_packet(
        [candidate] if candidate else [],
        created_at=created_at,
    )


def _policy_score(policy: str, candidate: CoachingCandidate) -> tuple[int, ...]:
    urgency = _URGENCY_RANK[candidate.urgency]
    focus = _FOCUS_RANK[candidate.focus_relevance]
    novelty = _NOVELTY_RANK[candidate.novelty]
    instruction = int(bool(candidate.transferable_instruction))
    # Unknown assistance must never receive the same benefit as proven
    # independent play. It remains neutral until canonical help events can be
    # associated with this opportunity.
    unassisted = int(candidate.assistance_level == 0)

    if policy == "safety_focus_lexicographic":
        return (urgency, focus, instruction, unassisted, novelty)
    if policy == "expected_learning_value":
        # Experimental bake-off formula only. Data must authorize or reject it.
        return (focus * 4 + novelty * 3 + urgency * 2 + instruction + unassisted,)
    if policy == "phase_guarded":
        phase = str(candidate.game_phase or "").lower()
        category = candidate.category.lower()
        phase_match = int(
            (phase == "opening" and "opening" in category)
            or (phase.endswith("endgame") and "endgame" in category)
            or (
                phase.endswith("middlegame")
                and "opening" not in category
                and "endgame" not in category
            )
        )
        immediate = int(candidate.urgency == CandidateUrgency.IMMEDIATE_DANGER)
        return (immediate, phase_match, focus, urgency, novelty)
    raise ValueError(f"unknown shadow policy: {policy}")


def build_shadow_packet(
    candidates: Iterable[CoachingCandidate],
    *,
    created_at: Optional[str] = None,
) -> dict[str, Any]:
    """Compare three policies without choosing a player-facing winner."""
    unique: dict[str, CoachingCandidate] = {}
    rejected: list[dict[str, Any]] = []
    for candidate in candidates:
        errors = candidate.validation_errors()
        if errors:
            rejected.append(
                {
                    "candidate_id": candidate.candidate_id,
                    "reasons": list(errors),
                }
            )
            continue
        existing = unique.get(candidate.candidate_id)
        if existing is None:
            unique[candidate.candidate_id] = candidate
        elif existing.to_document() != candidate.to_document():
            rejected.append(
                {
                    "candidate_id": candidate.candidate_id,
                    "reasons": ["duplicate_candidate_conflict"],
                }
            )

    admitted = sorted(unique.values(), key=lambda item: item.candidate_id)
    policies: dict[str, Any] = {}
    winner_ids: list[str] = []
    for policy in SHADOW_POLICIES:
        scored = [
            (candidate, _policy_score(policy, candidate)) for candidate in admitted
        ]
        top_score = max((score for _, score in scored), default=None)
        tied_candidate_ids = sorted(
            candidate.candidate_id for candidate, score in scored if score == top_score
        )
        winner_id = tied_candidate_ids[0] if tied_candidate_ids else None
        if winner_id:
            winner_ids.append(winner_id)
        policies[policy] = {
            "winner_candidate_id": winner_id,
            "winner_score": list(top_score) if top_score is not None else None,
            "tied_candidate_ids": tied_candidate_ids,
            "tie": len(tied_candidate_ids) > 1,
        }

    return {
        "schema_version": SHADOW_SCHEMA_VERSION,
        "policy_version": SHADOW_POLICY_VERSION,
        "created_at": created_at or datetime.now(timezone.utc).isoformat(),
        "candidate_count": len(admitted),
        "rejected_count": len(rejected),
        "candidates": [candidate.to_document() for candidate in admitted],
        "rejected": rejected,
        "policies": policies,
        "disagreement": len(set(winner_ids)) > 1,
        "player_visible": False,
    }


__all__ = [
    "SHADOW_POLICIES",
    "SHADOW_POLICY_VERSION",
    "SHADOW_SCHEMA_VERSION",
    "UNIFIED_V1_ADAPTER_VERSION",
    "build_shadow_packet",
    "build_shadow_packet_from_unified_response",
    "candidate_from_unified_decision",
]
