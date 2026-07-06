"""
Puzzle Miss Coaching
====================

When a user fails a prescribed-training puzzle, "h3 (you played) ·
d3 (solution)" + a fortune-cookie quote isn't coaching — it's
chess.com-style pass/fail. This service builds a structured coaching
breakdown for that moment, grounded in the position rather than
generic platitudes.

Output is fully deterministic — no LLM, no fabrication. Pieces:

  position_summary    coach-voice line on what's on the board
  opponent_threats    list of concrete threats from opponent's pieces
  played_critique     why the user's move falls short on the actual threat
  best_move_idea      why the best move wins (from pv_tactical_analyzer)
  takeaway            one-liner tied to the user's diagnosed gap

Quality bar: position_summary + opponent_threats + best_move_idea
are all sourced from board state and verified analyzers. Where we
don't have a clean idea to teach (e.g., subtle positional moves with
no PV pattern), we say so — never fake it.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

import chess

logger = logging.getLogger(__name__)


# Per-gap one-line lesson takeaways. Maps to canonical CLAUDE.md
# cognitive_gap names. When the puzzle's gap doesn't match, falls
# through to a generic "always check" line.
_GAP_TAKEAWAY = {
    "piece_safety":       "Before every move, ask: is each of my pieces defended?",
    "king_safety":        "Watch what my pieces are aiming at near your king. King first.",
    "tactical_oversight": "Captures and checks first — those are the forcing moves.",
    "missed_tactic":      "Look for forks, pins, and skewers before quiet moves.",
    "calculation_depth":  "One move deeper. What does my move threaten next turn?",
    "ignore_threat":      "After every move I make, ask: what changed? What am I now threatening?",
    "endgame_technique":  "In the endgame, your king is a fighting piece — use it.",
    "opening_knowledge":  "In the opening, develop pieces and fight for the center first.",
    "piece_activity":     "A piece that isn't doing anything is a wasted piece.",
    "pawn_structure":     "Every pawn move is permanent. Think before pushing.",
    "time_pressure":      "On a critical move, take the time you need — even if the clock is short.",
}

_GENERIC_TAKEAWAY = "Before every move, ask: what is my opponent threatening right now?"
# Offensive puzzles (you were meant to WIN material / land a tactic) get an
# attacking lesson, not the defensive "watch their threats" line. 2026-06-23.
_GENERIC_TAKEAWAY_OFFENSE = (
    "Before a quiet move, scan for loose enemy pieces and forcing moves — "
    "a capture or double attack may be waiting."
)


# Lichess theme groups. When the puzzle's role is clear, we frame the
# coaching around what the USER was supposed to do rather than "you
# didn't address the threat." A fork puzzle's lesson is "find the fork,"
# not "defend it."
_OFFENSIVE_THEMES = {
    "fork", "doubleAttack", "hangingPiece", "advantage", "crushing",
    "pin", "skewer", "discoveredAttack", "discoveredCheck",
    "doubleCheck", "deflection", "removeTheDefender", "attraction",
    "interference", "xRayAttack", "trappedPiece",
    "mate", "mateIn1", "mateIn2", "mateIn3", "mateIn4", "mateIn5",
    "kingsideAttack", "queensideAttack", "attackingF2F7",
    "backRankMate", "smotheredMate", "anastasiaMate", "arabianMate",
    "bodenMate", "doubleBishopMate", "dovetailMate", "hookMate",
    "sacrifice", "clearance", "intermezzo", "quietMove",
}
_DEFENSIVE_THEMES = {"defensiveMove", "exposedKing"}

# Pretty names for theme → coach voice headline. Lets us say "you missed
# the fork" instead of "there's a stronger move."
_THEME_NAMES = {
    "fork":              "fork",
    "pin":               "pin",
    "skewer":            "skewer",
    "discoveredAttack":  "discovered attack",
    "discoveredCheck":   "discovered check",
    "doubleCheck":       "double check",
    "deflection":        "deflection",
    "removeTheDefender": "remove-the-defender tactic",
    "attraction":        "attraction tactic",
    "interference":      "interference",
    "xRayAttack":        "x-ray attack",
    "trappedPiece":      "trapped piece",
    "mateIn1":           "mate in 1",
    "mateIn2":           "mate in 2",
    "mateIn3":           "mate in 3",
    "mateIn4":           "mate in 4",
    "mateIn5":           "mate in 5",
    "mate":              "checkmate",
    "kingsideAttack":    "kingside attack",
    "queensideAttack":   "queenside attack",
    "attackingF2F7":     "f7/f2 attack",
    "backRankMate":      "back-rank mate",
    "smotheredMate":     "smothered mate",
    "sacrifice":         "sacrifice",
    "clearance":         "clearance",
    "intermezzo":        "in-between move",
    "quietMove":         "quiet move",
    "hangingPiece":      "free piece to grab",
}


def _puzzle_role(themes: List[str]) -> str:
    """Return 'attacker', 'defender', or 'unclear' based on themes."""
    theme_set = set(themes or [])
    if theme_set & _OFFENSIVE_THEMES:
        return "attacker"
    if theme_set & _DEFENSIVE_THEMES:
        return "defender"
    return "unclear"


def _primary_theme_name(themes: List[str]) -> Optional[str]:
    """Pick the most teaching-friendly theme to name in coach voice."""
    if not themes:
        return None
    # Prefer specific patterns over generic descriptors
    priority = [
        "mateIn1", "mateIn2", "mateIn3", "mateIn4", "mateIn5", "mate",
        "fork", "pin", "skewer", "discoveredCheck", "discoveredAttack",
        "doubleCheck", "deflection", "removeTheDefender", "attraction",
        "interference", "xRayAttack", "trappedPiece", "hangingPiece",
        "smotheredMate", "backRankMate", "sacrifice", "intermezzo",
        "quietMove", "kingsideAttack", "queensideAttack", "attackingF2F7",
    ]
    for t in priority:
        if t in themes:
            return _THEME_NAMES.get(t)
    return None


# ──────────────────────────────────────────────────────────────
# Position summary
# ──────────────────────────────────────────────────────────────

_PIECE_NAMES = {
    chess.PAWN: "pawn", chess.KNIGHT: "knight", chess.BISHOP: "bishop",
    chess.ROOK: "rook", chess.QUEEN: "queen", chess.KING: "king",
}
_PIECE_VALUES = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3,
                 chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 0}


def _material_for(board: chess.Board, color: chess.Color) -> int:
    return sum(
        _PIECE_VALUES[p.piece_type]
        for sq, p in board.piece_map().items()
        if p.color == color and p.piece_type != chess.KING
    )


def _build_position_summary(board: chess.Board) -> str:
    """One-line coach voice description of the board state."""
    user_color = board.turn  # The side TO MOVE is the user (puzzle convention)
    opp_color = not user_color
    user_mat = _material_for(board, user_color)
    opp_mat = _material_for(board, opp_color)

    # Material framing — in coach voice, never "advantage 1.5"
    if user_mat == opp_mat:
        material_line = "Material's equal."
    elif user_mat > opp_mat:
        diff = user_mat - opp_mat
        material_line = (
            f"You're up a pawn." if diff <= 1
            else f"You've got an extra piece."
        )
    else:
        diff = opp_mat - user_mat
        material_line = (
            f"You're down a pawn." if diff <= 1
            else f"I've got an extra piece."
        )

    # Piece-development hint (early phase only)
    fullmove = board.fullmove_number
    if fullmove <= 12:
        # Count developed minor pieces (knights/bishops off the back rank)
        back_rank = 0 if user_color == chess.WHITE else 7
        undeveloped = 0
        for sq, p in board.piece_map().items():
            if (
                p.color == user_color
                and p.piece_type in (chess.KNIGHT, chess.BISHOP)
                and chess.square_rank(sq) == back_rank
            ):
                undeveloped += 1
        if undeveloped >= 2:
            return f"{material_line} You've still got pieces sitting on the back rank."

    return material_line


# ──────────────────────────────────────────────────────────────
# Opponent threats
# ──────────────────────────────────────────────────────────────

def _opponent_threats(board: chess.Board) -> List[str]:
    """Return short coach-voice descriptions of what the opponent is
    threatening from the side-to-move's perspective. Uses a hypothetical
    null-move (give opponent a free move) to detect threats they could
    cash in.
    """
    threats: List[str] = []
    user_color = board.turn

    # 1. Are we in check? That's the dominant threat.
    if board.is_check():
        threats.append("My pieces have your king in check.")
        return threats

    # 2. Pieces of ours that the opponent attacks. We look at squares
    #    the opponent already attacks where one of our non-king pieces
    #    sits. Filter to "real" threats: opponent's cheapest attacker
    #    is worth strictly less than the victim, OR victim is undefended.
    opp_color = not user_color
    seen_pieces = set()
    for sq, piece in board.piece_map().items():
        if piece.color != user_color or piece.piece_type == chess.KING:
            continue
        attackers = board.attackers(opp_color, sq)
        if not attackers:
            continue
        defenders = board.attackers(user_color, sq)

        victim_value = _PIECE_VALUES.get(piece.piece_type, 0)
        cheapest_attacker = min(
            (_PIECE_VALUES.get(board.piece_at(a).piece_type, 0) for a in attackers),
            default=0,
        )
        is_real_threat = (not defenders) or (cheapest_attacker < victim_value)
        if not is_real_threat:
            continue
        # Pick a representative attacker (cheapest) to name in the line
        cheapest_attacker_sq = min(
            attackers,
            key=lambda a: _PIECE_VALUES.get(board.piece_at(a).piece_type, 0),
        )
        attacker_piece = board.piece_at(cheapest_attacker_sq)
        attacker_name = _PIECE_NAMES.get(attacker_piece.piece_type, "piece")
        victim_name = _PIECE_NAMES.get(piece.piece_type, "piece")
        sq_name = chess.square_name(sq)
        threat_key = (victim_name, sq_name)
        if threat_key in seen_pieces:
            continue
        seen_pieces.add(threat_key)
        threats.append(
            f"My {attacker_name} is aiming at your {victim_name} on {sq_name}."
        )
        if len(threats) >= 3:
            break

    return threats


# ──────────────────────────────────────────────────────────────
# Played-move critique
# ──────────────────────────────────────────────────────────────

def _critique_played_move(
    board_before: chess.Board,
    played_uci: Optional[str],
    played_san: str,
    threats_before: List[str],
    role: str,
    theme_name: Optional[str],
    best_san: str,
) -> str:
    """Why does the user's move fall short?

    Framing depends on the puzzle's role:
      • attacker — user was supposed to FIND a tactic. Frame as "you
        missed the [theme]" with the best move named. Don't talk about
        "addressing threats" because that's the wrong direction.
      • defender — user was supposed to handle a threat. Use threat
        comparison: did their move address it, partially, or not.
      • unclear — generic "there's a stronger move" fallback, but with
        the best move named so it isn't empty advice.
    """
    if not played_san:
        return ""

    # ── Attacker puzzle ──
    if role == "attacker":
        if theme_name:
            return (
                f"You missed the {theme_name}. {best_san} was the move."
            )
        return f"You missed the tactic. {best_san} was the move."

    # ── Defender / threat-driven puzzle ──
    if role == "defender" and threats_before and played_uci:
        try:
            played_move = chess.Move.from_uci(played_uci)
        except Exception:
            played_move = None
        if played_move and played_move in board_before.legal_moves:
            after = board_before.copy()
            after.push(played_move)
            after.turn = not after.turn  # null-flip: see threats from opponent
            threats_after = _opponent_threats(after)
            if not threats_after:
                return (
                    f"{played_san} stops the threat — but {best_san} was "
                    f"the cleaner answer."
                )
            if len(threats_after) < len(threats_before):
                return (
                    f"{played_san} handles part of it. There's still: "
                    f"{threats_after[0]}"
                )
            # Didn't address it
            threat_text = threats_before[0]
            # Strip leading "My " so it reads naturally after the dash
            if threat_text.startswith("My "):
                threat_text = threat_text[3:]
            return (
                f"{played_san} doesn't stop it — {threat_text.rstrip('.')} is still on."
            )

    # ── Unclear / no threat ──
    # No dodge ("try it to feel why"): point to the better move plainly. The
    # WHY-THE-BEST-MOVE-WORKS box carries the verified reason. 2026-06-23.
    return f"{best_san} was the stronger move here."


# ──────────────────────────────────────────────────────────────
# Best-move idea — VERIFIED via the central caption layer
# ──────────────────────────────────────────────────────────────

def _verified_best_move_idea(
    board: chess.Board, best_move: chess.Move, best_san: str
) -> Optional[str]:
    """Why the SOLUTION move works — board-verified, single-source.

    Teachable-caption framework (docs/teachable_caption_framework_scope.md): the
    puzzle surface used to call pv_tactical_analyzer, which FABRICATED narratives
    (e.g. "Qxb2 forces the defender to move" on a free-bishop win). This routes the
    explanation through the central why function (`_recommended_move_why`) — every
    claim is true by construction. Returns None to ABSTAIN (caller renders a safe
    terse line) rather than invent. No LLM, no fabrication.
    """
    try:
        from services.caption_facts import (
            _recommended_move_why, static_exchange_eval,
            PIECE_TYPE_NAMES, PIECE_VALUE_CP,
        )
    except Exception:
        return None
    try:
        mover = board.turn
        enemy = not mover
        after = board.copy()
        after.push(best_move)
        # Double-attack enrichment: the move lands the piece where it ALSO
        # attacks a second enemy piece that's undefended or worth more — the
        # "double attack" lesson. Board-verified.
        my_val = PIECE_VALUE_CP.get(board.piece_at(best_move.from_square).piece_type, 0)
        second = None
        for sq in after.attacks(best_move.to_square):
            p = after.piece_at(sq)
            if not p or p.color != enemy or p.piece_type == chess.KING:
                continue
            if sq == best_move.to_square:
                continue
            val = PIECE_VALUE_CP.get(p.piece_type, 0)
            if (not after.attackers(enemy, sq)) or val > my_val:
                if second is None or val > second[1]:
                    second = (PIECE_TYPE_NAMES.get(p.piece_type, "piece"), val,
                              chess.square_name(sq))

        if board.is_capture(best_move):
            if board.is_en_passant(best_move):
                cap_name = "pawn"
            else:
                cp = board.piece_at(best_move.to_square)
                cap_name = PIECE_TYPE_NAMES.get(cp.piece_type, "piece") if cp else "piece"
            see = static_exchange_eval(board, best_move.to_square, mover) or 0
            verb = "wins" if see >= 100 else "takes"
            if second is not None:
                return (f"{best_san} {verb} the {cap_name}, and the {second[0]} on "
                        f"{second[2]} falls next — a double attack, two targets at once.")
            return f"{best_san} {verb} the {cap_name}."

        # Non-capture: a quiet move that creates a second-target threat.
        if second is not None:
            return (f"{best_san} hits the {second[0]} on {second[2]} — and the threat "
                    f"can't be met without giving something up.")

        # Otherwise lean on the single-source why (threat/escape/defend/castle/principle).
        why = _recommended_move_why(board, best_move)
        if why:
            return f"{best_san} — it {why}."
    except Exception:
        return None
    return None  # abstain — caller renders a safe terse line


# ──────────────────────────────────────────────────────────────
# Top-level
# ──────────────────────────────────────────────────────────────

def build_miss_coaching(
    fen_before: str,
    played_move_san: str,
    best_move_san: str,
    best_move_uci: str,
    *,
    played_move_uci: Optional[str] = None,
    pv_after_best: Optional[List[str]] = None,
    cognitive_gap: Optional[str] = None,
    themes: Optional[List[str]] = None,
    found: bool = False,
) -> Optional[Dict]:
    """Build the full coaching breakdown for a puzzle miss. Returns None
    when the FEN can't be parsed — caller should fall back to a simpler
    panel.

    `themes`: Lichess puzzle themes when available — drives critique
    framing (attacker vs defender vs unclear). When the user is the
    ATTACKER (fork/pin/skewer/mate), we frame "you missed the X" rather
    than "you didn't address the threat" (which is wrong direction).
    """
    if not fen_before or not best_move_san:
        return None
    try:
        board = chess.Board(fen_before)
    except Exception:
        return None

    pv_after_best = pv_after_best or []
    themes = themes or []
    role = _puzzle_role(themes)
    theme_name = _primary_theme_name(themes)

    position_summary = _build_position_summary(board)
    threats = _opponent_threats(board)
    played_critique = _critique_played_move(
        board, played_move_uci, played_move_san, threats,
        role=role, theme_name=theme_name, best_san=best_move_san,
    )

    # Best-move idea — VERIFIED via the central why layer (no fabrication).
    # Replaces pv_tactical_analyzer, which hallucinated tactical narratives
    # (docs/teachable_caption_framework_scope.md). Every claim is board-true.
    _best_mv = None
    if best_move_uci:
        try:
            _best_mv = chess.Move.from_uci(best_move_uci)
        except Exception:
            _best_mv = None
    if _best_mv is None:
        try:
            _best_mv = board.parse_san(best_move_san)
        except Exception:
            _best_mv = None

    best_move_idea = ""
    if _best_mv is not None and _best_mv in board.legal_moves:
        best_move_idea = _verified_best_move_idea(board, _best_mv, best_move_san) or ""
    if not best_move_idea:
        # Honest abstain — name the move, never fabricate, never "feel why".
        best_move_idea = f"{best_move_san} is the strongest move here."

    # Takeaway — match the puzzle's direction. An OFFENSIVE puzzle (the solution
    # wins material / lands a tactic) must not get the defensive "watch their
    # threats" line. Prefer a fitting gap takeaway; else split by role.
    if cognitive_gap and cognitive_gap in _GAP_TAKEAWAY:
        takeaway = _GAP_TAKEAWAY[cognitive_gap]
    elif role == "attacker" or (_best_mv is not None and board.is_capture(_best_mv)):
        takeaway = _GENERIC_TAKEAWAY_OFFENSE
    else:
        takeaway = _GENERIC_TAKEAWAY

    # Single concise teaching line for the card — names the pattern (when the
    # role is clear) then the verified why, so the UI shows ONE studiable line
    # instead of stacked "falls short" / "why best" boxes. The card was too long
    # and internally contradictory; the lesson is the one thing to remember.
    #
    # `found`: the user PLAYED the best move (a solve). Reinforce WHAT they found
    # with the same verified idea — a correct solve should teach too, not just
    # say "You found it." (Mohit 2026-07-06.) No critique on a correct move.
    if found:
        played_critique = ""
        if role == "attacker" and theme_name:
            lesson = f"You found the {theme_name}! {best_move_idea}"
        else:
            lesson = f"Nice — {best_move_idea}"
    elif role == "attacker" and theme_name:
        lesson = f"You missed the {theme_name}. {best_move_idea}"
    else:
        lesson = best_move_idea

    return {
        "position_summary": position_summary,
        "opponent_threats": threats,
        "played_critique": played_critique,
        "best_move_idea": best_move_idea,
        "lesson": lesson,
        "best_move_san": best_move_san,
        "played_move_san": played_move_san,
        "takeaway": takeaway,
        "role": role,
        "theme_name": theme_name,
    }
