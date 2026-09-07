"""What actually happened to the player's position over the game.

The narrative surfaces (Truth, Player Decryption) assert things like "you were
winning", "move 16 flipped the game — and it never came back", "you ran out of
time". Those are factual claims about the game, and until 2026-09-06 nothing
checked them: on lichess qBNJQg3g the review said the game "never came back"
while our own cards recorded `mover_state_after: "winning"` on all 54 user moves
after the move being blamed.

This module derives those facts ONCE, from the same cards the narrative
describes, so Truth and Player Decryption cannot disagree with each other or
with the board. Every consumer reads it here — do not recompute trajectory
inline (feedback_single_source_of_truth).

`mover_state_after` is produced by services/severity.py `_decisiveness_state`
and is one of "winning" / "balanced" / "losing", from the mover's point of view.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

# A "recovery" claim needs enough moves after the critical one to mean
# anything. Two winning moves before the game ends is noise; three or more is
# a position the player genuinely held.
MIN_MOVES_FOR_RECOVERY_CLAIM = 3

WINNING = "winning"
LOSING = "losing"


def _user_cards(decryption_v5_data: Optional[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    cards = [c for c in (decryption_v5_data or []) if c.get("is_user_move")]
    return sorted(cards, key=lambda c: (c.get("move_number") or 0))


def compute_trajectory(
    decryption_v5_data: Optional[List[Dict[str, Any]]],
    *,
    critical_move_number: Optional[int] = None,
    termination: str = "unknown",
    game_result: str = "",
    user_color: str = "white",
) -> Dict[str, Any]:
    """Return the trajectory facts the narrative layer is allowed to assert."""
    cards = _user_cards(decryption_v5_data)
    states = [c.get("mover_state_after") for c in cards]

    after = [
        c for c in cards
        if critical_move_number is not None
        and (c.get("move_number") or 0) > critical_move_number
    ]
    after_states = [c.get("mover_state_after") for c in after]

    stayed_winning = (
        len(after) >= MIN_MOVES_FOR_RECOVERY_CLAIM
        and all(s == WINNING for s in after_states)
    )

    ended_winning = bool(states) and states[-1] == WINNING

    return {
        "n_user_moves": len(cards),
        "critical_move_number": critical_move_number,
        "n_user_moves_after_critical": len(after),
        # Did the player hold a winning position at any point?
        "was_winning_at_some_point": any(s == WINNING for s in states),
        # Was every move after the blamed move still winning? If so, that move
        # did NOT decide the game and no collapse claim may be made about it.
        "stayed_winning_after_critical": stayed_winning,
        # Was the player still winning on their final move? A loss from here is
        # a loss off the board (clock, resignation) or a final-move collapse.
        "ended_winning": ended_winning,
        "is_timeout": (termination or "").lower() == "timeout",
        "termination": termination or "unknown",
        "game_result": game_result or "",
        "user_color": user_color,
    }


def won_on_board_lost_anyway(trajectory: Dict[str, Any]) -> bool:
    """The player was still winning at their last move but did not win.

    This is the shape the old copy could not express at all: a game decided by
    the clock (or a resignation in a winning position), not by a mistake.
    """
    return bool(trajectory.get("ended_winning"))
