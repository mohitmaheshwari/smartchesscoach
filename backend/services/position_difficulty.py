"""How hard was this position -- what does a typical player lose here?

docs/expected_points_scope.md.

"You erred" means almost nothing on its own. "You erred, and this was a
position almost nobody gets wrong" is coaching, and so is its opposite. The
base rate is the whole difference, and until now nothing in the product had
one.

WHAT IS MEASURED
----------------
For every cell of (phase, how level the position is, whether the opponent has
just made a threat): the average expected-points cost of a move there, over
519,776 user moves from 70 players. Overall 0.0278; the cells run 0.0023 to
0.1723, a spread of 75x.

WHY is_critical IS NOT A FEATURE -- IT WAS, AND IT WAS CIRCULAR
---------------------------------------------------------------
The first version conditioned on `is_critical` too, and on the whole corpus it
looked better: a 145x spread rather than 75x. It was useless where it mattered.

`is_critical` is set upstream FROM cp_loss. The caption layer then selects
moves BY cp_loss. So applying an is_critical-conditioned table to captioned
moves asks a question whose answer is already contained in the selection, and
the split collapses:

    with is_critical      routine  6.7%   testing  2.8%   hard 90.5%
    without               routine  9.7%   testing 24.1%   hard 65.5%

Nine cases in ten landing in one class is a table that tells the caller nothing
it did not already know. Dropping the circular feature costs spread on paper
and buys the only thing the table is for.

The general trap: a feature derived from the same quantity the caller gates on
cannot condition that caller. Check what a feature is computed FROM, not just
whether it separates.

LEAKAGE WAS MEASURED, NOT ASSUMED
---------------------------------
The base rate comes from the same players it judges, and our largest account
holds 12% of the corpus, so its baseline could have been partly its own doing.
Removing that account shifts cell means by a median of 0.0001 and a worst case
of 0.0035, so one shared table is fine and the leave-one-player-out build it
would otherwise have needed is not required.

THE THREE CLASSES ARE CLUSTERS IN THE DATA
------------------------------------------
Not chosen cut-points. Quiet positions sit at 0.0023-0.0148, a threat in a
losing or level position at 0.0101-0.0538, and a threat with something to play
for at 0.0704-0.1723. The boundaries sit at 0.02 and 0.07, in the gaps.

WHAT THIS IS NOT
----------------
Not a comparison against other players -- 70 people cannot support one, and two
of them are in the 1400 band. "Typical" means typical for the people we have,
which is the right reference for "most players at your level slip here" and the
wrong one for any general claim.

This module returns classes, never sentences. The words belong to the caption
layer, which is the single place coaching prose is written.

REFIT WHEN THE POPULATION CHANGES, exactly as with the expected-points table.
"""
from __future__ import annotations

from typing import Optional, Tuple

TABLE_VERSION = "position_difficulty.v2_no_is_critical_2026_09_29"
TOTAL_POSITIONS = 519776
OVERALL = 0.0278

# A cell thinner than this falls back to its phase-and-evaluation marginal. No
# cell in the v2 table is below it -- the smallest holds 427 -- but the fallback
# stays, because a refit on a different population may well produce one.
MIN_CELL_N = 300

ROUTINE, TESTING, HARD = "routine", "testing", "hard"
# The gaps between the three clusters above.
ROUTINE_UNDER = 0.02
HARD_FROM = 0.07

_EVAL_BANDS = ((-600, "losing"), (-200, "worse"), (200, "level"),
               (600, "better"), (10 ** 9, "winning"))

