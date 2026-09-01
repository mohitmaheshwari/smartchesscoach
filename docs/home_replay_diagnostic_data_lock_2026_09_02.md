# Home Replay Diagnostic — V1 Data Lock

**Status:** LOCKED for Mohit-only validation
**Date:** 2026-09-02
**Scope:** Values and selection rules needed before implementation. Wider rollout remains separately gated.

## Decision 1 — eligible coaching hypothesis

**VALUE:** V1 accepts only an active-focus hypothesis whose exact detector is Plan-authorized and whose two served positions independently pass the verified puzzle-admission and answer-redaction contracts. V1 does not introduce another recurrence threshold and does not call the hypothesis the player's “main weakness.”

**EVIDENCE:**

- `destination_safety_exact` is the only currently relevant exact detector promoted to Plan. Its sealed audit reported 200/200 semantic precision, 165/200 recall, 60/60 true negatives and zero critical adversarial errors.
- Mohit's production record contains 193 stored exact fires. Recurrence is therefore not the limiting question for his validation account.
- Detector authorization proves the narrow claim only. It does not prove peer-relative weakness or mental cause, so neither claim enters Home copy.

**REJECTED CANDIDATES:**

- Highest broad-category count: rejected because broad `piece_safety` mixes several mechanisms and cannot prove which lesson to test.
- Only Plan-authorized detector equals primary weakness: rejected because authorization measures claim safety, not personal severity.
- Peer-relative ranking for V1: rejected because comparable exact, Plan-authorized peer baselines do not yet exist across multiple families.

**MEASUREMENT METHOD:** Existing sealed promotion packet plus a 2026-09-02 read-only production aggregate. Stockfish was not rerun.

## Decision 2 — position pair

**VALUE:** Exactly two positions. Both share the same quality id and detector version. Position one comes from the player's game. Position two must have a different normalized FEN, come from a different game, and use a different moved-piece type for destination-safety V1. Both answers are independently admitted and graded.

**EVIDENCE:**

- Two positions have two distinct jobs: reconstruct the original decision and test transfer. One cannot test transfer; a third adds no new V1 result branch.
- Mohit's 193 fires span 160 games, 189 distinct positions, all four eligible piece types and all three game phases.
- The strict cross-game, cross-piece rule leaves 13,556 candidate pairs. Stronger surface separation does not create a supply cliff for the validation account.

**REJECTED CANDIDATES:**

- One own-game position: rejected because it cannot distinguish recognition from transfer.
- Same broad category: rejected because two unrelated piece-safety mechanisms would create a false comparison.
- Same or transposed position: rejected because it tests answer memory.
- Generic fallback with unproven detector identity: rejected because the second board must test the same exact decision.

**MEASUREMENT METHOD:** `backend/data/corpus_snapshots/home_replay_diagnostic_2026-09-02.json`.

## Decision 3 — result mapping

**VALUE:** Deterministic mapping from observable evidence; no score or confidence threshold.

| Evidence | V1 result |
|---|---|
| Both positions correct, no substantive help, final reason consistent | `controlled_transfer` |
| First correct but transfer position wrong or reason inconsistent | `familiar_only` |
| Correct only after Show on board or Ask one question | `prompted_recognition` |
| Both wrong independently | `current_learning_need` |
| Contracts incomplete, duplicate position, grading conflict, or unsupported answer | no result; fail closed |

`Let me try` is not substantive help. A correct move with an inconsistent reason cannot earn demonstrated transfer.

**REJECTED CANDIDATES:**

- Weighted diagnostic score: rejected because no continuous score is needed for the four product actions.
- Correct-move-only classification: rejected because it can reward a lucky move with the wrong explanation.
- Reflection before the move: rejected because it reveals what the coach is testing.

## Decision 4 — sparse evidence

**VALUE:** If two independently admitted positions do not exist, do not show the replay diagnostic. Preserve the existing curriculum action without a diagnostic claim.

**EVIDENCE:** The validation account has abundant supply. A single-position fallback would weaken the exact promise the feature is meant to validate.

**REJECTED CANDIDATES:** Single-position “mini diagnostic” and broad-category community fallback; both change what the result can honestly mean.

## Decision 5 — review cadence and improvement language

**VALUE:** Reuse the existing locked curriculum cadence: review after three analyzed games, with a 21-day calendar backstop that explicitly claims no new game evidence. Solving both boards earns controlled transfer only. Home may not say “improved” until an authorized real-game measurement exists.

**EVIDENCE:** The versioned review-opportunity snapshot found that three-game windows supplied at least six measured decisions in 99.05% of measured windows while two-game windows did so in 89.57%. Five-game windows reduced the share of users reaching the window. The 21-day path is already implemented as a check-in, not evidence.

**REJECTED CANDIDATES:** Immediate mastery, a fixed days-only review, and treating “no detector fire” as successful application.

## Decision 6 — rollout

**VALUE:** Default off; enrolled validation account only. No numeric wider-rollout threshold is locked before real diagnostic sessions exist.

**EVIDENCE:** Historical behavior predates this feature and cannot establish comprehension, answer leakage, completion or downstream-action baselines.

**REJECTED CANDIDATES:** All-user launch and thresholds derived from contaminated historical PostHog activity.
