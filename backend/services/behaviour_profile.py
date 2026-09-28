"""How a player plays — the behavioural traits, described rather than graded.

Mohit: *"behaviour detection is the real story a coach understands, and
knowledge"*, and then, of the six confirmed traits, *"all of them?"*

WHY THIS IS NOT A SCORECARD
---------------------------
`services/area_grades.py` grades board areas Excellent → Needs work, and that is
right for a skill. It is wrong for a disposition. "Thinks too long — Needs work"
would be a judgement the data refuses: measured per player, thinking longer goes
with FEWER errors, not more (r = -0.56). Traits are how someone plays, not how
well. So each one gets a sentence, never a grade and never a rank.

It is also not a focus. Five focuses is no focus — the picker still names ONE
thing to work on. This says who the player is; the focus says what to do next.

THE TRAITS, AND WHY THESE SIX
-----------------------------
Each was tested for the only property that makes a trait real: it must be stable
within a player across time AND spread across players. Measured over the first
half of each player's games against their second half:

    thinks too long          0.88     clock front-loaded    0.87
    error rate               0.83     knowledge breadth     0.77
    moves fast for him       0.76     plays on when lost    0.72

Ten more candidates were measured and rejected, and they are named here so
nobody rebuilds them: tilt -- one blunder causing the next -- is 0.18 and simply
is not real; aggression failed twice, at 0.23 as forcing-move share and 0.06
measured properly through wrong-register; errs-when-forcing 0.28; too-passive is
stable at 0.58 but has a spread of 0.009, so everyone is identical and it
separates nobody. Also weak and excluded: repeats-next-game 0.68,
notices-threats 0.65, endgame-weighted 0.64, opportunism 0.50.

ERROR RATE IS CARRIED BUT NOT SPOKEN
------------------------------------
It is the most stable thing here after the clock, and it is not a diagnosis: it
is how strong the player is. Telling someone their error rate is telling them
their rating back. It stays in the payload for ranking and measurement and has
no sentence.

THE CUTS ARE QUARTILES OF A MEASURED POPULATION, 48 players, 2026-09-28:

    thinks_long          q1 0.118  median 0.139  q3 0.175
    moves_fast           q1 0.055  median 0.084  q3 0.116
    clock_front_loaded   q1 0.391  median 0.468  q3 0.608
    plays_on_when_lost   q1 0.160  median 0.207  q3 0.237
    knowledge_breadth    q1 0.300  median 0.326  q3 0.363
    error_rate           q1 0.126  median 0.152  q3 0.170

A player inside the middle half gets NO sentence for that trait, because
"you are about average at this" is not worth a line on a page. Only the ends
say anything, and they say it without comparing.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

# Measured quartiles. (low_cut, high_cut) — outside them a trait speaks.
CUTS: Dict[str, tuple] = {
    "thinks_long": (0.118, 0.175),
    "moves_fast": (0.055, 0.116),
    "clock_front_loaded": (0.391, 0.608),
    "plays_on_when_lost": (0.160, 0.237),
    "knowledge_breadth": (0.300, 0.363),
    "error_rate": (0.126, 0.170),
}

# Carried for ranking and measurement, never rendered. See the module docstring.
SILENT_TRAITS = frozenset({"error_rate"})

# One sentence per end of each trait. No numbers, no grades, no comparison to
# other players. Written to be recognisable rather than flattering or damning --
# a player should read it and think "yes, that is me".
SENTENCES: Dict[str, Dict[str, str]] = {
    "thinks_long": {
        "high": "You take long thinks. When a position gets hard, you stop and work.",
        "low": "You keep moving. Long thinks are rare for you, even in sharp positions.",
    },
    "moves_fast": {
        "high": "A lot of your moves go in quickly, without a pause.",
        "low": "You give most moves a moment, rather than playing on instinct.",
    },
    "clock_front_loaded": {
        "high": "You spend most of your clock early, and finish games in a hurry.",
        "low": "You keep time back for later, so the end of the game is not rushed.",
    },
    "plays_on_when_lost": {
        "high": "You keep playing when the game has gone against you.",
        "low": "When a game turns bad, it tends to end soon after.",
    },
    "knowledge_breadth": {
        "high": "A lot of named ideas show up in your play.",
        "low": "The same few ideas carry most of your games.",
    },
}

MIN_MOVES = 400
MIN_TIMED_MOVES = 200


def describe(traits: Optional[Dict[str, float]]) -> List[Dict[str, str]]:
    """The sentences a player reads, for the traits that are at an end.

    A trait inside the middle half of the population says nothing. That is the
    honest outcome and it keeps the page short: most players will see two or
    three lines, not six.
    """
    lines: List[Dict[str, str]] = []
    for key, value in sorted((traits or {}).items()):
        if key in SILENT_TRAITS or key not in CUTS or value is None:
            continue
        low, high = CUTS[key]
        end = "high" if value >= high else "low" if value <= low else None
        if end is None:
            continue
        sentence = SENTENCES.get(key, {}).get(end)
        if sentence:
            lines.append({"trait": key, "end": end, "sentence": sentence})
    return lines


def build_profile(traits: Optional[Dict[str, float]],
                  moves: int, timed_moves: int) -> Dict[str, Any]:
    """The whole payload. `measured` is false when we have not watched enough.

    Saying nothing is a real answer here. A profile built on a handful of games
    describes the games, not the person.
    """
    enough = moves >= MIN_MOVES and timed_moves >= MIN_TIMED_MOVES
    return {
        "schema_version": "behaviour_profile.v1",
        "measured": bool(enough and traits),
        "reason": None if enough else "not enough games watched yet",
        "lines": describe(traits) if enough else [],
        # internal only: rates are numbers and are never rendered
        "_traits": dict(traits or {}),
    }
