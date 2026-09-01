# Personalized Game Review Coach  Phase 3 Shadow Data Lock

**Date:** 2026-09-01  
**Decision type:** shadow configuration only; visible-release numbers remain unlocked

## DECISION LOCKED: shadow planner configuration

**Formula:** D_teaching_then_critical  
**Moment cap:** 2  
**Reflection question budget:** 1

## Evidence

- The read-only production bake-off regenerated **947/947** simple_hang
  decisions from stored PGNs and stored Stockfish evaluations and all 947
  passed the current final verifier.
- Formula D selected a fully teachable event in **70.23%** of affected games,
  versus 68.39% for largest-loss/critical-first and 67.65% for chronology.
- Formula D agreed with largest-loss on **98.15%** of games, so the completeness
  gain does not radically change which chess moment is chosen.
- **97.05%** of affected games have at most two eligible events. A cap of two
  therefore keeps every verified event in 97.05% of the current affected set.
- One structural reflection candidate exists for **74.1%** of reviews; two
  candidates exist for 51.3%. That 22.8-point cliff supports one shadow
  question. Production contains zero reflection outcomes, so more interruption
  is not justified.

## Rejected candidates

- A_chronology: useful baseline, but lowest full-teaching selection rate
  (67.65%) and ignores event quality.
- B_largest_loss: slightly larger average stored loss but lower teaching
  completeness (68.39%).
- C_critical_then_loss: identical to B because every eligible simple_hang
  event in this corpus carries the critical flag; it adds no discrimination.
- Cap 1: discards a second verified event in 13.16% of affected games.
- Cap 3/4: preserves 2.95%/0.37% more games respectively but adds review length
  before any completion evidence exists.
- Two or three reflection questions: structural reach drops to 51.3% and 30.9%
  respectively, with no production behavior evidence to justify the cost.

## Measurement method

backend/scripts/measure_personalized_game_review_phase3.py ran inside the
production backend container with the current Stage 4 modules mounted under a
temporary /tmp overlay. It read only schema 16+ move observations, stored PGNs
and stored engine evaluations. It made zero engine runs, zero LLM calls and zero
database writes, and exported aggregate values only.

The exact output and source hashes are versioned in
backend/data/corpus_snapshots/personalized_game_review_phase3_planner_bakeoff_2026-09-01.json.

## Important non-lock

These values select a **shadow candidate**, not a production winner. Only one
Plan-grade detector exists and it reaches 5.96% of stored V5 games under the
strict final-verification join. The corpus has no human importance labels and
no reflection behavior. Final ranking, visible cap and rollout thresholds stay
open until the blinded coach review.
