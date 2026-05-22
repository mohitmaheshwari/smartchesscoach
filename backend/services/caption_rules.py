"""Caption rule registry — pure dispatch, no user-facing strings.

The architecture laws (R1-R5) and authoring guide live in
`backend/data/captions/README.md` alongside the content they govern.
Read that first if you're new to this module.

This module:
  - defines the Rule dataclass + CaptionOutput
  - holds the trigger functions (deciding IF a rule fires)
  - holds the render functions (deciding WHICH JSON variant to use
    and calling `caption_templates.render_template`)
  - exposes the priority-sorted `RULES` list consumed by
    `caption_renderer.render_caption`

No prose, no f-strings, no severity words live here — those are in
`backend/data/captions/*.json`. See [[README.md]] for the schema and
how to author new content.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Tuple

from services.caption_config import (
    MAX_CAPTION_WORDS,
    MIN_ALIGNED_REAR_VALUE_CP,
    MIN_MATERIAL_CAPTION_GAIN_CP,
    MIN_THREAT_SEE_CP,
)
from services.caption_templates import render_template, render_rule, should_fire


# ────────────────────────────────────────────────────────────────────
# Rule + CaptionOutput types
# ────────────────────────────────────────────────────────────────────

# Type for arrows: (from_square, to_square, color)
Arrow = Tuple[str, str, str]


@dataclass
class CaptionOutput:
    """What every rule's render function returns. Renderer aggregates."""
    caption: str
    highlight_squares: List[str] = field(default_factory=list)
    arrows: List[Arrow] = field(default_factory=list)
    rule_name: str = ""


@dataclass
class Rule:
    """One rule. Pure data — trigger and render are pure functions of
    the facts dict. No external state, no chess library imports."""
    name: str                                  # unique stable identifier
    category: str                              # matches primary_reason.category
    priority: int                              # lower fires first within category
    trigger: Callable[[Dict[str, Any]], bool]  # facts → should this rule fire?
    render: Callable[[Dict[str, Any]], CaptionOutput]


# ────────────────────────────────────────────────────────────────────
# Small helpers (NO chess logic, only fact-dict reads)
# ────────────────────────────────────────────────────────────────────

def _played(f: Dict[str, Any]) -> str:
    return f.get("played_san", "")


def _best(f: Dict[str, Any]) -> str:
    return f.get("best_move_san", "") or ""


def _empty_caption(rule_name: str) -> CaptionOutput:
    """Used by R-FALLBACK: returns silence."""
    return CaptionOutput(caption="", rule_name=rule_name)


# ────────────────────────────────────────────────────────────────────
# Rules — flat list, priority-sorted by category
# ────────────────────────────────────────────────────────────────────

# R01 — Mate. Highest priority. Two sub-templates: delivered vs allowed.
def _r01_trigger(f):
    return bool(f.get("mate_threat_evidence"))


def _r01_render(f):
    # Extract chess facts. Variant selection logic lives in R01_mate.json
    # under `select_variant` — Python doesn't decide which branch fires.
    ev = f["mate_threat_evidence"]
    side_delivering = ev.get("side_delivering_mate")
    moving_color = f.get("moving_piece_color")
    cpl = f.get("cp_loss") or 0
    eval_before_cp = f.get("eval_before_cp")
    facts = {
        "played_san": _played(f),
        "ply": ev.get("ply_to_mate"),
        "delivered_on_this_move": ev.get("delivered_on_this_move", False),
        "mover_delivers": bool(side_delivering and side_delivering == moving_color),
        "mover_is_user": f.get("mover_is_user"),
        "mate_already_on_board": (
            isinstance(eval_before_cp, (int, float)) and eval_before_cp <= -2000
        ),
        "pawn_swing": max(1, min(9, round(cpl / 100))) if cpl > 0 else 0,
    }
    cap = render_rule("R01_mate", facts) or ""
    return CaptionOutput(
        caption=cap,
        highlight_squares=[f.get("target_square", "")] if f.get("target_square") else [],
        arrows=[],
        rule_name="R01_mate",
    )


# R02 — Multi-target attack (rendered as "fork" or "double attack")
def _r02_trigger(f):
    return bool(f.get("multi_target_attack_evidence"))


