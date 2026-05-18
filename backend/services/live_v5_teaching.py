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
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

import chess

from services.caption_facts import extract_facts
from services.caption_principles import PRINCIPLES as CAPTION_PRINCIPLES
from services.caption_priority_resolver import resolve_priority

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────
# Phase 1.2 — structured material-value gate (Mohit signoff 2026-05-18)
#
# Goal: avoid surfacing the V5 teaching block when the existing
# realtime coaching message already names the same pattern/target.
#
# Mohit's spec explicitly says NOT to string-match against the
# realtime message text. Compare structured fields instead.
#
# In this Phase 1.2 ship, realtime emits the fields it ALREADY has
# (severity, target/piece squares parsed from SAN, best_move_family
# heuristically derived from best_move_san). The richer fields
# (principle_id, pattern_id, tactic_type) stay None until a later
# refactor of realtime_coaching_feedback adds principle detection.
# The gate is built to handle None gracefully — it suppresses only
# when there's clear evidence of duplication.
# ─────────────────────────────────────────────────────────────────


@dataclass
class MoveFeedbackTag:
    """Structured signal from the realtime feedback path. Used by the
    V5 surfacing gate to decide whether V5 adds a new abstraction or
    is duplicating what realtime already said.
    """
    severity: str  # excellent / good / inaccuracy / mistake / blunder
    principle_id: Optional[str] = None      # filled by future refactor
    pattern_id: Optional[str] = None        # filled by future refactor
    tactic_type: Optional[str] = None       # filled by future refactor
    target_square: Optional[str] = None     # parsable from SAN today
    piece_square: Optional[str] = None      # parsable from SAN today
    best_move_family: Optional[str] = None  # heuristic from best_move_san


_SAN_TARGET_RE = re.compile(r"([a-h][1-8])(?:=[QRBN])?[+#]?$")
_SAN_PIECE_FROM_RE = re.compile(r"^[NBRQK]?([a-h]?[1-8]?)x?[a-h][1-8]")


def _target_square_from_san(san: Optional[str]) -> Optional[str]:
    """Extract the destination square from a SAN like 'Nxe5+' or 'O-O'.

    Returns None for castling and unparsable input.
    """
    if not san or san in ("O-O", "O-O-O", "0-0", "0-0-0"):
        return None
    m = _SAN_TARGET_RE.search(san)
    return m.group(1) if m else None


def _classify_rating_band(user_rating: Optional[int]) -> str:
    """Same banding as deterministic_coach_service.RATING_BANDS."""
    if user_rating is None:
        return "beginner_high"
    if user_rating < 1000:
        return "beginner_low"
    if user_rating < 1400:
        return "beginner_high"
    if user_rating < 1800:
        return "intermediate"
    return "advanced"


# Rating-aware classification thresholds — mirrors
# realtime_coaching_feedback._classify_move_quality so the V5 gate
# uses the same severity vocabulary the realtime path uses.
_SEVERITY_THRESHOLDS_CP = {
    "beginner_low":  {"inaccuracy": 150, "mistake": 300, "blunder": 300},
    "beginner_high": {"inaccuracy": 75,  "mistake": 200, "blunder": 200},
    "intermediate":  {"inaccuracy": 50,  "mistake": 150, "blunder": 150},
    "advanced":      {"inaccuracy": 30,  "mistake": 100, "blunder": 100},
}


def _severity_from_cp_loss(cp_loss: int, user_rating: Optional[int]) -> str:
    band = _classify_rating_band(user_rating)
    t = _SEVERITY_THRESHOLDS_CP.get(band, _SEVERITY_THRESHOLDS_CP["beginner_high"])
    if cp_loss >= t["blunder"]:
        return "blunder"
    if cp_loss >= t["mistake"]:
        return "mistake"
    if cp_loss >= t["inaccuracy"]:
        return "inaccuracy"
    if cp_loss <= 5:
        return "excellent"
    return "good"


