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
from services.caption_templates import render_template, render_rule


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


# R05 — Check + extra threat
#
# Severity gate added 2026-05-13 (user-flagged bugs fb_77033d853689 +
# fb_d7e9c60cdeff): R05 fires appreciative voice ("Rd6+ — check, and
# attacks the pawn on e6 too") even when the played move is a real
# mistake or blunder (Rd6+ cp_loss 207, c5+ cp_loss 135). Skipping
# R05 when cp_loss >= 30 lets R12_blunder take over and frame the
# move as the mistake it actually is.
def _r05_trigger(f):
    if (f.get("cp_loss") or 0) >= 30:
        return False
    return f.get("is_check") and bool(f.get("threats_created"))


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


# R06 — Plain check
#
# Same severity gate as R05 (2026-05-13): praise voice on a check
# that turns out to be a mistake reads as "appreciative when engine
# says it's bad." Drop to silence; R12_blunder picks up.
def _r06_trigger(f):
    if (f.get("cp_loss") or 0) >= 30:
        return False
    return bool(f.get("is_check"))


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


# R08 — Material (eval-gated; primary_reason already checked gating)
def _r08_trigger(f):
    # Step aside when the engine flags this as a mistake — R12 takes
    # over and frames it correctly. Parth 2026-05-18 fb_d111aa020ab8:
    # Qxc7 with cp_loss=129 fired "wins material" while it was actually
    # a mistake. Mirror the same gate R05 already uses (line 280).
    if (f.get("cp_loss") or 0) >= 80:
        return False
    delta = f.get("material_delta_played_cp") or 0
    return delta >= MIN_MATERIAL_CAPTION_GAIN_CP


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


# R10 — Threat creation (no tactic above)
def _r10_trigger(f):
    threats = f.get("threats_created") or []
    return any(t.get("see_cp", 0) >= MIN_THREAT_SEE_CP for t in threats)


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


# R11 — Development (opening, minor piece, no tactic)
#
# Severity gate added 2026-05-13 (user-flagged fb_2b055c2dd847): R11
# fired "Develops the bishop to h4" on Bh4 with cp_loss 78 — engine
# rates it as a positional mistake but R11 framed it as good
# development. Same R05/R06 pattern. Skip when cp_loss >= 30.
def _r11_trigger(f):
    if (f.get("cp_loss") or 0) >= 30:
        return False
    return (
        f.get("phase") == "opening"
        and f.get("moving_piece_type") in ("knight", "bishop")
    )


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


# R12 — Blunder fallback. Fills the silence for moves whose engine
# evaluation labels them a mistake/blunder and that didn't fire any of
# the celebratory rules above (those are gated on cp_loss in
# extract_primary_reason). Phrasing is neutral: it describes loss in
# pawns and points at the engine's best alternative.
def _r12_trigger(f):
    return (f.get("cp_loss") or 0) >= 100


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

    facts = {
        "played_san": played,
        "best_move_san": best,
        "cp_loss": f.get("cp_loss") or 0,
        "mover_is_user": f.get("mover_is_user"),
        "best_move_san_differs": bool(best and best != played),

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
    }
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


# R13 — Opening central pawn move. Covers the first-pair e4/d4/d5/e5
# pushes that were silent in v1+v2 (no rule). Bend #7.
def _r13_trigger(f):
    return (
        f.get("phase") == "opening"
        and f.get("is_pawn_move")
        and (f.get("full_move_number") or 0) <= 2
        and f.get("target_square") in ("d4", "d5", "e4", "e5")
    )


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


# R14 — Forced best move in a losing position. Fires when played_is_best
# is True AND cp_loss is high (≥100). The player picked the engine's
# top choice — it's not a blunder, it's the best damage control in a
# bad position. Calling that "good" would be confusing ("if it's good
# why is cp_loss 392?"); calling it a blunder would be wrong (player
# played the right move).
def _r14_trigger(f):
    return bool(f.get("played_is_best")) and (f.get("cp_loss") or 0) >= 100


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


# R15 — Good move acknowledgment.
# Fires for user moves that are engine-best with cp_loss == 0 when no
# higher-priority celebratory category claimed the move. Sub-1400
# players need positive reinforcement, not just blame — see Mohit 2026-
# 05-19 review of 800-1400 coaching tone.
def _r15_trigger(f):
    # Belt + suspenders — the category gate in caption_facts.py already
    # ensures this, but trigger checks the same conditions defensively.
    return (
        bool(f.get("played_is_best"))
        and (f.get("cp_loss") or 0) == 0
        and f.get("mover_is_user") is True
    )


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
