"""Grade every part of a player's game, so they can see more than one focus.

Today a player sees exactly one area -- piece safety -- because that is the
only topic authorised to drive a plan. Mohit's own account carries 671
piece-safety mistakes and 1,524 in five other areas that no screen mentions,
plus a whole opening/middlegame/endgame split that is computed on every move
and has never been shown.

Grading is display-only. It reads stored observations and asserts nothing
about what the player should do next, so it needs no authorization id and is
not gated by detector quality. That is deliberate: showing someone where they
stand should not wait on the promotion queue.

HOW THE BANDS WERE SET
----------------------
Mistakes and blunders in an area, per game, so a player with 400 games is not
graded worse than one with 20 for playing more. Measured across 54 users with
at least 5 games each:

    area                 q1     median   q3
    piece_safety         1.09   1.27     1.56
    king_safety          0.67   0.80     0.88
    missed_tactic        0.53   0.63     0.75
    opening_knowledge    0.37   0.50     0.69
    endgame_technique    0.14   0.26     0.39
    tactical_oversight   0.20   0.25     0.35

    opening              1.81   2.34     2.69
    middlegame           1.66   2.07     2.43
    endgame              0.26   0.50     0.70

EVERY AREA GETS ITS OWN BANDS, and this is the whole reason the table above is
in the file. 0.4 mistakes a game is better than three quarters of players at
piece safety and worse than three quarters at endgame technique. A shared
Excellent/Good/Fair/Poor scale applied to one number would call the same
player strong and weak for the same behaviour. Grades here are always
relative to what other players do in THAT area.

Lower is better everywhere: these count mistakes, not achievements.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

# Quartiles measured 2026-09-25. Regenerate from the same query if the user
# base changes shape; do not hand-tune.
_BANDS: Dict[str, Dict[str, float]] = {
    "piece_safety":       {"q1": 1.09, "med": 1.27, "q3": 1.56},
    "king_safety":        {"q1": 0.67, "med": 0.80, "q3": 0.88},
    "missed_tactic":      {"q1": 0.53, "med": 0.63, "q3": 0.75},
    "opening_knowledge":  {"q1": 0.37, "med": 0.50, "q3": 0.69},
    "endgame_technique":  {"q1": 0.14, "med": 0.26, "q3": 0.39},
    "tactical_oversight": {"q1": 0.20, "med": 0.25, "q3": 0.35},
    "opening":            {"q1": 1.81, "med": 2.34, "q3": 2.69},
    "middlegame":         {"q1": 1.66, "med": 2.07, "q3": 2.43},
    "endgame":            {"q1": 0.26, "med": 0.50, "q3": 0.70},
}

# Plain words. No chess terms a beginner would have to look up.
LABELS: Dict[str, str] = {
    "piece_safety":       "Keeping pieces safe",
    "king_safety":        "Keeping your king safe",
    "missed_tactic":      "Spotting tactics",
    "opening_knowledge":  "Playing the opening",
    "endgame_technique":  "Playing the endgame",
    "tactical_oversight": "Seeing one move deeper",
    "opening":            "The opening",
    "middlegame":         "The middlegame",
    "endgame":            "The endgame",
}

AREAS = ("piece_safety", "king_safety", "missed_tactic",
         "opening_knowledge", "endgame_technique", "tactical_oversight")
PHASES = ("opening", "middlegame", "endgame")

GRADES = ("Excellent", "Good", "Fair", "Needs work")

# Below this a rate is noise. A player with three games has not shown us
# anything, and a confident grade there is a lie with a label on it.
MIN_GAMES = 5


def grade_for_rate(key: str, rate: float) -> Optional[str]:
    """Where this rate sits against what other players do in THIS area."""
    band = _BANDS.get(key)
    if band is None or rate is None:
        return None
    if rate <= band["q1"]:
        return "Excellent"
    if rate <= band["med"]:
        return "Good"
    if rate <= band["q3"]:
        return "Fair"
    return "Needs work"


def grade_areas(
    counts: Dict[str, int],
    games_played: int,
) -> Dict[str, Any]:
    """Grade every area and phase for one player.

    `counts` maps area/phase key -> number of mistakes and blunders.
    Returns areas and phases separately, each worst-first so the things worth
    working on are at the top.

    An area the player has never shown a mistake in still grades: zero
    mistakes a game is Excellent and is the honest reading. An area we have
    not seen ENOUGH GAMES to judge returns measured=False instead of a grade,
    rather than scoring absence as perfection.
    """
    enough = games_played >= MIN_GAMES

    def row(key: str) -> Dict[str, Any]:
        n = int(counts.get(key, 0) or 0)
        rate = (n / float(games_played)) if games_played else None
        return {
            "key": key,
            "label": LABELS.get(key, key),
            "measured": bool(enough),
            "grade": grade_for_rate(key, rate) if enough else None,
            # internal only -- never rendered, per the no-numbers rule
            "_rate": rate,
            "_mistakes": n,
        }

    def ordered(keys) -> List[Dict[str, Any]]:
        rows = [row(k) for k in keys]
        # Worst first. Unmeasured rows sit at the end rather than pretending
        # to be perfect, which is the bug the thinking-habits card just hit.
        order = {g: i for i, g in enumerate(reversed(GRADES))}
        rows.sort(key=lambda r: (r["measured"] is False,
                                 order.get(r["grade"], 99),
                                 -(r["_rate"] or 0)))
        return rows

    return {
        "measured": bool(enough),
        "games_played": games_played,
        "areas": ordered(AREAS),
        "phases": ordered(PHASES),
    }


def counts_from_observations(observations) -> Dict[str, int]:
    """Mistake and blunder counts per area and per phase.

    Counts a move once for its area and once for its phase, so the two lists
    answer different questions about the same games rather than double-
    counting inside one list.
    """
    counts: Dict[str, int] = {}
    for obs in observations or []:
        if obs.get("execution_quality") not in ("mistake", "blunder"):
            continue
        area = obs.get("missed_pattern")
        if area:
            counts[area] = counts.get(area, 0) + 1
        phase = obs.get("phase")
        if phase:
            counts[phase] = counts.get(phase, 0) + 1
    return counts
