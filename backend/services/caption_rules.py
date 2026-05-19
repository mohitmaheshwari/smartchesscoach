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
    mover_is_user = f.get("mover_is_user")
    mover_delivers = bool(side_delivering and side_delivering == moving_color)

    if delivered_on_this_move:
        # Same template regardless of side — game-over checkmate move.
        cap = f"{_played(f)}. Checkmate."
    elif mover_delivers:
        # The mover is setting up mate-in-N. From corpus audit: this
        # branch fires often on OPP setup moves toward user-side mate,
        # so we branch on mover_is_user to keep the voice user-relative.
        if mover_is_user is False:
            if ply == 1:
                cap = f"{_played(f)}. Opp threatens mate next move."
            elif ply:
                cap = f"{_played(f)}. Opp threatens mate in {ply}."
            else:
                cap = f"{_played(f)}. Opp is winning by force."
        else:
            if ply == 1:
                cap = f"{_played(f)}. Forces mate next move."
            elif ply:
                cap = f"{_played(f)}. Forces mate in {ply}."
            else:
                cap = f"{_played(f)}. Wins by force."
    else:
        # Mover walked into mate against themselves. The "Position is
        # lost" caption was rendering on OPP moves where opp had blundered
        # into a losing line — from user POV that's actually winning news.
        if mover_is_user is False:
            if ply == 1:
                cap = f"{_played(f)}. Mate is on for you next move."
            elif ply:
                cap = f"{_played(f)}. Mate is on for you in {ply}."
            else:
                cap = f"{_played(f)}. Opp's position is lost."
        else:
            # Parth 2026-05-18 fb_d576bbf21a65: "Ne4 allows mate in 2"
            # framed wrong because mate was ALREADY on the board pre-move
            # (eval_before in mate-territory). The move didn't CAUSE the
            # mate, it failed to defend against it. Split "allows" vs
            # "misses defense against" based on pre-move eval state.
            eval_before_cp = f.get("eval_before_cp")
            mate_already_on_board = (
                isinstance(eval_before_cp, (int, float))
                and eval_before_cp <= -2000
            )
            if mate_already_on_board:
                if ply == 1:
                    cap = f"{_played(f)} misses the defense against mate next move."
                elif ply:
                    cap = f"{_played(f)} misses the defense against mate in {ply}."
                else:
                    cap = f"{_played(f)}. Position was already lost."
            else:
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
    if t1:
        # Pawn-only fork (e.g. d7ce40cf #16 Ndb4 a2+d3, #23 Rc7 a7+f7)
        # — "forks" overstates a dual-pawn attack since neither target
        # is a piece. Use the lighter "attacks the pawns on …" template.
        both_pawns = t0["piece_type"] == "pawn" and t1["piece_type"] == "pawn"
        if both_pawns:
            cap = (
                f"{_played(f)} attacks the pawns on {t0['square']} "
                f"and {t1['square']} — likely wins one."
            )
        else:
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
    # Pick the highest-rear-value shape among the worth-captioning ones
    shapes = [s for s in f["aligned_pieces_evidence"] if _r03_shape_is_worth_captioning(s)]
    shape = max(shapes, key=lambda s: s["rear_piece_value_cp"])
    front_lower = shape["front_value_vs_rear"] == "lower"
    rear_is_king = shape.get("rear_is_king", False)
    front_is_king = shape.get("front_is_king", False)
    front_pt = shape["front_piece_type"]
    rear_pt = shape["rear_piece_type"]
    front_sq = shape["front_piece_square"]
    rear_sq = shape["rear_piece_square"]
    attacker_sq = shape["attacker_square"]

    if rear_is_king:
        cap = f"{_played(f)}. Pins the {front_pt} on {front_sq} to the king."
    elif front_is_king:
        # Front is the king under check from this attacker — by definition
        # a SKEWER, not a pin. King is forced to move (it's in check),
        # exposing the rear piece behind. Parth flagged fb_e76ee83db3e8 +
        # fb_05356cf43f98 (2026-05-17): "You cannot pin the king."
        # Value-based front_lower check hit the wrong branch because
        # PIECE_VALUE_CP[KING] = 0 (SEE-capped); king < queen → false pin.
        # Verb softened 2026-05-19 (fb_52bf0a0b813a): "falls" overclaims —
        # the rear piece is EXPOSED on the king's escape squares, but
        # depending on which way the king moves, the rear piece may or
        # may not actually be lost. "is exposed" stays true across all
        # king escape choices.
        cap = f"{_played(f)}. Skewers the king on {front_sq} — when it moves, the {rear_pt} on {rear_sq} is exposed."
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
#
# Same severity gate as R05 (2026-05-13): praise voice on a check
# that turns out to be a mistake reads as "appreciative when engine
# says it's bad." Drop to silence; R12_blunder picks up.
def _r06_trigger(f):
    if (f.get("cp_loss") or 0) >= 30:
        return False
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
    mover_is_user = f.get("mover_is_user")
    if mover_is_user is False:
        cap = f"{_played(f)}. Opponent forced to recapture the {captured}."
    else:
        cap = f"{_played(f)} — only move. Takes back the {captured}."
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
    mover_is_user = f.get("mover_is_user")
    captured = f.get("captured_piece_type", "piece")
    # Use the pedagogical gate (geometric + eval-supported) for the
    # "Free X" celebratory line. Parth 2026-05-17 fb_0467dc2bc44f +
    # fb_5d4a86e264e6 flagged captions that were geometrically true
    # but ignored positional compensation in the eval.
    uncontested = f.get("free_capture_uncontested")
    if mover_is_user is False:
        # Opp grabbed material from us. User-actionable framing.
        if uncontested:
            cap = f"{_played(f)}. Opponent grabs the {captured} — nothing was defending it."
        elif f.get("is_capture"):
            cap = f"{_played(f)}. Opponent takes the {captured}."
        else:
            cap = f"{_played(f)}. Opponent improves."
    else:
        # No "Net N cp in the exchange" wording — Parth 2026-05-18
        # fb_f5f6c2b44ae3 / fb_ef69bde92d3e: internal cp numbers leak
        # into user-facing text per [[feedback_1200_test]]. Describe
        # the capture concretely instead.
        if uncontested:
            cap = f"{_played(f)}. Free {captured} — nothing recaptures."
        elif f.get("is_capture"):
            cap = f"{_played(f)} — takes the {captured}."
        else:
            cap = f"{_played(f)}. Wins material in the resulting line."
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
        f"{_played(f)} threatens the {threat['target_piece_type']} "
        f"on {threat['target_square']}."
    )
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
    piece = f.get("moving_piece_type", "piece")
    sq = f.get("target_square", "")
    mover_is_user = f.get("mover_is_user")
    if mover_is_user is False:
        cap = f"Opponent develops the {piece} to {sq}."
    else:
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


