# Primary Strength Picker — Scope

**Date:** 2026-07-02
**Author:** Claude (Mohit signed off "go, one shot")

## Problem

Weakness picker exists. No strength picker. Coach only ever tells users
what's wrong. That's half a coaching relationship.

Also, without a cohort baseline, calling anything a "strength" is
templating (80% blunder-punish MIGHT be strong; without knowing the band
average, we don't know). Same trap as the piece_safety subtype disaster
earlier today.

## What we're building (all three in one pass)

### 1. Cohort baseline service
- `services/cohort_baselines_service.py`
- Computes per-rating-band averages + stddev for these signals:
  - `critical_find_rate`
  - `threat_response_rate`
  - `blunder_punish_rate`
  - `best_move_rate` (execution_dist['best'] / total_moves)
  - `brilliant_rate` (execution_dist['brilliant'] / total_moves)
  - `blunder_rate` (execution_dist['blunder'] / total_moves — INVERTED: lower is better)
  - Top-10 tactical patterns' execution rate (patterns_executed / total_moves)
- Bands: beginner (0-1199), intermediate (1200-1599), advanced (1600-1899), expert (1900+)
- Only users with ≥10 analyzed games count toward baselines
- Stored in `cohort_baselines` collection, keyed by `(band, metric)`

### 2. Primary Strength Picker
- `services/primary_strength_picker.py`
- For each user, computes z-score across each metric vs their own band's baseline
- Picks the SINGLE strongest signal (highest z-score, capped at metrics ≥ +0.5σ)
- Also picks a "signature tactical pattern" — the pattern they execute
  most frequently where their per-move rate ≥ 2× cohort mean
- Stores as `type: "strength"` in `user_active_focus` (parallel to
  weaknesses with `type: "weakness"` — same collection)

### 3. Narrative + surfacing
- Evidence-driven narrative: "You punish opponent blunders 81% of the
  time — that's +23pp vs the 2000+ average of 58%. Also 69 free_piece
  captures — you spot loose material."
- Wire into `/api/coach/active-focus` response (returns both strength +
  weakness now)
- Wire into `FocusCard.jsx` — new "You're strong at" row above weakness

## Non-goals

- Sub-typing strengths (would parallel piece_safety subtypes; deferred)
- Long-term "strength trend" (this pass = point-in-time)
- Rewarding streaks (that's the Habit Tracker's job)

## Acceptance

Mohit reads Parth's + Mohit's strengths and says:
- "Yeah, those are actually his strengths, matches what I'd say"
- Numbers are >0.5σ above cohort mean AND cross-checked against my own
  chess intuition (the "verify with own perspective" reflex, per memory)

## Rollout order

1. cohort_baselines_service.py + one-shot compute across all 47 users
2. primary_strength_picker.py + preview on Parth + Mohit + 3 others
3. Wire /coach/active-focus + FocusCard
4. Commit + push
