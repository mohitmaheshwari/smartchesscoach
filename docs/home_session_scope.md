# Home as a session the coach chose — scope

Mohit, 2026-10-06, after rejecting a card-by-card home page: the session should
have a shape — **appreciate, improve, discover, challenge** — and the coach
should choose which one today deserves.

He is right that this is better than the single card I kept proposing. A card is
a readout. A session is a decision, and the decision is what makes it feel like
a coach.

## What ships, and what does not

His design had eight sections. Four of them are displays, and his own principle —
*"Home is not where ChessGuru displays data, Home is where ChessGuru decides what
matters"* — rules them out. **①②③④ ship. ⑤⑥⑦⑧ do not**, and belong in Progress
and Learn where he put them himself a paragraph later.

**DISCOVER is held back from v1 on evidence, not taste.** The corpus is there —
192,307 deflection puzzles, 15,445 interference — and there is **no authored
lesson for either**. "Teach me" would open positions with no explanation, which
is the puzzle app the product is trying not to be. Detection is not teaching.
DISCOVER returns when there is something to read.

So v1 is **APPRECIATE · IMPROVE · CHALLENGE**.

## The chooser is the product

Everything else here already exists in some form. What does not exist anywhere is
the thing that decides today is an appreciate day rather than an improve day.
There is no session collection, no mode, no selector. That is the work.

### The rule

    APPRECIATE   when there is fresh evidence they did the thing right
    IMPROVE      when the focus has practice positions behind it
    CHALLENGE    when neither of the above has anything to say

Order matters and it is not arbitrary. A player who has just done something right
is told so FIRST, because the product currently opens every session by naming a
weakness, and for something people do for fun that reads as homework.

The mode is the HEADLINE. The session underneath may still contain more than one
block; the mode says which one leads and what the coach says at the top.

### What counts as fresh evidence, per mode

**APPRECIATE** — one of:
- a sound sacrifice in a recent game (`is_brilliant`: the player gave up material
  and it was still the engine's best move). 55 of 70 players have one.
- a pattern that has gone quiet: `pattern_decay` state `declining` or `fading`
  with a clean run of at least three games. 48 of 57 players have one.

**IMPROVE** — the active focus, and practice positions that actually exist for
it. The supply check is not optional: `king_safety` has 151 community puzzles and
341 coach positions and **zero** that pass verification, so 12 players have had a
focus with an empty practice button.

**CHALLENGE** — always available. 4.1M rated puzzles, and a player's own rating
band is enough to pick above their level.

## What the player sees

```
Good afternoon, Mohit.

FROM YOUR COACH
Something you have been working on is starting to show.      <- the mode
You have not left a piece hanging in your last several games.

           ↑ IMPROVING        ◎ WORKING ON         ★ STRENGTH
           Piece safety       Time management      Defence

TODAY WITH YOUR COACH
  01  APPRECIATE   The position you got right        2 min
  02  IMPROVE      Time management · 3 positions     5 min
  03  CHALLENGE    2 unseen positions, no hints      2 min

                   [ Start today's session -> ]
```

### The three signals

Measured, all three exist today: improving (48 of 57 players), working on (52),
strength (**39**). This is the best-supported part of his whole design and it
replaces the progress-bar block he asked to remove.

## Rules carried from the rest of the product

**No numbers in anything the player reads.** His mock has `+14%`, `214 games`,
`1:34`, `5 of your recent games`, `+109`. The standing rule is no numbers, and
three cards shipped this week obey it. Minutes are the one exception argued for
below.

**No claim of improvement we cannot evidence.** `+14% this month` is the single
most dangerous string in the design. His tactical conversion is flat — 51, 65,
55, 59, 57, 56, 53, 52, 53 across ten weeks — and the first person to check will
be him.

**Minutes are allowed.** "5 min" is a promise about the next five minutes, not a
score, and a session with no sense of length is a session nobody starts. Flagged
here because it is the one place this scope breaks the no-numbers rule on
purpose.

## How we will know it worked

Not clicks on the session. Whether the mode distribution is sane across the
population — a chooser that answers IMPROVE for everybody every day has not
chosen anything, and that is the failure to watch for.
