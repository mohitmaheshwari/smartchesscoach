"""
Trap detection — did the user fall for or avoid a trap?

This detector identifies trap moments using the existing trap_recognition
system and grades whether the user fell for it or escaped it.

Decision logic:
    Pre-condition ("clean test"):
      - Move is within opening phase (move_number <= 20)
      - A trap is active in this line (trap_recognition identifies it)
      - User hasn't already fallen for the trap pre-move

    Grade:
      - User plays the trap victim line (falls for it)     → "missed"
      - User escapes the trap (plays a defense)           → "applied"
      - Position isn't a trap moment                       → None
"""
from __future__ import annotations

from typing import Optional
import chess
import logging

logger = logging.getLogger(__name__)


def detect_trap_application(
    board_before: chess.Board,
    move: chess.Move,
    user_color: chess.Color,
    move_number: Optional[int] = None,
) -> Optional[str]:
    """
    Detect if user fell for or avoided a trap.

    Returns:
      "missed" — User played the trap victim line (fell for it)
      "applied" — User escaped the trap (detected + avoided it)
      None — Not a trap moment or trap not identified
    """
    # Only check openings (first 20 moves)
    if move_number is None or move_number > 20:
        return None

    try:
        from services.trap_recognition import detect_trap_setup, match_trap_line_step

        if not detect_trap_setup or not match_trap_line_step:
            return None

        # Get the game history up to this move
        # This is a simplified check — in production, we'd need the full game history
        game_fen = board_before.fen()

        # Check if a trap is active
        # Detects if there's a known trap in this position
        trap_hit = detect_trap_setup(board_before)
        if not trap_hit:
            return None

        # We found a trap position. Now check if user's move escapes it or falls for it.
        # A "missed" grade means user played into the trap.
        # An "applied" grade means user saw the trap and avoided it.

        # Simple heuristic:
        # - If user's move is the trap victim move → "missed"
        # - If user's move is a known defense → "applied"
        # - Otherwise → None (don't grade)

        user_move_san = board_before.san(move)

        # Check trap line — if user plays the victim move, they fell for it
        if trap_hit.get("victim_move") and user_move_san == trap_hit.get("victim_move"):
            return "missed"  # User fell for the trap

        # Check if it's a known defense/escape
        if trap_hit.get("defense_moves") and user_move_san in trap_hit.get("defense_moves", []):
            return "applied"  # User saw and avoided the trap

        # Neutral move — not clearly falling for or avoiding
        return None

    except Exception as e:
        logger.debug(f"Trap detection failed: {e}")
        return None
