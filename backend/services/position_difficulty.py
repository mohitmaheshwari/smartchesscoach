"""How hard was this position -- what does a typical player lose here?

docs/expected_points_scope.md.

"You erred" means almost nothing on its own. "You erred, and this was a
position almost nobody gets wrong" is coaching, and so is its opposite. The
base rate is the whole difference, and until now nothing in the product had
one.

WHAT IS MEASURED
----------------
For every cell of (phase, how level the position is, whether the opponent has
just made a threat, whether the move was already marked critical): the average
expected-points cost of a move there, over 519,661 user moves from 70 players.

The overall average is 0.0278 points. The cells run from 0.0013 to 0.1869 -- a
spread of 145x. Conditioning separates positions, and that was checked before
any of this shipped: if every cell had come out near the average, difficulty
would have been worth nothing and the right move would have been to drop it.

LEAKAGE WAS MEASURED, NOT ASSUMED
---------------------------------
The base rate is computed from the same players it then judges, and our largest
account holds 12% of the corpus, so its own baseline could have been partly its
own doing. Removing that account shifts the cell means by a median of 0.0001
and a worst case of 0.0035. One shared table is therefore fine and the
leave-one-player-out build it would otherwise have needed is not required.

THE THREE CLASSES ARE CLUSTERS IN THE DATA
------------------------------------------
Not chosen cut-points. The cells fall into three groups on their own:

    quiet, no threat, not critical      0.0013 - 0.0134
    a threat and nothing else           0.0279 - 0.0395
    a threat AND a critical moment      0.1008 - 0.1869

which is why the boundaries sit at 0.02 and 0.07, in the gaps.

WHAT THIS IS NOT
----------------
Not a comparison against other players -- 70 people cannot support one, and two
of them are in the 1400 band. "Typical" here means typical for the people we
have, which is the right reference for "most players at your level slip here"
and the wrong one for any general claim.

This module returns classes, never sentences. The words belong to the caption
layer, which is the single place coaching prose is written.

REFIT WHEN THE POPULATION CHANGES, exactly as with the expected-points table.
"""
from __future__ import annotations

from typing import Optional, Tuple

TABLE_VERSION = "position_difficulty.v1_measured_2026_09_29"
TOTAL_POSITIONS = 519661
OVERALL = 0.0278

# A cell thinner than this falls back to its phase-and-evaluation marginal.
# Chosen after seeing the cell sizes, not before: seven cells sit under it, the
# smallest holding nine positions.
MIN_CELL_N = 300

ROUTINE, TESTING, HARD = "routine", "testing", "hard"
# The gaps between the three clusters above.
ROUTINE_UNDER = 0.02
HARD_FROM = 0.07

_EVAL_BANDS = ((-600, "losing"), (-200, "worse"), (200, "level"),
               (600, "better"), (10 ** 9, "winning"))

# (phase, eval band, threat, critical) -> (mean expected-points cost, n)
DIFFICULTY = {
    ("endgame", "better", False, False): (0.0066, 4999),
    ("endgame", "better", False, True): (0.0449, 222),
    ("endgame", "better", True, False): (0.0343, 518),
    ("endgame", "better", True, True): (0.1836, 1371),
    ("endgame", "level", False, False): (0.0018, 10766),
    ("endgame", "level", False, True): (0.0702, 76),
    ("endgame", "level", True, False): (0.0279, 704),
    ("endgame", "level", True, True): (0.1869, 1461),
    ("endgame", "losing", False, False): (0.0046, 5440),
    ("endgame", "losing", False, True): (0.0031, 932),
    ("endgame", "losing", True, True): (0.0101, 1508),
    ("endgame", "winning", False, False): (0.0037, 5450),
    ("endgame", "winning", False, True): (0.0120, 1444),
    ("endgame", "winning", True, True): (0.1208, 1464),
    ("endgame", "worse", False, False): (0.0134, 5507),
    ("endgame", "worse", False, True): (0.0836, 113),
    ("endgame", "worse", True, False): (0.0395, 1077),
    ("endgame", "worse", True, True): (0.1030, 1220),
    ("middlegame", "better", False, False): (0.0064, 38360),
    ("middlegame", "better", False, True): (0.0718, 971),
    ("middlegame", "better", True, False): (0.0315, 7525),
    ("middlegame", "better", True, True): (0.1584, 12065),
    ("middlegame", "level", False, False): (0.0033, 41874),
    ("middlegame", "level", False, True): (0.0127, 381),
    ("middlegame", "level", True, False): (0.0286, 13257),
    ("middlegame", "level", True, True): (0.1236, 15161),
    ("middlegame", "losing", False, False): (0.0049, 14101),
    ("middlegame", "losing", False, True): (0.0042, 495),
    ("middlegame", "losing", True, True): (0.0157, 2820),
    ("middlegame", "winning", False, False): (0.0048, 19263),
    ("middlegame", "winning", False, True): (0.0267, 2454),
    ("middlegame", "winning", True, True): (0.1411, 3878),
    ("middlegame", "worse", False, False): (0.0106, 32884),
    ("middlegame", "worse", False, True): (0.0687, 82),
    ("middlegame", "worse", True, False): (0.0381, 10113),
    ("middlegame", "worse", True, True): (0.1073, 8860),
    ("opening", "better", False, False): (0.0057, 17789),
    ("opening", "better", False, True): (0.0793, 295),
    ("opening", "better", True, False): (0.0296, 4720),
    ("opening", "better", True, True): (0.1397, 8032),
    ("opening", "level", False, False): (0.0035, 133866),
    ("opening", "level", False, True): (0.0013, 517),
    ("opening", "level", True, False): (0.0280, 38837),
    ("opening", "level", True, True): (0.1008, 21344),
    ("opening", "losing", False, False): (0.0049, 1937),
    ("opening", "losing", False, True): (0.0117, 17),
    ("opening", "losing", True, True): (0.0196, 427),
    ("opening", "winning", False, False): (0.0059, 3336),
    ("opening", "winning", False, True): (0.0394, 316),
    ("opening", "winning", True, True): (0.1723, 785),
    ("opening", "worse", False, False): (0.0078, 10692),
    ("opening", "worse", False, True): (0.0653, 9),
    ("opening", "worse", True, False): (0.0382, 4111),
    ("opening", "worse", True, True): (0.1114, 3815),
}