def build_move_feedback_tag(
    *,
    played_san: str,
    best_move_san: Optional[str],
    cp_loss: int,
    user_rating: Optional[int],
) -> MoveFeedbackTag:
    """Build the structured tag from the data realtime already has.

    Phase 1.2 MVP: severity + parsed squares. Optional fields
    (principle_id, pattern_id, tactic_type) stay None until the
    realtime path is refactored to compute them.
    """
    severity = _severity_from_cp_loss(int(cp_loss or 0), user_rating)
    target_sq = _target_square_from_san(played_san)
    best_target_sq = _target_square_from_san(best_move_san)
    # best_move_family: rough heuristic from the best move's piece
    bm = (best_move_san or "").lstrip()
    best_move_family: Optional[str] = None
    if bm:
        if bm in ("O-O", "O-O-O", "0-0", "0-0-0"):
            best_move_family = "castle"
        elif bm[0] == "K":
            best_move_family = "K_move"
        elif bm[0] in "NBRQ":
            best_move_family = {
                "N": "developing_minor", "B": "developing_minor",
                "R": "rook_move", "Q": "queen_move",
            }.get(bm[0])
        else:
            best_move_family = "pawn_move"
    return MoveFeedbackTag(
        severity=severity,
        target_square=target_sq,
        piece_square=None,  # realtime path doesn't currently track piece origin
        best_move_family=best_move_family,
        principle_id=None,
        pattern_id=None,
        tactic_type=None,
    )


def should_suppress_v5_for_tag(
    tag: MoveFeedbackTag,
    v5_block: Dict[str, Any],
) -> Tuple[bool, str]:
    """Material-value gate. Returns (suppress, reason).

    Suppress V5 when the realtime tag already names what V5 would
    say. The check is structured (Mohit signoff 2026-05-18): no
    string matching against message text.
    """
    # Rule 1 — severity says no teaching needed.
    # Per Mohit: V5 must respect rating-aware silence. If realtime
    # classifies the move as fine for this user's rating, there's
    # no teaching gap to fill, even if V5 detected a principle.
    if tag.severity in ("excellent", "good"):
        return True, f"realtime severity={tag.severity!r}"

    # Rule 2 — principle_id duplicates (will activate when realtime
    # path emits principle_id; today this always passes through).
    if tag.principle_id and v5_block.get("principle_id"):
        if tag.principle_id == v5_block["principle_id"]:
            return True, "principle_id duplicate"

    # Rule 3 — pattern_id duplicates (same).
    if tag.pattern_id and v5_block.get("shape_pattern_id"):
        if tag.pattern_id == v5_block["shape_pattern_id"]:
            return True, "pattern_id duplicate"

    # Rule 4 — same tactic_type + same target square.
    if tag.tactic_type and tag.target_square:
        # Probe v5 evidence for matching tactic + target (the v5_block
        # exposes anchor_name but not raw evidence — degrade gracefully
        # until the v5 block layer carries tactic_type explicitly).
        anchor = (v5_block.get("anchor_name") or "").lower()
        if tag.tactic_type in anchor and tag.target_square in (v5_block.get("deterministic_draft") or ""):
            return True, f"tactic+target overlap ({tag.tactic_type})"

    return False, "no duplication"


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

    # Mirror the V5 wiring layer's principle-priority selection so the
    # resolver picks the SAME principle the review pipeline would.
    # Without this, resolve_priority falls back to source-order
    # (whichever detector fired first), which can land on a lower-
    # priority "walk the king" framing when the high-priority
    # END_RULE_OF_SQUARE is the right anchor.
    # Surfaced by Test 3 self-audit 2026-05-18 — Walloo21 was rendering
    # "Walk the king to safety — walk the king to safety." (tautology)
    # because resolver picked principles[0] = DEF_WALK_KING (priority 47)
    # instead of the priority-12 END_RULE_OF_SQUARE.
    _surviving = facts.get("principles_violated") or []
    _picked_principle_id: Optional[str] = None
    if _surviving:
        _sorted = sorted(
            _surviving,
            key=lambda ev: _CAPTION_PRINCIPLES_BY_ID.get(
                ev.get("principle_id") or "", {}
            ).get("priority", 99),
        )
        _picked_principle_id = _sorted[0].get("principle_id")

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
            "principle_id_used": _picked_principle_id,  # priority-sorted, mirrors V5 wiring
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