def _r12_compose_why(f):
    """Compose a concrete WHY clause for an R12 user blunder.

    Reads facts the extractor already produces (no chess imports — renderer
    rules never compute chess meaning). Returns "" if no concrete fact is
    available. Order is priority: most-specific cases first so 1200-rated
    players see the actionable consequence, not a generic engine appeal.
    """
    moving_piece = f.get("moving_piece_type") or "piece"
    target_sq = f.get("target_square") or ""
    opp_reply = f.get("opp_reply_san")

    # 1. Opponent's reply directly attacks the just-moved piece.
    #    Covers cases like Ne5 -> f4 where the move strands its own piece.
    if opp_reply and f.get("opp_reply_attacks_played_piece") and target_sq:
        return f"After {opp_reply}, your {moving_piece} on {target_sq} has no safe square."

    # 2. The move itself landed on a losing-exchange square.
    if f.get("is_exchange_losing") and target_sq:
        if opp_reply:
            return f"After {opp_reply}, your {moving_piece} on {target_sq} falls."
        return f"Your {moving_piece} on {target_sq} can't be defended."

    # 3. The move stripped a defender from another own piece.
    undef = f.get("pieces_now_undefended") or []
    hanging = [p for p in undef if p.get("now_attacked") and p.get("is_now_hanging")]
    if hanging:
        worst = max(hanging, key=lambda p: p.get("piece_value_cp", 0) or 0)
        piece = worst.get("piece_type", "piece")
        sq = worst.get("square", "")
        if sq:
            return f"Your {piece} on {sq} is now undefended."

    # 4. Opponent's reply wins material outright.
    cap_piece = f.get("opp_reply_captures_piece_type")
    if opp_reply and cap_piece:
        return f"Opponent plays {opp_reply} winning your {cap_piece}."

    # 5. Opponent's reply is a check.
    if opp_reply and (opp_reply.endswith("+") or opp_reply.endswith("#")):
        return f"Opponent has {opp_reply} forcing your king."

    # 6. Bare opponent response when nothing more specific applies.
    if opp_reply:
        return f"Opponent's strongest reply: {opp_reply}."

    return ""


