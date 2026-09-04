# Hidden Opportunities Phase 3A - Continuation Pre-Code Audit

**Status:** PASS WITH ORDERED RELEASE GATES
**Date:** 2026-09-04
**Current base:** `origin/working-code` at `fdb0c8ec`
**Development branch:** `codex/hidden-opportunities-resume-v1`
**Approved scope:** `docs/hidden_opportunities_causal_coaching_scope.md`

## Existing-surface decision

The canonical surface remains `/game/:gameId`, rendered by
`GameDecryptionV5` and `PersonalizedReviewCoach`. The central caption pipeline
owns move-level teaching, `VerifiedLineCause` owns played-versus-better chess
evidence, the Game Review adapter owns public projection, the existing planner
owns moment selection, and the learner ledger owns later understanding and
transfer.

**Decision: EXTEND existing.** No new review page, parallel narrator, detector
registry, opening/trap/endgame catalogue, mastery store, or chess-fact source is
authorized.

## Six hard gates

1. **Literal UI mockup - PASS.** The approved scope shows the exact pause,
   interactive try, square-based hint, proved replay, explanation, recognition
   choice, takeaway, and continue states with literal player-facing copy.
2. **Pattern/geometry headline - PASS.** The approved headline is "The check
   that buys you a move." SAN remains evidence, not the product headline.
3. **Data-derived thresholds - PASS FOR EVIDENCE INTEGRATION; BLOCKED FOR
   VISIBLE RANKING.** The four-ply forcing-check settlement policy and existing
   proof-family thresholds are locked by the v3 frozen review and bake-off. The
   fresh 83-case v4 packet has not yet received an independent blinded review.
   Target/line therefore remains Shadow. No visible moment-ranking formula or
   new numeric weight may be implemented until candidate formulas are measured
   against coach labels.
4. **Behavior-changing success - PASS.** The approved contract separates first
   attempt, assistance, recognition, practice, later-game application, and
   retention. Completing a replay cannot declare mastery.
5. **Deferred work - PASS.** Historical Stockfish reruns, runtime LLM chess
   authority, Maia/Otter truth authority, community explanations, unlimited
   search, and a new review redesign remain out of scope.
6. **Mohit sign-off - PASS.** Mohit explicitly approved continuation on
   2026-09-04 after the current-state audit described the preserved branch,
   unfinished independent review, Shadow status, and missing canonical wiring.

## Drift and preservation audit

The preserved evidence commit `122a3cf7` is not an ancestor of current
`origin/working-code`; it is one commit ahead and five commits behind. It owns
108 changed paths, including immutable anonymized packets, blinded reviews,
proof-family validators, regression tests, and canonical verifier changes.

The dirty archived main checkout is not an implementation source. Integration
must happen hunk-by-hunk on this clean current-base branch. Evidence files keep
their original hashes and historical results; conflicts in canonical runtime
files are resolved in favor of preserving both current production behavior and
the proved Phase 3A contracts.

## Authorized continuation order

1. Import and integrity-check the preserved evidence chain on the current base.
2. Re-run all Phase 3A proof, packet, privacy, and adjacent caption regressions.
3. Freeze an independent blinded response for the untouched v4 packet, then
   create its answer key and score only after the response is complete.
4. Keep every failing or unreviewed proof family in Shadow; inspect every
   disagreement and add mechanism-level regressions rather than position IDs.
5. Build and measure candidate within-game moment rankings against independent
   coach labels; lock the winning formula from data.
6. Only after those gates pass, extend the canonical Game Review interaction
   with proved opportunities for either player and validate full-game coaching
   quality before any rollout.

## Pre-code verdict

**PASS for preservation, integration, deterministic verification, and data
measurement. BLOCKED for player-visible opportunity ranking or rollout until
the independent v4 review and ranking data lock pass.**
