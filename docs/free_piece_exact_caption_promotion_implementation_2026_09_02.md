# Free-Piece Exact Caption Promotion — Implementation Record

**Date:** 2026-09-02
**Status:** IMPLEMENTED LOCALLY; not backfilled, pushed or deployed
**Scope:** `docs/free_piece_exact_caption_promotion_scope.md`
**Data lock:** `docs/free_piece_exact_caption_promotion_data_lock_2026_09_02.md`

## Delivered

1. `build_free_piece_exact_caption_promotion_packet.py` performs a read-only replay over both admitted puzzle pools. Its gold path parses the board and legal moves, identifies the captured piece directly, pushes the stored best move, and enumerates every legal immediate recapture without importing the candidate detector.
2. `free_piece_exact_caption_promotion_v1.json` freezes 50 distinct-source fires and 20 stratified near-negatives. It contains board/proof facts and one-way source keys, but no user, account or game identity.
3. `tactic:free_piece_exact` is promoted from Shadow to Caption. Prompt, Plan and Mastery remain false under the central authorization contract.
4. The existing verified-puzzle admission contract now carries an optional `caption_concept_id` only for an independently verified Caption-grade fact. `concept_id` remains reserved for Prompt/Plan-grade drill identity.
5. The existing centralized verified-puzzle feedback renderer may use `caption_concept_id` after an attempt. Skill extraction, plan selection and mastery continue to require `concept_id` and stronger authorization.
6. Empty `caption_concept_id` values are omitted from serialized verdicts. Existing v2 documents retain their original shape and fingerprint behavior; unrelated positions will not be rewritten merely because this additive field exists.

## Evidence result

The reproducible production-container replay used stored evidence only:

| Gate | Result |
|---|---:|
| Documents scanned | 52,060 |
| Existing exact candidates | 1,607 |
| Distinct candidate sources | 1,305 |
| Full-population independent exact passes | 1,607 / 1,607 |
| Stored fact mismatches | 0 |
| Candidate replay failures | 0 |
| Promotion fires | 50 / 50 true |
| Near-negative controls | 20 / 20 abstained |
| Raw semantic precision | 100% |
| 95% Wilson lower bound | 92.87% |
| Critical adversarial errors | 0 |

The selected positives span both pools and every claimed target type: knight, bishop, rook and queen. The negative packet contains five cases each for immediate recapture, pawn/lower-value capture, non-capture and insufficient stored consequence.

Packet selection fingerprint:

    2c758e25f505847438fd2819349f4410a077f9d802753551facbc1546acdd752

Canonical packet SHA-256:

    32d4bde64a14f01c96a0a4ece896e88f5c0e3a7a505be7bed948904f5f7a1c8e

Stockfish runs, LLM calls and database writes were all zero.

## Authorization boundary discovered and fixed

Before this phase, `AdmissionStatus.SPECIFIC` meant both “the exact fact is proved” and “the concept may identify a drill.” It therefore required the Prompt surface, which in turn requires Plan grade. Promoting this detector to Caption alone would have produced no specific explanation; changing it to Plan would have overstated the evidence.

The implementation keeps the stronger boundary intact:

- `caption_concept_id`: exact, post-answer explanation only;
- `concept_id`: persistent prompt/drill identity, still absent here;
- `broad_category`: existing `missed_tactic` compatibility and recovery behavior;
- no free-piece skill node, focus, recurrence, plan or mastery state.

This separation also applies safely to other already-Caption-grade exact facts without granting them Prompt authority. Existing stored rows remain servable and unchanged. They will show the new exact feedback only after a separately approved admission reconciliation/backfill; that operation is outside this phase.

## Verification

- Focused evidence/admission/feedback/runtime/Phase 2 suite: **66 passed**.
- Broad Complete Coaching, puzzle and training suite: **165 passed, 10 skipped**.
- Every direct test dependent on detector authorization, verified admission or verified feedback: **313 passed**.
- All 50 selected captions were rendered from fresh verdicts and checked for the exact move, piece, square and reusable action.
- Voice audit: clean for the 600–1500 audience; no parallel renderer was added.
- `git diff --check` and changed-file Python compilation are required again immediately before commit.

## Explicitly unchanged

- no frontend component, route, visual design or API contract;
- no accepted answer, Stockfish result, detector geometry or target-value threshold;
- no persistent prompt, learner focus, plan, mastery, skill tree or improvement claim;
- no production record, backfill, migration, feature flag, push or deployment;
- no Maia, Otter, Fathom, runtime LLM or fresh Stockfish work.