def _r12_compose_why_opp(f):
    """Compose a user-actionable WHY when OPPONENT blundered.

    Mirror of `_r12_compose_why` but from the user's perspective: the
    user is the one with the strong reply now. Reads facts the extractor
    produces. Returns "" if no concrete fact is available.

    Closes Parth 2026-05-18 Group B (#7-#11) and parts of Group D
    (#18-#20): "Opponent's X drops about N pawns" with no clue what
    we should DO about it.
    """
    # 1. User's best reply directly punishes the blunder.
    user_best = f.get("user_best_reply_san") or f.get("best_move_after_opp_blunder_san")
    if user_best:
        # What does our best reply DO?
        cap_pt = f.get("user_best_reply_captures_piece_type")
        if cap_pt:
            return f"You can play {user_best} winning the {cap_pt}."
        if user_best.endswith("+") or user_best.endswith("#"):
            return f"You can play {user_best} with a forcing reply."
        return f"You can play {user_best} to punish it."

    # 2. Opp's move left a piece undefended; we can take it.
    pieces_undef = f.get("opp_pieces_now_undefended") or f.get("pieces_now_undefended_by_opp") or []
    hanging = [p for p in pieces_undef if p.get("now_attacked") and p.get("is_now_hanging")]
    if hanging:
        worst = max(hanging, key=lambda p: p.get("piece_value_cp", 0) or 0)
        piece = worst.get("piece_type", "piece")
        sq = worst.get("square", "")
        if sq:
            return f"Their {piece} on {sq} is now undefended — take it."

    # 3. Opp's move stranded one of their own pieces — name the square.
    moving_piece = f.get("moving_piece_type") or "piece"
    target_sq = f.get("target_square") or ""
    if f.get("opp_played_landed_unsafe") and target_sq:
        return f"Their {moving_piece} on {target_sq} has no escape."

    return ""


def _r12_render(f):
    cpl = f.get("cp_loss") or 0
    pawns = max(1, min(9, round(cpl / 100)))
    pawns_word = "pawn" if pawns == 1 else "pawns"
    played = _played(f)
    best = _best(f)
    mover_is_user = f.get("mover_is_user")
    if mover_is_user is False:
        # Opp blundered — frame as user-actionable news.
        why = _r12_compose_why_opp(f)
        # Per [[no-hollow-coverage]] / [[feedback_1200_test]] — when we
        # have no concrete chess content to say (no opp-WHY clause)
        # AND the loss isn't blunder-tier, suppress entirely rather
        # than emit "Opponent's X drops about N pawns" with nothing
        # actionable. Honest silence > fluffy template.
        # For blunder-tier opp loss (cp_loss >= 250), keep firing with
        # the pawn-count so user knows opp gave up significant material,
        # even if we don't know the exact follow-up.
        if not why and cpl < 250:
            return None
        cap = f"Opponent's {played} drops about {pawns} {pawns_word}."
        if why:
            cap = cap + " " + why
    elif best and best != played:
        why = _r12_compose_why(f)
        # Same gate for user moves: if cp_loss is below blunder-tier
        # AND we have no WHY clause, suppress so a downstream rule (or
        # silence) takes over. Parth 2026-05-18 fb_47f9536059a6,
        # fb_f20bd8755a27, fb_62a02dd0ff9b: bare "loses about N pawns.
        # Y was better." is the hollow-WHY bug. Suppress it.
        if not why and cpl < 250:
            return None
        cap = f"{played} loses about {pawns} {pawns_word}. {best} was better."
        if why:
            cap = cap + " " + why
    else:
        why = _r12_compose_why(f)
        if not why and cpl < 250:
            return None
        cap = f"{played} loses about {pawns} {pawns_word}."
        if why:
            cap = cap + " " + why
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
    mover_is_user = f.get("mover_is_user")
    if mover_is_user is False:
        cap = f"{_played(f)}. Opponent claims the center."
    else:
        cap = f"{_played(f)}. Stakes a claim in the center."
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
    mover_is_user = f.get("mover_is_user")
    if mover_is_user is False:
        cap = f"{_played(f)}. Opponent had no better move here."
    else:
        cap = f"{_played(f)} — only move. Best you've got in this position."
    return CaptionOutput(
        caption=cap,
        highlight_squares=[f.get("target_square", "")] if f.get("target_square") else [],
        arrows=[],
        rule_name="R14_forced_best",
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
]
