# Acquisition Readiness Phase 6 - Hook Behavior Slice 17 Evidence

**Date:** 2026-09-07
**Scope:** `docs/acquisition_readiness_phase6_hook_behavior_precode_audit_2026_09_06.md`
**Status:** CORRECTED AND INDEPENDENTLY APPROVED

## Bounded change

Reflect now treats all coaching data and user actions for a position as one
owned request bundle instead of five overlapping effects:

- changing the current game or moment aborts and invalidates the prior
  explanation, contextual tags, quick tags, clock context, and intent
  hypotheses;
- every moment-owned UI field is cleared before replacement data can render;
- the new moment always requests its own explanation. It can no longer inherit
  a non-null prior explanation and silently skip the fetch;
- the arrow memo reads one coherent `currentMoment` identity; and
- a late moments-list response from a prior game cannot replace the selected
  game's positions or stop its loading state;
- gap analysis and both reflection-submit paths snapshot the exact game and
  move, share an abort signal, and guard every post-await write and timer; and
- moments cannot request detail for a newly selected game until their own
  `momentsOwnerGameId` proves that they belong to that game.

No hook warning was suppressed. The requests and response contracts are
unchanged.

## Behavioral evidence

`ReflectEffects.test.jsx` proves:

1. after switching from game 1 to game 2, the game-2 moment and explanation
   appear;
2. resolving game 1's delayed explanation afterward cannot replace game 2's
   coach explanation; and
3. resolving game 1's delayed moments list after game 2 is selected cannot
   replace game 2's current position;
4. switching games never dispatches a new-game request with the old move;
5. a late gap analysis cannot continue into submission or paint the new game;
   and
6. a late V1 submission cannot paint its diagnosis into the new game.

Independent review approved exact correction commit `c3a98e3f`. Transplanting
the focused suite to exact parent `6f8f6531` produced three failures out of
five tests: the wrong-game move request, stale gap continuation, and stale
submission paint. That is the intended discrimination evidence.

```text
focused Reflect: 1 suite / 5 tests passed
full frontend:    50 suites / 217 tests passed
ordinary build:   exit 0
strict build:     exit 1, exactly 15 exhaustive-deps findings
Reflect findings: 0
parent transplant: 3 failures / 5 tests
```

The 15 findings remaining at the correction commit were confined to
`CoachPlay.jsx`. No backend, endpoint contract, database, production flag,
push, deployment, or product-score change is included.
