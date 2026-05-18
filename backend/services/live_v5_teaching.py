"""
Live V5 Teaching — Phase 1.1 wedge (Mohit signoff 2026-05-18)
==============================================================

Brings the V5 caption pipeline (28 principles + 24 shape patterns +
named-rule anchors + Parth bug fixes + endgame principles) into
Play with Coach as a sidebar block underneath the existing realtime
coaching message.

See project memories:
  - project_play_with_coach_teaching_integration.md (parent deep plan)
  - project_play_with_coach_phase1_design.md (this phase's spec)
  - project_suppression_key_overhaul.md (state-keyed suppression layer
    this depends on)

Latency contract: this function targets <400-700ms total. It calls
extract_facts (pure Python, ~50-100ms) + resolve_priority (pure Python,
~10-50ms) + suppression check (set lookup, microseconds). It does NOT
call the LLM polish step — that's deferred to an async task with guards
(Phase 1.4).

Truth layer: the deterministic draft returned here is the ground-truth
caption per [[llm-as-controlled-narrator]]. LLM polish is presentation
only; if polish fails / times out / contradicts, the draft stays.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Set, Tuple

import chess

from services.caption_facts import extract_facts
from services.caption_principles import CAPTION_PRINCIPLES
from services.caption_priority_resolver import resolve_priority

logger = logging.getLogger(__name__)


# Build a quick lookup so we can read each principle's suppress policy.
_CAPTION_PRINCIPLES_BY_ID: Dict[str, Dict[str, Any]] = {
    p["id"]: p for p in CAPTION_PRINCIPLES if isinstance(p, dict) and p.get("id")
}


def _is_user_flag_enabled(user_doc: Dict[str, Any], session_doc: Dict[str, Any]) -> bool:
    """Check feature flag with per-session override.

    Priority:
      1. session feature_overrides.pwc_v5_teaching (if set, wins)
      2. user feature_flags.pwc_v5_teaching.enabled
      3. default: False
    """
    override = (session_doc.get("feature_overrides") or {}).get("pwc_v5_teaching")
    if override is not None:
        return bool(override)
    flag = (user_doc.get("feature_flags") or {}).get("pwc_v5_teaching") or {}
    return bool(flag.get("enabled"))


def _passes_suppression(
    principle_id: str,
    state_key: Optional[Tuple],
    fired_principles: Set[str],
    fired_state_keys: Set[Tuple],
) -> bool:
    """Check session-level suppression. Returns True if the fire is
    NEW (not yet suppressed) — caller mutates the sets after surfacing.

    Mirrors the V5 wiring layer's three-policy suppression
    (project_suppression_key_overhaul.md) but scoped to the
    PlayWithCoach session, not the V5 game record.
    """
    entry = _CAPTION_PRINCIPLES_BY_ID.get(principle_id, {})
    suppress = entry.get("suppress", "once_per_move")

    if suppress == "once_per_move":
        return True  # no game-state filter
    if suppress in ("once_per_game", "once_per_state_entry"):
        return principle_id not in fired_principles
    if suppress == "once_per_state_key":
        if state_key is None:
            # Degrade to once_per_game when detector didn't emit state_key.
            return principle_id not in fired_principles
        return state_key not in fired_state_keys
    # Unknown policy — be conservative, fire it.
    return True


def _draft_from_decision(decision: Dict[str, Any]) -> str:
    """Build the deterministic draft string from resolver decision.

    When focus=='principle' with a specialised detail, the resolver
    has already produced the right text via _principle_detail_text.
    The draft is `{anchor_name} — {anchor_detail}` mirroring the
    V5 review pipeline.
    """
    anchor_name = decision.get("anchor_name") or ""
    anchor_detail = decision.get("anchor_detail") or ""
    if anchor_name and anchor_detail:
        return f"{anchor_name} — {anchor_detail}"
    # Fallback to controlled-gen draft (move["caption"] for non-principle anchors).
    return (decision.get("deterministic_draft") or "").strip()


def v5_teaching_decision_for_live_move(
    *,
    fen_before: str,
    played_san: str,
    best_move_san: Optional[str],
    eval_before_cp: Optional[int],
    eval_after_cp: Optional[int],
    cp_loss: int,
    pv_after_played: Optional[List[str]] = None,
    pv_after_best: Optional[List[str]] = None,
    move_history_san: Optional[List[str]] = None,
    full_move_number: Optional[int] = None,
    mover_is_user: bool,
    user_doc: Dict[str, Any],
    session_doc: Dict[str, Any],
    session_fired_principles: Optional[Set[str]] = None,
    session_fired_state_keys: Optional[Set[Tuple]] = None,
) -> Optional[Dict[str, Any]]:
    """Deterministic V5 teaching block for one live move.

    Returns None when the feature flag is off, the detector found
    nothing worth surfacing, or suppression silences this fire.

    Returns a v5_block dict when surfacing:
        {
            "anchor_name":   str,        # "Rule of the Square"
            "anchor_detail": str,        # the specialised teaching text
            "deterministic_draft": str,  # "{name} — {detail}"
            "principle_id": Optional[str],
            "shape_pattern_id": Optional[str],
            "polish_status": "draft",
            "is_coach_move_teaching": bool,
            "protected_entities": list,  # for the async polish guards
            "state_key": Optional[Tuple],
            "principle_suppress_policy": Optional[str],
        }

    Callers are responsible for:
      - mutating session_fired_principles / session_fired_state_keys
        on the returned block (so the next move's call sees the update)
      - writing the v5_block to coach_messages
      - scheduling the async polish task (Phase 1.4) if desired
    """
    # Feature flag gate FIRST — fastest exit.
    if not _is_user_flag_enabled(user_doc, session_doc):
        return None

    if not played_san:
        return None
    if not fen_before:
        return None

    # Run the V5 detection pipeline. Pure-Python, fast.
    try:
        facts = extract_facts(
            fen_before=fen_before,
            played_san=played_san,
            best_move_san=best_move_san,
            eval_before_cp=eval_before_cp,
            eval_after_cp=eval_after_cp,
            cp_loss=cp_loss,
            pv_after_played=pv_after_played or [],
            pv_after_best=pv_after_best or [],
            move_history_san=move_history_san or [],
            full_move_number=full_move_number,
            mover_is_user=mover_is_user,
        )
    except (chess.InvalidMoveError, ValueError) as e:
        logger.info(f"[live_v5_teaching] extract_facts failed for {played_san}: {e}")
        return None
    except Exception:
        logger.exception(f"[live_v5_teaching] extract_facts crashed for {played_san}")
        return None

    # Apply session-level suppression BEFORE the resolver picks an anchor.
    # The resolver's own pickprioritizes principles; we need to filter
    # the suppressed ones out of facts["principles_violated"] first.
    fired_principles = session_fired_principles if session_fired_principles is not None else set()
    fired_state_keys = session_fired_state_keys if session_fired_state_keys is not None else set()

    raw_violated = facts.get("principles_violated") or []
    surviving: List[Dict[str, Any]] = []
    for ev in raw_violated:
        pid = ev.get("principle_id")
        if not pid:
            continue
        sk = ev.get("state_key")
        if _passes_suppression(pid, sk, fired_principles, fired_state_keys):
            surviving.append(ev)
    facts["principles_violated"] = surviving

    # Build the resolver decision off the suppression-filtered facts.
    try:
        # resolve_priority operates on a move-record-shaped dict, not
        # the facts dict directly. Build a minimal move record.
        move_record = {
            "caption_facts_principles_violated": facts.get("principles_violated") or [],
            "shape_pattern_id": facts.get("shape_pattern_id"),
            "shape_pattern_name": facts.get("shape_pattern_name"),
            "shape_pattern_desc": facts.get("shape_pattern_desc"),
            "shape_pattern_targets": facts.get("shape_pattern_targets"),
            "shape_pattern_executing_move": facts.get("shape_pattern_executing_move"),
            "shape_pattern_mover": facts.get("shape_pattern_mover"),
            "move_san": played_san,
            "best_move_san": best_move_san,
            "cp_loss": cp_loss,
            "phase": facts.get("phase"),
            "is_user_move": mover_is_user,
            "is_white": facts.get("moving_piece_color") == "white",
            "fen_before": fen_before,
            "fen_after": facts.get("fen_after"),
            "caption": "",  # let resolver build the draft from anchor_detail per Phase 0 fix
            "principle_cue": "",
            "principle_id_used": None,
            "rule_name": None,
        }
        decision = resolve_priority(move_record)
    except Exception:
        logger.exception(f"[live_v5_teaching] resolve_priority crashed for {played_san}")
        return None

    if decision.get("should_skip"):
        return None
    anchor_name = decision.get("anchor_name")
    if not anchor_name:
        return None

    # Identify the anchoring principle / shape so we know which
    # suppression set to update on return.
    anchored_principle_id: Optional[str] = None
    anchored_state_key: Optional[Tuple] = None
    if decision.get("focus") == "principle":
        # Pick the highest-priority surviving principle as the anchor.
        sorted_pv = sorted(
            facts.get("principles_violated") or [],
            key=lambda ev: _CAPTION_PRINCIPLES_BY_ID.get(
                ev.get("principle_id") or "", {}
            ).get("priority", 99),
        )
        if sorted_pv:
            anchored_principle_id = sorted_pv[0].get("principle_id")
            anchored_state_key = sorted_pv[0].get("state_key")

    shape_pattern_id = decision.get("focus") == "shape" and (
        facts.get("shape_pattern_id") or None
    ) or None

    draft = _draft_from_decision(decision)
    if not draft:
        return None

    v5_block = {
        "anchor_name":          anchor_name,
        "anchor_detail":        decision.get("anchor_detail") or "",
        "deterministic_draft":  draft,
        "principle_id":         anchored_principle_id,
        "shape_pattern_id":     shape_pattern_id,
        "polish_status":        "draft",
        "is_coach_move_teaching": not mover_is_user,
        "protected_entities":   decision.get("protected_entities") or [],
        "state_key":            anchored_state_key,
        "principle_suppress_policy": (
            _CAPTION_PRINCIPLES_BY_ID.get(anchored_principle_id or "", {}).get("suppress")
            if anchored_principle_id else None
        ),
    }
    return v5_block


def update_session_suppression(
    session_fired_principles: Set[str],
    session_fired_state_keys: Set[Tuple],
    v5_block: Dict[str, Any],
) -> None:
    """Mutate the session-level suppression sets after surfacing a v5_block.

    Call this AFTER you've decided to write the block to coach_messages.
    Skipping this call (e.g., on a dry-run / preview) keeps the next
    move's call eligible to fire the same lesson.
    """
    pid = v5_block.get("principle_id")
    state_key = v5_block.get("state_key")
    policy = v5_block.get("principle_suppress_policy")
    if not pid:
        return
    if policy in ("once_per_game", "once_per_state_entry"):
        session_fired_principles.add(pid)
    elif policy == "once_per_state_key":
        if state_key is not None:
            session_fired_state_keys.add(state_key)
        else:
            session_fired_principles.add(pid)
    # once_per_move → no session-level state update
