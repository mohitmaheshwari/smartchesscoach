"""How your chess is going — the week, the rhythm, and the session.

docs/chances_not_games_scope.md, extended 2026-10-06.

Mohit asked for four things and the first build shipped one of them:

    how is the week going          -> week_vs_usual
    how regular are you            -> rhythm
    are you learning, if not say so-> week_vs_usual carries the comparison
    quality of moves vs chances    -> already shipped, bars with no context

"Half" means nothing without "against what". This module is the against-what.

EVERY READING IS GATED ON ITS OWN EVIDENCE and says nothing rather than
guessing. The gates are not decoration: the session curve in particular is
stable for only about half the players who have enough games, so it is checked
against the player's own two halves before it is allowed to speak.

PURE FUNCTIONS. They take counts, not a database, so they can be tested without
one. `scripts/compute_habit_reading.py` does the gathering.
"""
from __future__ import annotations

import statistics
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

# A week with fewer chances than this is not a week, it is a couple of games.
MIN_WEEK_CHANCES = 20
# Weeks of history needed before "your usual" means anything.
MIN_PRIOR_WEEKS = 3
# Either side of this and the week is called different from usual. Below it the
# honest answer is "the same", and the same is the common case.
WEEK_SWING_POINTS = 6.0

# Days out of the last 28. Someone who played on four days did not have a quiet
# month, they had a different kind of month, and the wording has to carry that.
REGULAR_DAYS = 15
OCCASIONAL_DAYS = 5

# Session curve: how many games before "later in the session" begins.
LATER_FROM_GAME = 3
MIN_PER_SESSION_SLOT = 40
# The two halves of a player's own history must agree within this, in points,
# before the curve is spoken. Measured 2026-10-05: 11 of 23 players with enough
# games have a curve that holds, and the ones that flip all have small effects.
SESSION_HALVES_AGREE = 8.0
# Below this the fade is not worth a sentence even if it is real.
SESSION_MIN_FADE = 8.0


def week_vs_usual(this_week: Tuple[int, int],
                  prior_weeks: Sequence[Tuple[int, int]]) -> Optional[Dict[str, Any]]:
    """This week's conversion against the player's own usual.

    `this_week` and each prior week are (chances, taken). Returns None when
    there is not enough to compare, which is the correct answer for a new
    player and for a quiet week.
    """
    chances, taken = this_week
    if chances < MIN_WEEK_CHANCES:
        return None
    usable = [(c, t) for c, t in prior_weeks if c >= MIN_WEEK_CHANCES]
    if len(usable) < MIN_PRIOR_WEEKS:
        return None

    now = 100.0 * taken / chances
    usual = statistics.median([100.0 * t / c for c, t in usable])
    delta = now - usual
    if delta >= WEEK_SWING_POINTS:
        verdict, line = "better", "A better week than usual for you."
    elif delta <= -WEEK_SWING_POINTS:
        verdict, line = "worse", "A worse week than usual for you."
    else:
        # The common case, and the one worth saying out loud: steady is not
        # nothing, and pretending every week is a story would be a lie.
        verdict, line = "same", "About the same as your usual week."
    return {"chances": chances, "taken": taken, "verdict": verdict, "line": line}


def rhythm(days_played_last_28: int,
           median_games_per_day: Optional[float]) -> Optional[Dict[str, Any]]:
    """How regular the player has been. A description, never a judgement."""
    if days_played_last_28 <= 0:
        return None
    if days_played_last_28 >= REGULAR_DAYS:
        line = "You have played on most days this month."
        verdict = "regular"
    elif days_played_last_28 >= OCCASIONAL_DAYS:
        line = "You have played some days this month, not most."
        verdict = "occasional"
    else:
        line = "You have hardly played this month."
        verdict = "rare"
    return {
        "days": days_played_last_28,
        "median_games_per_day": median_games_per_day,
        "verdict": verdict,
        "line": line,
    }