def build_polish_move_record(
    *,
    v5_block: Dict[str, Any],
    fen_before: str,
    played_san: str,
    best_move_san: Optional[str],
    eval_before_cp: Optional[int],
    eval_after_cp: Optional[int],
    cp_loss: int,
    pv_after_played: Optional[List[str]],
    pv_after_best: Optional[List[str]],
    move_history_san: Optional[List[str]],
    full_move_number: Optional[int],
    mover_is_user: bool,
) -> Optional[Dict[str, Any]]:
    """Construct the `move` dict required by
    llm_caption_generator.generate_caption_for_move().

    Re-runs extract_facts to populate the caption_facts fields that
    the LLM polish prompt needs. Returns None if extraction fails
    (the polish task will then silently abandon).
    """
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
    except Exception:
        return None

    return {
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
        "caption": "",
        "principle_cue": "",
        "principle_id_used": None,
        "rule_name": None,
    }


def _polish_guards_pass(
    *,
    draft: str,
    polished: str,
    v5_block: Dict[str, Any],
) -> Tuple[bool, str]:
    """Apply the four Phase 1.4 guards (Mohit signoff 2026-05-18):

      1. same principle/target — every protected entity from the draft
         must still appear in the polished string.
      2. no contradiction — polished doesn't drop the anchor_name AND
         doesn't introduce explicit "not" / "isn't" / "doesn't" negation
         of the lesson.
      3. length cap — polished length ≤ 1.4× draft length.
      4. deadline — enforced at the caller via asyncio.wait_for(timeout=3.0).

    Returns (passed, reason). When passed=False, reason names which guard
    rejected (logged for debugging).
    """
    if not polished or not polished.strip():
        return False, "empty polish output"

    # Guard 1: protected entities (SAN moves, squares, piece words,
    # named patterns, principle anchor_name)
    protected = v5_block.get("protected_entities") or []
    missing = [e for e in protected if e and e not in polished]
    if missing:
        return False, f"missing protected entity {missing[0]!r}"

    # Guard 1b: anchor_name must survive (it's the click-target for
    # the future clickable-rule UI)
    anchor_name = v5_block.get("anchor_name") or ""
    if anchor_name and anchor_name not in polished:
        return False, f"anchor_name {anchor_name!r} dropped"

    # Guard 2: contradiction — explicit negation of the named pattern
    # No-pattern-name = drop already caught by Guard 1b. Here we catch
    # the wider case of "not a pin" / "isn't a fork" introducing a
    # contradicting claim. Heuristic; conservative on false positives.
    lower = polished.lower()
    contradictions = (
        "not a pin", "not a fork", "not a skewer", "not hanging",
        "isn't a pin", "isn't a fork", "isn't a skewer",
        "doesn't catch", "doesn't pin", "doesn't fork", "doesn't skewer",
    )
    if any(c in lower for c in contradictions):
        return False, "contains contradiction phrase"

    # Guard 3: length cap (1.4× draft length, by character)
    if len(polished) > int(len(draft) * 1.4):
        return False, f"polish too long ({len(polished)} > 1.4*{len(draft)})"

    return True, "ok"


