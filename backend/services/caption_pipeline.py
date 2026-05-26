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
        "opp_user_reply_tactic_kind",
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
    if any(caption_facts.get(_k) for _k in _concrete_fact_keys):
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
    if (
        shape_pattern_record is None
        and _detect_all_shapes is not None
        and _SHAPE_PATTERNS_BY_ID is not None
        and _verify_shapes_with_engine is not None
        and severity in ("mistake", "blunder", "opp_mistake", "opp_blunder")
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
) -> MoveTeachingDecision:
    """Compute the full teaching decision for ONE move.

    Returns a fresh MoveTeachingDecision. Callers apply state_mutations
    to their CrossMoveState (atomically for PWC).

    EXTRACTION STATUS (2026-05-26):
      The body is currently EMPTY — this is the dataclass-contract step.
      Subsequent commits will move logic from game_decryption_v5_service
      per-move loop into this function, ONE block at a time, verifying
      zero-diff with scripts/snapshot_captions.py after each.

      Until the migration is complete, V5 service per-move loop still
      contains the brain. live_v5_teaching still uses its subset. PWC
      gains nothing from this module YET.
    """
    raise NotImplementedError(
        "build_move_teaching_decision is the v100 extraction target. "
        "Migration in progress per services/caption_pipeline.py docstring. "
        "Today's V5 brain still lives in game_decryption_v5_service.py."
    )
