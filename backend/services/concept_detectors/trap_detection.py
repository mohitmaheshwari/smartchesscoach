"""
Trap detection — did the user fall for a known trap, or successfully
punish one, mid-game?

Rewritten 2026-08-03. The original version was a permanent no-op: it
called `trap_recognition.detect_trap_setup(board_before)` — a
chess.Board — but the real signature is
`detect_trap_setup(played_moves_san: List[str])`, which raises
`TypeError: 'Board' object is not iterable` every time (caught by the
broad except below, so it never crashed, just never fired). It also
read `trap_hit.get("victim_move")` / `trap_hit.get("defense_moves")` —
keys that don't exist anywhere on `detect_trap_setup`'s real return
shape (`name`, `family`, `trap_line`, `trap_line_steps`, `trap_color`,
`success_message`).

The correct victim/setter semantics are already implemented and proven
correct in `caption_pipeline.py`'s trap state machine (the one behind
the real, live `trap_fires` field): `trap_color` is the SETTER's color
(the side that benefits/punishes); the victim is simply the opposite
color. That code is stateful (tracks `active_trap` / cursor across
moves via `coach_sessions`) because its caller has persistent
per-session state to store it in. This detector's caller
(coach_memory.py, run once per historical move with no persisted
state between calls) doesn't have that — so instead of state, this
derives the same information by re-deriving it from the full move
history on every call: `detect_trap_setup` is retried at every prefix
length, and whichever prefix's `trap_line` the moves since then
actually follow (verified with `match_trap_line_step`, not assumed)
tells us both which trap is active and how far its line has
progressed, with no session state required.

What this can and can't grade, honestly:
  - "missed": the user is confirmed to be the trap's victim (their
    color != trap_color) and their move is exactly the known bad
    continuation at the correct even-indexed trap_line step. This is a
    real, engine-authored, verifiable fact from traps.json.
  - "applied": the user is confirmed to be the trap's setter (their
    color == trap_color) and their move is exactly the correct
    punishing continuation at the correct odd-indexed trap_line step.
  - There is deliberately NO "applied" grade for a victim who plays
    something OTHER than the known bad line. traps.json has no
    "defense_moves" / correct-escape field to verify that alternative
    against — grading an arbitrary different move as a deliberate,
    correct escape would be a guess, not a verified fact. Silence
    (None) is correct here, not a gap to paper over.
"""
from __future__ import annotations

from typing import List, Optional
import chess
import logging

from services.concept_detectors.evidence import (
    stored_best_matches,
    stored_best_move,
)

logger = logging.getLogger(__name__)


def detect_trap_application_detail(
    board_before: chess.Board,
    move: chess.Move,
    user_color: chess.Color,
    move_number: Optional[int] = None,
    move_history_san: Optional[List[str]] = None,
    best_move_san: Optional[str] = None,
    best_move_uci: Optional[str] = None,
) -> Optional[dict]:
    """
    Detect if the user's move fell into a known trap (as victim) or
    correctly executed a known trap's punishment (as setter).

    `move_history_san` must be the FULL SAN history of the game
    including this move (i.e. the caller appends this move's SAN before
    calling) — the detector cannot derive it from `board_before`, which
    is built fresh from a stored FEN and has no move_stack.

    Returns:
      "missed"   — user is the trap's victim and played the known bad
                   continuation
      "applied"  — user is the trap's setter and played the known
                   punishing continuation
      None       — not a trap moment, or the position doesn't match any
                   known trap's setup at all
    """
    if move_number is None or move_number > 20:
        return None
    if not move_history_san:
        return None

    try:
        from services.trap_recognition import (
            detect_trap_defense_setup,
            detect_trap_setup,
            match_trap_line_step,
        )
    except Exception as e:
        logger.debug(f"Trap detection import failed: {e}")
        return None

    mover_color_str = "white" if user_color == chess.WHITE else "black"
    n = len(move_history_san)

    try:
        # A victim earns application credit only for the exact authored,
        # validator-approved defense. Merely deviating from the trap line is
        # not enough: many deviations are still losing.
        defense = detect_trap_defense_setup(move_history_san[:-1])
        if defense:
            trap_color = str(defense.get("trap_color") or "").lower()
            defense_line = defense.get("defense_line") or []
            if (
                trap_color
                and mover_color_str != trap_color
                and defense_line
                and stored_best_matches(
                    board_before, move, best_move_san, best_move_uci
                )
                and match_trap_line_step(
                    {"trap_line": defense_line},
                    move_history_san[-1],
                    0,
                )
            ):
                return {
                    "outcome": "applied",
                    "content_id": defense.get("content_id"),
                    "family": defense.get("family"),
                }

        # The move being graded is always move_history_san[-1]. Try every
        # possible setup length: does move_history_san[:setup_len] exactly
        # complete some trap's setup, and does everything played since
        # (move_history_san[setup_len:]) match that trap's trap_line in
        # order? If so, the current move is trap_line step
        # (n - setup_len - 1).
        for setup_len in range(1, n):
            hit = detect_trap_setup(move_history_san[:setup_len])
            if not hit:
                continue
            trap_line = hit.get("trap_line") or []
            steps_played = n - setup_len
            if steps_played < 1 or steps_played > len(trap_line):
                continue
            if not all(
                match_trap_line_step(hit, move_history_san[setup_len + i], i)
                for i in range(steps_played)
            ):
                continue

            current_step_index = steps_played - 1
            trap_color = (hit.get("trap_color") or "").lower()
            if not trap_color:
                return None
            user_is_victim = mover_color_str != trap_color

            if user_is_victim and current_step_index % 2 == 0:
                best = stored_best_move(
                    board_before, best_move_san, best_move_uci
                )
                if best is None or best == move:
                    return None
                return {
                    "outcome": "missed",
                    "content_id": hit.get("content_id"),
                    "family": hit.get("family"),
                }
            if not user_is_victim and current_step_index % 2 == 1:
                if not stored_best_matches(
                    board_before, move, best_move_san, best_move_uci
                ):
                    return None
                return {
                    "outcome": "applied",
                    "content_id": hit.get("content_id"),
                    "family": hit.get("family"),
                }
            return None

        return None
    except Exception as e:
        logger.debug(f"Trap detection failed: {e}")
        return None


def detect_trap_application(
    board_before: chess.Board,
    move: chess.Move,
    user_color: chess.Color,
    move_number: Optional[int] = None,
    move_history_san: Optional[List[str]] = None,
    best_move_san: Optional[str] = None,
    best_move_uci: Optional[str] = None,
) -> Optional[str]:
    detail = detect_trap_application_detail(
        board_before,
        move,
        user_color,
        move_number=move_number,
        move_history_san=move_history_san,
        best_move_san=best_move_san,
        best_move_uci=best_move_uci,
    )
    return str(detail.get("outcome")) if detail else None
