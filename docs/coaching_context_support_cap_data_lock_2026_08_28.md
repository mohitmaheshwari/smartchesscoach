# Coaching Context Supporting-Focus Cap — Data Lock

**Decision date:** 2026-08-28  
**Scope:** `coaching_context.v1` presentation only  
**Decision:** one primary focus plus at most one visible contextual supporting focus

## Decision under lock

The candidates were primary only, primary plus one support, primary plus two
supports, and primary plus all three stored runners-up. This lock controls what
a player sees on one surface. It does not delete evidence, prevent the coach
from explaining a game-deciding off-focus move, or prevent a requested elective
from being represented separately.

## Discriminating production evidence

Read-only aggregate queries against `test_database` on 2026-08-28 found:

- 52 users with active-focus records;
- median, 75th-percentile and 90th-percentile active records per such user were
  all two;
- median, 75th-percentile and 90th-percentile active weakness records were all
  one;
- legacy focus documents store exactly three runners-up, but these are ranking
  residue rather than three independently authorized coaching plans;
- among newer cohort-standardized runner records, every measured rank was
  positive and the median first-to-second runner gap was only `0.196`; there is
  no empirical cliff that justifies exposing two or three runner cards;
- current training behavior is too sparse to claim that a larger set improves
  completion: only 13 users had `training_solve_attempts`, with median five
  attempts.

The present product therefore supports one diagnosed weakness authority and a
second contextual idea, but provides no behavioral evidence for three or four
simultaneous player-facing plans.

## Locked policy

- `primary_focus` remains singular and owns the instruction, CTA and outcome.
- `supporting_focuses` has a schema maximum of one in V1.
- The support must pass Plan authorization and be relevant to the current
  surface; otherwise the array is empty.
- A support cannot publish an independent improvement verdict or replace the
  primary CTA.
- A requested opening/endgame remains an `elective`, not a supporting diagnosis.
- Game Review may still lead with a decisive off-focus chess truth, then connect
  the active focus explicitly.

## Rejected candidates

- **Primary only:** rejected because a human coach may acknowledge another
  important issue and Mohit explicitly requires multiple active focuses.
- **Two or three supports:** rejected for V1 because production contains no
  completion/comprehension evidence for the added choices and the runner scores
  show no stable cutoff.
- **All runners-up:** rejected because a ranking list is not an authorization or
  a lesson plan.

## Reopening rule

The cap may be reconsidered only after an instrumented comparison measures
instruction recall, correct next-action selection and assignment completion for
one versus two visible supports. A larger list does not ship merely because it
fits in the payload or UI.