def _r02_render(f):
    shape = f["multi_target_attack_evidence"][0]
    targets = shape["attacked_targets"]
    t0 = targets[0]
    t1 = targets[1] if len(targets) > 1 else None
    facts = {
        "played_san": _played(f),
        "t0_piece_type": t0["piece_type"],
        "t0_square": t0["square"],
        "t1_piece_type": t1["piece_type"] if t1 else None,
        "t1_square": t1["square"] if t1 else None,
        "both_pawns": bool(t1 and t0["piece_type"] == "pawn" and t1["piece_type"] == "pawn"),
    }
    if t1:
        highlights = [shape["attacker_square"], t0["square"], t1["square"]]
        arrows = [
            (shape["attacker_square"], t0["square"], "red"),
            (shape["attacker_square"], t1["square"], "red"),
        ]
    else:
        highlights = [shape["attacker_square"], t0["square"]]
        arrows = [(shape["attacker_square"], t0["square"], "red")]
    cap = render_rule("R02_multi_target_attack", facts) or ""
    return CaptionOutput(cap, highlights, arrows, "R02_multi_target_attack")


# R03 — Aligned pieces (rendered as pin / skewer / x-ray based on data)
def _r03_shape_is_worth_captioning(s):
    """Pawn-front shapes are trivial unless rear is king — pin the pawn
    on d2 against the queen on d1 isn't actionable for a 1200 (R03 was
    firing 23k times in corpus audit, ~30%+ of which were these). Pawn
    pinned against king IS absolute and stays in.

    2026-05-17: rear-is-king exemption added to the value-floor check
    too. PIECE_VALUE_CP[KING]=0 (SEE-capped), so rear-is-king shapes
    fail `rear_value < MIN_ALIGNED_REAR_VALUE_CP` unconditionally. The
    "Pins X to the king" branch in _r03_render was unreachable —
    surfaced during Fix #1 (king-front skewer) verification when a
    Ruy Lopez Bb5 regression test produced R11_development instead
    of the expected pin caption.
    """
    if not s.get("rear_is_king", False):
        if s.get("rear_piece_value_cp", 0) < MIN_ALIGNED_REAR_VALUE_CP:
            return False
    if s.get("front_piece_type") == "pawn" and not s.get("rear_is_king", False):
        return False
    return True


def _r03_trigger(f):
    shapes = f.get("aligned_pieces_evidence") or []
    return any(_r03_shape_is_worth_captioning(s) for s in shapes)


def _r03_render(f):
    shapes = [s for s in f["aligned_pieces_evidence"] if _r03_shape_is_worth_captioning(s)]
    shape = max(shapes, key=lambda s: s["rear_piece_value_cp"])
    facts = {
        "played_san": _played(f),
        "front_piece_type": shape["front_piece_type"],
        "rear_piece_type": shape["rear_piece_type"],
        "front_square": shape["front_piece_square"],
        "rear_square": shape["rear_piece_square"],
        "rear_is_king": shape.get("rear_is_king", False),
        "front_is_king": shape.get("front_is_king", False),
        "front_lower": shape["front_value_vs_rear"] == "lower",
    }
    cap = render_rule("R03_aligned_pieces", facts) or ""
    return CaptionOutput(
        cap,
        highlight_squares=[shape["attacker_square"], shape["front_piece_square"], shape["rear_piece_square"]],
        arrows=[(shape["attacker_square"], shape["rear_piece_square"], "red")],
        rule_name="R03_aligned_pieces",
    )


# R04 — Discovered attack
def _r04_trigger(f):
    return bool(f.get("discovered_attack_evidence"))


def _r04_render(f):
    ev = f["discovered_attack_evidence"][0]
    attacker_sq = ev["discovered_attacker_square"]
    target_sq = ev["target_square"]
    cap = render_rule("R04_discovered_attack", {
        "played_san": _played(f),
        "discovered_attacker_piece_type": ev["discovered_attacker_piece_type"],
        "target_piece_type": ev["target_piece_type"],
        "target_square": target_sq,
    }) or ""
    return CaptionOutput(
        cap,
        highlight_squares=[attacker_sq, target_sq],
        arrows=[(attacker_sq, target_sq, "red")],
        rule_name="R04_discovered_attack",
    )


# R05 — Check + extra threat. Trigger thresholds (cp_loss < 30) are
# authored in backend/data/captions/R05_check_extra.json → trigger.when.
def _r05_trigger(f):
    return should_fire("R05_check_extra", {
        "is_check": bool(f.get("is_check")),
        "threats_created_present": bool(f.get("threats_created")),
        "cp_loss": f.get("cp_loss") or 0,
    })


