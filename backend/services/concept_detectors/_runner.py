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

import inspect
from typing import Iterable, List, Optional, Tuple

import chess

from services.concept_detectors.registry import all_detectors
from services.detector_quality import (
    QualityGrade,
    QualitySurface,
    can_influence,
    concept_quality_id,
    grade_for,
)

# Detectors beyond the documented 3-arg contract (board_before, move,
# user_color) declare extra optional kwargs — trap_detection and
# opening_play both need `move_number` to even run (their own first
# line is `if move_number is None: return None`), and opening_play also
# needs `opening_name`. The runner used to call every detector with
# exactly 3 positional args, so these two silently never fired in
# production — no crash, since the extra params have defaults, just a
# permanent no-op. Bug fixed 2026-08-03. Every OTHER detector keeps the
# strict 3-arg contract from registry.py unchanged; we only pass the
# extra kwargs to detectors that actually declare them, via
# inspect.signature, rather than widening the contract for all 10.
#
# 2026-08-03: both trap_detection and opening_play have been rewritten
# to work with the real, available data (see each module's own
# docstring for what changed and why). trap_detection now also declares
# `move_history_san`, needed because its caller (coach_memory.py)
# builds `board_before` fresh from a stored FEN on every move — the
# board has no move_stack to derive history from, so the full SAN
# history has to be threaded in explicitly, the same way move_number
# and opening_name already are.
_EXTRA_KWARG_CACHE: dict = {}
_EXTRA_KWARGS = ("move_number", "opening_name", "move_history_san")


def _extra_kwargs_accepted(detector) -> set:
    cached = _EXTRA_KWARG_CACHE.get(detector)
    if cached is None:
        params = inspect.signature(detector).parameters
        cached = {name for name in _EXTRA_KWARGS if name in params}
        _EXTRA_KWARG_CACHE[detector] = cached
    return cached


def run_detectors_for_move(
    board_before: chess.Board,
    move: chess.Move,
    user_color: chess.Color,
    move_number: Optional[int] = None,
    opening_name: Optional[str] = None,
    move_history_san: Optional[List[str]] = None,
    include_shadow: bool = False,
) -> List[Tuple[str, str]]:
    """Run every registered detector against a move.

    Returns a list of (skill_id, outcome) tuples for every detector that
    decided this position was a clean test. `outcome` is "applied" when
    the user passed and "wrong" when the user failed. Detectors that
    return None (not a clean test) are filtered out.

    `move_number` / `opening_name` / `move_history_san` are optional and
    only forwarded to detectors that declare them (trap_detection,
    opening_play) — every other detector keeps its strict
    3-positional-arg contract.

    Caller is responsible for persisting the outcomes via
    coach_memory.record_skill_attempt.
    """
    results: List[Tuple[str, str]] = []
    for skill_id, detector in all_detectors().items():
        quality_id = concept_quality_id(skill_id)
        grade = grade_for(quality_id)
        if grade == QualityGrade.DISABLED:
            continue
        try:
            accepted = _extra_kwargs_accepted(detector)
            kwargs = {}
            if "move_number" in accepted:
                kwargs["move_number"] = move_number
            if "opening_name" in accepted:
                kwargs["opening_name"] = opening_name
            if "move_history_san" in accepted:
                kwargs["move_history_san"] = move_history_san
            verdict = detector(board_before, move, user_color, **kwargs)
        except Exception:
            # Detector bugs must not poison the move pipeline.
            continue
        if not include_shadow and not can_influence(
            quality_id, QualitySurface.MASTERY
        ):
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
