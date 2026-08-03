"""
Rating-band teaching depth — PILOT (piece_safety only).

Prototype for docs/rating_band_teaching_depth_scope.md. NOT wired into
any live caller yet (neither realtime_coaching_feedback.py nor
caption_pipeline.py import this module). This exists to prove the
mechanism — real, engine-verified piece_safety positions rendered at all
four existing rating bands — for review before any production wiring.

Reuses the existing RATING_BANDS / get_rating_band() from
deterministic_coach_service.py rather than inventing new tiers, per the
scope doc's Section 0 decision (EXTEND, not PARALLEL).

Content source: docs/piece_safety_depth_tiers_authored.md — 3 real,
board-verified positions. Do NOT add more positions here without the same
verify-before-authoring discipline (2 of the original 4 candidates were
dropped after engine verification contradicted the simple narrative;
see that doc for what went wrong and why).
"""
from __future__ import annotations

from typing import Optional

from deterministic_coach_service import get_rating_band

# PWC (live play) length cap, per the scope doc's §6 resolution: share the
# same tiers as review, but cap rendered length regardless of band — a
# live, time-pressured game shouldn't get a paragraph even for a beginner.
PWC_MAX_CHARS = 140

PIECE_SAFETY_POSITIONS = {
    "bxf7_check_sac": {
        "game_id": "game_f2c022e03856",
        "pattern": "direct_hang",
        "played_san": "Bxf7+",
        "tiers": {
            "beginner_low": (
                "Bxf7+ gives check, but nothing defends your bishop on f7 "
                "— Black's king just takes it back with Kxf7. Before you "
                "capture with check, make sure the square is actually safe "
                "afterward, not just that it forces a reply."
            ),
            "beginner_high": (
                "Bxf7+ wins a pawn and forces the king to move, but only "
                "your bishop attacks f7 — no other piece backs it up. So "
                "after Kxf7, you're not up material, you're down a whole "
                "bishop for one pawn."
            ),
            "intermediate": (
                "Bxf7+ trades your bishop for a pawn and a forced king "
                "move, but the king move alone isn't worth a piece here — "
                "Black's king on f7 isn't actually in danger afterward, so "
                "you've spent your best minor piece for nothing concrete. "
                "Be3 kept developing and left the bishop for a moment when "
                "it would really cost something."
            ),
            "advanced": (
                "Bxf7+?? Kxf7 just loses the piece — the check achieves "
                "nothing since nothing backs it up. Be3 was calm and correct."
            ),
        },
    },
    "qxh3_queen_sac": {
        "game_id": "game_8efcc1db5aa4",
        "pattern": "direct_hang",
        "played_san": "Qxh3",
        "tiers": {
            "beginner_low": (
                "Qxh3 puts your queen on a square White's pawn on g2 "
                "already guards — gxh3 wins your queen for a pawn. Before "
                "any capture, check whether a pawn or piece already covers "
                "that square."
            ),
            "beginner_high": (
                "Qxh3 takes a pawn, but g2 was already watching h3 the "
                "whole time — your queen has nothing backing it up there, "
                "so gxh3 just wins your queen outright, not a fair trade."
            ),
            "intermediate": (
                "Qxh3 looks tempting — it grabs a pawn and gets close to "
                "White's king — but the g2 pawn was always covering h3, so "
                "this isn't a real sacrifice, it's a straight queen loss. "
                "Qg6 kept the queen active and safe, still eyeing the "
                "kingside without handing over your most valuable piece."
            ),
            "advanced": (
                "Qxh3?? gxh3 just loses the queen for a pawn — g2 always "
                "had it covered. Qg6 kept the pressure without the risk."
            ),
        },
    },
    "qd2_ignores_hang": {
        "game_id": "game_665fd66c997a",
        "pattern": "ignored_existing_threat",
        "played_san": "Qd2",
        "tiers": {
            "beginner_low": (
                "Qd2 doesn't deal with the fact that Black can already "
                "play Bxc4, winning your bishop — it was already "
                "undefended. Before making your own plan, always check: is "
                "anything of mine hanging right now?"
            ),
            "beginner_high": (
                "Qd2 develops the queen, but it ignores that your bishop "
                "on c4 has no defender and Black can simply take it with "
                "Bxc4. A move here needed to either defend c4, move the "
                "bishop, or find something bigger to do instead."
            ),
            "intermediate": (
                "Qd2 leaves the c4 bishop hanging to Bxc4 — and since the "
                "queen move doesn't create a big enough threat of its own, "
                "Black just wins the piece next move with nothing to show "
                "for it. Bxe6 was the right idea: instead of trying to "
                "save the bishop, it grabs Black's own loose piece on e6 "
                "first, so even after Bxc4, the trade comes out even or "
                "ahead."
            ),
            "advanced": (
                "Qd2 ignores Bxc4 hanging — Bxe6 first was correct, since "
                "it wins material of your own before Black gets to collect "
                "on c4."
            ),
        },
    },
}


def render_piece_safety_tier(
    position_key: str,
    user_rating: int,
    *,
    pwc_mode: bool = False,
) -> Optional[str]:
    """Render the depth-appropriate explanation for one authored position.

    position_key: one of PIECE_SAFETY_POSITIONS' keys.
    user_rating: the player's rating — mapped to a tier via the existing
        get_rating_band(), not a new threshold system.
    pwc_mode: if True, cap the rendered text to PWC_MAX_CHARS (truncate at
        the nearest sentence boundary) — live play shouldn't get a
        paragraph regardless of rating band.

    Returns None if position_key is unknown.
    """
    entry = PIECE_SAFETY_POSITIONS.get(position_key)
    if entry is None:
        return None

    band = get_rating_band(user_rating)
    tier_text = entry["tiers"][band["name"]]

    if pwc_mode and len(tier_text) > PWC_MAX_CHARS:
        truncated = tier_text[:PWC_MAX_CHARS]
        last_period = truncated.rfind(". ")
        if last_period > 0:
            tier_text = truncated[: last_period + 1]
        else:
            tier_text = truncated.rstrip() + "…"

    return tier_text
