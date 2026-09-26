# Behavioural focus — coach the habit, not the lifetime total

**Status: DRAFT, awaiting Mohit's signoff. No code until then.**
Written 2026-09-26. Mohit: *"detectors have to be these two, like one time
blunders, or calculation depth, time management, you know behavior detectors
should be the focus, no?"*

---

## The problem, in one line

The thing that picks each player's single focus adds up their whole history and
names whatever happened most. It has no idea whether it happened last week or
last spring.

## Why this is the right axis, in numbers

I spent today measuring board-motif detectors. Promoting the best of them would
change the focus topic for **1 user of 53**. Recency alone, promoting nothing,
changes it for **17 of 57 — 30%**:

```
                    lifetime (today)      recency-weighted
  piece_safety              43                   37
  king_safety               13                   19
  missed_tactic              1                    1

  swaps: piece_safety -> king_safety  11
         king_safety  -> piece_safety  4
         missed_tactic -> piece_safety  1
         king_safety  -> missed_tactic  1
```

Same three topics. Nothing new detected. A third of players are simply being
coached on the wrong one of the three, because a mistake from two hundred games
ago still counts as evidence of what they are doing now.

`pattern_decay_service` already computes this, with its own measured constants
(0.85 per game back, twenty games, recovery credit for clean games). **Eight
services use it. The focus picker is not one of them.**

Behavioural evidence is also already stored, in more volume than the motifs:

```
  ignored_opponent_threat    12,222 rows   58 users
  time_flag set              12,473 rows   48 users
  punished_opponent_blunder   9,029 rows   58 users
  missed_opponent_blunder     6,841 rows   58 users
  (for comparison) missed_pin 1,299 rows   50 users
```

## What the player sees

The card is the product, so the wording comes first and the mechanism follows.

**Today** (real text pulled from production this afternoon):

```
  You have moved a piece onto a square where it could be taken 49 times,
  across 40 of your games — most often a rook (15 of them). Last time you
  played Ng5: the knight landed on g5, and after hxg5 the exchange there
  went against you.
```

Three rules broken at once: counts a player does not need, a move name they
will not remember, and a total that spans a year of play as though it were a
habit they have today.

**Proposed:**

```
  Lately you have been leaving pieces where they can be taken. It has come
  up in most of your recent games, and a rook most often.

  Before you let go of a piece, look at what can reach the square.
```

And where the habit has faded:

```
  You used to leave pieces where they could be taken. That has stopped
  showing up. We are moving on.
```

No counts. Short sentences, common words. "Lately" and "recent" are doing the
work the numbers used to do, and they are honest in a way a lifetime total was
not.

## Part A — recency in the picker

Rank candidates by the decay model's weighted score instead of the lifetime
severity-weighted count. Everything else stays: the same authorized-subtype
filter, the same severity weights, the same rating priors, the same plan-surface
gate.

**The dependency that must be named, and it is not what I first wrote.**
Recency needs `played_at_utc`, the BSON date. **1,553 of 17,804 games do not
have it — 8.7%.**

(An earlier draft of this scope said 3,106 and 17.4%. That was my arithmetic
error: in MongoDB `$exists: false` also matches an explicit `null`, so my two
queries returned the same 1,553 rows and I added them together. The corrected
figure does not change the recommendation below, but it halves the size of the
problem.)

Never `date_played` instead: it holds ISO timestamps, chess.com's dotted
`2026.04.15`, and nothing at all for Play-with-Coach rows, and `.` sorts above
`-` in ASCII, so every dotted date lands after every timestamp regardless of
when it happened. That already put 407 games into the wrong side of 15 focus
windows.

**The real problem is that nothing writes the field.** Grepping for a writer
outside `scripts/`: there is none. `scripts/backfill_played_at_utc.py` is the
only thing that sets `played_at_utc`, and
`primary_weakness_picker` is the only thing that reads it. So this was never a
one-off migration — it is a chore that silently reopens with every import. The
evidence is exact: **all 1,553 undated games were imported this month**, and
**all 1,553 still carry a usable `date_played`**, so every one is recoverable.

So Part A has a prerequisite that is smaller and more durable than re-running a
migration:

1. **write `played_at_utc` in the import path**, so the field is right by
   construction and the gap cannot reopen, then
2. run the existing backfill once for the 1,553 historical rows.

Only then does the recency ranking cover every game. The 17-of-57 number below
was measured over the 82.6% of games that are dated today.

## Part B — turn time management back on

It is not missing, it is switched off:

```python
_TIME_MANAGEMENT_OUTCOME_CHECK_FIXED = False
# 18 of 38 active weakness-locks were permanently wedged on time_management,
# extending 7 more days on every check with no way out.
# Re-enable once check_focus_outcome has a matching time_flag-based branch.
```

The 28-day time box shipped this morning removes the wedge — every focus now
closes whatever the outcome check says. **But that is necessary, not
sufficient, and I want to be exact about it:** `_topic_rates` measures a topic
by counting `move_observations` with that `missed_pattern`, and
`missed_pattern` is **never** `time_management` — zero rows. So without a
time-flag branch every time-management focus would close at the box as
`time_boxed`, never as `improved`. The player would be told we are moving on
and never told they got better.

So Part B is two pieces, and the second is not optional:

1. flip the flag, and
2. give `check_focus_outcome` a branch that measures time flags per game
   before and after, the same shape as `_topic_rates` does for a pattern.

The evidence is there: `impulsive_critical` 11,984 rows and
`time_pressure_blunder` 489, across 48 users — about 2% of all observed moves,
so it is selective rather than a base rate.

## Out of scope, deliberately

- **`found_best_in_critical`.** It is False on **98,303 of 105,143** critical
  moments — 93%. That is a base rate, not a detector; building on it would tell
  almost every player they fail under pressure. Whatever counts as "critical"
  needs fixing first, on its own.
- **`calculation_depth`.** Its subtypes exist (`shallow_horizon_2ply`,
  `broken_forcing_sequence`) but are unregistered and unmeasured. It belongs on
  this axis and should be the next one measured, not bundled in untested.
- **New detectors of any kind.** Part A promotes nothing. That is the point.
- Rewriting every focus narrative. Only the lines shown above change.

## What would say this failed

A player whose focus swaps under recency, plays ten more games, and whose rate
on the NEW topic does not move while their rate on the old one stays flat. That
would mean recency picked a topic that was noise rather than a habit. It is
measurable per user from data we already store, with no new instrumentation.

And the flat check: if the recency ranking and the lifetime ranking agree for
everyone on production after the backfill, Part A is a no-op and should not
ship. Today it disagrees for 17 of 57, but that is measured on 82.6% of games
and the rest could change it.
