# Acquisition Readiness Phase 6 - Hook Behavior Slice 17 Evidence

**Date:** 2026-09-07
**Scope:** `docs/acquisition_readiness_phase6_hook_behavior_precode_audit_2026_09_06.md`
**Status:** SOURCE COMPLETE - independent review pending

## Bounded change

Reflect now treats all coaching data for a position as one owned request
bundle instead of five overlapping effects:

- changing the current game or moment aborts and invalidates the prior
  explanation, contextual tags, quick tags, clock context, and intent
  hypotheses;
- every moment-owned UI field is cleared before replacement data can render;
- the new moment always requests its own explanation. It can no longer inherit
  a non-null prior explanation and silently skip the fetch;
- the arrow memo reads one coherent `currentMoment` identity; and
- a late moments-list response from a prior game cannot replace the selected
  game's positions or stop its loading state.

No hook warning was suppressed. The requests and response contracts are
unchanged.

## Behavioral evidence

`ReflectEffects.test.jsx` proves:

1. after switching from game 1 to game 2, the game-2 moment and explanation
   appear;
2. resolving game 1's delayed explanation afterward cannot replace game 2's
   coach explanation; and
3. resolving game 1's delayed moments list after game 2 is selected cannot
   replace game 2's current position.

```text
focused Reflect: 1 suite / 2 tests passed
full frontend:    49 suites / 208 tests passed
ordinary build:   exit 0
strict build:     exit 1, exactly 23 exhaustive-deps findings
Reflect findings: 0
baseline:         27 findings
reduction:        4 findings
```

The 23 remaining findings are confined to `CoachPlay.jsx` and
`LabClassic.jsx`. No backend, endpoint contract, database, production flag,
push, deployment, or product-score change is included.
