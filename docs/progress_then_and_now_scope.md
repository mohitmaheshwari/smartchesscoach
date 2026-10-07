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

## Milestones, not one frozen "before"

Mohit, 2026-10-07: *"not just first 10 vs last 10, but also a comparison of
milestones like last 10 vs current 10 and then later... a coach never just gets
stuck on what you were before me, a coach keeps on teaching and seeing are you
improving."*

Correct, and it is the same correction he made about the home page. But the
milestone is **not** every ten games. It is the **focus cycle** — the period the
coach spent working on one thing. That is what a coach's notebook actually looks
like, and the chain already exists: **51 users have 2+ focuses**, 60 docs carry
a `closed_at`.

### Why fixed game blocks were measured and rejected

Blocks of 10 and 20 games, ordered by play date, over every user with 4+ blocks:

| | trend / noise | share above 1 |
|---|---|---|
| blocks of 10, averaged per-game scores | 1.46 | 58% |
| blocks of 10, **pooled raw counts** | 1.45 | 63% |
| blocks of 20, averaged | 1.22 | 53% |
| blocks of 20, **pooled raw counts** | 1.30 | 56% |

I expected pooling to fix it — averaging per-game percentages over small
denominators is a known way to manufacture variance, and this session already
hit that shape in the clock finding. **It made no difference** (1.45 vs 1.46),
because the denominator was never small: the median game offers 30
threat-awareness decisions, so a block of 10 pools ~300.

So the wobble is not a measurement artifact. The series are simply flat:

```
threat_awareness miss rate, pooled per block of 10
   9  11 13 14 11 13 12  9 11  9 11 10
  11   8 13 13 12 15  8  9 12 10 11 14
  12  12 12 10  8 11 11 14  8 11 10  9
```

Ten to twelve percent, unchanged across 120+ games. **A per-milestone "are you
improving" verdict on this data would be a coin flip in a coach's voice.** That
is the expected answer while ChessGuru is not yet live — these users predate the
features — but it decides the design: the chain reports what was worked on and
what the measurement found, including "nothing yet", and never manufactures a
verdict the data cannot support.

### What the chain says, and the behaviour that makes it coaching

```
WHAT WE HAVE WORKED ON

  Piece safety        we worked on this, and it has not moved
  King safety         six games in — still watching

  Piece safety did not move in the time we gave it, so we
  changed what we were doing rather than repeating it.
```

**A log that reads "no change" four times is depressing. A coach who says "this
is not working, we are switching" is the product.** So a milestone that finds no
change must *drive the next focus*, not just print. The machinery for that
already exists — `check_focus_outcome` is the single evaluator and
`close_focus` escalates — and must not be duplicated.

### Two things blocking the chain, one fixed

**FIXED 2026-10-07 — ordering was wrong for a third of users.**
`games.date_played` holds ISO strings, chess.com dotted dates and nothing at
all, and the window split compares them as **strings**: "." sorts above "-", so
every dotted date landed after every ISO timestamp regardless of the real date.
Measured: **16 of 49 active focuses had a polluted after-window containing 437
games that predated the focus.** `scripts/backfill_played_at_utc.py` existed,
dry-run-by-default with rollback, and had never been applied — 693 rows to
write, 0 unresolvable, 0 disagreeing with the PGN by more than a day. Applied.

**NOT FIXED — the measurement is computed daily and thrown away.**

```
focus_outcome_loop: SHADOW measured 53 focuses
  (nothing rendered; FOCUS_OUTCOME_RENDER_ENABLED is off)
```

`current_metric` is None on **all 327** focus docs. So there is no recorded
now-value for any user and the chain has nothing to read. Turning the flag on
also means the outcome checks resolve or escalate roughly **10 live accounts**,
which is why it has not been flipped. **Mohit's call.** Nothing else in this
scope can be honest until it is.

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
