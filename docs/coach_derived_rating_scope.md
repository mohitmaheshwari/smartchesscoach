# Coach-Derived Rating — Scope (DRAFT)

**Date:** 2026-07-06
**Author:** Claude (capturing decisions from the 2026-07-06 discussion with Mohit)
**Status:** DRAFT — decisions settled, NOT started. Ordered AFTER the
teaching-opponent scope is signed off. No code until this is signed off too.

## Why

Today PWC's rating is not coach-derived at all — `get_user_rating_from_games`
just reads the **chess.com/lichess Elo tag** off the last ~10 game PGNs and
averages them. It ignores `game_analyses` entirely (accuracy, cp_loss, how the
player actually played). So the "coach that watches how you play" doesn't
actually assess your play to know your level — it borrows the platform number.

Mohit's call: **the coach should derive its OWN rating from performance (PWC +
analysed games), and THAT is the authoritative number — not the imported one.**

## Decisions (settled 2026-07-06)

1. **Authoritative rating = performance-derived.**
   - **Move-quality is the primary signal** (accuracy / avg_cp_loss / per-move
     cp_loss from `game_analyses`). This matches the premise: rate how you play.
   - **Results are a secondary signal**, and **only from games the BOARD
     decided** — time-decided games (win *or* loss) are excluded from the
     results component (see #3).

2. **Move-quality is CLOCK-BLIND — by design.** A game where you were clearly
   better but lost on time costs **zero** skill rating. Your chess didn't get
   worse because the clock ran out. This falls out for free: move-quality never
   looks at the clock, so good moves are credited regardless of the result.

3. **Time management is NOT folded into the rating.** It's already a live,
   populated dimension (`time_flag`: impulsive_critical / time_pressure_blunder,
   `%clk` parsing — Mohit has 322 impulsive flags, Shobhit 211, on real data).
   Keeping it separate is strictly MORE informative: a genuine 1200 vs a 1350
   who flags are distinguishable. Two lanes:
   - board-skill rating → "how good is your chess?" (clock-blind)
   - time dimension → "can you manage the clock?" (already built)

4. **Imported rating (`assessed_rating`) is DEMOTED, not discarded.** Two jobs:
   - **Cold-start bootstrap** — a new user with 0 analysed / 0 PWC games has
     nothing to derive from; use imported until enough evidence accrues.
   - **Calibration / validation reference** — the move-quality→Elo mapping is
     noisy; validate the derived rating reproduces known ratings on users where
     we have both. Imported Elo is the independent ground-truth anchor.

5. **PWC contributes without circularity.** `coach_sessions.coach_skill_level`
   already stores the opponent's ABSOLUTE strength per session, so a PWC result
   is meaningful (result vs a known-strength opponent) independent of whatever
   rating we derive. The old "rating → opponent → rating" loop is broken by
   using the stored absolute skill.

## Data we already have (no new capture needed)

- `game_analyses.stockfish_analysis`: `accuracy` (e.g. 66.1), `avg_cp_loss`
  (69.5), per-move `cp_loss`.
- `games`: `opponent_rating`, `result`, `time_control_category`.
- `coach_sessions`: `coach_skill_level`, `result`.
- Time flags already derived in `move_observations`.

## The hard part (flagged, not hand-waved)

Converting move quality → an Elo **number** is noisy and scale-uncertain — the
same 66% accuracy is different Elo in a sharp vs quiet game. Approach:
- **Results-based performance rating as the objective backbone** (opponent
  rating + W/L/D via the Elo performance formula; PWC uses skill→Elo).
- **Move-quality as the primary enrichment**, calibrated so it reproduces
  imported ratings across the user base.
- Per our rule: **pull the accuracy-vs-known-rating distribution BEFORE locking
  any mapping constants** — do not guess the mapping (threshold-before-
  distribution is a sin).

## Open decisions (for signoff)

1. Move-quality → Elo mapping form (calibrated regression vs banded lookup).
2. Confidence weighting: how fast performance rating overtakes the imported
   bootstrap as games accrue (n-games / variance weighting).
3. Min sample before the derived rating is shown at all.
4. Flag + default (e.g. `PWC_COACH_DERIVED_RATING`, default off).

## Backlog (deferred, not this scope)

- **Side-by-side presentation of the two lanes.** Surface board-skill rating and
  time-management together so the story is legible:
  *"Your board play is ~1350, but time trouble is turning wins into losses —
  that's the lever."* This is a wiring/UX item, not a detection gap. Logged
  2026-07-06 at Mohit's request.

## Non-goals

- Folding time management into the rating number (decision #3).
- Changing the time-management dimension itself (it's live).
- Unifying the two *imported* rating fields (`assessed_rating` 1241 vs the live
  average 1184) — separate SSOT cleanup; imported is only a bootstrap/reference
  here anyway.