# (phase, eval band, opponent has just threatened) -> (mean cost, n)
DIFFICULTY = {
    ("endgame", "better", False): (0.0082, 5221),
    ("endgame", "better", True): (0.1427, 1889),
    ("endgame", "level", False): (0.0023, 10842),
    ("endgame", "level", True): (0.1352, 2165),
    ("endgame", "losing", False): (0.0044, 6373),
    ("endgame", "losing", True): (0.0101, 1508),
    ("endgame", "winning", False): (0.0054, 6894),
    ("endgame", "winning", True): (0.1208, 1464),
    ("endgame", "worse", False): (0.0148, 5626),
    ("endgame", "worse", True): (0.0733, 2300),
    ("middlegame", "better", False): (0.0080, 39342),
    ("middlegame", "better", True): (0.1097, 19599),
    ("middlegame", "level", False): (0.0034, 42263),
    ("middlegame", "level", True): (0.0793, 28422),
    ("middlegame", "losing", False): (0.0049, 14602),
    ("middlegame", "losing", True): (0.0157, 2820),
    ("middlegame", "winning", False): (0.0073, 21718),
    ("middlegame", "winning", True): (0.1411, 3879),
    ("middlegame", "worse", False): (0.0108, 32979),
    ("middlegame", "worse", True): (0.0704, 18980),
    ("opening", "better", False): (0.0069, 18085),
    ("opening", "better", True): (0.0990, 12755),
    ("opening", "level", False): (0.0035, 134409),
    ("opening", "level", True): (0.0538, 60195),
    ("opening", "losing", False): (0.0050, 1954),
    ("opening", "losing", True): (0.0196, 427),
    ("opening", "winning", False): (0.0088, 3652),
    ("opening", "winning", True): (0.1723, 785),
    ("opening", "worse", False): (0.0079, 10701),
    ("opening", "worse", True): (0.0734, 7927),
}

BY_PHASE_EVAL = {
    ("endgame", "better"): (0.0440, 7110),
    ("endgame", "level"): (0.0244, 13007),
    ("endgame", "losing"): (0.0055, 7881),
    ("endgame", "winning"): (0.0256, 8358),
    ("endgame", "worse"): (0.0318, 7926),
    ("middlegame", "better"): (0.0418, 58941),
    ("middlegame", "level"): (0.0339, 70685),
    ("middlegame", "losing"): (0.0067, 17422),
    ("middlegame", "winning"): (0.0276, 25597),
    ("middlegame", "worse"): (0.0326, 51959),
    ("opening", "better"): (0.0450, 30840),
    ("opening", "level"): (0.0191, 194604),
    ("opening", "losing"): (0.0076, 2381),
    ("opening", "winning"): (0.0377, 4437),
    ("opening", "worse"): (0.0358, 18628),
}


def band_of(cp: Optional[float]) -> str:
    """Which evaluation band, from the PLAYER's own side."""
    if cp is None:
        return "level"
    for edge, name in _EVAL_BANDS:
        if cp < edge:
            return name
    return "winning"


def phase_of(move_number: Optional[int]) -> str:
    """Coarse, and deliberately so: no phase is stored on a move evaluation.

    Move number is what every analysed move actually carries. Material would
    tell a middlegame from an endgame properly and would need the board parsed
    for half a million positions to find out how much better.
    """
    if move_number is None:
        return "middlegame"
    if move_number <= 15:
        return "opening"
    return "middlegame" if move_number <= 40 else "endgame"


def base_rate(phase: str, eval_cp: Optional[float],
              has_threat: bool) -> Tuple[float, int, str]:
    """(what a typical player loses here, positions behind it, where it came from).

    The source matters to the caller: a rate resting on a handful of positions
    is not a base rate, so thin cells fall back rather than answer confidently.
    """
    band = band_of(eval_cp)
    cell = DIFFICULTY.get((phase, band, bool(has_threat)))
    if cell and cell[1] >= MIN_CELL_N:
        return cell[0], cell[1], "cell"
    marginal = BY_PHASE_EVAL.get((phase, band))
    if marginal:
        return marginal[0], marginal[1], "phase_eval"
    return OVERALL, TOTAL_POSITIONS, "overall"


def difficulty_class(phase: str, eval_cp: Optional[float],
                     has_threat: bool) -> str:
    """routine / testing / hard, on the clusters in the measured table."""
    rate, _, _ = base_rate(phase, eval_cp, has_threat)
    if rate < ROUTINE_UNDER:
        return ROUTINE
    return HARD if rate >= HARD_FROM else TESTING


def relative_error(actual_loss: Optional[float], phase: str,
                   eval_cp: Optional[float], has_threat: bool) -> Optional[float]:
    """This move's cost against what the position usually costs.

    1.0 is exactly typical. Above 1.0 is worse than the position explains, and
    that -- not the raw cost -- is what makes a mistake worth raising. A move
    losing a tenth of a point where the average is a tenth of a point is the
    POSITION doing the work, not the player.

    Measured across the 88,714 moves that pass the caption gate today: 63.0% sit
    at or below 1.0, and 10.2% are more than twice what the position explains.
    That second group is the one a coach should be talking about.
    """
    if actual_loss is None:
        return None
    rate, _, _ = base_rate(phase, eval_cp, has_threat)
    return actual_loss / max(rate, 1e-6)