def _r05_render(f):
    threat = max(f["threats_created"], key=lambda t: t.get("target_value_cp", 0))
    cap = render_rule("R05_check_extra", {
        "played_san": _played(f),
        "target_piece_type": threat["target_piece_type"],
        "target_square": threat["target_square"],
    }) or ""
    return CaptionOutput(
        cap,
        highlight_squares=[threat["target_square"], threat["attacker_square"]],
        arrows=[(threat["attacker_square"], threat["target_square"], "red")],
        rule_name="R05_check_extra",
    )


# R06 — Plain check. Trigger thresholds in R06_check_plain.json.
def _r06_trigger(f):
    return should_fire("R06_check_plain", {
        "is_check": bool(f.get("is_check")),
        "cp_loss": f.get("cp_loss") or 0,
    })


def _r06_render(f):
    cap = render_rule("R06_check_plain", {
        "played_san": _played(f),
    }) or ""
    return CaptionOutput(
        cap,
        highlight_squares=[f.get("target_square", "")] if f.get("target_square") else [],
        arrows=[],
        rule_name="R06_check_plain",
    )


# R07 — Forced recapture
def _r07_trigger(f):
    return bool(f.get("is_forced_recapture"))


def _r07_render(f):
    cap = render_rule("R07_forced_recapture", {
        "played_san": _played(f),
        "captured_piece_type": f.get("captured_piece_type", "piece"),
        "mover_is_user": f.get("mover_is_user"),
    }) or ""
    return CaptionOutput(
        cap,
        highlight_squares=[f.get("target_square", "")] if f.get("target_square") else [],
        arrows=[],
        rule_name="R07_forced_recapture",
    )


# R08 — Material. Trigger thresholds (cp_loss < 80, material_delta >= 100)
# in R08_material.json. Python pre-computes the boolean for the JSON.
def _r08_trigger(f):
    delta = f.get("material_delta_played_cp") or 0
    return should_fire("R08_material", {
        "material_gain_meets_threshold": delta >= MIN_MATERIAL_CAPTION_GAIN_CP,
        "cp_loss": f.get("cp_loss") or 0,
    })


def _r08_render(f):
    cap = render_rule("R08_material", {
        "played_san": _played(f),
        "captured_piece_type": f.get("captured_piece_type", "piece"),
        "mover_is_user": f.get("mover_is_user"),
        "uncontested": bool(f.get("free_capture_uncontested")),
        "is_capture": bool(f.get("is_capture")),
    }) or ""
    return CaptionOutput(
        cap,
        highlight_squares=[f.get("target_square", "")] if f.get("target_square") else [],
        arrows=[],
        rule_name="R08_material",
    )


# R09 — King safety (castling)
def _r09_trigger(f):
    return bool(f.get("is_castling"))


def _r09_render(f):
    cap = render_rule("R09_king_safety", {
        "played_san": _played(f),
        "mover_is_user": f.get("mover_is_user"),
    }) or ""
    return CaptionOutput(
        cap,
        highlight_squares=[f.get("target_square", "")] if f.get("target_square") else [],
        arrows=[],
        rule_name="R09_king_safety",
    )


# R10 — Threat creation. Threshold (max_threat_see_cp >= 200) authored
# in R10_threat.json. Python computes the max from the threats list.
def _r10_trigger(f):
    threats = f.get("threats_created") or []
    max_see = max((t.get("see_cp", 0) for t in threats), default=0)
    return should_fire("R10_threat", {"max_threat_see_cp": max_see})


def _r10_render(f):
    threat = max(f["threats_created"], key=lambda t: t.get("see_cp", 0))
    cap = render_rule("R10_threat", {
        "played_san": _played(f),
        "target_piece_type": threat.get("target_piece_type"),
        "target_square": threat.get("target_square"),
    }) or ""
    return CaptionOutput(
        cap,
        highlight_squares=[threat["target_square"], threat["attacker_square"]],
        arrows=[(threat["attacker_square"], threat["target_square"], "red")],
        rule_name="R10_threat",
    )


# R11 — Development. Trigger in R11_development.json (renders silence).
def _r11_trigger(f):
    return should_fire("R11_development", {
        "phase": f.get("phase"),
        "moving_piece_type": f.get("moving_piece_type"),
        "cp_loss": f.get("cp_loss") or 0,
    })


