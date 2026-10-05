# The week, measured in chances taken — scope

Mohit, 2026-10-05: *"not just the game count, but the quality of games you're
playing... what types of moves are you playing, are you learning things, if not
we would obviously show that."*

## The idea in one line

A session is not nine games. It is **the chances those games gave you, and what
you did with them.**

Every other product counts games, rating, or puzzles solved. None of them can
tell you that four of today's games were over before anything happened.

## A correction, made before anything is designed

I first read the flat take rate as *"you are not improving"*. That was wrong and
the claim must not ship in that form.

Measured over the same weeks, his rating went **1067 → 1307**. He is improving
substantially. What is flat is one narrow thing: the share of tactical chances
he converts.

So the honest reading is not "nothing is working". It is either

- he improved through something other than tactical conversion, and that
  conversion is now the ceiling, **or**
- he is converting at the same rate against steadily harder opposition, which is
  real progress the raw rate cannot see.

**Both are interesting. Neither is "you are not learning."** The product says the
narrow true thing or it says nothing.

## What the player sees

```
┌──────────────────────────────────────────────────┐
│  YOUR WEEK                                       │
│                                                  │
│  Nine games. Four were over before anything       │
│  happened.                                        │
│                                                   │
│  The other five tested you, and you met about     │
│  half of what they asked.                         │
│                                                   │
│  ▁▁ ▃ ▂ █ ▁ ▆ █▁▁▁ ▇                              │
│  each bar is a game — how much it asked of you    │
├───────────────────────────────────────────────────┤
│  Your sharpest shape this week: taking free        │
│  material. Your weakest: skewers.                  │
│                                                    │
│  [ One skewer, right now → ]                       │
└────────────────────────────────────────────────────┘
```

The bar strip is the whole idea in one picture: a game that asked one question
and a game that asked sixteen look nothing alike, and today they are counted the
same.

## The three readings

### 1. Was this game worth playing? — chances in it

From `opportunity_gate.observe`: a position counts when the engine's best move
was a tactic. Measured on his last 25 games: every game tested him at least
once, but the spread was 1 to 16 chances. A fifteen-move game with one chance is
not practice.

### 2. Did you take them? — the rate

153 chances across those 25 games, 77 taken.

### 3. Is it moving? — the trend

Ten weeks, between 51% and 65%, no direction. **This reading is BLOCKED — see
below.**

## What blocks reading 3

A take rate means nothing without knowing whether the positions got harder.
`opponent_rating` is missing on **48% of all games** (9,918 of 19,203), and on
every coach game. It is missing for exactly the recent weeks this reading would
cover.

So reading 3 ships only after either

- opponent rating is backfilled from the platform APIs, or
- difficulty is taken from the board instead — `services/position_difficulty.py`
  already grades positions routine / testing / hard without needing a rating.

The second is probably the better answer and it is already built.

## What is NOT in this

- **No claim that a player is or is not improving.** Reading 3 is a trend in one
  narrow measure, and the wording must say which measure.
- **No rating prediction.**
- **Not all of chess.** The gate sees tactical shapes. It does not see endgame
  technique or planning, so "your week" here means "the tactical content of your
  week" and must not be worded as more than that.

## Open decisions for Mohit

1. **Numbers.** "Four of nine games" is a count, and the standing rule is no
   numbers in user-facing text. A week reading without any counts is close to
   useless. I think this earns an exception for plain counts of games and
   chances — never for rates or scores. Your call, and it applies to the
   behaviour cards too.

2. **How honest about a flat trend.** Once reading 3 is unblocked, some players
   will have a genuinely flat line. Saying so is the most valuable thing we can
   do and the most likely to make someone leave. My view: say it, but only
   alongside the specific thing being changed about it.

3. **Who it is for.** This needs analysed games with timestamps. 46 players have
   40+; 23 have 120+. It is a reading for engaged players, not a first-run
   screen.

## How we will know it worked

Not engagement with the card. The question is whether a player's take rate moves
after they start seeing it — which is the same standard the pin and skewer drill
is held to, and it needs weeks of new games either way.
