# Candidate-Aware Causal Captions — Implementation Handoff

**Date:** 2026-09-10
**Branch:** `codex/candidate-aware-causal-captions-v1`
**Base:** `origin/working-code@ee9318b1`
**Status:** implemented and locally verified; not pushed, backfilled or deployed

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

The first allowed production sequence remains:

1. run the script for one explicitly enrolled user without `--apply`;
2. inspect eligible games, searches, abstentions, engine time and storage estimate;
3. rerun with `--apply --confirm-plan <fingerprint>`;
4. enable personalized visibility only for that account;
5. complete an authenticated existing-review and newly-imported-game journey;
6. perform the locked blinded chess-quality and player-recognition validation before any larger cohort.

## Verification completed

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
