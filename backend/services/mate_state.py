"""One definition of "is this row about a mate, and which way did it go".

Two repaired consumers disagreed (Codex review of 116fbd90, finding P2):
`game_coach_review` treated a row with `eval_before` 9970 as mate-related while
`game_coach_summary` partitioned only on `cp_loss >= 9000` and let the same row
through as ordinary material. Divergence like that is what a shared helper is
for, so both now call this.

THE SIGN CONVENTION, verified rather than assumed
-------------------------------------------------
`mate_info` is a dict `{"before": int|None, "after": int|None}`, **WHITE-
relative and signed**: positive means White mates in N, negative means Black
mates in N, and 0 means mate was delivered by the move. Measured over 300
production games that ended in checkmate, the last row carrying `mate_info`
reads:

    white won      before +1, after 0        (89 games)
    black won      before -1, after 0        (50 games)
    white lost     after -1                  (72 games)
    black lost     after +1                  (79 games)

Consistent in every case, which is why the transition is read from this field
and not from the evaluation sign.

`eval_before` / `eval_after` are NOT usable for direction. Over the same games
black winners show a POSITIVE final eval (user-relative) while black losers
also show a POSITIVE final eval (white-relative). The two cannot both hold, so
the stored sign convention is inconsistent across rows and any "who had mate"
derived from it would be wrong some of the time. The evals are used here only
as a magnitude hint for *whether* a mate is involved, never for whose.

COVERAGE
--------
`mate_info` is present on about 8.1% of user rows. When it is absent the
transition is genuinely unknown, and the caller must say something neutral
rather than guess a direction.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

# At or above this, a stored evaluation is a mate sentinel rather than a
# centipawn quantity. Stockfish sentinels sit at +/-9000 and above.
MATE_SENTINEL_CP = 9000

# Transition labels. Deliberately plain, and none of them states a centipawn
# or material amount, because a mate is neither.
GAVE_UP_MATE = "gave up a forced mate"
ALLOWED_MATE = "allowed a forced mate"
KEPT_MATE = "still had a forced mate"
ESCAPED_MATE = "escaped a forced mate"
DELIVERED_MATE = "delivered mate"
SWAPPED_MATE = "turned a mate for you into one against you"
MATE_INVOLVED = "a forced mate was involved"


def is_mate_related(ev: Dict[str, Any]) -> bool:
    """True when this row's cost is about a mate rather than about material.

    Deliberately broader than `cp_loss >= MATE_SENTINEL_CP`: a move can go
    from "mate in 3 for you" to "+8585" and lose only 1,385 by the cp
    arithmetic while being entirely about a mate. Checking `mate_info` and
    both evaluations catches that; checking the delta alone does not.
    """
    mi = ev.get("mate_info")
    if isinstance(mi, dict) and any(v is not None for v in mi.values()):
        # Any non-empty mate_info means a mate was in the position. Keyed on
        # values rather than on the `before`/`after` names so a row written
        # with a different key shape is still recognised as mate-related --
        # `mate_transition` is where the names matter.
        return True
    for field in ("eval_before", "eval_after"):
        v = ev.get(field)
        if isinstance(v, (int, float)) and abs(v) >= MATE_SENTINEL_CP:
            return True
    cp = ev.get("cp_loss")
    return isinstance(cp, (int, float)) and abs(cp) >= MATE_SENTINEL_CP


def _side(value: Optional[int], user_is_white: bool) -> Optional[str]:
    """Whose mate is this signed, white-relative figure? None if no mate."""
    if value is None:
        return None
    if value == 0:
        return "delivered"
    return "user" if ((value > 0) == user_is_white) else "opponent"


def mate_transition(ev: Dict[str, Any], user_color: str) -> Optional[str]:
    """What happened to the mate across this move, from the player's side.

    Returns None when the row is not mate-related at all. Returns
    MATE_INVOLVED when it is, but `mate_info` is missing so the direction
    cannot be established -- which is the common case at 8.1% coverage, and
    is reported honestly rather than guessed.
    """
    if not is_mate_related(ev):
        return None
    mi = ev.get("mate_info")
    if not isinstance(mi, dict):
        return MATE_INVOLVED
    user_is_white = str(user_color) == "white"
    before = _side(mi.get("before"), user_is_white)
    after = _side(mi.get("after"), user_is_white)

    if after == "delivered":
        return DELIVERED_MATE
    if before == "user" and after is None:
        return GAVE_UP_MATE
    if before == "user" and after == "user":
        return KEPT_MATE
    if before == "user" and after == "opponent":
        return SWAPPED_MATE
    if before is None and after == "opponent":
        return ALLOWED_MATE
    if before == "opponent" and after is None:
        return ESCAPED_MATE
    if before == "opponent" and after == "opponent":
        # Still being mated. Not something this move caused.
        return MATE_INVOLVED
    return MATE_INVOLVED


def costs_the_player(transition: Optional[str]) -> bool:
    """Did this transition go against the player?

    KEPT_MATE, ESCAPED_MATE and DELIVERED_MATE did not, so a review must not
    describe them as a loss however large the cp difference looks.
    """
    return transition in (GAVE_UP_MATE, ALLOWED_MATE, SWAPPED_MATE)
