# Home as a coaching session — scope

Mohit, 2026-10-07, after rejecting four rounds of card layouts: *"think as a
user, you're a chess player and you open chessguru.ai... we are trying to
replace a human coach"*, and then the process itself — a coach looks at your
games, tells you what is good and what is bad, trains the bad, and **plays with
you, teaching through the game**.

The page has been failing because it was the shape of the work that produced it:
three features, three cards, eight labels, five bars. A coach is not a dashboard
with a kind voice.

## What a human coach does, and what we have for it

| the coach | ChessGuru today |
|---|---|
| reads 5-10 games, forms a picture | **strong** — six area grades, 4,263 gated chances, seven stable behaviour traits, per-move gaps |
| says what is GOOD and what is BAD | **half** — 39 strengths exist and render as one word with an unshippable narrative |
| trains the bad thing | **over-supplied** — 4.1M Lichess, 50k coach positions, 18 traps, 10 endgames |
| **plays with you, teaching as you go** | **built and buried** — triggers for encouragement, reflection, teaching, warning, opening guidance; a pre-move guardian; traps; punishment puzzles |
| shows you the good moves you played | **never shown** — 487 flagged moves per 600 games |

Nothing important is missing from the backend. The page represents one phase of
five, and the most differentiated one is a faded nav tile.

## The page: three movements, in a coach's order

### 1. WHAT I KNOW ABOUT YOU

Good and bad, in one voice, as a coach opens a session. Not grades, not bars.

```
I have been through your games.

You are hard to beat tactically — you blunder less than almost
anything else you do.

What is costing you is the clock. Seventy-one games you were
already winning, gone on time.
```

The strength comes first and it is not decoration: a coach who only names faults
loses the client. This is also where the one striking finding lives, which is
already built.

### 2. TODAY — a board, and a question before an answer

The coaching moment, and the thing no competitor does.

```
        [ board from HIS game, move 11 ]

You played Nd4 here.

Before I tell you anything — what were you checking?

  ( ) I checked what could capture the piece once it landed
  ( ) I moved the piece that was already under attack
  ( ) I was taking something
```

He commits, THEN gets the answer, and the answer is about his thinking rather
than the position: *"You went to the piece being attacked. A piece under attack
is often defended and perfectly safe. The one in danger is the one with nothing
behind it."*

Asking before telling is what makes it stick. A conclusion handed over is nodded
at and forgotten.

**All of this exists**: 12 ready positions from his own games, 2,126 of which
know the move he played, and `lesson_question_spec` already holds the question,
the belief options and the correction for each wrong one.

### 3. PLAY ME

The invitation, first-class, not a tile.

```
Twenty minutes, whenever you want.
I will stop you before the mistakes and tell you why.
```

This is where the product beats a human coach rather than imitating one: always
available, never tired, sees every move.

## What is removed

The card stack. The signals row, the progress bars, the separate session panel,
the eight small-caps labels. Their content survives as sentences inside the three
movements or moves to Progress, where charts belong.

## Rules carried

**Counts of games are allowed; rates, percentages and scores are not.**
"Seventy-one games" is the finding. "4.6% vs a cohort average of 6.7%, +0.9σ" is
the current strength narrative and is unshippable three times over.

**No cross-player comparison.** The strength mechanism currently derives from a
cohort and that has to change; within-player ("of everything I watch, this is
what you are best at") says the same thing without it. Out of scope here, named
so it is not forgotten.

**Nothing links anywhere empty.** Every destination is supply-checked server
side, as the session blocks already are.

## Reach, measured on prod after shipping (2026-10-07)

Of 128 users:

| | |
|---|---|
| movement 3, play me | **128** |
| movement 2, a board and a question | **59** |
| movement 1, what I know about you | **55** — 39 with a strength, 53 with the costly thing |
| neither movement 1 nor a board | 62 |

The 62 are not a hole: 57 have **no games at all**, and the other 5 have exactly
one. There is nothing true to say about a player from one game, so they get the
invitation and nothing else, which is the right answer.

Movement 2's board is keyed to the focus topic only when the player's own games
can show it. Strict reaches 33 of the 49 focused players; focus-else-largest
reaches 48. Everyone the strict rule missed was focused on `time_management`,
which has no board positions by construction — Mohit included.

Verified by maths, not by eye: on all 42 boards the named move is legal in the
position shown and the side to move matches the player's colour, with a negative
control proving the check can reject a board shown one move late.

## What was taken out of the finding chooser

`one_family_dominates` fired for **42 of 42** evaluable players with the
identical sentence. `alignment_share` runs 0.550–0.764 and the bar was 0.4,
picked from one player's 0.59 before anyone looked at the spread, and
`free_piece` is the largest shape for every player so the second condition
passed too. A finding every player gets is a fact about chess in a finding's
clothes. The function is kept, unwired, with the numbers in its docstring.

## Still open

- **Showing the brilliant move.** "Brilliant moves" is the most common stored
  strength (8 of 39) and movement 1 only *says* so. 487 moves per 600 games are
  flagged and not one has been put in front of the player who played it. The
  board belongs in movement 1 next to the sentence.
- **Strengths come from a cohort.** The mechanism compares the player to others
  at their rating, which the no-comparison rule forbids. Within-player ("of
  everything I watch, this is what you are best at") says the same thing
  without it. Only the *narrative* has been fixed so far, not the derivation.

## How we will know it worked

Whether a player answers the question. A board that is looked at and scrolled
past is the same dashboard with a picture on it.
