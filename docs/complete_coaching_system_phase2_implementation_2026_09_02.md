# Complete Coaching System — Phase 2 Implementation Record

**Date:** 2026-09-02
**Status:** IMPLEMENTED LOCALLY; additive shadow path, default-off, not deployed
**Approved lock:** docs/complete_coaching_system_phase2_data_lock_2026_09_02.md

## Delivered

1. learning_evidence_ledger.py is the single generic append boundary for migrated shadow LessonResult v2 events. It reuses learning_sessions, keeps the already-deployed PIC event-key formula, isolates sessions by canonical skill, rejects mismatched outer/nested identities, and atomically filters existing idempotency keys.
2. verified_puzzle_attempt_service.py now writes additive puzzle_attempt.v2 rows through a Mongo _id upsert. A client UUID is hashed with server-owned user, puzzle, and context identity. The UUID is also bound to the exact move, grader version, board, answer proof, and admission verdict; reusing it with a different move or changed proof is rejected.
3. Canonical attempt rows snapshot server grading, canonical rating provenance, admission/proof fingerprints, and explicit measurement limits. Missing client retry identity, rating, canonical content identity, assistance, or reveal state is not guessed.
4. Recovery credit has one unique user+puzzle claim. The API distinguishes “this attempt owns the credit” from “the credit was newly claimed now,” so a network retry cannot repeat downstream decay refreshes.
5. All routed puzzle surfaces now create an RFC 4122 v4 submission identity before sending, retain it across transport failure, and rotate only after the server answers: Challenge, Daily Fix, Game Review, Mission, Opening Walkthrough, Prescribed Training, and Skill Drill.
6. Community-puzzle compatibility counters no longer increment on canonical duplicate retries. The obsolete direct CoachingPuzzleService attempt writer was removed after a zero-caller audit.
7. Existing review reflections, guided PIC practice, personalized lesson answers, exact game misses, and exact handled opportunities share the canonical event contract. Personalized operational session events stay compatible; their shadow copy goes through the generic ledger.
8. Schema-18 exact handled evidence is captured only when derivation is ok, the opportunity is eligible, and the outcome is explicit. Historic exact fires missing newer fields remain available only as incomplete evidence; they cannot prove independent performance or application.
9. The generic mastery reducer is private and fail-closed. It rejects malformed events, cross-skill events, duplicate source identities, forged earned states, and outer/nested identity disagreement. It always reports visible_mastery_changed=false.

## Retry and evidence guarantees

The focused acceptance suite proves:

- the same submission UUID produces one canonical attempt, one recovery-credit record, and one shadow event;
- different UUIDs produce different attempts;
- one UUID cannot be reused for a different move;
- invalid or missing client identity cannot become learning evidence;
- rating and proof provenance come from server owners;
- assistance/reveal remain not_measured on current generic puzzle surfaces;
- incomplete correct work earns at most Learning;
- handled, missed, ineligible, and unavailable game opportunities remain distinct;
- legacy community attempt/stat counters do not double-count a retry;
- personalized lesson retries append one canonical shadow event.

## Verification

    Final combined Phase 2 + adjacent backend regression gate: 251 passed, 55 skipped
    In-scope frontend suites: 30 passed across 9 suites
    All 21 changed/new Python files: py_compile passed
    Frontend production bundle: compiled successfully in normal warning mode

The repository-mandated backend/tests/test_all_flows.py remains externally blocked in this isolated worktree: it immediately opens a live HTTP connection and fails because no backend server is running. A widest-collection run, excluding that script, was stopped after more than three minutes without a final summary because other live/environment tests do not fail or skip cleanly. The strict CI=true frontend build remains red on the repository's pre-existing hook-dependency warnings; the new submission hook contributes no warning. One extra untouched curriculum-copy test also has a pre-existing stale string expectation. None is counted as green.

## Explicitly unchanged

- no visible mastery, plan, focus, lesson wording, puzzle order, caption, or progress state;
- no detector grade, chess rule, accepted puzzle move, content mapping, or rating formula;
- no production Mongo record, backfill, migration, feature flag, deployment, or push;
- no Stockfish, Maia, Otter, Fathom, LLM, or network inference;
- no numeric mastery, retention, solve-rate, or improvement threshold.

Disabling COMPLETE_COACHING_SYSTEM_V1_ENABLED stops new canonical shadow emission. Additive v2 attempts remain an audit trail; existing visible readers continue to use their legacy paths.
