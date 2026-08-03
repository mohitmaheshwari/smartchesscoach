"""
Opening play detector — did the user stay in curriculum book, where
curriculum coverage actually exists?

Rewritten 2026-08-03. The original imported `get_opening_for_game`,
`is_in_book`, `is_known_bad_deviation` from `opening_curriculum_engine.py`
— none of the three exist anywhere in that file (confirmed: the module
only exports `get_available_openings`, `get_opening_guidance`,
`get_opening_summary`), so the import always raised and the broad
`except Exception` swallowed it silently every time.

Real, honest scope of what's gradable with the data that actually
exists:
  - `get_opening_guidance(opening_key, moves_played, user_color,
    assessment)` walks `opening_curriculum.json`'s move tree following
    `moves_played` and returns `is_in_book=True` only if every move in
    the sequence matched the tree. Passing the FULL history (including
    this move) and checking `is_in_book` tells us whether THIS move
    specifically stayed in book — "applied".
  - There is NO "known bad deviation" concept anywhere in this data
    model. `_off_book_guidance()` (the function that runs the moment a
    move leaves the tree) treats every deviation identically and
    neutrally ("That's off the main line — but that's OK") — there is
    no field distinguishing a sound deviation from a losing one. The
    original docstring's "missed — known losing line" case was always
    aspirational, not backed by real data. Grading it would be a guess,
    not a fact, so this now returns None (no grade) on any deviation,
    same honest-silence choice as trap_detection.py's un-gradable cases.
"""
from __future__ import annotations

from typing import List, Optional
import chess
import logging

logger = logging.getLogger(__name__)


def detect_opening_play_application(
    board_before: chess.Board,
    move: chess.Move,
    user_color: chess.Color,
    move_number: Optional[int] = None,
    opening_name: Optional[object] = None,
    move_history_san: Optional[List[str]] = None,
) -> Optional[str]:
    """
    Detect if the user's move stayed in the curriculum's book line.

    `opening_name` is whatever `recognize_opening_from_history` returns
    — a dict with a `"name"` key (e.g. `{"name": "italian_game", ...}`),
    the same shape caption_pipeline.py already consumes elsewhere. This
    accepts a plain string too, for callers that already resolved it.

    `move_history_san` must be the FULL SAN history including this move
    — `board_before` is built fresh from a stored FEN by the caller
    (coach_memory.py) and has no move_stack to derive it from.

    Returns:
      "applied" — the move matched the curriculum's book line
      None — no curriculum coverage for this opening, or the move
             deviated (deviation is not gradable good/bad with the
             data that exists — see module docstring)
    """
    if move_number is None or move_number > 15:
        return None
    if not opening_name or not move_history_san:
        return None

    opening_key = opening_name.get("name") if isinstance(opening_name, dict) else opening_name
    if not opening_key:
        return None

    try:
        from services.opening_curriculum_engine import get_opening_guidance

        user_color_str = "white" if user_color == chess.WHITE else "black"
        guidance = get_opening_guidance(
            opening_key=opening_key,
            moves_played=move_history_san,
            user_color=user_color_str,
        )
        if guidance is None:
            return None  # no curriculum entry for this opening at all
        if guidance.get("is_in_book"):
            return "applied"
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
