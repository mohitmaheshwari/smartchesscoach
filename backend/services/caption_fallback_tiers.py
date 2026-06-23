"""caption_fallback_tiers.py — Tier-2/Tier-3 NEVER-SILENCE coverage (2026-06-19).

When the R-rule pipeline produces no caption (R_FALLBACK_no_primary /
R_FALLBACK_no_trigger_fired), this returns a SHORT, TRUE-by-construction caption
instead of silence. Coverage is a first-class metric (memory
feedback_coverage_is_first_class): a mediocre caption beats `(silent — nothing shown)`.

LAWS (same as caption_renderer): facts-only, NO `import chess`, no board inspection.
Every clause is true because it reads a field extract_facts already board-verified.
This is deterministic — NOT the LLM `narrator_fallback.py`.

  Tier 2 — move explanation (what the move DOES): capture / castle / check /
            develop / pawn-push / reposition.
  Tier 3 — fallback floor: a calm-move / king-safety / eval-framed line, gated on
            cp_loss so we never call a real mistake "solid".

tier23_caption(facts) -> (caption: str, rule_name: str)  ('' only if facts missing)
"""
from typing import Any, Dict, Tuple

_PIECE = {"pawn": "pawn", "knight": "knight", "bishop": "bishop",
          "rook": "rook", "queen": "queen", "king": "king"}
_GOOD_CP = 50    # below this a quiet move is genuinely fine; above, don't call it "solid"
_MISTAKE_CP = 120  # below this, don't name a "better move" — it's a style pref, not a mistake
_CENTER = {"d4", "e4", "d5", "e5"}  # the four central squares (control-the-center principle)
_INACCURACY_CP = 70  # with a principle-why, an inaccuracy is teachable (not engine-worship)
_PRINCIPLE_PHRASE = {
    "center": "takes the center",
    "develop": "develops a piece",
    "castle": "castles to safety",
    "rook_open_file": "puts a rook on the open file",
}


def _subject(facts: Dict[str, Any]) -> str:
    return "You" if facts.get("mover_is_user") else "Your opponent"


def _poss(facts: Dict[str, Any]) -> str:
    return "your" if facts.get("mover_is_user") else "their"


def _develops(facts: Dict[str, Any]) -> bool:
    """A minor piece leaving its home rank = development (true from from_square)."""
    if facts.get("moving_piece_type") not in ("knight", "bishop"):
        return False
    fr = facts.get("from_square") or ""
    color = facts.get("moving_piece_color")
    if len(fr) < 2:
        return False
    return (color == "white" and fr[1] == "1") or (color == "black" and fr[1] == "8")


def _eval_suffix(facts: Dict[str, Any]) -> str:
    if facts.get("mover_is_user"):
        if facts.get("user_is_winning"):
            return " You're ahead — keeping it simple is the right idea."
        if facts.get("user_is_losing"):
            return " You're worse here, but playing on is right."
    return ""


def _better_suffix(facts: Dict[str, Any]) -> str:
    """For a decent-but-suboptimal USER move, surface the engine's better move with its
    PRINCIPLE as the why ("Though e4 was a bit stronger, taking the center.") — the
    'decent, but Y was better' structure gold uses. Gated on a principle (teaching, not
    engine-worship: Bc5 cp35 names e4; the d5-Scandinavian is protected by opening-naming
    firing first) + a meaningful cp band (below this = style; at/above _MISTAKE_CP the
    flagged missed-opportunity path handles it). Verify-safe: best move is engine truth,
    principle is board-verified."""
    if not facts.get("mover_is_user"):
        return ""
    best = facts.get("best_move_san")
    played = facts.get("played_san")
    why = facts.get("best_move_why")
    cp = int(facts.get("cp_loss") or 0)
    if best and played and best != played and why and 25 <= cp < _MISTAKE_CP:
        return f" Though {best} was a bit stronger, {why}."
    return ""