BY_PHASE_EVAL = {
    ("endgame", "better"): (0.0440, 7110),
    ("endgame", "level"): (0.0244, 13007),
    ("endgame", "losing"): (0.0055, 7880),
    ("endgame", "winning"): (0.0256, 8358),
    ("endgame", "worse"): (0.0318, 7917),
    ("middlegame", "better"): (0.0418, 58921),
    ("middlegame", "level"): (0.0339, 70673),
    ("middlegame", "losing"): (0.0067, 17416),
    ("middlegame", "winning"): (0.0276, 25595),
    ("middlegame", "worse"): (0.0326, 51939),
    ("opening", "better"): (0.0450, 30836),
    ("opening", "level"): (0.0191, 194564),
    ("opening", "losing"): (0.0076, 2381),
    ("opening", "winning"): (0.0377, 4437),
    ("opening", "worse"): (0.0358, 18627),
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

    Move number is what every analysed move actually carries. Material would be
    better for telling a middlegame from an endgame and would need the board
    parsed for half a million positions to find out how much better.
    """
    if move_number is None:
        return "middlegame"
    if move_number <= 15:
        return "opening"
    return "middlegame" if move_number <= 40 else "endgame"


def base_rate(phase: str, eval_cp: Optional[float],
              has_threat: bool, is_critical: bool) -> Tuple[float, int, str]:
    """(what a typical player loses here, positions behind it, where it came from).

    The source matters to the caller: a rate resting on nine positions is not a
    base rate, so thin cells fall back rather than answer confidently.
    """
    band = band_of(eval_cp)
    cell = DIFFICULTY.get((phase, band, bool(has_threat), bool(is_critical)))
    if cell and cell[1] >= MIN_CELL_N:
        return cell[0], cell[1], "cell"
    marginal = BY_PHASE_EVAL.get((phase, band))
    if marginal:
        return marginal[0], marginal[1], "phase_eval"
    return OVERALL, TOTAL_POSITIONS, "overall"


def difficulty_class(phase: str, eval_cp: Optional[float],
                     has_threat: bool, is_critical: bool) -> str:
    """routine / testing / hard, on the clusters in the measured table."""
    rate, _, _ = base_rate(phase, eval_cp, has_threat, is_critical)
    if rate < ROUTINE_UNDER:
        return ROUTINE
    return HARD if rate >= HARD_FROM else TESTING


def relative_error(actual_loss: Optional[float], phase: str,
                   eval_cp: Optional[float], has_threat: bool,
                   is_critical: bool) -> Optional[float]:
    """This move's cost against what the position usually costs.

    1.0 is exactly typical. Above 1.0 is worse than the position explains, and
    that -- not the raw cost -- is what makes a mistake worth raising. A move
    losing a tenth of a point where the average is a tenth of a point is the
    position doing the work, not the player.
    """
    if actual_loss is None:
        return None
    rate, _, _ = base_rate(phase, eval_cp, has_threat, is_critical)
    return actual_loss / max(rate, 1e-6)
