# Move-Quality Rating (v2) — Scope (DRAFT)

**Date:** 2026-07-06 (updated same day after validation)
**Author:** Claude (for Mohit's signoff)
**Status:** DRAFT — validated with data. No code until signed off.
**Supersedes** `coach_derived_rating_scope.md`.

## The decision

Move-quality is the **authoritative** rating. It's the only signal that measures
the user's *chess* — not their internet, their clock, or their focus. A
chess.com/lichess rating is contaminated by timeouts, disconnects, and
distraction, so it isn't "real" chess strength for a coaching product.
(Mohit, 2026-07-06.)

## What the validation actually found (read this before building)

We tested this end-to-end on 46 users with known ratings + the full corpus. Three
findings changed the design — recorded honestly so we don't re-learn them:

1. **The fancy error-rate composite did NOT beat plain accuracy.** Leave-one-out
   CV: accuracy MAE **264**, blunder+severe+hang composite MAE **281** (slightly
   *worse*; more features overfit 46 points). So **don't build the composite** —
   the accuracy number we already compute (Lichess formula from ACPL) is as good.
   An earlier claim that "blunder rate holds at the top" did not survive
   cross-validation — the top-end gradient (2.7% vs 2.9%) is too small to encode
   rating.

2. **Every move-level metric saturates at ~1500–1600.** Samuel: 30,000 moves,
   known 1755, predicted 1289 — off by 466 with a huge sample, so it's saturation
   not noise. Matthew (2167) predicts ~1493–1648 by any method. Strong players
   make few errors of *every* type, so error rates compress and stop
   discriminating. **This is a fundamental ceiling, not a feature-engineering
   gap.** BUT ChessGuru targets **600–1500** — *below* the ceiling. So move-quality
   works for the market; imported stays the number for the rare 1600+ user.

3. **It is a BAND, not a point.** Two honest reasons: MAE ~250 even at its best,
   AND the absolute number is methodology-sensitive — weighting by *moves* vs by
   *game* moved one user (mohit) from ~1357 to ~1000, a ~350 swing. So the product
   must show a **band / level**, never a precise integer.

## Recency — settled by data

A rating must track *current form*, not a lifetime average (people improve). But
a hard 10–15 game window is too jittery — measured swing of ±600, jumping 30–63
points per game. The working mechanism:

- **Move-weighted exponential decay (EWMA), half-life ≈ 30 games.**
- Measured jitter at half-life 30: **~13–15 points/game** — stable enough to show.
  (10–15 game windows: 30–63. Half-life 80: ~8 but too sluggish.)
- Trade-off (stated plainly): it reflects a real, sustained climb over ~30–50
  games (a few weeks), and deliberately ignores a single hot/cold game. Correct
  for a coaching rating.
- Reuses the recency-weighting philosophy already in `pattern_decay_service`.

## What we actually build

- **Metric:** the existing **accuracy** (Lichess formula from ACPL). No composite
  — validation showed it doesn't help.
- **Recency:** move-weighted EWMA of accuracy, **half-life ≈30 games**.
- **Presentation:** a **band / level with an honest range** (e.g. "Improver
  ~1000–1300"), never a bare number. Optionally a coarse 3–4 tier label.
- **Range of use:** authoritative for **600–1500**; above ~1600 defer to imported
  (few such users, and the metric can't resolve them).
- **Boundaries (unchanged decisions):** time management and results stay OUT of
  the number (own live lanes; a time-loss = 0 skill penalty). Imported rating =
  cold-start bootstrap + calibration reference until enough analysed moves exist.

## Honest limits (must surface in any user-facing copy)

- Band-level, not point-level; cannot separate 1947 from 2167.
- Saturates above ~1500–1600.
- Absolute value is methodology-sensitive (~±350 depending on weighting) — this
  is *why* we show a band.

## Open decisions (for signoff)

1. Band scheme — a number-with-range (`~1000–1300`) vs a named tier
   (Beginner / Improver / Intermediate)? (Recommend number-with-range: concrete
   but honestly wide.)
2. Minimum analysed games before a rating is shown (cold-start threshold).
3. Exact half-life (data says ~30; confirm) and the accuracy→rating mapping
   constants (re-fit cleanly on the calibration set, clamped to a sane range).
4. Flag + default (`PWC_MOVE_QUALITY_RATING`, default off).

## Acceptance

- **Correct ordering within 600–1500** on the known-rating users (the market band).
- **Stable**: shown rating jitter ≤ ~15 points/game (half-life ≈30 delivers this).
- **No false precision**: always a band/range, never an unqualified integer.
- Deterministic (stored per-move `accuracy` + a decay pass; no runtime engine/LLM).

## Rollout

1. Sign off this scope.
2. Re-fit the accuracy→rating mapping on the 46 calibration users (clamped);
   confirm within-band ordering for 600–1500.
3. Build the deterministic scorer: move-weighted EWMA (half-life ≈30) over stored
   per-game accuracy, mapped to a band. Behind the flag.
4. Wire into the PWC rating + coaching calibration; imported bootstrap for
   cold-start and for 1600+.
5. Validate on known-rating users; flag on.

## Non-goals

- The error-rate composite (validation showed no lift over accuracy).
- Point-precision, or any rating above ~1600 from move-quality.
- Results-based rating or folding time into the number (their own lanes).
- Any new per-move detection — reuse existing `accuracy` / `cp_loss`.