def _r11_render(f):
    """SILENT (Mohit 2026-05-20).

    R11 historically emitted 'Develops the X to Y' / 'Opponent develops
    the X to Y' on every routine minor-piece move in the opening. Mohit
    flagged this as vapid coaching — the user already SEES the move on
    the board; restating it teaches nothing. Per [[no-hollow-coverage]]:
    honest silence > narration of the obvious.

    R11's trigger gates already exclude tactical content (cp_loss < 30,
    no captures, no checks, no threats — those fire higher-priority
    rules first). So when R11 would have fired, there is by definition
    NOTHING new to teach. Return empty caption; the renderer falls
    through to no_trigger_fired and the promotion ladder
    (game_decryption_v5_service.py) can still surface opening / trap /
    principle / shape teaching when those detectors hit.
    """
    sq = f.get("target_square", "")
    return CaptionOutput(
        "",
        highlight_squares=[sq] if sq else [],
        arrows=[],
        rule_name="R11_development_silent",
    )


# R12 — Blunder fallback. cp_loss threshold (>= 100) in R12_blunder.json.
def _r12_trigger(f):
    return should_fire("R12_blunder", {"cp_loss": f.get("cp_loss") or 0})


def _r12_pick_hanging(undef_list):
    """Pick the highest-value hanging piece from a list of undefended
    pieces. Returns {piece_type, square} or None. Chess data extraction
    only — no prose."""
    hanging = [p for p in (undef_list or []) if p.get("now_attacked") and p.get("is_now_hanging")]
    if not hanging:
        return None
    worst = max(hanging, key=lambda p: p.get("piece_value_cp", 0) or 0)
    sq = worst.get("square") or ""
    if not sq:
        return None
    return {"piece_type": worst.get("piece_type", "piece"), "square": sq}


