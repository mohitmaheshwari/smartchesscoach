"""What a position is actually worth to OUR players, in game points.

docs/expected_points_scope.md.

WHY NOT CENTIPAWNS
------------------
Every gate in the product asks "how many centipawns did this move lose?", and
that question means something different in every position it is asked about.
Measured on 146,465 user moves:

    of the moves we flag today (cp_loss >= 150)
        23.0% cost less than a tenth of a point
        16.4% fired in a position that was already decided
    of the moves we ignore today (cp_loss < 150)
        2,959 cost a tenth of a point or more, 2,585 of them from a level
        position -- the ones that actually decide games

So the scale is wrong, not the detectors.

WHY NOT THE PUBLISHED CURVE
---------------------------
The widely used logistic (k = 0.00368) is fitted to strong play. Fitted to
ours it comes out at k = 0.00228, a little over half as steep, and a bootstrap
over games puts the interval at 0.00225 to 0.00235 -- the public value is
nowhere near it. An advantage is worth far less to a 900 player than that curve
claims, and a disadvantage is far less fatal.

WHY A TABLE AND NOT A FORMULA
-----------------------------
A two-parameter logistic was fitted first and rejected on its own residuals: it
reads 0.932 at +1200 where these players actually score 0.881, and 0.125 at
-800 where they actually score 0.084. It cannot represent the real shape,
because at 600-1500 nothing is ever finished:

    ceiling 0.873 -- even a completely winning position is thrown away about
                     one time in eight
    floor   0.093 -- even a completely lost one is saved about one in eleven

No logistic has a ceiling below 1.0. So the measured curve IS the model.

PROVENANCE
----------
Fitted 2026-09-29 on 518,265 user-move positions from 17,426 finished games,
50-centipawn buckets, buckets under 150 positions dropped, monotonicity imposed
by pool-adjacent-violators and a three-bucket smooth. Mate scores held out.
Bootstrapped over GAMES, never over positions: positions inside one game share
an outcome, so the game is the unit.

    eval    90% interval over games
    -600    0.125 .. 0.147
    -200    0.377 .. 0.405
       0    0.441 .. 0.459
    +200    0.559 .. 0.576
    +600    0.798 .. 0.817
   +1000    0.862 .. 0.894

An even position is worth 0.475, not 0.5, because these players lose rather
more games than they win. A curve pinned to 0.5 at an even evaluation cannot
express that, and fitting the intercept cut the error by 61%.

REFIT WHEN THE POPULATION CHANGES. These numbers describe the players we have.
If the rating mix moves, the table moves with it, and `TABLE_FITTED_ON`
records what it was fitted against so the drift is visible.
"""
from __future__ import annotations

from typing import Optional

TABLE_VERSION = "expected_points.v1_measured_2026_09_29"
TABLE_FITTED_ON = {
    "positions": 518265,
    "games": 17426,
    "bucket_cp": 50,
    "fitted_at": "2026-09-29",
}

# Centipawns from the PLAYER's own side -> expected game points.
EP_TABLE = {
    -1500: 0.0931, -1250: 0.0931, -1200: 0.0931, -1150: 0.0931,
    -1100: 0.0931, -1050: 0.0931, -1000: 0.0931, -950: 0.0931,
    -900: 0.0931, -850: 0.0931, -800: 0.0943, -750: 0.1007,
    -700: 0.1106, -650: 0.1234, -600: 0.1436, -550: 0.1733,
    -500: 0.2084, -450: 0.2438, -400: 0.2756, -350: 0.3077,
    -300: 0.3388, -250: 0.3666, -200: 0.3913, -150: 0.4091,
    -100: 0.4303, -50: 0.4447, 0: 0.4746, 50: 0.5002,
    100: 0.5330, 150: 0.5498, 200: 0.5719, 250: 0.5902,
    300: 0.6131, 350: 0.6374, 400: 0.6676, 450: 0.7003,
    500: 0.7353, 550: 0.7709, 600: 0.7994, 650: 0.8158,
    700: 0.8263, 750: 0.8373, 800: 0.8478, 850: 0.8599,
    900: 0.8673, 950: 0.8730, 1000: 0.8730, 1050: 0.8730,
    1100: 0.8730, 1150: 0.8730, 1200: 0.8730, 1250: 0.8730,
    1300: 0.8730, 1500: 0.8730,
}

_KEYS = sorted(EP_TABLE)
FLOOR = EP_TABLE[_KEYS[0]]
CEILING = EP_TABLE[_KEYS[-1]]
EVEN = EP_TABLE[0]


def expected_points(cp: Optional[float],
                    mate_in: Optional[int] = None) -> Optional[float]:
    """Expected game points, 0 to 1, from the player's own side.

    `cp` is centipawns already flipped to the player's perspective -- this
    module never guesses a colour, because `eval_before` is stored
    white-relative and a silent flip is how that becomes a bug.

    `mate_in` is a mate distance, also from the player's side: positive when
    they are delivering it, negative when they are receiving it.

    A mate maps to the ceiling or the floor rather than to 1.0 or 0.0, and that
    is deliberate. The ceiling IS what a completely winning position is worth to
    these players, and a forced mate they have not spotted is not worth more
    than that. Whether they convert a *detected* forced mate more reliably than
    an ordinary winning position is a real question and an unmeasured one; if it
    is ever measured this is the line to change.
    """
    if mate_in is not None:
        if mate_in > 0:
            return CEILING
        if mate_in < 0:
            return FLOOR
        # mate_in == 0 means the mate has been delivered: the game is over and
        # the point is banked, which is the one case that really is 1.0.
        return 1.0
    if cp is None:
        return None

    value = max(_KEYS[0], min(_KEYS[-1], float(cp)))
    lo = _KEYS[0]
    for key in _KEYS:
        if key <= value:
            lo = key
        else:
            hi = key
            span = hi - lo
            if span <= 0:
                return EP_TABLE[lo]
            weight = (value - lo) / span
            return EP_TABLE[lo] + weight * (EP_TABLE[hi] - EP_TABLE[lo])
    return EP_TABLE[_KEYS[-1]]


def ep_loss(cp_before: Optional[float], cp_after: Optional[float],
            mate_before: Optional[int] = None,
            mate_after: Optional[int] = None) -> Optional[float]:
    """What the move cost, in game points. Never negative.

    Both evaluations must already be from the player's own side. A move that
    improves the position costs nothing rather than a negative amount, because
    "you gained half a point here" is not a thing any detector should act on --
    the engine's best move is the reference, not the move played.
    """
    before = expected_points(cp_before, mate_before)
    after = expected_points(cp_after, mate_after)
    if before is None or after is None:
        return None
    return max(0.0, before - after)


def headroom(cp: Optional[float], mate_in: Optional[int] = None) -> Optional[float]:
    """How much there still is to lose from here.

    This replaces asking whether a position is "already decided", which was
    always the wrong question -- it was asked of the evaluation when it is
    really about how far the position can still fall. At +900 the answer is
    0.774, which is why a collapse from a winning position is the largest
    single thing a player can do to themselves, and why a mistake at -1200 is
    worth almost nothing and should not be raised.
    """
    value = expected_points(cp, mate_in)
    return None if value is None else max(0.0, value - FLOOR)
