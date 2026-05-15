"""
Caption Priority Resolver — pure-Python decision engine for the LLM
caption pipeline.

Collapses the 9 implicit branches the LLM used to navigate (trap /
opening / engine-best / primary_reason / shape / principle /
perspective / FEN / empty) into ONE decision made in code. The LLM
receives only the resolved focus + a tight whitelist of entities it
may name.

Per the architecture critique 2026-05-15: the deterministic extractor
(V5 facts) is the gold; the LLM should only verbalize. This module is
the "verbalize what?" decision — code, not prompt.

OUTPUT CONTRACT
───────────────
    {
      "should_skip"    : bool,
      "focus"          : "trap" | "shape" | "principle" | "opening"
                       | "mistake" | "category" | "empty",
      "anchor_name"    : str | None,     # what to NAME (e.g. "Knight Fork")
      "anchor_detail"  : str | None,     # one-sentence ground-truth fact
      "allowed_moves"  : List[str],      # SANs the LLM may reference
      "allowed_pieces" : List[str],      # "knight on f3"-style strings
      "voice_hint"     : "praise" | "critique" | "observe",
      "perspective"    : "user" | "opp",
      "move_played"    : str,
    }

PRIORITY ORDER (highest first)
──────────────────────────────
    1. trap              — known opening trap setup/in-line
    2. shape             — TIER 3 shape pattern fired
    3. principle         — caption_facts principles_violated
    4. opening           — curriculum match + opening phase
    5. mistake           — severity is mistake/blunder
    6. category          — primary_reason_category set
    7. empty             — no teaching signal → skip

Locked rule renderer_never_computes_chess_meaning: this is a priority
ROUTER. It reads pre-extracted facts and chooses a focus. No chess
analysis, no FEN parsing, no engine calls.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple


# Mistake-class severities (used for voice_hint)
TEACHING_SEVERITIES = {"mistake", "blunder", "opp_mistake", "opp_blunder"}

# Severity → voice_hint mapping
_VOICE_HINT_BY_SEVERITY = {
    "good":           "observe",
    "context":        "observe",
    "inaccuracy":     "critique",
    "mistake":        "critique",
    "blunder":        "critique",
    "opp_inaccuracy": "observe",
    "opp_mistake":    "observe",
    "opp_blunder":    "observe",
}


# ECO opening name → family head trimmer (same logic as the previous
# llm_caption_generator._trim_opening_family — kept here so the
# resolver is self-contained).
_OPENING_FAMILY_RE = re.compile(
    r"^(.+?\b(?:Defense|Defence|Game|Opening|Gambit|Attack|System|Variation))\b",
    re.IGNORECASE,
)


def _trim_opening_family(opening_name: Optional[str]) -> Optional[str]:
    if not opening_name:
        return None
    m = _OPENING_FAMILY_RE.match(opening_name)
    return m.group(1) if m else opening_name


# Map move SAN's first character to piece-type word (for allowed_pieces
# derivation). Pawn moves don't have a piece letter — file letter starts.
_SAN_PIECE_LETTERS = {"K": "king", "Q": "queen", "R": "rook", "B": "bishop", "N": "knight"}


def _moving_piece_from_san(san: str) -> str:
    if not san:
        return "piece"
    if san in ("O-O", "O-O-O"):
        return "king"
    first = san[0]
    if first in _SAN_PIECE_LETTERS:
        return _SAN_PIECE_LETTERS[first]
    return "pawn"


def _target_square_from_san(san: str) -> Optional[str]:
    """Extract the destination square from a SAN string."""
    if not san:
        return None
    if san == "O-O":
        return None  # castling — destination depends on side
    if san == "O-O-O":
        return None
    # Match the last [a-h][1-8] in the SAN (before any +/# or promotion)
    m = re.findall(r"[a-h][1-8]", san)
    return m[-1] if m else None


def _piece_string(piece_type: str, square: Optional[str]) -> str:
    if not piece_type:
        return ""
    if square:
        return f"{piece_type} on {square}"
    return piece_type


# ───────────────────────────────────────────────────────────────────
# Branch resolvers
# ───────────────────────────────────────────────────────────────────


def _resolve_trap(move: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    trap = move.get("_trap")
    if not trap:
        return None
    name = trap.get("name") or "Trap"
    step_label = trap.get("step_label", "setup_completed")
    description = trap.get("description") or ""
    step_expl = trap.get("step_explanation") or ""
    next_mv = trap.get("next_expected_move")

    detail = description if step_label == "setup_completed" else (step_expl or description)

    allowed_moves = [move.get("move_san") or ""]
    if next_mv:
        allowed_moves.append(next_mv)

    voice = "praise" if trap.get("this_move_by_user") and step_label == "trap_player_punishes" else "observe"
    perspective = "user" if move.get("is_user_move") else "opp"

    return {
        "focus":         "trap",
        "anchor_name":   name,
        "anchor_detail": detail.strip(),
        "allowed_moves": [m for m in allowed_moves if m],
        "allowed_pieces": [],
        "voice_hint":    voice,
        "perspective":   perspective,
    }


def _resolve_shape(move: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    sp_name = move.get("shape_pattern_name")
    if not sp_name:
        return None
    targets = move.get("shape_pattern_targets") or []
    mover_sq = move.get("shape_pattern_mover")

    # Derive piece strings for allowed_pieces from targets/mover squares.
    # We don't have piece-type-per-square data in the resolver (no FEN),
    # so we surface the SQUARES themselves. The LLM can name them.
    pieces: List[str] = []
    if mover_sq:
        pieces.append(mover_sq)
    for t in targets:
        if t and t not in pieces:
            pieces.append(t)

    played = move.get("move_san") or ""
    best = move.get("best_move_san") or ""
    allowed_moves = [played]
    if best and best != played:
        allowed_moves.append(best)

    is_user = bool(move.get("is_user_move"))
    voice = "praise" if is_user and (best in ("", played)) else "critique" if is_user else "observe"
    perspective = "user" if is_user else "opp"

    detail = f"{sp_name} — squares involved: {', '.join(pieces) if pieces else 'see facts'}."

    return {
        "focus":         "shape",
        "anchor_name":   sp_name,
        "anchor_detail": detail,
        "allowed_moves": allowed_moves,
        "allowed_pieces": pieces,
        "voice_hint":    voice,
        "perspective":   perspective,
    }


def _resolve_principle(move: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    principles = move.get("caption_facts_principles_violated") or []
    if not principles:
        return None
    # Take the FIRST principle (already priority-sorted upstream).
    top = principles[0]
    pid = top.get("principle_id") or ""
    evidence = top.get("evidence") or {}

    # Anchor name — humanise the principle id for the LLM.
    anchor_name = _PRINCIPLE_LABEL.get(pid, pid.replace("_", " ").title())

    # Compose a one-sentence detail from evidence fields.
    detail = _principle_detail_text(pid, evidence)

    # Pieces involved — pull from common evidence fields.
    pieces: List[str] = []
    for sq_key, type_key in (
        ("hanging_piece_square",   "hanging_piece_type"),
        ("piece_square",            "piece_type"),
        ("attacker_square",         "attacker_piece"),
        ("loosened_pawn_to",        None),
        ("bishop_square",           None),
    ):
        sq = evidence.get(sq_key)
        pt = evidence.get(type_key) if type_key else None
        if sq:
            pieces.append(_piece_string(pt or "piece", sq))

    played = move.get("move_san") or ""
    best = move.get("best_move_san") or ""
    allowed_moves = [played]
    if best and best != played:
        allowed_moves.append(best)

    severity = move.get("severity") or ""
    voice = _VOICE_HINT_BY_SEVERITY.get(severity, "observe")
    perspective = "user" if move.get("is_user_move") else "opp"

    return {
        "focus":         "principle",
        "anchor_name":   anchor_name,
        "anchor_detail": detail,
        "allowed_moves": allowed_moves,
        "allowed_pieces": pieces,
        "voice_hint":    voice,
        "perspective":   perspective,
    }


# Subset of player-facing principle labels. Kept short — for the
# resolver's own use; the LLM gets the label string only when this
# principle fires on the move.
_PRINCIPLE_LABEL = {
    "OP_FINISH_DEVELOPMENT":      "Develop all your pieces first",
    "OP_LOOSE_KING_PAWNS":        "Loose pawns near the king",
    "OP_QUEEN_OUT_EARLY":         "Queen out early gets chased",
    "OP_SAME_PIECE_TWICE":        "Don't move the same piece twice",
    "OP_PAWN_HEAVY":              "Too many pawn moves",
    "OP_CLAIM_CENTER":            "Claim the centre first",
    "OP_KNIGHT_ON_RIM":           "Knight on the rim",
    "OP_BISHOP_BLOCKED":          "Bishop blocked by own pawn",
    "OP_NOT_CASTLED":             "Castle by move 12",
    "TAC_CHECKS_CAPTURES_THREATS": "Checks, captures, threats first",
    "TAC_BACK_RANK":              "Back-rank weakness",
    "TAC_HANGING_PIECE":          "Loose piece on the board",
    "TAC_DEFENDER_COUNT":         "Count attackers and defenders",
    "TAC_FORK_PATTERN":           "Fork — one piece, two targets",
    "TAC_PIN_PATTERN":            "Pin — two pieces on one line",
    "TAC_SKEWER_PATTERN":         "Skewer",
    "TAC_DISCOVERED_PATTERN":     "Discovered attack",
    "DEF_MOST_ATTACKED":          "Defend the most-attacked piece",
    "TAC_CHANGED_AFTER_MOVE":     "What changed after the move",
    "MID_KING_SAFETY":            "King safety",
    "MID_KEEP_ATTACKERS":         "Trade defenders, keep attackers",
    "MID_ROOK_OPEN_FILE":         "Rook on the open file",
    "DEF_TRADE_ATTACKERS":        "Defending — trade their attackers",
    "MID_BAD_BISHOP":             "Bad bishop, reroute or trade",
    "MID_PAWN_BREAK":             "Pawn break opens the attack",
    "DEF_WALK_KING":              "Walk the king to safety",
    "END_PASSED_PAWN":            "Passed pawns must be pushed",
    "END_KING_ACTIVE":            "King is a fighter in the endgame",
}


def _principle_detail_text(pid: str, evidence: Dict[str, Any]) -> str:
    """Short ground-truth sentence built from evidence dict."""
    if not evidence:
        return _PRINCIPLE_LABEL.get(pid, pid).lower() + "."

    # Specialised per-principle phrasing for the most common cases.
    if pid == "TAC_HANGING_PIECE":
        sq = evidence.get("hanging_piece_square")
        pt = evidence.get("hanging_piece_type")
        owner = evidence.get("piece_color")
        side = "your" if owner == "user" else "their" if owner else "a"
        if sq and pt:
            return f"{side.capitalize()} {pt} on {sq} has no defender."
    if pid == "OP_BISHOP_BLOCKED":
        sq = evidence.get("bishop_square")
        blocker = evidence.get("blocking_pawn_to")
        if sq:
            return f"Bishop on {sq} blocked by own pawn{f' on {blocker}' if blocker else ''}."
    if pid == "OP_LOOSE_KING_PAWNS":
        sq = evidence.get("loosened_pawn_to")
        king_sq = evidence.get("king_still_on")
        if sq:
            return f"Pawn pushed to {sq} weakens the king{f' on {king_sq}' if king_sq else ''}."
    if pid == "OP_SAME_PIECE_TWICE":
        return "Same piece moved twice in the opening — fresh pieces still home."
    if pid == "OP_PAWN_HEAVY":
        n = evidence.get("own_pawn_moves_so_far")
        if n:
            return f"{n} pawn moves so far — pieces still on starting squares."
    # Fallback: principle label, lower-cased.
    return _PRINCIPLE_LABEL.get(pid, pid).lower() + "."


def _resolve_opening(move: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if move.get("phase") != "opening":
        return None
    op = move.get("_opening")
    if op:
        family = op.get("name") or ""
        summary = op.get("summary") or ""
        rules = op.get("golden_rules") or []
        # Pick the first golden rule as the teaching anchor; summary as fallback.
        detail = (rules[0] if rules else summary).strip()
    else:
        # Curriculum didn't match — fall back to ECO family trim.
        family = _trim_opening_family(move.get("opening_name")) or ""
        detail = ""

    if not family:
        return None

    played = move.get("move_san") or ""
    perspective = "user" if move.get("is_user_move") else "opp"

    return {
        "focus":         "opening",
        "anchor_name":   family,
        "anchor_detail": detail,
        "allowed_moves": [played],
        "allowed_pieces": [],
        "voice_hint":    "observe",
        "perspective":   perspective,
    }


def _resolve_mistake(move: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    severity = move.get("severity") or ""
    if severity not in TEACHING_SEVERITIES:
        return None
    played = move.get("move_san") or ""
    best = move.get("best_move_san") or ""
    if not best or best == played:
        return None

    is_user = bool(move.get("is_user_move"))
    voice = "critique" if is_user else "observe"
    perspective = "user" if is_user else "opp"

    # Anchor: "blunder" / "mistake" / similar
    label = severity.replace("opp_", "").capitalize()
    detail = f"Better was {best}."

    return {
        "focus":         "mistake",
        "anchor_name":   label,
        "anchor_detail": detail,
        "allowed_moves": [played, best],
        "allowed_pieces": [],
        "voice_hint":    voice,
        "perspective":   perspective,
    }


_CATEGORY_LABEL = {
    "opening_central_pawn": "Claims the centre",
    "development":          "Develops a piece",
    "opening_castled":      "Castles",
    "material":             "Material change",
    "tactic_played":        "Tactic",
    "check_plain":          "Check",
    "check_extra":          "Check with extra threat",
    "threat":               "Creates a threat",
    "mate":                 "Mate threat",
}


def _resolve_category(move: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    primary = move.get("caption_facts_primary_reason") or {}
    if not isinstance(primary, dict):
        return None
    category = primary.get("category")
    if not category:
        return None
    # Forced recapture is the SKIP signal even when it's in primary_reason.
    if category == "forced_recapture":
        return None

    played = move.get("move_san") or ""
    best = move.get("best_move_san") or ""

    label = _CATEGORY_LABEL.get(category, category.replace("_", " "))
    detail = ""

    # For captures, surface what was captured.
    captured = move.get("captured_piece_type")
    if category == "material" and captured:
        target_sq = _target_square_from_san(played)
        detail = f"Captures the {captured}{f' on {target_sq}' if target_sq else ''}."

    allowed_moves = [played]
    if best and best != played:
        allowed_moves.append(best)

    voice = "praise" if move.get("is_user_move") else "observe"
    perspective = "user" if move.get("is_user_move") else "opp"

    return {
        "focus":         "category",
        "anchor_name":   label,
        "anchor_detail": detail,
        "allowed_moves": allowed_moves,
        "allowed_pieces": [],
        "voice_hint":    voice,
        "perspective":   perspective,
    }


# ───────────────────────────────────────────────────────────────────
# Public entry point
# ───────────────────────────────────────────────────────────────────


def resolve_priority(move: Dict[str, Any]) -> Dict[str, Any]:
    """Decide what the LLM should focus on for this move.

    Returns the contract documented at the top of this module.
    Always returns a dict; empty-output cases are signalled by
    should_skip=True.
    """
    move_played = move.get("move_san") or ""

    # Forced recapture: hard skip, regardless of other facts.
    primary = move.get("caption_facts_primary_reason") or {}
    if isinstance(primary, dict) and primary.get("category") == "forced_recapture":
        return _empty(move_played)

    # Try resolvers in priority order. First non-None wins.
    for resolver in (
        _resolve_trap,
        _resolve_shape,
        _resolve_principle,
        _resolve_opening,
        _resolve_mistake,
        _resolve_category,
    ):
        decision = resolver(move)
        if decision is not None:
            decision["should_skip"] = False
            decision["move_played"] = move_played
            return decision

    return _empty(move_played)


def _empty(move_played: str) -> Dict[str, Any]:
    return {
        "should_skip":   True,
        "focus":         "empty",
        "anchor_name":   None,
        "anchor_detail": None,
        "allowed_moves": [],
        "allowed_pieces": [],
        "voice_hint":    "observe",
        "perspective":   "user",
        "move_played":   move_played,
    }
