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
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

import chess

from services.severity import (
    classify_severity,
    classify_severity_practical,
    PracticalSeverity,
)
from services.caption_facts import (
    PIECE_VALUE_CP,
    LegalMaterialLossCause,
    legal_exchange_gain,
    ReviewTeachingCause,
    build_legal_material_loss_cause,
    build_verified_line_cause,
    legally_hanging_pieces,
    static_exchange_eval,
)
from services.exact_endgame_service import (
    ExactEndgameCause,
    ExactEndgameEvidence,
    build_exact_endgame_cause,
    render_exact_endgame_cause,
)

logger = logging.getLogger(__name__)

# Locked by the 2026-09-01 Quality V2 evidence packet. This is the same
# legal-exchange floor used to measure 913 verified simple-hang causes.
REVIEW_LEGAL_LOSS_FLOOR_CP = 150

# --- cognitive_gap -> the fundamental the Socratic surface teaches -----------
# Review derived fundamental_violated from exactly two board facts, so across
# 8,405 stored Socratic cards 86% landed on the generic variant and 11 of the
# 19 variants never fired at all. Every analysed move already carries the
# analyser's own label. Of the 7,230 generic cards:
#
#   king_safety         1,546  21.4%   variants exist, never fired
#   piece_safety        1,083  15.0%   variants exist
#   missed_tactic         923  12.8%   -> calculate
#   endgame_technique     770  10.7%   NO honest variant
#   opening_knowledge     764  10.6%   variant asserts more than the gap does
#   tactical_oversight    433   6.0%   -> calculate
#   <no gap stored>     1,711  23.7%   stays generic
#
# Only the categories with a variant that says something the gap actually
# establishes are mapped. opening_knowledge is deliberately absent: the
# development variant claims "you moved a developed piece instead of bringing
# a new one out", which does not follow from "this move left known theory".
# endgame_technique, pawn_structure, piece_activity and time_pressure have no
# variant at all. A wrong name is worse than no name
# (services/concept_attribution.py).
#
# hanging_pieces is safe to propose because inject_socratic_user_facts already
# downgrades it back to None when no piece is actually hanging after the move.
GAP_TO_FUNDAMENTAL = {
    "piece_safety": "hanging_pieces",
    "missed_tactic": "calculate",
    "tactical_oversight": "calculate",
    "calculation_depth": "calculate",
    "king_safety": "king_safety",
}


# --- gates on the loose-piece ("you left X available") card -------------------
# Both numbers come from the 500-game distribution printed at the call site.
#
# LEGAL_LOSS_MIN_COST_CP: the move has to have cost something. Below 50cp the
# engine considers the move essentially free, so blaming it for giving a piece
# away contradicts the engine we are quoting. 63 of 641 cards (9.8%) sat here,
# including a recapture at cp_loss 0 and "Rxf8 ... Kxf8" narrated as a rook
# left available.
#
# This floor is deliberately FLAT rather than the rating-band inaccuracy floor
# from rating_resolver. The bands are a volume control for subtle engine
# preferences; a piece hanging for free is not subtle, and it is exactly what a
# 700-rated player most needs to hear. Using the bands here removed 170 cards,
# among them a genuine free knight at cp_loss 142 for a 988-rated player --
# the wrong axis for this card type.
LEGAL_LOSS_MIN_COST_CP = 50

# LEGAL_LOSS_GAME_OVER_CP: once one side is up ~15 pawns or the score is a mate
# sentinel, a card about a rook is noise -- the live examples were cards fired
# at evals of +9880 and -9990. 200 or 600 would have been far too aggressive:
# 223 of 641 cards (35%) are played when one side is already 600-1499 ahead,
# and losing a rook while down 700 is still a real mistake worth teaching.
LEGAL_LOSS_GAME_OVER_CP = 1500


def _position_already_decided(eval_after_cp: Optional[int]) -> bool:
    """True when the score after the move puts the game beyond material talk.

    Fails OPEN (returns False) when the eval is missing or unusable, so a card
    is never dropped for want of a number. That also covers the ~3.9% of stored
    analyses whose eval_before/eval_after are in PAWNS rather than centipawns:
    those read as tiny values, never trip this gate, and keep their card.
    """
    if not isinstance(eval_after_cp, (int, float)):
        return False
    return abs(float(eval_after_cp)) >= LEGAL_LOSS_GAME_OVER_CP

_EXACT_ENDGAME_REVIEW_ENABLED = os.environ.get(
    "EXACT_ENDGAME_REVIEW_ENABLED", "false"
).strip().lower() in {"1", "true", "yes", "on"}


# ────────────────────────────────────────────────────────────────────
# v104 (Mohit 2026-06-03) — FLOOR TEACHING PRINCIPLE INJECTION
# ────────────────────────────────────────────────────────────────────
# When R12 falls through to the bare "{played_san} is a mistake. {best} was
# better." shell (no failure_clause, no why_clause), append a transferable
# principle from data/captions/principle_bank.json. Selection is by
# (phase × severity bucket) and deterministic by FEN hash.

import json as _json_pb
import re as _re_pb
import zlib as _zlib_pb
from pathlib import Path as _Path_pb

_PRINCIPLE_BANK_PATH = (
    _Path_pb(__file__).resolve().parent.parent / "data" / "captions" / "principle_bank.json"
)
try:
    with open(_PRINCIPLE_BANK_PATH) as _fpb:
        _PRINCIPLE_BANK = _json_pb.load(_fpb).get("buckets", {})
    logger.info(f"[principle_bank] loaded {len(_PRINCIPLE_BANK)} buckets")
except Exception as _bank_exc:
    logger.warning(f"[principle_bank] load failed: {_bank_exc}")
    _PRINCIPLE_BANK = {}

_SHELL_RE = _re_pb.compile(
    r"^\S+\.?\s+is\s+an?\s+"
    r"(?P<sev>mistake|serious mistake|major blunder|inaccuracy)\.\s+"
    r"\S+\s+was\s+better\.?\s*$"
)


def _maybe_append_floor_principle(
    caption: str, full_move_number: int, mover_is_user: bool, fen_before: str,
) -> str:
    """Append a floor teaching principle when caption is the bare shell shape.

    Only fires on user moves (opp moves have their own variants).
    Returns the caption unchanged if shell doesn't match or bank is empty.
    """
    if not caption or not mover_is_user or not _PRINCIPLE_BANK:
        return caption
    m = _SHELL_RE.match(caption.strip())
    if not m:
        return caption
    sev = m.group("sev")
    sev_bucket = "blunder" if sev in ("serious mistake", "major blunder") else "mistake"
    mn = full_move_number or 1
    if mn <= 12:
        phase = "opening"
    elif mn <= 40:
        phase = "middlegame"
    else:
        phase = "endgame"
    bucket_key = f"{phase}_{sev_bucket}"
    bucket = _PRINCIPLE_BANK.get(bucket_key) or []
    if not bucket:
        return caption
    idx = _zlib_pb.crc32((fen_before or "").encode("utf-8")) % len(bucket)
    principle = bucket[idx]
    if not caption.endswith("."):
        caption = caption + "."
    return f"{caption} {principle}."




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
    # True when this move is the one the previous card recommended.
    move_was_our_recommendation: bool = False
    user_best_reply_san_is_forcing: bool = False

    # ─── Game metadata (for opening intro / curriculum walker) ───
    eco_code: Optional[str] = None
    opening_name: Optional[str] = None
    user_rating: Optional[int] = None
    # The analyser's own label for what went wrong on this move, one of the
    # nine cognitive_gap categories. Stored on every analysed move and, until
    # now, never read by the coaching layer -- which is why 86% of Socratic
    # cards fell to the generic variant. See GAP_TO_FUNDAMENTAL below.
    cognitive_gap: Optional[str] = None

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
    # Offline corpus audits replay stored Stockfish evidence and must never
    # initialize a fresh engine verifier. Runtime callers retain the deployed
    # behavior unless they explicitly opt out.
    allow_fresh_engine_verification: bool = True

    # ─── Coach Conductor: the player-model digest (docs/pwc_coach_conductor_scope.md).
    # The output of coach_conductor.player_motif_threads() — which motifs are THIS
    # player's recurring story (defense walk-into / offense slipping). When present
    # and the move is an engine-confirmed instance of one of them, the door surfaces
    # a personalized STATEMENT thread as the caption (the conductor's chosen "one most
    # useful thing"). None for review without a player model and for coach moves.
    player_motif_threads: Optional[Dict[str, Any]] = None

    # ─── Coach Conductor: the player's recurring OPENING mistakes
    # (coach_conductor.player_opening_threads() — {family: {played_san: ...}}).
    # Engine-confirmed recurring deviations only (sound deviations are filtered
    # out upstream). When the move is the player's recurring first-deviation in a
    # recognized opening AND costs real eval, the door PREPENDS an "again"
    # recurrence framing to the caption. None for review / coach moves.
    player_opening_threads: Optional[Dict[str, Any]] = None

    # ─── Coach Conductor: the player's CONCEPT strengths + weaknesses from
    # user_concept_understanding. See docs/pwc_memory_wiring_scope.md §5 Item B,
    # shipped 2026-07-08. Shape: {weaknesses: {cid: {name, clean_rate_pct, ...}},
    # strengths: {cid: ...}}. When the played move's principle_id_used matches a
    # weakness concept AND severity is mistake+, the door fires a STATEMENT
    # thread: "There it is again — [concept name]. This is the pattern you've
    # been slipping on. Slow down here." Silent on strengths (mastered concepts
    # never nagged). None for review / coach moves.
    player_concept_threads: Optional[Dict[str, Any]] = None

    # ─── Coach Conductor: user's STRONG openings (2026-07-08, Item E).
    # Set of normalized opening names (from services.player_performance.
    # get_strong_openings — ≥5 games, ≥55% win rate). When the player is
    # currently in one of these AND plays a sound move, fires a strength
    # thread: "You own the {opening} — this is your weapon. Trust it."
    # Complements player_opening_threads (which is the MISTAKE side).
    strong_openings: Optional[Set[str]] = None

    # ─── Coach Conductor: identity engine narrative (Item C).
    # {level, main_leak_label, phase_label, style_label} from
    # coach_conductor.player_identity_lead_in — high-confidence only.
    # When any conductor thread fires, decorated with a short
    # identity-cued lead-in ONCE per session. Silent for medium/low
    # confidence, and never for coach moves.
    player_identity: Optional[Dict[str, Any]] = None

    # ─── Session focus — the ACTIVE GOAL FILTER (Phase 1, 2026-07-08).
    # Mohit push: "if it's goal, coach should act on it." This is the
    # focus_bridge output at session start ({topic_key, topic_label,
    # dominant_subtype, days_into_focus, ...}). When a conductor thread
    # fires with a kind that aligns with the focus topic, the door
    # decorates the thread with a short "that's your [topic] focus this
    # week" anchor — so the coach voice EXPLICITLY connects today's stated
    # goal to what it just said. Once per session (goal_anchor restraint).
    session_focus: Optional[Dict[str, Any]] = None

    # Batch Review loads the real player context in shadow before rollout.
    # The decision still records the structured connection, but visible text
    # stays byte-for-byte on the base caption until the Stage 4 flag is on.
    # Live PWC leaves this False to preserve its existing conductor rollout.
    player_context_shadow_only: bool = False

    # Optional evidence packets are produced by their owning services. The
    # caption pipeline validates and consumes them; it never invokes a model
    # or tablebase subprocess itself.
    exact_endgame_evidence: Optional[Dict[str, Any]] = None
    human_policy_evidence: Optional[Dict[str, Any]] = None
    # Immutable background evidence for the played and candidate branches.
    # The central pipeline validates its source fingerprint before use.
    candidate_caption_evidence: Optional[Dict[str, Any]] = None


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

    # What the PREVIOUS card told the player to play. Read on the next user
    # move so a generic lesson cannot scold the very move we prescribed.
    last_recommended_san: Optional[str] = None
    # Coach Conductor restraint: motif-thread keys already pulled this game
    # ("offense:skewer", "defense:fork"). A thread fires at most once per game.
    # Mutated in place by the door when a thread fires; the caller persists it.
    conductor_threads_pulled: Set[str] = field(default_factory=set)


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
    # Carries the recommendation this card makes to the next move.
    last_recommended_san_after: Optional[str] = None
    # Coach Conductor: motif-thread key(s) pulled this move ("offense:skewer").
    # Caller unions into the session's conductor_threads_pulled for restraint.
    conductor_threads_pulled_added: Set[str] = field(default_factory=set)


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
    # The picture for the move we RECOMMEND, which lives on a different board:
    # board_before + the best move, not the board the card renders. Kept apart
    # from `arrows` so it can never be drawn over the played position -- that
    # is the whole bug this field exists to avoid. The review page shows it on
    # "What if I played X?", which already puts that exact position on screen.
    best_move_arrows: List[Dict[str, str]] = field(default_factory=list)
    best_move_arrows_fen: str = ""


@dataclass
class TeachingMeta:
    """Categorical metadata about WHAT was taught and HOW severe."""
    severity: str = "context"  # user-facing tier ("good"/"mistake"/"opp_mistake"/...)
    severity_canonical: str = "good"
    severity_practical: str = "good"
    caption_tier: str = "NONE"  # HIGH / MID / LOW / NONE per caption_classifier
    # Mohit 2026-05-31: the actual severity WORD R12 chose for the
    # rendered caption text (e.g. "is a mistake" -> "mistake"). Differs
    # from `severity` (which is the cp_loss-based canonical) when R12
    # tier resolution applies bumps/falls (played_smaller_win,
    # canonical-mistake-stayed-balanced, etc.). Frontend badge derives
    # from this field so the board badge and caption text always agree.
    # None when the caption isn't an R12-severity caption (clean move,
    # R15 good-move, opening intro, silent).
    caption_severity_word: Optional[str] = None
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
class CaptionExplanation:
    """Structured, auditable meaning behind the rendered coach sentence.

    The UI may render the strings, but it must never infer these fields by
    parsing prose.  `player_connection` is populated only when an existing
    evidence-backed conductor thread fired on this exact position.
    """
    board_explanation: str = ""
    player_connection: str = ""
    transferable_instruction: str = ""
    confidence: str = "silent"  # verified | limited | silent
    provenance: List[str] = field(default_factory=list)
    personal_evidence: Optional[Dict[str, Any]] = None
    final_verified: bool = False
    rendered_personalization: bool = False
    rollout_mode: str = "shadow"  # shadow | visible


@dataclass(frozen=True)
class CandidateComparison:
    """One compact, replayable comparison from verified branch evidence."""
    headline: str
    played_summary: str
    stronger_summary: str
    memory_cue: str
    played_line_moves: Tuple[str, ...]
    stronger_line_moves: Tuple[str, ...]
    source_fingerprint: str
    evidence_fingerprint: str
    cause_fingerprint: str
    proof_authority: str
    proof_version: str
    schema_version: str = "candidate_comparison.v1"

    def __post_init__(self) -> None:
        required = (
            self.headline, self.played_summary, self.stronger_summary,
            self.memory_cue, self.source_fingerprint, self.evidence_fingerprint,
            self.cause_fingerprint,
            self.proof_authority, self.proof_version,
        )
        if any(not str(value).strip() for value in required):
            raise ValueError("candidate comparison fields must be non-empty")
        if len((self.played_summary + " " + self.stronger_summary).split()) > 32:
            raise ValueError("candidate comparison exceeds the 32-word reading lock")
        if len(self.memory_cue.split()) > 18:
            raise ValueError("candidate memory cue exceeds the 18-word reading lock")
        if not self.played_line_moves or not self.stronger_line_moves:
            raise ValueError("candidate comparison requires two replayable branches")

    def public_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "headline": self.headline,
            "played": {"summary": self.played_summary, "moves": list(self.played_line_moves)},
            "stronger": {"summary": self.stronger_summary, "moves": list(self.stronger_line_moves)},
            "memory_cue": self.memory_cue,
            "source_fingerprint": self.source_fingerprint,
            "evidence_fingerprint": self.evidence_fingerprint,
            "cause_fingerprint": self.cause_fingerprint,
            "proof": {"authority": self.proof_authority, "version": self.proof_version},
        }


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
    # Explicit SAN sequence for the existing Game Review "Play this line"
    # interaction. Opponent-side alternatives cannot reuse pv_after_best from
    # the played-move record, so A3 returns the legally reconstructed line and
    # the central decision must carry it across the V5 boundary.
    coach_line_moves: List[str] = field(default_factory=list)
    coach_line_length_hint: Optional[int] = None
    # PWC user-mistake Socratic payload (2026-05-27 migration). Populated
    # ONLY when MoveInputs.socratic_context is set AND the R18 gates
    # don't suppress (cp_loss<80, threat-handling, opening theory).
    # See SocraticExtras docstring for field semantics.
    socratic_extras: Optional[SocraticExtras] = None
    # Stage 4: typed causal/personal explanation.  Both Review and PWC
    # receive the same shape; callers no longer need to parse caption prose.
    explanation: CaptionExplanation = field(default_factory=CaptionExplanation)
    # Canonical, typed position cause. Downstream surfaces may project this
    # value but must not rebuild it from prose or rerun chess inference.
    cause: Optional[ReviewTeachingCause] = None
    # Coach Conductor: the player-model thread that fired this move, if any.
    # Personal context frames the verified chess explanation; under the Stage
    # 4 renderer it never replaces that explanation.
    # Shape: {"kind","motif","side","text"}. None when no thread fired.
    conductor_thread: Optional[Dict[str, Any]] = None
    # Auditable derived evidence. Neither field is parsed from prose.
    exact_endgame_evidence: Optional[Dict[str, Any]] = None
    human_policy_evidence: Optional[Dict[str, Any]] = None
    # Surface-neutral, typed explanation questions for an exact submitted
    # move. Callers render the contract; they never rebuild chess facts.
    reason_bundle: Optional["TeachingReasonBundle"] = None
    candidate_comparison: Optional[CandidateComparison] = None


def build_reason_bundle_for_move(
    *,
    fen_before: str,
    submitted_move: str,
    quality_id: str,
):
    """Dispatch exact reason construction through promoted fact providers."""
    from services.destination_safety_detector import (
        QUALITY_ID as DESTINATION_SAFETY_QUALITY_ID,
        build_destination_safety_reason_bundle,
    )

    if quality_id == DESTINATION_SAFETY_QUALITY_ID:
        return build_destination_safety_reason_bundle(fen_before, submitted_move)
    return None


def build_candidate_comparison(
    inputs: MoveInputs,
    cause: Optional[ReviewTeachingCause],
) -> Optional[CandidateComparison]:
    """Compose one short comparison from a currently authorized exact cause."""
    if cause is None or not inputs.candidate_caption_evidence:
        return None
    from services.candidate_caption_evidence import CandidateEvidence, root_moves
    from services.detector_quality import QualitySurface, is_authorized

    quality_id = (
        "review:exact_endgame_result_change"
        if isinstance(cause, ExactEndgameCause)
        else "review:verified_single_game_cause"
    )
    if not is_authorized(quality_id, QualitySurface.CAPTION):
        return None
    source_row = {
        "fen_before": inputs.fen_before,
        "move_san": inputs.played_san,
        "best_move_san": inputs.best_move_san,
        "best_move_uci": inputs.best_move_uci,
        "eval_before": inputs.eval_before_cp,
        "eval_after": inputs.eval_after_cp,
        "cp_loss": inputs.cp_loss,
        "pv_after_played": list(inputs.pv_after_played or ()),
        "pv_after_best": list(inputs.pv_after_best or ()),
        "is_opponent_move": not inputs.mover_is_user,
        "move_number": inputs.full_move_number,
    }
    try:
        evidence = CandidateEvidence.from_document(
            inputs.candidate_caption_evidence, source_row
        )
        _board, played, best = root_moves(source_row)
        played_branch = evidence.branch(played.uci())
        best_branch = evidence.branch(best.uci())
        if played_branch is None or best_branch is None:
            return None
    except (TypeError, ValueError):
        return None

    if isinstance(cause, LegalMaterialLossCause):
        affected = cause.affected.piece
        if cause.played_capture is not None:
            headline = "Count both sides of the trade"
            played_summary = (
                f"{inputs.played_san} takes their {cause.played_capture.piece}, "
                f"but {cause.punishment_san} takes your {affected}."
            )
        else:
            headline = f"Your {affected} needed protection"
            played_summary = (
                f"{inputs.played_san} leaves your {affected} on "
                f"{cause.affected.square} open to {cause.punishment_san}."
            )
        stronger = cause.avoidable_with_san or cause.best_move_san
        purpose = {
            "moves_affected_piece": f"{stronger} moves it away.",
            "removes_attacker": f"{stronger} removes the attacker.",
            "adds_defender": f"{stronger} adds enough protection.",
        }.get(cause.best_move_purpose, f"{stronger} keeps that piece safe.")
        return CandidateComparison(
            headline=headline,
            played_summary=played_summary,
            stronger_summary=purpose,
            memory_cue="Count what you take and what comes back before starting a capture.",
            played_line_moves=played_branch.moves_san,
            stronger_line_moves=best_branch.moves_san,
            source_fingerprint=evidence.source_fingerprint,
            evidence_fingerprint=evidence.document()["fingerprint"],
            cause_fingerprint=cause.fingerprint,
            proof_authority=cause.proof_authority,
            proof_version=cause.proof_version,
        )

    if isinstance(cause, VerifiedLineCause):
        if cause.lesson_kind == "missed_forced_mate":
            headline = "A checkmating finish was available"
            played_text = f"{inputs.played_san} lets the finish pass."
            stronger_text = f"{cause.best_move_san} starts a line that ends in checkmate."
            memory = "Check every forcing reply before leaving an attack."
        elif cause.lesson_kind == "allowed_forced_mate":
            headline = "This move opened the door to mate"
            played_text = f"{inputs.played_san} allows {cause.reply_san} and a forced checkmate."
            stronger_text = f"{cause.best_move_san} stops that finish."
            memory = "Before moving, scan every check your opponent gets next."
        elif cause.lesson_kind == "exchange_sequence":
            headline = "The capture sequence ends badly"
            played_text = f"{inputs.played_san} starts a sequence that leaves you down material."
            stronger_text = f"{cause.best_move_san} avoids that exchange."
            memory = "Count every recapture before beginning a trade."
        elif cause.lesson_kind == "missed_material_opportunity" and cause.first_best_capture:
            target = cause.first_best_capture
            headline = "A material win was hiding here"
            played_text = f"{inputs.played_san} misses the {target.captured_piece} on {target.captured_square}."
            stronger_text = f"{cause.best_move_san} begins the line that wins it."
            memory = "Follow each candidate until you see what it actually wins."
        else:
            return None
        return CandidateComparison(
            headline=headline,
            played_summary=played_text,
            stronger_summary=stronger_text,
            memory_cue=memory,
            played_line_moves=played_branch.moves_san,
            stronger_line_moves=best_branch.moves_san,
            source_fingerprint=evidence.source_fingerprint,
            evidence_fingerprint=evidence.document()["fingerprint"],
            cause_fingerprint=cause.fingerprint,
            proof_authority="caption_facts.build_verified_line_cause",
            proof_version=cause.proof_version,
        )
    return None


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
    # v159 (2026-09-15): set when the played move IS the engine's top
    # choice, so no caller fault-frames it. The old downgrade lived
    # inline in V5 service gated on `is_user`, so opponent moves were
    # never covered ("Opponent's Nxh4 is an inaccuracy" on a move the
    # engine itself plays). Measured on the 426 user-flagged moves
    # carrying FEN+caption: 67 were the engine's own top move at depth
    # 16, ~15 of them captioned as a fault.
    is_best_equals_played: bool = False
    # Set when the played move delivers checkmate. Mate dominates every
    # positional read: Qf8# was captioned "Weak Squares - their bishop is
    # the wrong colour..." and b8=Q# "Free Pawn - push it to promote",
    # both on the move that ended the game.
    played_is_mate: bool = False
    # v186 (2026-10-05): the mover had a forced mate before this move and
    # still has one after it. Such a move is never an error tier, however
    # large cp_loss looks -- in a mate position cp_loss is the gap between
    # two clamped mate scores, so a slower mate reads like lost material.
    # 7,714 corpus moves preserve a mate; 94 were tiered as errors and 90
    # of those had the mate get FASTER.
    mate_preserved: bool = False



