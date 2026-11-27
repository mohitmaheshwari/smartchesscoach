"""Why did this error happen, when it is too rare to drill?

Mohit, 2026-11-27: "if that's less than 25%, then we would try to understand
why this error existed, was this a time pressure thing, was this an eye sight
or was player distracted, not focused... chess is just not calculation and
tactics, chess is also focus and behavioral tactics, so that's what we want
to track."

So this is the second half of the drill rule in
`player_coach_plan.below_drill_bar`: the error is real, the rate is under the
bar, and the player is owed a circumstance rather than an exercise.

WHAT EARNED A PLACE HERE
------------------------
A cause only counts if it is commoner among the errors than among the SAME
opportunities that went fine. Measured 2026-11-27 over 1,200 analysed games
and 5,466 eligible one-move piece-safety decisions, base rate 8.29%:

    signal                             n     with   without   lift
    time pressure (<60s left)        218   14.68%    8.05%   1.82x
    unravelling (big error in last 3) 1539  10.14%    7.56%   1.34x
    late game (move 31+)             672   10.42%    7.99%   1.30x
    snap move (<= 1/3 his own pace)  382    6.02%    8.49%   0.71x

WHAT WAS REFUSED
----------------
- **Moving fast is not a cause. It is protective** (0.71x). "Eyesight" and
  "he rushed" are the same guess and this is the third time the data has
  refused it: the teaching triage had a `rushed` rule that was backwards
  (a 0-1s error is a knowledge gap 21.7% of the time against 6.8% at 30s+),
  and now a snap move is measurably SAFER than a considered one. Do not
  reintroduce it.
- **Tilt**: dead. 62.7 accuracy after a loss against 62.4 after a win, and
  63.2 after three straight losses -- above their own average.
- **Board region / where his attention was**: dead. Errors by file ran
  11.26% / 11.15% / 11.83% in the middlegame and 10.80 / 10.78 / 10.76 in
  the endgame.
- **Very low clock (<15s)** is real at 1.76x but fired on only 7 of 453
  errors. Folded into time pressure rather than claimed separately.

THE CEILING, WHICH MUST STAY VISIBLE
------------------------------------
At least one signal covers 49.7% of errors. **Nothing explains the other
50.3%**, so `not_explained` is a first-class answer and is never dressed up
as one of the others. Saying "you were distracted" because nothing else fit
would be inventing the thing the player would most resent.
"""
from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List, Mapping, Optional, Sequence

# Measured 2026-11-27; see the module docstring. NOT locked -- /lock-via-data.
LOW_CLOCK_SECONDS = 60.0
UNRAVEL_PLIES = 3
UNRAVEL_BIG_CP = 200
LATE_GAME_MOVE = 31

# Strongest measured lift first. When several circumstances are true at once
# the strongest one is named, because naming all of them says nothing.
CAUSE_ORDER = ("time_pressure", "unravelling", "late_game")

# Player-facing, no digits (the plan's own rule), and each says what to do.
CAUSE_WORDS = {
    "time_pressure": (
        "Your clock was low",
        "This mostly happens when you are short of time. "
        "Keep enough time to check what your opponent can take."),
    "unravelling": (
        "It follows another mistake",
        "This mostly happens in the moves right after a mistake. "
        "When a move goes wrong, take your time on the next one."),
    "late_game": (
        "Late in the game",
        "This mostly happens deep into a game, when you are moving quickly. "
        "Slow down once the pieces start coming off."),
    "not_explained": (
        "No clear pattern yet",
        "These did not share a moment we can point to. "
        "Nothing to change in how you play yet."),
}


def _median(values: Sequence[float]) -> Optional[float]:
    vals = sorted(v for v in values if v is not None)
    if not vals:
        return None
    mid = len(vals) // 2
    return vals[mid] if len(vals) % 2 else (vals[mid - 1] + vals[mid]) / 2.0


def prior_big_error(game_rows: Sequence[Mapping[str, Any]], index: int,
                    plies: int = UNRAVEL_PLIES,
                    big_cp: int = UNRAVEL_BIG_CP) -> bool:
    """Did HE go wrong in the few moves before this one?

    The rows must be one game, his moves, in ply order. Measured elsewhere:
    he loses 85.1cp over the three moves after a big error against 53.2cp
    after a good one, a ratio of 1.60.
    """
    for row in game_rows[max(0, index - plies):index]:
        if (row.get("cp_loss") or 0) >= big_cp:
            return True
    return False


def cause_for_move(row: Mapping[str, Any], *, after_big_error: bool,
                   low_clock_seconds: float = LOW_CLOCK_SECONDS,
                   late_game_move: int = LATE_GAME_MOVE) -> str:
    """The one circumstance to name for a single error, or not_explained.

    Deliberately has no "rushed" branch: a snap move is measurably SAFER
    than a considered one (0.71x). See the module docstring.
    """
    clock = row.get("time_left_seconds")
    if clock is not None and clock < low_clock_seconds:
        return "time_pressure"
    if after_big_error:
        return "unravelling"
    move_no = row.get("move_number")
    if move_no is not None and move_no >= late_game_move:
        return "late_game"
    return "not_explained"


