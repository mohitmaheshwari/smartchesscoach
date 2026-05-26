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
from services.coaching_encounter_weights import passes_necessity_gate
from services.severity import classify_severity_practical


# ─────────────────────────────────────────────────────────────────
# Beginner-vocab glossary — first-encounter definitions for sub-1400
# players. Locked 2026-05-19: assumed chess literacy ("pin", "skewer",
# "defender") was a gap for 800-1000 players. On the FIRST time a user
# sees one of these principles, prepend a short one-sentence
# definition. After acknowledgment (any subsequent encounter), drop it.
# Each definition passes [[1200-test]]: concrete, no jargon.
# ─────────────────────────────────────────────────────────────────
BEGINNER_GLOSSARY: Dict[str, str] = {
    "TAC_PIN_PATTERN": "A pin happens when a piece can't move because something more valuable is behind it on the same line.",
    "TAC_FORK_PATTERN": "A fork is when one piece attacks two enemy pieces at once — one of them is going to fall.",
    "TAC_SKEWER_PATTERN": "A skewer is the opposite of a pin — the more valuable piece is in front and is forced to move, so what's behind falls.",
    "TAC_DISCOVERED_PATTERN": "A discovered attack — when one piece moves out of the way, the piece behind it suddenly attacks something.",
    "TAC_HANGING_PIECE": "A piece is 'hanging' when nothing defends it. Always count attackers vs defenders before each move.",
    "TAC_DEFENDER_COUNT": "Defenders are pieces that protect a square or piece. If attackers outnumber defenders, the target falls.",
    "END_RULE_OF_SQUARE": "Rule of the Square — to catch a passed pawn, draw an imaginary box from the pawn to its promotion square. If your king can step into the box, you catch it.",
    "END_OPPOSITION": "Opposition — when kings face each other one square apart with no piece between them. The side NOT to move usually wins the key squares.",
    "END_ROOK_BEHIND_PASSER": "Rook behind the passer — keep your rook behind a passed pawn (yours or theirs). Your pawn pushes safely; theirs is held back.",
}

# Only show glossary for users at this rating or below. Above, assume
# they know the terms.
GLOSSARY_RATING_CAP = 1400


def _glossary_for_principle(
    principle_id: Optional[str], user_rating: Optional[int]
) -> Optional[str]:
    """Return the glossary definition for this principle, or None if
    (a) no glossary entry exists, (b) user is above rating cap, or
    (c) principle_id is None."""
    if not principle_id:
        return None
    if user_rating is not None and user_rating > GLOSSARY_RATING_CAP:
        return None
    return BEGINNER_GLOSSARY.get(principle_id)

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
    severity: str  # good / inaccuracy / mistake / serious / blunder (canonical practical_tier; v100 step 9)
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