def _r12_render(f):
    """All R12 logic — severity tier, why-clause priority, suppression,
    variant selection — lives in R12_blunder.json. Python only extracts
    chess data + computes booleans for the JSON predicates."""
    played = _played(f)
    best = _best(f)
    opp_reply = f.get("opp_reply_san")
    user_best_reply = f.get("user_best_reply_san") or f.get("best_move_after_opp_blunder_san")

    # Chess data extraction for the why-clauses. Pick the worst hanging
    # piece on each side (data extraction, no prose).
    user_hanging = _r12_pick_hanging(f.get("pieces_now_undefended"))
    opp_hanging = _r12_pick_hanging(
        f.get("opp_pieces_now_undefended") or f.get("pieces_now_undefended_by_opp")
    )

    # Missed-tactic detection — walk pv_after_best with python-chess
    # to identify the tactical climax (mate / piece win / material).
    # Highest-priority why-clause when present. Detector module lives
    # in services/best_move_tactic_detector.py.
    missed_tactic_kind = None
    missed_tactic_target_piece = None
    missed_tactic_target_square = None
    missed_tactic_ply = None
    if best and best != played and f.get("mover_is_user") is not False:
        try:
            from services.best_move_tactic_detector import detect_missed_tactic
            # mover_is_user is True for R12 user blunders, so the player
            # who just moved is the user — moving_piece_color is the
            # user's color.
            user_color_inferred = "white" if f.get("moving_piece_color") == "white" else "black"
            tactic = detect_missed_tactic(
                fen_before=f.get("fen_before"),
                best_move_san=best,
                pv_after_best=f.get("pv_after_best") or [],
                user_color=user_color_inferred,
                eval_before_cp=f.get("eval_before_cp"),
            )
            if tactic:
                missed_tactic_kind = tactic.get("kind")
                missed_tactic_target_piece = tactic.get("piece_type")
                missed_tactic_target_square = tactic.get("square")
                missed_tactic_ply = tactic.get("ply")
        except Exception:  # pragma: no cover — defensive
            pass

    # v68 (2026-05-22): start from the full caption_facts dict and
    # add R12-computed extras on top. Previously this was an EXPLICIT
    # subset which made every new detector require a parallel edit
    # here to pass facts through to R12_blunder.json. The detector
    # work from v56-v66 (clearance_then_check, queen_fork,
    # attack_with_tempo, endgame_loose_pawn, un_developing,
    # defensive_pawn, knight_outpost, stop_opp_pawn, active_defense,
    # same_piece_better_square, discovered_vacating_check,
    # knight_on_rim, pawn_kicks_piece, why_clause_em_dash) ALL fired
    # but their facts were being dropped at R12 render time. Caught
    # by Mohit 2026-05-22 on game fc97ee1d m7 Bb5 — clearance_then_check
    # detector fired with follow_up_san=Qh5+ but the R12 caption fell
    # through to engine-speak why_user_missed_material because the
    # facts dict R12 built did not include the new keys.
    facts = dict(f)
    facts.update({
        "played_san": played,
        "best_move_san": best,
        "cp_loss": f.get("cp_loss") or 0,
        "mover_is_user": f.get("mover_is_user"),
        "best_move_san_differs": bool(best and best != played),

        # Missed-tactic from pv_after_best (highest priority why-clause)
        "missed_tactic_kind": missed_tactic_kind,
        "missed_tactic_target_piece": missed_tactic_target_piece,
        "missed_tactic_target_square": missed_tactic_target_square,
        "missed_tactic_ply": missed_tactic_ply,

        # Shape-pattern from pre-move board (e.g. king_pawn_lifted on f7)
        "shape_pattern_id": f.get("shape_pattern_id"),
        "shape_pattern_target_square": f.get("shape_pattern_target_square"),

        # Clearance-for-attack from hypothetical best_move (Légal /
        # Fried Liver family — set when best_move would have opened
        # a line for the queen/rook/bishop to attack king zone).
        "missed_clearance_attack_square": f.get("missed_clearance_attack_square"),
        "missed_clearance_attacker_piece": f.get("missed_clearance_attacker_piece"),

        # Eval-trajectory facts (Mohit 2026-05-21) — engine-derived
        # leverage. When the eval has been losing for 3+ user moves
        # before this one, frame the move as damage control, not the
        # source of the loss.
        "position_was_already_losing": f.get("position_was_already_losing"),
        "losing_since_move": f.get("losing_since_move"),

        # Board-state clause (Mohit 2026-05-21) — universal
        # coach-voice fallback. Pre-rendered string composed by
        # board_state_describer.py + V5 service from up to 3
        # bs_* template renderings. Fires as why-clause when
        # nothing more specific did.
        "board_state_clause": f.get("board_state_clause"),

        # Blocked-own-pawn principle (Mohit 2026-05-21) — named
        # opening teaching for moves where user played a non-pawn
        # piece to a square the engine's best (a pawn) wanted to
        # occupy. Common in d4+e5 structures where Nc3 blocks the
        # c-pawn's central support.
        "blocked_pawn_file": f.get("blocked_pawn_file"),
        "blocked_pawn_square": f.get("blocked_pawn_square"),
        "blocked_pawn_would_support": f.get("blocked_pawn_would_support"),

        # Curriculum deviation (Mohit 2026-05-21) — user deviated
        # from a curated opening tree's expected move. The clause
        # is the tree node's hand-authored wrong_feedback.
        "curriculum_deviation_clause": f.get("curriculum_deviation_clause"),
        "curriculum_expected_move": f.get("curriculum_expected_move"),
        "curriculum_opening_name": f.get("curriculum_opening_name"),

        # Position-eval flags (Mohit 2026-05-21) — reframe low-cp_loss
        # "is a mistake" captions into encouragement (winning) or
        # context (losing). When user is decisively winning or losing,
        # framing a 30-150cp positional preference as "a mistake" is
        # bad coaching. Already computed by caption_facts; just
        # propagated here so R12 / basic_mistake variants can pick.
        "user_is_winning": f.get("user_is_winning"),
        "user_is_losing": f.get("user_is_losing"),

        # User-side why-clause inputs
        "opp_reply_san": opp_reply,
        "opp_reply_attacks_played_piece": bool(f.get("opp_reply_attacks_played_piece")),
        "is_exchange_losing": bool(f.get("is_exchange_losing")),
        "target_square": f.get("target_square"),
        "moving_piece_type": f.get("moving_piece_type") or "piece",
        "captured_piece_type": f.get("opp_reply_captures_piece_type"),
        "opp_reply_san_is_check": bool(opp_reply and (opp_reply.endswith("+") or opp_reply.endswith("#"))),
        "pieces_now_undefended_present": user_hanging is not None,
        "piece_type": (user_hanging or {}).get("piece_type") if f.get("mover_is_user") is not False else (opp_hanging or {}).get("piece_type"),
        "square": (user_hanging or {}).get("square") if f.get("mover_is_user") is not False else (opp_hanging or {}).get("square"),

        # Opp-side why-clause inputs
        "user_best_reply_san": user_best_reply,
        "user_best_reply_san_is_forcing": bool(
            user_best_reply and (user_best_reply.endswith("+") or user_best_reply.endswith("#"))
        ),
        "opp_pieces_now_undefended_present": opp_hanging is not None,
        "opp_played_landed_unsafe": bool(f.get("opp_played_landed_unsafe")),
    })
    # For opp-side why_clauses, captured_piece_type comes from a different
    # source (the user's best reply, not opp's reply). Override when opp side.
    if f.get("mover_is_user") is False:
        facts["captured_piece_type"] = f.get("user_best_reply_captures_piece_type")

    cap = render_rule("R12_blunder", facts)
    if cap is None:
        return None
    return CaptionOutput(
        caption=cap,
        highlight_squares=[f.get("target_square", "")] if f.get("target_square") else [],
        arrows=[],
        rule_name="R12_blunder",
    )


