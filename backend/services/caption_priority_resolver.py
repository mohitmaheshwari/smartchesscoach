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
      "should_skip"        : bool,
      "focus"              : "trap" | "shape" | "principle" | "opening"
                           | "mistake" | "category" | "empty",
      "anchor_name"        : str | None,     # PRIMARY — what to NAME
      "anchor_detail"      : str | None,     # one-sentence ground-truth fact
      "secondary_focus"    : str | None,     # OPTIONAL second concept
      "secondary_anchor"   : str | None,     # name of secondary
      "secondary_detail"   : str | None,     # ground-truth for secondary
      "allowed_moves"      : List[str],      # SANs the LLM may reference
      "allowed_pieces"     : List[str],      # "knight on f3"-style strings
      "voice_hint"         : "praise" | "critique" | "observe",
      "perspective"        : "user" | "opp",
      "move_played"        : str,
      "move_role_phrase"   : str | None,     # generic fallback ("claims the
                                              # centre", "develops a piece")
                                              # — used by verifier for repair
      "punishment_move"    : str | None,     # opponent's best reply to a
                                              # mistake/blunder — the PUNISHMENT
                                              # the move walks into. Surfaces
                                              # pv_after_played[0] when severity
                                              # is in TEACHING_SEVERITIES.
    }

PRIMARY + SECONDARY pattern (2026-05-15 evolution)
────────────────────────────────────────────────────
The first non-None branch is the primary anchor. The second non-None,
non-redundant branch becomes the secondary — the LLM is told it may
weave it in IF natural within the 18-word limit. Redundant pairs
(same focus, same anchor_name, or category-as-secondary) are dropped.

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


# Central squares for "claims the centre" detection.
_CENTRAL_PAWN_TARGETS = {"d4", "d5", "e4", "e5"}
_CENTRE_ADJACENT      = {"c4", "c5", "f4", "f5", "d3", "d6", "e3", "e6"}


# ───────────────────────────────────────────────────────────────────
# Three-tier mode dispatch + protected entity extraction
# ───────────────────────────────────────────────────────────────────
#
# Architecture (Mohit signoff 2026-05-16):
#   Tier 1 (polish):    deterministic draft exists → LLM polishes for voice
#                       while preserving all protected entities verbatim
#   Tier 2 (controlled_gen): no draft but resolver has strong anchor →
#                       current anchor-driven prompt (build sentence from
#                       resolver decision)
#   Tier 3 (silent):    weak/no semantic signal → return empty string
#
# Protected entities are the chess primitives (SAN moves, squares, piece
# names, pattern names) that must survive any LLM rewrite character-for-
# character. The verifier enforces this — falling back to the draft as-is
# if the LLM strips one.

_PIECE_WORDS = {"queen", "knight", "bishop", "rook", "king", "pawn"}

# SAN matcher — accepts piece + optional disambig + optional x + dest,
# pawn captures (axb4), pawn moves (e4), promotions (e8=Q), castling.
_SAN_RE = re.compile(
    r"\b("
    r"[KQRBN][a-h]?[1-8]?x?[a-h][1-8](?:=[QRBN])?[+#]?"
    r"|[a-h]x[a-h][1-8](?:=[QRBN])?[+#]?"
    r"|[a-h][1-8](?:=[QRBN])?[+#]?"
    r"|O-O-O|O-O"
    r")\b"
)
_SQUARE_RE = re.compile(r"\b[a-h][1-8]\b")


