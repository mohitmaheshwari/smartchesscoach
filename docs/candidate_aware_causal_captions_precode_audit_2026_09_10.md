# Candidate-Aware Causal Captions — Pre-Code Audit

**Date:** 2026-09-10
**Scope:** `docs/candidate_aware_causal_captions_scope.md`
**Data lock:** `docs/candidate_aware_causal_captions_data_lock_2026_09_10.md`
**Code base:** `origin/working-code@ee9318b1`
**Result:** PASS — the measured data lock was explicitly approved before implementation began

## Six hard gates

1. **Literal UI mockup — PASS.** Section 2 of the scope shows the exact Game Review card, side-by-side board comparison, opponent opportunity, position-relative lesson question and post-move verdict. The selected compact shape is locked in data-lock section 6.
2. **Pattern/geometry headline — PASS.** Headlines name the idea—“Trading queens helps White here” and “A pawn fork was hiding here.” SAN is evidence inside the explanation, not the title.
3. **Data-derived thresholds and choices — PASS.** The candidate policy comes from a 600-position Maia bakeoff plus frozen 3,257-move Otter evidence. The three-moment cap preserves the complete natural count in 96.14% of candidate-bearing games. The validation threshold is the first 60-review count whose 39/60 preference clears the Wilson discrimination boundary. No generic centipawn soundness band is introduced.
4. **Behavior-changing success — PASS.** Gates require legal replay, exact chess truth, improved blinded coach preference, paired player recognition and later organic transfer kept separate from practice. Exposure, clicks and regenerated database fields cannot pass the feature.
5. **Deferred items remain deferred — PASS.** No broad rollout, full historical backfill, new visible ranker, public 25cp rule, Shadow promotion, broad positional assertion, community explanation, synchronous page inference or visible live-PWC model path is included.
6. **Mohit sign-off — PASS.** Mohit explicitly approved the complete scope and then explicitly approved the measured data lock on 2026-09-10 before implementation edits began.

## Existing-source ownership

| Concern | Canonical owner to extend |
|---|---|
| Move-level teaching decision | `services/caption_pipeline.py::MoveTeachingDecision` |
| Player-facing explanation | `services/caption_pipeline.py::CaptionExplanation` |
| Verified causal union | `services/caption_facts.py::ReviewTeachingCause` |
| Position-relative lesson question | `services/teaching_reason_contracts.py::TeachingReasonBundle` |
| Central decision builder | `services/caption_pipeline.py::build_move_teaching_decision` |
| Human-policy evidence | `services/human_policy_runtime.py` |
| Analysis-time human enrichment | `services/human_chess_analysis_enrichment.py` |
| New-game lifecycle | `analysis_worker.py` |
| Review cause projection | `services/game_review_contracts.py` and `game_review_event_adapter.py` |
| Stored branch legality/settlement | `services/stored_line_verifier.py` |
| Current game-level selection | existing deployed Game Review planner; unchanged in V1 |
| Game Review rendering/replay | `frontend/src/components/GameDecryptionV5.jsx` and existing `coach_line_moves` path |
| Personalized lesson rendering | `frontend/src/components/training/PersonalizedLessonWorkspace.jsx` |
| Opening authority | `data/opening_curriculum.json` via the existing unified opening source |
| Trap authority | `data/traps.json` via `services/trap_library.py` |
| Exact ending authority | existing Fathom/Syzygy evidence and canonical endgame theory service |
| Detector/surface authority | `services/detector_quality.py` |
| Learning and transfer | existing lesson-result ledger and organic-game transfer contracts |

No new opening, trap, endgame, principle, pattern, weakness, mastery or caption-template catalog is authorized. Candidate enrichment is evidence, not a rival chess-knowledge source.

## Forecasted bottleneck

The likely bottleneck is not React or model inference. It is the share of selected positions where a candidate branch reaches a complete, surface-authorized cause and settlement without a false material or positional inference.

The first implementation measurement must therefore report:

- selected positions;
- candidate-set size after deduplication;
- complete causes by family;
- abstentions by exact reason;
- exchange-accounting rejections;
- branch-verifier failures;
- engine wall time and peak memory;
- player-visible moments after the truth gate.

If coverage collapses, the answer is not to relax the verifier. The phase stops and names the missing proof family.

## Implementation sequence after data-lock approval

1. **Truth repair:** correct captured-value accounting and freeze Qxg3, Bxc3, recapture, x-ray, pinned recapture, promotion and truncated-payoff regressions.
2. **Typed comparison evidence:** extend the canonical cause/decision/explanation contracts with played and candidate branches, immutable provenance and safe public projection.
3. **Bounded enrichment:** use the locked candidate policy in the existing analysis lifecycle and a resumable historical job; remove the wasteful review-regeneration MultiPV path.
4. **Deterministic composition:** produce the headline, two-sentence explanation, replay, visual focus and memory cue only from verified facts and canonical knowledge identities.
5. **Game Review wiring:** expose at most three enriched moments, preserve the existing ranker, and generalize the current board replay control.
6. **Lesson wiring:** derive position-relative options and direct verdicts from the same reason bundle; keep static questions only as fallback.
7. **PWC boundary:** store/consume the schema in Shadow while live model inference remains off.
8. **Migration and gates:** dry-run the ten-game account cohort, reconcile every row, run blinded truth/preference review, then authenticated existing-game and new-game journeys.

Each step must leave a backward-compatible, default-off state. A later step may not weaken an earlier truth gate to increase coverage.

## Required tests

### Backend unit and adversarial

- `backend/tests/test_caption_pipeline_boundary.py`
- `backend/tests/test_game_review_contracts.py`
- `backend/tests/test_human_chess_analysis_enrichment.py`
- `backend/tests/test_personalized_lesson_contract.py`
- `backend/tests/test_personalized_lesson_adapter.py`
- `backend/tests/test_home_teaching_reason_bundle.py`
- `backend/tests/test_unsafe_recapture_pawn_fork_caption.py`
- new exchange-accounting and candidate-evidence contract tests
- new no-engine/no-model-on-review-read process test
- new idempotent enrichment and fingerprint tests

### Backend integration

- V5 generation from stored candidate evidence;
- analysis-worker enrichment without a second full-game analysis;
- historical dry-run/apply/rerun reconciliation;
- missing model, missing engine branch, rejected fingerprint and unsupported cause fallbacks;
- authenticated existing-game and newly imported-game response contracts.

### Frontend

- `frontend/src/components/training/PersonalizedLessonWorkspace.test.jsx`
- new `GameDecryptionV5` compact comparison and replay tests;
- no answer leakage before commit;
- legal one-step-at-a-time replay, reset and keyboard behavior;
- unchanged legacy rendering outside enrollment.

### Regression and release

- core backend suite required by repository instructions;
- clean frontend production build;
- focused caption, detector-authority and exact-endgame suites;
- `git diff --check`;
- generated packet privacy scan;
- deployed authenticated reach check before any cohort beyond the validation account.

## Entry contract

Implementation may begin only after Mohit explicitly approves the measured data lock. That approval authorizes the bounded implementation sequence above, not broad rollout or production deployment.
