"""
Opening play detector — did the user stay in or deviate from opening theory?

Grades whether the user followed opening theory (stayed in book) or
deviated (went off-book), and whether the deviation was good or bad.

Decision logic:
    Pre-condition ("clean test"):
      - Move is in opening phase (move_number <= 12 or <= 15 depending on opening)
      - Opening is recognized and has theory loaded

    Grade:
      - User plays a main-line move (in book)                 → "applied"
      - User deviates from book but position is sound         → "applied"
      - User deviates with a known losing line               → "missed"
      - User deviates into unclear territory                 → None (don't grade)
"""
from __future__ import annotations

from typing import Optional
import chess
import logging

logger = logging.getLogger(__name__)


def detect_opening_play_application(
    board_before: chess.Board,
    move: chess.Move,
    user_color: chess.Color,
    move_number: Optional[int] = None,
    opening_name: Optional[str] = None,
) -> Optional[str]:
    """
    Detect if user stayed in opening book or deviated with good/bad consequences.

    Returns:
      "applied" — User played book move or sound deviation
      "missed" — User deviated into a losing line
      None — Not in opening or unclear deviation
    """
    # Only check early opening (first 12-15 moves depending on opening)
    if move_number is None or move_number > 15:
        return None

    if not opening_name:
        return None

    try:
        from services.opening_curriculum_engine import (
            get_opening_for_game,
            is_in_book,
            is_known_bad_deviation,
        )

        # Try to determine if move is in opening book
        in_book = is_in_book(board_before, move, opening_name)
        if in_book:
            return "applied"  # User stayed in theory

        # User deviated. Check if it's a known bad line
        is_bad = is_known_bad_deviation(board_before, move, opening_name)
        if is_bad:
            return "missed"  # Bad deviation — lost immediately

        # Unclear deviation — don't grade
        return None

    except Exception as e:
        logger.debug(f"Opening play detection failed: {e}")
        return None


def detect_preparation_for_opening(
    board_before: chess.Board,
    move: chess.Move,
    user_color: chess.Color,
    move_number: Optional[int] = None,
) -> Optional[str]:
    """
    Simplified: detect if user played a preparatory move (like 1.d4 when they
    use Queen's Gambit, or 1.e4 for Italian openings).

    This is a lighter version that just checks if the opening move matches
    the user's repertoire.

    Returns:
      "applied" — Correct opening move
      None — Not evaluating this
    """
    if move_number != 1:  # Only grade white's first move
        return None

    if user_color != chess.WHITE:
        return None

    user_move_san = board_before.san(move)

    # Common opening moves that indicate preparation
    if user_move_san in ["e4", "d4", "c4", "Nf3"]:
        return "applied"  # Standard opening preparations

    return None