def is_quiet_opening_king_walk(
    board_before: Optional[chess.Board],
    played_move: Optional[chess.Move],
    full_move_number: Optional[int],
    max_full_move: int = 10,
) -> bool:
    """A king step in the opening that throws away castling for nothing.

    Mohit 2026-09-28, on a card badged GOOD with a green tick: "coach
    shouldn't really appreciate this, king out in the open in the second or
    third move you know, this should be criticised." The move was 2...Kf7,
    cp_loss 71 -- four points under the 75 the rating band needs to call
    anything an inaccuracy, because the position was already poor after
    1...f6 so the engine saw little ADDITIONAL loss. Centipawns measure the
    position; they do not measure having given up castling on move two.

    Deliberately narrow, because the first version was not. Over 600 games,
    38 early king moves forfeit castling -- and 25 of them have cp_loss 0
    because they are RECAPTURES: Kxe2, Kxf7, Kxd8, usually forced and
    perfectly correct. Criticising those would be worse than the bug.

    So: not a capture, not escaping check, and it must actually destroy
    castling rights the player still had. That leaves 5 in 600 games, and
    all five already score 108cp or worse -- so this floor changes almost
    nothing except the case where the engine happens to shrug.
    """
    if board_before is None or played_move is None:
        return False
    if full_move_number is not None and full_move_number > max_full_move:
        return False
    try:
        piece = board_before.piece_at(played_move.from_square)
        if piece is None or piece.piece_type != chess.KING:
            return False
        if board_before.is_capture(played_move):
            return False          # a recapture is usually forced, and fine
        if board_before.is_check():
            return False          # moving out of check is not a choice
        if board_before.is_castling(played_move):
            return False          # castling IS the thing we want
        colour = piece.color
        had_rights = (board_before.has_kingside_castling_rights(colour)
                      or board_before.has_queenside_castling_rights(colour))
        if not had_rights:
            return False
        after = board_before.copy(stack=False)
        after.push(played_move)
        keeps = (after.has_kingside_castling_rights(colour)
                 or after.has_queenside_castling_rights(colour))
        return not keeps
    except Exception:
        return False


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
    # v159: engine truth for the best-equals-played sanity downgrade.
    # Both optional - when either is missing the downgrade is skipped
    # (right-or-silent; we never guess that a move was best).
    # Needed by the opening king-walk floor. A real parameter, not a name
    # borrowed from a caller's scope: doing that an hour earlier threw a
    # NameError that a bare `except` swallowed, taking a whole caption block
    # with it silently.
    full_move_number: Optional[int] = None,
    best_move_san: Optional[str] = None,
    played_san: Optional[str] = None,
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
    #
    # Bug fix (2026-08-03): "only one piece could recapture here" does
    # NOT mean the recapture itself was safe — it can still hang the
    # recapturing piece to a further capture (confirmed on a real game:
    # black's Qxf3 recapturing White's queen on f3 was the only legal
    # recapture, but immediately lost the queen to White's next capture,
    # 431cp loss). The downgrade is only valid when the engine's own
    # canonical classification agrees this wasn't a real mistake —
    # otherwise a genuine blunder/mistake/serious tier silently became
    # "good" here, which fed into `severity_override` for the Socratic-
    # coaching gate downstream and suppressed it on every qualifying
    # forced-recapture blunder in production (0/12,328 analyzed games
    # had non-null socratic_coaching before this fix).
    is_forced_recapture = False
    if is_user and played_move is not None and prev_move is not None:
        if (board_before.is_capture(played_move)
                and played_move.to_square == prev_move.to_square):
            captures_on_sq = [
                m for m in board_before.legal_moves
                if m.to_square == played_move.to_square
                and board_before.is_capture(m)
            ]
            if len(captures_on_sq) <= 1 and severity_canonical not in ("blunder", "mistake", "serious"):
                is_forced_recapture = True
                severity = "good"

    # --- Best-equals-played sanity downgrade (v159) ----------------
    # You cannot lose centipawns by playing the engine's own top choice,
    # so a cp_loss that says otherwise is internally inconsistent, and
    # captioning the move as a fault contradicts the very move we would
    # recommend ("Opponent's Rxd6 is an inaccuracy. Play Rxd6 ..."
    # shipped to a real user).
    #
    # This used to live inline in game_decryption_v5_service.py gated on
    # `is_user`, so it covered review-side USER moves only. NOTE: PWC does
    # not reach this helper - it calls build_move_teaching_decision, which
    # classifies severity itself, so the same guard is applied there too.
    is_best_equals_played = False
    _best_norm = (best_move_san or "").strip().rstrip("!?+#")
    _played_norm = (played_san or "").strip().rstrip("!?+#")
    if _best_norm and _played_norm and _best_norm == _played_norm:
        is_best_equals_played = True
        if severity_canonical in ("inaccuracy", "mistake", "serious", "blunder"):
            severity = "good" if is_user else "context"
            severity_canonical = "good"

    # --- Mate dominance (v159) -------------------------------------
    # A move that ends the game is never an inaccuracy and never a
    # positional footnote. Board-verified, so right-or-silent.
    played_is_mate = False
    if played_move is not None:
        try:
            _b = board_before.copy(stack=False)
            _b.push(played_move)
            played_is_mate = _b.is_checkmate()
        except Exception:
            played_is_mate = False
    if played_is_mate:
        severity = "good" if is_user else "context"
        severity_canonical = "good"

    # --- Mate preserved (v186) -------------------------------------
    # The sibling guard above handles "this move IS checkmate". This one
    # handles the move before it: a forced mate existed, and after the move
    # a forced mate still exists for the same side. That is not an error,
    # whatever cp_loss says.
    #
    # Mohit 2026-10-05, on a K+2B vs K+P endgame card reading "Bg5 —
    # Blunder — Tactical · missed tactic": "look at it". At depth 22 Be6
    # mates in 9, Ke6 in 10, and his Bg5 in 20. He was mating before the
    # move and mating after it, and we called it a blunder.
    #
    # The cause is that `mate_info` is read NOWHERE in the render path.
    # Severity comes from cp_loss, and in a mate position cp_loss is the
    # gap between two clamped mate scores -- so "mate in 9 became mate in
    # 20" and "you dropped a rook" are the same number to this code.
    # Measured on the rendered cards: 3,966 are tiered as an error while the
    # mover still has a forced mate, 3,770 of them saying BLUNDER, and in
    # 2,609 the mate got FASTER. One player is told "blunder" on three
    # consecutive moves (3da52c5e m36-38) while delivering mate. A lower
    # bound -- 229,374 of 368,160 error-tier cards have no eval row to join
    # to, because move_evaluations stores only user moves.
    #
    # Mate is detected from the evals this function already receives, so
    # there is no new parameter and no second source of truth. The floor is
    # read off the distribution rather than chosen: evals carrying a mate
    # score run 9650..10000 (n=15,184) and evals without one top out at
    # 8308 (n=176,928), with zero overlap either way across 192,112 values.
    # 9000 sits in the empty gap.
    _MATE_EVAL_FLOOR = 9000
    mate_preserved = False
    _mover_sign = 1 if is_white else -1
    _mate_before = (
        practical_eval_before * _mover_sign
        if practical_eval_before is not None else None
    )
    _mate_after = (
        practical_eval_after * _mover_sign
        if practical_eval_after is not None else None
    )
    if (
        not played_is_mate
        and _mate_before is not None
        and _mate_after is not None
        and _mate_before >= _MATE_EVAL_FLOOR
        and _mate_after >= _MATE_EVAL_FLOOR
    ):
        mate_preserved = True
        if severity_canonical in ("inaccuracy", "mistake", "serious", "blunder"):
            severity = "good" if is_user else "context"
            severity_canonical = "good"

    # A quiet king walk in the opening is never "good", whatever the number
    # says. It floors at inaccuracy rather than being pushed higher: the move
    # gave something real away, and the engine is still the authority on HOW
    # much. Mate and forced recaptures are settled above and are untouched.
    if (
        is_user
        and not played_is_mate
        and severity == "good"
        and is_quiet_opening_king_walk(board_before, played_move, full_move_number)
    ):
        severity = "inaccuracy"
        severity_canonical = "inaccuracy"

    return SeverityComputation(
        severity_user_facing=severity,
        severity_canonical=severity_canonical,
        practical=practical,
        is_forced_recapture=is_forced_recapture,
        is_best_equals_played=is_best_equals_played,
        played_is_mate=played_is_mate,
        mate_preserved=mate_preserved,
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
                    # fb_80c1ea9555cb (Parth, 2026-05-31): TRADE detection.
                    # When best_move captures something BUT the capturer
                    # dies to a recapture (e.g. Bxc6 followed by bxc6),
                    # this is a TRADE, not a "free capture." The default
                    # why_user_missed_capture template tail ("Before every
                    # move, scan for free captures — material won is
                    # leverage you keep") is misleading for trades: no
                    # material is "won," the bishop dies. Detect the
                    # trade via the same _mover_dies_on_destination helper
                    # used by Day 1 detector-family fixes, then route to
                    # the trade variant which drops the false claim.
                    try:
                        from services.shape_detectors import _mover_dies_on_destination
                        _post = _board_cap.copy()
                        _post.push(_best_mv)
                        if _mover_dies_on_destination(_post, _best_mv.to_square):
                            caption_facts["best_move_capture_is_trade"] = True
                    except Exception:
                        pass
                    # Sac-awareness (fb_6f2a5ba1f626 reused for R12 why-
                    # clauses): when the BEST move is a capture whose
                    # attacker is worth MORE than the target AND the
                    # destination is defended after the capture, the
                    # best move is a SACRIFICE, not a 'wins the piece'
                    # win. R12 needs this so 'Nxh3+ was better — captures
                    # the pawn on h3. Material won is leverage…' stops
                    # firing on knight sacrifices.
                    # A sacrifice is a move that LOSES material when the
                    # exchange is played out -- not merely a big piece landing
                    # on a defended square.
                    #
                    # The old test was "attacker worth more than target AND
                    # something defends the square afterwards", using
                    # board.attackers(), which is pseudo-legal and does not
                    # play the trade out. Measured over 400 games it fired on
                    # 422 recommended captures and 247 of them (58%) actually
                    # WIN material -- so "it sacrifices your bishop to open up
                    # a strong attack, the attack is worth more than the pawn"
                    # was being said about moves that just win a piece.
                    #
                    # legal_exchange_gain plays every capture on the square,
                    # king recaptures included, which is the same authority the
                    # arrows and the recommended-move reason now use.
                    _attacker_piece = _board_cap.piece_at(_best_mv.from_square)
                    try:
                        _sac_gain = legal_exchange_gain(
                            _board_cap, _best_mv.to_square, _board_cap.turn,
                            first_move=_best_mv,
                        )
                    except (ValueError, TypeError):
                        _sac_gain = None
                    # Not from a position that is already lost. The variant
                    # this fact drives claims "the attack is worth more than
                    # the {piece} you lose", and from a lost position that is
                    # not true -- the engine is picking the best of bad
                    # options, not winning an attack. Measured over 400 games:
                    # 54 of 176 true sacrifices (31%) are played from a mover
                    # eval at or below -300. Uses the existing user_is_losing
                    # flag rather than a new threshold, and note that raw
                    # eval_before is WHITE-relative (measured 97% vs 44%), so
                    # reading its sign directly would have mis-signed every
                    # black-to-move card.
                    if (_sac_gain is not None and _sac_gain < 0
                            and not caption_facts.get("user_is_losing")):
                        _opp = not _board_cap.turn
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

    # 10b. Capture-removes-attacker (Parth fb_80c1ea9555cb, 2026-05-31).
    # Engine's best move captures an opp piece that was attacking a user
    # piece. The capture removes the attacker at the source — distinct
    # tactic from active defense (which adds a defender) or generic
    # capture-the-knight framing (which misses the "why this capture").
    try:
        from services.shape_detectors import simulate_capture_removes_attacker
        _rm_evs = simulate_capture_removes_attacker(fen_before, best_move)
        if _rm_evs:
            _e = _rm_evs[0]
            caption_facts["removed_attacker_target_piece"] = _e.get("removed_attacker_target_piece")
            caption_facts["removed_attacker_target_square"] = _e.get("removed_attacker_target_square")
            caption_facts["removed_attacker_captured_piece"] = _e.get("removed_attacker_captured_piece")
            caption_facts["removed_attacker_captured_square"] = _e.get("removed_attacker_captured_square")
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

    # 15. Missed discovered attack (2026-09-19).
    #
    # This is the first detector in the product promoted to caption grade on
    # HUMAN semantic review -- 49 positions Mohit ruled one at a time with the
    # board and both lines in front of him, 0 wrong -- rather than on two
    # implementations agreeing. See
    # docs/discovered_attack_caption_promotion_2026_09_19.md.
    #
    # Detector #12 above (simulate_discovered_attack_vacating_check) is the
    # narrow cousin: it only fires when the vacating move gives check. This is
    # the general case, and it carries its own independent payoff verifier.
    #
    # Gated on the live grade rather than on a flag, so the caption cannot
    # outrun its authorization: drop the grade to shadow and this goes silent
    # with no code change.
    try:
        from services.detector_quality import QualityGrade, grade_for
        from services.discovered_attack_puzzle_proof import (
            DISCOVERED_ATTACK_QUALITY_ID,
            build_discovered_attack_proof,
        )

        if grade_for(DISCOVERED_ATTACK_QUALITY_ID) == QualityGrade.CAPTION:
            _da_board = chess.Board(fen_before)
            _da_bundle = build_discovered_attack_proof(
                _da_board.copy(stack=False),
                move_san,
                best_move,
                pv_after_best or [],
                cp_loss,
            )
            if _da_bundle and getattr(_da_bundle.verifier, "verified", False):
                _vf = list(getattr(_da_bundle.verifier, "facts", ()) or ())
                _v = (_vf[0] or {}) if _vf else {}
                _blocker = _da_board.piece_at(
                    chess.parse_square(str(_v.get("vacated_square"))))
                if _v.get("target_square") and _blocker is not None:
                    caption_facts["missed_discovery_blocker_piece"] = (
                        chess.piece_name(_blocker.piece_type))
                    caption_facts["missed_discovery_slider_piece"] = _v.get("slider_piece")
                    caption_facts["missed_discovery_slider_square"] = _v.get("slider_square")
                    caption_facts["missed_discovery_target_piece"] = _v.get("target_piece")
                    caption_facts["missed_discovery_target_square"] = _v.get("target_square")
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
    pv_after_played: Optional[List[str]] = None,
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

    # A check the opponent cannot profit from: every legal answer also
    # attacks the checking piece. fb_ca8cc3ec9c5f shipped as a bare
    # "Opponent's Qb1+ is a major blunder." with no why at all.
    if not is_user:
        try:
            from services.caption_facts import (
                _opp_check_answered_by_hitting_it as _ocah,
            )
            _pc = _ocah(board, move)
            if _pc:
                caption_facts["opp_check_every_answer_hits_it"] = True
                caption_facts["opp_check_piece"] = _pc["piece"]
                caption_facts["opp_check_square"] = _pc["square"]
                caption_facts["opp_check_answer_count"] = _pc["answer_count"]
        except Exception:
            pass
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
                    # The verified recapture/fork explanation names all five
                    # plies. Preserve them in the existing coach-line payload
                    # so every SAN in the caption can be replayed on the board.
                    if _punish_facts.get(
                        "opp_user_reply_unsafe_recapture_pawn_fork"
                    ):
                        _coach_line_moves = [
                            move_san,
                            _user_reply,
                            *list(_next_pv_best_for_punish[:4]),
                        ]
                        coach_line_result = (
                            _coach_line_moves,
                            len(_coach_line_moves),
                        )
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
            # The LINE behind that reply, for the picture. Opponent moves carry
            # no engine row of their own -- move_evaluations stores user moves
            # only -- so an opp card's pv_after_played is empty and the
            # sequence builder gets nothing. The continuation is right here in
            # the next position's eval, already used for the coach line, and
            # was simply never handed to the arrows.
            #
            # Mohit 2026-10-06 on the Ng5 card: "the idea is missing, the main
            # idea is bishop takes the pawn and king takes bishop, our knight
            # checks the king and the knight now behind our knight gets
            # captured by our queen, so that's the whole line and arrow doesn't
            # show until there".
            caption_facts["user_reply_pv"] = [_user_reply] + list(
                (_next_eval.get("pv_after_best") or [])[:6]
            )
            if _user_reply.endswith("+") or _user_reply.endswith("#"):
                caption_facts["user_best_reply_san_is_forcing"] = True
            # WHY the recommended reply is good — every recommended move needs its why
            # (feedback_explain_why_recommended_move_good). "Play Bxe2" -> "Play Bxe2 —
            # it trades off his bishop." Board-verified; SEE-gated for material.
            try:
                from services.caption_facts import _recommended_move_why as _rmw
                from services.caption_facts import clearance_reply_why as _crw
                _reply_mv = _post_opp_board.parse_san(_user_reply)
                # A clearance beats the generic why, because the generic one
                # names the wrong motive. On Nf6+ (Mohit 2026-09-28)
                # _recommended_move_why returns "attacks the rook on e8":
                # true, and not why the move is played. The move is played to
                # get White's own knight off d5 so the rook on d1 reaches the
                # loose bishop. Only fires when the follow-up wins something.
                # The line AFTER our reply. It is on THIS move's record as
                # pv_after_played -- [reply, their answer, our payoff, ...] --
                # so the continuation is [1:].
                #
                # Two bugs found here, both by rendering the real game
                # rather than reasoning about it. The first version read
                # _next_eval["pv_after_best"] and got nothing, because an
                # opponent position has no engine entry of its own
                # (move_evaluations stores user moves only) -- so the
                # clearance abstained on exactly the cards it was written
                # for. The second read inputs.pv_after_played, which does not
                # exist in THIS function's scope; the NameError was swallowed
                # by the except below and took the whole narration block with
                # it, silently. Hence a real parameter.
                _reply_line = list(pv_after_played or [])[1:]
                _rwhy = _crw(
                    _post_opp_board,
                    _reply_mv,
                    _reply_line,
                    opp_cp_loss or 300,
                ) or _rmw(_post_opp_board, _reply_mv, line=_reply_line)
                if _rwhy:
                    caption_facts["opp_user_reply_why"] = _rwhy
                # WHY THEIR MOVE WAS THE MISTAKE, not just why ours is good.
                # Measured 2026-09-13: of 29,087 opponent mistake/inaccuracy
                # cards, 91% state a verdict and a move but never the reason.
                # When the reply leaves a piece with nowhere safe to go, say so
                # and give the geometry lesson that transfers.
                from services.caption_facts import (
                    _recommended_move_traps_piece as _rmtp,
                )
                # WHICH piece has no defender -- the scan Mohit asked for
                # (fb_f6050ba76406). Separate from the trapped-piece family: here the
                # piece is safe until they take back, and then nothing guards it.
                from services.caption_facts import (
                    _recapture_cost_target_is_undefended as _rctu,
                )
                _undef = _rctu(_post_opp_board, _reply_mv)
                if _undef:
                    caption_facts["opp_reply_exposes_undefended"] = True
                    caption_facts["opp_undefended_piece"] = _undef["piece"]
                    caption_facts["opp_undefended_square"] = _undef["square"]
                _trap = _rmtp(_post_opp_board, _reply_mv)
                if _trap:
                    caption_facts["opp_reply_traps_piece"] = True
                    caption_facts["opp_trapped_piece"] = _trap["piece"]
                    caption_facts["opp_trapped_square"] = _trap["square"]
                    caption_facts["opp_trapped_escape_count"] = _trap["escape_count"]
                    caption_facts["opp_trapped_on_rim"] = _trap.get("on_rim")
                    caption_facts["opp_trapped_lesson"] = _trap["lesson"]
            except Exception:
                pass
            if "x" in _user_reply:
                try:
                    _ur_move = _post_opp_board.parse_san(_user_reply)
                    _captured = _post_opp_board.piece_at(_ur_move.to_square)
                    if _captured:
                        # Only frame as "they drop the X / take it" when the
                        # user's capture actually WINS material — not an even
                        # trade. Parth fb_4e0609c302bb: "drop the pawn" misfired
                        # on c6 -> dxc6, an even pawn trade (engine even preferred
                        # O-O). Gate (SEE-lite, one ply): free (no recapturer) OR
                        # the captured piece is worth more than the capturing one.
                        _VAL = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3,
                                chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 100}
                        _b2 = _post_opp_board.copy()
                        _b2.push(_ur_move)
                        _recapturers = _b2.attackers(_b2.turn, _ur_move.to_square)
                        _atk_pt = _post_opp_board.piece_at(_ur_move.from_square)
                        _atk_val = _VAL.get(_atk_pt.piece_type, 0) if _atk_pt else 0
                        _victim_val = _VAL.get(_captured.piece_type, 0)
                        _wins_material = (not _recapturers) or (_victim_val > _atk_val)
                        if _wins_material:
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
        "opp_user_reply_unsafe_recapture_pawn_fork",
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

    # RETREAT detection — a developed piece fleeing a square the student attacks is a
    # RETREAT, not "development". Without this, a bishop chased home (Bg4 -> Bc8 after
    # h3) reads as "developing to an active diagonal" — the OPPOSITE of the truth, and
    # it dresses a forced passive retreat up as a good move. fb 2026-06-27.
    caption_facts["coach_move_is_retreat"] = False
    _mp = board_before.piece_at(move.from_square)
    if (_mp is not None and not is_castling
            and _mp.piece_type in (chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN)
            and not board_before.is_capture(move)):
        _val = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9}
        _pv = _val.get(_mp.piece_type, 0)
        _atk = board_before.attackers(student_color, move.from_square)
        _def = board_before.attackers(coach_color, move.from_square)
        _min_atk = min((_val.get(board_before.piece_at(s).piece_type, 0) for s in _atk), default=99)
        # Forced retreat: the piece sat on a square the student attacks with something
        # it can't safely ignore (a cheaper-or-equal attacker, or it's undefended).
        if _atk and (_min_atk <= _pv or not _def):
            caption_facts["coach_move_is_retreat"] = True
            caption_facts["coach_retreat_from"] = chess.square_name(move.from_square)
            caption_facts["coach_retreat_piece"] = chess.piece_name(_mp.piece_type)

    # SOUNDNESS — does the coach's move hang material (net SEE) to the student? A
    # "fork" / threat whose own piece can just be captured is NOT a threat — it's a
    # blunder, and we must never narrate it as a good double-attack ("Qxf6 — attacking
    # two of your pieces" while Bxf6 just wins the queen). Mohit 2026-06-27. The fork/
    # threat variants gate on this; an unsound coach move gets the honest overreach line.
    caption_facts["coach_move_is_sound"] = True
    try:
        from coach_play.coach_blunder_guard import material_hung_after
        _worst_hang, _ = material_hung_after(board_before, move)
        if _worst_hang >= 300:
            caption_facts["coach_move_is_sound"] = False
    except Exception:
        pass

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
            # Only surface a hanging/underdefended coach piece the student can
            # ACTUALLY take right now — there must be a LEGAL student move that
            # captures on that square. Drops pieces that are geometrically
            # attacked but uncapturable this move; the canonical case is the
            # student being in CHECK (only check-evasions are legal), where a
            # coach bishop on a3 reads as "undefended" yet Bxa3 is illegal. The
            # checker itself stays — e.g. Qxd8+ leaves the queen on d8 undefended
            # and Kxd8 is a legal evasion, so "capture the checker" is correct.
            # Verified on the Qxd8+ coach-card screenshot, 2026-06-25.
            _legal_capture_sqs = {
                m.to_square for m in board_after.legal_moves
                if board_after.is_capture(m)
            }
            hanging = [h for h in hanging if h.square in _legal_capture_sqs]
            underdefended = [
                h for h in underdefended if h.square in _legal_capture_sqs
            ]
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


