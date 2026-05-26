"""
caption_pipeline — single source of truth for the per-move caption brain.

Built per Mohit + reviewer agreement 2026-05-25 + 2026-05-26:
  - "build a central layer that gets shared by both pwc and review"
  - "extract a single build_move_teaching_decision(...) pipeline that
     returns caption + suppression mutations + trap state mutations +
     principle firing + visual annotations + coaching metadata"
  - "shared logic is good. Shared performance profile is not
     automatically good." Benchmark before extraction confirmed full
     V5 brain runs 3.5ms p50 / 6.4ms p99 per move — well within PWC's
     400-700ms budget. No fast/full mode flag required.

CONTRACT (Mohit-locked semantic-product split, not procedural):

  MoveInputs (immutable, pure-function inputs the function receives)
  CrossMoveState (mutable state threaded across moves in a session/game)
  MoveTeachingDecision (the complete teaching product for ONE move)

  build_move_teaching_decision(inputs, state) → (decision, new_state)

Both callers — game_decryption_v5_service (batch game review) AND
live_v5_teaching (live PWC coaching) — become thin shims around this
function. Any future detector, cue rewrite, severity tweak, or
softening change goes in ONE place and reaches both surfaces.

EXTRACTION CONTRACT (behavior preservation):
  - Snapshot 'baseline_v99' captured pre-extraction (scripts/snapshot_captions.py)
  - Regen-diff post-extraction MUST be byte-identical for:
      caption, rule_name, severity, severity_practical, severity_canonical,
      principle_id_used, shape_pattern_id, caption_tier,
      caption_arrows, caption_highlight_squares, shape_pattern_targets
  - silent_count must be identical (silence is sacred per Mohit 2026-05-25)
  - pytest at the boundary (~20 canonical positions from v83-v99 fixes)
    guards against future regression

MIGRATION STATUS (2026-05-26):
  [in progress] Step 1: dataclasses + skeleton (this file)
  [pending] Step 2: extract severity-classification block, verify zero diff
  [pending] Step 3: extract caption_facts wiring (lost_defender_lead, etc.)
  [pending] Step 4: extract opp punishment / positional detection
  [pending] Step 5: extract simulate_* detectors
  [pending] Step 6: extract trap recognition
  [pending] Step 7: extract shape pattern selection
  [pending] Step 8: extract board state describer
  [pending] Step 9: extract render + promotion ladder dispatch
  [pending] Step 10: wire PWC to use this module
  [pending] Step 11: retire shared_coaching_v5.MoveSeverity +
                     realtime_coaching_feedback._classify_move_quality
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

import chess

from services.severity import (
    classify_severity,
    classify_severity_practical,
    PracticalSeverity,
)

logger = logging.getLogger(__name__)


# ────────────────────────────────────────────────────────────────────
# CONTRACT DATACLASSES
# ────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class MoveInputs:
    """Everything a single move needs to be captioned. Pure inputs —
    no implicit caller state, no globals.

    Field naming mirrors what V5 service and live_v5_teaching pass
    today, so adoption is mechanical.
    """
    # ─── Position ────────────────────────────────────────────────
    fen_before: str
    played_san: str
    mover_is_user: bool
    mover_is_white: bool
    user_color: str  # "white" / "black" — what THIS user plays in this game/session
    full_move_number: int
    move_history_san: List[str]
    prev_move_san: Optional[str] = None  # last opponent move (for opening context)

    # ─── Engine truth ────────────────────────────────────────────
    best_move_san: Optional[str] = None
    eval_before_cp: Optional[int] = None
    eval_after_cp: Optional[int] = None
    cp_loss: int = 0
    pv_after_played: List[str] = field(default_factory=list)
    pv_after_best: List[str] = field(default_factory=list)

    # ─── Opp-side context (batch review fills these; PWC may leave
    # them None when looking-ahead isn't available yet) ──────────
    opp_eval_before: Optional[int] = None
    opp_eval_after: Optional[int] = None
    opp_cp_loss: Optional[int] = None
    user_best_reply_san: Optional[str] = None
    user_best_reply_san_is_forcing: bool = False

    # ─── Game metadata (for opening intro / curriculum walker) ───
    eco_code: Optional[str] = None
    opening_name: Optional[str] = None
    user_rating: Optional[int] = None

    # ─── Pre-extracted optional engine candidates (V5 service fetches
    # these; PWC can skip) ───────────────────────────────────────
    engine_candidates: Optional[List[Dict[str, Any]]] = None

    # ─── State-threading needed by select_shape_pattern_record for
    # zero-diff parity with V5 inline. V5 calls A6 with prev_move
    # (chess.Move) + eval_data["best_move_uci"]; the central layer
    # uses these for context-aware shape detection + engine verifier.
    # PWC leaves as None.
    prev_move_uci: Optional[str] = None
    best_move_uci: Optional[str] = None


@dataclass
class CrossMoveState:
    """Mutable state threaded across moves in a session OR game.

    Batch-review callers (V5 service) build a fresh state per game and
    discard at end. Live callers (PWC) persist this to coach_sessions
    Mongo doc and reload it on each move.

    Field names align with current persistence:
      - v5_fired_principles  ↔ coach_sessions.v5_fired_principles
      - v5_fired_state_keys  ↔ coach_sessions.v5_fired_state_keys
      - v5_trap_state        ↔ coach_sessions.v5_trap_state  (NEW)
      - v5_prev_user_eval_after ↔ coach_sessions.v5_prev_user_eval_after  (NEW)
    """
    fired_principles: Set[str] = field(default_factory=set)
    fired_state_keys: Set[Tuple] = field(default_factory=set)
    # Trap recognition state (V5 service tracks this game-wide; PWC
    # GAINS this when we wire the shared pipeline).
    active_trap: Optional[Dict[str, Any]] = None
    active_trap_step_cursor: int = 0
    active_trap_setup_completed_by_user: bool = False
    # Previous user eval_after — needed for opp cp_loss computation
    # on the NEXT opp move. Game-wide for batch; session-wide for PWC.
    prev_user_eval_after: Optional[int] = None


@dataclass
class StateMutations:
    """What changed in CrossMoveState during this move. Callers apply
    these atomically (PWC) or thread into next iteration (V5 service).

    Returning mutations explicitly (vs. mutating state in place) lets
    callers decide WHEN to persist: PWC writes only at end-of-success
    so an exception mid-move doesn't corrupt session state.
    """
    fired_principles_added: Set[str] = field(default_factory=set)
    fired_state_keys_added: Set[Tuple] = field(default_factory=set)
    active_trap_after: Optional[Dict[str, Any]] = None  # None = no change OR cleared
    active_trap_cleared: bool = False  # explicit clear signal
    active_trap_step_cursor_after: int = 0
    active_trap_setup_completed_by_user_after: bool = False
    prev_user_eval_after: Optional[int] = None


@dataclass
class TextSurface:
    """The user-visible caption text."""
    caption: str = ""
    rule_name: str = "R_FALLBACK"


@dataclass
class VisualSurface:
    """User-visible visual annotations."""
    arrows: List[Dict[str, str]] = field(default_factory=list)
    highlight_squares: List[str] = field(default_factory=list)


@dataclass
class TeachingMeta:
    """Categorical metadata about WHAT was taught and HOW severe."""
    severity: str = "context"  # user-facing tier ("good"/"mistake"/"opp_mistake"/...)
    severity_canonical: str = "good"
    severity_practical: str = "good"
    caption_tier: str = "NONE"  # HIGH / MID / LOW / NONE per caption_classifier
    has_teaching_content: bool = False
    principle_id_used: Optional[str] = None
    principle_cue: str = ""
    shape_pattern_id: Optional[str] = None
    shape_pattern_name: Optional[str] = None
    shape_pattern_desc: Optional[str] = None
    shape_pattern_targets: List[str] = field(default_factory=list)
    shape_pattern_mover: Optional[str] = None
    shape_pattern_executing_move: Optional[str] = None
    # Decisiveness / win-prob fields surface on the move record for
    # downstream consumers (admin/captions UI, future home-intelligence).
    mover_winprob_before: float = 0.5
    mover_winprob_after: float = 0.5
    mover_winprob_delta: float = 0.0
    mover_state_before: str = "balanced"
    mover_state_after: str = "balanced"
    stayed_winning: bool = False
    decisiveness_changed: bool = False


@dataclass
class MoveTeachingDecision:
    """The complete teaching product for one move.

    Caller responsibilities:
      - Persist `text` + `visual` to the move record / coach_messages
      - Apply `state_mutations` to CrossMoveState (atomically for PWC)
      - Use `teaching_meta` for downstream consumers (UI, audit, classifier)
      - Pass `debug_facts` to admin UI / authoring tools (do NOT use for
        rendering — it's the post-extract facts dict for inspection only)
    """
    text: TextSurface = field(default_factory=TextSurface)
    visual: VisualSurface = field(default_factory=VisualSurface)
    teaching_meta: TeachingMeta = field(default_factory=TeachingMeta)
    state_mutations: StateMutations = field(default_factory=StateMutations)
    # The full caption_facts dict — for debug / audit / authoring UI
    # only. Renderers SHOULD NOT read this; they consume the typed
    # fields above. (Per reviewer's "no downstream renderer consumes
    # cosmetic shifts" rule.)
    debug_facts: Dict[str, Any] = field(default_factory=dict)
    # Trap record from A5's update_trap_recognition_state. None when
    # no setup completed and no continuation step matched. Caller
    # writes this to move record for downstream consumers (R_PROMOTED_
    # trap_setup, frontend "Play this line" UI).
    trap_record: Optional[Dict[str, Any]] = None
    # Shape pattern record from A6's select_shape_pattern_record.
    # None when neither pre-move nor post-move shape detection fired.
    # Caller writes pattern_id / pattern_name / pattern_desc / mover /
    # targets / executing_move to move record.
    shape_pattern_record: Optional[Dict[str, Any]] = None
    # Whether the caller should suppress the entire teaching surface
    # (e.g. forced recapture, book move, suppressed by session-level
    # gates). Caller decides what to do — usually skip writing to UI.
    should_skip: bool = False
    skip_reason: str = ""


# ────────────────────────────────────────────────────────────────────
# EXTRACTED PIPELINE HELPERS
# ────────────────────────────────────────────────────────────────────
#
# Each helper is a self-contained extraction of a block that used to
# live inline in game_decryption_v5_service.py per-move loop. V5
# service calls them as it migrates; PWC's live_v5_teaching will call
# them too once the migration completes.
#
# CONTRACT: each helper MUST be a pure function (same inputs → same
# outputs, no globals, no side effects). The snapshot diff against
# baseline_v99.json proves zero behavioural drift on extraction.


@dataclass(frozen=True)
class SeverityComputation:
    """Output of compute_severity_for_move(). Bundles canonical +
    practical classification + forced-recapture detection so V5
    service / PWC can consume them with one call instead of the
    ~80 lines of inline orchestration that used to live in V5 service.

    NOTE: book-move downgrade and best-equals-played sanity downgrade
    are NOT yet inside this helper — V5 service still applies them
    inline. They'll move in a follow-up extraction once we're confident
    they're safe to share with PWC (PWC currently has no notion of
    book moves; folding it in is an additive capability gain there).
    """
    severity_user_facing: str        # "good" / "inaccuracy" / "opp_mistake" / ...
    severity_canonical: str          # raw cp_loss-based tier
    practical: PracticalSeverity
    is_forced_recapture: bool


def compute_severity_for_move(
    *,
    cp_loss: int,
    opp_cp_loss: int,
    is_user: bool,
    is_white: bool,
    user_color: str,
    # For canonical mate-sentinel escape hatch (always user POV, signed)
    mate_sentinel_eval_cp: Optional[int],
    # For practical severity. classify_severity_practical sign-flips
    # internally based on mover_is_white, so these MUST be white-POV
    # (the raw eval_data values). For user moves V5 service reads
    # eval_data["eval_before"] / ["eval_after"] (white POV); for opp
    # moves V5 tracks them separately as opp_eval_before/after.
    user_eval_before_white_pov: Optional[int],
    user_eval_after_white_pov: Optional[int],
    opp_eval_before: Optional[int],
    opp_eval_after: Optional[int],
    board_before: chess.Board,
    played_move: Optional[chess.Move],
    prev_move: Optional[chess.Move],
) -> SeverityComputation:
    """Replicates game_decryption_v5_service.py lines 2988-3082 (severity
    classification + practical-severity + forced-recapture detection),
    EXCLUDING the book-move and best-equals-played sanity downgrades
    which stay in V5 service for this extraction.

    Args (all explicit — no implicit caller state):
      cp_loss / opp_cp_loss        : centipawn loss for user / opp move
      is_user                      : True if user played this move
      is_white                     : True if the mover is white
      user_color                   : "white" / "black" — the user's colour
      mate_sentinel_eval_cp        : engine eval AFTER move, USER POV
                                     (signed). Used only for canonical
                                     classifier's mate-walked-into
                                     escape hatch.
      user_eval_before_white_pov   : white-POV engine eval BEFORE this
                                     move (used for practical-severity
                                     when is_user=True).
      user_eval_after_white_pov    : white-POV engine eval AFTER this
                                     move (used for practical-severity
                                     when is_user=True).
      opp_eval_before/after        : engine eval before/after from WHITE
                                     POV (for practical severity on opp
                                     moves — V5 service tracks separately).
      board_before                 : the python-chess Board before move
      played_move                  : chess.Move object of this move
      prev_move                    : chess.Move object of previous move
                                     (for forced-recapture detection)

    Returns SeverityComputation. Caller still applies book-move /
    best-equals-played downgrades and updates the move record.
    """
    # ─── Canonical severity (v92 — single source) ──────────────────
    _sev_classification = classify_severity(
        cp_loss if is_user else opp_cp_loss,
        mover_is_user=bool(is_user),
        user_post_eval_cp=mate_sentinel_eval_cp,
    )
    severity = _sev_classification.user_facing_tier
    severity_canonical = _sev_classification.tier

    # ─── Practical severity (v96/v98) ──────────────────────────────
    # classify_severity_practical does its own sign-flip based on
    # mover_is_white — so the evals we pass MUST be white-POV.
    if is_user:
        practical_eval_before = user_eval_before_white_pov
        practical_eval_after = user_eval_after_white_pov
    else:
        practical_eval_before = opp_eval_before
        practical_eval_after = opp_eval_after
    practical = classify_severity_practical(
        cp_loss if is_user else opp_cp_loss,
        mover_is_user=bool(is_user),
        mover_is_white=bool(is_white),
        eval_before_cp=practical_eval_before,
        eval_after_cp=practical_eval_after,
    )

    # ─── Forced recapture (V5 service lines 3076-3082) ─────────────
    # When user recaptures on a square where opp just captured AND
    # only one legal capture exists, the move was forced — caption
    # surfaces as R07_forced_recapture; severity is downgraded to
    # "good" so we don't tag it as a mistake.
    is_forced_recapture = False
    if is_user and played_move is not None and prev_move is not None:
        if (board_before.is_capture(played_move)
                and played_move.to_square == prev_move.to_square):
            captures_on_sq = [
                m for m in board_before.legal_moves
                if m.to_square == played_move.to_square
                and board_before.is_capture(m)
            ]
            if len(captures_on_sq) <= 1:
                is_forced_recapture = True
                severity = "good"

    return SeverityComputation(
        severity_user_facing=severity,
        severity_canonical=severity_canonical,
        practical=practical,
        is_forced_recapture=is_forced_recapture,
    )


def inject_user_blunder_detector_facts(
    caption_facts: Dict[str, Any],
    *,
    fen_before: str,
    move_san: str,
    best_move: Optional[str],
    pv_after_best: Optional[List[str]],
    move_number: Optional[int],
    is_user: bool,
    cp_loss: int,
) -> None:
    """Run the v53-v65 user-blunder detector suite and inject their
    facts into caption_facts.

    v100 step A1 (Mohit signoff 2026-05-26 — auto-propagation to PWC):
    extracted from game_decryption_v5_service.py lines 3665-3913 so
    both V5 review AND live_v5_teaching can call it. PWC users
    immediately get v53-v65 detector evidence in captions when
    live_v5_teaching is wired (follow-up commit).

    Gate (same as the V5-service inline block):
        is_user AND best_move AND best_move != move_san AND cp_loss >= 100

    When the gate is closed, returns immediately without touching
    caption_facts. When open, runs 14 detectors in registration order;
    each in its own try/except so one detector's failure cannot block
    others. The R12_blunder.json why_clauses_user predicates read
    these fact keys to render concrete teaching ("Play d5 kicking
    their bishop on e6") instead of engine-speak fallback.

    Detector roster (preserved exactly from V5 service order):
      1.  simulate_clearance_for_attack         (Légal's family)
      2.  simulate_clearance_then_check         (Légal's-Mate, v56)
      3.  simulate_attack_with_tempo            (v57)
      4.  simulate_queen_fork_with_check        (v61)
      5.  simulate_endgame_loose_pawn_grab      (v62)
      6.  simulate_un_developing                (v63 #4)
      7.  simulate_defensive_pawn_push          (v63 #7)
      8.  simulate_knight_outpost               (v63 #11)
      9.  simulate_stop_opponent_pawn_advance   (v63 #14)
      10. simulate_active_defense               (v64 #12)
      11. simulate_same_piece_better_square     (v64 #8)
      12. simulate_discovered_attack_vacating_check  (v64 #6)
      13. simulate_knight_on_rim_in_opening     (v65 #9)
      14. simulate_pawn_kicks_piece             (v65 #10)

    MUTATES caption_facts in place. No return.
    """
    if not (is_user and best_move and best_move != move_san and (cp_loss or 0) >= 100):
        return

    # Lazy-import shape_detectors to keep import cost out of code paths
    # that don't fire this gate (most moves).
    from services.shape_detectors import (
        simulate_clearance_for_attack,
        simulate_clearance_then_check,
        simulate_attack_with_tempo,
        simulate_queen_fork_with_check,
        simulate_endgame_loose_pawn_grab,
        simulate_un_developing,
        simulate_defensive_pawn_push,
        simulate_knight_outpost,
        simulate_stop_opponent_pawn_advance,
        simulate_active_defense,
        simulate_same_piece_better_square,
        simulate_discovered_attack_vacating_check,
        simulate_knight_on_rim_in_opening,
        simulate_pawn_kicks_piece,
    )

    # 1. Clearance-for-attack (Légal's family).
    try:
        _clearance_evs = simulate_clearance_for_attack(fen_before, best_move)
        if _clearance_evs:
            _ev0 = _clearance_evs[0]
            _targets = _ev0.get("targets") or []
            if _targets:
                caption_facts["missed_clearance_attack_square"] = _targets[0]
            _piece = _ev0.get("clearer_piece_type")
            if _piece:
                caption_facts["missed_clearance_attacker_piece"] = _piece
    except Exception:
        pass

    # 2. Clearance-then-check (Légal's-Mate, v56).
    try:
        _ctc_evs = simulate_clearance_then_check(fen_before, best_move)
        if _ctc_evs:
            _e = _ctc_evs[0]
            _piece = _e.get("clearer_piece_type")
            _dest = _e.get("slider_destination_square")
            _follow = _e.get("follow_up_san")
            _king = _e.get("king_square")
            if _piece and _dest and _follow:
                caption_facts["missed_clearance_then_check_piece"] = _piece
                caption_facts["missed_clearance_then_check_destination"] = _dest
                caption_facts["missed_clearance_then_check_follow_up_san"] = _follow
                if _king:
                    caption_facts["missed_clearance_then_check_king_square"] = _king
    except Exception:
        pass

    # 3. Attack-with-tempo (v57).
    try:
        _atw_evs = simulate_attack_with_tempo(
            fen_before, best_move, pv_after_best or [],
        )
        if _atw_evs:
            _e = _atw_evs[0]
            _piece = _e.get("attacked_piece_type")
            _sq = _e.get("attacked_square")
            _follow = _e.get("follow_up_san")
            if _piece and _sq:
                caption_facts["attack_with_tempo_piece"] = _piece
                caption_facts["attack_with_tempo_square"] = _sq
                if _follow:
                    caption_facts["attack_with_tempo_follow_up_san"] = _follow
    except Exception:
        pass

    # 4. Queen-fork-with-check (v61).
    try:
        _qf_evs = simulate_queen_fork_with_check(fen_before, best_move)
        if _qf_evs:
            _e = _qf_evs[0]
            caption_facts["queen_fork_sub_kind"] = _e.get("sub_kind")
            caption_facts["queen_fork_secondary_piece"] = _e.get("secondary_piece")
            caption_facts["queen_fork_secondary_square"] = _e.get("secondary_square")
            caption_facts["queen_fork_king_square"] = _e.get("king_square")
    except Exception:
        pass

    # 5. Endgame loose-pawn grab (v62).
    try:
        _eg_evs = simulate_endgame_loose_pawn_grab(fen_before, best_move)
        if _eg_evs:
            _e = _eg_evs[0]
            caption_facts["endgame_loose_pawn_sub_kind"] = _e.get("sub_kind")
            caption_facts["endgame_loose_pawn_moving_piece"] = _e.get("moving_piece_type")
            caption_facts["endgame_loose_pawn_square"] = _e.get("pawn_square")
    except Exception:
        pass

    # 6. Un-developing (v63 #4).
    try:
        _ud_evs = simulate_un_developing(
            fen_before, move_san, best_move,
            move_number=move_number,
        )
        if _ud_evs:
            _e = _ud_evs[0]
            caption_facts["un_developing_piece"] = _e.get("moving_piece_type")
            caption_facts["un_developing_from"] = _e.get("from_square")
            caption_facts["un_developing_home"] = _e.get("home_square")
    except Exception:
        pass

    # 7. Defensive pawn push (v63 #7).
    try:
        _dp_evs = simulate_defensive_pawn_push(
            fen_before, move_san, best_move,
            move_number=move_number,
        )
        if _dp_evs:
            _e = _dp_evs[0]
            caption_facts["defensive_pawn_user_san"] = _e.get("user_pawn_san")
            caption_facts["defensive_pawn_best_dev_san"] = _e.get("best_dev_san")
    except Exception:
        pass

    # 8. Knight outpost (v63 #11).
    try:
        _ko_evs = simulate_knight_outpost(fen_before, best_move)
        if _ko_evs:
            _e = _ko_evs[0]
            caption_facts["knight_outpost_destination"] = _e.get("knight_destination")
            caption_facts["knight_outpost_defender_piece"] = _e.get("defender_piece")
            caption_facts["knight_outpost_defender_square"] = _e.get("defender_square")
    except Exception:
        pass

    # 9. Stop opp pawn advance (v63 #14).
    try:
        _so_evs = simulate_stop_opponent_pawn_advance(
            fen_before, move_san, best_move,
        )
        if _so_evs:
            _e = _so_evs[0]
            caption_facts["stop_opp_pawn_blocking_san"] = _e.get("blocking_pawn_san")
            caption_facts["stop_opp_pawn_opp_square"] = _e.get("opp_pawn_square")
    except Exception:
        pass

    # 10. Active-defense (v64 #12).
    try:
        _ad_evs = simulate_active_defense(fen_before, best_move)
        if _ad_evs:
            _e = _ad_evs[0]
            caption_facts["active_defense_defended_piece"] = _e.get("defended_piece")
            caption_facts["active_defense_defended_square"] = _e.get("defended_square")
            caption_facts["active_defense_attacked_piece"] = _e.get("attacked_piece")
            caption_facts["active_defense_attacked_square"] = _e.get("attacked_square")
    except Exception:
        pass

    # 11. Same-piece-better-square (v64 #8).
    try:
        _sb_evs = simulate_same_piece_better_square(
            fen_before, move_san, best_move,
        )
        if _sb_evs:
            _e = _sb_evs[0]
            caption_facts["same_piece_better_extra_piece"] = _e.get("extra_piece")
            caption_facts["same_piece_better_extra_square"] = _e.get("extra_square")
            caption_facts["same_piece_better_shared_piece"] = _e.get("shared_piece")
            caption_facts["same_piece_better_shared_square"] = _e.get("shared_square")
    except Exception:
        pass

    # 12. Discovered-attack-vacating-with-check (v64 #6).
    try:
        _dv_evs = simulate_discovered_attack_vacating_check(fen_before, best_move)
        if _dv_evs:
            _e = _dv_evs[0]
            caption_facts["discovered_vac_moved_piece"] = _e.get("moved_piece")
            caption_facts["discovered_vac_slider_piece"] = _e.get("slider_piece")
            caption_facts["discovered_vac_exposed_piece"] = _e.get("exposed_piece")
            caption_facts["discovered_vac_exposed_square"] = _e.get("exposed_square")
    except Exception:
        pass

    # 13. Knight-on-rim in opening (v65 #9).
    try:
        _kr_evs = simulate_knight_on_rim_in_opening(
            fen_before, move_san, best_move,
            move_number=move_number,
        )
        if _kr_evs:
            _e = _kr_evs[0]
            caption_facts["knight_on_rim_square"] = _e.get("knight_square")
    except Exception:
        pass

    # 14. Pawn-kicks-piece (v65 #10).
    try:
        _pk_evs = simulate_pawn_kicks_piece(fen_before, best_move)
        if _pk_evs:
            _e = _pk_evs[0]
            caption_facts["pawn_kicks_piece_type"] = _e.get("kicked_piece_type")
            caption_facts["pawn_kicks_piece_square"] = _e.get("kicked_square")
    except Exception:
        pass


def inject_em_dash_and_trap_context_facts(
    caption_facts: Dict[str, Any],
    *,
    game_trap_fires: Optional[List[Dict[str, Any]]],
    best_move: Optional[str],
    move_san: str,
    is_user: bool,
    cp_loss: int,
    opening_name: Optional[str],
) -> Optional[Tuple[List[Dict[str, Any]], int]]:
    """A2: extract v66 em-dash voice-match + v69 trap-context wiring.

    Mohit signoff 2026-05-26 (auto-propagation arc). Extracted from
    game_decryption_v5_service.py lines 3684-3787 verbatim. Two
    responsibilities bundled because they share the same gate. Order
    of operations preserved EXACTLY:

      v66 em-dash (FIRST): when any of the 17 detector-evidence keys
      are present in caption_facts, set why_clause_em_dash=True so
      R12_blunder uses the em-dash parent variant ("Y was better
      — reason") instead of the two-sentence default.

      v69 trap-context (SECOND): when game_trap_fires contains a
      setter-role fire whose trap_line[0] equals best_move (and
      isn't sprung yet), stamp trap_context_name / _full_name /
      _first_punishment_san / _description + opening_name on
      caption_facts. Returns (trap_line_steps,
      coach_line_length_hint) from data/traps.json for the caller
      to populate the move record's coach_line UI fields.

    Note on the trap_context_name em-dash key: in V5's original
    inline ordering, trap-context runs AFTER em-dash, so a
    trap-only fire (no other detector keys) does NOT trigger
    em-dash voice on the same move. That ordering is preserved
    here — reversing would silently flip user-facing output.

    Gate (identical to V5-service inline block):
        is_user AND best_move AND best_move != move_san AND cp_loss >= 100

    Returns:
      - Tuple of (trap_line_steps, length_hint) when a trap-context
        fire matched and was stamped onto caption_facts. Caller uses
        these to populate the per-move coach_line UI fields.
      - None when the gate was closed OR no trap-context fire matched.
        Caller leaves coach_line fields at their existing values.

    MUTATES caption_facts in place.
    """
    if not (is_user and best_move and best_move != move_san and (cp_loss or 0) >= 100):
        return None

    # ORDER PRESERVATION: original V5 runs em-dash FIRST, then trap-
    # context. trap_context_name appears in the em-dash key list as
    # defensive future-proofing — but in the original code it's NOT
    # set by THIS function call when em-dash is evaluated (trap block
    # hasn't run yet). Reversing the order would silently flip
    # em-dash on trap-only fires. Keep the original order verbatim.

    # v66 em-dash voice-match (line 3684 of V5 service).
    _em_dash_facts = [
        "missed_tactic_kind",
        "missed_clearance_attack_square",
        "missed_clearance_then_check_follow_up_san",
        "attack_with_tempo_piece",
        "queen_fork_sub_kind",
        "endgame_loose_pawn_sub_kind",
        "discovered_vac_exposed_square",
        "active_defense_defended_square",
        "same_piece_better_extra_square",
        "un_developing_piece",
        "defensive_pawn_user_san",
        "knight_outpost_destination",
        "stop_opp_pawn_blocking_san",
        "knight_on_rim_square",
        "pawn_kicks_piece_square",
        "shape_pattern_id",
        "trap_context_name",
    ]
    if any(caption_facts.get(_k) for _k in _em_dash_facts):
        caption_facts["why_clause_em_dash"] = True

    # v69 trap-context wiring (line 3713 of V5 service).
    trap_result: Optional[Tuple[List[Dict[str, Any]], int]] = None
    if game_trap_fires:
        for _tf in game_trap_fires:
            if _tf.get("role") != "setter":
                continue
            _tl = _tf.get("trap_line") or []
            if not _tl:
                continue
            if _tf.get("sprung_moves", 0) >= len(_tl):
                continue
            if best_move != _tl[0]:
                continue
            _raw_name = (_tf.get("trap_name") or "").strip()
            # Strip trailing " Punishment" / " Trap" suffixes — they
            # collide with the verb "punishes" in caption templates.
            _display_name = _raw_name
            for _suf in (" Punishment", " Trap"):
                if _display_name.endswith(_suf):
                    _display_name = _display_name[: -len(_suf)].rstrip()
                    break
            caption_facts["trap_context_name"] = _display_name or _raw_name
            caption_facts["trap_context_full_name"] = _raw_name
            caption_facts["trap_context_first_punishment_san"] = _tl[0]
            _desc = (_tf.get("description") or "").strip()
            if _desc:
                caption_facts["trap_context_description"] = _desc
            # When a trap fires, the opening name IS the critical
            # lesson context — per the project memory rule.
            if opening_name:
                caption_facts["opening_name"] = opening_name
            # v70: look up the trap's rich step records (move +
            # explanation per ply) from data/traps.json for the
            # "Play this line" UI animation.
            try:
                from services.trap_library import get_trap_by_name
                _trap_full = get_trap_by_name(_raw_name)
                if _trap_full and _trap_full.get("trap_line"):
                    _trap_steps = _trap_full["trap_line"]
                    trap_result = (_trap_steps, len(_trap_steps))
            except Exception:
                pass
            # First match wins.
            break

    return trap_result


def inject_opp_side_narration_facts(
    caption_facts: Dict[str, Any],
    *,
    fen_before: str,
    board: chess.Board,
    move: chess.Move,
    move_san: str,
    full_move_number: Optional[int],
    is_user: bool,
    opp_cp_loss: int,
    eval_lookup: Dict[str, Dict[str, Any]],
    user_color: str,
) -> Optional[Tuple[List[str], int]]:
    """A3: extract opp-move narration block (v76/v77/v78.4/v80/v80.2).

    Mohit "go for all" 2026-05-26 (auto-propagation arc). Extracted
    verbatim from game_decryption_v5_service.py lines 3341-3530.

    Gate (identical to inline block):
        not is_user AND opp_cp_loss >= 30

    What this does (when the gate opens):
      - v76.2 derive user_best_reply_san from next-position eval:
        best_move first, then pv_after_best[0], then pv_after_played[0],
        validated as legal SAN in the post-opp position.
      - v78.4 build coach_line_moves = [opp_played, user_reply,
        opp_followup, user_continuation] when reply found AND
        opp_cp_loss >= 30. Returns the line for the caller.
      - v77 call detect_opp_move_punishments → opp_user_reply_* facts.
      - v80 call detect_opp_positional_mistake → opp_played_* facts.
      - Stamp user_best_reply_san + _is_forcing + captured_piece_type
        + target_square on caption_facts.
      - v80.2 opp_has_concrete_why = True iff at least one concrete
        fact key got populated (gates softer opp_soft_reply variant
        in R12 select_variant).

    Returns (coach_line_moves, length_hint) when the v78.4 line was
    built; else None. Caller uses to populate per-move coach_line UI.

    eval_lookup is the V5-service per-game dict keyed on FEN-prefix
    (first 4 fields of FEN). PWC currently doesn't have one — pass
    {} and the function returns None silently (no enrichment).

    MUTATES caption_facts in place.
    """
    if not ((not is_user) and (opp_cp_loss or 0) >= 30):
        return None

    coach_line_result: Optional[Tuple[List[str], int]] = None
    try:
        _post_opp_board = board.copy()
        _post_opp_board.push(move)
        _post_opp_fen_key = " ".join(_post_opp_board.fen().split()[:4])
        _next_eval = eval_lookup.get(_post_opp_fen_key, {})
        # v76.2 — user_best_reply derivation. best_move first, then
        # pv_after_best[0], then pv_after_played[0]. Validate legal
        # SAN to avoid hallucinated punishment lines.
        _user_reply = _next_eval.get("best_move") or None
        if not _user_reply:
            _next_pv_best = _next_eval.get("pv_after_best") or []
            _user_reply = _next_pv_best[0] if _next_pv_best else None
        if not _user_reply:
            _next_pv_played = _next_eval.get("pv_after_played") or []
            _user_reply = _next_pv_played[0] if _next_pv_played else None
        if _user_reply:
            try:
                _post_opp_board.parse_san(_user_reply)
            except Exception:
                _user_reply = None

        # v78.4 / v79.1 — coach_line for opp mistakes (cp_loss >= 30).
        if _user_reply and (opp_cp_loss or 0) >= 30:
            _next_pv_for_line = _next_eval.get("pv_after_best") or []
            _coach_line_moves = [move_san, _user_reply] + list(_next_pv_for_line[:2])
            coach_line_result = (_coach_line_moves, len(_coach_line_moves))

        # v77 — opp move punishment detectors.
        if _user_reply:
            try:
                from services.pattern_catalog import detect_opp_move_punishments
                _next_pv_best_for_punish = _next_eval.get("pv_after_best") or []
                _punish_facts = detect_opp_move_punishments(
                    post_opp_fen=_post_opp_board.fen(),
                    user_best_reply_san=_user_reply,
                    post_opp_pv_after_best=_next_pv_best_for_punish,
                    user_color=user_color,
                    post_opp_eval_before_cp=_next_eval.get("eval_before"),
                )
                if _punish_facts:
                    caption_facts.update(_punish_facts)
            except Exception as _punish_exc:
                logger.info(
                    f"[opp_punish] detect failed m{full_move_number} "
                    f"{move_san}: {_punish_exc}"
                )

        # v80 — opp positional mistake.
        try:
            from services.pattern_catalog import detect_opp_positional_mistake
            _opp_pos_facts = detect_opp_positional_mistake(
                pre_fen=fen_before,
                opp_played_san=move_san,
                move_number=full_move_number,
            )
            if _opp_pos_facts:
                caption_facts.update(_opp_pos_facts)
        except Exception as _opp_pos_exc:
            logger.info(
                f"[opp_positional] detect failed m{full_move_number} "
                f"{move_san}: {_opp_pos_exc}"
            )

        # Stamp user_best_reply + is_forcing + capture facts.
        if _user_reply:
            caption_facts["user_best_reply_san"] = _user_reply
            if _user_reply.endswith("+") or _user_reply.endswith("#"):
                caption_facts["user_best_reply_san_is_forcing"] = True
            if "x" in _user_reply:
                try:
                    _ur_move = _post_opp_board.parse_san(_user_reply)
                    _captured = _post_opp_board.piece_at(_ur_move.to_square)
                    if _captured:
                        _piece_name = chess.piece_name(_captured.piece_type)
                        caption_facts["user_best_reply_captures_piece_type"] = _piece_name
                        caption_facts["captured_piece_type"] = _piece_name
                        caption_facts["target_square"] = chess.square_name(_ur_move.to_square)
                except Exception:
                    pass
    except Exception:
        pass

    # v80.2 — opp_has_concrete_why. Set ONLY when a concrete detector
    # fact got populated. R12 select_variant uses this to route the
    # NOT-concrete case to opp_soft_reply ("Opponent's Nc3 — engine
    # has a slight preference here. Best reply: Nc6.") instead of
    # the overclaiming "Opponent's Nc3 is an inaccuracy" framing.
    _concrete_fact_keys = (
        "opp_user_reply_queen_fork_sub_kind",
        "opp_user_reply_clearance_follow_up_san",
        "opp_user_reply_clearance_attack_square",
        "opp_user_reply_attack_piece",
        "opp_user_reply_kicks_piece_type",
        "opp_user_reply_endgame_pawn_sub_kind",
        "captured_piece_type",
        "opp_played_wing_pawn_san",
        "opp_played_knight_on_rim_san",
        "opp_played_queen_early_san",
        "opp_played_un_developed_san",
    )
    has_concrete = any(caption_facts.get(_k) for _k in _concrete_fact_keys)
    # Pattern #2 (Mohit 2026-05-26 game_692ab776c5b1 m5 c5): tactic_kind
    # is concrete only when R12 has a template variant for the kind —
    # "mate" → why_opp_user_finds_mate, "piece_capture" → why_opp_user_wins_piece.
    # "material" has no template (it's a dead flag from detect_missed_tactic's
    # "honest material gain" fallback) and was previously promoting thin opp
    # inaccuracies past the cp<100 suppression gate.
    if caption_facts.get("opp_user_reply_tactic_kind") in ("mate", "piece_capture"):
        has_concrete = True
    if has_concrete:
        caption_facts["opp_has_concrete_why"] = True

    return coach_line_result


def inject_opening_context_facts(
    caption_facts: Dict[str, Any],
    *,
    board: chess.Board,
    move: chess.Move,
    move_san: str,
    move_index: int,
    phase: str,
    eco_code: Optional[str],
    opening_name: Optional[str],
    user_color: str,
    prev_move_san: Optional[str],
) -> None:
    """A4: opening intro (v74) + opening theory lookup (v88).

    Mohit "go for all" 2026-05-26 (auto-propagation arc). Extracted
    verbatim from game_decryption_v5_service.py lines 3369-3470.

    Gate: move_index < 6 AND phase == "opening"

    What this does (when gate opens):
      - v74 get_opening_introduction → opening_intro_name +
        opening_intro_idea (passes prev_move_san so 1.e4 d5 →
        Scandinavian, not "Closed Game")
      - v88 opening_theory_lookup against the POST-move FEN:
        if matched, sets opening_theory_name / _variation /
        _key_decision / _match_quality + per-move teaching
        (idea / why_good / why_bad / consequence / learning) +
        top_move_san / top_move_idea fallback

    Note: get_opening_introduction lives in
    services/game_decryption_v5_service. Lazy-imported here to avoid
    circular import (caption_pipeline is imported BY the V5 service).

    MUTATES caption_facts in place.
    """
    if not (move_index < 6 and phase == "opening"):
        return

    # v74 — opening introduction.
    try:
        from services.game_decryption_v5_service import get_opening_introduction
        _intro = get_opening_introduction(
            eco_code, opening_name, move_san, user_color,
            move_index=move_index,
            prev_move_san=prev_move_san,
        )
        if _intro:
            _in_name = _intro.get("name")
            _in_idea = _intro.get("idea")
            if _in_name:
                caption_facts["opening_intro_name"] = _in_name
            if _in_idea:
                caption_facts["opening_intro_idea"] = _in_idea
    except Exception:
        pass

    # v88 — opening_theory_tree lookup against post-move FEN.
    try:
        from services.opening_theory_lookup import (
            match_position as _otl_match,
            classify_played_move as _otl_classify,
            top_best_move as _otl_top_best,
        )
        _otl_after_board = board.copy()
        _otl_after_board.push(move)
        _theory = _otl_match(_otl_after_board.fen())
        if _theory:
            caption_facts["opening_theory_name"] = _theory.get("opening_name")
            caption_facts["opening_theory_variation"] = _theory.get("variation_name")
            caption_facts["opening_theory_key_decision"] = _theory.get("key_decision")
            _q = _otl_classify(_theory, move_san)
            caption_facts["opening_theory_match_quality"] = _q
            if _q == "best":
                _entry = (_theory.get("best_moves") or {}).get(move_san) or {}
                caption_facts["opening_theory_played_idea"] = _entry.get("idea")
                caption_facts["opening_theory_played_why_good"] = _entry.get("why_good")
            elif _q == "mistake":
                _entry = (_theory.get("mistake_moves") or {}).get(move_san) or {}
                caption_facts["opening_theory_played_why_bad"] = _entry.get("why_bad")
                caption_facts["opening_theory_played_consequence"] = _entry.get("consequence")
                caption_facts["opening_theory_played_learning"] = _entry.get("learning")
            _top = _otl_top_best(_theory)
            if _top:
                _top_san, _top_info = _top
                caption_facts["opening_theory_top_move_san"] = _top_san
                caption_facts["opening_theory_top_move_idea"] = _top_info.get("idea")
    except Exception:
        pass


def update_trap_recognition_state(
    *,
    played_san_so_far: List[str],
    move_san: str,
    is_user: bool,
    user_color: str,
    full_move_number: Optional[int],
    active_trap: Optional[Dict[str, Any]],
    active_trap_setup_completed_by_user: bool,
    active_trap_step_cursor: int,
) -> Tuple[
    Optional[Dict[str, Any]],  # trap_record (for content promotion)
    Optional[Dict[str, Any]],  # new active_trap
    bool,                       # new active_trap_setup_completed_by_user
    int,                        # new active_trap_step_cursor
]:
    """A5: trap recognition state machine (v69/v89 trap-line tracking).

    Mohit "go for all" 2026-05-26 (auto-propagation arc). Extracted
    verbatim from game_decryption_v5_service.py lines 3909-3989.

    State machine across game moves:
      - If active_trap is None: call detect_trap_setup() on the full
        played_san history. If a setup completes, set active_trap to
        the matched trap, return trap_record with step_label='setup_completed'.
      - If active_trap is set: call match_trap_line_step() with the
        current step_cursor. If the played move matches, advance the
        cursor and return trap_record with step_label='victim_falls'
        (even step) or 'trap_player_punishes' (odd step). When the
        cursor reaches end-of-line, clear active_trap. If the move
        deviates, clear active_trap.

    v89 plumbing: trap_record includes trap_color + user_is_victim
    derived from user_color vs trap.trap_color (opposite = victim).
    Used by R_PROMOTED_trap_setup variants to flip the warning
    framing ("watch out — Damiano Punishment territory; white plays
    Nxe5 next") when the user is on the victim side.

    Returns a 4-tuple:
      (trap_record, active_trap_after, active_trap_setup_completed_by_user_after,
       active_trap_step_cursor_after)

    The caller must update the same three state variables from the
    return values for the NEXT move to see the updated state. PWC
    callers will persist them on coach_sessions.

    The caller is responsible for appending move_san to
    played_san_so_far BEFORE calling — this matches V5 service's
    ordering and lets the detector see the full prefix including
    this move.
    """
    # Lazy import to avoid hot import on every call when no traps are
    # configured.
    try:
        from services.trap_recognition import detect_trap_setup, match_trap_line_step
    except Exception:
        return (None, active_trap, active_trap_setup_completed_by_user, active_trap_step_cursor)

    if detect_trap_setup is None or match_trap_line_step is None:
        return (None, active_trap, active_trap_setup_completed_by_user, active_trap_step_cursor)

    trap_record: Optional[Dict[str, Any]] = None
    try:
        if active_trap is None:
            hit = detect_trap_setup(played_san_so_far)
            if hit:
                active_trap = hit
                active_trap_setup_completed_by_user = bool(is_user)
                active_trap_step_cursor = 0
                # v89: user_is_victim derivation.
                _hit_trap_color = (hit.get("trap_color") or "").lower()
                _user_is_victim = bool(
                    _hit_trap_color
                    and (user_color or "").lower() != _hit_trap_color
                )
                trap_record = {
                    "name": hit["name"],
                    "family": hit["family"],
                    "description": hit["description"],
                    "step": 0,
                    "step_label": "setup_completed",
                    "completed_by_user": active_trap_setup_completed_by_user,
                    "this_move_by_user": bool(is_user),
                    "next_expected_move": hit["trap_line"][0] if hit["trap_line"] else None,
                    "trap_color": hit.get("trap_color"),
                    "user_is_victim": _user_is_victim,
                    "success_message": hit.get("success_message"),
                }
        else:
            step_index = active_trap_step_cursor
            if match_trap_line_step(active_trap, move_san, step_index):
                step_label = "victim_falls" if step_index % 2 == 0 else "trap_player_punishes"
                step_expl = ""
                steps = active_trap.get("trap_line_steps") or []
                if step_index < len(steps):
                    step_expl = steps[step_index].get("explanation", "")
                next_mv = None
                if step_index + 1 < len(active_trap["trap_line"]):
                    next_mv = active_trap["trap_line"][step_index + 1]
                _step_trap_color = (active_trap.get("trap_color") or "").lower()
                _step_user_is_victim = bool(
                    _step_trap_color
                    and (user_color or "").lower() != _step_trap_color
                )
                trap_record = {
                    "name": active_trap["name"],
                    "family": active_trap["family"],
                    "description": active_trap["description"],
                    "step": step_index + 1,
                    "step_label": step_label,
                    "step_explanation": step_expl,
                    "completed_by_user": active_trap_setup_completed_by_user,
                    "this_move_by_user": bool(is_user),
                    "next_expected_move": next_mv,
                    "trap_color": active_trap.get("trap_color"),
                    "user_is_victim": _step_user_is_victim,
                    "success_message": active_trap.get("success_message"),
                }
                active_trap_step_cursor = step_index + 1
                if active_trap_step_cursor >= len(active_trap["trap_line"]):
                    active_trap = None
                    active_trap_step_cursor = 0
            else:
                # Player deviated from trap_line — drop tracking.
                active_trap = None
                active_trap_step_cursor = 0
    except Exception as _trap_exc:
        logger.info(f"[trap] detect failed on move {full_move_number}: {_trap_exc}")
        trap_record = None

    return (
        trap_record,
        active_trap,
        active_trap_setup_completed_by_user,
        active_trap_step_cursor,
    )


def select_shape_pattern_record(
    *,
    fen_before: str,
    board: chess.Board,
    move: chess.Move,
    move_san: str,
    prev_move: Optional[chess.Move],
    eval_data: Dict[str, Any],
    pv_after_played: Optional[List[str]],
    severity: str,
    full_move_number: Optional[int],
    shapes_fired_this_game: Set[str],
) -> Optional[Dict[str, Any]]:
    """A6: shape pattern selection (pre-move detect + post-move detect).

    Mohit "go for all" 2026-05-26 (auto-propagation arc). Extracted
    verbatim from game_decryption_v5_service.py lines 3798-3903.

    Two passes:
      1. PRE-MOVE: select_shape_for_position on chess.Board(fen_before).
         If matched, runs v80.3 mover-departs suppression — when the
         played move's FROM square equals the pattern's mover anchor
         (and TO != mover), the move BREAKS the pattern, so suppress
         the attribution rather than caption "Be7 — Pin" on a move
         that ACTUALLY MOVES the pinning bishop away.

      2. POST-MOVE (fallback): if pre-move returned None AND severity
         in {mistake, blunder, opp_mistake, opp_blunder} AND
         pv_after_played present, run detect_all_shapes on the
         post-move board (the one passed as `board`), filter to
         patterns with detect_phase=post_move, verify against engine
         (opp's pv_after_played[0] is the executing move), pick the
         highest-priority candidate.

    `shapes_fired_this_game` is mutated when post-move shape fires
    (the set tracks once-per-game so we don't repeat the same
    "you walked into this" geometry).

    Returns the shape_pattern_record dict (with pattern_id,
    pattern_name, pattern_desc, mover, targets, executing_move,
    evidence) or None.

    Imports are lazy (services.shape_layer / services.shape_patterns)
    so we don't pay cost on every move when no shape fires.
    """
    # Lazy import to mirror V5 service's optional-import pattern.
    try:
        from services.shape_layer import select_shape_for_position as _select_shape_for_position
    except Exception:
        _select_shape_for_position = None
    try:
        from services.shape_detectors import detect_all_shapes as _detect_all_shapes
    except Exception:
        _detect_all_shapes = None
    try:
        from services.shape_patterns import PATTERNS_BY_ID as _SHAPE_PATTERNS_BY_ID
    except Exception:
        _SHAPE_PATTERNS_BY_ID = None
    try:
        from services.shape_detectors import verify_with_engine_data as _verify_shapes_with_engine
    except Exception:
        _verify_shapes_with_engine = None

    shape_pattern_record: Optional[Dict[str, Any]] = None

    # ── Pre-move shape detection ────────────────────────────────
    if _select_shape_for_position is not None:
        try:
            pre_move_board = chess.Board(fen_before)
            shape_pattern_record = _select_shape_for_position(
                pre_move_board,
                eval_data={"best_move_uci": eval_data.get("best_move_uci", "")},
                shapes_fired_this_game=shapes_fired_this_game,
                prev_move=prev_move,
            )
        except Exception as _shape_exc:
            logger.info(f"[shape_v3] detect failed on move {full_move_number}: {_shape_exc}")
            shape_pattern_record = None

        # v80.3 mover-departs suppression.
        if shape_pattern_record:
            _mover_sq = shape_pattern_record.get("mover")
            if _mover_sq:
                try:
                    _from_name = chess.square_name(move.from_square)
                    _to_name = chess.square_name(move.to_square)
                    if _from_name == _mover_sq and _to_name != _mover_sq:
                        logger.info(
                            f"[shape_v3] suppressing {shape_pattern_record.get('pattern_id')} "
                            f"on m{full_move_number} {move_san} — move breaks the pattern "
                            f"(mover {_mover_sq} departs)"
                        )
                        shape_pattern_record = None
                except Exception:
                    pass

    # ── Post-move shape detection (fallback) ────────────────────
    # Fires when player walked into a tactical geometry: gate is
    # cp_loss-tier (severity ∈ {mistake, serious, blunder, opp_*}).
    # "serious" (250-399cp) was missing from the gate until 2026-05-26
    # — added as part of the v100 central-layer convergence after
    # surfacing during V5 refactor verification.
    if (
        shape_pattern_record is None
        and _detect_all_shapes is not None
        and _SHAPE_PATTERNS_BY_ID is not None
        and _verify_shapes_with_engine is not None
        and severity in (
            "mistake", "serious", "blunder",
            "opp_mistake", "opp_serious", "opp_blunder",
        )
        and pv_after_played
    ):
        try:
            post_move_board = board.copy()
            opp_best_uci = ""
            try:
                opp_best_uci = post_move_board.parse_san(pv_after_played[0]).uci()
            except Exception:
                opp_best_uci = ""
            post_phase_ids = {
                pid for pid, p in _SHAPE_PATTERNS_BY_ID.items()
                if p.get("detect_phase") == "post_move"
            }
            if post_phase_ids:
                all_post = _detect_all_shapes(post_move_board, prev_move=move)
                post_candidates = [c for c in all_post if c["pattern_id"] in post_phase_ids]
                post_candidates = _verify_shapes_with_engine(
                    post_candidates, {"best_move_uci": opp_best_uci}
                )
                if post_candidates:
                    post_candidates.sort(
                        key=lambda c: -_SHAPE_PATTERNS_BY_ID[c["pattern_id"]].get("priority", 0)
                    )
                    ev = post_candidates[0]
                    spec = _SHAPE_PATTERNS_BY_ID[ev["pattern_id"]]
                    shape_pattern_record = {
                        "pattern_id":     ev["pattern_id"],
                        "pattern_name":   spec.get("name", ""),
                        "pattern_desc":   spec.get("description", ""),
                        "mover":          ev.get("mover"),
                        "targets":        ev.get("targets", []),
                        "executing_move": ev.get("executing_move"),
                        "evidence":       ev.get("evidence", ""),
                    }
                    shapes_fired_this_game.add(ev["pattern_id"])
        except Exception as _post_shape_exc:
            logger.info(
                f"[shape_post_move] detect failed on move {full_move_number}: "
                f"{_post_shape_exc}"
            )

    return shape_pattern_record


def inject_board_state_describer_clause(
    caption_facts: Dict[str, Any],
    *,
    fen_before: str,
    move_san: str,
    user_color: str,
    full_move_number: Optional[int],
    bs_recent_window: List[Set[str]],
    bs_window_size: int = 1,
) -> None:
    """A7: board_state_describer pass with v78 anti-repeat window.

    Mohit "go for all" 2026-05-26 (auto-propagation arc). Extracted
    verbatim from game_decryption_v5_service.py lines 3602-3643.
    Default bs_window_size=1 mirrors _BS_WINDOW_SIZE in V5 service
    (suppress only immediately-consecutive repeats).

    Runs UNCONDITIONALLY — each bs_* metric self-gates via its own
    threshold so clean positions return 0 facts naturally. Selects
    top 3 facts (max 2 per category), filters out fact_ids that
    fired in the last `bs_window_size` moves to avoid same-observation
    spam across consecutive moves, renders R12_blunder templates,
    joins into caption_facts["board_state_clause"].

    bs_recent_window is a list-of-sets the caller maintains across
    moves. This function appends a new set of fact_ids to it and
    trims to bs_window_size.

    MUTATES caption_facts AND bs_recent_window in place.
    """
    try:
        from services.board_state_describer import describe_board_state, select_top_facts
        from services.caption_templates import render_template
        _b = chess.Board(fen_before)
        _b.push_san(move_san)
        _fen_after = _b.fen()
        _bs_facts = describe_board_state(
            fen_after=_fen_after,
            user_color=(user_color or ""),
            move_number=full_move_number or 0,
        )
        _top = select_top_facts(_bs_facts, n=3, max_per_category=2)
        # v78 — filter out fact_ids already fired in the last N moves.
        if _top and bs_recent_window:
            _recent_ids: set = set()
            for _w in bs_recent_window:
                _recent_ids.update(_w)
            _top = [_bf for _bf in _top if _bf.fact_id not in _recent_ids]
        bs_recent_window.append({_bf.fact_id for _bf in _top})
        if len(bs_recent_window) > bs_window_size:
            bs_recent_window.pop(0)
        if _top:
            _rendered: list = []
            for _bf in _top:
                _merged = {**caption_facts, **_bf.placeholders}
                _txt = render_template("R12_blunder", _bf.fact_id, _merged)
                if _txt:
                    _rendered.append(_txt)
            if _rendered:
                caption_facts["board_state_clause"] = " ".join(_rendered)
    except Exception:
        pass


def classify_caption_tier(
    *,
    caption_text: str,
    rule_name: str,
) -> str:
    """A8: caption_classifier tier classification.

    Mohit "go for all" 2026-05-26 (auto-propagation arc). Extracted
    verbatim from game_decryption_v5_service.py lines 4067-4075.

    Returns "HIGH" / "MID" / "LOW" / "NONE". HIGH means the caption
    has real teaching content; the move record sets
    has_teaching_content=True only when tier=="HIGH".

    Lazy-imports caption_classifier so consumers without it
    (or PWC live calls where the classifier hasn't loaded yet)
    degrade to "NONE" cleanly.
    """
    try:
        from services.caption_classifier import classifier as _caption_classifier
        return _caption_classifier.classify(
            caption_text or "",
            rule_name or "",
        ).get("tier") or "NONE"
    except Exception:
        return "NONE"


def apply_promotion_ladder_dispatch(
    *,
    caption_payload: Dict[str, Any],
    caption_facts: Dict[str, Any],
    trap_record: Optional[Dict[str, Any]],
    opening_record: Optional[Dict[str, Any]],
    shape_pattern_record: Optional[Dict[str, Any]],
    move_san: str,
    is_user: bool,
    cp_loss: int,
    best_move: Optional[str],
    principle_cue: str,
    principle_id_used: Optional[str],
    full_move_number: Optional[int],
) -> None:
    """A9: promotion ladder dispatch — builds promotion_facts from
    caption_facts + detector records, calls dispatch_promotion(), and
    if a promoted variant fires, overwrites caption_payload's caption
    + rule_name (rule_name becomes "{prev_rule}→{promoted_source}").

    Mohit "go for all" 2026-05-26 (auto-propagation arc). Extracted
    verbatim from game_decryption_v5_service.py lines 3854-3963.

    The promotion ladder logic lives entirely in JSON
    (promotion_ladder.json + R_PROMOTED_*.json). Python only builds
    the facts dict; the dispatcher handles priority order, when-
    conditions, variant selection, severity thresholds, source labels.

    MUTATES caption_payload in place.
    """
    try:
        from services.caption_templates import dispatch_promotion as _dispatch_promotion
    except Exception:
        return
    if _dispatch_promotion is None:
        return

    try:
        tn = (trap_record or {}).get("name") or ""
        on = (opening_record or {}).get("name") or ""
        sp_id = (shape_pattern_record or {}).get("pattern_id") or ""
        promotion_facts = {
            # Move-level facts
            "move_san": move_san,
            "is_user": is_user,
            "cp_loss": cp_loss or 0,
            "best_move": best_move,
            "best_move_differs": bool(best_move and best_move != move_san),
            "caption_empty": not bool(caption_payload.get("caption")),

            # Detector records (predicates use dotted access:
            # trap_record.step_label, opening_record.name, etc.)
            "trap_record": trap_record or {},
            "opening_record": opening_record or {},

            # Promotion-template facts
            "trap_name": tn,
            "trap_description": (trap_record or {}).get("description") or "",
            "this_move_by_user": bool((trap_record or {}).get("this_move_by_user")),
            "trap_name_slug": tn.lower().replace(" ", "_") if tn else "",
            "trap_user_is_victim": bool((trap_record or {}).get("user_is_victim")),
            "trap_next_expected_move": (trap_record or {}).get("next_expected_move") or "",
            "trap_color": (trap_record or {}).get("trap_color") or "",

            "opening_name": on,
            "opening_summary": (opening_record or {}).get("summary") or "",
            "opening_name_slug": on.lower().replace(" ", "_") if on else "",

            "opening_intro_name": caption_facts.get("opening_intro_name"),
            "opening_intro_idea": caption_facts.get("opening_intro_idea"),

            "opening_theory_name": caption_facts.get("opening_theory_name"),
            "opening_theory_variation": caption_facts.get("opening_theory_variation"),
            "opening_theory_key_decision": caption_facts.get("opening_theory_key_decision"),
            "opening_theory_match_quality": caption_facts.get("opening_theory_match_quality"),
            "opening_theory_played_idea": caption_facts.get("opening_theory_played_idea"),
            "opening_theory_played_why_good": caption_facts.get("opening_theory_played_why_good"),
            "opening_theory_played_why_bad": caption_facts.get("opening_theory_played_why_bad"),
            "opening_theory_played_consequence": caption_facts.get("opening_theory_played_consequence"),
            "opening_theory_played_learning": caption_facts.get("opening_theory_played_learning"),
            "opening_theory_top_move_san": caption_facts.get("opening_theory_top_move_san"),
            "opening_theory_top_move_idea": caption_facts.get("opening_theory_top_move_idea"),

            "shape_pattern_name": (shape_pattern_record or {}).get("pattern_name") or "",
            "shape_pattern_desc": (shape_pattern_record or {}).get("pattern_desc") or "",
            "shape_pattern_id": sp_id,

            "principle_cue": principle_cue or "",
            "principle_id_used": principle_id_used or "unknown",

            "board_state_clause": caption_facts.get("board_state_clause"),

            "blocked_pawn_file": caption_facts.get("blocked_pawn_file"),
            "blocked_pawn_square": caption_facts.get("blocked_pawn_square"),
            "blocked_pawn_would_support": caption_facts.get("blocked_pawn_would_support"),

            "curriculum_deviation_clause": caption_facts.get("curriculum_deviation_clause"),
            "curriculum_expected_move": caption_facts.get("curriculum_expected_move"),
            "curriculum_opening_name": caption_facts.get("curriculum_opening_name"),

            "user_is_winning": caption_facts.get("user_is_winning"),
            "user_is_losing": caption_facts.get("user_is_losing"),
        }
        promoted_text, promoted_source = _dispatch_promotion(promotion_facts)
        if promoted_text:
            prev_rule = caption_payload.get("rule_name") or "R_FALLBACK"
            caption_payload["caption"] = promoted_text
            caption_payload["rule_name"] = f"{prev_rule}→{promoted_source}"
    except Exception as _promote_exc:
        logger.info(
            f"[content_promotion] move {full_move_number} "
            f"{move_san} failed: {_promote_exc}"
        )


def inject_eval_trajectory_facts(
    caption_facts: Dict[str, Any],
    *,
    move_evaluations: Optional[List[Dict[str, Any]]],
    current_move_number: Optional[int],
    user_color: str,
    is_user: bool,
    cp_loss: int,
) -> None:
    """A10: eval-trajectory detection.

    Mohit "until the final goal" 2026-05-26. Extracted verbatim from
    game_decryption_v5_service.py lines 3461-3478.

    When the user was already losing BEFORE this move, set
    position_was_already_losing + losing_since_move so R12 caption
    can say "you were already in trouble" instead of attributing the
    loss to this move.

    Gate (V5 inline): is_user AND cp_loss >= 100.

    Needs the game's full move_evaluations list. For PWC the list is
    typically not available on a per-session basis — pass None /
    empty and the helper silently no-ops (the inner detector returns
    empty when move_evaluations is empty).

    MUTATES caption_facts in place.
    """
    if not (is_user and (cp_loss or 0) >= 100):
        return
    if not move_evaluations:
        return
    try:
        from services.eval_trajectory import detect_trajectory
        _user_is_white = (user_color or "").lower() == "white"
        _traj = detect_trajectory(
            move_evaluations=move_evaluations,
            current_move_number=current_move_number,
            user_is_white=_user_is_white,
        )
        if _traj.get("position_was_already_losing"):
            caption_facts["position_was_already_losing"] = True
            lsm = _traj.get("losing_since_move")
            if lsm is not None:
                caption_facts["losing_since_move"] = lsm
    except Exception:
        pass


def inject_curriculum_deviation_facts(
    caption_facts: Dict[str, Any],
    *,
    move_history_san_excl_current: List[str],
    move_san: str,
    user_color: str,
    is_user: bool,
    cp_loss: int,
    full_move_number: Optional[int],
) -> None:
    """A11: curriculum-deviation detection.

    Mohit "until the final goal" 2026-05-26. Extracted verbatim from
    game_decryption_v5_service.py lines 3494-3547.

    Walks the opening_curriculum_engine trees that match the user's
    color. When the user is IN a curated opening (history walked the
    main line / variation) and deviates from the expected next move,
    surface the tree's hand-authored wrong_feedback +
    curriculum_expected_move + curriculum_opening_name.

    Gate (V5 inline): is_user AND cp_loss >= 30 AND full_move_number <= 20.

    Inputs:
      move_history_san_excl_current — move history BEFORE this move
        (caller computes cap_history[:-1] in V5; PWC sends its
        move_history_san directly).
      move_san — the move played (compared against expected_move).

    MUTATES caption_facts in place.
    """
    if not (is_user and (cp_loss or 0) >= 30):
        return
    if not full_move_number or full_move_number > 20:
        return
    try:
        from services.opening_curriculum_engine import (
            get_opening_guidance,
            _load_curriculum as _load_curr,
        )
        _user_color_norm = (user_color or "white").lower()
        _best_dev = None
        _curr_data = _load_curr()
        _candidate_openings = [
            _ok for _ok, _ent in _curr_data.items()
            if (_ent.get("color") or "").lower() == _user_color_norm
        ]
        for _ok in _candidate_openings:
            try:
                _g = get_opening_guidance(
                    _ok, list(move_history_san_excl_current), _user_color_norm,
                )
            except Exception:
                continue
            if not _g or not _g.get("is_in_book"):
                continue
            _exp = _g.get("expected_move")
            if not _exp:
                continue
            if _exp != move_san:
                _wrong = _g.get("wrong_feedback")
                if _wrong:
                    _best_dev = {
                        "expected": _exp,
                        "wrong": _wrong,
                        "opening": _g.get("position_name") or _ok,
                    }
                    break
        if _best_dev:
            caption_facts["curriculum_deviation_clause"] = _best_dev["wrong"]
            caption_facts["curriculum_expected_move"] = _best_dev["expected"]
            caption_facts["curriculum_opening_name"] = _best_dev["opening"]
    except Exception:
        pass


def inject_blocked_pawn_facts(
    caption_facts: Dict[str, Any],
    *,
    fen_before: str,
    played_san: str,
    best_move: Optional[str],
    full_move_number: Optional[int],
    is_user: bool,
    cp_loss: int,
) -> None:
    """A12: blocked-own-pawn principle detector.

    Mohit "until the final goal" 2026-05-26. Extracted verbatim from
    game_decryption_v5_service.py lines 3557-3579.

    When engine's best move was a pawn push to square X but user
    played a non-pawn piece move to that same X, the user blocked
    their own pawn's advance — surface as a named principle violation.

    Gate (V5 inline): is_user AND best_move AND best_move != move_san
                      AND cp_loss >= 30.

    MUTATES caption_facts in place.
    """
    if not (is_user and best_move and best_move != played_san and (cp_loss or 0) >= 30):
        return
    try:
        from services.principle_blocked_pawn import detect_blocked_pawn
        _bp = detect_blocked_pawn(
            fen_before=fen_before,
            played_san=played_san,
            best_move_san=best_move,
            move_number=full_move_number or 0,
            cp_loss=cp_loss or 0,
        )
        if _bp:
            caption_facts["blocked_pawn_file"] = _bp.get("pawn_file")
            caption_facts["blocked_pawn_square"] = _bp.get("blocked_square")
            _ws = _bp.get("would_support") or []
            if _ws:
                caption_facts["blocked_pawn_would_support"] = _ws[0]
    except Exception:
        pass


def inject_practical_severity_facts(
    caption_facts: Dict[str, Any],
    practical: PracticalSeverity,
) -> None:
    """Stamp the six practical-severity fields into caption_facts.

    Mirrors the v99 wiring (game_decryption_v5_service.py lines
    3336-3341): the JSON predicate engine (R12_blunder.json
    severity_tiers, select_variant rules) reads these from
    caption_facts. Without injection the v96-v99 tone-softening is
    dead code.

    PWC currently doesn't do this injection — live_v5_teaching
    skips the V5 wiring layer. When the pipeline is fully extracted
    and PWC calls compute_caption_facts(), this helper guarantees
    R12 + R_PROMOTED softening reach live coaching too.

    MUTATES caption_facts in place. No return.
    """
    caption_facts["severity_practical"] = practical.practical_tier
    caption_facts["severity_canonical"] = practical.canonical_tier
    caption_facts["mover_state_before"] = practical.state_before
    caption_facts["mover_state_after"] = practical.state_after
    caption_facts["stayed_winning"] = practical.stayed_winning
    caption_facts["decisiveness_changed"] = practical.decisiveness_changed


# ────────────────────────────────────────────────────────────────────
# PIPELINE ENTRY POINT
# ────────────────────────────────────────────────────────────────────


def build_move_teaching_decision(
    inputs: MoveInputs,
    state: CrossMoveState,
    *,
    shapes_fired_this_game: Optional[Set[str]] = None,
    bs_recent_window: Optional[List[Set[str]]] = None,
    game_trap_fires: Optional[List[Dict[str, Any]]] = None,
    eval_lookup: Optional[Dict[str, Dict[str, Any]]] = None,
    move_evaluations: Optional[List[Dict[str, Any]]] = None,
    opening_record: Optional[Dict[str, Any]] = None,
    severity_override: Optional[str] = None,
) -> MoveTeachingDecision:
    """B-phase: orchestrate the A1-A9 helpers into a single entry point.

    Mohit "go for phase B" 2026-05-26. PWC calls this instead of the
    six individual helpers it has today. V5 service keeps its
    per-block call points for now (it has additional inline logic
    interleaved with the A-helpers — curriculum detection, blocked-
    own-pawn, eval trajectory — that isn't part of the A-set).

    Auto-propagation contract: any future enrichment block added to
    caption_pipeline.py and called from this function automatically
    reaches PWC with zero changes to live_v5_teaching.

    Calling order mirrors V5 service per-move loop:
      1. extract_facts (base caption_facts dict)
      2. inject_practical_severity_facts (v99 R12 softening source)
      3. inject_opp_side_narration_facts (A3, opp moves only)
      4. inject_opening_context_facts (A4, idx<6 + opening phase)
      5. inject_user_blunder_detector_facts (A1, user blunders only)
      6. inject_em_dash_and_trap_context_facts (A2, user blunders only)
      7. select_shape_pattern_record (A6)
      8. inject_board_state_describer_clause (A7)
      9. render caption (caption_renderer.render_caption_dict)
      10. update_trap_recognition_state (A5, across-move state)
      11. apply_promotion_ladder_dispatch (A9, may overwrite caption)
      12. classify_caption_tier (A8)

    Optional state args are passed by reference so the helpers can
    mutate them in place (shapes_fired_this_game.add(), etc.). When
    None, fresh empty containers are used for THIS call only —
    degrades anti-repeat / once-per-game behaviour. Callers that need
    those semantics (V5 service per-game tracking; PWC per-session
    when wired) supply persistent containers from their own state.

    Returns a MoveTeachingDecision capturing text + visual +
    teaching_meta + state_mutations + debug_facts. Caller decides
    what to persist.
    """
    # Lazy imports to dodge circular dependency on V5 service.
    try:
        from services.caption_facts import extract_facts
    except Exception:
        extract_facts = None  # type: ignore
    try:
        from services.caption_renderer import render_caption_dict
    except Exception:
        render_caption_dict = None  # type: ignore

    # ─── State containers (caller-provided OR fresh per-call) ───
    _shapes = shapes_fired_this_game if shapes_fired_this_game is not None else set()
    _bs_window = bs_recent_window if bs_recent_window is not None else []
    _game_trap_fires = game_trap_fires if game_trap_fires is not None else []
    _eval_lookup = eval_lookup if eval_lookup is not None else {}

    # ─── Build chess.Board + chess.Move for the helpers that need them
    try:
        board_before = chess.Board(inputs.fen_before)
        played_move = board_before.parse_san(inputs.played_san)
    except Exception:
        # Bad SAN / FEN — return a no-op decision.
        return MoveTeachingDecision(
            should_skip=True,
            skip_reason=f"invalid SAN or FEN: {inputs.played_san!r}",
        )

    # ─── 1-2. Base caption_facts + practical severity ─────────────
    practical = classify_severity_practical(
        int(inputs.cp_loss or 0),
        mover_is_user=bool(inputs.mover_is_user),
        mover_is_white=bool(inputs.mover_is_white),
        eval_before_cp=inputs.eval_before_cp,
        eval_after_cp=inputs.eval_after_cp,
    )
    canonical = classify_severity(
        int(inputs.cp_loss or 0) if inputs.mover_is_user else int(inputs.opp_cp_loss or 0),
        mover_is_user=bool(inputs.mover_is_user),
    )

    caption_facts: Dict[str, Any] = {}
    if extract_facts is not None:
        try:
            caption_facts = extract_facts(
                fen_before=inputs.fen_before,
                played_san=inputs.played_san,
                best_move_san=inputs.best_move_san,
                eval_before_cp=inputs.eval_before_cp,
                eval_after_cp=inputs.eval_after_cp,
                cp_loss=int(inputs.cp_loss or 0),
                pv_after_played=list(inputs.pv_after_played),
                pv_after_best=list(inputs.pv_after_best),
                move_history_san=list(inputs.move_history_san),
                full_move_number=int(inputs.full_move_number or 0),
                mover_is_user=bool(inputs.mover_is_user),
            )
        except Exception:
            logger.exception("[caption_pipeline] extract_facts failed; using empty dict")
            caption_facts = {}

    inject_practical_severity_facts(caption_facts, practical)

    # ─── Order mirrors V5 service per-move loop exactly (verified
    # against game_decryption_v5_service.py callsites — zero-diff
    # depends on this ordering when V5 adopts the central entry).

    # ─── 3. A3 opp-side narration (gates on !is_user + opp_cp>=30) ──
    inject_opp_side_narration_facts(
        caption_facts,
        fen_before=inputs.fen_before,
        board=board_before,
        move=played_move,
        move_san=inputs.played_san,
        full_move_number=inputs.full_move_number,
        is_user=bool(inputs.mover_is_user),
        opp_cp_loss=int(inputs.opp_cp_loss or 0),
        eval_lookup=_eval_lookup,
        user_color=inputs.user_color,
    )

    # ─── 4. A4 opening context (gates on idx<6 + opening phase) ──
    _ply_idx = max(0, (inputs.full_move_number or 1) - 1) * 2
    if not inputs.mover_is_white:
        _ply_idx += 1
    _phase = "opening" if _ply_idx < 12 else "middlegame"
    inject_opening_context_facts(
        caption_facts,
        board=board_before,
        move=played_move,
        move_san=inputs.played_san,
        move_index=_ply_idx,
        phase=_phase,
        eco_code=inputs.eco_code,
        opening_name=inputs.opening_name,
        user_color=inputs.user_color,
        prev_move_san=inputs.prev_move_san,
    )

    # ─── 4b. EARLY pre-move shape pass (V5 lines 3391-3408 of orig).
    # Sets caption_facts["shape_pattern_id"] + ["shape_pattern_target_square"]
    # so R12 why-clauses (and the v66 em-dash voice-match in A2) can
    # consume them. The MAIN A6 shape detection (later, post-render)
    # produces shape_pattern_record which is a separate output. The
    # EARLY pass doesn't honour shapes_fired_this_game anti-repeat —
    # it just provides facts for downstream R-rules.
    try:
        from services.shape_layer import select_shape_for_position as _select_shape_early
        _pre_board_early = chess.Board(inputs.fen_before)
        _shape_early = _select_shape_early(
            _pre_board_early,
            eval_data={"best_move_uci": inputs.best_move_uci or ""},
        )
        if _shape_early:
            caption_facts["shape_pattern_id"] = _shape_early.get("pattern_id")
            _sp_targets_early = _shape_early.get("targets") or []
            if _sp_targets_early:
                caption_facts["shape_pattern_target_square"] = _sp_targets_early[0]
    except Exception:
        pass

    # ─── 5. A1 user blunder detectors (gates on user+cp>=100) ────
    inject_user_blunder_detector_facts(
        caption_facts,
        fen_before=inputs.fen_before,
        move_san=inputs.played_san,
        best_move=inputs.best_move_san,
        pv_after_best=list(inputs.pv_after_best),
        move_number=inputs.full_move_number,
        is_user=bool(inputs.mover_is_user),
        cp_loss=int(inputs.cp_loss or 0),
    )

    # ─── 6. A2 em-dash + trap-context (gates on user+cp>=100) ────
    inject_em_dash_and_trap_context_facts(
        caption_facts,
        game_trap_fires=_game_trap_fires,
        best_move=inputs.best_move_san,
        move_san=inputs.played_san,
        is_user=bool(inputs.mover_is_user),
        cp_loss=int(inputs.cp_loss or 0),
        opening_name=inputs.opening_name,
    )

    # ─── 7a. A10 eval-trajectory (gates on user + cp_loss>=100) ──
    inject_eval_trajectory_facts(
        caption_facts,
        move_evaluations=move_evaluations,
        current_move_number=inputs.full_move_number,
        user_color=inputs.user_color,
        is_user=bool(inputs.mover_is_user),
        cp_loss=int(inputs.cp_loss or 0),
    )

    # ─── 7b. A11 curriculum-deviation (gates on user + cp_loss>=30 + fmn<=20) ──
    inject_curriculum_deviation_facts(
        caption_facts,
        move_history_san_excl_current=list(inputs.move_history_san),
        move_san=inputs.played_san,
        user_color=inputs.user_color,
        is_user=bool(inputs.mover_is_user),
        cp_loss=int(inputs.cp_loss or 0),
        full_move_number=inputs.full_move_number,
    )

    # ─── 7c. A12 blocked-own-pawn (gates on user blunder + best!=played) ──
    inject_blocked_pawn_facts(
        caption_facts,
        fen_before=inputs.fen_before,
        played_san=inputs.played_san,
        best_move=inputs.best_move_san,
        full_move_number=inputs.full_move_number,
        is_user=bool(inputs.mover_is_user),
        cp_loss=int(inputs.cp_loss or 0),
    )

    # ─── 8. A7 board state describer ─────────────────────────────
    inject_board_state_describer_clause(
        caption_facts,
        fen_before=inputs.fen_before,
        move_san=inputs.played_san,
        user_color=inputs.user_color,
        full_move_number=inputs.full_move_number,
        bs_recent_window=_bs_window,
        bs_window_size=1,
    )

    # ─── 9. Render caption (caption_renderer) ────────────────────
    caption_payload: Dict[str, Any] = {"caption": "", "rule_name": "R_FALLBACK"}
    if render_caption_dict is not None:
        try:
            rendered = render_caption_dict(caption_facts)
            if isinstance(rendered, dict):
                caption_payload = rendered
        except Exception:
            logger.exception("[caption_pipeline] render_caption_dict failed; using fallback")

    # ─── 9b. v78 universal describer fallback ────────────────────
    # When rendered caption is empty AND board_state_clause was set
    # by A7 AND the move is being CRITIQUED (cp_loss >= 30), use
    # the describer output as the caption. v91 gate prevents the
    # describer from firing on clean moves as the only surface.
    _bs_cp_loss = int(
        inputs.cp_loss if inputs.mover_is_user else (inputs.opp_cp_loss or 0)
    ) or 0
    if (
        caption_payload
        and not (caption_payload.get("caption") or "").strip()
        and (caption_facts.get("board_state_clause") or "").strip()
        and _bs_cp_loss >= 30
    ):
        _bs_text = caption_facts["board_state_clause"].strip()
        caption_payload["caption"] = f"{inputs.played_san}. {_bs_text}"
        caption_payload["rule_name"] = "R16_board_state_fallback"

    # ─── 9c. Principle suppression + cue-pick ────────────────────
    # Mohit "central layer" 2026-05-26: moved from V5 service inline
    # block (game_decryption_v5_service.py per-move loop, post-render).
    # Both callers go through identical suppression/cue-pick logic.
    #
    # Policies (catalog.suppress):
    #   once_per_move       — no game-state filter (default)
    #   once_per_state_key  — re-arms when state_key changes
    #   once_per_game       — fires exactly once across the game
    #   once_per_state_entry — DEPRECATED; treated as once_per_game
    #
    # cue_absent is GATED on cp_loss >= 30 (otherwise principle
    # didn't apply — engine endorsed the move).
    principle_cue = ""
    principle_id_used: Optional[str] = None
    _fired_principles_added: Set[str] = set()
    _fired_state_keys_added: Set[Tuple] = set()
    try:
        from services.caption_principles import PRINCIPLES as _CAPTION_PRINCIPLES
        _PRINCIPLES_BY_ID = {
            p["id"]: p for p in _CAPTION_PRINCIPLES
            if isinstance(p, dict) and p.get("id")
        }
    except Exception:
        _PRINCIPLES_BY_ID = {}

    if _PRINCIPLES_BY_ID:
        raw_principles = caption_facts.get("principles_violated") or []
        caption_principles_violated: List[Dict[str, Any]] = []
        for _ev in raw_principles:
            _pid = _ev.get("principle_id")
            if not _pid:
                continue
            _entry = _PRINCIPLES_BY_ID.get(_pid, {})
            _suppress = _entry.get("suppress", "once_per_move")
            if _suppress == "once_per_game" or _suppress == "once_per_state_entry":
                if _pid in state.fired_principles:
                    continue
            elif _suppress == "once_per_state_key":
                _sk = _ev.get("state_key")
                if _sk is None:
                    if _pid in state.fired_principles:
                        continue
                else:
                    if _sk in state.fired_state_keys:
                        continue
                    _fired_state_keys_added.add(_sk)
            caption_principles_violated.append(_ev)
            _fired_principles_added.add(_pid)
        caption_facts["principles_violated"] = caption_principles_violated

        if caption_principles_violated:
            sorted_pv = sorted(
                caption_principles_violated,
                key=lambda ev: _PRINCIPLES_BY_ID.get(
                    ev.get("principle_id") or "", {}
                ).get("priority", 99),
            )
            _top = sorted_pv[0]
            _top_pid = _top.get("principle_id")
            _entry = _PRINCIPLES_BY_ID.get(_top_pid, {}) if _top_pid else {}
            _endorsement = _top.get("engine_endorsement", "absent")
            _cue_key = {
                "best": "cue_best",
                "top_n": "cue_top_n",
                "absent": "cue_absent",
            }.get(_endorsement, "cue_absent")
            _played_cp_loss_cue = int(
                inputs.cp_loss if inputs.mover_is_user else (inputs.opp_cp_loss or 0)
            ) or 0
            if _endorsement == "absent" and _played_cp_loss_cue < 30:
                pass
            else:
                principle_cue = _entry.get(_cue_key) or _entry.get("cue_absent") or ""
                principle_id_used = _top_pid
    if principle_cue:
        caption_facts["principle_cue"] = principle_cue
    if principle_id_used:
        caption_facts["principle_id_used"] = principle_id_used

    # ─── 9d. A6 shape pattern selection (post-push board) ────────
    # V5 service runs this AFTER board.push(move). We construct
    # post_move_board here from board_before + played_move.
    try:
        post_move_board = board_before.copy()
        post_move_board.push(played_move)
    except Exception:
        post_move_board = board_before
    # State-threading parity with V5 inline. V5's A6 call site has
    # `prev_move` local that's been reassigned to `move` (current)
    # at line 3666 BEFORE A6 fires at line 3678 — so V5's
    # `prev_move=prev_move` is effectively `prev_move=current_move`.
    # The shape detector's pre-move branch uses this as a context hint;
    # passing played_move replicates V5 inline behaviour.
    _shape_eval_data = {"best_move_uci": inputs.best_move_uci or ""}
    _shape_gate_severity = severity_override if severity_override else canonical.user_facing_tier
    shape_pattern_record = select_shape_pattern_record(
        fen_before=inputs.fen_before,
        board=post_move_board,
        move=played_move,
        move_san=inputs.played_san,
        prev_move=played_move,
        eval_data=_shape_eval_data,
        pv_after_played=list(inputs.pv_after_played),
        severity=_shape_gate_severity,
        full_move_number=inputs.full_move_number,
        shapes_fired_this_game=_shapes,
    )

    # ─── 10. A5 trap recognition state machine ───────────────────
    _played_so_far = list(inputs.move_history_san) + [inputs.played_san]
    trap_record, new_active_trap, new_setup_completed, new_step_cursor = (
        update_trap_recognition_state(
            played_san_so_far=_played_so_far,
            move_san=inputs.played_san,
            is_user=bool(inputs.mover_is_user),
            user_color=inputs.user_color,
            full_move_number=inputs.full_move_number,
            active_trap=state.active_trap,
            active_trap_setup_completed_by_user=state.active_trap_setup_completed_by_user,
            active_trap_step_cursor=state.active_trap_step_cursor,
        )
    )

    # ─── 11. A9 promotion ladder dispatch ────────────────────────
    apply_promotion_ladder_dispatch(
        caption_payload=caption_payload,
        caption_facts=caption_facts,
        trap_record=trap_record,
        opening_record=opening_record,  # V5 passes via kwarg; PWC passes None
        shape_pattern_record=shape_pattern_record,
        move_san=inputs.played_san,
        is_user=bool(inputs.mover_is_user),
        cp_loss=int(inputs.cp_loss or 0),
        best_move=inputs.best_move_san,
        principle_cue=caption_facts.get("principle_cue") or "",
        principle_id_used=caption_facts.get("principle_id_used"),
        full_move_number=inputs.full_move_number,
    )

    # ─── 12. A8 caption tier classification ──────────────────────
    tier = classify_caption_tier(
        caption_text=caption_payload.get("caption") or "",
        rule_name=caption_payload.get("rule_name") or "",
    )

    # ─── Build the decision ──────────────────────────────────────
    text = TextSurface(
        caption=caption_payload.get("caption") or "",
        rule_name=caption_payload.get("rule_name") or "R_FALLBACK",
    )
    # V5 move_output reads from caption_payload (renderer output),
    # NOT caption_facts. Match that source for zero-diff parity.
    visual = VisualSurface(
        arrows=caption_payload.get("arrows") or [],
        highlight_squares=caption_payload.get("highlight_squares") or [],
    )
    teaching_meta = TeachingMeta(
        severity=canonical.user_facing_tier,
        severity_canonical=practical.canonical_tier,
        severity_practical=practical.practical_tier,
        caption_tier=tier,
        has_teaching_content=(tier == "HIGH"),
        principle_id_used=caption_facts.get("principle_id_used"),
        principle_cue=caption_facts.get("principle_cue") or "",
        shape_pattern_id=(shape_pattern_record or {}).get("pattern_id"),
        shape_pattern_name=(shape_pattern_record or {}).get("pattern_name"),
        shape_pattern_desc=(shape_pattern_record or {}).get("pattern_desc"),
        shape_pattern_targets=(shape_pattern_record or {}).get("targets") or [],
        shape_pattern_mover=(shape_pattern_record or {}).get("mover"),
        shape_pattern_executing_move=(shape_pattern_record or {}).get("executing_move"),
        mover_winprob_before=practical.mover_winprob_before,
        mover_winprob_after=practical.mover_winprob_after,
        mover_winprob_delta=practical.winprob_delta,
        mover_state_before=practical.state_before,
        mover_state_after=practical.state_after,
        stayed_winning=practical.stayed_winning,
        decisiveness_changed=practical.decisiveness_changed,
    )
    state_mutations = StateMutations(
        fired_principles_added=_fired_principles_added,
        fired_state_keys_added=_fired_state_keys_added,
        active_trap_after=new_active_trap,
        active_trap_cleared=(state.active_trap is not None and new_active_trap is None),
        active_trap_step_cursor_after=new_step_cursor,
        active_trap_setup_completed_by_user_after=new_setup_completed,
        prev_user_eval_after=(inputs.eval_after_cp if inputs.mover_is_user else state.prev_user_eval_after),
    )

    return MoveTeachingDecision(
        text=text,
        visual=visual,
        teaching_meta=teaching_meta,
        state_mutations=state_mutations,
        debug_facts=caption_facts,
        trap_record=trap_record,
        shape_pattern_record=shape_pattern_record,
        should_skip=False,
        skip_reason="",
    )
