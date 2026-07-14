"""opening_deviation_detector.py — Detect opening deviations.

Opening understanding = knowing whether you're following theory or deviating,
and if deviating, understanding why it might be sound or unsound.

At launch, we DETECT deviations but DO NOT judge sound/unsound (too risky).
That comes in P2.

RATING-AWARE: 1100+ players get opening context. Below that, less emphasis.
"""

import chess
from typing import Dict, Optional, List


def detect_opening_deviation(move_history: List[str], fen_before: str, move_san: str) -> Optional[Dict]:
    """
    Detect if a move deviates from standard opening theory.

    Returns: {
        "is_deviation": bool,
        "opening_name": str,
        "mainline_move": str,
        "confidence": float
    } or None
    """

    # This is a stub for opening book integration
    # In real implementation, would check against opening_curriculum.json
    # and opening_book.recognize_opening_from_history()

    # For now: return None (no deviation detected)
    # Will implement full opening tracking in Phase 2
    return None


def count_opening_deviations(game_pgn: str) -> int:
    """Count how many deviations from theory in a game."""

    # Parse PGN and count deviations
    # At launch threshold: >= 3 deviations = surface card

    # Stub: return 0 (no detections yet)
    return 0


def opening_deviation_significant(deviation_count: int) -> bool:
    """Check if deviation count meets surface threshold (>= 3)."""
    return deviation_count >= 3
