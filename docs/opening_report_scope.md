# Opening knowledge — say which openings cost him games

**Status: DRAFT, awaiting Mohit's signoff. No code until then.**
Written 2026-09-26. Mohit: *"look at the games and find opening accuracy backed
by stockfish and our opening.json ... very very simple"*.

---

## Why opening_knowledge is the one topic that cannot be promoted

It has exactly one authorized detector, `left_book_for_a_worse_move`, and it
fires **twice in the entire product, across two users**. So the topic is mute,
and promoting it today would hand roughly 45 people a focus backed by two
events.

The detector is not broken so much as aimed at a hard problem: it tries to
catch the player leaving theory for a worse move, which needs the book to
match his move history. Opening detectors are also fed a half history
elsewhere in this codebase, so book lines rarely match at all.

**Nothing about the useful signal requires the book.** Which openings cost him
material is already computable from data we store on every game.

## What a player sees

### On the areas card, one line

```
  Playing the opening        Needs work
```

### On the opening report itself

```
  WHERE YOUR OPENINGS STAND

  Best        London System          you rarely slip here
              Ruy Lopez
              Philidor Defence

  Worst       Bishop's Opening       this one costs you most
              Giuoco Piano
              Scotch Game

  The Bishop's Opening costs you more mistakes than any other
  opening you play. Learn it, or stop playing it.

  [ Learn the Bishop's Opening ]        <- only when a tree exists
```

No numbers, per the standing rule. The ordering carries the information; the
rate chooses the words and never appears in them.

## His real data, which is the argument for building it

Measured 2026-09-26 from his 829 games:

```
  family                  games   opening moves   errors per 100
  London System              18             134             2.2
  Ruy Lopez                  28             293             7.5
  Philidor Defense           42             501             8.8
  Queens Gambit              34             415             8.9
  Italian Game              110           1,149            10.8
  Scandinavian Defense       61             862            11.5
  Kings Pawn Opening         38             529            15.7
  Scotch Game                20             277            15.9
  Giuoco Piano               47             649            16.5
  Bishops Opening            28             398            18.6
```

**This inverted the premise we started from.** The idea was that a player who
sticks to too few openings needs to broaden. He has played **54 families**,
only 16 of them once or twice. He is not narrow. The coaching is not "broaden"
— it is "the Bishop's Opening costs you eight times what the London does".

Had we shipped the broaden-if-narrow rule, it would have told him to widen a
repertoire that is already wide, which is the opposite of what his games say.

## The cuts, taken from the distribution rather than chosen

Across 1,625 user-and-family pairs:

**How many games before we say anything.** 30.3% of pairs have ONE game and
56.1% have three or fewer. A rate over one game is noise with a decimal point.

```
  >= 5 games AND >= 40 opening moves   -> eligible to be judged
```

That leaves 610 pairs product-wide, which is enough to rank and few enough
that every line has something behind it.

**What counts as weak.** Errors per 100 opening moves among eligible pairs:

```
  min 0.0   q1 9.6   median 13.4   q3 17.9   max 40.8
```

So the bands are that distribution, not round numbers: below q1 is where he
plays well, above q3 is where he does not. His Bishop's Opening at 18.6 is
past q3; his London at 2.2 is below the minimum quartile of the whole
population.

## Closing the loop into the curriculum

A weakness with no lesson behind it is a report, not coaching. Checked against
`opening_curriculum.json` (79 openings):

```
  Bishops Opening        teachable tree     yes
  Scotch Game            teachable tree     yes
  Scandinavian Defense   teachable tree     yes
  Italian Game           teachable tree     yes
  Giuoco Piano           NO TREE
  Kings Pawn Opening     NO TREE
  Queens Pawn Opening    NO TREE
```

So the "learn it" button appears only where a tree exists, and where none
does the line still names the cost without offering a door that opens onto
nothing.

## In scope

- An opening report per user: families ranked by errors per 100 opening moves,
  gated at 5 games and 40 moves.
- One sentence naming the worst family, with the curriculum link when the
  opening has a tree.
- A `gap:opening_knowledge:` id backed by this, so the topic becomes
  promotable on evidence instead of on two events.

## Out of scope

- Replacing or deleting `left_book_for_a_worse_move`. It is not wrong, it is
  rare; leave it at shadow.
- Move-by-move opening theory coaching. This says which opening hurts, not
  which move in it.
- Colour split (his White repertoire vs Black). Real and worth doing, but it
  halves every sample and the counts above are already thin at the tail.

## Two holes I would rather name than hide

**65 of his 829 games carry an opening name my grouping could not place**, and
they sit at 16.0 errors per 100 — worse than his average. A sixth of the
evidence is in a bucket called "unknown", which will distort any ranking built
on the rest. The grouping must use the canonical recognizer
(`opening_book.recognize_opening_from_history`) rather than the prefix match I
used to measure this, or that bucket stays.

**The tails are thin even after gating.** London System is 18 games and 134
opening moves. The ranking is directionally right; the exact order of the top
three and bottom three is not stable, and the copy must not imply it is —
"you rarely slip here" survives a sample wobble, "your best opening" does not.

## What would say this failed

He reads the report, plays the named opening ten more times, and his errors
per 100 in that family does not move. That is measurable from the same
numbers, per user, with no new instrumentation.
