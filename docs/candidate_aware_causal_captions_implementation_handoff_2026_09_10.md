# Candidate-Aware Causal Captions — Implementation Handoff

**Date:** 2026-09-10
**Branch:** `codex/candidate-aware-causal-captions-v1`
**Base:** `origin/working-code@ee9318b1`
**Status:** implemented and locally verified, including the destination-safety
v1→v2 release migration; not pushed, backfilled or deployed

## Critical release correction after independent review

The first implementation correctly bumped the destination-safety detector and
puzzle proof to v2, but initially made the puzzle-admission reader require v2
immediately. Production still stores thousands of matched v1/v1 admissions, so
deploying that shape—even with all three candidate-caption flags off—would have
removed those puzzles from every runtime pool. The candidate flags do not guard
detector identity or verified-puzzle admission.

The corrected release treats this as a bounded schema migration:

- stored puzzle admissions accept exactly the matched `(detector v1, proof v1)`
  or `(detector v2, proof v2)` pair during the transition;
- cross-version and unknown pairs still fail closed;
- all new writers and provenance stamps use the canonical v2 constant from
  `destination_safety_detector.py`;
- an active focus is pinned to its stored detector version until the focus
  migration rebuilds its baseline, so v1 and v2 decision semantics are never
  silently combined;
- the existing admission backfill now has a destination-safety mode that
  stages the complete two-pool migration, refuses partial/limited apply, binds
  apply to the immediately preceding dry-run row count, and verifies that zero
  legacy destination admissions remain; and
- the existing focus migration refreshes a stale v1 exact focus instead of
  incorrectly calling it already migrated.

The temporary v1/v1 admission pair must be removed in a later cleanup only
after both puzzle pools report zero legacy rows and all active exact focuses
carry v2 provenance.

## Player outcome

Game Review can now attach one compact, verified comparison to each of at most three already-selected learning moments:

- what happened after the played move;
- what the stronger stored move was trying to achieve;
- one button that plays both continuations on the board; and
- one short memory rule that applies beyond the position.

The personalized piece-safety lesson no longer has to ask the same three introspection choices before every position. When the current Plan-grade destination-safety proof owns the item, the player moves first and the server asks only questions established by that exact board: what attacked the origin square, whether the destination can be captured, whether the move counterattacks, and whether a recapture exists. Multi-part positions are taught one connection at a time. Unsupported or stale evidence falls back to the existing lesson.

## Single-source ownership

| Responsibility | Canonical owner | This implementation |
|---|---|---|
| Exact destination safety and exchange accounting | `services/destination_safety_detector.py` | Extends the existing promoted fact and reason-bundle owner; no second detector |
| Exact review causes | `services/caption_facts.py` | Reuses authorized `LegalMaterialLossCause`, `VerifiedLineCause` and exact-endgame causes |
| Human move relevance | `services/human_policy_runtime.py` | Consumes stored Maia/Otter evidence only; never establishes correctness |
| Candidate branch evidence | `services/candidate_caption_evidence.py` | New immutable, fingerprinted evidence contract and bounded writer |
| Featured-moment selection | `services/game_review_planner.py` | Keeps the existing ranker; only raises the locked cap from two to three |
| Player-facing explanation | `services/caption_pipeline.py` | The only composer of the candidate comparison and memory cue |
| V5 storage and regeneration | `services/game_decryption_v5_service.py` | Reads stored evidence; never launches Stockfish or a human model while rendering |
| Authenticated visibility | `routes/coach.py` | Projects comparisons only into the personalized variant and strips them from legacy/control |
| Lesson delivery | `services/personalized_lesson_adapter.py` + `services/teaching_engine.py` | Requires the same exact quality id, current detector version and Plan authorization |
| Review UI | `CandidateComparisonCard.jsx` + `GameDecryptionV5.jsx` | Shows compact copy and plays both legal stored lines on the existing board |
| Bounded historical enrichment | `scripts/backfill_candidate_caption_evidence.py` | One explicit user, at most ten eligible games, dry-run fingerprint before apply |

No new opening, trap, endgame, positional or mental-model assertion is introduced. No LLM is a chess authority.

## Runtime boundaries

Three independent flags are declared in both compose files and default off:

- `CANDIDATE_CAPTION_ENRICHMENT_ENABLED` — background evidence creation during normal analysis;
- `CANDIDATE_CAUSAL_CAPTIONS_ENABLED` — authenticated personalized Game Review exposure; and
- `CANDIDATE_LESSON_REASONS_ENABLED` — exact position-relative lesson questions.

Page reads start no Stockfish process and make no Maia, Otter or LLM call. Background analysis starts one persistent Stockfish process lazily only when an already-selected moment needs missing candidate branches, and searches only the bounded root candidates. Existing played and best continuations are reused first.

