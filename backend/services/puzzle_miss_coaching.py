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
    "tactical_oversight": "Captures and checks first — they make moves forced.",
    "missed_tactic":      "Look for forks, pins, and skewers before quiet moves.",
    "calculation_depth":  "One move deeper. What does my move threaten next turn?",
    "ignore_threat":      "After my every move, ask: what changed? What am I now threatening?",
    "endgame_technique":  "In the endgame, your king is a fighting piece — use it.",
    "opening_knowledge":  "In the opening, develop pieces and fight for the center first.",
    "piece_activity":     "A piece that isn't doing anything is a wasted piece.",
    "pawn_structure":     "Every pawn move is permanent. Think before pushing.",
    "time_pressure":      "On a critical move, take the time you need — even if the clock is short.",
}

_GENERIC_TAKEAWAY = "Before every move, ask: what is my opponent threatening right now?"


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
) -> str:
    """Why does the user's move fall short? Compare threats before vs
    threats after. If the played move didn't address any of them, say so
    plainly. If it addressed some, name what's left.
    """
    if not played_san:
        return ""
    if not threats_before:
        # No active threats — user's move just wasn't the strongest.
        return f"Your {played_san} doesn't lose anything, but there's a stronger move."

    # If we have a UCI, compute threats after to see what was addressed.
    if played_uci:
        try:
            played_move = chess.Move.from_uci(played_uci)
        except Exception:
            played_move = None
        if played_move and played_move in board_before.legal_moves:
            after = board_before.copy()
            after.push(played_move)
            # Now opponent to move — check threats AGAINST the user that
            # opponent could still execute.
            after.turn = not after.turn  # null-move flip back to user side
            threats_after = _opponent_threats(after)
            if not threats_after:
                return f"{played_san} addresses the immediate threat but there's a stronger move."
            if len(threats_after) < len(threats_before):
                return (
                    f"{played_san} handles part of it, but a threat is still "
                    f"there: {threats_after[0]}"
                )
            return (
                f"{played_san} doesn't address the threat — "
                f"{threats_before[0].lstrip('My ').rstrip('.')}, still."
            )

    return f"{played_san} doesn't address what's threatening you right now."


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
) -> Optional[Dict]:
    """Build the full coaching breakdown for a puzzle miss. Returns None
    when the FEN can't be parsed — caller should fall back to a simpler
    panel.
    """
    if not fen_before or not best_move_san:
        return None
    try:
        board = chess.Board(fen_before)
    except Exception:
        return None

    pv_after_best = pv_after_best or []

    position_summary = _build_position_summary(board)
    threats = _opponent_threats(board)
    played_critique = _critique_played_move(
        board, played_move_uci, played_move_san, threats
    )

    # Best-move idea — use the existing tactical analyzer.
    best_move_idea = ""
    if best_move_uci:
        try:
            from services.pv_tactical_analyzer import explain_best_move_tactically
            best_move_idea = explain_best_move_tactically(
                fen_before, best_move_uci, best_move_san, pv_after_best,
            ) or ""
        except Exception as e:
            logger.debug(f"pv_tactical_analyzer failed: {e}")

    if not best_move_idea:
        # Falls back to a plain "the engine prefers X" — honest about
        # not having a tactical signal rather than fabricating one.
        best_move_idea = (
            f"{best_move_san} is stronger here. The engine sees a small "
            f"advantage that's hard to explain in one line — play through "
            f"the move on the board to feel it."
        )

    takeaway = (
        _GAP_TAKEAWAY.get(cognitive_gap, _GENERIC_TAKEAWAY)
        if cognitive_gap else _GENERIC_TAKEAWAY
    )

    return {
        "position_summary": position_summary,
        "opponent_threats": threats,
        "played_critique": played_critique,
        "best_move_idea": best_move_idea,
        "best_move_san": best_move_san,
        "played_move_san": played_move_san,
        "takeaway": takeaway,
    }
