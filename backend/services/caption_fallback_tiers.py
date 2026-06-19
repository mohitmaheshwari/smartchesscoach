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
_GOOD_CP = 50  # below this a quiet move is genuinely fine; above, don't call it "solid"


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


def tier23_caption(facts: Dict[str, Any]) -> Tuple[str, str]:
    sub = _subject(facts)
    poss = _poss(facts)
    pt = facts.get("moving_piece_type")
    piece = _PIECE.get(pt, "piece")
    cp = int(facts.get("cp_loss") or 0)

    # ── Tier 2 — explain what the move does (priority order) ───────────────
    if facts.get("is_capture"):
        cap = _PIECE.get(facts.get("captured_piece_type"), "piece")
        sq = facts.get("target_square") or ""
        on = f" on {sq}" if sq else ""
        mdelta = int(facts.get("material_delta_played_cp") or 0)
        if facts.get("is_forced_recapture") or abs(mdelta) <= 60:
            tail = " — an even trade that keeps the balance."
        elif (mdelta > 60) == bool(facts.get("mover_is_user")) or mdelta > 60:
            tail = " — winning material." if mdelta > 150 else " — picking up a pawn."
        else:
            tail = "."
        return (f"{sub} take{'' if sub=='You' else 's'} the {cap}{on}{tail}", "R_TIER2_capture")

    if facts.get("is_castling"):
        return (f"{sub} castle{'' if sub=='You' else 's'} — the king tucks away safely "
                f"and the rook joins the game.", "R_TIER2_castle")

    if facts.get("is_check"):
        return (f"{sub} give{'' if sub=='You' else 's'} a check, forcing a reply.",
                "R_TIER2_check")

    if _develops(facts):
        return (f"{sub} develop{'' if sub=='You' else 's'} the {piece}, bringing a new "
                f"piece into the game.", "R_TIER2_develop")

    if facts.get("is_pawn_move"):
        sq = facts.get("target_square") or ""
        file_ = sq[0] if sq else ""
        fclause = f"the {file_}-pawn" if file_ else "a pawn"
        return (f"{sub} push{'' if sub=='You' else 'es'} {fclause}, claiming a little space.",
                "R_TIER2_pawn")

    if facts.get("threats_created"):
        return (f"{sub} bring{'' if sub=='You' else 's'} the {piece} to a more active spot.",
                "R_TIER2_activate")

    # ── Tier 3 — never-silence floor (gated so we don't praise a real slip) ─
    if pt == "king" and cp < _GOOD_CP:
        return (f"{sub} tidy{'' if sub=='You' else 's'} up the king, keeping it safe."
                + _eval_suffix(facts), "R_TIER3_king_safety")

    if cp < _GOOD_CP:
        return (f"A calm move that keeps {poss} position solid." + _eval_suffix(facts),
                "R_TIER3_calm")

    # cp is high but no detector fired — be honest, don't claim "solid".
    return (f"{sub} reposition{'' if sub=='You' else 's'} the {piece}; a more active "
            f"try was available here.", "R_TIER3_quiet_slip")