def reading(error_rows_by_game: Mapping[str, Sequence[Mapping[str, Any]]],
            fired_keys: Sequence[tuple]) -> Optional[Dict[str, Any]]:
    """The circumstance behind a set of errors, or None when there are none.

    `error_rows_by_game` is every one of his moves per game, in ply order, so
    the move BEFORE an error can be read. `fired_keys` are the
    (game_id, ply) pairs where the detector fired.

    Returns the dominant cause with its share, every cause counted, and the
    unexplained count -- which is never hidden and may well be the largest.
    """
    fired = set(fired_keys)
    causes: List[str] = []
    clocks: List[float] = []
    for game_id, rows in error_rows_by_game.items():
        for i, row in enumerate(rows):
            if (game_id, row.get("ply")) not in fired:
                continue
            causes.append(cause_for_move(
                row, after_big_error=prior_big_error(rows, i)))
            if row.get("time_left_seconds") is not None:
                clocks.append(row["time_left_seconds"])
    if not causes:
        return None

    counts = Counter(causes)
    explained = [c for c in CAUSE_ORDER if counts.get(c)]
    # The dominant cause is the commonest EXPLAINED one, and it is only
    # claimed when it covers more of the errors than "we cannot say".
    top = max(explained, key=lambda c: counts[c]) if explained else None
    unexplained = counts.get("not_explained", 0)
    if top is None or counts[top] <= unexplained:
        top = "not_explained"
    title, text = CAUSE_WORDS[top]
    return {
        "cause": top,
        "title": title,
        "text": text,
        # Counts stay here; the player-facing sentences carry no digits.
        "measured": {
            "errors": len(causes),
            "by_cause": dict(counts),
            "unexplained": unexplained,
            "median_clock_seconds": _median(clocks),
        },
    }


# ---------------------------------------------------------------------------
# Tracked behaviour axes
#
# Mohit, 2026-11-27: "chess is just not calculation and tactics, chess is also
# focus and behavioral tactics, so that's what we want to track."
#
# Each axis is a rate out of chances, from a pair of booleans that
# move_observations already carries at 100% coverage. They are TRACKED, not
# used as drill gates, and that is a measured decision rather than a
# preference. Per-user rates over the last ten games, 2026-11-27:
#
#   axis                        users  p25  median  max   at/above a 25% bar
#   kept pieces safe               65   4%     6%   30%   4 of 65
#   answered their threat          59  26%    32%   64%  46 of 59
#   punished their mistake         10  41%    54%   68%   9 of 10
#   found it when it mattered      62  87%    94%  100%  62 of 62
#
# So the 25% drill bar is calibrated to piece safety and transfers to none of
# the others: it would drill almost everyone, which is the opposite of the
# rule it came from. `found it when it mattered` has a 94% median -- missing
# the best move at a critical moment is near-universal, so it measures being
# human, not a weakness, and must never be shown as a fault.
#
# A per-axis bar has to come from each axis's own distribution before any of
# these gates a drill. Until then they are context: a rate the player and the
# coach can both read, comparable between players because it has a
# denominator.
AXES = {
    "axis:piece_safety": {
        "title": "Keeping pieces safe",
        "good": "Your pieces stayed safe",
        # This one is the structured verdict, counted in player_coach_file.
        "pair": None,
        "drill_bar": 0.25,          # measured: picks 4 of 65
    },
    "axis:threat_answered": {
        "title": "Answering their threats",
        "good": "You answered what they threatened",
        "pair": ("ignored_opponent_threat", "responded_to_threat"),
        "drill_bar": None,          # 25% would drill 46 of 59
    },
    "axis:punished_their_mistake": {
        "title": "Punishing their mistakes",
        "good": "You took what they gave you",
        "pair": ("missed_opponent_blunder", "punished_opponent_blunder"),
        "drill_bar": None,          # 25% would drill 9 of 10
    },
}

# Deliberately NOT an axis: was_critical_moment / found_best_in_critical.
# 94% median across 62 users. A number everyone fails is not a weakness, and
# showing it would read as "you are bad at chess".
NOT_AN_AXIS = ("found_best_in_critical",)


def axis_rates(rows: Sequence[Mapping[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Chances and wrong turns per tracked axis, over whatever rows are given.

    `wrong / chances` only -- no verdict, no drill decision. The bar for each
    axis is an open calibration (see AXES), and a rate with a denominator is
    worth showing on its own.
    """
    out: Dict[str, Dict[str, Any]] = {}
    for key, spec in AXES.items():
        pair = spec.get("pair")
        if not pair:
            continue
        wrong_field, right_field = pair
        wrong = sum(1 for r in rows if r.get(wrong_field))
        right = sum(1 for r in rows if r.get(right_field))
        chances = wrong + right
        if not chances:
            continue
        out[key] = {"title": spec["title"], "chances": chances, "wrong": wrong,
                    "rate": round(wrong / chances, 4)}
    return out