def _extract_protected_entities(draft: str, decision: Dict[str, Any]) -> List[str]:
    """Pull every concrete chess token from the draft + key entities from
    the resolver decision. These are the spans the LLM must preserve.

    What counts as protected:
      - Every SAN move in the draft (case-sensitive; SAN is conventional)
      - Every square name (case-sensitive lowercase, e.g. "d6")
      - Every piece word (case-insensitive: queen, knight, ...)
      - The shape pattern name from the resolver, if any
      - The principle anchor name when it's a NAMED pattern the player
        should recognise (Queen out early gets chased, etc.)
    """
    if not draft:
        draft = ""
    protected: List[str] = []
    seen: set = set()

    def _add(token: str):
        if not token:
            return
        key = token.lower()
        if key in seen:
            return
        seen.add(key)
        protected.append(token)

    for m in _SAN_RE.findall(draft):
        _add(m)
    for sq in _SQUARE_RE.findall(draft):
        _add(sq)
    for word in re.findall(r"[A-Za-z]+", draft):
        if word.lower() in _PIECE_WORDS:
            _add(word.lower())

    focus = decision.get("focus", "")
    anchor = decision.get("anchor_name") or ""
    # Protect anchor for shape / trap / named principles (Rule of the
    # Square, The Opposition, etc.). These are proper-noun teaching
    # concepts the LLM must preserve verbatim. For generic principle
    # labels ("Loose piece on the board") protection is also OK — the
    # verifier matches case-insensitively, so the LLM can use sentence
    # case without triggering a fallback.
    if focus in ("shape", "trap", "principle") and anchor:
        _add(anchor)
    if decision.get("punishment_move"):
        _add(decision["punishment_move"])
    for mv in (decision.get("allowed_moves") or []):
        _add(mv)

    return protected


def _resolve_caption_mode(move: Dict[str, Any], decision: Dict[str, Any]) -> str:
    """Pick which generation mode the LLM should run in.

    Reads `decision["deterministic_draft"]` (set upstream — may come
    from the principle anchor's specialised detail OR move["caption"],
    whichever the upstream draft resolver picked). Never falls back to
    a giant prompt — Tier 2 is the current bounded controlled-generation
    path, and Tier 3 is silence.
    """
    if decision.get("should_skip"):
        return "silent"
    draft = (decision.get("deterministic_draft") or "").strip()
    if draft:
        return "polish"
    if decision.get("anchor_name"):
        return "controlled_gen"
    return "silent"


def _move_role_phrase(san: str) -> Optional[str]:
    """Generic, board-free phrase describing what a move does in plain
    coach English. Used by the verifier when it strips a disallowed
    opening/shape name and needs a SAFE replacement clause.

    Pure string lookup — no chess imports, no FEN, no PV. Allowed by
    the locked rule renderer_never_computes_chess_meaning.
    """
    if not san:
        return None
    if san in ("O-O", "O-O-O"):
        return "castles for king safety"

    piece = _moving_piece_from_san(san)
    target = _target_square_from_san(san)

    if piece == "pawn":
        if target in _CENTRAL_PAWN_TARGETS:
            return "claims the centre"
        if target in _CENTRE_ADJACENT:
            return "fights for the centre"
        return "pushes the pawn forward"
    if piece in ("knight", "bishop"):
        return "develops a piece"
    if piece == "rook":
        return "swings the rook to a better file"
    if piece == "queen":
        return "moves the queen"
    if piece == "king":
        return "walks the king"
    return None


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
    # Prefer the principle the V5 deterministic renderer already chose
    # (principle_id_used). The rule engine prioritizes by relevance —
    # e.g. for a blunder where dxe4 was the forcing move, it picks
    # TAC_CHECKS_CAPTURES_THREATS over OP_QUEEN_OUT_EARLY even though
    # the queen-out-early principle also fires. Resolver previously
    # took principles[0] which was source-order, leading to abstract
    # framing ("queen out early") on what should be tactical teaching
    # ("dxe4 was the forcing move"). Mohit feedback fb_eb1d11ba227f.
    used_id = move.get("principle_id_used") or ""
    top: Optional[Dict[str, Any]] = None
    if used_id:
        for p in principles:
            if p.get("principle_id") == used_id:
                top = p
                break
    if top is None:
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
    # Added 2026-05-16 (Mohit signoff). See
    # project_endgame_principles_backlog.md for the full plan.
    "END_RULE_OF_SQUARE":         "Rule of the Square",
    "END_OPPOSITION":             "The Opposition",
    "END_ROOK_BEHIND_PASSER":     "Rook behind the passed pawn",
    # Added 2026-05-18 (Phase 6) — cross-opening theme detectors.
    "OP_BISHOP_TRADE_DOUBLES_PAWN": "Bishop trade doubles their pawns",
    "OP_F2_F7_STRIKE":             "Strike on f7 / f2",
    "OP_TRAPPED_KNIGHT":           "Knight has no safe square",
}


