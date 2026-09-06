# Hidden Opportunities — Full Shadow Incidence Census

**Status:** COMPLETE. Evidence sufficient for the blinded ranking review.
**Date:** 2026-09-06
**Runtime exposure:** none (SHADOW grade, allowlist-blocked from public APIs)
**Production reads/writes:** reads only — `database_writes: 0`
**Fresh engine or model runs:** none — `stockfish_runs: 0`, `model_calls: 0`
**Deployed commit at time of census:** `afcee3fa`

Run: `python backend/scripts/report_hidden_opportunity_shadow_incidence.py`
(full scan, no `--limit`). Wall clock ≈ 75 min, CPU-bound.

---

## Result

| Metric | Value |
|---|---|
| Analyses scanned | 14,356 |
| Positions seen | 552,901 |
| **Candidates** | **6,148** |
| Candidate games | 4,141 |
| **Comparable games (≥2 candidates)** | **1,299** |
| Candidates inside comparable games | 3,306 |
| Duplicate positions skipped | 643 |
| Missing game context | 1 |

Candidates per game: `1:2842, 2:845, 3:294, 4:99, 5:40, 6:13, 7:5, 8:2, 9:1`
(10,215 games yielded none).

**Verdict: proceed.** 1,299 comparable games is far above what a blinded
ranking review consumes.

---

## Composition — the part that constrains the review design

### Proof family (severe skew)

| Family | Candidates | Share |
|---|---|---|
| `target_and_line_geometry_with_payoff` | 4,766 | 77.5% |
| `forcing_tempo_and_move_order` | 1,308 | 21.3% |
| `exact_endgame_and_promotion_geometry` | 69 | 1.1% |
| `board_transformations_with_payoff` | **5** | **0.08%** |

The top two families are **98.8%** of all candidates.

`board_transformations_with_payoff` fires **5 times in 552,901 positions** —
about 1 in 110,000.

### Actor (mild)

| Actor | Candidates |
|---|---|
| user | 3,882 |
| opponent | 2,266 |

Roughly 1 : 1.7.

---

## Recommendation for the blinded review

1. **Stratify by proof family, with a floor per family.** A flat sample of any
   realistic size is ~78% target-line geometry. A ranking formula tuned on
   that sample would be tuned on one corner of the space while reporting on
   all four families.

2. **Treat `board_transformations_with_payoff` as NOT REVIEWABLE at n=5.**
   Five cases cannot license a family. The honest options are to over-sample
   it deliberately and label the result as provisional, or to withhold that
   family's authorization and say so. What must not happen is a flat sample
   containing zero of them, followed by a family-wide verdict — that would be
   authorization by silence.

3. **Do not stratify hard on actor.** At 1 : 1.7 the natural distribution is
   workable.

---

## Two corrections to earlier estimates in this session

**Linear extrapolation from 500 games was right on volume and wrong on
composition.** The sample predicted ~1,400 comparable games against an actual
1,299 — close. But it surfaced only **two** families. The two rarest
(`exact_endgame_and_promotion_geometry`, `board_transformations_with_payoff`)
were entirely absent from 500 games, and one of them is the family most at
risk of being authorized on no evidence. **Small samples size a corpus; they
do not characterise its tail.** Rare-category presence must be measured on the
full population before a sampling design is chosen.

**Opponent-side thinness was inferred wrongly.** From stored-row shape
(1,176 opponent rows vs 15,052 user rows, 7.2%) I predicted opponent evidence
would be ~13× thinner. Actual candidate ratio is 1 : 1.7. Opponent rows are
sparse but far more *productive* per row. Row counts are not a proxy for
candidate yield, and the stratification argument that followed from it was
wrong in its main axis: family is the severe skew, actor is not.

---

## Skip accounting (not blocking)

| Status | Count | Share of positions |
|---|---|---|
| `below_rating_threshold` | 384,816 | 69.6% |
| `not_proved` | 155,017 | 28.0% |
| `candidate` | 6,148 | 1.1% |
| `missing_actor_rating` | 3,555 | 0.6% |
| `missing_stored_evidence` | 3,365 | 0.6% |
| `invalid_stored_evidence` | 0 | 0% |

The two `missing_*` statuses are **disjoint by construction** —
`missing_actor_rating` is checked first, so a row missing both is only counted
as the former. Their similar sizes are coincidence, not a shared cause.

`missing_stored_evidence` is rows lacking a `best_move` field: at a 500-game
sample the field was absent on exactly 475 user rows against a reported
`missing_stored_evidence: 475`, an exact match.

Also observed across all 16,228 sampled rows: `best_move_san` and `ply` are
absent on **100%** of stored rows and are derived at runtime. Neither can ever
be used as a stored-evidence check or a join key — anything written later
assuming they are persisted will silently match nothing.

`pv_after_played` / `pv_after_best` are missing on 947 of 15,052 sampled user
rows (~6.3%). These never reach `missing_stored_evidence` because the
`best_move` check fires first, so the true stored-evidence gap is wider than
the reported count suggests.

---

## What remains locked off

Unchanged by this census. All four proof authorizations are SHADOW; the
public-API boundary is an allowlist reading only `formula_id`, `plan`,
`rollout_mode`, `selected_event_ids`, verified by sentinel injection. Game
Review must not display a Shadow proof, and the try → hint → reveal → replay
→ recognition experience stays unimplemented until the blinded review
authorizes what a player may see.
