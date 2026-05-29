"""
Concept-detector runner.

Iterates every registered detector against a single user move and
records the resulting skill-grade against coach_memory. Designed to be
called from two paths today:

  - Live PWC: after the user's move is accepted in coach_play, run the
    runner on (board_before, move, user_color) to record any concept
    application that occurred this move.
  - Game review: when re-rendering / analysing a played game move-by-
    move, run the same runner so historical games credit the user for
    concepts they applied even before the detector framework existed.

The runner is deliberately stateless on its own — it doesn't decide
whether the user is the mover, only the caller knows that. Mistakes in
the calling integration will produce false positives, so the
integration points are kept small (two call sites total).
"""
from __future__ import annotations

from typing import Iterable, List, Optional, Tuple

import chess

from services.concept_detectors.registry import all_detectors


def run_detectors_for_move(
    board_before: chess.Board,
    move: chess.Move,
    user_color: chess.Color,
) -> List[Tuple[str, str]]:
    """Run every registered detector against a move.

    Returns a list of (skill_id, outcome) tuples for every detector that
    decided this position was a clean test. `outcome` is "applied" when
    the user passed and "wrong" when the user failed. Detectors that
    return None (not a clean test) are filtered out.

    Caller is responsible for persisting the outcomes via
    coach_memory.record_skill_attempt.
    """
    results: List[Tuple[str, str]] = []
    for skill_id, detector in all_detectors().items():
        try:
            verdict = detector(board_before, move, user_color)
        except Exception:
            # Detector bugs must not poison the move pipeline.
            continue
        if verdict == "applied":
            results.append((skill_id, "applied"))
        elif verdict == "missed":
            results.append((skill_id, "wrong"))
    return results


def run_detectors_for_game(
    moves_iter: Iterable[Tuple[chess.Board, chess.Move, chess.Color]],
) -> List[Tuple[str, str]]:
    """Aggregate every detector-grade across an entire game.

    `moves_iter` yields `(board_before, move, user_color)` tuples for
    USER moves only (caller filters opponent moves out).

    Returns the deduplicated list of grades — if a single concept fired
    "applied" earlier in the game and "wrong" later, the LATEST grade
    wins (the user backslid). This matches how skill outcomes are
    tracked: the most recent demonstration is what counts.
    """
    by_skill: dict = {}
    for board_before, move, user_color in moves_iter:
        for skill_id, outcome in run_detectors_for_move(board_before, move, user_color):
            by_skill[skill_id] = outcome  # latest wins
    return list(by_skill.items())