## Data and reconciliation

Candidate evidence is additive and source-bound. Its fingerprint includes the normalized source row, legal replayed branches, engine provenance and human-policy provenance. A packet is classified as `missing`, `current`, `stale`, `changed` or `rejected`; invalid evidence cannot reach a caption.

The backfill command is dry-run by default. `--apply` requires the exact plan fingerprint printed by the prior dry-run and rechecks the analysis document, V5 version, FEN, played move and evaluation fields before every atomic write. Reports contain hashes and aggregate counts, not user identities or game ids.

The first allowed production sequence is now:

1. **Before changing the live detector baseline**, finish the still-pending
   authenticated checkpoint-game → newly imported organic-game E2E on the
   currently deployed `ee9318b1` release. If it is not run, record that as an
   explicit unresolved release gate; do not imply it passed.
2. Backup and restore-test `community_puzzles`,
   `community_training_positions`, `move_observations`, `user_active_focus`,
   and the game records carrying PIC evidence.
3. Deploy both candidate-caption commits with all three `CANDIDATE_*` flags
   false. This deploy must include the matched v1/v1 + v2/v2 admission window;
   do not deploy the original v2-only reader.
4. Re-grade destination-safety puzzle admissions **after deploy, never before**:

   ```bash
   python backend/scripts/backfill_verified_puzzle_admission.py \
     --quality-id gap:piece_safety:destination_safety_exact
   # Copy rows=N from the reviewed dry-run into --expect-rows.
   python backend/scripts/backfill_verified_puzzle_admission.py \
     --quality-id gap:piece_safety:destination_safety_exact \
     --apply --confirm destination-safety-v2 --expect-rows N
   ```

   Apply is valid only when both pools are selected, no `--limit` is present,
   the dry-run count still matches, the zero-violation gate passes, and the
   post-write report shows `destination_legacy_rows_remaining=0` for each pool.
   Compare admitted/quarantined/reclassified totals with the dry-run; do not
   require the old approved count to stay constant because v1 false positives
   must be honestly reclassified.
5. Re-derive the current v2 observation facts, first dry-run and then apply:

   ```bash
   python backend/scripts/backfill_move_observations.py --all
   python backend/scripts/backfill_move_observations.py --all --apply \
     --confirm phase8-observations
   ```

6. Only after the v2 observations are present, dry-run and apply the existing
   focus migration (one pilot first; `--all` remains a separate cohort
   decision). This intentionally rebuilds the focus baseline under v2 rather
   than mixing v1 and v2 decisions:

   ```bash
   python backend/scripts/migrate_destination_safety_focus.py \
     --email <pilot-email>
   python backend/scripts/migrate_destination_safety_focus.py \
     --email <pilot-email> --apply --confirm phase8-focus-bundles
   ```

7. Run `backfill_candidate_caption_evidence.py` for the one explicitly enrolled
   user without `--apply`; inspect eligible games, searches, abstentions,
   engine time and storage estimate; then apply only with its exact printed
   plan fingerprint.
8. Enable candidate-caption visibility only for that account and complete an
   authenticated existing-review plus newly imported-game journey. Keep wider
   rollout blocked on the locked blinded chess-quality and player-recognition
   validation.

## Verification completed

- Destination version transition, no-dark-window admission, full-pool apply
  safeguards, focus-version pinning, v1 focus refresh, and Phase 8 prerequisite
  contracts: **160 passed**.
- Expanded affected backend gate after the correction: **391 passed**; the same
  six caption-boundary failures already documented and reproduced at the clean
  base remain unrelated to this change.

- New candidate evidence, exchange accounting and runtime-boundary tests: **52 passed**.
- Review-contract gate: **75 passed**.
- Detector, puzzle-proof, lesson, human-policy and endgame affected gate: **161 passed**.
- Expanded affected backend gate: **193 passed, 15 skipped** after excluding one assertion independently proven to fail identically at the clean base.
- Caption-pipeline comparison: the same six legacy failures reproduce byte-for-byte at the clean base; no new failure was introduced.
- Frontend focused interaction gate: **14 passed across 4 suites**.
- Full frontend gate: **253 passed across 57 passing suites**; two Activation Hub failures reproduce identically at the clean base and touch no changed file.
- Production frontend build: **passed**. Existing source-map and bundle-size warnings remain.
- Python compilation of the changed backend modules: **passed**.

The repository's HTTP-style `tests/test_all_flows.py` was attempted but is inconclusive locally because it requires a running backend and stopped at the first connection refusal. It is not reported as green.

## Honest boundary

This release makes exact destination-safety lessons and already-authorized concrete review causes more teachable. It does not make every chess position explainable. Unsupported proof families abstain; broad positional ideas, non-best sound alternatives and live Play-with-Coach human-policy inference remain future governed work.