# ── Verified-caption rollout flag ───────────────────────────────────
# docs/caption_production_rollout_scope.md. When true,
# inject_good_move_reason_facts may emit the board-verified "attacks"
# reason for near-best QUIET moves that create a real new threat on an
# enemy piece (the "a4 could be hitting a piece on b5" gap). Purely
# additive — only fires where the good-move cascade would otherwise be
# silent, so it changes nothing else. Default OFF; flip server-side after
# the measured coverage / zero-false-claims report. 2026-07-08.
_VERIFIED_CAPTIONS = os.getenv("VERIFIED_CAPTIONS", "false").strip().lower() in (
    "1", "true", "yes", "on",
)


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

    # 2) Pawn break — an advanced pawn push that attacks an enemy pawn. ONLY the
    #    d/e files are a true "fight for the center"; c/f and flank pushes (like
    #    f5 hitting g4) are PAWN BREAKS that open lines — calling those "fights
    #    for the center" was the mislabel Parth flagged (30.f5). Split by file and
    #    name the pawn being struck. 2026-06-23.
    if moved.piece_type == chess.PAWN:
        to_file = chess.square_file(move.to_square)   # 0=a .. 7=h
        to_rank = chess.square_rank(move.to_square)   # 0=rank1 .. 7=rank8
        advanced = (
            (mover_color == chess.WHITE and to_rank >= 3)  # rank 4+
            or (mover_color == chess.BLACK and to_rank <= 4)  # rank 5-
        )
        if advanced:
            try:
                after = board_before.copy()
                after.push(move)
                _hit_sq = next(
                    (sq for sq in after.attacks(move.to_square)
                     if (p := after.piece_at(sq)) is not None
                     and p.color != mover_color and p.piece_type == chess.PAWN),
                    None)
            except Exception:
                _hit_sq = None
            if _hit_sq is not None:
                if to_file in (3, 4):  # d, e — true center
                    caption_facts["good_move_reason"] = "central_break"
                else:                  # c/f + flank — a pawn break, not center
                    caption_facts["good_move_break_square"] = chess.square_name(_hit_sq)
                    caption_facts["good_move_reason"] = "pawn_break"
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
            # Routine develop captions get a board-verified specific (Parth's
            # terse "Slightly Better" bucket), in priority order:
            #   develop_complete  — no own minor left home (development finished)
            #   develop_eyes      — the piece newly aims at an enemy minor/major
            #   develop_castle_ready — the move makes castling legal (was not)
            #   develop           — generic fallback
            # All board-accurate, never a generic plan-guess. 2026-06-23.
            try:
                _post = board_before.copy(); _post.push(move)
                _start = ({chess.B1, chess.G1, chess.C1, chess.F1}
                          if mover_color == chess.WHITE
                          else {chess.B8, chess.G8, chess.C8, chess.F8})
                _home_minor = any(
                    (p := _post.piece_at(sq)) and p.color == mover_color
                    and p.piece_type in (chess.KNIGHT, chess.BISHOP)
                    for sq in _start)
                if not _home_minor:
                    # gold overclaimed this on 6.Nc6 (f8 bishop still home) and lost
                    # a Parth point — we only say it when it's literally true.
                    caption_facts["good_move_reason"] = "develop_complete"
                    return
                # Newly aims at an enemy NON-pawn piece (a real target)?
                _enemy = not mover_color
                _targets = []
                for _s in _post.attacks(move.to_square):
                    _p = _post.piece_at(_s)
                    if _p and _p.color == _enemy and _p.piece_type != chess.PAWN:
                        _targets.append((_s, _p.piece_type))
                if _targets:
                    _pval = {chess.QUEEN: 9, chess.ROOK: 5, chess.BISHOP: 3, chess.KNIGHT: 3}
                    _targets.sort(key=lambda x: -_pval.get(x[1], 0))
                    caption_facts["good_move_eyes_piece"] = chess.piece_name(_targets[0][1])
                    caption_facts["good_move_eyes_square"] = chess.square_name(_targets[0][0])
                    caption_facts["good_move_reason"] = "develop_eyes"
                    return
                # Did this move make castling legal when it wasn't before?
                _pre = any(board_before.is_castling(m) for m in board_before.legal_moves)
                _aft_board = _post.copy(); _aft_board.turn = mover_color
                _aft = any(_aft_board.is_castling(m) for m in _aft_board.legal_moves)
                caption_facts["good_move_reason"] = (
                    "develop_castle_ready" if (_aft and not _pre) else "develop")
            except Exception:
                caption_facts["good_move_reason"] = "develop"
            return

    # 12) ATTACKS — a near-best QUIET move (non-capture) that creates a NEW
    #     attack on an enemy piece worth pressuring (knight or better). Fills
    #     the gap the develop cascade misses: pawn pushes (a4 hitting a bishop
    #     on b5), rook/queen shifts, any-phase threats. Reaches here only when
    #     no earlier branch fired (purely additive — converts a silent good
    #     move into a teachable one). VERIFIED by construction, then re-checked
    #     (belt-and-suspenders): only set when board_after literally attacks an
    #     enemy piece on that square. Behind VERIFIED_CAPTIONS (default off) for
    #     measured rollout. 2026-07-08 — docs/caption_production_rollout_scope.md
    if _VERIFIED_CAPTIONS and not caption_facts.get("good_move_reason"):
        try:
            if not board_before.is_capture(move):
                _post2 = board_before.copy()
                _post2.push(move)
                _enemy2 = not mover_color
                _pval2 = {chess.QUEEN: 9, chess.ROOK: 5, chess.BISHOP: 3, chess.KNIGHT: 3}
                _before_atk = set(board_before.attacks(move.from_square))
                _best2 = None
                for _s in _post2.attacks(move.to_square):
                    _p = _post2.piece_at(_s)
                    if (_p and _p.color == _enemy2 and _p.piece_type in _pval2
                            and _s not in _before_atk):
                        if (_best2 is None
                                or _pval2[_p.piece_type] > _pval2[_post2.piece_at(_best2).piece_type]):
                            _best2 = _s
                if _best2 is not None:
                    _pp = _post2.piece_at(_best2)
                    # Independent re-verify of the exact claim we will render.
                    if (_pp and _pp.color == _enemy2
                            and _post2.is_attacked_by(mover_color, _best2)):
                        caption_facts["good_move_reason"] = "attacks"
                        caption_facts["good_move_attacks_piece"] = chess.piece_name(_pp.piece_type)
                        caption_facts["good_move_attacks_square"] = chess.square_name(_best2)
        except Exception:
            pass
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
    allow_fresh_engine_verification: bool = True,
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

    # Build problem_facts based on fundamental_violated.
    #
    # These are user-facing: R18 narratives used to embed them via
    # {socratic_problem_facts_joined}. They were inherited from
    # smart_coaching as notes written ABOUT the student in the third
    # person, and the only variants that ever fired did not use the
    # joined field, so nobody saw it. Wiring cognitive_gap into variant
    # selection made those variants fire and produced "Your king position
    # got weaker. Student's king is in danger" -- the internal note,
    # shown to the player, restating the sentence before it. The
    # narratives no longer embed the joined string (every one of the
    # seven simply repeated itself) and these are written in the voice we
    # actually speak in, so a future variant that does embed them is safe.
    problem_facts: List[str] = []
    hanging_piece_name: Optional[str] = None
    hanging_square_name: Optional[str] = None

    if fundamental == "check_opponents_move":
        problem_facts.append("you did not answer the threat their last move made")
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
                            f"your {hanging_piece_name} on "
                            f"{hanging_square_name} is attacked and nothing "
                            f"defends it"
                        )
                        break
        except Exception:
            pass
        if not problem_facts:
            problem_facts.append("you left a piece undefended")
    elif fundamental == "calculate":
        problem_facts.append("you did not work out their reply")
    elif fundamental == "king_safety":
        problem_facts.append("your king is in danger")
    elif fundamental == "development":
        problem_facts.append("you moved a piece that was already out instead of bringing a new one into the game")
    elif fundamental == "center_control":
        problem_facts.append("you gave up control of the middle squares")
    elif fundamental == "have_a_plan":
        problem_facts.append("this move does not do a job")

    # Coach intent context (when set by the v2 selector).
    coach_intent = caption_facts["socratic_coach_intent"]
    if coach_intent:
        intent_map = {
            "hanging_piece_punishment": "the coach set this up to see whether you would spot the loose piece",
            "fork_opportunity": "the coach set up a double attack for you to deal with",
            "threat_awareness": "the coach made a threat for you to notice",
        }
        if coach_intent in intent_map:
            problem_facts.append(intent_map[coach_intent])

    # If upstream labeled the fundamental "hanging_pieces" but no piece is
    # actually hanging on the post-move board (e.g. an endgame conversion
    # blunder mislabeled, like 52.g7 in the kiandraa10 R+P endgame), downgrade
    # it so R18 variant selection falls to the generic branch instead of a
    # hanging-piece variant that would reference the now-None piece/square.
    if fundamental == "hanging_pieces" and hanging_piece_name is None:
        # Nothing is actually hanging, so the hanging variants cannot speak --
        # they would reference a piece and square that are None. Rather than
        # dropping to the generic variant, ask the analyser what it decided was
        # wrong with this move. Measured over 400 games, 53.4% of the moves
        # that reach this surface carry a gap we can map; almost all of them
        # were arriving here and being thrown away.
        _gap_fallback = GAP_TO_FUNDAMENTAL.get(
            str(socratic_context.get("cognitive_gap") or "").strip().lower()
        )
        if _gap_fallback == "hanging_pieces":
            # The gap agrees with the label the board just refuted. Trust the
            # board.
            _gap_fallback = None
        caption_facts["socratic_fundamental_violated"] = _gap_fallback
        fundamental = _gap_fallback
        # Rebuild the evidence for whatever we landed on; the hanging-piece
        # attempt left either nothing or a generic "you left a piece
        # undefended" that no longer matches the variant about to render.
        problem_facts = []
        if fundamental == "calculate":
            problem_facts.append("you did not work out their reply")
        elif fundamental == "king_safety":
            problem_facts.append("your king is in danger")

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
            verify_engine = None
            if allow_fresh_engine_verification:
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

    # Opening move-type signal: a central pawn push (pawn to a c-f file, rank
    # 4-5) in the opening is "controlling the center", not "quiet repositioning".
    # Lets opening coach moves WITHOUT a v2 teaching intent get phase-appropriate
    # narration instead of the generic terminal. (Mohit 2026-06-08: the coach's
    # e5 was mislabelled "improving the piece's position".)
    mpt = caption_facts.get("moving_piece_type")
    tsq = caption_facts.get("target_square") or ""
    caption_facts["coach_pawn_central"] = bool(
        mpt == "pawn" and caption_facts.get("phase") == "opening"
        and len(tsq) == 2 and tsq[0] in "cdef" and tsq[1] in "45"
    )


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

    # opponent_opportunity — DISABLED 2026-06-26 (Coach Conductor LAW 1: state,
    # never ask / never spoil). This fed the frontend "Can you see it?" callout —
    # which is either a quiz ("can you see it?") or a spoiler ("you can win the
    # knight on d4"). Both pre-empt the player's own move. The coach lets the
    # player play, then catches a MISS after the move. Kept None so the field
    # stays in the shape; the detection still runs for the post-move thread.
    # docs/pwc_coach_conductor_scope.md.
    opponent_opportunity: Optional[Dict[str, Any]] = None

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
        # Cap at 3 per smart_coaching's slicing semantics. The plan templates
        # append this to a finished sentence, so it needs to end like one --
        # plans were shipping as "... Get your king safe - castle".
        _joined = "; ".join(str(p) for p in recovery_facts[:3] if p).strip()
        if _joined and _joined[-1] not in ".!?":
            _joined += "."
        caption_facts["socratic_recovery_facts_joined"] = _joined
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
            def __getitem__(self, key):
                # A present-but-None fact must render as "" — never the literal
                # string "None" (the kiandraa10 endgame leak: an R18 hanging
                # variant referenced {socratic_hanging_piece}/{square} that were
                # None → "Your None on None is now undefended"). 2026-06-22.
                try:
                    v = dict.__getitem__(self, key)
                except KeyError:
                    return ""
                return "" if v is None else v
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
    move_history_san: Optional[List[str]] = None,
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

    # v100 — canonical recognizer fallback (single source: opening_book). The
    # eco-based get_opening_introduction misses openings the move-history recognizer
    # knows (Scandinavian, Sicilian, ...) when the game lacked an ECO/name header.
    # Only when this move IS the latest book move (match_length == full length), so
    # we name the opening on the move that defines it, not on a later deviation.
    # Memory project_opening_recognizer_canonical.
    if not caption_facts.get("opening_intro_name") and move_history_san is not None:
        try:
            from services.decryption_voice.opening_book import (
                recognize_opening_from_history,
            )
            _full = list(move_history_san) + [move_san]
            _rec = recognize_opening_from_history(_full)
            if _rec and _rec.get("caption") and _rec.get("match_length") == len(_full):
                _cap = _rec["caption"].strip()
                _nm, _, _idea = _cap.partition(". ")
                if _nm:
                    caption_facts["opening_intro_name"] = _nm
                if _idea:
                    caption_facts["opening_intro_idea"] = _idea.strip()
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

    if shape_pattern_record:
        try:
            from services.detector_quality import (
                QualitySurface as _QualitySurface,
                can_influence as _can_detector_influence,
                shape_quality_id as _shape_quality_id,
            )
            if not _can_detector_influence(
                _shape_quality_id(shape_pattern_record.get("pattern_id", "")),
                _QualitySurface.CAPTION,
            ):
                shape_pattern_record = None
        except Exception:
            shape_pattern_record = None

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
        # Mohit Day 3 Issue A (2026-05-30): cut to TOP-1 fact only. The
        # board_state_clause appears either (a) as a why-clause tail after
        # "X is a mistake. Y was better." or (b) as the standalone
        # caption when nothing else fires. In case (a), multiple bs
        # facts read as a stat dump ("Your bishop on h6 is alone in
        # opponent territory. Opponent attacks the center 4 times; you
        # attack it 1 time.") that doesn't explain the actual mistake.
        # In case (b), one strong fact is more readable than three weak
        # ones concatenated. Was n=3, max_per_category=2.
        _top = select_top_facts(_bs_facts, n=1, max_per_category=1)
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


def _extract_caption_severity_word(caption_text: str) -> Optional[str]:
    """Pull the severity WORD out of a rendered R12 caption.

    Mohit 2026-05-31 (Lab board-badge alignment): R12 picks a tier via
    severity_tiers rules (with bumps for played_smaller_win, canonical-
    mistake-stayed-balanced, etc.) and renders one of the fixed
    severity_phrases. The TIER itself isn't exposed as a structured
    field anywhere — only the rendered text contains the verdict word.

    Downstream surfaces (Lab badge, mastery cards) need that word to
    keep their visual classification in sync with the caption text.
    Easiest: parse the fixed phrases here, expose the result on
    TeachingMeta.caption_severity_word.

    Returns one of {"blunder", "mistake", "inaccuracy"} when R12
    produced a severity caption, or None for clean / R15 / opening /
    silent captions. "serious mistake" maps to "mistake" because the
    consumers (badge palette, mastery filters) don't have a separate
    "serious" bucket.

    The phrases match R12_blunder.json severity_phrases:
      blunder    -> "is a major blunder"
      serious    -> "is a serious mistake"
      mistake    -> "is a mistake"
      inaccuracy -> "is an inaccuracy"
    """
    if not caption_text:
        return None
    t = caption_text.lower()
    if "is a major blunder" in t:
        return "blunder"
    if "is a serious mistake" in t:
        return "mistake"
    if "is a mistake" in t:
        return "mistake"
    if "is an inaccuracy" in t:
        return "inaccuracy"
    return None


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


_PHASE2_ATTACKS_RE = __import__("re").compile(
    r"\battacks?\s+(?:the\s+)?(?:undefended\s+)?"
    r"(king|queen|rook|bishop|knight|pawn)"
    r"\s+on\s+([a-h][1-8])\b",
    flags=__import__("re").IGNORECASE,
)


def _verify_phase2_attack_claims(
    *,
    caption_text: str,
    fen_before: str,
    best_move_san: Optional[str],
    pv_after_best: List[str],
) -> Optional[Tuple[str, str]]:
    """Phase 2 semantic check: when the caption claims that best_move
    attacks the {piece} on {square}, verify the claim survives the
    natural opp reply (PV[1] of pv_after_best). Returns (claim_text,
    fail_reason) on the first failed claim, or None when all claims
    pass / no claims found.

    No engine spawn — uses pv_after_best already on MoveInputs (computed
    at analysis time at higher depth). When PV is empty / best_move is
    None, returns None (cannot verify -> trust the detector).

    Catches the Bxc6/b7 class at the CAPTION layer as a backstop: if a
    detector misses the survival check (today: active_defense /
    same_piece_better_square / pawn_kicks_piece all have it; future
    detectors may not), this still catches the illusory claim.
    """
    if not caption_text or not best_move_san or not pv_after_best:
        return None
    if len(pv_after_best) < 2:
        return None  # need opp's reply to verify

    matches = list(_PHASE2_ATTACKS_RE.finditer(caption_text))
    if not matches:
        return None

    try:
        board = chess.Board(fen_before)
        bm = board.parse_san(best_move_san)
        board.push(bm)
        opp_reply = board.parse_san(pv_after_best[1])
        board.push(opp_reply)
    except Exception:
        return None  # PV parse failure — trust the detector

    bm_to_sq = bm.to_square

    for m in matches:
        piece_name = m.group(1).lower()
        sq_name = m.group(2).lower()
        try:
            claimed_sq = chess.parse_square(sq_name)
        except Exception:
            continue

        # 1. Is the mover (best_move's piece) still on the board after
        #    opp's PV[1] reply? If not, "X attacks Y" is illusory.
        piece_at_dest = board.piece_at(bm_to_sq)
        if piece_at_dest is None:
            return (
                m.group(0),
                f"best_move's piece doesn't survive opp's {pv_after_best[1]} "
                f"(captured) — 'attacks the {piece_name} on {sq_name}' is illusory",
            )

        # 2. Does the mover still ATTACK the claimed square?
        attacks_now = board.attacks(bm_to_sq)
        if claimed_sq not in attacks_now:
            return (
                m.group(0),
                f"best_move's piece on {chess.square_name(bm_to_sq)} no longer "
                f"attacks {sq_name} after opp's {pv_after_best[1]}",
            )

        # 3. Is the target piece still on the claimed square?
        target_piece = board.piece_at(claimed_sq)
        if target_piece is None:
            return (
                m.group(0),
                f"no piece on {sq_name} after opp's {pv_after_best[1]} — "
                f"'attacks the {piece_name} on {sq_name}' is illusory",
            )

    return None


def _verify_and_recover_caption(
    *,
    caption_payload: Dict[str, Any],
    fen_before: str,
    played_move: chess.Move,
    user_color: str,
    played_san: str,
    best_move_san: Optional[str],
    pv_after_best: List[str],
    severity_practical: str,
    mover_is_user: bool,
) -> Optional[Dict[str, Any]]:
    """Post-render board-grounding check.

    Mohit 2026-05-30 "wire it in": every rendered caption gets a Phase 1
    audit against the post-played-move FEN. If a piece-on-square claim
    is hallucinated (or wrong piece type / wrong color), the variant is
    REPLACED — not silenced — by a bare severity caption that makes
    only the irreducibly-true claims (the SAN that was played, the
    severity tier, optionally the best move SAN).

    Recovery chain when verify fails:
      1. Bare R12-style severity caption — never references squares or
         piece counts, so it cannot hallucinate.
      2. If no severity / no best move (clean move): "{played_san}." —
         factual mention only.

    Returns a telemetry dict for every path. verdict is pass,
    fail_recovered, not_applicable, or not_run. This lets persistent
    concept events distinguish verified evidence from silence.

    The verifier itself is the one from scripts/content_correctness_audit.
    Mutates caption_payload in place; raising is OK (the caller has a
    try/except that preserves the original on crash).
    """
    text_in = (caption_payload.get("caption") or "").strip()
    if not text_in:
        return {"verdict": "not_applicable", "reason": "empty_caption"}

    # Build the post-played-move board (Phase 1 claims like "your queen
    # on a7" reference the position AFTER the played move, which is what
    # the player sees in the UI).
    try:
        post_board = chess.Board(fen_before)
        post_board.push(played_move)
        fen_after = post_board.fen()
    except Exception:
        return {"verdict": "not_run", "reason": "invalid_position_or_move"}

    try:
        from scripts.content_correctness_audit import audit_text_against_fen
    except Exception:
        return {"verdict": "not_run", "reason": "verifier_unavailable"}

    try:
        audit = audit_text_against_fen(
            text=text_in,
            fen=fen_after,
            user_color=user_color or "white",
            engine=None,  # Phase 1 (piece-on-square) only
        )
    except Exception:
        return {"verdict": "not_run", "reason": "verifier_error"}

    phase1_failed = (audit.overall == "fail")

    # Phase 2 (semantic): check "best_move attacks X on Y" survives opp PV[1].
    # No engine spawn — uses cached pv_after_best from MoveInputs (computed
    # at analysis-time depth in analysis_worker, OR by PWC's coach_opponent
    # which was about to run engine anyway). Render cost stays at ~50ms.
    phase2_fail: Optional[Tuple[str, str]] = None
    if not phase1_failed:
        # Only check Phase 2 when Phase 1 passed — if Phase 1 already failed
        # we'll recover anyway; no point doing more work.
        try:
            phase2_fail = _verify_phase2_attack_claims(
                caption_text=text_in,
                fen_before=fen_before,
                best_move_san=best_move_san,
                pv_after_best=pv_after_best or [],
            )
        except Exception:
            phase2_fail = None  # verifier crash — leave caption alone

    if not phase1_failed and phase2_fail is None:
        return {
            "verdict": "pass",
            "phase1": "pass",
            "phase2": "pass",
        }

    # Build the recovery caption — bare severity, no piece claims.
    _severity_phrases = {
        "blunder": "is a major blunder",
        "serious": "is a serious mistake",
        "mistake": "is a mistake",
        "inaccuracy": "is an inaccuracy",
    }
    sev_phrase = _severity_phrases.get((severity_practical or "").lower(), "")
    if mover_is_user and sev_phrase and best_move_san and best_move_san != played_san:
        recovery = f"{played_san} {sev_phrase}. {best_move_san} was better."
    elif mover_is_user and sev_phrase:
        recovery = f"{played_san} {sev_phrase}."
    elif (not mover_is_user) and sev_phrase:
        recovery = f"Opponent's {played_san} {sev_phrase}."
    elif best_move_san and best_move_san != played_san:
        # No phrase, but there IS a stronger move. `severity_practical` reads
        # "good" on plenty of cards the canonical tier calls a mistake (the two
        # tiers come from different classifiers), and every one of those used to
        # land on the bare "Nxh3." below -- a caption that says nothing at all,
        # which is the silence the coverage rule exists to prevent. Measured
        # 2026-09-30: 171 cards corpus-wide rendered as a lone SAN.
        #
        # Naming the stronger move asserts no verdict, and this function's own
        # contract already lists the best-move SAN among the irreducibly-true
        # claims recovery may make. It is strictly more than the SAN alone.
        recovery = (f"{played_san}. {best_move_san} was stronger here."
                    if mover_is_user
                    else f"Opponent's {played_san}. {best_move_san} was stronger.")
    else:
        # Clean move OR no severity and no alternative — acknowledge the SAN.
        recovery = f"{played_san}."

    prev_rule = caption_payload.get("rule_name") or "R_FALLBACK"
    failed_claims = [
        f"[{c.kind}] {c.text!r}: {c.detail}"
        for c in audit.claims if c.verdict == "fail"
    ]
    if phase2_fail is not None:
        failed_claims.append(f"[phase2_attack] {phase2_fail[0]!r}: {phase2_fail[1]}")
    logger.info(
        f"[caption_verifier] FAIL on '{text_in[:80]}' "
        f"(rule={prev_rule}): {'; '.join(failed_claims[:3])} "
        f"-> '{recovery}'"
    )
    caption_payload["caption"] = recovery
    caption_payload["rule_name"] = f"{prev_rule}→R_VERIFIER_RECOVERY"
    return {
        "original_text": text_in,
        "verdict": "fail_recovered",
        "recovery_text": recovery,
        "failed_claims": failed_claims,
    }


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
            # A generic Tier-2/3 never-silence FLOOR (R_TIER*) is a placeholder,
            # not a "real" caption — let the specific promotion fills (shape /
            # principle) override it. Otherwise the baked-in tier floor shadows
            # endgame-aware principles, e.g. a king move getting the WRONG "tidy
            # up the king, keeping it safe" instead of END_KING_ACTIVE's "Activate
            # the king." basic_mistake is cp-gated (>=50) so it can't fire on a
            # good move. 2026-06-23.
            "caption_empty": (
                not bool(caption_payload.get("caption"))
                or str(caption_payload.get("rule_name") or "").startswith("R_TIER")
            ),

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
            # Mohit 2026-05-28: per-step trap teaching. The trap_line_steps
            # in traps.json carry an `explanation` per move; this surfaces
            # the explanation for the current step so the punisher steps
            # (axb5, Qf3, etc.) celebrate the trap completion instead of
            # falling back to a generic 'takes the pawn' / 'threatens the
            # rook' caption. Game 65650b2b m6 Qf3: trap state active but
            # the winning move taught nothing.
            "trap_step_label": (trap_record or {}).get("step_label") or "",
            "trap_step_explanation": (trap_record or {}).get("step_explanation") or "",

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

# Distilled-caption rollout flag (default OFF). When "1"/"true", the caption TEXT is
# replaced by the validated distilled-template render (services.distilled_caption_service)
# when available; otherwise the existing R12 cascade caption is kept. Flip per env on the
# server for a flag-gated rollout (off -> 10% -> 100%). See docs/caption_distillation_*.md.
_DISTILLED_CAPTIONS_ENABLED = os.environ.get("DISTILLED_CAPTIONS_ENABLED", "0") not in ("0", "false", "False", "")
_CAUSAL_PERSONAL_CAPTIONS_ENABLED = os.environ.get(
    "CAUSAL_PERSONAL_CAPTIONS_ENABLED", "0"
) not in ("0", "false", "False", "")


_SALVAGE_SPLIT_RE = _re_pb.compile(r"(?<=[.!?])\s+")

# "X was better — <Capitalised sentence>" is a broken join. The em-dash slot
# promises a reason for the move just named and expects a lower-case verb
# phrase ("it defends the pawn on f2"); some why-variants are standalone
# sentences, which renders:
#
#   "Bc7 was better — This spot got hard a few moves ago, around move 12."
#
# The dash promises a why and delivers a topic change. 23 of 1127 flagged
# mistakes in one user's corpus shipped this shape. A SAN after the dash is
# fine and common ("— Kh2 lets Qh5+ come in with check"), so SAN tokens are
# excluded. 2026-09-06.
_DASH_BEFORE_SENTENCE_RE = _re_pb.compile(
    r"\s+[—–]\s+(?=(?!(?:O-O(?:-O)?|[KQRBN][a-h]?[1-8]?x?[a-h][1-8])\b)[A-Z][a-z]{2,})")


def _repair_dash_before_sentence(text: str) -> str:
    """Turn a dash that introduces a full sentence into a full stop."""
    if not text:
        return text
    return _DASH_BEFORE_SENTENCE_RE.sub(". ", text)


# Verdict without evidence. R12 already refuses to assert on this exact shape —
# its trigger note: "User-side low-cp moves stay silent via suppression
# (mover_is_user:true + why_clause:absent + cp_loss<250)". The fallback paths
# (R_PROMOTED_basic_mistake, R16_board_state_fallback, HELD_FLOOR) never got
# that rule, so 362 captions in one user's corpus still announced "X is a
# mistake" with no reason attached — 70% of them at cp 100-199. Telling a
# 1000-1300 player they blundered and then going quiet is worse than not
# calling it a blunder.
#
# Same threshold as R12 on purpose (feedback_single_source_of_truth): this is
# not a new judgement about what counts as a mistake, it is the existing one
# applied where it was missing. Above the bar the verdict stays — a real
# blunder must be named even when we cannot explain it.
_VERDICT_NO_EVIDENCE_CP = 250
_VERDICT_RE = _re_pb.compile(
    r"\bis (?:a|an) (?:major blunder|serious mistake|mistake|inaccuracy)\b",
    _re_pb.IGNORECASE)


# Only the hollow TEMPLATE shape may be softened. The consequence check below
# is a keyword list, and prose captions explain in words it does not contain -
# "Nxf7 is a mistake — you moved your knight away from defending e4" earns its
# verdict without matching a single keyword. Softening that produced "Nxf7 is
# playable — you moved your knight away from defending e4", which calls the
# move fine and then explains why it isn't. Shipped 2026-09-07, caught the same
# day by reading the softened output.
#
# So the rule is inverted: soften only when the caption is demonstrably the
# hollow shape (verdict + "X was better" + optional principle), never merely
# when no keyword matched. Cut taken from the corpus - softened template
# captions ran 46-160 chars (median 133) while every wrongly-softened prose
# caption ran 217-402.
_VERDICT_SOFTEN_MAX_CHARS = 180
_VERDICT_SOFTEN_MAX_SENTENCES = 3


