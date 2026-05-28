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

    # ─── PWC coach-move narration context (2026-05-26 migration off
    # smart_coaching.py per [[one-source-of-truth-for-coaching]]).
    # Set ONLY by routes/coach_play.py when the engine plays a move
    # and we want the central layer to produce the structured PWC
    # `coach_move_coaching` payload. None for V5 review and for PWC
    # user-side moves — those don't need coach-narration semantics.
    #
    # Expected shape (mirrors what shared_coaching_v5.generate_coach_
    # move_explanation reads today):
    #   {
    #     "v2": True,                            # gate flag
    #     "teaching_goal": "hanging_piece_punishment" | "fork_opportunity"
    #                    | "threat_awareness" | "opening_guidance",
    #     "why_instructive": str,                # short reason string
    #     "v2_breakdown": {"sub_scores": {...}}, # detailed v2 metric
    #     "v2_label": str,                       # short label for UI
    #   }
    coach_move_context: Optional[Dict[str, Any]] = None

    # ─── PWC user-mistake Socratic context (2026-05-27 migration off
    # smart_coaching.generate_smart_user_feedback per
    # [[one-source-of-truth-for-coaching]]). Set ONLY by
    # routes/coach_play.py:2713 when the USER played a move and
    # we want the central layer to produce the structured PWC
    # `socratic_question` / `socratic_hint` / `narrative` /
    # `focus_plan` payload that drives the post-mistake coaching panel.
    # None for V5 review, PWC coach moves, and PWC user moves that
    # aren't mistakes — those don't need Socratic semantics.
    #
    # Expected shape (mirrors generate_smart_user_feedback's inputs):
    #   {
    #     "severity": "mistake" | "blunder",  # gate flag
    #     "fundamental_violated": str | None,  # hanging_pieces, ...
    #     "coach_intent": str | None,          # hanging_piece_punishment,...
    #     "phase": "opening" | "middlegame" | "endgame",
    #   }
    socratic_context: Optional[Dict[str, Any]] = None


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
class CoachExtras:
    """Structured multi-field payload the PWC `coach_move_coaching`
    surface consumes. Frontend `CoachPlay.jsx:1344-1462` reads these.

    Populated ONLY when MoveInputs.coach_move_context is set (i.e., this
    move is the engine's move in a PWC live session and the caller asked
    for coach-narration). For all other contexts (V5 review, PWC user
    side) this stays None on the MoveTeachingDecision and the caller
    ignores it.

    Architectural note (2026-05-26): this dataclass exists so the
    central layer can produce the same rich shape that smart_coaching.py
    produces today, WITHOUT the LLM hallucination risk. Per
    [[one-source-of-truth-for-coaching]] the goal is to delete
    smart_coaching.py entirely once this path is wired and verified.

    Field semantics mirror smart_coaching.py / shared_coaching_v5.
    generate_coach_move_explanation return shape:
      - explanation: primary caption ("Nxe5 captures the undefended pawn.")
      - plan: what the user should think about next ("Always check ...")
      - threats: specific concrete threats the move creates
      - teaching_point: universal principle reinforcement
      - hint_for_user: actionable Socratic question for the user
      - opponent_opportunity: when the coach's move left something the
        student can exploit, describe it; else None.
      - v2_intent / v2_label: pass-through from coach_move_context for
        the UI badge.
    """
    move_san: str = ""
    explanation: str = ""
    plan: str = ""
    threats: List[str] = field(default_factory=list)
    teaching_point: str = ""
    hint_for_user: str = ""
    opponent_opportunity: Optional[Dict[str, Any]] = None
    v2_intent: Optional[str] = None
    v2_label: Optional[str] = None


@dataclass
class SocraticExtras:
    """Structured multi-field payload for PWC user-mistake coaching.
    Mirrors the dict shape that smart_coaching.generate_smart_user_
    feedback returns today (consumed by routes/coach_play.py:2734-
    2762 as socratic_question / socratic_hint / narrative / focus_plan).

    Populated ONLY when MoveInputs.socratic_context is set AND the
    R18_socratic_user_mistake.json suppression gates don't fire
    (cp_loss<80, user-addresses-threat, known opening theory). When
    populated, frontend renders the post-mistake coaching panel.

    Architectural note (2026-05-27): this exists so the central layer
    can produce the user-mistake Socratic shape deterministically,
    matching the migration pattern of CoachExtras (PR-1 through PR-5,
    commits c226d142 → abbd7f88). Per [[one-source-of-truth-for-
    coaching]] the goal is to delete smart_coaching.py entirely once
    this path is wired and verified.

    Field semantics:
      - narrative: 1-2 sentences naming what went wrong + habit to build
      - plan: what to focus on for the next 2-3 moves (drives the UI's
              "active coach plan" persistence in coach_sessions)
      - question: one Socratic question (< 20 words)
      - hint: one-sentence hint when the student can't answer
    """
    narrative: str = ""
    plan: str = ""
    question: str = ""
    hint: str = ""


