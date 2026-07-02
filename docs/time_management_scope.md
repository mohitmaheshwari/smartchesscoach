# Time Management as a Coaching Dimension — Scope

**Date:** 2026-07-02
**Status:** Building. Mohit signed off with "go do it".

## The problem

Time is real signal that the coaching system currently ignores:

- **Parth (2041):** 28 of 178 games ended in timeout (16%). Lost 22 on
  the clock (12%).
- **Mohit (1199):** 124 of 600 games ended in timeout (21%). Lost 110
  on the clock (**18%** — nearly 1 in 5 games).

For Mohit, this is a bigger visible pattern than most of what we already
surface — and the coach has no visibility into it. Same for Parth to a
lesser degree.

Data is already sitting there being ignored:
- PGN contains `%clk` annotations with time remaining per halfmove
  (both chess.com and Lichess)
- Game doc has `termination` field which includes `"timeout"`
- Game doc has `time_control` and `time_control_category`

We just aren't parsing any of it into observations.

## What we're building

### 1. `pgn_clock_parser.py`
- `parse_clocks_from_pgn(pgn) → List[Optional[float]]` — halfmove-indexed
  clock-remaining in seconds.
- `parse_increment_from_pgn(pgn) → int` — the `+N` seconds from
  `[TimeControl "600+5"]`.

### 2. Deriver v9 — per-observation time fields
Every user move observation gets three new fields:
- `time_spent_seconds` — how long the user spent on this move
  (computed as `clocks[i-2] - clocks[i] + increment`)
- `time_left_seconds` — clock remaining after user's move
- `time_flag` ∈ {`impulsive_critical`, `time_pressure_blunder`, `slow_paralysis`, None}

Flag definitions:
- **`impulsive_critical`** — `was_critical_moment=True` AND `time_spent < 3s`
  AND `execution_quality ∈ (mistake, blunder)`. Base severity: critical.
- **`time_pressure_blunder`** — `time_left < 30s` AND `execution_quality == blunder`.
  Base severity: critical.
- **`slow_paralysis`** — `time_spent > 90s` AND `execution_quality ∈ (mistake, blunder)`
  AND NOT `was_critical_moment`. Burned lots of time on a routine move and blundered.
  Base severity: moderate.

Severity promotion follows the same rules as other subtypes
(blunder → +1, high cp-loss + not-hopeless → +1).

### 3. Aggregator — new signals
- `time_flag_counts`: `{impulsive_critical: N, time_pressure_blunder: N, slow_paralysis: N}`
- `timeout_loss_rate` (game-level): `# games with (termination=timeout AND user lost) / total games`
- `avg_time_on_critical_moment`: mean `time_spent` across `was_critical_moment=True` events
- `pct_critical_played_fast`: fraction of critical moments where `time_spent < 10s`

### 4. Picker — `time_management` as a first-class topic
Not a `missed_pattern` from the analyzer — a **derived synthetic topic** scored
from the time signals above.

Score contributions:
- Weighted count of `time_flag` events (severity-weighted, same as other subtypes)
- Plus a big boost if `timeout_loss_rate > 10%` (game-level signal)

Subtypes surfaced in narrative (drawn directly from time_flag histogram
+ timeout rate):
- `chronic_timeout` — loses ≥10% of games on the clock (game-level)
- `impulsive_at_critical` — plays critical moments <3s (move-level)
- `time_pressure_blunder` — blunders under 30s left (move-level)
- `slow_paralysis` — burns time on routine moves then blunders (move-level)

### 5. Cohort baseline extension
Add `timeout_loss_rate` and `pct_critical_played_fast` to
`cohort_baselines_service.METRICS`. Users compared against band cohort
for whether their time-management is a signature weakness.

### 6. Narrative + moments page
- Evidence-driven narrative built from user's own time_flag histogram +
  game-level timeout rate.
- CTA links to `/coach/moments/time_management` — new topic in
  `moments_topic_registry` returning the 3 most illustrative moments
  (e.g., 3 games where they lost on time in a winning position, plus
  the specific move-level flag events).

## Verification bar

Same as piece_safety: ≥85% verified-true on 30-sample per flag per user.
Verifier checks:
- `impulsive_critical`: was_critical_moment=True in the stored obs
  AND time_spent<3 (recomputed from PGN)
- `time_pressure_blunder`: time_left<30 (recomputed) AND execution_quality=blunder
- `slow_paralysis`: time_spent>90 (recomputed) AND NOT was_critical_moment

Also apply "verify with own perspective": pull top 5 events per flag for
Parth + Mohit, check each one against the actual game.

## Non-goals

- Chess960 / weird time controls (Bullet chess handled — same %clk format;
  Correspondence / days-per-move deferred)
- Predicting time trouble (this is descriptive, not predictive)
- Recommending time-management drills (that's a follow-up feature)

## Acceptance

- Mohit reads Parth's + Mohit's `time_management` narratives (once each
  user has one) and says: "yes, that's their real time issue."
- ≥85% verified-true on all subtypes
- If a user has no time issues (timeout rate low, no impulsive/pressure
  flags), the picker DOES NOT emit a false time_management focus (honest
  silence).

## Rollout

1. `pgn_clock_parser.py` + tests on Parth PGN
2. Deriver v9 + backfill Parth (10-min iteration cycle)
3. Verify per-flag rates on Parth make sense against his 28 timeouts
4. Extend aggregator + picker
5. Extend cohort baselines
6. Board-verify + own-perspective check
7. Backfill Mohit + full corpus
8. Reassign focuses
9. Commit + push