async def polish_v5_block_async(
    *,
    db,
    message_id: Any,  # MongoDB _id of the coach_messages document
    v5_block: Dict[str, Any],
    fen_before: str,
    played_san: str,
    best_move_san: Optional[str],
    eval_before_cp: Optional[int],
    eval_after_cp: Optional[int],
    cp_loss: int,
    pv_after_played: Optional[List[str]],
    pv_after_best: Optional[List[str]],
    move_history_san: Optional[List[str]],
    full_move_number: Optional[int],
    mover_is_user: bool,
    timeout_seconds: float = 3.0,
) -> None:
    """Phase 1.4 — run LLM polish on the v5_block, with the four guards.

    Designed to be scheduled via `asyncio.create_task(...)` AFTER the
    move response has been sent. Updates the coach_messages document
    when guards pass. Stays at polish_status='draft' on any failure
    (rate limit, timeout, contradiction, length, missing entities).

    Never raises — logs only. The move response has already been sent
    by the time this runs; an exception here can't degrade UX.
    """
    import asyncio
    try:
        from services.llm_caption_generator import generate_caption_for_move

        move_record = build_polish_move_record(
            v5_block=v5_block,
            fen_before=fen_before,
            played_san=played_san,
            best_move_san=best_move_san,
            eval_before_cp=eval_before_cp,
            eval_after_cp=eval_after_cp,
            cp_loss=cp_loss,
            pv_after_played=pv_after_played,
            pv_after_best=pv_after_best,
            move_history_san=move_history_san,
            full_move_number=full_move_number,
            mover_is_user=mover_is_user,
        )
        if move_record is None:
            logger.info(f"[live_v5.polish] could not build move_record; staying at draft")
            return

        try:
            polished = await asyncio.wait_for(
                generate_caption_for_move(move_record),
                timeout=timeout_seconds,
            )
        except asyncio.TimeoutError:
            logger.info(f"[live_v5.polish] timeout after {timeout_seconds}s; staying at draft")
            return
        except Exception:
            logger.exception(f"[live_v5.polish] LLM call failed; staying at draft")
            return

        draft = v5_block.get("deterministic_draft") or ""
        passed, reason = _polish_guards_pass(
            draft=draft, polished=polished, v5_block=v5_block,
        )
        if not passed:
            logger.info(f"[live_v5.polish] guard rejected: {reason}; staying at draft")
            return

        # All guards passed — hot-swap.
        await db.coach_messages.update_one(
            {"_id": message_id},
            {"$set": {
                "message": polished,
                "anchor_detail": polished,
                "polish_status": "polished",
            }},
        )
        logger.info(f"[live_v5.polish] swapped to polished caption for message {message_id}")
    except Exception:
        logger.exception(f"[live_v5.polish] unexpected error; staying at draft")


# ─────────────────────────────────────────────────────────────────
# Phase 1.3 — adaptive coach-move teaching (Mohit signoff 2026-05-18)
#
# When the coach plays, occasionally surface a brief named-pattern
# observation ("Coach plays Bg5 — Pin. Watches your knight against
# your queen."). Frequency target: ~20% of coach moves on average,
# higher on clear plans / tactical setups, lower on quiet moves.
# Hard cooldown: max 2 coach captions per 6 coach moves.
# ─────────────────────────────────────────────────────────────────

# Subset of principle IDs that fire MEANINGFULLY on a coach's move
# (i.e., the principle is about a positive pattern the coach JUST
# CREATED, not a mistake the player JUST MADE). The cp_loss gates
# in caption_facts will suppress most "missed chance" principles
# when cp_loss is 0 — but TIER 3 shape patterns ALWAYS fire when
# the geometry is present.
_COACH_TEACHING_SHAPE_PATTERNS = True   # always allow shape patterns
_COACH_TEACHING_PRINCIPLES: Set[str] = {
    # Principles that fire when the played move CREATES a positive
    # pattern — useful as coach-move teaching ("Coach plays Bg5 — Pin").
    # 2026-05-18 self-audit follow-up: populated with the principles
    # whose detectors fire on engine-best (player creates the pattern)
    # not "missed chance" (which doesn't apply when coach IS the engine).
    "TAC_PIN_PATTERN",         # coach creates pin/skewer alignment
    "TAC_DISCOVERED_PATTERN",  # coach uncovers a piece's attack via the move
}


