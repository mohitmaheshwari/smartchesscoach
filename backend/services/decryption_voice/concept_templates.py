"""
Caption templates per chess concept.

Each detector in services/chess_brain/detector_registry.py +
advanced_detectors.py returns a DetectorResult with:
  - pattern_type:  enum value (e.g., "hanging_piece", "missed_mate")
  - details:       structured facts dict (varies per pattern)
  - teaching_hook: pre-built short phrase

This module turns those structured facts into short coaching captions
in locked Indian English voice. No LLM. No hallucination — every word
comes from the deterministic detector output or a template constant.

Templates intentionally short (≤ 2 sentences) for the post-game
"What would you play?" interactive cards. The board does the visual
work; the caption confirms what just happened.
"""

from __future__ import annotations

import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


# ── Per-pattern template renderers ────────────────────────────────────
# Each function takes a DetectorResult.details dict and returns a
# short caption. Returns None if details are missing required fields
# (caller falls through to generic).

def _render_hanging_piece(details: Dict) -> Optional[str]:
    piece = details.get("hanging_piece")
    sq = details.get("hanging_square")
    if not piece or not sq:
        return None
    # Most-valuable hanging piece — usually decisive on its own.
    return f"Your {piece} on {sq} was hanging. They could take it for free."


def _render_trapped_piece(details: Dict) -> Optional[str]:
    piece = details.get("trapped_piece") or details.get("piece")
    sq = details.get("trapped_square") or details.get("square")
    if not piece or not sq:
        return None
    return f"Your {piece} on {sq} had no safe square to go to."


def _render_missed_mate(details: Dict) -> Optional[str]:
    mate_in = details.get("mate_in")
    mate_move = details.get("mate_move") or details.get("first_move")
    if not mate_move:
        return None
    if mate_in == 1:
        return f"You missed mate in 1: {mate_move} ends the game."
    if mate_in == 2:
        return f"You missed mate in 2 starting with {mate_move}."
    return f"You missed a forced mate starting with {mate_move}."


def _render_missed_fork(details: Dict) -> Optional[str]:
    attacker = details.get("attacker")
    attacker_sq = details.get("attacker_square")
    targets = details.get("targets") or []
    if not attacker or not attacker_sq or not targets:
        return None
    if len(targets) == 2:
        return (
            f"You missed a fork: your {attacker} to {attacker_sq} attacks "
            f"the {targets[0]} and the {targets[1]} at the same time."
        )
    return (
        f"You missed a fork: your {attacker} to {attacker_sq} attacks "
        f"{len(targets)} pieces at once."
    )


def _render_missed_pin(details: Dict) -> Optional[str]:
    pinning = details.get("pinning_piece") or details.get("attacker")
    pinned = details.get("pinned_piece") or details.get("target")
    pinned_sq = details.get("pinned_square") or details.get("target_square")
    if not pinning or not pinned:
        return None
    where = f" on {pinned_sq}" if pinned_sq else ""
    return f"You missed a pin: your {pinning} pins their {pinned}{where} — it cannot move."


def _render_missed_skewer(details: Dict) -> Optional[str]:
    front = details.get("front_piece")
    back = details.get("back_piece")
    if not front or not back:
        return None
    return f"You missed a skewer: their {front} must move and their {back} falls behind it."


def _render_missed_back_rank(details: Dict) -> Optional[str]:
    move = details.get("mate_move") or details.get("move")
    if not move:
        return "You missed a back-rank mate."
    return f"You missed a back-rank mate: {move} ends the game."