def _principle_detail_text(pid: str, evidence: Dict[str, Any]) -> str:
    """Short ground-truth sentence built from evidence dict."""
    if not evidence:
        return _PRINCIPLE_LABEL.get(pid, pid).lower() + "."

    # Specialised per-principle phrasing for the most common cases.
    if pid == "TAC_HANGING_PIECE":
        sq = evidence.get("hanging_piece_square")
        pt = evidence.get("hanging_piece_type")
        # The hanging piece always belongs to the side that just moved.
        # `mover_is_user` tells us whose perspective we're writing for.
        # Fix 2026-05-17 (Parth fb_b31dacc286bf): the old branch read
        # `piece_color` and compared against "user", but evidence
        # stores actual color ("white"/"black"), so it always picked
        # "their" — wrong when the user hung their own piece.
        mover_is_user = evidence.get("mover_is_user")
        if sq and pt:
            if mover_is_user is True:
                return f"Your {pt} on {sq} has no defender."
            if mover_is_user is False:
                return f"Their {pt} on {sq} has no defender."
            return f"A {pt} on {sq} has no defender."
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
    if pid == "END_RULE_OF_SQUARE":
        # Mohit's template (2026-05-16 signoff):
        # "Their pawn on {pawn_square} runs to promotion. Your king on
        #  {king_square_played} is too far ({king_distance_before} >
        #  {pawn_distance}). {king_should_move_to} catches it in time."
        # Trimmed to keep within the LLM's 18-word cap after the
        # anchor "Rule of the Square — " is prepended.
        pawn_sq = evidence.get("pawn_square")
        king_played = evidence.get("king_square_played")
        king_target = evidence.get("king_should_move_to")
        pawn_dist = evidence.get("pawn_distance")
        king_dist = evidence.get("king_distance_before")
        if pawn_sq and king_played and king_target and pawn_dist is not None and king_dist is not None:
            return (
                f"Their pawn on {pawn_sq} runs to promotion. "
                f"Your king on {king_played} is too far ({king_dist} > {pawn_dist}). "
                f"{king_target} catches it in time."
            )
        # Fallback if evidence shape changes — never lose the principle name.
        return "Step into the square — your king must catch their passed pawn."
    if pid == "END_ROOK_BEHIND_PASSER":
        # Phase 4 — 2026-05-18. Two templates by perspective:
        #   supporting (own passer): "Your rook to {target} sits behind
        #     the pawn on {passer} — Tarrasch's rule. Supports the push."
        #   restraining (opp's passer): "Your rook to {target} sits
        #     behind their pawn on {passer} — Tarrasch's rule. Restrains
        #     the advance."
        rook_to = evidence.get("rook_target_square")
        passer = evidence.get("passer_square")
        perspective = evidence.get("perspective", "supporting")
        if rook_to and passer:
            if perspective == "restraining":
                return (
                    f"Your rook to {rook_to} sits behind their pawn on {passer} — "
                    f"Tarrasch's rule. Restrains the advance."
                )
            return (
                f"Your rook to {rook_to} sits behind the pawn on {passer} — "
                f"Tarrasch's rule. Supports the push."
            )
        return "Rook behind the passed pawn — Tarrasch's rule."
    if pid == "END_OPPOSITION":
        # Phase 3 — 2026-05-17. Template:
        #   "Your king to {target} faces theirs on {their_king}. They
        #    must step aside."
        # After the anchor "The Opposition — " is prepended, that's
        # well within the LLM 18-word cap.
        your_king = evidence.get("your_king_square")
        their_king = evidence.get("their_king_square")
        target = evidence.get("your_king_should_move_to")
        kind = evidence.get("opposition_kind") or "direct"
        if your_king and their_king and target:
            if kind == "distant":
                return (
                    f"Distant opposition — your king to {target}, "
                    f"theirs on {their_king}. They must step aside."
                )
            if kind == "diagonal":
                return (
                    f"Diagonal opposition — your king to {target} "
                    f"faces theirs on {their_king}. They give way."
                )
            return (
                f"Your king to {target} faces theirs on {their_king}. "
                f"They must step aside."
            )
        # Fallback if evidence shape changes — never lose the principle name.
        return "Take the opposition — face their king on the same line."
    if pid == "DEF_WALK_KING":
        # 2026-05-18 self-audit: DEF_WALK_KING was falling through to the
        # generic principle_label.lower() fallback ("walk the king to
        # safety."), producing tautological captions like "Walk the king
        # to safety — walk the king to safety." when this principle won
        # the anchor (e.g., when END_RULE_OF_SQUARE is suppressed and
        # DEF_WALK_KING is the next-priority survivor).
        king_move = evidence.get("engine_king_move")
        if king_move:
            return (
                f"Castling rights are gone — walk your king to safety by hand. "
                f"{king_move} is engine's pick."
            )
        return "Castling rights are gone — walk the king to safety by hand."
    if pid == "END_PASSED_PAWN":
        # Phase 5 — 2026-05-18. Was falling through to the generic
        # principle_label.lower() fallback ("passed pawns must be pushed.")
        # which has no concrete board reference. 1200-test fail.
        # Now: name the passer and the engine pick.
        passers = evidence.get("passed_pawn_squares") or []
        best = evidence.get("engine_chose_push") or evidence.get("best_san") or ""
        if passers and best:
            if len(passers) == 1:
                return (
                    f"Your pawn on {passers[0]} is passed. Push it — "
                    f"{best} is engine's pick. Every square forces them to react."
                )
            return (
                f"You have passed pawns on {' and '.join(passers[:2])}. "
                f"Push — engine's pick: {best}."
            )
        if best:
            return f"Push the passed pawn — {best} is engine's pick."
        return "Passed pawns must be pushed — every square forces opponent to react."
    if pid == "END_KING_ACTIVE":
        # Phase 5 — 2026-05-18. Was falling through to "king is a
        # fighter in the endgame." which is conceptually right but
        # gives no concrete next step. Now: name where the king is
        # and orient toward the centre.
        king_sq = evidence.get("king_square")
        if king_sq:
            return (
                f"Your king on {king_sq} stays on the back rank. "
                f"Endgame — walk it toward the centre to fight."
            )
        return "Activate your king — in the endgame it's a fighter, walk it to the centre."
    if pid == "OP_QUEEN_OUT_EARLY":
        sq = evidence.get("queen_to")
        n_minors = evidence.get("minor_pieces_developed")
        aligned = evidence.get("aligned_moves_offered") or []
        aligned_str = aligned[0] if aligned else ""
        if sq and aligned_str and n_minors is not None:
            piece = "piece" if n_minors == 1 else "pieces"
            return (f"Queen to {sq} with only {n_minors} minor {piece} developed — "
                    f"{aligned_str} keeps her safer.")
        if sq:
            return f"Queen to {sq} early — develop minor pieces first; queens get chased."
    if pid == "OP_CLAIM_CENTER":
        return "The centre pawns control key squares; claim them before pieces move."
    if pid == "OP_KNIGHT_ON_RIM":
        sq = evidence.get("knight_to")
        if sq:
            return f"Knight on {sq} (rim) controls fewer squares than from a central post."
        return "Knight on the rim — central squares give the knight more reach."
    if pid == "OP_NOT_CASTLED":
        return "King still in the centre past move 12 — castle to move it to a safe flank."
    if pid == "TAC_BACK_RANK":
        sq = evidence.get("king_square")
        if sq:
            return f"King on {sq} has no escape squares — back rank weakness."
        return "Back rank weakness — your king has no escape square."
    if pid == "TAC_DEFENDER_COUNT":
        sq = evidence.get("piece_square")
        pt = evidence.get("piece_type")
        att = evidence.get("attacker_count")
        defn = evidence.get("defender_count")
        if sq and pt and att is not None and defn is not None:
            return f"{pt.capitalize()} on {sq} — {att} attackers vs {defn} defenders."
    if pid == "TAC_CHECKS_CAPTURES_THREATS":
        best = evidence.get("best_move")
        kind = evidence.get("best_kind")  # "capture" | "check" | "threat"
        if best and kind:
            return f"A {kind} was available: {best} was the forcing move."
    if pid == "TAC_DISCOVERED_PATTERN":
        # match_kind=missed_chance — player did NOT play the discovery,
        # engine wanted it. Without explicit framing the LLM applies the
        # principle text to the played move ("your move uncovers..."),
        # which is wrong.
        return "A discovered attack was available — the played move missed it."
    if pid == "TAC_FORK_PATTERN":
        return "A fork was available — the played move missed it."
    if pid == "TAC_PIN_PATTERN":
        return "A pin was available — the played move missed it."
    if pid == "TAC_SKEWER_PATTERN":
        return "A skewer was available — the played move missed it."
    # ── Cross-opening theme detectors (Phase 6, 2026-05-18) ────────
    if pid == "OP_BISHOP_TRADE_DOUBLES_PAWN":
        # Template: "Your bishop took on {capture_square} — their pawn
        # from {recapture_pawn_from} must recapture, doubling pawns
        # on the {file}-file. Long-term target."
        cap_sq = evidence.get("capture_square")
        pawn_from = evidence.get("recapture_pawn_from")
        file_letter = evidence.get("doubled_pawn_file")
        if cap_sq and pawn_from and file_letter:
            return (
                f"Bishop takes on {cap_sq} — their pawn from {pawn_from} must "
                f"recapture, doubling their pawns on the {file_letter}-file. "
                f"Long-term target."
            )
        return "Bishop trade forces a doubled-pawn recapture — long-term target."
    if pid == "OP_F2_F7_STRIKE":
        # Template: "Capture on {strike_square} — only the king on
        # {enemy_king_square} defends. {attacker_piece} wins material."
        strike = evidence.get("strike_square")
        king_sq = evidence.get("enemy_king_square")
        attacker = evidence.get("attacker_piece_type") or "piece"
        if strike and king_sq:
            return (
                f"Capture on {strike} — only the king on {king_sq} defends it. "
                f"Your {attacker} wins material on the weak square."
            )
        return "Strike on f7 / f2 — the square only the king defends in the opening."
    if pid == "OP_TRAPPED_KNIGHT":
        # Template: "Your knight on {square} has no safe square — "
        # "every escape is attacked. Rescue or trade it now."
        knight_sq = evidence.get("trapped_knight_square")
        attackers = evidence.get("enemy_attacker_squares") or []
        if knight_sq and attackers:
            if len(attackers) == 1:
                return (
                    f"Your knight on {knight_sq} has no safe square. "
                    f"The piece on {attackers[0]} hits it and every escape is "
                    f"attacked. Rescue or trade now."
                )
            return (
                f"Your knight on {knight_sq} has no safe square — every escape "
                f"is attacked. Rescue or trade now."
            )
        if knight_sq:
            return f"Your knight on {knight_sq} has no safe square — rescue or trade."
        return "Knight has no safe square — rescue or trade before they win it."
    if pid == "OP_FINISH_DEVELOPMENT":
        # Fires only when player attacks (threat or queen-sortie) with
        # 2+ undeveloped minor pieces. The detail must reflect THAT —
        # not the principle's name. Without specific phrasing the LLM
        # hallucinates content like "you delay developing" on what is
        # often a piece-moving-back move.
        n_undev = evidence.get("undeveloped_minor_count")
        trigger = evidence.get("trigger_kind", "")
        target = evidence.get("premature_attack_target")
        if trigger == "queen_sortie":
            return (f"Queen sortie with {n_undev} minor pieces still home — "
                    "develop first." if n_undev
                    else "Queen out early while minor pieces still home.")
        if target and n_undev:
            return f"Attacks {target} with {n_undev} minor pieces still on starting squares."
        if n_undev:
            return f"{n_undev} minor pieces still home — finish development before attacking."
    # Fallback: principle label, lower-cased.
    return _PRINCIPLE_LABEL.get(pid, pid).lower() + "."