def tier23_caption(facts: Dict[str, Any], flagged_mistake: bool = False) -> Tuple[str, str]:
    cp = int(facts.get("cp_loss") or 0)

    # Flagged mistake whose WHY we couldn't derive (e.g. narrator HELD): name the
    # stronger move ONLY for a REAL mistake. A marginal engine preference (e.g. 1...d5
    # Scandinavian, cp 36) is a style choice, NOT a mistake — naming "e5 was stronger"
    # is engine-worship (memory feedback_caption_tone_undramatic). Below the mistake
    # bar, fall through to a plain explanation of what the move does. No fabricated why.
    if flagged_mistake:
        played = facts.get("played_san")
        best = facts.get("best_move_san")
        why = facts.get("best_move_why")
        if played and best and best != played:
            # Missed opportunity WITH a why ("Nf3 was stronger — it develops a piece",
            # "exd4 was stronger — it trades off his bishop"). The why makes it teaching,
            # so it fires from the inaccuracy range, not engine-worship.
            if why and cp >= _INACCURACY_CP:
                return (f"You played {played}; {best} was stronger — it {why}.",
                        "R_TIER_missed_principle")
            # No why to name — only call out a better move on a real mistake.
            if cp >= _MISTAKE_CP:
                return (f"You played {played}; {best} was the stronger move here.",
                        "R_TIER_mistake_floor")

    sub = _subject(facts)
    poss = _poss(facts)
    pt = facts.get("moving_piece_type")
    piece = _PIECE.get(pt, "piece")
    _suf = _better_suffix(facts)  # "decent, but {best} was stronger ({principle})"

    # ── Tier 2 — explain what the move does (priority order) ───────────────
    if facts.get("is_capture"):
        cap = _PIECE.get(facts.get("captured_piece_type"), "piece")
        verb = "take" if facts.get("mover_is_user") else "takes"
        # No "on {square}": SAN already names it (feedback_dont_restate_destination_square),
        # and "{captured} on {sq}" reads as a present-tense location claim the verifier
        # rightly rejects (post-move that square holds the CAPTURING piece).
        base = f"{sub} {verb} the {cap}"
        # Material verdict ONLY from a SEE-verified fact. material_delta alone ignores the
        # recapture, so never assert "winning"/"even" from it.
        if facts.get("free_capture_uncontested"):
            what = "pawn" if facts.get("captured_piece_type") == "pawn" else "piece"
            # If a clearly better WAY to take it existed (e.g. recapture with the pawn,
            # not the queen), surface that instead of overselling "free".
            tail = ("." + _suf) if _suf else f" — a free {what}."
        elif facts.get("is_exchange_losing"):
            tail = " — though it gives material back on the trade."
        elif facts.get("is_forced_recapture"):
            tail = ", recapturing to keep things even."
        else:
            # neutral capture — surface a clearly better alternative (e.g. recapture
            # with the pawn exd4 instead of the queen) when one carries a principle.
            tail = "." + _suf
        return (base + tail, "R_TIER2_capture")

    if facts.get("is_castling"):
        return (f"{sub} castle{'' if sub=='You' else 's'} — the king tucks away safely "
                f"and the rook joins the game.", "R_TIER2_castle")

    if facts.get("is_check"):
        return (f"{sub} give{'' if sub=='You' else 's'} a check, forcing a reply.",
                "R_TIER2_check")

    # P2b: a pawn or piece landing on a central square = the control-the-center
    # principle (transferable, board-verified: the piece sits on d4/e4/d5/e5).
    # 'center' is the #1 transferable-principle miss (449). The claim is true by
    # construction — target_square is in _CENTER.
    _tsq = facts.get("target_square") or ""
    _central = _tsq in _CENTER

    if facts.get("played_move_principle") == "outpost":
        # "outpost" is on the banned-jargon list (600-1500 audience) — describe
        # the idea in plain terms instead. 2026-06-23.
        return (f"{sub} post{'' if sub=='You' else 's'} the knight on a strong central "
                f"square the opponent can't easily challenge." + _suf, "R_TIER2_outpost")

    if _develops(facts):
        _vb = "develop" if sub == "You" else "develops"
        # Eyes an enemy piece? Name it (board-verified). The eyed piece belongs to the
        # side NOT moving, so its possessive is the opposite of the mover's.
        _eyes_p = facts.get("developed_eyes_piece")
        _eyes_s = facts.get("developed_eyes_square")
        if _eyes_p and _eyes_s:
            _their = "their" if facts.get("mover_is_user") else "your"
            return (f"{sub} {_vb} the {piece}, eyeing {_their} {_eyes_p} on {_eyes_s}." + _suf,
                    "R_TIER2_develop_eyes")
        if _central:
            return (f"{sub} {_vb} the {piece} to a strong central square, fighting for the "
                    f"center." + _suf, "R_TIER2_develop_center")
        return (f"{sub} {_vb} the {piece}, bringing a new piece into the game." + _suf,
                "R_TIER2_develop")

    if facts.get("is_pawn_move"):
        file_ = _tsq[0] if _tsq else ""
        fclause = f"the {file_}-pawn" if file_ else "a pawn"
        if _central:
            return (f"{sub} push{'' if sub=='You' else 'es'} {fclause} into the center — "
                    f"controlling the center is a core idea." + _suf, "R_TIER2_center")
        return (f"{sub} push{'' if sub=='You' else 'es'} {fclause}, claiming a little space."
                + _suf, "R_TIER2_pawn")

    if facts.get("played_move_principle") == "rook_open_file":
        return (f"{sub} put{'' if sub=='You' else 's'} the {piece} on the open file — "
                f"rooks belong on open files." + _suf, "R_TIER2_rook_file")

    if facts.get("threats_created"):
        if _central:
            return (f"{sub} post{'' if sub=='You' else 's'} the {piece} on a strong central "
                    f"square." + _suf, "R_TIER2_activate_center")
        return (f"{sub} bring{'' if sub=='You' else 's'} the {piece} to a more active spot."
                + _suf, "R_TIER2_activate")

    # ── Tier 3 — never-silence floor (gated so we don't praise a real slip) ─
    if pt == "king" and cp < _GOOD_CP:
        return (f"{sub} tidy{'' if sub=='You' else 's'} up the king, keeping it safe."
                + _suf + _eval_suffix(facts), "R_TIER3_king_safety")

    if cp < _GOOD_CP:
        return (f"A calm move that keeps {poss} position solid." + _suf + _eval_suffix(facts),
                "R_TIER3_calm")

    # cp is high but no detector fired — be honest, don't claim "solid".
    return (f"{sub} reposition{'' if sub=='You' else 's'} the {piece}; a more active "
            f"try was available here.", "R_TIER3_quiet_slip")