def _render_combination(details: Dict) -> Optional[str]:
    """Render the PV-walked combination chain. Variants by chain length
    and by whether the climax was mate or a fork."""
    chain = details.get("chain") or []
    if not chain:
        return None
    climax_tactic = details.get("climax_tactic")
    climax_details = details.get("climax_details") or {}
    forced = details.get("forced_reply", False)

    # 1-ply combination (mate-in-1)
    if climax_tactic == "mate" and len(chain) == 1:
        return f"You missed mate in 1: {chain[0]} ends the game."

    # 2-ply combination (best move + opp reply, climax is the opp reply
    # i.e., walking into mate)
    if climax_tactic == "mate" and len(chain) >= 2:
        # 3-or-more ply mate
        if len(chain) >= 3:
            return f"You missed a forced mate: {chain[0]} forces {chain[1]}, then {chain[2]} ends the game."
        return f"You missed a forced mate starting with {chain[0]}."

    # Fork at the climax (most common case — sacrificial forks etc.)
    if climax_tactic == "fork" and len(chain) >= 3:
        attacker = climax_details.get("attacker_piece", "piece")
        attacker_sq = climax_details.get("attacker_square", "")
        targets = climax_details.get("targets") or []
        is_check = climax_details.get("is_check_fork", False)
        first = chain[0]
        opp_reply = chain[1]
        climax_move = chain[2]

        force_word = "must play" if forced else "play"
        if is_check and targets:
            target_piece = targets[0].get("piece", "piece")
            target_sq = targets[0].get("square", "")
            tail = (
                f"Then {climax_move} forks the king and the {target_piece} on {target_sq}."
                if target_sq else
                f"Then {climax_move} forks the king and the {target_piece}."
            )
        elif len(targets) >= 2:
            t1 = targets[0].get("piece", "piece")
            t2 = targets[1].get("piece", "piece")
            tail = f"Then {climax_move} forks the {t1} and the {t2}."
        else:
            tail = f"Then {climax_move} wins material."
        return f"You missed {first}. They {force_word} {opp_reply}. {tail}"

    return None


def _render_walked_into_capture(details: Dict) -> Optional[str]:
    """User's just-moved piece is now hanging or in a losing trade."""
    piece = details.get("piece")
    sq = details.get("square")
    capture_san = details.get("capture_san")
    saving = details.get("saving_move")
    is_undef = details.get("is_undefended")
    if not piece or not sq:
        return None

    # Two flavours — undefended (hangs) or attacked-by-cheaper-piece.
    if is_undef:
        head = f"Your {piece} on {sq} has no defender."
    else:
        attacker = details.get("attacker_piece") or "piece"
        head = f"Your {piece} on {sq} is attacked by their {attacker} for less."

    if capture_san and saving:
        return f"{head} {capture_san} wins it. {saving} was safer."
    if capture_san:
        return f"{head} {capture_san} wins it."
    if saving:
        return f"{head} {saving} was safer."
    return head


def _render_walked_into_mate(details: Dict) -> Optional[str]:
    """User's move allowed forced mate against them."""
    mate_in = details.get("mate_in", 1)
    opp_move = details.get("opp_mate_move")
    saving_move = details.get("saving_move")
    if mate_in == 1 and opp_move and saving_move:
        return f"This allows mate. {opp_move} ends the game. {saving_move} was the only move that holds."
    if mate_in == 1 and opp_move:
        return f"This allows mate. {opp_move} ends the game."
    if saving_move:
        return f"This allows a forced mate. {saving_move} was the only move that holds."
    return "This allows a forced mate."


def _render_missed_discovery(details: Dict) -> Optional[str]:
    moving = details.get("moving_piece") or details.get("attacker")
    revealed = details.get("revealed_piece") or details.get("revealed")
    target = details.get("target") or details.get("target_piece")
    if not moving or not revealed:
        return None
    target_part = f" to win the {target}" if target else ""
    return (
        f"You missed a discovered attack: your {moving} moves and uncovers "
        f"the {revealed}{target_part}."
    )


def _render_walked_into_fork(details: Dict) -> Optional[str]:
    attacker = details.get("attacker")
    targets = details.get("targets") or []
    if not attacker:
        return None
    if len(targets) >= 2:
        return f"You walked into a fork: their {attacker} hits the {targets[0]} and the {targets[1]}."
    return f"You walked into a fork from their {attacker}."


