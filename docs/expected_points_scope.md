# Expected points, and how hard the position was

*Scope for sign-off. Written 2026-09-29.*

## The problem in one sentence

Every gate in the product asks "how many centipawns did this move lose?", and
that question has a different meaning in every position it is asked about.

Losing 200 centipawns from a level position can turn a game. Losing 200 from a
position that was already lost changes almost nothing. Losing 60 when the game
is exactly balanced can be the whole game. Today all three are scored the same
way, so we scold a player for a "blunder" in a game that was already gone, and
we say nothing at all about the quiet slip that actually cost them the point.

## What we will build

**One. An expected-points scale.**

Convert the engine's evaluation into the thing a player actually cares about:
how likely this position is to end in a win, a draw or a loss — expressed as
points from 0 to 1, always from the player's own side.

A move's cost becomes the drop in expected points, not the drop in centipawns.

The conversion is **calibrated on our own games**, not taken from a published
formula. Published curves are fitted to strong play. Our players are 600 to
1500, and at that level an advantage converts far less reliably than it does at
2000 — a rook up is not the same thing to a 700 player as it is to a
grandmaster. We have 18,143 games with results, which is plenty to fit a curve
with one or two parameters. We will also report how far our curve sits from the
standard one, because if they turn out to be the same, the simpler thing wins.

Mate scores get their own handling. "Mate in three" is not a large number of
centipawns and must never be treated as one.

**Two. How hard the position was.**

For each position, an estimate of what an ordinary player at this level loses
here. Built from the features we already store — phase of the game, how level
the position is, whether the opponent has just made a threat, whether the move
was already marked critical.

That turns "you lost half a point here" into the two sentences a coach actually
says: *this was a hard position and most people slip* or *this was
straightforward and you dropped it*.

## What changes for the person using it

Nothing new appears on any screen. This changes what the existing coaching
decides to talk about:

- mistakes in games that were already decided stop being raised
- quiet slips in balanced positions start being raised
- when we do raise something, we can say whether it was hard

No number from any of this is ever shown. No percentage, no scale, no score out
of a hundred, no comparison to other players.

## What we are deliberately not building

**A comparison against other players.** It needs a population, and we have 70
players — two of them in the 1400 band. Everything here compares a player to
themselves and to the position, never to a leaderboard.

**New detectors.** We have 68 and seven of them can reach a person. This makes
the ones we already ship better rather than adding more.

**Anything that needs the engine's other candidate moves.** We store the best
line and the played line, and nothing else. That is a separate, costed decision.

## How we will know whether it was worth doing

Measured before writing any of it, on the real corpus:

- of the moves we flag today, how many cost almost nothing in expected points
- of the moves we ignore today, how many cost a lot
- how many of our current flags fire in a position that was already decided

If those numbers are small, this is not worth building and we stop. If they are
large, they are the size of the win.

**Measured 2026-09-29, on 146,465 user moves from 5,000 games:**

```
FLAGGED TODAY  (cp_loss >= 150):          18,031
   costs under 10 points in 100:           4,152  (23.0%)
   fired in an already decided position:   2,950  (16.4%)

IGNORED TODAY  (cp_loss < 150):          128,434
   costs 10+ points in 100:                2,959  ( 2.3%)
   of those, from a balanced position:     2,585
```

Nearly a quarter of what we call a mistake barely moved the game, and one in six
fires at someone whose game was already decided. About 39% of what the coach
talks about changes. Worth building.

**The curve, fitted 2026-09-29 on 518,265 positions from 17,426 games:**

Our players' curve is a little over half as steep as the published one
(k = 0.00228 against 0.00368), and a bootstrap over games puts the interval at
0.00225 to 0.00235 — the public value is nowhere near it.

A two-parameter logistic was fitted first and rejected on its own residuals: it
reads 0.932 at +1200 where these players actually score 0.881. The real curve
has a **ceiling of 0.873** and a **floor of 0.093** — at this level nothing is
ever finished, and no logistic has a ceiling below 1.0. So the measured table is
the model.

An even position is worth **0.475**, not 0.5, because this population loses
rather more games than it wins. Fitting that intercept cut the error by 61%.

## How it is checked

- the curve is checked against held-out games: when it says a position is worth
  0.7 points, those positions should actually be worth about 0.7 points
- the difficulty estimate is checked the same way
- both are fitted on positions, not on players, so the small number of players
  limits how far the result can be generalised but does not stop the fit
- the existing test suites must still pass, and the change to each detector's
  fire count is reported per detector, never as one headline number
