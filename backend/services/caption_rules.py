"""
Caption Rules — flat declarative rule library.

ARCHITECTURE LAWS (enforced by review + grep test):

  LAW R1 — No `import chess`. No board parsing. No `parse_san`. No SEE
           recomputation. Rules read the facts dict produced by
           `caption_facts.extract_facts()` and nothing else.

  LAW R2 — No "smart" inference. If a rule needs a derived value, the
           extractor produces it. Templates only do format-string
           substitution from existing facts.

  LAW R3 — Single template per rule. No variant phrasings in v1.
           Compression + correctness only.

  LAW R4 — Rules are pure data. A `Rule` is (category, name, priority,
           trigger function, render function). The trigger function
           takes a facts dict and returns bool. The render function
           takes a facts dict and returns a CaptionOutput dict.

  LAW R5 — Rules ordered by category match, then priority. The first
           matching rule wins. No nested branching, no method dispatch.

Per design doc §5 + memory rule
`feedback_renderer_never_computes_chess_meaning.md`.
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
    ev = f["mate_threat_evidence"]
    side_delivering = ev.get("side_delivering_mate")
    moving_color = f.get("moving_piece_color")
    ply = ev.get("ply_to_mate")
    delivered_on_this_move = ev.get("delivered_on_this_move", False)
    if delivered_on_this_move:
        # The played move IS the mating move. Same template regardless of side.
        cap = f"{_played(f)}. Checkmate."
    elif side_delivering and side_delivering == moving_color:
        # We're delivering mate within the next few ply.
        if ply == 1:
            cap = f"{_played(f)}. Forces mate next move."
        elif ply:
            cap = f"{_played(f)}. Forces mate in {ply}."
        else:
            cap = f"{_played(f)}. Wins by force."
    else:
        # We walked into mate or allowed it
        if ply == 1:
            cap = f"{_played(f)} allows mate next move."
        elif ply:
            cap = f"{_played(f)} allows mate in {ply}."
        else:
            cap = f"{_played(f)}. Position is lost."
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
    attacker_piece = shape["attacker_piece_type"]
    if t1:
        cap = (
            f"{_played(f)} forks the {t0['piece_type']} on {t0['square']} "
            f"and the {t1['piece_type']} on {t1['square']}."
        )
        highlights = [shape["attacker_square"], t0["square"], t1["square"]]
        arrows = [
            (shape["attacker_square"], t0["square"], "red"),
            (shape["attacker_square"], t1["square"], "red"),
        ]
    else:
        cap = f"{_played(f)} attacks the {t0['piece_type']} on {t0['square']}."
        highlights = [shape["attacker_square"], t0["square"]]
        arrows = [(shape["attacker_square"], t0["square"], "red")]
    return CaptionOutput(cap, highlights, arrows, "R02_multi_target_attack")


# R03 — Aligned pieces (rendered as pin / skewer / x-ray based on data)
def _r03_trigger(f):
    shapes = f.get("aligned_pieces_evidence") or []
    return any(s.get("rear_piece_value_cp", 0) >= MIN_ALIGNED_REAR_VALUE_CP for s in shapes)


def _r03_render(f):
    # Pick the highest-rear-value shape
    shapes = [
        s for s in f["aligned_pieces_evidence"]
        if s.get("rear_piece_value_cp", 0) >= MIN_ALIGNED_REAR_VALUE_CP
    ]
    shape = max(shapes, key=lambda s: s["rear_piece_value_cp"])
    front_lower = shape["front_value_vs_rear"] == "lower"
    rear_is_king = shape.get("rear_is_king", False)
    front_pt = shape["front_piece_type"]
    rear_pt = shape["rear_piece_type"]
    front_sq = shape["front_piece_square"]
    rear_sq = shape["rear_piece_square"]
    attacker_sq = shape["attacker_square"]

    if rear_is_king:
        cap = f"{_played(f)}. Pins the {front_pt} on {front_sq} to the king."
    elif front_lower:
        cap = f"{_played(f)}. Pins the {front_pt} on {front_sq} against the {rear_pt} on {rear_sq}."
    else:
        # front >= rear in value — skewer-like
        cap = f"{_played(f)}. Lines up the {front_pt} on {front_sq} in front of the {rear_pt}."
    return CaptionOutput(
        cap,
        highlight_squares=[attacker_sq, front_sq, rear_sq],
        arrows=[(attacker_sq, rear_sq, "red")],
        rule_name="R03_aligned_pieces",
    )


# R04 — Discovered attack
def _r04_trigger(f):
    return bool(f.get("discovered_attack_evidence"))


def _r04_render(f):
    ev = f["discovered_attack_evidence"][0]
    attacker_sq = ev["discovered_attacker_square"]
    target_sq = ev["target_square"]
    target_pt = ev["target_piece_type"]
    cap = f"{_played(f)} uncovers the {ev['discovered_attacker_piece_type']} hitting the {target_pt} on {target_sq}."
    return CaptionOutput(
        cap,
        highlight_squares=[attacker_sq, target_sq],
        arrows=[(attacker_sq, target_sq, "red")],
        rule_name="R04_discovered_attack",
    )


# R05 — Check + extra threat
def _r05_trigger(f):
    return f.get("is_check") and bool(f.get("threats_created"))


def _r05_render(f):
    threat = max(f["threats_created"], key=lambda t: t.get("target_value_cp", 0))
    cap = (
        f"{_played(f)} — check, and attacks the {threat['target_piece_type']} "
        f"on {threat['target_square']} too."
    )
    return CaptionOutput(
        cap,
        highlight_squares=[threat["target_square"], threat["attacker_square"]],
        arrows=[(threat["attacker_square"], threat["target_square"], "red")],
        rule_name="R05_check_extra",
    )


# R06 — Plain check
def _r06_trigger(f):
    return bool(f.get("is_check"))


def _r06_render(f):
    cap = f"{_played(f)} — check. King must move or block."
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
    captured = f.get("captured_piece_type", "piece")
    cap = f"{_played(f)} — only move. Takes back the {captured}."
    return CaptionOutput(
        cap,
        highlight_squares=[f.get("target_square", "")] if f.get("target_square") else [],
        arrows=[],
        rule_name="R07_forced_recapture",
    )


# R08 — Material (eval-gated; primary_reason already checked gating)
def _r08_trigger(f):
    delta = f.get("material_delta_played_cp") or 0
    return delta >= MIN_MATERIAL_CAPTION_GAIN_CP


def _r08_render(f):
    delta = f["material_delta_played_cp"]
    if f.get("free_capture"):
        captured = f.get("captured_piece_type", "piece")
        cap = f"{_played(f)}. Free {captured} — nothing recaptures."
    elif f.get("is_capture"):
        captured = f.get("captured_piece_type", "piece")
        cap = f"{_played(f)} wins material. Net {delta} cp in the exchange."
    else:
        cap = f"{_played(f)}. Wins {delta} cp in the resulting line."
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
    mover_is_user = f.get("mover_is_user")
    if mover_is_user is False:
        # Opp castled — their good news, not yours. Describe rather
        # than celebrate.
        cap = f"{_played(f)}. Opponent tucks their king away."
    else:
        # Default + user-known: keep the original celebratory voice.
        cap = f"{_played(f)}. King is safe; rook joins the game."
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
    cap = (
        f"{_played(f)} threatens {threat['attacker_piece_type']}x{threat['target_square']} "
        f"winning the {threat['target_piece_type']}."
    )
    return CaptionOutput(
        cap,
        highlight_squares=[threat["target_square"], threat["attacker_square"]],
        arrows=[(threat["attacker_square"], threat["target_square"], "red")],
        rule_name="R10_threat",
    )


# R11 — Development (opening, minor piece, no tactic)
def _r11_trigger(f):
    return (
        f.get("phase") == "opening"
        and f.get("moving_piece_type") in ("knight", "bishop")
    )


def _r11_render(f):
    piece = f.get("moving_piece_type", "piece")
    sq = f.get("target_square", "")
    cap = f"Develops the {piece} to {sq}."
    return CaptionOutput(
        cap,
        highlight_squares=[sq] if sq else [],
        arrows=[],
        rule_name="R11_development",
    )


# R12 — Blunder fallback. Fills the silence for moves whose engine
# evaluation labels them a mistake/blunder and that didn't fire any of
# the celebratory rules above (those are gated on cp_loss in
# extract_primary_reason). Phrasing is neutral: it describes loss in
# pawns and points at the engine's best alternative.
def _r12_trigger(f):
    return (f.get("cp_loss") or 0) >= 100


def _r12_render(f):
    cpl = f.get("cp_loss") or 0
    pawns = max(1, min(9, round(cpl / 100)))
    pawns_word = "pawn" if pawns == 1 else "pawns"
    played = _played(f)
    best = _best(f)
    mover_is_user = f.get("mover_is_user")
    if mover_is_user is False:
        # Opp blundered — frame as user-actionable news, not coaching the
        # opponent on what they should have played.
        cap = f"Opponent's {played} drops about {pawns} {pawns_word}."
    elif best and best != played:
        cap = f"{played} loses about {pawns} {pawns_word}. {best} was better."
    else:
        cap = f"{played} loses about {pawns} {pawns_word}."
    return CaptionOutput(
        caption=cap,
        highlight_squares=[f.get("target_square", "")] if f.get("target_square") else [],
        arrows=[],
        rule_name="R12_blunder",
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
    Rule("R11_development",         "development",     11, _r11_trigger, _r11_render),
    Rule("R12_blunder",             "blunder",         12, _r12_trigger, _r12_render),
]