# R13 — Opening central pawn. All conditions (phase, move number,
# target square set) authored in R13_opening_central_pawn.json.
def _r13_trigger(f):
    return should_fire("R13_opening_central_pawn", {
        "phase": f.get("phase"),
        "is_pawn_move": bool(f.get("is_pawn_move")),
        "full_move_number": f.get("full_move_number") or 0,
        "target_square": f.get("target_square"),
    })


def _r13_render(f):
    sq = f.get("target_square", "")
    cap = render_rule("R13_opening_central_pawn", {
        "played_san": _played(f),
        "mover_is_user": f.get("mover_is_user"),
    }) or ""
    return CaptionOutput(
        cap,
        highlight_squares=[sq] if sq else [],
        arrows=[],
        rule_name="R13_opening_central_pawn",
    )


# R14 — Forced best in losing position. Thresholds in R14_forced_best.json.
def _r14_trigger(f):
    return should_fire("R14_forced_best", {
        "played_is_best": bool(f.get("played_is_best")),
        "cp_loss": f.get("cp_loss") or 0,
    })


def _r14_render(f):
    cap = render_rule("R14_forced_best", {
        "played_san": _played(f),
        "mover_is_user": f.get("mover_is_user"),
    }) or ""
    return CaptionOutput(
        caption=cap,
        highlight_squares=[f.get("target_square", "")] if f.get("target_square") else [],
        arrows=[],
        rule_name="R14_forced_best",
    )


# R15 — Good move acknowledgment. Conditions in R15_good_move.json.
def _r15_trigger(f):
    return should_fire("R15_good_move", {
        "played_is_best": bool(f.get("played_is_best")),
        "cp_loss": f.get("cp_loss") or 0,
        "mover_is_user": f.get("mover_is_user") is True,
    })


def _r15_render(f):
    cap = render_rule("R15_good_move", {
        "played_san": _played(f),
        "phase": f.get("phase") or "middlegame",
    }) or ""
    return CaptionOutput(
        caption=cap,
        highlight_squares=[f.get("target_square", "")] if f.get("target_square") else [],
        arrows=[],
        rule_name="R15_good_move",
    )


# R_FALLBACK — no rule matched. Silence.
def _r_fallback_trigger(f):
    return True  # always fires last


def _r_fallback_render(f):
    return _empty_caption("R_FALLBACK")


# ────────────────────────────────────────────────────────────────────
# RULES — flat list. Order = priority. The renderer picks the FIRST
# match whose category lines up with primary_reason.category AND
# whose trigger returns True.
# ────────────────────────────────────────────────────────────────────

RULES: List[Rule] = [
    Rule("R01_mate",                "mate",             1, _r01_trigger, _r01_render),
    Rule("R02_multi_target_attack", "tactic_played",    2, _r02_trigger, _r02_render),
    Rule("R03_aligned_pieces",      "tactic_played",    3, _r03_trigger, _r03_render),
    Rule("R04_discovered_attack",   "tactic_played",    4, _r04_trigger, _r04_render),
    Rule("R05_check_extra",         "check_extra",      5, _r05_trigger, _r05_render),
    Rule("R06_check_plain",         "check_plain",      6, _r06_trigger, _r06_render),
    Rule("R07_forced_recapture",    "forced_recapture", 7, _r07_trigger, _r07_render),
    Rule("R08_material",            "material",         8, _r08_trigger, _r08_render),
    Rule("R09_king_safety",         "king_safety",      9, _r09_trigger, _r09_render),
    Rule("R10_threat",              "threat",          10, _r10_trigger, _r10_render),
    Rule("R13_opening_central_pawn","opening_central_pawn", 9, _r13_trigger, _r13_render),
    Rule("R11_development",         "development",     11, _r11_trigger, _r11_render),
    Rule("R14_forced_best",         "forced_best",     11, _r14_trigger, _r14_render),
    Rule("R12_blunder",             "blunder",         12, _r12_trigger, _r12_render),
    Rule("R15_good_move",           "good_move",       12, _r15_trigger, _r15_render),
]
