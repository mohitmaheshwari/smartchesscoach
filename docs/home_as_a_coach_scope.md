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

## How we will know it worked

Whether a player answers the question. A board that is looked at and scrolled
past is the same dashboard with a picture on it.
