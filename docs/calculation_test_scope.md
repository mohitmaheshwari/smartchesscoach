# Showing your working

*Scope for sign-off. Written 2026-10-01.*

## The problem

We cannot tell from someone's games whether they calculate.

Everything the product measures is what happened after they moved. Measured on
10,679 mistakes across 46 players, the move that punishes them lands on the very
next move about six times in ten, and the kind of move that catches them out is
stable enough to describe. All of that is real, and none of it says how far the
player can actually see. The same good move can come from working it out, from
recognising the pattern, from a guess, or from luck.

And every answer the product has ever asked for is a single move.
`best_move_san`, in training, in the diagnostic, in missions, in play. We have
never once asked a player to show the line. So we measure whether they spot the
first move and nothing after it.

## What this is

One position from one of their own games. We ask them to play out the line
without moving the pieces, as far as they think it goes, and then say how it
ends.

They enter their move, then the opponent's best answer, then their reply, and
so on — as deep as they want to take it. **The line is not a fixed length.**
Some positions resolve in three half-moves and some take nine, and a player who
can see five is a different player from one who can see two. A fixed box would
measure the box.

When they stop, they say what the position is then: they are winning, it is
about equal, or they are worse.

## What we check

Stockfish already knows the sound line. So we can check three separate things,
and they are three different skills:

1. **Did they find the first move?** Spotting the idea.
2. **How far does their line stay sound?** Each half-move they entered either
   keeps the idea alive or does not. The first one that does not is where their
   sight ends.
3. **Were they right about how it ends?** A player can see six half-moves
   correctly and still think a drawn position is winning.

The position also has a depth of its own — how far you must see before the
outcome is settled. If someone stops at three half-moves on a position that
needs seven, they stopped early, which is different from being wrong.

## What the player gets back

The line they entered, with the first wrong half-move marked, and what the
sound continuation was from there. Plain, no score.

Over several of these, one sentence: how far they see reliably, and whether
they stop too early or go wrong.

## What we can honestly claim from it

That they could or could not work out a specific line, in a position taken from
their own game, with no clock on them.

## What we cannot claim

That they do this at the board. A test has no clock, no tension and no doubt
about whether a tactic is even there. A player who solves these and still walks
into the same thing in a game has a different problem, and naming that
difference is the whole point of pairing the two.

We also cannot say they calculated rather than remembered. A familiar pattern
produces a correct line.

## How we will know it works

Before it ships to anyone but Mohit:

- **It has to separate people.** If everyone's line breaks at the same
  half-move, the test is not measuring a difference and we stop.
- **It has to agree with itself.** The same player on two different positions
  of similar depth should look similar. If not, it is measuring the position.
- **It has to disagree with the games in an interesting way.** If the test
  ranks players exactly as their error rate already does, it has told us
  nothing new and is not worth the player's time.

Each is a measurement, not an opinion, and each can stop this.

## Not in the first version

- No tree of opponent alternatives. One sound line, checked.
- No difficulty matrix. The spread of depths at 600-1500 is too narrow to fill
  one, and inventing the bands before seeing the distribution is how we have
  got thresholds wrong before.
- No scores, no percentages, no comparison to other players on screen.
- No positions that are not from the player's own games, until the thing works.

## Open question for sign-off

How many of these would you ask someone to do, and when? A test with no clock
is slow and nobody will do ten. My instinct is one, offered after a game review
where the mistake was a missed line — so the position is one they have just
been looking at. But that is a product call and I would rather you made it.