def _resolve_opening(move: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if move.get("phase") != "opening":
        return None
    # Severity guard: a mistake/blunder during the opening is a more
    # urgent teaching moment than the opening's principles. Yield to
    # _resolve_mistake (which runs later in the priority chain) rather
    # than emitting a "Caro-Kann Defense — they develop ..." caption
    # on a +6.7 → +2.2 eval drop. Mohit feedback fb_eb1d11ba227f.
    if move.get("severity") in TEACHING_SEVERITIES:
        return None
    op = move.get("_opening")
    if not op:
        # No curriculum match → no opening anchor. Previously fell back
        # to the game's whole-game `opening_name` field, but that name
        # is the post-hoc ECO classification of the FULL game — naming
        # it on move 1 ("e4 — Caro-Kann Defense") is anachronistic. The
        # curriculum's min_matched_steps=3 gate exists precisely so we
        # don't claim an opening before its signature move is played.
        return None

    family = op.get("name") or ""
    summary = op.get("summary") or ""
    rules = op.get("golden_rules") or []
    detail = (rules[0] if rules else summary).strip()

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

    is_user = bool(move.get("is_user_move"))
    voice = "critique" if is_user else "observe"
    perspective = "user" if is_user else "opp"

    # Anchor: "blunder" / "mistake" / similar
    label = severity.replace("opp_", "").capitalize()

    if best and best != played:
        detail = f"Better was {best}."
        allowed_moves = [played, best]
    else:
        # No clear alternative on file (Stockfish couldn't or didn't
        # surface a single best). Still surface that the move is a
        # mistake — silence on a blunder is worse than no suggestion.
        # Mohit feedback fb_eb1d11ba227f exposed this: opening branch
        # had been masking a +6.7→+2.2 opp_blunder.
        detail = ""
        allowed_moves = [played]

    return {
        "focus":         "mistake",
        "anchor_name":   label,
        "anchor_detail": detail,
        "allowed_moves": allowed_moves,
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


# Focuses too generic to ever be a SECONDARY anchor (they'd dilute the
# primary teaching point rather than blend with it).
_DISALLOWED_AS_SECONDARY = {"category", "mistake"}


def _is_redundant_secondary(primary: Dict[str, Any], candidate: Dict[str, Any]) -> bool:
    """True if `candidate` would just repeat the primary's teaching."""
    if candidate.get("focus") in _DISALLOWED_AS_SECONDARY:
        return True
    if candidate.get("focus") == primary.get("focus"):
        return True
    p_name = (primary.get("anchor_name") or "").strip().lower()
    c_name = (candidate.get("anchor_name") or "").strip().lower()
    if p_name and c_name and p_name == c_name:
        return True
    return False


def resolve_priority(move: Dict[str, Any]) -> Dict[str, Any]:
    """Decide what the LLM should focus on for this move.

    Collects ALL non-None branch decisions in priority order, picks the
    first as primary, and the first non-redundant follow-up as secondary.
    The secondary is OPTIONAL — the LLM may weave it in or omit it
    depending on word budget.
    """
    move_played = move.get("move_san") or ""
    role_phrase = _move_role_phrase(move_played)

    # Punishment move: opponent's best reply to a mistake/blunder. This is
    # the LINE that teaches WHY the played move was bad — not just what
    # should have been played instead. Only meaningful when severity is
    # mistake-class and the V5 extractor captured the PV.
    punishment_move: Optional[str] = None
    if move.get("severity") in TEACHING_SEVERITIES:
        pv_after_played = move.get("pv_after_played") or []
        if pv_after_played:
            punishment_move = pv_after_played[0]

    # Forced recapture: hard skip, regardless of other facts.
    primary_facts = move.get("caption_facts_primary_reason") or {}
    if isinstance(primary_facts, dict) and primary_facts.get("category") == "forced_recapture":
        return _empty(move_played, role_phrase, punishment_move)

    decisions: List[Dict[str, Any]] = []
    for resolver in (
        _resolve_trap,
        _resolve_shape,
        _resolve_principle,
        _resolve_opening,
        _resolve_mistake,
        _resolve_category,
    ):
        d = resolver(move)
        if d is not None:
            decisions.append(d)

    if not decisions:
        return _empty(move_played, role_phrase, punishment_move)

    primary = decisions[0]
    secondary: Optional[Dict[str, Any]] = None
    for cand in decisions[1:]:
        if not _is_redundant_secondary(primary, cand):
            secondary = cand
            break

    primary["should_skip"]       = False
    primary["move_played"]       = move_played
    primary["move_role_phrase"]  = role_phrase
    primary["punishment_move"]   = punishment_move
    primary["secondary_focus"]   = secondary["focus"] if secondary else None
    primary["secondary_anchor"]  = secondary["anchor_name"] if secondary else None
    primary["secondary_detail"]  = secondary["anchor_detail"] if secondary else None
    # Also surface punishment_move on the allowed_moves list — without
    # this, the verifier strips it as a hallucinated SAN.
    if punishment_move and punishment_move not in primary["allowed_moves"]:
        primary["allowed_moves"].append(punishment_move)

    # Three-tier mode dispatch + protected entities (Mohit 2026-05-16).
    #
    # Deterministic draft source priority (added 2026-05-17 — Mohit
    # signoff after audit showed the principle anchor_detail wasn't
    # reaching the polish prompt, so users saw the R12 generic
    # blunder template instead of "Rule of the Square — ..."):
    #
    #   1. When focus == "principle" AND the resolver built a
    #      specialised anchor_detail, use "{anchor_name} — {detail}"
    #      as the draft. The principle's specialised text IS the
    #      semantic IR per [[llm-as-controlled-narrator]]; that's
    #      what the polish step should preserve.
    #   2. Fall back to move["caption"] (legacy R01-R14 renderer-rule
    #      output) for non-principle anchors and for principles
    #      that don't have a specialised detail yet.
    focus_for_draft = primary.get("focus")
    anchor_name_for_draft = primary.get("anchor_name") or ""
    anchor_detail_for_draft = primary.get("anchor_detail") or ""
    if (focus_for_draft == "principle"
            and anchor_name_for_draft
            and anchor_detail_for_draft):
        deterministic_draft = f"{anchor_name_for_draft} — {anchor_detail_for_draft}"
    else:
        deterministic_draft = (move.get("caption") or "").strip()
    primary["deterministic_draft"] = deterministic_draft
    primary["caption_mode"]        = _resolve_caption_mode(move, primary)
    primary["protected_entities"]  = _extract_protected_entities(deterministic_draft, primary)
    return primary


def _empty(move_played: str, role_phrase: Optional[str] = None,
           punishment_move: Optional[str] = None) -> Dict[str, Any]:
    return {
        "should_skip":         True,
        "focus":               "empty",
        "anchor_name":         None,
        "anchor_detail":       None,
        "secondary_focus":     None,
        "secondary_anchor":    None,
        "secondary_detail":    None,
        "allowed_moves":       [],
        "allowed_pieces":      [],
        "voice_hint":          "observe",
        "perspective":         "user",
        "move_played":         move_played,
        "move_role_phrase":    role_phrase,
        "punishment_move":     punishment_move,
        "deterministic_draft": "",
        "caption_mode":        "silent",
        "protected_entities":  [],
    }
