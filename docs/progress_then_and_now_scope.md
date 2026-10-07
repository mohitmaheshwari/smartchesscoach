# Progress: where you started, where you are, are you taking the lessons

Mohit, 2026-10-07: *"maybe player progress page should call it then — player
strength or weakness, how is he doing, how is he progressing, maybe how he
started when we first looked at him, now where is he doing? Is he taking our
lessons well, you know all that tracking, we already have it at backend"*

He is right on both counts: this belongs on Progress rather than Home, and the
tracking exists. What follows is what the data can actually support, measured
before anything is designed.

## What exists, counted

| | |
|---|---|
| `thinking_scores` | **18,587** docs, **65** users, **50 with 20+ scored games** |
| `game_analyses` | 18,654 |
| `puzzle_attempts` | 521 — but only **20 users** have a single one |
| `learning_sessions` | 271 |
| `user_active_focus` | 327 (280 weakness, 39 strength, 8 untyped) |
| `lesson_attempts` | **0** — not a real collection; lesson-taking lives in `puzzle_attempts` (positive control: 521 rows prove it is recorded, just elsewhere) |

`thinking_scores` is the backbone and it is far richer than the five-habit
summary it is usually read as. Per game, per habit: `score`, `mistakes`,
`opportunities`, and `examples` carrying `move_number`, `move`, `cp_loss` and a
written explanation. That is a then-and-now, a strength, a weakness and the
evidence for each, from one collection.

## What the data can and cannot say

**CAN: "when we first looked at you, and now."** 37 users have 10+ games either
side of joining, and 50 have 20+ scored games. First-ten versus last-ten on the
same habit, measured by the same function in the same run, is a fair and honest
statement.

**CANNOT: "and that is because of us."** Three biases all point the same way:
people sign up while losing so they drift back up unaided, users of a coaching
tool are self-selected for motivation, and Elo noise is ±50–100. The honest
version of causality is already built —
`backend/scripts/measure_coaching_contribution.py`, a within-user
difference-in-differences using the player's *untaught* gap categories as the
control — and today it finds **no detectable effect**, which is the expected
answer while ChessGuru is not yet live. So the page describes change; it never
claims credit for it.

**CANNOT: "is he taking our lessons well", for most people.** 20 users of 128
have ever attempted a puzzle. For the other 108 the honest answer is that they
have not started, and a page that implies otherwise is lying.

## Two traps that have already cost real bugs

**Never difference against `user_active_focus.baseline_metric`.** It was written
the day the focus locked, by whatever the detector looked like then, so
differencing today's count against it scores *our own detector changes* as
player improvement. On production it read 13 improved / 0 regressed; re-deriving
the before half over the same games with today's code gave 4 improved / 3 stuck
/ 6 regressed. The entire apparent effect was ours. **Both halves must be
measured by the same function in the same run.**

**Order by `games.date_played`, never `calculated_at`.** The median production
game is analysed 19 days after it was played and 42% more than 30 days after, so
an analysis-ordered window puts pre-coaching games inside the after half.
`thinking_scores` carries only `calculated_at`, so the game date has to be
joined in. (`date_played` is an ISO **string** — a datetime bound silently
matches nothing.)

## The page

Three questions, in the order a player asks them.

### 1. WHERE YOU STARTED, WHERE YOU ARE

```
When I first looked at your games, the thing that cost you most
was missing what your opponent was about to do.

Then     you missed it in about half the positions where it mattered
Now      you miss it in about one in five

Your first ten games I scored, against your last ten.
```

One habit — the one that was worst at the start, because that is the one he
wanted help with. Both halves by the same function. No percentages on screen
(the words carry it); no rating chart; no claim that we caused it.

### 2. WHAT YOU ARE BEST AT, AND WHAT STILL COSTS YOU

From the same `habit_scores`, within-player: of everything I watch, this is
your highest and this is your lowest. **No cohort.** This also replaces the
current strength derivation, which z-scores against other players — forbidden
by the no-comparison rule, and visibly broken: a dry-run refresh puts 14 of 37
users on the identical label.

### 3. ARE YOU TAKING THE LESSONS

Only shown to someone who has taken one. For the 20 who have: how many
positions, how many they got right, and whether the habit they practised is the
one that moved. For the other 108, this section does not render — the invitation
to start belongs there instead, and it is the truth.

## Out of scope, named so it is not forgotten

- Rating-over-time. It is the chart everyone asks for and the one that cannot
  support any claim worth making.
- Any contribution or credit figure. The measurement exists and says nothing
  yet; publishing a number from it would be inventing one.
- `FocusResolutionBanner` is silent for all 53 users and its baseline is the
  **lifetime** average, which includes the games it is measuring. It must not be
  wired into this page until that baseline is fixed, or it will make a false
  claim the first time it fires.

## How we will know it worked

Whether a player can answer "am I getting better at the thing my coach picked"
without reading a number. If the page needs a percentage to make its point, the
point was not there.