def _soften_verdict_without_evidence(text: str, *, mover_is_user: bool,
                                     cp_loss: int) -> str:
    """Drop the mistake verdict when nothing in the caption justifies it."""
    if not text or not mover_is_user:
        return text
    if abs(int(cp_loss or 0)) >= _VERDICT_NO_EVIDENCE_CP:
        return text
    if not _VERDICT_RE.search(text):
        return text
    # A caption that names a consequence HAS justified its verdict.
    if _SALVAGE_CONTENT_RE.search(text):
        return text
    # Anything longer or more elaborate than the hollow template is presumed to
    # be explaining itself in prose the keyword list cannot see. Leave it alone:
    # a verdict wrongly kept is a smaller harm than a verdict wrongly removed
    # from a caption that goes on to justify it.
    if len(text) > _VERDICT_SOFTEN_MAX_CHARS:
        return text
    if len([s for s in _SALVAGE_SPLIT_RE.split(text.strip()) if s.strip()]) > \
            _VERDICT_SOFTEN_MAX_SENTENCES:
        return text
    return _VERDICT_RE.sub("is playable", text)

# A salvaged caption has to still teach. A lone verdict ("Qf6 is a mistake.")
# or a bare principle carries no board content, so it is not worth keeping over
# the deterministic floor — the floor at least names the stronger move.
_SALVAGE_CONTENT_RE = _re_pb.compile(
    r"\b(lets|loses to|drops|hangs|leaves|allows|walks into|wins|attacks|"
    r"defends|traps|captures|forks|pins|threatens|recaptures|undefended)\b",
    _re_pb.IGNORECASE)


def _salvage_verified_sentences(text: str, verify_fn) -> str:
    """Keep the sentences of `text` that pass `verify_fn`; drop the rest.

    Returns "" when nothing worth shipping survives, in which case the caller
    falls through to the deterministic floor as before.

    This exists because the claim verifier is a whole-caption gate: a single
    false clause discards the true ones with it. Salvage is strictly
    truth-preserving — every surviving sentence individually passed the same
    verifier, and the rejoined text is verified again before it is returned.
    """
    if not text or not text.strip():
        return ""
    sentences = [s.strip() for s in _SALVAGE_SPLIT_RE.split(text.strip()) if s.strip()]
    if len(sentences) < 2:
        return ""  # nothing to salvage from a single failing sentence

    kept = [s for s in sentences if not verify_fn(s)]
    if not kept or len(kept) == len(sentences):
        # len(kept) == len(sentences) means every sentence passes alone but the
        # whole fails — a cross-sentence contradiction. Do not ship that.
        return ""

    if not any(_SALVAGE_CONTENT_RE.search(s) for s in kept):
        return ""

    joined = " ".join(kept)
    if verify_fn(joined):
        return ""
    return joined


def _normalize_san_for_match(san: Optional[str]) -> str:
    """Compare SAN ignoring check/mate marks so b4 matches b4+."""
    return str(san or "").replace("+", "").replace("#", "").replace(
        "!", "").replace("?", "").strip()


def _check_attack_arrows(
    board_before: Optional[chess.Board],
    best_move_uci: Optional[str],
    engine_line: Optional[Sequence[str]] = None,
) -> List[Dict[str, str]]:
    """Draw the two-attackers-plus-check picture, or nothing.

    Mohit 2026-09-17, on fb_1c52480b2e9b: "it should draw a line from Qa5 to
    [the] bishop and our bishop to [the] bishop and a queen checking the king,
    so it's easy." The words for that move ("gives check and wins the bishop
    on e5") name the fact; the board is what makes the geometry obvious -- two
    lines converging on one square, and a third into the king that says why
    the defender never gets a turn.

    The MOVE was always the engine's. The TARGET, until v181, was not: it was
    the best ``static_exchange_eval`` square on the after-board, and SEE does
    not count king recaptures, so a piece guarded only by the king scored as
    winnable. Mohit 2026-09-28: "it should only draw lines on stockfish backed
    move, right? that's what will make people understand the plan, right?"
    He is right, and the rule has to cover the claim as well as the move.

    Measured 2026-09-28 over 400 games / 461 cards this fired on, checking the
    arrowed square against the engine's OWN stored line:

        engine's line does take the arrowed piece      38
        engine's line never takes it                   94   (71%)
        no stored line available                      329

    and Stockfish run fresh at depth 16 on 60 of those 329 said 41 (68%) point
    at a piece it never takes either. One of the plainest: on move 13 of
    ef9f422a062d the engine plays Bxf3 Bxf3 Qxf3 Qxa1, winning the ROOK ON A1,
    while the green arrows converged on e1.

    So the target now comes from the line: the first piece our own side
    captures in it. 461 pictures become 203, every one of them the engine's
    plan rather than ours, and where both draw the target moves on 48 of 85 --
    the old square was wrong more often than right.

    Supporting arrows are legal captures, not ``attackers()`` hits: that set
    is pseudo-legal and a pinned piece put 5 undeliverable arrows on the board.
    """
    if board_before is None or not best_move_uci or not engine_line:
        return []
    try:
        move = chess.Move.from_uci(str(best_move_uci))
        if move not in board_before.legal_moves:
            return []
        mover = board_before.turn
        after = board_before.copy()
        after.push(move)
        if not after.is_check():
            return []

        # Walk the engine's line and stop at the first thing WE take.
        walk = after.copy()
        target_sq = None
        for san in engine_line:
            try:
                step = walk.parse_san(str(san))
            except (ValueError, AssertionError):
                break
            if walk.turn == mover and walk.is_capture(step):
                victim = walk.piece_at(step.to_square)
                if victim is not None and victim.piece_type != chess.KING:
                    target_sq = step.to_square
                    target_piece = victim
                    break
            walk.push(step)
        if target_sq is None:
            return []
        # The arrow is drawn on the board right after the best move, so the
        # piece it points at has to be standing there THEN. Measured
        # 2026-09-28: 61 of 203 lines capture on a square that only becomes
        # occupied later, which draws an arrow into an empty square -- the
        # same "pointing at nothing" complaint in a new disguise.
        standing = after.piece_at(target_sq)
        if (
            standing is None
            or standing.color == mover
            or standing.piece_type != target_piece.piece_type
        ):
            return []

        king_sq = after.king(not mover)
        if king_sq is None:
            return []

        arrows: List[Dict[str, str]] = [{
            "from": chess.square_name(move.to_square),
            "to": chess.square_name(target_sq),
            "color": "green",
            "teach": True,
        }]
        # The attackers that were ALREADY there are the reason the square
        # tips: one new attacker on an undefended piece is an ordinary
        # threat, a second attacker on a defended one is what wins it.
        for sq in sorted(after.attackers(mover, target_sq)):
            if sq == move.to_square or len(arrows) >= 3:
                continue
            # A pinned piece is in the attackers() set and cannot actually
            # make the capture, which is how arrows for illegal moves shipped.
            if after.is_pinned(mover, sq):
                continue
            arrows.append({
                "from": chess.square_name(sq),
                "to": chess.square_name(target_sq),
                "color": "green",
                "teach": True,
            })
        arrows.append({
            "from": chess.square_name(move.to_square),
            "to": chess.square_name(king_sq),
            "color": "red",
            "teach": True,
        })
        return arrows
    except Exception:
        return []


