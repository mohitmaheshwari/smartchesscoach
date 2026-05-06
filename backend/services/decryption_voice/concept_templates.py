"""
Caption templates per chess concept.

Voice goal: every caption reads like a coach speaking to a 1200-rated
player, not like Stockfish output. Don't paste SAN tokens (Kxh7, Qh5+)
into prose. Translate each move into a plain phrase ('you take with
the king', 'their queen comes to h5 with check'). SAN is fine for the
SAVING move (short, clear, the one move worth remembering) but not for
narrating an opponent's forcing line.

Each detector in services/chess_brain/detector_registry.py +
advanced_detectors.py returns a DetectorResult with structured facts.
This module turns those facts into short coaching captions in locked
Indian English voice. No LLM. No hallucination. Every word comes from
the deterministic detector output or a template constant.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

import chess

logger = logging.getLogger(__name__)


_PIECE_NAME = {
    chess.PAWN: "pawn",
    chess.KNIGHT: "knight",
    chess.BISHOP: "bishop",
    chess.ROOK: "rook",
    chess.QUEEN: "queen",
    chess.KING: "king",
}


def _humanize_move(
    board_before: chess.Board,
    san: str,
    user_color: chess.Color,
) -> str:
    """Render one SAN move as a short plain-English phrase from the
    user's perspective. 'their queen comes to h5 with check', 'you
    take with the king', etc. Falls back to the raw SAN if parsing
    fails — caller can still ship something readable.
    """
    try:
        m = board_before.parse_san(san)
        moving = board_before.piece_at(m.from_square)
        if not moving:
            return san
    except Exception:
        return san

    is_user = (moving.color == user_color)
    side_poss = "your" if is_user else "their"
    piece = _PIECE_NAME.get(moving.piece_type, "piece")
    to_sq = chess.square_name(m.to_square)

    # Detect check/mate after the move.
    after = board_before.copy()
    is_capture = board_before.is_capture(m)
    captured_name = None
    if is_capture:
        if board_before.is_en_passant(m):
            captured_name = "pawn"
        else:
            cap_p = board_before.piece_at(m.to_square)
            if cap_p:
                captured_name = _PIECE_NAME.get(cap_p.piece_type, "piece")
    after.push(m)
    if after.is_checkmate():
        suffix = ", mate"
    elif after.is_check():
        suffix = " with check"
    else:
        suffix = ""

    # King recapture phrasing — common in sacrifice lines, deserves the
    # natural 'you take with the king' rendering.
    if is_capture and moving.piece_type == chess.KING and is_user:
        return f"you take with the king{suffix}"
    if is_capture and moving.piece_type == chess.KING and not is_user:
        return f"their king takes{suffix}"

    if is_capture:
        cap = captured_name or "piece"
        return f"{side_poss} {piece} takes the {cap} on {to_sq}{suffix}"

    return f"{side_poss} {piece} comes to {to_sq}{suffix}"


def _humanize_chain(
    fen_before: str,
    chain_san: List[str],
    user_color_name: str,
) -> List[str]:
    """Walk a SAN chain from fen_before, return one humanized phrase
    per move. Skips entries that fail to parse."""
    out: List[str] = []
    user_color = chess.WHITE if (user_color_name or "").lower() == "white" else chess.BLACK
    try:
        board = chess.Board(fen_before)
    except Exception:
        return [s for s in chain_san]
    for san in chain_san:
        out.append(_humanize_move(board, san, user_color))
        try:
            m = board.parse_san(san)
            board.push(m)
        except Exception:
            break
    return out


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
    """Render the PV-walked combination chain.

    Voice rule: keep SAN for the moves the player should REMEMBER —
    the missed move (chain[0]) and the climax move (chain[2]) — but
    humanize the opp's forced reply in between (chain[1]) so it reads
    like a coach explaining the line, not Stockfish PV.
    """
    chain = details.get("chain") or []
    if not chain:
        return None
    climax_tactic = details.get("climax_tactic")
    climax_details = details.get("climax_details") or {}
    forced = details.get("forced_reply", False)
    fen_before = details.get("fen_before")
    user_color_name = details.get("user_color")

    # 1-ply combination (mate-in-1)
    if climax_tactic == "mate" and len(chain) == 1:
        return f"You missed mate in 1: {chain[0]} ends the game."

    # 2+-ply mate sequence
    if climax_tactic == "mate" and len(chain) >= 2:
        if len(chain) >= 3:
            return f"You missed a forced mate: {chain[0]} forces the line, ending with {chain[2]}."
        return f"You missed a forced mate starting with {chain[0]}."

    # Fork at the climax (most common case — sacrificial forks etc.)
    if climax_tactic == "fork" and len(chain) >= 3:
        attacker = climax_details.get("attacker_piece", "piece")
        targets = climax_details.get("targets") or []
        is_check = climax_details.get("is_check_fork", False)
        first = chain[0]
        opp_reply_san = chain[1]
        climax_move = chain[2]

        # Humanize opp's reply ('their king takes', 'they have to take').
        opp_reply_phrase = opp_reply_san
        if fen_before and user_color_name:
            try:
                humanized = _humanize_chain(fen_before, chain[:2], user_color_name)
                if len(humanized) > 1:
                    opp_reply_phrase = humanized[1]
            except Exception:
                pass

        # If the reply is strictly forced, state it as fact. Otherwise
        # use 'If they...' framing — the engine's best reply isn't the
        # only legal one and we shouldn't overstate it. Critical for
        # honest coaching: a 1200 player who plays Bxf7+ might face Kf8
        # or Ke7 instead, and the line becomes different.
        if forced:
            mid = f"Their reply is forced — {opp_reply_phrase}."
        else:
            # 'their king takes' → 'if their king takes'
            mid = f"If {opp_reply_phrase},"

        if is_check and targets:
            target_piece = targets[0].get("piece", "piece")
            target_sq = targets[0].get("square", "")
            tail_core = (
                f"{climax_move} forks the king and the {target_piece} on {target_sq}"
                if target_sq else
                f"{climax_move} forks the king and the {target_piece}"
            )
        elif len(targets) >= 2:
            t1 = targets[0].get("piece", "piece")
            t2 = targets[1].get("piece", "piece")
            tail_core = f"{climax_move} forks the {t1} and the {t2}"
        else:
            tail_core = f"{climax_move} wins material"

        # Join mid + tail. If mid ends with comma (the 'If they take,'
        # variant) the tail flows directly. Otherwise tail starts a new
        # sentence with 'Then {climax}.'
        if forced:
            return f"You missed {first}. {mid} Then {tail_core}."
        else:
            return f"You missed {first}. {mid} {tail_core}."

    return None


def _render_walked_into_attack(details: Dict) -> Optional[str]:
    """Opp's tactical sequence after user's wrong move (Greek Gift etc).

    Voice rule: don't paste SAN tokens (Kxh7, Qh5+) into prose — these
    read like Stockfish to a 1200 player. Translate each move into a
    short plain phrase via _humanize_chain. SAN is kept ONLY for the
    saving move (short, clear, the one move worth remembering).

    Structure:
      Sentence 1 — the threat: 'Their {piece} was coming to {square}.'
      Sentence 2 — the forced trade(s): 'After [humanized line],'
      Sentence 3 — the climax: 'their {piece} {forks/wins} your {x}.'
      Sentence 4 — the defense: '{saving_move} prevents it.'
    """
    chain = details.get("chain") or []
    fen_before = details.get("fen_before")  # may be missing
    user_color_name = details.get("user_color")  # may be missing
    saving = details.get("saving_move")
    climax_tactic = details.get("climax_tactic")
    climax_details = details.get("climax_details") or {}
    if len(chain) < 2:
        return None

    # Try to humanize the chain. If we don't have FEN/color, fall back
    # to the SAN tokens (still readable, less natural).
    humanized: List[str] = []
    if fen_before and user_color_name:
        try:
            humanized = _humanize_chain(fen_before, chain, user_color_name)
        except Exception:
            humanized = []
    if not humanized:
        humanized = chain

    # Sentence 1 — the threat (chain[1] is opp's first move).
    threat_phrase = humanized[1] if len(humanized) > 1 else chain[1]
    s1 = threat_phrase[:1].upper() + threat_phrase[1:] + "."

    # Sentence 2 — the user's first forced response merged with what
    # opp wins. We skip describing intermediate forcing moves (Qh5+
    # Kg8 etc.) — for a 1200 player, the threat + climax is what
    # matters; the middle ply is implicit in 'ends up'.
    first_forced = humanized[2] if len(humanized) > 2 else ""
    tail_clause = ""
    if climax_tactic == "mate":
        tail_clause = "their attack ends in mate"
    elif climax_tactic == "fork":
        attacker = climax_details.get("attacker_piece", "piece")
        targets = climax_details.get("targets") or []
        if targets and climax_details.get("is_check_fork"):
            t0 = targets[0]
            piece = t0.get("piece", "piece")
            sq = t0.get("square", "")
            tail_clause = (
                f"their {attacker} ends up forking your king and your {piece} on {sq}"
                if sq else f"their {attacker} ends up forking your king and your {piece}"
            )
        elif len(targets) >= 2:
            t1 = targets[0].get("piece", "piece")
            t2 = targets[1].get("piece", "piece")
            tail_clause = f"their {attacker} ends up forking your {t1} and your {t2}"

    if first_forced and tail_clause:
        # Capitalize the first forced response and join with 'and'
        ff = first_forced[:1].upper() + first_forced[1:]
        s2 = f"{ff}, and {tail_clause}."
    elif tail_clause:
        s2 = tail_clause[:1].upper() + tail_clause[1:] + "."
    elif first_forced:
        s2 = first_forced[:1].upper() + first_forced[1:] + ", and you lose material."
    else:
        s2 = "You lose material."

    out_parts = [s1, s2]
    if saving:
        out_parts.append(f"{saving} prevents it.")
    return " ".join(out_parts)


def _render_missed_attack_on_high_value(details: Dict) -> Optional[str]:
    """Best move attacks a heavier enemy piece without capturing."""
    best = details.get("best_move")
    target = details.get("target_piece")
    sq = details.get("target_square")
    if not best or not target:
        return None
    if sq:
        return f"{best} attacks their {target} on {sq}. They have to move it, and you gain time."
    return f"{best} attacks their {target}. They have to move it, and you gain time."


def _render_missed_check(details: Dict) -> Optional[str]:
    """Best move was a check; user played a non-check."""
    best = details.get("best_move")
    sides = details.get("side_attacks") or []
    if not best:
        return None
    if sides:
        top = sides[0]
        piece = top.get("piece", "piece")
        sq = top.get("square", "")
        if sq:
            return f"{best} was the move. The check also attacks the {piece} on {sq}."
        return f"{best} was the move. The check also attacks the {piece}."
    return f"{best} was the move. The check forces them to respond first."


def _render_missed_castle(details: Dict) -> Optional[str]:
    best = details.get("best_move")
    side = details.get("side", "kingside")
    if not best:
        return None
    return f"{best} was the move. Castling {side} takes your king out of the centre."


def _render_missed_capture(details: Dict) -> Optional[str]:
    best = details.get("best_move")
    cap = details.get("captured_piece")
    sq = details.get("captured_square")
    free = details.get("free", False)
    if not best or not cap:
        return None
    if free:
        return f"{best} wins the {cap} on {sq}. It has no defender."
    return f"{best} wins the {cap} on {sq}."


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
    "walked_into_attack": _render_walked_into_attack,
    "missed_attack_on_high_value": _render_missed_attack_on_high_value,
    "missed_check":       _render_missed_check,
    "missed_castle":      _render_missed_castle,
    "missed_capture":     _render_missed_capture,
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