@dataclass
class CoachMoveTeachingDecision:
    """Result of evaluating whether to surface coach-move teaching."""
    should_surface: bool
    reason: str
    v5_block: Optional[Dict[str, Any]] = None
    teaching_weight: float = 0.0


def _coach_move_teaching_weight(
    *,
    has_shape_pattern: bool,
    has_principle: bool,
    is_forced_recapture: bool,
    cp_loss: int,
) -> float:
    """Compute the adaptive surfacing weight for a coach move per
    Mohit's Phase 1.3 spec.

    Higher = more likely to surface. Surfacing decision applies
    `weight * random_uniform > 0.7`.

    Base: 0.4 (most coach moves are below threshold and stay silent).
    Modifiers:
      +0.4 — shape pattern detected (clear tactical pattern)
      +0.2 — principle from the coach-teaching subset
      -0.5 — forced recapture (routine, no teaching value)
      +0.2 — coach move was a significant improvement (cp_loss=0
             when prev position had a different best — proxy for
             strategic transformation)
    """
    weight = 0.4
    if has_shape_pattern:
        weight += 0.4
    if has_principle:
        weight += 0.2
    if is_forced_recapture:
        weight -= 0.5
    # cp_loss for coach moves is typically 0 (coach plays best).
    # If we had a cp_loss > 0 it'd indicate coach made a sub-optimal
    # move — definitely don't surface those.
    if cp_loss > 50:
        weight -= 0.3
    return max(0.0, min(1.0, weight))


def _coach_in_cooldown(
    coach_v5_surfaced_indices: List[int],
    coach_moves_made: int,
) -> bool:
    """Per Mohit's spec: max 2 coach V5 captions per 6 coach moves.

    Ramp-in: no cap for the first 6 coach moves of the session.
    """
    if coach_moves_made < 6:
        return False
    window_start = coach_moves_made - 6
    recent = [i for i in coach_v5_surfaced_indices if i > window_start]
    return len(recent) >= 2


def _build_coach_perspective_caption(
    *,
    anchor_name: str,
    coach_move_san: str,
    shape_pattern_desc: Optional[str] = None,
) -> str:
    """Intention-framed brief observation per Mohit's spec.

    NOT engine narration. Just a named-pattern observation.

    Examples:
      "Coach plays Bg5 — Pin."
      "Coach plays Ne5 — Pawn Fork. The knight attacks two pawns."
    """
    base = f"Coach plays {coach_move_san} — {anchor_name}."
    if shape_pattern_desc:
        return f"{base} {shape_pattern_desc.rstrip('.').rstrip()}."
    return base