def session_curve(early: Tuple[int, int], later: Tuple[int, int],
                  halves: Optional[Sequence[Tuple[float, float]]] = None
                  ) -> Optional[Dict[str, Any]]:
    """Does this player's conversion fall as a session goes on?

    `early` is their first two games of a session, `later` is the third onward,
    each (chances, taken). `halves` is the same fade measured separately on the
    two halves of their own history; the curve only speaks when both agree.

    Returns None rather than a weak claim. Measured across 46 players, the
    population curve is FLAT — 48% / 49% / 48% — so a fade is a fact about this
    player and not about chess, which is exactly what makes it worth saying and
    exactly why it has to survive its own stability check first.
    """
    ec, et = early
    lc, lt = later
    if ec < MIN_PER_SESSION_SLOT or lc < MIN_PER_SESSION_SLOT:
        return None
    fade = (100.0 * et / ec) - (100.0 * lt / lc)
    if fade < SESSION_MIN_FADE:
        return None
    if halves:
        usable = [h for h in halves if h is not None]
        if len(usable) < 2:
            return None
        first, second = usable[0], usable[1]
        if min(first, second) < SESSION_MIN_FADE:
            return None
        if abs(first - second) > SESSION_HALVES_AGREE:
            return None
    return {
        "fade_points": round(fade, 1),
        "line": "Your first game or two go best. After that it slips.",
        "next": "Most players hold steady across a session. You do not, so stop "
                "while it is still going well.",
    }


def results_fade(early: Tuple[int, int], later: Tuple[int, int],
                 conversion_fade: Optional[float],
                 halves: Optional[Sequence[Optional[float]]] = None
                 ) -> Optional[Dict[str, Any]]:
    """Do RESULTS fall away across a sitting while the tactical eye holds?

    This exists because `session_curve` correctly refused to speak and the
    refusal was the finding. Measured for one player 2026-10-06:

        conversion   first two games 53%, third onward 51%   -- flat
        win rate     first game 41%, 2nd-3rd 33%, 4th-6th 22% -- a cliff

    He keeps spotting tactics at the same rate deep into a session and loses far
    more games, so whatever degrades is NOT his tactical eye. That is a much
    more useful thing to tell someone than "you tilt", and it points somewhere
    specific — for this player, at a clock he loses 68 won positions on.

    `conversion_fade` is passed in so the sentence can only be used when the two
    disagree. If conversion fades too, the plain session line covers it and this
    one would be claiming a contrast that is not there.
    """
    ec, ew = early
    lc, lw = later
    if ec < MIN_PER_SESSION_SLOT or lc < MIN_PER_SESSION_SLOT:
        return None
    fade = (100.0 * ew / ec) - (100.0 * lw / lc)
    if fade < SESSION_MIN_FADE:
        return None
    # The whole point is the contrast. Without it there is no sentence here.
    if conversion_fade is None or conversion_fade >= SESSION_MIN_FADE:
        return None
    if halves:
        usable = [h for h in halves if h is not None]
        if len(usable) < 2 or min(usable) < SESSION_MIN_FADE:
            return None
        if abs(usable[0] - usable[1]) > SESSION_HALVES_AGREE:
            return None
    return {
        "fade_points": round(fade, 1),
        "line": "Your results fall away as a session goes on, but your eye for "
                "tactics does not.",
        "next": "Something other than spotting things is going wrong late in a "
                "sitting. Stop while it is still going well.",
    }


def build_habits(week: Optional[Mapping[str, Any]],
                 rhythm_reading: Optional[Mapping[str, Any]],
                 session: Optional[Mapping[str, Any]],
                 results: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    """The lines the card shows, in the order they should be read."""
    lines: List[Dict[str, str]] = []
    if week:
        lines.append({"kind": "week", "line": week["line"]})
    if rhythm_reading:
        lines.append({"kind": "rhythm", "line": rhythm_reading["line"]})
    if session:
        lines.append({"kind": "session", "line": session["line"],
                      "next": session["next"]})
    # Only one of these two can ever fire: `results_fade` requires conversion
    # NOT to fade, which is exactly when `session_curve` stays silent.
    if results:
        lines.append({"kind": "results", "line": results["line"],
                      "next": results["next"]})
    return {"measured": bool(lines), "lines": lines}