def build_move_feedback_tag(
    *,
    played_san: str,
    best_move_san: Optional[str],
    cp_loss: int,
    user_rating: Optional[int] = None,
    eval_before_cp: Optional[int] = None,
    eval_after_cp: Optional[int] = None,
    mover_is_user: bool = True,
    mover_is_white: bool = True,
) -> MoveFeedbackTag:
    """Build the structured tag from the data realtime already has.

    v100 step 9 (Mohit signoff 2026-05-26, option c — V5-gate scope only):
    severity classification is now delegated to the canonical
    `classify_severity_practical` (services/severity.py). The V5
    suppression gate (`should_suppress_v5_for_tag`) uses the practical
    tier — so "stayed winning + small Δwin_prob" silences V5 the same
    way the old beginner_high band's `inaccuracy=75cp` threshold used to.

    The previous rating-band classifier here had two problems the
    practical tier fixes:
      - It ignored position context (cp_loss=120 in a winning position
        means much less than cp_loss=120 in a balanced position).
      - It diverged from the canonical thresholds used by review.

    user_rating is retained for future use but is no longer consulted
    here. The realtime tone classifier
    (`realtime_coaching_feedback._classify_move_quality`) still uses
    rating-bands — that's the documented ★ KEY DIFFERENTIATOR and
    out-of-scope for this step.

    When eval data is missing (eval_before_cp / eval_after_cp = None),
    `classify_severity_practical` falls back to neutral (state=balanced,
    stayed_winning=False) and the practical tier equals the canonical
    cp_loss-based tier — same suppression behaviour as the old path on
    obvious goods (cp_loss<30) and on hard mistakes (cp_loss≥100).

    Phase 1.2 MVP: severity + parsed squares. Optional fields
    (principle_id, pattern_id, tactic_type) stay None until the
    realtime path is refactored to compute them.
    """
    practical = classify_severity_practical(
        int(cp_loss or 0),
        mover_is_user=bool(mover_is_user),
        mover_is_white=bool(mover_is_white),
        eval_before_cp=eval_before_cp,
        eval_after_cp=eval_after_cp,
    )
    severity = practical.practical_tier
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
    encounter_weights: Optional[Dict[str, float]] = None,
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

    # v100 A1 (Mohit signoff 2026-05-26 — auto-propagation): run the
    # user-blunder detector suite that V5 review uses, so PWC users
    # get the same v53-v65 detector evidence in captions ("Play d5
    # kicking their bishop on e6") instead of generic teaching.
    # Internal gate (is_user AND best_move differs AND cp_loss >= 100)
    # is preserved inside the helper — for non-qualifying moves this
    # is a near-no-op.
    try:
        from services.caption_pipeline import inject_user_blunder_detector_facts
        inject_user_blunder_detector_facts(
            facts,
            fen_before=fen_before,
            move_san=played_san,
            best_move=best_move_san,
            pv_after_best=pv_after_best or [],
            move_number=full_move_number,
            is_user=bool(mover_is_user),
            cp_loss=int(cp_loss or 0),
        )
    except Exception:
        logger.exception(
            f"[live_v5_teaching] blunder detector inject crashed for {played_san}"
        )

    # v100 A2 (auto-propagation): em-dash voice-match + trap-context
    # wiring. PWC doesn't currently scan the live session's move
    # history for traps (game_trap_fires=None) — the trap-context
    # branch silently skips, but the em-dash voice still fires
    # whenever an A1-suite detector populated caption_facts. PWC
    # users on a blunder now get the em-dash parent variant
    # ("Y was better — reason") instead of the two-sentence form,
    # matching V5 review output.
    try:
        from services.caption_pipeline import inject_em_dash_and_trap_context_facts
        inject_em_dash_and_trap_context_facts(
            facts,
            game_trap_fires=None,
            best_move=best_move_san,
            move_san=played_san,
            is_user=bool(mover_is_user),
            cp_loss=int(cp_loss or 0),
            opening_name=None,
        )
    except Exception:
        logger.exception(
            f"[live_v5_teaching] em-dash inject crashed for {played_san}"
        )

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

    # Necessity gate (Phase 1.6/1.7 — coaching_encounter_weights).
    # Even if a principle survives session-level suppression, we may
    # have taught it to this user recently enough that re-teaching is
    # noise. The decay model (~20%/day) lets concepts re-arm naturally.
    # Higher-rated players have lower thresholds: an 1800+ doesn't need
    # to be told "develop your knights first" twice in one week.
    # See [[play-with-coach-phase1-design]] §4 and §5.
    if encounter_weights:
        user_rating = user_doc.get("rating") if user_doc else None
        necessity_filtered: List[Dict[str, Any]] = []
        for ev in surviving:
            pid = ev.get("principle_id")
            if passes_necessity_gate(pid, encounter_weights, user_rating):
                necessity_filtered.append(ev)
            else:
                logger.info(
                    f"[live_v5_teaching] necessity gate suppressed "
                    f"principle={pid} (decay_score={encounter_weights.get(pid, 0):.2f}, "
                    f"rating={user_rating})"
                )
        facts["principles_violated"] = necessity_filtered

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
        # Carry forward the principle the live decision already picked.
        # Without this, generate_caption_for_move's internal resolve_priority
        # call falls through to principles[0] (source-order), which can
        # pick a different lower-priority principle. Polished output then
        # mentions the wrong anchor and guards reject every time.
        # Self-audit 2026-05-18 caught this — the rejection was correct
        # but wasted an LLM call per move.
        "principle_id_used": v5_block.get("principle_id"),
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

    # Guard 1: protected entities the DRAFT actually mentions must
    # survive in the polish. Filtering to draft-mentioned entities is
    # the right semantic — the LLM can only preserve what was in the
    # draft, not invent SAN moves the resolver listed for safety.
    # Self-audit 2026-05-18 caught this: protected_entities includes
    # the played + best SAN (Nc4, Ke3) but Walloo21's draft mentions
    # neither. Guard was rejecting EVERY polish for that reason.
    protected = v5_block.get("protected_entities") or []
    draft_protected = [e for e in protected if e and e in draft]
    missing = [e for e in draft_protected if e not in polished]
    if missing:
        return False, f"missing protected entity {missing[0]!r}"

    # Guard 1b: anchor_name must survive (it's the click-target for
    # the future clickable-rule UI). Only enforced if anchor_name
    # was in the draft.
    anchor_name = v5_block.get("anchor_name") or ""
    if anchor_name and anchor_name in draft and anchor_name not in polished:
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
    # whose detectors fire on engine-best (coach plays the best move
    # AND that move creates a pattern). Excluded: principles whose
    # detectors fire on the mover hanging their own piece / missing
    # a chance — those don't apply when coach IS the engine.
    "TAC_PIN_PATTERN",          # coach creates pin/skewer alignment
    "TAC_DISCOVERED_PATTERN",   # coach uncovers a piece's attack via the move
    "TAC_FORK_PATTERN",         # coach forks via multi-target attack
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
    encounter_weights: Optional[Dict[str, float]] = None,
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
    # Necessity gate for coach-move teaching too — same threshold model
    # as user-move path. Coach shouldn't teach forks 5x to a 1700 either.
    if encounter_weights:
        user_rating = user_doc.get("rating") if user_doc else None
        eligible_principles = [
            ev for ev in eligible_principles
            if passes_necessity_gate(ev.get("principle_id"), encounter_weights, user_rating)
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
