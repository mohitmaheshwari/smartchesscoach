"""How a player behaves, computed from their moves instead of defaulted.

Why this exists
---------------
Scanned every per-user field in production on 2026-09-22. Forty of them hold
the SAME VALUE for all 69 players. The behavioural block is the worst of it:

    avg_move_time_opening      10.0   for everyone
    avg_move_time_middlegame   15.0   for everyone
    avg_move_time_endgame       8.0   for everyone
    post_blunder_accuracy       0.5   for everyone
    recovery_capability         0.5   for everyone
    first_game_accuracy         0.5   for everyone
    blunder_spiral_rate         0.0   for everyone
    rushes_in_winning_positions False for everyone
    time_trouble_frequency      0.0   for everyone

Those are not measurements. They are the defaults the dataclass was born
with, and nothing has ever replaced them. The real median middlegame move
takes 5.1 seconds across 54,548 stored moves -- the hardcoded 15.0 is three
times the truth, and identical for every player in the system.

This is also why `behavioral_coaching_layer` diagnoses 53 of 57 eligible
players as nothing at all and the other 4 identically: every gate it opens
reads one of the fields above, and they never move.

The raw material was there the whole time. In `move_observations`:
`time_spent_seconds` on 90.3% of moves, `time_left_seconds` on 94.2%,
`cp_loss` and `eval_before` on 100%. Measured from there, the same questions
separate players cleanly -- mistakes after a mistake run 15.7% to 46.7%
across players, moves under two seconds run 4.7% to 48.6%.

So this module answers the existing questions from the moves, the same way
`positional_snapshot` does for position state.

LOAD-BEARING: reads stored observations only. No engine, no board replay, no
LLM. Returns None for anything it cannot support rather than a plausible
number -- a default is what created this problem, and a second one would
only hide it again.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

#: A move at or under this many seconds was not really considered. Mohit's
#: own threshold, already used by `player_identity` for impulse_moves.
IMPULSE_SECONDS = 2.0

#: cp_loss at or above this is a mistake worth counting. Matches the bar used
#: everywhere else in this codebase for "this move cost something real".
MISTAKE_CP = 100

#: Below this many usable moves a rate is noise, so it is reported as None.
#: Mohit ruled the record window is the last 10 games (2026-09-22); at a
#: median ~40 moves per game that is ~400 moves, so a per-phase or
#: per-situation slice needs far fewer than the whole window to be fair.
MIN_SAMPLE = 30

#: Where "winning" starts. Read off the distribution, not chosen: over
#: 120,000 stored moves the mistake rate is 8.8% in level positions
#: (-50..+50) and 23.6% at +200..+500, and +200 is where the jump happens.
WINNING_CP = 200
LEVEL_CP = 50


def _rate(hits: int, total: int) -> Optional[float]:
    """A proportion, or None when the sample is too small to mean anything."""
    if total < MIN_SAMPLE:
        return None
    return round(hits / total, 4)


def _median(values: List[float]) -> Optional[float]:
    if len(values) < MIN_SAMPLE:
        return None
    values = sorted(values)
    mid = len(values) // 2
    if len(values) % 2:
        return round(values[mid], 2)
    return round((values[mid - 1] + values[mid]) / 2, 2)


def behavioural_stats(observations: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    """Behaviour for one player, from their stored move observations.

    `observations` should already be limited to the window the caller wants
    (Mohit ruled: the last 10 games). This function does no filtering of its
    own beyond discarding unusable rows.

    Every value is either measured or None. There are no defaults here by
    design: a plausible-looking 0.5 is exactly what made the old block
    useless, and it is better to say "not enough evidence" than to say
    something true of nobody.
    """
    times_by_phase: Dict[str, List[float]] = {}
    impulse = timed = 0
    mistakes_by_state: Dict[str, List[int]] = {"winning": [], "level": [], "losing": []}
    after_mistake: List[int] = []
    prev_was_mistake: Dict[Any, bool] = {}
    total_moves = 0

    for obs in observations:
        cp = obs.get("cp_loss")
        is_mistake = isinstance(cp, (int, float)) and cp >= MISTAKE_CP
        total_moves += 1

        secs = obs.get("time_spent_seconds")
        if isinstance(secs, (int, float)) and secs > 0:
            timed += 1
            if secs <= IMPULSE_SECONDS:
                impulse += 1
            phase = str(obs.get("phase") or "unknown")
            times_by_phase.setdefault(phase, []).append(float(secs))

        ev = obs.get("eval_before")
        if isinstance(ev, (int, float)):
            if ev >= WINNING_CP:
                state = "winning"
            elif ev <= -WINNING_CP:
                state = "losing"
            elif -LEVEL_CP <= ev <= LEVEL_CP:
                state = "level"
            else:
                state = None
            if state:
                mistakes_by_state[state].append(1 if is_mistake else 0)

        # Tilt: a mistake on the move right after a mistake, same game. Keyed
        # per game so the last move of one game cannot contaminate the first
        # move of the next.
        game = obs.get("game_id")
        if prev_was_mistake.get(game):
            after_mistake.append(1 if is_mistake else 0)
        prev_was_mistake[game] = is_mistake

    stats: Dict[str, Any] = {
        "moves_observed": total_moves,
        "impulse_rate": _rate(impulse, timed),
        "mistake_rate_when_winning": _rate(
            sum(mistakes_by_state["winning"]), len(mistakes_by_state["winning"])
        ),
        "mistake_rate_when_level": _rate(
            sum(mistakes_by_state["level"]), len(mistakes_by_state["level"])
        ),
        "mistake_rate_when_losing": _rate(
            sum(mistakes_by_state["losing"]), len(mistakes_by_state["losing"])
        ),
        "mistake_rate_after_mistake": _rate(sum(after_mistake), len(after_mistake)),
    }

    for phase in ("opening", "middlegame", "endgame"):
        stats[f"median_move_seconds_{phase}"] = _median(times_by_phase.get(phase, []))

    # The one comparison worth drawing, and only when BOTH sides are real:
    # does this player get worse once they are ahead? Measured across 120,000
    # moves the average player errs ~2.7x more when winning than when level,
    # so the interesting fact is not the raw rate but the player's own ratio
    # against their own baseline.
    winning = stats["mistake_rate_when_winning"]
    level = stats["mistake_rate_when_level"]
    if winning is not None and level is not None and level > 0:
        stats["collapse_ratio"] = round(winning / level, 2)
    else:
        stats["collapse_ratio"] = None

    return stats