def evaluate_coach_move_teaching(
    *,
    fen_before_coach_move: str,
    coach_move_san: str,
    pv_after_coach: Optional[List[str]] = None,
    move_history_san: Optional[List[str]] = None,
    full_move_number: Optional[int] = None,
    user_doc: Dict[str, Any],
    session_doc: Dict[str, Any],
    coach_moves_made: int,
    coach_v5_surfaced_indices: List[int],
    rng_value: Optional[float] = None,
) -> CoachMoveTeachingDecision:
    """Decide whether to surface a V5 teaching block for the coach's
    move, per Phase 1.3 spec.

    Logic:
      1. Feature flag check (same flag as user-move V5).
      2. Run extract_facts with mover_is_user=False, cp_loss=0.
      3. Check for shape pattern OR coach-teaching-subset principle hit.
      4. Compute adaptive weight.
      5. Cooldown check (2 per 6 coach moves).
      6. Stochastic surface decision: weight * random > 0.7.

    rng_value: pass a deterministic value 0-1 for testing; otherwise
    a fresh random.random() is used.
    """
    import random

    if not _is_user_flag_enabled(user_doc, session_doc):
        return CoachMoveTeachingDecision(should_surface=False, reason="feature flag off")

    # Cooldown gate FIRST — no point detecting if we can't surface.
    if _coach_in_cooldown(coach_v5_surfaced_indices, coach_moves_made):
        return CoachMoveTeachingDecision(
            should_surface=False,
            reason=f"cooldown (2/6 cap; {coach_moves_made} moves, "
                   f"{len(coach_v5_surfaced_indices)} surfaced)",
        )

    # Run V5 detection on the coach's move.
    try:
        facts = extract_facts(
            fen_before=fen_before_coach_move,
            played_san=coach_move_san,
            best_move_san=coach_move_san,  # assume coach played best
            eval_before_cp=0,
            eval_after_cp=0,
            cp_loss=0,
            pv_after_played=pv_after_coach or [],
            pv_after_best=pv_after_coach or [],
            move_history_san=move_history_san or [],
            full_move_number=full_move_number,
            mover_is_user=False,
        )
    except Exception:
        return CoachMoveTeachingDecision(should_surface=False, reason="extract_facts failed")

    has_shape = bool(facts.get("shape_pattern_id"))
    eligible_principles = [
        ev for ev in (facts.get("principles_violated") or [])
        if ev.get("principle_id") in _COACH_TEACHING_PRINCIPLES
    ]
    has_principle = bool(eligible_principles)
    if not has_shape and not has_principle:
        return CoachMoveTeachingDecision(
            should_surface=False, reason="no shape or coach-teaching principle"
        )

    is_forced_recapture = bool(facts.get("forced_recapture"))
    weight = _coach_move_teaching_weight(
        has_shape_pattern=has_shape,
        has_principle=has_principle,
        is_forced_recapture=is_forced_recapture,
        cp_loss=0,
    )
    if rng_value is None:
        rng_value = random.random()
    if weight * rng_value <= 0.7:
        return CoachMoveTeachingDecision(
            should_surface=False,
            reason=f"weight*rng below threshold (w={weight:.2f} r={rng_value:.2f})",
            teaching_weight=weight,
        )

    # Build the v5_block. For shape patterns, use shape_pattern_name +
    # shape_pattern_desc; for principles, use the resolver.
    anchor_name: Optional[str] = None
    anchor_detail: Optional[str] = None
    principle_id: Optional[str] = None
    shape_pattern_id: Optional[str] = None
    deterministic_draft: Optional[str] = None

    if has_shape:
        anchor_name = facts.get("shape_pattern_name") or "Pattern"
        shape_pattern_id = facts.get("shape_pattern_id")
        shape_desc = facts.get("shape_pattern_desc")
        deterministic_draft = _build_coach_perspective_caption(
            anchor_name=anchor_name,
            coach_move_san=coach_move_san,
            shape_pattern_desc=shape_desc,
        )
        anchor_detail = shape_desc or anchor_name
    elif has_principle:
        ev = eligible_principles[0]
        principle_id = ev.get("principle_id")
        entry = _CAPTION_PRINCIPLES_BY_ID.get(principle_id or "", {})
        anchor_name = entry.get("name") or principle_id
        deterministic_draft = _build_coach_perspective_caption(
            anchor_name=anchor_name,
            coach_move_san=coach_move_san,
        )
        anchor_detail = anchor_name

    v5_block = {
        "anchor_name":          anchor_name,
        "anchor_detail":        anchor_detail,
        "deterministic_draft":  deterministic_draft,
        "principle_id":         principle_id,
        "shape_pattern_id":     shape_pattern_id,
        "polish_status":        "draft",
        "is_coach_move_teaching": True,
        "protected_entities":   [coach_move_san, anchor_name] if anchor_name else [coach_move_san],
        "state_key":            None,  # coach-move V5 doesn't use state-key suppression today
        "principle_suppress_policy": None,
    }
    return CoachMoveTeachingDecision(
        should_surface=True,
        reason=f"surface (w={weight:.2f} r={rng_value:.2f})",
        v5_block=v5_block,
        teaching_weight=weight,
    )


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
