# Move-Quality Rating (v2) — Scope (DRAFT)

**Date:** 2026-07-06
**Author:** Claude (for Mohit's signoff)
**Status:** DRAFT — data-backed, NOT started. No code until signed off.
**Supersedes** the direction in `coach_derived_rating_scope.md` (results-based +
cold-start). The data below changed the plan.

## The decision

Move-quality is the **authoritative** rating. It's the only signal that measures
the user's *chess* — not their internet, their clock, or their focus. A
chess.com/lichess rating is contaminated by timeouts, disconnects, and
distraction, so it isn't "real" chess strength for a coaching product. (Mohit,
2026-07-06.)

## Why the CURRENT move-quality metric isn't good enough

Today "move quality" is a single number: per-move `cp_loss` → average per game
(ACPL) → the Lichess accuracy formula `103.17·exp(−0.04354·ACPL) − 3.17`.

Two proven failures (measured on 46 users with known ratings + the full corpus):

1. **It saturates above ~1200.** Accuracy is flat-to-inverted at the top:
   - Matthew 2167 → 68.3%, Parth 1947 → 65.1%, **Toby 1160 → 67.9%**.
   - A 1160 out-scores a 1947. Correlation with rating is +0.80 overall but
     driven entirely by the low end; above ~1200 it can't separate a 1400 from
     a 2000. Reason: strong players face sharper positions against tougher
     opponents, so "closeness to engine-best" self-normalizes and stops climbing.
2. **It's type-blind.** A hung queen and a slow positional drift both just add
   centipawns — but the user understands "I hung a piece," not "my ACPL was 40."

## The replacement: an error-RATE composite

Rate the player by **how often they make understandable errors**, using the
per-move taxonomy we ALREADY compute (`cp_loss`, `cognitive_gap`, `subtype`).

**Why it works where accuracy fails (measured):** blunder rate keeps its gradient
at the top.

| rating | accuracy | blunder% (≥300cp) |
|---|---|---|
| 2167 Matthew | 68.3% | **2.9** |
| 1947 Parth | 65.1% | **2.7** |
| 1160 Toby | 67.9% | 3.8 |
| ~1137 (mohit) | 64% | 5.6 |
| ~1300–1400 mid | ~62% | ~5 |

Accuracy *inverts* Matthew/Parth vs the 1160; **blunder rate orders them
correctly** (stronger = fewer blunders). Correlations: blunder%≥300 = −0.78,
severe%≥500 = −0.77, hang% = −0.67 — as strong as accuracy, but they hold at the
top instead of flatlining. A blunder is a near-*absolute* event (a 2000 rarely
hangs material regardless of position; a 1200 does it often), so it's far more
skill-pure than "closeness to best."

## Candidate features (all already stored per move — no new detection)

- **blunder_rate** — moves with `cp_loss ≥ 300` per 100 moves (backbone)
- **severe_blunder_rate** — `cp_loss ≥ 500` per 100 moves
- **hang_rate** — `subtype == simple_hang` (SEE-verified, just fixed) per 100
- **tactical_blunder_rate** — tactical_seq_loss / severe missed_tactic per 100
- **difficulty normalization** — down-weight errors where the best move was NOT
  findable (not forcing / not a critical moment); count fundamentals fully. This
  is what stops us penalizing a missed deep engine-only nuance like a hang.

## How the number is produced

Fit a model (start: linear regression; inspect for isotonic/banded) mapping the
error-rate feature vector → rating, **calibrated on the ~46 users with known
imported ratings**. Per our rule (no threshold before the distribution), inspect
each feature's distribution and fit on data — do NOT hand-pick weights.

## Purpose / boundaries (consistent with prior decisions)

- Authoritative rating for **coaching calibration + opponent difficulty + "your
  chess is ~X."**
- **Time management and results stay OUT of the number** — they're their own
  live dimensions. (Losing on time = 0 skill penalty; that was decided.)
- **Imported rating = cold-start bootstrap + calibration reference** until enough
  analysed moves exist. Not the shipped number, not discarded.

## Honest limits (must also be reflected in any user-facing surface)

- **Band-level, not point-level.** It can order bands; it cannot separate 1947
  from 2167 (2.7 vs 2.9 blunder%).
- **Noisy** — opponent strength, blitz vs rapid, and small samples all leak in
  (a 700-move sample reads noisy). Needs a minimum move count before it's shown.
- It will **read a strong player a bit low** even after this — the ceiling of
  what move-level error rates can measure. Above ~2000 it's approximate.

## Open decisions (for signoff)

1. Feature set — start with blunder% + severe% + hang%, add tactical/difficulty
   features only if they measurably lift top-end discrimination?
2. Model form — linear vs banded lookup vs isotonic regression.
3. Minimum moves before a rating is shown (cold-start threshold).
4. Show a confidence band (± range) to the user? (Recommend yes — it's honest.)
5. Flag + default (e.g. `PWC_MOVE_QUALITY_RATING`, default off).

## Acceptance

- Beats the accuracy baseline's **MAE 252** on the calibration set, AND —
  critically — **holds discrimination above 1200** (Matthew/Parth must land above
  mid-1000s players, not collapse into them).
- Monotonic across rating bands; correct ordering at the top.
- Deterministic (computed from stored per-move data, no runtime engine/LLM).

## Rollout

1. Sign off this scope.
2. Pull per-user feature distributions; fit the composite on the 46 calibration
   users; report MAE + top-end ordering vs the accuracy baseline.
3. Iterate features until it beats accuracy AND holds at the top.
4. Build the deterministic scorer behind the flag.
5. Wire into the PWC rating + coaching calibration; imported bootstrap for
   cold-start; show a confidence band.
6. Validate on the known-rating users; flag on.

## Non-goals

- Results-based rating or folding time into the number (their own lanes).
- Point-precision at master level.
- Any new per-move detection — reuse existing `cp_loss` + subtypes.