@dataclass
class MoveTeachingDecision:
    """The complete teaching product for one move.

    Caller responsibilities:
      - Persist `text` + `visual` to the move record / coach_messages
      - Apply `state_mutations` to CrossMoveState (atomically for PWC)
      - Use `teaching_meta` for downstream consumers (UI, audit, classifier)
      - Pass `debug_facts` to admin UI / authoring tools (do NOT use for
        rendering — it's the post-extract facts dict for inspection only)
      - When `coach_extras` is populated, persist it as the PWC
        `coach_move_coaching` payload (frontend `CoachPlay.jsx`).
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
    # PWC coach-move narration payload (2026-05-26 migration). Populated
    # ONLY when MoveInputs.coach_move_context is set; None otherwise.
    # See CoachExtras docstring for field semantics.
    coach_extras: Optional[CoachExtras] = None
    # PWC user-mistake Socratic payload (2026-05-27 migration). Populated
    # ONLY when MoveInputs.socratic_context is set AND the R18 gates
    # don't suppress (cp_loss<80, threat-handling, opening theory).
    # See SocraticExtras docstring for field semantics.
    socratic_extras: Optional[SocraticExtras] = None


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

    # 6b. Missed capture (Mohit fb_ee2ec3abeffd 2026-05-27).
    # When best_move is a CAPTURE that didn't trigger missed_tactic_kind=
    # piece_capture (i.e. small material gain like a pawn), stamp the
    # captured piece + square so why_user_missed_capture can render the
    # real teaching ("Bxc5 wins the pawn on c5") instead of letting
    # positional detectors like defensive_pawn_push fire generic advice.
    # Skipped when missed_tactic_kind already produced piece-level
    # detail — those higher-priority variants render finer-grained
    # captions ("wins the queen on d8").
    if (best_move and "x" in best_move
            and not caption_facts.get("missed_tactic_target_piece")):
        try:
            _board_cap = chess.Board(fen_before)
            _best_mv = _board_cap.parse_san(best_move)
            if _board_cap.is_capture(_best_mv):
                # En-passant: captured pawn isn't on the destination
                # square — locate it one rank behind.
                if _board_cap.is_en_passant(_best_mv):
                    _captured = chess.Piece(chess.PAWN, not _board_cap.turn)
                else:
                    _captured = _board_cap.piece_at(_best_mv.to_square)
                if _captured is not None:
                    caption_facts["missed_capture_target_piece"] = (
                        chess.piece_name(_captured.piece_type)
                    )
                    caption_facts["missed_capture_target_square"] = (
                        chess.square_name(_best_mv.to_square)
                    )
                    # Sac-awareness (fb_6f2a5ba1f626 reused for R12 why-
                    # clauses): when the BEST move is a capture whose
                    # attacker is worth MORE than the target AND the
                    # destination is defended after the capture, the
                    # best move is a SACRIFICE, not a 'wins the piece'
                    # win. R12 needs this so 'Nxh3+ was better — captures
                    # the pawn on h3. Material won is leverage…' stops
                    # firing on knight sacrifices.
                    _PIECE_VAL = {
                        chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3,
                        chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 100,
                    }
                    _attacker_piece = _board_cap.piece_at(_best_mv.from_square)
                    _att_val = _PIECE_VAL.get(_attacker_piece.piece_type, 0) if _attacker_piece else 0
                    _tgt_val = _PIECE_VAL.get(_captured.piece_type, 0)
                    if _att_val > _tgt_val:
                        _board_post = _board_cap.copy()
                        _board_post.push(_best_mv)
                        _opp = not _board_cap.turn
                        if _board_post.attackers(_opp, _best_mv.to_square):
                            caption_facts["best_move_is_sacrifice"] = True
                            caption_facts["best_move_sac_attacker_piece"] = (
                                chess.piece_name(_attacker_piece.piece_type)
                                if _attacker_piece else "piece"
                            )
                            # Near-king sac: target within 2 squares of enemy king.
                            _enemy_king = _board_cap.king(_opp)
                            if _enemy_king is not None:
                                _dist = chess.square_distance(_best_mv.to_square, _enemy_king)
                                if _dist <= 2 and _captured.piece_type == chess.PAWN:
                                    caption_facts["best_move_sac_near_king"] = True
        except Exception:
            pass

    # 6c. "Played took the same piece without check" (Parth fb_0900360fd0e4:
    # 'also explain why bxf3 doesn't work'). Stamped UNCONDITIONALLY when
    # the played move and the engine's best move both capture the SAME
    # square AND best delivers check while played doesn't — even when a
    # higher-priority capture-family fact already fired (missed_tactic,
    # discovered_vac, etc.). Surfaced as a trailing clause appended by
    # build_move_teaching_decision so the existing rich why-clauses keep
    # their main content.
    if best_move and move_san and "x" in best_move and "x" in move_san:
        try:
            _board_pwc = chess.Board(fen_before)
            _b_mv = _board_pwc.parse_san(best_move)
            _p_mv = _board_pwc.parse_san(move_san)
            if (_b_mv.to_square == _p_mv.to_square
                    and (best_move.endswith("+") or best_move.endswith("#"))
                    and not move_san.endswith("+")
                    and not move_san.endswith("#")):
                caption_facts["played_capture_misses_check"] = True
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
        "missed_capture_target_piece",  # Mohit fb_ee2ec3abeffd (2026-05-27)
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


def inject_coach_move_facts(
    caption_facts: Dict[str, Any],
    *,
    board_before: chess.Board,
    move: chess.Move,
    user_color: str,
    coach_move_context: Optional[Dict[str, Any]],
) -> None:
    """Stamp the deterministic facts the central layer needs to produce
    PWC `coach_move_coaching` payload — the structured shape that
    `smart_coaching.generate_smart_coach_explanation` produces today via
    an LLM call (and hallucinates on, per fb_bb79d2445dc1).

    Mohit 2026-05-26: "the coach move should also come from the central
    layer, i can't afford to have 2 sources." See
    [[one-source-of-truth-for-coaching]].

    No-op when coach_move_context is None. Otherwise stamps:
      - coach_move_is_active: True (gate flag for downstream)
      - coach_intent: v2 teaching_goal label (may be None when no v2)
      - coach_v2_label: pass-through UI badge
      - coach_v2_why: short reason string from v2 selector
      - coach_v2_sub_scores: dict of v2 sub-metrics (capture_punishment,
        undefended, attacks_undefended, etc.)
      - coach_attack_targets: list of {piece, square, defender_count}
        for opp pieces the moved piece now attacks
      - coach_target_was_undefended: True iff the move was a capture and
        the captured square had no defenders BEFORE the move (free piece)
      - coach_was_castling: True iff the move was castling
      - coach_castling_side: "kingside" / "queenside" / None
      - student_can_exploit: dict of post-move opportunities for student
        (hanging coach pieces, available forks). Empty dict when nothing.

    Gate semantics (post-PR-5 2026-05-26):
      - coach_move_context is None  -> no-op (V5 review path).
      - coach_move_context is dict  -> R17 fires. When the dict has
        v2:True, the intent variants apply. When v2 is missing/False
        the deterministic facts still flow through and R17 picks the
        terminal coach_quiet_repositioning variant.

    Per [[one-source-of-truth-for-coaching]]: every PWC engine move
    must produce narration deterministically, even without a v2
    teaching signal. The terminal R17 variant + the board-state-aware
    fact stamping below ensures coverage.

    Pure function. Mutates caption_facts in place. No side effects.
    """
    if coach_move_context is None:
        return

    caption_facts["coach_move_is_active"] = True
    caption_facts["coach_intent"] = coach_move_context.get("teaching_goal") or None
    caption_facts["coach_v2_label"] = coach_move_context.get("v2_label") or None
    caption_facts["coach_v2_why"] = coach_move_context.get("why_instructive") or ""
    breakdown = coach_move_context.get("v2_breakdown") or {}
    sub = breakdown.get("sub_scores") if isinstance(breakdown, dict) else None
    caption_facts["coach_v2_sub_scores"] = sub if isinstance(sub, dict) else {}

    coach_color = board_before.piece_at(move.from_square)
    coach_color = coach_color.color if coach_color else None
    student_color = chess.WHITE if user_color == "white" else chess.BLACK

    # Castling — record side for template selection.
    is_castling = board_before.is_castling(move)
    caption_facts["coach_was_castling"] = is_castling
    if is_castling:
        side = "kingside" if chess.square_file(move.to_square) > 4 else "queenside"
        caption_facts["coach_castling_side"] = side
    else:
        caption_facts["coach_castling_side"] = None

    # Was the captured square undefended BEFORE the move? Free piece
    # vs trade is a core teaching distinction smart_coaching surfaces
    # via SEE; we expose it as a boolean for template predicates.
    target_was_undefended = False
    if board_before.is_capture(move) and not board_before.is_en_passant(move):
        defenders = board_before.attackers(
            not coach_color, move.to_square
        ) if coach_color is not None else chess.SquareSet()
        # Filter out the captured piece itself (its own square defends
        # nothing relevant for this question).
        defenders.discard(move.to_square)
        target_was_undefended = len(defenders) == 0
    caption_facts["coach_target_was_undefended"] = target_was_undefended

    # What does the moved piece NOW attack? Compute post-move attack set
    # against opp (student) non-king pieces, with defender counts so the
    # template can distinguish "free attack" from "pressure on defended".
    board_after = board_before.copy()
    try:
        board_after.push(move)
    except Exception:
        # Shouldn't happen — move was already validated by extract_facts.
        # Defensive: stamp empties and bail.
        caption_facts["coach_attack_targets"] = []
        caption_facts["student_can_exploit"] = {}
        return

    # Piece values for the "is this a REAL threat?" filter below.
    _PIECE_VAL = {
        chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3,
        chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 100,
    }
    coach_attack_targets: List[Dict[str, Any]] = []
    if coach_color is not None:
        moved_piece_after = board_after.piece_at(move.to_square)
        moved_val = _PIECE_VAL.get(
            moved_piece_after.piece_type, 0) if moved_piece_after else 0
        moved_attacks = board_after.attacks(move.to_square)
        for target_sq in moved_attacks:
            target_piece = board_after.piece_at(target_sq)
            if (target_piece is None
                    or target_piece.color == coach_color
                    or target_piece.piece_type == chess.KING):
                continue
            defenders = board_after.attackers(student_color, target_sq)
            attackers = board_after.attackers(coach_color, target_sq)
            target_val = _PIECE_VAL.get(target_piece.piece_type, 0)
            # Only narrate a REAL threat. A target is genuinely threatened
            # iff it is undefended (can simply be taken) OR the attacking
            # piece is worth <= the target (a lower/equal-value attacker
            # forces the target to move or be lost in the trade). A more-
            # valuable piece "attacking" a DEFENDED lesser piece wins
            # nothing — e.g. a queen attacking a thrice-defended pawn is
            # NOT a threat, just geometry. Stamping it as an "attack"
            # produced false coach captions ("Qg5 — attacks your pawn on
            # d2") that students correctly reject. fb_fa7db491c527.
            is_real_threat = (len(defenders) == 0) or (moved_val <= target_val)
            if not is_real_threat:
                continue
            coach_attack_targets.append({
                "piece": chess.piece_name(target_piece.piece_type),
                "square": chess.square_name(target_sq),
                "defender_count": len(defenders),
                "attacker_count": len(attackers),
            })
    caption_facts["coach_attack_targets"] = coach_attack_targets

    # What can the STUDENT exploit? Hanging coach pieces, fork chances.
    # Reuses the existing pattern_detectors module — same primitives
    # smart_coaching._scan_opportunities calls today (lines 1129-1149).
    student_opportunities: Dict[str, Any] = {}
    try:
        from coach_play.teaching.pattern_detectors import (
            find_hanging_pieces, find_fork_opportunities,
        )
        if coach_color is not None:
            hanging, underdefended = find_hanging_pieces(
                board_after, victim_color=coach_color
            )
            if hanging:
                student_opportunities["coach_hanging_pieces"] = [
                    {"piece": chess.piece_name(h.piece_type),
                     "square": chess.square_name(h.square)}
                    for h in hanging
                ]
            if underdefended:
                student_opportunities["coach_underdefended_pieces"] = [
                    {"piece": chess.piece_name(h.piece_type),
                     "square": chess.square_name(h.square)}
                    for h in underdefended
                ]
            forks = find_fork_opportunities(
                board_after, forker_color=student_color
            )
            if forks:
                student_opportunities["student_fork_chance_count"] = len(forks)
    except Exception:
        # pattern_detectors is best-effort; if it crashes we just don't
        # populate student_can_exploit. Template falls back gracefully.
        pass
    caption_facts["student_can_exploit"] = student_opportunities


def inject_good_move_reason_facts(
    caption_facts: Dict[str, Any],
    *,
    board_before: chess.Board,
    move: chess.Move,
    move_san: str,
    mover_is_user: bool,
    cp_loss: int,
    best_move_san: Optional[str],
    phase: str,
) -> None:
    """Stamp a SAFE, deterministic 'why' for a user move that equals the
    engine's best (cp_loss == 0) so R15_good_move can teach instead of just
    asserting "strongest move here." Parth fb_ba9db31ae393: "Best move. but
    why?"

    Cardinal rule (a wrong reason is worse than a terse one): only stamp a
    reason when it is UNAMBIGUOUS from the board. Categories, first match:
      - capture       : names the piece taken (always literally true)
      - central_break : a pawn pushed to a central square that attacks an
                        enemy pawn — contesting the center
      - develop       : opening only, a minor piece leaving its back rank
      - (none)        : leave unset → R15 falls back to "strongest move here"

    Leaves `good_move_reason` unset for everything else (quiet maneuvers,
    king walks, prophylaxis, rook lifts) — those have no safe one-line why.
    """
    caption_facts.setdefault("good_move_reason", None)
    if not mover_is_user:
        return
    # R15 territory: user move with cp_loss < 30 (near-best). Yellow-
    # bucket extension 2026-05-28: was previously gated on
    # 'played == best AND cp_loss == 0', which left near-best moves
    # (cpl 1-29) silent. Now fires for any near-best user move; R15's
    # default still only renders 'strongest move here' when cpl == 0.
    if int(cp_loss or 0) >= 30:
        return

    mover_color = board_before.turn

    # 1) Capture — name what was taken. Literally true even for trades/sacs;
    #    we only claim "takes", never "wins material".
    try:
        if board_before.is_en_passant(move):
            caption_facts["good_move_reason"] = "capture"
            caption_facts["good_move_captured_piece"] = "pawn"
            caption_facts["good_move_captured_square"] = chess.square_name(move.to_square)
            return
        if board_before.is_capture(move):
            cap = board_before.piece_at(move.to_square)
            if cap is not None:
                caption_facts["good_move_reason"] = "capture"
                caption_facts["good_move_captured_piece"] = chess.piece_name(cap.piece_type)
                caption_facts["good_move_captured_square"] = chess.square_name(move.to_square)
                return
    except Exception:
        pass

    moved = board_before.piece_at(move.from_square)
    if moved is None:
        return

    # 2) Central pawn break — a pawn pushed to a central file (c-f) on the
    #    4th+ rank that attacks an enemy pawn. Contests the center.
    if moved.piece_type == chess.PAWN:
        to_file = chess.square_file(move.to_square)   # 0=a .. 7=h
        to_rank = chess.square_rank(move.to_square)   # 0=rank1 .. 7=rank8
        central_file = to_file in (2, 3, 4, 5)        # c, d, e, f
        advanced = (
            (mover_color == chess.WHITE and to_rank >= 3)  # rank 4+
            or (mover_color == chess.BLACK and to_rank <= 4)  # rank 5-
        )
        if central_file and advanced:
            try:
                after = board_before.copy()
                after.push(move)
                hits_enemy_pawn = any(
                    (p := after.piece_at(sq)) is not None
                    and p.color != mover_color and p.piece_type == chess.PAWN
                    for sq in after.attacks(move.to_square)
                )
            except Exception:
                hits_enemy_pawn = False
            if hits_enemy_pawn:
                caption_facts["good_move_reason"] = "central_break"
                return

    # 3) Bishop-pair trade offer (Parth fb_bdff53b7e4d9). A bishop moves
    # to attack an enemy bishop AND opponent has the bishop pair (one
    # bishop on each square colour). Trading removes that advantage —
    # a concrete principle a 600-1500 player can apply going forward.
    if moved.piece_type == chess.BISHOP:
        enemy_color = not mover_color
        enemy_bishops = list(board_before.pieces(chess.BISHOP, enemy_color))
        if len(enemy_bishops) >= 2:
            # Square colour parity: a1=(0,0)=0=dark; odd sum = light.
            has_light = any(
                (chess.square_file(s) + chess.square_rank(s)) % 2 == 1
                for s in enemy_bishops
            )
            has_dark = any(
                (chess.square_file(s) + chess.square_rank(s)) % 2 == 0
                for s in enemy_bishops
            )
            if has_light and has_dark:
                # Does the moved bishop now attack one of those bishops?
                try:
                    after = board_before.copy()
                    after.push(move)
                except Exception:
                    after = None
                if after is not None:
                    for sq in after.attacks(move.to_square):
                        target = after.piece_at(sq)
                        if (target is not None
                                and target.color == enemy_color
                                and target.piece_type == chess.BISHOP):
                            sq_parity = (chess.square_file(sq) + chess.square_rank(sq)) % 2
                            color_name = "light" if sq_parity == 1 else "dark"
                            caption_facts["good_move_reason"] = "bishop_pair_trade"
                            caption_facts["good_move_trade_target_color"] = color_name
                            return

    # 4) Controls key squares (Parth fb_b250249f7724 / fb_fa464cae3b84):
    # the move puts a piece on a square that attacks one or more KEY
    # central / semi-central squares. Captures Parth's "c6 controls b5
    # and d5" pattern. Two safety thresholds:
    #   PAWN: attacks >= 1 KEY square — pawn structure is permanent, so
    #     "controls X" is meaningful even if another piece also covers
    #     X (the pawn locks the square in).
    #   PIECE (knight/bishop/rook/queen): attacks >= 2 KEY squares
    #     NEWLY (not already covered by the user before the move) — for
    #     mobile pieces, "controls" only teaches when it's a NEW
    #     positional gain. Avoids the queen-moves-but-still-attacks-its-
    #     own-old-square artifact.
    # Skip captures and checks (those moves have their own stories).
    try:
        if board_before.is_capture(move) or board_before.gives_check(move):
            pass  # skip — capture/check have their own caption stories
        else:
            # Central + semi-central squares (rank 4-5, files c-f).
            _KEY_SQUARES = [
                chess.square(f, r) for f in (2, 3, 4, 5) for r in (3, 4)
            ]
            after = board_before.copy()
            after.push(move)
            now_attacks = set(after.attacks(move.to_square))
            controlled: List[str] = []
            if moved.piece_type == chess.PAWN:
                # Pawn rule: just attack >= 1 key square (no "newly" filter).
                for ksq in _KEY_SQUARES:
                    if ksq not in now_attacks:
                        continue
                    occupant = after.piece_at(ksq)
                    if occupant is not None and occupant.color == mover_color:
                        continue  # we already own that square
                    controlled.append(chess.square_name(ksq))
                _min_required = 1
            else:
                # Piece rule: >= 2 NEWLY attacked key squares.
                before_user_attacks = set()
                for sq in chess.SQUARES:
                    p = board_before.piece_at(sq)
                    if p is not None and p.color == mover_color:
                        before_user_attacks |= set(board_before.attacks(sq))
                for ksq in _KEY_SQUARES:
                    if ksq not in now_attacks:
                        continue
                    if ksq in before_user_attacks:
                        continue  # already controlled
                    occupant = after.piece_at(ksq)
                    if occupant is not None and occupant.color == mover_color:
                        continue
                    controlled.append(chess.square_name(ksq))
                _min_required = 2
            if len(controlled) >= _min_required:
                caption_facts["good_move_reason"] = "controls_key_squares"
                caption_facts["good_move_controlled_squares"] = ", ".join(controlled)
                return
    except Exception:
        pass

    # 5) Supports own central pawn (Parth fb_dc63587ede08-class). Move
    # adds a defender to a CENTRAL user pawn (d4/e4 for white,
    # d5/e5 for black) that was previously UNDEFENDED. Conservative:
    # only fires when defender count goes 0 -> 1, so we celebrate the
    # FIRST defender (real teaching) and not over-protection 1->2 or
    # queen relocations that just shuffle which piece defends.
    try:
        if not (board_before.is_capture(move) or board_before.gives_check(move)):
            central_pawn_squares = (
                (chess.D4, chess.E4) if mover_color == chess.WHITE
                else (chess.D5, chess.E5)
            )
            after = board_before.copy()
            after.push(move)
            for pawn_sq in central_pawn_squares:
                p = after.piece_at(pawn_sq)
                if (p is None or p.piece_type != chess.PAWN
                        or p.color != mover_color):
                    continue
                before_defenders = board_before.attackers(mover_color, pawn_sq)
                # The pawn itself doesn't count as its own defender.
                before_defenders.discard(pawn_sq)
                after_defenders = after.attackers(mover_color, pawn_sq)
                after_defenders.discard(pawn_sq)
                if len(before_defenders) == 0 and len(after_defenders) >= 1:
                    # Newly defended. Confirm the played move IS the new
                    # defender (avoid edge cases where some other piece
                    # happened to start defending — unlikely but defensive).
                    if move.to_square in after_defenders:
                        caption_facts["good_move_reason"] = "supports_central_pawn"
                        caption_facts["good_move_supported_pawn_square"] = chess.square_name(pawn_sq)
                        return
    except Exception:
        pass

    # 6) Connects rooks. Move clears the user's back rank between two
    # rooks: before the move there WAS at least one user piece on the
    # back rank between the two rooks; after, the squares are clear and
    # the rooks see each other. Edge case but cleanly verifiable.
    try:
        if not board_before.is_capture(move):
            back_rank = 0 if mover_color == chess.WHITE else 7
            # Move's from-square must be on the back rank (otherwise
            # clearing it isn't possible).
            if chess.square_rank(move.from_square) == back_rank:
                after = board_before.copy()
                after.push(move)
                rooks_before = [
                    sq for sq in board_before.pieces(chess.ROOK, mover_color)
                    if chess.square_rank(sq) == back_rank
                ]
                rooks_after = [
                    sq for sq in after.pieces(chess.ROOK, mover_color)
                    if chess.square_rank(sq) == back_rank
                ]
                # Need exactly 2 rooks on the back rank both before and
                # after — moving one of the rooks itself breaks the
                # connection rather than enabling it.
                if len(rooks_before) == 2 and len(rooks_after) == 2 and rooks_before == rooks_after:
                    lo, hi = sorted(rooks_before)
                    files_between = range(
                        chess.square_file(lo) + 1, chess.square_file(hi)
                    )
                    def _any_user_piece_between(b):
                        for f in files_between:
                            sq = chess.square(f, back_rank)
                            p = b.piece_at(sq)
                            if p is not None and p.color == mover_color:
                                return True
                        return False
                    if _any_user_piece_between(board_before) and not _any_user_piece_between(after):
                        caption_facts["good_move_reason"] = "connects_rooks"
                        return
    except Exception:
        pass

    # 7) Development in the opening — a minor piece leaving its back rank.
    # Falls through here only when the controls-key-squares branch above
    # didn't produce a 2+-key-square hit, so develop stays as the generic
    # fallback for opening minor-piece moves.
    if phase == "opening" and moved.piece_type in (chess.KNIGHT, chess.BISHOP):
        back_rank = 0 if mover_color == chess.WHITE else 7
        if (chess.square_rank(move.from_square) == back_rank
                and chess.square_rank(move.to_square) != back_rank):
            caption_facts["good_move_reason"] = "develop"
            return


def inject_socratic_user_facts(
    caption_facts: Dict[str, Any],
    *,
    board_before: chess.Board,
    move: chess.Move,
    user_color: str,
    cp_loss: int,
    pv_after_played: Optional[List[str]],
    move_history_san: Optional[List[str]],
    user_rating: int,
    socratic_context: Optional[Dict[str, Any]],
) -> None:
    """Stamp the deterministic facts the central layer needs to produce
    the PWC socratic_question / socratic_hint / narrative / focus_plan
    payload — the structured shape that smart_coaching.generate_smart_
    user_feedback produces today via an LLM call.

    Mohit 2026-05-27: "use same direction" — same migration pattern
    as the coach-move surface (PR-1 through PR-5, commits c226d142 →
    abbd7f88). See [[one-source-of-truth-for-coaching]].

    No-op when socratic_context is None OR severity is not in
    ("mistake", "blunder"). Otherwise applies the three pre-routing
    gates from smart_coaching lines 105-160:

      Gate A: cp_loss < 80 → suppress (too small for "stronger move"
              framing — Parth bugs fb_3c558315d3c7 family).
      Gate B: user's move addresses an immediate forcing threat
              (tactical_safety.user_move_addresses_threat).
      Gate C: position is in known opening theory
              (decryption_voice.opening_book.recognize_opening_from_history).

    When ANY gate fires, the helper sets socratic_should_suppress=True
    and does NOT stamp socratic_is_active. The R18 trigger gates on
    socratic_is_active so suppression = no narration. Matches the
    smart_coaching "return None" behaviour exactly.

    When NO gate fires:
      - socratic_is_active: True (R18 trigger flag)
      - socratic_severity: "mistake" | "blunder"
      - socratic_fundamental_violated: pass-through label
      - socratic_coach_intent: pass-through label
      - socratic_phase: pass-through opening/middlegame/endgame
      - socratic_user_rating: pass-through
      - socratic_problem_facts: list of human-readable problem phrases
        (one per fundamental_violated category)
      - socratic_hanging_piece + socratic_hanging_square: when
        fundamental_violated == "hanging_pieces" and a hanging piece
        is found on the post-move board
      - socratic_recovery_facts: list of 1-3 rating-aware phrases
        derived from pv_after_played themes (castle/capture/develop)
      - socratic_opponent_threat_type: "fork" | "mate" | "capture"
        when severity=="blunder" and post-move position exposes a
        concrete threat from move_comparison._find_opponent_threats.
      - socratic_opponent_threat_text: the raw threat phrase
      - socratic_pv_themes: dict {castle, capture, develop, defend}
      - socratic_pv_capture_target: piece-name of the first capture
        target in pv_after_played, if any.

    Pure function. Mutates caption_facts in place. Best-effort gates —
    if a gate detector crashes, the gate is skipped (defensive).
    """
    if socratic_context is None:
        return

    severity = (socratic_context.get("severity") or "").strip().lower()
    if severity not in ("mistake", "blunder"):
        return

    # ─── PRE-ROUTING GATES (mirror smart_coaching 105-160) ────────
    suppress = False
    suppress_reason = ""

    # Gate A: cp_loss too small for "stronger move" framing.
    if cp_loss is not None and cp_loss < 80:
        suppress = True
        suppress_reason = f"cp_loss={cp_loss} below 'stronger move' threshold"

    # Gate B: user's move addresses an immediate forcing threat.
    if not suppress:
        try:
            from services.tactical_safety import user_move_addresses_threat
            if user_move_addresses_threat(board_before, move):
                suppress = True
                suppress_reason = "user move addresses an attacked own piece"
        except Exception:
            pass  # gate detector unavailable; skip

    # Gate C: position is in known opening theory.
    if not suppress and move_history_san is not None:
        try:
            from services.decryption_voice.opening_book import (
                recognize_opening_from_history,
            )
            move_san_check = board_before.san(move)
            full_history = list(move_history_san) + [move_san_check]
            if recognize_opening_from_history(full_history):
                suppress = True
                suppress_reason = "move is part of known opening theory"
        except Exception:
            pass  # gate detector unavailable; skip

    if suppress:
        caption_facts["socratic_should_suppress"] = True
        caption_facts["socratic_suppress_reason"] = suppress_reason
        return

    # ─── PROCEED — stamp facts for R18 rendering ─────────────────
    caption_facts["socratic_is_active"] = True
    caption_facts["socratic_severity"] = severity
    fundamental = socratic_context.get("fundamental_violated") or None
    caption_facts["socratic_fundamental_violated"] = fundamental
    caption_facts["socratic_coach_intent"] = socratic_context.get("coach_intent") or None
    caption_facts["socratic_phase"] = socratic_context.get("phase") or "middlegame"
    caption_facts["socratic_user_rating"] = int(user_rating or 1200)

    # Build problem_facts based on fundamental_violated (mirrors
    # smart_coaching 179-213).
    problem_facts: List[str] = []
    hanging_piece_name: Optional[str] = None
    hanging_square_name: Optional[str] = None

    if fundamental == "check_opponents_move":
        problem_facts.append("Student did not respond to the opponent's threat from the previous move")
    elif fundamental == "hanging_pieces":
        # Look for the user's hanging piece on the POST-move board.
        try:
            user_color_bool = chess.WHITE if user_color == "white" else chess.BLACK
            post = board_before.copy()
            post.push(move)
            for sq in chess.SQUARES:
                p = post.piece_at(sq)
                if (p and p.color == user_color_bool
                        and p.piece_type not in (chess.KING, chess.PAWN)):
                    attackers = list(post.attackers(not user_color_bool, sq))
                    defenders = list(post.attackers(user_color_bool, sq))
                    if attackers and not defenders:
                        hanging_piece_name = chess.piece_name(p.piece_type)
                        hanging_square_name = chess.square_name(sq)
                        problem_facts.append(
                            f"Student's {hanging_piece_name} on "
                            f"{hanging_square_name} is now undefended and attacked"
                        )
                        break
        except Exception:
            pass
        if not problem_facts:
            problem_facts.append("Student left a piece undefended")
    elif fundamental == "calculate":
        problem_facts.append("Student didn't calculate the opponent's response")
    elif fundamental == "king_safety":
        problem_facts.append("Student's king is in danger")
    elif fundamental == "development":
        problem_facts.append("Student moved an already-developed piece instead of developing a new one")
    elif fundamental == "center_control":
        problem_facts.append("Student lost control of the center")
    elif fundamental == "have_a_plan":
        problem_facts.append("Student's move doesn't serve a clear purpose")

    # Coach intent context (when set by the v2 selector).
    coach_intent = caption_facts["socratic_coach_intent"]
    if coach_intent:
        intent_map = {
            "hanging_piece_punishment": "The coach created a position to test piece safety awareness",
            "fork_opportunity": "The coach set up a double attack the student needed to handle",
            "threat_awareness": "The coach created a threat the student needed to notice",
        }
        if coach_intent in intent_map:
            problem_facts.append(intent_map[coach_intent])

    caption_facts["socratic_problem_facts"] = problem_facts
    caption_facts["socratic_hanging_piece"] = hanging_piece_name
    caption_facts["socratic_hanging_square"] = hanging_square_name

    # Recovery plan from PV themes (mirrors smart_coaching 215-298).
    recovery_facts: List[str] = []
    pv_themes = {"castle": False, "capture": False, "develop": False, "defend": False}
    capture_target: Optional[str] = None
    if pv_after_played and len(pv_after_played) >= 2:
        try:
            post = board_before.copy()
            post.push(move)
            sim = post.copy()
            user_color_bool = chess.WHITE if user_color == "white" else chess.BLACK
            for pv_move_san in pv_after_played[:4]:
                try:
                    pv_move = sim.parse_san(pv_move_san)
                    piece = sim.piece_at(pv_move.from_square)
                    is_user_move = (sim.turn == user_color_bool)
                    if is_user_move and piece:
                        if sim.is_castling(pv_move):
                            pv_themes["castle"] = True
                        elif sim.is_capture(pv_move):
                            pv_themes["capture"] = True
                            cap_piece = sim.piece_at(pv_move.to_square)
                            if cap_piece:
                                capture_target = chess.piece_name(cap_piece.piece_type)
                        elif piece.piece_type in (chess.KNIGHT, chess.BISHOP):
                            back_rank = 0 if piece.color == chess.WHITE else 7
                            if chess.square_rank(pv_move.from_square) == back_rank:
                                pv_themes["develop"] = True
                    sim.push(pv_move)
                except Exception:
                    break
        except Exception:
            pass

        # Rating-aware recovery phrasing (matches smart_coaching 250-278).
        if user_rating < 1000:
            if pv_themes["capture"]:
                recovery_facts.append("Look for pieces you can take safely")
            elif pv_themes["castle"]:
                recovery_facts.append("Your king needs to be safe first")
            elif pv_themes["develop"]:
                recovery_facts.append("Bring your pieces into the game")
            else:
                recovery_facts.append("Take a breath and look at the whole board")
        elif user_rating < 1400:
            if pv_themes["capture"] and capture_target:
                recovery_facts.append(f"There's a {capture_target} you can win back")
            if pv_themes["castle"]:
                recovery_facts.append("Get your king safe")
            if pv_themes["develop"]:
                recovery_facts.append("Finish developing your pieces")
            if not recovery_facts:
                recovery_facts.append("Think about what your pieces need right now")
        else:
            if pv_themes["capture"]:
                recovery_facts.append("Can you find a way to win material back?")
            if pv_themes["castle"]:
                recovery_facts.append("Think about king safety")
            if not recovery_facts:
                recovery_facts.append("Calculate the next 2-3 moves carefully")

    # Fallback when no PV: basic position checks (smart_coaching 280-298).
    if not recovery_facts:
        try:
            user_color_bool = chess.WHITE if user_color == "white" else chess.BLACK
            post = board_before.copy()
            post.push(move)
            king_sq = post.king(user_color_bool)
            if king_sq is not None:
                back_rank = 0 if user_color_bool == chess.WHITE else 7
                if (chess.square_rank(king_sq) == back_rank
                        and chess.square_file(king_sq) == 4):
                    recovery_facts.append("Get your king safe — castle")
                undeveloped = 0
                for sq in chess.SQUARES:
                    p = post.piece_at(sq)
                    if (p and p.color == user_color_bool
                            and p.piece_type in (chess.KNIGHT, chess.BISHOP)):
                        if chess.square_rank(sq) == back_rank:
                            undeveloped += 1
                if undeveloped >= 2:
                    recovery_facts.append(
                        f"Develop your {undeveloped} pieces still on the back row"
                    )
        except Exception:
            pass

    caption_facts["socratic_recovery_facts"] = recovery_facts
    caption_facts["socratic_pv_themes"] = pv_themes
    caption_facts["socratic_pv_capture_target"] = capture_target

    # Opponent-threat detection for blunders (mirrors smart_coaching 299-333).
    opp_threat_type: Optional[str] = None
    opp_threat_text: str = ""
    if severity == "blunder":
        try:
            from services.move_comparison import _find_opponent_threats
            try:
                from services.threat_verifier import _get_singleton_engine
                verify_engine = _get_singleton_engine()
            except Exception:
                verify_engine = None
            post = board_before.copy()
            post.push(move)
            user_color_bool = chess.WHITE if user_color == "white" else chess.BLACK
            threats = _find_opponent_threats(
                post, not user_color_bool, engine=verify_engine,
            )
            if threats:
                opp_threat_text = threats[0]
                threat_low = threats[0].lower()
                if "fork" in threat_low:
                    opp_threat_type = "fork"
                elif "checkmate" in threat_low or "mate" in threat_low:
                    opp_threat_type = "mate"
                elif "taken for free" in threat_low or "can be taken" in threat_low:
                    opp_threat_type = "capture"
        except Exception:
            pass
    caption_facts["socratic_opponent_threat_type"] = opp_threat_type
    caption_facts["socratic_opponent_threat_text"] = opp_threat_text


_R17_TEMPLATE: Optional[Dict[str, Any]] = None


def _load_r17_template() -> Dict[str, Any]:
    """Lazy-load R17_coach_move.json, cached process-wide. Returns the
    parsed dict, or empty {} when file missing / invalid (defensive)."""
    global _R17_TEMPLATE
    if _R17_TEMPLATE is not None:
        return _R17_TEMPLATE
    import json
    import os
    # caption_templates.py uses /app/backend/data/captions in container
    # and resolves the path via CAPTIONS_DIR; reuse that path semantics.
    _path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "data", "captions", "R17_coach_move.json",
    )
    try:
        with open(_path, encoding="utf-8") as f:
            _R17_TEMPLATE = json.load(f)
    except Exception as exc:
        logger.warning(f"[caption_pipeline] R17 load failed: {exc}; coach-narration disabled")
        _R17_TEMPLATE = {}
    return _R17_TEMPLATE


def _compute_r17_derived_facts(caption_facts: Dict[str, Any]) -> None:
    """R17 select_variant predicates read a few computed fields that
    aren't in the base facts dict — derive them in-place so the
    predicate matcher sees them. Pure helper, mutates caption_facts."""
    # coach_attack_first_target_* — peel the first entry off the
    # coach_attack_targets list (set by inject_coach_move_facts).
    targets = caption_facts.get("coach_attack_targets") or []
    if targets and isinstance(targets, list) and isinstance(targets[0], dict):
        first = targets[0]
        caption_facts["coach_attack_first_target_piece"] = first.get("piece")
        caption_facts["coach_attack_first_target_square"] = first.get("square")
        caption_facts["coach_attack_first_target_undefended"] = (
            (first.get("defender_count") or 0) == 0
        )
    # coach_v2_sub_* — flatten select keys from the v2 sub_scores dict
    # so the predicate matcher (which expects flat keys) can read them.
    sub = caption_facts.get("coach_v2_sub_scores") or {}
    if isinstance(sub, dict):
        caption_facts["coach_v2_sub_attacks_undefended"] = sub.get("attacks_undefended", 0) or 0
        caption_facts["coach_v2_sub_capture_punishment"] = sub.get("capture_punishment", 0) or 0
        caption_facts["coach_v2_sub_checks"] = sub.get("checks", 0) or 0
        caption_facts["coach_v2_sub_undefended"] = sub.get("undefended", 0) or 0


def _format_r17_field(template_str: str, facts: Dict[str, Any]) -> str:
    """Format an R17 template string with caption_facts. Tolerates
    missing keys — returns the unformatted string rather than raising
    KeyError so a partial fact dict doesn't crash the whole render.
    Mirrors the leniency of caption_templates.render_template."""
    if not template_str:
        return ""
    try:
        # Build a defaulted lookup so missing keys render as empty.
        class _SafeDict(dict):
            def __missing__(self, key):
                return ""
        return template_str.format_map(_SafeDict(facts))
    except Exception:
        return template_str


def populate_coach_extras(caption_facts: Dict[str, Any]) -> Optional["CoachExtras"]:
    """Render the R17_coach_move template into a CoachExtras instance.

    Gate: returns None when coach_move_is_active is not True (i.e., the
    caller did not pass coach_move_context to build_move_teaching_
    decision). Also returns None when the R17 file failed to load.

    Variant selection uses the same evaluate_when predicate the rest
    of the JSON-driven rule engine uses (caption_templates.py).
    Builds threats[] from coach_attack_targets, opponent_opportunity
    from student_can_exploit. v2_intent / v2_label come straight from
    coach_move_context via the facts dict.
    """
    if not caption_facts.get("coach_move_is_active"):
        return None

    cfg = _load_r17_template()
    if not cfg:
        return None

    # Mutate caption_facts in place with derived predicate inputs. Safe
    # because caption_facts is already a working copy from build_move_
    # teaching_decision (V5 service builds a fresh dict per move).
    _compute_r17_derived_facts(caption_facts)

    # Variant selection — reuse the JSON predicate engine.
    try:
        from services.caption_templates import select_first_match
    except Exception:
        logger.exception("[caption_pipeline] caption_templates import failed; R17 disabled")
        return None

    rules = cfg.get("select_variant") or []
    match = select_first_match(rules, caption_facts)
    variant_name = (match or {}).get("variant") if match else None
    if not variant_name:
        # Fallback ordering: explicit terminal {"variant": "coach_quiet_repositioning"}
        # in select_variant should always catch, but guard defensively.
        variant_name = "coach_quiet_repositioning"

    variant_body = (cfg.get("variants") or {}).get(variant_name) or {}
    if not isinstance(variant_body, dict):
        # Schema violation — log and bail.
        logger.warning(
            f"[caption_pipeline] R17 variant {variant_name!r} is not a dict; "
            f"check R17_coach_move.json schema"
        )
        return None

    # Render the four narrative fields.
    explanation = _format_r17_field(variant_body.get("explanation", ""), caption_facts)
    plan = _format_r17_field(variant_body.get("plan", ""), caption_facts)
    teaching_point = _format_r17_field(variant_body.get("teaching_point", ""), caption_facts)
    hint_for_user = _format_r17_field(variant_body.get("hint_for_user", ""), caption_facts)

    # Build threats[] from coach_attack_targets — concrete, grounded
    # claims about what the coach now attacks. Skip targets with zero
    # attacker_count (shouldn't happen but defensive).
    threats: List[str] = []
    for target in caption_facts.get("coach_attack_targets") or []:
        if not isinstance(target, dict):
            continue
        piece = target.get("piece")
        square = target.get("square")
        if not piece or not square:
            continue
        if (target.get("defender_count") or 0) == 0:
            threats.append(f"Attacks your {piece} on {square} (undefended)")
        else:
            threats.append(f"Attacks your {piece} on {square}")

    # opponent_opportunity — surface what the student can exploit.
    # Mirrors smart_coaching's structure so the frontend's existing
    # rendering of `opponent_opportunity` continues to work after the
    # source-of-truth flip in PR-4.
    opportunity_facts = caption_facts.get("student_can_exploit") or {}
    opponent_opportunity: Optional[Dict[str, Any]] = None
    if isinstance(opportunity_facts, dict) and opportunity_facts:
        # Compose a one-line message for the UI; keep the raw structured
        # data alongside so future renderers can use richer formatting.
        parts: List[str] = []
        hanging = opportunity_facts.get("coach_hanging_pieces") or []
        underdef = opportunity_facts.get("coach_underdefended_pieces") or []
        forks = opportunity_facts.get("student_fork_chance_count") or 0
        if hanging:
            names = ", ".join(
                f"{h['piece']} on {h['square']}" for h in hanging
                if isinstance(h, dict) and h.get("piece") and h.get("square")
            )
            if names:
                parts.append(f"Coach has undefended: {names}")
        if underdef:
            names = ", ".join(
                f"{h['piece']} on {h['square']}" for h in underdef
                if isinstance(h, dict) and h.get("piece") and h.get("square")
            )
            if names:
                parts.append(f"Under pressure: {names}")
        if forks:
            parts.append(f"You may have a fork available ({forks} chance{'s' if forks != 1 else ''})")
        if parts:
            opponent_opportunity = {
                "type": "smart",
                "message": "; ".join(parts),
                "details": opportunity_facts,
            }

    return CoachExtras(
        move_san=caption_facts.get("played_san") or "",
        explanation=explanation,
        plan=plan,
        threats=threats,
        teaching_point=teaching_point,
        hint_for_user=hint_for_user,
        opponent_opportunity=opponent_opportunity,
        v2_intent=caption_facts.get("coach_intent"),
        v2_label=caption_facts.get("coach_v2_label"),
    )


_R18_TEMPLATE: Optional[Dict[str, Any]] = None


def _load_r18_template() -> Dict[str, Any]:
    """Lazy-load R18_socratic_user_mistake.json, cached process-wide.
    Returns the parsed dict, or empty {} when file missing / invalid."""
    global _R18_TEMPLATE
    if _R18_TEMPLATE is not None:
        return _R18_TEMPLATE
    import json
    import os
    _path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "data", "captions", "R18_socratic_user_mistake.json",
    )
    try:
        with open(_path, encoding="utf-8") as f:
            _R18_TEMPLATE = json.load(f)
    except Exception as exc:
        logger.warning(f"[caption_pipeline] R18 load failed: {exc}; socratic disabled")
        _R18_TEMPLATE = {}
    return _R18_TEMPLATE


def _compute_r18_derived_facts(caption_facts: Dict[str, Any]) -> None:
    """R18 variant templates reference two joined-string fields that
    aren't directly in the base facts dict — derive them here so the
    template renderer's format_map sees them. Pure helper, mutates
    caption_facts in place.

    The list-to-string join is a defensive separation: variants embed
    the COMPOSED text directly via {socratic_problem_facts_joined},
    avoiding any need for list-rendering inside the JSON template.
    """
    problem_facts = caption_facts.get("socratic_problem_facts") or []
    if isinstance(problem_facts, list):
        caption_facts["socratic_problem_facts_joined"] = "; ".join(
            str(p) for p in problem_facts if p
        )
    else:
        caption_facts["socratic_problem_facts_joined"] = ""

    recovery_facts = caption_facts.get("socratic_recovery_facts") or []
    if isinstance(recovery_facts, list) and recovery_facts:
        # Cap at 3 per smart_coaching's slicing semantics.
        caption_facts["socratic_recovery_facts_joined"] = "; ".join(
            str(p) for p in recovery_facts[:3] if p
        )
    else:
        caption_facts["socratic_recovery_facts_joined"] = ""


def _format_r18_field(template_str: str, facts: Dict[str, Any]) -> str:
    """Format an R18 template string. Tolerates missing keys (matches
    _format_r17_field behaviour) and trims trailing whitespace +
    semicolons that arise when a joined-list slot was empty."""
    if not template_str:
        return ""
    try:
        class _SafeDict(dict):
            def __missing__(self, key):
                return ""
        out = template_str.format_map(_SafeDict(facts))
        # Clean up dangling joiners when a placeholder rendered empty.
        # e.g. "Step one is mate. Address it first. " → strip.
        # Or "...{recovery}." when recovery=="" → trim the trailing dot
        # the joiner left.
        out = out.replace("  ", " ").rstrip()
        # Drop trailing semicolons + spaces from join slot exhaustion.
        while out.endswith((";", " ", ".")) and out.endswith(" ."):
            out = out[:-2].rstrip()
        return out
    except Exception:
        return template_str


def populate_socratic_extras(caption_facts: Dict[str, Any]) -> Optional["SocraticExtras"]:
    """Render the R18_socratic_user_mistake template into a
    SocraticExtras instance.

    Gate: returns None when socratic_is_active is not True (i.e., the
    caller did not pass socratic_context, severity wasn't a
    mistake/blunder, or one of the three pre-routing suppression gates
    fired). Mirrors the "return None" semantics of smart_coaching.
    generate_smart_user_feedback exactly.

    Variant selection uses the same evaluate_when predicate the rest
    of the JSON-driven rule engine uses (caption_templates.select_
    first_match). Builds the four narrative fields (narrative, plan,
    question, hint) from the matched variant's template strings.

    Per [[one-source-of-truth-for-coaching]] this is the deterministic
    replacement for the LLM call in generate_smart_user_feedback.
    """
    if not caption_facts.get("socratic_is_active"):
        return None

    cfg = _load_r18_template()
    if not cfg:
        return None

    # Derive the joined fields that variant templates reference.
    _compute_r18_derived_facts(caption_facts)

    try:
        from services.caption_templates import select_first_match
    except Exception:
        logger.exception("[caption_pipeline] caption_templates import failed; R18 disabled")
        return None

    rules = cfg.get("select_variant") or []
    match = select_first_match(rules, caption_facts)
    variant_name = (match or {}).get("variant") if match else None
    if not variant_name:
        # All R18 select_variant branches have terminal generic catchers
        # (blunder_generic / mistake_generic). If we land here, something
        # structurally surprising happened — pick the safest generic.
        variant_name = (
            "blunder_generic"
            if caption_facts.get("socratic_severity") == "blunder"
            else "mistake_generic"
        )

    variant_body = (cfg.get("variants") or {}).get(variant_name) or {}
    if not isinstance(variant_body, dict):
        logger.warning(
            f"[caption_pipeline] R18 variant {variant_name!r} is not a dict; "
            f"check R18_socratic_user_mistake.json schema"
        )
        return None

    return SocraticExtras(
        narrative=_format_r18_field(variant_body.get("narrative", ""), caption_facts),
        plan=_format_r18_field(variant_body.get("plan", ""), caption_facts),
        question=_format_r18_field(variant_body.get("question", ""), caption_facts),
        hint=_format_r18_field(variant_body.get("hint", ""), caption_facts),
    )


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
        # Parth Class B (fb_04395de2ad67): suppress all bs_* state clauses
        # on OPPONENT moves. The bs_* facts describe the USER's permanent
        # board state — they are useful as fallback context on USER moves
        # when no concrete why-clause fires, but on opp moves (e.g. opp_
        # inaccuracy where the bishop just slid away to escape attack)
        # they pile on as a 3-fact stat dump ("Opponent has developed N
        # pieces; you've developed 0. Your rook has only 0 legal moves.
        # Opp attacks center 6 times…"), which adds noise without teaching
        # anything about the move that just happened. Opp moves get their
        # own narration via R12 opp variants — keep those clean.
        try:
            _uc_norm = (user_color or "").lower()
            _user_is_white = _uc_norm == "white"
            _mover_color = chess.Board(fen_before).turn
            _mover_is_user = (_mover_color == chess.WHITE) == _user_is_white
        except Exception:
            _mover_is_user = True
        if not _mover_is_user:
            return
        _bs_facts = describe_board_state(
            fen_after=_fen_after,
            user_color=(user_color or ""),
            move_number=full_move_number or 0,
        )
        _top = select_top_facts(_bs_facts, n=3, max_per_category=2)
        # Parth fb_57d99cb6de27 / fb_fc5fe6cd1c30: suppress
        # bs_king_shield_broken when the user's move was a CAPTURE.
        # "Your king has lost N shelter pawns" is a permanent state
        # fact; on an offensive user-capture (Nxh3+, Qxd6, ...) the
        # mention is irrelevant noise — the move story is about the
        # capture, not the user's own king. We keep the fact on
        # defensive / quiet user moves and on all opponent moves
        # (where shelter context amplifies the threat narrative).
        try:
            _b_before = chess.Board(fen_before)
            _move_obj = _b_before.parse_san(move_san)
            _played_was_capture = _b_before.is_capture(_move_obj)
            _mover_color = _b_before.turn
            _uc_norm = (user_color or "").lower()
            _user_is_white = _uc_norm == "white"
            _mover_is_user = (_mover_color == chess.WHITE) == _user_is_white
        except Exception:
            _played_was_capture = False
            _mover_is_user = True
        if _played_was_capture and _mover_is_user:
            _top = [_bf for _bf in _top if _bf.fact_id != "bs_king_shield_broken"]
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
            _wp = _bp.get("would_prepare") or []
            if _wp:
                caption_facts["blocked_pawn_would_prepare"] = _wp[0]
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

    # ─── 3b. PWC coach-move narration facts (2026-05-26 migration off
    # smart_coaching.py per [[one-source-of-truth-for-coaching]]).
    # ─── DATA-RICHNESS AUTO-DERIVATION (Mohit 2026-05-27) ──────────
    # "the things we expose to PWC should be available for review too…
    # so both layers can be data rich." The central layer is the single
    # source: it auto-derives the coach-move + Socratic teaching from
    # each move's INTRINSIC properties, so BOTH review and PWC get the
    # rich output without the caller having to hand in a context flag.
    # PWC can still pass an EXPLICIT context (with v2 intent) to enrich
    # further; when present it wins.
    #
    # coach_move_context: explicit (PWC) OR auto for ANY opponent move
    #   (review narrates opponent's moves like coach moves — Mohit
    #   "treat opponent moves in ALL reviews like coach moves").
    # socratic_context: explicit (PWC) OR auto for user mistakes/blunders
    #   (review shows Socratic teaching on every user mistake).
    _phase_for_ctx = (
        "opening"
        if (max(0, (inputs.full_move_number or 1) - 1) * 2
            + (0 if inputs.mover_is_white else 1)) < 12
        else "middlegame"
    )

    _effective_coach_ctx = inputs.coach_move_context
    if _effective_coach_ctx is None and not inputs.mover_is_user:
        # Opponent move with no explicit PWC context → narrate it.
        # Empty dict signals "narrate, no v2 intent" (R17 terminal
        # variant handles the no-intent case).
        _effective_coach_ctx = {}

    _effective_socratic_ctx = inputs.socratic_context
    if _effective_socratic_ctx is None and inputs.mover_is_user:
        # Respect a caller-downgraded severity (book move / forced
        # recapture → "good") so we don't fire Socratic on non-mistakes.
        # severity_override is a str (V5 passes its downgraded tier);
        # canonical is a SeverityClassification — use its .tier string.
        _canonical_tier = getattr(canonical, "tier", None) or ""
        _eff_sev = (severity_override or _canonical_tier or "").lower()
        if _eff_sev in ("mistake", "blunder"):
            # Derive fundamental_violated from facts already computed
            # by extract_facts (step 1). hanging > missed-tactic > none.
            _fundamental = None
            if caption_facts.get("pieces_now_undefended"):
                _fundamental = "hanging_pieces"
            elif caption_facts.get("missed_tactic_kind"):
                _fundamental = "calculate"
            _effective_socratic_ctx = {
                "severity": _eff_sev,
                "fundamental_violated": _fundamental,
                "coach_intent": None,
                "phase": _phase_for_ctx,
            }

    # No-op when context (effective) is None. Stamps coach_intent /
    # coach_attack_targets / student_can_exploit for the R17_coach_move
    # templates and the CoachExtras populator.
    inject_coach_move_facts(
        caption_facts,
        board_before=board_before,
        move=played_move,
        user_color=inputs.user_color,
        coach_move_context=_effective_coach_ctx,
    )

    # ─── 3c. User-mistake Socratic facts (migration off smart_coaching.
    # generate_smart_user_feedback per [[one-source-of-truth-for-
    # coaching]]). No-op when effective socratic_context is None or
    # severity isn't a mistake/blunder. When active, applies the three
    # pre-routing gates (cp_loss<80, user-addresses-threat, opening
    # theory) and stamps facts for R18_socratic_user_mistake templates.
    inject_socratic_user_facts(
        caption_facts,
        board_before=board_before,
        move=played_move,
        user_color=inputs.user_color,
        cp_loss=int(inputs.cp_loss or 0),
        pv_after_played=list(inputs.pv_after_played or []),
        move_history_san=list(inputs.move_history_san or []),
        user_rating=int(inputs.user_rating or 1200),
        socratic_context=_effective_socratic_ctx,
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

    # ─── 4c. Good-move "why" (R15) — safe deterministic reason for a
    # user best move so it teaches instead of "strongest move here".
    # fb_ba9db31ae393. No-op unless cp_loss==0 and the move IS best.
    inject_good_move_reason_facts(
        caption_facts,
        board_before=board_before,
        move=played_move,
        move_san=inputs.played_san,
        mover_is_user=bool(inputs.mover_is_user),
        cp_loss=int(inputs.cp_loss or 0),
        best_move_san=inputs.best_move_san,
        phase=_phase,
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

    # ─── 9a. Played-took-without-check postfix (Parth fb_0900360fd0e4).
    # When the played move and the best move BOTH capture the same square
    # AND best gives check while played doesn't, the existing why-clause
    # explains why BEST is better; this appends a single sentence
    # explaining what the PLAYED move missed. Keeps the existing rich
    # variants intact (discovered_vac, missed_piece, etc.) and just adds
    # the "why played wrong" tail.
    if (caption_facts.get("played_capture_misses_check")
            and caption_payload.get("caption")
            and inputs.played_san):
        _cap = (caption_payload.get("caption") or "").rstrip()
        if _cap and "took without the check" not in _cap:
            if not _cap.endswith("."):
                _cap += "."
            caption_payload["caption"] = (
                f"{_cap} {inputs.played_san} took without the check, "
                f"so the opponent has time to organise."
            )

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

    # ─── 13. R17 coach-move narration (PWC only — populated when
    # coach_move_context was passed; returns None otherwise so the
    # MoveTeachingDecision.coach_extras field stays None for V5 review
    # and PWC user-side moves). Per [[one-source-of-truth-for-coaching]]
    # this is the central-layer replacement for smart_coaching.py.
    coach_extras = populate_coach_extras(caption_facts)

    # ─── 14. R18 socratic user-mistake narration (PWC only — populated
    # when socratic_context was passed AND inject_socratic_user_facts
    # didn't suppress via cp_loss/threat/opening gates). Per
    # [[one-source-of-truth-for-coaching]] this is the central-layer
    # replacement for smart_coaching.generate_smart_user_feedback.
    socratic_extras = populate_socratic_extras(caption_facts)

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
        coach_extras=coach_extras,
        socratic_extras=socratic_extras,
    )