def _render_walked_into_pin(details: Dict) -> Optional[str]:
    pinning = details.get("pinning_piece") or details.get("attacker")
    pinned = details.get("pinned_piece") or details.get("target")
    if not pinning or not pinned:
        return None
    return f"Their {pinning} pinned your {pinned}. You cannot move it without losing more behind."


def _render_missed_overload(details: Dict) -> Optional[str]:
    overloaded = details.get("overloaded_piece")
    if not overloaded:
        return None
    return (
        f"You missed an overload: their {overloaded} is doing two jobs. "
        f"Make it choose."
    )


def _render_missed_removal(details: Dict) -> Optional[str]:
    target = details.get("target_piece")
    defender = details.get("defender")
    if not target or not defender:
        return None
    return (
        f"You missed removing the defender: their {defender} guards the {target}. "
        f"Take the {defender}, and the {target} falls."
    )


def _render_pawn_race(details: Dict) -> Optional[str]:
    """Opponent's passed pawn races to promotion; user's king is outside
    the square-of-the-pawn."""
    sq = details.get("pawn_square")
    saving = details.get("saving_move")
    if not sq:
        return None
    head = f"Their pawn on {sq} runs to promotion. Your king is too far."
    if saving:
        return f"{head} {saving} catches it in time."
    return head


def _render_outside_passed_pawn(details: Dict) -> Optional[str]:
    outside = details.get("outside_passed") or []
    if outside:
        sq = (outside[0] or {}).get("square") if isinstance(outside[0], dict) else None
        if sq:
            return (
                f"Your passed pawn on {sq} pulls their king toward it. "
                f"Push it — your king cleans up on the other side."
            )
    return "Your passed pawn is the deciding piece. Push it."


def _render_opposition(details: Dict) -> Optional[str]:
    has_op = details.get("user_has_opposition")
    if has_op is True:
        return "You had the opposition. Their king must give way."
    if has_op is False:
        return "They had the opposition. Their king holds the key squares."
    return None


# Pattern type → renderer. Keys must match TacticalPattern /
# StrategicConcept enum values + advanced_detectors pattern_types.
_TEMPLATE_REGISTRY = {
    # Tactical — high priority, common at 600-1400
    "combination":        _render_combination,
    "hanging_piece":      _render_hanging_piece,
    "trapped_piece":      _render_trapped_piece,
    "missed_mate":        _render_missed_mate,
    "missed_fork":        _render_missed_fork,
    "missed_pin":         _render_missed_pin,
    "missed_skewer":      _render_missed_skewer,
    "missed_back_rank":   _render_missed_back_rank,
    "missed_discovery":   _render_missed_discovery,
    "walked_into_mate":   _render_walked_into_mate,
    "walked_into_capture": _render_walked_into_capture,
    "missed_overload":    _render_missed_overload,
    "missed_removal":     _render_missed_removal,
    "walked_into_fork":   _render_walked_into_fork,
    "walked_into_pin":    _render_walked_into_pin,
    # Strategic / endgame — added incrementally
    "outside_passed_pawn": _render_outside_passed_pawn,
    "pawn_race":          _render_pawn_race,
    "opposition":         _render_opposition,
}


def render_caption(pattern_type: str, details: Dict) -> Optional[str]:
    """Render a short caption for a detected pattern. Returns None when
    we have no template for this pattern_type or details are insufficient."""
    if not pattern_type:
        return None
    renderer = _TEMPLATE_REGISTRY.get(pattern_type)
    if renderer is None:
        return None
    try:
        return renderer(details or {})
    except Exception as e:
        logger.warning(f"[concept_templates] render failed for {pattern_type}: {e}")
        return None


def has_template(pattern_type: str) -> bool:
    """True if we can render a caption for this pattern_type."""
    return pattern_type in _TEMPLATE_REGISTRY