def _reply_attack_arrows(
    board_before: Optional[chess.Board],
    played_move: Optional[chess.Move],
    user_reply_san: Optional[str],
) -> List[Dict[str, str]]:
    """Show the reply the card recommends: the move, and what it threatens.

    On an opponent card the words are addressed to the player -- "Play d5 --
    your pawn kicks their knight on c6" -- and that reply is legal on the board
    AFTER the opponent moved, which is the board the card renders. So this is
    the one board on which the picture and the caption mean the same move.

    Mohit 2026-09-23, on an inaccuracy card that drew nothing: "did we not talk
    about inaccuracies too? Why is missing there?" The picture used to come
    from _check_attack_arrows, which requires the move to give CHECK. d5 really
    does attack the knight on c6 -- SEE 200, board-verified -- it just is not a
    check, so the card said "Play d5" and left the player to find d5 themselves.
    A check is what makes a threat unanswerable; it is not what makes it worth
    drawing.

    Right-or-silent. Every target is proved winnable by SEE on the board after
    the reply, at most two of them plus the check, and the move arrow comes
    first so the picture starts on a piece the player can see. Measured over
    500 games: 50.5% of opponent cards draw, 77% of those with just two arrows
    and never more than four.
    """
    if board_before is None or played_move is None or not user_reply_san:
        return []
    try:
        after_opp = board_before.copy()
        after_opp.push(played_move)
        reply = after_opp.parse_san(str(user_reply_san))
        after_reply = after_opp.copy()
        after_reply.push(reply)
    except Exception:
        return []

    mover = after_opp.turn
    targets: List[Tuple[int, int]] = []
    for square in after_reply.attacks(reply.to_square):
        piece = after_reply.piece_at(square)
        if not piece or piece.color == mover or piece.piece_type == chess.KING:
            continue
        see = static_exchange_eval(after_reply, square, mover) or 0
        if see >= 100:
            targets.append((square, see))

    gives_check = after_reply.is_check()

    # A capture that wins material IS the point, even when the piece lands
    # somewhere that threatens nothing afterwards.
    #
    # Mohit 2026-10-05, on an opponent card reading "Bc5 leaves the bishop on
    # c5 hanging -- you can win it with bxc5" and drawing nothing at all: "also,
    # no arrow here, why the hell, i am getting angry". He is right to be. On
    # `B2k1b1r/7p/R5p1/5p2/1Pnp1B2/8/6PP/6K1 b` the reply bxc5 takes an
    # undefended bishop; the pawn then sits on c5 attacking b6 and d6, both
    # empty, and gives no check -- so every gate below failed and the card that
    # names a free piece drew no line to it.
    #
    # The old shape only ever asked "what does the reply threaten NEXT", which
    # is the right question for a quiet move and the wrong one for a capture,
    # where the material is already won on arrival.
    wins_material = False
    if after_opp.is_capture(reply):
        try:
            wins_material = legal_exchange_gain(
                after_opp, reply.to_square, mover, first_move=reply
            ) >= 100
        except (ValueError, TypeError):
            wins_material = False

    if not targets and not gives_check and not wins_material:
        return []

    # The MOVE first. _check_attack_arrows draws from the square the piece
    # lands on, which on this board is still empty -- the reply has not been
    # played. That left a line starting in mid-air and ending on the opponent's
    # piece, which is what "the arrwo shoed on opoponent queen" describes.
    arrows: List[Dict[str, str]] = [{
        "from": chess.square_name(reply.from_square),
        "to": chess.square_name(reply.to_square),
        "color": "blue",
        "teach": True,
    }]
    for square, _see in sorted(targets, key=lambda t: -t[1])[:2]:
        arrows.append({
            "from": chess.square_name(reply.to_square),
            "to": chess.square_name(square),
            "color": "green",
            "teach": True,
        })
    if gives_check:
        king_square = after_reply.king(not mover)
        if king_square is not None:
            arrows.append({
                "from": chess.square_name(reply.to_square),
                "to": chess.square_name(king_square),
                "color": "red",
                "teach": True,
            })
    seen = set()
    deduped = []
    for a in arrows:
        key = (a["from"], a["to"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(a)
    return deduped


# ─── One rule for drawing the engine's line ──────────────────────────
#
# Mohit 2026-10-06, after the fifth arrow fix in a row: "why we are not able to
# show up the full idea, do we have to do it for all positions?? i thought you
# understood the idea".
#
# He was right. This file had eight arrow builders chosen between at 22 call
# sites, four of them written that same day, each in answer to one screenshot.
# Every new card shape found another gap because the eighth builder repeated
# the first one's bug instead of sharing its logic: only winning_plan_arrows
# could follow a victim's flight, only it tracked our piece's route, only it
# refused to call a trade a win, and only _line_sequence_arrows knew that a
# sacrifice is drawn through to its recapture.
#
# His rule, which covers every case: take the engine's line from here and draw
# it to its payoff -- the move, the forced replies, and the capture or mate
# that is the point.
#
# docs/one_line_drawing_rule_scope.md carries the full reasoning and the list
# of behaviours that must not regress.

_PAYOFF_MATE = 4
_PAYOFF_RECAPTURE = 3
_PAYOFF_MATERIAL = 2
_PAYOFF_FORCING = 1


def walk_engine_line(
    board: Optional[chess.Board], line: Optional[Sequence[str]]
) -> List[tuple]:
    """Replay a SAN line from `board`, one tuple per ply.

    (ours, move, captured_piece_type, gives_check, is_mate). Stops at the first
    move that will not parse rather than discarding what already verified -- a
    Stockfish PV is legal by construction, but a truncated or mis-stored one
    should cost the tail, not the plies already proved.
    """
    if board is None or not line:
        return []
    probe = board.copy()
    us = probe.turn
    steps: List[tuple] = []
    for san in line:
        try:
            move = probe.parse_san(str(san))
        except (ValueError, AssertionError):
            break
        # En passant takes a pawn that is NOT on the destination square, so
        # piece_at(to_square) is None and the capture vanishes. Caught by
        # diffing 11,890 corpus rows against the pre-refactor snapshot: four
        # sequences lost their payoff entirely, every one of them ending in an
        # e.p. capture (h4xg3, exd6, dxc6, bxa3).
        if probe.is_en_passant(move):
            captured = chess.Piece(chess.PAWN, not probe.turn)
        else:
            captured = probe.piece_at(move.to_square) if probe.is_capture(move) else None
        gives_check = probe.gives_check(move)
        after = probe.copy()
        after.push(move)
        steps.append((
            probe.turn == us,
            move,
            captured.piece_type if captured else None,
            gives_check,
            after.is_checkmate(),
        ))
        probe.push(move)
    return steps


def find_line_payoff(
    board: Optional[chess.Board],
    steps: List[tuple],
    max_arrows: int = 5,
) -> Optional[tuple]:
    """Which ply is the point of the line, and why. (index, kind) or None.

    Ranked, because the same line can satisfy several and the strongest one is
    the lesson:

      mate       the move ends the game
      recapture  our first move gave material away on its own square and a
                 later capture of ours wins it back -- the sacrifice case,
                 where stopping at the first check showed a bishop given away
                 for a check (Mohit, the Ng5 card)
      material   our capture worth a knight or more that leaves us net ahead;
                 the net test is what stops a queen TRADE reading as winning a
                 queen (Qd3 Qxd3 Nxd3)
      forcing    a check or capture of ours, when nothing above applies
    """
    if not steps:
        return None

    for idx, (ours, _mv, _cap, _chk, is_mate) in enumerate(steps):
        if ours and is_mate:
            return (idx, _PAYOFF_MATE)

    sacrificed = False
    if board is not None and steps and steps[0][0]:
        first = steps[0][1]
        if board.is_capture(first):
            try:
                gain = legal_exchange_gain(
                    board, first.to_square, board.turn, first_move=first
                )
                sacrificed = gain is not None and gain < 0
            except (ValueError, TypeError):
                sacrificed = False
    if sacrificed:
        for idx, (ours, _mv, cap, _chk, _m) in enumerate(steps):
            if idx >= 2 and ours and cap is not None and idx <= max_arrows:
                return (idx, _PAYOFF_RECAPTURE)

    best_idx = None
    best_value = 0
    for idx, (ours, _mv, cap, _chk, _m) in enumerate(steps):
        if not ours or cap is None:
            continue
        value = PIECE_VALUE_CP.get(cap, 0)
        if value >= 320 and value > best_value:
            best_idx, best_value = idx, value
    if best_idx is not None:
        net = 0
        for ours, _mv, cap, _chk, _m in steps[: best_idx + 1]:
            if cap is None:
                continue
            value = PIECE_VALUE_CP.get(cap, 0)
            net += value if ours else -value
        if net >= 300:
            return (best_idx, _PAYOFF_MATERIAL)

    for idx, (ours, _mv, cap, chk, _m) in enumerate(steps):
        if idx >= 2 and ours and (cap is not None or chk):
            return (idx, _PAYOFF_FORCING)
    return None


def _line_sequence_arrows(
    board_after_opp: Optional[chess.Board],
    pv: Optional[List[str]],
    max_arrows: int = 5,
) -> List[Dict[str, str]]:
    """Draw the whole idea when the point of the move lands two moves later.

    Mohit 2026-09-26, on a card where the knight move and the rook that wins
    the bishop were never connected: "could have also drawn a line between
    rook and bishop, as rook takes it up... i would love to do that for moves
    that shows the complete line."

    The position: white knight on d5 blocks white's own rook on d1, and
    Black's bishop on d6 is undefended. Nf6+ forces gxf6, the knight leaves
    d5, and NOW Rxd6 wins the bishop. Engine best, +411. The old picture drew
    what the knight attacks from f6, which is true and is not the point.

    Colours carry the sequence, which is Mohit's second suggestion and the
    thing that makes this honest:

        blue      your move
        paleGrey  their forced reply
        green     your payoff -- the capture the whole line was for

    Drawing the reply matters. Without it the rook arrow describes a path
    that is BLOCKED on the board in front of the player, by their own knight,
    and a picture that is only true two plies from now is the exact bug this
    file spent 2026-09-22 removing. With the reply drawn, the three arrows
    read as an order of events rather than a claim about the current board.

    Fires only when the payoff is DELAYED. Measured over 198 opponent-mistake
    cards carrying a 3+ ply line: 78 win material on our very first move and
    are already drawn correctly by the single-move builders, 48 have the
    delayed shape this is for, and 72 never capture at all.
    """
    if board_after_opp is None or not pv:
        return []

    # The walk and the payoff choice now live in one place, shared with every
    # other line-drawing builder. See the note above walk_engine_line.
    _steps = walk_engine_line(board_after_opp, pv)
    if not _steps:
        return []
    # `us` is still needed below, for the sacrifice test. Dropping it when the
    # walk moved out is exactly the undefined-name slip this file warns about
    # three functions up, and it cost 8 tests.
    us = board_after_opp.turn
    steps: List[tuple] = [
        (ours, chess.square_name(mv.from_square), chess.square_name(mv.to_square),
         cap is not None, chk)
        for ours, mv, cap, chk, _mate in _steps
    ]
    payoff = None
    for idx, (ours, _f, _t, is_cap, _chk) in enumerate(steps):
        if ours and is_cap:
            payoff = idx
            break

    # A SACRIFICE is the one case where our capture comes first and the
    # single-move picture is actively misleading, so the "already drawn
    # correctly" reasoning above does not apply to it.
    #
    # Mohit 2026-10-02, on "Opponent's b5 is a serious mistake. Play Bxf7+ —
    # it wins a pawn", drawn as a lone arrow into f7: "it showed me to
    # sacrifice my bishop, should show me a complete line if theory that is
    # real coaching, you know?" One arrow into f7 shows a player giving a
    # bishop away for a pawn and stops; the point is Bxf7+ Kxf7 Qf3+, where
    # the check forks the king and the loose rook on a8.
    #
    # So when our first move is a capture that LOSES material on its own
    # square -- king recaptures played out, which is what makes it a sacrifice
    # rather than a win -- the line is drawn through to our last move in it.
    if payoff == 0 and board_after_opp is not None:
        try:
            first = board_after_opp.parse_san(str(pv[0]))
            gain = legal_exchange_gain(
                board_after_opp, first.to_square, us, first_move=first
            )
        except (ValueError, TypeError, AssertionError, IndexError):
            gain = 0
        if gain is not None and gain < 0:
            # The FIRST of our moves after their forced reply that does
            # something -- a capture or a check -- and only inside the arrow
            # budget. Taking the LAST of our moves instead walked a 12-ply PV
            # to a payoff far past the four arrows we draw, so the picture was
            # truncated mid-line and ended on THEIR move with no payoff at all
            # (game_af4d58d0936a move 9, four arrows, no green).
            # Prefer the move that WINS THE MATERIAL BACK over the first
            # thing that merely does something.
            #
            # Mohit 2026-10-06 on the Ng5 card: "the main idea is bishop takes
            # the pawn and king takes bishop, our knight checks the king and
            # the knight now behind our knight gets captured by our queen, so
            # that's the whole line and arrow doesn't show until there".
            #
            # Bxf2+ Kxf2 Ng4+ Kg1 Qxg5: the check at ply 3 is the mechanism,
            # the capture at ply 5 is the point. Stopping on the first check
            # showed him giving a bishop away and getting a check for it.
            _recapture = None
            _forcing = None
            for idx, (ours, _f, _t, is_cap, gives_chk) in enumerate(steps):
                if idx < 2 or not ours:
                    continue
                if is_cap and _recapture is None and idx <= max_arrows:
                    _recapture = idx
                if (is_cap or gives_chk) and _forcing is None:
                    _forcing = idx
            if _recapture is not None:
                payoff = _recapture
            elif _forcing is not None and _forcing <= max_arrows - 1:
                payoff = _forcing

    # Nothing to show, or the single-move builders already say it.
    if payoff is None or payoff < 2:
        return []

    arrows: List[Dict[str, str]] = []
    for idx, (ours, frm, to, _cap, _chk) in enumerate(steps[: payoff + 1]):
        if len(arrows) >= max_arrows:
            break
        if ours:
            colour = "green" if idx == payoff else "blue"
        else:
            colour = "palegrey"
        arrows.append({"from": frm, "to": to, "color": colour, "teach": True})
    return arrows


def winning_plan_arrows(
    board_before: Optional[chess.Board],
    best_move_uci: Optional[str],
    pv_after_best: Optional[Sequence[str]] = None,
    max_arrows: int = 5,
) -> List[Dict[str, str]]:
    """The whole idea: our move, the piece running, and us taking it anyway.

    Mohit 2026-10-06: "for a 1000, he couldn't really see Be5 attacking rook,
    but rook can move right? and then white bishop traps him, so i want to show
    the complete idea with arrow... the idea is to really find a move in
    stockfish line that actually takes up the bigger piece".

    Exactly so. "Be5 attacks the rook" is useless on its own, because the rook
    moves. The lesson is the chase:

        Be5    f4->e5   blue       our move
        ...Rg8 h8->g8   palegrey   the rook runs
        ...Rg7 g8->g7   palegrey   and runs again
        Bxg7   e5->g7   green      the same bishop takes it anyway

    _line_sequence_arrows cannot tell this story. It takes the FIRST of our
    captures, which here is Bxe6 winning a pawn at step four, and with a
    four-arrow budget it truncates before the green one and ends on their move.
    So this picks the capture of the most VALUABLE piece, then follows that
    piece backwards through the line to show where it fled from -- the moves in
    between that are about other material are dropped, because they are not the
    idea.

    Right-or-silent: every arrow is a move the engine's own line plays, and the
    payoff must be worth a knight or more, or the chase is not worth four
    arrows.
    """
    if board_before is None or not best_move_uci or not pv_after_best:
        return []
    try:
        board = board_before.copy()
        first = chess.Move.from_uci(str(best_move_uci))
        if first not in board.legal_moves:
            return []
    except (ValueError, AssertionError):
        return []

    us = board.turn
    moves: List[tuple] = []          # (ours, move, captured_type)
    board.push(first)
    moves.append((True, first, None))
    for san in list(pv_after_best):
        try:
            mv = board.parse_san(str(san))
        except (ValueError, AssertionError):
            break
        captured = board.piece_at(mv.to_square) if board.is_capture(mv) else None
        moves.append((board.turn == us, mv, captured.piece_type if captured else None))
        board.push(mv)

    # Our richest capture in the line. "Bigger piece" is the whole point, so a
    # pawn grab on the way does not qualify as the payoff.
    payoff_idx = None
    payoff_value = 0
    for idx, (ours, _mv, captured_type) in enumerate(moves):
        if not ours or captured_type is None:
            continue
        value = PIECE_VALUE_CP.get(captured_type, 0)
        if value >= 320 and value > payoff_value:
            payoff_idx, payoff_value = idx, value
    if payoff_idx is None:
        return []

    # The capture has to leave us AHEAD, not merely even. A recapture looks
    # identical to a win when you only read the piece that came off the board.
    #
    # Found by inspecting the corpus rather than being told: on
    # `5rk1/1pp3p1/3qp2p/p3p3/P3Pn2/N1P2NPP/1PQ2B2/6K1 b` the line is
    # Qd3 Qxd3 Nxd3 -- a queen TRADE. Nxd3 takes a queen, cleared the 320
    # threshold, and the picture would have said "play Qd3 and win the queen"
    # about an even swap. That is the claim this file spent v184 removing from
    # the sentences; it has no business arriving in the arrows.
    net = 0
    for ours, _mv, captured_type in moves[: payoff_idx + 1]:
        if captured_type is None:
            continue
        value = PIECE_VALUE_CP.get(captured_type, 0)
        net += value if ours else -value
    if net < 300:
        return []

    # Follow the victim backwards: whoever stood on the captured square got
    # there from somewhere, and that flight is the half a 1000-rated player
    # cannot see from a single arrow. Record where it stood at each ply so the
    # hunters can be matched against it.
    victim_square = moves[payoff_idx][1].to_square
    flight_idx: Dict[int, int] = {}          # move index -> nothing, just a set
    stood_at: Dict[int, int] = {}            # move index -> victim square then
    for idx in range(payoff_idx - 1, 0, -1):
        ours, mv, _captured = moves[idx]
        stood_at[idx] = victim_square
        if ours or mv.to_square != victim_square:
            continue
        flight_idx[idx] = 1
        victim_square = mv.from_square
    stood_at[0] = victim_square

    # Our moves that HUNT it. Mohit 2026-10-06, looking at the rendered card:
    # "a8 bishop is missing, the arrow is missing there". He is right and it is
    # the mechanism, not a detail: after Be5 Rg8, it is Bd5 -- the OTHER bishop,
    # from a8 -- that attacks g8 through e6 and f7 and forces the rook to run
    # again to g7, where the first bishop takes it. Two bishops cornering a
    # rook. Drawing only the victim's flight and our first and last moves shows
    # the rook running for no visible reason.
    hunter_idx: Dict[int, int] = {}
    board_at = board_before.copy()
    board_at.push(first)
    for idx in range(1, payoff_idx):
        ours, mv, _captured = moves[idx]
        target = stood_at.get(idx)
        if ours and target is not None:
            probe = board_at.copy()
            probe.push(mv)
            if target in probe.attacks(mv.to_square):
                hunter_idx[idx] = 1
        board_at.push(mv)

    # Our own piece's ROUTE to the square it strikes from. Mohit 2026-10-06,
    # pointing at a green arrow that began on an empty square: "why this
    # arrow?". On Q7/p4ppk/7p/8/1P1P1KP1/Pb3P2/8/6q1 b the line is
    # g5+ Ke4 Qc1 f4 Qh1+ Ke3 gxf4+ Kxf4 Qxa8 -- the capture is real, but it
    # happens nine plies later and the queen gets to h1 by travelling
    # g1 -> c1 -> h1. Drawn alone, h1->a8 starts where nothing stands and the
    # journey is invisible. Same fault as the mate arrow that began on c7
    # after the rook had moved to c8: a legal engine move drawn from a square
    # the piece has not reached yet.
    route_idx: Dict[int, int] = {}
    launch_square = moves[payoff_idx][1].from_square
    for idx in range(payoff_idx - 1, -1, -1):
        ours, mv, _captured = moves[idx]
        if not ours or mv.to_square != launch_square:
            continue
        route_idx[idx] = 1
        launch_square = mv.from_square

    chosen = sorted(
        {0, payoff_idx} | set(flight_idx) | set(hunter_idx) | set(route_idx)
    )
    # Trim from the middle if we overflow, dropping the LAST hunter first.
    # The earliest hunter is the one that brings a new piece to bear -- Bd5
    # from a8 is what makes the rook run a second time -- while a later one is
    # usually that same piece shuffling (Bxe6 merely clears the blocker). The
    # first version trimmed from the front and threw away exactly the arrow
    # Mohit had just asked for.
    while len(chosen) > max_arrows:
        # Hunters go before route steps. Dropping a route step leaves the
        # payoff arrow starting from a square the piece never visibly reached,
        # which is the bug this whole block exists to avoid.
        for idx in reversed(chosen[1:-1]):
            if idx in hunter_idx and idx not in route_idx:
                chosen.remove(idx)
                break
        else:
            for idx in chosen[1:-1]:
                if idx not in route_idx:
                    chosen.remove(idx)
                    break
            else:
                chosen.remove(chosen[1])

    arrows: List[Dict[str, str]] = []
    for idx in chosen:
        ours, mv, _captured = moves[idx]
        if idx == payoff_idx:
            colour = "green"
        elif ours:
            colour = "blue"
        else:
            colour = "palegrey"
        arrows.append({
            "from": chess.square_name(mv.from_square),
            "to": chess.square_name(mv.to_square),
            "color": colour,
            "teach": True,
        })
    return arrows


def recommended_move_arrows(
    board_before: Optional[chess.Board],
    best_move_uci: Optional[str],
    pv_after_best: Optional[Sequence[str]] = None,
) -> List[Dict[str, str]]:
    """Draw the move the card tells them to play.

    Mohit 2026-10-06, on a card reading "O-O is a major blunder. Be5 was better
    -- it wins the rook" with a bare board: "now why not arrow here?".

    The best-move picture came only from _check_attack_arrows, which requires
    the move to give CHECK. Be5 does not, so a card naming a concrete prize
    drew nothing at all -- the same shape as the "you can win it with bxc5"
    card, on the other side of the board.

    The move arrow is always true: it is the instruction the sentence just
    gave. A target arrow is added only when the engine's own continuation
    leaves that piece where it is. On the reported card Be5 hits the rook on
    h8, the knight on d6 and the pawn on d4, and the stored line answers Rg8 --
    the rook walks. It IS won nine plies later, so the caption is fair, but
    drawing e5->h8 would say it is won on arrival, which is the claim v184
    stopped making.
    """
    if board_before is None or not best_move_uci:
        return []
    try:
        best = chess.Move.from_uci(str(best_move_uci))
        if best not in board_before.legal_moves:
            return []
        after = board_before.copy()
        after.push(best)
    except (ValueError, AssertionError):
        return []

    arrows: List[Dict[str, str]] = [{
        "from": chess.square_name(best.from_square),
        "to": chess.square_name(best.to_square),
        "color": "blue",
        "teach": True,
    }]

    # Which squares does their reply vacate? Anything on one of those is not
    # won here, whatever the caption promises later in the line.
    vacated = set()
    line = list(pv_after_best or ())
    if line:
        try:
            probe = after.copy()
            reply = probe.parse_san(str(line[0]))
            vacated.add(reply.from_square)
        except (ValueError, AssertionError):
            # An unreadable line is not permission to claim the target.
            return arrows

    mover = board_before.turn
    best_target = None
    for square in after.attacks(best.to_square):
        if square in vacated:
            continue
        piece = after.piece_at(square)
        if not piece or piece.color == mover or piece.piece_type == chess.KING:
            continue
        gain = 0
        try:
            gain = legal_exchange_gain(after, square, mover) or 0
        except (ValueError, TypeError):
            gain = 0
        if gain < 100:
            continue
        value = PIECE_VALUE_CP.get(piece.piece_type, 0)
        if best_target is None or value > best_target[1]:
            best_target = (square, value)
    if best_target is not None:
        arrows.append({
            "from": chess.square_name(best.to_square),
            "to": chess.square_name(best_target[0]),
            "color": "green",
            "teach": True,
        })
    return arrows


def mate_arrows_for_played_board(
    board_before: Optional[chess.Board],
    played_move: Optional[chess.Move],
    best_move_uci: Optional[str],
) -> List[Dict[str, str]]:
    """The same mate, drawn on the board the player is actually looking at.

    Mohit 2026-10-06: "now, no arrow at all, what's wrong with you". Removing
    the contradictory shape arrows and leaving the board blank was the wrong
    call -- he asked to SEE the mating pattern, not to see less. Silence beats
    contradiction, but a true picture beats both.

    The card renders the position AFTER the played move, so the mate picture
    built for the post-mate board cannot be reused: after Bd5 the rook has not
    gone to c8 and the bishop has left e6. What IS true of this board, and is
    exactly the lesson:

      c7 -> c8   the move that was mate
      e6 -> d7   the squares the bishop was covering from the square it just
      e6 -> f7   left, which is why the mate is gone

    e6 is already highlighted as the from-square, so the two yellow lines read
    as "your bishop was here, holding these". Every arrow is drawn in
    board_before coordinates, which is the frame both boards share.
    """
    if board_before is None or played_move is None or not best_move_uci:
        return []
    geometry = _mate_geometry_arrows(board_before, best_move_uci)
    if not geometry:
        return []
    try:
        mate_move = chess.Move.from_uci(str(best_move_uci))
    except (ValueError, AssertionError):
        return []
    # The mating move itself, not the piece-to-king line: on this board the
    # mating piece has not moved yet, so showing where it would GO is the
    # instruction.
    arrows: List[Dict[str, str]] = [{
        "from": chess.square_name(mate_move.from_square),
        "to": chess.square_name(mate_move.to_square),
        "color": "red",
        "teach": True,
    }]
    # Keep the cover lines, minus any that start from a square the played move
    # has since filled or emptied in a way that makes them unreadable.
    for arrow in geometry[1:]:
        if arrow["from"] == chess.square_name(mate_move.to_square):
            continue
        arrows.append(dict(arrow))
    return arrows[:4]


def shape_arrows_survive_mate_picture(
    mate_picture: Optional[List[Dict[str, str]]],
    best_move_arrows: Optional[List[Dict[str, str]]],
) -> bool:
    """False when the mate picture owns the card and the shape arrows must go.

    Mohit 2026-10-06, with the badge and caption both already fixed: "now shows
    missed mate, but arrows are still showing for missed skewer". The card read
    "Bd5 missed a checkmate" over an alignment picture (e8->d8, d8->c7, d5->a8)
    that a shape detector had drawn independently. Two surfaces agreeing and
    the loudest one still telling the old story.

    The mate geometry cannot just be moved onto the main board: it is true of
    the position AFTER the mating move, which is why it carries its own FEN. On
    the board the player sees, their bishop has already left e6, so e6->d7 is
    not a line that exists there. So the shape arrows go rather than get
    replaced -- silence beats contradiction -- and the mate picture stays on
    the surface whose board it is true of.
    """
    return not (bool(mate_picture) and bool(best_move_arrows))


def _mate_geometry_arrows(
    board_before: Optional[chess.Board],
    best_move_uci: Optional[str],
) -> List[Dict[str, str]]:
    """Show WHY the mate is mate: who covers the king's squares, and what of
    theirs is in the way.

    Mohit 2026-10-05, on the Rc8# card: "this is a proper mating pattern, if
    all squares of king are taken by our bishop and it's just behind it's own
    pawn so that's also taken, you know, this is a geometry to learn and
    remember".

    On `rn2kb1r/2R1p2p/p3B1p1/5p2/3pn3/7N/1PP2PPP/2B1K2R w` the king on e8 is
    mated by Rc8 because the bishop on e6 covers d7 and f7 while their own pawn
    on e7 and bishop on f8 take the rest. The card drew c7->c8 and said
    "forcing move at the exposed king", which names the move and teaches none
    of that. A player who sees the two bishop lines learns a pattern; a player
    who sees one rook arrow learns one move.

    Right-or-silent, and board-verified: nothing is drawn unless the move
    really is checkmate, and every cover arrow is a square the king would use,
    attacked by the named piece of ours.
    """
    if board_before is None or not best_move_uci:
        return []
    try:
        after = board_before.copy()
        mate_move = chess.Move.from_uci(str(best_move_uci))
        if mate_move not in after.legal_moves:
            return []
        after.push(mate_move)
    except (ValueError, AssertionError):
        return []
    if not after.is_checkmate():
        return []

    mated = after.turn                      # the side now to move is mated
    king_square = after.king(mated)
    if king_square is None:
        return []

    # The arrow starts where the mating piece ENDS UP. This picture renders on
    # the board after the mating move, where c7 is empty and the rook is on c8
    # -- the first version drew from c7 and so began on a bare square.
    arrows: List[Dict[str, str]] = [{
        "from": chess.square_name(mate_move.to_square),
        "to": chess.square_name(king_square),
        "color": "red",
        "teach": True,
    }]

    # Every square the king would run to, and the piece of ours covering it.
    # Squares blocked by their OWN men need no arrow -- the board already shows
    # the obstruction, and an arrow pointing at their own pawn would read as an
    # attack on it.
    for square in chess.SQUARES:
        if square == king_square:
            continue
        if chess.square_distance(square, king_square) != 1:
            continue
        occupant = after.piece_at(square)
        if occupant is not None and occupant.color == mated:
            continue                        # their own piece is in the way
        for coverer in after.attackers(not mated, square):
            if coverer == mate_move.to_square:
                continue                    # the mating piece is already drawn
            arrows.append({
                "from": chess.square_name(coverer),
                "to": chess.square_name(square),
                "color": "yellow",
                "teach": True,
            })
            break
        if len(arrows) >= 4:
            break
    return arrows


def _abandoned_defender_arrows(
    board_before: Optional[chess.Board],
    played_move: Optional[chess.Move],
    *,
    mover_is_user: bool,
    cp_loss: int,
    pv_after_played: Optional[Sequence[str]] = None,
) -> List[Dict[str, str]]:
    """Draw the piece the move stopped defending, and the hand that takes it.

    Mohit 2026-10-05, on the Qh5+ card: "i think arrows could be better, you
    know, may be one more step ahead... the problem was knight was already
    under attack and he got his queen too under attack with the pawn now, but
    arrows should also show attacked knight".

    On `rn1qkbnr/1bp1p1pp/p7/5p2/1p1PN3/1B3Q2/PPP2PPP/R1B1K1NR w` the knight on
    e4 is attacked TWICE -- the f5 pawn and the b7 bishop -- and defended once,
    by the queen on f3. Qh5+ is the defender walking away. The caption says so
    ("runs into fxe4, losing your knight on e4") but every arrow pointed at the
    queen, because _punishment_arrows draws pv_after_played[0] and the engine's
    immediate reply here is g6: a block that also hits the queen. The capture
    the sentence is about, fxe4, is three plies further on, and nothing looked
    that far.

    So this walks the stored line for the capture of a piece this move had been
    defending, and draws THAT. The claim still answers to the engine -- the
    capture has to appear in the line, we never infer it from the static board,
    which is the mistake that produced 34% bad arrows before v181.

    Measured over the corpus: 18,884 user moves (3.15%) move a defender of an
    already-attacked piece, 18,691 of them its ONLY defender, and in 3,272 the
    engine's line really does take it. 2,095 are attacked two or more times
    like this one, where the second attacker is drawn too so the picture says
    "two onto one" rather than merely "this is hanging".
    """
    if board_before is None or played_move is None:
        return []
    if not mover_is_user or (cp_loss or 0) < 100:
        return []
    if not pv_after_played:
        return []

    mover = board_before.turn
    enemy = not mover

    # Pieces we were defending that the opponent ALREADY attacked. The move
    # leaving is what changes the count, so a piece nobody was eyeing is not
    # this lesson.
    at_risk = set()
    for square in chess.SQUARES:
        piece = board_before.piece_at(square)
        if not piece or piece.color != mover or piece.piece_type == chess.KING:
            continue
        if square == played_move.from_square:
            continue
        if not board_before.attackers(enemy, square):
            continue
        if played_move.from_square not in board_before.attackers(mover, square):
            continue
        at_risk.add(square)
    if not at_risk:
        return []

    try:
        board = board_before.copy()
        board.push(played_move)
    except Exception:
        return []

    # When their very next move takes something ELSE, that is the punishment
    # and _punishment_arrows draws exactly it; reaching past it to a deeper
    # capture makes the picture less direct, not more. When the immediate
    # capture IS one of the pieces we stopped defending, we keep going -- the
    # primary arrow comes out the same and the second attacker gets drawn too.
    #
    # Measured over 400 games. Of 156 cards this fires on, 133 drew the same
    # primary arrow as the punishment picture and only added the second
    # attacker, which is worth keeping. Of the 14 that genuinely differed,
    # several were overriding an immediate capture (Bxg3, Rxb6, Bxg5) with one
    # three plies later; this gate drops those to 3. A blanket defer-on-capture
    # fixed the 14 but threw away all 133 enrichments, which is why the test
    # is on the SQUARE and not merely on is_capture.
    try:
        first = board.parse_san(str(list(pv_after_played)[0]))
        if board.is_capture(first) and first.to_square not in at_risk:
            return []
    except (ValueError, AssertionError, IndexError):
        return []

    for san in list(pv_after_played)[:6]:
        try:
            move = board.parse_san(str(san))
        except (ValueError, AssertionError):
            return []
        if move not in board.legal_moves:
            return []
        if (board.turn == enemy
                and move.to_square in at_risk
                and board.is_capture(move)):
            victim = chess.square_name(move.to_square)
            arrows: List[Dict[str, str]] = [{
                "from": chess.square_name(move.from_square),
                "to": victim,
                "color": "red",
                "teach": True,
            }]
            # The other attacker, when there is one. "Two of theirs onto one of
            # yours" is the countable fact the lesson rests on, and it is
            # invisible if only the capture is drawn.
            for other in board.attackers(enemy, move.to_square):
                if other == move.from_square:
                    continue
                arrows.append({
                    "from": chess.square_name(other),
                    "to": victim,
                    "color": "yellow",
                    "teach": True,
                })
                break
            return arrows
        board.push(move)
    return []


def _punishment_arrows(
    board_before: Optional[chess.Board],
    played_move: Optional[chess.Move],
    *,
    mover_is_user: bool,
    cp_loss: int,
    pv_after_played: Optional[Sequence[str]] = None,
) -> List[Dict[str, str]]:
    """Draw the engine's own refutation of a blunder, or nothing.

    Mohit 2026-09-17: "we want to make sure we understand the blunders and
    mistakes from each game and try to arrow them, so they make sense."

    Until v181 the victim was chosen by ``static_exchange_eval``, and that was
    the wrong authority twice over. Mohit 2026-09-28, on move 30 of
    26d74ad6 (`1k2n2r/p1p5/1p5p/8/3q4/1Q3B2/PP3PP1/4R1K1 w - - 0 30`), where
    the caption read "Qf7 lets Nd6 attack the queen on f7" and the board drew
    d4->f2: "wrong arrow here, look at stockfish what is this suggesting and
    what are you doing there?"

    Both failures are the same blind spot, SEE ignoring the king:

      * as a DEFENDER -- f2 is covered only by Kg1, so SEE scored the pawn
        +100 "free" when Qxf2+ Kxf2 simply drops the queen. The existing
        ``legally_hanging_pieces`` fallback below was written for the mirror
        case (king as the only ATTACKER) and never guarded this direction.
      * ``board.attackers()`` is PSEUDO-legal, so a pinned attacker produced
        arrows for captures that are not legal moves at all.

    So the guess is gone. ``pv_after_played`` is the engine's actual answer to
    the move the card has already called a mistake, and it is stored on 93% of
    them, which makes it both truer and better covered than anything SEE can
    infer from the static position.

    Measured 2026-09-28 over 400 real games / 2,561 user-mistake cards, with
    Stockfish depth 13 as an INDEPENDENT judge (an arrow is "bad" when the move
    it draws is 100cp or more worse than the best reply):

        builder                       cards drawn   bad     illegal
        SEE guess (to v180)               1529      34%       3
        engine refutation (this)          1475       2%       0

    Coverage is unchanged, so nothing is traded away for the correctness --
    the picture simply stops contradicting the sentence beside it. Of the two
    residual "bad" samples both draw the engine's OWN stored line and differ
    only because the judge ran shallower than the committed analysis.

    Two shapes, and silence otherwise:

      * the refutation is a capture -- one red arrow, the piece they take.
        Judged clean on 70 of 70 samples.
      * the refutation is quiet but creates a real threat -- red for their
        move, yellow for what it now attacks. Gated on a LEGAL capture
        existing after a null move, not on ``attacks()``, which is why all
        516 of these passed the exact legality check with none failing.

    A quiet reply that threatens nothing draws nothing: 30...Kg1 is not a
    punishment picture, and v180 drew several.
    """
    if board_before is None or played_move is None:
        return []
    if not mover_is_user or (cp_loss or 0) < 100:
        return []
    if not pv_after_played:
        return []
    try:
        after = board_before.copy()
        after.push(played_move)
        try:
            punish = after.parse_san(str(pv_after_played[0]))
        except (ValueError, AssertionError):
            return []
        if punish not in after.legal_moves:
            return []

        move_arrow = {
            "from": chess.square_name(punish.from_square),
            "to": chess.square_name(punish.to_square),
            "color": "red",
            "teach": True,
        }
        if after.is_capture(punish):
            return [move_arrow]

        post = after.copy()
        post.push(punish)
        if post.is_check():
            # A check is its own story and the check-arrow builder tells it.
            return []
        probe = post.copy()
        probe.push(chess.Move.null())  # hand them the move to test the threat

        best: Optional[tuple] = None
        for move in probe.legal_moves:
            if move.from_square != punish.to_square or not probe.is_capture(move):
                continue
            victim = probe.piece_at(move.to_square)
            if victim is None:
                continue
            value = PIECE_VALUE_CP.get(victim.piece_type, 0)
            # Pawn threats are noise on a blunder card; a piece is the lesson.
            if value >= 320 and (best is None or value > best[0]):
                best = (value, move.to_square)
        if best is None:
            return []
        return [
            move_arrow,
            {
                "from": chess.square_name(punish.to_square),
                "to": chess.square_name(best[1]),
                "color": "yellow",
                "teach": True,
            },
        ]
    except Exception:
        return []


# No hyphen or en dash in this set. These captions write square
# references as "the b7-pawn" and "the e-file", and a hyphen here made
# that look like the move b7. Leaving it out also stops O-O matching
# inside O-O-O, which is the behaviour wanted.
_SAN_TOKEN_STOPS = set(" \t\n.,;:!?()[]—’'\"")


def _names_the_move(text, san):
    """True when `san` appears in `text` as a standalone move token.

    A token check on a SAN this code generated, not a judgement about chess.
    Written as an explicit scan rather than a regex because SAN carries `+`,
    `#` and `=`, which word-boundary classes split in the wrong places, and
    because a word-boundary escape written through a shell heredoc has twice
    arrived in this file as a literal backspace that matched nothing.
    """
    if not text or not san:
        return False
    san = san.strip()
    start = 0
    while True:
        i = text.find(san, start)
        if i < 0:
            return False
        before_ok = i == 0 or text[i - 1] in _SAN_TOKEN_STOPS
        j = i + len(san)
        after_ok = j >= len(text) or text[j] in _SAN_TOKEN_STOPS
        if before_ok and after_ok:
            return True
        start = i + 1


def _lead_with_the_stalemate(caption, *, played_san, mover_is_user,
                             threw_away_win, best_move_san=None):
    """Put the draw in front of whatever the rules produced.

    The tail is kept only when it names the better move. Everything else on
    these cards is floor text, written because nothing better had fired -- the
    open file, the calm position, the tidy king -- and on the move that ended
    the game it reads as praise.

    The move is named once. All 68 user-side tails here already open with the
    played move ("Kg3 misses mate in 3", "You played Kg3; ..."), so naming it
    in the lead as well said it twice; the lead names it only when nothing
    after it will. docs/stalemate_scope.md
    """
    tail = (caption or "").strip()
    keep_tail = bool(tail) and _names_the_move(tail, best_move_san)
    tail_names_played = keep_tail and _names_the_move(tail, played_san)
    them = "your opponent" if mover_is_user else "you"
    subject = "Your opponent" if them == "you" else "You"

    if tail_names_played:
        left = f"{them.capitalize()} was left with no legal move"
    else:
        left = f"{played_san} leaves {them} with no legal move"

    if threw_away_win and mover_is_user:
        lead = f"You had this won. {left[0].upper()}{left[1:]}, so the game is a draw by stalemate."
        principle = ("When you are winning easily, check your opponent has a "
                     "move before you play.")
    elif threw_away_win:
        lead = (f"Your opponent was winning. {left[0].upper()}{left[1:]}, so "
                f"the game is a draw by stalemate.")
        principle = ("Keep playing when you are losing. Your opponent can "
                     "still go wrong.")
    else:
        lead = f"{left[0].upper()}{left[1:]}, so the game is a draw by stalemate."
        principle = ""

    if keep_tail:
        return f"{lead} {tail}"
    if principle:
        return f"{lead} {principle}"
    return lead


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
        from services.caption_facts_verified import extract_facts_verified
    except Exception:
        extract_facts_verified = None  # type: ignore
    try:
        from services.caption_renderer import render_caption_dict
    except Exception:
        render_caption_dict = None  # type: ignore

    # Feature flag: use Stockfish verification layer
    USE_VERIFIED_FACTS = True

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

    _exact_endgame: Optional[ExactEndgameEvidence] = None
    _exact_endgame_cause: Optional[ExactEndgameCause] = None
    if inputs.exact_endgame_evidence:
        try:
            _exact_endgame = ExactEndgameEvidence.from_contract(
                inputs.exact_endgame_evidence
            )
            if " ".join(_exact_endgame.fen.split()[:4]) != " ".join(
                board_before.fen().split()[:4]
            ):
                raise ValueError("exact evidence belongs to a different position")
            _exact_endgame_cause = build_exact_endgame_cause(
                _exact_endgame,
                played_san=inputs.played_san,
                preferred_best_san=inputs.best_move_san,
            )
            if not (_EXACT_ENDGAME_REVIEW_ENABLED and inputs.mover_is_user):
                _exact_endgame_cause = None
        except Exception:
            logger.warning(
                "[exact_endgame] rejected stale or incomplete evidence on move %s",
                inputs.full_move_number,
            )
            _exact_endgame = None
            _exact_endgame_cause = None

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

    # --- Best-equals-played + mate dominance (v159, 2026-09-15) ----
    # compute_severity_for_move() carries these for the V5 review path,
    # but this function classifies severity itself and is what PWC calls,
    # so the guards have to hold here too or PWC stays unguarded.
    # Right-or-silent: with no best_move_san we never guess it was best.
    import dataclasses as _dc

    def _norm_san(x: Any) -> str:
        return str(x or "").strip().rstrip("!?+#")

    _best_eq_played = bool(
        _norm_san(inputs.best_move_san)
        and _norm_san(inputs.best_move_san) == _norm_san(inputs.played_san)
    )
    try:
        _b_after = board_before.copy(stack=False)
        _b_after.push(played_move)
        _played_is_mate = _b_after.is_checkmate()
    except Exception:
        _played_is_mate = False

    if _best_eq_played or _played_is_mate:
        if canonical.tier != "good" or practical.practical_tier != "good":
            logger.info(
                "[SEVERITY-SANITY] %s: canonical=%s practical=%s downgraded to "
                "good (best_equals_played=%s, is_mate=%s, is_user=%s)",
                inputs.played_san, canonical.tier, practical.practical_tier,
                _best_eq_played, _played_is_mate, inputs.mover_is_user,
            )
        canonical = _dc.replace(
            canonical,
            tier="good",
            user_facing_tier="good" if inputs.mover_is_user else "context",
        )
        # practical_tier drives R12 variant selection and the shape gate
        # (caption_facts["severity_practical"]), so leaving it on a fault
        # tier would still render fault-framed prose.
        practical = _dc.replace(
            practical, practical_tier="good", canonical_tier="good",
        )

    caption_facts: Dict[str, Any] = {}

    # Try verified facts first (Stockfish-backed), fall back to raw facts
    if USE_VERIFIED_FACTS and extract_facts_verified is not None:
        try:
            caption_facts = extract_facts_verified(
                fen_before=inputs.fen_before,
                played_san=inputs.played_san,
                best_move_san=inputs.best_move_san,
                eval_before_cp=inputs.eval_before_cp,
                eval_after_cp=inputs.eval_after_cp,
                pv_after_played=list(inputs.pv_after_played),
                pv_after_best=list(inputs.pv_after_best),
                move_history_san=list(inputs.move_history_san),
                full_move_number=int(inputs.full_move_number or 0),
                # 2026-07-14 severity-POV fix: pass the mover-POV cp_loss +
                # mover identity instead of letting the wrapper re-derive a
                # white-POV delta (which zeroed every black mover's mistakes
                # and mis-voiced captions).
                cp_loss=int(inputs.cp_loss or 0),
                mover_is_user=bool(inputs.mover_is_user),
            )
            logger.debug(f"[caption_pipeline] verified facts: verified={caption_facts.get('verified', False)}")
        except Exception:
            logger.exception("[caption_pipeline] extract_facts_verified failed; falling back")
            caption_facts = {}

    # Fall back to non-verified facts if verification failed or disabled
    if not caption_facts and extract_facts is not None:
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
            # Mark as not verified when using fallback
            caption_facts["verified"] = False
        except Exception:
            logger.exception("[caption_pipeline] extract_facts failed; using empty dict")
            caption_facts = {}

    inject_practical_severity_facts(caption_facts, practical)

    # ─── Forced mate, BEFORE the caption is written ────────────────────
    #
    # Mohit 2026-09-29 on move 31 of d75acb09, a card reading "You played
    # Rad2; Ka3 was the stronger move here -- Rad2 lets Qa1+ come in with
    # check": "caption should clearly mention about check mate."
    #
    # The stored line for that move is ['Qa1+', 'Ra2', 'Qxa2#'] -- the mate is
    # in the card's own data -- and build_verified_line_cause returns
    # lesson_kind='allowed_forced_mate', mate_in=2 for it. The fact was never
    # missing. It was computed AFTER the caption had already been written and
    # attached to candidate_comparison, a different surface, so the sentence
    # fell through to the generic floor and called a forced mate a check.
    #
    # So it moves up here, where the rules can still read it. Computed once
    # and handed to the later call site rather than run twice: it replays two
    # stored lines and runs no engine, but it is not free either.
    exact_line_cause = None
    if inputs.mover_is_user and inputs.best_move_san:
        try:
            exact_line_cause = build_verified_line_cause(
                fen_before=inputs.fen_before,
                played_san=inputs.played_san,
                best_move_san=inputs.best_move_san,
                pv_after_played=tuple(inputs.pv_after_played or ()),
                pv_after_best=tuple(inputs.pv_after_best or ()),
                cp_loss=int(inputs.cp_loss or 0),
            )
        except Exception:
            logger.exception("[caption_pipeline] verified line cause failed")
            exact_line_cause = None
    # No stalemate guard here, deliberately. 13 stored cards read "allows mate
    # in N" about a move after which there are no moves -- but all 132 of those
    # positions carry an EMPTY pv_after_played, because the game ended, so
    # `allowed_forced_mate` cannot be built for them at all. A guard here moved
    # 0 of 132. Those stored claims came from code that no longer exists; the
    # fix for them is a re-render. See
    # test_stalemate_threw_away_the_win.TestWhyNoMateGuardHere.
    if exact_line_cause is not None and exact_line_cause.mate_in:
        if exact_line_cause.lesson_kind == "allowed_forced_mate":
            caption_facts["allows_forced_mate"] = True
            caption_facts["allowed_mate_in"] = int(exact_line_cause.mate_in)
            # The move that starts it, so the sentence can name something the
            # player can find on the board rather than assert "mate" abstractly.
            caption_facts["allowed_mate_first_move"] = exact_line_cause.reply_san
            caption_facts["allowed_mate_word"] = (
                "move" if int(exact_line_cause.mate_in) == 1 else "moves"
            )
        elif exact_line_cause.lesson_kind == "missed_forced_mate":
            caption_facts["missed_forced_mate_line"] = True
            caption_facts["missed_forced_mate_in"] = int(exact_line_cause.mate_in)

    # ─── Order mirrors V5 service per-move loop exactly (verified
    # against game_decryption_v5_service.py callsites — zero-diff
    # depends on this ordering when V5 adopts the central entry).

    # ─── 3. A3 opp-side narration (gates on !is_user + opp_cp>=30) ──
    _coach_line_result = inject_opp_side_narration_facts(
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
        pv_after_played=list(inputs.pv_after_played or []),
    )
    _coach_line_moves: List[str] = []
    _coach_line_length_hint: Optional[int] = None
    # The V5 migration historically dropped this return value. Do not silently
    # activate every old generic opponent line as part of this narrow feature;
    # carry it only for the fully proved five-ply family introduced here.
    if (
        _coach_line_result is not None
        and caption_facts.get("opp_user_reply_unsafe_recapture_pawn_fork")
    ):
        _coach_line_moves = list(_coach_line_result[0])
        _coach_line_length_hint = int(_coach_line_result[1])

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
        # "serious" is a real, distinct tier between "mistake" and
        # "blunder" (services/severity.py) — it was missing here, so a
        # genuine near-blunder silently never qualified for Socratic
        # coaching even when severity_override correctly reported it.
        if _eff_sev in ("mistake", "blunder", "serious"):
            # Derive fundamental_violated from facts already computed
            # by extract_facts (step 1). hanging > missed-tactic > none.
            # Board-proved facts win: they are checked against this position,
            # while the gap is a stored classification of it.
            _fundamental = None
            if caption_facts.get("pieces_now_undefended"):
                _fundamental = "hanging_pieces"
            elif caption_facts.get("missed_tactic_kind"):
                _fundamental = "calculate"
            else:
                # Neither board fact fired. Before falling to the generic
                # variant -- which 86% of Socratic cards used to do -- ask the
                # analyser what it already decided was wrong with this move.
                _fundamental = GAP_TO_FUNDAMENTAL.get(
                    str(inputs.cognitive_gap or "").strip().lower()
                )
            _effective_socratic_ctx = {
                "severity": _eff_sev,
                "fundamental_violated": _fundamental,
                "coach_intent": None,
                "phase": _phase_for_ctx,
                # Carried so inject_socratic_user_facts can fall back to it
                # AFTER its hanging-piece guard. pieces_now_undefended is
                # truthy far more often than a piece is actually hanging on
                # the post-move board, so the guard was demoting most of these
                # moves straight to the generic variant without ever consulting
                # the gap.
                "cognitive_gap": inputs.cognitive_gap,
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
        allow_fresh_engine_verification=bool(
            inputs.allow_fresh_engine_verification
        ),
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
        move_history_san=inputs.move_history_san,
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

    # NOTE (2026-06-27): a king-safety "why" detector was tried here and REVERTED.
    # Static geometry can prove a king move steps off a check line, but NOT that
    # that's WHY the engine likes it. Engine-verifying its fires showed 2/3 were
    # misattributions (the king move was actually a queen recapture / a check
    # escape that incidentally left a diagonal). Attributing the why of a quiet
    # positional move needs search, not geometry — so we abstain rather than ship
    # a plausible-but-wrong reason. [[feedback_explain_why_recommended_move_good]]
    # [[feedback_query_engine_before_authoring]] [[feedback_diagnose_cause_from_board_not_effect_from_pv]]

    # ─── 9. ASSESSMENT-CONFLICT GATE (2026-06-13 feedback pattern #2) ─
    # fb_f901258f7831 / fb_c7b7be53b387 / fb_05710bfc7125 feedback: coach
    # says "mistake" when severity='good', or vice versa (assessment conflict).
    # Gate: don't render critique caption if cp_loss is below rating-band
    # threshold for the user's rating. Allows concrete-tactic captions (fork,
    # check, capture) through even on low cp_loss, but suppresses bare "is a
    # mistake" when it's not meeting the band's standard.
    #
    # Only applies to USER moves (opp moves always render per suppression).
    # Only suppresses if: (1) user move, (2) no concrete tactic fact fired,
    # (3) cp_loss < band threshold for user's rating.
    _should_gate_low_cp_caption = False
    if (inputs.mover_is_user and inputs.user_rating
            and (int(inputs.cp_loss or 0) or 0) > 0):
        # Band threshold from the single source (rating_resolver, Q1 2026-07-14
        # unification — was an inline ladder duplicating the band boundaries).
        from services.rating_resolver import caption_suppress_threshold_cp
        _rating = int(inputs.user_rating)
        _cp_threshold = caption_suppress_threshold_cp(_rating)

        _cp_loss = int(inputs.cp_loss or 0)
        # Check if the move has a concrete-tactic reason to render despite
        # low cp_loss (fork, check, capture, piece hang, etc.)
        _has_concrete_tactic = (
            caption_facts.get("queen_fork_sub_kind")
            or caption_facts.get("missed_clearance_attack_square")
            or caption_facts.get("attack_with_tempo_piece")
            or caption_facts.get("missed_tactic_kind") == "mate"
            or (caption_facts.get("is_capture") and
                caption_facts.get("captured_piece_type") in ("queen", "rook"))
            or caption_facts.get("opp_reply_san_is_check")
        )

        # Gate: suppress caption if below threshold AND no concrete tactic.
        # BUT never gate a genuine GOOD move (cp_loss < 30, R15 territory) —
        # the gate exists to suppress a false "is a mistake" critique on a
        # sub-threshold INACCURACY, not to silence engine-endorsed good moves.
        # Silencing good moves was the endgame-coverage hole (2026-06-23):
        # 59/354 endgame good moves rendered nothing. Good moves still earn a
        # good-move / tier-floor / principle caption (never-silence). The band's
        # inaccuracy-suppression (cp 30 → threshold) is preserved.
        if (30 <= _cp_loss < _cp_threshold and not _has_concrete_tactic):
            _should_gate_low_cp_caption = True

    # ─── 9. Render caption (caption_renderer) ────────────────────
    caption_payload: Dict[str, Any] = {"caption": "", "rule_name": "R_FALLBACK"}
    if render_caption_dict is not None and not _should_gate_low_cp_caption:
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
        # Mohit 2026-05-28 (game 2d7ade57 m31 Rxf4 cp_loss=8774): when R12
        # can't render (e.g. no best_move available — last move of game)
        # this fallback used to produce "Rxf4. Your queen on c7 is the only
        # piece doing anything." with zero severity framing — a blunder
        # rendered like a neutral observation. Prefix with the same
        # severity_phrase R12 would have used when severity is mistake or
        # worse, so the gravity isn't swallowed by the bs commentary.
        _bs_severity = (caption_facts.get("severity_practical") or "").lower()
        _bs_severity_phrases = {
            "blunder": "is a major blunder",
            "serious": "is a serious mistake",
            "mistake": "is a mistake",
        }
        _bs_severity_phrase = _bs_severity_phrases.get(_bs_severity, "")
        if inputs.mover_is_user and _bs_severity_phrase:
            caption_payload["caption"] = f"{inputs.played_san} {_bs_severity_phrase}. {_bs_text}"
        else:
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
        try:
            from services.detector_quality import (
                QualitySurface as _QualitySurface,
                can_influence as _can_detector_influence,
                grade_for as _detector_grade_for,
                principle_quality_id as _principle_quality_id,
            )
            _authorized_principles = []
            _shadow_principles = []
            for _raw_ev in raw_principles:
                _raw_pid = _raw_ev.get("principle_id")
                _quality_id = _principle_quality_id(_raw_pid or "")
                _annotated = dict(_raw_ev)
                _annotated["detector_quality_id"] = _quality_id
                _annotated["detector_quality_grade"] = _detector_grade_for(
                    _quality_id
                ).value
                if _can_detector_influence(
                    _quality_id, _QualitySurface.CAPTION
                ):
                    _authorized_principles.append(_annotated)
                else:
                    _shadow_principles.append(_annotated)
            raw_principles = _authorized_principles
            if _shadow_principles:
                _quality_shadow = caption_facts.setdefault(
                    "detector_quality_shadow", {}
                )
                _quality_shadow["principles_violated"] = _shadow_principles
        except Exception:
            _quality_shadow = caption_facts.setdefault(
                "detector_quality_shadow", {}
            )
            _quality_shadow["principles_violated"] = list(raw_principles)
            raw_principles = []
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
            # On a GOOD move (cp<30) only fire a principle that AFFIRMS the played
            # move (the move is in the principle's aligned set). A CORRECTIVE
            # principle — player did something other than the principle's move —
            # contradicts a move the engine endorsed: e.g. OP_NOT_CASTLED firing
            # "Castle now. O-O is the top engine pick." on Nd2 (cp0, itself best).
            # Affirming principles (END_KING_ACTIVE on the king step, a played pin)
            # still fire. 2026-06-23.
            _aligned_off = [str(a) for a in (_top.get("aligned_moves_offered") or [])]
            _played_norm = (inputs.played_san or "").replace("+", "").replace("#", "")
            _played_affirms = any(
                _played_norm == a.replace("+", "").replace("#", "") for a in _aligned_off
            )
            if _played_cp_loss_cue < 30 and not _played_affirms:
                # corrective principle on an engine-endorsed move — suppress.
                pass
            elif _endorsement == "absent" and _played_cp_loss_cue < 30:
                pass
            else:
                principle_cue = _entry.get(_cue_key) or _entry.get("cue_absent") or ""
                # A predicate may build a POSITION-SPECIFIC, board-verified why
                # (e.g. PAWN_PUSH_TRAPS_OWN_ROOK names the trapped rook + the
                # opponent's plan) — prefer it over the static principle cue.
                _why_text = (_top.get("evidence") or {}).get("why_text")
                if _why_text:
                    principle_cue = _why_text
                principle_id_used = _top_pid
    # This exact proof family has a longer six-move resolution. Keep the
    # diagnosis readable and carry the reusable lesson in Review's existing
    # teaching-cue surface; the full proof remains available as board replay.
    if (
        caption_facts.get("opp_user_reply_unsafe_recapture_pawn_fork")
        and caption_facts.get("opp_unsafe_recapture_pawn_fork_proof")
    ):
        principle_cue = (
            "When a piece recaptures, check whether a pawn can attack two "
            "pieces at once."
        )
        principle_id_used = "TAC_FORK_PATTERN"

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

    # ─── Trap visualisation on OUR move (2026-09-16) ────────────────
    # Mohit: "I would like arrows to start showing up when it's our move ...
    # before b4, show the knight trapping square or other squares ... any
    # piece that gets trapped should do this."
    #
    # The trap was only ever described on the OPPONENT's mistake card, in
    # words, after the fact. The lesson lands on the move the player actually
    # makes, so the same detector now runs on OUR played move and the card
    # SHOWS the cage: one arrow from each of our pieces to each square the
    # trapped piece can still reach, plus the trapping move itself. Words then
    # only have to carry what the board cannot show.
    #
    # Piece-agnostic by construction — the detector already skips only pawns
    # and kings, so a trapped queen, rook or bishop draws the same picture.
    try:
        from services.caption_facts import (
            _recommended_move_traps_piece as _rmtp_own,
        )
        _own_trap = _rmtp_own(board_before, played_move)
    except Exception:
        _own_trap = None
    # Arrows must agree with the words. cxb4 rebuilds the same cage as b4, so
    # the trap facts fire again — but _trap_caption deliberately stays silent
    # the second time, which left a full trap drawn under a caption about an
    # even trade. Draw the cage only on the card whose caption is about it.
    # Arrows must agree with the words, and the words are decided downstream:
    # the distilled caption (facts:traps_piece) is substituted into the card
    # AFTER this function returns, so neither caption_payload["rule_name"] nor
    # its caption text is usable as a gate here — trying both silently deleted
    # the whole cage. So apply the SAME rule _trap_caption applies, against the
    # same history, and the two stay in step by construction: if our previous
    # move already trapped this piece on this square, that card owns the
    # lesson and this one draws nothing.
    if _own_trap:
        _hist = list(inputs.move_history_san or [])
        if len(_hist) >= 2:
            try:
                _pb = chess.Board()
                for _san in _hist[:-2]:
                    _pb.push_san(_san)
                _pm = _pb.parse_san(_hist[-2])
                _pt = _rmtp_own(_pb, _pm)
                if (_pt and _pt.get("square") == _own_trap.get("square")
                        and _pt.get("piece") == _own_trap.get("piece")):
                    _own_trap = None
            except Exception:
                pass
    if _own_trap:
        caption_facts["played_move_traps_piece"] = True
        caption_facts["played_trapped_piece"] = _own_trap["piece"]
        caption_facts["played_trapped_square"] = _own_trap["square"]
        caption_facts["played_trapped_escape_count"] = _own_trap["escape_count"]
        caption_facts["played_trapped_on_rim"] = _own_trap.get("on_rim")
        caption_facts["played_trapped_evidence"] = _own_trap.get("escape_evidence") or []
        caption_facts["played_trapped_blocked_by_own"] = _own_trap.get("blocked_by_own") or []

        # THREE colours, three meanings — the picture has to teach, not just
        # decorate. Mohit on the first version: "it should also create L
        # arrows, right? like where are knight possible moves". Showing only
        # our attackers said "these squares are covered" without ever showing
        # that they ARE the piece's squares, which is the whole lesson.
        #
        #   green  b4 -> a5   the move you played, and what it attacks
        #   yellow a5 -> c6   every square the piece can still reach (its
        #                     L-shapes, for a knight — the geometry the cue
        #                     talks about)
        #   red    d5 -> c6   your piece covering that square
        #
        # Ours are prepended so the dedupe keeps OUR colour when an existing
        # rule already drew the same from/to pair (b4->a5 was rendering red
        # because a pre-existing arrow won the tie).
        _trap_arrows = []
        _target = _own_trap["square"]
        _attacker_sq = _own_trap.get("attacker_square") or ""
        _evidence = _own_trap.get("escape_evidence") or []

        # Mohit 2026-09-17 called the geometry "terrible ... it kills the
        # experience", and the suppression added then dropped every arrow that
        # was not tagged -- including this cage, which he had ASKED for a day
        # earlier ("whenever a piece is trapped I want arrows to print out all
        # the positions that piece had"). The cage was never the problem; it
        # was ungoverned.
        #
        # Measured over 500 games, 241 trapped-piece cards: the cage draws a
        # median of 4 arrows and 41% draw just 3, but the tail runs to 41. The
        # victim has exactly ONE escape square on 54% of them, and <=4 on 88%.
        # So the clutter is a tail, not the shape.
        #
        # Above 4 escape squares we ABSTAIN rather than truncate. A cut-off
        # cage is not a smaller lesson, it is a false one -- it shows "here are
        # its squares" while hiding some -- and a piece with six flight squares
        # does not read as trapped anyway. Losing a proof beats showing a
        # misleading one.
        _MAX_ESCAPES = 4
        _CAP = 6
        if len(_evidence) > _MAX_ESCAPES:
            _trap_arrows = []
        else:
            if _attacker_sq:
                _trap_arrows.append({
                    "from": _attacker_sq, "to": _target,
                    "color": "green", "teach": True,
                })
            # The victim's own moves are the shape, so they go before the
            # coverers and are never squeezed out by them.
            for _ev in _evidence:
                _sq = _ev.get("square")
                if _sq:
                    _trap_arrows.append({
                        "from": _target, "to": _sq,
                        "color": "yellow", "teach": True,
                    })
            # Then who covers each one, filling whatever room is left.
            for _ev in _evidence:
                _sq = _ev.get("square")
                for _cov in (_ev.get("covered_by") or []):
                    if len(_trap_arrows) >= _CAP:
                        break
                    _trap_arrows.append({
                        "from": _cov, "to": _sq,
                        "color": "red", "teach": True,
                    })

        _arrows = _trap_arrows + list(caption_payload.get("arrows") or [])
        _high = list(caption_payload.get("highlight_squares") or [])
        for _sq in [_target] + [e.get("square") for e in _evidence]:
            if _sq and _sq not in _high:
                _high.append(_sq)

        # Dedupe: a rule may already have drawn the trapping move. First wins,
        # and ours are first.
        _seen_pairs = set()
        _deduped = []
        for _a in _arrows:
            if not (_a.get("from") and _a.get("to")):
                continue
            _key = (_a["from"], _a["to"])
            if _key in _seen_pairs:
                continue
            _seen_pairs.add(_key)
            _deduped.append(_a)
        caption_payload["arrows"] = _deduped
        caption_payload["highlight_squares"] = _high

    # ─── Board-verified teaching cue (2026-09-16) ───────────────────
    # principle_cue is the amber "how to spot it next time" line the review
    # card renders (GameDecryptionV5.jsx:1784). It has been EMPTY on every
    # card since v139 — measured 0% across v139..v159 on 3,605 mistake cards
    # vs 39% at v135 — because all 35 catalog principles are graded shadow
    # (34) or disabled (1), so can_influence(.., CAPTION) is False for every
    # one of them. Captions became pure diagnosis: correct about what
    # happened, silent about how to see it coming.
    #
    # DELIBERATELY SET AFTER THE PROMOTION LADDER. R_PROMOTED_principle.json
    # renders "{move_san}. {principle_cue}" and overwrites the caption when a
    # principle is present. That rule was dormant only because the cue was
    # always empty; setting the cue earlier re-activated it and replaced a
    # real caption with the cue text ("h3. Next time: after you pick a
    # move..."), duplicating the amber line and losing the description. This
    # cue is for the teaching line only — it must never become the caption.
    #
    # Only two families fire, both naming a SPECIFIC verified piece. The
    # generic "a capture exists" / "a fork exists" facts are deliberately NOT
    # used: measured base rates say a loose piece is present in 99.7% of
    # positions and a forcing move in 82.1%, so a cue keyed on them attaches
    # to cards where it is not the lesson — observed on a free-rook capture
    # and on an even recapture. Right-or-silent beats a cue that is merely
    # true.
    # The fact being TRUE is not enough — it must be what THIS card is about.
    # opp_reply_traps_piece stayed true on the move after the trap was
    # diagnosed, so an even-trade card ("Bxb4 takes your pawn, but your pawn
    # can take back") was given "count the squares it can come back to — this
    # knight had 3". The rendered caption is the evidence that the card is
    # about that piece: require its square to appear in the text.
    _rendered_caption = (caption_payload.get("caption") or "")

    def _card_is_about(square: Any) -> bool:
        sq = str(square or "").strip()
        return bool(sq) and sq in _rendered_caption

    if not (caption_facts.get("principle_cue") or "").strip():
        _f = caption_facts
        # OUR move trapped something: the caption names the cage and the arrows
        # draw it, so the cue carries only the geometry that generalises.
        if _f.get("played_move_traps_piece") and _f.get("played_trapped_piece"):
            _f = dict(_f)
            _f["opp_trapped_piece"] = caption_facts.get("played_trapped_piece")
            _f["opp_trapped_square"] = caption_facts.get("played_trapped_square")
            _f["opp_trapped_on_rim"] = caption_facts.get("played_trapped_on_rim")
            _f["opp_reply_traps_piece"] = True
        if (_f.get("opp_reply_traps_piece") and _f.get("opp_trapped_piece")
                and (caption_facts.get("played_move_traps_piece")
                     or _card_is_about(_f.get("opp_trapped_square")))):
            # Teach the GEOMETRY, not a counting chore. "Count its escape
            # squares" is bookkeeping — slow, mechanical, and it transfers
            # nothing. What transfers is the shape that MAKES the count small,
            # because then you recognise it instead of counting it: a knight
            # moves in an L and an L needs room on two sides, so the edge of
            # the board eats half of them.
            _piece = str(_f.get("opp_trapped_piece") or "piece").lower()
            _sq = str(_f.get("opp_trapped_square") or "")
            _rim = bool(_f.get("opp_trapped_on_rim"))
            _corner = _sq in ("a1", "a8", "h1", "h8")
            if _piece == "knight" and _corner:
                _cue = ("A knight moves in an L, and every L needs room on two "
                        "sides. In the corner only two still fit on the board — "
                        "a corner knight is nearly always trappable.")
            elif _piece == "knight" and _rim:
                _cue = ("A knight moves in an L, and every L needs room on two "
                        "sides. On the edge half of them run off the board — "
                        "eight squares become four. That is why rim knights get "
                        "trapped.")
            elif _piece == "knight":
                _cue = ("A knight in the centre has eight L-squares. When they "
                        "are all covered, something took them away — find what, "
                        "and the same trap works again.")
            elif _piece == "queen":
                _cue = ("A queen is not trapped by the edge — she is trapped by "
                        "her own pieces blocking the way home. Before she goes "
                        "deep, look at the retreat, not the target.")
            elif _piece == "bishop":
                _cue = ("A bishop only ever sees one colour. Enemy pawns fixed on "
                        "that colour can take every square it owns at once.")
            elif _piece == "rook":
                _cue = ("A rook needs an open file or rank. Parked behind its own "
                        "pawns it has almost nowhere to run.")
            else:
                _cue = ("A piece deep in enemy territory needs a way back — check "
                        "the retreat squares before the attack ones.")
            caption_facts["principle_cue"] = _cue
            caption_facts["principle_id_used"] = "TAC_TRAPPED_PIECE"
            # Anchor square, re-checked by the caller against the FINAL
            # caption. V5 can swap in a distilled/facts caption after this
            # decision returns (rule facts:opp_trade on game c7f3400f m12),
            # so the text checked here is not always the text shown.
            caption_facts["principle_cue_anchor_square"] = _f.get("opp_trapped_square")
        elif (_f.get("opp_reply_exposes_undefended") and _f.get("opp_undefended_piece")
                and _card_is_about(_f.get("opp_undefended_square"))):
            caption_facts["principle_cue"] = (
                "A recapture removes a defender as well as a piece. The square "
                "that was guarded twice is often guarded once after the trade — "
                "look at what is left holding it, not at what was taken."
            )
            caption_facts["principle_id_used"] = "TAC_HANGING_PIECE"
            caption_facts["principle_cue_anchor_square"] = _f.get("opp_undefended_square")

    # ─── 11b. Board-grounding verifier (Mohit 2026-05-30) ───────────
    # Run Phase 1 of content_correctness_audit on the rendered caption
    # against the post-played-move FEN. Catches:
    #   • piece-on-square hallucinations ("your queen on a7" when queen
    #     isn't on a7)
    #   • wrong piece type at named square
    #   • wrong-color attribution ("your" vs "their")
    #   • illegal "Played X" SAN claims
    # Does NOT catch semantic claims ("X attacks Y" / counterfactual
    # framing) — Phase 2 with engine would be needed for those.
    # On verify-fail: recover with a stripped severity caption rather
    # than going silent ([[no-hollow-coverage]] is about avoiding fake
    # explanations, not avoiding all output — Mohit 2026-05-30: "captions
    # correct, not silent"). Telemetry: log the failed caption + reason
    # so we can iterate on the templates that hallucinate.
    _verifier_telemetry: Optional[Dict[str, Any]] = None
    try:
        _verifier_telemetry = _verify_and_recover_caption(
            caption_payload=caption_payload,
            fen_before=inputs.fen_before,
            played_move=played_move,
            user_color=inputs.user_color,
            played_san=inputs.played_san,
            best_move_san=inputs.best_move_san,
            pv_after_best=list(inputs.pv_after_best or []),
            severity_practical=practical.practical_tier,
            mover_is_user=bool(inputs.mover_is_user),
        )
        caption_facts["caption_verification"] = _verifier_telemetry
    except Exception as _ver_exc:
        # Defensive: verifier MUST NOT break caption rendering. Any
        # exception logs + the original caption survives unchanged.
        logger.warning(
            f"[caption_verifier] crashed on move {inputs.full_move_number}: "
            f"{_ver_exc!r} — leaving caption unchanged"
        )

    if "caption_verification" not in caption_facts:
        caption_facts["caption_verification"] = {
            "verdict": "not_run",
            "reason": "pipeline_exception",
        }

    # v104 (Mohit 2026-06-03) — floor teaching principle for bare shell.
    # Runs BEFORE tier classification so the enriched caption gets the
    # right tier assignment.
    try:
        _pcue = caption_facts.get("principle_cue") or ""
        _cap_now = caption_payload.get("caption") or ""
        if _pcue and inputs.mover_is_user and _SHELL_RE.match(_cap_now.strip()):
            # A fired failure-mode predicate (e.g. END_THREW_WON_PAWN_PUSH) carries
            # a real, position-relevant principle — prefer it over the generic
            # principle_bank floor on a bare-shell caption. [[principle-bank-is-filler]]
            if not _cap_now.endswith("."):
                _cap_now += "."
            caption_payload["caption"] = f"{_cap_now} {_pcue}"
        else:
            caption_payload["caption"] = _maybe_append_floor_principle(
                _cap_now,
                inputs.full_move_number,
                inputs.mover_is_user,
                inputs.fen_before,
            )
    except Exception as _pb_exc:
        logger.warning(f"[principle_bank] inject failed m{inputs.full_move_number}: {_pb_exc!r}")

    # ─── 11b2. WHY-BAD enrichment (one place) ────────────────────
    # A quiet move that DROPS material (e.g. Bc5 -> Nxc5) is often routed away
    # from R12's failure clauses (it's classified by its quiet/developing nature),
    # so it lands a bare "{played} is a mistake. {best} was better. {principle}"
    # with no reason the played move was bad. When the move is SEE-verified to drop
    # material and the caption carries no why-bad yet, splice the concrete reason
    # into the severity sentence. feedback_mistake_must_explain_why. 2026-06-23.
    try:
        if (inputs.mover_is_user and caption_facts.get("played_drops_material")
                and caption_facts.get("played_drops_piece")
                and caption_facts.get("played_drops_to_san")):
            _cap_wb2 = caption_payload.get("caption") or ""
            _has_whybad = _re_pb.search(
                r"(loses to |lets \S+ (win|capture)|allows \S+ (fork|pin|skew)|"
                r"walks into |drops the |\bhangs\b|win your \w+ on|forking your|"
                r"losing material|loses material in the trade|undefended)",
                _cap_wb2, _re_pb.I)
            _sev_m = _re_pb.search(
                _re_pb.escape(inputs.played_san or "")
                + r" is an? (?:mistake|major blunder|serious mistake|inaccuracy)",
                _cap_wb2)
            if not _has_whybad and _sev_m:
                _drop = (f"{_sev_m.group(0)} — it drops the "
                         f"{caption_facts['played_drops_piece']} after "
                         f"{caption_facts['played_drops_to_san']}")
                caption_payload["caption"] = (
                    _cap_wb2[:_sev_m.start()] + _drop + _cap_wb2[_sev_m.end():])
    except Exception as _wbad_exc:
        logger.warning(f"[why_bad] enrich failed m{inputs.full_move_number}: {_wbad_exc!r}")

    # ─── 11b3. WHY-BAD enrichment: king left in the centre (one place) ───
    # "Missed-best" mistakes where the engine's best move was to CASTLE and the
    # player didn't: the concrete downside is the king stranded in the centre.
    # Fires ONLY when verifiably true — the king is still on its home square (e1/
    # e8) past the opening — never as generic "you missed castling" filler.
    # Verified by narrator_claim_verifier._check_king_center. 2026-06-25.
    try:
        _best_cc = (inputs.best_move_san or "").replace("0", "O")
        if (inputs.mover_is_user and _best_cc in ("O-O", "O-O-O")
                and (inputs.full_move_number or 0) >= 7):
            _cap_cc = caption_payload.get("caption") or ""
            _has_wb_cc = _re_pb.search(
                r"(loses to |lets \S+ (win|capture)|allows |walks into |drops the |"
                r"\bhangs\b|win your \w+ on|losing material|in the cent(er|re)|"
                r"away from defending)", _cap_cc, _re_pb.I)
            _sev_cc = _re_pb.search(
                _re_pb.escape(inputs.played_san or "")
                + r" is an? (?:mistake|major blunder|serious mistake|inaccuracy)", _cap_cc)
            if not _has_wb_cc and _sev_cc:
                _bcc = chess.Board(inputs.fen_before)
                _bcc.push_san(inputs.played_san)
                _mc = chess.WHITE if inputs.mover_is_white else chess.BLACK
                _home = chess.E1 if _mc == chess.WHITE else chess.E8
                if _bcc.king(_mc) == _home:
                    _cc_drop = f"{_sev_cc.group(0)} — it leaves your king in the center"
                    caption_payload["caption"] = (
                        _cap_cc[:_sev_cc.start()] + _cc_drop + _cap_cc[_sev_cc.end():])
    except Exception as _cc_exc:
        logger.warning(f"[why_bad_kingcenter] enrich failed m{inputs.full_move_number}: {_cc_exc!r}")

    # ─── 11c. WHY-BETTER append (one place) ──────────────────────
    # Law: every recommended move needs its WHY (feedback_explain_why_recommended_
    # move_good). The R12 cascade names "{best} was better" but only some variants
    # attach the reason; the rest end bare or with a generic board-state note. Append
    # the board-verified best_move_why HERE in ONE place — fixing every variant at
    # once and auto-carrying future why extensions. Only fires when a real why is
    # available (right-or-silent) and the clause has no why yet. 2026-06-23.
    try:
        _bw = (caption_facts.get("best_move_why") or "").strip()
        _bm = (inputs.best_move_san or "").strip()
        if _bw and _bm and inputs.mover_is_user:
            _cap_wb = caption_payload.get("caption") or ""
            # Cover every measured generic recommendation shell, not only the
            # oldest exact "was better" wording.  The replacement is allowed
            # only because best_move_why is a strict board-derived fact.
            _wb_pat = (
                _re_pb.escape(_bm)
                + r" (?:was (?:the )?(?:better|stronger) move(?: here)?|"
                  r"was better|would have made things harder for your opponent)"
                  r"(?P<reason>\s*[—-]\s*[^.]*)?\."
            )
            _wb_m = _re_pb.search(_wb_pat, _cap_wb)
            # Skip when the shell ALREADY carries a reason, whatever it opens
            # with. The old guard tested for the literal " — it ", so a clause
            # beginning "it's" slipped through the space and was overwritten --
            # which is why "it's the textbook refutation in the Fried Liver
            # Attack" never reached a card: 4 of 17,689 stored reviews name a
            # trap, and 302 of 305 games where the player held the punishment
            # say nothing. 12 of the 37 authored user why-clauses do not start
            # with "it " and were all being replaced by the generic one:
            # curriculum deviation, knight-on-rim, queen-chased, un-developing,
            # blocks-pawn, position-already-losing, and the trap punishment.
            _wb_existing = (_wb_m.group("reason") or "").strip(" —-") if _wb_m else ""
            if _wb_m and not _wb_existing:
                caption_payload["caption"] = (
                    _cap_wb[:_wb_m.start()]
                    + f"{_bm} was better — it {_bw}."
                    + _cap_wb[_wb_m.end():]
                )
    except Exception as _wb_exc:
        logger.warning(f"[why_better] append failed m{inputs.full_move_number}: {_wb_exc!r}")

    # ─── 11d. PIN CONTEXT — the crux the caption kept missing ──────
    # When the user's mistake happens with one of their pieces ABSOLUTELY pinned to
    # their king, that pin is usually THE point (why the piece is fragile, why the move
    # fails). Prepend it before the single final truth boundary. The pin is first
    # derived with detect_relevant_king_pin (is_pinned + the pin ray), then the complete
    # rendered sentence is independently checked with every other chess claim. Mohit
    # 2026-07-01 (m9: the
    # e5 knight was pinned to the king; caption said only "d6 defends it").
    # docs/reasoning_correctness_scope.md
    try:
        if inputs.mover_is_user and abs(int(inputs.cp_loss or 0)) >= 100 and inputs.played_san:
            from services.caption_facts import detect_relevant_king_pin as _drkp
            _pb = chess.Board(inputs.fen_before)
            _pm = _pb.parse_san(inputs.played_san)
            _bm2 = _pb.parse_san(inputs.best_move_san) if inputs.best_move_san else None
            _pin = _drkp(_pb, _pb.turn, _pm, _bm2)
            if _pin:
                _pin_clause = (
                    f"Your {_pin['piece']} on {_pin['square']} is pinned to your king by "
                    f"the {_pin['pinner_piece']} on {_pin['pinner_square']}."
                )
                _existing = (caption_payload.get("caption") or "").strip()
                if "pinned to your king" not in _existing.lower():
                    caption_payload["caption"] = (_pin_clause + " " + _existing).strip()
                    caption_facts["user_king_pin"] = _pin
    except Exception as _pin_exc:
        logger.warning(f"[king_pin] m{inputs.full_move_number}: {_pin_exc!r}")

    # ─── 12. A8 caption tier classification ──────────────────────
    tier = classify_caption_tier(
        caption_text=caption_payload.get("caption") or "",
        rule_name=caption_payload.get("rule_name") or "",
    )

    # ─── DISTILLED CAPTIONS (flag-gated, default OFF) ────────────
    # Swap the caption TEXT with the validated distilled-template render when one is
    # available + engine-verified; all other surfaces (visual/teaching_meta/etc.) stay
    # exactly as the pipeline produced them. Abstain (None) -> keep existing caption.
    # Validated 91% coverage / 99% truth (backend/scripts/validate_everymove.py).
    if _DISTILLED_CAPTIONS_ENABLED:
        try:
            from services.distilled_caption_service import try_distilled_caption as _tdc
            # Coherence: when this move is the one the previous card told them to
            # play, the generic lessons must not scold it. Mohit 2026-09-13
            # (game c7f3400f m11/m12): the coach said "Play b4", the player played
            # b4 -- the engine's best move -- and the next card replied "that can be
            # okay, but first get your other pieces out".
            _tdc_inputs = inputs
            if (
                inputs.mover_is_user
                and state.last_recommended_san
                and _normalize_san_for_match(inputs.played_san)
                == _normalize_san_for_match(state.last_recommended_san)
            ):
                import dataclasses as _dcs
                _tdc_inputs = _dcs.replace(inputs, move_was_our_recommendation=True)
            _dc = _tdc(_tdc_inputs)
            if _dc and _dc[0]:
                caption_payload["caption"] = _dc[0]
                caption_payload["rule_name"] = _dc[1]
        except Exception:
            pass

    # Preserve the verified board explanation before any player-memory
    # framing.  Stage 4 keeps these as separate typed fields even when the
    # visible renderer joins them into one natural coaching paragraph.
    #
    # The unearned-verdict softener (v142) used to run only at the composition
    # boundary further down, which left two holes. The board explanation was
    # snapshotted here, BEFORE softening, so the two surfaces disagreed -- the
    # caption said "f3 is playable" while the explanation still said "f3 is a
    # mistake" -- and the explanation is exactly what the caption falls back to
    # when the personalized text fails verification, so a failure shipped the
    # verdict the softener had just refused. Worse, the personalized path
    # composes its caption FROM this snapshot, and the composed text is long
    # enough that the softener's template-shape guard then declines to touch
    # it: prefixing a sentence about the player made an unearned verdict
    # permanent. Soften once, here, before anything is built on top of it.
    caption_payload["caption"] = _soften_verdict_without_evidence(
        _repair_dash_before_sentence((caption_payload.get("caption") or "").strip()),
        mover_is_user=bool(inputs.mover_is_user),
        cp_loss=inputs.cp_loss or 0,
    )
    _board_explanation = (caption_payload.get("caption") or "").strip()
    _player_connection = ""
    _personal_evidence = None
    _rendered_personalization = False

    # ─── 12.5 COACH CONDUCTOR — the player-model thread ──────────
    # docs/pwc_coach_conductor_scope.md. When the player's motif digest is present
    # and THIS user move is an engine-confirmed instance of one of their recurring
    # patterns (walked-into fork / missed-or-found pin·skewer), surface the
    # personalized STATEMENT thread as the caption — the conductor's chosen "one
    # most useful thing". All gating (relevance, restraint, win eval-gain, engine-
    # truth) lives in coach_conductor; here we let it override + stamp the marker.
    _conductor_thread = None
    if inputs.mover_is_user and (
        inputs.player_motif_threads
        or inputs.player_opening_threads
        or inputs.player_concept_threads
        or inputs.strong_openings
    ):
        try:
            if inputs.player_motif_threads:
                from services.coach_conductor import compute_motif_thread
                _conductor_thread = compute_motif_thread(
                    fen_before=inputs.fen_before,
                    played_san=inputs.played_san,
                    best_move_san=inputs.best_move_san,
                    pv_after_played=inputs.pv_after_played,
                    pv_after_best=inputs.pv_after_best,
                    cp_loss=int(inputs.cp_loss or 0),
                    is_user_move=True,
                    threads=inputs.player_motif_threads,
                    threads_pulled=state.conductor_threads_pulled,
                    eval_before_cp=inputs.eval_before_cp,
                    eval_after_cp=inputs.eval_after_cp,
                    mover_is_white=inputs.mover_is_white,
                )
            # Concept memory — user_concept_understanding weaknesses (2026-07-08,
            # docs/pwc_memory_wiring_scope.md §5 Item B). Fires when the played
            # move's principle_id_used matches a weakness concept in the digest.
            # Priority sits between motif (specific pattern) and endgame
            # (position-type): concept is more general than motif but more
            # user-personal than endgame technique.
            if _conductor_thread is None and inputs.player_concept_threads:
                from services.coach_conductor import compute_concept_thread
                _conductor_thread = compute_concept_thread(
                    principle_id_used=caption_facts.get("principle_id_used"),
                    principles_violated=caption_facts.get("caption_facts_principles_violated"),
                    severity=caption_facts.get("severity_practical") or caption_facts.get("severity"),
                    played_san=inputs.played_san,
                    is_user_move=True,
                    threads=inputs.player_concept_threads,
                    threads_pulled=state.conductor_threads_pulled,
                )
            # Endgame technique recognition — a position-based STATEMENT, only when
            # no motif thread already won. Technique-verified by the concept detectors.
            if _conductor_thread is None:
                from services.coach_conductor import compute_endgame_thread
                _conductor_thread = compute_endgame_thread(
                    fen_before=inputs.fen_before,
                    played_san=inputs.played_san,
                    user_is_white=inputs.mover_is_white,
                    threads_pulled=state.conductor_threads_pulled,
                )
            # Opening recurrence — the player's recurring, engine-confirmed opening
            # mistake. PREPENDS its "again" framing to the move's caption so the
            # engine-grounded why + better move survive. Only when no motif/endgame
            # thread already won.
            if _conductor_thread is None and inputs.player_opening_threads:
                from services.coach_conductor import compute_opening_thread
                _conductor_thread = compute_opening_thread(
                    move_history_san=inputs.move_history_san,
                    played_san=inputs.played_san,
                    best_move_san=inputs.best_move_san,
                    practical_tier=caption_facts.get("severity_practical"),
                    user_is_white=inputs.mover_is_white,
                    threads=inputs.player_opening_threads,
                    threads_pulled=state.conductor_threads_pulled,
                )
            # Opening STRENGTH — the mirror of the mistake thread (Item E,
            # docs/pwc_memory_wiring_scope.md). Fires when the user plays a
            # sound move in an opening they own (≥5 games, ≥55% win rate).
            # Same threads_pulled key as the mistake thread so mutually
            # exclusive within a game — a player who's ALSO recurring-
            # mistake-prone in that opening gets the mistake thread first;
            # a player playing cleanly gets the strength callback.
            if _conductor_thread is None and inputs.strong_openings:
                from services.coach_conductor import compute_opening_strength_thread
                _conductor_thread = compute_opening_strength_thread(
                    move_history_san=inputs.move_history_san,
                    played_san=inputs.played_san,
                    practical_tier=caption_facts.get("severity_practical"),
                    user_is_white=inputs.mover_is_white,
                    strong_openings=inputs.strong_openings,
                    threads_pulled=state.conductor_threads_pulled,
                )
            # Identity lead-in (Item C, docs/pwc_memory_wiring_scope.md).
            # Decorate the first-fired conductor thread of the session with a
            # short identity-cued phrase if the fired kind aligns with the
            # user's known main_leak or phase vulnerability. Silent otherwise,
            # once-per-session restraint.
            if _conductor_thread and inputs.player_identity:
                try:
                    from services.coach_conductor import maybe_prepend_identity_lead_in
                    _conductor_thread = maybe_prepend_identity_lead_in(
                        _conductor_thread,
                        inputs.player_identity,
                        state.conductor_threads_pulled,
                    )
                except Exception as _il_exc:
                    logger.info(f"[conductor] identity lead-in skipped: {_il_exc}")
            # Goal anchor (Phase 1 goal-filter, 2026-07-08). When the fired
            # thread's kind aligns with today's session focus topic, append a
            # short anchor line so the goal card and the coaching voice read
            # as one connected thing. Once per session.
            if _conductor_thread and inputs.session_focus:
                try:
                    from services.coach_conductor import maybe_apply_goal_anchor
                    _conductor_thread = maybe_apply_goal_anchor(
                        _conductor_thread,
                        inputs.session_focus,
                        state.conductor_threads_pulled,
                    )
                except Exception as _ga_exc:
                    logger.info(f"[conductor] goal anchor skipped: {_ga_exc}")

            if _conductor_thread and _conductor_thread.get("text"):
                _thread_text = (_conductor_thread.get("text") or "").strip()
                _thread_side = _conductor_thread.get("side")
                if _thread_side in {"offense", "defense", "concept", "opening"}:
                    _player_connection = _thread_text
                    _personal_evidence = {
                        "eligible": True,
                        "source": (
                            "strong_openings"
                            if _conductor_thread.get("kind") == "opening_strength"
                            else {
                                "offense": "player_motif_threads",
                                "defense": "player_motif_threads",
                                "concept": "player_concept_threads",
                                "opening": "player_opening_threads",
                            }.get(_thread_side)
                        ),
                        "kind": _conductor_thread.get("kind"),
                        "key": _conductor_thread.get("motif"),
                    }

                if _CAUSAL_PERSONAL_CAPTIONS_ENABLED:
                    # Personal memory is context, never a substitute for the
                    # move-specific chess reason.  If there is no board
                    # explanation, keep the visible output honest and silent.
                    if _board_explanation:
                        caption_payload["caption"] = (
                            _thread_text + " " + _board_explanation
                        ).strip()
                        _rendered_personalization = bool(_player_connection)
                    else:
                        caption_payload["caption"] = ""
                    caption_payload["rule_name"] = "R_CONDUCTOR_stage4"
                elif inputs.player_context_shadow_only:
                    # Measure eligibility and retain the structured evidence,
                    # without changing the user-visible caption.
                    pass
                elif _conductor_thread.get("prepend"):
                    # Keep the underlying engine why + better move; lead with the
                    # recurrence. If the move had no caption (shouldn't for a real
                    # mistake), at least name the engine's better move so the
                    # "why" law isn't violated.
                    _existing = (caption_payload.get("caption") or "").strip()
                    if _existing:
                        caption_payload["caption"] = _conductor_thread["text"] + " " + _existing
                    else:
                        _b = inputs.best_move_san
                        caption_payload["caption"] = _conductor_thread["text"] + (
                            f" {inputs.played_san} — {_b} was the stronger move." if _b
                            else f" {inputs.played_san} slips here.")
                else:
                    caption_payload["caption"] = _conductor_thread["text"]
                if not _CAUSAL_PERSONAL_CAPTIONS_ENABLED and not inputs.player_context_shadow_only:
                    caption_payload["rule_name"] = "R_CONDUCTOR_thread"
        except Exception as _ct_exc:
            logger.warning(f"[conductor] thread compute failed m{inputs.full_move_number}: {_ct_exc!r}")

    # Exact WDL truth outranks approximate engine prose, but only for a fully
    # validated result change. It deliberately names no unpromoted technique.
    _exact_transferable_instruction = ""
    if (
        _exact_endgame is not None
        and _exact_endgame_cause is not None
    ):
        (
            _exact_headline,
            _exact_caption,
            _exact_transferable_instruction,
        ) = render_exact_endgame_cause(_exact_endgame_cause)
        caption_payload["caption"] = _exact_caption
        caption_payload["rule_name"] = "R_EXACT_ENDGAME_RESULT"
        caption_payload["arrows"] = []
        caption_payload["highlight_squares"] = []
        caption_facts["exact_endgame_evidence"] = _exact_endgame.contract_dict()
        caption_facts["exact_endgame_headline"] = _exact_headline
        _board_explanation = _exact_caption
        _player_connection = ""
        _personal_evidence = None
        _rendered_personalization = False

    # Stage 4's final truth boundary runs AFTER personalization.  The older
    # boundary above protected the base caption but conductor text was appended
    # later and could bypass it.  If the composed text fails, first retain the
    # already-verified board explanation; only then use the deterministic floor.
    _final_verified = False
    try:
        from services.narrator_claim_verifier import verify_caption as _stage4_verify
        from services.caption_fallback_tiers import tier23_caption as _stage4_floor
        _stage4_facts = {
            "move_san": inputs.played_san,
            "fen_before": caption_facts.get("fen_before") or inputs.fen_before,
            "fen_after": caption_facts.get("fen_after"),
            "is_user_move": bool(inputs.mover_is_user),
            "moving_piece_color": caption_facts.get("moving_piece_color"),
            "is_checkmate": bool(caption_facts.get("is_checkmate")),
            "cp_loss": abs(int(inputs.cp_loss or 0)),
            "eval_before_cp": inputs.eval_before_cp,
            "eval_after_cp": inputs.eval_after_cp,
            "best_move_san": inputs.best_move_san,
            "pv_after_played": list(inputs.pv_after_played or []),
            "pv_after_best": list(inputs.pv_after_best or []),
            "mate_threat_evidence": caption_facts.get("mate_threat_evidence"),
            "opp_unsafe_recapture_pawn_fork_proof": caption_facts.get(
                "opp_unsafe_recapture_pawn_fork_proof"
            ),
        }
        def _verify_final(text: str):
            return _stage4_verify(text, _stage4_facts, strict_v2=True)

        # Repair a dash that introduces a whole sentence before anything is
        # verified or shipped, so every downstream path sees the fixed text.
        _repaired = _repair_dash_before_sentence(
            (caption_payload.get("caption") or "").strip())
        _repaired = _soften_verdict_without_evidence(
            _repaired, mover_is_user=bool(inputs.mover_is_user),
            cp_loss=inputs.cp_loss or 0)
        if _repaired != (caption_payload.get("caption") or "").strip():
            caption_payload["caption"] = _repaired

        _candidate = (caption_payload.get("caption") or "").strip()
        _violations = _verify_final(_candidate) if _candidate else []
        if _violations:
            _base_violations = (
                _verify_final(_board_explanation)
                if _board_explanation else ["missing board explanation"]
            )
            if not _base_violations:
                caption_payload["caption"] = _board_explanation
                caption_payload["rule_name"] = (
                    (caption_payload.get("rule_name") or "") + "→PERSONAL_SOFTENED"
                )
                _rendered_personalization = False
            else:
                # SENTENCE SALVAGE — before falling to the floor.
                #
                # The verifier is a whole-caption gate: one false clause
                # anywhere discards every true clause with it, and the floor it
                # falls to is the hollow comparative ("You played X; Y was
                # stronger — it trades his bishop"). On lichess qBNJQg3g move 16
                # the pipeline had already produced the caption the game needed —
                #
                #   "Qf6 lets Qxc5 win your bishop on c5. Nxd3+ was better — it
                #    attacks the undefended pawn on f2, and your knight ..."
                #
                # — and threw ALL of it away over a `free_when_defended`
                # complaint about the SECOND sentence. The player was left with
                # no idea why their move lost a bishop.
                #
                # Keep the sentences that verify, drop the ones that don't. This
                # can only ever retain board-verified text; it never invents a
                # claim, so it cannot lower truthfulness — every surviving
                # sentence passed the same check the floor passes, and the join
                # is re-verified before shipping.
                # docs/review_truth_layer_scope.md, feedback_coverage_is_first_class
                _salvaged = _salvage_verified_sentences(_candidate, _verify_final)
                if _salvaged:
                    caption_payload["caption"] = _salvaged
                    caption_payload["rule_name"] = (
                        (caption_payload.get("rule_name") or "") + "→SENTENCE_SALVAGED"
                    )
                    _board_explanation = _salvaged
                    _rendered_personalization = False
                else:
                    _safe, _ = _stage4_floor(caption_facts, flagged_mistake=True)
                    if _safe and not _verify_final(_safe):
                        caption_payload["caption"] = _safe
                        caption_payload["rule_name"] = (
                            (caption_payload.get("rule_name") or "") + "→FINAL_VERIFY_SOFTENED"
                        )
                        _board_explanation = _safe
                        _rendered_personalization = False
        # A stalemate ends the game as a draw, and 127 of the 132 corpus
        # cards where a winning player stalemated never said so. One read
        # "Your opponent tidys up the king, keeping it safe" on the move that
        # turned a lost game into a draw.
        #
        # It lives here, not in a rule file, because it is a property of the
        # board after the move rather than of any rule: those 132 come from 16
        # different rules, and 64 are opponent moves carrying a stored cp_loss
        # of 0 that every severity gate routes to the praise tiers. Patching
        # one rule file moves 27 of 132.
        #
        # Leading matters twice: it is the headline, and the word cap cuts from
        # the end, so what gets dropped is the less important half. Placed
        # above the final verify so the result passes the same check as every
        # other caption. docs/stalemate_scope.md
        if caption_facts.get("played_is_stalemate"):
            caption_payload["caption"] = _lead_with_the_stalemate(
                caption_payload.get("caption") or "",
                played_san=inputs.played_san,
                mover_is_user=bool(inputs.mover_is_user),
                threw_away_win=bool(
                    caption_facts.get("played_stalemate_threw_away_win")
                ),
                best_move_san=inputs.best_move_san,
            )
            caption_payload["rule_name"] = (
                (caption_payload.get("rule_name") or "") + "→STALEMATE_LEAD"
            )
            _board_explanation = caption_payload["caption"]

        _final_text = (caption_payload.get("caption") or "").strip()
        _final_verified = bool(
            _final_text and not _verify_final(_final_text)
        )
    except Exception as _stage4_exc:
        logger.warning(
            f"[stage4_final_verify] m{inputs.full_move_number}: {_stage4_exc!r}"
        )
        # The truth boundary is unavailable, so no chess claim may ship.  Empty
        # text is intentional: callers can render their non-claim UI state, but
        # they cannot mistake an unchecked sentence for verified coaching.
        caption_payload["caption"] = ""
        caption_payload["rule_name"] = (
            (caption_payload.get("rule_name") or "") + "→FINAL_VERIFY_SILENT"
        )
        _board_explanation = ""
        _rendered_personalization = False

    # Caption classification must describe the final text, not the pre-
    # personalization template selected earlier.
    tier = classify_caption_tier(
        caption_text=caption_payload.get("caption") or "",
        rule_name=caption_payload.get("rule_name") or "",
    )

    _provenance = [caption_payload.get("rule_name") or "R_FALLBACK"]
    if _exact_endgame_cause is not None:
        _provenance.append(
            f"exact_endgame:{_exact_endgame_cause.evidence_fingerprint}"
        )
    _primary_reason = caption_facts.get("primary_reason") or {}
    if isinstance(_primary_reason, dict) and _primary_reason.get("category"):
        _provenance.append(f"reason:{_primary_reason['category']}")
    if _conductor_thread:
        _provenance.append(
            f"player_context:{_conductor_thread.get('side')}:{_conductor_thread.get('kind')}"
        )

    # Transfer the lesson without inventing a new knowledge catalog.  Prefer
    # the exact principle cue selected earlier.  A fired tactical thread may
    # reuse the matching cue from the canonical principle catalog.  Otherwise
    # a strict best-move purpose fact can become a position-specific next-game
    # scan.  If none of those facts exists, stay empty and honest.
    _transferable_instruction = (
        _exact_transferable_instruction
        or caption_facts.get("principle_cue")
        or ""
    )
    if not _transferable_instruction and _conductor_thread:
        _motif_principle = {
            "fork": "TAC_FORK_PATTERN",
            "pin": "TAC_PIN_PATTERN",
            "skewer": "TAC_SKEWER_PATTERN",
            "discovered_attack": "TAC_DISCOVERED_PATTERN",
            "loose_piece": "TAC_HANGING_PIECE",
        }.get(_conductor_thread.get("motif"))
        _entry = _PRINCIPLES_BY_ID.get(_motif_principle, {}) if _motif_principle else {}
        _transferable_instruction = (
            _entry.get("cue_top_n") or _entry.get("cue_absent") or ""
        )
    if not _transferable_instruction and inputs.mover_is_user and int(inputs.cp_loss or 0) >= 30:
        _best_purpose = (caption_facts.get("best_move_why") or "").strip().rstrip(".")
        if _best_purpose:
            _transferable_instruction = (
                f"Next time, before you commit, look for a move that {_best_purpose}."
            )

    explanation = CaptionExplanation(
        board_explanation=_board_explanation,
        player_connection=_player_connection,
        transferable_instruction=_transferable_instruction,
        confidence=(
            "verified" if _final_verified
            else "limited" if (caption_payload.get("caption") or "").strip()
            else "silent"
        ),
        provenance=_provenance,
        personal_evidence=_personal_evidence,
        final_verified=_final_verified,
        rendered_personalization=_rendered_personalization,
        rollout_mode=("visible" if _CAUSAL_PERSONAL_CAPTIONS_ENABLED else "shadow"),
    )

    # ─── Build the decision ──────────────────────────────────────
    text = TextSurface(
        caption=caption_payload.get("caption") or "",
        rule_name=caption_payload.get("rule_name") or "R_FALLBACK",
    )
    # V5 move_output reads from caption_payload (renderer output),
    # NOT caption_facts. Match that source for zero-diff parity.
    # Mohit 2026-09-17: "our geometry the way it shows is terrible, it kills
    # the experience -- remove that, don't delete the code, just stop showing
    # geometry." The trap picture draws up to _CAP = 14 arrows on one board,
    # which reads as clutter rather than a lesson. Every arrow the review card
    # renders passes through here, so this is the one place to hold them back.
    #
    # Nothing is deleted: the builders still run and still populate
    # caption_payload, so the facts, the cap and the dedupe are all intact and
    # REVIEW_LEGACY_ARROWS=true restores the old picture unchanged. Arrows that
    # are themselves the lesson opt back in by carrying "teach": True, so a
    # focused two-or-three arrow picture can ship without reopening the flood.
    _arrows_out = list(caption_payload.get("arrows") or [])
    # The one picture that earns its place on the board today: a check that
    # also piles a second attacker onto a piece. Tagged "teach" so it survives
    # the suppression below.
    # ...but only when it is true of the board the card is SHOWING. The review
    # board renders fen_after -- board_before plus the move that was PLAYED --
    # while this picture is computed on board_before plus the BEST move. Those
    # are the same position only when the player found the best move.
    #
    # Measured over 500 games: of 514 cards drawing this picture, 276 (54%)
    # drew it for a position the card never displays. The other two teach-arrow
    # builders (the trap cage and the punishment arrows) both compute on
    # board_before + played_move, so they were aligned all along; this one was
    # the odd source out.
    #
    # Reported 2026-09-22, on an opponent card: "Opponent's b4 is a major
    # blunder. Play Qe7 -- it attacks the queen on h7", with the arrow drawn
    # at White's queen on h7. best_move_uci there is the OPPONENT's best
    # alternative, a move the caption never mentions and the board never
    # reaches -- and "Qe7" happened to be legal for both sides, so the two
    # readings of three characters looked like one.
    # The engine's continuation after its own best move. v181 made this the
    # source of the check-picture's TARGET, so both callers below need it: one
    # draws the picture on the board the player reached, the other relocates it
    # onto the board the best move would have reached.
    _engine_line = list(inputs.pv_after_best or ())
    if not _engine_line and inputs.best_move_san == inputs.played_san:
        # They played the best move, so the line after it IS the best line.
        _engine_line = list(inputs.pv_after_played or ())

    if inputs.mover_is_user:
        _played_uci = played_move.uci() if played_move else ""
        _teach_arrows = (
            _check_attack_arrows(board_before, inputs.best_move_uci, _engine_line)
            if _played_uci and _played_uci == (inputs.best_move_uci or "")
            else []
        )
    else:
        # Their move is on the board; what the card recommends is our reply.
        # When the payoff is delayed, the sequence picture explains more than
        # the single-move one -- it is the difference between "here is what
        # the knight attacks" and "here is why the rook gets the bishop".
        _after_opp_board = None
        try:
            _after_opp_board = board_before.copy()
            _after_opp_board.push(played_move)
        except Exception:
            _after_opp_board = None
        # ...but only when the caption is actually ABOUT our reply.
        #
        # An opponent card can recommend one of two different moves. The R12
        # opp-punish variants say "Play <our reply>". The fallback tiers say
        # "<their better move> was stronger" -- caption_fallback_tiers'
        # R_TIER_missed_principle, which names best_move_san. The arrow
        # builders only ever knew about the first, so on a fallback card the
        # words named THEIR move and the board drew OURS.
        #
        # Reported 2026-09-28 on eb189840 move 10: "Your opponent played d6;
        # Nxe4 was stronger - it wins a pawn", drawn with g5->f6 and f6->e7,
        # which is Bxf6. Two different moves on one card, which is the same
        # fault fixed on 2026-09-22 arriving by a different route.
        #
        # Their better move is NOT drawn instead: it is legal on the board
        # before their move, not on the board this card renders, so drawing
        # it would trade a mismatch for a picture of a position the player
        # cannot see. Silence beats contradiction.
        _reply_san = caption_facts.get("user_best_reply_san")
        _caption_text = str(caption_payload.get("caption") or "")
        _caption_is_about_reply = bool(
            _reply_san and _normalize_san_for_match(_reply_san)
            in _normalize_san_for_match(_caption_text)
        )
        if _caption_is_about_reply:
            _teach_arrows = _line_sequence_arrows(
                _after_opp_board, inputs.pv_after_played
            ) or _line_sequence_arrows(
                _after_opp_board, caption_facts.get("user_reply_pv")
            ) or _reply_attack_arrows(
                board_before, played_move, _reply_san
            )
        else:
            _teach_arrows = []
    # One picture per card. The check picture is rarer and more striking, so it
    # wins when both are available; otherwise show what the blunder gave away.
    # Their reply AND the piece it costs, in that order -- the two halves of
    # one sentence, not a choice between them.
    #
    # v187 made this an either/or and Mohit caught it immediately: "now, it
    # removed the arrow of g7 to g6 attacking the queen, the idea is to show
    # player why this move is bad when he played Qh5, as he didn't see g6, you
    # know while already knight is under attack, so 2 attacks and one is gone
    # now". He is right, and the chain only reads with both: g6 blocks the
    # check and hits the queen, so the queen has to move, so the knight it was
    # defending falls. Drawing only the knight loses the cause; drawing only
    # g6 was the v186 picture that never mentioned the knight.
    if not _teach_arrows:
        _punish = _punishment_arrows(
            board_before,
            played_move,
            mover_is_user=inputs.mover_is_user,
            cp_loss=inputs.cp_loss,
            # A real parameter, never read off `inputs` inside the builder:
            # the narration block lost a whole section to exactly that slip.
            pv_after_played=list(inputs.pv_after_played or ()),
        )
        _victim = _abandoned_defender_arrows(
            board_before,
            played_move,
            mover_is_user=inputs.mover_is_user,
            cp_loss=inputs.cp_loss,
            pv_after_played=list(inputs.pv_after_played or ()),
        )
        # Four is the ceiling the other builders already observe, and the
        # punishment half comes first because it is the move they play next.
        _seen_pairs = set()
        _teach_arrows = []
        for _a in list(_punish) + list(_victim):
            _key = (_a["from"], _a["to"])
            if _key in _seen_pairs:
                continue
            _seen_pairs.add(_key)
            _teach_arrows.append(_a)
            if len(_teach_arrows) >= 4:
                break
    if _teach_arrows:
        # On a collision the TAGGED copy wins. The old order kept the untagged
        # one, which the suppression filter below then stripped -- so a picture
        # another rule had already drawn came out as no arrows at all.
        #
        # Qd5+ forking the rook on a8 and the king on g8 rendered with an empty
        # board: the fork rule emitted d5->a8 and d5->g8 untagged, the dedupe
        # dropped the tagged duplicates as "already there", and the filter then
        # removed the originals for having no tag.
        _teach_pairs = {(a["from"], a["to"]) for a in _teach_arrows}
        _arrows_out = _teach_arrows + [
            a for a in _arrows_out
            if (a.get("from"), a.get("to")) not in _teach_pairs
        ]
    if os.environ.get("REVIEW_LEGACY_ARROWS", "false").strip().lower() != "true":
        _arrows_out = [a for a in _arrows_out if a.get("teach") is True]
    # Mohit asked for exactly this picture (fb_1c52480b2e9b, v166): "it should
    # draw a line from Qa5 to [the] bishop and our bishop to [the] bishop and a
    # queen checking the king, so it's easy." It is real teaching -- it was
    # just being drawn over the position the player actually reached, where
    # those pieces are somewhere else. So it ships on its own board instead of
    # being dropped.
    _best_arrows: List[Dict[str, str]] = []
    _best_arrows_fen = ""
    # Declared outside the branch on purpose: it is read again further down to
    # decide whether the shape arrows are suppressed, and the branch does not
    # always run. A name that only exists on some paths is how this file lost a
    # whole caption block to a NameError swallowed by a bare except.
    _mate_picture: List[Dict[str, str]] = []
    if not inputs.mover_is_user or (played_move and played_move.uci() != (inputs.best_move_uci or "")):
        # When the recommended move is MATE, show the mate rather than the
        # attack. Mohit: "this is a proper mating pattern... this is a geometry
        # to learn and remember". _check_attack_arrows draws what the move
        # attacks, which on a mate is the king and nothing else; the lesson is
        # which squares the king cannot use and who covers them.
        _mate_picture = _mate_geometry_arrows(
            board_before, inputs.best_move_uci
        )
        # Order matters: mate first, then the whole winning plan, then the
        # single-move pictures. Mohit 2026-10-06: "i want to show the complete
        # idea with arrow... so user can see everything together". A lone
        # arrow onto a piece that then runs away teaches a 1000-rated player
        # nothing; the chase is the lesson.
        # Order matters, and v166's picture keeps its place. _check_attack_arrows
        # is the one Mohit asked for in fb_1c52480b2e9b and three tests pin its
        # exact output; the plan and the bare move are what fill the silence
        # BELOW it, not replacements for it.
        _candidate = (
            _mate_picture
            or _check_attack_arrows(
                board_before, inputs.best_move_uci, _engine_line
            )
            or winning_plan_arrows(
                board_before, inputs.best_move_uci, inputs.pv_after_best
            )
            or recommended_move_arrows(
                board_before, inputs.best_move_uci, inputs.pv_after_best
            )
        )
        if _candidate:
            try:
                _bb = board_before.copy()
                _bb.push(chess.Move.from_uci(str(inputs.best_move_uci)))
                _best_arrows = _candidate
                _best_arrows_fen = _bb.fen()
            except Exception:
                _best_arrows = []
                _best_arrows_fen = ""
    # When the lesson is a missed mate, the mate picture is the only picture.
    #
    # Mohit 2026-10-06, after the badge and caption were both fixed: "now shows
    # missed mate, but arrows are still showing for missed skewer". He was
    # looking at a card that said "Bd5 missed a checkmate" over an alignment
    # picture -- e8->d8, d8->c7, d5->a8 -- drawn by a shape detector that had
    # fired independently. Three surfaces, two of them now agreeing and the
    # loudest one still telling the old story.
    #
    # The mate geometry cannot simply be moved onto this board: it lives on the
    # position AFTER the mating move, which is why it carries its own FEN. On
    # the board the player is looking at, their bishop has already left e6, so
    # e6->d7 is not a line that exists. So the shape arrows go rather than get
    # replaced -- silence beats contradiction, the same rule the reply-arrow
    # builder follows -- and the mate picture stays on the surface whose board
    # it is true of.
    if not shape_arrows_survive_mate_picture(_mate_picture, _best_arrows):
        _arrows_out = mate_arrows_for_played_board(
            board_before, played_move, inputs.best_move_uci
        )
    # A card that names a better move and draws nothing is the complaint that
    # keeps coming back -- "no arrow here, why the hell", "now why not arrow
    # here?". The recommended move is legal on the board before the played
    # move, and that board shares its coordinates with the one on screen, so
    # the instruction can always be drawn even when no threat picture fires.
    # The whole plan goes on the board the player is looking at.
    #
    # v166 kept the recommended move's consequences off this board because
    # drawing them here was "real teaching drawn over the wrong position". That
    # rule was written against arrows that CONTRADICT what is on screen -- an
    # arrow starting where a piece no longer stands, describing a line that is
    # blocked right now.
    #
    # Mohit 2026-10-06 drew the distinction the rule was missing: "it's not
    # wrong teaching, it's what was missed from the player and it's what makes
    # him see things". A plan he did not play is not a false claim about the
    # position; it is the lesson, and the caption beside it already says
    # "Be5 was better". Putting it one click away under "What if I played X?"
    # defeats the point of showing it -- he asked to "see everything together".
    #
    # So the contract changes deliberately, with its tests, rather than being
    # broken by accident: this board may carry the plan for the move we are
    # recommending. What has NOT changed is that every arrow must be a move the
    # engine's own line actually plays, drawn in the coordinates of the
    # position before the played move.
    if not _arrows_out and inputs.mover_is_user and inputs.best_move_uci:
        # A SACRIFICE never passes the winning-plan test, because the whole
        # point is that material comes out level or worse while the initiative
        # does not. Mohit 2026-10-06, on a card whose engine move was Bxf2+:
        # "this is a sacrifice, so it should show the complete line why a
        # sacrifice is better here".
        #
        # On rnbq1rk1/ppp2ppp/3p1n2/2b1p1N1/2B1P3/P1N5/1PPP1PPP/R1BQK2R b the
        # line is Bxf2+ Kxf2 Ng4+ Kg1 Qxg5: give the bishop, the king MUST
        # take, the knight comes with check, the queen collects the knight on
        # g5. Net is +90 -- pawn and knight for a bishop -- so the 300cp gate
        # refuses it, correctly and uselessly.
        #
        # _line_sequence_arrows already knows this shape; it was built for the
        # Bxf7+ card in v183 and has a branch for a first capture that LOSES
        # material on its own square. It was only ever wired to opponent cards.
        _sac_line = (
            [inputs.best_move_san] + list(inputs.pv_after_best or ())
            if inputs.best_move_san else []
        )
        _arrows_out = winning_plan_arrows(
            board_before, inputs.best_move_uci, inputs.pv_after_best
        ) or _line_sequence_arrows(board_before, _sac_line) or [
            a for a in recommended_move_arrows(
                board_before, inputs.best_move_uci, inputs.pv_after_best
            )
            if a.get("color") == "blue"
        ]

    # The back-rank warning rides ALONG with the material reason, never instead
    # of it. Mohit 2026-10-06: "this is backrank mate but doesn't show in
    # caption or arrows". His card already said he drops a rook, which is true
    # and is not the bigger danger: the king on g8 has f7, g7 and h7 all filled
    # by its own pawns, so a rook on the back row mates. It is appended rather
    # than substituted because losing the rook is still the first thing he
    # needs to know.
    #
    # Not phrased as a mate claim: on that card Black holds with Be6 or Qf6, so
    # the sentence says the king has no way out, which is true of the position
    # whatever they choose.
    if caption_facts.get("back_rank_exposed") and caption_payload.get("caption"):
        try:
            from services.caption_templates import render_template
            _br = render_template("R12_blunder", "back_rank_no_escape", caption_facts)
            if _br and _br not in caption_payload["caption"]:
                caption_payload["caption"] = (
                    caption_payload["caption"].rstrip() + " " + _br
                )
        except Exception:
            pass

    visual = VisualSurface(
        arrows=_arrows_out,
        highlight_squares=caption_payload.get("highlight_squares") or [],
        best_move_arrows=_best_arrows,
        best_move_arrows_fen=_best_arrows_fen,
    )
    # Mohit 2026-05-31: extract the severity WORD R12 chose for the
    # rendered caption so downstream surfaces (Lab badge, mastery
    # evidence cards, future home-intel) don't text-parse the caption
    # themselves. R12's severity_phrases are fixed strings; matching
    # them here is reliable. Returns None for non-R12 captions (R15
    # good-move, opening intro, silent) so badge falls back to stored
    # classification.
    _caption_severity_word = _extract_caption_severity_word(
        caption_payload.get("caption") or ""
    )
    teaching_meta = TeachingMeta(
        severity=canonical.user_facing_tier,
        severity_canonical=practical.canonical_tier,
        severity_practical=practical.practical_tier,
        caption_tier=tier,
        caption_severity_word=_caption_severity_word,
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
    if _CAUSAL_PERSONAL_CAPTIONS_ENABLED and explanation.transferable_instruction:
        # Existing Review UI already has a distinct habit-cue surface.  Feed
        # it from the typed Stage 4 decision only after rollout is enabled;
        # shadow generation remains invisible.
        teaching_meta.principle_cue = explanation.transferable_instruction
    state_mutations = StateMutations(
        fired_principles_added=_fired_principles_added,
        fired_state_keys_added=_fired_state_keys_added,
        active_trap_after=new_active_trap,
        active_trap_cleared=(state.active_trap is not None and new_active_trap is None),
        active_trap_step_cursor_after=new_step_cursor,
        active_trap_setup_completed_by_user_after=new_setup_completed,
        prev_user_eval_after=(inputs.eval_after_cp if inputs.mover_is_user else state.prev_user_eval_after),
        # Remember what we just told them to play. Set on an opponent card
        # ("Play b4 ..."); only ever read by the very next move.
        last_recommended_san_after=(
            caption_facts.get("user_best_reply_san")
            if not inputs.mover_is_user else None
        ),
        conductor_threads_pulled_added=(
            {f"{_conductor_thread['side']}:{_conductor_thread['motif']}"}
            if _conductor_thread else set()
        ),
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

    legal_material_loss_cause = None
    if inputs.mover_is_user and inputs.best_move_san:
        # Already built above, before the caption was written, so the rules
        # could see a forced mate. Reused here rather than replayed twice.
        # build_legal_material_loss_cause answers a board question -- "after
        # this move, is something of mine worth >=150cp capturable for free?"
        # -- and this path used the answer as a verdict on the move, with no
        # other test at all. See the two gates below; both were chosen from
        # the measured distribution of 641 cards over 500 analysed games, not
        # from taste. Cross-tab (cost of the move x how decided the game
        # already was, eval units normalised):
        #
        #   cp_loss     close   one better   decided 600+   over 1500+   row
        #     <30           5           14             23            7    49
        #     <50           0            7              3            4    14
        #     <75           3           12             16            2    33
        #    <100           2           15             16            0    33
        #    <150          10           23             23            5    61
        #    <300           8           53             65            0   126
        #   >=300          47          159             77           42   325
        _board_cause_allowed = (
            int(inputs.cp_loss or 0) >= LEGAL_LOSS_MIN_COST_CP
            and not _position_already_decided(inputs.eval_after_cp)
        )
        board_cause = (
            build_legal_material_loss_cause(
                fen_before=inputs.fen_before,
                played_san=inputs.played_san,
                best_move_san=inputs.best_move_san,
                minimum_gain_cp=REVIEW_LEGAL_LOSS_FLOOR_CP,
            )
            if _board_cause_allowed
            else None
        )
        if (
            exact_line_cause is not None
            and exact_line_cause.lesson_kind
            in {"missed_forced_mate", "allowed_forced_mate"}
        ):
            legal_material_loss_cause = exact_line_cause
        else:
            legal_material_loss_cause = board_cause or exact_line_cause

    selected_cause = _exact_endgame_cause or legal_material_loss_cause
    candidate_comparison = build_candidate_comparison(inputs, selected_cause)

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
        coach_line_moves=_coach_line_moves,
        coach_line_length_hint=_coach_line_length_hint,
        socratic_extras=socratic_extras,
        explanation=explanation,
        cause=selected_cause,
        conductor_thread=_conductor_thread,
        exact_endgame_evidence=(
            _exact_endgame.contract_dict() if _exact_endgame is not None else None
        ),
        human_policy_evidence=inputs.human_policy_evidence,
        candidate_comparison=candidate_comparison,
    )
