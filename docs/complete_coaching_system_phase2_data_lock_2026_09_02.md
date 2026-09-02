# Complete Coaching System — Phase 2 Data and Migration Lock

**Date:** 2026-09-02  
**Status:** LOCKED FOR IMPLEMENTATION — Mohit said “go” after Phase 2 was named as the next phase  
**Parent scope:** `docs/complete_coaching_system_scope.md`  
**Architecture:** `docs/complete_coaching_system_spec.md`  
**Measured input:** `docs/complete_coaching_system_phase0_data_lock_2026_09_02.md`

## 1. Exact Phase 2 outcome

Phase 2 builds one additive, private evidence path. It does not change a learner's visible plan, mastery, puzzle order, caption, lesson copy, or progress state.

At the end of this phase:

- every producer declared **migrated** below emits a parseable `LessonResult v2` with a stable logical source identity;
- all shadow events append through one generic writer into the existing `learning_sessions.events` ledger;
- new server-graded puzzle attempts use an additive `puzzle_attempt.v2` document in the existing `puzzle_attempts` collection;
- a repeated submission carrying the same client submission identity cannot create a second attempt, a second recovery credit, or a second learning event;
- the canonical reducer can project one requested skill in shadow, without changing any visible mastery;
- missing assistance, reveal, identity, rating, content, proof, or provenance remains explicitly unknown and cannot be upgraded by inference.

This is evidence infrastructure, not evidence that the learner has improved.

## 2. Source-of-truth audit

Phase 2 extends existing owners; it creates no rival domain authority.

| Fact | Existing owner | Phase 2 treatment |
|---|---|---|
| Chess answer and accepted move set | `verified_puzzle_runtime.py` + stored `verified_admission` | Reused unchanged; no engine or client re-grading |
| Puzzle attempts and recovery credit | `verified_puzzle_attempt_service.py` + `puzzle_attempts` | Extended to v2 and made retry-safe |
| Lesson evidence contract | `personal_curriculum.LessonResult` | Extended additively; remains the only event contract |
| Learning event storage | `learning_sessions.events` | Generic append mechanics centralized; no new collection |
| Learner projection | `concept_mastery_service.py` | Generalized only for private shadow projection |
| Concept/content identity | `ConceptContractIndex`, with the current PIC compatibility identity | Resolved, never guessed from display labels |
| Rating and provenance | `rating_resolver.resolve_coaching_rating` | Snapshotted at attempt time |
| Detector authorization | `detector_quality.py` | Reused; no grade changes |
| Game opportunity fact | schema-18 `destination_safety_exact` | `eligible + handled/miss` may be recorded as raw shadow evidence |

The unused `CoachingPuzzleService.record_puzzle_attempt` direct insert is a bypass, not an authority. It has no repository caller and will be retired or made unreachable rather than preserved as a second write path.

## 3. Migrated producers

The following producers are inside Phase 2:

1. game-review reflection evidence already adapted by `review_learning_adapter`;
2. guided PIC practice already adapted by `review_learning_adapter`;
3. personalized lesson answers already serialized as `LessonResult v2`;
4. exact schema-18 destination-safety game opportunities, including both `handled` and `miss` when `derivation_status=ok` and `eligible=true`;
5. attempts graded through `record_verified_puzzle_attempt`, with canonical learning emission only when content/skill identity is resolvable and the Complete Coaching System flag is enabled.

Other historical lesson counters, opening quiz counters, trap counters, diagnostic counters, and bespoke progress services are not silently declared canonical. They remain legacy inputs until an explicit adapter proves equivalence.

## 4. Idempotency contract

One logical puzzle submission has one opaque `submission_id` created before the request is sent. The persisted attempt identity is a server-derived hash of:

```text
puzzle_attempt.v2 + user_id + puzzle_id + attempt_context + submission_id
```

The hash is used as the Mongo `_id`, so Mongo's built-in unique `_id` index is the concurrency boundary. A retry with the same request body returns the original stored result. A genuinely new attempt must use a new submission identity.

If an old caller supplies no submission identity, the server may preserve compatibility by generating a one-time identity, but the row is marked `idempotency_proven=false`. Such a row cannot become learner evidence. Phase 2 does not pretend a random server ID makes an already-lost client retry identity recoverable.

Lesson events preserve the deployed compatibility key derived from the event schema, origin, `source_event_id`, attempt kind, position, and application outcome. The session identity adds user and canonical skill isolation; the generic ledger stores one shadow session per user and skill and atomically filters keys already present.

## 5. Puzzle-attempt v2 contract

New rows retain current compatibility fields and add:

- `schema_version`, stable `attempt_id`, and `idempotency_proven`;
- server-graded played move, correctness, quality, puzzle/context identity, and event time;
- first-response identity when known, retry index when known, and response time when supplied;
- assistance/reveal measurement status, never an assumed “unassisted” value;
- attempt-time rating plus resolver source, platform, sample size, and as-of time;
- admission version and verdict fingerprint;
- detector, verifier, quality, content, grader, and source-event provenance when present;
- explicit `measurement_status` and `evidence_limitations`.

The server never accepts correctness, best move, weakness, rating, admission status, or mastery state from the browser.

## 6. Evidence eligibility

`LessonResult v2` remains capable of describing incomplete evidence. An incomplete event may prove exposure/learning, but it cannot prove independent performance, game use, retention, or reliability.

Current generic puzzle surfaces do not have server-owned hint/reveal sessions. Their new attempts therefore record assistance as `not_measured` and remain shadow-ineligible for independent mastery. This is intentional. The attempt stream becomes useful for integrity and later calibration without falsely claiming that the solve was unassisted.

Game opportunities are stronger because the exact detector already records comparable opportunity eligibility and an explicit outcome. They may project `handled` to `applied` and `miss` to `missed` in shadow. That projection is not displayed and is not a causal improvement claim.

## 7. No new numeric choices

Phase 2 introduces no mastery count, solve-rate threshold, retention interval, retry timeout, rating band, focus limit, or plan duration.

The following remain blocked exactly as Phase 0 locked them:

- how many solves prove independent performance;
- how many handled opportunities prove transfer or reliability;
- whether puzzle difficulty may use a human model;
- which legacy learning claims survive migration;
- any fixed result date or Elo promise.

Counts, parity rates, and test totals are acceptance evidence for the implementation, not player-learning thresholds.

## 8. Rollout and rollback

New canonical puzzle-to-lesson emission and expanded handled-opportunity capture run only when `COMPLETE_COACHING_SYSTEM_V1_ENABLED=true`. The default remains false.

Existing visible readers remain unchanged. The new reducer reports `rollout_mode=shadow` and `visible_mastery_changed=false`. Disabling the flag stops new Phase 2 emission without deleting attempts or rewriting history.

No production migration or backfill is authorized by this phase. Old rows remain intact and `measurement_unknown` where the required fields do not exist.

## 9. Acceptance evidence required

Phase 2 is complete only when focused tests prove:

- exact duplicate requests create one attempt and one event;
- different submission IDs create distinct attempts;
- server grading wins over any client claim;
- rating and admission provenance are copied from canonical server sources;
- missing assistance stays unknown and blocks independent credit;
- handled, missed, ineligible, and unavailable game facts remain distinct;
- the generic ledger isolates skills and deduplicates atomically;
- the shadow reducer rejects malformed, cross-skill, duplicate, or forged-state events;
- legacy flag-off API responses and visible mastery are unchanged.
