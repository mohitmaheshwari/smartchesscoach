"""Eval-trajectory analysis — reads what Stockfish already knows.

For a move under consideration, look at the last N user evaluations
and decide: was the user already in a losing position BEFORE this
move? That's the classic *"you were already in trouble"* coaching
moment — different from a single-move tactical blunder.

Used by V5 service to inject `position_was_already_losing` +
`losing_since_move` into caption_facts so R12 can surface a why-clause
that names the strategic decline rather than the surface mistake.

Mohit 2026-05-20 scaling principle: leverage engine output we already
have instead of writing one detector per chess pattern.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


# eval is stored as pawns in stockfish_analysis.move_evaluations
# (e.g. 0.46 = +46cp = white advantage of ~half a pawn). We convert
# to centipawns inside the helper so callers get familiar units.
LOSING_THRESHOLD_CP = 150       # eval <= -150cp (= 1.5 pawns down) counts as "losing"
LOOKBACK_USER_MOVES = 3         # require N consecutive user moves all losing
MIN_USER_MOVE_INDEX = 6         # don't fire before move 6 (not enough history)


def _eval_to_cp(eval_value: Any) -> Optional[int]:
    """Normalize eval to centipawns. Stockfish stores in pawns
    (-3.5 to +3.5 typical) but mate-territory values can be very
    large numbers. Returns None when the value isn't numeric."""
    if eval_value is None:
        return None
    try:
        v = float(eval_value)
    except (TypeError, ValueError):
        return None
    # Heuristic: if abs(v) > 100 it's already in centipawns; else pawns.
    if abs(v) > 100:
        return int(round(v))
    return int(round(v * 100))


def detect_trajectory(
    move_evaluations: List[Dict[str, Any]],
    current_move_number: int,
    user_is_white: bool,
) -> Dict[str, Any]:
    """Return {position_was_already_losing, losing_since_move}.

    Args:
      move_evaluations: full per-user-move eval list from
        stockfish_analysis. Each entry has at least
        {move_number, eval_before, eval_after}.
      current_move_number: the move being captioned (1-indexed).
      user_is_white: whose POV to use. White user → positive eval is
        good; Black user → flip sign.

    Behavior:
      - Finds the current move's eval entry by move_number.
      - Looks at LOOKBACK_USER_MOVES user moves immediately PRIOR.
      - From user POV, checks if ALL of those moves'
        `eval_before` were <= -LOSING_THRESHOLD_CP.
      - If yes → already losing. Walks further back to find the
        earliest contiguous "losing" move (`losing_since_move`).
      - Doesn't fire before MIN_USER_MOVE_INDEX (not enough history).
    """
    result = {
        "position_was_already_losing": False,
        "losing_since_move": None,
    }
    if not move_evaluations or current_move_number is None:
        return result

    # Locate current move
    current_idx = None
    for i, m in enumerate(move_evaluations):
        if m.get("move_number") == current_move_number:
            current_idx = i
            break
    if current_idx is None or current_idx < LOOKBACK_USER_MOVES:
        return result
    if current_move_number < MIN_USER_MOVE_INDEX:
        return result

    # Pull the eval_before values for the last LOOKBACK_USER_MOVES
    # entries strictly before current_idx.
    recent: List[Tuple[int, int]] = []  # (move_number, user_eval_cp)
    for i in range(current_idx - LOOKBACK_USER_MOVES, current_idx):
        m = move_evaluations[i]
        cp = _eval_to_cp(m.get("eval_before"))
        if cp is None:
            return result  # missing eval → can't decide; stay False
        user_cp = cp if user_is_white else -cp
        recent.append((m.get("move_number"), user_cp))

    if not all(e <= -LOSING_THRESHOLD_CP for _, e in recent):
        return result

    # Walk further back to find first move in the losing run.
    losing_since = recent[0][0]
    for i in range(current_idx - LOOKBACK_USER_MOVES - 1, -1, -1):
        m = move_evaluations[i]
        cp = _eval_to_cp(m.get("eval_before"))
        if cp is None:
            break
        user_cp = cp if user_is_white else -cp
        if user_cp <= -LOSING_THRESHOLD_CP:
            losing_since = m.get("move_number") or losing_since
        else:
            break

    return {
        "position_was_already_losing": True,
        "losing_since_move": losing_since,
    }
